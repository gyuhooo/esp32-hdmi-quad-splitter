#!/usr/bin/env python3
"""FPGA メイン基板のネットリスト検査: ヘッダ信号が J1/J2 と U1 の 2 ノード、電源ネットのノード数、孤立ネットなし、FPGA の全ボールが接続または NC。
使い方: check_fpga_netlist.py hardware/fpga_main/netlist.net"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import parse, find, find1
import fpga_common as F

doc = parse(open(sys.argv[1]).read())[0]
nets = {find1(n, "name")[1]: [(find1(x, "ref")[1], find1(x, "pin")[1]) for x in find(n, "node")] for n in find(find1(doc, "nets"), "net")}
bad = 0
def expect(cond, msg):
    global bad
    if not cond:
        bad += 1; print("NG:", msg)
hdr = {h[2] for h in F.HEADER_SIG}
for sig in hdr:
    refs = sorted(r for r, p in nets.get(sig, []))
    expect(refs in (["J1", "U1"], ["J2", "U1"]), f"{sig}: nodes {nets.get(sig)}")
for n, lo in (("GND", 100), ("+3V3", 40), ("+1V0", 15), ("+1V8", 10), ("+5V", 10)):
    expect(len(nets.get(n, [])) >= lo, f"{n}: only {len(nets.get(n, []))} nodes")
single = [n for n, nodes in nets.items() if len(nodes) < 2 and not n.startswith("unconnected")]
expect(not single, f"single-node nets {single}")
u1 = {p for n, nodes in nets.items() for r, p in nodes if r == "U1" and not n.startswith("unconnected")}
nc = {p for p, n in F.NET_OF.items() if n == "NC"}
expect(len(u1) + len(nc) == 256, f"U1 connected {len(u1)} + NC {len(nc)} != 256")
for p, n in F.NET_OF.items():
    if n != "NC":
        expect((("U1", p) in nets.get(n, [])), f"ball {p} should be on {n}")
sig_in_pwr = [(n, r, p) for n in ("GND", "+3V3", "+1V0", "+1V8") for r, p in nets[n] if r == "U1" and F.NET_OF[p] != n]
expect(not sig_in_pwr, f"wrong balls on power nets {sig_in_pwr[:5]}")
print(f"nets: {len(nets)}  header signals: {len(hdr)}  U1 connected balls: {len(u1)}  NC: {len(nc)}  problems: {bad}")
sys.exit(1 if bad else 0)
