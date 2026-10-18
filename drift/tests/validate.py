#!/usr/bin/env python3
"""Independent check of drift's results (written without reusing drift's code).

For every result in a --jsonl file, decode the LifeHistory RLE, then:
  * every known background cell whose neighbourhood is known must be stable;
  * evolve gen 0 forward, treating a cell as stable when nothing in its 3x3
    window differs from the background (dr's own assumption), and require the
    neighbours of changed cells to be determined;
  * the number of changed cells per generation must match "change_counts";
  * oscillators must repeat with the stated period, fizzles must be empty.

The rule must be a Golly MAP string or a B/S totalistic rule (use
`drift --show-rule` to get the MAP form of an INT rule).

Usage: tests/validate.py RESULTS.jsonl [--rule MAP...]
"""
import argparse
import base64
import itertools
import json
import re
import sys


def rule_table(rule):
    """table[k] for k = 256*NW + 128*N + 64*NE + 32*W + 16*C + 8*E + 4*SW + 2*S + SE"""
    if rule.startswith("MAP"):
        s = rule[3:]
        s += "=" * (-len(s) % 4)
        bits = "".join(f"{b:08b}" for b in base64.b64decode(s))
        return [bits[k] == "1" for k in range(512)]
    m = re.fullmatch(r"B(\d*)/S(\d*)", rule)
    if not m:
        sys.exit(f"validate.py: can't read rule {rule!r}; pass its MAP form with --rule")
    birth, surv = set(map(int, m.group(1))), set(map(int, m.group(2)))
    table = []
    for k in range(512):
        n = bin(k & ~16).count("1")
        table.append(n in surv if k & 16 else n in birth)
    return table


def parse_rle(text):
    lines = [l for l in text.split("\n") if l and not l.startswith("#") and not l.startswith("x")]
    body = "".join(lines)
    cells, r, c, run = {}, 0, 0, ""
    for ch in body:
        if ch.isdigit():
            run += ch
            continue
        n = int(run) if run else 1
        run = ""
        if ch == "!":
            break
        if ch == "$":
            r += n
            c = 0
        elif ch in ".b":
            c += n
        else:
            state = 1 if ch == "o" else ord(ch) - ord("A") + 1
            for _ in range(n):
                cells[(r, c)] = state
                c += 1
    return cells


OFFS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 0), (0, 1), (1, -1), (1, 0), (1, 1)]
WEIGHT = [256, 128, 64, 32, 16, 8, 4, 2, 1]


def next3(table, window, cache={}):
    """window: 9 values (0, 1 or None) -> 0, 1 or None (undetermined)"""
    key = (id(table), window)
    if key in cache:
        return cache[key]
    unk = [i for i, v in enumerate(window) if v is None]
    seen = set()
    for bits in itertools.product((0, 1), repeat=len(unk)):
        w = list(window)
        for i, b in zip(unk, bits):
            w[i] = b
        seen.add(table[sum(WEIGHT[i] for i in range(9) if w[i])])
        if len(seen) == 2:
            break
    res = int(seen.pop()) if len(seen) == 1 else None
    cache[key] = res
    return res


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
            tables[rule] = rule_table(rule)
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
