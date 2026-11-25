"""Clay views of a concept from concepts.py at true geometry (Fable's section loft), with the slots / rods / logo as
coloured decals on the bowed face. Massing only: no wall, no cavity.
    ~/.venvs/cad/bin/python clay_pebble.py [concept=pebble] [outdir] [P=2.5 N=2.5]   (pebble's egg / plan exponents)
"""
import sys, pathlib, math
import numpy as np
import pyvista as pv
import concepts
from concepts import CONCEPTS
from geo import W, LID

for a in [a for a in sys.argv[1:] if "=" in a]:
    k, v = a.split("="); setattr(concepts, "PEB_" + k, float(v)); sys.argv.remove(a)

key = sys.argv[1] if len(sys.argv) > 1 else "pebble"
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else pathlib.Path(__file__).parent / f"out-clay-{key}")
OUT.mkdir(parents=True, exist_ok=True)
bodies, yt, _ = CONCEPTS[key]()
b = bodies[0]

# ---- body: stack of sections (each 4k points, same order) -> structured surface, capped
zs = np.r_[np.linspace(b.z0, b.z1 - 8, 160), np.linspace(b.z1 - 8, b.z1 - 0.02, 60)[1:]]
rings = []
for z in zs:
    P = b.section(z)
    if P is not None:
        rings.append(np.c_[P, np.full(len(P), z)])
R = np.array(rings); nz, nk, _ = R.shape
pts = R.reshape(-1, 3)
faces = []
for i in range(nz - 1):
    for j in range(nk):
        a, c = i * nk + j, i * nk + (j + 1) % nk
        faces += [4, a, c, c + nk, a + nk]
bot = len(pts); top = bot + 1
pts = np.vstack([pts, R[0].mean(0), R[-1].mean(0)])
for j in range(nk):
    faces += [3, bot, (j + 1) % nk, j, 3, top, (nz - 1) * nk + j, (nz - 1) * nk + (j + 1) % nk]
body = pv.PolyData(pts, np.array(faces)).triangulate().clean()
body.save(OUT / "body.stl")

# ---- decals on the face: front-most y of the section at (x, z)
def face_y(x, z):
    P = b.section(z)
    fr = P[P[:, 1] < (P[:, 1].min() + P[:, 1].max()) / 2]
    fr = fr[np.argsort(fr[:, 0])]
    return float(np.interp(x, fr[:, 0], fr[:, 1]))

def decal(x0, x1, s0, s1, off, n=24):
    xs, ss = np.linspace(x0, x1, 8), np.linspace(s0, s1, n)
    P = []
    for s in ss:
        _, z = W(yt, s, 0.0)
        for x in xs:
            P.append((x, face_y(x, z) - off, z))
    g = pv.StructuredGrid(*np.array(P).reshape(n, 8, 3).transpose(2, 1, 0))
    return g.extract_surface().triangulate()

S_SLOT = (24.6, 91.45)  # along the face from the rim (tilt15 / oval: PCB bottom s 16.7)
parts = {"body": body}
for side, xc in (("l", -10.23), ("r", 10.23)):
    parts[f"bevel-{side}"] = decal(xc - 7.15, xc + 7.15, *S_SLOT, 0.15)
    parts[f"rod-{side}"] = decal(xc - 4.0, xc + 4.0, S_SLOT[0], S_SLOT[1], 0.3)
# liquid levels (hours ~7.5/12, minutes ~27/60) as a darker blue lower part
for side, xc, f in (("l", -10.23, 0.62), ("r", 10.23, 0.46)):
    parts[f"liq-{side}"] = decal(xc - 4.0, xc + 4.0, S_SLOT[0], S_SLOT[0] + f * (S_SLOT[1] - S_SLOT[0]), 0.4)
parts["logo"] = decal(-6.0, 6.0, 9.0, 16.5, 0.2)
COL = {"body": "#ece6d8", "logo": "#ffb347"}
for k in parts:
    if k.startswith("bevel"): COL[k] = "#9c958a"
    if k.startswith("rod"): COL[k] = "#f1ead2"
    if k.startswith("liq"): COL[k] = "#5aa6d6"

allm = pv.merge(list(parts.values())); c = list(allm.center)
VIEWS = {"seated": ((-0.45, -1.0, 0.75), False), "hero": ((-0.62, -1.0, 0.36), False), "left": ((-1.0, -0.38, 0.30), False),
         "rear": ((0.8, 1.0, 0.38), False), "front": ((0, -1, 0), True), "side": ((-1, 0, 0), True), "top": ((0, 0, 1), True)}

def shot(names, fname, size=(800, 1000)):
    pl = pv.Plotter(off_screen=True, window_size=(size[0] * len(names), size[1]), shape=(1, len(names)))
    for i, n in enumerate(names):
        d, par = VIEWS[n]; pl.subplot(0, i)
        pl.set_background("#d8d5cf", top="#f3f1ed")
        for k, m in parts.items():
            pl.add_mesh(m.compute_normals(feature_angle=60), color=COL[k], smooth_shading=True,
                        specular=0.08, specular_power=8, ambient=0.28, diffuse=0.8)
        pl.add_mesh(pv.Plane(center=(c[0], c[1], -0.02), direction=(0, 0, 1), i_size=600, j_size=600), color="#cfcac2", ambient=0.5, diffuse=0.6)
        nrm = sum(x * x for x in d) ** 0.5; dist = allm.length * (4.0 if not par else 2.5)
        up = (0, 1, 0) if n == "top" else (0, 0, 1)
        pl.camera_position = [tuple(c[j] + d[j] / nrm * dist for j in range(3)), tuple(c), up]
        if par:
            pl.camera.parallel_projection = True; pl.camera.parallel_scale = allm.length * 0.56
        else:
            pl.camera.view_angle = 17
        pl.add_text(n, font_size=12, color="black")
        pl.reset_camera_clipping_range()
    pl.enable_anti_aliasing("ssaa"); pl.screenshot(str(OUT / fname)); pl.close(); print(OUT / fname)

shot(["seated", "hero", "left", "rear"], "clay-hero.png")
shot(["front", "side", "top"], "clay-ortho.png", size=(700, 900))
