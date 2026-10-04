#!/usr/bin/env python3
"""簡易 3D モデルの生成 (2/2): 表裏のテクスチャ (レジスト緑 + 金パッド + 白シルク + 穴) と three.js の対話ビューア (HTML 1 枚)。
入力: 3d/board3d.json (gen_3d.py)、3d/lay_<layer>.png (kicad-cli で各層を白黒 PDF に出し pdftoppm -r 900 で変換したもの)
使い方: python make_3d_textures.py   (Pillow と numpy が要る。pcbnew は不要)
    for L in F.Cu F.Mask F.SilkS B.Cu B.Mask B.SilkS Edge.Cuts; do
      kicad-cli pcb export pdf --layers $L --black-and-white -o 3d/lay_$L.pdf quad_hdmi_tx.kicad_pcb; pdftoppm -r 900 -png -singlefile 3d/lay_$L.pdf 3d/lay_$L; done
"""
import os, json, base64, io
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
D3 = os.path.normpath(os.path.join(HERE, "..", "quad_hdmi_tx", "3d"))
data = json.load(open(os.path.join(D3, "board3d.json")))
BW, BH = data["board"]["w"], data["board"]["h"]
PPM = 20                                   # テクスチャの解像度 (px/mm)
TW, TH = int(round(BW * PPM)), int(round(BH * PPM))

def layer(name):
    """白黒プロット -> 描かれている所が True の配列 (基板外形で切り出し、PPM に合わせて縮小)"""
    im = Image.open(os.path.join(D3, f"lay_{name}.png")).convert("L")
    return im
edge = np.asarray(layer("Edge.Cuts")) < 128
ys, xs = np.where(edge)
bx0, bx1, by0, by1 = xs.min(), xs.max(), ys.min(), ys.max()       # 外形の線の外側 (0.1 mm 幅) を含む
def mask_of(name):
    im = layer(name).crop((bx0, by0, bx1 + 1, by1 + 1)).resize((TW, TH), Image.BOX)
    return np.asarray(im).astype(np.float32) / 255.0                  # 1 = 白 (何もない)、0 = 描画あり

def compose(side):
    cu = 1.0 - mask_of(f"{side}.Cu")          # 銅のある所 1
    opening = 1.0 - mask_of(f"{side}.Mask")   # レジスト開口 1
    silk = 1.0 - mask_of(f"{side}.SilkS")
    img = np.zeros((TH, TW, 3), np.float32)
    fr4, mask_cu, mask_bare = np.array([0x8c, 0x8a, 0x5a]) / 255, np.array([0x2e, 0x7d, 0x4f]) / 255, np.array([0x1f, 0x5c, 0x3a]) / 255
    gold, tin = np.array([0xd9, 0xb2, 0x5f]) / 255, np.array([0xc4, 0xc6, 0xc9]) / 255
    img[:] = mask_bare
    img = img * (1 - cu[..., None]) + mask_cu * cu[..., None]
    pad = opening * cu
    img = img * (1 - pad[..., None]) + gold * pad[..., None]
    bare = opening * (1 - cu)
    img = img * (1 - bare[..., None]) + fr4 * bare[..., None]
    s = silk * (1 - opening)
    img = img * (1 - s[..., None]) + np.array([0.96, 0.96, 0.94]) * s[..., None]
    out = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(out)
    for x, y, dx, dy in data["holes"]:
        r = max(dx, dy) / 2 * PPM
        d.ellipse((x * PPM - r, y * PPM - r, x * PPM + r, y * PPM + r), fill=(25, 25, 25))
    for x, y, dr in data["vias"]:
        r = dr / 2 * PPM
        d.ellipse((x * PPM - r, y * PPM - r, x * PPM + r, y * PPM + r), fill=(60, 50, 30))
    return out

top, bot = compose("F"), compose("B")
top.save(os.path.join(D3, "tex_top.png"), optimize=True); bot.save(os.path.join(D3, "tex_bot.png"), optimize=True)
print("textures", top.size, os.path.getsize(os.path.join(D3, "tex_top.png")), os.path.getsize(os.path.join(D3, "tex_bot.png")))

def datauri(im, q=80):
    buf = io.BytesIO(); im.convert("RGB").save(buf, "JPEG", quality=q, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
html = open(os.path.join(HERE, "viewer_template.html")).read()
html = html.replace("__BOARD_JSON__", json.dumps(data, separators=(",", ":"))).replace("__TEX_TOP__", datauri(top)).replace("__TEX_BOT__", datauri(bot))
open(os.path.join(D3, "viewer.html"), "w").write(html)
print("viewer.html", os.path.getsize(os.path.join(D3, "viewer.html")))
