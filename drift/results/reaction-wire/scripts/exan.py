exec(open('wirefit.py').read().split("base=C.parse_rle")[0])
p=C.parse_rle(open('ex.rle').read()); S=set(map(tuple,p.coords()))
react=C.parse_rle(open('reac2.rle').read()); R0=cells(react)
for a,b in ((0,28),(28,58),(58,90)):
    sub=set(c for c in S if a<=c[0]<b)
    # align reaction: find shift so that R0 constellation fits
    best=None
    for dx in range(-5,40):
        for dy in range(-5,15):
            sh=set((x+dx,y+dy) for x,y in R0)
            if sh<=sub: best=(dx,dy)
    dx,dy=best; stub=sub-set((x+dx,y+dy) for x,y in R0)
    stubR=set((x-dx,y-dy) for x,y in stub)   # in reaction coords
    q=C.Pattern.from_coords(list(sub),R); q.step(200); fin=cells(q)
    stillpart=set(c for c in fin if c[0]>=a-2+0 and c[1]>=dy+5) # everything but the ship far west
    ship_gone=set(c for c in fin if c[0]<a)
    print('example at x',a,'reaction shift',best,'stub cells',len(stub),'stub bbox (reaction coords)',
          min(x for x,y in stubR),max(x for x,y in stubR),min(y for x,y in stubR),max(y for x,y in stubR))
    shipcells=set((x+dx,y+dy) for x,y in R0 if y<=4)
    print('  restored (stub+constellation exact):', (fin-ship_gone)==(sub-shipcells))
    # does the stub match part of an idle wire?
    for name,F,Mc,dur in WIRES:
        bestov=0
        for k,tr in enumerate(TR):
            Ft=set(tr(x,y) for x,y in F)
            from collections import Counter
            cnt=Counter((sx-fx,sy-fy) for sx,sy in stub for fx,fy in Ft)
            o,n=cnt.most_common(1)[0]
            if n>bestov: bestov=n;bk=(k,o)
        print('   overlap with wire',name,bestov,'/',len(stub),bk)
    open('stub_%d.txt'%a,'w').write(repr(sorted(stubR)))
