#!/usr/bin/env python3
"""8x16 ビットマップフォント (ASCII 0x20-0x7E) を TTF から生成し、
Verilog $readmemh 用の hdl/font8x16.mem を出力する。

使い方: tools/make-font.py [TTF パス]
"""
import sys
from PIL import Image, ImageDraw, ImageFont

ttf = sys.argv[1] if len(sys.argv) > 1 else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
W, H = 8, 16
font = ImageFont.truetype(ttf, 15)
lines = []
for code in range(256):
    img = Image.new("L", (W, H), 0)
    if 0x20 <= code <= 0x7E:
        d = ImageDraw.Draw(img)
        d.text((0, -2), chr(code), font=font, fill=255)
    for y in range(H):
        bits = 0
        for x in range(W):
            if img.getpixel((x, y)) > 96:
                bits |= 0x80 >> x
        lines.append(f"{bits:02x}")
with open("hdl/font8x16.mem", "w") as f:
    f.write("\n".join(lines) + "\n")
print(f"hdl/font8x16.mem: {len(lines)} lines")
