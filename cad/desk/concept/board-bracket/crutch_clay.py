"""Concept clay, board retention alternative ("crutch"): a printed wedge sled between the board's acrylic back plate and
the shell's BACK wall, standing on the lid. The cavity closes upward (the back wall leans 16..27 deg to the board), so
the sled is loose on the way up and tightens in the last millimetre. Two C-frames in the planes of the screw columns
(x +-13.7): prong with 2 pads on the plate, horn to the back wall at the top, rail down the back wall (touching at
s 32..40 only: the wall's belly below is an undercut), foot on the lid. The centre is open below, so the USB adapter is
plugged LAST, from below (the battery rides up through the adapter's place).
The battery rides inside the frames (shelf + strap), not in the load path. No ribs: the shell is unchanged and nothing
stands beside the board's long edges. Plate / standoff / PCB thicknesses are ASSUMED as in keeper_clay.py.
    ~/.venvs/cad/bin/python crutch_clay.py [outdir]"""
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
PAD = (NUT_T1, NUT_T1 + 1.5, 5.0)
FK_T = (PAD[1], PAD[1] + 2.5)                   # the prongs' plate
FR_X = (11.7, 15.7)                             # C-frame, in the screw column's plane; inside the PCB edge (16.67)
FK_S = (5.0, 95.0)
HORN_S = (89.5, 95.0)                           # top horn, above the battery
RAIL = 2.4                                      # back rail's thickness
BAT = (-17.5, 17.5, FK_T[1] + 0.3, FK_T[1] + 10.3, 17.8, 85.8)
STRAP = (BAT[3] + 0.8, BAT[3] + 3.3, 50.0, 53.0)    # behind the battery; passes 0.9 behind the adapter on the way up
SHELF_S = (15.3, 17.5)
FOOT_Z = (0.3, 3.3)                             # the foot strut, on the lid (lid top = z 0)
JST = {"UART": 39.25, "J5": 56.22, "I2C": 73.19, "RTC": 84.3}
CUTOUTS = ("UART", "J5", "I2C")

tm = trimesh.load(D / "shell.stl")

def wall_t(x, s):
    """Inner back wall's depth t at (x, s)."""
    seg = trimesh.intersections.mesh_plane(tm, SN, SN * s)
    xs = seg[..., 0]; t = seg[..., 1] * C - seg[..., 2] * S
    c = (xs[:, 0] - x) * (xs[:, 1] - x) < 0
    u = (x - xs[c, 0]) / (xs[c, 1] - xs[c, 0]); tc = t[c, 0] + u * (t[c, 1] - t[c, 0])
    return float(np.sort(tc[tc > 15.0])[0])

def wall_y(x, z):
    """Inner back wall's world y at (x, z)."""
    seg = trimesh.intersections.mesh_plane(tm, (0, 0, 1), (0, 0, z))
    xs = seg[..., 0]; y = seg[..., 1]
    c = (xs[:, 0] - x) * (xs[:, 1] - x) < 0
    u = (x - xs[c, 0]) / (xs[c, 1] - xs[c, 0]); yc = y[c, 0] + u * (y[c, 1] - y[c, 0])
    return float(np.sort(yc[yc > 30.0])[0])

S_GRID = np.arange(14.0, HORN_S[1], 0.5)
WALL = {round(float(s), 1): wall_t(FR_X[1], float(s) + 0.25) for s in S_GRID}     # at the frames' outer edge
Y_FOOT = wall_y(FR_X[1], sum(FOOT_Z) / 2)
FEET_S = (32.0, 40.0)                           # low back feet: above the wall's belly (s ~20), which is an undercut
_run, RAIL_T = math.inf, {}                     # the rail never reaches deeper than the wall below it (it must slide out)
for _s, _tw in WALL.items():
    _run = min(_run, _tw)
    RAIL_T[_s] = _run - (0.0 if FEET_S[0] <= _s < FEET_S[1] else 0.6)

def sled():
    p = []
    for sx in (-1, 1):
        x0, x1 = sx * FR_X[0], sx * FR_X[1]
        p.append(box(x0, x1, *FK_T, *FK_S))                                               # prong
        for s in NUT_S:                                                                   # pads on the plate
            p.append(box(sx * (NUT_X - PAD[2] / 2), sx * (NUT_X + PAD[2] / 2), PAD[0], PAD[1], s - PAD[2] / 2, s + PAD[2] / 2))
        for s0, tw in WALL.items():
            s1 = s0 + 0.5
            if s0 >= HORN_S[0]:                                                           # horn: prong to the back wall
                p.append(box(x0, x1, FK_T[1], tw, s0, s1))
            elif -tw * S + s0 * C >= FOOT_Z[0]:                                           # rail, above the lid
                p.append(box(x0, x1, RAIL_T[s0] - RAIL, RAIL_T[s0], s0, s1))
            if STRAP[2] <= s0 < STRAP[3]:                                                 # strut from the rail to the strap
                p.append(box(x0, x1, STRAP[0], RAIL_T[s0] - RAIL, s0, s1))
        p.append(wbox(x0, x1, 15.6, Y_FOOT - 1.5, *FOOT_Z))                                     # foot strut on the lid
        p.append(box(x0, x1, FK_T[1], BAT[3] + 0.5, *SHELF_S))                            # battery shelf
    p.append(box(-FR_X[1], FR_X[1], *FK_T, *HORN_S))                                      # top bar
    p.append(box(-FR_X[1], FR_X[1], STRAP[0], STRAP[1], STRAP[2], STRAP[3]))              # strap behind the battery
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
SLED = sled()
adapter = pv.read(D / "dummy-adapter.stl")
battery = box(*BAT)
rods = merge([pv.read(D / f"dummy-rod-{k}.stl") for k in "lr"])
COL = dict(shell="#e2d6c0", lid="#b98a5e", glass="#9aa6b2", pcb="#5f7f62", nut="#c8834a", jst="#f0f0f0", plate="#cfe3ee",
           cable="#333333", sled="#e8893a", adapter="#7a4f86", battery="#b9b9b9", rod="#eef3ec")

def draw(pl, parts, clip=None, labels=(), title="", cam=None, par=None):
    pl.set_background("#d8d5cf", top="#f3f1ed")
    for k, m, op in parts:
        if clip is not None and k in ("shell", "lid"):
            m = m.clip(normal=clip[0], origin=clip[1], invert=True)
        pl.add_mesh(m, color=COL[k], opacity=op, ambient=0.3, diffuse=0.75, specular=0.08)
    for txt, p in labels:
        pl.add_point_labels([p], [txt], font_size=13, point_size=1, shape_opacity=0.8, always_visible=True,
                            text_color="black", shape_color="white", margin=3)
    pl.add_text(title, font_size=11, color="black")
    pl.camera_position = cam
    if par:
        pl.camera.parallel_projection = True; pl.camera.parallel_scale = par
    else:
        pl.camera.view_angle = 24
    pl.reset_camera_clipping_range()

def scene(drop=0.0, with_lid=True, bat_op=0.55):
    off = -SN * drop
    mv = lambda m: m.translate(off, inplace=False)
    sc = [("shell", shell, 1), ("glass", B["glass"], 1), ("rod", rods, 1), ("pcb", B["pcb"], 1), ("nut", B["nut"], 1),
          ("plate", B["plate"], 0.5), ("jst", B["jst"], 1), ("cable", B["cable"], 1), ("adapter", adapter, 0.35),
          ("sled", mv(SLED), 1), ("battery", mv(battery), bat_op)]
    return sc + ([("lid", lid, 1)] if with_lid else [])

ctr = [0, 30, 50]
side = ((1, 0, 0), (17.9, 0, 0))                                  # shell cut beside the board, seen from the JST side
eye = [ctr[0] + 330, ctr[1] + 90, ctr[2] + 40]
tw_top, tw_low = WALL[92.0], WALL[30.0]
pl = pv.Plotter(off_screen=True, window_size=(3 * 760, 940), shape=(1, 3))
pl.subplot(0, 0)
draw(pl, scene(0.0), clip=side, cam=[eye, ctr, [0, 0, 1]],
     title="seated: the sled stands on the lid, wedged between the back plate and the back wall",
     labels=[("horn on the back wall", W(15.7, tw_top - 3, 93.5)), ("low back foot (rail touches here)", W(15.7, WALL[36.0], 36)),
             ("foot on the lid", [15.7, 42, 3.5]), ("pad on the plate", W(16.2, PAD[1], NUT_S[0])),
             ("battery (loose in the sled)", W(17.5, 24, 78)), ("plugs + cables: nothing beside them", W(21, 6, 64)),
             ("strap", W(15.7, STRAP[1], 51.5))])
pl.subplot(0, 1)
draw(pl, scene(22.0, with_lid=False), clip=side, cam=[eye, ctr, [0, 0, 1]],
     title="lid off, sled 22 down: free of the back wall (gap = 0.3..0.5 x the drop)",
     labels=[("gap opens", W(15.7, tw_top - 1, 80)), ("USB adapter (ghost)", W(6, 22, 12))])
pl.subplot(0, 2)
fc = W(0, 28, 50)
draw(pl, [("sled", SLED, 1), ("battery", battery, 0.3)],
     cam=[[fc[0] + 170, fc[1] - 230, fc[2] + 90], fc, [0, 0, 1]],
     title="the sled alone, from the board side (battery ghosted)",
     labels=[("pad (4)", W(NUT_X, PAD[0], NUT_S[1])), ("horn", W(15.7, WALL[92.0] - 4, 93)), ("rail", W(15.7, WALL[60.0], 60)),
             ("foot", [15.7, 35, 2]), ("battery shelf", W(15.7, 22, 15.3)), ("strap", W(0, STRAP[1], 51.5)),
             ("top bar", W(0, FK_T[0], 92))])
pl.enable_anti_aliasing("ssaa"); pl.screenshot(str(OUT / "crutch-views.png")); pl.close(); print(OUT / "crutch-views.png")
print("back wall t at the frames' outer edge:", {k: round(v, 2) for k, v in WALL.items() if k in (20.0, 30.0, 50.0, 70.0, 86.0, 92.0, 94.5)},
      "foot y", round(Y_FOOT, 2))
