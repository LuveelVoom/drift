import sys, json
T = "/Users/leo/Desktop/Life tools/Vibecoded life tools/dr-attempt/drift/tools"
sys.path.insert(0, T)
from driftlib import rule_table, step, to_rle, complete
from mincomplete import min_complete
import wirebuild as wb
table = rule_table("B36/S23")
res = next(r for r in map(json.loads, open("hl-drift-results.jsonl")) if r["n"] == 35)
P, D, shapes = wb.measure(res, table)
for K in range(1, 5):
    sol = wb.solve(P, D, shapes, table, 5, K)
    if sol and sol[1]:
        break
S, unit = sol
N = int(sys.argv[1]) if len(sys.argv) > 1 else 6
wire = {(c[0] + n * S[0], c[1] + n * S[1]) for n in range(N + 4) for c in unit}
fixedlive = {(c[0] + n * S[0], c[1] + n * S[1]) for n in range(2, N + 2) for c in unit}
cells = {}
for (r, c) in fixedlive:
    for a in range(-2, 3):
        for b in range(-2, 3):
            p = (r + a, c + b)
            # fixed only if within the fixed periods (both neighbours in projection)
            cells[p] = 1 if p in wire else 2
# drop fixed cells near the two ends of the fixed stretch so the caps have room
proj = lambda p: p[0] * S[0] + p[1] * S[1]
lo = min(proj(p) for p in fixedlive) + 2 * (S[0]**2 + S[1]**2)
hi = max(proj(p) for p in fixedlive) - 2 * (S[0]**2 + S[1]**2)
cells = {p: v for p, v in cells.items() if lo <= proj(p) <= hi}
perp = lambda p: p[0] * S[1] - p[1] * S[0]
q0 = min(perp(p) for p in fixedlive); q1 = max(perp(p) for p in fixedlive)
L = S[0]**2 + S[1]**2
plo = min(proj(p) for p in fixedlive); phi = max(proj(p) for p in fixedlive)
X = int(sys.argv[2]) if len(sys.argv) > 2 else 2
bk = None
for extra in range(0, 4):
    W = X * 5 + extra * 5
    empty = lambda p: not (q0 - W <= perp(p) <= q1 + W and plo - L <= proj(p) <= phi + L)
    bk = min_complete(cells, table, 7, empty, 90)
    if bk: print("band extra", W); break
if bk is None:
    print("no cap"); sys.exit(1)
live = bk
print("stable:", step(live, table) == live, "cells", len(live))
open("stable.rle", "w").write(to_rle(live, "B36/S23"))
print(open("stable.rle").read())
# signal test: insert the signal at each nearby offset in the middle, watch it travel
mid = sorted(fixedlive, key=proj)[len(fixedlive) // 2]
shape0 = sorted(shapes[0])
for dr in range(-8, 9):
    for dc in range(-8, 9):
        sig = {(mid[0] + dr + r, mid[1] + dc + c) for r, c in shape0}
        h = live ^ sig
        ok = True
        for k in range(1, 3):
            for _ in range(P): h = step(h, table)
            want = {(r + k * D[0], c + k * D[1]) for r, c in sig}
            if (h ^ live) != want: ok = False; break
        if ok:
            for _ in range(400): h = step(h, table)
            print("signal travels; after it hits the end:", "wire restored" if h == live else
                  f"{len(h ^ live)} cells differ, still {'changing' if step(h, table) != h else 'stable'}")
            open("stable-with-signal.rle", "w").write(to_rle(live ^ sig, "B36/S23"))
            raise SystemExit
print("signal not found")
