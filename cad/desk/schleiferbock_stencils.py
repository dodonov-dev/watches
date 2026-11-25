"""Schleiferbock logo stencils for the pebble (round C) glow-through pocket: the E+H stencil's plate (smooth.stencil_block,
16.00 x 10.83 pocket, 1.60 thick, same clearances, sloped sides, bed face = the face against the skin, mirrored) with the
Schleiferbock logo (wheel, gear) as apertures instead of the letters; two stencils in a column as the E+H set.

Designed for a 0.2 nozzle: apertures and bridges down to MIN_W (0.25). The logo body is kept as drawn (sharp tips print
under-cut; trim by hand). The sparks are redrawn as slim wedges (SPARK_W_IN -> SPARK_W_OUT wide) on the SVG's spark axes,
their inner ends moved out until every bridge is >= MIN_W. Features a 0.4 nozzle would lose (narrower than 0.5) are listed.

    ~/.venvs/cad/bin/python cad/desk/schleiferbock_stencils.py
"""
import sys, math, pathlib
import numpy as np
import manifold3d as m3
from svgpathtools import parse_path, Line
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import housing as hw
import smooth as sm
from build123d import Plane, Pos, Polygon, Compound, Face, extrude, import_step, GeomType

LOGO_DIR = ROOT / "images" / "schleiferbock-logo"
LOGOS = (("wheel", LOGO_DIR / "schleiferbock-wheel.svg"), ("gear", LOGO_DIR / "schleiferbock-gear.svg"))
BOX_W = 14.0                                   # the E+H letters' area on the pebble C stencil
BOX_H = hw.LETTERS_ASPECT * BOX_W              # 8.83
PW, PH = BOX_W + 2 * sm.STENCIL_MARGIN, BOX_H + 2 * sm.STENCIL_MARGIN
K = math.tan(math.radians(sm.LOGO_FLARE_DEG))
BED_W, BED_H = PW - 2 * sm.STENCIL_CLR, PH - sm.STENCIL_CLR - sm.STENCIL_CLR_TOP
BED_R, BED_DY = sm.STENCIL_R - sm.STENCIL_CLR, (sm.STENCIL_CLR - sm.STENCIL_CLR_TOP) / 2
MIN_W = 0.25                                   # aperture / bridge width wanted (0.2 nozzle)
W_04 = 0.50                                    # ... what a 0.4 nozzle would want: narrower features are flagged
SPARK_W_IN, SPARK_W_OUT = 0.30, 0.40           # spark wedges: width at the inner (wheel) end and the outer end
SAMPLE = 0.02                                  # mm, curve sampling
SPARKS = 3                                     # the last SPARKS paths in each SVG are the sparks (separate cuts)
SEG = 96                                       # circular segments of round offsets
OUT_STEP = sm.OUT_ROOT / "logo-stencils-pebble-schleiferbock.step"
OUT_STL = HERE / "to-print" / "logo-stencils-pebble-schleiferbock.stl"
OUT_TXT = sm.OUT_ROOT / "logo-stencils-pebble-schleiferbock.txt"
OUT_PNG = LOGO_DIR / "stencil-pebble-preview.png"
REF_STEP = sm.OUT_ROOT / "logo-stencils-pebble.step"
check = hw.check
T = import_step(str(REF_STEP)).bounding_box().size.Z   # pebble C stencil thickness, 1.6036 ("1.60": the pocket less 0.1)
EAR_W = 0.30                                   # the ear bar (SVG: ~0.1 at its root, 0.39 at its end): a stroke this wide along it
EAR = ((103.565, 19.315), (117.35, 32.555))    # its centre line, SVG units: root (mid of 105.06 21.16 / 102.07 17.47), end
# named places (SVG units) to say where a thin piece is, apertures and bridges
ANCHORS = {"aperture": {"ear bar": (110.5, 26), "knife handle": (55, 59), "beard spike": (83.5, 41), "horn tip": (114, 0),
                        "snout tip": (77, 22.5), "body's bottom corner": (108, 70), "knife blade": (42, 52), "fist": (59, 63)},
           "bridge": {"horn root": (89, 12), "mouth notch": (78.5, 25.5), "throat notch": (86.5, 43), "ear/head crotch": (106, 26),
                      "knife tip / wheel": (35, 48), "hand / handle": (63, 58), "fist / handle": (57, 60)}}


def cs(polys):
    return m3.CrossSection([np.asarray(p, float) for p in polys], m3.FillRule.NonZero)


def union(parts):
    return m3.CrossSection.batch_boolean(list(parts), m3.OpType.Add)


def circle(c, r):
    return m3.CrossSection.circle(r, SEG).translate(tuple(map(float, c)))


def svg_paths(path):
    """Each <path> as a list of closed polylines in SVG units (y down)."""
    out = []
    for el in ET.parse(path).getroot().iter("{http://www.w3.org/2000/svg}path"):
        rings, cur = [], []
        for seg in parse_path(el.get("d")):
            if cur and abs(seg.start - cur[-1]) > 1e-6:
                rings.append(cur)
                cur = []
            n = 1 if isinstance(seg, Line) else max(8, int(seg.length() * 0.11 / SAMPLE))
            if not cur:
                cur.append(seg.start)
            cur += [seg.point(i / n) for i in range(1, n + 1)]
        rings.append(cur)
        out.append([[(z.real, z.imag) for z in r] for r in rings])
    return out


def polys(c):
    return [np.asarray(p) for p in c.to_polygons()]


def min_dist(a, b):
    """Smallest distance between the outlines of CrossSections a and b (vertices against segments, both ways)."""
    def vs(P, Q):
        best = np.inf
        for q in Q:
            s0, s1 = q, np.roll(q, -1, axis=0)
            e = s1 - s0
            ee = np.maximum((e * e).sum(1), 1e-18)
            for p in P:
                d = p[:, None, :] - s0[None]
                t = np.clip((d * e[None]).sum(2) / ee[None], 0, 1)
                best = min(best, np.sqrt(((d - t[..., None] * e[None]) ** 2).sum(2)).min())
        return best
    A, B = polys(a), polys(b)
    return min(vs(A, B), vs(B, A))


def opening(c, r):
    return c.offset(-r, m3.JoinType.Round, 2.0, SEG).offset(r, m3.JoinType.Round, 2.0, SEG)


def inscribed_w(c):
    lo, hi = 0.0, 2.0
    for _ in range(26):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if not c.offset(-mid, m3.JoinType.Round, 2.0, SEG).is_empty() else (lo, mid)
    return 2 * lo


class Logo:
    def __init__(self, name, path):
        self.name = name
        paths = svg_paths(path)
        pts = np.vstack([np.array(r) for p in paths for r in p])
        (x0, y0), (x1, y1) = pts.min(0), pts.max(0)
        # uniform scale to the largest size inside BOX_W x BOX_H, bounding box (sparks included) centred on (0, 0) as the
        # E+H letters, y up, mirrored in x: the bed face meets the skin, seen from outside the logo reads the right way
        self.s = s = min(BOX_W / (x1 - x0), BOX_H / (y1 - y0))
        self.c = cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.size = ((x1 - x0) * s, (y1 - y0) * s)
        self.paths = paths
        parts = [cs([self.tr(r) for r in p]) for p in paths]
        a, b = (np.array(p_) for p_ in self.tr(EAR))
        u = (b - a) / np.hypot(*(b - a))
        self.ear = m3.CrossSection.batch_hull([circle(a, EAR_W / 2), circle(b - u * EAR_W / 2, EAR_W / 2)])
        self.body = union(parts[:-SPARKS] + [self.ear])
        self.sparks_svg = parts[-SPARKS:]
        self.sparks, self.spark_d = self.make_sparks()
        self.ap = union([self.body] + self.sparks)

    def tr(self, r):
        cx, cy = self.c
        return [(-(x - cx) * self.s, -(y - cy) * self.s) for x, y in r]

    def back(self, X, Y):
        return self.c[0] - X / self.s, self.c[1] - Y / self.s

    def make_sparks(self):
        """Slim wedges on the SVG sparks' axes (kite: inner tip, side, outer tip, side): SPARK_W_IN wide at the inner end,
        SPARK_W_OUT at the outer end (that end at the kite's outer tip); the inner ends moved out together by d until
        every bridge (spark-spark, spark-body) is >= MIN_W."""
        axes = []
        for p in self.paths[-SPARKS:]:
            q = np.array(self.tr(p[0]))
            check(len(q) == 4 or (len(q) == 5 and np.allclose(q[0], q[-1])), f"{self.name}: a spark is not a kite")
            a, b = q[0], q[2]
            u = (b - a) / np.hypot(*(b - a))
            axes.append((a, b, u))
        ri, ro = SPARK_W_IN / 2, SPARK_W_OUT / 2

        def wedges(d):
            return [m3.CrossSection.batch_hull([circle(a + u * (d + ri), ri), circle(b - u * ro, ro)]) for a, b, u in axes]

        def gap(d):
            w = wedges(d)
            return min([min_dist(x, self.body) for x in w] + [min_dist(w[i], w[j]) for i in range(len(w)) for j in range(i + 1, len(w))])
        lo, hi = 0.0, 0.6
        check(gap(hi) >= MIN_W, f"{self.name}: sparks can't clear {MIN_W}")
        if gap(lo) >= MIN_W:
            return wedges(lo), lo
        else:
            for _ in range(24):
                mid = (lo + hi) / 2
                lo, hi = (lo, mid) if gap(mid) >= MIN_W else (mid, hi)
        return wedges(hi), hi

    def thin(self, region, w, kind):
        """Parts of region a disc of diameter w can't reach, grouped by the named place they lie at:
        {name: (pieces, area, longest, widest inscribed)}; corner slivers (< 0.25 r^2, a right angle's is 0.21 r^2) skipped."""
        r = w / 2 * 0.98
        out = {}
        for p in (region - opening(region, r)).decompose():
            a = p.area()
            if a < 0.25 * r * r:
                continue
            P = np.vstack(polys(p))
            ext = P.max(0) - P.min(0)
            X, Y = P.mean(0)
            q = np.array(self.back(X, Y))
            if min(min_dist(p, s_) for s_ in self.sparks) < 0.05:
                nm = "sparks"
            elif self.name == "gear" and 12 <= np.hypot(*(q - (16, 52))) <= 21:
                nm = "gear teeth"
            else:
                A = ANCHORS[kind]
                nm = min(A, key=lambda k: np.hypot(*(q - A[k])))
            n0, a0, l0, w0 = out.get(nm, (0, 0, 0, 0))
            out[nm] = (n0 + 1, a0 + a, max(l0, float(np.hypot(*ext))), max(w0, inscribed_w(p)))
        return out


def bed_outline():
    return m3.CrossSection.square((BED_W - 2 * BED_R, BED_H - 2 * BED_R), True) \
        .offset(BED_R, m3.JoinType.Round, 2.0, 256).translate((0, BED_DY))


def stencil(lg):
    st = sm.stencil_block(Plane.XY, PW, PH, T)
    holes = [Polygon(*[tuple(v) for v in P], align=None) for P in polys(lg.ap.simplify(0.001))]
    for h in holes:
        st = st - Pos(0, 0, -1) * extrude(h, T + 2)
    return st, len(holes)


def bed_face(st, z=0.0):
    fs = [f for f in st.faces() if f.geom_type == GeomType.PLANE and abs(f.center().Z - z) < 1e-6 and abs(abs(f.normal_at().Z) - 1) < 1e-6]
    check(len(fs) == 1, f"{len(fs)} faces at z {z}")
    return fs[0]


def plate_volume(st):
    """The solid's volume with its (straight) apertures filled: + T x the bed face's hole areas."""
    return st.volume + T * sum(Face(w).area for w in bed_face(st).inner_wires())


def main():
    logos = [Logo(n, p) for n, p in LOGOS]
    check(all(lg.tr([(16, 52)])[0][0] > 0 for lg in logos), "mirroring: the wheel should lie at +x on the bed (left from outside)")
    bed = bed_outline()
    ref = sorted(import_step(str(REF_STEP)).solids(), key=lambda s_: -s_.bounding_box().center().Y)
    v_want = T * (BED_W + K * T) * BED_H - T * (4 - math.pi) * BED_R ** 2
    out, R, data = [], [], []
    for i, lg in enumerate(logos):
        st, n_holes = stencil(lg)
        st = Pos(0, -i * (PH + 4), 0) * st              # the E+H set's column
        # closed, one solid (an island would be a second one), apertures as many as the logo's pieces, no holes in them
        comps = lg.ap.decompose()
        check(st.is_valid and len(st.solids()) == 1, f"{lg.name}: {len(st.solids())} solids")
        check(all(c.num_contour() == 1 for c in comps), f"{lg.name}: an aperture with a hole (an island)")
        for z in (0.0, T):
            check(len(bed_face(st, z).inner_wires()) == len(comps) == n_holes, f"{lg.name}: apertures at z {z}")
        # the plate: E+H stencil i's bounding box and filled volume
        bb, rb = st.bounding_box(), ref[i].bounding_box()
        vp, vr = plate_volume(st), plate_volume(ref[i])
        dbb = max(abs(a - b) for a, b in zip((*bb.min, *bb.max), (*rb.min, *rb.max)))
        check(dbb < 1e-3 and abs(vp - vr) < 1e-3 and abs(vp - v_want) < 1e-3, f"{lg.name}: plate {dbb:.4f} bbox, {vp:.4f} vs {vr:.4f} / {v_want:.4f}")
        mat = bed - lg.ap
        gaps = {"spark-spark": min(min_dist(lg.sparks[a], lg.sparks[b]) for a in range(SPARKS) for b in range(a + 1, SPARKS)),
                "spark-body": min(min_dist(x, lg.body) for x in lg.sparks), "logo-plate edge": min_dist(lg.ap, bed)}
        D = dict(lg=lg, st=st, bb=bb, vp=vp, vr=vr, dbb=dbb, gaps=gaps, comps=len(comps),
                 spark_w=[inscribed_w(x) for x in lg.sparks],
                 thin={(k, w): lg.thin(reg, w, k) for k, reg in (("aperture", lg.ap), ("bridge", mat)) for w in (MIN_W, W_04)})
        data.append(D)
        out.append(st)
    c = Compound(out)
    stp = sm.write_step(c, OUT_STEP)
    sm.write_stl(c, OUT_STL)
    ms = sm.check_stl(c, OUT_STL, bodies=len(out))
    lines = [f"LOGO STENCILS Schleiferbock, pebble C: the E+H stencil's plate (logo-stencils-pebble.*: pocket {PW:.2f} x {PH:.2f} "
             f"R{sm.STENCIL_R:g}, bed face {BED_W:.2f} x {BED_H:.2f} R{BED_R:g}, sides {sm.LOGO_FLARE_DEG:g} deg, {T:.4f} thick, "
             f"bed face = the face against the skin, logo mirrored); first row wheel, second gear (as the E+H set: 1st, 2nd row)",
             f"designed for a 0.2 nozzle: apertures and bridges >= {MIN_W} except sharp tips (under-cut: trim by hand); body as drawn but the ear bar (a {EAR_W} stroke along it, its root was ~0.1); "
             f"sparks redrawn as wedges {SPARK_W_IN} -> {SPARK_W_OUT} wide on the SVG sparks' axes, outer ends at the SVG tips"]
    for D in data:
        lg = D["lg"]
        lines.append(f"{lg.name}: logo {lg.size[0]:.2f} x {lg.size[1]:.2f} ({lg.s * 1000:.2f} um/unit), {D['comps']} apertures, one "
                     f"solid; plate bbox = E+H's within {D['dbb']:.1e}, filled volume {D['vp']:.4f} (E+H {D['vr']:.4f}); sparks' inner "
                     f"ends {lg.spark_d:.2f} out along their axes, widest {', '.join(f'{w:.2f}' for w in D['spark_w'])}; gaps " +
                     ", ".join(f"{k} {v:.3f}" for k, v in D["gaps"].items()))
        for (k, w), th in D["thin"].items():
            lines.append(f"  {k}s narrower than {w:g} ({'0.2' if w == MIN_W else '0.4'} nozzle): " + ("none" if not th else "; ".join(
                f"{nm} (x{n}, {a:.3f} mm2, {L:.2f} long, up to {wi:.2f} wide)" for nm, (n, a, L, wi) in sorted(th.items(), key=lambda t: -t[1][1]))))
    lines += sm.file_lines({"logo-stencils-pebble-schleiferbock": (stp, ms)})
    OUT_TXT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)
    preview(data, bed)


def preview(data, bed):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import cv2
    fig, axs = plt.subplots(2, 3, figsize=(18, 8.6))
    px = 0.01
    for row, D in enumerate(data):
        lg, st = D["lg"], D["st"]

        def draw(ax, z, mirror):
            sg = -1 if mirror else 1
            f = bed_face(st, z)
            for e in f.edges():
                P = np.array([(v.X, v.Y) for v in (e.position_at(t) for t in np.linspace(0, 1, 40))])
                ax.plot(sg * P[:, 0], P[:, 1] + row * (PH + 4), "k", lw=0.7)
            for P in polys(lg.ap):
                ax.fill(sg * P[:, 0], P[:, 1], color="#ffd24a", lw=0)
            ax.set_aspect("equal")
            ax.set_xlim(-10, 10)
            ax.set_ylim(-6, 6)
        ax = axs[row, 0]
        draw(ax, 0.0, True)
        for k, col in (("aperture", "#e0301e"), ("bridge", "#1e6be0")):     # what a 0.4 nozzle would lose
            r = W_04 / 2 * 0.98
            reg = lg.ap if k == "aperture" else bed - lg.ap
            for p in (reg - opening(reg, r)).decompose():
                if p.area() >= 0.25 * r * r:
                    for P in polys(p):
                        ax.fill(-P[:, 0], P[:, 1], color=col, lw=0)
        ax.set_title(f"{lg.name}: bed side (against the skin), seen from below\nred / blue: aperture / bridge narrower than 0.5 "
                     f"(lost with a 0.4 nozzle)", fontsize=9)
        ax = axs[row, 1]
        draw(ax, T, False)
        ax.set_title(f"{lg.name}: top side (as printed, faces the LED), seen from above; plate {T:.2f} thick", fontsize=9)
        # from outside: apertures (seen from outside = x mirrored back) blurred as by the 1.3 skin
        W, H = int(20 / px), int(12 / px)
        img = np.zeros((H, W), np.float32)
        for P in polys(lg.ap):
            q = np.c_[(-P[:, 0] + 10) / px, (6 - P[:, 1]) / px].round().astype(np.int32)
            cv2.fillPoly(img, [q], 1.0)
        glow = cv2.GaussianBlur(img, (0, 0), 0.3 / px)
        ax = axs[row, 2]
        ax.imshow(glow, cmap="magma", extent=(-10, 10, -6, 6), vmin=0, vmax=0.7)
        for P in polys(union([cs([lg.tr(r) for r in p]) for p in lg.paths])):   # the SVG as drawn, for comparison
            ax.plot(-np.r_[P[:, 0], P[:1, 0]], np.r_[P[:, 1], P[:1, 1]], color="#7fd3ff", lw=0.5)
        ax.set_title(f"{lg.name}: from outside, glow (blur 0.3 mm for the skin); blue line: the SVG as drawn", fontsize=9)
        ax.set_xlim(-10, 10)
        ax.set_ylim(-6, 6)
    fig.suptitle(f"Schleiferbock stencils, pebble C pocket: logo {data[0]['lg'].size[0]:.2f} / {data[1]['lg'].size[0]:.2f} x "
                 f"{data[0]['lg'].size[1]:.2f} mm, plate as the E+H stencil (mm)")
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=110)


if __name__ == "__main__":
    main()
