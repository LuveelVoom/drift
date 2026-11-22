import sys; sys.path.insert(0, "/Users/leo/Desktop/Life tools/Vibecoded life tools/casim")
import casim as C
from mrle import parse
R='B3/S23-a5'
h,c=parse('wires.rle')
L={p:s for p,s in c.items() if s%2==1}
seen=set();comps=[]
for p in sorted(L):
    if p in seen: continue
    st=[p];g=[];seen.add(p)
    while st:
        q=st.pop();g.append(q)
        for dx in range(-3,4):
            for dy in range(-3,4):
                r=(q[0]+dx,q[1]+dy)
                if r in L and r not in seen: seen.add(r);st.append(r)
    comps.append(g)
from collections import Counter
W={}
for g in comps:
    cnt=Counter(L[p] for p in g)
    x0=min(x for x,y in g);y0=min(y for x,y in g)
    print(len(g),cnt,(x0,y0,max(x for x,y in g),max(y for x,y in g)))
    main=[s for s in cnt if s not in (1,13,25)] or [1]
    if len(g)>10: W[main[0]]=g
import pickle; pickle.dump((L,W),open('wires.pkl','wb'))
for s,g in W.items():
    p=C.Pattern.from_coords(g,R)
    q=p.copy(); 
    res=p.period(400)
    print(s,res)
