#!/usr/bin/env python3
"""Known answers for driftlib.spark_stats (geometry only, so any rule's cycle will do)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import driftlib as L  # noqa: E402

RULE = "B3/S23-q4i"
table = L.rule_for(RULE)


def cycle(rle, p):
    h = [frozenset(q for q, s in L.parse_rle(rle).items() if s == 1)]
    for _ in range(p - 1):
        h.append(frozenset(L.step(h[-1], table)))
    assert frozenset(L.step(h[-1], table)) == h[0], "not periodic"
    return h


# findings/B3-S23-q4i/sparky.txt: p4 listed there with a depth-2 spark
sparky = cycle("x = 10, y = 7, rule = B3/S23-q4i\n4b3o$4b2o$obo4bo$7obo$8bo$2b3o3b2o$2bobo!", 4)
print("sparky p4:", L.spark_stats(sparky))
assert L.spark_stats(sparky)[1] >= 2


# Rotor 3 cells from the stator: free spark, depth 3, fully open.
c = [frozenset({(0, 0), (0, 3)}), frozenset({(0, 0)})]
assert L.spark_stats(c)[:2] == (1.0, 3), L.spark_stats(c)

# Transposed, so a row/column mix-up would show.
c = [frozenset({(0, 0), (3, 0)}), frozenset({(0, 0)})]
assert L.spark_stats(c)[:2] == (1.0, 3), L.spark_stats(c)

# Walled in: a rotor cell inside a closed stator ring can't be reached.
ring = {(r, c) for r in range(7) for c in range(7) if r in (0, 6) or c in (0, 6)}
c = [frozenset(ring | {(3, 3)}), frozenset(ring)]
assert L.spark_stats(c) == (0.0, 0, 0), L.spark_stats(c)

# No rotor at all.
assert L.spark_stats([frozenset(ring)]) == (0.0, 0, 0)
print("spark_stats: all ok")
