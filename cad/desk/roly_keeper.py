#!/usr/bin/env python3
"""Roly-poly board keeper: the pebble's round E keeper (smooth.py's KEEPER / SEAT) carried over to round 8's body.

A post-step on the mesh (manifold3d), as the pebble adds its ribs: rolypoly.py's out-rolypoly/body.stl is read, never
rewritten; everything here goes to out-rolypoly/keeper/. No shell rebuild.

  body.stl        round 8's body + two upper ribs, two fins behind the cell, the glass stops
  ribs.stl, stops.stl   the added material alone (for the views)
  fork.stl        the frame fork, seated (world frame)
  fork-print.stl  the fork as printed: flat on its back face, pads up, pads PAD_OVER proud
  fork-print-plate.stl  the same turned 90 deg, for the plates
  slot-top-enforcer.stl  support enforcer over the two slots' top end walls (body.stl's frame), for the plates
  keeper-views.png, report.txt

What differs from the pebble (user, 2026-11-27): the cell (measured 66.8 x 36 x 9.75) sits on its long edge right behind
the fork and fills the cavity's width there, so the pebble's two lower side ribs have no room. The fork's lower block is
backed by the cell, the cell by two fins that stand on the seam ring in front of the back wall. The fork cannot drop:
its lower block is 0.3 above the USB head, which goes in after it.

Frame: the board frame of rolypoly.py (x, y back, z up the face; the world is that tilted TILT back about the pivot).
u = x - XOFF, the button side at -u. Checks are the lean set: closed one-piece mesh, overhangs of the added faces,
seated clearances, nothing near the logo.

  ~/.venvs/cad/bin/python cad/desk/roly_keeper.py            build, check, write, views (xvfb-run -a for the views)
"""
import sys, math, pathlib, struct
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np
import manifold3d as m3
import rolypoly as rp
import housing as hw

SRC = HERE / "out-rolypoly"
OUT = SRC / "keeper"
X0 = rp.XOFF
BTN = hw.BTN_SIDE                                          # -1: the buttons at -u, the sockets at +u

K = dict(BOARD_T=9.15,                                     # glass front .. the plate's back face, measured (pebble, 2026-11-26)
         PAD=5.0, PAD_H=1.5, PAD_LEAD=0.6,                 # as the pebble: pads over the four screws; the fork's face PAD_H
                                                           # behind the model's plate (which sits on 0.5 foam strips)
         PAD_FWD=hw.GASKET,                                # the board goes in WITHOUT the strips, so the plate is this much
                                                           # further forward: the pads reach it there (2.0 long)
         PAD_OVER=1.0,                                     # printed this much proud, sanded to fit. Grey print 2026-11-28
                                                           # (pads 2.2 as printed): the fork was loose (user: "increase the
                                                           # feet further"); now 3.0 as printed
         FORK_T=2.5, RIB_T=3.5,
         SLOT_U=8.5, PRONG_U=21.0, EAR_U=24.0,             # centre slot's half width (USB head +-6), the prong's and the feet's outer edge
         LOW_Z=(0.3, 13.2),                                # lower block: above the PCB bottom (= the USB head's top) .. its top
         HEAD_Z=63.2, BAR_Z=71.2, TOP_Z=78.5,              # above the PCB bottom: the prong widens to the wall; the bar; the fork's top
         WALL_GAP=0.5,                                     # head and bar to the cavity wall
         FOOT_CLR=0.3,                                     # feet above the seam plane
         LEAD=0.8,                                         # lead-in on the bar's top back edge (it runs up under the ribs)
         RIB_HI=(11.0, 67.2, 79.2),                        # upper rib, button side: inner edge |u|, z range above the PCB bottom
         RIB_HI_PLUG=(13.0, 78.7, 79.2),                   # upper rib, plug side: a wedge, the RTC socket stays in view
         RIB_EMBED=0.8, RIB_STEP=0.5,
         CELL=(66.8, 36.0, 9.75),                          # MEASURED (user, 2026-11-27): along x, up, thick ("36 at the widest point")
         CELL_Z0=1.0,                                      # its bottom above the PCB bottom (rolypoly.py's BAT_HEAD_MIN: over the USB head)
         FIN_X=(-9.9, 7.75), FIN_W=3.0,                    # fins behind the cell: world x centres, thickness. The left one
                                                           # stands between the pin boss at x -14.5 (to x -11.9) and the USB
                                                           # slot; the right one beyond the slot, under the trim spot at x 13
                                                           # (it steps down FIN_UNDER below and in front of a spot)
         FIN_UNDER=0.5,
         FIN_GAP=0.3, FIN_TOP=14.0,                        # cell's back to the fins (was 0.6 for foam or tape: the fork's lower end
                                                           # has no ribs, the cell and the fins stop it; user 2026-11-28: no
                                                           # tape should be needed); their top above the PCB bottom
         FIN_FOOT=2.5,                                     # below the cell the fins' front edge recedes 45 deg: room for the USB head
         FIN_CLR=0.3,                                      # fins to the trim spots and to the seam's holes, at least
         PLUG_IN=5.0, PLUG_UP=4.0,                         # upward sockets (UART, J5, I2C), as the pebble: ASSUMED
         JST_Z={"uart": 22.45, "j5": 39.42, "i2c": 56.39, "rtc": 67.5}, RTC_LEN=4.4,
         USB_SLOT=(11.3, 5.9, 2.5, 0.0),                   # USB-C opening in the body's back wall, all in the body (which will
                                                           # be black): width, height, lower edge above the seam, world x
                                                           # centre; level, closed all round. User, 2026-11-28: the extension's
                                                           # socket end, 11 x 5.5, sits IN it: 0.15 a side, 0.4 in height (its
                                                           # roof is a bridge, printed without support)
         USB_R=1.0,                                        # its corners
         NOTCH_X=(-8.3, -1.7),                             # the old cable notch (5.6 round at x -5, split by the seam): filled,
                                                           # in the body and in the cup, from the wall beside it
         GAP_MIN=0.1)                                      # seated parts to the added material, at least (the stops are 0.15 from the glass)

SEAT = dict(SIDE_CLR=0.15, RAIL_H=3.0, RAIL_W=2.25, RAIL_LEAD=0.6, RAIL_Z=(-0.925, 1.475),   # rails: below the glass bottom / above its top
            TOP_CLR=0.3, TOP_D=2.6, TOP_FLAT=1.0, BOT_CLR=0.325, BOT_D=2.6, BOT_U0=10.0, BOT_T0=0.2,
            SLOPE=29.5,                                    # under-slopes to the face: + TILT = 37.5 deg from vertical as printed
            EMBED=1.0, BOT_EMBED=2.0, RAIL_TOE=3.5)                      # into the wall; the corners more (below the land the wall steps 1.3 forward)
OVERHANG_MAX = 45.0

PCB_Z0 = rp.PCB_Z0
YB = rp.Y_GLASS0 + K["BOARD_T"]                            # the plate's back face (the model's seat: on the 0.5 strips)
YP = YB - K["PAD_FWD"]                                     # the same as assembled, without the strips: the pads' tips
T0, T1 = YB + K["PAD_H"], YB + K["PAD_H"] + K["FORK_T"]    # the fork
R0, R1 = T1, T1 + K["RIB_T"]                               # the ribs
GLASS_Z = (PCB_Z0 + 1.125, PCB_Z0 + 1.125 + hw.GLASS_H)
SCREWS = [(su * hw.NUT_DX / 2, PCB_Z0 + hw.NUT_INSET + k * hw.NUT_DZ) for k in (0, 1) for su in (-1, 1)]   # (u, z)


def check(ok, msg):
    if not ok:
        raise SystemExit("CHECK FAILED: " + msg)


# ---- frames, mesh helpers --------------------------------------------------------------------------------------------------
_o = rp.pts_world(np.zeros((1, 3)))[0]
T_WB = np.c_[np.array([rp.pts_world(np.eye(3)[i:i + 1])[0] - _o for i in range(3)]).T, _o]      # board -> world (3 x 4)
_o = rp.pts_board(np.zeros((1, 3)))[0]
T_BW = np.c_[np.array([rp.pts_board(np.eye(3)[i:i + 1])[0] - _o for i in range(3)]).T, _o]      # world -> board


def world(M):
    return M.transform(T_WB.tolist())


def load(path):
    import pyvista as pv
    m = pv.read(str(path)).clean(tolerance=1e-7).triangulate()
    M = m3.Manifold(m3.Mesh(np.asarray(m.points, np.float32), m.faces.reshape(-1, 4)[:, 1:].astype(np.uint32)))
    check(M.status() == m3.Error.NoError and M.volume() > 0, f"{path.name}: not a closed mesh ({M.status()})")
    return M


def tris(M):
    me = M.to_mesh()
    return np.asarray(me.vert_properties, float)[:, :3], np.asarray(me.tri_verts, np.int64), me


def write_stl(M, path):
    V, F, _ = tris(M)
    P = V[F]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1), 1e-30)[:, None]
    rec = np.zeros(len(F), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, P
    with open(path, "wb") as f:
        f.write(b"roly-poly keeper".ljust(80, b" ") + struct.pack("<I", len(F)))
        rec.tofile(f)


def ccw(P):
    P = np.asarray(P, float)
    a = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    return (P if a > 0 else P[::-1]).tolist()


def prism_xz(P, y0, y1):                                   # (x, z) profile along y
    return m3.Manifold.extrude(m3.CrossSection([ccw(P)]), y1 - y0).transform([[1, 0, 0, 0], [0, 0, -1, y1], [0, 1, 0, 0]])


def prism_yz(P, x0, x1):                                   # (y, z) profile along x
    return m3.Manifold.extrude(m3.CrossSection([ccw(P)]), x1 - x0).transform([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0]])


def prism_xy(P, z0, z1):                                   # (x, y) profile along z
    return m3.Manifold.extrude(m3.CrossSection([ccw(P)]), z1 - z0).translate((0, 0, z0))


def box(x0, x1, y0, y1, z0, z1):
    return m3.Manifold.cube((abs(x1 - x0), abs(y1 - y0), abs(z1 - z0))).translate((min(x0, x1), min(y0, y1), min(z0, z1)))


def ubox(u0, u1, y0, y1, z0, z1):
    return box(X0 + u0, X0 + u1, y0, y1, z0, z1)


def union(parts):
    M = parts[0]
    for p in parts[1:]:
        M = M + p
    return M


def above_seam(M, clr=0.0):
    """M (board frame) cut along the seam plane (world z = SEAM + clr): what is above stays."""
    n = T_BW[:, :3] @ np.array([0.0, 0.0, 1.0])            # the world's up, in the board frame
    p0 = rp.pts_board(np.array([[0.0, 0.0, rp.SEAM + clr]]))[0]
    return M.trim_by_plane(n.tolist(), float(n @ p0))


class Walls:
    """The cavity wall read off the body mesh (board frame), by slices across z."""

    def __init__(self, body_b):
        self.M, self._s = body_b, {}

    def polys(self, z):
        z = round(float(z), 4)
        if z not in self._s:
            self._s[z] = [np.asarray(P) for P in self.M.slice(z).to_polygons()]
        return self._s[z]

    def _cross(self, z, axis, v):
        out = []
        for P in self.polys(z):
            Q = np.roll(P, -1, axis=0)
            k = (P[:, axis] - v) * (Q[:, axis] - v) < 0
            o = 1 - axis
            out += (P[k, o] + (v - P[k, axis]) * (Q[k, o] - P[k, o]) / (Q[k, axis] - P[k, axis])).tolist()
        return np.sort(out)

    def side_u(self, su, z, y):
        """Inner wall on the side su at height z and depth y, as |u|."""
        u = su * (self._cross(z, 1, y) - X0)
        u = u[u > 0]
        check(len(u) >= 2, f"wall at z {z:.2f}, y {y:.2f}, side {su:+d}: {len(u)} crossings")
        return float(u.min())

    def side_u_band(self, su, z, y0, y1, n=3):
        return min(self.side_u(su, z, y) for y in np.linspace(y0, y1, n))

    def back_y(self, x, z):
        """Inner back wall at x, z."""
        y = self._cross(z, 0, x)
        y = y[y > 5.0]
        check(len(y) >= 2, f"back wall at x {x:.2f}, z {z:.2f}: {len(y)} crossings")
        return float(y.min())


# ---- the parts (board frame) -----------------------------------------------------------------------------------------------
def stops():
    """The glass stops on the front wall (smooth.py's seat_mesh): a top wedge, two side rails, two bottom corners.
    The corners start at the seam ring (the print bed), so they have no underside but the slope."""
    Q, F = SEAT, rp.Y_LAND
    tan, e = math.tan(math.radians(Q["SLOPE"])), Q["EMBED"]
    up = hw.GLASS_W / 2 + Q["SIDE_CLR"]
    o = 0.5                                                # wedge and corners run this far into the rails

    def under(M, y0, z_a):                                 # keep y - y0 <= (z - z_a) tan
        k = math.hypot(1.0, tan)
        return M.trim_by_plane((0.0, -1.0 / k, tan / k), (tan * z_a - y0) / k)

    z0 = GLASS_Z[1] + Q["TOP_CLR"]
    z1 = z0 + Q["TOP_D"] / tan
    top = prism_yz([(F - e, z0), (F, z0), (F + Q["TOP_D"], z1), (F + Q["TOP_D"], z1 + Q["TOP_FLAT"]), (F - e, z1 + Q["TOP_FLAT"])],
                   X0 - up - o, X0 + up + o)
    h, L, u1 = Q["RAIL_H"], Q["RAIL_LEAD"], up + Q["RAIL_W"]
    rz = (GLASS_Z[0] + Q["RAIL_Z"][0], GLASS_Z[1] + Q["RAIL_Z"][1])
    parts, names = [top], ["top wedge"]
    for su in (-1, 1):
        prof = lambda emb: [(X0 + su * a, b) for a, b in ((up, F - emb), (u1, F - emb), (u1, F + h), (up + L, F + h), (up, F + h - L))]
        # the lower end runs on down into the wall (deeper there: beside and below the land the wall steps forward), so
        # the under-slope leaves no flat underside
        rail = prism_xy(prof(e), *rz) + prism_xy(prof(Q["BOT_EMBED"]), rz[0] - Q["RAIL_TOE"], rz[0] + 0.5)
        parts.append(under(rail, F, rz[0]))
        names.append("rail")
    zb = GLASS_Z[0] - Q["BOT_CLR"]
    z_a = zb - (Q["BOT_D"] + Q["BOT_T0"]) / tan
    eb = Q["BOT_EMBED"]
    for su in (-1, 1):
        a, b = sorted((X0 + su * Q["BOT_U0"], X0 + su * (up + o)))
        c = prism_yz([(F - eb, z_a - 6.0), (F + Q["BOT_D"], z_a - 6.0), (F + Q["BOT_D"], zb), (F - eb, zb)], a, b)
        parts.append(above_seam(under(c, F - Q["BOT_T0"], z_a)))
        names.append("bottom corner")
    for n_, P_ in zip(names, parts):
        check(P_.status() == m3.Error.NoError and P_.volume() > 1.0 and len(P_.decompose()) == 1, f"stop {n_}: {P_.status()}, {P_.volume():.2f} mm3")
    return union(parts), dict(up=up, top=(z0, z1 + Q["TOP_FLAT"]), rail_y=F + h, rail_z=rz, bot=(z_a, zb), bot_y=F + Q["BOT_D"],
                              parts=list(zip(names, parts)))


def ribs(W):
    """The two upper ribs (smooth.py's rib_mesh): prisms along y behind the fork; inner edge |u| = u_in from z_a to z_b,
    square on top, a 45 deg corbel below; the wall side RIB_EMBED inside the wall read off the mesh at three depths."""
    out, info = [], []
    for su, (u_in, za, zb) in ((BTN, K["RIB_HI"]), (-BTN, K["RIB_HI_PLUG"])):
        za, zb = PCB_Z0 + za, PCB_Z0 + zb
        wall = lambda z: max(W.side_u(su, z, y) for y in (R0, (R0 + R1) / 2, R1))
        emb = lambda z: u_in + (za - z) - (wall(z) + K["RIB_EMBED"])          # > 0: the corbel is that deep in the wall
        lo = za - K["RIB_STEP"]
        while emb(lo) < 0:
            lo -= K["RIB_STEP"]
        hi = lo + K["RIB_STEP"]
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if emb(mid) >= 0 else (lo, mid)
        zc = 0.5 * (lo + hi)
        side = [(float(z), wall(float(z)) + K["RIB_EMBED"]) for z in np.arange(zb, zc, -K["RIB_STEP"])]
        P = [(za, u_in), (zb, u_in)] + side + [(zc, u_in + (za - zc))]                          # (z, |u|)
        R = prism_xz([(X0 + su * u, z) for z, u in P], R0, R1)
        check(R.status() == m3.Error.NoError and R.volume() > 0 and len(R.decompose()) == 1, f"rib {su:+d}: {R.status()}")
        info.append(dict(su=su, u_in=u_in, z=(za, zb), foot=zc, vol=R.volume()))
        out.append(R)
    return union(out), info


def cell_seat(W):
    """The cell right behind the fork, centred between the walls over its own height and depth. Returns (box, numbers)."""
    L, H, T = K["CELL"]
    z0 = PCB_Z0 + K["CELL_Z0"]
    lo = max(W.side_u_band(-1, z, R0, R0 + T, 5) * -1 for z in np.arange(z0, z0 + H + 0.01, 1.0))      # x - X0, button side
    hi = min(W.side_u_band(1, z, R0, R0 + T, 5) for z in np.arange(z0, z0 + H + 0.01, 1.0))
    c = X0 + 0.5 * (lo + hi)
    return box(c - L / 2, c + L / 2, R0, R0 + T, z0, z0 + H), dict(x=(c - L / 2, c + L / 2), y=(R0, R0 + T), z=(z0, z0 + H),
                                                                  room=hi - lo, spare=(hi - lo - L) / 2)


def fins(W, cell, spots_b):
    """Two fins behind the cell: from the back wall forward to FIN_GAP behind the cell, from the seam ring (the bed) up.
    spots_b: the trim spots' boxes (board frame); a fin under one keeps FIN_UNDER below and in front of it."""
    yf = cell["y"][1] + K["FIN_GAP"]
    zt = PCB_Z0 + K["FIN_TOP"]
    out, steps = [], []
    for xc in K["FIN_X"]:
        xs = (xc - K["FIN_W"] / 2, xc, xc + K["FIN_W"] / 2)
        z_rim = rp.PIV_Z + (rp.SEAM - rp.PIV_Z + (27.5 - rp.PIV_Y) * rp.SIN_T) / rp.COS_T + 0.3      # just above the seam at the back wall
        over = [s for s in spots_b if s[0] - K["FIN_CLR"] < xs[2] and s[3] + K["FIN_CLR"] > xs[0]]
        top = [(yf, zt)]
        z_back = zt
        if over:
            ys, z_back = min(s[1] for s in over) - K["FIN_UNDER"], min(s[2] for s in over) - K["FIN_UNDER"]
            check(ys > yf + 2.0 and z_rim + 2.0 < z_back < zt, f"fin at x {xc}: no room under the trim spot (y {ys:.2f}, z {z_back:.2f})")
            top += [(ys, zt), (ys, z_back)]
            steps.append((xc, ys, z_back))
        back = [(min(W.back_y(x, z) for x in xs) + K["RIB_EMBED"], float(z)) for z in np.linspace(z_back, z_rim, 16)]
        back.append((back[-1][0], PCB_Z0 - 4.0))                                                     # straight down, cut at the seam
        zk, c = cell["z"][0] + 1.5, K["FIN_FOOT"]
        f = above_seam(prism_yz([(yf + c, back[-1][1]), (yf + c, zk - c), (yf, zk)] + top + back, xs[0], xs[2]))
        check(f.status() == m3.Error.NoError and f.volume() > 50.0 and len(f.decompose()) == 1, f"fin at x {xc}: {f.status()}, {f.volume():.1f}")
        out.append(f)
    return union(out), dict(y=yf, top=zt, steps=steps)


def fill_notch(M, z0, z1):
    """The old cable notch filled: the convex hull of the wall beside and around it (world frame). Outside the wall is
    convex, so the fill follows it (a chord across the notch's 5.6); inside it adds under 0.3."""
    piece = M ^ box(*K["NOTCH_X"], 20.0, 30.0, z0, z1)
    check(len(piece.decompose()) == 1 and piece.volume() > 20.0, f"notch fill: {len(piece.decompose())} pieces of wall")
    fill = piece.hull()
    return M + fill, fill.volume() - piece.volume()


def usb_slot():
    """The opening's cutter (world frame): W x H in (x, z) with USB_R corners, level along y through the back wall."""
    w, h, z0, xc = K["USB_SLOT"]
    r, zc = K["USB_R"], rp.SEAM + z0 + h / 2
    a = np.linspace(0.0, math.pi / 2, 9)
    P = [(xc + sx * (w / 2 - r) + r * math.cos(v + q), zc + sz * (h / 2 - r) + r * math.sin(v + q))
         for q, sx, sz in ((0.0, 1, 1), (math.pi / 2, -1, 1), (math.pi, -1, -1), (1.5 * math.pi, 1, -1)) for v in a]
    return (lambda y0, y1: prism_xz(P, y0, y1)), (xc - w / 2, xc + w / 2, zc - h / 2, zc + h / 2)


def fork(W, over=0.0):
    """The pebble's round E frame fork: two feet and a lower block across both lower screws, the button side's prong,
    widened to the wall above HEAD_Z, a top bar across both upper screws to the plug side's wall; a pad over each screw
    (over: that much proud, as printed). The feet end FOOT_CLR above the seam plane."""
    zl0, zl1 = PCB_Z0 + K["LOW_Z"][0], PCB_Z0 + K["LOW_Z"][1]
    zh, zbar, zt = PCB_Z0 + K["HEAD_Z"], PCB_Z0 + K["BAR_Z"], PCB_Z0 + K["TOP_Z"]
    b, s, pr, ear = BTN, K["SLOT_U"], K["PRONG_U"], K["EAR_U"]
    edge = lambda su, z: W.side_u_band(su, z, T0, T1) - K["WALL_GAP"]
    zs = np.arange(zh, zt + 1e-9, 0.5).tolist()
    if zs[-1] < zt - 1e-9:
        zs.append(zt)
    left = [(max(pr, min(edge(b, z), pr + (z - zh))), z) for z in zs]                # button side: 45 deg out, then along the wall
    right = [(edge(-b, z), z) for z in zs if z >= zbar - 1e-9]                       # plug side, the bar only
    head = [(b * u, z) for u, z in left] + [(-b * u, z) for u, z in right[::-1]] + [(b * s, zbar), (b * s, zh)]     # (u, z)
    parts = [ubox(-ear, ear, T0, T1, zl0, zl1)]
    parts += [above_seam(ubox(su * s, su * ear, T0, T1, PCB_Z0 - 8.0, zl1), K["FOOT_CLR"]) for su in (-1, 1)]
    parts.append(ubox(b * s, b * pr, T0, T1, zl0, zh + 1.0))
    parts.append(prism_xz([(X0 + u, z) for u, z in head], T0, T1))
    for u, z in SCREWS:
        parts.append(ubox(u - K["PAD"] / 2, u + K["PAD"] / 2, YP - over, T0 + 0.2, z - K["PAD"] / 2, z + K["PAD"] / 2))
    f = union(parts)
    L, e = K["LEAD"], 0.01
    f = f - prism_yz([(T1 - L, zt + e), (T1 + e, zt + e), (T1 + e, zt - L)], X0 - 60, X0 + 60)          # the bar's top back edge
    yf, L = YP - over, K["PAD_LEAD"]
    for z in sorted({z for _, z in SCREWS}):
        z1 = z + K["PAD"] / 2
        f = f - prism_yz([(yf - e, z1 - L), (yf - e, z1 + e), (yf + L, z1 + e)], X0 - 60, X0 + 60)      # pads, upper edge
    check(f.status() == m3.Error.NoError and len(f.decompose()) == 1, f"fork: {f.status()}, {len(f.decompose())} pieces")
    return f, dict(bar=(zbar, zt), bar_u=(-b * right[0][0], b * left[-1][0]), low=(zl0, zl1), head=zh)


def board_dummies(shift=0.0):
    """The seated board as boxes (board frame). shift: forward (the board without the 0.5 foam strips: hw.GASKET)."""
    y = lambda v: v - shift
    e = -BTN * hw.PCB_W / 2
    d = dict(glass=ubox(-hw.GLASS_W / 2, hw.GLASS_W / 2, y(rp.Y_GLASS0), y(rp.Y_GLASS1), *GLASS_Z),
             board=ubox(-hw.PCB_W / 2, hw.PCB_W / 2, y(rp.Y_GLASS1), y(YB), PCB_Z0, PCB_Z0 + hw.PCB_H))
    for n, z in K["JST_Z"].items():
        z = PCB_Z0 + z
        if n == "rtc":
            d["plug-rtc"] = ubox(e, e - BTN * hw.PLUG_PROUD, y(rp.Y_GLASS1), y(YB), z - K["RTC_LEN"] / 2, z + K["RTC_LEN"] / 2)
        else:
            d[f"plug-{n}"] = ubox(e + BTN * K["PLUG_IN"], e, y(YB), y(YB + K["PLUG_UP"]), z - hw.PLUG_LEN / 2, z + hw.PLUG_LEN / 2)
    return d


def overhang(M_new, ids):
    """Steepest downward face (deg from vertical) among the triangles that came from the added parts; faces on the bed
    (the seam plane) apart. Returns (deg, point)."""
    V, F, me = tris(M_new)
    run = np.asarray(me.run_index, np.int64) // 3
    oid = np.asarray(me.run_original_id)
    tid = np.zeros(len(F), np.int64)
    for k in range(len(oid)):
        tid[run[k]:run[k + 1]] = oid[k]
    k = np.isin(tid, list(ids))
    P = V[F[k]]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    a = np.linalg.norm(n, axis=1)
    ok = (a > 1e-9) & ~(P[:, :, 2].max(axis=1) < rp.SEAM + 1e-3)
    P, n = P[ok], n[ok] / a[ok, None]
    j = int(np.argmin(n[:, 2]))
    return math.degrees(math.asin(max(-n[j, 2], 0.0))), P[j].mean(axis=0), float(a[ok][n[:, 2] < -math.sin(math.radians(OVERHANG_MAX)) - 1e-6].sum() / 2)


def gap(A, B, search=6.0):
    return float(A.min_gap(B, search))


def build():
    OUT.mkdir(exist_ok=True)
    body0 = load(SRC / "body.stl")
    check(len(body0.decompose()) == 1, "body.stl is not one piece")
    body, dv_notch = fill_notch(body0, rp.SEAM - 0.5, rp.SEAM + K["USB_SLOT"][2] - 0.1)
    body = body.as_original()
    check(len(body.decompose()) == 1 and body.genus() == body0.genus() and 1.0 < dv_notch < 20.0, f"body's notch fill: {dv_notch:.2f} mm3")
    spots = load(SRC / "dummy-trim-spots.stl")
    spots_b = [q.transform(T_BW.tolist()).bounding_box() for q in spots.decompose()]
    Wl = Walls(body.transform(T_BW.tolist()))
    st_b, st_i = stops()
    rb_b, rb_i = ribs(Wl)
    cell_b, cell_i = cell_seat(Wl)
    fn_b, fn_i = fins(Wl, cell_i, spots_b)
    fk_b, fk_i = fork(Wl)
    fkp_b, _ = fork(Wl, over=K["PAD_OVER"])
    st, rb, fn = world(st_b).as_original(), world(union([rb_b, fn_b])).as_original(), None
    add = st + rb
    new = body + st + rb
    L = []
    # the USB-C slot, cut last
    cutter, sb = usb_slot()
    gone = new ^ cutter(15.0, 40.0)
    gb = gone.bounding_box()
    w_, h_ = K["USB_SLOT"][:2]
    area = w_ * h_ - (4 - math.pi) * K["USB_R"] ** 2
    check(len(gone.decompose()) == 1 and gb[1] > 20.0 and 0.8 * area * (gb[4] - gb[1]) < gone.volume() < area * (gb[4] - gb[1]) + 1e-6,
          f"USB slot cuts {gone.volume():.1f} mm3 in {len(gone.decompose())} pieces, y {gb[1]:.2f}..{gb[4]:.2f}")
    solid = new
    new = new - cutter(15.0, 40.0).as_original()
    check(new.genus() == solid.genus() + 1, f"USB slot: genus {solid.genus()} -> {new.genus()} (one closed opening expected)")

    # 1. the mesh
    check(new.status() == m3.Error.NoError and len(new.decompose()) == 1 and solid.genus() == body.genus(),
          f"body + keeper: {new.status()}, {len(new.decompose())} pieces, genus {solid.genus()} (was {body.genus()})")
    dv, dh = solid.volume() - body.volume(), new.hull().volume() - body.hull().volume()
    check(abs(dh) < 1e-3 * body.hull().volume() * 1e-3, f"the added material changes the outer hull by {dh:.3f} mm3")
    loose = [p.volume() for p in (add - body).decompose()]
    L.append(f"Body + keeper: closed, one piece, genus {new.genus()}; +{dv:.0f} mm3 ({dv * 1.24e-3:.1f} g PLA) in {len(loose)} pieces "
             f"(stops {st.volume():.0f}, ribs and fins {rb.volume():.0f} before the wall), outer hull unchanged ({dh:+.4f} mm3).")
    # every added piece is bedded in the wall
    for nm, q in [(n_, world(P_)) for n_, P_ in st_i["parts"]] + [("rib / fin", q) for q in rb.decompose()]:
        inw = (q ^ body).volume()
        check(inw > 0.02 * q.volume() and inw > 5.0, f"{nm}: {q.volume():.1f} mm3 with only {inw:.2f} mm3 in the wall")
    # the seam's magnet and pin holes stay open
    holes = union([m3.Manifold.cylinder(rp.SEAM_PIN_L, b_["r_boss"] - 1.0, circular_segments=48).translate((b_["x"], b_["y"], rp.SEAM - 1.0))
                   for b_ in rp.boss_spots()])
    check((add ^ holes).volume() < 1e-6 and gap(add, holes) >= K["FIN_CLR"], f"added material {gap(add, holes):.2f} from a seam hole")

    # 2. overhangs of the added faces
    deg, at, bad = overhang(new, {st.original_id(), rb.original_id()})
    check(deg <= OVERHANG_MAX + 0.05 and bad < 0.01, f"added faces overhang {deg:.1f} deg at {np.round(at, 1)} ({bad:.2f} mm2 over {OVERHANG_MAX:g})")
    L.append(f"Overhang of the added faces (body printed on its seam ring): steepest {deg:.1f} deg from vertical "
             f"at ({at[0]:.1f}, {at[1]:.1f}, {at[2]:.1f}); limit {OVERHANG_MAX:g}. No supports for them.")

    # 3. seated clearances
    fk, cell = world(fk_b), world(cell_b)
    stops_only, ribs_only = st, rb
    g = {}
    for tag, sh in (("on the foam strips (model)", 0.0), ("without the strips (as assembled)", hw.GASKET)):
        d = {n: world(v) for n, v in board_dummies(sh).items()}
        for n in ("slide", "boot", "rst"):
            b_ = load(SRC / f"dummy-button-{n}.stl")
            d[f"button-{n}"] = b_.translate((T_WB[:, :3] @ np.array([0.0, -sh, 0.0])).tolist())
        for n, v in d.items():
            ov = (v ^ add).volume()
            check(ov < 1e-6, f"{n} ({tag}) is {ov:.3f} mm3 inside the added material")
            g[(tag, n)] = min(gap(v, st), gap(v, rb))
        check(min(g[(tag, n)] for n in d) >= K["GAP_MIN"] - 1e-6, f"seated board {tag}: {min((v, k) for k, v in g.items() if k[0] == tag)}")
        L.append(f"Seated board {tag}: glass to the stops {g[(tag, 'glass')]:.2f}, board {g[(tag, 'board')]:.2f}, "
                 f"plugs {min(v for k, v in g.items() if k[0] == tag and k[1].startswith('plug')):.2f}, "
                 f"buttons {min(v for k, v in g.items() if k[0] == tag and k[1].startswith('button')):.2f} (to stops, ribs, fins).")
        if sh > 0.0:
            dm = d                                          # the fork and the cell are checked against the board as assembled
    usb, cable = load(SRC / "dummy-usb-head.stl"), load(SRC / "dummy-usb-cable.stl")
    led = load(SRC / "dummy-led-room.stl")
    # the fork: free of the body, the board (but the pads on the plate), plugs, USB head; bedded on the ribs
    for n, v in list(dm.items()) + [("usb head", usb), ("usb cable", cable), ("body", body), ("stops", st), ("ribs", rb), ("cell", cell)]:
        ov = (fk ^ v).volume()
        check(ov < 1e-4, f"fork overlaps {n} by {ov:.4f} mm3")
    g_wall = gap(fk, body)
    check(g_wall >= 0.3, f"fork to the cavity wall {g_wall:.2f}")
    g_usb = gap(fk, usb)
    bear = []
    for q in rb_b.decompose():                              # the fork's back face on each rib / the cell
        c = q.bounding_box()
        if c[1] < R0 + 1e-6 < c[4] and c[5] > PCB_Z0 + 40:
            a = (q.translate((0, -0.05, 0)) ^ fk_b).volume() / 0.05
            bear.append(a)
    check(len(bear) == 2 and min(bear) > 25.0, f"fork on the upper ribs: bearing {bear}")
    L.append(f"Fork seated: {fk.volume():.0f} mm3 ({fk.volume() * 1.24e-3:.1f} g); to the cavity wall {g_wall:.2f}, to the USB head {g_usb:.2f} "
             f"(it rests on the head if it slips); bears on the upper ribs {min(bear):.0f} and {max(bear):.0f} mm2; "
             f"bar z {fk_i['bar'][0]:.1f}..{fk_i['bar'][1]:.1f}, u {fk_i['bar_u'][1]:+.1f}..{fk_i['bar_u'][0]:+.1f}; "
             f"upward plugs to the fork {min(gap(fk, dm[n]) for n in dm if n.startswith('plug') and n != 'plug-rtc'):.2f}.")
    # the fins: clear of the USB head and cable, of the trim spots
    fn = world(fn_b)
    g_fu, g_fc, g_fs = gap(fn, usb), gap(fn, cable), gap(fn, spots)
    check((fn ^ usb).volume() + (fn ^ cable).volume() + (fn ^ spots).volume() < 1e-6 and g_fu >= rp.HEAD_CLR + 0.5 and g_fc >= rp.HEAD_CLR
          and g_fs >= K["FIN_CLR"], f"fins: USB head {g_fu:.2f}, cable {g_fc:.2f}, trim spots {g_fs:.2f}")
    # the cell: room, fork in front, fins behind, USB head below, nothing of the LEDs' room
    for n, v in (("body", new), ("usb head", usb), ("usb cable", cable), ("LEDs' room", led)) + tuple((k, v) for k, v in dm.items()):
        ov = (cell ^ v).volume()
        check(ov < (2.0 if n in ("plug-uart", "plug-j5") else 1e-4), f"cell overlaps {n} by {ov:.4f} mm3")
    g_cw, g_cf, g_cu, g_cl = gap(cell, body), gap(cell, world(fn_b)), gap(cell, usb), gap(cell, led, 40.0)
    check(cell_i["spare"] >= 0.3 and g_cw >= 0.25, f"cell: {cell_i['spare']:.2f} spare a side, {g_cw:.2f} to the wall")
    L.append(f"Cell {K['CELL'][0]:g} x {K['CELL'][1]:g} x {K['CELL'][2]:g} (measured) on its long edge right behind the fork: "
             f"x {cell_i['x'][0]:.2f}..{cell_i['x'][1]:.2f}, y {cell_i['y'][0]:.2f}..{cell_i['y'][1]:.2f}, z {cell_i['z'][0]:.1f}..{cell_i['z'][1]:.1f} "
             f"(board frame); room {cell_i['room']:.2f}, {cell_i['spare']:.2f} spare a side as a square box; to the wall {g_cw:.2f}, "
             f"to the fins {g_cf:.2f}, to the USB head {g_cu:.2f}, to the LEDs' room {g_cl:.2f}. "
             f"It was 1.0 behind the plate (68 x 35 x 10 in rolypoly.py): now {cell_i['y'][0] - YB:.2f}. The UART and J5 plugs "
             f"(not used here) would stand in its face.")
    sp = sorted((gap(cell, q, 20.0), float(np.mean(q.bounding_box()[0::3]))) for q in spots.decompose())
    L.append(f"Fins: to the USB head {g_fu:.2f}, to its cable {g_fc:.2f}, to the trim spots {g_fs:.2f}. Trim spots (rolypoly.py placed them "
             f"for the old cell) to the new cell: " + ", ".join(f"{g_:.2f} at x {x_:.1f}" for g_, x_ in sp) +
             (f". TO DO BY HAND: the segment at x {sp[0][1]:.1f} touches the cell's back; stick it higher or further along the wall "
              f"({rp.TRIM_SPOT_BAT:g} clear)." if sp[0][0] < rp.TRIM_SPOT_BAT else "."))
    # 4. the logo
    logo = load(SRC / "dummy-logo-new.stl")
    g_logo = min(gap(add, logo, 30.0), gap(add, led, 30.0))
    check(g_logo >= 3.0, f"added material {g_logo:.2f} from the logo / the LEDs' room")
    L.append(f"Logo: the nearest added material is {g_logo:.1f} from the letters and the LEDs' room; the skin is round 8's.")
    # the socket's way in from the slot: free of the body, ribs and fins; how far to the cell
    probe = lambda d: cutter(gb[1] - d, gb[1] - 0.02)
    check((probe(14.0) ^ new).volume() < 1e-6 and gap(probe(14.0), fn) >= 0.5, f"behind the USB slot: fins {gap(probe(14.0), fn):.2f} from the socket's way")
    lo, hi = 0.0, 40.0
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if (probe(mid) ^ cell).volume() < 1e-6 else (lo, mid)
    cup0 = max(load(SRC / "cup-rock.stl").decompose(), key=lambda q: q.volume())     # round 8's STL carries two zero-volume
    cup, dv_cup = fill_notch(cup0, rp.CUP_ROCK_CAST_TO - 1.5, rp.SEAM + 0.5)          # slivers at the bottom pole: left out
    check(len(cup.decompose()) == 1 and cup.genus() == cup0.genus() and 20.0 < dv_cup < 90.0 and cup.bounding_box()[5] < rp.SEAM + 1e-4,
          f"cup's notch fill: {dv_cup:.2f} mm3, {len(cup.decompose())} pieces, genus {cup0.genus()} -> {cup.genus()}, top {cup.bounding_box()[5]:.4f}")
    L.append(f"USB-C opening for the extension's socket end (11 x 5.5): {w_:g} x {h_:g}, corners r {K['USB_R']:g}, level through the body's back wall at x {sb[0]:g}..{sb[1]:g}, world z {sb[2]:g}..{sb[3]:g} "
             f"({K['USB_SLOT'][2]:g} above the seam), closed all round; wall there y {gb[1]:.2f}..{gb[4]:.2f} ({gb[4] - gb[1]:.2f} thick), {gone.volume():.0f} mm3 cut; "
             f"its roof is a {w_ - 2 * K['USB_R']:g} mm bridge, printed without support (not in the overhang figure above). Behind it: fins {gap(probe(14.0), fn):.2f} from the socket's way, "
             f"the cell's back {lo:.1f} from the wall's inner face, so a socket end up to {lo + gb[4] - gb[1]:.1f} long sits flush outside. "
             f"The old notch at x -5 is filled: body +{dv_notch:.1f} mm3, cup +{dv_cup:.1f} mm3 (keeper/cup-rock.stl; cast and cast plug unchanged). "
             f"The USB head and cable in the checks above are still round 8's right-angle one.")
    L.append(f"Stops (board frame): rails {SEAT['SIDE_CLR']:g} from the glass each side, top y {st_i['rail_y']:.2f}, z {st_i['rail_z'][0]:.2f}..{st_i['rail_z'][1]:.2f}; "
             f"top wedge from z {st_i['top'][0]:.3f} ({SEAT['TOP_CLR']:g} above the glass) to {st_i['top'][1]:.2f}; bottom corners' flat top z {st_i['bot'][1]:.3f} "
             f"({SEAT['BOT_CLR']:g} under the glass), from the seam ring. Ribs: " +
             "; ".join(f"{'button' if r['su'] == BTN else 'plug'} side to |u| {r['u_in']:g}, z {r['z'][0]:.1f}..{r['z'][1]:.1f}, corbel foot z {r['foot']:.1f}" for r in rb_i) +
             f". Fins at x {K['FIN_X'][0]:g} and {K['FIN_X'][1]:g}, front y {fn_i['y']:.2f}, top z {fn_i['top']:.1f}" +
             "".join(f"; the one at x {x_:g} steps down to z {z_:.1f} behind y {y_:.1f} (under a trim spot)" for x_, y_, z_ in fn_i["steps"]) + ".")

    # the fork as printed: flat on its back face, pads up
    fp = fkp_b.transform([[1, 0, 0, -X0], [0, 0, 1, -PCB_Z0], [0, -1, 0, T1]])
    bb = fp.bounding_box()
    hgt = K["FORK_T"] + K["PAD_H"] + K["PAD_FWD"] + K["PAD_OVER"]
    check(abs(bb[2]) < 1e-6 and abs(bb[5] - hgt) < 1e-6, f"fork as printed: z {bb[2]:.4f}..{bb[5]:.4f}")
    L.append(f"Fork as printed: {bb[3] - bb[0]:.1f} x {bb[4] - bb[1]:.1f} x {hgt:g}, flat on its back, pads up; pads {K['PAD_H'] + K['PAD_FWD']:g} to the plate as assembled "
             f"(no foam strips) + {K['PAD_OVER']:g} proud = {K['PAD_H'] + K['PAD_FWD'] + K['PAD_OVER']:g} as printed (was 2.2: loose in the grey print); sand to fit.")

    write_stl(new, OUT / "body.stl")
    write_stl(cup, OUT / "cup-rock.stl")
    write_stl(st, OUT / "stops.stl")
    # support enforcer for the plates, as the pebble's (make_plate.py): the middle 6 of each slot's top end wall (a bridge
    # SLOT_W wide, TILT off straight down), kept 0.14 off the inner face. Round 7's print: trees to the slot tops improved them.
    zt = rp.SLOT_Z[1]
    write_stl(world(union([box(X0 - rp.XOFF + x - 3.0, X0 - rp.XOFF + x + 3.0, rp.FACE_Y - 0.8, rp.Y_LAND - 0.14, zt - 0.65, zt + 0.45)
                           for x in rp.TUBE_X])), OUT / "slot-top-enforcer.stl")
    write_stl(rb, OUT / "ribs.stl")
    write_stl(fk, OUT / "fork.stl")
    write_stl(fp, OUT / "fork-print.stl")
    write_stl(fp.transform([[0, -1, 0, 0], [1, 0, 0, 0], [0, 0, 1, 0]]), OUT / "fork-print-plate.stl")   # turned 90 deg: its long side along the plate's x
    write_stl(cell, OUT / "dummy-cell.stl")
    for n, v in dm.items():
        write_stl(v, OUT / f"dummy-{n}.stl")
    (OUT / "report.txt").write_text("Roly-poly board keeper on round 8's body (roly_keeper.py)\n\n" + "\n".join("- " + s for s in L) + "\n")
    print("\n".join(L))
    return dict(cell=cell_i, fork=fk_i)


def views():
    import pyvista as pv
    rd = lambda n: pv.read(str(OUT / n))
    body = rd("body.stl")
    n_cut = (rp.R_TILT @ np.array([0.0, 1.0, 0.0])).tolist()
    Wp = lambda x, y, z: rp.pts_world(np.array([[x, y, z]], float))[0]
    cut = lambda y: body.clip(normal=n_cut, origin=Wp(0, y, 60).tolist(), invert=True)
    col = dict(body="#e2d6c0", rib="#7d5fb0", stop="#c8402f", glass="#9aa6b2", board="#5f7f62", cell="#d9b25a", usb="#8a8a8a",
               fork="#e8893a", plug="#f0f0f0")
    plugs = pv.merge([rd(f"dummy-plug-{n}.stl") for n in K["JST_Z"]], merge_points=False)
    usb = pv.read(str(SRC / "dummy-usb-head.stl"))

    def scene(pl, parts, title, cam):
        pl.set_background("#d8d5cf", top="#f3f1ed")
        for k, m, o in parts:
            pl.add_mesh(m, color=col[k], opacity=o, ambient=0.3, diffuse=0.75, specular=0.08)
        pl.add_text(title, font_size=10, color="black")
        ctr = Wp(X0 + 3, 4, 64)
        pl.camera_position = [(ctr + rp.R_TILT @ np.array(cam)).tolist(), ctr.tolist(), (0, 0, 1)]
        pl.camera.view_angle = 24
        pl.reset_camera_clipping_range()

    side, back = (-170.0, 300.0, -45.0), (0.0, 345.0, 0.0)
    y_cut = T1 + K["CELL"][2] + 4.5
    pl = pv.Plotter(off_screen=True, window_size=(5 * 700, 900), shape=(1, 5))
    pl.subplot(0, 0)
    scene(pl, [("body", cut(rp.Y_LAND + 3.2), 1), ("stop", rd("stops.stl"), 1)], "glass stops on the front wall (board out)", back)
    pl.subplot(0, 1)
    ribs_cut = rd("ribs.stl").clip(normal=n_cut, origin=Wp(0, R1 + 0.2, 60).tolist(), invert=True)      # without the fins
    scene(pl, [("body", cut(R1 + 0.2), 1), ("stop", rd("stops.stl"), 1), ("rib", ribs_cut, 1), ("glass", rd("dummy-glass.stl"), 1),
               ("board", rd("dummy-board.stl"), 1), ("plug", plugs, 1), ("fork", rd("fork.stl"), 1), ("usb", usb, 0.5)],
          "board + fork, from behind (cut behind the ribs)", back)
    for c, op in ((2, 1.0), (3, 0.16)):
        pl.subplot(0, c)
        scene(pl, [("body", cut(y_cut), 1), ("rib", rd("ribs.stl"), 1), ("glass", rd("dummy-glass.stl"), 1), ("board", rd("dummy-board.stl"), 1),
                   ("plug", plugs, 1), ("fork", rd("fork.stl"), 1), ("cell", rd("dummy-cell.stl"), op), ("usb", usb, 0.5)],
              "with the cell (cut behind it)" if op == 1.0 else "cell ghosted", side)
    pl.subplot(0, 4)
    col["cup"] = "#f3ecdc"
    scene(pl, [("body", body, 1), ("cup", rd("cup-rock.stl"), 1)], "the back from outside: USB-C slot in the body, the cup's notch closed", (40.0, 345.0, -30.0))
    pl.enable_anti_aliasing("ssaa")
    pl.screenshot(str(OUT / "keeper-views.png"))
    pl.close()
    print("wrote", OUT / "keeper-views.png")


if __name__ == "__main__":
    if "--views" not in sys.argv[1:]:
        build()
    if "--no-views" not in sys.argv[1:]:
        views()
