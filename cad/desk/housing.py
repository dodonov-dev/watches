#!/usr/bin/env python3
"""Desk housing v1 for the Waveshare ESP32-S3-LCD-3.16 (docs/desk-housing-plan.md, docs/lcd316-mechanical.md).

Parts (STEP + STL each, in out/):
  shell      one piece, open at the bottom. Inside: a plain pocket (R_IN corners, no internal features). Everything
             else is cut from outside: tube slots with a bevel (front), logo letters (side), USB-C hole (back),
             magnet holes (rim end face).
  lid        full-outline plate under the rim, with a locating plug, magnet holes, two ribs that press the carrier
             forward, and a cradle for the USB-C breakout (socket mouth against the back wall).
  carrier    plate behind the board (screwed to its 4 M2 nuts), legs down to the lid, battery rails. Nothing near
             the side walls.
  lightbox   tray glued to the logo side wall: back plate, an opal sheet in front of it, LED troughs at the sheet's
             top and bottom edges. (opal: the sheet itself, as a cutting reference.)
  teststrip  a plate as thick as the front with the same bevel and four slot widths.
Plus assembly.step / .stl with dummies (board, rods, battery, breakout, buttons, plugs), section STLs for render.py
and report.txt.

Checks (they raise instead of exporting a part that cannot work): the fits listed under "checks" below, the static
interference of every pair of bodies, and the swept paths of the two assembly moves:
  1. board + rods + carrier + battery: up at INSERT_SHIFT further back, then forward into the slots;
  2. lid + breakout: straight up.

Axes: X right (seen from the front), Y front -> back (front face at y = 0), Z up (shell rim at z = 0).
Run: ~/.venvs/cad/bin/python cad/desk/housing.py   then   ~/.venvs/cad/bin/python cad/desk/render.py
"""
import json, math, pathlib
import numpy as np
from build123d import (offset, Box, Cylinder, Cone, Pos, Plane, Rectangle, RectangleRounded, Polygon, Compound, Color,
                       extrude, fillet, chamfer, loft, export_step, export_stl, Axis, Align)
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

HERE = pathlib.Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# ---- parameters (mm) -----------------------------------------------------------------------------------------
W, D = 50.0, 34.0            # outer width (X), depth (Y)
WALL, BACK, TOP = 3.0, 3.0, 7.0   # side walls, back wall, top wall (wood: end grain needs the meat)
FRONT_T = 3.0                # front wall
SLOT_RIM = 0.0               # wall left at the slot edge, below the bevel (0: the 45° chamfer runs to the glass; prints as ~0.2–0.3)
BEVEL_DEG = 45.0             # bevel round each slot, measured from the wall's normal
FRONT_FLAT = False           # the one switch: True = a flat front SLOT_RIM thick, no bevel
R_OUT = 4.0                  # outer vertical edges
R_TOP = 3.0                  # top edges
R_IN = 3.0                   # cavity corners. Wood: drill the 4 corners 2 x R_IN first, or rest-mill with that bit
BOTTOM_BREAK = 0.5
VENTS = False                # slots through the back wall, a row at the top and one above the USB hole (off in v1)
VENT_W, VENT_H, VENT_N, VENT_PITCH = 1.5, 10.0, 5, 4.0

# board (docs/lcd316-mechanical.md); it hangs centred in X, glass against the front wall
PCB_W, PCB_H, BOARD_T = 33.35, 78.85, 9.0    # stack measured 9.0 (drawing 9.3)
GLASS_W, GLASS_H, GLASS_T = 31.2, 76.6, 3.9
AA_W, AA_H = 26.40, 67.65
AA_Z_FROM_PCB_BOTTOM = 7.5    # USB end: measured 7.6, drawing 7.475
NUT_DX, NUT_DZ, NUT_INSET = 27.35, 72.75, 3.0
BTN_SIDE = -1                # RST / BOOT / power slide: the -X edge seen from the front
BTN_PROUD = 1.0              # beyond the PCB edge. VERIFY on the board
BTN_Z = {"boot": 25.72, "rst": 36.49, "slide": 11.5}   # above the PCB bottom (slide: scaled from the drawing)
BTN_LEN, BTN_DEPTH = 4.0, 4.0   # keep-out along Z, and in Y behind the glass
PLUG_PROUD = 4.0             # J5 / I2C plug + wire bend beyond the +X PCB edge. VERIFY
PLUG_Z = {"j5": 39.42, "i2c": 56.39}   # above the PCB bottom
PLUG_LEN = 7.0
GASKET = 0.5                 # double-sided foam tape between the glass's short-end borders and the front wall
PROTOTYPE = True             # v1 prototype: board taped to the front wall, battery taped to the board, diffuser film glued
                             # behind the logo; prints only shell + lid (no ribs) + test strip. False: carrier + light box
CHIN = 13.0                  # free height between the lid plug and the PCB bottom (PROTOTYPE: PCB_Z0_PROTO instead)
# prototype USB: MOGOOD 90° USB-C adapter in the board's own port (bending over the flat side), socket facing the back wall.
# Listing: plug 8 out of the body (~6.5 of it inside the port), body 7 thick x 12 wide x 21 long, socket at the far end.
ADAPTER_COLLAR, ADAPTER_T = 1.5, 7.0   # body face below the port face (= PCB bottom edge, assumed flush); body thickness
ADAPTER_LID_CLR = 4.0        # body bottom to the lid
PCB_Z0_PROTO = ADAPTER_COLLAR + ADAPTER_T + ADAPTER_LID_CLR   # PCB bottom above the rim, prototype
ADAPTER_W, ADAPTER_L, ADAPTER_BEHIND = 12.0, 21.0, 5.0       # plug axis ~5 from the body's closed end (from the photo)
PORT_Y_FROM_BOARD_BACK = 2.0  # board's Type-C axis in front of the back of the board stack (assumed: measure)
CLEAR_TOP = 0.5              # PCB top to the cavity ceiling

# tubes / slots: the firmware's 2-tube 8 mm layout, tubeHeight 54 -> 72 px = 5.94 mm, flush with the AA long edges
TUBE_CC = 20.46              # centre to centre
ROD_W, ROD_H = 8.0, 4.0      # half-round acrylic
ROD_L = AA_H + 1.0           # 1 mm longer than the lit area
TAPE = (0.05, 0.25)          # OCA tape under the rods: thinnest, thickest
SLOT_W, SLOT_EXTRA_L = 8.6, 0.8
SLOT_R = 0.0                 # slot corners: square for the print, 0.5 for wood
INSERT_CLR = 0.25            # rod apex to the front wall's inner face during the up move
INSERT_SPARE_MIN = 1.0       # free depth that must remain behind the battery during the up move

# lid
LID_T, PLUG_H, PLUG_CLR = 3.0, 2.0, 0.3
MAG_D, MAG_H = 2.0, 1.0      # supermagnete S-02-01-N
MAG_CLR_D, MAG_CLR_H = 0.1, 0.2
MAG_MEAT_MIN = 0.4           # wall left round a magnet hole
RIB_X, RIB_W, RIB_FOAM, RIB_TOP = 15.7, 1.8, 0.5, 28.0   # ribs press the carrier plate below the battery

# carrier
CAR_T = 2.0
CAR_TOP_GAP = 0.2            # carrier top to the cavity ceiling: the Z stop, smaller than the rods' end play
LEG_X, LEG_W, LEG_GAP = 13.5, 3.0, 0.1   # legs outside the breakout cradle; gap to the lid plug
SCREW_D, HEAD_D = 2.3, 3.9   # M2 countersunk (DIN 965: head 3.8), clearance hole
BAT_W, BAT_H, BAT_T, BAT_Z0 = 29.5, 47.7, 9.9, 30.0       # BerryBase Soldered 103048, between the nut rows (carrier)
if PROTOTYPE:   # prototype: the user's pick, 3000 mAh 10 x 35 x 68, taped behind the board, upright, above the USB adapter
    BAT_W, BAT_H, BAT_T, BAT_Z0 = 35.0, 68.0, 10.0, None
RAIL_T, RAIL_CLR, RAIL_DEPTH = 1.2, 0.3, 6.0

# logo: E+H letters (trace_logo.py) cut through a side wall
LOGO_SIDE = -1               # -1: left seen from the front (the board's button side); +1: JST side
LETTERS_W = 24.0             # width of the letters themselves (their height follows, 0.631 of it)
LOGO_Z_ABOVE_TUBES = 4.0     # logo centre above the tubes' mid-height
LOGO_MARGIN = 1.0            # letters to the ends of the outer flat, and to the diffuser's edges in Y
LOGO_TOL = 0.01              # polyline simplification of the traced letters
STRIP_MIN = 1.2              # thinnest wall between the letter cuts (print; wood wants 2)

# light box, glued to the side wall behind the letters
OPAL_T = 2.0                 # diffuser sheet
OPAL_CLR = 0.1
LB_WIN_MARGIN_Z = 2.0        # diffuser beyond the letters, up and down
LB_BTN_CLR = 0.3             # tray to the button tips
LB_BACK = 0.8                # back plate behind the diffuser
LB_GLUE = 0.15               # tray to the cavity wall
LB_END = 5.0                 # block above and below the window: glue faces + LED troughs
LED_TROUGH_Z, LED_TROUGH_INSET = 1.6, 2.0   # trough depth beyond the sheet's edge; inset from the sheet's Y ends
WIRE_SLOT_W, WIRE_SLOT_D = 1.2, 1.5   # groove in the tray's inner face, from each trough to the tray's end

# USB-C breakout on the lid (Pololu 2585: 20.3 x 14, connector ~1.3 beyond the board edge)
BO_W, BO_L, BO_OVER, BO_PCB_T = 20.3, 14.0, 1.3, 1.6
BO_STAND = 2.8               # pad height above the plug top
BO_LIP, BO_LIP_H, BO_CLR = 1.2, 1.0, 0.15
BO_RELIEF_L, BO_RELIEF_D = 4.5, 1.5   # room under the solder joints at the breakout's front edge
BO_WIRE_GAP = 14.0           # opening in the front lip for the wires
USB_HOLE_W, USB_HOLE_H, USB_HOLE_R = 15.0, 8.5, 4.2    # passes a whole USB-C plug incl. overmould (typ. <= 12.5 x 6.5, bulky ~14 x 7.5): prototype = angled adapter in the board port, cable plugged through the hole
SOCKET_W, SOCKET_H, SOCKET_L = 8.94, 3.26, 7.35   # receptacle shell; it sits on the breakout PCB

# test strip
TS_SLOTS = (8.3, 8.5, 8.7, 9.0)
TS_REAL_PAIR = 1             # slots [i] and [i + 1] stand at TUBE_CC, so the bridge is the real one
TS_PITCH = 20.46             # the other pairs (= TUBE_CC: every bridge is the real one)
TS_MARGIN = 5.0
# second row: one short slot per edge profile (docs: profile-options.svg), all SLOT_W wide, labelled on the face
TS_PROFILES = ("S", "A", "B", "C", "D")   # straight, 45° to 1.5 rim, 45° to 0 (chosen), concave to 0.4 rim, round-over to 0
INLAY_CLRS = (0.10, 0.15, 0.20)   # translucent letter inlays pressed into the logo cut-outs: clearance per side, one set each
TS_PROFILE_L, TS_PROFILE_PITCH, TS_LABEL_H, TS_LABEL_D = 30.0, 18.0, 5.0, 0.6

# ---- derived -------------------------------------------------------------------------------------------------
FRONT = SLOT_RIM if FRONT_FLAT else FRONT_T
BEVEL_D = FRONT - SLOT_RIM                         # bevel depth
BEVEL_W = BEVEL_D * math.tan(math.radians(BEVEL_DEG))   # how far it opens the slot, per side
CAV_W, CAV_D = W - 2 * WALL, D - FRONT - BACK
CAV_YC = FRONT + CAV_D / 2
PLUG_TOP = PLUG_H
PCB_Z0 = PCB_Z0_PROTO if PROTOTYPE else PLUG_TOP + CHIN
PCB_Z1 = PCB_Z0 + PCB_H
if BAT_Z0 is None:                                 # prototype battery: centred on the board's height
    BAT_Z0 = PCB_Z0 + (PCB_H - BAT_H) / 2
CAV_H = PCB_Z1 + CLEAR_TOP
H_SHELL = CAV_H + TOP
AA_ZC = PCB_Z0 + AA_Z_FROM_PCB_BOTTOM + AA_H / 2
SLOT_L = ROD_L + SLOT_EXTRA_L
GLASS_Y0 = FRONT + GASKET
BOARD_Y1 = GLASS_Y0 + BOARD_T
CAR_Y1 = BOARD_Y1 + CAR_T
CAR_Z1 = CAV_H - CAR_TOP_GAP
INSERT_SHIFT = ROD_H + TAPE[1] + INSERT_CLR
USB_Z = (PCB_Z0 - ADAPTER_COLLAR - ADAPTER_T / 2 if PROTOTYPE
         else PLUG_TOP + BO_STAND + BO_PCB_T + SOCKET_H / 2)      # receptacle centre: the adapter's socket / the breakout's
BO_Y1 = D - BACK - BO_OVER                         # breakout PCB: back edge, front edge
BO_Y0 = BO_Y1 - BO_L
NUTS = [(sx * NUT_DX / 2, zz) for sx in (-1, 1) for zz in (PCB_Z0 + NUT_INSET, PCB_Z0 + NUT_INSET + NUT_DZ)]   # 72.75 pitch (drawing)

# ---- logo geometry -------------------------------------------------------------------------------------------
LOGO = json.load(open(HERE / "eh_logo.json"))


def _simplify(ring, tol):
    """Ramer-Douglas-Peucker on a closed ring."""
    pts = [tuple(p) for p in ring]
    far = max(range(len(pts)), key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2)
    ext = pts + [pts[0]]

    def rec(a, b):
        if b <= a + 1:
            return []
        (ax, ay), (bx, by) = ext[a], ext[b]
        dx, dy = bx - ax, by - ay
        n = math.hypot(dx, dy) or 1e-12
        dist, k = max((abs((ext[i][0] - ax) * dy - (ext[i][1] - ay) * dx) / n, i) for i in range(a + 1, b))
        return rec(a, k) + [k] + rec(k, b) if dist > tol else []

    return [pts[i] for i in [0] + rec(0, far) + [far] + rec(far, len(pts))]


_all = np.vstack([np.array(p) for p in LOGO["letters"]])
_u0, _v0 = _all.min(axis=0)
_u1, _v1 = _all.max(axis=0)
LETTERS_ASPECT = (_v1 - _v0) / (_u1 - _u0)


def letters_mm(width):
    """The letter polygons in mm, origin at the centre of their bounding box, x in reading direction, y up."""
    s = width / (_u1 - _u0)
    c = np.array([(_u0 + _u1) / 2, (_v0 + _v1) / 2])
    return [_simplify((np.array(p) - c) * s, LOGO_TOL) for p in LOGO["letters"]]


def strip_widths(polys, step=0.02):
    """Wall left between the cuts: from every boundary point a ray along the outward normal to the next boundary.
    Returns {edge class: (width, x, y)} for the thinnest ray of horizontal, vertical and slanted edges."""
    rings = [np.asarray(p) for p in polys]
    seg = np.vstack([np.hstack([p, np.roll(p, -1, axis=0)]) for p in rings])
    e = seg[:, 2:4] - seg[:, 0:2]
    best = {}
    for p in rings:
        q = np.roll(p, -1, axis=0)
        ccw = np.sum(p[:, 0] * q[:, 1] - q[:, 0] * p[:, 1]) > 0
        for a, b in zip(p, q):
            ln = float(np.hypot(*(b - a)))
            if ln < 1e-9:
                continue
            t = (b - a) / ln
            n = np.array([t[1], -t[0]]) if ccw else np.array([-t[1], t[0]])
            cls = "horizontal" if abs(t[1]) < 0.02 else "vertical" if abs(t[0]) < 0.02 else "slanted"
            den = n[0] * e[:, 1] - n[1] * e[:, 0]
            den = np.where(np.abs(den) < 1e-12, np.nan, den)
            for s in np.arange(step / 2, ln, step):
                o = a + t * s
                w = seg[:, 0:2] - o
                r = (w[:, 0] * e[:, 1] - w[:, 1] * e[:, 0]) / den
                k = (w[:, 0] * n[1] - w[:, 1] * n[0]) / den
                hit = r[(r > 1e-6) & (k >= 0) & (k <= 1)]
                if hit.size and (cls not in best or hit.min() < best[cls][0]):
                    best[cls] = (float(hit.min()), float(o[0]), float(o[1]))
    return best


LETTERS = letters_mm(LETTERS_W)
LETTERS_H = LETTERS_ASPECT * LETTERS_W
STRIPS = strip_widths(LETTERS)
STRIP = min(v[0] for v in STRIPS.values())
STRIP_PER_MM = STRIP / LETTERS_W
LOGO_YC = D / 2                                    # centred on the outer flat
LOGO_ZC = AA_ZC + LOGO_Z_ABOVE_TUBES
LOGO_Y = (LOGO_YC - LETTERS_W / 2, LOGO_YC + LETTERS_W / 2)
LOGO_Z = (LOGO_ZC - LETTERS_H / 2, LOGO_ZC + LETTERS_H / 2)

# ---- light box geometry: depths t are measured from the side wall's inner face towards the board -----------------
SIDE_OBSTACLE = PCB_W / 2 + (BTN_PROUD if LOGO_SIDE == BTN_SIDE else PLUG_PROUD)   # what stands beside the PCB


def lightbox_depths():
    t_in = CAV_W / 2 - SIDE_OBSTACLE - LB_BTN_CLR      # tray's inner face
    t_back = t_in - LB_BACK                            # diffuser's back
    return t_in, t_back, t_back - OPAL_T               # ... and its front: the air gap to the flat wall


def half_chord(t, r_in=R_IN, cav_d=CAV_D, offset=0.0):
    """Half the cavity's Y extent at depth t from the side wall, for an outline shrunk by offset."""
    if t < offset:
        return 0.0
    if t >= r_in:
        return cav_d / 2 - offset
    return cav_d / 2 - r_in + math.sqrt(max((r_in - offset) ** 2 - (r_in - t) ** 2, 0.0))


def opal_half_width(r_in=R_IN):
    return half_chord(max(lightbox_depths()[2], 0.0), r_in, offset=LB_GLUE) - OPAL_CLR


T_IN, T_BACK, T_FRONT = lightbox_depths()
OPAL_HALF = opal_half_width()
WIN_Z = (LOGO_Z[0] - LB_WIN_MARGIN_Z, LOGO_Z[1] + LB_WIN_MARGIN_Z)
LB_Z = (WIN_Z[0] - LB_END, WIN_Z[1] + LB_END)


def _sdf_rrect(x, y, cx, cy, hx, hy, r):
    """Signed distance to a rounded rectangle (negative inside)."""
    qx, qy = np.abs(x - cx) - (hx - r), np.abs(y - cy) - (hy - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def corner_magnet(sx, front, r_in=R_IN, r_out=R_OUT):
    """Where a rim corner holds the largest hole: the point farthest from both the cavity and the outside.
    Returns ((x, y), wall left round the magnet hole)."""
    span = r_out + max(WALL, FRONT, BACK)
    cx, cy = sx * (W / 2 - span / 2), (span / 2 if front else D - span / 2)
    for _ in range(6):                                 # grid search, 4 x finer round the best each time
        g = np.linspace(-span / 2, span / 2, 41)
        xs, ys = np.meshgrid(cx + g, cy + g)
        b = BOTTOM_BREAK                               # the rim face is the outline shrunk by the bottom chamfer
        d = np.minimum(-_sdf_rrect(xs, ys, 0, D / 2, W / 2 - b, D / 2 - b, max(r_out - b, 0.1)),
                       _sdf_rrect(xs, ys, 0, CAV_YC, CAV_W / 2, CAV_D / 2, r_in))
        k = np.unravel_index(np.argmax(d), d.shape)
        cx, cy, best, span = float(xs[k]), float(ys[k]), float(d[k]), span / 4
    return (round(cx, 2), round(cy, 2)), best - (MAG_D + MAG_CLR_D) / 2


def corner_meat(r_in=R_IN, r_out=R_OUT):
    return min(corner_magnet(1, f, r_in, r_out)[1] for f in (True, False))


def corner_magnets():
    return [corner_magnet(sx, front) for sx in (-1, 1) for front in (True, False)]


MAGNETS = corner_magnets()
MAG_MEAT = min(m for _, m in MAGNETS)


def logo_fit(r_in, r_out):
    """Widest letters with LOGO_MARGIN at both limits: the outer flat and the diffuser."""
    by_flat = D - 2 * r_out - 2 * LOGO_MARGIN
    by_opal = 2 * (opal_half_width(r_in) - abs(CAV_YC - LOGO_YC)) - 2 * LOGO_MARGIN
    return min(by_flat, by_opal), by_flat, by_opal


# ---- checks: every fit the spec depends on ----------------------------------------------------------------------
def check(ok, msg):
    if not ok:
        raise AssertionError(msg)


# front, slots, rods
check(SLOT_RIM <= FRONT, "slot rim thicker than the front wall")
check(CAV_W - 2 * R_IN >= GLASS_W + 2 * 0.3, f"front wall's flat inside {CAV_W - 2 * R_IN:.2f} < glass {GLASS_W} + 0.6")
SLOT_X1 = TUBE_CC / 2 + SLOT_W / 2 + BEVEL_W       # the bevel's outer edge on the face
FACE_SIDE_FLAT = W / 2 - R_OUT - SLOT_X1           # flat face between the bevel and the edge rounding
FACE_BRIDGE = TUBE_CC - SLOT_W - 2 * BEVEL_W       # flat face between the two bevels
FACE_TOP_FLAT = H_SHELL - R_TOP - (AA_ZC + SLOT_L / 2 + BEVEL_W)
FACE_BOTTOM = AA_ZC - SLOT_L / 2 - BEVEL_W
check(FACE_SIDE_FLAT >= 2.0, f"bevel runs into the edge rounding: {FACE_SIDE_FLAT:.2f} flat left")
check(FACE_BRIDGE >= 4.0, f"bridge between the slots only {FACE_BRIDGE:.2f} on the face")
check(FACE_TOP_FLAT >= 3.0 and FACE_BOTTOM >= 5.0, "slot bevel too close to the top or the rim")
check(TUBE_CC / 2 + SLOT_W / 2 <= CAV_W / 2 - R_IN, "slots reach the cavity's corner arcs")
check(SLOT_W - ROD_W >= 0.4 and SLOT_EXTRA_L >= 0.4, "rod clearance in the slot")
ROD_OVER_FACE = [ROD_H + t - FRONT - GASKET for t in TAPE]
ROD_OVER_RIM = [ROD_H + t - SLOT_RIM - GASKET for t in TAPE]
check(ROD_OVER_FACE[0] > 0, "rods do not reach the front face")
# Z stops: legs on the lid plug, carrier top under the ceiling; both must be tighter than the rods' end play
check(max(LEG_GAP, CAR_TOP_GAP) + 0.1 <= SLOT_EXTRA_L / 2, "the rods' ends would carry the board")
check(CAR_TOP_GAP <= CLEAR_TOP, "carrier top stop above the ceiling")
# insertion envelope
INSERT_MAX = (D - BACK) - (CAR_Y1 + BAT_T)          # how far back the stack can go at all
check(INSERT_MAX - INSERT_SHIFT >= INSERT_SPARE_MIN,
      f"insertion: needs {INSERT_SHIFT:.2f} back, the cavity allows {INSERT_MAX:.2f}")
check(CAV_W / 2 - PCB_W / 2 - PLUG_PROUD >= 1.0, "no room beside the PCB for the JST plugs")
# carrier, battery
check(PROTOTYPE or BAT_Z0 - RAIL_T >= PCB_Z0 + NUT_INSET + HEAD_D / 2 + 1 and BAT_Z0 + BAT_H <= PCB_Z1 - NUT_INSET - HEAD_D / 2 - 1,
      "battery (or its ledge) overlaps the screw heads")
check(PROTOTYPE or BAT_W / 2 + RAIL_CLR + RAIL_T <= PCB_W / 2, "battery rails wider than the carrier plate")
check(NUT_INSET - HEAD_D / 2 >= 0.8 and PCB_W / 2 - NUT_DX / 2 - HEAD_D / 2 >= 0.8, "screw heads break the plate edge")
check(PROTOTYPE or RIB_TOP < BAT_Z0 - RAIL_T - 0.5, "ribs reach the battery ledge")
check(LEG_X - LEG_W / 2 >= BO_W / 2 + BO_CLR + BO_LIP + 0.3, "carrier legs stand in the breakout cradle")
check(LEG_X + LEG_W / 2 <= PCB_W / 2, "carrier legs wider than the plate")
# lid, magnets, USB
check(MAG_MEAT >= MAG_MEAT_MIN, f"magnets: only {MAG_MEAT:.2f} mm of wall round the hole")
check(LID_T - MAG_H - MAG_CLR_H >= 1.0, "magnet holes too deep for the lid")
check(USB_Z - USB_HOLE_H / 2 >= 2.5, "USB hole too close to the rim")
check(PROTOTYPE or USB_Z + SOCKET_H / 2 + 1.0 <= PCB_Z0, "breakout socket reaches the board")
# logo
OUTER_FLAT = (R_OUT, D - R_OUT)
LOGO_FLAT_MARGIN = min(LOGO_Y[0] - OUTER_FLAT[0], OUTER_FLAT[1] - LOGO_Y[1])
check(LOGO_FLAT_MARGIN >= LOGO_MARGIN - 1e-6, f"letters {LOGO_FLAT_MARGIN:.2f} from the end of the flat side")
check(LOGO_Y[0] >= FRONT + 0.5 and LOGO_Y[1] <= D - BACK - 0.5, "letters wider than the cavity: blind cuts")
check(STRIP >= STRIP_MIN, f"thinnest strip between the letter cuts {STRIP:.2f} < {STRIP_MIN}")
check(LOGO_Z[1] + 3 <= CAV_H and LOGO_Z[0] >= PLUG_TOP + 5, "logo outside the cavity height")
# light box
check(T_FRONT >= 0, f"light box: {T_IN:.2f} mm between the wall and the {'buttons' if LOGO_SIDE == BTN_SIDE else 'plugs'}"
      f" cannot hold a {LB_BACK} back plate + {OPAL_T} diffuser")
OPAL_MARGIN_Y = OPAL_HALF - LETTERS_W / 2 - abs(CAV_YC - LOGO_YC)   # the diffuser is centred on the cavity
check(OPAL_MARGIN_Y >= LOGO_MARGIN - 1e-6, f"diffuser only {OPAL_MARGIN_Y:.2f} wider than the letters, per side")
check(LB_Z[1] <= CAV_H - 1 and LB_Z[0] >= PLUG_TOP + 1, "light box outside the cavity height")
check(LED_TROUGH_Z + 1.5 <= LB_END, "LED troughs leave no end wall")
check(WIRE_SLOT_D >= LB_BACK + 0.5, "wire grooves do not open into the LED troughs")


# ---- helpers -------------------------------------------------------------------------------------------------
def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(abs(x1 - x0), y1 - y0, z1 - z0)


def tbox(t0, t1, y0, y1, z0, z1):
    """A box given by depths from the logo side wall's inner face."""
    xs = sorted(LOGO_SIDE * (CAV_W / 2 - t) for t in (t0, t1))
    return box(xs[0], xs[1], y0, y1, z0, z1)


def rrect_prism(cx, cy, w, d, r, z0, h):
    return Pos(cx, cy, z0) * extrude(RectangleRounded(w, d, r) if r > 0 else Rectangle(w, d), h)


def volume_common(a, b):
    c = BRepAlgoAPI_Common(a.wrapped, b.wrapped)
    c.Build()
    if not c.IsDone():
        raise RuntimeError("boolean failed")
    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(c.Shape(), p)
    return p.Mass()


def gap(a, b):
    d = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    return d.Value()


def slot_cutter(x, zc, w, l):
    """One slot through a front plate (outer face y = 0, inner y = FRONT): straight w x l, bevelled out to the face."""
    prof = lambda ww, ll, r: RectangleRounded(ww, ll, r) if r > 0 else Rectangle(ww, ll)
    cut = Pos(x, FRONT / 2, zc) * extrude(Plane.XZ * prof(w, l, SLOT_R), FRONT / 2 + 1, both=True)
    if BEVEL_D > 0:
        over = 0.5                                     # the cone continues past the face, for a clean cut
        k = BEVEL_W / BEVEL_D
        g = (BEVEL_D + over) * k
        outer = Pos(x, 0, zc) * (Plane.XZ.offset(over) * prof(w + 2 * g, l + 2 * g, SLOT_R + g if SLOT_R > 0 else 0))
        inner = Pos(x, 0, zc) * (Plane.XZ.offset(-BEVEL_D) * prof(w, l, SLOT_R))
        cut += loft([outer, inner])
    return cut


def logo_faces(x_plane):
    """Letter polygons on a plane x = x_plane, readable from outside the LOGO_SIDE wall."""
    return [Plane.YZ.offset(x_plane) * Polygon(*[(LOGO_YC + LOGO_SIDE * u, LOGO_ZC + v) for u, v in poly], align=None)
            for poly in LETTERS]


# ---- parts ---------------------------------------------------------------------------------------------------
def make_shell(core=False):
    """core=True: without the logo and the magnet holes (the obstacle for the path checks: fewer faces)."""
    s = rrect_prism(0, D / 2, W, D, R_OUT, 0, H_SHELL)
    s = fillet(s.edges().group_by(Axis.Z)[-1], R_TOP)
    s = chamfer(s.edges().group_by(Axis.Z)[0], BOTTOM_BREAK)
    s -= rrect_prism(0, CAV_YC, CAV_W, CAV_D, R_IN, -1, CAV_H + 1)
    for sx in (-1, 1):
        s -= slot_cutter(sx * TUBE_CC / 2, AA_ZC, SLOT_W, SLOT_L)
    s -= Pos(0, D - BACK / 2, USB_Z) * extrude(Plane.XZ * RectangleRounded(USB_HOLE_W, USB_HOLE_H, USB_HOLE_R),
                                               BACK / 2 + 1, both=True)
    if VENTS:
        for zc in (CAV_H - 4 - VENT_H / 2, USB_Z + USB_HOLE_H / 2 + 4 + VENT_H / 2):
            for i in range(VENT_N):
                x = (i - (VENT_N - 1) / 2) * VENT_PITCH
                s -= box(x - VENT_W / 2, x + VENT_W / 2, D - BACK - 1, D + 1, zc - VENT_H / 2, zc + VENT_H / 2)
    if core:
        return s
    # letters through the side wall, deep enough for the corner zones where the wall is thicker
    for f in logo_faces(LOGO_SIDE * (W / 2 + 1)):
        s -= extrude(f, -LOGO_SIDE * (1 + WALL + R_IN + 0.5))
    for (x, y), _ in MAGNETS:
        s -= Pos(x, y, 0) * Cylinder((MAG_D + MAG_CLR_D) / 2, MAG_H + MAG_CLR_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return s


def make_lid():
    l = rrect_prism(0, D / 2, W, D, R_OUT, -LID_T, LID_T)
    l = chamfer(l.edges().group_by(Axis.Z)[0], BOTTOM_BREAK)
    for (x, y), _ in MAGNETS:
        l -= Pos(x, y, 0) * Cylinder((MAG_D + MAG_CLR_D) / 2, MAG_H + MAG_CLR_H, align=(Align.CENTER, Align.CENTER, Align.MAX))
    if PROTOTYPE:                                      # flat plate + magnets: inner parts wait for the USB / battery choice
        return l
    l += rrect_prism(0, CAV_YC, CAV_W - 2 * PLUG_CLR, CAV_D - 2 * PLUG_CLR, R_IN - PLUG_CLR, 0, PLUG_H)
    y_back = D - BACK - PLUG_CLR
    # ribs: fill the gap behind the carrier after the forward move (foam on their front faces)
    for sx in (() if PROTOTYPE else (-1, 1)):
        l += box(sx * RIB_X - RIB_W / 2, sx * RIB_X + RIB_W / 2, CAR_Y1 + RIB_FOAM, y_back, PLUG_TOP - 0.01, RIB_TOP)
    # USB-C breakout cradle: a pad with lips all round; gaps for the wires (front) and the connector (back)
    pad_top = PLUG_TOP + BO_STAND
    xi, xo = BO_W / 2 + BO_CLR, BO_W / 2 + BO_CLR + BO_LIP
    l += box(-xo, xo, BO_Y0 - BO_CLR - BO_LIP, y_back, PLUG_TOP - 0.01, pad_top + BO_LIP_H)
    l -= box(-xi, xi, BO_Y0 - BO_CLR, BO_Y1 + BO_CLR, pad_top, pad_top + 5)
    l -= box(-xi, xi, BO_Y0 - BO_CLR, BO_Y0 + BO_RELIEF_L, pad_top - BO_RELIEF_D, pad_top + 1)
    l -= box(-BO_WIRE_GAP / 2, BO_WIRE_GAP / 2, BO_Y0 - BO_CLR - BO_LIP - 1, BO_Y0, pad_top - BO_RELIEF_D, pad_top + 5)
    l -= box(-USB_HOLE_W / 2 - 0.25, USB_HOLE_W / 2 + 0.25, BO_Y1, y_back + 1, pad_top, pad_top + 5)
    return l


def carrier_boxes():
    """The carrier's solid boxes (also its envelope for the path checks)."""
    b = [("carrier-plate", (-PCB_W / 2, PCB_W / 2, BOARD_Y1, CAR_Y1, PCB_Z0, CAR_Z1))]
    rx = BAT_W / 2 + RAIL_CLR
    for sx, n in ((-1, "l"), (1, "r")):
        xs = sorted((sx * (LEG_X - LEG_W / 2), sx * (LEG_X + LEG_W / 2)))
        b.append((f"carrier-leg-{n}", (xs[0], xs[1], BOARD_Y1, CAR_Y1, PLUG_TOP + LEG_GAP, PCB_Z0 + 0.01)))
        xs = sorted((sx * rx, sx * (rx + RAIL_T)))
        b.append((f"carrier-rail-{n}", (xs[0], xs[1], CAR_Y1 - 0.01, CAR_Y1 + RAIL_DEPTH, BAT_Z0 - RAIL_T, BAT_Z0 + BAT_H)))
    b.append(("carrier-ledge", (-rx - RAIL_T, rx + RAIL_T, CAR_Y1 - 0.01, CAR_Y1 + 3.0, BAT_Z0 - RAIL_T, BAT_Z0)))
    return b


def make_carrier():
    c = None
    for _, dims in carrier_boxes():
        c = box(*dims) if c is None else c + box(*dims)
    # M2 countersunk holes at the board's nuts, heads flush on the battery side
    for x, zz in NUTS:
        c -= Pos(x, BOARD_Y1 + CAR_T / 2, zz) * Cylinder(SCREW_D / 2, CAR_T + 1, rotation=(90, 0, 0))
        c -= Pos(x, CAR_Y1 + 0.01, zz) * Cone(HEAD_D / 2, SCREW_D / 2, (HEAD_D - SCREW_D) / 2, rotation=(90, 0, 0),
                                              align=(Align.CENTER, Align.CENTER, Align.MIN))   # wide end at the back face
    return c


def make_lightbox():
    """Tray on the side wall: full-depth blocks above and below the window (glued to the wall's flat), a back plate
    between them. The opal sheet lies on the back plate; LEDs sit in the troughs at its top and bottom edges."""
    g = LB_GLUE
    body = rrect_prism(0, CAV_YC, CAV_W - 2 * g, CAV_D - 2 * g, R_IN - g, LB_Z[0], LB_Z[1] - LB_Z[0])
    body &= tbox(-1, T_IN, 0, D, LB_Z[0] - 1, LB_Z[1] + 1)
    body -= tbox(-1, T_BACK, 0, D, WIN_Z[0], WIN_Z[1])           # the window: all in front of the back plate
    ty = OPAL_HALF - LED_TROUGH_INSET
    for z0, z1, zs0, zs1 in ((WIN_Z[1] - 0.01, WIN_Z[1] + LED_TROUGH_Z, WIN_Z[1], LB_Z[1] + 1),
                             (WIN_Z[0] - LED_TROUGH_Z, WIN_Z[0] + 0.01, LB_Z[0] - 1, WIN_Z[0])):
        body -= tbox(T_FRONT, T_BACK, CAV_YC - ty, CAV_YC + ty, z0, z1)                 # LED trough
        body -= tbox(T_IN - WIRE_SLOT_D, T_IN + 1, CAV_YC + ty - WIRE_SLOT_W, CAV_YC + ty, zs0, zs1)     # wire groove
    return body


def make_opal():
    return tbox(T_FRONT, T_BACK, CAV_YC - OPAL_HALF, CAV_YC + OPAL_HALF, WIN_Z[0] + OPAL_CLR, WIN_Z[1] - OPAL_CLR)


def teststrip_layout():
    xs = [0.0]
    for i in range(1, len(TS_SLOTS)):
        xs.append(xs[-1] + (TUBE_CC if i - 1 == TS_REAL_PAIR else TS_PITCH))
    for i in range(1, len(TS_SLOTS)):
        bridge = xs[i] - xs[i - 1] - (TS_SLOTS[i] + TS_SLOTS[i - 1]) / 2 - 2 * BEVEL_W
        check(bridge >= 2.0, f"test strip: {bridge:.2f} between slots {i - 1} and {i}")
    x0 = xs[0] - TS_SLOTS[0] / 2 - BEVEL_W - TS_MARGIN
    x1 = xs[-1] + TS_SLOTS[-1] / 2 + BEVEL_W + TS_MARGIN
    h = SLOT_L + 2 * BEVEL_W + 2 * TS_MARGIN
    return xs, x0, x1, h


def profile_g(name):
    """Edge profile: (depth below the face, g(t) = how far the opening grows per side at depth t below the face)."""
    F = FRONT
    if name == "S":
        return 0.0, lambda t: 0.0
    if name == "A":
        return F - 1.5, lambda t: (F - 1.5) - t
    if name == "B":
        return F, lambda t: F - t
    if name == "C":                                    # concave, tangent to a 0.4 rim at the slot edge
        d = F - 0.4
        return d, lambda t: math.sqrt(max(d * d - t * t, 0.0))
    if name == "D":                                    # convex round-over, vertical where it meets the glass
        return F, lambda t: F - math.sqrt(max(F * F - (F - t) ** 2, 0.0))
    raise ValueError(name)


def profile_cutter(x, zc, w, l, name, steps=16):
    """Slot w x l through the front plate, its face edge shaped by profile `name` (lofted sections)."""
    cut = Pos(x, FRONT / 2, zc) * extrude(Plane.XZ * Rectangle(w, l), FRONT / 2 + 1, both=True)
    d, g = profile_g(name)
    if d <= 0:
        return cut
    ts = [d * i / steps for i in range(steps + 1)]
    secs = [Pos(x, 0, zc) * (Plane.XZ.offset(0.5) * Rectangle(w + 2 * (g(0) + 0.5), l + 2 * (g(0) + 0.5)))]
    for t in ts:
        gg = max(g(t), 0.0)
        if t >= d - 1e-6:
            gg = 0.0
        secs.append(Pos(x, 0, zc) * (Plane.XZ.offset(-t) * Rectangle(w + 2 * gg, l + 2 * gg)))
    return cut + loft(secs, ruled=True)


def make_logo_inlays():
    """Translucent letters pressed into the logo's cut-outs, flush with the outside: one E (with the slash) and one H
    per clearance in INLAY_CLRS, WALL thick, lying flat with the outer face on z = 0 (print it face down). The set
    with clearance index i carries i + 1 dimples (Ø0.8 x 0.4) on the back of one letter (the E), so the sets can be told apart."""
    sets = []
    for i, c in enumerate(INLAY_CLRS):
        pieces = []
        for poly in LETTERS:
            f = offset(Polygon(*[(-u, v) for u, v in poly], align=None), -c)   # mirrored: outer face down on the bed
            pieces.append(extrude(f, WALL))
        h = max(pieces, key=lambda b: b.bounding_box().min.X)                   # the H (mirrored: on the left)
        bb = h.bounding_box()
        for k in range(i + 1):
            h -= Pos(bb.center().X + (k - i / 2) * 1.6, bb.center().Y, WALL) * Cylinder(0.4, 0.8)
        pieces = [h if p is max(pieces, key=lambda b: b.bounding_box().min.X) else p for p in pieces]
        sets.append((c, Compound([Pos(0, -i * (LETTERS_H + 4), 0) * p for p in pieces])))
    return sets


def make_teststrip():
    """Front-wall coupon. Row 1: full-length slots TS_SLOTS wide with the chosen edge (slot n carries n notches on
    the top edge). Row 2: one short SLOT_W slot per edge profile TS_PROFILES, its letter engraved below it."""
    xs, x0, x1, h = teststrip_layout()
    xc = (x0 + x1) / 2
    span = (len(TS_PROFILES) - 1) * TS_PROFILE_PITCH
    row2_h = TS_PROFILE_L + 2 * FRONT + TS_LABEL_H + 3 * TS_MARGIN / 2
    px0, px1 = min(x0, xc - span / 2 - SLOT_W / 2 - FRONT - TS_MARGIN), max(x1, xc + span / 2 + SLOT_W / 2 + FRONT + TS_MARGIN)
    t = box(px0, px1, 0, FRONT, -h / 2 - row2_h, h / 2)
    z2 = -h / 2 - TS_MARGIN / 2 - FRONT - TS_PROFILE_L / 2
    for i, name in enumerate(TS_PROFILES):
        x = xc - span / 2 + i * TS_PROFILE_PITCH
        t -= profile_cutter(x, z2, SLOT_W, TS_PROFILE_L, name)
        zt = z2 - TS_PROFILE_L / 2 - FRONT - 1.0 - TS_LABEL_H / 2
        try:
            from build123d import Text
            label = Plane.XZ * Pos(x, zt) * Text(name, font_size=TS_LABEL_H)
            t -= extrude(label, TS_LABEL_D, dir=(0, 1, 0))
        except Exception as e:                         # no font: fall back to i + 1 notches on the bottom edge
            print(f"test strip label {name}: {e}; notches instead")
            for k in range(i + 1):
                xn = x + (k - i / 2) * 2.0
                t -= box(xn - 0.5, xn + 0.5, -1, FRONT + 1, -h / 2 - row2_h - 1, -h / 2 - row2_h + 1.0)
    for i, (x, w) in enumerate(zip(xs, TS_SLOTS)):
        t -= slot_cutter(x, 0, w, SLOT_L)
        for k in range(i + 1):
            xn = x + (k - i / 2) * 2.0
            t -= box(xn - 0.5, xn + 0.5, -1, FRONT + 1, h / 2 - 1.0, h / 2 + 1)
    return t


# ---- the bodies that move during assembly (keep-out envelopes) -----------------------------------------------------
class Body:
    """Axis-aligned box. solid(dy, ey, ez0, ez1): moved back by dy, stretched by ey towards the back and by
    ez0 / ez1 down / up, which is the volume it sweeps on a straight move."""

    def __init__(self, name, dims):
        self.name, self.dims = name, dims

    def solid(self, dy=0.0, ey=0.0, ez0=0.0, ez1=0.0):
        x0, x1, y0, y1, z0, z1 = self.dims
        return box(x0, x1, y0 + dy, y1 + dy + ey, z0 - ez0, z1 + ez1)


class Rod(Body):
    """Half-round rod with its tape (thickest), flat on the glass, round side to the front."""

    def __init__(self, name, x):
        self.name, self.x = name, x

    def solid(self, dy=0.0, ey=0.0, ez0=0.0, ez1=0.0):
        r, yf = ROD_W / 2, GLASS_Y0 - TAPE[1] + dy     # the rod's flat face
        z0, z1 = AA_ZC - ROD_L / 2 - ez0, AA_ZC + ROD_L / 2 + ez1
        rod = Pos(self.x, yf, z0) * Cylinder(r, z1 - z0, align=(Align.CENTER, Align.CENTER, Align.MIN))
        rod -= box(self.x - r - 1, self.x + r + 1, yf, yf + r + 1, z0 - 1, z1 + 1)
        return rod + box(self.x - r, self.x + r, yf - 0.01, yf + TAPE[1] + ey, z0, z1)


def moving_bodies():
    gz0 = PCB_Z0 + (PCB_H - GLASS_H) / 2
    m = [Body("glass", (-GLASS_W / 2, GLASS_W / 2, GLASS_Y0, GLASS_Y0 + GLASS_T, gz0, gz0 + GLASS_H)),
         Body("board", (-PCB_W / 2, PCB_W / 2, GLASS_Y0 + GLASS_T, BOARD_Y1, PCB_Z0, PCB_Z1)),
         Rod("rod-l", -TUBE_CC / 2), Rod("rod-r", TUBE_CC / 2)]
    yb = GLASS_Y0 + GLASS_T
    for n, z in BTN_Z.items():
        xs = sorted((BTN_SIDE * PCB_W / 2, BTN_SIDE * (PCB_W / 2 + BTN_PROUD)))
        m.append(Body(f"button-{n}", (xs[0], xs[1], yb, yb + BTN_DEPTH, PCB_Z0 + z - BTN_LEN / 2, PCB_Z0 + z + BTN_LEN / 2)))
    for n, z in PLUG_Z.items():
        xs = sorted((-BTN_SIDE * PCB_W / 2, -BTN_SIDE * (PCB_W / 2 + PLUG_PROUD)))
        m.append(Body(f"plug-{n}", (xs[0], xs[1], yb, BOARD_Y1, PCB_Z0 + z - PLUG_LEN / 2, PCB_Z0 + z + PLUG_LEN / 2)))
    if not PROTOTYPE:                                  # prototype: no carrier, the board is taped in
        m += [Body(n, d) for n, d in carrier_boxes()]
    by = BOARD_Y1 + 0.1 if PROTOTYPE else CAR_Y1         # prototype: taped to the board's back over Kapton
    m.append(Body("battery", (-BAT_W / 2, BAT_W / 2, by, by + BAT_T, BAT_Z0, BAT_Z0 + BAT_H)))
    return m


def lid_dummies():
    if PROTOTYPE:                # the adapter goes into the board's port from below, after the board is in
        py = BOARD_Y1 - PORT_Y_FROM_BOARD_BACK
        return [("adapter", box(-ADAPTER_W / 2, ADAPTER_W / 2, py - ADAPTER_BEHIND, py - ADAPTER_BEHIND + ADAPTER_L,
                                PCB_Z0 - ADAPTER_COLLAR - ADAPTER_T, PCB_Z0))]
    pad_top = PLUG_TOP + BO_STAND
    return [("breakout", box(-BO_W / 2, BO_W / 2, BO_Y0, BO_Y1, pad_top, pad_top + BO_PCB_T)),
            ("socket", box(-SOCKET_W / 2, SOCKET_W / 2, BO_Y1 + BO_OVER - SOCKET_L, BO_Y1 + BO_OVER,
                           USB_Z - SOCKET_H / 2, USB_Z + SOCKET_H / 2))]


EPS_V = 1e-3                 # mm3: touching faces give 0, any real overlap far more


def check_paths(shell_core, lid, lightbox, opal, moving):
    """Swept volumes of the two assembly moves against everything that is already in place. Returns the gaps."""
    drop = H_SHELL + 20
    fixed = {"shell": shell_core} if PROTOTYPE else {"shell": shell_core, "lightbox": lightbox, "opal": opal}
    gaps = {}
    for b in moving:
        # up at INSERT_SHIFT further back, then forward. Overlap is tested up to the Z stop (the carrier's top on the
        # ceiling), the gaps are those at the seated height
        for move, stop, seat in (("up", b.solid(dy=INSERT_SHIFT, ez0=drop, ez1=CAR_TOP_GAP), b.solid(dy=INSERT_SHIFT, ez0=drop)),
                                 ("forward", b.solid(ey=INSERT_SHIFT, ez1=CAR_TOP_GAP), b.solid(ey=INSERT_SHIFT))):
            for fn, f in fixed.items():
                v = volume_common(stop, f)
                check(v < EPS_V, f"insertion, {move} move: {b.name} cuts {v:.2f} mm3 out of the {fn}")
                gaps[(move, b.name, fn)] = gap(seat, f)
    # lid + breakout rise straight up: they hit whatever stands above them, so stretch the others upwards
    lid_set = [("lid", lid)] + lid_dummies()
    above = [(b.name, b.solid(ez1=drop)) for b in moving] + ([] if PROTOTYPE else [("lightbox", lightbox), ("opal", opal)])
    for ln, ls in lid_set:
        v = volume_common(ls, shell_core)
        check(v < EPS_V, f"{ln} cuts {v:.2f} mm3 out of the shell")
        gaps[("lid", ln, "shell")] = gap(ls, shell_core)
        for on, o in above:
            v = volume_common(ls, o)
            check(v < EPS_V, f"lid move: {ln} runs into the {on} ({v:.2f} mm3)")
            gaps[("lid", ln, on)] = gap(ls, o)
    return gaps


def check_static(named):
    """No two bodies of the finished assembly share volume."""
    for i, (na, a) in enumerate(named):
        for nb, b in named[i + 1:]:
            v = volume_common(a, b)
            check(v < EPS_V, f"assembled: {na} and {nb} overlap by {v:.2f} mm3")


def options_table():
    """The logo trade-off: cavity corner radius and outer edge radius against the letters that fit."""
    rows = ["  R_IN  R_OUT  wood bit  letters W x H   limit      strip  magnet meat"]
    for r_in, r_out in ((6, 4), (5, 4), (4, 4), (3, 4), (3, 3.5), (3, 3), (2, 3)):
        fit, by_flat, by_opal = logo_fit(r_in, r_out)
        mark = "  <- built" if (r_in, r_out) == (R_IN, R_OUT) else "  (frozen spec)" if (r_in, r_out) == (6, 4) else ""
        rows.append(f"  {r_in:<5} {r_out:<5}  {2 * r_in:>4} mm   {fit:5.2f} x {fit * LETTERS_ASPECT:5.2f}   "
                    f"{'diffuser' if by_opal < by_flat else 'flat    '}   {fit * STRIP_PER_MM:.2f}   {corner_meat(r_in, r_out):.2f}{mark}")
    return rows


def bbox_str(p):
    b = p.bounding_box()
    return f"{b.size.X:.1f} x {b.size.Y:.1f} x {b.size.Z:.1f}"


if __name__ == "__main__":
    shell, shell_core, lid, carrier = make_shell(), make_shell(core=True), make_lid(), make_carrier()
    lightbox, opal, teststrip = make_lightbox(), make_opal(), make_teststrip()
    moving = moving_bodies()

    # ---- geometric checks ----
    gaps = check_paths(shell_core, lid, lightbox, opal, moving)
    final = ([("shell", shell), ("lid", lid)] + ([] if PROTOTYPE else [("lightbox", lightbox), ("opal", opal)]) + lid_dummies()
             + [(b.name, b.solid()) for b in moving if not b.name.startswith("carrier-")] + ([] if PROTOTYPE else [("carrier", carrier)]))
    check_static(final)

    def worst(move, fixed, only=None):
        c = [(g, n) for (mv, n, f), g in gaps.items() if mv == move and f == fixed and (only is None or n.startswith(only))]
        if not c:
            return "n/a"
        g, n = min(c)
        return f"{g:.2f}" if only else f"{g:.2f} ({n})"

    # ---- exports ----
    parts = {"shell": shell, "lid": lid, "teststrip": teststrip}
    inlays = Compound([p for _, p in make_logo_inlays()])
    export_step(inlays, str(OUT / "logo-inlays.step"))
    export_stl(inlays, str(OUT / "logo-inlays.stl"), tolerance=0.01, angular_tolerance=0.1)
    if not PROTOTYPE:
        parts.update({"carrier": carrier, "lightbox": lightbox, "opal": opal})
    for n in ("carrier", "lightbox", "opal"):
        if n not in parts:
            for f in OUT.glob(f"{n}*"):
                f.unlink()
    colors = {"shell": "tan", "lid": "sienna", "carrier": "lightgreen", "lightbox": "orange", "opal": "white"}
    for name, part in parts.items():
        part.label = name
        export_step(part, str(OUT / f"{name}.step"))
        export_stl(part, str(OUT / f"{name}.stl"), tolerance=0.02, angular_tolerance=0.2)
    proto_hidden = lambda n: PROTOTYPE and (n in ("carrier", "lightbox", "opal") or n.startswith("carrier-"))
    dummies = [(n, s) for n, s in final if n not in parts and not proto_hidden(n)]
    asm_named = [(n, parts[n]) for n in ("shell", "lid", "carrier", "lightbox", "opal") if n in parts] + dummies
    for n, s in asm_named:
        s.label = n
        if n in colors:
            s.color = Color(colors[n])
    for f in list(OUT.glob("dummy-*.stl")) + list(OUT.glob("section-*.stl")):
        f.unlink()
    for n, s in dummies:
        export_stl(s, str(OUT / f"dummy-{n}.stl"), tolerance=0.03)
    asm = Compound([s for _, s in asm_named])
    export_step(asm, str(OUT / "assembly.step"))
    export_stl(asm, str(OUT / "assembly.stl"), tolerance=0.05)

    # sections for render.py: x = through the right tube's axis; y = through the logo's centre, seen from the front;
    # z = through the logo's centre, seen from above, assembled (z) and during the up move (ins)
    big = 3 * H_SHELL
    cut_x = box(TUBE_CC / 2, big, -big, big, -big, big)
    cut_y = box(-big, big, -big, LOGO_YC, -big, big)
    cut_z = box(-big, big, -big, big, LOGO_ZC, big)
    inserting = [(n, s) for n, s in asm_named if n in ("shell", "lightbox", "opal")] + [(b.name, b.solid(dy=INSERT_SHIFT)) for b in moving if not proto_hidden(b.name)]
    for tag, cutter, items in (("x", cut_x, asm_named), ("y", cut_y, asm_named), ("z", cut_z, asm_named), ("ins", cut_z, inserting)):
        for n, s in items:
            c = s - cutter
            if c.volume > 0.01:
                export_stl(c, str(OUT / f"section-{tag}-{n}.stl"), tolerance=0.03)

    # ---- report ----
    xs_ts, x0_ts, x1_ts, h_ts = teststrip_layout()
    side = "left (-X)" if LOGO_SIDE < 0 else "right (+X)"
    lbx = sorted(LOGO_SIDE * (CAV_W / 2 - t) for t in (LB_GLUE, T_IN))
    opx = sorted(LOGO_SIDE * (CAV_W / 2 - t) for t in (T_FRONT, T_BACK))
    R = []
    R.append(f"DESK HOUSING v1  ({'flat front' if FRONT_FLAT else f'front {FRONT} with a {BEVEL_DEG:.0f} deg bevel to a {SLOT_RIM} rim'})")
    R.append(f"outer        {W} x {D} x {H_SHELL + LID_T:.2f} (shell {H_SHELL:.2f} + lid {LID_T}); edges R{R_OUT} vertical, R{R_TOP} top")
    R.append(f"cavity       {CAV_W} x {CAV_D} x {CAV_H:.2f}, corners R{R_IN} ({2 * R_IN:.0f} mm bit or corner drill in wood)")
    R.append(f"slots        {SLOT_W} x {SLOT_L:.2f} at x +-{TUBE_CC / 2}, z {AA_ZC - SLOT_L / 2:.2f}..{AA_ZC + SLOT_L / 2:.2f}, corners R{SLOT_R}; "
             f"on the face {SLOT_W + 2 * BEVEL_W:.2f} x {SLOT_L + 2 * BEVEL_W:.2f}")
    R.append(f"face margins flat beside the bevels {FACE_SIDE_FLAT:.2f} (+ R{R_OUT} edge), bridge {FACE_BRIDGE:.2f} on the face / "
             f"{TUBE_CC - SLOT_W:.2f} at the rim, above {FACE_TOP_FLAT:.2f} (+ R{R_TOP} edge), below {FACE_BOTTOM:.2f} to the rim "
             f"({FACE_BOTTOM + LID_T:.2f} to the desk)")
    R.append(f"rods         {ROD_W} x {ROD_H} x {ROD_L:.2f}; apex over the face {ROD_OVER_FACE[0]:.2f}..{ROD_OVER_FACE[1]:.2f}, "
             f"over the rim (slot edge) {ROD_OVER_RIM[0]:.2f}..{ROD_OVER_RIM[1]:.2f} (tape {TAPE[0]}..{TAPE[1]}); "
             f"in the slot {(SLOT_W - ROD_W) / 2:.2f} per side, {SLOT_EXTRA_L / 2:.2f} per end")
    R.append(f"insertion    up at {INSERT_SHIFT:.2f} further back (rod {ROD_H} + tape {TAPE[1]} + {INSERT_CLR}), then forward. "
             f"The cavity allows {INSERT_MAX:.2f}: {INSERT_MAX - INSERT_SHIFT:.2f} spare behind the battery")
    R.append(f"  up move      rods to the front wall {worst('up', 'shell', 'rod')}, battery to the back wall {worst('up', 'shell', 'battery')}, "
             f"carrier to the ceiling {worst('up', 'shell', 'carrier-plate')}, plugs to the side wall {worst('up', 'shell', 'plug')}; "
             f"nearest to the light box {worst('up', 'lightbox')}")
    R.append(f"  forward move rods in the slots {worst('forward', 'shell', 'rod')}, nearest to the light box {worst('forward', 'lightbox')}; "
             f"no overlap anywhere on either move, also with the carrier up on its Z stop")
    lidg = sorted((g, f"{n} to {f}") for (mv, n, f), g in gaps.items() if mv == "lid" and f != "shell")[:3]
    R.append(f"  lid move     straight up, no overlap; nearest: " + ", ".join(f"{n} {g:.2f}" for g, n in lidg))
    R.append(f"Z stops      legs {LEG_GAP} above the lid plug, carrier top {CAR_TOP_GAP} under the ceiling; rod end play {SLOT_EXTRA_L / 2:.2f}")
    R.append(f"magnets      {len(MAGNETS)} x D{MAG_D} x {MAG_H} in holes D{MAG_D + MAG_CLR_D} x {MAG_H + MAG_CLR_H}, wall round the hole {MAG_MEAT:.2f}; "
             f"at {', '.join(f'({x:.2f}, {y:.2f})' for (x, y), _ in MAGNETS)}")
    R.append(f"USB          hole {USB_HOLE_W} x {USB_HOLE_H} R{USB_HOLE_R} at z {USB_Z:.2f} ({USB_Z - USB_HOLE_H / 2:.2f} above the rim); " +
             (f"adapter socket centre {PCB_Z0 - USB_Z:.2f} below the PCB, its face ~{D - BACK - (BOARD_Y1 - PORT_Y_FROM_BOARD_BACK - ADAPTER_BEHIND + ADAPTER_L):.1f} inside the back wall; body {PCB_Z0 - ADAPTER_COLLAR - ADAPTER_T:.1f} above the rim" if PROTOTYPE else f"breakout y {BO_Y0:.2f}..{BO_Y1:.2f}, top of the socket {PCB_Z0 - USB_Z - SOCKET_H / 2:.2f} below the PCB"))
    R.append(f"carrier      plate {PCB_W} x {CAR_T} x {CAR_Z1 - PCB_Z0:.2f}, legs at x +-{LEG_X}, battery z {BAT_Z0}..{BAT_Z0 + BAT_H}, "
             f"screws M2 x {CAR_T + 3:.0f} countersunk")
    R.append(f"logo         {side}, letters {LETTERS_W:.2f} x {LETTERS_H:.2f}, y {LOGO_Y[0]:.2f}..{LOGO_Y[1]:.2f}, z {LOGO_Z[0]:.2f}..{LOGO_Z[1]:.2f} "
             f"(centre {LOGO_ZC:.2f} = tubes' mid-height + {LOGO_Z_ABOVE_TUBES})")
    R.append(f"  margins      {LOGO_FLAT_MARGIN:.2f} to the ends of the {OUTER_FLAT[1] - OUTER_FLAT[0]:.0f} mm outer flat, "
             f"{OPAL_MARGIN_Y:.2f} to the diffuser's edges in Y, {LB_WIN_MARGIN_Z:.2f} in Z")
    R.append(f"  strips       thinnest wall between the cuts {STRIP:.2f} (target >= {STRIP_MIN} print, 2 wood): "
             + ", ".join(f"{k} edges {v[0]:.2f}" for k, v in sorted(STRIPS.items(), key=lambda kv: kv[1][0])))
    R.append(f"light box    tray x {lbx[0]:.2f}..{lbx[1]:.2f}, z {LB_Z[0]:.2f}..{LB_Z[1]:.2f} ({bbox_str(lightbox)}); "
f"{LB_BTN_CLR:.2f} to the button tips, {CAV_W / 2 - T_IN - PCB_W / 2:.2f} to the PCB edge")
    R.append(f"  diffuser     opal {2 * OPAL_HALF:.2f} x {WIN_Z[1] - WIN_Z[0] - 2 * OPAL_CLR:.2f} x {OPAL_T}, x {opx[0]:.2f}..{opx[1]:.2f}: "
             f"{T_FRONT:.2f} air to the flat wall, {LB_BACK} back plate behind; LED troughs "
             f"{2 * (OPAL_HALF - LED_TROUGH_INSET):.1f} x {OPAL_T} x {LED_TROUGH_Z} at its top and bottom edges")
    R.append(f"test strip   {x1_ts - x0_ts:.1f} x {h_ts:.1f} x {FRONT}, slots {', '.join(str(w) for w in TS_SLOTS)} at x "
             f"{', '.join(f'{x:.2f}' for x in xs_ts)} (slots {TS_REAL_PAIR + 1} and {TS_REAL_PAIR + 2} at {TUBE_CC}); n notches = slot n")
    R.append("volumes cm3  " + ", ".join(f"{n} {p.volume / 1000:.1f}" for n, p in parts.items()))
    R.append("")
    R.append("gaps along the insertion path, mm (swept body to what is fixed; 0.00 = it ends seated there):")
    R.append("  body             up: shell  light box   forward: shell  light box")
    for b in moving:
        R.append(f"  {b.name:<16} {gaps[('up', b.name, 'shell')]:9.2f} {min(gaps.get(('up', b.name, 'lightbox'), math.nan), gaps.get(('up', b.name, 'opal'), math.nan)):10.2f} "
                 f"{gaps[('forward', b.name, 'shell')]:16.2f} {min(gaps.get(('forward', b.name, 'lightbox'), math.nan), gaps.get(('forward', b.name, 'opal'), math.nan)):10.2f}")
    R.append("")
    R.append(f"logo options (letters that fit with {LOGO_MARGIN} mm to the flat's ends and to the diffuser's edges):")
    R += options_table()
    text = "\n".join(R)
    (OUT / "report.txt").write_text(text + "\n")
    print(text)
