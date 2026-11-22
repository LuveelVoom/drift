exec(open('search.py').read().split("wsel=")[0])
NAMES={1:'A',17:'B',15:'C',11:'D',19:'E'}
spark=set(c for t in range(16,36) for c in hist[t] if 8<=c[0]<=17 and -4<=c[1]<=6)
rq_cache={}
const0=set(c for c in hist[0] if c[1]>=6)  # constellation cells (ship is at y<=4)
out=[]
for s,g in W.items():
    p=C.Pattern.from_coords(g,R); p.step(600); F=cells(p)
    Mc=[c for c in g if L[c]==13]; pa=[c for c in g if L[c]==25]
    inreg=near(pa,3)
    dur={1:66,17:219,15:49,11:91,19:71}[s]
    T=30+dur+100; T+=(4-T%4)%4
    rq=react.copy(); rq.step(T); refT=cells(rq)
    shipref=set(c for c in refT if c[0]<0)
    n=0;t0=time.time()
    for k,tr in enumerate(TR):
        Ft=[tr(x,y) for x,y in F]; Mt=[tr(x,y) for x,y in Mc]; It=set(tr(x,y) for x,y in inreg)
        offs=set()
        for (sx,sy) in spark:
            for (wx,wy) in Ft:
                for i in range(-4,5):
                    for j in range(-4,5): offs.add((sx-wx+i,sy-wy+j))
        for (ox,oy) in offs:
            Wc=set((x+ox,y+oy) for x,y in Ft)
            if Wc & hist[0] or lane_bad(Wc): continue
            if any((x+i,y+j) in const0 for x,y in Wc for i in (-1,0,1) for j in (-1,0,1)): continue
            n+=1
            Mlist=sorted(near([(x+ox,y+oy) for x,y in Mt],1)); Mbase=sum(1 for c in Mlist if c in Wc)
            comb=C.Pattern.from_coords(list(Wc|hist[0]),R); hit=False
            for t in range(T):
                comb.step(1)
                if not hit and t>14 and t%3==0 and probe(comb,Mlist)!=Mbase: hit=True
            if not hit: continue
            fin=cells(comb); exp=refT|Wc; d=fin^exp
            Ir=set((x+ox,y+oy) for x,y in It)
            dIn=sum(1 for c in d if c in Ir); dOut=len(d)-dIn
            shipok=shipref<=fin and not any(c not in shipref and c[0]<0 and -4<=c[1]<=8 for c in fin)
            constok=all((c in fin) for c in const0) and not any(c not in refT and c[1]>=5 and -2<=c[0]<=18 and c not in Wc for c in fin)
            out.append((NAMES[s],k,ox,oy,len(d),dIn,dOut,shipok,constok))
    print(NAMES[s],'cands',n,'hits',sum(1 for o in out if o[0]==NAMES[s]),round(time.time()-t0,1),flush=True)
pickle.dump(out,open('res2.pkl','wb'))
out.sort(key=lambda o:(o[6],o[4]))
for o in out[:25]: print(o)
