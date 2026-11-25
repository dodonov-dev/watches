"""Natural stone relief on the round C pebble shell (to-print/pebble-C-shell.stl): a smooth displacement field on
relief_c.py's refined base (same masks and exclusions), built from few readable features, not a tessellation:
  N1  knapped: overlapping conchoidal flake scars (teardrop dishes, deep at the struck end, feathered at the far end,
      meeting at soft arrises), carved into a +0.30 skin whose remnants stay as cortex patches; faint ripples in a few
  N2  river: low-frequency anisotropic undulation plus sparse clustered dents, pits and nicks of varied elongation
  N3  worn: few large soft scars with rounded ridges (as if ground / sanded down), calm skin between, a few pits
Features are sized from the local curvature (smaller on tight curves), run roughly along the form, and are made
shallower or skipped where the shell already overhangs (printed standing), deep end down there.
    ~/.venvs/cad/bin/python relief_natural.py
Writes to-print/pebble-C-shell-relief-{N1,N2,N3}.stl and images/desk-housing-v3/relief-C-natural.png.
"""
import sys, math, json, pathlib
import numpy as np
import pyvista as pv
from scipy.spatial import cKDTree
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import relief_c as rc
from relief_c import ROOT, TP, ss, body, rect_dist, faces, mesh, log, OPEN_X, OPEN_S, Z_CLEAN

HERE = pathlib.Path(__file__).parent
LIM = 45.0


def load_base():
    """relief_c.main's set-up, with the (slow) hull depth cached: points, faces, normals, masks"""
    src = pv.read(rc.SRC).clean(tolerance=1e-7, absolute=True)
    Rg = rc.Regions(np.asarray(src.points, float))                       # (the same hull as relief_c: rng seed 11)
    z = np.load(HERE / "out-coupon/relief-c-base.npz"); P, F = z["P"], z["F"]
    dc = HERE / "out-coupon/relief-c-natural-depth.npy"
    if dc.exists() and dc.stat().st_mtime > rc.SRC.stat().st_mtime: depth = np.load(dc)
    else: depth = Rg.depth(P); np.save(dc, depth)
    Rg.depth = lambda Q: depth
    R = Rg(P)
    m = mesh(P, F).compute_normals(cell_normals=False, split_vertices=False, consistent_normals=True, auto_orient_normals=True)
    N = np.asarray(m.point_data["Normals"], float); F = faces(m).copy(); R["F"] = F
    oh = np.degrees(np.arcsin(np.clip(-N[:, 2], 0, 1)))
    nr = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]]); ar = np.linalg.norm(nr, axis=1)
    sup_top = lambda xc, tc, sc: (np.abs(sc - OPEN_S[1]) < 0.3) & (np.abs(xc) > 2.0) & (np.abs(xc) < 15.3) & (tc > -0.2) & (tc < 3.5)
    zc = P[F].mean(1)[:, 2]
    feat = ((ar > 1e-8) & (-nr[:, 2] > math.sin(math.radians(45)) * ar) & (zc > 0.01) & (zc < 50) & R["outer"][F].all(1)
            & ~sup_top(*body(P[F].mean(1))))
    dfeat = cKDTree(P[F[feat]].mean(1)).query(P)[0]
    outer = R["outer"] * ss((dfeat - 1.0) / 4.0)
    wW = outer * ss((R["d_open"] - 0.3) / 0.5) * ss((R["z"] - Z_CLEAN) / 0.5)      # relief_c's mask, as is
    logo = ss((2.5 - R["d_logo"]) / 1.5)
    return dict(P=P, F=F, N=N, R=R, oh=oh, dfeat=dfeat, wW=wW, logo=logo, sup_top=sup_top, src=src)


if __name__ == "__main__" and "prep" in sys.argv[1:2]:
    B = load_base(); P, R, oh, wW = B["P"], B["R"], B["oh"], B["wW"]
    on = wW > 0.9; x, t, s = R["x"], R["t"], R["s"]
    log("vertices", len(P), "relief", on.sum(), "bbox", P.min(0).round(1), P.max(0).round(1))
    for nm, mk in (("all", on), ("front t<8", on & (t < 8)), ("back t>45", on & (t > 45)), ("sides", on & (t >= 8) & (t <= 45)), ("dome z>90", on & (P[:, 2] > 90)), ("low z<25", on & (P[:, 2] < 25))):
        o = oh[mk]; log(f"{nm}: n {mk.sum()}, overhang >10 {np.mean(o > 10):.2f} >20 {np.mean(o > 20):.2f} >30 {np.mean(o > 30):.2f} >38 {np.mean(o > 38):.2f} max {o.max():.1f}; t {t[mk].min():.1f}..{t[mk].max():.1f}")
    for zz in range(5, 110, 10):
        mk = on & (np.abs(P[:, 2] - zz) < 1.5)
        if mk.sum(): log(f"z {zz}: x {x[mk].min():.1f}..{x[mk].max():.1f} y {P[mk, 1].min():.1f}..{P[mk, 1].max():.1f}; overhang back(y max) {oh[mk][np.argmax(P[mk, 1])]:.1f} side {oh[mk][np.argmax(x[mk])]:.1f} front {oh[mk][np.argmin(P[mk, 1])]:.1f} max {oh[mk].max():.1f}")
    sys.exit()


def waves(P, g, n, lam, stretch=(1.0, 1.0, 1.0)):
    """smooth pseudo-noise: a sum of n plane waves, wavelengths lam=(lo, hi), ~unit variance"""
    k = g.normal(size=(n, 3)); k /= np.linalg.norm(k, axis=1)[:, None]
    k = k * (2 * math.pi / g.uniform(*lam, n))[:, None] / np.array(stretch)
    return np.sin(P @ k.T + g.uniform(0, 2 * math.pi, n)).sum(1) * math.sqrt(2.0 / n)


def curvature(P, N, tree, pts, i, rho=5.0):
    """principal curvatures (convex > 0) and directions of the smooth shell at vertex i: a quadric over a rho ball"""
    n = N[i]; t1 = np.cross(n, [0.0, 0.0, 1.0] if abs(n[2]) < 0.9 else [1.0, 0.0, 0.0]); t1 /= np.linalg.norm(t1); t2 = np.cross(n, t1)
    Q = pts[tree.query_ball_point(P[i], rho)] - P[i]; u, v, w = Q @ t1, Q @ t2, Q @ n
    c = np.linalg.lstsq(np.c_[np.ones(len(u)), u, v, u * u / 2, u * v, v * v / 2], w, rcond=None)[0]
    ev, evec = np.linalg.eigh(np.array([[c[3], c[4]], [c[4], c[5]]]))
    k = -ev; D = evec[0][:, None] * t1[None] + evec[1][:, None] * t2[None]         # rows: 3D directions
    o = np.argsort(k); return k[o], D[o]                                           # (k_min, k_max), their directions


def shape(X, f, wob):
    """a feature's unit profile g at points X (g -1 at the deepest point, 0 on its outline, > 0 outside)"""
    q = X - f["c"]; u = (q @ f["e1"]) / f["a"]; v = q @ f["e2"]; w = q @ f["n"]
    v = v - f["bend"] * u * u * f["a"]
    U = (u + f["m"]) / np.clip(1 + f["m"] * u, 0.25, None)                         # deepest at u = -m: steep struck end
    V = v / (f["b"] * np.clip(1 + f["tau"] * u, 0.35, None))                       # fans out to the far end
    r2 = (U * U + V * V) * (1 + f["wob"] * wob) ** 2 + (w / (0.6 * f["a"] + 1.0)) ** 2
    if f["prof"] == "soft":
        return -np.clip(1 - r2, 0, None) ** 2
    g = r2 - 1
    if f["rip"] > 0:
        r = np.linalg.norm(q + 0.9 * f["a"] * f["e1"], axis=1)
        g = g + f["rip"] * np.sin(2 * math.pi * r / f["lam"] + f["ph"]) * ss((1 - np.sqrt(r2)) / 0.35) * ss((u + 0.5) / 0.7)
    return g


VARIANTS = {
    # lift: skin level the features are carved from; k: softmin radius (height, mm) = how round the arrises are
    # classes: n candidates are tried in order of size; sp: centre spacing x (ri + rj) within the class
    "N1": dict(title="N1 knapped: overlapping flake scars", seed=3, lift=0.30, k=0.025, und=0.0, classes=[
        dict(name="scar", prof="bowl", cand=5000, sp=0.70, D=(0.42, 0.70), b=(2.2, 8.0), amax=18.0, el=(1.2, 3.4), mk=(1.1, 1.8),
             sizes=((1.0, 0.60), (0.7, 0.28), (0.45, 0.12)), m=(0.10, 0.42), tau=(0.0, 0.30), scatter=28, rip=(0.25, 0.07), dmin=0.18)]),
    "N3": dict(title="N3 worn: large soft scars, calm skin, a few pits", seed=5, lift=0.25, k=0.09, und=0.0, classes=[
        dict(name="scar", prof="bowl", cand=5000, sp=0.92, D=(0.36, 0.62), b=(2.5, 8.5), amax=18.0, el=(1.1, 2.8), mk=(1.2, 2.0),
             sizes=((1.0, 0.55), (0.7, 0.30), (0.45, 0.15)), m=(0.05, 0.35), tau=(0.0, 0.25), scatter=30, rip=(0.0, 0.0), dmin=0.18),
        dict(name="pit", prof="soft", cand=60, sp=3.0, D=(0.22, 0.36), b=(0.9, 1.9), amax=5.0, el=(1.0, 2.6), mk=(0.0, 0.0),
             sizes=((1.0, 1.0),), m=(0.0, 0.2), tau=(0.0, 0.0), scatter=60, rip=(0.0, 0.0), dmin=0.15, flat_b=True)]),
    "N2": dict(title="N2 river: soft undulation, clustered dents, pits, nicks", seed=8, lift=0.12, k=0.02, und=0.11, classes=[
        dict(name="dent", prof="soft", cand=120, sp=1.5, D=(0.24, 0.40), b=(2.5, 6.0), amax=13.0, el=(1.0, 2.4), mk=(1.0, 1.8),
             sizes=((1.0, 0.6), (0.6, 0.4)), m=(0.0, 0.3), tau=(0.0, 0.2), scatter=40, rip=(0.0, 0.0), dmin=0.15, cluster=0.2),
        dict(name="nick", prof="soft", cand=14, sp=2.5, D=(0.20, 0.34), b=(0.7, 1.3), amax=9.0, el=(4.0, 8.0), mk=(0.0, 0.0),
             sizes=((1.0, 1.0),), m=(0.0, 0.3), tau=(-0.2, 0.2), scatter=50, rip=(0.0, 0.0), dmin=0.14, flat_b=True, bend=0.25, cluster=0.0),
        dict(name="pit", prof="soft", cand=400, sp=1.6, D=(0.20, 0.40), b=(0.7, 2.2), amax=5.0, el=(1.0, 2.8), mk=(0.0, 0.0),
             sizes=((1.0, 1.0),), m=(0.0, 0.25), tau=(0.0, 0.0), scatter=70, rip=(0.0, 0.0), dmin=0.14, flat_b=True, cluster=0.45)]),
}


def build(nm, B):
    V = VARIANTS[nm]; g = np.random.default_rng(V["seed"])
    P, F, N, R, oh, wW = B["P"], B["F"], B["N"], B["R"], B["oh"], B["wW"]
    x, t, s = R["x"], R["t"], R["s"]
    # distance to the exclusions: the openings with the bridge between them, the rim band, the notch / ledge
    d_span = np.where(t < 5.0, rect_dist(np.abs(x), s, (0.0, OPEN_X[1]), OPEN_S), np.inf)
    db = np.minimum(np.minimum(d_span - 0.3, R["z"] - Z_CLEAN), B["dfeat"] - 1.0)
    wob = waves(P, g, 10, (5.0, 13.0)); clus = waves(P, g, 5, (30.0, 70.0)); wc = np.clip(wob, -1, 1)
    calm = ss((8.0 - R["d_logo"]) / 8.0)                                           # the logo pocket keeps its skin: a wide
    E = V["lift"] * ss(db / 6.0) * ss((40.0 - oh) / 10.0) * (1 - calm)             # shallow dish in the lifted skin round it
    # features fade in over 2 mm, from a wavy line 0.3..1.5 off the exclusions (0.6..1.8 off the pocket)
    wf = ss((db - 0.9 - 0.6 * wc) / 2.0) * ss((R["d_logo"] - 1.2 + 0.6 * wc) / 2.0)
    zi = np.where((wW > 0) & (db > 0))[0]; tz = cKDTree(P[zi])
    sub = zi[g.choice(len(zi), 70000, replace=False)]; tsub = cKDTree(P[sub]); psub = P[sub]
    T = -np.array([0.0, 0.0, 1.0]) + N * N[:, 2:3]; T /= np.maximum(np.linalg.norm(T, axis=1), 1e-9)[:, None]   # down the wall
    lim = 42.5 - (3.0 if V["und"] else 0.0)
    S = np.ones(len(P)); cmin = np.zeros(len(P)); feats = []
    for C in V["classes"]:
        ok = zi[wf[zi] > 0.5]
        if C.get("cluster"): ok = ok[clus[ok] + g.normal(0, 0.5, len(ok)) > C["cluster"]]
        cand = g.choice(ok, C["cand"], replace=False)
        sz = np.array([q[0] for q in C["sizes"]])[g.choice(len(C["sizes"]), len(cand), p=[q[1] for q in C["sizes"]])]
        cand = cand[np.argsort(-sz * g.uniform(0.85, 1.15, len(cand)), kind="stable")]; sz = -np.sort(-sz)
        acc = []; skipped = 0
        for i, gs in zip(cand, sz):
            kk, dd = curvature(P, N, tsub, psub, i); n = N[i]
            if oh[i] > 12: e1 = -T[i]; th = g.normal(0, math.radians(12)); m = g.uniform(max(C["m"][0], 0.25), max(C["m"][1], 0.45))
            else: e1 = dd[0] * g.choice([-1, 1]); th = g.normal(0, math.radians(C["scatter"])); m = g.uniform(*C["m"])
            e1 = e1 * math.cos(th) + np.cross(n, e1) * math.sin(th); e1 /= np.linalg.norm(e1); e2 = np.cross(n, e1)
            kap = lambda e: max(kk[0] * (e @ dd[0]) ** 2 + kk[1] * (e @ dd[1]) ** 2, 0.0)
            D = g.uniform(*C["D"]) * math.sqrt(gs)
            if C.get("flat_b"): b = g.uniform(*C["b"])
            else: b = float(np.clip(math.sqrt(2 * D / (g.uniform(*C["mk"]) * kap(e2) + 1 / 250)), *C["b"])) * gs
            a = max(b, min(b * g.uniform(*C["el"]), C["amax"] * gs, math.sqrt(2 * D / (1.2 * kap(e1) + 1 / 400))))
            r = math.sqrt(a * b)
            if any(np.linalg.norm(P[i] - q["c"]) < C["sp"] * (r + q["r"]) for q in acc): continue
            rip = g.uniform(0.6, 1.0) * C["rip"][1] if (a > 6.5 and g.random() < C["rip"][0]) else 0.0
            f = dict(c=P[i], n=n, e1=e1, e2=e2, a=a, b=b, D=D, m=m, tau=g.uniform(*C["tau"]), wob=0.13, r=r, prof=C["prof"], cls=C["name"],
                     rip=rip, lam=g.uniform(1.9, 2.8), ph=g.uniform(0, 6.28), bend=g.uniform(-1, 1) * C.get("bend", 0.0))
            idx = zi[tz.query_ball_point(P[i], 1.3 * a * (1.0 if C["prof"] == "soft" else math.sqrt(1 + 6 * V["k"] / D)))]
            gv = shape(P[idx], f, wob[idx]); act = gv < 0.05
            if not act.any(): continue
            # printed standing: the feature may add atan(-dh/ds) down the wall to the shell's overhang
            inc = -(shape(P[idx] + 0.15 * T[idx], f, wob[idx]) - gv) / 0.15 * D * wf[idx]
            al = np.tan(np.radians(np.clip(lim - oh[idx], 0.0, 80.0)))
            fac = min(1.0, float((al[act] / np.maximum(inc[act], 1e-9)).min()))
            if fac * D < C["dmin"]: skipped += 1; continue
            f["D"] = D = fac * D; f["fac"] = fac; f["idx"], f["h"] = idx, D * gv
            acc.append(f)
        for f in acc:
            if f["prof"] == "soft": cmin[f["idx"]] = np.minimum(cmin[f["idx"]], f["h"])
            else: S[f["idx"]] += np.exp(-f["h"] / V["k"])
        feats += acc
        A = np.array([[f["a"], f["b"], f["D"], f["fac"]] for f in acc])
        log(f"{nm} {C['name']}: {len(acc)} placed ({skipped} skipped on overhang, {(A[:, 3] < 0.999).sum()} made shallower"
            f"{', ' + str(sum(f['rip'] > 0 for f in acc)) + ' rippled' if C['rip'][0] else ''}); length {2 * A[:, 0].min():.1f}-{2 * A[:, 0].max():.1f} "
            f"(median {2 * np.median(A[:, 0]):.1f}), width {2 * A[:, 1].min():.1f}-{2 * A[:, 1].max():.1f} (median {2 * np.median(A[:, 1]):.1f}), "
            f"elongation {np.min(A[:, 0] / A[:, 1]):.1f}-{np.max(A[:, 0] / A[:, 1]):.1f}, depth below the skin {A[:, 2].min():.2f}-{A[:, 2].max():.2f} (median {np.median(A[:, 2]):.2f})")
    c = -V["k"] * np.log(S) + cmin
    if V["und"]:
        E = E + V["und"] * 0.7 * waves(P, g, 7, (16.0, 30.0), stretch=(1.0, 1.0, 1.6)) * ss(db / 6.0) * ss((38.0 - oh) / 10.0) * (1 - calm)
    d0 = (E + c * wf) * wW
    d0 = d0 - np.minimum(d0, 0) * B["logo"]                                        # relief_c's rule: never below the skin there
    d0 = np.clip(d0, -0.40, 0.50)
    # safety net: where a triangle still overhangs past the limit, the relief is locally faded out
    sup_top = B["sup_top"]; att = np.ones(len(P)); xc, tc, sc = body(P[F].mean(1)); nsup = ~sup_top(xc, tc, sc)
    for it in range(40):
        d = d0 * att; Q = P + N * d[:, None]
        nr = np.cross(Q[F[:, 1]] - Q[F[:, 0]], Q[F[:, 2]] - Q[F[:, 0]]); ar = np.linalg.norm(nr, axis=1)
        o = np.degrees(np.arcsin(np.clip(-nr[:, 2] / np.maximum(ar, 1e-12), 0, 1)))
        bad = (ar > 0.02) & nsup & (np.abs(d[F]) > 1e-9).any(1) & (o > LIM - 0.15)
        if not bad.any(): break
        dist = cKDTree(Q[F[bad]].mean(1)).query(P, distance_upper_bound=3.0)[0]
        att *= 1 - 0.5 * ss(1 - np.clip(dist, 0, 3.0) / 3.0)
    log(f"{nm}: safety net {it} passes, {(att < 0.999).sum()} vertices faded ({(att < 0.5).sum()} by more than half)")
    on = wW > 0.95
    log(f"{nm}: {len(feats)} features; displacement on the relief region: min {d[on].min():+.3f}, 5% {np.percentile(d[on], 5):+.3f}, median "
        f"{np.median(d[on]):+.3f}, 95% {np.percentile(d[on], 95):+.3f}, max {d[on].max():+.3f}; untouched skin (within 0.03 of the lift) "
        f"{np.mean(c[on & (wf > 0.95)] > -0.03):.0%}; logo pocket (+1) min {d[R['d_logo'] <= 1.0].min():+.4f} max {d[R['d_logo'] <= 1.0].max():+.4f}; "
        f"bridge max |d| {np.abs(d[(t < 5) & (np.abs(x) < OPEN_X[0]) & (s > OPEN_S[0]) & (s < OPEN_S[1])]).max():.4f}")
    mm = mesh(Q, F); p = TP / f"pebble-C-shell-relief-{nm}.stl"; mm.save(p, binary=True)
    rc.check(mm, p.name, d, sup_top)
    return mm


def render(out, names):
    foc = json.loads((ROOT / "cad/desk/out-smooth/pebble/focus.json").read_text())
    st = np.array(foc["slot_top"]) * np.array([-1, 1, 1])
    c0 = np.array(out["W"].center); L = out["W"].length; el = math.radians(33)
    nc = len(names)
    pl = pv.Plotter(off_screen=True, window_size=(nc * 700, 860 + 860 + 600), shape=(3, nc), row_weights=[860, 860, 600], lighting="none")
    for j, (k, title) in enumerate(names):
        for i in range(3):
            pl.subplot(i, j); pl.set_background("#d8d5cf", top="#f3f1ed")
            foc_p = st if i == 2 else c0
            key = (1.0, 0.45, 0.5) if i == 1 else (-1.0, -0.25, 0.55)              # raking key light, weak fills
            for pos, it in ((key, 0.9), ((0.7, -0.9, 0.25) if i != 1 else (-0.7, 0.9, 0.25), 0.16), ((0.2, 1.0, 0.6) if i != 1 else (-0.2, -1.0, 0.6), 0.12)):
                pl.add_light(pv.Light(position=tuple(foc_p + np.array(pos) * 500), focal_point=tuple(foc_p), intensity=it), only_active=True)
            pl.add_mesh(out[k], color="#ece6d8", smooth_shading=(k != "W"), split_sharp_edges=(k != "W"), feature_angle=32, specular=0.06, specular_power=10, ambient=0.13, diffuse=0.92)
            if i < 2:
                az = math.radians(38 if i == 0 else 180 + 35)
                dv = np.array([-math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])
                pl.add_mesh(pv.Plane(center=(c0[0], c0[1], -0.05), direction=(0, 0, 1), i_size=600, j_size=600), color="#cfcac2", ambient=0.5, diffuse=0.6)
                pl.camera_position = [tuple(c0 + dv * L * 4.0), tuple(c0), (0, 0, 1)]; pl.camera.view_angle = 15
                pl.add_text(f"{title}\n{'front-left' if i == 0 else 'back-right'}, 33 deg above level", font_size=9, color="black")
            else:
                dv = np.array([-0.45, -1.0, 0.75]); dv /= np.linalg.norm(dv)
                pl.camera_position = [tuple(st + dv * 75), tuple(st), (0, 0, 1)]; pl.camera.view_angle = 22
                pl.add_text(f"{k}: left slot, top end", font_size=9, color="black")
            pl.reset_camera_clipping_range()
    pl.enable_anti_aliasing("ssaa"); p = ROOT / "images/desk-housing-v3/relief-C-natural.png"; pl.screenshot(str(p)); pl.close(); log(p)


if __name__ == "__main__":
    todo = [a for a in sys.argv[1:] if a in VARIANTS] or ([] if sys.argv[1:] else list(VARIANTS))
    if todo:
        B = load_base(); log("base", len(B["P"]), "vertices")
        for nm in todo: build(nm, B)
    if "render" in sys.argv[1:] or not sys.argv[1:]:
        names = [(k, VARIANTS[k]["title"]) for k in VARIANTS if (TP / f"pebble-C-shell-relief-{k}.stl").exists()] + [("W", "W: adaptive chord tessellation (reference)")]
        render({k: pv.read(TP / f"pebble-C-shell-relief-{k}.stl") for k, _ in names}, names)
