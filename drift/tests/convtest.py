#!/usr/bin/env python3
"""Known answers for driftlib.spark_outputs, with an asymmetric still life in all 8
orientations: distance, generation and clean value mustn't depend on orientation."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import driftlib as L  # noqa: E402
import finish as F  # noqa: E402

table = L.rule_for("B3/S23-q4i")
rle = "x = 9, y = 10, rule = B3/S23-q4i\nb2ob2o$obobo$o4bo$b4o$o$3b2o$2bobo$3bo$4b3o$6bo!"
g0 = {q for q, s in L.parse_rle(rle).items() if s == 1}
got = None
for t in F.TRANSFORMS:
    g = frozenset(t(*q) for q in g0)
    h = [g]
    for _ in range(16):
        h.append(frozenset(L.step(h[-1], table)))
    still = h[-1]
    assert h[-2] == still, "not restored"
    r = (L.spark_outputs(still, h), len(g - still), max(t2 for t2 in range(len(h)) if h[t2] != still) + 1)
    got = got or r
    assert r == got, (r, got)
print("converter:", got)
assert got[0][0] == 3 and got[1] == 1 and got[2] <= 8   # the plan's dist 3, back by gen 8
print("spark_outputs: all ok")
