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
"""Entry points for igor examples."""

try:
    from nomad.config.models.plugins import ExampleUploadEntryPoint
except ImportError as exc:
    raise ImportError(
        "Could not import nomad package. Please install the package 'nomad-lab'.",
    ) from exc

igor_example = ExampleUploadEntryPoint(
    title="Igor Reader",
    category="FAIRmat examples",
    description="""
        This example presents the capabilities of NOMAD platform to convert and
        and standardize data stored with Wavemetrics [Igor Pro](https://www.wavemetrics.com/) into the
        [NeXus](https://www.nexusformat.org/) format.

        It contains two examples:
        - Converting Igor Binary Wave (.ibw) and packed experiment  (.pxp) into NeXus files.
        - An example conversion of time-resolved resonant diffraction data into the standardized
          NeXus format for X-ray diffraction, [NXxrd](https://fairmat-nfdi.github.io/nexus_definitions/classes/contributed_definitions/NXxrd.html).
    """,
    plugin_package="pynxtools_igor",
    resources=["nomad/examples/*"],
)
