"""Schleiferbock logo, simplified for the glow-through stencil (pebble C: 14 x 8.83 logo box, 0.4 nozzle, seen only as
light through the skin): the goat's head alone (no arm, no knife), a bigger wheel / gear, bigger sparks.
Drawn in mm at stencil size, y down, as seen from outside. Every aperture is opened and closed with a MIN_W disc (nothing
narrower than a 0.4 nozzle's line, in the cut or in the plate), the separate cuts are kept GAP apart.
Writes schleiferbock-simple-{wheel,gear}.svg (paths: head, wheel, then the three sparks) and simple-preview.png.

    ~/.venvs/cad/bin/python images/schleiferbock-logo/simple.py
"""
import math, os, pathlib
import numpy as np
import manifold3d as m3
from svgpathtools import parse_path, Line

HERE = pathlib.Path(__file__).resolve().parent
BOX_W, BOX_H = 14.0, 8.83              # the logo box of the pebble C stencil
MIN_W = 0.5                            # narrowest aperture / plate strip inside one cut (0.4 nozzle)
GAP = 0.8                              # plate left between separate cuts: they must stay apart as light
SEG = 96
# wheel
WC, WR = (3.15, 5.68), 3.1             # centre, radius (the gear's tip radius)
GEAR_N, GEAR_ROOT, GEAR_TW = 8, 2.2, (1.2, 0.95)   # teeth, root radius, tooth width at the root / tip
# sparks: wedges fanning from the rim point at SPARK_AT (deg, y down: negative = up); the middle one starts further out
SPARK_AT = -40.0
SPARKS = ((-101, 1.5, 2.15), (-64, 2.1, 1.85), (-27, 1.3, 2.2))   # direction, inner end's distance from the rim point, length
SPARK_W = (0.55, 1.05)                              # width at the inner / outer end
# head, in profile, looking down-left at the wheel; the neck runs down to the box's bottom edge
SKULL = ("M 10.2 2.55 C 9.3 3.1, 8.3 4.0, 7.55 4.75 C 7.0 5.3, 7.1 6.1, 7.75 6.2 L 10.3 5.3 C 10.7 6.4, 10.6 7.8, 10.6 8.83 "
         "L 13.3 8.83 C 13.2 7.0, 12.9 5.2, 12.6 4.0 C 12.4 3.2, 11.9 2.7, 11.3 2.5 Z")
BEARD = "M 8.0 6.0 L 8.55 8.35 L 9.4 5.9 Z"
EAR = "M 11.5 2.6 C 12.4 2.3, 13.3 2.6, 14.0 3.3 C 13.2 3.6, 12.6 3.6, 12.0 3.4 Z"
HORN = ("M 10.15 2.6 C 9.9 1.2, 10.9 0.05, 12.2 0.05 C 13.3 0.05, 14.0 0.9, 13.95 2.0 C 13.5 1.3, 12.8 1.0, 12.2 1.05 "
        "C 11.6 1.1, 11.3 1.7, 11.4 2.6 Z")


def check(ok, msg):
    if not ok and os.environ.get("SB_DRAFT"):        # SB_DRAFT=1: draw it anyway (while designing)
        print("FAIL", msg)
    elif not ok:
        raise SystemExit("FAIL " + msg)


def cs(polys):
    return m3.CrossSection([np.asarray(p, float) for p in polys], m3.FillRule.NonZero)


def union(parts):
    return m3.CrossSection.batch_boolean(list(parts), m3.OpType.Add)


def circle(c, r):
    return m3.CrossSection.circle(r, SEG).translate(tuple(map(float, c)))


def clean(c, r=MIN_W / 2):
    """Opened then closed with a disc of radius r: no aperture and no notch narrower than 2 r, corners rounded r."""
    o = lambda x, d: x.offset(d, m3.JoinType.Round, 2.0, SEG)
    return o(o(o(o(c, -r), 2 * r), -r), 0.0).simplify(0.002)


def path(d, n=24):
    pts = []
    for seg in parse_path(d):
        k = 1 if isinstance(seg, Line) else n
        pts += [seg.point(i / k) for i in range(k)]
    return cs([[(z.real, z.imag) for z in pts]])


def head():
    return clean(union([path(SKULL), path(BEARD), path(EAR), path(HORN)]))


def wheel(gear):
    if not gear:
        return circle(WC, WR)
    (w0, w1), r0 = GEAR_TW, GEAR_ROOT - 0.3
    tooth = cs([[(r0, -w0 / 2), (WR, -w1 / 2), (WR, w1 / 2), (r0, w0 / 2)]])
    teeth = [tooth.rotate(SPARK_AT + 360 * (k + 0.5) / GEAR_N).translate(WC) for k in range(GEAR_N)]   # a gap at the sparks
    return clean(union(teeth + [circle(WC, GEAR_ROOT)]) ^ circle(WC, WR))


def sparks():
    a = math.radians(SPARK_AT)
    p0 = np.array(WC) + WR * np.array((math.cos(a), math.sin(a)))
    ri, ro = SPARK_W[0] / 2, SPARK_W[1] / 2
    out = []
    for ang, r0, L in SPARKS:
        u = np.array((math.cos(math.radians(ang)), math.sin(math.radians(ang))))
        out.append(m3.CrossSection.batch_hull([circle(p0 + u * (r0 + ri), ri), circle(p0 + u * (r0 + L - ro), ro)]))
    return out


def polys(c):
    return [np.asarray(p) for p in c.to_polygons()]


def gap(a, b):
    """Plate between cuts a and b: the largest d with a grown d/2 and b grown d/2 still apart."""
    lo, hi = 0.0, 6.0
    for _ in range(20):
        mid = (lo + hi) / 2
        g = lambda x: x.offset(mid / 2, m3.JoinType.Round, 2.0, SEG)
        lo, hi = (mid, hi) if (g(a) ^ g(b)).is_empty() else (lo, mid)
    return lo


def logo(gear):
    """[head, wheel, spark, spark, spark]; checked: inside the box, one outline each, GAP between them."""
    parts = [head(), wheel(gear)] + sparks()
    names = ["head", "gear" if gear else "wheel", "spark 1", "spark 2", "spark 3"]
    for n, p in zip(names, parts):
        (x0, y0, x1, y1) = p.bounds()
        check(p.num_contour() == 1, f"{n}: {p.num_contour()} outlines")
        check(x0 >= -1e-6 and y0 >= -1e-6 and x1 <= BOX_W + 1e-6 and y1 <= BOX_H + 1e-6, f"{n} leaves the box: {x0:.2f} {y0:.2f} {x1:.2f} {y1:.2f}")
    gaps = {f"{names[i]} / {names[j]}": gap(parts[i], parts[j]) for i in range(5) for j in range(i + 1, 5)}
    worst = min(gaps, key=gaps.get)
    check(gaps[worst] >= GAP - 1e-3, f"{worst}: {gaps[worst]:.2f} < {GAP}")
    return parts, gaps


def write_svg(path, parts):
    d = ["M " + " L ".join(f"{x:.3f} {y:.3f}" for x, y in polys(p)[0]) + " Z" for p in parts]
    body = "\n".join(f'    <path d="{x}"/>' for x in d)
    path.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{BOX_W}mm" height="{BOX_H}mm" viewBox="0 0 {BOX_W} {BOX_H}">
  <title>Schleiferbock, simplified (stencil)</title>
  <!-- simple.py. mm at stencil size, seen from outside. Separate cuts: head, wheel, then the three sparks; no islands -->
  <g fill="#000">
{body}
  </g>
</svg>
''')


def preview(logos, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import cv2
    px = 0.01
    fig, axs = plt.subplots(len(logos), 3, figsize=(21, 4.7 * len(logos)))
    for row, (name, parts) in enumerate(logos):
        ax = axs[row, 0]
        for p in parts:
            for P in polys(p):
                ax.fill(P[:, 0], P[:, 1], color="#111", lw=0)
        ax.plot([0, BOX_W, BOX_W, 0, 0], [0, 0, BOX_H, BOX_H, 0], color="#bbb", lw=0.6)
        ax.set_title(f"{name}: the cuts, seen from outside; grey: the {BOX_W:g} x {BOX_H:g} logo box (mm)", fontsize=10)
        img = np.zeros((int((BOX_H + 2) / px), int((BOX_W + 2) / px)), np.float32)
        for p in parts:
            for P in polys(p):
                cv2.fillPoly(img, [((P + 1) / px).round().astype(np.int32)], 1.0)
        for ax, sig in zip(axs[row, 1:], (0.3, 0.6)):
            ax.imshow(cv2.GaussianBlur(img, (0, 0), sig / px), cmap="magma", extent=(-1, BOX_W + 1, BOX_H + 1, -1), vmin=0, vmax=0.8)
            ax.set_title(f"{name}: glow from outside, blur {sig} mm ({'as the earlier preview' if sig == 0.3 else 'pessimistic'})", fontsize=10)
        for ax in axs[row]:
            ax.set_aspect("equal")
            ax.set_xlim(-1, BOX_W + 1)
            ax.set_ylim(BOX_H + 1, -1)
    fig.tight_layout()
    fig.savefig(path, dpi=100)


def main():
    out = []
    for name, gear in (("wheel", False), ("gear", True)):
        parts, gaps = logo(gear)
        write_svg(HERE / f"schleiferbock-simple-{name}.svg", parts)
        b = union(parts).bounds()
        print(f"{name}: {b[2] - b[0]:.2f} x {b[3] - b[1]:.2f}; gaps " + ", ".join(f"{k} {v:.2f}" for k, v in sorted(gaps.items(), key=lambda t: t[1])[:4]))
        out.append((name, parts))
    preview(out, HERE / "simple-preview.png")


if __name__ == "__main__":
    main()
