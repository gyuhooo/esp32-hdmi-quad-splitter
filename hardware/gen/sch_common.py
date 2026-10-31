"""回路図ジェネレータ共通部: BOM、カスタムシンボル生成、Sheet クラス、部品定数。
プロジェクトごとに configure() で名前・出力先・ルート UUID を設定してから使う。"""
import os, uuid
from sexp import Sym, dump, find, find1
from kicad_lib import get_symbol, pins as lib_pins, footprint as lib_fp

PROJECT = "project"
OUT = "."
ROOT_UUID = "00000000-0000-4000-8000-000000000001"
CFG = {"date": "2026-09-14", "rev": "A", "company": "gyuhooo", "comment": ""}
CUSTOM = {}          # lib_id -> symbol sexp (make_symbol の戻り値)。各プロジェクトが登録する

def configure(project, out, root_uuid, comment="", date="2026-09-14", rev="A"):
    """プロジェクト設定。環境変数 SCH_OUT_DIR で出力先を上書きできる (動作確認用)"""
    global PROJECT, OUT, ROOT_UUID
    PROJECT, OUT, ROOT_UUID = project, os.environ.get("SCH_OUT_DIR", out), root_uuid
    CFG.update(comment=comment, date=date, rev=rev)
    os.makedirs(OUT, exist_ok=True)
    return PROJECT, OUT, ROOT_UUID

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

    def pins_of(self, lib_id, unit=1):
        sym = self._lib(lib_id)
        # カスタムは名前が "QuadHDMI:X" のまま。ユニット名は "X_1_1"
        return lib_pins(sym, unit)

    # -- 要素
    def symbol(self, lib_id, ref, value, at, footprint=None, mpn="", desc="", rot=0, fields=None, in_bom=True, unit=1):
        sym = self._lib(lib_id)
        fp = footprint if footprint is not None else lib_fp(sym)
        x, y = at
        ppos = {}
        for num, nm, typ, px, py, ang, ln in self.pins_of(lib_id, unit):
            ppos[num] = (round(x + px, 3), round(y - py, 3), ang, nm, typ)
        def prop(k, v, dx, dy, hide=False, justify=None):
            e = [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]
            if justify: e.append([Sym("justify"), Sym(justify)])
            if hide: e.append(Sym("hide"))
            return [Sym("property"), k, v, [Sym("at"), round(x + dx, 3), round(y + dy, 3), 0], e]
        s = [Sym("symbol"), [Sym("lib_id"), lib_id], [Sym("at"), x, y, rot], [Sym("unit"), unit],
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
        s.append([Sym("instances"), [Sym("project"), PROJECT, [Sym("path"), self.path, [Sym("reference"), ref], [Sym("unit"), unit]]]])
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
        elif net in ("+5V", "+3V3", "+1V8", "+1V0", "VBUS") and int(ang) == 270:   # 上向きピン
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
        tb = [Sym("title_block"), [Sym("title"), self.title], [Sym("date"), CFG["date"]], [Sym("rev"), CFG["rev"]],
              [Sym("company"), CFG["company"]], [Sym("comment"), 1, CFG["comment"]]]
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
