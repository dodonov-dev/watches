#!/usr/bin/env python3
"""Desk housing, track B ("roly-poly"): CAD for the FDM prototype (docs/desk-housing-rolypoly-handoff.md, steps 3-4), round 6
(first print): the USB-C breakout is replaced by a right-angle USB-C extension in the board's own port, its cable out
through a round hole split by the seam; the door's slots get the smooth shells' printed land (8.1, 0.6 land); 1.0 logo skin.

Parts (STEP + STL each, in out-rolypoly/):
  body       the shell from the seam (z SEAM) up: lofted outer surface with the alcove, the inner surface the same points
             moved WALL along the surface normal; the door opening, four magnet tabs behind the door, the thinned logo
             wall, the battery bulkhead (notched for the USB head's way up), the cable notch in the back rim (open
             downward), the seam bosses.
  cup-rock   the bottom up to the seam: the rocking arc (R RR, symmetric about x 0, through the pole without a flat);
             the bowl open below the top terrace for a level cast of 304 balls in epoxy, one terrace above it for the
             stick-on trim segments; seam bosses; the cable notch in the back rim (open upward). Printed standing on its
             back so every layer draws the arc.
  cup-flat   the stable variant: the same outline cut flat at z CUT_FLAT, foot edge rounded, room for one strip; the
             same cable notch.
  door       the dark panel: flat plate with the two flat-end slots (E, F as a switch), glass locating ribs, magnet holes.
  arc-gauge  a concave R RR cradle to check (and true) the printed arc.
  (cup-rock-steps, terraces only for segments, behind BUILD_STEPS: it does not reach the 8 mm.)
Plus dummies (board, glass, rods, battery, the USB head and cable, the cast, segments, the LEDs' room) for the views,
the two keels' outer surfaces, report.txt and build-sheet.txt.

Frame (the study's): x right seen from the front, y front -> back (front is -y), z up from the bottom pole (the rocking
arc's lowest point). The rocking arc's centre is (x 0, z RR).

The shape functions (a_side, xc, bf_of, bb_of, the panel plane, the alcove flare) are the study's
(cad/desk/concept/rolypoly.py) with the chosen outline; the alcove outline is the door opening; the keel (the side view's
lower corner) is squared (KEEL).

Checks raise instead of exporting: fits (door + board straight in, battery up through the seam, the USB plug's way up into
the port, head and cable clear of cups / cast / segments / bosses / battery, the cable hole free along the cable, the cups
off straight down with the cable in, the LEDs' room, a tool's way to the door), the slots' land measured on sections of the
door, minimum walls measured on the solids, the arc through the
pole, the mass model on the exported meshes for the nominal and the bad case (centre of mass under the rocking centre,
one sideways rest position over the full revolution, fore-aft limits, plumb by the trim plan), the segment counts.

Run: ~/.venvs/cad/bin/python cad/desk/rolypoly.py   then   ~/.venvs/cad/bin/python cad/desk/render_rolypoly.py
"""
import sys, os, math, json, pathlib
import numpy as np

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import housing as hw                                   # hardware numbers + flat_end_cutter (its __main__ does not run)

check = hw.check
OUT = HERE / "out-rolypoly"

# ---- outline: the study's chosen one (XOFF=-5 Z2L=90 A2L=28.5 Z2R=102 A2R=34) ------------------------------------
P = dict(H=128.0, RR=44.0, ARC_DEG=62.0,
         Z2L=90.0, A2L=28.5, Z2R=102.0, A2R=34.0,              # shoulder end (z, half-width) per side
         BF=23.0, BB=27.0, ZC=28.0, NC=3.2, ZF=70.0, MF=2.8, MB=2.2, PE=2.6,
         ZK=28.0,                                              # keel: the belly's lower corner in the side view, up to here
         XOFF=-5.0, XZ1=62.0,                                  # upper body + door 5 mm left of the arc's centre
         FLARE=7.0, PANEL_SET=1.0)                             # alcove flare width; door face behind the surface
# Keel (round 2): the side view's lower corner (1 - u^NC)^(1/NC), u = (ZK - z) / ZK, squared from the study's 3.2 so the
# fore-aft limit has reserve; the front view, the R44 arc, the depth (50) and the seam stay as they are.
KEELS = {"study": 3.2, "square": 4.5}
KEEL = "square"
P["NC"] = KEELS[KEEL]
H, RR, PE, XOFF = P["H"], P["RR"], P["PE"], P["XOFF"]
SEAM = 22.0                                                    # body / cup joint (top of the ballast)
CUT_FLAT = 12.0                                                # stable cup: flat at this z (10 mm tall)
FOOT_R = 3.0                                                   # stable cup: foot edge rounding

# ---- printed walls --------------------------------------------------------------------------------------------
WALL = 2.4                                                     # FDM (SLA later ~2.0)
RHO_PLA = 1.24
RHO_DOOR = 1.24                                                # PLA Matte (white for the round 6 print; black later; PETG-CF ~1.3)

# ---- door (the dark panel) ------------------------------------------------------------------------------------
SLOT_TYPE = "E"                                                # E: 3 mm, bevel to a SLOT_LAND land (user); F: 4 mm, bevel to a 1 mm rim
SLOT_LAND = 0.6                                                # E: straight land at the door's inner face before the 45 deg starts
                                                               # (smooth shells' print test 2026-11-19: the knife edge printed 0.8 wide)
FRONT_BY_SLOT = {"E": (0.0, SLOT_LAND), "F": (1.0, 1.0)}       # (extra over hw.FRONT_T, rim): housing.flat_end_cutter
SLOT_W = 8.1                                                   # smooth shells' round 3: rods measured 8.0, snug fit (hw.SLOT_W 8.6)
ROD_PLAY_MIN = 0.1                                             # slot width over the rod, at least
LAND_DY, SLOT_SECTIONS = 0.01, 23                              # land measurement: depth step, sections along each slot
PCB_Z0 = 26.0                                                  # board's PCB bottom (study)
DOOR_W, DOOR_H, DOOR_R = 42.5, 82.0, 6.75                      # visible door; the opening is DOOR_GAP larger all round
DOOR_GAP = 0.25
PASS_CLR = 0.5                                                 # board envelope to the opening, at least
GLASS_RIB_T, GLASS_RIB_H, GLASS_RIB_CLR = 1.0, 2.0, 0.2        # locating frame round the glass on the door's back
DOOR_MAG_D, DOOR_MAG_H = 2.0, 1.0                              # S-02-01-N, 4 pairs: door <-> body tabs
TAB_H, TAB_DEPTH = 8.0, 3.0                                    # tab height (z) and depth behind the door's back
TAB_CLR = 0.5                                                  # tab to the board envelope
# tab centres, z above the PCB bottom, per side (-1 = button side, +1 = plug side): clear of the buttons / plugs
TABS = ((+1, 17.0), (+1, 68.0), (-1, 48.0), (-1, 68.0))

# ---- inside ---------------------------------------------------------------------------------------------------
M_BOARD, M_BAT, M_MISC = 30.0, 55.0, 10.0                      # ASSUMED (weigh them); misc = wires, USB head, LEDs, magnets
BAD = dict(M_BOARD=52.0, M_BAT=60.0, RHO_CAST=4.8)             # the bad case the asserts also cover (round 6: 52 g found online
                                                               # for one of the board's parts)
BAT_L, BAT_HT, BAT_T = 68.0, 35.0, 10.0                        # battery on its long edge (68 along x, 35 tall)
BAT_GAP = 1.0                                                  # board back -> battery (Kapton)
BAT_TAPE = 1.0                                                 # battery -> bulkhead (foam tape)
BAT_HEAD_MIN = 1.0                                             # battery bottom above the USB head, at least
BAT_Z0 = PCB_Z0 + BAT_HEAD_MIN                                 # battery bottom (round 6: over the USB head; was 23)
BULK_T, BULK_TOP = 1.5, BAT_Z0 + BAT_HT + 3.0                  # bulkhead behind the battery (3 over its top, as before)
BAT_SWEEP_MIN = 0.3                                            # battery's way up from below: clearance, at least

# ---- seam joint ---------------------------------------------------------------------------------------------------
SEAM_MAG_D, SEAM_MAG_H = 3.0, 2.0                              # S-03-02-N, ~300 g each (vendor), 6 pairs
SEAM_PIN_D, SEAM_PIN_L = 3.0, 10.0                             # steel dowel pins, 2
MAG_CLR_D, MAG_CLR_H = 0.1, 0.1                                # pocket: magnet + 0.1 of glue; set flush against a flat plate
MEAT_MIN = 0.8                                                 # wall left round a magnet / pin hole
BOSS_MEAT = 1.0
# boss positions on the seam: (kind, x, side) with side -1 = front wall, +1 = back wall
# front: only outside the door's width (the door's bottom edge is 2.4 above the seam); back: clear of the breakout cradle
BOSSES = (("mag", -29.0, +1), ("mag", -22.0, +1), ("mag", 22.0, +1), ("mag", 29.0, +1), ("mag", -33.0, -1), ("mag", 22.5, -1),
          ("pin", -15.0, +1), ("pin", 15.0, +1))

# ---- ballast --------------------------------------------------------------------------------------------------
SEG = (12.0, 19.0, 4.0)                                        # stick-on steel segment (Wegmann type 37), 5 g
SEG_G = 5.0
SEG_GAP = 0.3                                                  # between segments and to the walls
CAV_IN = 0.2                                                   # terrace walls this far inside the inner surface (a prism edge
                                                               # lying on the lofted inner surface makes the cut fail silently)
SEG_TOP_MAX = SEAM - 0.1                                       # top of the top layer, at most (searched down in 0.25 steps)
FLAT_FLOOR_MIN = 1.2                                           # stable cup: floor under the bottom layer, at least
TRIM_LAYERS = 1                                                # rocking cup: segment layers above the cast base (for trim)
RHO_CAST = 5.1                                                 # ASSUMED nominal: 304 balls 2-6 mm locked in epoxy (BAD: 4.8)
RHO_BALL, RHO_EPOXY = 7.93, 1.1                                # 304 stainless, epoxy
FWD_MIN_NOMINAL, FWD_MIN_BAD, MARGIN_MIN = 28.0, 25.0, 8.0     # fore-aft limit (deg) nominal / bad case; rocking margin (mm)
BUILD_STEPS = False                                            # the terraces-only rocking cup (round 1's alternative), off
PLUMB_TOL = 0.2                                                # centre of mass to the arc's centre line after the fill plan
# Trim spots: segments stuck standing (12 along x, 19 tall) on the bulkhead's back, right half, behind the battery. The
# door and board sit 5 mm left: with the cast in, the clock leans ~0.8 mm left, more than the symmetric trim layer can take.
TRIM_SPOTS = (27.5, 15.0)                                      # x centres, in the order they are used
TRIM_SPOT_Z0 = 27.5                                            # bottom; round 6: searched down to the lowest that clears the body
TRIM_SPOT_Z_LO = SEAM + 0.5                                    # ... from here, in 0.5 steps (round 5: 27.5 over the breakout)

# ---- USB: right-angle USB-C extension straight in the board's own port (round 6; the breakout + J5 pigtail are gone) ----
# ASSUMED head envelope, as housing.py's MOGOOD adapter box (the extension's head is "<= 12 x 7 x 21"): 12 across (x), 21
# along y, a 1.5 collar + 7 body below the PCB's bottom edge; the plug's axis 5 from the head's closed (front) end; the
# cable leaves the far end along +y at the head body's mid-thickness. The port: on the PCB's bottom edge, at the board's
# x centre, hw.PORT_Y_FROM_BOARD_BACK in front of the back of the board stack (housing.py: assumed, measure).
HEAD_W, HEAD_L, HEAD_BEHIND = hw.ADAPTER_W, hw.ADAPTER_L, hw.ADAPTER_BEHIND
HEAD_COLLAR, HEAD_T = hw.ADAPTER_COLLAR, hw.ADAPTER_T
CABLE_D = 5.0                                                  # the extension's cable
CABLE_HOLE_D = 5.6                                             # round passage through the back wall, split by the seam (smooth.py's
                                                               # notch for a cable up to 5)
HEAD_CLR = 0.5                                                 # head + cable to cups, cast, segments, bosses, bulkhead, at least
CABLE_LAY_MIN = 0.1                                            # cable laid up into the body's notch (a vertical sweep): at least

# ---- logo -----------------------------------------------------------------------------------------------------
LOGO_W, LOGO_X, LOGO_ZC = 14.0, 32.0, 30.0                     # letters' width, centre x, centre z (round 4: x 28 -> 32, off
                                                               # the alcove's flare onto the plain belly; scan in the report)
LOGO_FLARE_CLR = 2.0                                           # letters to the end of the alcove's outer flare, outside, at least
LED_SHIFT = 0.0                                                # LEDs' room right of the letters' centre (round 2-3: 2.0)
LOGO_SKIN = 1.0                                                # wall left over the letters (round 6: 0.8 -> 1.0, as the smooth
                                                               # shells after their 2026-11-19 print: thinner showed through unlit)

# ---- shape (the study's functions) ------------------------------------------------------------------------------
Z1 = RR * (1 - math.cos(math.radians(P["ARC_DEG"])))
A1 = RR * math.sin(math.radians(P["ARC_DEG"]))
S1 = (RR - Z1) / A1
SIDES = {"L": (P["Z2L"], P["A2L"]), "R": (P["Z2R"], P["A2R"])}


def a_side(z, side):
    """Half-width of the outline on one side ('L' = the viewer's left, 'R' = right)."""
    z2, a2 = SIDES[side]
    rc = H - z2
    z = np.asarray(z, float)
    t = np.clip((z - Z1) / (z2 - Z1), 0, 1)
    d = z2 - Z1
    herm = (2 * t**3 - 3 * t**2 + 1) * A1 + (t**3 - 2 * t**2 + t) * d * S1 + (-2 * t**3 + 3 * t**2) * a2
    arc = np.sqrt(np.clip(2 * RR * z - z * z, 0, None))
    crown = a2 / rc * np.sqrt(np.clip(rc**2 - (z - z2) ** 2, 0, None))
    return np.where(z <= Z1, arc, np.where(z >= z2, crown, herm))


def xc(z):
    t = np.clip((np.asarray(z, float) - Z1) / (P["XZ1"] - Z1), 0, 1)
    return XOFF * t * t * (3 - 2 * t)


def a_at(x, z):
    return np.where(np.asarray(x) - xc(z) < 0, a_side(z, "L"), a_side(z, "R"))


def _corner(z):
    u = np.clip((P["ZK"] - z) / P["ZK"], 0, 1)
    return (1 - u ** P["NC"]) ** (1 / P["NC"])


def bf_of(z):
    z = np.asarray(z, float)
    u = np.clip((z - P["ZF"]) / (H - P["ZF"]), 0, 1)
    return P["BF"] * _corner(z) * (1 - u ** P["MF"]) ** (1 / P["MF"])


def bb_of(z):
    z = np.asarray(z, float)
    u = np.clip((z - P["ZC"]) / (H - P["ZC"]), 0, 1)
    return P["BB"] * _corner(z) * (1 - u ** P["MB"]) ** (1 / P["MB"])


def y_front(x, z):
    a = np.maximum(a_at(x, z), 1e-6)
    return -bf_of(z) * np.clip(1 - (np.abs(x - xc(z)) / a) ** PE, 0, None) ** (1 / PE)


# door / opening: rounded rectangles centred on (XOFF, DOOR_ZC) in the x-z plane
DOOR_ZC = PCB_Z0 + hw.PCB_H / 2
OPEN_W, OPEN_H, OPEN_R = DOOR_W + 2 * DOOR_GAP, DOOR_H + 2 * DOOR_GAP, DOOR_R + DOOR_GAP


def sd_rrect(x, z, w, h, r, cx=XOFF, cz=DOOR_ZC):
    qx, qz = np.abs(x - cx) - (w / 2 - r), np.abs(z - cz) - (h / 2 - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qz, 0)) + np.minimum(np.maximum(qx, qz), 0) - r


def sd_open(x, z):
    return sd_rrect(x, z, OPEN_W, OPEN_H, OPEN_R)


def rrect_outline(w, h, r, step=0.1, cx=XOFF, cz=DOOR_ZC):
    """Points on a rounded rectangle (x, z), about `step` apart."""
    pts = []
    for qx, qz, a0 in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        ccx, ccz = cx + qx * (w / 2 - r), cz + qz * (h / 2 - r)
        for a in np.arange(a0, a0 + 90, math.degrees(step / max(r, 1e-6))):
            pts.append((ccx + r * math.cos(math.radians(a)), ccz + r * math.sin(math.radians(a))))
    pts = np.array(pts + [pts[0]])
    seg = []
    for p, q in zip(pts[:-1], pts[1:]):
        n = max(1, int(np.hypot(*(q - p)) / step))
        seg.append(p + (q - p) * np.linspace(0, 1, n, endpoint=False)[:, None])
    o = np.vstack(seg)
    return o[:, 0], o[:, 1]


_ox, _oz = rrect_outline(OPEN_W, OPEN_H, OPEN_R)
Y_PANEL = float(np.max(y_front(_ox, _oz))) + P["PANEL_SET"]          # the door's face (study's rule, on the opening)


def body_xyz(th, z, flare=P["FLARE"]):
    """Outer surface point(s) at superellipse angle th and height z, with the alcove (study's body_grid)."""
    th, z = np.broadcast_arrays(np.asarray(th, float), np.asarray(z, float))
    c, s = np.cos(th), np.sin(th)
    ex = np.sign(c) * np.abs(c) ** (2 / PE)
    ey = np.sign(s) * np.abs(s) ** (2 / PE)
    X = xc(z) + np.where(ex < 0, a_side(z, "L"), a_side(z, "R")) * ex
    Y = np.where(ey < 0, bf_of(z), bb_of(z)) * ey
    sd = sd_open(X, z)
    w = np.clip(1 - sd / flare, 0, 1)
    w = w * w * (3 - 2 * w)
    Y = np.where(Y < 0, Y + w * np.maximum(0, Y_PANEL - Y), Y)
    return X, Y, z


# ---- surfaces: a dense point grid, its normals, the inner surface ------------------------------------------------
from build123d import (Box, Cylinder, Pos, Plane, Polygon, Rectangle, RectangleRounded, Compound, Solid, Face, Wire, Edge,
                       Vector, Axis, Align, GeomType, extrude, export_step, import_step, BuildSketch, BuildLine, make_face)
from OCP.gp import gp_Pnt, gp_Pln, gp_Dir
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections

NU = 200                                   # points per section
WARP = 0.45                                # denser at the front (the alcove): density there 1 / (1 - WARP) of the mean


def theta_of(u):
    """Superellipse angle for the uniform parameter u in [0, 2pi): th = u - WARP cos u keeps the front (th = 3pi/2)."""
    return u - WARP * np.cos(u)


def _v_seam(target=np.pi):
    lo, hi = target - 1.0, target + 1.0              # theta_of is increasing: bisect theta_of(v) = target
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if theta_of(mid) < target else (lo, mid)
    return (lo + hi) / 2


U = np.linspace(0, 2 * np.pi, NU, endpoint=False)    # spline parameters (the same on every section)
V_SEAM = _v_seam()                                   # the periodic splines' seam on the left flank (theta = pi, y = 0):
TH = theta_of(U + V_SEAM)                            # away from the door, logo, USB, bosses and bulkhead


def z_rows(z0, z1, n, extra=()):
    """Rows from z0 to z1, cosine-spaced (dense at both ends), with the `extra` levels in exactly: an extra level replaces
    a cosine row closer than a third of the local spacing (near-duplicate rows make the normals noisy), never another
    extra level."""
    u = np.linspace(0, 1, n)
    z = list(z0 + (z1 - z0) * (1 - np.cos(np.pi * u)) / 2)
    fixed = [True] + [False] * (n - 2) + [True]
    for e in sorted(set(float(x) for x in extra if z0 < x < z1)):
        k = int(np.searchsorted(z, e))
        gap = z[k] - z[k - 1]
        if e - z[k - 1] < gap / 3 and not fixed[k - 1]:
            z[k - 1], fixed[k - 1] = e, True
        elif z[k] - e < gap / 3 and not fixed[k]:
            z[k], fixed[k] = e, True
        else:
            z.insert(k, e)
            fixed.insert(k, True)
    z = np.asarray(z)
    check(np.all(np.diff(z) > 1e-4), "z rows not increasing")
    for e in extra:
        check(not (z0 < e < z1) or np.min(np.abs(z - e)) < 1e-12, f"level {e} lost")
    return z


ZB0, ZB1 = 0.002, H - 0.02                 # first / last section; the outer loft closes at the bottom pole in a vertex (the
                                           # rolling surface runs through it: no flat), at the crown in a 2 mm flat cap
_OB, _OT = DOOR_ZC - OPEN_H / 2, DOOR_ZC + OPEN_H / 2
_FLARE_Z = list(np.linspace(_OB - P["FLARE"] - 1, _OB + 1.5, 20)) + list(np.linspace(_OT - 1.5, _OT + P["FLARE"] + 1, 20))
DENSE_Z = z_rows(ZB0, ZB1, 900, extra=[SEAM, CUT_FLAT, LOGO_ZC])


def grid(zs, flare=P["FLARE"]):
    Z = np.repeat(np.asarray(zs, float)[:, None], NU, 1)
    X, Y, _ = body_xyz(np.repeat(TH[None, :], len(zs), 0), Z, flare)
    return np.stack([X, Y, Z], -1)


def normals(G):
    """Outward unit normals of a grid (rows = z, columns = around, counter-clockwise seen from above)."""
    du = np.roll(G, -1, 1) - np.roll(G, 1, 1)
    dv = np.gradient(G, G[:, 0, 2], axis=0)             # rows are horizontal sections: z is the row coordinate
    n = np.cross(du, dv)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n


G_OUT = grid(DENSE_Z)
N_OUT = normals(G_OUT)
# outward check: at the widest row the normals point away from the centre line (the alcove is concave)
_k = int(np.argmin(np.abs(DENSE_Z - 40)))
check(np.mean(np.sum(N_OUT[_k, :, :2] * (G_OUT[_k, :, :2] - G_OUT[_k, :, :2].mean(0)), -1) > 0) > 0.9, "normals point inwards")


FOLD_TOL = 0.005                           # a column of offset points may run back down by this much (numerical)


def fold_depth(G, N, t):
    z = (G - t * N)[:, :, 2]
    return float((np.maximum.accumulate(z, axis=0) - z).max())


# The study's smoothstep flare leaves a convex shoulder of radius ~6 D / F^2 (about 1 mm where the floor is 8 deep), below
# the wall: offsetting it folds. The inner surfaces are generated from the same body with a wider flare (FLARE_IN, the
# smallest in 0.5 steps whose WALL offset does not fold): the wall is WALL everywhere except the alcove's shoulder (thicker).
FLARE_IN = P["FLARE"]
while fold_depth(grid(DENSE_Z, FLARE_IN), normals(grid(DENSE_Z, FLARE_IN)), WALL) > FOLD_TOL:
    FLARE_IN += 0.5
    check(FLARE_IN <= 3 * P["FLARE"], "no fold-free inner flare")
G_GEN = grid(DENSE_Z, FLARE_IN)
N_GEN = normals(G_GEN)


def offset_rows(t, zs, outer=False):
    """Sections of the inner-generating surface (outer=True: of the outer surface itself) moved t along its normal,
    re-sliced at the levels zs: [NU x 3] each. Folds are checked on the rows that feed these levels."""
    G_, N_ = (G_OUT, N_OUT) if outer else (G_GEN, N_GEN)
    Q = G_ - t * N_
    k = (DENSE_Z >= min(zs) - t - 2) & (DENSE_Z <= max(zs) + t + 2)
    check(fold_depth(G_[k], N_[k], t) <= FOLD_TOL, f"offset {t} folds")
    out = []
    for z in zs:
        sec = np.empty((NU, 3))
        for j in range(NU):
            zc_ = np.maximum.accumulate(Q[:, j, 2]) + np.arange(len(Q)) * 1e-9
            check(zc_[0] <= z <= zc_[-1], f"offset {t}: level {z:.2f} outside column {j} ({zc_[0]:.2f}..{zc_[-1]:.2f})")
            sec[j] = (np.interp(z, zc_, Q[:, j, 0]), np.interp(z, zc_, Q[:, j, 1]), z)
        sec[:, :2], _ = unloop(sec[:, :2])
        out.append(sec)
    return out


def _seg_cross(P):
    """Pairs (i, k), k > i + 1, of crossing segments P[i]P[i+1] and P[k]P[k+1] of a closed polyline, with the point."""
    A, B = P, np.roll(P, -1, 0)
    n = len(P)
    d1 = B - A
    out = []
    for i in range(n):
        k = np.arange(i + 2, n if i > 0 else n - 1)
        if not len(k):
            continue
        r_, s_ = d1[i], d1[k]
        den = r_[0] * s_[:, 1] - r_[1] * s_[:, 0]
        q = A[k] - A[i]
        ok = np.abs(den) > 1e-12
        t = np.where(ok, (q[:, 0] * s_[:, 1] - q[:, 1] * s_[:, 0]) / np.where(ok, den, 1), -1)
        u = np.where(ok, (q[:, 0] * r_[1] - q[:, 1] * r_[0]) / np.where(ok, den, 1), -1)
        hit = ok & (t >= 0) & (t <= 1) & (u >= 0) & (u <= 1)
        for kk, tt in zip(k[hit], t[hit]):
            out.append((i, int(kk), A[i] + tt * r_))
    return out


def unloop(P, max_loop=None):
    """Remove the small swallowtails an inward offset leaves at a convex crease: the points inside each loop are put on a
    quadratic Bezier from the point before, via the crossing, to the point after (it cuts the corner on the far side of
    the outer surface, so the wall only gets thicker). The point count and the columns stay as they are."""
    P = np.array(P, float)
    n = len(P)
    max_loop = max_loop or n // 8
    total = 0
    for _ in range(20):
        hits = [(i, k, X) for i, k, X in _seg_cross(P) if k - i <= max_loop]
        if not hits:
            break
        i, k, X = max(hits, key=lambda h: h[1] - h[0])
        a, b = P[i], P[(k + 1) % n]
        m = k - i
        for q in range(1, m + 1):
            t = q / (m + 1)
            P[(i + q) % n] = (1 - t) ** 2 * a + 2 * t * (1 - t) * X + t * t * b
        # spread the points of a window round it evenly along the new polyline (squeezed points make the spline wave)
        w0, w1 = i - m - 3, k + m + 4
        idx = [q % n for q in range(w0, w1 + 1)]
        W = P[idx]
        seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(W, axis=0), axis=1))]
        tgt = np.linspace(0, seg[-1], len(idx))
        P[idx] = np.c_[np.interp(tgt, seg, W[:, 0]), np.interp(tgt, seg, W[:, 1])]
        total += m
    check(not [h for h in _seg_cross(P) if h[1] - h[0] <= max_loop], "offset section still crosses itself")
    big = [h for h in _seg_cross(P)]
    check(not big, f"offset section crosses itself over {max(h[1] - h[0] for h in big) if big else 0} points")
    return P, total


def offset_range(t):
    zc_ = (G_GEN - t * N_GEN)[:, :, 2]
    return float(zc_[0].max()), float(zc_[-1].min())


# ---- OCC helpers --------------------------------------------------------------------------------------------------
def periodic_edge(pts):
    """Closed interpolating B-spline through pts with the parameters U: the same knots on every section. Interpolated as
    periodic (smooth all round), then made non-periodic with the same shape: STEP has no periodic B-splines, and the
    converted trims of a periodic lofted face came back invalid on re-import."""
    from OCP.BRep import BRep_Tool
    from OCP.Geom import Geom_BSplineCurve
    e = Edge.make_spline([tuple(map(float, p)) for p in pts], parameters=list(map(float, U)) + [2 * math.pi], periodic=True)
    bs = BRep_Tool.Curve_s(e.wrapped, 0.0, 1.0)            # the temporary edge's own curve, changed in place
    check(isinstance(bs, Geom_BSplineCurve), "section is not a B-spline")
    bs.SetNotPeriodic()
    check(not bs.IsPeriodic() and bs.IsClosed(), "section not closed after SetNotPeriodic")
    return BRepBuilderAPI_MakeEdge(bs).Edge()


def section_wire(pts):
    return BRepBuilderAPI_MakeWire(periodic_edge(pts)).Wire()


def loft(sections, pole=None):
    """Loft through the sections; pole: a point the loft starts from (the bottom pole) instead of a flat cap."""
    ts = BRepOffsetAPI_ThruSections(True, False, 1e-6)
    ts.CheckCompatibility(False)
    ts.SetMaxDegree(3)                     # the default (cubic in v here) re-imported from STEP as an invalid face
    if pole is not None:
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
        ts.AddVertex(BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float, pole))).Vertex())
    for s in sections:
        ts.AddWire(section_wire(s))
    ts.Build()
    check(ts.IsDone(), "loft failed")
    sol = Solid(ts.Shape())
    check(sol.is_valid, "lofted solid invalid")
    return sol


def plan_face(pts, z):
    """Planar face at z bounded by the periodic spline through pts (x, y)."""
    p3 = [(float(x), float(y), z) for x, y in np.asarray(pts)[:, :2]]
    return Face(Wire(Edge(periodic_edge(p3))))


import smooth as sm                                    # track A (not edited): STL writer, distances
write_stl, dist_shapes = sm.write_stl, sm.dist_shapes
EPS_V = hw.EPS_V
STL_VOL_TOL = sm.STL_VOL_TOL
STEP_VOL_TOL = 1e-3                                    # track A: 1e-4 on integrated volumes; ours are triangulated


def vol(shape, defl=0.02):
    """Volume from the shape's own triangulation (absolute deflection `defl`). OCC's integration (shape.volume, and also
    BRepGProp with an eps) is off by up to 25 % on these trimmed B-spline and extrusion faces and even goes negative on
    thin slabs; the triangulation agrees with the study's section areas and with the exported meshes."""
    import tempfile, os
    import pyvista as pv
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.StlAPI import StlAPI_Writer
    if not shape.solids():
        return 0.0
    BRepMesh_IncrementalMesh(shape.wrapped, defl, False, 0.2, True).Perform()
    fd, tmp = tempfile.mkstemp(suffix=".stl")
    os.close(fd)
    try:
        w = StlAPI_Writer()
        w.ASCIIMode = False
        check(w.Write(shape.wrapped, tmp), "temporary STL not written")
        m = pv.read(tmp)
        check(m.n_cells > 0, "a shape did not mesh")
        return float(m.volume)
    finally:
        os.remove(tmp)


def check_stl(shape, path, bodies=1, ref=None):
    """track A's check_stl: closed, `bodies` pieces, volume within STL_VOL_TOL of the solid's (here: of a coarser
    triangulation of the solid, since OCC's integrated volume is not reliable on these faces)."""
    import pyvista as pv
    mesh = pv.read(str(path)).clean()
    n_open = mesh.n_open_edges
    n_bodies = int(mesh.connectivity().point_data["RegionId"].max()) + 1
    v = abs(mesh.volume)
    ref = vol(shape) if ref is None else ref
    err = v / ref - 1
    check(n_open == 0, f"{path.name}: {n_open} open edges")
    check(n_bodies == bodies, f"{path.name}: {n_bodies} separate bodies, expected {bodies}")
    check(abs(err) <= STL_VOL_TOL, f"{path.name}: mesh volume {v:.1f} vs solid {ref:.1f} ({err * 100:+.2f} %)")
    return dict(kb=path.stat().st_size / 1024, tris=mesh.n_cells, err=err)


def write_step(shape, path):
    """track A's write_step: re-imported, same solid count, valid and closed, same volume (triangulated, see vol)."""
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRep import BRep_Tool
    export_step(shape, str(path))
    back = import_step(str(path))
    n0, n1 = len(shape.solids()), len(back.solids())
    check(n1 == n0, f"{path.name}: re-imported with {n1} solids, written {n0}")
    for sol in back.solids():
        check(BRepCheck_Analyzer(sol.wrapped).IsValid() and all(BRep_Tool.IsClosed_s(sh.wrapped) for sh in sol.shells()),
              f"{path.name}: an invalid or open solid")
    v0, v1 = vol(shape), sum(vol(x) for x in back.solids())
    check(abs(v1 / v0 - 1) <= STEP_VOL_TOL, f"{path.name}: volume {v1:.2f} back, {v0:.2f} written")
    return dict(solids=n1, faces=len(back.faces()), err=v1 / v0 - 1, kb=path.stat().st_size / 1024)


def box(x0, x1, y0, y1, z0, z1):
    return hw.box(min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1))


def xz_prism(w, h, r, cx, cz, y0, y1):
    """Rounded rectangle w x h (r) in the x-z plane round (cx, cz), from y0 to y1."""
    pl = Plane(origin=(cx, y0, cz), x_dir=(1, 0, 0), z_dir=(0, 1, 0))
    return extrude(pl * (RectangleRounded(w, h, r) if r > 0 else Rectangle(w, h)), y1 - y0)


def halfspace(pt, n, size=400.0):
    """Solid on the side of the plane through pt that n points to."""
    return Plane(origin=pt, z_dir=n) * Box(size, size, size, align=(Align.CENTER, Align.CENTER, Align.MIN))


def zcyl(x, y, r, z0, z1):
    return Pos(x, y, min(z0, z1)) * Cylinder(r, abs(z1 - z0), align=(Align.CENTER, Align.CENTER, Align.MIN))


def ycyl(x, z, r, y0, y1):
    return Plane(origin=(x, min(y0, y1), z), x_dir=(1, 0, 0), z_dir=(0, 1, 0)) * Cylinder(
        r, abs(y1 - y0), align=(Align.CENTER, Align.CENTER, Align.MIN))


def one_solid(s, what):
    sols = s.solids()
    check(len(sols) == 1 and s.is_valid, f"{what}: {len(sols)} solids, valid {s.is_valid}")
    return sols[0] if not isinstance(s, Solid) else s


def overlap(a, b):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    c = BRepAlgoAPI_Common(a.wrapped, b.wrapped)
    c.Build()
    check(c.IsDone(), "boolean common failed")
    from build123d import Compound as _C
    r_ = _C(c.Shape())
    return sum(vol(x) for x in r_.solids()) if r_.solids() else 0.0


# ---- derived numbers ------------------------------------------------------------------------------------------------
EXTRA, RIM = FRONT_BY_SLOT[SLOT_TYPE]
DOOR_T = hw.FRONT + EXTRA                              # 3 (E) or 4 (F); the door's face stays at Y_PANEL
Y_DOOR_BACK = Y_PANEL + DOOR_T
Y_GLASS0 = Y_DOOR_BACK + hw.GASKET
Y_GLASS1 = Y_GLASS0 + hw.GLASS_T
Y_BOARD1 = Y_GLASS0 + hw.BOARD_T                       # back of the board stack
PCB_Z1 = PCB_Z0 + hw.PCB_H
GLASS_Z0 = PCB_Z0 + (hw.PCB_H - hw.GLASS_H) / 2
AA_ZC = PCB_Z0 + hw.AA_Z_FROM_PCB_BOTTOM + hw.AA_H / 2
ROD_L = hw.TS_FLAT_ROD_L                               # 66.65
SLOT_L = ROD_L + hw.TS_FLAT_PLAY                       # 66.85
TUBE_X = (XOFF - hw.TUBE_CC / 2, XOFF + hw.TUBE_CC / 2)
BAT_Y0 = Y_BOARD1 + BAT_GAP
BAT_Y1 = BAT_Y0 + BAT_T
BULK_Y0 = BAT_Y1 + BAT_TAPE
BULK_Y1 = BULK_Y0 + BULK_T
# the board's envelope across (local x from the door's centre line): buttons on the -X edge, plugs on the +X edge
ENV_X = {hw.BTN_SIDE: hw.PCB_W / 2 + hw.BTN_PROUD, -hw.BTN_SIDE: hw.PCB_W / 2 + hw.PLUG_PROUD}
check(OPEN_W / 2 - max(ENV_X.values()) >= PASS_CLR - 1e-9, f"opening {OPEN_W} too narrow for the board envelope")
SEAM_R_HOLE = (SEAM_MAG_D + MAG_CLR_D) / 2
PIN_R_BODY, PIN_R_CUP = (SEAM_PIN_D + 0.1) / 2, (SEAM_PIN_D + 0.2) / 2
PIN_DEPTH = SEAM_PIN_L / 2 + 0.5
BOSS_H = {"mag": SEAM_MAG_H + MAG_CLR_H + 1.0, "pin": PIN_DEPTH + 1.0}
HOLE_R = {"mag": SEAM_R_HOLE, "pin": max(PIN_R_BODY, PIN_R_CUP)}


def opening_needed():
    """Smallest opening (w, h) for R OPEN_R corners: the board envelope + PASS_CLR, the PCB's corners inside the arcs."""
    hx = max(ENV_X.values()) + PASS_CLR
    r = OPEN_R
    dx = max(hw.PCB_W / 2 - (hx - r), 0.0)
    dz = math.sqrt(max((r - PASS_CLR) ** 2 - dx * dx, 0.0))
    hz = max(hw.PCB_H / 2 + PASS_CLR, hw.PCB_H / 2 + r - dz)
    return 2 * hx, 2 * hz


# ---- surfaces as solids ---------------------------------------------------------------------------------------------
def loft_levels(z0, z1, n=90):
    """Loft rows: cosine-spaced, plus 0.5 mm rows across both flares' bands (the outer's and the wider inner one's: the
    smoothsteps' ends are only C1 and the lofts overshoot there on coarse rows)."""
    band = list(np.arange(_OB - FLARE_IN - 1.5, _OB + 1.51, 0.5)) + list(np.arange(_OT - 1.5, _OT + FLARE_IN + 1.51, 0.5))
    return z_rows(z0, z1, n, extra=[SEAM, CUT_FLAT] + sorted(set(np.round(_FLARE_Z + band, 4))))


def surface_deviation(solid, pts):
    """Largest distance from points (that the surface should pass through) to the solid's lofted face."""
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCP.BRep import BRep_Tool
    srf = [BRep_Tool.Surface_s(f.wrapped) for f in solid.faces() if f.geom_type != GeomType.PLANE]
    check(len(srf) == 1, "lofted solid: expected one free-form face")
    d = []
    for p in pts:
        pr = GeomAPI_ProjectPointOnSurf(gp_Pnt(*map(float, p)), srf[0])
        check(pr.NbPoints() > 0, "projection failed")
        d.append(pr.LowerDistance())
    return float(np.max(d))


LOFT_TOL = 0.06                            # outer loft to the study's function
LOFT_TOL_IN = 0.15                         # inner lofts to their offset points (hidden; the measured wall governs)


class Surfaces:
    def __init__(self):
        self.outer = loft(list(grid(loft_levels(ZB0, ZB1))), pole=(float(xc(0.0)), 0.0, 0.0))
        lo, hi = offset_range(WALL)
        self.inner_z = (lo + 0.03, hi - 0.03)
        self.inner = loft(offset_rows(WALL, loft_levels(*self.inner_z)))
        # deviation: the outer from the study's function between the loft rows and between the columns; the inner from
        # its offset points between the loft rows
        rows = DENSE_Z[5::31]
        thm = theta_of(U + V_SEAM + np.pi / NU)
        mid = np.stack(body_xyz(np.repeat(thm[None, ::5], len(rows), 0), np.repeat(rows[:, None], len(thm[::5]), 1)), -1)
        self.dev_outer = surface_deviation(self.outer, np.vstack([G_OUT[5::31, ::10].reshape(-1, 3), mid.reshape(-1, 3)]))
        zs = [z for z in rows if self.inner_z[0] + 0.5 < z < self.inner_z[1] - 0.5]
        self.dev_inner = surface_deviation(self.inner, np.vstack([s[::10] for s in offset_rows(WALL, zs)]))
        check(self.dev_outer < LOFT_TOL and self.dev_inner < LOFT_TOL_IN,
              f"lofts off their points: outer {self.dev_outer:.3f}, inner {self.dev_inner:.3f}")

    def cup_outer(self, kind):
        """The cup's outer solid: the outer loft cut below the seam (rock) or between CUT_FLAT and the seam (flat): one loft
        for body and cups, so the seam has no step by construction."""
        key = "_cup_" + kind
        if not hasattr(self, key):
            z0 = -5.0 if kind == "rock" else CUT_FLAT
            setattr(self, key, one_solid(self.outer & box(-100, 100, -100, 100, z0, SEAM), f"cup-{kind} outer"))
        return getattr(self, key)

    def mid(self):
        """The surface moved WALL / 2 inwards, as a solid: features are clipped to it so their faces end inside the wall
        (a face on the outer loft itself makes the fuse fail)."""
        if not hasattr(self, "_mid"):
            lo, hi = offset_range(WALL / 2)
            self._mid = loft(offset_rows(WALL / 2, loft_levels(lo + 0.03, hi - 0.03)))
        return self._mid

    def band(self, t, z0, z1):
        """The OUTER surface moved t inwards, as a solid between the levels z0 and z1 (flat ends). Round 1 offset the
        inner-generating surface here: under the logo's left end (the alcove's wider inner flare) that left 2.6, not 0.8."""
        return loft(offset_rows(t, z_rows(z0, z1, 24), outer=True))


def seam_point(x, side, z=SEAM):
    """Outer surface at height z (a dense-grid row): the point at x on the front (side -1) or back (+1), its plan normal."""
    k = int(np.argmin(np.abs(DENSE_Z - z)))
    check(z != SEAM or abs(DENSE_Z[k] - SEAM) < 1e-9, "seam row missing")
    g, n = G_OUT[k], N_OUT[k]
    sel = np.where(np.sign(g[:, 1]) == side)[0]
    o = sel[np.argsort(g[sel, 0])]
    y = float(np.interp(x, g[o, 0], g[o, 1]))
    nx, ny = float(np.interp(x, g[o, 0], n[o, 0])), float(np.interp(x, g[o, 0], n[o, 1]))
    L = math.hypot(nx, ny)
    return np.array([x, y]), np.array([nx / L, ny / L])


def boss_spots():
    """Boss and hole centres: MEAT_MIN + 0.2 from the outer surface at the seam, plus however far the surface recedes over
    the cup's hole depth (the arc pulls in below the seam)."""
    out = []
    for kind, x, side in BOSSES:
        p, n = seam_point(x, side)
        depth = SEAM_MAG_H + MAG_CLR_H if kind == "mag" else PIN_DEPTH
        rec = 0.0
        for zz in np.linspace(SEAM - depth, SEAM, 6):
            q, _ = seam_point(x, side, zz)
            rec = max(rec, float(np.dot(p - q, n)))
        d = HOLE_R[kind] + MEAT_MIN + 0.2 + rec
        c = p - d * n
        out.append(dict(kind=kind, x=float(c[0]), y=float(c[1]), r_boss=HOLE_R[kind] + BOSS_MEAT, h=BOSS_H[kind],
                        side=side, x_nom=x, recede=rec))
    return out


# ---- battery: x where it passes the seam and sits (inner sections over its y band) --------------------------------------
def inner_x_limits(z, y0, y1, t=WALL):
    sec = offset_rows(t, [z])[0]
    xs, ys = sec[:, 0], sec[:, 1]
    lo, hi = -1e9, 1e9
    for yy in np.linspace(y0, y1, 21):
        # crossings of the closed polyline with the line y = yy
        a, b = np.c_[xs, ys], np.roll(np.c_[xs, ys], -1, 0)
        k = (a[:, 1] - yy) * (b[:, 1] - yy) <= 0
        xx = a[k, 0] + (yy - a[k, 1]) * (b[k, 0] - a[k, 0]) / np.where(b[k, 1] == a[k, 1], 1e-12, b[k, 1] - a[k, 1])
        lo, hi = max(lo, xx.min()), min(hi, xx.max())
    return lo, hi


def battery_path(dz=0.25):
    """The battery's way up from below (cup off): straight up at x X1 until its bottom reaches Z_MID, across to x X2, then
    straight up to its seat at x X2 (round 6: raised over the USB head to z BAT_Z0, its top reaches where the body's right
    side has narrowed (the upper body sits XOFF left), while the seam's opening is narrow on both sides: no straight way up
    leaves BAT_SWEEP_MIN; round 5's straight path is the case Z_MID = BAT_Z0). The levels each move passes, the inner
    sections across the battery's y band; Z_MID chosen for the largest least clearance. Returns a dict."""
    top = BAT_Z0 + BAT_HT
    zs = np.round(np.arange(SEAM, top + dz / 2, dz), 4)
    lims = np.array([inner_x_limits(z, BAT_Y0, BAT_Y1) for z in zs])

    def rng(z0, z1):
        k = (zs >= z0 - 1e-9) & (zs <= z1 + 1e-9)
        return lims[k, 0].max(), lims[k, 1].min()
    best = None
    for zm in np.round(np.arange(SEAM - 2.0, BAT_Z0 + dz / 2, dz), 4):
        lo1, hi1 = rng(SEAM, zm + BAT_HT)
        lo2, hi2 = rng(zm, top)
        x1, x2 = (lo1 + hi1) / 2, (lo2 + hi2) / 2
        lo3, hi3 = rng(zm, zm + BAT_HT)
        m = min((hi1 - lo1 - BAT_L) / 2, (hi2 - lo2 - BAT_L) / 2, min(x1, x2) - BAT_L / 2 - lo3, hi3 - max(x1, x2) - BAT_L / 2)
        if best is None or m > best["m"] + 1e-9:
            best = dict(m=float(m), Z_MID=float(zm), X1=float(x1), X2=float(x2), lo=float(lo2), hi=float(hi2),
                        straight=(hi2 - lo2 - BAT_L) / 2 if zm == BAT_Z0 else None)
    lo0, hi0 = rng(SEAM, top)
    best["straight"] = float((hi0 - lo0 - BAT_L) / 2)
    check(best["m"] >= BAT_SWEEP_MIN, f"battery: no way up from below with {BAT_SWEEP_MIN} each side (best {best['m']:.3f})")
    return best


BAT_PATH = battery_path()
BAT_X, BAT_XLO, BAT_XHI = BAT_PATH["X2"], BAT_PATH["lo"], BAT_PATH["hi"]

# ---- USB: the extension's head in the port, its cable straight back -----------------------------------------------
PORT_Y = Y_BOARD1 - hw.PORT_Y_FROM_BOARD_BACK          # the board's Type-C axis (y)
HEAD_X = XOFF                                          # the port at the board's x centre (housing.py)
HEAD_Y0 = PORT_Y - HEAD_BEHIND                         # the head's closed (front) end
HEAD_Y1 = HEAD_Y0 + HEAD_L                             # its far end: the cable leaves here, along +y
HEAD_Z1 = PCB_Z0                                       # collar face on the PCB's bottom edge (assumed flush with the port face)
HEAD_Z0 = HEAD_Z1 - HEAD_COLLAR - HEAD_T
CABLE_Z = HEAD_Z0 + HEAD_T / 2                         # the cable's axis: the head body's mid-thickness
Y_BACK_OUT = float(bb_of(CABLE_Z))                     # back surface on the centre line at the cable's height
CAST_TOP_MAX = HEAD_Z0 - HEAD_CLR                      # the cast (and the trim terrace) under the head: at most here
HEAD_NOTCH_X = HEAD_W / 2 + HEAD_CLR                   # bulkhead notch for the head's way up: half-width, top
HEAD_NOTCH_TOP = HEAD_Z1 + HEAD_CLR
TOOL_W = 6.0                                           # the door tool beside the head (right of it), its width
LED_MIN = 3.0                                          # LEDs' room to the battery's way up and the board's way in, at least
TOOL_MIN = 0.3                                         # the door tool's way to the board / battery, at least
SKIN_RANGE = (0.9, 1.1)                                # logo skin, normal thickness, over a sample of both letter floors
LOGO_OPEN = 5.0                                        # behind a letter floor, free along the ray this far = open there
LOGO_OPEN_MIN = 0.95                                   # each letter: share of its floor whose column opens into the cavity


def logo_frame():
    """Point on the outer surface at (LOGO_X, LOGO_ZC) on the front, its outward normal and a horizontal tangent: exact on
    the study's surface (round 4; until round 3 it snapped to the nearest grid column, ~1 mm apart there)."""
    lo, hi = -math.pi / 2, 0.0                                 # front centre .. right flank: x grows with theta
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if float(body_xyz(mid, LOGO_ZC)[0]) < LOGO_X else (lo, mid)
    th = (lo + hi) / 2
    P0 = np.array([float(v) for v in body_xyz(th, LOGO_ZC)])
    h = 1e-4
    t1 = (np.array([float(v) for v in body_xyz(th + h, LOGO_ZC)]) - np.array([float(v) for v in body_xyz(th - h, LOGO_ZC)])) / (2 * h)
    t2 = (np.array([float(v) for v in body_xyz(th, LOGO_ZC + h)]) - np.array([float(v) for v in body_xyz(th, LOGO_ZC - h)])) / (2 * h)
    nn = np.cross(t1, t2)
    nn = nn / np.linalg.norm(nn)
    if nn[1] > 0:
        nn = -nn
    xd = np.cross([0, 0, 1], nn)
    xd /= np.linalg.norm(xd)
    return P0, nn, xd


# ---- parts --------------------------------------------------------------------------------------------------------
def door_envelope(y1=None, grow=DOOR_GAP):
    """The door's outline (+ grow) as a prism from far in front to y1 (default: the door's back)."""
    return xz_prism(DOOR_W + 2 * grow, DOOR_H + 2 * grow, DOOR_R + grow, XOFF, DOOR_ZC, Y_PANEL - 60, Y_DOOR_BACK if y1 is None else y1)


def tab_spec(sx, zl):
    zt = PCB_Z0 + zl
    x_in = XOFF + sx * (hw.PCB_W / 2 + TAB_CLR)
    x_edge = XOFF + sx * OPEN_W / 2
    x_hole = XOFF + sx * (hw.PCB_W / 2 + TAB_CLR + DOOR_W / 2) / 2
    return zt, x_in, x_edge, x_hole


def tab_solid(S, sx, zl):
    zt, x_in, x_edge, x_hole = tab_spec(sx, zl)
    y1 = Y_DOOR_BACK + TAB_DEPTH
    s_max = abs(x_edge - x_in)
    t_max = y1 - (Y_PANEL + WALL)
    z_top = zt + TAB_H / 2
    z_full = zt - TAB_H / 2
    blk = box(x_in, x_edge + sx * 5.0, Y_PANEL - 5.0, y1, z_full - max(s_max, t_max) - 2, z_top)
    # 45 deg undersides towards the wall: into the opening (x) and behind the wall's inner face (y)
    blk = blk - halfspace((x_edge, 0, z_full - s_max), (-sx / math.sqrt(2), 0, -1 / math.sqrt(2)))
    blk = blk - halfspace((0, Y_PANEL + WALL, z_full - t_max), (0, 1 / math.sqrt(2), -1 / math.sqrt(2)))
    return (blk & S.mid()) - door_envelope()


def make_body(S):
    b = S.outer & box(-100, 100, -100, 100, SEAM, H + 10)
    b = b - S.inner
    b = one_solid(b, "body shell")
    shell_only = b
    # door opening through the alcove floor
    b = b - xz_prism(OPEN_W, OPEN_H, OPEN_R, XOFF, DOOR_ZC, Y_PANEL - 10, Y_PANEL + WALL + 1.0)
    # battery bulkhead (behind the battery, wall to wall), notched for the USB head's way up
    add = box(-100, 100, BULK_Y0, BULK_Y1, SEAM, BULK_TOP)
    add = add - box(HEAD_X - HEAD_NOTCH_X, HEAD_X + HEAD_NOTCH_X, BULK_Y0 - 1, BULK_Y1 + 1, SEAM - 1, HEAD_NOTCH_TOP)
    for s in boss_spots():
        add = add + zcyl(s["x"], s["y"], s["r_boss"], SEAM, SEAM + s["h"])
    for sx, zl in TABS:
        add = add + tab_solid(S, sx, zl)
    b = one_solid(b + (add & S.mid()), "body + features")
    # cuts: the cable notch (the round hole's part above the seam, open downward), seam holes, tab magnet holes, logo pocket
    b = b - cable_hole()
    for s in boss_spots():
        r = SEAM_R_HOLE if s["kind"] == "mag" else PIN_R_BODY
        d = SEAM_MAG_H + MAG_CLR_H if s["kind"] == "mag" else PIN_DEPTH
        b = b - zcyl(s["x"], s["y"], r, SEAM - 1, SEAM + d)
    for sx, zl in TABS:
        zt, _, _, xh = tab_spec(sx, zl)
        b = b - ycyl(xh, zt, (DOOR_MAG_D + MAG_CLR_D) / 2, Y_DOOR_BACK - 1, Y_DOOR_BACK + DOOR_MAG_H + MAG_CLR_H)
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    op = BRepAlgoAPI_Cut()
    op.SetFuzzyValue(1e-4)                                  # the roofed pocket: a plain cut misclassified it (round 5)
    pk = logo_pocket(S)
    b = b._bool_op((b,), (pk,), op)
    check(len(b.solids()) == 1, f"body after the logo cut: {len(b.solids())} solids")
    return one_solid(b, "body"), shell_only


def logo_letters_prism(depth_out=1.0, depth_in=WALL + 4.0):
    """The letters projected along the surface normal, from outside to deeper than the wall is anywhere under them (the
    alcove's wider inner flare thickens the wall to ~4.1 under the E's left bar: round 1's 3.9 left a sealed pocket there)."""
    p, n, xd = logo_frame()
    pl = Plane(origin=tuple(p + depth_out * n), x_dir=tuple(xd), z_dir=tuple(n))
    cut = None
    for poly in hw.letters_mm(LOGO_W):
        e = extrude(pl * Polygon(*[(u, v) for u, v in poly], align=None), depth_out + depth_in, dir=tuple(-n))
        cut = e if cut is None else cut + e
    return cut


ROOF_STEP = 0.5                                        # sections along each roofed letter edge
LOGO_LEDGE = 0.3                                       # a flat ceiling in the pockets may reach this far behind the skin
ROOF_START = 0.12                                      # the roofs start this far behind the skin (a clean strip of ceiling; 0.08 made the cut fail)


def logo_pocket(S):
    """Letters cut from inside to the 0.8 skin. Round 5: every downward-facing face of the pocket rises 45 deg towards the
    cavity (a slicer otherwise fills the pockets with support). Pocket = the straight prism along the logo's normal,
    united with one wedge per letter edge that has wall above it and runs flatter than 45 deg: a ruled loft through
    sections every ROOF_STEP along the edge, each starting exactly at the local skin depth (the skin's inner face lies
    deeper or shallower along the normal as the surface turns) and rising 1:1 towards the cavity. At the skin the
    outline is the straight prism's; floors stay flat."""
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    from OCP.gp import gp_Lin
    from build123d import Wire
    pr = logo_letters_prism()
    bb = pr.bounding_box()
    depth_out, depth_in = 1.0, WALL + 4.0
    w_end = depth_out + depth_in
    band = S.band(LOGO_SKIN, bb.min.Z - 1.0, bb.max.Z + w_end + 3.0)
    p, n, xd = logo_frame()
    up = np.cross(n, xd)
    P0 = p + depth_out * n
    si = IntCurvesFace_ShapeIntersector()
    si.Load(band.wrapped, 1e-6)

    def skin_depth(u, v):
        si.Perform(gp_Lin(gp_Pnt(*map(float, P0 + u * xd + v * up)), gp_Dir(*map(float, -n))), 0.0, 20.0)
        check(si.NbPnt() > 0, f"logo roof: no skin at ({u:.2f}, {v:.2f})")
        return min(si.WParameter(i) for i in range(1, si.NbPnt() + 1))

    def pt(u, v, w):
        return tuple(map(float, P0 + u * xd + v * up - w * n))

    eps, dl = 0.3, 0.2                                      # overlap into the letter, and in front of the skin (cut off)
    tool, n_w = pr, 0
    for poly in hw.letters_mm(LOGO_W):
        P = np.asarray(poly)
        area = 0.5 * (np.dot(P[:, 0], np.roll(P[:, 1], -1)) - np.dot(P[:, 1], np.roll(P[:, 0], -1)))
        for a_, b_ in zip(P, np.roll(P, -1, 0)):
            t = b_ - a_
            L = np.linalg.norm(t)
            if L < 1e-3:
                continue
            nrm = np.array([t[1], -t[0]]) / L * (1 if area > 0 else -1)          # outward of the letter
            if nrm[1] <= math.sin(math.radians(45)) + 1e-6:                          # not a ceiling flatter than 45 deg
                continue
            secs = []
            for f_ in np.linspace(0, 1, max(2, int(math.ceil(L / ROOF_STEP)) + 1)):
                u, v = a_ + f_ * t
                s0 = skin_depth(u, v - 0.05) + ROOF_START      # the roof starts just behind the skin: a line shared by
                R_ = w_end - s0                                 # the roof, the ceiling and the skin made the mesh leak
                secs.append(Wire.make_polygon([pt(u, v - eps, s0 - dl), pt(u, v - dl, s0 - dl), pt(u, v + R_, s0 + R_),
                                               pt(u, v - eps, s0 + R_)], close=True))
            wedge = Solid.make_loft(secs, ruled=True)
            check(wedge.is_valid and vol(wedge) > 0, "logo roof wedge invalid")
            tool = tool + wedge
            n_w += 1
    check(n_w >= 4 and len(tool.solids()) >= 1 and tool.is_valid, f"logo roofs: {n_w} wedges, tool valid {tool.is_valid}")
    pocket = tool & band
    check(len(pocket.solids()) >= 1 and pocket.is_valid, "logo pocket with roofs: invalid")
    return pocket


def slot_land_measure(door):
    """The slots measured on sections of the door (planes z, SLOT_SECTIONS along each slot, 0.3 inside its ends): at depths
    LAND_DY apart from the door's inner (back) face towards its face, the slot's two walls (the section's crossings nearest
    the slot's axis). The land on each side runs as far as its wall stays within 0.002 of where it meets the inner face.
    Per slot: width at the inner face (least, most), least land depth, and the opening on the face (least)."""
    ys = Y_DOOR_BACK - LAND_DY / 2 - LAND_DY * np.arange(int(round(DOOR_T / LAND_DY)))
    out = []
    for x0 in TUBE_X:
        w, depth, face = [], [], []
        for zs in np.linspace(AA_ZC - SLOT_L / 2 + 0.3, AA_ZC + SLOT_L / 2 - 0.3, SLOT_SECTIONS):
            seg = sm.section_segments(door, float(zs), bbox=(x0 - 9, x0 + 9, Y_PANEL - 1, Y_DOOR_BACK + 1), step=0.02)
            walls = []
            for y in ys:
                x1, y1, x2, y2 = seg.T
                k = (np.minimum(y1, y2) <= y) & (np.maximum(y1, y2) > y)
                xc_ = x1[k] + (y - y1[k]) * (x2[k] - x1[k]) / (y2[k] - y1[k])
                lo, hi = xc_[xc_ < x0], xc_[xc_ > x0]
                check(lo.size and hi.size, f"slot at x {x0:+.2f}, z {zs:.2f}: no walls at y {y:.3f}")
                walls.append((lo.max(), hi.min()))
            walls = np.array(walls)
            w.append(walls[0, 1] - walls[0, 0])
            face.append(walls[-1, 1] - walls[-1, 0])
            for j in (0, 1):
                off = np.abs(walls[:, j] - walls[0, j]) > 0.002
                depth.append((int(np.argmax(off)) if off.any() else len(ys)) * LAND_DY)
        out.append(dict(x=x0, w=min(w), w_max=max(w), depth=min(depth), depth_max=max(depth), face=min(face), n=len(w)))
    return out


def slot_land_check(door):
    SL = slot_land_measure(door)
    for q in SL:          # depth resolution LAND_DY: the land reads 0.60 when it is 0.60..0.61 deep
        check(abs(q["w"] - SLOT_W) < 1e-3 and abs(q["w_max"] - SLOT_W) < 1e-3 and abs(q["depth"] - RIM) < LAND_DY + 1e-6
              and abs(q["depth_max"] - RIM) < LAND_DY + 1e-6,
              f"slot at x {q['x']:+.2f}: land at the inner face {q['w']:.3f}..{q['w_max']:.3f} wide, {q['depth']:.3f}..{q['depth_max']:.3f} deep")
        want = SLOT_W + 2 * (DOOR_T - RIM) * math.tan(math.radians(hw.BEVEL_DEG))
        check(abs(q["face"] - want) < 0.05, f"slot at x {q['x']:+.2f}: opening on the face {q['face']:.3f}, designed {want:.3f}")
    check(SLOT_W - hw.ROD_W >= ROD_PLAY_MIN - 1e-9, f"slot {SLOT_W} over the rod {hw.ROD_W}: < {ROD_PLAY_MIN}")
    return SL


def door_part():
    d = xz_prism(DOOR_W, DOOR_H, DOOR_R, XOFF, DOOR_ZC, Y_PANEL, Y_DOOR_BACK)
    for x in TUBE_X:
        d = d - Pos(0, Y_PANEL + EXTRA, 0) * hw.flat_end_cutter(x, AA_ZC, SLOT_W, SLOT_L, EXTRA, RIM)
    # glass locating corners (L-shaped, 6 mm legs) on the back
    gx, gz0, gz1 = hw.GLASS_W / 2 + GLASS_RIB_CLR, GLASS_Z0 - GLASS_RIB_CLR, GLASS_Z0 + hw.GLASS_H + GLASS_RIB_CLR
    t, L, y0, y1 = GLASS_RIB_T, 6.0, Y_DOOR_BACK - 0.01, Y_DOOR_BACK + GLASS_RIB_H
    for sx in (-1, 1):
        for zc_, sz in ((gz0, -1), (gz1, 1)):
            xo = XOFF + sx * gx
            d = d + box(xo, xo + sx * t, y0, y1, zc_ + sz * t, zc_ - sz * L)
            d = d + box(xo + sx * t, xo - sx * (L - t), y0, y1, zc_, zc_ + sz * t)
    for sx, zl in TABS:
        zt, _, _, xh = tab_spec(sx, zl)
        d = d - ycyl(xh, zt, (DOOR_MAG_D + MAG_CLR_D) / 2, Y_DOOR_BACK - DOOR_MAG_H - MAG_CLR_H, Y_DOOR_BACK + 1)
    return one_solid(d, "door")


# ---- cups and ballast ------------------------------------------------------------------------------------------------
def terrace_section(zf):
    """The inner section at a floor, shrunk CAV_IN more in plan (along the section's own normals)."""
    sec = offset_rows(WALL, [zf])[0]
    P = sec[:, :2]
    d = np.roll(P, -1, 0) - np.roll(P, 1, 0)
    n = np.c_[d[:, 1], -d[:, 0]] / np.linalg.norm(d, axis=1)[:, None]      # outward for a counter-clockwise loop
    Q, _ = unloop(P - CAV_IN * n)
    return np.c_[Q, sec[:, 2]]


def floors(z_bottom, top):
    """Terrace floors from the top layer down: the top layer ends at `top`, each layer SEG[2] thick."""
    out, z = [], top - SEG[2]
    while z >= z_bottom - 1e-9:
        out.append(round(z, 4))
        z -= SEG[2]
    return out


def cup_bosses(S, z_floor):
    add = None
    for s in boss_spots():
        c = zcyl(s["x"], s["y"], s["r_boss"], SEAM - s["h"], SEAM)
        add = c if add is None else add + c
    return add


def cup_holes(c):
    for s in boss_spots():
        r = SEAM_R_HOLE if s["kind"] == "mag" else PIN_R_CUP
        d = SEAM_MAG_H + MAG_CLR_H if s["kind"] == "mag" else PIN_DEPTH
        c = c - zcyl(s["x"], s["y"], r, SEAM - d, SEAM + 1)
    return c


def make_cup(S, kind, layers, cast_to=None):
    """kind 'rock' (down to the pole) or 'flat' (cut at CUT_FLAT, foot rounded). layers: the terrace floors to cut.
    cast_to: the bowl is open (the inner surface) up to this level, for a level cast of steel shot in epoxy; the
    terraces start there."""
    c = one_solid(S.cup_outer(kind), f"cup-{kind} blank")
    if kind == "flat":
        bottom = [e for e in c.edges() if all(abs(e.position_at(t).Z - CUT_FLAT) < 1e-6 for t in (0, 0.3, 0.7))]
        check(len(bottom) >= 1, "flat cup: foot edge not found")
        c = c.fillet(FOOT_R, bottom)
        c = one_solid(c, "cup-flat after the foot rounding")
    cav = None
    for zf in layers:
        sec = terrace_section(zf)
        pr = extrude(plan_face(sec, zf), SEAM + 1 - zf)
        cav = pr if cav is None else cav + pr
    if cast_to is not None:
        cav = cav + box(-100, 100, -100, 100, -5, cast_to)
    cav = cav & S.inner
    env = c
    c = c - cav
    check(abs(vol(c) - (vol(env) - vol(cav & env))) < 1.0, f"cup-{kind}: the cavity cut failed")
    c = one_solid(c + (cup_bosses(S, min(layers)) & S.mid()), f"cup-{kind} + bosses")
    c = cup_holes(c)
    c = c - cable_hole(cup=True)                         # the cable notch, open upward: the cup comes off straight down
    return one_solid(c, f"cup-{kind}"), env, cav


# 2D packing of segments in a band: rows (DP over y), each row one orientation, segments centred in the free runs
PX = 0.1


def free_mask(loops, x0, x1, y0, y1, cavity=False, outline=None):
    """Raster (PX) of the free region. cavity=True: inside the one loop given. Otherwise the loops are a slice of the
    material: free = inside the largest loop (or `outline`, if given) and outside the material (even-odd over all loops)."""
    from matplotlib.path import Path as MPath
    xs, ys = np.arange(x0, x1, PX), np.arange(y0, y1, PX)
    XX, YY = np.meshgrid(xs, ys)
    pts = np.c_[XX.ravel(), YY.ravel()]
    cnt = np.zeros(len(pts), int)
    areas = []
    for L in loops:
        L = np.asarray(L)
        areas.append(0.5 * abs(np.dot(L[:, 0], np.roll(L[:, 1], 1)) - np.dot(L[:, 1], np.roll(L[:, 0], 1))))
        cnt += MPath(L).contains_points(pts)
    if cavity:
        return (cnt == 1).reshape(XX.shape), xs, ys
    outer = MPath(np.asarray(outline if outline is not None else loops[int(np.argmax(areas))])).contains_points(pts)
    free = (cnt % 2 == 0) & outer
    return free.reshape(XX.shape), xs, ys


def pack(free, xs, ys, gap=SEG_GAP):
    """Segments in the free raster: rows across (packed along y) or columns (packed along x), whichever holds more."""
    a = _pack_rows(free, xs, ys, gap)
    b = [(x, y, d, w) for y, x, w, d in _pack_rows(free.T, ys, xs, gap)]
    return a if len(a) >= len(b) else b


def _pack_rows(free, xs, ys, gap=SEG_GAP):
    """Segments in the free raster (eroded by gap), in rows: [(x, y, w_along_x, d_along_y)]."""
    from scipy.ndimage import binary_erosion
    r = int(round(gap / PX))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    f = binary_erosion(free, structure=(xx * xx + yy * yy <= r * r))
    ny = len(ys)
    types = [(SEG[0], SEG[1]), (SEG[1], SEG[0])]
    step = 5                                            # 0.5 mm row starts
    starts = list(range(0, ny, step))
    rowcache = {}

    def row(i, t):
        if (i, t) in rowcache:
            return rowcache[(i, t)]
        w, d = types[t]
        nd = int(math.ceil(d / PX))
        if i + nd > ny:
            rowcache[(i, t)] = (0, [])
            return rowcache[(i, t)]
        line = f[i:i + nd].all(0)
        segs = []
        k = 0
        n = len(line)
        while k < n:
            if not line[k]:
                k += 1
                continue
            e = k
            while e < n and line[e]:
                e += 1
            L = (e - k) * PX
            m = int((L + gap) // (w + gap))
            if m > 0:
                x0 = xs[k] + (L - (m * w + (m - 1) * gap)) / 2
                for q in range(m):
                    segs.append((x0 + w / 2 + q * (w + gap), ys[i] + d / 2, w, d))
            k = e
        rowcache[(i, t)] = (len(segs), segs)
        return rowcache[(i, t)]

    best = {}
    for i in reversed(range(0, ny + step, step)):
        if i >= ny:
            best[i] = (0, [])
            continue
        cand = best[min(i + step, ((ny + step - 1) // step) * step)] if (i + step) in best else (0, [])
        for t, (w, d) in enumerate(types):
            c, segs = row(i, t)
            if c == 0:
                continue
            j = i + int(math.ceil((d + gap) / PX / step)) * step
            nxt = best.get(j, (0, [])) if j < ny else (0, [])
            if c + nxt[0] > cand[0]:
                cand = (c + nxt[0], segs + nxt[1])
        best[i] = cand
    return best[0][1]


def usb_keepout(free, xs, ys, zf):
    """The USB head's and cable's plan footprints (+ HEAD_CLR) taken out of a segment band whose height comes within
    HEAD_CLR of theirs."""
    XX, YY = np.meshgrid(xs, ys)
    r = CABLE_D / 2
    for (x0, x1, y0, y1, z0, z1) in ((HEAD_X - HEAD_W / 2, HEAD_X + HEAD_W / 2, HEAD_Y0, HEAD_Y1, HEAD_Z0, HEAD_Z1),
                                     (HEAD_X - r, HEAD_X + r, HEAD_Y1, 60.0, CABLE_Z - r, CABLE_Z + r)):
        if zf + SEG[2] > z0 - HEAD_CLR and zf < z1 + HEAD_CLR:
            free &= ~((XX >= x0 - HEAD_CLR) & (XX <= x1 + HEAD_CLR) & (YY >= y0 - HEAD_CLR) & (YY <= y1 + HEAD_CLR))
    return free


def band_free_designed(zf, bosses):
    """Free region of a band (designed): the inner section at the floor, minus the bosses reaching into the band."""
    from matplotlib.path import Path as MPath
    sec = terrace_section(zf)[:, :2]
    f, xs, ys = free_mask([sec], -45, 45, -30, 32, cavity=True)
    lo, hi = offset_range(WALL)
    for z in (zf + SEG[2] / 2, zf + SEG[2] - 0.05):        # the terrace is cut by the inner surface too (the alcove's flare
        if lo < z < hi:                                     # pulls it back at the front near the seam)
            f &= free_mask([offset_rows(WALL, [z])[0][:, :2]], -45, 45, -30, 32, cavity=True)[0]
    XX, YY = np.meshgrid(xs, ys)
    pts = np.c_[XX.ravel(), YY.ravel()]
    a = np.linspace(0, 2 * np.pi, 72, endpoint=False)
    for s in bosses:
        if SEAM - s["h"] < zf + SEG[2]:
            disc = np.c_[s["x"] + s["r_boss"] * np.cos(a), s["y"] + s["r_boss"] * np.sin(a)]
            f &= ~MPath(disc).contains_points(pts).reshape(f.shape)
    return usb_keepout(f, xs, ys, zf), xs, ys


def band_free_measured(mesh, zf):
    """Free region of a band measured on the exported cup mesh: slices near the floor, mid-band and near the top."""
    f = None
    for dz in (0.05, SEG[2] / 2, SEG[2] - 0.05):
        sl = mesh.slice(normal="z", origin=(0, 0, zf + dz))
        loops = mesh_loops(sl)
        # round 6: the cable notch joins the wall's outer and inner curves into one C-shaped curve, so the largest curve
        # is no longer the outline; take the designed outer section (the notch then reads free; usb_keepout removes it)
        m, xs, ys = free_mask(loops, -45, 45, -30, 32, outline=offset_rows(0.0, [zf + dz], outer=True)[0][:, :2])
        f = m if f is None else f & m
    return usb_keepout(f, xs, ys, zf), xs, ys


def mesh_loops(sl):
    """Closed polylines (x, y) from a pyvista slice."""
    import pyvista as pv
    sl = sl.strip(join=True, max_length=100000)
    loops = []
    lines = sl.lines
    i = 0
    while i < len(lines):
        n = lines[i]
        ids = lines[i + 1:i + 1 + n]
        loops.append(sl.points[ids][:, :2])
        i += n + 1
    return loops


# ---- dummies (hardware, for the checks and the views) -----------------------------------------------------------
def board_bodies():
    """Seated board as boxes: glass, PCB stack, buttons, plugs; plus the rods (half-rounds through the slots)."""
    xc_ = XOFF
    out = {"glass": box(xc_ - hw.GLASS_W / 2, xc_ + hw.GLASS_W / 2, Y_GLASS0, Y_GLASS1, GLASS_Z0, GLASS_Z0 + hw.GLASS_H),
           "pcb": box(xc_ - hw.PCB_W / 2, xc_ + hw.PCB_W / 2, Y_GLASS1, Y_BOARD1, PCB_Z0, PCB_Z1)}
    for n, z in hw.BTN_Z.items():
        x0 = xc_ + hw.BTN_SIDE * hw.PCB_W / 2
        out[f"button-{n}"] = box(x0, x0 + hw.BTN_SIDE * hw.BTN_PROUD, Y_GLASS1, Y_GLASS1 + hw.BTN_DEPTH,
                                 PCB_Z0 + z - hw.BTN_LEN / 2, PCB_Z0 + z + hw.BTN_LEN / 2)
    for n, z in hw.PLUG_Z.items():
        x0 = xc_ - hw.BTN_SIDE * hw.PCB_W / 2
        out[f"plug-{n}"] = box(x0, x0 - hw.BTN_SIDE * hw.PLUG_PROUD, Y_GLASS1, Y_BOARD1,
                               PCB_Z0 + z - hw.PLUG_LEN / 2, PCB_Z0 + z + hw.PLUG_LEN / 2)
    return out


def rod_solids():
    r = hw.ROD_W / 2
    out = {}
    for n, x in zip(("rod-l", "rod-r"), TUBE_X):
        yf = Y_GLASS0 - hw.TAPE[1]                         # flat back on the glass (thickest tape), crown to the front
        z0 = AA_ZC - ROD_L / 2
        rod = Pos(x, yf, z0) * Cylinder(r, ROD_L, align=(Align.CENTER, Align.CENTER, Align.MIN))
        rod = rod - box(x - r - 1, x + r + 1, yf, yf + r + 1, z0 - 1, z0 + ROD_L + 1)
        out[n] = rod
    return out


def battery_solid(x=None):
    x = BAT_X if x is None else x
    return box(x - BAT_L / 2, x + BAT_L / 2, BAT_Y0, BAT_Y1, BAT_Z0, BAT_Z0 + BAT_HT)


def usb_solids(dz=0.0, dx=0.0):
    """The extension seated in the port (dz, dx: shifted, for the fault injection): its head, and its cable straight back
    from the head's far end to 3 mm outside the back surface."""
    return {"usb-head": box(HEAD_X + dx - HEAD_W / 2, HEAD_X + dx + HEAD_W / 2, HEAD_Y0, HEAD_Y1, HEAD_Z0 + dz, HEAD_Z1 + dz),
            "usb-cable": ycyl(HEAD_X + dx, CABLE_Z + dz, CABLE_D / 2, HEAD_Y1, Y_BACK_OUT + 3.0)}


def cable_hole(cup=False, r=None):
    """The round passage (CABLE_HOLE_D) round the cable through the back wall, from 2 mm behind the head; the cups' part
    runs straight up to the rim (open upward). r: another radius (the checks' passage)."""
    r = CABLE_HOLE_D / 2 if r is None else r
    h = ycyl(HEAD_X, CABLE_Z, r, HEAD_Y1 + 2.0, Y_BACK_OUT + 5.0)
    if cup:
        h = h + box(HEAD_X - r, HEAD_X + r, HEAD_Y1 + 2.0, Y_BACK_OUT + 5.0, CABLE_Z, SEAM + 1.0)
    return h


def cable_sweep(cable, up_to=None, from_z=None):
    """The cable's section moved straight along z: from its place up to `up_to` (a cup coming off below it), or from
    `from_z` up to its place (laid up into the body's notch): a box over the moved part plus the cable itself."""
    bb = cable.bounding_box()
    r = CABLE_D / 2
    xc_, zc_ = (bb.min.X + bb.max.X) / 2, (bb.min.Z + bb.max.Z) / 2
    z0, z1 = (zc_, up_to) if up_to is not None else (from_z, zc_)
    return cable + box(xc_ - r, xc_ + r, bb.min.Y, bb.max.Y, z0, z1)


def segment_solids(segs):
    return [box(x - w / 2, x + w / 2, y - d / 2, y + d / 2, z, z + SEG[2]) for x, y, w, d, z in segs]


# ---- mass properties of closed triangle meshes (from the exported files) ---------------------------------------------
def mesh_props(path, rho):
    """Mass (g), centroid, inertia tensor about the centroid (g mm^2) of a closed STL, by signed tetrahedra."""
    import pyvista as pv
    m = pv.read(str(path)).triangulate()
    f = m.faces.reshape(-1, 4)[:, 1:]
    a, b, c = (m.points[f[:, i]].astype(float) for i in range(3))
    v = np.einsum("ij,ij->i", a, np.cross(b, c)) / 6.0
    V = v.sum()
    check(V > 0, f"{path.name}: negative volume (normals inwards?)")
    cen = (v[:, None] * (a + b + c) / 4).sum(0) / V
    s = a + b + c
    C = np.zeros((3, 3))
    for i in range(3):
        for j in range(3):
            C[i, j] = (v * ((a[:, i] * a[:, j] + b[:, i] * b[:, j] + c[:, i] * c[:, j]) + s[:, i] * s[:, j])).sum() / 20.0
    C = C - V * np.outer(cen, cen)                      # second moments about the centroid
    I = np.trace(C) * np.eye(3) - C
    k = rho / 1000.0
    return dict(m=V * k, c=cen, I=I * k, V=V, pts=m.points)


def box_props(m, lo, hi):
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    d = hi - lo
    I = m / 12.0 * np.diag([d[1] ** 2 + d[2] ** 2, d[0] ** 2 + d[2] ** 2, d[0] ** 2 + d[1] ** 2])
    return dict(m=m, c=(lo + hi) / 2, I=I)


def combine(parts):
    M = sum(p["m"] for p in parts)
    G = sum(p["m"] * np.asarray(p["c"]) for p in parts) / M
    I = np.zeros((3, 3))
    for p in parts:
        r = np.asarray(p["c"]) - G
        I += p["I"] + p["m"] * (np.dot(r, r) * np.eye(3) - np.outer(r, r))
    return M, G, I


def support_heights(pts, G, axis, angles):
    """Height of the centre of mass over the desk when the body rests tilted by each angle (support function)."""
    out = []
    for a in angles:
        t = math.radians(a)
        d = np.array([math.sin(t), 0, -math.cos(t)]) if axis == "roll" else np.array([0, math.sin(t), -math.cos(t)])
        out.append(float((pts @ d).max() - G @ d))
    return np.array(out)


def righting_limit(pts, G, axis, sign):
    th = np.arange(0, 120.01, 0.5)
    u = support_heights(pts, G, axis, sign * th)
    down = np.where(np.diff(u) < -1e-6)[0]
    return (float(th[down[0]]) if len(down) else 120.0), u, th


# ---- measurements ------------------------------------------------------------------------------------------------------
def bspline_faces(shape):
    return [f for f in shape.faces() if f.geom_type == GeomType.BSPLINE]


def _on_surface(f, ref):
    from build123d import Vertex
    c = f.center()
    p = f.position_at(0.5, 0.5) if hasattr(f, "position_at") else c
    return dist_shapes(Vertex(p.X, p.Y, p.Z), ref)[0] < 1e-3


def sweep_y(shape, y_from=-80.0):
    """The volume a solid sweeps moving straight along +y from far in front to where it is."""
    bb = shape.bounding_box()
    from build123d import Solid as _S
    # boxes are swept exactly; other shapes by their bounding box in x-z (used for boxes only)
    return box(bb.min.X, bb.max.X, y_from, bb.max.Y, bb.min.Z, bb.max.Z)


def sweep_z(shape, z_from=-60.0):
    bb = shape.bounding_box()
    return box(bb.min.X, bb.max.X, bb.min.Y, bb.max.Y, z_from, bb.max.Z)


def near_faces(shape, a, margin):
    """Faces of `shape` whose bounding boxes come within `margin` of a's bounding box."""
    A = a.bounding_box()
    out = []
    for f in shape.faces():
        B = f.bounding_box()
        if (B.min.X <= A.max.X + margin and B.max.X >= A.min.X - margin and B.min.Y <= A.max.Y + margin and
                B.max.Y >= A.min.Y - margin and B.min.Z <= A.max.Z + margin and B.max.Z >= A.min.Z - margin):
            out.append(f)
    return out


def gap_to(a, b, margin=6.0):
    """Distance from a to b's surface, looking only at b's faces near a (BRepExtrema on the whole body is slow).
    Returns margin if nothing is that close."""
    fs = near_faces(b, a, margin)
    return min(margin, dist_shapes(a, Compound(fs))[0]) if fs else margin


def clear(a, b, what, need, touch_ok=False):
    """Gap between two solids, measured; overlap raises. Returns the gap."""
    v = overlap(a, b)
    check(v < EPS_V, f"{what}: overlap {v:.4f} mm3")
    g = gap_to(a, b)
    check(touch_ok or g >= need - 1e-6, f"{what}: gap {g:.3f} < {need}")
    return g


def arc_profile(mesh_path, z0=0.25):
    """The rocking arc measured on the exported cup: the section y = 0, its outline x left / right at z levels."""
    import pyvista as pv
    m = pv.read(str(mesh_path))
    sl = m.slice(normal="y", origin=(0, 0, 0))
    pts = sl.points
    lines = sl.lines
    segs = []
    i = 0
    while i < len(lines):
        n = lines[i]
        ids = lines[i + 1:i + 1 + n]
        for a_, b_ in zip(ids[:-1], ids[1:]):
            segs.append((pts[a_], pts[b_]))
        i += n + 1
    out = []
    for z in np.r_[np.arange(z0, 0.25, 0.01), np.arange(0.25, SEAM - 0.25, 0.25)]:
        xs = []
        for p, q in segs:
            if (p[2] - z) * (q[2] - z) <= 0 and p[2] != q[2]:
                t = (z - p[2]) / (q[2] - p[2])
                xs.append(p[0] + t * (q[0] - p[0]))
        if xs:
            out.append((z, min(xs), max(xs)))
    return np.array(out)


def fill_plan(cells, M0, Mx0, tol=PLUMB_TOL, k_max=4):
    """Which segments to leave out so the clock hangs plumb (centre of mass over the arc's centre, x 0): the fewest, then
    the closest. cells: [(x, y, w, d, z)]. Returns (left-out indices, G_x)."""
    import itertools
    xs = np.array([c[0] for c in cells])
    n = len(xs)
    order = list(np.argsort(xs))
    cand = sorted(set(order[:10] + order[-10:]))
    best = None
    for k in range(0, k_max + 1):
        for combo in itertools.combinations(cand, k):
            M = M0 + SEG_G * (n - k)
            gx = (Mx0 + SEG_G * (xs.sum() - xs[list(combo)].sum())) / M
            if best is None or abs(gx) < abs(best[1]) - 1e-12:
                best = (combo, gx)
        if abs(best[1]) <= tol:
            break
    return list(best[0]), float(best[1])


def mass_parts(meshes, segs, battery=None, extra=(), m_board=M_BOARD, m_bat=M_BAT):
    """Mass model: printed parts (and the cast) from the exported meshes, the rest as boxes (assumed masses)."""
    parts = [dict(meshes[n], name=n) for n in meshes] + [dict(e) for e in extra]
    lo = (XOFF - hw.PCB_W / 2, Y_GLASS0, PCB_Z0)
    parts.append(dict(box_props(m_board, lo, (XOFF + hw.PCB_W / 2, Y_BOARD1, PCB_Z1)), name="board"))
    b = battery or (BAT_X - BAT_L / 2, BAT_Y0, BAT_Z0, BAT_X + BAT_L / 2, BAT_Y1, BAT_Z0 + BAT_HT)
    parts.append(dict(box_props(m_bat, b[:3], b[3:]), name="battery"))
    rod_m = 1.19 * (math.pi * (hw.ROD_W / 2) ** 2 / 2 * ROD_L) / 1000
    for x in TUBE_X:
        parts.append(dict(box_props(rod_m, (x - 4, Y_GLASS0 - 4, AA_ZC - ROD_L / 2), (x + 4, Y_GLASS0, AA_ZC + ROD_L / 2)), name="rod"))
    parts.append(dict(m=M_MISC, c=np.array([0.0, 8.0, 35.0]), I=np.zeros((3, 3)), name="misc"))      # the study's misc
    for x, y, w, d, z in segs:
        parts.append(dict(box_props(SEG_G, (x - w / 2, y - d / 2, z), (x + w / 2, y + d / 2, z + SEG[2])), name="segment"))
    return parts


def stability(pts, parts):
    M, G, I = combine(parts)
    lim_r, u_r, th = righting_limit(pts, G, "roll", 1)
    lim_l, u_l, _ = righting_limit(pts, G, "roll", -1)
    lim_f, u_f, _ = righting_limit(pts, G, "pitch", -1)
    lim_b, u_b, _ = righting_limit(pts, G, "pitch", 1)
    fine = np.arange(-8, 8.001, 0.1)
    rest = float(fine[int(np.argmin(support_heights(pts, G, "pitch", fine)))])
    return dict(M=M, G=G, I=I, lim=(lim_r, lim_l, lim_f, lim_b), u=(u_r, u_l, u_f, u_b), th=th, rest_pitch=rest)


def rocking(st):
    M, G, I = st["M"], st["G"], st["I"]
    h = G[2]
    margin = RR - h
    T = 2 * math.pi * math.sqrt((I[1, 1] / M + h * h) * 1e-6 / (9.81 * margin * 1e-3)) if margin > 0 else float("nan")
    k = M / 1000 * 9.81 * margin / 1000 * math.pi / 180 * 1000          # righting stiffness, mN m per degree
    return margin, T, k


def shot_in_voids(mesh, cells, layers, top, grain=2.0, V=0.25):
    """Steps-only cup: the voids round the segments (measured on the exported mesh, voxels of V) that steel shot of
    `grain` reaches (3D opening by its radius + 0.1). Returns (volume cm3, centroid)."""
    from matplotlib.path import Path as MPath
    from scipy.ndimage import distance_transform_edt
    xs, ys = np.arange(-42, 42, V) + V / 2, np.arange(-26, 31, V) + V / 2
    zs = np.arange(min(layers), top, V) + V / 2
    XX, YY = np.meshgrid(xs, ys, indexing="ij")
    pts = np.c_[XX.ravel(), YY.ravel()]
    vox = np.zeros((len(xs), len(ys), len(zs)), bool)
    for k, z in enumerate(zs):
        loops = mesh_loops(mesh.slice(normal="z", origin=(0, 0, z)))
        cnt = np.zeros(len(pts), int)
        areas = []
        for L in loops:
            cnt += MPath(L).contains_points(pts)
            areas.append(abs(np.dot(L[:, 0], np.roll(L[:, 1], 1)) - np.dot(L[:, 1], np.roll(L[:, 0], 1))))
        free = ((cnt % 2 == 0) & MPath(loops[int(np.argmax(areas))]).contains_points(pts)).reshape(XX.shape)
        for x, y, w, d, zf in cells:
            if zf <= z <= zf + SEG[2]:
                free &= ~((np.abs(XX - x) <= w / 2) & (np.abs(YY - y) <= d / 2))
        vox[:, :, k] = free
    r_ = grain / 2 + 0.1
    core = distance_transform_edt(vox, sampling=V) >= r_
    fill = (distance_transform_edt(~core, sampling=V) <= r_) & vox
    idx = np.argwhere(fill)
    c = np.c_[xs[idx[:, 0]], ys[idx[:, 1]], zs[idx[:, 2]]].mean(0) if len(idx) else np.zeros(3)
    return fill.sum() * V ** 3 / 1000, c


# ---- round 2 helpers ----------------------------------------------------------------------------------------------
def row_runs(mesh, cells):
    """For each row of segments (same floor, same y), the free run along x it lies in, measured on the exported cup."""
    rows = {}
    for i, c in enumerate(cells):
        rows.setdefault((c[4], round(c[1], 2)), []).append(i)
    out = []
    from scipy.ndimage import binary_erosion
    for (z, y), idx in rows.items():
        f, xs, ys = band_free_measured(mesh, z)
        r_ = int(round(SEG_GAP / PX))
        yy, xx = np.mgrid[-r_:r_ + 1, -r_:r_ + 1]
        f = binary_erosion(f, structure=(xx * xx + yy * yy <= r_ * r_))
        d = cells[idx[0]][3]
        k = (ys >= y - d / 2) & (ys <= y + d / 2)
        line = f[k].all(0)
        runs = {}                                       # round 6: a row may be split into runs (by the USB head's footprint)
        for i in idx:
            j = int(np.argmin(np.abs(xs - cells[i][0])))
            check(line[j], f"row at y {y}: segment at x {cells[i][0]:.1f} is not on free ground")
            a, b = j, j
            while a > 0 and line[a - 1]:
                a -= 1
            while b < len(line) - 1 and line[b + 1]:
                b += 1
            runs.setdefault((a, b), []).append(i)
        for (a, b), ii in runs.items():
            out.append(dict(z=z, y=y, idx=sorted(ii, key=lambda i: cells[i][0]), run=(xs[a], xs[b] + PX)))
    return out


def spot_box(x):
    return box(x - SEG[0] / 2, x + SEG[0] / 2, BULK_Y1, BULK_Y1 + SEG[2], TRIM_SPOT_Z0, TRIM_SPOT_Z0 + SEG[1])


def spot_part(x):
    bb = spot_box(x).bounding_box()
    return dict(box_props(SEG_G, (bb.min.X, bb.min.Y, bb.min.Z), (bb.max.X, bb.max.Y, bb.max.Z)), name="trim spot")


def trim_plan(cells, runs, Mx_fixed, M_fixed, best_effort=False):
    """Plumb: the fewest trim spots (segments on the bulkhead's back, right), then the fewest trim-layer segments left out
    (leftmost first), the rest slid along their rows (all rows by the same fraction of their slack) so the centre of mass
    lands on x 0. Returns a dict: kept, left out, spots used, G_x, slide fraction, and the trim layer's reach by sliding
    (G_x range with every segment in and no spot)."""
    order = sorted(range(len(cells)), key=lambda i: cells[i][0])
    gap = SEG_GAP

    def layout(removed, t):
        kept = []
        for r_ in runs:
            ids = [i for i in r_["idx"] if i not in removed]
            if not ids:
                continue
            w = cells[ids[0]][2]
            B = len(ids) * w + (len(ids) - 1) * gap
            c_lo, c_hi = r_["run"][0] + B / 2, r_["run"][1] - B / 2
            check(c_hi >= c_lo - 1e-6, "a row does not fit its run")
            x0 = c_lo + t * (c_hi - c_lo) - B / 2
            for q, i in enumerate(ids):
                x, y, w_, d, z = cells[i]
                kept.append((x0 + w / 2 + q * (w + gap), y, w_, d, z))
        return kept

    def gx(kept, spots):
        M = M_fixed + SEG_G * (len(kept) + len(spots))
        return (Mx_fixed + SEG_G * (sum(c[0] for c in kept) + sum(spots))) / M

    auth = (gx(layout(set(), 0.0), []), gx(layout(set(), 1.0), []))
    for e in range(len(TRIM_SPOTS) + 1):
        spots = list(TRIM_SPOTS[:e])
        for k in range(len(cells)):
            removed = set(order[:k])
            lo, hi = gx(layout(removed, 0.0), spots), gx(layout(removed, 1.0), spots)
            if lo <= 0 <= hi:
                t = 0.0 if hi == lo else -lo / (hi - lo)
                kept = layout(removed, t)
                return dict(kept=kept, left=[cells[i] for i in sorted(removed)], spots=spots, gx=gx(kept, spots), t=t, auth=auth)
    msg = f"no trim plan reaches plumb (trim layer's reach {auth[0]:+.2f}..{auth[1]:+.2f}, spots {TRIM_SPOTS})"
    check(best_effort, msg)
    best = None                                         # the closest plan, for the report of a failed build
    for k in range(len(cells)):
        for t in (0.0, 1.0):
            kept = layout(set(order[:k]), t)
            g = gx(kept, list(TRIM_SPOTS))
            if best is None or abs(g) < abs(best["gx"]):
                best = dict(kept=kept, left=[cells[i] for i in sorted(order[:k])], spots=list(TRIM_SPOTS), gx=g, t=t, auth=auth, fail=msg)
    return best


def roll_full(pts, G, step=0.25):
    """Sideways over the whole revolution: the angles where the centre of mass is lowest (rest positions)."""
    th = np.arange(-180, 180, step)
    u = support_heights(pts, G, "roll", th)
    mins = [float(th[i]) for i in range(len(th)) if u[i] < u[i - 1] - 1e-9 and u[i] <= u[(i + 1) % len(th)] + 1e-9]
    maxs = [float(th[i]) for i in range(len(th)) if u[i] > u[i - 1] + 1e-9 and u[i] >= u[(i + 1) % len(th)] - 1e-9]
    return mins, maxs


def pitch_limits(pts, G, step=0.02, top=60.0):
    """Fore-aft: the rest angle (lowest centre of mass near upright) and the crests forward and backward, found from the
    rest angle; returned as (rest, forward limit, backward limit) in degrees from upright (+ = back)."""
    th = np.arange(-top, top + step / 2, step)
    u = support_heights(pts, G, "pitch", th)
    near = np.abs(th) <= 10
    i0 = int(np.flatnonzero(near)[np.argmin(u[near])])
    i = i0
    while i > 0 and u[i - 1] >= u[i] - 1e-12:
        i -= 1
    j = i0
    while j < len(th) - 1 and u[j + 1] >= u[j] - 1e-12:
        j += 1
    return float(th[i0]), float(-th[i]), float(th[j])


def overhangs(path, down, bed_cut, outer_tree=None, limit=45.0):
    """Area (mm2) of faces that look down more than `limit` deg from vertical in a print orientation (down = the
    direction to the bed), not counting faces on the bed; split into the outer surface and the rest when outer_tree is
    given (a KD tree of outer-surface points)."""
    import pyvista as pv
    m = pv.read(str(path)).compute_normals(cell_normals=True, point_normals=False, auto_orient_normals=False)
    n = m.cell_data["Normals"]
    a = m.compute_cell_sizes(length=False, volume=False).cell_data["Area"]
    c = m.cell_centers().points
    d = np.asarray(down, float)
    over = n @ d > math.cos(math.radians(limit))        # normal within `limit` of straight down: steeper than 45 deg from vertical
    on_bed = bed_cut(c)
    k = over & ~on_bed
    tot = float(a[k].sum())
    if outer_tree is None:
        return tot, None, c[k], a[k]
    dist, _ = outer_tree.query(c[k])
    outer = float(a[k][dist < 0.6].sum())
    return tot, outer, c[k], a[k]


def keel_grid(nc, zs):
    old = P["NC"]
    P["NC"] = nc
    try:
        return grid(zs)
    finally:
        P["NC"] = old


def keel_meshes():
    """Outer surfaces of the whole clock (body + rocking cup) with the study's keel and the chosen one, for the views."""
    import pyvista as pv
    zs = z_rows(ZB0, ZB1, 400)
    for name, nc in KEELS.items():
        G = keel_grid(nc, zs)
        Gc = np.concatenate([G, G[:, :1]], 1)
        sg = pv.StructuredGrid(Gc[..., 0][..., None], Gc[..., 1][..., None], Gc[..., 2][..., None])
        sg.extract_surface(algorithm="dataset_surface").triangulate().save(str(OUT / f"keel-{name}.stl"))


def arc_gauge():
    """Concave R RR cradle (axis along y): sits the cup in it to check the arc against the light, or carries sandpaper to
    true it. Printed flat side down."""
    g = box(-30, 30, -10, 10, -6, 12)
    cyl = Plane(origin=(0, -15, RR), x_dir=(1, 0, 0), z_dir=(0, 1, 0)) * Cylinder(RR, 30, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return one_solid(g - cyl, "arc gauge")


def led_keepout():
    """The room behind the logo for two LEDs (3..6 mm behind the letters), as a box in the logo's frame."""
    p, n, xd = logo_frame()
    up = np.cross(n, xd)
    h = hw.LETTERS_ASPECT * LOGO_W
    c = p - 6.5 * n + LED_SHIFT * xd                   # 4.5..8.5 behind the letters' centre
    pl = Plane(origin=tuple(c), x_dir=tuple(xd), z_dir=tuple(n))
    return extrude(pl * Rectangle(LOGO_W - 5, h - 2), 2.0, both=True)


def door_tool_access():
    """A blunt tool from below onto the door's back strip under the PCB (to push the door out): the space it needs. Round
    6: TOOL_W wide, right of the USB head (it reaches there with the plug in; round 5: 12 wide on the door's centre)."""
    x0 = HEAD_X + HEAD_W / 2 + HEAD_CLR
    return box(x0, x0 + TOOL_W, Y_DOOR_BACK + 0.3, Y_DOOR_BACK + 4.0, -20, PCB_Z0 - 0.3)


# ---- round 3 checks ------------------------------------------------------------------------------------------------
def pole_sections(mesh):
    """The sections x 0.01 and y 0.01 of the exported rocking cup: one curve runs through the bottom (lowest point, both
    sides of it reached, no gap between its points near the bottom). Returns {section: (lowest z, largest step near it)}."""
    out = {}
    for normal, k in (("y", 0), ("x", 1)):
        # 0.01 off the pole: a slice through the pole vertex itself splits the curve there
        sl = mesh.slice(normal=normal, origin=(0.01, 0.01, 0)).strip(join=True, max_length=1000000)
        lines, i, best = sl.lines, 0, None
        while i < len(lines):
            n = lines[i]
            P = sl.points[lines[i + 1:i + 1 + n]]
            if best is None or P[:, 2].min() < best[:, 2].min():
                best = P
            i += n + 1
        check(best is not None, f"no {normal} 0 section of the rocking cup")
        near = best[:, 2] < 0.05
        check(near.any() and best[:, 2].min() <= 0.002, f"section {normal} 0 does not reach the pole (lowest {best[:, 2].min():.4f})")
        check(best[near, k].min() < -0.2 and best[near, k].max() > 0.2, f"section {normal} 0 stops at the pole (one side only)")
        seg = np.linalg.norm(np.diff(best, axis=0), axis=1)
        step = float(seg[near[:-1] & near[1:]].max()) if (near[:-1] & near[1:]).any() else 0.0
        check(step < 2.5, f"section {normal} 0: a {step:.2f} gap near the pole")   # chords at 0.01 deflection on R44: <= 1.9
        out[normal] = (float(best[:, 2].min()), step)
    return out


def crest_range(pts, G, axis, sign, lim, tol=0.005):
    """The tipping crest's width: the angles near `lim` where the centre of mass is within tol of its highest."""
    th = np.arange(max(lim - 4, 0), lim + 4, 0.02)
    u = support_heights(pts, G, axis, sign * th)
    k = u >= u.max() - tol
    return float(th[k].min()), float(th[k].max())


LOGO_X_OLD = 28.0                                      # round 1-3 position, for logo-compare.png


def logo_outside(S, x=None):
    """Outside: the letters' footprint on the outer surface (outline points projected along the logo's direction):
    its smallest distance past the end of the alcove's outer flare (sd_open - FLARE; > 0 = plain belly), its x span, and
    how far the surface turns from the front (-y) at its left end, centre and right end (deg)."""
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    from OCP.gp import gp_Lin
    global LOGO_X
    keep = LOGO_X
    try:
        if x is not None:
            LOGO_X = x
        p, n, xd = logo_frame()
        up = np.cross(n, xd)
        si = IntCurvesFace_ShapeIntersector()
        si.Load(S.outer.wrapped, 1e-6)
        hits = []
        for poly in hw.letters_mm(LOGO_W):
            for u_, v_ in np.asarray(poly):
                o = p + u_ * xd + v_ * up + 3.0 * n
                si.Perform(gp_Lin(gp_Pnt(*map(float, o)), gp_Dir(*map(float, -n))), 0.0, 40.0)
                check(si.NbPnt() > 0, "logo outline misses the surface")
                w = min(si.WParameter(i) for i in range(1, si.NbPnt() + 1))
                hits.append(o - w * n)
        hits = np.array(hits)
        clr = float(min(sd_open(h[0], h[2]) for h in hits)) - P["FLARE"]

        def turn(xx):
            k = int(np.argmin(np.abs(DENSE_Z - LOGO_ZC)))
            g, nn = G_OUT[k], N_OUT[k]
            sel = np.where(g[:, 1] < 0)[0]
            j = sel[np.argmin(np.abs(g[sel, 0] - xx))]
            v = nn[j] / np.linalg.norm(nn[j])
            return math.degrees(math.acos(np.clip(-v[1], -1, 1)))
        return dict(clr=clr, x=(float(hits[:, 0].min()), float(hits[:, 0].max())),
                    turn=(turn(hits[:, 0].min()), turn(float(p[0])), turn(hits[:, 0].max())))
    finally:
        LOGO_X = keep


def logo_decal(S, x):
    """The letters' footprint as a thin skin (0.3) of the outer surface at logo position x, for the views."""
    global LOGO_X
    keep = LOGO_X
    try:
        LOGO_X = x
        pr = logo_letters_prism(1.0, 2.0)
        bb = pr.bounding_box()
        return pr & (S.outer - S.band(0.3, bb.min.Z - 1, bb.max.Z + 1))
    finally:
        LOGO_X = keep


def logo_outline_check(S, body, off=0.15, step=0.3):
    """The lit outline: just behind the skin's inner face (0.05), points `off` inside every letter edge are pocket (void)
    and points `off` outside are material; top edges included. Returns the counts and the worst edge kind."""
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN, TopAbs_OUT
    from OCP.gp import gp_Lin
    p, n, xd = logo_frame()
    up = np.cross(n, xd)
    P0 = p + 1.0 * n
    band = S.band(LOGO_SKIN, LOGO_ZC - 8, LOGO_ZC + 8)
    si = IntCurvesFace_ShapeIntersector()
    si.Load(band.wrapped, 1e-6)
    bad, n_in, n_out, tops = [], 0, 0, 0
    for poly in hw.letters_mm(LOGO_W):
        P = np.asarray(poly)
        area = 0.5 * (np.dot(P[:, 0], np.roll(P[:, 1], -1)) - np.dot(P[:, 1], np.roll(P[:, 0], -1)))
        for a, b in zip(P, np.roll(P, -1, 0)):
            L = np.linalg.norm(b - a)
            if L < 2 * step:
                continue
            t = (b - a) / L
            nrm = np.array([t[1], -t[0]]) * (1 if area > 0 else -1)          # outward in the letter's plane
            for s_ in np.arange(step, L - step + 1e-9, step):
                q = a + s_ * t
                o = P0 + q[0] * xd + q[1] * up
                si.Perform(gp_Lin(gp_Pnt(*map(float, o)), gp_Dir(*map(float, -n))), 0.0, 20.0)
                if not si.NbPnt():
                    continue
                w = min(si.WParameter(i) for i in range(1, si.NbPnt() + 1)) + 0.05
                for sign, want in ((-1, TopAbs_OUT), (1, TopAbs_IN)):
                    qq = q + sign * off * nrm
                    pt = P0 + qq[0] * xd + qq[1] * up - w * n
                    c = BRepClass3d_SolidClassifier(body.wrapped, gp_Pnt(*map(float, pt)), 1e-6)
                    st = c.State()
                    if sign < 0:
                        n_in += 1
                    else:
                        n_out += 1
                    tops += nrm[1] > 0.7
                    if st != want:
                        bad.append((round(float(q[0]), 2), round(float(q[1]), 2), "inside" if sign < 0 else "outside"))
    check(not bad, f"logo outline moved at the skin: {len(bad)} points, e.g. {bad[:4]}")
    return dict(n_in=n_in, n_out=n_out, tops=tops, off=off)


def logo_roof_check(S, path, slope_tol=1.0):
    """On the exported body: faces in the logo's pockets that look down more steeply than 45 deg (+ slope_tol) lie
    within LOGO_LEDGE of the skin (measured along the logo's normal to the skin's inner face). Returns the largest such
    distance and the steepest downward slope found further in (should be the 45 deg roofs)."""
    import pyvista as pv
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    from OCP.gp import gp_Lin
    p, n, xd = logo_frame()
    up = np.cross(n, xd)
    m = pv.read(str(path)).compute_normals(cell_normals=True, point_normals=False, auto_orient_normals=False)
    c = m.cell_centers().points
    nn = m.cell_data["Normals"]
    d = c - p
    u, v, w = d @ xd, d @ up, -(d @ n)
    reg = (np.abs(u) < LOGO_W / 2 + 0.5) & (v > -6) & (v < 6 + WALL + 4) & (w > 0.3) & (w < WALL + 5)
    lim = -math.sin(math.radians(45 + slope_tol))
    steep = reg & (nn[:, 2] < lim)
    band = S.band(LOGO_SKIN, LOGO_ZC - 8, LOGO_ZC + 14)
    si = IntCurvesFace_ShapeIntersector()
    si.Load(band.wrapped, 1e-6)
    far = 0.0
    for q in c[steep]:
        si.Perform(gp_Lin(gp_Pnt(*map(float, q)), gp_Dir(*map(float, n))), -5.0, 20.0)
        if si.NbPnt():
            far = max(far, min(abs(si.WParameter(i)) for i in range(1, si.NbPnt() + 1)))
    down = reg & (nn[:, 2] < -0.5)
    slope = float(np.degrees(np.arcsin(-nn[down, 2])).max()) if down.any() else 0.0
    roof = reg & (nn[:, 2] < -0.5) & (nn[:, 2] >= lim)
    check(far <= LOGO_LEDGE, f"logo pockets: a face steeper than 45 deg reaches {far:.2f} behind the skin (> {LOGO_LEDGE})")
    return dict(n_steep=int(steep.sum()), far=far, n_roof=int(roof.sum()), steepest=slope)


def logo_floor_check(body, outer_face, spacing=0.4, edge=0.25):
    """Rays along the logo's projection through a grid of points inside both letters (at least `edge` from their
    outlines): the first material is the skin (its normal thickness = the floor point's distance to the outer surface);
    behind the floor the column is open to the cavity where the ray runs free LOGO_OPEN at least. A letter is one
    connected void, so it is sealed only if none of its columns opens; each must open over LOGO_OPEN_MIN of its floor."""
    from matplotlib.path import Path as MPath
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    from OCP.gp import gp_Lin
    from build123d import Vertex
    p, n, xd = logo_frame()
    up = np.cross(n, xd)
    si = IntCurvesFace_ShapeIntersector()
    si.Load(body.wrapped, 1e-6)
    res = []
    for li, poly in enumerate(hw.letters_mm(LOGO_W)):
        poly = np.asarray(poly)
        segs = np.hstack([poly, np.roll(poly, -1, 0)])
        uu, vv = np.meshgrid(np.arange(poly[:, 0].min(), poly[:, 0].max(), spacing), np.arange(poly[:, 1].min(), poly[:, 1].max(), spacing))
        q = np.c_[uu.ravel(), vv.ravel()]
        q = q[MPath(poly).contains_points(q)]
        q = q[sm.seg_dist(q, segs) >= edge]
        check(len(q) >= 20, f"logo letter {li}: only {len(q)} sample points")
        for u_, v_ in q:
            o = p + u_ * xd + v_ * up + 3.0 * n
            si.Perform(gp_Lin(gp_Pnt(*map(float, o)), gp_Dir(*map(float, -n))), 0.0, 40.0)
            w = sorted(si.WParameter(i) for i in range(1, si.NbPnt() + 1))
            check(len(w) >= 2, f"logo letter {li} at ({u_:.1f}, {v_:.1f}): the ray crosses {len(w)} faces")
            f = o - w[1] * n
            thick = dist_shapes(Vertex(*map(float, f)), outer_face)[0]
            free = (w[2] - w[1]) if len(w) > 2 else 40.0
            res.append((li, thick, free))
    r_ = np.array(res)
    opn = {int(li): float(np.mean(r_[r_[:, 0] == li, 2] >= LOGO_OPEN)) for li in set(r_[:, 0])}
    out = dict(n=len(r_), lo=float(r_[:, 1].min()), hi=float(r_[:, 1].max()), open=opn, nl=len(hw.letters_mm(LOGO_W)))
    check(SKIN_RANGE[0] <= out["lo"] and out["hi"] <= SKIN_RANGE[1], f"logo skin {out['lo']:.3f}..{out['hi']:.3f} outside {SKIN_RANGE}")
    check(len(opn) == out["nl"] and min(opn.values()) >= LOGO_OPEN_MIN, f"logo: share of each letter open to the cavity {opn}")
    return out


# ---- build ------------------------------------------------------------------------------------------------------------
def packing(layers, bosses, measured_mesh=None):
    """Segments per layer: [(x, y, w, d, z_floor)]; designed from the sections or measured on a mesh."""
    out = {}
    for zf in layers:
        if measured_mesh is None:
            f, xs, ys = band_free_designed(zf, bosses)
        else:
            f, xs, ys = band_free_measured(measured_mesh, zf)
        out[zf] = [(x, y, w, d, zf) for x, y, w, d in pack(f, xs, ys)]
    return out




def best_stack(z_bottom, bosses, top_max=SEG_TOP_MAX):
    """The stack height (top layer ending 0..SEG[2] below top_max, 0.25 steps) that holds the most segments; ties: the
    lower stack. Returns ({floor z: segments}, top)."""
    best = None
    for i in range(int(SEG[2] / 0.25)):
        top = top_max - 0.25 * i
        pk = {z: v for z, v in packing(floors(z_bottom, top), bosses).items() if v}
        n = sum(len(v) for v in pk.values())
        if best is None or n > best[0] or (n == best[0] and top < best[2]):
            best = (n, pk, top)
    return best[1], best[2]


def battery_sweeps():
    """The battery's way up (battery_path) as boxes: straight up at X1, across at Z_MID, straight up at X2 to its seat."""
    bp, h = BAT_PATH, BAT_L / 2
    out = {"up": box(bp["X1"] - h, bp["X1"] + h, BAT_Y0, BAT_Y1, -60, bp["Z_MID"] + BAT_HT)}
    if bp["Z_MID"] < BAT_Z0:
        out["across"] = box(min(bp["X1"], bp["X2"]) - h, max(bp["X1"], bp["X2"]) + h, BAT_Y0, BAT_Y1, bp["Z_MID"], bp["Z_MID"] + BAT_HT)
        out["up to the seat"] = box(bp["X2"] - h, bp["X2"] + h, BAT_Y0, BAT_Y1, bp["Z_MID"], BAT_Z0 + BAT_HT)
    return out


def usb_checks(body, cups, door, bat, bd, rods, cast, seg_sets, dz=0.0, dx=0.0):
    """The extension's head and cable (dz, dx: shifted, for the fault injection) against everything, seated and on the
    ways in and out: the plug pushed up into the port from below (cup off, battery in), the cable laid up into the body's
    notch, each cup coming off straight down. Returns the measured gaps."""
    R = {}
    u = usb_solids(dz, dx)
    head, cable = u["usb-head"], u["usb-cable"]
    pas = CABLE_HOLE_D / 2 - CABLE_D / 2 - 0.01           # the cable in its round passage
    y_in = Y_BACK_OUT - WALL - 1.0                          # the cable's run inside, up to 1 mm before the back wall's inner face
    run = ycyl(HEAD_X + dx, CABLE_Z + dz, CABLE_D / 2, HEAD_Y1, y_in)
    up = sweep_z(head, -30.0)                               # the plug's way up into the port
    # the passage first (an obstruction in it would also show as a cable clearance below)
    R["hole"] = {}
    passage = cable_hole(r=CABLE_HOLE_D / 2 - 0.01)
    for n, cup in cups.items():
        R["hole"][n] = overlap(passage, cup)
    R["hole"]["body"] = overlap(passage, body)
    check(max(R["hole"].values()) < EPS_V and overlap(passage, cable) > 1.0, f"the cable hole is not free along the cable: {R['hole']}")
    # ways in and out: the plug up into the port (cup off, battery and board in), the cable laid up into the body's notch,
    # each cup off straight down (relative to the cups, head and cable move up)
    R["up_bat"] = clear(up, bat, "USB head on its way up: the battery", BAT_HEAD_MIN - 1e-3)
    R["up_body"] = clear(up, body, "USB head on its way up into the port: the body", HEAD_CLR)
    R["up_door"] = clear(up, door, "USB head on its way up: the door", HEAD_CLR)
    R["up_board"] = min(clear(up, s, f"USB head on its way up: {n}", HEAD_CLR, touch_ok=(n == "pcb"))
                        for n, s in list(bd.items()) + list(rods.items()))
    R["lay_body"] = clear(cable_sweep(cable, from_z=-30.0), body, "USB cable laid up into the body's notch", CABLE_LAY_MIN)
    hb = head.bounding_box()
    head_off = box(hb.min.X, hb.max.X, hb.min.Y, hb.max.Y, hb.min.Z, SEAM + 10)
    for n, cup in cups.items():
        R[f"off_head_cup-{n}"] = clear(head_off, cup, f"cup-{n} off straight down: the USB head", HEAD_CLR)
        R[f"off_cable_cup-{n}"] = clear(cable_sweep(cable, up_to=SEAM + 10), cup, f"cup-{n} off straight down: the USB cable", pas)
    # seated
    check(gap_to(head, bd["pcb"]) < 1e-3 and overlap(head, bd["pcb"]) < EPS_V, "USB head not seated against the PCB's edge")
    R["head_body"] = clear(head, body, "USB head to the body", HEAD_CLR)
    R["cable_body"] = clear(cable, body, "USB cable in the body's notch", pas)
    R["run_body"] = clear(run, body, "USB cable's run inside: the body (bosses, bulkhead)", HEAD_CLR)
    for n, cup in cups.items():
        R[f"head_cup-{n}"] = clear(head, cup, f"USB head to cup-{n}", HEAD_CLR)
        R[f"cable_cup-{n}"] = clear(cable, cup, f"USB cable in cup-{n}'s notch", pas)
        R[f"run_cup-{n}"] = clear(run, cup, f"USB cable's run inside cup-{n}", HEAD_CLR)
    R["head_cast"] = clear(head, cast, "USB head to the cast", HEAD_CLR)
    R["cable_cast"] = clear(cable, cast, "USB cable to the cast", HEAD_CLR)
    R["head_bat"] = clear(head, bat, "USB head to the battery", BAT_HEAD_MIN - 1e-3)
    R["cable_bat"] = clear(cable, bat, "USB cable to the battery", HEAD_CLR)
    R["segs"] = {}
    for n, (cup, segs) in seg_sets.items():
        g = 6.0
        for i, sg in enumerate(segs):
            g = min(g, clear(sg, head, f"{n}: segment {i} to the USB head", HEAD_CLR),
                    clear(sg, cable, f"{n}: segment {i} to the USB cable", HEAD_CLR),
                    clear(sg, head_off, f"{n}: segment {i} to the USB head as the cup comes off", HEAD_CLR))
        R["segs"][n] = g
    return R


def build():
    import time
    import pyvista as pv
    from scipy.spatial import cKDTree
    t0 = time.time()
    OUT.mkdir(exist_ok=True)
    for f_ in OUT.glob("dummy-*.stl"):                    # round 6: no stale dummies (breakout, socket, wires) in the views
        f_.unlink()
    log = lambda m: print(f"[{time.time() - t0:6.1f} s] {m}", flush=True)
    S = Surfaces()
    log(f"surfaces: outer {S.dev_outer:.3f}, inner {S.dev_inner:.3f} from their points; inner flare {FLARE_IN}; keel {KEEL} NC {P['NC']}")
    bosses = boss_spots()
    # round 6: the cast's top (= the trim layer's floor) as high as the USB head allows (round 5: 17.9, under SEG_TOP_MAX)
    top_rock = min(SEG_TOP_MAX, CAST_TOP_MAX + SEG[2])
    lay_rock = [round(top_rock - SEG[2], 4)]
    check(TRIM_LAYERS == 1, "round 6 builds one trim layer")
    pk_steps = packing(lay_rock, bosses)
    if BUILD_STEPS:
        pk_steps, top_steps = best_stack(S.inner_z[0], bosses, top_rock)
    lay_steps = sorted(pk_steps)
    cast_to = lay_rock[0]
    pk_flat, top_flat = best_stack(CUT_FLAT + FLAT_FLOOR_MIN, bosses)
    lay_flat = sorted(pk_flat)
    log(f"layers {[(z, len(v)) for z, v in sorted(pk_steps.items())]}, cast to {cast_to}, flat {[(z, len(v)) for z, v in sorted(pk_flat.items())]}")
    door = door_part()
    body, shell_only = make_body(S)
    log("body")
    cup_rock, env_rock, cav_rock = make_cup(S, "rock", lay_rock, cast_to=cast_to)
    cup_flat, env_flat, cav_flat = make_cup(S, "flat", lay_flat)
    parts = {"body": body, "cup-rock": cup_rock, "cup-flat": cup_flat, "door": door, "arc-gauge": arc_gauge()}
    if BUILD_STEPS:
        cup_steps, env_steps, cav_steps = make_cup(S, "rock", lay_steps)
        parts["cup-rock-steps"] = cup_steps
    R = {}
    cast_all = (S.inner & box(-100, 100, -100, 100, -5, cast_to)) - cup_rock
    sols = sorted(cast_all.solids(), key=vol, reverse=True)
    cast = sols[0]                                         # the pourable cavity; the rest are pockets in the dowel holes
    R["cast_frag"] = [vol(x) for x in sols[1:]]
    check(sum(R["cast_frag"]) < 0.01 * vol(cast), "cast region split into large pieces")
    log("cups")

    # ---- fits, on the solids
    fb = bspline_faces(shell_only)
    ref_o = bspline_faces(S.outer)[0]
    f_out = [f for f in fb if _on_surface(f, ref_o)]
    f_in = [f for f in fb if not _on_surface(f, ref_o)]
    check(len(f_out) == 1 and len(f_in) == 1, f"shell faces: {len(f_out)} outer, {len(f_in)} inner")
    R["wall_min"], R["wall_at"] = dist_shapes(f_out[0], f_in[0])
    check(R["wall_min"] >= WALL - 0.05, f"body wall {R['wall_min']:.3f} < {WALL}")
    bd = board_bodies()
    rods = rod_solids()
    plate = xz_prism(DOOR_W, DOOR_H, DOOR_R, XOFF, DOOR_ZC, -80, Y_DOOR_BACK)
    check(overlap(plate, body) < EPS_V, "door plate sweep hits the body")
    R["door_gap"] = gap_to(xz_prism(DOOR_W, DOOR_H, DOOR_R, XOFF, DOOR_ZC, -80, Y_PANEL + WALL - 0.05), body)
    check(R["door_gap"] >= DOOR_GAP - 0.01, f"door to the opening {R['door_gap']:.3f}")
    R["sweep"] = {}
    for n, s in bd.items():
        R["sweep"][n] = clear(sweep_y(s), body, f"{n} on the way in", PASS_CLR - 0.05)
    door_ribs = door - xz_prism(DOOR_W + 2, DOOR_H + 2, DOOR_R, XOFF, DOOR_ZC, Y_PANEL - 1, Y_DOOR_BACK)
    R["sweep"]["door ribs"] = clear(sweep_y(door_ribs), body, "door ribs on the way in", 0.3)
    R["glass_rib"] = dist_shapes(bd["glass"], door)[0]
    check(R["glass_rib"] >= GLASS_RIB_CLR - 0.01, f"glass to the door {R['glass_rib']:.3f}")
    for n, s in rods.items():
        check(overlap(s, door) < EPS_V, f"{n} in its slot")
    R["tab_pcb"] = min(gap_to(sweep_y(bd["pcb"]), tab_solid(S, sx, zl)) for sx, zl in TABS)
    bat = battery_solid()
    R["bat_sweep"] = {n: clear(sw, body, f"battery on its way up ({n})", BAT_SWEEP_MIN - 0.05) for n, sw in battery_sweeps().items()}
    R["bat_board"] = clear(bat, bd["pcb"], "battery to the board", BAT_GAP - 0.01)
    R["bat_bulk"] = gap_to(bat, body)
    # the LEDs' room behind the logo, and a tool's way to the door's back strip
    led = led_keepout()
    check(overlap(led, body) < EPS_V, "the LEDs' room behind the logo is not free")
    R["led_bat"] = min(gap_to(led, sw) for sw in battery_sweeps().values())
    R["led_board"] = min(gap_to(led, sweep_y(s)) for s in bd.values())          # gap_to stops looking at 6
    check(R["led_bat"] >= LED_MIN and R["led_board"] >= LED_MIN,
          f"LEDs' room: {R['led_bat']:.2f} from the battery's way up, {R['led_board']:.2f} from the board's way in (< {LED_MIN})")
    R["spots"] = {}
    global TRIM_SPOT_Z0                                 # round 6: the lowest bottom (0.5 steps) where both spots clear the body
    for z0 in np.arange(TRIM_SPOT_Z_LO, 27.51, 0.5):
        TRIM_SPOT_Z0 = float(z0)
        if all(overlap(spot_box(x), body) < EPS_V for x in TRIM_SPOTS):
            break
    for x in TRIM_SPOTS:
        sp = spot_box(x)
        R["spots"][x] = clear(sp, body, f"trim spot x {x}", 0.0, touch_ok=True)
        clear(sp, bat, f"trim spot x {x} to the battery", 0.3)
    check(TRIM_SPOTS[0] - TRIM_SPOTS[1] >= SEG[0] + 0.3, "trim spots overlap")
    tool = door_tool_access()
    check(overlap(tool, body) < EPS_V, "no tool access to the door's back strip")
    R["tool"] = min(gap_to(tool, s) for s in (bd["pcb"], bd["glass"], bat, *usb_solids().values()))
    check(R["tool"] >= TOOL_MIN, f"door tool's way: {R['tool']:.2f} from the board / battery / USB head (< {TOOL_MIN})")
    R["slots"] = slot_land_check(door)
    R["rod_slot"] = min(dist_shapes(r_, door)[0] for r_ in rods.values())
    check(R["rod_slot"] > 0.0, f"a rod touches its slot: {R['rod_slot']:.3f}")
    log("fits")
    R["meat_body"] = [dist_shapes(zcyl(s["x"], s["y"], SEAM_R_HOLE if s["kind"] == "mag" else PIN_R_BODY, SEAM,
                                       SEAM + (SEAM_MAG_H + MAG_CLR_H if s["kind"] == "mag" else PIN_DEPTH)), Compound(f_out))[0] for s in bosses]
    R["meat_cup"] = []
    for cup in [p_ for n_, p_ in parts.items() if n_.startswith("cup")]:
        co = [f for f in cup.faces() if f.geom_type != GeomType.PLANE and f.geom_type != GeomType.CYLINDER]
        R["meat_cup"] += [gap_to(zcyl(s["x"], s["y"], SEAM_R_HOLE if s["kind"] == "mag" else PIN_R_CUP,
                                      SEAM - (SEAM_MAG_H + MAG_CLR_H if s["kind"] == "mag" else PIN_DEPTH), SEAM), Compound(co)) for s in bosses]
    check(min(R["meat_body"] + R["meat_cup"]) >= MEAT_MIN - 0.05, f"seam holes: wall to the outside {min(R['meat_body'] + R['meat_cup']):.2f}")
    pocket = logo_pocket(S)
    R["logo_skin"] = dist_shapes(pocket, Compound(f_out))[0]
    check(abs(R["logo_skin"] - LOGO_SKIN) < 0.05, f"logo skin {R['logo_skin']:.3f}")
    pb = pocket.bounding_box()
    R["logo_box"] = (pb.min.X, pb.max.X, pb.min.Z, pb.max.Z)
    area = sum(0.5 * abs(np.dot(q[:, 0], np.roll(q[:, 1], 1)) - np.dot(q[:, 1], np.roll(q[:, 0], 1)))
               for q in map(np.asarray, hw.letters_mm(LOGO_W)))
    R["logo_left"] = vol(logo_letters_prism() & body) / area          # material left inside the letters, mean thickness
    # along the projection the 0.8 skin reads up to 0.8 / cos(40 deg) where the belly turns away; more means a sealed pocket
    check(R["logo_left"] <= LOGO_SKIN * 1.35, f"logo: {R['logo_left']:.2f} of material left in the letters (a sealed pocket?)")
    walls = [("rock", env_rock, cav_rock), ("flat", env_flat, cav_flat)] + ([("steps", env_steps, cav_steps)] if BUILD_STEPS else [])
    for n, env, cav in walls:
        below = cav & box(-100, 100, -100, 100, -10, SEAM - 0.01)
        skin = [f for f in env.faces() if not (f.geom_type == GeomType.PLANE and abs(f.center().Z - SEAM) < 1e-6)]
        R[f"wall_{n}"] = dist_shapes(below, Compound(skin))[0]
        check(R[f"wall_{n}"] >= (WALL - 0.05 if n != "flat" else 1.2), f"cup-{n}: wall {R[f'wall_{n}']:.2f}")
    R["flat_floor"] = min(lay_flat) - CUT_FLAT
    log("meat, skin, walls")

    # ---- export
    files = {}
    for n, p in parts.items():
        p.label = n
        st = write_step(p, OUT / f"{n}.step")
        v_coarse = vol(p, 0.05)
        write_stl(p, OUT / f"{n}.stl")
        files[n] = (st, check_stl(p, OUT / f"{n}.stl", ref=v_coarse))
    dummies = dict(bd)
    dummies.update(rods)
    dummies["battery"] = bat
    dummies.update(usb_solids())
    dummies["cast"] = cast
    dummies["led-room"] = led
    for n, s in dummies.items():
        write_stl(s, OUT / f"dummy-{n}.stl")
    keel_meshes()
    log("exported")

    # ---- ballast measured on the exported cups
    names = ["cup-rock", "cup-flat"] + (["cup-rock-steps"] if BUILD_STEPS else [])
    mesh = {n: pv.read(str(OUT / f"{n}.stl")) for n in names}
    lays = {"cup-rock": (lay_rock, pk_steps), "cup-flat": (lay_flat, pk_flat), "cup-rock-steps": (lay_steps, pk_steps)}
    pm = {}
    for n in names:
        lay, pk = lays[n]
        pm[n] = packing(lay, bosses, mesh[n])
        for z in lay:
            check(len(pm[n][z]) == len(pk[z]), f"{n} layer z {z}: {len(pm[n][z])} segments measured, {len(pk[z])} designed")
    cells = {n: [c for z in sorted(pm[n]) for c in pm[n][z]] for n in pm}
    for n in names:
        for c in cells[n]:
            check(overlap(segment_solids([c])[0], parts[n]) < EPS_V, f"{n}: segment at {c[:2]} hits the cup")
    runs = row_runs(mesh["cup-rock"], cells["cup-rock"])
    log(f"segments: rock {len(cells['cup-rock'])} over the cast, flat {len(cells['cup-flat'])}")

    # ---- mass model (calculated) on the exported meshes, nominal and bad case
    meshes = {n: mesh_props(OUT / f"{n}.stl", RHO_DOOR if n == "door" else RHO_PLA) for n in parts if n != "arc-gauge"}
    pts = {n: np.vstack([meshes["body"]["pts"], meshes[n]["pts"]]) for n in names}
    mm = lambda cup: {n: meshes[n] for n in ("body", cup, "door")}
    cases = {"nominal": dict(m_board=M_BOARD, m_bat=M_BAT, rho=RHO_CAST), "bad": dict(m_board=BAD["M_BOARD"], m_bat=BAD["M_BAT"], rho=BAD["RHO_CAST"])}
    C = {}
    # round 6: the mass model's asserts (assumed masses) are collected, written into the report and build sheet, then raised
    # at the end: the build still fails, but the numbers that fail are on paper
    FAIL = []
    soft = lambda ok, msg: ok or FAIL.append(msg)
    for cn, cs in cases.items():
        cast_p = dict(mesh_props(OUT / "dummy-cast.stl", cs["rho"]), name="cast")
        nb = mass_parts(mm("cup-rock"), [], m_board=cs["m_board"], m_bat=cs["m_bat"])
        M_nb, G_nb, _ = combine(nb)
        M_f, G_f, _ = combine(nb + [cast_p])
        try:
            tp = trim_plan(cells["cup-rock"], runs, M_f * G_f[0], M_f)
        except AssertionError as e:
            FAIL.append(f"{cn}: {e}")
            tp = trim_plan(cells["cup-rock"], runs, M_f * G_f[0], M_f, best_effort=True)
        kept, left, gx, auth, t = tp["kept"], tp["left"], tp["gx"], tp["auth"], tp["t"]
        x_need = -M_nb * G_nb[0] / (cast_p["m"] + SEG_G * len(cells["cup-rock"]))
        st = stability(pts["cup-rock"], mass_parts(mm("cup-rock"), kept, extra=[cast_p] + [spot_part(x) for x in tp["spots"]],
                                                   m_board=cs["m_board"], m_bat=cs["m_bat"]))
        margin, T, kst = rocking(st)
        rest_p, fwd, back = pitch_limits(pts["cup-rock"], st["G"])
        rest, crest = roll_full(pts["cup-rock"], st["G"])
        C[cn] = dict(cast=cast_p, kept=kept, left=left, spots=tp["spots"], gx=gx, auth=auth, t=t, x_need=x_need, st=st, margin=margin, T=T, kst=kst,
                     fwd=fwd, back=back, rest_p=rest_p, rest=rest, crest=crest, M_nb=M_nb, G_nb=G_nb)
        # the loft closes the pole in a cone 0.002 high (first section +-0.42): it reads as a +-0.25 deg pivot round upright,
        # far below what a print holds; any other rest position (beyond 1 deg) fails
        soft(len(rest) >= 1 and all(abs(q) <= 1.0 for q in rest), f"{cn}: sideways rest positions {rest} (upright only, expected)")
    n_, b_ = C["nominal"], C["bad"]
    soft(n_["margin"] >= MARGIN_MIN, f"nominal: centre of mass {n_['margin']:.2f} under the rocking centre (needs {MARGIN_MIN})")
    soft(b_["margin"] >= MARGIN_MIN, f"bad case: centre of mass {b_['margin']:.2f} under the rocking centre (needs {MARGIN_MIN})")
    soft(min(n_["fwd"], n_["back"]) >= FWD_MIN_NOMINAL, f"nominal fore-aft {n_['fwd']:.2f} / {n_['back']:.2f} < {FWD_MIN_NOMINAL}")
    soft(min(b_["fwd"], b_["back"]) >= FWD_MIN_BAD, f"bad case fore-aft {b_['fwd']:.2f} / {b_['back']:.2f} < {FWD_MIN_BAD}")
    soft(abs(n_["gx"]) < 0.01, f"trim plan misses plumb: {n_['gx']:+.3f}")
    arc = arc_profile(OUT / "cup-rock.stl", z0=0.005)
    rl, rr = np.hypot(arc[:, 1], arc[:, 0] - RR), np.hypot(arc[:, 2], arc[:, 0] - RR)
    R["arc"] = (float(np.max(np.abs(rl - rr))), float(np.max(np.abs(np.r_[rl, rr] - RR))))
    check(R["arc"][0] <= 0.03 and R["arc"][1] <= 0.03, f"rocking arc asymmetry {R['arc'][0]:.3f}, radius error {R['arc'][1]:.3f}")
    zs_arc = np.r_[np.arange(0.005, 0.25, 0.01), np.arange(0.25, SEAM - 0.25, 0.25)]
    check(len(arc) == len(zs_arc), f"rocking arc: the y 0 section has {len(arc)} of {len(zs_arc)} levels (a gap near the pole?)")
    low = meshes["cup-rock"]["pts"]
    low = low[low[:, 2] < 0.001]
    check(len(low) > 0, "no surface below z 0.001: the pole is missing")
    R["pole"] = (float(np.ptp(low[:, 0])), float(np.ptp(low[:, 1])))
    check(R["pole"][0] <= 2 * math.sqrt(2 * RR * 0.001) + 0.05, f"flat at the pole: {R['pole'][0]:.3f} wide below z 0.001")
    R["pole_sec"] = pole_sections(mesh["cup-rock"])
    st_flat = {cn: stability(pts["cup-flat"], mass_parts(mm("cup-flat"), cells["cup-flat"], m_board=cs["m_board"], m_bat=cs["m_bat"]))
               for cn, cs in cases.items()}
    for sf in st_flat.values():
        sf["ranges"] = [crest_range(pts["cup-flat"], sf["G"], ax, sg, lim)
                        for (ax, sg), lim in zip((("roll", 1), ("roll", -1), ("pitch", -1), ("pitch", 1)), sf["lim"])]
    for cn, sf in st_flat.items():
        soft(min(sf["lim"]) >= 25, f"stable cup, {cn}: tips at {min(sf['lim']):.0f} deg")
    zb0 = DOOR_ZC - BAT_L / 2
    alt = (XOFF - BAT_HT / 2, Y_BOARD1 + BAT_GAP, zb0, XOFF + BAT_HT / 2, Y_BOARD1 + BAT_GAP + BAT_T, zb0 + BAT_L)
    st_alt = stability(pts["cup-rock"], mass_parts(mm("cup-rock"), n_["kept"], battery=alt, extra=[n_["cast"]] + [spot_part(x) for x in n_["spots"]]))
    steps = None
    if BUILD_STEPS:
        st_s = stability(pts["cup-rock-steps"], mass_parts(mm("cup-rock-steps"), cells["cup-rock-steps"]))
        steps = (st_s, rocking(st_s))
    # final trim layouts (left out, slid, bulkhead spots) against everything near them; the logo's floors (after the export)
    for cn, c in C.items():
        boxes = segment_solids(c["kept"]) + [spot_box(x) for x in c["spots"]]
        for i, b in enumerate(boxes):
            for n, o in (("body", body), ("cup-rock", cup_rock), ("battery", bat), *usb_solids().items()):
                check(overlap(b, o) < EPS_V, f"{cn} trim layout: piece {i} hits the {n}")
            for j in range(i):
                check(overlap(b, boxes[j]) < EPS_V, f"{cn} trim layout: pieces {i} and {j} overlap")
    seg_sets = {f"cup-rock {cn}": (cup_rock, segment_solids(c["kept"]) + [spot_box(x) for x in c["spots"]]) for cn, c in C.items()}
    seg_sets["cup-flat"] = (cup_flat, segment_solids(cells["cup-flat"]))
    if os.environ.get("ROLY_DUMP"):                  # the solids for the fault-injection harness (never fatal)
        import pickle
        import build123d as _b3d

        def bare(o):                                 # base shapes without their (unpicklable) OCC history
            if isinstance(o, _b3d.Shape):
                return _b3d.Solid(o.wrapped) if isinstance(o, _b3d.Solid) else _b3d.Compound(o.wrapped)
            if isinstance(o, dict):
                return {k: bare(v) for k, v in o.items()}
            if isinstance(o, (list, tuple)):
                return type(o)(bare(v) for v in o)
            return o
        try:
            pathlib.Path(os.environ["ROLY_DUMP"]).write_bytes(pickle.dumps(bare(dict(body=body, cups=dict(rock=cup_rock, flat=cup_flat),
                door=door, bat=bat, bd=bd, rods=rods, cast=cast, seg_sets=seg_sets))))
        except Exception as e:
            log(f"ROLY_DUMP failed: {e!r}")
    R["usb"] = usb_checks(body, dict(rock=cup_rock, flat=cup_flat), door, bat, bd, rods, cast, seg_sets)
    R["skin"] = logo_floor_check(body, f_out[0])
    R["logo_outline"] = logo_outline_check(S, body)
    R["logo_roof"] = logo_roof_check(S, OUT / "body.stl")
    R["logo_out"] = logo_outside(S)
    check(R["logo_out"]["clr"] >= LOGO_FLARE_CLR, f"logo {R['logo_out']['clr']:.2f} past the alcove's flare (< {LOGO_FLARE_CLR})")
    R["logo_out_old"] = logo_outside(S, LOGO_X_OLD)
    for tag, x in (("old", LOGO_X_OLD), ("new", LOGO_X)):          # the views' painted footprints (after the export)
        write_stl(logo_decal(S, x), OUT / f"dummy-logo-{tag}.stl")
    log("mass model")

    # ---- print orientations: overhangs steeper than 45 deg (calculated on the exported meshes)
    tree = cKDTree(G_OUT.reshape(-1, 3))
    ov = {}
    t_, o_, cc, aa = overhangs(OUT / "body.stl", (0, 0, -1), lambda c: c[:, 2] < SEAM + 0.05, tree)
    ov["body"] = dict(total=t_, outer=o_, crown=float(aa[cc[:, 2] > 100].sum()),
                      bridge=float(aa[(cc[:, 2] > DOOR_ZC + OPEN_H / 2 - 3) & (cc[:, 2] < DOOR_ZC + OPEN_H / 2 + 6) & (np.abs(cc[:, 0] - XOFF) < OPEN_W / 2 + 2) & (cc[:, 1] < -5)].sum()))
    ymax = float(mesh["cup-rock"].bounds[3])
    t_, o_, cc, aa = overhangs(OUT / "cup-rock.stl", (0, 1, 0), lambda c: c[:, 1] > ymax - 0.05, tree)
    band = (np.abs(cc[:, 1]) < 12) & (cc[:, 2] < 12)
    ov["cup_back"] = dict(total=t_, outer=o_, band=float(aa[band].sum()))
    t_, o_, cc, aa = overhangs(OUT / "cup-rock.stl", (0, 0, 1), lambda c: c[:, 2] > SEAM - 0.05, tree)
    ov["cup_rim"] = dict(total=t_, outer=o_)
    R["pole_flat_rim_down"] = 2 * math.sqrt(2 * RR * 0.12)
    log("overhangs")

    # ---- the cast by weight, and the wiring
    Vc = C["nominal"]["cast"]["V"] / 1000
    phi = lambda rho: (rho - RHO_EPOXY) / (RHO_BALL - RHO_EPOXY)
    balls = dict(V=Vc, nom=Vc * phi(RHO_CAST) * RHO_BALL, low=Vc * phi(BAD["RHO_CAST"]) * RHO_BALL,
                 epoxy=Vc * (1 - phi(RHO_CAST)), phi=(phi(RHO_CAST), phi(BAD["RHO_CAST"])),
                 depth=cast_to - S.inner_z[0], half=(S.inner_z[0] + cast_to) / 2)
    balls["V1"] = vol(cast & box(-100, 100, -100, 100, -5, balls["half"])) / 1000
    balls["nom1"] = balls["V1"] * phi(RHO_CAST) * RHO_BALL
    # round 6: three batches of 5-minute epoxy, each to a third of the cast's volume (levels by bisection on the solid)
    lv = []
    for k in (1, 2):
        lo_, hi_ = S.inner_z[0], cast_to
        for _ in range(14):
            mid = (lo_ + hi_) / 2
            lo_, hi_ = (mid, hi_) if vol(cast & box(-100, 100, -100, 100, -5, mid)) / 1000 < k * Vc / 3 else (lo_, mid)
        lv.append((lo_ + hi_) / 2)
    balls["levels"] = lv + [cast_to]
    balls["batch_balls"] = Vc / 3 * phi(RHO_CAST) * RHO_BALL
    balls["batch_epoxy"] = Vc / 3 * (1 - phi(RHO_CAST))
    i2c = np.array([XOFF + hw.PCB_W / 2 + 2, Y_BOARD1 - 2, PCB_Z0 + hw.PLUG_Z["i2c"]])
    route = dict(led=float(np.linalg.norm(i2c - np.array([LOGO_X - 4, -12.0, i2c[2]])) + abs(i2c[2] - LOGO_ZC)))
    R["service"] = 40.0                                    # the door comes this far out to reach the plugs

    info = dict(R=R, files=files, meshes={n: dict(m=v["m"], c=list(v["c"]), V=v["V"]) for n, v in meshes.items()},
                cast_to=cast_to, cells=cells, C=C, st_flat=st_flat, st_alt=st_alt, rk_alt=rocking(st_alt), steps=steps,
                lay_rock=lay_rock, lay_steps=lay_steps, lay_flat=lay_flat, pk_steps=pk_steps, pk_flat=pk_flat, bosses=bosses,
                S=S, parts=parts, ov=ov, balls=balls, route=route)
    for n, cs in (("segments-rock", C["nominal"]["kept"]), ("segments-rock-left-out", C["nominal"]["left"]),
                  ("segments-flat", cells["cup-flat"])):
        if cs:
            write_stl(Compound(segment_solids(cs)), OUT / f"dummy-{n}.stl")
    write_stl(Compound([spot_box(x) for x in TRIM_SPOTS]), OUT / "dummy-trim-spots.stl")
    info["FAIL"] = FAIL
    report(info)
    build_sheet(info)
    focus(info)
    check(not FAIL, "mass model (assumed masses): " + "; ".join(FAIL))
    log("done")
    return info


def report(I):
    R, C = I["R"], I["C"]
    n_, b_ = C["nominal"], C["bad"]
    m = I["meshes"]
    bb = lambda n: I["parts"][n].bounding_box()
    b_all = [bb("body"), bb("cup-rock")]
    W = max(b.max.X for b in b_all) - min(b.min.X for b in b_all)
    D = max(b.max.Y for b in b_all) - min(b.min.Y for b in b_all)
    need_w, need_h = opening_needed()
    lean = lambda gx, mg: math.degrees(math.atan(gx / mg))
    nm = sum(1 for s in I["bosses"] if s["kind"] == "mag")
    cr, cf = I["cells"]["cup-rock"], I["cells"]["cup-flat"]
    ov, bl = I["ov"], I["balls"]
    L = []
    a = L.append
    a(f"DESK HOUSING track B: roly-poly, FDM prototype, round 6  (outline: the study's XOFF {XOFF} Z2L {P['Z2L']:.0f} A2L {P['A2L']} "
      f"Z2R {P['Z2R']:.0f} A2R {P['A2R']:.0f}; keel '{KEEL}' NC {P['NC']}; wall {WALL}; slot {SLOT_TYPE})")
    a("[m] measured on the exported files / solids; [d] designed; [calc] calculated from them with ASSUMED masses: nominal board "
      f"{M_BOARD:.0f} g, battery {M_BAT:.0f} g, misc {M_MISC:.0f} g, cast {RHO_CAST} g/cm3; bad case board {BAD['M_BOARD']:.0f}, battery "
      f"{BAD['M_BAT']:.0f}, cast {BAD['RHO_CAST']}")
    a("")
    U = R["usb"]
    if I["FAIL"]:
        a("FAILED (mass model, assumed masses; the build raises after writing this report):")
        for f_ in I["FAIL"]:
            a(f"  {f_}")
        a("")
    a("ROUND 6 (first print)")
    a(f"  usb        the breakout, its ledges / wall pocket / back hole / bulkhead notch and the J5 pigtail are gone; a right-angle "
      f"USB-C extension plugs straight into the board's own port from below (head {HEAD_W:g} x {HEAD_L:g} x {HEAD_COLLAR + HEAD_T:g} ASSUMED, "
      f"z {HEAD_Z0:.1f}..{HEAD_Z1:.1f}); its D{CABLE_D:g} cable leaves straight back at z {CABLE_Z:.1f}, x {HEAD_X:+g} through a round D{CABLE_HOLE_D:g} "
      f"hole split by the seam (body notch open downward, a notch open upward in each cup): each cup comes off straight down "
      f"with the plug in")
    a(f"  battery    raised {BAT_Z0 - 23.0:g} to z {BAT_Z0:g} ({BAT_HEAD_MIN:g} over the head); bulkhead to z {BULK_TOP:g}, notched {2 * HEAD_NOTCH_X:g} wide to "
      f"z {HEAD_NOTCH_TOP:g} for the head; its way up from below now has a {abs(BAT_PATH['X2'] - BAT_PATH['X1']):.2f} mm sideways step")
    a(f"  cast       top lowered 17.9 -> {I['cast_to']:g} ({HEAD_CLR:g} under the head; the trim terrace with it); segments under the head "
      f"and the cable dropped (rock {len(I['cells']['cup-rock'])} vs 6, flat {len(I['cells']['cup-flat'])} vs 12)")
    a(f"  trim spot  bottom 27.5 -> {TRIM_SPOT_Z0:g} (lowest that clears the body, 0.5 steps)")
    a(f"  slots      {SLOT_W:g} wide (was 8.6) with a {SLOT_LAND:g} straight land at the door's inner face, then 45 deg out to the face "
      "(smooth shells' round 3)")
    a(f"  logo       skin 0.8 -> {LOGO_SKIN:g} (per-letter pockets with 45 deg roofs kept)")
    a(f"  masses     bad case board 40 -> {BAD['M_BOARD']:g} g; door tool path moved right of the USB head")
    a("ROUND 5: the letter pockets get 45 deg roofs (a slicer filled them with support); lit outline, floors and skin unchanged")
    a(f"ROUND 4: the logo moved from x {LOGO_X_OLD:g} to x {LOGO_X:g} (off the alcove's flare onto the plain belly; same 14 mm, z "
      f"{LOGO_ZC:g}, glow-through); everything else as round 3")
    a("ROUND 3: checks and build-sheet text only, no geometry change (pole continuity, logo skin and openness over both letter "
      "floors, LED room / door tool minimums, final trim layouts, fore-aft from upright and from rest, tip ranges)")
    a("")
    a("ROUND 2 CHANGES")
    a(f"  keel       side view's lower corner squared: corner exponent {KEELS['study']} -> {P['NC']} (same corner height {P['ZK']:.0f}, "
      "same depth, front view, R44 arc and seam); comparison: keel-compare.png")
    a("  pole       the outer loft closes at the bottom pole in a point: the R44 arc runs through it (no flat)")
    a("  cup-rock   printed standing on its back: every layer draws the R44 arc; arc-gauge.stl to check (and true) it")
    a("  ballast    the cast is 304 balls 2-6 mm locked in epoxy, filled by weight; trim plan: segments slide along their rows")
    a("  breakout   no cradle: it comes up through a bulkhead notch in front of its seat and slides back (swept, asserted)")
    a("  magnets    pockets magnet + 0.1, set flush against a flat plate in glue; joint proof test in the build sheet")
    a("  checks     sideways over the full revolution; fore-aft limit to 0.02 deg; bad case asserted; only the pourable cast counted")
    a("  dropped    cup-rock-steps (BUILD_STEPS = False); no hole for the power slide")
    a("")
    a("SIZE AND SURFACE")
    a(f"  outer      [m] {W:.1f} wide x {D:.1f} deep x {bb('body').max.Z:.1f} tall on the rocking cup; {bb('body').max.Z - CUT_FLAT:.1f} on the flat cup")
    a(f"  surface    [m] outer loft within {I['S'].dev_outer:.3f} of the study's function (with the {KEEL} keel); inner lofts within {I['S'].dev_inner:.3f} of their points")
    a(f"  pole       [m] cup-rock.stl below z 0.001: {R['pole'][0]:.2f} wide across, {R['pole'][1]:.2f} along (the R44 arc alone: "
      f"{2 * math.sqrt(2 * RR * 0.001):.2f}); arc y 0, z 0.005..{SEAM - 0.25} (every level present): off R{RR:.0f} by {R['arc'][1]:.3f}, left-right "
      f"{R['arc'][0]:.3f} (radial); sections x / y 0.01 run as one curve through the bottom (lowest z "
      f"{R['pole_sec']['x'][0]:.4f} / {R['pole_sec']['y'][0]:.4f}, largest mesh step there {max(v[1] for v in R['pole_sec'].values()):.2f})")
    a(f"  wall       [m] body {R['wall_min']:.2f} at least; cup-rock {R['wall_rock']:.2f}, cup-flat {R['wall_flat']:.2f} (foot); [d] thicker at the "
      f"alcove's shoulder (inner flare {FLARE_IN})")
    a(f"  seam       [d] z {SEAM}: body above, cups below, all cut from the one outer loft")
    a("")
    a("PARTS  [m] volume, mass (solid PLA 1.24), centroid")
    for n in [k for k in m]:
        a(f"  {n:<15}{m[n]['V'] / 1000:6.1f} cm3 {m[n]['m']:6.1f} g   ({m[n]['c'][0]:+.2f}, {m[n]['c'][1]:+.2f}, {m[n]['c'][2]:.2f})")
    a(f"  arc-gauge      concave R{RR:.0f} cradle, 60 x 20")
    a("")
    a("DOOR AND BOARD")
    a(f"  door       [d] {DOOR_W} x {DOOR_H} R{DOOR_R}, {DOOR_T:.0f} thick ({SLOT_TYPE}), x {XOFF}, z {DOOR_ZC - DOOR_H / 2:.2f}..{DOOR_ZC + DOOR_H / 2:.2f}; "
      f"face y {Y_PANEL:.2f}, set back {Y_PANEL - float(y_front(XOFF, DOOR_ZC)):.2f} at its centre")
    a(f"  opening    [d] {OPEN_W} x {OPEN_H} R{OPEN_R}; the board needs {need_w:.2f} x {need_h:.2f} (J5/I2C plugs {hw.PLUG_PROUD} assumed)")
    a(f"  way in     [m] door edge gap {R['door_gap']:.2f}; " + ", ".join(f"{k} {v:.2f}" for k, v in R["sweep"].items()) + f"; PCB to the tabs {R['tab_pcb']:.2f}")
    a(f"  slots      [d] {SLOT_W} x {SLOT_L:.2f} for {ROD_L} rods ({hw.ROD_W:g} wide): 0.1 play per end, as track A (intended: the visible "
      f"opening is the slot; the rod sits 0.1 short of each end); x {TUBE_X[0]:.2f} / {TUBE_X[1]:.2f}, z {AA_ZC - SLOT_L / 2:.2f}..{AA_ZC + SLOT_L / 2:.2f}")
    SL = R["slots"]
    a(f"  land       [m] on {SL[0]['n']} sections along each slot: at the door's inner (back) face {min(q['w'] for q in SL):.3f}..{max(q['w_max'] for q in SL):.3f} "
      f"wide, straight for {min(q['depth'] for q in SL):.2f}..{max(q['depth_max'] for q in SL):.2f} from the inner face ({LAND_DY} steps), both sides, "
      f"both slots; then 45 deg out to an opening of {min(q['face'] for q in SL):.2f} on the face; rods to the door {R['rod_slot']:.3f} at the closest")
    a(f"  stack      [d] board stack {hw.BOARD_T} (housing.py's measured value; the drawing says 9.3): battery to the board "
      f"{R['bat_board']:.2f} [m], {R['bat_board'] - 0.3:.2f} with the drawing's 9.3")
    a("  power      no hole for the slide switch (the user drills one if wanted); RST / BOOT behind the door")
    a(f"  held by    [d] {len(TABS)} x D{DOOR_MAG_D}x{DOOR_MAG_H} pairs, door <-> tabs; opened with a suction cup on the face, or a blunt tool "
      f"from below on the door's back strip under the PCB ([m] tool path free of the body; {R['tool']:.2f} from the board / battery, asserted >= {TOOL_MIN})")
    a("")
    a("INSIDE")
    a(f"  battery    [d] {BAT_L:.0f} x {BAT_HT:.0f} x {BAT_T:.0f} on its long edge, x {BAT_X:+.2f}, z {BAT_Z0}..{BAT_Z0 + BAT_HT:.0f}, taped to the "
      f"bulkhead; [m] to the body {R['bat_bulk']:.2f}; its way up from below (cup off, before the board): straight up at x "
      f"{BAT_PATH['X1']:+.2f} until its bottom is at z {BAT_PATH['Z_MID']:.2f}, {BAT_PATH['X2'] - BAT_PATH['X1']:+.2f} sideways, up to its seat at x "
      f"{BAT_PATH['X2']:+.2f}: " + ", ".join(f"{k} {v:.2f}" for k, v in R["bat_sweep"].items()) + f" [m] (a straight way would leave "
      f"{BAT_PATH['straight']:+.2f} per side [d])")
    a(f"  usb head   [d] port at x {HEAD_X:+g}, y {PORT_Y:.2f} ({hw.PORT_Y_FROM_BOARD_BACK:g} in front of the board's back, ASSUMED); head x "
      f"{HEAD_X - HEAD_W / 2:+.1f}..{HEAD_X + HEAD_W / 2:+.1f}, y {HEAD_Y0:.2f}..{HEAD_Y1:.2f}, z {HEAD_Z0:.1f}..{HEAD_Z1:.1f}; [m] seated: body {U['head_body']:.2f}, "
      f"battery {U['head_bat']:.2f}, cast {U['head_cast']:.2f}, " + ", ".join(f"cup-{n} {U[f'head_cup-{n}']:.2f}" for n in ("rock", "flat")) +
      f"; pushed up into the port from below (cup off, battery and board in): body {U['up_body']:.2f}, battery {U['up_bat']:.2f}, door "
      f"{U['up_door']:.2f}, board (except the PCB edge it seats on) / rods {U['up_board']:.2f}; cups off straight down: " +
      ", ".join(f"cup-{n} {U[f'off_head_cup-{n}']:.2f}" for n in ("rock", "flat")) + f" (asserted >= {HEAD_CLR}, battery >= {BAT_HEAD_MIN})")
    a(f"  usb cable  [d] D{CABLE_D:g} straight back from y {HEAD_Y1:.2f} at z {CABLE_Z:.1f}; through the D{CABLE_HOLE_D:g} hole (body notch z {SEAM:g}.."
      f"{CABLE_Z + CABLE_HOLE_D / 2:.1f}, cup notches z {CABLE_Z - CABLE_HOLE_D / 2:.1f}..{SEAM:g}); [m] in the hole: body {U['cable_body']:.2f}, "
      + ", ".join(f"cup-{n} {U[f'cable_cup-{n}']:.2f}" for n in ("rock", "flat")) + f"; its run inside (to 1 mm before the wall): body "
      f"{U['run_body']:.2f}, " + ", ".join(f"cup-{n} {U[f'run_cup-{n}']:.2f}" for n in ("rock", "flat")) + f", cast {U['cable_cast']:.2f}, "
      f"battery {U['cable_bat']:.2f}; laid up into the body's notch {U['lay_body']:.2f}; cups off straight down: " +
      ", ".join(f"cup-{n} {U[f'off_cable_cup-{n}']:.2f}" for n in ("rock", "flat")) + "; the passage (D" + f"{CABLE_HOLE_D - 0.02:g}) overlaps "
      "nothing along the cable: " + ", ".join(f"{k} {v:.4f} mm3" for k, v in U["hole"].items()))
    a(f"  segments   [m] to the USB head / cable (seated and as the cup comes off): " + ", ".join(f"{k} {v:.2f}" for k, v in U["segs"].items()) +
      f" (asserted >= {HEAD_CLR}; the trim layouts of both cases, the bulkhead spots, the flat cup's segments)")
    a(f"  trim spots [m] x " + ", ".join(f"{x:+.1f}" for x in TRIM_SPOTS) + f", z {TRIM_SPOT_Z0}..{TRIM_SPOT_Z0 + SEG[1]:.1f} on the bulkhead's back: no "
      "overlap with the body (they sit on the bulkhead: no overlap, not a clearance), >= 0.3 from the battery; "
      "final trim layouts (left out, slid, spots) checked against body, cup, battery, USB head and cable for both cases")
    a(f"  logo       [d] {LOGO_W:.0f} mm letters at x {LOGO_X}, z {LOGO_ZC}; [m] pockets with 45 deg roofs: lit outline within "
      f"{R['logo_outline']['off']} at the skin ({R['logo_outline']['n_in']} points inside / {R['logo_outline']['n_out']} outside the edges, "
      f"{R['logo_outline']['tops']} on top edges); faces steeper than 46 deg only within {R['logo_roof']['far']:.3f} of the skin "
      f"({R['logo_roof']['n_steep']} facets), {R['logo_roof']['n_roof']} roof facets at 45 deg; skin {R['skin']['lo']:.3f}..{R['skin']['hi']:.3f} normal "
      f"to the surface over {R['skin']['n']} points on both letter floors; open to the cavity along the projection: "
      + ", ".join(f"{'EH'[k] if k < 2 else k} {v * 100:.0f} %" for k, v in sorted(R['skin']['open'].items())) +
      f" of the floor; outside, {R['logo_out']['clr']:.2f} past the end of the alcove's flare (x {R['logo_out']['x'][0]:.1f}.."
      f"{R['logo_out']['x'][1]:.1f}; at x {LOGO_X_OLD:g} it was {R['logo_out_old']['clr']:+.2f}, on the flare); the surface turns "
      + " / ".join(f"{t:.0f}" for t in R['logo_out']['turn']) + f" deg from the front at its left end / centre / right end; "
      f"LEDs' room (4.5..8.5 behind the letters' centre" + (f", {LED_SHIFT:g} right" if LED_SHIFT else "") + ") "
      f"free: {'>= 6' if R['led_bat'] >= 5.99 else format(R['led_bat'], '.2f')} from the battery's way up, "
      f"{'>= 6' if R['led_board'] >= 5.99 else format(R['led_board'], '.2f')} from the board's way in (asserted >= {LED_MIN})")
    a(f"  wiring     [d] no J5 wiring (USB through the board's own port); I2C 3V3 -> LEDs "
      f"{I['route']['led']:.0f} + {R['service']:.0f}; loops lie on the battery's top (z {BAT_Z0 + BAT_HT:.0f}..{BULK_TOP:.0f} behind the board)")
    a("")
    a("SEAM JOINT")
    a(f"  [d] {nm} x D{SEAM_MAG_D}x{SEAM_MAG_H} pairs + 2 x D{SEAM_PIN_D}x{SEAM_PIN_L} dowels; pockets {SEAM_MAG_H + MAG_CLR_H} deep, magnets set flush against a "
      f"flat plate in glue; [m] wall to the outside: body {min(R['meat_body']):.2f}, cups {min(R['meat_cup']):.2f}")
    hang = m["cup-rock"]["m"] + n_["cast"]["m"] + SEG_G * len(n_["kept"])
    a(f"  [calc] lifted by the body the joint carries {hang:.0f} g; proof test (build sheet) before the ballast goes in")
    a("")
    a("BALLAST")
    a(f"  cast       [m] pourable cavity up to z {I['cast_to']} (the step): {bl['V']:.2f} cm3, {bl['depth']:.1f} deep; [calc] {n_['cast']['m']:.0f} g "
      f"at {RHO_CAST} ({b_['cast']['m']:.0f} g at {BAD['RHO_CAST']}); centroid ({n_['cast']['c'][0]:+.2f}, {n_['cast']['c'][1]:+.2f}, {n_['cast']['c'][2]:.2f}); "
      f"left out: {len(R['cast_frag'])} pockets in the dowel holes ({sum(R['cast_frag']):.1f} mm3)")
    a(f"  balls      [calc] 304 balls to fill by weight: {bl['nom']:.0f} g for {RHO_CAST} (packing {bl['phi'][0]:.2f}), {bl['low']:.0f} g gives "
      f"{BAD['RHO_CAST']} (packing {bl['phi'][1]:.2f}); epoxy ~{bl['epoxy']:.0f} ml; three batches of 5-minute epoxy, each a third of the volume: to z " + " / ".join(f"{z:.1f}" for z in bl["levels"]))
    a(f"  trim layer [m] {len(cr)} segments fit on the cast (z {I['cast_to']}..{I['cast_to'] + SEG[2]:.1f}); " + ", ".join(
      f"row y {r_['y']:+.1f}: {len(r_['idx'])}" for r_ in row_runs_cached(I)))
    a(f"  cup-flat   [m] " + ", ".join(f"z {z:.2f}: {len(I['pk_flat'][z])}" for z in I["lay_flat"]) + f" = {len(cf)} segments ({SEG_G * len(cf):.0f} g); floor {R['flat_floor']:.2f}")
    a("")
    for cn, c in (("nominal", n_), ("bad case", b_)):
        st = c["st"]
        a(f"ROCKING, {cn.upper()} [calc]")
        a(f"  plumb      ballast (cast + all {len(cr)} segments) centre needed at x {c['x_need']:+.2f} (non-ballast parts {c['M_nb']:.0f} g at "
          f"x {c['G_nb'][0]:+.2f}); plan: {len(c['spots'])} segment(s) on the bulkhead's back at x " + (", ".join(f"{q:+.1f}" for q in c['spots']) or "-") +
          f", leave out {len(c['left'])} of the trim layer" + (" (" + ", ".join(f"x {q[0]:+.1f} y {q[1]:+.1f}" for q in c['left']) + ")" if c['left'] else "") +
          f", slide the rest {c['t'] * 100:.0f} % of their rows' slack to the right -> x {c['gx']:+.3f}; trim layer's reach with all in: "
          f"{c['auth'][0]:+.2f}..{c['auth'][1]:+.2f} mm")
        a(f"  result     {st['M']:.0f} g; centre of mass z {st['G'][2]:.2f} (y {st['G'][1]:+.2f}): {c['margin']:.2f} under the rocking centre; period "
          f"{c['T']:.2f} s (ideal rocker); righting {c['kst']:.2f} mN m per deg")
        a(f"  sideways   rests only upright over the whole revolution (" + ", ".join(f"{q:+.2f}" for q in c["rest"]) + " deg: the pole's 0.002 "
          f"closing cone); crests at " + ", ".join(f"{q:+.1f}" for q in c["crest"] if abs(q) > 1) + " deg")
        a(f"  fore-aft   rests at {c['rest_p']:+.2f} deg (+ = back); crests found from the rest angle, sampled every 0.02 deg: "
          f"forward {c['fwd']:.2f} from upright ({c['fwd'] + c['rest_p']:.2f} from rest), backward {c['back']:.2f} from upright "
          f"({c['back'] - c['rest_p']:.2f} from rest); needs {FWD_MIN_NOMINAL if cn == 'nominal' else FWD_MIN_BAD:.0f} from upright")
    sa, ra = I["st_alt"], I["rk_alt"]
    a(f"  what-if    [calc] battery upright on the door: {ra[0]:.2f} under, fore-aft {sa['lim'][2]:.0f} / {sa['lim'][3]:.0f} deg")
    a("")
    for cn, sf in I["st_flat"].items():
        rg = lambda q: f"{q[0]:.0f}-{q[1]:.0f}" if round(q[1]) - round(q[0]) >= 1 else f"{(q[0] + q[1]) / 2:.0f}"
        a(f"STABLE CUP, {cn} [calc] {sf['M']:.0f} g with {len(cf)} segments; centre of mass {sf['G'][2] - CUT_FLAT:.1f} over the desk; tips beyond "
          f"{rg(sf['ranges'][0])} deg right, {rg(sf['ranges'][1])} left, {rg(sf['ranges'][2])} forward, {rg(sf['ranges'][3])} backward "
          f"(a range where the crest is broad: within 0.005 of its top)")
    a("")
    a("PRINT ORIENTATION, overhangs steeper than 45 deg [m on the meshes]")
    a(f"  body rim-down:    {ov['body']['total']:.0f} mm2 in all ({ov['body']['outer']:.0f} on the outside); inside the crown above z 100: "
      f"{ov['body']['crown']:.0f}; the opening's top edge: {ov['body']['bridge']:.0f}")
    a(f"  cup-rock on back: {ov['cup_back']['total']:.0f} mm2 ({ov['cup_back']['outer']:.0f} outside, at the back's lower corner; the rolling band "
      f"|y| < 12, z < 12: {ov['cup_back']['band']:.0f})")
    a(f"  cup-rock rim-down (round 1, not used): {ov['cup_rim']['total']:.0f} mm2, and a {R['pole_flat_rim_down']:.1f} mm flat at the pole from "
      "one 0.12 layer")
    a("")
    a("FILES  [m] each STEP re-imported (solids, valid, closed, triangulated volume), each STL re-read (closed, one body, volume vs 0.05 mesh)")
    for n, (s_, t_) in I["files"].items():
        a(f"  {n:<15}STEP {s_['solids']} solid, {s_['faces']} faces, {s_['err'] * 100:+.4f} %, {s_['kb']:.0f} kB; STL {t_['tris']} triangles, "
          f"{t_['err'] * 100:+.3f} %, {t_['kb']:.0f} kB")
    a("")
    a("NOT VERIFIED HERE: the real masses and the cast's packing; the USB extension's head (12 x 21 x 8.5 envelope, plug axis 5 from its "
      "closed end, cable at its mid-thickness, D5 cable: ASSUMED from housing.py's MOGOOD box), the port's position (2.0 in front of the "
      "board's back, x centre, ASSUMED) and the cable's stiffness in the hole; the plugs' protrusion (4 assumed); magnet pull in the print; "
      "slicer toolpaths (supports, 1.0 logo skin, the opening's bridge); 5-minute epoxy heat per batch; cable lean; rocking feel; logo glow")
    text = "\n".join(L)
    (OUT / "report.txt").write_text(text + "\n")
    print(text, flush=True)


_RUNS = {}


def row_runs_cached(I):
    if "r" not in _RUNS:
        import pyvista as pv
        _RUNS["r"] = row_runs(pv.read(str(OUT / "cup-rock.stl")), I["cells"]["cup-rock"])
    return _RUNS["r"]


def build_sheet(I):
    C, R, bl = I["C"], I["R"], I["balls"]
    n_ = C["nominal"]
    nm = sum(1 for s in I["bosses"] if s["kind"] == "mag")
    hang = I["meshes"]["cup-rock"]["m"] + n_["cast"]["m"] + SEG_G * len(n_["kept"])
    lo = n_["left"]
    lv = bl["levels"]
    bp = BAT_PATH
    L = f"""ROLY-POLY: BUILD SHEET, round 6, first print (files in cad/desk/out-rolypoly/, copies in cad/desk/to-print/rolypoly-*.stl;
numbers in report.txt)

PRINT  (Bambu X1E, Bambu Studio, 0.4 nozzle)
  body.stl        PLA Matte white, 0.12 mm (the "0.12mm Fine" process), 4+ walls. Seam ring on the plate, crown up. Supports:
                  tree (auto), on build plate only: they reach the crown's inside ({I['ov']['body']['crown']:.0f} mm2 steeper than 45 deg) and the
                  door opening's top edge (a ~29 mm bridge between the R7 corners; or let it bridge and clean the edge). Tabs,
                  bosses and bulkhead start on the plate or have 45 deg undersides; the bulkhead's notch for the USB head is a
                  {2 * HEAD_NOTCH_X:.0f} mm bridge at z {HEAD_NOTCH_TOP:g}. The logo needs none: its pockets have 45 deg roofs; if supports appear there,
                  paint them off / add a support blocker over the logo. Check in the preview that the {LOGO_SKIN:g} logo skin is
                  solid (no gap between its walls). No brim on the seam ring. Ironing (top surfaces) as on the smooth shells: optional.
                  Seen in one OrcaSlicer run in round 5 (generic 0.4 profile, 0.12 layers, tree supports; a preview, not a
                  print, before the round 6 changes): the opening's top edge (29.5 mm) is held by trees that stand in front of the
                  body and lean in over the alcove; inside the crown only a cap of about 10 x 9 mm at the very top is supported;
                  cup-rock on its back touches the bed with 11 x 5 mm, the slicer's own support base of about 60 x 30 mm
                  carries it, and one of its eight seam holes gets a support tip (rim-down: all eight, and the last layer
                  at the pole is 2.2 x 13 mm).
  cup-rock.stl    PLA Matte white, 0.12 mm, 100 % infill. Standing on its BACK (the curved back down, seam ring vertical):
                  every layer then draws the R44 arc. It cannot stand on its own footprint (13.6 x 5.8 mm at 0.12 above the
                  bed, 25 x 11 at 0.6; its centre of mass is outside that): give it a broad support cradle from the build
                  plate under the back and the bowl ({I['ov']['cup_back']['total']:.0f} mm2 steeper than 45 deg in all, none on the rolling band),
                  a brim on the supports, and no supports inside the magnet and dowel holes or the cable notch. Watch the first
                  layers. Whether the rolling band needs sanding depends on the print: check it on the gauge (FINISH). (Rim-down
                  would leave a {R['pole_flat_rim_down']:.1f} mm flat at the bottom from the last 0.12 layer and need the bowl ceiling supported.)
  cup-flat.stl    PLA Matte white, foot on the plate, no supports.
  door.stl        PLA Matte white for this print (black later), 0.12 mm, face DOWN on a smooth plate.
  arc-gauge.stl   any PLA, flat side down: a concave R44 cradle.

FINISH
  cup-rock: remove the supports at the back, sand those spots. Sit the cup in arc-gauge.stl, unlined, against a light: it
  checks the central profile (the line the cup rolls on); no light under the arc. Where there is a blob or a support stub,
  sand that spot by hand and check again on the unlined gauge. Do not line the gauge with sandpaper to true the arc: paper of
  thickness t makes its radius R44 - t. Holes: the magnet and dowel holes printed horizontally: check each with a magnet / a
  pin, ream with a depth stop (D3.1 for the magnets, D3.2 for the dowels) before gluing. Break the seam ring's outer edge on
  body and cup lightly with 400 so they meet without a lip. Slots: a rod (8.0) should slide in with a little play (8.1 slot,
  {SLOT_LAND:g} land at the door's back); if tight, a light pass with a flat needle file on the land only.

PARTS
  {2 * nm} magnets D{SEAM_MAG_D} x {SEAM_MAG_H} (seam), 8 x D{DOOR_MAG_D} x {DOOR_MAG_H} (door), 2 steel dowels D{SEAM_PIN_D} x {SEAM_PIN_L}, gel CA glue or
  5-minute epoxy for the magnets, a flat plate (glass), the right-angle USB-C extension (head <= {HEAD_W:g} x {HEAD_COLLAR + HEAD_T:g} x {HEAD_L:g},
  cable D{CABLE_D:g}), two warm-white 0603 LEDs with leads >= 150 mm (resistor per LED, ~100 ohm at 3.3 V) and an SH1.0 4-pin pigtail
  for 3V3/GND from the I2C header, Kapton, 1 mm foam tape, 304 stainless balls 2-6 mm (~{bl['nom']:.0f} g used of the set), 5-minute
  epoxy (2 x 50 ml; ~{bl['epoxy']:.0f} ml mixed in all, in three batches), stick-on balancing weights (one 12 x 5 g strip), 2 rods 8 x 4
  half-round cut to {ROD_L}, OCA tape, a small phone-screen suction cup (to pull the door), a kitchen scale (0.1 g or 1 g),
  disposable cups and sticks for mixing.

ASSEMBLY (in this order)
  1. Magnets, flush: put a drop of glue in each pocket (the pocket is 0.1 deeper than the magnet), press the magnet in and hold
     the face against a flat plate until the glue sets; check with a straightedge. Stack each pair first so every body magnet
     attracts its cup magnet (mark faces); both cups use the same map. Door and tabs the same way.
  2. Dowels: glue the two pins 5 mm deep into the BODY; the cups' holes are the sliding fit (ream to D3.2 if tight).
  3. Joint proof test, before any ballast: put the empty cup on, hang {2 * hang / 1000:.2f} kg (twice the {hang:.0f} g it will carry:
     e.g. the ball set and a water bottle in a bag) from the cup, lift by the body's crown, hold 10 s, shake lightly: it must
     stay closed. Then peel: push one end of the cup down with a thumb; it must come off by hand without loosening a magnet.
  4. LEDs: place the two LEDs in the checked room: 4.5-8.5 mm behind the logo's centre, along its normal
     (dummy-led-room.stl), facing the letters; hold them with clear hot glue on their leads, bridged to the wall beside the
     letters (reach in from below or through the opening). Run the leads up the right side to the battery's top.
  5. Battery, from below (cup off, door out, body upside down or on its side): Kapton on its front, foam tape on its back.
     Push it up along the bulkhead, centred at x {bp['X1']:+.1f} (the seam's opening is tight: {R['bat_sweep']['up']:.2f} a side), until its
     bottom is {bp['Z_MID'] - SEAM:.1f} mm above the seam plane; then {abs(bp['X2'] - bp['X1']):.1f} mm to the {'left' if bp['X2'] < bp['X1'] else 'right'} (the body's right side narrows at the
     top) and on up to its seat: bottom {BAT_Z0 - SEAM:g} mm above the seam plane (z {BAT_Z0:g}, {BAT_HEAD_MIN:g} over where the USB head will be),
     x {BAT_X:+.1f}; press onto the bulkhead. Its lead goes up to its top.
  6. Wiring: lay the battery lead and the LED leads as loops on the battery's top behind the board, each with {R['service']:.0f} mm spare
     (LEDs -> I2C ~{I['route']['led']:.0f} mm), so the door can come {R['service']:.0f} mm out with everything plugged. The {R['service']:.0f} mm loop and
     the plugs' {hw.PLUG_PROUD:.0f} mm protrusion are ASSUMED, not checked: measure the plugged board (plugs, leads and their bends) first.
     Dry fit before anything is glued: with the real LED leads and battery lead in place, close the door, then pull it
     {R['service']:.0f} mm out with everything plugged. The loops must stay clear of the trim segments and the bulkhead spots.
  7. Door + board, in from the front: door face down; rods into the slots from behind (OCA on their flat), gasket tape on the
     glass's short-end borders, board glass-down between the four corner ribs. Hold the door in front of the opening, plug the
     battery and the LED pigtail, switch the board ON (the slide is not reachable when closed; no hole for it), push the
     loops in, set the door: the magnets pull it home.
  8. USB, from below (cup off): push the extension's right-angle plug straight up into the board's port (the head goes up
     through the seam's opening and the bulkhead's notch; checked: {R['usb']['up_body']:.2f} to the body, {R['usb']['up_bat']:.2f} to the battery),
     cable towards the back. Lay the cable into the round notch in the body's back rim (open downward, at x {HEAD_X:+g}).
  9. Cast (cup-rock off the body), 5-minute epoxy in three small batches (small batches keep the heat low; each needs about
     {bl['batch_epoxy']:.1f} ml of epoxy and {bl['batch_balls']:.0f} g of balls; a batch gels in ~5 min, so mix only one at a time):
     - stand the cup upright and level (in a roll of tape or a bowl of rice; phone level on the seam ring); weigh the empty cup;
     - per batch: mix the epoxy, pour it into the bowl first, then drop the balls in (largest first, small ones into the gaps,
       tap to settle), until the balls just stand under the epoxy's surface; let it gel (~15 min) before the next batch;
     - batch 1 to {SEAM - lv[0]:.1f} mm below the seam face, batch 2 to {SEAM - lv[1]:.1f} mm, batch 3 to the step {SEAM - lv[2]:.1f} mm below the seam
       face (where the smooth bowl meets the terrace; z {lv[2]:g}, {HEAD_CLR:g} under the USB head: do not overfill); measure down from the
       rim with a ruler. Fill by weight: the cup gains {bl['nom']:.0f} g of balls in all ({bl['low']:.0f} g is still fine; if the step is
       reached first, stop and note the mass). Level the last batch. Full cure: 24 h before the trim segments go on.
       The balls are 304 stainless: they do not stick to the magnets.
  10. Trim layer: {len(I['cells']['cup-rock'])} segments fit on the cast (dummy-segments-rock.stl). The plan (nominal masses): stick
      {len(n_['spots'])} segment(s) standing on the bulkhead's back at x {', '.join(f'{x:+.0f}' for x in n_['spots']) or '-'} (right of centre, from
      z {TRIM_SPOT_Z0:g} up; dummy-trim-spots.stl shows both spots), leave out {len(lo)} of the trim layer
      {(' (' + ', '.join(f'x {c[0]:+.0f} y {c[1]:+.0f}' for c in lo) + ')') if lo else ''} and slide the rest {n_['t'] * 100:.0f} % of their rows' slack
      to the right. The door and board sit 5 mm left: without the spot the clock leans left. Keep the second spot (x
      {TRIM_SPOTS[1]:+.0f}) free for later. Do not peel the adhesive yet.
  11. Cup on, straight up: the cable slides into the cup's notch (open upward), pins find the holes, the magnets close the
      seam. Trim the fully wired clock (door closed, cable in) on the table (below), then stick the segments down.
  To open the door later: cup off (straight down), unplug the USB head from below first, then the suction cup on the door's
  face (or a blunt tool from below on the door's back strip under the PCB, right of the USB head: its way is checked with
  the head in, {R['tool']:.2f} at the closest).

TRIM
  Level table, phone level on the flat door, everything wired and closed. The plan already uses about {n_['t'] * 100:.0f} % of
  the rows' travel: the bulkhead spots are the coarse adjustment. Coarse: add or take a segment at the bulkhead spots (cup off,
  from below). Fine:
  slide a row of segments towards the high side, or move a segment across: 10 mm of
  travel of one 5 g segment moves the lean by about {math.degrees(math.atan(SEG_G * 10 / n_['st']['M'] / n_['margin'])):.1f} deg. With all segments in, sliding alone reaches
  {n_['auth'][0]:+.2f}..{n_['auth'][1]:+.2f} mm of centre-of-mass offset; leaving segments out reaches further. 0.5 mm of offset leans it
  {math.degrees(math.atan(0.5 / n_['margin'])):.1f} deg.

STABLE VARIANT
  cup-flat instead of cup-rock: {len(I['cells']['cup-flat'])} segments fit (about one strip); no cast, no trim needed.

CHECK ON THE PRINT
  rocking duration and feel; the USB cable leaning it (righting {n_['kst']:.2f} mN m per degree); falling forward (beyond
  {n_['fwd']:.0f} deg, calculated); the size; the logo glow; the seam; the magnets' pull; the cast's real mass (weigh it).
"""
    (OUT / "build-sheet.txt").write_text(L)


def focus(I):
    p, n, xd = logo_frame()
    d = dict(door_c=[XOFF, Y_PANEL, DOOR_ZC], logo=list(map(float, p)), logo_n=list(map(float, n)), seam=SEAM, RR=RR, H=H,
             slot_top=[TUBE_X[0], Y_PANEL, AA_ZC + SLOT_L / 2], usb=[HEAD_X, Y_BACK_OUT, CABLE_Z], cut_flat=CUT_FLAT,
             G_rock=list(map(float, I["C"]["nominal"]["st"]["G"])), cast_to=I["cast_to"], keels=KEELS, keel=KEEL,
             logo_x=LOGO_X, logo_x_old=LOGO_X_OLD)
    (OUT / "focus.json").write_text(json.dumps(d, indent=1))


if __name__ == "__main__":
    build()
