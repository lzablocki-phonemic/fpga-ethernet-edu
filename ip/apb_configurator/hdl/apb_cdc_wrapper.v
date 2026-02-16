`timescale 1ns / 1ps

module apb_cdc_wrapper #(
    parameter APB_DATA_WIDTH = 32,
    parameter APB_ADDR_WIDTH = 32,
    parameter NUM_REGS       = 16,
    parameter BASE_ADDR      = 32'h0000_0000
)(
    input  wire                      pclk,
    input  wire                      presetn,
    input  wire [APB_ADDR_WIDTH-1:0] paddr,
    input  wire                      psel,
    input  wire                      penable,
    input  wire                      pwrite,
    input  wire [APB_DATA_WIDTH-1:0] pwdata,
    output wire [APB_DATA_WIDTH-1:0] prdata,
    output wire                      pready,
    output wire                      pslverr,

    // User Readout Domain
    input  wire                      rd_clk,
    output reg  [APB_DATA_WIDTH-1:0] rd_data_out[NUM_REGS-1:0],
    output reg                       rd_ready [NUM_REGS-1:0]
);

    wire [APB_DATA_WIDTH-1:0] config_array [NUM_REGS-1:0];
    wire                       config_ready_array [NUM_REGS-1:0];

    apb_configurator #(
        .APB_DATA_WIDTH(APB_DATA_WIDTH),
        .APB_ADDR_WIDTH(APB_ADDR_WIDTH),
        .NUM_REGS(NUM_REGS),
        .BASE_ADDR(BASE_ADDR)
    ) dut (
        .pclk(pclk),
        .presetn(presetn),
        .paddr(paddr),
        .psel(psel),
        .penable(penable),
        .pwrite(pwrite),
        .pwdata(pwdata),
        .prdata(prdata),
        .pready(pready),
        .pslverr(pslverr),
        .config_regs_out(config_array),
        .config_ready_out(config_ready_array)
    );

    integer i;
    always @(posedge rd_clk) begin
        for (i = 0; i < NUM_REGS; i = i + 1) begin
            rd_data_out[i] <= config_array[i];
            rd_ready[i]    <= config_ready_array[i];
        end
    end

endmodule