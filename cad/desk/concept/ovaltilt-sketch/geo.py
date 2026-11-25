# geometry + estimates for desk-shell concept sketches (thin-shell model; NOT CAD)
import numpy as np, math
RHO = 1.24e-3
A15 = math.radians(15); T15, C15, S15 = math.tan(A15), math.cos(A15), math.sin(A15)
LID = 3.0
T_IN = 4.55            # flat inner face behind the outer face on the centre line (as the oval)
BOW_H = 1.6            # outer front falls back this much (horizontal) at |x| 15.9 (glass edge + 0.3)
BOW_FADE = 10.0        # mm over which the bow fades out above / below the face (clay pass, 2026-11-20)
S0 = 16.7              # PCB bottom along the face from the rim (tilt15)

def bez(p0, p1, p2, p3, n=48):
    t = np.linspace(0, 1, n + 1)[:, None]
    p0, p1, p2, p3 = map(np.array, (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3
def line(p0, p1, n=2):
    t = np.linspace(0, 1, n)[:, None]; return (1 - t) * np.array(p0) + t * np.array(p1)
def chain(*segs):
    out = [segs[0]]
    for s in segs[1:]: out.append(s[1:])
    P = np.vstack(out)
    assert np.all(np.diff(P[:, 1]) > -1e-9), "profile not monotonic in z"
    return P
def hull(P):
    P = sorted(map(tuple, np.round(P, 6)))
    def cr(o, a, b): return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lo = []
    for p in P:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    up = []
    for p in reversed(P):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return np.array(lo[:-1] + up[:-1])
def perim(P):
    d = np.diff(np.r_[P, P[:1]], axis=0); return np.hypot(d[:, 0], d[:, 1]).sum()
def area_cent(P):
    x, y = P[:, 0], P[:, 1]; x2, y2 = np.roll(x, -1), np.roll(y, -1)
    cr = x * y2 - x2 * y; A = cr.sum() / 2
    if abs(A) < 1e-9: return 0.0, P[:, 0].mean(), P[:, 1].mean()
    return abs(A), ((x + x2) * cr).sum() / (6 * A), ((y + y2) * cr).sum() / (6 * A)
def edge_cent(P):
    Q = np.r_[P, P[:1]]; d = np.diff(Q, axis=0); L = np.hypot(d[:, 0], d[:, 1]); m = (Q[:-1] + Q[1:]) / 2
    return L.sum(), (m[:, 0] * L).sum() / L.sum(), (m[:, 1] * L).sum() / L.sum()
def inside(pt, P):
    x, y = pt; n = len(P); c = False
    for i in range(n):
        x1, y1 = P[i]; x2, y2 = P[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c
def dist_poly(pt, P):
    """signed: + inside (distance to boundary), - outside"""
    p = np.array(pt); Q = np.r_[P, P[:1]]; a = Q[:-1]; b = Q[1:]; ab = b - a
    t = np.clip(((p - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-12), 0, 1)
    d = np.hypot(*(a + t[:, None] * ab - p).T).min()
    return d if inside(pt, P) else -d

class Body:
    """loft: front/back profiles (y,z), left/right profiles (x,z); 4-quarter superellipse sections.
    yt: where the outer face line (centre line) meets the rim plane z=LID."""
    def __init__(s, front, back, left, right, n=2.8, nb=None, cfrac=0.5, xback=None, yt=0.0, face=(12, 96), bow=True, hidden=False):
        s.f, s.b, s.l, s.r = front, back, left, right
        s.n, s.nb, s.cfrac, s.yt, s.face, s.bow, s.hidden = n, nb or n, cfrac, yt, face, bow, hidden
        s.xback = xback or (lambda z: 0.0)
        s.z0 = max(p[0, 1] for p in (front, back, left, right)); s.z1 = min(p[-1, 1] for p in (front, back, left, right))
    def yf(s, z): return np.interp(z, s.f[:, 1], s.f[:, 0])
    def yb(s, z): return np.interp(z, s.b[:, 1], s.b[:, 0])
    def xl(s, z): return np.interp(z, s.l[:, 1], s.l[:, 0])
    def xr(s, z): return np.interp(z, s.r[:, 1], s.r[:, 0])
    def has(s, z): return s.z0 - 1e-9 <= z <= s.z1 + 1e-9
    def nfront(s, a, bf):
        if not s.bow or a <= 17.5 or bf <= BOW_H + 0.3: return s.n
        lo, hi = 2.0, 8.0
        f = lambda n: bf * (1 - (1 - (15.9 / a) ** n) ** (1 / n)) - BOW_H
        if f(lo) < 0: return lo
        if f(hi) > 0: return hi
        for _ in range(40):
            mid = (lo + hi) / 2
            if f(mid) > 0: lo = mid
            else: hi = mid
        return (lo + hi) / 2
    def section(s, z, k=40):
        yf, yb, xl, xr = s.yf(z), s.yb(z), s.xl(z), s.xr(z)
        if yb - yf < 0.2 or xr - xl < 0.2: return None
        yc = yf + s.cfrac * (yb - yf); xb = float(np.clip(s.xback(z), xl + 0.1, xr - 0.1))
        th = np.linspace(0, np.pi / 2, k + 1); c, sn = np.cos(th), np.sin(th)
        # the oval's bow over the face, faded out over BOW_FADE above and below it (a switch leaves a crease)
        g = min(z - (s.face[0] - BOW_FADE), (s.face[1] + BOW_FADE) - z) / BOW_FADE
        ss = lambda g: 0.0 if g <= 0 else 1.0 if g >= 1 else g * g * (3 - 2 * g)
        # nfront() gives up (returns n) below a half-width 17.5 / depth BOW_H + 0.3: fade towards those limits too
        w = ss(g) * ss((yc - yf - BOW_H - 0.3) / 6.0)
        nr = s.n + w * ss((xr - 17.5) / 6.0) * (s.nfront(xr, yc - yf) - s.n) if w else s.n
        nl = s.n + w * ss((-xl - 17.5) / 6.0) * (s.nfront(-xl, yc - yf) - s.n) if w else s.n
        q1 = np.c_[xr * sn ** (2 / nr), yc - (yc - yf) * c ** (2 / nr)]                 # front apex -> right
        q2 = np.c_[xb + (xr - xb) * c ** (2 / s.nb), yc + (yb - yc) * sn ** (2 / s.nb)]  # right -> back apex
        q3 = np.c_[xb + (xl - xb) * sn ** (2 / s.nb), yc + (yb - yc) * c ** (2 / s.nb)]  # back apex -> left
        q4 = np.c_[xl * c ** (2 / nl), yc - (yc - yf) * sn ** (2 / nl)]                 # left -> front apex
        return np.vstack([q1[:-1], q2[:-1], q3[:-1], q4[:-1]])
    def side_poly(s):
        return np.vstack([s.f, s.b[::-1]])
    def front_poly(s):
        return np.vstack([s.l, s.r[::-1]])

def W(yt, s, t):
    """face frame -> (y, z); s along the face from the rim, t into the body from the outer face (centre line)"""
    return yt + s * S15 + t * C15, LID + s * C15 - t * S15

def sections(bodies, z):
    return [P for P in (b.section(z) for b in bodies if b.has(z)) if P is not None]
def hull_at(bodies, z):
    S = sections(bodies, z)
    return hull(np.vstack(S)) if S else None

def analyse(name, bodies, yt, extra=(), flat_top=0.0, verbose=True):
    H = max(b.z1 for b in bodies)
    zs = np.arange(LID + 0.5, H, 1.0)
    M = My = Mz = Mx = 0.0; prev = None; shell = 0.0
    for z in zs:
        P = hull_at(bodies, z)
        if P is None: continue
        L, cx, cy = edge_cent(P); r = L / (2 * math.pi)
        ds = 1.0 if prev is None else math.hypot(1.0, r - prev); prev = r
        m = max(L - math.pi * 3.0, 0) * 3.0 * ds * RHO * 0.9
        M += m; Mx += m * cx; My += m * cy; Mz += m * z; shell += m
    if flat_top:
        P = hull_at(bodies, H - 0.05)
        if P is not None:
            A, cx, cy = area_cent(P); m = A * flat_top * RHO; M += m; Mx += m * cx; My += m * cy; Mz += m * (H - flat_top / 2); shell += m
    P0 = hull_at(bodies, 1.5); A, cx, cy = area_cent(P0); lid = A * LID * RHO
    M += lid; Mx += lid * cx; My += lid * cy; Mz += lid * 1.5
    for g, s_, t_ in ((30.0, S0 + 39.4, T_IN + 0.5 + 4.5), (55.0, S0 + 1 + 34, T_IN + 9.6 + 5.0), (2.8, 55, 2.0)):
        y, z = W(yt, s_, t_); M += g; My += g * y; Mz += g * z
    for g, x, y, z in extra: M += g; Mx += g * x; My += g * y; Mz += g * z
    cx, cy, cz = Mx / M, My / M, Mz / M
    F = hull(np.vstack(sections(bodies, 0.0)))
    yb_, yf_ = F[:, 1].max() - 0.5, F[:, 1].min() + 0.5
    best = (99, None)
    for i in range(len(F)):
        p, q = F[i], F[(i + 1) % len(F)]; e = q - p; L = np.hypot(*e)
        if L < 1e-9: continue
        d = abs(e[0] * (cy - p[1]) - e[1] * (cx - p[0])) / L - 0.5
        a = math.degrees(math.atan2(d, cz))
        if a < best[0]: best = (a, ((p + q) / 2).round(1))
    back = math.degrees(math.atan2(yb_ - cy, cz)); fwd = math.degrees(math.atan2(cy - yf_, cz))
    # real stack, 3D: clearance = distance to the outer section minus the 3.0 wall
    worst = {}
    def chk(tag, x, s_, t_, need_wall=3.0, dz=0.0):
        y, z = W(yt, s_, t_)
        if z < LID: return          # below the rim: lid zone, open during insertion
        P = hull_at(bodies, z + dz)
        d = -99 if P is None else dist_poly((x, y), P)
        c = d - need_wall
        if tag not in worst or c < worst[tag][0]: worst[tag] = (round(c, 2), round(s_, 1), x)
    for s_ in np.arange(0, 85.71, 1.0):
        for x in (-17.5, 17.5): chk("battery (up move, 0.5 behind seat)", x, s_, T_IN + 9.6 + 10 + 0.5)
    for s_ in np.arange(0, 95.76, 1.0):
        for x in (-17.7, 16.7): chk("board (up move, 4.0 behind seat)", x, s_, T_IN + 9.5 + 4.0)
    for s_ in np.arange(0, 80.1, 1.0): chk("plugs +X (up move)", 20.7, s_, T_IN + 9.5 + 4.0)
    for t_ in (T_IN, T_IN + 9.5, T_IN + 13.5):
        for x in (-16.7, 16.7): chk("board top: roof 3 above", x, 95.55 + 0.5, t_, need_wall=0.0, dz=3.0)
    # coordinator's box on the centre line (side view)
    box = [W(yt, 12, 3), W(yt, 95, 3), W(yt, 95, 26), W(yt, 12, 26)]
    dmin = 99
    for (y, z) in [box[2], box[3]] + [tuple((1 - u) * np.array(box[2]) + u * np.array(box[3])) for u in np.linspace(0, 1, 30)] + [W(yt, 95, t_) for t_ in np.linspace(8, 26, 10)]:
        d = max(dist_poly((y, z), b.side_poly()) for b in bodies)
        dmin = min(dmin, d)
    # outer overhang (deg from vertical), profiles only
    ov = 0
    for b in bodies:
        for P, sign in ((b.f, -1), (b.b, 1), (b.l, -1), (b.r, 1)):
            d = np.diff(P, axis=0); ok = (d[:, 1] > 1e-6) & (P[:-1, 1] >= LID - 1e-6)
            if ok.any(): ov = max(ov, math.degrees(math.atan(np.max(sign * d[ok, 0] / d[ok, 1]))))
    allp = np.vstack([np.vstack(sections(bodies, z)) for z in np.arange(0, H, 1.0) if sections(bodies, z)])
    res = dict(name=name, H=H, W=allp[:, 0].max() - allp[:, 0].min(), D=allp[:, 1].max() - allp[:, 1].min(), ymin=allp[:, 1].min(), ymax=allp[:, 1].max(),
               foot=(F[:, 0].min(), F[:, 0].max(), F[:, 1].min(), F[:, 1].max()), mass=M, shell_cm3=shell / RHO / 1000, lid_cm3=lid / RHO / 1000,
               com=(cx, cy, cz), back=back, fwd=fwd, worst=best, real=worst, box=dmin, overhang=ov, F=F)
    if verbose:
        print(f"== {name}: W {res['W']:.1f} D {res['D']:.1f} (y {res['ymin']:.1f}..{res['ymax']:.1f}) H {H:.1f}; foot x {F[:,0].min():.1f}..{F[:,0].max():.1f}, y {F[:,1].min():.1f}..{F[:,1].max():.1f}")
        print(f"   shell {res['shell_cm3']:.1f} cm3, lid {res['lid_cm3']:.1f}, mass {M:.0f} g; CoM x {cx:.1f} y {cy:.1f} z {cz:.1f}; tips back {back:.1f}, fwd {fwd:.1f}, worst {best[0]:.1f} over foot edge at {best[1]}")
        print(f"   real stack clearance beyond a 3.0 wall: " + "; ".join(f"{k} {v[0]} (s {v[1]}, x {v[2]})" for k, v in worst.items()))
        print(f"   coordinator box to the outline on the centre line: {dmin:.2f}; max outer overhang on profiles {ov:.0f} deg")
    return res
