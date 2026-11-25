#!/usr/bin/env python3
"""fizzPhys's kernel, firmware (src/fizz_light.h) vs sim (sim/src/fizzLight.ts), host only, no board.

  python3 firmware/tools/check_fizz_light.py [--frames 200] [--bubbles 500] [--seed 1] [--no-time] [--no-asan]

A seeded job: frames over transparency 0..1 (0 and 1 included), R 12..40, the pose's upX -1..1 (the stand 0.974, 0, +-1
included), TubeState.light -60..60 deg, the lid on / off (tau -0.5..0.6 rad, delta 0..1.3), exposed 0..3 and the tone
-1..1 (0, +-1 included), each with bubbles around / far below / above the surfaces, (y, z) in the bore disc (the wall and
the centre included), r 0.7..8, S, SL and the lid's height B (0 included); fizzTone on random RGB565 triples. Every input
is a float32 (hex bits) both sides read. Compared (float32 bits from both, -ffp-contract=off):
  - FIZZ_ATT: exact;
  - fizzTone: exact;
  - FizzLight fields (each side its own frame): within 2e-6 relative (the firmware's frame takes float32 transcendentals,
    the sim double ones), booleans exact;
  - FizzLit, each side on its own frame: within 1e-4 absolute;
  - FizzLit with the native kernel fed the sim's frame fields: bit for bit;
  - both sides: every output finite, K / wl / tv / sk in [0, 1], |(cx, cy)| <= 1 + 1e-6.
Also a native run under ASan / UBSan (--no-asan skips it) and the host's ns per bubble of fizzLit at -O2 (--no-time skips).
Exits 1 on any failure.
"""
import argparse, math, os, random, shutil, struct, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / 'sim'
DRIVER = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <vector>
#include "fizz_light.h"
static float fh(const char *s) { uint32_t u = (uint32_t)strtoul(s, nullptr, 16); float f; memcpy(&f, &u, 4); return f; }
static void ph(float f) { uint32_t u; memcpy(&u, &f, 4); printf(" %08x", u); }
static int words(char *line, char **w, int n) {
  int k = 0; for (char *t = strtok(line, " \t\r\n"); t && k < n; t = strtok(nullptr, " \t\r\n")) w[k++] = t; return k;
}
static void printFrame(const FizzLight &L) {
  printf("L"); ph(L.a8); ph(L.R); ph(L.R2); for (float v : L.w) ph(v); for (float v : L.invS) ph(v); for (float v : L.invH) ph(v);
  ph(L.ly); ph(L.lz); ph(L.la); ph(L.invA); ph(L.fk); ph(L.hx); ph(L.hy);
  printf(" %d %d %d", L.openR ? 1 : 0, L.openL ? 1 : 0, L.lid ? 1 : 0); ph(L.kLid); ph(L.tone); printf("\n");
}
// "L ..." of the sim's output back into a FizzLight (fed mode)
static bool readFrame(FILE *f, FizzLight &L) {
  static char line[4096]; char *w[64];
  while (fgets(line, sizeof line, f)) {
    if (line[0] != 'L') continue;
    if (words(line, w, 64) != 30) return false;
    int k = 1; L.a8 = fh(w[k++]); L.R = fh(w[k++]); L.R2 = fh(w[k++]);
    for (float &v : L.w) v = fh(w[k++]); for (float &v : L.invS) v = fh(w[k++]); for (float &v : L.invH) v = fh(w[k++]);
    L.ly = fh(w[k++]); L.lz = fh(w[k++]); L.la = fh(w[k++]); L.invA = fh(w[k++]); L.fk = fh(w[k++]); L.hx = fh(w[k++]); L.hy = fh(w[k++]);
    L.openR = atoi(w[k++]); L.openL = atoi(w[k++]); L.lid = atoi(w[k++]); L.kLid = fh(w[k++]); L.tone = fh(w[k++]);
    return true;
  }
  return false;
}
struct Bub { float x, y, z, r, S, SL, B; };
int main(int argc, char **argv) {
  if (argc < 3) return 2;
  const char *mode = argv[1];
  FILE *job = fopen(argv[2], "r"); if (!job) return 2;
  FILE *fed = !strcmp(mode, "fed") ? fopen(argv[3], "r") : nullptr;
  if (!strcmp(mode, "fed") && !fed) return 2;
  const bool timing = !strcmp(mode, "time");
  std::vector<FizzLight> frames; std::vector<std::vector<Bub>> bubs;
  if (!timing) { printf("A"); for (float v : FIZZ_ATT) ph(v); printf("\n"); }
  char line[1024]; char *w[16]; FizzLight L{}; bool have = false;
  while (fgets(line, sizeof line, job)) {
    const int n = words(line, w, 16);
    if (n == 10 && !strcmp(w[0], "F")) {
      float v[9]; for (int i = 0; i < 9; i++) v[i] = fh(w[i + 1]);
      if (fed) { if (!readFrame(fed, L)) { fprintf(stderr, "fed: sim frame missing\n"); return 3; } }
      else fizzLightFrame(L, v[0], v[1], v[2], v[3], v[4] != 0, v[5], v[6], (int)v[7], v[8]);
      have = true;
      if (timing) { frames.push_back(L); bubs.emplace_back(); } else printFrame(L);
    } else if (n == 8 && !strcmp(w[0], "B") && have) {
      Bub b{fh(w[1]), fh(w[2]), fh(w[3]), fh(w[4]), fh(w[5]), fh(w[6]), fh(w[7])};
      if (timing) { bubs.back().push_back(b); continue; }
      FizzLit o; fizzLit(L, b.x, b.y, b.z, b.r, b.S, b.SL, b.B, o);
      printf("O"); ph(o.K); ph(o.cx); ph(o.cy); ph(o.wl); ph(o.tv); ph(o.sk); printf("\n");
    } else if (n == 4 && !strcmp(w[0], "T")) {
      if (timing) continue;
      printf("T"); ph(fizzTone((uint16_t)strtoul(w[1], nullptr, 16), (uint16_t)strtoul(w[2], nullptr, 16), (uint16_t)strtoul(w[3], nullptr, 16))); printf("\n");
    }
  }
  if (timing) {   // ns per bubble: fizzLit, then the old explicit per-bubble set-up's rough equivalent (planBubble's expressions)
    const long N = atol(argv[3]); long done = 0; volatile float sink = 0; float acc = 0;
    auto t0 = std::chrono::steady_clock::now();
    while (done < N) for (size_t f = 0; f < frames.size() && done < N; f++) for (const Bub &b : bubs[f]) {
      FizzLit o; fizzLit(frames[f], b.x, b.y, b.z, b.r, b.S, b.SL, b.B, o); acc += o.K + o.cx + o.cy + o.wl + o.tv + o.sk; done++;
    }
    auto t1 = std::chrono::steady_clock::now(); sink = acc; done = 0; acc = 0;
    auto t2 = std::chrono::steady_clock::now();
    while (done < N) for (size_t f = 0; f < frames.size() && done < N; f++) for (const Bub &b : bubs[f]) {
      const float yHi = 20.0f, invHalfH = 1 / 40.0f, lxS = -0.7f, depthK = 1 - 0.7f * b.z * (1 - 0.3f);
      const float ly = fizzMx(-1, fizzMn(1, (yHi - b.y) * invHalfH)), nrm = 1 / sqrtf(lxS * lxS + ly * ly);
      const float dirX = lxS * nrm, dirY = ly * nrm, off = fizzMn(b.r * 0.3f, b.r - 1), bk = 0.4f * (b.r - 1);
      acc += -dirX * off - dirY * off + dirX * bk + dirY * bk + 0.6f * depthK + depthK; done++;
    }
    auto t3 = std::chrono::steady_clock::now(); sink = sink + acc;
    printf("%.2f %.2f\n", std::chrono::duration<double, std::nano>(t1 - t0).count() / N, std::chrono::duration<double, std::nano>(t3 - t2).count() / N);
  }
  return 0;
}
'''

def f32(v):
    return struct.unpack('<f', struct.pack('<f', v))[0]

def hx(v):
    return '%08x' % struct.unpack('<I', struct.pack('<f', f32(v)))[0]

def fl(h):
    return struct.unpack('<f', struct.pack('<I', int(h, 16)))[0]

def make_job(frames, bubbles, seed):
    rnd = random.Random(seed)
    lines = []
    def pick(special, lo, hi, p=0.25):
        return rnd.choice(special) if rnd.random() < p else rnd.uniform(lo, hi)
    for fi in range(frames):
        t = pick([0, 1, 0.005, 0.01, 0.5], 0, 1)
        R = rnd.uniform(12, 40) if fi % 7 else float(rnd.randint(12, 40))
        up = pick([0.974, 0, 1, -1, -0.974], -1, 1, 0.35)
        light = pick([0, 45, -45, 60, -60, 22.5], -60, 60)
        lid = rnd.random() < 0.4
        tau = pick([0, 0.6, -0.5], -0.5, 0.6) if lid else 0.0
        delta = pick([0, 1.3], 0, 1.3) if lid else 0.0
        exposed = rnd.randint(0, 3)
        tone = pick([0, 1, -1], -1, 1, 0.3)
        lines.append('F ' + ' '.join(hx(v) for v in (t, R, up, light, 1 if lid else 0, tau, delta, exposed, tone)))
        for bi in range(bubbles):
            r = rnd.uniform(0.7, 8)
            S = rnd.uniform(0, 300); SL = S - rnd.uniform(5, 300) if rnd.random() < 0.7 else rnd.uniform(-400, -5)
            k = rnd.random()
            if k < 0.35: x = S + rnd.uniform(-3, 1) * r                 # around the time edge's surface
            elif k < 0.5: x = SL + rnd.uniform(-1, 3) * r               # around the home edge's
            elif k < 0.75: x = SL + rnd.uniform(0, 1) * (S - SL)         # in the column, far from both
            elif k < 0.85: x = S + rnd.uniform(1, 60)                    # above (past) the time surface
            else: x = SL - rnd.uniform(1, 60)                            # below the home surface
            m = rnd.random()
            if m < 0.05: y = z = 0.0                                     # the centre
            elif m < 0.2:                                                # on the wall
                a = rnd.uniform(0, 2 * math.pi); y, z = R * math.cos(a), R * math.sin(a)
            else:
                rr = R * math.sqrt(rnd.random()); a = rnd.uniform(0, 2 * math.pi); y, z = rr * math.cos(a), rr * math.sin(a)
            y, z = f32(y), f32(z)
            if y * y + z * z > R * R:                                   # float rounding past the wall: back inside
                q = R / math.hypot(y, z) * (1 - 1e-6); y, z = y * q, z * q
            B = 0.0 if rnd.random() < 0.4 else rnd.uniform(0, 2 * R)
            lines.append('B ' + ' '.join(hx(v) for v in (x, y, z, r, S, SL, B)))
    for _ in range(2000):
        lines.append('T %04x %04x %04x' % (rnd.randrange(65536), rnd.randrange(65536), rnd.randrange(65536)))
    return '\n'.join(lines) + '\n'

def parse(text):
    A = None; L = []; O = []; T = []
    for line in text.split('\n'):
        w = line.split()
        if not w: continue
        if w[0] == 'A': A = w[1:]
        elif w[0] == 'L': L.append(w[1:])
        elif w[0] == 'O': O.append(w[1:])
        elif w[0] == 'T': T.append(w[1])
    return A, L, O, T

# FizzLight field names in print order (booleans at 25, 26, 27)
LNAMES = ['a8', 'R', 'R2', 'w0', 'w1', 'w2', 'w3', 'invS0', 'invS1', 'invS2', 'invS3', 'invS4', 'invH0', 'invH1', 'invH2', 'invH3', 'invH4',
          'ly', 'lz', 'la', 'invA', 'fk', 'hx', 'hy', 'openR', 'openL', 'lid', 'kLid', 'tone']
BOOLS = {24, 25, 26}
ONAMES = ['K', 'cx', 'cy', 'wl', 'tv', 'sk']

def sane(O, side):
    bad = 0
    for i, o in enumerate(O):
        v = [fl(h) for h in o]
        ok = all(math.isfinite(x) for x in v) and all(0 <= v[k] <= 1 for k in (0, 3, 4, 5)) and math.hypot(v[1], v[2]) <= 1 + 1e-6
        if not ok:
            bad += 1
            if bad <= 3: print(f'{side} bubble {i}: out of range {dict(zip(ONAMES, v))}')
    return bad

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--frames', type=int, default=200)
    ap.add_argument('--bubbles', type=int, default=500)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--no-time', action='store_true')
    ap.add_argument('--no-asan', action='store_true')
    a = ap.parse_args()
    fails = []
    with tempfile.TemporaryDirectory(prefix='watches-fizzlight-') as tmp:
        tmp = Path(tmp)
        (tmp / 'd.cpp').write_text(DRIVER)
        (tmp / 'job.txt').write_text(make_job(a.frames, a.bubbles, a.seed))
        cxx = os.environ.get('CXX', 'c++')
        base = [cxx, '-std=c++17', '-ffp-contract=off', '-I', str(ROOT / 'firmware/src'), str(tmp / 'd.cpp')]
        subprocess.run([*base, '-O2', '-o', str(tmp / 'd')], check=True)
        if not a.no_asan: subprocess.run([*base, '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-o', str(tmp / 'da')], check=True)
        cache = tmp / 'sim'
        subprocess.run([str(SIM / 'node_modules/.bin/tsc'), '-p', str(SIM / 'tools/fizz-light-ref.tsconfig.json'), '--outDir', str(cache)], check=True)
        (cache / 'package.json').write_text('{}')
        js = next(cache.rglob('fizz-light-ref.js'))
        simOut = subprocess.run(['node', str(js), str(tmp / 'job.txt')], stdout=subprocess.PIPE, check=True).stdout.decode()
        (tmp / 'sim.txt').write_text(simOut)
        own = subprocess.run([str(tmp / 'd'), 'own', str(tmp / 'job.txt')], stdout=subprocess.PIPE, check=True).stdout.decode()
        fed = subprocess.run([str(tmp / 'd'), 'fed', str(tmp / 'job.txt'), str(tmp / 'sim.txt')], stdout=subprocess.PIPE, check=True).stdout.decode()
        if not a.no_asan:
            r1 = subprocess.run([str(tmp / 'da'), 'own', str(tmp / 'job.txt')], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            r2 = subprocess.run([str(tmp / 'da'), 'fed', str(tmp / 'job.txt'), str(tmp / 'sim.txt')], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            asanOk = r1.returncode == 0 and r2.returncode == 0 and r1.stdout.decode() == own and r2.stdout.decode() == fed
            if not asanOk: fails.append('ASan / UBSan'); print(r1.stderr.decode()[-2000:], r2.stderr.decode()[-2000:])
        timing = None
        if not a.no_time:
            timing = subprocess.run([str(tmp / 'd'), 'time', str(tmp / 'job.txt'), '10000000'], stdout=subprocess.PIPE, check=True).stdout.decode().split()
    sA, sL, sO, sT = parse(simOut); nA, nL, nO, nT = parse(own); fA, fL, fO, fT = parse(fed)
    nb = a.frames * a.bubbles
    if not (len(sL) == len(nL) == len(fL) == a.frames and len(sO) == len(nO) == len(fO) == nb and len(sT) == len(nT)):
        sys.exit(f'counts: frames {len(sL)} / {len(nL)} / {len(fL)}, bubbles {len(sO)} / {len(nO)} / {len(fO)}, tones {len(sT)} / {len(nT)}')
    attOk = sA == nA and len(sA) == 66
    if not attOk: fails.append('FIZZ_ATT')
    toneDiff = sum(x != y for x, y in zip(sT, nT))
    if toneDiff: fails.append('fizzTone')
    # frames: relative, booleans exact
    worstRel = 0.0; worstAt = None; boolDiff = 0; fieldsOver = 0; bitsEq = 0; nf = 0
    for i, (s, n) in enumerate(zip(sL, nL)):
        for k, (x, y) in enumerate(zip(s, n)):
            if k in BOOLS: boolDiff += x != y; continue
            nf += 1; bitsEq += x == y
            u, v = fl(x), fl(y)
            rel = 0.0 if u == v else abs(u - v) / max(abs(u), abs(v))
            if rel > worstRel: worstRel, worstAt = rel, (i, LNAMES[k], u, v)
            if rel > 2e-6: fieldsOver += 1
    if boolDiff or fieldsOver: fails.append('FizzLight fields')
    # bubbles, own frames: absolute
    worstAbs = 0.0; absAt = None; over = 0; ownExact = 0
    for i, (s, n) in enumerate(zip(sO, nO)):
        ownExact += s == n
        for k, (x, y) in enumerate(zip(s, n)):
            d = abs(fl(x) - fl(y))
            if d > worstAbs: worstAbs, absAt = d, (i // a.bubbles, i % a.bubbles, ONAMES[k], fl(x), fl(y))
            if d > 1e-4: over += 1
    if over: fails.append('FizzLit (own frames)')
    # bubbles, the sim's frames: bit for bit
    fedDiff = [(i, k) for i, (s, f) in enumerate(zip(sO, fO)) for k, (x, y) in enumerate(zip(s, f)) if x != y]
    if fedDiff:
        fails.append('FizzLit (sim frames, bits)')
        for i, k in fedDiff[:5]: print(f'fed: frame {i // a.bubbles} bubble {i % a.bubbles} {ONAMES[k]}: sim {sO[i][k]} ({fl(sO[i][k]):.9g}) native {fO[i][k]} ({fl(fO[i][k]):.9g})')
    badS, badN = sane(sO, 'sim'), sane(nO, 'native') + sane(fO, 'native fed')
    if badS or badN: fails.append('ranges')
    print(f'FIZZ_ATT {len(sA)} entries {"identical" if attOk else "DIFFER"}; fizzTone {len(sT)} triples, {toneDiff} differ')
    print(f'FizzLight: {a.frames} frames x {nf // a.frames} float fields, {bitsEq}/{nf} bit-identical, {fieldsOver} over 2e-6 relative, worst {worstRel:.3g}'
          + (f' (frame {worstAt[0]} {worstAt[1]}: sim {worstAt[2]:.9g} native {worstAt[3]:.9g})' if worstAt else '') + f'; booleans {boolDiff} differ')
    print(f'FizzLit, own frames: {nb} bubbles, {ownExact} bit-identical, {over} outputs over 1e-4, worst {worstAbs:.3g}'
          + (f' (frame {absAt[0]} bubble {absAt[1]} {absAt[2]}: sim {absAt[3]:.9g} native {absAt[4]:.9g})' if absAt else ''))
    print(f'FizzLit, the sim\'s frames: {nb} bubbles x 6 outputs, {len(fedDiff)} differ in a bit')
    print(f'ranges (finite, K / wl / tv / sk in [0, 1], |c| <= 1 + 1e-6): sim {badS}, native {badN} out' + ('' if a.no_asan else f'; ASan / UBSan {"clean" if "ASan / UBSan" not in fails else "FAILED"}'))
    if timing: print(f'host -O2: fizzLit {timing[0]} ns a bubble; the explicit set-up\'s rough equivalent {timing[1]} ns')
    print('fizz light parity: ' + ('ok' if not fails else 'FAILED: ' + ', '.join(fails)))
    sys.exit(1 if fails else 0)

if __name__ == '__main__': main()
