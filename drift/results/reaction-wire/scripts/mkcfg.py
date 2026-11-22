import sys
sys.path.insert(0,'.')
from mrle import parse
h,c=parse('reaction.rle')
live={p for p,s in c.items() if s==1}
ship={p for p in live if p[1]<=4}; const=live-ship
AREA=sys.argv[2]; TIGHT=int(sys.argv[3]) if len(sys.argv)>3 else 1
X0,X1,Y0,Y1=(-30,60,-50,18) if AREA=='wire' else (-30,33,-19,16)          # drawn grid (x=col, y=row in pattern coords)
AREA=sys.argv[2]; TIGHT=int(sys.argv[3]) if len(sys.argv)>3 else 1
def unknown(x,y):
    if AREA=='tight':
        return (9<=x<=14 and -2<=y<=7) if TIGHT==1 else ((9<=x<=16 and -3<=y<=7) if TIGHT==3 else (9<=x<=18 and -5<=y<=8))
    if AREA=='wire':
        if x<=4 and -3<=y<=7: return False
        return x<=57 and y>=-47 and y<=15 and ((x>=11) or (y<=-2 and x>=4) or (x>=12 and y>=5))
    if AREA=='control':
        return (4<=x<=16 and -10<=y<=-2) or (7<=x<=14 and 6<=y<=13)
    if AREA=='small':
        return (4<=x<=16 and -10<=y<=-2) or (11<=x<=16 and -1<=y<=4) or (12<=x<=16 and 5<=y<=8)
    if AREA=='large':
        return (4<=x<=26 and -16<=y<=-2) or (11<=x<=26 and -1<=y<=4) or (12<=x<=26 and 5<=y<=10)
    return (11<=x<=28 and -14<=y<=4) or (16<=x<=28 and 5<=y<=10)
rows=[]
for y in range(Y0,Y1+1):
    r=''
    for x in range(X0,X1+1):
        if (x,y) in const and not (AREA=='control' and unknown(x,y)): r+='A'
        elif (x,y) in ship: r+='C'
        elif unknown(x,y): r+='.'
        else: r+='B'
    rows.append(r)
# RLE encode
def enc(row):
    out='';i=0
    while i<len(row):
        j=i
        while j<len(row) and row[j]==row[i]: j+=1
        n=j-i; out+=(str(n) if n>1 else '')+row[i]; i=j
    return out
body='$'.join(enc(r) for r in rows)+'!'
lines=[body[i:i+70] for i in range(0,len(body),70)]
# regions in (row, col) relative to grid top-left
R=lambda y,x:(y-Y0,x-X0)
def rect(y0,x0,y1,x1): a=R(y0,x0); b=R(y1,x1); return f"r {a[0]} {a[1]} {b[0]} {b[1]}"
cfg=f"""# The c/4 ship + constellation reaction (B3/S23-a5) whose spark should feed a wire.
# Background = constellation, gen-0 'spark' = the ship. Unknown cells only NE of the
# spark (x 11..28, y -14..4 and x 16..28, y 5..10 in the reaction's own coords);
# results must change a cell in the clear band just outside that area, i.e. throw an
# output spark into open space where a wire input could sit.
rule = B3/S23-a5
max-changed = 24
size = 20x22
margin = 0
max-gen = 100
escape = true
skip = oscillator, stable, maxgen
per-rotor = 0
no-count = {rect(-3,X0,7,-3)}
max-results = 0
pattern:
x = {X1-X0+1}, y = {Y1-Y0+1}, rule = LifeHistory
""" + '\n'.join(lines)+'\n'
open(sys.argv[1],'w').write(cfg)
print(cfg[:900])
