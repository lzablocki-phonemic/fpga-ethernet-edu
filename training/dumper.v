
    module dumper;
        initial begin
            $dumpfile("/home/piotr/workspace/Soc_ethernet/fpga-ethernet-edu/training/my_design.vcd");
            $dumpvars(0, my_design);
        end
    endmodule
    