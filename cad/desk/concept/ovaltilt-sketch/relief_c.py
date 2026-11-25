"""Surface relief on the round C pebble shell (to-print/pebble-C-shell.stl), a mesh pass on the finished smooth shell:
  F5  W's construction at ~5 mm facets, vertices raised at random 0.05..0.45 (>= 0.8 x the local chord sag)
  F9  the same at ~8-9 mm, raised 0.10..0.50 (the max-of-planes F of relief.facets scalloped on the flanks: dropped)
  W   WIP-like: a curvature-adaptive chord tessellation of the outer surface (vertices on the surface or lifted a
      little, flat triangles between them), its edges along the slot openings and the rim; chords inside <= 0.1
Relief on the outer surface only, from z 5 up, right up to the slot openings; untouched: the slots (footprint of the
openings on the face), the cavity, the rim band, the logo patch (never below the smooth surface).
The outer region is refined to ~0.5 mm (conforming midpoint subdivision + Delaunay flips) so the facets stay crisp.
    ~/.venvs/cad/bin/python relief_c.py
Writes to-print/pebble-C-shell-relief-{F5,F9}.stl (W as built earlier, read back) and images/desk-housing-v3/relief-C-versions.png.
"""
import sys, math, json, pathlib, time
import numpy as np
import pyvista as pv
from scipy.spatial import ConvexHull, cKDTree
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from relief import ROOT, TP, C15, S15, ss

SRC = TP / "pebble-C-shell.stl"
OPEN_X, OPEN_S = (2.25, 15.02), (24.70, 91.55)          # openings on the face, |x| and s (body frame)
LOGO_C, LOGO_HW = (0.0, 12.31), (8.0, 5.415)            # logo pocket centre (x, s), half sizes
Z_CLEAN = 5.0
H_REF = 0.5                                             # refined edge length on the relief region
W_DELTA, W_LIFT, W_IN = 0.16, 0.06, 0.10                # W: chord sag budget, vertex lift, max inside
rng = np.random.default_rng(11)
T0 = time.time()
def log(*a): print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def body(P):
    return P[:, 0], P[:, 1] * C15 - P[:, 2] * S15, P[:, 1] * S15 + P[:, 2] * C15     # x, t, s


def rect_dist(ax, s, xr, sr):
    return np.hypot(np.clip(np.maximum(xr[0] - ax, ax - xr[1]), 0, None), np.clip(np.maximum(sr[0] - s, s - sr[1]), 0, None))


class Regions:
    def __init__(self, P0):
        h = ConvexHull(P0[rng.choice(len(P0), min(30000, len(P0)), replace=False)]); self.E = h.equations

    def depth(self, P):
        return np.concatenate([-(c @ self.E[:, :3].T + self.E[:, 3]).max(1) for c in np.array_split(P, max(1, len(P) // 20000))])

    def __call__(self, P):
        x, t, s = body(P); front = t < 5.0
        d_open = np.where(front, rect_dist(np.abs(x), s, OPEN_X, OPEN_S), np.inf)
        d_logo = np.where(front, rect_dist(np.abs(x - LOGO_C[0]), s, (0, LOGO_HW[0]), (LOGO_C[1] - LOGO_HW[1], LOGO_C[1] + LOGO_HW[1])), np.inf)
        return dict(outer=self.depth(P) < 0.6, d_open=d_open, d_logo=d_logo, z=P[:, 2], x=x, t=t, s=s)


def faces(m): return m.faces.reshape(-1, 4)[:, 1:]


def edge_keys(F, n):
    a = F[:, [0, 1, 2]].ravel(); b = F[:, [1, 2, 0]].ravel()
    return np.minimum(a, b) * n + np.maximum(a, b)


def subdivide(P, F, active, h):
    """conforming midpoint subdivision of the active triangles' edges longer than h (an edge is split in every
    triangle using it, so the inactive neighbours are split too; their geometry is unchanged)"""
    while True:
        n = len(P); k = edge_keys(F, n)
        uk, inv = np.unique(k, return_inverse=True)
        a, b = uk // n, uk % n
        L = np.linalg.norm(P[a] - P[b], axis=1)
        act = np.zeros(len(uk), bool); act[inv[np.repeat(active, 3)]] = True
        sp = act & (L > h)
        if not sp.any(): return P, F, active
        mid = np.full(len(uk), -1); mid[sp] = n + np.arange(sp.sum())
        P = np.vstack([P, (P[a[sp]] + P[b[sp]]) / 2])
        M = mid[inv].reshape(-1, 3); ns = (M >= 0).sum(1)
        out, oa = [F[ns == 0]], [active[ns == 0]]
        for cnt in (1, 2, 3):
            sel = np.where(ns == cnt)[0]
            if not len(sel): continue
            V, Mm, A = F[sel], M[sel], active[sel]
            if cnt == 1: r = np.argmax(Mm >= 0, 1)                        # the split edge to e0
            elif cnt == 2: r = (np.argmin(Mm >= 0, 1) + 1) % 3            # the unsplit edge to e2
            else: r = np.zeros(len(sel), int)
            ix = (np.arange(3)[None, :] + r[:, None]) % 3
            V = np.take_along_axis(V, ix, 1); Mm = np.take_along_axis(Mm, ix, 1)
            v0, v1, v2, m0, m1, m2 = V[:, 0], V[:, 1], V[:, 2], Mm[:, 0], Mm[:, 1], Mm[:, 2]
            if cnt == 1:
                T = [np.c_[v0, m0, v2], np.c_[m0, v1, v2]]
            elif cnt == 2:
                short = np.linalg.norm(P[v0] - P[m1], axis=1) < np.linalg.norm(P[m0] - P[v2], axis=1)
                T = [np.c_[m0, v1, m1], np.where(short[:, None], np.c_[v0, m0, m1], np.c_[v0, m0, v2]),
                     np.where(short[:, None], np.c_[v0, m1, v2], np.c_[m0, m1, v2])]
            else:
                T = [np.c_[v0, m0, m2], np.c_[m0, v1, m1], np.c_[m2, m1, v2], np.c_[m0, m1, m2]]
            out += T; oa += [A] * len(T)
        F = np.vstack(out); active = np.concatenate(oa)


def flips(P, F, ok, iters=12, max_dihedral=6.0):
    """Delaunay edge flips between near-coplanar triangles whose four vertices are all ok (relief region)"""
    cl = math.cos(math.radians(max_dihedral)); total = 0
    for _ in range(iters):
        n = len(P); k = edge_keys(F, n); o = np.argsort(k, kind="stable"); ks = k[o]
        pair = np.where(ks[1:] == ks[:-1])[0]
        e0, e1 = o[pair], o[pair + 1]                                     # half-edge ids (tri*3 + local)
        t0, l0, t1 = e0 // 3, e0 % 3, e1 // 3
        a = F[t0, l0]; b = F[t0, (l0 + 1) % 3]; c0 = F[t0, (l0 + 2) % 3]
        l1 = e1 % 3; c1 = F[t1, (l1 + 2) % 3]
        good = ok[a] & ok[b] & ok[c0] & ok[c1] & (c0 != c1)
        nrm = lambda i, j, q: np.cross(P[j] - P[i], P[q] - P[i])
        n0, n1 = nrm(a, b, c0), nrm(b, a, c1)
        l0n, l1n = np.linalg.norm(n0, axis=1), np.linalg.norm(n1, axis=1)
        good &= np.einsum("ij,ij->i", n0, n1) > cl * l0n * l1n
        def ang(c):
            u, v = P[a] - P[c], P[b] - P[c]
            return np.arccos(np.clip(np.einsum("ij,ij->i", u, v) / (np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1) + 1e-15), -1, 1))
        exc = ang(c0) + ang(c1) - math.pi
        good &= exc > 1e-6
        m0, m1 = nrm(a, c1, c0), nrm(b, c0, c1)                          # new triangles keep the orientation
        good &= (np.einsum("ij,ij->i", m0, n0) > 0) & (np.einsum("ij,ij->i", m1, n0) > 0)
        good &= ~np.isin(np.minimum(c0, c1) * n + np.maximum(c0, c1), ks)
        cand = np.where(good)[0]
        if not len(cand): break
        cand = cand[np.argsort(-exc[cand])]; rank = np.empty(len(cand)); rank[:] = np.arange(len(cand))
        best = np.full(len(F), np.inf); np.minimum.at(best, t0[cand], rank); np.minimum.at(best, t1[cand], rank)
        acc = cand[(best[t0[cand]] == rank) & (best[t1[cand]] == rank)]
        # one new edge c0-c1 per accepted set (two quads could create the same one)
        nk = np.minimum(c0[acc], c1[acc]) * n + np.maximum(c0[acc], c1[acc])
        _, first = np.unique(nk, return_index=True); acc = acc[np.sort(first)]
        F[t0[acc]] = np.c_[a[acc], c1[acc], c0[acc]]; F[t1[acc]] = np.c_[b[acc], c0[acc], c1[acc]]
        total += len(acc)
    return F, total


def mesh(P, F): return pv.PolyData(P, np.c_[np.full(len(F), 3), F].ravel())


def chord_tess(P, N, w, R, g=None, target=None, delta=None, h=None, fade=None):
    """W (target None) or F (target: Poisson radius ~target, shrunk on tight curves; vertices lifted at random h=(lo, hi),
    at least 0.8 x the local chord sag, faded out where the shell overhangs 33..41 deg): seeds (boundary rows along the openings and the rim line, then a variable-radius Poisson disk with the
    radius from the local flatness), restricted Delaunay on the fine mesh, every fine vertex moved along its normal
    onto the coarse triangles"""
    zi = np.where(w > 0.5)[0]; tz = cKDTree(P[zi])
    # flatness: range of the points over a 4 mm ball off their best-fit plane ~ k rho^2 / 2
    G = rng if g is None else g
    sub = zi[G.choice(len(zi), 12000, replace=False)]; rho = 4.0; rg = np.empty(len(sub))
    for i, nb in enumerate(tz.query_ball_point(P[sub], rho)):
        Q = P[zi[nb]] - P[zi[nb]].mean(0)
        nv = np.linalg.svd(Q, full_matrices=False)[2][2]; e = Q @ nv; rg[i] = np.ptp(e)
    if target is None:
        rad = np.clip(rho * np.sqrt(W_DELTA / np.maximum(rg, 1e-4)), 2.0, 7.0)
    else:
        rad = np.clip(rho * np.sqrt(delta / np.maximum(rg, 1e-4)), 0.7 * target, 1.15 * target)
    ts = cKDTree(P[sub]); rad = np.array([np.median(rad[nb]) for nb in ts.query_ball_point(P[sub], 5.0)])
    r_at = lambda X: rad[ts.query(X)[1]]
    x, t, s = R["x"], R["t"], R["s"]
    seeds = []
    # opening outlines: per side a rectangle 0.55 outside the opening, corners kept, edges divided evenly
    fz = zi[(t[zi] < 5.0)]; txs = cKDTree(np.c_[x[fz], s[fz]])
    e = 0.55
    for sg in (-1, 1):
        cx = [sg * (OPEN_X[0] - e), sg * (OPEN_X[1] + e)]; cs = [OPEN_S[0] - e, OPEN_S[1] + e]
        C = [(cx[0], cs[0]), (cx[1], cs[0]), (cx[1], cs[1]), (cx[0], cs[1])]
        for k in range(4):
            p, q = np.array(C[k]), np.array(C[(k + 1) % 4])
            pts = np.linspace(p, q, 200); P3 = P[fz[txs.query(pts)[1]]]
            nseg = max(1, int(round(np.linalg.norm(q - p) / (0.8 * r_at(P3).mean()))))
            seeds += list(fz[txs.query(np.linspace(p, q, nseg + 1)[:-1])[1]])
    # the rim line: z 5.4..5.6 round the shell
    rim = zi[(R["z"][zi] > 5.4) & (R["z"][zi] < 5.6)]
    th = np.arctan2(P[rim, 1] - P[rim, 1].mean(), P[rim, 0]); rim = rim[np.argsort(th)]
    last = None; first = None
    for i in rim:
        if last is None or np.linalg.norm(P[i] - P[last]) >= 0.8 * r_at(P[i][None])[0]:
            seeds.append(i); last = i; first = i if first is None else first
    nb_bound = len(seeds)
    # interior: variable-radius Poisson disk, radius jittered +-15 %
    cand = G.permutation(zi[w[zi] > 0.9])
    rc = r_at(P[cand]) * G.uniform(0.85, 1.15, len(cand))
    cell = 7.5; grid = {}
    def put(i, r): grid.setdefault(tuple((P[i] // cell).astype(int)), []).append((P[i], r))
    for i in seeds: put(i, r_at(P[i][None])[0])
    for i, ri in zip(cand, rc):
        p = P[i]; g = (p // cell).astype(int); ok = True
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for q, rq in grid.get((g[0] + dx, g[1] + dy, g[2] + dz), ()):
                        if (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2 < ((ri + rq) / 2) ** 2:
                            ok = False; break
                    if not ok: break
                if not ok: break
        if ok: put(i, ri); seeds.append(i)
    seeds = np.array(seeds); S = P[seeds]; SN = N[seeds]
    # coarse vertices: on the surface at the boundaries, lifted W_LIFT 4 mm away from them
    db = cKDTree(S[:nb_bound]).query(S)[0]
    if target is None:
        lift = W_LIFT * ss(db / 4.0)
    else:
        sag = rg[ts.query(S)[1]] * (0.7 * r_at(S)) ** 2 / 16             # chord sag of a facet round the seed
        lift = np.maximum(G.uniform(*h, len(S)), np.minimum(0.8 * sag, h[1])) * fade[seeds]
        lift[:nb_bound] = 0.0
    V = S + SN * lift[:, None]
    # restricted Delaunay: fine vertices labelled by the nearest seed, a coarse triangle per fine triangle of 3 labels
    lab = np.full(len(P), -1); zz = np.where(w > 0)[0]; lab[zz] = cKDTree(S).query(P[zz])[1]
    Fm = R["F"]; L = lab[Fm]
    tri = L[(L >= 0).all(1) & (L[:, 0] != L[:, 1]) & (L[:, 1] != L[:, 2]) & (L[:, 0] != L[:, 2])]
    tri = np.unique(np.sort(tri, 1), axis=0)
    nt = np.cross(V[tri[:, 1]] - V[tri[:, 0]], V[tri[:, 2]] - V[tri[:, 0]])
    flip = np.einsum("ij,ij->i", nt, SN[tri].sum(1)) < 0; tri[flip] = tri[flip][:, [0, 2, 1]]
    # projection: candidates = triangles round the 2 nearest seeds
    inc = [[] for _ in range(len(S))]
    for j, tr in enumerate(tri):
        for v in tr: inc[v].append(j)
    D = max(len(l) for l in inc); INC = np.full((len(S), D), -1)
    for v, l in enumerate(inc): INC[v, :len(l)] = l
    d = np.zeros(len(P)); miss = 0
    nn = cKDTree(S).query(P[zz], k=2)[1]
    for ch in np.array_split(np.arange(len(zz)), max(1, len(zz) // 40000)):
        p, n = P[zz[ch]], N[zz[ch]]
        c = np.concatenate([INC[nn[ch, 0]], INC[nn[ch, 1]]], 1); valid = c >= 0; c = np.where(valid, c, 0)
        A, B, Cc = V[tri[c, 0]], V[tri[c, 1]], V[tri[c, 2]]
        nT = np.cross(B - A, Cc - A); nT /= np.linalg.norm(nT, axis=2, keepdims=True) + 1e-15
        den = np.einsum("ijk,ik->ij", nT, n); dd = np.einsum("ijk,ijk->ij", nT, A - p[:, None]) / np.where(np.abs(den) > 0.3, den, np.nan)
        X = p[:, None] + dd[..., None] * n[:, None]
        v0, v1, v2 = B - A, Cc - A, X - A
        d00, d01, d11 = (v0 * v0).sum(2), (v0 * v1).sum(2), (v1 * v1).sum(2); d20, d21 = (v2 * v0).sum(2), (v2 * v1).sum(2)
        den2 = d00 * d11 - d01 * d01 + 1e-15; bv = (d11 * d20 - d01 * d21) / den2; bw = (d00 * d21 - d01 * d20) / den2
        mb = np.minimum(np.minimum(1 - bv - bw, bv), bw)
        mb = np.where(valid & np.isfinite(dd), mb, -np.inf)
        inside = mb >= -1e-6
        score = np.where(inside, np.abs(np.nan_to_num(dd, nan=1e9)), 1e6 - mb)
        j = np.argmin(score, 1); r_ = np.arange(len(ch))
        miss += int((~inside[r_, j]).sum())
        d[zz[ch]] = np.where(np.isfinite(mb[r_, j]), np.nan_to_num(dd[r_, j]), 0.0)
    # stats: coarse edges, angles, neighbour dihedral (full-strength area)
    TT = tri[(w[seeds[tri]] > 0.9).all(1)]
    E = np.linalg.norm(V[TT[:, [0, 1, 2]]] - V[TT[:, [1, 2, 0]]], axis=2)
    a2 = np.linalg.norm(np.cross(V[TT[:, 1]] - V[TT[:, 0]], V[TT[:, 2]] - V[TT[:, 0]]), axis=1)
    minang = np.degrees(np.arcsin(np.clip(a2 / (E.max(1) * np.sort(E, 1)[:, 1]), 0, 1)))   # the smallest angle
    nT = np.cross(V[tri[:, 1]] - V[tri[:, 0]], V[tri[:, 2]] - V[tri[:, 0]]); nT /= np.linalg.norm(nT, axis=1)[:, None]
    ek = np.sort(np.stack([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]], 1).reshape(-1, 2), 1)
    ek = ek[:, 0] * len(S) + ek[:, 1]; ti = np.repeat(np.arange(len(tri)), 3); o = np.argsort(ek); ek, ti = ek[o], ti[o]
    same = np.where(ek[1:] == ek[:-1])[0]
    dih = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", nT[ti[same]], nT[ti[same + 1]]), -1, 1)))
    st = dict(lift=lift[nb_bound:], seeds=len(S), boundary=nb_bound, tris=len(tri), edge=E.ravel(), minang=minang, dih=dih, miss=miss,
              rad=rad, n_proj=len(zz), V=V, tri=tri)
    return d, st


def check(m, name, d, sup_top):
    e = m.extract_feature_edges(boundary_edges=True, non_manifold_edges=True, feature_edges=False, manifold_edges=False)
    bodies = int(m.connectivity().point_data["RegionId"].max() + 1)
    F = faces(m); P = m.points
    nr = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]]); a = np.linalg.norm(nr, axis=1); ok = a > 0.02   # >= 0.01 mm2
    oh = np.degrees(np.arcsin(np.clip(-nr[:, 2] / np.maximum(a, 1e-12), 0, 1)))
    xc, tc, sc = body(P[F].mean(1))
    rel = ok & (np.abs(d[F]) > 1e-9).any(1) & ~sup_top(xc, tc, sc)
    wi = np.argmax(np.where(rel, oh, -1))
    line = (f"{name}: open / non-manifold edges {e.n_cells}, bodies {bodies}, {m.n_cells} triangles; overhang printed standing on the "
            f"relief max {oh[rel].max():.2f} deg at (x {xc[wi]:.1f}, t {tc[wi]:.1f}, s {sc[wi]:.1f}) (99.9% {np.percentile(oh[rel], 99.9):.1f}; triangles >= 0.01 mm2, top end walls excluded)")
    log(line); return line


def main():
    src = pv.read(SRC).clean(tolerance=1e-7, absolute=True)
    P0 = np.asarray(src.points, float); F0 = faces(src).copy()
    log("source", SRC.name, len(F0), "triangles")
    Rg = Regions(P0)
    def zone(P):
        R = Rg(P)
        return R["outer"] & (R["z"] > Z_CLEAN - 0.5) & (R["d_open"] > 0.2)
    cache = pathlib.Path(__file__).parent / "out-coupon/relief-c-base.npz"   # the refined base (slow), per source
    if cache.exists() and cache.stat().st_mtime > SRC.stat().st_mtime:
        z = np.load(cache); P, F = z["P"], z["F"]; R = Rg(P)
    else:
        zv = zone(P0)
        P, F, act = subdivide(P0, F0, zv[F0].any(1), H_REF)
        log("subdivided", len(F))
        R = Rg(P)
        okv = R["outer"] & (R["z"] > Z_CLEAN - 0.5) & (R["d_open"] > 0.2)
        F, nf = flips(P, F, okv)
        log("flips", nf); np.savez(cache, P=P, F=F)
    m = mesh(P, F).compute_normals(cell_normals=False, split_vertices=False, consistent_normals=True, auto_orient_normals=True)
    N = m.point_data["Normals"]; F = faces(m).copy(); R["F"] = F           # (orientation as compute_normals left it)
    # weights
    oh = np.degrees(np.arcsin(np.clip(-N[:, 2], 0, 1)))
    # the shell's own overhang features (cable notch / lid ledge at the back bottom, bridges): 1.5 mm clear of them
    Fb = faces(m); nr = np.cross(P[Fb[:, 1]] - P[Fb[:, 0]], P[Fb[:, 2]] - P[Fb[:, 0]]); ar = np.linalg.norm(nr, axis=1)
    sup_top = lambda xc, tc, sc: (np.abs(sc - OPEN_S[1]) < 0.3) & (np.abs(xc) > 2.0) & (np.abs(xc) < 15.3) & (tc > -0.2) & (tc < 3.5)
    zc = P[Fb].mean(1)[:, 2]
    feat = ((ar > 1e-8) & (-nr[:, 2] > math.sin(math.radians(45)) * ar) & (zc > 0.01) & (zc < 50) & R["outer"][Fb].all(1)
            & ~sup_top(*body(P[Fb].mean(1))))
    dfeat = cKDTree(P[Fb[feat]].mean(1)).query(P)[0]
    wfeat = ss((dfeat - 1.0) / 4.0)                                      # (W was built with a 1.5 ramp)
    outer = R["outer"] * wfeat
    wW = outer * ss((R["d_open"] - 0.3) / 0.5) * ss((R["z"] - Z_CLEAN) / 0.5)
    logo = ss((2.5 - R["d_logo"]) / 1.5)                                 # 1 within 1 mm of the pocket, 0 by 2.5
    out = {"W": pv.read(TP / "pebble-C-shell-relief-W.stl")}            # W as built (unchanged)
    fade = ss((41.0 - oh) / 8.0) * ss((dfeat - 2.0) / 5.0)              # lifts: off near 41 deg and the notch / ledge
    for nm, seed, target, delta, h in (("F5", 5, 3.85, 0.45, (0.05, 0.45)), ("F9", 9, 6.5, 1.0, (0.10, 0.50))):
        d, st = chord_tess(P, N, wW, R, g=np.random.default_rng(seed), target=target, delta=delta, h=h, fade=fade)
        d = np.minimum(d, h[1]) * wW * ss((R["z"] - Z_CLEAN) / 3.0)      # capped (concave spans), a 3 mm rim ramp where
        d = d - np.minimum(d, 0) * logo                                  # no rim vertices (by the back ledge)
        clip = (d < -W_IN).sum(); d = np.maximum(d, -W_IN)
        mm = mesh(P + N * d[:, None], F); out[nm] = mm
        p = TP / f"pebble-C-shell-relief-{nm}.stl"; mm.save(p, binary=True)
        check(mm, p.name, d, sup_top)
        z = d[wW > 0.95]; L = st["lift"]
        log(f"{nm}: {st['seeds']} vertices ({st['boundary']} on the openings / rim line), {st['tris']} facets; edges median {np.median(st['edge']):.1f} "
            f"(5-95% {np.percentile(st['edge'], 5):.1f}-{np.percentile(st['edge'], 95):.1f}); smallest angle median {np.median(st['minang']):.0f}, "
            f"1% {np.percentile(st['minang'], 1):.0f}, min {st['minang'].min():.0f} deg; neighbour dihedral median {np.median(st['dih']):.1f} "
            f"(95% {np.percentile(st['dih'], 95):.1f}); vertex lift median {np.median(L):.2f}, max {L.max():.2f}; surface displacement median "
            f"{np.median(z):+.3f}, 5% {np.percentile(z, 5):+.3f}, 95% {np.percentile(z, 95):+.3f}, max {d.max():+.3f}; clamped at -{W_IN}: "
            f"{clip} of {(np.abs(d) > 0).sum()}; logo patch min {d[R['d_logo'] <= 1.0].min():+.3f}")
    render(out)


def render(out):
    foc = json.loads((ROOT / "cad/desk/out-smooth/pebble/focus.json").read_text())
    st = np.array(foc["slot_top"]) * np.array([-1, 1, 1])                # the left slot's top end (viewer's left)
    names = [("F5", "F5: raised chord facets ~5 mm"), ("F9", "F9: raised chord facets ~8-9 mm"), ("W", "W: adaptive chord tessellation")]
    c0 = np.array(out["W"].center); L = out["W"].length
    el, az = math.radians(33), math.radians(38)
    dview = np.array([-math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])
    pl = pv.Plotter(off_screen=True, window_size=(3 * 760, 900 + 620), shape=(2, 3),
                    row_weights=[900, 620], lighting="none")
    for j, (k, title) in enumerate(names):
        for i in range(2):
            pl.subplot(i, j); pl.set_background("#d8d5cf", top="#f3f1ed")
            foc_p = c0 if i == 0 else st
            for pos, it in (((-1.0, -0.25, 0.55), 0.85), ((0.7, -0.9, 0.25), 0.2), ((0.2, 1.0, 0.6), 0.15)):
                pl.add_light(pv.Light(position=tuple(foc_p + np.array(pos) * 500), focal_point=tuple(foc_p), intensity=it), only_active=True)
            pl.add_mesh(out[k], color="#ece6d8", smooth_shading=False, specular=0.08, specular_power=12, ambient=0.14, diffuse=0.9)
            if i == 0:
                pl.add_mesh(pv.Plane(center=(c0[0], c0[1], -0.05), direction=(0, 0, 1), i_size=600, j_size=600), color="#cfcac2", ambient=0.5, diffuse=0.6)
                pl.camera_position = [tuple(c0 + dview * L * 4.0), tuple(c0), (0, 0, 1)]; pl.camera.view_angle = 17
                pl.add_text(f"{title}\nfront-left, 33 deg above level", font_size=10, color="black")
            else:
                dv = np.array([-0.45, -1.0, 0.75]); dv /= np.linalg.norm(dv)
                pl.camera_position = [tuple(st + dv * 60), tuple(st), (0, 0, 1)]; pl.camera.view_angle = 22
                pl.add_text(f"{k}: left slot, top end", font_size=10, color="black")
            pl.reset_camera_clipping_range()
    pl.enable_anti_aliasing("ssaa"); p = ROOT / "images/desk-housing-v3/relief-C-versions.png"; pl.screenshot(str(p)); pl.close(); log(p)


if __name__ == "__main__":
    main()
