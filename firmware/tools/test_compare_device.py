#!/usr/bin/env python3
"""compare-device.py's dump -> replay round trip on the host (no board): python3 firmware/tools/test_compare_device.py
[--board lcd316] [--res 320w8-8] [--tolerance 12] [fixture.json]

render.cpp + physics.cpp (ESP stubs) render a desk-view state (lid on: the fixture's viewElevation, default
testdata/tilted-fizz-board-look-lid.json; backTilt 0.26 / 0.4) and print the `x` dump's LAYOUT / STATE / strip lines,
STATE through state_dump.h's formatTubeState (main.cpp's). compare-device.py's parse_dump + render_ref replay it in the
sim: 0 pixels beyond the tolerance, backTilt carried over. Control: the same dump with STATE cut to the fields before
backTilt (an older record) parses with backTilt left out (render-ref: newTube's 0) and replays off by pixels beyond the
tolerance, so the test sees a dropped field. Exit 1 on a failure.
"""
import argparse, importlib.util, json, os, re, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import boardtag
from spritesheets import job_sprites

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('compare_device', Path(__file__).resolve().parent / 'compare-device.py')
cd = importlib.util.module_from_spec(spec); spec.loader.exec_module(cd)

STATE = {'hours': {'fillTarget': 0.42, 'light': 20.0, 'backTilt': 0.26}, 'minutes': {'fillTarget': 0.71, 'light': 20.0, 'backTilt': 0.4},
         'seconds': {'fillTarget': 0.5, 'light': 20.0, 'backTilt': 0.26}}

HARNESS = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "render.h"
#include "layout.h"
#include "state_dump.h"
static uint16_t strip[TUBE_COUNT][PANEL_W * TUBE_HEIGHT_MAX];
static char line[PANEL_W * 4 + 2];
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
  Params design = PRESET_DEFAULT, p[TUBE_COUNT]; TubeState st[TUBE_COUNT];
  for (int i = 0; i < TUBE_COUNT; i++) { st[i].trace = traceBuf(i); st[i].traceWet = traceWetBuf(i); }
  char in[256];
  while (fgets(in, sizeof in, stdin)) {
    in[strcspn(in, "\r\n")] = 0;
    if (in[0] == 'P') { char *eq = strchr(in + 2, '='); if (!eq) return 4; *eq = 0; if (!setParam(design, in + 2, eq + 1)) { fprintf(stderr, "unknown param %s\n", in + 2); return 5; } }
    else if (in[0] == 'S') { int i; float f, l, b; if (sscanf(in + 2, "%d %f %f %f", &i, &f, &l, &b) != 4) return 6; st[i].fillTarget = f; st[i].light = l; st[i].backTilt = b; }
  }
  for (int i = 0; i < TUBE_COUNT; i++) boardParams(design, p[i], TUBE_PX_SCALE(i), PX_SCALE_FIZZ);
#if TUBE_COUNT == 3
  const FaceLayout l = faceLayout(p[0], p[1], p[2]);
  printf("LAYOUT %d %d %d %d %d %d %d %d\n", PANEL_W, PANEL_H, l.Hh, l.yH, l.yM, l.Hm, l.yS, l.Hs);
#else
  const FaceLayout l = faceLayout(p[0], p[1]);
  printf("LAYOUT %d %d %d %d %d %d\n", PANEL_W, PANEL_H, l.Hh, l.yH, l.yM, l.Hm);
#endif
  for (int i = 0; i < TUBE_COUNT; i++) renderTube(i, st[i], p[i], 1, strip[i], nullptr, l.top(i));
  printf("STATE");   // main.cpp `x`
  for (int i = 0; i < TUBE_COUNT; i++) { const int n = formatTubeState(line, sizeof line, st[i]); if (n <= 0 || n >= (int)sizeof line) return 7; fputs(line, stdout); }
  printf("\n");
  for (int i = 0; i < TUBE_COUNT; i++)
    for (int y = 0; y < l.rows(i); y++) {
      char *o = line;
      for (int x = 0; x < PANEL_W; x++) o += sprintf(o, "%04x", __builtin_bswap16(strip[i][y * PANEL_W + x]));
      puts(line);
    }
  puts("END");
  return 0;
}
'''

def fmt(v):
    return ('1' if v else '0') if isinstance(v, bool) else str(v)

def exp(c):
    return ((c >> 11 & 31) << 3 | (c >> 11 & 31) >> 2, (c >> 5 & 63) << 2 | (c >> 5 & 63) >> 4, (c & 31) << 3 | (c & 31) >> 2)

def off(a, b, tol):
    n = big = worst = 0
    for x, y in zip(a, b):
        if x != y:
            n += 1; d = max(abs(p - q) for p, q in zip(exp(x), exp(y))); worst = max(worst, d); big += d > tol
    return n, big, worst

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--board', default='lcd316', choices=('lcd316', 'amoled191'))
    ap.add_argument('--res', default='320w8-8')
    ap.add_argument('--tolerance', type=int, default=12)
    ap.add_argument('fixture', nargs='?', default=str(ROOT / 'firmware/tools/testdata/tilted-fizz-board-look-lid.json'))
    a = ap.parse_args()
    lcd = a.board == 'lcd316'
    if not lcd: a.res = '240'
    params = {**json.load(open(a.fixture)), 'fizz': False}
    if not (params.get('vertical') and params.get('viewElevation', 0) > 0): sys.exit('test_compare_device: the fixture needs the lid (vertical, viewElevation > 0)')
    env = dict(os.environ, LW_BOARD=a.board, LW_RES=a.res, LW_TUBES='2')
    names = ('hours', 'minutes')
    fails = []
    def check(ok, what):
        print(('ok   ' if ok else 'FAIL ') + what)
        if not ok: fails.append(what)
    with tempfile.TemporaryDirectory(prefix='watches-dump-') as tmp:
        tmp = Path(tmp)
        (tmp / 'esp_heap_caps.h').write_text('#pragma once\n#include <cstdlib>\n#define MALLOC_CAP_SPIRAM 0\n'
                                             'inline void *heap_caps_malloc(size_t n, int) { return std::calloc(n, 1); }\n')
        (tmp / 'esp_random.h').write_text('#pragma once\n#include <cstdint>\ninline uint32_t esp_random() { return 0xabcdef01; }\n')
        (tmp / 'h.cpp').write_text(HARNESS)
        subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O2', '-ffp-contract=off',
                        *(['-DBOARD_LCD316', *boardtag.res_flags(a.res, 2)] if lcd else []),
                        '-I', str(tmp), '-I', str(ROOT / 'firmware/src'), '-I', str(ROOT / 'spec'),
                        str(tmp / 'h.cpp'), str(ROOT / 'firmware/src/render.cpp'), str(ROOT / 'firmware/src/physics.cpp'),
                        '-o', str(tmp / 'h')], check=True)
        script = [f'P {k}={fmt(v)}' for k, v in params.items() if k != 'v']
        script += [f'S {i} {STATE[t]["fillTarget"]} {STATE[t]["light"]} {STATE[t]["backTilt"]}' for i, t in enumerate(names)]
        dump = subprocess.run([str(tmp / 'h')], input='\n'.join(script) + '\n', stdout=subprocess.PIPE, text=True, check=True).stdout
        sprites = job_sprites(params.get('digitFont', 0), tmp)
        cache = str(tmp / 'sim')

        def replay(text):
            W, H, TH, Y0, dev, job = cd.parse_dump(text, params)
            if sprites: job['sprites'] = sprites
            ref = cd.render_ref(job, str(tmp), env, cache)
            assert len(ref) == W * H, f'sim rendered {len(ref)} px, the dump {W}x{H}'
            return dev, job, ref

        dev, job, ref = replay(dump)
        for t in names:
            got = job[t].get('backTilt')
            check(got is not None and abs(got - STATE[t]['backTilt']) < 1e-6, f'{t} backTilt {STATE[t]["backTilt"]} round-trips (parsed {got})')
        n, big, worst = off(dev, ref, a.tolerance)
        check(big == 0, f'replay vs native: {n} px off, {big} > {a.tolerance}/255, worst {worst}')

        # an older record: STATE without backTilt (the fields before it, per tube)
        st = re.search(r'^STATE(.*)$', dump, re.M); f = st.group(1).split(); k = len(f) // len(names)
        assert k == len(cd.STATE_KEYS), f'STATE has {k} fields per tube, compare-device.py STATE_KEYS {len(cd.STATE_KEYS)}'
        old = 'STATE ' + ' '.join(v for t in range(len(names)) for v in f[t * k:(t + 1) * k - 1])
        dev0, job0, ref0 = replay(dump.replace(st.group(0), old))
        check(all('backTilt' not in job0[t] for t in names), 'an older record (no backTilt) parses, backTilt left to newTube()')
        n0, big0, worst0 = off(dev0, ref0, a.tolerance)
        check(big0 > 0, f'control, replay without backTilt vs native: {n0} px off, {big0} > {a.tolerance}/255, worst {worst0}')
    print(f'{a.board}{"@" + a.res if lcd else ""}: {"FAIL " + str(len(fails)) if fails else "all ok"}')
    sys.exit(1 if fails else 0)

if __name__ == '__main__': main()
