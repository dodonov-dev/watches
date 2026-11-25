"""Pebble slots, round C (user, 2026-11-24): A's openings as printed, the tubes at c-c 18, the horns fixed.
  A18     A as printed (smooth.py round A's lip(): a circular arc vertical at the 0.6 land, radius solved per side so it
          would meet the bowed face tangentially, ended LIP_SHORT_DEG before tangency and run out along its tangent;
          extruded S0..S1; straight ends square to the face, full depth), at c-c 18. The horns: where each lip stops at
          the straight end, the end plane leaves the lip's crescent as a step whose outer tail runs out at 3 deg to the
          face (a feather; printed standing a 75 deg ceiling)
  D-l     the horn fix: over the last l mm before each end the lip's depth below the face eases (smoothstep, C1) to 0;
          its width (its line on the face) unchanged, so the opening's outline stays A's; the corner step 0; in the
          last l mm the land's wall runs on up to the face
Body frame (x, t, s); both slots from one formula in |x| (mirror-exact about x = 0); the face is the oval's bow f(x),
straight along s.
    ~/.venvs/cad/bin/python slot_corners_c.py [outdir]
"""
import sys, math, pathlib
import numpy as np
from slot_edges import f, HALF, LAND, CROWN

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path(__file__).parents[4] / "images/desk-housing-v3")
S0, S1 = 24.70, 91.55                                  # smooth.py SLOT_S
XC = 9.0
T_IN = 3.0 + float(f(20.46 / 2))                       # smooth.py PEBBLE_FRONT 3.392
L = T_IN - LAND
LIP_SHORT_DEG = 3.0
ROD_W, ROD_GAP = 8.0, 0.1
C15, S15 = math.cos(math.radians(15)), math.sin(math.radians(15))
VAR = {"A18": None, "D-1.5": 1.5, "D-3": 3.0}
LABEL = {"A18": "A at c-c 18, as printed (horns)", "D-1.5": "fix: lip depth eases out over the last 1.5",
         "D-3": "fix: lip depth eases out over the last 3"}


def lip_arc(xc, sg):
    """smooth.py round A, PebbleModel.lip(): (r, phi*) of the tangent arc on side sg of the slot at xc"""
    F = lambda u: float(f(xc + sg * u))
    dF = lambda u: (F(u + 1e-6) - F(u - 1e-6)) / 2e-6
    r, ph = 2.0, math.pi / 2
    for _ in range(500):
        u = HALF + r * (1 - math.cos(ph))
        ph = math.pi / 2 + math.atan(dF(u))
        r_new = (L - F(u)) / math.sin(ph)
        if abs(r_new - r) < 1e-12:
            break
        r = 0.5 * (r + r_new)
    return r, ph


LIPS = {sg: lip_arc(XC, sg) for sg in (-1, 1)}         # the right slot; the left one mirrors it


def lip_profile(dx, sg):
    """A's lip: t of the cut's surface at dx beyond the land (side sg of the right slot), before max() with the face"""
    r, ph = LIPS[sg]
    pe = ph - math.radians(LIP_SHORT_DEG)
    dxe = r * (1 - math.cos(pe))
    with np.errstate(invalid="ignore"):
        arc = L - r * np.sin(np.arccos(np.clip(1 - dx / r, -1, 1)))
    run = (L - r * math.sin(pe)) - (dx - dxe) / math.tan(pe)
    return np.where(dx <= dxe, arc, run)


def surface(x, s, v):
    lam = VAR[v]
    x, s = np.broadcast_arrays(np.asarray(x, float), np.asarray(s, float))
    fx = f(x)
    u = np.abs(x) - XC
    sg = np.where(u >= 0, 1, -1)                         # +1: the slot's outer side (|x| > XC)
    dx = np.abs(u) - HALF
    inside_s = (s > S0) & (s < S1)
    lip = np.where(sg > 0, lip_profile(np.clip(dx, 0, None), 1), lip_profile(np.clip(dx, 0, None), -1))
    lip = np.maximum(lip, fx)
    if lam is not None:
        e = np.clip(np.minimum(s - S0, S1 - s), 0, None)
        k = np.clip(e / lam, 0, 1); k = k * k * (3 - 2 * k)
        lip = fx + k * (lip - fx)
    p = np.where(inside_s, np.where(dx < 0, T_IN, lip), fx)
    return np.maximum(p, fx)


def numbers(v):
    sm = (S0 + S1) / 2
    xs = np.linspace(-24, 24, 96001); P = surface(xs, sm, v); d = P - f(xs)
    r = xs[(xs > 0) & (d > 1e-9)]
    lip_in, lip_out = (XC - HALF) - r.min(), r.max() - (XC + HALF)
    # the corner step: just inside the end vs just past it, beside the slot
    dxs = np.linspace(1e-6, 4, 4001)
    step = max(float((surface(XC + HALF + dxs, S1 - 1e-7, v) - surface(XC + HALF + dxs, S1 + 1e-7, v)).max()),
               float((surface(XC - HALF - dxs, S1 - 1e-7, v) - surface(XC - HALF - dxs, S1 + 1e-7, v)).max()))
    # overhang printed standing beside the slot near the top end (the end wall itself apart), and at the bottom end
    h = 0.01; xx = np.arange(XC - HALF - 4, XC + HALF + 4, h)
    ov = {}
    for name, (sa, sb) in (("top", (S1 - 5, S1 - 0.005)), ("bottom", (S0 + 0.005, S0 + 5))):
        ss = np.arange(sa, sb, h); X, S = np.meshgrid(xx, ss); T = surface(X, S, v)
        Ts, Tx = np.gradient(T, h, h); nn = np.sqrt(Tx ** 2 + 1 + Ts ** 2)
        o = np.degrees(np.arcsin(np.clip(-(S15 + Ts * C15) / nn, 0, 1)))
        ok = (T < T_IN - 1e-9) & (np.abs(Tx) < 40) & (np.abs(np.abs(X) - XC) > HALF + 0.02)
        ov[name] = float(o[ok].max())
    xw = np.linspace(XC - HALF, XC + HALF, 401)
    return dict(lip_in=lip_in, lip_out=lip_out, bridge=2 * r.min(), opening=r.max() - r.min(), step=step,
                ov_top=ov["top"], ov_bot=ov["bottom"], rods_proud=float(f(XC)) - (T_IN - CROWN),
                flat=(float((T_IN - f(xw)).min()), float(T_IN - f(XC))), r=(LIPS[-1][0], LIPS[1][0]))


def world(x, t, s): return np.stack([np.broadcast_to(x, np.shape(t)), t * C15 + s * S15, s * C15 - t * S15], -1)


def clay_png(N):
    import pyvista as pv
    fine = lambda a, b, h: np.arange(a, b, h)
    edges = [sx * (XC + g * HALF) for sx in (-1, 1) for g in (-1, 1)]
    cl = np.r_[[e + o * d for e in edges for o in [np.sign(e) * np.sign(abs(e) - XC)] for d in (-1e-4, 1e-4, 0.0033, 0.013, 0.03)]]
    xs = np.unique(np.round(np.r_[fine(-24, 24.0001, 0.1), fine(-XC - HALF - 4, -XC + HALF + 4, 0.02),
                                  fine(XC - HALF - 4, XC + HALF + 4, 0.02), edges, cl], 7))
    ss = np.unique(np.round(np.r_[fine(10, S0 - 5, 0.5), fine(S0 - 5, S0 + 5, 0.02), fine(S0 + 5, S1 - 5, 0.5),
                                  fine(S1 - 5, S1 + 5, 0.02), fine(S1 + 5, 104, 0.5), [S0 - 1e-4, S0 + 1e-4, S1 - 1e-4, S1 + 1e-4]], 7))
    X, S = np.meshgrid(xs, ss)
    nv = len(VAR)
    pl = pv.Plotter(off_screen=True, window_size=(nv * 640, 3 * 560), shape=(3, nv), lighting="none")
    e33 = math.radians(33)
    corner = world(-(XC + 0.5), 1.5, S1 - 1.0)
    views = (((-0.22, -math.cos(e33), math.sin(e33)), "seated (33 deg above level)", world(0.0, 2.0, 58.0), 200, 24, "clay"),
             ((-0.35, -1.0, 0.40), "left slot's top end, outer corner on the left", corner, 45, 17, "clay"),
             ((-0.10, -1.0, 0.45), "front, a little from above (as in Bambu)", world(0.0, 2.0, 84.0), 120, 25, "green"))
    for j, v in enumerate(VAR):
        T = surface(X, S, v)
        g_ = pv.StructuredGrid(*np.moveaxis(world(X, T, S), -1, 0)); g_.point_data["t"] = T.ravel(order="F")
        body = g_.extract_surface(algorithm=None).clip_scalar("t", value=T_IN - 1e-6, invert=True)    # through-slots open
        body = body.extract_surface(algorithm=None).compute_normals(feature_angle=40, auto_orient_normals=True)
        for i, (d, name, foc, dist, ang, style) in enumerate(views):
            pl.subplot(i, j)
            dd = np.array(d) / np.linalg.norm(d)
            up = np.array([0, 0, 1.0]); right = np.cross(-dd, up); right /= np.linalg.norm(right)
            if style == "green":
                pl.set_background("#3a3d42", top="#55595f"); col, spec = "#58b947", 0.25
            else:
                pl.set_background("#d8d5cf", top="#f3f1ed"); col, spec = "#ece6d8", 0.15
            pl.add_light(pv.Light(position=tuple(foc + dist * (dd - 0.9 * right + 1.0 * up)), focal_point=tuple(foc), intensity=0.95), only_active=True)
            pl.add_light(pv.Light(position=tuple(foc + dist * (dd + 0.6 * right - 0.3 * up)), focal_point=tuple(foc), intensity=0.25), only_active=True)
            pl.add_mesh(body, color=col, smooth_shading=True, specular=spec, specular_power=12, ambient=0.15, diffuse=0.85)
            pl.camera_position = [tuple(foc + dd * dist), tuple(foc), (0, 0, 1)]; pl.camera.view_angle = ang
            n = N[v]
            txt = f"{LABEL[v]}\n{name}"
            if i == 0:
                txt += f"\ncorner step {n['step']:.2f}; top-end ceiling beside the slot {n['ov_top']:.0f} deg"
            pl.add_text(txt, font_size=9, color="white" if style == "green" else "black")
    pl.enable_anti_aliasing("ssaa"); p = OUT / "slot-corners-C-clay.png"; pl.screenshot(str(p)); pl.close(); print(p)


if __name__ == "__main__":
    N = {v: numbers(v) for v in VAR}
    for v, n in N.items():
        print(v, {k: (round(x, 3) if isinstance(x, float) else tuple(round(y, 3) for y in x) if isinstance(x, tuple) else x) for k, x in n.items()})
    clay_png(N)
