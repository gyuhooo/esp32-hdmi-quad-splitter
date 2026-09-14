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
if STAGE == "import" and not os.path.exists(SES):
    print("no SES file"); sys.exit(1)

board = pcbnew.LoadBoard(PCB)
if STAGE == "import":
    # pcbnew.ImportSpecctraSES はこの環境では失敗し、その後 board ハンドルが無効になるため自前パーサだけを使う
    from ses_import import import_ses
    for t in list(board.GetTracks()):        # 二重取り込みを避け、ロック済みファンアウトだけ残す
        if not t.IsLocked():
            board.Remove(t)
    print("SES parser:", import_ses(board, SES))
else:
    print("finish stage: reusing routed board")
print("tracks:", len(list(board.GetTracks())))
# 使われなかったアクセスビア (B.Cu 側に配線がない信号ネットのロック済みビア) とその引き出し線を削除
board.BuildConnectivity()
conn = board.GetConnectivity()
plane_nets = {"GND", "+3V3"} | {f"CH{n}_1V8" for n in range(1, 5)}
removed = 0
for via in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.IsLocked()]:
    if via.GetNetname() in plane_nets:
        continue
    tracks = [t for t in conn.GetConnectedTracks(via)]
    if tracks and all(t.IsLocked() for t in tracks):      # ロック済みの引き出し線しか繋がっていない = 使われなかった
        for t in tracks:
            if t.IsLocked() and t.GetLength() < pcbnew.FromMM(3.0):
                board.Remove(t)
        board.Remove(via); removed += 1
print("removed unused access vias:", removed)
# オートルータが残した ADV pin15 (AVDD) は、同ネットの右隣のビアへ L 字で接続する
board.BuildConnectivity(); conn = board.GetConnectivity()
fixed = 0
for n in range(1, 5):
    fp = board.FindFootprintByReference(f"U{n}1")
    pad = [p for p in fp.Pads() if p.GetNumber() == "15"][0]
    if conn.GetConnectedTracks(pad):
        continue
    px, py = pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == pad.GetNetname()
            and t.GetPosition().x / 1e6 > px + 1.0 and abs(t.GetPosition().y / 1e6 - py) < 3.0]
    if not vias:
        continue
    v = min(vias, key=lambda t: abs(t.GetPosition().x / 1e6 - px))
    vx, vy = v.GetPosition().x / 1e6, v.GetPosition().y / 1e6
    for (ax, ay), (bx, by) in (((px, py), (vx, py)), ((vx, py), (vx, vy))):
        t = pcbnew.PCB_TRACK(board); t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(ax), pcbnew.FromMM(ay))); t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(bx), pcbnew.FromMM(by)))
        t.SetWidth(pcbnew.FromMM(0.15)); t.SetLayer(pcbnew.F_Cu); t.SetNetCode(pad.GetNetCode()); board.Add(t)
    fixed += 1
print("manual AVDD pin15 fixes:", fixed)
# 配線後に外層 GND ベタを追加 (オートルータには渡さない: FreeRouting はベタを障害物として扱う)
gnd = board.FindNet("GND")
existing = {z.GetZoneName() for z in board.Zones()}
for layer, name in ((pcbnew.B_Cu, "GND_B"), (pcbnew.F_Cu, "GND_F")):
    if name in existing:
        continue
    z = pcbnew.ZONE(board); z.SetLayer(layer); z.SetNetCode(gnd.GetNetCode()); z.SetZoneName(name)
    o = z.Outline(); o.NewOutline()
    bb = board.GetBoardEdgesBoundingBox()
    for x, y in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()), (bb.GetRight(), bb.GetBottom()), (bb.GetLeft(), bb.GetBottom())):
        o.Append(x, y)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL); z.SetMinThickness(pcbnew.FromMM(0.25))
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
