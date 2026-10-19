#!/usr/bin/env python3
"""What did the 2c/3 signal turn into? For each max-gen result of feed.cfg,
run the disturbance forward from the known cells (the stable-background rule
drift uses, so no completion is needed) and look at its last 30 generations
for a clean signal: a change pattern that repeats 3 times in a row, moved by
the same amount each time. Results are grouped by the output signal's period
and displacement; the input is the 2c/3 signal moving (2,2) every 3 gens.

Usage: classify.py RULEMAP [feed.jsonl]"""
import collections, json, os, sys
T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "drift", "tests")
sys.path.insert(0, T)
from validate import parse_rle, rule_table, next3, OFFS

table = rule_table(sys.argv[1])
path = sys.argv[2] if len(sys.argv) > 2 else "feed.jsonl"
NAMES = {(2, 2): "straight on", (-2, -2): "reflected back (180)", (-2, 2): "turned left (up-right)",
         (2, -2): "turned right (down-left)"}


def history(res):
    cells = parse_rle(res["lifehistory"])
    bk = {p: int(s in (1, 4)) for p, s in cells.items() if s in (1, 2, 3, 4)}
    state = {p: int(s in (1, 3)) for p, s in cells.items() if s in (1, 2, 3, 4)}
    hist = []
    for t in range(res["gen"] + 1):
        ch = {p for p, v in state.items() if p in bk and v != bk[p]}
        hist.append({p: state[p] for p in ch})
        near = {(r + a, c + b) for r, c in ch for a, b in OFFS}
        new = dict(bk)
        for r, c in near:
            v = next3(table, tuple(state.get((r + a, c + b)) for a, b in OFFS))
            if v is None:
                return hist
            new[(r, c)] = v
        state = new
    return hist


def signal(hist):
    """(P, displacement) of a signal repeating 3 times at the end, else None."""
    G = len(hist) - 1
    for P in range(1, 13):
        if G - 3 * P < 0:
            break
        a = sorted(hist[G - 3 * P].items())
        if not a:
            continue
        d = None
        ok = True
        for k in range(1, 4):
            b = sorted(hist[G - 3 * P + k * P].items())
            if len(a) != len(b):
                ok = False
                break
            dd = (b[0][0][0] - a[0][0][0], b[0][0][1] - a[0][0][1])
            if dd == (0, 0) or (d and dd != (d[0] * k, d[1] * k)) or \
                    any((q[0] - p[0], q[1] - p[1]) != dd or vp != vq for (p, vp), (q, vq) in zip(a, b)):
                ok = False
                break
            d = d or dd
        if ok:
            return P, d
    return None


groups = collections.defaultdict(list)
n = 0
for line in open(path):
    res = json.loads(line)
    if res["kind"] != "maxgen":
        continue
    n += 1
    s = signal(history(res))
    groups[s].append(res["n"])
print(f"{n} results still going at max gen")
for s, nums in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    if s is None:
        print(f"  {len(nums):5d}  no clean signal at the end")
        continue
    P, d = s
    name = NAMES.get(d, "") if P == 3 else ""
    print(f"  {len(nums):5d}  period {P}, moving {d}{'  = 2c/3 signal ' + name if name else ''}  e.g. #{nums[0]}")
