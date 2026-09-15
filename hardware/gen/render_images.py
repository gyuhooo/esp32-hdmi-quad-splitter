#!/usr/bin/env python3
"""fab/*.pdf (export_fab.sh の出力) を docs/images/pcb-*.png に変換する。
使い方: (venv に Pillow を入れて) python3 render_images.py
"""
import os, subprocess, sys
from PIL import Image, ImageChops
HERE = os.path.dirname(os.path.abspath(__file__))
FAB = os.path.join(HERE, "..", "quad_hdmi_tx", "fab")
IMG = os.path.join(HERE, "..", "..", "docs", "images")
TMP = os.environ.get("TMPDIR", "/tmp")
for name in ("top", "bottom", "in1_gnd", "in2_pwr"):
    pdf = os.path.join(FAB, f"{name}.pdf")
    if not os.path.exists(pdf):
        sys.exit(f"missing {pdf}; run export_fab.sh first")
    base = os.path.join(TMP, f"render_{name}")
    subprocess.run(["pdftoppm", "-r", "150", "-png", "-singlefile", pdf, base], check=True)
    im = Image.open(base + ".png").convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    bbox = ImageChops.difference(im, bg).getbbox()
    if bbox:
        pad = 10
        bbox = (max(0, bbox[0] - pad), max(0, bbox[1] - pad), min(im.width, bbox[2] + pad), min(im.height, bbox[3] + pad))
        im = im.crop(bbox)
    out = os.path.join(IMG, f"pcb-{name}.png")
    im.save(out, optimize=True)
    print(out, im.size)
