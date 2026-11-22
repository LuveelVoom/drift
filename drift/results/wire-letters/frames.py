import lib
TR=lib.TR
# inverse transforms
def inv(k):
    for j in range(8):
        if all(TR[j](*TR[k](x,y))==(x,y) for x,y in [(1,2),(3,-5)]): return j
INV=[inv(k) for k in range(8)]
def comp(a,b):  # T_a o T_b
    for j in range(8):
        if all(TR[j](x,y)==TR[a](*TR[b](x,y)) for x,y in [(1,2),(3,-5)]): return j
COMP=[[comp(a,b) for b in range(8)] for a in range(8)]

class Wire:
    def __init__(s,name,cells,sfun,s0,P,p):
        # sfun: axis coordinate (increasing in signal direction); chunk = cells with s0<=s<s0+P ; p: period vector (s increases by P)
        s.name=name; s.p=p; s.P=P; s.sfun=sfun; s.s0=s0
        s.chunk={c for c in cells if s0<=sfun(*c)<s0+P}
        # verify periodicity on next chunk
        nxt={c for c in cells if s0+P<=sfun(*c)<s0+2*P}
        assert nxt=={(x+p[0],y+p[1]) for x,y in s.chunk}, name
        s.base={((x-s0) if False else x, y) for x,y in s.chunk}
    def slab(s,m):  # canonical cells of slab m
        return {(x+m*s.p[0],y+m*s.p[1]) for x,y in s.chunk}
    def slabidx(s,c):
        return (s.sfun(*c)-s.s0)//s.P
    def has(s,c):
        m=s.slabidx(c); x,y=c
        return (x-m*s.p[0],y-m*s.p[1]) in s.chunk
    def urange(s):
        pass

def find_frames(W,cells,ufun,umarg=2,minrun=2):
    """frames (k,t,mlo,mhi): T_k(canonical)+t matches cells on slabs mlo..mhi (in canonical coords)"""
    us=[ufun(*c) for c in W.chunk]; ulo,uhi=min(us)-umarg,max(us)+umarg
    c0=min(W.chunk)
    out=[];seen=set()
    for k in range(8):
        T=TR[k]; Ti=TR[INV[k]]
        Tc0=T(*c0)
        for q in cells:
            t=(q[0]-Tc0[0],q[1]-Tc0[1])
            back={Ti(x-t[0],y-t[1]) for x,y in cells}
            # slab matching
            inreg={}
            for b in back:
                if ulo<=ufun(*b)<=uhi:
                    inreg.setdefault(W.slabidx(b),set()).add(b)
            good=[m for m in inreg if inreg[m]==W.slab(m)]
            if not good: continue
            good=sorted(good)
            # longest consecutive run containing slab 0? take all runs
            runs=[];a=good[0];prev=a
            for m in good[1:]+[None]:
                if m is None or m!=prev+1:
                    if prev-a+1>=minrun: runs.append((a,prev))
                    if m is not None: a=m
                if m is not None: prev=m
            for a,b in runs:
                # normalize: shift t so that... key by (k, t reduced)
                Tp=T(*W.p)
                # canonical representative: t' = t + j*Tp so that slab range shifts by -j
                key=(k,a,b,t)
                out.append((k,t,a,b))
    # dedupe equivalent frames: (k,t,a,b) ~ (k,t+j Tp,a-j,b-j)
    res=[];keys=set()
    for k,t,a,b in out:
        Tp=TR[k](*W.p)
        j=-a  # make a=0
        tt=(t[0]-j*Tp[0],t[1]-j*Tp[1])
        key=(k,tt,0,b-a)
        if key not in keys: keys.add(key); res.append(key)
    return res

def find_ports(W,cells,ufun,umarg=2,minlen=8):
    """per-s agreement. returns list of (k,t,slo,shi): T_k(canon)+t agrees with cells for canonical s in [slo,shi]
    (within tube u in [ulo-umarg,uhi+umarg]); normalized so that slo in [0,P)."""
    us=[ufun(*c) for c in W.chunk]; ulo,uhi=min(us)-umarg,max(us)+umarg
    c0=min(W.chunk)
    res={}
    for k in range(8):
        T=TR[k]; Ti=TR[INV[k]]; Tc0=T(*c0)
        for q in cells:
            t=(q[0]-Tc0[0],q[1]-Tc0[1])
            back=[Ti(x-t[0],y-t[1]) for x,y in cells]
            back=[b for b in back if ulo<=ufun(*b)<=uhi]
            bs=set(back)
            svals=set(W.sfun(*b) for b in back)
            if not svals: continue
            smin,smax=min(svals),max(svals)
            # canonical cells in tube for s in [smin-?,smax]
            bad=set()
            for b in back:
                if not W.has(b): bad.add(W.sfun(*b))
            # canonical cells missing in piece
            for m in range((smin-W.s0)//W.P-1,(smax-W.s0)//W.P+2):
                for c in W.slab(m):
                    sv=W.sfun(*c)
                    if smin<=sv<=smax and c not in bs: bad.add(sv)
            # runs of good s within [smin,smax]
            s=smin
            while s<=smax:
                if s in bad: s+=1; continue
                a=s
                while s<=smax and s not in bad: s+=1
                b=s-1
                if b-a+1>=minlen:
                    Tp=T(*W.p)
                    j=(a-W.s0)//W.P  # shift so a in [s0,s0+P)
                    tt=(t[0]+j*Tp[0],t[1]+j*Tp[1])
                    key=(k,tt,a-j*W.P,b-j*W.P)
                    res[key]=1
    # keep maximal: drop keys contained in others with same k,tt
    keys=list(res)
    out=[k for k in keys if not any(o!=k and o[0]==k[0] and o[1]==k[1] and o[2]<=k[2] and o[3]>=k[3] for o in keys)]
    return out
