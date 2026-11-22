import sys
from mrle import parse
G={'##./.#./.#./.#./###':'1','###/#.#/#.#/#.#/###':'0','.../.../.##/#../.##':'c','..#/..#/.#./#../#..':'/',
'###/..#/###/#../###':'2','..#/..#/.##/#.#/.##':'d','#.#/#.#/###/..#/..#':'4','###/..#/###/..#/###':'3',
'.../.../###/#.#/###':'o','##./#.#/##./#.#/#.#':'R','###/.#./.#./.#./.#.':'T','###/#.#/###/..#/###':'9',
'###/#../###/#.#/###':'6','###/#.#/###/#.#/###':'8','###/#../###/..#/###':'5','.#./#.#/###/#.#/#.#':'A',
'##./#.#/##./#.#/##.':'B','.##/#../#../#../.##':'C','##./#.#/#.#/#.#/##.':'D','###/#../###/#../###':'E',
'...../...../#.#.#/#.#.#/.#.#.':'w'}
h,c=parse(sys.argv[1])
D={p for p,s in c.items() if s==4}
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
for g in sorted(groups,key=lambda g:(min(y for x,y in g),min(x for x,y in g))):
    x0=min(x for x,y in g);x1=max(x for x,y in g);y0=min(y for x,y in g);y1=max(y for x,y in g)
    cols=[x for x in range(x0,x1+1) if any((x,y) in D for y in range(y0,y1+1))]
    runs=[];cur=[]
    for x in range(x0,x1+2):
        if x in cols: cur.append(x)
        elif cur: runs.append(cur);cur=[]
    s=''
    for r in runs:
        bm='/'.join(''.join('#' if (x,y) in D else '.' for x in r) for y in range(y0,y1+1))
        s+=G.get(bm,'?')
    print((x0,y0,x1,y1),s)
