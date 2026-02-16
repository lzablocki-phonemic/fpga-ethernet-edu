module iverilog_dump();
initial begin
    $dumpfile("my_design_make_AAA.vcd");
    $dumpvars(0, my_design);
end
endmodule
