#!/usr/bin/env python3
"""Turn a travelling signal into a true, exactly periodic wire.

drift's "max gen" results carry a signal along a track it improvised, which is
usually only roughly periodic. This:

1. completes the result's background, runs it, and measures the signal: it
   repeats every P generations, moved by D;
2. asks a SAT solver for a background that repeats exactly with shift K*D and
   carries the same signal. It works on a cylinder: cells that differ by K*D
   are identified. Every cylinder cell has one background value; in each phase
   the signal is the set of cells that differ from the background (the
   measured shape). Constraints: every phase steps to the next (the last phase
   steps to the first, moved by D); the background alone is a still life;
   cells further than WIDTH from the signal's path are dead;
3. tiles that background into a long wire, puts one signal on it and
   simulates, checking the signal keeps its shape and speed across the wire.

Usage: wirebuild.py RESULTS.jsonl --rule MAP --n N [--width 5] [--kmax 4] [--out wire.rle]
"""
import argparse
import json
import os
import sys

from pysat.solvers import Cadical153

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate import parse_rle, rule_table  # noqa: E402
from complete import complete, step  # noqa: E402

OFFS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 0), (0, 1), (1, -1), (1, 0), (1, 1)]
WEIGHT = [256, 128, 64, 32, 16, 8, 4, 2, 1]


def measure(res, table, gens=160):
    """Complete the background and find the signal: (P, D, shapes) or None.
    shapes[t] = cells differing from the background at phase t, relative to
    phase 0's first cell."""
    cells = parse_rle(res["lifehistory"])
    known = {p: s for p, s in cells.items() if s in (1, 2, 3, 4)}
    bk = None
    for m in (3, 6):
        bk = complete(known, table, m)
        if bk:
            break
    if not bk:
        return None
    bg = frozenset(p for p, v in bk.items() if v)
    g = set(bg)
    for p, s in known.items():
        if s == 3:
            g.add(p)
        elif s == 4:
            g.discard(p)
    h = [frozenset(g)]
    for _ in range(gens):
        h.append(frozenset(step(h[-1], table)))
    ch = [sorted(h[t] ^ bg) for t in range(len(h))]
    for P in range(1, 40):
        for t0 in range(20, 60):
            a, b = ch[t0], ch[t0 + P]
            if not a or len(a) != len(b):
                continue
            d = (b[0][0] - a[0][0], b[0][1] - a[0][1])
            if d != (0, 0) and all((q[0] - p[0], q[1] - p[1]) == d for p, q in zip(a, b)) \
                    and all((p in h[t0]) == (q in h[t0 + P]) for p, q in zip(a, b)):
                o = ch[t0][0]
                shapes = [frozenset((r - o[0], c - o[1]) for r, c in ch[t0 + t]) for t in range(P)]
                return P, d, shapes
    return None


def solve(P, D, shapes, table, width, K):
    S = (D[0] * K, D[1] * K)                      # wire period
    L = S[0] ** 2 + S[1] ** 2
    proj = lambda p: p[0] * S[0] + p[1] * S[1]
    perp = lambda p: p[0] * S[1] - p[1] * S[0]

    def canon(p):
        n = proj(p) // L
        return (p[0] - n * S[0], p[1] - n * S[1])

    T = P * K                                     # phases until the signal is back where it was
    sig = []                                      # signal cells (canonical) at each phase
    for t in range(T):
        k, ph = divmod(t, P)
        sig.append({canon((r + k * D[0], c + k * D[1])) for r, c in shapes[ph]})
    allsig = set().union(*sig)
    W = width * max(abs(S[0]), abs(S[1]), 1) * 2
    lo = min(perp(c) for c in allsig) - W
    hi = max(perp(c) for c in allsig) + W
    var = {}

    def b(c):                                     # background variable, or 0 outside the band
        c = canon(c)
        if not lo <= perp(c) <= hi:
            return 0
        if c not in var:
            var[c] = len(var) + 2
        return var[c]

    # cells of one period, plus a 2-cell ring outside the band (which must stay dead)
    ring = 2 * (abs(S[0]) + abs(S[1]))
    rs = [c[0] for c in allsig]
    cs = [c[1] for c in allsig]
    span = abs(S[0]) + abs(S[1]) + W + 3
    cells = {(r, c) for r in range(min(rs) - span, max(rs) + span + 1)
             for c in range(min(cs) - span, max(cs) + span + 1)
             if canon((r, c)) == (r, c) and lo - ring <= perp((r, c)) <= hi + ring}
    clauses = []

    def constrain(win, flips_in, target, flip_out):
        """Forbid assignments where rule(win) != target. Each entry is (var or 0,
        flipped?) meaning value = var XOR flipped."""
        vs = sorted({v for v, _ in win + [(target, flip_out)] if v})
        for a in range(1 << len(vs)):
            asg = {v: (a >> i) & 1 for i, v in enumerate(vs)}
            val = lambda v, f: (asg[v] if v else 0) ^ f
            w = sum(WEIGHT[i] for i, (v, f) in enumerate(win) if val(v, f))
            if int(table[w]) != val(target, flip_out):
                if not vs:
                    return False
                clauses.append([-v if asg[v] else v for v in vs])
        return True

    for x in cells:
        # the background alone is a still life
        if not constrain([(b((x[0] + dr, x[1] + dc)), 0) for dr, dc in OFFS], None, b(x), 0):
            return None
        for t in range(T):
            win = [(b(q), int(canon(q) in sig[t])) for q in ((x[0] + dr, x[1] + dc) for dr, dc in OFFS)]
            if not constrain(win, None, b(x), int(canon(x) in sig[(t + 1) % T])):
                return None
    s = Cadical153(bootstrap_with=clauses)
    if not s.solve():
        return None
    model = set(x for x in s.get_model() if x > 0)
    return S, {c for c, v in var.items() if v in model}


def check(P, D, shapes, S, unit, table, periods=40, travel=8):
    """Tile the background into a long wire, add one signal a quarter of the
    way along and simulate for `travel` wire periods. Only the area around the
    signal's expected position is compared (the cut wire ends decay inwards)."""
    L = S[0] ** 2 + S[1] ** 2
    proj = lambda p: p[0] * S[0] + p[1] * S[1]
    wire = frozenset((c[0] + n * S[0], c[1] + n * S[1]) for n in range(periods) for c in unit)
    K = round((S[0] * D[0] + S[1] * D[1]) / (D[0] ** 2 + D[1] ** 2))   # signal steps per wire period
    steps = travel * K * P
    shape0 = sorted(shapes[0])
    base = (periods // 4) * S[0], (periods // 4) * S[1]
    for dr in range(-abs(S[0]) - 2, abs(S[0]) + 3):        # try placements of the signal
        for dc in range(-abs(S[1]) - 2, abs(S[1]) + 3):
            o = (base[0] + dr, base[1] + dc)
            sig0 = {(o[0] + r, o[1] + c) for r, c in shape0}
            h = frozenset(set(wire) ^ sig0)
            ok = True
            for t in range(1, steps + 1):
                h = frozenset(step(h, table))
                if t % P == 0:
                    k = t // P
                    want = {(r + k * D[0], c + k * D[1]) for r, c in sig0}
                    mid = sum(proj(p) for p in want) / len(want)
                    near = {p for p in h ^ wire if abs(proj(p) - mid) <= 3 * L}
                    if near != want:
                        ok = False
                        break
            if ok:
                return set(wire) ^ sig0, travel
    return None, 0


def rle(cells, rule):
    rs = [r for r, c in cells]
    cs = [c for r, c in cells]
    rows = ["".join("o" if (r, c) in cells else "b" for c in range(min(cs), max(cs) + 1)).rstrip("b")
            for r in range(min(rs), max(rs) + 1)]
    body, out, i = "$".join(rows), "", 0
    while i < len(body):
        j = i
        while j < len(body) and body[j] == body[i]:
            j += 1
        out += (str(j - i) if j - i > 1 else "") + body[i]
        i = j
    return f"x = {max(cs) - min(cs) + 1}, y = {max(rs) - min(rs) + 1}, rule = {rule}\n{out}!\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--rule", required=True)
    ap.add_argument("--name", default="")
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--width", type=int, default=5)
    ap.add_argument("--kmax", type=int, default=4)
    ap.add_argument("--out")
    a = ap.parse_args()
    table = rule_table(a.rule)
    res = next(r for r in map(json.loads, open(a.jsonl)) if r["n"] == a.n)
    m = measure(res, table)
    if not m:
        print(f"#{a.n}: no clean periodic signal")
        return 1
    P, D, shapes = m
    print(f"#{a.n}: signal repeats every {P} gens moving {D}")
    for K in range(1, a.kmax + 1):
        sol = solve(P, D, shapes, table, a.width, K)
        if not sol:
            print(f"  wire period {K}x{D}: no background")
            continue
        S, unit = sol
        if not unit:
            print(f"  wire period {S}: only an empty background fits")
            continue
        g, periods = check(P, D, shapes, S, unit, table)
        if g:
            print(f"  wire period {S}: background found ({len(unit)} live cells per period); "
                  f"a single signal crosses {periods} wire periods of a tiled wire")
            if a.out:
                open(a.out, "w").write(rle(g, a.name or res["rule"]))
                print(f"  wrote {a.out}")
            return 0
        print(f"  wire period {S}: background found, but a single signal doesn't travel on it")
    return 1


if __name__ == "__main__":
    sys.exit(main())
