exec(open('wirefit.py').read().split("base=C.parse_rle")[0])
import gencfg
exec(open('sparkdist.py').read().split("def weak_spark")[0])
h,c=parse('ws.rle')
sub=set(p for p,s in c.items() if 295<=p[0]<345 and 120<=p[1]<180 and s%2==1)
q=C.Pattern.from_coords(list(sub),R); q.step(300); F=cells(q)
q=C.Pattern.from_coords(list(sub),R); snaps=[sub]
for t in range(80): q.step(1); snaps.append(cells(q))
# known clean output cells of ws2: (325,130),(325,131),(326,131), first at gen 74; draw signal at gen 74-12
t0=62; st=snaps[t0]; on0=st-F; off0=F-st
print('signal at gen',t0,'diff cells',len(on0),len(off0), 'bbox', min(x for x,y in on0|off0),max(x for x,y in on0|off0),min(y for x,y in on0|off0),max(y for x,y in on0|off0))
out=[(325,130),(325,131),(326,131)]
blank=set(p for p in F if min(max(abs(p[0]-a),abs(p[1]-b)) for a,b in out)<=3)   # pink-piece cells near the output
unk=near(blank,1)-(F-blank)
allc=F|unk
b=(min(x for x,y in allc)-3,max(x for x,y in allc)+3,min(y for x,y in allc)-3,max(y for x,y in allc)+3)
gencfg.write(sys.argv[1],"Positive control: ws2 (wA -> weak spark) with the spark piece's cells within 3 of the known\nclean output blanked. drift must rebuild a fizzle with a clean output spark.",
 (F-blank)|off0, on0|off0, unk, set(), b,
 {'rule':'B3/S23-a5','max-changed':12,'size':'8x8','margin':0,'max-gen':80,'skip':'oscillator, stable, maxgen','output-dist':10,'per-rotor':0,'max-results':0})
print('blanked',len(blank),'unknown',len(unk))
