#!/usr/bin/env python3
"""Specctra SES を自前で読み込み、配線とビアを pcbnew の基板に追加する (ImportSpecctraSES が使えない場合の代替)。
座標は DSN/SES の µm、y は上向きなので反転する。"""
import re, sys, os
import pcbnew
from pcbnew import VECTOR2I
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import parse, find, find1

def import_ses(board, ses_path):
    doc = parse(open(ses_path).read())[0]
    routes = find1(doc, "routes")
    res = find1(routes, "resolution") if routes else None
    # (resolution um N): 1 単位 = 1/N µm。FreeRouting の SES は N=10 (0.1 µm 単位) で書かれる
    res_n = float(res[2]) if res else 10.0
    scale = 1.0 / res_n              # 単位 -> µm
    layers = {board.GetLayerName(l): l for l in (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu)}
    layers.update({"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu, "In1.Cu": pcbnew.In1_Cu, "In2.Cu": pcbnew.In2_Cu})
    def P(x, y):
        return VECTOR2I(int(round(float(x) * scale * 1000)), int(round(-float(y) * scale * 1000)))
    n_wire = n_via = 0
    netmap = {str(k): v.GetNetCode() for k, v in board.GetNetsByName().items()}
    class _NI:
        def __init__(self, code): self.code = code
        def GetNetCode(self): return self.code
    netout = find1(routes, "network_out")
    for net in find(netout, "net"):
        name = str(net[1])
        if name not in netmap:
            print("  unknown net", name); continue
        ni = _NI(netmap[name])
        for w in find(net, "wire"):
            path = find1(w, "path"); layer = str(path[1]); width = float(path[2]) * scale * 1000
            pts = [float(v) for v in path[3:] if not isinstance(v, list)]
            for i in range(0, len(pts) - 2, 2):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(P(pts[i], pts[i + 1])); t.SetEnd(P(pts[i + 2], pts[i + 3]))
                t.SetWidth(int(width)); t.SetLayer(layers.get(layer, pcbnew.F_Cu)); t.SetNetCode(ni.GetNetCode())
                board.Add(t); n_wire += 1
        for v in find(net, "via"):
            pad = str(v[1]); m = re.search(r"_(\d+):(\d+)_um", pad)
            dia, drill = (int(m.group(1)), int(m.group(2))) if m else (600, 300)
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(P(v[2], v[3])); via.SetWidth(pcbnew.FromMM(dia / 1000)); via.SetDrill(pcbnew.FromMM(drill / 1000))
            via.SetViaType(pcbnew.VIATYPE_THROUGH); via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); via.SetNetCode(ni.GetNetCode())
            board.Add(via); n_via += 1
    return n_wire, n_via

if __name__ == "__main__":
    b = pcbnew.LoadBoard(sys.argv[1]); print(import_ses(b, sys.argv[2])); pcbnew.SaveBoard(sys.argv[1], b)
