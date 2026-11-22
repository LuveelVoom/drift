import pickle,lib,draw
L={}
for n in 'DRIFT': L[n]=pickle.load(open('final_%s.pkl'%n,'rb'))[n]
def norm(cs):
    cs={(-x,-y) for x,y in cs}
    return cs
x=0; idle=set(); sig=set(); parts={}
H=max(max(y for _,y in norm(L[n][1]))-min(y for _,y in norm(L[n][1])) for n in 'DRIFT')
for n in 'DRIFT':
    s,c,sc,r=L[n]
    c=norm(c); sc=norm(sc)
    x0=min(a for a,b in c); y1=max(b for a,b in c)
    sh=lambda S:{(a-x0+x,b-y1+H) for a,b in S}
    idle|=sh(c); sig|=sh(sc); parts[n]=sh(sc)
    w=max(a for a,b in c)-x0+1; print(n,'w',w,'h',y1-min(b for a,b in c)+1,'period',r['period'])
    x+=w+40
p=lib.pat(idle); q=p.copy(); q.step(1); print('idle still',set(q.coords())==idle)
# interaction check: combined vs separate after 3000 gens
G=3000
pc=lib.pat(sig); pc.step(G); comb=set(pc.coords())
sep=set()
for n in 'DRIFT':
    pp=lib.pat(parts[n]); pp.step(G); sep|=set(pp.coords())
print('combined==separate at',G,comb==sep)
open('DRIFT.rle','w').write(lib.pat(sig).to_rle())
open('DRIFT-idle.rle','w').write(lib.pat(idle).to_rle())
print(draw.png([(idle,(255,255,255)),(sig^idle,(255,60,60))],'DRIFT.png',1,pad=10))
