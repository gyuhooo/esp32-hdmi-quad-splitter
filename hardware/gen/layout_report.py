#!/usr/bin/env python3
"""配線後の基板を集計する: 配線長、ビア数、未接続、DRC の種類別件数、TMDS ペアの長さ差。"""
import os, re, sys
from collections import Counter, defaultdict
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.environ.get("PCB_PROJECT", "quad_hdmi_tx")
OUT = os.path.normpath(os.path.join(HERE, "..", PROJECT))
board = pcbnew.LoadBoard(os.path.join(OUT, PROJECT + ".kicad_pcb"))

length = defaultdict(float); vias = Counter(); tracks = 0
for t in board.GetTracks():
    n = t.GetNetname()
    if t.GetClass() == "PCB_VIA":
        vias[n] += 1
    else:
        tracks += 1; length[n] += t.GetLength() / 1e6
print(f"tracks: {tracks}  vias: {sum(vias.values())}  routed nets: {len(length)}")
print("longest nets:")
for n, l in sorted(length.items(), key=lambda kv: -kv[1])[:6]:
    print(f"   {n:14s} {l:6.1f} mm  vias {vias[n]}")
print("TMDS pairs (length P / N, diff, vias):")
for ch in (range(1, 5) if PROJECT == "quad_hdmi_tx" else ()):
    for p in ("TXC", "TX0", "TX1", "TX2"):
        lp, ln = length.get(f"CH{ch}_{p}_P", 0), length.get(f"CH{ch}_{p}_N", 0)
        print(f"   CH{ch}_{p}: {lp:5.1f} / {ln:5.1f}  d={abs(lp-ln):4.2f}  vias {vias[f'CH{ch}_{p}_P']}/{vias[f'CH{ch}_{p}_N']}")
rpt = os.path.join(OUT, "drc.rpt")
if os.path.exists(rpt):
    txt = open(rpt).read()
    m = re.search(r"\*\* Found (\d+) DRC violations", txt); u = re.search(r"\*\* Found (\d+) unconnected pads", txt)
    print("DRC violations:", m.group(1) if m else "?", " unconnected:", u.group(1) if u else "?")
    print("  ", Counter(re.findall(r"^\[(\w+)\]", txt, re.M)).most_common(12))
    un = re.findall(r"\[unconnected_items\][^\n]*\n\s*([^\n]*)\n\s*([^\n]*)", txt)
    nets = Counter()
    for a, b in un:
        mm = re.search(r'\[Net ([^\]]+)\]|Net "([^"]+)"|net ([\w+\-]+)', a + " " + b)
        if mm: nets[next(g for g in mm.groups() if g)] += 1
    print("  unconnected by net:", nets.most_common(15))

if PROJECT == "fpga_main":                       # ヘッダ信号の配線長 (チャネルごとの最小/最大) と層別の配線長
    import collections
    ch = collections.defaultdict(list)
    for n, l in length.items():
        m = re.match(r"CH([1-4])_", n)
        if m: ch[m.group(1)].append(l)
    for c in sorted(ch):
        print(f"   CH{c}: {len(ch[c])} nets, length {min(ch[c]):5.1f} .. {max(ch[c]):5.1f} mm (mean {sum(ch[c])/len(ch[c]):5.1f})")
    per_layer = Counter()
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK": per_layer[t.GetLayerName()] += t.GetLength() / 1e6
    print("   length per layer (mm):", {k: round(v) for k, v in per_layer.items()})
