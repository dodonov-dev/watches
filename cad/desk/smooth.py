#!/usr/bin/env python3
"""Desk housing, track A ("smooth"): v1's architecture (one-piece shell open at the bottom + flat magnetic lid, board
taped to the front wall, battery taped behind the board, MOGOOD 90 deg USB-C adapter in the board's port) in a new
outer form: the front runs into the top through an R15 roll, rear vertical corners R10, one R5 chain round the front
edges, over the roll, along the top and round the top-rear edge. Two variants:
  upright  front vertical
  tilt15   front leaning back 15 deg, top level, back vertical (a trapezoid in the side view); the lid continues the
           front slope and its toe is rounded. Everything that was parallel to the front in v1 (glass, board, rods,
           battery, the insertion moves, the adapter's plug axis) is parallel to the tilted front.

Frames: world X right (seen from the front), Y front -> back, Z up, shell rim at z = 0, lid below it, desk at z = -LID_T.
The body frame (x, t, s) leans with the front: t = depth behind the front's outer face, s = along the face, measured
from where the face meets the rim plane. world y = t cos + s sin, z = -t sin + s cos (a rotation about X).

Checks raise instead of exporting: static overlap of every pair of bodies, the swept insertion paths, rod / slot fits,
face margins, minimum wall (measured between the cavity and the outer surface on the solids), magnet meat (measured on
sections of the solids), logo fit, USB hole / cable notch, single valid solids, watertight STLs.

Run: ~/.venvs/cad/bin/python cad/desk/smooth.py [upright|tilt15 ...]   then   ~/.venvs/cad/bin/python cad/desk/render_smooth.py
"""
import sys, math, pathlib
import numpy as np

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import housing as hw                                   # hardware numbers + helpers (its __main__ does not run)
from build123d import (Box, Cylinder, Pos, Plane, Polygon, Polyline, RectangleRounded, Rectangle, Compound, Color,
                       BuildSketch, BuildLine, make_face, fillet, extrude, export_step, export_stl, Axis, Align,
                       GeomType, ShapeList, Vector, Face, CenterOf)
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.gp import gp_Pln, gp_Pnt, gp_Dir
from OCP.GeomAbs import GeomAbs_Cylinder

check, volume_common, gap = hw.check, hw.volume_common, hw.gap
OUT_ROOT = HERE / "out-smooth"

# ---- parameters (mm) -----------------------------------------------------------------------------------------
W = 50.0
WALL, BACK, TOP_T = 3.0, 3.0, 3.0      # side walls, back wall, top wall (the front comes from the slot type)
R_ROLL = 15.0                          # front -> top, outer radius
R_REAR = 10.0                          # rear vertical corners, in plan
R_EDGE = 5.0                           # the tangent chain: front edges, over the roll, top sides, top-rear edge
R_IN = 3.0                             # cavity: the ceiling's side edges
R_IN_FRONT = 4.5                       # cavity front corners (along the face): sized for the front magnets' meat (R3 0.41,
                                       # R4 0.61, R4.5 0.72 on the upright E build); the
                                       # front wall's inner flat must stay >= glass + 0.6
R_IN_REAR = 8.5                        # cavity rear corners. R3 inside R10 would leave 1.34 of wall on the diagonal;
                                       # R7 (concentric) gives 3.0 but a 2.5 rim (0.2 magnet meat); 8.5 gives ~0.5 meat
CEIL_JOIN_R = 2.0                      # 2D roundings where the ceiling's straight pieces meet
GLASS_SEAT = 0.5                       # the front's inner face runs flat at least this far past the glass's top end
REAR_CHAMFER = 4.0                     # 45 deg at the back of the ceiling: shortens the bridge, thickens the top-rear edge
BRIDGE_MAX = 20.0
BOTTOM_BREAK = 0.5
LID_T, TOE_R = 3.0, 2.0                # lid; the tilted lid's toe round
SLOT_TYPE = "E"                        # E: 3 mm front, 45 deg bevel to a SLOT_LAND land (user, round 2); F: 4 mm front, bevel to a 1 mm rim
SLOT_LAND = 0.6                        # E: straight land at the inner face before the bevel starts. Print test 2026-11-19: the
                                       # bevel ran to a knife edge (0 rim) the 0.4 nozzle cannot print; 8.2 slots measured 9.0
FRONT_BY_SLOT = {"F": (4.0, 1.0), "E": (3.0, SLOT_LAND)}
SLOT_W = 8.1                           # print test 2026-11-19: rods measured 8.0, snug fit wanted (8.2 + knife edge gave 9.0)
ROD_PLAY_MIN = 0.1                     # slot width over the rod, at least (0.4 before the X1E, 0.2 until the 2026-11-19 test)
ROD_L = hw.TS_FLAT_ROD_L               # 66.65: rods cut 1 mm shorter than the lit length
SLOT_L = ROD_L + hw.TS_FLAT_PLAY       # 66.85
FACE_TOP_FLAT_MIN = 3.0                # flat face between the slot's top end and the roll's tangent line
FACE_SIDE_FLAT_MIN, FACE_BRIDGE_MIN = 2.0, 4.0
INSERT_CLR = hw.INSERT_CLR             # rod apex to the front wall's inner face during the up move
INSERT_SHIFT = hw.ROD_H + hw.TAPE[1] - hw.GASKET + INSERT_CLR   # 4.0 (v1's 4.5 ignored the gasket)
SPARE_MIN = hw.INSERT_SPARE_MIN        # measured gap behind the battery during the up move
Z_STOP = hw.CAR_TOP_GAP                # overshoot past the seat tested on the up move. The forward move has none: the
                                       # rods are 0.2 shorter than the slots, so they must be within +-0.1 along the face
WALL_MIN = 3.0
BAT_ADAPTER_MIN = 1.0                  # battery taped low (BAT_LOW): to the adapter / plug head, and to the lid
ORDERS = {                             # assembly order (--order=...); the first is built by default
    "battery-after": "board + rods (no battery) in as v1 (back, up, forward); then the battery up behind the seated board, "
                     "held BAT_HOLD further back, and forward onto the board",
    "v1": "board + rods + battery in together (back, up, forward), as v1",
    "rods-after": "board + battery up with no backward shift; the rods pushed in through the slots afterwards",
}
ORDER = "battery-after"
BAT_HOLD = 0.5                         # battery-after: how far behind its seat the battery travels up
BAT_SPARE_AFTER = 0.5                  # battery-after: clearance round the battery's sweep, at least
LOGO_SKIN = 1.0                        # skin left over a pocketed (glow-through) logo; print test 2026-11-19: 0.6 showed from
                                       # outside (lighter rectangle, sink lines where the wall stepped 3.0 -> 0.6)
LOGO_FLARE_DEG = 45.0                  # the pocket's two vertical sides slope this much from the wall's normal, widening from the
                                       # floor to the inner face (wall thins gradually; 2026-11-19 sink lines); top / bottom straight
LOGO_MARGIN = hw.LOGO_MARGIN
# Logo style. "cut": the letters cut through the wall, translucent inlays pressed in (round 1). Printed standing, its
# strips start in mid-air (cantilevers, islands): they failed on the coupons of 2026-11-17. "stencil": one plain
# rounded-rectangle pocket from inside behind a LOGO_SKIN skin, and a flat-printed stencil of the logo (painted black)
# pushed into it; the LEDs light the skin through the letters (user, 2026-11-18).
LOGO_STYLE = "stencil"
STENCIL_MARGIN = 1.0                   # pocket beyond the letters' box, all round
STENCIL_R = 1.0                        # pocket corner radius, seen through the wall
STENCIL_CLR = 0.10                     # stencil to pocket, per side, in the stencil's plane (paint adds a few hundredths)
STENCIL_CLR_TOP = 0.30                 # ... at the pocket's top: its ceiling is a bridge when printed standing, it may sag
STENCIL_BACK = 0.10                    # the stencil's back face this far inside the pocket's mouth
STENCIL_STRIPS = {"front": (None, 1.0, 1.4), "side": (None, 1.6, 2.0)}   # strip width per stencil (None: as designed)
NOTCH_W, NOTCH_H = 5.6, 6.0            # cable notch (tilt15): for a cable up to 5, open at the rim, closed by the lid
CABLE_D = 5.0
PLUG_LEN_A, PLUG_T_A, PLUG_W_A = 25.0, 6.5, 12.0   # a straight USB-C plug with its overmould (typ.)
DENSITY = 1.24                         # PLA, g/cm3
BOARD_G, BATTERY_G = 30.0, 55.0        # assumed
EPS_V = hw.EPS_V

VARIANTS = {
    # ADAPTER_FLOOR: the adapter's lowest point above the rim (sets the board's height). Upright keeps v1's 4 (the hole
    # sits on the adapter's axis); tilt15 takes its cable through a notch at the rim, so 1 is enough.
    "upright": dict(TILT=0.0, ADAPTER_FLOOR=4.0, TOTAL_MIN=109.0, LOGO_W=15.0, LOGO_MODE="front", LOGO_ZC=None, USB="hole", BAT_LOW=False),
    "tilt15": dict(TILT=15.0, ADAPTER_FLOOR=1.0, TOTAL_MIN=0.0, LOGO_W=24.0, LOGO_MODE="cut", LOGO_ZC=18.0 - LID_T, USB="notch", BAT_LOW=True),
}


# ---- small geometry helpers ------------------------------------------------------------------------------------
def box(x0, x1, y0, y1, z0, z1):
    return hw.box(min(x0, x1), max(x0, x1), y0, y1, z0, z1)


def near(lst, pt):
    return ShapeList(sorted(lst, key=lambda v: (v.center() - Vector(*pt)).length)[:1])


def yz_face(pts, rounds):
    """Polygon in the YZ plane (u = world Y, v = world Z); rounds = {vertex index: radius}."""
    with BuildSketch(Plane.YZ) as sk:
        with BuildLine():
            Polyline(*pts, close=True)
        make_face()
        for i, r in rounds.items():
            fillet(near(sk.vertices(), (*pts[i], 0)), r)
    return sk.sketch


def unique(edges):
    out = []
    for e in edges:
        if not any(e.is_same(u) for u in out):
            out.append(e)
    return out


def dist_shapes(a, b):
    d = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    d.Perform()
    p = d.PointOnShape1(1)
    return d.Value(), (p.X(), p.Y(), p.Z())


def flared_block(pl, w, h, r, depth, k, dy=0.0):
    """A w x h rounded rectangle on plane pl (centre (0, dy) in its coordinates) grown `depth` along pl's normal while
    its two ends (the sides along pl's y) move out by k per mm, top and bottom straight: the union of two oblique prisms
    of the rectangle, one leaning each way (exact while k depth <= w / 2 - r; build123d's loft twists the corner pairing)."""
    check(k * depth <= w / 2 - r + 1e-9, "flared block: too deep for its width")
    f0 = pl * Pos(0, dy) * RectangleRounded(w, h, r)
    ln = depth * math.sqrt(1 + k * k)
    b = None
    for sg in (1, -1):
        p_ = extrude(f0, ln, dir=tuple((pl.z_dir + pl.x_dir * (sg * k)).normalized()))
        b = p_ if b is None else b + p_
    b = b.clean()
    v_want = depth * (w + k * depth) * h - depth * (4 - math.pi) * r * r
    check(b.is_valid and len(b.solids()) == 1 and abs(b.volume - v_want) < 1e-6 * v_want, "flared block invalid")
    return b


def section_segments(shape, z, bbox=None, step=0.05):
    """Section of a solid by the plane z: its boundary as 2D segments (N, 4)."""
    sec = BRepAlgoAPI_Section(shape.wrapped, gp_Pln(gp_Pnt(0, 0, z), gp_Dir(0, 0, 1)))
    sec.Build()
    edges = Compound(sec.Shape()).edges()
    if not edges:                    # the plane section comes back empty on some boolean results (oval): use the bottom
        sl = shape & box(-500, 500, -500, 500, z, z + 0.002)      # face of a thin slab instead
        edges = [e for f in sl.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6 for e in f.edges()]
        check(len(edges) > 0, f"no section at z {z}")
    segs = []
    for e in edges:
        n = max(2, int(e.length / step) + 1)
        p = np.array([[q.X, q.Y] for q in (e.position_at(i / (n - 1)) for i in range(n))])
        s = np.hstack([p[:-1], p[1:]])
        if bbox is not None:
            x0, x1, y0, y1 = bbox
            k = (np.maximum(s[:, 0], s[:, 2]) >= x0) & (np.minimum(s[:, 0], s[:, 2]) <= x1) & \
                (np.maximum(s[:, 1], s[:, 3]) >= y0) & (np.minimum(s[:, 1], s[:, 3]) <= y1)
            s = s[k]
        segs.append(s)
    return np.vstack(segs)


def seg_dist(pts, segs):
    a, ab = segs[:, :2], segs[:, 2:] - segs[:, :2]
    l2 = np.maximum((ab ** 2).sum(1), 1e-12)
    ap = pts[:, None, :] - a[None]
    t = np.clip((ap * ab[None]).sum(2) / l2[None], 0, 1)
    d = ap - t[..., None] * ab[None]
    return np.sqrt((d ** 2).sum(2)).min(1)


def inside(pts, segs):
    """Even-odd rule on the whole section (holes included). Exact only if the segments were not clipped near pts."""
    x, y = pts[:, 0][:, None], pts[:, 1][:, None]
    x1, y1, x2, y2 = segs.T
    dy = np.where(np.abs(y2 - y1) < 1e-15, 1e-15, y2 - y1)
    cross = ((y1 <= y) != (y2 <= y)) & (x < x1 + (y - y1) * (x2 - x1) / dy)
    return cross.sum(1) % 2 == 1


# ---- the model -------------------------------------------------------------------------------------------------
class Model:
    def __init__(self, name, D, r_in_rear=R_IN_REAR):
        cfg = VARIANTS[name]
        self.name, self.cfg, self.D, self.R_IN_REAR = name, cfg, D, r_in_rear
        self.tilt = cfg["TILT"]
        th = math.radians(self.tilt)
        c, sn = self.c, self.sn = math.cos(th), math.sin(th)
        # oval: the front's inner face is flat at FRONT behind a curved face; its slot bevel runs from a SLOT_LAND land there
        self.FRONT, self.RIM = (cfg["FRONT"], SLOT_LAND) if cfg.get("FRONT") else FRONT_BY_SLOT[SLOT_TYPE]
        self.BEVEL_D = self.FRONT - self.RIM
        self.BEVEL_W = self.BEVEL_D * math.tan(math.radians(hw.BEVEL_DEG))
        # stack, in t (behind the front's outer face)
        self.GLASS_T0 = self.FRONT + hw.GASKET
        self.GLASS_T1 = self.GLASS_T0 + hw.GLASS_T
        self.BOARD_T1 = self.GLASS_T0 + hw.BOARD_T
        self.PORT_T = self.BOARD_T1 - hw.PORT_Y_FROM_BOARD_BACK
        self.AD_T = (self.PORT_T - hw.ADAPTER_BEHIND, self.PORT_T - hw.ADAPTER_BEHIND + hw.ADAPTER_L)
        self.BAT_T = (self.BOARD_T1 + 0.1, self.BOARD_T1 + 0.1 + hw.BAT_T)
        # board height: the adapter's lowest point (its far, bottom edge) ADAPTER_FLOOR above the rim
        s_low = (cfg["ADAPTER_FLOOR"] + self.AD_T[1] * sn) / c
        self.PCB_S0 = math.ceil((s_low + hw.ADAPTER_COLLAR + hw.ADAPTER_T) * 10 - 1e-6) / 10
        self.PCB_S1 = self.PCB_S0 + hw.PCB_H
        self.AD_S = (self.PCB_S0 - hw.ADAPTER_COLLAR - hw.ADAPTER_T, self.PCB_S0)
        self.SOCKET_S = self.PCB_S0 - hw.ADAPTER_COLLAR - hw.ADAPTER_T / 2
        self.AA_SC = self.PCB_S0 + hw.AA_Z_FROM_PCB_BOTTOM + hw.AA_H / 2
        self.SLOT_S = (self.AA_SC - SLOT_L / 2, self.AA_SC + SLOT_L / 2)
        self.ROD_S = (self.AA_SC - ROD_L / 2, self.AA_SC + ROD_L / 2)
        if cfg["BAT_LOW"]:      # taped as low as it goes: BAT_ADAPTER_MIN above the adapter (its box reaches the PCB edge)
            self.BAT_S0 = self.PCB_S0 + BAT_ADAPTER_MIN
        else:                   # v1: centred on the board's height
            self.BAT_S0 = self.PCB_S0 + (hw.PCB_H - hw.BAT_H) / 2
        bat_low_z = self.to_world(self.BAT_T[1], self.BAT_S0)[1]                # its lowest edge (back, bottom)
        check(bat_low_z >= BAT_ADAPTER_MIN, f"battery {bat_low_z:.2f} above the lid")
        self.GLASS_S0 = self.PCB_S0 + (hw.PCB_H - hw.GLASS_H) / 2
        self.GLASS_TOP = self.GLASS_S0 + hw.GLASS_H
        # height: the roll's tangent line FACE_TOP_FLAT_MIN above the slot's top end, in 0.5 steps, at least TOTAL_MIN
        self.TAN_LEN = R_ROLL * math.tan(math.radians(90 - self.tilt) / 2)    # roll tangent points to the virtual corner
        h_min = (self.SLOT_S[1] + FACE_TOP_FLAT_MIN) * c + R_ROLL * (1 - sn)   # from s_tangent = (H - R(1 - sin)) / cos
        # ... and the front's inner face must run flat to GLASS_SEAT above the glass's top end before the ceiling ramp
        # starts; the highest it may go with WALL_MIN under the roll is where it leaves the roll's 3 mm offset
        self.DS_MAX = math.sqrt(max((R_ROLL - WALL_MIN) ** 2 - (R_ROLL - self.FRONT) ** 2, 0.0))
        self.FOOT_TAN = CEIL_JOIN_R * math.tan(math.radians(45 - self.tilt) / 2)   # the foot's rounding, along the face
        s_need = self.GLASS_TOP + GLASS_SEAT + self.FOOT_TAN - self.DS_MAX
        h_min = max(h_min, s_need * c + R_ROLL * (1 - sn))
        self.H = max(math.ceil(h_min * 2 - 1e-9) / 2, cfg["TOTAL_MIN"] - LID_T)
        self.S_TANGENT = (self.H - R_ROLL * (1 - sn)) / c
        self.ROLL_C = self.to_world(R_ROLL, self.S_TANGENT)                    # roll centre (y, z)
        self.Y_VIRT = self.H * sn / c                                          # virtual top-front corner
        self.TOE_Y = -LID_T * sn / c
        self._cache = {}

    # frames
    def to_world(self, t, s):
        return (t * self.c + s * self.sn, -t * self.sn + s * self.c)

    def to_body(self, y, z):
        return (y * self.c - z * self.sn, y * self.sn + z * self.c)

    def wt(self, shape):
        return shape.rotate(Axis.X, -self.tilt) if self.tilt else shape

    def front_out_y(self, x, z):
        """World y of the outer front surface at (x, z), on its flat part (the oval overrides it)."""
        return self.y_front(z)

    def y_front(self, z, t=0.0):
        """World y of the plane t (parallel to the front) at height z."""
        return (t + z * self.sn) / self.c

    # ---- outer form ----
    def outer_body(self):
        """Shell + lid as one solid (z from -LID_T to H): side profile with the roll, R10 rear corners, the R5 chain."""
        if "outer" in self._cache:
            return self._cache["outer"]
        D, H = self.D, self.H
        pts = [(self.TOE_Y, -LID_T), (self.Y_VIRT, H), (D, H), (D, -LID_T)]
        body = extrude(yz_face(pts, {1: R_ROLL}), W / 2, both=True)
        rear = [e for e in body.edges().filter_by(Axis.Z) if abs(abs(e.center().X) - W / 2) < 1e-6 and abs(e.center().Y - D) < 1e-6]
        check(len(rear) == 2, "rear vertical edges not found")
        body = body.fillet(R_REAR, rear)
        chain = []
        y_top_seam = self.ROLL_C[0]
        for f in body.faces():
            if f.geom_type != GeomType.PLANE:
                continue
            n = f.normal_at()
            if abs(abs(n.X) - 1) < 1e-6:                   # side faces: front edge, roll, top; not the bottom / rear seam
                for e in f.edges():
                    ps = [e.position_at(t) for t in (0, .5, 1)]
                    if all(abs(p.Z + LID_T) < 1e-6 for p in ps):
                        continue
                    if e.geom_type == GeomType.LINE and all(abs(p.Y - (D - R_REAR)) < 1e-4 for p in ps):
                        continue
                    chain.append(e)
            elif n.Z > 1 - 1e-6:                           # top: sides, round the rear corners, back; not the roll seam
                for e in f.edges():
                    ps = [e.position_at(t) for t in (0, .5, 1)]
                    if e.geom_type == GeomType.LINE and all(abs(p.Y - y_top_seam) < 1e-4 for p in ps):
                        continue
                    chain.append(e)
        chain = unique(chain)
        check(len(chain) == 9, f"R5 chain: {len(chain)} edges selected, expected 9")
        body = body.fillet(R_EDGE, chain)
        check(body.is_valid and len(body.solids()) == 1, "outer body invalid after the R5 chain")
        self._cache["outer"] = body
        return body

    def shell_env(self):
        """The shell's outer solid (z >= 0), before the bottom break: the reference for the wall measurement."""
        if "env" not in self._cache:
            big = 400
            self._cache["env"] = self.outer_body() & box(-big, big, -big, big, 0, big)
        return self._cache["env"]

    def lid_env(self):
        big = 400
        return self.outer_body() & box(-big, big, -big, big, -LID_T, 0)

    def ceiling(self):
        """Cavity side profile (y, z): the front's inner face, a 45 deg ramp under the roll, a flat ceiling (a bridge in Y),
        45 deg down to the back wall; printed standing on the rim. Only the flat and the small join roundings pass 45 deg.
        The ramp's foot sits on the front's inner plane between GLASS_SEAT above the glass and the highest point the
        roll's 3 mm offset allows; the ramp runs up at 45 deg until it meets that offset (or the top wall's underside), and
        the flat ceiling continues from there, so it may sit lower than H - TOP_T (a thicker top). The foot that gives
        the highest ceiling is used."""
        if "ceil" in self._cache:
            return self._cache["ceil"]
        F = self.FRONT
        zt, (yc, zr) = self.H - TOP_T, self.ROLL_C
        ra = R_ROLL - WALL_MIN - 0.01                         # the roll's 3 mm offset (0.01 inside it)
        yb = self.D - BACK
        s_lo = self.GLASS_TOP + GLASS_SEAT + self.FOOT_TAN   # foot vertex (the rounding's tangent point is FOOT_TAN lower)
        s_hi = self.S_TANGENT + self.DS_MAX - 0.02
        check(s_hi >= s_lo - 1e-6, f"no room for the ceiling ramp's foot: s {s_lo:.2f}..{s_hi:.2f}")

        def ramp_top(sf):
            p = self.to_world(F, sf)
            v = zt - p[1]                                     # up to the top wall's underside
            # where the 45 deg ray (1, 1) leaves the offset circle: |p + v (1, 1) - C| = ra
            dy, dz = p[0] - yc, p[1] - zr
            b_, c_ = dy + dz, dy * dy + dz * dz - ra * ra
            disc = b_ * b_ - 2 * c_
            if disc >= 0:
                vc = (-b_ + math.sqrt(disc)) / 2
                if p[0] + vc < yc:                            # it leaves the offset while still under the roll
                    v = min(v, vc)
            return p, (p[0] + v, p[1] + v)

        best = None
        for i in range(201):
            sf = s_lo + (s_hi - s_lo) * i / 200
            p1, p2 = ramp_top(sf)
            if best is None or p2[1] > best[2][1] + 1e-9:
                best = (sf, p1, p2)
        sf, p1, p2 = best
        zc = p2[1]
        tail = [(yb - REAR_CHAMFER, zc), (yb, zc - REAR_CHAMFER), (yb, -1.0)]
        pts = [(self.y_front(-1, F), -1.0), p1, p2] + tail
        face = yz_face(pts, {i: CEIL_JOIN_R for i in (1, 2, 3, 4)})
        k22 = CEIL_JOIN_R * math.tan(math.radians(22.5))
        info = dict(foot=p1, top=p2, z_ceil=zc, flat_end=sf - self.FOOT_TAN,
                    bridge=(yb - REAR_CHAMFER - k22) - (p2[0] + k22),
                    text=f"45 deg ramp under the roll from ({p1[0]:.2f}, {p1[1]:.2f}) to ({p2[0]:.2f}, {p2[1]:.2f}) (y, z), "
                         f"flat ceiling at z {zc:.2f} (top wall {self.H - zc:.2f} thick there)")
        self._cache["ceil"] = (face, info)
        return face, info

    def cavity(self):
        if "cav" in self._cache:
            return self._cache["cav"]
        face, _ = self.ceiling()
        half = W / 2 - WALL
        prism = extrude(face, half, both=True)
        sides = []
        for f in prism.faces():
            if f.geom_type == GeomType.PLANE and abs(abs(f.normal_at().X) - 1) < 1e-6:
                sides += [e for e in f.edges() if not all(abs(e.position_at(t).Z + 1) < 1e-6 for t in (0, .5, 1))]
        prism = prism.fillet(R_IN, unique(sides))     # the ceiling's side edges (one tangent chain per side; R_IN everywhere)
        plan = box(-half, half, -80, self.D - BACK, -2, self.H + 2)
        rear = [e for e in plan.edges().filter_by(Axis.Z) if e.center().Y > self.D - BACK - 1e-6]
        plan = plan.fillet(self.R_IN_REAR, rear)      # rear corners, vertical
        fr = box(-half, half, self.FRONT, self.FRONT + 200, -60, self.H / self.c + 60)      # body frame
        fe = [e for e in fr.edges().filter_by(Axis.Z) if e.center().Y < self.FRONT + 1e-6]
        fr = self.wt(fr.fillet(R_IN_FRONT, fe))      # front corners, along the face
        cav = prism & plan & fr
        check(cav.is_valid and len(cav.solids()) == 1, "cavity invalid")
        self._cache["cav"] = cav
        return cav

    def slot_cutter(self, x):
        """Flat-end slot (body frame): straight SLOT_W x SLOT_L through the front, 45 deg on the long sides only from the
        face down to a straight land RIM deep at the inner face (E: SLOT_LAND); the two ends are straight walls."""
        w, l, d, g = SLOT_W, SLOT_L, self.BEVEL_D, self.BEVEL_W
        s0 = self.SLOT_S[0]
        cut = box(x - w / 2, x + w / 2, -1, self.FRONT + 1, s0, s0 + l)
        if d > 0:
            over = 0.5
            go = g * (d + over) / d
            vee = Polygon((x - w / 2 - go, -over), (x + w / 2 + go, -over), (x + w / 2, d), (x - w / 2, d), align=None)
            cut += Pos(0, 0, s0) * extrude(vee, l)
        return self.wt(cut)

    def usb_cutter(self):
        D = self.D
        if self.cfg["USB"] == "hole":
            z = self.to_world(0, self.SOCKET_S)[1]
            return Pos(0, D - BACK / 2, z) * extrude(Plane.XZ * RectangleRounded(hw.USB_HOLE_W, hw.USB_HOLE_H, hw.USB_HOLE_R),
                                                     BACK / 2 + 1, both=True)
        r = NOTCH_W / 2
        zc = NOTCH_H - r
        n = box(-r, r, D - BACK - 1, D + 1, -1, zc)
        return n + Pos(0, D - BACK - 1, zc) * Cylinder(r, BACK + 2, rotation=(-90, 0, 0), align=(Align.CENTER, Align.CENTER, Align.MIN))

    # ---- logo ----
    def pocket(self):
        """The glow-through pocket (LOGO_STYLE "stencil"): pw x ph R STENCIL_R at its flat floor (LOGO_SKIN behind the
        outer surface where that comes closest), the two vertical sides sloped LOGO_FLARE_DEG out to the wall's inner face,
        top and bottom straight; then the mouth straight on POCKET_OVER into the cavity (on tilt15 the mouth runs past the
        inner side flat into the cavity's corner rounds: there it cuts a short straight notch, so the stencil goes in).
        plane: on the floor, z into the cavity, y = world +Z."""
        if "pocket" in self._cache:
            return self._cache["pocket"]
        if self.cfg["LOGO_MODE"] == "front":
            w = FRONT_LOGO_W
            h = hw.LETTERS_ASPECT * w
            zc = (FRONT_LOGO_RIM + self.GLASS_S0 - FRONT_LOGO_GLASS) / 2
            pw, ph = w + 2 * STENCIL_MARGIN, h + 2 * STENCIL_MARGIN
            # the oval's face curves back towards the sides: its skin is thicker on the centre line
            floor = LOGO_SKIN + max(self.front_out_y(x, z) for x in np.linspace(-pw / 2, pw / 2, 81)
                                    for z in (zc - ph / 2, zc, zc + ph / 2))
            pl = Plane(origin=(0, floor, zc), x_dir=(-1, 0, 0), z_dir=(0, 1, 0))
            depth = self.FRONT - floor
            wall_box = box(-60, 60, -10, self.FRONT, -5, 60)
            ctr = 0.0
        else:
            L = self.logo_layout()
            side = hw.LOGO_SIDE
            pw, ph, zc = L["w"] + 2 * STENCIL_MARGIN, L["h"] + 2 * STENCIL_MARGIN, L["zc"]
            floor = side * (W / 2 - LOGO_SKIN)
            pl = Plane(origin=(floor, L["yc"], zc), x_dir=(0, -side, 0), z_dir=(-side, 0, 0))
            depth = WALL - LOGO_SKIN
            wall_box = box(side * (W / 2 + 5), side * (W / 2 - WALL), -10, self.D + 10, -5, self.H + 5)
            ctr = L["yc"]
        k = math.tan(math.radians(LOGO_FLARE_DEG))
        mw = pw + 2 * k * depth
        cut = flared_block(pl, pw, ph, STENCIL_R, depth, k) + extrude(pl.offset(depth) * RectangleRounded(mw, ph, STENCIL_R), POCKET_OVER)
        check(cut.is_valid and len(cut.solids()) == 1, "logo pocket cutter invalid")
        res = dict(pl=pl, pw=pw, ph=ph, zc=zc, floor=floor, depth=depth, k=k, ctr=ctr, wall_box=wall_box,
                   mouth=(mw, ph), cut=cut)
        self._cache["pocket"] = res
        return res

    def logo_layout(self):
        """LOGO_W is the letters' width at most; on a flat too short for it (skin logo) they shrink in 0.5 steps to fit
        with LOGO_MARGIN at both ends."""
        if self.cfg["LOGO_ZC"] is None:                 # v1: centre 4 above the tubes' mid-height
            zc = self.to_world(0, self.AA_SC)[1] + hw.LOGO_Z_ABOVE_TUBES
        else:
            zc = self.cfg["LOGO_ZC"]
        w = self.cfg["LOGO_W"]
        while True:
            h = hw.LETTERS_ASPECT * w
            ztop = zc + h / 2
            flat0 = self.y_front(ztop) + R_EDGE / self.c  # the side flat starts where the front's R5 ends (at the letters' top)
            flat1 = self.D - R_REAR
            if flat1 - flat0 - w >= 2 * LOGO_MARGIN - 1e-6 or self.cfg["LOGO_MODE"] == "cut" or w <= 8:
                break
            w -= 0.5
        # centred on the outer flat, moved (within the margins) onto the inner 3 mm flat if it fits there, so cut letters
        # go through a wall of constant thickness (the inlays seat fully)
        in0, in1 = self.y_front(ztop, self.FRONT + R_IN_FRONT), self.D - BACK - self.R_IN_REAR
        lo, hi = flat0 + LOGO_MARGIN + w / 2, flat1 - LOGO_MARGIN - w / 2
        a_, b_ = max(lo, in0 + w / 2), min(hi, in1 - w / 2)
        if a_ > b_:
            a_, b_ = lo, hi                         # the inner flat is too short: keep the outer margins only
        yc = min(max((flat0 + flat1) / 2, a_), b_) if a_ <= b_ else (flat0 + flat1) / 2
        return dict(w=w, h=h, yc=yc, zc=zc, y=(yc - w / 2, yc + w / 2), z=(zc - h / 2, zc + h / 2),
                    flat=(flat0, flat1), margin=min(yc - w / 2 - flat0, flat1 - yc - w / 2), letters=hw.letters_mm(w))

    def front_logo(self):
        """One small logo cut through the front, centred on x 0 under the tubes (upright and oval). The letters' size is
        shared (FRONT_LOGO_W); they sit centred between FRONT_LOGO_RIM above the rim and FRONT_LOGO_GLASS below the glass.
        Where the front is thicker than the inlay (oval), a flat recess on the inside, the letters' box + FRONT_LOGO_RECESS
        all round, leaves FRONT_LOGO_T on the centre line."""
        if "flogo" in self._cache:
            return self._cache["flogo"]
        w = FRONT_LOGO_W
        h = hw.LETTERS_ASPECT * w
        zlo, zhi = FRONT_LOGO_RIM, self.GLASS_S0 - FRONT_LOGO_GLASS
        zc = (zlo + zhi) / 2
        pl = Plane(origin=(0, -3.0, zc), x_dir=(1, 0, 0), z_dir=(0, -1, 0))     # seen from the front: x right, z up
        cut, floor, pocket = None, None, None
        if LOGO_STYLE == "stencil":
            # one rounded-rectangle pocket from inside; its flat floor LOGO_SKIN behind the outer surface where that
            # comes closest (the oval's face curves back towards the sides: its skin is thicker on the centre line)
            P = self.pocket()
            cut, floor, pocket = P["cut"], P["floor"], (P["pw"], P["ph"])
        else:
            for poly in hw.letters_mm(w):
                e = extrude(pl * Polygon(*[(u, v) for u, v in poly], align=None), self.FRONT + 5.0, dir=(0, 1, 0))
                cut = e if cut is None else cut + e
        recess = None
        if self.FRONT > FRONT_LOGO_T + 1e-6:
            m_ = FRONT_LOGO_RECESS
            recess = box(-w / 2 - m_, w / 2 + m_, FRONT_LOGO_T, self.FRONT + 1.0, zc - h / 2 - m_, zc + h / 2 + m_)
        res = dict(w=w, h=h, zc=zc, z=(zc - h / 2, zc + h / 2), cut=cut, recess=recess, floor=floor, pocket=pocket,
                   inner_y=FRONT_LOGO_T if recess is not None else self.FRONT)
        self._cache["flogo"] = res
        return res

    def logo_cutters(self):
        if self.cfg["LOGO_MODE"] == "front":
            fl = self.front_logo()
            return [fl["cut"]] + ([fl["recess"]] if fl["recess"] is not None else [])
        L = self.logo_layout()
        side = hw.LOGO_SIDE
        if LOGO_STYLE == "stencil":                 # one rounded-rectangle pocket from inside, LOGO_SKIN under the side flat
            return [self.pocket()["cut"]]
        x0 = side * (W / 2 + 1) if self.cfg["LOGO_MODE"] == "cut" else side * (W / 2 - LOGO_SKIN)
        depth = (W / 2 + 1 - 12.0) if self.cfg["LOGO_MODE"] == "cut" else (W / 2 - LOGO_SKIN - 12.0)
        cuts = []
        for poly in L["letters"]:
            f = Plane.YZ.offset(x0) * Polygon(*[(L["yc"] + side * u, L["zc"] + v) for u, v in poly], align=None)
            cuts.append(extrude(f, -side * depth))
        return cuts

    # ---- parts ----
    def shell(self, level="full", magnets=None):
        """level: body (outer - cavity), core (+ slots + USB: the obstacle for the path checks), full (+ logo + magnets)."""
        key = ("shell", level)
        if key in self._cache:
            return self._cache[key]
        s = self.shell_env()
        bottom = [f for f in s.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6 and abs(f.center().Z) < 1e-6]
        check(len(bottom) == 1, "shell bottom face")
        s = s.chamfer(BOTTOM_BREAK, None, bottom[0].edges())
        s = s - self.cavity()
        if level != "body":
            for sx in (-1, 1):
                s = s - self.slot_cutter(sx * hw.TUBE_CC / 2)
            s = s - self.usb_cutter()
        if level == "full":
            for c in self.logo_cutters():
                s = s - c
            for (x, y), _ in magnets:
                s = s - Pos(x, y, 0) * Cylinder((hw.MAG_D + hw.MAG_CLR_D) / 2, hw.MAG_H + hw.MAG_CLR_H,
                                                align=(Align.CENTER, Align.CENTER, Align.MIN))
        self._cache[key] = s
        return s

    def lid_blank(self):
        if "lid" in self._cache:
            return self._cache["lid"]
        l = self.lid_env()
        bottom = [f for f in l.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6]
        check(len(bottom) == 1, "lid bottom face")
        edges = bottom[0].edges()
        if not self.tilt:
            l = l.chamfer(BOTTOM_BREAK, None, edges)
        else:                                       # toe R2 along the front, R2 -> 0.5 round the front corners, 0.5 elsewhere
            # the bottom loop is one tangent contour: add it once, then set the radius edge by edge (constant, or linear
            # from the lower to the higher relative abscissa along the contour)
            from OCP.TopExp import TopExp
            from OCP.BRep import BRep_Tool
            yf = self.TOE_Y
            front = [e for e in edges if all(abs(e.position_at(t).Y - yf) < 1e-4 for t in (0, 1))]
            check(len(front) == 1, "lid: toe edge not found")
            mk = BRepFilletAPI_MakeFillet(l.wrapped)
            mk.Add(front[0].wrapped)
            check(mk.NbContours() == 1 and mk.NbEdges(1) == len(edges), "lid: bottom loop is not one contour")
            for j in range(1, mk.NbEdges(1) + 1):
                e = mk.Edge(1, j)
                v0, v1 = TopExp.FirstVertex_s(e, True), TopExp.LastVertex_s(e, True)
                a0, a1 = mk.RelativeAbscissa(1, v0), mk.RelativeAbscissa(1, v1)
                f0, f1 = (abs(BRep_Tool.Pnt_s(v).Y() - yf) < 1e-4 for v in (v0, v1))
                if f0 and f1:
                    mk.SetRadius(TOE_R, 1, j)
                elif f0 or f1:
                    r0, r1 = (TOE_R, BOTTOM_BREAK) if f0 else (BOTTOM_BREAK, TOE_R)
                    v0_low = a0 < a1 if abs(a0 - a1) < 0.5 else a0 > a1          # the contour may wrap at this edge
                    mk.SetRadius(*((r0, r1) if v0_low else (r1, r0)), 1, j)
                else:
                    mk.SetRadius(BOTTOM_BREAK, 1, j)
            mk.Build()
            check(mk.IsDone(), "lid toe fillet failed")
            from build123d import Solid
            l = Solid(mk.Shape())
        check(l.is_valid, "lid invalid after the bottom break")
        self._cache["lid"] = l
        return l

    def lid(self, magnets):
        l = self.lid_blank()
        for (x, y), _ in magnets:
            l = l - Pos(x, y, 0) * Cylinder((hw.MAG_D + hw.MAG_CLR_D) / 2, hw.MAG_H + hw.MAG_CLR_H,
                                            align=(Align.CENTER, Align.CENTER, Align.MAX))
        return l

    # ---- bodies (body frame boxes) ----
    def moving_bodies(self):
        m = [Body(self, "glass", (-hw.GLASS_W / 2, hw.GLASS_W / 2, self.GLASS_T0, self.GLASS_T1, self.GLASS_S0, self.GLASS_S0 + hw.GLASS_H)),
             Body(self, "board", (-hw.PCB_W / 2, hw.PCB_W / 2, self.GLASS_T1, self.BOARD_T1, self.PCB_S0, self.PCB_S1)),
             Rod(self, "rod-l", -hw.TUBE_CC / 2), Rod(self, "rod-r", hw.TUBE_CC / 2)]
        for n, z in hw.BTN_Z.items():
            m.append(Body(self, f"button-{n}", (hw.BTN_SIDE * hw.PCB_W / 2, hw.BTN_SIDE * (hw.PCB_W / 2 + hw.BTN_PROUD),
                                                self.GLASS_T1, self.GLASS_T1 + hw.BTN_DEPTH,
                                                self.PCB_S0 + z - hw.BTN_LEN / 2, self.PCB_S0 + z + hw.BTN_LEN / 2)))
        for n, z in hw.PLUG_Z.items():
            m.append(Body(self, f"plug-{n}", (-hw.BTN_SIDE * hw.PCB_W / 2, -hw.BTN_SIDE * (hw.PCB_W / 2 + hw.PLUG_PROUD),
                                              self.GLASS_T1, self.BOARD_T1,
                                              self.PCB_S0 + z - hw.PLUG_LEN / 2, self.PCB_S0 + z + hw.PLUG_LEN / 2)))
        m.append(Body(self, "battery", (-hw.BAT_W / 2, hw.BAT_W / 2, *self.BAT_T, self.BAT_S0, self.BAT_S0 + hw.BAT_H)))
        return m

    def adapter(self):
        return Body(self, "adapter", (-hw.ADAPTER_W / 2, hw.ADAPTER_W / 2, *self.AD_T, *self.AD_S))


class Body:
    """Box in the body frame (x, t, s). solid(dt, et, es0, es1): moved back by dt, stretched by et towards the back and
    by es0 / es1 down / up along the face: the volume swept on a straight move. Returned in the world frame."""

    def __init__(self, m, name, dims):
        self.m, self.name = m, name
        x0, x1, *rest = dims
        self.dims = (min(x0, x1), max(x0, x1), *rest)

    def solid(self, dt=0.0, et=0.0, es0=0.0, es1=0.0):
        x0, x1, t0, t1, s0, s1 = self.dims
        return self.m.wt(box(x0, x1, t0 + dt, t1 + dt + et, s0 - es0, s1 + es1))


class Rod(Body):
    """Half-round rod with its tape (thickest), flat on the glass, round side to the front."""

    def __init__(self, m, name, x, tape=hw.TAPE[1]):
        self.m, self.name, self.x, self.tape = m, name, x, tape

    def solid(self, dt=0.0, et=0.0, es0=0.0, es1=0.0):
        m, r = self.m, hw.ROD_W / 2
        tf = m.GLASS_T0 - self.tape + dt
        s0, s1 = m.ROD_S[0] - es0, m.ROD_S[1] + es1
        rod = Pos(self.x, tf, s0) * Cylinder(r, s1 - s0, align=(Align.CENTER, Align.CENTER, Align.MIN))
        rod -= box(self.x - r - 1, self.x + r + 1, tf, tf + r + 1, s0 - 1, s1 + 1)
        return m.wt(rod + box(self.x - r, self.x + r, tf - 0.01, tf + self.tape + et, s0, s1))


# ---- depth -----------------------------------------------------------------------------------------------------
ADAPTER_BACK_MIN = 0.5                 # adapter (seated) to the back wall, at least


def bat_sweeps(m, order, drop=200.0):
    """The battery's swept solids for an assembly order, and the clearance it needs."""
    bat = [b for b in m.moving_bodies() if b.name == "battery"][0]
    if order == "battery-after":
        return [("bat-up", bat.solid(dt=BAT_HOLD, es0=drop, es1=Z_STOP)), ("bat-fwd", bat.solid(et=BAT_HOLD))], BAT_SPARE_AFTER
    dt = INSERT_SHIFT if order == "v1" else 0.0
    return [("up", bat.solid(dt=dt, es0=drop, es1=Z_STOP))], SPARE_MIN


def depth_gaps(name, D, order, r_in_rear=R_IN_REAR):
    """At depth D, measured on the solid: (battery clearance on its sweeps, overshoot included; adapter clearance seated,
    to the nearest shell surface); a negative value = overlap volume."""
    m = Model(name, D, r_in_rear)
    try:
        s = m.shell("body")
        shape_ok = True
    except AssertionError:                     # so shallow that the rear corners eat the top's straight sides: not this
        shape_ok = False                       # shape any more; measure against the cavity's walls instead
        s = Compound([f for f in m.cavity().faces() if not (f.geom_type == GeomType.PLANE and abs(f.center().Z + 1) < 1e-6)])
    gb = math.inf
    for _, sw in bat_sweeps(m, order)[0]:
        v = volume_common(sw, s) if shape_ok else 0.0
        gb = min(gb, gap(sw, s) if v < EPS_V else -v)
    a = m.adapter().solid()
    va = volume_common(a, s) if shape_ok else 0.0
    ga = gap(a, s) if va < EPS_V else -va
    return gb, ga, shape_ok


def min_depth(name, order, r_in_rear=R_IN_REAR):
    """Smallest depth (0.5 steps) with the battery's clearance (BAT_SPARE_AFTER or SPARE_MIN) round its sweep and
    ADAPTER_BACK_MIN round the adapter, both measured on the solid. Returns D, gaps at D, gaps at D - 0.5, the limit."""
    m = Model(name, 40.0, r_in_rear)
    sws, need = bat_sweeps(m, order)
    ys = [v.Y for _, sw in sws for v in sw.vertices()]
    ya = [v.Y for v in m.adapter().solid().vertices()]
    D = math.floor(max(max(ys) + need, max(ya) + ADAPTER_BACK_MIN) * 2 + 2 * BACK) / 2   # plane estimate
    prev = depth_gaps(name, D - 0.5, order, r_in_rear)
    while True:
        g = depth_gaps(name, D, order, r_in_rear)
        if g[0] >= need - 1e-6 and g[1] >= ADAPTER_BACK_MIN - 1e-6 and g[2]:
            lim = [n for n, v, k in (("battery", prev[0], need), ("adapter", prev[1], ADAPTER_BACK_MIN)) if v < k - 1e-6]
            if not prev[2]:
                lim.append("outer shape (shallower, the rear corners swallow the top's straight sides)")
            return D, g, prev, " and ".join(lim) or "?"
        D, prev = D + 0.5, g


# ---- measurements on the solids --------------------------------------------------------------------------------
def magnet_search(m, shell_body, lid_blank):
    """Rim corners: the point farthest from the boundaries of both the shell's rim face (z = 0+, with the bottom break)
    and the lid's section at the depth of its hole. Returns [((x, y), meat)]."""
    z_lid = -(hw.MAG_H + hw.MAG_CLR_H)
    r_hole = (hw.MAG_D + hw.MAG_CLR_D) / 2
    s_all, l_all = section_segments(shell_body, 1e-3, step=0.5), section_segments(lid_blank, z_lid, step=0.5)
    out = []
    for sx in (-1, 1):
        for front in (True, False):
            cx = sx * (W / 2 - 3.0)
            cy = (m.y_front(0) + 2.0) if front else (m.D - 3.0)
            span = 12.0
            bb = (cx - span, cx + span, cy - span, cy + span)
            # coarse full sections for the inside test, fine clipped copies for the distances
            s_seg = section_segments(shell_body, 1e-3, bbox=bb)
            l_seg = section_segments(lid_blank, z_lid, bbox=bb)
            best = (-1, cx, cy)
            for _ in range(6):
                g = np.linspace(-span / 2, span / 2, 41)
                xs, ys = np.meshgrid(best[1] + g, best[2] + g)
                p = np.c_[xs.ravel(), ys.ravel()]
                ds = np.where(inside(p, s_all), seg_dist(p, s_seg), -1)
                dl = np.where(inside(p, l_all), seg_dist(p, l_seg), -1)
                d = np.minimum(ds, dl)
                k = int(np.argmax(d))
                best, span = (float(d[k]), float(p[k, 0]), float(p[k, 1])), span / 4
            out.append(((round(best[1], 2), round(best[2], 2)), best[0] - r_hole))
    return out


def classify_outer(env):
    groups = {}
    for f in env.faces():
        gt = f.geom_type
        if gt == GeomType.PLANE:
            n = f.normal_at()
            if n.Z < -1 + 1e-6:
                continue                                  # the rim face
            name = ("top" if n.Z > 1 - 1e-6 else "back" if n.Y > 1 - 1e-6 else "sides" if abs(abs(n.X) - 1) < 1e-6 else "front")
        elif gt == GeomType.CYLINDER:
            r = BRepAdaptor_Surface(f.wrapped).Cylinder().Radius()
            name = "roll R15" if abs(r - R_ROLL) < 1e-3 else "rear corners R10" if abs(r - R_REAR) < 1e-3 else "R5 chain"
        else:
            name = "R5 chain"
        groups.setdefault(name, []).append(f)
    return groups


def wall_measure(m):
    env, cav = m.shell_env(), m.cavity()
    cav_faces = Compound([f for f in cav.faces() if not (f.geom_type == GeomType.PLANE and abs(f.center().Z + 1) < 1e-6)])
    res = {}
    for name, fs in classify_outer(env).items():
        res[name] = dist_shapes(Compound(fs), cav_faces)
    return res


def front_face_margins(m, shell):
    """On the solid, in the body frame: the planar front face, its outer outline and the two slot openings."""
    s = shell.rotate(Axis.X, m.tilt) if m.tilt else shell
    fr = [f for f in s.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Y < -1 + 1e-6 and abs(f.center().Y) < 1e-4]
    check(len(fr) == 1, f"front face: {len(fr)} candidates")
    f = fr[0]
    ob = f.outer_wire().bounding_box()
    holes = sorted([w.bounding_box() for w in f.inner_wires()], key=lambda b: b.min.X)
    check(len(holes) == 2, "front face should have two slot openings")
    return dict(side=min(ob.max.X - holes[1].max.X, holes[0].min.X - ob.min.X), bridge=holes[1].min.X - holes[0].max.X,
                above=ob.max.Z - max(h.max.Z for h in holes), below=min(h.min.Z for h in holes),
                open_w=holes[0].max.X - holes[0].min.X, open_l=holes[0].max.Z - holes[0].min.Z, face_top=ob.max.Z)


SLOT_SECTIONS = 23                     # sections along each slot for the land measurement (about 3 mm apart)
LAND_DY = 0.01                         # depth step of the land measurement


def slot_land_measure(m, shell):
    """The slots' straight lands, measured on sections of the solid (body frame) at SLOT_SECTIONS heights along the
    slots (0.3 inside their ends): at depths LAND_DY apart from the inner face outwards, the slot's two walls (the
    section's crossings nearest the slot's axis); the land on each side runs as far as its wall stays within 0.002 of
    where it meets the inner face. Per slot: least and most width there, least land depth (both sides, every section).
    Also the seated rod's clearance to the shell with the thinnest and the thickest tape (the half-round is widest at its
    flat face, behind the inner face: the land's inner edge is where it comes closest)."""
    s = shell.rotate(Axis.X, m.tilt) if m.tilt else shell
    ys = m.FRONT - LAND_DY / 2 - LAND_DY * np.arange(int(1.5 / LAND_DY))
    res = {sx: dict(x=sx * hw.TUBE_CC / 2, w=[], depth=[]) for sx in (-1, 1)}
    for zs in np.linspace(m.SLOT_S[0] + 0.3, m.SLOT_S[1] - 0.3, SLOT_SECTIONS):
        seg = section_segments(s, float(zs), bbox=(-hw.TUBE_CC / 2 - 9, hw.TUBE_CC / 2 + 9, -2, m.FRONT + 0.5), step=0.02)
        for sx in (-1, 1):
            x0 = sx * hw.TUBE_CC / 2
            walls = []
            for y in ys:                                 # crossings of the line at depth y with the section
                x1, y1, x2, y2 = seg.T
                k = (np.minimum(y1, y2) <= y) & (np.maximum(y1, y2) > y)
                xc = x1[k] + (y - y1[k]) * (x2[k] - x1[k]) / (y2[k] - y1[k])
                lo, hi = xc[xc < x0], xc[xc > x0]
                check(lo.size and hi.size, f"slot at x {x0:+.2f}, s {zs:.2f}: no walls at depth {y:.3f}")
                walls.append((lo.max(), hi.min()))
            walls = np.array(walls)
            res[sx]["w"].append(walls[0, 1] - walls[0, 0])
            for j in (0, 1):
                off = np.abs(walls[:, j] - walls[0, j]) > 0.002
                n = int(np.argmax(off)) if off.any() else len(ys)
                res[sx]["depth"].append(n * LAND_DY)
    out = [dict(x=r["x"], w=min(r["w"]), w_max=max(r["w"]), depth=min(r["depth"]), n=len(r["w"])) for r in res.values()]
    clr = {t: min(gap(Rod(m, "rod", sx * hw.TUBE_CC / 2, t).solid(), shell) for sx in (-1, 1)) for t in hw.TAPE}
    r = hw.ROD_W / 2
    clr_d = {t: SLOT_W / 2 - math.sqrt(r * r - (m.GLASS_T0 - t - m.FRONT) ** 2) for t in hw.TAPE}
    return out, clr, clr_d


def slot_land_check(m, shell):
    SL, clr, clr_d = slot_land_measure(m, shell)
    for q in SL:          # depth resolution LAND_DY: the land reads 0.60 when it is 0.60..0.61 deep
        check(abs(q["w"] - SLOT_W) < 1e-3 and abs(q["w_max"] - SLOT_W) < 1e-3 and abs(q["depth"] - m.RIM) < LAND_DY + 1e-6,
              f"slot at x {q['x']:+.2f}: land {q['w']:.3f}..{q['w_max']:.3f} wide, {q['depth']:.3f} deep at its shallowest")
    check(min(clr.values()) > 0.0, f"a rod touches its slot: {clr}")
    return SL, clr, clr_d


def slot_lines(m, SL, clr, clr_d):
    return (f"  land       [m] on {SL[0]['n']} sections along each slot: {min(q['w'] for q in SL):.3f}..{max(q['w_max'] for q in SL):.3f} "
            f"wide, {min(q['depth'] for q in SL):.2f} deep at the shallowest (along t, from the inner face; {LAND_DY} steps), both "
            f"sides, both slots; then 45 deg out to the face. Print test 2026-11-19: the knife edge (0 land) of the 8.2 slots printed "
            f"9.0 wide; rod in the slot [m] " + ", ".join(f"{v:.3f} (tape {t})" for t, v in clr.items()) +
            " to the shell at the land's inner edge (closest); [d] in X there " + ", ".join(f"{v:.3f}" for v in clr_d.values()))


def logo_skin_measure(shell):
    side = hw.LOGO_SIDE
    outer = [f for f in shell.faces() if f.geom_type == GeomType.PLANE and abs(f.center().X - side * W / 2) < 1e-6]
    pocket = [f for f in shell.faces() if f.geom_type == GeomType.PLANE and abs(abs(f.normal_at().X) - 1) < 1e-6
              and abs(f.center().X - side * (W / 2 - LOGO_SKIN)) < 1e-6]
    if not outer or not pocket:
        return math.nan
    return dist_shapes(Compound(outer), Compound(pocket))[0]


STL_DEFLECTION, STL_ANGLE = 0.01, 0.1   # absolute chordal deflection (mm) and angular deflection (rad) of the STL meshes
STL_VOL_TOL = 0.003                      # mesh volume vs the solid's, relative
STEP_VOL_TOL = 1e-4                      # re-imported STEP volume vs the solid's, relative


def write_stl(shape, path):
    """STL with an absolute deflection (build123d's export_stl meshes with a relative one)."""
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.StlAPI import StlAPI_Writer
    BRepMesh_IncrementalMesh(shape.wrapped, STL_DEFLECTION, False, STL_ANGLE, True).Perform()
    w = StlAPI_Writer()
    w.ASCIIMode = False
    check(w.Write(shape.wrapped, str(path)), f"STL not written: {path}")


def check_stl(shape, path, bodies=1):
    """The written mesh: closed, `bodies` connected pieces, volume within STL_VOL_TOL of the solid's. Returns its info."""
    import pyvista as pv
    mesh = pv.read(str(path)).clean()
    n_open = mesh.n_open_edges
    n_bodies = int(mesh.connectivity().point_data["RegionId"].max()) + 1
    vol = abs(mesh.volume)
    err = vol / shape.volume - 1
    check(n_open == 0, f"{path.name}: {n_open} open edges")
    check(n_bodies == bodies, f"{path.name}: {n_bodies} separate bodies, expected {bodies}")
    check(abs(err) <= STL_VOL_TOL, f"{path.name}: mesh volume {vol:.1f} vs solid {shape.volume:.1f} ({err * 100:+.2f} %)")
    return dict(kb=path.stat().st_size / 1024, tris=mesh.n_cells, err=err)


def write_step(shape, path):
    """STEP, re-imported: the same number of solids, each valid and closed, the same total volume (STEP_VOL_TOL)."""
    from build123d import import_step
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRep import BRep_Tool
    export_step(shape, str(path))
    back = import_step(str(path))
    n0, n1 = len(shape.solids()), len(back.solids())
    check(n1 == n0, f"{path.name}: re-imported with {n1} solids, written {n0} ({len(back.faces())} faces back, "
                    f"{len(shape.faces())} written)")
    for sol in back.solids():
        check(BRepCheck_Analyzer(sol.wrapped).IsValid() and all(BRep_Tool.IsClosed_s(sh.wrapped) for sh in sol.shells()), f"{path.name}: an invalid or open solid")
    v0, v1 = sum(x.volume for x in shape.solids()), sum(x.volume for x in back.solids())
    check(abs(v1 / v0 - 1) <= STEP_VOL_TOL, f"{path.name}: volume {v1:.2f} back, {v0:.2f} written")
    return dict(solids=n1, faces=len(back.faces()), err=v1 / v0 - 1, kb=path.stat().st_size / 1024)


def export_part(shape, out, name, report, bodies=1):
    """A printed part: STEP + STL, both checked; their numbers go into `report`."""
    shape.label = name
    st = write_step(shape, out / f"{name}.step")
    write_stl(shape, out / f"{name}.stl")
    report[name] = (st, check_stl(shape, out / f"{name}.stl", bodies))




def face_name(shell, pt):
    """Name of the shell face nearest to a point (inside the cavity)."""
    from build123d import Vertex
    v = Vertex(*pt)
    f = min(shell.faces(), key=lambda f: dist_shapes(v, f)[0])
    if f.geom_type == GeomType.PLANE:
        n = f.normal_at(f.center())
        return ("front wall's inner face" if n.Y > 0.9 else "back wall's inner face" if n.Y < -0.9 else
                "side wall's inner face" if abs(n.X) > 0.9 else "ceiling" if n.Z < -0.9 else "rim" if n.Z > 0.9 else "sloped face")
    return f"curved face ({f.geom_type.name.lower()})"


# ---- checks along the assembly moves ----------------------------------------------------------------------------
def check_paths(m, shell_core, lid, moving, adapter, order):
    """Swept volumes of every move of the assembly order against everything already in place; the gaps are measured on
    the same sweeps (overshoot included)."""
    drop = 2 * m.H
    gaps = {}
    rods_after = order == "rods-after"
    shift = 0.0 if rods_after else INSERT_SHIFT
    first = [b for b in moving if not (rods_after and isinstance(b, Rod)) and not (order == "battery-after" and b.name == "battery")]
    for b in first:
        moves = [("up", b.solid(dt=shift, es0=drop, es1=Z_STOP))]
        if not rods_after:
            moves.append(("forward", b.solid(et=shift)))
        for move, sw in moves:
            v = volume_common(sw, shell_core)
            check(v < EPS_V, f"{m.name}: insertion, {move} move: {b.name} cuts {v:.2f} mm3 out of the shell")
            gaps[(move, b.name)] = gap(sw, shell_core)
    seated = [(b.name, b.solid()) for b in moving]
    if order == "battery-after":                       # the battery's own two moves, behind the seated board
        board_seated = [(n, x) for n, x in seated if n != "battery"]
        for move, sw in bat_sweeps(m, order, drop)[0]:
            for on, o in [("shell", shell_core)] + board_seated:
                v = volume_common(sw, o)
                check(v < EPS_V, f"{m.name}: battery, {move}: runs into the {on} ({v:.2f} mm3)")
            gaps[(move, "battery")] = gap(sw, shell_core)
            gaps[(move, "battery-board")] = min(gap(sw, o) for n, o in board_seated if n in ("board", "plug-j5", "plug-i2c"))
    if rods_after:                                     # rods pushed in through the slots from the front, onto the glass
        for b in moving:
            if isinstance(b, Rod):
                sw = b.solid(dt=-15.0, et=15.0)
                for on, o in [("shell", shell_core)] + [(n, x) for n, x in seated if not n.startswith("rod")]:
                    v = volume_common(sw, o)
                    check(v < EPS_V, f"{m.name}: rod from the front runs into the {on} ({v:.2f} mm3)")
                gaps[("front", b.name)] = gap(sw, shell_core)
    # the adapter (or the right-angle plug): along its plug axis (along the face) from below, after the board and battery
    sweep = adapter.solid(es0=drop)
    for on, o in [("shell", shell_core)] + seated:
        v = volume_common(sweep, o)
        check(v < EPS_V, f"{m.name}: adapter move runs into the {on} ({v:.2f} mm3)")
        gaps[("adapter", on)] = gap(sweep, o)
    # the lid, straight up (world Z). Its sweep: the prism of the lid blank's largest outline (its bottom, before the
    # break) from far below up to the rim; it contains the real lid, toe included, at every height of the move
    bot = [f for f in m.lid_env().faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6]
    check(len(bot) == 1, "lid blank bottom face")
    lsweep = Pos(0, 0, -drop) * extrude(Face(bot[0].outer_wire()).moved(Pos(0, 0, LID_T)), drop)
    check(volume_common(lid, lsweep) >= lid.volume - 1e-3, "lid sweep does not contain the lid")
    for on, o in [("shell", shell_core), ("adapter", adapter.solid())] + seated:
        v = volume_common(lsweep, o)
        check(v < EPS_V, f"{m.name}: lid move runs into the {on} ({v:.2f} mm3)")
        gaps[("lid", on)] = gap(lid, o)
    return gaps


def check_static(named):
    for i, (na, a) in enumerate(named):
        for nb, b in named[i + 1:]:
            v = volume_common(a, b)
            check(v < EPS_V, f"assembled: {na} and {nb} overlap by {v:.2f} mm3")


# ---- the small front logo (upright, oval) ---------------------------------------------------------------------------
FRONT_LOGO_MAX_W = 14.0                # letters' width at most, 0.5 steps
FRONT_LOGO_STRIP_MIN = 0.6             # thinnest strip between the letter cuts accepted for this logo
FRONT_LOGO_GLASS = 1.0                 # letters' top below the glass's lower edge, at least
FRONT_LOGO_RIM = 3.0                   # letters' bottom above the rim, at least
FRONT_LOGO_T = 3.0                     # inlay thickness = front wall left at the letters (oval: on the centre line)
FRONT_LOGO_RECESS = 1.0                # oval: the inside recess, beyond the letters' box all round
ROD_SWEEP_X = hw.TUBE_CC / 2 - hw.ROD_W / 2   # the rods pass the front wall's inner face on their up move from here outwards


def front_logo_width():
    """The widest letters (0.5 steps, <= FRONT_LOGO_MAX_W) that fit between the rim and the glass on every shell with this
    logo, with strips >= FRONT_LOGO_STRIP_MIN."""
    glass = {Model(n, 40.0).GLASS_S0 for n, c in VARIANTS.items() if c["LOGO_MODE"] == "front"}
    check(len(glass) == 1, f"the front-logo shells differ in glass height: {glass}")
    room = glass.pop() - FRONT_LOGO_GLASS - FRONT_LOGO_RIM
    w = FRONT_LOGO_MAX_W
    while hw.LETTERS_ASPECT * w > room or hw.STRIP_PER_MM * w < FRONT_LOGO_STRIP_MIN - 1e-9:
        w -= 0.5
        check(w > 4, "no front logo fits")
    return w


FRONT_LOGO_W = front_logo_width()


def make_front_inlays():
    """Inlays for the front logo, as housing.make_logo_inlays: one E and one H (and whatever else the logo has) per
    clearance in hw.INLAY_CLRS, FRONT_LOGO_T thick, mirrored so the outer face lies on the bed; set i carries i + 1
    dimples on the back of the H."""
    from build123d import offset
    w = FRONT_LOGO_W
    lh = hw.LETTERS_ASPECT * w
    out = []
    for i, c in enumerate(hw.INLAY_CLRS):
        pieces = [extrude(offset(Polygon(*[(-u, v) for u, v in poly], align=None), -c), FRONT_LOGO_T) for poly in hw.letters_mm(w)]
        k = max(range(len(pieces)), key=lambda j: pieces[j].bounding_box().min.X)       # the H (mirrored: on the right)
        bb = pieces[k].bounding_box()
        for d in range(i + 1):
            pieces[k] = pieces[k] - Pos(bb.center().X + (d - i / 2) * 1.6, bb.center().Y, FRONT_LOGO_T) * Cylinder(0.4, 0.8)
        out += [Pos(0, -i * (lh + 4), 0) * p for p in pieces]
    return Compound(out)


def all_sweeps(m, order, drop=None):
    """Every swept solid of the assembly order (board set, battery, adapter), named."""
    drop = drop or 2 * m.H
    moving = m.moving_bodies()
    rods_after = order == "rods-after"
    shift = 0.0 if rods_after else INSERT_SHIFT
    first = [b for b in moving if not (rods_after and isinstance(b, Rod)) and not (order == "battery-after" and b.name == "battery")]
    sw = [(f"{b.name} up", b.solid(dt=shift, es0=drop, es1=Z_STOP)) for b in first]
    if not rods_after:
        sw += [(f"{b.name} forward", b.solid(et=shift)) for b in first]
    if order == "battery-after":
        sw += [(f"battery {mv}", s_) for mv, s_ in bat_sweeps(m, order, drop)[0]]
    return sw + [("adapter up", m.adapter().solid(es0=drop))]


def front_logo_check(m, shell, lid, order):
    """Checks and numbers for the front logo: limits, the voids against every body and sweep, LED room measured against
    the shell as well as the hardware. Returns a dict for the report."""
    fl = m.front_logo()
    w, h, (z0, z1) = fl["w"], fl["h"], fl["z"]
    strip = hw.STRIP_PER_MM * w
    check(strip >= FRONT_LOGO_STRIP_MIN - 1e-9, f"front logo strips {strip:.2f}")
    check(z0 >= FRONT_LOGO_RIM - 1e-6 and z1 <= m.GLASS_S0 - FRONT_LOGO_GLASS + 1e-6, "front logo outside its band")
    check(z1 < m.SLOT_S[0] - 1.0, "front logo reaches the slots")
    void = fl["cut"] if fl["recess"] is None else fl["cut"] + fl["recess"]
    void = void & box(-60, 60, -10, m.FRONT, -5, 60)       # what it removes: the front wall only (the cutters reach past it)
    if fl["recess"] is not None:
        rb = fl["recess"].bounding_box()
        check(rb.max.Z <= m.GLASS_S0 - 0.2, f"recess top {rb.max.Z:.2f} reaches the glass ({m.GLASS_S0:.2f})")
        check(rb.min.Z >= 1.0, f"recess bottom {rb.min.Z:.2f} reaches the rim")
    skin = (math.nan, math.nan)
    if fl["pocket"] is not None:                 # stencil pocket: inside the band, clear of the R5 edges, skin measured
        pw, ph = fl["pocket"]
        check(fl["zc"] + ph / 2 <= m.GLASS_S0 - 0.2, f"logo pocket top {fl['zc'] + ph / 2:.2f} reaches the glass ({m.GLASS_S0:.2f})")
        check(fl["zc"] - ph / 2 >= BOTTOM_BREAK + 1.0, f"logo pocket bottom {fl['zc'] - ph / 2:.2f} too close to the rim")
        check(pw / 2 <= getattr(m, "W", W) / 2 - R_EDGE - 1.0, "logo pocket reaches the R5 edges")
        floor_f = [f for f in shell.faces() if f.geom_type == GeomType.PLANE and abs(abs(f.normal_at().Y) - 1) < 1e-6
                   and abs(f.center().Y - fl["floor"]) < 1e-6]
        check(len(floor_f) == 1, f"logo pocket floor: {len(floor_f)} faces")
        fb = floor_f[0].bounding_box()
        outer = [f for f in shell.faces() if f.bounding_box().min.Y < fl["floor"] - 1e-3     # faces reaching in front of the floor
                 and f.bounding_box().max.X > fb.min.X and f.bounding_box().min.X < fb.max.X
                 and f.bounding_box().max.Z > fb.min.Z and f.bounding_box().min.Z < fb.max.Z]
        d_min = dist_shapes(Compound(outer), floor_f[0])[0]
        d_ctr = fl["floor"] - m.front_out_y(0.0, fl["zc"])
        check(abs(d_min - LOGO_SKIN) < 0.01, f"logo skin measured {d_min:.3f}, want {LOGO_SKIN}")
        skin = (d_min, d_ctr)
    seated = [(b.name, b.solid()) for b in m.moving_bodies()] + [("adapter", m.adapter().solid()), ("lid", lid)]
    sweeps = all_sweeps(m, order)
    for n, o in seated + sweeps:
        v = volume_common(void, o)
        check(v < EPS_V, f"front logo cut / recess overlaps the {n} ({v:.2f} mm3)")
    # LED room A: right behind the letters, between the inner face and the adapter, inside the rods' path
    ad = m.adapter().solid()
    ad_y0 = min(v.Y for v in ad.vertices())
    xa = min(w / 2, ROD_SWEEP_X - 0.3)
    zoneA = box(-xa, xa, fl["inner_y"], ad_y0 - 0.3, z0, z1)
    vA = [(n, volume_common(zoneA, o)) for n, o in [("shell", shell)] + seated + sweeps]
    bad = [(n, v) for n, v in vA if v > EPS_V]
    check(not bad, f"LED room behind the logo overlaps: {bad}")
    gA = min((gap(zoneA, o), n) for n, o in [(n, o) for n, o in seated + sweeps])
    # free room beside the adapter at the letters' height: the cavity minus every body and sweep, |x| > adapter + 0.5
    beside = None
    for sx in (-1, 1):
        b_ = box(sx * (hw.ADAPTER_W / 2 + 0.5), sx * 40, -10, 60, z0, z1) & m.cavity()
        for n, o in seated + sweeps:
            if n != "lid":
                b_ = b_ - o
        beside = b_ if beside is None else beside + b_
    bb_ = beside.bounding_box()
    # what the letters see straight behind them, measured: inner face (or recess floor) to the adapter
    d_ad = BRepExtrema_DistShapeShape(ad.wrapped, shell.wrapped)
    d_ad.Perform()
    q = d_ad.PointOnShape2(1)
    rim_gap = min(gap(fl["cut"], f) for f in shell.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6 and abs(f.center().Z) < 1e-6)
    return dict(w=w, h=h, z=(z0, z1), strip=strip, recess=fl["recess"], inner_y=fl["inner_y"], ad_y0=ad_y0, skin=skin,
                pocket=fl["pocket"], floor=fl["floor"], zc=fl["zc"],
                zoneA=(2 * xa, ad_y0 - 0.3 - fl["inner_y"], z1 - z0), gA=gA, beside_vol=beside.volume, beside_bb=bb_,
                ad_near=(d_ad.Value(), face_name(shell, (q.X(), q.Y(), q.Z()))), rim_gap=rim_gap)


SLICER_LINE = ("slicer       suggested: ironing on top surfaces (user, for the next print: the flat tops came out patchy); "
               "X1E, 0.4 nozzle, PLA, no supports")
POCKET_OVER = 3.0                      # the pocket's mouth runs on straight this far into the cavity
STENCIL_SWEEP = 15.0                   # the stencil's insertion, tested: from this far inside the cavity onto the floor


def pocket_check(m, shell, lid, order, mag_xy):
    """The glow-through pocket, on the finished shell. `removed`: what the logo cutters really took out round the pocket
    (the shell without them, less the finished shell, in a box 2 mm round the cutter): it must equal what the cutters
    were meant to take (no extra hole, nothing missing), and the floor must be one unbroken face of the designed outline.
    Measured from `removed` (the run-on's notches included): the thinnest material to the outside; the distances to the
    glass, the slots' and magnets' voids and the rim; no overlap with any seated body, the lid or any sweep. Also: the
    mouth on the wall's inner face; the stencil (outline) pushed in along the pocket's axis from STENCIL_SWEEP inside
    onto the floor, against the shell. Returns a dict for the report."""
    P = m.pocket()
    pl, k, d = P["pl"], P["k"], P["depth"]
    zd, o = pl.z_dir, pl.origin
    void = P["cut"] & P["wall_box"]                      # the pocket proper: floor to the inner face (where the stencil sits)
    env = m.shell_env()
    outer = Compound([f for f in env.faces() if not (f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6 and abs(f.center().Z) < 1e-6)])
    cb = P["cut"].bounding_box()
    B = box(cb.min.X - 2, cb.max.X + 2, cb.min.Y - 2, cb.max.Y + 2, cb.min.Z - 2, cb.max.Z + 2)
    core_b = m.shell("core") & B
    removed = core_b - shell
    cutters = None
    for c_ in m.logo_cutters():
        cutters = c_ if cutters is None else cutters + c_
    v_want = (core_b & cutters).volume
    check(abs(removed.volume - v_want) < max(EPS_V, 1e-6 * v_want),
          f"logo pocket: the shell lacks {removed.volume:.3f} mm3 round the pocket, the cutters take {v_want:.3f}")
    floor_f = [f for f in shell.faces() if f.geom_type == GeomType.PLANE and (f.normal_at() - zd).length < 1e-6
               and abs((f.center() - o).dot(zd)) < 1e-4]
    a_want = P["pw"] * P["ph"] - (4 - math.pi) * STENCIL_R ** 2
    check(len(floor_f) == 1 and not floor_f[0].inner_wires() and abs(floor_f[0].area - a_want) < 1e-4 * a_want,
          f"logo pocket floor: {len(floor_f)} face(s), " + ", ".join(f"{f.area:.3f} mm2 with {len(f.inner_wires())} holes" for f in floor_f) +
          f"; designed one of {a_want:.3f} without holes")
    skin_any, p_any = dist_shapes(outer, Compound(removed.faces()))
    check(skin_any >= LOGO_SKIN - 0.01, f"logo pocket: {skin_any:.3f} of material to the outside at {p_any}")
    # the straight run-on into the cavity thins nothing beyond what the mouth itself leaves (tilt15: the mouth's front end
    # meets the R5 corner's offset), and stays out of the front wall
    mouth_f = [f for f in void.faces() if f.geom_type == GeomType.PLANE and abs(abs(f.normal_at().dot(zd)) - 1) < 1e-6
               and abs((f.center() - o).dot(zd) - d) < 1e-4]
    check(len(mouth_f) == 1, f"logo pocket: {len(mouth_f)} mouth faces")
    mouth_wall = dist_shapes(outer, mouth_f[0])[0]
    ext = (P["cut"] - P["wall_box"]) & env
    ext_wall = dist_shapes(outer, Compound(ext.faces()))[0] if ext.volume > EPS_V else math.inf
    check(ext_wall >= min(mouth_wall, WALL_MIN) - 1e-3, f"logo pocket: its run-on into the cavity leaves {ext_wall:.3f} of wall, "
                                                       f"the mouth {mouth_wall:.3f}")
    if m.cfg["LOGO_MODE"] != "front":
        v = volume_common(P["cut"], m.wt(box(-W, W, -5, m.FRONT, -50, 200)))
        check(v < EPS_V, f"logo pocket cuts {v:.3f} mm3 into the front wall")
    # the mouth, measured: across the two sloped sides (their far edges), and between the pocket's top and bottom faces
    xd = pl.x_dir
    sk, ck = math.sin(math.radians(LOGO_FLARE_DEG)), math.cos(math.radians(LOGO_FLARE_DEG))
    vb = P["cut"].bounding_box()

    def near_void(f, tol=0.01):
        b = f.bounding_box()
        return all(getattr(b.min, c) >= getattr(vb.min, c) - tol and getattr(b.max, c) <= getattr(vb.max, c) + tol for c in "XYZ")
    flanks = [f for f in shell.faces() if f.geom_type == GeomType.PLANE and abs(abs(f.normal_at().dot(zd)) - sk) < 1e-6
              and abs(abs(f.normal_at().dot(xd)) - ck) < 1e-6 and near_void(f)]
    check(len(flanks) == 2, f"logo pocket: {len(flanks)} sloped side faces")
    u = [(Vector(*v) - o).dot(xd) for f in flanks for v in f.vertices()]
    lev = [(Vector(*v) - o).dot(zd) for f in flanks for v in f.vertices()]
    zs = sorted(f.center().Z for f in shell.faces() if f.geom_type == GeomType.PLANE and abs(abs(f.normal_at().Z) - 1) < 1e-6 and near_void(f))
    check(len(zs) == 2, f"logo pocket: {len(zs)} top / bottom faces")
    mouth = (max(u) - min(u), zs[1] - zs[0])
    check(abs(mouth[0] - P["mouth"][0]) < 0.01 and abs(mouth[1] - P["mouth"][1]) < 0.01 and abs(max(lev) - min(lev) - d) < 0.01,
          f"logo pocket mouth measured {mouth[0]:.3f} x {mouth[1]:.3f}, designed {P['mouth'][0]:.3f} x {P['mouth'][1]:.3f}")
    # inside the wall's flat inner face (a hole in it)? Required on the fronts; the tilt15's side flat is shorter than the mouth
    inner = [f for f in shell.faces() if f.geom_type == GeomType.PLANE and (f.normal_at() - zd).length < 1e-6
             and abs((f.center() - o).dot(zd) - d) < 1e-4]
    in_flat = any((w.bounding_box().center() - (o + zd * d)).length < 1.0 for f in inner for w in f.inner_wires())
    if m.cfg["LOGO_MODE"] == "front":
        check(in_flat, "logo pocket mouth runs out of the front's flat inner face")
    # the stencil, seated on the floor and on its way in
    st = stencil_block(pl, P["pw"], P["ph"])
    sw_, sh_ = P["pw"] - 2 * STENCIL_CLR + 2 * k * STENCIL_T, P["ph"] - STENCIL_CLR - STENCIL_CLR_TOP
    top = pl.offset(STENCIL_T) * Pos(0, (STENCIL_CLR - STENCIL_CLR_TOP) / 2) * RectangleRounded(sw_, sh_, STENCIL_R - STENCIL_CLR)
    sweep = st + extrude(top, STENCIL_SWEEP)
    v = volume_common(sweep, shell)
    check(v < EPS_V, f"logo stencil: its way into the pocket cuts {v:.3f} mm3 out of the shell")
    vb = void.bounding_box()
    walls_ = [f for f in shell.faces() if not (f.geom_type == GeomType.PLANE and (f.normal_at() - zd).length < 1e-6
                                                and abs((f.center() - o).dot(zd)) < 1e-4)      # all but the floor it sits on
              and all(getattr(f.bounding_box().min, c) <= getattr(vb.max, c) + 1.0 and
                      getattr(f.bounding_box().max, c) >= getattr(vb.min, c) - 1.0 for c in "XYZ")]
    st_gap = dist_shapes(Compound(walls_), st)[0]
    seated = [(b.name, b.solid()) for b in m.moving_bodies()] + [("adapter", m.adapter().solid()), ("lid", lid)]
    for n, o_ in seated + all_sweeps(m, order):
        v = volume_common(removed, o_)
        check(v < EPS_V, f"logo pocket overlaps the {n} ({v:.2f} mm3)")
    glass = [o_ for n, o_ in seated if n == "glass"][0]
    holes_m = [Pos(x, y, 0) * Cylinder((hw.MAG_D + hw.MAG_CLR_D) / 2, hw.MAG_H + hw.MAG_CLR_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
               for x, y in mag_xy]
    slot_voids = [m.slot_cutter(sx * hw.TUBE_CC / 2) & m.shell("body") for sx in (-1, 1)]     # what the slots take out
    g = dict(glass=gap(removed, glass), rim=removed.bounding_box().min.Z, magnets=min(gap(removed, h_) for h_ in holes_m),
             slots=min(gap(removed, sv) for sv in slot_voids), removed=removed.volume)
    check(g["rim"] >= BOTTOM_BREAK + 1.0 - 1e-6 and g["magnets"] >= 1.0 and g["slots"] >= 1.0,
          f"logo pocket: {g['rim']:.2f} above the rim, {g['magnets']:.2f} from a magnet hole, {g['slots']:.2f} from a slot")
    return dict(skin_any=skin_any, mouth=mouth, mouth_d=P["mouth"], depth=d, st_gap=st_gap, pw=P["pw"], in_flat=in_flat,
                ext_wall=ext_wall, mouth_wall=mouth_wall, **g)


def pocket_lines(PK):
    return [f"  pocket     [m] its sides slope {LOGO_FLARE_DEG:g} deg out from the floor to the mouth on the inner face, "
            f"{PK['mouth'][0]:.2f} x {PK['mouth'][1]:.2f} ([d] {PK['mouth_d'][0]:.2f} x {PK['mouth_d'][1]:.2f}, {PK['depth']:.2f} behind the floor), "
            f"top and bottom straight; " + ("the mouth lies inside the wall's flat inner face" if PK["in_flat"] else
            f"the mouth runs past the inner side flat into the cavity's corner rounds, where the straight {POCKET_OVER:g} run-on cuts a "
            f"short notch (wall left {PK['ext_wall']:.2f}; at the mouth's edge {PK['mouth_wall']:.2f}, by its front end, the R{R_EDGE:g} corner)") + f"; thinnest material from the pocket to the outside {PK['skin_any']:.2f} (the floor's skin); "
            f"[m] from all the material the pocket removes ({PK['removed']:.1f} mm3, run-on included; exactly what its cutters "
            f"should take, floor one face of the designed outline): to the rim {PK['rim']:.2f}, to the glass {PK['glass']:.2f}, to a "
            f"magnet hole {PK['magnets']:.2f}, to a slot {PK['slots']:.2f}; clear of every seated body, the lid and every sweep",
            f"  stencil    [m] its outline ({STENCIL_T:.2f} thick, sides sloped as the pocket's) goes in along the pocket's axis from "
            f"{STENCIL_SWEEP:g} inside onto the floor without touching the shell; seated, {PK['st_gap']:.2f} to the pocket's walls "
            f"(the least: normal to the sloped sides)"]


def front_logo_lines(m, F):
    R = [f"logo         [d] front, centred on x 0 under the tubes: {F['w']:g} x {F['h']:.2f} letters (widest <= {FRONT_LOGO_MAX_W:g} in 0.5 "
         f"steps between {FRONT_LOGO_RIM} above the rim and {FRONT_LOGO_GLASS} below the glass at z {m.GLASS_S0:.2f}; the same on upright "
         f"and oval), " + (f"cut through, z {F['z'][0]:.2f}..{F['z'][1]:.2f} ({F['z'][0] + LID_T:.2f}.. above the desk); strips {F['strip']:.2f} "
         f"(accepted >= {FRONT_LOGO_STRIP_MIN} for this logo; v1 wants 1.2); inlays: out-smooth/logo-inlays-small.*" if F["pocket"] is None else
         f"letters z {F['z'][0]:.2f}..{F['z'][1]:.2f} ({F['z'][0] + LID_T:.2f}.. above the desk), glow-through: one pocket from inside, "
         f"{F['pocket'][0]:.2f} x {F['pocket'][1]:.2f} R{STENCIL_R:g} at its flat floor (letters + {STENCIL_MARGIN:g} all round), floor at y "
         f"{F['floor']:.2f}, z {F['zc'] - F['pocket'][1] / 2:.2f}..{F['zc'] + F['pocket'][1] / 2:.2f}, its two vertical sides sloped "
         f"{LOGO_FLARE_DEG:g} deg out to the inner face (print test 2026-11-19: the 0.6 skin and its 3.0 -> 0.6 step showed from outside); "
         f"[m] skin {F['skin'][0]:.2f} at its thinnest, {F['skin'][1]:.2f} on the centre line; stencils: out-smooth/logo-stencils-small.*")]
    if F["recess"] is not None:
        rb = F["recess"].bounding_box()
        R.append(f"  recess     [d] flat, on the inside, x {rb.min.X:.2f}..{rb.max.X:.2f}, z {rb.min.Z:.2f}..{rb.max.Z:.2f}, floor at y "
                 f"{FRONT_LOGO_T} (wall {FRONT_LOGO_T} on the centre line); {m.GLASS_S0 - rb.max.Z:.2f} below the glass, {rb.min.Z:.2f} above the rim")
    R.append(f"  LED room   [m] behind the letters, inside the rods' path (|x| < {ROD_SWEEP_X:.2f}), between the inner face (y {F['inner_y']:.2f}) "
             f"and the adapter (y {F['ad_y0']:.2f}): a {F['zoneA'][0]:.2f} x {F['zoneA'][1]:.2f} x {F['zoneA'][2]:.2f} box is clear of the "
             f"shell, the hardware and every sweep (nearest: {F['gA'][1]} {F['gA'][0]:.2f}); the adapter's nearest shell surface "
             f"{F['ad_near'][0]:.2f} ({F['ad_near'][1]}). Beside the adapter (|x| > {hw.ADAPTER_W / 2 + 0.5:g}) at the letters' height: "
             f"{F['beside_vol'] / 1000:.2f} cm3 free of the shell, hardware and sweeps (x {F['beside_bb'].min.X:.1f}..{F['beside_bb'].max.X:.1f}, "
             f"y {F['beside_bb'].min.Y:.1f}..{F['beside_bb'].max.Y:.1f}); the rods sweep up past the front wall at |x| {ROD_SWEEP_X:.2f}..")
    R.append(f"  wall       [m] letters to the rim face {F['rim_gap']:.2f} (the bottom break takes {BOTTOM_BREAK})")
    return R


MAG_MEAT_FRONT_MIN = 0.6
ROD_MISALIGN = 0.11                    # tested: rods this far off along the face on the forward move


# ---- one variant -------------------------------------------------------------------------------------------------
def build(name, order=ORDER):
    rods_after = order == "rods-after"
    tag = name + ("" if order == ORDER else f"-{order}")
    out = OUT_ROOT / tag
    out.mkdir(parents=True, exist_ok=True)
    print(f"[{tag}] depth search ...", flush=True)
    depths = {o: min_depth(name, o) for o in ORDERS}
    D_r3 = min_depth(name, order, r_in_rear=R_IN)[0]          # the depth if the rear cavity corners were R3
    D = depths[order][0]
    m = Model(name, D)
    print(f"[{tag}] D {D}, H {m.H}; building ...", flush=True)
    c, sn = m.c, m.sn
    shell_body = m.shell("body")
    lid_blank = m.lid_blank()
    magnets = magnet_search(m, shell_body, lid_blank)
    meat_f = min(v for (x, y), v in magnets if y < m.D / 2)
    meat_r = min(v for (x, y), v in magnets if y > m.D / 2)
    shell_core = m.shell("core")
    shell = m.shell("full", magnets)
    lid = m.lid(magnets)
    moving = m.moving_bodies()
    adapter = m.adapter()
    for n, p in (("shell", shell), ("lid", lid)):
        check(p.is_valid and len(p.solids()) == 1, f"{name}: {n} is not a single valid solid")

    # ---- fits ----
    L = m.logo_layout()
    _, CI = m.ceiling()
    ROD_FACE = [hw.ROD_H + t - m.FRONT - hw.GASKET for t in hw.TAPE]        # apex over (+) / under (-) the face
    check(SLOT_W - hw.ROD_W >= ROD_PLAY_MIN - 1e-9 and SLOT_L - ROD_L >= 0.1, "rod clearance in the slot")
    check(SLOT_L <= hw.AA_H - 0.2, "slot longer than the lit area: black glass would show")
    check(-0.5 <= ROD_FACE[0] <= 0.8, "rod apex too far from the face")
    inner_flat = W - 2 * WALL - 2 * R_IN_FRONT
    check(inner_flat >= hw.GLASS_W + 0.6 - 1e-6, f"front wall's inner flat {inner_flat:.2f} < glass {hw.GLASS_W} + 0.6")
    check(hw.TUBE_CC / 2 + SLOT_W / 2 <= W / 2 - WALL - R_IN_FRONT, "slots reach the cavity's front corner rounds")
    check(CI["flat_end"] >= max(m.SLOT_S[1], m.GLASS_TOP) + GLASS_SEAT - 1e-6,
          f"ceiling ramp starts at s {CI['flat_end']:.2f} along the face, below the slot / glass top + {GLASS_SEAT}")
    # the ceiling, measured on the solid: the flat (a bridge in Y) and the ramp
    zc = CI["z_ceil"]
    flats = [f for f in shell_core.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6 and abs(f.center().Z - zc) < 1e-3]
    check(len(flats) == 1, f"flat ceiling face: {len(flats)} found at z {zc:.2f}")
    fb = flats[0].bounding_box()
    bridge_y, bridge_x = fb.max.Y - fb.min.Y, fb.max.X - fb.min.X
    check(bridge_y <= BRIDGE_MAX, f"ceiling bridge {bridge_y:.1f} > {BRIDGE_MAX}")
    ramps = [f for f in shell_core.faces() if f.geom_type == GeomType.PLANE and abs(f.normal_at().Z + math.sqrt(.5)) < 1e-3
             and abs(f.normal_at().Y - math.sqrt(.5)) < 1e-3 and f.center().Z > m.H / 2]
    check(len(ramps) == 1, f"ceiling ramp face: {len(ramps)} found")
    rb = ramps[0].bounding_box()
    FM = front_face_margins(m, shell_core)
    SL, ROD_CLR, ROD_CLR_D = slot_land_check(m, shell_core)
    check(FM["side"] >= FACE_SIDE_FLAT_MIN - 1e-6, f"flat beside the bevels {FM['side']:.2f}")
    check(FM["bridge"] >= FACE_BRIDGE_MIN, f"bridge between the slots {FM['bridge']:.2f}")
    flat_above = m.S_TANGENT - m.SLOT_S[1]
    check(flat_above >= FACE_TOP_FLAT_MIN - 1e-6, f"flat above the slots {flat_above:.2f}")
    check(abs(FM["above"] - flat_above) < 0.05, f"front face top measured {FM['above']:.2f}, derived {flat_above:.2f}")
    check(meat_f >= MAG_MEAT_FRONT_MIN - 1e-6, f"{name}: front magnets: only {meat_f:.2f} round a hole")
    check(meat_r >= hw.MAG_MEAT_MIN, f"{name}: rear magnets: only {meat_r:.2f} round a hole")
    # logo
    front_logo = m.cfg["LOGO_MODE"] == "front"
    if front_logo:                                # letters inside the front's flat zone: clear of the R5 edges and the slots
        fw = FRONT_LOGO_W / 2
        check(fw <= W / 2 - R_EDGE - 1.0, "front logo reaches the R5 edges")
    else:
        check(L["margin"] >= LOGO_MARGIN - 1e-6, f"letters {L['margin']:.2f} from the ends of the side flat")
        y_in0 = m.y_front(L["z"][1], m.FRONT)
        check(L["y"][0] >= y_in0 + 0.5 and L["y"][1] <= m.D - BACK - 0.5, "letters outside the cavity: blind cuts")
        check(L["z"][0] >= 3.0 and L["z"][1] <= zc - 3, "logo outside the cavity height")
        strip = hw.STRIP_PER_MM * L["w"]
        if m.cfg["LOGO_MODE"] == "cut":
            check(strip >= hw.STRIP_MIN, f"letter strips {strip:.2f} < {hw.STRIP_MIN}: use the skin")
        y_flat_in = (m.y_front(L["z"][1], m.FRONT + R_IN_FRONT), m.D - BACK - m.R_IN_REAR)   # inner side flat (3 mm wall)
        logo_in_flat = L["y"][0] >= y_flat_in[0] and L["y"][1] <= y_flat_in[1]
        pocketed = m.cfg["LOGO_MODE"] == "skin" or LOGO_STYLE == "stencil"
        skin = logo_skin_measure(shell) if pocketed else math.nan
        if pocketed:
            check(abs(skin - LOGO_SKIN) < 0.01, f"logo skin measured {skin:.3f}")
        side_pocket = None
        if LOGO_STYLE == "stencil":               # the pocket's floor must lie under the outer side flat (constant skin)
            pw, ph = L["w"] + 2 * STENCIL_MARGIN, L["h"] + 2 * STENCIL_MARGIN
            f0 = m.y_front(L["zc"] + ph / 2) + R_EDGE / m.c
            side_pocket = (pw, ph, L["yc"] - pw / 2, L["yc"] + pw / 2, L["zc"] - ph / 2, L["zc"] + ph / 2, f0, L["flat"][1],
                           m.pocket()["floor"])
            check(side_pocket[2] >= f0 + 0.5 and side_pocket[3] <= L["flat"][1] - 0.5,
                  f"logo pocket y {side_pocket[2]:.2f}..{side_pocket[3]:.2f} outside the side flat {f0:.2f}..{L['flat'][1]:.2f}")
            check(side_pocket[4] >= BOTTOM_BREAK + 1.0, f"logo pocket bottom {side_pocket[4]:.2f} too close to the rim")

    # ---- walls, measured ----
    walls = wall_measure(m)
    wmin = min(v for v, _ in walls.values())
    check(wmin >= WALL_MIN - 1e-3, f"{name}: minimum wall {wmin:.2f} < {WALL_MIN}: " +
          ", ".join(f"{k} {v:.2f} at ({p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f})" for k, (v, p) in walls.items()))

    # ---- USB ----
    sy, sz = m.to_world(m.AD_T[1], m.SOCKET_S)                 # adapter's socket face, centre
    lam_in = (m.D - BACK - sy) / c                              # along the socket axis to the back wall's inner / outer face
    lam_out = (m.D - sy) / c
    z_wall_out = sz - lam_out * sn
    usb = dict(lam_in=lam_in, lam_out=lam_out, z_wall_out=z_wall_out)
    usb_cut = m.usb_cutter()
    usb["lid_gap"] = gap(usb_cut, lid)
    ad = adapter.solid()
    back_in = [f for f in shell_core.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Y < -1 + 1e-6
               and abs(f.center().Y - (m.D - BACK)) < 1e-4]
    check(len(back_in) >= 1, "back wall's inner face")
    usb["ad_back"] = min(gap(ad, f) for f in back_in)
    g_near, p_near = dist_shapes(shell_core, ad)
    d2 = BRepExtrema_DistShapeShape(shell_core.wrapped, ad.wrapped)
    d2.Perform()
    q = d2.PointOnShape1(1)
    usb["ad_near"], usb["ad_near_face"] = d2.Value(), face_name(shell_core, (q.X(), q.Y(), q.Z()))
    if m.cfg["USB"] == "hole":
        check(z_wall_out - hw.USB_HOLE_H / 2 >= 2.5, "USB hole too close to the rim")
        usb["rim"] = z_wall_out - hw.USB_HOLE_H / 2
    else:
        rear_mag = [(x, y) for (x, y), _ in magnets if y > m.D / 2]
        usb["notch_mag"] = min(gap(usb_cut, Pos(x, y, 0) * Cylinder((hw.MAG_D + hw.MAG_CLR_D) / 2, 1.2,
                                                                     align=(Align.CENTER, Align.CENTER, Align.MIN))) for x, y in rear_mag)
        usb["notch_side"] = (W / 2 - R_REAR) - NOTCH_W / 2
        check(usb["notch_mag"] >= WALL_MIN, f"notch {usb['notch_mag']:.2f} from a magnet hole")
        check(NOTCH_W >= CABLE_D + 0.5, "notch narrower than the cable")
        check(usb["lid_gap"] < 1e-6, "notch does not reach the lid")
        usb["hole_bottom"] = z_wall_out - hw.USB_HOLE_H / 2
        ht = PLUG_T_A / 2
        usb["a_wall"] = (m.D - BACK - sy - ht * sn) / c          # straight plug's top end corner to the back wall
        usb["a_floor"] = (sz - ht * c) / sn                       # its lower face to the lid
        usb["b_wall"] = m.D - BACK - max(v.Y for v in ad.vertices())
        usb["b_floor"] = min(v.Z for v in ad.vertices())
        usb["b_exit_z"] = sz
        usb["cable_lid"] = (sz - CABLE_D / 2 * c) / sn            # a straight cable from the head's end reaches the lid
    bat_solid = [b for b in moving if b.name == "battery"][0].solid()
    usb["ad_bat"] = gap(ad, bat_solid)
    bat_lid = gap(bat_solid, lid)
    if m.cfg["BAT_LOW"]:
        check(usb["ad_bat"] >= BAT_ADAPTER_MIN - 1e-6 and bat_lid >= BAT_ADAPTER_MIN - 1e-6,
              f"battery: {usb['ad_bat']:.2f} to the adapter, {bat_lid:.2f} to the lid")

    # ---- assembly checks ----
    print(f"[{tag}] path checks ...", flush=True)
    gaps = check_paths(m, shell_core, lid, moving, adapter, order)
    final = [("shell", shell), ("lid", lid), ("adapter", ad)] + [(b.name, b.solid()) for b in moving]
    check_static(final)
    misalign = None
    if not rods_after:                                  # rods ROD_MISALIGN off along the face on the forward move
        r = [b for b in moving if isinstance(b, Rod)][0]
        misalign = volume_common(r.solid(et=INSERT_SHIFT, es0=-ROD_MISALIGN, es1=ROD_MISALIGN), shell_core)

    FL = front_logo_check(m, shell, lid, order) if front_logo else None
    PK = pocket_check(m, shell, lid, order, [xy for xy, _ in magnets]) if LOGO_STYLE == "stencil" else None

    # ---- extents, tipping ----
    from build123d import CenterOf
    bb = Compound([shell, lid]).bounding_box()
    tops = [f for f in shell.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z > 1 - 1e-6 and abs(f.center().Z - m.H) < 1e-4]
    check(len(tops) == 1, "flat top face")
    tb = tops[0].bounding_box()
    parts_m = [(p.volume / 1000 * DENSITY, p.center(CenterOf.MASS)) for p in (shell, lid)]
    bo = Vector(0, *m.to_world((m.GLASS_T0 + m.BOARD_T1) / 2, m.PCB_S0 + hw.PCB_H / 2))
    ba = Vector(0, *m.to_world(sum(m.BAT_T) / 2, m.BAT_S0 + hw.BAT_H / 2))
    parts_m += [(BOARD_G, bo), (BATTERY_G, ba)]
    mass = sum(g for g, _ in parts_m)
    cm = sum((p * g for g, p in parts_m), Vector(0, 0, 0)) * (1 / mass)
    bf = [f for f in lid.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6][0]
    foot = bf.bounding_box()
    if m.tilt:                                     # the toe round really is TOE_R: the foot starts where it meets the desk
        toe_contact = m.TOE_Y + TOE_R / math.tan(math.radians(90 - m.tilt) / 2)
        mid = min(p.Y for e in bf.edges() for p in (e.position_at(t / 40) for t in range(41)) if abs(p.X) < 10)
        check(abs(mid - toe_contact) < 0.05, f"toe: foot starts at y {mid:.2f} mid-width, R{TOE_R} gives {toe_contact:.2f}")
    h_top = m.H + LID_T
    z_cm = cm.Z + LID_T
    tip = dict(back=mass * (foot.max.Y - cm.Y) / h_top, fwd=mass * (cm.Y - foot.min.Y) / h_top,
               ang_back=math.degrees(math.atan2(foot.max.Y - cm.Y, z_cm)), ang_fwd=math.degrees(math.atan2(cm.Y - foot.min.Y, z_cm)))

    # ---- exports ----
    for f in list(out.glob("*.stl")) + list(out.glob("*.step")):
        f.unlink()
    colors = {"shell": "tan", "lid": "sienna"}
    parts = {"shell": shell, "lid": lid}
    files = {}
    for n, p in parts.items():
        export_part(p, out, n, files)
    dummies = [(n, s_) for n, s_ in final if n not in parts]
    for n, s_ in final:
        s_.label = n
        if n in colors:
            s_.color = Color(colors[n])
    for n, s_ in dummies:
        write_stl(s_, out / f"dummy-{n}.stl")
    files["assembly"] = (write_step(Compound([s_ for _, s_ in final]), out / "assembly.step"), None)
    big = 3 * m.H
    cut_x = box(hw.TUBE_CC / 2, big, -big, big, -big, big)        # section through the right tube's axis, seen from +X
    for n, s_ in final:
        cs = s_ - cut_x
        if cs.volume > 0.01:
            write_stl(cs, out / f"section-x-{n}.stl")
    import json
    st, sb = m.to_world(0, m.SLOT_S[1]), m.to_world(0, m.SLOT_S[0])
    (out / "focus.json").write_text(json.dumps({"slot_top": [-hw.TUBE_CC / 2, st[0], st[1]], "slot_bottom": [-hw.TUBE_CC / 2, sb[0], sb[1]],
                                                "H": m.H, "D": m.D, "tilt": m.tilt,
                                                **({"logo": [0.0, 0.0, m.front_logo()["zc"]], "logo_normal": [0.0, -1.0, 0.0]} if front_logo
                                                   else {"logo": [-W / 2, L["yc"], L["zc"]]})}))
    if front_logo:                                # the front wall round the logo alone, to see the cut from inside
        write_stl(shell & box(-16, 16, -5, m.FRONT + 3, -1, 25), out / "section-l-shell.stl")

    # ---- report ----
    def worst(move, only):
        c_ = [(g, n) for (mv, n), g in gaps.items() if mv == move and n.startswith(only)]
        return f"{min(c_)[0]:.2f}" if c_ else "n/a"

    sl = m.to_world(0, m.SLOT_S[0]), m.to_world(0, m.SLOT_S[1])
    R = []
    R.append(f"DESK HOUSING smooth / {tag}  (front {'vertical' if not m.tilt else f'leaning back {m.tilt:.0f} deg'}; front {m.FRONT} with "
             f"flat-end slots ({SLOT_TYPE}): a {m.RIM} straight land at the inner face, then 45 deg on the long sides out to the face, straight ends)")
    R.append(f"assembly     order '{order}': {ORDERS[order]}" + (f" ({BAT_HOLD})" if order == "battery-after" else "") +
             "; then the adapter / plug from below, then the lid")
    R.append("[m] measured on the finished solids (OCC distances, sections, faces); [d] derived from the parameters")
    R.append(f"outer        [m] {bb.size.X:.2f} x {bb.size.Y:.2f} x {bb.size.Z:.2f} (W x D x H, shell + lid); shell {m.H} tall + lid {LID_T}; "
             f"depth at the rim {m.D}" + (f"; flat top {tb.size.Y:.2f} deep (y {tb.min.Y:.2f}..{tb.max.Y:.2f}), {m.D - m.Y_VIRT:.2f} back to "
                                          f"the virtual front-top corner [d]; footprint {foot.size.Y:.2f} deep (toe R{TOE_R})" if m.tilt else
                                          f"; flat top {tb.size.Y:.2f} deep"))
    R.append(f"  edges      [d] roll R{R_ROLL} (turns {90 - m.tilt:.0f} deg), rear vertical corners R{R_REAR}, R{R_EDGE} chain over the front edges / "
             f"roll / top / top-rear, bottom break {BOTTOM_BREAK}")
    R.append(f"cavity       [d] {W - 2 * WALL} wide; front inner face at t {m.FRONT}, back inner y {m.D - BACK}; corners: front R{R_IN_FRONT} "
             f"(inner flat {inner_flat:.2f} for the {hw.GLASS_W} glass), rear R{m.R_IN_REAR}, ceiling side edges R{R_IN}")
    R.append(f"  ceiling    [d] {CI['text']}; 45 deg x {REAR_CHAMFER} down to the back wall; joins R{CEIL_JOIN_R}. The inner front face runs "
             f"flat to s {CI['flat_end']:.2f} (glass top {m.GLASS_TOP:.2f}, slot top {m.SLOT_S[1]:.2f})")
    R.append(f"  bridge     [m] flat ceiling face {bridge_y:.2f} in Y (y {fb.min.Y:.2f}..{fb.max.Y:.2f}) x {bridge_x:.2f} in X at z {zc:.2f}; "
             f"the 45 deg ramp face spans y {rb.min.Y:.2f}..{rb.max.Y:.2f}, z {rb.min.Z:.2f}..{rb.max.Z:.2f}")
    R.append(f"board        [d] PCB bottom s {m.PCB_S0:.2f} along the face (adapter's lowest point {m.cfg['ADAPTER_FLOOR']} above the rim), "
             f"AA centre s {m.AA_SC:.2f}; battery s {m.BAT_S0:.2f}..{m.BAT_S0 + hw.BAT_H:.2f}, t {m.BAT_T[0]:.2f}..{m.BAT_T[1]:.2f} "
             f"({'taped low: ' + f'{BAT_ADAPTER_MIN} above the adapter' if m.cfg['BAT_LOW'] else 'centred on the board, v1'}); "
             f"[m] battery to the adapter {usb['ad_bat']:.2f}, to the lid {bat_lid:.2f}")
    R.append(f"slots        [d] {SLOT_W} x {SLOT_L:.2f} for rods cut to {ROD_L:.2f} (lit {hw.AA_H}), at x +-{hw.TUBE_CC / 2}, s {m.SLOT_S[0]:.2f}.."
             f"{m.SLOT_S[1]:.2f} (world z {sl[0][1]:.2f}..{sl[1][1]:.2f}); {(hw.AA_H - SLOT_L) / 2:.2f} inside the lit area per end; "
             f"[m] on the face {FM['open_w']:.2f} x {FM['open_l']:.2f}")
    R.append(slot_lines(m, SL, ROD_CLR, ROD_CLR_D))
    R.append(f"face margins [m] flat beside the bevels {FM['side']:.2f} (+ R{R_EDGE}), bridge {FM['bridge']:.2f} on the face "
             f"([d] {hw.TUBE_CC - SLOT_W:.2f} at the land), above the slots {FM['above']:.2f} to the roll's tangent line; [d] below "
             f"{m.SLOT_S[0]:.2f} along the face to the rim")
    R.append(f"rods         [d] {hw.ROD_W} x {hw.ROD_H} x {ROD_L:.2f}; apex {ROD_FACE[0]:+.2f}..{ROD_FACE[1]:+.2f} to the face (tape "
             f"{hw.TAPE[0]}..{hw.TAPE[1]}; + = proud); in the slot {(SLOT_W - hw.ROD_W) / 2:.2f} per side, {(SLOT_L - ROD_L) / 2:.2f} per end")
    if rods_after:
        R.append(f"insertion    [m] rods' path from the front to the shell {worst('front', 'rod')}")
    else:
        R.append(f"insertion    board + rods{' + battery' if order == 'v1' else ''}: up along the face at {INSERT_SHIFT:.2f} further back "
                 f"(rod {hw.ROD_H} + tape {hw.TAPE[1]} - gasket {hw.GASKET} + {INSERT_CLR}), then forward")
    need = {"battery-after": f"{BAT_SPARE_AFTER} round the battery's own sweeps", "v1": f"{SPARE_MIN} round the battery on the board's sweep",
            "rods-after": f"{SPARE_MIN} round the battery on the board's sweep"}
    R.append(f"  depth      [m] smallest depth (0.5 steps) with {need[order]} and {ADAPTER_BACK_MIN} round the adapter: built {D}, limited by the "
             f"{depths[order][3]} (battery {depths[order][1][0]:.2f}, adapter {depths[order][1][1]:.2f}; at {D - 0.5}: battery "
             f"{depths[order][2][0]:.2f}, adapter {depths[order][2][1]:.2f}). Other orders: " +
             "; ".join(f"{o} {v[0]} (limited by the {v[3]})" for o, v in depths.items() if o != order) +
             f". With R{R_IN} rear cavity corners (1.34 wall there) it would be {D_r3}")
    if order == "battery-after":
        R.append(f"  battery    [m] up {BAT_HOLD} behind its seat, then forward: clearance to the shell {gaps[('bat-up', 'battery')]:.2f} up, "
                 f"{gaps[('bat-fwd', 'battery')]:.2f} forward; to the board / plugs {gaps[('bat-up', 'battery-board')]:.2f} on the way up")
    R.append(f"  up move    [m] clearance on the whole sweep (0.2 overshoot included): rods to the front wall {worst('up', 'rod')}, battery "
             f"{worst('up', 'battery') if order != 'battery-after' else '(own moves, below)'}, plugs {worst('up', 'plug')}, buttons {worst('up', 'button')}, glass {worst('up', 'glass')}")
    if not rods_after:
        R.append(f"  forward    [m] rods in the slots {worst('forward', 'rod')}; the rods are {SLOT_L - ROD_L:.2f} shorter than the slots, "
                 f"so they must line up within +-{(SLOT_L - ROD_L) / 2:.2f}: {ROD_MISALIGN} off, a rod cuts {misalign:.2f} mm3 [m]")
    R.append(f"  adapter    [m] plugged in along the face from below after the board: free; sweep to the board {gaps[('adapter', 'board')]:.2f}, "
             f"glass {gaps[('adapter', 'glass')]:.2f}, battery {gaps[('adapter', 'battery')]:.2f}, shell {gaps[('adapter', 'shell')]:.2f}")
    R.append(f"  lid move   [m] straight up, free (swept as the prism of its largest outline, toe included); lid to the adapter "
             f"{gaps[('lid', 'adapter')]:.2f}, to the battery {gaps[('lid', 'battery')]:.2f}")
    R.append(f"magnets      [m] 4 x D{hw.MAG_D} x {hw.MAG_H} in holes D{hw.MAG_D + hw.MAG_CLR_D} x {hw.MAG_H + hw.MAG_CLR_H} (shell rim and lid); "
             f"wall round the hole: front {meat_f:.2f}, rear {meat_r:.2f} (rim section at z 0 and lid section at z -1.2); " +
             ", ".join(f"({x:.2f}, {y:.2f}) {v:.2f}" for (x, y), v in magnets))
    if m.cfg["USB"] == "hole":
        R.append(f"USB          v1 hole {hw.USB_HOLE_W} x {hw.USB_HOLE_H} R{hw.USB_HOLE_R} at z {usb['z_wall_out']:.2f} ([d] {usb['rim']:.2f} above "
                 f"the rim; [m] {usb['lid_gap']:.2f} to the lid); [d] socket face {usb['lam_in']:.2f} in front of the back wall's inner face "
                 f"({usb['lam_out']:.2f} from the outside); [m] adapter to the back wall's inner face {usb['ad_back']:.2f}, to the battery {usb['ad_bat']:.2f}")
    else:
        R.append(f"USB          [d] the adapter's socket faces back and {m.tilt:.0f} deg down; its face sits {usb['lam_out']:.2f} inside the back "
                 f"wall's outer face along its axis ({usb['lam_in']:.2f} to the inner face). A v1 hole on that axis would sit at z "
                 f"{usb['z_wall_out']:.2f} (bottom {usb['hole_bottom']:.2f}, {'above' if usb['hole_bottom'] >= 0 else 'below'} the rim): not built")
        R.append(f"  built      cable notch {NOTCH_W} wide x {NOTCH_H} high (round top) in the back wall at x 0, open at the rim, the lid closes it; "
                 f"[d] {usb['notch_side']:.2f} of flat back wall each side to the corner round, [m] {usb['notch_mag']:.2f} to the rear magnet holes")
        R.append(f"  (a)        [d] straight plug ({PLUG_LEN_A:.0f} long, {PLUG_T_A} thick) in the adapter's socket: its lower face meets the lid "
                 f"after {usb['a_floor']:.2f} and its top end the back wall after {usb['a_wall']:.1f} along the axis: does not fit")
        R.append(f"  (b)        right-angle plug in the board's port (head = the adapter's box, 12 x 7 x 21, cable out of its far end): [m] far "
                 f"end to the back wall's inner face {usb['b_wall']:.1f} horizontally, lowest edge {usb['b_floor']:.2f} above the lid, head to "
                 f"the battery {usb['ad_bat']:.2f}; [d] cable exit centre z {usb['b_exit_z']:.2f}, a straight D{CABLE_D:g} cable reaches the "
                 f"lid {usb['cable_lid']:.1f} after the head: it has to bend there and run on the lid to the notch. NOT VERIFIED: head, strain relief and bend of the real cable are not modelled")
    R.append(f"  adapter    [m] nearest shell surface {usb['ad_near']:.2f} ({usb['ad_near_face']}); to the back wall's inner face {usb['ad_back']:.2f}")
    if front_logo:
        R += front_logo_lines(m, FL)
    else:
        R.append(f"logo         [d] left (-X), letters {L['w']:.2f} x {L['h']:.2f}" +
                 (f" (shrunk from {m.cfg['LOGO_W']:g} to fit the {L['flat'][1] - L['flat'][0]:.1f} side flat; {m.cfg['LOGO_W']:g} would need "
                  f"depth {m.D + m.cfg['LOGO_W'] - L['w']:.1f})" if L['w'] < m.cfg['LOGO_W'] else "") + f", y {L['y'][0]:.2f}..{L['y'][1]:.2f}, z {L['z'][0]:.2f}..{L['z'][1]:.2f} "
                 f"(centre {L['zc'] + LID_T:.2f} above the desk); " +
                 (f"glow-through: one pocket from inside, {side_pocket[0]:.2f} x {side_pocket[1]:.2f} R{STENCIL_R:g} (letters + {STENCIL_MARGIN:g} "
                  f"all round), y {side_pocket[2]:.2f}..{side_pocket[3]:.2f}, z {side_pocket[4]:.2f}..{side_pocket[5]:.2f} (side flat y "
                  f"{side_pocket[6]:.2f}..{side_pocket[7]:.2f} at its top) at its flat floor, x {side_pocket[8]:.2f}; [m] skin {skin:.2f} (flat side: "
                  f"the same everywhere on the floor); stencils: out-smooth/logo-stencils-tilt15.*"
                  if side_pocket is not None else
                  f"cut through, strips {strip:.2f}; v1's inlays fit" + ("" if logo_in_flat else " (part of the letters over a thicker corner zone)")
                  if m.cfg["LOGO_MODE"] == "cut" else f"pocketed from inside, [m] skin {skin:.2f}; cut through the strips would be {strip:.2f}"))
        R.append(f"  margins    [d] {L['margin']:.2f} (least) to the ends of the side flat (y {L['flat'][0]:.2f}..{L['flat'][1]:.2f} at the letters' top); "
                 f"inner wall flat y {y_flat_in[0]:.2f}..{y_flat_in[1]:.2f}")
    if PK:
        R += pocket_lines(PK)
    R.append("min wall     [m] between the cavity surface and the outer surface (exact; before slots, logo, magnets, USB; bottom break "
             "excluded): " + ", ".join(f"{k} {v:.2f}" for k, (v, p) in sorted(walls.items(), key=lambda kv: kv[1][0])))
    R.append(f"  minimum    [m] {wmin:.2f}; by design thinner: slot land {m.RIM} deep, logo skin {LOGO_SKIN if m.cfg['LOGO_MODE'] == 'skin' or LOGO_STYLE == 'stencil' else '-'}, "
             f"magnet meat {min(meat_f, meat_r):.2f}")
    R.append(f"print        shell standing on its rim (opening down), meant to print without supports (check the layer preview): front inner face {'vertical' if not m.tilt else f'{m.tilt:.0f} deg overhang'}, "
             f"45 deg ramp under the roll, [m] flat bridge {bridge_y:.2f} in Y, 45 deg at the back; slot ends bridge {SLOT_W}..{FM['open_w']:.1f}, "
             f"the slots' sides a {m.RIM} land at the inner face (no knife edge); " +
             (f"logo pocket: its top a bridge {PK['pw']:.1f}..{PK['mouth'][0]:.1f} wide, its sides sloped {LOGO_FLARE_DEG:g} deg; " if PK else "") +
             ("USB hole round-topped" if m.cfg["USB"] == "hole" else "notch round-topped") +
             f"; the R{CEIL_JOIN_R:g} joins of the ceiling and its side blends pass 45 deg locally (about 1.4 wide)" +
             f". Lid: flat, top face down (the {'toe round and ' if m.tilt else ''}bottom break on top)")
    R.append(SLICER_LINE)
    R.append(f"volumes cm3  [m] shell {shell.volume / 1000:.1f}, lid {lid.volume / 1000:.1f}  ({(shell.volume + lid.volume) / 1000 * DENSITY:.0f} g at {DENSITY} g/cm3)")
    R.append(f"tipping      [m+d] mass {mass:.0f} g (print + board {BOARD_G:.0f} g + battery {BATTERY_G:.0f} g, both assumed); centre of mass "
             f"y {cm.Y:.1f}, {z_cm:.1f} above the desk; foot y {foot.min.Y:.2f}..{foot.max.Y:.2f}")
    R.append(f"  push       horizontal at the top ({h_top:.1f} above the desk) that tips it: backwards {tip['back']:.0f} gf, forwards "
             f"{tip['fwd']:.0f} gf; tips over when tilted {tip['ang_back']:.0f} deg back / {tip['ang_fwd']:.0f} deg forward")
    R += file_lines(files)
    R.append("open items (need the real parts):")
    if not rods_after:
        R.append(f"  - rods on the forward move: they must line up with the slots within +-{(SLOT_L - ROD_L) / 2:.2f} along the face "
                 f"({ROD_MISALIGN} off already cuts {misalign:.2f} mm3 per rod)")
    R.append(f"  - magnets: glue them in, do not press: the rear ligament round the hole is {meat_r:.2f}")
    if m.cfg["USB"] == "notch":
        R.append(f"  - cable: the plug head, its strain relief and the bend are not modelled; a straight D{CABLE_D:g} cable from the head reaches "
                 f"the lid after about {usb['cable_lid']:.0f} mm, so it has to bend there; check with the real right-angle plug")
    R.append("  - board and battery masses, the port's position in the board stack, the adapter's real shape (all assumed, as in v1)")
    R.append("")
    R.append("clearances along the insertion path, mm, measured on the swept solids (0.00 = it ends seated there):")
    R.append("  body                up   forward")
    for b in moving:
        if ("up", b.name) in gaps:
            fwd = gaps.get(("forward", b.name), gaps.get(("front", b.name), math.nan))
            R.append(f"  {b.name:<16} {gaps[('up', b.name)]:6.2f} {fwd:9.2f}")
        elif ("bat-up", b.name) in gaps:
            R.append(f"  {b.name:<16} {gaps[('bat-up', b.name)]:6.2f} {gaps[('bat-fwd', b.name)]:9.2f}   (its own moves, {BAT_HOLD} behind its seat)")
    text = "\n".join(R)
    (out / "report.txt").write_text(text + "\n")
    print(text, flush=True)
    return m


# ---- oval ("shampoo bottle") variant ------------------------------------------------------------------------------
# Plan: superellipse |2x/W|^n + |2(y - D/2)/D|^n = 1, extruded straight up; flat top, its edge rounded R_TOP; flat lid
# with the same outline. Upright, same hardware, inside arrangement and assembly order as "upright". The front's outer
# face is the curved plan; the face behind it is flat (the glass is taped to it), so the front is thickest on the centre
# line. Cavity: the plan offset inwards by WALL, closed at the front by that flat face; under the top a 45 deg taper all
# round (RAMP high) and a short flat ceiling. Magnets in local bosses inside the rim.
OVAL = dict(W=56.0, D=36.0, N=2.8, R_TOP=6.0, TOTAL=110.0, PTS=360,
            RAMP=7.0,                  # 45 deg taper under the top, all round: shortens the flat ceiling to ~14 in Y
            MAG_DEPTH=2.3,             # magnet axis this far inside the outer surface, along its normal
            MAG_PHI=(-60.0, 45.0),     # outward normal angle (deg from +X, plan) of the right front / right rear magnet
            BOSS_R=1.85, BOSS_H=3.0,   # boss round each magnet hole, inside the rim
            LOGO_W=14.0)               # unused: the oval carries the shared small front logo (Model.front_logo)
OVAL_BRIDGE_MIN = 2.5                  # face bridge between the slots (v1: 4.0; the specified slot gives ~2.9 here)


def oval_dense(k=40000):
    """The plan as dense arrays: x, y, outward unit normal (nx, ny), arc length."""
    W_, D_, n = OVAL["W"], OVAL["D"], OVAL["N"]
    t = np.linspace(0, 2 * np.pi, k, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    x = W_ / 2 * np.sign(c) * np.abs(c) ** (2 / n)
    y = D_ / 2 + D_ / 2 * np.sign(s) * np.abs(s) ** (2 / n)
    dx, dy = np.gradient(x, t), np.gradient(y, t)
    L = np.hypot(dx, dy)
    nx, ny = dy / L, -dx / L                               # outward for a counter-clockwise curve
    arc = np.concatenate([[0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
    return x, y, nx, ny, arc


def oval_front_y(x):
    W_, D_, n = OVAL["W"], OVAL["D"], OVAL["N"]
    return D_ / 2 - D_ / 2 * (1 - abs(2 * x / W_) ** n) ** (1 / n)


def oval_front_c():
    """Front wall thickness on the centre line (the flat inner face's y): the smallest (0.05 steps) for which the flat
    inner face, inside the plan's WALL offset, still spans the glass + 0.3 each side (v1's rule)."""
    x, y, nx, ny, _ = oval_dense()
    ox, oy = x - WALL * nx, y - WALL * ny
    fc = 3.0
    while True:
        k = (oy <= fc) & (oy < OVAL["D"] / 2)
        if k.any() and np.abs(ox[k]).max() >= hw.GLASS_W / 2 + 0.3:
            return round(fc, 2)
        fc += 0.05


def oval_at_normal(phi):
    """Point on the plan whose outward normal points at phi (deg, from +X), and that normal."""
    x, y, nx, ny, _ = oval_dense()
    a = np.degrees(np.arctan2(ny, nx))
    i = int(np.argmin(np.abs((a - phi + 180) % 360 - 180)))
    return (float(x[i]), float(y[i])), (float(nx[i]), float(ny[i]))


VARIANTS["oval"] = dict(TILT=0.0, ADAPTER_FLOOR=4.0, TOTAL_MIN=OVAL["TOTAL"], LOGO_W=OVAL["LOGO_W"], LOGO_MODE="front",
                        LOGO_ZC=None, USB="hole", BAT_LOW=False, FRONT=oval_front_c())


class OvalModel(Model):
    def __init__(self):
        super().__init__("oval", OVAL["D"])
        self.W = OVAL["W"]
        self.H = OVAL["TOTAL"] - LID_T
        self.Z_RAMP = self.H - TOP_T - OVAL["RAMP"]          # where the taper under the top begins
        self._cache = {}

    def front_out_y(self, x, z):
        return oval_front_y(x)

    def plan(self, inset=0.0):
        """The plan as a periodic spline face; inset > 0: through points moved `inset` inwards along the exact normal (the
        implicit function's gradient). Not OCC's offset: its offset curves do not survive a STEP round trip."""
        k = OVAL["PTS"]
        W_, D_, n = OVAL["W"], OVAL["D"], OVAL["N"]
        pts = []
        for i in range(k):
            t = 2 * math.pi * i / k
            c, s = math.cos(t), math.sin(t)
            x, y = W_ / 2 * math.copysign(abs(c) ** (2 / n), c), D_ / 2 + D_ / 2 * math.copysign(abs(s) ** (2 / n), s)
            if inset:
                u, v = 2 * x / W_, 2 * (y - D_ / 2) / D_
                gx = n * abs(u) ** (n - 1) * math.copysign(1, u) * 2 / W_
                gy = n * abs(v) ** (n - 1) * math.copysign(1, v) * 2 / D_
                g = math.hypot(gx, gy)
                x, y = x - inset * gx / g, y - inset * gy / g
            pts.append((x, y))
        with BuildSketch() as sk:
            with BuildLine():
                from build123d import Spline
                Spline(*pts, periodic=True)
            make_face()
        return sk.sketch.faces()[0]

    def outer_body(self):
        if "outer" in self._cache:
            return self._cache["outer"]
        body = extrude(self.plan().moved(Pos(0, 0, -LID_T)), self.H + LID_T)
        body = fillet(body.edges().group_by(Axis.Z)[-1], OVAL["R_TOP"])
        check(body.is_valid and len(body.solids()) == 1, "oval outer body invalid")
        self._cache["outer"] = body
        return body

    def cavity_plan(self):
        cp = self.plan(WALL) & Pos(0, self.FRONT + 50, 0) * Rectangle(200, 100)
        check(len(cp.faces()) == 1, "oval cavity plan")
        return cp.faces()[0]

    def cavity(self):
        if "cav" in self._cache:
            return self._cache["cav"]
        # the taper of (offset plan) & (front half-plane) = taper of each, intersected (both convex): the full offset plan
        # tapered at 45 deg, cut by a wedge that holds the flat front face and its own 45 deg ramp
        op = self.plan(WALL)
        zr, F = self.Z_RAMP, self.FRONT
        cav = extrude(op.moved(Pos(0, 0, -1)), zr + 1) + extrude(op.moved(Pos(0, 0, zr)), OVAL["RAMP"], taper=45)
        top = self.H + 5
        wedge = extrude(yz_face([(F, -2.0), (F, zr), (F + top - zr, top), (OVAL["D"] + 10, top), (OVAL["D"] + 10, -2.0)], {}),
                        OVAL["W"], both=True)
        cav = cav & wedge
        check(cav.is_valid and len(cav.solids()) == 1, "oval cavity invalid")
        self._cache["cav"] = cav
        return cav

    def magnet_spots(self):
        """[(x, y)] of the four magnet axes: right front, right rear and their mirror images."""
        out = []
        for phi in OVAL["MAG_PHI"]:
            for sx in (1, -1):
                ph = phi if sx > 0 else 180 - phi
                (px, py), (nx, ny) = oval_at_normal(ph)
                out.append((round(px - OVAL["MAG_DEPTH"] * nx, 3), round(py - OVAL["MAG_DEPTH"] * ny, 3)))
        return out

    def bosses(self):
        env = self.env_broken()
        b = None
        for x, y in self.magnet_spots():
            c = Pos(x, y, 0) * Cylinder(OVAL["BOSS_R"], OVAL["BOSS_H"], align=(Align.CENTER, Align.CENTER, Align.MIN))
            b = c if b is None else b + c
        return b & env

    def env_broken(self):
        if "envb" not in self._cache:
            s = self.shell_env()
            bottom = [f for f in s.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6 and abs(f.center().Z) < 1e-6]
            check(len(bottom) == 1, "oval shell bottom face")
            self._cache["envb"] = s.chamfer(BOTTOM_BREAK, None, bottom[0].edges())
        return self._cache["envb"]

    def usb_cutter(self):
        z = self.SOCKET_S
        return Pos(0, self.D - 3, z) * extrude(Plane.XZ * RectangleRounded(hw.USB_HOLE_W, hw.USB_HOLE_H, hw.USB_HOLE_R), 5, both=True)

    def shell(self, level="full", magnets=None):
        key = ("shell", level)
        if key in self._cache:
            return self._cache[key]
        s = self.env_broken() - self.cavity()
        s = s + self.bosses()
        if level != "body":
            for sx in (-1, 1):
                s = s - self.slot_cutter(sx * hw.TUBE_CC / 2)
            s = s - self.usb_cutter()
        if level in ("full", "strip"):
            for c in self.logo_cutters():
                s = s - c
        if level == "full":
            for x, y in self.magnet_spots():
                s = s - Pos(x, y, 0) * Cylinder((hw.MAG_D + hw.MAG_CLR_D) / 2, hw.MAG_H + hw.MAG_CLR_H,
                                                align=(Align.CENTER, Align.CENTER, Align.MIN))
        self._cache[key] = s
        return s

    def lid(self, magnets=None):
        l = self.lid_blank()
        for x, y in self.magnet_spots():
            l = l - Pos(x, y, 0) * Cylinder((hw.MAG_D + hw.MAG_CLR_D) / 2, hw.MAG_H + hw.MAG_CLR_H,
                                            align=(Align.CENTER, Align.CENTER, Align.MAX))
        return l


def meat_at(spots, shell_body, lid_blank):
    """Wall round each magnet hole, measured on the rim section (z 0+, with the bottom break and the bosses) and on the
    lid's section at the hole's depth: [(shell meat, lid meat)]."""
    r_hole = (hw.MAG_D + hw.MAG_CLR_D) / 2
    z_lid = -(hw.MAG_H + hw.MAG_CLR_H)
    s_all, l_all = section_segments(shell_body, 1e-3, step=0.1), section_segments(lid_blank, z_lid, step=0.1)
    p = np.array(spots)
    ins_s, ins_l = inside(p, s_all), inside(p, l_all)
    ds, dl = seg_dist(p, s_all), seg_dist(p, l_all)
    return [(float(ds[i] - r_hole) if ins_s[i] else -1.0, float(dl[i] - r_hole) if ins_l[i] else -1.0) for i in range(len(spots))]


OVAL_STRIP_Y = 12.0                    # test strip: the shell in front of this plane
OVAL_STRIP_ABOVE = 8.0                 # ... from the rim up to this far above the slots' upper ends


def file_lines(files):
    R = ["files        [m] each STEP re-imported, each STL re-read:"]
    for n, (st, ms) in files.items():
        R.append(f"  {n:<16} STEP {st['solids']} solid(s), {st['faces']} faces, volume {st['err'] * 100:+.4f} %, {st['kb']:.0f} kB" +
                 (f"; STL closed, {ms['tris']} triangles, volume {ms['err'] * 100:+.3f} %, {ms['kb']:.0f} kB" if ms else ""))
    return R


def build_oval(order=ORDER):
    name = "oval"
    out = OUT_ROOT / name
    out.mkdir(parents=True, exist_ok=True)
    m = OvalModel()
    check(abs(m.GLASS_S0 - Model("upright", 40.0).GLASS_S0) < 1e-9, "oval and upright differ in glass height: the front logo would differ")
    print(f"[{name}] W {m.W} D {m.D} H {m.H} front {m.FRONT}; building ...", flush=True)
    shell_body = m.shell("body")
    lid_blank = m.lid_blank()
    spots = m.magnet_spots()
    meats = meat_at(spots, shell_body, lid_blank)
    shell_core = m.shell("core")
    shell = m.shell("full")
    lid = m.lid()
    moving = m.moving_bodies()
    adapter = m.adapter()
    for n, p in (("shell", shell), ("lid", lid)):
        check(p.is_valid and len(p.solids()) == 1, f"{name}: {n} is not a single valid solid")
    for (x, y), (ms, ml) in zip(spots, meats):
        check(min(ms, ml) >= MAG_MEAT_FRONT_MIN - 1e-6, f"oval: magnet at ({x:.2f}, {y:.2f}): {ms:.2f} in the rim, {ml:.2f} in the lid")

    # ---- front, slots, rods ----
    check(SLOT_W - hw.ROD_W >= ROD_PLAY_MIN - 1e-9 and SLOT_L - ROD_L >= 0.1, "rod clearance in the slot")
    check(SLOT_L <= hw.AA_H - 0.2, "slot longer than the lit area")
    gl = [f for f in shell_core.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Y > 1 - 1e-6 and abs(f.center().Y - m.FRONT) < 1e-4]
    check(len(gl) == 1, f"flat inner front face: {len(gl)} found")
    glb = gl[0].bounding_box()
    check(glb.size.X >= hw.GLASS_W + 0.6 - 1e-3, f"flat inner front face {glb.size.X:.2f} wide < glass + 0.6")
    check(glb.max.Z >= m.GLASS_TOP + GLASS_SEAT, f"flat inner front face ends at z {glb.max.Z:.2f}, glass top {m.GLASS_TOP:.2f}")
    SL, ROD_CLR, ROD_CLR_D = slot_land_check(m, shell_core)
    zmid = m.AA_SC
    env_seg = section_segments(m.shell_env(), zmid, step=0.005)
    front_seg = env_seg[(env_seg[:, 1] < m.FRONT) & (env_seg[:, 3] < m.FRONT)]

    def face_y(x):
        """The curved outer face at x (measured: section of the solid)."""
        k = (np.minimum(front_seg[:, 0], front_seg[:, 2]) <= x) & (np.maximum(front_seg[:, 0], front_seg[:, 2]) >= x)
        sg = front_seg[k]
        ys = [y0 + (y1 - y0) * (x - x0) / (x1 - x0) if abs(x1 - x0) > 1e-12 else min(y0, y1) for x0, y0, x1, y1 in sg]
        return min(ys)

    # the wall at each slot's edges and centre, and the real half-round rod against the curved face: over the rod's width,
    # how far its surface stays behind the face (positive = recessed), and where it comes closest
    slots_tab = []
    r = hw.ROD_W / 2
    for sx in (-1, 1):
        x0 = sx * hw.TUBE_CC / 2
        walls_ = [(lab, x, m.FRONT - face_y(x)) for lab, x in (("inner edge", x0 - sx * SLOT_W / 2), ("centre", x0), ("outer edge", x0 + sx * SLOT_W / 2))]
        rods_ = []
        for tape in hw.TAPE:
            tf = m.GLASS_T0 - tape                                  # the rod's flat face
            xs_ = np.linspace(x0 - r, x0 + r, 801)
            rec = [(tf - math.sqrt(max(r * r - (x - x0) ** 2, 0.0)) - face_y(x), x) for x in xs_]
            rods_.append((tape,) + min(rec))
        slots_tab.append(("left" if sx < 0 else "right", walls_, rods_))
    rod_min = min(v for _, _, rr in slots_tab for _, v, _ in rr)
    check(rod_min > 0, f"a rod stands proud of the curved face ({rod_min:.3f})")
    # the openings on the face, measured on the solid: the bevel planes meet the curved face in vertical lines
    env_side = Compound([f for f in m.shell_env().faces() if f.geom_type != GeomType.PLANE])
    xs_open = []
    for e in shell_core.edges():                  # straight vertical edges (stored as lines or B-splines), slot-long
        eb = e.bounding_box()
        if eb.size.X > 1e-5 or eb.size.Y > 1e-5 or abs(eb.size.Z - SLOT_L) > 1e-3 or eb.max.Y > m.FRONT - 0.01:
            continue
        if dist_shapes(e, env_side)[0] < 1e-4:
            xs_open.append(round(eb.center().X, 4))
    xs_open = sorted(set(xs_open))
    check(len(xs_open) == 4, f"slot opening edges on the face: {xs_open}")
    openings = [(xs_open[0], xs_open[1]), (xs_open[2], xs_open[3])]
    bridge_face = xs_open[2] - xs_open[1]
    # the specified slot (a SLOT_LAND land at the flat inner face, then 45 deg through ~4.5 of wall at the slots' inner
    # edges) may leave a narrower bridge than v1's 4.0: checked against OVAL_BRIDGE_MIN instead, and reported
    check(bridge_face >= OVAL_BRIDGE_MIN, f"bridge between the slots {bridge_face:.3f}")

    # ---- ceiling, measured ----
    zc = m.H - TOP_T
    flats = [f for f in shell_core.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6 and abs(f.center().Z - zc) < 1e-3]
    check(len(flats) == 1, f"flat ceiling: {len(flats)}")
    fb = flats[0].bounding_box()
    check(min(fb.size.X, fb.size.Y) <= BRIDGE_MAX, "ceiling bridge too long")

    # ---- walls, measured ----
    env, cav = m.shell_env(), m.cavity()
    cav_faces = Compound([f for f in cav.faces() if not (f.geom_type == GeomType.PLANE and abs(f.center().Z + 1) < 1e-6)])
    groups = {}
    for f in env.faces():
        if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6:
            continue
        nm = "top" if (f.geom_type == GeomType.PLANE and f.normal_at().Z > 1 - 1e-6) else ("top edge R6" if f.center().Z > m.H - OVAL["R_TOP"] - 1 else "sides")
        groups.setdefault(nm, []).append(f)
    walls = {k: dist_shapes(Compound(v), cav_faces) for k, v in groups.items()}
    wmin = min(v for v, _ in walls.values())
    check(wmin >= WALL_MIN - 1e-3, "oval: minimum wall " + ", ".join(f"{k} {v:.2f} at {tuple(round(q, 1) for q in p)}" for k, (v, p) in walls.items()))
    wall_glass_edge = m.FRONT - face_y(hw.GLASS_W / 2)

    # ---- USB ----
    usb_cut = m.usb_cutter()
    usb_z = m.SOCKET_S
    check(usb_z - hw.USB_HOLE_H / 2 >= 2.5, "USB hole too close to the rim")
    ad = adapter.solid()
    usb_lid = gap(usb_cut, lid)
    bdist = BRepExtrema_DistShapeShape(shell_core.wrapped, ad.wrapped)
    bdist.Perform()
    q = bdist.PointOnShape1(1)
    ad_near, ad_face = bdist.Value(), face_name(shell_core, (q.X(), q.Y(), q.Z()))
    check(ad_near >= ADAPTER_BACK_MIN - 1e-6, f"adapter {ad_near:.2f} from the shell")
    sock_y = m.to_world(m.AD_T[1], m.SOCKET_S)[0]
    back_y = OVAL["D"] - WALL

    # ---- assembly ----
    print(f"[{name}] path checks ...", flush=True)
    gaps = check_paths(m, shell_core, lid, moving, adapter, order)
    final = [("shell", shell), ("lid", lid), ("adapter", ad)] + [(b.name, b.solid()) for b in moving]
    check_static(final)
    rod = [b for b in moving if isinstance(b, Rod)][0]
    misalign = volume_common(rod.solid(et=INSERT_SHIFT, es0=-ROD_MISALIGN, es1=ROD_MISALIGN), shell_core)
    boss = m.bosses()
    sweeps = all_sweeps(m, order)
    boss_gap = min((gap(boss, sw), n) for n, sw in sweeps)
    check(boss_gap[0] > 0.2, f"magnet bosses {boss_gap[0]:.2f} from the {boss_gap[1]}")

    # ---- front logo ----
    FL = front_logo_check(m, shell, lid, order)
    PK = pocket_check(m, shell, lid, order, spots)
    bow = max(face_y(-FL["w"] / 2), face_y(FL["w"] / 2)) - face_y(0.0)    # the outer face behind the letters' ends

    # ---- test strip: the front slice of the shell, from the rim up past the slots, logo and recess included ----
    zs1 = m.SLOT_S[1] + OVAL_STRIP_ABOVE
    strip = m.shell("strip") & box(-60, 60, -10, OVAL_STRIP_Y, -1, zs1)
    check(strip.is_valid and len(strip.solids()) == 1, "test strip is not one valid solid")
    for n, o in final:
        if n not in ("shell", "lid"):
            v = volume_common(strip, o)
            check(v < EPS_V, f"test strip overlaps the {n} ({v:.2f} mm3)")
    sbb = strip.bounding_box()
    foot_f = [f for f in strip.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6 and abs(f.center().Z) < 1e-6]
    foot_area = sum(f.area for f in foot_f)
    fbb = Compound(foot_f).bounding_box()

    # ---- extents, tipping ----
    from build123d import CenterOf
    bb = Compound([shell, lid]).bounding_box()
    tops = [f for f in shell.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z > 1 - 1e-6 and abs(f.center().Z - m.H) < 1e-4]
    tb = tops[0].bounding_box()
    parts_m = [(p.volume / 1000 * DENSITY, p.center(CenterOf.MASS)) for p in (shell, lid)]
    bo = Vector(0, *m.to_world((m.GLASS_T0 + m.BOARD_T1) / 2, m.PCB_S0 + hw.PCB_H / 2))
    ba = Vector(0, *m.to_world(sum(m.BAT_T) / 2, m.BAT_S0 + hw.BAT_H / 2))
    parts_m += [(BOARD_G, bo), (BATTERY_G, ba)]
    mass = sum(g for g, _ in parts_m)
    cm = sum((p * g for g, p in parts_m), Vector(0, 0, 0)) * (1 / mass)
    bf = [f for f in lid.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6][0]
    foot = bf.bounding_box()
    h_top = m.H + LID_T
    z_cm = cm.Z + LID_T
    tip = dict(back=mass * (foot.max.Y - cm.Y) / h_top, fwd=mass * (cm.Y - foot.min.Y) / h_top,
               ang_back=math.degrees(math.atan2(foot.max.Y - cm.Y, z_cm)), ang_fwd=math.degrees(math.atan2(cm.Y - foot.min.Y, z_cm)))

    # ---- exports ----
    for f in list(out.glob("*.stl")) + list(out.glob("*.step")):
        f.unlink()
    parts = {"shell": shell, "lid": lid, "teststrip": strip}
    files = {}
    for n, p in parts.items():
        export_part(p, out, n, files)
    for n, s_ in final:
        s_.label = n
        if n in ("shell", "lid"):
            s_.color = Color("tan" if n == "shell" else "sienna")
    for n, s_ in final:
        if n not in parts:
            write_stl(s_, out / f"dummy-{n}.stl")
    files["assembly"] = (write_step(Compound([s_ for _, s_ in final]), out / "assembly.step"), None)
    big = 3 * m.H
    for tag_, cutter in (("x", box(hw.TUBE_CC / 2, big, -big, big, -big, big)), ("z", box(-big, big, -big, big, zmid, big))):
        for n, s_ in final:
            cs = s_ - cutter
            if cs.volume > 0.01:
                write_stl(cs, out / f"section-{tag_}-{n}.stl")
    write_stl(shell & box(-16, 16, -5, m.FRONT + 3, -1, 25), out / "section-l-shell.stl")   # the front wall round the logo
    import json
    st, sb = (-hw.TUBE_CC / 2, face_y(-hw.TUBE_CC / 2), m.SLOT_S[1]), (-hw.TUBE_CC / 2, face_y(-hw.TUBE_CC / 2), m.SLOT_S[0])
    (out / "focus.json").write_text(json.dumps({"slot_top": list(st), "slot_bottom": list(sb), "H": m.H, "D": m.D,
                                                "logo": [0.0, face_y(0.0), m.front_logo()["zc"]], "logo_normal": [0.0, -1.0, 0.0],
                                                "zmid": zmid, "tilt": 0.0}))

    # ---- report ----
    def worst(move, only):
        c_ = [(g, n) for (mv, n), g in gaps.items() if mv == move and n.startswith(only)]
        return f"{min(c_)[0]:.2f}" if c_ else "n/a"

    R = []
    R.append(f"DESK HOUSING smooth / oval  (superellipse plan |2x/W|^n + |2(y - D/2)/D|^n = 1, W {OVAL['W']}, D {OVAL['D']}, n {OVAL['N']}, "
             f"straight up; flat top, edge R{OVAL['R_TOP']}; upright)")
    R.append(f"assembly     order '{order}': {ORDERS[order]} ({BAT_HOLD}); then the adapter from below, then the lid")
    R.append("[m] measured on the finished solids (OCC distances, sections, faces, edges); [d] derived from the parameters")
    R.append(f"outer        [m] {bb.size.X:.2f} x {bb.size.Y:.2f} x {bb.size.Z:.2f} (W x D x H, shell + lid); shell {m.H} tall + lid {LID_T}; "
             f"flat top {tb.size.X:.2f} x {tb.size.Y:.2f}")
    R.append(f"front        [d] curved outside, flat inside at y {m.FRONT} (centre-line thickness: the smallest, 0.05 steps, whose flat "
             f"inner face spans the {hw.GLASS_W} glass + 0.3 each side inside the {WALL} offset); [m] flat face {glb.size.X:.2f} wide, "
             f"z {glb.min.Z:.2f}..{glb.max.Z:.2f}; front wall along y at the glass edge (x {hw.GLASS_W / 2}) {wall_glass_edge:.2f}")
    R.append(f"cavity       [d] the plan offset {WALL} inwards (a spline through exactly offset points), closed at the front by the flat "
             f"face; vertical to z {m.Z_RAMP:.2f}, then a 45 deg taper all round, {OVAL['RAMP']} high (inset {OVAL['RAMP']}), to the flat ceiling at z {zc:.2f}")
    R.append(f"  ceiling    [m] flat ceiling face {fb.size.X:.2f} x {fb.size.Y:.2f} (bridge {min(fb.size.X, fb.size.Y):.2f}, in Y); every other "
             f"ceiling surface is the 45 deg taper; its junctions are sharp (no blend passes 45 deg)")
    R.append(f"board        [d] PCB bottom z {m.PCB_S0:.2f} (adapter's lowest point {m.cfg['ADAPTER_FLOOR']} above the rim), AA centre z {m.AA_SC:.2f}; "
             f"battery z {m.BAT_S0:.2f}..{m.BAT_S0 + hw.BAT_H:.2f}, y {m.BAT_T[0]:.2f}..{m.BAT_T[1]:.2f} (centred, v1); glass y {m.GLASS_T0:.2f}..{m.GLASS_T1:.2f}")
    R.append(f"slots        [d] E adapted to the curved wall: straight {SLOT_W} x {SLOT_L:.2f} land {m.RIM} deep at the flat inner face, then "
             f"45 deg on the long sides out to the curved face, straight ends; x +-{hw.TUBE_CC / 2}, z {m.SLOT_S[0]:.2f}..{m.SLOT_S[1]:.2f}; "
             f"{(hw.AA_H - SLOT_L) / 2:.2f} inside the lit area per end")
    R.append(slot_lines(m, SL, ROD_CLR, ROD_CLR_D))
    R.append(f"  openings   [m] on the face (the edges where the bevels meet it): left x {openings[0][0]:.4f}..{openings[0][1]:.4f} "
             f"({openings[0][1] - openings[0][0]:.2f} wide), right x {openings[1][0]:.4f}..{openings[1][1]:.4f}; bridge between them "
             f"{bridge_face:.3f} (v1 wants 4.0" + ("" if bridge_face >= 4.0 else f"; accepted >= {OVAL_BRIDGE_MIN} here") + ")")
    for side, walls_, rods_ in slots_tab:
        R.append(f"  {side:<5} slot [m] front wall: " + ", ".join(f"{lab} (x {x:+.2f}) {t:.2f}" for lab, x, t in walls_))
        R.append(f"             [m face, d rod] the half-round rod against the curved face, over its width: recessed everywhere; closest "
                 + "; ".join(f"{v:.3f} behind it at x {x:+.2f} (tape {t})" for t, v, x in rods_))
    R.append(f"rods         [d] {hw.ROD_W} x {hw.ROD_H} x {ROD_L:.2f}, crown {hw.ROD_H + hw.TAPE[0] - hw.GASKET:.2f}..{hw.ROD_H + hw.TAPE[1] - hw.GASKET:.2f} "
             f"in front of the flat inner face; in the slot {(SLOT_W - hw.ROD_W) / 2:.2f} per side, {(SLOT_L - ROD_L) / 2:.2f} per end")
    R.append(f"insertion    board + rods: up at {INSERT_SHIFT:.2f} further back, then forward; [m] up: rods to the front wall {worst('up', 'rod')}, "
             f"plugs {worst('up', 'plug')}, buttons {worst('up', 'button')}, glass {worst('up', 'glass')}; forward: rods in the slots "
             f"{worst('forward', 'rod')} (rods {ROD_MISALIGN} off along the face cut {misalign:.2f} mm3 each)")
    R.append(f"  battery    [m] up {BAT_HOLD} behind its seat, then forward: clearance to the shell {gaps[('bat-up', 'battery')]:.2f} up, "
             f"{gaps[('bat-fwd', 'battery')]:.2f} forward; to the board / plugs {gaps[('bat-up', 'battery-board')]:.2f}")
    R.append(f"  adapter    [m] from below along its plug axis: free; nearest shell surface {ad_near:.2f} ({ad_face}); [d] its socket face "
             f"{back_y - sock_y:.2f} in front of the back wall's inner face on the centre line")
    R.append(f"  lid move   [m] straight up, free; lid to the adapter {gaps[('lid', 'adapter')]:.2f}")
    R.append(f"magnets      [m] 4 x D{hw.MAG_D} x {hw.MAG_H} in holes D{hw.MAG_D + hw.MAG_CLR_D} x {hw.MAG_H + hw.MAG_CLR_H}; axes {OVAL['MAG_DEPTH']} "
             f"inside the outer surface, each in a boss D{2 * OVAL['BOSS_R']:g} x {OVAL['BOSS_H']} inside the rim; wall round the hole (rim / lid): " +
             ", ".join(f"({x:.2f}, {y:.2f}) {ms:.2f} / {ml:.2f}" for (x, y), (ms, ml) in zip(spots, meats)) +
             f"; bosses {boss_gap[0]:.2f} from the nearest sweep ({boss_gap[1]})")
    R.append(f"USB          v1 hole {hw.USB_HOLE_W} x {hw.USB_HOLE_H} R{hw.USB_HOLE_R} through the back on the centre line at z {usb_z:.2f} "
             f"([d] {usb_z - hw.USB_HOLE_H / 2:.2f} above the rim; [m] {usb_lid:.2f} to the lid)")
    R += front_logo_lines(m, FL)
    R += pocket_lines(PK)
    R.append(f"  bow        [m] the curved face lies {bow:.3f} further back at the letters' ends than on the centre line, so the flat "
             f"{FRONT_LOGO_T} inlay, flush at the centre, stands {bow:.3f} proud there")
    R.append(f"test strip   [m] teststrip.*: the shell in front of y {OVAL_STRIP_Y} from the rim to z {zs1:.2f} ({OVAL_STRIP_ABOVE} above the slots), "
             f"logo cut and recess included, no magnet holes; {sbb.size.X:.2f} x {sbb.size.Y:.2f} x {sbb.size.Z:.2f}, {strip.volume / 1000:.2f} cm3; "
             f"stands on its rim as the shell prints: footprint {foot_area:.0f} mm2 within x {fbb.min.X:.2f}..{fbb.max.X:.2f}, y "
             f"{fbb.min.Y:.2f}..{fbb.max.Y:.2f} (the front wall and the two side returns), {sbb.size.Z:.2f} tall; no overlap with the "
             f"glass, board, buttons, plugs, rods, battery or adapter seated")
    R.append("min wall     [m] between the cavity surface and the outer surface (exact; before slots, logo, magnets, USB; bottom break "
             "excluded): " + ", ".join(f"{k} {v:.2f}" for k, (v, p) in sorted(walls.items(), key=lambda kv: kv[1][0])))
    R.append(f"  minimum    [m] {wmin:.2f}; by design thinner: slot land {m.RIM} deep, " + (f"logo skin {FL['skin'][0]:.2f}" if FL["pocket"] is not None else f"logo strips {FL['strip']:.2f}") + f", magnet meat {min(min(a) for a in meats):.2f}")
    R.append(f"print        shell standing on its rim (opening down), meant to print without supports (check the layer preview): walls "
             f"vertical, 45 deg taper under the top, [m] flat bridge {min(fb.size.X, fb.size.Y):.2f}; slot ends bridge {SLOT_W}.. the opening, "
             f"the slots' sides a {m.RIM} land at the inner face (no knife edge); logo pocket: its top a bridge {PK['pw']:.1f}..{PK['mouth'][0]:.1f} "
             f"wide, its sides sloped {LOGO_FLARE_DEG:g} deg; the USB hole's round top is a short local overhang; bosses sit on the bed side. "
             f"Lid: flat, top face down")
    R.append(SLICER_LINE)
    R.append(f"volumes cm3  [m] shell {shell.volume / 1000:.1f}, lid {lid.volume / 1000:.1f}  ({(shell.volume + lid.volume) / 1000 * DENSITY:.0f} g at {DENSITY} g/cm3)")
    R.append(f"tipping      [m+d] mass {mass:.0f} g (print + board {BOARD_G:.0f} g + battery {BATTERY_G:.0f} g, both assumed); centre of mass "
             f"y {cm.Y:.1f}, {z_cm:.1f} above the desk; foot y {foot.min.Y:.2f}..{foot.max.Y:.2f} (on the centre line)")
    R.append(f"  push       horizontal at the top ({h_top:.1f} above the desk) that tips it: backwards {tip['back']:.0f} gf, forwards "
             f"{tip['fwd']:.0f} gf; tips over when tilted {tip['ang_back']:.0f} deg back / {tip['ang_fwd']:.0f} deg forward")
    R += file_lines(files)
    R.append("open items (need the real parts):")
    R.append(f"  - rods on the forward move: they must line up with the slots within +-{(SLOT_L - ROD_L) / 2:.2f} along the face "
             f"({ROD_MISALIGN} off cuts {misalign:.2f} mm3 per rod)")
    R.append("  - magnets: glue them into the bosses, do not press")
    R.append("  - the slot openings on a curved face, the rods sitting under it, the fine letter strips: judge on the test strip")
    R.append("  - board and battery masses, the port's position in the board stack, the adapter's real shape (all assumed, as in v1)")
    R.append("")
    R.append("clearances along the insertion path, mm, measured on the swept solids (0.00 = it ends seated there):")
    R.append("  body                up   forward")
    for b in moving:
        if ("up", b.name) in gaps:
            R.append(f"  {b.name:<16} {gaps[('up', b.name)]:6.2f} {gaps.get(('forward', b.name), math.nan):9.2f}")
        elif ("bat-up", b.name) in gaps:
            R.append(f"  {b.name:<16} {gaps[('bat-up', b.name)]:6.2f} {gaps[('bat-fwd', b.name)]:9.2f}   (its own moves, {BAT_HOLD} behind its seat)")
    text = "\n".join(R)
    (out / "report.txt").write_text(text + "\n")
    print(text, flush=True)
    return m


def build_inlays():
    """The shared inlays of the small front logo (upright, oval)."""
    inl = make_front_inlays()
    n = len(inl.solids())
    st = write_step(inl, OUT_ROOT / "logo-inlays-small.step")
    write_stl(inl, OUT_ROOT / "logo-inlays-small.stl")
    ms = check_stl(inl, OUT_ROOT / "logo-inlays-small.stl", bodies=n)
    bb = inl.bounding_box()
    text = "\n".join([
        f"LOGO INLAYS, small (front logo of upright and oval): letters {FRONT_LOGO_W:g} x {hw.LETTERS_ASPECT * FRONT_LOGO_W:.2f}, "
        f"{FRONT_LOGO_T} thick, mirrored (outer face on the bed); clearance per side {', '.join(str(c) for c in hw.INLAY_CLRS)}, "
        f"set i has i + 1 dimples on the back of the H; {n} pieces, {bb.size.X:.1f} x {bb.size.Y:.1f} overall",
        f"strips between the letter cuts {hw.STRIP_PER_MM * FRONT_LOGO_W:.2f} (scaled from v1's 24 mm letters)",
    ] + file_lines({"logo-inlays-small": (st, ms)}))
    (OUT_ROOT / "logo-inlays-small.txt").write_text(text + "\n")
    print(text, flush=True)


STENCIL_T = WALL_MIN - LOGO_SKIN - STENCIL_BACK      # 1.9


def stencil_block(pl, pw, ph, t=STENCIL_T):
    """A stencil's outline as a solid, its bed face on plane pl: the pocket's floor outline less STENCIL_CLR per side
    (STENCIL_CLR_TOP at the top, pl's +y), its two ends sloped as the pocket's, t thick."""
    k = math.tan(math.radians(LOGO_FLARE_DEG))
    return flared_block(pl, pw - 2 * STENCIL_CLR, ph - STENCIL_CLR - STENCIL_CLR_TOP, STENCIL_R - STENCIL_CLR, t, k,
                        dy=(STENCIL_CLR - STENCIL_CLR_TOP) / 2)


def stencil_apertures(st, w, s, t):
    """A stencil (as printed, bed face at z 0) against its letters: on the bed face and on the top face, one hole per
    letter polygon, each the letter's area and centroid (shrunk by (s - s0) / 2 for wider strips) at the mirrored place
    (-u, v): seen from outside, through the skin, the bed face shows the logo the right way round. The expected holes are
    built here from hw.letters_mm, independently of the cutters. Raises; returns the hole areas."""
    from build123d import offset
    s0 = hw.STRIP_PER_MM * w
    want = []
    for poly in hw.letters_mm(w):
        q = Polygon(*[(u, v) for u, v in poly], align=None)                 # as seen from outside
        if s > s0 + 1e-9:
            q = offset(q, -(s - s0) / 2)
        c = q.center(CenterOf.MASS)
        want.append((q.area, -c.X, c.Y))
    mirror_ok = all(any(abs(a - a2) < 1e-6 * a and abs(-x - x2) < 1e-6 and abs(y - y2) < 1e-6 for a2, x2, y2 in want)
                    for a, x, y in want)
    check(not mirror_ok, "stencil: the logo is mirror-symmetric, the reading-direction test would be blind")
    for z, sg in ((0.0, -1), (t, 1)):
        fs = [f for f in st.faces() if f.geom_type == GeomType.PLANE and abs(f.normal_at().Z - sg) < 1e-6 and abs(f.center().Z - z) < 1e-6]
        check(len(fs) == 1, f"stencil {s:.2f}: {len(fs)} faces at z {z}")
        got = [(Face(wr).area, Face(wr).center(CenterOf.MASS)) for wr in fs[0].inner_wires()]
        check(len(got) == len(want), f"stencil {s:.2f}: {len(got)} apertures at z {z}, the logo has {len(want)} letters")
        for a, x, y in want:
            hit = [g for g in got if abs(g[0] - a) < 1e-4 * a and abs(g[1].X - x) < 1e-3 and abs(g[1].Y - y) < 1e-3]
            check(len(hit) == 1, f"stencil {s:.2f}: no aperture of {a:.3f} mm2 at ({x:.3f}, {y:.3f}) on z {z} (the letters "
                                 f"missing, misplaced, the wrong size or not mirrored)")
    return [a for a, _, _ in want]


def make_stencils(w, strips):
    """Logo stencils for the glow-through pocket: stencil_block (the pocket's floor outline less the clearances, its two
    vertical sides sloped as the pocket's: printed flat they widen upwards, a LOGO_FLARE_DEG overhang), the letters as
    straight holes, STENCIL_T thick; mirrored so the face that meets the skin lies on the bed. One per strip width in
    `strips` (None: the logo as designed; wider strips shrink the letters), in a column."""
    from build123d import offset
    h = hw.LETTERS_ASPECT * w
    s0 = hw.STRIP_PER_MM * w
    pw, ph = w + 2 * STENCIL_MARGIN, h + 2 * STENCIL_MARGIN
    sw, sh = pw - 2 * STENCIL_CLR, ph - STENCIL_CLR - STENCIL_CLR_TOP
    t = STENCIL_T
    k = math.tan(math.radians(LOGO_FLARE_DEG))
    out, rows, areas = [], [], []
    for i, s in enumerate(strips):
        s = s0 if s is None else s
        check(s >= s0 - 1e-9, f"stencil strip {s} narrower than the logo's {s0:.2f}")
        st = stencil_block(Plane.XY, pw, ph, t)
        for poly in hw.letters_mm(w):
            hole = Polygon(*[(-u, v) for u, v in poly], align=None)
            if s > s0 + 1e-9:
                hole = offset(hole, -(s - s0) / 2)
            st = st - Pos(0, 0, -1) * extrude(hole, t + 2)
        check(st.is_valid and len(st.solids()) == 1, f"stencil {s:.2f}: not one valid solid")
        areas.append(stencil_apertures(st, w, s, t))
        bb = st.bounding_box()
        check(abs(bb.size.X - (sw + 2 * k * t)) < 1e-3 and abs(bb.size.Y - sh) < 1e-3 and abs(bb.size.Z - t) < 1e-6,
              f"stencil {s:.2f}: {bb.size.X:.3f} x {bb.size.Y:.3f} x {bb.size.Z:.3f}")
        out.append(Pos(0, -i * (ph + 4), 0) * st)
        rows.append(s)
    return Compound(out), dict(w=w, h=h, s0=s0, pocket=(pw, ph), mouth=(pw + 2 * k * (WALL_MIN - LOGO_SKIN), ph),
                               size=(sw, sh), top=(sw + 2 * k * t, sh), t=t, strips=rows, areas=areas)


def build_stencils():
    """Stencils for the small front logo (upright, oval) and the tilt15's side logo."""
    for tag, w, kind, who in (("small", FRONT_LOGO_W, "front", "the front logo of upright and oval"),
                              ("tilt15", VARIANTS["tilt15"]["LOGO_W"], "side", "the tilt15's side logo")):
        c, S = make_stencils(w, STENCIL_STRIPS[kind])
        n = len(c.solids())
        base = OUT_ROOT / f"logo-stencils-{tag}"
        st = write_step(c, base.with_suffix(".step"))
        write_stl(c, base.with_suffix(".stl"))
        ms = check_stl(c, base.with_suffix(".stl"), bodies=n)
        text = "\n".join([
            f"LOGO STENCILS, {tag} ({who}): letters {S['w']:g} x {S['h']:.2f}; pocket {S['pocket'][0]:.2f} x {S['pocket'][1]:.2f} R{STENCIL_R:g} "
            f"at its floor (behind the {LOGO_SKIN} skin), its two vertical sides sloped {LOGO_FLARE_DEG:g} deg out to {S['mouth'][0]:.2f} x "
            f"{S['mouth'][1]:.2f} at a {WALL_MIN} wall's inner face (the oval's is deeper), top and bottom straight",
            f"stencil [d] {S['t']:.2f} thick ({WALL_MIN} wall - {LOGO_SKIN} skin - {STENCIL_BACK} inside the mouth); bed face {S['size'][0]:.2f} x "
            f"{S['size'][1]:.2f} R{STENCIL_R - STENCIL_CLR:g}, its two vertical sides sloped {LOGO_FLARE_DEG:g} deg as the pocket's (a "
            f"{LOGO_FLARE_DEG:g} deg overhang printed flat), top face {S['top'][0]:.2f} x {S['top'][1]:.2f}; clearance {STENCIL_CLR} per side "
            f"in its plane ({STENCIL_CLR * math.cos(math.radians(LOGO_FLARE_DEG)):.2f} normal to the sloped sides), {STENCIL_CLR_TOP} at the top "
            f"(the pocket's ceiling is a bridge); mirrored, the face that meets the skin on the bed",
            "strip widths, first row to last (as printed, top to bottom in the slicer's top view): " +
            ", ".join(f"{s:.2f}" + (" (as designed)" if abs(s - S['s0']) < 1e-9 else "") for s in S["strips"]),
            "apertures [m] on the bed face and the top face of each: one per letter, at the mirrored place (reads right from "
            "outside, through the skin), areas mm2: " + "; ".join(", ".join(f"{a:.2f}" for a in ar) for ar in S["areas"]),
            "paint them black (all faces); push into the pocket from inside, the reading direction checked from outside; a drop of glue",
        ] + file_lines({f"logo-stencils-{tag}": (st, ms)}))
        base.with_suffix(".txt").write_text(text + "\n")
        print(text, flush=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    order = ORDER
    for a in sys.argv[1:]:
        if a.startswith("--order="):
            order = a.split("=", 1)[1]
        elif a == "--rods-after":
            order = "rods-after"
    check(order in ORDERS, f"unknown order {order}; one of {', '.join(ORDERS)}")
    names = args or list(VARIANTS)
    for n in names:
        if n in ("inlays", "stencils"):
            continue
        build_oval(order) if n == "oval" else build(n, order)
    if LOGO_STYLE == "stencil":
        build_stencils()
    elif "inlays" in names or any(VARIANTS[n]["LOGO_MODE"] == "front" for n in names if n in VARIANTS):
        build_inlays()
