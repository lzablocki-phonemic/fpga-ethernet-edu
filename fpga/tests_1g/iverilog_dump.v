module iverilog_dump();
initial begin
    $dumpfile("/home/piotr/workspace/Soc_ethernet/fpga-ethernet-edu/fpga/tests_1g/../sim/fpga_core_1G_fifo.fst");
    $dumpvars(0, fpga_core_1G_fifo);
end
endmodule
