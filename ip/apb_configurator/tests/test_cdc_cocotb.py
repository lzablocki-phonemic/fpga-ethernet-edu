import cocotb
import os
import random
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

async def apb_write(dut, reg_index, val):
    """Perform an APB write transaction using register index.
    
    Args:
        dut: The device under test (cocotb DUT object)
        reg_index: The register index (0-based)
        val: The value to write to the register
    
    This function calculates the byte address from the register index,
    data width, and base address, then performs a standard APB write.
    """
    # Calculate parameters from DUT configuration
    WIDTH = int(dut.APB_DATA_WIDTH.value)
    BASE = int(dut.BASE_ADDR.value)
    # Convert register index to byte address (word-aligned)
    addr = BASE + (reg_index * (WIDTH // 8))

    await RisingEdge(dut.pclk)
    
    # SETUP phase: Set address, data, and control signals
    dut.paddr.value = addr
    dut.pwdata.value = val
    dut.psel.value = 1       # Select peripheral
    dut.pwrite.value = 1     # Write operation
    dut.penable.value = 0    # PENABLE low during setup
    
    await RisingEdge(dut.pclk)
    
    # ACCESS phase: Assert PENABLE and wait for PREADY
    dut.penable.value = 1
    while not dut.pready.value:
        await RisingEdge(dut.pclk)
    
    # Return to idle state
    dut.psel.value = 0
    dut.penable.value = 0

@cocotb.test()
async def run_cdc_test(dut):
    """Test Clock Domain Crossing (CDC) functionality.
    
    This test verifies that data written on the APB clock domain is correctly
    transferred to the readout clock domain through CDC synchronizers.
    
    The test runs multiple timing scenarios controlled by the CLOCK_SCENARIO
    environment variable:
    - FAST_APB: Fast APB clock (100MHz), slow readout (25MHz)
    - SLOW_APB: Slow APB clock (25MHz), fast readout (100MHz)
    - EQUAL_APB: Equal clock speeds (100MHz both) with phase offset
    
    For each scenario, the test:
    1. Writes random values to random registers on the APB domain
    2. Waits for CDC propagation delay
    3. Reads the values on the readout clock domain
    4. Verifies data integrity across clock domains
    
    This ensures the CDC logic works correctly regardless of relative clock speeds.
    """
    # 1. Read test scenario from environment variable (set by pytest)
    # This allows running the same test with different clock configurations
    scenario = os.environ.get("CLOCK_SCENARIO", "FAST_APB")
    
    # 2. Configure clock periods based on scenario
    # Testing different relative clock speeds ensures CDC logic is robust
    if scenario == "FAST_APB":
        pclk_per = 10  # APB clock: 100 MHz (fast write domain)
        rd_clk_per = 40 # Readout clock: 25 MHz (slow read domain)
        dut._log.info("SCENARIO: Fast APB (10ns), Slow Readout (40ns)")
    elif scenario == "SLOW_APB":
        pclk_per = 40  # APB clock: 25 MHz (slow write domain)
        rd_clk_per = 10 # Readout clock: 100 MHz (fast read domain)
        dut._log.info("SCENARIO: Slow APB (40ns), Fast Readout (10ns)")
    else: # EQUAL_APB or default
        pclk_per = 10  # APB clock: 100 MHz
        rd_clk_per = 10 # Readout clock: 100 MHz (same speed, tests phase offset)
        dut._log.info("SCENARIO: Equal Speeds (10ns)")

    # Start APB clock immediately
    cocotb.start_soon(Clock(dut.pclk, pclk_per, units="ns").start())
    
    # Start readout clock with 3ns phase shift
    # This tests setup/hold timing and ensures CDC works with arbitrary phase relationships
    await Timer(3, units="ns") 
    cocotb.start_soon(Clock(dut.rd_clk, rd_clk_per, units="ns").start())

    # 3. Apply reset to initialize the design
    dut.presetn.value = 0  # Assert active-low reset
    await Timer(100, units="ns")  # Hold reset for sufficient time
    dut.presetn.value = 1  # Deassert reset
    await RisingEdge(dut.pclk)  # Wait for one APB clock cycle

    # 4. Execute CDC verification logic
    # Read DUT configuration parameters
    NUM_REGS = int(dut.NUM_REGS.value)
    WIDTH = int(dut.APB_DATA_WIDTH.value)

    # Test multiple random register accesses to verify CDC functionality
    # Using 5 iterations provides good coverage without excessive runtime
    for i in range(5):
        # Select random register and generate random test value
        reg_idx = random.randint(0, NUM_REGS - 1)
        test_val = random.getrandbits(WIDTH)

        # Write to register on APB clock domain
        await apb_write(dut, reg_idx, test_val)

        # Wait for CDC propagation delay
        # CDC synchronizers typically need 2-3 destination clock cycles
        # We wait 4x the slower clock period to ensure propagation
        await Timer(max(pclk_per, rd_clk_per) * 4, units="ns")

        # Read from register on readout clock domain
        # The new interface outputs all registers in parallel, so we just read the index
        await RisingEdge(dut.rd_clk)  # Wait for clock edge
        
        # Verify data integrity across clock domains
        # We access the specific register from the array
        observed = dut.rd_data_out[reg_idx].value.integer
        is_ready = int(dut.rd_ready[reg_idx].value)
        
        assert is_ready == 1, f"CDC Ready flag not set for reg {reg_idx}!"
        assert observed == test_val, f"CDC Mismatch on reg {reg_idx}! Expected: {hex(test_val)}, Got: {hex(observed)}"