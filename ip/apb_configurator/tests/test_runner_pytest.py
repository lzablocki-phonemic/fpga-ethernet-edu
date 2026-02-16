"""Pytest test runner for APB Configurator CDC tests.

This module uses pytest parametrization to run the CDC cocotb tests across
multiple hardware configurations and timing scenarios. This provides comprehensive
coverage of different design parameters and clock domain crossing conditions.

The test matrix includes:
- Hardware configurations: Different data widths and register counts
- Timing scenarios: Different relative clock speeds between APB and readout domains

Each combination is tested independently to ensure the design works correctly
across all supported configurations.
"""

import warnings
# Ignore deprecation warnings from cocotb_test library to keep output clean
warnings.filterwarnings("ignore", category=DeprecationWarning, module="cocotb_test")

import os
import pytest
from cocotb_test.simulator import run

# Define hardware parameter variations to test
# Testing multiple configurations ensures the design is parameterizable
HARDWARE_CONFIGS = [
    {"width": "32", "regs": "16"},  # Standard 32-bit with 16 registers
    {"width": "64", "regs": "8"}    # Wide 64-bit with fewer registers
]

# Define clock timing scenarios for CDC testing
# Different relative clock speeds test the robustness of CDC synchronizers
TIMING_SCENARIOS = [
    "FAST_APB",   # Fast APB clock, slow readout clock
    "SLOW_APB",   # Slow APB clock, fast readout clock
    "EQUAL_APB"   # Equal clock speeds with phase offset
]

# Parametrize test to run for all combinations of hardware configs and timing scenarios
# This creates 2 hardware configs × 3 timing scenarios = 6 test cases total
@pytest.mark.parametrize("hw_config", HARDWARE_CONFIGS)
@pytest.mark.parametrize("scenario", TIMING_SCENARIOS)
def test_apb_configurator(hw_config, scenario):
    """Run CDC tests for a specific hardware configuration and timing scenario.
    
    Args:
        hw_config: Dictionary with 'width' and 'regs' keys defining hardware parameters
        scenario: String defining the clock timing scenario (FAST_APB, SLOW_APB, EQUAL_APB)
    
    This function:
    1. Sets up directory paths for HDL sources, testbench, and simulation output
    2. Configures the timing scenario via environment variable
    3. Runs the Icarus Verilog simulation with cocotb tests
    4. Each test runs in an isolated simulation build directory
    
    The parametrization ensures comprehensive testing across all supported
    configurations without manually writing separate test functions.
    """
    
    # --- 1. Setup directory paths ---
    # Get absolute path to current tests directory
    # Expected: ip/apb_configurator/tests
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Navigate to HDL source directory
    # Expected: ip/apb_configurator/hdl
    hdl_dir = os.path.join(tests_dir, '..', 'hdl')
    
    # Navigate to testbench directory (contains CDC wrapper)
    # Expected: ip/apb_configurator/tb
    tb_dir = os.path.join(tests_dir, '..', 'tb')
    
    # Navigate to simulation output directory
    # Expected: ip/apb_configurator/sim
    base_sim_dir = os.path.join(tests_dir, '..', 'sim')
    
    # --- 2. Set environment variable for test logic ---
    # The cocotb test reads this to configure clock periods
    os.environ["CLOCK_SCENARIO"] = scenario

    # --- 3. Run Verilog simulation with cocotb ---
    run(
        # Specify Verilog source files to compile
        # Include both the DUT and the CDC testbench wrapper
        verilog_sources=[
            os.path.join(hdl_dir, "apb_configurator.v"),  # Main design
            os.path.join(tb_dir, "apb_cdc_wrapper.v")      # CDC testbench wrapper
        ],
        
        # Top-level module for simulation (the testbench wrapper)
        toplevel="apb_cdc_wrapper",
        
        # Python module containing cocotb tests
        module="test_cdc_cocotb",
        
        # Add tests directory to Python search path
        # This ensures the test_cdc_cocotb module can be imported
        python_search=[tests_dir],
        
        # Set Verilog parameters for this test configuration
        # These override the default parameter values in the HDL
        parameters={
            "APB_DATA_WIDTH": hw_config["width"],  # Data bus width (32 or 64)
            "NUM_REGS": hw_config["regs"],         # Number of registers (16 or 8)
            "APB_ADDR_WIDTH": "32"                 # Address bus width (fixed)
        },
        
        # Use separate build directory for each configuration
        # This prevents conflicts when running tests in parallel
        # Format: sim/build_w32_FAST_APB, sim/build_w64_SLOW_APB, etc.
        sim_build=os.path.join(base_sim_dir, f"build_w{hw_config['width']}_{scenario}"),
        
        # Use Icarus Verilog simulator
        sim="icarus"
    )