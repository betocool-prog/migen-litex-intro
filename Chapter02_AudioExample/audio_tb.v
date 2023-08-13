// audio_tb.v

`timescale 1 ns/10 ps  // time-unit = 1 ns, precision = 10 ps

module audio_tb;

    reg           clk1000;
    reg           cpu_reset0;
    wire          user_led0;
    wire          user_led1;
    wire          user_led2;
    wire          i2s_tx0_clk;
    wire          i2s_tx0_sync;
    wire          i2s_tx0_tx;
    wire          i2s_tx_mclk0;

    top UUT (.clk1000(clk1000), .cpu_reset0(cpu_reset0), .user_led0(user_led0), .user_led1(user_led1), .user_led2(user_led2),
            .i2s_tx0_clk(i2s_tx0_clk), .i2s_tx0_sync(i2s_tx0_sync), .i2s_tx0_tx(i2s_tx0_tx), .i2s_tx_mclk0(i2s_tx_mclk0));
    
    initial // initial block executes only once
        begin
            cpu_reset0 = 0;
            #200
            cpu_reset0 = 1;
        end

    always 
        begin
            clk1000 = 1'b0; 
            #5; // high for 10 * timescale = 10 ns

            clk1000 = 1'b1;
            #5; // low for 10 * timescale = 10 ns
        end
    
endmodule