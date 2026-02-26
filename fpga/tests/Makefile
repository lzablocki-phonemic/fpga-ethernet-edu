# Makefile for fpga_core_10g cocotb testbench

TOPLEVEL_LANG = verilog

SIM ?= icarus
WAVES ?= 0

COCOTB_HDL_TIMEUNIT = 1ns
COCOTB_HDL_TIMEPRECISION = 1ps

DUT      = fpga_core_10g
TOPLEVEL = $(DUT)
MODULE   ?= test_$(DUT)

# Project root (relative to fpga/tests/)
PROJ_ROOT = ../..

# Python module path (for xgmii_sniffer etc.)
export PYTHONPATH := $(PWD)/../python:$(PYTHONPATH)

# Source directories
TB_DIR     = $(PROJ_ROOT)/fpga/tb
HDL_DIR     = $(PROJ_ROOT)/fpga/hdl
APB_CFG_DIR = $(PROJ_ROOT)/ip/eth_apb/hdl
APB_CFG_BASE_DIR = $(PROJ_ROOT)/ip/apb_configurator/hdl
FIR_DIR     = $(PROJ_ROOT)/ip/fir/hdl
ETH_LIB_DIR = $(PROJ_ROOT)/external/verilog-ethernet

# Verilog sources
VERILOG_SOURCES += $(TB_DIR)/udp_axi_data_gen.v
VERILOG_SOURCES += $(HDL_DIR)/fpga_core_10g.v
VERILOG_SOURCES += $(APB_CFG_DIR)/mac_udp_10G_apbConfig.v
VERILOG_SOURCES += $(APB_CFG_BASE_DIR)/apb_configurator.v
VERILOG_SOURCES += $(FIR_DIR)/fir_filter.v
VERILOG_SOURCES += $(FIR_DIR)/fir_filter_apbConfig.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/eth_mac_10g_fifo.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/eth_mac_10g.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/axis_xgmii_rx_64.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/axis_xgmii_tx_64.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/lfsr.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/eth_axis_rx.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/eth_axis_tx.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/udp_complete_64.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/udp_checksum_gen_64.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/udp_64.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/udp_ip_rx_64.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/udp_ip_tx_64.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/ip_complete_64.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/ip_64.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/ip_eth_rx_64.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/ip_eth_tx_64.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/ip_arb_mux.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/arp.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/arp_cache.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/arp_eth_rx.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/arp_eth_tx.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/rtl/eth_arb_mux.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/lib/axis/rtl/arbiter.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/lib/axis/rtl/priority_encoder.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/lib/axis/rtl/axis_fifo.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/lib/axis/rtl/axis_async_fifo.v
VERILOG_SOURCES += $(ETH_LIB_DIR)/lib/axis/rtl/axis_async_fifo_adapter.v

# Simulation build output goes to ../sim
SIM_BUILD ?= $(PWD)/../sim

export COCOTB_RESULTS_FILE = $(SIM_BUILD)/results.xml
# B2B mode: 0=external XGMII (default), 1=internal cross-connect
B2B_EN ?= 0

ifeq ($(SIM), icarus)
	PLUSARGS += -fst
	COMPILE_ARGS += -Pfpga_core_10g.B2B_EN=$(B2B_EN)

	ifeq ($(WAVES), 1)
		VERILOG_SOURCES += iverilog_dump.v
		COMPILE_ARGS += -s iverilog_dump
	endif
else ifeq ($(SIM), verilator)
	COMPILE_ARGS += -Wno-SELRANGE -Wno-WIDTH

	ifeq ($(WAVES), 1)
		COMPILE_ARGS += --trace-fst
	endif
endif

include $(shell cocotb-config --makefiles)/Makefile.sim

iverilog_dump.v:
	echo 'module iverilog_dump();' > $@
	echo 'initial begin' >> $@
	echo '    $$dumpfile("$(SIM_BUILD)/$(TOPLEVEL).fst");' >> $@
	echo '    $$dumpvars(0, $(TOPLEVEL));' >> $@
	echo 'end' >> $@
	echo 'endmodule' >> $@

clean::
	@rm -rf iverilog_dump.v
	@rm -rf dump.fst $(SIM_BUILD)/$(TOPLEVEL).fst $(TOPLEVEL).fst
	@rm -rf sim_build $(SIM_BUILD)/results.xml
