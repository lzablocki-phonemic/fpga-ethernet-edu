# Makefile for APB Configurator Tests
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

# ------------------------------------------------------------------------------
# Cocotb Configuration
# ------------------------------------------------------------------------------
# Tell Cocotb to write the XML results file into the build directory
export COCOTB_RESULTS_FILE = $(SIM_BUILD)/results.xml

# ------------------------------------------------------------------------------
# Build Directory Configuration
# ------------------------------------------------------------------------------
# This places all compilation files (vvp, log, etc.) in the 'sim' folder
# distinct from the 'tests' folder.
# $(PWD) is the directory where you run 'make' (tests/)
SIM_BUILD ?= $(PWD)/../sim

# ------------------------------------------------------------------------------
# Waveform Configuration
# ------------------------------------------------------------------------------
# Set WAVES=1 to enable waveform dumping (e.g., make WAVES=1 TEST_MODE=cdc)
# VCD files will be saved to $(SIM_BUILD)/waveform.vcd
WAVES ?= 0
ifneq ($(WAVES),0)
    # Enable VCD waveform dumping for Icarus Verilog
    COMPILE_ARGS += -DVCD_ENABLE
    PLUSARGS += +vcd_file=$(SIM_BUILD)/waveform.vcd
endif

# ------------------------------------------------------------------------------
# Test Mode Configuration
# ------------------------------------------------------------------------------
# Options: simple (default), cdc
TEST_MODE ?= simple

# Hardware Parameters
WIDTH ?= 32
REGS  ?= 16

# ------------------------------------------------------------------------------
# Sources & Logic
# ------------------------------------------------------------------------------
# 1. Base Source
VERILOG_SOURCES += $(PWD)/../hdl/apb_configurator.v
VERILOG_SOURCES += $(PWD)/../tb/dump_vcd.v

# 2. Select Top Level based on Mode
ifeq ($(TEST_MODE),cdc)
    # CDC Mode: Uses Wrapper
    VERILOG_SOURCES += $(PWD)/../hdl/apb_cdc_wrapper.v
    TOPLEVEL = apb_cdc_wrapper
    MODULE   = test_cdc_cocotb
    
    # Pass params to wrapper
    COMPILE_ARGS += -Papb_cdc_wrapper.APB_DATA_WIDTH=$(WIDTH)
    COMPILE_ARGS += -Papb_cdc_wrapper.NUM_REGS=$(REGS)
else
    # Simple Mode: Direct IP
    TOPLEVEL = apb_configurator
    MODULE   = test_apb_configurator_cocotb
    
    # Pass params to IP
    COMPILE_ARGS += -Papb_configurator.APB_DATA_WIDTH=$(WIDTH)
    COMPILE_ARGS += -Papb_configurator.NUM_REGS=$(REGS)
endif

# ------------------------------------------------------------------------------
# Cocotb Include
# ------------------------------------------------------------------------------
include $(shell cocotb-config --makefiles)/Makefile.sim


# Add this to the bottom of your Makefile
cleanall: clean
	rm -rf ../sim/*.vvp ../sim/*.xml ../sim/build_*