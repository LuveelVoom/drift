import letters,solve,cad,lib,test,pickle,sys,time
def specs():
    S={}
    S['D']=solve.solve3(letters.D(h=13,w=2,bowl=5,v=8),[0,2,6],[])
    S['R']=solve.solve3(letters.R6(crotch=11,ct=1,cr=1,sl=1,legdiag=1,legv=3,legr=4,legup=2,bowlr=5,bowl=1,bw=0,bw2=0),[0,24],[23,21,15])
    S['I']=solve.solve(letters.Iserif(stem=7,bw=4,tw=4),verbose=False)
    S['F']=solve.solve3(letters.F2(stem=4,sw=0,mid=2,top=3,gap=1),[0,18],[1,19,7,15])
    S['T']=solve.solve(letters.T2(stem=10,arm=1,sw=0),allowed=[0,10],verbose=False)
    return S
def verify(name,s):
    c,info=cad.build(s)
    p=lib.pat(c); p.step(1); still=set(p.coords())==c
    # inject at the wA junction with the longest filler
    js=[(j['cy']-j['cx'],i) for i,j in enumerate(info['junc']) if j['W'] is cad.WA]
    ji=max(js)[1]
    sc=test.inject(c,info,ji)
    q=lib.pat(sc); seen=set(); t0=time.time()
    P=None; start=frozenset(sc)
    for g in range(1,8000):
        q.step(1); cur=set(q.coords())
        seen|=cur^c
        if len(cur)>len(c)+60: break
        if cur==sc: P=g; break
    # coverage: every junction cut point near a diff cell
    def near(pt):
        return any(abs(x-pt[0])<=12 and abs(y-pt[1])<=12 for x,y in seen)
    cov=0
    for j in info['junc']:
        W=j['W']; s0=(j['cx']+j['cy'])//2
        # a canonical cell at s0
        cc=[cc for m in range(-3,8) for cc in W.slab(m) if W.sfun(*cc)==s0]
        pt=cad.xf(j['K'],j['tX'],cc[0]) if cc else None
        cov+= bool(pt and near(pt))
    return dict(still=still,period=P,junctions=len(info['junc']),visited=cov,cells=len(c),secs=round(time.time()-t0,1)),c,sc
if __name__=='__main__':
    S=specs(); out={}
    for n in (sys.argv[1:] or 'DRIFT'):
        r,c,sc=verify(n,S[n]); print(n,r,[x[2] for x in S[n]],flush=True); out[n]=(S[n],c,sc,r)
    pickle.dump(out,open('final_%s.pkl'%''.join(sys.argv[1:] or ['all']),'wb'))
