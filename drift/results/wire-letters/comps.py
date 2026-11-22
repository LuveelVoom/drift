from mrle import parse
from collections import Counter
h,c=parse('ws.rle')
L={p:s for p,s in c.items() if s%2==1}
seen=set();comps=[]
for p in sorted(L):
    if p in seen: continue
    st=[p];g=[];seen.add(p)
    while st:
        q=st.pop();g.append(q)
        for dx in range(-4,5):
            for dy in range(-4,5):
                r=(q[0]+dx,q[1]+dy)
                if r in L and r not in seen: seen.add(r);st.append(r)
    comps.append(g)
comps.sort(key=lambda g:(min(y for x,y in g)//60,min(x for x,y in g)))
import pickle
out=[]
for i,g in enumerate(comps):
    cnt=Counter(L[p] for p in g)
    bb=(min(x for x,y in g),min(y for x,y in g),max(x for x,y in g),max(y for x,y in g))
    print(i,len(g),bb,dict(cnt))
    out.append({p:L[p] for p in g})
pickle.dump(out,open('comps.pkl','wb'))
