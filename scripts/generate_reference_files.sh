#!/bin/bash
READER=igor
NXDL=NXroot

function update_igor_ibw_example {
  echo "Update igor ibw example"
  pynx convert config_file.json Norm_0057.ibw Norm_0059.ibw --reader $READER --nxdl $NXDL --ignore-undocumented --output example_ibw.nxs &> ibw_ref_output.txt
}

function update_igor_ibw_entry_example {
  echo "Update igor ibw example with entry file"
  pynx convert config_file.json Norm_0057.ibw Norm_0059.ibw Norm57.yaml.entry --reader $READER --nxdl $NXDL --ignore-undocumented --output example_ibw_entry.nxs &> ibw_entry_ref_output.txt
}

function update_igor_pxp_example {
  echo "Update igor pxp example"
  pynx convert config_file.json Fig2a.pxp Scan57_59.yaml.entry --reader $READER --nxdl $NXDL --ignore-undocumented --output example_pxp.nxs &> pxp_ref_output.txt
}

project_dir=$(dirname $(dirname $(realpath $0)))
cd $project_dir/tests/data

update_igor_ibw_example
update_igor_ibw_entry_example
update_igor_pxp_example