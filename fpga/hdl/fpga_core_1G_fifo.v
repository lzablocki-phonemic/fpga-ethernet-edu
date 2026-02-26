`resetall
`timescale 1ns / 1ps
`default_nettype none

/*
 * FPGA Core 1G FIFO Top Level
 *
 * Instantiates 2 x mac_udp_1G_apbConfig connected back-to-back via GMII.
 * Instantiates 1 x fir_filter_apbConfig (8-bit) on Node A intercepting RX payload.
 */

module fpga_core_1G_fifo #
(
    parameter TARGET = "GENERIC",
    parameter B2B_EN = 0           // 0=external GMII, 1=internal cross-connect
)
(
    /*
     * Clock: 125MHz
     * Synchronous reset
     */
    input  wire        clk,
    input  wire        rst,

    /*
     * External GMII ports for testing
     * Node A
     */
    input  wire        gmii_a_rx_clk,
    input  wire [7:0]  gmii_a_rxd,
    input  wire        gmii_a_rx_dv,
    input  wire        gmii_a_rx_er,
    output wire        gmii_a_tx_clk,
    output wire [7:0]  gmii_a_txd,
    output wire        gmii_a_tx_en,
    output wire        gmii_a_tx_er,

    /*
     * External GMII ports for testing
     * Node B
     */
    input  wire        gmii_b_rx_clk,
    input  wire [7:0]  gmii_b_rxd,
    input  wire        gmii_b_rx_dv,
    input  wire        gmii_b_rx_er,
    output wire        gmii_b_tx_clk,
    output wire [7:0]  gmii_b_txd,
    output wire        gmii_b_tx_en,
    output wire        gmii_b_tx_er,

    /*
     * APB inputs for Node A MAC Configuration
     */
    input  wire [31:0] paddr_a,
    input  wire        psel_a,
    input  wire        penable_a,
    input  wire        pwrite_a,
    input  wire [31:0] pwdata_a,
    output wire [31:0] prdata_a,
    output wire        pready_a,
    output wire        pslverr_a,

    /*
     * APB inputs for Node B MAC Configuration
     */
    input  wire [31:0] paddr_b,
    input  wire        psel_b,
    input  wire        penable_b,
    input  wire        pwrite_b,
    input  wire [31:0] pwdata_b,
    output wire [31:0] prdata_b,
    output wire        pready_b,
    output wire        pslverr_b,

    /*
     * APB inputs for FIR Filter Configuration (attached to Node A)
     */
    input  wire [31:0] paddr_fir_a,
    input  wire        psel_fir_a,
    input  wire        penable_fir_a,
    input  wire        pwrite_fir_a,
    input  wire [31:0] pwdata_fir_a,
    output wire [31:0] prdata_fir_a,
    output wire        pready_fir_a,
    output wire        pslverr_fir_a
);

// =========================================================================
// Internal GMII cross-connect between Node A and Node B
// =========================================================================
wire        mac_a_tx_clk_int;
wire [7:0]  mac_a_txd_int;
wire        mac_a_tx_en_int;
wire        mac_a_tx_er_int;

wire        mac_b_tx_clk_int;
wire [7:0]  mac_b_txd_int;
wire        mac_b_tx_en_int;
wire        mac_b_tx_er_int;

// =========================================================================
// Node A — RX Source Selection
// B2B_EN=1: Node A RX ← Node B TX (internal cross-connect, clk domain)
// B2B_EN=0: Node A RX ← External GMII
// =========================================================================
wire        mac_a_rx_clk_in = B2B_EN ? clk              : gmii_a_rx_clk;
wire [7:0]  mac_a_rxd_in    = B2B_EN ? mac_b_txd_int    : gmii_a_rxd;
wire        mac_a_rx_dv_in  = B2B_EN ? mac_b_tx_en_int  : gmii_a_rx_dv;
wire        mac_a_rx_er_in  = B2B_EN ? mac_b_tx_er_int  : gmii_a_rx_er;

// =========================================================================
// Node B — RX Source Selection
// B2B_EN=1: Node B RX ← Node A TX (internal cross-connect, clk domain)
// B2B_EN=0: Node B RX ← External GMII
// =========================================================================
wire        mac_b_rx_clk_in = B2B_EN ? clk              : gmii_b_rx_clk;
wire [7:0]  mac_b_rxd_in    = B2B_EN ? mac_a_txd_int    : gmii_b_rxd;
wire        mac_b_rx_dv_in  = B2B_EN ? mac_a_tx_en_int  : gmii_b_rx_dv;
wire        mac_b_rx_er_in  = B2B_EN ? mac_a_tx_er_int  : gmii_b_rx_er;

// Connect output to external ports unconditionally for monitoring/capture
assign gmii_a_tx_clk = mac_a_tx_clk_int;
assign gmii_a_txd    = mac_a_txd_int;
assign gmii_a_tx_en  = mac_a_tx_en_int;
assign gmii_a_tx_er  = mac_a_tx_er_int;

assign gmii_b_tx_clk = mac_b_tx_clk_int;
assign gmii_b_txd    = mac_b_txd_int;
assign gmii_b_tx_en  = mac_b_tx_en_int;
assign gmii_b_tx_er  = mac_b_tx_er_int;

// =========================================================================
// Node A: mac_udp_1G_apbConfig + FIR Filter
// =========================================================================

wire [7:0] node_a_rx_ext_tdata;
wire       node_a_rx_ext_tvalid;
wire       node_a_rx_ext_tready;
wire       node_a_rx_ext_tlast;
wire       node_a_rx_ext_tuser;

wire [7:0] node_a_tx_ext_tdata;
wire       node_a_tx_ext_tvalid;
wire       node_a_tx_ext_tready;
wire       node_a_tx_ext_tlast;
wire       node_a_tx_ext_tuser;

mac_udp_1G_apbConfig #(
    .TARGET("A")
) node_a (
    .clk(clk),
    .rst(rst),
    
    .gmii_rx_clk(mac_a_rx_clk_in),
    .gmii_rxd(mac_a_rxd_in),
    .gmii_rx_dv(mac_a_rx_dv_in),
    .gmii_rx_er(mac_a_rx_er_in),
    
    .gmii_tx_clk(mac_a_tx_clk_int),
    .gmii_txd(mac_a_txd_int),
    .gmii_tx_en(mac_a_tx_en_int),
    .gmii_tx_er(mac_a_tx_er_int),
    
    .udp_rx_ext_tdata(node_a_rx_ext_tdata),
    .udp_rx_ext_tvalid(node_a_rx_ext_tvalid),
    .udp_rx_ext_tready(node_a_rx_ext_tready),
    .udp_rx_ext_tlast(node_a_rx_ext_tlast),
    .udp_rx_ext_tuser(node_a_rx_ext_tuser),
    
    .udp_tx_ext_tdata(node_a_tx_ext_tdata),
    .udp_tx_ext_tvalid(node_a_tx_ext_tvalid),
    .udp_tx_ext_tready(node_a_tx_ext_tready),
    .udp_tx_ext_tlast(node_a_tx_ext_tlast),
    .udp_tx_ext_tuser(node_a_tx_ext_tuser),
    
    .paddr(paddr_a),
    .psel(psel_a),
    .penable(penable_a),
    .pwrite(pwrite_a),
    .pwdata(pwdata_a),
    .prdata(prdata_a),
    .pready(pready_a),
    .pslverr(pslverr_a)
);

// FIR Filter Instance (8-bit data)
fir_filter_apbConfig #(
    .DATA_WIDTH(8)
) fir_a (
    .clk(clk),
    .rst(rst),
    
    .s_axis_tdata(node_a_rx_ext_tdata),
    .s_axis_tvalid(node_a_rx_ext_tvalid),
    .s_axis_tready(node_a_rx_ext_tready),
    .s_axis_tlast(node_a_rx_ext_tlast),
    .s_axis_tuser(node_a_rx_ext_tuser),
    
    .m_axis_tdata(node_a_tx_ext_tdata),
    .m_axis_tvalid(node_a_tx_ext_tvalid),
    .m_axis_tready(node_a_tx_ext_tready),
    .m_axis_tlast(node_a_tx_ext_tlast),
    .m_axis_tuser(node_a_tx_ext_tuser),
    
    .paddr(paddr_fir_a),
    .psel(psel_fir_a),
    .penable(penable_fir_a),
    .pwrite(pwrite_fir_a),
    .pwdata(pwdata_fir_a),
    .prdata(prdata_fir_a),
    .pready(pready_fir_a),
    .pslverr(pslverr_fir_a)
);

// =========================================================================
// Node B: mac_udp_1G_apbConfig (No FIR, dummy loopback)
// =========================================================================

wire [7:0] node_b_rx_ext_tdata;
wire       node_b_rx_ext_tvalid;
wire       node_b_rx_ext_tready;
wire       node_b_rx_ext_tlast;
wire       node_b_rx_ext_tuser;

mac_udp_1G_apbConfig #(
    .TARGET("B")
) node_b (
    .clk(clk),
    .rst(rst),
    
    .gmii_rx_clk(mac_b_rx_clk_in),
    .gmii_rxd(mac_b_rxd_in),
    .gmii_rx_dv(mac_b_rx_dv_in),
    .gmii_rx_er(mac_b_rx_er_in),
    
    .gmii_tx_clk(mac_b_tx_clk_int),
    .gmii_txd(mac_b_txd_int),
    .gmii_tx_en(mac_b_tx_en_int),
    .gmii_tx_er(mac_b_tx_er_int),
    
    .udp_rx_ext_tdata(node_b_rx_ext_tdata),
    .udp_rx_ext_tvalid(node_b_rx_ext_tvalid),
    .udp_rx_ext_tready(node_b_rx_ext_tready),
    .udp_rx_ext_tlast(node_b_rx_ext_tlast),
    .udp_rx_ext_tuser(node_b_rx_ext_tuser),
    
    // Hard loopback the external interface if it tries to send out
    .udp_tx_ext_tdata(node_b_rx_ext_tdata),
    .udp_tx_ext_tvalid(node_b_rx_ext_tvalid),
    .udp_tx_ext_tready(node_b_rx_ext_tready),
    .udp_tx_ext_tlast(node_b_rx_ext_tlast),
    .udp_tx_ext_tuser(node_b_rx_ext_tuser),
    
    .paddr(paddr_b),
    .psel(psel_b),
    .penable(penable_b),
    .pwrite(pwrite_b),
    .pwdata(pwdata_b),
    .prdata(prdata_b),
    .pready(pready_b),
    .pslverr(pslverr_b)
);

endmodule
`resetall
