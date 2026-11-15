#!/usr/bin/env python3
"""Clay views of a massing study: ~/.venvs/cad/bin/python clay.py <tag> [scheme]"""
import sys, pathlib
import pyvista as pv

tag = sys.argv[1] if len(sys.argv) > 1 else "a"
scheme = sys.argv[2] if len(sys.argv) > 2 else "two"
OUT = pathlib.Path(__file__).parent / f"out-{tag}"
SCHEMES = {
    "two": {"ribbon": "#ece6d8", "cradle": "#6b4a34", "plinth": "#1c1c1c"},
    "mono": {"ribbon": "#d9b98a", "cradle": "#d2b183", "plinth": "#1c1c1c"},
    "dark": {"ribbon": "#2b2b2d", "cradle": "#c9a777", "plinth": "#141414"},
}
COL = dict(SCHEMES[scheme], **{"glass": "#0c0c0e", "rod-l": "#7fc4e8", "rod-r": "#7fc4e8", "logo": "#ffb347"})
meshes = {k: pv.read(str(OUT / f"{k}.stl")) for k in COL}
allm = pv.merge(list(meshes.values()))
c = list(allm.center)

VIEWS = {  # name: (direction to the camera, parallel?)
    "hero": ((-0.62, -1.0, 0.36), False),
    "hero-right": ((0.75, -1.0, 0.30), False),
    "rear": ((0.8, 1.0, 0.38), False),
    "rear-left": ((-0.85, 1.0, 0.36), False),
    "left": ((-1.0, -0.38, 0.30), False),
    "front": ((0, -1, 0), True),
    "side": ((-1, 0, 0), True),
    "top": ((-0.25, -0.55, 1.0), False),
}


def shot(names, fname, size=(900, 1100)):
    pl = pv.Plotter(off_screen=True, window_size=(size[0] * len(names), size[1]), shape=(1, len(names)))
    for i, n in enumerate(names):
        d, par = VIEWS[n]
        pl.subplot(0, i)
        pl.set_background("#d8d5cf", top="#f3f1ed")
        for k, m in meshes.items():
            rod = k.startswith("rod")
            pl.add_mesh(m.compute_normals(feature_angle=30, split_vertices=True), color=COL[k], smooth_shading=True,
                        specular=0.6 if rod else 0.08, specular_power=40 if rod else 8, ambient=0.28, diffuse=0.8)
        ground = pv.Plane(center=(c[0], c[1], allm.bounds[4] - 0.01), direction=(0, 0, 1), i_size=600, j_size=600)
        pl.add_mesh(ground, color="#cfcac2", ambient=0.5, diffuse=0.6)
        nrm = sum(x * x for x in d) ** 0.5
        dist = allm.length * (4.0 if not par else 2.5)
        pl.camera_position = [tuple(c[j] + d[j] / nrm * dist for j in range(3)), tuple(c), (0, 0, 1)]
        if par:
            pl.camera.parallel_projection = True
            pl.camera.parallel_scale = allm.length * 0.56
        else:
            pl.camera.view_angle = 17
        pl.reset_camera_clipping_range()
    pl.enable_anti_aliasing("ssaa")
    pl.screenshot(str(OUT / fname))
    pl.close()
    print(OUT / fname)


shot(["hero", "left", "rear"], f"clay-{scheme}-hero.png")
shot(["front", "side", "top"], f"clay-{scheme}-ortho.png", size=(700, 1000))
shot(["rear-left"], f"clay-{scheme}-rear-left.png")


# close-ups of the slot ends (massing.py writes the focus points)
import json
fp = OUT / "focus.json"
if fp.exists():
    f = json.loads(fp.read_text())
    n, up = f["normal"], f["up"]
    pl = pv.Plotter(off_screen=True, window_size=(2400, 900), shape=(1, 3))
    # top end seen from above the tube, top end seen along the face from below, bottom end seen from above
    cams = [("top", 0.9, 0.55), ("top", 0.9, -0.55), ("bottom", 0.9, 0.55)]
    for i, (end, kn, ku) in enumerate(cams):
        pl.subplot(0, i)
        pl.set_background("#d8d5cf", top="#f3f1ed")
        for k, m in meshes.items():
            rod = k.startswith("rod")
            pl.add_mesh(m.compute_normals(feature_angle=30, split_vertices=True), color=COL[k], smooth_shading=True,
                        specular=0.6 if rod else 0.08, specular_power=40 if rod else 8, ambient=0.3, diffuse=0.8,
                        opacity=0.55 if rod else 1.0)
        c0 = f[end]
        d = [kn * n[j] + ku * up[j] + (-0.35 if j == 0 else 0) for j in range(3)]
        nn = sum(x * x for x in d) ** 0.5
        pl.camera_position = [tuple(c0[j] + d[j] / nn * 120 for j in range(3)), tuple(c0), tuple(up)]
        pl.camera.view_angle = 9
        pl.reset_camera_clipping_range()
    pl.enable_anti_aliasing("ssaa")
    pl.screenshot(str(OUT / f"clay-{scheme}-ends.png"))
    pl.close()
    print(OUT / f"clay-{scheme}-ends.png")
