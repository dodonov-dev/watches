#!/usr/bin/env python3
"""Painted seam for the pebble's relief shells: plate _15 = plate _10's two shells with the layer seam hidden.
Per shell, by what a layer's loops are (scanned every STEP):
  cavity   wherever the cavity exists: a strip up its back wall at x = XC. Where the outer skin and the cavity are one
           loop (cable notch below z 6.3, slot zone z 23.6..87.6) that is the layer's only seam on the main body
  pillar   the front pillar between the two slots is its own loop. Not painted (its inner face is two triangles 64 mm
           tall): seam = aligned puts its seam up its inner (cavity side) corner by itself, see `check`
  edges    where the outer skin is a loop of its own (foot band, dome): seam_coupon's edge route up the back
Seam = aligned + scarf joint (coupon 2 of plate _13).
The STLs are only read. The routes follow the exact surface: after regenerating a shell STL, run this again (the old
route CSVs and plates are stale), slice and `check`.
    ~/.venvs/cad/bin/python cad/desk/seam_shell.py [check]
SEAM_ONLY=N1: that shell alone in the middle of the bed, plate _16_plate_pebble_N1_seam.3mf (build and check).
SEAM_ROUND=D SEAM_ONLY=N1: round D's N1 (the board keeper's ribs in the cavity) with its fork and the lid, plate
_17_plate_pebble_D_N1_fork_lid.3mf, route pebble-D-seam-route-N1.csv (build and check). SEAM_ROUND=E: round E's N1 and
fork, plate _18_plate_pebble_E_N1_fork.3mf.
Writes to-print/pebble-C-seam-route-{W,N1}.csv (x,y,z,polyline,half width), _15_plate_pebble_W_N1_seam.3mf and
images/desk-housing-v3/seam-shell-routes.png. `check` reads G-code sliced from the plate (SEAM_GCODE=plate_1.gcode).
"""
import os, sys, re, json, subprocess
import numpy as np, pyvista as pv
import seam_coupon as sc

HERE, TP, IMG, LAYER, log = sc.HERE, sc.TP, sc.IMG, sc.LAYER, sc.log
PLATE = "_15_plate_pebble_W_N1_seam.3mf"
RND = os.environ.get("SEAM_ROUND", "C")                                                            # the shells' round (to-print names)
SHELLS = [(f"pebble-{RND}-relief-W", "W", 70, 160), (f"pebble-{RND}-relief-N1-knapped", "N1", 186, 160)]   # as on plate _10
ONLY = os.environ.get("SEAM_ONLY")
if ONLY: SHELLS = [(nm, tag, 128, 128) for nm, tag, _, _ in SHELLS if tag == ONLY]; PLATE = f"_16_plate_pebble_{ONLY}_seam.3mf"
EXTRA = []                             # further objects, after the shells: their G-code labels stay 100..
if RND in ("D", "E"):                  # N1 with the board keeper's ribs and its fork. Plate _17: round D + the lid (round C's,
    assert ONLY == "N1"                # unchanged since); plate _18: round E, no lid
    SHELLS = [(SHELLS[0][0], "N1", 90, 170)]; PLATE = {"D": "_17_plate_pebble_D_N1_fork_lid.3mf", "E": "_18_plate_pebble_E_N1_fork.3mf"}[RND]
    EXTRA = [[f"pebble-{RND}-fork (pads up: sand them to fit)", f"pebble-{RND}-fork.stl", {}, 190, 128, False]]
    if RND == "D": EXTRA.append(["pebble-C-lid (flipped)", "pebble-C-lid.stl", {}, 90, 60, False])
STL = f"pebble-{RND}-shell-relief-{{}}.stl"; ROUTE = f"pebble-{RND}-seam-route-{{}}.csv"
SUP = {"enable_support": "1", "support_type": "tree(manual)", "support_on_build_plate_only": "1", "enable_overhang_speed": "0,0",
       "tree_support_branch_angle": "10", "support_object_xy_distance": "0.7"}                     # make_plate.SUP
SEAM = {"seam_position": "aligned", "override_filament_scarf_seam_setting": "1", "seam_slope_type": "external"}
XC = 8.0 if RND == "E" else 6.0        # the cavity strip's x: clear of the cable notch (|x| < 3.1; round E: the USB slot, |x| < 5.5)
STEP = 0.2; PAD = 0.24                 # topology scan step; the edge routes overlap the neighbouring zones by PAD
R_EDGE = 0.4; R_IN = 1.2               # strip half widths: outer skin (fine mesh) / cavity (triangles ~1.5)
OUTER, CAV = 0, 100                    # polyline ids: 0.. edge routes, 100.. cavity
HALF = 0.21                            # half a wall line: a seam start sits this far under the surface


def cross(P, L, r, x0):
    """the slice's crossings of the line x = x0: y ascending, and each one's loop"""
    a, b = P[L[:, 0]], P[L[:, 1]]; k = ((a[:, 0] - x0) * (b[:, 0] - x0) <= 0) & (a[:, 0] != b[:, 0])
    y = a[k, 1] + (b[k, 1] - a[k, 1]) * (x0 - a[k, 0]) / (b[k, 0] - a[k, 0]); o = np.argsort(y); y, g = y[o], r[L[k, 0]][o]
    keep = np.r_[True, np.diff(y) > 1e-3][:len(y)]; return y[keep], g[keep]


def scan(mesh):
    """per height: the cavity back wall's y at XC (nan: no cavity) and whether the outer skin is a loop of its own"""
    out = []
    for z in np.arange(LAYER / 2, mesh.bounds[5] - 0.02, STEP):
        c = mesh.slice(normal="z", origin=(0, 0, z)).connectivity(); P = np.asarray(c.points); r = np.asarray(c.point_data["RegionId"])
        L = c.lines.reshape(-1, 3)[:, 1:]; y6, g6 = cross(P, L, r, XC)
        cav = len(y6) >= 2 and y6[-1] - y6[-2] < 6.0 and np.ptp(P[:, 1]) > 20   # a wall's thickness in front of the back skin (not the apex)
        out.append((z, y6[-2] if cav else np.nan, not cav or g6[-2] != g6[-1]))
    return np.array(out)


def runs(mask):
    e = np.flatnonzero(np.diff(np.r_[0, mask.astype(int), 0])); return list(zip(e[::2], e[1::2] - 1))


def routes(tag):
    mesh = pv.read(TP / STL.format(tag)); T = scan(mesh); z = T[:, 0]; rows = []; maps = []
    for n, (i, j) in enumerate(runs(T[:, 2] > 0)):
        z0 = max(0.0, np.floor((z[i] - PAD) / LAYER) * LAYER); z1 = min(mesh.bounds[5], z[j] + PAD + LAYER)
        r = sc.find_route(mesh, z0, z1); R, e = r["R"], r["e"]; rows.append(np.c_[R, np.full(len(R), OUTER + n), np.full(len(R), R_EDGE)]); maps.append(r)
        log(f"{tag} edge route {n}: z {R[0, 2]:.2f}..{R[-1, 2]:.2f} ({len(R)} layers), x {R[:, 0].min():.1f}..{R[:, 0].max():.1f}; on an edge > 5 deg {np.mean(e > 5):.2f}, "
            f"> 8 {np.mean(e > 8):.2f}, median {np.median(e):.1f} deg")
    for n, (i, j) in enumerate(runs(np.isfinite(T[:, 1]))):
        k = slice(i, j + 1); m = j + 1 - i; rows.append(np.c_[np.full(m, XC), T[k, 1], z[k], np.full(m, CAV + n), np.full(m, R_IN)])
        log(f"{tag} cavity strip {n}: z {z[i]:.2f}..{z[j]:.2f}, y {T[k, 1].min():.2f}..{T[k, 1].max():.2f}, largest step {np.abs(np.diff(T[k, 1])).max() if m > 1 else 0:.2f}")
    np.savetxt(TP / ROUTE.format(tag), np.vstack(rows), fmt="%.4f", delimiter=",")
    return maps


def picture(M):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    n = max(len(m) for m in M.values()); fig, ax = plt.subplots(len(M), n, figsize=(8 * n, 6.5 * len(M)), squeeze=False)
    for row, (tag, maps) in zip(ax, M.items()):
        for a, r in zip(row, maps):
            E = np.where(r["ok"], r["E"], np.nan)
            a.imshow(E, origin="lower", extent=[r["XS"][0], r["XS"][-1], r["zs"][0], r["zs"][-1]], aspect="equal", cmap="RdBu_r", vmin=-15, vmax=15)
            a.plot(r["R"][:, 0], r["R"][:, 2], "k-", lw=1.2); a.set_xlim(-sc.XLIM - 1, sc.XLIM + 1)
            a.set_title(f"{tag}, z {r['zs'][0]:.1f}..{r['zs'][-1]:.1f} seen from behind: red = ridge (+-15 deg), black = painted seam", fontsize=9)
            a.set_xlabel("x across the back, mm"); a.set_ylabel("z, mm")
    plt.tight_layout(); plt.savefig(IMG / "seam-shell-routes.png", dpi=100)


def build():
    M = {tag: routes(tag) for _, tag, _, _ in SHELLS}
    if not ONLY: picture(M)
    objs = [[nm, STL.format(tag), {**SUP, **SEAM}, x, y, True, ROUTE.format(tag)] for nm, tag, x, y in SHELLS] + EXTRA
    subprocess.run([sys.executable, str(HERE / "make_plate.py")], check=True, env={**os.environ, "PLATE_OUT": PLATE, "PLATE_OBJECTS": json.dumps(objs)})


def check(gcode):
    """per shell, from sliced G-code: every loop with outer wall in it, its start (the seam) against the painted strips.
    plate -> STL frame from the outer walls' own bounding box (not from the seams). Edge routes: distance within the
    layer. Starts on no strip are sorted by depth under the layer's convex outline: < 1 mm skin, < 2.5 recessed (slot
    lips, pockets: can be seen), deeper = cavity side"""
    from scipy.spatial import cKDTree, ConvexHull
    num = re.compile(r"([XYZEF])(-?\d*\.?\d+)"); S = [[] for _ in SHELLS]; B = [[1e9, 1e9, -1e9, -1e9] for _ in SHELLS]
    one = len(SHELLS) + len(EXTRA) == 1; cur = 0 if one else None      # a single object is not labelled in the G-code
    x = y = z = 0.0; feat = ""; trav = True; path = None
    for ln in open(gcode, errors="ignore"):
        if ln[0] == ";":
            if ln.startswith("; Z_HEIGHT:"): z = float(ln.split(":")[1])
            elif ln.startswith("; start printing object, unique label id:"):
                i = int(ln.split(":")[1]) - 100; cur = i if 0 <= i < len(SHELLS) else None; trav = True; path = None
            elif ln.startswith("; stop printing object, unique label id:"): cur = 0 if one else None
            elif ln.startswith("; FEATURE:"): feat = ln.split(":")[1].strip()
            continue
        if ln[0] != "G" or ln[1] not in "0123": continue
        v = dict(num.findall(ln.split(";")[0])); px, py = x, y
        if "X" in v: x = float(v["X"])
        if "Y" in v: y = float(v["Y"])
        ext = "E" in v and float(v["E"]) > 0 and ("X" in v or "Y" in v)
        if cur is not None and ext:
            if trav or path is None: path = [px, py, z, 0.0, 0.0, 0.0]; S[cur].append(path)   # a path starts where extrusion resumes after a travel
            if feat == "Outer wall": path[4] = 1.0                                 # (it may start as an overhang wall)
            elif feat == "Overhang wall" and not path[4]: path[5] = 1.0
            if "Z" in v: path[3] = 1.0                                             # a z move inside the path: a scarf ramp
            if feat in ("Outer wall", "Overhang wall"):
                b = B[cur]; b[0] = min(b[0], x, px); b[1] = min(b[1], y, py); b[2] = max(b[2], x, px); b[3] = max(b[3], y, py)
        if ext: trav = False
        elif "X" in v or "Y" in v: trav = True
    for (nm, tag, ox, oy), st, gb in zip(SHELLS, S, B):
        st = np.array([q for q in st if q[4]])
        if not len(st): log(nm, "not found in the G-code"); continue
        mesh = pv.read(TP / STL.format(tag)); b = mesh.bounds; A = np.loadtxt(TP / ROUTE.format(tag), delimiter=",")
        sh = (gb[0] + gb[2]) / 2 - (b[0] + b[1]) / 2, (gb[1] + gb[3]) / 2 - (b[2] + b[3]) / 2    # the walls' bbox centre = the STL's
        Q = np.c_[st[:, 0] - sh[0], st[:, 1] - sh[1], st[:, 2] - LAYER / 2]                       # STL frame, layer centre
        log(f"{nm}: {len(np.unique(st[:, 2]))} layers, {len(Q)} outer-wall loops ({int(st[:, 5].sum())} start as an overhang wall); walls' bbox "
            f"{gb[2] - gb[0]:.2f} x {gb[3] - gb[1]:.2f} (STL less a line width {b[1] - b[0] - 2 * HALF:.2f} x {b[3] - b[2] - 2 * HALF:.2f}), "
            f"placed {sh[0] - ox + (b[0] + b[1]) / 2:+.2f}, {sh[1] - oy + (b[2] + b[3]) / 2:+.2f} off make_plate's position")
        ids = np.unique(A[:, 3]); D = np.full((len(Q), len(ids)), np.inf); DL = D.copy()          # 3-d distance (the paint) / within the layer
        for k, pid in enumerate(ids):
            R = A[A[:, 3] == pid]; L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(R[:, :3], axis=0), axis=1))]
            t = np.arange(0, L[-1], 0.02); D[:, k] = cKDTree(np.c_[[np.interp(t, L, R[:, c]) for c in range(3)]].T).query(Q)[0]
            inz = (Q[:, 2] > R[0, 2] - LAYER) & (Q[:, 2] < R[-1, 2] + LAYER)
            DL[inz, k] = np.hypot(Q[inz, 0] - np.interp(Q[inz, 2], R[:, 2], R[:, 0]), Q[inz, 1] - np.interp(Q[inz, 2], R[:, 2], R[:, 1]))
        flat = lambda d: np.sqrt(np.maximum(d ** 2 - HALF ** 2, 0))                               # a start sits HALF under the surface
        near = D.argmin(1); d = flat(D.min(1)); on = d < np.where(ids[near] < CAV, R_EDGE + 0.2, R_IN + 0.5)
        for k, pid in enumerate(ids):
            m = on & (near == k); R = A[A[:, 3] == pid]; kind = "edge route" if pid < CAV else "cavity strip"
            if not m.any(): log(f"   {kind} z {R[0, 2]:.2f}..{R[-1, 2]:.2f}: no seam on it"); continue
            dl = flat(DL[m, k]) if pid < CAV else d[m]
            log(f"   {kind} z {R[0, 2]:.2f}..{R[-1, 2]:.2f}: seam on it in {len(np.unique(Q[m, 2]))} layers, z {Q[m, 2].min():.2f}..{Q[m, 2].max():.2f}; "
                f"distance {'within the layer ' if pid < CAV else ''}median {np.median(dl):.2f}, 90 % {np.percentile(dl, 90):.2f}, max {dl.max():.2f} mm; with a scarf ramp {st[m, 3].mean():.2f}")
        zl = np.unique(Q[:, 2]); n_on = np.array([np.sum(on & (Q[:, 2] == q)) for q in zl])
        log(f"   layers with no seam on any strip: {int(np.sum(n_on == 0))} of {len(zl)}" + (f" (z {zl[n_on == 0].min():.2f}..{zl[n_on == 0].max():.2f})" if np.any(n_on == 0) else ""))
        off = np.flatnonzero(~on); depth = np.zeros(len(off)); hulls = {}
        for n, i in enumerate(off):
            zc = round(Q[i, 2], 3)
            if zc not in hulls:
                P = np.asarray(mesh.slice(normal="z", origin=(0, 0, zc)).points)[:, :2]; hulls[zc] = ConvexHull(P).equations
            eq = hulls[zc]; depth[n] = -(eq[:, :2] @ Q[i, :2] + eq[:, 2]).max()
        log(f"   on no strip: {len(off)} starts")
        for cls, lo_d, hi_d in (("on the skin (< 1 mm under the outline)", -9, 1.0), ("recessed (1..2.5 mm)", 1.0, 2.5), ("cavity side (> 2.5 mm)", 2.5, 99)):
            for lo, hi in ((0, 6.3), (6.3, 23.6), (23.6, 87.6), (87.6, 120)):
                k = (depth >= lo_d) & (depth < hi_d) & (Q[off, 2] >= lo) & (Q[off, 2] < hi); m = off[k]
                if len(m): log(f"      {cls}, z {lo}..{hi}: {len(m)} in {len(np.unique(Q[m, 2]))} layers (z {Q[m, 2].min():.2f}..{Q[m, 2].max():.2f}); 10..90 %: x {np.percentile(Q[m, 0], 10):.2f}..{np.percentile(Q[m, 0], 90):.2f}, "
                               f"y {np.percentile(Q[m, 1], 10):.2f}..{np.percentile(Q[m, 1], 90):.2f}, depth {np.percentile(depth[k], 10):.1f}..{np.percentile(depth[k], 90):.1f}; with a scarf ramp {st[m, 3].mean():.2f}")
        dep = np.full(len(Q), np.nan); dep[off] = depth
        np.save(os.path.splitext(gcode)[0] + f"-starts-{tag}.npy", np.c_[Q, st[:, 3], d, near, on, dep])


if __name__ == "__main__":
    if sys.argv[1:2] == ["check"]: check(os.environ["SEAM_GCODE"])
    else: build()
