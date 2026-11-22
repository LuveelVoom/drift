# Generic drift config writer. Coordinates are (x, y) cells; the grid covers bounds.
def near(A,d): return set((x+i,y+j) for x,y in A for i in range(-d,d+1) for j in range(-d,d+1))
def write(path, header, bg, spark, unknown, nocount, bounds, opts, kill=frozenset(), mustreach=frozenset()):
    X0,X1,Y0,Y1=bounds
    rows=[]
    for y in range(Y0,Y1+1):
        r=''
        for x in range(X0,X1+1):
            c=(x,y)
            if c in spark and c in bg: r+='D'
            elif c in spark: r+='C'
            elif c in bg: r+='A'
            elif c in unknown: r+='.'
            else: r+='B'
        rows.append(r)
    def enc(row):
        out='';i=0
        while i<len(row):
            j=i
            while j<len(row) and row[j]==row[i]: j+=1
            n=j-i; out+=(str(n) if n>1 else '')+row[i]; i=j
        return out
    body='$'.join(enc(r) for r in rows)+'!'
    lines=[body[i:i+70] for i in range(0,len(body),70)]
    regs=[]
    for key,cs in (('no-count',nocount),('must-reach',mustreach)):
      for y in sorted(set(y for x,y in cs)):
        xs=sorted(x for x,yy in cs if yy==y); run=[xs[0]]
        for x in xs[1:]+[None]:
            if x is not None and x==run[-1]+1: run.append(x); continue
            regs.append(f"{key} = l {y-Y0} {run[0]-X0} {y-Y0} {run[-1]-X0}")
            if x is not None: run=[x]
    cfg='\n'.join('# '+l for l in header.splitlines())+'\n'+''.join(f"{k} = {v}\n" for k,v in opts.items())
    cfg+='\n'.join(regs)+'\npattern:\n'+f"x = {X1-X0+1}, y = {Y1-Y0+1}, rule = LifeHistory\n"+'\n'.join(lines)+'\n'
    open(path,'w').write(cfg)
