`timescale 1ns/1ps
module my_design (
    input wire clk,
    input wire rst,
    output reg [3:0] count
);

    always @(posedge clk or posedge rst) begin
        if (rst)
            count <= 4'b0000;
        else
            count <= count + 1;
    end

    initial begin
        $display("STARTING VCD DUMP");
        $dumpfile("my_design_ver.vcd");   
        $dumpvars(0, my_design);       
        $dumpon;                       
        $display("VCD DUMP INITIALIZED");
    end

    always @(clk) begin
        $dumpflush; 
    end
endmodule