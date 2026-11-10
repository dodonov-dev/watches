#!/usr/bin/env python3
"""Rear-parallax gate regression, sim vs firmware (host, no board): raw tilt sequences through ImuFilter + stepTube on both
sides (lcd316 320w10-8-6, three tubes at their px scales, a preset's params), the quantised shifts compared every step.

  python3 firmware/tools/check_rear_gate.py [--preset firmware/bench/lcd-1105.json]

Cases: a smooth sustained swing (along -0.2 + 0.8 sin(2 pi t / 3)) must hold the shift at 0 once the swing is under way
(t >= 4 s), its reversals included; a slow tilt (along -1 .. -0.7, 8 s sine) must move it (the gate open). Each case:
the firmware's integers equal the sim's on every step. Exits 1 on any failure.
"""
from pathlib import Path
import argparse, json, os, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / 'sim'
sys.path.insert(0, str(ROOT / 'firmware/tools'))
import boardtag

RES, TUBES, STEPS = '320w10-8-6', 3, 1500   # 30 s at 50 Hz
CASES = {   # name: (along(t), across(t)) as C / JS expressions of t (s); hold = t from which the shift must be 0 (None: must move)
    'smooth-swing': ('-0.2 + 0.8 * sin(2 * PI * t / 3)', '0.05', 4.0),
    'slow-tilt': ('-1 + 0.3 * (1 - cos(2 * PI * t / 8)) / 2', '0.05', None),
}

HARNESS = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include "physics.h"
#include "layout.h"
static const float PI = 3.14159265358979f;
static void setParam(Params &p, const char *name, const char *val) {
  for (const ParamField &f : PARAM_FIELDS) if (!strcmp(f.name, name)) {
    uint8_t *q = (uint8_t *)&p + f.off;
    switch (f.type) {
      case 'f': *(float *)q = atof(val); break;
      case 'i': *(int *)q = atoi(val); break;
      case 'b': *(bool *)q = !(val[0] == '0' || val[0] == 'f' || val[0] == 'F' || val[0] == 'n'); break;
      case 'c': *(uint32_t *)q = strtoul(val[0] == '#' ? val + 1 : val, nullptr, 16); break;
    }
  }
}
int main(int argc, char **argv) {
  if (!physics_init()) return 3;
  Params design = PRESET_DEFAULT, p[TUBE_COUNT];
  char line[256];
  while (fgets(line, sizeof line, stdin)) {
    line[strcspn(line, "\r\n")] = 0;
    char *eq = strchr(line, '='); if (!eq) continue; *eq = 0; setParam(design, line, eq + 1);
  }
  for (int i = 0; i < TUBE_COUNT; i++) boardParams(design, p[i], TUBE_PX_SCALE(i), PX_SCALE_FIZZ);
  TubeState st[TUBE_COUNT]; ImuFilter f;
  for (int i = 0; i < TUBE_COUNT; i++) { st[i].trace = traceBuf(i); st[i].traceWet = traceWetBuf(i); st[i].fillTarget = 0.5f; }
  for (int n = 0; n < STEPS; n++) {
    const float t = n * PHYS_DT;
    const TiltInput raw{(float)(ALONG), (float)(ACROSS), 0, 0};
    const TiltInput in = f.step(raw, p[0], PHYS_DT);
    for (int i = 0; i < TUBE_COUNT; i++) {
      stepTube(st[i], in, p[i], PHYS_DT, TUBE_PX_SCALE(i));
      printf("%d %d %d %d ", st[i].rearX16, st[i].rearY16, st[i].rearX16w, st[i].rearY16w);
    }
    printf("\n");
  }
  return 0;
}
'''

SIMJS = r'''
const path = require('path');
const [cache, presetFile, along, across, steps] = process.argv.slice(2);
const ph = require(path.join(cache, 'sim/src/physics.js')), pr = require(path.join(cache, 'sim/src/params.js'));
const L = require(path.join(cache, 'spec/layout.js'));
const design = { ...pr.DEFAULT_PARAMS, ...pr.migrateParams(JSON.parse(require('fs').readFileSync(presetFile, 'utf8'))) };
const ps = L.TUBE_PX_SCALE.map((k) => pr.boardParams(design, k, L.PX_SCALE_FIZZ));
const tubes = ps.map(() => ({ ...ph.newTube(), fillTarget: 0.5 }));
const f = new ph.ImuFilter(), PI = Math.PI, sin = Math.sin, cos = Math.cos, out = [];
const A = new Function('t', 'PI', 'sin', 'cos', 'return ' + along), C = new Function('t', 'PI', 'sin', 'cos', 'return ' + across);
for (let n = 0; n < +steps; n++) {
  const t = n * ph.PHYS_DT;
  const inp = f.step({ along: Math.fround(A(t, Math.fround(PI), sin, cos)), across: Math.fround(C(t, PI, sin, cos)), gyroAlong: 0, gyroAcross: 0 }, ps[0], ph.PHYS_DT);
  out.push(tubes.map((s, i) => { ph.stepTube(s, inp, ps[i], ph.PHYS_DT, L.TUBE_PX_SCALE[i]); return `${s.rearX16} ${s.rearY16} ${s.rearX16w} ${s.rearY16w}`; }).join(' '));
}
console.log(out.join('\n'));
'''

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--preset', default=str(ROOT / 'firmware/bench/lcd-1105.json'))
    a = ap.parse_args()
    preset = json.load(open(a.preset))
    env = dict(os.environ, LW_BOARD='lcd316', LW_RES=RES, LW_TUBES=str(TUBES))
    fails = 0
    with tempfile.TemporaryDirectory(prefix='watches-rear-') as tmp:
        tmp = Path(tmp)
        (tmp / 'esp_heap_caps.h').write_text('#pragma once\n#include <cstdlib>\n#define MALLOC_CAP_SPIRAM 0\n'
                                             'inline void *heap_caps_malloc(size_t n, int) { return std::calloc(n, 1); }\n')
        (tmp / 'esp_random.h').write_text('#pragma once\n#include <cstdint>\ninline uint32_t esp_random() { return 1; }\n')
        cache = tmp / 'sim'
        subprocess.run([str(SIM / 'node_modules/.bin/tsc'), '-p', str(SIM / 'tools/render-ref.tsconfig.json'), '--outDir', str(cache)], check=True)
        (cache / 'package.json').write_text('{}')
        (cache / 'node_modules/@spec').mkdir(parents=True)
        (cache / 'node_modules/@spec/layout.js').write_bytes((cache / 'spec/layout.js').read_bytes())
        (tmp / 'sim.js').write_text(SIMJS)
        stdin = ''.join(f'{k}={("1" if v else "0") if isinstance(v, bool) else v}\n' for k, v in preset.items() if k != 'v')
        for name, (along, across, hold) in CASES.items():
            src = tmp / f'{name}.cpp'
            src.write_text(HARNESS.replace('ALONG', along).replace('ACROSS', across).replace('STEPS', str(STEPS)))
            subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O2', '-ffp-contract=off', *boardtag.tubes_flags(TUBES),
                            '-DBOARD_LCD316', *boardtag.res_flags(RES, TUBES), '-I', str(tmp), '-I', str(ROOT / 'firmware/src'),
                            '-I', str(ROOT / 'spec'), str(src), str(ROOT / 'firmware/src/physics.cpp'), '-o', str(tmp / name)], check=True)
            fw = subprocess.run([str(tmp / name)], input=stdin.encode(), stdout=subprocess.PIPE, check=True).stdout.decode().split('\n')
            sim = subprocess.run(['node', str(tmp / 'sim.js'), str(cache), a.preset, along, across, str(STEPS)], env=env,
                                 stdout=subprocess.PIPE, check=True).stdout.decode().split('\n')
            fw = [list(map(int, l.split())) for l in fw if l.strip()]; sim = [list(map(int, l.split())) for l in sim if l.strip()]
            differ = sum(1 for x, y in zip(fw, sim) if x != y)
            moving = [n for n, v in enumerate(sim) if any(v)]
            frac = sum(1 for v in sim if any(c % 16 for c in v))
            late = [n for n in moving if hold is not None and n * 0.02 >= hold]
            ok = differ == 0 and len(fw) == len(sim) == STEPS and (late == [] if hold is not None else moving != [])
            peak = max((abs(c) for v in sim for c in v), default=0)
            print(f'{name:13s} {"ok" if ok else "FAIL"}: {STEPS} steps, sim != firmware on {differ}, shift non-zero on {len(moving)} steps '
                  f'({len(late)} after t = {hold} s), fractional on {frac}, peak |shift| {peak}/16 px')
            fails += not ok
    sys.exit(1 if fails else 0)

if __name__ == '__main__': main()
