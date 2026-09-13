// 書き込み専用の簡易 I2C マスタ (7bit アドレス、レジスタ 1 バイト + データ 1 バイト)
// SCL は sys_clk / (4 * CLK_DIV)。100 MHz, CLK_DIV=250 で 100 kHz。
module i2c_master #(
  parameter CLK_DIV = 250
)(
  input  wire       clk,
  input  wire       rst,
  input  wire       start,        // 1 クロックのパルスで書き込み開始 (busy=0 のとき)
  input  wire [6:0] dev_addr,
  input  wire [7:0] reg_addr,
  input  wire [7:0] data,
  output reg        busy,
  output reg        ack_error,    // いずれかの ACK が返らなかった
  inout  wire       scl,
  inout  wire       sda
);
  reg scl_o = 1, sda_o = 1;
  assign scl = scl_o ? 1'bz : 1'b0;
  assign sda = sda_o ? 1'bz : 1'b0;

  reg [15:0] div = 0;
  reg [1:0]  phase = 0;           // 1 ビットを 4 フェーズで送る
  wire tick = (div == CLK_DIV - 1);
  always @(posedge clk) div <= (rst || tick) ? 16'd0 : div + 1'b1;

  localparam S_IDLE = 0, S_START = 1, S_BIT = 2, S_ACK = 3, S_STOP = 4;
  reg [2:0]  state = S_IDLE;
  reg [1:0]  byte_idx;            // 0: addr, 1: reg, 2: data
  reg [2:0]  bit_idx;
  reg [7:0]  shift;
  reg [23:0] packet;

  always @(posedge clk) begin
    if (rst) begin
      state <= S_IDLE; busy <= 0; scl_o <= 1; sda_o <= 1; phase <= 0; ack_error <= 0;
    end else begin
      if (state == S_IDLE) begin
        if (start) begin
          packet <= {dev_addr, 1'b0, reg_addr, data};
          busy <= 1; ack_error <= 0; state <= S_START; phase <= 0;
        end
      end else if (tick) begin
        phase <= phase + 1'b1;
        case (state)
          S_START: case (phase)      // SCL=1 のまま SDA を落とす
            0: sda_o <= 1;
            1: sda_o <= 0;
            3: begin scl_o <= 0; byte_idx <= 0; bit_idx <= 7; shift <= packet[23:16]; state <= S_BIT; end
          endcase
          S_BIT: case (phase)
            0: sda_o <= shift[bit_idx];
            1: scl_o <= 1;
            3: begin scl_o <= 0;
                 if (bit_idx == 0) state <= S_ACK; else bit_idx <= bit_idx - 1'b1; end
          endcase
          S_ACK: case (phase)
            0: sda_o <= 1;           // 解放してスレーブの ACK を待つ
            1: scl_o <= 1;
            2: if (sda !== 1'b0) ack_error <= 1;
            3: begin scl_o <= 0;
                 if (byte_idx == 2) state <= S_STOP;
                 else begin
                   byte_idx <= byte_idx + 1'b1; bit_idx <= 7;
                   shift <= (byte_idx == 0) ? packet[15:8] : packet[7:0];
                   state <= S_BIT;
                 end
               end
          endcase
          S_STOP: case (phase)
            0: sda_o <= 0;
            1: scl_o <= 1;
            2: sda_o <= 1;
            3: begin state <= S_IDLE; busy <= 0; end
          endcase
        endcase
      end
    end
  end
endmodule
