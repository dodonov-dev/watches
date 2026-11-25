"""Surface relief on the pebble, flat-shaded clay (mesh displacement of the checked A shell, outward only):
  smooth   to-print/pebble-A-shell.stl as exported
  WIP      to-print/pebble-PREVIEW-shell.stl (the first print: coarse tessellation facets)
  facets   planar facets ~8 mm (tangent planes at Poisson-disk seeds, the surface raised to them), crisp convex ridges
  river    low-frequency smooth undulation, like a river stone
Relief only on the outer surface, faded out over the front panel (slots, logo) and where the surface already overhangs
near 45 deg printed standing. Prints facet size / chord deviation of the WIP and the relief's amplitude.
    ~/.venvs/cad/bin/python relief.py [outdir]
"""
import sys, math, pathlib
import numpy as np
import pyvista as pv
from scipy.spatial import ConvexHull, cKDTree

ROOT = pathlib.Path(__file__).parents[4]
OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "images/desk-housing-v3")
TP = ROOT / "cad/desk/to-print"
C15, S15 = math.cos(math.radians(15)), math.sin(math.radians(15))
rng = np.random.default_rng(7)


def outer_mask(m, tol=1.5):
    h = ConvexHull(m.points[rng.choice(m.n_points, min(4000, m.n_points), replace=False)])
    E = h.equations
    d = np.concatenate([-(c @ E[:, :3].T + E[:, 3]).max(1) for c in np.array_split(m.points, 40)])   # depth inside the hull
    return d < tol


def ss(u): u = np.clip(u, 0, 1); return u * u * (3 - 2 * u)


def weights(m, z_clean=5.0, outer=None):
    """1 on the outer surface; feathered to 0 over FEATHER before the front panel (slots, brow, chin, logo), in the
    bottom z_clean (plus a 4 mm ramp), and where the printed overhang nears 45 deg"""
    P = m.points; N = m.point_data["Normals"]
    x, y, z = P.T
    t, s = y * C15 - z * S15, y * S15 + z * C15                        # body frame (front t ~ 0, s along the lean)
    dx = np.clip(np.abs(x) - 19.0, 0, None); dsv = np.clip(np.maximum(4.0 - s, s - 99.0), 0, None)
    wp = ss(np.hypot(dx, dsv) / FEATHER)
    wp = 1 - (1 - wp) * ss((25.0 - t) / 6.0)                            # the panel is the front only (fades out by t 25)
    oh = np.degrees(np.arcsin(np.clip(-N[:, 2], 0, 1)))                  # overhang from vertical, printed standing
    wo = ss((38.0 - oh) / 8.0)
    wz = ss((z - z_clean) / 4.0)
    return wp * wo * wz * (outer_mask(m) if outer is None else outer)


FEATHER = 8.0


def facets(m, w, lo, hi, tilt, dome=0.0, cap=0.5, seed=1):
    """irregular planar facets, outward only: Poisson-disk seeds with mixed radii (lo..hi, x (1 + dome) on the dome);
    per seed its tangent plane tilted by a random tilt (deg) in a random direction, lifted so it stays above the
    surface over its cell; the surface raised to the lowest of the nearest planes (convex ridges), capped"""
    r = np.random.default_rng(seed)
    P = m.points; N = m.point_data["Normals"]
    idx = r.permutation(np.where(w > 0.02)[0])[:200000]
    rad = r.uniform(lo, hi, len(idx)) * (1 + dome * ss((P[idx, 2] - 80.0) / 20.0))
    cell = hi * (1 + dome); grid, keep = {}, []
    for i, ri in zip(idx, rad):
        p = P[i]; g = tuple((p // cell).astype(int))
        ok = True
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for (q, rq) in grid.get((g[0] + dx, g[1] + dy, g[2] + dz), ()):
                        if np.linalg.norm(p - q) < (ri + rq) / 2:
                            ok = False; break
                    if not ok: break
                if not ok: break
            if not ok: break
        if ok:
            grid.setdefault(g, []).append((p, ri)); keep.append((i, ri))
    si = np.array([k for k, _ in keep]); R = np.array([k for _, k in keep])
    S, SN = P[si], N[si]
    th = np.radians(r.uniform(*tilt, len(si)))
    u = np.cross(SN, r.normal(size=(len(si), 3))); u /= np.linalg.norm(u, axis=1)[:, None]
    n = SN * np.cos(th)[:, None] + u * np.sin(th)[:, None]
    o = 2.0 * R * np.tan(th)          # lifted: stays above the surface out to 2 cells, so no plane dips (no k-nearest jumps)
    Q = S + SN * o[:, None]
    _, nb = cKDTree(S).query(P, k=14)
    num = np.einsum("ijk,ijk->ij", n[nb], Q[nb] - P[:, None, :])
    den = np.einsum("ijk,ik->ij", n[nb], N)
    di = np.where(den > 0.3, num / np.maximum(den, 1e-6), np.inf).min(1)
    d = np.clip(np.where(np.isfinite(di), di, 0.0), 0, cap)
    # stats over the fully relieved area: facet size (nearest-seed spacing), angle between neighbouring planes
    full = w[si] > 0.95
    dist, nn = cKDTree(S).query(S, k=2); sp = dist[:, 1][full]
    pr = np.array(sorted(cKDTree(S).query_pairs(1.3 * hi * (1 + dome))))
    near = np.linalg.norm(S[pr[:, 0]] - S[pr[:, 1]], axis=1) < 1.25 * (R[pr[:, 0]] + R[pr[:, 1]]) / 2
    pr = pr[near & full[pr[:, 0]] & full[pr[:, 1]]]
    ang = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", n[pr[:, 0]], n[pr[:, 1]]), -1, 1)))
    return d * w, dict(n=len(si), size=sp, ang=ang, planes=(Q, n), clamp=float((di[w > 0.95] < 0).mean()))


def apply_planes(m, planes, w, cap=0.5):
    """the same facet planes on another mesh of the same surface (the coupon)"""
    Q, n = planes; P = m.points; N = m.point_data["Normals"]
    _, nb = cKDTree(Q).query(P, k=14)
    num = np.einsum("ijk,ijk->ij", n[nb], Q[nb] - P[:, None, :])
    den = np.einsum("ijk,ik->ij", n[nb], N)
    di = np.where(den > 0.3, num / np.maximum(den, 1e-6), np.inf).min(1)
    return np.clip(np.where(np.isfinite(di), di, 0.0), 0, cap) * w


def tri_overhang(m, mask_w=None):
    """printed overhang (deg from vertical) of every triangle; with mask_w only those touching relief (w > 0)"""
    F = m.faces.reshape(-1, 4)[:, 1:] if m.faces.size % 4 == 0 else m.triangulate().faces.reshape(-1, 4)[:, 1:]
    P = m.points; nr = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
    a = np.linalg.norm(nr, axis=1); ok = a > 1e-9
    oh = np.degrees(np.arcsin(np.clip(-nr[ok, 2] / a[ok], 0, 1)))
    if mask_w is not None:
        oh = oh[mask_w[F[ok]].max(1) > 0]
    return oh


def displaced(m, d):
    out = m.copy(); out.points = m.points + m.point_data["Normals"] * d[:, None]
    out.point_data.clear(); out.cell_data.clear()                       # stale normals would shade it as the original
    return out


def knapped(m, w, spacing=8.0, cap=1.0):
    P = m.points; idx = rng.permutation(np.where(w > 0.01)[0])[:150000]
    grid, seeds = {}, []                                                # greedy Poisson disk on the surface
    for i in idx:
        p = P[i]; g = tuple((p // spacing).astype(int))
        near = [q for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
                for q in grid.get((g[0] + dx, g[1] + dy, g[2] + dz), ())]
        if any(np.linalg.norm(p - q) < spacing for q in near):
            continue
        grid.setdefault(g, []).append(p); seeds.append(p)
    seeds = np.array(seeds)
    # planar facets: the tangent planes at the seeds, the surface raised to the nearest enclosing one (outward only,
    # convex ridges between facets as the WIP's tessellation, but ~8 mm and designed)
    N = m.point_data["Normals"]; si = cKDTree(P).query(seeds)[1]; sn = N[si]
    _, nb = cKDTree(seeds).query(P, k=8)
    num = np.einsum("ijk,ijk->ij", sn[nb], seeds[nb] - P[:, None, :])
    den = np.einsum("ijk,ik->ij", sn[nb], N)
    di = np.where(den > 0.3, num / np.maximum(den, 1e-6), np.inf).min(1)
    d = np.clip(np.where(np.isfinite(di), di, 0.0), 0, cap)            # no enclosing plane (was: a 1.0 spike, the specks)
    pr = np.array(sorted(cKDTree(seeds).query_pairs(1.3 * spacing)))   # neighbouring facets: angle between their planes
    ang = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", sn[pr[:, 0]], sn[pr[:, 1]]), -1, 1)))
    return d * w, len(seeds), ang


def river(m, w, amp=0.8):
    P = m.points; n = np.zeros(len(P))
    for _ in range(7):
        k = rng.normal(size=3); k /= np.linalg.norm(k); lam = rng.uniform(12, 22)
        n += np.sin(2 * np.pi * (P @ k) / lam + rng.uniform(0, 2 * np.pi))
    n = (n - n.min()) / (n.max() - n.min())
    return amp * n * w


def dihedral(m, sel):
    """angle between the normals of edge-adjacent triangles whose centres are in sel"""
    F = m.faces.reshape(-1, 4)[:, 1:]; n = m.compute_normals(cell_normals=True, point_normals=False).cell_data["Normals"]
    E = np.sort(np.stack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]], 1).reshape(-1, 2), 1)
    c = np.repeat(np.arange(len(F)), 3); o = np.lexsort(E.T[::-1]); E, c = E[o], c[o]
    same = np.all(E[1:] == E[:-1], 1); a, b = c[:-1][same], c[1:][same]
    k = sel[a] & sel[b]
    return np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", n[a[k]], n[b[k]]), -1, 1)))


def wip_stats(wip, smooth):
    ow = outer_mask(wip)
    cells = wip.extract_points(ow, adjacent_cells=False).extract_surface(algorithm="dataset_surface")
    c = cells.cell_centers().points
    away = c[:, 1] * C15 - c[:, 2] * S15 > 12                           # not the front panel (changed since the WIP)
    e = cells.extract_all_edges(); L = e.compute_cell_sizes()["Length"]
    _, cp = smooth.find_closest_cell(c[away], return_closest_point=True)
    dev = np.linalg.norm(cp - c[away], axis=1)
    cc = wip.cell_centers().points; hull_in = outer_mask(pv.PolyData(cc))
    sel = hull_in & (cc[:, 1] * C15 - cc[:, 2] * S15 > 12)
    ang = dihedral(wip, sel)
    return np.median(L), np.percentile(L, 90), np.median(dev), np.percentile(dev, 95), ang[ang < 40]   # not the rim / slot edges


def main():
    sm = pv.read(TP / "pebble-A-shell.stl").clean(tolerance=0.005, absolute=True).compute_normals(split_vertices=False, auto_orient_normals=True)
    wip = pv.read(TP / "pebble-PREVIEW-shell.stl").clean()
    w = weights(sm)
    global F5, F9
    d5, F5 = facets(sm, w, 3.5, 7.0, (1.5, 4.0), seed=5)
    d9, F9 = facets(sm, w, 6.0, 12.0, (0.0, 1.5), dome=0.25, seed=9)
    a, b, c, d, angwip = wip_stats(wip, sm)
    print(f"WIP: edges median {a:.2f} (90% {b:.2f}), inside {c:.3f} / {d:.3f}; neighbour angle {np.median(angwip):.1f} / {np.percentile(angwip, 95):.1f}")
    for nm, dd, F in (("F5", d5, F5), ("F9", d9, F9)):
        z = dd[w > 0.95]
        print(f"{nm}: {F['n']} facets, size (seed spacing) median {np.median(F['size']):.1f} (5-95% {np.percentile(F['size'], 5):.1f}-"
              f"{np.percentile(F['size'], 95):.1f}); neighbour angle median {np.median(F['ang']):.1f} (95% {np.percentile(F['ang'], 95):.1f}) deg; "
              f"raised median {np.median(z):.2f}, 95% {np.percentile(z, 95):.2f}, max {dd.max():.2f}; under the surface before clamp {F['clamp']:.1%}")
    V = [("smooth (A as exported)", displaced(sm, 0 * d5)), ("WIP (preview tessellation)", wip),
         ("F5: facets 3.5-7 mm, tilt 1.5-4 deg", displaced(sm, d5)), ("F9: facets 6-12 mm (dome +25%), tilt 0-1.5 deg", displaced(sm, d9))]
    for nm, mm in V[2:]:
        oh = tri_overhang(mm, w)
        print(nm[:2], f"overhang printed standing on the relief: max {oh.max():.1f}, 99.9% {np.percentile(oh, 99.9):.1f}")
    c0 = np.array(sm.center); L = sm.length
    def shot(views, fname, wh):
        pl = pv.Plotter(off_screen=True, window_size=(len(V) * wh[0], len(views) * wh[1]), shape=(len(views), len(V)),
                        lighting="none")
        for j, (name, m) in enumerate(V):
            for i, (vn, d, par) in enumerate(views):
                pl.subplot(i, j); pl.set_background("#d8d5cf", top="#f3f1ed")
                for pos, it in (((-1.0, -0.15, 0.35), 0.9), ((0.6, -1.0, 0.3), 0.18)):   # raking key from upper left, weak fill
                    pl.add_light(pv.Light(position=tuple(c0 + np.array(pos) * 500), focal_point=tuple(c0), intensity=it), only_active=True)
                pl.add_mesh(m, color="#ece6d8", smooth_shading=False, specular=0.1, specular_power=10, ambient=0.12, diffuse=0.9)
                pl.add_mesh(pv.Plane(center=(c0[0], c0[1], -3.0), direction=(0, 0, 1), i_size=600, j_size=600),
                            color="#cfcac2", ambient=0.5, diffuse=0.6)
                dd = np.array(d) / np.linalg.norm(d)
                pl.camera_position = [tuple(c0 + dd * L * (4.0 if not par else 2.5)), tuple(c0), (0, 0, 1)]
                if par:
                    pl.camera.parallel_projection = True; pl.camera.parallel_scale = L * 0.5
                else:
                    pl.camera.view_angle = 17
                pl.reset_camera_clipping_range()
                pl.add_text(f"{name}\n{vn}", font_size=10, color="black")
        pl.enable_anti_aliasing("ssaa"); p = OUT / fname; pl.screenshot(str(p)); pl.close(); print(p)
    shot([("hero", (-0.62, -1.0, 0.36), False), ("left", (-1.0, -0.38, 0.30), False)], "relief-hero.png", (700, 880))
    shot([("front", (0, -1, 0.0), True), ("side", (-1, 0, 0), True)], "relief-ortho.png", (620, 820))


if __name__ == "__main__":
    main()
