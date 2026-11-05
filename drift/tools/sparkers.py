"""sparkers.py RULE MINDEPTH FINISHED.txt ... : distinct clean sparky oscillators (no damage) with
spark depth >= MINDEPTH, re-simulated, one combined RLE (header without spaces)."""
import sys, re
import os; sys.path.insert(0, os.environ.get('DRIFT_TOOLS', os.path.dirname(os.path.abspath(__file__))))
import driftlib as L
rule, mind = sys.argv[1], int(sys.argv[2]); T = L.rule_for(rule)
TR=[lambda r,c:(r,c),lambda r,c:(r,-c),lambda r,c:(-r,c),lambda r,c:(-r,-c),lambda r,c:(c,r),lambda r,c:(c,-r),lambda r,c:(-c,r),lambda r,c:(-c,-r)]
def norm(s):
    r0=min(r for r,c in s); c0=min(c for r,c in s); return tuple(sorted((r-r0,c-c0) for r,c in s))
seen=set(); osc=[]
for fn in sys.argv[3:]:
    for head,rle in re.findall(r"(#C [^\n]*)\n(x = [^\n]*\n(?:[^#\n][^\n]*\n)*)", open(fn).read()):
        if "still-life cells changed" in head: continue
        s=frozenset(L.parse_rle(rle)); h=[s]; idx={}
        while h[-1] not in idx and len(h)<600: idx[h[-1]]=len(h)-1; h.append(frozenset(L.step(h[-1],T)))
        if h[-1] not in idx: continue
        st=idx[h[-1]]; cyc=h[st:-1]
        if len(cyc)<2: continue
        op,dep,tc=L.spark_stats(cyc)
        if dep<mind: continue
        key=min(norm({t(*p) for p in ph}) for ph in cyc for t in TR)
        if key in seen: continue
        seen.add(key); osc.append((dep,tc,len(cyc),len(cyc[0]),cyc[0],op))
osc.sort(key=lambda o:(-o[0],-o[1]))
x=0; allc=set()
for i,(dep,tc,per,n,ph,op) in enumerate(osc):
    r0=min(r for r,c in ph); c0=min(c for r,c in ph); w=max(c for r,c in ph)-c0+1
    allc|={(r-r0,c-c0+x) for r,c in ph}
    print(f"{i+1}. x={x}: p{per}, {n} cells, spark depth {dep}, {tc} touch cells, open {op:.0%}"); x+=w+8
if allc:
    lines=L.to_rle(allc,rule).split("\n"); print(lines[0].replace(" ","")); print("".join(lines[1:]))
