#!/bin/bash
READER=igor
NXDL=NXroot

function update_igor_ibw_example {
  echo "Update igor ibw example"
  dataconverter config_file.json Norm_0057.ibw Norm_0059.ibw --reader $READER --nxdl $NXDL --output example_ibw.nxs 
}

function update_igor_ibw_entry_example {
  echo "Update igor ibw example with entry file"
  dataconverter config_file.json Norm_0057.ibw Norm_0059.ibw Norm57.yaml.entry --reader $READER --nxdl $NXDL --output example_ibw_entry.nxs
}

function update_igor_pxp_example {
  echo "Update igor pxp example"
  dataconverter config_file.json Fig2a.pxp Scan57_59.yaml.entry --reader $READER --nxdl $NXDL --output example_pxp.nxs 
}

project_dir=$(dirname $(dirname $(realpath $0)))
cd $project_dir/tests/data

update_igor_ibw_example
update_igor_ibw_entry_example
update_igor_pxp_example