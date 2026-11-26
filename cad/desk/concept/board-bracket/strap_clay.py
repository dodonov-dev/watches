"""Concept clay, board retention alternative ("strap"): ONE strap printed in the shell, wall to wall behind the board at
mid-height, far enough back that the board still enters 6.8 behind its seat. After the board is seated, the battery in
a thin printed tray slides up between the board's back plate and the strap and fills the gap: 4 pads on the plate by
its screws, the side walls' tops on the strap, legs on the lid. The battery lies loose in the tray (not in the load
path). Soft variant with the same shell: no tray, the battery with two foam strips. Assembly order as in report-A:
board, battery (tray), USB adapter from below, lid. Thicknesses ASSUMED as in keeper_clay.py.
    ~/.venvs/cad/bin/python strap_clay.py [outdir]"""

import sys, math, pathlib
import numpy as np
import pyvista as pv
import trimesh

D = pathlib.Path(__file__).resolve().parents[2] / "out-smooth" / "pebble"
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).parent
A = math.radians(15); C, S = math.cos(A), math.sin(A)
M = np.eye(4); M[1, 1:3] = (C, S); M[2, 1:3] = (-S, C)          # body (x, t, s) -> world
TN, SN = np.array([0, C, -S]), np.array([0, S, C])

def box(x0, x1, t0, t1, s0, s1):
    x0, x1 = sorted((x0, x1))
    return pv.Box((x0, x1, t0, t1, s0, s1)).triangulate().transform(M, inplace=False)

def wbox(x0, x1, y0, y1, z0, z1):                                # world-frame box (for the foot on the lid)
    x0, x1 = sorted((x0, x1))
    return pv.Box((x0, x1, y0, y1, z0, z1)).triangulate()

def W(x, t, s):
    return (M[:3, :3] @ np.array([x, t, s])).tolist()

def merge(ms):
    return pv.merge(ms, merge_points=False)

# ---- concept numbers (mm, body frame) -------------------------------------------------------------------
PCB_T1, NUT_T1 = 8.79, 12.89
PLATE_T0, CONN_T1 = NUT_T1 - 2.0, NUT_T1 - 1.0
BAT_WIN = (-7.4, 6.0, 31.4, 44.9)
NUT_X, NUT_S = 27.35 / 2, (19.8, 92.55)
JST = {"UART": 39.25, "J5": 56.22, "I2C": 73.19, "RTC": 84.3}
CUTOUTS = ("UART", "J5", "I2C")
SHIFT = 6.8                                     # the pebble's board travels up this far behind its seat (report-A)
PAD = (NUT_T1, NUT_T1 + 1.0, 5.0)               # tray pads on the plate
FLOOR = (PAD[1], PAD[1] + 1.5)                  # tray floor
POCKET = 11.2                                   # battery 10 + swelling room
WALL_T1 = FLOOR[1] + POCKET                     # the side walls' tops = the strap's front face
WALL_X = (17.7, 20.2)
BAT = (-17.5, 17.5, FLOOR[1] + 0.2, FLOOR[1] + 10.2, 17.8, 85.8)
TRAY_S = (17.8, 86.3)
STRAP_T, STRAP_S = (WALL_T1, WALL_T1 + 3.5), (52.0, 60.0)
HAUNCH = 9.0                                    # 45 deg corbels under the strap's ends: a 40 bridge instead of 58
LEG = ((8.0, 12.0), 5.2)                        # x range, bottom s (lid top is z 0)

tm = trimesh.load(D / "shell.stl")

def wall_x(s, t0):
    """Cavity half-width at depth t0, height s."""
    seg = trimesh.intersections.mesh_plane(tm, SN, SN * s)
    x = seg[..., 0]; t = seg[..., 1] * C - seg[..., 2] * S
    c = (t[:, 0] - t0) * (t[:, 1] - t0) < 0
    u = (t0 - t[c, 0]) / (t[c, 1] - t[c, 0]); xc = x[c, 0] + u * (x[c, 1] - x[c, 0])
    return float(xc[xc > 0].min())

def strap():
    p, tmid = [], sum(STRAP_T) / 2
    for s0 in np.arange(STRAP_S[0] - HAUNCH, STRAP_S[1], 1.0):
        xw = wall_x(s0 + 0.5, tmid)
        if s0 >= STRAP_S[0]:
            p.append(box(-xw - 0.6, xw + 0.6, *STRAP_T, s0, s0 + 1.0))
        else:                                                                             # corbel, 45 deg underside
            d = s0 - (STRAP_S[0] - HAUNCH) + 1.0
            p += [box(sx * (xw - d), sx * (xw + 0.6), *STRAP_T, s0, s0 + 1.0) for sx in (-1, 1)]
    return merge(p)

def tray(ds=0.0):
    a, b = TRAY_S[0] - ds, TRAY_S[1] - ds
    p = [box(-WALL_X[1], -8.0, *FLOOR, a, b), box(7.0, WALL_X[1], *FLOOR, a, b),          # floor, slot for the BAT lead
         box(-8.0, 7.0, *FLOOR, 46.5 - ds, b)]
    for sx in (-1, 1):
        p.append(box(sx * WALL_X[0], sx * WALL_X[1], FLOOR[1], WALL_T1, a, b))            # side wall, its top on the strap
        p.append(box(sx * 6.8, sx * WALL_X[1], FLOOR[0], FLOOR[1] + 6.0, a - 2.5, a))     # lip under the battery
        p.append(box(sx * LEG[0][0], sx * LEG[0][1], FLOOR[0], FLOOR[0] + 3.0, LEG[1] - ds, a - 2.5))   # leg on the lid
        p.append(box(sx * (NUT_X - 2.5), sx * (NUT_X + 2.5), *FLOOR, b, 95.0 - ds))       # finger to the top screw
        for s in NUT_S:
            p.append(box(sx * (NUT_X - PAD[2] / 2), sx * (NUT_X + PAD[2] / 2), PAD[0], PAD[1], s - PAD[2] / 2 - ds, s + PAD[2] / 2 - ds))
    return merge(p)

def board():
    g = pv.read(D / "dummy-glass.stl")
    pcb = box(-16.675, 16.675, 7.79, PCB_T1, 16.8, 95.65)
    nuts = merge([box(sx * NUT_X - 1.75, sx * NUT_X + 1.75, PCB_T1, PLATE_T0, s - 1.75, s + 1.75)
                  for sx in (-1, 1) for s in NUT_S])
    cx = 16.675 - 5.0
    pl = [box(-16.675, BAT_WIN[0], PLATE_T0, NUT_T1, 16.8, 95.65), box(BAT_WIN[1], cx, PLATE_T0, NUT_T1, 16.8, 95.65),
          box(BAT_WIN[0], BAT_WIN[1], PLATE_T0, NUT_T1, 16.8, BAT_WIN[2]),
          box(BAT_WIN[0], BAT_WIN[1], PLATE_T0, NUT_T1, BAT_WIN[3], 95.65)]
    edges = [16.8] + [v for k in CUTOUTS for v in (JST[k] - 3.5, JST[k] + 3.5)] + [95.65]
    pl += [box(cx, 16.675, PLATE_T0, NUT_T1, a, b) for a, b in zip(edges[0::2], edges[1::2])]
    jst = [box(12.2, 16.6, PCB_T1, CONN_T1, s - (2.2 if k == "RTC" else 2.8), s + (2.2 if k == "RTC" else 2.8))
           for k, s in JST.items()]
    plug = [box(16.6, 20.67, PCB_T1 + 0.3, CONN_T1 - 0.3, s - 2.2, s + 2.2) for s in JST.values()]
    tmid = (PCB_T1 + CONN_T1) / 2
    cab = merge([pv.Spline(np.array([W(20.0, tmid, s), W(23.0, tmid + 0.6, s), W(25.0, tmid + 4.0, s - 1.0),
                                     W(25.5 if s < 80 else 23.0, tmid + 12.0, s - 4.0)]), 30).tube(radius=0.6)
                 for s in JST.values()])
    return dict(glass=g, pcb=pcb, nut=nuts, plate=merge(pl), jst=merge(jst + plug), cable=cab)

shell, lid = pv.read(D / "shell.stl"), pv.read(D / "lid.stl")
B = board()
STRAP = strap()
adapter = pv.read(D / "dummy-adapter.stl")
rods = merge([pv.read(D / f"dummy-rod-{k}.stl") for k in "lr"])
COL = dict(shell="#e2d6c0", lid="#b98a5e", glass="#9aa6b2", pcb="#5f7f62", nut="#c8834a", jst="#f0f0f0", plate="#cfe3ee",
           cable="#333333", tray="#e8893a", strap="#b5651d", adapter="#7a4f86", battery="#b9b9b9", rod="#eef3ec")

def draw(pl, parts, clip=None, labels=(), title="", cam=None):
    pl.set_background("#d8d5cf", top="#f3f1ed")
    for k, m, op in parts:
        if clip is not None and k in ("shell", "lid", "strap"):
            m = m.clip(normal=clip[0], origin=clip[1], invert=True)
        pl.add_mesh(m, color=COL[k], opacity=op, ambient=0.3, diffuse=0.75, specular=0.08)
    for txt, p in labels:
        pl.add_point_labels([p], [txt], font_size=13, point_size=1, shape_opacity=0.8, always_visible=True,
                            text_color="black", shape_color="white", margin=3)
    pl.add_text(title, font_size=11, color="black")
    pl.camera_position = cam
    pl.camera.view_angle = 24
    pl.reset_camera_clipping_range()

def scene(ds=0.0, with_lid=True, board_dt=0.0, with_tray=True):
    mv = lambda m: m.translate(TN * board_dt, inplace=False)
    sc = [("shell", shell, 1), ("strap", STRAP, 1), ("glass", mv(B["glass"]), 1), ("rod", mv(rods), 1), ("pcb", mv(B["pcb"]), 1),
          ("nut", mv(B["nut"]), 1), ("plate", mv(B["plate"]), 0.5), ("jst", mv(B["jst"]), 1), ("cable", mv(B["cable"]), 1)]
    if with_tray:
        sc += [("adapter", adapter, 0.35), ("tray", tray(ds), 1), ("battery", box(*BAT).translate(-SN * ds, inplace=False), 0.55)]
    return sc + ([("lid", lid, 1)] if with_lid else [])

ctr = [0, 30, 50]
side = ((1, 0, 0), (21.5, 0, 0))                                  # cut beside the tray, seen from the JST side
eye = [ctr[0] + 330, ctr[1] + 90, ctr[2] + 40]
pl = pv.Plotter(off_screen=True, window_size=(4 * 640, 940), shape=(1, 4))
pl.subplot(0, 0)
draw(pl, scene(with_tray=False, with_lid=False, board_dt=SHIFT), clip=side, cam=[eye, ctr, [0, 0, 1]],
     title=f"1. board going up, {SHIFT} behind its seat: passes in front of the strap",
     labels=[("strap (part of the shell)", W(21.5, STRAP_T[1], 56)), ("board on its way up", W(21, NUT_T1 + SHIFT, 75))])
pl.subplot(0, 1)
draw(pl, scene(ds=30.0, with_lid=False), clip=side, cam=[eye, ctr, [0, 0, 1]],
     title="2. board seated; battery tray sliding up between plate and strap",
     labels=[("tray + battery", W(20.2, 22, 20))])
pl.subplot(0, 2)
draw(pl, scene(), clip=side, cam=[eye, ctr, [0, 0, 1]],
     title="3. seated: pads on the plate, side walls on the strap, legs on the lid",
     labels=[("strap", W(21.5, STRAP_T[1], 56)), ("side wall's top bears on the strap", W(20.2, WALL_T1, 70)),
             ("pad on the plate", W(16.2, PAD[1], NUT_S[1])), ("leg on the lid", W(12, FLOOR[0] + 3, 8)),
             ("plugs + cables free", W(21, 6, 46))])
pl.subplot(0, 3)
fc = W(0, 20, 52)
draw(pl, [("tray", tray(), 1), ("battery", box(*BAT), 0.3), ("strap", STRAP, 0.6)],
     cam=[[fc[0] + 150, fc[1] - 250, fc[2] + 60], fc, [0, 0, 1]],
     title="tray from the board side (strap behind it, battery ghosted)",
     labels=[("pad (4)", W(NUT_X, PAD[0], NUT_S[0])), ("slot for the battery lead", W(0, FLOOR[0], 32)),
             ("side wall", W(WALL_X[1], 20, 75)), ("leg", W(10, FLOOR[0], 9)), ("strap + corbel", W(26, STRAP_T[0], 54))])
pl.enable_anti_aliasing("ssaa"); pl.screenshot(str(OUT / "strap-views.png")); pl.close(); print(OUT / "strap-views.png")
print("strap t", STRAP_T, "span", round(2 * wall_x(56.5, sum(STRAP_T) / 2), 1), "entry clearance", round(STRAP_T[0] - NUT_T1 - SHIFT, 2))

# ---- soft variant, same strap: no tray; the battery on two foam strips fills the gap, a foot on the lid under it ------
FOAM_T = (NUT_T1, WALL_T1 - 10.0)               # 3.7: 4 mm strips squeezed 0.3 where the strap presses
BATF = (-17.5, 17.5, FOAM_T[1], WALL_T1, 17.8, 85.8)
STRIP_X, STRIP_S = (9.0, 15.0), (20.0, 84.0)    # beside the BAT window (x -7.4..6.0); stuck to the battery
FOOT_XY = ((9.0, 15.0), (21.5, 29.5))           # lid foot under the battery's bottom face (world x, y), clear of the adapter
COL.update(foam="#f2d94e", lead="#b03030", foot="#8a5f3a")

def soft(ds=0.0):
    off = -SN * ds
    strips = merge([box(sx * STRIP_X[0], sx * STRIP_X[1], *FOAM_T, *STRIP_S) for sx in (-1, 1)])
    tg = sum(FOAM_T) / 2
    lead = pv.Spline(np.array([W(-0.5, (PCB_T1 + CONN_T1) / 2, 35.5), W(-0.5, tg, 32.5), W(-1.5, tg, 24.0), W(-7.5, tg, 18.5),
                               W(-8.0, tg + 2.0, 16.6), W(-8.0, BATF[2] + 4.0, 17.0)]), 40).tube(radius=0.7)
    return [("foam", strips.translate(off, inplace=False), 1), ("battery", box(*BATF).translate(off, inplace=False), 0.6),
            ("lead", lead.translate(off, inplace=False), 1)]

def lid_foot():
    p = []
    for sx in (-1, 1):
        for y in np.arange(FOOT_XY[1][0], FOOT_XY[1][1], 1.0):      # top follows the battery's bottom face (s 17.8), 0.2 under it
            p.append(wbox(sx * FOOT_XY[0][0], sx * FOOT_XY[0][1], y, y + 1.0, 0.0, (17.6 - (y + 0.5) * S) / C))
    return merge(p)

base = [k for k in scene(with_tray=False, with_lid=False)]
pl = pv.Plotter(off_screen=True, window_size=(3 * 760, 940), shape=(1, 3))
pl.subplot(0, 0)
draw(pl, base + soft(30.0), clip=side, cam=[eye, ctr, [0, 0, 1]],
     title="1. board seated; the battery with its two foam strips sliding up between plate and strap",
     labels=[("strap (part of the shell)", W(21.5, STRAP_T[1], 56)), ("battery", W(17.5, 22, 25)),
             ("foam strip", W(15, FOAM_T[1], 0))])
pl.subplot(0, 1)
draw(pl, base + soft() + [("adapter", adapter, 0.35), ("lid", lid, 1), ("foot", lid_foot(), 1)], clip=side, cam=[eye, ctr, [0, 0, 1]],
     title="2. seated: the strap presses the battery, the foam presses the plate; a foot on the lid under the battery",
     labels=[("strap on the battery's back", W(21.5, STRAP_T[1], 56)), ("foam strip (3.7 of gap)", W(15, FOAM_T[1], 74)),
             ("foot on the lid", [15, 30, 6]), ("plugs + cables free", W(21, 6, 46)), ("battery lead", W(-8, 18, 16))])
pl.subplot(0, 2)
fc = W(0, 20, 50)
draw(pl, soft() + [("strap", STRAP, 0.6), ("foot", lid_foot(), 1), ("plate", B["plate"], 0.25), ("jst", B["jst"], 0.5)],
     cam=[[fc[0] + 150, fc[1] - 250, fc[2] + 60], fc, [0, 0, 1]],
     title="battery from the board side (back plate ghosted): strips beside the lead's window",
     labels=[("foam strip", W(12, FOAM_T[0], 70)), ("foam strip", W(-12, FOAM_T[0], 60)), ("lead from the BAT socket", W(-0.5, FOAM_T[0], 33)),
             ("strap", W(26, STRAP_T[0], 56)), ("foot (lid)", [12, 22, 4])])
pl.enable_anti_aliasing("ssaa"); pl.screenshot(str(OUT / "strap-foam-views.png")); pl.close(); print(OUT / "strap-foam-views.png")
