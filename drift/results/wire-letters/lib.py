import sys,pickle; sys.path.insert(0,"/Users/leo/Desktop/Life tools/Vibecoded life tools/casim")
import casim as C
R='B3/S23-a5'
comps=pickle.load(open('comps.pkl','rb'))
def pat(cells): return C.Pattern.from_coords(list(cells),R)
def cellset(p):
    return set(map(tuple,p.coords())) if hasattr(p,'coords') else None
TR=[lambda x,y:(x,y),lambda x,y:(-y,x),lambda x,y:(-x,-y),lambda x,y:(y,-x),
    lambda x,y:(-x,y),lambda x,y:(y,x),lambda x,y:(x,-y),lambda x,y:(-y,-x)]
def idle(i,g=600):
    p=pat(comps[i].keys()); p.step(g); a=set(p.coords()); p.step(1); assert set(p.coords())==a,i; return a
def run(cells,g):
    p=pat(cells); p.step(g); return set(p.coords())
def selfsym(S,win):
    """for each transform k, translations t with T_k(S)+t == S on window win (set of cells)"""
    res={}
    Sw=[c for c in S if c in win]
    for k,T in enumerate(TR):
        TS=set(T(*c) for c in S)
        a0=min(Sw)
        ts=set()
        for b in TS:
            t=(a0[0]-b[0],a0[1]-b[1])
            if all(((x-t[0],y-t[1]) in S_inv) for (x,y) in []): pass
            ok=True
            # check window
            for w in win:
                if (w in S)!=((w[0]-t[0],w[1]-t[1]) in TS): ok=False;break
            if ok: ts.add(t)
        res[k]=sorted(ts)
    return res
