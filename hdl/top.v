// 4 出力 HDMI テストパターン発生器 トップ (Artix-7 + ADV7513 x4)
// 各出力のモードは MODE0..3 パラメータで決める (video_modes.vh 参照)。
module top #(
  parameter integer MODE0 = 1,    // OUT1: 1080p 59.94
  parameter integer MODE1 = 0,    // OUT2: 1080p 60
  parameter integer MODE2 = 5,    // OUT3: 720p 59.94
  parameter integer MODE3 = 9     // OUT4: 480p 59.94
)(
  input  wire        clk100,      // 100 MHz 発振器
  input  wire        rst_n,       // 押しボタン等 (Low でリセット)
  // ADV7513 x4 (パラレル RGB)
  output wire [3:0]  hdmi_clk,
  output wire [95:0] hdmi_d,      // [23:0]=OUT1 ... [95:72]=OUT4
  output wire [3:0]  hdmi_de,
  output wire [3:0]  hdmi_hs,
  output wire [3:0]  hdmi_vs,
  input  wire [3:0]  hdmi_hpd,    // TPD12S016 HPD_A (ADV7513 HPD と共通、3.3 V)
  input  wire [3:0]  hdmi_int,    // ADV7513 INT (現状未使用)
  // I2C: 2 バス x 2 デバイス (アドレス 0x39 / 0x3D)
  inout  wire [1:0]  i2c_scl,
  inout  wire [1:0]  i2c_sda,
  output wire [3:0]  led           // 各出力の初期化完了
);
  wire rst = ~rst_n;

  wire [3:0] locked;
  hdmi_channel #(.MODE(MODE0), .OUT_NAME("OUT1")) ch0 (.clk100(clk100), .rst(rst), .pix_clk(hdmi_clk[0]),
    .pix_rgb(hdmi_d[23:0]),  .pix_de(hdmi_de[0]), .pix_hs(hdmi_hs[0]), .pix_vs(hdmi_vs[0]), .locked(locked[0]));
  hdmi_channel #(.MODE(MODE1), .OUT_NAME("OUT2")) ch1 (.clk100(clk100), .rst(rst), .pix_clk(hdmi_clk[1]),
    .pix_rgb(hdmi_d[47:24]), .pix_de(hdmi_de[1]), .pix_hs(hdmi_hs[1]), .pix_vs(hdmi_vs[1]), .locked(locked[1]));
  hdmi_channel #(.MODE(MODE2), .OUT_NAME("OUT3")) ch2 (.clk100(clk100), .rst(rst), .pix_clk(hdmi_clk[2]),
    .pix_rgb(hdmi_d[71:48]), .pix_de(hdmi_de[2]), .pix_hs(hdmi_hs[2]), .pix_vs(hdmi_vs[2]), .locked(locked[2]));
  hdmi_channel #(.MODE(MODE3), .OUT_NAME("OUT4")) ch3 (.clk100(clk100), .rst(rst), .pix_clk(hdmi_clk[3]),
    .pix_rgb(hdmi_d[95:72]), .pix_de(hdmi_de[3]), .pix_hs(hdmi_hs[3]), .pix_vs(hdmi_vs[3]), .locked(locked[3]));

  // ADV7513 初期化 (バス 0: OUT1=0x39, OUT2=0x3D / バス 1: OUT3=0x39, OUT4=0x3D)
  wire [3:0] done, err;
  // 同一バス上の 2 台は衝突しないよう直列に初期化する (後段は前段の done を待つ)
  adv7513_init #(.I2C_ADDR(7'h39), .ASPECT_16_9(MODE0 < 8)) i0 (.clk(clk100), .rst(rst), .hpd(hdmi_hpd[0]),
    .enable(1'b1),    .done(done[0]), .error(err[0]), .scl(i2c_scl[0]), .sda(i2c_sda[0]));
  adv7513_init #(.I2C_ADDR(7'h3D), .ASPECT_16_9(MODE1 < 8)) i1 (.clk(clk100), .rst(rst), .hpd(hdmi_hpd[1]),
    .enable(done[0]), .done(done[1]), .error(err[1]), .scl(i2c_scl[0]), .sda(i2c_sda[0]));
  adv7513_init #(.I2C_ADDR(7'h39), .ASPECT_16_9(MODE2 < 8)) i2 (.clk(clk100), .rst(rst), .hpd(hdmi_hpd[2]),
    .enable(1'b1),    .done(done[2]), .error(err[2]), .scl(i2c_scl[1]), .sda(i2c_sda[1]));
  adv7513_init #(.I2C_ADDR(7'h3D), .ASPECT_16_9(MODE3 < 8)) i3 (.clk(clk100), .rst(rst), .hpd(hdmi_hpd[3]),
    .enable(done[2]), .done(done[3]), .error(err[3]), .scl(i2c_scl[1]), .sda(i2c_sda[1]));

  assign led = done & ~err & locked;
endmodule
