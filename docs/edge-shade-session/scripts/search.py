import math
def scr(s,R,g,n):
    s1=s/n;c1=math.sqrt(1-s1*s1);ca=math.sqrt(1-s*s);st=s*c1-ca*s1;ct=ca*c1+s*s1;sa=n*st
    return R*s-(R*ca)*(st/ct)-g*(sa/math.sqrt(1-sa*sa))
R=4.0;g=.87;n=1.49
lo,hi=0,1
for i in range(60):
    m=(lo+hi)/2;s1=m/n;st=m*math.sqrt(1-s1*s1)-math.sqrt(1-m*m)*s1
    if n*st<1: lo=m
    else: hi=m
a,b=0,lo
for i in range(100):
    c=b-(b-a)*0.6180339887498949;e=a+(b-a)*0.6180339887498949
    if scr(c,R,g,n)<scr(e,R,g,n): a=c
    else: b=e
sF=(a+b)/2;dF=scr(sF,R,g,n)
def base(d):
    if d>=dF: return 1
    lo,hi=0,sF
    for i in range(60):
        m=(lo+hi)/2
        if scr(m,R,g,n)<d: lo=m
        else: hi=m
    return (lo+hi)/2/sF
H=72
bases=[base(abs(y+0.5-36)*0.0825) for y in range(H)]
def lensmap(lens,curve):
    sc=-curve if lens<0 else curve; st=abs(lens)
    if st==0 or sc==0: return None
    e=1+sc*2 if sc>0 else 1/(1-sc*2)
    out=[]
    for yd in range(H):
        d=(yd+0.5-H/2)/(H/2);u=abs(d);s=(-1 if d<0 else 1)*((1-st)*u+st*u**e)
        out.append(min(H-1,max(0,math.floor(H/2+s*H/2))))
    return out
def fold(T,src):
    F={}
    for y in range(H):
        r=src[y];F[r]=min(F.get(r,999),T[y])
    post=[0 if T[y]==F[src[y]] else 1 for y in range(H)]
    return F,post
found=[]
for lens in [x/10 for x in range(-10,11)]:
  for curve in [x/10 for x in range(-30,31)]:
    src=lensmap(lens,curve)
    if not src: continue
    for pw in (1,2.5,4):
      for k1,k2 in ((0.5,0.75),(0.3,0.6),(0.67,1)):
        T1=[math.floor(k1*b**(2*pw)*256+0.5) for b in bases];T2=[math.floor(k2*b**(2*pw)*256+0.5) for b in bases]
        F1,p1=fold(T1,src);F2,p2=fold(T2,src)
        for y in range(H):
          r=src[y]
          if p1[y] and p2[y] and F1[r]==F2[r] and T1[y]!=T2[y]:
            n1=sum(p1);n2=sum(p2)
            if p1==p2 and max(n1,n2)<=32: found.append((lens,curve,pw,k1,k2,y,r,F1[r],T1[y],T2[y],n1,n2))
            break
print(len(found)); print(found[:10])
print('--- tile-level')
res=[]
for lens in [x/10 for x in range(-10,11)]:
  for curve in [x/10 for x in range(-30,31)]:
    src=lensmap(lens,curve)
    if not src: continue
    for pw in (1,2.5,4):
      for k1,k2 in ((0.5,0.75),(0.3,0.6),(0.67,1),(0.2,0.3),(1,0.9)):
        T1=[math.floor(k1*b**(2*pw)*256+0.5) for b in bases];T2=[math.floor(k2*b**(2*pw)*256+0.5) for b in bases]
        F1,p1=fold(T1,src);F2,p2=fold(T2,src)
        if p1!=p2 or sum(p1)>32 or sum(p1)==0: continue
        ys=[y for y in range(H) if p1[y]]
        for t in range(0,len(ys),4):
          grp=ys[t:t+4]
          tiles={src[y]//4 for y in grp}
          srcunch=all(F1.get(r,0)==F2.get(r,0) for tt in tiles for r in range(tt*4,tt*4+4))
          if srcunch and any(T1[y]!=T2[y] for y in grp): res.append((lens,curve,pw,k1,k2,grp,tiles)); break
print(len(res)); print(res[:8])
