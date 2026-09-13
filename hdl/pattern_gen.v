// テストパターン生成: カラーバー + 動くボックス + グラデーション + ラベル/カウンタ文字
// 出力は x,y,de 入力から 3 クロック遅延
module pattern_gen #(
  parameter H_ACTIVE = 1920,
  parameter V_ACTIVE = 1080,
  parameter [8*16-1:0] LABEL = "1080p 60        ",
  parameter [8*4-1:0]  OUT_NAME = "OUT1"
)(
  input  wire        clk,
  input  wire [11:0] x,
  input  wire [11:0] y,
  input  wire        de_in,
  input  wire        hs_in,
  input  wire        vs_in,
  input  wire [23:0] frames_bcd,
  input  wire [7:0]  tc_hh, tc_mm, tc_ss, tc_ff,
  output reg  [23:0] rgb,
  output reg         de_out,
  output reg         hs_out,
  output reg         vs_out
);
  localparam SCALE_SHIFT = (V_ACTIVE >= 1080) ? 2 : 1;   // 1080p: 4x, 720p/480p: 2x
  localparam BAR_W = H_ACTIVE / 8;
  localparam BOX   = V_ACTIVE / 12;

  // ---- 文字列を組み立てる ----
  function [7:0] dig; input [3:0] b; begin dig = 8'h30 + b; end endfunction

  wire [8*20-1:0] line1 = {OUT_NAME, " ", LABEL[127:8]};   // 4 + 1 + 15 = 20 文字
  wire [8*20-1:0] line2 = {"F", dig(frames_bcd[23:20]), dig(frames_bcd[19:16]), dig(frames_bcd[15:12]),
                           dig(frames_bcd[11:8]), dig(frames_bcd[7:4]), dig(frames_bcd[3:0]), " ",
                           dig(tc_hh[7:4]), dig(tc_hh[3:0]), ":", dig(tc_mm[7:4]), dig(tc_mm[3:0]), ":",
                           dig(tc_ss[7:4]), dig(tc_ss[3:0]), ":", dig(tc_ff[7:4]), dig(tc_ff[3:0]), " "};

  localparam TEXT_W = (8 * 20) << SCALE_SHIFT;
  localparam TEXT_H = 16 << SCALE_SHIFT;
  localparam TX = (H_ACTIVE - TEXT_W) / 2;
  localparam TY1 = V_ACTIVE / 10;
  localparam TY2 = V_ACTIVE * 8 / 10;

  wire t1_in, t1_on, t2_in, t2_on;
  text_overlay #(.LEN(20), .SCALE_SHIFT(SCALE_SHIFT), .X0(TX), .Y0(TY1)) u_t1
    (.clk(clk), .x(x), .y(y), .str(line1), .in_text(t1_in), .pixel_on(t1_on));
  text_overlay #(.LEN(20), .SCALE_SHIFT(SCALE_SHIFT), .X0(TX), .Y0(TY2)) u_t2
    (.clk(clk), .x(x), .y(y), .str(line2), .in_text(t2_in), .pixel_on(t2_on));

  // ---- 背景 (ステージ 1 で計算、ステージ 2 で文字と合成) ----
  // 動くボックス: フレーム番号下 2 桁で横に移動 (1 フレーム 1 ステップなのでコマ落ちが見える)
  wire [7:0]  step  = {1'b0, frames_bcd[7:4], 3'b0} + {2'b0, frames_bcd[7:4], 1'b0} + frames_bcd[3:0]; // 10*tens + ones = 0..99
  wire [11:0] box_x = step * ((H_ACTIVE - BOX) / 100);   // 定数乗算のみ

  // 下部グラデーション用 DDA (除算を使わず 0..255 を H_ACTIVE 画素に割り付ける)
  reg [7:0]  ramp = 0;
  reg [12:0] ramp_acc = 0;
  always @(posedge clk) begin
    if (x == 0) begin ramp <= 0; ramp_acc <= 0; end
    else if (ramp_acc + 13'd256 >= H_ACTIVE) begin ramp_acc <= ramp_acc + 13'd256 - H_ACTIVE; ramp <= ramp + 1'b1; end
    else ramp_acc <= ramp_acc + 13'd256;
  end

  reg [23:0] bg;
  reg        s1_de, s1_hs, s1_vs;
  always @(posedge clk) begin
    s1_de <= de_in; s1_hs <= hs_in; s1_vs <= vs_in;
    // 外枠 (1 ピクセル白): スケーリング/オーバースキャン検出用
    if (x == 0 || y == 0 || x == H_ACTIVE - 1 || y == V_ACTIVE - 1)
      bg <= 24'hFFFFFF;
    // 下部グラデーション
    else if (y >= V_ACTIVE - BOX)
      bg <= {ramp, ramp, ramp};
    // 動くボックス (中央帯)
    else if (y >= V_ACTIVE / 2 - BOX / 2 && y < V_ACTIVE / 2 + BOX / 2 && x >= box_x && x < box_x + BOX)
      bg <= 24'hFFFFFF;
    else begin
      // 75% カラーバー (白 黄 シアン 緑 マゼンタ 赤 青 黒)
      if      (x < 1 * BAR_W) bg <= 24'hC0C0C0;
      else if (x < 2 * BAR_W) bg <= 24'hC0C000;
      else if (x < 3 * BAR_W) bg <= 24'h00C0C0;
      else if (x < 4 * BAR_W) bg <= 24'h00C000;
      else if (x < 5 * BAR_W) bg <= 24'hC000C0;
      else if (x < 6 * BAR_W) bg <= 24'hC00000;
      else if (x < 7 * BAR_W) bg <= 24'h0000C0;
      else                    bg <= 24'h000000;
    end
  end

  // ---- 合成 (ステージ 2) ----
  reg [23:0] s2_bg;
  reg        s2_de, s2_hs, s2_vs;
  always @(posedge clk) begin
    s2_bg <= bg; s2_de <= s1_de; s2_hs <= s1_hs; s2_vs <= s1_vs;
  end
  always @(posedge clk) begin
    de_out <= s2_de; hs_out <= s2_hs; vs_out <= s2_vs;
    if (!s2_de)                 rgb <= 24'h000000;
    else if (t1_on || t2_on)    rgb <= 24'hFFFFFF;
    else if (t1_in || t2_in)    rgb <= {1'b0, s2_bg[23:17], 1'b0, s2_bg[15:9], 1'b0, s2_bg[7:1]}; // 半透明黒
    else                        rgb <= s2_bg;
  end
endmodule
