#!/usr/bin/env python3
"""FPGA メイン基板 (fpga_main) のレイアウト生成: 配置、外形、プレーン、BGA ファンアウト (fpga_common の計画)、
BGA 直下のデカップリング、プレーン系ネットのファンアウトビア。
使い方: gen_fpga_pcb.py -> fpga_main.kicad_pcb (BGA エスケープと電源ビアは配線済み・ロック、信号は未配線) と drc_pre.rpt

基板: 115 x 72 mm、6 層 (F / In1 GND / In2 SIG1 / In3 SIG2 / In4 PWR / B)。y < 38 はキャリア基板 (quad_hdmi_tx rev B) の真下で、
ソケット J1/J2 (キャリアの J7/J8 の鏡像位置) 以外は置かない。FPGA は露出部の中央 (51.6, 56)、下辺に JTAG/ボタン/DIP/LED、右下に電源。
"""
import os, sys, json, math, re
import pcbnew
from pcbnew import VECTOR2I, FromMM
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import parse, find, find1
import fpga_common as F

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "fpga_main"))
PCB = os.path.join(OUT, "fpga_main.kicad_pcb")
FPLIB = "/usr/share/kicad/footprints/"
W, H = 115.0, 72.0
FX, FY = F.FPGA_XY
IN2, IN3, BCU, FCU = pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu, pcbnew.F_Cu
LAYER = {"In2": IN2, "In3": IN3}
ROLE = json.load(open(os.path.join(OUT, "roles.json")))
def R(role):
    return ROLE[role]

# ---------------------------------------------------------------- ネットリスト
doc = parse(open(os.path.join(OUT, "netlist.net")).read())[0]
comps = {}
for c in find(find1(doc, "components"), "comp"):
    comps[find1(c, "ref")[1]] = dict(value=find1(c, "value")[1], fp=find1(c, "footprint")[1])
pad_net = {}
for n in find(find1(doc, "nets"), "net"):
    name = find1(n, "name")[1]
    for node in find(n, "node"):
        pad_net[(find1(node, "ref")[1], find1(node, "pin")[1])] = name

# ---------------------------------------------------------------- 配置
PL = {}
PIN_PLACE = {}
def place(ref, x, y, rot=0, side="F"):
    PL[ref] = (x, y, rot, side)
def place_pins(ref, pins):
    """ピン番号 -> 目標座標 (表面)。回転は後でピン位置が合うように決める"""
    PIN_PLACE[ref] = pins

place("U1", FX, FY, 0)
place_pins("J1", {"1": (F.HDR_X1, F.HDR_Y[("J1", 1)]), "2": (F.HDR_X1, F.HDR_Y[("J1", 0)]), "3": (F.HDR_X1 + F.HDR_PITCH, F.HDR_Y[("J1", 1)])})
place_pins("J2", {"1": (F.HDR_X1, F.HDR_Y[("J2", 1)]), "2": (F.HDR_X1, F.HDR_Y[("J2", 0)]), "3": (F.HDR_X1 + F.HDR_PITCH, F.HDR_Y[("J2", 1)])})
# フラッシュ (FPGA 右): ピン 1-4 (CS, DO, IO2, GND) が BGA 側
place("U2", 68.0, 57.5, 0)                      # BGA 右辺の出口 (x 60.6) との間に 4 mm の通路を空ける
place(R("c_flash"), 74.0, 53.6, 0)
place(R("r_cs"), 76.1, 55.5, 0); place(R("r_wp"), 76.1, 57.5, 0); place(R("r_hold"), 76.1, 59.5, 0)
# 発振器 (FPGA 左、D4 の左出口 y=51.5 の近く)
place("X1", 38.0, 50.0, 0); place(R("c_osc"), 35.5, 50.0, 90)
# 下辺: JTAG、ボタン、DIP、LED
place_pins("J3", {"1": (8.0, 69.0), "2": (8.0, 67.0), "3": (10.0, 69.0)})
place_pins("J4", {"1": (24.0, 69.0), "2": (26.54, 69.0)})
place_pins("J5", {"1": (3.0, 46.0), "2": (5.54, 46.0), "3": (3.0, 48.54)})        # PMOD: 左端、縦
place("SW1", 41.5, 68.3, 0); place("SW2", 47.3, 68.3, 0)
place(R("r_prog"), 33.0, 66.0, 0); place(R("r_rst"), 36.5, 65.5, 0); place(R("c_rst"), 29.5, 65.5, 0)
place("SW3", 55.3, 68.2, 0)
LED_X = {f"D{i + 1}": round(61.5 + 2.0 * i, 2) for i in range(7)}       # 縦置き (rot 90): A が上 (抵抗側)、K が下 (GND ビア)
for d, x in LED_X.items():
    place(d, x, 69.0, 90)
for d, role in (("D1", "r_pwr_led"), ("D2", "r_done_led"), ("D3", "r_init_led"), ("D4", "r_led0"), ("D5", "r_led1"), ("D6", "r_led2"), ("D7", "r_led3")):
    place(R(role), LED_X[d], 66.9, 0)
# コンフィグ系抵抗: FPGA 右下 (DONE/INIT/PROG/M0 は下辺側、TMS/TDI は JTAG 側)
place(R("r_done"), 62.5, 62.0, 90); place(R("r_init"), 64.5, 62.0, 90); place(R("r_m0"), 66.5, 62.0, 90)
place(R("r_tms"), 33.0, 63.5, 90); place(R("r_tdi"), 35.0, 63.5, 90)
# 電源部 (右下): USB-C は右辺、バックは 3 ブロック横並び
place("J10", W - 3.67, 46.0, 90)
place(R("r_cc1"), 104.5, 42.0, 0); place(R("r_cc2"), 104.5, 44.0, 0)
place("F1", 104.5, 48.5, 270)                 # pad1 (VBUS) 上、pad2 (+5V) 下 -> In4 の +5V バーへ
place(R("c_5v"), 100.5, 52.0, 0)
BUCKS = {"U3": 82.5, "U4": 94.5, "U5": 106.5}
UY = 57.5
for u, ux in BUCKS.items():
    place(u, ux, UY, 0)
    place(R(f"{u}_cbst"), ux + 2.4, UY - 2.3, 0)
    place({"U3": "L1", "U4": "L2", "U5": "L3"}[u], ux + 4.5, UY + 0.8, 0)
    place(R(f"{u}_cout1"), ux + 4.5, UY + 4.6, 0); place(R(f"{u}_cout2"), ux + 4.5, UY + 7.1, 0)
    place(R(f"{u}_cin1"), ux - 0.5, UY + 4.0, 0); place(R(f"{u}_cin2"), ux - 0.5, UY + 6.5, 0)
    place(R(f"{u}_cin0"), ux - 0.5, UY - 2.9, 0)
    place(R(f"{u}_ren"), ux - 3.0, UY + 7.0, 270)          # pad1 (+5V) 上: ビアは +5V の歯 (In4) の中へ
    if f"{u}_cen" in ROLE: place(R(f"{u}_cen"), ux + 0.8, UY + 9.0, 0)
    if f"{u}_rtop" in ROLE:
        place(R(f"{u}_rtop"), ux - 3.6, UY - 0.8, 90); place(R(f"{u}_rbot"), ux - 3.6, UY + 1.3, 90)
place("JP1", 85.0, 51.8, 0, "B")              # 裏面、+5V バー (In4) の真下。FPGA_5V は J2 の 39/40 ピンへ配線
# FPGA デカップリング (裏面)。BGA 中央の十字 (行 7.5 / 列 7.5) はビアが無いので 0402 を置ける
CORRIDOR = {}        # ref -> (net of the pad that gets an explicit via)
def dec(net, val, i, x, y, rot, side="B"):
    ref = R(f"dec_{net}_{val}_{i}"); place(ref, x, y, rot, side); return ref
# 十字通路のコンデンサ: ビアは半整数格子 (セル中心) に置く (整数格子だとボールパッドに近すぎる)。中心 ±1.0 にビア
for i, (x, y, rot) in enumerate(((FX, FY - 2.0, 90), (FX, FY + 2.0, 90), (FX + 1.0, FY, 0), (FX - 2.0, FY, 0))):   # 腕 (列 7.5、行 >= 11.5) にはビアを置かない (幅 1.0 の腕が切れる)
    CORRIDOR[dec("+1V0", "0.47uF", i, x, y, rot)] = "+1V0"
dec("+1V0", "4.7uF", 0, 82.0, 67.9, 0); dec("+1V0", "4.7uF", 1, 87.5, 67.8, 0); dec("+1V0", "100uF", 0, 78.0, 67.7, 0)
for i, x in enumerate((FX + 4.0, FX + 7.0)):
    CORRIDOR[dec("+1V8", "0.47uF", i, x, FY, 0)] = "+1V8"
dec("+1V8", "4.7uF", 0, 62.0, FY + 0.5, 90); dec("+1V8", "47uF", 0, 98.0, 59.5, 90)
for i, (x, y) in enumerate(((41.3, 48.5), (41.3, 52.0), (41.3, 59.0), (41.3, 62.5), (62.2, 49.0), (62.2, 52.0), (63.5, 60.0), (63.5, 63.0), (38.0, 57.0))):
    dec("+3V3", "0.47uF", i, x, y, 90)
for i, (x, y, r_) in enumerate(((41.3, 55.5, 90), (38.0, 61.0, 90), (62.2, 45.0, 90), (69.5, 62.0, 0))):
    dec("+3V3", "4.7uF", i, x, y, r_)
dec("+3V3", "47uF", 0, 100.5, 46.5, 0, "F")
# 取付穴: H1-H4 はキャリアと同じ、H5-H7 はこの基板だけ
for ref, (x, y) in {"H1": (26.2, 3.0), "H2": (51.6, 3.0), "H3": (112.0, 35.0), "H4": (77.0, 3.0), "H5": (3.0, 64.0), "H6": (112.5, 69.5), "H7": (3.0, 3.0)}.items():
    place(ref, x, y)

# ---------------------------------------------------------------- 基板生成
board = pcbnew.BOARD()
bds = board.GetDesignSettings()
bds.SetCopperLayerCount(6)
board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER);  board.SetLayerName(pcbnew.In1_Cu, "GND")
board.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_SIGNAL); board.SetLayerName(pcbnew.In2_Cu, "SIG1")
board.SetLayerType(pcbnew.In3_Cu, pcbnew.LT_SIGNAL); board.SetLayerName(pcbnew.In3_Cu, "SIG2")
board.SetLayerType(pcbnew.In4_Cu, pcbnew.LT_POWER);  board.SetLayerName(pcbnew.In4_Cu, "PWR")
bds.m_MinClearance = FromMM(0.15)
bds.m_TrackMinWidth = FromMM(0.15)
bds.m_ViasMinSize = FromMM(0.5)
bds.m_MinThroughDrill = FromMM(0.2)
bds.m_HoleClearance = FromMM(0.18)
bds.m_ViasMinAnnularWidth = FromMM(0.1)
bds.m_CopperEdgeClearance = FromMM(0.3)
ncd = bds.m_NetSettings.m_DefaultNetClass
ncd.SetClearance(FromMM(0.15)); ncd.SetTrackWidth(FromMM(0.15)); ncd.SetViaDiameter(FromMM(0.5)); ncd.SetViaDrill(FromMM(0.3))

nets = {}
def net(name):
    if name not in nets:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni); nets[name] = ni
    return nets[name]

missing = []
for ref, c in comps.items():
    lib, name = c["fp"].split(":")
    if ref.startswith("H"):
        name = "MountingHole_3.2mm_M3"
    fp = pcbnew.FootprintLoad(FPLIB + lib + ".pretty", name)
    if fp is None:
        missing.append(c["fp"]); continue
    fp.SetReference(ref); fp.SetValue(c["value"])
    if ref not in PL and ref not in PIN_PLACE:
        missing.append(f"noplace:{ref}"); PL[ref] = (20 + 5 * (len(missing) % 15), 40 + 5 * (len(missing) // 15), 0, "F")
    board.Add(fp)
    if ref in PIN_PLACE:
        x, y, rot, side = 0.0, 0.0, 0, "F"
    else:
        x, y, rot, side = PL[ref]
    if side == "B":
        fp.Flip(VECTOR2I(0, 0), False)
    fp.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
    fp.SetOrientationDegrees(rot)
    for pad in fp.Pads():
        nn = pad_net.get((ref, pad.GetNumber()))
        if nn and not nn.startswith("unconnected-"):
            pad.SetNet(net(nn))
    fp.Reference().SetTextSize(VECTOR2I(FromMM(0.8), FromMM(0.8)))
    fp.Reference().SetTextThickness(FromMM(0.12))
    fp.Reference().SetLayer(pcbnew.F_Fab if side == "F" else pcbnew.B_Fab)
    fp.Value().SetVisible(False)
if missing:
    print("WARN:", missing)

def padpos(ref, num):
    fp = board.FindFootprintByReference(ref)
    for p in fp.Pads():
        if p.GetNumber() == num:
            return p.GetPosition().x / 1e6, p.GetPosition().y / 1e6
    raise KeyError((ref, num))
def padnet(ref, num):
    fp = board.FindFootprintByReference(ref)
    for p in fp.Pads():
        if p.GetNumber() == num:
            return p.GetNetname()

# ピン位置指定の部品: 回転を総当たりしてピン 1 を目標に置き、他のピンも合う向きを採用
for ref, pins in PIN_PLACE.items():
    fp = board.FindFootprintByReference(ref)
    ok = False
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot); fp.SetPosition(VECTOR2I(0, 0))
        p1x, p1y = padpos(ref, "1"); tx, ty = pins["1"]
        fp.SetPosition(VECTOR2I(FromMM(tx - p1x), FromMM(ty - p1y)))
        if all(abs(padpos(ref, n)[0] - x) < 0.02 and abs(padpos(ref, n)[1] - y) < 0.02 for n, (x, y) in pins.items()):
            ok = True; break
    assert ok, (ref, pins, [(n, padpos(ref, n)) for n in pins])
# ソケット J1/J2 のパッドを 1.7 -> 1.5 mm に (穴 1.0 mm、アニュラ 0.25 mm)。列の隙間が 0.84 -> 1.04 mm になり、J1 への信号が J2 の列を 0.15 mm 配線 2 本で抜けやすくなる
for ref in ("J1", "J2"):
    for pad in board.FindFootprintByReference(ref).Pads():
        pad.SetSize(VECTOR2I(FromMM(1.5), FromMM(1.5)))
assert abs(padpos("J1", "79")[0] - (F.HDR_X1 + 39 * F.HDR_PITCH)) < 0.02 and abs(padpos("J2", "80")[1] - F.HDR_Y[("J2", 0)]) < 0.02

# 外形
def seg(x1, y1, x2, y2, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(VECTOR2I(FromMM(x1), FromMM(y1))); s.SetEnd(VECTOR2I(FromMM(x2), FromMM(y2)))
    s.SetLayer(layer); s.SetWidth(FromMM(w)); board.Add(s)
for a, b in (((0, 0), (W, 0)), ((W, 0), (W, H)), ((W, H), (0, H)), ((0, H), (0, 0))):
    seg(a[0], a[1], b[0], b[1])
# キャリア基板の輪郭 (参考、表面シルク)
seg(0.5, 38.0, W - 0.5, 38.0, pcbnew.F_SilkS, 0.15)

# プレーン
ZONES = {}          # net -> [polygon (board mm)] (In4 の島と裏面ベタ: ファンアウトビアの領域判定に使う)
def zone_poly(netname, layer, pts, prio=0, name="", clearance=0.25, minw=0.2):
    if prio > 0:
        ZONES.setdefault(netname, []).append(list(pts))
    z = pcbnew.ZONE(board)
    z.SetLayer(layer); z.SetNetCode(net(netname).GetNetCode()); z.SetAssignedPriority(prio); z.SetZoneName(name or netname)
    o = z.Outline(); o.NewOutline()
    for x, y in pts:
        o.Append(FromMM(x), FromMM(y))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL); z.SetMinThickness(FromMM(minw)); z.SetLocalClearance(FromMM(clearance))
    z.SetIsFilled(False)
    board.Add(z); return z
G = F.grid_xy
zone_poly("GND", pcbnew.In1_Cu, [(0, 0), (W, 0), (W, H), (0, H)], clearance=0.15, minw=0.15)
zone_poly("+3V3", pcbnew.In4_Cu, [(0, 0), (W, 0), (W, H), (0, H)], clearance=0.15, minw=0.15)
# +1V0: BGA 中央の島 (VCCINT/VCCBRAM のビアを含み、VCCO_0 のビア (10.5, 4.5) を避ける) + 列 7.5 の腕 + 下の帯 + U3 出力への立ち上がり
isl = [(4.0, 4.0), (8.0, 4.0), (8.0, 3.0), (11.0, 3.0), (11.0, 11.5), (5.0, 11.5), (5.0, 9.6), (4.0, 9.6)]   # (列, 行)。E7 (CFGBVS, +3V3) のセル (3.5, 5.5) と L6 (VCCO_0) の (10.5, 4.5) は外
zone_poly("+1V0", pcbnew.In4_Cu, [G(r, c) for c, r in isl], prio=1, name="+1V0_island", clearance=0.15, minw=0.15)
ax0, ax1 = G(0, 7.0)[0], G(0, 8.0)[0]
zone_poly("+1V0", pcbnew.In4_Cu, [(ax0, G(11.0, 0)[1]), (ax1, G(11.0, 0)[1]), (ax1, 66.5), (ax0, 66.5)], prio=1, name="+1V0_arm", clearance=0.15, minw=0.15)
zone_poly("+1V0", pcbnew.In4_Cu, [(50.5, 66.0), (83.5, 66.0), (83.5, 59.5), (90.5, 59.5), (90.5, 68.8), (50.5, 68.8)],
          prio=1, name="+1V0_strip", clearance=0.2, minw=0.2)
# +5V: バー (ヒューズから) + 各バックの IN 側の歯
comb = [(76.0, 50.5), (112.0, 50.5), (112.0, 53.0)]
for u in ("U5", "U4", "U3"):
    ux = BUCKS[u]
    comb += [(ux - 1.2, 53.0), (ux - 1.2, 65.4), (ux - 3.6, 65.4), (ux - 3.6, 53.0)]
comb += [(76.0, 53.0)]
zone_poly("+5V", pcbnew.In4_Cu, comb, prio=1, name="+5V_comb", clearance=0.2, minw=0.2)
# +1V8: 裏面ベタ (BGA 中央右の VCCAUX/VCCADC/VCCBATT ビア + 行 7.5 の通路 + U4 出力への帯)
xe = FX + 9.0                      # BGA 右端 + 1.5 (エスケープの終端)
p18 = [G(3.6, 6.0), G(3.6, 11.6), (G(0, 11.6)[0], FY - 0.75), (xe, FY - 0.75), (xe, FY - 1.0), (101.5, FY - 1.0), (101.5, 66.0), (89.0, 66.0),
       (89.0, FY + 2.0), (xe, FY + 2.0), (xe, FY + 0.75), (G(0, 11.6)[0], FY + 0.75), G(11.4, 11.6), G(11.4, 6.0)]   # 立ち上がりは U4 の FB 分圧 (x 90.9) まで広げる
zone_poly("+1V8", pcbnew.B_Cu, p18, prio=1, name="+1V8_B", clearance=0.15, minw=0.15)

# テキスト
def text(s, x, y, layer=pcbnew.F_SilkS, size=0.8, mirror=False, rot=0):
    t = pcbnew.PCB_TEXT(board); t.SetText(s); t.SetLayer(layer)
    t.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size))); t.SetTextThickness(FromMM(0.12))
    if rot: t.SetTextAngleDegrees(rot)
    if mirror: t.SetMirrored(True)
    board.Add(t)
text("FPGA MAIN rev A  XC7A35T-1FTG256C", 22.0, 41.5, size=1.2)
text("carrier board (quad_hdmi_tx) stacks above this line", 60.0, 39.3, size=0.8)
text("JTAG 2mm", 14.5, 64.6); text("JTAG 1x6", 30.3, 71.3); text("PROG", 41.5, 71.3); text("RST", 47.3, 71.3)
text("LEDs (L to R): PWR DONE INIT USER0-3", 20.0, 63.3, size=0.8)
text("PMOD", 4.3, 42.8)
text("USB-C 5V", 108.0, 39.8); text("1V0", 87.0, 53.6); text("1V8", 99.0, 53.6); text("3V3", 111.0, 53.6)

# ---------------------------------------------------------------- 配線ユーティリティ
def add_track(pts, netname, width=0.15, layer=FCU):
    ni = net(netname)
    for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
        if abs(x1 - x2) < 1e-6 and abs(y1 - y2) < 1e-6:
            continue
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(VECTOR2I(FromMM(x1), FromMM(y1))); t.SetEnd(VECTOR2I(FromMM(x2), FromMM(y2)))
        t.SetWidth(FromMM(width)); t.SetLayer(layer); t.SetNetCode(ni.GetNetCode()); t.SetLocked(True); board.Add(t)
def add_via(x, y, netname, dia=0.5, drill=0.3):
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); via.SetDrill(FromMM(drill)); via.SetWidth(FromMM(dia))
    via.SetViaType(pcbnew.VIATYPE_THROUGH); via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNetCode(net(netname).GetNetCode()); via.SetLocked(True); board.Add(via)

# ---------------------------------------------------------------- BGA ファンアウト (fpga_common.PLAN)
n_bga_via = n_bga_trk = 0
for pin, e in F.PLAN.items():
    nn = F.NET_OF[pin]
    if nn == "NC":
        continue
    assert padnet("U1", pin) == nn, (pin, padnet("U1", pin), nn)
    bx, by = F.ball_xy(pin)
    if e["kind"] == "straight":
        vx, vy = G(*e["via"]); add_track([(bx, by), (vx, vy)], nn, 0.2); add_via(vx, vy, nn); n_bga_via += 1
    elif e["kind"] == "power":
        cx, cy = G(*e["cell"]); add_track([(bx, by), (cx, cy)], nn, 0.15); add_via(cx, cy, nn); n_bga_via += 1
    else:
        cx, cy = G(*e["cell"]); add_track([(bx, by), (cx, cy)], nn, 0.15); add_via(cx, cy, nn); n_bga_via += 1
        pts = [G(*q) for q in [e["cell"]] + e["path"]]
        add_track(pts, nn, 0.15, LAYER[e["layer"]]); n_bga_trk += 1
for pin, nn in F.NET_OF.items():
    b = F.BALLS[pin]
    if b["ring"] == 2 and b["kind"] == "IO" and nn != "NC":
        side, pos = F.exit_of(pin); ci, cj = F.natural_cell(b)
        end = {"up": (-1.5, cj), "down": (F.N + 0.5, cj), "left": (ci, -1.5), "right": (ci, F.N + 0.5)}[side]
        add_track([F.ball_xy(pin), G(ci, cj), G(*end)], nn, 0.15); n_bga_trk += 1
print(f"BGA fan-out: {n_bga_via} vias, {n_bga_trk} escape traces")

# ---------------------------------------------------------------- BGA 十字通路のデカップリング: 明示ビア
PREHANDLED = set()
for ref, pnet in CORRIDOR.items():
    fp = board.FindFootprintByReference(ref)
    cx, cy = fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6
    for pad in fp.Pads():
        px, py = pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6
        nn = pad.GetNetname()
        if nn == "+1V8":
            PREHANDLED.add((ref, pad.GetNumber())); continue          # 裏面ベタに直結
        dx, dy = px - cx, py - cy; L = math.hypot(dx, dy); dx, dy = dx / L, dy / L
        vx, vy = cx + dx * 1.0, cy + dy * 1.0
        add_track([(px, py), (vx, vy)], nn, 0.2, BCU); add_via(vx, vy, nn)
        PREHANDLED.add((ref, pad.GetNumber()))
# 裏面の +1V8 コンデンサはベタに直結。FB 分圧の上側抵抗は COUT から表面で配線 (ビア不要)
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetname() == "+1V8" and fp.GetLayer() == BCU and fp.GetReference().startswith("C"):
            PREHANDLED.add((fp.GetReference(), pad.GetNumber()))
PREHANDLED.add((R("U3_rtop"), "1"))                          # +1V0 の FB 上側: COUT から表面で配線 (U4 の分は裏面ベタへビア)
PREHANDLED.add(("U5", "1"))                                  # AP63203 FB = VOUT: 表面で L3 のパッド 2 (+3V3) へ固定配線 (下記)
fbx, fby = padpos("U5", "1"); lx, ly = padpos("L3", "2")
assert padnet("U5", "1") == "+3V3" and padnet("L3", "2") == "+3V3"
add_track([(fbx, fby), (fbx - 2.06, fby), (fbx - 2.06, 53.6), (lx + 1.1, 53.6), (lx + 1.1, ly), (lx, ly)], "+3V3", 0.2)   # CIN0 (真上) を避けて左から回る
# D1 (PWR) と D3 (INIT) の抵抗の +3V3 パッドは、抵抗列の上 (y 65.3) の表面配線で結び、1 個のビアで +3V3 プレーンへ
chain = []
for role in ("r_pwr_led", "r_init_led"):
    ref = R(role); fp = board.FindFootprintByReference(ref)
    for pad in fp.Pads():
        if pad.GetNetname() == "+3V3":
            px, py = pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6
            add_track([(px, py), (px, 65.3)], "+3V3", 0.2); chain.append(px); PREHANDLED.add((ref, pad.GetNumber()))
add_track([(min(chain), 65.3), (max(chain), 65.3)], "+3V3", 0.2)
add_via((min(chain) + max(chain)) / 2, 65.3, "+3V3", dia=0.6)

# ---------------------------------------------------------------- プレーン系ネットのファンアウトビア (gen_pcb.py と同じ方法)
PLANE_NETS = {"GND", "+3V3", "+1V0", "+1V8", "+5V"}
VIA_D, VIA_DRILL, CLR = 0.6, 0.3, 0.22
all_pads = []
for fp in board.GetFootprints():
    for pad in fp.Pads():
        bb = pad.GetBoundingBox()
        lys = {L for L in (pcbnew.F_Cu, pcbnew.B_Cu) if pad.IsOnLayer(L)}
        all_pads.append((bb.GetCenter().x / 1e6, bb.GetCenter().y / 1e6, bb.GetWidth() / 2e6, bb.GetHeight() / 2e6, pad.GetNetname(), lys))
vias_placed = [(v.GetPosition().x / 1e6, v.GetPosition().y / 1e6, v.GetNetname()) for v in board.GetTracks() if v.GetClass() == "PCB_VIA"]
segs = []
for t in board.GetTracks():
    if t.GetClass() == "PCB_TRACK":
        segs.append((t.GetStart().x / 1e6, t.GetStart().y / 1e6, t.GetEnd().x / 1e6, t.GetEnd().y / 1e6, t.GetWidth() / 2e6, t.GetNetname(), t.GetLayer()))
def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0: return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
# BGA の格子線 (内層のエスケープが通る整数列/行) にはビアを置かない: FPGA の周囲 (±9.5 mm) では整数格子線から 0.35 以上離す
def on_escape_line(x, y):
    gx, gy = x - (FX - 7.5), y - (FY - 7.5)
    if not (-2.5 <= gx <= 17.5 and -2.5 <= gy <= 17.5):
        return False
    fx, fy = abs(gx - round(gx)), abs(gy - round(gy))
    return fx < 0.4 or fy < 0.4
WHY = []
def in_poly(x, y, poly):
    inside = False; n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside
def region_ok(netname, x, y, r):
    """プレーン系ネットのビアが、そのネットの銅 (In4 の島 / 櫛 / 裏面ベタ / +3V3 の残り) に完全に入るか"""
    pts = [(x + dx, y + dy) for dx in (-r - 0.25, r + 0.25) for dy in (-r - 0.25, r + 0.25)]
    if netname == "GND":
        return True
    if netname == "+3V3":
        return not any(in_poly(px, py, poly) for n_, polys in ZONES.items() if n_ != "+1V8" for poly in polys for px, py in pts)
    return any(all(in_poly(px, py, poly) for px, py in pts) for poly in ZONES.get(netname, []))
def clear_of(x, y, netname, sx0=None, sy0=None, hw_stub=0.1, via_check=True, layer=None):
    if via_check and not region_ok(netname, x, y, VIA_D / 2):
        WHY.append(f"via@({x:.2f},{y:.2f}) outside {netname} plane region"); return False
    for px, py, hw, hh, pn, lys in all_pads:
        if pn == netname:
            continue
        dx = max(abs(x - px) - hw, 0); dy = max(abs(y - py) - hh, 0)
        if via_check and math.hypot(dx, dy) < VIA_D / 2 + CLR:
            WHY.append(f"via@({x:.2f},{y:.2f}) hits pad {pn} @({px:.2f},{py:.2f})"); return False
        if sx0 is not None and (layer is None or layer in lys):
            for k in range(0, 13):
                t = k / 12.0
                qx, qy = sx0 + (x - sx0) * t, sy0 + (y - sy0) * t
                ddx = max(abs(qx - px) - hw, 0); ddy = max(abs(qy - py) - hh, 0)
                if math.hypot(ddx, ddy) < hw_stub + CLR:
                    WHY.append(f"stub->({x:.2f},{y:.2f}) hits pad {pn} @({px:.2f},{py:.2f})"); return False
    for vx, vy, vn in vias_placed:
        if vn == netname:                        # 同じネットのビア: 穴同士の間隔だけ確保 (銅の重なりは可)
            if via_check and math.hypot(x - vx, y - vy) < 0.55:
                WHY.append(f"via@({x:.2f},{y:.2f}) too close to same-net via @({vx:.2f},{vy:.2f})"); return False
            continue
        if via_check and math.hypot(x - vx, y - vy) < VIA_D + CLR:
            WHY.append(f"via@({x:.2f},{y:.2f}) hits via @({vx:.2f},{vy:.2f})"); return False
        if sx0 is not None and seg_dist(vx, vy, sx0, sy0, x, y) < VIA_D / 2 + hw_stub + CLR:
            WHY.append(f"stub->({x:.2f},{y:.2f}) hits via @({vx:.2f},{vy:.2f})"); return False
    for x1, y1, x2, y2, hw, pn, ly in segs:
        if pn == netname:
            continue
        if via_check and seg_dist(x, y, x1, y1, x2, y2) < VIA_D / 2 + hw + CLR:
            WHY.append(f"via@({x:.2f},{y:.2f}) hits seg {pn}"); return False
        if sx0 is not None and (layer is None or ly == layer):
            if min(seg_dist(sx0, sy0, x1, y1, x2, y2), seg_dist(x, y, x1, y1, x2, y2),
                   seg_dist(x1, y1, sx0, sy0, x, y), seg_dist(x2, y2, sx0, sy0, x, y)) < hw + hw_stub + CLR:
                WHY.append(f"stub->({x:.2f},{y:.2f}) hits seg {pn}"); return False
    if not (1.0 < x < W - 1.0 and 1.0 < y < H - 1.0):
        WHY.append(f"via@({x:.2f},{y:.2f}) out of board"); return False
    return True
def rot(vx, vy, deg):
    a = math.radians(deg); return (vx * math.cos(a) - vy * math.sin(a), vx * math.sin(a) + vy * math.cos(a))
n_via = 0; n_fail = []; n_bridge = 0
for fp in board.GetFootprints():
    if fp.GetReference() == "U1":
        continue
    pads = list(fp.Pads())
    tht_nums = {p.GetNumber() for p in pads if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH}
    fx, fy = fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6
    skip = set()
    if len(pads) > 4:
        by_net = {}
        for p in pads:
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and p.GetNetname() in PLANE_NETS:
                by_net.setdefault(p.GetNetname(), []).append(p)
        for nn, plist in by_net.items():
            plist.sort(key=lambda p: (round(p.GetPosition().x / 1e6, 1), round(p.GetPosition().y / 1e6, 1)))
            run = [plist[0]]
            def flush(run):
                global n_bridge
                if len(run) >= 3:
                    for a, b2 in zip(run[:-1], run[1:]):
                        tr = pcbnew.PCB_TRACK(board)
                        tr.SetStart(a.GetPosition()); tr.SetEnd(b2.GetPosition()); tr.SetWidth(FromMM(0.2))
                        tr.SetLayer(pcbnew.F_Cu if a.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu); tr.SetNetCode(a.GetNetCode()); tr.SetLocked(True); board.Add(tr)
                        n_bridge += 1
                    for q in run[1:-1]:
                        skip.add(q.GetNumber())
            for q in plist[1:]:
                a = run[-1]
                if math.hypot((q.GetPosition().x - a.GetPosition().x) / 1e6, (q.GetPosition().y - a.GetPosition().y) / 1e6) <= 0.55:
                    run.append(q)
                else:
                    flush(run); run = [q]
            flush(run)
    for pad in pads:
        netname = pad.GetNetname()
        if netname not in PLANE_NETS or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or pad.GetNumber() in tht_nums or pad.GetNumber() in skip:
            continue
        if (fp.GetReference(), pad.GetNumber()) in PREHANDLED:
            continue
        PREHANDLED.add((fp.GetReference(), pad.GetNumber()))        # 同番号の重複パッドは内部で繋がっている
        px, py = pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6
        sx, sy = pad.GetSize().x / 1e6, pad.GetSize().y / 1e6
        ang = -pad.GetOrientationDegrees()
        if fp.GetReference() == "J10":
            dx, dy = -1.0, 0.0                      # USB-C: 基板内側 (左) へ
        elif len(pads) <= 4:
            dx, dy = px - fx, py - fy
            if abs(dx) + abs(dy) < 1e-3: dx, dy = 1.0, 0.0
        else:
            ax = rot(1, 0, ang) if sx >= sy else rot(0, 1, ang)
            dx, dy = ax
            if (px - fx) * dx + (py - fy) * dy < 0: dx, dy = -dx, -dy
        L = math.hypot(dx, dy); dx, dy = dx / L, dy / L
        ex = abs(dx * rot(1, 0, ang)[0] + dy * rot(1, 0, ang)[1]) * sx / 2 + abs(dx * rot(0, 1, ang)[0] + dy * rot(0, 1, ang)[1]) * sy / 2
        d0 = ex + CLR + VIA_D / 2 + 0.1
        ey = abs(-dy * rot(1, 0, ang)[0] + dx * rot(1, 0, ang)[1]) * sx / 2 + abs(-dy * rot(0, 1, ang)[0] + dx * rot(0, 1, ang)[1]) * sy / 2
        e0 = ey + CLR + VIA_D / 2 + 0.1
        cands = [(d0, 0.0), (d0 + 0.4, 0.0), (d0 + 0.75, 0.0), (0.0, e0), (0.0, -e0), (d0 + 0.4, 0.6), (d0 + 0.4, -0.6),
                 (0.3, e0), (0.3, -e0), (-0.3, e0), (-0.3, -e0), (d0 + 1.1, 0.0), (d0 + 1.5, 0.0), (d0 + 1.1, 0.6), (d0 + 1.1, -0.6),
                 (d0 + 1.9, 0.0), (d0 + 2.25, 0.0), (d0 + 1.9, 0.6), (d0 + 1.9, -0.6)]
        if len(pads) > 4:
            cands += [(-d0, 0.0), (-d0 - 0.4, 0.0), (-d0 - 0.75, 0.0), (-d0 - 0.4, 0.6), (-d0 - 0.4, -0.6)]
        placed = False
        hw_stub = 0.1 if min(sx, sy) < 0.4 else 0.125
        pad_layer = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
        for d, lat in cands:
            vx, vy = px + dx * d - dy * lat, py + dy * d + dx * lat
            if len(pads) > 4 and lat != 0.0 and d > 0:
                mx, my = px + dx * (ex + 0.25), py + dy * (ex + 0.25)
            else:
                mx, my = px, py
            if clear_of(vx, vy, netname, mx, my, hw_stub, layer=pad_layer) and (mx == px or clear_of(mx, my, netname, px, py, hw_stub, via_check=False, layer=pad_layer)):
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(VECTOR2I(FromMM(vx), FromMM(vy))); via.SetDrill(FromMM(VIA_DRILL)); via.SetWidth(FromMM(VIA_D))
                via.SetViaType(pcbnew.VIATYPE_THROUGH); via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                via.SetNetCode(pad.GetNetCode()); via.SetLocked(True); board.Add(via)
                pts = [(px, py), (mx, my), (vx, vy)] if (mx, my) != (px, py) else [(px, py), (vx, vy)]
                for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
                    tr = pcbnew.PCB_TRACK(board)
                    tr.SetStart(VECTOR2I(FromMM(ax), FromMM(ay))); tr.SetEnd(VECTOR2I(FromMM(bx), FromMM(by)))
                    tr.SetWidth(FromMM(0.25 if min(sx, sy) >= 0.4 else 0.2)); tr.SetLayer(pad_layer)
                    tr.SetNetCode(pad.GetNetCode()); tr.SetLocked(True); board.Add(tr)
                    segs.append((ax, ay, bx, by, tr.GetWidth() / 2e6, netname, pad_layer))
                vias_placed.append((vx, vy, netname)); n_via += 1; placed = True
                break
        if not placed:
            n_fail.append(f"{fp.GetReference()}.{pad.GetNumber()}({netname})")
            if os.environ.get("FANOUT_DEBUG"):
                print("DEBUG", fp.GetReference(), pad.GetNumber(), netname, "pad", (round(px, 2), round(py, 2)), "dir", (round(dx, 2), round(dy, 2)))
                print("      candidates", len(cands), "reasons", len(WHY))
                for w_ in WHY: print("     ", w_)
        WHY.clear()
fail_pads = []
for fp in board.GetFootprints():
    for pad in fp.Pads():
        key = f"{fp.GetReference()}.{pad.GetNumber()}({pad.GetNetname()})"
        if key in n_fail:
            fail_pads.append((fp, pad))
placed_keys = set()
for fp, pad in fail_pads:
    px, py = pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6
    for other in fp.Pads():
        if other is pad or other.GetNetname() != pad.GetNetname():
            continue
        ox, oy = other.GetPosition().x / 1e6, other.GetPosition().y / 1e6
        if 0 < math.hypot(px - ox, py - oy) <= 0.6:
            tr = pcbnew.PCB_TRACK(board)
            tr.SetStart(VECTOR2I(FromMM(px), FromMM(py))); tr.SetEnd(VECTOR2I(FromMM(ox), FromMM(oy)))
            tr.SetWidth(FromMM(0.2)); tr.SetLayer(pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu)
            tr.SetNetCode(pad.GetNetCode()); tr.SetLocked(True); board.Add(tr)
            placed_keys.add(f"{fp.GetReference()}.{pad.GetNumber()}({pad.GetNetname()})"); break
n_fail = [k for k in n_fail if k not in placed_keys]
print(f"fanout vias: {n_via}  chained pads: {n_bridge}  bridged to neighbour: {len(placed_keys)}  failed: {len(n_fail)} {n_fail[:12]}")
if n_fail:
    open(os.path.join(OUT, "fanout_failed.txt"), "w").write("\n".join(n_fail) + "\n")
elif os.path.exists(os.path.join(OUT, "fanout_failed.txt")):
    os.remove(os.path.join(OUT, "fanout_failed.txt"))

# ---------------------------------------------------------------- 保存 (ゾーン塗りと DRC は pcb_drc.py で別プロセス)
pcbnew.SaveBoard(PCB, board)
print("saved", PCB, "tracks:", len(list(board.GetTracks())))
