#
# Copyright The NOMAD Authors.
#
# This file is part of NOMAD. See https://nomad-lab.eu for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Tests for the pynxtools Igor reader plugin."""

import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from igor2 import binarywave
from pynxtools.dataconverter.convert import get_reader
from pynxtools.dataconverter.template import Template
from pynxtools.testing.nexus_conversion import ReaderTest

from pynxtools_igor.reader import parse_note

READER_NAME = "igor"
READER_CLASS = get_reader(READER_NAME)
NXDLS = ["NXroot"]

# Define lines/sections to be ignored in _all_ test cases
ignore_lines_all_tests: list = []
ignore_sections_all_tests: dict = {}

data_dir_path = Path(__file__).parent / "data"

# Test cases should be [("files", ignore_lines, ignore_sections, "test-id")]
test_cases: list[tuple[list[str], list[Any], dict[Any, Any], str]] = [
    (
        [
            "config_file.json",
            "Norm_0057.ibw",
            "Norm_0059.ibw",
            "example_ibw.nxs",
            "ibw_ref_output.txt",
        ],
        [],
        {},
        "ibw-to-nxs",
    ),
    (
        [
            "config_file.json",
            "Norm_0057.ibw",
            "Norm_0059.ibw",
            "Norm57.yaml.entry",
            "example_ibw_entry.nxs",
            "ibw_entry_ref_output.txt",
        ],
        [],
        {},
        "ibw-to-nxs-with-entry",
    ),
    (
        [
            "config_file.json",
            "Fig2a.pxp",
            "Scan57_59.yaml.entry",
            "example_pxp.nxs",
            "pxp_ref_output.txt",
        ],
        [],
        {},
        "pxp-to-nxs-with-entry",
    ),
]

test_params: list[Any] = []
for test_case in test_cases:
    for nxdl in NXDLS:
        test_params += [
            pytest.param(
                nxdl,
                test_case[0],
                test_case[1],
                test_case[2],
                id=f"{test_case[3]}-{nxdl.lower()}",
            )
        ]


@pytest.mark.parametrize(
    "nxdl, files, ignore_lines, ignore_sections",
    test_params,
)
def test_nexus_conversion(  # noqa: PLR0917
    nxdl,
    files,
    ignore_lines,
    ignore_sections,
    tmp_path,
    caplog,
):
    """
    Test Igor reader

    Parameters
    ----------
    nxdl : str
        Name of the NXDL application definition that is to be tested by
        this reader plugin.
    files : str
        All files that should go into the test.
    ignore_lines: dict[str, list[str]]
        Lines within the log files to ignore.
    ignore_sections: dict[str, list[str]]
        Subsections of the log files to ignore.
    tmp_path : pathlib.PosixPath
        Pytest fixture variable, used to clean up the files generated during
        the test.
    caplog : _pytest.logging.LogCaptureFixture
        Pytest fixture variable, used to capture the log messages during the
        test.

    Returns
    -------
    None.

    """
    caplog.clear()

    files_or_dir = [str(data_dir_path / file) for file in files]

    ignore_lines: list[str] = ignore_lines_all_tests + ignore_lines
    ignore_sections: dict[str, list[str]] = ignore_sections_all_tests | ignore_sections

    test = ReaderTest(
        nxdl=nxdl,
        reader_name=READER_NAME,
        files_or_dir=files_or_dir,
        tmp_path=tmp_path,
        caplog=caplog,
    )
    test.convert_to_nexus(caplog_level="WARNING", ignore_undocumented=True)
    test.check_reproducibility_of_nexus(
        ignore_lines=ignore_lines, ignore_sections=ignore_sections
    )


def test_parse_note_keeps_values_with_spaces():
    """Wave-note values with spaces or "=" must survive (B14)."""
    note = b"DATE=2018 4 26;HOUR=16:13:14;\r\nCOMMENT=a=b c\nnot a pair\na=1 b=2"
    assert parse_note(note) == {
        "DATE": "2018 4 26",
        "HOUR": "16:13:14",
        "COMMENT": "a=b c",
        "a": "1",
        "b": "2",
    }


def test_parse_note_of_example_ibw():
    """All pairs of the ;-separated note in the example file are read (B14)."""
    notes = parse_note(
        binarywave.load(Path(__file__).parent / "data" / "Norm_0057.ibw")["wave"][
            "note"
        ]
    )
    assert notes["SCAN_N"] == "57"
    assert notes["HOUR"] == "16:13:14"
    # tests/data/Norm_0057.ibw was written with a Korean locale:
    # its DATE note entry is "2018년 4 26일 목" (year, month, day, weekday).
    assert notes["DATE"].startswith("2018")
    assert " 4 26" in notes["DATE"]


def _ibw_entries(*files: Path) -> set[str]:
    """Read the given ibw files with the igor reader and return the entry names."""
    reader = READER_CLASS()
    reader.read(template=Template(), file_paths=tuple(str(f) for f in files))
    return set(reader.entries)


def _copy_example_ibw(*targets: Path) -> list[Path]:
    """Copy the example ibw file to each target path (folders are created)."""
    source = Path(__file__).parent / "data" / "Norm_0057.ibw"
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, target)
    return list(targets)


def test_ibw_entry_names_keep_dots(tmp_path):
    """
    File names with dots must give separate entries
    (Bug B31 in https://github.com/FAIRmat-NFDI/pynxtools-plugin-audit/blob/main/pynxtools-unification/FINDINGS.md).
    """
    # The entry name used to be everything before the first dot, so a.1.ibw
    # and a.2.ibw both became "a" and the second file overwrote the first.
    # Now the full name without the extension is used.
    files = _copy_example_ibw(tmp_path / "a.1.ibw", tmp_path / "a.2.ibw")
    assert _ibw_entries(*files) == {"a.1", "a.2"}


def test_ibw_same_name_in_different_folders(tmp_path):
    """Same file name in two folders: the folder name is prepended (B31)."""
    # x/scan.ibw and y/scan.ibw would both be "scan", so both files get their
    # folder name in front: x__scan and y__scan.
    files = _copy_example_ibw(tmp_path / "x" / "scan.ibw", tmp_path / "y" / "scan.ibw")
    assert _ibw_entries(*files) == {"x__scan", "y__scan"}


def test_ibw_same_folder_name_adds_more_folders(tmp_path):
    """If folder_name still clashes, the next folder level is prepended (B31)."""
    # a/data/scan.ibw and b/data/scan.ibw would both be "data__scan", so one
    # more folder level is added: a__data__scan and b__data__scan.
    files = _copy_example_ibw(
        tmp_path / "a" / "data" / "scan.ibw", tmp_path / "b" / "data" / "scan.ibw"
    )
    assert _ibw_entries(*files) == {"a__data__scan", "b__data__scan"}


def test_ibw_same_file_twice_is_read_once(tmp_path):
    """The same file given twice gives one entry (B31)."""
    # Passing the identical path twice is not a name clash but a duplicate
    # input: the file is read once (with a warning), not into two entries.
    (file,) = _copy_example_ibw(tmp_path / "scan.ibw")
    assert _ibw_entries(file, file) == {"scan"}


def _entry_file(tmp_path: Path, entries: dict[str, Any]) -> Path:
    """Write an igor entry file (yaml) and return its path."""
    entry_file = tmp_path / "scans.yaml.entry"
    entry_file.write_text(yaml.safe_dump(entries), encoding="utf-8")
    return entry_file


def test_entry_file_name_matching_several_ibw_files_raises(tmp_path):
    """An entry file name that fits several ibw files must raise an error (B31)."""
    # x/scan.ibw and y/scan.ibw both end in "scan.ibw", so an entry file with
    # data: scan.ibw used to put both files into the same entry, and the
    # second overwrote the first.
    files = _copy_example_ibw(tmp_path / "x" / "scan.ibw", tmp_path / "y" / "scan.ibw")
    entry_file = _entry_file(tmp_path, {"my_scan": {"data": "scan.ibw"}})
    with pytest.raises(ValueError, match=r"matches several files"):
        _ibw_entries(*files, entry_file)


def test_entry_file_accepts_path_with_folder(tmp_path):
    """An entry file can name an ibw file by a path with its folder (B31)."""
    # data: x/scan.ibw picks exactly one of the two files; the other one gets
    # an entry name derived from its file name.
    files = _copy_example_ibw(tmp_path / "x" / "scan.ibw", tmp_path / "y" / "scan.ibw")
    entry_file = _entry_file(tmp_path, {"my_scan": {"data": "x/scan.ibw"}})
    assert _ibw_entries(*files, entry_file) == {"my_scan", "scan"}
