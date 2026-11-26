"""Concept clay, board retention v3 ("keeper"): the battery is off the board (Kapton to the back wall, not drawn), so a
printed fork slides up from the open bottom right behind the board and presses the acrylic back plate through 4 pads
near its 4 screws (the pads are what gets sanded to fit). Two short ribs per side on the shell's side walls back the
fork at the two screw rows. Notches in the JST-side prong (UART, J5, I2C, RTC) and a shortened upper rib on that side
let the cables out sideways. Plate / standoff / PCB thicknesses are ASSUMED (photos 2026-11-26): only the plate's back
face at 9.0 behind the glass front is from a measurement (to be re-measured, docs/lcd316-mechanical.md). Real pebble C shell; the rest are concept boxes.
    ~/.venvs/cad/bin/python keeper_clay.py [outdir]"""
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

def W(x, t, s):
    return (M[:3, :3] @ np.array([x, t, s])).tolist()

def merge(ms):
    return pv.merge(ms, merge_points=False)

# ---- concept numbers (mm, body frame) -------------------------------------------------------------------
PCB_T1, NUT_T1 = 8.79, 12.89                    # PCB back (1.0 assumed); the plate's back face (tallest, flat)
PLATE_T0 = NUT_T1 - 2.0                         # acrylic plate 2.0 (assumed) on brass standoffs
CONN_T1 = NUT_T1 - 1.0                          # connector tops: 1 below the plate's back face (user)
BAT_WIN = (-7.4, 6.0, 31.4, 44.9)               # plate window over the BAT connector (from the photo, +-1)
NUT_X, NUT_S = 27.35 / 2, (19.8, 92.55)
PAD = (NUT_T1, NUT_T1 + 1.5, 5.0)               # pad tips on the nuts .. fork face, pad size
FK_T = (PAD[1], PAD[1] + 2.5)                   # fork plate
RIB_T = (FK_T[1], FK_T[1] + 2.5)
SLOT_X = 8.5                                    # clears the USB adapter (x +-6) and the BAT window (x -7.4..6.0)
PRONG_X = 20.5                                  # prong's outer edge (cavity 21.4 at s 95)
EAR_X, EAR_S = 23.5, (12.0, 30.0)               # lower ears, backed by the lower ribs
FK_S = (5.0, 95.0); BRIDGE_S1 = 8.0             # bridge on the lid (z 0 = s 4.5 here), below the adapter (s 8.3)
RIB_LO = (21.5, (13.0, 31.0))                   # inner edge, s range: outside the connectors' up-move sweep (x <= 20.67)
RIB_HI = {-1: (18.5, (84.0, 96.0)),             # the connectors' up-move passes 1.0 in front of them
          1: (18.5, (89.5, 96.0))}              # JST side: starts above the RTC cable's way out
JST = {"UART": 39.25, "J5": 56.22, "I2C": 73.19, "RTC": 84.3}   # +X edge (seen from the front); RTC from the photo
CUTOUTS = ("UART", "J5", "I2C")                 # the plate's own cut-outs (RTC sits under the plate)
NOTCH = (14.5, 8.0)                             # notch from x 14.5 to the prong's edge, 8 tall

def fork(ds=0.0):
    p = [box(-EAR_X, EAR_X, *FK_T, FK_S[0] - ds, BRIDGE_S1 - ds),                         # bridge
         box(-5, 5, FK_T[1], FK_T[1] + 2.5, FK_S[0] + 0.8 - ds, BRIDGE_S1 - ds)]          # pull tab (clear of the lid)
    for sx in (-1, 1):
        cuts = sorted(JST.values()) if sx > 0 else []
        edges = [BRIDGE_S1] + [v for c in cuts for v in (c - NOTCH[1] / 2, c + NOTCH[1] / 2)] + [FK_S[1]]
        p.append(box(sx * SLOT_X, sx * NOTCH[0], *FK_T, BRIDGE_S1 - ds, FK_S[1] - ds))  # inner strip, full length
        for a, b in zip(edges[0::2], edges[1::2]):                                      # outer strip between notches
            p.append(box(sx * NOTCH[0], sx * PRONG_X, *FK_T, a - ds, b - ds))
        p.append(box(sx * PRONG_X, sx * EAR_X, *FK_T, EAR_S[0] - ds, EAR_S[1] - ds))     # lower ear
        for s in NUT_S:
            p.append(box(sx * (NUT_X - PAD[2] / 2), sx * (NUT_X + PAD[2] / 2), PAD[0], PAD[1], s - PAD[2] / 2 - ds,
                         s + PAD[2] / 2 - ds))
    return merge(p)

def ribs():
    tm = trimesh.load(D / "shell.stl"); tm0 = sum(RIB_T) / 2
    r = []
    for sides, (x_in, (s_a, s_b)) in (((-1, 1), RIB_LO), ((-1,), RIB_HI[-1]), ((1,), RIB_HI[1])):
        for s0 in np.arange(s_a, s_b, 1.0):        # stepped: each 1 mm piece runs 0.6 into the measured wall
            seg = trimesh.intersections.mesh_plane(tm, SN, SN * (s0 + 0.5))
            x = seg[..., 0]; t = seg[..., 1] * C - seg[..., 2] * S
            c = (t[:, 0] - tm0) * (t[:, 1] - tm0) < 0
            u = (tm0 - t[c, 0]) / (t[c, 1] - t[c, 0]); xc = x[c, 0] + u * (x[c, 1] - x[c, 0])
            xw = xc[xc > 0].min()
            r += [box(sx * x_in, sx * (xw + 0.6), *RIB_T, s0, min(s0 + 1.0, s_b)) for sx in sides]
    return merge(r)

def board():
    g = pv.read(D / "dummy-glass.stl")
    pcb = box(-16.675, 16.675, 7.79, PCB_T1, 16.8, 95.65)
    nuts = merge([box(sx * NUT_X - 1.75, sx * NUT_X + 1.75, PCB_T1, PLATE_T0, s - 1.75, s + 1.75)
                  for sx in (-1, 1) for s in NUT_S])                                  # brass standoffs
    cx = 16.675 - 5.0                                                                 # cut-outs reach 5 in (photo)
    pl = [box(-16.675, BAT_WIN[0], PLATE_T0, NUT_T1, 16.8, 95.65), box(BAT_WIN[1], cx, PLATE_T0, NUT_T1, 16.8, 95.65),
          box(BAT_WIN[0], BAT_WIN[1], PLATE_T0, NUT_T1, 16.8, BAT_WIN[2]),
          box(BAT_WIN[0], BAT_WIN[1], PLATE_T0, NUT_T1, BAT_WIN[3], 95.65)]
    edges = [16.8] + [v for k in CUTOUTS for v in (JST[k] - 3.5, JST[k] + 3.5)] + [95.65]
    pl += [box(cx, 16.675, PLATE_T0, NUT_T1, a, b) for a, b in zip(edges[0::2], edges[1::2])]
    jst = [box(12.2, 16.6, PCB_T1, CONN_T1, s - (2.2 if k == "RTC" else 2.8), s + (2.2 if k == "RTC" else 2.8))
           for k, s in JST.items()]
    jst.append(box(-3.5, 2.5, PCB_T1, CONN_T1, 33.0, 37.5))                           # BAT connector in the window
    tm = (PCB_T1 + CONN_T1) / 2
    cab = merge([pv.Spline(np.array([W(14.0, tm, s), W(18.0, tm + 0.2, s), W(22.0, tm + 3.0, s + 0.5),
                                     W(22.8 if k == "RTC" else 24.0, tm + 8.0, s + 1.5)]), 30).tube(radius=0.6)
                 for k, s in JST.items()])
    return dict(glass=g, pcb=pcb, nut=nuts, plate=merge(pl), jst=merge(jst), cable=cab)

shell = pv.read(D / "shell.stl")
RIB = ribs()
B = board()
adapter = pv.read(D / "dummy-adapter.stl")
COL = dict(shell="#e2d6c0", rib="#c9a97a", glass="#9aa6b2", pcb="#5f7f62", nut="#c8834a", jst="#f0f0f0", plate="#cfe3ee",
           cable="#333333", fork="#e8893a", adapter="#7a4f86")

def draw(pl, parts, clip=None, slab=None, labels=(), title="", cam=None, par=None):
    pl.set_background("#d8d5cf", top="#f3f1ed")
    for k, m, op in parts:
        if slab is not None:
            bodies = [pv.PolyData(b.extract_surface()).triangulate() for b in m.split_bodies()] if k != "shell" else [m]
            def capped(b):
                try:
                    return b.clip_closed_surface(normal=slab[0], origin=slab[1]).clip_closed_surface(normal=slab[2], origin=slab[3])
                except ValueError:                  # open meshes (cables): plain clip
                    return b.clip(normal=slab[0], origin=slab[1], invert=False).clip(normal=slab[2], origin=slab[3], invert=False)
            m = [capped(b) for b in bodies]
            m = [b for b in m if b.n_points]
            if not m:
                continue
            m = pv.merge(m)
        elif clip is not None and k in ("shell",):
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

def scene(ds):
    return [("shell", shell, 1), ("rib", RIB, 1), ("glass", B["glass"], 1), ("pcb", B["pcb"], 1), ("nut", B["nut"], 1),
            ("plate", B["plate"], 0.45), ("jst", B["jst"], 1), ("cable", B["cable"], 1), ("fork", fork(ds), 1), ("adapter", adapter, 0.3)]

# 1. cutaway from behind / below: seated, and the fork pulled down 50
ctr = W(0, 15, 45)
eye = [ctr[0] - 150, ctr[1] + 290, ctr[2] - 60]                  # behind, from the JST side, a little from below
back = (tuple(TN), W(0, RIB_T[1] + 0.3, 0))
pl = pv.Plotter(off_screen=True, window_size=(2 * 820, 920), shape=(1, 2))
pl.subplot(0, 0)
draw(pl, scene(0.0), clip=back, title="seated: 4 pads press the acrylic back plate; ribs behind the fork",
     cam=[eye, ctr, list(SN)],
     labels=[("upper rib, shortened for the RTC cable", W(21, RIB_T[1], 93)), ("lower rib", W(25, RIB_T[1], 20)),
             ("pull tab", W(0, FK_T[1] + 2.5, 6.5)), ("cable notch", W(18, FK_T[1], JST["J5"])),
             ("RTC notch", W(18, FK_T[1], JST["RTC"])), ("USB adapter (ghost)", W(0, 27, 12))])
pl.subplot(0, 1)
draw(pl, scene(50.0), clip=back, title="fork pulled 50 down: back plate, its cut-outs, plugs and cables", cam=[eye, ctr, list(SN)],
     labels=[("acrylic plate", W(-8, NUT_T1, 70)), ("RTC + cable", W(16, NUT_T1, JST["RTC"])),
             ("I2C", W(16, NUT_T1, JST["I2C"])), ("BAT window", W(0, NUT_T1, 40))])
pl.enable_anti_aliasing("ssaa"); pl.screenshot(str(OUT / "keeper-cutaway.png")); pl.close(); print(OUT / "keeper-cutaway.png")

# 2. the fork alone, its board-facing side (pads, notches), and a section across the top nut row
pl = pv.Plotter(off_screen=True, window_size=(2 * 820, 920), shape=(1, 2))
pl.subplot(0, 0)
fc = W(0, FK_T[0], 48)
draw(pl, [("fork", fork(0.0), 1)], title="fork, the side facing the board (pads by the 4 screws of the plate)",
     cam=[[fc[i] - TN[i] * 260 - SN[i] * 60 + (110 if i == 0 else 0) for i in range(3)], fc, list(SN)],
     labels=[("pad (sand to fit)", W(NUT_X, PAD[0], NUT_S[1] + 4)), ("cable notches", W(19, PAD[0], JST["I2C"])),
             ("lower ear", W(-EAR_X, FK_T[0], 33)), ("slot for the USB adapter", W(0, FK_T[0], 12))])
pl.subplot(0, 1)
s_hi, s_lo = NUT_S[1] + 0.5, NUT_S[1] - 4.0
cs = W(0, 13, s_hi)
draw(pl, scene(0.0), slab=(tuple(-SN), W(0, 0, s_hi), tuple(SN), W(0, 0, s_lo)),
     title=f"section across the face at the top screws (s {NUT_S[1]}), from above",
     cam=[[cs[i] + SN[i] * 300 for i in range(3)], cs, list(-TN)], par=30,
     labels=[("glass", W(0, 5.8, s_hi)), ("PCB", W(-3, 8.6, s_hi)), ("standoff", W(NUT_X, 9.8, s_hi)), ("plate", W(3, 11.9, s_hi)),
             ("pad", W(-NUT_X, PAD[0] + 0.7, s_hi)), ("fork", W(-4, FK_T[0] + 1.2, s_hi)), ("rib", W(-20.5, RIB_T[0] + 1.2, s_hi))])
pl.enable_anti_aliasing("ssaa"); pl.screenshot(str(OUT / "keeper-parts.png")); pl.close(); print(OUT / "keeper-parts.png")
