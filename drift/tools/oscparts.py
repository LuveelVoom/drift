#!/usr/bin/env python3
"""Extract the real oscillators from selected plus-search results.

usage: oscparts.py SELECT.jsonl OUTPREFIX
SELECT lines: {"cfg":..., "n":...} (from tlosc). For each: complete (Finisher.oscillator), split
into independent parts (finish.oscillator_parts), minimise each part's stator
(L.minimize, cyclic), re-check the period by simulation, and for the part containing the
traffic-light area count phases with all 12 traffic-light cells. Distinct by rotor key.
Writes OUTPREFIX.txt (one line each) and OUTPREFIX.rle (all, 8 apart, header without spaces)."""
import json, re, sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import driftlib as L
import finish as F
from tlosc import TL_A, TL_B

T = L.rule_for("B3/S23-q4i")
fins, seen, out = {}, set(), []
for line in open(sys.argv[1]):
    sel = json.loads(line)
    cfg = sel["cfg"]
    res = next(json.loads(l) for l in open(cfg[:-4] + "-results.jsonl") if json.loads(l)["n"] == sel["n"])
    fin = fins.setdefault(cfg, F.Finisher(cfg, T, 10))
    got = fin.oscillator(res)
    if not got or not got[1]:
        continue
    info = got[1]
    p, g = res["period"], res["gen"]
    cyc = [frozenset(x) for x in info["hist"][g:g + p]]
    R = int(re.search(r"-r(\d)", cfg).group(1))
    o = res.get("origin", (0, 0))
    c = (R + 1 - o[0], R + 1 - o[1])
    tlcells = [{(c[0] + a, c[1] + b) for a, b in s} for s in (TL_A, TL_B)]
    for ph, per, key, alone in F.oscillator_parts(cyc, T):
        if key in seen:
            continue
        seen.add(key)
        tlph = sum(1 for s in ph if any(t <= s for t in tlcells))
        best = None
        for margin, secs in ((4, 20), (7, 40)):
            m = L.minimize([set(s) for s in ph], T, True, margin=margin, seconds=secs)
            if not m:
                continue
            h = [frozenset(m[0])]
            for _ in range(2 * per):
                h.append(frozenset(L.step(h[-1], T)))
            if h[per] == h[0] and h[2 * per] == h[0] and not any(h[d] == h[0] for d in range(1, per)):
                best = h[:per]
                break
        shrunk = best is not None
        if not best:
            if not alone:
                continue
            best = ph
        op, dep, tc = L.spark_stats(best)
        out.append(dict(src=f"{cfg.split('/')[0]} #{sel['n']}", period=per, cells=len(best[0]), depth=dep, touch=tc,
                        open=op, tl=tlph, shrunk=shrunk, phase=sorted(best[0])))
        print(f"p{per}, {len(best[0])} cells, spark depth {dep}, {tc} touch, traffic light in {tlph}/{per} phases"
              f"{'' if shrunk else ' (stator not minimised)'}  [{cfg.split('/')[0]} #{sel['n']}]", flush=True)
out.sort(key=lambda o: (-(o["tl"] > 0), -o["period"], -o["depth"], o["cells"]))
with open(sys.argv[2] + ".txt", "w") as f:
    for k, o in enumerate(out):
        f.write(f"{k + 1}. p{o['period']}, {o['cells']} cells, spark depth {o['depth']}, {o['touch']} touch cells, "
                f"traffic light in {o['tl']}/{o['period']} phases  [{o['src']}]\n")
allc, x = set(), 0
for o in out:
    ph = o["phase"]
    r0 = min(r for r, cc in ph)
    c0 = min(cc for r, cc in ph)
    allc |= {(r - r0, cc - c0 + x) for r, cc in ph}
    x += max(cc for r, cc in ph) - c0 + 9
if allc:
    lines = L.to_rle(allc, "B3/S23-q4i").split("\n")
    open(sys.argv[2] + ".rle", "w").write(lines[0].replace(" ", "") + "\n" + "".join(lines[1:]) + "\n")
