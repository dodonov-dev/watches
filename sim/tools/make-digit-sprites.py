#!/usr/bin/env python3
"""Cut an AI-generated digit sheet (digits 0-9 in one row on pure black) into
uniform-height sprite sheets with a proper alpha channel, one per cell height.

  python3 sim/tools/make-digit-sprites.py images/digits/digits-steel-sheet.png sim/public/assets/digits-steel.png 64 100

Cell heights: every value spec/layout.h SPRITE_CELL_H takes (a build picks one by its tube px scale). The first
goes to <out>, the others to <out stem>-<height>.png. Each is scaled from the source sheet (Lanczos).

Output: RGBA PNG, 10 glyphs left-to-right, every glyph padded to the same cell
width/height; a JSON sidecar (<out>.json) lists the cell size and per-glyph
ink width so the renderer can space them proportionally.
"""
import json, sys
from PIL import Image, ImageOps
import numpy as np

src, dst0, heights = sys.argv[1], sys.argv[2], [int(v) for v in sys.argv[3:]]
assert heights, 'cell heights: one or more'
im = np.asarray(Image.open(src).convert('RGB')).astype(np.float32) / 255.0
lum = im.max(axis=2)
ink = lum > 0.06
# column runs = glyphs (the sheet is one row, glyphs never touch)
cols = ink.any(axis=0)
runs, x = [], 0
while x < len(cols):
    if cols[x]:
        x0 = x
        while x < len(cols) and cols[x]: x += 1
        if x - x0 > 10: runs.append((x0, x))
    else: x += 1
assert len(runs) == 10, f'expected 10 glyphs, found {len(runs)}: {runs}'
rows = np.where(ink.any(axis=1))[0]; y0, y1 = rows[0], rows[-1] + 1
# alpha: opaque where the metal is, soft ramp at the antialiased rim
alpha = np.clip(lum / 0.18, 0, 1)
rgb = np.clip(im / np.maximum(alpha[..., None], 1e-3), 0, 1)  # un-premultiply the black matte
rgba = np.dstack([rgb, alpha])
for cell_h in heights:
    dst = dst0 if cell_h == heights[0] else '%s-%d.png' % (dst0[:-4] if dst0.endswith('.png') else dst0, cell_h)
    glyphs = []
    for (x0, x1) in runs:
        g = (rgba[y0:y1, x0:x1] * 255).round().astype(np.uint8)
        gi = Image.fromarray(g, 'RGBA')
        s = cell_h / gi.height
        gi = gi.resize((max(1, round(gi.width * s)), cell_h), Image.LANCZOS)
        glyphs.append(gi)
    cell_w = max(g.width for g in glyphs)
    sheet = Image.new('RGBA', (cell_w * 10, cell_h), (0, 0, 0, 0))
    for i, g in enumerate(glyphs):
        sheet.paste(g, (i * cell_w + (cell_w - g.width) // 2, 0))
    sheet.save(dst, optimize=True)
    json.dump({'cellW': cell_w, 'cellH': cell_h, 'widths': [g.width for g in glyphs]}, open(dst + '.json', 'w'))
    print(dst, sheet.size, [g.width for g in glyphs])
