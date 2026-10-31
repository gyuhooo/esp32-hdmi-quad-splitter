#!/usr/bin/env python3
"""基板の自動配線: DSN 書き出し -> FreeRouting -> SES 読み込み -> ゾーン塗り -> DRC。
使い方:
  route_pcb.py export                 # quad_hdmi_tx.dsn を書き出す (PCB_PROJECT=fpga_main で FPGA 基板)
  java -jar freerouting.jar -de quad_hdmi_tx.dsn -do quad_hdmi_tx.ses -mp 40 -mt 4   # 別途実行
  route_pcb.py import                 # SES 取り込み、ゾーン塗り、DRC
"""
import os, sys, subprocess, time, re, math
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.environ.get("PCB_PROJECT", "quad_hdmi_tx")        # quad_hdmi_tx (キャリア) または fpga_main
OUT = os.path.normpath(os.path.join(HERE, "..", PROJECT))
PCB = os.path.join(OUT, PROJECT + ".kicad_pcb")
STAGE = sys.argv[1] if len(sys.argv) > 1 else "export"
DSN = os.path.join(OUT, PROJECT + ".dsn")
SES = os.path.join(OUT, PROJECT + ".ses")
if STAGE in ("export-inc", "import-inc"):        # 追加配線: 配線済みの基板を固定して未配線ネットだけルータに渡す
    DSN = os.path.join(OUT, PROJECT + "_inc.dsn"); SES = os.path.join(OUT, PROJECT + "_inc.ses")
if STAGE == "export-cont":                       # 継続配線: 配線済みを初期状態 (引き剥がし可) として渡す。結果の SES は PROJECT.ses に置いて import する
    DSN = os.path.join(OUT, PROJECT + "_cont.dsn")
def unrouted_nets():
    """最後の DRC レポートの未接続項目からネット名を集める"""
    rpt_ = os.path.join(OUT, "drc.rpt")
    if not os.path.exists(rpt_): return set()
    txt_ = open(rpt_).read()
    return set(re.findall(r"^\[unconnected_items\][^\n]*\n(?:[^\n]*\n){0,1}[^\n]*\[([^\]]+)\]", txt_, re.M)) | \
           set(re.findall(r"^\[unconnected_items\][^\n]*\n(?:[^\n]*\n){2}[^\n]*\[([^\]]+)\]", txt_, re.M))

if STAGE in ("export", "export-inc", "export-cont"):
    board = pcbnew.LoadBoard(PCB)
    for z in list(board.Zones()):            # 仕上げ段で足した外層 GND ベタはルータに渡さない
        if z.GetZoneName() in ("GND_F", "GND_B"):
            board.Delete(z)
    for t in list(board.GetTracks()):        # ロックされたファンアウトビアは残す。追加配線では配線済みを全て固定する。継続配線ではそのまま渡す (引き剥がし可)
        if STAGE == "export-inc":
            t.SetLocked(True)
        elif STAGE == "export" and not t.IsLocked():
            board.Delete(t)
    if PROJECT == "fpga_main":               # ルータ用のビア禁止領域 (保存しない): BGA 直下 (プレーンのメッシュを切らない) と +1V0 の腕
        import fpga_common as F
        fx, fy = F.FPGA_XY
        def rule_area(pts, vias, tracks, layers):
            z = pcbnew.ZONE(board); z.SetIsRuleArea(True); z.SetDoNotAllowVias(vias); z.SetDoNotAllowTracks(tracks)
            z.SetDoNotAllowCopperPour(False); z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
            if layers == "all": z.SetLayerSet(pcbnew.LSET.AllCuMask(board.GetCopperLayerCount()))
            else: z.SetLayer(layers)
            o = z.Outline(); o.NewOutline()
            for x, y in pts:
                o.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
            board.Add(z)
        def rect(x0, y0, x1, y1):
            return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        rule_area(rect(fx - 8.0, fy - 8.0, fx + 8.0, fy + 8.0), True, False, "all")          # BGA 直下: ビア禁止 (全層)
        rule_area(rect(fx - 0.7, fy + 8.0, fx + 0.7, fy + 11.3), True, False, "all")         # +1V0 の腕 (In4): ビア禁止
        rule_area(rect(fx - 8.0, fy - 8.0, fx + 8.0, fy + 8.0), True, True, pcbnew.B_Cu)     # BGA 直下の裏面: +1V8 ベタを切らない
        rule_area([(fx + 8.0, fy - 1.0), (101.5, fy - 1.0), (101.5, 66.0), (89.0, 66.0), (89.0, fy + 2.0), (fx + 8.0, fy + 2.0)],
                  True, True, pcbnew.B_Cu)                                                   # +1V8 の帯 (裏面): 配線・ビア禁止
        eb_ = board.GetBoardEdgesBoundingBox()
        L_, T_, R_, B_ = eb_.GetLeft() / 1e6 + 0.05, eb_.GetTop() / 1e6 + 0.05, eb_.GetRight() / 1e6 - 0.05, eb_.GetBottom() / 1e6 - 0.05
        for pts in (rect(L_, T_, L_ + 0.45, B_), rect(R_ - 0.45, T_, R_, B_), rect(L_, T_, R_, T_ + 0.45), rect(L_, B_ - 0.45, R_, B_)):
            rule_area(pts, True, True, "all")                                                # 外形から 0.45 mm は配線・ビア禁止 (銅-外形 0.3 mm)
    ok = pcbnew.ExportSpecctraDSN(board, DSN)
    print("DSN export:", ok, os.path.getsize(DSN), "unrouted nets:", sorted(unrouted_nets()) if STAGE == "export-inc" else "")
    sys.exit(0)
if STAGE in ("import", "import-inc") and not os.path.exists(SES):
    print("no SES file"); sys.exit(1)

board = pcbnew.LoadBoard(PCB)
if STAGE == "import-inc":
    from ses_import import import_ses
    nets_ = unrouted_nets()
    print("incremental import for nets:", sorted(nets_), import_ses(board, SES, nets_))
elif STAGE == "import":
    # pcbnew.ImportSpecctraSES はこの環境では失敗し、その後 board ハンドルが無効になるため自前パーサだけを使う
    from ses_import import import_ses
    for t in list(board.GetTracks()):        # 二重取り込みを避け、ロック済みファンアウトだけ残す
        if not t.IsLocked():
            board.Delete(t)
    print("SES parser:", import_ses(board, SES))
    inc = os.path.join(OUT, PROJECT + "_inc.ses")           # 追加配線 (export-inc -> FreeRouting) があれば、未配線だったネットだけ重ねる
    if os.path.exists(inc) and unrouted_nets():
        print("incremental SES:", sorted(unrouted_nets()), import_ses(board, inc, unrouted_nets()))
else:
    print("finish stage: reusing routed board")
print("tracks:", len(list(board.GetTracks())))
# 注意: board.Remove() はこの環境の pcbnew (7.0.11) で Python 側の参照を壊し、以後 Tracks()/Zones() が SwigPyObject になる。board.Delete() を使う
# ルータが基板端に寄せすぎたビア/配線端点を、銅-外形 0.3 mm を満たす位置まで内側へずらす (DSN には外形クリアランスが渡らない)
eb = board.GetBoardEdgesBoundingBox()           # 外形線の線幅 0.1 を含むので 0.05 内側が実際の外形
Lb, Tb, Rb, Hb = eb.GetLeft() / 1e6 + 0.05, eb.GetTop() / 1e6 + 0.05, eb.GetRight() / 1e6 - 0.05, eb.GetBottom() / 1e6 - 0.05
n_nudge = 0
def move_point(old, new):
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and not t.IsLocked():
            if t.GetStart() == old: t.SetStart(new)
            if t.GetEnd() == old: t.SetEnd(new)
def inside(x, y, r_):
    """(x, y) を外形から r_ + 0.3 以上内側へ"""
    return (min(max(x, Lb + 0.31 + r_), Rb - 0.31 - r_), min(max(y, Tb + 0.31 + r_), Hb - 0.31 - r_))
for via in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and not t.IsLocked()]:
    r_ = via.GetWidth() / 2e6; x, y = via.GetPosition().x / 1e6, via.GetPosition().y / 1e6
    nx, ny = inside(x, y, r_)
    if (nx, ny) != (x, y):
        old = pcbnew.VECTOR2I(via.GetPosition()); new = pcbnew.VECTOR2I(pcbnew.FromMM(nx), pcbnew.FromMM(ny))
        move_point(old, new); via.SetPosition(new); n_nudge += 1
for t in [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and not t.IsLocked()]:
    hw = t.GetWidth() / 2e6
    for p in (t.GetStart(), t.GetEnd()):
        x, y = p.x / 1e6, p.y / 1e6
        nx, ny = inside(x, y, hw)
        if (nx, ny) != (x, y):
            old = pcbnew.VECTOR2I(p); new = pcbnew.VECTOR2I(pcbnew.FromMM(nx), pcbnew.FromMM(ny))
            move_point(old, new); n_nudge += 1
print("nudged vias/track ends away from board edges:", n_nudge)
# (使われなかったアクセスビアは、最後に DRC の via_dangling を見て削除する。ロック済み配線だけで完結する事前配線を壊さないため)
plane_nets = {"GND", "+3V3", "+1V0", "+1V8", "+5V"} if PROJECT == "fpga_main" else {"GND", "+3V3"} | {f"CH{n}_1V8" for n in range(1, 5)}
# オートルータが残した未接続 (同一ネット内の島) を、島同士の最寄りの端点間で L 字 / 直線 / B.Cu 経由 (ビア 2 個) で接続する。
# 候補はまず他ネットの銅との衝突を幾何で除外し、通ったものだけ DRC で確認する (違反が増えたら取り消す)
def uid(item):
    return item.m_Uuid.AsString()
def net_clusters(netcode):
    board.BuildConnectivity(); cn = board.GetConnectivity()
    items = [t for t in board.GetTracks() if t.GetNetCode() == netcode]
    items += [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() == netcode]
    seen, clusters = set(), []
    for it in items:
        if uid(it) in seen:
            continue
        stack, cl = [it], []
        while stack:
            x = stack.pop()
            if uid(x) in seen:
                continue
            seen.add(uid(x)); cl.append(x)
            for y in list(cn.GetConnectedTracks(x)) + list(cn.GetConnectedPads(x)):
                if uid(y) not in seen:
                    stack.append(y)
        clusters.append(cl)
    return clusters
def endpoints(cluster):
    """(x, y, layer) の集合: F/B の配線端点、ビア (両層)、SMD パッド中心"""
    pts = set()
    for it in cluster:
        if it.GetClass() == "PCB_VIA":
            p = it.GetPosition(); pts.add((p.x / 1e6, p.y / 1e6, pcbnew.F_Cu)); pts.add((p.x / 1e6, p.y / 1e6, pcbnew.B_Cu))
        elif it.GetClass() == "PCB_TRACK":
            for p in (it.GetStart(), it.GetEnd()):
                pts.add((p.x / 1e6, p.y / 1e6, it.GetLayer()))
        elif it.GetClass() == "PAD" and it.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
            p = it.GetPosition(); pts.add((p.x / 1e6, p.y / 1e6, it.GetLayer()))
    return pts
def mk_track(a, b, layer, netcode, width=0.15):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(a[0]), pcbnew.FromMM(a[1]))); t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(b[0]), pcbnew.FromMM(b[1])))
    t.SetWidth(pcbnew.FromMM(width)); t.SetLayer(layer); t.SetNetCode(netcode)
    return t
def mk_via(p, netcode, dia=0.5, drill=0.3):
    v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(p[0]), pcbnew.FromMM(p[1])))
    v.SetDrill(pcbnew.FromMM(drill)); v.SetWidth(pcbnew.FromMM(dia)); v.SetNetCode(netcode); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    return v
def collides(new_items, netcode, clr=0.16):
    """新規アイテムが他ネットの配線・ビア・パッドに幾何的に衝突するか"""
    c = pcbnew.FromMM(clr)
    for ni in new_items:
        layers = [pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu] if ni.GetClass() == "PCB_VIA" else [ni.GetLayer()]
        for layer in layers:
            s = ni.GetEffectiveShape(layer)
            for t in board.GetTracks():
                if t.GetNetCode() == netcode:
                    continue
                if t.GetClass() != "PCB_VIA" and t.GetLayer() != layer:
                    continue
                if s.Collide(t.GetEffectiveShape(layer), c):
                    return True
            for fp in board.GetFootprints():
                for p in fp.Pads():
                    if p.GetNetCode() == netcode and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                        continue
                    if not p.IsOnLayer(layer) and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                        continue
                    if s.Collide(p.GetEffectiveShape(layer), c + (pcbnew.FromMM(0.1) if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH else 0)):
                        return True
    return False
def drc_bad_count(path):
    pcbnew.WriteDRCReport(board, path, pcbnew.EDA_UNITS_MILLIMETRES, True)
    rep = open(path).read()
    return len(re.findall(r"^\[(clearance|shorting_items|copper_edge_clearance|hole_clearance|track_dangling)\]", rep, re.M))
def candidate_paths(a, b, netcode):
    """a, b: (x, y, layer)。同層なら L 字 2 通り + 直線、異層/失敗時は a にビアを打って B.Cu で L 字、b にビア"""
    ax, ay, al = a; bx, by, bl = b
    out = []
    if al == bl:
        for mid in ((bx, ay), (ax, by)):
            segs = [((ax, ay), mid), (mid, (bx, by))]
            out.append([mk_track(p, q, al, netcode) for p, q in segs if p != q])
        out.append([mk_track((ax, ay), (bx, by), al, netcode)])
    other = pcbnew.B_Cu if al == pcbnew.F_Cu else pcbnew.F_Cu
    for mid in ((bx, ay), (ax, by)):
        items = [mk_via((ax, ay), netcode)]
        items += [mk_track(p, q, other, netcode) for p, q in (((ax, ay), mid), (mid, (bx, by))) if p != q]
        if bl != other:
            items.append(mk_via((bx, by), netcode))
        out.append(items)
    return out
def connect_clusters(netcode, netname, baseline):
    cls = net_clusters(netcode)
    if len(cls) < 2:
        return 0
    cls.sort(key=len, reverse=True)
    main = cls[0]; done = 0
    for cl in cls[1:]:
        pa, pb = endpoints(main), endpoints(cl)
        pairs = sorted(((abs(x1 - x2) + abs(y1 - y2), (x1, y1, l1), (x2, y2, l2)) for x1, y1, l1 in pa for x2, y2, l2 in pb
                        if abs(x1 - x2) + abs(y1 - y2) < 30.0), key=lambda e: e[0] + (0 if e[1][2] == e[2][2] else 1.0))
        ok = False
        for d, a, b in pairs[:12]:
            for items in candidate_paths(b, a, netcode):
                if collides(items, netcode):
                    continue
                for it in items:
                    board.Add(it)
                if drc_bad_count(os.path.join(OUT, "drc_try.rpt")) <= baseline:
                    ok = True; break
                for it in items:
                    board.Delete(it)
            if ok:
                break
        print("  ", netname, "cluster of", len(cl), "->", "connected" if ok else "COULD NOT CONNECT")
        if ok:
            done += 1; main = main + cl
    return done
for z in board.Zones():                          # finish 段では外層ベタが塗られているので、一旦消して誤検出を防ぐ
    if z.GetZoneName() in ("GND_F", "GND_B"):
        z.UnFill()
# 手配線 (ルータが最後まで通せなかったネット): 既存配線の端点に繋ぐ。ネットが未接続のときだけ追加する
MANUAL = {"fpga_main": [("INIT_B", (65.5, 69.7875), [("F.Cu", [(65.5, 70.85)]), ("via", (65.5, 70.85)), ("B.Cu", [(65.5, 62.5)]), ("via", (65.5, 62.5)), ("F.Cu", [(65.5, 61.49), (64.5, 61.49)])])]}
# INIT_B: LED D3 のカソードパッド (65.5, 69.79) から下のビアへ、裏面を上がって、R (INIT_B プルアップ) の INIT_B パッド (64.5, 61.49) へ
board.BuildConnectivity()
for netname, start_near, steps in MANUAL.get(PROJECT, []):
    ni = board.FindNet(netname)
    if ni is None: continue
    nc = ni.GetNetCode()
    if not any(netname in ln for ln in re.findall(r"^\[unconnected_items\][^\n]*\n(?:[^\n]*\n){1,2}", open(os.path.join(OUT, "drc_try.rpt")).read() if os.path.exists(os.path.join(OUT, "drc_try.rpt")) else "", re.M)):
        pcbnew.WriteDRCReport(board, os.path.join(OUT, "drc_try.rpt"), pcbnew.EDA_UNITS_MILLIMETRES, True)
    rep_ = open(os.path.join(OUT, "drc_try.rpt")).read()
    if f"[{netname}]" not in rep_.split("[unconnected_items]", 1)[-1] if "[unconnected_items]" in rep_ else True:
        continue
    ends_ = [pcbnew.VECTOR2I(q) for t in board.GetTracks() if t.GetNetCode() == nc and t.GetClass() == "PCB_TRACK" for q in (t.GetStart(), t.GetEnd())]
    p0 = min(ends_, key=lambda q: math.hypot(q.x / 1e6 - start_near[0], q.y / 1e6 - start_near[1]), default=None)
    prev = (p0.x / 1e6, p0.y / 1e6) if p0 is not None and math.hypot(p0.x / 1e6 - start_near[0], p0.y / 1e6 - start_near[1]) < 0.3 else start_near
    for kind, data in steps:
        if kind == "via":
            board.Add(mk_via(data, nc, dia=0.5, drill=0.3)); prev = data
        else:
            layer = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu, "In2.Cu": pcbnew.In2_Cu, "In3.Cu": pcbnew.In3_Cu}[kind]
            for q in data:
                board.Add(mk_track(prev, q, layer, nc)); prev = q
    print("manual route added:", netname, "from", prev)
baseline = drc_bad_count(os.path.join(OUT, "drc_try.rpt"))
print("baseline DRC clearance-type violations:", baseline)
n_fix = 0
for net in board.GetNetsByName().values():
    name = net.GetNetname()
    if not name or name.startswith("unconnected") or name in plane_nets:
        continue
    n_fix += connect_clusters(net.GetNetCode(), name, baseline)
print("generic cluster fixes:", n_fix)
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
def final_drc():
    pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    return open(rpt).read()
txt = final_drc()
def seg_d(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0: return math.hypot(px - x1, py - y1)
    tt = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + tt * dx), py - (y1 + tt * dy))
def unconnected_count():
    board.BuildConnectivity()
    return board.GetConnectivity().GetUnconnectedCount(False)
def trim_dangling(txt):
    """片端が浮いた配線 (ルータが使わなかった事前配線の端や余り): 途中に他の配線/ビア/パッドが接続していればそこまで切り詰め、
    無ければ削除する。1 本ごとにラッツネストの未接続数が増えないことを確かめ、増えたら元に戻す。戻り値: 変更数"""
    dang = [(float(x), float(y), ly) for x, y, ly in re.findall(r"^\[track_dangling\][^@]*@\(([-\d.]+) mm, ([-\d.]+) mm\): Track \[[^\]]*\] on (\S+),", txt, re.M)]
    if not dang:
        return 0
    base = unconnected_count()
    n = 0
    for t in [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]:
        ends = [pcbnew.VECTOR2I(t.GetStart()), pcbnew.VECTOR2I(t.GetEnd())]
        for k, p in enumerate(ends):
            if not any(abs(p.x / 1e6 - x) < 0.01 and abs(p.y / 1e6 - y) < 0.01 and t.GetLayerName() == ly for x, y, ly in dang):
                continue
            cn = board.GetConnectivity()
            x1, y1, x2, y2 = ends[0].x / 1e6, ends[0].y / 1e6, ends[1].x / 1e6, ends[1].y / 1e6
            pts = []
            for o in cn.GetConnectedTracks(t):
                for q in ((o.GetPosition(),) if o.GetClass() == "PCB_VIA" else (o.GetStart(), o.GetEnd())):
                    if seg_d(q.x / 1e6, q.y / 1e6, x1, y1, x2, y2) < 0.02 + (o.GetWidth() / 2e6 if o.GetClass() == "PCB_VIA" else 0):
                        pts.append(pcbnew.VECTOR2I(q))
            for pad in cn.GetConnectedPads(t):
                pts.append(pcbnew.VECTOR2I(pad.GetPosition()))
            # 浮いている端 = 接続点が 0.3 mm 以内に無い方 (DRC のマーカは配線の始点なので当てにしない)
            def near(e): return any(math.hypot((q.x - e.x) / 1e6, (q.y - e.y) / 1e6) < 0.12 for q in pts)
            if near(ends[k]) and not near(ends[1 - k]):
                k = 1 - k; p = ends[k]
            other = ends[1 - k]
            inner = [q for q in pts if math.hypot((q.x - other.x) / 1e6, (q.y - other.y) / 1e6) > 0.02 and math.hypot((q.x - p.x) / 1e6, (q.y - p.y) / 1e6) > 0.02]
            near_via = [q for q in pts if math.hypot((q.x - p.x) / 1e6, (q.y - p.y) / 1e6) <= 0.45]
            if t.GetLength() < pcbnew.FromMM(0.12):            # ごく短い浮き断片は削除 (接続が切れれば戻す)
                dup = t.Duplicate(); board.Delete(t)
                if unconnected_count() > base:
                    board.Add(dup); unconnected_count(); break
                n += 1; break
            if inner:
                q = max(inner, key=lambda q: math.hypot((q.x - other.x) / 1e6, (q.y - other.y) / 1e6))
                if k == 0: t.SetStart(q)
                else: t.SetEnd(q)
                if unconnected_count() > base:                 # 接続が切れた: 元に戻す
                    if k == 0: t.SetStart(p)
                    else: t.SetEnd(p)
                    unconnected_count(); break
            elif near_via:                                     # 端のすぐ脇のビアに乗っている: 端をビア中心へ寄せる
                q = min(near_via, key=lambda q: math.hypot((q.x - p.x) / 1e6, (q.y - p.y) / 1e6))
                if k == 0: t.SetStart(q)
                else: t.SetEnd(q)
                if unconnected_count() > base:
                    if k == 0: t.SetStart(p)
                    else: t.SetEnd(p)
                    unconnected_count(); break
            else:
                dup = t.Duplicate(); board.Delete(t)
                if unconnected_count() > base:
                    board.Add(dup); unconnected_count(); break
            n += 1
            break
    return n
def remove_dangling_vias(txt):
    dang = [(float(x), float(y)) for x, y in re.findall(r"^\[via_dangling\][^@]*@\(([-\d.]+) mm, ([-\d.]+) mm\): Via", txt, re.M)]
    n_d = 0
    base = unconnected_count()
    for v in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]:
        vx, vy = v.GetPosition().x / 1e6, v.GetPosition().y / 1e6
        if any(abs(vx - x) < 0.01 and abs(vy - y) < 0.01 for x, y in dang):
            pos = pcbnew.VECTOR2I(v.GetPosition())
            removed = []
            # そのビアにしか繋がっていない短いロック済み引き出し線 (アクセスビアのスタブ) も一緒に消す
            for t in [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.IsLocked() and t.GetLength() < pcbnew.FromMM(3.0)]:
                if t.GetStart() == pos or t.GetEnd() == pos:
                    removed.append(t.Duplicate()); board.Delete(t)
            removed.append(v.Duplicate()); board.Delete(v)
            if unconnected_count() > base:                     # 接続が切れた: 元に戻す
                for it in removed: board.Add(it)
                unconnected_count(); continue
            n_d += 1
    return n_d
for t in [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLength() < pcbnew.FromMM(0.05)]:
    board.Delete(t)                                  # 長さ 0 の配線 (切り詰めの残骸) は消す
def split_t_junctions():
    """ルータの配線端がロック済み配線 (事前配線) の途中に乗っている所で、そのロック済み配線を分割する。
    KiCad の接続判定では繋がっているが、浮き配線の判定が端点同士の接続しか見ないため、分割しないと余りの部分を切り詰められない"""
    locked = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.IsLocked()]
    ends = {}
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and not t.IsLocked():
            for q in (t.GetStart(), t.GetEnd()):
                ends.setdefault((t.GetNetCode(), t.GetLayer()), []).append(q)
    n = 0
    for t in locked:
        pts_ = []
        for q in ends.get((t.GetNetCode(), t.GetLayer()), []):
            x1, y1, x2, y2 = t.GetStart().x / 1e6, t.GetStart().y / 1e6, t.GetEnd().x / 1e6, t.GetEnd().y / 1e6
            if seg_d(q.x / 1e6, q.y / 1e6, x1, y1, x2, y2) < 0.005 and min(math.hypot(q.x / 1e6 - x1, q.y / 1e6 - y1), math.hypot(q.x / 1e6 - x2, q.y / 1e6 - y2)) > 0.05:
                pts_.append(q)
        if not pts_: continue
        q = pts_[0]
        t2 = t.Duplicate(); t2.SetStart(pcbnew.VECTOR2I(q)); t2.SetLocked(True); board.Add(t2)
        t.SetEnd(pcbnew.VECTOR2I(q)); n += 1
    return n
for _ in range(4):
    if not split_t_junctions(): break
for t in [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLength() < pcbnew.FromMM(0.05)]:
    board.Delete(t)                                  # 分割で出来た長さ 0 の断片
for _ in range(12):
    n1 = trim_dangling(txt)
    if n1:
        filler.Fill(board.Zones()); pcbnew.SaveBoard(PCB, board); txt = final_drc()
    n2 = remove_dangling_vias(txt)
    if n2:
        filler.Fill(board.Zones()); pcbnew.SaveBoard(PCB, board); txt = final_drc()
    print("dangling cleanup: trimmed/removed tracks", n1, " removed vias", n2)
    if not n1 and not n2:
        break
m = re.search(r"\*\* Found (\d+) DRC violations", txt); u = re.search(r"\*\* Found (\d+) unconnected pads", txt)
print("DRC violations:", m.group(1) if m else "?", " unconnected:", u.group(1) if u else "?")
kinds = re.findall(r"^\[(\w+)\]", txt, re.M)
from collections import Counter
print("  ", Counter(kinds).most_common(10))
for m in list(re.finditer(r"^\[(clearance|hole_clearance|copper_edge_clearance|solder_mask_bridge|shorting_items)\][^\n]*\n((?:    [^\n]*\n)+)", txt, re.M))[:16]:
    print("    ", m.group(1), "|", " / ".join(l.strip() for l in m.group(2).strip().split("\n")))
