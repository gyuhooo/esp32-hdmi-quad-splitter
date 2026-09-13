// 映像タイミング発生器 (プログレッシブ、セパレートシンク)
module video_timing #(
  parameter H_ACTIVE = 1920, H_FP = 88, H_SYNC = 44, H_BP = 148,
  parameter V_ACTIVE = 1080, V_FP = 4,  V_SYNC = 5,  V_BP = 36,
  parameter SYNC_POL = 1            // 1: 正極性, 0: 負極性
)(
  input  wire        clk,           // ピクセルクロック
  input  wire        rst,
  output reg  [11:0] x,             // アクティブ領域内座標 (de=1 のとき有効)
  output reg  [11:0] y,
  output reg         de,
  output reg         hs,
  output reg         vs,
  output reg         frame_start    // 各フレーム先頭で 1 クロック
);
  localparam H_TOTAL = H_ACTIVE + H_FP + H_SYNC + H_BP;
  localparam V_TOTAL = V_ACTIVE + V_FP + V_SYNC + V_BP;

  reg [11:0] hcnt = 0, vcnt = 0;

  always @(posedge clk) begin
    if (rst) begin
      hcnt <= 0; vcnt <= 0;
    end else begin
      if (hcnt == H_TOTAL - 1) begin
        hcnt <= 0;
        vcnt <= (vcnt == V_TOTAL - 1) ? 12'd0 : vcnt + 1'b1;
      end else
        hcnt <= hcnt + 1'b1;
    end
  end

  wire h_sync_raw = (hcnt >= H_ACTIVE + H_FP) && (hcnt < H_ACTIVE + H_FP + H_SYNC);
  wire v_sync_raw = (vcnt >= V_ACTIVE + V_FP) && (vcnt < V_ACTIVE + V_FP + V_SYNC);

  always @(posedge clk) begin
    de          <= (hcnt < H_ACTIVE) && (vcnt < V_ACTIVE);
    hs          <= SYNC_POL ? h_sync_raw : ~h_sync_raw;
    vs          <= SYNC_POL ? v_sync_raw : ~v_sync_raw;
    x           <= hcnt;
    y           <= vcnt;
    frame_start <= (hcnt == H_TOTAL - 1) && (vcnt == V_TOTAL - 1);   // 次クロックがフレーム先頭
  end
endmodule
