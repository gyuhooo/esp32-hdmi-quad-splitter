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
# チャネル: HDMI 上辺、TPD、ADV (rot 180)、LDO
CX = {1: 24.0, 2: 46.0, 3: 68.0, 4: 90.0}
for n, cx in CX.items():
    place(f"J{n}", cx, 10.4, 90)              # HDMI: パッド y=13.7、開口部は上辺
    place(f"U{n}2", cx, 20.5, 90)             # TPD12S016: TMDS パッド上辺 (y=17.6)、A 側下辺 (y=23.4)
    place(f"U{n}1", cx, 33.0, 180)            # ADV7513: TMDS 上辺 (y=27.3)、データ 下辺/左辺
    # TPD まわりのコンデンサ
    place(f"C{n}17", cx - 6.5, 17.5, 90)      # VCCA 0.1u (+3V3)
    place(f"C{n}20", cx + 6.5, 17.5, 90)      # 5V_OUT 0.1u
    place(f"C{n}19", cx + 6.5, 24.0, 90)      # VCC5V 0.1u
    # ADV 右側の列 (rot 180 後: pin1..16 が右辺、上から 16..1)
    col = cx + 8.5
    place(f"C{n}09", col, 28.5, 0)            # AVDD (pin15) 0.1u
    place(f"C{n}13", col, 30.0, 0)            # BGVDD 0.1u
    place(f"C{n}14", col, 31.5, 0)            # PVDD 0.1u
    place(f"C{n}15", col, 33.0, 0)            # PVDD 1u
    place(f"C{n}04", col, 34.5, 0)            # DVDD (pin11) 0.1u
    place(f"C{n}03", col, 36.0, 0)            # DVDD (pin1) 0.1u
    place(f"C{n}12", col, 38.0, 0)            # AVDD 10u
    place(f"C{n}08", col, 40.0, 0)            # 1V8 10u
    place(f"FB{n}1", cx + 11.5, 29.0, 90)     # 1V8 -> AVDD
    place(f"FB{n}2", cx + 11.5, 32.5, 90)     # 1V8 -> PVDD
    place(f"R{n}1", cx + 11.5, 36.0, 90)      # R_EXT 887
    place(f"R{n}2", cx + 11.5, 38.5, 90)      # PD 10k
    # ADV 上辺 (TMDS 以外: pin 28-32 が左側 x=cx-1.75..-3.75)
    place(f"C{n}10", cx - 4.5, 24.0, 0)       # AVDD (pin25) 0.1u
    place(f"C{n}11", cx + 6.5, 27.0, 0)       # AVDD (pin19) 0.1u
    place(f"C{n}16", cx - 7.5, 25.5, 0)       # DVDD_3V 0.1u
    place(f"C{n}18", cx - 7.5, 27.0, 0)       # DVDD_3V 1u
    place(f"C{n}06", cx - 7.5, 28.5, 0)       # DVDD (pin31) 0.1u
    place(f"R{n}4", cx - 7.5, 30.0, 0)        # CEC_CLK 0R
    place(f"R{n}3", cx - 7.5, 31.5, 0)        # INT 10k
    place(f"C{n}07", cx - 8.5, 40.0, 0)       # DVDD (pin51) 0.1u
    place(f"C{n}05", cx - 8.5, 41.5, 0)       # DVDD 0.1u 予備
    # LDO
    place(f"U{n}3", cx, 48.5, 0)
    place(f"C{n}01", cx - 7.0, 48.5, 90)      # 10u in
    place(f"C{n}02", cx + 7.0, 48.5, 90)      # 22u out
    place(f"C{n}03", cx + 10.0, 48.5, 90) if False else None
# C{n}03 は上で DVDD 用に使ったので LDO 出力 0.1u は C{n}03 ではなく回路図の割り当てに従う:
# 回路図: C{n}01=10u(in) C{n}02=22u(out) C{n}03=0.1u(out) C{n}04..07=DVDD 0.1u x4, C{n}08=1V8 10u,
#         C{n}09..11=AVDD 0.1u x3, C{n}12=AVDD 10u, C{n}13,14=PVDD 0.1u x2, C{n}15=PVDD 1u,
#         C{n}16,17=+3V3 0.1u x2, C{n}18=+3V3 1u, C{n}19=+5V 0.1u, C{n}20=5V_OUT 0.1u
for n, cx in CX.items():
    place(f"C{n}03", cx + 10.0, 48.5, 90)     # LDO 出力 0.1u
    place(f"C{n}04", cx + 8.5, 34.5, 0)       # DVDD 0.1u (pin11)
    place(f"C{n}05", cx - 8.5, 41.5, 0)       # DVDD 0.1u (pin51 付近)
    place(f"C{n}06", cx - 7.5, 28.5, 0)       # DVDD 0.1u (pin31)
    place(f"C{n}07", cx + 8.5, 36.0, 0)       # DVDD 0.1u (pin1)
# 電源部 (右辺)
place("J5", 109.5, 60.0, 90)                  # USB-C、開口部右
place("F1", 104.0, 50.0, 90)
place("R5", 103.0, 68.0, 0)
place("R6", 103.0, 70.0, 0)
place("J6", 106.0, 40.0, 0)
place("U5", 102.0, 82.0, 0)
place("R7", 97.0, 82.0, 90)
place("C51", 106.0, 79.5, 0)
place("L1", 107.0, 86.5, 0)
place("C52", 99.0, 75.0, 0)
place("C53", 102.5, 75.0, 0)
place("C54", 106.0, 75.0, 0)
place("C55", 100.0, 92.0, 0)
place("C56", 104.0, 92.0, 0)
place("D1", 109.0, 96.0, 0)
place("R8", 109.0, 99.0, 0)
place("JP1", 6.0, 107.5, 0)
for i, y in enumerate((58.0, 60.5, 63.0, 65.5)):
    place(f"R{i+1}", 12.0, y, 0)              # I2C プルアップ
place("H1", 12.5, 22.0); place("H2", 111.0, 6.0); place("H3", 111.0, 106.0); place("H4", 60.0, 106.0)

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
    zone(f"CH{n}_1V8", pcbnew.In2_Cu, cx - 10.5, 24.0, cx + 10.5, 52.0, prio=1)

# テキスト
t = pcbnew.PCB_TEXT(board); t.SetText("QUAD HDMI TX  ADV7513 x4  rev A"); t.SetLayer(pcbnew.F_SilkS)
t.SetPosition(VECTOR2I(FromMM(60), FromMM(58))); t.SetTextSize(VECTOR2I(FromMM(1.5), FromMM(1.5))); board.Add(t)

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
