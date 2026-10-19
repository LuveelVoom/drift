#!/usr/bin/env python3
"""Connector searches for either B3/S23-a5 wire: turns and 180-degree reflectors.

Both wires are given and only the gap between them is unknown:
  * the incoming wire, cut after its signal;
  * a copy of the wire (end cap included) turned right, left, or 180 degrees
    (reflect-right / reflect-left: lying beside the incoming wire on that side,
    heading back), its open end at Q = E + A*heading + B*side;
  * an unknown connector zone around E..Q; everything else known.
Success = a fizzle (the signal is absorbed by the outgoing wire's end cap) that
changes cells deep inside the outgoing wire (--must-reach).

Usage: make_connector2.py WIRE MODE A B [MAXCHANGED SIZE] > conn.cfg
  WIRE: 2c3 (wire2.rle) or 5c11 (../turns/wire-5c11.rle)
  MODE: right, left, reflect-right, reflect-left, straight"""
import sys

WIRES = {
    # heading, axis offset (across coordinate of the wire's centre line),
    # signal cells (state 3 = on in gen 0 only, 4 = off), kept from along >= start,
    # incoming cut at along = end, outgoing piece from along >= piece
    "2c3": dict(file="wire2.rle", H=(1, 1), axis=0, signal={(36, 35): "C", (36, 36): "D"},
                start=50, end=94, piece=60),
    "5c11": dict(file="../turns/wire-5c11.rle", H=(-1, 1), axis=39, signal={(15, 23): "D"},
                 start=-22, end=19, piece=-15),   # periodic part: along -16..20
}
wname, mode, A, B = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
C = int(sys.argv[5]) if len(sys.argv) > 5 else 12
SIZE = sys.argv[6] if len(sys.argv) > 6 else "8x8"
W = dict(WIRES[wname])
import os
if os.environ.get("END"): W["end"] = int(os.environ["END"])        # testing: where the incoming wire is cut
ZONE = int(os.environ.get("ZONE", 7))
H = W["H"]
HR = (H[1], -H[0])        # heading turned right (clockwise on screen)
HL = (-H[1], H[0])        # heading turned left
along = lambda p: H[0] * p[0] + H[1] * p[1]


def parse(path):
    cells, r, c, run = set(), 0, 0, ""
    for ch in "".join(open(path).read().split("\n")[1:]):
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
    return cells


def axis_point(L):   # cell on the centre line at along = L
    X = W["axis"]
    return ((L * H[0] + X * HR[0]) // 2, (L * H[1] + X * HR[1]) // 2)


wire = {p for p in parse(W["file"]) if along(p) >= W["start"]}
incoming = {p for p in wire if along(p) <= W["end"]}
E = axis_point(W["end"])
rot = {"straight": lambda p: p,
       "right": lambda p: (p[1], -p[0]),        # clockwise
       "left": lambda p: (-p[1], p[0]),         # anticlockwise
       "reflect-right": lambda p: (-p[0], -p[1]),
       "reflect-left": lambda p: (-p[0], -p[1])}[mode]
side = HL if mode in ("left", "reflect-left") else HR
Q = (E[0] + A * H[0] + B * side[0], E[1] + A * H[1] + B * side[1])
src = {p for p in wire if along(p) >= W["piece"]}
ref = rot(axis_point(W["piece"]))
outgoing = {(r - ref[0] + Q[0], c - ref[1] + Q[1]) for r, c in map(rot, src)}


def near(p, s, d):
    return any(abs(p[0] - q[0]) <= d and abs(p[1] - q[1]) <= d for q in s)


if incoming & outgoing or any(near(p, incoming, 1) for p in outgoing):
    sys.exit("the two wires touch for these A, B")
live = incoming | outgoing
seg = [(E[0] + round(t * (Q[0] - E[0]) / 20), E[1] + round(t * (Q[1] - E[1]) / 20)) for t in range(21)]
rs = [r for r, c in live]
cs = [c for r, c in live]
r0, r1, c0, c1 = min(rs) - 3, max(rs) + 3, min(cs) - 3, max(cs) + 3
rows = []
for r in range(r0, r1 + 1):
    row = ""
    for c in range(c0, c1 + 1):
        p = (r, c)
        if p in W["signal"]: row += W["signal"][p]
        elif p in live: row += "A"
        elif any(abs(r - q[0]) <= ZONE and abs(c - q[1]) <= ZONE for q in seg): row += "."   # connector
        elif along(p) <= W["start"] + 6 and near(p, incoming, 3): row += "."   # behind the cut
        else: row += "B"
    rows.append(row)
name = f"conn-{wname}-{mode}-{A}-{B}.rle"
with open(name, "w") as f:
    f.write(f"x = {c1 - c0 + 1}, y = {r1 - r0 + 1}, rule = LifeHistory\n" + "$".join(rows) + "!\n")
# must reach: small boxes on the outgoing wire's centre line, far from its open end
pts = []
lo = W["piece"] + 30
hi = max(along(p) for p in src) - 6
for L in range(lo + (lo - W["end"]) % 2, hi, 6):
    a = rot(axis_point(L))
    pts.append((a[0] - ref[0] + Q[0] - r0, a[1] - ref[1] + Q[1] - c0))
if not pts:
    sys.exit("outgoing piece too short")
reach = "\n".join(f"must-reach = r {r - 2} {c - 2} {r + 2} {c + 2}" for r, c in pts)
print(f"""# Connector search: {wname} wire, {mode}, A={A}, B={B}
rule = B3/S23-a5
pattern = {name}
max-changed = {C}
size = {SIZE}
margin = 12
max-gen = 240
{reach}
skip = oscillator, stable
per-rotor = 3
no-pics""")
