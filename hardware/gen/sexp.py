"""KiCad S 式の最小パーサ / シリアライザ"""
import re

class Sym(str):
    """クォートなしのシンボル"""
    pass

_tok = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)

def parse(text):
    pos, stack, root = 0, [], []
    cur = root
    while pos < len(text):
        m = _tok.match(text, pos)
        if not m:
            break
        pos = m.end()
        if m.group(1):
            new = []; cur.append(new); stack.append(cur); cur = new
        elif m.group(2):
            cur = stack.pop()
        elif m.group(3) is not None:
            cur.append(m.group(3).replace('\\"', '"'))
        elif m.group(4) is not None:
            cur.append(Sym(m.group(4)))
    return root

def dump(node, indent=0):
    if isinstance(node, list):
        if not node:
            return "()"
        parts = [dump(n, indent + 1) for n in node]
        flat = "(" + " ".join(parts) + ")"
        if len(flat) < 100 and not any(isinstance(n, list) and any(isinstance(m, list) for m in n) for n in node):
            return flat
        head = parts[0]
        rest = parts[1:]
        out = "(" + head
        line = out
        lines = []
        for p in rest:
            if "\n" in p or len(line) + len(p) > 100:
                lines.append(line); line = "  " * (indent + 1) + p
            else:
                line += " " + p
        lines.append(line)
        return "\n".join(lines) + ")"
    if isinstance(node, Sym):
        return str(node)
    if isinstance(node, bool):
        return "yes" if node else "no"
    if isinstance(node, int):
        return str(node)
    if isinstance(node, float):
        t = f"{round(node, 4):.4f}".rstrip("0").rstrip(".")
        return t if t not in ("", "-0") else "0"
    return '"' + str(node).replace('"', '\\"') + '"'

def find(node, name):
    """直下の子から (name ...) を全て返す"""
    return [n for n in node if isinstance(n, list) and n and n[0] == name]

def find1(node, name):
    r = find(node, name)
    return r[0] if r else None
