// 8x16 フォントによる 1 行テキスト重畳。SCALE_SHIFT で 2^n 倍に拡大。
// 出力 pixel_on は入力座標に対して 2 クロック遅延する。
module text_overlay #(
  parameter LEN = 20,
  parameter SCALE_SHIFT = 2,         // 0:1x 1:2x 2:4x 3:8x
  parameter X0 = 0,
  parameter Y0 = 0
)(
  input  wire            clk,
  input  wire [11:0]     x,
  input  wire [11:0]     y,
  input  wire [8*LEN-1:0] str,       // str[8*LEN-1 -: 8] が先頭文字
  output reg             in_text,     // テキストボックス内 (2 クロック遅延)
  output reg             pixel_on    // 文字の前景ピクセル (2 クロック遅延)
);
  reg [7:0] font [0:4095];
  initial $readmemh("font8x16.mem", font);

  localparam BOX_W = (8 * LEN) << SCALE_SHIFT;
  localparam BOX_H = 16 << SCALE_SHIFT;

  wire        in_box = (x >= X0) && (x < X0 + BOX_W) && (y >= Y0) && (y < Y0 + BOX_H);
  wire [11:0] cx = (x - X0) >> SCALE_SHIFT;
  wire [11:0] cy = (y - Y0) >> SCALE_SHIFT;
  wire [7:0]  char_idx = cx[11:3];
  wire [2:0]  col = cx[2:0];
  wire [3:0]  row = cy[3:0];

  // ステージ 1: 文字コードを取り出す
  reg        s1_in_box;
  reg [7:0]  s1_code;
  reg [2:0]  s1_col;
  reg [3:0]  s1_row;
  always @(posedge clk) begin
    s1_in_box <= in_box;
    s1_code   <= in_box ? str[8*(LEN-1-char_idx) +: 8] : 8'h20;
    s1_col    <= col;
    s1_row    <= row;
  end

  // ステージ 2: フォント ROM 参照
  reg [7:0] s2_line;
  reg [2:0] s2_col;
  always @(posedge clk) begin
    s2_line <= font[{s1_code, s1_row}];
    s2_col  <= s1_col;
    in_text  <= s1_in_box;
  end

  always @* pixel_on = in_text & s2_line[3'd7 - s2_col];
endmodule
