"""Fault injection for the round-7 checks: each fault must raise (FIRED), each baseline must pass (SILENT). The faulty part is
built separately; the checks keep the design values. Run from cad/desk after a build with ROLY_DUMP=<file>:
~/.venvs/cad/bin/python rolypoly_faults.py <file>"""
import sys, pickle, types
sys.path.insert(0, '.')
import rolypoly as rp
from build123d import Pos
D = pickle.loads(open(sys.argv[1], 'rb').read())
body, blank, cups, bat, bd, rods, cast, seg_sets, spots = (D[k] for k in ("body", "blank", "cups", "bat", "bd", "rods", "cast", "seg_sets", "spots"))
S7 = types.SimpleNamespace(outer=D["outer7"])
box = rp.box
X, Z, YB = rp.HEAD_X, rp.CABLE_Z, rp.Y_BACK_OUT
RES = []


def run(name, fn, expect=True):
    """expect True: a fault (must FIRE); False: a baseline (must stay SILENT)."""
    try:
        fn()
        fired, msg = False, ""
    except AssertionError as e:
        fired, msg = True, str(e)[:150]
    ok = fired == expect
    RES.append(ok)
    print(f"{'ok  ' if ok else 'BAD '} {'FIRED ' if fired else 'SILENT'}  {name}{': ' + msg if fired else ''}", flush=True)


def uc(**kw):
    a = dict(body=body, cups=cups, bat=bat, bd=bd, rods=rods, cast=cast, seg_sets=seg_sets)
    a.update({k: v for k, v in kw.items() if k in a})
    return rp.usb_checks(a["body"], a["cups"], a["bat"], a["bd"], a["rods"], a["cast"], a["seg_sets"],
                         **{k: v for k, v in kw.items() if k in ("dz", "dx")})


# ---- round 6's USB faults (unchanged but for the door) --------------------------------------------------------------
run("USB: no fault", lambda: uc(), expect=False)
run("USB: head + cable 2 mm down (cups / cast)", lambda: uc(dz=-2.0))
run("USB: obstruction in the cable passage (body notch)", lambda: uc(body=body + box(X - 0.3, X + 0.3, YB - 1.5, YB - 1.0, Z + 2.55, Z + 2.75)))
run("USB: head 0.6 up (plug's way up: battery)", lambda: uc(dz=0.6))
orig = rp.usb_solids


def cable_up(dz=0.0, dx=0.0):
    u = orig(dz, dx)
    u["usb-cable"] = orig(1.5, dx)["usb-cable"]
    return u


rp.usb_solids = cable_up
run("USB: cable 1.5 up (laid into the body's notch)", lambda: uc())
rp.usb_solids = orig
run("USB: cup-rock: a lip in its notch's open top (cup off)", lambda: uc(cups=dict(rock=cups["rock"] + box(X + 2.7, X + 2.8, YB - 2.0, YB - 1.0, 21.8, 22.0), flat=cups["flat"])))
run("USB: a boss-like block 0.3 over the cable's inner run (body)", lambda: uc(body=body + box(X - 1, X + 1, 18, 19, Z + 2.8, Z + 3.2)))
ss = dict(seg_sets)
c_, sg = ss["cup-flat"]
ss["cup-flat"] = (c_, sg + [box(X - 6, X + 6, rp.HEAD_Y0, rp.HEAD_Y0 + 19, 13.4, 17.4)])
run("USB: a flat-cup segment under the head (0.1 below it)", lambda: uc(seg_sets=ss))

# ---- new round 7 checks ----------------------------------------------------------------------------------------------
# 1. the flat zone and its blend (designed surface): a creased blend, and a plane too far forward for the zone
run("flat zone: the built surface", lambda: rp.flat_zone_check(), expect=False)
run("flat zone: blend with a linear ramp (crease)", lambda: rp.flat_zone_check(sh=rp.face_shape(rp.FACE_Y, ease=lambda t: t)))
run("flat zone: plane 0.5 further forward (natural surface creeps into the zone)",
    lambda: rp.flat_zone_check(sh=rp.face_shape(rp.FACE_Y - 0.5), face=rp.FACE_Y - 0.5))
# 2. the front's thickness along the slot edges: a 0.2 skin proud of the face beside the left slot's top
x_l = rp.TUBE_X[0] - rp.FACE_OPEN / 2
zt = rp.AA_ZC + rp.SLOT_L / 2
run("front thickness: the body", lambda: rp.front_thickness_check(body), expect=False)
run("front thickness: 0.2 proud beside the left slot's top", lambda: rp.front_thickness_check(
    body + box(x_l - 1.5, x_l - 0.02, rp.FACE_Y - 0.2, rp.FACE_Y + 0.5, zt - 8, zt - 4)))
# 3. the inner land under the glass: a 0.2 rib behind it, and a 0.5 dent into it
run("inner land: the body", lambda: rp.land_check(body), expect=False)
run("inner land: a 0.2 rib behind the land plane", lambda: rp.land_check(
    body + box(rp.LAND_X[0] + 0.5, rp.LAND_X[0] + 2.5, rp.Y_LAND - 0.5, rp.Y_LAND + 0.2, 60, 62)))
run("inner land: a 0.5 dent in the land at the glass's corner", lambda: rp.land_check(
    body - box(rp.LAND_X[0] - 1, rp.LAND_X[0] + 3, rp.Y_LAND - 0.5, rp.Y_LAND + 1, rp.LAND_Z[1] - 3, rp.LAND_Z[1] + 1)))


# 4. the slots' land, measured on a separately cut front (the design's SLOT_W / RIM stay as they are)
def cut(**kw):
    b = blank
    for x in rp.TUBE_X:
        b = b - rp.slot_cutter(x, **kw)
    return b


run("slot land: the body", lambda: rp.slot_land_check(body), expect=False)
run("slot land: front blank cut as designed", lambda: rp.slot_land_check(cut()), expect=False)
run("slot land: cut 8.2 wide", lambda: rp.slot_land_check(cut(w=8.2)))
run("slot land: knife edge (no land)", lambda: rp.slot_land_check(cut(rim=0.0)))
# 5. the board's way in: a rib 0.1 beside the PCB's up move, and a lip in a slot's land in the rod's way forward
bb = rp.board_sweeps()[("pcb", "up")].bounding_box()
rb = rods["rod-l"].bounding_box()
run("board's way in: the body", lambda: rp.board_way_check(body), expect=False)
run("board's way in: a rib 0.1 beside the PCB's up move", lambda: rp.board_way_check(
    body + box(bb.min.X - 20, bb.min.X - 0.1, bb.min.Y, bb.max.Y, 70, 72)))
run("board's way in: a 0.2 lip in the left slot's land (rod's way forward)", lambda: rp.board_way_check(
    body + box(rb.min.X - 0.2, rb.min.X + 0.15, rp.Y_LAND - 0.6, rp.Y_LAND, 60, 62)))
# 6. the battery's way in: a rib 0.1 beside its last move up
bs = rp.battery_sweeps()
b2 = (bs.get("up to the seat") or bs["up"]).bounding_box()
run("battery's way in: the body", lambda: rp.battery_way_check(body, bd), expect=False)
run("battery's way in: a rib 0.1 beside its way up", lambda: rp.battery_way_check(
    body + box(b2.max.X + 0.1, b2.max.X + 20, b2.min.Y, b2.max.Y, 50, 52), bd))
# 7. the trim spots: one pushed 0.3 into the wall, one floating 0.5 off it, the battery seated 12 further back
x0 = rp.TRIM_SPOTS[0]
rp.place_spots(body)                                       # the reference placement (the build's)
n_ = rp.SPOTS[x0]["R"][:, 1]                               # into the wall
run("trim spots: as placed", lambda: rp.trim_spot_check(body, bat, spots), expect=False)
run("trim spots: one 0.3 into the back wall", lambda: rp.trim_spot_check(body, bat, {**spots, x0: Pos(*(0.3 * n_)) * spots[x0]}))
run("trim spots: one floating 0.5 off the wall", lambda: rp.trim_spot_check(body, bat, {**spots, x0: Pos(*(-0.5 * n_)) * spots[x0]}))
run("trim spots: battery seated 12 further back", lambda: rp.trim_spot_check(body, Pos(0, 12, 0) * bat, spots))
# 8. the logo's clearance to the zone's blend: the letters moved left onto the blend
run("logo clearance: as built", lambda: rp.check(rp.logo_outside(S7)["clr"] >= rp.LOGO_ZONE_CLR, "logo on the zone's blend"), expect=False)
run("logo clearance: letters at x 24", lambda: rp.check(rp.logo_outside(S7, 24.0)["clr"] >= rp.LOGO_ZONE_CLR, "logo on the zone's blend"))

# ---- round 7b: the logo's stencil pocket and the stencil ---------------------------------------------------------------
import math, tempfile, pathlib
import numpy as np
from build123d import Plane, Rectangle, extrude, Polygon, Solid
PK, led, after = D["pocket"], D["led"], D["after"]
F = PK["F"]
p_, n_l, xd, up = F
outer_face = [f for f in rp.bspline_faces(D["outer7"])][0]


def frame_box(u0, u1, v0, v1, w0, w1):
    """A box in the logo's frame: u, v across, w0..w1 behind the logo's tangent plane."""
    pl = Plane(origin=tuple(map(float, rp.frame_pt(F, (u0 + u1) / 2, (v0 + v1) / 2, w0))), x_dir=tuple(map(float, xd)), z_dir=tuple(map(float, -n_l)))
    return extrude(pl * Rectangle(u1 - u0, v1 - v0), w1 - w0)


ST = rp.stencil_block(PK)
top_s = float(rp.depths_along(PK["band"], F, [(0.0, PK["ph"] / 2 - 0.01)])[0])
run("logo pocket floor: the body", lambda: rp.pocket_floor_check(body, PK, outer_face), expect=False)
run("logo pocket floor: skin 0.3 thinner over 4 x 2 at its centre", lambda: rp.pocket_floor_check(
    body - frame_box(-2, 2, -1, 1, rp.LOGO_SKIN - 0.3, rp.LOGO_SKIN + 0.5), PK, outer_face))
run("logo pocket floor: a 0.5 plate left over its right half (sealed there)", lambda: rp.pocket_floor_check(
    body + (frame_box(0.5, PK["pw"] / 2 - 0.3, -PK["ph"] / 2 + 0.3, PK["ph"] / 2 - 0.3, 3.0, 3.5) & PK["cut"]), PK, outer_face))
run("logo pocket outline: the body", lambda: rp.pocket_outline_check(body, PK), expect=False)
run("logo pocket outline: 0.3 filled along its left edge", lambda: rp.pocket_outline_check(
    body + (frame_box(-PK["pw"] / 2 - 1, -PK["pw"] / 2 + 0.3, -3, 3, 0, 8) & PK["cut"]), PK))


def roof(b):
    with tempfile.TemporaryDirectory() as td:
        f = pathlib.Path(td) / "b.stl"
        rp.write_stl(b, f)
        return rp.logo_roof_check(PK, f)


run("logo pocket overhang: the body", lambda: roof(body), expect=False)
run("logo pocket overhang: a flat ceiling 1.5 above its top edge, from 0.8 behind the skin", lambda: roof(
    body - frame_box(-3, 3, PK["ph"] / 2 - 1.0, PK["ph"] / 2 + 1.5, top_s + 0.8, PK["wF"])))
run("logo stencil: as designed", lambda: rp.stencil_check(body, PK, ST, after), expect=False)
run("logo stencil: 0.15 oversize per side (0.05 over the pocket's floor)", lambda: rp.stencil_check(body, PK, rp.stencil_block(PK, clr=-0.05), after))
run("logo stencil: a 0.5 rib across its way in, 3 behind its back", lambda: rp.stencil_check(
    body + frame_box(-1, 1, -2, 2, ST["w_back"] + 3.0, ST["w_back"] + 3.5), PK, ST, after))
run("logo stencil: 1.2 thicker (hits the LEDs' room)", lambda: rp.stencil_check(body, PK, rp.stencil_block(PK, t_min=rp.STENCIL_T_MIN + 1.2), after))
run("logo stencil: the LEDs' room 0.5 further out (towards the logo)", lambda: rp.stencil_check(
    body, PK, ST, {**after, "LEDs' room": Pos(*map(float, 0.5 * n_l)) * led}))
ST_parts = rp.stencil_parts(PK, ST, (None,))
run("logo stencil apertures: as designed", lambda: rp.stencil_print(PK, ST, ST_parts), expect=False)


def mirrored():
    st = ST["solid"]
    pl = Plane(origin=tuple(map(float, rp.frame_pt(F, 0, 0, PK["w_front"] - 1.0))), x_dir=tuple(map(float, xd)), z_dir=tuple(map(float, n_l)))
    for poly in rp.hw.letters_mm(rp.LOGO_W):
        st = st - extrude(pl * Polygon(*[(-u, v) for u, v in poly], align=None), ST["w_back"] - PK["w_front"] + 3.0, dir=tuple(map(float, -n_l)))
    return rp.stencil_print(PK, ST, [(rp.one_solid(st, "mirrored"), rp.hw.STRIP_PER_MM * rp.LOGO_W)])


run("logo stencil apertures: letters mirrored", mirrored)
print(f"\n{sum(RES)} of {len(RES)} as expected" + ("" if all(RES) else ": SOME CHECKS DID NOT BEHAVE"))
