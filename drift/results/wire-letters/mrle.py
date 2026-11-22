import re,sys
def parse(path):
    txt=open(path).read().splitlines()
    hdr=[l for l in txt if l.startswith('x')][0]
    body=''.join(l for l in txt if not l.startswith('x') and not l.startswith('#'))
    cells={}; x=y=0; i=0
    for m in re.finditer(r'(\d*)([p-y][A-X]|[a-zA-Z.$!])',body):
        n=int(m.group(1)) if m.group(1) else 1; t=m.group(2)
        if t=='$': y+=n; x=0; continue
        if t=='!': break
        if t in '.b': x+=n; continue
        if t=='o': s=1
        elif len(t)==1: s=ord(t)-64
        else: s=(ord(t[0])-ord('p')+1)*24+ord(t[1])-64
        for k in range(n): cells[(x+k,y)]=s
        x+=n
    return hdr,cells
if __name__=='__main__':
    h,c=parse(sys.argv[1])
    W=max(x for x,y in c)+1;H=max(y for x,y in c)+1
    sym=lambda s: '.' if s==0 else ('#' if s==4 else (chr(ord('a')+s-1) if s<26 else '*'))
    x0=int(sys.argv[2]) if len(sys.argv)>2 else 0; x1=int(sys.argv[3]) if len(sys.argv)>3 else W
    for y in range(H): print('%3d '%y+''.join(sym(c.get((x,y),0)) for x in range(x0,x1)))
    from collections import Counter; print(Counter(c.values()))
