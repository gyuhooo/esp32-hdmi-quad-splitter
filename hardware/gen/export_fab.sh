#!/usr/bin/env bash
# ガーバー / ドリル / 画像を書き出す (kicad-cli 7)。6 層: F, In1 (GND), In2/In3 (信号), In4 (電源), B
set -euo pipefail
cd "$(dirname "$0")/../quad_hdmi_tx"
rm -rf fab && mkdir -p fab/gerber
kicad-cli pcb export gerbers --layers "F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" \
  --subtract-soldermask --use-drill-file-origin -o fab/gerber/ quad_hdmi_tx.kicad_pcb
kicad-cli pcb export drill --format excellon --excellon-units mm --generate-map --map-format gerberx2 -o fab/gerber/ quad_hdmi_tx.kicad_pcb
kicad-cli pcb export pos --format csv --units mm --side both --use-drill-file-origin -o fab/cpl.csv quad_hdmi_tx.kicad_pcb
kicad-cli pcb export pdf --layers "F.Cu,F.SilkS,Edge.Cuts" -o fab/top.pdf quad_hdmi_tx.kicad_pcb
kicad-cli pcb export pdf --layers "B.Cu,B.SilkS,Edge.Cuts" --mirror -o fab/bottom.pdf quad_hdmi_tx.kicad_pcb
kicad-cli pcb export pdf --layers "In1.Cu,Edge.Cuts" -o fab/in1_gnd.pdf quad_hdmi_tx.kicad_pcb
kicad-cli pcb export pdf --layers "In2.Cu,Edge.Cuts" -o fab/in2_sig.pdf quad_hdmi_tx.kicad_pcb
kicad-cli pcb export pdf --layers "In3.Cu,Edge.Cuts" -o fab/in3_sig.pdf quad_hdmi_tx.kicad_pcb
kicad-cli pcb export pdf --layers "In4.Cu,Edge.Cuts" -o fab/in4_pwr.pdf quad_hdmi_tx.kicad_pcb
(cd fab/gerber && zip -q ../gerber.zip *)
ls fab fab/gerber | head -30
