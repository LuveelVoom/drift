# mkend.py WIRE OUTDIR [LEAD] [REACH] : wire-end weak-spark search config
exec(open('wirefit.py').read().split("base=C.parse_rle")[0])
import gencfg, json
nm=sys.argv[1]; out=sys.argv[2]; LEAD=int(sys.argv[3]) if len(sys.argv)>3 else 12; REACH=int(sys.argv[4]) if len(sys.argv)>4 else 4
s={'A':1,'B':17,'C':15,'D':11,'E':19}[nm]; g=W[s]
F=[w for w in WIRES if w[0]==nm][0][1]; M=set(p for p in g if L[p]==13)
q=C.Pattern.from_coords(g,R); arrive=None; t=0; snaps=[]
while True:
    t+=1; q.step(1); d=cells(q)^F; snaps.append(cells(q))
    if min(max(abs(a-b),abs(c-e)) for a,c in d for b,e in M)<=1: arrive=t; break
st=snaps[arrive-LEAD-1]; d=st^F
on0=st-F; off0=F-st
print(nm,'signal drawn at gen',arrive-LEAD,'cells on',len(on0),'off',len(off0),'dist to terminator',min(max(abs(a-b),abs(c-e)) for a,c in d for b,e in M))
bg=F-M
unk=near(M,REACH)-bg
allc=F|unk
b=(min(x for x,y in allc)-3,max(x for x,y in allc)+3,min(y for x,y in allc)-3,max(y for x,y in allc)+3)
name=f"end-{nm}-lead{LEAD}-r{REACH}"
gencfg.write(f"{out}/{name}.cfg",
 f"Weak-spark output for wire {nm}: idle wire with its terminator replaced by unknown cells\n(within {REACH} of it), signal drawn {LEAD} gens before it reaches the end. Keep fizzles\nthat put a cell at least output-dist (5) from the signal; judge with the clean-output test.",
 bg|off0, on0|off0, unk, set(), b,
 {'rule':'B3/S23-a5','max-changed':12,'size':'8x8','margin':0,'max-gen':80,'skip':'oscillator, stable, maxgen',
  'output-dist':5,'per-rotor':0,'max-results':0})
# state 4 = off in gen 0 only: gencfg writes 'D' for cells in spark & bg
json.dump(dict(name=name,F=sorted(F),M=sorted(M),bounds=b),open(f"{out}/{name}.json",'w'))
print(name,'unknown cells',len(unk))
