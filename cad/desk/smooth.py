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


def _edge_points(e, step):
    """Points along an edge about `step` apart, evaluated in C++ (GCPnts_UniformAbscissa): fast on long B-spline edges."""
    from OCP.GCPnts import GCPnts_UniformAbscissa
    c = BRepAdaptor_Curve(e.wrapped)
    n = max(2, int(e.length / step) + 1)
    ua = GCPnts_UniformAbscissa(c, float(e.length / (n - 1)), -1.0)     # the abscissa overload (an int is taken as one too)
    if ua.IsDone() and ua.NbPoints() >= n - 1:
        us = [ua.Parameter(i) for i in range(1, ua.NbPoints() + 1)]
        if us[0] > c.FirstParameter() + 1e-12:
            us.insert(0, c.FirstParameter())
        if us[-1] < c.LastParameter() - 1e-12:      # it may stop short of the end: the last segment would be missing
            us.append(c.LastParameter())
        pts = [c.Value(u) for u in us]
    else:                                    # (short or closed edges it refuses): evenly in the parameter, twice as dense
        u0, u1 = c.FirstParameter(), c.LastParameter()
        pts = [c.Value(u0 + (u1 - u0) * i / (2 * n - 1)) for i in range(2 * n)]
    return np.array([[p.X(), p.Y()] for p in pts])


def section_segments(shape, z, bbox=None, step=0.05, fast=False):
    """Section of a solid by the plane z: its boundary as 2D segments (N, 4). fast: edges sampled in C++ and skipped
    when they miss bbox (the pebble's long B-spline sections; build123d's position_at takes ~10 ms a point there)."""
    sec = BRepAlgoAPI_Section(shape.wrapped, gp_Pln(gp_Pnt(0, 0, z), gp_Dir(0, 0, 1)))
    sec.Build()
    edges = Compound(sec.Shape()).edges()
    if not edges:                    # the plane section comes back empty on some boolean results (oval): use the bottom
        sl = shape & box(-500, 500, -500, 500, z, z + 0.002)      # face of a thin slab instead
        edges = [e for f in sl.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6 for e in f.edges()]
        check(len(edges) > 0, f"no section at z {z}")
    segs = []
    for e in edges:
        if fast:
            if bbox is not None:
                eb = e.bounding_box()
                if eb.max.X < bbox[0] or eb.min.X > bbox[1] or eb.max.Y < bbox[2] or eb.min.Y > bbox[3]:
                    continue
            p = _edge_points(e, step)
        else:
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

    def front_out_t(self, x, s):
        """Body frame: t of the outer front surface at (x, s) (untilted shells: world y at z = s; the pebble overrides it)."""
        check(not self.tilt, "front_out_t: a tilted shell must override it")
        return self.front_out_y(x, s)

    def logo_floor_t(self, pw, ph, zc):
        """The outer front's largest t over a front pocket's floor (pw x ph, centred on x 0, s zc)."""
        return max(self.front_out_t(x, z) for x in np.linspace(-pw / 2, pw / 2, 81) for z in (zc - ph / 2, zc, zc + ph / 2))

    def front_logo_wz(self):
        """The small front logo: letters' width and centre along the face (s; world z on the untilted shells)."""
        return FRONT_LOGO_W, (FRONT_LOGO_RIM + self.GLASS_S0 - FRONT_LOGO_GLASS) / 2

    insert_shift = INSERT_SHIFT                # board + rods: how far behind their seat they travel up
    tube_cc = hw.TUBE_CC                       # the rods' / tubes' centre distance (the pebble: its own)
    logo_skin = LOGO_SKIN                      # glow-through pocket: skin left over its floor
    logo_recess = True                         # front logo: a flat recess on the inside where the front is thicker than an inlay

    def lid_sweep(self, drop):
        """The lid's move straight up (world Z): the prism of the lid blank's largest outline (its bottom, before the break)
        from far below up to the rim; it contains the real lid, toe included, at every height of the move."""
        bot = [f for f in self.lid_env().faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6]
        check(len(bot) == 1, "lid blank bottom face")
        return Pos(0, 0, -drop) * extrude(Face(bot[0].outer_wire()).moved(Pos(0, 0, LID_T)), drop)

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
        if self.cfg["LOGO_MODE"] == "front":           # body frame (t, s) = world (y, z) on the untilted shells
            w, zc = self.front_logo_wz()
            h = hw.LETTERS_ASPECT * w
            pw, ph = w + 2 * STENCIL_MARGIN, h + 2 * STENCIL_MARGIN
            # the oval's face curves back towards the sides: its skin is thicker on the centre line
            floor = self.logo_skin + self.logo_floor_t(pw, ph, zc)
            oy, oz = self.to_world(floor, zc)
            pl = Plane(origin=(0, oy, oz), x_dir=(-1, 0, 0), z_dir=(0, self.c, -self.sn))
            depth = self.FRONT - floor
            wall_box = self.wt(box(-60, 60, -10, self.FRONT, -5, 60))
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
        w, zc = self.front_logo_wz()
        h = hw.LETTERS_ASPECT * w
        pl = Plane(origin=(0, -3.0, zc), x_dir=(1, 0, 0), z_dir=(0, -1, 0))     # seen from the front: x right, z up
        cut, floor, pocket = None, None, None
        if LOGO_STYLE == "stencil":
            # one rounded-rectangle pocket from inside; its flat floor LOGO_SKIN behind the outer surface where that
            # comes closest (the oval's face curves back towards the sides: its skin is thicker on the centre line)
            P = self.pocket()
            cut, floor, pocket = P["cut"], P["floor"], (P["pw"], P["ph"])
        else:
            check(not self.tilt, "front logo: cut-through letters are built for an untilted front only")
            for poly in hw.letters_mm(w):
                e = extrude(pl * Polygon(*[(u, v) for u, v in poly], align=None), self.FRONT + 5.0, dir=(0, 1, 0))
                cut = e if cut is None else cut + e
        recess = None
        if self.FRONT > FRONT_LOGO_T + 1e-6 and self.logo_recess:
            m_ = FRONT_LOGO_RECESS
            recess = self.wt(box(-w / 2 - m_, w / 2 + m_, FRONT_LOGO_T, self.FRONT + 1.0, zc - h / 2 - m_, zc + h / 2 + m_))
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
                s = s - self.slot_cutter(sx * self.tube_cc / 2)
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
             Rod(self, "rod-l", -self.tube_cc / 2), Rod(self, "rod-r", self.tube_cc / 2)]
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
    dt = m.insert_shift if order == "v1" else 0.0
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
    res = {sx: dict(x=sx * m.tube_cc / 2, w=[], depth=[]) for sx in (-1, 1)}
    for zs in np.linspace(m.SLOT_S[0] + 0.3, m.SLOT_S[1] - 0.3, SLOT_SECTIONS):
        seg = section_segments(s, float(zs), bbox=(-m.tube_cc / 2 - 9, m.tube_cc / 2 + 9, -2, m.FRONT + 0.5), step=0.02,
                               fast=getattr(m, "fast_sections", False))
        for sx in (-1, 1):
            x0 = sx * m.tube_cc / 2
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
                off = np.abs(walls[:, j] - walls[0, j]) > getattr(m, "land_tol", 0.002)
                n = int(np.argmax(off)) if off.any() else len(ys)
                res[sx]["depth"].append(n * LAND_DY)
    out = [dict(x=r["x"], w=min(r["w"]), w_max=max(r["w"]), depth=min(r["depth"]), n=len(r["w"])) for r in res.values()]
    clr = {t: min(gap(Rod(m, "rod", sx * m.tube_cc / 2, t).solid(), shell) for sx in (-1, 1)) for t in hw.TAPE}
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
STEP_VOL_TOL_MESH = 5e-4                 # ... both measured on fine meshes (the pebble: vol_props precise; two 0.002 meshes of the
                                         # same surfaces, parameterised differently, differ by up to ~2e-4)


VOL_MESH = (0.003, 0.03)                 # vol_props precise: deflection (mm), angle (rad)
VOL_MESH_K = (1.0, 0.8, 0.6)             # ... retried this much finer when a mesh comes out open
VOL_MESH_LOG = []
_VOL_CACHE = {}


def vol_props(shape, precise=False, read_back=False):
    """Volume and centre of mass. precise: from a fine triangulation (VOL_MESH, closed: checked; finer than the STLs', so
    comparing the two catches a bad tessellation). On the pebble's trimmed B-spline faces OCC's integration misreads: the default rule by 0.3 %,
    the adaptive one by up to 0.5 % (the lid with its magnet holes: 7499 against 7535 meshed and from the sections)."""
    if not precise:
        return shape.volume, shape.center(CenterOf.MASS)
    key = (hash(shape.wrapped), read_back)
    if key in _VOL_CACHE:
        return _VOL_CACHE[key]
    import tempfile, pyvista as pv
    from build123d import import_step
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.StlAPI import StlAPI_Writer
    with tempfile.TemporaryDirectory() as td:          # meshed as read back from STEP: the in-memory pebble shell
        g = pathlib.Path(td) / "v.step"                # meshes with open edges, its read-back (ShapeFix on import) not
        if read_back:                                  # already read back from STEP: a second round trip of the pebble's
            back = shape                               # test strip meshes with 20 open edges, the first with none
        else:
            export_step(shape, str(g))
            back = import_step(str(g))
        tried = []
        for k in VOL_MESH_K:                           # BRepMesh leaves a few open edges now and then: mesh again a bit
            from OCP.BRepTools import BRepTools        # finer; every retry is recorded (VOL_MESH_LOG, the report)
            BRepTools.Clean_s(back.wrapped)
            BRepMesh_IncrementalMesh(back.wrapped, VOL_MESH[0] * k, False, VOL_MESH[1] * k, True).Perform()
            f = pathlib.Path(td) / "v.stl"
            w = StlAPI_Writer()
            w.ASCIIMode = False
            check(w.Write(back.wrapped, str(f)), "volume mesh not written")
            mesh = pv.read(str(f)).clean()
            tried.append((k, mesh.n_open_edges))
            if mesh.n_open_edges == 0:
                break
    if len(tried) > 1:
        VOL_MESH_LOG.append(tried)
    check(mesh.n_open_edges == 0, f"volume mesh: open edges at every density tried {tried}")
    tri = mesh.faces.reshape(-1, 4)[:, 1:]
    v0, v1, v2 = (mesh.points[tri[:, i]].astype(float) for i in range(3))
    v6 = np.einsum("ij,ij->i", v0, np.cross(v1, v2))
    V = v6.sum() / 6
    c = (v6[:, None] * (v0 + v1 + v2)).sum(0) / (24 * V)
    check(V > 0, "volume mesh inside out")
    _VOL_CACHE[key] = (V, Vector(*c))
    return _VOL_CACHE[key]


def write_stl(shape, path, fresh=False, fine=False):
    """STL with an absolute deflection (build123d's export_stl meshes with a relative one). fresh: drop any triangulation
    the shape already carries first (the pebble's shell, meshed coarser on the way, came out with 981 open edges)."""
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.StlAPI import StlAPI_Writer
    if fresh:
        from OCP.BRepTools import BRepTools
        BRepTools.Clean_s(shape.wrapped)
    d, a = (STL_DEFLECTION / 2, STL_ANGLE / 2) if fine else (STL_DEFLECTION, STL_ANGLE)
    BRepMesh_IncrementalMesh(shape.wrapped, d, False, a, True).Perform()
    w = StlAPI_Writer()
    w.ASCIIMode = False
    check(w.Write(shape.wrapped, str(path)), f"STL not written: {path}")


def check_stl(shape, path, bodies=1, precise=False):
    """The written mesh: closed, `bodies` connected pieces, volume within STL_VOL_TOL of the solid's. Returns its info."""
    import pyvista as pv
    mesh = pv.read(str(path)).clean()
    n_open = mesh.n_open_edges
    n_bodies = int(mesh.connectivity().point_data["RegionId"].max()) + 1
    vol = abs(mesh.volume)
    v_solid = vol_props(shape, precise)[0]
    err = vol / v_solid - 1
    check(n_open == 0, f"{path.name}: {n_open} open edges")
    check(n_bodies == bodies, f"{path.name}: {n_bodies} separate bodies, expected {bodies}")
    check(abs(err) <= STL_VOL_TOL, f"{path.name}: mesh volume {vol:.1f} vs solid {v_solid:.1f} ({err * 100:+.2f} %)")
    return dict(kb=path.stat().st_size / 1024, tris=mesh.n_cells, err=err)


def write_step(shape, path, precise=False):
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
    v0, v1 = sum(vol_props(x, precise)[0] for x in shape.solids()), sum(vol_props(x, precise, True)[0] for x in back.solids())
    tol = STEP_VOL_TOL_MESH if precise else STEP_VOL_TOL
    check(abs(v1 / v0 - 1) <= tol, f"{path.name}: volume {v1:.2f} back, {v0:.2f} written")
    return dict(solids=n1, faces=len(back.faces()), err=v1 / v0 - 1, kb=path.stat().st_size / 1024)


def export_part(shape, out, name, report, bodies=1, precise=False):
    """A printed part: STEP + STL, both checked; their numbers go into `report`."""
    shape.label = name
    st = write_step(shape, out / f"{name}.step", precise)
    if precise:                  # the pebble: mesh the STEP as read back (checked above): meshing the in-memory shell left
        from build123d import import_step          # 981 open edges along its B-spline intersection edges, the
        back = import_step(str(out / f"{name}.step"))   # read-back (ShapeFix on import) none
        check(len(back.solids()) == 1 or len(back.solids()) == len(shape.solids()), f"{name}: STEP read back")
        write_stl(back, out / f"{name}.stl", fresh=True, fine=True)   # 0.01 / 0.1 rad meshed the pebble's shell with
                                                                        # a fold: +0.7 % volume, closed; 0.005 / 0.05: +0.03 %
    else:
        write_stl(shape, out / f"{name}.stl")
    report[name] = (st, check_stl(shape, out / f"{name}.stl", bodies, precise))




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
    shift = 0.0 if rods_after else m.insert_shift
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
    # the lid, straight up (world Z), swept as the prism of its largest outline (m.lid_sweep)
    lsweep = m.lid_sweep(drop)
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
    shift = 0.0 if rods_after else m.insert_shift
    first = [b for b in moving if not (rods_after and isinstance(b, Rod)) and not (order == "battery-after" and b.name == "battery")]
    sw = [(f"{b.name} up", b.solid(dt=shift, es0=drop, es1=Z_STOP)) for b in first]
    if not rods_after:
        sw += [(f"{b.name} forward", b.solid(et=shift)) for b in first]
    if order == "battery-after":
        sw += [(f"battery {mv}", s_) for mv, s_ in bat_sweeps(m, order, drop)[0]]
    return sw + [("adapter up", m.adapter().solid(es0=drop))]


def front_logo_check(m, shell, lid, order, skin_only=False):
    """Checks and numbers for the front logo: limits, the voids against every body and sweep, LED room measured against
    the shell as well as the hardware. Returns a dict for the report. On a tilted front (pebble) the logo's numbers are
    in the body frame: y -> t, z -> s (bf() turns a world solid into it)."""
    bf = lambda sh_: sh_.rotate(Axis.X, m.tilt) if m.tilt else sh_
    fl = m.front_logo()
    w, h, (z0, z1) = fl["w"], fl["h"], fl["z"]
    strip = hw.STRIP_PER_MM * w
    check(strip >= FRONT_LOGO_STRIP_MIN - 1e-9, f"front logo strips {strip:.2f}")
    check(z0 >= FRONT_LOGO_RIM - 1e-6 and z1 <= m.GLASS_S0 - FRONT_LOGO_GLASS + 1e-6, "front logo outside its band")
    check(z1 < m.SLOT_S[0] - 1.0, "front logo reaches the slots")
    void = fl["cut"] if fl["recess"] is None else fl["cut"] + fl["recess"]
    void = void & m.wt(box(-60, 60, -10, m.FRONT, -5, 60))     # what it removes: the front wall only (the cutters reach past it)
    if fl["recess"] is not None:
        rb = bf(fl["recess"]).bounding_box()
        check(rb.max.Z <= m.GLASS_S0 - 0.2, f"recess top {rb.max.Z:.2f} reaches the glass ({m.GLASS_S0:.2f})")
        check(rb.min.Z >= 1.0, f"recess bottom {rb.min.Z:.2f} reaches the rim")
    skin = (math.nan, math.nan)
    if fl["pocket"] is not None:                 # stencil pocket: inside the band, clear of the R5 edges, skin measured
        pw, ph = fl["pocket"]
        check(fl["zc"] + ph / 2 <= m.GLASS_S0 - 0.2, f"logo pocket top {fl['zc'] + ph / 2:.2f} reaches the glass ({m.GLASS_S0:.2f})")
        check(fl["zc"] - ph / 2 >= BOTTOM_BREAK + 1.0, f"logo pocket bottom {fl['zc'] - ph / 2:.2f} too close to the rim")
        check(pw / 2 <= getattr(m, "W", W) / 2 - R_EDGE - 1.0, "logo pocket reaches the R5 edges")
        sh_b = bf(shell)
        floor_f = [f for f in sh_b.faces() if f.geom_type == GeomType.PLANE and abs(abs(f.normal_at().Y) - 1) < 1e-6
                   and abs(f.center().Y - fl["floor"]) < 1e-6]
        check(len(floor_f) == 1, f"logo pocket floor: {len(floor_f)} faces")
        fb = floor_f[0].bounding_box()
        outer = [f for f in sh_b.faces() if f.bounding_box().min.Y < fl["floor"] - 1e-3     # faces reaching in front of the floor
                 and f.bounding_box().max.X > fb.min.X and f.bounding_box().min.X < fb.max.X
                 and f.bounding_box().max.Z > fb.min.Z and f.bounding_box().min.Z < fb.max.Z]
        d_min = dist_shapes(Compound(outer), floor_f[0])[0]
        d_ctr = fl["floor"] - m.front_out_t(0.0, fl["zc"])
        check(abs(d_min - m.logo_skin) < 0.01, f"logo skin measured {d_min:.3f}, want {m.logo_skin}")
        skin = (d_min, d_ctr)
    if skin_only:                                # (pebble round C: the skin alone)
        return dict(w=w, h=h, z=(z0, z1), skin=skin, zc=fl["zc"], floor=fl["floor"], pocket=fl["pocket"])
    seated = [(b.name, b.solid()) for b in m.moving_bodies()] + [("adapter", m.adapter().solid()), ("lid", lid)]
    sweeps = all_sweeps(m, order)
    for n, o in seated + sweeps:
        v = volume_common(void, o)
        check(v < EPS_V, f"front logo cut / recess overlaps the {n} ({v:.2f} mm3)")
    # LED room A: right behind the letters, between the inner face and the adapter, inside the rods' path
    ad = m.adapter().solid()
    ad_y0 = min(v.Y for v in bf(ad).vertices())
    rsx = m.tube_cc / 2 - hw.ROD_W / 2                  # the rods sweep up past the front wall from here outwards
    xa = min(w / 2, rsx - 0.3)
    zoneA = m.wt(box(-xa, xa, fl["inner_y"], ad_y0 - 0.3, z0, z1))
    vA = [(n, volume_common(zoneA, o)) for n, o in [("shell", shell)] + seated + sweeps]
    bad = [(n, v) for n, v in vA if v > EPS_V]
    check(not bad, f"LED room behind the logo overlaps: {bad}")
    gA = min((gap(zoneA, o), n) for n, o in [(n, o) for n, o in seated + sweeps])
    # free room beside the adapter at the letters' height: the cavity minus every body and sweep, |x| > adapter + 0.5
    beside = None
    for sx in (-1, 1):
        b_ = m.wt(box(sx * (hw.ADAPTER_W / 2 + 0.5), sx * 40, -10, 60, z0, z1)) & m.cavity()
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
    return dict(w=w, h=h, z=(z0, z1), strip=strip, recess=fl["recess"], inner_y=fl["inner_y"], ad_y0=ad_y0, skin=skin, rsx=rsx,
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
    check(skin_any >= m.logo_skin - 0.01, f"logo pocket: {skin_any:.3f} of material to the outside at {p_any}")
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
    yd = pl.y_dir                                        # world +Z on the upright fronts and the sides, up the face on the pebble
    zs = sorted((f.center() - o).dot(yd) for f in shell.faces() if f.geom_type == GeomType.PLANE
                and abs(abs(f.normal_at().dot(yd)) - 1) < 1e-6 and near_void(f))
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
    st_t = P.get("st_t", STENCIL_T)                       # the stencil's thickness (the pebble's: what its pocket leaves)
    st = stencil_block(pl, P["pw"], P["ph"], st_t)
    sw_, sh_ = P["pw"] - 2 * STENCIL_CLR + 2 * k * st_t, P["ph"] - STENCIL_CLR - STENCIL_CLR_TOP
    top = pl.offset(st_t) * Pos(0, (STENCIL_CLR - STENCIL_CLR_TOP) / 2) * RectangleRounded(sw_, sh_, STENCIL_R - STENCIL_CLR)
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
    slot_voids = [m.slot_cutter(sx * m.tube_cc / 2) & m.shell("body") for sx in (-1, 1)]     # what the slots take out
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


def meat_at(spots, shell_body, lid_blank, fast=False):
    """Wall round each magnet hole, measured on the rim section (z 0+, with the bottom break and the bosses) and on the
    lid's section at the hole's depth: [(shell meat, lid meat)]."""
    r_hole = (hw.MAG_D + hw.MAG_CLR_D) / 2
    z_lid = -(hw.MAG_H + hw.MAG_CLR_H)
    s_all, l_all = section_segments(shell_body, 1e-3, step=0.1, fast=fast), section_segments(lid_blank, z_lid, step=0.1, fast=fast)
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


# ---- pebble ("leaning pebble", track A2: the oval's look on the tilt15's 15 deg front) --------------------------------
# The user's pick D of concept round 1 (docs/desk-housing-oval-tilt-handoff.md, "Concept round 1"): Fable's section loft
# from concept/ovaltilt-sketch (concepts.pebble with PEB_P 2.7, PEB_N 2.8, PEB_BW 33, PEB_BZ 18): 66 W x 58 D x 110 H with
# the lid, front leaning back 15 deg, one convex back, an egg-shaped front outline widest 18 above the desk, a dome. The
# sketch has the desk at z 0 and the rim at its LID 3: here everything sits 3 lower; x and y are the same (y 0 where the
# face line meets the rim plane), so the body frame is Model's with TILT 15. Changes to the sketch's sections (measured
# against it in the report):
#   (1) over the slots (OVAL_Z) and |x| <= 17 the front is the oval's curve (W 56, D 36, n 2.8; 4.55 on the centre line,
#       3.0 where the 3 mm offset meets the flat inner face at the glass edge + 0.3) on a cylinder along the lean: no crown;
#       blended into the sketch's bow by |x| 20 (where that leaves the front chain concave by a few um, its lower hull);
#   (2) the bow fades in from the rim (the sketch: from 1 mm below it), so the lid carries none and its land is a prism;
#   (3) the plan exponent is RIM_DN higher at the rim, fading out over RIM_ZC: the plan's diagonals start at <= 45 deg
#       (sketch: 46.6 deg in the first 0.1 mm);
#   (4) the apex is closed by a flat TOP_CAP below the top.
# Outer surface and cavity are B-spline surfaces through dense horizontal sections (bspline_loft). The cavity is the
# shell's ball erosion (a true 3D inward offset of ERODE_R, computed on the convex sections' support functions), cut by the
# flat inner front face (t = FRONT, as the oval's), narrowed from the top down so its walls never overhang more than
# TENT_DEG (the tent under the dome), and closed by a flat ceiling (a bridge) at the lowest 0.5 step where that is at most
# BRIDGE_MAX deep. Magnets in bosses inside the rim as the oval's; USB through a closed USB-C slot at the back (round E;
# a rim notch as the tilt15's until round D).
PEBBLE = dict(P=2.7, N=2.8, BW=33.0, BZ=18.0,          # the user's pick D (2026-11-20): the sketch's knobs
              H=107.0,                                  # apex above the rim (110 with the lid)
              RIM_DN=0.1, RIM_ZC=3.0,                   # (3)
              OVAL_X=(17.0, 20.0),                      # (1): the oval's curve to |x| 17, blended into the sketch's by 20 ...
              OVAL_Z=(10.0, 14.0, 92.0, 95.0),          # ... with weight 0 -> 1 -> 1 -> 0 at these heights (slots: z 24..89;
                                                        # the glass's flat inner face z 16..91 must be as the oval's)
              K=48, STEP=0.4, TOP_CAP=0.03,             # points per plan quadrant; no point moves more than STEP between two
                                                        # sections of the loft
              ERODE_R=WALL_MIN + 0.02, DZ=0.05, M=720,  # cavity: erosion radius (+0.02: the lofts stray up to ~0.01 from
                                                        # their sections; 0.005 measured 2.994), z grid, plan directions
              TENT_DEG=43.0, BRIDGE_MAX=15.0, ZF_FROM=90.0,   # tent: 44 lofted to 45.02 under the dome
              CAV_N=192, CAV_LOW=-1.0,                  # cavity sections: points, lowest (below the rim, for the cut)
              MAG_DEPTH=2.3, MAG_PHI=(-60.0, 45.0), BOSS_R=1.85, BOSS_H=3.0,   # as the oval's
              LOGO_W=12.0, LOGO_W_MAX=14.0,             # A: 12; B: the largest that fits, up to 14 (front_logo_wz)
              STENCIL_MIN_T=1.2,                        # B: the stencil at least this thick (the 1.3 skin leaves less room)
              SEAT_D=2.0, LOGO_SEAT_D=3.5,              # the glass seat / logo seat reach this far behind the flat inner face
                                                        # (not 3.0: the pocket's run-on ends there, coincident faces)
              SEAT_TOP_DEG=60.0,                        # the glass seat's top end from the face's normal: 45 from vertical printed
              SEAT_WALL_MIN=1.9,                        # the seat's wall, at least (named exception to WALL_MIN)
              LIP_SHORT_DEG=3.0, LIP_ARC_N=400,         # slots C = A: the round lip ends this short of tangency, run out along its
                                                        # tangent (it crosses the face at that angle); chords per lip arc
              MESH_DEFL=0.005, MESH_ANG=0.05,           # the OCC shell's mesh before the slots are cut (chord error <= 0.02)
              CUT_THROUGH=1.0,                          # slot cutter mesh: how far behind the inner face it cuts through
              STRIP_T=12.0,                             # test strip: the shell in front of t 12
              USB_SLOT=(11.0, 5.5, 2.5))                # USB-C slot in the back wall: width, height, lower edge above the rim

# The pebble's board keeper (round D, user 2026-11-26; round E, 2026-11-27). The rods fix the board along x and s; nothing
# held it against the front wall (it hangs under the 15 deg lean). A printed fork slides up from the open bottom right
# behind the board's acrylic back plate and presses the plate through a pad over each of its 4 screws; 4 ribs on the
# shell's side walls back the fork behind the pads. The battery is off the board (Kapton to the back wall; not modelled).
# Body frame; s absolute, laid out for the PCB's bottom edge at PCB_S0.
# Round D had one prong, 3 pads and 3 ribs kept outside the board's edge (the model's back-shifted up move): printed, it
# held, but the prong twisted off its narrow upper rib. Round E (user): the board slides in along the front wall, also
# with its rods on, so the ribs reach over the board; the fork is a frame open on the plug side: a top bar across both
# upper screws, the button side's prong, a lower block across both lower screws.
# The plug side (UART, J5 and I2C open upwards, to the back; only RTC opens to the side): their plugs and wires stand
# behind the plate, in the column of that side's screws. The top bar passes over that column on its way up, so those
# sockets are empty while the fork goes in or out (user: plugged in afterwards, through the fork's open side). The bar
# cannot pass the adapter either. Assembly: board, fork, adapter, battery plug / upward plugs, lid.
KEEPER = dict(PCB_S0=16.8,
              BOARD_T=9.15,                             # glass front .. the back plate's back face: measured (user, 2026-11-26).
                                                        # hw.BOARD_T (9.0, all variants) still places the USB port and adapter
              PAD=5.0, PAD_H=1.5,                       # square pads centred on the plate's screws; the fork's face this far
                                                        # behind the plate
              PAD_OVER=0.7, PAD_LEAD=0.6,               # pads printed this much proud and sanded to fit; lead-in on their upper edge.
                                                        # 0.7 (user, 2026-11-27): the board goes in WITHOUT the 0.5 foam strips the
                                                        # model still has (hw.GASKET), so it sits 0.5 further forward: D's +0.2
                                                        # was "a little loose" bare and "perfectly tight" with tape on the glass
              FORK_T=2.5, RIB_T=3.5,
              SLOT_X=8.5,                               # centre slot's half width: the adapter (+-6), the plate's BAT window
              PRONG_X=21.0, TOP_S=95.3,                 # the button side's prong: its outer edge; the fork's top end (PCB top 95.65)
              HEAD_S0=80.0, BAR_S0=88.0,                # round E: above HEAD_S0 the prong widens to the wall; the top bar from BAR_S0
              HEAD_EDGE=((83.0, 24.0), (86.0, 23.95), (87.5, 23.6), (89.0, 23.15), (90.5, 22.7), (92.0, 22.2), (93.5, 21.65),
                         (95.3, 20.95)),                # (s, |x|) of the head's and the bar's outer edges: 0.5 inside the cavity
                                                        # wall at the fork's front depth (read off the C shell; the wall gap is checked)
              EAR_X=24.0, EAR_S1=30.0,                  # the two feet and the lower block across them, backed by the lower ribs;
                                                        # it ends here, below the lowest upward socket and the BAT window
              ADAPTER_CLR=0.3, LID_CLR=0.15,            # lower block above the adapter; the fork's foot above the lid
              LEAD=0.8,                                 # lead-in on the back edges that run under the ribs
              # ribs: inner edge |x|, s range; a 45 deg corbel below. Round E (user, 2026-11-27): the board slides in along the
              # front wall (no back-shifted up move), so the ribs reach over the board, behind the pads
              RIB_LO=(14.0, 24.8, 31.0),                # lower pair: as far in as 45 deg up from just above the rim allows
              RIB_HI=(11.0, 84.0, 96.0),                # upper, button side: over the whole pad (x 11.2..16.2)
              RIB_HI_PLUG=(13.0, 95.5, 96.0),           # upper, plug side: a wedge that leaves the RTC socket and its plug in view
              RIB_EMBED=1.0, RIB_STEP=0.5,              # ribs run this far into the wall; their wall side sampled at this step
              JST_Z={"uart": 22.45, "rtc": 67.5},       # sockets above the PCB bottom besides hw.PLUG_Z's (rtc: from a photo)
              RTC_LEN=4.4,                              # the 2-pin plug's length along the edge (hw.PLUG_LEN: the 4-pin ones)
              PLUG_IN=5.0, PLUG_UP=4.0,                 # upward sockets: their column reaches this far in from the PCB edge (the
                                                        # plate's cut-outs); plug + wire bend this far behind the plate. ASSUMED
              PATH_MIN=0.5)                             # the seated board, plugs and adapter to the ribs, at least


def _ss(g):
    return 0.0 if g <= 0 else 1.0 if g >= 1 else g * g * (3 - 2 * g)


def _lower_hull(q):
    """q: a front chain (x, y) of a section; replace y by its lower convex hull as a function of x. Returns the change."""
    o = np.argsort(q[:, 0], kind="stable")
    x, y = q[o, 0], q[o, 1]
    hx, hy = [], []
    for xi, yi in zip(x, y):
        while len(hx) >= 2 and (hx[-1] - hx[-2]) * (yi - hy[-2]) - (hy[-1] - hy[-2]) * (xi - hx[-2]) <= 0:
            hx.pop()
            hy.pop()
        hx.append(xi)
        hy.append(yi)
    yn = np.interp(x, hx, hy)
    d = float(np.max(np.abs(yn - y)))
    q[o, 1] = yn
    return d


def pebble_sketch():
    """The concept sketch's modules (geo, concepts) with the user's pick D set."""
    d = HERE / "concept" / "ovaltilt-sketch"
    if str(d) not in sys.path:
        sys.path.append(str(d))
    import geo, concepts
    check(pathlib.Path(geo.__file__).parent == d and pathlib.Path(concepts.__file__).parent == d,
          f"sketch modules from elsewhere: {geo.__file__}, {concepts.__file__}")
    concepts.PEB_P, concepts.PEB_N, concepts.PEB_BW, concepts.PEB_BZ = PEBBLE["P"], PEBBLE["N"], PEBBLE["BW"], PEBBLE["BZ"]
    return geo, concepts


class PebbleShape:
    """The pebble's outer surface as horizontal sections; z above the rim (the lid below 0)."""

    def __init__(self):
        geo, concepts = pebble_sketch()
        bodies, yt, _ = concepts.pebble()
        check(len(bodies) == 1 and yt == 0.0, "sketch: one pebble body with the face line at y 0")
        self.geo, self.cn, self.b = geo, concepts, bodies[0]
        self.ref = concepts.pebble()[0][0]                 # untouched, for the comparison
        self.H = self.b.z1 - geo.LID
        check(abs(self.H - PEBBLE["H"]) < 1e-9 and abs(self.b.z0) < 1e-9 and abs(geo.LID - LID_T) < 1e-9,
              f"sketch: apex {self.H}, desk {self.b.z0}, lid {geo.LID}")
        self.corr = 0.0                                    # largest change by the lower hull (1)

    def n_at(self, z):
        return PEBBLE["N"] + PEBBLE["RIM_DN"] * min(1.0, max(0.0, 1 - z / PEBBLE["RIM_ZC"])) ** 2

    def section(self, z, k=PEBBLE["K"]):
        """(4k, 2) points, counter-clockwise from the front apex (x 0): Fable's Body.section with the changes (1)-(3)."""
        g, b = self.geo, self.b
        zk = z + g.LID
        n = self.n_at(z)
        b.n = b.nb = n                                     # the sketch's nfront() falls back on b.n
        yf, yb, xl, xr = b.yf(zk), b.yb(zk), b.xl(zk), b.xr(zk)
        check(yb - yf > 0.2 and xr - xl > 0.2, f"pebble: no section at z {z}")
        yc = yf + b.cfrac * (yb - yf)
        xb = float(np.clip(b.xback(zk), xl + 0.1, xr - 0.1))
        th = np.linspace(0, np.pi / 2, k + 1)
        c, sn = np.cos(th), np.sin(th)
        # (2) the bow fades in from the rim to the face's start and out above it as the sketch's
        gb = min((zk - g.LID) / (b.face[0] - g.LID), (b.face[1] + g.BOW_FADE - zk) / g.BOW_FADE)
        w = _ss(gb) * _ss((yc - yf - g.BOW_H - 0.3) / 6.0)
        nr = n + w * _ss((xr - 17.5) / 6.0) * (b.nfront(xr, yc - yf) - n) if w else n
        nl = n + w * _ss((-xl - 17.5) / 6.0) * (b.nfront(-xl, yc - yf) - n) if w else n
        q1 = np.c_[xr * sn ** (2 / nr), yc - (yc - yf) * c ** (2 / nr)]
        q2 = np.c_[xb + (xr - xb) * c ** (2 / n), yc + (yb - yc) * sn ** (2 / n)]
        q3 = np.c_[xb + (xl - xb) * sn ** (2 / n), yc + (yb - yc) * c ** (2 / n)]
        q4 = np.c_[xl * c ** (2 / nl), yc - (yc - yf) * sn ** (2 / nl)]
        wz = _ss(gb)                                       # B: the oval's curve fades with the bow itself (no second blend:
                                                           # the A geometry's OVAL_Z fades left 0.02..0.035 dents)
        if wz > 0:                                         # (1)
            x2 = min(PEBBLE["OVAL_X"][1], xr - 3.0)       # near the dome the section narrows: blend inside it
            x1 = min(PEBBLE["OVAL_X"][0], x2 - 2.5)
            for q in (q1, q4):
                ax = np.abs(q[:, 0])
                wx = np.array([1 - _ss((v - x1) / (x2 - x1)) for v in ax])
                k_ = wx > 0
                q[k_, 1] += wz * wx[k_] * (yf + PEBBLE_BOW_K * oval_front_y(q[k_, 0]) / math.cos(math.radians(15)) - q[k_, 1])
                self.corr = max(self.corr, _lower_hull(q))
        return np.vstack([q1[:-1], q2[:-1], q3[:-1], q4[:-1]])

    def sketch_section(self, z, k=PEBBLE["K"]):
        return self.ref.section(z + self.geo.LID, k)

    def levels(self, z0, z1, step=PEBBLE["STEP"], dz_max=2.0):
        """Heights from z0 to z1 such that no section point moves more than `step` from one to the next."""
        zl, P0 = [z0], self.section(z0)
        z = z0
        while z < z1 - 1e-12:
            d = dz_max
            while True:
                zn = min(z + d, z1)
                P1 = self.section(zn)
                if np.linalg.norm(P1 - P0, axis=1).max() <= step or d < 1e-4:
                    break
                d /= 1.5
            zl.append(zn)
            z, P0 = zn, P1
        return zl


def convex_ccw(P, what):
    """A section must be convex and counter-clockwise (the erosion and the support functions rely on it)."""
    d = np.diff(np.r_[P, P[:1]], axis=0)
    L = np.hypot(d[:, 0], d[:, 1])
    check(L.min() > 1e-9, f"{what}: repeated points")
    t = d / L[:, None]
    cr = t[:, 0] * np.roll(t[:, 1], -1) - t[:, 1] * np.roll(t[:, 0], -1)
    check(cr.min() > -1e-9, f"{what}: not convex (turn {cr.min():.2e})")


# B-spline lofts through horizontal sections: u periodic (the sections' points, one parameter set for all), v through
# the sections' poles (one parameter set for all); planar caps at both ends; sewn into a solid
def _interp(P, params, periodic):
    from OCP.OCP.collections import HArray1_gp_Pnt, HArray1_double
    from OCP.GeomAPI import GeomAPI_Interpolate
    a = HArray1_gp_Pnt(1, len(P))
    for i, p in enumerate(P):
        a.SetValue(i + 1, gp_Pnt(*map(float, p)))
    pr = HArray1_double(1, len(params))
    for i, v in enumerate(params):
        pr.SetValue(i + 1, float(v))
    it = GeomAPI_Interpolate(a, pr, periodic, 1e-9)
    it.Perform()
    check(it.IsDone(), "spline interpolation failed")
    return it.Curve()


def _poles(c):
    return np.array([[c.Pole(i).X(), c.Pole(i).Y(), c.Pole(i).Z()] for i in range(1, c.NbPoles() + 1)])


def _knots(c):
    return [c.Knot(i) for i in range(1, c.NbKnots() + 1)], [c.Multiplicity(i) for i in range(1, c.NbKnots() + 1)]


def bspline_loft(secs, zs):
    """secs: (N, 2) arrays with corresponding points (counter-clockwise), at heights zs (rising). Returns the solid and its
    lateral B-spline surface."""
    from OCP.OCP.collections import Array2_gp_Pnt, Array1_double, Array1_int
    from OCP.Geom import Geom_BSplineSurface, Geom_Plane
    from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire,
                                    BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid)
    from OCP.TopoDS import TopoDS
    from OCP.ShapeFix import ShapeFix_Solid
    from build123d import Solid
    S = np.array(secs)
    K, N, _ = S.shape
    check(K >= 4 and np.all(np.diff(zs) > 0), "loft: sections")
    d = np.hypot(*np.diff(np.concatenate([S, S[:, :1]], 1), axis=1).transpose(2, 0, 1))
    cu = np.concatenate([np.zeros((K, 1)), np.cumsum(d, 1)], 1)
    u = (cu / cu[:, -1:]).mean(0)                                   # N + 1 values, 0 .. 1 (periodic)
    curves = [_interp(np.c_[S[k], np.full(N, zs[k])], u, True) for k in range(K)]
    uk, um = _knots(curves[0])
    check(all(np.allclose(_knots(c_)[0], uk) and _knots(c_)[1] == um for c_ in curves), "loft: section knots differ")
    Q = np.array([_poles(c_) for c_ in curves])
    dv = np.linalg.norm(np.diff(S, axis=0), axis=2).mean(1)
    check(dv.min() > 1e-6, "loft: two sections coincide")
    v = np.r_[0, np.cumsum(dv)]
    v /= v[-1]
    cols = [_interp(Q[:, j], v, False) for j in range(Q.shape[1])]
    vk, vm = _knots(cols[0])
    R_ = np.array([_poles(c_) for c_ in cols])
    P2 = Array2_gp_Pnt(1, R_.shape[0], 1, R_.shape[1])
    for i in range(R_.shape[0]):
        for j in range(R_.shape[1]):
            P2.SetValue(i + 1, j + 1, gp_Pnt(*R_[i, j]))

    def arr(vals, T):
        a = T(1, len(vals))
        for i, x in enumerate(vals):
            a.SetValue(i + 1, x)
        return a
    srf = Geom_BSplineSurface(P2, arr(uk, Array1_double), arr(vk, Array1_double), arr(um, Array1_int), arr(vm, Array1_int),
                              3, 3, True, False)
    sew = BRepBuilderAPI_Sewing(1e-6)
    sew.Add(BRepBuilderAPI_MakeFace(srf, 1e-7).Face())
    for vv, z in ((0.0, zs[0]), (1.0, zs[-1])):
        w = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(srf.VIso(vv)).Edge()).Wire()
        sew.Add(BRepBuilderAPI_MakeFace(Geom_Plane(gp_Pnt(0, 0, float(z)), gp_Dir(0, 0, 1)), w, True).Face())
    sew.Perform()
    so = BRepBuilderAPI_MakeSolid(TopoDS.Shell(sew.SewedShape())).Solid()
    fx = ShapeFix_Solid(so)
    fx.Perform()
    sol = Solid(fx.Solid())
    bb = sol.bounding_box()
    check(sol.is_valid and sol.volume > 0 and len(sol.faces()) == 3 and bb.min.Z > zs[0] - 1e-3 and bb.max.Z < zs[-1] + 1e-3
          and np.abs(S).max() + 1.0 > max(abs(bb.min.X), abs(bb.max.X), abs(bb.min.Y), abs(bb.max.Y)), "loft: not a valid closed solid")
    return sol, srf


def surface_samples(srf, nu=720, nv=1200):
    """Points and unit normals (pointing away from the sections' centres) on a loft's lateral surface: (nv, nu, 6)."""
    from OCP.gp import gp_Vec
    p, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
    u0, u1, v0, v1 = srf.Bounds()
    out = np.zeros((nv, nu, 6))
    for i, vv in enumerate(np.linspace(v0, v1, nv)):
        for j, uu in enumerate(np.linspace(u0, u1, nu, endpoint=False)):
            srf.D1(uu, vv, p, du, dv)
            out[i, j, :3] = (p.X(), p.Y(), p.Z())
            out[i, j, 3:] = np.cross((du.X(), du.Y(), du.Z()), (dv.X(), dv.Y(), dv.Z()))
        n = out[i, :, 3:]
        n /= np.linalg.norm(n, axis=1)[:, None]
        c = out[i, :, :2].mean(0)
        if (((out[i, :, :2] - c) * n[:, :2]).sum(1)).mean() < 0:
            out[i, :, 3:] = -n
    return out


def _dirs(M):
    ph = 2 * np.pi * np.arange(M) / M
    return np.c_[np.cos(ph), np.sin(ph)]


def _hrep_poly(g, U, guess=None):
    """Counter-clockwise vertices of {p : p . U_j <= g_j}; None if empty."""
    from scipy.spatial import HalfspaceIntersection, ConvexHull
    from scipy.optimize import linprog
    ip = guess if guess is not None and (U @ guess - g).max() < -1e-3 else None
    if ip is None:
        r = linprog(np.r_[0, 0, -1], A_ub=np.c_[U, np.ones(len(U))], b_ub=g, bounds=[(None, None)] * 2 + [(0, None)])
        if not r.success or r.x[2] < 1e-3:
            return None
        ip = r.x[:2]
    V = HalfspaceIntersection(np.c_[U, -g], ip).intersections
    return V[ConvexHull(V).vertices]


def _resample(P, n):
    """A convex counter-clockwise polygon, n points evenly along it from where it crosses x 0 at the front."""
    Q = np.r_[P, P[:1]]
    i = [j for j in range(len(P)) if Q[j, 0] < 0 <= Q[j + 1, 0] and Q[j, 1] + Q[j + 1, 1] < 2 * P[:, 1].mean()]
    check(len(i) == 1, "resample: front crossing of x 0")
    j = i[0]
    a, b = Q[j], Q[j + 1]
    s0 = np.array([0.0, a[1] + (b[1] - a[1]) * (0 - a[0]) / (b[0] - a[0])])
    R_ = np.r_[[s0], np.roll(P, -(j + 1), axis=0), [s0]]
    L = np.r_[0, np.cumsum(np.hypot(*np.diff(R_, axis=0).T))]
    t = np.linspace(0, L[-1], n, endpoint=False)
    return np.c_[np.interp(t, L, R_[:, 0]), np.interp(t, L, R_[:, 1])]


def pebble_cavity(m):
    """The cavity's sections for the loft (see the block comment) and what they imply: the flat ceiling's height and size,
    how much the tent takes, the board's up-move shift that clears the chin. Measured afterwards on the solids."""
    P_, shape = PEBBLE, m.shape
    DZ, R, M = P_["DZ"], P_["ERODE_R"], P_["M"]
    U = _dirs(M)
    check(M % 4 == 0 and abs(U[3 * M // 4, 1] + 1) < 1e-12, "plan directions: -y must be one of them")
    J = int(math.ceil(shape.H / DZ - 1e-9))            # outer sections at j DZ, j = 0 .. J - 1 (below the apex)
    HO = np.empty((J, M))
    for j in range(J):
        S = shape.section(j * DZ, 150)
        convex_ccw(S, f"outer section at z {j * DZ:.2f}")
        HO[j] = (S @ U.T).max(0)                       # chords lie inside the curve: the erosion errs on the safe side
    mR = int(R / DZ + 1e-9)
    ms = np.arange(-mR, mR + 1)
    rho = np.sqrt(np.maximum(R * R - (ms * DZ) ** 2, 0.0))
    j0, jtop = int(round(P_["CAV_LOW"] / DZ)), int((shape.H - R) / DZ) - 1
    jo = np.arange(j0, jtop + 1)
    zo = jo * DZ
    G = np.full((len(jo), M), np.inf)                  # the ball (radius R) inside the shell (z >= 0: open at the rim)
    for m_, r_ in zip(ms, rho):
        jj = jo + m_
        ok = jj >= 0
        G[ok] = np.minimum(G[ok], HO[jj[ok]] - r_)
    yplane = lambda z: (m.FRONT + z * m.sn) / m.c      # the flat inner face in the plan at z (y >= this)

    def with_plane(g, z):
        g = g.copy()
        g[3 * M // 4] = min(g[3 * M // 4], -yplane(z))
        return g
    # the flat ceiling: the lowest 0.5 step whose section (behind the flat face) is at most BRIDGE_MAX across
    zf, top = None, None
    for zf_ in np.arange(P_["ZF_FROM"], zo[-1], 0.5):
        Pt = _hrep_poly(with_plane(G[int(round((zf_ - zo[0]) / DZ))], zf_), U)
        dims = (np.ptp(Pt[:, 0]), np.ptp(Pt[:, 1]))
        if min(dims) <= P_["BRIDGE_MAX"]:
            zf, top = float(zf_), dims
            break
    check(zf is not None, "pebble: no ceiling height with a short enough bridge")
    i_f = int(round((zf - zo[0]) / DZ))
    rate = math.tan(math.radians(P_["TENT_DEG"])) * DZ
    raw, prev, guess, cut = {}, None, None, (0.0, None)
    for i in range(i_f, -1, -1):
        g = G[i] if prev is None else np.minimum(G[i], prev + rate)
        P = _hrep_poly(g, U, guess)
        check(P is not None, f"pebble cavity empty at z {zo[i]:.2f}")
        h = (P @ U.T).max(0)
        if prev is not None and (prev + rate < G[i] - 1e-9).any():
            he = (_hrep_poly(G[i], U, guess) @ U.T).max(0)
            if (he - h).max() > cut[0]:
                cut = (float((he - h).max()), float(zo[i]))
        raw[i], prev, guess = P, h, P.mean(0)
    # the chin: rods on their up move (thickest tape, furthest forward) against the cavity's front, flat face included
    r = hw.ROD_W / 2
    need = (-math.inf, None)
    for i in range(int(round(-zo[0] / DZ)), int(round((15.0 - zo[0]) / DZ))):
        z = zo[i]
        P = _hrep_poly(with_plane(G[i], z), U)
        fr = P[P[:, 1] < P[:, 1].mean()]
        fr = fr[np.argsort(fr[:, 0])]
        for sx in (-1, 1):
            xs = sx * m.tube_cc / 2 + np.linspace(-r, r, 81)
            tc = np.interp(xs, fr[:, 0], fr[:, 1]) * m.c - z * m.sn
            tr = m.GLASS_T0 - hw.TAPE[1] - np.sqrt(np.maximum(r * r - (xs - sx * m.tube_cc / 2) ** 2, 0))
            k = int(np.argmax(tc - tr))
            if tc[k] - tr[k] > need[0]:
                need = (float(tc[k] - tr[k]), (float(xs[k]), float(z), float(tc[k])))
    shift = max(INSERT_SHIFT, math.ceil((need[0] + INSERT_CLR) * 10 - 1e-6) / 10)
    # where the flat inner face begins on the centre line (the eroded front passes behind it)
    flat0 = None
    for i in range(int(round(-zo[0] / DZ)), i_f):
        P = _hrep_poly(G[i], U)
        fr = P[P[:, 1] < P[:, 1].mean()]
        fr = fr[np.argsort(fr[:, 0])]
        if np.interp(0.0, fr[:, 0], fr[:, 1]) <= yplane(zo[i]):
            flat0 = float(zo[i])
            break
    # loft levels: from CAV_LOW to the ceiling, no resampled point moving more than STEP between two
    res = {}

    def rs(i):
        if i not in res:
            res[i] = _resample(raw[i], P_["CAV_N"])
        return res[i]
    i0 = int(round(-zo[0] / DZ))                       # the rim: a level of its own (the cavity's narrowest, a waist)
    levels, i = list(range(0, i0, int(round(0.25 / DZ)))) + [i0], i0
    while i < i_f:
        nxt = i + 1
        dz_max = 0.25 if zo[i] < 4.0 else 2.0             # the rim: a waist, then the flare (2.996 with 1 mm steps)
        for k in range(i + 1, min(i_f, i + int(round(dz_max / DZ))) + 1):
            if np.linalg.norm(rs(k) - rs(i), axis=1).max() > P_["STEP"]:
                break
            nxt = k
        levels.append(nxt)
        i = nxt
    return dict(zs=[float(zo[i]) for i in levels], secs=[rs(i) for i in levels], zf=zf, top=top, tent_cut=cut,
                need=need, shift=shift, flat0=flat0, raw=raw, zo=zo, U=U, G=G)


# Front "A" (user, 2026-11-21, after the WIP print: front too thick, rods sat 0.4..0.6 under the face; 45 deg bevels and
# the bridge's nose too geometric): the outer face keeps the oval's curve; the flat inner face comes forward to WALL_MIN
# at the A slot centres (3.39 on the centre line, the oval's rule gave 4.55; kept in round B). Round B (2026-11-23): tubes
# c-c 18, slots from concept/ovaltilt-sketch/slot_ends.py N1; round C (2026-11-24): A's openings again, re-solved for
# c-c 18, flat ends (PebbleModel.lip / slot_surface / slot_cutter_mesh). Over the
# glass the inner face stays flat out to the glass + 0.3 (the glass seat, PebbleModel.seat()): the wall there thins to
# ~2.0 at the glass's edge, a named exception like the land, measured and reported.
PEBBLE_BOW_K = 1.0
PEBBLE_FRONT = math.ceil((WALL_MIN + oval_front_y(hw.TUBE_CC / 2)) * 1000 - 1e-6) / 1000


VARIANTS["pebble"] = dict(TILT=15.0, ADAPTER_FLOOR=1.0, TOTAL_MIN=0.0, LOGO_W=PEBBLE["LOGO_W"], LOGO_MODE="front", LOGO_ZC=None,
                          USB="notch", BAT_LOW=True, FRONT=PEBBLE_FRONT)


class PebbleModel(Model):
    """Model's body frame (TILT 15) and hardware stack (as tilt15: ADAPTER_FLOOR 1, battery low, the oval's 4.55 front)."""
    logo_recess = False                         # the stencil pocket holds the inlay recess entirely: none
    tube_cc = 18.0                              # B (user, 2026-11-23): tubes 18 apart (the firmware moves its columns)
    logo_skin = 1.3                             # B: hides the pocket's outline (a subtler glow, user)
    fast_sections = True                        # section_segments sampled in C++ (long B-spline section edges)

    def __init__(self):
        super().__init__("pebble", 58.0)
        self.BOARD_T1 = self.GLASS_T0 + KEEPER["BOARD_T"]   # the plate's back face as measured (the port's depth stays hw's)
        self.shape = PebbleShape()
        self.H = PEBBLE["H"]
        self._cache = {}
        self.CAV = pebble_cavity(self)
        self.insert_shift = self.CAV["shift"]
        bb = self.shell_env().bounding_box()
        self.W, self.D = bb.size.X, bb.max.Y

    # ---- outer form ----
    def shell_env(self):
        if "env" not in self._cache:
            zl = self.shape.levels(0.0, self.H - PEBBLE["TOP_CAP"])
            secs = [self.shape.section(z) for z in zl]
            for z, S in zip(zl, secs):
                convex_ccw(S, f"outer section at z {z:.3f}")
            self._cache["env"], self._cache["env_srf"] = bspline_loft(secs, zl)
            self._cache["env_levels"] = zl
        return self._cache["env"]

    def lid_env(self):
        """The lid: the underside's round (its first 45 deg, Fable's R7.5) lofted from the foot up to the land, then the
        land straight up to the rim (its sections are equal)."""
        if "lid_env" not in self._cache:
            z_land = -LID_T + self.shape.cn.RU * (1 - math.cos(math.radians(45)))
            check(np.abs(self.shape.section(z_land) - self.shape.section(0.0)).max() < 1e-9, "pebble: the lid's land is not a prism")
            zl = self.shape.levels(-LID_T, z_land)
            arc, self._cache["lid_srf"] = bspline_loft([self.shape.section(z) for z in zl], zl)
            top = [f for f in arc.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z > 1 - 1e-6]
            check(len(top) == 1, "pebble lid: top of the round")
            lid = (arc + extrude(top[0], -z_land)).clean()
            check(lid.is_valid and len(lid.solids()) == 1 and abs(lid.bounding_box().max.Z) < 1e-6, "pebble lid invalid")
            self._cache["lid_env"], self._cache["z_land"], self._cache["lid_levels"] = lid, z_land, zl
        return self._cache["lid_env"]

    def lid_blank(self):
        return self.lid_env()                    # its edge is the round: no break

    def lid_sweep(self, drop):
        """The lid straight up: the prism of its largest outline (the land) from far below to the rim."""
        top = [f for f in self.lid_env().faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z > 1 - 1e-6 and abs(f.center().Z) < 1e-6]
        check(len(top) == 1, "pebble lid: top face")
        return Pos(0, 0, -drop) * extrude(Face(top[0].outer_wire()), drop)

    def front_out_t(self, x, s):
        """Body frame: t of the outer front surface at (x, s): the line along t there meets the envelope's B-spline
        surface (exact; plane sections of the envelope come back incomplete at some heights)."""
        from OCP.GeomAPI import GeomAPI_IntCS
        from OCP.Geom import Geom_Line
        from OCP.gp import gp_Lin
        self.shell_env()
        y0, z0 = self.to_world(-5.0, s)
        it = GeomAPI_IntCS(Geom_Line(gp_Lin(gp_Pnt(float(x), y0, z0), gp_Dir(0, self.c, -self.sn))), self._cache["env_srf"])
        check(it.IsDone() and it.NbPoints() > 0, f"pebble: no front at x {x:.2f}, s {s:.2f}")
        ts = [self.to_body(it.Point(i).Y(), it.Point(i).Z())[0] for i in range(1, it.NbPoints() + 1)]
        return min(ts)

    def logo_floor_t(self, pw, ph, zc):
        """The floor (less logo_skin) so that the outer front's nearest point to the floor's real outline (R STENCIL_R
        corners), in 3D, is logo_skin away: over the outline and logo_skin round it, outer points (x, g, s) at an in-plane
        distance dp from the outline need the floor at g + sqrt(skin^2 - dp^2) or deeper (the front curves and tilts
        towards the floor beyond the outline's edge). A 0.25 grid, refined at 0.02 round the five worst points."""
        key = ("logo_floor", round(pw, 6), round(ph, 6), round(zc, 6))
        if key in self._cache:
            return self._cache[key]
        from scipy.interpolate import RectBivariateSpline
        r, sk = STENCIL_R, self.logo_skin
        def dp(x, s_):
            qx, qs = np.abs(x) - (pw / 2 - r), np.abs(s_ - zc) - (ph / 2 - r)
            return np.maximum(np.hypot(np.maximum(qx, 0.0), np.maximum(qs, 0.0)) - r, 0.0)
        # the front sampled exactly every 0.5 (IntCS is slow), bicubic in between; the worst point then exactly
        gx = np.arange(-pw / 2 - sk - 0.5, pw / 2 + sk + 0.5 + 1e-9, 0.5)
        gs = np.arange(zc - ph / 2 - sk - 0.5, zc + ph / 2 + sk + 0.5 + 1e-9, 0.5)
        G = RectBivariateSpline(gx, gs, np.array([[self.front_out_t(x, s_) for s_ in gs] for x in gx]))
        X, S_ = np.meshgrid(np.arange(-pw / 2 - sk, pw / 2 + sk + 1e-9, 0.01), np.arange(zc - ph / 2 - sk, zc + ph / 2 + sk + 1e-9, 0.01))
        D = dp(X, S_)
        N = np.where(D < sk, G.ev(X, S_) + np.sqrt(np.clip(sk * sk - D * D, 0, None)), -np.inf)
        i = np.unravel_index(np.argmax(N), N.shape)
        xb, sb = float(X[i]), float(S_[i])
        best = -math.inf
        for x in np.arange(xb - 0.05, xb + 0.05 + 1e-9, 0.01):
            for s_ in np.arange(sb - 0.05, sb + 0.05 + 1e-9, 0.01):
                d_ = float(dp(x, s_))
                if d_ < sk:
                    best = max(best, self.front_out_t(x, s_) + math.sqrt(sk * sk - d_ * d_))
        check(abs(best - float(N[i])) < 2e-3, f"pebble logo floor: the front's interpolation is off by {best - float(N[i]):.4f}")
        self._cache[key] = best - sk
        return self._cache[key]

    def front_logo_wz(self):
        """B (user, 2026-11-23): the largest letters (0.5 steps, <= LOGO_W_MAX) whose pocket fits between FRONT_LOGO_RIM
        above the rim and 0.2 below the glass (top-aligned there, mostly on the straight face) with a stencil at least
        STENCIL_MIN_T thick in front of LOGO_SKIN (the pebble's 1.3)."""
        if "logo_wz" not in self._cache:
            for w in np.arange(PEBBLE["LOGO_W_MAX"], 5.9, -0.5):
                h = hw.LETTERS_ASPECT * w
                pw, ph = w + 2 * STENCIL_MARGIN, h + 2 * STENCIL_MARGIN
                zc = self.GLASS_S0 - 0.2 - ph / 2
                if zc - h / 2 < FRONT_LOGO_RIM or hw.STRIP_PER_MM * w < FRONT_LOGO_STRIP_MIN:
                    continue
                st_t = self.FRONT - (self.logo_skin + self.logo_floor_t(pw, ph, zc)) - STENCIL_BACK
                if st_t >= PEBBLE["STENCIL_MIN_T"]:
                    self._cache["logo_wz"] = (float(w), zc)
                    break
            check("logo_wz" in self._cache, "pebble: no logo fits")
        return self._cache["logo_wz"]

    land_tol = 3e-5                             # the lips leave the land tangentially: 0.002 would read ~0.7 deep

    def pocket(self):
        """Model's glow-through pocket (flanks LOGO_FLARE_DEG at the sides, top and bottom straight), behind the pebble's
        thicker skin; its stencil as thick as the pocket leaves (STENCIL_BACK inside the mouth)."""
        P = Model.pocket(self)
        if "st_t" not in P:
            P["st_t"] = self.FRONT - P["floor"] - STENCIL_BACK
            check(P["st_t"] >= PEBBLE["STENCIL_MIN_T"] - 1e-9, f"pebble stencil only {P['st_t']:.2f} thick")
            P["mouth_x"], P["mouth_s"] = P["mouth"][0] / 2, (P["zc"] - P["ph"] / 2, P["zc"] + P["ph"] / 2)
        return P

    # ---- slots "C" (user, 2026-11-24): A's openings as printed, re-solved for c-c 18; flat ends; no horn fix (the relief
    # is to hide the horns, as on the WIP) ----
    def lip(self, xc, sg):
        """Round A's lip on side sg of the slot at xc (sg = +1: its +x side), body frame: an arc that starts vertical at the
        land's top (t = L) and turns until it would meet the bowed face tangentially, its radius solved for that side.
        Returns (r, phi*)."""
        L = self.FRONT - self.RIM
        half = SLOT_W / 2
        F = lambda u: PEBBLE_BOW_K * float(oval_front_y(xc + sg * u))
        dF = lambda u: (F(u + 1e-6) - F(u - 1e-6)) / 2e-6
        r, ph = 2.0, math.pi / 2
        for _ in range(500):
            u = half + r * (1 - math.cos(ph))
            ph = math.pi / 2 + math.atan(dF(u))
            r_new = (L - F(u)) / math.sin(ph)
            if abs(r_new - r) < 1e-12:
                break
            r = 0.5 * (r + r_new)
        u = half + r * (1 - math.cos(ph))
        check(abs(L - r * math.sin(ph) - F(u)) < 1e-9 and abs(-1 / math.tan(ph) - dF(u)) < 1e-6 and r > 0.3,
              f"lip at x {xc:+.2f}, side {sg:+d}: no tangent arc (r {r:.3f})")
        return r, ph

    def slot_params(self):
        """The slots' design numbers: centres, land, A's lips per side (inner: towards x 0), each ended LIP_SHORT_DEG
        short of tangency and run out along its tangent; their widths on the face; ends flat (ae 0)."""
        if "slotp" not in self._cache:
            f = lambda x: PEBBLE_BOW_K * oval_front_y(np.asarray(x, float))
            xc, half = self.tube_cc / 2, SLOT_W / 2
            L, T = self.FRONT - self.RIM, self.FRONT
            lips = {}
            for side, sg in (("in", -1), ("out", 1)):
                r, ph = self.lip(xc, sg)
                pe = ph - math.radians(PEBBLE["LIP_SHORT_DEG"])
                dxe = r * (1 - math.cos(pe))
                # where the run-out crosses the face: its width on the face
                g = lambda d: (L - r * math.sin(pe) - (d - dxe) / math.tan(pe)) - float(f(xc + sg * (half + d)))
                lo, hi = dxe, dxe + 2.0
                check(g(lo) > 0 > g(hi), f"lip {side}: its run-out does not cross the face")
                for _ in range(100):
                    mid = 0.5 * (lo + hi); lo, hi = (mid, hi) if g(mid) > 0 else (lo, mid)
                lips[side] = dict(r=r, ph=ph, pe=pe, dxe=dxe, w=0.5 * (lo + hi))
            self._cache["slotp"] = dict(f=f, xc=xc, half=half, L=L, T=T, lips=lips, a_in=lips["in"]["w"],
                                        a_out=lips["out"]["w"], ae=0.0)
        return self._cache["slotp"]

    def slot_surface(self, x, s, half=None, only=None):
        """The material's surface t over (x, s), body frame (A's lips, flat ends); through the slots: FRONT."""
        P = self.slot_params()
        f, L, T = P["f"], P["L"], P["T"]
        S0, S1 = self.SLOT_S
        x, s = np.broadcast_arrays(np.asarray(x, float), np.asarray(s, float))
        fx = f(x)
        u = np.abs(x) - P["xc"]                             # both slots from |x|: mirror-exact
        dx = np.abs(u) - P["half"]
        lip = np.full_like(fx, -np.inf)
        for side, sgn in (("in", u < 0), ("out", u >= 0)):
            q = P["lips"][side]
            d = np.clip(dx, 0, None)
            with np.errstate(invalid="ignore"):
                arc = L - q["r"] * np.sin(np.arccos(np.clip(1 - d / q["r"], -1, 1)))
            run = (L - q["r"] * math.sin(q["pe"])) - (d - q["dxe"]) / math.tan(q["pe"])
            lip = np.where(sgn, np.where(d <= q["dxe"], arc, run), lip)
        ins = (s > S0) & (s < S1)
        p = np.where(ins, np.where(dx < 0, T, lip), -np.inf)
        return np.maximum(p, fx)

    def slot_cutter(self, x):
        """OCC proxy of a slot's cut (its bounding box: the through-slot and lips) for distance checks only (the logo
        pocket to the slots); the shell's slots are cut on the mesh (slot_cutter_mesh, manifold3d)."""
        P = self.slot_params()
        sx = 1 if x > 0 else -1
        S0, S1 = self.SLOT_S
        x0, x1 = sx * P["xc"] - sx * (P["half"] + P["a_in"]), sx * P["xc"] + sx * (P["half"] + P["a_out"])
        return self.wt(box(min(x0, x1), max(x0, x1), -1, P["T"] + 1, S0, S1))

    def slot_cutter_mesh(self):
        """Both slots as one closed mesh (world frame; manifold3d): round A's cutter profile (body frame (x, t): the
        through-slot from CUT_THROUGH behind the inner face to the land's top, each lip's arc in LIP_ARC_N chords, its
        tangent run-out 1.5 long, then 4 in front of the face) extruded exactly S0..S1 (flat ends, true planes); the right
        slot's, mirrored for the left one."""
        if "slotmesh" in self._cache:
            return self._cache["slotmesh"]
        import manifold3d as m3
        P = self.slot_params()
        xc, half, L, T = P["xc"], P["half"], P["L"], P["T"]
        S0, S1 = self.SLOT_S
        side = {}
        for nm, sg in (("in", -1), ("out", 1)):
            q = P["lips"][nm]
            th = np.linspace(0.0, q["pe"], PEBBLE["LIP_ARC_N"] + 1)
            arc = np.c_[xc + sg * (half + q["r"] * (1 - np.cos(th))), L - q["r"] * np.sin(th)]
            d = np.array([sg * math.sin(q["pe"]), -math.cos(q["pe"])])
            P2 = arc[-1] + 1.5 * d
            check(P2[1] < float(P["f"](P2[0])) - 0.01, f"slot lip {nm}: its run-out stays behind the face")
            side[nm] = np.r_[arc, [P2, [P2[0], -4.0]]]
        top = T + PEBBLE["CUT_THROUGH"]
        poly = np.r_[[[xc - half, top]], side["in"], side["out"][::-1], [[xc + half, top]]]
        area = 0.5 * np.sum(poly[:, 0] * np.roll(poly[:, 1], -1) - np.roll(poly[:, 0], -1) * poly[:, 1])
        if area < 0:
            poly = poly[::-1]
        cs = m3.CrossSection([poly.tolist()])
        check(cs.num_contour() == 1 and abs(cs.area() - abs(area)) < 1e-6 * abs(area), f"slot cutter profile: {cs.num_contour()} contours, area {cs.area():.6f} vs {abs(area):.6f}")
        R = m3.Manifold.extrude(cs, S1 - S0)              # (x, t, s - S0)
        Mx = [[1, 0, 0, 0], [0, self.c, self.sn, S0 * self.sn], [0, -self.sn, self.c, S0 * self.c]]
        R = R.transform(Mx)
        M = R + R.mirror((1, 0, 0))
        check(M.status() == m3.Error.NoError and not M.is_empty() and len(M.decompose()) == 2, f"slot cutter mesh: {M.status()}")
        self._cache["slotmesh"] = M
        self._cache["slotmesh_n"] = len(poly)
        return M

    def seat(self):
        """The flat inner face where the cavity's 3 mm offset lies behind it (body frame, added to the cavity): over the
        glass, |x| <= glass + 0.3, from 0.5 below it to GLASS_SEAT above it, SEAT_D deep, its top end rising SEAT_TOP_DEG
        from the face's normal (a ceiling at 45 deg from vertical when printed); under the glass round the logo pocket's
        mouth (+ 0.5), LOGO_SEAT_D deep."""
        if "seat" not in self._cache:
            F, gx = self.FRONT, hw.GLASS_W / 2 + 0.3
            s_a, s_b = self.GLASS_S0 - 0.5, self.GLASS_TOP + GLASS_SEAT
            d = PEBBLE["SEAT_D"]
            k = math.tan(math.radians(PEBBLE["SEAT_TOP_DEG"]))
            prof = Polygon((F, s_a), (F + d, s_a), (F + d, s_b + d * k), (F, s_b), align=None)   # (t, s)
            glass = extrude(Plane.YZ * prof, gx, both=True)
            P = self.pocket()
            mx, (s_m0, s_m1) = P["mouth_x"], P["mouth_s"]
            logo = box(-mx - 0.5, mx + 0.5, F, F + PEBBLE["LOGO_SEAT_D"], s_m0 - 0.5, s_a + 0.01)
            seat = (glass + logo).clean()
            check(seat.is_valid and len(seat.solids()) == 1, "pebble seat invalid")
            self._cache["seat"] = self.wt(seat)
            self._cache["seat_dims"] = dict(gx=gx, s=(s_a, s_b), lx=mx + 0.5, ls=s_m0 - 0.5)
        return self._cache["seat"]

    # ---- cavity ----
    def cavity(self, seat=True):
        """The 3 mm offset behind the flat inner face (seat False: what WALL_MIN is measured on), plus the seat."""
        if "cav0" not in self._cache:
            loft, self._cache["cav_srf"] = bspline_loft(self.CAV["secs"], self.CAV["zs"])
            cav = loft & self.wt(box(-100, 100, self.FRONT, self.FRONT + 300, -100, 300))
            check(cav.is_valid and len(cav.solids()) == 1, "pebble cavity invalid")
            self._cache["cav0"] = cav
        if not seat:
            return self._cache["cav0"]
        if "cav" not in self._cache:
            cav = (self._cache["cav0"] + self.seat()).clean()
            check(cav.is_valid and len(cav.solids()) == 1, "pebble cavity + seat invalid")
            self._cache["cav"] = cav
        return self._cache["cav"]

    # ---- magnets, USB ----
    def magnet_spots(self):
        """[(x, y)] of the four magnet axes (as the oval's): MAG_DEPTH inside the rim's outline along its normal at MAG_PHI."""
        P = self.shape.section(0.0, 150)
        d = np.roll(P, -1, axis=0) - np.roll(P, 1, axis=0)
        nrm = np.c_[d[:, 1], -d[:, 0]]
        nrm /= np.linalg.norm(nrm, axis=1)[:, None]
        a = np.degrees(np.arctan2(nrm[:, 1], nrm[:, 0]))
        out = []
        for phi in PEBBLE["MAG_PHI"]:
            for sx in (1, -1):
                ph = phi if sx > 0 else 180 - phi
                i = int(np.argmin(np.abs((a - ph + 180) % 360 - 180)))
                out.append((round(float(P[i, 0] - PEBBLE["MAG_DEPTH"] * nrm[i, 0]), 3),
                            round(float(P[i, 1] - PEBBLE["MAG_DEPTH"] * nrm[i, 1]), 3)))
        return out

    def bosses(self):
        b = None
        for x, y in self.magnet_spots():
            c = Pos(x, y, 0) * Cylinder(PEBBLE["BOSS_R"], PEBBLE["BOSS_H"], align=(Align.CENTER, Align.CENTER, Align.MIN))
            b = c if b is None else b + c
        return b & self.shell_env()

    def usb_cutter(self):
        """USB-C slot (round E, user 2026-11-27; rounds A..D had tilt15's cable notch, open at the rim): the socket end of a
        short bendable extension sits in it. USB_SLOT's W x H, round-ended, level through the back wall at x 0, closed
        all round, its lower edge USB_SLOT's z0 above the rim. Tight on purpose (the user sands it to fit)."""
        w, h, z0 = PEBBLE["USB_SLOT"]
        check(z0 >= 2.5 and w > h, f"pebble USB slot: {z0} above the rim, {w} x {h}")
        r, zc, a = h / 2, z0 + h / 2, (w - h) / 2
        y0 = self.CAV["raw"][int(round(-self.CAV["zo"][0] / PEBBLE["DZ"]))][:, 1].max() - 2.0    # inside the rim's back
        y1 = self.D + 2.0
        n = box(-a, a, y0, y1, z0, z0 + h)
        for sx in (-1, 1):
            n = n + Pos(sx * a, y0, zc) * Cylinder(r, y1 - y0, rotation=(-90, 0, 0), align=(Align.CENTER, Align.CENTER, Align.MIN))
        return n

    def shell(self, level="full", magnets=None):
        key = ("shell", level)
        if key in self._cache:
            return self._cache[key]
        s = self.shell_env() - self.cavity()
        s = s + self.bosses()
        if level != "body":                     # (the slots: on the mesh, slot_cutter_mesh)
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

    # ---- board keeper (rounds D, E) ----
    def moving_bodies(self):
        """Model's, with this board's plugs instead of hw's side plugs: UART, J5 and I2C stand behind the plate (upward
        sockets, in the plate's cut-outs), RTC goes in from the side."""
        K, q = KEEPER, self.keeper()
        m = [b for b in Model.moving_bodies(self) if not b.name.startswith("plug")]
        e = q["plug_sx"] * hw.PCB_W / 2
        for n, (s, ln) in q["plugs"].items():
            if n == "rtc":
                m.append(Body(self, f"plug-{n}", (e, e + q["plug_sx"] * hw.PLUG_PROUD, self.GLASS_T1, self.BOARD_T1, s - ln / 2, s + ln / 2)))
            else:
                m.append(Body(self, f"plug-{n}", (e - q["plug_sx"] * K["PLUG_IN"], e, self.BOARD_T1, self.BOARD_T1 + K["PLUG_UP"],
                                                   s - ln / 2, s + ln / 2)))
        return m

    def keeper(self):
        """The keeper's derived numbers (body frame): depths, the screws' s, the sockets, the pads, the ribs."""
        if "keeper" not in self._cache:
            K = KEEPER
            check(abs(self.PCB_S0 - K["PCB_S0"]) < 1e-6, f"keeper laid out for the PCB bottom at s {K['PCB_S0']}, it is at {self.PCB_S0}")
            ft = (self.BOARD_T1 + K["PAD_H"], self.BOARD_T1 + K["PAD_H"] + K["FORK_T"])
            psx = -hw.BTN_SIDE
            plugs = {n: (self.PCB_S0 + z, K["RTC_LEN"] if n == "rtc" else hw.PLUG_LEN) for n, z in {**hw.PLUG_Z, **K["JST_Z"]}.items()}
            screws = (self.PCB_S0 + hw.NUT_INSET, self.PCB_S0 + hw.NUT_INSET + hw.NUT_DZ)
            pads = [(sx, s_) for s_ in screws for sx in (psx, -psx)]                 # (side, s): over all four screws
            low = min(s - ln / 2 for n, (s, ln) in plugs.items() if n != "rtc")
            check(K["EAR_S1"] < low - 2.0, f"keeper: the lower block (to s {K['EAR_S1']}) reaches the lowest upward socket ({low:.2f})")
            top = max(s + ln / 2 for n, (s, ln) in plugs.items() if n != "rtc")
            check(K["BAR_S0"] > top + 2.0, f"keeper: the top bar (from s {K['BAR_S0']}) reaches the highest upward socket ({top:.2f})")
            E = K["HEAD_EDGE"]
            check(abs(E[0][0] - (K["HEAD_S0"] + E[0][1] - K["PRONG_X"])) < 1e-9 and abs(E[-1][0] - K["TOP_S"]) < 1e-9 and E[0][1] <= K["EAR_X"]
                  and all(a[0] < b[0] and a[1] >= b[1] for a, b in zip(E, E[1:])), "keeper: HEAD_EDGE")
            ribs = [(-psx, *K["RIB_HI"]), (psx, *K["RIB_HI_PLUG"]), (1, *K["RIB_LO"]), (-1, *K["RIB_LO"])]
            self._cache["keeper"] = dict(fork_t=ft, rib_t=(ft[1], ft[1] + K["RIB_T"]), plug_sx=psx, plugs=plugs, screws=screws,
                                         pads=pads, ribs=ribs, low_s0=self.AD_S[1] + K["ADAPTER_CLR"])
        return self._cache["keeper"]

    def fork(self, over=0.0, drop=0.0):
        """The keeper fork (round E: a frame open on the plug side), world frame, seated: two feet and a lower block across
        both lower screws (above the adapter, which goes in after the fork), the button side's prong, widened to the wall
        above HEAD_S0, and a top bar across both upper screws; a pad over each screw. over: the pads this much proud (as
        printed). drop > 0: every piece stretched that far down the face instead: the volume its way up from below sweeps
        (no lead-ins, no foot cut)."""
        K, q = KEEPER, self.keeper()
        (T0, T1), psx, top = q["fork_t"], q["plug_sx"], K["TOP_S"]
        lo = lambda s: s - drop
        s_bot = 2.0                                     # below the lid's plane at this depth: the foot is cut along it
        E = K["HEAD_EDGE"]
        x_bar = float(np.interp(K["BAR_S0"], [a for a, _ in E], [b for _, b in E]))             # the bar's plug-side end at its foot
        parts = [box(-K["EAR_X"], K["EAR_X"], T0, T1, lo(q["low_s0"]), K["EAR_S1"])]            # lower block, above the adapter
        for sx in (-1, 1):
            parts.append(box(sx * K["SLOT_X"], sx * K["EAR_X"], T0, T1, lo(s_bot), K["EAR_S1"]))   # foot
        parts.append(box(-psx * K["SLOT_X"], -psx * K["PRONG_X"], T0, T1, lo(s_bot), K["HEAD_S0"] + 1.0))   # the prong: button side
        head = ([(-K["PRONG_X"], K["HEAD_S0"])] + [(-x, s) for s, x in E] + [(x, s) for s, x in E[::-1] if s > K["BAR_S0"]] +
                [(x_bar, K["BAR_S0"]), (-K["SLOT_X"], K["BAR_S0"]), (-K["SLOT_X"], K["HEAD_S0"])])   # (x, s), button side at -x
        parts.append(Pos(0, (T0 + T1) / 2, 0) * extrude(Plane.XZ * Polygon(*[(psx * x, s) for x, s in head], align=None), (T1 - T0) / 2, both=True))
        if drop > 0.0:                                  # what the head and the bar sweep below themselves
            parts.append(box(-psx * K["SLOT_X"], -psx * E[0][1], T0, T1, lo(K["HEAD_S0"]), E[0][0]))
            parts.append(box(-psx * K["SLOT_X"], psx * x_bar, T0, T1, lo(K["BAR_S0"]), K["BAR_S0"]))
        for sx, s in q["pads"]:
            parts.append(box(sx * (hw.NUT_DX - K["PAD"]) / 2, sx * (hw.NUT_DX + K["PAD"]) / 2, self.BOARD_T1 - over, T0,
                             lo(s - K["PAD"] / 2), s + K["PAD"] / 2))
        f = parts[0]
        for p_ in parts[1:]:
            f = f + p_
        if drop == 0.0:
            wedge = lambda pts, x0, x1: Pos((x0 + x1) / 2, 0, 0) * extrude(Plane.YZ * Polygon(*pts, align=None), (x1 - x0) / 2, both=True)
            L, e = K["LEAD"], 0.01
            f = f - wedge([(T1 - L, top + e), (T1 + e, top + e), (T1 + e, top - L)], -30, 30)   # the top bar's top, back edge
            for sx in (-1, 1):                                                                  # the lower block's top, back edge
                x0, x1 = sorted((-psx * (K["SLOT_X"] if sx == psx else K["PRONG_X"]), sx * (K["EAR_X"] + 1)))
                f = f - wedge([(T1 - L, K["EAR_S1"] + e), (T1 + e, K["EAR_S1"] + e), (T1 + e, K["EAR_S1"] - L)], x0, x1)
            tf, L = self.BOARD_T1 - over, K["PAD_LEAD"]
            for s in q["screws"]:
                s1 = s + K["PAD"] / 2
                f = f - wedge([(tf - e, s1 - L), (tf - e, s1 + e), (tf + L, s1 + e)], -30, 30)  # pads, upper edge
        f = self.wt(f.clean())
        if drop == 0.0:
            f = f & box(-100, 100, -100, 300, K["LID_CLR"], 300)                                # the foot, level above the lid
        check(f.is_valid and len(f.solids()) == 1, "keeper fork is not one valid solid")
        return f

    def fork_print(self):
        """The fork as printed: flat on its back face (the ribs' side), pads up, PAD_OVER proud."""
        f = self.fork(over=KEEPER["PAD_OVER"]).rotate(Axis.X, self.tilt).rotate(Axis.X, -90)    # body (x, t, s) -> (x, s, -t)
        f = Pos(0, 0, self.keeper()["fork_t"][1]) * f
        bb = f.bounding_box()
        check(abs(bb.min.Z) < 1e-6 and abs(bb.max.Z - (KEEPER["FORK_T"] + KEEPER["PAD_H"] + KEEPER["PAD_OVER"])) < 1e-6,
              f"fork as printed: z {bb.min.Z:.4f}..{bb.max.Z:.4f}")
        return f

    def rib_mesh(self, core_M):
        """The ribs as one mesh (world frame; manifold3d), added to the shell on the mesh as the slots are cut. Each is a
        prism along t (the fork's back face .. RIB_T behind it) of a profile in (s, x): the inner edge |x| = x_in from s_a
        to s_b, square at the top; below s_a a 45 deg corbel in that plane (43.1 deg from vertical printed standing); the
        wall side RIB_EMBED inside the cavity wall, which is read off core_M (the shell before the ribs) at the rib's
        three depths, every RIB_STEP. Returns (mesh, [(sx, x_in, s_a, s_b, corbel's foot s, volume)])."""
        import manifold3d as m3
        K, q = KEEPER, self.keeper()
        T0, T1 = q["rib_t"]
        ts = (T0, (T0 + T1) / 2, T1)
        Mb = {1: core_M.transform([[1, 0, 0, 0], [0, self.c, -self.sn, 0], [0, self.sn, self.c, 0]])}     # body (x, t, s)
        Mb[-1] = Mb[1].mirror((1, 0, 0))

        def wall(sx, s):
            polys = [np.asarray(P) for P in Mb[sx].slice(s).to_polygons()]
            out = []
            for t0 in ts:
                xs = []
                for P in polys:
                    Q = np.roll(P, -1, axis=0)
                    k = (P[:, 1] - t0) * (Q[:, 1] - t0) < 0
                    x = P[k, 0] + (t0 - P[k, 1]) * (Q[k, 0] - P[k, 0]) / (Q[k, 1] - P[k, 1])
                    xs += x[x > 0].tolist()
                check(len(xs) == 2, f"rib: the wall at s {s:.2f}, t {t0:.2f} crosses {len(xs)} times")   # inner, outer
                out.append(min(xs))
            return max(out)

        ribs, info = None, []
        for sx, x_in, s_a, s_b in q["ribs"]:
            emb = lambda s: x_in + (s_a - s) - (wall(sx, s) + K["RIB_EMBED"])     # > 0: the corbel is that deep in the wall
            lo = s_a - K["RIB_STEP"]
            while emb(lo) < 0:
                lo -= K["RIB_STEP"]
            hi = lo + K["RIB_STEP"]
            for _ in range(40):
                mid = 0.5 * (lo + hi)
                lo, hi = (mid, hi) if emb(mid) >= 0 else (lo, mid)
            s_c = 0.5 * (lo + hi)
            check(self.to_world(T1, s_c)[1] > 1.0, f"rib at x {sx * x_in:+.1f}: its corbel reaches the rim (s {s_c:.2f})")
            side = [(float(s), wall(sx, float(s)) + K["RIB_EMBED"]) for s in np.arange(s_b, s_c, -K["RIB_STEP"])]
            P = np.array([(s_a, x_in), (s_b, x_in)] + side + [(s_c, x_in + (s_a - s_c))])          # (s, x)
            area = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
            if area < 0:
                P = P[::-1]
            cs = m3.CrossSection([P.tolist()])
            check(cs.num_contour() == 1 and abs(cs.area() - abs(area)) < 1e-6 * abs(area), f"rib profile at x {sx * x_in:+.1f}")
            R = m3.Manifold.extrude(cs, T1 - T0)                                                    # (s, x, t - T0)
            R = R.transform([[0, 1, 0, 0], [self.sn, 0, self.c, T0 * self.c], [self.c, 0, -self.sn, -T0 * self.sn]])
            if sx < 0:
                R = R.mirror((1, 0, 0))
            check(R.status() == m3.Error.NoError and R.volume() > 0, f"rib at x {sx * x_in:+.1f}: {R.status()}")
            info.append((sx, x_in, s_a, s_b, s_c, R.volume()))
            ribs = R if ribs is None else ribs + R
        check(len(ribs.decompose()) == len(q["ribs"]), "ribs touch each other")
        return ribs.as_original(), info

    def seat_mesh(self):
        """The glass pocket's stops as one mesh (world frame; manifold3d), see SEAT: the top wedge, two side rails, two
        bottom corners. Built in the body frame (x, t, s) as prisms, the under-slopes cut by planes. Returns (mesh,
        dict of the numbers)."""
        import manifold3d as m3
        Q, F = SEAT, self.FRONT
        tan, e = math.tan(math.radians(Q["SLOPE"])), Q["EMBED"]
        xp = hw.GLASS_W / 2 + Q["SIDE_CLR"]
        o = 0.5                                         # the wedge and the corners run this far into the rails (no face-to-face joints)

        def ccw(P):
            P = np.asarray(P, float)
            a_ = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
            return (P if a_ > 0 else P[::-1]).tolist()

        def prism_ts(P, x0, x1):                        # (t, s) profile along x
            return m3.Manifold.extrude(m3.CrossSection([ccw(P)]), x1 - x0).transform([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0]])

        def prism_xt(P, s0, s1):                        # (x, t) profile along s
            return m3.Manifold.extrude(m3.CrossSection([ccw(P)]), s1 - s0).translate((0, 0, s0))

        def under(M_, t0, s_a):                         # keep t - t0 <= (s - s_a) tan: the under-slope, SLOPE to the face
            k = math.hypot(1.0, tan)
            return M_.trim_by_plane((0.0, -1.0 / k, tan / k), (tan * s_a - t0) / k)

        s0 = self.GLASS_TOP + Q["TOP_CLR"]              # the wedge leaves the floor here (the glass on the floor: no strips)
        s1 = s0 + Q["TOP_D"] / tan
        top = prism_ts([(F - e, s0), (F, s0), (F + Q["TOP_D"], s1), (F + Q["TOP_D"], s1 + Q["TOP_FLAT"]), (F - e, s1 + Q["TOP_FLAT"])], -xp - o, xp + o)
        h, L, x1 = Q["RAIL_H"], Q["RAIL_LEAD"], xp + Q["RAIL_W"]
        rail = prism_xt([(xp, F - e), (x1, F - e), (x1, F + h), (xp + L, F + h), (xp, F + h - L)], *Q["RAIL_S"])
        rail = under(rail, F, Q["RAIL_S"][0])
        sb = self.GLASS_S0 - Q["BOT_CLR"]               # the corners' flat top
        s_a = sb - (F + Q["BOT_D"] - Q["BOT_T0"]) / tan
        bot = under(prism_ts([(F - e, s_a - 0.5), (F + Q["BOT_D"], s_a - 0.5), (F + Q["BOT_D"], sb), (F - e, sb)], Q["BOT_X0"], xp + o), Q["BOT_T0"], s_a)
        parts = [top, rail, rail.mirror((1, 0, 0)), bot, bot.mirror((1, 0, 0))]
        for n_, P_ in zip(("top wedge", "rail", "rail", "bottom corner", "bottom corner"), parts):
            check(P_.status() == m3.Error.NoError and P_.volume() > 1.0 and len(P_.decompose()) == 1, f"pocket stop {n_}: {P_.status()}, {P_.volume():.2f} mm3")
        M_ = parts[0]
        for P_ in parts[1:]:
            M_ = M_ + P_
        M_ = M_.transform([[1, 0, 0, 0], [0, self.c, self.sn, 0], [0, -self.sn, self.c, 0]])        # body (x, t, s) -> world
        return M_.as_original(), dict(xp=xp, top=(s0, s1 + Q["TOP_FLAT"]), rail_t=F + h, rail_x1=x1, bot=(s_a, sb), bot_t=F + Q["BOT_D"])


PEB_STRAIGHT_TOL = 0.01                # the face over the slots: straight along the lean within this (t, both ways)
PEB_OVERHANG_MAX = 45.0                # deg from vertical, outside and inside (bridges apart)


def pebble_overhangs(m, nu=480, nv=1000):
    """The outer surface and the cavity's sampled (B-spline surfaces, exact points and normals): the steepest overhang
    (deg from vertical, where the surface faces down) and where; the cavity only where it is the shell's surface (above the
    rim, below the flat ceiling, behind the flat inner face)."""
    A = surface_samples(m._cache["env_srf"], nu, nv).reshape(-1, 6)
    k = int(np.argmin(A[:, 5]))
    out = (math.degrees(math.asin(max(-A[k, 5], 0.0))), A[k, :3])
    C = surface_samples(m._cache["cav_srf"], nu, nv).reshape(-1, 6)
    t = C[:, 1] * m.c - C[:, 2] * m.sn
    C = C[(C[:, 2] > 0.0) & (C[:, 2] < m.CAV["zf"] - 1e-6) & (t > m.FRONT + 1e-6)]
    k = int(np.argmax(C[:, 5]))                        # the cavity's normal points into the shell: the shell faces down
    inn = (math.degrees(math.asin(max(C[k, 5], 0.0))), C[k, :3])
    return out, inn, A


def pebble_region(m, p):
    x, y, z = p
    t = y * m.c - z * m.sn
    return ("rim zone" if z < 3.0 else "dome" if z > 85.0 else "front" if t < m.FRONT + 3.0 else
            "back" if y > 40.0 and abs(x) < 20.0 else "sides")


PEB_FULL_CHECKS = False                # round B (user): only land, overhangs, clearances, logo skin, insertion path and closed
                                       # bodies; True adds the walls (exact and sampled), the seat's wall, the outline against the
                                       # sketch, the face's straightness and the flat inner face's span (true by construction)


def occ_to_manifold(shape, defl=0.005, ang=0.05):
    """An OCC solid as a manifold3d Manifold: meshed as read back from STEP (the in-memory pebble shell meshes with open
    edges), deflection `defl` (absolute) / `ang`; vertices merged."""
    import tempfile, pyvista as pv, manifold3d as m3
    from build123d import import_step
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.StlAPI import StlAPI_Writer
    with tempfile.TemporaryDirectory() as td:
        g = pathlib.Path(td) / "m.step"
        export_step(shape, str(g))
        back = import_step(str(g))
        BRepMesh_IncrementalMesh(back.wrapped, defl, False, ang, True).Perform()
        fs = pathlib.Path(td) / "m.stl"
        w = StlAPI_Writer()
        w.ASCIIMode = False
        check(w.Write(back.wrapped, str(fs)), "mesh not written")
        mesh = pv.read(str(fs)).clean()
    check(mesh.n_open_edges == 0, f"OCC mesh: {mesh.n_open_edges} open edges")
    F = mesh.faces.reshape(-1, 4)[:, 1:]
    M = m3.Manifold(m3.Mesh64(vert_properties=np.ascontiguousarray(mesh.points, np.float64), tri_verts=np.ascontiguousarray(F, np.uint64)))
    check(M.status() == m3.Error.NoError and not M.is_empty(), f"OCC mesh to manifold: {M.status()}")
    return M


def manifold_arrays(M):
    m = M.to_mesh64()
    return np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts, np.int64)


def write_manifold_stl(M, path):
    import pyvista as pv
    V, F = manifold_arrays(M)
    pv.PolyData(V, np.c_[np.full(len(F), 3), F].ravel()).save(str(path), binary=True)


def mesh_quality(M, path=None):
    """The final mesh: pieces, open / non-manifold edges (pyvista, on the written STL or the arrays), degenerate slivers
    (triangles under 1e-6 mm2 or with an inscribed radius under 1e-4)."""
    import pyvista as pv
    V, F = manifold_arrays(M)
    pd = pv.PolyData(V, np.c_[np.full(len(F), 3), F].ravel()).clean()
    nm = pd.extract_feature_edges(boundary_edges=False, feature_edges=False, manifold_edges=False, non_manifold_edges=True).n_cells
    a, b, c_ = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c_ - a), axis=1)
    per = np.linalg.norm(b - a, axis=1) + np.linalg.norm(c_ - b, axis=1) + np.linalg.norm(a - c_, axis=1)
    rin = 2 * area / np.maximum(per, 1e-12)
    return dict(pieces=len(M.decompose()), open=pd.n_open_edges, nonman=nm, tris=len(F), tiny=int((area < 1e-6).sum()),
                slivers=int((rin < 1e-4).sum()), min_rin=float(rin.min()), vol=M.volume())


def mesh_check_paths(m, shell_M, lid, moving, adapter, order):
    """check_paths with the shell as a mesh (manifold3d): every sweep of the assembly order against the shell (overlap
    volume, min_gap), the body-to-body parts as check_paths (OCC)."""
    drop = 2 * m.H
    gaps = {}
    toM = lambda s_: occ_to_manifold(s_, 0.01, 0.1)

    def vs_shell(sw, what):
        Ms = toM(sw)
        v = (Ms ^ shell_M).volume()
        check(v < EPS_V, f"{m.name}: {what} cuts {v:.3f} mm3 out of the shell")
        return Ms.min_gap(shell_M, 10.0)
    shift = m.insert_shift
    first = [b for b in moving if not (order == "battery-after" and b.name == "battery")]
    for b in first:
        gaps[("up", b.name)] = vs_shell(b.solid(dt=shift, es0=drop, es1=Z_STOP), f"insertion, up move: {b.name}")
        gaps[("forward", b.name)] = vs_shell(b.solid(et=shift), f"insertion, forward move: {b.name}")
    seated = [(b.name, b.solid()) for b in moving]
    board_seated = [(n, x) for n, x in seated if n != "battery"]
    for move, sw in bat_sweeps(m, order, drop)[0]:
        for on, o in board_seated:
            v = volume_common(sw, o)
            check(v < EPS_V, f"{m.name}: battery, {move}: runs into the {on} ({v:.2f} mm3)")
        gaps[(move, "battery")] = vs_shell(sw, f"battery, {move}")
        gaps[(move, "battery-board")] = min(gap(sw, o) for n, o in board_seated if n in ("board", "plug-j5", "plug-i2c"))
    sweep = adapter.solid(es0=drop)
    gaps[("adapter", "shell")] = vs_shell(sweep, "adapter move")
    for on, o in seated:
        v = volume_common(sweep, o)
        check(v < EPS_V, f"{m.name}: adapter move runs into the {on} ({v:.2f} mm3)")
        gaps[("adapter", on)] = gap(sweep, o)
    lsweep = m.lid_sweep(drop)
    check(volume_common(lid, lsweep) >= lid.volume - 1e-3, "lid sweep does not contain the lid")
    gaps[("lid", "shell")] = vs_shell(lsweep, "lid move")
    for on, o in [("adapter", adapter.solid())] + seated:
        v = volume_common(lsweep, o)
        check(v < EPS_V, f"{m.name}: lid move runs into the {on} ({v:.2f} mm3)")
        gaps[("lid", on)] = gap(lid, o)
    for n, o in seated + [("adapter", adapter.solid()), ("lid", lid)]:
        Mo = toM(o)
        v = (Mo ^ shell_M).volume()
        check(v < EPS_V, f"assembled: the shell and the {n} overlap by {v:.3f} mm3")
        gaps[("seated", n)] = Mo.min_gap(shell_M, 10.0)
    return gaps


def mesh_land(m, shell_M, cutter_M):
    """The lands, body frame. The design's depth (slot_surface at the land's edge). On the final mesh: the walls' spacing
    at the inner face and
    how far each wall runs straight (vertices within 3e-4 of the plane): manifold drops the land's top vertex, since the
    lip starts vertical, tangent to the land, so the final wall runs on to the lip's first node."""
    out = {}
    for tag, M_ in (("final", shell_M),):
        V, F = manifold_arrays(M_)
        t = V[:, 1] * m.c - V[:, 2] * m.sn
        s = V[:, 1] * m.sn + V[:, 2] * m.c
        S0, S1 = m.SLOT_S
        body = (s >= S0) & (s <= S1) & (t <= m.FRONT + 1e-6)
        for sx in (-1, 1):
            for sg in (-1, 1):
                e = sx * m.tube_cc / 2 + sg * SLOT_W / 2
                k = body & (np.abs(V[:, 0] - e) < 3e-4)
                check(k.sum() >= 2, f"mesh land ({tag}): no wall at x {e:+.3f}")
                atT = k & (np.abs(t - m.FRONT) < 1e-4)
                out[(tag, sx, sg)] = (float(np.median(V[atT, 0])) if atT.any() else math.nan, float(m.FRONT - t[k].min()))
    widths = [out[("final", sx, 1)][0] - out[("final", sx, -1)][0] for sx in (-1, 1)]
    smid = sum(m.SLOT_S) / 2                                 # the design (manifold drops the node: see above)
    design = [m.FRONT - m.slot_params()["L"]] * 4             # the lips start at the land's top, L (slot_surface's limit there)
    reach = [out[("final", sx, sg)][1] for sx in (-1, 1) for sg in (-1, 1)]
    return min(widths), max(widths), min(design), max(design), min(reach), max(reach)


def mesh_slot_overhang(m, shell_M):
    """On the final mesh, the triangles of the slots' region (lips, lands, ends; body frame, in front of the inner face,
    within the cut's bounding box): the steepest overhang printed standing (deg from vertical) and where, apart from the
    named exception: the top end walls (the plane s = S1, facing down the slot: 75 deg ceilings, on tree supports, as in
    A; it includes the lips' crescents in that plane). Returns (rest, where), (the exception's steepest, its extent
    x range (both slots), t range, its area)."""
    P = m.slot_params()
    V, F = manifold_arrays(shell_M)
    a, b, c_ = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    cr = np.cross(b - a, c_ - a)
    ar = np.linalg.norm(cr, axis=1) / 2
    n = cr / np.maximum(2 * ar, 1e-15)[:, None]
    cen = (a + b + c_) / 3
    t = cen[:, 1] * m.c - cen[:, 2] * m.sn
    s = cen[:, 1] * m.sn + cen[:, 2] * m.c
    ns = n[:, 1] * m.sn + n[:, 2] * m.c
    S0, S1 = m.SLOT_S
    reg = (np.abs(cen[:, 0]) < P["xc"] + P["half"] + P["a_out"] + 0.5) & (s > S0 - 0.5) & (s < S1 + 0.5) & (t < m.FRONT - 1e-3)
    ov = np.degrees(np.arcsin(np.clip(-n[:, 2], 0, 1)))
    exc = reg & (np.abs(s - S1) < 1e-3) & (ns < -1 + 1e-6)
    rest = np.where(reg & ~exc)[0]
    i = rest[np.argmax(ov[rest])]
    k = np.where(exc)[0]
    check(len(k) > 0, "pebble: no top end wall found on the mesh")
    xe = np.abs(V[F[k]].reshape(-1, 3)[:, 0])
    te = (V[F[k]].reshape(-1, 3)[:, 1] * m.c - V[F[k]].reshape(-1, 3)[:, 2] * m.sn)
    return ((float(ov[i]), (round(float(cen[i, 0]), 2), round(float(s[i]), 2))),
            (float(ov[k].max()), (float(xe.min()), float(xe.max())), (float(te.min()), float(te.max())), float(ar[k].sum())))


def mesh_front_wall(m, shell_M):
    """The front wall's thickness along t on the final mesh, round the slots: from points of the flat inner face (a grid,
    not in the slots or within 0.05 of a land), the first hit outwards (-t). Returns the minimum and where."""
    P = m.slot_params()
    S0, S1 = m.SLOT_S
    best = (math.inf, None)
    dvec = np.array([0.0, -m.c, m.sn])                      # -t in world
    for s_ in np.linspace(S0 - P["ae"], S1 + P["ae"], 40):
        for x in np.linspace(-(P["xc"] + P["half"] + P["a_out"]), P["xc"] + P["half"] + P["a_out"], 81):
            dx = abs(abs(x) - P["xc"]) - P["half"]
            if dx < 0.05 and S0 - 0.05 <= s_ <= S1 + 0.05:
                continue
            o = np.array([x, *m.to_world(m.FRONT - 1e-4, s_)])
            hits = shell_M.ray_cast(tuple(o), tuple(o + 8 * dvec))
            if not hits:
                continue
            d = min(h.distance for h in hits) * 8            # (distance: the fraction of the ray)
            if d < best[0]:
                best = (d, (round(x, 2), round(s_, 2)))
    return best


# The glass pocket's stops (round E, user 2026-11-27). The rods are NOT glued to the glass (gluing loses the sanded
# low-pass filter, the moire comes back), so they do not locate the board: the shell has to hold it along the face (it
# slid up) and sideways. The glass already sits in a shallow pocket in the front wall (floor = the inner face at FRONT;
# side steps 1.2 high at |x| 15.9, a bottom ledge <= 1.1 high outside |x| 10, at its top only the corners' ramp). Added on
# the mesh like the ribs: a wedge across the pocket's top, rails on its side steps, taller bottom corners. Where they
# overhang printed standing they slope SLOPE to the face (+ the 15 deg lean = 45). The user assembles without the foam
# strips, so the wedge starts for the glass ON the pocket's floor; with the strips the glass can rise ~0.9 more.
SEAT = dict(SIDE_CLR=0.15,                              # rails to the glass, each side (the pocket itself: 0.3)
            RAIL_H=3.0, RAIL_W=2.25, RAIL_LEAD=0.6,     # rails: height over the pocket's floor, width, lead-in on the inner edge
            RAIL_S=(17.0, 96.0),                        # ... from the bottom ledge (ramping up) to above the glass
            TOP_CLR=0.3, TOP_D=2.6, TOP_FLAT=1.0,       # top wedge: it leaves the floor this far above the glass, rises to this
                                                        # depth, then runs level this far
            BOT_CLR=0.325, BOT_D=2.6, BOT_X0=10.0,      # bottom corners: their flat top this far under the glass, up to this
                                                        # depth over the floor, from |x| BOT_X0 (logo pocket and adapter inside it)
            BOT_T0=3.2,                                 # ... their under-slope leaves the wall from this depth (the chin's face
                                                        # is 3.3..4.5 there)
            SLOPE=29.5, EMBED=0.8,                      # under-slopes to the face (deg; 44.5 printed); every piece starts this far in the wall
            MIN_GAP=0.1)                                # the seated glass / board to the stops, at least (also without the strips)


def seat_on(m, shell_M, seat_M):
    """shell + the pocket's stops. They must stay inside the outer skin (nothing of them outside the envelope) and join
    the shell into one piece. Returns (the union, the volume they add, the steepest overhang of their faces left on the
    surface printed standing (deg from vertical) and where)."""
    import manifold3d as m3
    out_v = (seat_M - occ_to_manifold(m.shell_env(), 0.01, 0.1)).volume()
    check(out_v < 1e-3, f"pocket stops: {out_v:.3f} mm3 of them is outside the outer skin")
    added = (seat_M - shell_M).volume()
    U = shell_M + seat_M
    check(U.status() == m3.Error.NoError and len(U.decompose()) == 1 and added > 1.0,
          f"shell + pocket stops: {U.status()}, {len(U.decompose())} pieces, {added:.1f} mm3 added")
    me = U.to_mesh64()
    V, F = np.asarray(me.vert_properties)[:, :3], np.asarray(me.tri_verts, np.int64)
    ri = np.asarray(me.run_index) // 3
    mine = np.zeros(len(F), bool)
    for k, oid in enumerate(me.run_original_id):
        if oid == seat_M.original_id():
            mine[ri[k]:ri[k + 1]] = True
    check(mine.any(), "pocket stops: none of their faces is on the surface")
    a, b, c_ = V[F[mine, 0]], V[F[mine, 1]], V[F[mine, 2]]
    n = np.cross(b - a, c_ - a)
    ar = np.linalg.norm(n, axis=1)
    ov = np.degrees(np.arcsin(np.clip(-n[:, 2] / np.maximum(ar, 1e-15), 0, 1)))
    ov[ar < 1e-7] = 0.0
    i = int(np.argmax(ov))
    return U, added, (float(ov[i]), ((a[i] + b[i] + c_[i]) / 3).round(2))


def seat_gaps(m, seat_M, fork, adapter):
    """The stops against what is seated: glass, board, buttons, plugs, rods, adapter, fork; glass and board also 0.5 further
    forward (no foam strips: the glass on the pocket's floor). Returns {name: gap} for the glass and the least other."""
    G = {}
    bodies = [(b.name, b.solid()) for b in m.moving_bodies() if b.name != "battery"] + [("adapter", adapter.solid()), ("fork", fork)]
    bodies += [(b.name + ", no strips", b.solid(dt=-hw.GASKET)) for b in m.moving_bodies() if b.name in ("glass", "board")]
    for n, o in bodies:
        Ms = occ_to_manifold(o, 0.01, 0.1)
        v = (Ms ^ seat_M).volume()
        check(v < EPS_V, f"{m.name}: the seated {n} is in a pocket stop ({v:.3f} mm3)")
        G[n] = Ms.min_gap(seat_M, 10.0)
    worst = min(G, key=G.get)
    check(G[worst] >= SEAT["MIN_GAP"] - 1e-9, f"{m.name}: the seated {worst} is {G[worst]:.3f} from a pocket stop")
    return G


def keeper_ribs_on(m, shell_M, ribs_M):
    """shell + ribs. The ribs must stay inside the wall: what they add is one piece per rib, all in the cavity (a rib that
    came out through the outer skin would add a piece outside), and each rib is in the wall all along its bearing span
    (its section in the wall at 7 heights from s_a to s_b). Returns (the union, the added volume, the steepest overhang
    of the ribs' faces left on the surface printed standing (deg from vertical) and where)."""
    import manifold3d as m3
    spans = m.keeper()["ribs"]
    n_ribs = len(spans)
    Eb = (ribs_M ^ shell_M).transform([[1, 0, 0, 0], [0, m.c, -m.sn, 0], [0, m.sn, m.c, 0]])        # in the wall; body (x, t, s)
    for sx, x_in, s_a, s_b in spans:
        for s in np.linspace(s_a + 0.3, s_b - 0.3, 7):
            a_ = 0.0
            for P in Eb.slice(float(s)).to_polygons():
                P = np.asarray(P)
                if sx * P[:, 0].mean() > 0:
                    a_ += abs(0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]))
            check(a_ >= 0.6 * KEEPER["RIB_EMBED"] * KEEPER["RIB_T"],
                  f"rib at x {sx * x_in:+.1f}: only {a_:.2f} mm2 of its section is in the wall at s {s:.1f}")
    added = ribs_M - shell_M
    check(len(added.decompose()) == n_ribs, f"ribs: they add {len(added.decompose())} pieces, not {n_ribs} (through the wall?)")
    for R in ribs_M.decompose():                           # each rib by itself: one piece, in the cavity, RIB_EMBED in the wall
        bb = R.bounding_box()
        sx = 1.0 if bb[0] + bb[3] > 0 else -1.0
        A = R - shell_M
        V = np.asarray(A.to_mesh64().vert_properties)[:, :3]
        p_in = V[np.argmin(sx * V[:, 0])] - np.array([sx * 0.05, 0, 0])     # just inside the cavity, off the rib's inner edge
        hits = shell_M.ray_cast(tuple(p_in), tuple(p_in + np.array([sx * 100.0, 0, 0])))
        emb = (R ^ shell_M).volume() / ((bb[5] - bb[2]) * KEEPER["RIB_T"])  # mean depth in the wall (over its height, ~)
        check(len(A.decompose()) == 1 and len(hits) == 2 and emb >= 0.6 * KEEPER["RIB_EMBED"],
              f"rib at x {sx * abs(p_in[0]):+.1f}: {len(A.decompose())} pieces, {len(hits)} wall faces outside it (2: in the cavity), "
              f"{emb:.2f} deep in the wall")
    U = shell_M + ribs_M
    check(U.status() == m3.Error.NoError and len(U.decompose()) == 1, f"shell + ribs: {U.status()}, {len(U.decompose())} pieces")
    me = U.to_mesh64()
    V, F = np.asarray(me.vert_properties)[:, :3], np.asarray(me.tri_verts, np.int64)
    ri = np.asarray(me.run_index) // 3
    mine = np.zeros(len(F), bool)
    for k, oid in enumerate(me.run_original_id):
        if oid == ribs_M.original_id():
            mine[ri[k]:ri[k + 1]] = True
    check(mine.any(), "ribs: none of their faces is on the surface")
    a, b, c_ = V[F[mine, 0]], V[F[mine, 1]], V[F[mine, 2]]
    n = np.cross(b - a, c_ - a)
    ar = np.linalg.norm(n, axis=1)
    ov = np.degrees(np.arcsin(np.clip(-n[:, 2] / np.maximum(ar, 1e-15), 0, 1)))
    ov[ar < 1e-7] = 0.0
    i = int(np.argmax(ov))
    return U, added.volume(), (float(ov[i]), ((a[i] + b[i] + c_[i]) / 3).round(2))


def keeper_plugs(m):
    """This board's plugs (PebbleModel.moving_bodies): three standing behind the plate, RTC to the side."""
    return [b for b in m.moving_bodies() if b.name.startswith("plug")]


def keeper_rib_gap(m, ribs_M, adapter):
    """The ribs against what sits in front of them, seated: board, glass, buttons, every plug, the adapter. Round E (user,
    2026-11-27): the board slides in along the front wall, also with its rods on, so the ribs reach over it and the
    back-shifted up move (insert_shift) is not swept against them. Returns the least gap and whose."""
    worst = (math.inf, None)
    for n, o in [(b.name, b.solid()) for b in m.moving_bodies() if b.name != "battery" and not isinstance(b, Rod)] + [("adapter", adapter.solid())]:
        Ms = occ_to_manifold(o, 0.01, 0.1)
        v = (Ms ^ ribs_M).volume()
        check(v < EPS_V, f"{m.name}: the seated {n} is in a rib ({v:.3f} mm3)")
        worst = min(worst, (Ms.min_gap(ribs_M, 10.0), n))
    check(worst[0] >= KEEPER["PATH_MIN"] - 1e-9, f"{m.name}: the seated {worst[1]} is {worst[0]:.2f} from a rib")
    return worst


def keeper_fork_check(m, fork, core_M, core0_M, ribs_M, lid, moving, adapter):
    """The fork seated and on its way up from below: no overlap with the shell (ribs included), the seated board, plugs,
    buttons, adapter or lid. Round E: it goes in before the adapter and with the upward sockets (UART, J5, I2C) empty, the
    top bar passes over them: those are checked seated only. Returns its gaps: to the walls (the shell before the ribs),
    to the adapter, the bearing areas on the ribs (contact in their front plane), the least of them with the fork
    pushed sideways to a wall."""
    Mf = occ_to_manifold(fork, 0.01, 0.1)
    sweep = m.fork(drop=2 * m.H)
    for what, M_ in (("seated", Mf), ("on its way up", occ_to_manifold(sweep, 0.01, 0.1))):
        v = (M_ ^ core_M).volume()
        check(v < EPS_V, f"{m.name}: the fork {what} cuts {v:.3f} mm3 out of the shell")
    seated = [(b.name, b.solid()) for b in moving if b.name != "battery"] + [("adapter", adapter.solid())]
    psx = -hw.BTN_SIDE                                      # what must be there, stated here (not read back from keeper())
    check(sorted(b.name for b in keeper_plugs(m)) == ["plug-i2c", "plug-j5", "plug-rtc", "plug-uart"],
          f"keeper: the plugs among the moving bodies are {sorted(b.name for b in keeper_plugs(m))}")
    for on, o in seated + [("lid", lid)]:
        for what, f_ in (("seated", fork), ("on its way up", sweep)):
            if f_ is sweep and on in ("lid", "adapter", "plug-uart", "plug-j5", "plug-i2c"):
                continue
            v = volume_common(f_, o)
            check(v < EPS_V, f"{m.name}: the fork {what} runs into the {on} ({v:.3f} mm3)")
    K, q = KEEPER, m.keeper()
    T1, e = q["fork_t"][1], 1e-3
    tb = lambda M_: M_.transform([[1, 0, 0, 0], [0, m.sn, m.c, 0], [0, m.c, -m.sn, 0]])       # (x, s, t): slices at a depth t
    Fb, Rb = tb(Mf), tb(ribs_M)
    # contact in the bearing plane: the fork's back face (just inside it: the lead-ins have receded there) on the ribs' front face
    def contact(F_):                                        # (x, s) of each contact patch's centre, its area
        out = []
        for c in (F_.slice(T1 - e) ^ Rb.slice(T1 + e)).decompose():
            b = c.bounds()
            out.append(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, c.area()))
        return out
    bear = contact(Fb)
    areas = sorted(round(a, 1) for _, _, a in bear)
    s_lo, s_hi = m.PCB_S0 + hw.NUT_INSET, m.PCB_S0 + hw.NUT_INSET + hw.NUT_DZ
    where = sorted((round(x / abs(x)), s > (s_lo + s_hi) / 2) for x, s, _ in bear)      # (side, upper?)
    check(where == sorted([(psx, False), (psx, True), (-psx, False), (-psx, True)]) and min(areas) > 5.0 and Mf.min_gap(ribs_M, 1.0) < 1e-3,
          f"{m.name}: the fork bears on the ribs at (side, upper) {where} over {areas} mm2, {Mf.min_gap(ribs_M, 1.0):.3f} from them")
    # ... and pushed sideways as far as the walls let it (the top bar runs wall to wall: its gap is the fork's side play)
    wall = Mf.min_gap(core0_M, 10.0)
    side = []
    for d in (-wall, wall):
        c_ = contact(Fb.translate((d, 0, 0)))
        side.append(min(a_ for _, _, a_ in c_) if len(c_) == 4 else 0.0)
    check(min(side) > 5.0, f"{m.name}: pushed {wall:.2f} sideways the fork bears on a rib over only {min(side):.1f} mm2")
    pads = Fb.slice(m.BOARD_T1 + e).decompose()             # the pads' tips: on the plate, one over each of the four screws
    board = [o for n, o in seated if n == "board"][0]
    want = sorted([(sx * hw.NUT_DX / 2, s_) for sx in (-1, 1) for s_ in (s_lo, s_hi)])
    got = sorted((round((c.bounds()[0] + c.bounds()[2]) / 2, 3), round((c.bounds()[1] + c.bounds()[3]) / 2, 3)) for c in pads)
    check(len(pads) == len(want) and gap(fork, board) < 1e-6 and all(abs(g[0] - w[0]) < 0.5 and abs(g[1] - w[1]) < 0.5 for g, w in zip(got, want))
          and min(c.area() for c in pads) > 0.7 * K["PAD"] ** 2,
          f"{m.name}: the pads' tips {got} (screws {want}), {gap(fork, board):.3f} from the plate")
    return dict(wall=wall, adapter=gap(fork, adapter.solid()), lid=gap(fork, lid), bear=areas, side=min(side))


def build_pebble(order=ORDER):
    """Rounds B, C: the shell is built in OCC without the slots (shell-noslots.step), meshed finely and cut with the slots'
    mesh (manifold3d). Round C (user, 2026-11-24): four checks only: the final shell mesh closed and in one piece,
    overhangs <= 45 outside the named exception (the top end walls), seated clearances (the rods in the slots; the
    adapter's up-move past the chin), the logo's thinnest skin. The rest (land, insertion sweeps, front-wall ray casts,
    STEP / STL read-back, slivers, magnets, cable, tipping) behind PEB_FULL_CHECKS."""
    import manifold3d as m3
    name = "pebble"
    out = OUT_ROOT / name
    out.mkdir(parents=True, exist_ok=True)
    print(f"[{name}] sections, cavity ...", flush=True)
    m = PebbleModel()
    CV, SP = m.CAV, m.slot_params()
    print(f"[{name}] W {m.W:.2f} H {m.H} front {m.FRONT}, c-c {m.tube_cc}, ceiling z {CV['zf']}, up-move shift {m.insert_shift}; "
          f"building ...", flush=True)
    spots = m.magnet_spots()
    if PEB_FULL_CHECKS:
        meats = meat_at(spots, m.shell("body"), m.lid_blank(), fast=True)
    shell_core = m.shell("core")                           # OCC, no slots
    shell = m.shell("full")
    lid = m.lid()
    moving = m.moving_bodies()
    adapter = m.adapter()
    ad = adapter.solid()
    for n, p in (("shell (before the slots)", shell), ("lid", lid)):
        check(p.is_valid and len(p.solids()) == 1, f"{name}: {n} is not a single valid solid")
    if PEB_FULL_CHECKS:
        for (x, y), (ms, ml) in zip(spots, meats):
            check(min(ms, ml) >= MAG_MEAT_FRONT_MIN - 1e-6, f"pebble: magnet at ({x:.2f}, {y:.2f}): {ms:.2f} in the rim, {ml:.2f} in the lid")

    # ---- the slots, on the mesh ----
    print(f"[{name}] slots (mesh) ...", flush=True)
    cutter = m.slot_cutter_mesh()
    MESH_D, MESH_A = PEBBLE["MESH_DEFL"], PEBBLE["MESH_ANG"]
    shell_M = occ_to_manifold(shell, MESH_D, MESH_A) - cutter
    core_M = occ_to_manifold(shell_core, MESH_D, MESH_A) - cutter
    for n_, M_ in (("shell", shell_M), ("core", core_M)):
        check(M_.status() == m3.Error.NoError and not M_.is_empty() and len(M_.decompose()) == 1,
              f"pebble {n_} after the slots: {M_.status()}, {len(M_.decompose())} pieces")

    # ---- the keeper (rounds D, E): ribs added on the mesh, the fork ----
    print(f"[{name}] keeper: ribs, fork ...", flush=True)
    KQ = m.keeper()
    core0_M = core_M                                       # the shell before the ribs: the cavity walls
    ribs_M, rib_info = m.rib_mesh(core0_M)
    shell_M, rib_vol, (ov_rib, ov_rib_p) = keeper_ribs_on(m, shell_M, ribs_M)
    core_M = keeper_ribs_on(m, core0_M, ribs_M)[0]
    check(ov_rib <= PEB_OVERHANG_MAX, f"pebble: a rib face overhangs {ov_rib:.2f} deg at {ov_rib_p}")
    rib_gap = keeper_rib_gap(m, ribs_M, adapter)
    fork = m.fork()
    FK = keeper_fork_check(m, fork, core_M, core0_M, ribs_M, lid, moving, adapter)
    # ---- the glass pocket's stops (round E): added on the mesh ----
    seat_M, SQ = m.seat_mesh()
    shell_M, seat_vol, (ov_seat, ov_seat_p) = seat_on(m, shell_M, seat_M)
    core_M = seat_on(m, core_M, seat_M)[0]
    check(ov_seat <= PEB_OVERHANG_MAX, f"pebble: a pocket stop's face overhangs {ov_seat:.2f} deg at {ov_seat_p}")
    SG = seat_gaps(m, seat_M, fork, adapter)
    Q = mesh_quality(shell_M)
    check(Q["open"] == 0 and Q["nonman"] == 0 and Q["pieces"] == 1, f"pebble shell mesh: {Q}")

    # ---- land, rods in the slots (final mesh) ----
    check(SLOT_W - hw.ROD_W >= ROD_PLAY_MIN - 1e-9 and SLOT_L - ROD_L >= 0.1, "rod clearance in the slot")
    if PEB_FULL_CHECKS:
        lw0, lw1, ld, ld1, lr0, lr1 = mesh_land(m, core_M, cutter)
        check(abs(lw0 - SLOT_W) < 1e-3 and abs(lw1 - SLOT_W) < 1e-3 and abs(ld - m.RIM) < LAND_DY + 1e-6 and abs(ld1 - m.RIM) < LAND_DY + 1e-6
              and m.RIM - LAND_DY <= lr0 and lr1 <= m.RIM + 0.05,
              f"pebble land on the mesh: {lw0:.4f}..{lw1:.4f} wide, {ld:.3f}..{ld1:.3f} deep (design), the final wall straight for {lr0:.3f}..{lr1:.3f}")

    rod_clr = {}
    for t in hw.TAPE:
        g_ = []
        for sx in (-1, 1):
            Mr = occ_to_manifold(Rod(m, "rod", sx * m.tube_cc / 2, t).solid(), 0.01, 0.1)
            v = (Mr ^ core_M).volume()
            check(v < EPS_V, f"a rod (tape {t}) runs into its slot ({v:.3f} mm3)")
            g_.append(Mr.min_gap(core_M, 5.0))
        rod_clr[t] = min(g_)
    smid = sum(m.SLOT_S) / 2
    xs = np.linspace(-24, 24, 48001)
    Pm = m.slot_surface(xs, smid)
    fx = SP["f"](xs)
    rr = xs[(xs > 0) & (Pm - fx > 1e-3)]
    opening, gap_open = rr.max() - rr.min(), 2 * rr.min()
    shallow = xs[(np.abs(xs) < SP["xc"]) & (Pm - fx < 0.3)]
    nose_reads = 2 * np.abs(shallow).max() if len(shallow) else 0.0
    mat1 = m.FRONT - float(m.slot_surface(SP["xc"] - SP["half"] - 1.0, smid))
    proud = {t: float(SP["f"](SP["xc"])) - (m.GLASS_T0 - t - hw.ROD_W / 2) for t in hw.TAPE}

    # ---- overhangs: outside, the cavity (B-splines), the slots (final mesh) ----
    print(f"[{name}] overhangs, walls ...", flush=True)
    (ov_out, ov_out_p), (ov_in, ov_in_p), OS = pebble_overhangs(m)
    (ov_slot, ov_slot_p), (ov_top, top_x, top_t, top_a) = mesh_slot_overhang(m, shell_M)
    check(abs(ov_top - (90 - m.tilt)) < 0.1, f"pebble: the top end walls {ov_top:.2f} deg from vertical, want {90 - m.tilt}")
    check(ov_out <= PEB_OVERHANG_MAX and ov_in <= PEB_OVERHANG_MAX and ov_slot <= PEB_OVERHANG_MAX,
          f"pebble: overhang {ov_out:.2f} deg outside at {ov_out_p.round(2)}, {ov_in:.2f} inside at {ov_in_p.round(2)}, "
          f"{ov_slot:.2f} at the slots at (x, s) {ov_slot_p}")
    zf = CV["zf"]
    flats = [f for f in shell_core.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6 and abs(f.center().Z - zf) < 1e-3]
    check(len(flats) == 1, f"flat ceiling: {len(flats)}")
    fb = flats[0].bounding_box()
    bridge = min(fb.size.X, fb.size.Y)
    check(bridge <= PEBBLE["BRIDGE_MAX"] + 1e-3, f"ceiling bridge {bridge:.2f}")
    if PEB_FULL_CHECKS:
        fw_min, fw_p = mesh_front_wall(m, shell_M)
        check(fw_min >= m.RIM - 0.01, f"pebble: the front wall round the slots {fw_min:.3f} thick at (x, s) {fw_p}")
        wtxt = (f"[m, mesh] the front wall round the slots, along t from the inner face, at its thinnest {fw_min:.2f} at (x, s) {fw_p} "
                f"(the land: {m.RIM} by design); [d] 1 mm out from a land {mat1:.2f}; elsewhere unchanged since A (3.01 measured, the "
                f"seat over the glass's edge 1.90; not re-measured: PEB_FULL_CHECKS off)")

    if PEB_FULL_CHECKS:
        # ---- USB: rim notch, the cable to it ----
        usb_cut = m.usb_cutter()
        # (round E: a closed slot, no rim notch; the cable path below still ends at the lid: stale, PEB_FULL_CHECKS only)
        sy, sz = m.to_world(m.AD_T[1], m.SOCKET_S)
        rc = CABLE_D / 2
        lam = (sz - rc - 0.05) / m.sn
        pb = (sy + lam * m.c, sz - lam * m.sn)
        from build123d import Sphere
        cable = (Pos(0, sy, sz) * Cylinder(rc, lam, rotation=(-90 - m.tilt, 0, 0), align=(Align.CENTER, Align.CENTER, Align.MIN))
                 + Pos(0, *pb) * Sphere(rc)
                 + Pos(0, pb[0], pb[1]) * Cylinder(rc, m.D + 5 - pb[0], rotation=(-90, 0, 0), align=(Align.CENTER, Align.CENTER, Align.MIN)))
        cab = {}
        for on, o in [("shell", shell), ("lid", lid)] + [(b.name, b.solid()) for b in moving]:
            v = volume_common(cable, o)
            check(v < EPS_V, f"pebble: the cable runs into the {on} ({v:.2f} mm3)")
            cab[on] = gap(cable, o)

    # ---- clearances, insertion path (final mesh) ----
    if PEB_FULL_CHECKS:
        print(f"[{name}] path checks (mesh) ...", flush=True)
        gaps = mesh_check_paths(m, core_M, lid, moving, adapter, order)
        final = [("lid", lid), ("adapter", ad)] + [(b.name, b.solid()) for b in moving]
        check_static(final)
        bat_solid = [b for b in moving if b.name == "battery"][0].solid()
        ad_bat, bat_lid = gap(ad, bat_solid), gap(bat_solid, lid)
        check(ad_bat >= BAT_ADAPTER_MIN - 1e-6 and bat_lid >= BAT_ADAPTER_MIN - 1e-6, f"battery: {ad_bat:.2f} to the adapter, {bat_lid:.2f} to the lid")
        rod = [b for b in moving if isinstance(b, Rod)][0]
        misalign = (occ_to_manifold(rod.solid(et=m.insert_shift, es0=-ROD_MISALIGN, es1=ROD_MISALIGN), 0.01, 0.1) ^ core_M).volume()
        sweeps = all_sweeps(m, order)
        boss_gap = min((gap(m.bosses(), sw), n) for n, sw in sweeps)
        check(boss_gap[0] > 0.2, f"magnet bosses {boss_gap[0]:.2f} from the {boss_gap[1]}")
    else:                                       # the adapter's up-move past the chin only
        print(f"[{name}] adapter's up-move (mesh) ...", flush=True)
        Ms = occ_to_manifold(adapter.solid(es0=2 * m.H), 0.01, 0.1)
        v = (Ms ^ core_M).volume()
        check(v < EPS_V, f"{name}: the adapter's up-move cuts {v:.3f} mm3 out of the shell")
        gaps = {("adapter", "shell"): Ms.min_gap(core_M, 10.0)}
    # ---- logo (skin; on the OCC shell: the slots do not reach it) ----
    print(f"[{name}] logo ...", flush=True)
    FL = front_logo_check(m, shell, lid, order, skin_only=not PEB_FULL_CHECKS)
    if PEB_FULL_CHECKS:
        PK = pocket_check(m, shell, lid, order, spots)
    P_ = m.pocket()

    # ---- test strip ----
    zs1 = m.SLOT_S[1] + OVAL_STRIP_ABOVE
    strip = m.shell("strip") & m.wt(box(-60, 60, -10, PEBBLE["STRIP_T"], -10, zs1))
    check(strip.is_valid and len(strip.solids()) == 1, "test strip is not one valid solid")
    strip_M = occ_to_manifold(strip, MESH_D, MESH_A) - cutter
    QS = mesh_quality(strip_M)
    check(QS["open"] == 0 and QS["nonman"] == 0 and QS["pieces"] == 1, f"pebble test strip mesh: {QS}")

    # ---- tipping (the shell's mass from the final mesh) ----
    if PEB_FULL_CHECKS:
        lb = lid.bounding_box()
        V_, F_ = manifold_arrays(shell_M)
        a_, b_, c__ = V_[F_[:, 0]], V_[F_[:, 1]], V_[F_[:, 2]]
        v6 = np.einsum("ij,ij->i", a_, np.cross(b_, c__))
        shell_v, shell_c = v6.sum() / 6, (v6[:, None] * (a_ + b_ + c__)).sum(0) / (4 * v6.sum())
        lid_v, lid_c = vol_props(lid, True)
        parts_m = [(shell_v / 1000 * DENSITY, Vector(*shell_c)), (lid_v / 1000 * DENSITY, lid_c),
                   (BOARD_G, Vector(0, *m.to_world((m.GLASS_T0 + m.BOARD_T1) / 2, m.PCB_S0 + hw.PCB_H / 2))),
                   (BATTERY_G, Vector(0, *m.to_world(sum(m.BAT_T) / 2, m.BAT_S0 + hw.BAT_H / 2)))]
        mass = sum(g for g, _ in parts_m)
        cm = sum((p * g for g, p in parts_m), Vector(0, 0, 0)) * (1 / mass)
        foot = [f for f in lid.faces() if f.geom_type == GeomType.PLANE and f.normal_at().Z < -1 + 1e-6][0].bounding_box()
        z_cm = cm.Z + LID_T
        ang_b, ang_f = math.degrees(math.atan2(foot.max.Y - cm.Y, z_cm)), math.degrees(math.atan2(cm.Y - foot.min.Y, z_cm))
        bbM = shell_M.bounding_box()
    bbM = shell_M.bounding_box()
    # ---- exports ----
    print(f"[{name}] exports ...", flush=True)
    for f in list(out.glob("*.stl")) + list(out.glob("*.step")):
        f.unlink()
    files = {}
    if PEB_FULL_CHECKS:
        export_part(lid, out, "lid", files, precise=True)
        st_shell = write_step(shell, out / "shell-noslots.step", precise=True)
    else:                                       # no read-back checks (round C)
        export_step(lid, str(out / "lid.step"))
        write_stl(lid, out / "lid.stl", fresh=True, fine=True)
        export_step(shell, str(out / "shell-noslots.step"))
    write_manifold_stl(shell_M, out / "shell.stl")
    write_manifold_stl(strip_M, out / "teststrip.stl")
    if PEB_FULL_CHECKS:
        mesh_files = {}
        for n_, M_ in (("shell", shell_M), ("teststrip", strip_M)):
            import pyvista as pv
            me = pv.read(str(out / f"{n_}.stl")).clean()
            err = abs(me.volume) / M_.volume() - 1
            check(me.n_open_edges == 0 and abs(err) < 1e-4, f"{n_}.stl: {me.n_open_edges} open edges, volume {err * 100:+.3f} %")
            mesh_files[n_] = (me.n_cells, err, (out / f"{n_}.stl").stat().st_size / 1024)

    final = [("lid", lid), ("adapter", ad), ("fork", fork)] + [(b.name, b.solid()) for b in moving if b.name != "battery"]
    for n, s_ in final:                         # (the battery: off the board with the keeper, not modelled)
        if n not in ("lid",):
            write_stl(s_, out / f"dummy-{n}.stl")
    export_step(fork, str(out / "fork.step"))
    Mfp = occ_to_manifold(m.fork_print(), 0.005, 0.05)      # welded, closed (the plain STL writer leaves split vertices)
    check(len(Mfp.decompose()) == 1, "fork-print: not one piece")
    write_manifold_stl(Mfp, out / "fork-print.stl")
    write_manifold_stl(ribs_M, out / "ribs.stl")
    write_manifold_stl(seat_M, out / "stops.stl")
    if PEB_FULL_CHECKS:
        stc, SS = make_stencils(FL["w"], STENCIL_STRIPS["front"], t=P_["st_t"])
        base = OUT_ROOT / "logo-stencils-pebble"
        st_ = write_step(stc, base.with_suffix(".step"))
        write_stl(stc, base.with_suffix(".stl"))
        ms_ = check_stl(stc, base.with_suffix(".stl"), bodies=len(stc.solids()))
        files["stencils"] = (st_, ms_)
        base.with_suffix(".txt").write_text(
            f"LOGO STENCILS, pebble C (= B): letters {SS['w']:g} x {SS['h']:.2f}; pocket {SS['pocket'][0]:.2f} x {SS['pocket'][1]:.2f} "
            f"R{STENCIL_R:g} behind the {m.logo_skin} skin, sides {LOGO_FLARE_DEG:g} deg, top and bottom straight; stencil "
            f"{SS['t']:.2f} thick (the pocket {P_['depth']:.2f} deep less {STENCIL_BACK}); strips " +
            ", ".join(f"{x:.2f}" for x in SS["strips"]) + "\n")

    z_aa = m.to_world(0, m.AA_SC)[1]
    write_manifold_stl(shell_M.trim_by_plane((-1, 0, 0), -m.tube_cc / 2), out / "section-x-shell.stl")
    write_manifold_stl(shell_M.trim_by_plane((0, 0, -1), -z_aa), out / "section-z-shell.stl")
    for tag_, cutter_ in (("x", box(m.tube_cc / 2, 300, -300, 300, -300, 300)), ("z", box(-300, 300, -300, 300, z_aa, 300))):
        for n, s_ in final:
            cs = s_ - cutter_
            if cs.volume > 0.01:
                write_stl(cs, out / f"section-{tag_}-{n}.stl")
    lw = m3.Manifold.cube((32, 12, 30)).translate((-16, -6, -1))
    write_manifold_stl(shell_M ^ lw.rotate((-m.tilt, 0, 0)), out / "section-l-shell.stl")
    import json
    fw = lambda x, s_: [x, *m.to_world(float(SP["f"](x)), s_)]
    (out / "focus.json").write_text(json.dumps({"slot_top": fw(m.tube_cc / 2, m.SLOT_S[1]), "slot_bottom": fw(m.tube_cc / 2, m.SLOT_S[0]),
                                                "H": m.H, "D": m.D, "logo": fw(0.0, FL["zc"]), "logo_normal": [0.0, -m.c, m.sn],
                                                "zmid": z_aa, "tilt": m.tilt}))

    if PEB_FULL_CHECKS:
        # ---- report ----
        def worst(move, only):
            c_ = [(g, n) for (mv, n), g in gaps.items() if mv == move and n.startswith(only)]
            return f"{min(c_)[0]:.2f}" if c_ else "n/a"
        LP = SP["lips"]
        xo = (SP["xc"] - SP["half"] - SP["a_in"], SP["xc"] + SP["half"] + SP["a_out"])
        xw_ = np.linspace(SP["xc"] - SP["half"], SP["xc"] + SP["half"], 401)
        endw = (float((m.FRONT - SP["f"](xw_)).min()), float(m.FRONT - SP["f"](SP["xc"])))
        horn = max(float(m.slot_surface(SP["xc"] + sg * (SP["half"] + 1e-6), sum(m.SLOT_S) / 2) - SP["f"](SP["xc"] + sg * (SP["half"] + 1e-6)))
                   for sg in (-1, 1))
        R = [f"DESK HOUSING smooth / pebble, round C (user, 2026-11-24: A's openings as printed, re-solved for tubes c-c {m.tube_cc}; flat "
             f"ends; no horn fix: the relief is to hide them; logo and the rest as B, skin {m.logo_skin}); round A: report-A.txt, "
             f"baseline 4.55: report-baseline-front4.55.txt",
             "[m] measured on the finished solids / meshes or their exact B-spline surfaces; [d] derived. Checks: land, overhangs, "
             "clearances, logo skin, insertion path, closed bodies (PEB_FULL_CHECKS off: the cavity walls, outline, straightness not "
             "re-measured)",
             "SLOTS ON THE MESH: the shell is built in OCC without the slots, meshed (deflection "
             f"{MESH_D} mm, {MESH_A} rad) and cut with the slots' mesh in manifold3d (as in B). "
             "shell-noslots.step has NO slots; shell.stl / teststrip.stl are the cut meshes",
             f"frame        world (x, y, z) = shell.stl's; body frame x = x, t = y cos{m.tilt:g} - z sin{m.tilt:g} (inwards from the face), "
             f"s = y sin{m.tilt:g} + z cos{m.tilt:g} (up the face); the face t = f(x) (the oval's bow, f(0) = 0), the flat inner face "
             f"t {m.FRONT:.3f}; slots s {m.SLOT_S[0]:.2f}..{m.SLOT_S[1]:.2f}, x +-({SP['xc'] - SP['half']:.2f}..{SP['xc'] + SP['half']:.2f}); "
             f"openings on the face x +-({xo[0]:.2f}..{xo[1]:.2f})",
             f"outer        [m] {bbM[3] - bbM[0]:.2f} x {bbM[4] - bbM[1]:.2f} x {bbM[5] - bbM[2] + LID_T:.2f} (with the lid); the front's bow: "
             f"the oval's curve, fading with the sketch's own bow (A's 0.02..0.035 dents at z ~11 / ~92: <= 0.002); flat inner face "
             f"at t {m.FRONT:.3f}",
             f"slots        [d] round A's rule at c-c {m.tube_cc} (x +-{SP['xc']}): {SLOT_W} x {SLOT_L:.2f} through, s "
             f"{m.SLOT_S[0]:.2f}..{m.SLOT_S[1]:.2f}; {m.RIM} land; round lips, an arc vertical at the land, its radius solved for each "
             f"side (inner r {LP['in']['r']:.3f}, outer r {LP['out']['r']:.3f}), ended {PEBBLE['LIP_SHORT_DEG']:g} deg short of "
             f"tangency and run out along its tangent: on the face inner {SP['a_in']:.2f}, outer {SP['a_out']:.2f} wide; the "
             f"openings {opening:.2f} wide, {gap_open:.2f} apart (the bridge on the face); ends flat, square to the face, from the "
             f"inner face out to the face: {endw[1]:.2f} deep on the slot's axis, {endw[0]:.2f} at its outer edge (the tubes butt "
             f"against them); the horns as in A: where each lip stops at the end, the end plane leaves the lip's crescent, up to "
             f"{horn:.2f} deep at the land. Cutter: A's profile ({m._cache['slotmesh_n']} nodes, {PEBBLE['LIP_ARC_N']} chords per arc) "
             f"extruded exactly S0..S1 (manifold3d), the right slot's mirrored. Simplified: nothing",
             f"  land       [m, mesh] the lands' walls {lw0:.4f}..{lw1:.4f} apart at the inner face; {ld:.3f}..{ld1:.3f} deep by design; "
             f"on the final mesh each wall runs straight {lr0:.3f}..{lr1:.3f} from the inner face (to the lip's first node: "
             f"the lip starts vertical, tangent to the land, and manifold drops the land's top vertex); rods in "
             f"the slots [m, mesh] clear: " + ", ".join(f"{v:.3f} (tape {t})" for t, v in rod_clr.items()),
             f"  nose       [d] gap between the openings on the face {gap_open:.2f}; reads ~{nose_reads:.1f} wide (< 0.3 below the face); "
             f"rods' crown {proud[hw.TAPE[0]]:.2f}..{proud[hw.TAPE[1]]:.2f} proud of the face",
             f"overhangs    [m] outside {ov_out:.2f}, cavity {ov_in:.2f} (B-splines); slots (final mesh: lips, lands, the bottom ends) "
             f"{ov_slot:.2f} at (x, s) {ov_slot_p} deg from vertical printed standing; named exception: the top end walls (the plane "
             f"s {m.SLOT_S[1]:.2f}, the lips' crescents included) {ov_top:.2f} deg, |x| {top_x[0]:.2f}..{top_x[1]:.2f}, t "
             f"{top_t[0]:.2f}..{top_t[1]:.2f}, {top_a:.1f} mm2 both: tree supports from inside, as in A; ceiling bridge {bridge:.2f}",
             f"walls        {wtxt}",
             f"insertion    board + rods up at {m.insert_shift:.2f} behind their seat (the chin's inner rim edge, [d] {CV['need'][0]:.2f} to "
             f"touch + {INSERT_CLR}), then forward; [m, mesh] up: rods {worst('up', 'rod')}, glass {worst('up', 'glass')}, board "
             f"{worst('up', 'board')}, plugs {worst('up', 'plug')}, buttons {worst('up', 'button')}; forward: rods in the slots "
             f"{worst('forward', 'rod')} ({ROD_MISALIGN} off along the face cuts {misalign:.2f} mm3)",
             f"  battery    [m, mesh] up {gaps[('bat-up', 'battery')]:.2f}, forward {gaps[('bat-fwd', 'battery')]:.2f}; to the board / plugs "
             f"{gaps[('bat-up', 'battery-board')]:.2f}; to the adapter {ad_bat:.2f}, to the lid {bat_lid:.2f}",
             f"  adapter    [m, mesh] its sweep to the shell {gaps[('adapter', 'shell')]:.2f} (A: 0.08), seated {gaps[('seated', 'adapter')]:.2f}; "
             f"to the board {gaps[('adapter', 'board')]:.2f}; lid move: shell {gaps[('lid', 'shell')]:.2f}, adapter {gaps[('lid', 'adapter')]:.2f}; "
             f"bosses {boss_gap[0]:.2f} from the nearest sweep; cable to the notch: shell {cab['shell']:.2f}, battery {cab['battery']:.2f}",
             f"logo         [d] {FL['w']:g} x {FL['h']:.2f} letters (the largest <= {PEBBLE['LOGO_W_MAX']:g} that leaves a {PEBBLE['STENCIL_MIN_T']} "
             f"stencil), s {FL['z'][0]:.2f}..{FL['z'][1]:.2f}; pocket {P_['pw']:.2f} x {P_['ph']:.2f} R{STENCIL_R:g} (sides {LOGO_FLARE_DEG:g} deg, "
             f"top and bottom straight, the top a short bridge), floor at t {P_['floor']:.3f} (set from the front's nearest point in 3D "
             f"over and round its outline), {P_['depth']:.2f} deep; [m] skin "
             f"{FL['skin'][0]:.3f} at its thinnest, {FL['skin'][1]:.3f} at the pocket's centre; stencil {P_['st_t']:.2f} thick, "
             f"{PK['st_gap']:.2f} to the pocket's walls seated, in along its axis without touching; pocket to the glass {PK['glass']:.2f}, "
             f"to the slots' cut (bounding box) {PK['slots']:.2f}, the rim {PK['rim']:.2f}",
             f"magnets      [m] wall round the holes (rim / lid) " + ", ".join(f"{ms:.2f} / {ml:.2f}" for ms, ml in meats),
             f"mesh         [m] shell: {Q['pieces']} piece, {Q['open']} open / {Q['nonman']} non-manifold edges, {Q['tris']} triangles, "
             f"{Q['tiny']} under 1e-6 mm2, {Q['slivers']} slivers (inscribed radius < 1e-4; least {Q['min_rin']:.2e}); test strip "
             f"{QS['pieces']} piece, {QS['open']} / {QS['nonman']}, {QS['slivers']} slivers",
             f"volumes      [m] shell {shell_v / 1000:.1f}, lid {lid_v / 1000:.1f} cm3 ({(shell_v + lid_v) / 1000 * DENSITY:.0f} g); with "
             f"board + battery {mass:.0f} g, tips at {ang_b:.1f} back / {ang_f:.1f} forward"]
        R += file_lines(files)
        R.append(f"  shell-noslots STEP 1 solid, {st_shell['faces']} faces (no slots), {st_shell['kb']:.0f} kB")
        for n_, (nt, err, kb) in mesh_files.items():
            R.append(f"  {n_:<16} STL (cut mesh) closed, {nt} triangles, volume vs the manifold {err * 100:+.4f} %, {kb:.0f} kB")
        R += ["", "clearances along the insertion path, mm, on the final mesh (0.00 = it ends seated there):", "  body                up   forward"]
        for b in moving:
            if ("up", b.name) in gaps:
                R.append(f"  {b.name:<16} {gaps[('up', b.name)]:6.2f} {gaps.get(('forward', b.name), math.nan):9.2f}")
            elif ("bat-up", b.name) in gaps:
                R.append(f"  {b.name:<16} {gaps[('bat-up', b.name)]:6.2f} {gaps[('bat-fwd', b.name)]:9.2f}   (its own moves)")
    else:
        LP = SP["lips"]
        xo = (SP["xc"] - SP["half"] - SP["a_in"], SP["xc"] + SP["half"] + SP["a_out"])
        xw_ = np.linspace(SP["xc"] - SP["half"], SP["xc"] + SP["half"], 401)
        endw = (float((m.FRONT - SP["f"](xw_)).min()), float(m.FRONT - SP["f"](SP["xc"])))
        horn = max(float(m.slot_surface(SP["xc"] + sg * (SP["half"] + 1e-6), sum(m.SLOT_S) / 2) - SP["f"](SP["xc"] + sg * (SP["half"] + 1e-6)))
                   for sg in (-1, 1))
        R = [f"DESK HOUSING smooth / pebble, round D (2026-11-26) = round C (user, 2026-11-24: A's openings as printed, re-solved for "
             f"tubes c-c {m.tube_cc}; flat ends; no horn fix, the relief is to hide them; logo and the rest as B) + the board keeper",
             "[m] measured on the final mesh / exact surfaces, [d] design. Checks (round C, user: four only): the shell mesh closed, "
             "overhangs outside the supported top end walls, seated clearances (rods, the adapter's up-move), the logo's thinnest skin",
             f"frame        shell.stl's world (x, y, z); body frame x = x, t = y cos{m.tilt:g} - z sin{m.tilt:g} (inwards from the face), "
             f"s = y sin{m.tilt:g} + z cos{m.tilt:g} (up the face); the face t = f(x) (the oval's bow), the flat inner face t {m.FRONT:.3f}",
             f"slots        [d] {SLOT_W} x {SLOT_L:.2f} through at x +-{SP['xc']} (c-c {m.tube_cc}), s {m.SLOT_S[0]:.2f}..{m.SLOT_S[1]:.2f}, "
             f"{m.RIM} land; A's round lips (arc r {LP['in']['r']:.2f} inner, {LP['out']['r']:.2f} outer, {PEBBLE['LIP_SHORT_DEG']:g} deg short of "
             f"tangency, then its tangent): on the face {SP['a_in']:.2f} inner, {SP['a_out']:.2f} outer; openings x +-({xo[0]:.2f}..{xo[1]:.2f}), "
             f"{opening:.2f} wide, bridge on the face {gap_open:.2f}; rods' crown {proud[hw.TAPE[0]]:.2f}..{proud[hw.TAPE[1]]:.2f} proud of the face; "
             f"ends flat, square to the face, full depth: {endw[1]:.2f} on the slot's axis, {endw[0]:.2f} at its outer edge; horns as A "
             f"(the lips' crescents in the end planes, up to {horn:.2f} deep at the land). Cut on the mesh (manifold3d): A's profile "
             f"extruded S0..S1, mirrored; shell-noslots.step has NO slots",
             f"mesh         [m] shell.stl {Q['pieces']} piece, {Q['open']} open / {Q['nonman']} non-manifold edges, {Q['tris']} triangles",
             f"overhangs    [m] outside {ov_out:.2f}, cavity {ov_in:.2f}, slots {ov_slot:.2f} at (x, s) {ov_slot_p} (limit {PEB_OVERHANG_MAX:g}); "
             f"supported (named exception): the top end walls, the plane s {m.SLOT_S[1]:.2f}, {ov_top:.1f} deg, |x| {top_x[0]:.2f}..{top_x[1]:.2f}, "
             f"t {top_t[0]:.2f}..{top_t[1]:.2f} ({top_a:.1f} mm2 both): tree supports from inside, as in A; ceiling bridge {bridge:.2f}",
             f"clearances   [m] seated rods in the slots " + ", ".join(f"{v:.3f} (tape {t})" for t, v in rod_clr.items()) +
             f"; the adapter's up-move past the chin {gaps[('adapter', 'shell')]:.3f}",
             f"logo         [d] {FL['w']:g} x {FL['h']:.2f} letters, pocket floor t {P_['floor']:.3f}; [m] skin {FL['skin'][0]:.3f} at its "
             f"thinnest, {FL['skin'][1]:.3f} at the pocket's centre; stencil {P_['st_t']:.2f} (as B: logo-stencils-pebble.*)",
             f"files        out-smooth/pebble: shell.stl, teststrip.stl (cut meshes), lid.step / .stl, shell-noslots.step (no slots, no "
             f"ribs), sections, dummies"]
    K = KEEPER
    R.append(
        f"keeper       round E (user, 2026-11-27; D printed: it held, but the one-prong fork snapped off its narrow upper rib): the board "
        f"held against the front wall by a printed fork behind its back plate (plate's back face at t {m.BOARD_T1:.2f}: {K['BOARD_T']} "
        f"behind the glass front, measured) and {len(rib_info)} ribs on the side walls, behind the pads. The fork is a frame open on "
        f"the plug side (x {KQ['plug_sx']:+d}): [d] {K['FORK_T']} thick at t {KQ['fork_t'][0]:.2f}..{KQ['fork_t'][1]:.2f}: two feet |x| "
        f"{K['SLOT_X']}..{K['EAR_X']} and a lower block across them s {KQ['low_s0']:.2f}..{K['EAR_S1']:g} (above the adapter), the button "
        f"side's prong |x| {K['SLOT_X']}..{K['PRONG_X']}, widened to the wall above s {K['HEAD_S0']:g}, a top bar s {K['BAR_S0']:g}.."
        f"{K['TOP_S']:g} from wall to wall, foot {K['LID_CLR']} above the lid; pads {K['PAD']:g} x {K['PAD']:g} over the plate's four "
        f"screws (x, s): " + ", ".join(f"{sx * hw.NUT_DX / 2:+.2f}, {s:.2f}" for sx, s in KQ["pads"]) + f"; {K['PAD_H']} proud (+"
        f"{K['PAD_OVER']} in fork-print.stl: sand to fit). Ribs {K['RIB_T']} thick at t {KQ['rib_t'][0]:.2f}..{KQ['rib_t'][1]:.2f} (x of the "
        f"inner edge, s; the 45 deg corbel below ends at s): " +
        "; ".join(f"{sx * x_in:+.1f}, {s_a:g}..{s_b:g}, {s_c:.1f}" for sx, x_in, s_a, s_b, s_c, _ in rib_info) +
        f". They reach over the board: it slides in along the front wall, also with its rods on (user), so the back-shifted up move "
        f"({m.insert_shift:.2f}) is not swept against them. [m, mesh] the ribs add {rib_vol:.0f} mm3 in {len(rib_info)} pieces, each "
        f"inside the cavity, {K['RIB_EMBED']} in the wall; their steepest face {ov_rib:.1f} deg from vertical; seated, the board, plugs, "
        f"buttons and adapter stay {rib_gap[0]:.2f} from them ({rib_gap[1]}); the fork, seated and on its way up, clear of shell, "
        f"board, RTC plug and buttons: {FK['wall']:.2f} to the walls, {FK['adapter']:.2f} to the adapter, {FK['lid']:.2f} above the lid; "
        f"it bears on the ribs (contact in their front plane) over " + ", ".join(f"{a:g}" for a in FK["bear"]) +
        f" mm2 (at least {FK['side']:.1f} mm2 with the fork pushed sideways to a wall), its pads on the plate over the screws. "
        f"The glass still sits on the {hw.GASKET} foam strips at its short ends (hw.GASKET; stuck to the wall only, or the liner "
        f"left on towards the glass): without them the board sits {hw.GASKET} further forward, the pads do not reach and the adapter "
        f"meets the chin. ASSUMED plugs: UART / J5 / I2C {K['PLUG_IN']:g} in from the edge, plug + wire bend {K['PLUG_UP']:g} behind "
        f"the plate; RTC {hw.PLUG_PROUD:g} beyond the edge. Order: board (UART / J5 / I2C empty: the top bar passes over them), "
        f"fork, adapter, then the battery's plug and any upward plugs through the fork's open side, lid. The battery is off the "
        f"board (Kapton to the back wall): not modelled, no dummy. Files: fork.step (seated), fork-print.stl (flat on its back, "
        f"pads up), ribs.stl (for the relief shells)")
    Q_ = SEAT
    R.append(
        f"pocket stops round E (user, 2026-11-27): the rods are not glued to the glass, so the shell holds the board along the face and "
        f"sideways by the glass, in its pocket in the front wall (floor t {m.FRONT}). [d] top: a wedge across |x| {SQ['xp']:.2f}, "
        f"leaving the floor {Q_['TOP_CLR']} above the glass's top (s {SQ['top'][0]:.2f}), {Q_['SLOPE']:g} deg to the face up to "
        f"{Q_['TOP_D']} deep, top at s {SQ['top'][1]:.2f}; sides: rails |x| {SQ['xp']:.2f}..{SQ['rail_x1']:.2f} ({Q_['SIDE_CLR']} "
        f"from the glass each side; the pocket's own steps: 0.3), {Q_['RAIL_H']} over the floor (t {SQ['rail_t']:.2f}), s "
        f"{Q_['RAIL_S'][0]:g}..{Q_['RAIL_S'][1]:g}, {Q_['RAIL_LEAD']} lead-in; bottom: corners |x| {Q_['BOT_X0']:g}..{SQ['xp']:.2f}, "
        f"flat top {Q_['BOT_CLR']} under the glass (s {SQ['bot'][1]:.2f}), {Q_['BOT_D']} over the floor (t {SQ['bot_t']:.2f}). "
        f"[m, mesh] they add {seat_vol:.0f} mm3, all inside the outer skin, the shell one piece; their steepest face {ov_seat:.1f} deg "
        f"from vertical; seated: glass {SG['glass']:.2f}, without the foam strips (as the user assembles: 0.5 further forward) "
        f"{SG['glass, no strips']:.2f}, board {SG['board']:.2f} / {SG['board, no strips']:.2f}, the nearest other part "
        f"{min((v, k) for k, v in SG.items() if not k.startswith(('glass', 'board')))[0]:.2f} "
        f"({min((v, k) for k, v in SG.items() if not k.startswith(('glass', 'board')))[1]}). With the strips the glass can rise "
        f"{hw.GASKET / math.tan(math.radians(Q_['SLOPE'])):.2f} more before it meets the wedge. The fork's pads are printed +"
        f"{KEEPER['PAD_OVER']} for the same reason (sand to fit). NOT MODELLED: the board without the strips (the model keeps "
        f"hw.GASKET; the adapter dummy is the old 90 deg adapter, the user now has a short bendable extension). File: stops.stl")
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


def make_stencils(w, strips, t=None):
    """Logo stencils for the glow-through pocket: stencil_block (the pocket's floor outline less the clearances, its two
    vertical sides sloped as the pocket's: printed flat they widen upwards, a LOGO_FLARE_DEG overhang), the letters as
    straight holes, STENCIL_T thick; mirrored so the face that meets the skin lies on the bed. One per strip width in
    `strips` (None: the logo as designed; wider strips shrink the letters), in a column."""
    from build123d import offset
    h = hw.LETTERS_ASPECT * w
    s0 = hw.STRIP_PER_MM * w
    pw, ph = w + 2 * STENCIL_MARGIN, h + 2 * STENCIL_MARGIN
    sw, sh = pw - 2 * STENCIL_CLR, ph - STENCIL_CLR - STENCIL_CLR_TOP
    t = STENCIL_T if t is None else t
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
    """Stencils for the small front logo (upright, oval) and the tilt15's side logo (the pebble's: build_pebble)."""
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
    names = args or [n for n in VARIANTS if n != "pebble"]     # pebble: WIP, only on request (smooth.py pebble)
    for n in names:
        if n in ("inlays", "stencils"):
            continue
        build_oval(order) if n == "oval" else build_pebble(order) if n == "pebble" else build(n, order)
    if LOGO_STYLE == "stencil":
        build_stencils()
    elif "inlays" in names or any(VARIANTS[n]["LOGO_MODE"] == "front" for n in names if n in VARIANTS):
        build_inlays()
