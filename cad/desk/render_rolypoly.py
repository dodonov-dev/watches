#!/usr/bin/env python3
"""Views of the roly-poly print set (out-rolypoly/*.stl), coloured like the clay views where it helps comparing.

  logo-compare.png      body from the front and three-quarter right, the logo's footprint painted on: old and new position
  keel-compare.png      side view of the whole clock, the study's keel and the chosen one at the same scale, and their
                        outlines (section x 0) laid over each other
  clay-ortho.png        body + rocking cup + door + rods: front, front mid-rock (15 deg), left side (the clay's cameras)
  clay-hero.png         the same in perspective: front-left, mid-rock, back-right
  stable-ortho.png      with the flat cup: front, tilted 15 deg on its foot edge, left side
  parts-views.png       body, rocking cup, flat cup, door, arc gauge, feature edges drawn
  print-cup.png         rocking cup as printed: standing on its back (build direction up), from the side and from above
  body-views.png        body: front, left, back, bottom (seam, bosses, bulkhead with the USB head's notch, cable notch, tabs)
  section-views.png     cuts: y 3.5 seen from the front (battery, bulkhead, cast, segments); x = door centre seen from +x
                        (door, board, battery, bulkhead, cast); x = cable close-up seen from -x (USB head, cable hole, seam, cast)
  ballast-views.png     cups from above: rocking cup with the cast (brown) and the trim layer as planned (left-out
                        segments red), the flat cup with its segments, a cut through the rocking cup
  door-views.png        door front and back
  detail-joint.png      seam faces: body from below, rocking cup from above
  detail-logo.png       the thinned logo wall from outside and inside

Run after rolypoly.py: ~/.venvs/cad/bin/python cad/desk/render_rolypoly.py
"""
import json, pathlib
import numpy as np
import pyvista as pv

OUT = pathlib.Path(__file__).parent / "out-rolypoly"
F = json.loads((OUT / "focus.json").read_text())
H = F["H"]
IVORY, DARK, BLUE = (233, 226, 211), (40, 40, 43), (122, 190, 226)
COL = {"body": IVORY, "cup-rock": (224, 214, 196), "cup-flat": (224, 214, 196), "door": DARK, "rod-l": BLUE, "rod-r": BLUE,
       "glass": (60, 70, 90), "pcb": (40, 110, 60), "battery": (170, 170, 175), "usb-head": (30, 30, 32), "usb-cable": (60, 60, 64),
       "segments-rock": (95, 98, 105), "segments-rock-left-out": (200, 50, 50), "segments-flat": (95, 98, 105),
       "segments-steps": (95, 98, 105), "cast": (70, 62, 55), "cup-rock-steps": (224, 214, 196), 
       "led-room": (255, 176, 64), "arc-gauge": (150, 180, 150)}


def rd(n):
    p = OUT / (f"{n}.stl" if (OUT / f"{n}.stl").exists() else f"dummy-{n}.stl")
    if not p.exists():
        return None
    m = pv.read(str(p))
    if n == "cast":                                    # it fills the cup's cavity exactly: pull it in 0.05 so it does not z-fight
        m = m.clean().compute_normals(point_normals=True, cell_normals=False, auto_orient_normals=True)
        m.points = m.points - 0.05 * m.point_data["Normals"]
    return m


def color(n):
    if n.startswith("button"):
        return (200, 40, 40)
    if n.startswith("plug"):
        return (220, 180, 40)
    return COL.get(n, (150, 150, 150))


def posed(m, tilt):
    m = m.copy()
    m.rotate_y(tilt, point=(0, 0, 0), inplace=True)
    return m


def scene(names, tilt=0.0):
    ms = [(n, rd(n)) for n in names]
    ms = [(n, posed(m, tilt)) for n, m in ms if m is not None]
    zmin = min(m.bounds[4] for n, m in ms if n in ("body", "cup-rock", "cup-flat"))
    for _, m in ms:
        m.translate((0, 0, -zmin), inplace=True)
    return ms


def shot(fname, scenes, views, size=(700, 1000), edges=False, floor=True, par_scale=None):
    pl = pv.Plotter(off_screen=True, window_size=(size[0] * len(views), size[1]), shape=(1, len(views)))
    for i, (ms, (d, up, par, c)) in enumerate(zip(scenes, views)):
        pl.subplot(0, i)
        pl.set_background("#d8d5cf", top="#f3f1ed")
        for n, m in ms:
            pl.add_mesh(m, color=color(n), smooth_shading=True, split_sharp_edges=True, specular=0.1, ambient=0.3, diffuse=0.8)
            if edges:
                pl.add_mesh(m.extract_feature_edges(35, boundary_edges=False, manifold_edges=False), color="black", line_width=1)
        if floor:
            pl.add_mesh(pv.Plane(center=(0, 0, -0.02), direction=(0, 0, 1), i_size=700, j_size=700), color="#cfcac2", ambient=0.5, diffuse=0.6)
        c = c or (0, 2, H / 2)
        n_ = np.linalg.norm(d)
        pl.camera_position = [tuple(c[j] + d[j] / n_ * (700 if not par else 500) for j in range(3)), c, up]
        if par:
            pl.camera.parallel_projection = True
            pl.camera.parallel_scale = par_scale or H * 0.62
        else:
            pl.camera.view_angle = 14
        pl.reset_camera_clipping_range()
    pl.enable_anti_aliasing("ssaa")
    pl.screenshot(str(OUT / fname))
    pl.close()
    print(OUT / fname)


Z = (0, 0, 1)
FRONT, LEFT, BACK = ((0, -1, 0), Z, True, None), ((-1, 0, 0), Z, True, None), ((0, 1, 0), Z, True, None)
HERO, HERO_BR = ((-0.55, -1.0, 0.34), Z, False, None), ((0.9, 1.0, 0.34), Z, False, None)
ROCK = ["body", "cup-rock", "door", "rod-l", "rod-r"]
FLAT = ["body", "cup-flat", "door", "rod-l", "rod-r"]

def logo_compare():
    """Body from the front and three-quarter right, the letters' footprint painted on: the old position and the new one."""
    body = pv.read(str(OUT / "body.stl"))
    views = [((0, -1, 0), "front"), ((0.75, -1.0, 0.15), "3/4 right")]
    pl = pv.Plotter(off_screen=True, window_size=(560 * 4, 860), shape=(1, 4))
    i = 0
    for tag, label in (("old", f"old: x {F['logo_x_old']:g}"), ("new", f"new: x {F['logo_x']:g}")):
        decal = pv.read(str(OUT / f"dummy-logo-{tag}.stl")).clean().compute_normals(point_normals=True, cell_normals=False,
                                                                                  auto_orient_normals=True)
        decal.points = decal.points + 0.12 * decal.point_data["Normals"]       # just off the surface: no z-fighting
        for d, vn in views:
            pl.subplot(0, i)
            pl.set_background("#d8d5cf", top="#f3f1ed")
            pl.add_mesh(body, color=IVORY, smooth_shading=True, specular=0.05, ambient=0.3, diffuse=0.8)
            pl.add_mesh(decal, color=(230, 90, 20), ambient=0.5)
            pl.add_text(f"{label}, {vn}", font_size=11)
            c = np.array((0.0, 0.0, H / 2 + 6))
            n_ = np.linalg.norm(d)
            pl.camera_position = [tuple(c + np.array(d) / n_ * 500), tuple(c), (0, 0, 1)]
            pl.camera.parallel_projection = True
            pl.camera.parallel_scale = H * 0.5
            pl.reset_camera_clipping_range()
            i += 1
    pl.enable_anti_aliasing("ssaa")
    pl.screenshot(str(OUT / "logo-compare.png"))
    pl.close()
    print(OUT / "logo-compare.png")


def keel_compare():
    names = list(F["keels"])
    pl = pv.Plotter(off_screen=True, window_size=(700 * 3, 1000), shape=(1, 3))
    outl = {}
    for i, n in enumerate(names):
        m = pv.read(str(OUT / f"keel-{n}.stl"))
        pl.subplot(0, i)
        pl.set_background("#d8d5cf", top="#f3f1ed")
        pl.add_mesh(m, color=IVORY, smooth_shading=True, specular=0.05, ambient=0.3, diffuse=0.8)
        pl.add_mesh(pv.Plane(center=(0, 0, -0.02), direction=(0, 0, 1), i_size=700, j_size=700), color="#cfcac2", ambient=0.5, diffuse=0.6)
        pl.add_text(f"{n} keel (NC {F['keels'][n]})", font_size=12)
        pl.camera_position = [(-500, 2, H / 2), (0, 2, H / 2), (0, 0, 1)]
        pl.camera.parallel_projection = True
        pl.camera.parallel_scale = H * 0.62
        outl[n] = m.slice(normal="x", origin=(0, 0, 0))
    pl.subplot(0, 2)
    pl.set_background("white")
    for n, col in zip(names, ("gray", "black")):
        pl.add_mesh(outl[n], color=col, line_width=3)
    pl.add_text("x 0 section: " + names[0] + " gray, " + names[1] + " black", font_size=12)
    pl.camera_position = [(-500, 2, 24), (0, 2, 24), (0, 0, 1)]
    pl.camera.parallel_projection = True
    pl.camera.parallel_scale = 30
    pl.screenshot(str(OUT / "keel-compare.png"))
    pl.close()
    print(OUT / "keel-compare.png")


keel_compare()
if (OUT / "dummy-logo-new.stl").exists():
    logo_compare()
shot("clay-ortho.png", [scene(ROCK), scene(ROCK, 15), scene(ROCK)], [FRONT, FRONT, LEFT])
shot("clay-hero.png", [scene(ROCK), scene(ROCK, 15), scene(ROCK)], [HERO, HERO, HERO_BR], size=(820, 1100))
shot("stable-ortho.png", [scene(FLAT), scene(FLAT, 15), scene(FLAT)], [FRONT, FRONT, LEFT])


def single(n, d, up=Z, c=None, scale=None):
    m = rd(n)
    return [(n, m)], (d, up, True, c or tuple(np.array(m.center))), scale


def multi(fname, items, size=(600, 700), edges=True):
    pl = pv.Plotter(off_screen=True, window_size=(size[0] * len(items), size[1]), shape=(1, len(items)))
    for i, (ms, (d, up, par, c), scale) in enumerate(items):
        pl.subplot(0, i)
        pl.set_background("white")
        for n, m in ms:
            pl.add_mesh(m, color=color(n), smooth_shading=True, split_sharp_edges=True, specular=0.2)
            if edges:
                pl.add_mesh(m.extract_feature_edges(35, boundary_edges=False, manifold_edges=False), color="black", line_width=1)
        n_ = np.linalg.norm(d)
        allm = pv.merge([m for _, m in ms])
        c = c or tuple(allm.center)
        pl.camera_position = [tuple(c[j] + d[j] / n_ * 600 for j in range(3)), c, up]
        pl.camera.parallel_projection = True
        if scale:
            pl.camera.parallel_scale = scale
        else:
            pl.reset_camera()
        pl.reset_camera_clipping_range()
    pl.screenshot(str(OUT / fname))
    pl.close()
    print(OUT / fname)


ISO = (-0.8, -1.0, 0.7)
multi("parts-views.png", [single("body", ISO), single("cup-rock", (-0.8, -1.0, -0.7)), single("cup-flat", (-0.8, -1.0, 0.7)),
                          single("door", (0.6, 1.0, 0.4)), single("arc-gauge", (-0.8, -1.0, 0.7))], size=(480, 600))
cup = rd("cup-rock")
cup_p = cup.copy().rotate_x(-90, point=(0, 0, 0))         # standing on its back: +y down, so -y is the build direction (up)
cup_p.translate((0, 0, -cup_p.bounds[4]), inplace=True)
multi("print-cup.png", [([("cup-rock", cup_p)], ((-1, 0, 0), Z, True, None), None),
                        ([("cup-rock", cup_p)], ((-0.7, -1, 0.6), Z, True, None), None)], size=(700, 600))
multi("body-views.png", [single("body", (0, -1, 0)), single("body", (-1, 0, 0)), single("body", (0, 1, 0)),
                         single("body", (0, 0, -1), up=(0, -1, 0))], size=(520, 760))
multi("door-views.png", [single("door", (0, -1, 0)), single("door", (0, 1, 0))], size=(500, 800))


def clipped(names, normal, origin):
    out = []
    for n in names:
        m = rd(n)
        if m is None:
            continue
        c = m.clip(normal=normal, origin=origin, invert=False)
        if c.n_points:
            out.append((n, c))
    return out


INSIDE = ["body", "cup-rock", "door", "rod-l", "rod-r", "glass", "pcb", "battery", "usb-head", "usb-cable", "segments-rock",
          "cast", "led-room"] + [p.stem[len("dummy-"):] for p in OUT.glob("dummy-button-*.stl")] + \
         [p.stem[len("dummy-"):] for p in OUT.glob("dummy-plug-*.stl")]
dc = F["door_c"]
multi("section-views.png", [(clipped(INSIDE, (0, 1, 0), (0, 3.5, 0)), ((0, -1, 0), Z, True, (0, 0, H / 2)), H * 0.55),
                            (clipped(INSIDE, (-1, 0, 0), (dc[0], 0, 0)), ((1, 0, 0), Z, True, (0, 2, H / 2)), H * 0.55),
                            (clipped(INSIDE, (1, 0, 0), (F["usb"][0], 0, 0)), ((-1, 0, 0), Z, True, (0, 2, 30)), 30)],
      size=(650, 900), edges=False)
multi("ballast-views.png", [([(n, rd(n)) for n in ("cup-rock", "cast", "segments-rock", "segments-rock-left-out") if rd(n) is not None],
                             ((0, 0, 1), (0, 1, 0), True, (0, 2, 10)), 34),
                            ([(n, rd(n)) for n in ("cup-flat", "segments-flat") if rd(n) is not None],
                             ((0, 0, 1), (0, 1, 0), True, (0, 2, 17)), 34),
                            ([(n, rd(n).clip(normal=(0, 1, 0), origin=(0, 0, 0), invert=False)) for n in ("cup-rock", "cast", "segments-rock")
                              if rd(n) is not None], ((0, -1, 0.0), Z, True, (0, 2, 11)), 24)], size=(620, 560), edges=False)
multi("detail-joint.png", [single("body", (0, 0, -1), up=(0, -1, 0), c=(0, 2, F["seam"]), scale=30),
                           single("cup-rock", (0, 0, 1), up=(0, 1, 0), c=(0, 2, F["seam"]), scale=30)], size=(800, 650))
lg, ln = np.array(F["logo"]), np.array(F["logo_n"])
body_cut = rd("body").clip_box(bounds=(lg[0] - 14, lg[0] + 14, lg[1] - 14, lg[1] + 14, lg[2] - 9, lg[2] + 9), invert=False)
multi("detail-logo.png", [([("body", body_cut)], (tuple(ln), Z, True, tuple(lg)), 10),
                          ([("body", body_cut)], (tuple(-ln), Z, True, tuple(lg)), 10)], size=(700, 520))
