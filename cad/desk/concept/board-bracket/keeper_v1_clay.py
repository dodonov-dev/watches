"""Concept clay, simplest board retention ("keeper", Fable's pick): two ribs on the shell's side walls, one printed
fork that slides up from the open bottom between the battery and the ribs, foam strips on its prongs pressing the
battery (taped to the PCB as today) forward. Only the holding parts are drawn; the adapter is a ghost because it sets
the fork's slot. Real pebble C shell; the rest are concept boxes.
    ~/.venvs/cad/bin/python keeper_clay.py [outdir]"""
import sys, math, pathlib
import numpy as np
import pyvista as pv

D = pathlib.Path(__file__).resolve().parents[2] / "out-smooth" / "pebble"
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).parent
A = math.radians(15); C, S = math.cos(A), math.sin(A)
M = np.eye(4); M[1, 1:3] = (C, S); M[2, 1:3] = (-S, C)          # body (x, t, s) -> world
TN, SN = np.array([0, C, -S]), np.array([0, S, C])

def box(x0, x1, t0, t1, s0, s1):
    return pv.Box((x0, x1, t0, t1, s0, s1)).triangulate().transform(M, inplace=False)

def W(x, t, s):
    return (M[:3, :3] @ np.array([x, t, s])).tolist()

# ---- concept numbers (mm, body frame) -------------------------------------------------------------------
BAT_T1 = 22.99                       # battery back (dummy)
FOAM = (BAT_T1, BAT_T1 + 1.5)        # 2 mm foam, 1.5 compressed
FK_T = (FOAM[1], FOAM[1] + 2.5)      # fork plate
SLOT_X = 7.5                         # clears the adapter (x +-6, back face t 26.9)
FK_X = 24.0
FK_S = (2.5, 80.0)                   # bridge on the lid plug, prongs to s 80
BRIDGE_S1 = 7.5                      # bridge top: below the adapter (s 8.3)
RIB_X = 21.5                         # rib's inner edge
RIB_S = (14.0, 78.0)

def fork(ds=0.0):
    p = [box(-FK_X, FK_X, *FK_T, FK_S[0] - ds, BRIDGE_S1 - ds)]                      # bridge
    for sx in (-1, 1):
        p.append(box(*sorted((sx * SLOT_X, sx * FK_X)), *FK_T, BRIDGE_S1 - ds, FK_S[1] - ds))   # prong
    p.append(box(-6, 6, FK_T[0], FK_T[1] + 4, FK_S[0] - ds, FK_S[0] + 2 - ds))        # finger tab
    foam = [box(*sorted((sx * (SLOT_X + 0.5), sx * 17.0)), *FOAM, 22 - ds, 76 - ds) for sx in (-1, 1)]
    return pv.merge(p, merge_points=False), pv.merge(foam, merge_points=False)

def ribs():
    sh = pv.read(D / "shell.stl")
    # each rib: from the side wall in to RIB_X, just behind the fork (clipped by the wall later visually: overlap ok)
    import trimesh
    tm = trimesh.load(D / "shell.stl"); tm0 = FK_T[1] + 1.25
    r = []
    for s0 in np.arange(RIB_S[0], RIB_S[1], 1.0):          # stepped: each 2 mm piece runs 0.6 into the measured wall
        sc = s0 + 0.5
        seg = trimesh.intersections.mesh_plane(tm, SN, SN * sc)
        x = seg[..., 0]; t = seg[..., 1] * C - seg[..., 2] * S
        c = (t[:, 0] - tm0) * (t[:, 1] - tm0) < 0
        u = (tm0 - t[c, 0]) / (t[c, 1] - t[c, 0]); xc = x[c, 0] + u * (x[c, 1] - x[c, 0])
        xw = xc[xc > 0].min()
        r += [box(*sorted((sx * RIB_X, sx * (xw + 0.6))), FK_T[1], FK_T[1] + 2.5, s0, s0 + 1.0) for sx in (-1, 1)]
    return sh, pv.merge(r, merge_points=False)

shell, rib = ribs()
glass = pv.read(D / "dummy-glass.stl"); board = pv.read(D / "dummy-board.stl"); bat = pv.read(D / "dummy-battery.stl")
adapter = pv.read(D / "dummy-adapter.stl")
# ribs only inside the shell: clip them to the cavity side of the wall by intersecting with a slab (cheap: keep as is,
# the part outside the wall is hidden inside the wall's material in these views)

COL = dict(shell="#e2d6c0", rib="#c9a97a", glass="#9aa6b2", board="#7f8a80", battery="#b9b9b9", fork="#e8893a",
           foam="#f2d04a", adapter="#7a4f86")

def panel(pl, ds, clip, title, cam, par=None, labels=(), floor=None):
    fk, fm = fork(ds)
    sh = shell.clip(normal=clip[0], origin=clip[1], invert=True)
    if floor is not None:                       # capped slab between floor and clip planes (closed meshes)
        slab = lambda m: m.clip_closed_surface(normal=tuple(-np.array(clip[0])), origin=clip[1]).clip_closed_surface(
            normal=floor[0], origin=floor[1])
        sh = slab(shell)
    pl.set_background("#d8d5cf", top="#f3f1ed")
    pl.add_mesh(sh, color=COL["shell"], ambient=0.3, diffuse=0.75, specular=0.05)
    def cut(m):
        if floor is not None:
            out = [slab(pv.PolyData(bd.extract_surface()).triangulate()) for bd in m.split_bodies()]
            out = [o for o in out if o.n_points]
            return pv.merge(out) if out else pv.PolyData()
        return m.clip(normal=clip[0], origin=clip[1], invert=True) if clip[2] else m
    for m, k, op in ((rib, "rib", 1), (glass, "glass", 1), (board, "board", 1), (bat, "battery", 1),
                     (fk, "fork", 1), (fm, "foam", 1), (adapter, "adapter", 0.35)):
        mm = cut(m)
        if mm.n_points:
            pl.add_mesh(mm, color=COL[k], opacity=op, ambient=0.3, diffuse=0.75, specular=0.08)
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

ctr = W(0, 22, 40)
eye = [ctr[0] + 140, ctr[1] + 290, ctr[2] - 75]                  # behind, right, from below (the open bottom)
back = (tuple(TN), W(0, FK_T[1] + 2.6, 0), False)                 # shell cut just behind the ribs

pl = pv.Plotter(off_screen=True, window_size=(2 * 820, 900), shape=(1, 2))
pl.subplot(0, 0)
panel(pl, 0.0, back, "seated: fork pushes the battery -> board -> front wall", [eye, ctr, list(SN)],
      labels=[("rib (shell)", W(-26, FK_T[1] + 1.2, 60)), ("fork", W(15, FK_T[1], 50)),
("finger tab", W(0, FK_T[1] + 4, FK_S[0])),
              ("USB adapter (ghost)", W(0, 26, 12))])
pl.subplot(0, 1)
panel(pl, 45.0, back, "fork pulled 45 mm down: board free, drops back 4 mm", [eye, ctr, list(SN)])
pl.enable_anti_aliasing("ssaa"); pl.screenshot(str(OUT / "keeper-v1-cutaway.png")); pl.close(); print(OUT / "keeper-v1-cutaway.png")

# section across the face at s 50, seen from above (everything above the plane removed)
cs = W(0, 18, 50)
pl = pv.Plotter(off_screen=True, window_size=(900, 760))
panel(pl, 0.0, (tuple(SN), W(0, 0, 50), True), "section at mid-height, from above: front wall -> glass -> PCB -> battery -> foam -> fork -> ribs",
      [[cs[i] + SN[i] * 300 for i in range(3)], cs, list(-TN)], par=26, floor=(tuple(SN), W(0, 0, 44)),
      labels=[("foam", W(12, FOAM[1] - 0.5, 50)), ("fork", W(-20, FK_T[1] - 1, 50)), ("rib (shell)", W(26, FK_T[1] + 1.5, 50)),
              ("battery", W(0, 18, 50)), ("PCB + parts", W(0, 10.5, 50)), ("glass", W(0, 5.8, 50))])
pl.enable_anti_aliasing("ssaa"); pl.screenshot(str(OUT / "keeper-v1-section.png")); pl.close(); print(OUT / "keeper-v1-section.png")
