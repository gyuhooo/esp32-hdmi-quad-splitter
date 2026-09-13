// 1 出力分: ピクセルクロック + タイミング + カウンタ + パターン -> ADV7513 の 24bit RGB バス
module hdmi_channel #(
  parameter integer MODE = 0,
  parameter [8*4-1:0] OUT_NAME = "OUT1"
)(
  input  wire        clk100,
  input  wire        rst,
  output wire        pix_clk,      // ADV7513 CLK
  output wire [23:0] pix_rgb,      // D[23:0] (R=D[23:16] G=D[15:8] B=D[7:0]、入力 ID 0)
  output wire        pix_de,
  output wire        pix_hs,
  output wire        pix_vs,
  output wire        locked
);
`include "video_modes.vh"
  localparam H_ACTIVE = mode_h_active(MODE), H_FP = mode_h_fp(MODE), H_SYNC = mode_h_sync(MODE), H_BP = mode_h_bp(MODE);
  localparam V_ACTIVE = mode_v_active(MODE), V_FP = mode_v_fp(MODE), V_SYNC = mode_v_sync(MODE), V_BP = mode_v_bp(MODE);
  localparam SYNC_POL = mode_sync_pol(MODE);
  localparam FPS      = mode_fps_int(MODE);
  localparam [8*16-1:0] LABEL = mode_label(MODE);

  mmcm_pixclk #(.DIVCLK(mode_mmcm_divclk(MODE)), .MULT_F(mode_mmcm_mult(MODE)), .DIV_F(mode_mmcm_div(MODE)))
    u_clk (.clk_in(clk100), .rst(rst), .clk_out(pix_clk), .locked(locked));

  // ピクセルクロック域のリセット (locked 後に解除)
  reg [3:0] rst_sync = 4'hF;
  always @(posedge pix_clk or negedge locked)
    if (!locked) rst_sync <= 4'hF; else rst_sync <= {rst_sync[2:0], 1'b0};
  wire prst = rst_sync[3];

  wire [11:0] x, y;
  wire de, hs, vs, frame_start;
  video_timing #(.H_ACTIVE(H_ACTIVE), .H_FP(H_FP), .H_SYNC(H_SYNC), .H_BP(H_BP),
                 .V_ACTIVE(V_ACTIVE), .V_FP(V_FP), .V_SYNC(V_SYNC), .V_BP(V_BP), .SYNC_POL(SYNC_POL))
    u_timing (.clk(pix_clk), .rst(prst), .x(x), .y(y), .de(de), .hs(hs), .vs(vs), .frame_start(frame_start));

  wire [23:0] frames_bcd;
  wire [7:0]  tc_hh, tc_mm, tc_ss, tc_ff;
  frame_counter #(.FPS(FPS)) u_cnt (.clk(pix_clk), .rst(prst), .frame_start(frame_start),
    .frames_bcd(frames_bcd), .tc_hh(tc_hh), .tc_mm(tc_mm), .tc_ss(tc_ss), .tc_ff(tc_ff));

  pattern_gen #(.H_ACTIVE(H_ACTIVE), .V_ACTIVE(V_ACTIVE), .LABEL(LABEL), .OUT_NAME(OUT_NAME))
    u_pat (.clk(pix_clk), .x(x), .y(y), .de_in(de), .hs_in(hs), .vs_in(vs),
           .frames_bcd(frames_bcd), .tc_hh(tc_hh), .tc_mm(tc_mm), .tc_ss(tc_ss), .tc_ff(tc_ff),
           .rgb(pix_rgb), .de_out(pix_de), .hs_out(pix_hs), .vs_out(pix_vs));
endmodule
