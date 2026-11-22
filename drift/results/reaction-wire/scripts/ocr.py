from mrle import parse
h,c=parse('wires.rle')
D={p for p,s in c.items() if s==4}
# find text lines: cluster by connected components with dilation
import itertools
seen=set();groups=[]
for p in sorted(D):
    if p in seen: continue
    st=[p];g=[];seen.add(p)
    while st:
        q=st.pop();g.append(q)
        for dx in range(-2,3):
            for dy in range(-1,2):
                r=(q[0]+dx,q[1]+dy)
                if r in D and r not in seen: seen.add(r);st.append(r)
    groups.append(g)
F={}
glyphs={}
for g in sorted(groups,key=lambda g:(min(y for x,y in g),min(x for x,y in g))):
    x0=min(x for x,y in g);x1=max(x for x,y in g);y0=min(y for x,y in g);y1=max(y for x,y in g)
    # split columns
    cols=[x for x in range(x0,x1+1) if any((x,y) in D for y in range(y0,y1+1))]
    runs=[];cur=[]
    for x in range(x0,x1+2):
        if x in cols: cur.append(x)
        elif cur: runs.append(cur);cur=[]
    out=[]
    for r in runs:
        bm='/'.join(''.join('#' if (x,y) in D else '.' for x in r) for y in range(y0,y1+1))
        out.append(bm)
    print((x0,y0,x1,y1),out)
