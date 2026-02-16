"""
Cocotb testbench for fir_filter_apbConfig — APB-configured FIR filter.

APB Register Map:
  0x00 CTRL        - bit0: bypass
  0x04 COEFF_ADDR  - coefficient index
  0x08 COEFF_DATA  - coefficient value (write triggers coeff_we pulse)

Tests:
  1. Bypass/loopback — enable bypass via APB, data passes through unchanged
  2. Impulse response — load known coefficients via APB, send unit impulse
  3. Step response    — send all-1s, verify accumulation
  4. Back-pressure   — toggle m_axis_tready to test flow control
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge


# =============================================================================
# APB Register Addresses
# =============================================================================
APB_IDX_CTRL       = 0
APB_IDX_COEFF_ADDR = 1
APB_IDX_COEFF_DATA = 2

def reg_addr(idx):
    """Convert register index to byte address (word-aligned)."""
    return idx * 4


# =============================================================================
# APB helpers
# =============================================================================

async def apb_write(dut, addr, data):
    """Perform a single APB write transaction (SETUP + ACCESS phase)."""
    dut.paddr.value   = addr
    dut.pwdata.value  = data
    dut.pwrite.value  = 1
    dut.psel.value    = 1
    dut.penable.value = 0
    await RisingEdge(dut.clk)

    dut.penable.value = 1
    await RisingEdge(dut.clk)

    while not dut.pready.value:
        await RisingEdge(dut.clk)

    dut.psel.value    = 0
    dut.penable.value = 0
    dut.pwrite.value  = 0
    await RisingEdge(dut.clk)


async def load_coefficients(dut, coeffs):
    """Load FIR coefficients via APB COEFF_ADDR / COEFF_DATA registers."""
    for i, c in enumerate(coeffs):
        await apb_write(dut, reg_addr(APB_IDX_COEFF_ADDR), i)
        await apb_write(dut, reg_addr(APB_IDX_COEFF_DATA), c)


# =============================================================================
# AXI-Stream helpers
# =============================================================================

async def reset(dut):
    """Apply synchronous reset for several cycles."""
    dut.rst.value           = 1
    dut.psel.value          = 0
    dut.penable.value       = 0
    dut.pwrite.value        = 0
    dut.paddr.value         = 0
    dut.pwdata.value        = 0
    dut.s_axis_tdata.value  = 0
    dut.s_axis_tvalid.value = 0
    dut.s_axis_tlast.value  = 0
    dut.m_axis_tready.value = 1
    for _ in range(10):
        await RisingEdge(dut.clk)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


async def send_sample(dut, data, last=False):
    """Send a single sample via AXI-Stream input."""
    dut.s_axis_tdata.value  = data
    dut.s_axis_tvalid.value = 1
    dut.s_axis_tlast.value  = 1 if last else 0
    while True:
        await RisingEdge(dut.clk)
        if dut.s_axis_tready.value == 1:
            break
    dut.s_axis_tvalid.value = 0
    dut.s_axis_tlast.value  = 0


async def recv_sample(dut, timeout=100):
    """Receive a single sample from AXI-Stream output. Returns (data, last)."""
    dut.m_axis_tready.value = 1
    for _ in range(timeout):
        await RisingEdge(dut.clk)
        if dut.m_axis_tvalid.value == 1:
            data = int(dut.m_axis_tdata.value)
            last = int(dut.m_axis_tlast.value)
            return data, last
    raise TimeoutError("No output sample received")


# =============================================================================
# Test 1: Bypass Mode
# =============================================================================
@cocotb.test()
async def test_bypass(dut):
    """Enable bypass via APB CTRL[0]=1; output must match input exactly."""
    cocotb.start_soon(Clock(dut.clk, 10, unit='ns').start())
    await reset(dut)

    await apb_write(dut, reg_addr(APB_IDX_CTRL), 0x1)

    test_values = [0, 1, 42, 255, 1000, 65535]
    for i, val in enumerate(test_values):
        last = (i == len(test_values) - 1)
        await send_sample(dut, val, last=last)
        data, got_last = await recv_sample(dut)
        assert data == val, f"Bypass mismatch: sent {val}, got {data}"
        if last:
            assert got_last == 1, "Expected tlast on final sample"

    dut._log.info("Bypass mode test PASSED")


# =============================================================================
# Test 2: Impulse Response
# =============================================================================
@cocotb.test()
async def test_impulse_response(dut):
    """
    Load coefficients [1, 2, 3, 4] via APB, send a unit impulse (1, 0, 0, 0).
    Expected output: h[0]=1, h[1]=2, h[2]=3, h[3]=4.
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit='ns').start())
    await reset(dut)

    await load_coefficients(dut, [1, 2, 3, 4])
    await apb_write(dut, reg_addr(APB_IDX_CTRL), 0x0)  # bypass off

    samples = [1, 0, 0, 0]
    results = []
    for i, s in enumerate(samples):
        await send_sample(dut, s, last=(i == len(samples) - 1))
        data, _ = await recv_sample(dut)
        results.append(data)

    dut._log.info(f"Impulse response: {results}")
    expected = [1, 2, 3, 4]
    assert results == expected, f"Impulse response mismatch: {results} != {expected}"

    dut._log.info("Impulse response test PASSED")


# =============================================================================
# Test 3: Step Response
# =============================================================================
@cocotb.test()
async def test_step_response(dut):
    """
    Load coefficients [1, 1, 1, 1] via APB, send a step (all 1s).
    Expected: cumulative sum: 1, 2, 3, 4, 4, 4, ...
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit='ns').start())
    await reset(dut)

    await load_coefficients(dut, [1, 1, 1, 1])
    await apb_write(dut, reg_addr(APB_IDX_CTRL), 0x0)  # bypass off

    num_samples = 6
    results = []
    for i in range(num_samples):
        await send_sample(dut, 1, last=(i == num_samples - 1))
        data, _ = await recv_sample(dut)
        results.append(data)

    dut._log.info(f"Step response: {results}")
    expected = [1, 2, 3, 4, 4, 4]
    assert results == expected, f"Step response mismatch: {results} != {expected}"

    dut._log.info("Step response test PASSED")


# =============================================================================
# Test 4: Back-Pressure
# =============================================================================
@cocotb.test()
async def test_backpressure(dut):
    """
    Toggle m_axis_tready to test flow control. Verify no data is lost
    and all samples are received correctly (bypass mode for simplicity).
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit='ns').start())
    await reset(dut)

    await apb_write(dut, reg_addr(APB_IDX_CTRL), 0x1)  # bypass on

    test_values = [10, 20, 30, 40, 50]
    results = []

    for i, val in enumerate(test_values):
        if i % 2 == 1:
            dut.m_axis_tready.value = 0
            await send_sample(dut, val, last=(i == len(test_values) - 1))
            for _ in range(3):
                await RisingEdge(dut.clk)
            dut.m_axis_tready.value = 1
            data, _ = await recv_sample(dut)
            results.append(data)
        else:
            dut.m_axis_tready.value = 1
            await send_sample(dut, val, last=(i == len(test_values) - 1))
            data, _ = await recv_sample(dut)
            results.append(data)

    dut._log.info(f"Back-pressure results: {results}")
    assert results == test_values, f"Back-pressure mismatch: {results} != {test_values}"

    dut._log.info("Back-pressure test PASSED")
