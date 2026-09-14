#!/usr/bin/env python3
"""kicad-cli が出力したネットリストを検査する (簡易 ERC)。
- IC/コネクタの全ピンが接続されているか (未接続はネット名 unconnected-*)
- 1 ピンしか繋がっていないネット
- 電源ネットの存在
"""
import sys, re
from collections import defaultdict
from sexp import parse, find, find1

net_file = sys.argv[1]
doc = parse(open(net_file).read())[0]
comps = {c[1][1] if isinstance(c[1], list) else None: c for c in find(find1(doc, "components"), "comp")}
refs = {}
for c in find(find1(doc, "components"), "comp"):
    ref = find1(c, "ref")[1]; val = find1(c, "value")[1]
    refs[ref] = val
nets = find(find1(doc, "nets"), "net")
pin_net = {}
net_pins = defaultdict(list)
for n in nets:
    name = find1(n, "name")[1]
    for node in find(n, "node"):
        ref = find1(node, "ref")[1]; pin = find1(node, "pin")[1]
        pin_net[(ref, pin)] = name
        net_pins[name].append((ref, pin))

errors = []
# 1 ピンネット
for name, ps in net_pins.items():
    if len(ps) == 1 and not name.startswith("unconnected-"):
        errors.append(f"single-pin net {name}: {ps}")
# unconnected ピンのうち意図しないもの
allowed_unconnected = {("J1","14"),("J2","14"),("J3","14"),("J4","14")} | {("J5",p) for p in ("A6","A7","B6","B7","A8","B8")}
for (ref, pin), name in pin_net.items():
    if name.startswith("unconnected-") and (ref, pin) not in allowed_unconnected:
        errors.append(f"unconnected pin {ref}.{pin} ({refs.get(ref)})")
# ADV7513 の全 65 ピン、TPD の全 24 ピンが登場するか
for ref, val in refs.items():
    exp = 65 if val.startswith("ADV7513") else 24 if val.startswith("TPD12S016") else None
    if exp:
        have = {p for (r, p) in pin_net if r == ref}
        missing = [str(i) for i in range(1, exp + 1) if str(i) not in have]
        if missing: errors.append(f"{ref} missing pins: {missing}")
for pn in ("+5V", "+3V3", "GND", "VBUS", "CH1_1V8", "CH4_1V8", "I2C_A_SCL", "I2C_B_SDA", "CH1_TX2_P", "CH4_TXC_N"):
    if pn not in net_pins: errors.append(f"missing net {pn}")
# ネットごとの期待ピン数
def expect(pattern, count, what):
    for name, ps in net_pins.items():
        if re.fullmatch(pattern, name) and len(ps) != count:
            errors.append(f"{name}: expected {count} pins ({what}), got {len(ps)}: {sorted(ps)}")
expect(r"CH[1-4]_(D\d+|CLK|DE|HS|VS)", 2, "header + ADV7513")
expect(r"CH[1-4]_TX[C012]_[PN]", 3, "ADV7513 + TPD + HDMI")
expect(r"CH[1-4]_HPD", 3, "header + ADV7513 + TPD")
expect(r"CH[1-4]_INT", 3, "header + ADV7513 + pull-up")
expect(r"CH[1-4]_(CEC|DDC_SCL|DDC_SDA|HPD_CONN)", 2, "TPD + HDMI")
expect(r"CH[1-4]_(CEC_A|DDC_SCL_A|DDC_SDA_A)", 2, "ADV7513 + TPD")
expect(r"CH[1-4]_5V_OUT", 3, "TPD + HDMI + cap")
expect(r"CH[1-4]_(REXT|PD|CEC_CLK)", 2, "ADV7513 + resistor")
expect(r"I2C_[AB]_(SCL|SDA)", 4, "header + pull-up + 2x ADV7513")
# 電源ネットに信号ピンが混ざっていないか
for ref, val in refs.items():
    if val.startswith("ADV7513"):
        for (r, p), name in pin_net.items():
            if r != ref: continue
            if name == "GND" and p not in {"65","3","4","5","6","7","8","9","10"}:
                errors.append(f"{ref}.{p} on GND unexpectedly")
            if name == "+3V3" and p != "29":
                errors.append(f"{ref}.{p} on +3V3 unexpectedly")
gnd = net_pins.get("GND", [])
print(f"  GND pins: {len(gnd)}  +3V3 pins: {len(net_pins.get('+3V3', []))}  +5V pins: {len(net_pins.get('+5V', []))}")
print(f"components: {len(refs)}  nets: {len(nets)}")
for pn in ("GND", "+3V3", "+5V", "CH1_1V8", "CH1_AVDD", "CH1_HPD", "I2C_A_SCL", "CH1_TX0_P", "CH1_D0", "CH1_CLK"):
    print(f"  {pn:10s} {len(net_pins.get(pn, []))} pins  {sorted(net_pins.get(pn, []))[:6]}")
if errors:
    print("ERRORS:"); [print("  ", e) for e in errors]; sys.exit(1)
print("netlist check OK")
