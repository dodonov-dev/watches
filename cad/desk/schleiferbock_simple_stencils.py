"""Simplified Schleiferbock stencils for the pebble (round C) glow-through pocket: the plate and the two types of
schleiferbock_stencils.py ("through": the whole logo cut through; "sparks": only the sparks through, the head and wheel a
pocket from the top down to a FLOOR on the bed face), with the simplified logo of images/schleiferbock-logo/simple.py
(goat's head, bigger wheel / gear, bigger sparks; drawn in mm at stencil size for a 0.4 nozzle, used as drawn).
The SVGs are read as they are: 1 unit = 1 mm, the last three paths are the sparks. One STL per stencil.

    ~/.venvs/cad/bin/python images/schleiferbock-logo/simple.py && ~/.venvs/cad/bin/python cad/desk/schleiferbock_simple_stencils.py
"""
import numpy as np
import schleiferbock_stencils as sb
from schleiferbock_stencils import sm, check, cs, union, polys, min_dist, inscribed_w, stencil, bed_face, T, FLOOR, SPARKS, PW, PH
from build123d import Pos

LOGOS = tuple((n, sb.LOGO_DIR / f"schleiferbock-simple-{n}.svg") for n in ("wheel", "gear"))
MIN_W = 0.5                                    # narrowest cut / plate strip (0.4 nozzle)
OUT_STL = sb.HERE / "to-print" / "logo-stencil-schleiferbock-simple-{name}-{type}.stl"
OUT_TXT = sm.OUT_ROOT / "logo-stencils-pebble-schleiferbock-simple.txt"
OUT_PNG = sb.LOGO_DIR / "stencil-pebble-simple-preview.png"


class Logo:
    def __init__(self, name, path):
        self.name = name
        paths = sb.svg_paths(path)
        pts = np.vstack([np.array(r) for p in paths for r in p])
        (x0, y0), (x1, y1) = pts.min(0), pts.max(0)
        self.size = (x1 - x0, y1 - y0)
        check(self.size[0] <= sb.BOX_W + 1e-6 and self.size[1] <= sb.BOX_H + 1e-6, f"{name}: {self.size} outside the logo box")
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        # bounding box centred on (0, 0), y up, mirrored in x: the bed face meets the skin, from outside it reads the right way
        parts = [cs([[(-(x - cx), -(y - cy)) for x, y in r] for r in p]) for p in paths]
        self.parts, self.sparks = parts[:-SPARKS], parts[-SPARKS:]
        self.body = union(self.parts)
        self.ap = union(parts)


def main():
    logos = [Logo(n, p) for n, p in LOGOS]
    bed = sb.bed_outline()
    lines = [f"LOGO STENCILS Schleiferbock simplified, pebble C: the E+H stencil's plate (pocket {PW:.2f} x {PH:.2f}, {T:.4f} thick, bed face "
             f"= the face against the skin, logo mirrored); goat's head, wheel / gear, three sparks, drawn for a 0.4 nozzle",
             f"two types: through (the logo cut through); sparks (only the sparks through, head and wheel a pocket from the top face, "
             f"the LED side, to a {FLOOR:g} floor on the bed face: they glow dimmer)"]
    data = []
    for lg in logos:
        cuts = lg.parts + lg.sparks
        check(lg.parts[1].bounds()[0] > 0, f"{lg.name}: mirroring, the wheel should lie at +x on the bed (left from outside)")
        gaps = [min_dist(cuts[a], cuts[b]) for a in range(len(cuts)) for b in range(a + 1, len(cuts))] + [min_dist(lg.ap, bed)]
        check(min(gaps) >= MIN_W, f"{lg.name}: {min(gaps):.2f} of plate between cuts / to the edge")
        lines.append(f"{lg.name}: logo {lg.size[0]:.2f} x {lg.size[1]:.2f}, {len(cuts)} cuts; sparks "
                     f"{', '.join(f'{inscribed_w(c):.2f}' for c in lg.sparks)} wide; least plate between cuts {min(gaps[:-1]):.2f}, "
                     f"to the plate's edge {gaps[-1]:.2f}")
        for ty, floor in (("through", None), ("sparks", FLOOR)):
            st, n = stencil(lg, floor)
            holes = len(bed_face(st, 0.0).inner_wires())
            check(st.is_valid and len(st.solids()) == 1 and holes == n == (len(cuts) if floor is None else SPARKS), f"{lg.name} {ty}: {holes} holes")
            f = sb.pathlib.Path(str(OUT_STL).format(name=lg.name, type=ty))
            sm.write_stl(st, f)
            m = sm.check_stl(st, f, bodies=1)
            lines.append(f"  {f.name:<52} STL closed, {m['tris']} triangles, volume {st.volume:.2f} mm3, {m['kb']:.0f} kB")
        data.append(lg)
    OUT_TXT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)
    preview(data, bed)


def preview(logos, bed):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import cv2
    px, DIM, SIG = 0.01, 0.35, 0.3             # the body's glow through FLOOR and the skin's blur: illustrative guesses
    fig, axs = plt.subplots(len(logos), 3, figsize=(20, 4.4 * len(logos)))
    for row, lg in enumerate(logos):
        ax = axs[row, 0]
        for P in polys(bed):
            ax.fill(P[:, 0], P[:, 1], color="#ddd", lw=0)
        for P in polys(lg.ap):
            ax.fill(P[:, 0], P[:, 1], color="#ffd24a", ec="k", lw=0.5)
        ax.set_title(f"{lg.name}: as printed, seen from above (top = LED side; the bed face goes against the skin)", fontsize=9)
        ax.set_aspect("equal")
        img = np.zeros((int(12 / px), int(20 / px)), np.float32)
        pix = lambda P: [np.c_[(-P[:, 0] + 10) / px, (6 - P[:, 1]) / px].round().astype(np.int32)]   # from outside: x mirrored back
        for P in polys(lg.ap):
            cv2.fillPoly(img, pix(P), 1.0)
        dim = img * DIM
        for P in polys(union(lg.sparks)):
            cv2.fillPoly(dim, pix(P), 1.0)
        for ax, im, t in ((axs[row, 1], img, "through type"), (axs[row, 2], dim, f"sparks type (body x{DIM} through the {FLOOR:g} floor: a guess)")):
            ax.imshow(cv2.GaussianBlur(im, (0, 0), SIG / px), cmap="magma", extent=(-10, 10, -6, 6), vmin=0, vmax=0.8)
            ax.set_title(f"{lg.name}, {t}: glow from outside, blur {SIG}", fontsize=9)
        for ax in axs[row]:
            ax.set_xlim(-10, 10)
            ax.set_ylim(-6, 6)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=100)


if __name__ == "__main__":
    main()
