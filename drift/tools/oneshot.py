#!/usr/bin/env python3
"""One-shot glider reactions: the catalyst may be destroyed afterwards.

usage: python3 tools/oneshot.py CONFIG [MIND]      (put in drift/tools/, next to convanalyze.py)
  env: DIR glider direction per 4 gens as dr,dc (default 1,-1), OUT (default oneshot.rle),
       LATER gens simulated after the result's last gen to see the catalyst's fate (default 100),
       JOBS worker processes for the completion stage (default 2)

Reads CONFIG-results.jsonl (run drift with a short max-gen, keeping maxgen results). For every
"maxgen", "fizzle" or "oscillator" result:

Stage 1, no completion (exact): replay the reaction on drift's own known cells. A cell's next
state is computed only where its whole 3x3 neighbourhood is known; every other cell keeps its
background value. drift fixed every background cell the reaction can reach, so this reproduces
its evolution. Then
  contact  first gen differing from (background + free glider)
  entry    cells differing from (background + free glider) in gens contact..contact+2, plus the
           free glider up to contact
  output   cells alive outside the background, in the dead region 4-connected to the outside
           (unknown cells counted as empty: this only adds candidates, never removes one), at
           Chebyshev distance >= MIND (default 4) from the entry
Results without an output stop here. Duplicates (same nearby background + glider, over the 8
orientations) are dropped.

Stage 2, survivors only, in JOBS processes: complete the background (finish.py), keep only the
still-life pieces within 2 of a cell the reaction changed (the completion may fill far-away
unconstrained space with arbitrary still lifes), re-check the output on the completed pattern,
check the glider comes from infinity (started 40 periods back it reaches the same gen 0), and
simulate LATER more gens: catalyst restored / destroyed and what is left."""
import json, os, sys
from multiprocessing import Pool
import numpy as np
TOOLS = os.environ.get("DRIFT_TOOLS", os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import driftlib as L
import finish as F
import convanalyze as C

DIR = tuple(int(x) for x in os.environ.get("DIR", "1,-1").split(","))
OUT = os.environ.get("OUT", "oneshot.rle")
LATER = int(os.environ.get("LATER", "100"))
JOBS = int(os.environ.get("JOBS", "2"))
TR = C.TR


def cheb(p, qs):
    return min(max(abs(p[0] - a), abs(p[1] - b)) for a, b in qs)


def exterior(walls, pad=8):
    rs = [r for r, c in walls]
    cs = [c for r, c in walls]
    r0, r1, c0, c1 = min(rs) - pad, max(rs) + pad, min(cs) - pad, max(cs) + pad
    free, todo = {(r0, c0)}, [(r0, c0)]
    while todo:
        r, c = todo.pop()
        for q in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if r0 <= q[0] <= r1 and c0 <= q[1] <= c1 and q not in free and q not in walls:
                free.add(q)
                todo.append(q)
    return free, (r0, r1, c0, c1)


def frozen_run(states, table, gens):
    """Replay on known cells only. states: {(r,c): 1..4} from drift's LifeHistory."""
    rs = [r for r, c in states]
    cs = [c for r, c in states]
    r0, c0 = min(rs) - 1, min(cs) - 1
    H, W = max(rs) - r0 + 2, max(cs) - c0 + 2
    known = np.zeros((H, W), bool)
    bg = np.zeros((H, W), np.int16)
    cur = np.zeros((H, W), np.int16)
    for (r, c), s in states.items():
        if s in (1, 2, 3, 4):
            known[r - r0, c - c0] = True
            bg[r - r0, c - c0] = s in (1, 4)
            cur[r - r0, c - c0] = s in (1, 3)
    k = np.pad(known, 1)
    full = np.ones_like(known)
    for a in (0, 1, 2):
        for b in (0, 1, 2):
            full &= k[a:a + H, b:b + W]
    tab = np.array([bool(x) for x in table])
    out = [cur.copy()]
    for _ in range(gens):
        p = np.pad(cur, 1)
        idx = (p[:-2, :-2] * 256 + p[:-2, 1:-1] * 128 + p[:-2, 2:] * 64 + p[1:-1, :-2] * 32 + p[1:-1, 1:-1] * 16 +
               p[1:-1, 2:] * 8 + p[2:, :-2] * 4 + p[2:, 1:-1] * 2 + p[2:, 2:])
        cur = np.where(full, tab[idx], bg).astype(np.int16)
        out.append(cur.copy())
    toset = lambda g: frozenset((int(r) + r0, int(c) + c0) for r, c in zip(*np.nonzero(g)))
    return toset(bg), [toset(g) for g in out]


def output_of(still, hist, glider, table, mind):
    """(dist, gen, depth, contact) of the farthest output, or None."""
    g = len(hist) - 1
    fg = [glider]
    for _ in range(g):
        fg.append(frozenset(L.step(fg[-1], table)))
    contact = next((t for t in range(g + 1) if hist[t] != (still | fg[t])), None)
    if contact is None:
        return None
    entry = set().union(*fg[:contact + 1])
    for t in range(contact, min(contact + 3, g + 1)):
        entry |= hist[t] ^ (still | fg[t])
    ext, _ = exterior(still)
    best = None
    for t in range(contact + 1, g + 1):
        for p in hist[t] - still:
            if p in ext:
                d = cheb(p, entry)
                if d >= mind and (best is None or d > best[0]):
                    best = (d, t, cheb(p, still), contact)
    return best


def canon(still, glider):
    best = None
    for t in TR:
        a = [t(*p) for p in still | glider]
        gl = {t(*p) for p in glider}
        r0 = min(p[0] for p in a)
        c0 = min(p[1] for p in a)
        k = tuple(sorted(((p[0] - r0, p[1] - c0), p in gl) for p in a))
        best = k if best is None or k < best else best
    return best


def near_pieces(still, changed):
    return frozenset().union(*[cp for cp in L.components(still)
                               if any(max(abs(a - c), abs(b - d)) <= 2 for a, b in cp for c, d in changed)])


FIN = {}


def stage2(job):
    cfg, res, mind = job
    table = L.rule_for(L.config_rule(cfg))
    fin = FIN.setdefault(cfg, F.Finisher(cfg, table, 5))
    fast = C.Fast(table)
    g = res["gen"]
    # Complete locally: new live cells only within R of drift's known live background (R = 2,
    # then 4, then 6), so unconstrained space isn't filled with arbitrary still lifes.
    known = {p: s for p, s in L.parse_rle(res["lifehistory"]).items() if s in (1, 2, 3, 4)}
    onbg = [p for p, s in known.items() if s in (1, 4)]
    spark_on = frozenset(p for p, s in known.items() if s == 3)
    spark_off = frozenset(p for p, s in known.items() if s == 4)
    emp0 = fin.empty_for(res)
    bk = None
    for R in (2, 4, 6):
        allowed = {(r + a, c + b) for r, c in onbg for a in range(-R, R + 1) for b in range(-R, R + 1)}
        bk = L.complete(known, table, R + 1, lambda p: emp0(p) or p not in allowed)
        if bk:
            break
    if not bk:
        return dict(n=res["n"], why="no completion")
    still = frozenset(p for p, v in bk.items() if v)
    glider = spark_on
    hist = [frozenset((still - spark_off) | spark_on)]
    for _ in range(g):
        hist.append(frozenset(L.step(hist[-1], table)))
    changed = set().union(*(frozenset(h) ^ still for h in hist[:g + 1]))
    still = near_pieces(still, changed)
    if frozenset(L.step(still, table)) != still:
        return dict(n=res["n"], why="prune broke the still life")
    hs, off = fast.run(still | glider, g, pad=14)
    if hs[-1] is None:
        return dict(n=res["n"], why="left the box")
    hist = [C.cells_of(x, off) for x in hs]
    best = output_of(still, hist, glider, table, mind)
    if not best:
        return dict(n=res["n"], why="no output after completion")
    back = frozenset((p[0] - DIR[0] * 40, p[1] - DIR[1] * 40) for p in glider)
    hb, offb = fast.run(still | back, 160, pad=6)
    if hb[-1] is None or C.cells_of(hb[-1], offb) != (still | glider):
        return dict(n=res["n"], why="not from infinity")
    _, box = exterior(still)
    inb = lambda p: box[0] <= p[0] <= box[1] and box[2] <= p[1] <= box[3]
    hl = [hist[-1]]
    for _ in range(LATER):
        hl.append(frozenset(L.step(hl[-1], table)))
    end = frozenset(p for p in hl[-1] if inb(p))
    if end == still and frozenset(p for p in hl[-2] if inb(p)) == still:
        fate = "catalyst restored"
    else:
        per = next((d for d in range(1, 61) if frozenset(p for p in hl[-1 - d] if inb(p)) == end), None)
        if per is None:
            fate = f"still active after {LATER} more gens"
        else:
            fate = "catalyst destroyed; " + ("settles into a still life" if per == 1 else f"leaves a p{per}")
            if still <= end:
                fate += " (old still life intact, plus debris)"
    return dict(n=res["n"], kind=res["kind"], still=sorted(still), glider=sorted(glider), dist=best[0],
                gen=best[1], depth=best[2], contact=best[3], fate=fate)


def main():
    cfg = sys.argv[1]
    mind = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    table = L.rule_for(L.config_rule(cfg))
    counts, jobs, seen = {}, [], set()
    for line in open(cfg[:-4] + "-results.jsonl"):
        res = json.loads(line)
        if res["kind"] not in ("maxgen", "fizzle", "oscillator"):
            continue
        counts[res["kind"]] = counts.get(res["kind"], 0) + 1
        states = {p: s for p, s in L.parse_rle(res["lifehistory"]).items() if s in (1, 2, 3, 4)}
        bg, hist = frozen_run(states, table, res["gen"])
        glider = hist[0] - bg
        if len(glider) != 5:
            counts["odd"] = counts.get("odd", 0) + 1
            continue
        if not output_of(bg, hist, glider, table, mind):
            counts["no output (stage 1)"] = counts.get("no output (stage 1)", 0) + 1
            continue
        changed = set().union(*(h ^ bg for h in hist))
        k = canon(near_pieces(bg, changed) if bg else frozenset(), glider)
        if k in seen:
            counts["duplicate"] = counts.get("duplicate", 0) + 1
            continue
        seen.add(k)
        jobs.append((cfg, res, mind))
    print(f"stage 1: {counts}; {len(jobs)} go to completion", flush=True)
    with Pool(JOBS) as pool:
        out = pool.map(stage2, jobs)
    found = {}
    for o in out:
        if "why" in o:
            counts[o["why"]] = counts.get(o["why"], 0) + 1
            continue
        still, glider = frozenset(map(tuple, o["still"])), frozenset(map(tuple, o["glider"]))
        k = canon(still, glider)
        if k in found and len(found[k]["still"]) <= len(still):
            continue
        o["still"], o["glider"] = still, glider
        found[k] = o
    items = sorted(found.values(), key=lambda o: ("restored" in o["fate"], -o["dist"], len(o["still"])))
    print("counts:", counts, "kept:", len(items))
    allc, x = set(), 0
    for i, o in enumerate(items):
        cells = o["still"] | o["glider"]
        rs = [r for r, c in o["still"]]
        cs = [c for r, c in o["still"]]
        print(f"{i + 1}. {len(o['still'])} cells {max(cs) - min(cs) + 1}x{max(rs) - min(rs) + 1}: glider hits at gen "
              f"{o['contact']}, output {o['dist']} from the entry at gen {o['gen']} (depth {o['depth']}); "
              f"{o['fate']}   [#{o['n']}, {o['kind']}]")
        r0 = min(p[0] for p in cells)
        c0 = min(p[1] for p in cells)
        allc |= {(p[0] - r0, p[1] - c0 + x) for p in cells}
        x += max(p[1] for p in cells) - c0 + 14
    if allc:
        lines = L.to_rle(allc, L.config_rule(cfg)).split("\n")
        with open(OUT, "w") as f:
            f.write(lines[0].replace(" ", "") + "\n" + "".join(lines[1:]) + "\n")
        print(f"all {len(items)} in one pattern: {OUT}")


if __name__ == "__main__":
    main()
