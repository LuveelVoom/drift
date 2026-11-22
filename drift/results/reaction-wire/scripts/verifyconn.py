# verifyconn.py MANIFEST.json DIR : finish.py-completed escapes -> full simulation check
exec(open('verify.py').read())
import json
from collections import Counter
man=json.load(open(sys.argv[1])); D=sys.argv[2]
react=C.parse_rle(open('reac2.rle').read()); g0r=cells(react)
ship=set(p for p in g0r if p[1]<=4); const=g0r-ship
rq=react.copy(); rq.step(400); ship400=set(p for p in cells(rq) if p[0]<-20)
for m in man:
    fp=f"{D}/{m['name']}-finished.txt"
    try: esc=finished_escapes(fp)
    except FileNotFoundError: print(m['name'],'no finished file'); continue
    print(m['name'],'escapes:',len(esc))
    Wc=set(map(tuple,m['W'])); Mc=set(map(tuple,m['M']))
    for title,p in esc:
        S=set(map(tuple,p.coords()))
        (dx,dy),n=Counter((a-x,b-y) for x,y in S for a,b in (const|Wc)).most_common(1)[0]
        S=set((x+dx,y+dy) for x,y in S)
        ok_align = const<=S and Wc<=S and ship<=S
        q=C.Pattern.from_coords(list(S),R); Ml=sorted(near(Mc,1)); mb=sum(1 for x in Ml if x in S); hit=None
        for t in range(400):
            q.step(1)
            if hit is None and probe(q,Ml)!=mb: hit=t
        fin=cells(q)
        still=S-ship
        restored = set(c for c in fin if c[0]>=-20)==still
        shipok = set(c for c in fin if c[0]<-20)==ship400
        print('  ',title[:60],'| aligned',ok_align,'| signal at far end gen',hit,'| restored',restored,'| ship ok',shipok)
        if hit and restored and shipok:
            out=f"{D}/{m['name']}-WORKS-{len(S)}.rle"
            xs=[x for x,y in S]; ys=[y for x,y in S]
            P=C.Pattern.from_coords(sorted(S),R); open(out,'w').write(P.to_rle()); print('   WORKS ->',out)
