"""sparkout.py RULE RLE SPARKRLE: for converters (still life + the given spark, pieces >= 7 apart),
output cells = cells alive outside the still life, reachable from outside, at Chebyshev distance
>= 2 from every cell the spark reaches when evolved alone."""
import sys
import os; sys.path.insert(0, os.environ.get('DRIFT_TOOLS', os.path.dirname(os.path.abspath(__file__))))
import driftlib as L, convanalyze as C
rule, path, sprle = sys.argv[1:4]; T = L.rule_for(rule); f = C.Fast(T)
spark0 = C.norm(frozenset(L.parse_rle("x=0,y=0\n" + sprle)))
cells = frozenset(L.parse_rle(open(path).read()))
for i, comp in enumerate(sorted(C.split(cells, 7), key=lambda c: (min(r for r, _ in c), min(cc for _, cc in c)))):
    X = C.Conv(comp, f, gens=80)
    env = set(); s = X.inp
    for t in range(60):
        env |= s; s = frozenset(L.step(s, T))
    outs = {}
    for t in range(1, len(X.hist)):
        for p in X.hist[t] - X.still:
            if p in X.ext and C.cheb(p, env) >= 2 and p not in outs:
                outs[p] = t
    tag = "spark matches" if any(C.norm({tf(*p) for p in X.inp}) == spark0 for tf in C.TR) else "SPARK DIFFERS"
    if outs:
        far = max(outs, key=lambda p: C.cheb(p, env))
        print(f"{i+1}. {len(X.still)} cells, back {X.back}: output {C.cheb(far, env)} beyond the spark's own reach, "
              f"depth {max(C.cheb(p, X.still) for p in outs)}, gens {min(outs.values())}-{max(outs.values())} ({tag})")
    else:
        print(f"{i+1}. {len(X.still)} cells, back {X.back}: nothing beyond the spark's own reach ({tag})")
