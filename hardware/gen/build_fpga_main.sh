#!/bin/sh
# FPGA メイン基板の生成チェーン: 回路図 -> ネットリスト -> 基板 (配置 + BGA ファンアウト) -> ゾーン塗り + 配線前 DRC
set -e
cd "$(dirname "$0")"
python3 gen_fpga_schematic.py
(cd ../fpga_main && kicad-cli sch export netlist -o netlist.net fpga_main.kicad_sch)
python3 gen_fpga_pcb.py
python3 pcb_drc.py ../fpga_main/fpga_main.kicad_pcb ../fpga_main/drc_pre.rpt "$@"
