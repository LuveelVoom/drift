# brute-force cross-check: small still lifes fully inside the rw3 unknown area
import sys; sys.path.insert(0, "/Users/leo/Desktop/Life tools/Vibecoded life tools/casim")
import casim as C
R='B3/S23-a5'
def cells(p): return set(map(tuple,p.coords()))
SL={'block':'2o$2o!','beehive':'b2o$o2bo$b2o!','loaf':'b2o$o2bo$bobo$2bo!','boat':'2o$obo$bo!',
    'tub':'bo$obo$bo!','ship':'2o$obo$b2o!','pond':'b2o$o2bo$o2bo$b2o!','aircraft carrier':'2o$o2bo$2b2o!',
    'snake':'2obo$ob2o!','barge':'bo$obo$bobo$2bo!','long boat':'2o$obo$bobo$2bo!'}
def unknown(x,y):
    return (4<=x<=16 and -10<=y<=-2) or (11<=x<=16 and -1<=y<=4) or (12<=x<=16 and 5<=y<=8)
react=C.parse_rle(open('reac2.rle').read()); g0=cells(react)
ref=[];q=react.copy()
for t in range(121): ref.append(cells(q)); q.step(1)
TR=[lambda x,y:(x,y),lambda x,y:(-x,y),lambda x,y:(x,-y),lambda x,y:(-x,-y),lambda x,y:(y,x),lambda x,y:(-y,x),lambda x,y:(y,-x),lambda x,y:(-y,-x)]
nint=0;found=[]
for name,rle in SL.items():
    base=cells(C.parse_rle('x=0,y=0,rule=%s\n%s'%(R,rle)))
    t=C.Pattern.from_coords(list(base),R); t.step(1)
    if cells(t)!=base: print("not stable:",name); continue
    orients=set()
    for tr in TR:
        s=[tr(x,y) for x,y in base]; mx=min(a for a,b in s); my=min(b for a,b in s)
        orients.add(frozenset((a-mx,b-my) for a,b in s))
    for o in orients:
        for ox in range(-2,20):
            for oy in range(-12,10):
                S=set((a+ox,b+oy) for a,b in o)
                if not all(unknown(*c) for c in S): continue
                p=C.Pattern.from_coords(list(S|g0),R); inter=False
                for t in range(1,121):
                    p.step(1)
                    if not inter and cells(p)!=(ref[t]|S): inter=True
                if inter:
                    nint+=1
                    if cells(p)==(ref[120]|S): found.append((name,sorted(S)))
print('interacting placements',nint,'clean (escape-type) ones',len(found)); print(found[:10])
