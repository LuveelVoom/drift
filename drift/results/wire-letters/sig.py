import lib,cad
# signal in canonical wA coords: comp0 frame k=0,t=(-10,10)
drawn=set(lib.comps[0].keys()); idle=lib.idle(0)
def sigA(g):
    st=lib.run(drawn,g)
    D=st^idle
    return {(x+10,y-10) for x,y in D}  # canonical coords
if __name__=='__main__':
    for g in range(0,60,4):
        D=sigA(g); s=[x-y for x,y in D]
        print(g,len(D),min(s) if D else None,max(s) if D else None)
