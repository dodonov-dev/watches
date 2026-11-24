// perf-cheap A evidence (host only, not built by the firmware): a still board through ImuFilter + followClock + stepTube
// + renderTube (lcd316 320w8-8, tiles, push lens), the look on stdin as `P name=value` lines (fizz off: random).
//   build_noise.sh SRC_DIR OUT   (SRC_DIR = a firmware/src: this branch's, or 87f19af's in a worktree, W=<that worktree>)
//   OUT sigma along across normal frames qL hL qA hA qB hB [mode [rate]]
// sigma: Gaussian accel noise (g) per axis, or -1 = replay NOISE_FILE (along / across / normal deviations a line, the
// board's recorded `i` stream at rest: imu_rest_dev.txt). q*/h*: an extra quantHyst-like hold applied by the harness to
// light (deg), angle (deg), backTilt (rad) before the render (0 = none: the build's own physics only), h in steps.
// mode 0 (the only one): per frame changed pixels and frame-to-frame deltas of the SHOWN rows (the push-lens map applied,
// panel byte order swapped to native RGB565), dirty tile pairs (the push's work), light changes. rate: an across ramp,
// g/s. FRAMES_OUT=file writes every frame's shown rows, native RGB565 (cmp.py compares two builds' files). HOLD_EDGES / DUMP: experiments (slug, slosh, cap held; state).
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <random>
#include <algorithm>
#include "render.h"
#include "layout.h"
#include "tiles.h"
static uint16_t strip[2][2][PANEL_W * TUBE_HEIGHT_MAX], prev[2][PANEL_W * TUBE_HEIGHT_MAX];
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
// hysteresis quantiser: index i (value i * d); moves when the value leaves (i +- h) * d, to the nearest index inside
static float hyst(float v, float q, float d, float h) {
  if (d <= 0) return v;
  const float u = v / d, i = q / d;
  if (u - i > h) return ceilf(u - h) * d;
  if (i - u > h) return floorf(u + h) * d;
  return q;
}
int main(int argc, char **argv) {
  if (!render_init() || !physics_init()) return 3;
  const float sigma = atof(argv[1]), A = atof(argv[2]), C = atof(argv[3]), N = atof(argv[4]);
  const int frames = atoi(argv[5]);
  const float qL = atof(argv[6]), hL = atof(argv[7]), qA = atof(argv[8]), hA = atof(argv[9]), qB = atof(argv[10]), hB = atof(argv[11]);
  const int mode = argc > 12 ? atoi(argv[12]) : 0; const float rate = argc > 13 ? atof(argv[13]) : 0;   // mode 1: quantised vs raw render; rate: across ramp g/s after warm-up
  static long fHist[256]; int fMax = 0;
  long dHist[256] = {0}; int dMax = 0; long dPx = 0, stepMax = 0;
  Params design = PRESET_DEFAULT, p[2]; TubeState st[2];
  for (int i = 0; i < 2; i++) { st[i].trace = traceBuf(i); st[i].traceWet = traceWetBuf(i); }
  char line[512];
  while (fgets(line, sizeof line, stdin)) {
    line[strcspn(line, "\r\n")] = 0;
    if (line[0] == 'P') { char *eq = strchr(line + 2, '='); if (!eq) return 4; *eq = 0; setParam(design, line + 2, eq + 1); }
  }
  for (int i = 0; i < 2; i++) boardParams(design, p[i], TUBE_PX_SCALE(i), PX_SCALE_FIZZ);
  const FaceLayout lay = faceLayout(p[0], p[1]);
  ImuFilter f; std::mt19937 rng(12345); std::normal_distribution<float> nd(0, sigma > 0 ? sigma : 1);
  static float dev[20000][3]; int nDev = 0;   // sigma < 0: replay the board's recorded deviations (imu_dev.txt), cycled
  if (sigma < 0) { FILE *df = fopen(getenv("NOISE_FILE"), "r"); while (nDev < 20000 && fscanf(df, "%f %f %f", &dev[nDev][0], &dev[nDev][1], &dev[nDev][2]) == 3) nDev++; fclose(df); }
  const float fills[2] = {(float)((10 + 9.5 / 60) / 12), (float)(9.5 / 60)};
  TubeState q[2] = {st[0], st[1]};
  double sumPx[2] = {0, 0}, sumPairs[2] = {0, 0}; long lightCh[2] = {0, 0}, dirtyFrames[2] = {0, 0}, frameN = 0;
  float lmin[2] = {1e9, 1e9}, lmax[2] = {-1e9, -1e9}, amin = 1e9, amax = -1e9, bmin = 1e9, bmax = -1e9;
  float prevLight[2] = {NAN, NAN};
  const int warm = 500;   // 10 s settle
  for (int k = 0; k < warm + frames; k++) {
    const float ramp = k >= warm ? rate * (k - warm) * PHYS_DT : 0;
    TiltInput raw = sigma < 0 ? TiltInput{A + dev[k % nDev][0], C + ramp + dev[k % nDev][1], 0, 0, N + dev[k % nDev][2]}
                              : TiltInput{A + nd(rng), C + ramp + nd(rng), 0, 0, N + nd(rng)};
    TiltInput in = f.step(raw, p[0]);
    for (int i = 0; i < 2; i++) {
      followClock(st[i], fills[i], PHYS_DT, k == 0);
      stepTube(st[i], in, p[i], PHYS_DT, TUBE_PX_SCALE(i));
      st[i].backTilt = f.backTilt();
      // the experiment's quantisation: what the render reads
      TubeState s = st[i];
      s.light = k == 0 ? hyst(st[i].light, roundf(st[i].light / (qL > 0 ? qL : 1)) * (qL > 0 ? qL : 1), qL, hL) : hyst(st[i].light, q[i].light, qL, hL);
      s.angle = k == 0 ? st[i].angle : hyst(st[i].angle, q[i].angle, qA, hA);
      s.backTilt = k == 0 ? st[i].backTilt : hyst(st[i].backTilt, q[i].backTilt, qB, hB);
      if (getenv("HOLD_EDGES")) {   // experiment: slug / slosh / cap held at 1/16 px, HOLD_EDGES steps of hysteresis
        const float he = atof(getenv("HOLD_EDGES"));
        s.slugPos = k == 0 ? st[i].slugPos : hyst(st[i].slugPos, q[i].slugPos, 0.0625f, he);
        s.fillPos = k == 0 ? st[i].fillPos : hyst(st[i].fillPos, q[i].fillPos, 0.0625f, he);
        s.cap = k == 0 ? st[i].cap : hyst(st[i].cap, q[i].cap, 0.0625f, he);
      }
      if (getenv("DUMP") && k >= warm && k < warm + 5 && i == 1) printf("st fill %.6f slug %.6f vel %.6f cap %.6f pinF %.6f pinH %.6f lineVF %.6f reading %.6f edgeL %.6f acrossT %.6f film %.6f %.6f ag %.6f\n", st[i].fillPos, st[i].slugPos, st[i].slugVel, st[i].cap, st[i].pinFree, st[i].pinHome, st[i].lineVFree, st[i].reading, st[i].edgeLight, st[i].acrossTilt, st[i].filmFree, st[i].filmHome, st[i].agitation);
      q[i] = s;
      uint16_t *buf = strip[i][k & 1];
      const int16_t *map = nullptr; renderTube(i, s, p[i], 2, buf, &map, lay.top(i));
      // the shown rows (the push applies the lens row map), in native RGB565 (the strip holds panel byte order)
      static uint16_t shown[2][PANEL_W * TUBE_HEIGHT_MAX];
      for (int r = 0; r < lay.rows(i); r++)
        for (int x = 0; x < PANEL_W; x++) shown[i][r * PANEL_W + x] = __builtin_bswap16(buf[(map ? map[r] : r) * PANEL_W + x]);
      if (k >= warm && getenv("FRAMES_OUT")) {
        static FILE *fo = fopen(getenv("FRAMES_OUT"), "wb");
        fwrite(shown[i], 2, lay.rows(i) * PANEL_W, fo);
        if (k == warm + frames - 1 && i == 1) fclose(fo);
      }
      if (k >= warm) {
        if (i == 0) frameN++;
        const int rows = lay.rows(i); long px = 0;
        auto ex = [](uint16_t c, int ch) { const int v = ch == 0 ? (c >> 11 & 31) << 3 | (c >> 13) : ch == 1 ? (c >> 5 & 63) << 2 | (c >> 9 & 3) : (c & 31) << 3 | (c >> 2 & 7); return v; };
        for (int j = 0; j < rows * PANEL_W; j++) if (shown[i][j] != prev[i][j]) {
          px++; int d = 0; for (int ch = 0; ch < 3; ch++) d = std::max(d, abs(ex(shown[i][j], ch) - ex(prev[i][j], ch)));
          if (mode == 0) { fHist[d]++; if (d > fMax) fMax = d; }
        }
        const TileDirty *d = tile_dirty(buf); long pairs = 0;
        if (d && d->valid) for (int t = 0; t < TILE_MAX; t++) for (int w = 0; w < TILE_PAIR_WORDS; w++) pairs += __builtin_popcount(d->bits[t][w]);
        else pairs = -1;
        sumPx[i] += px; sumPairs[i] += pairs; dirtyFrames[i] += px > 0;
        if (s.light != prevLight[i]) lightCh[i]++;
        lmin[i] = fminf(lmin[i], st[i].light); lmax[i] = fmaxf(lmax[i], st[i].light);
        if (i == 0) { amin = fminf(amin, st[i].angle); amax = fmaxf(amax, st[i].angle); bmin = fminf(bmin, st[i].backTilt); bmax = fmaxf(bmax, st[i].backTilt); }
      }
      prevLight[i] = s.light;
      memcpy(prev[i], shown[i], sizeof prev[i]);
    }
  }
  if (mode == 0) { long big = 0, n = 0; for (int d = 1; d < 256; d++) { n += fHist[d]; if (d > 12) big += fHist[d]; }
    printf("frame to frame: %ld px changed, max %d/255, > 12/255: %ld, > 24/255:", n, fMax, big); long b24 = 0; for (int d = 25; d < 256; d++) b24 += fHist[d]; printf(" %ld\n", b24); }
  printf("light p2p %.4f/%.4f deg (raw), angle p2p %.4f deg, backTilt p2p %.5f rad | per frame: H px %.1f pairs %.1f lightCh %.3f dirty %.3f | M px %.1f pairs %.1f lightCh %.3f dirty %.3f\n",
         lmax[0] - lmin[0], lmax[1] - lmin[1], amax - amin, bmax - bmin,
         sumPx[0] / frameN, sumPairs[0] / frameN, (double)lightCh[0] / frameN, (double)dirtyFrames[0] / frameN,
         sumPx[1] / frameN, sumPairs[1] / frameN, (double)lightCh[1] / frameN, (double)dirtyFrames[1] / frameN);
  return 0;
}
