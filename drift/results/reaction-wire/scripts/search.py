import sys,pickle,time; sys.path.insert(0, "/Users/leo/Desktop/Life tools/Vibecoded life tools/casim")
import casim as C, numpy as np
R='B3/S23-a5'
L,W=pickle.load(open('wires.pkl','rb'))
NAMES={1:'A',17:'B',15:'C',11:'D',19:'E'}
react=C.parse_rle(open('reac2.rle').read())
def cells(p): return set(map(tuple,p.coords()))
# reaction history
hist=[];q=react.copy()
for t in range(0,41): hist.append(cells(q)); q.step(1)
early=set().union(*hist[:16])
spark=set(c for t in range(21,31) for c in hist[t] if 8<=c[0]<=16 and -3<=c[1]<=6)
TR=[lambda x,y:(x,y),lambda x,y:(-x,y),lambda x,y:(x,-y),lambda x,y:(-x,-y),
    lambda x,y:(y,x),lambda x,y:(-y,x),lambda x,y:(y,-x),lambda x,y:(-y,-x)]
def near(A,d):
    return set((x+i,y+j) for x,y in A for i in range(-d,d+1) for j in range(-d,d+1))
early2=near(early,2)
def lane_bad(Wc):
    return any(x<=9 and -2<=y<=6 for x,y in Wc)
def probe(p,lst):
    a=p.cells; x0=p.x0; y0=p.y0; H,Wd=a.shape; n=0
    for x,y in lst:
        i=y-y0; j=x-x0
        if 0<=i<H and 0<=j<Wd and a[i,j]: n+=1
    return n
def run_case(name,Fw,Mreg,T,refT,shipreg):
    pass
wsel=sys.argv[1:] or list(NAMES.values())
results=[]
for s,g in W.items():
    if NAMES[s] not in wsel: continue
    p=C.Pattern.from_coords(g,R); p.step(600); F=cells(p)
    Mc=[c for c in g if L[c]==13]
    # reference: duration
    dur={1:66,17:219,15:49,11:91,19:71}[s]
    T=30+dur+80; T+= (4-T%4)%4
    rq=react.copy(); rq.step(T); refT=cells(rq)
    ncand=0;t0=time.time()
    for k,tr in enumerate(TR):
        Ft=[tr(x,y) for x,y in F]; Mt=[tr(x,y) for x,y in Mc]
        offs=set()
        for (sx,sy) in spark:
            for (wx,wy) in Ft:
                for i in range(-3,4):
                    for j in range(-3,4):
                        offs.add((sx-wx+i,sy-wy+j))
        for (ox,oy) in offs:
            Wc=set((x+ox,y+oy) for x,y in Ft)
            if Wc & early2 or lane_bad(Wc): continue
            ncand+=1
            Mlist=sorted(near([(x+ox,y+oy) for x,y in Mt],1)); Mbase=sum(1 for c in Mlist if c in Wc)
            comb=C.Pattern.from_coords(list(Wc|hist[0]),R)
            hit=False
            for t in range(T):
                comb.step(1)
                if not hit and t>20 and t%3==0:
                    if probe(comb,Mlist)!=Mbase: hit=True
            fin=cells(comb)
            exact= fin==(refT|Wc)
            # ship check: reference ship cells (those of refT left of x<0)
            shipref=set(c for c in refT if c[0]<0)
            shipok= all(c in fin for c in shipref) and not any((c not in shipref) and c[0]<0 and -4<=c[1]<=8 for c in fin)
            if hit or exact and False:
                results.append((NAMES[s],k,ox,oy,hit,exact,shipok))
                print(NAMES[s],k,(ox,oy),'signal' if hit else '-', 'EXACT' if exact else 'diff', 'shipOK' if shipok else 'shipBAD',flush=True)
    print('wire',NAMES[s],'candidates',ncand,'time',round(time.time()-t0,1),flush=True)
pickle.dump(results,open('res_%s.pkl'%''.join(wsel),'wb'))
