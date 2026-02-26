`resetall
`timescale 1ns / 1ps
`default_nettype none

/*
 * FPGA Core 10G — Two UDP 10G nodes + FIR filter on Node A
 *
 * PHY-less design: Node A and Node B are directly connected via XGMII:
 *   Node A TX → Node B RX
 *   Node B TX → Node A RX
 *
 * Node A includes an additional FIR filter (fir_filter_apbConfig) with its
 * own APB slave bus. The FIR AXI-Stream I/O is exposed at the top level.
 */
module fpga_core_10g #
(
    parameter TARGET = "GENERIC",
    parameter B2B_EN = 0           // 0=external XGMII, 1=internal cross-connect
)
(
    /*
     * Clock: 156.25 MHz (10G Standard)
     */
    input  wire        clk,
    input  wire        rst,
    input  wire        trigger_b,
    /*
     * Node A — XGMII (connected to Node B + External Injection)
     */
    input  wire        xgmii_a_rx_clk,
    input  wire [63:0] xgmii_a_rxd,
    input  wire [7:0]  xgmii_a_rxc,
    output wire        xgmii_a_tx_clk,
    output wire [63:0] xgmii_a_txd,
    output wire [7:0]  xgmii_a_txc,

    /*
     * Node B — XGMII (connected to Node A + External Injection)
     */
    input  wire        xgmii_b_rx_clk,
    input  wire [63:0] xgmii_b_rxd, 
    input  wire [7:0]  xgmii_b_rxc,
    output wire        xgmii_b_tx_clk,
    output wire [63:0] xgmii_b_txd,
    output wire [7:0]  xgmii_b_txc,

    /*
     * Node A — Ethernet APB slave
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
     * Node A — FIR APB slave
     */
    input  wire [31:0] paddr_fir_a,
    input  wire        psel_fir_a,
    input  wire        penable_fir_a,
    input  wire        pwrite_fir_a,
    input  wire [31:0] pwdata_fir_a,
    output wire [31:0] prdata_fir_a,
    output wire        pready_fir_a,
    output wire        pslverr_fir_a,

    /*
     * Node B — Ethernet APB slave
     */
    input  wire [31:0] paddr_b,
    input  wire        psel_b,
    input  wire        penable_b,
    input  wire        pwrite_b,
    input  wire [31:0] pwdata_b,
    output wire [31:0] prdata_b,
    output wire        pready_b,
    output wire        pslverr_b
);

// =========================================================================
// Internal XGMII wiring
// =========================================================================
wire        node_a_xgmii_tx_clk;
wire [63:0] node_a_xgmii_txd;
wire [7:0]  node_a_xgmii_txc;

wire        node_b_xgmii_tx_clk;
wire [63:0] node_b_xgmii_txd;
wire [7:0]  node_b_xgmii_txc;

// =========================================================================
// Internal UDP Payload Extensions (for FIR filtering)
// =========================================================================
wire [63:0] node_a_udp_rx_ext_tdata;
wire [7:0]  node_a_udp_rx_ext_tkeep;
wire        node_a_udp_rx_ext_tvalid;
wire        node_a_udp_rx_ext_tready;
wire        node_a_udp_rx_ext_tlast;
wire        node_a_udp_rx_ext_tuser;

wire [63:0] node_a_udp_tx_ext_tdata;
wire [7:0]  node_a_udp_tx_ext_tkeep;
wire        node_a_udp_tx_ext_tvalid;
wire        node_a_udp_tx_ext_tready;
wire        node_a_udp_tx_ext_tlast;
wire        node_a_udp_tx_ext_tuser;


wire [63:0] node_b_udp_rx_ext_tdata;
wire [7:0]  node_b_udp_rx_ext_tkeep;
wire        node_b_udp_rx_ext_tvalid;
wire        node_b_udp_rx_ext_tready;
wire        node_b_udp_rx_ext_tlast;
wire        node_b_udp_rx_ext_tuser;

wire [63:0] node_b_udp_tx_ext_tdata;
wire [7:0]  node_b_udp_tx_ext_tkeep;
wire        node_b_udp_tx_ext_tvalid;
wire        node_b_udp_tx_ext_tready;
wire        node_b_udp_tx_ext_tlast;
wire        node_b_udp_tx_ext_tuser;


// =========================================================================
// Node A — RX Source Selection
// b2b_en=1: Node A RX ← Node B TX (internal cross-connect, clk domain)
// b2b_en=0: Node A RX ← External XGMII (xgmii_a_rx_clk domain)
// =========================================================================
wire        node_a_rx_clk = B2B_EN ? clk              : xgmii_a_rx_clk;
wire [63:0] node_a_rxd    = B2B_EN ? node_b_xgmii_txd : xgmii_a_rxd;
wire [7:0]  node_a_rxc    = B2B_EN ? node_b_xgmii_txc : xgmii_a_rxc;

// =========================================================================
// Node A — UDP 10G MAC with Ethernet APB Configuration
// =========================================================================
mac_udp_10G_apbConfig #(
    .TARGET("A")
) node_a (
    .clk(clk),
    .rst(rst),

    .xgmii_rx_clk(node_a_rx_clk),
    .xgmii_rxd   (node_a_rxd),
    .xgmii_rxc   (node_a_rxc),
    .xgmii_tx_clk(node_a_xgmii_tx_clk),
    .xgmii_txd   (node_a_xgmii_txd),
    .xgmii_txc   (node_a_xgmii_txc),

    .paddr   (paddr_a),
    .psel    (psel_a),
    .penable (penable_a),
    .pwrite  (pwrite_a),
    .pwdata  (pwdata_a),
    .prdata  (prdata_a),
    .pready  (pready_a),
    .pslverr (pslverr_a),

    .udp_rx_ext_tdata (node_a_udp_rx_ext_tdata),
    .udp_rx_ext_tkeep (node_a_udp_rx_ext_tkeep),
    .udp_rx_ext_tvalid(node_a_udp_rx_ext_tvalid),
    .udp_rx_ext_tready(node_a_udp_rx_ext_tready),
    .udp_rx_ext_tlast (node_a_udp_rx_ext_tlast),
    .udp_rx_ext_tuser (node_a_udp_rx_ext_tuser),

    .udp_tx_ext_tdata (node_a_udp_tx_ext_tdata),
    .udp_tx_ext_tkeep (node_a_udp_tx_ext_tkeep),
    .udp_tx_ext_tvalid(node_a_udp_tx_ext_tvalid),
    .udp_tx_ext_tready(node_a_udp_tx_ext_tready),
    .udp_tx_ext_tlast (node_a_udp_tx_ext_tlast),
    .udp_tx_ext_tuser (node_a_udp_tx_ext_tuser)
);

// Node A TX → external XGMII port (monitoring)
assign xgmii_a_tx_clk= node_a_xgmii_tx_clk;
assign xgmii_a_txd   = node_a_xgmii_txd;
assign xgmii_a_txc   = node_a_xgmii_txc;

// =========================================================================
// Node A — FIR Filter with APB Configuration
// DATA_WIDTH=64 to match 10G pipeline width
// =========================================================================
fir_filter_apbConfig #(
    .DATA_WIDTH (64),
    .COEFF_WIDTH(16),
    .NUM_TAPS   (64)
) fir_a (
    .clk  (clk),
    .rst  (rst),

    .paddr   (paddr_fir_a),
    .psel    (psel_fir_a),
    .penable (penable_fir_a),
    .pwrite  (pwrite_fir_a),
    .pwdata  (pwdata_fir_a),
    .prdata  (prdata_fir_a),
    .pready  (pready_fir_a),
    .pslverr (pslverr_fir_a),

    .s_axis_tdata  (node_a_udp_rx_ext_tdata),
    // NOT implemented for now
    // .s_axis_tkeep  (node_a_udp_rx_ext_tkeep), 
    .s_axis_tvalid (node_a_udp_rx_ext_tvalid),
    .s_axis_tready (node_a_udp_rx_ext_tready),
    .s_axis_tlast  (node_a_udp_rx_ext_tlast),
    .s_axis_tuser  (node_a_udp_rx_ext_tuser),

    .m_axis_tdata  (node_a_udp_tx_ext_tdata),
    // NOT implemented for now
    // .m_axis_tkeep  (node_a_udp_tx_ext_tkeep),
    .m_axis_tvalid (node_a_udp_tx_ext_tvalid),
    .m_axis_tready (node_a_udp_tx_ext_tready),
    .m_axis_tlast  (node_a_udp_tx_ext_tlast),
    .m_axis_tuser  (node_a_udp_tx_ext_tuser)
);

assign node_a_udp_tx_ext_tkeep = 8'hFF;


// =========================================================================
// Node B — RX Source Selection
// b2b_en=1: Node B RX ← Node A TX (internal cross-connect, clk domain)
// b2b_en=0: Node B RX ← External XGMII (xgmii_b_rx_clk domain)
// =========================================================================
wire        node_b_rx_clk = B2B_EN ? clk              : xgmii_b_rx_clk;
wire [63:0] node_b_rxd    = B2B_EN ? node_a_xgmii_txd : xgmii_b_rxd;
wire [7:0]  node_b_rxc    = B2B_EN ? node_a_xgmii_txc : xgmii_b_rxc;

// =========================================================================
// Node B — UDP 10G MAC with Ethernet APB Configuration
// =========================================================================
mac_udp_10G_apbConfig #(
    .TARGET("B")
) node_b (
    .clk(clk),
    .rst(rst),

    .xgmii_rx_clk(node_b_rx_clk),
    .xgmii_rxd   (node_b_rxd),
    .xgmii_rxc   (node_b_rxc),
    .xgmii_tx_clk(node_b_xgmii_tx_clk),
    .xgmii_txd   (node_b_xgmii_txd),
    .xgmii_txc   (node_b_xgmii_txc),

    .paddr   (paddr_b),
    .psel    (psel_b),
    .penable (penable_b),
    .pwrite  (pwrite_b),
    .pwdata  (pwdata_b),
    .prdata  (prdata_b),
    .pready  (pready_b),
    .pslverr (pslverr_b),

    .udp_rx_ext_tdata (node_b_udp_rx_ext_tdata),
    .udp_rx_ext_tkeep (node_b_udp_rx_ext_tkeep),
    .udp_rx_ext_tvalid(node_b_udp_rx_ext_tvalid),
    .udp_rx_ext_tready(node_b_udp_rx_ext_tready),
    .udp_rx_ext_tlast (node_b_udp_rx_ext_tlast),
    .udp_rx_ext_tuser (node_b_udp_rx_ext_tuser),

    .udp_tx_ext_tdata (node_b_udp_tx_ext_tdata),
    .udp_tx_ext_tkeep (node_b_udp_tx_ext_tkeep),
    .udp_tx_ext_tvalid(node_b_udp_tx_ext_tvalid),
    .udp_tx_ext_tready(node_b_udp_tx_ext_tready),
    .udp_tx_ext_tlast (node_b_udp_tx_ext_tlast),
    .udp_tx_ext_tuser (node_b_udp_tx_ext_tuser)
);

// Node B TX → external XGMII port (monitoring)
assign xgmii_b_tx_clk= node_b_xgmii_tx_clk;
assign xgmii_b_txd   = node_b_xgmii_txd;
assign xgmii_b_txc   = node_b_xgmii_txc;


udp_axi_data_gen #(
    .DATA_WIDTH (64)
) node_b_udp_gen (
    .clk  (clk),
    .rst  (rst),
    .trigger(trigger_b),
    .s_axis_tdata  (node_b_udp_rx_ext_tdata),
    .s_axis_tvalid (node_b_udp_rx_ext_tvalid),
    .s_axis_tready (node_b_udp_rx_ext_tready),
    .s_axis_tlast  (node_b_udp_rx_ext_tlast),
    .s_axis_tuser  (node_b_udp_rx_ext_tuser),

    .m_axis_tdata  (node_b_udp_tx_ext_tdata),
    .m_axis_tvalid (node_b_udp_tx_ext_tvalid),
    .m_axis_tready (node_b_udp_tx_ext_tready),
    .m_axis_tlast  (node_b_udp_tx_ext_tlast),
    .m_axis_tuser  (node_b_udp_tx_ext_tuser)
);

assign node_b_udp_tx_ext_tkeep = 8'hFF;

endmodule

`resetall
