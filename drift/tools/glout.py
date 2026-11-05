"""glout.py RULE RLE: per glider reaction (still life + glider, pieces >=8 apart), exterior output
cells >= 3 from the glider's free path (both directions), their depth (distance from the still life;
>=2 = free) and side. Also chain-free 'escape' check: anything left far away."""
import sys
import os; sys.path.insert(0, os.environ.get('DRIFT_TOOLS', os.path.dirname(os.path.abspath(__file__))))
import driftlib as L, convanalyze as C
rule, path = sys.argv[1], sys.argv[2]; T = L.rule_for(rule); f = C.Fast(T)
cells = frozenset(L.parse_rle(open(path).read()))
comps = sorted(C.split(cells, 7), key=lambda c: (min(r for r, _ in c), min(cc for _, cc in c)))
for i, comp in enumerate(comps):
    X = C.Conv(comp, f, gens=80)
    gl = X.inp
    # free glider path, 40 periods back and forward
    path_cells = set(); g = gl
    for t in range(160):
        path_cells |= g; g = frozenset(L.step(g, T))
    g = frozenset((r - 40, c - 40) for r, c in gl)
    for t in range(160):
        path_cells |= g; g = frozenset(L.step(g, T))
    outs = {}
    for t in range(1, len(X.hist)):
        for p in X.hist[t] - X.still:
            if p in X.ext and C.cheb(p, path_cells) >= 3 and p not in outs:
                outs[p] = t
    if outs:
        depth = max(C.cheb(p, X.still) for p in outs)
        far = max(outs, key=lambda p: C.cheb(p, path_cells))
        print(f"{i+1:3d}. {len(X.still)} cells, back {X.back}: {len(outs)} output cells, max off-path {C.cheb(far, path_cells)}, depth {depth}, first gen {min(outs.values())}")
    else:
        print(f"{i+1:3d}. {len(X.still)} cells, back {X.back}: no output off the glider's path")
