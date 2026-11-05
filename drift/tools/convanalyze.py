#!/usr/bin/env python3
"""Describe and chain-test spark converters.

usage: python3 tools/convanalyze.py RULE PATTERN.rle [--chain] [--json OUT.jsonl]   (needs numpy; put in drift/tools/)

PATTERN holds converters (still life + input spark) at least 5 cells apart,
e.g. the combined RLE written by sparkconv.py. For each one:
  still   = the state once the reaction is over (checked to be a still life)
  input   = gen-0 cells not in the still life
  outputs = clusters of cells alive outside the still life (in the dead region
            4-connected to the outside) at Chebyshev distance >= 2 from the input,
            grouped over all generations (cells <= 2 apart)
Per output:
  dist   largest distance from the input
  depth  smallest distance from the still life (1 = touching it; 2+ = a free spark)
  side   which side of the still life's box it is on, relative to the input's side:
         same / turn (90 degrees) / opposite
  route  "through" if the output's activity isn't connected (outside the still
         life, over all gens) to the activity around the input: the signal
         went through the catalyst; "along" if it crawled round the outside
--chain: for every ordered pair (X, Y), every output cell p of X, every
orientation of Y with Y's input spark on cells alive at p's generation:
place Y's still life, simulate, and report placements where both still lifes
come back and Y's own output appears. Also reports placements that end up
periodic (a loop: an oscillator built from the two).
"""
import json
import sys

import numpy as np

sys.path.insert(0, __import__("os").environ.get("DRIFT_TOOLS", __import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import driftlib as L  # noqa: E402

TR = [lambda r, c: (r, c), lambda r, c: (r, -c), lambda r, c: (-r, c), lambda r, c: (-r, -c),
      lambda r, c: (c, r), lambda r, c: (c, -r), lambda r, c: (-c, r), lambda r, c: (-c, -r)]


class Fast:
    """numpy stepper on a fixed box (cells leaving it are an error)."""
    def __init__(self, table):
        self.t = np.array([bool(x) for x in table], dtype=bool)

    def run(self, cells, gens, pad=12):
        rs = [r for r, c in cells]
        cs = [c for r, c in cells]
        r0, c0 = min(rs) - pad, min(cs) - pad
        H, W = max(rs) - r0 + pad + 1, max(cs) - c0 + pad + 1
        g = np.zeros((H, W), dtype=np.int16)
        for r, c in cells:
            g[r - r0, c - c0] = 1
        out = [g.copy()]
        for _ in range(gens):
            p = np.pad(g, 1)
            idx = (p[:-2, :-2] * 256 + p[:-2, 1:-1] * 128 + p[:-2, 2:] * 64 + p[1:-1, :-2] * 32 +
                   p[1:-1, 1:-1] * 16 + p[1:-1, 2:] * 8 + p[2:, :-2] * 4 + p[2:, 1:-1] * 2 + p[2:, 2:])
            g = self.t[idx].astype(np.int16)
            if g[0].any() or g[-1].any() or g[:, 0].any() or g[:, -1].any():
                out.append(None)
                return out, (r0, c0)
            out.append(g.copy())
        return out, (r0, c0)


def cells_of(g, off):
    rr, cc = np.nonzero(g)
    return frozenset(zip((rr + off[0]).tolist(), (cc + off[1]).tolist()))


def cheb(p, qs):
    return min(max(abs(p[0] - a), abs(p[1] - b)) for a, b in qs)


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


def side_of(p, bx):
    r0, r1, c0, c1 = bx
    d = {"N": r0 - p[0], "S": p[0] - r1, "W": c0 - p[1], "E": p[1] - c1}
    return max(d, key=d.get)


REL = {("N", "N"): "same", ("N", "S"): "opposite", ("S", "S"): "same", ("S", "N"): "opposite",
       ("E", "E"): "same", ("E", "W"): "opposite", ("W", "W"): "same", ("W", "E"): "opposite"}


class Conv:
    def __init__(self, g0, fast, gens=60):
        self.g0 = frozenset(g0)
        hist, off = fast.run(self.g0, gens)
        if hist[-1] is None:
            raise ValueError("escapes")
        self.hist = [cells_of(g, off) for g in hist]
        self.still = self.hist[-1]
        if self.hist[-2] != self.still:
            raise ValueError("doesn't settle")
        self.inp = self.g0 - self.still
        self.back = max(t for t in range(len(self.hist)) if self.hist[t] != self.still) + 1
        self.hist = self.hist[:self.back + 1]
        rs = [r for r, c in self.still]
        cs = [c for r, c in self.still]
        self.box = (min(rs), max(rs), min(cs), max(cs))
        self.ext = exterior(self.still)
        self.analyse()

    def analyse(self):
        act = {}   # exterior alive cell -> first gen
        for t in range(1, len(self.hist)):
            for p in self.hist[t] - self.still:
                if p in self.ext and p not in act:
                    act[p] = t
        allact = set(act) | set(self.inp)
        reach = set()   # exterior activity 8-connected to the input
        todo = list(self.inp)
        reach |= set(todo)
        while todo:
            r, c = todo.pop()
            for a in (-1, 0, 1):
                for b in (-1, 0, 1):
                    q = (r + a, c + b)
                    if q in allact and q not in reach:
                        reach.add(q)
                        todo.append(q)
        far = {p: t for p, t in act.items() if cheb(p, self.inp) >= 2}
        insides = side_of(next(iter(self.inp)), self.box)
        self.inside = insides
        self.outs = []
        for comp in L.components(far, 2):
            cells = sorted(comp, key=lambda p: (far[p], p))
            dist = max(cheb(p, self.inp) for p in comp)
            depth = max(cheb(p, self.still) for p in comp)
            far_cell = max(comp, key=lambda p: (cheb(p, self.inp), -far[p]))
            sd = side_of(far_cell, self.box)
            rel = REL.get((insides, sd), "turn")
            route = "along" if any(p in reach for p in comp) else "through"
            self.outs.append(dict(cells=cells, gens=sorted({far[p] for p in comp}), first=far[cells[0]],
                                  dist=dist, depth=depth, side=sd, rel=rel, route=route, n=len(comp)))
        self.outs.sort(key=lambda o: -o["dist"])

    def summary(self):
        w, h = self.box[3] - self.box[2] + 1, self.box[1] - self.box[0] + 1
        s = f"{w}x{h}, {len(self.still)} cells, input {len(self.inp)} cell(s) on {self.inside}, back by gen {self.back}"
        parts = []
        for o in self.outs:
            parts.append(f"[{o['rel']} side ({o['side']}), {o['route']}, dist {o['dist']}, depth {o['depth']}, "
                         f"gens {o['first']}-{o['gens'][-1]}, {o['n']} cells]")
        sites = [o for o in self.outs if o["dist"] >= 2]
        tags = []
        if any(o["route"] == "through" for o in sites):
            tags.append("THROUGH")
        if any(min(max(abs(a[0] - b[0]), abs(a[1] - b[1])) for a in o1["cells"] for b in o2["cells"]) >= 3
               for i1, o1 in enumerate(sites) for o2 in sites[i1 + 1:]):
            tags.append("SPLITTER")
        if self.back >= 10:
            tags.append("LONG")
        if any(o["depth"] >= 2 for o in sites):
            tags.append("FREE-SPARK")
        if any(o["rel"] == "opposite" for o in sites):
            tags.append("OPPOSITE-SIDE")
        if any(o["rel"] == "turn" for o in sites):
            tags.append("TURN")
        return s, parts, tags


def split(cells, gap=5):
    return [frozenset(c) for c in L.components(cells, gap)]


def norm(cells):
    r0 = min(r for r, c in cells)
    c0 = min(c for r, c in cells)
    return frozenset((r - r0, c - c0) for r, c in cells)


def chain(convs, fast, out_tests=3):
    """X's output -> Y's input placements that work."""
    found = []
    for xi, X in enumerate(convs):
        cand = []
        for o in X.outs:
            for p in o["cells"]:
                t = min(t for t in range(1, len(X.hist)) if p in X.hist[t])
                cand.append((t, p))
        for yi, Y in enumerate(convs):
            for ti, tf in enumerate(TR):
                yin = [tf(*q) for q in Y.inp]
                ystill = [tf(*q) for q in Y.still]
                anchor = yin[0]
                done = set()
                for t, p in cand:
                    alive = X.hist[t]
                    for a in yin:   # put spark cell a on p
                        dr, dc = p[0] - a[0], p[1] - a[1]
                        sp = {(r + dr, c + dc) for r, c in yin}
                        if not sp <= alive:
                            continue
                        ys = frozenset((r + dr, c + dc) for r, c in ystill)
                        key = (dr, dc)
                        if key in done:
                            continue
                        done.add(key)
                        if ys & X.still:
                            continue
                        both = X.still | ys
                        if frozenset(L.step(both, fast_table)) != both:
                            continue
                        yout = {(r + dr, c + dc) for o in Y.outs if o["dist"] == Y.outs[0]["dist"]
                                for r, c in (tf(*q) for q in o["cells"])}
                        hist, off = fast.run(X.g0 | ys, 300)
                        if hist[-1] is None:
                            continue
                        H = [cells_of(g, off) for g in hist]
                        if H[-1] == both and H[-2] == both:
                            if any(H[u] & yout for u in range(t, len(H))):
                                found.append(dict(x=xi, y=yi, orient=ti, shift=(dr, dc), kind="chain",
                                                  g0=X.g0 | ys))
                            continue
                        for per in range(2, 150):   # a loop: periodic, both still lifes nearly all stator
                            if H[-1] == H[-1 - per] and H[-2] == H[-2 - per]:
                                stator = frozenset.intersection(*H[-1 - per:-1])
                                if len(stator & both) >= 0.8 * len(both):
                                    found.append(dict(x=xi, y=yi, orient=ti, shift=(dr, dc),
                                                      kind=f"periodic p{per}", g0=X.g0 | ys))
                                break
    return found


def main():
    global fast_table
    rule, path = sys.argv[1], sys.argv[2]
    table = L.rule_for(rule)
    fast_table = table
    fast = Fast(table)
    cells = frozenset(L.parse_rle(open(path).read()))
    convs = []
    for comp in sorted(split(cells), key=lambda c: (min(r for r, _ in c), min(cc for _, cc in c))):
        try:
            convs.append(Conv(comp, fast))
        except ValueError as e:
            print("skipped a component:", e)
    for i, X in enumerate(convs):
        s, parts, tags = X.summary()
        print(f"{i + 1:3d}. {s}  {' '.join(tags)}")
        for p in parts:
            print("       " + p)
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w") as f:
            for i, X in enumerate(convs):
                s, parts, tags = X.summary()
                f.write(json.dumps(dict(i=i + 1, g0=sorted(X.g0), tags=tags, summary=s, outs=parts)) + "\n")
    if "--chain" in sys.argv:
        res = chain(convs, fast)
        seen = set()
        for r in res:
            k = (r["x"], r["y"], r["kind"], norm(r["g0"]))
            if k in seen:
                continue
            seen.add(k)
            print(f"chain {r['x'] + 1} -> {r['y'] + 1} ({r['kind']}): {''.join(L.to_rle(r['g0'], rule).split(chr(10))[1:])}")


if __name__ == "__main__":
    main()
