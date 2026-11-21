"""Fault injection for the round-6 checks: each fault must raise (FIRED). Run from cad/desk after a build with ROLY_DUMP=<file>: ~/.venvs/cad/bin/python rolypoly_faults.py <file>"""
import sys, pickle, traceback
sys.path.insert(0, '.')
import rolypoly as rp
D = pickle.loads(open(sys.argv[1], 'rb').read())
body, cups, door, bat, bd, rods, cast, seg_sets = (D[k] for k in ("body", "cups", "door", "bat", "bd", "rods", "cast", "seg_sets"))
box = rp.box
X, Z, YB = rp.HEAD_X, rp.CABLE_Z, rp.Y_BACK_OUT

def run(name, fn):
    try:
        fn()
    except AssertionError as e:
        print(f"FIRED   {name}: {str(e)[:160]}")
        return True
    print(f"SILENT  {name}")
    return False

def uc(**kw):
    a = dict(body=body, cups=cups, door=door, bat=bat, bd=bd, rods=rods, cast=cast, seg_sets=seg_sets)
    a.update(kw)
    return rp.usb_checks(a["body"], a["cups"], a["door"], a["bat"], a["bd"], a["rods"], a["cast"], a["seg_sets"], **{k: v for k, v in kw.items() if k in ("dz", "dx")})

print("baseline:", "passes" if not run("no fault (must be SILENT)", lambda: uc()) else "FAILS")
run("head + cable 2 mm down (cups / cast)", lambda: uc(dz=-2.0))
run("obstruction in the cable passage (body notch)", lambda: uc(body=body + box(X - 0.3, X + 0.3, YB - 1.5, YB - 1.0, Z + 2.55, Z + 2.75)))
run("head 0.6 up (plug's way up: battery)", lambda: uc(dz=0.6))
orig = rp.usb_solids
def cable_up(dz=0.0, dx=0.0):
    u = orig(dz, dx); u["usb-cable"] = orig(1.5, dx)["usb-cable"]; return u
rp.usb_solids = cable_up
run("cable 1.5 up (laid into the body's notch)", lambda: uc())
rp.usb_solids = orig
run("cup-rock: a lip in its notch's open top (cup off)", lambda: uc(cups=dict(rock=cups["rock"] + box(X + 2.7, X + 2.8, YB - 2.0, YB - 1.0, 21.8, 22.0), flat=cups["flat"])))
run("a boss-like block 0.3 over the cable's inner run (body)", lambda: uc(body=body + box(X - 1, X + 1, 18, 19, Z + 2.8, Z + 3.2)))
ss = dict(seg_sets); c_, sg = ss["cup-flat"]; ss["cup-flat"] = (c_, sg + [box(X - 6, X + 6, rp.HEAD_Y0, rp.HEAD_Y0 + 19, 13.4, 17.4)])
run("a flat-cup segment under the head (0.1 below it)", lambda: uc(seg_sets=ss))
run("tool path: a 0.3 too close to the head (TOOL_MIN 0.3 vs head) ", lambda: rp.check(min(rp.gap_to(rp.box(rp.HEAD_X + 6.1, rp.HEAD_X + 12, rp.Y_DOOR_BACK + 0.3, rp.Y_DOOR_BACK + 4, -20, rp.PCB_Z0 - 0.3), s) for s in rp.usb_solids().values()) >= rp.TOOL_MIN, "tool too close to the head"))
# slots
rp.check(True, "")
print("slot baseline:", "passes" if not run("slot land, no fault (must be SILENT)", lambda: rp.slot_land_check(door)) else "FAILS")
r0 = rp.RIM; rp.RIM = 0.0
run("slot land 0 (knife edge, round 5's E)", lambda: rp.slot_land_check(rp.door_part()))
rp.RIM = r0
from build123d import Pos
def land_at_face():                               # the cutter turned round: land on the face, bevel to the back
    d = rp.xz_prism(rp.DOOR_W, rp.DOOR_H, rp.DOOR_R, rp.XOFF, rp.DOOR_ZC, rp.Y_PANEL, rp.Y_DOOR_BACK)
    for x in rp.TUBE_X:
        cut = rp.hw.flat_end_cutter(x, rp.AA_ZC, rp.SLOT_W, rp.SLOT_L, rp.EXTRA, rp.RIM).mirror(rp.Plane.XZ)
        d = d - Pos(0, rp.Y_PANEL + rp.hw.FRONT, 0) * cut
    return d
run("slot land at the face instead of the inner face", lambda: rp.slot_land_check(land_at_face()))
w0 = rp.SLOT_W; rp.SLOT_W = 8.2; d82 = rp.door_part(); rp.SLOT_W = w0     # a door cut 8.2, checked against the design's 8.1
run("slot 8.2 wide", lambda: rp.slot_land_check(d82))
# battery path
b0 = rp.BAT_SWEEP_MIN; rp.BAT_SWEEP_MIN = 0.4
run("battery way up with 0.4 required", lambda: rp.battery_path())
rp.BAT_SWEEP_MIN = b0
run("battery straight up (sweep boxes vs body, X2 = X1)", lambda: rp.clear(rp.box(rp.BAT_PATH['X2'] - 34, rp.BAT_PATH['X2'] + 34, rp.BAT_Y0, rp.BAT_Y1, -60, rp.BAT_Z0 + rp.BAT_HT), body, "battery straight up at X2", rp.BAT_SWEEP_MIN - 0.05))
