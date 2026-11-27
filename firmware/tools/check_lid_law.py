#!/usr/bin/env python3
"""The desk-view lid's law, firmware (src/lid_law.h) vs sim (sim/src/lidLaw.ts), host only, no board.

  python3 firmware/tools/check_lid_law.py [--laws 300] [--points 200] [--seed 1] [--no-asan]

A seeded job: laws over tau -0.5..0.6 rad, delta 0..1.3 rad, contactAngle 0..120 (20, 70, 89, 90 included) and
liquidTransparency 0..1 (0, 0.08, 0.8, 1 included), each with points q 0..1, u -0.1..1.1 (the ends included) and, for
the law's own coordinate (lo + hi) / 2w (negative by up to hw / w on a thin row), u -6..3; and lidKey on (angle, key)
pairs: angles on and an ulp or two around the step boundaries (n + 0.5) / 1024 and the hold edges key +- 0.6 / 1024, keys
NaN / the angle's step / a neighbour step / random. Every input is a float32 (hex bits) both sides read. Compared (float32 bits from both, -ffp-contract=off):
  - the tables with the native sample loop fed the sim's tanT / tanD / sd / cd / A (and its k8 / inv1t): bit for bit;
  - lidOpacity / lidWet on the sim's tables: bit for bit;
  - each side from its own trig (the firmware's float32 tanf / sinf / cosf / logf, the sim's double ones rounded, an ulp
    apart on ~1-3 % of arguments): laws whose trig agree, tables within 2e-6 relative and points within 1e-5; where an
    input differs, the dish's root near the back line is ill-conditioned (z + 1 -> 0, a near-tangent discriminant), so a
    one-ulp input moves lam there by up to ~1e-4 relative on the sim's own maths too. Those laws are held to the native
    loop's measured sensitivity, that law's own and that entry's: 2 x sum over inputs k of (ulps apart in k) x (the
    largest move one ulp of k makes in the entry, both signs: the native loop fed the sim's trig, nudged) + 2e-6
    relative; the points to the first-order bound of their tables' differences (+ 2e-6). The plain 2e-6 / 1e-5 counts
    are printed too;
  - lidKey: bit for bit;
  - hm (the meniscus rise / R) with the tables (fed: bit for bit; own trig: the tables' bound, its own one-ulp
    sensitivity) and lidRimW(law, R) for R 4..60 px (20 and 26.5 included) on every law: bit for bit given the same hm
    (the native one on the sim's hm; each side's own against a float32 model of it), own trig within the bound of the
    hm difference;
  - both sides: every value finite, lam in [0, 4] and non-increasing over u, keep / opacity / wet in [0, 1].
Pinned second-to-last law, the front-wall branch (review 1: tau 0, delta 75 deg, contactAngle 20, transparency 0.08):
lam > 1 at u = 1 / 16, non-increasing, no 0 before the last entry, on both sides.
Pinned last law, the board pose (tau 13 deg, delta 11 deg, contactAngle 70, transparency 0.08): lam at u 0 / .25 / .5 /
.75 / 1 = 1.528 / 0.662 / 0.369 / 0.164 / 0 and F = 1 - keep at u .25 / .5 = 0.109 / 0.057, within 2e-3 on both sides
(docs/lid-fill/model.md); hm 0.1763 (tan 10 deg) within 1e-4 and lidRimW at R 20 = 1.234 within 2e-3. The back contact
band's clamps: contactAngle 20 (the front-wall law) at R 20 -> 3 (LID_RIM_MAX), contactAngle 89 (a pinned law) -> 0.5
(LID_RIM_MIN), on both sides.
Also a native run under ASan / UBSan (--no-asan skips it). Exits 1 on any failure.
"""
import argparse, math, os, random, struct, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / 'sim'
DRIVER = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "lid_law.h"
static float fh(const char *s) { uint32_t u = (uint32_t)strtoul(s, nullptr, 16); float f; memcpy(&f, &u, 4); return f; }
static void ph(float f) { uint32_t u; memcpy(&u, &f, 4); printf(" %08x", u); }
static int words(char *line, char **w, int n) {
  int k = 0; for (char *t = strtok(line, " \t\r\n"); t && k < n; t = strtok(nullptr, " \t\r\n")) w[k++] = t; return k;
}
#define LWORDS (1 + 7 + 2 * (LID_N + 1) + 1)
// "L tanT tanD sd cd A k8 inv1t lam keep hm" of the sim's output (fed mode)
static bool readLaw(FILE *f, float *trig, LidLaw &L) {
  static char line[8192]; char *w[LWORDS + 4];
  while (fgets(line, sizeof line, f)) {
    if (line[0] != 'L') continue;
    if (words(line, w, LWORDS + 4) != LWORDS) return false;
    int k = 1; for (int i = 0; i < 5; i++) trig[i] = fh(w[k++]);
    L.k8 = fh(w[k++]); L.inv1t = fh(w[k++]);
    for (float &v : L.lam) v = fh(w[k++]);
    for (float &v : L.keep) v = fh(w[k++]);
    L.hm = fh(w[k++]);
    return true;
  }
  return false;
}
int main(int argc, char **argv) {
  if (argc < 3) return 2;
  const bool nudge = !strcmp(argv[1], "nudge"), fedMode = nudge || !strcmp(argv[1], "fed");
  FILE *job = fopen(argv[2], "r"); if (!job) return 2;
  FILE *fed = fedMode ? fopen(argv[3], "r") : nullptr;
  if (fedMode && !fed) return 2;
  char line[1024]; char *w[8]; LidLaw L{}, S{}; bool have = false;
  while (fgets(line, sizeof line, job)) {
    const int n = words(line, w, 8);
    if (n == 5 && !strcmp(w[0], "W")) {
      const float tau = fh(w[1]), delta = fh(w[2]), th = fh(w[3]), tr = fh(w[4]);
      float trig[5];
      if (fedMode) {   // the sample loop from the sim's trig; the points on the sim's own tables
        if (!readLaw(fed, trig, S)) { fprintf(stderr, "fed: sim law missing\n"); return 3; }
        lidLawSamples(L, trig[0], trig[1], trig[2], trig[3], trig[4]); L.k8 = S.k8; L.inv1t = S.inv1t;   // S.hm: the sim's
        if (nudge) {   // the sample loop's sensitivity: each input one ulp up / down ("N input sign lam keep")
          for (int i = 0; i < 5; i++) for (int sg = -1; sg <= 1; sg += 2) {
            float t2[5]; memcpy(t2, trig, sizeof t2); t2[i] = nextafterf(t2[i], sg * INFINITY);
            LidLaw V{}; lidLawSamples(V, t2[0], t2[1], t2[2], t2[3], t2[4]);
            printf("N %d %d", i, sg); for (float v : V.lam) ph(v); for (float v : V.keep) ph(v); ph(V.hm); printf("\n");
          }
          continue;
        }
      } else {
        lidLawBuild(L, tau, delta, th, tr);
        const float thr = fizzMx(20, fizzMn(89, th)) * (float)(M_PI / 180);
        trig[0] = tanf(tau); trig[1] = tanf(delta); trig[2] = sinf(delta); trig[3] = cosf(delta); trig[4] = 1 / cosf(thr);
        S = L;
      }
      printf("L"); for (float v : trig) ph(v); ph(L.k8); ph(L.inv1t); for (float v : L.lam) ph(v); for (float v : L.keep) ph(v); ph(L.hm); printf("\n");
      have = true;
    } else if (n == 3 && !strcmp(w[0], "K") && !nudge) {
      printf("Y"); ph(lidKey(fh(w[1]), fh(w[2]))); printf("\n");
    } else if (n == 2 && !strcmp(w[0], "R") && have && !nudge) {   // the back contact band on S's hm (fed: the sim's)
      printf("M"); ph(lidRimW(S, fh(w[1]))); printf("\n");
    } else if (n == 3 && !strcmp(w[0], "P") && have && !nudge) {
      const float q = fh(w[1]), u = fh(w[2]);
      printf("O"); ph(lidOpacity(S, q, u)); ph(lidWet(S, q, u)); printf("\n");
    }
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

PIN = (math.radians(13), math.radians(11), 70, 0.08)
FRONT = (0, math.radians(75), 20, 0.08)   # review 1: the refracted ray runs to the front wall
# poses whose table takes the front-wall path below the cap of 4 (rare: ~1 in 10^4 of a tau x delta x theta grid), so the
# fed comparison holds that branch's arithmetic bit for bit
FRONT_LOW = [(0.49, 0.8775, 29, 0.08), (0.2333, 0.8612, 35, 0.08), (0.16, 0.8775, 35, 0.5)]
PIN_LAM = [(0, 1.528), (8, 0.662), (16, 0.369), (24, 0.164), (32, 0.0)]   # table index (u = i / 32), lam
PIN_F = [(8, 0.109), (16, 0.057)]                                            # 1 - keep
TH89 = (0, math.radians(11), 89, 0.08)   # the back contact band's floor (lidRimW 0.5 at R 20)
RADII = [4, 4.5, 5, 6, 7.25, 8, 10, 12.5, 15, 17.75, 20, 22, 26.5, 30, 33.3, 40, 47.1, 52, 60]   # lidRimW's R, px
PIN_HM, PIN_RIM, R_PIN = 0.1763, 1.234, RADII.index(20)

def make_job(laws, points, seed):
    rnd = random.Random(seed)
    lines = []
    def pick(special, lo, hi, p=0.25):
        return rnd.choice(special) if rnd.random() < p else rnd.uniform(lo, hi)
    def pts():
        for k in range(points):
            q = pick([0, 1, 0.5], 0, 1, 0.1)
            if k < 14: u = (-0.1, 0, 1, 1.1, 0.5, 1 / 32, 31 / 32, -6, -1, -0.5, -0.01, 1.01, 1.5, 3)[k]
            elif k % 4 == 0: u = rnd.uniform(-6, 3)    # the law's own coordinate (lo + hi) / 2w: below 0 by up to hw / w
            else: u = rnd.uniform(-0.1, 1.1)
            lines.append('P ' + hx(q) + ' ' + hx(u))
        lines.extend('R ' + hx(r) for r in RADII)   # no rnd: the key job below keeps its draws
    for _ in range(laws):
        tau = pick([0, -0.5, 0.6, math.radians(13)], -0.5, 0.6)
        delta = pick([0, 1.3, math.radians(11)], 0, 1.3)
        theta = pick([0, 20, 70, 89, 90, 120], 0, 120, 0.4)
        t = pick([0, 0.08, 0.8, 1, 0.01, 0.999], 0, 1, 0.4)
        lines.append('W ' + ' '.join(hx(v) for v in (tau, delta, theta, t)))
        pts()
    lines.append('W ' + ' '.join(hx(v) for v in TH89))
    pts()
    for w in FRONT_LOW:
        lines.append('W ' + ' '.join(hx(v) for v in w))
        pts()
    lines.append('W ' + ' '.join(hx(v) for v in FRONT))
    pts()
    lines.append('W ' + ' '.join(hx(v) for v in PIN))
    pts()
    lines += key_job(rnd)
    return '\n'.join(lines) + '\n'

def nextf(v, n):   # the float n ulps from float v (finite, n may be negative)
    i = struct.unpack('<i', struct.pack('<f', f32(v)))[0]
    i = i if i >= 0 else -(i & 0x7fffffff)   # ordered by value
    j = i + n
    return struct.unpack('<f', struct.pack('<i', j if j >= 0 else (-j) | -0x80000000))[0]

NAN_HEX = '7fc00000'
def key_job(rnd):
    out = []
    def K(angle, key): out.append('K ' + hx(angle) + ' ' + (key if isinstance(key, str) else hx(key)))
    STEPS = 1024   # lid_law.h / lidLaw.ts LID_KEY_STEPS
    step = lambda a: math.floor(f32(f32(a * STEPS) + 0.5)) / STEPS
    for _ in range(600):   # step boundaries (n + 0.5) / STEPS and an ulp or two around them
        b = (rnd.randint(-720, 1600) + 0.5) / STEPS
        for d in (-2, -1, 0, 1, 2):
            a = nextf(b, d)
            K(a, NAN_HEX); K(a, step(a)); K(a, step(a) + 1 / STEPS)
    for _ in range(600):   # the hold edges: key +- 0.6 / STEPS and an ulp or two around
        key = rnd.randint(-720, 1600) / STEPS
        for e in (f32(0.6 / STEPS), -f32(0.6 / STEPS)):
            for d in (-2, -1, 0, 1, 2): K(nextf(f32(key + e), d), key)
    for _ in range(1000):  # random angles and keys
        a = rnd.uniform(-0.6, 1.4)
        K(a, rnd.choice([NAN_HEX, step(a), step(a) - 1 / STEPS, rnd.uniform(-0.6, 1.4), a]))
    K(0.0, NAN_HEX); K(-0.0, NAN_HEX); K(0.0, -0.0); K(-0.5 / STEPS, NAN_HEX); K(0.5 / STEPS, NAN_HEX)
    return out

def parse(text):
    L = []; O = []; Y = []; M = []
    for line in text.split('\n'):
        w = line.split()
        if not w: continue
        if w[0] == 'L': L.append(w[1:])
        elif w[0] == 'O': O.append(w[1:])
        elif w[0] == 'Y': Y.append(w[1])
        elif w[0] == 'M': M.append(w[1])
    return L, O, Y, M

N1 = 33
def fields(l):   # -> trig[5], k8, inv1t, lam[33], keep[33] as hex strings (hmOf: hm)
    return l[:5], l[5], l[6], l[7:7 + N1], l[7 + N1:7 + 2 * N1]

def hmOf(l):
    return l[7 + 2 * N1]

def rimModel(hm, r):   # lidRimW in float32 (sim: max(0.5, min(3, F(F(hm F(R)) F(0.35)))))
    return max(0.5, min(3.0, f32(f32(hm * f32(r)) * f32(0.35))))

def sane(L, O, side):
    bad = 0
    for i, l in enumerate(L):
        _, k8, inv, lam, keep = fields(l)
        v = [fl(h) for h in [k8, inv, *lam, *keep]]
        lv = [fl(h) for h in lam]
        ok = all(math.isfinite(x) for x in v) and all(0 <= x <= 4 for x in lv) and all(0 <= fl(h) <= 1 for h in keep) \
            and all(lv[j] >= lv[j + 1] for j in range(N1 - 1))
        if not ok:
            bad += 1
            if bad <= 3: print(f'{side} law {i}: out of range')
    for i, o in enumerate(O):
        v = [fl(h) for h in o]
        if not all(math.isfinite(x) and 0 <= x <= 1 for x in v):
            bad += 1
            if bad <= 3: print(f'{side} point {i}: out of range {v}')
    return bad

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--laws', type=int, default=300)
    ap.add_argument('--points', type=int, default=200)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--no-asan', action='store_true')
    a = ap.parse_args()
    fails = []
    with tempfile.TemporaryDirectory(prefix='watches-lidlaw-') as tmp:
        tmp = Path(tmp)
        (tmp / 'd.cpp').write_text(DRIVER)
        (tmp / 'job.txt').write_text(make_job(a.laws, a.points, a.seed))
        cxx = os.environ.get('CXX', 'c++')
        base = [cxx, '-std=c++17', '-ffp-contract=off', '-Wall', '-I', str(ROOT / 'firmware/src'), str(tmp / 'd.cpp')]
        subprocess.run([*base, '-O2', '-o', str(tmp / 'd')], check=True)
        if not a.no_asan: subprocess.run([*base, '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-o', str(tmp / 'da')], check=True)
        cache = tmp / 'sim'
        subprocess.run([str(SIM / 'node_modules/.bin/tsc'), '-p', str(SIM / 'tools/lid-law-ref.tsconfig.json'), '--outDir', str(cache)], check=True)
        (cache / 'package.json').write_text('{}')
        js = next(cache.rglob('lid-law-ref.js'))
        simOut = subprocess.run(['node', str(js), str(tmp / 'job.txt')], stdout=subprocess.PIPE, check=True).stdout.decode()
        (tmp / 'sim.txt').write_text(simOut)
        own = subprocess.run([str(tmp / 'd'), 'own', str(tmp / 'job.txt')], stdout=subprocess.PIPE, check=True).stdout.decode()
        fed = subprocess.run([str(tmp / 'd'), 'fed', str(tmp / 'job.txt'), str(tmp / 'sim.txt')], stdout=subprocess.PIPE, check=True).stdout.decode()
        nud = subprocess.run([str(tmp / 'd'), 'nudge', str(tmp / 'job.txt'), str(tmp / 'sim.txt')], stdout=subprocess.PIPE, check=True).stdout.decode()
        if not a.no_asan:
            r1 = subprocess.run([str(tmp / 'da'), 'own', str(tmp / 'job.txt')], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            r2 = subprocess.run([str(tmp / 'da'), 'fed', str(tmp / 'job.txt'), str(tmp / 'sim.txt')], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if not (r1.returncode == 0 and r2.returncode == 0 and r1.stdout.decode() == own and r2.stdout.decode() == fed):
                fails.append('ASan / UBSan'); print(r1.stderr.decode()[-2000:], r2.stderr.decode()[-2000:])
    sL, sO, sY, sM = parse(simOut); nL, nO, nY, nM = parse(own); fL, fO, fY, fM = parse(fed)
    nl = a.laws + len(FRONT_LOW) + 3; npt = nl * a.points; nR = len(RADII)
    if not (len(sM) == len(nM) == len(fM) == nl * nR): sys.exit(f'counts: lidRimW {len(sM)} / {len(nM)} / {len(fM)}')
    if not (len(sY) == len(nY) == len(fY) > 0): sys.exit(f'counts: lidKey {len(sY)} / {len(nY)} / {len(fY)}')
    keyDiff = [i for i, (x, y, z) in enumerate(zip(sY, nY, fY)) if not (x == y == z)]
    if keyDiff:
        fails.append('lidKey')
        kj = [l for l in make_job(a.laws, a.points, a.seed).split('\n') if l.startswith('K')]
        for i in keyDiff[:5]: print(f'lidKey: {kj[i]}: sim {sY[i]} native {nY[i]}')
    if not (nud.count('N ') == 10 * nl and len(sL) == len(nL) == len(fL) == nl and len(sO) == len(nO) == len(fO) == npt):
        sys.exit(f'counts: laws {len(sL)} / {len(nL)} / {len(fL)}, points {len(sO)} / {len(nO)} / {len(fO)}')
    # tables, own trig: the plain relative counts, and against the sensitivity bound where the trig inputs differ
    sens = [[[0.0] * (2 * N1 + 1) for _ in range(5)] for _ in range(nl)]   # law, input, value (lam, keep, hm): the largest one-ulp move
    jumps = []; nN = 0
    for line in nud.split('\n'):
        w = line.split()
        if w and w[0] == 'N':
            li = nN // 10; nN += 1   # 5 inputs x 2 signs a law
            base = sL[li][7:7 + 2 * N1 + 1]
            for j, (x, y) in enumerate(zip(base, w[3:])):
                d = abs(fl(x) - fl(y)); k = int(w[1])
                if d > 1e-3:   # a jump across a branch (the dish's discriminant, the cuts |tz| > 1e-3, the fold): counted, and in that entry's own bound
                    jumps.append((li, k, int(w[2]), ('lam', 'keep', 'hm')[j // N1], j % N1, fl(x), fl(y)))
                if d > sens[li][k][j]: sens[li][k][j] = d
    def ulps(x, y):   # float32 ulps between two finite floats of one sign (as here)
        return abs(struct.unpack('<i', struct.pack('<f', fl(x)))[0] - struct.unpack('<i', struct.pack('<f', fl(y)))[0])
    worstRel = 0.0; worstAt = None; over = 0; bitsEq = 0; nf = 0; trigEq = 0; overB = 0; worstB = 0.0; worstBAt = None
    dTab = []   # per law: |own - sim| of lam, keep, k8, inv1t (for the points' bound)
    for i, (s_, n) in enumerate(zip(sL, nL)):
        st, sk, si, slam, skeep = fields(s_); nt, nk, ni, nlam, nkeep = fields(n)
        same = st == nt; trigEq += same
        du = [ulps(x, y) for x, y in zip(st, nt)]
        dTab.append(([abs(fl(x) - fl(y)) for x, y in zip(slam, nlam)], [abs(fl(x) - fl(y)) for x, y in zip(skeep, nkeep)],
                     abs(fl(sk) - fl(nk)), abs(fl(si) - fl(ni))))
        for name, xs, ys, off in (('k8', [sk], [nk], None), ('inv1t', [si], [ni], None), ('lam', slam, nlam, 0), ('keep', skeep, nkeep, N1),
                                  ('hm', [hmOf(s_)], [hmOf(n)], 2 * N1)):
            for j, (x, y) in enumerate(zip(xs, ys)):
                nf += 1; bitsEq += x == y
                u, v = fl(x), fl(y)
                rel = 0.0 if u == v else abs(u - v) / max(abs(u), abs(v))
                if rel > worstRel: worstRel, worstAt = rel, (i, name, j, u, v)
                if rel > 2e-6: over += 1
                lim = 2e-6 * max(abs(u), abs(v))
                if off is not None and not same: lim += 2 * sum(du[k] * sens[i][k][off + j] for k in range(5))   # this law's, this entry's
                if abs(u - v) > lim:
                    overB += 1
                    if overB <= 5: print(f'own trig: law {i} {name}[{j}]: sim {u:.9g} native {v:.9g}, bound {lim:.3g} (inputs {du} ulps apart)')
                if lim > 0 and abs(u - v) / lim > worstB: worstB, worstBAt = abs(u - v) / lim, (i, name, j)
    if overB: fails.append('tables (own trig)')
    # tables, the sim's trig: bits
    fedDiff = [(i, k) for i, (s, f) in enumerate(zip(sL, fL)) for k, (x, y) in enumerate(zip(s[5:], f[5:])) if x != y]
    if fedDiff:
        fails.append('tables (sim trig, bits)')
        for i, k in fedDiff[:5]: print(f'fed: law {i} field {k}: sim {sL[i][5 + k]} native {fL[i][5 + k]}')
    # points, the sim's tables: bits; own tables: absolute
    ptDiff = [(i, k) for i, (s, f) in enumerate(zip(sO, fO)) for k in range(2) if s[k] != f[k]]
    if ptDiff:
        fails.append('lidOpacity / lidWet (sim tables, bits)')
        for i, k in ptDiff[:5]: print(f'fed: law {i // a.points} point {i % a.points} {("opacity", "wet")[k]}: sim {sO[i][k]} native {fO[i][k]}')
    worstAbs = 0.0; absAt = None; overA = 0; ptEq = 0; overP = 0
    pts = [l.split()[1:] for l in make_job(a.laws, a.points, a.seed).split('\n') if l.startswith('P')]
    for i, (s_, n) in enumerate(zip(sO, nO)):
        ptEq += s_ == n
        li = i // a.points
        q, u = fl(pts[i][0]), fl(pts[i][1])
        v = min(1.0, max(0.0, u)) * 32; j = min(31, int(v))
        dlam, dkeep, dk8, dinv = dTab[li]
        _, sk, si, slam, _ = fields(sL[li])
        k8, inv1t, lamMax = fl(sk), fl(si), max(fl(slam[j]), fl(slam[j + 1]))
        dl, dkp = max(dlam[j], dlam[j + 1]), max(dkeep[j], dkeep[j + 1])
        dv = (k8 * q * dl + dk8 * q * lamMax) / 8   # the attenuation's argument / 8: its slope is at most 1 / 8
        bound = (dkp + dv + 2e-6, (dv * inv1t + dinv + 2e-6) if inv1t > 0 else q * dl + 2e-6)
        for k in range(2):
            d = abs(fl(s_[k]) - fl(n[k]))
            if d > worstAbs: worstAbs, absAt = d, (li, i % a.points, ('opacity', 'wet')[k], fl(s_[k]), fl(n[k]))
            if d > 1e-5: overA += 1
            if d > max(1e-5 if sL[li][:5] == nL[li][:5] else 0, bound[k]):
                overP += 1
                if overP <= 5: print(f'own tables: law {li} point {i % a.points} {("opacity", "wet")[k]}: sim {fl(s_[k]):.9g} native {fl(n[k]):.9g}, bound {bound[k]:.3g}')
    if overP: fails.append('lidOpacity / lidWet (own tables)')
    # the back contact band: fed bit for bit (the sim's hm), each side against the float32 model on its own hm, own trig
    # within the hm difference's bound
    rimFed = [i for i, (x, y) in enumerate(zip(sM, fM)) if x != y]
    rimModelOff = [(side, i) for side, (Ls, Ms) in (('sim', (sL, sM)), ('native', (nL, nM))) for i, m in enumerate(Ms)
                   if f32(rimModel(fl(hmOf(Ls[i // nR])), RADII[i % nR])) != fl(m)]
    rimOwn = 0; rimOwnEq = 0
    for i, (x, y) in enumerate(zip(sM, nM)):
        rimOwnEq += x == y
        dh = abs(fl(hmOf(sL[i // nR])) - fl(hmOf(nL[i // nR])))
        if abs(fl(x) - fl(y)) > dh * RADII[i % nR] * 0.35 + 2e-6 * max(abs(fl(x)), abs(fl(y))):
            rimOwn += 1
            if rimOwn <= 5: print(f'lidRimW own: law {i // nR} R {RADII[i % nR]}: sim {fl(x):.9g} native {fl(y):.9g}')
    for i in rimFed[:5]: print(f'lidRimW fed: law {i // nR} R {RADII[i % nR]}: sim {sM[i]} native {fM[i]}')
    for side, i in rimModelOff[:5]: print(f'lidRimW {side}: law {i // nR} R {RADII[i % nR]}: off the float32 model')
    if rimFed: fails.append('lidRimW (sim hm, bits)')
    if rimModelOff: fails.append('lidRimW (float32 model)')
    if rimOwn: fails.append('lidRimW (own trig)')
    # its pins: the board pose (last law), contactAngle 20 (the front-wall law, second to last), 89 (TH89)
    iTh89 = nl - 3 - len(FRONT_LOW)
    rimPin = []
    for Ls, Ms in ((sL, sM), (nL, nM)):
        rimPin.append((fl(hmOf(Ls[-1])), fl(Ms[(nl - 1) * nR + R_PIN]), fl(Ms[(nl - 2) * nR + R_PIN]), fl(Ms[iTh89 * nR + R_PIN])))
    rimPinOk = all(abs(hm - PIN_HM) <= 1e-4 and abs(r70 - PIN_RIM) <= 2e-3 and r20 == 3.0 and r89 == 0.5 for hm, r70, r20, r89 in rimPin)
    if not rimPinOk: fails.append('pinned back contact band')
    badS = sane(sL, sO, 'sim'); badN = sane(nL, nO, 'native') + sane(fL, fO, 'native fed')
    if badS or badN: fails.append('ranges')
    # the board pose, last law
    pin = []
    for L in (sL, nL):
        _, _, _, lam, keep = fields(L[-1])
        pin.append(([fl(lam[i]) for i, _ in PIN_LAM], [1 - fl(keep[i]) for i, _ in PIN_F]))
    pinOk = all(abs(v - w) <= 2e-3 for lam, F in pin for v, w in zip(lam + F, [x for _, x in PIN_LAM] + [x for _, x in PIN_F]))
    if not pinOk: fails.append('pinned board pose')
    # the front-wall branch, second-to-last law
    front = []
    for L in (sL, nL, fL):
        lam = [fl(h) for h in fields(L[-2])[3]]
        front.append((lam[2], all(lam[j] >= lam[j + 1] for j in range(N1 - 1)), all(x > 0 for x in lam[:-1])))
    frontOk = all(l2 > 1 and mono and pos for l2, mono, pos in front)
    if not frontOk: fails.append('front-wall branch')
    print(f'tables, own trig: {nl} laws x {nf // nl} values, {bitsEq}/{nf} bit-identical, {over} over 2e-6 relative, worst {worstRel:.3g}'
          + (f' (law {worstAt[0]} {worstAt[1]}[{worstAt[2]}]: sim {worstAt[3]:.9g} native {worstAt[4]:.9g})' if worstAt else '')
          + f'; trig inputs bit-identical on {trigEq}/{nl} laws; {overB} over the per-value bound (2e-6 relative + where the trig differs 2 x sum_k ulps_k x that entry\'s one-ulp sensitivity to k; {len(jumps)} one-ulp moves over 1e-3 among them), worst {worstB:.2f} of it'
          + (f' (law {worstBAt[0]} {worstBAt[1]}[{worstBAt[2]}])' if worstBAt else ''))
    for j in jumps[:3]: print(f'one-ulp jump: law {j[0]} input {j[1]} {"+-"[j[2] < 0]}1 ulp: {j[3]}[{j[4]}] {j[5]:.6g} -> {j[6]:.6g}')
    print(f'lidKey: {len(sY)} (angle, key) pairs, {len(keyDiff)} differ in a bit')
    print(f'tables, the sim\'s trig: {nl} laws x {3 + 2 * N1} values (k8, inv1t, lam, keep, hm), {len(fedDiff)} differ in a bit')
    print(f'lidOpacity / lidWet, the sim\'s tables: {npt} points x 2, {len(ptDiff)} differ in a bit')
    print(f'lidOpacity / lidWet, own tables: {npt} points, {ptEq} bit-identical, {overA} outputs over 1e-5, worst {worstAbs:.3g}'
          + (f' (law {absAt[0]} point {absAt[1]} {absAt[2]}: sim {absAt[3]:.9g} native {absAt[4]:.9g})' if absAt else '')
          + f'; {overP} over the bound (1e-5 where the trig agrees, else the tables\' first-order bound)')
    print(f'lidRimW: {nl} laws x {nR} R (4..60 px), the sim\'s hm: {len(rimFed)} differ in a bit; off the float32 model on its own hm: {len(rimModelOff)}; '
          f'own trig: {rimOwnEq}/{len(sM)} bit-identical, {rimOwn} over the hm difference\'s bound')
    for side, (hm, r70, r20, r89) in zip(('sim', 'native'), rimPin):
        print(f'back contact band ({side}): hm {hm:.4f}, lidRimW at R 20: contactAngle 70 {r70:.4f}, 20 {r20:g}, 89 {r89:g}')
    print(f'back contact band: want hm {PIN_HM} within 1e-4, lidRimW {PIN_RIM} within 2e-3, 3, 0.5: {"ok" if rimPinOk else "MOVED"}')
    for side, (lam, F) in zip(('sim', 'native'), pin):
        print(f'board pose ({side}): lam ' + ' / '.join(f'{v:.3f}' for v in lam) + ', F ' + ' / '.join(f'{v:.3f}' for v in F))
    print(f'board pose: want lam ' + ' / '.join(str(x) for _, x in PIN_LAM) + ', F ' + ' / '.join(str(x) for _, x in PIN_F) + f' within 2e-3: {"ok" if pinOk else "MOVED"}')
    print('front wall (tau 0, delta 75 deg, contactAngle 20, t 0.08): ' + '; '.join(f'{side} lam(1/16) {l2:.3f}, non-increasing {mono}, no 0 before the last {pos}' for side, (l2, mono, pos) in zip(('sim', 'native', 'native fed'), front))
          + f': {"ok" if frontOk else "FAILED"}')
    print(f'ranges (finite, lam in [0, 4] and non-increasing, keep / opacity / wet in [0, 1]): sim {badS}, native {badN} out' + ('' if a.no_asan else f'; ASan / UBSan {"clean" if "ASan / UBSan" not in fails else "FAILED"}'))
    print('lid law parity: ' + ('ok' if not fails else 'FAILED: ' + ', '.join(fails)))
    sys.exit(1 if fails else 0)

if __name__ == '__main__': main()
