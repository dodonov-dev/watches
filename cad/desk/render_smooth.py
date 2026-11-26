#!/usr/bin/env python3
"""Preview PNGs of the smooth housing (out-smooth/<variant>/*.stl), feature edges drawn so cuts and seams show.

  shell-views.png         front, left, top, back
  shell-iso.png           iso front-left, iso back-right
  lid-views.png           lid from above and below
  assembly-views.png      shell + lid + dummies (board, glass, rods, battery, adapter, buttons, plugs)
  section-x-views.png     cut through the right tube's axis, seen from +X: roll, ceiling, board, battery, adapter
  detail-slot-end.png     close-up of the top end of the left slot
  detail-logo.png         the logo from outside

Run after smooth.py: ~/.venvs/cad/bin/python cad/desk/render_smooth.py [variant ...]
"""
import sys, json, pathlib
import pyvista as pv

ROOT = pathlib.Path(__file__).parent / "out-smooth"
VIEWS = {   # camera direction (from the object towards the camera), up
    "front": ((0, -1, 0), (0, 0, 1)), "back": ((0, 1, 0), (0, 0, 1)),
    "left": ((-1, 0, 0), (0, 0, 1)), "right": ((1, 0, 0), (0, 0, 1)),
    "top": ((0, 0, 1), (0, 1, 0)), "bottom": ((0, 0, -1), (0, 1, 0)),
    "iso-front-left": ((-1, -1.3, 0.8), (0, 0, 1)), "iso-back-right": ((1, 1.3, 0.8), (0, 0, 1)),
    "iso-under-back": ((0.6, 1.3, -1.0), (0, 0, 1)), "iso-top": ((-0.6, -0.8, 1.6), (0, 0, 1)),
    "slot-top": ((-0.7, -1.0, 0.9), (0, 0, 1)), "slot-bottom": ((-0.7, -1.0, -0.5), (0, 0, 1)),
}
COLORS = {"shell": "tan", "lid": "sienna", "fork": "darkorange", "glass": "steelblue", "board": "darkgreen", "rod-l": "lightcyan",
          "rod-r": "lightcyan", "battery": "silver", "adapter": "purple"}


def color(name):
    for k, c in (("button", "red"), ("plug", "gold")):
        if name.startswith(k):
            return c
    return COLORS.get(name, "gray")


def render(out, name, meshes, views, size=500, height=700, focus=None, half=None, edges=True, smooth=True):
    pl = pv.Plotter(off_screen=True, window_size=(size * len(views), height), shape=(1, len(views)))
    allm = pv.merge([m for m, _ in meshes])
    r = allm.length
    for i, v in enumerate(views):
        d, up = VIEWS[v]
        pl.subplot(0, i)
        for m, col in meshes:
            pl.add_mesh(m, color=col, specular=0.3, smooth_shading=smooth, split_sharp_edges=True)
            if edges:
                pl.add_mesh(m.extract_feature_edges(35, boundary_edges=False, manifold_edges=False), color="black", line_width=1)
        pl.add_text(v, font_size=10)
        f = focus[i] if focus and isinstance(focus[0], (list, tuple)) else focus
        c = f or allm.center
        n = sum(x * x for x in d) ** 0.5
        pl.camera_position = [tuple(c[k] + d[k] / n * r * 2.2 for k in range(3)), tuple(c), up]
        pl.camera.parallel_projection = True
        if half:
            pl.camera.parallel_scale = half
            pl.reset_camera_clipping_range()
        else:
            pl.reset_camera()
    pl.screenshot(str(out / f"{name}.png"))
    pl.close()
    print(out / f"{name}.png")


def run(variant):
    out = ROOT / variant
    focus = json.loads((out / "focus.json").read_text())
    rd = lambda n: (pv.read(str(out / f"{n}.stl")), color(n))
    shell, lid = [rd("shell")], [rd("lid")]
    dummies = [(pv.read(str(f)), color(f.stem[len("dummy-"):])) for f in sorted(out.glob("dummy-*.stl"))]
    section = [(pv.read(str(f)), color(f.stem[len("section-x-"):])) for f in sorted(out.glob("section-x-*.stl"))]
    render(out, "shell-views", shell, ["front", "left", "top", "back"], size=450, height=750)
    render(out, "shell-iso", shell, ["iso-front-left", "iso-back-right", "iso-under-back"], size=600, height=750)
    render(out, "lid-views", lid, ["top", "bottom", "iso-front-left"], size=450, height=500)
    render(out, "assembly-views", shell + lid + dummies, ["front", "left", "iso-front-left", "iso-under-back"], size=500, height=750)
    render(out, "section-x-views", section, ["right"], size=800, height=1100)
    rods = [m for m in dummies if m[1] == "lightcyan"]
    render(out, "detail-slot-end", shell + rods, ["slot-top", "slot-bottom", "front"], size=700, height=700,
           focus=[focus["slot_top"], focus["slot_bottom"], focus["slot_top"]], half=10, smooth=False)
    if "logo_normal" in focus:                         # oval, pebble: look at the logo along its normal; mid-height section from above
        nx, ny, nz = focus["logo_normal"]            # the pebble's front leans back: its normal points a little up
        VIEWS["logo-outside"] = ((nx, ny, nz), (0, 0, 1))
        VIEWS["logo-inside"] = ((-nx, -ny, -nz), (0, 0, 1))
        lw = [(pv.read(str(out / "section-l-shell.stl")), "tan")]
        render(out, "detail-logo", lw, ["logo-outside", "logo-inside"], size=700, height=600, focus=focus["logo"], half=9, smooth=False)
    else:
        render(out, "detail-logo", shell, ["left"], size=800, height=600, focus=focus["logo"], half=16)
    if (out / "teststrip.stl").exists():
        ts = [(pv.read(str(out / "teststrip.stl")), "tan")]
        render(out, "teststrip-views", ts, ["front", "iso-front-left", "back", "top"], size=450, height=750, smooth=False)
    zsec = [(pv.read(str(f)), color(f.stem[len("section-z-"):])) for f in sorted(out.glob("section-z-*.stl"))]
    if zsec:
        render(out, "section-z-views", zsec, ["top"], size=900, height=700)


for v in sys.argv[1:] or sorted(p.name for p in ROOT.iterdir() if p.is_dir()):
    run(v)
if (ROOT / "logo-inlays-small.stl").exists():
    render(ROOT, "logo-inlays-small-views", [(pv.read(str(ROOT / "logo-inlays-small.stl")), "khaki")], ["top", "iso-front-left"],
           size=600, height=600, smooth=False)
