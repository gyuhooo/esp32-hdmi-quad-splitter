#!/usr/bin/env python3
"""4 出力 HDMI 送信基板 (ADV7513 x4 + TPD12S016 x4) の KiCad 7 回路図を生成する。

出力: hardware/quad_hdmi_tx/*.kicad_sch, *.kicad_pro, bom.csv, fpga_header_pinmap.csv
"""
import os, uuid, csv, sys
from sexp import Sym, dump, find, find1
from kicad_lib import get_symbol, pins as lib_pins, footprint as lib_fp

PROJECT = "quad_hdmi_tx"
OUT = os.path.join(os.path.dirname(__file__), "..", PROJECT)
ROOT_UUID = "9c8f0a10-0000-4000-8000-000000000001"

def U():
    return str(uuid.uuid4())

# ---------------------------------------------------------------- 部品表
BOM = {}   # ref -> dict
def bom_add(ref, value, footprint, mpn, desc, lib_id):
    BOM[ref] = dict(ref=ref, value=value, footprint=footprint, mpn=mpn, desc=desc, lib_id=lib_id)

# ---------------------------------------------------------------- カスタムシンボル
def make_symbol(name, ref_prefix, value, fp, left, right, top, bottom, half_w, half_h, datasheet="~"):
    """left/right/top/bottom: [(number, name, type)] または None (空き)。ピン間隔 2.54。"""
    def pin(num, nm, typ, x, y, ang):
        return [Sym("pin"), Sym(typ), Sym("line"), [Sym("at"), x, y, ang], [Sym("length"), 2.54],
                [Sym("name"), nm, [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]],
                [Sym("number"), num, [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]]]
    unit_pins = [Sym("symbol"), f"{name}_1_1"]
    def col(items, x, ang):
        n = len(items); y0 = (n - 1) / 2 * 2.54
        for i, it in enumerate(items):
            if it: unit_pins.append(pin(it[0], it[1], it[2], x, round(y0 - i * 2.54, 2), ang))
    def row(items, y, ang):
        n = len(items); x0 = -(n - 1) / 2 * 2.54
        for i, it in enumerate(items):
            if it: unit_pins.append(pin(it[0], it[1], it[2], round(x0 + i * 2.54, 2), y, ang))
    col(left, -(half_w + 2.54), 0); col(right, half_w + 2.54, 180)
    row(top, half_h + 2.54, 270); row(bottom, -(half_h + 2.54), 90)
    body = [Sym("symbol"), f"{name}_0_1",
            [Sym("rectangle"), [Sym("start"), -half_w, half_h], [Sym("end"), half_w, -half_h],
             [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]],
             [Sym("fill"), [Sym("type"), Sym("background")]]]]
    def prop(k, v, hide=False):
        e = [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]
        if hide: e.append(Sym("hide"))
        return [Sym("property"), k, v, [Sym("at"), 0, 0, 0], e]
    return [Sym("symbol"), name, [Sym("pin_names"), [Sym("offset"), 1.016]], [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
            prop("Reference", ref_prefix), prop("Value", value), prop("Footprint", fp, True), prop("Datasheet", datasheet, True),
            body, unit_pins]

# D0=62 ... D8=54, D9=52, D10=50 ... D23=37
def adv_dpin(i):
    return 62 - i if i <= 8 else (52 if i == 9 else 50 - (i - 10))
ADV_LEFT = [("53", "CLK", "input"), ("63", "DE", "input"), ("64", "HSYNC", "input"), ("2", "VSYNC", "input"), None] + \
           [(str(adv_dpin(i)), f"D{i}", "input") for i in range(23, -1, -1)]
ADV_RIGHT = [("18", "TXC+", "output"), ("17", "TXC-", "output"), ("21", "TX0+", "output"), ("20", "TX0-", "output"),
             ("24", "TX1+", "output"), ("23", "TX1-", "output"), ("27", "TX2+", "output"), ("26", "TX2-", "output"), None,
             ("16", "HPD", "input"), ("28", "INT", "output"), ("30", "CEC", "bidirectional"), ("32", "CEC_CLK", "input"),
             ("33", "DDCSCL", "open_collector"), ("34", "DDCSDA", "bidirectional"), ("35", "SCL", "input"), ("36", "SDA", "bidirectional"),
             ("22", "PD", "input"), ("14", "R_EXT", "passive")]
ADV_TOP = [("1", "DVDD", "power_in"), ("11", "DVDD", "power_in"), ("31", "DVDD", "power_in"), ("51", "DVDD", "power_in"),
           ("15", "AVDD", "power_in"), ("19", "AVDD", "power_in"), ("25", "AVDD", "power_in"),
           ("12", "PVDD", "power_in"), ("13", "BGVDD", "power_in"), ("29", "DVDD_3V", "power_in")]
ADV_BOTTOM = [("65", "EPAD", "power_in"), ("3", "SPDIF", "input"), ("4", "MCLK", "input"), ("5", "I2S0", "input"),
              ("6", "I2S1", "input"), ("7", "I2S2", "input"), ("8", "I2S3", "input"), ("9", "SCLK", "input"), ("10", "LRCLK", "input")]
ADV_FP = "Package_QFP:LQFP-64-1EP_10x10mm_P0.5mm_EP5x5mm_ThermalVias"
ADV_SYM = make_symbol("ADV7513", "U", "ADV7513BSWZ", ADV_FP, ADV_LEFT, ADV_RIGHT, ADV_TOP, ADV_BOTTOM, 20.32, 38.1,
                      "https://www.analog.com/media/en/technical-documentation/data-sheets/ADV7513.pdf")

TPD_LEFT = [("1", "CEC_A", "bidirectional"), ("2", "SCL_A", "bidirectional"), ("3", "SDA_A", "bidirectional"), ("4", "HPD_A", "output"), None,
            ("5", "LS_OE", "input"), ("12", "CT_HPD", "input"), None, ("24", "VCCA", "power_in"), ("11", "VCC5V", "power_in")]
TPD_RIGHT = [("23", "D2+", "passive"), ("22", "D2-", "passive"), ("21", "D1+", "passive"), ("20", "D1-", "passive"),
             ("18", "D0+", "passive"), ("17", "D0-", "passive"), ("16", "CLK+", "passive"), ("15", "CLK-", "passive"), None,
             ("7", "CEC_B", "bidirectional"), ("8", "SCL_B", "bidirectional"), ("9", "SDA_B", "bidirectional"), ("10", "HPD_B", "input"),
             ("13", "5V_OUT", "power_out")]
TPD_BOTTOM = [("6", "GND", "power_in"), ("14", "GND", "power_in"), ("19", "GND", "power_in")]
TPD_FP = "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm"
TPD_SYM = make_symbol("TPD12S016PW", "U", "TPD12S016PWR", TPD_FP, TPD_LEFT, TPD_RIGHT, [], TPD_BOTTOM, 15.24, 19.05,
                      "https://www.ti.com/lit/ds/symlink/tpd12s016.pdf")

CUSTOM = {"QuadHDMI:ADV7513": ADV_SYM, "QuadHDMI:TPD12S016PW": TPD_SYM}

# ---------------------------------------------------------------- 回路図シート
class Sheet:
    def __init__(self, fname, title, sheet_uuid, page):
        # sheet_uuid: 親シート内のシートシンボルの UUID (インスタンスパスに使う)。ファイル自身の UUID は別に持つ。
        self.fname, self.title, self.uuid, self.page = fname, title, sheet_uuid, page
        self.file_uuid = ROOT_UUID if sheet_uuid == ROOT_UUID else sheet_uuid.replace("-0000-4000-", "-0001-4000-")
        self.items = []
        self.libs = {}       # lib_id -> symbol sexp
        self.refcount = {}
        self.path = f"/{ROOT_UUID}" if sheet_uuid == ROOT_UUID else f"/{ROOT_UUID}/{sheet_uuid}"

    # -- ライブラリ
    def _lib(self, lib_id):
        if lib_id not in self.libs:
            if lib_id in CUSTOM:
                sym = [Sym("symbol"), lib_id] + CUSTOM[lib_id][2:]
            else:
                lib, name = lib_id.split(":")
                sym = get_symbol(lib, name)
                sym = [Sym("symbol"), lib_id] + sym[2:]
            self.libs[lib_id] = sym
        return self.libs[lib_id]

    def pins_of(self, lib_id):
        sym = self._lib(lib_id)
        # カスタムは名前が "QuadHDMI:X" のまま。ユニット名は "X_1_1"
        return lib_pins(sym)

    # -- 要素
    def symbol(self, lib_id, ref, value, at, footprint=None, mpn="", desc="", rot=0, fields=None, in_bom=True):
        sym = self._lib(lib_id)
        fp = footprint if footprint is not None else lib_fp(sym)
        x, y = at
        ppos = {}
        for num, nm, typ, px, py, ang, ln in self.pins_of(lib_id):
            ppos[num] = (round(x + px, 3), round(y - py, 3), ang, nm, typ)
        def prop(k, v, dx, dy, hide=False, justify=None):
            e = [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]
            if justify: e.append([Sym("justify"), Sym(justify)])
            if hide: e.append(Sym("hide"))
            return [Sym("property"), k, v, [Sym("at"), round(x + dx, 3), round(y + dy, 3), 0], e]
        s = [Sym("symbol"), [Sym("lib_id"), lib_id], [Sym("at"), x, y, rot], [Sym("unit"), 1],
             [Sym("in_bom"), Sym("yes" if in_bom else "no")], [Sym("on_board"), Sym("yes")], [Sym("dnp"), Sym("no")],
             [Sym("uuid"), U()],
             prop("Reference", ref, 2.54, -2.54, justify="left"), prop("Value", value, 2.54, 0, justify="left"),
             prop("Footprint", fp, 0, 0, True), prop("Datasheet", "~", 0, 0, True)]
        if mpn:
            s.append(prop("MPN", mpn, 0, 0, True))
        for k, v in (fields or {}).items():
            s.append(prop(k, v, 0, 0, True))
        for num in ppos:
            s.append([Sym("pin"), num, [Sym("uuid"), U()]])
        s.append([Sym("instances"), [Sym("project"), PROJECT, [Sym("path"), self.path, [Sym("reference"), ref], [Sym("unit"), 1]]]])
        self.items.append(s)
        if in_bom and not ref.startswith("#"):
            bom_add(ref, value, fp, mpn, desc, lib_id)
        return ppos

    def label(self, net, x, y, rot=0, shape="passive"):
        just = {0: "left", 90: "left", 180: "right", 270: "right"}[rot]
        self.items.append([Sym("global_label"), net, [Sym("shape"), Sym(shape)], [Sym("at"), x, y, rot], [Sym("fields_autoplaced")],
                           [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]], [Sym("justify"), Sym(just)]], [Sym("uuid"), U()],
                           [Sym("property"), "Intersheetrefs", "${INTERSHEET_REFS}", [Sym("at"), x, y, 0],
                            [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]], Sym("hide")]]])

    def wire(self, x1, y1, x2, y2):
        self.items.append([Sym("wire"), [Sym("pts"), [Sym("xy"), x1, y1], [Sym("xy"), x2, y2]],
                           [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("default")]], [Sym("uuid"), U()]])

    def junction(self, x, y):
        self.items.append([Sym("junction"), [Sym("at"), x, y], [Sym("diameter"), 0], [Sym("color"), 0, 0, 0, 0], [Sym("uuid"), U()]])

    def nc(self, x, y):
        self.items.append([Sym("no_connect"), [Sym("at"), x, y], [Sym("uuid"), U()]])

    def text(self, s, x, y, size=1.27):
        self.items.append([Sym("text"), s, [Sym("at"), x, y, 0], [Sym("effects"), [Sym("font"), [Sym("size"), size, size]],
                           [Sym("justify"), Sym("left"), Sym("bottom")]], [Sym("uuid"), U()]])

    _pwr_n = [0]
    def power(self, net, x, y, down=False):
        """電源シンボルをピン位置 (x,y) に接続。down=True は GND 系 (下向き)。"""
        Sheet._pwr_n[0] += 1
        ref = f"#PWR{Sheet._pwr_n[0]:03d}"
        lib_id = "power:" + net
        if down:
            self.wire(x, y, x, y + 2.54); self.symbol(lib_id, ref, net, (x, y + 2.54), in_bom=False)
        else:
            self.wire(x, y, x, y - 2.54); self.symbol(lib_id, ref, net, (x, y - 2.54), in_bom=False)

    def pwr_flag(self, x, y):
        Sheet._pwr_n[0] += 1
        self.symbol("power:PWR_FLAG", f"#FLG{Sheet._pwr_n[0]:03d}", "PWR_FLAG", (x, y), in_bom=False)

    # -- ピンにラベルを付ける (ピン角度から向きを決める)
    def label_pin(self, ppos, num, net, shape="passive"):
        x, y, ang, nm, typ = ppos[num]
        rot = {0: 180, 180: 0, 270: 90, 90: 270}[int(ang)]
        self.label(net, x, y, rot, shape)

    def net_or_power(self, ppos, num, net):
        """電源ネットで上下向きのピンならシンボル、それ以外はグローバルラベル。
        側面ピン (2.54 mm 間隔で並ぶ) に電源シンボルを置くと隣のピンと短絡するのでラベルを使う。"""
        x, y, ang, nm, typ = ppos[num]
        if net == "GND" and int(ang) == 90:            # 下向きピン
            self.power("GND", x, y, down=True)
        elif net in ("+5V", "+3V3", "+1V8", "VBUS") and int(ang) == 270:   # 上向きピン
            self.power(net, x, y)
        else:
            self.label_pin(ppos, num, net)

    def flag(self, net, x, y):
        """PWR_FLAG を電源ネットに付ける"""
        self.pwr_flag(x, y); self.wire(x, y, x, y + 5.08)
        Sheet._pwr_n[0] += 1
        self.symbol("power:" + net, f"#PWR{Sheet._pwr_n[0]:03d}", net, (x, y + 5.08), in_bom=False)

    # -- 2 端子縦置き部品 (R/C/FB): pin1 上, pin2 下
    def two_pin(self, lib_id, ref, value, x, y, top_net, bottom_net, footprint, mpn="", desc=""):
        p = self.symbol(lib_id, ref, value, (x, y), footprint, mpn, desc)
        self.net_or_power(p, "1", top_net)
        self.net_or_power(p, "2", bottom_net)
        return p

    # -- 出力
    def write(self, sub_sheets=None, title_block=None):
        doc = [Sym("kicad_sch"), [Sym("version"), 20230121], [Sym("generator"), Sym("eeschema")],
               [Sym("uuid"), self.file_uuid], [Sym("paper"), "A3"]]
        tb = [Sym("title_block"), [Sym("title"), self.title], [Sym("date"), "2026-09-14"], [Sym("rev"), "A"],
              [Sym("company"), "gyuhooo"], [Sym("comment"), 1, "Quad HDMI test pattern generator - ADV7513 x4 carrier"]]
        doc.append(tb)
        doc.append([Sym("lib_symbols")] + list(self.libs.values()))
        doc += self.items
        for sh in (sub_sheets or []):
            doc.append(sh)
        if self.uuid == ROOT_UUID:
            doc.append([Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]])
        with open(os.path.join(OUT, self.fname), "w") as f:
            f.write(dump(doc) + "\n")

# ---------------------------------------------------------------- 定数 (部品)
C0402 = "Capacitor_SMD:C_0402_1005Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
R0402 = "Resistor_SMD:R_0402_1005Metric"
R0603 = "Resistor_SMD:R_0603_1608Metric"
FB0603 = "Inductor_SMD:L_0603_1608Metric"
MPN_C100N = "GRM155R71C104KA88D"   # 0.1uF 16V X7R 0402
MPN_C1U   = "GRM188R61A105KA61D"   # 1uF 10V X5R 0603
MPN_C10U  = "GRM188R60J106ME47D"   # 10uF 6.3V X5R 0603
MPN_C22U  = "GRM21BR60J226ME39L"   # 22uF 6.3V X5R 0805
MPN_FB    = "BLM18PG121SN1D"       # 120ohm@100MHz 0603

# ---------------------------------------------------------------- チャネルシート
def channel_sheet(n, sheet_uuid, page, i2c_bus, pd_high):
    sh = Sheet(f"hdmi_ch{n}.kicad_sch", f"HDMI OUT{n}: ADV7513 + TPD12S016", sheet_uuid, page)
    P = f"CH{n}_"
    i2c = f"I2C_{i2c_bus}_"
    sh.text(f"HDMI OUT{n}   I2C bus {i2c_bus}, ADV7513 address {'0x7A (PD/AD=H)' if pd_high else '0x72 (PD/AD=L)'}", 20, 20, 2.5)

    # ---- ADV7513
    u = sh.symbol("QuadHDMI:ADV7513", f"U{n}1", "ADV7513BSWZ", (120, 130), ADV_FP, "ADV7513BSWZ", "HDMI 1.4 transmitter, 165 MHz, LQFP-64 EP")
    for num, nm, typ in [p for p in ADV_LEFT if p]:
        if nm == "HSYNC": net = P + "HS"
        elif nm == "VSYNC": net = P + "VS"
        else: net = P + nm
        sh.label_pin(u, num, net, "input")
    tmds = {"TXC+": "TXC_P", "TXC-": "TXC_N", "TX0+": "TX0_P", "TX0-": "TX0_N", "TX1+": "TX1_P", "TX1-": "TX1_N", "TX2+": "TX2_P", "TX2-": "TX2_N"}
    for num, nm, typ in [p for p in ADV_RIGHT if p]:
        if nm in tmds: net = P + tmds[nm]
        elif nm == "HPD": net = P + "HPD"
        elif nm == "INT": net = P + "INT"
        elif nm == "CEC": net = P + "CEC_A"
        elif nm == "CEC_CLK": net = P + "CEC_CLK"
        elif nm == "DDCSCL": net = P + "DDC_SCL_A"
        elif nm == "DDCSDA": net = P + "DDC_SDA_A"
        elif nm == "SCL": net = i2c + "SCL"
        elif nm == "SDA": net = i2c + "SDA"
        elif nm == "PD": net = P + "PD"
        elif nm == "R_EXT": net = P + "REXT"
        sh.label_pin(u, num, net)
    for num, nm, typ in ADV_TOP:
        net = {"DVDD": P + "1V8", "AVDD": P + "AVDD", "PVDD": P + "PVDD", "BGVDD": P + "PVDD", "DVDD_3V": "+3V3"}[nm]
        sh.label_pin(u, num, net)
    for num, nm, typ in ADV_BOTTOM:
        sh.label_pin(u, num, "GND")     # EPAD と未使用オーディオ入力は GND
    sh.text("Unused audio inputs (SPDIF, MCLK, I2S0-3, SCLK, LRCLK) tied to GND.  CEC_CLK: 0R to GND (lift to add a 3-100 MHz clock).", 70, 178, 1.5)

    # ---- TPD12S016
    t = sh.symbol("QuadHDMI:TPD12S016PW", f"U{n}2", "TPD12S016PWR", (250, 110), TPD_FP, "TPD12S016PWR", "HDMI ESD/level shifter/5V load switch, TSSOP-24")
    tl = {"CEC_A": P + "CEC_A", "SCL_A": P + "DDC_SCL_A", "SDA_A": P + "DDC_SDA_A", "HPD_A": P + "HPD",
          "LS_OE": "+3V3", "CT_HPD": "+3V3", "VCCA": "+3V3", "VCC5V": "+5V"}
    for num, nm, typ in [p for p in TPD_LEFT if p]:
        sh.label_pin(t, num, tl[nm])
    tr = {"D2+": "TX2_P", "D2-": "TX2_N", "D1+": "TX1_P", "D1-": "TX1_N", "D0+": "TX0_P", "D0-": "TX0_N", "CLK+": "TXC_P", "CLK-": "TXC_N",
          "CEC_B": "CEC", "SCL_B": "DDC_SCL", "SDA_B": "DDC_SDA", "HPD_B": "HPD_CONN", "5V_OUT": "5V_OUT"}
    for num, nm, typ in [p for p in TPD_RIGHT if p]:
        sh.label_pin(t, num, P + tr[nm])
    for num, nm, typ in TPD_BOTTOM:
        x, y, ang, _, _ = t[num]; sh.power("GND", x, y, down=True)

    # ---- HDMI コネクタ
    j = sh.symbol("Connector:HDMI_A", f"J{n}", "HDMI_A", (350, 110), "Connector_HDMI:HDMI_A_Molex_208658-1001_Horizontal",
                  "208658-1001", "HDMI type A receptacle, right angle")
    jm = {"1": "TX2_P", "3": "TX2_N", "4": "TX1_P", "6": "TX1_N", "7": "TX0_P", "9": "TX0_N", "10": "TXC_P", "12": "TXC_N",
          "13": "CEC", "15": "DDC_SCL", "16": "DDC_SDA", "18": "5V_OUT", "19": "HPD_CONN"}
    for num, net in jm.items():
        sh.label_pin(j, num, P + net)
    for num in ("2", "5", "8", "11", "17", "SH"):
        x, y, ang, _, _ = j[num]; sh.power("GND", x, y, down=True)
    x, y, ang, _, _ = j["14"]; sh.nc(x, y)

    # ---- 1.8 V LDO (チャネルごと)
    l = sh.symbol("Regulator_Linear:AMS1117-1.8", f"U{n}3", "TLV1117LV18DCYR", (60, 230), None, "TLV1117LV18DCYR",
                  "1.8 V 1 A LDO, SOT-223 (AMS1117-1.8 pin compatible)")
    x, y, _, _, _ = l["3"]; sh.wire(x, y, x - 5.08, y); sh.power("+3V3", x - 5.08, y)
    x, y, _, _, _ = l["2"]; sh.wire(x, y, x + 5.08, y); sh.label(P + "1V8", x + 5.08, y, 0)
    x, y, _, _, _ = l["1"]; sh.power("GND", x, y, down=True)
    sh.two_pin("Device:C", f"C{n}01", "10uF", 40, 250, "+3V3", "GND", C0603, MPN_C10U, "10uF 6.3V X5R 0603")
    sh.two_pin("Device:C", f"C{n}02", "22uF", 80, 250, P + "1V8", "GND", C0805, MPN_C22U, "22uF 6.3V X5R 0805")
    sh.two_pin("Device:C", f"C{n}03", "0.1uF", 92, 250, P + "1V8", "GND", C0402, MPN_C100N, "0.1uF 16V X7R 0402")

    # ---- フェライトビーズ: 1V8 -> AVDD / PVDD
    sh.two_pin("Device:FerriteBead", f"FB{n}1", "120R@100MHz", 120, 230, P + "1V8", P + "AVDD", FB0603, MPN_FB, "Ferrite bead 0603")
    sh.two_pin("Device:FerriteBead", f"FB{n}2", "120R@100MHz", 135, 230, P + "1V8", P + "PVDD", FB0603, MPN_FB, "Ferrite bead 0603")

    # ---- 抵抗
    sh.two_pin("Device:R", f"R{n}1", "887R 1%", 160, 230, P + "REXT", "GND", R0402, "RC0402FR-07887RL", "887 ohm 1% 0402 (TMDS current reference)")
    sh.two_pin("Device:R", f"R{n}2", "10k", 172, 230, P + "PD", "+3V3" if pd_high else "GND", R0402, "RC0402FR-0710KL", "10k 0402 (I2C address select)")
    sh.two_pin("Device:R", f"R{n}3", "10k", 184, 230, "+3V3", P + "INT", R0402, "RC0402FR-0710KL", "10k 0402 (INT pull-up)")
    sh.two_pin("Device:R", f"R{n}4", "0R", 196, 230, P + "CEC_CLK", "GND", R0402, "RC0402FR-070RL", "0 ohm 0402")

    # ---- デカップリング
    caps = [("1V8", "0.1uF", C0402, MPN_C100N, 4), ("1V8", "10uF", C0603, MPN_C10U, 1),
            ("AVDD", "0.1uF", C0402, MPN_C100N, 3), ("AVDD", "10uF", C0603, MPN_C10U, 1),
            ("PVDD", "0.1uF", C0402, MPN_C100N, 2), ("PVDD", "1uF", C0603, MPN_C1U, 1),
            ("+3V3", "0.1uF", C0402, MPN_C100N, 2), ("+3V3", "1uF", C0603, MPN_C1U, 1),
            ("+5V", "0.1uF", C0402, MPN_C100N, 1), ("5V_OUT", "0.1uF", C0402, MPN_C100N, 1)]
    idx = 4; x = 40
    for net, val, fp, mpn, cnt in caps:
        for _ in range(cnt):
            full = net if net.startswith("+") else P + net
            desc = {"0.1uF": "0.1uF 16V X7R 0402", "1uF": "1uF 10V X5R 0603", "10uF": "10uF 6.3V X5R 0603"}[val]
            sh.two_pin("Device:C", f"C{n}{idx:02d}", val, x, 275, full, "GND", fp, mpn, desc)
            idx += 1; x += 12
    sh.text("Decoupling: place 0.1uF at each supply pin. C_5V_OUT near TPD12S016 pin 13.  AVDD/PVDD/BGVDD fed through ferrite beads.", 40, 262, 1.5)
    sh.text("TMDS pairs: 100 ohm differential, length-matched within 0.1 mm per pair, TPD12S016 within 10 mm of the connector.", 200, 150, 1.5)
    sh.write()
    return sh

# ---------------------------------------------------------------- FPGA コネクタシート
def header_pinout():
    """J1/J2 のピン割り当て: [(pin, net)] を返す"""
    def ch_signals(n):
        P = f"CH{n}_"
        groups = [[P + "CLK"], [P + "DE", P + "HS", P + "VS"]] + [[P + f"D{i}" for i in range(k, k + 4)] for k in range(0, 24, 4)]
        out = []
        for g in groups:
            out += g + ["GND"]
        return out     # 28 signals + 8 GND = 36
    def header(a, b, bus):
        sig = ["FPGA_5V", "FPGA_5V"] + ch_signals(a) + ch_signals(b) + \
              [f"I2C_{bus}_SCL", f"I2C_{bus}_SDA", f"CH{a}_HPD", f"CH{b}_HPD", f"CH{a}_INT", f"CH{b}_INT"]
        assert len(sig) == 80, len(sig)
        return list(zip(range(1, 81), sig))
    return {"J7": header(1, 2, "A"), "J8": header(3, 4, "B")}

def fpga_sheet(sheet_uuid, page):
    sh = Sheet("fpga_conn.kicad_sch", "FPGA interface headers", sheet_uuid, page)
    sh.text("FPGA interface: 2x 80-pin 2.54 mm headers (J7 = OUT1/OUT2, J8 = OUT3/OUT4). 3.3 V LVCMOS. Keep stack height short (< 30 mm) for the 148.5 MHz buses.", 20, 20, 2.0)
    pm = header_pinout()
    for ref, x in (("J7", 110), ("J8", 300)):
        p = sh.symbol("Connector_Generic:Conn_02x40_Odd_Even", ref, "FPGA_" + ref, (x, 150),
                      "Connector_PinHeader_2.54mm:PinHeader_2x40_P2.54mm_Vertical", "PH2-80-UA", "2x40 pin header 2.54 mm (or box header)")
        for pin, net in pm[ref]:
            sh.net_or_power(p, str(pin), net)
    # I2C プルアップ
    for i, (net, x) in enumerate((("I2C_A_SCL", 30), ("I2C_A_SDA", 45), ("I2C_B_SCL", 60), ("I2C_B_SDA", 75))):
        sh.two_pin("Device:R", f"R{i+1}", "4.7k", x, 250, "+3V3", net, R0402, "RC0402FR-074K7L", "4.7k 0402 (I2C pull-up)")
    # 5 V 供給ジャンパ
    jp = sh.symbol("Jumper:SolderJumper_2_Open", "JP1", "5V->FPGA", (130, 250), "Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm",
                   "", "Solder jumper: feed +5V to FPGA board via header pins 1/2")
    x, y, _, _, _ = jp["1"]; sh.wire(x, y, x - 5.08, y); sh.power("+5V", x - 5.08, y)
    x, y, _, _, _ = jp["2"]; sh.wire(x, y, x + 5.08, y); sh.label("FPGA_5V", x + 5.08, y, 0)
    sh.text("JP1 closed: this board powers the FPGA board through J7/J8 pins 1-2. Leave open if the FPGA board has its own supply.", 20, 262, 1.5)
    sh.write()
    return sh

# ---------------------------------------------------------------- 電源シート
def power_sheet(sheet_uuid, page):
    sh = Sheet("power.kicad_sch", "Power: USB-C 5 V in, 3.3 V buck", sheet_uuid, page)
    sh.text("Power input: USB-C 5 V (2 A). +3V3 buck (AP63203, 2 A) feeds four per-channel 1.8 V LDOs (on channel sheets).", 20, 20, 2.0)
    # USB-C
    j = sh.symbol("Connector:USB_C_Receptacle_USB2.0_16P", "J5", "USB-C 5V in", (60, 120),
                  "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal", "USB4105-GF-A", "USB-C receptacle 16P (power only)")
    x, y, _, _, _ = j["A4"]; sh.wire(x, y, x + 10.16, y); sh.label("VBUS", x + 10.16, y, 0)
    for num in ("A1", "S1"):
        x, y, _, _, _ = j[num]; sh.power("GND", x, y, down=True)
    for num in ("A6", "A7", "B6", "B7", "A8", "B8"):
        x, y, _, _, _ = j[num]; sh.nc(x, y)
    x, y, _, _, _ = j["A5"]; sh.wire(x, y, x + 7.62, y); sh.label("CC1", x + 7.62, y, 0)
    x, y, _, _, _ = j["B5"]; sh.wire(x, y, x + 7.62, y); sh.label("CC2", x + 7.62, y, 0)
    sh.two_pin("Device:R", "R5", "5.1k", 110, 150, "CC1", "GND", R0402, "RC0402FR-075K1L", "5.1k 0402 (USB-C sink CC)")
    sh.two_pin("Device:R", "R6", "5.1k", 125, 150, "CC2", "GND", R0402, "RC0402FR-075K1L", "5.1k 0402 (USB-C sink CC)")
    # ヒューズ -> +5V
    f = sh.two_pin("Device:Polyfuse", "F1", "2A", 110, 90, "VBUS", "+5V", "Fuse:Fuse_1206_3216Metric", "1206L200/12SLYR", "PTC resettable fuse 2 A hold, 1206")
    sh.flag("VBUS", 130, 110); sh.flag("+5V", 145, 110)
    sh.text("Alternative 5 V input: J6 (2.54 mm header).", 100, 60, 1.5)
    j6 = sh.symbol("Connector_Generic:Conn_01x02", "J6", "5V ALT IN", (150, 90), "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "", "2-pin header, alternative 5 V input")
    x, y, _, _, _ = j6["1"]; sh.wire(x, y, x - 5.08, y); sh.label("VBUS", x - 5.08, y, 180)
    x, y, _, _, _ = j6["2"]; sh.power("GND", x, y, down=True)
    # バック
    u = sh.symbol("Regulator_Switching:AP63203WU", "U5", "AP63203WU", (230, 110), None, "AP63203WU-7", "3.3 V 2 A synchronous buck, TSOT-23-6")
    x, y, _, _, _ = u["3"]; sh.wire(x, y, x - 10.16, y); sh.power("+5V", x - 10.16, y); sh.junction(x - 10.16, y)
    x2, y2, _, _, _ = u["2"]; sh.wire(x2, y2, x2 - 5.08, y2); sh.label("BUCK_EN", x2 - 5.08, y2, 180)
    sh.two_pin("Device:R", "R7", "100k", 200, 140, "+5V", "BUCK_EN", R0402, "RC0402FR-07100KL", "100k 0402 (EN pull-up to VIN)")
    x, y, _, _, _ = u["4"]; sh.power("GND", x, y, down=True)
    x, y, _, _, _ = u["5"]; sh.wire(x, y, x + 7.62, y); sh.label("SW", x + 7.62, y, 0)
    x, y, _, _, _ = u["6"]; sh.wire(x, y, x + 7.62, y); sh.label("BST", x + 7.62, y, 0)
    x, y, _, _, _ = u["1"]; sh.wire(x, y, x + 7.62, y); sh.label("+3V3", x + 7.62, y, 0)     # 固定 3.3 V 版: FB は VOUT に直結
    sh.two_pin("Device:C", "C51", "0.1uF", 270, 140, "BST", "SW", C0402, MPN_C100N, "0.1uF 16V X7R 0402 (bootstrap)")
    # インダクタ: 横置きにするため 2 端子縦置きヘルパを使い、上=SW 下=+3V3
    sh.two_pin("Device:L", "L1", "4.7uH", 290, 140, "SW", "+3V3", "Inductor_SMD:L_Taiyo-Yuden_NR-40xx", "NR4018T4R7M", "4.7uH 2.2A shielded inductor 4x4 mm")
    sh.two_pin("Device:C", "C52", "10uF", 200, 180, "+5V", "GND", C0805, "GRM21BR61A106KE19L", "10uF 10V X5R 0805")
    sh.two_pin("Device:C", "C53", "10uF", 215, 180, "+5V", "GND", C0805, "GRM21BR61A106KE19L", "10uF 10V X5R 0805")
    sh.two_pin("Device:C", "C54", "0.1uF", 230, 180, "+5V", "GND", C0402, MPN_C100N, "0.1uF 16V X7R 0402")
    sh.two_pin("Device:C", "C55", "22uF", 260, 180, "+3V3", "GND", C0805, MPN_C22U, "22uF 6.3V X5R 0805")
    sh.two_pin("Device:C", "C56", "22uF", 275, 180, "+3V3", "GND", C0805, MPN_C22U, "22uF 6.3V X5R 0805")
    sh.flag("+3V3", 300, 165)
    # GND フラグ
    sh.pwr_flag(330, 200); sh.wire(330, 200, 330, 205); sh.power("GND", 330, 205, down=True)
    # LED
    d = sh.symbol("Device:LED", "D1", "PWR", (330, 120), "LED_SMD:LED_0603_1608Metric", "LTST-C193KGKT-5A", "Green LED 0603")
    x, y, _, _, _ = d["2"]; sh.wire(x, y, x + 5.08, y); sh.power("+3V3", x + 5.08, y)
    x, y, _, _, _ = d["1"]; sh.wire(x, y, x - 5.08, y); sh.label("LED_K", x - 5.08, y, 180)
    sh.two_pin("Device:R", "R8", "1k", 310, 140, "LED_K", "GND", R0402, "RC0402FR-071KL", "1k 0402")
    # 取付穴
    for i, x in enumerate((30, 45, 60, 75)):
        sh.symbol("Mechanical:MountingHole", f"H{i+1}", "M3", (x, 230), "MountingHole:MountingHole_3.2mm_M3", "", "Mounting hole M3")
    sh.text("Buck per AP63203 datasheet: CIN 2x10uF, CBST 0.1uF, L 4.7uH, COUT 2x22uF, FB tied to VOUT (fixed 3.3 V version).", 180, 205, 1.5)
    sh.write()
    return sh

# ---------------------------------------------------------------- ルート
def root_sheet(subs):
    sh = Sheet(f"{PROJECT}.kicad_sch", "Quad HDMI TX carrier (ADV7513 x4) - root", ROOT_UUID, 1)
    sh.text("Quad HDMI test pattern generator - HDMI TX carrier board", 20, 25, 4)
    sh.text("FPGA board (Artix-7) --J1/J2--> 4x ADV7513 (24-bit RGB -> TMDS) --> 4x TPD12S016 (ESD, 5V, DDC/HPD level shift) --> 4x HDMI A", 20, 32, 2)
    sheets = []
    for i, (s, x, y) in enumerate(zip(subs, (30, 30, 30, 120, 120, 120), (50, 100, 150, 50, 100, 150))):
        sheets.append([Sym("sheet"), [Sym("at"), x, y], [Sym("size"), 70, 30], [Sym("fields_autoplaced")],
                       [Sym("stroke"), [Sym("width"), 0.1524], [Sym("type"), Sym("solid")]], [Sym("fill"), [Sym("color"), 0, 0, 0, 0.0]],
                       [Sym("uuid"), s.uuid],
                       [Sym("property"), "Sheetname", s.title, [Sym("at"), x, y - 1, 0],
                        [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]], [Sym("justify"), Sym("left"), Sym("bottom")]]],
                       [Sym("property"), "Sheetfile", s.fname, [Sym("at"), x, y + 30 + 1, 0],
                        [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]], [Sym("justify"), Sym("left"), Sym("top")]]],
                       [Sym("instances"), [Sym("project"), PROJECT, [Sym("path"), f"/{ROOT_UUID}", [Sym("page"), str(s.page)]]]]])
    sh.write(sub_sheets=sheets)

def write_project():
    pro = """{
  "board": {"design_settings": {"defaults": {}, "rules": {}}, "layer_presets": [], "viewports": []},
  "boards": [], "cvpcb": {"equivalence_files": []}, "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
  "meta": {"filename": "%s.kicad_pro", "version": 1},
  "net_settings": {"classes": [{"bus_width": 12, "clearance": 0.2, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2,
    "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": "Default", "pcb_color": "rgba(0, 0, 0, 0.000)",
    "schematic_color": "rgba(0, 0, 0, 0.000)", "track_width": 0.2, "via_diameter": 0.6, "via_drill": 0.3, "wire_width": 6}], "meta": {"version": 3}},
  "pcbnew": {"last_paths": {}, "page_layout_descr_file": ""},
  "schematic": {"drawing": {}, "legacy_lib_dir": "", "legacy_lib_list": []},
  "sheets": [], "text_variables": {}
}
""" % PROJECT
    with open(os.path.join(OUT, PROJECT + ".kicad_pro"), "w") as f:
        f.write(pro)

def write_bom_and_pinmap():
    with open(os.path.join(OUT, "bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Reference", "Value", "Footprint", "MPN", "Description"])
        for ref in sorted(BOM, key=lambda r: (''.join(c for c in r if c.isalpha()), int(''.join(c for c in r if c.isdigit()) or 0))):
            b = BOM[ref]; w.writerow([ref, b["value"], b["footprint"], b["mpn"], b["desc"]])
    # 集計版
    agg = {}
    for b in BOM.values():
        k = (b["value"], b["footprint"], b["mpn"], b["desc"])
        agg.setdefault(k, []).append(b["ref"])
    with open(os.path.join(OUT, "bom_grouped.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Qty", "Value", "Footprint", "MPN", "Description", "References"])
        for k, refs in sorted(agg.items(), key=lambda kv: -len(kv[1])):
            w.writerow([len(refs), k[0], k[1], k[2], k[3], " ".join(sorted(refs))])
    with open(os.path.join(OUT, "fpga_header_pinmap.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Header", "Pin", "Signal", "FPGA_pin(fill in)", "Direction(FPGA)"])
        for ref, lst in header_pinout().items():
            for pin, net in lst:
                d = "" if net in ("GND", "FPGA_5V") else ("out" if not net.endswith(("HPD", "INT", "SDA")) else ("inout" if net.endswith("SDA") else "in"))
                w.writerow([ref, pin, net, "", d])

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    subs = [power_sheet("9c8f0a10-0000-4000-8000-000000000002", 2),
            fpga_sheet("9c8f0a10-0000-4000-8000-000000000003", 3),
            channel_sheet(1, "9c8f0a10-0000-4000-8000-000000000011", 4, "A", False),
            channel_sheet(2, "9c8f0a10-0000-4000-8000-000000000012", 5, "A", True),
            channel_sheet(3, "9c8f0a10-0000-4000-8000-000000000013", 6, "B", False),
            channel_sheet(4, "9c8f0a10-0000-4000-8000-000000000014", 7, "B", True)]
    root_sheet(subs)
    write_project()
    write_bom_and_pinmap()
    print("generated", OUT, "parts:", len(BOM))
