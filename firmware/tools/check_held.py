#!/usr/bin/env python3
"""Held render inputs (physics.h quantHyst: the light angle and the edge skew), sim vs firmware (host, no board): raw tilt
sequences through ImuFilter + stepTube on both sides (lcd316 320w8-8, a look's params), the held values compared every step.

  python3 firmware/tools/check_held.py [--preset firmware/tools/testdata/tilted-fizz-board-look-lid.json]

The sim runs that chain in float32 (Math.fround) with the shared pAtan2 / pExpNeg, so the two hold the same bits on EVERY
step of every case. Noise cases carry the board's own accelerometer noise at rest (docs/perf-cheap/tools/imu_rest_dev.txt,
recorded with `i`, cycled) on top of a pose: 'stand' / 'flat' rest 60 s (once settled, t >= 10 s: steps of at most one,
at most once per 5 s, and at the end within a quarter band of the mean); 'slow-tilt' (stand, across 0 -> 0.4 over 30 s),
'swing' (along -0.6 + 0.4 sin(2 pi t / 2)) and 'angle-cap' (landscape, a slow tilt into the cap: review 2's 5.75 -> 6
jump): a held value follows, never moving further in a physics step than its spring (rounded up to whole steps, or one
step). Settled cases, no noise: a params change at 20 s (both sides call heldReseat there, as main paramsChanged does) and
the springs settling at a rest a fraction of a step off the grid (Astra review 1's repro, lightPhys 0, acrossK 200,
acrossDamp 40, lightAngle 32 -> 32.0937652587890625, and more; review 2's LCD atan2f pose): at the end each held value
sits on the mean (within a quarter step). 'angle-limit' (landscape, angleMax 6 -> 0) and 'orient' (vertical -> landscape,
angleMax 3) keep the skew inside the new limit, sampled right after heldReseat too (what a render before the next step
reads). 'math': the shared pAtan2 / pExpNeg, firmware vs sim, bit for bit. Exits 1 on any failure.
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
    # a slow tilt into the cap (review 2: 5.75 -> 6 deg in one frame): the held skew walks onto the limit's step
    'angle-cap': ('-0.2', '0.01 * t', '0.97', False, 'slow', LAND, None),
    # vertical -> landscape at 20 s: the tighter limit applies before anything renders
    'orient': ('-0.2', '0.137', '0.97', False, 'limit', {}, {'vertical': False, 'angleMax': 3}),
    # review 2's settled LCD atan2f case: the shared pAtan2 makes both sides' rest the same bits by construction
    'lcd-atan2': ('-0.5099999904632568', '0.0005563255399465561', '0.8601742386817932', False, 'settle', {}, None),
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
static uint32_t bits(float v) { uint32_t u; memcpy(&u, &v, 4); return u; }
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
      for (int i = 0; i < TUBE_COUNT; i++) heldReseat(st[i], p[i]);
      // what a render right after the change reads (main: `x`, or a frame before the next physics step)
      const float aMax = p[0].vertical ? ANGLE_VERTICAL_MAX_DEG : fminf(p[0].angleMax, ANGLE_HARD_MAX_DEG);
      printf("R %08x %08x %.9g %.9g %.9g\n", bits(st[0].light), bits(st[0].angle), st[0].light, st[0].angle, aMax);
    }
    const float t = n * PHYS_DT;
    const float *d = dev[n % nDev];
    const TiltInput raw{(float)(ALONG) + d[0], (float)(ACROSS) + d[1], 0, 0, (float)(NORMAL) + d[2]};
    const TiltInput in = f.step(raw, p[0], PHYS_DT);
    stepTube(st[0], in, p[0], PHYS_DT, TUBE_PX_SCALE(0));
    const float aMax = p[0].vertical ? ANGLE_VERTICAL_MAX_DEG : fminf(p[0].angleMax, ANGLE_HARD_MAX_DEG);
    printf("%08x %08x %.9g %.9g %.9g %.9g %.9g %.9g %.9g\n", bits(st[0].light), bits(st[0].angle), st[0].light, st[0].angle,
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
const dv = new DataView(new ArrayBuffer(4)), hx = (v) => { dv.setFloat32(0, v); return dv.getUint32(0).toString(16).padStart(8, '0'); };
const A = fn(along), C = fn(across), N = fn(normal), upd = JSON.parse(after);
for (let n = 0; n < +steps; n++) {
  if (n === +change && Object.keys(upd).length) {
    design = { ...design, ...upd }; ps = L.TUBE_PX_SCALE.map((k) => pr.boardParams(design, k, L.PX_SCALE_FIZZ)); ph.heldReseat(s, ps[0]);
    out.push(`R ${hx(s.light)} ${hx(s.angle)}`);
  }
  const t = F(n * F(ph.PHYS_DT)), d = dev[n % dev.length];
  // the firmware's float inputs: the pose expression in float32, plus the deviation, rounded once more
  const inp = f.step({ along: F(F(A(t, F(PI), sin, cos)) + F(d[0])), across: F(F(C(t, F(PI), sin, cos)) + F(d[1])), gyroAlong: 0, gyroAcross: 0,
                       normal: F(F(N(t, F(PI), sin, cos)) + F(d[2])) }, ps[0], ph.PHYS_DT);
  ph.stepTube(s, inp, ps[0], ph.PHYS_DT, L.TUBE_PX_SCALE[0]);
  out.push(`${hx(s.light)} ${hx(s.angle)}`);
}
console.log(out.join('\n'));
'''

MATH_C = r'''
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <cmath>
#include "physics.h"
static uint32_t bits(float v) { uint32_t u; memcpy(&u, &v, 4); return u; }
int main() {   // the shared parity functions over a spread of float inputs, as bits: inputs then results
  uint32_t x = 12345;
  for (int k = 0; k < 20000; k++) {
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    const float a = (int)(x % 2000001u) * 1e-6f - 1, b = (int)((x >> 7) % 2000001u) * 1.3e-6f - 1.3f;
    const float e = (x % 100000u) * 4e-5f;   // pExpNeg's x >= 0
    printf("%08x %08x %08x %08x %08x\n", bits(a), bits(b), bits(e), bits(pAtan2(a, b)), bits(pExpNeg(e)));
  }
}
'''
MATH_JS = r'''
const path = require('path'), fs = require('fs');
const ph = require(path.join(process.argv[2], 'sim/src/physics.js'));
const dv = new DataView(new ArrayBuffer(4));
const f = (hx) => { dv.setUint32(0, parseInt(hx, 16)); return dv.getFloat32(0); };
const h = (v) => { dv.setFloat32(0, v); return dv.getUint32(0).toString(16).padStart(8, '0'); };
const out = [];
for (const l of fs.readFileSync(process.argv[3], 'utf8').split('\n')) {
  if (!l.trim()) continue;
  const w = l.split(' ');
  out.push([...w.slice(0, 3), h(ph.pAtan2(f(w[0]), f(w[1]))), h(ph.pExpNeg(f(w[2])))].join(' '));
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
        # the shared parity functions (physics.h pAtan2 / pExpNeg vs the sim's): every bit equal
        (tmp / 'math.cpp').write_text(MATH_C); (tmp / 'math.js').write_text(MATH_JS)
        subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O2', '-ffp-contract=off', *boardtag.tubes_flags(TUBES), '-DBOARD_LCD316',
                        *boardtag.res_flags(RES, TUBES), '-I', str(tmp), '-I', str(ROOT / 'firmware/src'), '-I', str(ROOT / 'spec'),
                        str(tmp / 'math.cpp'), '-o', str(tmp / 'math')], check=True)
        mc = subprocess.run([str(tmp / 'math')], stdout=subprocess.PIPE, check=True).stdout.decode()
        (tmp / 'math.txt').write_text(mc)
        mj = subprocess.run(['node', str(tmp / 'math.js'), str(cache), str(tmp / 'math.txt')], env=env, stdout=subprocess.PIPE, check=True).stdout.decode()
        mcl, mjl = mc.split(), mj.split()
        mbad = sum(1 for x, y in zip(mcl, mjl) if x != y)
        mok = len(mcl) == len(mjl) and mbad == 0
        print(f'{"math":11s} {"ok" if mok else "FAIL"}: pAtan2 / pExpNeg on {len(mcl) // 5} inputs each, sim != firmware on {mbad} values')
        fails += not mok
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
            fwR = [l.split()[1:] for l in fw if l.startswith('R ')]; simR = [l.split()[1:] for l in sim if l.startswith('R ')]
            fw = [l.split() for l in fw if l.strip() and not l.startswith('R ')]
            if os.environ.get('HELD_DUMP') == name: open(f'/tmp/claude-1000/held-{name}.txt', 'w').write('\n'.join(' '.join(v) for v in fw))
            sim = [l.split() for l in sim if l.strip() and not l.startswith('R ')]
            # right after the change, before a step (what a render then reads): sim == firmware, the skew inside the limit
            reseat_ok = len(fwR) == len(simR) and all(a[:2] == b[:2] for a, b in zip(fwR, simR)) and \
                all(abs(float(r[3])) <= float(r[4]) + 1e-6 for r in fwR)
            differ = sum(1 for x, y in zip(fw, sim) if x[:2] != y[:2])   # the held values' bits
            held = [[float(v[2]) / Q[0], float(v[3]) / Q[1]] for v in fw]   # in steps
            raw = [[float(v[4]) / Q[0], float(v[5]) / Q[1]] for v in fw]; mean = [[float(v[6]) / Q[0], float(v[7]) / Q[1]] for v in fw]
            aMax = [float(v[8]) for v in fw]
            settle = 500   # 10 s
            rng = range(settle + 1, STEPS)
            changes = [sum(1 for n in rng if held[n][k] != held[n - 1][k]) for k in range(2)]
            whole = [sum(1 for n in rng if abs(held[n][k] - held[n - 1][k]) > 0.999) for k in range(2)]   # moves of a step or more
            jump = [max(abs(held[n][k] - held[n - 1][k]) for n in rng) for k in range(2)]
            jumpAt = [max(rng, key=lambda n: abs(held[n][k] - held[n - 1][k])) for k in range(2)]
            # a held value never moves further in a step than the spring did (rounded up), or one step (the mean's pull)
            over = [sum(1 for n in rng if abs(held[n][k] - held[n - 1][k]) > max(1, math.ceil(abs(raw[n][k] - raw[n - 1][k])) + 1e-6)) for k in range(2)]
            endErr = [abs(held[-1][k] - mean[-1][k]) for k in range(2)]   # steps, the settled error (to the mean)
            outside = sum(1 for n in range(STEPS) if abs(held[n][1] * Q[1]) > aMax[n] + 1e-6)
            ok = len(fw) == len(sim) == STEPS and differ == 0 and outside == 0 and reseat_ok
            if kind == 'rest': ok = ok and max(jump) <= 1 and max(whole) <= (STEPS - settle) // 250 and all(e <= 0.5 * h + 1e-3 for e, h in zip(endErr, HYST))   # the slow-change bound (the trace drifts)
            if kind in ('slow', 'move'): ok = ok and over == [0, 0] and changes[0] + changes[1] > 0
            if kind in ('settle', 'limit'): ok = ok and all(e <= 0.25 + 1e-3 for e in endErr)   # settled on the mean (its last creep)
            print(f'{name:11s} {"ok" if ok else "FAIL"}: {STEPS} steps, sim != firmware on {differ}; after 10 s light / angle: changes '
                  f'{changes[0]} / {changes[1]} (whole steps {whole[0]} / {whole[1]}), largest step {jump[0]:.3g} / {jump[1]:.3g} (step {jumpAt[0]} / {jumpAt[1]}), beyond the spring\'s own move {over[0]} / {over[1]}; '
                  f'at the end held {held[-1][0] * Q[0]:.6g} / {held[-1][1] * Q[1]:.6g} deg, |held - mean| {endErr[0]:.3f} / {endErr[1]:.3f} steps'
                  f'{f", held skew past the limit on {outside} steps" if outside else ""}{"" if reseat_ok else ", RESEAT: sim != firmware or past the limit before a step"}')
            fails += not ok
    sys.exit(1 if fails else 0)

if __name__ == '__main__': main()
