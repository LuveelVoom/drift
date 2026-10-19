#!/usr/bin/env python3
"""Input for "what can the q4i 2c/3 signal turn into?": a piece of the exactly
periodic diagonal 2c/3 wire (from wirebuild.py on signals.jsonl result #9330)
carrying its signal, ending in unknown space.

  * the wire heads down-right, (2,2) every 3 gens, period (4,4);
  * PERIODS wire periods are kept; the signal starts one period in;
  * the back end is left unknown (drift completes it), cells beside the wire
    are cleared (known dead), and everything past the front end is unknown.
Usage: make_feed.py RULEMAP [PERIODS] > feed.cfg   (writes feed.rle)"""
import json, os, sys
T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "drift", "tools")
sys.path.insert(0, T)
import wirebuild as wb
from driftlib import rule_table

table = rule_table(sys.argv[1])
PERIODS = int(sys.argv[2]) if len(sys.argv) > 2 else 6
res = next(r for r in map(json.loads, open("../signals.jsonl")) if r["n"] == 9330)
P, D, shapes = wb.measure(res, table)
S, unit = wb.solve(P, D, shapes, table, 5, 2)
g, _ = wb.check(P, D, shapes, S, unit, table)          # a long wire with a working signal
L = S[0] ** 2 + S[1] ** 2
proj = lambda p: p[0] * S[0] + p[1] * S[1]
wire_all = {(c[0] + n * S[0], c[1] + n * S[1]) for n in range(40) for c in unit}
sig = set(g) ^ wire_all                                   # the signal's cells
s0 = min(proj(p) for p in sig)
shift = -(s0 - L)                                          # put the signal one period from the back
lo, hi = s0 - L, s0 + (PERIODS - 1) * L                    # kept part of the wire, in proj units
wire = {p for p in wire_all if lo <= proj(p) < hi}
near = lambda p, d: any(abs(p[0] - q[0]) <= d and abs(p[1] - q[1]) <= d for q in wire)
rs = [r for r, c in wire]; cs = [c for r, c in wire]
r0, r1, c0, c1 = min(rs) - 4, max(rs) + 4, min(cs) - 4, max(cs) + 4
rows = []
for r in range(r0, r1 + 1):
    row = ""
    for c in range(c0, c1 + 1):
        p = (r, c)
        if p in sig: row += "D" if p in wire else "C"
        elif proj(p) < lo + L // 2: row += "."                   # back end: unknown
        elif proj(p) >= hi - 2: row += "."                       # past the front: unknown
        elif p in wire: row += "A"
        else: row += "B"                                         # beside the wire: empty
    rows.append(row.rstrip("."))
open("feed.rle", "w").write(f"x = {c1 - c0 + 1}, y = {r1 - r0 + 1}, rule = LifeHistory\n" + "$".join(rows) + "!\n")
print(f"""# The q4i diagonal 2c/3 wire ({PERIODS} periods) carrying its signal into
# unknown space: what can the signal be turned into?
rule = B3/S23-q4i
pattern = feed.rle
max-changed = 6
size = 4x4
margin = 60
max-gen = 200
skip = oscillator, fizzle, stable
per-rotor = 5
max-results = 3000
no-pics""")
