// perf-cheap A' evidence (host only): c++ -std=c++17 -O2 -ffp-contract=off -DBOARD_LCD316 <boardtag res flags 320w8-8>
//   -I <esp stubs> -I firmware/src -I spec palstep.cpp firmware/src/physics.cpp; run: palstep 0.125 < presets as
//   `N name` / `P k=v` / `R` blocks (DBG=1 lists the entries that moved more than 1 LSB).
// The colour bound of A' (render.cpp LIGHT_KEY_*): for every preset, each tube, every exact light L on a 1/64 deg grid over
// +-LIGHT_MAX_DEG, the palette renderTube would build at L (87f19af's colours) against the one at each key it can hold for L
// (a multiple of LIGHT_KEY_Q within LIGHT_KEY_HYST), both with L's highlight row: the largest per-channel RGB565 difference
// of every palette entry the render takes (rows, bubbleIn, tubeBackRows, bubbleRimRows, band rows).
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "render.cpp"
static uint16_t strip[PANEL_W * TUBE_HEIGHT_MAX];
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
static int d565(uint16_t a, uint16_t b, int ch) {
  const int s = ch == 0 ? 11 : ch == 1 ? 5 : 0, m = ch == 1 ? 63 : 31;
  return abs(((a >> s) & m) - ((b >> s) & m));
}
static Palette pa, pb; static PalCache ca, cb;
int main(int argc, char **argv) {
  const float D = atof(argv[1]);
  if (!render_init() || !physics_init()) return 3;
  Params design = PRESET_DEFAULT, p[2]; TubeState st[2]; uint32_t gen = 1;
  char line[512], name[256] = "?";
  int worstAll[3] = {0, 0, 0};
  while (fgets(line, sizeof line, stdin)) {
    line[strcspn(line, "\r\n")] = 0;
    if (line[0] == 'N') strcpy(name, line + 2);
    else if (line[0] == 'P') { char *eq = strchr(line + 2, '='); *eq = 0; setParam(design, line + 2, eq + 1); }
    else if (line[0] == 'R') {
      int worst[3] = {0, 0, 0}, worstHi[3] = {0, 0, 0}; long over = 0;
      for (int i = 0; i < 2; i++) {
        boardParams(design, p[i], TUBE_PX_SCALE(i), PX_SCALE_FIZZ); gen++;
        st[i] = TubeState(); st[i].trace = traceBuf(i); st[i].traceWet = traceWetBuf(i); st[i].fillTarget = 0.5f;
        renderTube(i, st[i], p[i], gen, strip);
        Tube &t = tubeAt(i); const int H = t.H;
        // perf-cheap A': every exact light L on a 1/64 deg grid, its highlight row from L (highlightTop), against every key
        // renderTube can hold for it (the multiples of LIGHT_KEY_Q within LIGHT_KEY_HYST of L): palette(L) vs palette(key)
        const int K = (int)(LIGHT_MAX_DEG * 64);
        for (int k = -K; k <= K; k++) {
          const float L = k / 64.0f; const int hi = t.highlightTop(p[i], L);
          ca = *t.palCache; ca.bandValid = false; t.buildPalette(p[i], L, hi, pa, ca);
          { const Palette keep = t.pal; t.pal = pa; t.buildBandRows(ca); t.pal = keep; }
          for (int j = (int)floorf((L - LIGHT_KEY_HYST) / D); j <= (int)ceilf((L + LIGHT_KEY_HYST) / D); j++) {
            const float key = j * D;
            if (fabsf(L - key) > LIGHT_KEY_HYST) continue;
            cb = *t.palCache; cb.bandValid = false; t.buildPalette(p[i], key, hi, pb, cb);
            { const Palette keep = t.pal; t.pal = pb; t.buildBandRows(cb); t.pal = keep; }
            for (int y = 0; y < H; y++) {
              const uint16_t A[7] = {pa.rows[y], pa.bubbleIn[y], pa.tubeBackRows[y], pa.bubbleRimRows[y], ca.bandInner[y], ca.bandLensMix[y], ca.bandRimC[y]};
              const uint16_t B[7] = {pb.rows[y], pb.bubbleIn[y], pb.tubeBackRows[y], pb.bubbleRimRows[y], cb.bandInner[y], cb.bandLensMix[y], cb.bandRimC[y]};
              for (int e = 0; e < 7; e++) for (int ch = 0; ch < 3; ch++) {
                const int d = d565(A[e], B[e], ch);
                if (d > worst[ch]) worst[ch] = d;
                if (d > 1) { over++; if (getenv("DBG")) printf("  tube %d light %g key %g row %d entry %d ch %d: %04x -> %04x\n", i, L, key, y, e, ch, A[e], B[e]); }
              }
            }
          }
        }
      }
      for (int ch = 0; ch < 3; ch++) if (worst[ch] > worstAll[ch]) worstAll[ch] = worst[ch];
      printf("%-48s worst R/G/B %d/%d/%d LSB565 (entries > 1: %ld)\n", name, worst[0], worst[1], worst[2], over); (void)worstHi;
      design = PRESET_DEFAULT;
    }
  }
  printf("ALL worst R/G/B %d/%d/%d LSB565, palette at the exact light vs at any key of step %g deg it can hold\n", worstAll[0], worstAll[1], worstAll[2], D);
  return 0;
}
