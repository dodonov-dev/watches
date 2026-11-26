#!/usr/bin/env python3
"""Seam coupon for the pebble: the dome cap (z >= Z0, above the slots) of a relief shell, once per variant on one plate, the
seam painted along the relief's edges at the back. Shows how the layer seam looks when it rides the arrises, and what
a scarf joint changes (outer-first walls and a slow outer wall are held back in VARIANTS). The cap is the band where the seam must be outside:
every layer is a closed ring there (in the slot zone the seam can sit inside the cavity).
  route   per layer (0.08) the back contour y(x); edge strength = the in-layer corner over a 0.5 mm arm less its
          +-4 mm mean (the form's own curvature); a z-monotone path of the highest sum, leaning <= LEAN on the
          surface, within XLIM of the centre line (narrower towards the top)
  ids     n blind notches (1.5 wide, 0.8 deep, 2 tall) in the front of the cut rim
    ~/.venvs/cad/bin/python cad/desk/seam_coupon.py [check]
Writes to-print/pebble-C-seam-coupon-{n}.stl, pebble-C-seam-coupon-route.csv, _13_plate_seam_coupon.3mf and
images/desk-housing-v3/seam-coupon-route.png. `check` reads G-code sliced from the plate (SEAM_GCODE=plate_1.gcode).
"""
import os, sys, re, math, json, subprocess, pathlib
import numpy as np, pyvista as pv, trimesh, manifold3d as m3

HERE = pathlib.Path(__file__).parent; TP = HERE / "to-print"; IMG = HERE.parent.parent / "images/desk-housing-v3"
SRC = TP / "pebble-C-shell-relief-N1.stl"
Z0 = 88.5                              # cut: the slots' top ends close at 88.04, above it the skin is a closed ring
LAYER = 0.08; DX = 0.04; XLIM = 12.0; LEAN = 60.0; ARM = 0.5; BASE = 4.0
PLATE = "_13_plate_seam_coupon.3mf"; ROUTE = "pebble-C-seam-coupon-route.csv"
AL = {"enable_overhang_speed": "0,0", "seam_position": "aligned"}
VARIANTS = [                           # name, per-object settings (the rest is the plate's: 0.08, 4 walls, inner/outer, 60 mm/s)
    ("seam-coupon 1 edge", AL),
    ("seam-coupon 2 scarf", {**AL, "override_filament_scarf_seam_setting": "1", "seam_slope_type": "external"}),
    # held back (low expected effect; the next to try if 1 and 2 both disappoint; both checked in G-code):
    # ("seam-coupon 3 outer-first", {**AL, "wall_sequence": "outer wall/inner wall"}),
    # ("seam-coupon 4 slow 30", {**AL, "outer_wall_speed": "30"}),
]
XY = [(90, 160), (170, 160), (90, 100), (170, 100)]
log = lambda *a: print(*a, flush=True)


def back_maps(mesh, zs, XS):
    """per layer: the back contour y(x) on XS (the outermost crossing), the half width and the rearmost y"""
    Y = np.full((len(zs), len(XS)), np.nan); hw = np.zeros(len(zs)); ym = np.zeros(len(zs))
    for k, z in enumerate(zs):
        s = mesh.slice(normal="z", origin=(0, 0, z)); Q = np.asarray(s.points, float); L = s.lines.reshape(-1, 3)[:, 1:]
        a, b = Q[L[:, 0]].copy(), Q[L[:, 1]].copy(); sw = a[:, 0] > b[:, 0]; a[sw], b[sw] = b[sw].copy(), a[sw].copy()
        env = np.full(len(XS), -np.inf)
        i0 = np.ceil((a[:, 0] - XS[0]) / DX - 1e-9).astype(int); i1 = np.floor((b[:, 0] - XS[0]) / DX + 1e-9).astype(int)
        for n in np.where((i1 >= 0) & (i0 < len(XS)) & (i1 >= i0))[0]:
            lo, hi = max(i0[n], 0), min(i1[n], len(XS) - 1); x = XS[lo:hi + 1]; dx = b[n, 0] - a[n, 0]
            y = a[n, 1] + (b[n, 1] - a[n, 1]) * ((x - a[n, 0]) / dx if dx > 1e-12 else 0.0)
            env[lo:hi + 1] = np.maximum(env[lo:hi + 1], y)
        Y[k] = np.where(np.isfinite(env), env, np.nan); hw[k] = np.abs(Q[:, 0]).max(); ym[k] = Q[:, 1].max()
    return Y, hw, ym


def edges(Y):
    """edge strength, degrees: > 0 on a ridge (arris), < 0 in a valley"""
    a = round(ARM / DX); T = np.full_like(Y, np.nan)
    s1 = (Y[:, a:-a] - Y[:, :-2 * a]) / ARM; s2 = (Y[:, 2 * a:] - Y[:, a:-a]) / ARM
    T[:, a:-a] = np.degrees(np.arctan(s1) - np.arctan(s2))
    w = 2 * round(BASE / DX) + 1; ok = np.isfinite(T); c = np.cumsum(np.c_[np.zeros(len(T)), np.where(ok, T, 0)], axis=1)
    n = np.cumsum(np.c_[np.zeros(len(T)), ok], axis=1); h = w // 2; i = np.arange(T.shape[1])
    lo, hi = np.clip(i - h, 0, None), np.clip(i + h + 1, None, T.shape[1])
    return T - (c[:, hi] - c[:, lo]) / np.maximum(n[:, hi] - n[:, lo], 1)


def find_route(mesh, z0=Z0, z1=None):
    """the edge route up the back between z0 and z1 (default: the top), one point per layer centre"""
    ztop = mesh.bounds[5] if z1 is None else z1; zs = np.arange(z0 + LAYER / 2, ztop - 0.02, LAYER); XS = np.arange(-XLIM - BASE, XLIM + BASE + 1e-9, DX)
    Y, hw, ym = back_maps(mesh, zs, XS); E = edges(Y)
    lim = np.minimum(XLIM, 0.45 * hw); ok = (np.abs(XS)[None] <= lim[:, None]) & np.isfinite(E)
    sc = np.where(ok, np.clip(np.nan_to_num(E), -5, 15), -1e6)
    ds = np.hypot(LAYER, np.r_[0, np.diff(ym)]); K = np.maximum(1, np.floor(math.tan(math.radians(LEAN)) * ds / DX)).astype(int)
    n, w = sc.shape; best = sc[0].copy(); bk = np.zeros((n, w), int)
    for i in range(1, n):
        k = int(min(K[i], w - 1)); cand = np.full((2 * k + 1, w), -1e12)
        for s in range(-k, k + 1):                                    # from cell j - s, a small price on going sideways
            sh = np.roll(best, s)
            if s > 0: sh[:s] = -1e12
            if s < 0: sh[s:] = -1e12
            cand[s + k] = sh - 0.05 * abs(s)
        a = cand.argmax(0); bk[i] = a - k; best = cand.max(0) + sc[i]
    p = np.zeros(n, int); p[-1] = best.argmax()
    for i in range(n - 1, 0, -1): p[i - 1] = p[i] - bk[i, p[i]]
    R = np.c_[XS[p], Y[np.arange(n), p], zs]; e = E[np.arange(n), p]
    return dict(R=R, e=e, zs=zs, XS=XS, E=E, ok=ok, Y=Y)


def coupons():
    t = trimesh.load(SRC); body = m3.Manifold(m3.Mesh(np.asarray(t.vertices, np.float32), np.asarray(t.faces, np.uint32)))
    cap = body.trim_by_plane((0.0, 0.0, 1.0), Z0)
    pm = pv.read(SRC); s = pm.slice(normal="z", origin=(0, 0, Z0 + 1.0)); Q = np.asarray(s.points)
    out = []
    for n in range(1, len(VARIANTS) + 1):
        c = cap
        for i in range(n):
            x = (i - (n - 1) / 2) * 3.5; yf = Q[np.abs(Q[:, 0] - x) < 0.8, 1].min()
            c = c - m3.Manifold.cube((1.5, 2.8, 3.0)).translate((x - 0.75, yf - 2.0, Z0 - 1.0))
        g = c.to_mesh(); tm = trimesh.Trimesh(np.asarray(g.vert_properties)[:, :3], np.asarray(g.tri_verts), process=False)
        fn = f"pebble-C-seam-coupon-{n}.stl"; tm.export(TP / fn); out.append(fn)
        log(fn, "triangles", len(tm.faces), "watertight", tm.is_watertight, "volume", round(tm.volume / 1000, 2), "cm3",
            "bbox", np.round(tm.bounds[0], 2), np.round(tm.bounds[1], 2), "pieces", c.decompose().__len__())
        assert tm.is_watertight and len(c.decompose()) == 1
    return out


def picture(r):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 7)); E = np.where(r["ok"], r["E"], np.nan)
    ax.imshow(E, origin="lower", extent=[r["XS"][0], r["XS"][-1], r["zs"][0], r["zs"][-1]], aspect="equal", cmap="RdBu_r", vmin=-15, vmax=15)
    ax.plot(r["R"][:, 0], r["R"][:, 2], "k-", lw=1.2); ax.set_xlim(-XLIM - 1, XLIM + 1)
    ax.set_title("seam coupon (N1 dome cap, seen from behind): relief edges at the back, red = ridge (+-15 deg); black = painted seam route", fontsize=9)
    ax.set_xlabel("x across the back, mm"); ax.set_ylabel("z in the shell, mm"); plt.tight_layout(); plt.savefig(IMG / "seam-coupon-route.png", dpi=110)


def build():
    files = coupons(); r = find_route(pv.read(TP / files[0])); R, e = r["R"], r["e"]
    np.savetxt(TP / ROUTE, R, fmt="%.4f", delimiter=",")
    step = np.degrees(np.arctan2(np.abs(np.diff(R[:, 0])), np.hypot(np.diff(R[:, 1]), np.diff(R[:, 2]))))
    log(f"route: {len(R)} layers z {R[0, 2]:.2f}..{R[-1, 2]:.2f}, x {R[:, 0].min():.1f}..{R[:, 0].max():.1f}; on an edge > 5 deg {np.mean(e > 5):.2f}, > 8 {np.mean(e > 8):.2f}, "
        f"> 12 {np.mean(e > 12):.2f}, median {np.median(e):.1f} deg; lean max {step.max():.0f} deg")
    for lo, hi in ((Z0, 95), (95, 100), (100, 104), (104, 110)):
        k = (R[:, 2] >= lo) & (R[:, 2] < hi); log(f"   z {lo}-{hi}: {k.sum()} layers, on an edge > 5 deg {np.mean(e[k] > 5):.2f}, median {np.median(e[k]):.1f}")
    picture(r)
    objs = [[nm, fn, cfg, x, y, False, ROUTE] for (nm, cfg), fn, (x, y) in zip(VARIANTS, files, XY)]
    subprocess.run([sys.executable, str(HERE / "make_plate.py")], check=True, env={**os.environ, "PLATE_OUT": PLATE, "PLATE_OBJECTS": json.dumps(objs)})


def check(gcode):
    """per coupon, from sliced G-code: where every layer's outer skin starts (the seam) against the route, scarf ramps
    (z moves inside an outer wall), wall order and outer wall speed"""
    R = np.loadtxt(TP / ROUTE, delimiter=","); num = re.compile(r"([XYZEF])(-?\d*\.?\d+)")
    O = {nm: dict(starts=[], first=[], F=[]) for nm, _ in VARIANTS}
    x = y = z = f = 0.0; cur = None; feat = ""; trav = True; layer_first = None      # trav: the head has moved without extruding
    for ln in open(gcode, errors="ignore"):
        if ln[0] == ";":
            if ln.startswith("; Z_HEIGHT:"): z = float(ln.split(":")[1])
            elif ln.startswith("; start printing object, unique label id:"):        # make_plate: identify_id 100 + i
                i = int(ln.split(":")[1]) - 100; cur = VARIANTS[i][0] if 0 <= i < len(VARIANTS) else None; layer_first = None; trav = True
            elif ln.startswith("; stop printing object, unique label id:"): cur = None
            elif ln.startswith("; FEATURE:"): feat = ln.split(":")[1].strip()       # (not repeated when the next object starts in the same role)
            continue
        if ln[0] != "G" or ln[1] not in "0123": continue
        v = dict(num.findall(ln.split(";")[0])); px, py = x, y
        if "X" in v: x = float(v["X"])
        if "Y" in v: y = float(v["Y"])
        if "F" in v: f = float(v["F"])
        ext = "E" in v and float(v["E"]) > 0 and ("X" in v or "Y" in v)
        if cur and ext and layer_first is None and feat in ("Outer wall", "Inner wall"): layer_first = feat; O[cur]["first"].append(feat)
        if cur and feat == "Outer wall" and ext:
            o = O[cur]
            if trav: o["starts"].append([px, py, z, 0.0])                          # a loop starts where extrusion resumes after a travel
            if "Z" in v and o["starts"]: o["starts"][-1][3] = 1.0                  # a z move inside the loop: a scarf ramp
            o["F"].append(f)
        if ext: trav = False
        elif "X" in v or "Y" in v: trav = True
    res = {}
    for (nm, _), (cx, cy) in zip(VARIANTS, XY):
        o = O[nm]; S = np.array(o["starts"])
        if not len(S): log(nm, "not found in the G-code"); continue
        # plate -> shell frame: the rearmost seam start per layer sits on the back skin; fit the offset on the route
        zs = np.unique(S[:, 2]); B = np.array([S[S[:, 2] == q][np.argmax(S[S[:, 2] == q][:, 1])] for q in zs])
        rx = np.interp(B[:, 2] + Z0, R[:, 2], R[:, 0]); ry = np.interp(B[:, 2] + Z0, R[:, 2], R[:, 1])
        off = np.median(B[:, 0] - rx), np.median(B[:, 1] - ry)
        d = np.hypot(B[:, 0] - off[0] - rx, B[:, 1] - off[1] - ry); F = np.array(o["F"]) / 60
        first = max(set(o["first"]), key=o["first"].count)
        res[nm] = dict(layers=len(zs), med=float(np.median(d)), in03=float(np.mean(d < 0.3)), in06=float(np.mean(d < 0.6)), ramp=float(B[:, 3].mean()), first=first, v=float(np.median(F)))
        zb = B[:, 2] + Z0; bands = "; ".join(f"z {lo:g}-{hi:g}: {np.median(d[(zb >= lo) & (zb < hi)]):.2f} / {d[(zb >= lo) & (zb < hi)].max():.2f}" for lo, hi in ((Z0, 95), (95, 100), (100, 104), (104, 108)))
        log(f"{nm}: {len(zs)} layers; seam to route median {np.median(d):.2f} mm, within 0.3: {np.mean(d < 0.3):.2f}, within 0.6: {np.mean(d < 0.6):.2f} (median / max by band: {bands}); "
            f"skin loops with a scarf ramp {B[:, 3].mean():.2f} (all outer-wall loops {S[:, 3].mean():.2f}); walls start with: {first}; outer wall speed median {np.median(F):.0f} mm/s (10..90 %: {np.percentile(F, 10):.0f}..{np.percentile(F, 90):.0f})")
    return res


if __name__ == "__main__":
    if sys.argv[1:2] == ["check"]: check(os.environ["SEAM_GCODE"])
    else: build()
