#!/usr/bin/env python3
"""Glider-triggered reactions from a drift glider search, checked from infinity.

usage: python3 tools/gliderin.py CONFIG [CONFIG ...]     (put in drift/tools/)
  env: SECS (shrink seconds, default 10), OUT (combined RLE, default glider-reactions.rle),
       DIR glider direction as dr,dc per 4 gens (default 1,1 = down-right, as drawn in the
       configs); MAXBOX (default 16): larger still lifes are counted, not listed

For every fizzle or escape result: complete the background (finish.py), shrink it
(fizzles only), then check that the glider really comes from infinity: put it 40
periods back along its path (160 gens earlier) next to the same still life and
require the evolution to reach exactly the gen-0 pattern. Then simulate forward and
classify:
  eater      the glider is absorbed and the still life restored, no output far from it
  converter  the still life is restored and some cell outside it was alive at
             Chebyshev distance >= 4 from the gen-0 glider (a spark output)
  escape     the still life is restored and objects leave; what they are is listed
Deduplicated by still life + glider over the 8 orientations; one combined RLE.
"""
import json
import os
import sys

TOOLS = os.environ.get("DRIFT_TOOLS", os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import driftlib as L  # noqa: E402
import finish as F  # noqa: E402

SECS = float(os.environ.get("SECS", "10"))
OUT = os.environ.get("OUT", "glider-reactions.rle")
DIR = tuple(int(x) for x in os.environ.get("DIR", "1,1").split(","))
MAXBOX = int(os.environ.get("MAXBOX", "16"))   # larger still lifes (usually drift-built wires) are counted, not listed
TR = [lambda r, c: (r, c), lambda r, c: (r, -c), lambda r, c: (-r, c), lambda r, c: (-r, -c),
      lambda r, c: (c, r), lambda r, c: (c, -r), lambda r, c: (-c, r), lambda r, c: (-c, -r)]


def cheb(p, qs):
    return min(max(abs(p[0] - a), abs(p[1] - b)) for a, b in qs)


def from_infinity(still, glider, table, periods=40):
    back = frozenset((r - DIR[0] * periods, c - DIR[1] * periods) for r, c in glider)
    s = frozenset(still | back)
    for _ in range(4 * periods):
        s = frozenset(L.step(s, table))
    return s == frozenset(still | glider)


def exterior(still, pad=6):
    rs = [r for r, c in still]
    cs = [c for r, c in still]
    r0, r1, c0, c1 = min(rs) - pad, max(rs) + pad, min(cs) - pad, max(cs) + pad
    free, todo = {(r0, c0)}, [(r0, c0)]
    while todo:
        r, c = todo.pop()
        for q in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if r0 <= q[0] <= r1 and c0 <= q[1] <= c1 and q not in free and q not in still:
                free.add(q)
                todo.append(q)
    return free


def classify(still, glider, table, rule):
    rs = [r for r, c in still]
    cs = [c for r, c in still]
    box = (min(rs) - 6, max(rs) + 6, min(cs) - 6, max(cs) + 6)
    inbox = lambda p: box[0] <= p[0] <= box[1] and box[2] <= p[1] <= box[3]
    h = [frozenset(still | glider)]
    for _ in range(400):
        h.append(frozenset(L.step(h[-1], table)))
    local = [frozenset(p for p in x if inbox(p)) for x in h]
    back = next((t for t in range(1, 380) if all(local[u] == still for u in range(t, t + 20))), None)
    if back is None:
        return None
    far = h[-1] - still
    ext = exterior(still)
    if not far:
        dist = max((cheb(p, glider) for t in range(1, back) for p in h[t] - still if p in ext), default=0)
        kind = "converter" if dist >= 4 else "eater"
        return dict(kind=kind, back=back, dist=dist, what="")
    kinds = []
    for comp in L.components(far, 3):
        k = L.object_kind(frozenset(comp), table)
        kinds.append(k or f"{len(comp)}-cell object")
    return dict(kind="escape", back=back, dist=None, what=", ".join(sorted(kinds)))


def canon(still, glider):
    best = None
    for t in TR:
        a = [t(*p) for p in still | glider]
        g = {t(*p) for p in glider}
        r0 = min(p[0] for p in a)
        c0 = min(p[1] for p in a)
        k = tuple(sorted(((p[0] - r0, p[1] - c0), p in g) for p in a))
        best = k if best is None or k < best else best
    return best


def main():
    found, counts = {}, {}
    rule = None
    for cfg in sys.argv[1:]:
        rule = L.config_rule(cfg)
        table = L.rule_for(rule)
        fin = F.Finisher(cfg, table, SECS)
        for line in open(cfg[:-4] + "-results.jsonl"):
            res = json.loads(line)
            kind = res["kind"]
            if kind not in ("fizzle", "escape"):
                continue
            counts[kind] = counts.get(kind, 0) + 1
            got = fin.fizzle(res) if kind == "fizzle" else fin.escape(res)
            if not got:
                counts["no completion"] = counts.get("no completion", 0) + 1
                continue
            k2, info = got
            still = frozenset(info["still"])
            glider = frozenset(info["hist"][0]) - still
            if kind == "fizzle":
                info["empty"] = fin.empty_for(res)
                g0 = fin.shrink(k2, info) or info["hist"][0]
                still = frozenset(g0) - glider
            if len(glider) != 5 or not still:
                counts["odd"] = counts.get("odd", 0) + 1
                continue
            if not from_infinity(still, glider, table):
                counts["not from infinity"] = counts.get("not from infinity", 0) + 1
                continue
            c = classify(still, glider, table, rule)
            if not c:
                counts["not restored"] = counts.get("not restored", 0) + 1
                continue
            key = canon(still, glider)
            if key in found and len(found[key]["still"]) <= len(still):
                continue
            rs = [r for r, cc in still]
            cs = [cc for r, cc in still]
            if max(max(rs) - min(rs), max(cs) - min(cs)) + 1 > MAXBOX:
                counts["box too big"] = counts.get("box too big", 0) + 1
                continue
            c.update(still=still, glider=glider, cfg=cfg, n=res["n"],
                     w=max(cs) - min(cs) + 1, h=max(rs) - min(rs) + 1)
            found[key] = c
    order = {"escape": 0, "converter": 1, "eater": 2}
    items = sorted(found.values(), key=lambda o: (order[o["kind"]], -(o["dist"] or 0), len(o["still"])))
    print("counts:", counts, "kept:", len(items))
    allc, x, y, rowh = set(), 0, 0, 0
    for i, o in enumerate(items):
        if i and i % 8 == 0:
            y, x, rowh = y + rowh + 12, 0, 0
        cells = o["still"] | o["glider"]
        r0 = min(p[0] for p in cells)
        c0 = min(p[1] for p in cells)
        w = max(p[1] for p in cells) - c0 + 1
        allc |= {(p[0] - r0 + y, p[1] - c0 + x) for p in cells}
        rowh = max(rowh, max(p[0] for p in cells) - r0 + 1)
        x += w + 12
        extra = f"output dist {o['dist']}" if o["kind"] != "escape" else f"out: {o['what']}"
        print(f"{i + 1:3d}. row {i // 8 + 1} col {i % 8 + 1}: {o['kind']}, still life {o['w']}x{o['h']} "
              f"{len(o['still'])} cells, {extra}, still life back by gen {o['back']}   [{o['cfg']} #{o['n']}]")
        print("     " + "".join(L.to_rle(cells, rule).split("\n")[1:]))
    if items:
        lines = L.to_rle(allc, rule).split("\n")
        with open(OUT, "w") as f:
            f.write(lines[0].replace(" ", "") + "\n" + "".join(lines[1:]) + "\n")
        print(f"all {len(items)} in one pattern: {OUT}")


if __name__ == "__main__":
    main()
