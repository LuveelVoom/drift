# usage: wirefit.py PATTERN.rle   (reaction + catalyst, plain 2-state RLE, same coords as reac2.rle)
# Tries every wire (A-E idle, plus wA with the domino input converter) in 8 orientations at
# every offset near the new output spark; success = signal reaches the wire's far end and
# everything (constellation, catalyst, wire) is exactly restored with the c/4 ship escaping.
import sys,pickle,time; sys.path.insert(0, "/Users/leo/Desktop/Life tools/Vibecoded life tools/casim")
import casim as C
from mrle import parse
R='B3/S23-a5'
def cells(p): return set(map(tuple,p.coords()))
def near(A,d): return set((x+i,y+j) for x,y in A for i in range(-d,d+1) for j in range(-d,d+1))
def probe(p,lst):
    a=p.cells; x0=p.x0; y0=p.y0; H,Wd=a.shape; n=0
    for x,y in lst:
        i=y-y0; j=x-x0
        if 0<=i<H and 0<=j<Wd and a[i,j]: n+=1
    return n
TR=[lambda x,y:(x,y),lambda x,y:(-x,y),lambda x,y:(x,-y),lambda x,y:(-x,-y),
    lambda x,y:(y,x),lambda x,y:(-y,x),lambda x,y:(y,-x),lambda x,y:(-y,-x)]
L,W=pickle.load(open('wires.pkl','rb'))
NAMES={1:'A',17:'B',15:'C',11:'D',19:'E'}
WIRES=[]
for s,g in W.items():
    p=C.Pattern.from_coords(g,R); p.step(600)
    WIRES.append((NAMES[s],cells(p),[q for q in g if L[q]==13],{1:66,17:219,15:49,11:91,19:71}[s]))
h,c=parse('ws.rle')
sub={p:s for p,s in c.items() if 160<=p[0]<215 and 125<=p[1]<180 and s%2==1}
WIRES.append(('A+domino',set(p for p,s in sub.items() if s!=25),[p for p,s in sub.items() if s==13],70))
base=C.parse_rle(open(sys.argv[1]).read())
g0=cells(base)
hist=[];q=base.copy()
for t in range(60): hist.append(cells(q)); q.step(1)
still=hist[0]-set(p for p in hist[0] if p[1]<=4 and p[0]<=3)   # minus the incoming ship
# output spark = cells alive at gen>=16 that are not in the still background and not in the lane
spark=set(p for t in range(16,60) for p in hist[t] if p not in still and not (p[0]<=7 and -3<=p[1]<=7))
lane=lambda Wc:any(x<=9 and -2<=y<=6 for x,y in Wc)
found=0
for name,F,Mc,dur in WIRES:
    T=40+dur+100; T+=(4-T%4)%4
    rq=base.copy(); rq.step(T); refT=cells(rq)
    for k,tr in enumerate(TR):
        Ft=[tr(x,y) for x,y in F]; Mt=[tr(x,y) for x,y in Mc]
        offs=set((sx-wx+i,sy-wy+j) for (sx,sy) in spark for (wx,wy) in Ft for i in range(-3,4) for j in range(-3,4))
        for ox,oy in offs:
            Wc=set((x+ox,y+oy) for x,y in Ft)
            if Wc&near(g0,1) or lane(Wc): continue
            Ml=sorted(near([(x+ox,y+oy) for x,y in Mt],1)); mb=sum(1 for x in Ml if x in Wc)
            cb=C.Pattern.from_coords(list(Wc|g0),R); hit=False
            for t in range(T):
                cb.step(1)
                if not hit and t>14 and t%3==0 and probe(cb,Ml)!=mb: hit=True
            if hit and cells(cb)==(refT|Wc):
                found+=1; print('WORKS',name,'orient',k,'offset',(ox,oy),flush=True)
print(sys.argv[1],'working placements:',found)
