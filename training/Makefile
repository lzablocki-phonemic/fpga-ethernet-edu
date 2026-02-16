TOPLEVEL_LANG = verilog
SIM ?= icarus

# TRICK: Force WAVES=0 so Cocotb does NOT add the '-fst' flag
WAVES = 1

# Project Defaults
DUT      = my_design
TOPLEVEL = $(DUT)
COCOTB_TEST_MODULES = test_$(DUT)

# Source Files
VERILOG_SOURCES += $(PWD)/$(DUT).v

# ALWAYS compile the dumper (removed the ifeq check)
VERILOG_SOURCES += iverilog_dump.v
COMPILE_ARGS += -s iverilog_dump

# Explicitly add current directory to PYTHONPATH
export PYTHONPATH := $(PWD):$(PYTHONPATH)

ifeq ($(SIM), icarus)
    COMPILE_ARGS += -I $(PWD)
    COMPILE_ARGS += $(foreach v,$(filter PARAM_%,$(.VARIABLES)),-P $(TOPLEVEL).$(subst PARAM_,,$(v))=$($(v)))
endif

include $(shell cocotb-config --makefiles)/Makefile.sim

# Dynamic Waveform Dumper (Standard VCD)
iverilog_dump.v:
	echo 'module iverilog_dump();' > $@
	echo 'initial begin' >> $@
	echo '    $$dumpfile("my_design_make.vcd");' >> $@
	echo '    $$dumpvars(0, my_design);' >> $@
	echo 'end' >> $@
	echo 'endmodule' >> $@

clean::
	@rm -rf iverilog_dump.v
	@rm -rf my_design.vcd
	@rm -rf sim_build
	@rm -rf __pycache__
	@rm -rf results.xml