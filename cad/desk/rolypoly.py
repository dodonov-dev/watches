#!/usr/bin/env python3
"""Desk housing, track B ("roly-poly"): CAD for the FDM prototype (docs/desk-housing-rolypoly-handoff.md), round 8: the face,
board, glass, rods, land, battery and USB head TILT back (TILT deg, nominal 8; pivot: the board's bottom back edge, lifted so
the USB head's lowest corner stays at round 7's height over the cast). The front is the body's own surface, leaning with the
face: horizontal sections are the study's superellipses whose front quarter-curves are pulled apart by a flat where the
tubes are (the face plane, 3.0 in front of the land along both slots), the front depth on the centre line follows the face
plane over the slots, rounds over into the head above and blends into the belly / keel below (no recess, no brow, no shelf);
the head leans back by HEAD_SHEAR of the face's lean. Slots: 0.6 land, then a round lip to the face on each long side
(pebble-A), STRIP_W flat between the slots, straight ends. One surface for body and cup: the cup's rim meets the body
exactly at the seam. The flat cup is dropped.

Parts (STEP + STL each, in out-rolypoly/):
  body       the shell from the seam (z SEAM) up: lofted outer surface, the inner surface the same points moved WALL along
             the surface normal; the inner land (the front FRONT_T thick over the glass), the two slots (SLOT_W with a SLOT_LAND
             land at the inner face, then the lips), the logo's stencil pocket (from inside), the cable notch in the back rim
             (open downward), the seam bosses.
  cup-rock   the same surface below the seam: the rocking arc, the bowl for the cast, the trim terrace, bosses, notch.
  arc-gauge  a concave R RR cradle to check (and true) the printed arc.
  logo-stencil  the logo's stencils: the pocket's floor outline, the letters cut through; three web widths, laid out for
             printing (flat back on the bed).
Plus dummies (board, glass, rods, battery, the USB head and cable, the cast, segments, the LEDs' room) for the views,
the two keels' outer surfaces, report.txt, build-sheet.txt; with --surface only the surface-level study for this TILT
(surface-tilt<T>.json: side silhouette, grid mass model), run for 6 / 8 / 10 before the build.

Frame (the study's): x right seen from the front, y front -> back (front is -y), z up from the bottom pole (the rocking
arc's lowest point). The rocking arc's centre is (x 0, z RR). The board frame: the same, before the tilt (round 7's
numbers, lifted by LIFT); world = board frame turned TILT about the x axis through (PIV_Y, PIV_Z), top backwards.

Checks raise instead of exporting: the front surface (the face plane over the slots on the function and on the solid, its
smallest radius of curvature, no brow above the slots, the seam front's slope), the front's thickness along the slot edges
and the inner land under the glass (measured on the body, in the board frame), the slots' land and lips (sections), the seam
(body and cup sections equal), the board's and battery's ways in from below, the USB plug's way up, head and cable clear of
the cup / cast / segments / bosses / battery, the cable hole, the cup off straight down with the cable in, the trim spots on
the back wall, the LEDs' room, the logo pocket (skin, outline, overhangs) and the stencil, minimum walls measured on the
solids, the arc through the pole, overhangs printed rim-down, and the mass model on the exported meshes for the nominal and
the bad case (centre of mass under the rocking centre, one sideways rest position over the full revolution, fore-aft limits,
plumb by the trim plan). The mass model's asserts are collected, written into the report and the build sheet, then raised.

Run: ROLY_TILT=6 / 8 / 10 ~/.venvs/cad/bin/python cad/desk/rolypoly.py --surface  (each a minute), then
     ~/.venvs/cad/bin/python cad/desk/rolypoly.py   then   ~/.venvs/cad/bin/python cad/desk/render_rolypoly.py
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
# ---- printed walls --------------------------------------------------------------------------------------------
WALL = 2.4                                                     # FDM (SLA later ~2.0)
RHO_PLA = 1.24

# ---- front (round 8): the body's own surface leaning with the face, a flat where the tubes are, lipped slots ---------------
SLOT_LAND = 0.6                                                # straight land at the inner face before the lip starts
                                                               # (smooth shells' print test 2026-11-19: a knife edge printed 0.8 wide)
RIM = SLOT_LAND
SLOT_W = 8.1                                                   # smooth shells' round 3: rods measured 8.0, snug fit (hw.SLOT_W 8.6)
ROD_PLAY_MIN = 0.1                                             # slot width over the rod, at least
LAND_DY, SLOT_SECTIONS = 0.01, 23                              # land measurement: depth step, sections along each slot
LAND_TOL = 3e-5                                                # a wall counts as land while within this of where it meets the inner
                                                               # face (the lip leaves the land tangentially: the pebble's land_tol)
FRONT_T = hw.FRONT                                             # 3: the front over the glass, and along every slot edge
FACE_Y = -16.4                                                 # board frame: the face plane (round 7's: the board keeps its place)
STRIP_W = 7.0                                                  # flat strip between the two slots' openings on the face (pebble-A)
LIP_END_DEG = 87.0                                             # the lip (a quarter ellipse, vertical at the land's top) stops this
                                                               # short of tangency and runs out along its tangent: it meets the face
                                                               # at 3 deg (no visible edge; the boolean stays transversal: pebble-A)
LIP_DEG_STEP = 1.5                                             # the lip's facets (sagitta < 0.001)
ZONE_MARGIN = 0.3                                              # the flat beyond both slots' openings on the face (x), and beyond the
                                                               # slots' ends along the lean (z) (polish: 1.5 -> 0.3, what the slots
                                                               # need: the thickness is measured 0.1 outside the openings)
FRONT_T_TOL = 0.05                                             # front thickness at the slot edges: FRONT_T -+ this
BLEND_R_MIN = 2.5                                              # outer surface: smallest radius of curvature over the front
SEAM_DEG_MAX = 30.0                                            # the front's lean from vertical between the seam and the slots, at most
                                                               # (round 7's shelf ran out flat)
LAND_MARGIN = 1.0                                              # inner land beyond the glass, all round
ZONE_FLAT_TOL = 0.01                                           # the flat on the lofted solid: off the face plane at most
SEAM_TOL = 0.02                                                # body and cup outer sections at the seam: apart at most
BOARD_SWEEP_MIN = 0.3                                          # the board's way in from below: clearance, at least
# board's way in (board frame): up along the lean at y + BOARD_UP_SHIFT (the rods' crowns 0.5 behind the land), then
# forward onto the land
BOARD_UP_SHIFT = hw.ROD_H + hw.TAPE[1] - hw.GASKET + 0.5
# The tilt. Nominal TILT 8 (user: 6 / 8 / 10 to compare, ROLY_TILT for the studies). Pivot: the board stack's bottom back
# edge (y PIV_Y, z PIV_Z = round 7's PCB bottom): the USB head hangs below the board and turns with it; its far end goes down
# ~1.9 mm at 8 deg, below round 7's 17.5 (the cast's top 17 + HEAD_CLR). Lifting the board instead (tried: 1.87) raised the
# centre of mass 0.5 and the clock got a second rest lying on its side (~96 deg). So the board stays and the cast gets a
# dimple under the head's far end, made by a printed CAST PLUG set into the last batch (cast-plug.stl).
LIFT = float(os.environ.get("ROLY_LIFT", "0.0"))               # board frame lifted this much (0: the pivot is round 7's)
TILT = float(os.environ.get("ROLY_TILT", "8.0"))
COS_T, SIN_T, TAN_T = math.cos(math.radians(TILT)), math.sin(math.radians(TILT)), math.tan(math.radians(TILT))
# The front surface (see body8_xyz). Below the slots the centre line's depth blends from the study's belly / keel (at
# FRONT_Z_A) into the face plane (at the slots' lower ends + ZONE_MARGIN) with a C1 ease; the flat's width fades in with it.
# Above the slots the head rounds over (exponent HEAD_M over the rest of the height); the flat fades out over HEAD_FADE. The body
# above the seam leans back with the face: the sections' y-centre moves back HEAD_SHEAR x tan(TILT) per mm on average, a
# smoothstep from SHEAR_Z0 to SHEAR_Z1, constant above. Without it the battery's top corners (tilted back into the narrowing
# back) miss their way in (-0.10 a side at 8 deg; with it +0.59).
FRONT_Z_A = 0.0
HEAD_SHEAR = float(os.environ.get("ROLY_SHEAR", "0.6"))     # ROLY_SHEAR: the tilt studies (10 deg needs more: a thinner head folds)
HEAD_M = 2.4
SHEAR_LEN = 30.0
SHEAR_Z1 = 100.0                                               # the lean stops here (a smoothstep from SHEAR_Z0): the head above does
                                                               # not lean further (full lean to the crown: the head's front corners
                                                               # bent with R 3.1 and read as edges in the clay views; polish: z1 70 -> 100 for a fuller crown, R 4.8)
SHEAR_Z0 = SEAM                                                # where the lean starts (None: Z_B, the face plane's lower end)
HEAD_FADE = 25.0                                               # (polish: 10 -> 25: the band above the slots)
PE_FRONT = 3.0                                                 # the front quarter-curves' exponent where the flat is full (the study's PE 2.6;
                                                               # polish: 3.0 lets the curvature start gently at the flat's ends)
FLANK_MIN = 3.0                                                # the flat's ends stay this far inside the section's flanks

# the board stack in the board frame (round 7's), the pivot, the lift
Y_LAND = FACE_Y + FRONT_T                              # the inner land (the front's inner face over the glass)
Y_GLASS0 = Y_LAND + hw.GASKET
Y_GLASS1 = Y_GLASS0 + hw.GLASS_T
Y_BOARD1 = Y_GLASS0 + hw.BOARD_T                       # back of the board stack
PORT_Y = Y_BOARD1 - hw.PORT_Y_FROM_BOARD_BACK          # the board's Type-C axis (y)
HEAD_Y0 = PORT_Y - hw.ADAPTER_BEHIND                   # the head's closed (front) end
HEAD_Y1 = HEAD_Y0 + hw.ADAPTER_L                       # its far end: the cable leaves here
PIV_Y = Y_BOARD1


def _head_low_rel():
    """The USB head's lowest corner below the pivot after the tilt (the head hangs ADAPTER_COLLAR + ADAPTER_T below the PCB)."""
    return min(-(y - PIV_Y) * SIN_T + z * COS_T for y in (HEAD_Y0, HEAD_Y1) for z in (-hw.ADAPTER_COLLAR - hw.ADAPTER_T, 0.0))


PCB_Z0_R7 = 26.0                                       # round 7's PCB bottom
PCB_Z0 = PCB_Z0_R7 + LIFT                               # board frame = world before the tilt
HEAD_LOW = PCB_Z0 + _head_low_rel()                    # the USB head's lowest corner (world z)
PIV_Z = PCB_Z0


def to_world(y, z):
    """Board frame (y, z) -> world (arrays or floats)."""
    y, z = np.asarray(y, float), np.asarray(z, float)
    return PIV_Y + (y - PIV_Y) * COS_T + (z - PIV_Z) * SIN_T, PIV_Z - (y - PIV_Y) * SIN_T + (z - PIV_Z) * COS_T


def to_board(y, z):
    y, z = np.asarray(y, float), np.asarray(z, float)
    return PIV_Y + (y - PIV_Y) * COS_T - (z - PIV_Z) * SIN_T, PIV_Z + (y - PIV_Y) * SIN_T + (z - PIV_Z) * COS_T


def pts_board(P):
    """(n, 3) world points -> board frame."""
    P = np.asarray(P, float)
    yb, zb = to_board(P[:, 1], P[:, 2])
    return np.c_[P[:, 0], yb, zb]


def pts_world(P):
    P = np.asarray(P, float)
    y, z = to_world(P[:, 1], P[:, 2])
    return np.c_[P[:, 0], y, z]


R_TILT = np.array([[1.0, 0.0, 0.0], [0.0, COS_T, SIN_T], [0.0, -SIN_T, COS_T]])   # board -> world, for vectors


def y_face(z, face=None):
    """World y of the face plane (board frame y = FACE_Y) at world height z."""
    face = FACE_Y if face is None else face
    return PIV_Y + ((face - PIV_Y) + (np.asarray(z, float) - PIV_Z) * SIN_T) / COS_T


# ---- inside ---------------------------------------------------------------------------------------------------
M_BOARD, M_BAT, M_MISC = 34.0, 47.0, 10.0                      # WEIGHED (2026-11-24): board with rods and LEDs 34, battery 47;
                                                               # misc = USB cable ~5 (still being chosen), magnets ~1, the rest
BAD = dict(M_BOARD=38.0, M_BAT=50.0, RHO_CAST=4.8)             # the bad case: the weighed masses + a margin (was 52 / 60, a guess
                                                               # found online); the cast is filled by feel, not measured
BAT_L, BAT_HT, BAT_T = 68.0, 35.0, 10.0                        # battery on its long edge (68 along x, 35 tall)
BAT_GAP = 1.0                                                  # board back -> battery (Kapton + tape): taped to the board's back
BAT_HOLD = 0.5                                                 # its way up: this far behind its seat, then forward onto the board
BAT_HEAD_MIN = 1.0                                             # battery bottom above the USB head, at least
BAT_Z0 = PCB_Z0 + BAT_HEAD_MIN                                 # battery bottom (round 6: over the USB head; was 23)
BAT_SWEEP_MIN = 0.3                                            # battery's way up from below: clearance, at least (asserted - 0.05)

# ---- seam joint ---------------------------------------------------------------------------------------------------
SEAM_MAG_D, SEAM_MAG_H = 3.0, 2.0                              # S-03-02-N, ~300 g each (vendor), 6 pairs
SEAM_PIN_D, SEAM_PIN_L = 3.0, 10.0                             # steel dowel pins, 2
MAG_CLR_D, MAG_CLR_H = 0.1, 0.1                                # pocket: magnet + 0.1 of glue; set flush against a flat plate
MEAT_MIN = 0.8                                                 # wall left round a magnet / pin hole
BOSS_MEAT = 1.0
# boss positions on the seam: (kind, x, side) with side -1 = front wall, +1 = back wall; round 6's (the printed cups' holes),
# placed on the seam section (round 8: new positions, the cups are new)
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
BACK_MIN = 25.0                                                # nominal backward limit, at least (round 8: the tilt moves the mass
                                                               # back; the brief asks forward >= 28 only, round 7 held both at 28)
BUILD_STEPS = False                                            # the terraces-only rocking cup (round 1's alternative), off
PLUMB_TOL = 0.2                                                # centre of mass to the arc's centre line after the fill plan
# Trim spots (round 7: the bulkhead is gone): segments stuck standing (12 across, 19 tall, 4 thick) on the back inner wall,
# right of the centre line, turned so their back lies on the wall. The board sits 5 mm left: with the cast in, the clock
# leans left, more than the symmetric trim layer can take.
TRIM_SPOTS = (27.5, 13.0, 18.0)                                # x centres, in the order they are used (round 6: 27.5, 15 on the
                                                               # bulkhead; turned to the curved wall, 15 would touch the first
                                                               # spot; the third sits above the other two: the bad case needs it.
                                                               # Round 8: the third 20 -> 18: at 20 the nominal case overshot plumb
                                                               # by 0.03 with all three; a fourth at x 34 hit the tilted battery)
TRIM_SPOT_Z_LO = SEAM + 0.5                                    # each spot's bottom: the lowest from here (0.5 steps) clear of the body
TRIM_SPOT_BAT = 0.3                                            # spot to the battery (seated and on its way up), at least

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
HEAD_CLR = 0.5                                                 # head + cable to cups, cast, segments, bosses, spots, at least
CABLE_HOLE_FROM = 4.0                                          # the passage starts this far behind the head's far end (round 7: 3.4)
CABLE_LAY_MIN = 0.1                                            # cable laid up into the body's notch (a vertical sweep): at least

# ---- logo -----------------------------------------------------------------------------------------------------
LOGO_W, LOGO_X, LOGO_ZC = 14.0, 27.0, 38.0                     # letters' width, centre x, centre z (round 7b: x 32, z 31. Round 8:
                                                               # there the pocket straddled the new front's turn from the belly
                                                               # into the leaning face: its floor's normals spread 50 deg, the lower
                                                               # right flank leaned 6 deg INTO the axis (the stencil would not go
                                                               # in). Up to z 38 (on the leaning part) and left to x 27: the front
                                                               # sits ~3 further back than round 7's belly, so at x 30 the LEDs'
                                                               # room came 2.5 from the battery (needs 3); x 27: 3.4, flanks >= 26
                                                               # deg from the axis, the letters more frontal)
LOGO_ZONE_CLR = 2.0                                            # letters right of the front's flat, at least
LED_SHIFT = 0.0                                                # LEDs' room right of the letters' centre (round 2-3: 2.0)
LOGO_SKIN = 1.0                                                # wall left over the letters (round 6: 0.8 -> 1.0, as the smooth
                                                               # shells after their 2026-11-19 print: thinner showed through unlit)
# Round 7b: the smooth shells' "stencil" logo. One rounded-rectangle pocket from inside behind the LOGO_SKIN skin, and a
# separate stencil (painted black, the letters cut through) pushed into it from inside before the board: logos swap without
# reprinting the body. The belly curves strongly here (the surface turns ~33 deg across the letters): a plane over the
# pocket's outline lies 1.0 .. ~3.4 behind the outer surface, more than the wall. So the floor follows the outer surface at
# LOGO_SKIN (as the letters' floors did) and so does the stencil's front face; its back is one plane (printed on the bed).
# The flanks taper (STENCIL_DEG, the top STENCIL_TOP_DEG) from the floor out to the inner face, corners round (the pebble's: the rectangle
# should not read from outside). smooth.py's STENCIL_CLR_TOP (a bridged top) does not apply: the top flank prints as a ceiling
# under 45 deg (the pebble dropped it too); nor STENCIL_BACK: the inner face is curved, the flat back stands proud of it.
STENCIL_MARGIN = 1.1                                           # pocket floor beyond the letters' box, all round (the pebble's)
STENCIL_R = 2.0                                                # its corners (the pebble's)
STENCIL_DEG = 45.0                                             # the pocket's flanks from the floor's normal (the wall's) ...
STENCIL_TOP_DEG = 52.0 + TILT                                  # ... the top one (blended round the upper corners): printed
                                                               # rim-down it is a ceiling; at 45 it came out 46 from vertical (round
                                                               # 7b: 52); round 8: the logo sits on the leaning front, its axis looks
                                                               # TILT up: + TILT keeps the ceiling as steep
STENCIL_LEDGE = 0.12                                           # the flanks start this far behind the floor (a straight strip:
                                                               # a kink lying on the floor's surface fails the boolean; round 5)
STENCIL_CLR = 0.10                                             # stencil to pocket, per side, across the axis, all round
STENCIL_T_MIN = 0.8                                            # the stencil at its thinnest (where the floor lies deepest)
STENCIL_SWEEP = 15.0                                           # its way in, tested: along the axis from this far inside
STENCIL_STRIPS = (None, 1.0, 1.4)                              # web between the letter cuts, per stencil (None: as designed)
STENCIL_GAP_MIN = 0.5                                          # stencil (seated) to the board, battery, USB and their ways in
STENCIL_LED_MIN = 0.2                                          # ... to the LEDs' room
POCKET_OVER = 0.5                                              # the flanks run on this far past the inner face
POCKET_BOSS_CLR = 0.3                                          # a seam boss near the pocket stays whole, + this all round

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


def _sstep(t):
    return t * t * (3 - 2 * t)


def plan_xy(th, z):
    """The study's body without any front treatment: (X, Y) at superellipse angle th and height z."""
    c, s = np.cos(th), np.sin(th)
    ex = np.sign(c) * np.abs(c) ** (2 / PE)
    ey = np.sign(s) * np.abs(s) ** (2 / PE)
    X = xc(z) + np.where(ex < 0, a_side(z, "L"), a_side(z, "R")) * ex
    Y = np.where(ey < 0, bf_of(z), bb_of(z)) * ey
    return X, Y


# ---- round 8's front: the slots, the flat, the surface ------------------------------------------------------------------
ROD_L = hw.TS_FLAT_ROD_L                               # 66.65
SLOT_L = ROD_L + hw.TS_FLAT_PLAY                       # 66.85
TUBE_X = (XOFF - hw.TUBE_CC / 2, XOFF + hw.TUBE_CC / 2)
AA_ZC = PCB_Z0 + hw.AA_Z_FROM_PCB_BOTTOM + hw.AA_H / 2   # board frame
SLOT_Z = (AA_ZC - SLOT_L / 2, AA_ZC + SLOT_L / 2)       # board frame
OPEN_HALF = (hw.TUBE_CC - STRIP_W) / 2                 # each slot's opening on the face, half (6.73)
FACE_OPEN = 2 * OPEN_HALF
LIP_B = FRONT_T - RIM                                  # the lip's depth (2.4)
_LE = math.radians(LIP_END_DEG)
LIP_A = (OPEN_HALF - SLOT_W / 2) / ((1 - math.cos(_LE)) + (1 - math.sin(_LE)) * math.tan(_LE))   # its width (to the arc's end)
ZONE_X = (TUBE_X[0] - OPEN_HALF - ZONE_MARGIN, TUBE_X[1] + OPEN_HALF + ZONE_MARGIN)
ZONE_ZB = (SLOT_Z[0] - ZONE_MARGIN, SLOT_Z[1] + ZONE_MARGIN)   # the face plane along the lean (board frame z on the face)
Z_B = float(to_world(FACE_Y, ZONE_ZB[0])[1])           # ... in world z: the plane from Z_B to Z_T
Z_T = float(to_world(FACE_Y, ZONE_ZB[1])[1])


def _quad(t):
    """C1 ease (two parabolas): 0 -> 1 with zero slope at both ends."""
    t = np.clip(t, 0, 1)
    return np.where(t < 0.5, 2 * t * t, 1 - 2 * (1 - t) ** 2)


def y_centre(z, shear=None):
    """The sections' y-centre: 0 up to SHEAR_Z0, then the body leans back by `shear` of the face's lean (C1 ramp over
    SHEAR_LEN); with SHEAR_Z1 set: a smoothstep from SHEAR_Z0 to SHEAR_Z1 instead (shear x the face's lean on average),
    constant above (the head does not lean further)."""
    shear = HEAD_SHEAR if shear is None else shear
    z0 = Z_B if SHEAR_Z0 is None else SHEAR_Z0
    d = np.asarray(z, float) - z0
    if SHEAR_Z1 is not None:
        return shear * TAN_T * (SHEAR_Z1 - z0) * _sstep(np.clip(d / (SHEAR_Z1 - z0), 0, 1))
    r = np.where(d <= 0, 0.0, np.where(d < SHEAR_LEN, d * d / (2 * SHEAR_LEN), d - SHEAR_LEN / 2))
    return shear * TAN_T * r


def front_line(z, ease=None, shear=None, head_m=None):
    """The front's y on the flat (the centre line's side profile) and the flat's weight (0: none, 1: the full width).
    Below Z_B: the study's belly / keel (-bf_of) eased into the face plane from FRONT_Z_A; Z_B..Z_T: the face plane; above:
    the head: the plane's line continued from the leaned centre, times a superellipse taper (exponent head_m) to the top."""
    ease = ease or _quad
    shear = HEAD_SHEAR if shear is None else shear
    head_m = HEAD_M if head_m is None else head_m
    z = np.asarray(z, float)
    w = ease(np.clip((z - FRONT_Z_A) / (Z_B - FRONT_Z_A), 0, 1))
    y_lo = -bf_of(z) * (1 - w) + y_face(z) * w
    u = np.clip((z - Z_T) / (H - Z_T), 0, 1)
    yct = float(y_centre(Z_T, shear))
    B_t = yct - float(y_face(Z_T))
    g1 = TAN_T - float(y_centre(Z_T + 1e-4, shear) - y_centre(Z_T - 1e-4, shear)) / 2e-4
    taper = np.clip(1 - u ** head_m, 0, None) ** (1 / head_m)
    y_hd = y_centre(z, shear) - (B_t - g1 * (z - Z_T)) * taper
    y = np.where(z < Z_B, y_lo, np.where(z <= Z_T, y_face(z), y_hd))
    wf = np.where(z <= Z_T, w, 1 - _sstep(np.clip((z - Z_T) / HEAD_FADE, 0, 1)))
    return y, wf


def body8_xyz(th, z, ease=None, shear=None, head_m=None, flat=True):
    """Round 8's outer surface at superellipse angle th (the study's parameter) and height z. The back half is the study's,
    moved back by y_centre. The front half: its two quarter-curves (the study's superellipse, exponent PE, as functions of
    the x fraction) are pulled apart by the flat [xl, xr] at y = front_line (the face plane over the slots): the curve
    leaves the flat with zero slope and zero curvature. The flat spans ZONE_X (both openings + ZONE_MARGIN) times its
    weight, about the section's centre xc. Parameter: |phi| <= phf on the flat (speed matched to the curves' at their
    start), the curves by sin(v pi / 2) of the x fraction (finite speed at the flat's ends). flat=False: no flat (the
    study's front curve at the front_line depth)."""
    th, z = np.broadcast_arrays(np.asarray(th, float), np.asarray(z, float))
    yfront, wf = front_line(z, ease, shear, head_m)
    if not flat:
        wf = np.zeros_like(wf)
    yc_ = y_centre(z, shear)
    xc_ = xc(z)
    aL, aR = a_side(z, "L"), a_side(z, "R")
    bf = yc_ - yfront
    bb = bb_of(z)
    xl = xc_ + wf * (ZONE_X[0] - xc_)
    xr = xc_ + wf * (ZONE_X[1] - xc_)
    WL, WR = np.maximum(xl - (xc_ - aL), 1e-9), np.maximum(xc_ + aR - xr, 1e-9)
    c, s = np.cos(th), np.sin(th)
    ex = np.sign(c) * np.abs(c) ** (2 / PE)
    ey = np.sign(s) * np.abs(s) ** (2 / PE)
    Xb = xc_ + np.where(ex < 0, aL, aR) * ex
    Yb = yc_ + bb * ey
    phi = np.mod(th, 2 * np.pi) - 1.5 * np.pi           # 0 at the front's centre, -pi/2 the left flank, +pi/2 the right
    A = (xr - xl) / 2
    Bw = (WL + WR) / 2 * np.pi / 2
    phf = A * (np.pi / 2) / np.maximum(A + Bw, 1e-12)
    v = np.clip((np.abs(phi) - phf) / np.maximum(np.pi / 2 - phf, 1e-12), 0, 1)
    g = np.sin(v * np.pi / 2)
    pf = PE + (PE_FRONT - PE) * wf                      # the study's exponent where there is no flat (the keel, the crown)
    Yc = yc_ - bf * np.clip(1 - g ** pf, 0, None) ** (1 / pf)
    inflat = np.abs(phi) <= phf
    Xf = np.where(inflat, xl + (xr - xl) * (phi + phf) / np.maximum(2 * phf, 1e-12), np.where(phi > 0, xr + WR * g, xl - WL * g))
    Yf = np.where(inflat, yfront, Yc)
    front = s < 0
    return np.where(front, Xf, Xb), np.where(front, Yf, Yb), z


def flat_limits(z):
    """The flat's x ends and the flanks' x at world height z (for the checks)."""
    _, wf = front_line(z)
    xc_ = xc(z)
    return xc_ + wf * (ZONE_X[0] - xc_), xc_ + wf * (ZONE_X[1] - xc_), xc_ - a_side(z, "L"), xc_ + a_side(z, "R"), wf


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
DENSE_Z = z_rows(ZB0, ZB1, 900, extra=[SEAM, Z_B, Z_T])


def normals(G):
    """Outward unit normals of a grid (rows = z, columns = around, counter-clockwise seen from above)."""
    du = np.roll(G, -1, 1) - np.roll(G, 1, 1)
    dv = np.gradient(G, G[:, 0, 2], axis=0)             # rows are horizontal sections: z is the row coordinate
    n = np.cross(du, dv)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n


FOLD_TOL = 0.005                           # a column of offset points may run back down by this much (numerical)


def fold_depth(G, N, t):
    z = (G - t * N)[:, :, 2]
    return float((np.maximum.accumulate(z, axis=0) - z).max())


class Shape:
    """One outer surface on the dense grid, its normals; the inner surface is the outer moved WALL along its normal (asserted
    fold-free: round 8's front has no tight convex bend; the lips are cut, not lofted)."""

    def __init__(self, name, fn):
        """fn(th, z) -> X, Y, Z."""
        self.name, self.fn = name, fn
        self.G_OUT = self.grid(DENSE_Z)
        self.N_OUT = normals(self.G_OUT)
        k = int(np.argmin(np.abs(DENSE_Z - 40)))         # outward: at the widest row the normals point away from the centre line
        g = self.G_OUT[k]
        check(np.mean(np.sum(self.N_OUT[k, :, :2] * (g[:, :2] - g[:, :2].mean(0)), -1) > 0) > 0.9, f"{name}: normals point inwards")
        self.fold = fold_depth(self.G_OUT, self.N_OUT, WALL)
        check(self.fold <= FOLD_TOL, f"{name}: the WALL offset folds ({self.fold:.4f})")
        self.G_GEN, self.N_GEN = self.G_OUT, self.N_OUT

    def xyz(self, th, z):
        return self.fn(th, z)

    def grid(self, zs):
        Z = np.repeat(np.asarray(zs, float)[:, None], NU, 1)
        X, Y, _ = self.xyz(np.repeat(TH[None, :], len(zs), 0), Z)
        return np.stack([X, Y, Z], -1)

    def offset_rows(self, t, zs, outer=False):
        """Sections of the outer surface moved t along its normal, re-sliced at the levels zs: [NU x 3] each. Folds are
        checked on the rows that feed these levels."""
        G_, N_ = self.G_OUT, self.N_OUT
        Q = G_ - t * N_
        k = (DENSE_Z >= min(zs) - t - 2) & (DENSE_Z <= max(zs) + t + 2)
        check(fold_depth(G_[k], N_[k], t) <= FOLD_TOL, f"{self.name}: offset {t} folds")
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

    def offset_range(self, t):
        zc_ = (self.G_GEN - t * self.N_GEN)[:, :, 2]
        return float(zc_[0].max()), float(zc_[-1].min())


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


SH8 = Shape(f"round 8 (tilt {TILT:g})", body8_xyz)


def tw(shape):
    """A board-frame solid turned into the world (TILT about x through the pivot, top backwards)."""
    return shape.rotate(Axis((0, PIV_Y, PIV_Z), (1, 0, 0)), -TILT)


def tb(shape):
    """A world solid turned into the board frame."""
    return shape.rotate(Axis((0, PIV_Y, PIV_Z), (1, 0, 0)), TILT)


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
    if abs(v1 / v0 - 1) > STEP_VOL_TOL:                 # noted in the report's FILES lines, not fatal (the STL is checked on its own)
        print(f"NOTE {path.name}: triangulated volume {v1:.2f} re-imported, {v0:.2f} written ({(v1 / v0 - 1) * 100:+.3f} %)", flush=True)
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
PCB_Z1 = PCB_Z0 + hw.PCB_H
GLASS_Z0 = PCB_Z0 + (hw.PCB_H - hw.GLASS_H) / 2
BAT_Y0 = Y_BOARD1 + BAT_GAP
BAT_Y1 = BAT_Y0 + BAT_T
# the inner land (board frame): flat at Y_LAND over the glass + LAND_MARGIN (z) and the flat's width (x: the front is FRONT_T
# behind both slots' whole openings), its lower edge rising towards the back (no flat overhang)
LAND_X = (min(XOFF - hw.GLASS_W / 2 - LAND_MARGIN, ZONE_X[0]), max(XOFF + hw.GLASS_W / 2 + LAND_MARGIN, ZONE_X[1]))
LAND_Z = (GLASS_Z0 - LAND_MARGIN, GLASS_Z0 + hw.GLASS_H + LAND_MARGIN)
# the board's envelope across (local x from the board's centre line): buttons on the -X edge, plugs on the +X edge
ENV_X = {hw.BTN_SIDE: hw.PCB_W / 2 + hw.BTN_PROUD, -hw.BTN_SIDE: hw.PCB_W / 2 + hw.PLUG_PROUD}
SEAM_R_HOLE = (SEAM_MAG_D + MAG_CLR_D) / 2
PIN_R_BODY, PIN_R_CUP = (SEAM_PIN_D + 0.1) / 2, (SEAM_PIN_D + 0.2) / 2
PIN_DEPTH = SEAM_PIN_L / 2 + 0.5
BOSS_H = {"mag": SEAM_MAG_H + MAG_CLR_H + 1.0, "pin": PIN_DEPTH + 1.0}
HOLE_R = {"mag": SEAM_R_HOLE, "pin": max(PIN_R_BODY, PIN_R_CUP)}
CUP_ROCK_CAST_TO = 17.0                                # the cast's top (round 6 / 7): the USB head's lowest corner stays HEAD_CLR over it


# ---- surfaces as solids ---------------------------------------------------------------------------------------------
C1_JOINTS = (FRONT_Z_A + (Z_B - FRONT_Z_A) / 2, Z_B, Z_T, Z_T + HEAD_FADE) + (
    (SHEAR_Z0, SHEAR_Z1) if SHEAR_Z1 is not None else (Z_B, Z_B + SHEAR_LEN) if SHEAR_Z0 is None else (SHEAR_Z0, SHEAR_Z0 + SHEAR_LEN))   # where the surface is only C1


def loft_levels(z0, z1, n=100):
    """The loft rows: cosine-spaced, plus 0.5 mm rows round each C1 joint of the front (the lofts overshoot there on coarse
    rows) and the seam."""
    band = [z for j in C1_JOINTS for z in np.arange(j - 1.5, j + 1.51, 0.5)]
    return z_rows(z0, z1, n, extra=[SEAM] + sorted(set(np.round(band, 4))))


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


LOFT_TOL = 0.06                            # outer loft to the surface function
LOFT_TOL_IN = 0.15                         # inner lofts to their offset points (hidden; the measured wall governs)


class Surfaces:
    """The lofted solids of SH8 (one surface for body and cup): outer (from the bottom pole), inner (WALL), mid (WALL / 2),
    bands."""

    def __init__(self, sh):
        self.sh = sh
        self.levels = loft_levels
        self.outer = loft(list(sh.grid(self.levels(ZB0, ZB1))), pole=(float(xc(0.0)), 0.0, 0.0))
        lo, hi = sh.offset_range(WALL)
        self.inner_z = (lo + 0.03, hi - 0.03)
        self.inner = loft(sh.offset_rows(WALL, self.levels(*self.inner_z)))
        # deviation: the outer from its function between the loft rows and between the columns; the inner from its offset
        # points between the loft rows
        sel = np.zeros(len(DENSE_Z), bool)
        sel[5::31] = True
        rows = DENSE_Z[sel]
        thm = theta_of(U + V_SEAM + np.pi / NU)
        mid = np.stack(sh.xyz(np.repeat(thm[None, ::5], len(rows), 0), np.repeat(rows[:, None], len(thm[::5]), 1)), -1)
        self.dev_outer = surface_deviation(self.outer, np.vstack([sh.G_OUT[sel, ::10].reshape(-1, 3), mid.reshape(-1, 3)]))
        zs = [z for z in rows if self.inner_z[0] + 0.5 < z < self.inner_z[1] - 0.5]
        self.dev_inner = surface_deviation(self.inner, np.vstack([q[::10] for q in sh.offset_rows(WALL, zs)]))
        check(self.dev_outer < LOFT_TOL and self.dev_inner < LOFT_TOL_IN,
              f"{sh.name} lofts off their points: outer {self.dev_outer:.3f}, inner {self.dev_inner:.3f}")

    def cup_outer(self):
        """The rocking cup's outer solid: the outer loft below the seam."""
        if not hasattr(self, "_cup"):
            self._cup = one_solid(self.outer & box(-100, 100, -100, 100, -5.0, SEAM), "cup-rock outer")
        return self._cup

    def mid(self):
        """The surface moved WALL / 2 inwards, as a solid: features are clipped to it so their faces end inside the wall
        (a face on the outer loft itself makes the fuse fail)."""
        if not hasattr(self, "_mid"):
            lo, hi = self.sh.offset_range(WALL / 2)
            self._mid = loft(self.sh.offset_rows(WALL / 2, self.levels(lo + 0.03, hi - 0.03)))
        return self._mid

    def band(self, t, z0, z1):
        """The OUTER surface moved t inwards, as a solid between the levels z0 and z1 (flat ends)."""
        return loft(self.sh.offset_rows(t, z_rows(z0, z1, 24), outer=True))


def seam_point(x, side, z=SEAM, sh=None):
    """Outer surface at height z (a dense-grid row): the point at x on the front (side -1) or back (+1), its plan normal.
    Round 8's surface by default."""
    sh = SH8 if sh is None else sh
    k = int(np.argmin(np.abs(DENSE_Z - z)))
    check(z != SEAM or abs(DENSE_Z[k] - SEAM) < 1e-9, "seam row missing")
    g, n = sh.G_OUT[k], sh.N_OUT[k]
    sel = np.where(np.sign(g[:, 1]) == side)[0]
    o = sel[np.argsort(g[sel, 0])]
    y = float(np.interp(x, g[o, 0], g[o, 1]))
    nx, ny = float(np.interp(x, g[o, 0], n[o, 0])), float(np.interp(x, g[o, 0], n[o, 1]))
    L = math.hypot(nx, ny)
    return np.array([x, y]), np.array([nx / L, ny / L])


def boss_spots():
    """Boss and hole centres: MEAT_MIN + 0.2 from the outer surface at the seam, plus however far the surface recedes over
    the cup's hole depth (the arc pulls in below the seam) and the body's (round 8: the front leans back above the seam)."""
    out = []
    for kind, x, side in BOSSES:
        p, n = seam_point(x, side)
        depth = SEAM_MAG_H + MAG_CLR_H if kind == "mag" else PIN_DEPTH
        rec = 0.0
        for zz in np.r_[np.linspace(SEAM - depth, SEAM, 6), np.linspace(SEAM, SEAM + depth, 6)]:
            q, _ = seam_point(x, side, zz)
            rec = max(rec, float(np.dot(p - q, n)))
        d = HOLE_R[kind] + MEAT_MIN + 0.2 + rec
        c = p - d * n
        out.append(dict(kind=kind, x=float(c[0]), y=float(c[1]), r_boss=HOLE_R[kind] + BOSS_MEAT, h=BOSS_H[kind],
                        side=side, x_nom=x, recede=rec))
    return out


# ---- battery: x where it passes the seam and sits (inner sections across its y band, board frame) -----------------------
_QB = {}


def inner_x_limits(zb, y0, y1, t=WALL):
    """The inner surface's section at board-frame height zb (the WALL offset of the dense grid turned into the board frame,
    each column re-sliced): the x span free over the board-frame y band y0..y1."""
    if t not in _QB:
        Q = (SH8.G_OUT - t * SH8.N_OUT).reshape(-1, 3)
        _QB[t] = pts_board(Q).reshape(SH8.G_OUT.shape)
    Q = _QB[t]
    zc_ = np.maximum.accumulate(Q[:, :, 2], axis=0) + np.arange(len(Q))[:, None] * 1e-9
    xs = np.array([np.interp(zb, zc_[:, j], Q[:, j, 0]) for j in range(Q.shape[1])])
    ys = np.array([np.interp(zb, zc_[:, j], Q[:, j, 1]) for j in range(Q.shape[1])])
    lo, hi = -1e9, 1e9
    for yy in np.linspace(y0, y1, 21):
        # crossings of the closed polyline with the line y = yy
        a, b = np.c_[xs, ys], np.roll(np.c_[xs, ys], -1, 0)
        k = (a[:, 1] - yy) * (b[:, 1] - yy) <= 0
        xx = a[k, 0] + (yy - a[k, 1]) * (b[k, 0] - a[k, 0]) / np.where(b[k, 1] == a[k, 1], 1e-12, b[k, 1] - a[k, 1])
        lo, hi = max(lo, xx.min()), min(hi, xx.max())
    return lo, hi


def battery_path(dz=0.25, sweep_min=None):
    """The battery's way up from below (cup off, board in): straight up at x X1 until its bottom reaches Z_MID, across to
    x X2, then straight up to its seat height at x X2, all BAT_HOLD behind its seat; then forward onto the board's back
    (round 6: raised over the USB head to z BAT_Z0, its top reaches where the body's right side has narrowed (the upper
    body sits XOFF left), while the seam's opening is narrow on both sides; a straight way is the case Z_MID = BAT_Z0).
    The levels each move passes, the inner sections across the battery's y band (seat and held back); Z_MID chosen for
    the largest least clearance. Round 8: all in the board frame (the battery tilts with the board and moves along it);
    the levels from where the whole band lies above the seam (below it the cup is off). Returns a dict."""
    sweep_min = BAT_SWEEP_MIN if sweep_min is None else sweep_min
    top = BAT_Z0 + BAT_HT
    zs0 = PIV_Z + (SEAM - PIV_Z + (BAT_Y1 + BAT_HOLD - PIV_Y) * SIN_T) / COS_T
    zs = np.round(np.arange(zs0, top + dz / 2, dz), 4)
    lims = np.array([inner_x_limits(z, BAT_Y0, BAT_Y1 + BAT_HOLD) for z in zs])

    def rng(z0, z1):
        k = (zs >= z0 - 1e-9) & (zs <= z1 + 1e-9)
        return lims[k, 0].max(), lims[k, 1].min()
    best = None
    for zm in np.round(np.arange(zs0 - 2.0, BAT_Z0 + dz / 2, dz), 4):
        lo1, hi1 = rng(zs0, zm + BAT_HT)
        lo2, hi2 = rng(zm, top)
        x1, x2 = (lo1 + hi1) / 2, (lo2 + hi2) / 2
        lo3, hi3 = rng(zm, zm + BAT_HT)
        m = min((hi1 - lo1 - BAT_L) / 2, (hi2 - lo2 - BAT_L) / 2, min(x1, x2) - BAT_L / 2 - lo3, hi3 - max(x1, x2) - BAT_L / 2)
        if best is None or m > best["m"] + 1e-9:
            best = dict(m=float(m), Z_MID=float(zm), X1=float(x1), X2=float(x2), lo=float(lo2), hi=float(hi2),
                        straight=(hi2 - lo2 - BAT_L) / 2 if zm == BAT_Z0 else None)
    lo0, hi0 = rng(zs0, top)
    best["zs0"] = float(zs0)
    best["straight"] = float((hi0 - lo0 - BAT_L) / 2)
    check(best["m"] >= sweep_min, f"battery: no way up from below with {sweep_min} each side (best {best['m']:.3f})")
    return best


BAT_PATH = battery_path(sweep_min=float(os.environ.get("ROLY_BAT_MIN", BAT_SWEEP_MIN)))
BAT_X, BAT_XLO, BAT_XHI = BAT_PATH["X2"], BAT_PATH["lo"], BAT_PATH["hi"]

# ---- USB: the extension's head in the port (board frame, turned with the board), its cable straight back ----------------
HEAD_X = XOFF                                          # the port at the board's x centre (housing.py)
HEAD_Z1 = PCB_Z0                                       # collar face on the PCB's bottom edge (assumed flush with the port face)
HEAD_Z0 = HEAD_Z1 - HEAD_COLLAR - HEAD_T               # board frame
_hc = np.array([[HEAD_X + sx * HEAD_W / 2, y, z] for sx in (-1, 1) for y in (HEAD_Y0, HEAD_Y1) for z in (HEAD_Z0, HEAD_Z1)])
HEAD_BB = tuple(float(v) for v in np.r_[pts_world(_hc).min(0), pts_world(_hc).max(0)][[0, 3, 1, 4, 2, 5]])   # world box
CABLE_Y0, CABLE_Z_HEAD = (float(v) for v in to_world(HEAD_Y1, HEAD_Z0 + HEAD_T / 2))   # the far end's centre (world)
CABLE_Z = max(CABLE_Z_HEAD, CUP_ROCK_CAST_TO + HEAD_CLR + CABLE_D / 2)   # the cable runs straight back (horizontal) at this height:
                                                       # it leaves the head and bends up a little to clear the cast (round 7: z 21)
Y_BACK_OUT = float(bb_of(CABLE_Z) + y_centre(CABLE_Z))  # back surface on the centre line at the cable's height
check(HEAD_BB[4] > CUP_ROCK_CAST_TO - 3.0, "the USB head reaches too far into the cast for the plug's dimple")
LED_MIN = 3.0                                          # LEDs' room to the battery's way up and the board's way in, at least
SKIN_RANGE = (LOGO_SKIN - 0.02, LOGO_SKIN + 0.05)      # logo skin, normal thickness, over a grid on the pocket's floor
LOGO_OPEN = 5.0                                        # behind the floor, free along the ray this far = open there
LOGO_OPEN_MIN = 0.95                                   # share of the floor whose column opens into the cavity


def logo_frame():
    """Point on the outer surface at (LOGO_X, LOGO_ZC) on the front, its outward normal and a horizontal tangent: exact on
    the surface function (round 4; until round 3 it snapped to the nearest grid column, ~1 mm apart there)."""
    body_xyz = SH8.xyz
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
LAND_DEG = 50.0                                        # the land's lower face rises this steeply towards the back, in the world
LAND_SLOPE = math.tan(math.radians(LAND_DEG + TILT))   # ... in the board frame (the tilt takes TILT off it)


def land_fill():
    """The inner land's block (world): from far in front back to Y_LAND over LAND_X x LAND_Z in the board frame, its lower
    face rising towards the back (LAND_DEG from horizontal in the world: no flat overhang when printed rim-down). Clipped
    to the mid surface by make_body."""
    blk = box(LAND_X[0], LAND_X[1], FACE_Y - 15, Y_LAND, LAND_Z[0] - 15 * LAND_SLOPE, LAND_Z[1])
    n = np.array([0.0, LAND_SLOPE, -1.0]) / math.hypot(LAND_SLOPE, 1.0)
    return tw(blk - halfspace((0.0, Y_LAND, LAND_Z[0]), tuple(n)))


def slot_profile(x, w=None, rim=None, lip_a=None):
    """One slot's section across (board frame x, y): w straight through from behind the land (Y_LAND + 1), a straight land
    `rim` deep at the inner face, then on each long side the lip: a quarter ellipse lip_a wide and FRONT_T - rim deep,
    vertical at the land's top, stopped LIP_END_DEG short of the face and run out along its tangent through the face plane
    (3 deg) to 0.05 in front of it, then straight out to 1 in front. Points counter-clockwise."""
    w = SLOT_W if w is None else w
    rim = RIM if rim is None else rim
    a = LIP_A if lip_a is None else lip_a
    b = FRONT_T - rim
    ph = np.radians(np.r_[np.arange(0.0, LIP_END_DEG, LIP_DEG_STEP), LIP_END_DEG])
    arc = np.c_[w / 2 + a * (1 - np.cos(ph)), Y_LAND - rim - b * np.sin(ph)]
    e = arc[-1]
    d = np.array([a * math.sin(_LE), -b * math.cos(_LE)])
    t = (e[1] - (FACE_Y - 0.05)) / (b * math.cos(_LE))
    run = e + t * d
    right = np.vstack([[w / 2, Y_LAND + 1.0], arc, run, [run[0], FACE_Y - 1.0]])
    left = right[::-1] * np.array([-1.0, 1.0])
    return np.vstack([right, left]) + np.array([x, 0.0])


def lip_x(depth, w=None, rim=None, lip_a=None):
    """Designed: the slot's half width (from its axis) at `depth` in front of the land (board frame), on the profile."""
    P = slot_profile(0.0, w, rim, lip_a)
    R = P[P[:, 0] > 0]
    y = Y_LAND - depth
    k = np.argsort(-R[:, 1])
    return float(np.interp(-y, -R[k, 1], R[k, 0]))


def slot_cutter(x, w=None, rim=None, lip_a=None):
    """One slot (world): slot_profile extruded along the lean over SLOT_L (straight ends), turned with the board."""
    P = slot_profile(x, w, rim, lip_a)
    c = Pos(0, 0, SLOT_Z[0]) * extrude(Polygon(*[tuple(map(float, q)) for q in P], align=None), SLOT_L, dir=(0, 0, 1))
    bb = c.bounding_box()
    check(abs(bb.min.Z - SLOT_Z[0]) < 1e-6 and abs(bb.max.Z - SLOT_Z[1]) < 1e-6, "slot cutter: not along the slot")
    return tw(c)


def front_box():
    """Region round both slots (and the land) where the front's measurements are taken (world): the fault harness's blank."""
    return tw(box(LAND_X[0] - 4, LAND_X[1] + 4, FACE_Y - 3, Y_LAND + 3, LAND_Z[0] - 3, LAND_Z[1] + 3))


def make_body(S):
    """Round 8's body: the shell from the seam up, the inner land and the seam bosses (clipped to the mid surface), the
    cable notch and the seam holes, the two slots, the logo pocket. Returns (body, the bare shell, the front blank: the
    front region before the slots are cut, for the fault harness)."""
    b = S.outer & box(-100, 100, -100, 100, SEAM, H + 10)
    b = b - S.inner
    b = one_solid(b, "body shell")
    shell_only = b
    add = land_fill()
    for s in boss_spots():
        add = add + zcyl(s["x"], s["y"], s["r_boss"], SEAM, SEAM + s["h"])
    b = one_solid(b + (add & S.mid()), "body + land + bosses")
    # cuts: the cable notch (the round hole's part above the seam, open downward), seam holes, slots, logo pocket
    b = b - cable_hole()
    for s in boss_spots():
        r = SEAM_R_HOLE if s["kind"] == "mag" else PIN_R_BODY
        d = SEAM_MAG_H + MAG_CLR_H if s["kind"] == "mag" else PIN_DEPTH
        b = b - zcyl(s["x"], s["y"], r, SEAM - 1, SEAM + d)
    b = one_solid(b, "body before the slots")
    blank = one_solid(b & front_box(), "front blank")
    for x in TUBE_X:
        b = b - slot_cutter(x)
    b = one_solid(b, "body with the slots")
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    op = BRepAlgoAPI_Cut()
    op.SetFuzzyValue(1e-4)                                  # the roofed pocket: a plain cut misclassified it (round 5)
    pk = logo_pocket(S)["cut"]
    b = b._bool_op((b,), (pk,), op)
    check(len(b.solids()) == 1, f"body after the logo cut: {len(b.solids())} solids")
    return one_solid(b, "body"), shell_only, blank


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


LOGO_LEDGE = 0.3                                       # a ceiling steeper than 45 deg may reach this far behind the skin (the
                                                       # flanks' STENCIL_LEDGE strip at the top of the floor)


def logo_axes():
    """The logo's frame: its centre on the outer surface, the outward normal n (the pocket's axis), the horizontal tangent
    xd and up = n x xd."""
    p, n, xd = logo_frame()
    return p, n, xd, np.cross(n, xd)


def frame_pt(F, u, v, w):
    """The point (u, v) of the logo's plane, w behind its tangent plane at the logo's centre (along -n)."""
    p, n, xd, up = F
    return p + u * xd + v * up - w * n


def rr_outline(w, h, r, step=1.0, arc_step=0.4):
    """A rounded rectangle w x h (corners r) round the origin, counter-clockwise from the middle of its right edge: points
    about `step` apart on the straight edges (arc_step on the corners) and their outward unit normals. (Chords 1 apart
    miss the floor's curve by < 0.01: within the flanks' STENCIL_LEDGE strip.)"""
    a, b = w / 2 - r, h / 2 - r
    pts, nrm = [], []

    def edge(p0, p1, nn):
        k = max(1, int(math.ceil(math.dist(p0, p1) / step)))
        for t in np.arange(k) / k:
            pts.append(np.add(p0, t * np.subtract(p1, p0)))
            nrm.append(nn)

    def arc(c, a0):
        k = max(2, int(math.ceil(r * math.pi / 2 / arc_step)))
        for t in np.arange(k) / k:
            d = np.array([math.cos(a0 + t * math.pi / 2), math.sin(a0 + t * math.pi / 2)])
            pts.append(np.asarray(c, float) + r * d)
            nrm.append(d)
    edge((w / 2, 0), (w / 2, b), (1, 0))
    arc((a, b), 0)
    edge((a, h / 2), (-a, h / 2), (0, 1))
    arc((-a, b), math.pi / 2)
    edge((-w / 2, b), (-w / 2, -b), (-1, 0))
    arc((-a, -b), math.pi)
    edge((-a, -h / 2), (a, -h / 2), (0, -1))
    arc((a, -b), 1.5 * math.pi)
    edge((w / 2, -b), (w / 2, 0), (1, 0))
    return np.array(pts, float), np.array(nrm, float)


def rr_sdf(uv, w, h, r):
    """Signed distance of points (u, v) to the rounded rectangle w x h (corners r) round the origin: < 0 inside."""
    q = np.abs(np.asarray(uv, float)) - np.array([w / 2 - r, h / 2 - r])
    return np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(np.max(q, axis=1), 0) - r


def rr_grid(w, h, r, spacing, edge=0.0):
    """Points `spacing` apart inside the rounded rectangle, at least `edge` from its outline."""
    uu, vv = np.meshgrid(np.arange(-w / 2, w / 2 + 1e-9, spacing), np.arange(-h / 2, h / 2 + 1e-9, spacing))
    q = np.c_[uu.ravel(), vv.ravel()]
    return q[rr_sdf(q, w, h, r) <= -edge]


def depths_along(shape, F, uv, w0=-3.0, last=False):
    """Lines along -n through the points uv of the logo's plane: the depth w (frame_pt) where each first (last: last)
    meets the shape's surface."""
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    from OCP.gp import gp_Lin
    si = IntCurvesFace_ShapeIntersector()
    si.Load(shape.wrapped, 1e-6)
    n = F[1]
    out = []
    for u, v in np.asarray(uv):
        si.Perform(gp_Lin(gp_Pnt(*map(float, frame_pt(F, u, v, w0))), gp_Dir(*map(float, -n))), 0.0, 40.0)
        check(si.NbPnt() > 0, f"logo: nothing along the axis at ({u:.2f}, {v:.2f})")
        ws = [si.WParameter(i) for i in range(1, si.NbPnt() + 1)]
        out.append(w0 + (max(ws) if last else min(ws)))
    return np.array(out)


def floor_normals(band, F, q, d=0.05):
    """Outward unit normals of the band's surface where lines along -n through q meet it (central differences)."""
    q = np.asarray(q, float)
    pt = lambda uv: np.array([frame_pt(F, u, v, w) for (u, v), w in zip(uv, depths_along(band, F, uv))])
    du, dv = np.array([d, 0.0]), np.array([0.0, d])
    N = np.cross(pt(q + du) - pt(q - du), pt(q + dv) - pt(q - dv))
    N /= np.linalg.norm(N, axis=1)[:, None]
    return N * np.sign(N @ F[1])[:, None]


def _polywire(P):
    return Wire.make_polygon([tuple(map(float, x)) for x in P], close=True)


_POCKET = {}


def logo_pocket(S):
    """Round 7b: the stencil pocket, cut from inside. Its floor: the outer surface moved LOGO_SKIN in (the band), inside the
    letters' box + STENCIL_MARGIN (corners STENCIL_R) projected along the logo's normal n (the pocket's axis). Its four
    flanks: from STENCIL_LEDGE behind the floor (a straight strip along the axis) they lean out STENCIL_DEG from the floor's
    own normal until POCKET_OVER past the inner face, then run on straight along the axis into the cavity. The tool is a
    ruled loft through four outlines (front, kink, exit, end; one point per outline point), the pocket the tool inside the
    band, less the seam bosses it would reach (+ POCKET_BOSS_CLR: the front one at x 22.5 lies behind its lower left
    corner). Returns a dict (cached per surfaces): frame, outline, floor depths, flank lines, the cutter, the band."""
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    from OCP.gp import gp_Lin
    if id(S) in _POCKET:
        return _POCKET[id(S)]
    F = logo_axes()
    p, n, xd, up = F
    h = hw.LETTERS_ASPECT * LOGO_W
    pw, ph = LOGO_W + 2 * STENCIL_MARGIN, h + 2 * STENCIL_MARGIN
    q, m = rr_outline(pw, ph, STENCIL_R)
    band = S.band(LOGO_SKIN, SEAM - 2.0, LOGO_ZC + ph / 2 + 12.0)
    s = depths_along(band, F, q)
    kink = s + STENCIL_LEDGE
    # the flanks lean STENCIL_DEG (the top one STENCIL_TOP_DEG) from the floor's own normal (the wall's), outwards: the wall
    # thins as at the pebble's flat floor. Against the axis they lean less where the belly turns away (right): the pocket
    # still widens along it
    N = floor_normals(band, F, q)
    M = m[:, :1] * xd + m[:, 1:] * up
    L = M - np.sum(M * N, 1)[:, None] * N
    L /= np.linalg.norm(L, axis=1)[:, None]
    b_ = np.radians(STENCIL_DEG + (STENCIL_TOP_DEG - STENCIL_DEG) * np.clip(m[:, 1], 0, 1))[:, None]
    dirs = -np.cos(b_) * N + np.sin(b_) * L
    widen = np.sum(dirs * M, 1) / np.sum(dirs * -n, 1)           # lateral out per mm along the axis
    check(widen.min() >= math.tan(math.radians(10.0)), f"logo pocket: a flank leans only {math.degrees(math.atan(widen.min())):.1f} deg "
                                                       "from the axis (the stencil would not go in)")
    O = np.array([frame_pt(F, u, v, k) for (u, v), k in zip(q, kink)])
    si = IntCurvesFace_ShapeIntersector()
    si.Load(S.inner.wrapped, 1e-6)
    ex = []
    for o, d in zip(O, dirs):                              # where each flank line leaves the wall into the cavity
        si.Perform(gp_Lin(gp_Pnt(*map(float, o)), gp_Dir(*map(float, d))), 0.0, 30.0)
        check(si.NbPnt() > 0, "logo pocket: a flank line never reaches the inner face")
        ex.append(min(si.WParameter(i) for i in range(1, si.NbPnt() + 1)))
    ex = np.array(ex)
    E = O + (ex + POCKET_OVER)[:, None] * dirs
    wE = -((E - p) @ n)
    wF = float(wE.max() + 0.3)
    Fe = E - (wF - wE)[:, None] * n
    w_front = float(s.min() - 1.5)
    A = np.array([frame_pt(F, u, v, w_front) for u, v in q])
    tool = Solid.make_loft([_polywire(X) for X in (A, O, E, Fe)], ruled=True)
    check(tool.is_valid and len(tool.solids()) == 1, "logo pocket tool invalid")
    cut = tool & band
    trims = []
    for b_ in boss_spots():                                # the seam bosses near it stay whole (+ POCKET_BOSS_CLR)
        g = zcyl(b_["x"], b_["y"], b_["r_boss"] + POCKET_BOSS_CLR, SEAM - 1.0, SEAM + b_["h"] + POCKET_BOSS_CLR)
        if dist_shapes(g, cut)[0] < 1e-6:
            cut = cut - g
            trims.append((b_["kind"], b_["x_nom"], b_["side"]))
    cut = one_solid(cut, "logo pocket")
    uvE = np.c_[(E - p) @ xd, (E - p) @ up]
    res = dict(F=F, pw=pw, ph=ph, R=STENCIL_R, q=q, m=m, s=s, kink=kink, dirs=dirs, widen=widen, exit=ex, wE=wE, wF=wF, w_front=w_front,
               band=band, inner=S.inner, tool=tool, cut=cut, trims=trims, mouth=(float(uvE[:, 0].min()), float(uvE[:, 0].max()),
                                                    float(uvE[:, 1].min()), float(uvE[:, 1].max())))
    _POCKET[id(S)] = res
    return res


def stencil_block(P, clr=STENCIL_CLR, t_min=STENCIL_T_MIN):
    """The stencil's outline as a solid, seated in the pocket P: the floor's outline less clr all round (R less clr) as a
    straight prism along the axis (the pocket widens along it: the gap grows behind the floor's strip; and its back
    corners stay clear of the boss behind the pocket's lower left corner), its front face the pocket's floor (the band),
    its back one plane across the axis t_min behind the deepest point of the front face. Returns a dict: solid, back
    face, w_back, the front's depth range."""
    F = P["F"]
    p, n, xd, up = F
    w, h, r = P["pw"] - 2 * clr, P["ph"] - 2 * clr, P["R"] - clr
    q, _ = rr_outline(w, h, r, 0.5, 0.2)
    gi = rr_grid(w, h, r, 0.5, 0.02)
    s = depths_along(P["band"], F, np.vstack([q, gi]))
    w_back = float(s.max() + t_min)
    pl = Plane(origin=tuple(frame_pt(F, 0, 0, P["w_front"])), x_dir=tuple(xd), z_dir=tuple(-n))
    st = one_solid(extrude(pl * RectangleRounded(w, h, r), w_back - P["w_front"]) & P["band"], "stencil block")
    back = Plane(origin=tuple(frame_pt(F, 0, 0, w_back)), x_dir=tuple(xd), z_dir=tuple(-n)) * RectangleRounded(w, h, r)
    return dict(solid=st, back=back, w_back=w_back, front=(float(s.min()), float(s.max())), clr=clr, t_min=t_min)


def stencil_parts(P, ST, strips=STENCIL_STRIPS):
    """The stencils, seated: ST's block with the letters cut straight through along the axis, one per web width in strips
    (None: the logo as designed; wider webs shrink the letters by half the difference). Returns [(solid, web)]."""
    from build123d import offset
    F = P["F"]
    p, n, xd, up = F
    s0 = hw.STRIP_PER_MM * LOGO_W
    pl = Plane(origin=tuple(frame_pt(F, 0, 0, P["w_front"] - 1.0)), x_dir=tuple(xd), z_dir=tuple(n))
    out = []
    for s_ in strips:
        s_ = s0 if s_ is None else s_
        check(s_ >= s0 - 1e-9, f"stencil web {s_} narrower than the logo's {s0:.2f}")
        st = ST["solid"]
        for poly in hw.letters_mm(LOGO_W):
            hole = Polygon(*[(u, v) for u, v in poly], align=None)
            if s_ > s0 + 1e-9:
                hole = offset(hole, -(s_ - s0) / 2)
            st = st - extrude(pl * hole, ST["w_back"] - P["w_front"] + 3.0, dir=tuple(-n))
        out.append((one_solid(st, f"stencil {s_:.2f}"), s_))
    return out


def stencil_print(P, ST, parts):
    """The stencils turned for printing: the back (the wide, flat face) on the bed at z 0, the front (the floor's curve)
    up; in the logo's frame (x reading direction, y up the face: seen from above as from outside), one row each. The
    apertures are checked against the letters (built here from hw.letters_mm, independently of the cutters): one per
    letter on the bed face, its area and centroid at (u, v) (not mirrored: from above the logo reads as from outside).
    Returns (Compound, [hole areas per stencil])."""
    from build123d import offset, CenterOf
    F = P["F"]
    p, n, xd, up = F
    pl = Plane(origin=tuple(frame_pt(F, 0, 0, ST["w_back"])), x_dir=tuple(xd), z_dir=tuple(n))
    s0 = hw.STRIP_PER_MM * LOGO_W
    out, areas = [], []
    for i, (st, s_) in enumerate(parts):
        loc = pl.to_local_coords(st)
        bb = loc.bounding_box()
        check(abs(bb.min.Z) < 1e-4, f"stencil {s_:.2f}: its back is not on the bed ({bb.min.Z:.4f})")
        want = []
        for poly in hw.letters_mm(LOGO_W):
            qq = Polygon(*[(u, v) for u, v in poly], align=None)
            if s_ > s0 + 1e-9:
                qq = offset(qq, -(s_ - s0) / 2)
            c = qq.center(CenterOf.MASS)
            want.append((qq.area, c.X, c.Y))
        fs = [f for f in loc.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6 and abs(f.center().Z) < 1e-4]
        check(len(fs) == 1, f"stencil {s_:.2f}: {len(fs)} bed faces")
        got = [(Face(wr).area, Face(wr).center(CenterOf.MASS)) for wr in fs[0].inner_wires()]
        check(len(got) == len(want), f"stencil {s_:.2f}: {len(got)} apertures on the bed face, the logo has {len(want)} letters")
        for a, x, y in want:
            hit = [g for g in got if abs(g[0] - a) < 1e-3 * a and abs(g[1].X - x) < 1e-3 and abs(g[1].Y - y) < 1e-3]
            check(len(hit) == 1, f"stencil {s_:.2f}: no aperture of {a:.3f} mm2 at ({x:.3f}, {y:.3f}) (the letters missing, "
                                 f"misplaced, the wrong size or mirrored)")
        check(want[0][1] < want[1][1], "stencil: the letters' order (E left of H, from outside) is not the logo's")
        out.append(Pos(0, -i * (P["ph"] + 6.0), 0) * loc)
        areas.append([a for a, _, _ in want])
    return Compound(out), areas


def stencil_frame(P, ST, strip=None):
    """Web left round the letters at the stencil's front (its narrowest outline), at least; and between the letters."""
    s0 = hw.STRIP_PER_MM * LOGO_W
    s_ = s0 if strip is None else strip
    c = ST["clr"]
    pts = []
    for poly in hw.letters_mm(LOGO_W):
        P_ = np.asarray(poly)
        for a, b in zip(P_, np.roll(P_, -1, 0)):
            for t in np.linspace(0, 1, max(2, int(np.linalg.norm(b - a) / 0.02)), endpoint=False):
                pts.append(a + t * (b - a))
    d = -rr_sdf(np.array(pts), P["pw"] - 2 * c, P["ph"] - 2 * c, P["R"] - c)
    return float(d.min() + (s_ - s0) / 2)


def slot_land_measure(part):
    """The slots measured on sections of the body's front in the board frame (planes z, SLOT_SECTIONS along each slot, 0.3
    inside its ends): at depths LAND_DY apart from the inner land (Y_LAND) towards the face, the slot's two walls (the
    section's crossings nearest the slot's axis). The land on each side runs as far as its wall stays within LAND_TOL of where
    it meets the inner face; the lip: the walls' largest distance from the designed profile (lip_x) over all depths. Per slot:
    width at the inner face (least, most), land depth (least, most), the opening at the last depth (0.005 behind the face),
    the lip's deviation."""
    part = tb(part) & box(TUBE_X[0] - 9.5, TUBE_X[1] + 9.5, FACE_Y - 1.5, Y_LAND + 1.5, SLOT_Z[0] - 1, SLOT_Z[1] + 1)
    ys = Y_LAND - LAND_DY / 2 - LAND_DY * np.arange(int(round(FRONT_T / LAND_DY)))
    want = np.array([lip_x(Y_LAND - y) for y in ys])
    out = []
    for x0 in TUBE_X:
        w, depth, face, dev = [], [], [], []
        for zs in np.linspace(SLOT_Z[0] + 0.3, SLOT_Z[1] - 0.3, SLOT_SECTIONS):
            seg = sm.section_segments(part, float(zs), bbox=(x0 - 9, x0 + 9, FACE_Y - 1, Y_LAND + 1), step=0.02)
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
            dev.append(float(max(np.abs(x0 - walls[:, 0] - want).max(), np.abs(walls[:, 1] - x0 - want).max())))
            for j in (0, 1):
                off = np.abs(walls[:, j] - walls[0, j]) > LAND_TOL
                depth.append((int(np.argmax(off)) if off.any() else len(ys)) * LAND_DY)
        out.append(dict(x=x0, w=min(w), w_max=max(w), depth=min(depth), depth_max=max(depth), face=min(face), n=len(w),
                        lip_dev=max(dev), face_want=2 * want[-1], face_depth=float(Y_LAND - ys[-1])))
    return out


LIP_TOL = 0.03                                          # the slot's walls off the designed profile (land + lip), at most


def slot_land_check(part):
    """The slots' land and lips on the body (or a faulty front blank from the harness), against the design values."""
    SL = slot_land_measure(part)
    for q in SL:          # depth resolution LAND_DY: the land reads 0.60 when it is 0.60..0.61 deep
        check(abs(q["w"] - SLOT_W) < 1e-3 and abs(q["w_max"] - SLOT_W) < 1e-3 and abs(q["depth"] - RIM) < LAND_DY + 1e-6
              and abs(q["depth_max"] - RIM) < LAND_DY + 1e-6,
              f"slot at x {q['x']:+.2f}: land at the inner face {q['w']:.3f}..{q['w_max']:.3f} wide, {q['depth']:.3f}..{q['depth_max']:.3f} deep")
        check(q["lip_dev"] <= LIP_TOL, f"slot at x {q['x']:+.2f}: the walls leave the designed land + lip by {q['lip_dev']:.3f}")
        check(abs(q["face"] - q["face_want"]) < 0.05, f"slot at x {q['x']:+.2f}: opening {q['face_depth']:.3f} in front of the land "
              f"{q['face']:.3f}, designed {q['face_want']:.3f}")
    check(SLOT_W - hw.ROD_W >= ROD_PLAY_MIN - 1e-9, f"slot {SLOT_W} over the rod {hw.ROD_W}: < {ROD_PLAY_MIN}")
    return SL


def _ray_hits(shape, o, d, tmax=40.0):
    """Parameters along the ray o + t d (unit d) where it crosses the shape's faces, sorted."""
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    from OCP.gp import gp_Lin
    si = IntCurvesFace_ShapeIntersector()
    si.Load(shape.wrapped, 1e-6)
    si.Perform(gp_Lin(gp_Pnt(*map(float, o)), gp_Dir(*map(float, d))), -tmax, tmax)
    w = sorted(si.WParameter(i) for i in range(1, si.NbPnt() + 1))
    return [v for i, v in enumerate(w) if i == 0 or v - w[i - 1] > 1e-5]      # a ray through an edge hits both faces


def slot_edge_points(step=0.5, out=0.1):
    """Points on the face just outside both slots' openings (`out` beyond the edge), board frame: along the long sides and
    across the ends; (x, z, which edge)."""
    pts = []
    z0, z1 = SLOT_Z
    for x0 in TUBE_X:
        h = FACE_OPEN / 2
        for z in np.arange(z0, z1 + 1e-9, step):
            pts += [(x0 - h - out, z, "left"), (x0 + h + out, z, "right")]
        for x in np.arange(x0 - h, x0 + h + 1e-9, step / 2):
            pts += [(x, z0 - out, "bottom end"), (x, z1 + out, "top end")]
    return pts


def front_thickness_check(part, tol=FRONT_T_TOL):
    """The front's thickness at the slots' edges, measured on the solid in the board frame: a ray along the face's normal
    just outside each opening's edge, from the outer face (first crossing) to the inner face (the next): FRONT_T -+ tol
    everywhere (the rods' crowns stand proud of the face along both slots' whole length and width by the same amount), and
    where the face lies."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN
    part = tb(part) & box(TUBE_X[0] - 9.5, TUBE_X[1] + 9.5, FACE_Y - 3, Y_LAND + 3, SLOT_Z[0] - 3, SLOT_Z[1] + 3)
    th, face, bad = [], [], []
    for x, z, kind in slot_edge_points():
        w = _ray_hits(part, (x, FACE_Y - 5.0, z), (0, 1, 0), 15.0)
        check(len(w) >= 2, f"front at x {x:.2f}, z {z:.2f}: the ray crosses {len(w)} faces")
        mid = FACE_Y - 5.0 + (w[0] + w[1]) / 2
        c = BRepClass3d_SolidClassifier(part.wrapped, gp_Pnt(float(x), float(mid), float(z)), 1e-6)
        check(c.State() == TopAbs_IN, f"front at x {x:.2f}, z {z:.2f}: no material between the first two crossings")
        t = w[1] - w[0]
        th.append(t)
        face.append(FACE_Y - 5.0 + w[0])
        if abs(t - FRONT_T) > tol:
            bad.append((round(x, 2), round(z, 2), kind, round(t, 3)))
    check(not bad, f"front not {FRONT_T} -+ {tol} at {len(bad)} slot-edge points, e.g. {bad[:4]}")
    return dict(n=len(th), lo=float(min(th)), hi=float(max(th)), face=(float(min(face)), float(max(face))))


# ---- cups and ballast ------------------------------------------------------------------------------------------------
def terrace_section(zf):
    """The inner section at a floor (round 6's surface: the cups), shrunk CAV_IN more in plan (along the section's own
    normals)."""
    sec = SH8.offset_rows(WALL, [zf])[0]
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


def cast_dimple(S, cast_to):
    """The cast's dimple under the USB head's far end (world): the head's box grown by HEAD_CLR and run 12 up (turned with
    the board), below the cast's top, inside the inner surface. None if the head stays HEAD_CLR over the cast anyway."""
    if HEAD_LOW - HEAD_CLR >= cast_to - 1e-9:
        return None
    g = HEAD_CLR
    hd = tw(box(HEAD_X - HEAD_W / 2 - g, HEAD_X + HEAD_W / 2 + g, HEAD_Y0 - g, HEAD_Y1 + g, HEAD_Z0 - g, HEAD_Z1 + 12))
    return one_solid(hd & box(-100, 100, -100, 100, -5, cast_to) & S.inner, "cast dimple")


def cast_plug(dimple, cast_to):
    """The printed plug that makes the dimple: set into the last batch of the cast (taped or greased), pulled out when it has
    cured. The dimple plus a 5 x 5 handle 6 high over its middle."""
    bb = dimple.bounding_box()
    cx, cy = (bb.min.X + bb.max.X) / 2, (bb.min.Y + bb.max.Y) / 2
    return one_solid(dimple + box(cx - 2.5, cx + 2.5, cy - 2.5, cy + 2.5, cast_to - 0.3, cast_to + 6.0), "cast plug")


def make_cup(S, layers, cast_to=None, kind="rock"):
    """The rocking cup (down to the pole). layers: the terrace floors to cut. cast_to: the bowl is open (the inner surface)
    up to this level, for a level cast of steel shot in epoxy; the terraces start there."""
    c = one_solid(S.cup_outer(), f"cup-{kind} blank")
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
    for (x0, x1, y0, y1, z0, z1) in (HEAD_BB, (HEAD_X - r, HEAD_X + r, CABLE_Y0 - 0.5, 60.0, CABLE_Z - r, CABLE_Z + r)):
        if zf + SEG[2] > z0 - HEAD_CLR and zf < z1 + HEAD_CLR:
            free &= ~((XX >= x0 - HEAD_CLR) & (XX <= x1 + HEAD_CLR) & (YY >= y0 - HEAD_CLR) & (YY <= y1 + HEAD_CLR))
    return free


def band_free_designed(zf, bosses):
    """Free region of a band (designed): the inner section at the floor, minus the bosses reaching into the band."""
    from matplotlib.path import Path as MPath
    sec = terrace_section(zf)[:, :2]
    f, xs, ys = free_mask([sec], -45, 45, -30, 32, cavity=True)
    lo, hi = SH8.offset_range(WALL)
    for z in (zf + SEG[2] / 2, zf + SEG[2] - 0.05):        # the terrace is cut by the inner surface too (the alcove's flare
        if lo < z < hi:                                     # pulls it back at the front near the seam)
            f &= free_mask([SH8.offset_rows(WALL, [z])[0][:, :2]], -45, 45, -30, 32, cavity=True)[0]
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
        m, xs, ys = free_mask(loops, -45, 45, -30, 32, outline=SH8.offset_rows(0.0, [zf + dz], outer=True)[0][:, :2])
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
    """The seated board (world): board_bodies_b turned with the tilt."""
    return {n: tw(v) for n, v in board_bodies_b().items()}


def board_bodies_b():
    """Seated board as boxes in the board frame: glass, PCB stack, buttons, plugs."""
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
    return {n: tw(v) for n, v in rod_solids_b().items()}


def rod_solids_b():
    """The rods (8 x 4 half-rounds through the slots), board frame."""
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
    return tw(box(x - BAT_L / 2, x + BAT_L / 2, BAT_Y0, BAT_Y1, BAT_Z0, BAT_Z0 + BAT_HT))


def usb_solids(dz=0.0, dx=0.0):
    """The extension seated in the port (dz, dx: shifted in the world, for the fault injection): its head (turned with the
    board), and its cable straight back (horizontal) from the far end's centre (0.5 inside the head) to 3 mm outside the back
    surface."""
    head = tw(box(HEAD_X - HEAD_W / 2, HEAD_X + HEAD_W / 2, HEAD_Y0, HEAD_Y1, HEAD_Z0, HEAD_Z1))
    return {"usb-head": Pos(dx, 0, dz) * head,
            "usb-cable": ycyl(HEAD_X + dx, CABLE_Z + dz, CABLE_D / 2, CABLE_Y0 - 0.5, Y_BACK_OUT + 3.0)}


def cable_hole(cup=False, r=None):
    """The round passage (CABLE_HOLE_D) round the cable through the back wall, from CABLE_HOLE_FROM behind the head's far end;
    the cup's part runs straight up to the rim (open upward). r: another radius (the checks' passage)."""
    r = CABLE_HOLE_D / 2 if r is None else r
    h = ycyl(HEAD_X, CABLE_Z, r, CABLE_Y0 + CABLE_HOLE_FROM, Y_BACK_OUT + 5.0)
    if cup:
        h = h + box(HEAD_X - r, HEAD_X + r, CABLE_Y0 + CABLE_HOLE_FROM, Y_BACK_OUT + 5.0, CABLE_Z, SEAM + 1.0)
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


STENCIL_MASS = {}                                      # the seated logo stencil (as designed), set by build(): with the body


def tilted(p):
    """Mass properties given in the board frame, turned into the world."""
    c = pts_world(np.asarray(p["c"], float)[None])[0]
    return dict(p, c=c, I=R_TILT @ p["I"] @ R_TILT.T)


def mass_parts(meshes, segs, extra=(), m_board=M_BOARD, m_bat=M_BAT):
    """Mass model: printed parts (and the cast) from the exported meshes, the rest as boxes (weighed masses); board,
    battery and rods in the board frame, turned with the tilt. Plus the logo stencil (in the body)."""
    parts = [dict(meshes[n], name=n) for n in meshes] + [dict(e) for e in extra]
    if "body" in meshes and STENCIL_MASS:
        parts.append(dict(STENCIL_MASS, name="logo stencil"))
    lo = (XOFF - hw.PCB_W / 2, Y_GLASS0, PCB_Z0)
    parts.append(dict(tilted(box_props(m_board, lo, (XOFF + hw.PCB_W / 2, Y_BOARD1, PCB_Z1))), name="board"))
    b = (BAT_X - BAT_L / 2, BAT_Y0, BAT_Z0, BAT_X + BAT_L / 2, BAT_Y1, BAT_Z0 + BAT_HT)
    parts.append(dict(tilted(box_props(m_bat, b[:3], b[3:])), name="battery"))
    rod_m = 1.19 * (math.pi * (hw.ROD_W / 2) ** 2 / 2 * ROD_L) / 1000
    for x in TUBE_X:
        parts.append(dict(tilted(box_props(rod_m, (x - 4, Y_GLASS0 - 4, AA_ZC - ROD_L / 2), (x + 4, Y_GLASS0, AA_ZC + ROD_L / 2))), name="rod"))
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


SPOTS = {}                                             # nominal x -> placed spot (place_spots: solid, centroid, rotation, z0)


def spot_geom(x, z0, clr=0.02):
    """A trim spot (SEG: 12 across, 4 thick, 19 tall) standing on the back inner wall with its centre column at x and its
    bottom at z0: turned about z so its back is parallel to the wall's chord there, moved off the wall until its whole back
    face lies inside the inner sections (designed, round 7's surface) + clr: on a wall curved in plan it rests on its two
    vertical edges. Returns dict(solid, c (centroid), R (columns: across, out of the wall, up), z0, sag (gap at its middle))."""
    from matplotlib.path import Path as MPath
    zs = list(np.linspace(z0, z0 + SEG[1], 5))
    secs = SH8.offset_rows(WALL, zs)
    mid = secs[2][:, :2]
    back = mid[mid[:, 1] > 0]
    back = back[np.argsort(back[:, 0])]
    yb = lambda xx: float(np.interp(xx, back[:, 0], back[:, 1]))
    t = np.array([SEG[0], yb(x + SEG[0] / 2) - yb(x - SEG[0] / 2)])
    t /= np.linalg.norm(t)
    n = np.array([t[1], -t[0]])                         # off the wall, towards the front
    p0 = np.array([x, yb(x)])
    paths = [MPath(q[:, :2]) for q in secs]
    us = np.linspace(-SEG[0] / 2, SEG[0] / 2, 49)

    def inside(sv):
        pts = p0 + us[:, None] * t + sv * n
        return all(pth.contains_points(pts, radius=-1e-9).all() for pth in paths)
    lo, hi = -2.0, 8.0
    check(inside(hi), f"trim spot at x {x}: no room off the wall")
    for _ in range(40):
        m_ = (lo + hi) / 2
        lo, hi = (lo, m_) if inside(m_) else (m_, hi)
    sv = hi + clr
    c2 = p0 + (sv + SEG[2] / 2) * n
    c = np.array([c2[0], c2[1], z0 + SEG[1] / 2])
    solid = Plane(origin=tuple(map(float, c)), x_dir=(float(t[0]), float(t[1]), 0.0), z_dir=(0, 0, 1)) * Box(SEG[0], SEG[2], SEG[1])
    R = np.array([[t[0], -n[0], 0.0], [t[1], -n[1], 0.0], [0.0, 0.0, 1.0]])
    return dict(solid=solid, c=c, R=R, z0=float(z0), sag=float(sv), x=x)


def place_spots(body):
    """Each trim spot at the lowest bottom (0.5 steps from TRIM_SPOT_Z_LO) where it clears the body on the solid (the seam
    bosses, the notch) and the spots placed before it (+ SEG_GAP)."""
    SPOTS.clear()
    for x in TRIM_SPOTS:
        free = lambda g: overlap(g["solid"], body) < EPS_V and all(dist_shapes(g["solid"], q["solid"])[0] >= SEG_GAP for q in SPOTS.values())
        for z0 in np.arange(TRIM_SPOT_Z_LO, 70.0, 0.5):
            g = spot_geom(x, float(z0))
            if free(g):
                break
        check(free(g), f"trim spot at x {x}: no place on the back wall")
        SPOTS[x] = g
    return SPOTS


def trim_spot_check(body, bat, spots=None):
    """The trim spots against the body (no overlap, resting on the wall: within 0.1), the battery seated and on its way in
    (TRIM_SPOT_BAT), the USB head and cable (HEAD_CLR), the board's way in (BOARD_SWEEP_MIN) and each other."""
    spots = spots or {x: SPOTS[x]["solid"] for x in TRIM_SPOTS}
    out = {}
    usb = usb_solids()
    for x, sp in spots.items():
        g_body = clear(sp, body, f"trim spot x {x}", 0.0, touch_ok=True)
        check(g_body <= 0.1, f"trim spot x {x}: {g_body:.3f} off the wall (not resting on it)")
        g_bat = min([clear(sp, bat, f"trim spot x {x} to the battery", TRIM_SPOT_BAT)] +
                    [clear(sp, sw, f"trim spot x {x} to the battery's way in ({n})", TRIM_SPOT_BAT) for n, sw in battery_sweeps().items()])
        g_usb = min(clear(sp, u_, f"trim spot x {x} to the {n}", HEAD_CLR) for n, u_ in usb.items())
        g_brd = min(clear(sp, sw, f"trim spot x {x} to the board's way in", BOARD_SWEEP_MIN) for sw in board_sweeps().values())
        out[x] = dict(body=g_body, bat=g_bat, usb=g_usb, board=g_brd)
        if x in SPOTS:
            g = SPOTS[x]
            out[x].update(z0=g["z0"], sag=g["sag"], c=[float(v) for v in g["c"]], turn=math.degrees(math.atan2(g["R"][1, 0], g["R"][0, 0])))
    xs = list(spots)
    for i in range(len(xs)):
        for j in range(i):
            check(overlap(spots[xs[i]], spots[xs[j]]) < EPS_V, f"trim spots x {xs[i]} and {xs[j]} overlap")
    return out


def spot_box(x):
    return SPOTS[x]["solid"]


def spot_part(x):
    g = SPOTS[x]
    p = box_props(SEG_G, (0, 0, 0), (SEG[0], SEG[2], SEG[1]))
    return dict(m=SEG_G, c=g["c"], I=g["R"] @ p["I"] @ g["R"].T, name="trim spot")


def trim_plan(cells, runs, Mx_fixed, M_fixed, best_effort=False):
    """Plumb: the fewest trim spots (segments on the back wall, right), then the fewest trim-layer segments left out
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
        return (Mx_fixed + SEG_G * (sum(c[0] for c in kept) + sum(float(SPOTS[x]["c"][0]) for x in spots))) / M

    auth = (gx(layout(set(), 0.0), []), gx(layout(set(), 1.0), []))
    for e in range(len(TRIM_SPOTS) + 1):
        spots = list(TRIM_SPOTS[:e])
        for k in range(len(cells)):
            # leave out the leftmost k (towards plumb from the left), or (round 8: three spots overshoot by 0.01) the rightmost
            for removed in (set(order[:k]), set(order[len(order) - k:]) if k else set()):
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
    """The whole clock's outer surface with keel exponent nc."""
    old = P["NC"]
    P["NC"] = nc
    try:
        return SH8.grid(np.asarray(zs))
    finally:
        P["NC"] = old


# ---- surface-level study (ROLY_TILT=6 / 8 / 10 ... --surface): grid mass model, side silhouette -------------------------
def _poly_props(P_):
    x, y = P_[:, 0], P_[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cr = x * y1 - x1 * y
    A = cr.sum() / 2
    return A, ((x + x1) * cr).sum() / (6 * A), ((y + y1) * cr).sum() / (6 * A)


def _slices(G, zq):
    """A (rows x cols x 3) grid re-sliced at the levels zq (per column; columns made monotone)."""
    Z = np.maximum.accumulate(G[:, :, 2], axis=0) + np.arange(len(G))[:, None] * 1e-9
    return [np.c_[[np.interp(z, Z[:, j], G[:, j, 0]) for j in range(G.shape[1])],
                  [np.interp(z, Z[:, j], G[:, j, 1]) for j in range(G.shape[1])]] for z in zq]


def _solid(G, zq, rho):
    pr = np.array([_poly_props(q) for q in _slices(G, zq)])
    m = np.abs(pr[:, 0]) * np.gradient(zq) * rho / 1000
    return dict(m=float(m.sum()), c=np.array([(m * pr[:, 1]).sum(), (m * pr[:, 2]).sum(), (m * zq).sum()]) / m.sum(), I=np.zeros((3, 3)))


def grid_model(sh=None):
    """The mass model on the surface function alone [est]: shell = outer grid minus its WALL offset (slices every 0.25),
    cast = the offset below CUP_ROCK_CAST_TO; board, battery, rods, misc as in mass_parts; the trim as 15 g at (5, 6, 25)
    (round 7's nominal plan, roughly); no bosses, land, logo. Fore-aft limits from the outer grid's support function.
    Nominal and bad case. Biased against the full model (round 7: margin -0.44, forward -0.58): compare tilts with it."""
    sh = sh or SH8
    G = sh.G_OUT
    zq = np.arange(0.05, H - 0.05, 0.25)
    GI = G - WALL * sh.N_OUT
    zi = zq[(zq > GI[0, :, 2].max() + 0.05) & (zq < GI[-1, :, 2].min() - 0.05)]
    out = _solid(G, zq, RHO_PLA)
    inn = _solid(GI, zi, RHO_PLA)
    shell = dict(m=out["m"] - inn["m"], c=(out["m"] * out["c"] - inn["m"] * inn["c"]) / (out["m"] - inn["m"]), I=np.zeros((3, 3)))
    pts = G.reshape(-1, 3)
    R = dict(shell=shell["m"])
    for cn, (mb, mt, rho) in (("nominal", (M_BOARD, M_BAT, RHO_CAST)), ("bad", (BAD["M_BOARD"], BAD["M_BAT"], BAD["RHO_CAST"]))):
        cast = _solid(GI, zi[zi < CUP_ROCK_CAST_TO], rho)
        parts = mass_parts({}, [], extra=[shell, cast, dict(m=15.0, c=np.array([5.0, 6.0, 25.0]), I=np.zeros((3, 3)))], m_board=mb, m_bat=mt)
        M, Gc, _ = combine(parts)
        rest, fwd, back = pitch_limits(pts, Gc)
        R[cn] = dict(M=float(M), G=[float(v) for v in Gc], margin=float(RR - Gc[2]), fwd=fwd, back=back, rest=rest, cast=cast["m"])
    return R


def silhouette(sh=None, n=600):
    """The side silhouette (the outer surface's least and largest y per height) and the centre line's front profile."""
    sh = sh or SH8
    zs = np.r_[np.linspace(ZB0, 6, 60), np.linspace(6.2, ZB1, n)]
    th = np.linspace(0, 2 * np.pi, 720, endpoint=False)
    Y = np.array([sh.xyz(th, np.full_like(th, z))[1] for z in zs])
    return dict(z=zs.tolist(), front=Y.min(1).tolist(), back=Y.max(1).tolist(), centre=front_line(zs)[0].tolist())


def head_room(sh=None):
    """The cavity above the board's highest point (world z): its volume (cm3, inner grid slices) and height."""
    sh = sh or SH8
    zt = float(pts_world(np.array([[0.0, Y_GLASS0, PCB_Z1], [0.0, Y_BOARD1, PCB_Z1]]))[:, 2].max())
    GI = sh.G_OUT - WALL * sh.N_OUT
    top = float(GI[-1, :, 2].min()) - 0.05
    zq = np.arange(zt, top, 0.25)
    v = _solid(GI, zq, 1000.0)["m"] / 1000 if len(zq) > 2 else 0.0
    return dict(z=zt, v=float(v), h=float(top - zt))


def surface_study():
    """--surface: this TILT's surface-level numbers into out-rolypoly/surface-tilt<T>.json (for the report's tilt table and
    the silhouette view)."""
    OUT.mkdir(exist_ok=True)
    fc = front_check()
    gm = grid_model()
    d = dict(tilt=TILT, lift=LIFT, pcb_z0=PCB_Z0, Z_B=Z_B, Z_T=Z_T, shear=HEAD_SHEAR, front=fc, grid=gm, sil=silhouette(), head=head_room(),
             face=dict(z=[Z_B, Z_T], y=[float(y_face(Z_B)), float(y_face(Z_T))]), board_top=[float(v) for v in to_world(Y_BOARD1, PCB_Z1)])
    (OUT / f"surface-tilt{TILT:g}.json").write_text(json.dumps(d, indent=1, default=float))
    print(f"tilt {TILT:g}: lift {LIFT:.2f}, plane z {Z_B:.2f}..{Z_T:.2f}, " + ", ".join(
        f"{cn}: margin {gm[cn]['margin']:.2f}, fwd {gm[cn]['fwd']:.2f}, back {gm[cn]['back']:.2f}, {gm[cn]['M']:.0f} g" for cn in ("nominal", "bad")) +
        f"; front: min radius {fc['r_min']:.2f} at {fc['r_at']}, seam slope {fc['seam_deg']:.1f} deg", flush=True)
    return d


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


def logo_outside(S, x=None, polys=None):
    """Outside: the letters' footprint (polys: other outlines in the logo's plane, e.g. the stencil pocket's floor) on the
    outer surface (outline points projected along the logo's direction): its smallest distance (x) right of the front's flat
    (where the curve begins; > 0 = on the curve), its x span, and how far the surface turns from the front (-y) at its left
    end, centre and right end (deg)."""
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
        for poly in (hw.letters_mm(LOGO_W) if polys is None else polys):
            for u_, v_ in np.asarray(poly):
                o = p + u_ * xd + v_ * up + 3.0 * n
                si.Perform(gp_Lin(gp_Pnt(*map(float, o)), gp_Dir(*map(float, -n))), 0.0, 40.0)
                check(si.NbPnt() > 0, "logo outline misses the surface")
                w = min(si.WParameter(i) for i in range(1, si.NbPnt() + 1))
                hits.append(o - w * n)
        hits = np.array(hits)
        clr = float(min(h[0] - flat_limits(h[2])[1] for h in hits))

        def turn(xx):
            k = int(np.argmin(np.abs(DENSE_Z - LOGO_ZC)))
            g, nn = SH8.G_OUT[k], SH8.N_OUT[k]
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


def pocket_outline_check(body, P, off=0.1):
    """The floor's outline, on the body: just behind the floor (0.05) points `off` inside the designed outline are pocket
    (void), and points `off` outside it (0.06 behind the floor's depth at the outline: in front of the flanks' kink) are
    wall (material), all round. Returns the counts."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN, TopAbs_OUT
    F, q, m = P["F"], P["q"], P["m"]
    qi, qo = q - off * m, q + off * m
    bad = []
    for kind, Q, W, want in (("inside", qi, depths_along(P["band"], F, qi) + 0.05, TopAbs_OUT),
                             ("outside", qo, P["s"] + 0.06, TopAbs_IN)):
        for (u, v), w in zip(Q, W):
            c = BRepClass3d_SolidClassifier(body.wrapped, gp_Pnt(*map(float, frame_pt(F, u, v, w))), 1e-6)
            if c.State() != want:
                bad.append((kind, round(float(u), 2), round(float(v), 2)))
    check(not bad, f"logo pocket: its floor's outline moved: {len(bad)} points, e.g. {bad[:4]}")
    return dict(n=2 * len(q), off=off)


def boss_holes():
    """The seam holes as (x, y, r, z top), for the logo pocket's checks."""
    return [(s["x"], s["y"], SEAM_R_HOLE if s["kind"] == "mag" else PIN_R_BODY,
             SEAM + (SEAM_MAG_H + MAG_CLR_H if s["kind"] == "mag" else PIN_DEPTH)) for s in boss_spots()]


def logo_roof_check(P, path, slope_tol=1.0):
    """On the exported body, printed rim-down: faces round the logo pocket (its mouth's extent, from 0.3 behind the logo's
    tangent plane into the cavity; not the seam face on the bed nor the seam holes) that look down more steeply than 45
    deg (+ slope_tol) lie within LOGO_LEDGE of the skin (along the logo's normal to the floor's surface). Returns the
    largest such distance and the steepest downward slope found further in (the top flank)."""
    import pyvista as pv
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    from OCP.gp import gp_Lin
    p, n, xd, up = P["F"]
    m = pv.read(str(path)).compute_normals(cell_normals=True, point_normals=False, auto_orient_normals=False)
    c = m.cell_centers().points
    nn = m.cell_data["Normals"]
    d = c - p
    u, v, w = d @ xd, d @ up, -(d @ n)
    u0, u1, v0, v1 = P["mouth"]
    reg = (u > u0 - 0.5) & (u < u1 + 0.5) & (v > v0 - 0.5) & (v < v1 + 0.5) & (w > 0.3) & (w < P["wF"] + 1.0) & (c[:, 2] > SEAM + 0.05)
    for x, y, r, z1 in boss_holes():
        reg &= ~((np.hypot(c[:, 0] - x, c[:, 1] - y) < r + 0.1) & (c[:, 2] < z1 + 0.1))
    lim = -math.sin(math.radians(45 + slope_tol))
    steep = reg & (nn[:, 2] < lim)
    si = IntCurvesFace_ShapeIntersector()
    si.Load(P["band"].wrapped, 1e-6)
    far = 0.0
    for q in c[steep]:
        si.Perform(gp_Lin(gp_Pnt(*map(float, q)), gp_Dir(*map(float, n))), -5.0, 20.0)
        if si.NbPnt():
            far = max(far, min(abs(si.WParameter(i)) for i in range(1, si.NbPnt() + 1)))
        else:
            far = max(far, 20.0)
    down = reg & ~steep & (nn[:, 2] < -0.5)
    slope = float(np.degrees(np.arcsin(-nn[down, 2])).max()) if down.any() else 0.0
    check(far <= LOGO_LEDGE, f"logo pocket: a face steeper than 45 deg reaches {far:.2f} behind the skin (> {LOGO_LEDGE})")
    return dict(n_steep=int(steep.sum()), far=far, n_roof=int(down.sum()), steepest=slope, n=int(reg.sum()))


def pocket_floor_check(body, P, outer_face, spacing=0.4, edge=0.3):
    """Rays along the logo's axis through a grid on the pocket's floor (at least `edge` inside its outline): the first
    face is the outside, the second the floor: the skin there is the floor point's distance to the outer surface (its
    normal thickness); behind the floor the ray runs free (open to the cavity) LOGO_OPEN at least over LOGO_OPEN_MIN of
    the floor. Returns the count, the skin's range, the floor's depth range along the axis, the open share."""
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    from OCP.gp import gp_Lin
    from build123d import Vertex
    F = P["F"]
    n = F[1]
    g = rr_grid(P["pw"], P["ph"], P["R"], spacing, edge)
    check(len(g) >= 200, f"logo pocket floor: only {len(g)} sample points")
    si = IntCurvesFace_ShapeIntersector()
    si.Load(body.wrapped, 1e-6)
    res = []
    for u_, v_ in g:
        o = frame_pt(F, u_, v_, -3.0)
        si.Perform(gp_Lin(gp_Pnt(*map(float, o)), gp_Dir(*map(float, -n))), 0.0, 60.0)
        w = sorted(si.WParameter(i) for i in range(1, si.NbPnt() + 1))
        check(len(w) >= 2, f"logo pocket floor at ({u_:.1f}, {v_:.1f}): the ray crosses {len(w)} faces")
        f = o - w[1] * n
        thick = dist_shapes(Vertex(*map(float, f)), outer_face)[0]
        res.append((thick, w[1] - 3.0, (w[2] - w[1]) if len(w) > 2 else 60.0))
    r_ = np.array(res)
    out = dict(n=len(r_), lo=float(r_[:, 0].min()), hi=float(r_[:, 0].max()), depth=(float(r_[:, 1].min()), float(r_[:, 1].max())),
               open=float(np.mean(r_[:, 2] >= LOGO_OPEN)))
    check(SKIN_RANGE[0] <= out["lo"] and out["hi"] <= SKIN_RANGE[1], f"logo skin {out['lo']:.3f}..{out['hi']:.3f} outside {SKIN_RANGE}")
    check(out["open"] >= LOGO_OPEN_MIN, f"logo pocket: only {out['open'] * 100:.0f} % of the floor open to the cavity")
    return out


def pocket_clear_check(P):
    """The pocket's cutter against the body's other features nearby: the seam holes and bosses, the inner land, the slots."""
    from build123d import Vertex
    cut = P["cut"]
    g = dict(holes=min(dist_shapes(cut, zcyl(x, y, r, SEAM, z1))[0] for x, y, r, z1 in boss_holes()),
             bosses=min(dist_shapes(cut, zcyl(s["x"], s["y"], s["r_boss"], SEAM, SEAM + s["h"]))[0] for s in boss_spots()),
             land=dist_shapes(cut, land_fill())[0], slots=min(dist_shapes(cut, slot_cutter(x))[0] for x in TUBE_X),
             seam=cut.bounding_box().min.Z - SEAM)
    check(g["holes"] >= MEAT_MIN and g["land"] > 0.5 and g["slots"] > 1.0,
          f"logo pocket: {g['holes']:.2f} from a seam hole, {g['land']:.2f} from the inner land, {g['slots']:.2f} from a slot")
    return g


def stencil_check(body, P, ST, others):
    """The stencil (its outline: the letters only take material away) against the body, seated (lying on the floor) and
    on its way in: pushed from STENCIL_SWEEP inside along the axis onto the floor (a prism along the axis: its silhouette is its
    back face); the gap to the pocket's flanks (not to the floor it lies on); seated, clear
    of `others` (what goes in after it, seated and on its way in: STENCIL_GAP_MIN, the LEDs' room STENCIL_LED_MIN); how
    far its flat back stands proud of the curved inner face. Returns the numbers."""
    n = P["F"][1]
    st = ST["solid"]
    sweep = st + extrude(Face(ST["back"].faces()[0].wrapped), STENCIL_SWEEP, dir=tuple(-n))
    bb = sweep.bounding_box()
    local = body & box(bb.min.X - 1, bb.max.X + 1, bb.min.Y - 1, bb.max.Y + 1, bb.min.Z - 1, bb.max.Z + 1)   # (fast overlaps)
    v = overlap(st, local)
    check(v < EPS_V, f"logo stencil seated: {v:.3f} mm3 inside the body")
    v = overlap(sweep, local)
    check(v < EPS_V, f"logo stencil: its way into the pocket cuts {v:.3f} mm3 out of the body")
    ref = bspline_faces(P["band"])[0]
    fl = [f for f in near_faces(body, st, 1.0) if not _on_surface(f, ref)]
    flank = dist_shapes(st, Compound(fl))[0]
    check(flank > 0.02, f"logo stencil: {flank:.3f} to the pocket's flanks")
    gaps = {k: clear(st, o, f"logo stencil to the {k}", STENCIL_LED_MIN if k == "LEDs' room" else STENCIL_GAP_MIN)
            for k, o in others.items()}
    w_, h_, r_ = P["pw"] - 2 * ST["clr"], P["ph"] - 2 * ST["clr"], P["R"] - ST["clr"]
    g = np.vstack([rr_grid(w_, h_, r_, 0.5), rr_outline(w_ - 0.1, h_ - 0.1, r_ - 0.05, 0.5, 0.2)[0]])
    w_in = depths_along(P["inner"], P["F"], g)
    thick = ST["w_back"] - depths_along(st, P["F"], g)
    return dict(flank=flank, gaps=gaps, proud=(float((ST["w_back"] - w_in).min()), float((ST["w_back"] - w_in).max())),
                t=(float(thick.min()), float(thick.max())))


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


def battery_sweeps(path=None):
    """The battery's way in (battery_path) as boxes, BAT_HOLD behind its seat: straight up at X1, across at Z_MID, straight
    up at X2 to its seat height; then forward onto the board's back. Board frame (along the lean), turned into the world."""
    bp, h = path or BAT_PATH, BAT_L / 2
    y0, y1 = BAT_Y0 + BAT_HOLD, BAT_Y1 + BAT_HOLD
    out = {"up": box(bp["X1"] - h, bp["X1"] + h, y0, y1, -60, bp["Z_MID"] + BAT_HT)}
    if bp["Z_MID"] < BAT_Z0:
        out["across"] = box(min(bp["X1"], bp["X2"]) - h, max(bp["X1"], bp["X2"]) + h, y0, y1, bp["Z_MID"], bp["Z_MID"] + BAT_HT)
        out["up to the seat"] = box(bp["X2"] - h, bp["X2"] + h, y0, y1, bp["Z_MID"], BAT_Z0 + BAT_HT)
    out["forward"] = box(bp["X2"] - h, bp["X2"] + h, BAT_Y0, y1, BAT_Z0, BAT_Z0 + BAT_HT)
    return {k: tw(v) for k, v in out.items()}


def board_sweeps(shift=BOARD_UP_SHIFT):
    """The board's way in from below (cup off, rods taped on): every piece (glass, PCB, buttons, plugs, rods) straight up
    from below the seam `shift` behind its seat to its seat height, then forward onto the land (the rods into their
    slots). Boxes over each piece's bounding box (the pieces are boxes; the rods are swept as their 8 x 4 boxes). Board
    frame ("up" = along the lean), turned into the world. {(piece, "up" | "forward"): solid}."""
    out = {}
    for n, s_ in list(board_bodies_b().items()) + list(rod_solids_b().items()):
        bb = s_.bounding_box()
        out[(n, "up")] = tw(box(bb.min.X, bb.max.X, bb.min.Y + shift, bb.max.Y + shift, -60.0, bb.max.Z))
        out[(n, "forward")] = tw(box(bb.min.X, bb.max.X, bb.min.Y, bb.max.Y + shift, bb.min.Z, bb.max.Z))
    return out


def board_way_check(body, sweeps=None):
    """The board's way in against the body: BOARD_SWEEP_MIN for every piece up and forward, except the rods' forward move
    into their slots (designed (SLOT_W - ROD_W) / 2 a side: asserted free and at least half of that)."""
    sweeps = sweeps or board_sweeps()
    R = {}
    for (n, mv), sw in sweeps.items():
        rod_in = n.startswith("rod") and mv == "forward"
        need = (SLOT_W - hw.ROD_W) / 4 if rod_in else BOARD_SWEEP_MIN
        R[f"{n} {mv}"] = clear(sw, body, f"board's way in: {n} {mv}", need - 1e-6)
    return R


def battery_way_check(body, bd, sweeps=None):
    """The battery's way in (after the board) against the body (BAT_SWEEP_MIN - 0.05, as round 6) and the seated board."""
    sweeps = sweeps or battery_sweeps()
    R = {}
    for n, sw in sweeps.items():
        R[n] = clear(sw, body, f"battery on its way in ({n})", BAT_SWEEP_MIN - 0.05)
        R[n + " / board"] = min(clear(sw, s_, f"battery on its way in ({n}): {k}", BAT_GAP - 0.01) for k, s_ in bd.items())
    return R


def land_check(part, step=0.5, dy=0.02):
    """The inner land under the glass, measured on the solid: over the glass + LAND_MARGIN (outside both slots' straight
    cuts + 0.05), a point dy in front of Y_LAND is material and a point dy behind it is free (nothing behind the land
    plane: flat), and the glass's border ring (tape) has material in front all round. Board frame. Returns the counts."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN, TopAbs_OUT
    part = tb(part) & box(LAND_X[0] - 2, LAND_X[1] + 2, Y_LAND - 4, Y_LAND + 4, LAND_Z[0] - 2, LAND_Z[1] + 2)
    bad, n = [], 0
    for x in np.arange(LAND_X[0] + 0.01, LAND_X[1], step):
        if any(abs(x - x0) < SLOT_W / 2 + 0.05 for x0 in TUBE_X):
            zr = [z for z in np.arange(LAND_Z[0] + 0.01, LAND_Z[1], step) if not (AA_ZC - SLOT_L / 2 - 0.05 < z < AA_ZC + SLOT_L / 2 + 0.05)]
        else:
            zr = np.arange(LAND_Z[0] + 0.01, LAND_Z[1], step)
        for z in zr:
            n += 1
            for yy, want in ((Y_LAND - dy, TopAbs_IN), (Y_LAND + dy, TopAbs_OUT)):
                c = BRepClass3d_SolidClassifier(part.wrapped, gp_Pnt(float(x), float(yy), float(z)), 1e-7)
                if c.State() != want:
                    bad.append((round(float(x), 2), round(float(z), 2), "material" if want == TopAbs_IN else "free"))
    check(not bad, f"inner land not flat under the glass: {len(bad)} of {n} points, e.g. {bad[:4]}")
    return dict(n=n, step=step)


def _min_radius(P_, h=0.1, win=3):
    """Smallest radius of curvature along a polyline (n x 2), resampled every h by arc length; the turning over +-win
    samples. Returns (radius, index into the resampled points, the resampled points)."""
    P_ = np.asarray(P_, float)
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P_, axis=0), axis=1))]
    if d[-1] < 4 * win * h:
        return 1e9, 0, P_
    t = np.arange(0, d[-1], h)
    Q = np.c_[np.interp(t, d, P_[:, 0]), np.interp(t, d, P_[:, 1])]
    a = np.arctan2(*(Q[win:] - Q[:-win]).T[::-1])
    da = np.abs((a[win:] - a[:-win] + np.pi) % (2 * np.pi) - np.pi)
    k = da / (win * h)
    i = int(np.argmax(k))
    return 1 / max(k[i], 1e-12), i + win, Q


def front_check(fn=None, outer=None):
    """The front surface (fn: an xyz function of (th, z); default the built one): (1) over Z_B..Z_T the flat (x in ZONE_X)
    lies on the face plane exactly, and the flat's ends stay FLANK_MIN inside the flanks; (2) the smallest radius of
    curvature over the front (rows: horizontal sections, 4 mm in from the flanks, from 6 below the seam to the head;
    columns: vertical lines every 1 mm across the flat + 10, from 6 below the seam to the head) >= BLEND_R_MIN; (3) no
    brow: above Z_B nothing of the front lies in front of the face plane; (4) no shelf: between the seam and Z_B the centre
    line leans at most SEAM_DEG_MAX from vertical; (5) on the lofted solid (outer, world): rays along the face's normal onto
    the flat lie within ZONE_FLAT_TOL of the plane. Returns the numbers."""
    fn = fn or SH8.xyz
    R = {}
    thf = np.linspace(np.pi + 1e-4, 2 * np.pi - 1e-4, 6000)
    dev, brow, flank = 0.0, -1e9, 1e9
    for z in np.linspace(Z_B, Z_T, 160):
        X, Y, _ = fn(thf, np.full_like(thf, z))
        k = (X >= ZONE_X[0]) & (X <= ZONE_X[1])
        dev = max(dev, float(np.abs(Y[k] - y_face(z)).max()))
    for z in np.linspace(Z_B, H - 1.0, 400):
        X, Y, _ = fn(thf, np.full_like(thf, z))
        brow = max(brow, float((y_face(z) - Y).max()))
    for z in np.linspace(0.5, H - 1.0, 400):
        xl, xr, fl, fr, wf = flat_limits(z)
        if wf > 1e-6:
            flank = min(flank, float(xl - fl), float(fr - xr))
    R.update(fn_dev=dev, brow=brow, flank=flank)
    check(dev < 1e-9, f"front: the flat is off the face plane by {dev:.2e}")
    check(flank >= FLANK_MIN, f"front: the flat's end {flank:.2f} from a flank (< {FLANK_MIN})")
    check(brow <= 1e-6, f"front: a brow: the surface stands {brow:.3f} in front of the face plane above the slots' lower ends")
    # (2) radii
    best = (1e9, None)
    z_hi = Z_T + HEAD_FADE + 6.0
    for z in np.arange(SEAM - 6.0, z_hi, 0.5):
        X, Y, _ = fn(thf, np.full_like(thf, z))
        xl, xr, fl, fr, _ = flat_limits(z)
        k = (X > fl + 4) & (X < fr - 4)
        r, i, Q = _min_radius(np.c_[X[k], Y[k]])
        if r < best[0]:
            best = (r, ("row", round(float(z), 2), round(float(Q[i, 0]), 2)))
    zc = np.arange(SEAM - 6.0, z_hi, 0.05)
    for x in np.arange(ZONE_X[0] - 10, ZONE_X[1] + 10.01, 1.0):
        ys, zk = [], []
        for z in zc:
            X, Y, _ = fn(thf[::6], np.full(len(thf[::6]), z))
            if X.min() < x - 4 < x + 4 < X.max():
                o = np.argsort(X)
                ys.append(float(np.interp(x, X[o], Y[o])))
                zk.append(z)
        if len(zk) > 20:
            r, i, Q = _min_radius(np.c_[zk, ys])
            if r < best[0]:
                best = (r, ("column", round(float(x), 2), round(float(Q[i, 0]), 2)))
    R["r_min"], R["r_at"] = best
    check(best[0] >= BLEND_R_MIN, f"front: radius of curvature {best[0]:.2f} < {BLEND_R_MIN} at {best[1]} (a crease)")
    # (4) the seam's front: the centre line from the seam to Z_B
    z4 = np.linspace(SEAM, Z_B, 400)
    X, Y, _ = fn(np.full_like(z4, 1.5 * np.pi), z4)
    sl = np.degrees(np.arctan(np.abs(np.gradient(Y, z4))))
    R["seam_deg"] = float(sl.max())
    R["seam_y"] = float(Y[0])
    check(R["seam_deg"] <= SEAM_DEG_MAX, f"front: leans {R['seam_deg']:.1f} deg from vertical above the seam (a shelf; > {SEAM_DEG_MAX})")
    if outer is not None:                               # (5) rays along the face's normal onto the lofted outer face
        from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
        from OCP.gp import gp_Lin
        ob = tb(outer)
        si = IntCurvesFace_ShapeIntersector()
        si.Load(ob.wrapped, 1e-6)
        d = []
        for x in np.arange(ZONE_X[0] + 0.1, ZONE_X[1], 0.5):
            for z in np.arange(ZONE_ZB[0] + 0.1, ZONE_ZB[1], 0.5):
                si.Perform(gp_Lin(gp_Pnt(float(x), float(FACE_Y - 5.0), float(z)), gp_Dir(0, 1, 0)), 0.0, 10.0)
                check(si.NbPnt() > 0, f"front: no outer face at x {x:.1f}, z {z:.1f} (board frame)")
                d.append(abs(min(si.WParameter(i) for i in range(1, si.NbPnt() + 1)) - 5.0))
        R["solid_dev"], R["solid_n"] = float(max(d)), len(d)
        check(R["solid_dev"] <= ZONE_FLAT_TOL, f"front: the flat on the lofted solid {R['solid_dev']:.4f} off the face plane (> {ZONE_FLAT_TOL})")
    return R


def seam_check(body, cup, tol=SEAM_TOL):
    """The seam: the body's outer section 0.01 above the seam and the cup's 0.01 below it (measured on the solids, the outer
    loop of each; not at the cable notch: above the seam it is the round hole's part, below the cup's straight slot): the
    largest distance from either to the other. Returns it."""
    def outer_loop(part, z):
        seg = sm.section_segments(part, z, step=0.1)
        pts = np.r_[seg[:, :2], seg[:, 2:]]
        # the outer loop: points farthest out per direction from the centre
        a = np.degrees(np.arctan2(pts[:, 1] - 2.0, pts[:, 0]))
        r = np.hypot(pts[:, 0], pts[:, 1] - 2.0)
        keep = np.zeros(len(pts), bool)
        for b in np.arange(-180, 180, 0.5):
            k = np.flatnonzero((a >= b) & (a < b + 0.5))
            if len(k):
                keep[k[np.argmax(r[k])]] = True
        return pts[keep], seg
    pb, sb = outer_loop(body, SEAM + 0.01)
    pc, sc = outer_loop(cup, SEAM - 0.01)
    notch = lambda q: q[~((np.abs(q[:, 0] - HEAD_X) < CABLE_HOLE_D / 2 + 0.5) & (q[:, 1] > 0))]   # the cable notch differs by design
    pb, pc = notch(pb), notch(pc)
    d = max(float(sm.seg_dist(pb, sc).max()), float(sm.seg_dist(pc, sb).max()))
    check(d <= tol, f"seam: the body's and the cup's outer sections {d:.3f} apart (> {tol})")
    return d


def usb_checks(body, cups, bat, bd, rods, cast, seg_sets, dz=0.0, dx=0.0):
    """The extension's head and cable (dz, dx: shifted, for the fault injection) against everything, seated and on the
    ways in and out: the plug pushed up into the port from below (cup off, battery in), the cable laid up into the body's
    notch, each cup coming off straight down. Returns the measured gaps."""
    R = {}
    u = usb_solids(dz, dx)
    head, cable = u["usb-head"], u["usb-cable"]
    pas = CABLE_HOLE_D / 2 - CABLE_D / 2 - 0.01           # the cable in its round passage
    y_in = Y_BACK_OUT - WALL - 1.0                          # the cable's run inside, up to 1 mm before the back wall's inner face
    run = ycyl(HEAD_X + dx, CABLE_Z + dz, CABLE_D / 2, CABLE_Y0 + 0.5, y_in)
    up = Pos(dx, 0, dz) * tw(box(HEAD_X - HEAD_W / 2, HEAD_X + HEAD_W / 2, HEAD_Y0, HEAD_Y1, -30.0, HEAD_Z1))   # the plug's
                                                            # way up into the port: along the lean
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
    R["run_body"] = clear(run, body, "USB cable's run inside: the body (bosses)", HEAD_CLR)
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


def sha256(path):
    import hashlib
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def build():
    import time
    import pyvista as pv
    from scipy.spatial import cKDTree
    t0 = time.time()
    OUT.mkdir(exist_ok=True)
    for f_ in list(OUT.glob("dummy-*.stl")) + [OUT / n for n in ("door.stl", "door.step", "door-views.png", "cup-flat.stl", "cup-flat.step",
                                                                   "stable-ortho.png", "logo-compare.png", "keel-study.stl", "keel-square.stl")]:
        if f_.exists():                                    # no stale dummies, round 6's door or round 7's flat cup in the views
            f_.unlink()
    log = lambda m: print(f"[{time.time() - t0:6.1f} s] {m}", flush=True)
    log(f"tilt {TILT:g}: lift {LIFT:.3f} (PCB bottom z {PCB_Z0:.3f} in the board frame), face plane z {Z_B:.2f}..{Z_T:.2f}, "
        f"lip {LIP_A:.3f} x {LIP_B:.2f}, battery path {BAT_PATH['m']:.2f}")
    R = {}
    R["front"] = front_check()
    log(f"front (function): radius {R['front']['r_min']:.2f} at {R['front']['r_at']}, seam {R['front']['seam_deg']:.1f} deg, "
        f"brow {R['front']['brow']:+.2e}, flank {R['front']['flank']:.2f}")
    import pickle
    import build123d as _b3d
    early = os.environ.get("ROLY_EARLY")                # a debugging cache of the lofts and parts (never for a release build)
    bosses = boss_spots()
    lay_rock = [CUP_ROCK_CAST_TO]
    check(TRIM_LAYERS == 1 and not BUILD_STEPS, "one trim layer, no steps cup")
    cast_to = lay_rock[0]
    pk_steps = packing(lay_rock, bosses)
    log(f"layers {[(z, len(v)) for z, v in sorted(pk_steps.items())]}, cast to {cast_to}")
    if early and pathlib.Path(early).exists():
        E = pickle.loads(pathlib.Path(early).read_bytes())
        S = Surfaces.__new__(Surfaces)
        S.sh, S.levels, S.outer, S.inner, S._mid, S.inner_z, S.dev_outer, S.dev_inner = SH8, loft_levels, E["outer"], E["inner"], E["mid"], E["inner_z"], E["dev"][0], E["dev"][1]
        R["front"].update(E["front_solid"])
        log("loaded the cached lofts (ROLY_EARLY)")
    else:
        S = Surfaces(SH8)
        log(f"surfaces: outer {S.dev_outer:.3f}, inner {S.dev_inner:.3f}; keel {KEEL} NC {P['NC']}")
        R["front"].update({k: v for k, v in front_check(outer=S.outer).items() if k.startswith("solid")})
        log(f"front on the solid: {R['front']['solid_dev']:.4f}")
    if early and pathlib.Path(early).exists() and os.environ.get("ROLY_EARLY_PARTS") and "body" in E:
        body, shell_only, blank, cup_rock, env_rock, cav_rock = (E[k] for k in ("body", "shell", "blank", "cup", "env", "cav"))
        log("loaded the cached parts (ROLY_EARLY_PARTS)")
    else:
        body, shell_only, blank = make_body(S)
        log("body")
        cup_rock, env_rock, cav_rock = make_cup(S, lay_rock, cast_to=cast_to)
        if early:
            b_ = lambda o: _b3d.Solid(o.wrapped) if isinstance(o, _b3d.Solid) else _b3d.Compound(o.wrapped)
            pathlib.Path(early).write_bytes(pickle.dumps(dict(outer=b_(S.outer), inner=b_(S.inner), mid=b_(S.mid()), inner_z=S.inner_z,
                dev=(S.dev_outer, S.dev_inner), body=b_(body), shell=b_(shell_only), blank=b_(blank), cup=b_(cup_rock), env=b_(env_rock),
                cav=b_(cav_rock), front_solid={k: v for k, v in R["front"].items() if k.startswith("solid")})))
    dimple = cast_dimple(S, cast_to)
    parts = {"body": body, "cup-rock": cup_rock, "arc-gauge": arc_gauge()}
    if dimple is not None:
        parts["cast-plug"] = cast_plug(dimple, cast_to)
    cast_all = (S.inner & box(-100, 100, -100, 100, -5, cast_to)) - cup_rock
    if dimple is not None:
        cast_all = cast_all - dimple
        R["dimple"] = dict(V=vol(dimple) / 1000, depth=cast_to - (HEAD_LOW - HEAD_CLR), bb=dimple.bounding_box())
    sols = sorted(cast_all.solids(), key=vol, reverse=True)
    cast = sols[0]                                         # the pourable cavity; the rest are pockets in the dowel holes
    R["cast_frag"] = [vol(x) for x in sols[1:]]
    check(sum(R["cast_frag"]) < 0.01 * vol(cast), "cast region split into large pieces")
    log("cup")
    R["seam"] = seam_check(body, cup_rock)
    log(f"seam: body and cup {R['seam']:.4f} apart")

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
    R["thick"] = front_thickness_check(body)
    R["land"] = land_check(body)
    R["slots"] = slot_land_check(body)
    R["rod_slot"] = min(dist_shapes(r_, body)[0] for r_ in rods.values())
    check(R["rod_slot"] > 0.0 and all(overlap(r_, body) < EPS_V for r_ in rods.values()), f"a rod touches its slot: {R['rod_slot']:.3f}")
    R["glass_land"] = gap_to(bd["glass"], body)
    check(abs(R["glass_land"] - hw.GASKET) < 0.01, f"glass to the land {R['glass_land']:.3f}, the gasket is {hw.GASKET}")
    for n, s_ in bd.items():
        check(overlap(s_, body) < EPS_V, f"seated {n} hits the body")
    R["board_way"] = board_way_check(body)
    bat = battery_solid()
    R["bat_sweep"] = battery_way_check(body, bd)
    R["bat_board"] = clear(bat, bd["pcb"], "battery to the board", BAT_GAP - 0.01)
    R["bat_body"] = gap_to(bat, body)
    # the head: the board's top in the body, the battery to the back wall (seated), the head's room above the board
    R["board_top"] = min(gap_to(s_, body) for s_ in bd.values())
    R["bat_back"] = gap_to(bat, body, 15.0)
    R["head_room"] = head_room()
    led = led_keepout()
    check(overlap(led, body) < EPS_V, "the LEDs' room behind the logo is not free")
    R["led_bat"] = min(gap_to(led, sw) for sw in list(battery_sweeps().values()) + [bat])
    R["led_board"] = min(gap_to(led, sw) for sw in board_sweeps().values())          # gap_to stops looking at 6
    check(R["led_bat"] >= LED_MIN and R["led_board"] >= LED_MIN,
          f"LEDs' room: {R['led_bat']:.2f} from the battery's way in, {R['led_board']:.2f} from the board's way in (< {LED_MIN})")
    place_spots(body)
    R["spots"] = trim_spot_check(body, bat)
    log("fits")
    R["meat_body"] = [dist_shapes(zcyl(s["x"], s["y"], SEAM_R_HOLE if s["kind"] == "mag" else PIN_R_BODY, SEAM,
                                       SEAM + (SEAM_MAG_H + MAG_CLR_H if s["kind"] == "mag" else PIN_DEPTH)), Compound(f_out))[0] for s in bosses]
    co = [f for f in cup_rock.faces() if f.geom_type != GeomType.PLANE and f.geom_type != GeomType.CYLINDER]
    R["meat_cup"] = [gap_to(zcyl(s["x"], s["y"], SEAM_R_HOLE if s["kind"] == "mag" else PIN_R_CUP,
                                 SEAM - (SEAM_MAG_H + MAG_CLR_H if s["kind"] == "mag" else PIN_DEPTH), SEAM), Compound(co)) for s in bosses]
    check(min(R["meat_body"] + R["meat_cup"]) >= MEAT_MIN - 0.05, f"seam holes: wall to the outside {min(R['meat_body'] + R['meat_cup']):.2f}")
    # the logo: the stencil pocket (cut in make_body) and the stencils
    PK = logo_pocket(S)
    R["logo_skin"] = dist_shapes(PK["cut"], Compound(f_out))[0]            # thinnest material over the pocket, anywhere
    check(abs(R["logo_skin"] - LOGO_SKIN) < 0.02, f"logo skin {R['logo_skin']:.3f}")
    pb = PK["cut"].bounding_box()
    R["logo_box"] = (pb.min.X, pb.max.X, pb.min.Z, pb.max.Z)
    R["pocket_clear"] = pocket_clear_check(PK)
    ST = stencil_block(PK)
    st_parts = stencil_parts(PK, ST)
    st_print, R["stencil_areas"] = stencil_print(PK, ST, st_parts)
    R["stencil_frame"] = stencil_frame(PK, ST)
    check(R["stencil_frame"] >= 0.6, f"logo stencil: {R['stencil_frame']:.2f} of frame round the letters")
    sw_b = {f"board's way in ({k[0]} {k[1]})": v_ for k, v_ in board_sweeps().items()}
    sw_t = {f"battery's way in ({k})": v_ for k, v_ in battery_sweeps().items()}
    after = {**{f"seated {k}": v_ for k, v_ in bd.items()}, **rods, "battery": bat, **usb_solids(), "LEDs' room": led, **sw_b, **sw_t}
    R["stencil"] = stencil_check(body, PK, ST, after)
    R["stencil"].update(w_back=ST["w_back"], front=ST["front"], bb=st_print.solids()[0].bounding_box().size)
    log(f"logo stencil: back {ST['w_back']:.2f} behind the logo's plane, {R['stencil']['t'][0]:.2f}..{R['stencil']['t'][1]:.2f} thick, "
        f"{R['stencil']['flank']:.3f} to the flanks, LEDs' room {R['stencil']['gaps']['LEDs' + chr(39) + ' room']:.2f}")
    below = cav_rock & box(-100, 100, -100, 100, -10, SEAM - 0.01)
    skin = [f for f in env_rock.faces() if not (f.geom_type == GeomType.PLANE and abs(f.center().Z - SEAM) < 1e-6)]
    R["wall_rock"] = dist_shapes(below, Compound(skin))[0]
    check(R["wall_rock"] >= WALL - 0.05, f"cup-rock: wall {R['wall_rock']:.2f}")
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
    dummies["stencil"] = st_parts[0][0]                       # seated, as designed
    for n, s_ in dummies.items():
        write_stl(s_, OUT / f"dummy-{n}.stl")
    st_ = write_step(st_print, OUT / "logo-stencil.step")
    st_back = import_step(str(OUT / "logo-stencil.step"))  # meshed in memory (moved copies of one block) the STL came out
    write_stl(st_back, OUT / "logo-stencil.stl")           # with ~300 open edges; from the re-imported STEP it is closed
    files["logo-stencil"] = (st_, check_stl(st_back, OUT / "logo-stencil.stl", bodies=len(st_parts)))
    keel_meshes()
    log("exported")

    # ---- ballast measured on the exported cup
    names = ["cup-rock"]
    mesh = {n: pv.read(str(OUT / f"{n}.stl")) for n in names}
    pm = {"cup-rock": packing(lay_rock, bosses, mesh["cup-rock"])}
    for z in lay_rock:
        check(len(pm["cup-rock"][z]) == len(pk_steps[z]), f"cup-rock layer z {z}: {len(pm['cup-rock'][z])} segments measured, {len(pk_steps[z])} designed")
    cells = {n: [c for z in sorted(pm[n]) for c in pm[n][z]] for n in pm}
    for c in cells["cup-rock"]:
        check(overlap(segment_solids([c])[0], cup_rock) < EPS_V, f"cup-rock: segment at {c[:2]} hits the cup")
    runs = row_runs(mesh["cup-rock"], cells["cup-rock"])
    log(f"segments: rock {len(cells['cup-rock'])} over the cast")

    # ---- mass model (calculated) on the exported meshes, nominal and bad case
    meshes = {n: mesh_props(OUT / f"{n}.stl", RHO_PLA) for n in parts if n != "arc-gauge"}
    STENCIL_MASS.update(mesh_props(OUT / "dummy-stencil.stl", RHO_PLA))   # (its paint not counted)
    STENCIL_MASS.pop("pts")
    pts = {"cup-rock": np.vstack([meshes["body"]["pts"], meshes["cup-rock"]["pts"]])}
    mm = lambda cup: {n: meshes[n] for n in ("body", cup)}
    cases = {"nominal": dict(m_board=M_BOARD, m_bat=M_BAT, rho=RHO_CAST), "bad": dict(m_board=BAD["M_BOARD"], m_bat=BAD["M_BAT"], rho=BAD["RHO_CAST"])}
    C = {}
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
        soft(len(rest) >= 1 and all(abs(q) <= 1.0 for q in rest), f"{cn}: sideways rest positions {rest} (upright only, expected)")
    n_, b_ = C["nominal"], C["bad"]
    soft(n_["margin"] >= MARGIN_MIN, f"nominal: centre of mass {n_['margin']:.2f} under the rocking centre (needs {MARGIN_MIN})")
    soft(b_["margin"] >= MARGIN_MIN, f"bad case: centre of mass {b_['margin']:.2f} under the rocking centre (needs {MARGIN_MIN})")
    soft(n_["fwd"] >= FWD_MIN_NOMINAL, f"nominal forward {n_['fwd']:.2f} < {FWD_MIN_NOMINAL}")
    soft(n_["back"] >= BACK_MIN, f"nominal backward {n_['back']:.2f} < {BACK_MIN}")
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
    # the keel against round 7's (the study's keel, the cups as printed): the cup's centre-line section, how far it moved
    zk = np.linspace(0.05, SEAM, 300)
    Yk = np.array([SH8.xyz(1.5 * np.pi, z)[1] for z in zk])
    R["keel_dev"] = [(float(z), float(y + bf_of(z))) for z, y in zip(zk, Yk)]
    for cn, c in C.items():
        boxes = segment_solids(c["kept"]) + [spot_box(x) for x in c["spots"]]
        for i, b in enumerate(boxes):
            for n, o in (("body", body), ("cup-rock", cup_rock), ("battery", bat), *usb_solids().items()):
                check(overlap(b, o) < EPS_V, f"{cn} trim layout: piece {i} hits the {n}")
            for j in range(i):
                check(overlap(b, boxes[j]) < EPS_V, f"{cn} trim layout: pieces {i} and {j} overlap")
    seg_sets = {f"cup-rock {cn}": (cup_rock, segment_solids(c["kept"]) + [spot_box(x) for x in c["spots"]]) for cn, c in C.items()}
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
            pathlib.Path(os.environ["ROLY_DUMP"]).write_bytes(pickle.dumps(bare(dict(body=body, blank=blank, outer=S.outer, cups=dict(rock=cup_rock),
                bat=bat, bd=bd, rods=rods, cast=cast, seg_sets=seg_sets, spots={x: SPOTS[x]["solid"] for x in TRIM_SPOTS},
                pocket=PK, led=led, after=after))))
        except Exception as e:
            log(f"ROLY_DUMP failed: {e!r}")
    R["usb"] = usb_checks(body, dict(rock=cup_rock), bat, bd, rods, cast, seg_sets)
    R["skin"] = pocket_floor_check(body, PK, f_out[0])
    R["logo_outline"] = pocket_outline_check(body, PK)
    R["logo_roof"] = logo_roof_check(PK, OUT / "body.stl")
    R["logo_out"] = logo_outside(S)
    check(R["logo_out"]["clr"] >= LOGO_ZONE_CLR, f"logo {R['logo_out']['clr']:.2f} right of the front's flat (< {LOGO_ZONE_CLR})")
    R["logo_out_pocket"] = logo_outside(S, polys=[PK["q"]])
    check(R["logo_out_pocket"]["clr"] >= 0.0, f"logo pocket's floor {R['logo_out_pocket']['clr']:.2f} on the front's flat")
    R["logo_lip"] = dist_shapes(PK["cut"], slot_cutter(TUBE_X[1]))[0]
    write_stl(logo_decal(S, LOGO_X), OUT / "dummy-logo-new.stl")
    log("mass model")

    # ---- print orientations: overhangs steeper than 45 deg (calculated on the exported meshes)
    tree = cKDTree(SH8.G_OUT.reshape(-1, 3))
    ov = {}
    t_, o_, cc, aa = overhangs(OUT / "body.stl", (0, 0, -1), lambda c: c[:, 2] < SEAM + 0.05, tree)
    dist, _ = tree.query(cc)
    cb = pts_board(cc)
    slot = (np.min(np.abs(cb[:, 0][:, None] - np.array(TUBE_X)[None]), 1) < FACE_OPEN / 2 + 0.1) & (np.abs(cb[:, 2] - SLOT_Z[1]) < 0.1) & \
        (cb[:, 1] > FACE_Y - 0.2) & (cb[:, 1] < Y_LAND + 0.2)
    notch = (np.abs(cc[:, 0] - HEAD_X) < CABLE_HOLE_D / 2 + 0.1) & (cc[:, 2] < SEAM + CABLE_HOLE_D) & (cc[:, 1] > 10)
    lp, ln_, lxd = logo_frame()
    logo_r = (np.linalg.norm(cc - lp, axis=1) < LOGO_W)
    outer_k = (dist < 0.6) & ~slot & ~notch
    ov["body"] = dict(total=t_, outer=float(aa[outer_k].sum()), slots=float(aa[slot].sum()), notch=float(aa[notch].sum()),
                      crown=float(aa[(cc[:, 2] > 100) & ~outer_k & ~slot].sum()), logo=float(aa[logo_r & ~outer_k].sum()),
                      other=float(aa[~outer_k & ~slot & ~notch & ~(cc[:, 2] > 100) & ~logo_r].sum()),
                      outer_at=[[round(float(v), 1) for v in q] for q in cc[outer_k][np.argsort(-aa[outer_k])][:3]])
    check(ov["body"]["outer"] < 1.0, f"body rim-down: {ov['body']['outer']:.1f} mm2 of the outside overhangs more than 45 deg, at {ov['body']['outer_at']}")
    m_out = pv.read(str(OUT / "body.stl")).compute_normals(cell_normals=True, point_normals=False, auto_orient_normals=False)
    ncell, ccell = m_out.cell_data["Normals"], m_out.cell_centers().points
    cbo = pts_board(ccell)
    dist2, _ = tree.query(ccell)
    slot_o = (np.min(np.abs(cbo[:, 0][:, None] - np.array(TUBE_X)[None]), 1) < FACE_OPEN / 2 + 0.1) & (cbo[:, 1] > FACE_Y - 0.2) & \
        (cbo[:, 1] < Y_LAND + 0.2) & (cbo[:, 2] > SLOT_Z[0] - 0.1) & (cbo[:, 2] < SLOT_Z[1] + 0.1)
    k_o = (dist2 < 0.6) & (ccell[:, 2] > SEAM + 0.05) & ~slot_o
    R["outer_steepest"] = float(np.degrees(np.arcsin(np.clip(-ncell[k_o, 2], -1, 1))).max())
    # the slots' top ends (bridges): their faces' vertices, board frame; the width at the land (within its depth) and overall
    top = np.flatnonzero(slot_o & (np.abs(cbo[:, 2] - SLOT_Z[1]) < 0.1) & (ncell @ np.array([0.0, -SIN_T, -COS_T]) > 0.99))
    pb_ = pts_board(m_out.extract_cells(top).points)
    br = {}
    for x0, nm_ in zip(TUBE_X, ("left", "right")):
        q = pb_[np.abs(pb_[:, 0] - x0) < FACE_OPEN / 2 + 0.2]
        ql = q[q[:, 1] > Y_LAND - RIM + 0.01]
        br[nm_] = (float(np.ptp(ql[:, 0])) if len(ql) else 0.0, float(np.ptp(q[:, 0])) if len(q) else 0.0)
    ov["body"]["bridge"] = dict(land=min(v[0] for v in br.values()), face=max(v[1] for v in br.values()), each=br)
    ymax = float(mesh["cup-rock"].bounds[3])
    t_, o_, cc, aa = overhangs(OUT / "cup-rock.stl", (0, 1, 0), lambda c: c[:, 1] > ymax - 0.05, tree)
    band = (np.abs(cc[:, 1]) < 12) & (cc[:, 2] < 12)
    ov["cup_back"] = dict(total=t_, outer=o_, band=float(aa[band].sum()))
    ymin = float(mesh["cup-rock"].bounds[2])
    t_, o_, cc, aa = overhangs(OUT / "cup-rock.stl", (0, -1, 0), lambda c: c[:, 1] < ymin + 0.05, tree)
    band = (np.abs(cc[:, 1]) < 12) & (cc[:, 2] < 12)
    ov["cup_front"] = dict(total=t_, outer=o_, band=float(aa[band].sum()))
    log("overhangs")

    # ---- the cast by weight, and the wiring
    Vc = C["nominal"]["cast"]["V"] / 1000
    phi = lambda rho: (rho - RHO_EPOXY) / (RHO_BALL - RHO_EPOXY)
    balls = dict(V=Vc, nom=Vc * phi(RHO_CAST) * RHO_BALL, low=Vc * phi(BAD["RHO_CAST"]) * RHO_BALL,
                 epoxy=Vc * (1 - phi(RHO_CAST)), phi=(phi(RHO_CAST), phi(BAD["RHO_CAST"])),
                 depth=cast_to - S.inner_z[0], half=(S.inner_z[0] + cast_to) / 2)
    lv = []
    for k in (1, 2):
        lo_, hi_ = S.inner_z[0], cast_to
        for _ in range(14):
            mid = (lo_ + hi_) / 2
            lo_, hi_ = (mid, hi_) if vol(cast & box(-100, 100, -100, 100, -5, mid)) / 1000 < k * Vc / 3 else (lo_, mid)
        lv.append((lo_ + hi_) / 2)
    balls["levels"] = lv + [cast_to]
    i2c = pts_world(np.array([[XOFF + hw.PCB_W / 2 + 2, Y_BOARD1 - 2, PCB_Z0 + hw.PLUG_Z["i2c"]]]))[0]
    route = dict(led=float(np.linalg.norm(i2c - np.array([LOGO_X - 4, -12.0, i2c[2]])) + abs(i2c[2] - LOGO_ZC)))
    R["service"] = 50.0                                    # leads: from the board down past the seam, to plug from below
    tilts = {}
    for f_ in sorted(OUT.glob("surface-tilt*.json")):
        d_ = json.loads(f_.read_text())
        tilts[d_["tilt"]] = d_

    info = dict(R=R, PK=PK, st_webs=[w_ for _, w_ in st_parts], files=files, meshes={n: dict(m=v["m"], c=list(v["c"]), V=v["V"]) for n, v in meshes.items()},
                cast_to=cast_to, cells=cells, C=C, lay_rock=lay_rock, pk_steps=pk_steps, bosses=bosses,
                S=S, parts=parts, ov=ov, balls=balls, route=route, tilts=tilts)
    for n, cs in (("segments-rock", C["nominal"]["kept"]), ("segments-rock-left-out", C["nominal"]["left"])):
        if cs:
            write_stl(Compound(segment_solids(cs)), OUT / f"dummy-{n}.stl")
    write_stl(Compound([spot_box(x) for x in TRIM_SPOTS]), OUT / "dummy-trim-spots.stl")
    info["FAIL"] = FAIL
    report(info)
    build_sheet(info)
    focus(info)
    if FAIL:                                           # report only (user, 2026-11-24): the balance is set by hand
        log("mass model (report only): " + "; ".join(FAIL))
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
    nm = sum(1 for s in I["bosses"] if s["kind"] == "mag")
    cr = I["cells"]["cup-rock"]
    ov, bl, Fr, Th = I["ov"], I["balls"], R["front"], R["thick"]
    U = R["usb"]
    crown_y = Y_GLASS0 - np.array(hw.TAPE) - hw.ROD_H               # board frame, tape thin / thick
    proud = (Th["face"][0] - crown_y.max(), Th["face"][1] - crown_y.min())
    SL = R["slots"]
    hr = R["head_room"]
    gb = lambda d: f"{d:.2f}"
    L = []
    a = L.append
    a(f"DESK HOUSING track B: roly-poly, FDM prototype, round 8  (outline: the study's XOFF {XOFF} Z2L {P['Z2L']:.0f} A2L {P['A2L']} "
      f"Z2R {P['Z2R']:.0f} A2R {P['A2R']:.0f}; keel '{KEEL}' NC {P['NC']}; wall {WALL}; TILT {TILT:g} deg; lipped slots; one cup)")
    a("[m] measured on the exported files / solids; [d] designed; [calc] calculated from them with WEIGHED masses: nominal board "
      f"{M_BOARD:.0f} g, battery {M_BAT:.0f} g, misc {M_MISC:.0f} g, cast {RHO_CAST} g/cm3; bad case board {BAD['M_BOARD']:.0f}, battery "
      f"{BAD['M_BAT']:.0f}, cast {BAD['RHO_CAST']}; [est] the surface-level grid model (no bosses, land, logo; trim as one 15 g lump)")
    a("")

    gtop = pts_world(np.array([[0.0, Y_GLASS0, GLASS_Z0 + hw.GLASS_H], [0.0, Y_BOARD1, PCB_Z1]]))
    a("ROUND 8 (face tilted back, pebble-like front, one cup)")
    dm = R.get("dimple")
    a(f"  tilt       face, glass, board, rods, land, battery (taped to the board's back) and the USB head turn {TILT:g} deg back about "
      f"the board stack's bottom back edge (y {PIV_Y:+.2f}, z {PIV_Z:.2f}; lifted {LIFT:g}). The glass's top front edge goes "
      f"{gtop[0, 1] - Y_GLASS0:.1f} back (y {gtop[0, 1]:+.1f}, z {gtop[0, 2]:.1f}); the board's top back edge at y {gtop[1, 1]:+.1f}, "
      f"z {gtop[1, 2]:.1f}. The USB head's far end goes down to z {HEAD_LOW:.2f} (round 7: 17.5, {HEAD_CLR:g} over the cast's top z "
      f"{CUP_ROCK_CAST_TO:g})" + (f": the cast gets a dimple there ({dm['V']:.2f} cm3, up to {dm['depth']:.2f} deep, made by the printed "
      f"cast-plug.stl in the last batch); the cable leaves the head's far end (z {CABLE_Z_HEAD:.2f}) and runs back level at z {CABLE_Z:.2f} "
      f"(round 7: 21), clear of the cast. A lift of the board instead (1.87) raised the centre of mass 0.5: a second rest lying on "
      f"its side (~96 deg)" if dm else ""))
    a(f"  front      [d] the body's own surface: each horizontal section is the study's superellipse whose two front quarter-curves "
      f"are pulled apart by a flat over x {ZONE_X[0]:+.2f}..{ZONE_X[1]:+.2f} (both slots' openings + {ZONE_MARGIN:g}); the curves leave it "
      f"with zero slope and zero curvature. On the flat the front is the face plane from z {Z_B:.2f} to {Z_T:.2f} (the slots' ends + "
      f"{ZONE_MARGIN:g} along the lean), {FRONT_T:g} in front of the land. Below, the centre line blends (C1 ease) from the study's "
      f"belly and keel (z {FRONT_Z_A:g}) into the plane, the flat fading in with it: at the seam the front is at y {Fr['seam_y']:+.2f} "
      f"(round 7's cups: -17.75 with the alcove's flare) and leans at most {Fr['seam_deg']:.1f} deg from vertical between the seam and the "
      f"slots (asserted <= {SEAM_DEG_MAX:g}: no shelf). Above, the head rounds over (exponent {HEAD_M:g}) from the plane's line, the flat "
      f"fading out over {HEAD_FADE:g}: nothing stands in front of the plane above z {Z_B:.1f} ({Fr['brow']:+.1e}: no brow). The body above "
      f"the seam leans back with the face: the sections' centre moves back {float(y_centre(H)):.1f} from z {SHEAR_Z0:g} to {SHEAR_Z1:g} "
      f"(a smoothstep, {HEAD_SHEAR:g} x the face's lean on average), constant above: the battery's top corners need it (see 'battery'); "
      f"leaning on to the crown bent the head's front corners with R 3.1 (they read as edges)")
    a(f"  front [m]  smallest radius of curvature over the front {Fr['r_min']:.2f} at {Fr['r_at']} (rows and columns from 6 below the "
      f"seam to the head; asserted >= {BLEND_R_MIN}); the flat's ends {Fr['flank']:.1f} inside the flanks at least; on the lofted solid "
      f"the flat lies within {Fr['solid_dev']:.4f} of the face plane ({Fr['solid_n']} points; asserted <= {ZONE_FLAT_TOL})")
    a(f"  slots      [d] {SLOT_W:g} x {SLOT_L:.2f} straight through, a {SLOT_LAND:g} land at the inner face, then on each long side a "
      f"round lip (pebble-A): a quarter ellipse {LIP_A:.2f} across x {LIP_B:.2f} deep (radius {LIP_B ** 2 / LIP_A:.2f} at the land, "
      f"{LIP_A ** 2 / LIP_B:.2f} at the face), vertical at the land's top, stopped {90 - LIP_END_DEG:g} deg short of the face and run out "
      f"along its tangent: it meets the face at {90 - LIP_END_DEG:g} deg; each opening {FACE_OPEN:.2f} on the face, the flat strip "
      f"between them {hw.TUBE_CC - FACE_OPEN:.2f}; straight ends")
    a(f"  slots [m]  on {SL[0]['n']} board-frame sections along each slot: {min(q['w'] for q in SL):.3f}..{max(q['w_max'] for q in SL):.3f} "
      f"wide at the inner face, land {min(q['depth'] for q in SL):.2f}..{max(q['depth_max'] for q in SL):.2f} deep (wall within {LAND_TOL:g}), "
      f"the walls within {max(q['lip_dev'] for q in SL):.3f} of the designed land + lip at every depth (asserted <= {LIP_TOL}), opening "
      f"{min(q['face'] for q in SL):.2f} at {SL[0]['face_depth']:.3f} in front of the land (designed {SL[0]['face_want']:.2f}); rods to "
      f"the body {R['rod_slot']:.3f} at the closest")
    a(f"  thickness  [m] the front along both slots' edges (rays along the face's normal 0.1 outside each opening, {Th['n']} points along "
      f"the long sides and across the ends): {Th['lo']:.3f}..{Th['hi']:.3f} (asserted {FRONT_T:g} -+ {FRONT_T_TOL:g}). The rods (8 x 4 "
      f"half-rounds, flat on the glass) stand {proud[0]:.2f}..{proud[1]:.2f} proud of the face at their crowns (tape {hw.TAPE[0]:g} / "
      f"{hw.TAPE[1]:g}), along their whole length")
    a(f"  land       [m] the inner land is flat at y {Y_LAND:+.2f} (board frame) over the glass + {LAND_MARGIN:g} ({R['land']['n']} points "
      f"every {R['land']['step']:g}); glass on it {R['glass_land']:.2f} (the gasket tape); its lower edge rises {LAND_DEG:g} deg towards the "
      f"back in the world")
    kd = np.array(R["keel_dev"])
    kd5 = np.abs(kd[kd[:, 0] <= 5, 1]).max()
    kd10 = np.abs(kd[kd[:, 0] <= 10, 1]).max()
    a(f"  seam, cup  one surface for body and cup: [m] the body's and the cup's outer sections at the seam {R['seam']:.4f} apart "
      f"(asserted <= {SEAM_TOL}); no alcove flare any more. The cup's front changed from the keel up: the centre line moves "
      f"back by at most {kd5:.3f} below z 5, {kd10:.2f} below z 10, {np.abs(kd[:, 1]).max():.2f} at the seam (round 6's cup without its "
      f"alcove: the study's keel) [d]; the rolling arc (front view, section y 0), keel exponent and cast step as before; the cable notch "
      f"1 lower (z {CABLE_Z:g}), still split by the seam")
    bw = R["board_way"]
    a(f"  board      in from below (cup off), rods taped on: along the lean {BOARD_UP_SHIFT:.2f} behind its seat, then forward onto the "
      f"land; [m] least gaps: up {min(v for k, v in bw.items() if k.endswith(' up')):.2f}, forward "
      f"{min(v for k, v in bw.items() if k.endswith('forward') and not k.startswith('rod')):.2f} (asserted >= {BOARD_SWEEP_MIN}); the rods "
      f"into their slots {min(v for k, v in bw.items() if k.startswith('rod') and k.endswith('forward')):.3f} a side; seated, the board's "
      f"nearest body surface {R['board_top']:.2f}; held by the gasket tape on the glass's border and a foam pad behind the battery")
    bs = R["bat_sweep"]
    a(f"  battery    taped to the board's back (Kapton, {BAT_GAP:g}), tilts with it. In from below after the board, along the lean, "
      f"{BAT_HOLD:g} behind its seat: up at x {BAT_PATH['X1']:+.2f}, from z {BAT_PATH['Z_MID']:.2f} (board frame) "
      f"{BAT_PATH['X2'] - BAT_PATH['X1']:+.2f} sideways, up to z {BAT_Z0:.2f} at x {BAT_PATH['X2']:+.2f}, forward onto the board; [d] "
      f"{BAT_PATH['m']:.2f} a side on the inner sections (its top corners, where the body narrows, decide it: at {TILT:g} deg without the "
      f"body's lean it was negative); [m] " + ", ".join(f"{k} {v:.2f}" for k, v in bs.items() if "/" not in k) +
      f" (asserted >= {BAT_SWEEP_MIN - 0.05:.2f}); to the seated board >= {min(v for k, v in bs.items() if '/' in k):.2f}; seated: "
      f"{R['bat_body']:.2f} to the body (the back wall {R['bat_back']:.2f}), {U['head_bat']:.2f} over the USB head (asserted >= {BAT_HEAD_MIN:g})")
    a(f"  head       [m] above the board's highest point (z {hr['z']:.1f}) the cavity is {hr['h']:.1f} high, {hr['v']:.1f} cm3 (inner "
      f"grid); the board's top {R['board_top']:.2f} from the body at the closest")
    sp = R["spots"]
    a("  trim spots on the back inner wall, right of the centre line, turned to the wall: " + "; ".join(
      f"x {x:+.1f}: z {v['z0']:.1f}..{v['z0'] + SEG[1]:.1f}, turned {v['turn']:+.1f} deg, resting on its edges ({v['sag']:.2f} off "
      f"the wall at its middle), {v['body']:.3f} to the body, {v['bat']:.2f} to the battery (seated and on its way in), {v['usb']:.2f} "
      f"to the USB head / cable, {v['board']:.2f} to the board's way in" for x, v in sp.items()) + " [m]")
    a(f"  logo       stencil pocket as 7b, letters {LOGO_W:g} mm, MOVED from x 32, z 31 to x {LOGO_X:g}, z {LOGO_ZC:g}: there the pocket "
      f"straddled the new front's turn from the belly into the leaning face (its lower right flank leaned into the axis: the stencil "
      f"would not go in); at x 30 the LEDs' room came 2.5 from the battery (needs 3); [m] the letters "
      f"{R['logo_out']['clr']:.2f} right of the front's flat (asserted >= {LOGO_ZONE_CLR:g}), the pocket's floor {R['logo_out_pocket']['clr']:.2f} "
      f"(asserted >= 0), the pocket {R['logo_lip']:.2f} from the right slot's lip; the surface turns " +
      " / ".join(f"{t:.0f}" for t in R['logo_out']['turn']) + " deg from the front across the letters (round 7: 17 / 30 / 51)")
    tl = I["tilts"]
    if tl:
        a("  TILT 6 / 8 / 10 [d, surface level, for the side views (tilt-compare.png)]:")
        for t_, d_ in sorted(tl.items()):
            a(f"    tilt {t_:4.1f}: body lean {d_['shear']:g}{' (less folds the head)' if d_['shear'] != HEAD_SHEAR else ''}, plane z "
              f"{d_['Z_B']:.1f}..{d_['Z_T']:.1f}, the board's top {d_['board_top'][0] - Y_BOARD1:+.1f} back; front: smallest radius "
              f"{d_['front']['r_min']:.2f}, lean above the seam {d_['front']['seam_deg']:.1f} deg; head cavity {d_['head']['v']:.0f} cm3")
    a("ROUND 7 (printed 2026-11-23): no door, a vertical flat zone recessed into the body (brow and shelf), cups as round 6, "
      "logo stencil 7b; nominal 8.57 mm, fwd 28.3 / back 31.1; bad 6.17")
    a("ROUND 6: USB extension in the board's own port, cable through a D5.6 hole split by the seam; slots 8.1 with a 0.6 land; "
      "logo skin 1.0; battery over the USB head; cast to z 17. ROUND 5-2: logo, keel, pole, cast ballast, magnets")
    a("")
    a("SIZE AND SURFACE")
    a(f"  outer      [m] {W:.1f} wide x {D:.1f} deep x {bb('body').max.Z:.1f} tall on the rocking cup")
    a(f"  surface    [m] outer loft within {I['S'].dev_outer:.3f} of its function, inner within {I['S'].dev_inner:.3f} of its points")
    a(f"  pole       [m] cup-rock.stl below z 0.001: {R['pole'][0]:.2f} wide across, {R['pole'][1]:.2f} along; arc y 0 off R{RR:.0f} by "
      f"{R['arc'][1]:.3f}, left-right {R['arc'][0]:.3f}; sections x / y 0.01 run as one curve through the bottom")
    a(f"  wall       [m] body {R['wall_min']:.2f} at least ({FRONT_T:g} over the glass); cup-rock {R['wall_rock']:.2f}")
    a("")
    a("PARTS  [m] volume, mass (solid PLA 1.24), centroid")
    for n in m:
        a(f"  {n:<15}{m[n]['V'] / 1000:6.1f} cm3 {m[n]['m']:6.1f} g   ({m[n]['c'][0]:+.2f}, {m[n]['c'][1]:+.2f}, {m[n]['c'][2]:.2f})")
    a(f"  logo stencil   {STENCIL_MASS['V'] / 1000:6.2f} cm3 {STENCIL_MASS['m']:6.2f} g   (seated, as designed; in the mass model with the body)")
    a(f"  arc-gauge      concave R{RR:.0f} cradle, 60 x 20")
    a("  (round 7: body 56.0 g, cup-rock 16.7 g)")
    a("")
    a("INSIDE")
    a(f"  board      [d] stack {hw.BOARD_T} (housing.py's measured value): glass y {Y_GLASS0:+.2f}..{Y_GLASS1:+.2f}, board back "
      f"{Y_BOARD1:+.2f} (board frame); battery to the board {R['bat_board']:.2f} [m]; RST / BOOT reachable from below with the cup off")
    a(f"  usb head   [d] port at x {HEAD_X:+g}, y {PORT_Y:.2f} (board frame, ASSUMED); turned with the board: world box x "
      f"{HEAD_BB[0]:.1f}..{HEAD_BB[1]:.1f}, y {HEAD_BB[2]:.1f}..{HEAD_BB[3]:.1f}, z {HEAD_BB[4]:.1f}..{HEAD_BB[5]:.1f}; [m] seated: body "
      f"{U['head_body']:.2f}, battery {U['head_bat']:.2f}, cast {U['head_cast']:.2f}, cup {U['head_cup-rock']:.2f}; pushed up into the "
      f"port along the lean: body {U['up_body']:.2f}, battery {U['up_bat']:.2f}, board / rods {U['up_board']:.2f}; cup off straight down "
      f"{U['off_head_cup-rock']:.2f}")
    a(f"  usb cable  [d] D{CABLE_D:g} straight back (horizontal; it bends {TILT:g} deg at the head) from the far end's centre (y {CABLE_Y0:.2f}, "
      f"z {CABLE_Z:.2f}) through the D{CABLE_HOLE_D:g} hole split by the seam (from y {CABLE_Y0 + CABLE_HOLE_FROM:.2f}); [m] in the hole: "
      f"body {U['cable_body']:.2f}, cup {U['cable_cup-rock']:.2f}; its run inside: body {U['run_body']:.2f}, cup {U['run_cup-rock']:.2f}, cast "
      f"{U['cable_cast']:.2f}, battery {U['cable_bat']:.2f}; laid up into the body's notch {U['lay_body']:.2f}; cup off "
      f"{U['off_cable_cup-rock']:.2f}; the passage overlaps nothing: " + ", ".join(f"{k} {v:.4f} mm3" for k, v in U["hole"].items()))
    a(f"  segments   [m] to the USB head / cable (seated and as the cup comes off): " + ", ".join(f"{k} {v:.2f}" for k, v in U["segs"].items()))
    pk, sk, stn, lr = I["PK"], R["skin"], R["stencil"], R["logo_roof"]
    pc = R["pocket_clear"]
    a(f"  pocket     [d] floor {pk['pw']:.2f} x {pk['ph']:.2f} R{pk['R']:g} projected along the logo's normal onto the outer surface "
      f"moved {LOGO_SKIN:g} in; the floor lies {sk['depth'][0]:.2f}..{sk['depth'][1]:.2f} behind the logo's tangent plane; flanks "
      f"{STENCIL_DEG:g} deg from the floor's normal, the top one {STENCIL_TOP_DEG:g} ({math.degrees(math.atan(pk['widen'].min())):.0f}.."
      f"{math.degrees(math.atan(pk['widen'].max())):.0f} deg from the axis)")
    a(f"  pocket     [m] skin {sk['lo']:.3f}..{sk['hi']:.3f} over {sk['n']} points of the floor (asserted {SKIN_RANGE[0]:g}..{SKIN_RANGE[1]:g}), "
      f"{R['logo_skin']:.3f} at the thinnest anywhere; open to the cavity over {sk['open'] * 100:.0f} % of the floor; the floor's outline "
      f"within {R['logo_outline']['off']:g} ({R['logo_outline']['n']} points); printed rim-down, faces steeper than 46 deg only within "
      f"{lr['far']:.3f} of the skin (asserted <= {LOGO_LEDGE:g}), the steepest further in {lr['steepest']:.1f} deg from vertical; "
      f"{pc['holes']:.2f} from a seam hole, {pc['bosses']:.2f} from a boss, {pc['land']:.2f} from the inner land, {pc['slots']:.2f} from a "
      f"slot, its lowest point {pc['seam']:.2f} above the seam")
    og = {k: v for k, v in stn["gaps"].items() if k != "LEDs' room"}
    kmin = min(og, key=og.get)
    a(f"  stencil    [m] {stn['t'][0]:.2f}..{stn['t'][1]:.2f} thick (back plane w {stn['w_back']:.2f}); its back {stn['proud'][0]:+.2f}.."
      f"{stn['proud'][1]:+.2f} proud of the inner face; goes in along the axis from {STENCIL_SWEEP:g} inside without touching the body; "
      f"seated {stn['flank']:.3f} to the flanks; {stn['gaps'][chr(76) + 'EDs' + chr(39) + ' room']:.2f} to the LEDs' room (asserted >= "
      f"{STENCIL_LED_MIN:g}); to the board, battery, rods, USB (seated, and the ways in) >= {og[kmin]:.2f} ({kmin}; asserted >= "
      f"{STENCIL_GAP_MIN:g}); frame round the letters {R['stencil_frame']:.2f}")
    a(f"  stencils   [m] out-rolypoly/logo-stencil.stl / .step: {len(R['stencil_areas'])} stencils, webs " +
      ", ".join(f"{w:.2f}" for w in I["st_webs"]) + f"; {stn['bb'].X:.2f} x {stn['bb'].Y:.2f} x {stn['bb'].Z:.2f} each, flat back on the bed")
    a(f"  LEDs       room free: {'>= 6' if R['led_bat'] >= 5.99 else format(R['led_bat'], '.2f')} from the battery (seated and its way in), "
      f"{'>= 6' if R['led_board'] >= 5.99 else format(R['led_board'], '.2f')} from the board's way in (asserted >= {LED_MIN})")
    a(f"  wiring     [d] I2C 3V3 -> LEDs {I['route']['led']:.0f} mm + slack; leads plugged from below with the cup off (~{R['service']:.0f} "
      f"mm each: ASSUMED, check)")
    a("")
    a("SEAM JOINT (new positions on the new seam section; the parts as round 6)")
    a(f"  [d] {nm} x D{SEAM_MAG_D}x{SEAM_MAG_H} pairs + 2 x D{SEAM_PIN_D}x{SEAM_PIN_L} dowels at " + ", ".join(
      f"{s['kind']} x {s['x']:+.1f} y {s['y']:+.1f}" for s in I["bosses"]) + f"; [m] wall to the outside: body {min(R['meat_body']):.2f}, "
      f"cup {min(R['meat_cup']):.2f}")
    hang = m["cup-rock"]["m"] + n_["cast"]["m"] + SEG_G * len(n_["kept"])
    a(f"  [calc] lifted by the body the joint carries {hang:.0f} g")
    a("")
    a("BALLAST")
    a(f"  cast       [m] pourable cavity up to z {I['cast_to']}: {bl['V']:.2f} cm3 (round 7: 23.53); [calc] {n_['cast']['m']:.0f} g at {RHO_CAST} "
      f"({b_['cast']['m']:.0f} g at {BAD['RHO_CAST']}); balls {bl['nom']:.0f} g, epoxy ~{bl['epoxy']:.0f} ml, three batches to z " +
      " / ".join(f"{z:.1f}" for z in bl["levels"]))
    if dm:
        a(f"  dimple     [d] under the USB head's far end: {dm['V']:.2f} cm3 ({dm['V'] * RHO_CAST:.1f} g of cast less), x {dm['bb'].min.X:.1f}.."
          f"{dm['bb'].max.X:.1f}, y {dm['bb'].min.Y:.1f}..{dm['bb'].max.Y:.1f}, down to z {dm['bb'].min.Z:.2f}; the plug (cast-plug.stl) "
          f"is its shape plus a 5 x 5 handle")
    a(f"  trim layer [m] {len(cr)} segments fit on the cast (z {I['cast_to']}..{I['cast_to'] + SEG[2]:.1f}); " + ", ".join(
      f"row y {r_['y']:+.1f}: {len(r_['idx'])}" for r_ in row_runs_cached(I)))
    a("")
    rk = lambda c: (f"{c['st']['M']:.0f} g, margin {c['margin']:.2f}, period {c['T']:.2f} s, forward {c['fwd']:.1f} / back {c['back']:.1f} deg, "
                    f"rests " + ", ".join(f"{q:+.1f}" for q in c["rest"]) + f", plumb {c['gx']:+.2f} with {len(c['spots'])} spot(s)")
    a(f"ROCKING [calc, report only; weighed masses]: nominal (board {M_BOARD:g}, battery {M_BAT:g}): {rk(n_)}; bad case (board "
      f"{BAD['M_BOARD']:g}, battery {BAD['M_BAT']:g}, cast {BAD['RHO_CAST']:g}): {rk(b_)}" + (f"; outside the old limits: " + "; ".join(I["FAIL"]) if I["FAIL"] else ""))
    a("")
    ob = ov["body"]
    a("PRINT ORIENTATION, overhangs steeper than 45 deg [m on the meshes]")
    a(f"  body rim-down:    {ob['total']:.0f} mm2 in all: outside {ob['outer']:.1f} (asserted < 1; the outside leans at most "
      f"{R['outer_steepest']:.1f} deg from vertical over the bed); the slots' top ends {ob['slots']:.0f} (bridges, the end faces look "
      f"{TILT:g} deg off straight down: [m] on the mesh {ob['bridge']['land']:.2f} wide along the land, {ob['bridge']['face']:.2f} at the "
      f"face incl. the lips' run-out; designed {SLOT_W:g} / {FACE_OPEN:.2f} + 2 x the run-out); inside the crown above z 100: {ob['crown']:.0f}; round the logo "
      f"pocket {ob['logo']:.0f}; the cable notch's arch {ob['notch']:.0f}; other inside {ob['other']:.0f}")
    a(f"  cup-rock on its back: {ov['cup_back']['total']:.0f} mm2 ({ov['cup_back']['outer']:.0f} outside; the rolling band: {ov['cup_back']['band']:.0f}); "
      f"on its front: {ov['cup_front']['total']:.0f} mm2 ({ov['cup_front']['outer']:.0f} outside; the rolling band: {ov['cup_front']['band']:.0f})")
    a("")
    a("FILES  [m] each STEP re-imported (solids, valid, closed, triangulated volume), each STL re-read (closed, one body, volume vs 0.05 mesh)")
    for n, (s_, t_) in I["files"].items():
        a(f"  {n:<15}STEP {s_['solids']} solid, {s_['faces']} faces, {s_['err'] * 100:+.4f} %, {s_['kb']:.0f} kB; STL {t_['tris']} triangles, "
          f"{t_['err'] * 100:+.3f} %, {t_['kb']:.0f} kB")
    a("")
    a("NOT VERIFIED HERE: the cast's packing (filled by feel), the USB cable's mass (~5 g in misc); the USB extension's head (12 x 21 x 8.5, ASSUMED), the port's "
      "position (2.0 in front of the board's back, ASSUMED) and the cable's bend at the head; the plugs' protrusion (4 assumed); the "
      "leads' length; the gasket tape's hold on a tilted face; the face's look (clay views only); the slicer's toolpaths (the slots' "
      "bridges, the lips at 0.08 layers); magnet pull; cable lean; rocking feel; the stencil's fit and the logo's glow")
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
    lo = n_["left"]
    lv = bl["levels"]
    bp = BAT_PATH
    ob = I["ov"]["body"]
    sp = R["spots"]
    fail = ""                                          # the mass model is report only (the balance is set by hand)
    L = f"""ROLY-POLY: BUILD SHEET, round 8: face tilted back {TILT:g} deg, pebble-like front with lipped slots, a new rocking cup
(files in cad/desk/out-rolypoly/; numbers in report.txt). The round 6 / 7 cups do NOT fit this body (its front at the seam is
new): print the new cup-rock. The flat cup is dropped.
{fail}
PRINT  (Bambu X1E, Bambu Studio, 0.4 nozzle)
  body.stl        PLA Matte white, 0.08 mm (0.08 HQ), 6 walls. Seam ring on the plate, crown up. Supports: tree, on build
                  plate only (as round 7: they improved the slots' top ends): for the slots' top ends ({ob['slots']:.0f} mm2; each a
                  bridge {SLOT_W:g} wide at the inner land, {FACE_OPEN:.1f} at the face, its end face {TILT:g} deg off straight down),
                  the crown's inside ({ob['crown']:.0f} mm2) and the cable notch's arch. The outside has no overhang steeper than
                  45 deg ({ob['outer']:.1f} mm2; it leans out at most {R['outer_steepest']:.0f} deg). Block supports in the logo pocket
                  (its top flank leans {R['logo_roof']['steepest']:.0f} deg from vertical). The inner land's lower edge rises {LAND_DEG:g} deg.
                  No brim on the seam ring. enable_overhang_speed 0 as round 7's plate (closure-ring test: B best).
  cup-rock.stl    PLA Matte white, 0.08. On its back as round 7, tipped 35 deg toward its rim (to-print/mkplate8.py,
                  CUP_TILT): it stands on the rim's back edge; round 7's ring patch moves from the front to the
                  lower front by the keel; tree supports (mostly inside the bowl) + 8 mm brim on the back edge.
                  (Lying on its front would put the support cradle on the front.) Sand the rolling band lightly if a seam shows.
  arc-gauge.stl   any PLA, flat side down (optional).
  cast-plug.stl   any PLA, handle up (it stands on its sloped bottom: a few support pins, or print it handle down).
  logo-stencil.stl  {len(R['stencil_areas'])} stencils (webs {', '.join(f'{w:.2f}' for w in I['st_webs'])}), as round 7b: flat back on the plate,
                  no supports; paint the one you use black.

FINISH
  Slots: a rod (8.0) should drop in with a little play (8.1 slot, {SLOT_LAND:g} land at the inner face, then the round lips); if
  tight, a light pass with a flat needle file on the land only, not on the lips. Check the inner land behind the glass is
  clean (no blobs at the slots' ends). Break the seam ring's outer edge lightly with 400 so body and cup meet without a lip.

PARTS
  As round 7: {2 * nm} magnets D{SEAM_MAG_D} x {SEAM_MAG_H} and 2 dowels (new holes: the cup is new), the right-angle USB-C extension,
  the logo stencil, two warm-white 0603 LEDs + an SH1.0 4-pin pigtail, Kapton, double-sided foam tape (1 mm) for the battery,
  gasket tape ({hw.GASKET:g}) for the glass's border, a soft foam pad, OCA for the rods, 2 rods 8 x 4 half-round cut to {ROD_L},
  the 304 balls and 5-minute epoxy, stick-on weights.

ASSEMBLY (in this order; everything goes in from below with the cup off; "along the lean" = parallel to the face, {TILT:g} deg
back from vertical)
  1. Body: magnets and dowels in the seam bosses (flush in glue); the cup's magnets likewise.
  2. Logo, then LEDs: as round 7b (stencil in from inside along the pocket's axis, a drop of glue on its back edge; LEDs in
     the room 4.5-8.5 mm behind the logo).
  3. Board: rods on the glass (OCA, centred on the tubes), gasket tape on the glass's border. Plug the LED pigtail into the I2C
     header and switch the board ON first. Bring the board in through the seam opening, glass to the front, and push it up
     ALONG THE LEAN keeping it {BOARD_UP_SHIFT:.1f} mm behind its seat (the rods' crowns 0.5 behind the inner land; checked >=
     {BOARD_SWEEP_MIN:g} on the way), up to its height, then forward: the rods drop into their slots (0.05 a side), the glass
     presses onto the land.
  4. Battery, from below after the board, taped to its back as round 7: Kapton on the board's back, foam tape on the battery
     (liner on), its lead plugged first; push it up along the lean {BAT_HOLD:g} mm behind its seat, centred at x {bp['X1']:+.1f} (the
     centre of the seam opening), until it is {bp['Z_MID'] - bp['zs0']:.1f} mm in, then {abs(bp['X2'] - bp['X1']):.1f} mm to the
     {'left' if bp['X2'] < bp['X1'] else 'right'} and on up to its height (its bottom 1 mm over where the USB head will be); peel
     the liner and press it onto the board's back. Checked: >= {min(v for k, v in R['bat_sweep'].items() if '/' not in k):.2f} to the body
     on the way; its top corners are the tight spot.
  5. USB: push the extension's right-angle plug up into the board's port from below, along the lean (checked:
     {R['usb']['up_body']:.2f} to the body, {R['usb']['up_bat']:.2f} to the battery), cable towards the back, bent {TILT:g} deg at the head
     to run level into the round notch in the back rim (x {HEAD_X:+g}).
  6. Hold-down: as round 7 (gasket tape, rods in their slots, a foam pad between the battery's back and the back wall left of
     x +5).
  7. Cast (cup off), as round 7: three batches of 5-minute epoxy to {SEAM - lv[0]:.1f} / {SEAM - lv[1]:.1f} / {SEAM - lv[2]:.1f} mm
     below the seam face; {bl['nom']:.0f} g of balls in all ({bl['low']:.0f} g is still fine). NEW: before the last batch sets, press
     the cast plug (cast-plug.stl, wrapped in packing tape or greased) into it under where the USB head's far end will be: its
     flat top flush with the cast's top, its long side along y at x {HEAD_X:+g} (dummy-usb-head.stl shows the place); pull it out
     after the cure. It leaves the dimple the tilted head needs ({HEAD_CLR:g} clear). 24 h cure.
  8. Trim layer: {len(I['cells']['cup-rock'])} segments fit on the cast (dummy-segments-rock.stl). The plan (nominal masses): stick
     {len(n_['spots'])} segment(s) standing on the back inner wall at x {', '.join(f'{x:+.0f}' for x in n_['spots']) or '-'} (bottoms at z
     {', '.join(f"{sp[x]['z0']:.1f}" for x in TRIM_SPOTS)}, i.e. {', '.join(f"{sp[x]['z0'] - SEAM:.1f}" for x in TRIM_SPOTS)} mm above the seam
     plane; fill the gap behind each one's middle, up to {max(sp[x]['sag'] for x in TRIM_SPOTS):.1f} mm, with foam tape), leave out
     {len(lo)} of the trim layer{(' (' + ', '.join(f'x {c[0]:+.0f} y {c[1]:+.0f}' for c in lo) + ')') if lo else ''} and slide the rest
     {n_['t'] * 100:.0f} % of their rows' slack to the right. Do not peel the adhesive yet.
  9. Cup on, straight up: the cable slides into the cup's notch, pins find the holes, magnets close the seam. Trim on the
     table, then stick the segments down.
  To service: cup off, unplug the USB head; battery and board come out the way they went in (along the lean).

TRIM
  Level table, everything wired and closed. The face leans {TILT:g} deg back now: put the phone level on the back of the head or
  on the table edge, not on the face. Coarse: a segment at the back-wall spots. Fine: slide a row of segments towards the high
  side: 10 mm of one 5 g segment moves the lean by about {math.degrees(math.atan(SEG_G * 10 / n_['st']['M'] / n_['margin'])):.1f} deg.

CHECK ON THE PRINT
  the front (flat over the slots, no brow, no shelf, the seam's front), the lips and the slots' top ends, the rods' crowns
  standing proud ({FRONT_T:g} front, 0.55..0.75), the board's and battery's ways in along the lean, the USB cable's bend at
  the head, rocking and falling forward (beyond {n_['fwd']:.0f} deg) / backward (beyond {n_['back']:.0f} deg, calculated), the
  stencil's fit and the logo glow.
"""
    (OUT / "build-sheet.txt").write_text(L)


def focus(I):
    p, n, xd = logo_frame()
    fc = pts_world(np.array([[XOFF, FACE_Y, AA_ZC]]))[0]
    st = pts_world(np.array([[TUBE_X[0], FACE_Y, SLOT_Z[1]]]))[0]
    d = dict(face_c=[float(v) for v in fc], face_y=float(fc[1]), tilt=TILT, logo=list(map(float, p)), logo_n=list(map(float, n)), seam=SEAM,
             RR=RR, H=H, slot_top=[float(v) for v in st], usb=[HEAD_X, Y_BACK_OUT, CABLE_Z], zone_x=list(ZONE_X), z_b=Z_B, z_t=Z_T,
             face_n=[0.0, -COS_T, SIN_T], tube_x=list(TUBE_X), G_rock=list(map(float, I["C"]["nominal"]["st"]["G"])), cast_to=I["cast_to"],
             keels=KEELS, keel=KEEL, logo_x=LOGO_X, seam_front_y=I["R"]["front"]["seam_y"])
    (OUT / "focus.json").write_text(json.dumps(d, indent=1))


if __name__ == "__main__":
    if "--surface" in sys.argv[1:]:
        surface_study()
    else:
        build()
