"""Relief coupons: the pebble A shell's dome cap from z Z0 up, slots filled flush (the front panel is smooth in every
variant), printed standing as the shell, rim on the bed. F5 / F9: relief.facets on the full shell, the same planes
applied to the coupon's outer surface; plain: no relief (slicer fuzzy-skin tests).
    ~/.venvs/cad/bin/python coupon.py
Writes cad/desk/to-print/relief-coupon-{F5,F9,plain}.stl and images/desk-housing-v3/relief-coupons.png.
"""
import sys, math, pathlib
REBUILD = "--rebuild" in sys.argv; sys.argv = sys.argv[:1]
import numpy as np
import pyvista as pv
import relief
from relief import ROOT, TP, C15, S15, facets, apply_planes, weights, tri_overhang
from slot_edges import f, HALF

Z0 = 72.0
STEP = ROOT / "cad/desk/out-smooth/pebble/shell.step"
TMP = ROOT / "cad/desk/concept/ovaltilt-sketch/out-coupon"; TMP.mkdir(exist_ok=True)


def build_cap():
    from build123d import (import_step, export_stl, Spline, Line, Wire, Face, Box, Pos, Axis, Vector, Align,
                           extrude, GeomType)
    shell = import_step(str(STEP))
    # the flat inner face: its t (body frame) from the largest plane facing back-down
    best = None
    for fc in shell.faces():
        if fc.geom_type != GeomType.PLANE: continue
        nrm = fc.normal_at(fc.center())
        if abs(nrm.Y * C15 - nrm.Z * S15) > 0.999 and (best is None or fc.area > best.area):
            best = fc
    c = best.center(); t_in = c.Y * C15 - c.Z * S15
    print(f"inner face t {t_in:.4f}, area {best.area:.0f}")
    s0 = (Z0 - 6) / C15; s1 = 91.85 + 0.6
    plugs = []
    XC = 10.23
    for sg in (-1, 1):
        # trapezoid: on the face the opening (lips included) + margin, at the inner face the land's hole + 0.3; its slanted
        # sides run through wall material (behind the lips' chords), so it fills only the cut and nothing sticks out
        fx = sorted((sg * 3.0, sg * 16.2)); bx = sorted((sg * (XC - HALF - 0.3), sg * (XC + HALF + 0.3)))
        xs = np.linspace(fx[0], fx[1], 41)
        sp = Spline(*[Vector(x, float(f(x)), 0) for x in xs])
        w = Wire([sp, Line(Vector(fx[1], float(f(fx[1])), 0), Vector(bx[1], t_in, 0)), Line(Vector(bx[1], t_in, 0), Vector(bx[0], t_in, 0)),
                  Line(Vector(bx[0], t_in, 0), Vector(fx[0], float(f(fx[0])), 0))])
        pl = extrude(Face(w), amount=s1 - s0)
        plugs.append(pl.translate((0, 0, s0)).rotate(Axis.X, -15))
    cap = shell.fuse(*plugs, tol=0.02)
    box = Pos(0, 0, Z0) * Box(300, 300, 100, align=(Align.CENTER, Align.CENTER, Align.MIN))
    cap = cap & box
    sol = cap.solids()
    print("cap solids", len(sol), "volume", round(sum(s.volume for s in sol) / 1000, 2), "cm3")
    from build123d import export_step
    export_step(cap, str(TMP / "cap.step"))
    back = import_step(str(TMP / "cap.step"))                           # meshed from the STEP read back: closed (the
    export_stl(back, str(TMP / "cap.stl"), tolerance=0.003, angular_tolerance=0.05)   # in-memory one leaves a crack)


def refine(m, h=0.45, flips=True):
    """longest-edge bisection until every edge is <= h (conforming: an edge is split in both its triangles), then
    Delaunay edge flips between near-coplanar triangles (< 2 deg) so the slivers of the CAD tessellation become
    roughly isotropic"""
    import heapq
    V = [tuple(p) for p in m.points]; F = [list(f) for f in m.faces.reshape(-1, 4)[:, 1:]]
    E = {}
    for i, f in enumerate(F):
        for k in range(3):
            E.setdefault(tuple(sorted((f[k], f[(k + 1) % 3]))), set()).add(i)
    L = lambda e: math.dist(V[e[0]], V[e[1]])
    q = [(-L(e), e) for e in E if L(e) > h]; heapq.heapify(q)
    while q:
        _, e = heapq.heappop(q)
        if e not in E or L(e) <= h:
            continue
        a, b = e; mi = len(V); V.append(tuple((np.array(V[a]) + np.array(V[b])) / 2))
        for fi in list(E.pop(e)):
            f = F[fi]; k = [j for j in range(3) if {f[j], f[(j + 1) % 3]} == {a, b}][0]
            p_, q_, r_ = f[k], f[(k + 1) % 3], f[(k + 2) % 3]
            F[fi] = [p_, mi, r_]; nf = len(F); F.append([mi, q_, r_])
            E[tuple(sorted((q_, r_)))].discard(fi); E[tuple(sorted((q_, r_)))].add(nf)
            for ed, fid in (((p_, mi), fi), ((mi, r_), fi), ((mi, q_), nf), ((mi, r_), nf)):
                E.setdefault(tuple(sorted(ed)), set()).add(fid)
            for ed in ((p_, mi), (mi, q_), (mi, r_)):
                ed = tuple(sorted(ed))
                if L(ed) > h: heapq.heappush(q, (-L(ed), ed))
    P = np.array(V); F = np.array(F)
    if flips:
        for _ in range(6):
            nflip = 0
            E = {}
            for i, f in enumerate(F):
                for k in range(3):
                    E.setdefault(tuple(sorted((f[k], f[(k + 1) % 3]))), []).append(i)
            done = set()
            for (a, b), fs in E.items():
                if len(fs) != 2 or fs[0] in done or fs[1] in done: continue
                f0, f1 = F[fs[0]], F[fs[1]]
                c0 = [v for v in f0 if v not in (a, b)][0]; c1 = [v for v in f1 if v not in (a, b)][0]
                n0 = np.cross(P[f0[1]] - P[f0[0]], P[f0[2]] - P[f0[0]]); n1 = np.cross(P[f1[1]] - P[f1[0]], P[f1[2]] - P[f1[0]])
                if np.dot(n0, n1) < np.cos(np.radians(2)) * np.linalg.norm(n0) * np.linalg.norm(n1): continue
                ang = lambda c: np.arccos(np.clip(np.dot(P[a] - P[c], P[b] - P[c]) / (np.linalg.norm(P[a] - P[c]) * np.linalg.norm(P[b] - P[c])), -1, 1))
                if ang(c0) + ang(c1) <= np.pi + 1e-9: continue
                # orientation: f0 has a->b in order (or b->a); keep the winding
                k = list(f0).index(a); ab = f0[(k + 1) % 3] == b
                nf0, nf1 = ([c0, c1, b], [c1, c0, a]) if ab else ([c1, c0, b], [c0, c1, a])
                m0 = np.cross(P[nf0[1]] - P[nf0[0]], P[nf0[2]] - P[nf0[0]]); m1 = np.cross(P[nf1[1]] - P[nf1[0]], P[nf1[2]] - P[nf1[0]])
                if np.dot(m0, n0) <= 0 or np.dot(m1, n0) <= 0: continue
                F[fs[0]], F[fs[1]] = nf0, nf1; done.update(fs); nflip += 1
            if not nflip: break
    out = pv.PolyData(P, np.c_[np.full(len(F), 3), F].ravel())
    e = np.linalg.norm(P[F[:, [0, 1, 2]]] - P[F[:, [1, 2, 0]]], axis=2)
    a2 = np.linalg.norm(np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]]), axis=1)
    asp = e.max(1) ** 2 / np.maximum(a2, 1e-12)                                    # 1.15 equilateral
    print(f"refined: {len(F)} triangles, edges median {np.median(e):.2f} max {e.max():.2f}; aspect (longest^2/2A) median {np.median(asp):.2f}, 95% {np.percentile(asp, 95):.1f}")
    return out


def check(m, name):
    e = m.extract_feature_edges(boundary_edges=True, non_manifold_edges=True, feature_edges=False, manifold_edges=False)
    bodies = m.connectivity().point_data["RegionId"].max() + 1
    zmin = m.points[:, 2].min()
    oh = tri_overhang(m)
    F = m.faces.reshape(-1, 4)[:, 1:]; P = m.points
    nr = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]]); a = np.linalg.norm(nr, axis=1)
    ok = a > 1e-9; zc = P[F[ok]].mean(1)[:, 2]
    bad = (oh > 45.0) & (zc > 0.01)
    hz = zc[bad]
    print(f"{name}: open/non-manifold edges {e.n_cells}, bodies {bodies}, rim z {zmin:.4f} (flat: "
          f"{np.ptp(P[P[:, 2] < 0.01, 2]):.1e}), height {P[:, 2].max():.2f}, volume {m.volume / 1000:.2f} cm3; "
          f"faces > 45 deg (off the bed): {bad.sum()} ({a[ok][bad].sum() / 2:.1f} mm2"
          + (f", at z {hz.min():.1f}..{hz.max():.1f}, max {oh[bad].max():.1f}" if bad.any() else "") + ")")


def main():
    if not (TMP / "cap.stl").exists() or REBUILD:
        build_cap()
    coarse = pv.read(TMP / "cap.stl").clean(tolerance=0.002, absolute=True)
    rf = TMP / "cap-refined.vtp"
    if REBUILD or not rf.exists() or rf.stat().st_mtime < (TMP / "cap.stl").stat().st_mtime:
        refine(coarse).save(rf)
    cap = pv.read(rf)                                                   # isotropic ~0.45 mm: facet ridges stay straight
    cap = cap.compute_normals(split_vertices=False, auto_orient_normals=True)
    # outer surface: nothing of the coupon along the normal (rays), on the coarse mesh, carried to the refined one
    import vtk
    from scipy.spatial import cKDTree
    cc = coarse.compute_normals(split_vertices=False, auto_orient_normals=True)
    lid = pv.Plane(center=(0, 30, Z0 - 0.01), direction=(0, 0, 1), i_size=300, j_size=300).triangulate()
    obb = vtk.vtkOBBTree(); obb.SetDataSet(cc.merge(lid)); obb.BuildLocator()   # the open bottom closed: rays from the
                                                                        # cavity must not escape through it
    hit = vtk.vtkPoints()
    outer_c = np.array([obb.IntersectWithLine(tuple(p + n * 0.4), tuple(p + n * 40.0), hit, None) == 0
                        for p, n in zip(cc.points, cc.point_data["Normals"])], float)
    tc = cKDTree(cc.points)                                             # majority of the 16 nearest: no single-vertex islands
    _, nb = tc.query(cap.points, k=16)
    outer = relief.ss((outer_c[nb].mean(1) - 0.3) / 0.4)
    print("outer vertices", f"{outer.mean():.0%}")
    print("coupon mesh", cap.n_cells, "triangles")
    sm = pv.read(TP / "pebble-A-shell.stl").clean(tolerance=0.005, absolute=True).compute_normals(split_vertices=False, auto_orient_normals=True)
    w = weights(sm)
    _, F5 = facets(sm, w, 3.5, 7.0, (1.0, 2.5), seed=5)
    _, F9 = facets(sm, w, 6.0, 12.0, (0.0, 1.0), dome=0.25, seed=9)
    wc = weights(cap, z_clean=Z0 + 3.0, outer=outer)
    out = {}
    for name, F in (("F5", F5), ("F9", F9), ("plain", None)):
        m = cap.copy()
        if F is not None:
            m.points = cap.points + cap.point_data["Normals"] * apply_planes(cap, F["planes"], wc)[:, None]
        m.point_data.clear(); m.cell_data.clear()
        m.points[:, 2] -= Z0
        m.points[np.abs(m.points[:, 2]) < 1e-6, 2] = 0.0
        p = TP / f"relief-coupon-{name}.stl"; m.save(p); out[name] = m
        check(m, p.name)
    # picture: flat-shaded, grazing light, front-3/4 and back-3/4
    V = (("front 3/4", (-0.7, -1.0, 0.35)), ("back 3/4", (0.7, 1.0, 0.35)))
    c0 = np.array(out["plain"].center); L = out["plain"].length
    pl = pv.Plotter(off_screen=True, window_size=(3 * 640, 2 * 600), shape=(2, 3), lighting="none")
    for j, name in enumerate(("F5", "F9", "plain")):
        for i, (vn, d) in enumerate(V):
            pl.subplot(i, j); pl.set_background("#d8d5cf", top="#f3f1ed")
            dd = np.array(d) / np.linalg.norm(d)
            side = np.cross(dd, (0, 0, 1)); side /= np.linalg.norm(side)
            for pos, it in ((side * 1.0 + np.array((0, 0, 0.3)), 0.8), (dd + np.array((0, 0, 0.2)), 0.45)):
                pl.add_light(pv.Light(position=tuple(c0 + pos * 500), focal_point=tuple(c0), intensity=it), only_active=True)
            pl.add_mesh(out[name], color="#ece6d8", smooth_shading=False, specular=0.05, ambient=0.18, diffuse=0.9)
            pl.camera_position = [tuple(c0 + dd * L * 3.2), tuple(c0), (0, 0, 1)]; pl.camera.view_angle = 22
            pl.reset_camera_clipping_range()
            pl.add_text(f"relief-coupon-{name}  {vn}", font_size=10, color="black")
    pl.enable_anti_aliasing("ssaa"); p = ROOT / "images/desk-housing-v3/relief-coupons.png"; pl.screenshot(str(p)); pl.close(); print(p)


if __name__ == "__main__":
    main()
