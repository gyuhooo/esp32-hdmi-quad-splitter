#!/usr/bin/env python3
"""FPGA メイン基板の共通定義: XC7A35T-FTG256 のボール表 (KiCad シンボルから取得)、BGA エスケープ計画、
キャリア基板ヘッダ信号のボール割り当て。

gen_fpga_schematic.py (ネット名) と gen_fpga_pcb.py (ビア/配線座標) の両方がこれを使うので、割り当ては常に一致する。

座標系: ボール (r, c) は 0 始まり (A1 = (0, 0)、行 = A..T、列 = 1..16)。基板上の位置は FPGA 中心 + (-7.5 + c, -7.5 + r) mm。
dog-bone ビアは「セル」(半整数座標 (r±0.5, c±0.5)、ボール 4 個の中心) に置く。外向き対角のセルは全ボールで重複しない。

エスケープの方針 (1.0 mm ピッチ、パッド 0.4、ビア 0.5/0.3、配線 0.15/クリアランス 0.15):
  リング 1 (最外周): 表面パッドから直接。GND/電源ボールは真外側 1.0 mm のビアでプレーンへ。
  リング 2: 表面で外向きセルを通り、リング 1 のパッドの隙間 (半整数列) から外へ。
  リング 3-4: 外向きセルのビア -> 内層 In2 (SIG1) で整数格子線に沿って外へ (ビア列の隙間 0.5 mm に配線 1 本)。
  リング 5 以降の信号 (JTAG/CCLK/DONE 等、PMOD): 同じ方法で In3 (SIG2)。
  整数格子線は層ごとに 1 配線が占有する。各ビアは隣接 4 格子点のどれかから、最寄りの辺へ向かう (占有点が重ならないよう貪欲に割り当て)。
"""
import os, re, csv, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kicad_lib import get_symbol, pins as lib_pins

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = "ABCDEFGHJKLMNPRT"
N = 16
FPGA_XY = (51.6, 55.0)          # FPGA 中心 (基板 mm)。ヘッダ中心 x=51.6 に揃える
HDR_X1, HDR_PITCH = 2.07, 2.54  # ヘッダ列 1 の x、列ピッチ (キャリア基板 J7/J8 と同じ)
HDR_Y = {("J1", 1): 16.93, ("J1", 0): 19.47, ("J2", 1): 32.33, ("J2", 0): 34.87}   # (ヘッダ, 奇数?) -> ピン位置 y
IN2, IN3 = "In2", "In3"

# ---------------------------------------------------------------- ボール表
SYM = get_symbol("FPGA_Xilinx_Artix7", "XC7A35T-FTG256")
BALLS = {}
def _kind(name):
    if name.startswith("IO_"): return "IO"
    if name == "GND" or name in ("GNDADC_0", "VREFP_0", "VREFN_0", "VP_0", "VN_0", "M1_0", "M2_0"): return "GND"
    if name.startswith(("VCCINT", "VCCBRAM")): return "+1V0"
    if name.startswith(("VCCAUX", "VCCADC", "VCCBATT")): return "+1V8"
    if name.startswith("VCCO") or name == "CFGBVS_0": return "+3V3"
    if name in ("DXP_0", "DXN_0"): return "NC"
    return {"M0_0": "CFG_M0", "TCK_0": "TCK", "TMS_0": "TMS", "TDI_0": "TDI", "TDO_0": "TDO", "CCLK_0": "CCLK",
            "DONE_0": "DONE", "INIT_B_0": "INIT_B", "PROGRAM_B_0": "PROGRAM_B"}[name]
for unit in (1, 2, 3, 4):
    for num, name, typ, px, py, ang, ln in lib_pins(SYM, unit):
        r, c = ROWS.index(num[0]), int(num[1:]) - 1
        m = re.search(r"_(\d+)$", name)
        BALLS[num] = dict(pin=num, name=name, unit=unit, r=r, c=c, ring=min(r, c, N - 1 - r, N - 1 - c) + 1,
                          bank=int(m.group(1)) if m and name.startswith("IO_") else None, kind=_kind(name),
                          mrcc="MRCC" in name, srcc="SRCC" in name)
assert len(BALLS) == 256, len(BALLS)
def ball_xy(pin):
    """ボールの基板座標 (mm)"""
    b = BALLS[pin]; return FPGA_XY[0] - 7.5 + b["c"], FPGA_XY[1] - 7.5 + b["r"]
def grid_xy(row, col):
    """格子座標 (行, 列; 半整数可) -> 基板座標"""
    return FPGA_XY[0] - 7.5 + col, FPGA_XY[1] - 7.5 + row

# ---------------------------------------------------------------- 用途が決まっているボール
FIXED = {
    "J13": "QSPI_D0", "J14": "QSPI_D1", "K15": "QSPI_D2", "K16": "QSPI_D3", "L12": "QSPI_CS",   # バンク 14 のコンフィグ兼用ピン
    "D4": "CLK100",                                   # MRCC (バンク 35)
    "T3": "RST_N",                                    # 下辺 (表面から直接): ボタン、LED、DIP スイッチ
    "R10": "LED0", "R11": "LED1", "T12": "LED2", "R12": "LED3",
    "T13": "SW0", "R13": "SW1", "T14": "SW2", "T15": "SW3",
    "E5": "PMOD_1", "E6": "PMOD_2", "F5": "PMOD_3", "G5": "PMOD_4",       # リング 5 (In3 で左へ): 左端の PMOD
    "H5": "PMOD_7", "J5": "PMOD_8", "K5": "PMOD_9", "L5": "PMOD_10",
}
PREFER_DIR = {p: "left" for p in ("E5", "E6", "F5", "G5", "H5", "J5", "K5", "L5")}
PREFER_DIR.update({"J13": "right", "J14": "right", "L12": "right", "E8": "right", "D4": "left"})    # フラッシュは右、CCLK も右へ、クロックは左 (発振器)
PREFER_DIR.update({"L7": "down", "M7": "down", "N7": "down", "N8": "down"})          # JTAG は下へ
for p, n in FIXED.items():
    assert BALLS[p]["kind"] == "IO", (p, BALLS[p]["name"])

# ---------------------------------------------------------------- エスケープ計画
def natural_cell(b):
    r, c = b["r"], b["c"]
    return (r - 0.5 if r <= 7 else r + 0.5, c - 0.5 if c <= 7 else c + 0.5)

def plan_escapes(use_pins=None):
    """信号ボール (リング >= 3、IO/コンフィグ信号) と電源/GND ボール (リング >= 2) のビア位置、
    信号の内層配線 (層、格子点、方向、経路) を決める。use_pins を与えるとその信号ボールだけを計画する
    (未使用 IO はビアも配線も持たない)。戻り値: (pin -> dict(...), 失敗したピン)"""
    used = {IN2: set(), IN3: set()}
    blocked = set()                     # リング 1 の GND/電源ボールの真外側ビアが塞ぐ格子点 (全層)
    plan = {}
    for p, b in BALLS.items():
        if b["ring"] == 1 and b["kind"] in ("GND", "+1V0", "+1V8", "+3V3"):
            r, c = b["r"], b["c"]
            pt = (r - 1, c) if r == 0 else (r + 1, c) if r == N - 1 else (r, c - 1) if c == 0 else (r, c + 1)
            blocked.add(pt); plan[p] = dict(via=pt, kind="straight")
        elif b["ring"] >= 2 and b["kind"] in ("GND", "+1V0", "+1V8", "+3V3"):
            plan[p] = dict(cell=natural_cell(b), kind="power")
    for L in used: used[L] |= blocked
    def line_pts(pt, d):
        i, j = pt
        if d == "up":    return [(k, j) for k in range(i, -2, -1)]
        if d == "down":  return [(k, j) for k in range(i, N + 1)]
        if d == "left":  return [(i, k) for k in range(j, -2, -1)]
        if d == "right": return [(i, k) for k in range(j, N + 1)]
    def route(pt, d, pts_needed, layer):
        """格子点 pt から方向 d へ。終端の格子点 (-1 / 16) が塞がれていれば手前で半格子ずらして終える"""
        i, j = pt
        last = pts_needed[-1]
        if last in blocked:
            body = pts_needed[:-1]
            if any(q in used[layer] for q in body): return None
            if d == "up":    path = [pt, (-0.5, j), (-0.5, j + 0.5), (-1.5, j + 0.5)]; end = (-1.5, j + 0.5)
            elif d == "down": path = [pt, (N - 0.5, j), (N - 0.5, j + 0.5), (N + 0.5, j + 0.5)]; end = (N + 0.5, j + 0.5)
            elif d == "left": path = [pt, (i, -0.5), (i + 0.5, -0.5), (i + 0.5, -1.5)]; end = (i + 0.5, -1.5)
            else:             path = [pt, (i, N - 0.5), (i + 0.5, N - 0.5), (i + 0.5, N + 0.5)]; end = (i + 0.5, N + 0.5)
            return body, path, end
        if any(q in used[layer] for q in pts_needed): return None
        if d == "up":    end = (-1.5, j)
        elif d == "down": end = (N + 0.5, j)
        elif d == "left": end = (i, -1.5)
        else:             end = (i, N + 0.5)
        return pts_needed, [pt, end], end
    def try_ball(b, layers, all_dirs):
        ci, cj = natural_cell(b)
        vdir = "up" if b["r"] <= 7 else "down"
        hdir = "left" if b["c"] <= 7 else "right"
        dv = b["r"] if vdir == "up" else N - 1 - b["r"]
        dh = b["c"] if hdir == "left" else N - 1 - b["c"]
        pref = PREFER_DIR.get(b["pin"])
        dirs = [vdir, hdir] if dv <= dh else [hdir, vdir]
        if pref in dirs: dirs = [pref] + [d for d in dirs if d != pref]
        if all_dirs: dirs = dirs + [d for d in ("up", "down", "left", "right") if d not in dirs]
        def cand_pts(d):
            if d in ("up", "down"):
                i = ci - 0.5 if d == "up" else ci + 0.5
                outer, inner = (cj - 0.5, cj + 0.5) if cj < 7.5 else (cj + 0.5, cj - 0.5)
                return [(int(i), int(outer)), (int(i), int(inner))]
            j = cj - 0.5 if d == "left" else cj + 0.5
            outer, inner = (ci - 0.5, ci + 0.5) if ci < 7.5 else (ci + 0.5, ci - 0.5)
            return [(int(outer), int(j)), (int(inner), int(j))]
        for layer in layers:
            for d in dirs:
                for pt in cand_pts(d):
                    res = route(pt, d, line_pts(pt, d), layer)
                    if res:
                        body, path, end = res
                        used[layer] |= set(body) | {pt}
                        pos = end[1] if d in ("up", "down") else end[0]
                        plan[b["pin"]] = dict(cell=(ci, cj), kind="signal", layer=layer, pt=pt, dir=d, path=path, end=end, side=d, pos=pos)
                        return True
        return False
    sig = [b for b in BALLS.values() if b["ring"] >= 3 and (b["kind"] == "IO" or b["kind"] not in ("GND", "+1V0", "+1V8", "+3V3", "NC"))]
    if use_pins is not None:
        sig = [b for b in sig if b["pin"] in use_pins]
    else:
        sig = [b for b in sig if b["ring"] <= 4 or b["kind"] != "IO" or b["pin"] in FIXED]   # リング 5 以上の IO は用途が決まったものだけ
    sig.sort(key=lambda b: (b["ring"], b["r"], b["c"]))
    outer = [b for b in sig if b["ring"] <= 4]; inner = [b for b in sig if b["ring"] >= 5]
    todo = [b for b in outer if not try_ball(b, [IN2], False)]              # 1: リング 3-4 を In2 へ
    todo += [b for b in inner if not try_ball(b, [IN3], False)]             # 2: 深いリングを In3 へ
    todo = [b for b in todo if not try_ball(b, [IN3, IN2], False)]          # 3: あぶれたものを反対の層へ
    todo = [b for b in todo if not try_ball(b, [IN2, IN3], True)]           # 4: 方向も自由にして再試行
    return plan, [b["pin"] for b in todo]

PLAN, PLAN_FAILS = plan_escapes()
PLAN1_FAILS = list(PLAN_FAILS)        # 全候補での計画で失敗したボール (ヘッダ候補から外れる)

def exit_of(pin):
    """信号ボールの出口: (side, pos) side = up/down/left/right、pos = 辺に沿った格子座標。表面 (リング 1-2) も含む"""
    b = BALLS[pin]
    if b["ring"] == 1:
        if b["r"] == 0: return "up", b["c"]
        if b["r"] == N - 1: return "down", b["c"]
        return ("left", b["r"]) if b["c"] == 0 else ("right", b["r"])
    if b["ring"] == 2:
        ci, cj = natural_cell(b)
        if b["r"] == 1: return "up", cj
        if b["r"] == N - 2: return "down", cj
        return ("left", ci) if b["c"] == 1 else ("right", ci)
    e = PLAN.get(pin)
    return (e["side"], e["pos"]) if e and e["kind"] == "signal" else None

def perimeter_p(side, pos):
    """基板上のヘッダ (上側) から見た周回パラメータ。下辺中央 (左寄り) 0 -> 左辺 -> 上辺 -> 右辺 -> 下辺中央 (右寄り) 64"""
    if side == "down":
        return 7.5 - pos if pos < 7.5 else 56 + (N - 0.5 - pos)
    if side == "left": return 8 + (N - 0.5 - pos)
    if side == "up":   return 24 + (pos + 0.5)
    return 40 + (pos + 0.5)

def exit_xy(pin):
    side, pos = exit_of(pin)
    if side == "up":    return grid_xy(-1.5, pos)
    if side == "down":  return grid_xy(N + 0.5, pos)
    if side == "left":  return grid_xy(pos, -1.5)
    return grid_xy(pos, N + 0.5)

# ---------------------------------------------------------------- ヘッダ信号 (キャリア基板の J7/J8 と同じピン番号)
def header_signals():
    """[(header, pin, signal, x, y)] 全ピン (GND / FPGA_5V 含む)。J1 = キャリア J7、J2 = キャリア J8 (gen_schematic.header_pinout と同じ)"""
    from gen_schematic import header_pinout
    out = []
    for cref, lst in header_pinout().items():
        hdr = {"J7": "J1", "J8": "J2"}[cref]
        for pin, sig in lst:
            col = (pin + 1) // 2
            x = HDR_X1 + HDR_PITCH * (col - 1); y = HDR_Y[(hdr, pin % 2)]
            out.append((hdr, pin, sig, x, y))
    return out
HEADER_ALL = header_signals()
HEADER_SIG = [h for h in HEADER_ALL if h[2] not in ("GND", "FPGA_5V")]
assert len(HEADER_SIG) == 124, len(HEADER_SIG)

def assign_header():
    """ヘッダ信号 (x 順) を、BGA の周回順に並べた出口 (左下 -> 左 -> 上 -> 右 -> 右下) に単調に割り当てる。
    124 個の連続した出口の窓のうち、ヘッダピンとの距離の総和が最小のものを選ぶ"""
    order = {("J1", 1): 0, ("J2", 1): 1, ("J2", 0): 2, ("J1", 0): 3}
    hdr = sorted(HEADER_SIG, key=lambda h: ((h[1] + 1) // 2, order[(h[0], h[1] % 2)]))
    cands = [p for p, b in BALLS.items() if b["kind"] == "IO" and b["ring"] <= 4 and p not in FIXED and exit_of(p)]
    cands.sort(key=lambda p: perimeter_p(*exit_of(p)))
    best = None
    for o in range(0, len(cands) - len(hdr) + 1):
        cost = 0.0
        for h, p in zip(hdr, cands[o:o + len(hdr)]):
            ex, ey = exit_xy(p); cost += abs(h[3] - ex) + abs(h[4] - ey)
        if best is None or cost < best[0]: best = (cost, o)
    o = best[1]
    return {p: h[2] for h, p in zip(hdr, cands[o:o + len(hdr)])}, [p for p in cands[:o] + cands[o + len(hdr):]]

HEADER_ASSIGN, SPARE = assign_header()

# ---------------------------------------------------------------- 全ボールのネット
NET_OF = {}
for p, b in BALLS.items():
    if p in FIXED: NET_OF[p] = FIXED[p]
    elif p in HEADER_ASSIGN: NET_OF[p] = HEADER_ASSIGN[p]
    elif b["kind"] == "IO": NET_OF[p] = "NC"
    else: NET_OF[p] = b["kind"]
SIGNAL_PINS = [p for p, n in NET_OF.items() if n not in ("GND", "+1V0", "+1V8", "+3V3", "NC")]
# 使うボールだけで計画し直す (未使用 IO の格子線を解放)。出口の辺が変わるボールがあっても割り当ては変えない
PLAN, PLAN_FAILS = plan_escapes(set(SIGNAL_PINS))
assert not PLAN_FAILS, PLAN_FAILS

def report():
    import collections
    print(f"balls {len(BALLS)}  planned {len(PLAN)}  plan failures {PLAN_FAILS}  (first pass, all candidates: {PLAN1_FAILS})")
    print(f"header signals {len(HEADER_ASSIGN)}  spare IO (rings 1-4) {len(SPARE)}: {SPARE}")
    unused5 = [p for p, b in BALLS.items() if b['kind'] == 'IO' and NET_OF[p] == 'NC' and b['ring'] >= 5]
    print(f"unused IO on ring>=5: {len(unused5)}")
    by_layer = collections.Counter(e["layer"] for p, e in PLAN.items() if e["kind"] == "signal" and NET_OF[p] != "NC")
    print("inner-layer escapes in use:", dict(by_layer))
    for ch in (1, 2, 3, 4):
        banks = collections.Counter(BALLS[p]["bank"] for p, n in HEADER_ASSIGN.items() if n.startswith(f"CH{ch}_"))
        sides = collections.Counter(exit_of(p)[0] for p, n in HEADER_ASSIGN.items() if n.startswith(f"CH{ch}_"))
        print(f"  CH{ch}: banks {dict(banks)}  exits {dict(sides)}")
    i2c = {n: (p, BALLS[p]["bank"]) for p, n in HEADER_ASSIGN.items() if n.startswith("I2C")}
    print("  I2C:", i2c)

if __name__ == "__main__":
    report()
