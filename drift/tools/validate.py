#!/usr/bin/env python3
"""Independent check of drift's results (written without reusing drift's code).

For every result in a --jsonl file, decode the LifeHistory RLE, then:
  * every known background cell whose neighbourhood is known must be stable;
  * evolve gen 0 forward, treating a cell as stable when nothing in its 3x3
    window differs from the background (dr's own assumption), and require the
    neighbours of changed cells to be determined;
  * the number of changed cells per generation must match "change_counts";
  * oscillators must repeat with the stated period, fizzles must be empty.

Usage: tools/validate.py RESULTS.jsonl [--rule RULE]   (the rule is read from the results by default)
"""
import argparse
import base64
import itertools
import json
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from driftlib import OFFS, WEIGHT, next3, parse_rle, rule_for  # noqa: E402


def check(res, table):
    cells = parse_rle(res["lifehistory"])
    bk = {p: (1 if s in (1, 4) else 0) for p, s in cells.items() if s in (1, 2, 3, 4)}
    g0 = {p: (1 if s in (1, 3) else 0) for p, s in cells.items() if s in (1, 2, 3, 4)}
    errors = []
    # 1. background stability
    for (r, c), v in bk.items():
        w = tuple(bk.get((r + dr, c + dc)) for dr, dc in OFFS)
        if None not in w and next3(table, w) != v:
            errors.append(f"background unstable at {r},{c}")
            break
    # 2. evolution
    gen = res["gen"]
    state = dict(g0)
    history = []
    for t in range(gen + 1):
        changed = {p for p, v in state.items() if p in bk and v != bk[p]}
        history.append(frozenset((p, state[p]) for p in changed))
        want = res["change_counts"][t]
        if len(changed) != want:
            errors.append(f"gen {t}: {len(changed)} changed cells, drift says {want}")
            break
        if t == gen:
            break
        near = {(r + dr, c + dc) for (r, c) in changed for dr, dc in OFFS}
        new = dict(bk)   # cells away from changes keep their background value
        for (r, c) in near:
            w = tuple(state.get((r + dr, c + dc)) for dr, dc in OFFS)
            v = next3(table, w)
            if v is None:
                errors.append(f"gen {t + 1}: cell {r},{c} next to a change is undetermined")
                break
            new[(r, c)] = v
        if errors:
            break
        state = new
    if not errors:
        if res["kind"] == "oscillator":
            p = res["period"]
            if history[gen] != history[gen - p] or not history[gen]:
                errors.append(f"gen {gen} doesn't repeat gen {gen - p}")
        elif res["kind"] == "fizzle" and history[gen]:
            errors.append("fizzle doesn't return to the background")
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--rule")
    a = ap.parse_args()
    tables = {}
    n = bad = 0
    for line in open(a.jsonl):
        res = json.loads(line)
        rule = a.rule or res["rule"]
        if rule not in tables:
            tables[rule] = rule_for(rule)
        errs = check(res, tables[rule])
        n += 1
        if errs:
            bad += 1
            if bad <= 5:
                print(f"result #{res['n']} ({res['kind']}): " + "; ".join(errs))
    print(f"{n} results checked, {bad} invalid")
    return 1 if bad or not n else 0


if __name__ == "__main__":
    sys.exit(main())
