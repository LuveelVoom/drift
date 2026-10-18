#!/usr/bin/env python3
"""Complete drift results into real patterns and check them.

drift's results are partial: only the background cells the search needed are
known. For each chosen result this fills in the unknown cells with a SAT
solver so that the background is a genuine still life (everything outside a
box around the result is dead), then simulates the finished pattern in the
rule and checks the claimed behaviour.

Needs python-sat (pip install python-sat).

Usage: tests/complete.py RESULTS.jsonl --rule MAP... [--n 1,5,7 | --first K] [--margins 3,6,10]
       tests/complete.py RESULTS.jsonl --rule MAP... --best OUT.txt   (one working pattern per rotor)
"""
import argparse
import base64
import json
import sys

from pysat.solvers import Cadical153

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from validate import parse_rle, rule_table  # noqa: E402
from minimize import minimize  # noqa: E402

WEIGHT = [256, 128, 64, 32, 16, 8, 4, 2, 1]
OFFS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 0), (0, 1), (1, -1), (1, 0), (1, 1)]


def complete(cells, table, margin, empty=None):
    """Returns {(r,c): 0/1} background, or None if no completion fits.
    empty(p): True for cells that must stay dead."""
    rs = [r for r, c in cells]
    cs = [c for r, c in cells]
    r0, r1, c0, c1 = min(rs) - margin, max(rs) + margin, min(cs) - margin, max(cs) + margin
    var = {}
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            var[(r, c)] = len(var) + 1
    s = Cadical153()
    if empty:
        for p, v in var.items():
            if empty(p) and cells.get(p) not in (1, 4):
                s.add_clause([-v])
    for p, st in cells.items():
        if st in (1, 4):
            s.add_clause([var[p]])
        elif st in (2, 3):
            s.add_clause([-var[p]])
    # Every cell in the box and the ring around it is stable (outside = dead).
    for r in range(r0 - 1, r1 + 2):
        for c in range(c0 - 1, c1 + 2):
            nb = [var.get((r + dr, c + dc)) for dr, dc in OFFS]
            for w in range(512):
                bits = [(w >> (8 - k)) & 1 for k in range(9)]
                if table[w] == bool(bits[4]):
                    continue   # this neighbourhood is stable
                clause, possible = [], True
                for v, b in zip(nb, bits):
                    if v is None:          # outside the box: dead
                        if b:
                            possible = False
                            break
                    else:
                        clause.append(-v if b else v)
                if possible:
                    s.add_clause(clause)
    if not s.solve():
        return None
    model = set(x for x in s.get_model() if x > 0)
    return {p: int(v in model) for p, v in var.items()}


def step(live, table):
    cand = {(r + dr, c + dc) for r, c in live for dr, dc in OFFS}
    out = set()
    for r, c in cand:
        w = sum(WEIGHT[k] for k, (dr, dc) in enumerate(OFFS) if (r + dr, c + dc) in live)
        if table[w]:
            out.add((r, c))
    return out


def to_rle(live, rule):
    if not live:
        return f"x = 0, y = 0, rule = {rule}\n!"
    rs = [r for r, c in live]
    cs = [c for r, c in live]
    lines = []
    for r in range(min(rs), max(rs) + 1):
        row = "".join("o" if (r, c) in live else "b" for c in range(min(cs), max(cs) + 1)).rstrip("b")
        lines.append(row)
    body = "$".join(lines)
    # simple run-length compression
    out, i = "", 0
    while i < len(body):
        j = i
        while j < len(body) and body[j] == body[i]:
            j += 1
        out += (str(j - i) if j - i > 1 else "") + body[i]
        i = j
    return f"x = {max(cs) - min(cs) + 1}, y = {max(rs) - min(rs) + 1}, rule = {rule}\n{out}!"


def check(res, table, margins, empty=None):
    """Complete one result. Returns (ok, history, population) or (False, None, 0)."""
    cells = parse_rle(res["lifehistory"])
    known = {p: s for p, s in cells.items() if s in (1, 2, 3, 4)}
    bk = None
    for m in margins:
        bk = complete(known, table, m, empty)
        if bk:
            break
    if not bk:
        return False, None, 0
    bg = {p for p, v in bk.items() if v}
    g0 = set(bg)
    for p, s in known.items():
        if s == 3:
            g0.add(p)
        elif s == 4:
            g0.discard(p)
    hist = [frozenset(g0)]
    for _ in range(res["gen"] + 3 * res.get("period", 1)):
        hist.append(frozenset(step(hist[-1], table)))
    if res["kind"] == "oscillator":
        p, g = res["period"], res["gen"]
        ok = all(hist[t] == hist[t - p] for t in range(g, len(hist))) and \
            not any(hist[g] == hist[g - d] for d in range(1, p))
    else:
        ok = res["kind"] == "fizzle" and hist[res["gen"]] == frozenset(bg)
    return ok, hist, len(hist[0])


def exposed(g0, period, table):
    """True if some rotor cell can be reached from outside the pattern without
    crossing a live stator cell (4-connected steps, so a diagonal chain of
    stator cells counts as a wall). False = billiard table."""
    phases = [frozenset(g0)]
    for _ in range(period - 1):
        phases.append(frozenset(step(phases[-1], table)))
    cells = set().union(*phases)
    stator = frozenset.intersection(*phases)
    rotor = cells - stator
    rs = [r for r, c in cells]
    cs = [c for r, c in cells]
    r0, r1, c0, c1 = min(rs) - 1, max(rs) + 1, min(cs) - 1, max(cs) + 1
    seen = {(r0, c0)}
    todo = [(r0, c0)]
    while todo:
        r, c = todo.pop()
        if (r, c) in rotor:
            return True
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (r + dr, c + dc)
            if r0 <= q[0] <= r1 and c0 <= q[1] <= c1 and q not in seen and q not in stator:
                seen.add(q)
                todo.append(q)
    return False


def parse_regions(specs):
    regs = []
    for s in specs or []:
        r0, c0, r1, c1 = map(int, s.replace(",", " ").split())
        regs.append((min(r0, r1), min(c0, c1), max(r0, r1), max(c0, c1)))
    return regs


def empty_pred(regs, res):
    """Cells (in the result's RLE coordinates) inside a --keep-empty region."""
    if not regs:
        return None
    orr, occ = res.get("origin", (0, 0))
    return lambda p: any(r0 <= p[0] + orr <= r1 and c0 <= p[1] + occ <= c1 for r0, c0, r1, c1 in regs)


def sparks(g0, period, table, empty):
    """Rotor cells inside the empty regions, and how far the furthest one is
    from the nearest live stator cell (1 = next to the object)."""
    phases = [frozenset(g0)]
    for _ in range(period - 1):
        phases.append(frozenset(step(phases[-1], table)))
    stator = frozenset.intersection(*phases)
    rotor = set().union(*phases) - stator
    sp = [p for p in rotor if empty(p)]
    depth = max((min(max(abs(p[0] - q[0]), abs(p[1] - q[1])) for q in stator) for p in sp), default=0)
    return len(sp), depth


def best(a, table):
    groups = {}
    for line in open(a.jsonl):
        try:
            res = json.loads(line)
        except ValueError:
            continue
        if res["kind"] != "oscillator":
            continue
        groups.setdefault(res["rotor"], []).append(res)
    margins = list(map(int, a.margins.split(",")))
    regs = parse_regions(a.keep_empty)
    found, failed = [], 0
    for rotor, cands in groups.items():
        cands.sort(key=lambda r: r["gen"])          # short transients first
        for res in cands[:a.tries]:
            empty = empty_pred(regs, res)
            ok, hist, pop = check(res, table, margins, empty)
            if ok:
                g0 = hist[res["gen"]]   # a phase of the oscillator itself (gen 0 still has the spark)
                pop = len(g0)
                if a.minimize:
                    p, g = res["period"], res["gen"]
                    m = minimize(hist[g - p:g], table, True, margin=a.min_margin, seconds=a.min_seconds,
                                 empty=empty)
                    if m and m[1] < pop:
                        h = [frozenset(m[0])]   # re-check the minimised pattern
                        for _ in range(2 * p):
                            h.append(frozenset(step(h[-1], table)))
                        if h[p] == h[0] and h[2 * p] == h[p] and not any(h[d] == h[0] for d in range(1, p)):
                            g0, pop = m
                if a.no_billiards and not exposed(g0, res["period"], table):
                    continue   # try another stator for the same rotor
                sp = sparks(g0, res["period"], table, empty) if empty else (0, 0)
                if a.sparky and not sp[0]:
                    continue   # the spark was only in the transient
                found.append((res["period"], pop, rotor, res, g0, sp))
                break
        else:
            failed += 1
    found.sort(key=lambda f: (-f[5][1], -f[0], f[1]) if a.sparky else (-f[0], f[1]))
    with open(a.best, "w") as out:
        for per, pop, rotor, res, g0, sp in found:
            name = f"  (Life rotor: {res['name']})" if res.get("known") else ""
            kind = "exposed rotor" if exposed(g0, per, table) else "billiard table"
            spark = f"  spark: {sp[0]} cells, depth {sp[1]}" if regs else ""
            out.write(f"p{per}  {pop} cells  {kind}{spark}  rotor {rotor}{name}\n")
            out.write(to_rle(g0, a.name or res["rule"]) + "\n\n")
    by = {}
    for f in found:
        by[f[0]] = by.get(f[0], 0) + 1
    print(f"{len(groups)} distinct rotors: {len(found)} completed into working oscillators, "
          f"{failed} not completed. By period: " + ", ".join(f"p{k}: {v}" for k, v in sorted(by.items())))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--rule", required=True, help="MAP form of the rule (drift --show-rule)")
    ap.add_argument("--name", help="rule name to put in the RLE (default: the result's rule)")
    ap.add_argument("--n", help="result numbers, comma separated")
    ap.add_argument("--first", type=int, default=5)
    ap.add_argument("--margins", default="3,6,10")
    ap.add_argument("--best", metavar="OUT", help="complete every rotor, keep one working pattern each")
    ap.add_argument("--tries", type=int, default=8, help="with --best: candidates tried per rotor")
    ap.add_argument("--minimize", action="store_true", help="with --best: shrink each stator (SAT)")
    ap.add_argument("--keep-empty", action="append", metavar="R0,C0,R1,C1",
                    help="pattern-relative rectangle that must stay empty (repeatable)")
    ap.add_argument("--sparky", action="store_true",
                    help="with --best and --keep-empty: keep oscillators whose own cycle puts live "
                         "cells into the empty area; sorted by how far the spark sticks out")
    ap.add_argument("--no-billiards", action="store_true",
                    help="with --best: drop billiard tables (rotor walled in by the stator)")
    ap.add_argument("--min-margin", type=int, default=4, help="stator box margin around the rotor")
    ap.add_argument("--min-seconds", type=float, default=20, help="time limit per oscillator")
    a = ap.parse_args()
    table = rule_table(a.rule)
    if a.best:
        return best(a, table)
    want = set(int(x) for x in a.n.split(",")) if a.n else None
    done = 0
    for line in open(a.jsonl):
        try:
            res = json.loads(line)
        except ValueError:
            continue
        if want is not None and res["n"] not in want:
            continue
        if want is None and done >= a.first:
            break
        done += 1
        cells = parse_rle(res["lifehistory"])
        known = {p: s for p, s in cells.items() if s in (1, 2, 3, 4)}
        bk = None
        for m in map(int, a.margins.split(",")):
            bk = complete(known, table, m)
            if bk:
                break
        head = f"#{res['n']} {res['kind']} p{res.get('period', '')} from gen {res['gen'] - res.get('period', 0)}"
        if not bk:
            print(f"{head}: NO still-life completion within margin {a.margins.split(',')[-1]}")
            continue
        bg = {p for p, v in bk.items() if v}
        g0 = set(bg)
        for p, s in known.items():
            if s == 3:
                g0.add(p)
            elif s == 4:
                g0.discard(p)
        # Check: background stable, and the claimed outcome happens.
        stable = step(bg, table) == bg
        hist = [frozenset(g0)]
        for _ in range(res["gen"] + 3 * res.get("period", 1)):
            hist.append(frozenset(step(hist[-1], table)))
        verdict = "?"
        if res["kind"] == "oscillator":
            p, g = res["period"], res["gen"]
            ok = all(hist[t] == hist[t - p] for t in range(g, len(hist)))
            exact = not any(hist[g] == hist[g - d] for d in range(1, p))
            verdict = f"WORKS: p{p} oscillator" if ok and exact else "does NOT oscillate as claimed"
        elif res["kind"] == "fizzle":
            verdict = "WORKS: returns to the background" if hist[res["gen"]] == frozenset(bg) else "does NOT fizzle"
        print(f"{head}: background {'stable' if stable else 'UNSTABLE'}, {verdict}")
        print(to_rle(hist[0], a.name or res["rule"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
