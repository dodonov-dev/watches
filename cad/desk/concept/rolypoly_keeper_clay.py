#!/usr/bin/env python3
"""Concept clay, roly-poly board keeper options after the pebble's round E (frame fork: top bar across both upper screws,
wide ribs reaching over the board, glass stops on the front wall): round 8's real body (out-rolypoly/body.stl, cup off,
the back cut away) and dummies; keepers, ribs, stops and the moved cells are concept boxes in the board frame.
The I2C plug's 4.0 is ASSUMED as on the pebble. rolypoly_keeper.py's section sheet is older (round D's one-prong fork).

  ~/.venvs/cad/bin/python cad/desk/concept/rolypoly_keeper_clay.py [out dir]   (default images/rolypoly-keeper)
"""
import sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import numpy as np
import pyvista as pv
import rolypoly as rp
import housing as hw

D = HERE.parent / "out-rolypoly"
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent.parent.parent / "images" / "rolypoly-keeper"
OUT.mkdir(parents=True, exist_ok=True)

X0 = rp.XOFF
YB = rp.Y_GLASS0 + 9.15                                   # the plate's back face
F0, F1 = YB + 1.5, YB + 4.0                               # the pebble's pad height and fork thickness
RIB_Y = (F1, F1 + 3.5)                                    # round E's ribs, 3.5 thick
BAT_Y1 = YB + rp.BAT_GAP + rp.BAT_T
LEG = (BAT_Y1 + 0.65, BAT_Y1 + 3.15)                      # behind the cell; 0.65 of foam
BAT_Z1 = rp.BAT_Z0 + rp.BAT_HT
Z_CR = (BAT_Z1 + 1.0, BAT_Z1 + 4.5)                       # the crank bar, above the cell
SX = (X0 - 12.5, X0 - 8.5)                                # the stick's plane, 4 thick
PRONG_X = (X0 - 21.0, SX[1])                              # the pebble's prong
SCREW = (X0 - hw.NUT_DX / 2, rp.PCB_Z0 + hw.NUT_INSET + hw.NUT_DZ)   # button side, upper
TOP = SCREW[1] + 2.8
Z_FOOT = 23.8


def W(x, y, z):
    return rp.pts_world(np.array([[x, y, z]], float))[0].tolist()


def box(x0, x1, y0, y1, z0, z1):
    m = pv.Box((min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1))).triangulate()
    m.points = rp.pts_world(np.asarray(m.points, float))
    return m


def merge(ms):
    return pv.merge(ms, merge_points=False)


def lim(z, y0, y1):
    return rp.inner_x_limits(z, y0, y1)


def zs(s):
    """The pebble's s (along the face) -> the roly-poly's board-frame z."""
    return rp.PCB_Z0 + s - 16.8


BAR_Z = (zs(88.0), zs(95.3))                               # round E's top bar
SCREWS = [(X0 + sx * hw.NUT_DX / 2, rp.PCB_Z0 + hw.NUT_INSET + k * hw.NUT_DZ) for k in (0, 1) for sx in (-1, 1)]


def pads(which):
    return [box(sx - 2.5, sx + 2.5, YB, F0, sz - 2.5, sz + 2.5) for sx, sz in which]


def top_end(z0):
    """Round E's upper end: the bar across both upper screws, wall to wall, the button side's prong down to z0, 2 pads."""
    l = lim(BAR_Z[1], F0, F1)
    return [box(l[0] + 0.47, l[1] - 0.47, F0, F1, *BAR_Z), box(*PRONG_X, F0, F1, z0, BAR_Z[1])] + pads(SCREWS[2:])


def stick():
    """Option 1: E's upper end, then a step over the cell and a leg behind it."""
    return merge(top_end(Z_CR[0]) + [box(*SX, F0, LEG[1], *Z_CR), box(*SX, *LEG, Z_FOOT, Z_CR[1])])


def foam():
    return merge([box(*SX, BAT_Y1, LEG[0], z, z + 6.0) for z in (31.0, 52.0)])


def frame_fork():
    """Options 2 / 3: round E's frame fork as it is (lower block across both lower screws, two feet, 4 pads)."""
    return merge(top_end(zs(17.1)) + [box(X0 - 24.0, X0 + 24.0, F0, F1, zs(17.1), zs(30.0))]
                 + [box(X0 + s * 8.5, X0 + s * 24.0, F0, F1, 23.0, zs(17.1)) for s in (-1, 1)] + pads(SCREWS[:2]))


def wedge(side, tip, z_top, z_min=23.0, flat=0.0):
    """A rib from the side wall, its inner edge at X0 + side*tip down to z_top - flat, then receding 45 deg to the wall."""
    out = []
    for k in range(60):
        z1 = z_top - k
        z0 = max(z1 - 1.0, z_min)
        edge = X0 + side * (tip + max(0.0, k + 1 - flat))
        wall = lim(0.5 * (z0 + z1), *RIB_Y)[0 if side < 0 else 1] + side * 1.5
        if z0 >= z1 or side * (wall - edge) <= 0:
            break
        out.append(box(edge, wall, *RIB_Y, z0, z1))
    return out


def upper_ribs():
    return wedge(-1, 11.0, zs(96.0), flat=12.0) + wedge(1, 13.0, zs(96.0))     # button side flat 12 high; plug side a wedge


def ribs1():
    return merge(upper_ribs() + [box(SX[0] - 0.75, SX[1] + 0.75, LEG[1], LEG[1] + 9.5, 22.6, 31.0)])   # + one from the rim


def ribs_e():
    return merge(upper_ribs() + wedge(-1, 14.0, zs(31.0)) + wedge(1, 14.0, zs(31.0)))


def ribs2():
    """Option 2: the cell fills the width behind the fork, so no lower side ribs; two ribs from the rim behind the cell."""
    return merge(upper_ribs() + [box(x - 1.75, x + 1.75, CELL2[3] + 0.65, CELL2[3] + 9.0, 23.6, 34.0) for x in BACK_X])


def foam2():
    return merge([box(x - 1.75, x + 1.75, CELL2[3], CELL2[3] + 0.65, 27.5, 34.0) for x in BACK_X])


def stops():
    """Round E's glass stops on the front wall: side rails 0.15 from the glass, a top wedge, bottom corners."""
    gx, gz = (X0 - hw.GLASS_W / 2, X0 + hw.GLASS_W / 2), (rp.PCB_Z0 + 1.125, rp.PCB_Z0 + 1.125 + hw.GLASS_H)
    y0 = rp.Y_LAND - 0.5
    return merge([box(gx[0] - 2.4, gx[0] - 0.15, y0, rp.Y_LAND + 3.0, gz[0], gz[1]),
                  box(gx[1] + 0.15, gx[1] + 2.4, y0, rp.Y_LAND + 3.0, gz[0], gz[1]),
                  box(gx[0] - 2.4, gx[1] + 2.4, y0, rp.Y_LAND + 2.6, gz[1] + 0.3, gz[1] + 3.0)]
                 + [box(X0 + s * 10.0, X0 + s * 15.75, y0, rp.Y_LAND + 2.6, gz[0] - 3.0, gz[0] - 0.33) for s in (-1, 1)])


def plug():
    e = X0 + hw.PCB_W / 2
    z = rp.PCB_Z0 + hw.PLUG_Z["i2c"]
    return box(e - 5.0, e, YB - 1.0, YB + 4.0, z - 3.5, z + 3.5)


body = pv.read(D / "body.stl")
n_cut = (rp.R_TILT @ np.array([0.0, 1.0, 0.0])).tolist()
body_cut = body.clip(normal=n_cut, origin=W(0, LEG[1] + 3.6, 60), invert=True)
dummy = {k: pv.read(D / f"dummy-{k}.stl") for k in ("glass", "pcb", "battery", "usb-head")}
COL = dict(body="#e2d6c0", rib="#7d5fb0", glass="#9aa6b2", pcb="#5f7f62", battery="#d9b25a", usb="#8a8a8a", stick="#e8893a",
           foam="#3a3a3a", plug="#f0f0f0", stop="#c8402f")
CELL2 = (-35.69, 32.31, F1, F1 + rp.BAT_T, 27.0, 62.0)                       # the 68 x 35 cell on its long edge, right behind the fork
BACK_X = (-16.0, 12.0)                                                      # two ribs from the rim behind that cell, foam on them
CELL3 = (-26.0, 24.0, RIB_Y[1], RIB_Y[1] + 10.0, 27.0, 61.0)                  # 103450 (50 x 34 x 10), behind the ribs


def scene(pl, parts, title, cam=(-170.0, 300.0, -45.0)):
    pl.set_background("#d8d5cf", top="#f3f1ed")
    for k, m, o in parts:
        pl.add_mesh(m, color=COL[k], opacity=o, ambient=0.3, diffuse=0.75, specular=0.08)
    pl.add_text(title, font_size=11, color="black")
    ctr = np.array(W(X0 + 3, 4, 64))
    pl.camera_position = [(ctr + rp.R_TILT @ np.array(cam)).tolist(), ctr.tolist(), (0, 0, 1)]   # from behind, the button side
    pl.camera.view_angle = 24
    pl.reset_camera_clipping_range()


def cut_at(y):
    return body.clip(normal=n_cut, origin=W(0, y, 60), invert=True)


# ---- the three options side by side (top: seated, bottom: the cell ghosted) ------------------------------------------------
OPTS = [("1  BAR + LEG behind the cell (cell and wiring as now)", [("stick", stick()), ("foam", foam())], ribs1(), dummy["battery"]),
        ("2  PEBBLE'S FRAME FORK, the same cell on its long edge right behind it", [("stick", frame_fork()), ("foam", foam2())], ribs2(), box(*CELL2)),
        ("3  PEBBLE'S FRAME FORK, smaller cell (103450, 50 wide)", [("stick", frame_fork())], ribs_e(), box(*CELL3))]
pl = pv.Plotter(off_screen=True, window_size=(3 * 760, 2 * 900), shape=(2, 3))
for r, op in enumerate((1.0, 0.16)):
    for c, (title, keeper, rib, cell) in enumerate(OPTS):
        pl.subplot(r, c)
        scene(pl, [("body", body_cut, 1), ("rib", rib, 1), ("glass", dummy["glass"], 1), ("pcb", dummy["pcb"], 1),
                   ("battery", cell, op), ("usb", dummy["usb-head"], 0.35), ("plug", plug(), 1)] + [(k, m, 1) for k, m in keeper],
              title if r == 0 else "cell ghosted")
pl.enable_anti_aliasing("ssaa")
pl.screenshot(str(OUT / "keeper-options-clay.png")); pl.close()
print("wrote", OUT / "keeper-options-clay.png")

# ---- the same for all three: the glass stops on the front wall, and the upper end (seen square from behind) ---------------
BACK = (0.0, 345.0, 0.0)
pl = pv.Plotter(off_screen=True, window_size=(2 * 760, 900), shape=(1, 2))
pl.subplot(0, 0)
scene(pl, [("body", cut_at(rp.Y_LAND + 3.2), 1), ("stop", stops(), 1)],
      "all options: glass stops (red) on the front wall, board out", BACK)
pl.subplot(0, 1)
scene(pl, [("body", cut_at(RIB_Y[1] + 0.2), 1), ("stop", stops(), 1), ("rib", merge(upper_ribs()), 1), ("glass", dummy["glass"], 1),
           ("pcb", dummy["pcb"], 1), ("plug", plug(), 1), ("stick", merge(top_end(Z_CR[0])), 1)],
      "all options: board in, the bar on both upper screws, upper ribs (violet) behind it", BACK)
pl.enable_anti_aliasing("ssaa")
pl.screenshot(str(OUT / "keeper-stops-clay.png")); pl.close()
print("wrote", OUT / "keeper-stops-clay.png")
