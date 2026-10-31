#!/usr/bin/env python3
"""基板を読み込み、ゾーンを塗って DRC レポートを書き、要約を表示する。
使い方: pcb_drc.py <board.kicad_pcb> <report.rpt> [--no-fill]"""
import sys, re, pcbnew
from collections import Counter
pcb, rpt = sys.argv[1], sys.argv[2]
board = pcbnew.LoadBoard(pcb)
if "--no-fill" not in sys.argv:
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(pcb, board)
pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
txt = open(rpt).read()
m = re.search(r"\*\* Found (\d+) DRC violations", txt); u = re.search(r"\*\* Found (\d+) unconnected pads", txt)
kinds = Counter(re.findall(r"^\[(\w+)\]", txt, re.M))
print("DRC violations:", m.group(1) if m else "?", "unconnected:", u.group(1) if u else "?", dict(kinds))
for mm in list(re.finditer(r"^\[(clearance|hole_clearance|copper_edge_clearance|shorting_items|via_dangling|courtyards_overlap|silk_over_copper|silk_overlap|silk_edge_clearance|solder_mask_bridge|zones_intersect|text_height)\][^\n]*\n((?:    [^\n]*\n)+)", txt, re.M))[:int(sys.argv[sys.argv.index("--show") + 1]) if "--show" in sys.argv else 20]:
    print("   ", mm.group(1), "|", " / ".join(l.strip() for l in mm.group(2).strip().split("\n")))
