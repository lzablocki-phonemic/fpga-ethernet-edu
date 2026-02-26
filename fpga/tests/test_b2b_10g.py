"""
B2B (back-to-back) integration test for fpga_core_10g.

Requires: make MODULE=test_b2b_10g B2B_EN=1

Node B originates a UDP packet via udp_axi_data_gen trigger.
Node B resolves Node A's MAC via ARP (internal b2b path).
Node A (loopback=True) echoes the payload back.
All XGMII traffic is captured to .pcap files for Wireshark.
"""

import logging
import os

from scapy.layers.l2 import Ether, ARP
from scapy.layers.inet import IP, UDP

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from cocotbext.eth import XgmiiFrame, XgmiiSource, XgmiiSink

from xgmii_sniffer import XgmiiSniffer


class TB:
    def __init__(self, dut):
        self.dut = dut

        dut.rst.setimmediatevalue(0)
        dut.xgmii_a_rx_clk.setimmediatevalue(0)
        dut.xgmii_b_rx_clk.setimmediatevalue(0)
        dut.trigger_b.setimmediatevalue(0)

        self.log = logging.getLogger("cocotb.tb")
        self.log.setLevel(logging.DEBUG)

        cocotb.start_soon(Clock(dut.clk, 6.4, units="ns").start())

        self.xgmii_source_a = XgmiiSource(dut.xgmii_a_rxd, dut.xgmii_a_rxc, dut.clk)
        self.xgmii_sink_a = XgmiiSink(dut.xgmii_a_txd, dut.xgmii_a_txc, dut.clk)
        self.xgmii_source_b = XgmiiSource(dut.xgmii_b_rxd, dut.xgmii_b_rxc, dut.clk)
        self.xgmii_sink_b = XgmiiSink(dut.xgmii_b_txd, dut.xgmii_b_txc, dut.clk)

        self.sniffers = {}

    def start_sniffers(self):
        self.sniffers['node_a_tx'] = XgmiiSniffer('Node_A_TX', self.xgmii_sink_a, self.log)
        self.sniffers['node_b_tx'] = XgmiiSniffer('Node_B_TX', self.xgmii_sink_b, self.log)

    def save_pcaps(self, prefix='b2b'):
        pcap_dir = os.path.join(os.path.dirname(__file__), '..', 'sim')
        os.makedirs(pcap_dir, exist_ok=True)
        for name, sniffer in self.sniffers.items():
            sniffer.stop()
            path = os.path.join(pcap_dir, f'{prefix}_{name}.pcap')
            sniffer.write_pcap(path)

    async def init(self):
        for k in range(10):
            await RisingEdge(self.dut.clk)
        self.dut.rst.value = 1
        for k in range(10):
            await RisingEdge(self.dut.clk)
        self.dut.rst.value = 0

    async def apb_write(self, sel, addr, data):
        psel = getattr(self.dut, f"psel_{sel}")
        penable = getattr(self.dut, f"penable_{sel}")
        paddr = getattr(self.dut, f"paddr_{sel}")
        pwrite = getattr(self.dut, f"pwrite_{sel}")
        pwdata = getattr(self.dut, f"pwdata_{sel}")
        pready = getattr(self.dut, f"pready_{sel}")

        psel.value = 1
        penable.value = 0
        paddr.value = addr
        pwrite.value = 1
        pwdata.value = data
        await RisingEdge(self.dut.clk)
        penable.value = 1
        while True:
            await RisingEdge(self.dut.clk)
            if pready.value:
                break
        psel.value = 0
        penable.value = 0
        pwrite.value = 0
        pwdata.value = 0

    async def apb_read(self, sel, addr):
        psel = getattr(self.dut, f"psel_{sel}")
        penable = getattr(self.dut, f"penable_{sel}")
        paddr = getattr(self.dut, f"paddr_{sel}")
        pwrite = getattr(self.dut, f"pwrite_{sel}")
        prdata = getattr(self.dut, f"prdata_{sel}")
        pready = getattr(self.dut, f"pready_{sel}")

        psel.value = 1
        penable.value = 0
        paddr.value = addr
        pwrite.value = 0
        await RisingEdge(self.dut.clk)
        penable.value = 1
        while True:
            await RisingEdge(self.dut.clk)
            if pready.value:
                break
        data = prdata.value.integer
        psel.value = 0
        penable.value = 0
        return data

    async def trigger_udp_b(self):
        self.log.info("Trigger UDP for Node B")
        trigger_udp = getattr(self.dut, "trigger_b")
        await RisingEdge(self.dut.clk)
        trigger_udp.value = 1
        await RisingEdge(self.dut.clk)
        trigger_udp.value = 0
        await RisingEdge(self.dut.clk)

    async def setup_mac_a(self, loopback=True):
        self.log.info(f"Configure APB for Node A (loopback={loopback})")
        self.dut.psel_a.value = 0
        self.dut.penable_a.value = 0
        self.dut.pwrite_a.value = 0
        self.dut.paddr_a.value = 0
        self.dut.pwdata_a.value = 0
        self.dut.psel_b.value = 0
        self.dut.penable_b.value = 0
        self.dut.pwrite_b.value = 0
        self.dut.paddr_b.value = 0
        self.dut.pwdata_b.value = 0
        self.dut.psel_fir_a.value = 0
        self.dut.penable_fir_a.value = 0
        self.dut.pwrite_fir_a.value = 0
        self.dut.paddr_fir_a.value = 0
        self.dut.pwdata_fir_a.value = 0
        await RisingEdge(self.dut.clk)
        ctrl_val = 1 if loopback else 0
        await self.apb_write("a", 0x00, ctrl_val)
        await self.apb_write("a", 0x08, 0x00000001)
        await self.apb_write("a", 0x0C, 0x00000200)
        await self.apb_write("a", 0x18, 0xC0A80101)
        await self.apb_write("a", 0x1c, 0xC0A80102)
        await self.apb_write("a", 0x28, 0xC0A80102)
        await self.apb_write("a", 0x2C, 0xFFFFFF00)
        await self.apb_write("a", 0x24, 1234)
        await self.apb_write("a", 0x20, 1234)

    async def setup_mac_b(self, loopback=False):
        self.log.info(f"Configure APB for Node B (loopback={loopback})")
        await RisingEdge(self.dut.clk)
        ctrl_val = 1 if loopback else 0
        await self.apb_write("b", 0x00, ctrl_val)
        await self.apb_write("b", 0x08, 0x00000002)
        await self.apb_write("b", 0x0C, 0x00000200)
        await self.apb_write("b", 0x18, 0xC0A80102)
        await self.apb_write("b", 0x1c, 0xC0A80101)
        await self.apb_write("b", 0x28, 0xC0A80102)
        await self.apb_write("b", 0x2C, 0xFFFFFF00)
        await self.apb_write("b", 0x24, 1234)
        await self.apb_write("b", 0x20, 1234)


@cocotb.test()
async def test_mac_b2b(dut):
    """Test standard UDP MAC b2b on Node A and B (10G).

    Node B originates a UDP packet (via udp_axi_data_gen trigger).
    Node B's udp_complete resolves Node A's MAC via ARP (internal b2b path).
    The UDP packet flows: Node B TX → Node A RX (internal b2b).
    Node A (loopback=True) echoes the payload back.
    Node A TX → Node B RX (internal b2b) AND external sink (xgmii_a).

    All XGMII traffic is captured and saved to .pcap files for Wireshark.
    """
    tb = TB(dut)
    await tb.init()

    cocotb.start_soon(Clock(dut.xgmii_a_rx_clk, 6.4, units="ns").start())
    cocotb.start_soon(Clock(dut.xgmii_b_rx_clk, 6.4, units="ns").start())

    # Start packet sniffers BEFORE any traffic
    tb.start_sniffers()

    await tb.setup_mac_a(loopback=False)
    await tb.setup_mac_b(loopback=False)

    # Allow configuration to settle
    await Timer(1, units="us")

    tb.log.info("Triggering UDP data generation on Node B")
    await tb.trigger_udp_b()

    # Wait for ARP resolution + UDP packet transit
    await Timer(10, units="us")

    # Check sniffers captured a UDP packet on Node A's TX
    found_udp = any(UDP in pkt for pkt in tb.sniffers['node_a_tx'].packets)

    tb.log.info("=== Capture Summary ===")
    tb.log.info("Node A TX: %d packets captured", tb.sniffers['node_a_tx'].frame_count)
    tb.log.info("Node B TX: %d packets captured", tb.sniffers['node_b_tx'].frame_count)
    tb.log.info("UDP found on Node A TX: %s", found_udp)

    # Save pcap files for Wireshark analysis
    tb.save_pcaps(prefix='b2b')

    assert found_udp, "No UDP packet received on Node A's external XGMII sink"

    for _ in range(100):
        await RisingEdge(dut.clk)
