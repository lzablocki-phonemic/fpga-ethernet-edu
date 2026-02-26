`timescale 1ns / 1ps

module udp_axi_data_gen #
(
    parameter DATA_WIDTH    = 16,
    parameter BYTES_TO_SEND = 1000
)
(
    input  wire                        clk,
    input  wire                        rst,
    input  wire                        trigger,

    input  wire [DATA_WIDTH-1:0]       s_axis_tdata,
    input  wire                        s_axis_tvalid,
    output wire                        s_axis_tready,
    input  wire                        s_axis_tlast,
    input  wire [0:0]                  s_axis_tuser,

    output wire [DATA_WIDTH-1:0]       m_axis_tdata,
    output wire                        m_axis_tvalid,
    output wire                        m_axis_tlast,
    output wire [0:0]                  m_axis_tuser,
    input  wire                        m_axis_tready
);

    localparam BYTES_PER_WORD = DATA_WIDTH / 8;
    localparam MAX_TRANSFERS  = BYTES_TO_SEND / BYTES_PER_WORD;

    reg [$clog2(MAX_TRANSFERS)-1:0] transfer_cnt;
    reg [DATA_WIDTH-1:0]            data_reg;
    reg                             busy_reg;

    assign s_axis_tready = 1'b1;

    assign m_axis_tdata  = data_reg;
    assign m_axis_tvalid = busy_reg;
    assign m_axis_tlast  = (transfer_cnt == (MAX_TRANSFERS - 1)) && busy_reg;
    assign m_axis_tuser  = 1'b0;

    always @(posedge clk) begin
        if (rst) begin
            transfer_cnt <= 0;
            data_reg     <= 0;
            busy_reg     <= 1'b0;
        end else begin
            if (!busy_reg) begin
                if (trigger) begin
                    busy_reg <= 1'b1;
                end
            end else begin
                if (m_axis_tready) begin
                    data_reg <= data_reg + 1'b1;
                    
                    if (transfer_cnt == MAX_TRANSFERS - 1) begin
                        transfer_cnt <= 0;
                        busy_reg     <= 1'b0;
                    end else begin
                        transfer_cnt <= transfer_cnt + 1'b1;
                    end
                end
            end
        end
    end

endmodule