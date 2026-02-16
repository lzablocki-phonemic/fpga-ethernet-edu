# Makefile for fir_filter_apbConfig cocotb testbench

TOPLEVEL_LANG = verilog

SIM ?= icarus
WAVES ?= 0

COCOTB_HDL_TIMEUNIT = 1ns
COCOTB_HDL_TIMEPRECISION = 1ps

DUT      = fir_filter_apbConfig
TOPLEVEL = $(DUT)
MODULE   = test_$(DUT)

# Project root (relative to ip/fir/tests/)
PROJ_ROOT = ../../..

# Source directories
HDL_DIR     = $(PROJ_ROOT)/ip/fir/hdl
APB_CFG_DIR = $(PROJ_ROOT)/ip/apb_configurator/hdl

# Verilog sources: APB wrapper + FIR core + apb_configurator
VERILOG_SOURCES += $(HDL_DIR)/fir_filter_apbConfig.v
VERILOG_SOURCES += $(HDL_DIR)/fir_filter.v
VERILOG_SOURCES += $(APB_CFG_DIR)/apb_configurator.v

# Simulation build output goes to ../sim
SIM_BUILD ?= $(PWD)/../sim

export COCOTB_RESULTS_FILE = $(SIM_BUILD)/results.xml

# Icarus Verilog options
COMPILE_ARGS += -g2012
PLUSARGS += -fst

ifeq ($(WAVES), 1)
	VERILOG_SOURCES += iverilog_dump.v
	COMPILE_ARGS += -s iverilog_dump
endif

include $(shell cocotb-config --makefiles)/Makefile.sim

iverilog_dump.v:
	echo 'module iverilog_dump();' > $@
	echo 'initial begin' >> $@
	echo '    $$dumpfile("$(TOPLEVEL).fst");' >> $@
	echo '    $$dumpvars(0, $(TOPLEVEL));' >> $@
	echo 'end' >> $@
	echo 'endmodule' >> $@

clean::
	@rm -rf iverilog_dump.v
	@rm -rf dump.fst $(TOPLEVEL).fst
	@rm -rf sim_build results.xml
