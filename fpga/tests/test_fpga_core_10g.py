"""
Testbench for fpga_core_10g
"""

import logging
import math
import os
import struct

import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for CI
import matplotlib.pyplot as plt
from scipy.signal import firwin

from scapy.layers.l2 import Ether, ARP
from scapy.layers.inet import IP, UDP

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from cocotbext.eth import XgmiiFrame, XgmiiSource, XgmiiSink


class TB:
    def __init__(self, dut):
        self.dut = dut

        # Set signals to known values before creating XGMII objects
        dut.rst.setimmediatevalue(0)
        dut.xgmii_a_rx_clk.setimmediatevalue(0)
        dut.xgmii_b_rx_clk.setimmediatevalue(0)
        dut.trigger_b.setimmediatevalue(0)

        self.log = logging.getLogger("cocotb.tb")
        self.log.setLevel(logging.DEBUG)

        cocotb.start_soon(Clock(dut.clk, 6.4, units="ns").start())

        # Ethernet (pass reset=None to avoid cocotbext-eth Logic('Z') crash)
        self.xgmii_source_a = XgmiiSource(dut.xgmii_a_rxd, dut.xgmii_a_rxc, dut.clk)
        self.xgmii_sink_a = XgmiiSink(dut.xgmii_a_txd, dut.xgmii_a_txc, dut.clk)
        self.xgmii_source_b = XgmiiSource(dut.xgmii_b_rxd, dut.xgmii_b_rxc, dut.clk)
        self.xgmii_sink_b = XgmiiSink(dut.xgmii_b_txd, dut.xgmii_b_txc, dut.clk)


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
        self.log.info(f"Trigger UDP for Node B (loopback)")
        trigger_udp = getattr(self.dut, "trigger_b")
       
        await RisingEdge(self.dut.clk)
        trigger_udp.value = 1 
        await RisingEdge(self.dut.clk)
        trigger_udp.value = 0
        await RisingEdge(self.dut.clk)


    async def setup_mac_b(self, loopback=True):
        self.log.info(f"Configure APB for Node B (loopback={loopback})")
        
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
        await self.apb_write("b", 0x00, ctrl_val)
        # Configure local MAC: 02:00:00:00:00:02
        await self.apb_write("b", 0x08, 0x00000002) # SRC_MAC_L
        await self.apb_write("b", 0x0C, 0x00000200) # SRC_MAC_H
        # Configure IPs: 192.168.1.2
        await self.apb_write("b", 0x18, 0xC0A80102) # SRC_IP
        await self.apb_write("b", 0x1c, 0xC0A80101) # DST_IP

        await self.apb_write("b", 0x28, 0xC0A80102) # GATEWAY_IP
        await self.apb_write("b", 0x2C, 0xFFFFFF00) # SUBNET_MASK
        # Configure UDP ports
        await self.apb_write("b", 0x24, 1234)       # DST_PORT
        await self.apb_write("b", 0x20, 1234)       # SRC_PORT

        # Basic readback verification
        readback_ip = await self.apb_read("a", 0x18)
        assert readback_ip == 0xC0A80101, f"APB Readback error: expected 0xC0A80101, got {hex(readback_ip)}"


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
        await self.apb_write("a", 0x1c, 0xC0A80102) # DST_IP
        await self.apb_write("a", 0x28, 0xC0A80102) # GATEWAY_IP
        await self.apb_write("a", 0x2C, 0xFFFFFF00) # SUBNET_MASK
        # Configure UDP ports
        await self.apb_write("a", 0x24, 1234)       # DST_PORT
        await self.apb_write("a", 0x20, 1234)       # SRC_PORT

        # Basic readback verification
        readback_ip = await self.apb_read("a", 0x18)
        assert readback_ip == 0xC0A80101, f"APB Readback error: expected 0xC0A80101, got {hex(readback_ip)}"

    async def setup_fir_a(self, coeffs, num_taps=64):
        """Write FIR coefficients via APB. Zero-pads to num_taps."""
        self.log.info("Configure FIR for Node A (%d taps, %d non-zero)", num_taps, len(coeffs))
        # Pad with zeros to fill all taps
        full_coeffs = list(coeffs) + [0] * (num_taps - len(coeffs))
        for i, c in enumerate(full_coeffs):
            await self.apb_write("fir_a", 1 * 4, i)  # COEFF_ADDR
            await self.apb_write("fir_a", 2 * 4, c & 0xFFFF)  # COEFF_DATA (16-bit)

    async def setup_fir_bypass(self, bypass=True):
        self.log.info(f"Configure FIR Bypass={bypass}")
        await self.apb_write("fir_a", 0 * 4, 1 if bypass else 0)

    async def send_and_receive_udp(self, payload, sport=5678, dport=1234):
        """Send a UDP packet and return the received UDP response, handling ARP."""
        eth = Ether(src='5a:51:52:53:54:55', dst='02:00:00:00:00:00')
        ip = IP(src='192.168.1.2', dst='192.168.1.1')
        udp = UDP(sport=sport, dport=dport)
        test_pkt = eth / ip / udp / payload

        await self.xgmii_source_a.send(XgmiiFrame.from_payload(test_pkt.build()))

        rx_frame = await self.xgmii_sink_a.recv()
        rx_pkt = Ether(bytes(rx_frame.get_payload()))

        if ARP in rx_pkt:
            self.log.info("Handling ARP request")
            eth_arp = Ether(src='5a:51:52:53:54:55', dst='02:00:00:00:00:01')
            arp = ARP(hwtype=1, ptype=0x0800, hwlen=6, plen=4, op=2,
                hwsrc='5a:51:52:53:54:55', psrc='192.168.1.2',
                hwdst='02:00:00:00:00:01', pdst='192.168.1.1')
            await self.xgmii_source_a.send(XgmiiFrame.from_payload((eth_arp / arp).build()))
            rx_frame = await self.xgmii_sink_a.recv()
            rx_pkt = Ether(bytes(rx_frame.get_payload()))

        assert UDP in rx_pkt, "Expected UDP response packet"
        return rx_pkt


# Directory for test output plots
PLOT_DIR = os.path.join(os.path.dirname(__file__), '..', 'sim', 'plots')
os.makedirs(PLOT_DIR, exist_ok=True)


def to_signed8(val):
    """Convert unsigned byte to signed int8."""
    return val - 256 if val > 127 else val


def fir_reference(samples, coeffs, coeff_width=16):
    """Compute reference FIR output for a list of byte samples.

    Mimics the hardware: signed 8-bit samples, signed coeff_width-bit coefficients,
    truncated to 8-bit output.
    """
    num_taps = len(coeffs)
    half = 1 << (coeff_width - 1)
    mask = (1 << coeff_width) - 1
    out = []
    for n in range(len(samples)):
        acc = 0
        for k in range(num_taps):
            idx = n - k
            x = samples[idx] if idx >= 0 else 0
            # Treat sample as signed 8-bit
            if x > 127:
                x -= 256
            # Treat coefficient as signed coeff_width-bit
            c = coeffs[k] & mask
            if c >= half:
                c -= (1 << coeff_width)
            acc += x * c
        out.append(acc & 0xFF)
    return out


def plot_fir_result(title, filename, input_samples, expected, actual,
                    coeffs_label="", signed=True):
    """Save a 3-panel PNG comparing FIR input, expected output, and actual HW output."""
    n = len(input_samples)
    x = np.arange(n)

    if signed:
        inp_plot = [to_signed8(s) for s in input_samples[:n]]
        exp_plot = [to_signed8(s) for s in expected[:n]]
        act_plot = [to_signed8(s) for s in actual[:n]]
        ylabel = 'Amplitude (signed)'
    else:
        inp_plot = list(input_samples[:n])
        exp_plot = list(expected[:n])
        act_plot = list(actual[:n])
        ylabel = 'Amplitude (unsigned)'

    fig, axes = plt.subplots(3, 1, figsize=(14, 8), sharex=True)
    fig.suptitle(f'{title}\nCoeffs: {coeffs_label}', fontsize=13)

    axes[0].plot(x, inp_plot, 'b-', linewidth=0.8, label='Input')
    axes[0].set_ylabel(ylabel)
    axes[0].set_title('Input Signal')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc='upper right')

    axes[1].plot(x, exp_plot, 'g-', linewidth=0.8, label='Expected (Python ref)')
    axes[1].set_ylabel(ylabel)
    axes[1].set_title('Expected FIR Output')
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(loc='upper right')

    axes[2].plot(x, act_plot, 'r-', linewidth=0.8, label='Actual (HW)')
    axes[2].plot(x, exp_plot, 'g--', linewidth=0.5, alpha=0.5, label='Expected')
    axes[2].set_ylabel(ylabel)
    axes[2].set_xlabel('Sample index')
    axes[2].set_title('Actual HW Output vs Expected')
    axes[2].grid(True, alpha=0.3)
    axes[2].legend(loc='upper right')

    # Mark 64-bit word boundaries
    for ax in axes:
        for wb in range(0, n, 8):
            ax.axvline(x=wb, color='gray', linestyle=':', linewidth=0.3)

    plt.tight_layout()
    path = os.path.join(PLOT_DIR, filename)
    plt.savefig(path, dpi=150)
    plt.close(fig)
    return path


@cocotb.test()
async def test_mac_loopback(dut):
    """Test standard UDP MAC loopback on Node A (10G)."""
    tb = TB(dut)
    await tb.init()

    cocotb.start_soon(Clock(dut.xgmii_a_rx_clk, 6.4, units="ns").start())
    cocotb.start_soon(Clock(dut.xgmii_b_rx_clk, 6.4, units="ns").start())

    await tb.setup_mac_a(loopback=True)
    tb.log.info("Test UDP RX packet loopback on Node A")

    payload = bytes([x % 256 for x in range(64)])
    eth = Ether(src='5a:51:52:53:54:55', dst='02:00:00:00:00:00')
    ip = IP(src='192.168.1.2', dst='192.168.1.1')
    udp = UDP(sport=1234, dport=1234)
    test_pkt = eth / ip / udp / payload

    test_frame = XgmiiFrame.from_payload(test_pkt.build())
    await tb.xgmii_source_a.send(test_frame)

    # ARP Response
    rx_frame = await tb.xgmii_sink_a.recv()
    rx_pkt = Ether(bytes(rx_frame.get_payload()))
    tb.log.info("RX ARP packet: %s", repr(rx_pkt))

    assert ARP in rx_pkt
    
    eth_arp = Ether(src='5a:51:52:53:54:55', dst='02:00:00:00:00:01')
    arp = ARP(hwtype=1, ptype=0x0800, hwlen=6, plen=4, op=2,
        hwsrc='5a:51:52:53:54:55', psrc='192.168.1.2',
        hwdst='02:00:00:00:00:01', pdst='192.168.1.1')
    await tb.xgmii_source_a.send(XgmiiFrame.from_payload((eth_arp / arp).build()))
        
    # UDP Payload Response
    rx_frame = await tb.xgmii_sink_a.recv()
    rx_pkt = Ether(bytes(rx_frame.get_payload()))
    tb.log.info("RX UDP packet: %s", repr(rx_pkt))

    assert UDP in rx_pkt
    assert rx_pkt.dst == '5a:51:52:53:54:55'
    assert rx_pkt[UDP].payload == test_pkt[UDP].payload
    
    for _ in range(100):
        await RisingEdge(dut.clk)

@cocotb.test()
async def test_fir_loopback(dut):
    """Test UDP loopback via FIR Bypass on Node A (10G)."""
    tb = TB(dut)
    await tb.init()

    cocotb.start_soon(Clock(dut.xgmii_a_rx_clk, 6.4, units="ns").start())
    cocotb.start_soon(Clock(dut.xgmii_b_rx_clk, 6.4, units="ns").start())

    # MAC loopback must be DISABLED so it forwards to FIR
    await tb.setup_mac_a(loopback=False)
    # FIR is configured to BYPASS (which acts as a loopback)
    tb.log.info("Test UDP RX packet loopback via FIR Bypass on Node A")
    await tb.setup_fir_bypass(bypass=True)

    payload = bytes([x % 256 for x in range(64)])
    eth = Ether(src='5a:51:52:53:54:55', dst='02:00:00:00:00:00')
    ip = IP(src='192.168.1.2', dst='192.168.1.1')
    udp = UDP(sport=1235, dport=1234)
    test_pkt = eth / ip / udp / payload

    test_frame = XgmiiFrame.from_payload(test_pkt.build())
    await tb.xgmii_source_a.send(test_frame)

    # ARP Response
    rx_frame = await tb.xgmii_sink_a.recv()
    rx_pkt = Ether(bytes(rx_frame.get_payload()))
    tb.log.info("RX ARP packet: %s", repr(rx_pkt))

    assert ARP in rx_pkt
    
    eth_arp = Ether(src='5a:51:52:53:54:55', dst='02:00:00:00:00:01')
    arp = ARP(hwtype=1, ptype=0x0800, hwlen=6, plen=4, op=2,
        hwsrc='5a:51:52:53:54:55', psrc='192.168.1.2',
        hwdst='02:00:00:00:00:01', pdst='192.168.1.1')
    await tb.xgmii_source_a.send(XgmiiFrame.from_payload((eth_arp / arp).build()))
        
    # UDP Payload Response
    rx_frame = await tb.xgmii_sink_a.recv()
    rx_pkt = Ether(bytes(rx_frame.get_payload()))
    tb.log.info("RX UDP packet: %s", repr(rx_pkt))

    assert UDP in rx_pkt
    assert rx_pkt.dst == '5a:51:52:53:54:55'
    assert rx_pkt[UDP].payload == test_pkt[UDP].payload
    
    for _ in range(100):
        await RisingEdge(dut.clk)


@cocotb.test()
async def test_fir_processing(dut):
    """Test UDP RX packet forwarding and FIR multiplication on Node A (10G)."""
    tb = TB(dut)
    await tb.init()

    # Need clocks for XGMII on B if we test B, but we are only testing A loopback
    cocotb.start_soon(Clock(dut.xgmii_a_rx_clk, 6.4, units="ns").start())
    cocotb.start_soon(Clock(dut.xgmii_b_rx_clk, 6.4, units="ns").start())

    # Configure Node A to NOT loopback
    await tb.setup_mac_a(loopback=False)

    # Configure FIR to multiply by 2 and disable bypass
    await tb.setup_fir_a([2, 0, 0, 0])
    await tb.setup_fir_bypass(bypass=False)

    tb.log.info("Test UDP RX packet processing via FIR on Node A")

    # Limit payload to 0-120 to avoid unsigned byte overflow after multiplying by 2
    payload_bytes = [x for x in range(32)]
    payload = bytes(payload_bytes)
    eth = Ether(src='5a:51:52:53:54:55', dst='02:00:00:00:00:00')
    ip = IP(src='192.168.1.2', dst='192.168.1.1')
    udp = UDP(sport=5678, dport=1234)
    test_pkt = eth / ip / udp / payload
    
    # We must respond to ARP first
    await tb.xgmii_source_a.send(XgmiiFrame.from_payload(test_pkt.build()))

    rx_frame = await tb.xgmii_sink_a.recv()
    rx_pkt = Ether(bytes(rx_frame.get_payload()))
    if ARP in rx_pkt:
        eth_arp = Ether(src='5a:51:52:53:54:55', dst='02:00:00:00:00:01')
        arp = ARP(hwtype=1, ptype=0x0800, hwlen=6, plen=4, op=2,
            hwsrc='5a:51:52:53:54:55', psrc='192.168.1.2',
            hwdst='02:00:00:00:00:01', pdst='192.168.1.1')
        await tb.xgmii_source_a.send(XgmiiFrame.from_payload((eth_arp / arp).build()))
        rx_frame = await tb.xgmii_sink_a.recv()
        rx_pkt = Ether(bytes(rx_frame.get_payload()))

    assert UDP in rx_pkt
    
    # The returned payload should be exactly the source multiplied by 2!
    expected_payload_bytes = bytes([x * 2 for x in payload_bytes])
    
    assert rx_pkt.dst == '5a:51:52:53:54:55'
    assert rx_pkt[UDP].payload.load[:32] == expected_payload_bytes[:32], f"FIR failed to multiply! Expected {expected_payload_bytes[:32].hex()}, got {rx_pkt[UDP].payload.load[:32].hex()}"
    
    tb.log.info("Successfully validated FIR multiplier forward mode on Node A (10G)")
    for _ in range(100):
        await RisingEdge(dut.clk)


# =========================================================================
# Realistic FIR test cases with signal processing
# =========================================================================

@cocotb.test()
async def test_fir_sine_wave_gain(dut):
    """Test FIR gain on a quantized sine wave signal.

    Generates a low-frequency sine wave (quantized to 8-bit signed),
    applies a gain-of-3 FIR (coeffs=[3,0,0,0]), and verifies
    each output byte matches the expected scaled value.
    """
    tb = TB(dut)
    await tb.init()

    cocotb.start_soon(Clock(dut.xgmii_a_rx_clk, 6.4, units="ns").start())
    cocotb.start_soon(Clock(dut.xgmii_b_rx_clk, 6.4, units="ns").start())

    await tb.setup_mac_a(loopback=False)

    # Gain of 3, single tap
    await tb.setup_fir_a([3, 0, 0, 0])
    await tb.setup_fir_bypass(bypass=False)

    tb.log.info("Test FIR gain=3 on a quantized sine wave")

    # Generate a sine wave: 64 samples, amplitude=40 (stays within 8-bit after *3)
    num_samples = 64
    amplitude = 40  # 40 * 3 = 120, fits in signed 8-bit [-128..127]
    freq = 4  # 4 full cycles across 64 samples
    samples = []
    for n in range(num_samples):
        val = int(amplitude * math.sin(2 * math.pi * freq * n / num_samples))
        samples.append(val & 0xFF)  # Convert to unsigned byte

    payload = bytes(samples)

    tb.log.info("Sine wave payload (first 16): %s", [f"0x{b:02x}" for b in payload[:16]])

    rx_pkt = await tb.send_and_receive_udp(payload)

    # Compute expected: each signed sample * 3, truncated to 8 bits
    expected = fir_reference(samples, [3, 0, 0, 0])

    rx_data = list(rx_pkt[UDP].payload.load[:num_samples])
    tb.log.info("RX payload  (first 16): %s", [f"0x{b:02x}" for b in rx_data[:16]])
    tb.log.info("Expected    (first 16): %s", [f"0x{b:02x}" for b in expected[:16]])

    # Save visualization
    png = plot_fir_result(
        'FIR Gain=3 on Sine Wave', 'fir_sine_gain.png',
        samples, expected, rx_data, coeffs_label='[3, 0, 0, 0]'
    )
    tb.log.info("Plot saved: %s", png)

    assert rx_data == expected, (
        f"Sine wave gain mismatch!\n"
        f"  Expected: {bytes(expected).hex()}\n"
        f"  Got:      {bytes(rx_data).hex()}"
    )

    tb.log.info("PASS: FIR gain=3 on sine wave verified")
    for _ in range(100):
        await RisingEdge(dut.clk)


@cocotb.test()
async def test_fir_moving_average(dut):
    """Test FIR as a 4-tap moving average filter on a noisy step signal.

    Input: a step function (0 → 80) with added pseudo-random noise.
    Coeffs: [1, 1, 1, 1] — simple 4-sample sum (acts as moving average
    without division, but the trend should smooth the step).
    Verifies output matches the Python reference FIR computation.
    """
    tb = TB(dut)
    await tb.init()

    cocotb.start_soon(Clock(dut.xgmii_a_rx_clk, 6.4, units="ns").start())
    cocotb.start_soon(Clock(dut.xgmii_b_rx_clk, 6.4, units="ns").start())

    await tb.setup_mac_a(loopback=False)

    # 4-tap moving sum: [1, 1, 1, 1]
    await tb.setup_fir_a([1, 1, 1, 1])
    await tb.setup_fir_bypass(bypass=False)

    tb.log.info("Test FIR moving average on noisy step signal")

    # Generate noisy step signal: 32 samples of ~0, then 32 samples of ~20
    # Use a simple PRNG for reproducible noise
    num_samples = 64
    samples = []
    seed = 42
    for n in range(num_samples):
        base = 0 if n < 32 else 20
        # Simple LCG noise: ±5 range
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        noise = (seed >> 16) % 11 - 5  # Range: -5 to +5
        val = max(0, min(60, base + noise))  # Clamp to safe unsigned range
        samples.append(val & 0xFF)

    payload = bytes(samples)
    tb.log.info("Noisy step (first 16): %s", list(payload[:16]))
    tb.log.info("Noisy step (last 16):  %s", list(payload[-16:]))

    rx_pkt = await tb.send_and_receive_udp(payload)

    expected = fir_reference(samples, [1, 1, 1, 1])

    rx_data = list(rx_pkt[UDP].payload.load[:num_samples])
    tb.log.info("RX result  (first 16): %s", rx_data[:16])
    tb.log.info("Expected   (first 16): %s", expected[:16])

    png = plot_fir_result(
        'FIR Moving Average on Noisy Step', 'fir_moving_avg.png',
        samples, expected, rx_data, coeffs_label='[1, 1, 1, 1]', signed=False
    )
    tb.log.info("Plot saved: %s", png)

    assert rx_data == expected, (
        f"Moving average mismatch!\n"
        f"  Expected: {bytes(expected).hex()}\n"
        f"  Got:      {bytes(rx_data).hex()}"
    )

    tb.log.info("PASS: FIR 4-tap moving average verified")
    for _ in range(100):
        await RisingEdge(dut.clk)


@cocotb.test()
async def test_fir_differentiator(dut):
    """Test FIR as a simple differentiator (first difference).

    Coeffs: [1, -1, 0, 0] — computes y[n] = x[n] - x[n-1].
    Input: a slow ramp (constant slope) should produce near-constant output.
    Verifies analytical derivative property and cross-word boundary correctness.
    """
    tb = TB(dut)
    await tb.init()

    cocotb.start_soon(Clock(dut.xgmii_a_rx_clk, 6.4, units="ns").start())
    cocotb.start_soon(Clock(dut.xgmii_b_rx_clk, 6.4, units="ns").start())

    await tb.setup_mac_a(loopback=False)

    # Differentiator: y[n] = x[n] - x[n-1]
    # coeffs[0]=1, coeffs[1]=-1 (as 16-bit signed: 0xFFFF)
    await tb.setup_fir_a([1, 0xFFFF, 0, 0])
    await tb.setup_fir_bypass(bypass=False)

    tb.log.info("Test FIR differentiator on a ramp signal")

    # Ramp signal: each sample increases by 3
    num_samples = 64
    slope = 3
    samples = [(n * slope) & 0xFF for n in range(num_samples)]
    payload = bytes(samples)

    tb.log.info("Ramp input (first 16): %s", list(payload[:16]))

    rx_pkt = await tb.send_and_receive_udp(payload)

    expected = fir_reference(samples, [1, -1, 0, 0])

    rx_data = list(rx_pkt[UDP].payload.load[:num_samples])
    tb.log.info("RX diff    (first 16): %s", rx_data[:16])
    tb.log.info("Expected   (first 16): %s", expected[:16])

    # First sample: x[0] - 0 = x[0]; remaining samples: x[n] - x[n-1] = slope
    png = plot_fir_result(
        'FIR Differentiator on Ramp', 'fir_differentiator.png',
        samples, expected, rx_data, coeffs_label='[1, -1, 0, 0]', signed=False
    )
    tb.log.info("Plot saved: %s", png)

    assert rx_data == expected, (
        f"Differentiator mismatch!\n"
        f"  Expected: {bytes(expected).hex()}\n"
        f"  Got:      {bytes(rx_data).hex()}"
    )

    # Also verify the analytical property: output[1:] should all equal slope
    for i in range(1, min(num_samples, len(rx_data))):
        assert rx_data[i] == (slope & 0xFF), (
            f"Differentiator output[{i}] = {rx_data[i]}, expected constant {slope}"
        )

    tb.log.info("PASS: FIR differentiator verified (constant slope=%d)", slope)
    for _ in range(100):
        await RisingEdge(dut.clk)


@cocotb.test()
async def test_fir_sine_dual_freq(dut):
    """Test FIR low-pass effect on a signal with two frequency components.

    Input: sum of low-freq sine (2 cycles/packet) + high-freq sine (16 cycles/packet).
    Coeffs: [1, 1, 1, 1] — moving sum acts as a low-pass filter.
    Verifies that the FIR output matches the Python reference.
    Also checks that high-frequency energy is attenuated relative to low-frequency.
    """
    tb = TB(dut)
    await tb.init()

    cocotb.start_soon(Clock(dut.xgmii_a_rx_clk, 6.4, units="ns").start())
    cocotb.start_soon(Clock(dut.xgmii_b_rx_clk, 6.4, units="ns").start())

    await tb.setup_mac_a(loopback=False)

    # Low-pass: 4-tap moving sum
    await tb.setup_fir_a([1, 1, 1, 1])
    await tb.setup_fir_bypass(bypass=False)

    tb.log.info("Test FIR low-pass on dual-frequency sine signal")

    num_samples = 64
    f_low = 2    # 2 cycles across the packet (low frequency)
    f_high = 16  # 16 cycles across the packet (high frequency)
    a_low = 15   # Amplitude of low-frequency component
    a_high = 10  # Amplitude of high-frequency component

    samples = []
    for n in range(num_samples):
        low  = a_low  * math.sin(2 * math.pi * f_low  * n / num_samples)
        high = a_high * math.sin(2 * math.pi * f_high * n / num_samples)
        val = int(low + high) + 64  # DC offset to keep positive
        val = max(0, min(127, val))  # Clamp to safe range
        samples.append(val & 0xFF)

    payload = bytes(samples)
    tb.log.info("Dual-freq input (first 16): %s", list(payload[:16]))

    rx_pkt = await tb.send_and_receive_udp(payload)

    expected = fir_reference(samples, [1, 1, 1, 1])

    rx_data = list(rx_pkt[UDP].payload.load[:num_samples])
    tb.log.info("RX filtered (first 16): %s", rx_data[:16])
    tb.log.info("Expected    (first 16): %s", expected[:16])

    png = plot_fir_result(
        'FIR Low-Pass on Dual-Frequency Signal', 'fir_dual_freq.png',
        samples, expected, rx_data, coeffs_label='[1, 1, 1, 1]'
    )
    tb.log.info("Plot saved: %s", png)

    assert rx_data == expected, (
        f"Dual-freq filter mismatch!\n"
        f"  Expected: {bytes(expected).hex()}\n"
        f"  Got:      {bytes(rx_data).hex()}"
    )

    tb.log.info("PASS: FIR low-pass on dual-frequency signal verified")
    for _ in range(100):
        await RisingEdge(dut.clk)


@cocotb.test()
async def test_fir_lowpass_1500B(dut):
    """Test FIR low-pass filter on a full 1500B Ethernet MTU UDP packet.

    Generates a 1472-byte payload (max UDP payload for 1500B Ethernet MTU)
    containing a sum of three sine waves at different frequencies:
      - 3 Hz  (low)  — should pass through
      - 25 Hz (mid)  — partially attenuated
      - 100 Hz (high) — strongly attenuated by the moving average

    Coeffs: [1, 1, 1, 1] — 4-tap moving sum (low-pass).
    Saves a detailed before/after PNG visualization.
    """
    tb = TB(dut)
    await tb.init()

    cocotb.start_soon(Clock(dut.xgmii_a_rx_clk, 6.4, units="ns").start())
    cocotb.start_soon(Clock(dut.xgmii_b_rx_clk, 6.4, units="ns").start())

    await tb.setup_mac_a(loopback=False)

    # Design a proper 64-tap low-pass FIR filter with scipy
    # Cutoff at normalized freq 0.1 (passes low freqs, attenuates high)
    num_taps = 64
    cutoff = 0.1  # Normalized cutoff frequency (0 to 1, where 1 = Nyquist)
    fir_float = firwin(num_taps, cutoff)

    # Quantize to 16-bit signed integers: scale to use full range
    coeff_scale = 2**14  # Use 14 bits of headroom (max coeff ~16384)
    fir_int16 = [int(round(c * coeff_scale)) for c in fir_float]
    # Convert to unsigned 16-bit for APB (two's complement)
    fir_apb = [c & 0xFFFF for c in fir_int16]

    tb.log.info("64-tap FIR coefficients (first 8): %s", fir_int16[:8])
    tb.log.info("64-tap FIR coefficients (mid 8):   %s", fir_int16[28:36])

    await tb.setup_fir_a(fir_apb)
    await tb.setup_fir_bypass(bypass=False)

    tb.log.info("Test FIR 64-tap low-pass (cutoff=%.2f) on 1472B UDP packet", cutoff)

    # Max UDP payload for 1500B Ethernet MTU:
    # 1500 - 20 (IP hdr) - 8 (UDP hdr) = 1472 bytes
    num_samples = 1472
    fs = num_samples  # Treat sample rate = num_samples for easy freq mapping
    f_low = 30      # ~3 cycles across the packet
    f_mid = 100     # ~25 cycles
    f_high = 250   # ~100 cycles — well above Nyquist/4 for 4-tap filter

    a_low = 20
    a_mid = 20
    a_high = 20
    dc_offset = 64  # Keep values positive

    t = np.arange(num_samples)
    signal = (
        a_low  * np.sin(2 * np.pi * f_low  * t / fs) +
        a_mid  * np.sin(2 * np.pi * f_mid  * t / fs) +
        a_high * np.sin(2 * np.pi * f_high * t / fs) +
        dc_offset
    )
    # Quantize to unsigned 8-bit, clamp to [0, 127] to avoid signed overflow
    samples = [int(max(0, min(127, round(s)))) & 0xFF for s in signal]

    payload = bytes(samples)
    tb.log.info("Payload size: %d bytes (target: 1472)", len(payload))

    rx_pkt = await tb.send_and_receive_udp(payload)

    expected = fir_reference(samples, fir_int16, coeff_width=16)
    rx_data = list(rx_pkt[UDP].payload.load[:num_samples])

    tb.log.info("RX payload length: %d", len(rx_data))

    # Save a comprehensive 5-panel plot
    fig, axes = plt.subplots(5, 1, figsize=(16, 14), sharex=False)
    fig.suptitle(
        f'FIR 64-Tap Low-Pass on 1472B UDP Packet\n'
        f'Input: {f_low}Hz + {f_mid}Hz + {f_high}Hz | cutoff={cutoff} | 16-bit coeffs',
        fontsize=13
    )

    # Panel 1: Input signal
    inp_signed = [to_signed8(s) for s in samples]
    axes[0].plot(t, inp_signed, 'b-', linewidth=0.4)
    axes[0].set_ylabel('Amplitude')
    axes[0].set_title(f'Input Signal ({num_samples} samples)')
    axes[0].grid(True, alpha=0.3)

    # Panel 2: Expected output
    exp_signed = [to_signed8(s) for s in expected]
    axes[1].plot(t, exp_signed, 'g-', linewidth=0.4)
    axes[1].set_ylabel('Amplitude')
    axes[1].set_title('Expected FIR Output (Python reference)')
    axes[1].grid(True, alpha=0.3)

    # Panel 3: Actual HW output overlaid with expected
    act_signed = [to_signed8(s) for s in rx_data]
    axes[2].plot(t[:len(act_signed)], act_signed, 'r-', linewidth=0.4, label='HW')
    axes[2].plot(t, exp_signed, 'g--', linewidth=0.3, alpha=0.5, label='Expected')
    axes[2].set_ylabel('Amplitude')
    axes[2].set_title('Actual HW Output vs Expected')
    axes[2].grid(True, alpha=0.3)
    axes[2].legend(loc='upper right')

    # Panel 4: Frequency spectrum comparison (input vs output)
    inp_fft = np.abs(np.fft.rfft(inp_signed))
    out_fft = np.abs(np.fft.rfft(act_signed[:num_samples]))
    freqs = np.fft.rfftfreq(num_samples, d=1.0)
    axes[3].semilogy(freqs[:len(inp_fft)], inp_fft + 1, 'b-', linewidth=0.6, label='Input spectrum')
    axes[3].semilogy(freqs[:len(out_fft)], out_fft + 1, 'r-', linewidth=0.6, label='Output spectrum')
    axes[3].set_xlabel('Normalized frequency')
    axes[3].set_ylabel('Magnitude (log)')
    axes[3].set_title('Frequency Spectrum (Input vs Output)')
    axes[3].grid(True, alpha=0.3)
    axes[3].legend(loc='upper right')


    
    N = num_samples
    window = np.hanning(N)

    # Obliczenie FFT z normalizacją i oknem
    inp_fft = np.abs(np.fft.rfft(inp_signed * window)) / N
    out_fft = np.abs(np.fft.rfft(act_signed[:N] * window)) / N

    # Konwersja na dB (dodajemy małą stałą, aby uniknąć log(0))
    inp_db = 20 * np.log10(inp_fft + 1e-9)
    out_db = 20 * np.log10(out_fft + 1e-9)

    freqs = np.fft.rfftfreq(N, d=1.0)

    axes[4].plot(freqs, inp_db, 'b-', linewidth=0.8, label='Input (dB)', alpha=0.7)
    axes[4].plot(freqs, out_db, 'r-', linewidth=0.8, label='Output (dB)', alpha=0.7)

    axes[4].set_ylim(bottom=-100, top=max(inp_db.max(), out_db.max()) + 10)
    axes[4].set_xlim((0, 0.5))

    axes[4].set_xlabel('Normalized Frequency (cycles/sample)')
    axes[4].set_ylabel('Magnitude [dB]')
    axes[4].set_title('Power Spectral Density (Normalized)')
    axes[4].grid(True, which='both', linestyle='--', alpha=0.5)
    axes[4].legend(loc='upper right')


    plt.tight_layout()
    png_path = os.path.join(PLOT_DIR, 'fir_lowpass_1500B.png')
    plt.savefig(png_path, dpi=150)
    plt.close(fig)
    tb.log.info("Plot saved: %s", png_path)

    assert rx_data == expected, (
        f"1500B FIR low-pass mismatch!\n"
        f"  First 32 expected: {bytes(expected[:32]).hex()}\n"
        f"  First 32 got:      {bytes(rx_data[:32]).hex()}"
    )

    tb.log.info("PASS: FIR low-pass on 1472B UDP packet verified")
    for _ in range(100):
        await RisingEdge(dut.clk)
