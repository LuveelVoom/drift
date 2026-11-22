import cad
def boxes(s):
    c,info=cad.build(s,geom=True); B=[]
    for n,g,d in info['placed']:
        cs=cad.PIECES[n].cells; X=[x for x,y in cs]; Y=[y for x,y in cs]
        pts=[cad.xf(g,d,cc) for cc in ((min(X),min(Y)),(max(X),max(Y)),(min(X),max(Y)),(max(X),min(Y)))]
        # rotate 180 as final output
        pts=[(-x,-y) for x,y in pts]
        B.append((min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)))
    x0=min(b[0] for b in B);y0=min(b[1] for b in B);x1=max(b[2] for b in B);y1=max(b[3] for b in B)
    return (x1-x0+1,y1-y0+1),[((b[0]+b[2])/2-x0,(b[1]+b[3])/2-y0) for b in B]
