import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

async def reset_dut(dut):
    dut.presetn.value = 0
    dut.psel.value = 0
    dut.penable.value = 0
    dut.pwrite.value = 0
    await Timer(20, unit="ns")
    dut.presetn.value = 1
    await RisingEdge(dut.pclk)

async def apb_write(dut, address, data):
    await RisingEdge(dut.pclk)
    dut.psel.value = 1
    dut.penable.value = 0
    dut.pwrite.value = 1
    dut.paddr.value = address
    dut.pwdata.value = data
    await RisingEdge(dut.pclk)
    dut.penable.value = 1
    while True:
        await RisingEdge(dut.pclk)
        if dut.pready.value == 1:
            err = dut.pslverr.value
            break
    dut.psel.value = 0
    dut.penable.value = 0
    return err

async def apb_read(dut, address):
    await RisingEdge(dut.pclk)
    dut.psel.value = 1
    dut.penable.value = 0
    dut.pwrite.value = 0
    dut.paddr.value = address
    await RisingEdge(dut.pclk)
    dut.penable.value = 1
    while True:
        await RisingEdge(dut.pclk)
        if dut.pready.value == 1:
            data = dut.prdata.value
            err = dut.pslverr.value
            break
    dut.psel.value = 0
    dut.penable.value = 0
    return data, err

@cocotb.test()
async def test_simple_access(dut):
    """Test standard write and read access.
    
    This test verifies basic APB write and read functionality:
    - Writes a test pattern to register 0
    - Reads back the value and verifies it matches
    - Confirms no APB error is generated for valid access
    - Verifies the config_ready flag is set for the written register
    
    This is a fundamental sanity check that the APB interface works correctly
    for valid addresses and that data is properly stored and retrieved.
    """
    cocotb.start_soon(Clock(dut.pclk, 10, unit="ns").start())
    await reset_dut(dut)

    # Write to Register 0 (Address 0x00)
    await apb_write(dut, 0x00, 0xAABBCCDD)
    
    # Read from Register 0
    data, err = await apb_read(dut, 0x00)
    
    assert err == 0, "APB Error detected on valid access"
    assert data == 0xAABBCCDD, f"Read mismatch. Got {hex(data.to_unsigned())}"
    
    # Check ready flag output
    assert dut.config_ready_out.value.to_unsigned() & 0x1, "Flag for Reg 0 not set"

@cocotb.test()
async def test_error_access(dut):
    """Test access out of bounds.
    
    This test verifies that the APB configurator correctly detects and reports
    errors for out-of-bounds addresses:
    - Attempts to write to address 0x100 (beyond valid register range)
    - Verifies that PSLVERR is asserted (err == 1)
    
    For NUM_REGS=16, valid addresses are 0x00-0x3C (16 registers * 4 bytes each).
    Any access beyond this range should trigger an APB error response.
    """
    cocotb.start_soon(Clock(dut.pclk, 10, unit="ns").start())
    await reset_dut(dut)
    
    # Address 0x100 is out of bounds for default NUM_REGS=16 (max offset 0x3C)
    err = await apb_write(dut, 0x100, 0x12345678)
    assert err == 1, "APB Error NOT detected on invalid access"

@cocotb.test()
async def test_full_range_access(dut):
    """Test read/write access to all registers.
    
    This comprehensive test verifies that all registers in the configurator
    are independently addressable and functional:
    - Writes unique values to all 16 registers (0x1000 + register index)
    - Reads back all registers and verifies data integrity
    - Confirms no errors occur for any valid register address
    - Verifies all config_ready flags are set (one per register)
    
    This test ensures:
    - All registers are accessible and independent
    - No address decoding issues exist
    - The ready flag mechanism works for all registers
    """
    cocotb.start_soon(Clock(dut.pclk, 10, unit="ns").start())
    await reset_dut(dut)

    num_regs = 16 # Default parameter

    # Write unique values to all registers
    for i in range(num_regs):
        await apb_write(dut, i * 4, 0x1000 + i)

    # Verify all registers
    for i in range(num_regs):
        data, err = await apb_read(dut, i * 4)
        assert err == 0, f"Error reading register {i}"
        assert data == 0x1000 + i, f"Register {i} mismatch. Expected {hex(0x1000 + i)}, got {hex(data.to_unsigned())}"

    # Check that all ready flags are set
    assert dut.config_ready_out.value == (1 << num_regs) - 1, "Not all ready flags set"

@cocotb.test()
async def test_reset_behavior(dut):
    """Test that reset clears all registers.
    
    This test verifies the reset functionality of the APB configurator:
    - Writes known values to multiple registers
    - Applies an active-low reset (presetn = 0)
    - Verifies all register data is cleared to 0
    - Verifies all config_ready flags are cleared
    
    Proper reset behavior is critical for:
    - System initialization to a known state
    - Recovery from error conditions
    - Ensuring no stale configuration data persists
    """
    cocotb.start_soon(Clock(dut.pclk, 10, unit="ns").start())
    await reset_dut(dut)

    # Write some values
    await apb_write(dut, 0x00, 0xDEADBEEF)
    await apb_write(dut, 0x04, 0xCAFEBABE)

    # Assert Reset
    dut.presetn.value = 0
    await Timer(50, unit="ns")
    dut.presetn.value = 1
    await RisingEdge(dut.pclk)

    # Verify registers are cleared
    data0, _ = await apb_read(dut, 0x00)
    data1, _ = await apb_read(dut, 0x04)
    
    assert data0 == 0, "Register 0 not cleared by reset"
    assert data1 == 0, "Register 1 not cleared by reset"
    assert dut.config_ready_out.value == 0, "Ready flags not cleared by reset"

@cocotb.test()
async def test_invalid_read(dut):
    """Test reading from an invalid address.
    
    This test verifies error handling for read operations to invalid addresses:
    - Attempts to read from address 0x100 (out of bounds)
    - Verifies PSLVERR is asserted (err == 1)
    - Verifies read data returns 0 (safe default value)
    
    Returning 0 for invalid reads is a defensive design practice that:
    - Prevents undefined behavior
    - Makes debugging easier (predictable error state)
    - Avoids potential security issues from reading unintended data
    """
    cocotb.start_soon(Clock(dut.pclk, 10, unit="ns").start())
    await reset_dut(dut)

    # Read from out-of-bounds address
    data, err = await apb_read(dut, 0x100)
    
    assert err == 1, "APB Error NOT detected on invalid read"
    assert data == 0, "Indvalid read should return 0"

@cocotb.test()
async def test_stress_access(dut):
    """Randomized stress test.
    
    This test performs randomized read/write operations to verify robustness:
    - Executes 100 random transactions (mix of reads and writes)
    - Randomly selects addresses (including some out of bounds)
    - Uses a shadow memory model to track expected values
    - Verifies all operations complete with correct error status
    - Confirms data integrity for all valid accesses
    
    This stress test helps catch:
    - Race conditions or timing issues
    - Edge cases not covered by directed tests
    - Incorrect state machine behavior under varied access patterns
    - Proper error handling mixed with valid operations
    """
    import random
    cocotb.start_soon(Clock(dut.pclk, 10, unit="ns").start())
    await reset_dut(dut)

    num_regs = 16
    access_count = 100
    
    shadow_mem = {}

    for _ in range(access_count):
        is_write = random.choice([True, False])
        reg_idx = random.randint(0, num_regs + 2) # Including some out of bounds
        addr = reg_idx * 4
        
        if is_write:
            wdata = random.randint(0, 0xFFFFFFFF)
            err = await apb_write(dut, addr, wdata)
            
            if reg_idx < num_regs:
                assert err == 0, f"Unexpected write error at index {reg_idx}"
                shadow_mem[reg_idx] = wdata
            else:
                assert err == 1, f"Expected write error at index {reg_idx}"
        else:
            data, err = await apb_read(dut, addr)
            
            if reg_idx < num_regs:
                assert err == 0, f"Unexpected read error at index {reg_idx}"
                expected = shadow_mem.get(reg_idx, 0)
                assert data == expected, f"Data mismatch at {reg_idx}. Expected {hex(expected)}, got {hex(data.to_unsigned())}"
            else:
               assert err == 1, f"Expected read error at index {reg_idx}"
