#!/usr/bin/env bash
# 簡易 3D モデル一式を作る: STEP (基板のみ)、board3d.json + OBJ/MTL、各層の白黒プロット、テクスチャ + three.js ビューア。
# 使い方: make_3d.sh [quad_hdmi_tx|fpga_main]   (Pillow/numpy 入りの python を PY で指定可: PY=venv/bin/python)
set -euo pipefail
P="${1:-quad_hdmi_tx}"
PY="${PY:-python3}"
cd "$(dirname "$0")/../$P"
mkdir -p 3d
kicad-cli pcb export step --subst-models -o "3d/$P.step" "$P.kicad_pcb" >/dev/null
PCB_PROJECT="$P" python3 ../gen/gen_3d.py
for L in F.Cu F.Mask F.SilkS B.Cu B.Mask B.SilkS Edge.Cuts; do
  kicad-cli pcb export pdf --layers "$L" --black-and-white -o "3d/lay_$L.pdf" "$P.kicad_pcb" >/dev/null
  pdftoppm -r 900 -png -singlefile "3d/lay_$L.pdf" "3d/lay_$L"
  rm -f "3d/lay_$L.pdf"
done
PCB_PROJECT="$P" "$PY" ../gen/make_3d_textures.py
ls -la 3d
