#!/usr/bin/env python3
"""Stepped sequences, current render.cpp vs a saved reference (native C++, no board): fizz, residue, cross-frame memos.

  python3 firmware/tools/check_fizz_steps.py --reference /tmp/render-before.cpp [--fma] [--board lcd316 --res 320f]
                                             [--tiles] [-j N] [presets/x.json ...]

Each preset (default: presets/*.json and presets/physical/*.json, plus the built-in spring SCENES) runs the deterministic sequence of firmware/src/seq.h
(the board's `X` command: a fixed tilt script, both tubes and the fizz stepped, a frame every 2 steps) in a fresh
process per side, with esp_random as a fixed LCG, so the bubbles really move: births, springs, parked and popping
foam. Frames are compared by hash per tube (strip pixels, and the fizz state: render.cpp is #included by the driver,
its tubes' Fizz slots + spring clocks hashed), with the fizz counts; the first differing frame is reported. A rewrite
that changes struct Fizz or those fields on purpose: --pixels-only.
check_render_frames.py never steps the fizz (every bubble of a scene on one spot), so a fizz rewrite needs this too.
--fma builds both sides with -mfma -ffp-contract=fast: like the board, a * b + c fuses, so a rewrite that changes
which products feed which adds shows up (default -ffp-contract=off, like the other host checks). Still not the
board's code: confirm a fizz rewrite on the board with tools/check_board_steps.py.
--board / --res as check_board_render.py (default amoled191; lcd316 --res 320f = the wide LCD canvas); --tiles: the
current side renders through the tiled band loop (-DTILE_RENDER=1).
"""
import argparse, glob, json, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Built-in scenes on PRESET_DEFAULT (no preset spring's slug slides it dry in the sequence): a spring at the home end
# of a free slug (scattered births while the slug is away, SPRING_BACK decay after), vertical, remaining.
SCENES = {
    'spring, free slug': {'fizz': True, 'fizzSource': 1, 'freeLiquid': True, 'fizzCount': 64, 'fizzSourceX': 0},
    'spring, vertical': {'fizz': True, 'fizzSource': 1, 'vertical': True, 'fizzCount': 64, 'fizzSourceX': 0.5},
    'spring, remaining, big': {'fizz': True, 'fizzSource': 1, 'remaining': True, 'freeLiquid': True, 'fizzCount': 120,
                               'fizzSize': 6, 'fizzSizeVar': 0.6, 'fizzSourceX': 0.2},
}

HARNESS = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include RENDER_SRC   // the side's render.cpp itself: its tubes' fizz state is hashed below
#include "seq.h"
static uint16_t strip[2][PANEL_W * TUBE_HEIGHT_MAX];
static uint32_t fizzHash(int i) {   // the stepped state of one tube: live slots, spring clocks
#ifdef PIXELS_ONLY
  return 0;
#else
  const Tube &t = tubes[i];
  uint32_t h = seqHash((const uint16_t *)t.fizz, t.fizzN * (int)sizeof(Fizz) / 2);
  const float c[2] = {t.springScatter, t.springClock};
  return h ^ seqHash((const uint16_t *)c, sizeof c / 2) * 31u ^ (uint32_t)t.fizzN;
#endif
}
static bool setParam(Params &p, const char *name, const char *val) {   // main.cpp setParam
  for (const ParamField &f : PARAM_FIELDS) if (!strcmp(f.name, name)) {
    uint8_t *q = (uint8_t *)&p + f.off;
    switch (f.type) {
      case 'f': *(float *)q = atof(val); break;
      case 'i': *(int *)q = atoi(val); break;
      case 'b': *(bool *)q = !(val[0] == '0' || val[0] == 'f' || val[0] == 'F' || val[0] == 'n'); break;
      case 'c': *(uint32_t *)q = strtoul(val[0] == '#' ? val + 1 : val, nullptr, 16); break;
    }
    return true;
  }
  return false;
}
int main() {
  if (!render_init() || !physics_init()) return 3;
  Params design = PRESET_DEFAULT, p; TubeState h, m; uint32_t gen = 1;
  char line[256];
  while (fgets(line, sizeof line, stdin)) {
    line[strcspn(line, "\r\n")] = 0;
    char *eq = strchr(line, '='); if (!eq) return 4;
    *eq = 0; if (!setParam(design, line, eq + 1)) fprintf(stderr, "unknown param %s\n", line);
  }
  boardParams(design, p);
  uint16_t *const s[2] = {strip[0], strip[1]};
  const int words = tubeLayout(p).H * PANEL_W;
  seqRun(h, m, p, gen, s, [&](int frame, uint16_t *const *st) {
    int fh, sh, fm, sm; const int lh = fizzCounts(0, fh, sh), lm = fizzCounts(1, fm, sm);
    printf("SEQ %d %08x %08x fizz %d/%d %d/%d state %08x %08x\n", frame, seqHash(st[0], words), seqHash(st[1], words), lh, fh, lm, fm,
           fizzHash(0), fizzHash(1));
  });
  return 0;
}
'''

def fmt(v):
    return ('1' if v else '0') if isinstance(v, bool) else str(v)

def first_diff(a, b):
    """(frame line of a, of b) at the first differing frame, or None."""
    la, lb = a.splitlines(), b.splitlines()
    for x, y in zip(la, lb):
        if x != y: return x, y
    if len(la) != len(lb): return (f'{len(la)} lines', f'{len(lb)} lines')
    return None

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--reference', required=True, type=Path)
    ap.add_argument('--fma', action='store_true', help='-mfma -ffp-contract=fast on both sides (fused multiply-add like the board)')
    ap.add_argument('--board', default='amoled191', choices=('amoled191', 'lcd316'))
    ap.add_argument('--res', default='320', help='lcd316 canvas rows (320f = LCD_FILL)')
    ap.add_argument('--tiles', action='store_true', help='current side through the tiled band loop (-DTILE_RENDER=1)')
    ap.add_argument('--pixels-only', action='store_true', help='compare strips and counts, not the fizz state (struct Fizz changed on purpose)')
    ap.add_argument('-j', type=int, default=os.cpu_count() or 4)
    ap.add_argument('-v', action='store_true', help='print each preset\'s fizz counts: most per tube over the sequence and at the end')
    ap.add_argument('presets', nargs='*')
    a = ap.parse_args()
    reference = a.reference.resolve(strict=True)
    paths = a.presets or sorted(glob.glob(str(ROOT / 'presets/*.json')) + glob.glob(str(ROOT / 'presets/physical/*.json')))
    jobs = [] if a.presets else [(f'scene: {k}', ''.join(f'{n}={fmt(v)}\n' for n, v in o.items())) for k, o in SCENES.items()]
    for path in paths:
        params = json.load(open(path))
        if isinstance(params, dict) and 'tubeHeight' in params:
            jobs.append((path, ''.join(f'{k}={fmt(v)}\n' for k, v in params.items() if k != 'v')))
    lcd = a.board == 'lcd316'
    with tempfile.TemporaryDirectory(prefix='watches-steps-') as tmp:
        tmp = Path(tmp)
        (tmp / 'esp_heap_caps.h').write_text('#pragma once\n#include <cstdlib>\n#define MALLOC_CAP_SPIRAM 0\n'
                                             'inline void *heap_caps_malloc(size_t n, int) { return std::calloc(n, 1); }\n')
        (tmp / 'esp_random.h').write_text('#pragma once\n#include <cstdint>\n'   # a fixed LCG: the bubbles move, the same way on both sides
                                          'inline uint32_t esp_random() { static uint32_t s = 721; s = s * 1664525u + 1013904223u; return s; }\n')
        (tmp / 'h.cpp').write_text(HARNESS)
        fp = ['-mfma', '-ffp-contract=fast'] if a.fma else ['-ffp-contract=off']
        board = [f'-DBOARD_LCD316', f'-DRENDER_H={a.res.rstrip("f")}', f'-DLCD_FILL={int(a.res.endswith("f"))}'] if lcd else []
        sides = [('reference', reference), ('current', ROOT / 'firmware/src/render.cpp')]
        builds = [subprocess.Popen([os.environ.get('CXX', 'c++'), '-std=c++17', '-O2', *fp, *board,
                                    *(['-DTILE_RENDER=1'] if a.tiles and name == 'current' else []),
                                    *(['-DPIXELS_ONLY'] if a.pixels_only else []), f'-DRENDER_SRC="{src}"',
                                    '-I', str(tmp), '-I', str(ROOT / 'firmware/src'), '-I', str(ROOT / 'spec'),
                                    str(tmp / 'h.cpp'), str(ROOT / 'firmware/src/physics.cpp'), '-o', str(tmp / name)])
                  for name, src in sides]
        for (name, _), b in zip(sides, builds):
            if b.wait(): raise SystemExit(f'{name}: host build failed')
        def run(job):
            path, script = job
            outs = []
            for name, _ in sides:
                r = subprocess.run([str(tmp / name)], input=script.encode(), capture_output=True)
                if r.returncode: return path, f'{name} exited {r.returncode}: {r.stderr.decode()[-300:]}', None
                outs.append(r.stdout.decode())
            return path, None, (first_diff(*outs), outs[1].count('\n'), outs[1])
        bad = 0
        with ThreadPoolExecutor(a.j) as ex:
            for path, err, res in ex.map(run, jobs):
                name = path if path.startswith('scene: ') else os.path.relpath(path, ROOT)
                if err: bad += 1; print(f'{name:40s} ERROR {err}'); continue
                diff, frames, out = res
                if diff: bad += 1; print(f'{name:40s} DIFFERS\n  reference {diff[0]}\n  current   {diff[1]}')
                else: print(f'{name:40s} {frames} frames identical')
                if a.v:
                    rows = [l.split()[5:7] for l in out.splitlines()]   # 'live/foam' per tube
                    most = [max(int(r[t].split('/')[0]) for r in rows) for t in (0, 1)]
                    foam = [max(int(r[t].split('/')[1]) for r in rows) for t in (0, 1)]
                    print(f'  fizz live max h {most[0]} m {most[1]}, foam max h {foam[0]} m {foam[1]}, end {" ".join(rows[-1])}')
        tag = f'{a.board}{"@" + a.res if lcd else ""}{" fma" if a.fma else ""}{" tiles" if a.tiles else ""}'
        print(f'{tag}: {len(jobs) - bad} of {len(jobs)} presets identical over the sequence')
        sys.exit(1 if bad else 0)

if __name__ == '__main__': main()
