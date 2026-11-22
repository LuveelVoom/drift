import sys,re; sys.path.insert(0, "/Users/leo/Desktop/Life tools/Vibecoded life tools/casim")
import casim as C
R='B3/S23-a5'
def cells(p): return set(map(tuple,p.coords()))
def exterior(still):
    xs=[x for x,y in still]; ys=[y for x,y in still]
    X0,X1,Y0,Y1=min(xs)-4,max(xs)+4,min(ys)-4,max(ys)+4
    ext=set(); st=[(X0,Y0)]
    while st:
        p=st.pop()
        if p in ext or p in still or not(X0<=p[0]<=X1 and Y0<=p[1]<=Y1): continue
        ext.add(p); st+=[(p[0]+1,p[1]),(p[0]-1,p[1]),(p[0],p[1]+1),(p[0],p[1]-1)]
    return ext
def weak_spark(g0,T=300,skip_gens=0):
    """still = final state; output = cells alive at some gen, not in still, in exterior.
    returns max over output cells of Chebyshev distance to nearest still-life cell, and those cells"""
    q=C.Pattern.from_coords(list(g0),R); H=[g0]
    for t in range(T): q.step(1); H.append(cells(q))
    still=H[-1]; ext=exterior(still)
    out={}
    for t,S in enumerate(H[1:],1):
        if t<skip_gens: continue
        for c in S-still:
            if c in ext: out.setdefault(c,t)
    def d(c): return min(max(abs(c[0]-a),abs(c[1]-b)) for a,b in still)
    best=max((d(c),c,t) for c,t in out.items()) if out else (0,None,None)
    return best,still,out
def clean_outputs(still,out):
    ext=exterior(still); res=[]
    for c,t in out.items():
        for i in (-1,0,1):
            for j in (-1,0,1):
                e=(c[0]+i,c[1]+j)
                if e in ext and e not in out and not any((e[0]+a,e[1]+b) in still for a in (-1,0,1) for b in (-1,0,1)):
                    res.append((c,t)); break
            else: continue
            break
    return res
