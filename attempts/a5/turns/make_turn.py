#!/usr/bin/env python3
"""Write a turn-search config for the diagonal 5c/11 wire in wire-5c11.rle.

Coordinates: u = col - row grows along the wire (the signal moves +20 in u
per 22 gens), v = row + col runs across it (the wire spans v 27..51).

The input is the wire from u = UB to UE (known cells: live wire cells, dead
cells in the band) carrying the signal in its one-cell phase (a dead wire
cell at (15,23), u = 8). Past the cut there is an unknown turn zone UE < u <=
UE+T; beyond that everything is cleared, so the signal can't carry on
straight. The new signal has to reach v <= 24-REACH (left turn, up-left) or
v >= 54+REACH (right turn, down-right).

Usage: make_turn.py left|right [T] [REACH] > turn.cfg   (writes turn-input.rle)"""
import sys
side = sys.argv[1]
T = int(sys.argv[2]) if len(sys.argv) > 2 else 16
REACH = int(sys.argv[3]) if len(sys.argv) > 3 else 12
UB, UE, VLO, VHI = -22, 28, 25, 53

# --- the input pattern (rows/cols as in wire-5c11.rle)
cells = set()
lines = [l for l in open("wire-5c11.rle").read().split("\n")[1:] if l]
r = c = 0
run = ""
for ch in "".join(lines):
    if ch.isdigit():
        run += ch
        continue
    n = int(run) if run else 1
    run = ""
    if ch == "$": r += n; c = 0
    elif ch == "b": c += n
    elif ch == "o":
        for _ in range(n): cells.add((r, c)); c += 1
    elif ch == "!": break
rows = []
for rr in range(0, 40):
    row = ""
    for cc in range(0, 45):
        u, v = cc - rr, rr + cc
        if (rr, cc) == (15, 23): row += "D"       # the signal: wire cell dead in gen 0
        elif UB <= u <= UE and VLO <= v <= VHI: row += "A" if (rr, cc) in cells else "B"
        else: row += "."
    rows.append(row.rstrip("."))
with open("turn-input.rle", "w") as f:
    f.write("x = 45, y = 40, rule = LifeHistory\n" + "$".join(rows) + "!\n")

# --- regions (triangles; L = far away)
L = 300
def even(a, b):   # make a - b even so corners land on cells
    return a if (a - b) % 2 == 0 else a + 1
def corner(v, u):
    return (v - u) // 2, (v + u) // 2
def tri(*pts):
    return "t " + " ".join(f"{a} {b}" for a, b in pts)
k = even(VLO - 1, UE); r0, c0 = corner(k, UE)        # v <= VLO-1, u <= UE
side_lo = tri((r0, c0), (r0 + L, c0 - L), (r0 - L, c0 - L))
k = even(VHI + 1, UE); r1, c1 = corner(k, UE)        # v >= VHI+1, u <= UE
side_hi = tri((r1, c1), (r1 + L, c1 - L), (r1 + L, c1 + L))
m = UE + T + 1                                       # u >= m: straight ahead blocked
ahead = tri((-L, m - L), (L, m + L), (-L, L + m + L))
if side == "left":                                   # v <= k
    k = VLO - 1 - REACH
    reach = tri((-L, k + L), (L, k - L), (-L, k - L))
    push = "up c/4 6"
else:                                                # v >= k
    k = VHI + 1 + REACH
    reach = tri((-L, k + L), (L, k - L), (L, k + L))
    push = "right c/4 6"
print(f"""# Turn search ({side}) for the diagonal 5c/11 wire. Input: turn-input.rle.
rule = B3/S23-a5
pattern = turn-input.rle
max-changed = 10
size = 6x6
margin = 40
max-gen = 150
push = {push}
clear = {side_lo}
clear = {side_hi}
clear = {ahead}
must-reach = {reach}
skip = oscillator, stable
per-rotor = 5
max-results = 2000
no-pics""")
