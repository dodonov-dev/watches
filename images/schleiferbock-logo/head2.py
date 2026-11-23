import math, re, sys
def poly(pts): return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in pts) + " Z"
def spark(x0, y0, ang, r0, L, w):
    a = math.radians(ang); ux, uy = math.cos(a), math.sin(a); nx, ny = -uy, ux
    p = lambda t, o: (x0 + ux*(r0+t*L) + nx*o, y0 + uy*(r0+t*L) + ny*o)
    return poly([p(0, 0), p(0.3, w/2), p(1, 0), p(0.3, -w/2)])
def gear(cx, cy, ro, ri, n, tw=0.42):
    pts = []
    for i in range(n):
        a0, da = 2*math.pi*i/n, 2*math.pi/n
        for f, rr in ((0, ri), (0.5 - tw/2 - 0.07, ri), (0.5 - tw/2, ro), (0.5 + tw/2, ro), (0.5 + tw/2 + 0.07, ri)):
            a = a0 + f*da; pts.append((cx + rr*math.cos(a), cy + rr*math.sin(a)))
    return poly(pts)
def disc(cx, cy, r): return f"M {cx-r:.2f} {cy} a {r} {r} 0 1 0 {2*r} 0 a {r} {r} 0 1 0 {-2*r} 0 Z"
# head frame: local face drawn horizontal facing left, poll at origin; tilted down TILT deg, poll placed at POLL
TILT, POLL, S = 30, (98, 20), 1.0
def T(x, y):
    a = math.radians(-TILT); c, s = math.cos(a), math.sin(a)
    return (POLL[0] + S*(x*c - y*s), POLL[1] + S*(x*s + y*c))
def tp(d):  # transform an absolute M/L/C path given in local coords
    out = []
    for tok in re.findall(r"[MLCZ]|[-\d.]+\s*,?\s*[-\d.]+", d):
        if tok in "MLCZ": out.append(tok); continue
        x, y = map(float, re.split(r"[ ,]+", tok.strip())); X, Y = T(x, y); out.append(f"{X:.2f} {Y:.2f}")
    return " ".join(out)
def f(p): return f"{p[0]:.2f} {p[1]:.2f}"
chin = T(-18, 7.5)
HEAD = (tp("M 3 -2.5 L -8 -3.5 L -13 -3.6 L -12 -0.6 L -15.5 -1.6 C -20 -1, -25 0, -28.5 1 C -31 2, -31 5.5, -28 6 L -18 7.5")
        + f" L {f((chin[0]+2, chin[1]+10))} L {f((chin[0]+6, chin[1]+1))}"                  # beard hangs straight down
        + " C 96 42, 95 46, 94 51"                                                          # throat
        + " L 70 47.5 L 64 47 L 60.5 49.5 L 64.5 51.5 L 60.5 54 L 64 56.5 L 70 55.5"        # foreleg + cloven hoof
        + " L 95 62 L 99 80 L 120 80 C 119 64, 116 52, 112 41 "                            # chest, bust, back of neck
        + tp("L 13 6 L 14 2.5 L 3 -0.5") + " Z")                                           # ear sticking back
HORN = tp("M -9 -3 C -6 -15, 7 -20, 16 -13 C 19 -10, 20 -6, 18.5 -2 C 16 -8, 9 -12, 1 -2.5 Z")
cx, cy, r = 27, 40, 19
ca = math.radians(16); rim = (cx + r*math.cos(ca), cy + r*math.sin(ca))
TOOL = poly([(rim[0] + 3, rim[1] - 1.6), (66, 50), (66, 53), (rim[0] + 2.6, rim[1] + 1.6)])
SPARKS = [spark(*rim, a, 6, L, 4.4) for a, L in ((50, 13), (82, 15), (114, 12))]
def write(name, wheel):
    paths = [HEAD, HORN, TOOL, wheel] + SPARKS
    body = "\n".join(f'    <path d="{d}"/>' for d in paths)
    open(name, "w").write(f'''<svg xmlns="http://www.w3.org/2000/svg" width="24mm" height="16.08mm" viewBox="4 0 115 77">
  <title>Schleiferbock</title>
  <!-- flat, single fill, no holes/islands: every path is a separate through-cut. 1 unit = 0.21 mm at 24 mm wide -->
  <g fill="#000">
{body}
  </g>
</svg>
''')
write(sys.argv[1], gear(cx, cy, r + 1, r - 3, 10))
write(sys.argv[2], disc(cx, cy, r))
