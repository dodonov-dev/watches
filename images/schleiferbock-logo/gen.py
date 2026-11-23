import math
def poly(pts): return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in pts) + " Z"
def spark(x0, y0, ang, r0, L, w):
    a = math.radians(ang); ux, uy = math.cos(a), math.sin(a); nx, ny = -uy, ux
    p = lambda t, o: (x0 + ux*(r0+t*L) + nx*o, y0 + uy*(r0+t*L) + ny*o)
    return poly([p(0, 0), p(0.3, w/2), p(1, 0), p(0.3, -w/2)])
GOAT = ("M 7 23 L 13 27 C 22 25, 32 25, 38 24 L 42 15 L 45 12 C 49 12, 52 16, 55 21 L 56 24 "
        "C 55 26, 53 27, 51 26 L 50 33 L 47 27 C 45 30, 44 33, 44 36 L 44 50 L 39.5 50 L 40 37 "
        "C 32 38, 24 38, 18 37 L 18 50 L 13.5 50 L 13 36 C 11 33, 11 30, 12 28 Z")
HORN = "M 42 16 C 40 9, 35 4, 28 4 C 35 2, 43 5, 46 13 Z"
EAR = "M 42.5 17 L 35 20.5 L 36.5 22.5 L 44 20 Z"
def svg(name, groups, vb):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">', '<g fill="#000" fill-rule="nonzero">']
    for tr, paths in groups:
        out.append(f' <g transform="{tr}">' if tr else ' <g>')
        out += [f'  <path d="{d}"/>' for d in paths]
        out.append(' </g>')
    out += ['</g>', '</svg>']
    open(name, "w").write("\n".join(out) + "\n")
# A: standing goat + grinding wheel, sparks off the far side
cx, cy, r = 80, 32, 18
sp = [spark(cx, cy, a, r + 3, L, 4) for a, L in ((-60, 15), (-30, 18), (0, 13))]
svg("A.svg", [("translate(0,6)", [GOAT, HORN, EAR]),
              ("", [f"M {cx-r} {cy} a {r} {r} 0 1 0 {2*r} 0 a {r} {r} 0 1 0 {-2*r} 0 Z"] + sp)], "-2 -6 120 66")
def gear(cx, cy, ro, ri, n, tw=0.42):
    pts = []
    for i in range(n):
        a0, da = 2*math.pi*i/n, 2*math.pi/n
        for f, rr in ((0, ri), (0.5 - tw/2 - 0.07, ri), (0.5 - tw/2, ro), (0.5 + tw/2, ro), (0.5 + tw/2 + 0.07, ri)):
            a = a0 + f*da; pts.append((cx + rr*math.cos(a), cy + rr*math.sin(a)))
    return poly(pts)
def disc(cx, cy, r): return f"M {cx-r} {cy} a {r} {r} 0 1 0 {2*r} 0 a {r} {r} 0 1 0 {-2*r} 0 Z"
def fan(cx, cy, r, src, angs):
    sx, sy = cx + r*math.cos(math.radians(src)), cy + r*math.sin(math.radians(src))
    return [spark(sx, sy, a, 3.5, L, 4.2) for a, L in angs]
FAN = ((-50, 15), (-20, 19), (10, 14))
cx, cy, r = 79, 30, 17
svg("B.svg", [("translate(0,4)", [GOAT, HORN, EAR]), ("", [disc(cx, cy, r)] + fan(cx, cy, r, -25, FAN))], "4 -6 116 62")
svg("C.svg", [("translate(0,4)", [GOAT, HORN, EAR]), ("", [gear(cx, cy, r + 1, r - 3, 10)] + fan(cx, cy, r + 1, -25, FAN))], "4 -6 116 62")
