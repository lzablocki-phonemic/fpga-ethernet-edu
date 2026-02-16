`resetall
`timescale 1ns / 1ps
`default_nettype none

/*
 * FIR Filter with APB Configuration
 *
 * Wraps the pure fir_filter with an APB slave interface.
 * Follows the same APB pattern as mac_udp_1G_apbConfig.

 
 */
module fir_filter_apbConfig #
(
    parameter DATA_WIDTH  = 16,
    parameter COEFF_WIDTH = 16,
    parameter NUM_TAPS    = 64
)
(
    /*
     * Clock / synchronous reset
     */
    input  wire                        clk,
    input  wire                        rst,

    /*
     * APB slave interface (active-high rst maps to active-low presetn)
     */
    input  wire [31:0]                 paddr,
    input  wire                        psel,
    input  wire                        penable,
    input  wire                        pwrite,
    input  wire [31:0]                 pwdata,
    output wire [31:0]                 prdata,
    output wire                        pready,
    output wire                        pslverr,

    /*
     * AXI-Stream input
     */
    input  wire [DATA_WIDTH-1:0]       s_axis_tdata,
    input  wire                        s_axis_tvalid,
    output wire                        s_axis_tready,
    input  wire                        s_axis_tlast,
    input  wire [0:0]                  s_axis_tuser,

    /*
     * AXI-Stream output
     */
    output wire [DATA_WIDTH-1:0]       m_axis_tdata,
    output wire                        m_axis_tvalid,
    output wire                        m_axis_tlast,
    output wire [0:0]                  m_axis_tuser,
    input  wire                        m_axis_tready
);

// =========================================================================
// APB Configuration
// =========================================================================
localparam NUM_REGS = 3;

/*
 * APB Register Map (32-bit, word-aligned):
 *   0x00 CTRL        - bit0: bypass
 *                      (bit1+ reserved - CTRL shared convention, only bit0 used)
 *   0x04 COEFF_ADDR  - coefficient index to write [$clog2(NUM_TAPS)-1:0]
 *   0x08 COEFF_DATA  - coefficient value [COEFF_WIDTH-1:0]
 *                      (writing this register triggers a one-cycle coeff_we pulse)
 */

// APB register index definitions (word address = index * 4)
localparam APB_IDX_CTRL       = 0;  // 0x00 - bit0: bypass
localparam APB_IDX_COEFF_ADDR = 1;  // 0x04 - coefficient address
localparam APB_IDX_COEFF_DATA = 2;  // 0x08 - coefficient data (write triggers coeff_we)

wire [31:0] config_regs  [NUM_REGS-1:0];
wire        config_ready [NUM_REGS-1:0];
wire        presetn = ~rst;

apb_configurator #(
    .APB_DATA_WIDTH(32),
    .APB_ADDR_WIDTH(32),
    .NUM_REGS(NUM_REGS),
    .BASE_ADDR(32'h0000_0000)
) apb_cfg (
    .pclk(clk),
    .presetn(presetn),
    .paddr(paddr),
    .psel(psel),
    .penable(penable),
    .pwrite(pwrite),
    .pwdata(pwdata),
    .prdata(prdata),
    .pready(pready),
    .pslverr(pslverr),
    .config_regs_out(config_regs),
    .config_ready_out(config_ready)
);

// Extract configuration signals
// Note: only bit0 of CTRL is used (same convention as eth APB)
wire        bypass     = config_regs[APB_IDX_CTRL][0];

wire [$clog2(NUM_TAPS)-1:0] coeff_addr_cfg = config_regs[APB_IDX_COEFF_ADDR][$clog2(NUM_TAPS)-1:0];
wire [COEFF_WIDTH-1:0]      coeff_data_cfg = config_regs[APB_IDX_COEFF_DATA][COEFF_WIDTH-1:0];

// =========================================================================
// Coefficient write pulse generation
// coeff_we pulses for exactly one clock cycle on each APB write to COEFF_DATA.
// Detected by snooping the APB access phase directly (psel & penable & pwrite).
// =========================================================================
localparam COEFF_DATA_BYTE_ADDR = APB_IDX_COEFF_DATA * 4;

// One-cycle pulse: active during the APB ACCESS phase targeting COEFF_DATA
wire coeff_we = psel & penable & pwrite &
                (paddr == COEFF_DATA_BYTE_ADDR);

// =========================================================================
// FIR Filter core
// =========================================================================
fir_filter #(
    .DATA_WIDTH (DATA_WIDTH),
    .COEFF_WIDTH(COEFF_WIDTH),
    .NUM_TAPS   (NUM_TAPS)
) fir_core (
    .clk          (clk),
    .rst          (rst),

    // APB-driven control
    .bypass       (bypass),
    .coeff_we     (coeff_we),
    .coeff_addr   (coeff_addr_cfg),
    .coeff_data   (coeff_data_cfg),

    // AXI-Stream pass-through
    .s_axis_tdata (s_axis_tdata),
    .s_axis_tvalid(s_axis_tvalid),
    .s_axis_tready(s_axis_tready),
    .s_axis_tlast (s_axis_tlast),
    .s_axis_tuser (s_axis_tuser),

    .m_axis_tdata (m_axis_tdata),
    .m_axis_tvalid(m_axis_tvalid),
    .m_axis_tlast (m_axis_tlast),
    .m_axis_tuser (m_axis_tuser),
    .m_axis_tready(m_axis_tready)
);

endmodule

`resetall
