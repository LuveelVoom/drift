import zlib,struct
def png(layers,out,S=3,pad=5):
    """layers: list of (cells,color)"""
    allc=set().union(*[l[0] for l in layers])
    x0=min(x for x,y in allc)-pad;y0=min(y for x,y in allc)-pad
    x1=max(x for x,y in allc)+pad;y1=max(y for x,y in allc)+pad
    col={}
    for cs,c in layers:
        for p in cs: col[p]=c
    W=(x1-x0+1)*S;H=(y1-y0+1)*S;rows=[]
    for y in range(y0,y1+1):
        r=bytearray()
        for x in range(x0,x1+1): r+=bytes(col.get((x,y),(0,0,0)))*S
        for k in range(S): rows.append(b'\0'+bytes(r))
    def chunk(t,d): return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
    open(out,'wb').write(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',W,H,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(bytes(b''.join(rows))))+chunk(b'IEND',b''))
    return (x1-x0+1-2*pad,y1-y0+1-2*pad)
