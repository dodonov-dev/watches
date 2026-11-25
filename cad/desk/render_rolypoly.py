#!/usr/bin/env python3
"""Views of the roly-poly print set (out-rolypoly/*.stl), coloured like the clay views where it helps comparing.

  tilt-compare.png      true side silhouettes for TILT 6 / 8 / 10 (surface level, out-rolypoly/surface-tilt*.json; each run with
                        ROLY_TILT=<t> rolypoly.py --surface): each alone (face plane and rods marked) and laid over each other
  keel-compare.png      side view of the whole clock, the study's keel and the chosen one at the same scale, and their
                        outlines (section x 0) laid over each other
  clay-ortho.png        body + rocking cup + rods: front, front mid-rock (15 deg), left side (the clay's cameras)
  clay-hero.png         the same in perspective: front-left, mid-rock, back-right
  parts-views.png       body, rocking cup, arc gauge, feature edges drawn
  print-cup.png         rocking cup as printed: standing on its back (build direction up), from the side and from above
  body-views.png        body: front, left, back, bottom (seam, bosses, inner land, slots, cable notch)
  face-views.png        round 8's front: front (raking light from the left), three-quarter left (raking light), the side
                        (raking light from above: the lean, the seam's front)
  lips-views.png        the slots' lips close up: the left slot's top end in raking light, the section across both slots
                        (board frame, the rods standing proud), the section along the centre line at the seam (no shelf)
  section-views.png     cuts: y 3.5 seen from the front (battery, trim spots, cast, segments); x = the face's centre seen from +x
                        (front, board, battery, cast); x = cable close-up seen from -x (USB head, cable hole, seam, cast)
  ballast-views.png     the rocking cup from above with the cast (brown) and the trim layer as planned (left-out segments
                        red), a cut through it
  detail-joint.png      seam faces: body from below, rocking cup from above
  detail-logo.png       the logo's stencil pocket: outside (raking light), inside, inside with the stencil, a section

Run after rolypoly.py: ~/.venvs/cad/bin/python cad/desk/render_rolypoly.py
"""
import json, pathlib
import numpy as np
import pyvista as pv

OUT = pathlib.Path(__file__).parent / "out-rolypoly"
F = json.loads((OUT / "focus.json").read_text())
H = F["H"]
IVORY, DARK, BLUE = (233, 226, 211), (40, 40, 43), (122, 190, 226)
COL = {"body": IVORY, "cup-rock": (224, 214, 196), "cup-flat": (224, 214, 196), "rod-l": BLUE, "rod-r": BLUE, "trim-spots": (95, 98, 105),
       "glass": (60, 70, 90), "pcb": (40, 110, 60), "battery": (170, 170, 175), "usb-head": (30, 30, 32), "usb-cable": (60, 60, 64),
       "segments-rock": (95, 98, 105), "segments-rock-left-out": (200, 50, 50), "segments-flat": (95, 98, 105),
       "segments-steps": (95, 98, 105), "cast": (70, 62, 55), "cup-rock-steps": (224, 214, 196), 
       "led-room": (255, 176, 64), "arc-gauge": (150, 180, 150), "stencil": DARK}


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
ROCK = ["body", "cup-rock", "rod-l", "rod-r"]

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


def tilt_compare():
    """Side silhouettes per tilt (surface level): front / back outline per height, the face plane over the slots, the rods'
    crowns 0.75 in front of it; then all laid over each other."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    runs = sorted((json.loads(p.read_text()) for p in OUT.glob("surface-tilt*.json")), key=lambda d: d["tilt"])
    if not runs:
        return
    cols = {6.0: "tab:green", 8.0: "tab:blue", 10.0: "tab:red"}
    fig, axs = plt.subplots(1, len(runs) + 1, figsize=(4.2 * (len(runs) + 1), 7.2), sharey=True)
    for ax, d in zip(axs, runs):
        s_ = d["sil"]
        z, f, b = np.array(s_["z"]), np.array(s_["front"]), np.array(s_["back"])
        ax.fill_betweenx(z, f, b, color=np.array(IVORY) / 255, ec="0.35", lw=1.0)
        ax.axhline(F["seam"], color="0.55", lw=0.8, ls=":")
        fz, fy = np.array(d["face"]["z"]), np.array(d["face"]["y"])
        ax.plot(fy, fz, color=cols.get(d["tilt"], "k"), lw=3, alpha=0.6)
        t = np.radians(d["tilt"])
        ax.plot(fy - 0.75 * np.cos(t), fz + 0.75 * np.sin(t), color=np.array(BLUE) / 255, lw=2)
        ax.set_title(f"tilt {d['tilt']:g} deg (body lean {d['shear']:g})", fontsize=10)
        ax.set_aspect("equal")
        ax.set_xlim(-30, 36)
        ax.set_xlabel("y (front left, back right), mm")
        ax.grid(alpha=0.25)
    ax = axs[-1]
    for d in runs:
        s_ = d["sil"]
        ax.plot(s_["front"], s_["z"], color=cols.get(d["tilt"], "k"), lw=1.5, label=f"tilt {d['tilt']:g}")
        ax.plot(s_["back"], s_["z"], color=cols.get(d["tilt"], "k"), lw=1.5)
    ax.set_aspect("equal")
    ax.set_xlim(-30, 36)
    ax.legend(fontsize=9)
    ax.set_title("laid over each other", fontsize=10)
    ax.grid(alpha=0.25)
    axs[0].set_ylabel("z above the desk, mm")
    fig.suptitle("side silhouettes, seen from the left (true scale); blue: rod crowns, thick: the face plane over the slots; dotted: "
                 "the seam", fontsize=10)
    fig.tight_layout()
    fig.savefig(str(OUT / "tilt-compare.png"), dpi=110)
    print(OUT / "tilt-compare.png")


tilt_compare()
keel_compare()
shot("clay-ortho.png", [scene(ROCK), scene(ROCK, 15), scene(ROCK)], [FRONT, FRONT, LEFT])
shot("clay-hero.png", [scene(ROCK), scene(ROCK, 15), scene(ROCK)], [HERO, HERO, HERO_BR], size=(820, 1100))


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
multi("parts-views.png", [single("body", ISO), single("cup-rock", (-0.8, -1.0, -0.7)), single("arc-gauge", (-0.8, -1.0, 0.7))],
      size=(480, 600))
cup = rd("cup-rock")
cup_p = cup.copy().rotate_x(-90, point=(0, 0, 0))         # standing on its back: +y down, so -y is the build direction (up)
cup_p.translate((0, 0, -cup_p.bounds[4]), inplace=True)
multi("print-cup.png", [([("cup-rock", cup_p)], ((-1, 0, 0), Z, True, None), None),
                        ([("cup-rock", cup_p)], ((-0.7, -1, 0.6), Z, True, None), None)], size=(700, 600))
multi("body-views.png", [single("body", (0, -1, 0)), single("body", (-1, 0, 0)), single("body", (0, 1, 0)),
                         single("body", (0, 0, -1), up=(0, -1, 0))], size=(520, 760))


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


INSIDE = ["body", "cup-rock", "rod-l", "rod-r", "glass", "pcb", "battery", "usb-head", "usb-cable", "segments-rock",
          "cast", "led-room", "trim-spots"] + [p.stem[len("dummy-"):] for p in OUT.glob("dummy-button-*.stl")] + \
         [p.stem[len("dummy-"):] for p in OUT.glob("dummy-plug-*.stl")]
dc = F["face_c"]
multi("section-views.png", [(clipped(INSIDE, (0, 1, 0), (0, 3.5, 0)), ((0, -1, 0), Z, True, (0, 0, H / 2)), H * 0.55),
                            (clipped(INSIDE, (-1, 0, 0), (dc[0], 0, 0)), ((1, 0, 0), Z, True, (0, 2, H / 2)), H * 0.55),
                            (clipped(INSIDE, (1, 0, 0), (F["usb"][0], 0, 0)), ((-1, 0, 0), Z, True, (0, 2, 30)), 30)],
      size=(650, 900), edges=False)
multi("ballast-views.png", [([(n, rd(n)) for n in ("cup-rock", "cast", "segments-rock", "segments-rock-left-out") if rd(n) is not None],
                             ((0, 0, 1), (0, 1, 0), True, (0, 2, 10)), 34),
                            ([(n, rd(n).clip(normal=(0, 1, 0), origin=(0, 0, 0), invert=False)) for n in ("cup-rock", "cast", "segments-rock")
                              if rd(n) is not None], ((0, -1, 0.0), Z, True, (0, 2, 11)), 24)], size=(620, 560), edges=False)
multi("detail-joint.png", [single("body", (0, 0, -1), up=(0, -1, 0), c=(0, 2, F["seam"]), scale=30),
                           single("cup-rock", (0, 0, 1), up=(0, 1, 0), c=(0, 2, F["seam"]), scale=30)], size=(800, 650))
lg, ln = np.array(F["logo"]), np.array(F["logo_n"])


def detail_logo():
    """The logo's stencil pocket: outside (raking light from the left: the skin should not show the pocket), inside, inside
    with the stencil seated (dark), and the section z = the logo's centre seen from above (body ivory, stencil dark)."""
    body_cut = rd("body").clip_box(bounds=(lg[0] - 14, lg[0] + 14, lg[1] - 14, lg[1] + 14, lg[2] - 9, lg[2] + 9), invert=False)
    st = rd("stencil")
    pl = pv.Plotter(off_screen=True, window_size=(620 * 4, 560), shape=(1, 4))
    views = [("outside, light from the left", [("body", body_cut)], tuple(ln), False),
             ("inside", [("body", body_cut)], tuple(-ln), True),
             ("inside, stencil seated", [("body", body_cut), ("stencil", st)], tuple(-ln), True)]
    for i, (label, ms, d, edges) in enumerate(views):
        pl.subplot(0, i)
        pl.set_background("white")
        if i == 0:
            pl.add_light(pv.Light(position=tuple(lg + np.array([-300, -80, 40])), focal_point=tuple(lg), intensity=0.9))
        for n, m in ms:
            if m is None:
                continue
            pl.add_mesh(m, color=DARK if n == "stencil" else color(n), smooth_shading=True, split_sharp_edges=True, specular=0.2)
            if edges and n == "body":
                pl.add_mesh(m.extract_feature_edges(35, boundary_edges=False, manifold_edges=False), color="black", line_width=1)
        pl.add_text(label, font_size=11)
        pl.camera_position = [tuple(lg + np.array(d) * 600), tuple(lg), Z]
        pl.camera.parallel_projection = True
        pl.camera.parallel_scale = 11
        pl.reset_camera_clipping_range()
    pl.subplot(0, 3)
    pl.set_background("white")
    for n, m, c in (("body", rd("body"), (120, 110, 95)), ("stencil", st, DARK)):
        if m is None:
            continue
        sl = m.slice(normal=(0, 0, 1), origin=tuple(lg))
        if sl.n_points:
            pl.add_mesh(sl, color=c, line_width=3)
    pl.add_text(f"section z {lg[2]:.0f}, from above (front down)", font_size=11)
    pl.camera_position = [tuple(lg + np.array([0, 0, 600])), tuple(lg), (0, 1, 0)]
    pl.camera.parallel_projection = True
    pl.camera.parallel_scale = 11
    pl.reset_camera_clipping_range()
    pl.screenshot(str(OUT / "detail-logo.png"))
    pl.close()
    print(OUT / "detail-logo.png")


detail_logo()


def face_views():
    """Round 8's front for judging the face: raking light from the left (front, three-quarter), the side with light from
    above-front (the lean, the head, the seam's front), the seam close up from the front-left below."""
    ms = scene(ROCK)
    pl = pv.Plotter(off_screen=True, window_size=(640 * 4, 900), shape=(1, 4))
    zc = F["face_c"][2]
    sz = F["seam"]
    cams = [((0, -1, 0), (0, 0, zc), 72, "front", (-400, -120, zc + 60)),
            ((-0.6, -1.0, 0.25), (0, 0, zc), 72, "three-quarter left", (-400, -120, zc + 60)),
            ((-1, 0, 0), (0, 4, zc), 72, f"left side: the face leans {F['tilt']:g} deg", (-150, -400, 300)),
            ((-1.0, -0.35, 0.1), (-5, F["seam_front_y"], sz + 6), 24, "the seam's front from the left: no shelf", (-300, -300, 200))]
    for i, (d, c, sc, label, lp) in enumerate(cams):
        pl.subplot(0, i)
        pl.set_background("#d8d5cf", top="#f3f1ed")
        for n, m in ms:
            pl.add_mesh(m, color=color(n), smooth_shading=True, split_sharp_edges=True, specular=0.1, ambient=0.3, diffuse=0.8)
        pl.add_text(label, font_size=11)
        n_ = np.linalg.norm(d)
        pl.camera_position = [tuple(np.array(c) + np.array(d) / n_ * 500), c, (0, 0, 1)]
        pl.camera.parallel_projection = True
        pl.camera.parallel_scale = sc
        pl.reset_camera_clipping_range()
    pl.enable_anti_aliasing("ssaa")
    pl.screenshot(str(OUT / "face-views.png"))
    pl.close()
    print(OUT / "face-views.png")


face_views()


def lips_views():
    """The slots' lips: the left slot's top end close up (raking light), the section across both slots at the face's centre
    (in the board frame: the rods standing proud), the centre line's section through the seam (body and cup: no shelf)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    st = np.array(F["slot_top"])
    fn = np.array(F["face_n"])
    t = np.radians(F["tilt"])
    lean = np.array([0.0, np.sin(t), np.cos(t)])
    ms = scene(ROCK)
    pl = pv.Plotter(off_screen=True, window_size=(900, 900))
    pl.set_background("#d8d5cf", top="#f3f1ed")
    c = st - 6 * lean + np.array([5.0, 0, 0])
    for n, m in ms:
        pl.add_mesh(m, color=color(n), smooth_shading=True, split_sharp_edges=True, specular=0.1, ambient=0.3, diffuse=0.8)
    d = -fn * 1.0 + np.array([-0.45, 0, 0]) + lean * 0.35
    pl.camera_position = [tuple(c - d / np.linalg.norm(d) * 160), tuple(c), tuple(lean)]
    pl.camera.view_angle = 14
    pl.reset_camera_clipping_range()
    pl.enable_anti_aliasing("ssaa")
    img = pl.screenshot(None, return_img=True)
    pl.close()
    fig, axs = plt.subplots(1, 3, figsize=(19, 6.6), gridspec_kw=dict(width_ratios=[1, 1.5, 0.9]))
    axs[0].imshow(img)
    axs[0].set_axis_off()
    axs[0].set_title("the left slot's top end")
    # across the slots: plane through the face's centre, normal = the lean
    fc = np.array(F["face_c"])
    ax = axs[1]
    for n, col in (("body", "0.35"), ("rod-l", "tab:blue"), ("rod-r", "tab:blue"), ("glass", "0.2")):
        m = rd(n)
        if m is None:
            continue
        sl = m.slice(normal=tuple(lean), origin=tuple(fc))
        P = sl.points
        u = P[:, 0]
        v = -(P - fc) @ fn                                 # depth behind the face plane
        for i in range(sl.n_cells):
            ids = sl.get_cell(i).point_ids
            ax.plot(u[ids], v[ids], color=col, lw=1.2)
    ax.axhline(0, color="tab:orange", lw=0.6, ls="--")
    ax.set_xlim(F["zone_x"][0] - 4, F["zone_x"][1] + 4)
    ax.set_ylim(6, -2)
    ax.set_aspect("equal")
    ax.set_xlabel("x, mm")
    ax.set_ylabel("behind the face plane, mm")
    ax.set_title("across the slots at mid-height (board frame): 0.6 land, round lips, 7 mm flat strip, rods proud")
    ax.grid(alpha=0.25)
    # the centre line through the seam
    ax = axs[2]
    for n, col in (("body", "0.25"), ("cup-rock", "tab:brown")):
        m = rd(n)
        sl = m.slice(normal="x", origin=(-5.0, 0, 0))
        P = sl.points
        for i in range(sl.n_cells):
            ids = sl.get_cell(i).point_ids
            ax.plot(P[ids, 1], P[ids, 2], color=col, lw=1.2)
    ax.axhline(F["seam"], color="0.6", lw=0.6, ls=":")
    ax.set_xlim(-26, -4)
    ax.set_ylim(0, 60)
    ax.set_aspect("equal")
    ax.set_xlabel("y, mm (front left)")
    ax.set_ylabel("z, mm")
    ax.set_title("section x -5 (between the slots): body / cup")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(str(OUT / "lips-views.png"), dpi=100)
    print(OUT / "lips-views.png")


lips_views()
