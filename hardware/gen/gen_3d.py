#!/usr/bin/env python3
"""簡易 3D モデルの生成 (1/2): 基板データ -> quad_hdmi_tx/3d/board3d.json と Wavefront OBJ/MTL。
KiCad の 3D モデルライブラリが無い環境でも部品の外形が分かるよう、パッケージ種別ごとの寸法表で部品を直方体に置き換える。
テクスチャ (銅箔・レジスト・シルク) と three.js ビューアは make_3d_textures.py (Pillow) が作る。
使い方: python3 gen_3d.py   (pcbnew の Python が必要)
"""
import os, json, math
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "quad_hdmi_tx"))
D3 = os.path.join(OUT, "3d")
os.makedirs(D3, exist_ok=True)
board = pcbnew.LoadBoard(os.path.join(OUT, "quad_hdmi_tx.kicad_pcb"))
THICK = board.GetDesignSettings().GetBoardThickness() / 1e6

# パッケージ寸法表: footprint 名の部分一致 -> (本体 長さ (footprint の x 方向), 幅, 高さ, 種別)
# 種別: ic (黒)、cap (茶)、res (黒、端子銀)、ind (灰)、led (黄)、conn (金属)、hdr (黒樹脂 + ピン)、ldo (黒 + タブ)
PKG = [
    ("LQFP-64", (10.0, 10.0, 1.6, "ic")), ("TSSOP-24", (7.8, 4.4, 1.1, "ic")), ("TSOT-23-6", (2.9, 1.6, 1.0, "ic")),
    ("SOT-223", (6.5, 3.5, 1.6, "ldo")), ("C_0402", (1.0, 0.5, 0.5, "cap")), ("R_0402", (1.0, 0.5, 0.4, "res")),
    ("C_0603", (1.6, 0.8, 0.8, "cap")), ("L_0603", (1.6, 0.8, 0.8, "ind")), ("LED_0603", (1.6, 0.8, 0.6, "led")),
    ("C_0805", (2.0, 1.25, 1.25, "cap")), ("Fuse_1206", (3.2, 1.6, 0.9, "res")), ("NR-40xx", (4.0, 4.0, 1.8, "ind")),
    ("HDMI_A", (None, None, 6.3, "conn")), ("USB_C", (None, None, 3.3, "conn")),
    ("PinHeader_2x40", (101.6, 5.08, 2.54, "hdr")), ("PinHeader_1x02", (5.08, 2.54, 2.54, "hdr")),
]
COLORS = {"ic": "1c1c1e", "cap": "b48a5a", "res": "262626", "ind": "6d6d70", "led": "e8d26a", "conn": "c8c9cc", "hdr": "1a1a1a", "ldo": "1c1c1e",
          "lead": "cfcfcf", "pin": "d4b25a", "fr4": "2f6b45"}

def classify(name):
    for key, spec in PKG:
        if key in name:
            return spec
    return None

parts, holes = [], []
for fp in board.GetFootprints():
    name = str(fp.GetFPID().GetLibItemName())
    x, y, rot, flipped = fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6, fp.GetOrientationDegrees(), fp.IsFlipped()
    for p in fp.Pads():
        if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) and p.GetDrillSize().x > 0:
            holes.append([round(p.GetPosition().x / 1e6, 3), round(p.GetPosition().y / 1e6, 3), round(p.GetDrillSize().x / 1e6, 2), round(p.GetDrillSize().y / 1e6, 2)])
    spec = classify(name)
    if not spec:
        continue
    L, W, H, kind = spec
    cy = fp.GetCourtyard(pcbnew.B_CrtYd if flipped else pcbnew.F_CrtYd)
    cb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False, False)
    if L is None:                                   # コネクタ: コートヤードの外形をそのまま本体に
        cxp, cyp = cb.GetCenter().x / 1e6, cb.GetCenter().y / 1e6
        w, d = cb.GetWidth() / 1e6 - 0.3, cb.GetHeight() / 1e6 - 0.3
    elif kind == "hdr":                             # ピンヘッダ: パッドの格子から本体 (ピン数 x 2.54) を決める (回転・原点位置に依らない)
        xs = sorted(set(round(p.GetPosition().x / 1e6, 2) for p in fp.Pads())); ys = sorted(set(round(p.GetPosition().y / 1e6, 2) for p in fp.Pads()))
        cxp, cyp = (xs[0] + xs[-1]) / 2, (ys[0] + ys[-1]) / 2
        if len(xs) >= len(ys):
            w, d = xs[-1] - xs[0] + 2.54, 2.54 * min(len(ys), 2)
        else:
            w, d = 2.54 * min(len(xs), 2), ys[-1] - ys[0] + 2.54
    else:
        cxp, cyp = x, y
        w, d = (L, W) if abs(math.sin(math.radians(rot))) < 0.5 else (W, L)
    part = {"ref": fp.GetReference(), "fp": name, "kind": kind, "x": round(cxp, 3), "y": round(cyp, 3), "w": round(w, 3), "d": round(d, 3), "h": H, "side": "B" if flipped else "F"}
    if kind == "hdr":                               # ピン: 各パッドの列 x と、本体中心から ±1.27 の行
        rows = sorted(set(round(p.GetPosition().y / 1e6, 2) for p in fp.Pads()))
        cols = sorted(set(round(p.GetPosition().x / 1e6, 2) for p in fp.Pads()))
        if len(rows) == 2 and abs(rows[1] - rows[0]) > 3:         # SMD 2 列: パッドは本体の外、ピンは本体の中 (行間 2.54)
            rows = [cyp - 1.27, cyp + 1.27]
        if len(cols) == 2 and abs(cols[1] - cols[0]) > 3:
            cols = [cxp - 1.27, cxp + 1.27]
        part["pins"] = [[c, r] for c in cols for r in rows]
        part["pin_h"] = 8.5
    if kind in ("cap", "res", "ind", "led"):
        part["ends"] = 0.3 if L >= 1.6 else 0.2    # 端子 (銀) の長さ
    if kind == "ic":
        part["lead"] = 0.75 if "LQFP" in name else 0.65 if "TSSOP" in name else 0.5
    parts.append(part)
vias = [[round(t.GetPosition().x / 1e6, 3), round(t.GetPosition().y / 1e6, 3), round(t.GetDrill() / 1e6, 2)] for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
eb = board.GetBoardEdgesBoundingBox()
data = {"board": {"x": 0.0, "y": 0.0, "w": round(eb.GetWidth() / 1e6 - 0.1, 2), "h": round(eb.GetHeight() / 1e6 - 0.1, 2), "t": THICK},
        "colors": COLORS, "parts": parts, "holes": holes, "vias": vias}
json.dump(data, open(os.path.join(D3, "board3d.json"), "w"))
print("parts:", len(parts), "holes:", len(holes), "vias:", len(vias), "board:", data["board"])

# ---------------------------------------------------------------- OBJ / MTL (y が上、KiCad の y は +z へ: 右手系)
V, VT, VN, F = [], [], [], {}
def box(x0, x1, y0, y1, z0, z1, mat, uv=None):
    """x: 基板 x、y: 高さ (上向き)、z: 基板 y (奥行き)。uv を渡した面 (上/下) にはテクスチャ座標を付ける"""
    base = len(V)
    corners = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    V.extend(corners)
    faces = [((0, 1, 2, 3), (0, 0, 1)), ((5, 4, 7, 6), (0, 0, -1)), ((4, 0, 3, 7), (-1, 0, 0)), ((1, 5, 6, 2), (1, 0, 0)), ((3, 2, 6, 7), (0, 1, 0)), ((4, 5, 1, 0), (0, -1, 0))]
    for idx, n in faces:
        VN.append(n); ni = len(VN)
        if uv and n[1] != 0:
            # 上面/下面: u = x / W、v = 1 - (基板 y) / H  (基板 y = z)
            tex = []
            for i in idx:
                vx, vy, vz = corners[i]
                VT.append((vx / uv[0], 1.0 - vz / uv[1])); tex.append(len(VT))
            F.setdefault(mat, []).append([(base + i + 1, t, ni) for i, t in zip(idx, tex)])
        else:
            F.setdefault(mat, []).append([(base + i + 1, 0, ni) for i in idx])
W, Hb, T = data["board"]["w"], data["board"]["h"], THICK
box(0, W, -T / 2, T / 2, 0, Hb, "board", uv=(W, Hb))
for p in parts:
    x0, x1 = p["x"] - p["w"] / 2, p["x"] + p["w"] / 2
    z0, z1 = p["y"] - p["d"] / 2, p["y"] + p["d"] / 2
    top, sign = (T / 2, 1) if p["side"] == "F" else (-T / 2, -1)
    def up(a, b):
        return (min(top + sign * a, top + sign * b), max(top + sign * a, top + sign * b))
    y0, y1 = up(0.05, p["h"])
    box(x0, x1, y0, y1, z0, z1, p["kind"])
    if "ends" in p:
        e = p["ends"]
        along_x = p["w"] >= p["d"]
        if along_x:
            box(x0 - 0.02, x0 + e, y0 - 0.02, y1 + 0.02, z0 - 0.02, z1 + 0.02, "lead"); box(x1 - e, x1 + 0.02, y0 - 0.02, y1 + 0.02, z0 - 0.02, z1 + 0.02, "lead")
        else:
            box(x0 - 0.02, x1 + 0.02, y0 - 0.02, y1 + 0.02, z0 - 0.02, z0 + e, "lead"); box(x0 - 0.02, x1 + 0.02, y0 - 0.02, y1 + 0.02, z1 - e, z1 + 0.02, "lead")
    if "lead" in p:                                  # IC のリード: 本体の周囲に薄い板
        l = p["lead"]; ly0, ly1 = up(0.0, 0.15)
        box(x0 - l, x1 + l, ly0, ly1, z0 - l, z1 + l, "lead")
    for c, r in p.get("pins", []):
        py0, py1 = up(0.0, p["pin_h"])
        box(c - 0.32, c + 0.32, py0, py1, r - 0.32, r + 0.32, "pin")
with open(os.path.join(D3, "quad_hdmi_tx_simplified.obj"), "w") as f:
    f.write("# Quad HDMI TX carrier rev B - simplified 3D model (board + component boxes). Units: mm. Y up.\nmtllib quad_hdmi_tx_simplified.mtl\n")
    for v in V: f.write(f"v {v[0]:.3f} {v[1]:.3f} {v[2]:.3f}\n")
    for t in VT: f.write(f"vt {t[0]:.5f} {t[1]:.5f}\n")
    for n in VN: f.write(f"vn {n[0]} {n[1]} {n[2]}\n")
    for mat, faces in F.items():
        f.write(f"usemtl {mat}\n")
        for face in faces:
            f.write("f " + " ".join(f"{a}/{b}/{c}" if b else f"{a}//{c}" for a, b, c in face) + "\n")
with open(os.path.join(D3, "quad_hdmi_tx_simplified.mtl"), "w") as f:
    def mtl(name, rgb, extra=""):
        r, g, b_ = int(rgb[0:2], 16) / 255, int(rgb[2:4], 16) / 255, int(rgb[4:6], 16) / 255
        f.write(f"newmtl {name}\nKd {r:.3f} {g:.3f} {b_:.3f}\nKa 0.2 0.2 0.2\nKs 0.3 0.3 0.3\nNs 40\n{extra}\n")
    mtl("board", COLORS["fr4"], "map_Kd tex_top.png")
    for k, c in COLORS.items():
        if k != "fr4": mtl(k, c)
print("OBJ:", len(V), "vertices,", sum(len(v) for v in F.values()), "faces")
