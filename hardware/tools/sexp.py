"""Minimal KiCad s-expression parser / serializer."""
import re

class Sym(str):
    """A bare symbol (unquoted token)."""
    __slots__ = ()

_tok = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)

def parse(text):
    pos = 0
    stack = [[]]
    n = len(text)
    while pos < n:
        m = _tok.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError("bad token at %d: %r" % (pos, text[pos:pos+40]))
        pos = m.end()
        if m.group(1):
            stack.append([])
        elif m.group(2):
            lst = stack.pop()
            stack[-1].append(lst)
        elif m.group(3) is not None:
            stack[-1].append(m.group(3).replace('\\"', '"'))
        elif m.group(4) is not None:
            stack[-1].append(Sym(m.group(4)))
    if len(stack) != 1:
        raise ValueError("unbalanced parens")
    return stack[0]

def _fmt_num(v):
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, int):
        return str(v)
    s = ("%.6f" % v).rstrip("0").rstrip(".")
    if s in ("-0", ""):
        s = "0"
    return s

def dump(node, indent=0):
    """Serialize a nested list back to s-expression text (KiCad-ish formatting)."""
    if isinstance(node, list):
        if not node:
            return "()"
        head = node[0]
        parts = []
        for x in node:
            parts.append(dump(x, indent + 1))
        # put each sublist on its own line if there are any sublists
        if any(isinstance(x, list) for x in node[1:]):
            out = "(" + parts[0]
            i = 1
            # keep leading atoms on the same line
            while i < len(node) and not isinstance(node[i], list):
                out += " " + parts[i]
                i += 1
            for p in parts[i:]:
                out += "\n" + "\t" * (indent + 1) + p
            out += "\n" + "\t" * indent + ")"
            return out
        return "(" + " ".join(parts) + ")"
    if isinstance(node, Sym):
        return str(node)
    if isinstance(node, bool):
        return "yes" if node else "no"
    if isinstance(node, (int, float)):
        return _fmt_num(node)
    # string -> quoted
    return '"' + str(node).replace('\\', '\\\\').replace('"', '\\"') + '"'

def find_all(node, key):
    """Yield direct children lists whose head symbol == key."""
    for x in node:
        if isinstance(x, list) and x and x[0] == key:
            yield x

def find(node, key):
    for x in find_all(node, key):
        return x
    return None

def num(x):
    try:
        return float(x)
    except Exception:
        return None
