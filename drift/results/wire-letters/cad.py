import lib,frames as F,pickle
TR=lib.TR; INV=F.INV; COMP=F.COMP
SA=lib.idle(0); SD=lib.idle(9)
WA=F.Wire('A',SA,lambda x,y:x-y,40,20,(10,-10))
WD=F.Wire('D',SD,lambda x,y:-y,-78,20,(0,-20))
WA.u=lambda x,y:x+y; WD.u=lambda x,y:x
for W in (WA,WD):
    us=[W.u(*c) for c in W.chunk]; W.ulo,W.uhi=min(us),max(us)
PORTS=pickle.load(open('ports.pkl','rb'))
DET=[1,1,1,1,-1,-1,-1,-1]
class Piece:
    def __init__(s,name,ci,inW,inks,outW,outk):
        s.name=name; s.cells=lib.idle(ci)
        Ap,Dp=PORTS[ci]
        pl={'A':Ap,'D':Dp}
        s.inW={'A':WA,'D':WD}[inW]; s.outW={'A':WA,'D':WD}[outW]
        s.ins=[p for p in pl[inW] if p[0] in inks]
        s.out=[p for p in pl[outW] if p[0]==outk][0]
        assert len(s.ins)==2,(name,s.ins)
PIECES={
 'AD':Piece('AD',25,'A',(0,7),'D',0),
 'DA':Piece('DA',26,'D',(0,4),'A',0),
 'T1':Piece('T1',32,'A',(0,7),'A',3),
 'T2':Piece('T2',33,'A',(0,7),'A',3),
 'T3':Piece('T3',34,'A',(0,7),'A',3),
}
def xf(g,d,c): x,y=TR[g](*c); return (x+d[0],y+d[1])
def tocan(K,t,c): return TR[INV[K]](c[0]-t[0],c[1]-t[1])

def build(spec,close=True,verbose=False,geom=False):
    """spec: list of (piecename, turn 'L'/'R', extra periods before this piece).
    returns cells, info. First piece placed at identity w/ chosen mirror by its turn."""
    placed=[]  # (piece, g, d, outframe(K,t,a,b))
    cellsets=[]
    fill=set()
    junc=[]
    def native(pc):  # native turn direction
        return {'AD':'L','DA':'R','T1':'L','T2':'L','T3':'L'}[pc]
    g0=0 if spec[0][1]==native(spec[0][0]) else 4
    pc=PIECES[spec[0][0]]
    placed.append([pc,g0,(0,0)])
    for idx in range(1,len(spec)+(1 if close else 0)):
        name,turn,extra=spec[idx%len(spec)]
        X,gX,dX=placed[-1]
        k,t,a,b=X.out
        K=COMP[gX][k]; tX=xf(gX,dX,t); W=X.outW
        Y=PIECES[name]; assert Y.inW is W,(X.name,name)
        want_det=1 if turn==native(name) else -1
        opts=[]
        for k2,t2,a2,b2 in Y.ins:
            g=COMP[K][INV[k2]]
            if DET[g]!=want_det: continue
            # minimal j
            Kp=TR[K](*W.p)
            for j in range(-10,40):
                ya,yb=a2+j*W.P,b2+j*W.P
                cx=max(a+3,min(b-3,ya+3)); cy=max(cx,ya+3)
                if cx<=b-3 and cy<=yb-3:
                    opts.append((j,g,k2,t2,cx,cy,a2,b2)); break
        j,g,k2,t2,cx,cy,a2,b2=min(opts)
        j0=j; j=j+extra
        ya,yb=a2+j*W.P,b2+j*W.P
        if extra>0: cy=ya+3
        Kp=TR[K](*W.p)
        Tt2=TR[g](*t2)
        d=(tX[0]+j*Kp[0]-Tt2[0],tX[1]+j*Kp[1]-Tt2[1])
        junc.append(dict(K=K,tX=tX,W=W,cx=cx,cy=cy,b=b,ya=ya,j=j,j0=j0,iX=len(placed)-1))
        if idx<len(spec): placed.append([Y,g,d])
        else:
            closing=(g,d)
    if geom:
        return None,dict(placed=[(p.name,g,d) for p,g,d in placed],junc=junc,closing=closing if close else None)
    # cells
    cells=[{xf(g,d,c) for c in pc.cells} for pc,g,d in placed]
    for jn in junc:
        K,tX,W=jn['K'],jn['tX'],jn['W']
        iX=jn['iX']; iY=(iX+1)%len(placed)
        def su(c):
            cc=tocan(K,tX,c); return W.sfun(*cc),W.u(*cc)
        def rm(cs,pred):
            return {c for c in cs if not pred(*su(c))}
        cx,cy,b,ya=jn['cx'],jn['cy'],jn['b'],jn['ya']
        cells[iX]=rm(cells[iX],lambda s,u:(s>=cx and W.ulo-2<=u<=W.uhi+2) or (cx+4<s<=b+30 and W.ulo-8<=u<=W.uhi+8))
        cells[iY]=rm(cells[iY],lambda s,u:(s<cy and W.ulo-2<=u<=W.uhi+2) or (ya-30<=s<cy-4 and W.ulo-8<=u<=W.uhi+8))
        mlo=(cx-W.s0)//W.P-1; mhi=(cy-W.s0)//W.P+1
        for m in range(mlo,mhi+1):
            for c in W.slab(m):
                if cx<=W.sfun(*c)<cy: fill.add(xf(K,tX,c))
    allc=set().union(*cells)|fill
    info=dict(placed=[(p.name,g,d) for p,g,d in placed],junc=junc)
    if close: info['closing']=closing
    return allc,info
