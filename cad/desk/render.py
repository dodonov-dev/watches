#!/usr/bin/env python3
"""Preview PNGs of the housing (out/*.stl), with feature edges drawn so through-cuts show.

  <part>-views.png      shell, lid, carrier, lightbox, teststrip, assembly: axis views + iso views
  section-x-views.png   cut through the right tube's axis, seen from +X
  section-y-views.png   cut through the logo's centre, seen from the front: whole, and the light box close up
  section-z-views.png   cut through the logo's centre, seen from above: assembled
  section-ins-views.png the same cut with the board 4.5 mm further back (the up move of the insertion)
  detail-*.png          close-ups: slot bevel, logo from outside, light box in the y and z sections

Run after housing.py: ~/.venvs/cad/bin/python cad/desk/render.py [name ...]
"""
import sys, pathlib
import pyvista as pv

OUT = pathlib.Path(__file__).parent / "out"
VIEWS = {   # camera direction (from the object towards the camera), up
    "front": ((0, -1, 0), (0, 0, 1)), "back": ((0, 1, 0), (0, 0, 1)),
    "left": ((-1, 0, 0), (0, 0, 1)), "right": ((1, 0, 0), (0, 0, 1)),
    "top": ((0, 0, 1), (0, 1, 0)), "bottom": ((0, 0, -1), (0, 1, 0)),
    "iso-front-left": ((-1, -1.3, 0.8), (0, 0, 1)), "iso-back-right": ((1, 1.3, 0.8), (0, 0, 1)),
    "iso-back-left": ((-1, 1.3, 0.8), (0, 0, 1)), "iso-front-right": ((1, -1.3, 0.8), (0, 0, 1)),
    "iso-under-back": ((0.6, 1.3, -1.0), (0, 0, 1)), "iso-under-front": ((-0.6, -1.3, -1.0), (0, 0, 1)),
    "iso-top-left": ((-1.2, -0.5, 1.0), (0, 0, 1)),
}
COLORS = {"shell": "tan", "lid": "sienna", "carrier": "lightgreen", "lightbox": "orange", "opal": "white",
          "glass": "steelblue", "board": "darkgreen", "rod-l": "lightcyan", "rod-r": "lightcyan", "battery": "silver",
          "breakout": "purple", "socket": "black", "teststrip": "tan", "assembly": "tan"}


def color(name):
    for k in ("button", "plug", "carrier"):
        if name.startswith(k):
            return {"button": "red", "plug": "gold", "carrier": "lightgreen"}[k]
    return COLORS.get(name, "gray")


def render(name, meshes, views, size=500, height=640, focus=None, half=None):
    """focus + half: a close-up centred on focus, half mm from the centre to the top of the picture."""
    pl = pv.Plotter(off_screen=True, window_size=(size * len(views), height), shape=(1, len(views)))
    allm = pv.merge([m for m, _ in meshes])
    c, r = (focus or allm.center), allm.length
    for i, v in enumerate(views):
        d, up = VIEWS[v]
        pl.subplot(0, i)
        for m, col in meshes:
            pl.add_mesh(m, color=col, specular=0.2)
            pl.add_mesh(m.extract_feature_edges(35, boundary_edges=False, manifold_edges=False), color="black", line_width=1)
        pl.add_text(v, font_size=10)
        n = sum(x * x for x in d) ** 0.5
        pl.camera_position = [tuple(c[k] + d[k] / n * r * 2.2 for k in range(3)), tuple(c), up]
        pl.camera.parallel_projection = True
        if half:
            pl.camera.parallel_scale = half
            pl.reset_camera_clipping_range()
        else:
            pl.reset_camera()
    pl.screenshot(str(OUT / f"{name}.png"))
    pl.close()
    print(OUT / f"{name}.png")


def part(name):
    return [(pv.read(str(OUT / f"{name}.stl")), color(name))]


def assembly():
    """The printed parts + the dummies, each in its colour."""
    names = ["shell", "lid", "carrier", "lightbox", "opal"]
    ms = [(pv.read(str(OUT / f"{n}.stl")), color(n)) for n in names if (OUT / f"{n}.stl").exists()]
    return ms + [(pv.read(str(f)), color(f.stem[len("dummy-"):])) for f in sorted(OUT.glob("dummy-*.stl"))]


def section(tag):
    fs = sorted(OUT.glob(f"section-{tag}-*.stl"))
    return [(pv.read(str(f)), color(f.stem[len(f"section-{tag}-"):])) for f in fs]


PARTS = {"shell": ["front", "left", "back", "iso-front-left", "iso-back-right", "bottom"],
         "lid": ["iso-back-right", "iso-front-left", "top", "back"],
         "carrier": ["iso-back-right", "iso-front-left", "back", "left"],
         "lightbox": ["iso-front-left", "iso-back-right", "left", "right", "top"],
         "teststrip": ["front", "iso-front-left", "back"],
         "assembly": ["front", "left", "iso-front-left", "iso-under-back"]}
JOBS = {n: (lambda n=n: render(f"{n}-views", assembly() if n == "assembly" else part(n), PARTS[n])) for n in PARTS}
JOBS["section-x"] = lambda: render("section-x-views", section("x"), ["right"], size=700, height=1000)
JOBS["section-y"] = lambda: render("section-y-views", section("y"), ["front"], size=700, height=1000)
# JOBS["detail-lightbox-section"] = lambda: render("detail-lightbox-section", section("y"), ["front"], size=900, height=1000,
#                                                 focus=(-19, 17, 60), half=18)
JOBS["section-z"] = lambda: render("section-z-views", section("z"), ["top", "iso-top-left"], size=800, height=700)
JOBS["section-ins"] = lambda: render("section-ins-views", section("ins"), ["top", "iso-top-left"], size=800, height=700)
JOBS["detail-bevel"] = lambda: render("detail-bevel", part("shell"), ["iso-front-left", "front"], size=700, height=700,
                                      focus=(0, 0, 88), half=16)
JOBS["detail-logo"] = lambda: render("detail-logo", assembly(), ["left", "iso-front-left"], size=700, height=700,
                                     focus=(-25, 17, 60), half=14)
JOBS["detail-logo-section"] = lambda: render("detail-logo-section", section("z"), ["top"], size=1000, height=800,
                                             focus=(-17, 17, 60), half=16)
for name in sys.argv[1:] or [n for n in JOBS if n not in PARTS or (OUT / f"{n}.stl").exists() or n == "assembly"]:
    JOBS[name]()
