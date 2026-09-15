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
                        if abs(x1 - x2) + abs(y1 - y2) < 10.0), key=lambda e: e[0] + (0 if e[1][2] == e[2][2] else 1.0))
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
                    board.Remove(it)
            if ok:
                break
        print("  ", netname, "cluster of", len(cl), "->", "connected" if ok else "COULD NOT CONNECT")
        if ok:
            done += 1; main = main + cl
    return done
for z in board.Zones():                          # finish 段では外層ベタが塗られているので、一旦消して誤検出を防ぐ
    if z.GetZoneName() in ("GND_F", "GND_B"):
        z.UnFill()
baseline = drc_bad_count(os.path.join(OUT, "drc_try.rpt"))
print("baseline DRC clearance-type violations:", baseline)
n_fix = 0
for net in board.GetNetsByName().values():
    name = net.GetNetname()
    if not name or name.startswith("unconnected") or name in plane_nets:
        continue
    n_fix += connect_clusters(net.GetNetCode(), name, baseline)
print("generic cluster fixes:", n_fix)
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
def final_drc():
    pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    return open(rpt).read()
txt = final_drc()
# 片層にしか配線が付いていないビア (via_dangling) は不要なので削除する。同じ点で出会う配線同士はそのまま繋がる
dang = [(float(x), float(y)) for x, y in re.findall(r"^\[via_dangling\][^@]*@\(([-\d.]+) mm, ([-\d.]+) mm\): Via", txt, re.M)]
if dang:
    n_d = 0
    for v in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]:
        vx, vy = v.GetPosition().x / 1e6, v.GetPosition().y / 1e6
        if any(abs(vx - x) < 0.01 and abs(vy - y) < 0.01 for x, y in dang):
            board.Remove(v); n_d += 1
    print("removed dangling vias:", n_d)
    filler.Fill(board.Zones()); pcbnew.SaveBoard(PCB, board)
    txt = final_drc()
m = re.search(r"\*\* Found (\d+) DRC violations", txt); u = re.search(r"\*\* Found (\d+) unconnected pads", txt)
print("DRC violations:", m.group(1) if m else "?", " unconnected:", u.group(1) if u else "?")
kinds = re.findall(r"^\[(\w+)\]", txt, re.M)
from collections import Counter
print("  ", Counter(kinds).most_common(10))
