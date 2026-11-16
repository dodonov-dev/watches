#!/usr/bin/env python3
"""Roly-poly study for the desk housing ("soft cairn" that rocks sideways and rights itself).
A numeric mass model, not CAD: the body is an analytic surface, the parts are boxes with ASSUMED masses.

  ~/.venvs/cad/bin/python rolypoly.py [KEY=value ...]     -> out-rolypoly/report.txt, body STL, clay views

Axes: x right (seen from the front), y front -> back (front is -y), z up from the bottom pole. Tubes along z.
Asymmetry: Z2L / A2L and Z2R / A2R (default: Z2 / A2) give the left and the right outline their own shoulder, so one
side narrows later than the other. The rocking arc under it stays the same on both sides; the report says how far
the ballast has to sit off-centre for the tubes to hang plumb.
Shape: plan sections are superellipses (exponent PE) with half-width a(z), half-depth bf(z) to the front and bb(z)
to the back. Front view: the underside is a circular arc of radius RR (the rocking radius). Side view: the underside
is nearly flat fore-aft, so it rocks sideways only and stands firm in pitch.
"""
import sys, math, json, pathlib
import numpy as np

P = dict(H=128.0, RR=44.0, ARC_DEG=62.0, Z2=96.0, A2=31.0,      # front silhouette: arc, shoulder to (Z2, A2), crown
         BF=23.0, BB=27.0, ZC=28.0, NC=3.2, ZF=70.0, MF=2.8, MB=2.2, PE=2.6,   # depth: belly corner, front/back crowns
         WALL=2.4, RHO_SHELL=1.24,                                 # printed shell: PLA 2.4 mm (SLS PA12: 2.0 / 1.0)
         PANEL_W=40.0, PANEL_Z0=26.0, PANEL_H=79.0, PANEL_T=4.0, PANEL_R=7.0, FLARE=7.0, PANEL_SET=1.0, M_PANEL=12.0,
         M_BOARD=30.0, BOARD_T=9.3, PCB_H=78.85, GASKET=0.5,       # ASSUMED 30 g: weigh the board
         M_BAT=55.0, BAT_L=68.0, BAT_H=35.0, BAT_T=10.0,           # ASSUMED 55 g; lies on its long edge behind the board
         M_MISC=10.0, Z_MISC=35.0, Y_MISC=8.0,
         BALLAST_TOP=22.0, RHO_BALLAST=5.1,                        # steel shot in epoxy ~5.1; solid steel 7.85
         XOFF=0.0, XZ1=62.0,                                       # upper body + panel moved sideways (- = left) over the arc
         CUT=0.0,                                                  # stable variant: the bottom cut off flat at this z
         LOGO_X=0.0, LOGO_W=14.0,                                  # logo on the front at this x (0 = on the left flank; -1 = right flank)
         STAG=0.0,                                                 # tubes staggered and shortened by this (+ = the right one lower)
         VIEW_X=-0.55,                                             # the hero camera's side (- = from the left)
         TILT=15.0)
TAG = ""
for kv in sys.argv[1:]:
    k, v = kv.split("=")
    if k == "OUT":
        TAG = "-" + v
    else:
        P[k] = float(v)
H, RR, WALL, PE = P["H"], P["RR"], P["WALL"], P["PE"]
XOFF, CUT = P["XOFF"], P["CUT"]
OUT = pathlib.Path(__file__).parent / ("out-rolypoly" + TAG)
OUT.mkdir(exist_ok=True)
KAPPA = math.gamma(1 + 1 / PE) ** 2 / math.gamma(1 + 2 / PE)       # superellipse area = 4 a b KAPPA

# ---- shape ------------------------------------------------------------------------------------------------------
Z1 = RR * (1 - math.cos(math.radians(P["ARC_DEG"])))
A1 = RR * math.sin(math.radians(P["ARC_DEG"]))
S1 = (RR - Z1) / A1
SIDES = {s: (P.get("Z2" + s, P["Z2"]), P.get("A2" + s, P["A2"])) for s in "LR"}   # shoulder end (z, half-width) per side
ASYM = SIDES["L"] != SIDES["R"]


def a_side(z, side):
    """Half-width of the outline on one side ('L' = x < 0, the viewer's left; 'R' = x > 0)."""
    z2, a2 = SIDES[side]
    rc = H - z2
    z = np.asarray(z, float)
    t = np.clip((z - Z1) / (z2 - Z1), 0, 1)
    d = z2 - Z1
    herm = (2 * t**3 - 3 * t**2 + 1) * A1 + (t**3 - 2 * t**2 + t) * d * S1 + (-2 * t**3 + 3 * t**2) * a2
    arc = np.sqrt(np.clip(2 * RR * z - z * z, 0, None))
    crown = a2 / rc * np.sqrt(np.clip(rc**2 - (z - z2) ** 2, 0, None))
    return np.where(z <= Z1, arc, np.where(z >= z2, crown, herm))


def xc(z):
    """Centre line of the outline: 0 over the rocking arc, XOFF from XZ1 up."""
    t = np.clip((np.asarray(z, float) - Z1) / (P["XZ1"] - Z1), 0, 1)
    return XOFF * t * t * (3 - 2 * t)


def a_of(z, x0=0.0):
    """Free half-width round x0: what has to fit inside."""
    return np.minimum(a_side(z, "L") - (xc(z) - x0), a_side(z, "R") + (xc(z) - x0))


def a_at(x, z):
    return np.where(np.asarray(x) - xc(z) < 0, a_side(z, "L"), a_side(z, "R"))


def _corner(z):   # 0 at the pole -> 1 at ZC: the belly's lower corner in the side view (flat-ish underside)
    u = np.clip((P["ZC"] - z) / P["ZC"], 0, 1)
    return (1 - u ** P["NC"]) ** (1 / P["NC"])


def bf_of(z):
    z = np.asarray(z, float)
    u = np.clip((z - P["ZF"]) / (H - P["ZF"]), 0, 1)
    return P["BF"] * _corner(z) * (1 - u ** P["MF"]) ** (1 / P["MF"])


def bb_of(z):
    z = np.asarray(z, float)
    u = np.clip((z - P["ZC"]) / (H - P["ZC"]), 0, 1)
    return P["BB"] * _corner(z) * (1 - u ** P["MB"]) ** (1 / P["MB"])


def y_front(x, z):
    a = np.maximum(a_at(x, z), 1e-6)
    return -bf_of(z) * np.clip(1 - (np.abs(x - xc(z)) / a) ** PE, 0, None) ** (1 / PE)


# alcove: a flat panel set back behind the front surface, with a soft flare round it
PW, PZ0, PZ1 = P["PANEL_W"], P["PANEL_Z0"], P["PANEL_Z0"] + P["PANEL_H"]
PZC = (PZ0 + PZ1) / 2


def sd_panel(x, z):   # signed distance to the rounded panel outline in the x-z plane (negative inside)
    r = P["PANEL_R"]
    qx, qz = np.abs(x - XOFF) - (PW / 2 - r), np.abs(z - PZC) - (P["PANEL_H"] / 2 - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qz, 0)) + np.minimum(np.maximum(qx, qz), 0) - r


_bx = XOFF + np.concatenate([np.linspace(-PW / 2, PW / 2, 81), np.full(161, PW / 2), np.full(161, -PW / 2)])
_bz = np.concatenate([np.full(81, PZ1), np.linspace(PZ0, PZ1, 161), np.linspace(PZ0, PZ1, 161)])
Y_PANEL = float(np.max(y_front(_bx, _bz))) + P["PANEL_SET"]       # outer face of the panel


def body_grid(nz=300, nt=1440):
    u = np.linspace(0, 1, nz)
    z = CUT + (H - CUT) * (1 - np.cos(np.pi * u)) / 2
    z[0], z[-1] = max(CUT, 1e-3), H - 1e-3
    th = np.linspace(0, 2 * np.pi, nt, endpoint=False)
    c, s = np.cos(th), np.sin(th)
    ex = np.sign(c) * np.abs(c) ** (2 / PE)
    ey = np.sign(s) * np.abs(s) ** (2 / PE)
    Z = np.repeat(z[:, None], nt, 1)
    X = xc(z)[:, None] + np.where(ex[None, :] < 0, a_side(z, "L")[:, None], a_side(z, "R")[:, None]) * ex[None, :]
    Y = np.where(ey[None, :] < 0, bf_of(z)[:, None], bb_of(z)[:, None]) * ey[None, :]
    sd = sd_panel(X, Z)
    w = np.clip(1 - sd / P["FLARE"], 0, 1)
    w = w * w * (3 - 2 * w)
    front = Y < 0
    Y = np.where(front, Y + w * np.maximum(0, Y_PANEL - Y), Y)
    return X, Y, Z, (sd < 0) & front


X, Y, Z, IN_PANEL = body_grid()

# ---- masses -----------------------------------------------------------------------------------------------------
def tri_areas(X, Y, Z):
    p = np.stack([X, Y, Z], -1)
    p00, p01 = p[:-1], np.roll(p, -1, 1)[:-1]
    p10, p11 = p[1:], np.roll(p, -1, 1)[1:]
    a1 = 0.5 * np.linalg.norm(np.cross(p01 - p00, p10 - p00), axis=-1)
    a2 = 0.5 * np.linalg.norm(np.cross(p11 - p01, p10 - p01), axis=-1)
    cen = (p00 + p01 + p10 + p11) / 4
    return a1 + a2, cen


area, cen = tri_areas(X, Y, Z)
skin = ~(IN_PANEL[:-1] & IN_PANEL[1:])                              # the panel area is the insert, not the shell
dm = area * skin * WALL * P["RHO_SHELL"] / 1000.0                   # g
parts = []   # (name, mass g, (x, y, z), inertia about its own y axis g mm^2)
c_shell = (cen * dm[..., None]).sum((0, 1)) / dm.sum()
i_shell = (dm * ((cen[..., 0] - c_shell[0]) ** 2 + (cen[..., 2] - c_shell[2]) ** 2)).sum()
parts.append(("shell", dm.sum(), tuple(c_shell), i_shell))

zb = np.linspace(CUT + WALL, P["BALLAST_TOP"], 200)
ai, bfi, bbi = (np.clip(f(zb) - WALL, 0, None) for f in (a_of, bf_of, bb_of))
A_in = 2 * KAPPA * ai * (bfi + bbi)
m_bal = P["RHO_BALLAST"] / 1000.0 * np.trapezoid(A_in, zb)
zc_bal = np.trapezoid(A_in * zb, zb) / np.trapezoid(A_in, zb)
yc_bal = np.trapezoid(A_in * 0.43 * (bbi - bfi), zb) / np.trapezoid(A_in, zb)
i_bal = P["RHO_BALLAST"] / 1000.0 * np.trapezoid(A_in * (0.23 * ai**2 + (zb - zc_bal) ** 2), zb)
parts.append(("ballast", m_bal, (0.0, yc_bal, zc_bal), i_bal))

y_board = Y_PANEL + P["PANEL_T"] + P["GASKET"] + P["BOARD_T"] / 2
parts.append(("panel", P["M_PANEL"], (XOFF, Y_PANEL + P["PANEL_T"] / 2, PZC), P["M_PANEL"] * (PW**2 + P["PANEL_H"] ** 2) / 12))
parts.append(("board", P["M_BOARD"], (XOFF, y_board, PZ0 + P["PCB_H"] / 2), P["M_BOARD"] * (33.35**2 + P["PCB_H"] ** 2) / 12))
zz = np.linspace(P["BALLAST_TOP"] + 1, 80, 600)
_zh = np.linspace(0, P["BAT_H"], 36)[None, :] + zz[:, None]         # the battery's height at each candidate level
_lo = (xc(_zh) - a_side(_zh, "L")).max(1) + WALL                    # free span inside the shell over that height
_hi = (xc(_zh) + a_side(_zh, "R")).min(1) - WALL
fit = np.where(_hi - _lo >= P["BAT_L"] + 1.0)[0]
z_bat0 = float(zz[fit[0]]) if len(fit) else float("nan")            # lowest level where the belly is wide enough
x_bat = float((_lo + _hi)[fit[0]] / 2) if len(fit) and XOFF else 0.0   # centred in the free span
y_bat = y_board + P["BOARD_T"] / 2 + 1 + P["BAT_T"] / 2
parts.append(("battery", P["M_BAT"], (x_bat, y_bat, z_bat0 + P["BAT_H"] / 2), P["M_BAT"] * (P["BAT_L"] ** 2 + P["BAT_H"] ** 2) / 12))
parts.append(("misc", P["M_MISC"], (0.0, P["Y_MISC"], P["Z_MISC"]), 0.0))

# an asymmetric shell pulls the centre of mass sideways: put the ballast off-centre by as much as brings it back
x_off = sum(p[1] * p[2][0] for p in parts if p[0] != "ballast")
lean_untrimmed = x_off / sum(p[1] for p in parts)                  # mm of sideways offset with centred ballast
if not CUT:                                                        # a flat foot needs no trim
    parts[1] = ("ballast", m_bal, (-x_off / m_bal, yc_bal, zc_bal), i_bal)
M = sum(p[1] for p in parts)
G = np.array([sum(p[1] * p[2][i] for p in parts) / M for i in range(3)])
I_cm = sum(p[3] + p[1] * ((p[2][0] - G[0]) ** 2 + (p[2][2] - G[2]) ** 2) for p in parts)   # about the y axis through G
h = G[2]
margin = RR - h
ASYM = ASYM or XOFF != 0
T_roll = 2 * math.pi * math.sqrt((I_cm / M + h * h) * 1e-6 / (9.81 * margin * 1e-3)) if margin > 0 else float("nan")

# ---- stability: height of the centre of mass over the desk against tilt (support function of the outer surface) ---
pts = np.stack([X, Y, Z], -1).reshape(-1, 3)


def g_height(theta_deg, axis):
    t = math.radians(theta_deg)
    d = np.array([math.sin(t), 0, -math.cos(t)]) if axis == "roll" else np.array([0, math.sin(t), -math.cos(t)])
    return float((pts @ d).max() - G @ d)


def righting_limit(axis, sign=1):
    th = np.arange(0, 121, 1.0)
    u = np.array([g_height(sign * t, axis) for t in th])
    up = np.where(np.diff(u) < -1e-6)[0]
    return (float(th[up[0]]) if len(up) else 120.0), u


lim_roll, u_roll = righting_limit("roll")           # leaning to the viewer's right
lim_roll_l, u_roll_l = righting_limit("roll", -1)
lim_fwd, u_fwd = righting_limit("pitch", -1)      # top goes forward (falls on its face)
lim_back, u_back = righting_limit("pitch", 1)
fine = np.arange(-8, 8.01, 0.1)
rest_pitch = float(fine[int(np.argmin([g_height(t, "pitch") for t in fine]))])     # + = leans back
push = lambda u, lim: M / 1000 * 9.81 * (u[int(lim)] - u[0])                          # mJ to tip it past the limit
batt_ok = len(fit) > 0 and bb_of(z_bat0 + P["BAT_H"]) - WALL >= y_bat + P["BAT_T"] / 2

R = []
_zz = np.linspace(0, H, 500)
R.append(f"ROLY-POLY STUDY  body {float((xc(_zz) + a_side(_zz, 'R')).max() - (xc(_zz) - a_side(_zz, 'L')).min()):.0f} wide x {P['BF'] + P['BB']:.0f} deep x {H:.0f} tall; rocking radius {RR:.0f}; wall {WALL} at {P['RHO_SHELL']} g/cm3")
R.append(f"panel        {PW:.0f} x {P['PANEL_H']:.0f}, z {PZ0:.0f}..{PZ1:.0f}, outer face {-Y_PANEL:.1f} in front of the centre plane; "
         f"set back {Y_PANEL - float(y_front(XOFF, PZC)):.1f} at its centre, {P['PANEL_SET']:.1f} at its top corners")
R.append("masses g     " + ", ".join(f"{n} {m:.0f} @ z {c[2]:.0f}" for n, m, c, _ in parts) + f"  -> total {M:.0f}")
R.append(f"  ballast    up to z {P['BALLAST_TOP']:.0f}: {np.trapezoid(A_in, zb) / 1000:.1f} cm3 at {P['RHO_BALLAST']} g/cm3; battery on its long edge from z {z_bat0:.1f} "
         f"({'fits' if batt_ok else 'DOES NOT FIT'})")
if CUT:
    R.append(f"centre of mass  {h - CUT:.1f} over the desk (x {G[0]:.2f}, y {G[1]:.1f}); stable variant: bottom cut flat at z {CUT:.0f}, "
             f"foot {2 * float(a_side(CUT, 'L')):.0f} wide x {float(bf_of(CUT) + bb_of(CUT)):.0f} deep, {H - CUT:.0f} tall")
    R.append(f"tips over    beyond {lim_roll:.0f} deg to the right, {lim_roll_l:.0f} to the left, {lim_fwd:.0f} forward, {lim_back:.0f} backward")
else:
    R.append(f"centre of mass  z {h:.1f} (x {G[0]:.2f}, y {G[1]:.1f}); rocking radius - height = {margin:.1f} mm ({'rights itself' if margin > 0 else 'FALLS OVER'})")
    if ASYM:
        R.append(f"asymmetry    upper body {XOFF:+.1f} mm off the arc's centre; left shoulder to z {SIDES['L'][0]:.0f} / half-width {SIDES['L'][1]:.0f}, right to z {SIDES['R'][0]:.0f} / {SIDES['R'][1]:.0f}: "
                 f"the shell's centre of mass sits {parts[0][2][0]:+.1f} mm off; with centred ballast the clock would lean "
                 f"{math.degrees(math.atan(lean_untrimmed / margin)):+.1f} deg; it hangs plumb with the ballast's centre {parts[1][2][0]:+.2f} mm off-centre (applied below)")
    R.append(f"sideways     period {T_roll:.2f} s; rights itself from up to {lim_roll:.0f} deg to the right, {lim_roll_l:.0f} to the left; a centre of mass 0.5 mm off to one side leans it "
             f"{math.degrees(math.atan(0.5 / margin)):.1f} deg (trim needed)")
    R.append(f"fore-aft     rests leaning {rest_pitch:+.1f} deg (+ = back); falls forward beyond {lim_fwd:.0f} deg ({push(u_fwd, lim_fwd):.1f} mJ), "
             f"backward beyond {lim_back:.0f} deg ({push(u_back, lim_back):.1f} mJ); sideways the same push energy tilts it "
             f"{float(np.interp(push(u_fwd, lim_fwd), M / 1000 * 9.81 * (u_roll - u_roll[0]), np.arange(0, 121.0))):.0f} deg")
text = "\n".join(R)
(OUT / "report.txt").write_text(text + "\n")
print(text)

# ---- clay views: upright and caught mid-rock -------------------------------------------------------------------------
import pyvista as pv

Xc, Yc, Zc = (np.concatenate([A, A[:, :1]], 1) for A in (X, Y, Z))
body = pv.StructuredGrid(Xc[..., None], Yc[..., None], Zc[..., None]).extract_surface(algorithm="dataset_surface").triangulate()
body.save(str(OUT / "body.stl"))
q = body.points
col = np.tile(np.array([233, 226, 211], np.uint8), (len(q), 1))                       # ivory
on_panel = (sd_panel(q[:, 0], q[:, 2]) < 0) & (q[:, 1] < 0) & (np.abs(q[:, 1] - Y_PANEL) < 0.05)
col[on_panel] = (40, 40, 43)                                                              # the dark panel
zt = PZ0 + 7.45 + 67.65 / 2                                                               # the lit tubes' centre
for sx in (-1, 1):                                                                        # the two rods, as strips
    zs = zt - sx * P["STAG"] / 2                                                          # staggered: each rod STAG shorter
    col[on_panel & (np.abs(q[:, 0] - XOFF - sx * 10.23) < 4.0) & (np.abs(q[:, 2] - zs) < 33.3 - abs(P["STAG"]) / 2)] = (122, 190, 226)
lw = P["LOGO_W"]                                                                          # letters "EH": height about 0.64 of the width
if P["LOGO_X"] > 0:                                                                       # logo on the front of the belly
    col[(q[:, 1] < 0) & (np.abs(q[:, 0] - P["LOGO_X"]) < lw / 2) & (np.abs(q[:, 2] - 25.5 - lw * 0.32) < lw * 0.32)] = (255, 176, 64)
elif P["LOGO_X"] < 0:                                                                     # logo on the right flank
    col[(q[:, 0] > xc(q[:, 2]) + 0.8 * a_side(q[:, 2], "R")) & (np.abs(q[:, 1] - 2) < lw / 2) & (np.abs(q[:, 2] - 25.5 - lw * 0.32) < lw * 0.32)] = (255, 176, 64)
else:                                                                                     # logo, left flank
    col[(q[:, 0] < -0.8 * a_side(q[:, 2], "L")) & (np.abs(q[:, 1] - 2) < 7.5) & (np.abs(q[:, 2] - 34) < 4.75)] = (255, 176, 64)
body["rgb"] = col


def posed(tilt_deg):
    m = body.copy()
    m.rotate_y(tilt_deg, point=(0, 0, 0), inplace=True)      # + = leans to the viewer's right
    m.translate((0, 0, -m.bounds[4]), inplace=True)
    return m


def shot(fname, poses, views, size=(820, 1100)):
    pl = pv.Plotter(off_screen=True, window_size=(size[0] * len(views), size[1]), shape=(1, len(views)))
    for i, (tilt, (d, par)) in enumerate(zip(poses, views)):
        m = posed(tilt)
        pl.subplot(0, i)
        pl.set_background("#d8d5cf", top="#f3f1ed")
        pl.add_mesh(m, scalars="rgb", rgb=True, smooth_shading=True, specular=0.05, ambient=0.3, diffuse=0.8)
        pl.add_mesh(pv.Plane(center=(0, 0, -0.01), direction=(0, 0, 1), i_size=700, j_size=700), color="#cfcac2", ambient=0.5, diffuse=0.6)
        c = (0, 2, H / 2)
        n = sum(x * x for x in d) ** 0.5
        pl.camera_position = [tuple(c[j] + d[j] / n * (700 if not par else 500) for j in range(3)), c, (0, 0, 1)]
        if par:
            pl.camera.parallel_projection = True
            pl.camera.parallel_scale = H * 0.62
        else:
            pl.camera.view_angle = 14
        pl.reset_camera_clipping_range()
    pl.enable_anti_aliasing("ssaa")
    pl.screenshot(str(OUT / fname))
    pl.close()
    print(OUT / fname)


HERO, FRONT, SIDE = ((P["VIEW_X"], -1.0, 0.34), False), ((0, -1, 0), True), ((-1, 0, 0), True)
shot("clay-hero.png", [0, P["TILT"], 0], [HERO, HERO, ((0.9, 1.0, 0.34), False)])
shot("clay-ortho.png", [0, P["TILT"], 0], [FRONT, FRONT, SIDE], size=(700, 1000))
