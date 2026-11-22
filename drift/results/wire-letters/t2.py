import lib,frames as F,pickle
SA=lib.idle(0); SD=lib.idle(9)
WA=F.Wire('A',SA,lambda x,y:x-y,40,20,(10,-10))
WD=F.Wire('D',SD,lambda x,y:-y,-78,20,(0,-20))
uA=lambda x,y:x+y; uD=lambda x,y:x
P={}
for i in (0,9,25,26,32,33,34,35):
    S=lib.idle(i)
    a=F.find_ports(WA,S,uA); d=F.find_ports(WD,S,uD)
    print(i,'A',a); print(i,'D',d)
    P[i]=(a,d)
pickle.dump(P,open('ports.pkl','wb'))
