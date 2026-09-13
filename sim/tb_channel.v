// hdmi_channel を 1 本シミュレーションし、FRAME 番目のフレームを PPM に書き出す
`timescale 1ns/1ps
module tb_channel;
  parameter integer MODE  = 9;      // 既定: 480p 59.94 (フレームが小さい)
  parameter integer FRAME = 2;      // 何フレーム目を保存するか (0 始まり)
  parameter         OUT   = "frame.ppm";

  reg clk = 0;
  always #5 clk = ~clk;             // SIM では MMCM をバイパスするので周波数は任意
  reg rst = 1;

  wire        pix_clk, de, hs, vs, locked;
  wire [23:0] rgb;
  hdmi_channel #(.MODE(MODE), .OUT_NAME("OUT1")) dut (.clk100(clk), .rst(rst), .pix_clk(pix_clk),
    .pix_rgb(rgb), .pix_de(de), .pix_hs(hs), .pix_vs(vs), .locked(locked));

  integer fd, frame = -1, px = 0, w = 0, h = 0, lines = 0;
  reg vs_d = 0, de_d = 0;
  wire vs_active = (dut.SYNC_POL) ? vs : ~vs;
  initial begin
    #100 rst = 0;
    fd = $fopen(OUT, "w");
    $fwrite(fd, "P6\n%0d %0d\n255\n", dut.H_ACTIVE, dut.V_ACTIVE);
  end
  always @(posedge pix_clk) begin
    vs_d <= vs_active; de_d <= de;
    if (vs_active && !vs_d) begin
      frame = frame + 1;
      if (frame > FRAME) begin
        $fclose(fd);
        $display("saved %s: frame %0d, %0dx%0d, %0d active lines, counter=%h tc=%h:%h:%h:%h",
                 OUT, FRAME, dut.H_ACTIVE, dut.V_ACTIVE, lines,
                 dut.frames_bcd, dut.tc_hh, dut.tc_mm, dut.tc_ss, dut.tc_ff);
        $finish;
      end
    end
    if (frame == FRAME && de) begin
      $fwrite(fd, "%c%c%c", rgb[23:16], rgb[15:8], rgb[7:0]);
      px = px + 1;
    end
    if (frame == FRAME && de_d && !de) lines = lines + 1;
  end
endmodule
