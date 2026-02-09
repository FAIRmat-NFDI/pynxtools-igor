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
"""Igor pro reader implementation for the DataConverter."""

import logging
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from igor2 import binarywave, packed
from pynxtools.dataconverter.readers.multi.reader import MultiFormatReader
from pynxtools.dataconverter.readers.utils import parse_yml

logger = logging.getLogger("pynxtools")


def parse_note(bnote: bytes) -> dict[str, Any]:
    """
    Parsers the note field of the igor binarywave file.
    It assumes that the note field contains key-value pairs of the
    form 'key=value' separated by newlines.

    Args:
        bnote (bytes): The bytes of the binarywave note field.

    Returns:
        Dict[str, Any]: The dictionary of the parsed note field.
    """
    note = bnote.decode("utf-8").replace("\r", "\n")
    notes = {}
    for line in note.split():
        split = line.split("=")
        if len(split) == 2:
            key, val = split
            notes[key] = val

    return notes


def axis_from(ibw_data: dict[str, Any], dim: int) -> np.ndarray:
    """
    Returns the axis values for a given dimension from the wave header.

    Args:
        ibw_data (Dict[str, Any]): The ibw data containing the wave_header.
        dim (int): The dimension to return the axis for.

    Returns:
        np.ndarray: The axis values.
    """
    wave_header = ibw_data["wave"]["wave_header"]
    return (
        wave_header["sfA"][dim] * np.arange(wave_header["nDim"][dim])
        + wave_header["sfB"][dim]
    )


def axis_units_from(ibw_data: dict[str, Any], dim: int) -> str:
    """ "
    Returns the unit for a given dimension from the wave header.

    Args:
        ibw_data (Dict[str, Any]): The ibw data containing the wave_header.
        dim (int): The dimension to return the unit for.

    Returns:
        str: The axis units
    """
    unit_arr = ibw_data["wave"]["wave_header"]["dimUnits"][dim]

    unit = ""
    for elem in unit_arr:
        unit += elem.decode("utf-8")

    return unit


def iterate_dictionary(dic, key_string):
    """Recursively iterate in dictionary and give back its values"""
    keys = key_string.split("/", 1)
    if keys[0] not in dic and bytes(keys[0], "utf8") in dic:
        keys[0] = bytes(keys[0], "utf8")
    if keys[0] in dic:
        if len(keys) == 1:
            return dic[keys[0]]
        if not len(keys) == 1:
            return iterate_dictionary(dic[keys[0]], keys[1])
    else:
        return None


class IgorReader(MultiFormatReader):
    """Reader for FHI specific igor binarywave files"""

    supported_nxdls = ["*"]
    config_file: str | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ibw_files = []
        self.pxp_files = []
        self.eln_data = None
        self.data = {}
        self.attrs = {}
        self.entries = {}

        self.extensions = {
            ".yml": self.handle_eln_file,
            ".yaml": self.handle_eln_file,
            ".json": self.set_config_file,
            ".ibw": self.handle_ibw_file,
            ".pxp": self.handle_pxp_file,
            ".entry": self.handle_entry_files,
        }

    def handle_eln_file(self, file_path: str) -> dict[str, Any]:
        self.eln_data = parse_yml(file_path)
        return {}

    def get_eln_data(self, key: str, path: str) -> Any:
        """Returns data from the given eln path."""
        if self.eln_data is None:
            return None

        return self.eln_data.get(path)

    def set_config_file(self, file_path: str) -> dict[str, Any]:
        if self.config_file is not None:
            logger.info(f"Config file already set. Skipping the new file {file_path}.")
        self.config_file = file_path
        return {}

    def handle_objects(self, objects: tuple[Any]) -> dict[str, Any]:
        if not isinstance(objects, tuple) or not len(objects) == 1:
            raise ValueError(
                f"Expect tuple of length 1 as objects, got {type(objects)}",
            )
        if not isinstance(objects[0], dict):
            # We expect a dict of entry name dicts with data entries with wave paths as entries
            raise ValueError(f"Expected dict as first object, got {type(objects[0])}!")
        self.parse_entry_dict(objects[0])
        return {}

    def handle_entry_files(self, file_path: str) -> dict[str, Any]:
        with open(file_path, encoding="utf-8") as file:
            entry_dict = yaml.safe_load(file)
        self.parse_entry_dict(entry_dict)
        return {}

    def parse_entry_dict(self, entry_dict: dict) -> None:
        for name, entry in entry_dict.items():
            if not isinstance(entry, dict):
                raise ValueError(
                    f"Entry dict need to contain only dicts, got {type(entry)} for key {name}!",
                )
            self.entries[name] = entry

    def get_data(self, key: str, path: str) -> Any:
        return self.data.get(f"{self.callbacks.entry_name}/{path}")

    def get_attr(self, key: str, path: str) -> Any:
        return self.attrs.get(f"{self.callbacks.entry_name}/{path}")

    def get_entry_names(self) -> list[str]:
        if self.entries:
            return self.entries.keys()
        else:
            return ["entry"]

    def get_data_dims(self, key: str, path: str) -> list[str]:
        return self.data.get(f"{self.callbacks.entry_name}/dims")

    def post_process(self) -> None:
        if (
            len(self.ibw_files) > 0
            and len(self.pxp_files) > 0
            or len(self.pxp_files) > 1
        ):
            # we only support either (multiple) ibw files, or one pxp experiment
            raise ValueError(
                "This reader supports either (multiple) ibw files, or one pxp file! "
                f"Got {len(self.ibw_files)} iwb file(s), and {len(self.pxp_files)} pxp file(s).",
            )
        if len(self.ibw_files):
            # parse ibw files
            for file in self.ibw_files:
                self.process_ibw_files(file)
            return

        if len(self.pxp_files):
            # parse single pxp file
            self.process_pxp_files(self.pxp_files[0])

    def process_ibw_files(self, file: str) -> None:
        # We look for and entry with corresponding file name.
        entry = ""
        entry_dict = {}
        for en, ed in self.entries.items():
            if ed.get("data", "") == Path(file).name:
                entry = en
                entry_dict = ed
                break
        # Otherwise, we create an entry with the ibw file name as entry name
        if not entry:
            entry = Path(file).name.split(".")[0]
            self.entries[entry] = {}

        ibw = binarywave.load(file)
        # read wave notes
        for key, val in parse_note(ibw["wave"]["note"]).items():
            self.attrs[f"{entry}/note/{key}"] = val
        # axes
        dims = []
        for dim in range(ibw["wave"]["wave_header"]["nDim"].size):
            if ibw["wave"]["wave_header"]["nDim"][dim] > 0:
                # rename axis if name provided
                if f"axis{dim}_name" in entry_dict:
                    axis_name = entry_dict[f"axis{dim}_name"]
                else:
                    axis_name = f"axis{dim}"
                self.data[f"{entry}/{axis_name}.data"] = axis_from(ibw, dim)
                self.data[f"{entry}/{axis_name}.units"] = axis_units_from(ibw, dim)
                if f"axis{dim}_units" in entry_dict:
                    self.data[f"{entry}/{axis_name}.units"] = entry_dict[
                        f"axis{dim}_units"
                    ]

                self.data[f"{entry}/{axis_name}.index"] = dim
                dims.append(axis_name)

        self.data[f"{entry}/dims"] = dims
        self.data[f"{entry}/data"] = ibw["wave"]["wData"]
        if "data_units" in entry_dict:
            self.data[f"{entry}/data.units"] = entry_dict["data_units"]
        else:
            self.data[f"{entry}/data.units"] = ibw["wave"]["data_units"]

        # copy additional metadata if provided
        if "metadata" in entry_dict.keys():
            for key, val in entry_dict["metadata"].items():
                self.attrs[f"{entry}/{key}"] = val

    def process_pxp_files(self, file: str) -> None:
        _, pxp = packed.load(file)
        # read data for all defined entries
        for entry, entry_dict in self.entries.items():
            if "data" not in entry_dict.keys():
                raise ValueError(f"'data' not found for entry {entry}.")
            data_wave = iterate_dictionary(pxp, entry_dict["data"])
            if not data_wave:
                raise ValueError(
                    f"'data' wave {entry_dict['data']} not found in file {file}.",
                )
            # read wave notes
            for key, val in parse_note(data_wave.wave["wave"]["note"]).items():
                self.attrs[f"{entry}/note/{key}"] = val
            # axes
            dims = []
            for dim in range(data_wave.wave["wave"]["wave_header"]["nDim"].size):
                # only process non-empty dimensions
                if data_wave.wave["wave"]["wave_header"]["nDim"][dim] > 0:
                    # rename axis if name provided
                    if f"axis{dim}_name" in entry_dict:
                        axis_name = entry_dict[f"axis{dim}_name"]
                    else:
                        axis_name = f"axis{dim}"
                    # use axis wave if provided
                    if f"axis{dim}" in entry_dict:
                        axis_wave = iterate_dictionary(pxp, entry_dict[f"axis{dim}"])
                        if not axis_wave:
                            raise ValueError(
                                f"'axis{dim}' wave {entry_dict[f'axis{dim}']} not found in file {file}.",
                            )
                        self.data[f"{entry}/{axis_name}.data"] = axis_wave.wave["wave"][
                            "wData"
                        ]
                        self.data[f"{entry}/{axis_name}.units"] = axis_wave.wave[
                            "wave"
                        ]["data_units"]
                    else:
                        self.data[f"{entry}/{axis_name}.data"] = axis_from(
                            data_wave.wave,
                            dim,
                        )
                        self.data[f"{entry}/{axis_name}.units"] = axis_units_from(
                            data_wave.wave,
                            dim,
                        )
                    if f"axis{dim}_units" in entry_dict:
                        self.data[f"{entry}/{axis_name}.units"] = entry_dict[
                            f"axis{dim}_units"
                        ]

                    self.data[f"{entry}/{axis_name}.index"] = dim
                    dims.append(axis_name)
            # data errors
            if "data_errors" in entry_dict:
                error_wave = iterate_dictionary(pxp, entry_dict["data_errors"])
                if not error_wave:
                    raise ValueError(
                        f"'data_errors' wave {entry_dict['data_errors']} not found in file {file}.",
                    )
                self.data[f"{entry}/data.errors"] = error_wave.wave["wave"]["wData"]

            # data
            self.data[f"{entry}/dims"] = dims
            self.data[f"{entry}/data"] = data_wave.wave["wave"]["wData"]
            if "data_units" in entry_dict:
                self.data[f"{entry}/data.units"] = entry_dict["data_units"]
            else:
                self.data[f"{entry}/data.units"] = data_wave.wave["wave"]["data_units"]

            # copy additional metadata if provided
            if "metadata" in entry_dict.keys():
                for key, val in entry_dict["metadata"].items():
                    self.attrs[f"{entry}/{key}"] = val

    def handle_ibw_file(self, file_path: str) -> dict[str, Any]:
        self.ibw_files.append(file_path)
        return {}

    def handle_pxp_file(self, file_path: str) -> dict[str, Any]:
        self.pxp_files.append(file_path)
        return {}


READER = IgorReader
