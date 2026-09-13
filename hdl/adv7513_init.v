// ADV7513 初期化シーケンサ。電源投入後と HPD 立ち上がり後に設定テーブルを書き込む。
// レジスタ値は ADI "ADV7513 Programming Guide" のクイックスタート (24bit RGB 4:4:4 入力 -> HDMI) に基づく。
module adv7513_init #(
  parameter SYS_CLK_HZ = 100_000_000,
  parameter [6:0] I2C_ADDR = 7'h39,      // PD/AD ピン Low: 0x39 (8bit 0x72) / High: 0x3D (0x7A)
  parameter ASPECT_16_9 = 1
)(
  input  wire clk,
  input  wire rst,
  input  wire hpd,                       // ADV7513 の HPD 出力 (または常時 1)
  input  wire enable,                    // 同一 I2C バスの前段が完了してから 1 にする
  output reg  done,
  output wire error,
  inout  wire scl,
  inout  wire sda
);
  localparam N = 19;
  function [15:0] tbl; input integer i; begin
    case (i)
      0:  tbl = 16'h41_10;   // パワーアップ
      1:  tbl = 16'h98_03;   // 以下 固定値 (必須)
      2:  tbl = 16'h9A_E0;
      3:  tbl = 16'h9C_30;
      4:  tbl = 16'h9D_61;
      5:  tbl = 16'hA2_A4;
      6:  tbl = 16'hA3_A4;
      7:  tbl = 16'hE0_D0;
      8:  tbl = 16'hF9_00;
      9:  tbl = 16'h15_00;   // 入力 ID 0: 24bit RGB 4:4:4 セパレートシンク
      10: tbl = 16'h16_30;   // 出力 4:4:4、色深度 8bit
      11: tbl = ASPECT_16_9 ? 16'h17_02 : 16'h17_00;  // アスペクト比
      12: tbl = 16'h18_46;   // CSC 無効
      13: tbl = 16'hAF_06;   // HDMI モード、HDCP 無効
      14: tbl = 16'h4C_04;   // GC パケット 色深度 8bit
      15: tbl = 16'h40_80;   // GC パケット有効
      16: tbl = 16'h55_10;   // AVI InfoFrame: RGB、アクティブフォーマット有効
      17: tbl = ASPECT_16_9 ? 16'h56_28 : 16'h56_18;  // AVI: 画角 16:9 / 4:3
      18: tbl = 16'hD6_C0;   // HPD を強制 High (モニタ未接続でも出力を続ける)
      default: tbl = 16'h00_00;
    endcase
  end endfunction

  // HPD 立ち上がりから 250 ms 待ってから書き込む
  localparam WAIT = SYS_CLK_HZ / 4;
  reg [27:0] wait_cnt = 0;
  reg        hpd_d = 0, run = 0;
  reg [4:0]  idx = 0;
  reg        start = 0;
  wire       busy, ack_error;
  reg        err = 0;
  assign error = err;

  wire [15:0] entry = tbl(idx);
  i2c_master u_i2c (.clk(clk), .rst(rst), .start(start), .dev_addr(I2C_ADDR),
                    .reg_addr(entry[15:8]), .data(entry[7:0]),
                    .busy(busy), .ack_error(ack_error), .scl(scl), .sda(sda));

  localparam S_WAIT = 0, S_WRITE = 1, S_BUSY = 2, S_DONE = 3;
  reg [1:0] state = S_WAIT;

  always @(posedge clk) begin
    hpd_d <= hpd;
    start <= 0;
    if (rst) begin
      state <= S_WAIT; wait_cnt <= 0; idx <= 0; done <= 0; err <= 0;
    end else begin
      if (hpd && !hpd_d) begin           // HPD 立ち上がりで再初期化
        state <= S_WAIT; wait_cnt <= 0; idx <= 0; done <= 0; err <= 0;
      end
      case (state)
        S_WAIT:  if (wait_cnt == WAIT) begin if (enable) state <= S_WRITE; end else wait_cnt <= wait_cnt + 1'b1;
        S_WRITE: begin start <= 1; state <= S_BUSY; end
        S_BUSY:  if (!busy && !start) begin
                   if (ack_error) err <= 1;
                   if (idx == N - 1) begin state <= S_DONE; done <= 1; end
                   else begin idx <= idx + 1'b1; state <= S_WRITE; end
                 end
        S_DONE:  ;
      endcase
    end
  end
endmodule
