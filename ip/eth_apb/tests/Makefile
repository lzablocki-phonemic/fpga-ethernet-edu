# Makefile for fpga_core cocotb testbench
# Two b2b UDP 1G nodes with APB configuration

TOPLEVEL_LANG = verilog

SIM ?= icarus
WAVES ?= 0

COCOTB_HDL_TIMEUNIT = 1ns
COCOTB_HDL_TIMEPRECISION = 1ps

DUT      = fpga_core
TOPLEVEL = $(DUT)
MODULE   = test_$(DUT)

# Project root (relative to this Makefile location: ip/eth_apb/tests/)
PROJ_ROOT = ../../..

# RTL source directories
IP_APB_DIR  = $(PROJ_ROOT)/ip/eth_apb/hdl
IP_CFG_DIR  = $(PROJ_ROOT)/ip/apb_configurator/hdl
ETH_RTL_DIR = $(PROJ_ROOT)/external/verilog-ethernet/rtl
AXIS_RTL_DIR = $(PROJ_ROOT)/external/verilog-ethernet/lib/axis/rtl

# Top-level
VERILOG_SOURCES += $(IP_APB_DIR)/fpga_core.v

# Custom IP
VERILOG_SOURCES += $(IP_APB_DIR)/mac_udp_1G_apbConfig.v
VERILOG_SOURCES += $(IP_CFG_DIR)/apb_configurator.v

# Ethernet MAC (GMII FIFO)
VERILOG_SOURCES += $(ETH_RTL_DIR)/eth_mac_1g_fifo.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/eth_mac_1g.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/axis_gmii_rx.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/axis_gmii_tx.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/lfsr.v

# Ethernet frame
VERILOG_SOURCES += $(ETH_RTL_DIR)/eth_axis_rx.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/eth_axis_tx.v

# UDP/IP stack
VERILOG_SOURCES += $(ETH_RTL_DIR)/udp_complete.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/udp_checksum_gen.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/udp.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/udp_ip_rx.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/udp_ip_tx.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/ip_complete.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/ip.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/ip_eth_rx.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/ip_eth_tx.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/ip_arb_mux.v

# ARP
VERILOG_SOURCES += $(ETH_RTL_DIR)/arp.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/arp_cache.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/arp_eth_rx.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/arp_eth_tx.v
VERILOG_SOURCES += $(ETH_RTL_DIR)/eth_arb_mux.v

# AXI-Stream infrastructure
VERILOG_SOURCES += $(AXIS_RTL_DIR)/arbiter.v
VERILOG_SOURCES += $(AXIS_RTL_DIR)/priority_encoder.v
VERILOG_SOURCES += $(AXIS_RTL_DIR)/axis_fifo.v
VERILOG_SOURCES += $(AXIS_RTL_DIR)/axis_async_fifo.v
VERILOG_SOURCES += $(AXIS_RTL_DIR)/axis_async_fifo_adapter.v

# Simulation build output goes to ../sim
SIM_BUILD ?= $(PWD)/../sim

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
