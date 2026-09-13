## Artix-7 用 制約ファイルの例。ピン番号はボードに合わせて書き換える。
## 100 MHz 発振器
set_property -dict {PACKAGE_PIN R4 IOSTANDARD LVCMOS33} [get_ports clk100]
create_clock -period 10.000 -name clk100 [get_ports clk100]
set_property -dict {PACKAGE_PIN T6 IOSTANDARD LVCMOS33} [get_ports rst_n]

## ADV7513 ごとの出力ピン (例: OUT1)。hdmi_d[23:0], hdmi_clk[0], hdmi_de[0], hdmi_hs[0], hdmi_vs[0]
## 24 本のデータと CLK/DE/HS/VS は同じバンクにまとめ、CLK は ODDR で出すとタイミングが揃う。
# set_property -dict {PACKAGE_PIN xx IOSTANDARD LVCMOS33 SLEW FAST} [get_ports {hdmi_d[0]}]
# ...
# set_property -dict {PACKAGE_PIN xx IOSTANDARD LVCMOS33 SLEW FAST} [get_ports {hdmi_clk[0]}]

## ADV7513 のセットアップ/ホールド (データシート: tsu 1.0 ns, th 0.7 ns 程度、要確認) に対する出力遅延制約の例
# set_output_delay -clock [get_clocks -of_objects [get_pins ch0/u_clk/u_mmcm/CLKOUT0]] -max 1.0 [get_ports {hdmi_d[23:0] hdmi_de[0] hdmi_hs[0] hdmi_vs[0]}]
# set_output_delay -clock [get_clocks -of_objects [get_pins ch0/u_clk/u_mmcm/CLKOUT0]] -min -0.7 [get_ports {hdmi_d[23:0] hdmi_de[0] hdmi_hs[0] hdmi_vs[0]}]

## I2C (プルアップ 4.7 kΩ を基板側に実装)
# set_property -dict {PACKAGE_PIN xx IOSTANDARD LVCMOS33 PULLUP true} [get_ports {i2c_scl[0]}]
# set_property -dict {PACKAGE_PIN xx IOSTANDARD LVCMOS33 PULLUP true} [get_ports {i2c_sda[0]}]

## 4 本のピクセルクロックは互いに非同期。クロック間のタイミング解析を切る。
set_clock_groups -asynchronous \
  -group [get_clocks -of_objects [get_pins ch0/u_clk/u_mmcm/CLKOUT0]] \
  -group [get_clocks -of_objects [get_pins ch1/u_clk/u_mmcm/CLKOUT0]] \
  -group [get_clocks -of_objects [get_pins ch2/u_clk/u_mmcm/CLKOUT0]] \
  -group [get_clocks -of_objects [get_pins ch3/u_clk/u_mmcm/CLKOUT0]] \
  -group [get_clocks clk100]
