#!/usr/bin/env python3
"""Held render inputs (physics.h quantHyst: the light angle and the edge skew), sim vs firmware (host, no board): raw tilt
sequences through ImuFilter + stepTube on both sides (lcd316 320w8-8, a look's params), the held values compared every step.

  python3 firmware/tools/check_held.py [--preset firmware/tools/testdata/tilted-fizz-board-look-lid.json]

The sim runs that chain in float32 (Math.fround), so the two must pick the same step on EVERY step of every case.
Noise cases carry the board's own accelerometer noise at rest (docs/perf-cheap/tools/imu_rest_dev.txt, recorded with `i`,
cycled) on top of a pose: 'stand' / 'flat' rest 60 s (once settled, t >= 10 s: single steps only, at most once per 5 s);
'slow-tilt' (stand, across 0 -> 0.4 over 30 s) and 'swing' (along -0.6 + 0.4 sin(2 pi t / 2)): a held value follows, never
moving further in a physics step than its spring (rounded up to whole steps, or one step). Settled cases, no noise: a
params change at 20 s (both sides call heldReseat there, as main paramsChanged does) after which the springs settle at a
rest a fraction of a step off the grid (the first: Astra review 1's repro, lightPhys 0, acrossK 200, acrossDamp 40,
lightAngle 32 -> 32.0937652587890625); at the end each held value is within a quarter band of its spring (the settled
error bound), and 'angle-limit' (landscape, angleMax 6 -> 0) keeps the held skew inside the new limit from the change on.
Exits 1 on any failure.
"""
from pathlib import Path
import argparse, json, math, os, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / 'sim'
sys.path.insert(0, str(ROOT / 'firmware/tools'))
import boardtag

RES, TUBES, STEPS, CHANGE = '320w8-8', 2, 3000, 1000   # 60 s at 50 Hz; a settled case's params change at step 1000 (20 s)
NOISE = ROOT / 'docs/perf-cheap/tools/imu_rest_dev.txt'
Q, HYST = (0.125, 0.03125), (3, 8)   # physics.h LIGHT_Q_DEG / ANGLE_Q_DEG, LIGHT_Q_HYST / ANGLE_Q_HYST
REPRO = {'lightPhys': 0, 'acrossK': 200, 'acrossDamp': 40, 'lightAngle': 32}
LAND = {'vertical': False, 'angleMax': 6, 'angleTiltGain': 20}
# name: (along(t), across(t), normal(t)) as C / JS expressions of t (s), noise on / off, kind, params at the start,
# params from step CHANGE on
CASES = {
    'stand': ('-0.966', '0', '0.259', True, 'rest', {}, None),
    'flat': ('0', '0', '1', True, 'rest', {}, None),
    'slow-tilt': ('-0.966', '0.4 * (t < 30 ? t / 30 : 1)', '0.259', True, 'slow', {}, None),
    'swing': ('-0.6 + 0.4 * sin(2 * PI * t / 2)', '0.05', '0.3', True, 'move', {}, None),
    'repro-32': ('-0.966', '0', '0.259', False, 'settle', REPRO, {'lightAngle': 32.0937652587890625}),
    'light-q3': ('-0.966', '0', '0.259', False, 'settle', REPRO, {'lightAngle': 32.09375}),
    'light-neg': ('-0.966', '0', '0.259', False, 'settle', {**REPRO, 'lightAngle': -20}, {'lightAngle': -20.0937652587890625}),
    'light-big': ('-0.966', '0', '0.259', False, 'settle', REPRO, {'lightAngle': 61.3}),
    'angle-land': ('-0.2', '0.137', '0.97', False, 'settle', LAND, {'angleTiltGain': 20.3}),
    'angle-limit': ('-0.2', '0.137', '0.97', False, 'limit', LAND, {'angleMax': 0}),
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
static float dev[20000][3]; static int nDev = 0;
int main(int argc, char **argv) {   // argv: noise file (or -), then name=value params applied at step CHANGE
  if (!physics_init()) return 3;
  if (strcmp(argv[1], "-")) {
    FILE *nf = fopen(argv[1], "r");
    while (nDev < 20000 && fscanf(nf, "%f %f %f", &dev[nDev][0], &dev[nDev][1], &dev[nDev][2]) == 3) nDev++;
    fclose(nf);
  }
  if (!nDev) { nDev = 1; dev[0][0] = dev[0][1] = dev[0][2] = 0; }
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
    if (n == CHANGE && argc > 2) {   // main paramsChanged: the params, then every tube's held values reseated
      for (int a = 2; a < argc; a++) { char buf[128]; strcpy(buf, argv[a]); char *eq = strchr(buf, '='); *eq = 0; setParam(design, buf, eq + 1); }
      for (int i = 0; i < TUBE_COUNT; i++) boardParams(design, p[i], TUBE_PX_SCALE(i), PX_SCALE_FIZZ);
      heldReseat(st[0]);
    }
    const float t = n * PHYS_DT;
    const float *d = dev[n % nDev];
    const TiltInput raw{(float)(ALONG) + d[0], (float)(ACROSS) + d[1], 0, 0, (float)(NORMAL) + d[2]};
    const TiltInput in = f.step(raw, p[0], PHYS_DT);
    stepTube(st[0], in, p[0], PHYS_DT, TUBE_PX_SCALE(0));
    const float aMax = p[0].vertical ? ANGLE_VERTICAL_MAX_DEG : fminf(p[0].angleMax, ANGLE_HARD_MAX_DEG);
    printf("%d %d %.9g %.9g %.9g %.9g %.9g\n", (int)(st[0].light / LIGHT_Q_DEG), (int)(st[0].angle / ANGLE_Q_DEG),
           st[0].lightRaw, st[0].angleRaw, st[0].lightMean, st[0].angleMean, aMax);
  }
  return 0;
}
'''

SIMJS = r'''
const path = require('path'), fs = require('fs');
const [cache, presetFile, noiseFile, along, across, normal, steps, change, after] = process.argv.slice(2);
const ph = require(path.join(cache, 'sim/src/physics.js')), pr = require(path.join(cache, 'sim/src/params.js'));
const L = require(path.join(cache, 'spec/layout.js'));
let design = { ...pr.DEFAULT_PARAMS, ...pr.migrateParams(JSON.parse(fs.readFileSync(presetFile, 'utf8'))) };
let ps = L.TUBE_PX_SCALE.map((k) => pr.boardParams(design, k, L.PX_SCALE_FIZZ));
const dev = noiseFile === '-' ? [[0, 0, 0]] : fs.readFileSync(noiseFile, 'utf8').split('\n').filter((l) => l.trim()).map((l) => l.trim().split(/\s+/).map(Number));
const s = { ...ph.newTube(), fillTarget: 0.5 }, f = new ph.ImuFilter(), PI = Math.PI, sin = Math.sin, cos = Math.cos, F = Math.fround, out = [];
const fn = (e) => new Function('t', 'PI', 'sin', 'cos', 'return ' + e);
const A = fn(along), C = fn(across), N = fn(normal), upd = JSON.parse(after);
for (let n = 0; n < +steps; n++) {
  if (n === +change && Object.keys(upd).length) {
    design = { ...design, ...upd }; ps = L.TUBE_PX_SCALE.map((k) => pr.boardParams(design, k, L.PX_SCALE_FIZZ)); ph.heldReseat(s);
  }
  const t = F(n * F(ph.PHYS_DT)), d = dev[n % dev.length];
  // the firmware's float inputs: the pose expression in float32, plus the deviation, rounded once more
  const inp = f.step({ along: F(F(A(t, F(PI), sin, cos)) + F(d[0])), across: F(F(C(t, F(PI), sin, cos)) + F(d[1])), gyroAlong: 0, gyroAcross: 0,
                       normal: F(F(N(t, F(PI), sin, cos)) + F(d[2])) }, ps[0], ph.PHYS_DT);
  ph.stepTube(s, inp, ps[0], ph.PHYS_DT, L.TUBE_PX_SCALE[0]);
  out.push(`${Math.trunc(s.light / ph.LIGHT_Q_DEG)} ${Math.trunc(s.angle / ph.ANGLE_Q_DEG)}`);
}
console.log(out.join('\n'));
'''

def fmt(v): return ('1' if v else '0') if isinstance(v, bool) else repr(v) if isinstance(v, float) else str(v)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--preset', default=str(ROOT / 'firmware/tools/testdata/tilted-fizz-board-look-lid.json'))
    a = ap.parse_args()
    preset = json.load(open(a.preset))
    env = dict(os.environ, LW_BOARD='lcd316', LW_RES=RES, LW_TUBES=str(TUBES))
    fails = 0
    with tempfile.TemporaryDirectory(prefix='watches-held-') as tmp:
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
        for name, (along, across, normal, noisy, kind, start, after) in CASES.items():
            look = {**preset, **start}
            stdin = ''.join(f'{k}={fmt(v)}\n' for k, v in look.items() if k != 'v')
            pf = tmp / f'{name}.json'; pf.write_text(json.dumps(look))
            src = tmp / f'{name}.cpp'
            src.write_text(HARNESS.replace('ALONG', along).replace('ACROSS', across).replace('NORMAL', normal)
                           .replace('STEPS', str(STEPS)).replace('CHANGE', str(CHANGE)))
            subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O2', '-ffp-contract=off', *boardtag.tubes_flags(TUBES),
                            '-DBOARD_LCD316', *boardtag.res_flags(RES, TUBES), '-I', str(tmp), '-I', str(ROOT / 'firmware/src'),
                            '-I', str(ROOT / 'spec'), str(src), str(ROOT / 'firmware/src/physics.cpp'), '-o', str(tmp / name)], check=True)
            noise = str(NOISE) if noisy else '-'
            fw = subprocess.run([str(tmp / name), noise, *[f'{k}={fmt(v)}' for k, v in (after or {}).items()]], input=stdin.encode(),
                                stdout=subprocess.PIPE, check=True).stdout.decode().split('\n')
            sim = subprocess.run(['node', str(tmp / 'sim.js'), str(cache), str(pf), noise, along, across, normal, str(STEPS), str(CHANGE),
                                  json.dumps(after or {})], env=env, stdout=subprocess.PIPE, check=True).stdout.decode().split('\n')
            fw = [l.split() for l in fw if l.strip()]; sim = [list(map(int, l.split())) for l in sim if l.strip()]
            held = [list(map(int, v[:2])) for v in fw]
            raw = [[float(v[2]) / Q[0], float(v[3]) / Q[1]] for v in fw]
            aMax = [float(v[6]) for v in fw]
            differ = sum(1 for x, y in zip(held, sim) if x != y)
            settle = 500   # 10 s
            rng = range(settle + 1, STEPS)
            changes = [sum(1 for n in rng if held[n][k] != held[n - 1][k]) for k in range(2)]
            jump = [max(abs(held[n][k] - held[n - 1][k]) for n in rng) for k in range(2)]
            over = [sum(1 for n in rng if abs(held[n][k] - held[n - 1][k]) > max(1, math.ceil(abs(raw[n][k] - raw[n - 1][k])))) for k in range(2)]
            endErr = [abs(held[-1][k] - raw[-1][k]) for k in range(2)]   # steps, the settled error
            outside = sum(1 for n in range(STEPS) if abs(held[n][1] * Q[1]) > aMax[n] + 1e-6)
            ok = len(held) == len(sim) == STEPS and differ == 0 and outside == 0
            if kind == 'rest': ok = ok and max(jump) <= 1 and max(changes) <= (STEPS - settle) // 250
            if kind in ('slow', 'move'): ok = ok and over == [0, 0] and changes[0] > 0
            if kind in ('settle', 'limit'): ok = ok and all(endErr[k] <= 0.25 * HYST[k] + 1e-3 for k in range(2))   # the quarter band, to the mean (float ulps from the spring)
            print(f'{name:11s} {"ok" if ok else "FAIL"}: {STEPS} steps, sim != firmware on {differ}; after 10 s light / angle: changes '
                  f'{changes[0]} / {changes[1]}, largest step {jump[0]} / {jump[1]}, beyond the spring\'s own move {over[0]} / {over[1]}; '
                  f'at the end held {held[-1][0] * Q[0]:g} / {held[-1][1] * Q[1]:g} deg, |held - spring| {endErr[0]:.3f} / {endErr[1]:.3f} steps'
                  f'{f", held skew past the limit on {outside} steps" if outside else ""}')
            fails += not ok
    sys.exit(1 if fails else 0)

if __name__ == '__main__': main()
