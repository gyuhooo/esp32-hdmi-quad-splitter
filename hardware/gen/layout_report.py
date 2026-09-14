#!/usr/bin/env python3
"""配線後の基板を集計する: 配線長、ビア数、未接続、DRC の種類別件数、TMDS ペアの長さ差。"""
import os, re, sys
from collections import Counter, defaultdict
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "quad_hdmi_tx"))
board = pcbnew.LoadBoard(os.path.join(OUT, "quad_hdmi_tx.kicad_pcb"))

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
for ch in range(1, 5):
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
