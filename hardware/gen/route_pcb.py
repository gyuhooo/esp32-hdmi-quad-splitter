#!/usr/bin/env python3
"""基板の自動配線: DSN 書き出し -> FreeRouting -> SES 読み込み -> ゾーン塗り -> DRC。
使い方:
  route_pcb.py export                 # quad_hdmi_tx.dsn を書き出す
  java -jar freerouting.jar -de quad_hdmi_tx.dsn -do quad_hdmi_tx.ses -mp 40 -mt 4   # 別途実行
  route_pcb.py import                 # SES 取り込み、ゾーン塗り、DRC
"""
import os, sys, subprocess, time, re
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "quad_hdmi_tx"))
PCB = os.path.join(OUT, "quad_hdmi_tx.kicad_pcb")
STAGE = sys.argv[1] if len(sys.argv) > 1 else "export"
DSN = os.path.join(OUT, "quad_hdmi_tx.dsn")
SES = os.path.join(OUT, "quad_hdmi_tx.ses")

if STAGE == "export":
    board = pcbnew.LoadBoard(PCB)
    for t in list(board.GetTracks()):        # ロックされたファンアウトビアは残す
        if not t.IsLocked():
            board.Remove(t)
    ok = pcbnew.ExportSpecctraDSN(board, DSN)
    print("DSN export:", ok, os.path.getsize(DSN))
    sys.exit(0)
if not os.path.exists(SES):
    print("no SES file"); sys.exit(1)

board = pcbnew.LoadBoard(PCB)
ok = pcbnew.ImportSpecctraSES(SES)            # LoadBoard で読んだ基板に取り込む (7.0 API は引数 1 つ)
if not ok or len(list(board.GetTracks())) < 300:
    from ses_import import import_ses
    for t in list(board.GetTracks()):        # 二重取り込みを避け、ロック済みファンアウトだけ残す
        if not t.IsLocked():
            board.Remove(t)
    print("fallback SES parser:", import_ses(board, SES))
print("SES import:", ok, "tracks:", len(list(board.GetTracks())))
# 配線後に外層 GND ベタを追加 (オートルータには渡さない: FreeRouting はベタを障害物として扱う)
gnd = board.FindNet("GND")
for layer, name in ((pcbnew.B_Cu, "GND_B"), (pcbnew.F_Cu, "GND_F")):
    z = pcbnew.ZONE(board); z.SetLayer(layer); z.SetNetCode(gnd.GetNetCode()); z.SetZoneName(name)
    o = z.Outline(); o.NewOutline()
    bb = board.GetBoardEdgesBoundingBox()
    for x, y in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()), (bb.GetRight(), bb.GetBottom()), (bb.GetLeft(), bb.GetBottom())):
        o.Append(x, y)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL); z.SetMinThickness(pcbnew.FromMM(0.25))
    z.SetLocalClearance(pcbnew.FromMM(0.3)); z.SetAssignedPriority(0); board.Add(z)
filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())
pcbnew.SaveBoard(PCB, board)

rpt = os.path.join(OUT, "drc.rpt")
pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
txt = open(rpt).read()
m = re.search(r"\*\* Found (\d+) DRC violations", txt); u = re.search(r"\*\* Found (\d+) unconnected pads", txt)
print("DRC violations:", m.group(1) if m else "?", " unconnected:", u.group(1) if u else "?")
kinds = re.findall(r"^\[(\w+)\]", txt, re.M)
from collections import Counter
print("  ", Counter(kinds).most_common(10))
