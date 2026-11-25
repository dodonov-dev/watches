# true-scale SVG sheets: front / left side / top (+ horizontal section for the pebble). 1 mm = 4 px.
from geo import *
import geo
K = 4.0
BODY, EDGE, GRID = "#EFE9DF", "#57534e", "#e9e9e9"
BOXF, BOXS, ROD, RED, REAL = "#8ea0bb", "#5d6f8c", "#2f7fd6", "#c8322b", "#3b4a66"

def pth(P, close=True):
    return "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in P) + (" Z" if close else "")
class Sheet:
    def __init__(s, w, h): s.w, s.h, s.o = w, h, [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="DejaVu Sans, Arial, sans-serif">', f'<rect width="{w}" height="{h}" fill="#ffffff"/>']
    def add(s, x): s.o.append(x)
    def text(s, x, y, t, size=13, fill="#222", anchor="start", weight="normal", rot=None):
        tr = f' transform="rotate({rot} {x:.1f} {y:.1f})"' if rot is not None else ""
        t = t.replace("&", "&amp;").replace("<", "&lt;")
        s.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}"{tr}>{t}</text>')
    def save(s, path): open(path, "w").write("\n".join(s.o + ["</svg>"]))
class View:
    """maps mm (u, v) -> px; sx = +1/-1 flips u"""
    def __init__(s, sh, ox, oy, sx=1, k=K): s.sh, s.ox, s.oy, s.sx, s.k = sh, ox, oy, sx, k
    def p(s, u, v): return s.ox + s.sx * s.k * u, s.oy - s.k * v
    def P(s, pts): return [s.p(u, v) for u, v in pts]
    def poly(s, pts, fill="none", stroke=EDGE, sw=1.2, dash=None, op=1.0, close=True):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        s.sh.add(f'<path d="{pth(s.P(pts), close)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round" fill-opacity="{op}"{d}/>')
    def line(s, a, b, stroke=EDGE, sw=1.0, dash=None):
        (x1, y1), (x2, y2) = s.p(*a), s.p(*b); d = f' stroke-dasharray="{dash}"' if dash else ""
        s.sh.add(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{stroke}" stroke-width="{sw}"{d}/>')
    def dot(s, u, v, r=4, fill=RED):
        x, y = s.p(u, v); s.sh.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r}" fill="{fill}"/>')
    def text(s, u, v, t, dx=0, dy=0, **kw):
        x, y = s.p(u, v); s.sh.text(x + dx, y + dy, t, **kw)
    def grid(s, u0, u1, v0, v1, step=10):
        for u in np.arange(math.ceil(u0 / step) * step, u1 + 1e-6, step): s.line((u, v0), (u, v1), GRID, 1)
        for v in np.arange(math.ceil(v0 / step) * step, v1 + 1e-6, step): s.line((u0, v), (u1, v), GRID, 1)
        s.poly([(u0, v0), (u1, v0), (u1, v1), (u0, v1)], stroke="#cfcfcf", sw=1)
    def dimh(s, u0, u1, v, label, off=0):
        (x0, y), (x1, _) = s.p(u0, v), s.p(u1, v); y += off
        s.sh.add(f'<path d="M{x0:.1f},{y-4:.1f} V{y+4:.1f} M{x1:.1f},{y-4:.1f} V{y+4:.1f} M{x0:.1f},{y:.1f} H{x1:.1f}" stroke="#444" stroke-width="1" fill="none"/>')
        s.sh.text((x0 + x1) / 2, y + 15, label, size=12, anchor="middle", fill="#333")
    def dimv(s, u, v0, v1, label, off=0):
        (x, y0), (_, y1) = s.p(u, v0), s.p(u, v1); x += off
        s.sh.add(f'<path d="M{x-4:.1f},{y0:.1f} H{x+4:.1f} M{x-4:.1f},{y1:.1f} H{x+4:.1f} M{x:.1f},{y0:.1f} V{y1:.1f}" stroke="#444" stroke-width="1" fill="none"/>')
        s.sh.text(x - 6, (y0 + y1) / 2, label, size=12, anchor="middle", fill="#333", rot=-90)

def front_branch(P):
    """outer front of a section polygon as y(x)"""
    yc = P[np.argmax(P[:, 0]), 1]
    F = P[P[:, 1] <= yc + 1e-6]; F = F[np.argsort(F[:, 0])]
    return F
def offset_in(P, d):
    Q = np.r_[P[-1:], P, P[:1]]; t = Q[2:] - Q[:-2]; t /= np.hypot(t[:, 0], t[:, 1])[:, None]
    nrm = np.c_[-t[:, 1], t[:, 0]]
    A = area_cent(P)[0]; s = 1.0
    P2 = P + d * nrm
    if area_cent(P2)[0] > A: P2 = P - d * nrm
    return P2
def clip_y(P, y0):
    """keep the part with y >= y0"""
    out = []
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        ia, ib = a[1] >= y0, b[1] >= y0
        if ia: out.append(a)
        if ia != ib:
            u = (y0 - a[1]) / (b[1] - a[1]); out.append(a + u * (b - a))
    return np.array(out)

def sheet(key, title, sub, notes, bodies, yt, res, contours, logo="front", usb=None, extra_section=None, path=None, logo_xy=None, top_note=None):
    Hh = 716 if not extra_section else 1030
    sh = Sheet(1260, Hh)
    sh.text(28, 34, title, size=21, weight="bold")
    for i, n in enumerate(sub): sh.text(28, 56 + 17 * i, n, size=13, fill="#222")
    for i, n in enumerate(notes): sh.text(28, 56 + 17 * len(sub) + 4 + 15 * i, n, size=11.5, fill="#555")
    base = 650
    Hmm = res["H"]
    fv = View(sh, 190, base); sv = View(sh, 712, base, sx=-1); tv = View(sh, 962, base - 16)
    for v, (u0, u1, v0, v1), lab in ((fv, (-38, 38, -6, 116), "FRONT"), (sv, (-8, 72, -6, 116), "LEFT SIDE  (front on the right)"), (tv, (-38, 38, -6, 72), "TOP  (front at the bottom)")):
        v.grid(u0, u1, v0, v1)
        x, y = v.p(u0 if v.sx > 0 else u1, v1); sh.text(x + 2, y - 6, lab, size=12, fill="#666", weight="bold")
    for v, (u0, u1) in ((fv, (-38, 38)), (sv, (-8, 72))): v.line((u0, 0), (u1, 0), "#888", 2.2)
    # ---------- side
    vis = [b for b in bodies]
    for b in vis: sv.poly(b.side_poly(), fill=BODY, stroke="none")
    for b in vis:  # redraw outer strokes only where not inside another body
        P = b.side_poly(); Q = np.r_[P, P[:1]]
        for i in range(len(Q) - 1):
            n = max(1, int(np.hypot(*(Q[i + 1] - Q[i])) / 0.8))
            for j in range(n):
                a_, b2 = Q[i] + (Q[i + 1] - Q[i]) * j / n, Q[i] + (Q[i + 1] - Q[i]) * (j + 1) / n; m = (a_ + b2) / 2
                if m[1] > 0.05 and any(o is not b and dist_poly(m, o.side_poly()) > 0.05 for o in vis): continue
                sv.line(a_, b2, EDGE, 1.6)
    hl = hull_at(bodies, LID)
    sv.line((hl[:, 1].min(), LID), (hl[:, 1].max(), LID), "#8a8a8a", 1, "5,3")
    box = [W(yt, 12, 3), W(yt, 95, 3), W(yt, 95, 26), W(yt, 12, 26)]
    sv.poly(box, fill=BOXF, stroke=BOXS, sw=1, op=0.45)
    sv.poly([W(yt, S0, T_IN + 0.5), W(yt, S0 + 78.85, T_IN + 0.5), W(yt, S0 + 78.85, T_IN + 9.5), W(yt, S0, T_IN + 9.5)], stroke=REAL, sw=0.9, dash="4,2")
    sv.poly([W(yt, S0 + 1, T_IN + 9.6), W(yt, S0 + 69, T_IN + 9.6), W(yt, S0 + 69, T_IN + 19.6), W(yt, S0 + 1, T_IN + 19.6)], stroke=REAL, sw=0.9, dash="4,2")
    sv.poly([W(yt, 24.7, T_IN - 3.6), W(yt, 91.35, T_IN - 3.6), W(yt, 91.35, T_IN + 0.4), W(yt, 24.7, T_IN + 0.4)], fill=ROD, stroke="none", op=0.9)
    cx, cy, cz = res["com"]; F = res["F"]
    sv.line((F[:, 1].min() + 0.5, -1.6), (F[:, 1].max() - 0.5, -1.6), RED, 3.2); sv.dot(cy, cz)
    sv.text(cy, cz, "CoM", dx=7, dy=4, size=11, fill=RED)
    if usb is not None: sv.poly([(usb + 0.4, LID), (usb + 0.4, LID + 6), (usb - 3.2, LID + 6), (usb - 3.2, LID)], fill="#333", stroke="none"); sv.text(usb, LID + 3, "USB notch", dx=-8, dy=4, size=11, fill="#333", anchor="end")
    sv.dimh(res["ymax"], res["ymin"], 0, f"D {res['D']:.0f}  (foot {F[:,1].max()-F[:,1].min():.0f})", off=18)
    sv.dimv(res["ymax"] + 5, 0, Hmm, f"H {Hmm:.0f}", off=0)
    # 15 deg mark
    a, b_ = W(yt, 97, 0), W(yt, 112, 0); sv.line(a, b_, "#999", 1, "3,3"); sv.line(a, (a[0], a[1] + 14.5), "#999", 1, "3,3"); sv.text(a[0], a[1] + 14.5, "15°", dx=-4, dy=-2, size=11, fill="#666", anchor="end")
    # ---------- front
    for b in bodies:
        if not b.hidden: fv.poly(b.front_poly(), fill=BODY, sw=1.6)
    for b in bodies:
        if b.hidden: fv.poly(b.front_poly(), stroke="#8a8580", sw=1, dash="5,3")
    z0, z1 = LID + 24.6 * C15, LID + 91.45 * C15
    for sg in (-1, 1):
        fv.poly([(sg * 2.235, z0), (sg * 16.61, z0), (sg * 16.61, z1), (sg * 2.235, z1)], fill="#d8d0c2", stroke="#8a8377", sw=0.8)
        fv.poly([(sg * 6.23, LID + 24.7 * C15), (sg * 14.23, LID + 24.7 * C15), (sg * 14.23, LID + 91.35 * C15), (sg * 6.23, LID + 91.35 * C15)], fill=ROD, stroke="none", op=0.85)
    bz = [W(yt, 12, 26)[1], W(yt, 95, 3)[1]]
    fv.poly([(-17.5, bz[0]), (17.5, bz[0]), (17.5, bz[1]), (-17.5, bz[1])], stroke=BOXS, sw=1, dash="5,3")
    if logo_xy:
        lx, lz, lw = logo_xy; lh = lw * 0.631
        fv.poly([(lx - lw / 2, lz), (lx + lw / 2, lz), (lx + lw / 2, lz + lh), (lx - lw / 2, lz + lh)], stroke="#b58a2a", sw=1); fv.text(lx, lz + lh / 2, "EH", dy=4, size=10, fill="#b58a2a", anchor="middle")
    fv.line((-38, LID), (38, LID), "#8a8a8a", 1, "5,3")
    xs = np.vstack([b.front_poly() for b in bodies if not b.hidden])
    fv.dimh(xs[:, 0].min(), xs[:, 0].max(), 0, f"W {xs[:,0].max()-xs[:,0].min():.0f}", off=18)
    # ---------- top
    env = hull(np.vstack([np.vstack(sections(bodies, z)) for z in np.arange(0, Hmm, 1.0) if sections(bodies, z)]))
    if len(bodies) == 1: tv.poly(env, fill=BODY, sw=1.6)
    else:
        for b in bodies:
            e = hull(np.vstack([b.section(z) for z in np.arange(b.z0, b.z1, 1.0) if b.section(z) is not None])); tv.poly(e, fill=BODY, sw=1.6, dash="5,3" if b.hidden else None)
        for b in bodies:
            if not b.hidden:
                e = hull(np.vstack([b.section(z) for z in np.arange(b.z0, b.z1, 1.0) if b.section(z) is not None])); tv.poly(e, fill=BODY, sw=1.6)
    for z in list(contours) + [Hmm - 0.01]:
        for b in bodies:
            if b.has(z) and b.section(z) is not None: tv.poly(b.section(z), stroke="#a39c90", sw=0.8, dash="4,3" if b.hidden else None)
    tv.poly(F, stroke=RED, sw=1.1, dash="5,3")
    for sg in (-1, 1):
        y0, y1 = W(yt, 24.7, T_IN - 3.6)[0], W(yt, 91.35, T_IN - 3.6)[0]
        tv.poly([(sg * 6.23, y0), (sg * 14.23, y0), (sg * 14.23, y1), (sg * 6.23, y1)], fill=ROD, stroke="none", op=0.85)
    by = [W(yt, 12, 3)[0], W(yt, 95, 26)[0]]
    tv.poly([(-17.5, by[0]), (17.5, by[0]), (17.5, by[1]), (-17.5, by[1])], stroke=BOXS, sw=1, dash="5,3")
    x, y = tv.p(-38, -6); sh.text(x, y + 16, "contours z " + ", ".join(f"{z:g}" for z in contours) + "; red dashed: foot", size=11, fill="#666")
    # legend
    sh.text(28, 706, "1 mm = 4 px, grid 10 mm. Blue-grey: stack box s 12..95 (along the face from the rim), t 3..26; dashed in it: real board+glass and battery. Blue: rods 8 x 66.65 at x ±10.23. Red: CoM, flat foot.", size=11, fill="#555")
    if top_note:
        x, y = tv.p(-38, -6); sh.text(x, y + 31, top_note, size=11, fill="#666")
    if extra_section: extra_section(sh, fv, sv)
    sh.save(path)

def pebble_section(body, yt, zc=57.0):
    def draw(sh, fv, sv):
        fv.line((-36, zc), (36, zc), "#b03a8a", 1, "8,3,2,3"); fv.text(36, zc, "A", dx=4, dy=4, size=12, fill="#b03a8a", weight="bold"); fv.text(-36, zc, "A", dx=-14, dy=4, size=12, fill="#b03a8a", weight="bold")
        sv.line((-6, zc), (66, zc), "#b03a8a", 1, "8,3,2,3")
        P = body.section(zc, k=120); yfc = body.yf(zc); yin = yfc + T_IN / C15
        cav = clip_y(offset_in(P, 3.0), yin)
        Fb = front_branch(P); yo = lambda x: np.interp(x, Fb[:, 0], Fb[:, 1])
        def slot(x0):
            pts = []
            for sg in (-1, 1):
                u = 0.0
                while True:
                    x = x0 + sg * (4.05 + u); y = yin - 0.6 / C15 - u / C15
                    if y <= yo(x): break
                    u += 0.01
                pts.append((x, y, u))
            (xl, yl, ul), (xr, yr, ur) = pts
            mid = [(x, yo(x) - 0.4) for x in np.linspace(xl, xr, 12)]
            return [(x0 - 4.05, yin + 0.3), (x0 - 4.05, yin - 0.6 / C15), (xl, yl - 0.0)] + mid + [(xr, yr), (x0 + 4.05, yin - 0.6 / C15), (x0 + 4.05, yin + 0.3)], (xl, xr)
        def content(v, lab=True):
            v.poly(P, fill="#d9d2c4", sw=1.4); v.poly(cav, fill="#ffffff", sw=0.9)
            edges = []
            for x0 in (-10.23, 10.23):
                S, e = slot(x0); edges.append(e); v.poly(S, fill="#ffffff", stroke="none")
                v.poly(S[1:-1], stroke=EDGE, sw=0.9, close=False)
                th = np.linspace(0, np.pi, 40); gy = yin + 0.5 / C15 - 0.05
                v.poly([(x0 + 4 * np.cos(t), gy - 4 / C15 * np.sin(t)) for t in th], fill=ROD, stroke="#1d5fa8", sw=0.8, op=0.55)
            g0 = yin + 0.5 / C15
            v.poly([(-15.6, g0), (15.6, g0), (15.6, g0 + 3.9 / C15), (-15.6, g0 + 3.9 / C15)], fill="#cfe3f5", stroke="#6f8fb0", sw=0.8, op=0.7)
            v.poly([(-16.675, g0 + 3.9 / C15), (16.675, g0 + 3.9 / C15), (16.675, g0 + 9.0 / C15), (-16.675, g0 + 9.0 / C15)], fill="#b9c6b0", stroke="#6c7a63", sw=0.8, op=0.7)
            v.poly([(-17.5, g0 + 9.1 / C15), (17.5, g0 + 9.1 / C15), (17.5, g0 + 19.1 / C15), (-17.5, g0 + 19.1 / C15)], fill="#c9c9d6", stroke="#77778c", sw=0.8, op=0.7)
            return edges
        # full section, 4 px/mm, front at the bottom
        v1 = View(sh, 190, 990 + 4 * P[:, 1].min() - 8)
        sh.text(40, 740, f"SECTION A–A  horizontal cut at z {zc:g}", size=12, fill="#666", weight="bold"); sh.text(40, 755, "1 mm = 4 px, front at the bottom", size=11, fill="#777")
        content(v1)
        v1.text(0, yin + 14.6 / C15, "battery", dy=4, size=10.5, fill="#555", anchor="middle"); v1.text(0, yin + 7 / C15, "board", dy=4, size=10.5, fill="#445", anchor="middle")
        # detail 12 px/mm
        v2 = View(sh, 772, 948 + 12 * (yfc - 1.2), k=12.0)
        sh.text(490, 740, "DETAIL 3x (1 mm = 12 px): the front wall in the same cut", size=12, fill="#666", weight="bold"); sh.text(490, 755, "outer face bowed across the width like the oval's, inner face flat;", size=11, fill="#777"); sh.text(490, 769, "slots: 8.1 x 0.6 land at the inner face, then 45° out to the bowed face, straight ends", size=11, fill="#777")
        clipid = "cl"
        (x0, y0), (x1, y1) = v2.p(-23.5, yfc + 12.2), v2.p(23.5, yfc - 1.2)
        sh.add(f'<clipPath id="{clipid}"><rect x="{x0:.1f}" y="{y0:.1f}" width="{x1-x0:.1f}" height="{y1-y0:.1f}"/></clipPath><g clip-path="url(#{clipid})">')
        edges = content(v2); sh.add("</g>")
        sh.add(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1-x0:.1f}" height="{y1-y0:.1f}" fill="none" stroke="#cfcfcf"/>')
        tc = (yin - yfc) * C15; te = (yin - yo(15.6)) * C15; ts = (yin - yo(10.23)) * C15; t9 = (yin - yo(15.9)) * C15
        v2.line((0, yfc), (0, yin), "#b03a8a", 1.4); v2.text(0, (yfc + yin) / 2, f"{tc:.2f}", dx=5, dy=4, size=12, fill="#b03a8a", weight="bold")
        v2.line((15.6, yo(15.6)), (15.6, yin), "#b03a8a", 1.4); v2.text(15.6, (yo(15.6) + yin) / 2, f"{te:.2f}", dx=5, dy=4, size=12, fill="#b03a8a", weight="bold")
        br = edges[1][0] - edges[0][1]
        for x0, lab, an in ((-10.23, f"opening {edges[0][1]-edges[0][0]:.1f}", "middle"), (0, f"bridge {br:.1f}", "middle"), (5.2, "rod 8 x 4, crown %.2f under the face" % ((yin + 0.5 / C15 - 0.05 - 4 / C15 - yo(10.23)) * C15), "start")):
            v2.text(x0, yfc - 1.2, lab, dy=15, size=11, fill="#555", anchor=an)
        v2.text(0, yin + 2.6, "glass 31.2 x 3.9", dy=3, size=11, fill="#456", anchor="middle")
        v2.text(0, yin + 7.4, "board", dy=3, size=11, fill="#454", anchor="middle")
        v2.text(-19.6, yin + 1.2, "x", size=1, fill="#fff")
        sh.text(490, 990, f"Wall, perpendicular to the face (this cut shows it x1.035): {tc:.2f} on the centre line, {ts:.2f} at the slot centre,", size=11, fill="#555")
        sh.text(490, 1004, f"{te:.2f} at x 15.6, {t9:.2f} at x 15.9 (oval: 4.55 / 4.16 / 3.21 / 3.00). The bow is the same at every height of the face;", size=11, fill="#555")
        sh.text(490, 1018, "along the lean the face is straight over the slots (a crown of up to 0.5 over their 67 mm is possible, see the text).", size=11, fill="#555")
        return dict(tc=tc, te=te, ts=ts, bridge=br, opening=edges[0][1] - edges[0][0])
    return draw
