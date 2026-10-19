#!/usr/bin/env python3
"""Find wire candidates among drift's "max gen" results.

A repeating track is only a candidate: a disturbance that zigzags along a
track drift improvised also gives a repeating background. Check candidates
with wirebuild.py, which requires the signal itself to repeat.

A signal still going at max gen has built its own track. If that track is a
wire, the known background repeats: shifting it by the wire's period maps it
onto itself. For each result this finds the shift with the best agreement
over known cells (at least MIN overlapping cells) and lists the strongest
candidates, grouped by shift.

Usage: tools/wirecheck.py RESULTS.jsonl [--min 80] [--top 10]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from driftlib import parse_rle  # noqa: E402


def best_shift(bk, min_overlap):
    best = (0.0, 0, None)
    for dr in range(-14, 15):
        for dc in range(-14, 15):
            if (dr, dc) <= (0, 0):       # each shift and its negative once
                continue
            both = [p for p in bk if (p[0] + dr, p[1] + dc) in bk]
            if len(both) < min_overlap:
                continue
            live = sum(1 for p in both if bk[p])
            if live < 8:                 # mostly empty space agrees trivially
                continue
            agree = sum(bk[p] == bk[(p[0] + dr, p[1] + dc)] for p in both) / len(both)
            if agree > best[0]:
                best = (agree, len(both), (dr, dc))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--min", type=int, default=80)
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args()
    rows = []
    for line in open(a.jsonl):
        try:
            res = json.loads(line)
        except ValueError:
            continue
        if res.get("kind") != "maxgen":
            continue
        cells = parse_rle(res["lifehistory"])
        bk = {p: int(s in (1, 4)) for p, s in cells.items() if s in (1, 2, 3, 4)}
        agree, n, shift = best_shift(bk, a.min)
        if shift:
            rows.append((agree, n, shift, res["n"]))
    rows.sort(reverse=True)
    print(f"{len(rows)} max-gen results with a repeating background candidate")
    seen = {}
    for agree, n, shift, num in rows:
        seen.setdefault(shift, []).append((agree, n, num))
    shown = 0
    for agree, n, shift, num in rows:
        if shown >= a.top:
            break
        if seen.get(shift) is None:
            continue
        group = seen.pop(shift)
        print(f"  shift {shift}: best {agree:.0%} of {n} known cells (result #{num}); "
              f"{len(group)} results with this shift")
        shown += 1


if __name__ == "__main__":
    main()
