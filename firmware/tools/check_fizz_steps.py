#!/usr/bin/env python3
"""Stepped sequences, current render.cpp vs a saved reference (native C++, no board): fizz, residue, cross-frame memos.

  python3 firmware/tools/check_fizz_steps.py --reference /tmp/render-before.cpp [--fma] [--board lcd316 --res 320f]
                                             [--tubes 2|3] [--tiles] [-j N] [presets/x.json ...]

Each preset (default: presets/*.json and presets/physical/*.json, plus the built-in spring SCENES) runs the deterministic sequence of firmware/src/seq.h
(the board's `X` command: a fixed tilt script, every tube and the fizz stepped, a frame every 2 steps) in a fresh
process per side, with esp_random as a fixed LCG, so the bubbles really move: births, springs, parked and popping
foam. Frames are compared by hash per tube (strip pixels, and the fizz state: render.cpp is #included by the driver,
its tubes' Fizz slots + spring clocks hashed), with the fizz counts; the first differing frame is reported. A rewrite
that changes struct Fizz or those fields on purpose: --pixels-only.
check_render_frames.py never steps the fizz (every bubble of a scene on one spot), so a fizz rewrite needs this too.
--fma builds both sides with -mfma -ffp-contract=fast: like the board, a * b + c fuses, so a rewrite that changes
which products feed which adds shows up (default -ffp-contract=off, like the other host checks). Still not the
board's code: confirm a fizz rewrite on the board with tools/check_board_steps.py.
--board / --res / --tubes as check_board_render.py (default amoled191; lcd316 --res 320f = the wide LCD canvas; --tubes 3
= + the seconds tube); --tiles: the current side renders through the tiled band loop (-DTILE_RENDER=1).

  python3 firmware/tools/check_fizz_steps.py --sim [--board lcd316 --res 320w8-8] [--job NAME ...] [-v]

--sim: the stepped fizz state, sim vs firmware (no --reference): each job of SIM_JOBS (the board look,
testdata/tilted-fizz-board-look.json; default lcd316 --res 320w8-8, the board it was saved on) runs in the native
render.cpp + physics.cpp build and in sim/tools/render-ref.ts (its fizzSteps mode), both drawing from one seeded
generator (xorshift32, (word >>> 8) / 2^24: a test-only esp_random stub, Math.random in the sim job): a frame before
the first step and after every 2nd, the fizz stepped at fixed inputs (along, across, normal, agitation; normal is
carried for the signed-normal input and not read yet). After every step each tube's slot count and the generator's
draw count (exact), the spring clocks and every slot's fields (within SIM_TOL) are compared; the first mismatch is
reported. Each native job runs twice (identical output: the jobs repeat exactly). The legacy kernel computes in doubles
in the sim and in floats in the firmware (-ffp-contract=off): a decision a rounding flips shows as a count mismatch.
"""
import argparse, glob, json, math, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import boardtag

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
static uint16_t strip[TUBE_COUNT][PANEL_W * TUBE_HEIGHT_MAX];
static uint32_t fizzHash(int i) {   // the stepped state of one tube: live slots, spring clocks
#ifdef PIXELS_ONLY
  return 0;
#else
  const Tube &t = tubeAt(i);
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
  Params design = PRESET_DEFAULT; TubeState st[TUBE_COUNT]; uint32_t gen = 1;
  char line[256];
  while (fgets(line, sizeof line, stdin)) {
    line[strcspn(line, "\r\n")] = 0;
    char *eq = strchr(line, '='); if (!eq) return 4;
    *eq = 0; if (!setParam(design, line, eq + 1)) fprintf(stderr, "unknown param %s\n", line);
  }
  Params p[TUBE_COUNT]; for (int i = 0; i < TUBE_COUNT; i++) boardParams(design, p[i], TUBE_PX_SCALE(i), PX_SCALE_FIZZ);   // each tube at its px scale
  uint16_t *s[TUBE_COUNT]; TubeState *tb[TUBE_COUNT]; const Params *pp[TUBE_COUNT]; int top[TUBE_COUNT];
#if TUBE_COUNT == 3
  const FaceLayout lay = faceLayout(p[0], p[1], p[2]);
#else
  const FaceLayout lay = faceLayout(p[0], p[1]);
#endif
  for (int i = 0; i < TUBE_COUNT; i++) { s[i] = strip[i]; tb[i] = &st[i]; pp[i] = &p[i]; top[i] = lay.top(i); }
  uint32_t hash[TUBE_COUNT];
  seqRun(tb, pp, gen, s, top, [&](int frame, int i, const uint16_t *px) {   // the board's `X` line, + the fizz state
    hash[i] = seqHash(px, lay.rows(i) * PANEL_W);
    if (i < TUBE_COUNT - 1) return;
    printf("SEQ %d", frame);
    for (int k = 0; k < TUBE_COUNT; k++) printf(" %08x", hash[k]);
    printf(" fizz");
    for (int k = 0; k < TUBE_COUNT; k++) { int f, sl; const int live = fizzCounts(k, f, sl); printf(" %d/%d", live, f); }
    printf(" state");
    for (int k = 0; k < TUBE_COUNT; k++) printf(" %08x", fizzHash(k));
    printf("\n");
  });
  return 0;
}
'''

# --sim: the native side of the shared stepped jobs. stdin: design params `name=value`, `---`, then commands: `seed N`,
# `every F`, `tube I field value` (TubeState, before the first run), `set name value` (a design param from here on:
# every tube's params derived again, a new generation), `run n dt along across normal agitation`.
SIM_HARNESS = r"""
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include RENDER_SRC
static uint16_t strip[TUBE_COUNT][PANEL_W * TUBE_HEIGHT_MAX];
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
static bool setState(TubeState &s, const char *f, float v) {
  struct { const char *n; float TubeState::*m; } F[] = {{"fillTarget", &TubeState::fillTarget}, {"fillPos", &TubeState::fillPos},
    {"slugPos", &TubeState::slugPos}, {"angle", &TubeState::angle}, {"cap", &TubeState::cap}, {"light", &TubeState::light},
    {"edgeLight", &TubeState::edgeLight}, {"acrossTilt", &TubeState::acrossTilt}};
  for (auto &e : F) if (!strcmp(e.n, f)) { s.*e.m = v; return true; }
  return false;
}
static void emit(int step, int i) {   // one tube's state line (render-ref.ts fizzJob writes the same)
  const Tube &t = tubeAt(i);
  printf("S %d %d %d %llu %.9g %.9g", step, i, t.fizzN, (unsigned long long)fizzTestDraws(), t.springClock, t.springScatter);
  for (int k = 0; k < t.fizzN; k++) { const Fizz &f = t.fizz[k]; printf(" %.9g %.9g %.9g %.9g %.9g", f.x, f.y, f.v, f.life, f.z); }
  printf(" %.9g %d %.9g %d", t.fizzLen, t.fizzExposed, t.fizzShift, t.H);
  for (int r = 0; r < t.H; r++) printf(" %.9g", t.fizzSurf[r]);
  for (int r = 0; r < t.H; r++) printf(" %.9g", t.fizzSurfL[r]);
  printf("\n");
}
int main() {
  if (!render_init() || !physics_init()) return 3;
  Params design = PRESET_DEFAULT, p[TUBE_COUNT]; TubeState st[TUBE_COUNT]; uint32_t gen = 1; int every = 2, step = 0; bool started = false, changed = false;
  for (int i = 0; i < TUBE_COUNT; i++) {
    st[i].trace = traceBuf(i); st[i].traceWet = traceWetBuf(i);
    if (st[i].trace) memset(st[i].trace, 0, TUBE_LENGTH_PX * sizeof(uint16_t));
    if (st[i].traceWet) memset(st[i].traceWet, 0, TUBE_LENGTH_PX * sizeof(uint16_t));
  }
  auto derive = [&]() { for (int i = 0; i < TUBE_COUNT; i++) boardParams(design, p[i], TUBE_PX_SCALE(i), PX_SCALE_FIZZ); gen++; };
  auto frame = [&]() {
#if TUBE_COUNT == 3
    const FaceLayout lay = faceLayout(p[0], p[1], p[2]);
#else
    const FaceLayout lay = faceLayout(p[0], p[1]);
#endif
    for (int i = 0; i < TUBE_COUNT; i++) renderTube(i, st[i], p[i], gen, strip[i], nullptr, lay.top(i));
  };
  char line[512]; bool head = true;
  while (fgets(line, sizeof line, stdin)) {
    line[strcspn(line, "\r\n")] = 0;
    if (head) {
      if (!strcmp(line, "---")) { head = false; derive(); continue; }
      char *eq = strchr(line, '='); if (!eq) return 4;
      *eq = 0; if (!setParam(design, line, eq + 1)) fprintf(stderr, "unknown param %s\n", line);
      continue;
    }
    char a[64], b[64]; int n, i; float dt, along, across, normal, agit; unsigned long seed;
    if (sscanf(line, "seed %lu", &seed) == 1) fizzTestRng() = seed ? (uint32_t)seed : 1u;
    else if (sscanf(line, "every %d", &every) == 1) {}
    else if (sscanf(line, "tube %d %63s %63s", &i, a, b) == 3) { if (i >= TUBE_COUNT || !setState(st[i], a, atof(b))) return 5; }
    else if (sscanf(line, "set %63s %63s", a, b) == 2) { if (!setParam(design, a, b)) return 6; derive(); changed = true; }
    else if (sscanf(line, "run %d %f %f %f %f %f", &n, &dt, &along, &across, &normal, &agit) == 6) {
      if (!started || changed) frame();   // the first frame, and one after a params change: the new height's surfaces
      started = true; changed = false;
      for (int k = 0; k < n; k++) {
        for (int j = 0; j < TUBE_COUNT; j++) st[j].agitation = agit;
        for (int j = 0; j < TUBE_COUNT; j++) stepFizzTube(j, p[j], dt, along, across, agit);
        step++;
        if (step % every == 0) frame();
        for (int j = 0; j < TUBE_COUNT; j++) emit(step, j);   // after the step and its frame
      }
    }
    else return 7;
  }
  return 0;
}
"""
# The shared generator, counted: the test-only esp_random of --sim (the sim job's Math.random is the same).
SIM_RANDOM = ('#pragma once\n#include <cstdint>\n'
              'inline uint32_t &fizzTestRng() { static uint32_t s = 1; return s; }\n'
              'inline uint64_t &fizzTestDraws() { static uint64_t n = 0; return n; }\n'
              'inline uint32_t esp_random() { uint32_t &x = fizzTestRng(); x ^= x << 13; x ^= x >> 17; x ^= x << 5; fizzTestDraws()++; return x; }\n')
LOOK = ROOT / 'firmware/tools/testdata/tilted-fizz-board-look.json'   # the tilted-fizz board look (saved on lcd316 320w8-8)
SIM_BOARD = ('lcd316', '320w8-8')
DT = 0.02   # PHYS_DT
UP = (-1.0, 0.0, 0.0)   # (along, across, normal) of a vertical watch held upright

def _tilt(back_deg, across=0.0):
    """(along, across, normal) upright, tilted back by back_deg (face toward the sky; < 0: forward), rolled by `across`."""
    t = math.radians(back_deg); k = math.sqrt(max(0.0, 1 - across * across))
    return (-math.cos(t) * k, across, math.sin(t) * k)

def _run(n, pose, agitation=0.0, **set_):
    return {'n': n, 'dt': DT, 'along': pose[0], 'across': pose[1], 'normal': pose[2], 'agitation': agitation, **({'set': set_} if set_ else {})}

def _shake(n):
    """Shaking about upright: along / across swing at 4 Hz, agitation from 0.8 decaying to 0."""
    return [_run(1, (-1 + 0.3 * math.sin(k * DT * 25.13), 0.25 * math.sin(k * DT * 25.13), 0.2 * math.sin(k * DT * 25.13)),
                 0.8 * (1 - k / n)) for k in range(n)]

FILLS = {'hours': {'fillTarget': 0.85}, 'minutes': {'fillTarget': 0.4}, 'seconds': {'fillTarget': 0.5}}
# name: (design params over the board look, runs). Most fill upright first, then hold the pose. Steps of PHYS_DT.
SIM_JOBS = {
    'upright': ({}, [_run(300, UP)]),
    'back 15': ({}, [_run(100, UP), _run(250, _tilt(15))]),
    'forward 15': ({}, [_run(100, UP), _run(250, _tilt(-15))]),
    'across + back': ({}, [_run(100, UP), _run(250, _tilt(15, 0.3))]),
    'face up': ({}, [_run(100, UP), _run(250, (0.0, 0.0, 1.0))]),
    'face down': ({}, [_run(100, UP), _run(250, (0.0, 0.0, -1.0))]),
    'shaking': ({}, [_run(80, UP), *_shake(200), _run(70, UP)]),
    'crowded foam': ({'fizzCount': 240, 'fizzSourceRate': 60, 'fizzFoamLife': 6}, [_run(400, UP)]),
    'scattered, across': ({'fizzSource': 0, 'fizzCount': 200}, [_run(60, UP), _run(200, _tilt(10, 0.5))]),
    'height + mode changes': ({}, [_run(80, UP), _run(60, UP, tubeHeight=40), _run(60, UP, vertical=False),
                                   _run(60, UP, vertical=True), _run(60, _tilt(20, -0.4), tubeHeight=54)]),
    'landscape': ({'vertical': False, 'fizzSource': 0}, [_run(60, (0.0, 0.0, 1.0)), _run(150, (-0.3, 0.6, 0.74))]),
}
SIM_SEED = 0x2545F491
# Sim vs firmware in lockstep (each step from the firmware's state): per field, the largest difference accepted. Slot and
# draw counts, which slots are foam and on which side, are exact. Free bubbles: one step's float rounding. Parked foam
# (x, y): FOAM_TOL px, because the legacy packing tests contacts its last sweep left at exactly touching distance
# (settleFoam), so doubles and floats take or skip a push or a slide (<= FOAM_SLIDE * speed * dt) at random there.
SIM_TOL = {'x': 1e-3, 'y': 1e-3, 'v': 1e-6, 'life': 1e-4, 'z': 1e-6, 'springClock': 1e-4, 'springScatter': 1e-4}
FOAM_TOL = 2.0
FOAM_FIELDS = ('x', 'y')
SLOT_FIELDS = ('x', 'y', 'v', 'life', 'z')

def sim_main(a):
    import shutil
    board = a.board or SIM_BOARD[0]
    res = a.res if a.res is not None else SIM_BOARD[1] if not a.board else '320'
    lcd = board == 'lcd316'
    look = json.load(open(LOOK))
    unknown = [j for j in a.job or [] if j not in SIM_JOBS]
    if unknown: raise SystemExit(f'unknown job {unknown[0]!r}; jobs: {", ".join(SIM_JOBS)}')
    jobs = {k: v for k, v in SIM_JOBS.items() if not a.job or k in a.job}
    env = {**os.environ, 'LW_BOARD': board, 'LW_RES': res if lcd else '', 'LW_TUBES': str(a.tubes)}
    names = ['hours', 'minutes', 'seconds'][:a.tubes]
    with tempfile.TemporaryDirectory(prefix='watches-simsteps-') as tmp:
        tmp = Path(tmp)
        (tmp / 'esp_heap_caps.h').write_text('#pragma once\n#include <cstdlib>\n#define MALLOC_CAP_SPIRAM 0\n'
                                             'inline void *heap_caps_malloc(size_t n, int) { return std::calloc(n, 1); }\n')
        (tmp / 'esp_random.h').write_text(SIM_RANDOM)
        (tmp / 'h.cpp').write_text(SIM_HARNESS)
        flags = [*boardtag.tubes_flags(a.tubes), *(['-DBOARD_LCD316', *boardtag.res_flags(res, a.tubes)] if lcd else [])]
        build = subprocess.Popen([os.environ.get('CXX', 'c++'), '-std=c++17', '-O2', '-fno-strict-aliasing', '-ffp-contract=off', *flags,
                                  f'-DRENDER_SRC="{ROOT / "firmware/src/render.cpp"}"', '-I', str(tmp), '-I', str(ROOT / 'firmware/src'),
                                  '-I', str(ROOT / 'spec'), str(tmp / 'h.cpp'), str(ROOT / 'firmware/src/physics.cpp'), '-o', str(tmp / 'native')])
        # the sim job: render-ref.ts compiled into this run's own directory (not the shared node_modules cache)
        out = tmp / 'ts'
        tsc = subprocess.run(['npx', 'tsc', '-p', 'tools/render-ref.tsconfig.json', '--outDir', str(out)], cwd=ROOT / 'sim', capture_output=True, text=True)
        if tsc.returncode: raise SystemExit(f'sim: tsc failed\n{tsc.stdout}{tsc.stderr}')
        (out / 'package.json').write_text('{}')
        (out / 'node_modules' / '@spec').mkdir(parents=True)
        shutil.copy(out / 'spec' / 'layout.js', out / 'node_modules' / '@spec' / 'layout.js')
        if build.wait(): raise SystemExit('native: host build failed')

        def run(item):
            k, (name, (over, runs)) = item
            design = {**look, **over}   # the sim migrates from its version v (the firmware takes the fields as they are)
            script = ''.join(f'{f}={fmt(v)}\n' for f, v in design.items() if f != 'v') + f'---\nseed {SIM_SEED}\nevery 2\n'
            script += ''.join(f'tube {i} {f} {v!r}\n' for i, n in enumerate(names) for f, v in FILLS[n].items())
            for r in runs:
                script += ''.join(f'set {f} {fmt(v)}\n' for f, v in r.get('set', {}).items())
                script += f'run {r["n"]} {r["dt"]!r} {r["along"]!r} {r["across"]!r} {r["normal"]!r} {r["agitation"]!r}\n'
            nat = [subprocess.run([str(tmp / 'native')], input=script.encode(), capture_output=True) for _ in range(2)]
            if nat[0].returncode: return name, f'native exited {nat[0].returncode}: {nat[0].stderr.decode()[-300:]}', None
            if nat[0].stdout != nat[1].stdout: return name, 'native: two runs of the job differ (not deterministic)', None
            jobf, natf = tmp / f'job{k}.json', tmp / f'native{k}.txt'
            natf.write_bytes(nat[0].stdout)
            json.dump({'params': design, **{n: FILLS[n] for n in names},
                       'fizzSteps': {'seed': SIM_SEED, 'every': 2, 'runs': runs, **({} if a.free else {'lockstep': str(natf)})}}, open(jobf, 'w'))
            r = subprocess.run(['node', str(out / 'sim' / 'tools' / 'render-ref.js'), str(jobf), '-'], env=env, capture_output=True)
            if r.returncode: return name, f'sim exited {r.returncode}: {r.stderr.decode()[-500:]}', None
            if a.keep: (a.keep / f'{name}.native.txt').write_bytes(nat[0].stdout); (a.keep / f'{name}.sim.txt').write_bytes(r.stdout)
            return name, None, sim_compare(nat[0].stdout.decode(), r.stdout.decode())

        bad = 0
        with ThreadPoolExecutor(a.j) as ex:
            for name, err, res_ in ex.map(run, enumerate(jobs.items())):
                if err: bad += 1; print(f'{name:24s} ERROR {err}'); continue
                diff, steps, worst, most = res_
                if diff: bad += 1; print(f'{name:24s} DIFFERS {diff}'); continue
                print(f'{name:24s} {steps} steps match' + (f'; slots max {"/".join(map(str, most))}; worst '
                      + ', '.join(f'{f} {v:.2g}' for f, v in worst.items()) if a.v else ''))
        tag = f'{board}{"@" + res if lcd else ""}{"+t3" if a.tubes == 3 else ""}'
        print(f'{tag}: {len(jobs) - bad} of {len(jobs)} jobs match, sim vs firmware, step by step')
        sys.exit(1 if bad else 0)

def sim_compare(nat, sim):
    """(first mismatch or None, steps, worst difference per field, most slots per tube) of the two sides' state lines."""
    la, lb = nat.splitlines(), sim.splitlines()
    worst = {**{f: 0.0 for f in SIM_TOL}, **{f'foam {f}': 0.0 for f in FOAM_FIELDS}, 'surf': 0.0}; most = {}
    if len(la) != len(lb): return f'{len(la)} native state lines, {len(lb)} sim', 0, worst, []
    w = len(SLOT_FIELDS); L = SLOT_FIELDS.index('life')
    for x, y in zip(la, lb):
        p, q = x.split(), y.split()
        where = f'step {p[1]} tube {p[2]}'
        if p[:4] != q[:4]: return f'{where}: slots native {p[3]} sim {q[3]}', 0, worst, []
        most[p[2]] = max(most.get(p[2], 0), int(p[3]))
        if p[4] != q[4]: return f'{where}: draws native {p[4]} sim {q[4]}', 0, worst, []
        for f, i in (('springClock', 5), ('springScatter', 6)):
            d = abs(float(p[i]) - float(q[i])); worst[f] = max(worst[f], d)
            if d > SIM_TOL[f]: return f'{where}: {f} native {p[i]} sim {q[i]}', 0, worst, []
        for s in range(int(p[3])):
            o = 7 + w * s; lp, lq = float(p[o + L]), float(q[o + L])
            if (lp > 0) != (lq > 0) or (lp < 0) != (lq < 0): return f'{where} slot {s}: life native {lp} sim {lq}', 0, worst, []
            for j, f in enumerate(SLOT_FIELDS):
                d = abs(float(p[o + j]) - float(q[o + j]))
                k, tol = (f'foam {f}', FOAM_TOL) if lp != 0 and f in FOAM_FIELDS else (f, SIM_TOL[f])
                worst[k] = max(worst[k], d)
                if d > tol: return f'{where} slot {s}: {k} native {p[o + j]} sim {q[o + j]}', 0, worst, []
        e = 7 + w * int(p[3])   # the frame's surfaces (render parity): reported (-v), not held to a tolerance
        if p[e + 1] != q[e + 1] or p[e + 3] != q[e + 3]: return f'{where}: exposed / rows native {p[e + 1]} {p[e + 3]} sim {q[e + 1]} {q[e + 3]}', 0, worst, []
        for i in [e, e + 2, *range(e + 4, len(p))]:
            worst['surf'] = max(worst['surf'], abs(float(p[i]) - float(q[i])))
    return None, len(la) // max(1, len(most)), worst, [most[t] for t in sorted(most)]

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
    ap.add_argument('--reference', type=Path, help='the saved render.cpp to compare against (not with --sim)')
    ap.add_argument('--sim', action='store_true', help='stepped fizz state, sim vs firmware, on the shared seeded jobs (SIM_JOBS)')
    ap.add_argument('--job', action='append', help='--sim: only this job (repeatable; names: SIM_JOBS)')
    ap.add_argument('--keep', type=Path, help='--sim: write each job\'s state lines here (NAME.native.txt, NAME.sim.txt)')
    ap.add_argument('--free', action='store_true', help='--sim: the sim runs on from its own state (default lockstep: every step starts from the firmware state)')
    ap.add_argument('--fma', action='store_true', help='-mfma -ffp-contract=fast on both sides (fused multiply-add like the board)')
    ap.add_argument('--board', default=None, choices=('amoled191', 'lcd316'), help='default amoled191 (--sim: lcd316 --res 320w8-8)')
    ap.add_argument('--res', default=None, help='lcd316 res tag: rows + tube widths (320 / 320f / 320fh / 320fm, tools/boardtag.py)')
    ap.add_argument('--tubes', type=int, default=2, choices=(2, 3), help='3 = + the seconds tube (-DTUBE_COUNT=3)')
    ap.add_argument('--tiles', action='store_true', help='current side through the tiled band loop (-DTILE_RENDER=1)')
    ap.add_argument('--pixels-only', action='store_true', help='compare strips and counts, not the fizz state (struct Fizz changed on purpose)')
    ap.add_argument('-j', type=int, default=os.cpu_count() or 4)
    ap.add_argument('-v', action='store_true', help='print each preset\'s fizz counts: most per tube over the sequence and at the end')
    ap.add_argument('presets', nargs='*')
    a = ap.parse_args()
    if a.sim: return sim_main(a)
    if not a.reference: ap.error('--reference is required (or --sim)')
    a.board = a.board or 'amoled191'; a.res = a.res if a.res is not None else '320'
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
        board = [*boardtag.tubes_flags(a.tubes), *(['-DBOARD_LCD316', *boardtag.res_flags(a.res, a.tubes)] if lcd else [])]
        sides = [('reference', reference), ('current', ROOT / 'firmware/src/render.cpp')]
        builds = [subprocess.Popen([os.environ.get('CXX', 'c++'), '-std=c++17', '-O2', '-fno-strict-aliasing', *fp, *board,   # fizzHash reads floats as uint16_t
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
            return path, None, (first_diff(*outs), outs[1].count('\n'), outs)
        bad = 0
        with ThreadPoolExecutor(a.j) as ex:
            for path, err, res in ex.map(run, jobs):
                name = path if path.startswith('scene: ') else os.path.relpath(path, ROOT)
                if err: bad += 1; print(f'{name:40s} ERROR {err}'); continue
                diff, frames, outs = res
                if diff: bad += 1; print(f'{name:40s} DIFFERS\n  reference {diff[0]}\n  current   {diff[1]}')
                else: print(f'{name:40s} {frames} frames identical')
                if a.v:   # both sides' populations when they differ (a rewrite that is not exact must keep them close)
                    for side, out in zip(('reference', 'current') if diff else ('',), outs[::-1][:1] if not diff else outs):
                        rows = [(w := l.split())[w.index('fizz') + 1:w.index('fizz') + 1 + a.tubes] for l in out.splitlines()]   # 'live/foam' per tube
                        T = range(a.tubes); nm = 'hms'
                        most = [max(int(r[t].split('/')[0]) for r in rows) for t in T]
                        foam = [max(int(r[t].split('/')[1]) for r in rows) for t in T]
                        mean = [sum(int(r[t].split('/')[1]) for r in rows) / len(rows) for t in T]
                        print(f'  {side + " " if side else ""}fizz live max {" ".join(f"{nm[t]} {most[t]}" for t in T)}, foam max {" ".join(f"{nm[t]} {foam[t]}" for t in T)}'
                              f' mean {" ".join(f"{nm[t]} {mean[t]:.1f}" for t in T)}, end {" ".join(rows[-1])}')
        tag = f'{a.board}{"@" + a.res if lcd else ""}{"+t3" if a.tubes == 3 else ""}{" fma" if a.fma else ""}{" tiles" if a.tiles else ""}'
        print(f'{tag}: {len(jobs) - bad} of {len(jobs)} presets identical over the sequence')
        sys.exit(1 if bad else 0)

if __name__ == '__main__': main()
