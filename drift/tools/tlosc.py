#!/usr/bin/env python3
"""Oscillators from the plus (bo$3o$bo!) searches: complete each distinct rotor (period >= MINP),
then look through its whole cycle for a clean traffic light (both phases tried) and for the plus,
centred where the plus was drawn. Clean = all its cells alive and no other live cell within
1 of them. Also period and spark stats. One JSON line per oscillator to OUT.

usage: tlosc.py OUT MINP CONFIG... (config dir names end in -r2/-r3[a-c]: ring radius)"""
import json, os, re, sys
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import driftlib as L
import finish as F

TL_A = [(-3, -1), (-3, 0), (-3, 1), (3, -1), (3, 0), (3, 1), (-1, -3), (0, -3), (1, -3), (-1, 3), (0, 3), (1, 3)]
TL_B = [(-4, 0), (-3, 0), (-2, 0), (2, 0), (3, 0), (4, 0), (0, -4), (0, -3), (0, -2), (0, 2), (0, 3), (0, 4)]
PLUS = [(-1, 0), (0, -1), (0, 0), (0, 1), (1, 0)]


def clean_at(phase, shape, c):
    cells = {(c[0] + a, c[1] + b) for a, b in shape}
    if not cells <= phase:
        return False
    ring = {(r + i, cc + j) for r, cc in cells for i in (-1, 0, 1) for j in (-1, 0, 1)} - cells
    return not (ring & phase)


FIN = {}


def work(job):
    cfg, line = job
    res = json.loads(line)
    if cfg not in FIN:
        T = L.rule_for(L.config_rule(cfg))
        FIN[cfg] = F.Finisher(cfg, T, 5)
    fin = FIN[cfg]
    try:
        got = fin.oscillator(res)
    except Exception as e:
        return None
    if not got or not got[1]:
        return dict(cfg=cfg, n=res["n"], status=got[0] if got else "no completion")
    kind, info = got
    p, g = res["period"], res["gen"]
    cyc = [frozenset(x) for x in info["hist"][g:g + p]]
    R = int(re.search(r"-r(\d)", cfg).group(1))
    o = res.get("origin", (0, 0))
    c = (R + 1 - o[0], R + 1 - o[1])
    tl = [t for t, ph in enumerate(cyc) if clean_at(ph, TL_A, c) or clean_at(ph, TL_B, c)]
    has = lambda ph, shape: {(c[0] + a, c[1] + b) for a, b in shape} <= ph
    tl_loose = [t for t, ph in enumerate(cyc) if has(ph, TL_A) or has(ph, TL_B)]
    # partial traffic light: how many of its 4 blinkers (either phase) are present, best and worst phase
    blink = [TL_A[0:3], TL_A[3:6], TL_A[6:9], TL_A[9:12]]
    blinkB = [TL_B[0:3], TL_B[3:6], TL_B[6:9], TL_B[9:12]]
    nb = [sum(1 for x, y in zip(blink, blinkB) if has(ph, x) or has(ph, y)) for ph in cyc]
    pl = [t for t, ph in enumerate(cyc) if clean_at(ph, PLUS, c)]
    op, dep, tc = L.spark_stats(cyc)
    return dict(cfg=cfg, n=res["n"], status=kind, period=p, cells=len(cyc[0]), tl=len(tl), tl_loose=len(tl_loose), blinkers_max=max(nb), blinkers_min=min(nb), plus=len(pl),
                open=op, depth=dep, touch=tc, g0=sorted(info["hist"][0]), damage=info.get("damage", 0))


def main():
    out, minp = sys.argv[1], int(sys.argv[2])
    jobs, seen = [], set()
    for cfg in sys.argv[3:]:
        for line in open(cfg[:-4] + "-results.jsonl"):
            r = json.loads(line)
            if r["kind"] != "oscillator" or r["period"] < minp or r["rotor"] in seen:
                continue
            seen.add(r["rotor"])
            jobs.append((cfg, line))
    print(len(jobs), "distinct rotors to complete", flush=True)
    with Pool(2) as pool, open(out, "w") as fo:
        for k, r in enumerate(pool.imap_unordered(work, jobs, chunksize=4)):
            if r:
                fo.write(json.dumps(r) + "\n")
            if k % 100 == 0:
                print(k, flush=True)


if __name__ == "__main__":
    main()
