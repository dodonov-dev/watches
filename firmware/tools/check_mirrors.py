#!/usr/bin/env python3
"""Constants with one name in the firmware and the sim must have one value: exits 1 on drift.

  python3 firmware/tools/check_mirrors.py

Compares every UPPER_CASE #define / const in firmware/src + spec/layout.h with the same name in sim/src + spec/layout.ts,
after normalising (no f suffix, parens, spaces; case-folded hex). Expressions that differ only by a language idiom are
listed in BOARD_DEPENDENT and skipped. Runs without a build.
"""
import glob, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Spelled differently on purpose (board selection, float vs double rounding spelled out, font tables).
BOARD_DEPENDENT = {'BOARD_TAG', 'PANEL_W', 'PANEL_H', 'PX_SCALE', 'SPRITE_FONT', 'TUBE_HEIGHT_MAX', 'TUBE_HEIGHT_PX', 'FILM_FULL_PX_S'}

def norm(v):
    v = re.sub(r'\s+', '', v).lower()
    v = re.sub(r'(?<=\d)\.?0*f\b', '', v); v = re.sub(r'(?<=\.\d)f\b', '', v); v = re.sub(r'(\d\.\d*?)0*f?\b', lambda m: m[1].rstrip('.'), v)
    while v.startswith('(') and v.endswith(')') and v.count('(') == 1: v = v[1:-1]
    return v

def c_consts():
    out = {}
    for f in [*glob.glob(str(ROOT / 'firmware/src/*.cpp')), *glob.glob(str(ROOT / 'firmware/src/*.h')), str(ROOT / 'spec/layout.h')]:
        for l in open(f, errors='ignore'):
            m = re.match(r'\s*#define\s+([A-Z][A-Z_0-9]+)\s+([^/]+?)\s*(//.*)?$', l)
            if m: out.setdefault(m[1], m[2])
    return out

def ts_consts():
    out = {}
    for f in [*glob.glob(str(ROOT / 'sim/src/**/*.ts'), recursive=True), str(ROOT / 'spec/layout.ts')]:
        for l in open(f, errors='ignore'):
            if re.match(r'\s*(export )?const [A-Z]', l):
                code = l.split('//')[0]
                for m in re.finditer(r'\b([A-Z][A-Z_0-9]+)(?:\s*:\s*\w+)?\s*=\s*([^;,]+)', code): out.setdefault(m[1], m[2].strip())
    return out

def main():
    c, ts = c_consts(), ts_consts()
    both = sorted((set(c) & set(ts)) - BOARD_DEPENDENT)
    bad = [(k, c[k], ts[k]) for k in both if norm(c[k]) != norm(ts[k])]
    for k, a, b in bad: print(f'DRIFT {k}: firmware {a!r}, sim {b!r}')
    print(f'{len(both)} shared constants, {len(bad)} differ')
    sys.exit(1 if bad else 0)

if __name__ == '__main__': main()
