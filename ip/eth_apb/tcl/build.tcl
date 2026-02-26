# ==============================================================================
# TCL Build Script for fpga_core
#
# Compiles all Verilog sources for the fpga_core design using Icarus Verilog.
# Also supports running cocotb simulation.
#
# Usage:
#   tclsh build.tcl compile     - Compile only (syntax check)
#   tclsh build.tcl simulate    - Run cocotb simulation
#   tclsh build.tcl all         - Compile + simulate
#   tclsh build.tcl clean       - Clean build artifacts
# ==============================================================================

# Project root (relative to ip/eth_apb/tcl/)
set proj_root [file normalize [file join [file dirname [info script]] "../../.."]]
# Source directories
set rtl_dir      "$proj_root/ip/eth_apb/hdl"
set ip_apb_dir   "$proj_root/ip/eth_apb/hdl"
set ip_cfg_dir   "$proj_root/ip/apb_configurator/hdl"
set eth_rtl_dir  "$proj_root/external/verilog-ethernet/rtl"
set axis_rtl_dir "$proj_root/external/verilog-ethernet/lib/axis/rtl"

# Build directory
set build_dir    "$proj_root/ip/eth_apb/sim"
set tb_dir       "$proj_root/ip/eth_apb/tests"

# ==============================================================================
# Source file list
# ==============================================================================
set verilog_sources [list \
    "$rtl_dir/fpga_core.v" \
    "$ip_apb_dir/mac_udp_1G_apbConfig.v" \
    "$ip_cfg_dir/apb_configurator.v" \
    "$eth_rtl_dir/eth_mac_1g_rgmii_fifo.v" \
    "$eth_rtl_dir/eth_mac_1g_rgmii.v" \
    "$eth_rtl_dir/iddr.v" \
    "$eth_rtl_dir/oddr.v" \
    "$eth_rtl_dir/ssio_ddr_in.v" \
    "$eth_rtl_dir/rgmii_phy_if.v" \
    "$eth_rtl_dir/eth_mac_1g.v" \
    "$eth_rtl_dir/axis_gmii_rx.v" \
    "$eth_rtl_dir/axis_gmii_tx.v" \
    "$eth_rtl_dir/lfsr.v" \
    "$eth_rtl_dir/eth_axis_rx.v" \
    "$eth_rtl_dir/eth_axis_tx.v" \
    "$eth_rtl_dir/udp_complete.v" \
    "$eth_rtl_dir/udp_checksum_gen.v" \
    "$eth_rtl_dir/udp.v" \
    "$eth_rtl_dir/udp_ip_rx.v" \
    "$eth_rtl_dir/udp_ip_tx.v" \
    "$eth_rtl_dir/ip_complete.v" \
    "$eth_rtl_dir/ip.v" \
    "$eth_rtl_dir/ip_eth_rx.v" \
    "$eth_rtl_dir/ip_eth_tx.v" \
    "$eth_rtl_dir/ip_arb_mux.v" \
    "$eth_rtl_dir/arp.v" \
    "$eth_rtl_dir/arp_cache.v" \
    "$eth_rtl_dir/arp_eth_rx.v" \
    "$eth_rtl_dir/arp_eth_tx.v" \
    "$eth_rtl_dir/eth_arb_mux.v" \
    "$axis_rtl_dir/arbiter.v" \
    "$axis_rtl_dir/priority_encoder.v" \
    "$axis_rtl_dir/axis_fifo.v" \
    "$axis_rtl_dir/axis_async_fifo.v" \
    "$axis_rtl_dir/axis_async_fifo_adapter.v" \
]

# ==============================================================================
# Procedures
# ==============================================================================

proc ensure_dir {dir} {
    if {![file exists $dir]} {
        file mkdir $dir
    }
}

proc do_compile {} {
    global verilog_sources build_dir

    ensure_dir $build_dir

    puts "============================================"
    puts "  Compiling fpga_core design (Icarus Verilog)"
    puts "============================================"

    # Check that all source files exist
    foreach src $verilog_sources {
        if {![file exists $src]} {
            puts "ERROR: Source file not found: $src"
            return 1
        }
    }

    # Build iverilog command
    set cmd "iverilog -g2012 -o $build_dir/fpga_core.vvp -s fpga_core"
    foreach src $verilog_sources {
        append cmd " $src"
    }

    puts "Running: $cmd"
    set result [catch {exec {*}[split $cmd " "]} output]

    if {$result} {
        puts "COMPILE FAILED:"
        puts $output
        return 1
    }

    puts "Compile successful: $build_dir/fpga_core.vvp"
    puts ""

    # Also list all source files
    puts "Source files compiled:"
    foreach src $verilog_sources {
        puts "  [file tail $src]"
    }

    return 0
}

proc do_simulate {} {
    global tb_dir

    puts "============================================"
    puts "  Running cocotb simulation"
    puts "============================================"

    set cmd "make -C $tb_dir SIM=icarus"
    puts "Running: $cmd"
    set result [catch {exec make -C $tb_dir SIM=icarus 2>@1} output]
    puts $output

    if {$result} {
        puts "\nSIMULATION FAILED"
        return 1
    }

    puts "\nSimulation completed successfully"
    return 0
}

proc do_clean {} {
    global build_dir tb_dir

    puts "Cleaning build artifacts..."

    catch {file delete -force $build_dir}
    catch {exec make -C $tb_dir clean 2>@1}

    puts "Clean done."
    return 0
}

proc print_usage {} {
    puts "Usage: tclsh build.tcl \[command\]"
    puts ""
    puts "Commands:"
    puts "  compile   - Compile Verilog sources (syntax check)"
    puts "  simulate  - Run cocotb simulation"
    puts "  all       - Compile + simulate"
    puts "  clean     - Remove build artifacts"
    puts "  help      - Show this message"
}

# ==============================================================================
# Main
# ==============================================================================
if {$argc == 0} {
    print_usage
    exit 0
}

set command [lindex $argv 0]

switch $command {
    "compile" {
        exit [do_compile]
    }
    "simulate" {
        exit [do_simulate]
    }
    "all" {
        set rc [do_compile]
        if {$rc != 0} { exit $rc }
        exit [do_simulate]
    }
    "clean" {
        exit [do_clean]
    }
    "help" {
        print_usage
        exit 0
    }
    default {
        puts "Unknown command: $command"
        print_usage
        exit 1
    }
}
