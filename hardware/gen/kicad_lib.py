"""KiCad シンボルライブラリから部品定義を取り出す (extends を平坦化)"""
import os, copy
from sexp import parse, find, find1, Sym

LIB_DIR = os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")
_cache = {}

def _load(lib):
    if lib not in _cache:
        with open(os.path.join(LIB_DIR, lib + ".kicad_sym")) as f:
            _cache[lib] = parse(f.read())[0]
    return _cache[lib]

def get_symbol(lib, name):
    """lib:name のシンボル定義 (S式) を返す。extends は親の本体を取り込んで平坦化する。"""
    root = _load(lib)
    for s in find(root, "symbol"):
        if s[1] == name:
            sym = copy.deepcopy(s)
            ext = find1(sym, "extends")
            if ext:
                parent = get_symbol(lib, ext[1])
                # 親のユニット (グラフィック/ピン) を子に取り込み、名前を付け替える
                merged = [Sym("symbol"), name]
                child_props = {p[1]: p for p in find(sym, "property")}
                for item in parent[2:]:
                    if isinstance(item, list) and item[0] == "property":
                        merged.append(child_props.get(item[1], item))
                    elif isinstance(item, list) and item[0] == "symbol":
                        unit = copy.deepcopy(item)
                        unit[1] = name + unit[1][len(ext[1]):]
                        merged.append(unit)
                    else:
                        merged.append(item)
                for p in child_props.values():
                    if not any(isinstance(m, list) and m[0] == "property" and m[1] == p[1] for m in merged):
                        merged.append(p)
                return merged
            return sym
    raise KeyError(f"{lib}:{name}")

def pins(sym):
    """[(number, name, type, x, y, angle, length)] (ユニット 1 のみ)"""
    out = []
    for unit in find(sym, "symbol"):
        if not (unit[1].endswith("_1_1") or unit[1].endswith("_0_1") or unit[1].endswith("_1_0")):
            continue
        for p in find(unit, "pin"):
            at = find1(p, "at"); ln = find1(p, "length")
            out.append((find1(p, "number")[1], find1(p, "name")[1], str(p[1]),
                        float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0, float(ln[1])))
    return out

def footprint(sym):
    fp = [p for p in find(sym, "property") if p[1] == "Footprint"]
    return fp[0][2] if fp else ""

if __name__ == "__main__":
    import sys
    for ref in sys.argv[1:]:
        lib, name = ref.split(":")
        s = get_symbol(lib, name)
        print(f"== {ref}  fp={footprint(s)}  extends={find1(s,'extends')}")
        for p in pins(s):
            print("   ", p)
