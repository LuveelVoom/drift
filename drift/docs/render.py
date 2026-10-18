#!/usr/bin/env python3
"""Draw a drift config's starting position as an SVG picture.

Shows the pattern (live, known dead, unknown, the gen-0 spark) and the regions
given by clear / no-change / no-count / no-check / must-reach, in rows and
columns relative to the pattern's top-left cell, as drift uses them.

Usage: docs/render.py CONFIG OUT.svg [--pad N] [--window R0 C0 R1 C1] [--cell PX]
       docs/render.py --rle FILE OUT.svg      (a finished two-state pattern)
"""
import argparse
import os
import re
import sys

STYLE = {
    "on": "#1f1f1f", "off": "#ffffff", "unknown": "#cfcfcf",
    "spark_on": "#2e9e44", "spark_off": "#d6402f", "unchecked": "#b9a3e3",
    "clear": "#dce9fb", "must-reach": "#ffc98a", "no-count": "#fff2a8",
    "no-change": "#f3b6c4", "no-check": "#b9a3e3",
}
LABEL = {
    "on": "alive", "off": "known dead", "unknown": "unknown",
    "spark_on": "alive in gen 0 only (spark)", "spark_off": "dead in gen 0 only",
    "unchecked": "unknown, background not checked", "clear": "cleared (empty)",
    "must-reach": "must-reach", "no-count": "no-count", "no-change": "no-change",
    "no-check": "no-check",
}
# dr2 characters -> cell kind
CHARS = {"o": "on", "O": "on", "3": "on", ".": "off", ":": "off", "2": "off",
         "1": "spark_on", "0": "spark_off", ",": "unknown", "?": "unknown", "s": "unknown",
         "4": "unchecked"}
LH = {0: "unknown", 1: "on", 2: "off", 3: "spark_on", 4: "spark_off", 5: "on", 6: "off"}


def parse_region(text):
    t = text.split()
    kind = t[0] if t[0] in "rltp" else "r"
    nums = list(map(int, t[1:] if t[0] in "rltp" else t))
    return kind, nums


def contains(reg, r, c):
    kind, n = reg
    if kind == "p":
        return (r, c) == (n[0], n[1])
    if kind in "rl":
        r0, c0, r1, c1 = n
        if not (min(r0, r1) <= r <= max(r0, r1) and min(c0, c1) <= c <= max(c0, c1)):
            return False
        return kind == "r" or r0 * (c1 - c) + r1 * (c - c0) + r * (c0 - c1) == 0
    r0, c0, r1, c1, r2, c2 = n
    o = r0 * (c1 - c2) + r1 * (c2 - c0) + r2 * (c0 - c1)
    return (o * (r0 * (c1 - c) + r1 * (c - c0) + r * (c0 - c1)) >= 0 and
            o * (r0 * (c - c2) + r * (c2 - c0) + r2 * (c0 - c)) >= 0 and
            o * (r * (c1 - c2) + r1 * (c2 - c) + r2 * (c - c1)) >= 0)


def load_pattern(text):
    lines = [l.rstrip("\r") for l in text.split("\n")]
    lines = [l for l in lines if l.strip() and not l.strip().startswith(("#", ";"))]
    cells = {}
    if any(l.strip().startswith("x") and "=" in l for l in lines) or any("$" in l for l in lines):
        body = "".join(l.strip() for l in lines if not (l.strip().startswith("x") and "=" in l))
        r = c = 0
        run = ""
        for ch in body:
            if ch.isdigit():
                run += ch
                continue
            n = int(run) if run else 1
            run = ""
            if ch == "!":
                break
            if ch == "$":
                r += n
                c = 0
                continue
            st = 0 if ch in "b." else 1 if ch == "o" else ord(ch) - ord("A") + 1
            for _ in range(n):
                cells[(r, c)] = LH[st]
                c += 1
    else:
        for r, l in enumerate(lines):
            for c, ch in enumerate(l.strip()):
                if ch == "!":
                    return cells
                cells[(r, c)] = CHARS.get(ch, "unknown")
            if "!" in l:
                break
    return cells


def read_config(path):
    text = open(path).read().split("\n")
    regions, pattern, i = [], None, 0
    base = os.path.dirname(os.path.abspath(path))
    while i < len(text):
        l = text[i].strip()
        i += 1
        if not l or l.startswith("#"):
            continue
        l = re.sub(r"\s+#.*$", "", l)
        if l.rstrip(":= ") == "pattern" and (l.endswith(":") or l.endswith("=")):
            block = []
            while i < len(text):
                block.append(text[i])
                i += 1
                if "!" in block[-1]:
                    break
            pattern = "\n".join(block)
            continue
        m = re.match(r"([a-z-]+)\s*=?\s*(.*)$", l)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        if key in ("clear", "no-change", "no-count", "no-check", "must-reach"):
            regions.append((key, parse_region(val)))
        elif key == "pattern":
            pattern = open(os.path.join(base, val)).read()
    return load_pattern(pattern), regions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", help="drift config, or with --rle a plain RLE file")
    ap.add_argument("--rle", action="store_true", help="draw a finished pattern (dead = white)")
    ap.add_argument("out")
    ap.add_argument("--pad", type=int, default=5)
    ap.add_argument("--window", type=int, nargs=4, metavar=("R0", "C0", "R1", "C1"))
    ap.add_argument("--cell", type=int, default=12)
    ap.add_argument("--title", default="")
    a = ap.parse_args()
    if a.rle:
        cells = {p: ("on" if k == "on" else "off") for p, k in load_pattern(open(a.config).read()).items()
                 if k == "on"}
        rs = [r for r, c in cells]
        cs = [c for r, c in cells]
        for r in range(min(rs) - a.pad, max(rs) + a.pad + 1):
            for c in range(min(cs) - a.pad, max(cs) + a.pad + 1):
                cells.setdefault((r, c), "off")
        regions = []
        a.pad = 0   # the padding is already in cells
    else:
        cells, regions = read_config(a.config)
    if a.window:
        r0, c0, r1, c1 = a.window
    else:
        rs = [r for r, c in cells] or [0]
        cs = [c for r, c in cells] or [0]
        r0, r1, c0, c1 = min(rs) - a.pad, max(rs) + a.pad, min(cs) - a.pad, max(cs) + a.pad
    S = a.cell
    W, H = (c1 - c0 + 1) * S, (r1 - r0 + 1) * S
    used = set()
    out = []
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            kind = cells.get((r, c))
            reg = [k for k, g in regions if contains(g, r, c)]
            if kind is None:
                kind = "off" if "clear" in reg else "unknown"
            fill = STYLE[kind]
            if kind == "off" and "clear" in reg and (r, c) not in cells:
                fill = STYLE["clear"]
                used.add("clear")
            else:
                used.add(kind)
            x, y = (c - c0) * S, (r - r0) * S
            out.append(f'<rect x="{x}" y="{y}" width="{S}" height="{S}" fill="{fill}"/>')
            for k in ("must-reach", "no-count", "no-change", "no-check"):
                if k in reg:
                    used.add(k)
                    inset = 2 if k == "must-reach" else 3
                    out.append(f'<rect x="{x + inset}" y="{y + inset}" width="{S - 2 * inset}" height="{S - 2 * inset}" '
                               f'fill="none" stroke="{STYLE[k]}" stroke-width="2"/>')
    # grid lines and the pattern origin
    grid = []
    for c in range(c1 - c0 + 2):
        grid.append(f'<line x1="{c * S}" y1="0" x2="{c * S}" y2="{H}"/>')
    for r in range(r1 - r0 + 2):
        grid.append(f'<line x1="0" y1="{r * S}" x2="{W}" y2="{r * S}"/>')
    ox, oy = (0 - c0) * S, (0 - r0) * S
    origin = (f'<rect x="{ox}" y="{oy}" width="{S}" height="{S}" fill="none" stroke="#2a62c9" '
              f'stroke-width="1.5" stroke-dasharray="2,2"/>') if r0 <= 0 <= r1 and c0 <= 0 <= c1 and not a.rle else ""
    order = ["on", "off", "unknown", "spark_on", "spark_off", "unchecked", "clear",
             "must-reach", "no-count", "no-change", "no-check"]
    legend = [k for k in order if k in used]
    LW, lh = 260, 18
    lx = W + 16
    leg = []
    for i, k in enumerate(legend):
        y = 8 + i * lh
        if k in ("must-reach", "no-count", "no-change", "no-check"):
            leg.append(f'<rect x="{lx + 1}" y="{y + 1}" width="10" height="10" fill="#cfcfcf" '
                       f'stroke="{STYLE[k]}" stroke-width="2"/>')
        else:
            leg.append(f'<rect x="{lx}" y="{y}" width="12" height="12" fill="{STYLE[k]}" stroke="#999" stroke-width="0.5"/>')
        leg.append(f'<text x="{lx + 18}" y="{y + 10}">{LABEL[k]}</text>')
    if origin and not a.rle:
        y = 8 + len(legend) * lh
        leg.append(f'<rect x="{lx}" y="{y}" width="12" height="12" fill="none" stroke="#2a62c9" stroke-dasharray="2,2"/>')
        leg.append(f'<text x="{lx + 18}" y="{y + 10}">row 0, col 0 of the pattern</text>')
    TW = W + LW
    TH = max(H, 8 + (len(legend) + 1) * lh) + (22 if a.title else 0)
    ty = 22 if a.title else 0
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{TW}" height="{TH}" viewBox="0 0 {TW} {TH}" '
           f'font-family="Helvetica, Arial, sans-serif" font-size="12">',
           '<rect width="100%" height="100%" fill="#ffffff"/>']
    if a.title:
        svg.append(f'<text x="0" y="15" font-weight="bold" font-size="14">{a.title}</text>')
    svg.append(f'<g transform="translate(0,{ty})">')
    svg += out
    svg.append('<g stroke="#9a9a9a" stroke-width="0.4">' + "".join(grid) + "</g>")
    svg.append(origin)
    svg.append('<g fill="#222">' + "".join(leg) + "</g>")
    svg.append("</g></svg>")
    open(a.out, "w").write("\n".join(svg))


if __name__ == "__main__":
    sys.exit(main())
