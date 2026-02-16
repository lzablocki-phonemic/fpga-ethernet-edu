#!/bin/bash
export REMOTE_DEBUG=1
export PATH=/home/piotr/workspace/Soc_ethernet/fpga-ethernet-edu/.venv/bin:$PATH
make SIM=icarus COCOTB_TEST_MODULES=test_fpga_core
