def ex(c): r=(c>>11)&31;g=(c>>5)&63;b=c&31; return (r<<3|r>>2, g<<2|g>>4, b<<3|b>>2)
def p(r,g,b): return ((r&0xf8)<<8)|((g&0xfc)<<3)|(b>>3)
def sh(c,T):
    return p(*[ (x*(256-T)+128)>>8 for x in ex(c)])
def tdiv(a,b): return int(a/b) if a*b>=0 else -int(-a/b)
def tl(bg,mark,T,C,m=256,markU=None):
    B=ex(bg);M=ex(mark)
    c=[B[i]+(((M[i]-B[i])*T+128)>>8) for i in range(3)]
    lb=299*B[0]+587*B[1]+114*B[2]; lc=299*c[0]+587*c[1]+114*c[2]; d=lc-lb
    if m<256: Cm=(C*m+128)>>8; W=(255*m+128)>>8; top=1000*W; dark=(110000*m+128)>>8; den0=((1000*m+128)>>8)+1
    else: Cm=C;W=255;top=255000;dark=110000;den0=1000
    if abs(d)>=Cm: return p(*c)
    dir=(1 if d>0 else -1) if d!=0 else (-1 if lb>dark else 1)
    if m<256 and d==0 and T>0 and markU is not None:
        U=ex(markU); e=299*U[0]+587*U[1]+114*U[2]-lb*256//m
        if e!=0: dir=1 if e>0 else -1
    target=max(0,min(top,lb+dir*Cm))
    if dir<0:
        den=max(lc,den0); c=[(x*target+den//2)//den for x in c]
    else:
        den=max(den0,top-lc); K=max(0,min(256,tdiv((target-lc)*256,den))); c=[x+(((W-x)*K+128)>>8) for x in c]
    return p(*[min(255,x) for x in c])
for bg,ink in ((0x738e,0x73ae),(0x73ae,0x738e)):
    ref=sh(tl(bg,ink,128,40000),128)
    fold=tl(sh(bg,128),sh(ink,128),128,40000,128,ink)
    print(hex(bg),hex(ink),'shaded',hex(sh(bg,128)),hex(sh(ink,128)),'ref',hex(ref),'fold',hex(fold))
