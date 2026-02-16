`timescale 1ns / 1ps

// -----------------------------------------------------------------------------
// Module: apb_configurator
// Description: Generic APB slave module for parameter configuration.
// -----------------------------------------------------------------------------

module apb_configurator #(
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
    output reg  [APB_DATA_WIDTH-1:0] prdata,
    output reg                       pready,
    output reg                       pslverr,

    output wire [APB_DATA_WIDTH-1:0] config_regs_out [NUM_REGS-1:0],
    output wire                      config_ready_out [NUM_REGS-1:0]
);

    reg [APB_DATA_WIDTH-1:0] registers [0:NUM_REGS-1];
    reg                      reg_ready_flags [0:NUM_REGS-1];

    // Address decoding (word-aligned)
    wire [APB_ADDR_WIDTH-1:0] local_addr = paddr - BASE_ADDR;
    // Assuming 32-bit words (4 bytes)
    wire [APB_ADDR_WIDTH-1:0] reg_index  = local_addr / (APB_DATA_WIDTH/8);
    
    wire                      addr_valid = (paddr >= BASE_ADDR) && (reg_index < NUM_REGS);
    wire apb_setup  = psel && !penable;
    wire apb_access = psel && penable;
    wire apb_write  = apb_access && pwrite;
    wire apb_read   = apb_access && !pwrite;

    genvar g;
    generate
        for (g = 0; g < NUM_REGS; g = g + 1) begin : gen_reg_out
            assign config_regs_out[g] = registers[g];
            assign config_ready_out[g] = reg_ready_flags[g];
        end
    endgenerate
    integer i;

    always @(posedge pclk or negedge presetn) begin
        if (!presetn) begin
            prdata          <= {APB_DATA_WIDTH{1'b0}};
            pready          <= 1'b0;
            pslverr         <= 1'b0;
            
            for (i = 0; i < NUM_REGS; i = i + 1) begin
                registers[i] <= {APB_DATA_WIDTH{1'b0}};
                reg_ready_flags[i] <= 1'b0;
            end
        end else begin
            pready  <= 1'b0;
            pslverr <= 1'b0;

            if (apb_access && !pready) begin
                pready <= 1'b1; // Zero wait-state

                if (addr_valid) begin
                    if (apb_write) begin
                        registers[reg_index]       <= pwdata;
                        reg_ready_flags[reg_index] <= 1'b1;
                    end else if (apb_read) begin
                        prdata <= registers[reg_index];
                    end
                end else begin
                    pslverr <= 1'b1;
                    prdata  <= {APB_DATA_WIDTH{1'b0}};
                end
            end
        end
    end

endmodule
