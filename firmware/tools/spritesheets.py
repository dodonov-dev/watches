#!/usr/bin/env python3
"""Digit sprite sheets for the build and check tools: the sheet names in digitFont order and their files per cell
height (sim/public/assets, cut by sim/tools/make-digit-sprites.py). A canvas uses one height: spec/layout.h
SPRITE_CELL_H (sim render.ts spriteFile)."""
import json, os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(ROOT, 'sim', 'public', 'assets')
SHEETS = [
    'digits-steel', 'digits-brass-steampunk', 'digits-copper-gauge',
    'digits-forged-iron', 'digits-ivory-enamel', 'digits-carved-slate',
    'digits-amber-resin',
]  # digitFont 5..11 (sim render.ts SPRITE_SHEETS)
SPRITE_FONT = 5
CELL_HEIGHTS = (64, 100)   # every value SPRITE_CELL_H takes

def sheet_path(name, cell_h):
    return os.path.join(ASSETS, name + ('' if cell_h == 64 else '-%d' % cell_h) + '.png')

def load(name, cell_h):
    """(RGBA image, {cellW, cellH, widths}) of a sheet at a cell height."""
    path = sheet_path(name, cell_h)
    meta = json.load(open(path + '.json')); im = Image.open(path).convert('RGBA')
    if meta['cellH'] != cell_h or im.size != (meta['cellW'] * 10, cell_h):
        raise ValueError('%s: not a %d-row sheet (%dx%d, cell %dx%d)' % (path, cell_h, *im.size, meta['cellW'], meta['cellH']))
    return im, meta

def job_sprites(font, outdir):
    """The `sprites` entry of a render-ref.ts job for digitFont `font`: its sheet at every cell height, raw RGBA files
    in outdir (render-ref takes the one of its canvas); [] for a bitmap font."""
    i = int(round(font)) - SPRITE_FONT
    if i < 0: return []
    out = []
    for h in CELL_HEIGHTS:
        im, meta = load(SHEETS[i], h)
        rgba = os.path.join(str(outdir), '%s-%d.rgba' % (SHEETS[i], h))
        open(rgba, 'wb').write(im.tobytes())
        out.append({'i': i, 'w': im.width, 'h': im.height, 'cellW': meta['cellW'], 'cellH': meta['cellH'], 'widths': meta['widths'], 'rgbaFile': rgba})
    return out
