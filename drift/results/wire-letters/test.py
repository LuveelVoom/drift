import lib,cad,sig
TR=lib.TR
def inject(cells,info,ji,g=24):
    """put signal in junction ji filler (must be wA)"""
    jn=info['junc'][ji]; W=jn['W']; assert W is cad.WA
    D=sig.sigA(g)
    s=[W.sfun(*c) for c in D]; mid=(jn['cx']+jn['cy'])//2
    m=round((mid-(min(s)+max(s))/2)/W.P)
    out=set(cells)
    for c in D:
        cc=(c[0]+m*W.p[0],c[1]+m*W.p[1]); out^={cad.xf(jn['K'],jn['tX'],cc)}
    return out
def check(cells,info,ji,maxp=4000):
    p=lib.pat(cells); q=p.copy(); q.step(1)
    still=set(q.coords())==cells
    s=inject(cells,info,ji)
    ps=lib.pat(s)
    r=ps.period(maxp)
    return still,r
if __name__=='__main__':
    for e in range(0,3):
        spec=[('T1','L',e)]*4
        c,info=cad.build(spec)
        print(e,info['closing'],[ (j['j0'],j['j']) for j in info['junc']])
