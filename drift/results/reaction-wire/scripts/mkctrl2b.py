exec(open('wirefit.py').read().split("base=C.parse_rle")[0])
import gencfg
h,c=parse('ws.rle')
sub={p:s for p,s in c.items() if 160<=p[0]<215 and 125<=p[1]<180 and s%2==1}
idle=set(p for p,s in sub.items() if s!=25); stim=set(p for p,s in sub.items() if s==25)
unk=near(stim,4)-stim
nc=set(q for q in near(idle,1) if min(max(abs(q[0]-a),abs(q[1]-b)) for a,b in stim)>12)
xs=[x for x,y in idle|stim];ys=[y for x,y in idle|stim]
b=(min(xs)-3,max(xs)+3,min(ys)-3,max(ys)+3)
print('blanked converter cells:',len(idle&unk),'unknown cells',len(unk-idle)+len(idle&unk))
gencfg.write(sys.argv[1],"Positive control (with must-reach on the far wire): domino -> wA converter with the cells within 4 of the domino unknown.\ndrift must rebuild them and report an escape (signal on the no-count wire).",
  idle-unk, stim, unk, nc, b, {'rule':'B3/S23-a5','max-changed':20,'size':'16x16','margin':0,'max-gen':80,'escape':'true',
  'skip':'oscillator, stable, maxgen','per-rotor':0,'max-results':0}, mustreach=set(c for c in idle-unk if min(max(abs(c[0]-a),abs(c[1]-b)) for a,b in stim)>12))
