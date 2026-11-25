"""Pebble front, slot edge options at true scale: a horizontal section through the front wall and 3D clay close-ups.
  CUR  as printed (WIP): the oval's front, 4.55 on the centre line; 0.6 land, then 45 deg out to the face
  A    wall 3.0 at the slot centres (inner face forward, outer bow kept); 0.6 land, then a round lip of radius = the
       depth left, vertical at the land and tangent to the face
  B    as A, but an elliptical lip: 4.0 wide, the same depth (gentler)
    ~/.venvs/cad/bin/python slot_edges.py [outdir]
"""
import sys, math, pathlib
import numpy as np

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path(__file__).parent / "out-slot-edges")
OUT.mkdir(parents=True, exist_ok=True)
W_, D_, N_ = 56.0, 36.0, 2.8                           # the oval's plan: the front's bow across the width
def f(x): return D_ / 2 * (1 - (1 - np.minimum(np.abs(2 * np.asarray(x) / W_), 0.999) ** N_) ** (1 / N_))
XC, HALF, LAND = 20.46 / 2, 8.1 / 2, 0.6
CROWN = 3.65                                           # rod crown in front of the inner face (tape mid)
S0, S1 = 25.0, 91.85                                   # slot along the face (pebble WIP)
VAR = {"CUR": dict(t_in=4.55, lip="45"),
       "A": dict(t_in=3.0 + float(f(XC)), lip="round"),
       "B": dict(t_in=3.0 + float(f(XC)), lip="ellipse", a=4.0)}
LABEL = {"CUR": "CUR: as printed (front 4.55, 45° bevels)", "A": "A: 3 mm at the slots, round lip",
         "B": "B: 3 mm at the slots, wide elliptical lip"}


def profile(x, v):
    """depth (t, from the outer face's centre line, inwards) of the material surface across the width"""
    V = VAR[v]; L = V["t_in"] - LAND
    x = np.asarray(x, float); out = f(x).copy()
    for xc in (-XC, XC):
        u = np.abs(x - xc)
        p = np.full_like(x, -np.inf)
        p[u < HALF] = V["t_in"]
        for sg in (-1, 1):                              # each side of the slot meets the bowed face at its own depth
            m = (u >= HALF) & (np.sign(x - xc) == sg)
            if V["lip"] == "45":
                p[m] = L - (u[m] - HALF)
                continue
            r = L - float(f(xc + sg * (HALF + 2.0)))
            for _ in range(50):                         # lip depth r: it ends on the face, a (width) = r or fixed
                a = r if V["lip"] == "round" else V["a"]
                r = L - float(f(xc + sg * (HALF + a)))
            a = r if V["lip"] == "round" else V["a"]
            k = m & (u <= HALF + a)
            p[k] = L - r * np.sqrt(np.clip(1 - ((HALF + a - u[k]) / a) ** 2, 0, 1))
        out = np.maximum(out, p)
    return out


def numbers(v):
    V = VAR[v]; xs = np.linspace(-24, 24, 48001); P = profile(xs, v)
    face = np.abs(P - f(xs)) < 1e-3
    # opening edges on the face (where the profile leaves the face) and the bridge's face-flat between the slots
    right = xs[(xs > 0) & ~face]; op = (right.min(), right.max())
    mid = xs[(np.abs(xs) < XC) & face]
    return dict(centre=V["t_in"], slot=V["t_in"] - float(f(XC)), glass=V["t_in"] - float(f(15.6)),
                rod=float(f(XC)) - (V["t_in"] - CROWN), opening=op[1] - op[0], bridge=2 * mid.max() if len(mid) else 0.0)


def section_png():
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle, Wedge
    fig, axs = plt.subplots(len(VAR), 1, figsize=(13, 3.6 * len(VAR)))
    for ax, v in zip(axs, VAR):
        V = VAR[v]; xs = np.linspace(-24, 24, 4801); P = profile(xs, v)
        poly = np.vstack([np.c_[xs, -P], [[24, -V["t_in"]], [-24, -V["t_in"]]]])
        ax.add_patch(Polygon(poly, closed=True, fc="#ece6d8", ec="#555", lw=1.2))
        gy = -V["t_in"] - 0.0
        ax.add_patch(Rectangle((-15.6, gy - 3.9), 31.2, 3.9, fc="#cfe3f3", ec="#89a"))
        for xc in (-XC, XC):
            base = -(V["t_in"] - CROWN) - 4.0
            ax.add_patch(Wedge((xc, base), 4.0, 0, 180, fc="#8fc3e6", ec="#3b7fb0", alpha=0.9))
        ax.plot(xs, -f(xs), color="#c33", lw=0.8, ls="--")
        n = numbers(v)
        ax.set_title(f"{LABEL[v]}   |  wall: centre {n['centre']:.2f}, slot centre {n['slot']:.2f}, at the glass edge (x 15.6) "
                     f"{n['glass']:.2f}  |  rod crown {'proud ' if n['rod'] > 0 else 'under the face '}{abs(n['rod']):.2f}  |  "
                     f"opening {n['opening']:.1f}, bridge flat {n['bridge']:.1f}", fontsize=9)
        ax.set_xlim(-24, 24); ax.set_ylim(-9.5, 1.5); ax.set_aspect("equal"); ax.grid(alpha=0.25)
        ax.set_yticks([]); ax.set_xlabel("x, mm (front view: left to right); outside is up; red dashed: the outer face without slots")
    fig.suptitle("Pebble front: horizontal section through the slots at true scale (glass light blue, rods blue)", fontsize=11)
    fig.tight_layout(); p = OUT / "slot-edges-section.png"; fig.savefig(p, dpi=120); print(p)


def clay_png():
    import pyvista as pv
    c15, s15 = math.cos(math.radians(15)), math.sin(math.radians(15))
    def world(x, t, s): return np.stack([x, t * c15 + s * s15, s * c15 - t * s15], -1)
    xs = np.linspace(-26, 26, 1041); ss = np.linspace(12, 104, 369)
    pl = pv.Plotter(off_screen=True, window_size=(3 * 700, 2 * 760), shape=(2, 3))
    for j, v in enumerate(VAR):
        V = VAR[v]
        P = np.tile(profile(xs, v), (len(ss), 1))
        inslot = (ss[:, None] >= S0) & (ss[:, None] <= S1)
        P = np.where(inslot, P, f(xs)[None, :])
        X, S = np.meshgrid(xs, ss)
        body = pv.StructuredGrid(*np.moveaxis(world(X, P, S), -1, 0))
        rods = []
        for xc in (-XC, XC):
            th = np.linspace(0, math.pi, 49); sr = np.linspace(S0 + 0.1, S1 - 0.1, 2)
            TH, SR = np.meshgrid(th, sr)
            base = V["t_in"] - CROWN + 4.0
            rods.append(pv.StructuredGrid(*np.moveaxis(world(xc + 4.0 * np.cos(TH), base - 4.0 * np.sin(TH), SR), -1, 0)))
        for i, (d, name) in enumerate((((-0.35, -1.0, 0.7), "seated"), ((-0.45, -1.0, 0.25), "close-up, top end"))):
            pl.subplot(i, j); pl.set_background("#d8d5cf", top="#f3f1ed")
            pl.add_mesh(body, color="#ece6d8", smooth_shading=True, specular=0.08, ambient=0.3, diffuse=0.8)
            for r in rods:
                pl.add_mesh(r, color="#9cc9e8", smooth_shading=True, specular=0.5, specular_power=30, ambient=0.3)
            if i == 0:
                foc = world(0.0, 2.0, 58.0); dist = 230
            else:
                foc = world(5.0, 2.0, 90.0); dist = 85
            dd = np.array(d) / np.linalg.norm(d)
            pl.camera_position = [tuple(foc + dd * dist), tuple(foc), (0, 0, 1)]; pl.camera.view_angle = 25
            pl.add_text(f"{LABEL[v]}\n{name}", font_size=10, color="black")
    pl.enable_anti_aliasing("ssaa"); p = OUT / "slot-edges-clay.png"; pl.screenshot(str(p)); pl.close(); print(p)


if __name__ == "__main__":
    for v in VAR:
        print(v, {k: round(x, 2) for k, x in numbers(v).items()})
    section_png(); clay_png()
