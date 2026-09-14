#!/usr/bin/env python3
"""fpga_header_pinmap.csv の FPGA_pin 列 (使用する FPGA ボードのヘッダ→FPGA ピン対応) を埋めたあと、
Vivado 用の XDC を生成する。

使い方: gen_xdc.py hardware/quad_hdmi_tx/fpga_header_pinmap.csv > constraints/board.xdc
"""
import csv, sys, re

rows = list(csv.DictReader(open(sys.argv[1])))
ports = {}
for r in rows:
    sig, pin = r["Signal"], r["FPGA_pin(fill in)"].strip()
    if sig in ("GND", "FPGA_5V") or not pin:
        continue
    m = re.fullmatch(r"CH([1-4])_(D(\d+)|CLK|DE|HS|VS|HPD|INT)", sig)
    if m:
        ch = int(m.group(1)) - 1
        kind = m.group(2)
        if kind.startswith("D"):
            port = f"hdmi_d[{ch * 24 + int(m.group(3))}]"
        else:
            port = {"CLK": f"hdmi_clk[{ch}]", "DE": f"hdmi_de[{ch}]", "HS": f"hdmi_hs[{ch}]",
                    "VS": f"hdmi_vs[{ch}]", "HPD": f"hdmi_hpd[{ch}]", "INT": f"hdmi_int[{ch}]"}[kind]
    else:
        m = re.fullmatch(r"I2C_([AB])_(SCL|SDA)", sig)
        bus = 0 if m.group(1) == "A" else 1
        port = f"i2c_{m.group(2).lower()}[{bus}]"
    ports[port] = pin

print("## Generated from fpga_header_pinmap.csv - quad HDMI TX carrier (J7/J8)")
for port, pin in sorted(ports.items()):
    extra = " SLEW FAST" if not port.startswith(("i2c", "hdmi_hpd", "hdmi_int")) else ""
    print(f"set_property -dict {{PACKAGE_PIN {pin} IOSTANDARD LVCMOS33{extra}}} [get_ports {{{port}}}]")
missing = [r["Signal"] for r in rows if r["Signal"] not in ("GND", "FPGA_5V") and not r["FPGA_pin(fill in)"].strip()]
if missing:
    print(f"## WARNING: {len(missing)} signals have no FPGA pin assigned yet", file=sys.stderr)
