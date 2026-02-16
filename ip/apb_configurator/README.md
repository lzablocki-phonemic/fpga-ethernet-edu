# fpga-ethernet-edu: APB_configurator IP

This is the propsal of universal APB facade component used for the parametrization read/write using APB, and allows CDC.

What works:
1. read/write for single burst write 
2. tests :
* pytest generation of the test
* Makefile simple tests from APBside, and CDC for internal connection

Tests can be executed
    make cleanall; make TEST_MODE=simple
    make cleanall; make TEST_MODE=cdc

    pytest test_runner_pytest.py