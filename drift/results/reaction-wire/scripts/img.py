import sys,zlib,struct
from mrle import parse
h,c=parse(sys.argv[1]); out=sys.argv[2]
x0,y0,x1,y1=[int(a) for a in sys.argv[3:7]] if len(sys.argv)>6 else (0,0,max(x for x,y in c)+1,max(y for x,y in c)+1)
S=int(sys.argv[7]) if len(sys.argv)>7 else 3
pal={0:(0,0,0),1:(255,255,255),4:(255,80,80),17:(80,160,255),25:(255,200,0),11:(0,220,0),9:(200,0,200),13:(255,120,0),15:(0,255,255),19:(160,255,120),3:(255,0,255),21:(150,150,255),7:(255,150,150),23:(120,80,40),6:(90,90,90),8:(60,60,140)}
W=(x1-x0)*S;H=(y1-y0)*S
rows=[]
for y in range(y0,y1):
    r=bytearray()
    for x in range(x0,x1):
        r+=bytes(pal.get(c.get((x,y),0),(128,128,128)))*S
    for k in range(S): rows.append(b'\0'+bytes(r))
raw=b''.join(rows)
def chunk(t,d): return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
open(out,'wb').write(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',W,H,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))
