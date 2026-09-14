#!/usr/bin/env python3
"""ネットリストから KiCad 基板を生成する: 部品配置、外形、プレーン、ネットクラス。
使い方: gen_pcb.py            -> quad_hdmi_tx.kicad_pcb (未配線)
"""
import os, sys, json, re
import pcbnew
from pcbnew import VECTOR2I, FromMM
sys.path.insert(0, os.path.dirname(__file__))
from sexp import parse, find, find1

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "quad_hdmi_tx"))
PCB = os.path.join(OUT, "quad_hdmi_tx.kicad_pcb")
FPLIB = "/usr/share/kicad/footprints/"
W, H = 115.0, 110.0          # 基板外形 mm

# ---------------------------------------------------------------- ネットリスト読み込み
doc = parse(open(os.path.join(OUT, "netlist.net")).read())[0]
comps = {}
for c in find(find1(doc, "components"), "comp"):
    comps[find1(c, "ref")[1]] = dict(value=find1(c, "value")[1], fp=find1(c, "footprint")[1])
pad_net = {}
for n in find(find1(doc, "nets"), "net"):
    name = find1(n, "name")[1]
    for node in find(n, "node"):
        pad_net[(find1(node, "ref")[1], find1(node, "pin")[1])] = name

# ---------------------------------------------------------------- 配置表
# (x, y, rot, side)  side: "F" or "B"
PL = {}
def place(ref, x, y, rot=0, side="F"):
    PL[ref] = (x, y, rot, side)

# FPGA ヘッダ: J7 左辺 (縦、pin1 上)、J8 下辺 (横、pin1 左)
place("J7", 5.0, 4.0, 0)
place("J8", 12.0, 100.0, 90)
# チャネル: HDMI 上辺、TPD、ADV (rot 180)、LDO。ピッチ 24 mm
CX = {1: 25.0, 2: 49.0, 3: 73.0, 4: 97.0}
for n, cx in CX.items():
    place(f"J{n}", cx, 10.4, 90)              # HDMI: パッド y=13.7、開口部は上辺
    place(f"U{n}2", cx, 20.5, 90)             # TPD12S016: TMDS パッド上辺 (y=17.6)、A 側下辺 (y=23.4)
    place(f"U{n}1", cx, 33.0, 180)            # ADV7513: TMDS 上辺 (y=27.3)、データ 下辺/左辺
    # TPD まわり
    place(f"C{n}17", cx - 6.5, 17.5, 90)      # VCCA 0.1u (+3V3)
    place(f"C{n}20", cx + 6.5, 17.5, 90)      # 5V_OUT 0.1u
    place(f"C{n}19", cx + 6.5, 24.0, 90)      # VCC5V 0.1u
    # ADV 右側の列 (縦置き、2.2 mm ピッチ)。rot 180 後の右辺: 上から HPD16 AVDD15 REXT14 BGVDD13 PVDD12 DVDD11 ... VSYNC2 DVDD1
    col = cx + 9.0
    for ref, y in ((f"C{n}11", 26.0), (f"C{n}09", 28.2), (f"C{n}13", 30.4), (f"C{n}14", 32.6), (f"C{n}15", 34.8),
                   (f"C{n}04", 37.0), (f"C{n}07", 39.2), (f"C{n}12", 41.4), (f"C{n}08", 43.6)):
        place(ref, col, y, 90)
    # フェライトビーズ / 抵抗の列 (縦置き)
    col2 = cx + 11.0
    for ref, y in ((f"FB{n}1", 27.0), (f"FB{n}2", 29.5), (f"R{n}1", 32.0), (f"R{n}2", 34.5)):
        place(ref, col2, y, 90)
    # ADV 上辺左側 (pin 28-32: INT, DVDD_3V, CEC, DVDD, CEC_CLK) 用
    place(f"C{n}10", cx - 5.0, 24.8, 0)       # AVDD (pin25) 0.1u
    for ref, y in ((f"C{n}16", 24.5), (f"C{n}18", 26.7), (f"C{n}06", 28.9)):
        place(ref, cx - 7.0, y, 90)           # DVDD_3V 0.1u / 1u、DVDD (pin31) 0.1u
    place(f"R{n}3", cx - 9.5, 24.0, 90)       # INT 10k
    place(f"R{n}4", cx - 9.5, 26.5, 90)       # CEC_CLK 0R
    place(f"C{n}05", cx - 7.5, 41.0, 0)       # DVDD (pin51) 0.1u
    # LDO 行
    place(f"U{n}3", cx, 49.0, 0)
    place(f"C{n}01", cx - 7.0, 49.0, 90)      # 10u in
    place(f"C{n}02", cx + 7.0, 49.0, 90)      # 22u out
    place(f"C{n}03", cx + 10.0, 49.0, 90)     # 0.1u out
# 電源部 (右辺、y >= 55)
place("J5", 109.5, 64.0, 90)                  # USB-C、開口部右
place("F1", 104.0, 57.0, 90)
place("R5", 103.0, 71.0, 0)
place("R6", 103.0, 73.0, 0)
place("J6", 110.5, 20.0, 0)
place("U5", 102.0, 82.0, 0)
place("R7", 97.0, 82.0, 90)
place("C51", 106.0, 79.5, 0)
place("L1", 107.0, 86.5, 0)
place("C52", 99.0, 76.0, 0)
place("C53", 102.5, 76.0, 0)
place("C54", 106.0, 76.0, 0)
place("C55", 100.0, 92.0, 0)
place("C56", 104.0, 92.0, 0)
place("D1", 110.0, 90.0, 0)
place("R8", 110.0, 93.0, 0)
place("JP1", 6.0, 107.5, 0)
for i, y in enumerate((58.0, 60.5, 63.0, 65.5)):
    place(f"R{i+1}", 12.0, y, 0)              # I2C プルアップ
place("H1", 12.0, 14.0); place("H2", 111.0, 6.0); place("H3", 111.0, 106.0); place("H4", 60.0, 106.0)

# ---------------------------------------------------------------- 基板生成
board = pcbnew.BOARD()
bds = board.GetDesignSettings()
bds.SetCopperLayerCount(4)
board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
board.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_POWER)
board.SetLayerName(pcbnew.In1_Cu, "GND")
board.SetLayerName(pcbnew.In2_Cu, "PWR")
bds.m_MinClearance = FromMM(0.15)
bds.m_TrackMinWidth = FromMM(0.15)
bds.m_ViasMinSize = FromMM(0.5)
bds.m_MinThroughDrill = FromMM(0.3)
bds.m_ViasMinAnnularWidth = FromMM(0.1)
bds.m_CopperEdgeClearance = FromMM(0.3)

nets = {}
def net(name):
    if name not in nets:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni); nets[name] = ni
    return nets[name]

missing = []
for ref, c in comps.items():
    lib, name = c["fp"].split(":")
    fp = pcbnew.FootprintLoad(FPLIB + lib + ".pretty", name)
    if fp is None:
        missing.append(c["fp"]); continue
    fp.SetReference(ref); fp.SetValue(c["value"])
    if ref not in PL:
        missing.append(f"noplace:{ref}"); PL[ref] = (20 + 5 * (len(missing) % 15), 60 + 5 * (len(missing) // 15), 0, "F")
    x, y, rot, side = PL[ref]
    board.Add(fp)
    if side == "B":
        fp.Flip(VECTOR2I(0, 0), False)
    fp.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
    fp.SetOrientationDegrees(rot)
    for pad in fp.Pads():
        nn = pad_net.get((ref, pad.GetNumber()))
        if nn and not nn.startswith("unconnected-"):
            pad.SetNet(net(nn))
    # リファレンスを小さく
    fp.Reference().SetTextSize(VECTOR2I(FromMM(0.8), FromMM(0.8)))
    fp.Reference().SetTextThickness(FromMM(0.12))
if missing:
    print("WARN:", missing)

# 外形
def seg(x1, y1, x2, y2, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(VECTOR2I(FromMM(x1), FromMM(y1))); s.SetEnd(VECTOR2I(FromMM(x2), FromMM(y2)))
    s.SetLayer(layer); s.SetWidth(FromMM(w)); board.Add(s)
for a, b in (((0, 0), (W, 0)), ((W, 0), (W, H)), ((W, H), (0, H)), ((0, H), (0, 0))):
    seg(a[0], a[1], b[0], b[1])

# プレーン
def zone(netname, layer, x1, y1, x2, y2, prio=0, name=""):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer); z.SetNetCode(net(netname).GetNetCode())
    z.SetAssignedPriority(prio)
    z.SetZoneName(name or netname)
    o = z.Outline(); o.NewOutline()
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        o.Append(FromMM(x), FromMM(y))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetMinThickness(FromMM(0.2))
    z.SetLocalClearance(FromMM(0.25))
    z.SetIsFilled(False)
    board.Add(z); return z
zone("GND", pcbnew.In1_Cu, 0, 0, W, H)
zone("+3V3", pcbnew.In2_Cu, 0, 0, W, H)
for n, cx in CX.items():
    zone(f"CH{n}_1V8", pcbnew.In2_Cu, cx - 11.85, 24.0, cx + 11.85, 53.0, prio=1)

# テキスト
t = pcbnew.PCB_TEXT(board); t.SetText("QUAD HDMI TX  ADV7513 x4  rev A"); t.SetLayer(pcbnew.F_SilkS)
t.SetPosition(VECTOR2I(FromMM(60), FromMM(58))); t.SetTextSize(VECTOR2I(FromMM(1.5), FromMM(1.5))); board.Add(t)

# ---------------------------------------------------------------- プレーン系ネットのファンアウトビア
# FreeRouting は内層プレーンへの接続 (パッド -> ビア) を作らないので、SMD パッドごとに先に打っておく。
import math
PLANE_NETS = {"GND", "+3V3"} | {f"CH{n}_1V8" for n in CX}
VIA_D, VIA_DRILL, CLR = 0.6, 0.3, 0.15
all_pads = []       # (x, y, hw, hh, net)  軸平行の近似矩形 (mm)
for fp in board.GetFootprints():
    for pad in fp.Pads():
        bb = pad.GetBoundingBox()
        all_pads.append((bb.GetCenter().x / 1e6, bb.GetCenter().y / 1e6, bb.GetWidth() / 2e6, bb.GetHeight() / 2e6, pad.GetNetname()))
vias_placed = []    # (x, y)
def clear_of(x, y, netname):
    for px, py, hw, hh, pn in all_pads:
        if pn == netname:
            continue
        dx = max(abs(x - px) - hw, 0); dy = max(abs(y - py) - hh, 0)
        if math.hypot(dx, dy) < VIA_D / 2 + CLR:
            return False
    for vx, vy in vias_placed:
        if math.hypot(x - vx, y - vy) < VIA_D + CLR:
            return False
    if not (1.0 < x < W - 1.0 and 1.0 < y < H - 1.0):
        return False
    return True
def rot(vx, vy, deg):
    a = math.radians(deg); return (vx * math.cos(a) - vy * math.sin(a), vx * math.sin(a) + vy * math.cos(a))
n_via = 0; n_fail = []
for fp in board.GetFootprints():
    pads = list(fp.Pads())
    tht_nums = {p.GetNumber() for p in pads if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH}
    fx, fy = fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6
    for pad in pads:
        netname = pad.GetNetname()
        if netname not in PLANE_NETS or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or pad.GetNumber() in tht_nums:
            continue
        px, py = pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6
        sx, sy = pad.GetSize().x / 1e6, pad.GetSize().y / 1e6
        ang = -pad.GetOrientationDegrees()          # KiCad は y 下向き座標。画面上の回転を数学座標へ
        if len(pads) <= 4:
            dx, dy = px - fx, py - fy               # 2 端子部品: 部品中心から外向き
            if abs(dx) + abs(dy) < 1e-3: dx, dy = 1.0, 0.0
        else:
            ax = rot(1, 0, ang) if sx >= sy else rot(0, 1, ang)   # パッド長軸
            dx, dy = ax
            if (px - fx) * dx + (py - fy) * dy < 0: dx, dy = -dx, -dy
        L = math.hypot(dx, dy); dx, dy = dx / L, dy / L
        ex = abs(dx * rot(1, 0, ang)[0] + dy * rot(1, 0, ang)[1]) * sx / 2 + abs(dx * rot(0, 1, ang)[0] + dy * rot(0, 1, ang)[1]) * sy / 2
        d0 = ex + CLR + VIA_D / 2 + 0.1
        # 横方向 (パッド軸に直交) の候補も用意する: 縦に並んだ 2 端子部品では外向きに置けないことがある
        ey = abs(-dy * rot(1, 0, ang)[0] + dx * rot(1, 0, ang)[1]) * sx / 2 + abs(-dy * rot(0, 1, ang)[0] + dx * rot(0, 1, ang)[1]) * sy / 2
        e0 = ey + CLR + VIA_D / 2 + 0.1
        cands = [(d0, 0.0), (d0 + 0.75, 0.0), (0.0, e0), (0.0, -e0), (d0 + 0.4, 0.6), (d0 + 0.4, -0.6),
                 (0.3, e0), (0.3, -e0), (-0.3, e0), (-0.3, -e0), (d0 + 1.5, 0.0), (d0 + 1.1, 0.6), (d0 + 1.1, -0.6), (d0 + 2.25, 0.0)]
        placed = False
        for d, lat in cands:
            vx, vy = px + dx * d - dy * lat, py + dy * d + dx * lat
            if clear_of(vx, vy, netname):
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(VECTOR2I(FromMM(vx), FromMM(vy))); via.SetDrill(FromMM(VIA_DRILL)); via.SetWidth(FromMM(VIA_D))
                via.SetViaType(pcbnew.VIATYPE_THROUGH); via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                via.SetNetCode(pad.GetNetCode()); via.SetLocked(True); board.Add(via)
                tr = pcbnew.PCB_TRACK(board)
                tr.SetStart(VECTOR2I(FromMM(px), FromMM(py))); tr.SetEnd(VECTOR2I(FromMM(vx), FromMM(vy)))
                tr.SetWidth(FromMM(0.25 if min(sx, sy) >= 0.4 else 0.2)); tr.SetLayer(pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu)
                tr.SetNetCode(pad.GetNetCode()); tr.SetLocked(True); board.Add(tr)
                vias_placed.append((vx, vy)); n_via += 1; placed = True
                break
        if not placed:
            n_fail.append(f"{fp.GetReference()}.{pad.GetNumber()}({netname})")
print(f"fanout vias: {n_via}  failed: {len(n_fail)} {n_fail[:12]}")

pcbnew.SaveBoard(PCB, board)
print("saved", PCB, "footprints:", len(list(board.GetFootprints())), "nets:", len(nets))

# ネットクラスをプロジェクトファイルへ
pro_path = os.path.join(OUT, "quad_hdmi_tx.kicad_pro")
pro = json.load(open(pro_path))
pro["net_settings"] = {
    "classes": [
        {"name": "Default", "clearance": 0.15, "track_width": 0.2, "via_diameter": 0.6, "via_drill": 0.3,
         "diff_pair_width": 0.15, "diff_pair_gap": 0.15, "diff_pair_via_gap": 0.25, "microvia_diameter": 0.3, "microvia_drill": 0.1,
         "bus_width": 12, "line_style": 0, "wire_width": 6, "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)"},
        {"name": "TMDS", "clearance": 0.15, "track_width": 0.15, "via_diameter": 0.5, "via_drill": 0.3,
         "diff_pair_width": 0.15, "diff_pair_gap": 0.15, "diff_pair_via_gap": 0.25, "microvia_diameter": 0.3, "microvia_drill": 0.1,
         "bus_width": 12, "line_style": 0, "wire_width": 6, "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)"},
        {"name": "Power", "clearance": 0.2, "track_width": 0.5, "via_diameter": 0.8, "via_drill": 0.4,
         "diff_pair_width": 0.2, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "microvia_diameter": 0.3, "microvia_drill": 0.1,
         "bus_width": 12, "line_style": 0, "wire_width": 6, "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)"}],
    "meta": {"version": 3},
    "netclass_patterns": [{"pattern": "CH*_TX*", "netclass": "TMDS"}] +
                         [{"pattern": p, "netclass": "Power"} for p in ("+5V", "+3V3", "VBUS", "CH*_1V8", "CH*_AVDD", "CH*_PVDD", "CH*_5V_OUT", "SW", "FPGA_5V")]
}
pro["board"]["design_settings"] = {
    "rules": {"min_clearance": 0.15, "min_track_width": 0.15, "min_via_diameter": 0.5, "min_through_hole_diameter": 0.3,
              "min_via_annular_width": 0.1, "min_copper_edge_clearance": 0.3, "solder_mask_clearance": 0.0, "solder_mask_min_width": 0.0},
    "defaults": {}, "track_widths": [0.15, 0.2, 0.3, 0.5], "via_dimensions": [{"diameter": 0.5, "drill": 0.3}, {"diameter": 0.8, "drill": 0.4}],
    "diff_pair_dimensions": [{"width": 0.15, "gap": 0.15, "via_gap": 0.25}]
}
json.dump(pro, open(pro_path, "w"), indent=2)
print("project updated")
