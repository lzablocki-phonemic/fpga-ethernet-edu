import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
import debugpy 
listen_host, listen_port = debugpy.listen(("localhost", 5678))


@cocotb.test()
async def run_test(dut):
    """Test the counter increments and resets"""
    # Suspend execution until debugger attaches
    debugpy.wait_for_client()
    # Break into debugger for user control
    breakpoint()  # or debugpy.breakpoint() on 3.6 and below

    # Start a 10ns period clock (100MHz)
    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())
    
    # Reset the DUT
    dut._log.info("Resetting DUT...")
    dut.rst.value = 1
    await Timer(20, unit="ns")
    dut.rst.value = 0

    # Run for 15 clock cycles and check the count
    for i in range(15):
        await RisingEdge(dut.clk)
        current_count = dut.count.value
        dut._log.info(f"Cycle {i}: Count is {current_count}")
        
        # Simple check: Ensure reset is low
        assert dut.rst.value == 0, f"Reset active on cycle {i}!"

    dut._log.info("Simulation finished successfully!")