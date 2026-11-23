import math, re, sys
from hd import HEAD_L, HORN_L
exec(open("head2.py").read().split("# head frame")[0].split("import math, re, sys")[1])
TILT, POLL, S = 25, (92, 19), 1.15
def T(x, y):
    a = math.radians(-TILT); c, s = math.cos(a), math.sin(a)
    return (POLL[0] + S*(x*c - y*s), POLL[1] + S*(x*s + y*c))
def tp(d):
    out = []
    for tok in re.findall(r"[MLCZ]|[-\d.]+\s*,?\s*[-\d.]+", d):
        if tok in "MLCZ": out.append(tok); continue
        x, y = map(float, re.split(r"[ ,]+", tok.strip())); X, Y = T(x, y); out.append(f"{X:.2f} {Y:.2f}")
    return " ".join(out)
f = lambda p: f"{p[0]:.2f} {p[1]:.2f}"
front, back = HEAD_L.split(" L -8 12 ")[0], HEAD_L.split("C 8 13, 9.5 9, 9.5 6.5 ")[1]
th = T(-12.5, 11)
HEAD = (tp(front)
        + f" C {f((th[0]+4, th[1]+3))}, {f((90, 46))}, {f((90, 55))}"                          # throat
        + " L 64.5 57.4 C 63 58.4, 62.4 58.2, 60.6 57.0 C 56.6 56.8, 54.6 60.6, 55.4 65.0 L 61 65.8 C 61.8 64.8, 62.8 64.4, 64.5 64.6"  # foreleg, pastern, hoof
        + f" L 93 66.5 L 95 76 L 110 76 C 109 56, 108 36, {f(T(9.5, 6.5))} "                     # chest, bust, back of neck
        + tp(back))
HORN = tp(HORN_L)
cx, cy, r = 16, 52, 19
ca = math.radians(-24); rim = (cx + r*math.cos(ca), cy + r*math.sin(ca))
tip = (cx + (r - 1.5)*math.cos(ca), cy + (r - 1.5)*math.sin(ca))    # blade tip bites into the wheel: one cut, no sliver
def knife(hoof, tip, handle=9.0, hw=2.2, bolster=1.0, bw=2.6, blade=4.2, nose=1.1):
    # local frame: u from the hoof toward the tip, v>0 = spine (up). Rounded butt, bolster, straight spine,
    # belly curving up to a blunt nose (nose half-width) that sinks into the wheel.
    ux, uy = tip[0] - hoof[0], tip[1] - hoof[1]; L = math.hypot(ux, uy); ux, uy = ux/L, uy/L
    vx, vy = uy, -ux
    if vy > 0: vx, vy = -vx, -vy
    P = lambda u, v: (hoof[0] + ux*u + vx*v, hoof[1] + uy*u + vy*v)
    b0 = handle + bolster
    pts = [P(handle, hw)]
    pts += [P(-1 + hw*math.cos(a), hw*math.sin(a)) for a in [math.pi/2 + k*math.pi/8 for k in range(9)]]
    pts += [P(handle, -hw), P(handle, -bw), P(b0, -bw), P(b0 + 0.3, -blade)]
    for k in range(1, 15):
        t = k / 14; pts.append(P(b0 + 0.6 + (L - b0 - 0.6)*t, -blade + (blade + nose - 0.4)*t**2.4))
    pts += [P(L, blade - 0.6), P(L - 1.2, blade), P(b0 + 0.6, blade), P(b0, bw), P(handle, bw)]
    return poly(pts)
TOOL = knife((59, 60.5), tip)
SPARKS = [spark(*rim, a, 9.5, L, 4.4) for a, L in ((-42, 10), (-72, 13), (-102, 10))]
def write(name, wheel):
    paths = [HEAD, HORN, TOOL, wheel] + SPARKS
    body = "\n".join(f'    <path d="{d}"/>' for d in paths)
    open(name, "w").write(f'''<svg xmlns="http://www.w3.org/2000/svg" width="24mm" height="16.98mm" viewBox="-6 -11 130 92">
  <title>Schleiferbock</title>
  <!-- flat, single fill, no holes/islands: union all paths (knife tip overlaps the wheel on purpose); sparks are separate cuts. 1 unit = 0.185 mm at 24 mm wide -->
  <g fill="#000">
{body}
  </g>
</svg>
''')
def gear_ph(phase_deg, n=10, tw=0.42):
    pts = []
    for k in range(n):
        a0, da = 2*math.pi*k/n + math.radians(phase_deg), 2*math.pi/n
        for fr, rr in ((0, r - 3), (0.5 - tw/2 - 0.07, r - 3), (0.5 - tw/2, r + 1), (0.5 + tw/2, r + 1), (0.5 + tw/2 + 0.07, r - 3)):
            a = a0 + fr*da; pts.append((cx + rr*math.cos(a), cy + rr*math.sin(a)))
    return poly(pts)
write(sys.argv[1], gear_ph(-24 - 18))   # a tooth centred on the contact point
write(sys.argv[2], disc(cx, cy, r))
