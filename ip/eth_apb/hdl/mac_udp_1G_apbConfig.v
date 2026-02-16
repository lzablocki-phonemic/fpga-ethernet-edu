`resetall
`timescale 1ns / 1ps
`default_nettype none

/*
 * UDP 1G MAC with APB Configuration
 *
 * Single Ethernet node: GMII MAC (PHY-less using eth_mac_1g_fifo) + UDP/IP stack + APB-configurable parameters.
 * Supports loopback mode with FIR filter external connectivity.
 */

module mac_udp_1G_apbConfig #
(
    parameter TARGET = "GENERIC"
)
(
    /*
     * Clock: 125MHz
     * Synchronous reset
     */
    input  wire        clk,
    input  wire        rst,
    
    /*
     * Ethernet: GMII
     */
    input  wire        gmii_rx_clk,
    input  wire [7:0]  gmii_rxd,
    input  wire        gmii_rx_dv,
    input  wire        gmii_rx_er,
    output wire        gmii_tx_clk,
    output wire [7:0]  gmii_txd,
    output wire        gmii_tx_en,
    output wire        gmii_tx_er,

    /*
     * External UDP Payload RX (from MAC to FIR)
     */
    output wire [7:0]  udp_rx_ext_tdata,
    output wire        udp_rx_ext_tvalid,
    input  wire        udp_rx_ext_tready,
    output wire        udp_rx_ext_tlast,
    output wire        udp_rx_ext_tuser,

    /*
     * External UDP Payload TX (from FIR to MAC)
     */
    input  wire [7:0]  udp_tx_ext_tdata,
    input  wire        udp_tx_ext_tvalid,
    output wire        udp_tx_ext_tready,
    input  wire        udp_tx_ext_tlast,
    input  wire        udp_tx_ext_tuser,

    /*
     * APB slave interface
     */
    input  wire [31:0] paddr,
    input  wire        psel,
    input  wire        penable,
    input  wire        pwrite,
    input  wire [31:0] pwdata,
    output wire [31:0] prdata,
    output wire        pready,
    output wire        pslverr
);

// =========================================================================
// APB Configuration
// =========================================================================
localparam NUM_REGS = 12;

localparam APB_IDX_CTRL        = 0;
localparam APB_IDX_STATUS      = 1;
localparam APB_IDX_SRC_MAC_L   = 2;
localparam APB_IDX_SRC_MAC_H   = 3;
localparam APB_IDX_DST_MAC_L   = 4;
localparam APB_IDX_DST_MAC_H   = 5;
localparam APB_IDX_SRC_IP      = 6;
localparam APB_IDX_DST_IP      = 7;
localparam APB_IDX_SRC_PORT    = 8;
localparam APB_IDX_DST_PORT    = 9;
localparam APB_IDX_GATEWAY_IP  = 10;
localparam APB_IDX_SUBNET_MASK = 11;

wire [31:0] config_regs [NUM_REGS-1:0];
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

wire        loopback_en     = config_regs[APB_IDX_CTRL][0];
wire        clear_arp       = config_regs[APB_IDX_CTRL][2];

wire [47:0] local_mac       = {config_regs[APB_IDX_SRC_MAC_H][15:0], config_regs[APB_IDX_SRC_MAC_L]};
wire [31:0] local_ip        = config_regs[APB_IDX_SRC_IP];
wire [31:0] gateway_ip      = config_regs[APB_IDX_GATEWAY_IP];
wire [31:0] subnet_mask     = config_regs[APB_IDX_SUBNET_MASK];

wire [15:0] src_port_cfg    = config_regs[APB_IDX_SRC_PORT][15:0];
wire [15:0] dst_port_cfg    = config_regs[APB_IDX_DST_PORT][15:0];

// =========================================================================
// Internal AXI-Stream Wires
// =========================================================================

wire [7:0] rx_axis_tdata;
wire       rx_axis_tvalid;
wire       rx_axis_tready;
wire       rx_axis_tlast;
wire       rx_axis_tuser;

wire [7:0] tx_axis_tdata;
wire       tx_axis_tvalid;
wire       tx_axis_tready;
wire       tx_axis_tlast;
wire       tx_axis_tuser;

wire rx_eth_hdr_ready;
wire rx_eth_hdr_valid;
wire [47:0] rx_eth_dest_mac;
wire [47:0] rx_eth_src_mac;
wire [15:0] rx_eth_type;
wire [7:0] rx_eth_payload_axis_tdata;
wire rx_eth_payload_axis_tvalid;
wire rx_eth_payload_axis_tready;
wire rx_eth_payload_axis_tlast;
wire rx_eth_payload_axis_tuser;

wire tx_eth_hdr_ready;
wire tx_eth_hdr_valid;
wire [47:0] tx_eth_dest_mac;
wire [47:0] tx_eth_src_mac;
wire [15:0] tx_eth_type;
wire [7:0] tx_eth_payload_axis_tdata;
wire tx_eth_payload_axis_tvalid;
wire tx_eth_payload_axis_tready;
wire tx_eth_payload_axis_tlast;
wire tx_eth_payload_axis_tuser;

wire rx_ip_hdr_valid;
wire rx_ip_hdr_ready;
wire [47:0] rx_ip_eth_dest_mac;
wire [47:0] rx_ip_eth_src_mac;
wire [15:0] rx_ip_eth_type;
wire [3:0] rx_ip_version;
wire [3:0] rx_ip_ihl;
wire [5:0] rx_ip_dscp;
wire [1:0] rx_ip_ecn;
wire [15:0] rx_ip_length;
wire [15:0] rx_ip_identification;
wire [2:0] rx_ip_flags;
wire [12:0] rx_ip_fragment_offset;
wire [7:0] rx_ip_ttl;
wire [7:0] rx_ip_protocol;
wire [15:0] rx_ip_header_checksum;
wire [31:0] rx_ip_source_ip;
wire [31:0] rx_ip_dest_ip;
wire [7:0] rx_ip_payload_axis_tdata;
wire rx_ip_payload_axis_tvalid;
wire rx_ip_payload_axis_tready;
wire rx_ip_payload_axis_tlast;
wire rx_ip_payload_axis_tuser;

wire tx_ip_hdr_valid;
wire tx_ip_hdr_ready;
wire [5:0] tx_ip_dscp;
wire [1:0] tx_ip_ecn;
wire [15:0] tx_ip_length;
wire [7:0] tx_ip_ttl;
wire [7:0] tx_ip_protocol;
wire [31:0] tx_ip_source_ip;
wire [31:0] tx_ip_dest_ip;
wire [7:0] tx_ip_payload_axis_tdata;
wire tx_ip_payload_axis_tvalid;
wire tx_ip_payload_axis_tready;
wire tx_ip_payload_axis_tlast;
wire tx_ip_payload_axis_tuser;

wire rx_udp_hdr_valid;
wire rx_udp_hdr_ready;
wire [47:0] rx_udp_eth_dest_mac;
wire [47:0] rx_udp_eth_src_mac;
wire [15:0] rx_udp_eth_type;
wire [3:0] rx_udp_ip_version;
wire [3:0] rx_udp_ip_ihl;
wire [5:0] rx_udp_ip_dscp;
wire [1:0] rx_udp_ip_ecn;
wire [15:0] rx_udp_ip_length;
wire [15:0] rx_udp_ip_identification;
wire [2:0] rx_udp_ip_flags;
wire [12:0] rx_udp_ip_fragment_offset;
wire [7:0] rx_udp_ip_ttl;
wire [7:0] rx_udp_ip_protocol;
wire [15:0] rx_udp_ip_header_checksum;
wire [31:0] rx_udp_ip_source_ip;
wire [31:0] rx_udp_ip_dest_ip;
wire [15:0] rx_udp_source_port;
wire [15:0] rx_udp_dest_port;
wire [15:0] rx_udp_length;
wire [15:0] rx_udp_checksum;
wire [7:0] rx_udp_payload_axis_tdata;
wire rx_udp_payload_axis_tvalid;
wire rx_udp_payload_axis_tready;
wire rx_udp_payload_axis_tlast;
wire rx_udp_payload_axis_tuser;

wire tx_udp_hdr_valid;
wire tx_udp_hdr_ready;
wire [5:0] tx_udp_ip_dscp;
wire [1:0] tx_udp_ip_ecn;
wire [7:0] tx_udp_ip_ttl;
wire [31:0] tx_udp_ip_source_ip;
wire [31:0] tx_udp_ip_dest_ip;
wire [15:0] tx_udp_source_port;
wire [15:0] tx_udp_dest_port;
wire [15:0] tx_udp_length;
wire [15:0] tx_udp_checksum;
wire [7:0] tx_udp_payload_axis_tdata;
wire tx_udp_payload_axis_tvalid;
wire tx_udp_payload_axis_tready;
wire tx_udp_payload_axis_tlast;
wire tx_udp_payload_axis_tuser;

// RX FIFO: input side (from UDP RX payload)
wire [7:0]  rx_fifo_in_tdata;
wire        rx_fifo_in_tvalid;
wire        rx_fifo_in_tready;
wire        rx_fifo_in_tlast;
wire        rx_fifo_in_tuser;

// RX FIFO: output side (routed to loopback or FIR)
wire [7:0]  rx_fifo_out_tdata;
wire        rx_fifo_out_tvalid;
wire        rx_fifo_out_tready;
wire        rx_fifo_out_tlast;
wire        rx_fifo_out_tuser;

// TX FIFO: input side (from loopback or FIR return)
wire [7:0]  tx_fifo_in_tdata;
wire        tx_fifo_in_tvalid;
wire        tx_fifo_in_tready;
wire        tx_fifo_in_tlast;
wire        tx_fifo_in_tuser;

// TX FIFO: output side (to UDP TX payload)
wire [7:0]  tx_fifo_out_tdata;
wire        tx_fifo_out_tvalid;
wire        tx_fifo_out_tready;
wire        tx_fifo_out_tlast;
wire        tx_fifo_out_tuser;

// =========================================================================
// IP ports not used
// =========================================================================
assign rx_ip_hdr_ready = 1;
assign rx_ip_payload_axis_tready = 1;

assign tx_ip_hdr_valid = 0;
assign tx_ip_dscp = 0;
assign tx_ip_ecn = 0;
assign tx_ip_length = 0;
assign tx_ip_ttl = 0;
assign tx_ip_protocol = 0;
assign tx_ip_source_ip = 0;
assign tx_ip_dest_ip = 0;
assign tx_ip_payload_axis_tdata = 0;
assign tx_ip_payload_axis_tvalid = 0;
assign tx_ip_payload_axis_tlast = 0;
assign tx_ip_payload_axis_tuser = 0;

// =========================================================================
// Port Check (on UDP RX input side)
// =========================================================================
wire is_target_port = (rx_udp_dest_port == dst_port_cfg) && dst_port_cfg != 0;
wire is_source_port = (rx_udp_source_port == src_port_cfg) && src_port_cfg != 0;
wire port_match     = is_target_port;
wire loopback_match = (is_target_port && is_source_port) || loopback_en;
wire no_match       = !port_match;

reg port_match_reg = 0;
reg no_match_reg   = 0;

always @(posedge clk) begin
    if (rst) begin
        port_match_reg <= 0;
        no_match_reg   <= 0;
    end else begin
        if (rx_udp_payload_axis_tvalid) begin
            if ((!port_match_reg && !no_match_reg) ||
                (rx_udp_payload_axis_tvalid && rx_udp_payload_axis_tready && rx_udp_payload_axis_tlast)) begin
                port_match_reg <= port_match;
                no_match_reg   <= no_match;
            end
        end else begin
            port_match_reg <= 0;
            no_match_reg   <= 0;
        end
    end
end

// =========================================================================
// Routing Decision (persists across RX FIFO drain)
// =========================================================================

reg route_loopback = 0;

always @(posedge clk) begin
    if (rst) begin
        route_loopback <= 0;
    end else begin
        if (rx_udp_payload_axis_tvalid && port_match_reg && !route_loopback && loopback_match) begin
            // Latch loopback decision on first valid beat of a matched packet
            route_loopback <= 1;
        end else if (route_loopback && rx_fifo_out_tvalid && rx_fifo_out_tready && rx_fifo_out_tlast) begin
            // Clear after RX FIFO output packet completes
            route_loopback <= 0;
        end
    end
end

// =========================================================================
// UDP Header Handling
// =========================================================================
assign tx_udp_hdr_valid       = rx_udp_hdr_valid && port_match;
assign rx_udp_hdr_ready       = (tx_eth_hdr_ready && port_match) || no_match;
assign tx_udp_ip_dscp         = 0;
assign tx_udp_ip_ecn          = 0;
assign tx_udp_ip_ttl          = 64;
assign tx_udp_ip_source_ip    = local_ip;
assign tx_udp_ip_dest_ip      = rx_udp_ip_source_ip;
assign tx_udp_source_port     = rx_udp_dest_port;
assign tx_udp_dest_port       = rx_udp_source_port;
assign tx_udp_length          = rx_udp_length;
assign tx_udp_checksum        = 0;

// =========================================================================
// TX FIFO Output → UDP TX Payload
// =========================================================================
assign tx_udp_payload_axis_tdata  = tx_fifo_out_tdata;
assign tx_udp_payload_axis_tvalid = tx_fifo_out_tvalid;
assign tx_fifo_out_tready         = tx_udp_payload_axis_tready;
assign tx_udp_payload_axis_tlast  = tx_fifo_out_tlast;
assign tx_udp_payload_axis_tuser  = tx_fifo_out_tuser;

// =========================================================================
// RX FIFO Input ← UDP RX Payload (when port matched)
// =========================================================================
assign rx_fifo_in_tdata  = rx_udp_payload_axis_tdata;
assign rx_fifo_in_tvalid = rx_udp_payload_axis_tvalid && port_match_reg;
assign rx_fifo_in_tlast  = rx_udp_payload_axis_tlast;
assign rx_fifo_in_tuser  = rx_udp_payload_axis_tuser;

assign rx_udp_payload_axis_tready = (rx_fifo_in_tready && port_match_reg) || no_match_reg;

// =========================================================================
// RX FIFO Output Routing (Loopback or Forward to FIR)
// =========================================================================

// Forward to FIR: RX FIFO output → external RX port (only when NOT loopback)
assign udp_rx_ext_tdata  = rx_fifo_out_tdata;
assign udp_rx_ext_tvalid = rx_fifo_out_tvalid && !route_loopback;
assign udp_rx_ext_tlast  = rx_fifo_out_tlast;
assign udp_rx_ext_tuser  = rx_fifo_out_tuser;

// RX FIFO output backpressure: consumed by TX FIFO (loopback) or FIR (forward)
assign rx_fifo_out_tready = route_loopback ? tx_fifo_in_tready : udp_rx_ext_tready;

// =========================================================================
// TX FIFO Input Mux (Loopback from RX FIFO vs FIR return)
// =========================================================================
assign tx_fifo_in_tdata  = route_loopback ? rx_fifo_out_tdata  : udp_tx_ext_tdata;
assign tx_fifo_in_tvalid = route_loopback ? rx_fifo_out_tvalid : udp_tx_ext_tvalid;
assign tx_fifo_in_tlast  = route_loopback ? rx_fifo_out_tlast  : udp_tx_ext_tlast;
assign tx_fifo_in_tuser  = route_loopback ? rx_fifo_out_tuser  : udp_tx_ext_tuser;

// FIR return backpressure (only accepted when NOT in loopback)
assign udp_tx_ext_tready = tx_fifo_in_tready && !route_loopback;

// synthesis translate_off
always @(posedge clk) begin
    if (route_loopback && rx_fifo_out_tvalid && rx_fifo_out_tready && rx_fifo_out_tlast)
        $display("[Node %0s] Loopback: packet forwarded from RX FIFO to TX FIFO", TARGET);
    if (!route_loopback && rx_fifo_out_tvalid && rx_fifo_out_tready && rx_fifo_out_tlast)
        $display("[Node %0s] FIR Forward: packet sent from RX FIFO to FIR", TARGET);
end
// synthesis translate_on

// =========================================================================
// Ethernet MAC (1G GMII FIFO)
// =========================================================================
eth_mac_1g_fifo #(
    .ENABLE_PADDING(1),
    .MIN_FRAME_LENGTH(64),
    .TX_FIFO_DEPTH(4096),
    .TX_FRAME_FIFO(1),
    .RX_FIFO_DEPTH(4096),
    .RX_FRAME_FIFO(1)
)
eth_mac_inst (
    .rx_clk(gmii_rx_clk),
    .rx_rst(rst),
    .tx_clk(clk), // For GMII generation we'll drive it from MAC clk or testbench
    .tx_rst(rst),
    .logic_clk(clk),
    .logic_rst(rst),
    .tx_axis_tdata(tx_axis_tdata),
    .tx_axis_tkeep(1'b1), // data is 8 bits, keep is 1
    .tx_axis_tvalid(tx_axis_tvalid),
    .tx_axis_tready(tx_axis_tready),
    .tx_axis_tlast(tx_axis_tlast),
    .tx_axis_tuser(tx_axis_tuser),
    .rx_axis_tdata(rx_axis_tdata),
    .rx_axis_tkeep(),
    .rx_axis_tvalid(rx_axis_tvalid),
    .rx_axis_tready(rx_axis_tready),
    .rx_axis_tlast(rx_axis_tlast),
    .rx_axis_tuser(rx_axis_tuser),
    .gmii_rxd(gmii_rxd),
    .gmii_rx_dv(gmii_rx_dv),
    .gmii_rx_er(gmii_rx_er),
    .gmii_txd(gmii_txd),
    .gmii_tx_en(gmii_tx_en),
    .gmii_tx_er(gmii_tx_er),
    .rx_clk_enable(1'b1),
    .tx_clk_enable(1'b1),
    .rx_mii_select(1'b0),
    .tx_mii_select(1'b0),
    .tx_error_underflow(),
    .tx_fifo_overflow(),
    .tx_fifo_bad_frame(),
    .tx_fifo_good_frame(),
    .rx_error_bad_frame(),
    .rx_error_bad_fcs(),
    .rx_fifo_overflow(),
    .rx_fifo_bad_frame(),
    .rx_fifo_good_frame(),
    .cfg_ifg(8'd12),
    .cfg_tx_enable(1'b1),
    .cfg_rx_enable(1'b1)
);

assign gmii_tx_clk = clk;

// =========================================================================
// Ethernet Frame RX
// =========================================================================
eth_axis_rx
eth_axis_rx_inst (
    .clk(clk),
    .rst(rst),
    .s_axis_tdata(rx_axis_tdata),
    .s_axis_tvalid(rx_axis_tvalid),
    .s_axis_tready(rx_axis_tready),
    .s_axis_tlast(rx_axis_tlast),
    .s_axis_tuser(rx_axis_tuser),
    .m_eth_hdr_valid(rx_eth_hdr_valid),
    .m_eth_hdr_ready(rx_eth_hdr_ready),
    .m_eth_dest_mac(rx_eth_dest_mac),
    .m_eth_src_mac(rx_eth_src_mac),
    .m_eth_type(rx_eth_type),
    .m_eth_payload_axis_tdata(rx_eth_payload_axis_tdata),
    .m_eth_payload_axis_tvalid(rx_eth_payload_axis_tvalid),
    .m_eth_payload_axis_tready(rx_eth_payload_axis_tready),
    .m_eth_payload_axis_tlast(rx_eth_payload_axis_tlast),
    .m_eth_payload_axis_tuser(rx_eth_payload_axis_tuser),
    .busy(),
    .error_header_early_termination()
);

// =========================================================================
// Ethernet Frame TX
// =========================================================================
eth_axis_tx
eth_axis_tx_inst (
    .clk(clk),
    .rst(rst),
    .s_eth_hdr_valid(tx_eth_hdr_valid),
    .s_eth_hdr_ready(tx_eth_hdr_ready),
    .s_eth_dest_mac(tx_eth_dest_mac),
    .s_eth_src_mac(tx_eth_src_mac),
    .s_eth_type(tx_eth_type),
    .s_eth_payload_axis_tdata(tx_eth_payload_axis_tdata),
    .s_eth_payload_axis_tvalid(tx_eth_payload_axis_tvalid),
    .s_eth_payload_axis_tready(tx_eth_payload_axis_tready),
    .s_eth_payload_axis_tlast(tx_eth_payload_axis_tlast),
    .s_eth_payload_axis_tuser(tx_eth_payload_axis_tuser),
    .m_axis_tdata(tx_axis_tdata),
    .m_axis_tvalid(tx_axis_tvalid),
    .m_axis_tready(tx_axis_tready),
    .m_axis_tlast(tx_axis_tlast),
    .m_axis_tuser(tx_axis_tuser),
    .busy()
);

// =========================================================================
// UDP Complete
// =========================================================================
localparam ARP_RETRY_INTERVAL = 125000000 * 1; 
localparam ARP_TIMEOUT        = 125000000 * 4; 

udp_complete #(
    .ARP_REQUEST_RETRY_COUNT   (4),
    .ARP_REQUEST_RETRY_INTERVAL(ARP_RETRY_INTERVAL),
    .ARP_REQUEST_TIMEOUT       (ARP_TIMEOUT)
)
udp_complete_inst (
    .clk(clk),
    .rst(rst),
    .s_eth_hdr_valid(rx_eth_hdr_valid),
    .s_eth_hdr_ready(rx_eth_hdr_ready),
    .s_eth_dest_mac(rx_eth_dest_mac),
    .s_eth_src_mac(rx_eth_src_mac),
    .s_eth_type(rx_eth_type),
    .s_eth_payload_axis_tdata(rx_eth_payload_axis_tdata),
    .s_eth_payload_axis_tvalid(rx_eth_payload_axis_tvalid),
    .s_eth_payload_axis_tready(rx_eth_payload_axis_tready),
    .s_eth_payload_axis_tlast(rx_eth_payload_axis_tlast),
    .s_eth_payload_axis_tuser(rx_eth_payload_axis_tuser),
    .m_eth_hdr_valid(tx_eth_hdr_valid),
    .m_eth_hdr_ready(tx_eth_hdr_ready),
    .m_eth_dest_mac(tx_eth_dest_mac),
    .m_eth_src_mac(tx_eth_src_mac),
    .m_eth_type(tx_eth_type),
    .m_eth_payload_axis_tdata(tx_eth_payload_axis_tdata),
    .m_eth_payload_axis_tvalid(tx_eth_payload_axis_tvalid),
    .m_eth_payload_axis_tready(tx_eth_payload_axis_tready),
    .m_eth_payload_axis_tlast(tx_eth_payload_axis_tlast),
    .m_eth_payload_axis_tuser(tx_eth_payload_axis_tuser),
    .s_ip_hdr_valid(tx_ip_hdr_valid),
    .s_ip_hdr_ready(tx_ip_hdr_ready),
    .s_ip_dscp(tx_ip_dscp),
    .s_ip_ecn(tx_ip_ecn),
    .s_ip_length(tx_ip_length),
    .s_ip_ttl(tx_ip_ttl),
    .s_ip_protocol(tx_ip_protocol),
    .s_ip_source_ip(tx_ip_source_ip),
    .s_ip_dest_ip(tx_ip_dest_ip),
    .s_ip_payload_axis_tdata(tx_ip_payload_axis_tdata),
    .s_ip_payload_axis_tvalid(tx_ip_payload_axis_tvalid),
    .s_ip_payload_axis_tready(tx_ip_payload_axis_tready),
    .s_ip_payload_axis_tlast(tx_ip_payload_axis_tlast),
    .s_ip_payload_axis_tuser(tx_ip_payload_axis_tuser),
    .m_ip_hdr_valid(rx_ip_hdr_valid),
    .m_ip_hdr_ready(rx_ip_hdr_ready),
    .m_ip_eth_dest_mac(rx_ip_eth_dest_mac),
    .m_ip_eth_src_mac(rx_ip_eth_src_mac),
    .m_ip_eth_type(rx_ip_eth_type),
    .m_ip_version(rx_ip_version),
    .m_ip_ihl(rx_ip_ihl),
    .m_ip_dscp(rx_ip_dscp),
    .m_ip_ecn(rx_ip_ecn),
    .m_ip_length(rx_ip_length),
    .m_ip_identification(rx_ip_identification),
    .m_ip_flags(rx_ip_flags),
    .m_ip_fragment_offset(rx_ip_fragment_offset),
    .m_ip_ttl(rx_ip_ttl),
    .m_ip_protocol(rx_ip_protocol),
    .m_ip_header_checksum(rx_ip_header_checksum),
    .m_ip_source_ip(rx_ip_source_ip),
    .m_ip_dest_ip(rx_ip_dest_ip),
    .m_ip_payload_axis_tdata(rx_ip_payload_axis_tdata),
    .m_ip_payload_axis_tvalid(rx_ip_payload_axis_tvalid),
    .m_ip_payload_axis_tready(rx_ip_payload_axis_tready),
    .m_ip_payload_axis_tlast(rx_ip_payload_axis_tlast),
    .m_ip_payload_axis_tuser(rx_ip_payload_axis_tuser),
    .s_udp_hdr_valid(tx_udp_hdr_valid),
    .s_udp_hdr_ready(tx_udp_hdr_ready),
    .s_udp_ip_dscp(tx_udp_ip_dscp),
    .s_udp_ip_ecn(tx_udp_ip_ecn),
    .s_udp_ip_ttl(tx_udp_ip_ttl),
    .s_udp_ip_source_ip(tx_udp_ip_source_ip),
    .s_udp_ip_dest_ip(tx_udp_ip_dest_ip),
    .s_udp_source_port(tx_udp_source_port),
    .s_udp_dest_port(tx_udp_dest_port),
    .s_udp_length(tx_udp_length),
    .s_udp_checksum(tx_udp_checksum),
    .s_udp_payload_axis_tdata(tx_udp_payload_axis_tdata),
    .s_udp_payload_axis_tvalid(tx_udp_payload_axis_tvalid),
    .s_udp_payload_axis_tready(tx_udp_payload_axis_tready),
    .s_udp_payload_axis_tlast(tx_udp_payload_axis_tlast),
    .s_udp_payload_axis_tuser(tx_udp_payload_axis_tuser),
    .m_udp_hdr_valid(rx_udp_hdr_valid),
    .m_udp_hdr_ready(rx_udp_hdr_ready),
    .m_udp_eth_dest_mac(rx_udp_eth_dest_mac),
    .m_udp_eth_src_mac(rx_udp_eth_src_mac),
    .m_udp_eth_type(rx_udp_eth_type),
    .m_udp_ip_version(rx_udp_ip_version),
    .m_udp_ip_ihl(rx_udp_ip_ihl),
    .m_udp_ip_dscp(rx_udp_ip_dscp),
    .m_udp_ip_ecn(rx_udp_ip_ecn),
    .m_udp_ip_length(rx_udp_ip_length),
    .m_udp_ip_identification(rx_udp_ip_identification),
    .m_udp_ip_flags(rx_udp_ip_flags),
    .m_udp_ip_fragment_offset(rx_udp_ip_fragment_offset),
    .m_udp_ip_ttl(rx_udp_ip_ttl),
    .m_udp_ip_protocol(rx_udp_ip_protocol),
    .m_udp_ip_header_checksum(rx_udp_ip_header_checksum),
    .m_udp_ip_source_ip(rx_udp_ip_source_ip),
    .m_udp_ip_dest_ip(rx_udp_ip_dest_ip),
    .m_udp_source_port(rx_udp_source_port),
    .m_udp_dest_port(rx_udp_dest_port),
    .m_udp_length(rx_udp_length),
    .m_udp_checksum(rx_udp_checksum),
    .m_udp_payload_axis_tdata(rx_udp_payload_axis_tdata),
    .m_udp_payload_axis_tvalid(rx_udp_payload_axis_tvalid),
    .m_udp_payload_axis_tready(rx_udp_payload_axis_tready),
    .m_udp_payload_axis_tlast(rx_udp_payload_axis_tlast),
    .m_udp_payload_axis_tuser(rx_udp_payload_axis_tuser),
    .ip_rx_busy(),
    .ip_tx_busy(),
    .udp_rx_busy(),
    .udp_tx_busy(),
    .ip_rx_error_header_early_termination(),
    .ip_rx_error_payload_early_termination(),
    .ip_rx_error_invalid_header(),
    .ip_rx_error_invalid_checksum(),
    .ip_tx_error_payload_early_termination(),
    .ip_tx_error_arp_failed(),
    .udp_rx_error_header_early_termination(),
    .udp_rx_error_payload_early_termination(),
    .udp_tx_error_payload_early_termination(),
    .local_mac(local_mac),
    .local_ip(local_ip),
    .gateway_ip(gateway_ip),
    .subnet_mask(subnet_mask),
    .clear_arp_cache(clear_arp)
);

// =========================================================================
// RX FIFO — buffers incoming UDP payload before routing decision
// =========================================================================
axis_fifo #(
    .DEPTH(8192),
    .DATA_WIDTH(8),
    .KEEP_ENABLE(0),
    .ID_ENABLE(0),
    .DEST_ENABLE(0),
    .USER_ENABLE(1),
    .USER_WIDTH(1),
    .FRAME_FIFO(0)
)
udp_rx_fifo (
    .clk(clk),
    .rst(rst),
    .s_axis_tdata (rx_fifo_in_tdata),
    .s_axis_tkeep (0),
    .s_axis_tvalid(rx_fifo_in_tvalid),
    .s_axis_tready(rx_fifo_in_tready),
    .s_axis_tlast (rx_fifo_in_tlast),
    .s_axis_tid   (0),
    .s_axis_tdest (0),
    .s_axis_tuser (rx_fifo_in_tuser),
    .m_axis_tdata (rx_fifo_out_tdata),
    .m_axis_tkeep (),
    .m_axis_tvalid(rx_fifo_out_tvalid),
    .m_axis_tready(rx_fifo_out_tready),
    .m_axis_tlast (rx_fifo_out_tlast),
    .m_axis_tid   (),
    .m_axis_tdest (),
    .m_axis_tuser (rx_fifo_out_tuser),
    .status_overflow(),
    .status_bad_frame(),
    .status_good_frame()
);

// =========================================================================
// TX FIFO — buffers outgoing data (loopback or FIR return) before UDP TX
// =========================================================================
axis_fifo #(
    .DEPTH(8192),
    .DATA_WIDTH(8),
    .KEEP_ENABLE(0),
    .ID_ENABLE(0),
    .DEST_ENABLE(0),
    .USER_ENABLE(1),
    .USER_WIDTH(1),
    .FRAME_FIFO(0)
)
udp_tx_fifo (
    .clk(clk),
    .rst(rst),
    .s_axis_tdata (tx_fifo_in_tdata),
    .s_axis_tkeep (0),
    .s_axis_tvalid(tx_fifo_in_tvalid),
    .s_axis_tready(tx_fifo_in_tready),
    .s_axis_tlast (tx_fifo_in_tlast),
    .s_axis_tid   (0),
    .s_axis_tdest (0),
    .s_axis_tuser (tx_fifo_in_tuser),
    .m_axis_tdata (tx_fifo_out_tdata),
    .m_axis_tkeep (),
    .m_axis_tvalid(tx_fifo_out_tvalid),
    .m_axis_tready(tx_fifo_out_tready),
    .m_axis_tlast (tx_fifo_out_tlast),
    .m_axis_tid   (),
    .m_axis_tdest (),
    .m_axis_tuser (tx_fifo_out_tuser),
    .status_overflow(),
    .status_bad_frame(),
    .status_good_frame()
);

endmodule
`resetall
