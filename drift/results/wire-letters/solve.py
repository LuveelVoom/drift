import cad,itertools
def resid(spec):
    c,info=cad.build(spec,geom=True)
    g0,d0=info['placed'][0][1],info['placed'][0][2]
    g,d=info['closing']
    assert g==g0,('orientation does not close',g,g0)
    return d
def solve(spec,maxdev=6,verbose=True,allowed=None):
    spec=[list(s) for s in spec]
    r0=resid(spec)
    if r0==(0,0): return spec
    n=len(spec); V=[]
    for i in range(n):
        s2=[list(x) for x in spec]; s2[i][2]+=1
        r=resid(s2); V.append((r[0]-r0[0],r[1]-r0[1]))
    best=None
    # try pairs and triples of adjustments: find integer deltas
    idx=[i for i in range(n) if allowed is None or i in allowed]
    for i,j in itertools.combinations(idx,2):
        a,b=V[i],V[j]
        det=a[0]*b[1]-a[1]*b[0]
        if det==0: continue
        # solve x*a+y*b=-r0
        rx,ry=-r0[0],-r0[1]
        xn=rx*b[1]-ry*b[0]; yn=a[0]*ry-a[1]*rx
        if xn%det or yn%det: continue
        x,y=xn//det,yn//det
        if spec[i][2]+x<0 or spec[j][2]+y<0: continue
        cost=abs(x)+abs(y)
        if best is None or cost<best[0]: best=(cost,i,j,x,y)
    if best is None:
        # single direction
        for i in idx:
            a=V[i]
            for x in range(-maxdev*3,maxdev*3+1):
                if (x*a[0],x*a[1])==(-r0[0],-r0[1]) and spec[i][2]+x>=0:
                    best=(abs(x),i,i,x,0)
    if best is None:
        if verbose: print('no solution; r0',r0,'V',V)
        return None
    cost,i,j,x,y=best
    if verbose: print('r0',r0,'adjust',i,x,j,y)
    spec[i][2]+=x
    if j!=i: spec[j][2]+=y
    assert resid(spec)==(0,0)
    return spec
def solve3(spec,pair,par,verbose=False):
    """try parity fixes on index list par (+0,+1), then solve pair"""
    for p in [None]+list(par):
        sp=[list(x) for x in spec]
        if p is not None: sp[p][2]+=1
        s=solve(sp,allowed=pair,verbose=verbose)
        if s: return s
    return None
