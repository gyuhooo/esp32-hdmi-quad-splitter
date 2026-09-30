#!/usr/bin/env python3
"""ネットリストから KiCad 基板を生成する: 部品配置、外形、プレーン、ネットクラス、事前配線、ファンアウトビア。
使い方: gen_pcb.py            -> quad_hdmi_tx.kicad_pcb (未配線) と drc_pre.rpt

rev B: 細長い基板 (115 x 38 mm、6 層)。HDMI 4 個を 25.4 mm ピッチで上辺に並べ、
FPGA ヘッダ (2x40 SMD x2) は裏面に横向きに置く。ヘッダの列 (2.54 mm) は ADV の真下に並ぶ。
"""
import os, sys, json, re, math
import pcbnew
from pcbnew import VECTOR2I, FromMM
sys.path.insert(0, os.path.dirname(__file__))
from sexp import parse, find, find1

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "quad_hdmi_tx"))
PCB = os.path.join(OUT, "quad_hdmi_tx.kicad_pcb")
FPLIB = "/usr/share/kicad/footprints/"
W, H = 115.0, 38.0          # 基板外形 mm (縦 = 横の 0.33)

# ---------------------------------------------------------------- 主要寸法
PITCH = 25.4                                   # HDMI / チャネルのピッチ (= ヘッダ 10 列)
CX = {n: 13.5 + PITCH * (n - 1) for n in (1, 2, 3, 4)}
YT = 18.0                                      # TPD12S016 中心。TMDS パッド上段 y=YT-2.86、A 側下段 y=YT+2.86
YA = 30.4                                      # ADV7513 中心 (rot 180: TMDS 上辺 y=YA-5.68、データ 下辺 y=YA+5.68)
XH = 51.6                                      # ヘッダ中心 x。列 1 は x=2.07 (= CX[1]-11.43)、以後 2.54 ずつ右
YJ7, YJ8 = 18.2, 33.6                          # ヘッダ中心 y (裏面)。J7 のパッド 2 列の隙間 (y 17.25..19.15) に TPD のビアが入る
# 裏面ヘッダのパッド (1.0 mm 幅、2.54 ピッチ) の隙間の中心は x = cx + 2.54*m。ビアはそこへ寄せる

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
# 縦置き 2 端子部品の列: パッド中心のオフセット p、パッドの半分の長さ ph、ビアはパッド中心から ph+0.62 外側
PKG = {"0402": (0.5, 0.28), "0603": (0.8, 0.475), "0805": (0.95, 0.6)}
def stack(x, y_first_via, items, side="F"):
    """items: [(ref, pkg, rot)] を上から順に、上側のビアが y_first_via に来るように置く。隣同士のビア間隔 0.9"""
    y_via = y_first_via
    for ref, pkg, rot in items:
        p, ph = PKG[pkg]
        v = p + ph + 0.62
        yc = y_via + v
        place(ref, x, yc, rot, side)
        y_via = yc + v + 0.9

place("J7", XH, YJ7, 90, "B")
place("J8", XH, YJ8, 90, "B")
for n, cx in CX.items():
    # 表面: HDMI (上辺、"PCB Edge" 線を y=0 に)、TPD、ADV
    place(f"J{n}", cx, 7.02, 90)
    place(f"U{n}2", cx, YT, 90)
    place(f"U{n}1", cx, YA, 180)
    # 2 端子部品は縦置きで、x は裏面ヘッダのパッド列の隙間の中心 (cx ± 2.54 m) に置く。縦置きの外向きビアがヘッダのパッドに当たらない。
    # 同じ列で隣り合う部品は、向かい合うパッドのビア同士が 0.82 mm 以上離れるよう stack() で並べる。
    # rot 90 ではパッド 1 (回路図で先に書いたネット) が下側 (+y)、パッド 2 (GND など) が上側
    place(f"C{n}20", cx + 5.08, 14.6, 270)    # 5V_OUT (pin13) 0.1u。GND (pad2) は下 (ビアは TMDS の U ターンの上端 y=16.5 の上、(cx+5.08, 15.9))
    stack(cx + 7.62, 14.8, [(f"C{n}19", "0402", 90), (f"C{n}18", "0603", 90)])          # VCC5V (pin11) 0.1u、DVDD_3V 1u (+3V3、島の上)
    stack(cx - 7.62, 13.4, [(f"C{n}17", "0402", 90)])                                  # +3V3: VCCA 0.1u
    stack(cx - 10.3, 14.6, [(f"R{n}3", "0402", 90)])   # INT pull-up。x=cx-10.3: 左の内層通路 (x=cx-8.2..-9.7) を空ける
    place(f"R{n}2", cx + 1.9, 27.3, 0, "B")   # PD/AD 選択 (10k): 裏面、pin22 のビア (cx+1.25, 26.0) の真下
    place(f"C{n}03", cx + 12.7, 20.0, 90)     # LDO 出力 0.1u (1V8): 島の首 (x = cx+7.7..13.2) の上
    # ADV まわり (y >= 22.6)。右: AVDD/PVDD 系、左: 1V8 系 (島の中、x >= cx-11.3)
    place(f"R{n}1", cx + 7.62, 24.8, 90)      # REXT (GND=pad2 上、ビア y=23.4)。REXT 側は pin14 (y=27.65) へ
    place(f"C{n}13", cx + 7.62, 27.7, 90)     # PVDD 0.1u (GND=pad2 上、ビア y=26.3)。この列の y>=28.6 は ADV 右辺ピン (1/3/10/11) のビア
    stack(cx + 10.16, 22.6, [(f"FB{n}1", "0603", 90), (f"C{n}09", "0402", 90), (f"C{n}10", "0402", 90), (f"C{n}11", "0402", 90)])  # 1V8->AVDD、AVDD 0.1u x3
    stack(cx + 12.7, 22.6, [(f"FB{n}2", "0603", 90), (f"C{n}12", "0603", 90), (f"C{n}15", "0603", 90)])  # 1V8->PVDD、AVDD 10u、PVDD 1u
    # x = cx-7.62 の列は ADV 左辺ピンのエスケープビアが使うので部品を置かない
    stack(cx - 10.3, 23.4, [(f"C{n}04", "0402", 90), (f"C{n}05", "0402", 90), (f"C{n}06", "0402", 90)])   # 1V8 0.1u x3 (上のビア y=23.4 は島の外 = GND 側)
    place(f"C{n}14", cx + 10.16, 27.9, 90, "B")  # PVDD 0.1u: 裏面の帯、GND (pad2) を上に (後で向きを確認)
    # 裏面の J7-J8 の間の帯 (y 22.65..29.15)
    place(f"C{n}07", cx + 5.5, 7.4, 90, "B")     # 1V8 0.1u: LDO の脇。1V8 (pad1) を上にして LDO 出力の配線 (y=5.8) に直結
    place(f"R{n}4", cx - 3.81, 24.1, 90, "B")    # CEC_CLK 0R -> GND: J7 列 4 下段 (GND) の真下、GND パッドは上 (J7 pin8 の裏面配線に直結)
    place(f"C{n}16", cx - 0.25, 24.4, 90, "B")   # DVDD_3V 0.1u: 裏面、pin29 のビアの脇。+3V3 パッド (下) は pin29 のビアへ裏面で直結
    # 裏面: LDO は HDMI の真裏 (シェルタブの穴の間)、その下にコンデンサ。1V8 のものは島の首 (x = cx+7.7..12.2) の上
    place(f"U{n}3", cx, 5.8, 0, "B")
    place(f"C{n}01", cx - 10.9, 10.4, 90, "B")  # 10u in (+3V3): 左端、縦置き (内層の通路とヘッダ列 1 のビア (cx-11.43, 13.3) を避ける)
    place(f"C{n}02", cx + 10.16, 11.9, 90, "B")  # 22u out (1V8): 縦置き、両パッドのビアがヘッダ列の隙間 x=cx+10.16 かつ首の中
    place(f"C{n}08", cx + 12.7, 11.9, 90, "B")   # 1V8 10u: 同上 (x=cx+12.7)
# I2C プルアップ: I2C_A は OUT1 の TPD 右、I2C_B は OUT3 の TPD 右
# 各チャネルの裏面、J7-J8 の間の帯の上端 (x=cx-7.62 はヘッダ列の隙間)。+3V3 (pad1) は上 (y<24.5、島の外) に向ける (後で向きを確認)
for i, n in enumerate((1, 2, 3, 4)):
    place(f"R{i+1}", CX[n] - 7.62, 23.6, 90, "B")
# 電源部 (右端 x >= 103)
place("J5", W - 3.67, 10.0, 90)               # USB-C、開口部右。"PCB Edge" 線 (中心から 3.67 mm) を x=W に合わせる
place("R5", 104.5, 6.0, 0)
place("R6", 104.5, 8.0, 0)
place("F1", 104.5, 12.0, 90)
place("C54", 105.5, 15.6, 0)
place("U5", 105.5, 18.5, 0)
place("C52", 105.5, 22.3, 0)
place("C53", 105.5, 24.8, 0)
place("R7", 105.5, 27.3, 0)
place("C51", 107.8, 16.0, 0)
place("L1", 110.0, 19.5, 0)
place("C55", 110.0, 24.3, 0)
place("C56", 110.0, 26.8, 0)
place("D1", 108.0, 2.5, 0)
place("R8", 104.5, 2.5, 0)
place("J6", 105.5, 31.0, 0)
place("JP1", 109.0, 30.5, 0, "B")
place("H1", 26.2, 3.0); place("H2", 51.6, 3.0); place("H4", 77.0, 3.0); place("H3", 112.0, 35.0)

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
        name = "MountingHole_3.2mm_M3"          # パッドなしの取付穴 (コートヤードが小さい)
    fp = pcbnew.FootprintLoad(FPLIB + lib + ".pretty", name)
    if fp is None:
        missing.append(c["fp"]); continue
    fp.SetReference(ref); fp.SetValue(c["value"])
    if ref not in PL:
        missing.append(f"noplace:{ref}"); PL[ref] = (20 + 5 * (len(missing) % 15), 20 + 5 * (len(missing) // 15), 0, "F")
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
def padnet(ref, num):
    fp = board.FindFootprintByReference(ref)
    for p in fp.Pads():
        if p.GetNumber() == num:
            return p.GetNetname()

# 裏面ヘッダ: 列 1 (ピン 1/2) が左端に来る向きにする。列 k の中心 x = XH - 49.53 + 2.54 (k-1)
for ref in ("J7", "J8"):
    if padpos(ref, "1")[0] > padpos(ref, "79")[0]:
        board.FindFootprintByReference(ref).SetOrientationDegrees(-90)
    x1 = padpos(ref, "1")[0]
    assert abs(x1 - (CX[1] - 11.43)) < 0.02, (ref, x1)
    fp = board.FindFootprintByReference(ref)
    for it in list(fp.GraphicalItems()):
        if it.GetLayer() == pcbnew.B_CrtYd:
            fp.Remove(it)
    sh = pcbnew.FP_SHAPE(fp); sh.SetShape(pcbnew.SHAPE_T_RECT); sh.SetLayer(pcbnew.B_CrtYd); sh.SetWidth(FromMM(0.05))
    sh.SetStart0(VECTOR2I(FromMM(-4.45), FromMM(-50.3))); sh.SetEnd0(VECTOR2I(FromMM(4.45), FromMM(50.3))); fp.Add(sh); sh.SetDrawCoord()
# 裏面 C07: 1V8 (pad1) を上 (-y、LDO 出力配線側) に。R1-R4: +3V3 (pad1) を上に。C14: GND (pad2) を上に
def pad_up(ref, num_up, num_dn):
    if padpos(ref, num_up)[1] > padpos(ref, num_dn)[1]:
        fp = board.FindFootprintByReference(ref); fp.SetOrientationDegrees(fp.GetOrientationDegrees() + 180)
for n, cx in CX.items():
    pad_up(f"C{n}07", "1", "2"); pad_up(f"C{n}14", "2", "1")
for i in (1, 2, 3, 4):
    pad_up(f"R{i}", "1", "2")
# 裏面 LDO: タブ (pin2 の大きい方) が +x 側 (島の首側) に来る向きにする
for n, cx in CX.items():
    fp = board.FindFootprintByReference(f"U{n}3")
    tab = max((p for p in fp.Pads() if p.GetNumber() == "2"), key=lambda p: p.GetSize().x * p.GetSize().y)
    if tab.GetPosition().x / 1e6 < cx:
        fp.SetOrientationDegrees(fp.GetOrientationDegrees() + 180)

# 外形
def seg(x1, y1, x2, y2, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(VECTOR2I(FromMM(x1), FromMM(y1))); s.SetEnd(VECTOR2I(FromMM(x2), FromMM(y2)))
    s.SetLayer(layer); s.SetWidth(FromMM(w)); board.Add(s)
for a, b in (((0, 0), (W, 0)), ((W, 0), (W, H)), ((W, H), (0, H)), ((0, H), (0, 0))):
    seg(a[0], a[1], b[0], b[1])

# プレーン: In1 = GND、In4 = +3V3 に CHn_1V8 の島 (ADV の下 + LDO へ伸びる首)
def zone_poly(netname, layer, pts, prio=0, name=""):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer); z.SetNetCode(net(netname).GetNetCode()); z.SetAssignedPriority(prio); z.SetZoneName(name or netname)
    o = z.Outline(); o.NewOutline()
    for x, y in pts:
        o.Append(FromMM(x), FromMM(y))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL); z.SetMinThickness(FromMM(0.2)); z.SetLocalClearance(FromMM(0.25))
    z.SetIsFilled(False)
    board.Add(z); return z
zone_poly("GND", pcbnew.In1_Cu, [(0, 0), (W, 0), (W, H), (0, H)])
zone_poly("+3V3", pcbnew.In4_Cu, [(0, 0), (W, 0), (W, H), (0, H)])
ISL_L, ISL_R, ISL_TOP = -11.3, 13.4, 24.5     # 島の本体 (cx 相対)。+3V3 のビア (pin29 の逃げ、TPD 周り) は y < 24.5 に置く
NECK_L, NECK_R = 8.7, 13.8                     # 首: LDO 出力ビア (cx+9.6, 5.8)、C02 / C08 (裏面)、C03 (表面) のビアを含む。C18/C19 の列 (cx+7.62) は外
for n, cx in CX.items():
    zone_poly(f"CH{n}_1V8", pcbnew.In4_Cu,
              [(cx + NECK_L, 4.0), (cx + NECK_R, 4.0), (cx + NECK_R, ISL_TOP), (cx + ISL_R, ISL_TOP), (cx + ISL_R, H),
               (cx + ISL_L, H), (cx + ISL_L, ISL_TOP), (cx + NECK_L, ISL_TOP)], prio=1)

# テキスト
t = pcbnew.PCB_TEXT(board); t.SetText("HDMI TX rev B"); t.SetLayer(pcbnew.F_SilkS)
t.SetPosition(VECTOR2I(FromMM(108.5), FromMM(37.3))); t.SetTextSize(VECTOR2I(FromMM(0.8), FromMM(0.8))); t.SetTextThickness(FromMM(0.12)); board.Add(t)

# ---------------------------------------------------------------- 事前配線ユーティリティ
def add_track(pts, netname, width=0.15, layer=pcbnew.F_Cu):
    ni = net(netname)
    for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
        if abs(x1 - x2) < 1e-6 and abs(y1 - y2) < 1e-6:
            continue
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(VECTOR2I(FromMM(x1), FromMM(y1))); t.SetEnd(VECTOR2I(FromMM(x2), FromMM(y2)))
        t.SetWidth(FromMM(width)); t.SetLayer(layer); t.SetNetCode(ni.GetNetCode()); t.SetLocked(True); board.Add(t)
def add_via(x, y, netname, dia=0.6, drill=0.3):
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(VECTOR2I(FromMM(x), FromMM(y))); via.SetDrill(FromMM(drill)); via.SetWidth(FromMM(dia))
    via.SetViaType(pcbnew.VIATYPE_THROUGH); via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNetCode(net(netname).GetNetCode()); via.SetLocked(True); board.Add(via)

# ---------------------------------------------------------------- TMDS 事前配線 (表面のみ、ビアなし)
# ADV 上辺 -> 上へ -> 横へ (yh レーン) -> TPD の脇を上へ -> TPD 本体下 (yl レーン) -> TPD パッド -> 斜めにコネクタへ
n_tmds = 0
for n, cx in CX.items():
    adv, tpd, hd = f"U{n}1", f"U{n}2", f"J{n}"
    # (net, ADV pin, TPD pin, HDMI pin, yh, x_v オフセット, yl)。左グループは左端から、右グループは右端から TPD 下へ入る
    left = [("TX1_N", "23", "20", "6", YT + 4.35, -4.35, YT - 0.30), ("TX1_P", "24", "21", "4", YT + 4.80, -4.80, YT - 0.70),
            ("TX2_N", "26", "22", "3", YT + 5.25, -5.25, YT - 1.10), ("TX2_P", "27", "23", "1", YT + 5.70, -5.70, YT - 1.50)]
    right = [("TX0_P", "21", "18", "7", YT + 4.35, 4.35, YT - 0.30), ("TX0_N", "20", "17", "9", YT + 4.80, 4.80, YT - 0.70),
             ("TXC_P", "18", "16", "10", YT + 5.25, 5.25, YT - 1.10), ("TXC_N", "17", "15", "12", YT + 5.70, 5.70, YT - 1.50)]
    for sig, pa, pt, ph, yh, xv, yl in left + right:
        netname = f"CH{n}_{sig}"
        xa, ya = padpos(adv, pa); xt, yt = padpos(tpd, pt); xc, yc = padpos(hd, ph)
        x_v = cx + xv
        y_d = pad_bottom(hd, ph) + 0.5                                             # コネクタパッド下端の少し下で斜めを終える
        pts = [(xa, ya), (xa, yh), (x_v, yh), (x_v, yl), (xt, yl), (xt, yt),
               (xt, YT - 3.9), (xc, y_d), (xc, yc)]
        add_track(pts, netname); n_tmds += 1
print("TMDS pre-routed lines:", n_tmds)

# ---------------------------------------------------------------- 囲われたパッドのアクセスビア、5V_OUT、LDO 出力、EP サーマルビア、ヘッダへの事前配線
# 座標は全て cx 相対 (右が +x、下が +y)。内層: SIG1 = In2、SIG2 = In3。
# 事前配線の方針 (rev B2):
#   J8 (下側ヘッダ): ADV 下辺 (D0-D11/CLK/DE/HS) はエスケープビア (y=33.35/34.0 = J8 の 2 列の隙間) から裏面で真下のパッドへ落とすか、
#     内層 SIG2 で y=34.8..36.5 の横レーンを通って列 1-2/9 の隙間ビアへ。列 4-7 上段は GND (EP のサーマルビアに裏面で直結)。
#   J7 (上側ヘッダ): ADV 左辺 (D12-D23) は左の内層通路 (x=cx-8.19..-9.69、SIG1/SIG2 各 6 レーン) を上り、
#     列 1-2 の隙間ビア、ヘッダの上 (y=11.2..12.1) の横レーン経由で列 5-8 の上段、または ADV 脇の帯 (x=cx-6.35..-5.5) を上って列 3-4 へ。
#     下辺の D1/D2/D4/D5/D10 は ADV 右脇の通路 (x=cx+3.35/3.65/3.95) を上り、y=24.0..24.6 のレーンで右の列 8-10 へ。
#   交差しないレーン割り当ての規則: 右に曲がる縦通路は「右の通路ほど低い横レーン」、横レーンから下に曲がる先は「左ほど低いレーン」。
IN2, IN3, BCU, FCU = pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu, pcbnew.F_Cu
n_access = 0
PREHANDLED = set()
for n, cx in CX.items():
    tpd, adv, hd, ldo = f"U{n}2", f"U{n}1", f"J{n}", f"U{n}3"
    base7 = base8 = 20 * (n - 1)
    def T(pts, nn, layer=FCU, w=0.15):
        add_track([(cx + px, py) for px, py in pts], nn, width=w, layer=layer)
    def V(x, y, nn, d=0.5):
        global n_access
        add_via(cx + x, y, nn, dia=d); n_access += 1
    def jpad(ref, col, upper):
        """ヘッダ ref の列 col (1..10、このチャネル) の上段/下段パッド: (pin, x_rel, y)"""
        pin = 20 * (n - 1) + 2 * col - (1 if upper else 0)
        xp, yp = padpos(ref, str(pin))
        assert abs(xp - (cx - 11.43 + 2.54 * (col - 1))) < 0.03, (ref, col, xp)
        return pin, xp - cx, yp
    def jnet(ref, col, upper):
        return padnet(ref, str(20 * (n - 1) + 2 * col - (1 if upper else 0)))
    # ---- TPD A 側 (pin 1-11): TMDS の U ターンに囲われているので本体下にビア。偶数ピンは y=YT+0.3、奇数は YT+0.7 (0.65 ピッチを 2 段に)
    # この帯 (y 18.05..18.95) は裏面 J7 のパッド 2 列の隙間 (17.25..19.15) に入る
    tpd_via = {}
    for num in ("1", "2", "3", "4", "6", "7", "8", "9", "10", "11"):
        x, y = padpos(tpd, num); nn = padnet(tpd, num)
        yv = YT + (0.3 if int(num) % 2 == 0 else 0.7)
        add_track([(x, y), (x, yv)], nn, width=0.15); add_via(x, yv, nn, dia=0.5); n_access += 1
        PREHANDLED.add((tpd, num)); tpd_via[num] = (x - cx, yv)
    # LS_OE(5) / CT_HPD(12) = +3V3: TMDS 左右グループの隙間 (x=cx+1.25) に 0.5 mm ビアを置き、パッド下端の下 y=YT+3.95 のバーで接続
    x5, y5 = padpos(tpd, "5"); x12, y12 = padpos(tpd, "12")
    add_via(cx + 1.25, YT + 4.8, "+3V3", dia=0.5)
    add_track([(cx + 1.25, YT + 4.8), (cx + 1.25, YT + 3.95), (x5, YT + 3.95), (x5, y5)], "+3V3", width=0.15)
    add_track([(cx + 1.25, YT + 3.95), (x12, YT + 3.95), (x12, y12)], "+3V3", width=0.15)
    PREHANDLED.add((tpd, "5")); PREHANDLED.add((tpd, "12"))
    # VCCA (pin24, +3V3、上段左端): 左へ引き出してヘッダ列の隙間 x=cx-5.08 にビア
    x24, y24 = padpos(tpd, "24")
    add_track([(x24, y24), (cx - 5.08, y24)], "+3V3", width=0.15); add_via(cx - 5.08, y24, "+3V3", dia=0.5); n_access += 1
    PREHANDLED.add((tpd, "24"))
    x19, y19 = padpos(tpd, "19"); x6, _ = padpos(tpd, "6")
    assert abs(x19 - x6) < 0.01
    add_track([(x19, y19), (x19, YT + 0.3)], "GND", width=0.15)               # pin6 のビア (x6, YT+0.3) に乗る
    PREHANDLED.add((tpd, "19"))
    # ---- ADV 上辺で TMDS に挟まれた/覆われたピン: 19/22/25/28/30/32 は y=YA-4.4、29/31 は YA-3.8 (0.5 ピッチを 2 段に)。裏面はヘッダの間の帯
    top_via = {}
    for num, yv in (("19", YA - 4.4), ("22", YA - 4.4), ("25", YA - 4.4), ("28", YA - 4.4), ("30", YA - 4.4), ("32", YA - 4.4),
                    ("29", YA - 3.8), ("31", YA - 3.8)):
        x, y = padpos(adv, num); nn = padnet(adv, num)
        add_track([(x, y), (x, yv)], nn, width=0.15); add_via(x, yv, nn, dia=0.5); n_access += 1
        PREHANDLED.add((adv, num)); top_via[num] = (x - cx, yv)
    # DVDD_3V (pin29, +3V3) のビアは 1V8 の島の中: SIG1 で上辺のビアの間を抜けて TPD の +3V3 バーのビア (cx+1.25, YT+4.8) へ
    x29, y29v = top_via["29"]
    assert abs(x29 + 2.25) < 0.02 and abs(y29v - 26.6) < 0.02, (x29, y29v)
    T([(x29, y29v), (x29, 25.4), (1.25, 25.4), (1.25, YT + 4.8)], "+3V3", IN3)
    # C16 (DVDD_3V 0.1u、裏面 (cx-0.25, 24.4)): GND パッド (上) は TMDS の縦線の間 (cx-0.25, 23.3) の 0.5 ビア、+3V3 パッド (下) は pin29 のビアへ裏面で
    xc, yc = padpos(f"C{n}16", "2"); assert padnet(f"C{n}16", "2") == "GND" and abs(xc - (cx - 0.25)) < 0.02 and abs(yc - 23.9) < 0.05, (xc, yc)
    T([(-0.25, yc), (-0.25, 23.3)], "GND", BCU, 0.2); V(-0.25, 23.3, "GND")
    xc, yc = padpos(f"C{n}16", "1"); assert padnet(f"C{n}16", "1") == "+3V3" and abs(yc - 24.9) < 0.05, (xc, yc)
    T([(-0.25, yc), (-0.25, 25.3), (x29, 25.3), (x29, y29v)], "+3V3", BCU, 0.2)
    PREHANDLED.add((f"C{n}16", "1")); PREHANDLED.add((f"C{n}16", "2"))
    # ---- 5V_OUT: TPD pin13 -> コネクタ pin18、C{n}20 pad1 -> pin13 側面。C20 の GND (上) は右脇 (cx+5.6, 14.1) のビア (真上は裏面の横レーンの通路)
    x13, y13 = padpos(tpd, "13"); x18, y18 = padpos(hd, "18"); xc20, yc20 = padpos(f"C{n}20", "1")
    yb = pad_bottom(hd, "18") + 0.5
    add_track([(x13, y13), (x13, yb + 0.4), (x18, yb), (x18, y18)], f"CH{n}_5V_OUT", width=0.2)
    add_track([(xc20, yc20), (x13 + 0.7, yc20), (x13, yc20 + 0.5)], f"CH{n}_5V_OUT", width=0.2)
    xg, yg = padpos(f"C{n}20", "2"); assert padnet(f"C{n}20", "2") == "GND" and abs(yg - 15.08) < 0.05, yg
    T([(xg - cx, yg), (5.08, 15.9)], "GND", FCU, 0.25); V(5.08, 15.9, "GND", 0.6)
    PREHANDLED.add((f"C{n}20", "2"))
    # ---- LDO 出力: 小さい pin2 -> タブ -> 右へ -> 首の中のビア (裏面)
    fp = board.FindFootprintByReference(ldo)
    p2 = sorted((p for p in fp.Pads() if p.GetNumber() == "2"), key=lambda p: p.GetSize().x * p.GetSize().y)
    (xs, ys), (xb, yb2) = (p2[0].GetPosition().x / 1e6, p2[0].GetPosition().y / 1e6), (p2[1].GetPosition().x / 1e6, p2[1].GetPosition().y / 1e6)
    add_track([(xs, ys), (xb, yb2), (cx + 9.6, yb2)], f"CH{n}_1V8", width=0.5, layer=pcbnew.B_Cu)
    add_via(cx + 9.6, yb2, f"CH{n}_1V8", dia=0.8, drill=0.4); n_access += 1
    PREHANDLED.add((ldo, "2"))
    x7, y7 = padpos(f"C{n}07", "1")
    add_track([(x7, y7), (x7, yb2)], f"CH{n}_1V8", width=0.3, layer=pcbnew.B_Cu)      # C07 の 1V8 パッド -> LDO 出力の配線
    PREHANDLED.add((f"C{n}07", "1"))
    for num in ("1", "3"):
        xq, yq = padpos(ldo, num); nn = padnet(ldo, num)
        add_track([(xq, yq), (cx - 5.6, yq)], nn, width=0.3, layer=pcbnew.B_Cu); add_via(cx - 5.6, yq, nn); n_access += 1
        PREHANDLED.add((ldo, num))
    # ---- ADV 下辺 (pin 49-64) のエスケープビア: 本体下、EP (y<=YA+2.5) と パッド内端 (YA+4.9) の間の 2 段 (YA+2.95 / YA+3.6 = J8 の 2 列の隙間)。
    bot = {}                                        # net -> (x_rel, y_via)
    for k, pin in enumerate(range(49, 65)):
        x, y = padpos(adv, str(pin)); nn = padnet(adv, str(pin))
        if not nn:
            continue
        yv = YA + (2.95 if k % 2 else 3.6)
        assert abs(x - (cx - 3.75 + 0.5 * k)) < 0.02
        add_track([(x, y), (x, yv)], nn, width=0.15); add_via(x, yv, nn, dia=0.5)
        PREHANDLED.add((adv, str(pin))); n_access += 1; bot[nn] = (x - cx, yv)
    # ---- ADV 左辺 (pin 33-48) のエスケープビア:
    #   上 5 本 (33-37) は x=cx-7.0 / -7.62 に交互、中 8 本 (38-45) は隙間の列 x=cx-7.62 に 0.65 ピッチ (斜めの引き出し)、
    #   46/47 (D14/D13) は本体下 (J8 の 2 列の隙間)、48 (D12) は左下 (cx-6.9, 34.0) から裏面で J8 列 3 下段へ
    left = {}
    for k, pin in enumerate(range(33, 49)):
        x, y = padpos(adv, str(pin)); nn = padnet(adv, str(pin))
        if not nn:
            continue
        if k <= 4:
            xv = cx - (7.0 if k % 2 == 0 else 7.62)
            add_track([(x, y), (xv, y)], nn, width=0.15); add_via(xv, y, nn, dia=0.5); left[nn] = (xv - cx, y)
        elif k <= 12:
            yv = 29.15 + 0.65 * (k - 5)
            xe = cx - (6.6 if k <= 9 else 6.4)              # ずれが大きい下側は斜めを浅くする
            add_track([(x, y), (xe, y), (cx - 7.62, yv)], nn, width=0.15); add_via(cx - 7.62, yv, nn, dia=0.5); left[nn] = (-7.62, yv)
        elif k == 13:   # pin46 (D14): 本体下 (y=33.15 は J8 の 2 列の隙間)
            add_track([(x, y), (cx - 4.3, y)], nn, width=0.15); add_via(cx - 4.3, y, nn, dia=0.5); left[nn] = (-4.3, y)
        elif k == 14:   # pin47 (D13): 本体下 (下辺 pin49 のビア (cx-3.75, 34.0) と 0.65 離す)
            add_track([(x, y), (cx - 4.75, y), (cx - 4.4, 33.95)], nn, width=0.15); add_via(cx - 4.4, 33.95, nn, dia=0.5); left[nn] = (-4.4, 33.95)
        else:           # pin48 (D12): 隙間の列の一番下 (cx-7.62, 34.35)。裏面で J8 列 3 下段のパッドへ
            add_track([(x, y), (cx - 7.0, y), (cx - 7.62, 34.35)], nn, width=0.15); add_via(cx - 7.62, 34.35, nn, dia=0.5); left[nn] = (-7.62, 34.35)
        PREHANDLED.add((adv, str(pin))); n_access += 1
    # ---- 右辺: HPD (pin16) は本体下 (cx+4.6, 26.3) のビア -> 裏面で J8 列 8 上段へ。AVDD (pin15) は表面で pin19 の AVDD ビアへ (右列は R1/C13 で塞がっている)
    x, y = padpos(adv, "16"); nn = padnet(adv, "16")
    add_track([(x, y), (cx + 4.9, y), (cx + 4.6, 26.3)], nn, width=0.15); add_via(cx + 4.6, 26.3, nn, dia=0.5)
    PREHANDLED.add((adv, "16")); n_access += 1
    _, xh, yh = jpad("J8", 8, True); assert jnet("J8", 8, True) == nn
    T([(4.6, 26.3), (xh, yh)], nn, BCU)
    x, y = padpos(adv, "15"); nn = padnet(adv, "15"); x19a, y19a = top_via["19"]
    assert padnet(adv, "19") == nn
    add_track([(x, y), (cx + 4.75, y), (cx + 3.0, 26.25), (cx + x19a, y19a)], nn, width=0.15)
    PREHANDLED.add((adv, "15"))
    # VS (pin2): 本体下 (cx+4.45, 33.55 = J8 の隙間) のビア -> 裏面で J8 列 8 下段へ
    x, y = padpos(adv, "2"); nn = padnet(adv, "2")
    add_track([(x, y), (cx + 4.9, y), (cx + 4.45, 33.55)], nn, width=0.15); add_via(cx + 4.45, 33.55, nn, dia=0.5)
    PREHANDLED.add((adv, "2")); n_access += 1
    _, xh, yh = jpad("J8", 8, False); assert jnet("J8", 8, False) == nn
    T([(4.45, 33.55), (6.0, 35.1), (xh, yh)], nn, BCU)
    # INT (pin28、上辺のビア (cx-1.75, 26.0)) -> 裏面で J8 列 3 上段へ (下へ出てから左へ: 上辺のビア列と C16 の配線を避ける)
    xi, yi = top_via["28"]; nn = padnet(adv, "28"); assert nn == f"CH{n}_INT"
    _, xh, yh = jpad("J8", 3, True); assert jnet("J8", 3, True) == nn
    T([(xi, yi), (xi, 27.3), (-6.0, 27.3), (xh, yh)], nn, BCU)
    # ---- ADV 露出パッド (GND) のサーマルビア: 裏面 J8 のパッドを避け、上側 2 段 + 中央の隙間の列に打つ
    for xo in (-2.0, -1.2, -0.4, 0.4, 1.2, 2.0):
        for yo in (-2.05, -1.4):
            add_via(cx + xo, YA + yo, "GND", dia=0.5)
    for yo in (0.2, 1.0):
        add_via(cx, YA + yo, "GND", dia=0.5)
    PREHANDLED.add((adv, "65"))
    # J8 列 4-7 上段 (GND、EP の真下): サーマルビアへ裏面で直結
    for col, tgt in ((4, (-2.0, YA - 1.4)), (5, (0.0, YA + 0.2)), (6, (0.0, YA + 0.2)), (7, (2.0, YA - 1.4))):
        pin, xp, yp = jpad("J8", col, True); assert jnet("J8", col, True) == "GND", (col, jnet("J8", col, True))
        T([(xp, yp), tgt], "GND", BCU, 0.25); PREHANDLED.add(("J8", str(pin)))
    # ---- J8 列 4-7 下段: 真上のエスケープビアから裏面で真下へ
    for col, dnet in ((4, "D11"), (5, "D8"), (6, "D3"), (7, "HS")):
        nn = f"CH{n}_{dnet}"; pin, xp, yp = jpad("J8", col, False); assert jnet("J8", col, False) == nn, (col, dnet)
        xs, ys = bot[nn]; assert abs(xs - xp) < 0.07, (dnet, xs, xp)
        T([(xs, ys), (xs, 35.0), (xp, yp)], nn, BCU)
    # ---- J8 列 1-2 (D6/D7/CLK/D9) と列 9 (D0/DE): SIG2 の横レーン (y=34.8..36.5) -> 列の隙間 (y=33.3/33.95) のビア -> 裏面でパッドへ
    #   右側の出所ほど低いレーン (他の出所の縦線の下を通る)、レーンが低いほど遠い列へ
    for dnet, col, upper, ylane, xv, yv in (("D9", 2, False, 35.6, -8.45, 33.95), ("CLK", 2, True, 35.9, -8.9, 33.3),
                                            ("D7", 1, False, 36.2, -11.08, 33.95), ("D6", 1, True, 36.5, -11.78, 33.3),
                                            ("DE", 9, True, 34.8, 8.54, 33.3), ("D0", 9, False, 35.1, 9.24, 33.95)):
        nn = f"CH{n}_{dnet}"; pin, xp, yp = jpad("J8", col, upper); assert jnet("J8", col, upper) == nn, (dnet, col)
        xs, ys = bot[nn]
        xr = -9.0 if dnet == "CLK" else xv                       # CLK の縦線は D9 のビア (cx-8.45) を避けて x=cx-9.0
        T([(xs, ys), (xs, ylane), (xr, ylane), (xr, yv), (xv, yv)], nn, IN3); V(xv, yv, nn)
        T([(xv, yv), (xp, yp)], nn, BCU)
    # D12 (pin48 のビア (cx-6.9, 34.0)) -> 裏面で J8 列 3 下段へ
    nn = f"CH{n}_D12"; pin, xp, yp = jpad("J8", 3, False); assert jnet("J8", 3, False) == nn
    T([(-7.62, 34.35), (-6.6, 34.9), (xp, yp)], nn, BCU)
    # ---- J7 列 4-7 下段 (GND): 裏面で束ねて、TMDS の U ターンの外 ((cx-4.6, 25.4) と (cx+5.4, 25.6)) のビアへ。R4 (CEC_CLK 0R) の GND パッドにも直結
    for col in (4, 5, 6, 7):
        assert jnet("J7", col, False) == "GND", col
    _, x4, y4 = jpad("J7", 4, False); _, x5, y5 = jpad("J7", 5, False); _, x6, y6 = jpad("J7", 6, False); _, x7, y7 = jpad("J7", 7, False)
    xr4, yr4 = padpos(f"R{n}4", "2"); assert padnet(f"R{n}4", "2") == "GND" and abs(xr4 - cx - x4) < 0.02 and abs(yr4 - 23.6) < 0.05, (xr4, yr4)
    T([(x4, y4), (x4, 23.6)], "GND", BCU, 0.2); T([(x4, 22.6), (-4.6, 22.6), (-4.6, 25.4)], "GND", BCU, 0.2); V(-4.6, 25.4, "GND", 0.6)
    T([(x5, y5), (x5, 22.6), (x4, 22.6)], "GND", BCU, 0.2)
    T([(x6, y6), (x6, 21.9), (1.9, 22.5), (1.9, 22.9), (5.08, 22.9), (5.4, 23.2), (5.4, 25.6)], "GND", BCU, 0.2); V(5.4, 25.6, "GND", 0.6)
    T([(x7, y7), (x7, 22.9)], "GND", BCU, 0.2)
    for col in (4, 5, 6, 7):
        PREHANDLED.add(("J7", str(jpad("J7", col, False)[0])))
    PREHANDLED.add((f"R{n}4", "2"))
    # 左の通路のすぐ右 (x=cx-7.62) の部品のビア: I2C プルアップ R{n} の +3V3 (裏面)、C17 の GND、右端 C03 の GND/1V8 (次チャネルの通路の脇)
    xq, yq = padpos(f"R{n}", "1"); assert padnet(f"R{n}", "1") == "+3V3" and abs(xq - cx + 7.62) < 0.02 and abs(yq - 23.09) < 0.05, (xq, yq)
    T([(-7.62, yq), (-7.62, 22.2)], "+3V3", BCU, 0.25); V(-7.62, 22.2, "+3V3", 0.6); PREHANDLED.add((f"R{n}", "1"))
    xq, yq = padpos(f"C{n}17", "2"); assert padnet(f"C{n}17", "2") == "GND" and abs(xq - cx + 7.62) < 0.02 and abs(yq - 14.32) < 0.05, (xq, yq)
    T([(-7.62, yq), (-7.62, 13.42)], "GND", FCU, 0.25); V(-7.62, 13.42, "GND", 0.6); PREHANDLED.add((f"C{n}17", "2"))
    xq, yq = padpos(f"C{n}03", "2"); assert padnet(f"C{n}03", "2") == "GND" and abs(xq - cx - 12.7) < 0.02 and abs(yq - 19.5) < 0.05, (xq, yq)
    T([(12.7, yq), (12.7, 18.6)], "GND", FCU, 0.25); V(12.7, 18.6, "GND", 0.6); PREHANDLED.add((f"C{n}03", "2"))
    xq, yq = padpos(f"C{n}03", "1"); assert padnet(f"C{n}03", "1") == f"CH{n}_1V8" and abs(yq - 20.5) < 0.05, (xq, yq)
    T([(12.7, yq), (12.7, 21.4)], f"CH{n}_1V8", FCU, 0.25); V(12.7, 21.4, f"CH{n}_1V8", 0.6); PREHANDLED.add((f"C{n}03", "1"))
    xr4, yr4 = padpos(f"R{n}4", "1"); assert padnet(f"R{n}4", "1") == f"CH{n}_CEC_CLK" and abs(yr4 - 24.6) < 0.05
    T([(xr4 - cx, yr4), top_via["32"]], f"CH{n}_CEC_CLK", BCU)
    # ---- J7 列 8-10 (下辺の D1/D2/D4/D5/D10): ADV 右脇の通路 x=cx+3.35/3.65/3.95 を上り、y=24.0/24.3/24.6 のレーンで右へ、列の隙間のビアへ
    #   通路の内側 (3.35) ほど高いレーン、近い列ほど高いレーン。下段のビアは列中心 +0.35、上段は -0.35 (縦線がもう一方のビアを避ける)
    for dnet, layer, xc_, yleg, ylane, col, upper in (("D10", IN2, 3.35, 31.9, 24.0, 8, False), ("D2", IN2, 3.65, 32.2, 24.3, 9, True),
                                                      ("D1", IN2, 3.95, 32.5, 24.6, 9, False),
                                                      ("D5", IN3, 3.35, 32.2, 24.0, 10, True), ("D4", IN3, 3.65, 32.5, 24.3, 10, False)):
        nn = f"CH{n}_{dnet}"; pin, xp, yp = jpad("J7", col, upper); assert jnet("J7", col, upper) == nn, (dnet, col)
        xs, ys = bot[nn]
        xv = xp + (-0.35 if upper else 0.35)
        if col == 8:
            xv = 6.5                                             # 列 8 下段: TMDS の縦線 (cx+5.7) から離す
        T([(xs, ys), (xs, yleg), (xc_, yleg), (xc_, ylane), (xv, ylane), (xv, 17.85 if upper else 18.55)], nn, layer)
        V(xv, 17.85 if upper else 18.55, nn)
        T([(xv, 17.85 if upper else 18.55), (xp, yp)], nn, BCU)
    # ---- ADV 脇の帯 (x=cx-6.5..-5.5) を SIG2 で上る 3 本: 左から D15 (左辺の一番下から入る) -> J7 列 3 下段 (ビア (cx-6.85, 22.9) からパッドの下端へ)、
    #   D13 (本体下から入る) -> 列 3 上段 (ビア (cx-6.1, 13.3) の真下がパッド)、D14 -> 列 4 上段 (ビア (cx-5.56, 13.75) から裏面の横線)
    nn = f"CH{n}_D15"; pin, xp, yp = jpad("J7", 3, False); assert jnet("J7", 3, False) == nn
    xs, ys = left[nn]; assert abs(ys - 33.7) < 0.02
    T([(xs, ys), (-6.5, ys), (-6.5, 23.6), (-6.85, 23.6), (-6.85, 22.9)], nn, IN3); V(-6.85, 22.9, nn); T([(-6.85, 22.9), (-6.6, 22.1), (xp, yp)], nn, BCU)
    nn = f"CH{n}_D13"; pin, xp, yp = jpad("J7", 3, True); assert jnet("J7", 3, True) == nn
    xs, ys = left[nn]; assert abs(ys - 33.95) < 0.02
    T([(xs, ys), (-6.1, ys), (-6.1, 13.3)], nn, IN3); V(-6.1, 13.3, nn); T([(-6.1, 13.3), (xp, yp)], nn, BCU)
    nn = f"CH{n}_D14"; pin, xp, yp = jpad("J7", 4, True); assert jnet("J7", 4, True) == nn
    xs, ys = left[nn]; assert abs(ys - 33.15) < 0.02
    T([(xs, ys), (-5.56, ys), (-5.56, 13.75)], nn, IN3); V(-5.56, 13.75, nn); T([(-5.56, 13.75), (xp, 13.75), (xp, yp)], nn, BCU)
    # DDC_SCL_A (pin33) -> TPD pin2 のビア: SIG1 で帯の右端 (x=cx-5.9) を上り y=23.7 で右へ。
    # DDC_SDA_A (pin34) -> TPD pin3 のビア: SIG1 で y=27.15 を右へ (上辺のビア列の下)、x=cx-1.25 を上り、pin4 のビアの脇から入る
    x2, y2 = tpd_via["2"]; x3, y3 = tpd_via["3"]
    assert padnet(tpd, "2") == f"CH{n}_DDC_SCL_A" and padnet(tpd, "3") == f"CH{n}_DDC_SDA_A"
    xs, ys = left[f"CH{n}_DDC_SCL_A"]; T([(xs, ys), (-5.9, ys), (-5.9, 23.7), (x2, 23.7), (x2, y2)], f"CH{n}_DDC_SCL_A", IN2)
    xs, ys = left[f"CH{n}_DDC_SDA_A"]; T([(xs, ys), (-1.25, ys), (-1.25, 19.0), (x3, y3)], f"CH{n}_DDC_SDA_A", IN2)
    # ---- 左の内層通路 (x=cx-8.19..-9.69、0.3 ピッチ): 出所が下のネットほど左のレーン (右のレーンは出所より上で始まるので交差しない)
    #   SIG1: D23 -> 列 2 上段 (ビア (cx-8.19, 13.0))、D22/D21/D20 -> ヘッダ上の横レーン (y=12.1/11.8/11.5) -> 列 5/8/7 上段、
    #         D19 -> 列 1 下段 (y=22.2 で左へ)、D18 -> 列 1 上段 (y=22.5 で左へ、x=cx-12.13 を上って (cx-11.43, 13.3))
    #   SIG2: DDC_SCL_A/DDC_SDA_A -> 横レーン (12.1/11.8) -> TPD pin2/3 のビア、D17 -> 列 2 下段 (隙間ビア)、D16 -> 横レーン 11.5 -> 列 6 上段
    routes = [
        # net, layer, path (cx 相対), via (or None), bottom track (or None)
        ("D23", IN2, [left[f"CH{n}_D23"], (-8.19, 28.65), (-8.19, 17.85), (-7.62, 17.85)], (-7.62, 17.85), [(-7.62, 17.85), (-8.6, 17.85), (-8.89, 15.675)]),
        ("D22", IN2, [left[f"CH{n}_D22"], (-8.49, 29.15), (-8.49, 12.1), (-7.0, 12.1), (-7.0, 12.8)], (-7.0, 12.8), [(-7.0, 12.8), (-1.27, 12.8), (-1.27, 15.675)]),
        ("D21", IN2, [left[f"CH{n}_D21"], (-8.79, 29.8), (-8.79, 11.8), (6.2, 11.8), (6.2, 17.85)], (6.2, 17.85), [(6.2, 17.85), (6.35, 15.675)]),
        ("D20", IN2, [left[f"CH{n}_D20"], (-9.09, 30.45), (-9.09, 11.5), (7.0, 11.5), (7.0, 13.35)], (7.0, 13.35), [(7.0, 13.35), (3.81, 13.35), (3.81, 15.675)]),
        ("D19", IN2, [left[f"CH{n}_D19"], (-9.39, 31.1), (-9.39, 22.2), (-11.43, 22.2), (-11.43, 18.55)], (-11.43, 18.55), [(-11.43, 18.55), (-11.43, 20.725)]),
        ("D18", IN2, [left[f"CH{n}_D18"], (-9.69, 31.75), (-9.69, 22.5), (-12.13, 22.5), (-12.13, 13.3), (-11.43, 13.3)], (-11.43, 13.3), [(-11.43, 13.3), (-11.43, 15.675)]),
        ("D17", IN3, [left[f"CH{n}_D17"], (-8.19, 32.4), (-8.19, 18.6), (-7.62, 18.6)], (-7.62, 18.6), [(-7.62, 18.6), (-8.6, 18.6), (-8.89, 20.725)]),
        ("D16", IN3, [left[f"CH{n}_D16"], (-8.49, 33.05), (-8.49, 11.5), (7.6, 11.5), (7.6, 12.8)], (7.6, 12.8), [(7.6, 12.8), (1.27, 12.8), (1.27, 15.675)]),
    ]
    targets = {"D23": (2, True), "D22": (5, True), "D21": (8, True), "D20": (7, True), "D19": (1, False), "D18": (1, True), "D17": (2, False), "D16": (6, True)}
    for dnet, layer, path, via, btrack in routes:
        nn = f"CH{n}_{dnet}"
        assert abs(path[0][1] - path[1][1]) < 0.02, (dnet, path[0], path[1])
        T(path, nn, layer)
        if via:
            V(via[0], via[1], nn)
            col, upper = targets[dnet]; pin, xp, yp = jpad("J7", col, upper); assert jnet("J7", col, upper) == nn, (dnet, col)
            assert abs(btrack[-1][0] - xp) < 0.6, (dnet, btrack[-1], xp)
            T(btrack, nn, BCU)
    # ---- TPD A 側の 4 本 (CEC / DDC_SCL / DDC_SDA / HPD_CONN) -> HDMI コネクタ。ルータ任せだと OUT1 で落ちるので固定:
    #   CEC / DDC_SCL: 裏面で J7 列 5-6 の上段パッドの隙間 (x=cx-0.3 / +0.4) を上り、HDMI パッドの上 (y=8.55) のビアから表面でパッドへ
    #   HPD_CONN: SIG1 で右上へ (cx+5.7, 12.3) のビア -> 表面で pin19 へ。DDC_SDA: SIG2 で右上へ (cx+8.8, 12.6) のビア -> 表面でコネクタの上を回って pin16 へ
    hv = {}
    for num in ("7", "8", "9", "10"):
        hv[num] = tpd_via[num]
    assert padnet(tpd, "7") == f"CH{n}_CEC" and padnet(hd, "13") == f"CH{n}_CEC"
    assert padnet(tpd, "8") == f"CH{n}_DDC_SCL" and padnet(hd, "15") == f"CH{n}_DDC_SCL"
    assert padnet(tpd, "9") == f"CH{n}_DDC_SDA" and padnet(hd, "16") == f"CH{n}_DDC_SDA"
    assert padnet(tpd, "10") == f"CH{n}_HPD_CONN" and padnet(hd, "19") == f"CH{n}_HPD_CONN"
    for num, hpin in (("7", "13"), ("8", "15"), ("9", "16"), ("10", "19")):
        xh, yh = padpos(hd, hpin); assert abs(yh - 10.3) < 0.05, (hpin, yh)
        hv[num] = (hv[num], xh - cx)
    (x7, y7), xh13 = hv["7"]; (x8, y8), xh15 = hv["8"]; (x9, y9), xh16 = hv["9"]; (x10, y10), xh19 = hv["10"]
    assert abs(x7 - 0.32) < 0.02 and abs(x8 - 0.97) < 0.02 and abs(x9 - 1.62) < 0.02 and abs(x10 - 2.28) < 0.02, (x7, x8, x9, x10)
    nn = f"CH{n}_CEC"
    T([(x7, y7), (x7, 17.9), (-0.3, 17.3), (-0.3, 11.0), (xh13, 8.55)], nn, BCU); V(xh13, 8.55, nn); T([(xh13, 8.55), (xh13, 10.3)], nn, FCU)
    nn = f"CH{n}_DDC_SCL"
    T([(x8, y8), (x8, 17.9), (0.4, 17.3), (0.4, 11.0), (xh15, 8.55)], nn, BCU); V(xh15, 8.55, nn); T([(xh15, 8.55), (xh15, 10.3)], nn, FCU)
    nn = f"CH{n}_HPD_CONN"
    T([(x10, y10), (x10, 17.8), (5.7, 14.4), (5.7, 12.3)], nn, IN2); V(5.7, 12.3, nn); T([(5.7, 12.3), (xh19, 11.1), (xh19, 10.3)], nn, FCU)
    nn = f"CH{n}_DDC_SDA"
    T([(x9, y9), (x9, 17.8), (5.24, 14.2), (8.5, 14.2), (8.8, 13.9), (8.8, 12.6)], nn, IN3); V(8.8, 12.6, nn)
    T([(8.8, 12.6), (9.2, 11.2), (9.2, 7.0), (xh16 + 0.05, 7.0), (xh16 + 0.05, 10.3)], nn, FCU)
    # HDMI pin17 (GND) の上向きビアは DDC_SDA の縦線 (x=cx+3.05) から離して 0.5 mm で打つ
    xh17, yh17 = padpos(hd, "17"); assert padnet(hd, "17") == "GND" and abs(xh17 - cx - 3.5) < 0.02
    T([(3.5, yh17), (3.55, 8.4)], "GND", FCU, 0.2); V(3.55, 8.4, "GND"); PREHANDLED.add((hd, "17"))
    # TPD pin14 (GND、上段) の上向きビア: D16 の裏面横線 (y=12.8) と J7 列 7 のパッドの間 (cx+2.93, 13.45) に 0.5 mm で
    x14, y14 = padpos(tpd, "14"); assert padnet(tpd, "14") == "GND" and abs(x14 - cx - 2.93) < 0.02
    T([(2.93, y14), (2.93, 13.45)], "GND", FCU, 0.2); V(2.93, 13.45, "GND"); PREHANDLED.add((tpd, "14"))
    # ---- HPD: TPD pin4 のビア (cx-1.62, 18.3) -> 裏面で J7 列 5-6 の下段パッドの隙間 (x=cx+0.31) を下り、ADV pin16 のビア (cx+4.6, 26.3) へ (ルータが OUT4 で落とす)
    nn = padnet(tpd, "4"); assert nn == f"CH{n}_HPD"
    x4, y4 = tpd_via["4"]; assert abs(x4 + 1.62) < 0.02 and abs(y4 - 18.3) < 0.01
    T([(x4, y4), (-1.16, 18.3), (0.31, 19.77), (0.31, 22.57), (4.04, 26.3), (4.6, 26.3)], nn, BCU)
    # ---- AVDD: pin25 のビア -> pin19 のビア (SIG1、上辺のビアの下)、pin19 のビア -> SIG2 で右上へ -> (cx+10.16, 22.66) のビア -> FB1 の AVDD パッド
    nn = padnet(adv, "19"); assert nn == f"CH{n}_AVDD" and padnet(adv, "25") == nn
    x25, y25 = top_via["25"]; x19, y19 = top_via["19"]; assert abs(x25 + 0.25) < 0.02 and abs(x19 - 2.75) < 0.02
    T([(x25, y25), (0.44, 26.69), (2.06, 26.69), (x19, y19)], nn, IN2)
    T([(x19, y19), (x19, 23.9), (5.14, 21.5), (9.0, 21.5), (10.16, 22.66)], nn, IN3); V(10.16, 22.66, nn)
    fb = board.FindFootprintByReference(f"FB{n}1")
    pf = [q for q in fb.Pads() if q.GetNetname() == nn]; assert len(pf) == 1
    xf, yf = pf[0].GetPosition().x / 1e6, pf[0].GetPosition().y / 1e6; assert abs(xf - cx - 10.16) < 0.02 and abs(yf - 23.7) < 0.1, (xf, yf)
    T([(10.16, 22.66), (xf - cx, yf)], nn, FCU, 0.25)
    # ---- PVDD: ADV pin13 -> C13 pad1 -> (cx+8.9, 28.2) のビア -> 裏面で C14 pad1 (ルータが落とす短い配線)。pin11 (1V8) のビアはその手前 (cx+6.9, 28.95) に固定
    x, y = padpos(adv, "13"); nn = padnet(adv, "13"); assert nn == f"CH{n}_PVDD"
    xc, yc = padpos(f"C{n}13", "1"); assert padnet(f"C{n}13", "1") == nn and abs(xc - cx - 7.62) < 0.02 and abs(yc - y) < 0.1, (xc, yc, y)
    add_track([(x, y), (xc - 0.5, y), (xc, yc), (cx + 8.9, 28.2)], nn, width=0.2); V(8.9, 28.2, nn)
    x14c, y14c = padpos(f"C{n}14", "1"); assert padnet(f"C{n}14", "1") == nn and abs(x14c - cx - 10.16) < 0.02, (x14c, y14c)
    T([(8.9, 28.2), (x14c - cx, y14c)], nn, BCU, 0.2)
    x, y = padpos(adv, "11"); nn = padnet(adv, "11"); assert nn == f"CH{n}_1V8" and abs(y - 29.15) < 0.02
    add_track([(x, y), (cx + 6.7, y), (cx + 6.9, 28.95)], nn, width=0.2); V(6.9, 28.95, nn); PREHANDLED.add((adv, "11"))   # 0.5 mm: pin12 のパッドと C13 の間
    # ---- R2 (PD/AD、裏面 (cx+1.9, 27.3)): PD パッド -> pin22 のビア。GND 側は EP のサーマルビア (cx+2.0, 28.35)、+3V3 側 (OUT2/4) は上辺のビアの間を上って C16 の +3V3 パッドへ
    pdnet = f"CH{n}_PD"; xpd, ypd = None, None
    for num in ("1", "2"):
        xq, yq = padpos(f"R{n}2", num)
        if padnet(f"R{n}2", num) == pdnet:
            xpd, ypd, xoth, yoth, other = xq - cx, yq, None, None, None
    for num in ("1", "2"):
        xq, yq = padpos(f"R{n}2", num)
        if padnet(f"R{n}2", num) != pdnet:
            xoth, yoth, other = xq - cx, yq, padnet(f"R{n}2", num)
    assert xpd is not None and abs(ypd - 27.3) < 0.05 and abs(xpd - 1.4) < 0.05 and abs(xoth - 2.4) < 0.05, (xpd, ypd, xoth)
    assert padnet(adv, "22") == pdnet
    T([(xpd, ypd), top_via["22"]], pdnet, BCU)
    if other == "GND":
        T([(xoth, yoth), (2.0, YA - 2.05)], "GND", BCU, 0.2)          # EP のサーマルビア (cx+2.0, 28.35) に裏面で直結
    else:
        assert other == "+3V3", other
        xc16, yc16 = padpos(f"C{n}16", "1"); assert padnet(f"C{n}16", "1") == "+3V3"
        T([(xoth, yoth), (2.0, 26.9), (2.0, 25.4), (0.3, 25.3), (xc16 - cx, yc16)], "+3V3", BCU, 0.2)   # C16 の +3V3 パッド (pin29 のビア経由で +3V3) へ
    PREHANDLED.add((f"R{n}2", "1")); PREHANDLED.add((f"R{n}2", "2"))
    # ---- FPGA_5V (OUT2 の J8 列 10 = ピン 39/40 -> JP1): 裏面で 2 ピンを結び、隙間 (cx+12.7, 37.35) のビアから SIG2 で下端を右へ、JP1 の下のビアへ
    if n == 2:
        pin_u, xu, yu = jpad("J8", 10, True); pin_l, xl, yl = jpad("J8", 10, False)
        assert jnet("J8", 10, True) == "FPGA_5V" and jnet("J8", 10, False) == "FPGA_5V"
        T([(xu, yu), (xl, yl), (xl, 37.35), (12.7, 37.35)], "FPGA_5V", BCU, 0.25); V(12.7, 37.35, "FPGA_5V")
        xj, yj = padpos("JP1", "2"); assert padnet("JP1", "2") == "FPGA_5V", padnet("JP1", "2")
        T([(12.7, 37.35), (xj - cx, 37.35), (xj - cx, 31.6)], "FPGA_5V", IN3, 0.25); V(xj - cx, 31.6, "FPGA_5V")
        T([(xj - cx, 31.6), (xj - cx, yj)], "FPGA_5V", BCU, 0.25)
print("access vias:", n_access)

# ---------------------------------------------------------------- プレーン系ネットのファンアウトビア
# FreeRouting は内層プレーンへの接続 (パッド -> ビア) を作らないので、SMD パッドごとに先に打っておく。
PLANE_NETS = {"GND", "+3V3"} | {f"CH{n}_1V8" for n in CX}
VIA_D, VIA_DRILL, CLR = 0.6, 0.3, 0.22
all_pads = []       # (x, y, hw, hh, net, layers)  軸平行の近似矩形 (mm)。layers: パッドの銅がある外層の集合
for fp in board.GetFootprints():
    for pad in fp.Pads():
        bb = pad.GetBoundingBox()
        lys = {L for L in (pcbnew.F_Cu, pcbnew.B_Cu) if pad.IsOnLayer(L)}
        all_pads.append((bb.GetCenter().x / 1e6, bb.GetCenter().y / 1e6, bb.GetWidth() / 2e6, bb.GetHeight() / 2e6, pad.GetNetname(), lys))
vias_placed = [(v.GetPosition().x / 1e6, v.GetPosition().y / 1e6) for v in board.GetTracks() if v.GetClass() == "PCB_VIA"]
segs = []           # 既存配線 (x1, y1, x2, y2, halfwidth, net, layer)
for t in board.GetTracks():
    if t.GetClass() == "PCB_TRACK":
        segs.append((t.GetStart().x / 1e6, t.GetStart().y / 1e6, t.GetEnd().x / 1e6, t.GetEnd().y / 1e6, t.GetWidth() / 2e6, t.GetNetname(), t.GetLayer()))
def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0: return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
DEBUG = os.environ.get("FANOUT_DEBUG", "")
WHY = []
def clear_of(x, y, netname, sx0=None, sy0=None, hw_stub=0.1, via_check=True, layer=None):
    """ビア (x,y) と、(sx0,sy0) から (x,y) への引き出し線が他ネットと干渉しないか。via_check=False なら線分だけ検査"""
    for px, py, hw, hh, pn, lys in all_pads:
        if pn == netname:
            continue
        dx = max(abs(x - px) - hw, 0); dy = max(abs(y - py) - hh, 0)
        if via_check and math.hypot(dx, dy) < VIA_D / 2 + CLR:
            WHY.append(f"via@({x:.2f},{y:.2f}) hits pad {pn} @({px:.2f},{py:.2f}) hw={hw:.2f} hh={hh:.2f}")
            return False
        if sx0 is not None and (layer is None or layer in lys):
            for k in range(0, 13):
                t = k / 12.0
                qx, qy = sx0 + (x - sx0) * t, sy0 + (y - sy0) * t
                ddx = max(abs(qx - px) - hw, 0); ddy = max(abs(qy - py) - hh, 0)
                if math.hypot(ddx, ddy) < hw_stub + CLR:
                    WHY.append(f"stub->({x:.2f},{y:.2f}) hits pad {pn} @({px:.2f},{py:.2f})")
                    return False
    for vx, vy in vias_placed:
        if via_check and math.hypot(x - vx, y - vy) < VIA_D + CLR:
            WHY.append(f"via@({x:.2f},{y:.2f}) hits via @({vx:.2f},{vy:.2f})"); return False
        if sx0 is not None and seg_dist(vx, vy, sx0, sy0, x, y) < VIA_D / 2 + hw_stub + CLR:
            WHY.append(f"stub->({x:.2f},{y:.2f}) hits via @({vx:.2f},{vy:.2f})"); return False
    for x1, y1, x2, y2, hw, pn, ly in segs:
        if pn == netname:
            continue
        if via_check and seg_dist(x, y, x1, y1, x2, y2) < VIA_D / 2 + hw + CLR:
            WHY.append(f"via@({x:.2f},{y:.2f}) hits seg {pn} ({x1:.2f},{y1:.2f})-({x2:.2f},{y2:.2f})"); return False
        if sx0 is not None and (layer is None or ly == layer):
            if min(seg_dist(sx0, sy0, x1, y1, x2, y2), seg_dist(x, y, x1, y1, x2, y2),
                   seg_dist(x1, y1, sx0, sy0, x, y), seg_dist(x2, y2, sx0, sy0, x, y)) < hw + hw_stub + CLR:
                WHY.append(f"stub->({x:.2f},{y:.2f}) hits seg {pn} ({x1:.2f},{y1:.2f})-({x2:.2f},{y2:.2f})"); return False
    if not (1.0 < x < W - 1.0 and 1.0 < y < H - 1.0):
        WHY.append(f"via@({x:.2f},{y:.2f}) out of board"); return False
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
        ey = abs(-dy * rot(1, 0, ang)[0] + dx * rot(1, 0, ang)[1]) * sx / 2 + abs(-dy * rot(0, 1, ang)[0] + dx * rot(0, 1, ang)[1]) * sy / 2
        e0 = ey + CLR + VIA_D / 2 + 0.1
        # 裏面ヘッダのパッド列 (2.54 ピッチ、隙間 0.74 mm) を確実に跨げるよう、外向きの距離を 0.4 刻みで並べる
        cands = [(d0, 0.0), (d0 + 0.4, 0.0), (d0 + 0.75, 0.0), (0.0, e0), (0.0, -e0), (d0 + 0.4, 0.6), (d0 + 0.4, -0.6),
                 (0.3, e0), (0.3, -e0), (-0.3, e0), (-0.3, -e0), (d0 + 1.1, 0.0), (d0 + 1.5, 0.0), (d0 + 1.1, 0.6), (d0 + 1.1, -0.6),
                 (d0 + 1.9, 0.0), (d0 + 2.25, 0.0), (d0 + 1.9, 0.6), (d0 + 1.9, -0.6)]
        if len(pads) > 4:
            cands += [(-d0, 0.0), (-d0 - 0.4, 0.0), (-d0 - 0.75, 0.0), (-d0 - 0.4, 0.6), (-d0 - 0.4, -0.6)]   # 内向き (IC の本体下) は IC だけ
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
                vias_placed.append((vx, vy)); n_via += 1; placed = True
                break
        if not placed:
            n_fail.append(f"{fp.GetReference()}.{pad.GetNumber()}({netname})")
            if f"{fp.GetReference()}.{pad.GetNumber()}" in DEBUG.split(","):
                print("DEBUG", DEBUG, "pad", (px, py), "dir", (round(dx, 2), round(dy, 2)), "ex", round(ex, 2), "d0", round(d0, 2))
                for w in WHY[-40:]: print("   ", w)
        WHY.clear()
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
if n_fail:
    open(os.path.join(OUT, "fanout_failed.txt"), "w").write("\n".join(n_fail) + "\n")
elif os.path.exists(os.path.join(OUT, "fanout_failed.txt")):
    os.remove(os.path.join(OUT, "fanout_failed.txt"))

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

# 配線前 DRC (未接続以外は 0 であること)
from collections import Counter
rpt = os.path.join(OUT, "drc_pre.rpt")
import subprocess
subprocess.run([sys.executable, "-c", "import pcbnew,sys; b=pcbnew.LoadBoard(sys.argv[1]); pcbnew.WriteDRCReport(b, sys.argv[2], pcbnew.EDA_UNITS_MILLIMETRES, True)", PCB, rpt],
               check=True, stderr=subprocess.DEVNULL)   # 別プロセス: 同一プロセスだと .kicad_pro のネットクラス (0.15) が反映されない
txt = open(rpt).read()
kinds = Counter(re.findall(r"^\[(\w+)\]", txt, re.M))
print("pre-route DRC:", kinds.most_common())
for k in ("clearance", "courtyards_overlap", "copper_edge_clearance", "hole_clearance", "shorting_items", "via_dangling", "silk_over_copper", "silk_overlap"):
    for m in re.finditer(r"^\[" + k + r"\][^\n]*\n((?:    [^\n]*\n)+)", txt, re.M):
        print("   ", k, "|", " / ".join(l.strip() for l in m.group(1).strip().split("\n")))
