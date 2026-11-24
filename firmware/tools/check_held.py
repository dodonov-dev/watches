#!/usr/bin/env python3
"""Held render inputs (physics.h quantHyst: light, angle, the stand's back tilt), sim vs firmware (host, no board): raw tilt
sequences through ImuFilter + stepTube on both sides (lcd316 320w8-8, a look's params), the held values compared every step.

  python3 firmware/tools/check_held.py [--preset firmware/tools/testdata/tilted-fizz-board-look-lid.json]

Cases carry the board's own accelerometer noise at rest (docs/perf-cheap/tools/imu_rest_dev.txt, recorded with `i`, cycled)
on top of a pose: 'stand' / 'flat' rest 60 s (once settled, t >= 10 s: a held value changes by single steps only, at most
once per 5 s: the recorded trace's own slow drift), 'slow-tilt' (stand, across 0 -> 0.4 over 30 s) and 'swing' (along
-0.6 + 0.4 sin(2 pi t / 2)): a held value follows, never moving further in a physics step than its spring (rounded up to
whole steps, or one step). Sim vs firmware: equal on every step, but for at most 1 % of the steps one step apart (the sim's
double springs and the firmware's float ones crossing a threshold a step apart), never in a rest case. The largest
|held - raw| (the lag, after 10 s) is printed. Exits 1 on any failure.
"""
from pathlib import Path
import argparse, json, math, os, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / 'sim'
sys.path.insert(0, str(ROOT / 'firmware/tools'))
import boardtag

RES, TUBES, STEPS = '320w8-8', 2, 3000   # 60 s at 50 Hz
NOISE = ROOT / 'docs/perf-cheap/tools/imu_rest_dev.txt'
CASES = {   # name: (along(t), across(t), normal(t)) as C / JS expressions of t (s), before the noise; kind
    'stand': ('-0.966', '0', '0.259', 'rest'),
    'flat': ('0', '0', '1', 'rest'),
    'slow-tilt': ('-0.966', '0.4 * (t < 30 ? t / 30 : 1)', '0.259', 'slow'),
    'swing': ('-0.6 + 0.4 * sin(2 * PI * t / 2)', '0.05', '0.3', 'move'),
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
int main(int argc, char **argv) {
  if (!physics_init()) return 3;
  FILE *nf = fopen(argv[1], "r");
  while (nDev < 20000 && fscanf(nf, "%f %f %f", &dev[nDev][0], &dev[nDev][1], &dev[nDev][2]) == 3) nDev++;
  fclose(nf);
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
    const float *d = dev[n % nDev];
    const TiltInput raw{(float)(ALONG) + d[0], (float)(ACROSS) + d[1], 0, 0, (float)(NORMAL) + d[2]};
    const TiltInput in = f.step(raw, p[0], PHYS_DT);
    stepTube(st[0], in, p[0], PHYS_DT, TUBE_PX_SCALE(0));
    printf("%d %d %d %.9g %.9g %.9g\n", (int)(st[0].light / LIGHT_Q_DEG), (int)(st[0].angle / ANGLE_Q_DEG), (int)(f.backTilt() / BACK_TILT_Q_RAD),
           st[0].light - st[0].lightRaw, st[0].angle - st[0].angleRaw, f.backTilt() - (f.poseValid ? poseBackTilt(f.pose) : 0.0f));
  }
  return 0;
}
'''

SIMJS = r'''
const path = require('path'), fs = require('fs');
const [cache, presetFile, noiseFile, along, across, normal, steps] = process.argv.slice(2);
const ph = require(path.join(cache, 'sim/src/physics.js')), pr = require(path.join(cache, 'sim/src/params.js'));
const L = require(path.join(cache, 'spec/layout.js'));
const design = { ...pr.DEFAULT_PARAMS, ...pr.migrateParams(JSON.parse(fs.readFileSync(presetFile, 'utf8'))) };
const ps = L.TUBE_PX_SCALE.map((k) => pr.boardParams(design, k, L.PX_SCALE_FIZZ));
const dev = fs.readFileSync(noiseFile, 'utf8').split('\n').filter((l) => l.trim()).map((l) => l.trim().split(/\s+/).map(Number));
const s = { ...ph.newTube(), fillTarget: 0.5 }, f = new ph.ImuFilter(), PI = Math.PI, sin = Math.sin, cos = Math.cos, F = Math.fround, out = [];
const fn = (e) => new Function('t', 'PI', 'sin', 'cos', 'return ' + e);
const A = fn(along), C = fn(across), N = fn(normal);
for (let n = 0; n < +steps; n++) {
  const t = F(n * F(ph.PHYS_DT)), d = dev[n % dev.length];
  // the firmware's float inputs: the pose expression in float32, plus the deviation, rounded once more
  const inp = f.step({ along: F(F(A(t, F(PI), sin, cos)) + F(d[0])), across: F(F(C(t, F(PI), sin, cos)) + F(d[1])), gyroAlong: 0, gyroAcross: 0,
                       normal: F(F(N(t, F(PI), sin, cos)) + F(d[2])) }, ps[0], ph.PHYS_DT);
  ph.stepTube(s, inp, ps[0], ph.PHYS_DT, L.TUBE_PX_SCALE[0]);
  out.push(`${Math.trunc(s.light / ph.LIGHT_Q_DEG)} ${Math.trunc(s.angle / ph.ANGLE_Q_DEG)} ${Math.trunc(f.backTilt() / ph.BACK_TILT_Q_RAD)}`);
}
console.log(out.join('\n'));
'''

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
        stdin = ''.join(f'{k}={("1" if v else "0") if isinstance(v, bool) else v}\n' for k, v in preset.items() if k != 'v')
        for name, (along, across, normal, kind) in CASES.items():
            src = tmp / f'{name}.cpp'
            src.write_text(HARNESS.replace('ALONG', along).replace('ACROSS', across).replace('NORMAL', normal).replace('STEPS', str(STEPS)))
            subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O2', '-ffp-contract=off', *boardtag.tubes_flags(TUBES),
                            '-DBOARD_LCD316', *boardtag.res_flags(RES, TUBES), '-I', str(tmp), '-I', str(ROOT / 'firmware/src'),
                            '-I', str(ROOT / 'spec'), str(src), str(ROOT / 'firmware/src/physics.cpp'), '-o', str(tmp / name)], check=True)
            fw = subprocess.run([str(tmp / name), str(NOISE)], input=stdin.encode(), stdout=subprocess.PIPE, check=True).stdout.decode().split('\n')
            sim = subprocess.run(['node', str(tmp / 'sim.js'), str(cache), a.preset, str(NOISE), along, across, normal, str(STEPS)], env=env,
                                 stdout=subprocess.PIPE, check=True).stdout.decode().split('\n')
            fw = [l.split() for l in fw if l.strip()]; sim = [list(map(int, l.split())) for l in sim if l.strip()]
            held = [list(map(int, v[:3])) for v in fw]; off = [[float(x) for x in v[3:]] for v in fw]
            Q = (0.125, 0.03125, 1 / 32768)   # physics.h LIGHT_Q_DEG, ANGLE_Q_DEG, BACK_TILT_Q_RAD
            raw = [[held[n][k] - off[n][k] / Q[k] for k in range(3)] for n in range(len(held))]   # the springs' values, in steps
            differ = sum(1 for x, y in zip(held, sim) if x != y)
            far = sum(1 for x, y in zip(held, sim) if any(abs(a - b) > 1 for a, b in zip(x, y)))
            settle = 500   # 10 s
            rng = range(settle + 1, STEPS)
            changes = [sum(1 for n in rng if held[n][k] != held[n - 1][k]) for k in range(3)]
            jump = [max(abs(held[n][k] - held[n - 1][k]) for n in rng) for k in range(3)]
            # a held value never moves further in a step than the spring did (rounded up), or one step (the mean's pull)
            over = [sum(1 for n in rng if abs(held[n][k] - held[n - 1][k]) > max(1, math.ceil(abs(raw[n][k] - raw[n - 1][k])))) for k in range(3)]
            maxLag = [max(abs(o[k]) for o in off[settle:]) for k in range(3)]
            # sim and firmware agree on every step; where the double sim springs and the float firmware ones cross a threshold
            # a step apart, the held values may differ by one step for a step (at most 1 % of the steps)
            ok = len(held) == len(sim) == STEPS and far == 0 and differ <= STEPS // 100
            if kind == 'rest': ok = ok and differ == 0 and jump[0] <= 1 and jump[1] <= 1 and jump[2] <= 1 and max(changes) <= (STEPS - settle) // 250
            if kind == 'slow': ok = ok and over == [0, 0, 0] and changes[0] > 0
            if kind == 'move': ok = ok and over == [0, 0, 0] and all(c > 0 for c in changes[:2])
            print(f'{name:10s} {"ok" if ok else "FAIL"}: {STEPS} steps, sim != firmware on {differ} ({far} by more than a step); after 10 s held '
                  f'light / angle / back tilt: changes {changes[0]} / {changes[1]} / {changes[2]}, largest step {jump[0]} / {jump[1]} / {jump[2]}, '
                  f'beyond the spring\'s own move {over[0]} / {over[1]} / {over[2]}, |held - raw| up to {maxLag[0]:.3f} deg / {maxLag[1]:.3f} deg / '
                  f'{maxLag[2]:.4f} rad')
            fails += not ok
    sys.exit(1 if fails else 0)

if __name__ == '__main__': main()
