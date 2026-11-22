# turtle specs: (piece, turn, extra periods of straight wire before this piece)
L,R='L','R'
def corner(turn,a=0,b=0):  # orth->orth 90 via 45 chamfer: extra a before, b on diagonal
    return [('DA',turn,a),('AD',turn,b)]
def D(h=8,w=2,bowl=5,v=2,c=0):
    # start: left stem going S
    return (corner(L,h,c)+                  # bottom-left
            [('DA',L,w),('AD',L,bowl)]+     # bottom edge, bottom-right diagonal
            [('DA',L,v),('AD',L,bowl)]+     # right side, top-right diagonal
            corner(L,w,c))                  # top edge, top-left
def I(h=12,w=1,c=0):
    return corner(L,h,c)+corner(L,w,c)+corner(L,h,c)+corner(L,w,c)
def F(stem=6,sw=1,mid=4,armw=1,gap=3,top=6,topw=1,top0=0,c=0):
    # start: going S on stem left side (first extra = top-left corner to bottom)
    return (corner(L,top0+stem+gap+armw*2+5,c)+ corner(L,sw,c)+  # bottom-left, bottom-right
            corner(R,stem,c)+            # up to mid arm: N->E
            corner(L,mid,c)+corner(L,armw,c)+   # mid arm end
            corner(R,mid,c)+             # W->N
            corner(R,gap,c)+             # N->E top arm
            corner(L,top,c)+corner(L,topw,c)+   # top arm end
            corner(L,top+sw,c))          # top-left
def T(stem=10,sw=1,arm=4,bw=1,c=0):
    return (corner(L,stem,c)+corner(L,sw,c)+   # bottom-left, bottom-right
            corner(R,stem,c)+                  # N->E concave
            corner(L,arm,c)+corner(L,bw,c)+    # right end
            corner(L,arm*2+sw,c)+corner(L,bw,c)+ # top edge, left end
            corner(R,arm,c))                   # E->S concave
def Rl(stem=12,sw=1,crotch=6,leg=6,foot=0,legup=3,notch=1,bowl=4,top=3,c=0):
    return (corner(L,stem,c)+corner(L,sw,c)+   # stem bottom
            [('DA',R,crotch),('T1',R,0)]+       # N -> NE -> SE
            [('T1',L,leg),('T1',L,foot)]+       # foot: SE->NE->NW
            [('T1',R,legup),('AD',L,notch)]+    # NW->NE ; NE->N
            [('DA',L,bowl),('AD',L,0)]+         # N->NW->W
            corner(L,top,c))                    # W->S
def R2(stem=14,sw=1,crotch=6,t1='T1',legdiag=2,legv=4,footw=1,legr=3,t2='T1',legup=1,notch=1,bowlr=2,bowl=2,top=3,c=0):
    return [('DA',L,stem),('AD',L,c),('DA',L,sw),('AD',L,c),
            ('DA',R,crotch),(t1,R,0),('AD',R,legdiag),
            ('DA',L,legv),('AD',L,c),('DA',L,footw),('AD',L,c),
            ('DA',L,legr),(t2,R,legup),('AD',L,notch),
            ('DA',L,bowlr),('AD',L,bowl),('DA',L,top),('AD',L,c)]
def R3(stem=14,sw=1,crotch=6,bb=0,legdiag=1,legv=4,footw=1,legr=3,legup=1,bowlr=2,bowl=2,top=3,c=0):
    return [('DA',L,stem),('AD',L,c),('DA',L,sw),('AD',L,c),
            ('DA',R,crotch),('AD',R,0),('DA',R,bb),('AD',R,legdiag),
            ('DA',L,legv),('AD',L,c),('DA',L,footw),('AD',L,c),
            ('DA',L,legr),('AD',R,legup),
            ('DA',L,bowlr),('AD',L,bowl),('DA',L,top),('AD',L,c)]
def R4(stem=14,sw=1,crotch=4,t1='T1',legdiag=0,legv=2,footw=1,legr=3,legup=1,bowlr=2,bowl=3,top=3,c=0):
    return [('DA',L,stem),('AD',L,c),('DA',L,sw),('AD',L,c),
            ('DA',R,crotch),(t1,R,0),('AD',R,legdiag),
            ('DA',L,legv),('AD',L,c),('DA',L,footw),('AD',L,c),
            ('DA',L,legr),('AD',R,legup),
            ('DA',L,bowlr),('AD',L,bowl),('DA',L,top),('AD',L,c)]
def R5(stem=14,sw=0,crotch=10,ct=0,cr=2,legdiag=1,legv=3,footw=0,legr=3,legup=1,bowlr=4,bowl=2,top=3,c=0):
    return [('DA',L,stem),('AD',L,c),('DA',L,sw),('AD',L,c),
            ('DA',R,crotch),('AD',R,c),('DA',R,ct),('AD',R,c),
            ('DA',L,cr),('AD',R,legdiag),('DA',L,legv),('AD',L,c),
            ('DA',L,footw),('AD',L,c),('DA',L,legr),('AD',R,legup),
            ('DA',L,bowlr),('AD',L,bowl),('DA',L,top),('AD',L,c)]
def R6(stem=14,sw=0,crotch=10,ct=2,cr=1,bw=1,sl=1,bw2=1,legdiag=2,legv=2,footw=0,legr=2,legup=2,bowlr=3,bowl=1,top=3,c=0):
    return [('DA',L,stem),('AD',L,c),('DA',L,sw),('AD',L,c),
            ('DA',R,crotch),('AD',R,c),('DA',R,ct),('AD',R,c),
            ('DA',R,cr),('AD',R,c),('DA',L,bw),('AD',L,c),
            ('DA',L,sl),('AD',L,c),('DA',R,bw2),('AD',R,legdiag),
            ('DA',L,legv),('AD',L,c),('DA',L,footw),('AD',L,c),
            ('DA',L,legr),('AD',R,legup),
            ('DA',L,bowlr),('AD',L,bowl),('DA',L,top),('AD',L,c)]
def Iserif(stem=8,ov=0,th=0,bw=1,tw=1,c=0):
    return (corner(R,stem,c)+corner(L,ov,c)+corner(L,th,c)+corner(L,bw,c)+corner(L,th,c)+corner(R,ov,c)+
            corner(R,stem,c)+corner(L,ov,c)+corner(L,th,c)+corner(L,tw,c)+corner(L,th,c)+corner(R,ov,c))
def F2(stem=5,sw=1,mid=2,armw=0,gap=1,top=3,topw=0,c=0):
    return (corner(L,0,c)+corner(L,sw,c)+corner(R,stem,c)+corner(L,mid,c)+corner(L,armw,c)+corner(R,mid,c)+
            corner(R,gap,c)+corner(L,top,c)+corner(L,topw,c)+corner(L,0,c))
def T2(stem=8,sw=1,arm=2,bw=0,c=0):
    return (corner(L,0,c)+corner(L,sw,c)+corner(R,stem,c)+corner(L,arm,c)+corner(L,bw,c)+
            corner(L,0,c)+corner(L,bw,c)+corner(R,arm,c))
