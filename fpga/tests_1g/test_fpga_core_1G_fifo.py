"""
Testbench for fpga_core_1G_fifo
"""

import logging
import os

from scapy.layers.l2 import Ether, ARP
from scapy.layers.inet import IP, UDP

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from cocotbext.eth import GmiiFrame
from gmii_compat import GmiiSource, GmiiSink
from xgmii_sniffer import XgmiiSniffer


class TB:
    def __init__(self, dut):
        self.dut = dut

        # Set signals to known values BEFORE creating GMII objects
        dut.rst.setimmediatevalue(0)
        dut.gmii_a_rx_clk.setimmediatevalue(0)
        dut.gmii_b_rx_clk.setimmediatevalue(0)

        self.log = logging.getLogger("cocotb.tb")
        self.log.setLevel(logging.DEBUG)

        # 1G runs at 125 MHz (8.0 ns period)
        cocotb.start_soon(Clock(dut.clk, 8.0, units="ns").start())

        # GMII Sources: drive RX inputs (safe to create early, we control the signals)
        self.gmii_source_a = GmiiSource(dut.gmii_a_rxd, dut.gmii_a_rx_er, dut.gmii_a_rx_dv,
                                        dut.gmii_a_rx_clk)
                                        
        self.gmii_source_b = GmiiSource(dut.gmii_b_rxd, dut.gmii_b_rx_er, dut.gmii_b_rx_dv,
                                        dut.gmii_b_rx_clk)

        # GMII Sinks: created in init() after reset, to avoid Logic('Z') on TX outputs
        self.gmii_sink_a = None
        self.gmii_sink_a_pcap = None
        self.gmii_sink_b = None

        self.sniffers = {}

    def start_sniffer(self):
        self.sniffer = XgmiiSniffer('Node_A_TX', self.gmii_sink_a_pcap, self.log)
        self.sniffers = {"Node_A_TX": self.sniffer}

    def save_pcaps(self, prefix='1G_fifo'):
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

        # Wait a few clocks for RTL TX outputs to settle (no longer Z)
        for k in range(5):
            await RisingEdge(self.dut.clk)

        # Now safe to create GMII Sinks (TX outputs are driven by the MAC)
        self.gmii_sink_a = GmiiSink(self.dut.gmii_a_txd, self.dut.gmii_a_tx_er, self.dut.gmii_a_tx_en,
                                    self.dut.gmii_a_tx_clk)
        self.gmii_sink_a_pcap = GmiiSink(self.dut.gmii_a_txd, self.dut.gmii_a_tx_er, self.dut.gmii_a_tx_en,
                                    self.dut.gmii_a_tx_clk)                                    
        self.gmii_sink_b = GmiiSink(self.dut.gmii_b_txd, self.dut.gmii_b_tx_er, self.dut.gmii_b_tx_en,
                                    self.dut.gmii_b_tx_clk)

        # Drain any stale frames from async FIFOs (left over from previous tests)
        for k in range(50):
            await RisingEdge(self.dut.clk)
        
    async def drain_rx_fifos(self):
        while not self.gmii_sink_a.empty():
            self.gmii_sink_a.recv_nowait()
        while not self.gmii_sink_b.empty():
            self.gmii_sink_b.recv_nowait()

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
        
        ctrl_val = 0
        if loopback: ctrl_val |= 1
        await self.apb_write("a", 0x00, ctrl_val)
        # Configure local MAC: 02:00:00:00:00:01
        await self.apb_write("a", 0x08, 0x00000001) # SRC_MAC_L
        await self.apb_write("a", 0x0C, 0x00000200) # SRC_MAC_H
        # Configure IPs: 192.168.1.1
        await self.apb_write("a", 0x18, 0xC0A80101) # SRC_IP
        await self.apb_write("a", 0x28, 0xC0A80102) # GATEWAY_IP
        await self.apb_write("a", 0x2C, 0xFFFFFF00) # SUBNET_MASK
        # Configure UDP ports
        await self.apb_write("a", 0x24, 1234)       # DST_PORT
        await self.apb_write("a", 0x20, 1234)       # SRC_PORT

        # Basic readback verification
        readback_ip = await self.apb_read("a", 0x18)
        assert readback_ip == 0xC0A80101, f"APB Readback error: expected 0xC0A80101, got {hex(readback_ip)}"

    async def setup_mac_b(self, loopback=False):
        """Configure Node B via APB."""
        self.log.info(f"Configure APB for Node B (loopback={loopback})")

        ctrl_val = 0
        if loopback: ctrl_val |= 1
        await self.apb_write("b", 0x00, ctrl_val)
        # Configure local MAC: 02:00:00:00:00:02
        await self.apb_write("b", 0x08, 0x00000002)  # SRC_MAC_L
        await self.apb_write("b", 0x0C, 0x00000200)  # SRC_MAC_H
        # Configure IPs: 192.168.1.2
        await self.apb_write("b", 0x18, 0xC0A80102)  # SRC_IP
        await self.apb_write("b", 0x1C, 0xC0A80101)  # DST_IP
        await self.apb_write("b", 0x28, 0xC0A80101)  # GATEWAY_IP
        await self.apb_write("b", 0x2C, 0xFFFFFF00)  # SUBNET_MASK
        # Configure UDP ports
        await self.apb_write("b", 0x24, 1234)         # DST_PORT
        await self.apb_write("b", 0x20, 1234)         # SRC_PORT

    async def setup_fir_a(self, coeffs):
        self.log.info("Configure FIR for Node A")
        for i, c in enumerate(coeffs):
            await self.apb_write("fir_a", 1 * 4, i)  # COEFF_ADDR
            await self.apb_write("fir_a", 2 * 4, c)  # COEFF_DATA

    async def setup_fir_bypass(self, bypass=True):
        self.log.info(f"Configure FIR Bypass={bypass}")
        await self.apb_write("fir_a", 0 * 4, 1 if bypass else 0)


@cocotb.test()
async def test_mac_loopback(dut):
    """Test standard UDP MAC loopback on Node A."""
    tb = TB(dut)
    await tb.init()

    # 125 MHz clocks
    cocotb.start_soon(Clock(dut.gmii_a_rx_clk, 8.0, units="ns").start())
    cocotb.start_soon(Clock(dut.gmii_b_rx_clk, 8.0, units="ns").start())

    await tb.setup_mac_a(loopback=False)
    tb.log.info("Test UDP RX packet MAC loopback on Node A")

    payload = bytes([x % 256 for x in range(64)])
    eth = Ether(src='5a:51:52:53:54:55', dst='02:00:00:00:00:00')
    ip = IP(src='192.168.1.100', dst='192.168.1.1')
    udp = UDP(sport=1234, dport=1234)
    test_pkt = eth / ip / udp / payload
    test_frame = GmiiFrame.from_payload(test_pkt.build())

    await tb.gmii_source_a.send(test_frame)

    # 1. ARP Response
    rx_frame = await tb.gmii_sink_a.recv()
    rx_pkt = Ether(bytes(rx_frame.get_payload()))
    tb.log.info("RX ARP packet: %s", repr(rx_pkt))

    assert ARP in rx_pkt
    
    eth_arp = Ether(src='5a:51:52:53:54:55', dst='02:00:00:00:00:01')
    arp = ARP(hwtype=1, ptype=0x0800, hwlen=6, plen=4, op=2,
        hwsrc='5a:51:52:53:54:55', psrc='192.168.1.100',
        hwdst='02:00:00:00:00:01', pdst='192.168.1.1')
    await tb.gmii_source_a.send(GmiiFrame.from_payload((eth_arp / arp).build()))

    # 2. UDP Payload Response
    rx_frame = await tb.gmii_sink_a.recv()
    rx_pkt = Ether(bytes(rx_frame.get_payload()))
    tb.log.info("RX UDP packet: %s", repr(rx_pkt))

    assert UDP in rx_pkt
    assert rx_pkt.dst == '5a:51:52:53:54:55'
    assert rx_pkt[UDP].payload == test_pkt[UDP].payload

    for _ in range(100):
        await RisingEdge(dut.clk)


@cocotb.test()
async def test_fir_loopback(dut):
    """Test UDP loopback via FIR Bypass on Node A."""
    tb = TB(dut)
    await tb.init()

    # 125 MHz clocks
    cocotb.start_soon(Clock(dut.gmii_a_rx_clk, 8.0, units="ns").start())
    cocotb.start_soon(Clock(dut.gmii_b_rx_clk, 8.0, units="ns").start())

    # MAC loopback must be DISABLED so it forwards to FIR
    await tb.setup_mac_a(loopback=False)
    # FIR is configured to BYPASS (which acts as a loopback)
    tb.log.info("Test UDP RX packet loopback via FIR Bypass on Node A")
    await tb.setup_fir_bypass(bypass=True)

    payload = bytes([x % 256 for x in range(64)])
    eth = Ether(src='5a:51:52:53:54:55', dst='02:00:00:00:00:00')
    ip = IP(src='192.168.1.100', dst='192.168.1.1')
    udp = UDP(sport=5678, dport=1234)
    test_pkt = eth / ip / udp / payload
    test_frame = GmiiFrame.from_payload(test_pkt.build())

    await tb.gmii_source_a.send(test_frame)

    # 1. ARP Response
    rx_frame = await tb.gmii_sink_a.recv()
    rx_pkt = Ether(bytes(rx_frame.get_payload()))
    tb.log.info("RX ARP packet: %s", repr(rx_pkt))

    assert ARP in rx_pkt
    
    eth_arp = Ether(src='5a:51:52:53:54:55', dst='02:00:00:00:00:01')
    arp = ARP(hwtype=1, ptype=0x0800, hwlen=6, plen=4, op=2,
        hwsrc='5a:51:52:53:54:55', psrc='192.168.1.100',
        hwdst='02:00:00:00:00:01', pdst='192.168.1.1')
    await tb.gmii_source_a.send(GmiiFrame.from_payload((eth_arp / arp).build()))

    # 2. UDP Payload Response
    rx_frame = await tb.gmii_sink_a.recv()
    rx_pkt = Ether(bytes(rx_frame.get_payload()))
    tb.log.info("RX UDP packet: %s", repr(rx_pkt))

    assert UDP in rx_pkt
    assert rx_pkt.dst == '5a:51:52:53:54:55'
    assert rx_pkt[UDP].payload == test_pkt[UDP].payload

    for _ in range(100):
        await RisingEdge(dut.clk)

@cocotb.test()
async def test_fir_processing(dut):
    """Test forwarding UDP packets through the FIR filter (Processing Mode)."""
    tb = TB(dut)
    await tb.init()

    cocotb.start_soon(Clock(dut.gmii_a_rx_clk, 8.0, units="ns").start())
    cocotb.start_soon(Clock(dut.gmii_b_rx_clk, 8.0, units="ns").start())

    # Configure Node A to NOT loopback
    await tb.setup_mac_a(loopback=False)
    await tb.drain_rx_fifos()
    
    # Configure FIR to multiply by 2 and disable bypass
    await tb.setup_fir_a([2, 0, 0, 0])
    await tb.setup_fir_bypass(bypass=False)
    tb.start_sniffer()

    tb.log.info("Test UDP RX packet forwarding via FIR on Node A")

    # Limit payload to 0-120 to avoid unsigned byte overflow after multiplying by 2
    payload_bytes = [x for x in range(32)]
    payload = bytes(payload_bytes)
    eth = Ether(src='5a:51:52:53:54:55', dst='02:00:00:00:00:00')
    ip = IP(src='192.168.1.100', dst='192.168.1.1')
    udp = UDP(sport=5678, dport=1234)
    test_pkt = eth / ip / udp / payload
    
    # We must respond to ARP first
    await tb.gmii_source_a.send(GmiiFrame.from_payload(test_pkt.build()))

    rx_frame = await tb.gmii_sink_a.recv()
    rx_pkt = Ether(bytes(rx_frame.get_payload()))
    if ARP in rx_pkt:
        eth_arp = Ether(src='5a:51:52:53:54:55', dst='02:00:00:00:00:01')
        arp = ARP(hwtype=1, ptype=0x0800, hwlen=6, plen=4, op=2,
            hwsrc='5a:51:52:53:54:55', psrc='192.168.1.100',
            hwdst='02:00:00:00:00:01', pdst='192.168.1.1')
        await tb.gmii_source_a.send(GmiiFrame.from_payload((eth_arp / arp).build()))

        rx_frame = await tb.gmii_sink_a.recv()
        rx_pkt = Ether(bytes(rx_frame.get_payload()))

    assert UDP in rx_pkt
    
    # The returned payload should be exactly the source multiplied by 2!
    expected_payload_bytes = bytes([x * 2 for x in payload_bytes])
    
    tb.save_pcaps(prefix='1G_fifo')


    assert rx_pkt.dst == '5a:51:52:53:54:55'
    assert rx_pkt[UDP].payload.load[:32] == expected_payload_bytes[:32], f"FIR failed to multiply! Expected {expected_payload_bytes[:32].hex()}, got {rx_pkt[UDP].payload.load[:32].hex()}"
    
    tb.log.info("Successfully validated FIR multiplier forward mode on Node A")
    for _ in range(100):
        await RisingEdge(dut.clk)


