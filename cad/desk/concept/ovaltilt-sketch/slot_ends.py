"""Pebble front after the A print: slot ends and the bridge ("nose") between the slots, at true scale.
  A    as printed: round lips (vertical at the 0.6 land, tangent to the face), ends perpendicular to the face (printed
       standing with the front leaning back 15 deg the top end is a 75 deg ceiling; the lips end in a crescent step:
       the "horns")
  A'   A, the ends sloped: from the inner face (no land at the ends) a quarter-sine out to the face, steepest at the
       inner face where it is 44.5 deg from vertical printed standing; the lips wrap round the corners (the opening on
       the face a rounded rectangle). The bottom end mirrors the top.
  N1   A' + one round crown between the slots: the inner lips grow until they meet on the centre line (exponent 1.4:
       a tighter crown than a circle, no flat, no ridge)
  N2   N1 + small lips on the outer sides (1.0 wide)
  N1-18, N1-16.5   N1 with the rods at c-c 18 / 16.5 instead of 20.46 (the display's columns move: one firmware parameter)
The face is the oval's bow f(x), straight along s (as over the slots; the sketch ignores the fade above / below).
    ~/.venvs/cad/bin/python slot_ends.py [outdir]
"""
import sys, math, pathlib
import numpy as np
from slot_edges import f, HALF, LAND, CROWN, S0, S1

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path(__file__).parents[4] / "images/desk-housing-v3")
T_IN = 3.0 + float(f(20.46 / 2))                       # A: wall 3.0 at the slot centres (3.39 on the centre line)
L = T_IN - LAND
M0 = 1.70                                              # steepest end slope (depth per s): 44.5 deg from vertical printed
C15, S15 = math.cos(math.radians(15)), math.sin(math.radians(15))
VAR = {"A": dict(xc=10.23, ends="flat", lip_in=("round",), lip_out=("round",)),
       "A'": dict(xc=10.23, ends="slope", lip_in=("round",), lip_out=("round",)),
       "N1": dict(xc=10.23, ends="slope", lip_in=("crown", 1.4), lip_out=("round",)),
       "N2": dict(xc=10.23, ends="slope", lip_in=("crown", 1.4), lip_out=("ell", 1.0)),
       "N1-18": dict(xc=9.0, ends="slope", lip_in=("crown", 1.4), lip_out=("round",)),
       "N1-16.5": dict(xc=8.25, ends="slope", lip_in=("crown", 1.4), lip_out=("round",))}
LABEL = {"A": "A: as printed (ends square to the face)", "A'": "A': sloped ends, lips round the corners",
         "N1": "N1: A' + round crown between the slots", "N2": "N2: N1 + small outer lips",
         "N1-18": "N1 at c-c 18 (firmware column shift)", "N1-16.5": "N1 at c-c 16.5 (firmware column shift)"}


def lip(xc, sg, spec):
    """(width a, exponent m) of the lip on side sg of the slot at xc"""
    xin = abs(xc) - HALF                                # land edge to the centre line
    inner = (sg * np.sign(xc)) < 0
    if spec[0] == "crown":
        return xin, spec[1]
    if spec[0] == "ell":
        return spec[1], 2.0
    a = 2.0                                             # round: width = the depth left at its end on the face
    for _ in range(60):
        a = L - float(f(xc + sg * (HALF + a)))
    return a, 2.0


def end_len(V):
    xs = np.linspace(V["xc"] - HALF - 7, V["xc"] + HALF + 7, 2001)
    return math.pi / 2 * (T_IN - float(f(xs).min())) / M0


def surface(x, s, v):
    """material surface t (depth from the face's centre line, inwards) over (x, s); through the slot: T_IN"""
    V = VAR[v]; x, s = np.broadcast_arrays(np.asarray(x, float), np.asarray(s, float))
    fx = f(x); out = fx.copy(); ae = end_len(V)
    for xc in (-V["xc"], V["xc"]):
        u = x - xc; dx = np.abs(u) - HALF
        inner = np.sign(u) != np.sign(xc)
        a_in, m_in = lip(xc, -np.sign(xc), V["lip_in"]); a_out, m_out = lip(xc, np.sign(xc), V["lip_out"])
        a = np.where(inner, a_in, a_out); m = np.where(inner, m_in, m_out)
        ds = np.where(s > S1, s - S1, np.where(s < S0, S0 - s, 0.0))
        qx = np.clip(dx, 0, None) / a
        if V["ends"] == "flat":
            qs = np.where(ds > 0, np.inf, 0.0)
        else:
            qs = ds / ae
        q = np.hypot(qx, qs)
        w = qx ** 2 / (qx ** 2 + qs ** 2 + 1e-12)
        with np.errstate(invalid="ignore"):
            ps = fx + (L - fx) * (1 - np.sqrt(np.clip(1 - (1 - np.clip(q, 0, 1)) ** m, 0, 1)))
            pe = fx + (T_IN - fx) * (1 - np.sin(np.pi / 2 * np.clip(q, 0, 1)))
        p = np.where(q < 1, w * ps + (1 - w) * pe, -np.inf)
        p = np.where((dx < 0) & (ds == 0), T_IN, p)
        out = np.maximum(out, p)
    return out


def numbers(v):
    V = VAR[v]; xc = V["xc"]; sm = (S0 + S1) / 2
    xs = np.linspace(-24, 24, 48001); P = surface(xs, sm, v); d = P - f(xs)
    cut = d > 1e-3
    r = xs[(xs > 0) & cut]; opening = r.max() - r.min()
    gap = 2 * r.min()
    bright = xs[(np.abs(xs) < xc) & (d < 0.3)]; vis = 2 * np.abs(bright).max() if len(bright) else 0.0
    mat1 = T_IN - float(surface(xc - HALF - 1.0, sm, v))                  # material 1 mm from the land, inner side
    rod = float(f(xc)) - (T_IN - CROWN)
    # top end, printed standing: overhang of the material surface facing the cut
    xx = np.arange(xc - HALF - 8, xc + HALF + 8, 0.01); ss = np.arange(S1 - 1.5, S1 + 5, 0.01)
    X, S = np.meshgrid(xx, ss); T = surface(X, S, v)
    dTs, dTx = np.gradient(T, 0.01, 0.01)
    nz = dTs * C15 + S15; nn = np.sqrt(dTx ** 2 + 1 + dTs ** 2)
    act = (T > f(X) + 1e-3) & (T < T_IN - 1e-6) & np.isfinite(dTs) & (S > S1 - 1.0)
    if V["ends"] == "flat":
        oh = 75.0
    else:
        oh = float(np.degrees(np.arcsin(np.clip(-(nz / nn)[act], -1, 1))).max())
    ext = 0.0 if V["ends"] == "flat" else end_len(V)
    return dict(opening=opening, gap=gap, vis=vis, rod=rod, mat1=mat1, overhang=oh, ext=ext,
                bridge_in=2 * (xc - HALF), rod_edge=xc + 4.0)


def world(x, t, s): return np.stack([x, t * C15 + s * S15, s * C15 - t * S15], -1)


def section_png():
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle, Wedge
    fig = plt.figure(figsize=(14, 3.0 * len(VAR) + 4.2))
    gs = fig.add_gridspec(len(VAR) + 1, 2, height_ratios=[1] * len(VAR) + [1.5])
    for i, v in enumerate(VAR):
        ax = fig.add_subplot(gs[i, :]); V = VAR[v]
        xs = np.linspace(-24, 24, 4801); P = surface(xs, (S0 + S1) / 2, v)
        P = np.where(P >= T_IN - 1e-9, np.nan, P)
        # material: between the outer surface and the inner face, except the through-slots
        for seg in np.split(np.arange(len(xs)), np.where(np.diff(np.isnan(P)))[0] + 1):
            if np.isnan(P[seg[0]]): continue
            xx, pp = xs[seg], P[seg]
            ax.add_patch(Polygon(np.vstack([np.c_[xx, -pp], [[xx[-1], -T_IN], [xx[0], -T_IN]]]), closed=True,
                                 fc="#ece6d8", ec="#555", lw=1.1))
        ax.add_patch(Rectangle((-15.6, -T_IN - 3.9), 31.2, 3.9, fc="#cfe3f3", ec="#89a"))
        for xc in (-V["xc"], V["xc"]):
            ax.add_patch(Wedge((xc, -(T_IN - CROWN) - 4.0), 4.0, 0, 180, fc="#8fc3e6", ec="#3b7fb0", alpha=0.9))
        ax.plot(xs, -f(xs), color="#c33", lw=0.7, ls="--")
        n = numbers(v)
        ax.set_title(f"{LABEL[v]}  |  opening on the face {n['opening']:.1f}, gap between openings {n['gap']:.1f} "
                     f"(reads as {n['vis']:.1f}: < 0.3 below the face)  |  rods proud {n['rod']:.2f}  |  "
                     f"1 mm from the land {n['mat1']:.2f}  |  bridge at the inner face {n['bridge_in']:.1f}, rods' outer edges ±{n['rod_edge']:.2f} (glass ±15.6)", fontsize=8)
        ax.set_xlim(-24, 24); ax.set_ylim(-8.5, 1.5); ax.set_aspect("equal"); ax.grid(alpha=0.25); ax.set_yticks([])
    ax.set_xlabel("x, mm (front view, left to right); outside up; red dashed: the face without slots; glass light blue, rods blue")
    # top end, cut along the slot at x = xc (fill) and through the lip (x = xc + 4.05 + 1.0, line), print orientation
    for j, v in enumerate(("A", "A'")):
        ax = fig.add_subplot(gs[len(VAR), j]); xc = VAR[v]["xc"]
        ss = np.linspace(S1 - 6, S1 + 7, 2601)
        T = surface(np.full_like(ss, xc), ss, v); keep = T < T_IN - 1e-9
        top = world(0 * ss[keep], T[keep], ss[keep]); bot = world(0 * ss[keep], np.full(keep.sum(), T_IN), ss[keep])
        poly = np.vstack([top[:, 1:], bot[::-1, 1:]])
        ax.add_patch(Polygon(poly, closed=True, fc="#ece6d8", ec="#555", lw=1.1))
        wf = world(0 * ss, f(np.full_like(ss, xc)), ss)
        ax.plot(wf[:, 1], wf[:, 2], color="#c33", lw=0.7, ls="--")
        z0 = world(0, T_IN, S1)[2]; y0 = world(0, T_IN, S1)[1]
        ax.plot([y0, y0 - 4], [z0, z0 + 4], color="#2a7", lw=0.9, ls=":", label="45 deg (printable ceiling)")
        ax.annotate("", xy=(y0 + 2.5, z0 + 4), xytext=(y0 + 2.5, z0 - 1), arrowprops=dict(arrowstyle="->", color="#555"))
        ax.text(y0 + 2.8, z0 + 1, "print\nup", fontsize=8, color="#555")
        ax.set_xlim(y0 - 7, y0 + 5); ax.set_ylim(z0 - 5, z0 + 7)
        n = numbers(v)
        ax.set_title(f"{v}: top end, cut along the slot centre\nprinted standing: ceiling {n['overhang']:.1f} deg from vertical"
                     + (f"; opening {n['ext']:.2f} longer per end" if n['ext'] else ""), fontsize=9)
        ax.set_aspect("equal"); ax.grid(alpha=0.25); ax.legend(fontsize=7, loc="lower right")
        ax.set_xlabel("world y (front left), mm"); ax.set_ylabel("world z, mm")
    fig.suptitle("Pebble front: sections through the slots at true scale (glass light blue, rods blue)", fontsize=11)
    fig.tight_layout(); p = OUT / "slot-ends-nose-section.png"; fig.savefig(p, dpi=115); print(p)


def clay_png():
    import pyvista as pv
    xs = np.arange(-26, 26.001, 0.05)
    ss = np.unique(np.r_[np.arange(12, S0 - 4, 0.5), np.arange(S0 - 4, S0 + 1, 0.04), np.arange(S0 + 1, S1 - 1, 0.5),
                         np.arange(S1 - 1, S1 + 5, 0.04), np.arange(S1 + 5, 104, 0.5)])
    X, S = np.meshgrid(xs, ss)
    nv = len(VAR)
    pl = pv.Plotter(off_screen=True, window_size=(nv * 560, 2 * 720), shape=(2, nv), lighting="three lights")
    e33 = math.radians(33)
    views = (((-0.22, -math.cos(e33), math.sin(e33)), "seated (33 deg above level)", world(0.0, 2.0, 58.0), 210, 24),
             ((-0.45, -1.0, 0.02), "top end of the right slot, from the front", None, 62, 25))
    for j, v in enumerate(VAR):
        V = VAR[v]; T = surface(X, S, v)
        body = pv.StructuredGrid(*np.moveaxis(world(X, T, S), -1, 0)).extract_surface().compute_normals(feature_angle=50)
        rods = []
        for xc in (-V["xc"], V["xc"]):
            th = np.linspace(0, math.pi, 49); sr = np.linspace(S0 + 0.1, S1 - 0.1, 2); TH, SR = np.meshgrid(th, sr)
            base = T_IN - CROWN + 4.0
            rods.append(pv.StructuredGrid(*np.moveaxis(world(xc + 4.0 * np.cos(TH), base - 4.0 * np.sin(TH), SR), -1, 0)))
        for i, (d, name, foc, dist, ang) in enumerate(views):
            pl.subplot(i, j); pl.set_background("#d8d5cf", top="#f3f1ed")
            pl.add_mesh(body, color="#ece6d8", smooth_shading=True, specular=0.15, specular_power=10, ambient=0.18, diffuse=0.85)
            for r in rods:
                pl.add_mesh(r, color="#9cc9e8", smooth_shading=True, specular=0.5, specular_power=30, ambient=0.3)
            if foc is None:
                foc = world(V["xc"] + 2.0, 1.0, S1 + 0.5)
            dd = np.array(d) / np.linalg.norm(d)
            pl.camera_position = [tuple(foc + dd * dist), tuple(foc), (0, 0, 1)]; pl.camera.view_angle = ang
            pl.add_text(f"{LABEL[v]}\n{name}", font_size=9, color="black")
    pl.enable_anti_aliasing("ssaa"); p = OUT / "slot-ends-nose-clay.png"; pl.screenshot(str(p)); pl.close(); print(p)


if __name__ == "__main__":
    for v in VAR:
        print(v, {k: round(float(x), 2) for k, x in numbers(v).items()})
    section_png(); clay_png()
