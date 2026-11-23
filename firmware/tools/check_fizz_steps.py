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
the first step and after every 2nd, the fizz stepped at fixed inputs (along, across, normal, agitation; the vertical
kernel reads only the gain-free pose updatePose makes of them, the landscape one along / across). After every step each
tube's slot count and the generator's draw count, the vertical bodies' height key and postponed births (exact), the
spring clocks and every slot's fields (x y v life z, and the body's y z: within SIM_TOL; parked foam of the legacy
landscape kernel within FOAM_TOL) and the frame's inputs the kernel steps on (len, shift, surf / surfL, strokeR /
strokeL rows: SURF_TOL / STROKE_TOL; exposed, rows exact) are compared, every record's length checked and every field
finite on both sides; the first mismatch is reported.
Generation: after every frame each side's own fizz inputs of it (native F lines, sim G lines, written before any
input replaces the sim's) are compared, in both modes: len, shift, surf / surfL (SURF_TOL), strokeR / strokeL
(STROKE_TOL), exposed and rows exact; every F record is validated (frame, tube, rows, length, finite).
Modes: lockstep (default; each step from the firmware's state, surfaces and strokes) is a diagnostic: it erases
accumulated divergence. --free is common-input kernel parity, the acceptance mode for vertical jobs: the sim's state
runs free, and after each frame both kernels step on the firmware frame's fizz inputs (its F lines; render-ref checks
each record before using it), since the sim's drawTube computes them in doubles. LEGACY_JOBS (they run the landscape
kernel, doubles in the sim, floats in the firmware: a decision a rounding flips shows as a count mismatch) are reported
there as diagnostics. --free also runs each job once more as an independent full pipeline (the sim's own frame inputs,
no injection): information only, expected to drift; its first divergence step per job is reported.
The comparator's mutation self-checks (NaN / inf, a record too short / long, a surface, len, shift, a stroke, a foam
position moved; a bad or missing F record; a G surface or stroke moved) must all be rejected; render-ref must refuse a
corrupt inputs file. Each native job runs twice (identical output: the jobs repeat exactly).
"""
import argparse, glob, json, math, os, struct, subprocess, sys, tempfile
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
#ifndef FIZZ_C_WALL   // a reference render.cpp from before the gain-free pose argument (tilted fizz point 4): seq.h steps through this
void stepFizz(const Params &pH, const Params &pM, float dt, float along, float across, float agitation, const Pose &) { stepFizz(pH, pM, dt, along, across, agitation); }
#if TUBE_COUNT == 3
void stepFizz(const Params &pH, const Params &pM, const Params &pS, float dt, float along, float across, float agitation, const Pose &) { stepFizz(pH, pM, pS, dt, along, across, agitation); }
#endif
#endif
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
# `every F`, `tube I field value` (TubeState, before a run: a clock wrap's fill step by step), `set name value` (a design param from here on:
# every tube's params derived again, a new generation), `run n dt along across normal agitation`.
SIM_HARNESS = r"""
#include <cstdio>
#include <cstdlib>
#include <cstring>
static double parkWorst = -1e30; static long parkN = 0;   // the vertical kernel's parks (FIZZ_PARK_HOOK): how far short of its zone
#define FIZZ_PARK_HOOK(t, k, u, uc) (parkN++, parkWorst = (uc) - FOAM_CATCH - (u) > parkWorst ? (uc) - FOAM_CATCH - (u) : parkWorst)
struct Tube; static void motionBirth(const Tube &t, int k);   // births (FIZZ_BIRTH_HOOK): the MOTION line
#define FIZZ_BIRTH_HOOK(t, k) motionBirth(t, k)
static long plN = 0;   // settleFoam's placements in the tube stepping now (FIZZ_PLACE_HOOK): the PL lines, the settle's cost
#define FIZZ_PLACE_HOOK(t, s) (plN++)
#include RENDER_SRC
// MOTION (stderr, every job): over every step of a vertical tube, the largest move of a live bubble back down the tube
// (away from the end the rise heads for; not born that step) as a multiple of fizzSpeed dt (the rise's own step: the
// overdamped contact and the foam's packing stay within it), and the births: how many, the nearest to that end's
// surface (px). The stand job's expectation reads it (the board's 'fizz explosion' at the surface, 2026-11-22).
static float mvX0[TUBE_COUNT][FIZZ_POOL], mvV0[TUBE_COUNT][FIZZ_POOL]; static bool mvBorn[TUBE_COUNT][FIZZ_POOL];
static int mvSide = 1; static double mvDownWorst = 0, mvBirthGap = 1e30; static long mvBirths = 0;
static int mvTube(const Tube &t) { for (int i = 0; i < TUBE_COUNT; i++) if (&tubeAt(i) == &t) return i; return 0; }
static void motionBirth(const Tube &t, int k) {
  mvBorn[mvTube(t)][k] = true; mvBirths++; const Fizz &f = t.fizz[k];
  const double g = mvSide > 0 ? foamFront(t.fizzSurf, t.H, f.y, 1) - f.x : foamFront(t.fizzSurfL, t.H, f.y, -1) + f.x;
  if (g < mvBirthGap) mvBirthGap = g;
}
static void motionBefore(int i) { const Tube &t = tubeAt(i); for (int k = 0; k < FIZZ_POOL; k++) { mvX0[i][k] = k < t.fizzN ? t.fizz[k].x : 0; mvV0[i][k] = k < t.fizzN ? t.fizz[k].v : 0; mvBorn[i][k] = false; } }
static void motionAfter(int i, const Params &p, float dt) {
  const Tube &t = tubeAt(i); if (!t.bodyH || !(p.fizzSpeed > 0)) return;
  for (int k = 0; k < t.fizzN; k++) if (!mvBorn[i][k] && mvV0[i][k] != 0 && t.fizz[k].v != 0) {
    const double down = -mvSide * (double)(t.fizz[k].x - mvX0[i][k]) / (p.fizzSpeed * dt);
    if (down > mvDownWorst) mvDownWorst = down;
  }
}
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
static const Params *tubeP[TUBE_COUNT];   // each tube's params now (main)
static void emit(int step, int i) {   // one tube's state line (render-ref.ts fizzJob writes the same)
  const Tube &t = tubeAt(i);
  printf("S %d %d %d %llu %.9g %.9g %d %u", step, i, t.fizzN, (unsigned long long)fizzTestDraws(), t.springClock, t.springScatter, t.bodyH, (unsigned)t.fizzBlocked);
  for (int k = 0; k < t.fizzN; k++) {
    const Fizz &f = t.fizz[k]; const FizzBody &b = t.body[k];
    printf(" %.9g %.9g %.9g %.9g %.9g %.9g %.9g %d", f.x, f.y, f.v, f.life, f.z, b.y, b.z, (int)b.contact);
  }
  printf(" %.9g %d %.9g %d", t.fizzLen, t.fizzExposed, t.fizzShift, t.H);
  for (int r = 0; r < t.H; r++) printf(" %.9g", t.fizzSurf[r]);
  for (int r = 0; r < t.H; r++) printf(" %.9g", t.fizzSurfL[r]);
  for (int r = 0; r < t.H; r++) printf(" %.9g", t.strokeR[r]);
  for (int r = 0; r < t.H; r++) printf(" %.9g", t.strokeL[r]);
  printf(" %.9g %.9g %.9g\n", t.fizzLidT, t.fizzLidTau, t.fizzLidDelta);   // the desk view's lid: T, tau, delta
  if (t.bodyH) {   // vertical: live bodies (free and foam) outside the eroded disc (stderr; the containment expectation reads it)
    const float R = boreR(*tubeP[i]); int out = 0;
    for (int k = 0; k < t.fizzN; k++) {
      const Fizz &f = t.fizz[k]; const FizzBody &b = t.body[k]; const float a = R - fizzR(*tubeP[i], f.v);
      if (f.v != 0 && b.y * b.y + b.z * b.z > a * a * (1 + 1e-5f) + 1e-6f) out++;
    }
    if (out) fprintf(stderr, "OUT step %d tube %d: %d\n", step, i, out);
  }
}
// `selftest`: the vertical births (springSpawnV, fizzScatterV, ensureFizz) over tube heights, sizes, source rows,
// spreads and column profiles (a long straight column, a short one, a curved dish, a steep slant): contained in the
// eroded disc, row and tint level derived from the body, inside the row's span (the whole disc FOAM_CATCH inside both
// surfaces), a spring within its spread of (fizzSourceY, z = 0), postponed only without room (the size, or the span),
// uniform over the disc.
static void profileOf(Tube &t, int kind) {   // 0 straight 300 px, 1 short (6 px), 2 curved dish, 3 steep slant
  const float yc = fizzYc(t.H);
  for (int r = 0; r < t.H; r++) {
    const float q = yc > 0 ? (r - yc) / yc : 0;
    t.fizzSurf[r] = kind == 0 ? 300 : kind == 1 ? 6 : kind == 2 ? 40 + 30 * q * q : 20 + 3.0f * r;
    t.fizzSurfL[r] = kind == 2 ? -8 * q * q : 0;
    t.strokeR[r] = t.strokeL[r] = 0;
  }
  t.surfH = t.H;
}
static int birthSelftest() {
  Tube &t = tubeAt(0); long n = 0, bad = 0, postponed = 0, wrongPostpone = 0, spanNone = 0; double sum2 = 0, sumY = 0, sumZ = 0; long nU = 0;
  auto fail = [&](const char *what, float H, float y, float z, float a) { if (bad++ < 5) fprintf(stderr, "selftest: %s H %g y %g z %g a %g\n", what, H, y, z, a); };
  const int HS[] = {4, 6, 8, 12, 20, 40, 54, 80};
  const float SIZE[] = {2, 5, 9, 14}, VAR[] = {0, 0.5f}, SY[] = {0, 0.5f, 1, 1.3f}, SP[] = {0, 1, 4, 30};
  for (int prof = 0; prof < 4; prof++)
  for (int H : HS) for (float size : SIZE) for (float var : VAR) for (float sy : SY) for (float sp : SP) {
    Params p = PRESET_DEFAULT; p.vertical = true; p.glassWall = 3; p.tubeHeight = H; p.fizzSize = size; p.fizzSizeVar = var;
    p.fizzSourceY = sy; p.fizzSourceSpread = sp; p.fizzSourceX = 0.3f;
    t.H = tubeLayout(p).H; t.fizzShift = 0; profileOf(t, prof);
    const float R = boreR(p), aMax = R - fizzR(p, 0.5f + (FIZZ_SIZES - 0.5f) / FIZZ_SIZES);
    for (int rep = 0; rep < (prof ? 20 : 60); rep++) for (int kind = 0; kind < 2; kind++) {
      Fizz f{}; FizzBody b{}; const uint32_t blk = t.fizzBlocked; const int k = rep % 7;
      const bool ok = kind == 0 ? springSpawnV(t, p, f, b, k) : fizzScatterV(t, p, f, b, k, -1);
      n++;
      const float a = R - fizzR(p, f.v);
      if (!ok) {
        postponed++;
        float lo, hi; const bool span = aMax > 0 && fizzSpanV(t, f.y, fizzR(p, 1.5f), lo, hi);   // f.v is 0 now: the largest size's span
        if (!span) spanNone++;
        if (t.fizzBlocked != blk + 1 || f.v != 0 || (aMax > 0 && prof == 0)) { wrongPostpone++; fail("postponed", H, 0, 0, aMax); }
        continue;
      }
      const float r = fizzR(p, f.v);
      if (!(a > 0)) fail("born without room", H, b.y, b.z, a);
      if (b.y * b.y + b.z * b.z > a * a * (1 + 1e-5f) + 1e-6f) fail("outside the disc", H, b.y, b.z, a);
      if (f.y != fizzRowOf(t.H, b.y, a, fizzRowBias(k, f.v, fizzBias0(t))) || f.z != fizzLevelOf(b.z, a)) fail("row / level not derived", H, b.y, b.z, a);
      if (fabsf(f.y - fizzYc(t.H) - b.y) > fizzBias0(t) * (1 + 1e-5f)) fail("row bias past its bound", H, b.y, f.y, a);
      if (kind == 0) {
        const float y0 = (2 * sy - 1) * a;
        if (fabsf(b.z) > sp * (1 + 1e-5f) + 1e-5f) fail("spring off its depth", H, b.y, b.z, a);
        if (fabsf(b.y - y0) > sp * (1 + 1e-5f) + 1e-5f && b.y * b.y + b.z * b.z < a * a * (1 - 1e-4f)) fail("spring off its row", H, b.y, b.z, a);
      }
      if (f.x > discFit(t.fizzSurf, t.H, f.y, r, 1) - FOAM_CATCH + 1e-4f || -f.x > discFit(t.fizzSurfL, t.H, f.y, r, -1) - FOAM_CATCH + 1e-4f)
        fail("born outside its row's span", H, f.x, f.y, a);
      if (kind == 1 && prof == 0 && H == 54 && size == 5) { sum2 += (b.y * b.y + b.z * b.z) / (a * a); sumY += b.y / a; sumZ += b.z / a; nU++; }
    }
  }
  const double m2 = sum2 / nU, my = sumY / nU, mz = sumZ / nU;   // uniform over the disc: E rho^2 / a^2 = 1/2, E y = E z = 0
  if (fabs(m2 - 0.5) > 0.03 || fabs(my) > 0.05 || fabs(mz) > 0.05) { bad++; fprintf(stderr, "selftest: not uniform: E rho2 %g E y %g E z %g (%ld)\n", m2, my, mz, nU); }
  // ensureFizz (scattered, vertical) on each profile: every live slot in the disc and its row's span, the rest idle
  long ensured = 0, idle = 0;
  for (int prof = 0; prof < 4; prof++) {
    Params p = PRESET_DEFAULT; p.vertical = true; p.glassWall = 3; p.tubeHeight = 40; p.fizzSize = 5; p.fizzSizeVar = 0.5f; p.fizzSource = 0; p.fizzCount = 120;
    t.H = tubeLayout(p).H; t.fizzShift = 0; profileOf(t, prof); t.fizzN = 0; t.bodyH = 0;
    t.ensureFizz(p, 200, 0);
    const float R = boreR(p);
    for (int k = 0; k < t.fizzN; k++) {
      const Fizz &f = t.fizz[k]; const FizzBody &b = t.body[k];
      if (f.v == 0) { idle++; continue; }
      ensured++;
      const float r = fizzR(p, f.v), a = R - r;
      if (b.y * b.y + b.z * b.z > a * a * (1 + 1e-5f) + 1e-6f) fail("ensureFizz outside the disc", t.H, b.y, b.z, a);
      if (f.x > discFit(t.fizzSurf, t.H, f.y, r, 1) - FOAM_CATCH + 1e-4f || -f.x > discFit(t.fizzSurfL, t.H, f.y, r, -1) - FOAM_CATCH + 1e-4f)
        fail("ensureFizz outside its row's span", t.H, f.x, f.y, a);
    }
    if (prof == 1 && ensured && idle == 0) fail("ensureFizz born in a 6 px column", t.H, 0, 0, 0);
  }
  t.fizzN = 0; t.bodyH = 0;
  printf("SELFTEST births %ld postponed %ld (no span %ld, wrongly %ld) ensureFizz %ld live %ld idle; failures %ld uniform E rho2/a2 %.3f E y %.3f E z %.3f\n",
         n, postponed, spanNone, wrongPostpone, ensured, idle, bad, m2, my, mz);
  return bad ? 9 : 0;
}
// `selftest`, the bodies' rebuild (fizzBodiesFor): after a change of rows, glassWall, fizzSize or fizzSizeVar every live
// body is inside its new eroded disc at once (before any motion), its row and tint level derived; a body already inside
// keeps its (y, z); a size that no longer fits is retired (idle, fizzBlocked); no draws.
static int rebuildSelftest() {
  Tube &t = tubeAt(0); long bad = 0, checked = 0, kept = 0, retired = 0;
  auto fail = [&](const char *what, int k, float y, float z, float a) { if (bad++ < 5) fprintf(stderr, "selftest rebuild: %s slot %d y %g z %g a %g\n", what, k, y, z, a); };
  Params p = PRESET_DEFAULT; p.vertical = true; p.glassWall = 3; p.tubeHeight = 54; p.fizzSize = 5; p.fizzSizeVar = 0.5f; p.fizzSource = 0;
  t.H = tubeLayout(p).H; profileOf(t, 0); t.fizzN = 0; t.bodyH = 0;
  for (int k = 0; k < 200; k++) { t.fizz[k] = {0, 0, 0, 0, 0}; t.body[k] = {0, 0, 0, {0, 0, 0}}; fizzScatterV(t, p, t.fizz[k], t.body[k], k, -1); t.fizzN++; }
  fizzBodiesFor(t, p);
  struct Change { const char *what; float H, wall, size, var; };
  const Change CH[] = {{"rows 54 -> 20", 20, 3, 5, 0.5f}, {"rows 20 -> 54", 54, 3, 5, 0.5f}, {"glassWall 3 -> 8", 54, 8, 5, 0.5f},
                       {"fizzSize 5 -> 14", 54, 8, 14, 0.5f}, {"fizzSizeVar 0.5 -> 1", 54, 8, 14, 1}, {"rows 54 -> 12", 12, 8, 14, 1}};
  for (const Change &c : CH) {
    static FizzBody was[FIZZ_POOL]; for (int k = 0; k < t.fizzN; k++) was[k] = t.body[k];
    const uint64_t d0 = fizzTestDraws(); const uint32_t b0 = t.fizzBlocked;
    p.tubeHeight = c.H; p.glassWall = c.wall; p.fizzSize = c.size; p.fizzSizeVar = c.var; t.H = tubeLayout(p).H; profileOf(t, 0);
    fizzBodiesFor(t, p);
    if (fizzTestDraws() != d0) fail("draws in the rebuild", -1, 0, 0, 0);
    const float R = boreR(p); long ret = 0;
    for (int k = 0; k < t.fizzN; k++) {
      const Fizz &f = t.fizz[k]; const FizzBody &b = t.body[k];
      if (f.v == 0) continue;
      checked++;
      const float a = R - fizzR(p, f.v);
      if (!(a > 0)) { fail("kept without room", k, b.y, b.z, a); continue; }
      if (b.y * b.y + b.z * b.z > a * a * (1 + 1e-5f) + 1e-6f) fail(c.what, k, b.y, b.z, a);
      if (f.y != fizzRowOf(t.H, b.y, a, fizzRowBias(k, f.v, fizzBias0(t))) || f.z != fizzLevelOf(b.z, a)) fail("row / level not derived", k, b.y, b.z, a);
      if (was[k].y * was[k].y + was[k].z * was[k].z <= a * a && (b.y != was[k].y || b.z != was[k].z)) fail("moved although inside", k, b.y, b.z, a);
      else if (b.y == was[k].y && b.z == was[k].z) kept++;
    }
    for (int k = 0; k < t.fizzN; k++) if (t.fizz[k].v == 0 && was[k].y != 0) ret++;
    retired += t.fizzBlocked - b0;
    (void)ret;
  }
  if (retired == 0) fail("nothing retired by fizzSize 14 on a 12-row tube", -1, 0, 0, 0);
  t.fizzN = 0; t.bodyH = 0;
  printf("SELFTEST rebuild %d changes, %ld bodies checked inside at once (%ld kept their place), %ld retired; failures %ld\n", (int)(sizeof CH / sizeof CH[0]), checked, kept, retired, bad);
  return bad ? 10 : 0;
}
// `selftest`, the motion (point 4) against its analytic cases, one bubble of the mean size (U = fizzSpeed) in a long
// closed column far from both ends: free flight at 15 deg back keeps y and travels (z_w - z0) cot(theta) along the tube
// to the front glass in (z_w - z0) / (U sin theta) (within a step); on the wall it converges to the ridge as tan(psi / 2)
// = tan(psi0 / 2) exp(-t / tau_w), tau_w = (R - r) / (k_w U |b_perp|), never past it, x at k_w U b_x; face up / down it
// does not move along the tube and settles on the front / back high point; a roll moves the ridge and the rope follows
// without a jump (no step longer than k_w U dt); face up -> face down releases it into the liquid; an end closed by
// the glass stops it with the whole disc inside, no foam.
static int motionSelftest() {
  Tube &t = tubeAt(0); long bad = 0;
  auto fail = [&](const char *what, double got, double want) { if (bad++ < 8) fprintf(stderr, "selftest motion: %s: got %g want %g\n", what, got, want); };
  Params p = PRESET_DEFAULT; p.vertical = true; p.glassWall = 3; p.tubeHeight = 54; p.fizzSize = 5; p.fizzSizeVar = 0; p.fizzSpeed = 48;
  p.fizzSource = 1; p.fizzSourceRate = 0; p.fizzFoamLife = 1.5f; p.freeLiquid = false;
  t.H = tubeLayout(p).H; t.fizzShift = 0; t.fizzLen = 9000; t.fizzExposed = 0; t.springClock = 0; t.springScatter = 0;
  for (int r = 0; r < t.H; r++) { t.fizzSurf[r] = 5000; t.fizzSurfL[r] = -5000; t.strokeR[r] = t.strokeL[r] = 0; } t.surfH = t.H;
  const float R = boreR(p), r0 = fizzR(p, 1), a = R - r0, U = p.fizzSpeed, dt = 0.02f;
  const double th = 15 * M_PI / 180;
  auto put = [&](float x, float y, float z, int c) {
    t.fizzN = 1; t.fizz[0] = {x, 0, 1, 0, 0.5f}; t.body[0] = {y, z, (uint8_t)c, {0, 0, 0}};
    t.bodyH = t.H; t.bodyR = R; t.bodySize = p.fizzSize; t.bodyVar = p.fizzSizeVar;
  };
  auto step = [&](Pose q) { stepFizzTube(0, p, dt, -q.x, -q.y, 0, q); };
  const Pose back{(float)cos(th), 0, (float)sin(th)};
  double flightErr = 0, tauErr = 0, rollMax = 0, rollEnd = 0;
  {   // free flight to the front glass
    const float y0 = 0.3f * a, z0 = -0.2f * a, zw = sqrtf(a * a - y0 * y0);
    put(0, y0, z0, 0);
    const double want = (zw - z0) / tan(th), tw = (zw - z0) / (U * sin(th));
    int n = 0; float xPrev = 0;
    while (!(t.body[0].contact & FIZZ_C_WALL) && n < 2000) { xPrev = t.fizz[0].x; step(back); n++; if (!(t.body[0].contact & FIZZ_C_WALL) && t.body[0].y != y0) fail("y moved in free flight", t.body[0].y, y0); }
    if (n * dt < tw - 1e-4 || (n - 1) * dt > tw + 1e-4) fail("time to the wall (s)", n * dt, tw);
    if (xPrev > want + 1e-3 || xPrev + U * cos(th) * dt < want - 1e-3) fail("flight distance (px)", xPrev, want);
    flightErr = fabs(xPrev + 0.5 * U * cos(th) * dt - want);
  }
  {   // on the wall: convergence to the ridge (0, a), tau_w
    const double psi0 = 60 * M_PI / 180, tau = a / (FIZZ_KW * U * sin(th));
    put(0, a * (float)sin(psi0), a * (float)cos(psi0), FIZZ_C_WALL);
    double prev = psi0; float x0 = 0;
    for (int n = 1; n * dt <= 2 * tau; n++) {
      x0 = t.fizz[0].x; step(back);
      const double psi = atan2(t.body[0].y, t.body[0].z);
      if (psi > prev + 1e-6 || psi < -1e-6) fail("psi not monotone toward the ridge", psi, prev);
      prev = psi;
      if (fabs(t.fizz[0].x - x0 - FIZZ_KW * U * cos(th) * dt) > 1e-3) fail("x speed on the wall", t.fizz[0].x - x0, FIZZ_KW * U * cos(th) * dt);
      if (!(t.body[0].contact & FIZZ_C_WALL)) fail("left the wall", 0, 1);
      const double want = 2 * atan(tan(psi0 / 2) * exp(-n * dt / tau));
      tauErr = fmax(tauErr, fabs(tan(psi / 2) / tan(want / 2) - 1));
    }
    if (tauErr > 0.03) fail("tan(psi/2) against the exponential (rel)", tauErr, 0);
  }
  for (int dn = 0; dn < 2; dn++) {   // face up / down: no axial motion, to the front / back high point
    const Pose q{0, 0, dn ? -1.0f : 1.0f};
    put(100, 0.5f * a, -0.3f * a, 0);
    for (int n = 0; n < 500; n++) { step(q); if (t.fizz[0].x != 100) { fail("face up / down: axial motion", t.fizz[0].x, 100); break; } }
    if (fabsf(t.body[0].y) > 0.02f * a || fabsf(t.body[0].z - (dn ? -a : a)) > 0.02f * a) fail(dn ? "face down: not on the back high point" : "face up: not on the front high point", t.body[0].z, dn ? -a : a);
  }
  {   // roll: the ridge swings, the rope follows without a jump
    put(0, 0, a, FIZZ_C_WALL);
    float yPrev = 0, zPrev = a; const int N = 300;
    for (int n = 0; n < N; n++) {
      const float ac = 0.3f * sinf((float)M_PI * n / N);   // roll 0 -> 0.3 -> 0
      const Pose q{(float)cos(th), -ac, (float)sin(th)};
      const float m = sqrtf(q.x * q.x + q.y * q.y + q.z * q.z);
      step(Pose{q.x / m, q.y / m, q.z / m});
      const double d = hypot(t.body[0].y - yPrev, t.body[0].z - zPrev); rollMax = fmax(rollMax, d);
      if (d > FIZZ_KW * U * dt * 1.01 + 1e-4) fail("roll: a jump (px a step)", d, FIZZ_KW * U * dt);
      yPrev = t.body[0].y; zPrev = t.body[0].z;
    }
    rollEnd = t.body[0].y;
  }
  {   // release: on the front glass face up, then face down
    put(100, 0, a, FIZZ_C_WALL);
    step(Pose{0, 0, -1});
    if (t.body[0].contact & FIZZ_C_WALL) fail("face down: still on the front glass", t.body[0].contact, 0);
    if (fabsf(t.body[0].z - (a - U * dt)) > 1e-3f) fail("face down: released z", t.body[0].z, a - U * dt);
  }
  {   // a closed end: stops with the whole disc inside, rests on the glass, no foam
    for (int r = 0; r < t.H; r++) t.fizzSurf[r] = 150;
    put(100, 0, 0, 0);
    for (int n = 0; n < 300; n++) step(Pose{1, 0, 0});
    const float lim = discFit(t.fizzSurf, t.H, t.fizz[0].y, r0, 1);
    if (fabsf(t.fizz[0].x - lim) > 1e-4f || !(t.body[0].contact & FIZZ_C_END) || t.fizz[0].life != 0) fail("closed end", t.fizz[0].x, lim);
  }
  t.fizzN = 0; t.bodyH = 0;
  printf("SELFTEST motion flight |dx - (z_w - z0) cot| %.3g px, ridge tan(psi/2) rel err %.3g, roll max %.3g px/step (k_w U dt %.3g), back from the roll at y %.3g; failures %ld\n",
         flightErr, tauErr, rollMax, FIZZ_KW * U * dt, rollEnd, bad);
  return bad ? 11 : 0;
}
// `selftest`, containment of the move (point 4, fizzMoveV): from inside, on the wall (c WALL) or kicked past it (a stir,
// c free), with contact bits incl. a closed end, at eroded radii down to nearly fitting bubbles (a 1e-3 px), speeds up
// to far past the sliders' (2000 px/s) and steps up to 0.1 s, the forcing reversing at random between steps: every end
// point inside the eroded disc. The review's repro (a 0.5 on the front wall z 0.5, face down at 60 px/s, dt 0.02: 1.2
// px of flight) ends on the back wall, z -0.5, in contact, not past it at z -0.7.
static int containSelftest() {
  long bad = 0, n = 0, rel = 0, far = 0; double worst = 0;
  auto fail = [&](const char *what, double a, double y, double z) { if (bad++ < 8) fprintf(stderr, "selftest contain: %s: a %g y %g z %g\n", what, a, y, z); };
  {
    float y = 0, z = 0.5f; uint8_t c = FIZZ_C_WALL;
    fizzMoveV(y, z, c, 0.5f, 60, 0, -1, 1, 0.02f);
    if (fabsf(z + 0.5f) > 1e-5f || y != 0 || !(c & FIZZ_C_WALL)) fail("repro: not on the back wall", 0.5, y, z);
    if (!(z * z <= 0.25f * (1 + 1e-5f))) fail("repro: past the back wall", 0.5, y, z);
  }
  uint32_t s = 0x9E3779B9u;
  auto rnd = [&]() { s ^= s << 13; s ^= s >> 17; s ^= s << 5; return (s >> 8) * (1.0f / 16777216); };
  const float A[] = {1e-3f, 0.05f, 0.5f, 3, 20}, US[] = {1, 48, 270, 2000}, DT[] = {0.002f, 0.02f, 0.1f};
  for (float a : A) for (float U : US) for (float dt : DT) for (int trial = 0; trial < 150; trial++) {
    const int kind = trial % 3;   // 0 inside, 1 on the wall, 2 kicked past it
    const float rho = kind == 0 ? a * sqrtf(rnd()) : kind == 1 ? a : a * (1 + 0.5f * rnd()), phi = 6.2831853f * rnd();
    float y = rho * cosf(phi), z = rho * sinf(phi); uint8_t c = (uint8_t)((kind == 1 ? FIZZ_C_WALL : 0) | (rnd() < 0.3f ? FIZZ_C_END : 0));
    float bx = 2 * rnd() - 1, by = 2 * rnd() - 1, bz = 2 * rnd() - 1;
    for (int k = 0; k < 24; k++) {
      if (rnd() < 0.3f) { by = -by; bz = -bz; }   // the forcing reverses
      if (rnd() < 0.1f) { by = 0; bz = 0; }        // along the tube only
      const float m = sqrtf(bx * bx + by * by + bz * bz) + 1e-6f, qy = by / m, qz = bz / m, bp2 = qy * qy + qz * qz;
      const float inv = bp2 > 0 ? 1 / sqrtExact(bp2) : 0;
      const bool wall = c & FIZZ_C_WALL, inward = wall && qy * y + qz * z < 0;
      fizzMoveV(y, z, c, a, U, qy, qz, inv, dt); n++;
      if (inward) { rel++; if (U * dt * sqrtf(bp2) > 2 * a && (c & FIZZ_C_WALL)) far++; }
      const double e = sqrt((double)y * y + (double)z * z) / a - 1; worst = fmax(worst, e);
      if (!(y * y + z * z <= a * a * (1 + 1e-5f) + 1e-12f)) { fail("outside the eroded disc", a, y, z); break; }
      c &= ~FIZZ_C_END;
    }
  }
  if (!rel || !far) fail("no inward releases (or none across the bore) tried", rel, far, 0);
  printf("SELFTEST contain %ld moves (%ld inward releases, %ld across the bore onto the far wall), worst |p| / a - 1 %.2g; review repro on the back wall; failures %ld\n",
         n, rel, far, worst, bad);
  return bad ? 13 : 0;
}
// `selftest`, the endpoint support (point 5, review 2): the review's repro (r 5, no band, a profile rising 1 px a row: the
// whole disc's target 98, not the centre row's 100) for the support helper, the render clamp (fizzEndClampX) and the
// stepper's other open end; then the render clamp over random profiles (sloped, curved, receding), bands, depths and
// lens magnifications 0.7 .. 1.6 on both edges: every row of the drawn footprint (r along, r / m across) inside that
// row's L + P, and the clamp tight (a row on it) wherever it moved the bubble.
static int supportSelftest() {
  Tube &t = tubeAt(0); long bad = 0, n = 0, moved = 0; double slack = 0;
  auto fail = [&](const char *what, double got, double want) { if (bad++ < 8) fprintf(stderr, "selftest support: %s: got %g want %g\n", what, got, want); };
  Params p = PRESET_DEFAULT; p.vertical = true; p.glassWall = 3; p.tubeHeight = 54; p.fizzSize = 10; p.fizzSizeVar = 0;
  t.H = tubeLayout(p).H; const int H = t.H; const float yc = fizzYc(H), r = fizzR(p, 1), R = boreR(p);
  static float mag[TUBE_HEIGHT_MAX];
  const float y0 = floorf(yc);   // the repro's centre, on a row
  for (int iy = 0; iy < H; iy++) { t.fizzSurf[iy] = 100 + (iy - y0); t.fizzSurfL[iy] = -(100 + (iy - y0)); t.strokeR[iy] = t.strokeL[iy] = 0; mag[iy] = 1; }
  t.surfH = H;
  {
    float uc, ut; fizzEndSupport(t.fizzSurf, t.strokeR, H, 1, y0, r, 0, uc, ut);
    if (fabsf(ut - 98) > 1e-4f) fail("repro: support target", ut, 98);
    const Fizz f{100, y0, 1, 0, 0.5f}; const FizzBody b{0, 0, 0, {0, 0, 0}}; float kR, kL;
    const float x = fizzEndClampX(t, p, f, b, mag, kR, kL);
    if (fabsf(x - 98) > 1e-4f) fail("repro: render clamp", x, 98);
    // the stepper's other open end (the home edge, rising toward the time edge at no speed): past its target, the bubble
    // goes back to the whole disc's (on its row, the row bias in), short of the centre row's (S there, its old limit)
    p.fizzSpeed = 0; p.fizzSource = 1; p.fizzSourceRate = 0; p.fizzFoamLife = 1.5f; p.freeLiquid = true;
    for (int iy = 0; iy < H; iy++) t.fizzSurf[iy] = 5000;
    t.fizzShift = 0; t.fizzLen = 9000; t.fizzExposed = 3; t.springClock = 0; t.springScatter = 0;
    t.fizzN = 1; t.fizz[0] = {-99.5f, y0, 1, 0, 0.5f}; t.body[0] = {y0 - yc, 0, 0, {0, 0, 0}};
    t.bodyH = H; t.bodyR = R; t.bodySize = p.fizzSize; t.bodyVar = p.fizzSizeVar;
    stepFizzTube(0, p, 0.02f, -1, 0, 0, Pose{1, 0, 0});
    const float yr = t.fizz[0].y, centre = 100 + (yr - y0);
    fizzEndSupport(t.fizzSurfL, t.strokeL, H, -1, yr, r, 0, uc, ut);
    if (fabsf(-t.fizz[0].x - ut) > 1e-4f || !(ut < centre - 1.5f)) fail("repro: the other open end", -t.fizz[0].x, ut);
    t.fizzN = 0; t.bodyH = 0;
  }
  uint32_t q = 0x2545F491u;
  auto rnd = [&]() { q ^= q << 13; q ^= q >> 17; q ^= q << 5; return (q >> 8) * (1.0f / 16777216); };
  for (int trial = 0; trial < 4000; trial++) {
    const int kind = trial % 4;   // 0 sloped, 1 curved dish, 2 steep and receding (the bubble well past it), 3 ragged
    const float sl = 4 * rnd() - 2, cu = 60 * rnd() - 30, base = 100 + 40 * rnd(), band = rnd() < 0.3f ? 0 : 16 * rnd(), mg = 0.7f + 0.9f * rnd();
    for (int iy = 0; iy < H; iy++) {
      const float d = (iy - yc) / yc;
      const float v = kind == 0 ? base + sl * (iy - yc) : kind == 1 ? base + cu * d * d : kind == 2 ? base - 20 + 3 * sl * (iy - yc) : base + 6 * rnd();
      t.fizzSurf[iy] = v; t.fizzSurfL[iy] = v - 150 - 20 * rnd();   // the home edge (liquid frame x): 150 .. 170 px left of it
      t.strokeR[iy] = band * (0.5f + 0.5f * rnd()); t.strokeL[iy] = band * rnd();
      mag[iy] = mg * (1 + 0.1f * d * d);
    }
    const float rr = r, a = R - rr, phi = 6.2831853f * rnd(), rho = a * sqrtf(rnd());
    const FizzBody b{rho * cosf(phi), rho * sinf(phi), 0, {0, 0, 0}};
    const Fizz f{(rnd() < 0.5f ? base : base - 160) + 30 * rnd() - 15, yc + (2 * rnd() - 1) * a, 1, 0, 0.5f};
    float kR, kL; const float x = fizzEndClampX(t, p, f, b, mag, kR, kL); n++;
    const float m = fizzMag(mag, H, f.y, rr), ry = rr / m;
    double tight = 1e30;   // the smallest distance of a drawn row to its limit, both edges
    for (int s = 1; s >= -1; s -= 2) {
      const float *S = s > 0 ? t.fizzSurf : t.fizzSurfL, *B = s > 0 ? t.strokeR : t.strokeL; const float k = s > 0 ? kR : kL;
      for (int iy = (int)fmaxf(0, ceilf(f.y - ry)); iy <= (int)fminf(H - 1, floorf(f.y + ry)); iy++) {
        const double dy = (iy - f.y) * m, h = sqrt(fmax(0, (double)rr * rr - dy * dy)), L = s * S[iy] + k * B[iy];
        const double over = s * x + h - (L + rr * fmax(0.3, 1 - B[iy] / (2 * rr)));
        tight = fmin(tight, -over);
        if (over > 1e-3) { fail(s > 0 ? "render clamp: the drawn disc past L + P (time edge)" : "render clamp: the drawn disc past L + P (home edge)", over, 0); break; }
      }
    }
    if (x != f.x) { moved++; slack = fmax(slack, tight); if (tight > 1e-3) fail("render clamp: moved but no drawn row on its limit", tight, 0); }
  }
  printf("SELFTEST support repro 98 (helper, render clamp, other open end); render clamp %ld bubbles, %ld clamped, every drawn row inside L + P (slack of the tightest row <= %.2g px); failures %ld\n",
         n, moved, slack, bad);
  return bad ? 14 : 0;
}
// `selftest`, packing in physical coordinates (point 6, review 2; the surface model, docs/tilted-fizz-surface-model.md):
// settleFoam steps (dt 0.02, buoyancy along the tube unless stated) on pairs parked far from the surface (both
// unseated, gliding fizzSpeed dt), so the packing alone sets their separation. The review's repro (contact 5.5, axial
// 5, transverse 0, depth 3 apart: a 3D distance of 5.83, no overlap) keeps its separation. Contact: at depths 3 apart
// and 4 px along a pair parts in the surface plane symmetrically, each at most FOAM_PUSH fizzSpeed dt a step, the front
// gliding on, the rear waiting (never below where its step began), apart within 0.5 s; one above the other (one
// physical (y, z), two slots) it parts along the bore wall's tangent; at its surface (a profile 20 px ahead) the pair
// ends side by side, each at its own target, in-plane about m + FOAM_GAP apart; too big for two side by side
// (2 (R - r) < m): the rear waits behind the front, nothing steps back. A resident (seated at its target) under an
// arrival beneath / beside / ahead: never pushed down the tube, the arrival never below its step's start, apart in the
// end. Drift (one bubble): on a profile rising 1 px a row, k_w U dt sigma / (1 + sigma^2) a step up the slope; on a flat
// one with a 0.2 across buoyancy, k_w U dt 0.2; in the band's depth ramp (sigma_z > 0) toward the front glass. Every
// foam bubble's display row is fizzRowOf of its body, its tint level fizzLevelOf of its depth.
static int packSelftest() {
  Tube &t = tubeAt(0); long bad = 0;
  auto fail = [&](const char *what, double got, double want) { if (bad++ < 8) fprintf(stderr, "selftest pack: %s: got %.9g want %.9g\n", what, got, want); };
  Params p = PRESET_DEFAULT; p.vertical = true; p.glassWall = 3; p.tubeHeight = 54; p.fizzSize = 5; p.fizzSizeVar = 0; p.fizzSpeed = 48;
  t.H = tubeLayout(p).H; const int H = t.H; const float R = boreR(p), bias0 = fizzBias0(t);
  float r = fizzR(p, 1), m = 2 * r + 0.5f, a = R - r;
  auto surf = [&](float S, float slope = 0, float B = 0) { for (int iy = 0; iy < H; iy++) { t.fizzSurf[iy] = S + slope * iy; t.fizzSurfL[iy] = -5000; t.strokeR[iy] = B; t.strokeL[iy] = 0; } };
  surf(5000);
  t.surfH = H; t.bodyH = H; t.bodyR = R; t.bodySize = p.fizzSize; t.bodyVar = p.fizzSizeVar;
  const float dt = 0.02f, g = p.fizzSpeed * dt, pb = FOAM_PUSH * g;   // the step (the glide), a contact's in-plane bound
  float bu = 1, by = 0, bz = 0;
  auto derived = [&]() {
    for (int k = 0; k < t.fizzN; k++) {
      if (t.fizz[k].y != fizzRowOf(H, t.body[k].y, a, fizzRowBias(k, 1, bias0))) fail("display row not derived from the body", t.fizz[k].y, fizzRowOf(H, t.body[k].y, a, fizzRowBias(k, 1, bias0)));
      if (t.fizz[k].z != fizzLevelOf(t.body[k].z, a)) fail("tint level not derived from the depth", t.fizz[k].z, fizzLevelOf(t.body[k].z, a));
      if (t.body[k].y * t.body[k].y + t.body[k].z * t.body[k].z > a * a * (1 + 1e-5f)) fail("outside the eroded disc", hypot(t.body[k].y, t.body[k].z), a);
    }
  };
  double planeMax = 0;   // the largest in-plane move of a step (no drift: contacts only)
  auto stepOnce = [&]() {
    float y0[2], z0[2], x0[2];
    for (int k = 0; k < t.fizzN; k++) { y0[k] = t.body[k].y; z0[k] = t.body[k].z; x0[k] = t.fizz[k].x; t.fizz[k].life = 3; }
    settleFoam(t, p, p.fizzSpeed, t.fizzSurf, 1, dt, false, 0, t.strokeR, bu, by, bz); derived();
    for (int k = 0; k < t.fizzN; k++) {
      const double e = hypot(t.body[k].y - y0[k], t.body[k].z - z0[k]); if (bu == 1 && by == 0 && bz == 0) planeMax = fmax(planeMax, e);
      if (bu == 1 && by == 0 && bz == 0 && e > pb * (1 + 1e-5) + 1e-6) fail("moved in the plane past FOAM_PUSH fizzSpeed dt", e, pb);
      float uc, ut; fizzEndSupport(t.fizzSurf, t.strokeR, H, 1, t.fizz[k].y, r, fizzEndK(t.body[k].y, t.body[k].z, a, r, rowLerp(t.strokeR, H, t.fizz[k].y)), uc, ut);
      if (t.fizz[k].x < x0[k] - 1e-4f && fabsf(t.fizz[k].x - ut) > 1e-4f) fail("moved down the tube, not by its endpoint (nothing is pushed down)", t.fizz[k].x - x0[k], 0);
    }
  };
  auto pair = [&](float u0, float u1, float y0, float y1, float z0, float z1, int steps = 1) {
    t.fizzN = 2; t.foam->nOrder = 0;
    const float y[2] = {y0, y1}, z[2] = {z0, z1}, u[2] = {u0, u1};
    for (int k = 0; k < 2; k++) { t.body[k] = {y[k], z[k], 0, {0, 0, 0}}; t.fizz[k] = {u[k], fizzRowOf(H, y[k], a, fizzRowBias(k, 1, bias0)), 1, 3, fizzLevelOf(z[k], a)}; }
    for (int n = 0; n < steps; n++) stepOnce();
  };
  auto d3of = [&]() { const double du = t.fizz[0].x - t.fizz[1].x, dy = t.body[0].y - t.body[1].y, dz = t.body[0].z - t.body[1].z; return sqrt(du * du + dy * dy + dz * dz); };
  if (m != 5.5f) fail("contact distance", m, 5.5);
  pair(100, 95, 0, 0, 1.5f, -1.5f);
  if (t.fizz[0].x - t.fizz[1].x != 5 || t.body[0].y != 0 || t.body[1].y != 0 || t.body[0].z != 1.5f) fail("repro: pushed (x0 - x1)", t.fizz[0].x - t.fizz[1].x, 5);
  pair(100, 96, 0, 0, 1.5f, -1.5f);   // 5 px apart in 3D: parts in the plane, symmetric, capped; the rear waits
  {
    if (fabs(t.body[0].z + t.body[1].z) > 1e-5 || t.body[0].y != 0) fail("depth 3 apart: not symmetric in the plane", t.body[0].z + t.body[1].z, 0);
    if (fabs(t.fizz[0].x - (100 + g)) > 1e-4) fail("depth 3 apart: the front glides", t.fizz[0].x, 100 + g);
    if (!(t.body[0].z > 1.5f)) fail("depth 3 apart: not parted in the plane", t.body[0].z, 1.5);
    for (int n = 1; n < 25; n++) stepOnce();
    if (d3of() < m - 1e-4) fail("depth 3 apart: still overlapping after 0.5 s", d3of(), m);
  }
  const float yb = 0.25f * a;
  pair(100, 96, yb, yb, 0, 0);   // one physical (y, z), two slots (row biases differ): along the wall's tangent there
  {
    const float b0 = fizzRowBias(0, 1, bias0), b1 = fizzRowBias(1, 1, bias0);
    if (b0 == b1) fail("the two slots' row biases are equal (no test)", b0, b1);
    for (int k = 0; k < 2; k++) if (fabs(t.body[k].y - yb) > 1e-5) fail("one above the other: not along the wall's tangent (y moved)", t.body[k].y, yb);
    if (fabs(t.body[0].z + t.body[1].z) > 1e-5 || !(fabs(t.body[0].z - t.body[1].z) > 0)) fail("one above the other: parted in the plane", t.body[0].z - t.body[1].z, 2 * pb);
  }
  surf(120);   // their surface 20 px ahead: side by side there, one u
  pair(100, 96, yb, yb, 0, 0, 250);
  {
    const double du = t.fizz[0].x - t.fizz[1].x, q = hypot(t.body[0].y - t.body[1].y, t.body[0].z - t.body[1].z);
    for (int k = 0; k < 2; k++) {   // each at its own target (B 0: k plays no part)
      float uc, ut; fizzEndSupport(t.fizzSurf, t.strokeR, H, 1, t.fizz[k].y, r, 0, uc, ut);
      if (fabs(t.fizz[k].x - ut) > 1e-3) fail("at the surface: not at its target", t.fizz[k].x, ut);
    }
    if (fabs(du) > 0.5) fail("at the surface: not side by side (du)", du, 0);
    if (sqrt(du * du + q * q) < m - 1e-3 || q < m - 0.5) fail("at the surface: in-plane separation", q, m + FOAM_GAP);
  }
  // a resident (slot 0, seated at its target) and an arrival (slot 1) beneath / beside behind / ahead of it
  float uT;
  { t.body[0] = {0, 0.5f * a, 0, {0, 0, 0}}; t.fizz[0].y = fizzRowOf(H, 0, a, fizzRowBias(0, 1, bias0)); float uc; fizzEndSupport(t.fizzSurf, t.strokeR, H, 1, t.fizz[0].y, r, 0, uc, uT); }
  const float YO[] = {0, 1.5f, 3, 0.5f}, UO[] = {-4, -4, -2, -0.3f};
  int res = 0;
  for (int c = 0; c < 4; c++) {
    pair(uT, uT + UO[c], 0, YO[c], 0.5f * a, 0.5f * a, 60);   // stepOnce checks: nobody moved down the tube
    res++;
    if (d3of() < m - 0.05) fail("resident: the arrival still overlapping after 1.2 s", d3of(), c);
  }
  surf(5000);
  {   // drift: up a profile rising 1 px a row (sigma_y 1: k_w U dt / 2 a step), then a 0.2 across buoyancy on a flat one
    t.fizzN = 1; t.foam->nOrder = 0;
    surf(5000, 1);
    t.body[0] = {0, 0, 0, {0, 0, 0}}; t.fizz[0] = {100, fizzRowOf(H, 0, a, fizzRowBias(0, 1, bias0)), 1, 3, fizzLevelOf(0, a)};
    stepOnce();
    if (fabs(t.body[0].y - FIZZ_KW * g * 0.5f) > 1e-4f || t.body[0].z != 0) fail("drift up the profile's slope", t.body[0].y, FIZZ_KW * g * 0.5f);
    surf(5000); by = 0.2f; bu = sqrtf(1 - by * by);
    t.body[0] = {0, 0, 0, {0, 0, 0}}; t.fizz[0] = {100, fizzRowOf(H, 0, a, fizzRowBias(0, 1, bias0)), 1, 3, fizzLevelOf(0, a)};
    stepOnce();
    if (fabs(t.body[0].y - FIZZ_KW * g * by) > 1e-4f) fail("drift with the across buoyancy", t.body[0].y, FIZZ_KW * g * by);
    by = 0; bu = 1; surf(5000, 0, 8);   // in the band's depth ramp: toward the front glass (sigma_z > 0)
    const float z0 = 0.6f * a;
    t.body[0] = {0, z0, 0, {0, 0, 0}}; t.fizz[0] = {100, fizzRowOf(H, 0, a, fizzRowBias(0, 1, bias0)), 1, 3, fizzLevelOf(z0, a)};
    stepOnce();
    if (!(t.body[0].z > z0) || t.body[0].y != 0) fail("drift in the depth ramp: not toward the front glass", t.body[0].z - z0, 0);
    surf(5000);
  }
  p.fizzSize = 40; r = fizzR(p, 1); m = 2 * r + 0.5f; a = R - r; t.bodySize = p.fizzSize;   // 2 a < m: no room side by side
  pair(100, 80, 0, 0, 0, 0, 3);
  {
    const double q = hypot(t.body[0].y - t.body[1].y, t.body[0].z - t.body[1].z), gB = p.fizzSpeed * dt * (r * r) / (fizzR(p, 1) * fizzR(p, 1));
    if (!(2 * a < m) || q > 2 * a + 1e-4) fail("too big: parted in the plane past the bore", q, 2 * a);
    if (fabs(t.fizz[1].x - 80) > 1e-3) fail("too big: the rear waits (does not glide on, not back)", t.fizz[1].x, 80);
    if (fabs(t.fizz[0].x - (100 + 3 * gB)) > 1e-3) fail("too big: the front glides", t.fizz[0].x, 100 + 3 * gB);
  }
  t.fizzN = 0; t.bodyH = 0;
  printf("SELFTEST pack repro (m 5.5, du 5, dz 3) unmoved; depth-3 pair parted symmetrically in the plane, apart within 0.5 s; one above the other along the wall's tangent; at the surface side by side; too big: the rear waits; in the plane <= FOAM_PUSH fizzSpeed dt a step (worst %.3g px, bound %.3g); nothing moved down the tube but by its own endpoint; a resident and an arrival in %d placements apart; drift up the slope, with the across buoyancy, toward the front glass in the band's ramp; failures %ld\n",
         planeMax, pb, res, bad);
  return bad ? 15 : 0;
}
// `selftest`, foam crossing the side wall on a band (review 3 item 1; the pack test's bands are 0): r 2.5 on a flat
// profile with a 10 px band, fizzSpeed dt 0.96. A pair on the bore wall by the side, the front one pushing the other
// round it, where k (1 on the wall's front half, 0 on its back half) turns over: the review's repro moved the state by
// 0.001 px but the drawn bubble 10 px back. Over 60 settleFoam steps from on, near and behind its target, both sides,
// lens magnification 1 and 1.3, every foam bubble: its DRAWN centre (fizzEndClampX, the render clamp) moves at most
// fizzSpeed dt a step (+ 1e-3 px; lens 1.3: + 0.05 px), its state at most fizzSpeed dt down the tube and in the
// surface plane, never past its own physical endpoint (the whole-disc support of L + P, k from its body), inside the
// eroded disc.
static int sideSelftest() {
  Tube &t = tubeAt(0); long bad = 0, n = 0, crossed = 0; double worstR = 0, worstS = 0, worstP = 0, worstE = -1e30;
  auto fail = [&](const char *what, double got, double want) { if (bad++ < 8) fprintf(stderr, "selftest side: %s: got %.9g want %.9g\n", what, got, want); };
  Params p = PRESET_DEFAULT; p.vertical = true; p.glassWall = 3; p.tubeHeight = 54; p.fizzSize = 5; p.fizzSizeVar = 0; p.fizzSpeed = 48;
  t.H = tubeLayout(p).H; const int H = t.H; const float R = boreR(p), bias0 = fizzBias0(t), r = fizzR(p, 1), a = R - r, dt = 0.02f, g = p.fizzSpeed * dt;
  static float mag[TUBE_HEIGHT_MAX];
  for (int iy = 0; iy < H; iy++) { t.fizzSurf[iy] = 100; t.fizzSurfL[iy] = -5000; t.strokeR[iy] = 10; t.strokeL[iy] = 0; }
  t.surfH = H; t.bodyH = H; t.bodyR = R; t.bodySize = p.fizzSize; t.bodyVar = p.fizzSizeVar;
  auto target = [&](int k) { float uc, ut; const FizzBody &b = t.body[k];
    fizzEndSupport(t.fizzSurf, t.strokeR, H, 1, t.fizz[k].y, r, fizzEndK(b.y, b.z, a, r, rowLerp(t.strokeR, H, t.fizz[k].y)), uc, ut); return ut; };
  auto drawn = [&](int k) { float kR, kL; return fizzEndClampX(t, p, t.fizz[k], t.body[k], mag, kR, kL); };
  const float MG[] = {1, 1.3f}, ZA[] = {0.05f, 0.3f, 1, 2.5f}, GAP[] = {3, 4.5f}, BEHIND[] = {0, 0.5f, 3, 12};
  for (float mg : MG) for (float zA : ZA) for (float gap : GAP) for (float behind : BEHIND) for (int sy = -1; sy <= 1; sy += 2) {
    for (int iy = 0; iy < H; iy++) mag[iy] = mg;
    const float tolR = mg == 1 ? 1e-3f : 0.05f, phA = acosf(zA / a), phB = phA - gap / a;
    const float Y[2] = {sy * a * sinf(phA), sy * a * sinf(phB)}, Z[2] = {zA, a * cosf(phB)};
    t.fizzN = 2; t.foam->nOrder = 0;
    for (int k = 0; k < 2; k++) {
      t.body[k] = {Y[k], Z[k], 0, {0, 0, 0}}; t.fizz[k] = {0, fizzRowOf(H, Y[k], a, fizzRowBias(k, 1, bias0)), 1, 3, fizzLevelOf(Z[k], a)};
      t.fizz[k].x = target(k) - behind;
    }
    for (int s = 0; s < 60; s++) {
      float x0[2], y0[2], z0[2], d0[2];
      for (int k = 0; k < 2; k++) { x0[k] = t.fizz[k].x; y0[k] = t.body[k].y; z0[k] = t.body[k].z; d0[k] = drawn(k); t.fizz[k].life = 3; }
      settleFoam(t, p, p.fizzSpeed, t.fizzSurf, 1, dt, false, 0, t.strokeR);
      for (int k = 0; k < 2; k++) {
        const FizzBody &b = t.body[k]; n++;
        const double dR = fabs(drawn(k) - d0[k]), dS = x0[k] - t.fizz[k].x, dP = hypot(b.y - y0[k], b.z - z0[k]), over = t.fizz[k].x - target(k);
        worstR = fmax(worstR, dR - g); worstS = fmax(worstS, dS); worstP = fmax(worstP, dP); worstE = fmax(worstE, over);
        if (dR > g + tolR) fail("the drawn bubble moved more than fizzSpeed dt", dR, g);
        if (dS > g + 1e-4) fail("moved back down the tube more than fizzSpeed dt", dS, g);
        if (dP > g + 1e-4) fail("moved in the surface plane more than fizzSpeed dt", dP, g);
        if (over > 1e-4) fail("past its own physical endpoint", t.fizz[k].x, target(k));
        if (b.y * b.y + b.z * b.z > a * a * (1 + 1e-5f)) fail("outside the eroded disc", hypot(b.y, b.z), a);
        if (t.fizz[k].y != fizzRowOf(H, b.y, a, fizzRowBias(k, 1, bias0))) fail("display row not derived from the body", t.fizz[k].y, fizzRowOf(H, b.y, a, fizzRowBias(k, 1, bias0)));
      }
    }
    if (t.body[0].z < 0) crossed++;
  }
  t.fizzN = 0; t.bodyH = 0;
  printf("SELFTEST side wall, 10 px band: %ld bubble-steps, drawn move worst fizzSpeed dt %+.3g px, back down worst %.3g px, in the plane worst %.3g px (fizzSpeed dt %.3g), past the endpoint worst %.3g px; %ld of %d pairs crossed to the back half; failures %ld\n",
         n, worstR, worstS, worstP, g, worstE, crossed, 2 * 4 * 2 * 4 * 2, bad);
  return bad ? 16 : 0;
}
// `selftest`, the wall contact after a held contact (review 3 item 2): a big free bubble (r 7.5, eroded radius 16) on the
// front wall, nearly along the tube, meets a smaller foam bubble (r 2.5) ahead and nearer the glass: the contact deflects
// it inward, off the wall, so it is no longer on the wall (FIZZ_C_WALL clear). The foam gone, the following step is
// free flight from there (x by U bx dt, z by U bz dt), not put back on the wall and slid at FIZZ_KW. A deflection
// that leaves it on the circle (no inward part) keeps the contact.
static int wallFlagSelftest() {
  Tube &t = tubeAt(0); long bad = 0;
  auto fail = [&](const char *what, double got, double want) { if (bad++ < 8) fprintf(stderr, "selftest wall flag: %s: got %.9g want %.9g\n", what, got, want); };
  Params p = PRESET_DEFAULT; p.vertical = true; p.glassWall = 3; p.tubeHeight = 54; p.fizzSize = 10; p.fizzSizeVar = 1; p.fizzSpeed = 48;
  p.fizzSource = 1; p.fizzSourceRate = 0; p.fizzFoamLife = 3; p.freeLiquid = false;
  t.H = tubeLayout(p).H; t.fizzShift = 0; t.fizzLen = 9000; t.fizzExposed = 1; t.springClock = 0; t.springScatter = 0;
  for (int r = 0; r < t.H; r++) { t.fizzSurf[r] = 5000; t.fizzSurfL[r] = -5000; t.strokeR[r] = t.strokeL[r] = 0; } t.surfH = t.H;
  const float R = boreR(p), rB = fizzR(p, 1.5f), rS = fizzR(p, 0.5f), a = R - rB, rref = fizzR(p, 1), U = p.fizzSpeed * rB * rB / (rref * rref), dt = 0.02f;
  t.bodyH = t.H; t.bodyR = R; t.bodySize = p.fizzSize; t.bodyVar = p.fizzSizeVar; t.foam->nOrder = 0;
  const float bz = 0.05f, bx = sqrtf(1 - bz * bz); const Pose q{bx, 0, bz};
  float zHeld = 0, dx2 = 0, dz2 = 0;
  for (int kind = 0; kind < 2; kind++) {   // 0: the foam nearer the glass (inward deflection), 1: straight ahead on the axis line (none)
    t.fizzN = 2;
    t.fizz[0] = {100, 0, 1.5f, 0, 0.5f}; t.body[0] = {0, a, FIZZ_C_WALL, {0, 0, 0}};
    t.fizz[1] = {109, 0, 0.5f, 3, 0.5f}; t.body[1] = {0, kind == 0 ? a + 3 : a, 0, {0, 0, 0}};
    for (int k = 0; k < 2; k++) { const float ak = R - fizzR(p, t.fizz[k].v); t.fizz[k].y = fizzRowOf(t.H, t.body[k].y, ak, fizzRowBias(k, t.fizz[k].v, fizzBias0(t))); t.fizz[k].z = fizzLevelOf(t.body[k].z, ak); }
    if (fabsf(a - 16) > 1e-5f || !(rS < rB)) fail("setup: eroded radius", a, 16);
    stepFizzTube(0, p, dt, -bx, 0, 0, q);
    const FizzBody &b = t.body[0]; const float d = hypotf(b.y, b.z);
    if (kind == 0) {
      zHeld = b.z;
      if (!(d < a - 0.1f)) fail("inward deflection: not moved off the wall", d, a - 0.1);
      if (b.contact & FIZZ_C_WALL) fail("inward deflection: still on the wall", b.contact, 0);
      const float x1 = t.fizz[0].x, z1 = b.z;
      t.fizz[1].v = 0; t.fizz[1].life = 0;   // the foam gone: the following step
      stepFizzTube(0, p, dt, -bx, 0, 0, q);
      dx2 = t.fizz[0].x - x1; dz2 = t.body[0].z - z1;
      if (fabsf(dx2 - U * bx * dt) > 1e-3f) fail("following step: not free flight along the tube", dx2, U * bx * dt);
      if (fabsf(dz2 - U * bz * dt) > 1e-4f) fail("following step: not free flight across (put back on the wall?)", dz2, U * bz * dt);
    } else if (!(b.contact & FIZZ_C_WALL) || fabsf(d - a) > 1e-4f) fail("held on the axis line: left the wall", d, a);
  }
  t.fizzN = 0; t.bodyH = 0;
  printf("SELFTEST wall flag: r 7.5 held by r 2.5 foam, z %.6g -> %.6g, off the wall; the following step free (dx %.4g = U bx dt %.4g, dz %.4g = U bz dt %.4g); held on the axis line it stays on the wall; failures %ld\n",
         a, zHeld, dx2, U * bx * dt, dz2, U * bz * dt, bad);
  return bad ? 17 : 0;
}
// `selftest`, a free bubble behind a lone foam bubble on the front ridge (review 3 item 5), stand-like pose (13 deg back,
// no roll: the ridge at y 0 on the front glass), a 6 px band, the foam at its target with a long life. Exactly centred
// (the same (y, z)) it waits behind the foam: an admissible symmetric rest (held, never parked by the contact, nothing
// recycled). Offset across by 0.05 .. 3 px, with the bore clear beside the foam, it slides round it and parks in its
// own zone beside it: 1 px and more within LONE_T; a near-symmetric one later, its offset growing at the frictionless
// contact's rate (the approach's tangential share, ~ e^(t / tau), tau = m / (k_w U b_x): t(0.05) - t(0.25) = tau ln 5,
// within 25%), not stuck; the resident is never pushed down the tube, keeps its slot and its life runs down.
static int loneSelftest() {
  Tube &t = tubeAt(0); long bad = 0;
  auto fail = [&](const char *what, double got, double want) { if (bad++ < 8) fprintf(stderr, "selftest lone: %s: got %.9g want %.9g\n", what, got, want); };
  Params p = PRESET_DEFAULT; p.vertical = true; p.glassWall = 3; p.tubeHeight = 54; p.fizzSize = 5; p.fizzSizeVar = 0; p.fizzSpeed = 48;
  p.fizzSource = 1; p.fizzSourceRate = 0; p.fizzFoamLife = 10; p.freeLiquid = false;
  t.H = tubeLayout(p).H; t.fizzShift = 0; t.fizzLen = 400; t.fizzExposed = 1; t.springClock = 0; t.springScatter = 0;
  for (int r = 0; r < t.H; r++) { t.fizzSurf[r] = 300; t.fizzSurfL[r] = 0; t.strokeR[r] = 6; t.strokeL[r] = 0; } t.surfH = t.H;
  const int H = t.H; const float R = boreR(p), r = fizzR(p, 1), a = R - r, dt = 0.02f, bias0 = fizzBias0(t);
  const double th = 13 * M_PI / 180; const Pose q{(float)cos(th), 0, (float)sin(th)};
  t.bodyH = H; t.bodyR = R; t.bodySize = p.fizzSize; t.bodyVar = p.fizzSizeVar;
  const float OFF[] = {0, 0.05f, 0.25f, 1, 3};   // px across (along the wall) from the ridge
  const float LONE_T = 1.0f;
  float tPark[5]; long held0 = 0;
  for (int c = 0; c < 5; c++) {
    t.fizzN = 2; t.foam->nOrder = 0;
    t.body[0] = {0, a, 0, {0, 0, 0}}; t.fizz[0] = {0, fizzRowOf(H, 0, a, fizzRowBias(0, 1, bias0)), 1, 9, fizzLevelOf(a, a)};
    { float uc, ut; fizzEndSupport(t.fizzSurf, t.strokeR, H, 1, t.fizz[0].y, r, fizzEndK(0, a, a, r, rowLerp(t.strokeR, H, t.fizz[0].y)), uc, ut); t.fizz[0].x = ut; }
    const float ps = OFF[c] / a;   // the free bubble on the wall, behind
    t.body[1] = {a * sinf(ps), a * cosf(ps), FIZZ_C_WALL, {0, 0, 0}}; t.fizz[1] = {t.fizz[0].x - 20, fizzRowOf(H, t.body[1].y, a, fizzRowBias(1, 1, bias0)), 1, 0, fizzLevelOf(t.body[1].z, a)};
    float life = t.fizz[0].life;
    parkWorst = -1e30; parkN = 0; tPark[c] = -1; long held = 0;
    for (int n = 0; n < 150; n++) {
      const float x1 = t.fizz[1].x, x0 = t.fizz[0].x;
      stepFizzTube(0, p, dt, -q.x, 0, 0, q);
      if (t.fizzN < 2 || t.fizz[0].v != 1 || !(t.fizz[0].life > 0 && t.fizz[0].life < life)) { fail("the foam recycled / its life not running down", t.fizz[0].life, life); break; }
      life = t.fizz[0].life;
      { float uc, ut; fizzEndSupport(t.fizzSurf, t.strokeR, H, 1, t.fizz[0].y, r, fizzEndK(t.body[0].y, t.body[0].z, a, r, rowLerp(t.strokeR, H, t.fizz[0].y)), uc, ut);
        if (t.fizz[0].x < x0 - 1e-4f && fabsf(t.fizz[0].x - ut) > 1e-4f) { fail("the resident pushed down the tube (not by its endpoint)", t.fizz[0].x - x0, 0); break; } }
      if (t.fizz[1].life != 0) { tPark[c] = (n + 1) * dt; break; }
      if (t.fizz[1].x - x1 < 0.5f * p.fizzSpeed * dt * FIZZ_KW) held++;
    }
    if (c == 0) held0 = held;
    if (parkN && !(parkWorst < 0)) fail("parked short of its own zone (by the contact)", parkWorst, 0);
    if (c == 0 && (tPark[c] >= 0 || held < 50)) fail("centred: did not wait behind the foam", tPark[c], -1);
    if (c > 0 && !(tPark[c] >= 0 && tPark[c] <= (OFF[c] >= 1 ? LONE_T : 3 * LONE_T))) fail("offset: did not slide round the foam in time (s)", tPark[c], OFF[c] >= 1 ? LONE_T : 3 * LONE_T);
  }
  const double tau = (2 * r + 0.5) / (FIZZ_KW * p.fizzSpeed * cos(th)), tauM = (tPark[1] - tPark[2]) / log(5.0);
  if (!(fabs(tauM / tau - 1) < 0.25)) fail("near-symmetric: the offset's growth time (s)", tauM, tau);
  t.fizzN = 0; t.bodyH = 0;
  printf("SELFTEST lone ridge foam: centred waits (%ld steps held of 150), offset 0.05 / 0.25 / 1 / 3 px parks beside it after %.2f / %.2f / %.2f / %.2f s, offset growth time %.3f s (m / k_w U b_x %.3f), the resident never pushed down, not recycled; failures %ld\n",
         held0, tPark[1], tPark[2], tPark[3], tPark[4], tauM, tau, bad);
  return bad ? 18 : 0;
}
// `selftest`, chain parking (point 6): a straight column with a free time edge, one foam bubble parked at it, a chain of
// bubbles behind it at the same depth and row, each touching the next. Over 300 steps a bubble only ever starts a foam
// life inside its own endpoint zone (u > uc - FOAM_CATCH), never by the contact; the chain is held back behind the foam.
static int chainSelftest() {
  Tube &t = tubeAt(0); long bad = 0, parks = 0; double worst = 0;
  Params p = PRESET_DEFAULT; p.vertical = true; p.glassWall = 3; p.tubeHeight = 54; p.fizzSize = 5; p.fizzSizeVar = 0; p.fizzSpeed = 48;
  p.fizzSource = 1; p.fizzSourceRate = 0; p.fizzFoamLife = 4; p.freeLiquid = false;
  t.H = tubeLayout(p).H; t.fizzShift = 0; t.fizzLen = 400; t.fizzExposed = 1; t.springClock = 0; t.springScatter = 0;
  for (int r = 0; r < t.H; r++) { t.fizzSurf[r] = 300; t.fizzSurfL[r] = 0; t.strokeR[r] = 6; t.strokeL[r] = 0; } t.surfH = t.H;
  const float R = boreR(p), r0 = fizzR(p, 1), a = R - r0, m = 2 * r0 + 0.5f;
  t.bodyH = t.H; t.bodyR = R; t.bodySize = p.fizzSize; t.bodyVar = p.fizzSizeVar; t.foam->nOrder = 0;
  const int N = 12; t.fizzN = N;
  for (int k = 0; k < N; k++) {
    t.body[k] = {0, 0, 0, {0, 0, 0}};
    t.fizz[k] = {300 - r0 - k * (m - 0.2f), fizzRowOf(t.H, 0, a, fizzRowBias(k, 1, fizzBias0(t))), 1, k == 0 ? 3.5f : 0, 0.5f};
  }
  parkWorst = -1e30; parkN = 0; long held = 0;
  for (int n = 0; n < 300; n++) {
    float x0[FIZZ_POOL]; for (int k = 0; k < t.fizzN; k++) x0[k] = t.fizz[k].x;
    stepFizzTube(0, p, 0.02f, -1, 0, 0, Pose{1, 0, 0});
    for (int k = 0; k < t.fizzN; k++) if (t.fizz[k].v != 0 && t.fizz[k].life == 0 && t.fizz[k].x - x0[k] < 0.5f * p.fizzSpeed * 0.02f) held++;   // pushed back by the foam
  }
  parks = parkN; worst = parkWorst;
  if (parks == 0 || !(worst < 0)) { bad++; fprintf(stderr, "selftest chain: %ld parks, worst %g px short of the zone\n", parks, worst); }
  if (held == 0) { bad++; fprintf(stderr, "selftest chain: the foam never held a bubble back\n"); }
  t.fizzN = 0; t.bodyH = 0;
  printf("SELFTEST chain %d bubbles: %ld parks, each inside its own zone (worst %.3g px past its start), %ld bubble-steps held back by the foam; failures %ld\n", N, parks, -worst, held, bad);
  return bad ? 12 : 0;
}
// `selftest`, the desk view's lid (docs/tilted-fizz-deskview.md "Fizz"): the time edge's S the front contact line W - T z_R,
// B = 2 T z_R the lid (S + B the back line, S + B / 2 = W flat), the stand's tau / delta. Three same-row foam bubbles
// (row yc: y = -bias) at the front glass, mid-bore and the back glass glide from 3r below to their endpoints: L = S + k B,
// k = (z_R - z) / 2 z_R, less r, plus P = r pf; the front one ends at the front line, the back one at the back line, the
// middle between; on the level plane nothing drifts in (y, z) (sigma_z = -tan tau, buoyancy along its normal); the render
// clamp keeps each where it is (it sits on its own target), with the veil's exemption kR 1.
static int lidSelftest() {
  Tube &t = tubeAt(0); long bad = 0;
  auto fail = [&](const char *what, double got, double want) { if (bad++ < 8) fprintf(stderr, "selftest lid: %s: got %.9g want %.9g\n", what, got, want); };
  Params p = PRESET_DEFAULT; p.vertical = true; p.glassWall = 3; p.tubeHeight = 55; p.fizzSize = 5; p.fizzSizeVar = 0; p.fizzSpeed = 48;
  t.H = tubeLayout(p).H; const int H = t.H; const float R = boreR(p), bias0 = fizzBias0(t), r = fizzR(p, 1), a = R - r, dt = 0.02f, yc = fizzYc(H);
  const float tau = 0.2217f, delta = 0.1274f, T = tanf(tau) + tanf(delta), W = 300;   // the stand (13 deg back), e 20 deg
  static float mag[TUBE_HEIGHT_MAX];
  for (int iy = 0; iy < H; iy++) {
    const float dy = iy - yc, zr = sqrtf(fmaxf(0, R * R - dy * dy));
    t.fizzSurf[iy] = W - T * zr; t.strokeR[iy] = 2 * T * zr; t.fizzSurfL[iy] = -5000; t.strokeL[iy] = 0; mag[iy] = 1;
  }
  t.surfH = H; t.bodyH = H; t.bodyR = R; t.bodySize = p.fizzSize; t.bodyVar = p.fizzSizeVar;
  t.fizzLidT = T; t.fizzLidTau = tau; t.fizzLidDelta = delta; t.lid = fizzLidOf(T, tau, delta, R);
  const float pf = 1 / cosf(delta) - 1 / cosf(tau);   // signed: < 0 here (tau > delta)
  if (!t.lid.on || fabsf(t.lid.pf - pf) > 1e-5f || fabsf(t.lid.tanT - tanf(tau)) > 1e-5f) fail("fizzLidOf pf", t.lid.pf, pf);
  const float Z[3] = {a, 0, -a}; float end[3] = {0, 0, 0};
  t.fizzN = 3; t.foam->nOrder = 0;
  for (int k = 0; k < 3; k++) {
    const float y = -fizzRowBias(k, 1, bias0);
    t.body[k] = {y, Z[k] * sqrtf(fmaxf(0, 1 - (y * y) / (a * a))), FIZZ_C_WALL, {0, 0, 0}};
    t.fizz[k] = {0, fizzRowOf(H, y, a, fizzRowBias(k, 1, bias0)), 1, 1000, fizzLevelOf(t.body[k].z, a)};
    if (fabsf(t.fizz[k].y - yc) > 1e-4f) fail("not on row yc", t.fizz[k].y, yc);
    const int iy = (int)yc; const float kk = fizzLidK(t.body[k].y, t.body[k].z, R);
    end[k] = t.fizzSurf[iy] + kk * t.strokeR[iy] - r + r * t.lid.pf;   // its row is exactly yc (an integer row: H odd) or between two
    t.fizz[k].x = end[k] - 3 * r;
  }
  if ((H & 1) == 0) fail("tube rows even (the test wants a centre row)", H, H + 1);
  const float bu = cosf(tau), bz = sinf(tau);   // the stand's buoyancy: normal to the level plane
  float y0[3], z0[3];
  for (int k = 0; k < 3; k++) { y0[k] = t.body[k].y; z0[k] = t.body[k].z; }
  for (int s = 0; s < 120; s++) { for (int k = 0; k < 3; k++) t.fizz[k].life = 1000; settleFoam(t, p, p.fizzSpeed, t.fizzSurf, 1, dt, false, 0, t.strokeR, bu, 0, bz); }
  const float S0 = t.fizzSurf[(int)yc], B0 = t.strokeR[(int)yc];
  for (int k = 0; k < 3; k++) {
    if (fabsf(t.fizz[k].x - end[k]) > 1e-3f) fail(k == 0 ? "front: not at L - r + P" : k == 1 ? "middle: not at L - r + P" : "back: not at L - r + P", t.fizz[k].x, end[k]);
    if (hypotf(t.body[k].y - y0[k], t.body[k].z - z0[k]) > 1e-3f) fail("drifted on the level plane", hypotf(t.body[k].y - y0[k], t.body[k].z - z0[k]), 0);
    float kR, kL; const float xd = fizzEndClampX(t, p, t.fizz[k], t.body[k], mag, kR, kL);
    if (fabsf(xd - t.fizz[k].x) > 1e-3f) fail("render clamp moved it", xd, t.fizz[k].x);
    if (kR != 1) fail("veil exemption under the lid", kR, 1);
  }
  const float fr = t.fizz[0].x + r - r * t.lid.pf, md = t.fizz[1].x + r - r * t.lid.pf, bk = t.fizz[2].x + r - r * t.lid.pf;   // their lines L
  if (!(fr - S0 >= 0 && fr - S0 < 0.15f * B0)) fail("front: L not at the front line", fr, S0);
  if (!(S0 + B0 - bk >= 0 && S0 + B0 - bk < 0.15f * B0)) fail("back: L not at the back line", bk, S0 + B0);
  if (!(fabsf(md - (S0 + 0.5f * B0)) < 0.02f * B0)) fail("middle: L not between", md, S0 + 0.5f * B0);
  printf("SELFTEST lid: front / middle / back glass end at L = S + %.3f / %.3f / %.3f B (S %.2f, B %.2f, P %.3f r); level plane drift 0, render clamp kept; failures %ld\n",
         (fr - S0) / B0, (md - S0) / B0, (bk - S0) / B0, S0, B0, t.lid.pf, bad);
  t.fizzN = 0; t.bodyH = 0; t.lid = {false, 0, 0, 0}; t.fizzLidT = t.fizzLidTau = t.fizzLidDelta = 0;
  return bad ? 21 : 0;
}
// `selftest`, the whole-step in-plane bound from the first placement (Astra review 4 item 4): one foam bubble (r = r_ref
// 2.5, U 48, dt 0.02, a flat zero-width band) under strong transverse buoyancy (0.6, 0.8, 0) drifts at most FOAM_PUSH U dt
// a step (0.3394 px; the uncapped drift moved 0.4608); two in contact under it, each the same bound.
static int pushSelftest() {
  Tube &t = tubeAt(0); long bad = 0; double worst = 0;
  auto fail = [&](const char *what, double got, double want) { if (bad++ < 8) fprintf(stderr, "selftest push: %s: got %.9g want %.9g\n", what, got, want); };
  Params p = PRESET_DEFAULT; p.vertical = true; p.glassWall = 3; p.tubeHeight = 55; p.fizzSize = 5; p.fizzSizeVar = 0; p.fizzSpeed = 48;
  t.H = tubeLayout(p).H; const int H = t.H; const float R = boreR(p), bias0 = fizzBias0(t), r = fizzR(p, 1), a = R - r, dt = 0.02f, lim = FOAM_PUSH * p.fizzSpeed * dt;
  for (int iy = 0; iy < H; iy++) { t.fizzSurf[iy] = 300; t.fizzSurfL[iy] = -5000; t.strokeR[iy] = 0; t.strokeL[iy] = 0; }
  t.surfH = H; t.bodyH = H; t.bodyR = R; t.bodySize = p.fizzSize; t.bodyVar = p.fizzSizeVar; t.lid = {false, 0, 0, 0};
  for (int pair = 0; pair < 2; pair++) {
    t.fizzN = pair ? 2 : 1; t.foam->nOrder = 0;
    const float Y[2] = {-4, -4 + 5.2f}, Z[2] = {0, 0.3f};
    for (int k = 0; k < t.fizzN; k++) { t.body[k] = {Y[k], Z[k], 0, {0, 0, 0}}; t.fizz[k] = {300 - r, fizzRowOf(H, Y[k], a, fizzRowBias(k, 1, bias0)), 1, 1000, fizzLevelOf(Z[k], a)}; }
    for (int st = 0; st < 40; st++) {
      float y0[2], z0[2];
      for (int k = 0; k < t.fizzN; k++) { y0[k] = t.body[k].y; z0[k] = t.body[k].z; t.fizz[k].life = 1000; }
      settleFoam(t, p, p.fizzSpeed, t.fizzSurf, 1, dt, false, 0, t.strokeR, 0.6f, 0.8f, 0);
      for (int k = 0; k < t.fizzN; k++) { const double d = hypot(t.body[k].y - y0[k], t.body[k].z - z0[k]); worst = fmax(worst, d); if (d > lim * (1 + 1e-5) + 1e-6) fail(pair ? "pair: in-plane past FOAM_PUSH U dt" : "isolated: in-plane past FOAM_PUSH U dt", d, lim); }
    }
  }
  printf("SELFTEST push bound: isolated and contacting foam under buoyancy (0.6, 0.8, 0): in-plane worst %.4f px a step (bound %.4f); failures %ld\n", worst, lim, bad);
  t.fizzN = 0; t.bodyH = 0;
  return bad ? 22 : 0;
}
static int selftests() {
  int e = birthSelftest(); const int e2 = rebuildSelftest(), e3 = motionSelftest(), e4 = chainSelftest(), e5 = containSelftest(), e6 = supportSelftest(), e7 = packSelftest();
  const int e8 = sideSelftest(), e9 = wallFlagSelftest(), e10 = loneSelftest(), e11 = lidSelftest(), e12 = pushSelftest();
  return e ? e : e2 ? e2 : e3 ? e3 : e4 ? e4 : e5 ? e5 : e6 ? e6 : e7 ? e7 : e8 ? e8 : e9 ? e9 : e10 ? e10 : e11 ? e11 : e12;
}
int main() {
  if (!render_init() || !physics_init()) return 3;
  const unsigned long bootAllocs = heapCalls();
  Params design = PRESET_DEFAULT, p[TUBE_COUNT]; TubeState st[TUBE_COUNT]; uint32_t gen = 1; int every = 2, step = 0; bool started = false, changed = false;
  for (int i = 0; i < TUBE_COUNT; i++) {
    st[i].trace = traceBuf(i); st[i].traceWet = traceWetBuf(i);
    if (st[i].trace) memset(st[i].trace, 0, TUBE_LENGTH_PX * sizeof(uint16_t));
    if (st[i].traceWet) memset(st[i].traceWet, 0, TUBE_LENGTH_PX * sizeof(uint16_t));
  }
  auto derive = [&]() { for (int i = 0; i < TUBE_COUNT; i++) { boardParams(design, p[i], TUBE_PX_SCALE(i), PX_SCALE_FIZZ); tubeP[i] = &p[i]; } gen++; };
  auto frame = [&]() {
#if TUBE_COUNT == 3
    const FaceLayout lay = faceLayout(p[0], p[1], p[2]);
#else
    const FaceLayout lay = faceLayout(p[0], p[1]);
#endif
    for (int i = 0; i < TUBE_COUNT; i++) renderTube(i, st[i], p[i], gen, strip[i], nullptr, lay.top(i));
    for (int i = 0; i < TUBE_COUNT; i++) {   // the frame's fizz inputs (stderr F lines): --free hands them to the sim kernel
      const Tube &t = tubeAt(i);
      fprintf(stderr, "F %d %d %.9g %d %.9g %d", step, i, t.fizzLen, t.fizzExposed, t.fizzShift, t.H);
      const float *const rows[4] = {t.fizzSurf, t.fizzSurfL, t.strokeR, t.strokeL};
      for (const float *v : rows) for (int r = 0; r < t.H; r++) fprintf(stderr, " %.9g", v[r]);
      fprintf(stderr, " %.9g %.9g %.9g\n", t.fizzLidT, t.fizzLidTau, t.fizzLidDelta);
    }
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
    if (!strcmp(line, "selftest")) return selftests();
    if (sscanf(line, "seed %lu", &seed) == 1) fizzTestRng() = seed ? (uint32_t)seed : 1u;
    else if (sscanf(line, "every %d", &every) == 1) {}
    else if (sscanf(line, "tube %d %63s %63s", &i, a, b) == 3) { if (i >= TUBE_COUNT || !setState(st[i], a, atof(b))) return 5; }
    else if (sscanf(line, "set %63s %63s", a, b) == 2) { if (!setParam(design, a, b)) return 6; derive(); changed = true; }
    else if (sscanf(line, "run %d %f %f %f %f %f", &n, &dt, &along, &across, &normal, &agit) == 6) {
      Pose pose = POSE_DEFAULT; const bool valid = updatePose(pose, along, across, normal);   // the run's gain-free pose (ImuFilter::pose's maths)
      for (int j = 0; j < TUBE_COUNT; j++) st[j].backTilt = valid ? poseBackTilt(pose) : 0;   // desk view: the lid's tau (ImuFilter::backTilt)
      if (!started || changed) frame();   // the first frame, and one after a params change: the new height's surfaces
      started = true; changed = false;
      for (int k = 0; k < n; k++) {
        for (int j = 0; j < TUBE_COUNT; j++) st[j].agitation = agit;
        mvSide = (mirrored(p[0]) ? -pose.x : pose.x) >= 0 ? 1 : -1;
        for (int j = 0; j < TUBE_COUNT; j++) {
          motionBefore(j); plN = 0; stepFizzTube(j, p[j], dt, along, across, agit, pose); motionAfter(j, p[j], dt);
          if (plN) fprintf(stderr, "PL %d %d %ld\n", step + 1, j, plN);   // the step's settle placements in tube j (the drain / pile-up expectations)
        }
        step++;
        if (step % every == 0) frame();
        for (int j = 0; j < TUBE_COUNT; j++) emit(step, j);   // after the step and its frame
      }
    }
    else return 7;
  }
  if (heapCalls() != bootAllocs) { fprintf(stderr, "%lu allocations after boot\n", heapCalls() - bootAllocs); return 8; }
  if (parkN) fprintf(stderr, "PARKS %ld worst %.6g px short of the zone\n", parkN, parkWorst);
  fprintf(stderr, "MOTION down worst %.6g x fizzSpeed dt; births %ld, nearest %.6g px from the surface\n", mvDownWorst, mvBirths, mvBirthGap);
  return 0;
}
"""
# The shared generator, counted: the test-only esp_random of --sim (the sim job's Math.random is the same).
SIM_RANDOM = ('#pragma once\n#include <cstdint>\n'
              'inline uint32_t &fizzTestRng() { static uint32_t s = 1; return s; }\n'
              'inline uint64_t &fizzTestDraws() { static uint64_t n = 0; return n; }\n'
              'inline uint32_t esp_random() { uint32_t &x = fizzTestRng(); x ^= x << 13; x ^= x >> 17; x ^= x << 5; fizzTestDraws()++; return x; }\n')
# Counted boot allocations (the jobs fail on any after render_init); FAIL_ALLOC_BYTES=n: every request of n bytes fails.
SIM_HEAP = ('#pragma once\n#include <cstdlib>\n#define MALLOC_CAP_SPIRAM 0\n'
            'inline unsigned long &heapCalls() { static unsigned long n = 0; return n; }\n'
            'inline void *heap_caps_malloc(size_t n, int) { heapCalls()++; const char *f = std::getenv("FAIL_ALLOC_BYTES");\n'
            '  return f && (size_t)std::atol(f) == n ? nullptr : std::calloc(n, 1); }\n')
BODY_BYTES = 480 * 12   # FIZZ_POOL x sizeof(FizzBody): one tube's vertical bodies (render_init)
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

def _f32(v): return struct.unpack('f', struct.pack('f', v))[0]   # a value both sides read alike (the native TubeState is float)

def _fill(run, tubes):
    """run with TubeState set before it (tube index -> fillTarget): the native `tube` lines, render-ref's run.tubes."""
    return {**run, 'tubes': {str(i): {'fillTarget': _f32(v)} for i, v in tubes.items()}}

STAND = (-0.976, -0.01, 0.22)   # the board's stand pose (g -0.976 -0.01 0 0 0.22)
DRAIN_AT, FULL = 1000, 0.999    # the wrap jobs: steps at the stand before the retract (the foam formed), the full column

def _wrap(tubes):
    """A clock wrap (physics.cpp followClock): fillTarget full -> 0 over RETRACT_S = 2 s (smoothstep, one step at a time) on
    `tubes`, then the empty column 1 s, the clock's first minute (0.02) and a refill (0.3): the source works again."""
    runs = [_run(DRAIN_AT, STAND)]
    for k in range(1, 101):
        u = k / 100; runs.append(_fill(_run(1, STAND), {i: FULL * (1 - u * u * (3 - 2 * u)) for i in tubes}))
    return runs + [_run(50, STAND), _fill(_run(100, STAND), {i: 0.02 for i in tubes}), _fill(_run(200, STAND), {i: 0.3 for i in tubes})]

# the lid fixture's fields over the board look (viewElevation 20, surfaceBlick 0.2: the user's look on the board)
LID_OVER = (lambda a, b: {k: v for k, v in b.items() if a.get(k) != v})(   # v too: the sim migrates from it
    json.load(open(ROOT / 'firmware/tools/testdata/tilted-fizz-board-look.json')), json.load(open(ROOT / 'firmware/tools/testdata/tilted-fizz-board-look-lid.json')))
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
    'spring dry, slug away': ({}, [_run(150, UP)]),
    # vertical only (the mode change above runs the legacy landscape kernel, doubles vs floats: diagnostic under --free)
    'height changes': ({}, [_run(80, UP), _run(60, UP, tubeHeight=40), _run(60, _tilt(15), tubeHeight=54), _run(60, _tilt(15), glassWall=8),
                            _run(60, (0.0, 0.0, 1.0), fizzSize=9), _run(60, UP, fizzSizeVar=1)]),
    'back 15, 20 s': ({}, [_run(100, UP), _run(1000, _tilt(15))]),   # the stand: the rope forms
    'board look 60 s': ({}, [_run(3000, UP)]),   # the diagnosed pulse replay (docs/tilted-fizz-plan.md): parks, foam count
    'board look 60 s, across 0.05': ({}, [_run(3000, (-math.sqrt(1 - 0.05 ** 2), 0.05, 0.0))]),
    'stand 13 back, 30 s': ({}, [_run(1500, (-0.976, -0.01, 0.22))]),   # the board's 'fizz explosion' pose (2026-11-22)
    # the desk view's lid (testdata/tilted-fizz-board-look-lid.json: viewElevation 20): the time edge's endpoint rule flipped
    'lid stand 13 back, 30 s': (LID_OVER, [_run(1500, (-0.976, -0.01, 0.22))]),
    'lid back 15': (LID_OVER, [_run(100, UP), _run(250, _tilt(15))]),
    'lid across + back': (LID_OVER, [_run(100, UP), _run(250, _tilt(15, 0.3))]),
    'lid upright, shaking': (LID_OVER, [_run(80, UP), *_shake(200), _run(70, UP)]),
    # signed P (P / r = 1 / cos delta - 1 / cos tau): far back < 0, forward > 0
    'lid back 35': (LID_OVER, [_run(100, UP), _run(250, _tilt(35))]),   # e 20: P -0.185 r (the lid faded to 26 %)
    'lid forward 30': (LID_OVER, [_run(100, UP), _run(250, _tilt(-30))]),   # e 20: P +0.401 r
    'lid e 45, back 40': ({**LID_OVER, 'viewElevation': 45}, [_run(100, UP), _run(250, _tilt(40))]),   # P -0.302 r
    # the drain (docs/tilted-fizz-surface-model.md "Drain"; the board's hour wrap, 2026-11-23): the user's look at the stand,
    # a full column's clock wraps; stranded foam and the bubbles the surface leaves burst, the empty tube clears
    'wrap retract, minutes': (LID_OVER, _wrap([1])),
    'wrap retract, both tubes': (LID_OVER, _wrap([0, 1])),
    # fizz_bench's load (480 scattered, then a 240 spring at 20/s): the hours column full against the glass (closed, the
    # bubbles pile up there), then its end opens under the pile (the board's settleFoam watchdog panic, 2026-11-23)
    'pile-up, 480 then spring 240': (LID_OVER, [_run(400, STAND, fizzSource=0, fizzCount=480), _fill(_run(100, STAND), {0: FULL}),
                                               _run(300, STAND, fizzSource=1, fizzSourceRate=20, fizzCount=240)]),
}
JOB_TUBES = {'spring dry, slug away': {'hours': {'slugPos': 220.0}},   # TubeState over FILLS: the slug slid off its spring
             'wrap retract, minutes': {'minutes': {'fillTarget': FULL}},
             'wrap retract, both tubes': {'hours': {'fillTarget': FULL}, 'minutes': {'fillTarget': FULL}},
             'pile-up, 480 then spring 240': {'hours': {'fillTarget': 1.0}, 'minutes': {'fillTarget': 0.992}}}

def _clock_held(lines, err):   # at the pool cap a birth waits: the spring clock sits at its one birth of credit
    return None if any(w[2] == '0' and float(w[5]) == 1 for w in lines) else 'the spring clock never waited at the cap'

def _dry(lines, err):   # tube 0's spring point dry: every birth scattered (springScatter 1), tube 1's wet (0)
    t0 = [float(w[6]) for w in lines if w[2] == '0']; t1 = [float(w[6]) for w in lines if w[2] == '1']
    return None if t0 and min(t0) == 1 and max(t1) == 0 else f'springScatter hours {min(t0)}..{max(t0)}, minutes {min(t1)}..{max(t1)}'

def _contained(lines, err):   # no across rise: every live body stays in the bore's eroded disc (the harness's OUT lines)
    out = [l for l in err.splitlines() if l.startswith('OUT ')]
    return f'{len(out)} steps with bodies outside, first: {out[0]}' if out else None

def _overdamped(lines, err):   # the stand: nothing moves back down faster than the rise's own step; births far from the surface
    m = next((l.split() for l in err.splitlines() if l.startswith('MOTION ')), None)
    if not m: return 'no MOTION line'
    down, gap = float(m[3]), float(m[10])
    # fizzSpeed dt bounds the foam's push back (settleFoam's cap; the profile's own recession exempt) and is the rise's
    # step: 1.3 leaves room for a front at a lower row after a slide along a curved meniscus (measured worst 1.0x)
    return None if down <= 1.3 and gap >= 20 else f'moved down {down:.3g} x fizzSpeed dt (max 1.3), a birth {gap:.3g} px from the surface (min 20)'

DRAIN_RATIO = 3      # the drain's worst settle (placements a step) at most this multiple of the same job's quiet stand
BLOCKED_MAX = 20     # births postponed in a wrapped tube by the job's end (a spring point without room waits uncounted)
PILE_MAX = 10000     # the pile-up's worst settle (placements a step); 4ef9323: 193,764 (every piled bubble foam at once)
def _placements(err):   # the harness's PL lines: (step, tube) -> settleFoam's placements that step
    return {(int(w[1]), int(w[2])): int(w[3]) for w in (l.split() for l in err.splitlines() if l.startswith('PL '))}

def _drained(tubes):
    """The wrap: the drain's worst settle within DRAIN_RATIO x the quiet stand's (steps up to DRAIN_AT), the wrapped tubes
    empty a second after the retract, the spring born again in the refilled column, births postponed bounded."""
    def check(lines, err):
        pl = _placements(err); end = DRAIN_AT + 150
        quiet = max([n for (s, t), n in pl.items() if t in tubes and s <= DRAIN_AT] or [0])
        drain = max([n for (s, t), n in pl.items() if t in tubes and DRAIN_AT < s <= end] or [0])
        if not quiet or drain > DRAIN_RATIO * quiet: return f'settle placements: drain worst {drain}, quiet stand worst {quiet} (max x{DRAIN_RATIO})'
        st = {(int(w[1]), int(w[2])): w for w in lines}
        for t in tubes:
            w = st[(end, t)]; live = sum(float(w[HEAD + 8 * k + 2]) != 0 for k in range(int(w[3])))
            if live: return f'tube {t}: {live} bubbles left {end - DRAIN_AT - 100} steps after the retract'
            w = st[(max(s for s, _ in st), t)]; live = sum(float(w[HEAD + 8 * k + 2]) != 0 for k in range(int(w[3])))
            if not live or int(w[8]) > BLOCKED_MAX: return f'tube {t} at the end: {live} live, {w[8]} births postponed (max {BLOCKED_MAX})'
        return None
    return check

def _piled(lines, err):   # the pile-up: the opening end's settle stays bounded (the monolayer; the rest bursts)
    worst = max(_placements(err).values() or [0])
    return None if worst <= PILE_MAX else f'settle placements worst {worst} a step (max {PILE_MAX})'

# name: (what, check over the firmware's state lines (split) -> None or why not)
SIM_EXPECT = {'wrap retract, minutes': ('drain', _drained([1])), 'wrap retract, both tubes': ('drain', _drained([0, 1])),
              'pile-up, 480 then spring 240': ('bounded settle', _piled),'crowded foam': ('pool saturation', _clock_held), 'spring dry, slug away': ('spring dry / wet', _dry),
              'upright': ('containment', _contained), 'back 15': ('containment', _contained), 'height changes': ('containment', _contained),
              'back 15, 20 s': ('containment', _contained), 'shaking': ('containment', _contained),
              'stand 13 back, 30 s': ('overdamped contacts', _overdamped), 'lid stand 13 back, 30 s': ('overdamped contacts', _overdamped),
              'lid back 15': ('containment', _contained), 'lid upright, shaking': ('containment', _contained)}
SIM_SEED = 0x2545F491
# Sim vs firmware in lockstep (each step from the firmware's state): per field, the largest difference accepted. Slot and
# draw counts, which slots are foam and on which side, are exact. Free bubbles: one step's float rounding. Parked foam
# (x, y): FOAM_TOL px, because the legacy packing tests contacts its last sweep left at exactly touching distance
# (settleFoam), so doubles and floats take or skip a push or a slide (<= FOAM_SLIDE * speed * dt) at random there.
# Vertical records (the body key bodyH != 0: the vertical kernel stepped) hold their foam to SIM_TOL too: that kernel is
# float32 in the firmware's order on both sides, its packing sweeps pairs in the firmware's order with the same tie
# rules, so there is no double / float decision to flip (measured worst over the jobs, common inputs: 1e-6 px, the
# printing). FOAM_TOL (2 px) stays for the legacy landscape kernel only (doubles in the sim).
SIM_TOL = {'x': 1e-3, 'y': 1e-3, 'v': 1e-6, 'life': 1e-4, 'z': 1e-6, 'by': 1e-3, 'bz': 1e-3, 'c': 0, 'springClock': 1e-4, 'springScatter': 1e-4}
FOAM_TOL = 2.0
LEGACY_JOBS = ('height + mode changes', 'landscape')   # they run the landscape kernel (--free: diagnostic)
FOAM_FIELDS = ('x', 'y', 'by')
SLOT_FIELDS = ('x', 'y', 'v', 'life', 'z', 'by', 'bz', 'c')   # by, bz, c: the vertical watch's physical y, z and contact (FizzBody: exact)
HEAD = 9   # S step tube fizzN draws springClock springScatter bodyH blocked

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
        (tmp / 'esp_heap_caps.h').write_text(SIM_HEAP)
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
        bad = 0   # the self-tests, then the jobs (jbad)
        r = subprocess.run([str(tmp / 'native')], input=b'---\nselftest\n', capture_output=True)
        print(f'{"births":24s} ' + (r.stdout.decode().strip() or '') + ('' if not r.returncode else f' FAILED ({r.returncode}) {r.stderr.decode()[-400:]}'))
        bad += r.returncode != 0
        r = subprocess.run([str(tmp / 'native')], input=b'---\n', capture_output=True, env={**os.environ, 'FAIL_ALLOC_BYTES': str(BODY_BYTES)})
        print(f'{"body allocation fails":24s} ' + ('render_init refused (exit 3)' if r.returncode == 3 else f'FAILED: exit {r.returncode}, not 3'))
        bad += r.returncode != 3

        def run(item):
            k, (name, (over, runs)) = item
            design = {**look, **over}   # the sim migrates from its version v (the firmware takes the fields as they are)
            script = ''.join(f'{f}={fmt(v)}\n' for f, v in design.items() if f != 'v') + f'---\nseed {SIM_SEED}\nevery 2\n'
            tubes = {n: {**FILLS[n], **JOB_TUBES.get(name, {}).get(n, {})} for n in names}
            script += ''.join(f'tube {i} {f} {v!r}\n' for i, n in enumerate(names) for f, v in tubes[n].items())
            for r in runs:   # a run's TubeState (`tubes`, render-ref's run.tubes) and design params, then its steps
                script += ''.join(f'tube {i} {f} {v!r}\n' for i, tv in r.get('tubes', {}).items() for f, v in tv.items())
                script += ''.join(f'set {f} {fmt(v)}\n' for f, v in r.get('set', {}).items())
                script += f'run {r["n"]} {r["dt"]!r} {r["along"]!r} {r["across"]!r} {r["normal"]!r} {r["agitation"]!r}\n'
            nat = [subprocess.run([str(tmp / 'native')], input=script.encode(), capture_output=True) for _ in range(2)]
            if nat[0].returncode: return name, f'native exited {nat[0].returncode}: {nat[0].stderr.decode()[-300:]}', None
            if nat[0].stdout != nat[1].stdout: return name, 'native: two runs of the job differ (not deterministic)', None
            jobf, natf = tmp / f'job{k}.json', tmp / f'native{k}.txt'
            natf.write_bytes(nat[0].stdout)
            inf = tmp / f'inputs{k}.txt'   # --free: the frames' fizz inputs (the native F lines): common to both kernels
            inf.write_text(''.join(l + '\n' for l in nat[0].stderr.decode().splitlines() if l.startswith('F ')))
            def sim(mode, path):   # the sim job: lockstep / inputs from a file, or (mode None) the full pipeline alone
                jf = path.with_suffix(f'.{mode or "full"}.json')
                json.dump({'params': design, **tubes, 'fizzSteps': {'seed': SIM_SEED, 'every': 2, 'runs': runs, **({mode: str(path)} if mode else {})}}, open(jf, 'w'))
                return subprocess.run(['node', str(out / 'sim' / 'tools' / 'render-ref.js'), str(jf), '-'], env=env, capture_output=True)
            natives[name] = (nat[0].stdout.decode(), nat[0].stderr.decode(), lambda path: sim('inputs', path), inf)
            r = sim('inputs', inf) if a.free else sim('lockstep', natf)
            if r.returncode: return name, f'sim exited {r.returncode}: {r.stderr.decode()[-500:]}', None
            if a.keep: (a.keep / f'{name}.native.txt').write_bytes(nat[0].stdout); (a.keep / f'{name}.sim.txt').write_bytes(r.stdout)
            gen = gen_compare(nat[0].stderr.decode(), r.stdout.decode())
            if gen[0]: return name, f'frame inputs generated differently: {gen[0]}', None
            res_ = sim_compare(nat[0].stdout.decode(), r.stdout.decode())
            if not res_[0] and name in SIM_EXPECT:
                why = SIM_EXPECT[name][1]([l.split() for l in nat[0].stdout.decode().splitlines()], nat[0].stderr.decode())
                if why: return name, f'{SIM_EXPECT[name][0]}: {why}', None
            full = None
            if a.free:   # the independent full pipeline (no injection): information, its first divergence
                rf = sim(None, natf)
                full = f'sim exited {rf.returncode}' if rf.returncode else (sim_compare(nat[0].stdout.decode(), rf.stdout.decode())[0] or 'matches')
            mo = next((l[7:] for l in nat[0].stderr.decode().splitlines() if l.startswith('MOTION ')), '')
            return name, None, (*res_, gen, full, mo)

        mode = 'free: common-input kernel parity (acceptance for vertical jobs)' if a.free else 'lockstep (diagnostic)'
        print(f'{"mode":24s} {mode}' + ('' if a.free else ': every step from the firmware state; --free is the acceptance mode for vertical jobs'))
        natives = {}   # per job: native state lines, F lines, a sim run on an inputs file (the self-checks)
        jbad = vbad = 0; nlegacy = sum(n in LEGACY_JOBS for n in jobs); fulls = []
        with ThreadPoolExecutor(a.j) as ex:
            for name, err, res_ in ex.map(run, enumerate(jobs.items())):
                diag = a.free and name in LEGACY_JOBS   # the landscape kernel (doubles vs floats): a diagnostic in --free
                tag_ = ' (legacy kernel, diagnostic)' if diag else ''
                if err: jbad += 1; vbad += not diag; print(f'{name:24s} ERROR{tag_} {err}'); continue
                diff, steps, worst, most, gen, full, mo = res_
                if full: fulls.append((name, full))
                if diff: jbad += 1; vbad += not diag; print(f'{name:24s} DIFFERS{tag_} {diff}'); continue
                print(f'{name:24s} {steps} steps match{tag_}; frame inputs generated alike over {gen[1]} frames' + (f'; slots max {"/".join(map(str, most))}; worst '
                      + ', '.join(f'{f} {v:.2g}' for f, v in worst.items()) + f'; generation worst surf {gen[2]["surf"]:.2g} stroke {gen[2]["stroke"]:.2g}; motion: {mo}' if a.v else ''))
        if a.free:
            print('full pipeline, no input injection (information: expected to drift; the first divergence per job):')
            for name, full in fulls: print(f'  {name:24s} ' + ('all steps match' if full == 'matches' else f'first divergence: {full}'))
        def pick(test):   # the first job (in job order) the self-check can use
            for n in jobs:
                if n in natives:
                    try: return n, test(n)
                    except StopIteration: pass
            return None, None
        jn, sr = pick(lambda n: sim_compare_selftest(natives[n][0]))
        if jn:
            base, accepted, nm = sr; ok = base is None and not accepted; bad += not ok
            print(f'{"comparator mutations":24s} ' + (f'{nm} of {nm} rejected, unmutated {jn!r} accepted' if ok else
                  f'FAILED: unmutated {"rejected: " + base if base else "accepted"}; accepted {", ".join(accepted) or "none"}'))
        else: bad += 1; print(f'{"comparator mutations":24s} FAILED: no job with vertical foam to mutate')
        jn, sr = pick(lambda n: gen_compare_selftest(natives[n][1], ''))
        if jn:
            base, accepted, nm = sr; ok = base is None and not accepted; bad += not ok
            print(f'{"generation mutations":24s} ' + (f'{nm} of {nm} rejected, unmutated {jn!r} accepted' if ok else
                  f'FAILED: unmutated {"rejected: " + base if base else "accepted"}; accepted {", ".join(accepted) or "none"}'))
            _, _, run_inputs, inf = natives[jn]; fl = inf.read_text().splitlines(); w0 = fl[0].split(); refused = 0
            corrupt = {'frame index': ' '.join([w0[0], str(int(w0[1]) + 1), *w0[2:]]), 'record short': ' '.join(w0[:-1]),
                       'rows': ' '.join([*w0[:6], str(int(w0[6]) + 1), *w0[7:]]), 'NaN field': ' '.join([*w0[:8], 'NaN', *w0[9:]])}
            for cn, c in corrupt.items():
                cf = inf.with_suffix(f'.bad{refused}.txt'); cf.write_text('\n'.join([c, *fl[1:]]) + '\n')
                rr = run_inputs(cf); refused += rr.returncode != 0 and b'render-ref: inputs line' in rr.stderr
            ok = refused == len(corrupt); bad += not ok
            print(f'{"injected F records":24s} ' + (f'{refused} of {len(corrupt)} corrupt inputs files refused by render-ref ({", ".join(corrupt)})' if ok else f'FAILED: {refused} of {len(corrupt)} refused'))
        else: bad += 1; print(f'{"generation mutations":24s} FAILED: no job with strokes to mutate')
        tag = f'{board}{"@" + res if lcd else ""}{"+t3" if a.tubes == 3 else ""}'
        if a.free:
            nv = len(jobs) - nlegacy
            print(f'{tag}: {nv - vbad} of {nv} vertical jobs match, {nlegacy - (jbad - vbad)} of {nlegacy} legacy-kernel jobs (diagnostic), sim vs firmware, step by step, {mode}' + ('' if bad == 0 else '; a self-test FAILED'))
            sys.exit(1 if bad or vbad else 0)
        print(f'{tag}: {len(jobs) - jbad} of {len(jobs)} jobs match, sim vs firmware, step by step, {mode}' + ('' if bad == 0 else '; a self-test FAILED'))
        sys.exit(1 if bad or jbad else 0)

# The frame's surfaces the kernel steps on (fizzLen, fizzShift, fizzSurf / fizzSurfL per row): canvas px up to ~1000
# (float ulp <= 1.2e-4 px there). Both sides derive them from the same float TubeState with the same formulae, the sim
# in doubles: they differ by a few ulps at that scale, also after a subtraction (cancellation keeps the absolute
# error). 1e-3 px = 8 ulps at 1024 and a thousandth of a pixel; measured worst 3e-5. Between frames (lockstep) the sim
# steps on the firmware's own surfaces, so they match exactly there.
SURF_TOL = 1e-3
# Stroke widths (strokeR / strokeL: min(surfaceWidth, the ring-profile separation), canvas px <= ~20): derived per row
# from the same surfaces and walls, the sim in doubles; the same few-ulp argument as SURF_TOL.
STROKE_TOL = 1e-3
# The desk view's lid (T, tau, delta: the last fields of S / F / G records): float32 tanf / atan2f against the sim's doubles
# rounded (an ulp or two); --free and lockstep hand the sim the firmware's.
LID_TOL = 1e-5
LID_N = 3
LID_FIELDS = ('T', 'tau', 'delta')

def _record(line, side):
    """(fields, why not) of one state line: 'S', HEAD + 8 * fizzN + 4 + 4 * H fields, all finite numbers."""
    p = line.split()
    if len(p) < HEAD + 4 or p[0] != 'S': return None, f'{side}: not a state line: {line[:60]!r}'
    try: v = [float(s) for s in p[1:]]
    except ValueError: return None, f'{side}: not a number in {line[:60]!r}'
    bad = next((i for i, x in enumerate(v, 1) if not math.isfinite(x)), None)
    if bad is not None: return None, f'{side} step {p[1]} tube {p[2]}: field {bad} is {p[bad]}'
    n = int(v[2]) if v[2] == int(v[2]) and v[2] >= 0 else -1
    e = HEAD + len(SLOT_FIELDS) * n
    H = int(v[e + 2]) if n >= 0 and e + 3 < len(p) and v[e + 2] == int(v[e + 2]) and v[e + 2] >= 0 else -1
    if n < 0 or H < 0 or len(p) != e + 4 + 4 * H + LID_N: return None, f'{side} step {p[1]} tube {p[2]}: {len(p)} fields for fizzN {p[3]}'
    return p, None

def sim_compare(nat, sim):
    """(first mismatch or None, steps, worst difference per field, most slots per tube) of the two sides' state lines."""
    la, lb = nat.splitlines(), sim.splitlines()
    worst = {**{f: 0.0 for f in SIM_TOL}, **{f'foam {f}': 0.0 for f in FOAM_FIELDS}, 'surf': 0.0, 'stroke': 0.0, 'lid': 0.0}; most = {}
    la = [l for l in la if not l.startswith('G ')]; lb = [l for l in lb if not l.startswith('G ')]   # state lines only
    if len(la) != len(lb): return f'{len(la)} native state lines, {len(lb)} sim', 0, worst, []
    if not la: return 'no state lines', 0, worst, []
    w = len(SLOT_FIELDS); L = SLOT_FIELDS.index('life')
    for x, y in zip(la, lb):
        p, why = _record(x, 'native')
        if why: return why, 0, worst, []
        q, why = _record(y, 'sim')
        if why: return why, 0, worst, []
        where = f'step {p[1]} tube {p[2]}'
        if p[:4] != q[:4]: return f'{where}: step / tube / slots native {" ".join(p[1:4])} sim {" ".join(q[1:4])}', 0, worst, []
        most[p[2]] = max(most.get(p[2], 0), int(p[3]))
        if p[4] != q[4]: return f'{where}: draws native {p[4]} sim {q[4]}', 0, worst, []
        if p[7:9] != q[7:9]: return f'{where}: bodyH / blocked native {" ".join(p[7:9])} sim {" ".join(q[7:9])}', 0, worst, []
        for f, i in (('springClock', 5), ('springScatter', 6)):
            d = abs(float(p[i]) - float(q[i])); worst[f] = max(worst[f], d)
            if d > SIM_TOL[f]: return f'{where}: {f} native {p[i]} sim {q[i]}', 0, worst, []
        vert = p[7] != '0'   # the vertical kernel stepped (its bodies' key): foam held to SIM_TOL
        for s in range(int(p[3])):
            o = HEAD + w * s; lp, lq = float(p[o + L]), float(q[o + L])
            if (lp > 0) != (lq > 0) or (lp < 0) != (lq < 0): return f'{where} slot {s}: life native {lp} sim {lq}', 0, worst, []
            for j, f in enumerate(SLOT_FIELDS):
                d = abs(float(p[o + j]) - float(q[o + j]))
                k, tol = (f'foam {f}', SIM_TOL[f] if vert else FOAM_TOL) if lp != 0 and f in FOAM_FIELDS else (f, SIM_TOL[f])
                worst[k] = max(worst[k], d)
                if d > tol: return f'{where} slot {s}: {k} native {p[o + j]} sim {q[o + j]}', 0, worst, []
        e = HEAD + w * int(p[3])   # the frame's surfaces the kernel steps on: exposed / rows exact, len shift surf surfL SURF_TOL
        if p[e + 1] != q[e + 1] or p[e + 3] != q[e + 3]: return f'{where}: exposed / rows native {p[e + 1]} {p[e + 3]} sim {q[e + 1]} {q[e + 3]}', 0, worst, []
        H = int(p[e + 3])
        for i in range(len(p) - LID_N, len(p)):   # the lid's T, tau, delta
            d = abs(float(p[i]) - float(q[i])); worst['lid'] = max(worst['lid'], d)
            if d > LID_TOL: return f'{where}: lid {LID_FIELDS[i - len(p) + LID_N]} native {p[i]} sim {q[i]}', 0, worst, []
        for i in [e, e + 2, *range(e + 4, len(p) - LID_N)]:
            d = abs(float(p[i]) - float(q[i])); j = i - e - 4; st = j >= 2 * H
            worst['stroke' if st else 'surf'] = max(worst['stroke' if st else 'surf'], d)
            k = 'len' if i == e else 'shift' if i == e + 2 else f'{("surf", "surfL", "strokeR", "strokeL")[j // H]} row {j % H}'
            if d > (STROKE_TOL if st else SURF_TOL): return f'{where}: {k} native {p[i]} sim {q[i]}', 0, worst, []
    return None, len(la) // max(1, len(most)), worst, [most[t] for t in sorted(most)]

def _frame_record(line, side, tag):
    """(fields, why not) of one frame-input line: tag ('F' native, 'G' sim), step, tube, len, exposed, shift, H, then
    surf, surfL, strokeR, strokeL per row, the lid's T, tau, delta: 7 + 4 * H + 3 fields, all finite numbers."""
    p = line.split()
    if len(p) < 7 or p[0] != tag: return None, f'{side}: not a {tag} line: {line[:60]!r}'
    try: v = [float(x) for x in p[1:]]
    except ValueError: return None, f'{side}: not a number in {line[:60]!r}'
    bad = next((i for i, x in enumerate(v, 1) if not math.isfinite(x)), None)
    if bad is not None: return None, f'{side} {tag} step {p[1]} tube {p[2]}: field {bad} is {p[bad]}'
    H = int(v[5]) if v[5] == int(v[5]) and v[5] >= 0 else -1
    if H < 0 or len(p) != 7 + 4 * H + LID_N: return None, f'{side} {tag} step {p[1]} tube {p[2]}: {len(p)} fields for rows {p[6]}'
    return p, None

def gen_compare(nat_err, sim_out):
    """(first mismatch or None, frames, worst surface / stroke difference) of the two sides' own frame inputs: the
    native F lines (stderr), the sim's G lines (generated before any replacement)."""
    fa = [l for l in nat_err.splitlines() if l.startswith('F')]; ga = [l for l in sim_out.splitlines() if l.startswith('G')]
    worst = {'surf': 0.0, 'stroke': 0.0, 'lid': 0.0}
    if len(fa) != len(ga): return f'{len(fa)} native frame records, {len(ga)} sim', 0, worst
    if not fa: return 'no frame records', 0, worst
    for x, y in zip(fa, ga):
        p, why = _frame_record(x, 'native', 'F')
        if why: return why, 0, worst
        q, why = _frame_record(y, 'sim', 'G')
        if why: return why, 0, worst
        where = f'frame at step {p[1]} tube {p[2]}'
        if p[1:3] != q[1:3]: return f'{where}: sim frame at step {q[1]} tube {q[2]}', 0, worst
        if p[4] != q[4] or p[6] != q[6]: return f'{where}: exposed / rows native {p[4]} {p[6]} sim {q[4]} {q[6]}', 0, worst
        H = int(p[6])
        for i in range(len(p) - LID_N, len(p)):   # the lid's T, tau, delta (the sim's atan2 / tan in doubles, rounded)
            d = abs(float(p[i]) - float(q[i])); worst['lid'] = max(worst['lid'], d)
            if d > LID_TOL: return f'{where}: lid {LID_FIELDS[i - len(p) + LID_N]} native {p[i]} sim {q[i]}', 0, worst
        for i in [3, 5, *range(7, len(p) - LID_N)]:
            d = abs(float(p[i]) - float(q[i])); j = i - 7; st = j >= 2 * H
            worst['stroke' if st else 'surf'] = max(worst['stroke' if st else 'surf'], d)
            if d > (STROKE_TOL if st else SURF_TOL):
                k = 'len' if i == 3 else 'shift' if i == 5 else f'{("surf", "surfL", "strokeR", "strokeL")[j // H]} row {j % H}'
                return f'{where}: {k} native {p[i]} sim {q[i]}', 0, worst
    return None, len(fa), worst

def gen_compare_selftest(err, out):
    """gen_compare on one job's F lines against themselves as G lines (must match), then mutated (each rejected)."""
    fl = [l for l in err.splitlines() if l.startswith('F')]
    k = next(i for i, l in enumerate(fl) if any(float(v) != 0 for v in l.split()[7 + 2 * int(l.split()[6]):-LID_N]))   # a frame with a stroke
    p = fl[k].split(); H = int(p[6]); so = 7 + 2 * H + next(j for j, v in enumerate(p[7 + 2 * H:-LID_N]) if float(v) != 0)
    G = lambda ls: '\n'.join('G' + l[1:] for l in ls)
    def at(i, v, native=False):   # field i of record k set to v, on the sim (G) side or the native (F) side
        q = list(p); q[i] = v(q[i]) if callable(v) else v; m = [*fl[:k], ' '.join(q), *fl[k + 1:]]
        return ('\n'.join(m), G(fl)) if native else ('\n'.join(fl), G(m))
    muts = {
        'G stroke +0.01': at(so, lambda s: repr(float(s) + 0.01)), 'G surf row +0.01': at(7, lambda s: repr(float(s) + 0.01)),
        'G strokeL row NaN': at(7 + 3 * H, 'nan'), 'G exposed flipped': at(4, lambda s: str(3 - int(s))),
        'F frame index wrong': at(1, lambda s: str(int(s) + 1), True), 'F rows wrong': at(6, lambda s: str(int(s) + 1), True),
        'F record short': ('\n'.join([*fl[:k], ' '.join(p[:-1]), *fl[k + 1:]]), G(fl)), 'F inf': at(9, 'inf', True),
        'F record missing': ('\n'.join(fl[:-1]), G(fl)), 'G lid T +0.01': at(len(p) - 3, lambda s: repr(float(s) + 0.01)),
        'G lid tau NaN': at(len(p) - 2, 'nan'), 'G lid delta +0.01': at(len(p) - 1, lambda s: repr(float(s) + 0.01)),
    }
    accepted = [n for n, (a_, b_) in muts.items() if gen_compare(a_, b_)[0] is None]
    return gen_compare('\n'.join(fl), G(fl))[0], accepted, len(muts)

def sim_compare_selftest(nat):
    """The comparator on one job's native lines against themselves (must match), then mutated (each must be rejected):
    (why the unmutated lines were rejected or None, the mutations accepted, how many)."""
    lines = nat.splitlines(); w = len(SLOT_FIELDS); LF = SLOT_FIELDS.index('life')
    def foam_at(l):   # a vertical record's first parked slot, or None
        v = l.split(); return next((s for s in range(int(v[3])) if v[7] != '0' and float(v[HEAD + w * s + LF]) != 0), None)
    k = next(i for i, l in enumerate(lines) if int(l.split()[3]) > 0 and int(l.split()[HEAD + w * int(l.split()[3]) + 3]) > 0 and foam_at(l) is not None)
    p = lines[k].split(); e = HEAD + w * int(p[3]); H = int(p[e + 3]); fo = HEAD + w * foam_at(lines[k])
    def at(i, v, both=False):   # the lines with field i of line k set to v (both: on the native side too)
        q = list(p); q[i] = v(q[i]) if callable(v) else v; m = [*lines[:k], ' '.join(q), *lines[k + 1:]]
        return ('\n'.join(m) if both else nat), '\n'.join(m)
    X, LIFE = HEAD, HEAD + SLOT_FIELDS.index('life')
    muts = {
        'x NaN': at(X, 'nan'), 'x NaN (JS)': at(X, 'NaN'), 'life inf both sides': at(LIFE, 'inf', True),
        'bodyH NaN both sides': at(7, 'NaN', True), 'surf row NaN': at(e + 4, 'nan'),
        'surface 10 -> 1000': at(e + 4, lambda s: repr(float(s) + 990)), 'surfL row +1': at(e + 4 + H, lambda s: repr(float(s) + 1)),
        'len +1': at(e, lambda s: repr(float(s) + 1)), 'shift +1': at(e + 2, lambda s: repr(float(s) + 1)),
        'record short': (nat, '\n'.join([*lines[:k], ' '.join(p[:-1]), *lines[k + 1:]])),
        'record long': (nat, '\n'.join([*lines[:k], ' '.join([*p, '0']), *lines[k + 1:]])),
        'record long both sides': ('\n'.join(m := [*lines[:k], ' '.join([*p, '0']), *lines[k + 1:]]), '\n'.join(m)),
        'line missing': (nat, '\n'.join(lines[:-1])), 'no lines': ('', ''),
        'strokeR row +0.01': at(e + 4 + 2 * H, lambda s: repr(float(s) + 0.01)), 'strokeL row +0.01': at(e + 4 + 3 * H, lambda s: repr(float(s) + 0.01)),
        'strokeR row NaN': at(e + 4 + 2 * H + 1, 'nan'),
        'vertical foam x +0.01': at(fo, lambda s: repr(float(s) + 0.01)), 'vertical foam y +0.01': at(fo + 1, lambda s: repr(float(s) + 0.01)),
        'vertical foam body y +0.01': at(fo + SLOT_FIELDS.index('by'), lambda s: repr(float(s) + 0.01)),
        'lid T +0.01': at(len(p) - 3, lambda s: repr(float(s) + 0.01)), 'lid tau +0.01': at(len(p) - 2, lambda s: repr(float(s) + 0.01)),
        'lid delta NaN': at(len(p) - 1, 'nan'),
    }
    accepted = [n for n, (a_, b_) in muts.items() if sim_compare(a_, b_)[0] is None]
    return sim_compare(nat, nat)[0], accepted, len(muts)

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
    ap.add_argument('--free', action='store_true', help='--sim: common-input kernel parity, the acceptance mode for vertical jobs: the sim runs on from its own state, both kernels on the firmware frames\' inputs (+ an independent full-pipeline run, information); default lockstep, a diagnostic: every step starts from the firmware state')
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
