#!/usr/bin/env python3
"""2 枚構成の機械的整合を検査する: キャリア基板 J7/J8 (裏面 SMD ヘッダ) のピン位置と、メイン基板 J1/J2 (ソケット) のピン位置・ネット、共通の取付穴 H1-H4。"""
import os, sys, pcbnew
HERE = os.path.dirname(os.path.abspath(__file__))
c = pcbnew.LoadBoard(os.path.join(HERE, "..", "quad_hdmi_tx", "quad_hdmi_tx.kicad_pcb"))
m = pcbnew.LoadBoard(os.path.join(HERE, "..", "fpga_main", "fpga_main.kicad_pcb"))
def pads(b, ref):
    fp = b.FindFootprintByReference(ref)
    return fp, {p.GetNumber(): (p.GetPosition().x / 1e6, p.GetPosition().y / 1e6, p.GetNetname()) for p in fp.Pads()}
worst, bad = 0.0, []
for cref, mref in (("J7", "J1"), ("J8", "J2")):
    cfp, cp = pads(c, cref); mfp, mp = pads(m, mref)
    cy = cfp.GetPosition().y / 1e6
    for n in range(1, 81):
        cx, _, cnet = cp[str(n)]; mx, my, mnet = mp[str(n)]
        post_y = cy - 1.27 if n % 2 == 1 else cy + 1.27          # SMD ヘッダのピンは中心線 ±1.27 (パッドはその外側)
        worst = max(worst, abs(cx - mx), abs(post_y - my))
        if cnet != mnet: bad.append((mref, n, cnet, mnet))
for h in ("H1", "H2", "H3", "H4"):
    if c.FindFootprintByReference(h).GetPosition() != m.FindFootprintByReference(h).GetPosition(): bad.append(("hole", h))
print(f"header/socket pin position error: {worst:.3f} mm  mismatches: {bad}")
sys.exit(1 if bad or worst > 0.02 else 0)
