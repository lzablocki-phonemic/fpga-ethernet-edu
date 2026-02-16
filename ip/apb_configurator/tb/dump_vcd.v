`timescale 1ns / 1ps

// Waveform dumping module for cocotb simulations
// This module automatically dumps VCD waveforms when VCD_ENABLE is defined
module dump_vcd;
    initial begin
        `ifdef VCD_ENABLE
            // Get VCD filename from plusargs, default to "waveform.vcd"
            string vcd_file;
            if (!$value$plusargs("vcd_file=%s", vcd_file)) begin
                vcd_file = "waveform.vcd";
            end
            
            $display("[VCD] Dumping waveforms to: %s", vcd_file);
            $dumpfile(vcd_file);
            $dumpvars(0);  // 0 = dump all levels of hierarchy
        `endif
    end
endmodule
