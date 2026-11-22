# mkconn.py WIRE OUTDIR [D]  -> writes one drift config per (orientation, placement) and a manifest
exec(open('wirefit.py').read().split("base=C.parse_rle")[0])
import gencfg, json
wname=sys.argv[1]; outdir=sys.argv[2]; DIST=int(sys.argv[3]) if len(sys.argv)>3 else 5
react=C.parse_rle(open('reac2.rle').read())
H=[];q=react.copy()
for t in range(60): H.append(cells(q)); q.step(1)
g0=H[0]; ship=set(p for p in g0 if p[1]<=4); const=g0-ship
spk=set(p for t in range(16,36) for p in H[t] if p not in const and p[0]>=6)   # spark cells near the box
def allowed(x,y):
    if x<=4 and -3<=y<=7: return False          # ship's past / outgoing lane
    return (x>=11) or (y<=-2 and x>=4) or (x>=12 and y>=5)
def dist(c,S): return min(max(abs(c[0]-a),abs(c[1]-b)) for a,b in S)
Wd={n:(F,Mc) for n,F,Mc,_ in WIRES}
F,Mc=Wd[wname]
# input-end cells of the idle wire: state-25 cells of the drawn wire (or the converter part for A+domino)
if wname=='A+domino':
    h2,c2=parse('ws.rle'); PA=set(p for p,s in c2.items() if 160<=p[0]<215 and 125<=p[1]<180 and s==21)
else:
    s={'A':1,'B':17,'C':15,'D':11,'E':19}[wname]; PA=set(p for p in W[s] if L[p]==25)
cx=lambda S:(sum(x for x,y in S)/len(S),sum(y for x,y in S)/len(S))
man=[]
for k,tr in enumerate(TR):
    Ft=set(tr(*p) for p in F); Pt=set(tr(*p) for p in PA); Mt=set(tr(*p) for p in Mc)
    a=cx(Pt); b=cx(Mt); dx,dy=b[0]-a[0],b[1]-a[1]
    if not (dx>0 and dy<0): continue             # wire must run NE, away from lane and constellation
    # candidate placements: input end at Chebyshev distance DIST from the spark, three directions
    cands={}
    for ox in range(-80,80):
        pass
    # choose by target point for the input end's nearest cell: E, NE, N of the spark
    for lab,(tx,ty) in {'E':(10+DIST,2),'NE':(10+DIST-1,1-DIST+1),'N':(8,1-DIST)}.items():
        best=None
        for p in Pt:
            ox,oy=tx-p[0],ty-p[1]
            Wc=set((x+ox,y+oy) for x,y in Ft)
            if Wc&near(g0,2): continue
            if any(not allowed(x,y) for x,y in Wc): continue
            Pc=set((x+ox,y+oy) for x,y in Pt)
            d=dist_min=min(max(abs(a1-b1),abs(a2-b2)) for a1,a2 in Pc for b1,b2 in spk)
            if d!=DIST: continue
            best=(ox,oy); break
        if best is None: print(wname,k,lab,'no placement'); continue
        ox,oy=best
        Wc=set((x+ox,y+oy) for x,y in Ft); Pc=set((x+ox,y+oy) for x,y in Pt); Mcc=set((x+ox,y+oy) for x,y in Mt)
        unk=set(c for c in near(spk,DIST+2) if allowed(*c) and c not in Wc and c not in g0 and dist(c,spk)<=DIST+2)
        nc=set(c for c in near(Wc,1) if dist(c,Pc)>10)|set((x,y) for x in range(-30,-2) for y in range(-3,8))
        allc=Wc|g0|unk
        bounds=(min(-30,min(x for x,y in allc)-3),max(x for x,y in allc)+3,min(y for x,y in allc)-3,max(17,max(y for x,y in allc)+3))
        name=f"conn-{wname.replace('+','')}-o{k}-{lab}-d{DIST}"
        gencfg.write(f"{outdir}/{name}.cfg",
          f"Reaction -> wire {wname} connector search (orientation {k}, input end {lab} of the spark, distance {DIST}).\n"
          f"Escape = reaction and constellation back, ship leaving west, signal on the no-count part of the wire.",
          const|Wc, ship, unk, nc, bounds,
          {'rule':'B3/S23-a5','max-changed':24,'size':'20x22','margin':0,'max-gen':120,'escape':'true',
           'skip':'oscillator, stable, maxgen','per-rotor':0,'max-results':0},
          mustreach=set(c for c in Wc if dist(c,Pc)>10))
        man.append(dict(name=name,wire=wname,k=k,ox=ox,oy=oy,bounds=bounds,unknown=len(unk),M=sorted(Mcc),W=sorted(Wc)))
        print(name,'offset',(ox,oy),'unknown cells',len(unk))
json.dump(man,open(f"{outdir}/manifest-{wname.replace('+','')}-d{DIST}.json",'w'))
