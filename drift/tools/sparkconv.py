#!/usr/bin/env python3
"""Pick spark converters out of drift fizzle results (B/S, INT or MAP rules).

usage: python3 tools/sparkconv.py CONFIG [CONFIG ...]     (put this file in drift/tools/)
  env: MIND    smallest output distance to keep (default 2)
       MAXBOX  largest still-life box side to keep (default 10)
       SECS    seconds per shrink (default 15)
       OUT     combined RLE file (default converters.rle)

For every fizzle in CONFIG-results.jsonl: complete the background (finish.py's
Finisher), shrink it, re-simulate from gen 0 and require the still life to be
fully back. The input spark is the gen-0 cells that aren't in the still life.
An output is a cell born outside the still life (in the dead region 4-connected
to the outside). Reported per converter:
  dist    largest Chebyshev distance from the input spark of any output cell
  clean   the same, counting only output cells that some outside cell sees
          without also seeing a still-life cell (a receiver needn't touch the
          catalyst); 0 if none
  gen     first generation an output at distance `dist` appears
  back    generation from which the still life is restored
Converters are deduplicated over the 8 orientations (still life + spark),
sorted by box, and laid out 10 cells apart in one RLE (OUT). Coordinates are
drift's result coordinates (row, col).
"""
import json
import os
import sys

TOOLS = os.environ.get("DRIFT_TOOLS", os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import driftlib as L  # noqa: E402
import finish as F  # noqa: E402

MIND = int(os.environ.get("MIND", "2"))
MAXBOX = int(os.environ.get("MAXBOX", "10"))
SECS = float(os.environ.get("SECS", "15"))
OUT = os.environ.get("OUT", "converters.rle")
TR = [lambda r, c: (r, c), lambda r, c: (r, -c), lambda r, c: (-r, c), lambda r, c: (-r, -c),
      lambda r, c: (c, r), lambda r, c: (c, -r), lambda r, c: (-c, r), lambda r, c: (-c, -r)]


def around(p):
    r, c = p
    return [(r + i, c + j) for i in (-1, 0, 1) for j in (-1, 0, 1)]


def exterior(still, pad=4):
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


def cheb(p, qs):
    return min(max(abs(p[0] - a), abs(p[1] - b)) for a, b in qs)


def box(cells):
    rs = [r for r, c in cells]
    cs = [c for r, c in cells]
    return max(cs) - min(cs) + 1, max(rs) - min(rs) + 1   # width, height


def outputs(still, hist):
    """(dist, gen, clean) over the reaction hist[1:]."""
    spark = hist[0] - still
    ext = exterior(still)
    best, clean = (0, 0), 0
    for t in range(1, len(hist)):
        for p in hist[t] - still:
            if p not in ext:
                continue
            d = cheb(p, spark)
            if d > best[0]:
                best = (d, t)
            if d > clean and any(q in ext and not any(x in still for x in around(q)) for q in around(p)):
                clean = d
    return best[0], best[1], clean


def canon(g0, spark):
    best = None
    for t in TR:
        a = [t(*p) for p in g0]
        s = {t(*p) for p in spark}
        r0 = min(p[0] for p in a)
        c0 = min(p[1] for p in a)
        k = tuple(sorted(((p[0] - r0, p[1] - c0), p in s) for p in a))
        best = k if best is None or k < best else best
    return best


def harvest(cfg, found, counts):
    rule = L.config_rule(cfg)
    table = L.rule_for(rule)
    fin = F.Finisher(cfg, table, SECS)
    for line in open(cfg[:-4] + "-results.jsonl"):
        res = json.loads(line)
        if res["kind"] != "fizzle":
            continue
        counts["fizzles"] += 1
        got = fin.fizzle(res)
        if not got:
            counts["no completion"] += 1
            continue
        kind, info = got
        spark = set(info["hist"][0]) ^ set(info["still"])
        g0 = fin.shrink(kind, info) or info["hist"][0]
        still = frozenset(set(g0) ^ spark)
        if not still:
            continue
        h = [frozenset(g0)]
        for _ in range(res["gen"] + 6):
            h.append(frozenset(L.step(h[-1], table)))
        if h[-1] != still or h[-2] != still:
            counts["not restored"] += 1
            continue
        dist, gen, clean = outputs(still, h)
        if dist < MIND:
            counts["output too close"] += 1
            continue
        w, hh = box(still)
        if max(w, hh) > MAXBOX:
            counts["box too big"] += 1
            continue
        k = canon(g0, h[0] - still)
        if k in found and found[k]["cells"] <= len(still):
            counts["duplicate"] += 1
            continue
        back = max(t for t in range(len(h)) if h[t] != still) + 1
        found[k] = dict(cfg=cfg, n=res["n"], dist=dist, gen=gen, clean=clean, back=back,
                        w=w, h=hh, cells=len(still), g0=g0, rule=rule)


def main():
    found, counts = {}, dict.fromkeys(["fizzles", "no completion", "not restored", "output too close",
                                       "box too big", "duplicate"], 0)
    for cfg in sys.argv[1:]:
        harvest(cfg, found, counts)
    conv = sorted(found.values(), key=lambda o: (max(o["w"], o["h"]), o["w"] * o["h"], -o["dist"], o["cells"]))
    print("counts:", counts, "kept:", len(conv))
    allc, x, y, rowh = set(), 0, 0, 0
    for i, o in enumerate(conv):
        if i and i % 8 == 0:
            y, x, rowh = y + rowh + 10, 0, 0
        r0 = min(p[0] for p in o["g0"])
        c0 = min(p[1] for p in o["g0"])
        w = max(p[1] for p in o["g0"]) - c0 + 1
        allc |= {(p[0] - r0 + y, p[1] - c0 + x) for p in o["g0"]}
        rowh = max(rowh, max(p[0] for p in o["g0"]) - r0 + 1)
        x += w + 10
        print(f"{i + 1:3d}. row {i // 8 + 1} col {i % 8 + 1}: {o['w']}x{o['h']}, {o['cells']} cells, output dist "
              f"{o['dist']} (clean {o['clean']}) at gen {o['gen']}, back by gen {o['back']}   [{o['cfg']} #{o['n']}]")
        print("     " + "".join(L.to_rle(o["g0"], o["rule"]).split("\n")[1:]))
    if conv:
        lines = L.to_rle(allc, conv[0]["rule"]).split("\n")
        with open(OUT, "w") as f:
            f.write(lines[0] + "\n" + "".join(lines[1:]) + "\n")
        print(f"all {len(conv)} in one pattern: {OUT}")


if __name__ == "__main__":
    main()
