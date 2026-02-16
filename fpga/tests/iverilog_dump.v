module iverilog_dump();
initial begin
    $dumpfile("/home/piotr/workspace/Soc_ethernet/fpga-ethernet-edu/fpga/tests/../sim/fpga_core_10g.fst");
    $dumpvars(0, fpga_core_10g);
end
endmodule
