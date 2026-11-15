#!/usr/bin/env python3
"""Massing study: an oval ("shampoo bottle") body. Superellipse plan extruded straight up, soft top edge, flat lid.
Solid, no cavity: only for clay views and proportions. Writes the part names clay.py expects.

  ~/.venvs/cad/bin/python oval.py <tag> [KEY=value ...]   then   clay.py <tag> two

Frame: front apex at y = 0, back at y = D, desk at z = 0.
"""
import sys, math, json, pathlib
from build123d import *

P = dict(W=56.0, D=36.0, H=110.0, N=2.8, RT=6.0, LID=3.0, LID_IN=1.5,
         FRONT_C=4.5,                       # front wall at the centre line; the inner face behind it is flat
         SLOT_W=8.6, SLOT_L=66.85, SLOT_X=10.23, SLOT_Z0=23.4, ROD_R=4.0, ROD_L=66.65, GASKET=0.5, TAPE=0.15)
tag = sys.argv[1] if len(sys.argv) > 1 else "oval"
for kv in sys.argv[2:]:
    k, v = kv.split("=")
    P[k] = float(v)
W, D, H, N = P["W"], P["D"], P["H"], P["N"]
OUT = pathlib.Path(__file__).parent / f"out-{tag}"
OUT.mkdir(exist_ok=True)


def plan(a, b, n=N, k=160):
    pts = []
    for i in range(k):
        t = 2 * math.pi * i / k
        c, s = math.cos(t), math.sin(t)
        pts.append((a * abs(c) ** (2 / n) * (1 if c >= 0 else -1), D / 2 + b * abs(s) ** (2 / n) * (1 if s >= 0 else -1)))
    with BuildSketch() as sk:
        with BuildLine():
            Spline(*pts, periodic=True)
        make_face()
    return sk.sketch


def front_y(x):
    """Outer front surface at x."""
    return D / 2 - D / 2 * (1 - abs(2 * x / W) ** N) ** (1 / N)


body = extrude(plan(W / 2, D / 2).moved(Location((0, 0, P["LID"]))), H - P["LID"])
body = fillet(body.edges().group_by(Axis.Z)[-1], P["RT"])
lid = extrude(plan(W / 2 - P["LID_IN"], D / 2 - P["LID_IN"]), P["LID"])

yin = P["FRONT_C"]                       # flat inner face of the front wall
glass_y = yin + P["GASKET"]
z0, z1 = P["SLOT_Z0"], P["SLOT_Z0"] + P["SLOT_L"]
hw = P["SLOT_W"] / 2
for sx in (-1, 1):
    x0 = sx * P["SLOT_X"]
    # 45 deg on the long sides, opening outwards from the inner face (zero rim); straight ends
    with BuildSketch(Plane.XY.offset(z0)) as ch:
        with BuildLine():
            Polyline((x0 - hw, yin + 0.01), (x0 + hw, yin + 0.01), (x0 + hw + yin + 2, -2), (x0 - hw - yin - 2, -2), close=True)
        make_face()
    body -= extrude(ch.sketch, P["SLOT_L"])
    body -= Box(P["SLOT_W"], 1.0, P["SLOT_L"], align=(Align.CENTER, Align.MIN, Align.MIN)).moved(Location((x0, yin - 0.01, z0)))
gz0, gz1 = z0 - 8.4, z1 - 0.9 + 2.6
body -= Box(32, 2.5, gz1 - gz0, align=(Align.CENTER, Align.MIN, Align.MIN)).moved(Location((0, yin, gz0)))
glass = Box(31.2, 2.0, gz1 - gz0, align=(Align.CENTER, Align.MIN, Align.MIN)).moved(Location((0, glass_y, gz0)))

rods = []
for sx in (-1, 1):
    with BuildSketch(Plane.XY) as rs:
        Circle(P["ROD_R"])
        Rectangle(3 * P["ROD_R"], 2 * P["ROD_R"], align=(Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    rod = extrude(rs.sketch, P["ROD_L"])
    rods.append(rod.moved(Location((sx * P["SLOT_X"], glass_y - P["TAPE"], z0 + (P["SLOT_L"] - P["ROD_L"]) / 2))))

hidden = Box(4, 4, 4).moved(Location((0, D / 2, H / 2 + 20)))      # clay.py wants these names; both sit inside the body
parts = {"ribbon": body, "cradle": hidden, "plinth": lid, "glass": glass, "rod-l": rods[0], "rod-r": rods[1],
         "logo": Box(2, 2, 2).moved(Location((0, D / 2, H / 2 + 30)))}
for k, p in parts.items():
    export_stl(p, str(OUT / f"{k}.stl"), tolerance=0.02, angular_tolerance=0.08)
(OUT / "focus.json").write_text(json.dumps({"top": [-P["SLOT_X"], front_y(P["SLOT_X"]), z1], "bottom": [-P["SLOT_X"], front_y(P["SLOT_X"]), z0],
                                            "normal": [0, -1, 0], "up": [0, 0, 1]}))

apex = P["ROD_R"] + P["TAPE"] - P["GASKET"]            # rod crown in front of the inner face
print(f"{tag}: oval {W:.0f} x {D:.0f} x {H:.0f}, superellipse n {N}")
for name, x in (("centre line", 0.0), ("slot inner edge", P["SLOT_X"] - hw), ("slot centre", P["SLOT_X"]),
                ("slot outer edge", P["SLOT_X"] + hw), ("glass edge", 15.6), ("cavity corner x 22", 22.0)):
    t = yin - front_y(x)
    print(f"  front wall at {name:<18} {t:5.2f}" + (f"   rod crown {apex - t:+.2f} to the face" if "slot" in name else ""))
