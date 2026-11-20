#!/usr/bin/env python3
"""Edge shade factors, firmware vs sim, row by row (host, no device): the rod profile (render.cpp buildShade, sim
render.ts edgeShadeRows) over a matrix of looks per board / canvas.

  python3 firmware/tools/check_shade_rows.py [--board lcd316 --res 320w8-8] [--tubes 2]

Looks: every preset's tube geometry (tubeHeight, rows, stacking) x edgeShade 0.3 / 0.67 / 1 x edgeShadePow 0.25 / 0.6 /
1 / 2.5 / 4 x edgeShadeFold 0 / 0.4 / 0.8 / 1, plus a tubeHeight sweep and a lens sweep (lens -1 .. 1 x curve -3 .. 3). Compares per tube the shown rows'
factors and the lens row map the fold uses (firmware lensSrc, sim lensSourceRows: float32 both), and pins one strong
lens (H 72, lens 1 / curve 3: shown rows 33..35 show drawn row 36). Exits 1 on any difference, a missing or reordered
tube, a look with no shaded row, or a moved pin.
"""
import argparse, glob, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import boardtag

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / 'sim'
HARNESS = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "render.h"
#include "layout.h"
const uint16_t *render_shade_rows(int idx, int &H);
const int16_t *render_lens_rows(int idx);
static uint16_t strip[PANEL_W * TUBE_HEIGHT_MAX];
static bool setParam(Params &p, const char *name, const char *val) {
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
  Params design = PRESET_DEFAULT, p[TUBE_COUNT]; TubeState st[TUBE_COUNT]; uint32_t gen = 1;
  for (int i = 0; i < TUBE_COUNT; i++) { st[i].trace = traceBuf(i); st[i].traceWet = traceWetBuf(i); }
  char line[256];
  while (fgets(line, sizeof line, stdin)) {
    line[strcspn(line, "\r\n")] = 0;
    if (line[0] == 'P') { char *eq = strchr(line + 2, '='); if (!eq) return 4; *eq = 0; setParam(design, line + 2, eq + 1); }
    else if (line[0] == 'R') {
      for (int i = 0; i < TUBE_COUNT; i++) boardParams(design, p[i], TUBE_PX_SCALE(i), PX_SCALE_FIZZ);
      gen++;
#if TUBE_COUNT == 3
      const FaceLayout lay = faceLayout(p[0], p[1], p[2]);
#else
      const FaceLayout lay = faceLayout(p[0], p[1]);
#endif
      for (int i = 0; i < TUBE_COUNT; i++) {
        renderTube(i, st[i], p[i], gen, strip, nullptr, lay.top(i));
        int H = 0; const uint16_t *T = render_shade_rows(i, H); const int16_t *L = render_lens_rows(i);
        printf("%s%d:", i ? ";" : "", i);
        if (T) for (int y = 0; y < H; y++) printf(y ? ",%u" : "%u", T[y]);
        printf(":");
        if (L) for (int y = 0; y < H; y++) printf(y ? ",%d" : "%d", L[y]);
      }
      printf("\n"); fflush(stdout);
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
    ap.add_argument('--board', default='lcd316')
    ap.add_argument('--res', default='320w8-8')
    ap.add_argument('--tubes', type=int, default=2, choices=(2, 3))
    a = ap.parse_args()
    lcd = a.board == 'lcd316'
    if not lcd: a.res = '240'
    looks = []
    geo = []
    for path in sorted(glob.glob(str(ROOT / 'presets/*.json')) + glob.glob(str(ROOT / 'presets/physical/*.json'))):
        q = json.load(open(path))
        if isinstance(q, dict) and 'tubeHeight' in q: geo.append(q)
    base = json.load(open(ROOT / 'presets/1.json'))
    for h in range(8, 81, 4): geo.append({**base, 'tubeHeight': h})
    for lens in (-1, -0.6, -0.2, 0.2, 0.6, 1):
        for curve in (-3, -1, -0.2, 0.2, 1, 3): geo.append({**base, 'lens': lens, 'lensCurve': curve})
    pin = {**base, 'tubeHeight': 54, 'lens': 1, 'lensCurve': 3, 'edgeShade': 0.67, 'edgeShadePow': 1, 'fizz': False}
    for g in geo:
        for k in (0.3, 0.67, 1):
            for pw in (0.25, 0.6, 1, 2.5, 4):
                for fo in (0, 0.4, 0.8, 1): looks.append({**g, 'edgeShade': k, 'edgeShadePow': pw, 'edgeShadeFold': fo, 'fizz': False})
    looks.append(pin)
    env = dict(os.environ, LW_BOARD=a.board, LW_RES=a.res, LW_TUBES=str(a.tubes))
    with tempfile.TemporaryDirectory(prefix='watches-shrows-') as tmp:
        tmp = Path(tmp)
        (tmp / 'esp_heap_caps.h').write_text('#pragma once\n#include <cstdlib>\n#define MALLOC_CAP_SPIRAM 0\n'
                                             'inline void *heap_caps_malloc(size_t n, int) { return std::calloc(n, 1); }\n')
        (tmp / 'esp_random.h').write_text('#pragma once\n#include <cstdint>\ninline uint32_t esp_random() { return 0xabcdef01; }\n')
        (tmp / 'h.cpp').write_text(HARNESS)
        subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O2', '-ffp-contract=off', '-DSHADE_ROWS_DUMP', *boardtag.tubes_flags(a.tubes),
                        *(['-DBOARD_LCD316', *boardtag.res_flags(a.res, a.tubes)] if lcd else []),
                        '-I', str(tmp), '-I', str(ROOT / 'firmware/src'), '-I', str(ROOT / 'spec'),
                        str(tmp / 'h.cpp'), str(ROOT / 'firmware/src/render.cpp'), str(ROOT / 'firmware/src/physics.cpp'),
                        '-o', str(tmp / 'h')], check=True)
        script = []
        for q in looks: script += [f'P {k}={fmt(v)}' for k, v in q.items() if k != 'v'] + ['R']
        fw = subprocess.run([str(tmp / 'h')], input=('\n'.join(script) + '\n').encode(), stdout=subprocess.PIPE, check=True).stdout.decode().split('\n')
        cache = tmp / 'sim'
        subprocess.run([str(SIM / 'node_modules/.bin/tsc'), '-p', str(SIM / 'tools/shade-rows.tsconfig.json'), '--outDir', str(cache)], check=True)
        (cache / 'package.json').write_text('{}')
        (cache / 'node_modules/@spec').mkdir(parents=True)
        shutil.copy(cache / 'spec/layout.js', cache / 'node_modules/@spec/layout.js')
        (tmp / 'looks.json').write_text(json.dumps(looks))
        sim = subprocess.run(['node', str(cache / 'sim/tools/shade-rows.js'), str(tmp / 'looks.json')], env=env, stdout=subprocess.PIPE, check=True).stdout.decode().split('\n')
    rows = diff = worst = maps = mapdiff = bad = 0
    for i, q in enumerate(looks):
        tf, ts = fw[i].split(';'), sim[i].split(';')
        if len(tf) != a.tubes or len(ts) != a.tubes: print(f'look {i}: {len(tf)} firmware / {len(ts)} sim tubes, want {a.tubes}'); bad += 1; continue
        for t, (f, g) in enumerate(zip(tf, ts)):
            fi, fT, fL = f.split(':'); si, sT, sL = g.split(':')
            if fi != str(t) or si != str(t): print(f'look {i}: tube ids {fi} / {si} at {t}'); bad += 1; continue
            A = [int(v) for v in fT.split(',') if v]; B = [int(v) for v in sT.split(',') if v]
            if not A or len(A) != len(B): print(f'look {i} tube {t}: {len(A)} firmware rows, {len(B)} sim'); bad += 1; continue
            for x, y in zip(A, B):
                rows += 1
                if x != y: diff += 1; worst = max(worst, abs(x - y))
            if fL or sL:
                maps += 1; mapdiff += fL != sL
                if fL != sL and mapdiff <= 3: print(f'look {i} tube {t}: lens maps differ (lens {q.get("lens")} / {q.get("lensCurve")}, H {len(A)})')
    # the pin: the last look, tube 0 (H 72 at 320w8-8)
    L = [int(v) for v in fw[len(looks) - 1].split(';')[0].split(':')[2].split(',') if v]
    pinned = len(L) == 72 and L[33:36] == [36, 36, 36] if lcd and a.res == '320w8-8' else None
    tag = f'{a.board}{"@" + a.res if lcd else ""}{"+t3" if a.tubes == 3 else ""}'
    print(f'{tag}: {len(looks)} looks, {rows} shaded rows, {diff} differ (worst {worst}/256); {maps} lens maps, {mapdiff} differ'
          + ('' if pinned is None else f'; pin lens 1 / 3 rows 33..35 -> {L[33:36]} {"ok" if pinned else "MOVED"}'))
    sys.exit(1 if diff or mapdiff or bad or pinned is False else 0)

if __name__ == '__main__': main()
