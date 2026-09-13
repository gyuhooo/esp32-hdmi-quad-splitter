// フレームカウンタ (6 桁 BCD) とタイムコード hh:mm:ss:ff (ノンドロップ)
module frame_counter #(
  parameter FPS = 60                 // 1 秒あたりのフレーム数 (29.97 は 30 を指定)
)(
  input  wire       clk,
  input  wire       rst,
  input  wire       frame_start,
  output reg [23:0] frames_bcd,      // 6 桁 BCD (上位から)
  output reg [7:0]  tc_hh, tc_mm, tc_ss, tc_ff   // 各 2 桁 BCD
);
  // BCD 桁を 1 つ進める。桁上げは呼び出し側で判断する。
  function [7:0] bcd_inc2; input [7:0] v; begin
    bcd_inc2 = (v[3:0] == 4'd9) ? {v[7:4] + 4'd1, 4'd0} : {v[7:4], v[3:0] + 4'd1};
  end endfunction

  localparam [7:0] FF_MAX = (FPS == 60) ? 8'h59 : 8'h29;

  always @(posedge clk) begin
    if (rst) begin
      frames_bcd <= 0; tc_hh <= 0; tc_mm <= 0; tc_ss <= 0; tc_ff <= 0;
    end else if (frame_start) begin
      // 6 桁フレーム番号
      if (frames_bcd[3:0] != 9)       frames_bcd[3:0]   <= frames_bcd[3:0] + 1;
      else begin frames_bcd[3:0] <= 0;
        if (frames_bcd[7:4] != 9)     frames_bcd[7:4]   <= frames_bcd[7:4] + 1;
        else begin frames_bcd[7:4] <= 0;
          if (frames_bcd[11:8] != 9)  frames_bcd[11:8]  <= frames_bcd[11:8] + 1;
          else begin frames_bcd[11:8] <= 0;
            if (frames_bcd[15:12] != 9) frames_bcd[15:12] <= frames_bcd[15:12] + 1;
            else begin frames_bcd[15:12] <= 0;
              if (frames_bcd[19:16] != 9) frames_bcd[19:16] <= frames_bcd[19:16] + 1;
              else begin frames_bcd[19:16] <= 0;
                frames_bcd[23:20] <= (frames_bcd[23:20] == 9) ? 4'd0 : frames_bcd[23:20] + 1;
              end
            end
          end
        end
      end
      // タイムコード
      if (tc_ff != FF_MAX) tc_ff <= bcd_inc2(tc_ff);
      else begin tc_ff <= 0;
        if (tc_ss != 8'h59) tc_ss <= bcd_inc2(tc_ss);
        else begin tc_ss <= 0;
          if (tc_mm != 8'h59) tc_mm <= bcd_inc2(tc_mm);
          else begin tc_mm <= 0;
            tc_hh <= (tc_hh == 8'h23) ? 8'h00 : bcd_inc2(tc_hh);
          end
        end
      end
    end
  end
endmodule
