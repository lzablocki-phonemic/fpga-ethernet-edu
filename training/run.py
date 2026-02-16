import os
from pathlib import Path
from cocotb_tools.runner import get_runner

def run_simulation():
    # Identify the directory where this script sits
    training_path = Path(__file__).resolve().parent
    design_v = training_path / "my_design.v"
    
    sim = os.getenv("SIM", "icarus")
    runner = get_runner(sim)

    # Build the design
    runner.build(
        sources=[design_v],
        hdl_toplevel="my_design",
        always=True
    )

    # Run the test
    runner.test(
        hdl_toplevel="my_design",
        test_module="test_my_design",
        waves=True  # We use the internal Verilog $dumpfile instead
    )

if __name__ == "__main__":
    run_simulation()