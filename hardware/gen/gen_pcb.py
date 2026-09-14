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
    # ADV 右側の列 (縦置き)。0603 の前後は 2.4 mm、0402 同士は 2.0 mm
    col = cx + 9.0
    for ref, y in ((f"C{n}11", 26.0), (f"C{n}09", 28.0), (f"C{n}13", 30.0), (f"C{n}14", 32.0), (f"C{n}15", 34.4),
                   (f"C{n}04", 36.8), (f"C{n}07", 38.8), (f"C{n}12", 41.4), (f"C{n}08", 44.6)):
        place(ref, col, y, 90)
    # フェライトビーズ / 抵抗の列 (縦置き)
    col2 = cx + 11.0
    for ref, y in ((f"FB{n}1", 27.0), (f"FB{n}2", 30.2), (f"R{n}1", 32.8), (f"R{n}2", 35.0)):
        place(ref, col2, y, 90)
    # ADV 左上 (pin 29/31 用) の列。ADV のコートヤード (±6.7) から離す
    for ref, y in ((f"C{n}16", 23.7), (f"C{n}18", 25.9), (f"C{n}06", 28.6), (f"C{n}10", 30.6), (f"R{n}4", 32.8)):
        place(ref, cx - 9.2, y, 0)            # 横置き: ビアは左右へ。DVDD_3V 0.1u / 1u、DVDD (pin31)、AVDD (pin25)、CEC_CLK 0R
    place(f"R{n}3", cx - 9.2, 21.5, 0)        # INT 10k (+3V3 側のビアは島の外)
    place(f"C{n}05", cx - 7.5, 41.0, 0)       # DVDD (pin51) 0.1u
    # LDO 行: 入力 (3.3 V) 側を左、出力 (1.8 V) 側を右に分ける
    place(f"U{n}3", cx, 49.0, 0)
    place(f"C{n}01", cx - 6.5, 52.5, 0)       # 10u in (3.3 V): 島の外
    place(f"C{n}02", cx + 7.0, 49.0, 90)      # 22u out
    place(f"C{n}03", cx + 10.0, 49.0, 90)     # 0.1u out
# 電源部 (右辺、y >= 55)
place("J5", 109.5, 64.0, 90)                  # USB-C、開口部右
place("F1", 103.5, 54.5, 90)
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
place("H1", 12.7, 8.5); place("H2", 111.0, 6.0); place("H3", 111.0, 106.0); place("H4", 60.0, 106.0)

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
bds.m_MinThroughDrill = FromMM(0.2)
bds.m_HoleClearance = FromMM(0.18)
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
    if ref.startswith("H"):
        name = "MountingHole_3.2mm"             # パッドなしの取付穴 (コートヤードが小さい)
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
    fp.Reference().SetLayer(pcbnew.F_Fab if side == "F" else pcbnew.B_Fab)   # シルクには置かない (CPL で実装)
    fp.Value().SetVisible(False)
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
def zone_poly(netname, layer, pts, prio=0, name=""):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer); z.SetNetCode(net(netname).GetNetCode()); z.SetAssignedPriority(prio); z.SetZoneName(name or netname)
    o = z.Outline(); o.NewOutline()
    for x, y in pts:
        o.Append(FromMM(x), FromMM(y))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL); z.SetMinThickness(FromMM(0.2)); z.SetLocalClearance(FromMM(0.25))
    board.Add(z); return z
for n, cx in CX.items():
    # 本体: y 26.5..50.1 (左半分) / ..53 (右半分、LDO 出力側)。pin31 (x=cx-3.25) のビア用に上へ切り欠きを伸ばす
    zone_poly(f"CH{n}_1V8", pcbnew.In2_Cu,
              [(cx - 11.85, 26.5), (cx - 2.9, 26.5), (cx - 2.9, 29.6), (cx - 1.6, 29.6), (cx - 1.6, 26.5),   # pin29 用スロット
               (cx + 11.85, 26.5), (cx + 11.85, 53.0), (cx - 1.5, 53.0), (cx - 1.5, 50.1), (cx - 11.85, 50.1)], prio=1)

# テキスト
t = pcbnew.PCB_TEXT(board); t.SetText("QUAD HDMI TX  ADV7513 x4  rev A"); t.SetLayer(pcbnew.F_SilkS)
t.SetPosition(VECTOR2I(FromMM(60), FromMM(58))); t.SetTextSize(VECTOR2I(FromMM(1.5), FromMM(1.5))); board.Add(t)

# ---------------------------------------------------------------- TMDS 事前配線
def add_track(pts, netname, width=0.15, layer=pcbnew.F_Cu):
    ni = net(netname)
    for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(VECTOR2I(FromMM(x1), FromMM(y1))); t.SetEnd(VECTOR2I(FromMM(x2), FromMM(y2)))
        t.SetWidth(FromMM(width)); t.SetLayer(layer); t.SetNetCode(ni.GetNetCode()); t.SetLocked(True); board.Add(t)
def padpos(ref, num):
    fp = board.FindFootprintByReference(ref)
    for p in fp.Pads():
        if p.GetNumber() == num:
            return p.GetPosition().x / 1e6, p.GetPosition().y / 1e6
    raise KeyError((ref, num))
def pad_bottom(ref, num):
    fp = board.FindFootprintByReference(ref)
    for p in fp.Pads():
        if p.GetNumber() == num:
            return p.GetBoundingBox().GetBottom() / 1e6
    raise KeyError((ref, num))
n_tmds = 0
for n, cx in CX.items():
    adv, tpd, hd = f"U{n}1", f"U{n}2", f"J{n}"
    # (net, ADV pin, TPD pin, HDMI pin, 水平の y, 縦の x オフセット, レーン y)。左グループは左端から、右グループは右端から TPD 下へ入る
    left = [("TX1_N", "23", "20", "6", 24.85, -4.35, 20.35), ("TX1_P", "24", "21", "4", 25.30, -4.80, 19.90),
            ("TX2_N", "26", "22", "3", 25.75, -5.25, 19.45), ("TX2_P", "27", "23", "1", 26.20, -5.70, 19.00)]
    right = [("TX0_P", "21", "18", "7", 24.85, 4.35, 20.35), ("TX0_N", "20", "17", "9", 25.30, 4.80, 19.90),
             ("TXC_P", "18", "16", "10", 25.75, 5.25, 19.45), ("TXC_N", "17", "15", "12", 26.20, 5.70, 19.00)]
    for sig, pa, pt, ph, yh, xv, yl in left + right:
        netname = f"CH{n}_{sig}"
        xa, ya = padpos(adv, pa); xt, yt = padpos(tpd, pt); xc, yc = padpos(hd, ph)
        x_v = cx + xv
        y_d = pad_bottom(hd, ph) + 0.5                                             # コネクタパッド下端の少し下で斜めを終える
        pts = [(xa, ya), (xa, yh), (x_v, yh), (x_v, yl), (xt, yl), (xt, yt),      # ADV -> U ターン -> TPD パッド
               (xt, 16.6), (xc, y_d), (xc, yc)]                                    # TPD -> コネクタ
        add_track(pts, netname); n_tmds += 1
print("TMDS pre-routed lines:", n_tmds)

# ---------------------------------------------------------------- 囲われたパッドへの B.Cu アクセスビアと 5V_OUT
def add_via(x, y, netname, dia=0.6, drill=0.3):
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); via.SetDrill(FromMM(drill)); via.SetWidth(FromMM(dia))
    via.SetViaType(pcbnew.VIATYPE_THROUGH); via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNetCode(net(netname).GetNetCode()); via.SetLocked(True); board.Add(via)
def padnet(ref, num):
    fp = board.FindFootprintByReference(ref)
    for p in fp.Pads():
        if p.GetNumber() == num:
            return p.GetNetname()
n_access = 0
PREHANDLED = set()
for n, cx in CX.items():
    tpd, adv, hd = f"U{n}2", f"U{n}1", f"J{n}"
    # TPD 下段 (A/B 側信号と VCC5V): TMDS の U ターンに囲われているので本体下 (パッド列の間) にビアを置く。0.65 ピッチなので 2 段に互い違い
    for num, yv in (("1", 22.1), ("2", 20.95), ("3", 22.1), ("4", 20.95), ("7", 22.1), ("8", 20.95), ("9", 22.1), ("10", 20.95), ("11", 22.1)):
        x, y = padpos(tpd, num); nn = padnet(tpd, num)
        add_track([(x, y), (x, yv)], nn, width=0.15); add_via(x, yv, nn); n_access += 1
    # ADV 上辺で TMDS に挟まれた/覆われたピン: AVDD19, PD22, AVDD25 は y=28.6、INT28/CEC30/CEC_CLK32 は y=29.4 (29/31 のプレーン用ビアは 28.6 に来る)
    for num, yv, dia in (("19", 28.6, 0.6), ("22", 28.6, 0.6), ("25", 28.6, 0.6),
                         ("28", 28.7, 0.5), ("30", 28.7, 0.5), ("32", 28.7, 0.5), ("29", 29.9, 0.6), ("31", 29.9, 0.6)):
        x, y = padpos(adv, num); nn = padnet(adv, num)
        add_track([(x, y), (x, yv)], nn, width=0.15); add_via(x, yv, nn, dia=dia); n_access += 1
        PREHANDLED.add((adv, num))
    # 5V_OUT: TPD pin13 -> コネクタ pin18、C{n}20 pad1 -> pin13 側面
    x13, y13 = padpos(tpd, "13"); x18, y18 = padpos(hd, "18"); xc20, yc20 = padpos(f"C{n}20", "1")
    yb = pad_bottom(hd, "18") + 0.5
    add_track([(x13, y13), (x13, yb + 0.4), (x18, yb), (x18, y18)], f"CH{n}_5V_OUT", width=0.2)
    add_track([(xc20, yc20), (x13 + 0.7, yc20), (x13, yc20 + 0.3)], f"CH{n}_5V_OUT", width=0.2)
print("access vias:", n_access)

# ---------------------------------------------------------------- プレーン系ネットのファンアウトビア
# FreeRouting は内層プレーンへの接続 (パッド -> ビア) を作らないので、SMD パッドごとに先に打っておく。
import math
PLANE_NETS = {"GND", "+3V3"} | {f"CH{n}_1V8" for n in CX}
VIA_D, VIA_DRILL, CLR = 0.6, 0.3, 0.22
all_pads = []       # (x, y, hw, hh, net)  軸平行の近似矩形 (mm)
for fp in board.GetFootprints():
    for pad in fp.Pads():
        bb = pad.GetBoundingBox()
        all_pads.append((bb.GetCenter().x / 1e6, bb.GetCenter().y / 1e6, bb.GetWidth() / 2e6, bb.GetHeight() / 2e6, pad.GetNetname()))
vias_placed = [(v.GetPosition().x / 1e6, v.GetPosition().y / 1e6) for v in board.GetTracks() if v.GetClass() == "PCB_VIA"]
segs = []           # 既存配線 (x1, y1, x2, y2, halfwidth, net)
for t in board.GetTracks():
    if t.GetClass() == "PCB_TRACK":
        segs.append((t.GetStart().x / 1e6, t.GetStart().y / 1e6, t.GetEnd().x / 1e6, t.GetEnd().y / 1e6, t.GetWidth() / 2e6, t.GetNetname()))
def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0: return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
def clear_of(x, y, netname, sx0=None, sy0=None, hw_stub=0.1, via_check=True):
    """ビア (x,y) と、(sx0,sy0) から (x,y) への引き出し線が他ネットと干渉しないか。via_check=False なら線分だけ検査"""
    for px, py, hw, hh, pn in all_pads:
        if pn == netname:
            continue
        dx = max(abs(x - px) - hw, 0); dy = max(abs(y - py) - hh, 0)
        if via_check and math.hypot(dx, dy) < VIA_D / 2 + CLR:
            return False
        if sx0 is not None:
            # 引き出し線 vs パッド矩形 (矩形をビア半径ぶん近似で膨らませて線分距離)
            if seg_dist(px, py, sx0, sy0, x, y) < math.hypot(hw, hh) * 0.75 + hw_stub + CLR and max(abs(x - px) - hw, abs(y - py) - hh, abs(sx0 - px) - hw, abs(sy0 - py) - hh) < 0.6:
                return False
    for vx, vy in vias_placed:
        if via_check and math.hypot(x - vx, y - vy) < VIA_D + CLR:
            return False
        if sx0 is not None and seg_dist(vx, vy, sx0, sy0, x, y) < VIA_D / 2 + hw_stub + CLR:
            return False
    for x1, y1, x2, y2, hw, pn in segs:
        if pn == netname:
            continue
        if via_check and seg_dist(x, y, x1, y1, x2, y2) < VIA_D / 2 + hw + CLR:
            return False
        if sx0 is not None:
            # 線分同士の最短距離 (端点で近似)
            if min(seg_dist(sx0, sy0, x1, y1, x2, y2), seg_dist(x, y, x1, y1, x2, y2),
                   seg_dist(x1, y1, sx0, sy0, x, y), seg_dist(x2, y2, sx0, sy0, x, y)) < hw + hw_stub + CLR:
                return False
    if not (1.0 < x < W - 1.0 and 1.0 < y < H - 1.0):
        return False
    return True
def rot(vx, vy, deg):
    a = math.radians(deg); return (vx * math.cos(a) - vy * math.sin(a), vx * math.sin(a) + vy * math.cos(a))
n_via = 0; n_fail = []; n_bridge = 0
for fp in board.GetFootprints():
    pads = list(fp.Pads())
    tht_nums = {p.GetNumber() for p in pads if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH}
    fx, fy = fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6
    # 連続する同ネットの SMD パッド (QFP の GND 入力など) は数珠つなぎにして両端だけビアを打つ
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
        px, py = pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6
        sx, sy = pad.GetSize().x / 1e6, pad.GetSize().y / 1e6
        ang = -pad.GetOrientationDegrees()          # KiCad は y 下向き座標。画面上の回転を数学座標へ
        if fp.GetReference() in ("J1", "J2", "J3", "J4"):
            dx, dy = 0.0, -1.0                      # HDMI コネクタ: 上 (筐体側) へ。下は TMDS の扇形配線
        elif len(pads) <= 4:
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
                 (0.3, e0), (0.3, -e0), (-0.3, e0), (-0.3, -e0), (d0 + 1.5, 0.0), (d0 + 1.1, 0.6), (d0 + 1.1, -0.6), (d0 + 2.25, 0.0),
                 (-d0, 0.0), (-d0 - 0.75, 0.0), (-d0 - 0.4, 0.6), (-d0 - 0.4, -0.6)]      # 最後は内向き (IC の本体下)
        placed = False
        hw_stub = 0.1 if min(sx, sy) < 0.4 else 0.125
        for d, lat in cands:
            vx, vy = px + dx * d - dy * lat, py + dy * d + dx * lat
            # 途中点: IC パッドではパッド先端 + 0.25 mm までまっすぐ出る (横候補でも隣のパッドをかすめない)
            if len(pads) > 4 and lat != 0.0 and d > 0:
                mx, my = px + dx * (ex + 0.25), py + dy * (ex + 0.25)
            else:
                mx, my = px, py
            if clear_of(vx, vy, netname, mx, my, hw_stub) and (mx == px or clear_of(mx, my, netname, px, py, hw_stub, via_check=False)):
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(VECTOR2I(FromMM(vx), FromMM(vy))); via.SetDrill(FromMM(VIA_DRILL)); via.SetWidth(FromMM(VIA_D))
                via.SetViaType(pcbnew.VIATYPE_THROUGH); via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                via.SetNetCode(pad.GetNetCode()); via.SetLocked(True); board.Add(via)
                pts = [(px, py), (mx, my), (vx, vy)] if (mx, my) != (px, py) else [(px, py), (vx, vy)]
                for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
                    tr = pcbnew.PCB_TRACK(board)
                    tr.SetStart(VECTOR2I(FromMM(ax), FromMM(ay))); tr.SetEnd(VECTOR2I(FromMM(bx), FromMM(by)))
                    tr.SetWidth(FromMM(0.25 if min(sx, sy) >= 0.4 else 0.2)); tr.SetLayer(pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu)
                    tr.SetNetCode(pad.GetNetCode()); tr.SetLocked(True); board.Add(tr)
                    segs.append((ax, ay, bx, by, tr.GetWidth() / 2e6, netname))
                vias_placed.append((vx, vy)); n_via += 1; placed = True
                break
        if not placed:
            n_fail.append(f"{fp.GetReference()}.{pad.GetNumber()}({netname})")
# 置けなかったパッド: 0.6 mm 以内の同ネットパッド (同一部品) に短絡配線して、隣のビアに相乗りする
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
        {"name": "Power", "clearance": 0.15, "track_width": 0.5, "via_diameter": 0.8, "via_drill": 0.4,
         "diff_pair_width": 0.2, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "microvia_diameter": 0.3, "microvia_drill": 0.1,
         "bus_width": 12, "line_style": 0, "wire_width": 6, "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)"}],
    "meta": {"version": 3},
    "netclass_patterns": [{"pattern": "CH*_TX*", "netclass": "TMDS"}] +
                         [{"pattern": p, "netclass": "Power"} for p in ("+5V", "+3V3", "VBUS", "CH*_1V8", "CH*_AVDD", "CH*_PVDD", "CH*_5V_OUT", "SW", "FPGA_5V")]
}
pro["board"]["design_settings"] = {
    "rules": {"min_clearance": 0.15, "min_track_width": 0.15, "min_via_diameter": 0.5, "min_through_hole_diameter": 0.2, "min_hole_clearance": 0.18,
              "min_via_annular_width": 0.1, "min_copper_edge_clearance": 0.3, "solder_mask_clearance": 0.0, "solder_mask_min_width": 0.0},
    "defaults": {}, "track_widths": [0.15, 0.2, 0.3, 0.5], "via_dimensions": [{"diameter": 0.5, "drill": 0.3}, {"diameter": 0.8, "drill": 0.4}],
    "diff_pair_dimensions": [{"width": 0.15, "gap": 0.15, "via_gap": 0.25}]
}
json.dump(pro, open(pro_path, "w"), indent=2)
print("project updated")
