// ピクセルクロック生成 (Xilinx 7 シリーズ MMCME2_BASE)。100 MHz 入力。
// シミュレーション時は `define SIM で MMCM を使わず clk_in をそのまま返す。
module mmcm_pixclk #(
  parameter integer DIVCLK = 4,
  parameter real    MULT_F = 37.125,
  parameter real    DIV_F  = 6.25
)(
  input  wire clk_in,     // 100 MHz (BUFG 済み)
  input  wire rst,
  output wire clk_out,
  output wire locked
);
`ifdef SIM
  assign clk_out = clk_in;
  assign locked  = 1'b1;
`else
  wire clkfb, clk_unbuf;
  MMCME2_BASE #(
    .CLKIN1_PERIOD(10.0),
    .DIVCLK_DIVIDE(DIVCLK),
    .CLKFBOUT_MULT_F(MULT_F),
    .CLKOUT0_DIVIDE_F(DIV_F),
    .BANDWIDTH("OPTIMIZED")
  ) u_mmcm (
    .CLKIN1(clk_in), .CLKFBIN(clkfb), .CLKFBOUT(clkfb), .CLKFBOUTB(),
    .CLKOUT0(clk_unbuf), .CLKOUT0B(), .CLKOUT1(), .CLKOUT1B(), .CLKOUT2(), .CLKOUT2B(),
    .CLKOUT3(), .CLKOUT3B(), .CLKOUT4(), .CLKOUT5(), .CLKOUT6(),
    .LOCKED(locked), .PWRDWN(1'b0), .RST(rst)
  );
  BUFG u_bufg (.I(clk_unbuf), .O(clk_out));
`endif
endmodule
