#!/usr/bin/env python3
"""Massing study for the desk housing: ribbon (front + top, rolled) over a U cradle (sides + back).
Not a production model: solid cradle, no cavity. Only for clay views and proportions.

  ~/.venvs/cad/bin/python massing.py <tag> [KEY=value ...]

WEDGE=0: a slab of constant depth D that leans back by LEAN (the back leans too).
WEDGE=1: the front leans back by LEAN, the back is vertical, the top is level and TOP long: the sides narrow upwards.
SLOT_PROFILE: 0 = edge rolled in all round (SLOT_R); 1 = 45 deg chamfer on the long sides only, the ends straight;
              2 = 45 deg chamfer on all four sides. The chamfer runs from the face down to SLOT_LAND above the wall's
              inner face (0 = to a zero rim).
Body frame: front face y = 0, z along the face. World frame: after the lean, z up, desk at z = 0.
"""
import sys, math, pathlib
from build123d import *

P = dict(W=50.0, D=30.0, H=108.0, T=3.0, RW=15.0, RB=10.0, RE=1.5, LEAN=6.0, WEDGE=0, TOP=14.0,
         PLINTH_H=2.5, PLINTH_IN=2.0, SLOT_W=8.6, SLOT_L=69.45, SLOT_X=10.23, SLOT_Z0=21.0,
         SLOT_R=2.0, SLOT_PROFILE=0, SLOT_LAND=0.0, ROD_R=4.0, ROD_L=68.65, GASKET=0.5, TAPE=0.15,
         LOGO_W=15.0, LOGO_H=9.5, LOGO_Y=11.5, LOGO_Z=58.0)   # logo box centre: body frame (slab), world (wedge)
tag = sys.argv[1] if len(sys.argv) > 1 else "a"
for kv in sys.argv[2:]:
    k, v = kv.split("=")
    P[k] = float(v)
W, D, H, T, RW, RB, RE, LEAN = (P[k] for k in ("W", "D", "H", "T", "RW", "RB", "RE", "LEAN"))
WEDGE = bool(P["WEDGE"])
th = math.radians(LEAN)
s_, c_ = math.sin(th), math.cos(th)
EXT = 12.0   # body below z = 0 before the lean cut
OUT = pathlib.Path(__file__).parent / f"out-{tag}"
OUT.mkdir(exist_ok=True)


def near(shape_list, pt, n=1):
    return ShapeList(sorted(shape_list, key=lambda s: (s.center() - Vector(*pt)).length)[:n])


def poly_prism(pts, fillets, half_x):
    """YZ polygon (sketch-local u = Y, v = Z), corners rounded per {index: radius}, extruded +-half_x in X."""
    with BuildSketch(Plane.YZ) as s:
        with BuildLine():
            Polyline(*pts, close=True)
        make_face()
        for i, r in fillets.items():
            if r > 0:
                fillet(near(s.vertices(), (*pts[i], 0)), r)
    return extrude(s.sketch, half_x, both=True)


def plan_prism(y0, y1, z0, z1):
    with BuildSketch(Plane.XY) as plan:
        with Locations((0, (y0 + y1) / 2)):
            Rectangle(W, y1 - y0)
        fillet(near(plan.vertices(), (-W / 2, y1, 0)) + near(plan.vertices(), (W / 2, y1, 0)), RB)
    return extrude(plan.sketch.moved(Location((0, 0, z0))), z1 - z0)


if WEDGE:
    u, dn = (c_, s_), (s_, -c_)                    # body-frame directions of the world's "back" and "down"
    p1 = (0.0, H)                                  # H = face length up to the virtual top-front corner
    p2 = (P["TOP"] * u[0], H + P["TOP"] * u[1])
    p3 = (p2[0] + dn[0] * (H + 40), p2[1] + dn[1] * (H + 40))
    outer = [(0.0, -EXT), p1, p2, p3]
    q = (T, H - T * c_ + T * (1 - s_) / c_ * s_)   # inner corner: the front and the top offset inwards by T
    cc = (q[0] + 200 * u[0], q[1] + 200 * u[1])
    inner_pts = [(T, -60.0), q, cc, (cc[0] + 500 * dn[0], cc[1] + 500 * dn[1])]
    tang = RW * math.tan(math.radians(90 - LEAN) / 2)
    depth = P["TOP"] + H * s_                      # world y of the back plane
else:
    outer = [(0.0, -EXT), (0.0, H), (D, H), (D, -EXT)]
    inner_pts = [(T, -EXT - 1), (T, H - T), (D + 5, H - T), (D + 5, -EXT - 1)]
    tang = RW
    depth = D / c_

env = poly_prism(outer, {1: RW}, W / 2 + (1 if not WEDGE else 0))
if not WEDGE:
    env &= plan_prism(0, D, -EXT, H)

# soften the ribbon's outer edges: front verticals, the roll, the top
if RE > 0:
    es = [e for e in env.edges()
          if (abs(abs(e.center().X) - W / 2) < 0.01 and (e.center().Y < 0.01 or e.center().Z > H - tang - 0.01))
          or (not WEDGE and e.center().Z > H - 0.01 and e.center().Y > D - RB - 0.01)]
    try:
        env = fillet(es, RE)
    except Exception as ex:
        print("edge fillet failed:", ex)

inner = poly_prism(inner_pts, {1: RW - T}, W)
ribbon = env - inner
cradle = env & inner

# slots through the ribbon, a pocket for the glass behind
glass_y = T + P["GASKET"]
for sx in (-1, 1):
    x0 = sx * P["SLOT_X"]
    with BuildSketch(Plane.XZ.offset(1)) as sk:      # XZ normal is -Y; start 1 mm in front of the face
        with Locations((x0, P["SLOT_Z0"] + P["SLOT_L"] / 2)):
            RectangleRounded(P["SLOT_W"], P["SLOT_L"], 1.0 if P["SLOT_PROFILE"] == 0 else 0.3)
    ribbon -= extrude(sk.sketch, -(glass_y + 1))
    prof, cdep = int(P["SLOT_PROFILE"]), T - P["SLOT_LAND"]
    rim = [e for e in ribbon.edges() if abs(e.center().Y) < 0.01 and abs(e.center().X - x0) < P["SLOT_W"]
           and P["SLOT_Z0"] - 1 < e.center().Z < P["SLOT_Z0"] + P["SLOT_L"] + 1]
    try:
        if prof == 0 and P["SLOT_R"] > 0:
            ribbon = fillet(rim, P["SLOT_R"])
        elif prof == 1:      # a V channel along the tube; its ends stay straight walls
            hw = P["SLOT_W"] / 2
            with BuildSketch(Plane.XY.offset(P["SLOT_Z0"])) as ch:
                with BuildLine():
                    Polyline((x0 - hw - cdep - 1, -1), (x0 + hw + cdep + 1, -1), (x0 + hw, cdep), (x0 - hw, cdep), close=True)
                make_face()
            ribbon -= extrude(ch.sketch, P["SLOT_L"])
        elif prof == 2:
            ribbon = chamfer(rim, min(cdep, T - 0.02))
    except Exception as ex:
        print("slot profile failed:", ex)
gz0, gz1 = P["SLOT_Z0"] - 8.4, P["SLOT_Z0"] + P["SLOT_L"] - 0.9 + 2.6
pocket = Box(32, 2.5, gz1 - gz0, align=(Align.CENTER, Align.MIN, Align.MIN)).moved(Location((0, T, gz0)))
cradle -= pocket
glass = Box(31.2, 2.0, gz1 - gz0, align=(Align.CENTER, Align.MIN, Align.MIN)).moved(Location((0, glass_y, gz0)))

rods = []
for sx in (-1, 1):
    with BuildSketch(Plane.XY) as rs:
        Circle(P["ROD_R"])
        Rectangle(3 * P["ROD_R"], 2 * P["ROD_R"], align=(Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    rod = extrude(rs.sketch, P["ROD_L"])
    rz0 = P["SLOT_Z0"] + (P["SLOT_L"] - P["ROD_L"]) / 2
    rods.append(rod.moved(Location((sx * P["SLOT_X"], glass_y - P["TAPE"], rz0))))

logo = Box(0.3, P["LOGO_W"], P["LOGO_H"]).moved(Location((-W / 2, P["LOGO_Y"], P["LOGO_Z"])))   # placeholder, left side

# lean back, cut the bottom level, round the rear corners (wedge), inset plinth
parts = {"ribbon": ribbon, "cradle": cradle, "glass": glass, "rod-l": rods[0], "rod-r": rods[1]}
below = Box(600, 600, 300, align=(Align.CENTER, Align.CENTER, Align.MAX))
up = Location((0, 0, P["PLINTH_H"]))
for k in parts:
    parts[k] = parts[k].rotate(Axis.X, -LEAN) - below
    if WEDGE and k in ("ribbon", "cradle"):
        parts[k] &= plan_prism(-20, depth, -5, 2 * H)
    parts[k] = parts[k].moved(up)
parts["logo"] = logo.moved(up) if WEDGE else logo.rotate(Axis.X, -LEAN).moved(up)

ins = P["PLINTH_IN"]
with BuildSketch(Plane.XY) as ps:
    with Locations((0, depth / 2)):
        Rectangle(W - 2 * ins, depth - 2 * ins)
    vs = ps.vertices()
    fillet(near(vs, (-W / 2, depth, 0)) + near(vs, (W / 2, depth, 0)), max(RB - ins, 0.5))
    fillet(near(ps.vertices(), (-W / 2, 0, 0)) + near(ps.vertices(), (W / 2, 0, 0)), 1.0)
parts["plinth"] = extrude(ps.sketch, P["PLINTH_H"])

import json
def world(y, z):
    return [-P["SLOT_X"], y * c_ + z * s_, -y * s_ + z * c_ + P["PLINTH_H"]]
(OUT / "focus.json").write_text(json.dumps({"top": world(0, P["SLOT_Z0"] + P["SLOT_L"]), "bottom": world(0, P["SLOT_Z0"]),
                                            "normal": [0, -c_, s_], "up": [0, s_, c_]}))
for k, p in parts.items():
    export_stl(p, str(OUT / f"{k}.stl"), tolerance=0.02, angular_tolerance=0.08)
bb = Compound(children=[p for k, p in parts.items() if k != "logo"]).bounding_box()
print(f"{tag}: {'wedge' if WEDGE else 'slab'}, front {LEAN:.0f} deg -> bbox {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f}")
print(f"  slot along the face {P['SLOT_Z0']:.1f}..{P['SLOT_Z0'] + P['SLOT_L']:.1f}, the roll starts at {H - tang:.1f}; base depth {depth:.1f}")
if WEDGE:
    for z in (15.0, 25.0, 50.0, 75.0):   # flat side width (ribbon seam -> start of the rear corner) at world height z
        print(f"  side flat at z {z:.0f}: {depth - RB - (z * s_ / c_ + T / c_):.1f}")
else:
    print(f"  side flat between the seam and the rear corner {D - T - RB:.1f}")
