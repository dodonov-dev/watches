#!/usr/bin/env python3
"""Sim vs firmware render parity on any board / canvas, on the host (no device): every preset, one pinned scene.

  python3 firmware/tools/check_board_render.py [--board lcd316] [--res 320] [--tiles] [--tolerance 12] [presets/x.json ...]

Board: --board / --res (320f: LCD_FILL), else $LW_BOARD / $LW_RES, else lcd316 at 320 (amoled191 works too). The firmware side is render.cpp + physics.cpp built for that canvas with the ESP stubs,
params scaled by physics.h boardParams; the sim side is tools/render-ref.ts with LW_BOARD / LW_RES (params.ts
boardParams). Presets default to presets/*.json and presets/physical/*.json (design px). Fizz off (random). Prints
per preset the pixels off and those beyond the tolerance (RGB888 steps); exits 1 if any preset has one.
--tiles: the firmware side renders through the tiled band loop (-DTILE_RENDER=1, host sink = memcpy) as the LCD board
does; without it the host takes the strip path.
"""
import argparse, glob, json, os, shutil, struct, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / 'sim'
SHEETS = ['digits-steel', 'digits-brass-steampunk', 'digits-copper-gauge', 'digits-forged-iron',
          'digits-ivory-enamel', 'digits-carved-slate', 'digits-amber-resin']
STATE = {'hours': {'fillTarget': 0.42, 'light': 20.0}, 'minutes': {'fillTarget': 0.71, 'light': 20.0}}

HARNESS = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "render.h"
#include "layout.h"
static uint16_t strip[PANEL_W * TUBE_HEIGHT_MAX], canvas[PANEL_W * PANEL_H];
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
  Params design = PRESET_DEFAULT, p; TubeState st[2]; uint32_t gen = 1;
  for (int i = 0; i < 2; i++) { st[i].trace = traceBuf(i); st[i].traceWet = traceWetBuf(i); }
  char line[256];
  while (fgets(line, sizeof line, stdin)) {
    line[strcspn(line, "\r\n")] = 0;
    if (line[0] == 'P') { char *eq = strchr(line + 2, '='); if (!eq) return 4; *eq = 0; if (!setParam(design, line + 2, eq + 1)) fprintf(stderr, "unknown param %s\n", line + 2); }
    else if (line[0] == 'S') { int i; float f, l; sscanf(line + 2, "%d %f %f", &i, &f, &l); st[i] = TubeState(); st[i].trace = traceBuf(i); st[i].traceWet = traceWetBuf(i); st[i].fillTarget = f; st[i].light = l; }
    else if (line[0] == 'R') {
      boardParams(design, p); gen++;
      memset(canvas, 0, sizeof canvas);
      const TubeLayout lay = tubeLayout(p);
      for (int i = 0; i < 2; i++) {
        renderTube(i, st[i], p, gen, strip);
        const int y0 = i ? lay.yM : lay.yH;
        for (int k = 0; k < lay.H * PANEL_W; k++) canvas[y0 * PANEL_W + k] = __builtin_bswap16(strip[k]);
      }
      fwrite(canvas, sizeof canvas, 1, stdout); fflush(stdout);
      design = PRESET_DEFAULT;
    }
  }
  return 0;
}
'''

def fmt(v):
    return ('1' if v else '0') if isinstance(v, bool) else str(v)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--board', default=os.environ.get('LW_BOARD') or 'lcd316')
    ap.add_argument('--res', default=os.environ.get('LW_RES') or '320')
    ap.add_argument('--tolerance', type=int, default=12)
    ap.add_argument('--tiles', action='store_true', help='firmware side through the tiled band loop (-DTILE_RENDER=1)')
    ap.add_argument('--out', type=Path, help='write device / ref / diff PNGs of failing presets here')
    ap.add_argument('presets', nargs='*')
    a = ap.parse_args()
    if a.board not in ('lcd316', 'amoled191'): sys.exit(f'check_board_render: unknown board {a.board}')
    lcd = a.board == 'lcd316'
    if not lcd: a.res = '240'
    paths = a.presets or sorted(glob.glob(str(ROOT / 'presets/*.json')) + glob.glob(str(ROOT / 'presets/physical/*.json')))
    env = dict(os.environ, LW_BOARD=a.board, LW_RES=a.res)
    with tempfile.TemporaryDirectory(prefix='watches-board-') as tmp:
        tmp = Path(tmp)
        (tmp / 'esp_heap_caps.h').write_text('#pragma once\n#include <cstdlib>\n#define MALLOC_CAP_SPIRAM 0\n'
                                             'inline void *heap_caps_malloc(size_t n, int) { return std::calloc(n, 1); }\n')
        (tmp / 'esp_random.h').write_text('#pragma once\n#include <cstdint>\ninline uint32_t esp_random() { return 0xabcdef01; }\n')
        (tmp / 'h.cpp').write_text(HARNESS)
        subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O2', '-ffp-contract=off', *(['-DTILE_RENDER=1'] if a.tiles else []), *([f'-DBOARD_LCD316', f'-DRENDER_H={a.res.rstrip("f")}', f'-DLCD_FILL={int(a.res.endswith("f"))}'] if lcd else []),
                        '-I', str(tmp), '-I', str(ROOT / 'firmware/src'), '-I', str(ROOT / 'spec'),
                        str(tmp / 'h.cpp'), str(ROOT / 'firmware/src/render.cpp'), str(ROOT / 'firmware/src/physics.cpp'),
                        '-o', str(tmp / 'h')], check=True)
        cache = tmp / 'sim'
        subprocess.run([str(SIM / 'node_modules/.bin/tsc'), '-p', str(SIM / 'tools/render-ref.tsconfig.json'), '--outDir', str(cache)], check=True)
        (cache / 'package.json').write_text('{}')
        (cache / 'node_modules/@spec').mkdir(parents=True)
        shutil.copy(cache / 'spec/layout.js', cache / 'node_modules/@spec/layout.js')
        jobs, script = [], []
        for path in paths:
            params = json.load(open(path))
            if not isinstance(params, dict) or 'tubeHeight' not in params: continue
            params = {**params, 'fizz': False}
            job = {'params': params, **STATE}
            font = int(round(params.get('digitFont', 0)))
            if font >= 5:
                base = SIM / 'public/assets' / (SHEETS[font - 5] + '.png')
                im = Image.open(base).convert('RGBA'); meta = json.load(open(str(base) + '.json'))
                rgba = tmp / (SHEETS[font - 5] + '.rgba')
                if not rgba.exists(): rgba.write_bytes(im.tobytes())
                job['sprite'] = {'i': font - 5, 'w': im.width, 'h': im.height, 'cellW': meta['cellW'], 'cellH': meta['cellH'], 'widths': meta['widths'], 'rgbaFile': str(rgba)}
            jf = tmp / f'job{len(jobs)}.json'; jf.write_text(json.dumps(job))
            jobs.append((path, jf))
            script += [f'P {k}={fmt(v)}' for k, v in params.items() if k != 'v']
            script += [f'S {i} {STATE[t]["fillTarget"]} {STATE[t]["light"]}' for i, t in enumerate(('hours', 'minutes'))] + ['R']
        out = subprocess.run([str(tmp / 'h')], input=('\n'.join(script) + '\n').encode(), stdout=subprocess.PIPE, check=True).stdout
        W = int(a.res.rstrip("f")) * 820 // 320 if lcd else 536; H = int(a.res.rstrip("f")); n = W * H
        assert len(out) == len(jobs) * n * 2, f'harness wrote {len(out)} bytes for {len(jobs)} presets of {W}x{H}'
        exp = lambda c: ((c >> 11 & 31) << 3 | (c >> 11 & 31) >> 2, (c >> 5 & 63) << 2 | (c >> 5 & 63) >> 4, (c & 31) << 3 | (c & 31) >> 2)
        bad = 0
        for k, (path, jf) in enumerate(jobs):
            ref_bin = tmp / 'ref.bin'
            subprocess.run(['node', str(cache / 'sim/tools/render-ref.js'), str(jf), str(ref_bin)], env=env, check=True, stdout=subprocess.DEVNULL)
            ref = struct.unpack(f'<{n}H', ref_bin.read_bytes())
            dev = struct.unpack_from(f'<{n}H', out, k * n * 2)
            off = big = worst = 0
            for i in range(n):
                if ref[i] != dev[i]:
                    off += 1; A, B = exp(ref[i]), exp(dev[i]); d = max(abs(A[j] - B[j]) for j in range(3))
                    worst = max(worst, d); big += d > a.tolerance
            name = os.path.relpath(path, ROOT)
            print(f'{name:40s} {off:6d} px off, {big:5d} > {a.tolerance}/255, worst {worst}')
            if big:
                bad += 1
                if a.out:
                    a.out.mkdir(parents=True, exist_ok=True)
                    for tag, px in (('ref', ref), ('device', dev)):
                        im = Image.new('RGB', (W, H)); im.putdata([exp(c) for c in px]); im.save(a.out / f'{Path(path).stem}-{tag}.png')
        print(f'{a.board}{"@" + a.res if lcd else ""} ({W}x{H}): {len(jobs) - bad} of {len(jobs)} presets within {a.tolerance}/255')
        sys.exit(1 if bad else 0)

if __name__ == '__main__': main()
