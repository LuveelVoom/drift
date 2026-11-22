# verify drift escape results of a connector config: fill unknowns dead, simulate, check
import json,re,sys
exec(open('wirefit.py').read().split("base=C.parse_rle")[0])
def lh_parse(s,ox,oy):
    body=s.split('\n',1)[1].replace('\n','');x=y=0;out={}
    for m in re.finditer(r'(\d*)([.A-F$!bo])',body):
        n=int(m.group(1) or 1);t=m.group(2)
        if t=='$': y+=n;x=0;continue
        if t=='!':break
        for k in range(n): out[(x+k+ox,y+oy)]=t
        x+=n
    return out
def check(res_path, bounds, Mcells, T, full_extra=set()):
    """For each escape: on cells = A/E/D?, spark = C/D; unknown -> dead.
    full_extra: cells to add (rest of a long wire) not drawn in the grid."""
    X0,X1,Y0,Y1=bounds; out=[]
    for line in open(res_path):
        r=json.loads(line)
        if r['kind']!='escape': continue
        g=lh_parse(r['lifehistory'],X0,Y0)
        still=set(p for p,t in g.items() if t in 'AE')|set(full_extra)
        spark=set(p for p,t in g.items() if t=='C'); kill=set(p for p,t in g.items() if t=='D')
        g0=(still|spark)-kill
        q=C.Pattern.from_coords(list(still),R); q.step(1); stable=cells(q)==still
        Ml=sorted(near(Mcells,1)); mb=sum(1 for x in Ml if x in still)
        p=C.Pattern.from_coords(list(g0),R); hit=None
        for t in range(T):
            p.step(1)
            if hit is None and probe(p,Ml)!=mb: hit=t
        fin=cells(p); extra=fin-still; missing=still-fin
        out.append(dict(n=r['n'],stable=stable,signal_at_end=hit,extra=len(extra),missing=len(missing),fin=fin,still=still,g0=g0))
    return out
def finished_escapes(path):
    txt=open(path).read(); sec=txt.split('## Escapes',1)
    if len(sec)<2: return []
    out=[]
    for m in re.finditer(r'#C (escape[^\n]*)\n(x = [^\n]*\n(?:[^#\n][^\n]*\n?)+)',sec[1]):
        out.append((m.group(1),C.parse_rle(m.group(2))))
    return out
def strip_casing(S,W,H,d=3):
    return set((x,y) for x,y in S if d<=x<W-d and d<=y<H-d)
def run_finished(p, T, Mcells_local=None):
    g0=set(map(tuple,p.coords())); q=p.copy(); hist=[g0]
    for t in range(T): q.step(1); hist.append(set(map(tuple,q.coords())))
    fin=hist[-1]; q.step(1); stable=set(map(tuple,q.coords()))==fin
    return g0,fin,stable,hist
