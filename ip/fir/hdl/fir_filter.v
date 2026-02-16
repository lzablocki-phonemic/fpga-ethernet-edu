`resetall
`timescale 1ns / 1ps
`default_nettype none

/*
 * FIR Filter with AXI-Stream interface and bypass mode
 *
 * Supports two operating modes selected at compile time by SAMPLE_WIDTH vs DATA_WIDTH:
 *
 *   SAMPLE_WIDTH <= DATA_WIDTH  (packed mode)
 *     Multiple samples fit in one AXI word. Each word is unpacked into
 *     SAMPLES_PER_WORD individual samples, filtered, and repacked.
 *     The delay line persists across word boundaries within a packet.
 *
 *   SAMPLE_WIDTH > DATA_WIDTH   (wide-sample mode)
 *     One sample spans multiple AXI beats. Incoming beats are accumulated
 *     into a full sample, filtered, then serialized back out.
 *
 * Parameters:
 *   DATA_WIDTH   — AXI-Stream data bus width (default 16)
 *   COEFF_WIDTH  — coefficient width (default 16)
 *   NUM_TAPS     — number of FIR taps (default 4)
 *   SAMPLE_WIDTH — individual sample width (default 8)
 *
 * When bypass=1, input data passes straight through.
 * History / delay line is cleared on tlast so each packet starts fresh.
 */
module fir_filter #
(
    parameter DATA_WIDTH   = 16,
    parameter COEFF_WIDTH  = 16,
    parameter NUM_TAPS     = 64,
    parameter SAMPLE_WIDTH = 8
)
(
    input  wire                        clk,
    input  wire                        rst,

    input  wire                        bypass,

    input  wire                        coeff_we,
    input  wire [$clog2(NUM_TAPS)-1:0] coeff_addr,
    input  wire [COEFF_WIDTH-1:0]      coeff_data,

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

// Accumulator width to prevent overflow
localparam ACC_WIDTH = SAMPLE_WIDTH + COEFF_WIDTH + $clog2(NUM_TAPS);

// =========================================================================
// Coefficient storage (shared by both modes)
// =========================================================================
reg [COEFF_WIDTH-1:0] coeffs [0:NUM_TAPS-1];

integer k;
initial begin
    for (k = 0; k < NUM_TAPS; k = k + 1)
        coeffs[k] = 0;
end

always @(posedge clk) begin
    if (coeff_we)
        coeffs[coeff_addr] <= coeff_data;
end

// =========================================================================
// Mode selection via generate
// =========================================================================
generate
if (SAMPLE_WIDTH <= DATA_WIDTH) begin : gen_packed
    // =================================================================
    // PACKED MODE: multiple samples per AXI word
    // =================================================================
    localparam SAMPLES_PER_WORD = DATA_WIDTH / SAMPLE_WIDTH;

    // Sample history (persists across word boundaries within a packet)
    // history[0] = oldest, history[NUM_TAPS-2] = most recent
    reg [SAMPLE_WIDTH-1:0] history [0:NUM_TAPS-2];

    // Pipeline control
    wire input_accepted = s_axis_tvalid;
    reg out_valid = 0;
    reg out_last  = 0;
    reg out_user  = 0;
    reg [DATA_WIDTH-1:0] out_data = 0;
    reg input_accepted_reg = 0;

    assign s_axis_tready = input_accepted_reg;
    assign m_axis_tdata  = out_data;
    assign m_axis_tvalid = out_valid;
    assign m_axis_tlast  = out_last;
    assign m_axis_tuser  = out_user;

    // Work array: [history | current word samples]
    reg [SAMPLE_WIDTH-1:0] all_samples [0:NUM_TAPS-2+SAMPLES_PER_WORD];

    integer s, t, h;
    reg signed [ACC_WIDTH-1:0] sample_acc;

    initial begin
        for (h = 0; h < NUM_TAPS-1; h = h + 1)
            history[h] = 0;
    end

    always @(posedge clk) begin
        if (rst) begin
            out_valid <= 0;
            out_last  <= 0;
            out_user  <= 0;
            out_data  <= 0;
            input_accepted_reg <= 0;
            for (h = 0; h < NUM_TAPS-1; h = h + 1)
                history[h] <= 0;
        end else begin
            if (input_accepted && !input_accepted_reg) begin
                out_valid <= 0;
                input_accepted_reg <= 1;
            end

            if (input_accepted_reg) begin
                // Build combined sample array
                for (h = 0; h < NUM_TAPS-1; h = h + 1)
                    all_samples[h] = history[h];
                for (s = 0; s < SAMPLES_PER_WORD; s = s + 1)
                    all_samples[NUM_TAPS-1+s] = s_axis_tdata[s*SAMPLE_WIDTH +: SAMPLE_WIDTH];

                if (bypass) begin
                    out_data <= s_axis_tdata;
                end else begin
                    for (s = 0; s < SAMPLES_PER_WORD; s = s + 1) begin
                        sample_acc = 0;
                        for (t = 0; t < NUM_TAPS; t = t + 1) begin
                            sample_acc = sample_acc
                                + $signed({{(ACC_WIDTH-SAMPLE_WIDTH){all_samples[NUM_TAPS-1+s-t][SAMPLE_WIDTH-1]}}, all_samples[NUM_TAPS-1+s-t]})
                                * $signed({{(ACC_WIDTH-COEFF_WIDTH){coeffs[t][COEFF_WIDTH-1]}}, coeffs[t]});
                        end
                        out_data[s*SAMPLE_WIDTH +: SAMPLE_WIDTH] <= sample_acc[SAMPLE_WIDTH-1:0];
                    end
                end

                // Update history for next beat
                for (h = 0; h < NUM_TAPS-1; h = h + 1)
                    history[h] <= all_samples[SAMPLES_PER_WORD + h];

                out_valid <= 1;
                out_user  <= s_axis_tuser;

                if (s_axis_tlast) begin
                    out_last <= 1;
                    input_accepted_reg <= 0;
                    for (h = 0; h < NUM_TAPS-1; h = h + 1)
                        history[h] <= 0;
                end else begin
                    out_last <= 0;
                end
            end else begin
                out_last  <= 0;
                out_valid <= 0;
            end
        end
    end

end else begin : gen_wide
    // =================================================================
    // WIDE-SAMPLE MODE: one sample spans multiple AXI beats
    // =================================================================
    localparam BEATS_PER_SAMPLE = SAMPLE_WIDTH / DATA_WIDTH;
    localparam CNT_WIDTH = $clog2(BEATS_PER_SAMPLE);

    // FIR delay line (sample-level)
    reg [SAMPLE_WIDTH-1:0] delay_line [0:NUM_TAPS-1];

    // Input accumulator
    reg [SAMPLE_WIDTH-1:0] sample_in;
    reg [CNT_WIDTH:0]      in_cnt;
    reg                     in_last;  // remember tlast during accumulation
    reg                     in_user;

    // Output shift register
    reg [SAMPLE_WIDTH-1:0] sample_out;
    reg [CNT_WIDTH:0]      out_cnt;
    reg                     out_active;
    reg                     out_last;
    reg                     out_user;

    // State: 0=accumulate, 1=output
    reg state = 0;
    localparam S_ACCUMULATE = 0;
    localparam S_OUTPUT     = 1;

    assign s_axis_tready = (state == S_ACCUMULATE);
    assign m_axis_tdata  = sample_out[DATA_WIDTH-1:0];
    assign m_axis_tvalid = (state == S_OUTPUT);
    assign m_axis_tlast  = (state == S_OUTPUT) && (out_cnt == BEATS_PER_SAMPLE - 1) && out_last;
    assign m_axis_tuser  = out_user;

    integer i, t;
    reg signed [ACC_WIDTH-1:0] wide_acc;

    initial begin
        for (i = 0; i < NUM_TAPS; i = i + 1)
            delay_line[i] = 0;
    end

    always @(posedge clk) begin
        if (rst) begin
            state      <= S_ACCUMULATE;
            sample_in  <= 0;
            in_cnt     <= 0;
            in_last    <= 0;
            in_user    <= 0;
            sample_out <= 0;
            out_cnt    <= 0;
            out_last   <= 0;
            out_user   <= 0;
            for (i = 0; i < NUM_TAPS; i = i + 1)
                delay_line[i] <= 0;
        end else begin
            case (state)
            S_ACCUMULATE: begin
                if (s_axis_tvalid) begin
                    // Shift in DATA_WIDTH bits (LSB-first accumulation)
                    sample_in <= {s_axis_tdata, sample_in[SAMPLE_WIDTH-1:DATA_WIDTH]};
                    in_cnt    <= in_cnt + 1;

                    // Remember tlast and tuser from any beat
                    if (s_axis_tlast) in_last <= 1;
                    in_user <= s_axis_tuser;

                    // Last beat of this sample?
                    if (in_cnt == BEATS_PER_SAMPLE - 1) begin
                        // Full sample assembled — compute FIR
                        // The complete sample is {s_axis_tdata, sample_in[SW-1:DW]}
                        // Shift delay line
                        for (i = NUM_TAPS-1; i > 0; i = i - 1)
                            delay_line[i] <= delay_line[i-1];
                        delay_line[0] <= {s_axis_tdata, sample_in[SAMPLE_WIDTH-1:DATA_WIDTH]};

                        if (bypass) begin
                            sample_out <= {s_axis_tdata, sample_in[SAMPLE_WIDTH-1:DATA_WIDTH]};
                        end else begin
                            // FIR multiply-accumulate
                            wide_acc = 0;
                            // Current sample (tap 0)
                            wide_acc = wide_acc
                                + $signed({{(ACC_WIDTH-SAMPLE_WIDTH){s_axis_tdata[DATA_WIDTH-1]}},
                                           {s_axis_tdata, sample_in[SAMPLE_WIDTH-1:DATA_WIDTH]}})
                                * $signed({{(ACC_WIDTH-COEFF_WIDTH){coeffs[0][COEFF_WIDTH-1]}}, coeffs[0]});
                            // Previous samples (taps 1..NUM_TAPS-1)
                            for (t = 1; t < NUM_TAPS; t = t + 1) begin
                                wide_acc = wide_acc
                                    + $signed({{(ACC_WIDTH-SAMPLE_WIDTH){delay_line[t-1][SAMPLE_WIDTH-1]}}, delay_line[t-1]})
                                    * $signed({{(ACC_WIDTH-COEFF_WIDTH){coeffs[t][COEFF_WIDTH-1]}}, coeffs[t]});
                            end
                            sample_out <= wide_acc[SAMPLE_WIDTH-1:0];
                        end

                        in_cnt  <= 0;
                        out_cnt <= 0;
                        out_last <= in_last || s_axis_tlast;
                        out_user <= in_user;
                        in_last <= 0;
                        state   <= S_OUTPUT;
                    end
                end
            end

            S_OUTPUT: begin
                if (m_axis_tready) begin
                    // Shift out next DATA_WIDTH chunk
                    sample_out <= {{DATA_WIDTH{1'b0}}, sample_out[SAMPLE_WIDTH-1:DATA_WIDTH]};
                    out_cnt    <= out_cnt + 1;

                    if (out_cnt == BEATS_PER_SAMPLE - 1) begin
                        // Done outputting this sample
                        state <= S_ACCUMULATE;

                        // Clear delay line on packet boundary
                        if (out_last) begin
                            for (i = 0; i < NUM_TAPS; i = i + 1)
                                delay_line[i] <= 0;
                        end
                    end
                end
            end
            endcase
        end
    end

end
endgenerate

endmodule

`resetall
