#!/usr/bin/env python3
"""E+H mark from eh-logo.svg (Wikimedia, en: File:Endress+Hauser_logo.svg) → eh_logo.json for the housing's logo cut.

The SVG's blue parallelogram is path25267; the letters inside it (cut through the wall) are path25269 (E with the
slash) and path25271 (H). The output has the outline and the letter polygons in units of the outline's width
(x 0..1, y up), so housing.py scales them to LOGO_W. It also writes eh_logo_check.png.
Run: ~/.venvs/cad/bin/python cad/desk/trace_logo.py
"""
import json, pathlib
from svgelements import SVG, Path, Move, Close

HERE = pathlib.Path(__file__).parent
OUTLINE_ID, LETTER_IDS = "path25267", ("path25269", "path25271")
STEP = 0.02                  # sampling step along curves, SVG units (the mark is ~14 units wide)


def rings(path):
    """Closed polylines of a path (one per subpath), curves sampled every STEP."""
    out, cur = [], []
    for seg in path:
        if isinstance(seg, Move):
            if len(cur) > 2:
                out.append(cur)
            cur = [(seg.end.x, seg.end.y)]
            continue
        if isinstance(seg, Close):
            if len(cur) > 2:
                out.append(cur)
            cur = []
            continue
        n = max(1, int(seg.length() / STEP)) if type(seg).__name__ in ("Arc", "CubicBezier", "QuadraticBezier") else 1
        for i in range(1, n + 1):
            p = seg.point(i / n)
            cur.append((p.x, p.y))
    if len(cur) > 2:
        out.append(cur)
    # drop the duplicated closing point
    return [r[:-1] if r[0] == r[-1] else r for r in out]


svg = SVG.parse(str(HERE / "eh-logo.svg"))
els = {e.id: e for e in svg.elements() if isinstance(e, Path)}
outline = rings(els[OUTLINE_ID])
assert len(outline) == 1, f"outline has {len(outline)} rings"
letters = []
for i in LETTER_IDS:
    r = rings(els[i])
    assert len(r) == 1, f"{i} has {len(r)} rings: a hole would drop an island out of the cut"
    letters += r

xs = [x for x, _ in outline[0]]
ys = [y for _, y in outline[0]]
x0, w, ymax = min(xs), max(xs) - min(xs), max(ys)
norm = lambda ring: [[(x - x0) / w, (ymax - y) / w] for x, y in ring]   # SVG y down → up
json.dump({"source": "eh-logo.svg", "outline": norm(outline[0]), "letters": [norm(r) for r in letters],
           "aspect": (max(ys) - min(ys)) / w}, open(HERE / "eh_logo.json", "w"))

from PIL import Image, ImageDraw
S = 60
im = Image.new("RGB", (int(w * S) + 20, int((max(ys) - min(ys)) * S) + 20), "white")
dr = ImageDraw.Draw(im)
tr = lambda ring: [((x - x0) * S + 10, (y - min(ys)) * S + 10) for x, y in ring]
dr.polygon(tr(outline[0]), fill=(0, 150, 230))
for r in letters:
    dr.polygon(tr(r), fill="white", outline=(0, 120, 0))
im.save(HERE / "eh_logo_check.png")
print(f"outline {len(outline[0])} pts, letters {[len(r) for r in letters]} pts, aspect {(max(ys) - min(ys)) / w:.3f}")
