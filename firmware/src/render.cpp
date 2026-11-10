#include <climits>
#include <atomic>
#include <new>
#include "render.h"
#include "gen/sprites_gen.h"
#include "layout.h"
#include "tiles.h"
#ifdef DIGIT_PROF
#include "esp_timer.h"
#include "esp_cpu.h"
#endif
#ifdef DIGIT_VERIFY
#include "esp_cpu.h"
#endif
#ifdef TICK_PROF
#include "esp_cpu.h"
#endif
#ifdef FIZZ_PROF
#include "esp_cpu.h"
#define FZ_T0(v) const uint32_t v = esp_cpu_get_cycle_count()
#define FZ_ADD(a, i, v) ((a)[i] += esp_cpu_get_cycle_count() - (v))
#else
#define FZ_T0(v)
#define FZ_ADD(a, i, v) ((void)0)
#endif
#if defined(TUBE_PROF) || defined(TUBE_VERIFY) || defined(TILE_VERIFY)
#include "esp_cpu.h"
#endif
#if defined(FIZZ_PROF) && FIZZ_PROF >= 2
#define FZC(i) (d.prof[i]++)
#else
#define FZC(i) ((void)0)
#endif
#include <math.h>
#include <string.h>
#include <stdlib.h>
#include <esp_heap_caps.h>
#include <esp_random.h>
// The tick kernels in IRAM on the LCD (drawTicks): the 16 KB instruction cache is shared by both render cores. AMOLED
// and host builds: flash (the AMOLED has no internal RAM to spare).
#if defined(BOARD_LCD316) && defined(__XTENSA__)
#include "esp_attr.h"
#define TICK_IRAM IRAM_ATTR
#define FIZZ_IRAM IRAM_ATTR   // the fizz kernels likewise (step 5)
#ifndef TUBE_IRAM_OFF
#define TUBE_IRAM IRAM_ATTR   // drawTube's per-row kernels likewise (step 6)
#else
#define TUBE_IRAM
#endif
#else
#define TICK_IRAM
#define FIZZ_IRAM
#define TUBE_IRAM
#endif
// Sprite digit blends on the S3's SIMD (PIE) on the LCD build (see pieBlend); AMOLED and host builds: scalar.
#if defined(BOARD_LCD316) && defined(__XTENSA__)
#define DIGIT_PIE 1
#else
#define DIGIT_PIE 0
#endif

// ---------------------------------------------------------------------------------------------
// helpers — same maths as the sim (colours are float RGB triplets, quantised to 565 at the end)
// ---------------------------------------------------------------------------------------------
// The ESP32-S3 FPU has no min/max/floor/ceil (nor divide or sqrt) instructions: libm fminf/fmaxf/floorf/ceilf
// are out-of-line calls, a dozen per pixel in the edge loops. These inline forms return the same value for
// every non-NaN input (floor/ceil keep NaN; ffloor(-0) is +0, which no caller can tell apart).
static inline float fmn(float a, float b) { return b < a ? b : a; }
static inline float fmx(float a, float b) { return a < b ? b : a; }
static inline float ffloor(float x) {
  if (!(fabsf(x) < 8388608.0f)) return x;   // |x| >= 2^23 is already integral (or inf / NaN)
  const float t = (float)(int)x;
  return t > x ? t - 1 : t;
}
static inline float fceil(float x) {
  if (!(fabsf(x) < 8388608.0f)) return x;
  const float t = (float)(int)x;
  return t < x ? t + 1 : t;
}
struct RGB { float r, g, b; };
static inline float jround(float x) { return ffloor(x + 0.5f); }           // JS Math.round
static inline float clampf(float v, float lo, float hi) { return v < lo ? lo : v > hi ? hi : v; }
static inline RGB hexToRgb(uint32_t v) { return { (float)((v >> 16) & 0xff), (float)((v >> 8) & 0xff), (float)(v & 0xff) }; }
static inline RGB mix(RGB a, RGB b, float t) { return { a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t }; }
static inline RGB scale(RGB a, float k) { return { a.r * k, a.g * k, a.b * k }; }
static inline uint16_t rgb565(int r, int g, int b) { return (uint16_t)(((r & 0xf8) << 8) | ((g & 0xfc) << 3) | (b >> 3)); }
// (int)jround(v) of a clamped channel: v + 0.5 lies in [0.5, 255.5] (or is NaN, both trunc it), where floor is trunc.
static inline uint16_t q(RGB c) {
  return rgb565((int)(clampf(c.r, 0, 255) + 0.5f), (int)(clampf(c.g, 0, 255) + 0.5f), (int)(clampf(c.b, 0, 255) + 0.5f));
}
static inline RGB to888(uint16_t c) {
  int r5 = (c >> 11) & 0x1f, g6 = (c >> 5) & 0x3f, b5 = c & 0x1f;
  return { (float)((r5 << 3) | (r5 >> 2)), (float)((g6 << 2) | (g6 >> 4)), (float)((b5 << 3) | (b5 >> 2)) };
}
// Integer lerp between two 565 colours. t is quantised to 1/256; rounding matches the sim's
// jround(a + (b-a)*t), expanding channels to RGB888 and using +128 for round-half-up.
static inline void expand565(uint16_t c, int &r, int &g, int &b) {
  int r5 = (c >> 11) & 0x1f, g6 = (c >> 5) & 0x3f, b5 = c & 0x1f;
  r = (r5 << 3) | (r5 >> 2); g = (g6 << 2) | (g6 >> 4); b = (b5 << 3) | (b5 >> 2);
}
// Same exact RGB888 interpolation, with red and blue in separate 16-bit lanes.
static inline uint16_t blend565T(uint16_t a, uint16_t b, int T) {
  if (T <= 0) return a;
  if (T >= 256) return b;
  const uint32_t a5 = ((a >> 8) & 0xf8u) | ((uint32_t)(a & 31) << 19);
  const uint32_t b5 = ((b >> 8) & 0xf8u) | ((uint32_t)(b & 31) << 19);
  const uint32_t arb = a5 | ((a5 >> 5) & 0x00070007u), brb = b5 | ((b5 >> 5) & 0x00070007u);
  const uint32_t ag6 = (a >> 5) & 63, bg6 = (b >> 5) & 63;
  const uint32_t ag = (ag6 << 2) | (ag6 >> 4), bg = (bg6 << 2) | (bg6 >> 4);
  // A lane never exceeds 255*256+128. Unsigned wrap preserves packed-lane borrows.
  const uint32_t rb = (arb << 8) + (brb - arb) * (uint32_t)T + 0x00800080u;
  const uint32_t g = (ag << 8) + (bg - ag) * (uint32_t)T + 128;
  return (uint16_t)((rb & 0xf800u) | ((g >> 5) & 0x07e0u) | (rb >> 27));
}
static inline uint16_t blend565(uint16_t a, uint16_t b, float t) {
  return blend565T(a, b, (int)(t * 256 + 0.5f));
}
// The residue of one strip row (drawTube step 3d). Depth: a coat of film path coefficient A = eta (2 - eta) 2^16
// (per column) crossed by this row's rays (path weight K = 256 / (1 - u^2), capped) takes the annular path
// fraction f = FILM_PHI[(A K + 2^15) >> 16] of the chord, times traceAmount (G, 1/256): T = min(256, f G / 256),
// the same integers as the sim. Colour: a dried dye stain is a Beer-Lambert tint of the tube back B toward the
// body row C, B^(1-T/256) C^(T/256) per channel in linear light, from the two rows' logs (FILM_LG); same index math
// as the sim's filmMix: lgB + ((dl T + 128) >> 8) == (lgB (256 - T) + lgC T + 128) >> 8. T >= 256 = the body row.
struct ResidueTint {
  int lgB0, lgB1, lgB2, dl0, dl1, dl2;   // log of B, log C - log B per channel (Q8)
  const uint8_t *ex;                     // FILM_EX
  const uint16_t *phi;                   // FILM_PHI
  uint32_t K; int G;                     // row path weight (1/256, capped at 2^18), traceAmount (1/256)
  float kq;                              // K / 2^16, for interpolated A
  uint16_t full;                         // C (rgb565)
  uint16_t at(int T) const {             // 0 < T
    if (T >= 256) return full;
    return rgb565(ex[lgB0 + ((dl0 * T + 128) >> 8)], ex[lgB1 + ((dl1 * T + 128) >> 8)], ex[lgB2 + ((dl2 * T + 128) >> 8)]);
  }
  int depthT(uint32_t A) const {         // stain depth 1/256 of a column's coat (sim: Math.floor(depth(A) + 0.5))
    const uint32_t i = (A * K + 32768u) >> 16;
    const int T = ((i >= 256 ? 256 : phi[i]) * G + 128) >> 8;
    return T < 256 ? T : 256;
  }
  float depthF(float A) const {          // the same for A interpolated between columns, unrounded (sim depth)
    const float i = A * kq;
    return fmn(256, (i >= 255.5f ? 256 : phi[(int)(i + 0.5f)]) * G * (1.0f / 256));
  }
};
// Dried-trace fill of one strip row over [x0, x1) and [x2, x3) over the tube back (the only layer under it),
// written in the strip's byte-swapped layout. aLo / aHi = the smallest non-zero / largest traceA of the span, so
// every depth lies in [depthT(aLo), depthT(aHi)] (monotone in A): when the spans are long against that band, the
// row's colours come from a LUT built once for both spans (any width: TRACE_LUT covers every T), otherwise per
// pixel. (Step 6: the LUT used to stop at 48 depths, so the grazing rows, whose path weight spreads the depths
// over ~100 steps, took the per-pixel colour: 4 ms of the minutes core.)
// noinline: inside drawTube the loop shared a register file with hundreds of locals and spilled every
// iteration; on its own it stays in registers.
#define TRACE_LUT 257   // T 0..256; PSRAM, one per tube (render_init)
#define TRACE_BLK 16    // columns per traceFillLutI skip block (TraceMemo::blkMax)
#ifndef TUBE_BAND
#if TILE_RENDER
#define TUBE_BAND TILE_ROWS   // a band is a tile (tiles.h): internal RAM, copied out when done
#else
#define TUBE_BAND 8   // drawTube's row band: strip rows the base stages run over together (cache-resident)
#endif
#endif
#if TILE_RENDER && TUBE_BAND != TILE_ROWS
#error "tiled render: the band is the tile"
#endif
#if TILE_RENDER && !(defined(BOARD_LCD316) && defined(__XTENSA__))
// Host sink (check_render_frames.py --tiles): memcpy, so the tiled band loop is proven pixel for pixel off the board.
static uint16_t hostTile[2][2][TILE_ROWS * PANEL_W];
bool tiles_init() { return true; }
uint16_t *tile_slot(int idx, int slot) { return hostTile[idx & 1][slot & 1]; }
void tile_begin(int, uint16_t *, int) {}
void tile_put(int idx, int slot, uint16_t *dst, int rows) { memcpy(dst, hostTile[idx & 1][slot & 1], (size_t)rows * PANEL_W * 2); }
void tile_end(int) {}
const uint32_t *tile_prof(int) { static const uint32_t z[5] = {}; return z; }
#endif
#if TILE_RENDER
// The change record of one finished tile (tiles.h TileDirty): per column pair p the hash of its `rows` words (the tile's
// strip rows; a word = columns 2p, 2p + 1) against hash[p], the tube's last hashed render of this tile; a pair that
// differs takes the new hash and sets bit p % 32 of bits[p / 32]. Per word but the last h = F(h ^ w), F(x) = x K1, x ^= x
// >> 16, x K2; the last word only h ^= w (F is a bijection: it would collide the same). A bijection per word, so one
// changed word always changes the hash; F mixes every bit into every other (the push's chain, x K, x ^= x >> 15, keeps a
// high-bit change in a few high bits: host scenes 2026-11-05, 4.6 M changed 4-word units, its low 20 bits collided
// 14,286 times and the whole hash once (2 words, 1-3 bits each), F's 1 and 0 times; 4.4 expected of an ideal 20 bits).
// A collision left is repaired by the push's rolling refresh. Two pairs at a time: independent chains overlap the
// multiplies' latency. Reads the slot while its copy runs.
static_assert(TILE_ROWS == 4 && TILE_PAIRS % 2 == 0, "tileHashes: 4-row tiles, pairs two at a time");
static void __attribute__((noinline)) tileHashes(const uint32_t *tile, int rows, uint32_t *hash, uint32_t *bits) {
  constexpr int P = TILE_PAIRS; constexpr uint32_t K1 = 0x9E3779B1u, K2 = 0x85EBCA6Bu, H0 = 0x811C9DC5u;
#define TH_ROUND(h, w) do { h = ((h) ^ (w)) * K1; h ^= h >> 16; h *= K2; } while (0)
  for (int j = 0; j < TILE_PAIR_WORDS; j++) {
    const int p0 = 32 * j, p1 = p0 + 32 < P ? p0 + 32 : P;
    uint32_t m = 0;
    if (rows == TILE_ROWS) {   // one pointer a row (1,640 B apart: past l32i's offsets), the pair's bit kept shifted
      const uint32_t *w0 = tile + p0, *w1 = w0 + P, *w2 = w1 + P, *w3 = w2 + P;
      uint32_t *hp = hash + p0, bit = 1;
      for (int n = (p1 - p0) >> 1; n > 0; n--, w0 += 2, w1 += 2, w2 += 2, w3 += 2, hp += 2, bit <<= 2) {
        uint32_t a = H0, b = H0;
        TH_ROUND(a, w0[0]); TH_ROUND(b, w0[1]);
        TH_ROUND(a, w1[0]); TH_ROUND(b, w1[1]);
        TH_ROUND(a, w2[0]); TH_ROUND(b, w2[1]);
        a ^= w3[0]; b ^= w3[1];
        if (a != hp[0]) { hp[0] = a; m |= bit; }
        if (b != hp[1]) { hp[1] = b; m |= bit << 1; }
      }
    }
    else for (int p = p0; p < p1; p++) {   // the tube's last tile, short of TILE_ROWS
      uint32_t h = H0;
      for (int r = 0; r + 1 < rows; r++) TH_ROUND(h, tile[r * P + p]);
      h ^= tile[(rows - 1) * P + p];
      if (h != hash[p]) { hash[p] = h; m |= 1u << (p - p0); }
    }
    bits[j] = m;
  }
#undef TH_ROUND
}
#endif
// -DTILE_CLIP_CHECK (tiled builds, board and host): every strip write of drawTube (and the reads around it) is checked
// against the memory the render may touch now: the band's tile slot during a tile, the strip after the band loop. A
// write outside would land in other internal RAM (the stages' row tests still see the whole strip): stop at once.
// Per core: both tubes render at once (debug only, so file-static is fine here).
#if TILE_RENDER && defined(TILE_CLIP_CHECK)
#ifdef __XTENSA__
#include "esp_cpu.h"
#include "esp_system.h"
static inline int clipCore() { return esp_cpu_get_core_id() & 1; }
static void __attribute__((noinline)) tileClipFail(const void *, int) { esp_system_abort("TILE_CLIP_CHECK: a strip write outside the tile slot"); }
#else
#include <cstdio>
static inline int clipCore() { return 0; }
static void __attribute__((noinline)) tileClipFail(const void *p, int n) { std::fprintf(stderr, "TILE_CLIP_CHECK: %d px at %p outside the tile slot\n", n, p); abort(); }
#endif
static const uint16_t *tileClipLo[2], *tileClipHi[2];
#define TCLIP(p, n) do { const uint16_t *p_ = (const uint16_t *)(p); const int c_ = clipCore(); \
                         if (p_ < tileClipLo[c_] || p_ + (n) > tileClipHi[c_]) tileClipFail(p_, (n)); } while (0)
#define TCLIP_SET(lo, hi) do { const int c_ = clipCore(); tileClipLo[c_] = (lo); tileClipHi[c_] = (hi); } while (0)
#else
#define TCLIP(p, n) ((void)0)
#define TCLIP_SET(lo, hi) ((void)0)
#endif
TUBE_IRAM static void __attribute__((noinline)) traceFillLut(uint16_t *row, const uint16_t *traceA, int x0, int x1, const ResidueTint &t,
                                                    int Tlo, const uint16_t *lut) {
  for (int x = x0; x < x1; x++) {
    if (!traceA[x]) continue;
    const int T = t.depthT(traceA[x]);
    if (T) row[x] = lut[T - Tlo];
  }
}
// The same fill with the colour indexed by i = (A K + 2^15) >> 16 (depthT's phi index, clamped at 256) instead of T:
// lutI[i - iZ] = the colour of T(i) for i in [iZ, i1]; T(i) is non-decreasing in i (FILM_PHI is), so T > 0 exactly
// from iZ on. Saves depthT's phi load and gain multiply per pixel (step 6). With no wrap of A K over the span and
// iZ >= 1, "A != 0 and i >= iZ" is exactly A >= aMin = ceil((iZ 2^16 - 2^15) / K): a column below costs one compare,
// and a TRACE_BLK block whose largest coat (blkMax, traceBlur) is below aMin one compare in all (the thin coat between
// the deposits, ~half the minutes tube's residue columns while it swings).
TUBE_IRAM static void __attribute__((noinline)) traceFillLutI(uint16_t *row, const uint16_t *traceA, int x0, int x1, uint32_t K, int iZ,
                                                     uint32_t aMin, const uint16_t *blkMax, const uint16_t *lutI) {
  for (int x = x0; x < x1;) {
    const int b = (unsigned)x / TRACE_BLK, e = (b + 1) * TRACE_BLK, xe = e < x1 ? e : x1;
    if (blkMax[b] < aMin) { x = xe; continue; }
    for (; x < xe; x++) {
      const uint32_t A = traceA[x];
      if (A < aMin) continue;
      uint32_t i = (A * K + 32768u) >> 16; if (i > 256) i = 256;
      row[x] = lutI[i - iZ];
    }
  }
}
// iZ0: the first phi index of a visible depth (T > 0) at this traceAmount (drawTube, per frame); blkMax: TraceMemo's.
TUBE_IRAM static void __attribute__((noinline)) traceFillRow(uint16_t *row, const uint16_t *traceA, int x0, int x1, int x2, int x3,
                                                    const ResidueTint &tint, int aLo, int aHi, int iZ0, const uint16_t *blkMax,
                                                    uint16_t *lut) {   // lut: 2 x TRACE_LUT entries, the tube's own
  const ResidueTint t = tint;
  const int Tlo = t.depthT((uint32_t)aLo), Thi = t.depthT((uint32_t)aHi);
  const int n = (x1 > x0 ? x1 - x0 : 0) + (x3 > x2 ? x3 - x2 : 0);
  // i of the span's extremes; no 32-bit wrap of A K there (then i is monotone in A over the span)
  const uint64_t qLo = (uint64_t)(uint32_t)aLo * t.K + 32768u, qHi = (uint64_t)(uint32_t)aHi * t.K + 32768u;
  if (aHi >= aLo && qHi < (1ull << 32) && n > 0) {
    const int iLo = (int)(qLo >> 16) > 256 ? 256 : (int)(qLo >> 16), i1 = (int)(qHi >> 16) > 256 ? 256 : (int)(qHi >> 16);
    auto Ti = [&](int i) { const int T = ((i >= 256 ? 256 : t.phi[i]) * t.G + 128) >> 8; return T < 256 ? T : 256; };   // depthT from i
    // the first i >= iLo of T > 0 (T(i) non-decreasing, 0 exactly below iZ0)
    const int iZ = iLo > iZ0 ? iLo : iZ0;
    if (iZ > i1) return;   // every pixel of the spans takes T 0: nothing to write (the paths below write nothing either)
    if (n > (i1 - iZ + 1) + (Thi - Tlo + 1)) {
      uint16_t *const lutI = lut + TRACE_LUT;
      // T(i) runs through [T(iZ), Thi] non-decreasing: one colour per depth reached, as lut[T - Tlo] held it
      uint16_t c = 0;
      for (int i = iZ, Tp = -1; i <= i1; i++) { const int T = Ti(i); if (T != Tp) { Tp = T; c = __builtin_bswap16(t.at(T)); } lutI[i - iZ] = c; }
      const uint32_t aMin = ((uint32_t)iZ * 65536u - 32768u + t.K - 1) / t.K;
      traceFillLutI(row, traceA, x0, x1, t.K, iZ, aMin, blkMax, lutI);
      traceFillLutI(row, traceA, x2, x3, t.K, iZ, aMin, blkMax, lutI);
      return;
    }
  }
  if (n > Thi - Tlo + 1) {
    for (int T = Tlo; T <= Thi; T++) lut[T - Tlo] = T ? __builtin_bswap16(t.at(T)) : 0;
    traceFillLut(row, traceA, x0, x1, t, Tlo, lut);
    traceFillLut(row, traceA, x2, x3, t, Tlo, lut);
    return;
  }
  for (int k = 0; k < 2; k++) for (int x = k ? x2 : x0, xe = k ? x3 : x1; x < xe; x++) {
    if (!traceA[x]) continue;
    const int T = t.depthT(traceA[x]);
    if (T) row[x] = __builtin_bswap16(t.at(T));
  }
}
static inline int alphaT(float t) { return (int)(t * 256 + 0.5f); }
// Sheared dry residue of one strip row over [x0, x1) (drawTube step 3d): the imminent smear past an edge's
// wet reach, sampled sh * w back (w = 1 - smoothstep(out * invZ), out = px outward of the edge at e),
// linear between columns, tinted as the general zone loop does these pixels, where the midpoint share is
// 0 / 1 and the film weight is 0. noinline for the same reason as traceFillRow.
TUBE_IRAM static void __attribute__((noinline)) traceShearRow(uint16_t *row, const uint16_t *traceA, int a0, int a1, int x0, int x1,
                                                     const ResidueTint &tint, float e, bool home, float sh, float invZ) {
  for (int x = x0; x < x1; x++) {
    const float o = home ? e - x - 0.5f : x + 0.5f - e;
    const float s = clampf(o * invZ, 0, 1), xf = x - sh * (1 - s * s * (3 - 2 * s));
    const int i0 = (int)ffloor(xf);
    const float ft = xf - i0;
    const float r0 = i0 >= a0 && i0 < a1 ? (float)traceA[i0] : 0.0f, r1 = i0 + 1 >= a0 && i0 + 1 < a1 ? (float)traceA[i0 + 1] : 0.0f;
    const int T = r0 + r1 > 0 ? (int)(tint.depthF(r0 + (r1 - r0) * ft) + 0.5f) : 0;
    if (T > 0) row[x] = __builtin_bswap16(tint.at(T));
  }
}
// Per-row edge loops of drawTube, noinline for the same reason as traceFillRow (register pressure in the
// giant function). `row` is the strip row (byte-swapped 565); each is the exact loop it replaced.
static inline void rowPxa(uint16_t *row, int x, uint16_t c, float t) {   // Tube::pxa on a strip row
  row[x] = __builtin_bswap16(t >= 1 ? c : blend565(__builtin_bswap16(row[x]), c, t));
}
#ifdef TUBE_VERIFY
// The step-5 ramps, verbatim (TUBE_VERIFY: the SIMD path is compared against them).
// Step 3 soft-edge AA ramp plus folded glow, time edge: rightwards from a0 until the alpha reaches 0.
static void __attribute__((noinline)) rampRowRScalar(uint16_t *row, int a0, int aEnd, float ex, float hw, float invW, float invGlow,
                                               bool glow, float glowStrength, float lightK, int x0, int solidLo, int solidHi,
                                               bool trace, uint16_t back, uint16_t fg) {
  for (int x = a0; x <= aEnd; x++) {
    float t = glow ? fmx(0, 1 - (x + 0.5f - ex) * invGlow) : 0;
    float a = fmn(1, clampf((ex + hw - x - 0.5f) * invW, 0, 1) + t * t * glowStrength * lightK);
    if (a <= 0) break;
    if (a >= 1 && x >= solidLo && x < solidHi) continue;   // the span already drew it full
    if (x >= x0 && x < PANEL_W) {
      if (trace) rowPxa(row, x, fg, a);
      else row[x] = __builtin_bswap16(blend565(back, fg, a));
    }
  }
}
// Same, home edge: leftwards from xStart; only [x0, xi) is drawn.
static void __attribute__((noinline)) rampRowLScalar(uint16_t *row, int xStart, int bEnd, float exL, float hw, float invW, float invGlow,
                                               bool glow, float glowStrength, float lightKL, int x0, int xi, int solidLo, int solidHi,
                                               bool trace, uint16_t back, uint16_t fg) {
  if (bEnd < x0) bEnd = x0;   // walking left: every x < x0 is skipped anyway
  for (int x = xStart; x >= bEnd; x--) {
    float t = glow ? fmx(0, 1 - (exL - (x + 0.5f)) * invGlow) : 0;
    float a = fmn(1, clampf((x + 0.5f - exL + hw) * invW, 0, 1) + t * t * glowStrength * lightKL);
    if (a <= 0) break;
    if (x < x0 || x >= xi || x >= PANEL_W) continue;
    if (a >= 1 && x >= solidLo && x < solidHi) continue;
    if (trace) rowPxa(row, x, fg, a);
    else row[x] = __builtin_bswap16(blend565(back, fg, a));
  }
}
#endif
#if DIGIT_PIE
static bool rampPieR(uint16_t *row, int a0, int aEnd, float ex, float hw, float invW, float invGlow, bool glow, float glowStrength,
                     float lightK, int x0, int solidLo, int solidHi, uint16_t fg, const uint16_t *lo, const uint16_t *hi);
static bool rampPieL(uint16_t *row, int xStart, int bEnd, float exL, float hw, float invW, float invGlow, bool glow, float glowStrength,
                     float lightKL, int x0, int xi, int solidLo, int solidHi, uint16_t fg, const uint16_t *lo, const uint16_t *hi);
#endif
// Step 3 soft-edge AA ramp plus folded glow, time edge: rightwards from a0 until the alpha reaches 0. lo / hi: the strip
// (the LCD's SIMD path, rampPieR, blends whole blocks inside it).
TUBE_IRAM static void __attribute__((noinline)) rampRowR(uint16_t *row, int a0, int aEnd, float ex, float hw, float invW, float invGlow,
                                               bool glow, float glowStrength, float lightK, int x0, int solidLo, int solidHi,
                                               bool trace, uint16_t back, uint16_t fg, const uint16_t *lo, const uint16_t *hi) {
#if DIGIT_PIE
  if (trace && rampPieR(row, a0, aEnd, ex, hw, invW, invGlow, glow, glowStrength, lightK, x0, solidLo, solidHi, fg, lo, hi)) return;
#else
  (void)lo; (void)hi;
#endif
  for (int x = a0; x <= aEnd; x++) {
    float t = glow ? fmx(0, 1 - (x + 0.5f - ex) * invGlow) : 0;
    float a = fmn(1, clampf((ex + hw - x - 0.5f) * invW, 0, 1) + t * t * glowStrength * lightK);
    if (a <= 0) break;
    // trace: blended over the pixel, T 0 leaves it as it is, and the alpha never rises along the walk (cov and the
    // glow fall monotonically with x, also as rounded): stop at the first T 0 (step 6). Not without trace: the
    // pixel is set from `back` there.
    if (trace && a < 1 && (int)(a * 256 + 0.5f) <= 0) break;
    if (a >= 1 && x >= solidLo && x < solidHi) continue;   // the span already drew it full
    if (x >= x0 && x < PANEL_W) {
      if (trace) rowPxa(row, x, fg, a);
      else row[x] = __builtin_bswap16(blend565(back, fg, a));
    }
  }
}
// Same, home edge: leftwards from xStart; only [x0, xi) is drawn.
TUBE_IRAM static void __attribute__((noinline)) rampRowL(uint16_t *row, int xStart, int bEnd, float exL, float hw, float invW, float invGlow,
                                               bool glow, float glowStrength, float lightKL, int x0, int xi, int solidLo, int solidHi,
                                               bool trace, uint16_t back, uint16_t fg, const uint16_t *lo, const uint16_t *hi) {
#if DIGIT_PIE
  if (trace && rampPieL(row, xStart, bEnd, exL, hw, invW, invGlow, glow, glowStrength, lightKL, x0, xi, solidLo, solidHi, fg, lo, hi)) return;
#else
  (void)lo; (void)hi;
#endif
  if (bEnd < x0) bEnd = x0;   // walking left: every x < x0 is skipped anyway
  for (int x = xStart; x >= bEnd; x--) {
    float t = glow ? fmx(0, 1 - (exL - (x + 0.5f)) * invGlow) : 0;
    float a = fmn(1, clampf((x + 0.5f - exL + hw) * invW, 0, 1) + t * t * glowStrength * lightKL);
    if (a <= 0) break;
    if (trace && a < 1 && (int)(a * 256 + 0.5f) <= 0) break;   // as in rampRowR (alpha falls leftwards)
    if (x < x0 || x >= xi || x >= PANEL_W) continue;
    if (a >= 1 && x >= solidLo && x < solidHi) continue;
    if (trace) rowPxa(row, x, fg, a);
    else row[x] = __builtin_bswap16(blend565(back, fg, a));
  }
}
// sqrtf is two out-of-line calls here (see sqrtExact). Reciprocal-sqrt seed + 3 Newton steps: relative error <= 2.1e-7
// against sqrtf for 1e-30 <= x < 1200 (below that it returns < 1e-10); as an 8-bit coverage it moved 1 step in
// 2.5e-7 of the samples. Not for values that must match the sim bit for bit.
// The bits move with __builtin_bit_cast: the build has -fno-builtin-memcpy, so a memcpy here was two out-of-line calls
// (and window spills) per root — most of the fizz kernel's time (step 5, 2026-10-29).
static inline float rsqrtApprox(float x) {   // 1/sqrt(x), same seed and Newton steps as sqrtApprox
  float y = __builtin_bit_cast(float, 0x5f3759dfu - (__builtin_bit_cast(uint32_t, x) >> 1));
  const float hx = 0.5f * x;
  y = y * (1.5f - hx * y * y); y = y * (1.5f - hx * y * y); y = y * (1.5f - hx * y * y);
  return y;
}
static inline float sqrtApprox(float x) {
  float y = __builtin_bit_cast(float, 0x5f3759dfu - (__builtin_bit_cast(uint32_t, x) >> 1));
  const float hx = 0.5f * x;
  y = y * (1.5f - hx * y * y); y = y * (1.5f - hx * y * y); y = y * (1.5f - hx * y * y);
  return x * y;
}
// sqrtf for x >= 0, bit for bit: on the S3 newlib's sqrtf is a wrapper (NaN / negative checks, errno) around
// __ieee754_sqrtf, the FPU's correctly rounded sqrt0.s / maddn.s / divn.s sequence; that sequence inline, no calls (two
// windowed calls a root: the fizz physics takes one per disc row in discFit). Host builds: sqrtf.
static inline float sqrtExact(float x) {
#ifdef __XTENSA__
  float f0, f1 = x, f2, f3, f4, f5, f6, f7;
  __asm__("sqrt0.s %[f2], %[f1]\n\tconst.s %[f3], 0\n\tmaddn.s %[f3], %[f2], %[f2]\n\tnexp01.s %[f4], %[f1]\n\t"
          "const.s %[f0], 3\n\taddexp.s %[f4], %[f0]\n\tmaddn.s %[f0], %[f3], %[f4]\n\tnexp01.s %[f3], %[f1]\n\t"
          "neg.s %[f5], %[f3]\n\tmaddn.s %[f2], %[f0], %[f2]\n\tconst.s %[f0], 0\n\tconst.s %[f6], 0\n\t"
          "const.s %[f7], 0\n\tmaddn.s %[f0], %[f5], %[f2]\n\tmaddn.s %[f6], %[f2], %[f4]\n\tconst.s %[f4], 3\n\t"
          "maddn.s %[f7], %[f4], %[f2]\n\tmaddn.s %[f3], %[f0], %[f0]\n\tmaddn.s %[f4], %[f6], %[f2]\n\tneg.s %[f2], %[f7]\n\t"
          "maddn.s %[f0], %[f3], %[f2]\n\tmaddn.s %[f7], %[f4], %[f7]\n\tmksadj.s %[f2], %[f1]\n\tnexp01.s %[f1], %[f1]\n\t"
          "maddn.s %[f1], %[f0], %[f0]\n\tneg.s %[f3], %[f7]\n\taddexpm.s %[f0], %[f2]\n\taddexp.s %[f3], %[f2]\n\t"
          "divn.s %[f0], %[f1], %[f3]"
          : [f0] "=&f"(f0), [f1] "+f"(f1), [f2] "=&f"(f2), [f3] "=&f"(f3), [f4] "=&f"(f4), [f5] "=&f"(f5), [f6] "=&f"(f6), [f7] "=&f"(f7));
  return f0;
#else
  return sqrtf(x);
#endif
}
// Step 5 fizz: one row of an AA bubble disc (see drawTube). Coverage and core are decided from squared distances
// with a 1e-4 relative margin that float rounding cannot cross; a root is taken only in the anti-aliased ring
// (approximate, see sqrtApprox) and in the core's margin (exact).
struct DiscRow {
  float fx, dy, r, in2, out2, offX, offY, kc, core2Lo, core2Hi, wallT;
  float sR, sL, bR, bL, veilA, pullR, pullL;   // surface fronts, band widths, FOAM_VEIL x stroke opacity, pulls
  int veilLo, veilHi;                           // first ix the time-edge band can veil / last ix + 1 the home-edge band can (INT_MAX / INT_MIN when no band)
  float blickK, bX, bY, rbOut, bIn2, bOut2;    // pinpoint: fizzBlick, centre offset, rb + 0.5, (rb - 0.5)^2 and (rb + 0.5)^2 with margins
  float tintA;                                  // bubbleDark x depthK: opacity of the dark tint over the see-through interior
  bool core, mirror, blick; int xsI, L; uint16_t cRim, cBlick;
#ifdef FIZZ_PROF
  uint32_t *prof;                               // the tube's fizzProf (FZC: FIZZ_PROF=2 pixel classes)
#endif
};
#define FIZZ_SIZES 12   // size classes, depth levels: see fizzV / fizzZ
#define FIZZ_DEPTHS 4
#define FIZZ_MQ 4       // the masks' |dx| steps a px (4: maskRows shifts by 2), |dy| steps a px: see FizzClass
#define FIZZ_MDY 8
// Veil of one disc pixel by the pixel's footprint over each surface band [profile, profile +- width]: continuous
// as the edge moves. Out of the pixel loop (noinline) so its nine floats are not live there; a division per
// veiled pixel only (bubbles touching a band). Multiplies cov in the sim's order, so the result is bit-identical.
static float __attribute__((noinline)) discVeil(int ix, const DiscRow &d, float cov) {   // returns the veiled cov, sim order
  if (ix + 1 > d.sR && d.bR > 0) { const float a1 = fmn(ix + 1, d.sR + d.bR), a0 = fmx(ix, d.sR);
    if (a1 > a0) { const float q = ((a0 + a1) / 2 - d.sR) / d.bR; cov *= 1 - d.veilA * (a1 - a0) * (1 - q) * (1 - d.pullR * q); } }
  if (ix < d.sL && d.bL > 0) { const float a1 = fmn(ix + 1, d.sL), a0 = fmx(ix, d.sL - d.bL);
    if (a1 > a0) { const float q = (d.sL - (a0 + a1) / 2) / d.bL; cov *= 1 - d.veilA * (a1 - a0) * (1 - q) * (1 - d.pullL * q); } }
  return cov;
}
// blend565T(a, b, T) with b's lanes expanded once (a disc row blends every ring pixel toward the same rim colour).
struct RimLanes { uint32_t rb, g; uint16_t c; };
static inline RimLanes rimLanes(uint16_t b) {
  const uint32_t b5 = ((b >> 8) & 0xf8u) | ((uint32_t)(b & 31) << 19), bg6 = (b >> 5) & 63;
  return { b5 | ((b5 >> 5) & 0x00070007u), (bg6 << 2) | (bg6 >> 4), b };
}
static inline uint16_t blend565L(uint16_t a, const RimLanes &B, int T) {   // == blend565T(a, B.c, T), same integers
  if (T <= 0) return a;
  if (T >= 256) return B.c;
  const uint32_t a5 = ((a >> 8) & 0xf8u) | ((uint32_t)(a & 31) << 19);
  const uint32_t arb = a5 | ((a5 >> 5) & 0x00070007u);
  const uint32_t ag6 = (a >> 5) & 63, ag = (ag6 << 2) | (ag6 >> 4);
  const uint32_t rb = (arb << 8) + (B.rb - arb) * (uint32_t)T + 0x00800080u;
  const uint32_t g = (ag << 8) + (B.g - ag) * (uint32_t)T + 128;
  return (uint16_t)((rb & 0xf800u) | ((g >> 5) & 0x07e0u) | (rb >> 27));
}
// Two instantiations: BLICK false is the plain disc (small bubbles, fizzBlick 0, and every row the pinpoint cannot
// reach) and carries none of the pinpoint state in its pixel loop.
// Profile (2026-10-29, LCD wide, user preset, -DFIZZ_PROF): ~10 px visited a row, half of them outside the disc;
// ~100 cycles a pixel of tests and spills, ~90 a ring root, ~130 a blend. So a row visits only what it can draw:
// the chord (|dx| beyond its half-width plus a margin far above float rounding has d2 >= out2), clipped to the panel,
// minus the certainly-core pixels that write nothing (no tint, out of the pinpoint's reach), each pixel then taking
// the exact tests it took before. Output-neutral: every pixel left out reached `continue` without a write.
template <bool BLICK>
static void __attribute__((noinline)) discRowT(uint16_t *row, int ixa, int ixb, const DiscRow &d) {
  const float fx = d.fx, dy = d.dy, dy2 = dy * dy, r = d.r, in2 = d.in2, out2 = d.out2, offX = d.offX, offY = d.offY, wallT = d.wallT;
  if (dy2 >= out2) return;   // every d2 = dx² + dy2 >= dy2 >= out2: nothing on this row
  const float bdy = BLICK ? dy - d.bY : 0, bRem = BLICK ? d.bOut2 - bdy * bdy : 0;   // pinpoint reach left for dx² on this row
  if (BLICK && !(bRem > 0)) { discRowT<false>(row, ixa, ixb, d); return; }   // out of the pinpoint's reach: the plain disc
  { const float w = sqrtApprox(out2 - dy2) + 0.01f;   // the chord's half-width, plus margin
    const int lo = (int)fceil(fx - 0.5f - w), hi = (int)ffloor(fx - 0.5f + w);
    if (lo > ixa) ixa = lo; if (hi < ixb) ixb = hi; }
  const int x0 = d.mirror ? d.L - 1 - d.xsI : d.xsI, step = d.mirror ? -1 : 1;   // panel x = x0 + step * ix
  { const int lo = d.mirror ? x0 - (PANEL_W - 1) : -x0, hi = d.mirror ? x0 : PANEL_W - 1 - x0;
    if (lo > ixa) ixa = lo; if (hi < ixb) ixb = hi; }
  if (ixa > ixb) return;
  // Certainly inside the core (dc2 < core2Lo with margin) and writing nothing (no tint; minus the pinpoint's reach on
  // its rows): up to two spans jumped over.
  int cut[4], nc = 0;
  if (d.core && d.tintA <= 0) {
    const float cy = dy - offY, rem = d.core2Lo * (1 - 1e-4f) - cy * cy;
    if (rem > 0) { const float hw = sqrtApprox(rem) - 0.01f; if (hw > 0) {
      const int a = (int)fceil(fx + offX - hw - 0.5f), b = (int)ffloor(fx + offX + hw - 0.5f);
      if (BLICK) {
        const float bw = sqrtApprox(bRem) + 0.01f;
        const int pa = (int)ffloor(fx + d.bX - bw - 0.5f), pb = (int)fceil(fx + d.bX + bw - 0.5f);
        const int b0 = b < pa - 1 ? b : pa - 1, a1 = a > pb + 1 ? a : pb + 1;
        if (a <= b0) { cut[nc++] = a; cut[nc++] = b0; }
        if (a1 <= b) { cut[nc++] = a1; cut[nc++] = b; }
      } else if (a <= b) { cut[nc++] = a; cut[nc++] = b; }
    } }
  }
  int spanA[3], spanB[3], ns = 0;
  { int a = ixa;
    for (int i = 0; i < nc; i += 2) {
      const int e = cut[i] - 1 < ixb ? cut[i] - 1 : ixb;
      if (a <= e) { spanA[ns] = a; spanB[ns++] = e; }
      if (cut[i + 1] + 1 > a) a = cut[i + 1] + 1;
#if defined(FIZZ_PROF) && FIZZ_PROF >= 2
      { const int sa = cut[i] > ixa ? cut[i] : ixa, sb = cut[i + 1] < ixb ? cut[i + 1] : ixb; if (sb >= sa) d.prof[FZ_PX_SKIP] += sb - sa + 1; }
#endif
    }
    if (a <= ixb) { spanA[ns] = a; spanB[ns++] = ixb; } }
  const int veilLo = d.veilLo, veilHi = d.veilHi;
  const RimLanes rim = rimLanes(d.cRim);
  for (int k = 0; k < ns; k++)
  for (int ix = spanA[k]; ix <= spanB[k]; ix++) {
    FZC(FZ_PX_VISIT);
    const float dx = ix + 0.5f - fx;
    const float d2 = dx * dx + dy2;
    if (d2 >= out2) { FZC(FZ_PX_OUT); continue; }   // d > r + 0.5: no coverage
    float cov = (d2 <= in2 ? 1.0f : fmn(1, r + 0.5f - sqrtApprox(d2))) * wallT;
    if (cov <= 0) { FZC(FZ_PX_COV0); continue; }
#if defined(FIZZ_PROF) && FIZZ_PROF >= 2
    if (d2 > in2) FZC(FZ_PX_AA);
#endif
    if (ix >= veilLo || ix < veilHi) { FZC(FZ_PX_VEIL); cov = discVeil(ix, d, cov); }   // only bubbles at a surface band pay for the veil
    const float cx = dx - offX, cy = dy - offY, dc2 = cx * cx + cy * cy;
#if defined(FIZZ_PROF) && FIZZ_PROF >= 2
    if (d.core && dc2 >= d.core2Lo && dc2 <= d.core2Hi) FZC(FZ_PX_SQRT);
#endif
    const bool inCore = d.core && (dc2 < d.core2Lo || (dc2 <= d.core2Hi && sqrtExact(dc2) < d.kc));
    float g = 0;
    if (BLICK) {   // pinpoint weight
      const float bdx = dx - d.bX, bdx2 = bdx * bdx;
      if (bdx2 < bRem) { const float db2 = bdx2 + bdy * bdy; g = d.blickK * (db2 <= d.bIn2 ? 1.0f : clampf(d.rbOut - sqrtApprox(db2), 0, 1)); }
    }
#if defined(FIZZ_PROF) && FIZZ_PROF >= 2
    if (g > 0) FZC(FZ_PX_BLICK);
#endif
    uint16_t *px = row + (x0 + step * ix);
    if (inCore) {   // see-through interior (sim): the pinpoint or the dark tint over the liquid as-is, one write, nothing at tint 0
      FZC(FZ_PX_CORE);
      if (g > 0) { FZC(FZ_PX_COREW); const float w = g + d.tintA * (1 - g); rowPxa(px, 0, d.tintA > 0 ? blend565(0, d.cBlick, g / w) : d.cBlick, cov * w); }   // fused with the tint (sim)
      else if (d.tintA > 0) { FZC(FZ_PX_COREW); rowPxa(px, 0, 0, cov * d.tintA); }
      continue;
    }
    FZC(FZ_PX_RING);
#if defined(FIZZ_PROF) && FIZZ_PROF >= 2
    if (cov >= 1 && g <= 0) FZC(FZ_PX_SOLID);
#endif
    if (g > 0) rowPxa(px, 0, blend565(d.cRim, d.cBlick, g), cov);   // ring, pinpoint mixed in 888 before the one blend
    else *px = __builtin_bswap16(cov >= 1 ? rim.c : blend565L(__builtin_bswap16(*px), rim, (int)(cov * 256 + 0.5f)));   // rowPxa toward the rim
  }
}
static inline void discRow(uint16_t *row, int ixa, int ixb, const DiscRow &d) {
  if (d.blick) discRowT<true>(row, ixa, ixb, d); else discRowT<false>(row, ixa, ixb, d);
}
// A size-class bubble's row by its mask (FizzLook): what maskRow / maskPx read, on maskRows' stack.
struct MaskRowK {
  const uint8_t *m;          // the mask's |dy| row: coverage 0..255 of tube column ix at m[|FIZZ_MQ ix + base|]
  int base;
  int W256, tint256;         // the row's wall transmission and the core's dark tint, x 256
  int c0, c1;                // the core: [c0, c1], see-through (empty: c0 > c1)
  int x0, step;              // panel x = x0 + step * ix
  RimLanes rim;
};
static inline int maskT(int t8, int W256) { return ((t8 + (t8 >> 7)) * W256 + 128) >> 8; }   // 0..255 coverage x wall: blend565's T
// Columns [a, b] of a class bubble's row outside the pinpoint's reach: the ring blended toward the rim by its coverage,
// the core left as it is or tinted.
FIZZ_IRAM static void __attribute__((noinline)) maskRow(uint16_t *row, int a, int b, const MaskRowK &k) {
  const uint8_t *const m = k.m; const int W = k.W256, step = k.step, base = k.base; const RimLanes rim = k.rim;
  auto ring = [&](int ia, int ib) {
    uint16_t *px = row + k.x0 + step * ia;
    for (int ix = ia, v = FIZZ_MQ * ia + base; ix <= ib; ix++, px += step, v += FIZZ_MQ) {
      const int t8 = m[v < 0 ? -v : v];
      if (!t8) continue;
      const int T = maskT(t8, W);
      *px = __builtin_bswap16(T >= 256 ? rim.c : blend565L(__builtin_bswap16(*px), rim, T));
    }
  };
  const int c0 = k.c0 > a ? k.c0 : a, c1 = k.c1 < b ? k.c1 : b;
  if (c0 > c1) { ring(a, b); return; }
  ring(a, c0 - 1);
  if (k.tint256 > 0) {   // see-through interior: the dark tint over the liquid as is
    uint16_t *px = row + k.x0 + step * c0;
    for (int ix = c0, v = FIZZ_MQ * c0 + base; ix <= c1; ix++, px += step, v += FIZZ_MQ) {
      const int t8 = m[v < 0 ? -v : v];
      if (t8) *px = __builtin_bswap16(blend565T(__builtin_bswap16(*px), 0, (maskT(t8, W) * k.tint256 + 128) >> 8));
    }
  }
  ring(c1 + 1, b);
}
// Columns [a, b] a surface band veils or the pinpoint can reach: discRowT's per-pixel veil (on the mask's coverage),
// pinpoint and one write.
struct MaskPxK {
  float fx, bX, bdy2, bRem, bIn2, rbOut, blickK, tintA;   // pinpoint (bRem <= 0: out of reach)
  float sR, sL, bR, bL, veilA, pullR, pullL; int veilLo, veilHi;   // the veil (discVeil)
  uint16_t cRim, cBlick;
};
FIZZ_IRAM static void __attribute__((noinline)) maskPx(uint16_t *row, int a, int b, const MaskRowK &k, const MaskPxK &q) {
  for (int ix = a; ix <= b; ix++) {
    const int v = FIZZ_MQ * ix + k.base, t8 = k.m[v < 0 ? -v : v];
    if (!t8) continue;
    const int T0 = maskT(t8, k.W256);
    if (T0 <= 0) continue;
    float cov = T0 * (1.0f / 256);
    if (ix >= q.veilLo || ix < q.veilHi) {   // discVeil: the pixel's footprint over each surface band
      if (ix + 1 > q.sR && q.bR > 0) { const float a1 = fmn(ix + 1, q.sR + q.bR), a0 = fmx(ix, q.sR);
        if (a1 > a0) { const float u = ((a0 + a1) / 2 - q.sR) / q.bR; cov *= 1 - q.veilA * (a1 - a0) * (1 - u) * (1 - q.pullR * u); } }
      if (ix < q.sL && q.bL > 0) { const float a1 = fmn(ix + 1, q.sL), a0 = fmx(ix, q.sL - q.bL);
        if (a1 > a0) { const float u = (q.sL - (a0 + a1) / 2) / q.bL; cov *= 1 - q.veilA * (a1 - a0) * (1 - u) * (1 - q.pullL * u); } }
      if (cov <= 0) continue;
    }
    float g = 0;
    if (q.bRem > 0) {
      const float bdx = ix + 0.5f - q.fx - q.bX, bdx2 = bdx * bdx;
      if (bdx2 < q.bRem) { const float db2 = bdx2 + q.bdy2; g = q.blickK * (db2 <= q.bIn2 ? 1.0f : clampf(q.rbOut - sqrtApprox(db2), 0, 1)); }
    }
    uint16_t *px = row + (k.x0 + k.step * ix);
    if (ix >= k.c0 && ix <= k.c1) {   // see-through interior (sim): the pinpoint or the dark tint, one write
      if (g > 0) { const float w = g + q.tintA * (1 - g); rowPxa(px, 0, q.tintA > 0 ? blend565(0, q.cBlick, g / w) : q.cBlick, cov * w); }
      else if (q.tintA > 0) rowPxa(px, 0, 0, cov * q.tintA);
      continue;
    }
    if (g > 0) rowPxa(px, 0, blend565(q.cRim, q.cBlick, g), cov);   // ring, pinpoint mixed in 888 before the one blend
    else rowPxa(px, 0, q.cRim, cov);
  }
}
// Step 3e concave surface band over [xa, xb): pixel-footprint stroke from the inner shoulder to the outer
// colour at interior opacity `fill` (surfaceFill), thinned by the receding pull, the blick (`blickK`: this
// row's specular weight, peaking mid-dish) and the lit rim. See sim.
TUBE_IRAM static void __attribute__((noinline)) bandRow(uint16_t *row, int xa, int xb, float xm, int dir, float hw, float wEff, float invWidth,
                                              float a, float fill, float blickK, float pull, float rimK, uint16_t inner, uint16_t outer, uint16_t liquid, uint16_t hiC, uint16_t rimC) {
  if (xa < 0) xa = 0; if (xb > PANEL_W) xb = PANEL_W;
  const float rimLo = fmx(0, wEff - 1);
  for (int x = xa; x < xb; x++) {
    const float t = dir * (x + 0.5f - xm);
    const float lo = fmx(t - 0.5f, -hw), hi = fmn(t + 0.5f, wEff);
    const float coverage = fmx(0, hi - lo);
    if (coverage <= 0) continue;
    const float u = clampf(((lo + hi) * 0.5f + hw) * invWidth, 0, 1);
    const float us = u * u * (3 - 2 * u);
    const uint16_t c = blend565(inner, outer, us);
    const float af = a * fill * coverage * (1 - pull * us);
    const float ab = a * blickK * coverage * 4 * u * (1 - u);
    const float rimCoverage = fmx(0, hi - fmx(lo, rimLo));
    const float ar = a * rimK * rimCoverage;
    // fill, blick and rim composite as ONE write per pixel (premultiplied sum), so the fixed-point
    // rounding is taken once; a single layer takes the plain path (see sim). The division runs only
    // on multi-layer pixels: the 1-2 rim px per row and the blick rows.
    RGB P{0, 0, 0}; float A = 0; int nL = 0; uint16_t cLast = 0;
    auto layer = [&](uint16_t col, float al) {
      if (al < 1 / 255.0f) return;
      const RGB C = to888(col); const float k = 1 - al;
      P.r = P.r * k + C.r * al; P.g = P.g * k + C.g * al; P.b = P.b * k + C.b * al;
      A = A * k + al; nL++; cLast = col;
    };
    layer(pull > 0 ? blend565(c, liquid, pull) : c, af); layer(hiC, fmn(1, ab)); layer(rimC, fmn(1, ar));
    if (nL == 1) rowPxa(row, x, cLast, A);
    else if (nL > 1) { const float inv = 1 / A; rowPxa(row, x, q({P.r * inv, P.g * inv, P.b * inv}), A); }
  }
}
static inline float luma(RGB c) { return 0.299f * c.r + 0.587f * c.g + 0.114f * c.b; }

// Ambient-light desaturation (params.ambientLight, sim ambientize): a colour brighter than the
// diffuse body luma reads as a reflection of the neutral room light — grey of the same luma —
// instead of the liquid glowing brighter in its own colour. Full desaturation at twice the body luma.
// Callers scale amt by the liquid's opacity (ambientAmt): bright areas of a transparent liquid are
// mostly light transmitted through it (tinted), so full desaturation would leave it colourless.
static inline RGB ambientize(RGB c, float bodyL, float amt) {
  if (amt <= 0) return c;
  float l = luma(c);
  float k = amt * fmn(1, fmx(0, (l - bodyL) / bodyL));
  return k > 0 ? mix(c, RGB{l, l, l}, k) : c;
}
// Diffuse body luma: the ambientize reference (sim ambientBodyL).
static inline float ambientBodyL(const Params &p) {
  return fmx(1, luma(scale(hexToRgb(p.liquid), p.brightness * p.liquidBright)));
}
// Effective ambientize amount: the knob, scaled down by transparency (sim ambientAmt).
static inline float ambientAmt(const Params &p) {
  return p.ambientLight * (1 - clampf(p.liquidTransparency, 0, 1));
}

// Per-column streak factor 0.82..1 for the dried traces (subtle texture, not stripes) — the same
// integer hash as the sim's traceStreak, so both smears show identical striations (no shimmer).
static inline float traceStreak(uint32_t n) {
  uint32_t h = n * 2654435761u + 0x9E3779B9u;
  h ^= h >> 15; h *= 2246822519u; h ^= h >> 13;
  return 0.82f + 0.18f * ((h >> 16) * (1.0f / 65535.0f));
}
// Wet film (step 3d, see sim): the film a fully drawn receding line leaves, h = eta * R, eta = filmEta(p)
// (physics.cpp, once per frame per tube).
// Film tables, immutable once render_init built them (PSRAM: internal RAM has no 5 KB to spare):
// FILM_PHI[i] = path fraction 1/256 through the annular film at (2 eta - eta^2)/(1 - u^2) = i/256;
// FILM_LG[v] = -log2 of the decoded sRGB channel v, Q8; FILM_EX[m] = sRGB encoding of 2^(-m/256). Same
// formulas, rounding and index math as the sim, so D^(1-f) C^f (linear light) comes out the same on both sides.
// The residue takes the same law, B^(1-tau) C^tau against the tube back (ResidueTint).
static uint16_t *FILM_PHI = nullptr, *FILM_LG = nullptr;
static uint8_t *FILM_EX = nullptr;
static double srgbLin(double c) { return c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4); }
static double srgbEnc(double l) { return l <= 0.0031308 ? 12.92 * l : 1.055 * pow(l, 1 / 2.4) - 0.055; }
static void buildFilmLuts() {
  for (int i = 0; i <= 256; i++) FILM_PHI[i] = (uint16_t)floor(256 * (1 - sqrt(1 - i / 256.0)) + 0.5);
  for (int v = 0; v < 256; v++) { const double lg = floor(-log2(srgbLin((v < 1 ? 1 : v) / 255.0)) * 256 + 0.5); FILM_LG[v] = (uint16_t)(lg > 4095 ? 4095 : lg); }
  for (int m = 0; m < 4096; m++) FILM_EX[m] = (uint8_t)floor(255 * srgbEnc(pow(2.0, -m / 256.0)) + 0.5);
}
// The film path fraction through a row, 1/256, for thickness eta (sim filmRowT).
static inline int filmRowT(float eta, float kRow) {
  if (eta <= 0) return 0;
  const float q = eta * (2 - eta) * kRow;
  return q >= 1 ? 256 : FILM_PHI[(int)(q * 256 + 0.5f)];
}
// 1 - smoothstep(t), t clamped to 0..1 (sim ease): the imminent zone's eases, 1 at the line, 0 at its reach.
static inline float ease(float t) { const float s = clampf(t, 0, 1); return 1 - s * s * (3 - 2 * s); }
// The residue zones of one strip row (drawTube step 3d, [z0, z1)): the soft ramp over plain residue, or near a
// sheared / filmed edge the imminent residue and the wet film (see the comments at the call). Step 6: out of drawTube
// (noinline): inline, its ~40 live values spilled every pixel. The same expressions, in the same order.
// The residue blur's cross-frame memo (drawTube, step 6): the key of the last traceA (filmV; the columns computed
// [a0, a1) and read [c0, c1) of traceRaw) and the per-frame dirty flags. PSRAM, one per tube (render_init).
// blkMax: the largest traceA of each TRACE_BLK-column block over [a0, a1) (traceFillLutI's skip test).
struct TraceMemo { bool valid; float filmV; int a0, a1, c0, c1, aLo, aHi; uint8_t dirty[TUBE_LENGTH_PX];
                   uint16_t blkMax[(TUBE_LENGTH_PX + TRACE_BLK - 1) / TRACE_BLK]; };
// mode (a segment's: residueRowMode / residueZones): on a thin row or segment every residue sample has depthF + 0.5 < 1,
// so T = (int)(fmx(dF, fw) + 0.5) is (int)(fw + 0.5) (fw >= dF wherever that shows, else both give 0): the sampling goes,
// and with it the shift (it only moves the sample), and the film term of a side whose term is exactly +0 on the row.
struct ZoneRow {
  const uint16_t *traceA; const ResidueTint *tint;
  float ex, exL, hw, invSoftW, xm, invBW, invN, shL, shR, invZL, invZR, etaL, etaR, kRow, visL, visR;
  int softW, xrL, xr, a0, a1; bool rowPlain;
  // the segment modes' inputs (residueRowMode / residueZones): the span's largest coat, trZ, TraceMemo::blkMax, and the
  // two zone segments [zl0, zl1) and [zr0, zr1)
  int aHi, trZ; const uint16_t *blkMax; int zl0, zl1, zr0, zr1;
};
TUBE_IRAM static void __attribute__((noinline)) traceZoneRow(uint16_t *row, int z0, int z1, const ZoneRow &z, int mode) {
  const ResidueTint &tint = *z.tint; const uint16_t *traceA = z.traceA;
  const float ex = z.ex, exL = z.exL, hw = z.hw, invSoftW = z.invSoftW, xm = z.xm, invBW = z.invBW, invN = z.invN;
  const bool thin = mode & 1;
  const float shL = thin ? 0.0f : z.shL, shR = thin ? 0.0f : z.shR, invZL = z.invZL, invZR = z.invZR, kRow = z.kRow;
  const float etaL = thin && !(mode & 2) ? 0.0f : z.etaL, etaR = thin && !(mode & 4) ? 0.0f : z.etaR;
  const float visL = z.visL, visR = z.visR;
  const int softW = z.softW, xrL = z.xrL, xr = z.xr, a0 = z.a0, a1 = z.a1; const bool rowPlain = z.rowPlain;
  for (int x = z0; x < z1; x++) {
    const float cr = ex + hw - x - 0.5f, cl = x + 0.5f - exL + hw;
    const float cov = softW > 0
      ? clampf((cr < cl ? cr : cl) * invSoftW, 0, 1)
      : (x >= xrL && x < xr ? 1.0f : 0.0f);
    if (cov >= 1) continue;
    if (rowPlain) {
      const int T = traceA[x] ? tint.depthT(traceA[x]) : 0;
      if (T > 0) row[x] = __builtin_bswap16(tint.at(T));
      continue;
    }
    const float oL = exL - x - 0.5f, oR = x + 0.5f - ex, bt = clampf((x + 0.5f - xm) * invBW + 0.5f, 0, 1);
    float sh = 0, fw = 0;
    if (bt < 1) { const float k = 1 - bt, wN = ease(oL * invN); if (shL != 0) sh += k * shL * ease(oL * invZL); if (etaL > 0) fw += k * filmRowT(etaL * wN, kRow) * wN * visL; }
    if (bt > 0) { const float wN = ease(oR * invN); if (shR != 0) sh += bt * shR * ease(oR * invZR); if (etaR > 0) fw += bt * filmRowT(etaR * wN, kRow) * wN * visR; }
    int T;
    if (thin) T = (int)(fw + 0.5f);   // see ZoneRow
    else {
      const float xf = x - sh;
      const int i0 = (int)ffloor(xf);
      const float ft = xf - i0;
      const float r0 = i0 >= a0 && i0 < a1 ? (float)traceA[i0] : 0.0f, r1 = i0 + 1 >= a0 && i0 + 1 < a1 ? (float)traceA[i0 + 1] : 0.0f;
      T = (int)(fmx(r0 + r1 > 0 ? tint.depthF(r0 + (r1 - r0) * ft) : 0.0f, fw) + 0.5f);
    }
    if (T > 0) row[x] = __builtin_bswap16(tint.at(T));
  }
}

// drawTube 3d, per residue row: bit 1 = thin (no coat of the span [a0, a1) shows on the row: every depth it samples, in the
// fill, the sheared spans and the zone, is of a coat A <= aHi, a column or interpolated between two, and depthT / depthF
// are non-decreasing in A, so each is 0 when aHi's phi index is below trZ; the fill and sheared spans write nothing then,
// the zone only its film: ZoneRow::thin). That index is floor(v), v = (aHi K + 2^15) / 2^16, in depthT; depthF's float
// forms of it (rounded product + 0.5, or fused) stay within ~5e-5 of v below index 257, so they can only reach floor(v) + 1
// when v is within 2^-10 of it: the bound takes that one then. Bits 2 / 4, on a thin row: the home / time edge's film term
// can be non-zero. It is exactly +0 when that film is off, or when every filmRowT index it takes is 0: eta wN <= eta <= 1
// (wN <= 1) and eta (2 - eta) kRow rises with eta, so the index stays 0 while the bound is below a quarter of the rounding
// step (its own rounding: a few ulp). Flash: once a row, no IRAM to spare.
static int coatMode(uint32_t aMax, const ZoneRow &z) {   // aMax: the largest coat any sample can take
  const uint64_t v = (uint64_t)aMax * z.tint->K + 32768u;
  const uint64_t idx = (v >> 16) + ((v & 0xffffu) >= 0xffffu - 63 ? 1 : 0);
  if ((idx < 256 ? (int)idx : 256) >= z.trZ) return 0;
  const float kRow = z.kRow;
  auto film = [kRow](float eta) { return !(eta <= 0 || (eta <= 1 && eta * (2 - eta) * kRow * 256 < 0.25f)); };
  return 1 | (film(z.etaL) ? 2 : 0) | (film(z.etaR) ? 4 : 0);
}
static int __attribute__((noinline)) residueRowMode(const ZoneRow &z) { return coatMode((uint32_t)z.aHi, z); }
// The row's two zone segments (drawTube 3d), each by its mode: the row's, or on a row that is not thin the segment's own:
// its samples lie within S >= |shL| + |shR| + 1 px of it (the shift sums shL and shR scaled by weights <= 1; a sample takes
// the floor column and the next), so the largest coat they can take is the largest blkMax over those columns in [a0, a1)
// (0 past them). A thin segment writes only a film (ZoneRow): none on a plain row. Flash, like residueRowMode.
static void __attribute__((noinline)) residueZones(uint16_t *row, const ZoneRow &z, int rowMode) {
  const float shAbs = fabsf(z.shL) + fabsf(z.shR);
  const int S = shAbs < (float)TUBE_LENGTH_PX ? (int)shAbs + 2 : TUBE_LENGTH_PX + 2;
  for (int seg = 0; seg < 2; seg++) {
    const int z0 = seg ? z.zr0 : z.zl0, z1 = seg ? z.zr1 : z.zl1;
    if (z1 <= z0) continue;
    int mode = rowMode;
    if (!mode) {
      const int c0 = z0 - S > z.a0 ? z0 - S : z.a0, c1 = z1 + S < z.a1 ? z1 + S : z.a1;
      uint32_t m = 0;
      for (int b = c0 / TRACE_BLK; b * TRACE_BLK < c1; b++) if (z.blkMax[b] > m) m = z.blkMax[b];
      mode = coatMode(m, z);
    }
    if (mode == 0 || (mode > 1 && !z.rowPlain)) traceZoneRow(row, z0, z1, z, mode);
  }
}

// Per-channel LUTs built once with the exact float formulas they replace (bit-exact with the sim):
// sprite alpha 0..255 -> blend fraction; tick emboss highlight / shadow of an expanded 565 channel.
static uint16_t LUT_alphaT16[256];
static uint8_t LUT_embHi[256], LUT_embLo[256];
// A 565 colour as expand565's three 8-bit channels in one word, r | g << 8 | b << 16: EXP565[2 hi] | EXP565[2 lo + 1]
// for its high / low byte (each byte's bits land in disjoint places, g's from both; interleaved: one base register).
// The sprite digit runs blend with it (blendLanesSw): no per-pixel unpacking, and a strip pixel is read in its
// byte-swapped layout as it is. 2 KB, PSRAM, built once by render_init (always cache-hot in the digit pass).
static uint32_t *EXP565 = nullptr;
static void buildLuts() {
  for (int v = 0; v < 256; v++) {
    LUT_alphaT16[v] = (uint16_t)alphaT(v / 255.0f);
    LUT_embHi[v] = (uint8_t)jround(clampf((float)v + (255.0f - (float)v) * 0.7f, 0, 255));
    LUT_embLo[v] = (uint8_t)jround(clampf((float)v * 0.25f, 0, 255));
  }
  if (EXP565) for (int v = 0; v < 256; v++) {
    const uint32_t r5 = v >> 3, gh = v & 7, gl = v >> 5, b5 = v & 31;   // high byte: r5 g[5:3]; low byte: g[2:0] b5
    EXP565[2 * v] = ((r5 << 3) | (r5 >> 2)) | (((gh << 5) | (gh >> 1)) << 8);
    EXP565[2 * v + 1] = ((gl << 2) << 8) | (((b5 << 3) | (b5 >> 2)) << 16);
  }
}
static inline uint32_t lanes565(uint16_t c) { return EXP565[(c >> 8) * 2] | EXP565[(c & 0xff) * 2 + 1]; }
static inline uint32_t lanesSw(uint16_t s) { return EXP565[(s & 0xff) * 2] | EXP565[(s >> 8) * 2 + 1]; }   // a strip pixel (byte-swapped)
// blend565T(a, b, T) for 0 < T < 256 on lanes (a = lanes of the pixel behind, b = of the mark), in the strip's
// byte-swapped layout: the same lane arithmetic, the result packed straight into the swapped bit positions.
static inline uint16_t blendLanesSw(uint32_t a, uint32_t b, uint32_t T) {
  const uint32_t arb = a & 0x00ff00ffu, ag = (a >> 8) & 0xff;
  const uint32_t rb = (arb << 8) + ((b & 0x00ff00ffu) - arb) * T + 0x00800080u;   // lanes as blend565T
  const uint32_t g = (ag << 8) + (((b >> 8) & 0xff) - ag) * T + 128;
  return (uint16_t)(((rb >> 8) & 0xf8) | ((rb >> 19) & 0x1f00) | ((g >> 13) & 7) | ((g << 3) & 0xe000));
}
static inline uint16_t embossHi(uint16_t c) { int r, g, b; expand565(c, r, g, b); return rgb565(LUT_embHi[r], LUT_embHi[g], LUT_embHi[b]); }
static inline uint16_t embossLo(uint16_t c) { int r, g, b; expand565(c, r, g, b); return rgb565(LUT_embLo[r], LUT_embLo[g], LUT_embLo[b]); }

TubeLayout tubeLayout(const Params &p) {
  int H = (int)jround(p.tubeHeight); H = H < 4 ? 4 : H > TUBE_HEIGHT_MAX ? TUBE_HEIGHT_MAX : H;
  auto y = [&](float v) { int r = (int)jround(v); return r < 0 ? 0 : r > PANEL_H - H ? PANEL_H - H : r; };
  return { H, y(p.hoursY), y(p.minutesY) };
}

// Each tube is drawn into an H x PANEL_W strip buffer (H ≤ TUBE_HEIGHT_MAX); panel-row y maps to
// strip row y - baseY. Anything outside the strip is clipped (the sim never draws there either).
// All working state lives in a per-tube `Tube` context (below) so the two tubes can render on
// different cores at the same time; nothing in this file is file-static and mutable per frame.
static const int L = TUBE_LENGTH_PX;
struct Tube;

// ---------------------------------------------------------------------------------------------
// palette
// ---------------------------------------------------------------------------------------------
struct Palette {
  uint16_t rows[TUBE_HEIGHT_MAX], bubbleIn[TUBE_HEIGHT_MAX], tubeBackRows[TUBE_HEIGHT_MAX];
  uint16_t bubbleRimRows[TUBE_HEIGHT_MAX];   // fizz ring colour per row, dimmed by the cylinder's light (scalar bubbleRim: spirit bubble, pinpoint)
  uint16_t body, tubeBack, bubbleRim;
  float rowK[TUBE_HEIGHT_MAX];   // luma weight per row for front brightening (sim step 3a)
  uint16_t dryT[TUBE_HEIGHT_MAX]; // 1/256: what an empty tube transmits of the back per row (0 inside the wall band); fades rear marks behind air
  uint32_t gen = 0; int H = 0; float light = 0; bool valid = false;   // cache key (light is exact: hit while the tube is at rest)
};

// buildPalette's light-independent library results per row, kept per (gen, H) (step 6: a moving light rebuilds the
// palette every frame, ~1-2 ms a tube, mostly these calls). Only the raw call results are kept: every expression
// that consumes them is evaluated as before, so the board's fused multiply-adds see the same operands.
// PSRAM, one per tube (render_init).
struct PalCache {
  uint32_t gen = 0; int H = 0; bool valid = false;
  float rimPow[TUBE_HEIGHT_MAX], dryExp[TUBE_HEIGHT_MAX], asinY[TUBE_HEIGHT_MAX], chord[TUBE_HEIGHT_MAX];
  float ambCos[TUBE_HEIGHT_MAX], reflExp[TUBE_HEIGHT_MAX];   // glassW
  // light-independent row terms of buildPalette, the same expressions: wall glow + rim, over the contents, dryT, the
  // back gradient and the body shading before the light mix
  float wall[TUBE_HEIGHT_MAX], wetRim[TUBE_HEIGHT_MAX], dryT[TUBE_HEIGHT_MAX]; RGB back[TUBE_HEIGHT_MAX], c0[TUBE_HEIGHT_MAX];
  float liqDry[TUBE_HEIGHT_MAX];   // weight of the empty tube's row over the contents: past their edge liqU (sim liqT)
  // 3e concave band colours per row, a function of the palette and the row cache only (buildBandRows, rebuilt with the
  // palette): inner shoulder, the lens / body mix under the outer colour, the rim colour, the back's luma weight
  uint16_t bandInner[TUBE_HEIGHT_MAX], bandLensMix[TUBE_HEIGHT_MAX], bandRimC[TUBE_HEIGHT_MAX]; float bandBackK[TUBE_HEIGHT_MAX];
  // the palette rows those band colours were made of (bandValid: since this pc's (gen, H)): a row whose body and back
  // colours did not change keeps them (a moving light changes ~1 row in 10 a frame)
  uint16_t bandKeyRow[TUBE_HEIGHT_MAX], bandKeyBack[TUBE_HEIGHT_MAX]; bool bandValid = false;
  float u[TUBE_HEIGHT_MAX];   // buildPalette's row position u (rim light), the same expression
};

// ---------------------------------------------------------------------------------------------
// bitmap fonts (digitFont 0..4)
// ---------------------------------------------------------------------------------------------
struct Font { uint8_t w, h; uint8_t g[10][8]; };
static const Font FONTS[] = {
  {3, 5, {{7,5,5,5,7},{2,6,2,2,7},{7,1,7,4,7},{7,1,7,1,7},{5,5,7,1,1},{7,4,7,1,7},{7,4,7,5,7},{7,1,1,1,1},{7,5,7,5,7},{7,5,7,1,7}}},
  {4, 6, {{6,9,9,9,9,6},{2,6,2,2,2,7},{6,9,1,2,4,15},{14,1,6,1,9,6},{2,6,10,15,2,2},{15,8,14,1,9,6},{6,8,14,9,9,6},{15,1,2,4,4,4},{6,9,6,9,9,6},{6,9,9,7,1,6}}},
  {5, 7, {{14,17,19,21,25,17,14},{4,12,4,4,4,4,14},{14,17,1,2,4,8,31},{31,2,4,2,1,17,14},{2,6,10,18,31,2,2},{31,16,30,1,1,17,14},{6,8,16,30,17,17,14},{31,1,2,4,8,8,8},{14,17,17,14,17,17,14},{14,17,17,15,1,2,12}}},
  {5, 7, {{31,17,17,17,17,17,31},{1,1,1,1,1,1,1},{31,1,1,31,16,16,31},{31,1,1,31,1,1,31},{17,17,17,31,1,1,1},{31,16,16,31,1,1,31},{31,16,16,31,17,17,31},{31,1,1,1,1,1,1},{31,17,17,31,17,17,31},{31,17,17,31,1,1,31}}},
  {6, 8, {{30,51,51,51,51,51,51,30},{12,28,12,12,12,12,12,63},{30,51,3,6,12,24,48,63},{62,3,3,30,3,3,51,30},{6,14,30,54,63,6,6,6},{63,48,48,62,3,3,51,30},{30,48,48,62,51,51,51,30},{63,3,6,12,24,24,24,24},{30,51,51,30,51,51,51,30},{30,51,51,31,3,3,3,30}}},
};
static const int NUM_FONTS = sizeof(FONTS) / sizeof(FONTS[0]);
static const int SPRITE_FONT = NUM_FONTS;

// ---------------------------------------------------------------------------------------------
// sprite glyphs: box-filtered from the flash sheet into the device box, cached per tube
// ---------------------------------------------------------------------------------------------
// Fixed pool per tube (3 B/px), allocated once at boot (render_init) in PSRAM: deterministic footprint, no
// heap traffic on param changes. Internal RAM cannot take it: the two DMA strips + BT controller leave
// <60 KB there. GLYPH_POOL_PX is sized for the sliders' worst case (sim PARAM_META): 10 glyphs of at most
// bw x bh = (GLYPH_EM_W x GLYPH_EM_H) * DIGIT_SCALE_MAX texels, each grown by DIGIT_SHADOW_OFFSET_MAX on the right and
// below, two planes (behind air / behind liquid) when the shadow is baked in; scale and offset are design px, so the wider tube's px scale (PX_SCALE_MAX) grows both sides (rounded up).
// A set that does not fit (values pushed past the sliders over serial) drops the glyphs past the budget
// (visible, not silent).
// The sheet the glyphs are filtered from has SPRITE_CELL_H rows (layout.h): at least the texels per pixel of the design
// (64 rows at px scale 1) on the widest tube.
static_assert(SPRITE_CELL_H >= 64 * PX_SCALE_MAX, "digit sprite sheets too small for the widest tube (layout.h SPRITE_CELL_H)");
#define GLYPH_CEIL(v) ((int)(v) + ((float)(int)(v) < (v)))
#define GLYPH_OFF_PX GLYPH_CEIL(DIGIT_SHADOW_OFFSET_MAX * PX_SCALE_MAX)
#define GLYPH_POOL_PX (10 * 2 * (GLYPH_CEIL(GLYPH_EM_W * DIGIT_SCALE_MAX * PX_SCALE_MAX) + GLYPH_OFF_PX) * (GLYPH_CEIL(GLYPH_EM_H * DIGIT_SCALE_MAX * PX_SCALE_MAX) + GLYPH_OFF_PX))
#define GLYPH_POOL_CAPS MALLOC_CAP_SPIRAM
// w x h texels (body plus the baked shadow margin); `adv` is the body width the layout advances by.
// Vertical watch (ScaledSet::rot): the planes are stored as the panel shows them — the glyph turned a quarter
// clockwise, its bottom row in column 0 — so w x h is the turned box and the draw pass needs no special case.
// c/a: the glyph as drawn behind air; cw/aw: as drawn behind liquid (the shadow composite depends on the
// liquid's transparency, see bakeShadow). Without a shadow both pairs alias the same plane.
// span[plane]: per row the first and one-past-last column with coverage (both 0 = empty row), so the
// compositor skips the transparent margins; nullptr when the glyph is taller than the span table.
struct ScaledGlyph { int w, h, adv; uint16_t *c, *cw; uint8_t *a, *aw; const uint8_t *span[2]; };
// Span table per tube (boot-time, PSRAM like the pool): 10 glyphs x 2 planes x GLYPH_SPAN_ROWS rows x 2 B.
// GLYPH_SPAN_ROWS covers GLYPH_BH_CAP plus the largest slider shadow offset; a glyph pushed taller
// (or wider than 255 columns) over serial draws without spans (full rows), never past the table.
#define GLYPH_BH_CAP 96   // tallest glyph drawn, rows (Labels::rows); the slider's worst case fits, more over serial is cut
#define GLYPH_SPAN_ROWS 128
static_assert(GLYPH_EM_H * DIGIT_SCALE_MAX * PX_SCALE_MAX <= GLYPH_BH_CAP && GLYPH_BH_CAP + GLYPH_OFF_PX <= GLYPH_SPAN_ROWS, "glyph caps vs the sliders");
#define GLYPH_SPAN_BYTES (10 * 2 * GLYPH_SPAN_ROWS * 2)
struct ScaledSet {
  int sheet = -1, bw = 0, bh = 0; float brightness = -1, tintAmt = -1, tone = 0; uint32_t tint = 0;
  int shadow = -2, shadowOff = 0; float shadowA = -1, transK = -1; bool rot = false;
  float floorC = -1; uint16_t floorR = 0;   // contrast floor baked into the behind-liquid plane (bakeFloor), 0 = none
  ScaledGlyph g[10] = {};
  uint16_t *poolC = nullptr; uint8_t *poolA = nullptr; uint8_t *poolS = nullptr;
};
// ---------------------------------------------------------------------------------------------
// marks (ticks + labels) seen through the liquid
// ---------------------------------------------------------------------------------------------
// Integer version of the sim's throughLiquid (luma in 1/1000 units, blend fractions in 1/256).
// T = liquidTransparency in 1/256, C = contrast in 1/1000 (both hoisted into Mark).
static uint16_t throughLiquid(uint16_t bg, uint16_t mark, int T, int C) {
  if (C <= 0) return blend565T(bg, mark, T);   // no contrast floor: skip both luminance calculations
  int Br, Bg, Bb, Mr, Mg, Mb;
  expand565(bg, Br, Bg, Bb); expand565(mark, Mr, Mg, Mb);
  int cr = Br + (((Mr - Br) * T + 128) >> 8), cg = Bg + (((Mg - Bg) * T + 128) >> 8), cb = Bb + (((Mb - Bb) * T + 128) >> 8);
  int lb = 299 * Br + 587 * Bg + 114 * Bb, lc = 299 * cr + 587 * cg + 114 * cb, d = lc - lb;
  if (abs(d) >= C) return rgb565(cr, cg, cb);
  int dir = d != 0 ? (d > 0 ? 1 : -1) : (lb > 110000 ? -1 : 1);
  int target = lb + dir * C; if (target < 0) target = 0; if (target > 255000) target = 255000;
  if (dir < 0) {
    int den = lc < 1000 ? 1000 : lc;   // scale toward black
    cr = (cr * target + den / 2) / den; cg = (cg * target + den / 2) / den; cb = (cb * target + den / 2) / den;
  } else {
    int den = 255000 - lc; if (den < 1000) den = 1000;   // mix toward white
    int K = (target - lc) * 256 / den; if (K > 256) K = 256; if (K < 0) K = 0;
    cr += ((255 - cr) * K + 128) >> 8; cg += ((255 - cg) * K + 128) >> 8; cb += ((255 - cb) * K + 128) >> 8;
  }
  if (cr > 255) cr = 255; if (cg > 255) cg = 255; if (cb > 255) cb = 255;
  return rgb565(cr, cg, cb);
}

// rel = +1 / -1: emboss highlight / shadow of body colour c, derived after the liquid pass.
// Liquid column bounds per tube row in panel coordinates: liquid where lo <= x < hi.
// Concave surface band of one tube for the rear-mark compositor (render frame, before the `remaining`
// mirror; 0 = time edge, dir +1, 1 = home edge, dir -1): per row the profile x, the outward stroke width
// (0 = no band) and the fill / blick / rim weights, stroke opacity included. See sim BandInfo / markFn.
struct BandInfo { const float *xm[2], *w[2], *fill[2], *blick[2], *rim[2]; float pull[2], hw; bool mirror; int L; };
// Liquid body bounds per tube row (panel frame) plus, when drawn, the surface band past them.
struct Edges { const float *lo, *hi; const BandInfo *band = nullptr; };
struct Mark {
  Tube &t; int y0; Edges edges; bool onTop; int T, C;   // T: transparency 1/256, C: contrast 1/1000
  int Cin;       // the floor inside the liquid: C, or 0 where it is baked into the plane (bakeFloor)
  bool bakedT;   // the mark's coverage already includes the liquid's transparency (sprite digits with a baked shadow, see bakeShadow)
  Mark(Tube &t_, int y0_, Edges e, const Params &p, bool onTop_, float contrast, bool bakedT_ = false, bool floorBaked = false) : t(t_), y0(y0_), edges(e), onTop(onTop_), bakedT(bakedT_) {
    T = (int)(p.liquidTransparency * 256 + 0.5f); if (T < 0) T = 0; if (T > 256) T = 256;
    C = (int)(contrast * 1000 + 0.5f); Cin = floorBaked ? 0 : C;
  }
  // covT: coverage in 1/256 (256 = opaque)
  inline void operator()(int x, int y, uint16_t c, int covT = 256, int rel = 0) const;
#ifdef TICK_PROF
  uint32_t *prof = nullptr;   // -DTICK_PROF: the tick layer's counters (Tube::tickProf); null for every other mark
  void profPixel(int x, int y, uint16_t c, int covT, int rel) const;
#endif
  // A rear mark within the concave surface band's footprint (see sim markFn); false when the pixel is outside
  // it, or inside the body where the band lets everything through — the plain paths then apply.
  bool bandMark(int x, int y, int ry, uint16_t c, int covT, int rel, bool inside) const;
  // Whether the mark at (x, tube row ry) is composited through the liquid — the same test operator() applies.
  inline bool inLiquid(int x, int ry) const { return !onTop && x >= edges.lo[ry] && x < edges.hi[ry]; }
  // A mark pixel over the liquid: its colour through the liquid (contrast floor included); covT is updated.
  inline uint16_t wetColour(uint16_t bg, uint16_t c, int &covT) const { return wetColourT(bg, c, covT, T, Cin, bakedT); }
  // bakedT: the texel as is without a floor; with one, the colour the glyph shows at full glyph coverage —
  // the texel over the liquid at a = max(T, cov) — is floored and blended by the rest, cov / a (sim markFn).
  // recipT (optional, from recipOf(T)): the division by T as a multiply.
  static inline uint16_t wetColourT(uint16_t bg, uint16_t c, int &covT, int T, int C, bool bakedT, uint32_t recipT = 0) {
    if (!bakedT) return throughLiquid(bg, c, T, C);
    if (C <= 0) return c;
    if (covT >= T) { const int a = covT; covT = 256; return throughLiquid(bg, c, a, C); }   // (cov * 256 + cov / 2) / cov
    const uint32_t n = (uint32_t)(covT * 256 + (T >> 1));
    covT = recipT ? (int)(((uint64_t)n * recipT) >> 32) : (int)(n / T);
    return throughLiquid(bg, c, T, C);
  }
  // ceil(2^32 / d) for 1 <= d <= 256: (n * recipOf(d)) >> 32 == n / d exactly for n < 2^24.
  static inline uint32_t recipOf(int d) { return d > 0 ? 0xFFFFFFFFu / (uint32_t)d + 1 : 0; }
};

#define PIE_LANES 144     // a SIMD run's lanes: <= FRAC_RUN_MAX pixels plus <= 7 lanes before it, in whole 16-B blocks
#define FRAC_RUN_MAX 130  // a run's part: a copy spans at most gw + 1 <= 129 columns (gw is capped at 128)
// The digit kernels' scratch, one per Tube (both tubes render at once, one per core), allocated once by render_init,
// 16-B aligned: internal RAM in LCD fast mode (the SIMD lanes are rewritten every run), else PSRAM (the BLE window, the
// AMOLED). 1,119 B a tube with the alignment slack, 1,407 B with -DDIGIT_VERIFY. Never on the render tasks' stacks (4 KB,
// several frames deep under these kernels).
struct DigitScratch {
  int16_t T[PIE_LANES] __attribute__((aligned(16)));    // SIMD lanes: coverage (PieRun)
  uint16_t C[PIE_LANES] __attribute__((aligned(16)));   // SIMD lanes: colour (PieRun)
  uint32_t row[FRAC_RUN_MAX];                           // scalar fractional run: covT << 16 | colour
#ifdef DIGIT_VERIFY
  uint16_t want[PIE_LANES];                             // -DDIGIT_VERIFY: the scalar blend PieRun::end compares with
#endif
};
#if DIGIT_PIE
// The last fractional run's taps (spriteRunFrac, SIMD path): under a magnifying lens neighbouring strip rows sample the
// same source row, so a glyph row repeats the one before it with the same run and only the blend is new. Reset by
// planLabels every frame (a memo within the digit pass, never across frames). Keyed on the tap weights too: the dry
// and the wet copy take different ones.
#define FRAC_MEMO_MAX FRAC_RUN_MAX
struct FracMemo {
  const uint8_t *a0, *a1; const uint16_t *cq; int m, nIn, p0, p1, q0, q1, scaleT, mode, w00, w10, w01, w11; bool valid;
  int16_t T[FRAC_MEMO_MAX]; uint16_t C[FRAC_MEMO_MAX];
};
#endif
#define LABELS_MAX 12   // a tube's labels: 12 h at step 1, 60 min at step 5 (the sliders' smallest); more over serial is cut
struct Label { int x0, y; char text[3]; int len; int adv[2]; };   // y: panel row of the first glyph's top
struct Labels {
  Label list[LABELS_MAX]; int n; int bw, bh, ry0, ry1, yTop; ScaledGlyph *sprite; const Font *font; int gap;
  uint16_t rows[GLYPH_BH_CAP]; int16_t sourceRows[TUBE_HEIGHT_MAX]; int shadow, shadowT, shadowOff;   // shadow colour (-1 = none), opacity 1/256, px offset
  int16_t drySourceRows[TUBE_HEIGHT_MAX]; int dryRy0, dryRy1;   // rear digits behind air (digitDryLens)
  // Vertical watch: glyphs turned to read upright, a label's digits advance across the tube (panel y) from
  // Label::y, Label::x0 is where the glyph body starts along it; bw x bh stay the glyph as read (sim Labels).
  bool vertical = false;
  // View-angle parallax of the rear wall (sim Labels): behind air (d) and behind liquid (w, / liquidIor), 1/16 px, x along
  // the panel, y in rows down; 0 on top. Set every frame (shiftTap takes the taps).
  int sx16d = 0, sx16w = 0, sy16d = 0, sy16w = 0;
  // cache key: everything above is a function of (params gen, H) plus these motion-derived ints (the parallax enters
  // only through the row spans: whole rows and overhang of the dry and the wet copy)
  uint32_t gen = 0; int H = 0, bottomOff = 0, first = -1, keyRowD = 0, keyRowW = 0; bool valid = false, have = false;
};
// The rear parallax of a column of wet share k (1/256; sim shiftTap): the dry shift d16 moved toward the wet one w16 (1/16
// px) by k, as whole px i and the far tap's weight w1 (1/256; destination c samples source c - i - w1/256). 1/4096 px ints.
// Premultiplied bilinear colour of a resampled pixel (sim mix565): each 565 channel of the four taps weighted by its
// tap's alpha x weight m, divided by the pixel's coverage a = (sum m + 32768) >> 16 (1..255) through a reciprocal table
// (no divide: ((S + 128) >> 8) * floor(2^24 / a), rounded >> 32, clamped). One tap at full weight gives its own colour.
struct MixRecip { uint32_t v[256]; constexpr MixRecip() : v() { for (int a = 1; a < 256; a++) v[a] = (1u << 24) / (uint32_t)a; } };
static constexpr MixRecip MIX_RECIP{};
static inline uint32_t mixCh(uint32_t S, uint64_t R, uint32_t mx) {
  const uint32_t v = (uint32_t)(((uint64_t)((S + 128) >> 8) * R + (1ull << 31)) >> 32);
  return v > mx ? mx : v;
}
static inline uint16_t mix565(uint32_t m00, uint32_t m10, uint32_t m01, uint32_t m11, uint32_t c00, uint32_t c10, uint32_t c01, uint32_t c11, int a) {
  const uint64_t R = MIX_RECIP.v[a];
  const uint32_t r = mixCh(m00 * (c00 >> 11) + m10 * (c10 >> 11) + m01 * (c01 >> 11) + m11 * (c11 >> 11), R, 31);
  const uint32_t g = mixCh(m00 * ((c00 >> 5) & 63) + m10 * ((c10 >> 5) & 63) + m01 * ((c01 >> 5) & 63) + m11 * ((c11 >> 5) & 63), R, 63);
  const uint32_t b = mixCh(m00 * (c00 & 31) + m10 * (c10 & 31) + m01 * (c01 & 31) + m11 * (c11 & 31), R, 31);
  return (uint16_t)(r << 11 | g << 5 | b);
}
struct ShiftTap { int i, w1; };
static inline ShiftTap shiftTap(int d16, int w16, int k) {
  const int v = d16 * 256 + (w16 - d16) * k;
  ShiftTap t; t.i = v >> 12; t.w1 = ((v & 4095) + 8) >> 4;
  if (t.w1 == 256) { t.i++; t.w1 = 0; }
  return t;
}

// Cylinder warp of an independently warped mark (sim markWarp): |row offset from the axis| 0..1 -> the source's.
struct MarkWarp {
  float strength, signedCurve, exponent;
  MarkWarp(float lens, float curve = 1) {
    strength = fabsf(clampf(lens, -1, 1));
    signedCurve = lens < 0 ? -clampf(curve, -3, 3) : clampf(curve, -3, 3);
    exponent = signedCurve > 0 ? 1 + signedCurve * 2 : 1 / (1 - signedCurve * 2);
  }
  inline float at(float u) const { return signedCurve == 0 ? u : (1 - strength) * u + strength * powf(u, exponent); }
  float inv(float w) const {   // monotone on 0..1: bisection (sim markUnwarp)
    float lo = 0, hi = 1;
    for (int i = 0; i < 32; i++) { float m = (lo + hi) / 2; if (at(m) < w) lo = m; else hi = m; }
    return (lo + hi) / 2;
  }
};
static void markSourceRows(int height, float lens, int16_t *out, float curve = 1) {
  const MarkWarp warp(lens, curve);
  for (int yd = 0; yd < height; yd++) {
    float d = (yd + 0.5f - height / 2.0f) / (height / 2.0f);
    float s = (d < 0 ? -1 : 1) * warp.at(fabsf(d));
    out[yd] = (int16_t)clampf(ffloor(height / 2.0f + s * height / 2.0f), 0, height - 1);
  }
}
// markSourceRows before it is rounded to rows: the source's offset from the tube axis, in rows (sim
// markSourceOffsets); offsetRow = its markSourceRows row.
static void markSourceOffsets(int height, float lens, float *out) {
  const MarkWarp warp(lens);
  for (int yd = 0; yd < height; yd++) {
    float d = (yd + 0.5f - height / 2.0f) / (height / 2.0f);
    float s = (d < 0 ? -1 : 1) * warp.at(fabsf(d));
    out[yd] = s * height / 2.0f;
  }
}
static inline int offsetRow(int height, float off) { return (int)clampf(ffloor(height / 2.0f + off), 0, height - 1); }
// Vertical watch, rear ticks under rear digits: one wall, one axis across the tube, so the liquid moves both by
// the digits' remap (digitDryLens -> bottomLens) and a tick clear of a label behind air stays clear of it behind
// liquid, at every wet share (sim TickFollow; tickLens has no say).
static inline bool rearTicksFollowDigits(const Params &p) { return p.vertical && p.digits && !p.digitsOnTop && !p.ticksOnTop; }

static void digitRowColors(const Params &p, int bh, uint16_t *out) {
  int n = bh < 1 ? 1 : bh; if (n > 96) n = 96;
  RGB a = hexToRgb(p.digitColor), b = hexToRgb(p.digitColor2);
  for (int i = 0; i < n; i++) {
    float t = n == 1 ? 0 : (float)i / (n - 1); float u = t < 0.8f ? t / 0.8f : 1 - (t - 0.8f) / 0.2f * 0.35f;
    out[i] = q(scale(mix(a, b, u), p.brightness * p.digitBright));
  }
}

// Which column is behind liquid; edges null (digits on top) = all wet.
// Wet share of each panel column in 1/256 (sim wetShare): how many tube rows are liquid there (lo <= x < hi,
// Mark's own test) — 256 where every row is, 0 where none is, the meniscus in between. A rear mark takes that
// share of the liquid's refraction (source rows blended from the behind-air warp toward the behind-liquid one,
// parallax scaled), so the warp grows as the surface passes over it. Built by drawTube into its own Tube's
// table (Tube::wetShare, PSRAM from render_init): the two tubes render at the same time, one per core.
static void buildWetShare(const Edges &e, int H, uint16_t *share, int16_t *run) {
  memset(run, 0, (PANEL_W + 1) * sizeof(int16_t));
  for (int ry = 0; ry < H; ry++) {
    const int a = (int)fceil(clampf(e.lo[ry], 0, PANEL_W)), b = (int)fceil(clampf(e.hi[ry], 0, PANEL_W));
    if (b > a) { run[a]++; run[b]--; }
  }
  for (int x = 0, n = 0; x < PANEL_W; x++) { n += run[x]; share[x] = (uint16_t)((n * 256 + (H >> 1)) / H); }
}
// Source row for wet share k (1/256): the behind-air row moved toward the behind-liquid one.
static inline int blendRow(int dry, int wet, int k) { return dry + (((wet - dry) * k + 128) >> 8); }
// A column's wet share from its tube's table; null = 256 everywhere (digits on top).
struct Warp {
  const uint16_t *share;
  explicit Warp(const uint16_t *share_) : share(share_) {}
  bool all() const { return !share; }
  int operator()(int x) const { return !share ? 256 : x < 0 || x >= PANEL_W ? 0 : share[x]; }
};

// ---------------------------------------------------------------------------------------------
// per-tube render context
// ---------------------------------------------------------------------------------------------
// Bubbles per tube: FIZZ_POOL (layout.h). A count pushed past the sliders over serial (or a spring needing more) is
// capped and reported (fizzOverflow), not silently dropped.
static std::atomic<int> fizzOverflowPeak{0};   // largest count requested past FIZZ_POOL (0 = everything fitted), see fizzOverflow(); both cores step
static inline void atomicMax(std::atomic<int> &a, int v) { int c = a.load(std::memory_order_relaxed); while (v > c && !a.compare_exchange_weak(c, v, std::memory_order_relaxed)) {} }
// px in the liquid frame; v = size/speed factor, 0 = an idle slot (a spring's pool: not drawn, not moved);
// life != 0 = parked under a surface, |life| s left before it pops: > 0 under the time edge, < 0 under the home
// edge of a free slug.
struct Fizz { float x, y, v, life, z; };   // z: depth in the bore (0 front wall, 1 back), drawn at spawn and every recycle
// Foam constants (mirror sim/src/render.ts): pop swell + fade time, slide speed along the surface as a
// fraction of fizzSpeed per px/row of meniscus slope, lag rate behind an advancing surface (also how a caught
// bubble glides onto the surface), how far short of the profile a free bubble's rim is caught (or recycled, at
// a surface foam can't form on), how much a concave surface band veils the foam behind it at the profile.
#define FOAM_POP_T 0.3f
#define FOAM_SLIDE 0.5f
#define FOAM_FOLLOW 6.0f
#define FOAM_CATCH (2.0f * PX_SCALE_FIZZ)   // the liquid's px
#define FOAM_VEIL 0.7f
#define BLICK_H 0.18f   // surface blick tent half-height / tube height (sim BLICK_H)
#define FOAM_RELAX 3   // packing sweeps per step
// A spring is fixed in the tube (mirror sim/src/render.ts): fizzSourceX of the column as it sits at home. While the
// liquid covers it, it takes every birth, whatever the tilt; a free slug sliding off it leaves it dry, and every
// birth goes scattered. Covered again, it takes its births back over SPRING_BACK s (a share ramping to 0), so a
// slug bouncing at home does not flip the stream. Births only: nothing in flight moves.
// It emits at a steady cadence, fizzSourceRate bubbles/s, into idle slots of the pool (fizzCount does not apply):
// how many are in flight follows from their path, so a tilt that shortens it shows fewer.
// Glass holds the gas a spring's rise carries into it (fizzFoamLife > 0), so the stream bends along the glass
// instead of ending there: at the bore wall a bubble stays against the glass and slides along it with the along
// drive (one pace for all, so a train keeps its gaps) until it lets go — at random, on average after fizzFoamLife
// s, sooner when shaken — and slips behind the wall band; one arriving onto a bubble already held there coalesces
// into it. At a closed end (the tube's end glass, not a surface) it parks as foam does, slides along the glass
// with the across rise and pops after its life.
#define SPRING_BACK 3.0f

// Everything that depends only on (params, H): rebuilt when the generation counter moves.
struct RowCache {
  uint32_t gen = 0; int H = 0; bool valid = false;
  int16_t tickWet[TUBE_HEIGHT_MAX], tickDry[TUBE_HEIGHT_MAX];   // tick source-row warps
  bool tickFollow; float tickEdge[2][2];                         // sim TickFollow: on, and edge(h) per [minutes][major]
  int16_t lensSrc[TUBE_HEIGHT_MAX]; bool lensOn; bool lensPos;   // applyLens row map
  float mag[TUBE_HEIGHT_MAX];                                    // lensMagRows (fizz squash)
  int16_t capX0[TUBE_HEIGHT_MAX];                                // rounded-corner mask
  // edge profile terms (sim edgeCap): d = boreRow(row), u2 = d^2; boreR = bore radius (sim boreR)
  float rowD[TUBE_HEIGHT_MAX], rowU2[TUBE_HEIGHT_MAX], boreR;
  uint16_t hiC;                                                  // front-bright colour
  uint16_t lensC;                                                // concave surface stroke colour (sim lensC)
  uint16_t darkC;                                                // deep liquid colour (sim darkC): dark tone target, unlit stroke shade
  uint16_t toneC; int toneT;                                     // surfaceTone target colour and blend 1/256 (sim toneC/toneK)
};
// One end's meniscus for this frame (sim CapShape): cosT = cos of its contact angle (> 0 concave), h = px
// its contact ring leads the surface centre, asym = across sag, cap = wobble, k = short-column scale.
struct CapShape { float cosT, h, asym, cap, k; };
// Edge-effect blend tables: (row, k) -> 565, a function of the palette and lightK only. Rebuilt when
// lightK moves (exact compare: at rest it is constant, in motion it changes every frame anyway).
#define EFFECT_MAX 16
struct EffectTable { uint32_t gen = 0; int H = 0; float lightK = -1; bool valid = false; uint16_t c[TUBE_HEIGHT_MAX * EFFECT_MAX]; };

// Per-row facts of the rear-mark compositors, the same for every glyph / tick of the layer (markRowFacts): the row's
// liquid interval [Li, Hi) (empty when Hi <= Li) and where the surface band may touch it, nb footprints [b0, b1),
// sorted (a conservative superset of Mark::bandMark's own test: the per-pixel compositor runs there). depth and tm:
// the ticks' lens depth of the row and TickMemo (drawTicks), unused by the digits.
// TickMemo, per row and kind (0 behind air or on top, 1 behind liquid): what one tick row (drawTicks) writes over a
// pixel behind `raw` (strip layout) for tick colour c and edge share fT (0: a plot row, see tickRow), per column:
// o[0] x - 1, o[1] x, o[2] x + 1 .. x + w - 1, o[3] x + w, o[4] x + w + 1 (strip layout). fT -1: empty.
struct TickMemo { uint16_t raw, c; int16_t fT; uint16_t o[5]; };
struct DigitRow { int Li, Hi, nb, b0[2], b1[2]; float depth; TickMemo tm[2]; };
static_assert(sizeof(DigitRow) == 64, "a DigitRow fills one 64-B cache line (render_init aligns the table)");

#ifdef TICK_PROF
// -DTICK_PROF tick counters per tube (render_tick_profile; main prints them in `f`, per frame): frames; cycles of the
// layer, its row facts (+ depth table), tick row ranges, tickRow calls (with their strip line fills), pixels through
// the per-pixel compositor; tick rows (all, wholly behind air / behind liquid / pixel by pixel), memo fills, per-pixel
// compositor pixels, segments, ticks; cycles of the memo fills (part of the tickRow calls).
enum { TP_FRAMES, TP_CYC, TP_CYC_FACTS, TP_CYC_RANGE, TP_CYC_ROWS, TP_CYC_GEN, TP_ROWS, TP_ROW_DRY, TP_ROW_WET, TP_ROW_MIX,
       TP_FILLS, TP_PX_GEN, TP_SEGS, TP_TICKS, TP_CYC_FILLS, TP_N };
#endif
#ifdef TUBE_PROF
// -DTUBE_PROF drawTube stage cycles per tube (render_tube_profile; main prints them in `f`, per frame): frames; the
// whole render call; palette + row cache (renderTube); edges + tube back; residue prep (blur), residue rows; nose
// backing; body + soft ramps; 3a; 3b; 3c; 4; 3e band; bounds / mirror / wet share; label layout; rear ticks; rear
// digits; fizz; bubble + top marks + lens. TU_TR*: residue rows split (fill, shear, zone); TU_RAMP the soft ramps
// (part of the body), TU_BANDK the 3e kernel (part of the band), TU_PALB / TU_PALP band rows / buildPalette (part of pal),
// TU_HASH the tiles' change records (tileHashes).
enum { TU_FRAMES, TU_ALL, TU_PAL, TU_BACK, TU_TRPREP, TU_TRROWS, TU_BACKING, TU_BODY, TU_FRONT, TU_GLOW, TU_FILM, TU_INSET,
       TU_BAND, TU_BOUNDS, TU_LABELS, TU_TICKS, TU_DIGITS, TU_FIZZ, TU_TOP, TU_TRFILL, TU_TRSHEAR, TU_TRZONE, TU_RAMP, TU_BANDK, TU_PALB, TU_PALP, TU_TILE, TU_HASH, TU_N };
#define TU_T0() uint32_t tuT = esp_cpu_get_cycle_count()
#define TU_MARK(i) do { const uint32_t tuN = esp_cpu_get_cycle_count(); tubeProf[i] += tuN - tuT; tuT = tuN; } while (0)
#define TU_SUB0(v) const uint32_t v = esp_cpu_get_cycle_count()
#define TU_SUB(i, v) (tubeProf[i] += esp_cpu_get_cycle_count() - (v))
#else
#define TU_T0()
#define TU_MARK(i) ((void)0)
#define TU_SUB0(v)
#define TU_SUB(i, v) ((void)0)
#endif
#ifdef TUBE_VERIFY
// -DTUBE_VERIFY (LCD board, off by default): the step-5 code of the step-6 float-path changes runs next to the new
// code and the results are compared bitwise (render_tube_verify; main prints them in `f`): TV_ZONE residue row
// columns (fill + shear calls and the old inline zone loop on a row copy: covers the thin-row skips too), TV_PAL
// palette entries (the old buildPalette).
enum { TV_ZONE, TV_PAL, TV_BAND, TV_TRACE, TV_RAMP, TV_N };
static volatile uint32_t tubeVerifyN[2][TV_N], tubeVerifyBad[2][TV_N];   // per core
static inline void tubeVerify(int k, int n, int bad) { const int c = esp_cpu_get_core_id() & 1; tubeVerifyN[c][k] += n; tubeVerifyBad[c][k] += bad; }
void render_tube_verify(int k, uint32_t &n, uint32_t &bad) { n = tubeVerifyN[0][k] + tubeVerifyN[1][k]; bad = tubeVerifyBad[0][k] + tubeVerifyBad[1][k]; }
#endif
#if TILE_RENDER && defined(TILE_VERIFY)
static volatile uint32_t tileVerifyN[2], tileVerifyBad[2];   // per core
static inline void tileVerify(uint32_t n, uint32_t bad) { const int c = esp_cpu_get_core_id() & 1; tileVerifyN[c] += n; tileVerifyBad[c] += bad; }
void render_tile_verify(uint32_t &n, uint32_t &bad) { n = tileVerifyN[0] + tileVerifyN[1]; bad = tileVerifyBad[0] + tileVerifyBad[1]; }
#endif
// Step 5: what every bubble of one tube shares in a frame (drawTube -> planBubble).
struct FizzFrame {
  const float *mag;                    // lensMagRows (fizz squash)
  float yHi, invHalfH, lxSign;         // highlight row, 2 / H, light x sign (mirrored liquid frame)
  float veilA, pullR, pullL;           // surface band veil opacity, receding pulls
  int xsI, L; uint16_t blickC; bool mir;
};
struct MarkPlan;   // step 9, after the mark kernels
// All mutable state of one tube's renderer (hours = tubes[0], minutes = tubes[1], seconds = *tubeS: tubeAt). Two of
// these are static (fixed footprint, ~9 KB each), the seconds tube's in PSRAM (render_init); the strip pointer / geometry
// are set per call by renderTube. Nothing here is shared between the tubes, so they can render concurrently on both
// cores. lane: the scratch the render borrows per core (tiles.h slots and copy channel): hours 0, minutes and seconds 1
// (one after the other on core 1, main renderBoth), so tube identity (idx: px scale, residue streak) and lane differ.
struct Tube {
  uint16_t *FB = nullptr; int baseY = 0, H = TUBE_HEIGHT_PX; int idx = 0;
#if TUBE_COUNT == 3
  int lane = 0;
#else
  static constexpr int lane = -1;   // unused: two tubes, the lane is idx (laneOf)
#endif
  inline int laneOf() const { return TUBE_COUNT == 3 ? lane : idx; }
  const int16_t **lensRowsOut = nullptr;   // set by renderTube: hand the lens row map to the caller instead of applying it
  Palette pal; RowCache rc; Labels labels; ScaledSet set;
  PalCache *palCache = nullptr;   // PSRAM, render_init
  TraceMemo *traceMemo = nullptr; // PSRAM, render_init
  float *traceStreakTab = nullptr; // traceStreak(x + idx 6151) per column, TUBE_LENGTH_PX, PSRAM, render_init
#ifdef TUBE_VERIFY
  uint16_t *verifyRow = nullptr;  // PANEL_W, PSRAM, render_init
  Palette *verifyPal = nullptr;   // PSRAM, render_init
  float glassWRef(const Params &p, int y, int hiTop, float lam) const;
  void buildPaletteRef(const Params &p, float lightDeg, Palette &pal) const;
#endif
#ifdef TICK_PROF
  mutable uint32_t tickProf[TP_N] = {};   // -DTICK_PROF: accumulated until render_tick_profile_reset
#endif
#ifdef FIZZ_PROF
  uint32_t fizzProf[FZ_N] = {};           // -DFIZZ_PROF: accumulated until render_fizz_profile_reset
#endif
#ifdef TUBE_PROF
  uint32_t tubeProf[TU_N] = {};           // -DTUBE_PROF: accumulated until render_tube_profile_reset
#endif
#ifdef DIGIT_PROF
  // slow (band) px / cycles stay 0 since step 8 of the LCD perf plan (no band over sprite digits); frac px count the
  // sub-pixel parallax runs (rear parallax, 2026-11-06)
  mutable uint32_t prof[11] = {};     // per frame: glyphs, rows, int px plain, int px liquid, frac px plain, frac px liquid, slow px, runs; us: layoutLabels, rear ticks, rear digits
  mutable uint32_t profCyc[3] = {};   // CPU cycles: plain runs, band (slow) runs, ramp columns
#endif
#ifdef BOARD_LCD316
  EffectTable *glowT = nullptr;   // [2], PSRAM, render_init: 6.8 KB a tube of internal RAM on the LCD (step 7: the tiles'
                                  // room), and only the hard-edge glow (edgeSoft 0, no residue) reads it
#else
  EffectTable glowT[2];                                       // 0 = time edge, 1 = home edge
#endif
#if TILE_RENDER && defined(TILE_VERIFY)
  uint16_t *tileVerifyStrip = nullptr;   // TUBE_HEIGHT_MAX x PANEL_W, PSRAM, render_init (-DTILE_VERIFY)
#endif
  float edges[TUBE_HEIGHT_MAX], edgesL[TUBE_HEIGHT_MAX];      // render-frame liquid edges per row
  // rear-mark wet share per panel column (buildWetShare) + its scratch: PANEL_W / PANEL_W + 1 entries, PSRAM,
  // allocated once by render_init (internal RAM is ~2.7 KB from full once BLE is up; 4.3 KB here hung its init)
  uint16_t *wetShare = nullptr; int16_t *wetRun = nullptr;
  // digit source offset from the axis per row behind air, then behind liquid (sim TickFollow dry / wet):
  // 2 x TUBE_HEIGHT_MAX, PSRAM, allocated once by render_init
  float *digitOff = nullptr;
  DigitRow *digitRows = nullptr;   // TUBE_HEIGHT_MAX, PSRAM, allocated once by render_init (spriteRowFacts, tickBand)
  float boundLo[TUBE_HEIGHT_MAX], boundHi[TUBE_HEIGHT_MAX];   // panel-frame bounds for the mark compositor (edges + surface stroke)
  float strokeR[TUBE_HEIGHT_MAX], strokeL[TUBE_HEIGHT_MAX];   // outward extent of the concave surface stroke per edge (sim strokeR/L)
  float bandFill[2][TUBE_HEIGHT_MAX], bandBlick[2][TUBE_HEIGHT_MAX], bandRim[2][TUBE_HEIGHT_MAX];   // its layer weights per row, 0 = time edge, 1 = home: rear-mark compositor (sim BandInfo)
  uint16_t backR[TUBE_HEIGHT_MAX], backL[TUBE_HEIGHT_MAX];    // local backing past each edge before body/glow: convex nose (sim backR/L)
  Fizz *fizz = nullptr; int fizzN = 0; float fizzLen = 0;     // fizz: FIZZ_POOL slots, PSRAM, render_init; fizzLen: liquid length px, set by drawTube
  float fizzSurf[TUBE_HEIGHT_MAX], fizzSurfL[TUBE_HEIGHT_MAX]; // liquid-frame surface front per row (profile = edges - xs, the inner rim of a surface band), time / home edge, set by drawTube: where foam parks
  uint8_t fizzExposed = 0;                                    // bit 1 = time edge short of the far end, bit 2 = home edge of a free slug off the near end
  float fizzShift = 0;                                        // px the liquid frame sits off its home (a free slug that slid away; 0 pinned), set by drawTube
  float springScatter = 0;                                    // share of spring births born scattered instead (0 = all at the spring), advanced by stepFizz
  float springClock = 0;                                      // bubbles the spring may release now (its cadence accrued)
  struct FoamWork *foam = nullptr;                            // stepFizz / settleFoam work space (sweep order kept between steps, grid), PSRAM, render_init
  struct FizzLook *look = nullptr;                            // the fizz's size classes and depth-level colours (planFizz), PSRAM, render_init
  uint16_t traceA[TUBE_LENGTH_PX];                            // dried-trace residue depth per column, 1/256 with headroom (traceAmount > 1)
  uint16_t traceRaw[TUBE_LENGTH_PX];                          // render-frame residue copy, input to the taper blur
  uint16_t *traceLut = nullptr;                               // traceFillRow's per-row colour table, TRACE_LUT entries (one per tube: both cores render), PSRAM, render_init
  MarkPlan *plan = nullptr;                                   // the marks' per-frame plans (step 9), PSRAM, render_init
#if DIGIT_PIE
  FracMemo *fracMemo = nullptr;                               // the digits' last fractional run (spriteRunFracPie), PSRAM, render_init
#endif
  DigitScratch *scratch = nullptr;                            // the digit kernels' lanes and rows (16-B aligned), render_init: internal (LCD fast mode) / PSRAM
  // The fizz's per-frame constants (planFizz, read per bubble row): surface band veil opacity, receding pulls,
  // fizzBlick, the mirrored liquid frame's x map; per row the veil bounds (DiscRow veilLo / veilHi).
  float fzVeilA = 0, fzPullR = 0, fzPullL = 0, fzBlickK = 0; int fzXsI = 0, fzL = 0; bool fzMir = false;   // per row: FizzLook veilLo / veilHi
  // Panel rows [rowLo, rowHi) the pixel helpers may touch (inStrip, hspan): the strip, or the band being drawn (step 9:
  // the marks run band by band, each stage clipped to the band's rows; on the tiled LCD the band is a tile slot).
  int rowLo = 0, rowHi = 0;
#if TILE_RENDER
  // Strips the tube's last renders wrote by DMA only (tile_strip_clean), one entry per strip buffer: the three-tube LCD
  // pushes one strip while the other core renders the tube into its other one, so a render never writes the entry the
  // push of the other strip reads (both directions of a lost update only cost a writeback). Else null.
  const uint16_t *volatile cleanStrip[2] = {nullptr, nullptr};
  // Change records (tiles.h TileDirty): per tile and column pair the hash of the last render that hashed its tiles
  // (TILE_MAX x TILE_PAIRS, PSRAM), the rows that render had (-1: no valid table); one record per strip buffer (PSRAM).
  // All allocated by render_init. renderSeq counts every render of the tube.
  uint32_t *tileHash = nullptr; int hashH = -1; uint32_t renderSeq = 0;
  TileDirty *dirty[2] = {nullptr, nullptr};
  TileDirty *dirtyFor(const uint16_t *strip) {   // strip's record; a strip without one takes a free entry, else the first
    const int e = dirty[0]->strip == strip ? 0 : dirty[1]->strip == strip ? 1 : !dirty[0]->strip || dirty[1]->strip ? 0 : 1;
    dirty[e]->strip = strip;
    return dirty[e];
  }
#endif

  inline bool inStrip(int x, int y) const { return x >= 0 && x < PANEL_W && y >= rowLo && y < rowHi; }
  inline uint16_t rd(int x, int y) const { TCLIP(FB + (y - baseY) * PANEL_W + x, 1); return __builtin_bswap16(FB[(y - baseY) * PANEL_W + x]); }
  inline void wr(int x, int y, uint16_t c) const { TCLIP(FB + (y - baseY) * PANEL_W + x, 1); FB[(y - baseY) * PANEL_W + x] = __builtin_bswap16(c); }
  void hspan(int y, int x0, int x1, uint16_t c) const {
    if (y < rowLo || y >= rowHi) return;
    if (x0 < 0) x0 = 0; if (x1 > PANEL_W) x1 = PANEL_W;
    if (x1 <= x0) return;
    uint16_t s = __builtin_bswap16(c);
    uint16_t *p = FB + (y - baseY) * PANEL_W + x0;
    TCLIP(p, x1 - x0);
    int n = x1 - x0;
    if (((uintptr_t)p & 2) && n) { *p++ = s; n--; }
    uint32_t ss = (uint32_t)s | ((uint32_t)s << 16);
    uint32_t *p32 = (uint32_t *)p;
    for (; n >= 2; n -= 2) *p32++ = ss;
    if (n) *(uint16_t *)p32 = s;
  }
  inline void px(int x, int y, uint16_t c) const { if (inStrip(x, y)) wr(x, y, c); }
  inline void pxa(int x, int y, uint16_t c, float t) const {
    if (!inStrip(x, y)) return;
    wr(x, y, t >= 1 ? c : blend565(rd(x, y), c, t));
  }
  inline void pxaT(int x, int y, uint16_t c, int T) const {
    if (!inStrip(x, y)) return;
    wr(x, y, T >= 256 ? c : blend565T(rd(x, y), c, T));
  }

  float glassW(const Params &p, int y, int hiTop, float lam, const PalCache &pc) const;
  int highlightTop(const Params &p, float lightDeg) const;
  void buildPalCache(const Params &p, uint32_t gen, PalCache &pc) const;
  void buildBandRows(PalCache &pc) const;
  void buildPalette(const Params &p, float lightDeg, Palette &pal, const PalCache &pc) const;
  ScaledGlyph *scaledGlyphs(int sheetIdx, int bw, int bh, float brightness, uint32_t tintHex, float tintAmt, float tone, int shadow, float shadowA, int shadowOff, float transK, bool rot, float floorC, uint16_t floorR);
  bool layoutLabels(int y0, const Params &p, uint32_t gen, int ticksN, const TubeState &st, float fill, Labels &lb);
  void spriteRowFacts(int y0, const Labels &lb, const Mark &mark, int r0, int r1) const;
  void spriteGlyphRows(const struct GlyphPlan &gp, int y0, const Labels &lb, const Warp &warp, const Mark &mark, int r0, int r1) const;
  // Step 9: the marks planned once a frame (planTicks / planLabels / planFizz, before the band loop: they read no
  // pixel), then drawn band by band (tickBand / labelBand / fizzBand: rows [r0, r1) only, r0 a band's first row and r1
  // its end, or the whole tube [0, H)). Per pixel the ops and their order are the frame-at-once draw's.
  bool planTicks(int y0, const Params &p, int ticksN, const int16_t *wetRows, const int16_t *dryRows,
                 const Edges *edges, const Mark &mark, float dxFull = 0, float dyFull = 0) const;
  void tickBand(int y0, const Mark &mark, int r0, int r1) const;
  void planLabels(const Labels &lb, const Warp &warp, int y0) const;
  void labelBand(int y0, const Labels &lb, const Warp &warp, const Mark &mark, bool rowFacts, int r0, int r1) const;
  void planFizz(const Params &p, const FizzFrame &ff);
  void fizzBand(int r0, int r1);
  void planBubble(const Fizz &f, const Params &p, const FizzFrame &ff, struct BubblePlan &b);
  void bubbleRows(const struct BubblePlan &b, int r0, int r1);
  void discOf(const struct BubblePlan &b, DiscRow &d) const;
  inline void discRowOf(const struct BubblePlan &b, DiscRow &d, int iy, float wallT, float dy);
  void maskRows(const struct BubblePlan &b, int iy0, int iy1);
  void ensureFizz(const Params &p, float len, float agitation);
  inline float fizzSquashRow(const Params &p, int y) const;
  void lensMagRows(const Params &p, float *rows) const;
  CapShape capShape(const Params &p, float len, float tilt, float side, float cap, float pin, float lineV) const;
  inline float edgeCap(int ry, const CapShape &c) const;
  inline float wallCap(int ry, const CapShape &c) const;
  inline float wallX(int ry, float xe, float tanA, const CapShape &c) const;
  inline float wallXL(int ry, float xs, float tanA, const CapShape &c) const;
  inline float edgeX(int ry, float xe, float tanA, const CapShape &c) const;
  inline float edgeXL(int ry, float xs, float tanA, const CapShape &c) const;
  void buildRowCache(const Params &p, uint32_t gen);
  void applyLens(const Params &p);
  const uint16_t *effectTable(EffectTable &T, const Params &p, const Palette &pal, uint32_t gen, float lightK, bool glow) const;
  void drawTube(int y0, const TubeState &st, const Params &p, uint32_t gen, int ticksN);
  void traceBlur(const uint16_t *trace, bool mir, int a0, int a1, int c0, int c1, float filmV, int &aLo, int &aHi);
};
static Tube tubes[2];
#if TUBE_COUNT == 3
static Tube *tubeS = nullptr;   // the seconds tube (~16 KB at 10-8-6): internal in fast mode, else PSRAM (render_init)
static inline Tube &tubeAt(int idx) { return idx == 2 ? *tubeS : tubes[idx & 1]; }
#else
static inline Tube &tubeAt(int idx) { return tubes[idx & 1]; }
#endif
#define TUBE_LANE(idx) ((idx) ? 1 : 0)   // the scratch lane of tube idx (Tube::lane)

inline void Mark::operator()(int x, int y, uint16_t c, int covT, int rel) const {
#ifdef TICK_PROF
  if (prof) { profPixel(x, y, c, covT, rel); return; }
#endif
  if (!t.inStrip(x, y)) return;
  int ry = y - y0;
  const bool inside = !onTop && x >= edges.lo[ry] && x < edges.hi[ry];
  if (!onTop && edges.band && bandMark(x, y, ry, c, covT, rel, inside)) return;
  if (inside) {
    c = wetColour(t.rd(x, y), c, covT);
    if (rel) { covT = covT * T >> 8; if (covT <= 0) return; }   // rear relief fades with the liquid's opacity (sim markFn)
  } else if (!onTop) { covT = covT * t.pal.dryT[ry] >> 8; if (covT <= 0) return; }   // rear marks vanish behind the wall band
  if (rel > 0) c = embossHi(c);
  else if (rel < 0) c = embossLo(c);
  t.wr(x, y, covT >= 256 ? c : blend565T(t.rd(x, y), c, covT));
}
#ifdef TICK_PROF
// A tick pixel through the per-pixel compositor (band footprints, rows across the liquid's edge), timed.
void __attribute__((noinline)) Mark::profPixel(int x, int y, uint16_t c, int covT, int rel) const {
  const uint32_t c0 = esp_cpu_get_cycle_count();
  Mark m = *this; m.prof = nullptr;
  m(x, y, c, covT, rel);
  prof[TP_CYC_GEN] += esp_cpu_get_cycle_count() - c0; prof[TP_PX_GEN]++;
}
#endif
// The concave surface band's footprint at a rear-mark pixel — it overlaps the body by hw inside the profile:
// its rim and blick stay on top of the mark (the write is scaled by what they let through; approximation as
// in the sim: the layers' own colour also yields by that share). Past the body the rear wall is seen through
// the dish: the mark is liquid-tinted as far as the fill is opaque there (its own per-pixel opacity, no
// threshold), dry for the rest; the band's plane is the behind-air one, so the coverage never has the
// transparency baked in and the wet part applies it itself. The wet/dry colour mix and the blend over the
// pixel are taken in 888 and rounded ONCE (parity with the sim). Out of the hot operator (noinline): the
// divisions run only on the few mark pixels under a band.
bool __attribute__((noinline)) Mark::bandMark(int x, int y, int ry, uint16_t c, int covT, int rel, bool inside) const {
  const BandInfo &b = *edges.band;
  const int xr = b.mirror ? b.L - 1 - x : x;
  const float hw = b.hw;
  // the edge whose footprint (hw inside the profile to the stroke width past it) can hold this pixel
  const int side = xr + 0.5f > b.xm[0][ry] - hw ? 0 : 1;
  const float wEff = b.w[side][ry];   // 0: no band on that side; a far pixel gets no coverage below
  if (wEff <= 0) return false;
  const float tt = (side == 0 ? 1 : -1) * (xr + 0.5f - b.xm[side][ry]);
  const float lo = fmx(tt - 0.5f, -hw), hi = fmn(tt + 0.5f, wEff), coverage = hi - lo;
  if (coverage <= 0) return false;
  const float u = clampf(((lo + hi) * 0.5f + hw) / (wEff + hw), 0, 1), us = u * u * (3 - 2 * u);
  const float ab = fmn(1, b.blick[side][ry] * coverage * 4 * u * (1 - u));
  const float ar = fmn(1, b.rim[side][ry] * fmx(0, hi - fmx(lo, fmx(0, wEff - 1))));
  const float through = (1 - ab) * (1 - ar);
  if (inside) {
    if (through >= 1) return false;   // nothing on top here: the plain body path, byte-identical
    c = wetColour(t.rd(x, y), c, covT);
    if (rel) covT = covT * T >> 8;
    covT = (int)(covT * through + 0.5f); if (covT <= 0) return true;
    if (rel > 0) c = embossHi(c); else if (rel < 0) c = embossLo(c);
    t.wr(x, y, covT >= 256 ? c : blend565T(t.rd(x, y), c, covT));
    return true;
  }
  const float wet = fmn(1, b.fill[side][ry] * coverage * (1 - b.pull[side] * us));
  const float cov = covT * (1 / 256.0f);
  const float aw = cov * wet * (rel ? T * (1 / 256.0f) : 1), ad = cov * (1 - wet) * (t.pal.dryT[ry] * (1 / 256.0f));
  const float al = (aw + ad) * through;
  if (al < 1 / 255.0f) return true;
  const uint16_t bg = t.rd(x, y);
  RGB M = to888(c);
  if (aw > 0) {
    const RGB CT = to888(throughLiquid(bg, c, T, C));
    M = ad > 0 ? mix(M, CT, aw / (aw + ad)) : CT;
  }
  if (rel > 0) M = to888(embossHi(q(M))); else if (rel < 0) M = to888(embossLo(q(M)));
  t.wr(x, y, al >= 1 ? q(M) : q(mix(to888(bg), M, al)));
  return true;
}

// Glass wall shading weight 0..1 per row (sim: glassW): ambient cylinder shade, specular tent on the
// top wall, faint band on the lower wall. The wall band and rim live in buildPalette.
float Tube::glassW(const Params &p, int y, int hiTop, float lam, const PalCache &pc) const {   // pc: valid for this (gen, H)
  float amb = 0.5f + 0.5f * pc.ambCos[y];
  float w = p.glassBody * (amb + (lam - amb) * p.lightPhys);
  if (y >= hiTop && y < hiTop + p.highlightH)
    w += p.glassHiBright * powf(1 - fabsf((y - hiTop) / fmx(1, p.highlightH - 1) - 0.5f) * 2, p.highlightSharp);
  w += p.glassReflect * pc.reflExp[y];
  return fmn(1, w);
}
// The 3e band's per-row colours (PalCache), after buildPalette and buildRowCache: the expressions drawTube's surface()
// evaluated per row and edge.
void Tube::buildBandRows(PalCache &pc) const {
  auto tone = [&](uint16_t c) -> uint16_t { return rc.toneT > 0 ? blend565T(c, rc.toneC, rc.toneT) : c; };
  // A row's four colours are a function of its palette row and back row and rc (keyed on the same (gen, H) as pc).
  for (int ry = 0; ry < H; ry++) {
    if (pc.bandValid && pc.bandKeyRow[ry] == pal.rows[ry] && pc.bandKeyBack[ry] == pal.tubeBackRows[ry]) continue;
    pc.bandKeyRow[ry] = pal.rows[ry]; pc.bandKeyBack[ry] = pal.tubeBackRows[ry];
    pc.bandInner[ry] = tone(blend565(pal.rows[ry], rc.darkC, 0.3f));
    pc.bandLensMix[ry] = blend565(rc.lensC, pal.rows[ry], 0.2f);
    pc.bandBackK[ry] = fmn(1, luma(to888(pal.tubeBackRows[ry])) / 255.0f);
    pc.bandRimC[ry] = q(mix(to888(rc.hiC), to888(q(mix(to888(pal.rows[ry]), to888(rc.darkC), 0.75f))), pc.bandBackK[ry]));
  }
  pc.bandValid = true;
}
// Contents index the palette's thin-edge chord refracts by (water; params carry no index). Sim THIN_IOR.
static constexpr float THIN_IOR = 1.333f;
// Fill pc for (p, H): the same calls on the same arguments as buildPalette / glassW made inline.
void Tube::buildPalCache(const Params &p, uint32_t gen, PalCache &pc) const {
  if (pc.valid && pc.gen == gen && pc.H == H) return;
  pc.valid = true; pc.gen = gen; pc.H = H; pc.bandValid = false;
  const float yc = (H - 1) / 2.0f, wallU = 1 - 2 * fmx(1, p.glassWall) / H;
  // sim buildPalette thinK: the refracted chord √(1 − (u·R/(n·r))²), floored by the wall
  const float thinK = 1 / (THIN_IOR * fmx(1e-3f, 1 - 2 * fmx(0, p.glassWall) / H));
  for (int y = 0; y < H; y++) {
    const float t = (float)y / (H - 1);
    const float u = (y + 0.5f - H / 2.0f) / (H / 2.0f), au = fabsf(u);
    pc.u[y] = u;
    pc.rimPow[y] = powf(fmx(0, (au - wallU) / (1 - wallU)), 2.5f);
    pc.dryExp[y] = p.glassWall <= 0 || au >= wallU ? 0 : expf(-(wallU - au) / 0.04f);
    pc.asinY[y] = asinf(clampf((yc - y) / yc, -1, 1));
    const float ku = u * thinK;
    pc.chord[y] = p.liquidThin > 0 ? sqrtf(fmx(0, 1 - ku * ku)) : 0;
    pc.ambCos[y] = cosf((t - 0.3f) * (float)M_PI * 1.6f);
    const float d = (t - 0.82f) / 0.07f;
    pc.reflExp[y] = expf(-d * d);
  }
  const float wet = clampf(p.wallWet, 0, 1);
  // sim liqU / liqT: the contents fill the share wallWet of the band; past their edge the empty tube's row
  const float liqU = wallU + wet * (1 - wallU);
  RGB body = hexToRgb(p.liquid), lo = hexToRgb(p.liquidLo), tubeBack = hexToRgb(p.tubeBack), tubeBack2 = hexToRgb(p.tubeBack2);
  for (int y = 0; y < H; y++) {   // buildPalette's loop, its light-independent part
    float t = (float)y / (H - 1);
    float u = (y + 0.5f - H / 2.0f) / (H / 2.0f), au = fabsf(u);
    float rim = p.glassRim * pc.rimPow[y];
    float glow = p.glassWallGlow * clampf(0.4f + 3 * (au - wallU) / (1 - wallU), 0, 1);
    pc.wall[y] = glow + rim - glow * rim;
    const float gW = glow * (1 - wet); pc.wetRim[y] = gW + rim - gW * rim;
    pc.dryT[y] = p.glassWall <= 0 ? 1 : au >= wallU ? 0 : 1 - pc.dryExp[y];
    pc.liqDry[y] = p.glassWall <= 0 ? 0 : au >= liqU ? 1 : expf(-(liqU - au) / 0.04f);
    int gradient = (int)jround(p.tubeBackGradient);
    float backMix = gradient == 1 ? t : gradient == 2 ? 1 - fabsf(t * 2 - 1)
      : gradient == 3 ? fabsf(t * 2 - 1) : 0;
    pc.back[y] = mix(tubeBack, tubeBack2, backMix);
    RGB c;
    if (t < 0.33f) c = mix(mix(body, lo, 0.25f), body, t / 0.33f);
    else c = mix(body, lo, ((t - 0.33f) / 0.67f) * p.shadeDepth);
    pc.c0[y] = c;
  }
}

// Top row of the highlight band for highlight angle lightDeg (sim highlightTop).
int Tube::highlightTop(const Params &p, float lightDeg) const {
  float yc = (H - 1) / 2.0f;
  return (int)jround(yc - yc * sinf(lightDeg * (float)M_PI / 180) - (p.highlightH - 1) / 2);
}

#ifdef TUBE_VERIFY
// The step-5 palette code, verbatim (TUBE_VERIFY).
float Tube::glassWRef(const Params &p, int y, int hiTop, float lam) const {
  float t = (float)y / (H - 1);
  float amb = 0.5f + 0.5f * cosf((t - 0.3f) * (float)M_PI * 1.6f);
  float w = p.glassBody * (amb + (lam - amb) * p.lightPhys);
  if (y >= hiTop && y < hiTop + p.highlightH)
    w += p.glassHiBright * powf(1 - fabsf((y - hiTop) / fmx(1, p.highlightH - 1) - 0.5f) * 2, p.highlightSharp);
  float d = (t - 0.82f) / 0.07f;
  w += p.glassReflect * expf(-d * d);
  return fmn(1, w);
}
void Tube::buildPaletteRef(const Params &p, float lightDeg, Palette &pal) const {
  RGB body = hexToRgb(p.liquid), hi = hexToRgb(p.liquidHi), lo = hexToRgb(p.liquidLo);
  RGB tubeBack = hexToRgb(p.tubeBack), tubeBack2 = hexToRgb(p.tubeBack2), ghi = hexToRgb(p.glassHi);
  float br = p.brightness * p.liquidBright;
  RGB liquidHiScaled = scale(hi, br), glassHiScaled = scale(ghi, p.brightness);
  const RGB rimTint = scale(hexToRgb(p.rimTint), p.brightness);
  float bodyL = ambientBodyL(p), ambAmt = ambientAmt(p);
  float yc = (H - 1) / 2.0f, lightRad = 2 * lightDeg * (float)M_PI / 180;
  int hiTop = highlightTop(p, lightDeg);
  const RGB rimC = hexToRgb(p.bubbleRim);
  const RGB rimLit = { fmn(255, rimC.r * br), fmn(255, rimC.g * br), fmn(255, rimC.b * br) };   // clipped lit rim (sim rimLit)
  float rowL[TUBE_HEIGHT_MAX];   // per-row body-shading luma (fixed-size local, sim rowL)
  // Wall band (sim buildPalette): rows whose ray misses the bore never reach the back (dryT 0),
  // ramping up over a few rows inside; the liquid still shows through there. A neutral grazing
  // rim rises toward the silhouette on both sides (glassRim). glassWall 0 keeps a one-row rim.
  float wallU = 1 - 2 * fmx(1, p.glassWall) / H;
  RGB glassEdge = scale(mix(ghi, {180, 190, 195}, 0.72f), p.brightness);
  const float wet = clampf(p.wallWet, 0, 1);   // sim: a gas (0) keeps the glow and the empty tube's band over its column
  const float liqU = wallU + wet * (1 - wallU);   // sim liqU: the contents' edge
  const float thinK = 1 / (THIN_IOR * fmx(1e-3f, 1 - 2 * fmx(0, p.glassWall) / H));   // sim thinK
  for (int y = 0; y < H; y++) {
    float t = (float)y / (H - 1);
    float u = (y + 0.5f - H / 2.0f) / (H / 2.0f), au = fabsf(u);
    float rim = p.glassRim * powf(fmx(0, (au - wallU) / (1 - wallU)), 2.5f);
    // Wall glow (sim glowW/wallW): light piped along the wall lights the band itself; plateau with a
    // short ramp starting just inside the band, the grazing rim on top. Dry glass only, as far as the contents
    // wet the wall (wallWet): a liquid frustrates the internal reflection and fills the band (rim alone over it).
    float glow = p.glassWallGlow * clampf(0.4f + 3 * (au - wallU) / (1 - wallU), 0, 1);
    const float wall = glow + rim - glow * rim;
    const float gW = glow * (1 - wet), wetRim = gW + rim - gW * rim;   // over the contents: the glow they leave piped, the rim
    float dryT = p.glassWall <= 0 ? 1 : au >= wallU ? 0 : 1 - expf(-(wallU - au) / 0.04f);
    pal.dryT[y] = (uint16_t)(dryT * 256 + 0.5f);
    int gradient = (int)jround(p.tubeBackGradient);
    float backMix = gradient == 1 ? t : gradient == 2 ? 1 - fabsf(t * 2 - 1)
      : gradient == 3 ? fabsf(t * 2 - 1) : 0;
    RGB back = mix(tubeBack, tubeBack2, backMix);
    float lam = fmx(0, cosf(asinf(clampf((yc - y) / yc, -1, 1)) - lightRad));
    RGB c;
    if (t < 0.33f) c = mix(mix(body, lo, 0.25f), body, t / 0.33f);
    else c = mix(body, lo, ((t - 0.33f) / 0.67f) * p.shadeDepth);
    if (p.lightPhys > 0) c = mix(c, mix(lo, body, 1 - p.shadeDepth * (1 - lam)), p.lightPhys);
    // Thin edge: shorter chord toward the walls absorbs less, the colour drifts to a grey of its
    // own peak channel, strongest on the outermost rows.
    if (p.liquidThin > 0) {
      float ku = u * thinK, chord = sqrtf(fmx(0, 1 - ku * ku)), m = fmx(c.r, fmx(c.g, c.b));
      c = mix(c, {m, m, m}, p.liquidThin * (1 - chord) * (1 - chord));
    }
    rowL[y] = luma(c);   // the light inside the liquid at this row (before backing, highlight, glass: they do not light a bubble)
    // Transparent liquid shows the per-row tube-back gradient. The highlight remains a surface
    // reflection and goes on after it.
    c = scale(c, br);
    c = mix(c, scale(back, p.brightness), p.liquidTransparency);
    // Side-lit rim (sim rimLight/rimTint): rises as u^2 toward the walls.
    if (p.rimLight > 0) {
      float rk = p.rimLight * u * u;
      c = {fmn(255, c.r + rk * rimTint.r), fmn(255, c.g + rk * rimTint.g), fmn(255, c.b + rk * rimTint.b)};
    }
    if (y >= hiTop && y < hiTop + p.highlightH) {
      float k = powf(1 - fabsf((y - hiTop) / fmx(1, p.highlightH - 1) - 0.5f) * 2, p.highlightSharp);
      c = mix(c, liquidHiScaled, fmn(1, (0.35f + 0.65f * k) * p.highlightBright));
    }
    float gw = glassWRef(p, y, hiTop, lam);
    float wetK = p.glassOverLiquid + (1 - p.glassOverLiquid) * p.liquidTransparency, glassWet = gw * wetK;
    // Empty tube: back only where the ray reaches it (wall band dark), glass over it, glow + rim on top.
    const RGB dryRow = mix(scale(mix(scale(back, dryT), ghi, gw), p.brightness), glassEdge, wall);
    pal.tubeBackRows[y] = q(dryRow);
    // Glass weight rises to the dry-side one with transparency; the grazing rim is the outer surface's
    // reflection, full weight over the liquid (sim).
    c = ambientize(mix(mix(c, glassHiScaled, glassWet), glassEdge, wetRim), bodyL, ambAmt);
    if (wet < 1) c = mix(c, dryRow, p.glassWall <= 0 ? 0 : au >= liqU ? 1 : expf(-(liqU - au) / 0.04f));   // past the contents' edge: the empty tube's row
    pal.rows[y] = q(c);
    pal.bubbleIn[y] = q(mix(c, {0, 0, 0}, p.bubbleDark));
  }
  // Fizz ring: the lit rim shaded as the liquid is lit at that row (body shading relative to its brightest row), cap 0.8 (sim).
  float rowLMax = 1; for (int y = 0; y < H; y++) rowLMax = fmx(rowLMax, rowL[y]);
  for (int y = 0; y < H; y++) pal.bubbleRimRows[y] = q(ambientize(scale(rimLit, 0.8f * rowL[y] / rowLMax), bodyL, ambAmt));
  pal.body = q(scale(body, br));
  pal.tubeBack = q(scale(tubeBack, p.brightness));
  pal.bubbleRim = q(ambientize(scale(rimC, br), bodyL, ambAmt));
  float lmax = 1;
  for (int y = 0; y < H; y++) { pal.rowK[y] = luma(to888(pal.rows[y])); lmax = fmx(lmax, pal.rowK[y]); }
  for (int y = 0; y < H; y++) pal.rowK[y] /= lmax;
}
#endif
// Style top light blended (lightPhys) with a Lambert cylinder lit from 2*light (sim buildPalette).
void Tube::buildPalette(const Params &p, float lightDeg, Palette &pal, const PalCache &pc) const {
  RGB body = hexToRgb(p.liquid), hi = hexToRgb(p.liquidHi), lo = hexToRgb(p.liquidLo);
  RGB tubeBack = hexToRgb(p.tubeBack), tubeBack2 = hexToRgb(p.tubeBack2), ghi = hexToRgb(p.glassHi);
  float br = p.brightness * p.liquidBright;
  RGB liquidHiScaled = scale(hi, br), glassHiScaled = scale(ghi, p.brightness);
  const RGB rimTint = scale(hexToRgb(p.rimTint), p.brightness);
  float bodyL = ambientBodyL(p), ambAmt = ambientAmt(p);
  float yc = (H - 1) / 2.0f, lightRad = 2 * lightDeg * (float)M_PI / 180;
  int hiTop = highlightTop(p, lightDeg);
  const RGB rimC = hexToRgb(p.bubbleRim);
  const RGB rimLit = { fmn(255, rimC.r * br), fmn(255, rimC.g * br), fmn(255, rimC.b * br) };   // clipped lit rim (sim rimLit)
  float rowL[TUBE_HEIGHT_MAX];   // per-row body-shading luma (fixed-size local, sim rowL)
  // Wall band (sim buildPalette): rows whose ray misses the bore never reach the back (dryT 0),
  // ramping up over a few rows inside; the liquid still shows through there. A neutral grazing
  // rim rises toward the silhouette on both sides (glassRim). glassWall 0 keeps a one-row rim.
  float wallU = 1 - 2 * fmx(1, p.glassWall) / H;
  RGB glassEdge = scale(mix(ghi, {180, 190, 195}, 0.72f), p.brightness);
  const float wet = clampf(p.wallWet, 0, 1);   // sim: a gas (0) keeps the glow and the empty tube's band over its column
  for (int y = 0; y < H; y++) {
    const float u = pc.u[y];   // (y + 0.5 - H / 2) / (H / 2), from pc: a division a row less
    // Wall glow (sim glowW/wallW): light piped along the wall lights the band itself; plateau with a
    // short ramp starting just inside the band, the grazing rim on top. Dry glass only, as far as the contents
    // wet the wall (wallWet): a liquid frustrates the internal reflection and fills the band (rim alone over it).
    // Over the contents (wetRim): the glow they leave piped, the rim. These, dryT, the back gradient and the body
    // shading before the light come from pc (buildPalCache: the same expressions, once per generation).
    const float wall = pc.wall[y], wetRim = pc.wetRim[y], dryT = pc.dryT[y];
    pal.dryT[y] = (uint16_t)(dryT * 256 + 0.5f);
    const RGB back = pc.back[y];
    float lam = fmx(0, cosf(pc.asinY[y] - lightRad));
    RGB c = pc.c0[y];
    if (p.lightPhys > 0) c = mix(c, mix(lo, body, 1 - p.shadeDepth * (1 - lam)), p.lightPhys);
    // Thin edge: shorter chord toward the walls absorbs less, the colour drifts to a grey of its
    // own peak channel, strongest on the outermost rows.
    if (p.liquidThin > 0) {
      float chord = pc.chord[y], m = fmx(c.r, fmx(c.g, c.b));
      c = mix(c, {m, m, m}, p.liquidThin * (1 - chord) * (1 - chord));
    }
    rowL[y] = luma(c);   // the light inside the liquid at this row (before backing, highlight, glass: they do not light a bubble)
    // Transparent liquid shows the per-row tube-back gradient. The highlight remains a surface
    // reflection and goes on after it.
    c = scale(c, br);
    c = mix(c, scale(back, p.brightness), p.liquidTransparency);
    // Side-lit rim (sim rimLight/rimTint): rises as u^2 toward the walls.
    if (p.rimLight > 0) {
      float rk = p.rimLight * u * u;
      c = {fmn(255, c.r + rk * rimTint.r), fmn(255, c.g + rk * rimTint.g), fmn(255, c.b + rk * rimTint.b)};
    }
    if (y >= hiTop && y < hiTop + p.highlightH) {
      float k = powf(1 - fabsf((y - hiTop) / fmx(1, p.highlightH - 1) - 0.5f) * 2, p.highlightSharp);
      c = mix(c, liquidHiScaled, fmn(1, (0.35f + 0.65f * k) * p.highlightBright));
    }
    float gw = glassW(p, y, hiTop, lam, pc);
    float wetK = p.glassOverLiquid + (1 - p.glassOverLiquid) * p.liquidTransparency, glassWet = gw * wetK;
    // Empty tube: back only where the ray reaches it (wall band dark), glass over it, glow + rim on top.
    const RGB dryRow = mix(scale(mix(scale(back, dryT), ghi, gw), p.brightness), glassEdge, wall);
    pal.tubeBackRows[y] = q(dryRow);
    // Glass weight rises to the dry-side one with transparency; the grazing rim is the outer surface's
    // reflection, full weight over the liquid (sim).
    c = ambientize(mix(mix(c, glassHiScaled, glassWet), glassEdge, wetRim), bodyL, ambAmt);
    if (wet < 1) c = mix(c, dryRow, pc.liqDry[y]);   // past the contents' edge: the empty tube's row
    pal.rows[y] = q(c);
    pal.bubbleIn[y] = q(mix(c, {0, 0, 0}, p.bubbleDark));
  }
  // Fizz ring: the lit rim shaded as the liquid is lit at that row (body shading relative to its brightest row), cap 0.8 (sim).
  float rowLMax = 1; for (int y = 0; y < H; y++) rowLMax = fmx(rowLMax, rowL[y]);
  for (int y = 0; y < H; y++) pal.bubbleRimRows[y] = q(ambientize(scale(rimLit, 0.8f * rowL[y] / rowLMax), bodyL, ambAmt));
  pal.body = q(scale(body, br));
  pal.tubeBack = q(scale(tubeBack, p.brightness));
  pal.bubbleRim = q(ambientize(scale(rimC, br), bodyL, ambAmt));
  float lmax = 1;
  for (int y = 0; y < H; y++) { pal.rowK[y] = luma(to888(pal.rows[y])); lmax = fmx(lmax, pal.rowK[y]); }
  for (int y = 0; y < H; y++) pal.rowK[y] /= lmax;
}


// Bake the digit shadow into one plane (w x h texels c/a holding the body at the top-left, see sim
// bakeShadow): the shadow copy, offset `off` px down-right in the shadow colour at `shadowA`, composited
// UNDER the body. The draw pass used to blend the two copies one after the other, each at its coverage
// times the factor k the compositor applies to a mark behind liquid (liquidTransparency; 1 behind air):
// out = bg(1 - k*s)(1 - k*b) + shadowC*k*s*(1 - k*b) + bodyC*k*b. That is one blend of the composite with
// alpha A = 1 - (1 - k*s)(1 - k*b) and colour (shadowC*k*s*(1 - k*b) + bodyC*k*b) / A — the transparency
// INCLUDED, because two layers at k reach an opacity (up to 1 - (1-k)^2) a single mark at k never could.
// So a plane is baked per context: behind air with k = 1, behind liquid with k = transparency, and the
// Mark skips its own transparency step for these glyphs (Mark::bakedT). Exact to within one quantisation
// step at half the per-frame work; the approximations are the wall-band fade rows behind air (their
// factor varies per row) and a non-zero markContrast (floored on the composite instead of per layer).
// Texels are visited bottom-right to top-left so the body texel a shadow sample reads, (x-off, y-off),
// has not been rewritten yet.
// Index of texel (x, y) of a w x h glyph as the viewer reads it; rot: stored turned (see ScaledGlyph, sim texel).
static inline int texel(int x, int y, int w, int h, bool rot) { return rot ? x * h + (h - 1 - y) : y * w + x; }
// The contrast floor (markContrast) baked into the behind-liquid plane against one liquid colour R, the body (sim
// bakeFloor): per texel the colour that, blended over R by its coverage as is, gives what the per-pixel floor would
// have made of it over R, c' = R + (floor(mix(R, c, a)) - R) / a with a = max(T, cov). Drawn without a floor
// (Mark::Cin), so the liquid behind still shows through by the same coverage.
static void bakeFloor(uint16_t *c, const uint8_t *a, int n, float transK, float contrast, uint16_t floorR) {
  const RGB R = to888(floorR); const float lb = luma(R);
  for (int i = 0; i < n; i++) {
    if (!a[i]) continue;
    const float ak = fmx(transK, a[i] / 255.0f);
    if (ak <= 0) continue;
    RGB m = mix(R, to888(c[i]), ak);
    const float lc = luma(m), d = lc - lb;
    if (fabsf(d) >= contrast) continue;   // already apart: the texel as is
    const int dir = d != 0 ? (d > 0 ? 1 : -1) : (lb > 110 ? -1 : 1);
    const float target = clampf(lb + dir * contrast, 0, 255);
    m = dir < 0 ? scale(m, target / fmx(1, lc)) : mix(m, RGB{255, 255, 255}, fmn(1, (target - lc) / fmx(1, 255 - lc)));
    c[i] = q(RGB{R.r + (m.r - R.r) / ak, R.g + (m.g - R.g) / ak, R.b + (m.b - R.b) / ak});
  }
}
// Contrast floor of the rear sprite digits baked into their behind-liquid plane (sim floorBake): C and the body
// colour, or C = 0 (no floor, digits on top, no baked shadow plane).
static void floorBake(const Params &p, float &C, uint16_t &R) {
  C = p.markContrast * p.digitBright; R = 0;
  if (!(C > 0) || p.digitsOnTop || !(p.digitShadow && p.digitShadowStrength > 0)) { C = 0; return; }
  R = q(scale(hexToRgb(p.liquid), p.brightness * p.liquidBright));
}
static void bakeShadow(uint16_t *c, uint8_t *a, int w, int h, int bw, int bh, int off, uint16_t shadowC, float shadowA, float k, bool rot) {
  const RGB sc = to888(shadowC);
  for (int y = h - 1; y >= 0; y--) for (int x = w - 1; x >= 0; x--) {
    const int i = texel(x, y, w, h, rot);
    const int as = x >= off && y >= off ? a[texel(x - off, y - off, w, h, rot)] : 0;
    const int ab = x < bw && y < bh ? a[i] : 0;
    if (!as && (!ab || k >= 1)) continue;                // empty, or a body-only texel behind air: unchanged
    const float s = as * shadowA * (1.0f / 255) * k, b = ab * (1.0f / 255) * k, A = 1 - (1 - s) * (1 - b);
    if (A <= 0) { c[i] = 0; a[i] = 0; continue; }        // fully transparent (k = 0: opaque liquid hides the mark)
    const float ws = s * (1 - b) / A, wb = b / A;
    const RGB bc = ab ? to888(c[i]) : RGB{ 0, 0, 0 };
    c[i] = q({ sc.r * ws + bc.r * wb, sc.g * ws + bc.g * wb, sc.b * ws + bc.b * wb });
    a[i] = (uint8_t)jround(A * 255);
  }
}

// shadow: 565 colour of the baked digit shadow (-1 = none), shadowA its opacity, shadowOff its px offset,
// transK the liquid transparency the behind-liquid plane is baked for (clamped float, as in the sim).
ScaledGlyph *Tube::scaledGlyphs(int sheetIdx, int bw, int bh, float brightness, uint32_t tintHex, float tintAmt, float tone,
                                int shadow, float shadowA, int shadowOff, float transK, bool rot, float floorC, uint16_t floorR) {
  if (sheetIdx < 0 || sheetIdx >= NUM_SPRITE_SHEETS) return nullptr;
  ScaledSet &S = set;
  if (!S.poolC || !S.poolA || !EXP565 || !digitRows) return nullptr;   // render_init failed: no sprite digits (visible)
  if (S.sheet == sheetIdx && S.bw == bw && S.bh == bh && S.brightness == brightness && S.tint == tintHex && S.tintAmt == tintAmt && S.tone == tone
      && S.shadow == shadow && S.shadowA == shadowA && S.shadowOff == shadowOff && S.transK == transK && S.rot == rot
      && S.floorC == floorC && S.floorR == floorR) return S.g;
  const int off = shadow >= 0 ? shadowOff : 0;   // baked shadow margin (right and bottom)
  const SpriteSheet &sp = *SPRITE_SHEETS[sheetIdx];
  RGB tint = hexToRgb(tintHex);
  auto tm = [&](float v, float ch) { return v * (1 - tintAmt) + v * (ch / 255.0f) * tintAmt; };
  float t = fmx(-1, fmn(1, tone));
  auto tn = [&](float v) { return t < 0 ? v * (1 + t) : v + (255 - v) * t; };
  int used = 0;
  for (int d = 0; d < 10; d++) {
    int gw = (int)fmx(1, jround(sp.widths[d] * (float)bw / sp.cellW));
    float cx0 = d * sp.cellW + (sp.cellW - sp.widths[d]) / 2.0f;
    const int tw = gw + off, th = bh + off, planes = off > 0 ? 2 : 1;
    if (used + planes * tw * th > GLYPH_POOL_PX) { S.g[d] = { 0, 0, 0, S.poolC, S.poolC, S.poolA, S.poolA, { nullptr, nullptr } }; continue; }   // over budget: glyph dropped
    S.g[d].w = rot ? th : tw; S.g[d].h = rot ? tw : th; S.g[d].adv = gw;
    S.g[d].c = S.poolC + used; S.g[d].a = S.poolA + used; used += tw * th;
    if (planes == 2) { S.g[d].cw = S.poolC + used; S.g[d].aw = S.poolA + used; used += tw * th; }
    else { S.g[d].cw = S.g[d].c; S.g[d].aw = S.g[d].a; }
    memset(S.g[d].c, 0, tw * th * 2); memset(S.g[d].a, 0, tw * th);
    // Box bounds as exact ratios (x * width / gw, not x / sx): the reciprocal form lands a hair below an
    // integer in float and a hair above in the sim's doubles, dropping the glyph's last sheet column here.
    for (int y = 0; y < bh; y++) for (int x = 0; x < gw; x++) {
      int X0 = (int)ffloor(cx0 + (float)(x * sp.widths[d]) / gw), X1 = (int)fmx(X0 + 1, ffloor(cx0 + (float)((x + 1) * sp.widths[d]) / gw));
      int Y0 = (int)ffloor((float)(y * sp.cellH) / bh), Y1 = (int)fmx(Y0 + 1, ffloor((float)((y + 1) * sp.cellH) / bh));
      float r = 0, g = 0, b = 0, al = 0; int n = 0;
      for (int Y = Y0; Y < Y1; Y++) for (int X = X0; X < X1; X++) {
        if (X < 0 || X >= sp.w || Y < 0 || Y >= sp.h) { n++; continue; }
        const uint8_t *px4 = sp.rgba + ((size_t)Y * sp.w + X) * 4; float pa = px4[3];
        r += px4[0] * pa; g += px4[1] * pa; b += px4[2] * pa; al += pa; n++;
      }
      int k = texel(x, y, tw, th, rot);
      if (al > 0) {
        S.g[d].c[k] = q(scale({ tn(tm(r / al, tint.r)), tn(tm(g / al, tint.g)), tn(tm(b / al, tint.b)) }, brightness));
        S.g[d].a[k] = (uint8_t)jround(al / n);
      }
    }
    if (planes == 2) {
      memcpy(S.g[d].cw, S.g[d].c, tw * th * 2); memcpy(S.g[d].aw, S.g[d].a, tw * th);
      bakeShadow(S.g[d].c, S.g[d].a, tw, th, gw, bh, off, (uint16_t)shadow, shadowA, 1.0f, rot);
      bakeShadow(S.g[d].cw, S.g[d].aw, tw, th, gw, bh, off, (uint16_t)shadow, shadowA, transK, rot);
      if (floorC > 0) bakeFloor(S.g[d].cw, S.g[d].aw, tw * th, transK, floorC, floorR);
    }
    // Row spans of both planes (the behind-liquid plane can be all-transparent at transparency 0).
    S.g[d].span[0] = S.g[d].span[1] = nullptr;
    const int sw = S.g[d].w, sh = S.g[d].h;   // the stored (panel-frame) box
    if (S.poolS && sh <= GLYPH_SPAN_ROWS && sw <= 255) {   // endpoints are bytes: a wider glyph draws full rows
      for (int pl = 0; pl < planes; pl++) {
        uint8_t *sp = S.poolS + (d * 2 + pl) * GLYPH_SPAN_ROWS * 2; const uint8_t *ap = pl ? S.g[d].aw : S.g[d].a;
        for (int y = 0; y < sh; y++) {
          int x0 = 0, x1 = 0;
          for (int x = 0; x < sw; x++) if (ap[y * sw + x]) { if (x1 == 0) x0 = x; x1 = x + 1; }
          sp[y * 2] = (uint8_t)x0; sp[y * 2 + 1] = (uint8_t)x1;
        }
        S.g[d].span[pl] = sp;
      }
      if (planes == 1) S.g[d].span[1] = S.g[d].span[0];
    }
  }
  S.sheet = sheetIdx; S.bw = bw; S.bh = bh; S.brightness = brightness; S.tint = tintHex; S.tintAmt = tintAmt; S.tone = tone;
  S.shadow = shadow; S.shadowA = shadowA; S.shadowOff = shadowOff; S.transK = transK; S.rot = rot; S.floorC = floorC; S.floorR = floorR;
  return S.g;
}


bool Tube::layoutLabels(int y0, const Params &p, uint32_t gen, int ticksN, const TubeState &st, float fill, Labels &lb) {
  const float acrossTilt = st.acrossTilt;
  bool minutes = ticksN == 60;
  int every = (int)fmx(1, jround(minutes ? p.digitMinuteStep : p.digitHourStep));
  // Motion-dependent parts of the layout, folded into the cache key.
  int bottomOff = p.digitsOnTop ? (int)jround(acrossTilt * p.topParallax) : 0;
  // View-angle parallax (sim layoutLabels): the rear wall's shift behind air and behind liquid, 1/16 px, quantised by the
  // physics step (TubeState rearX16 … rearY16w).
  {
    const bool rear = !p.digitsOnTop;
    lb.sx16d = rear ? st.rearX16 : 0; lb.sy16d = rear ? st.rearY16 : 0; lb.sx16w = rear ? st.rearX16w : 0; lb.sy16w = rear ? st.rearY16w : 0;
  }
  const ShiftTap tyD = shiftTap(lb.sy16d, lb.sy16w, 0), tyW = shiftTap(lb.sy16d, lb.sy16w, 256);
  const int keyRowD = tyD.i * 2 + (tyD.w1 ? 1 : 0), keyRowW = tyW.i * 2 + (tyW.w1 ? 1 : 0);
  int start = (int)jround(minutes ? p.digitMinuteStart : p.digitHourStart); if (start <= 0) start = every;
  int first = start, last = ticksN - 1;
  if (minutes ? p.digitsLastOnlyM : p.digitsLastOnlyH) {
    float f = fill < 0 ? 0 : fill * ticksN; if (f > ticksN - 1e-3f) f = ticksN - 1e-3f;
    int s = minutes ? every : 1; first = last = (int)f / s * s;
    if (first == 0) first = 1;
  }
  if (lb.valid && lb.gen == gen && lb.H == H && lb.bottomOff == bottomOff && lb.first == first && lb.keyRowD == keyRowD && lb.keyRowW == keyRowW) return lb.have;
  lb.valid = true; lb.gen = gen; lb.H = H; lb.bottomOff = bottomOff; lb.first = first; lb.keyRowD = keyRowD; lb.keyRowW = keyRowW; lb.have = false;
  if (!p.digits) return false;
  float kx = minutes ? p.digitScaleXMin : p.digitScaleX, ky = minutes ? p.digitScaleYMin : p.digitScaleY;
  float bottom = (minutes ? p.digitBottomMin : p.digitBottom) + bottomOff;
  int idx = (int)jround(p.digitFont); bool useSprite = idx >= SPRITE_FONT;
  const Font *font = &FONTS[idx < 0 ? 0 : idx >= NUM_FONTS ? NUM_FONTS - 1 : idx];
  // Vertical watch: the glyph's width lies across the tube and its height along it, so the scales swap roles.
  const bool V = p.vertical; const float kw = V ? ky : kx;
  int bw = (int)fmx(1, jround((useSprite ? GLYPH_EM_W : font->w) * kw));
  int bh = (int)fmx(1, jround((useSprite ? GLYPH_EM_H : font->h) * (V ? kx : ky)));
  if (bh > GLYPH_BH_CAP) bh = GLYPH_BH_CAP;
  float shadowA = clampf(p.digitShadowStrength, 0, 1); int shadowOff = (int)fmx(1, jround(p.digitShadowOffset));
  int shadow = p.digitShadow && shadowA > 0 ? q(scale(hexToRgb(p.digitShadowColor), p.brightness * p.digitBright)) : -1;
  // Sprite glyphs carry the shadow baked in (one draw pass); bitmap glyphs still draw it as a second pass.
  // The behind-liquid plane is baked for the liquid transparency itself (the Mark skips its own step for
  // these glyphs): the unquantised float, as in the sim, so both bakes round the same way.
  float floorC; uint16_t floorR; floorBake(p, floorC, floorR);
  ScaledGlyph *sprite = useSprite ? scaledGlyphs(idx - SPRITE_FONT, bw, bh, p.brightness * p.digitBright, p.digitTint, p.digitTintAmount, p.digitTone, shadow, shadowA, shadowOff, clampf(p.liquidTransparency, 0, 1), V, floorC, floorR) : nullptr;
  int gap = sprite ? (int)fmx(1, jround(bw / 5.0f)) : (int)fmx(1, jround(kw));
  int yBase = y0 + H - 1 - (int)bottom, yTop = yBase - bh + 1;
  // NB: sim uses yBase = y0+H-1-bottom with fractional `bottom` possible; presets use integers.
  if (p.digitsOnTop) { markSourceRows(H, p.topLens, lb.sourceRows, p.lensCurve); memcpy(lb.drySourceRows, lb.sourceRows, sizeof(lb.sourceRows)); }
  else { markSourceRows(H, p.bottomLens, lb.sourceRows); markSourceRows(H, p.digitDryLens, lb.drySourceRows); }
  lb.n = 0;
  const bool flip = V && p.remaining;   // vertical + remaining: the scale runs from the top (right) end
  int yMin = yBase + 1, yMax = yBase;   // vertical: the labels' extent across the tube
  for (int i = first; i <= last && lb.n < LABELS_MAX; i += every) {
    Label &l = lb.list[lb.n++];
    if (minutes && p.digitsLeadingZero) { l.text[0] = '0' + i / 10; l.text[1] = '0' + i % 10; l.len = 2; }
    else if (i >= 10) { l.text[0] = '0' + i / 10; l.text[1] = '0' + i % 10; l.len = 2; }
    else { l.text[0] = '0' + i; l.len = 1; }
    int w = -gap;
    for (int k = 0; k < l.len; k++) { l.adv[k] = sprite ? sprite[l.text[k] - '0'].adv : bw; w += l.adv[k] + gap; }
    int m = (int)jround(p.cornerR);
    if (V) {
      // centred on its tick along the tube and on the tube's axis across it (`digitBottom` has no say; the front
      // parallax still shifts it); a label too wide for the tube starts at the near wall
      const float cc = (float)i * L / ticksN;
      int x0 = (int)jround((flip ? L - cc : cc) - bh / 2.0f);
      l.x0 = x0 < m ? m : x0 > L - bh - m ? L - bh - m : x0;
      l.y = y0 + ((H - w) >> 1) - bottomOff; if (l.y < y0) l.y = y0;
      if (l.y < yMin) yMin = l.y;
      if (l.y + w - 1 > yMax) yMax = l.y + w - 1;
      continue;
    }
    int x0 = (int)jround((float)i * L / ticksN - w / 2.0f);
    l.x0 = x0 < m ? m : x0 > L - w - m ? L - w - m : x0; l.y = yTop;
  }
  int sourceRy0 = (V ? yMin : yTop) - y0, sourceRy1 = (V ? yMax : yBase) - y0 + (shadow >= 0 ? shadowOff : 0);
  lb.ry0 = H; lb.ry1 = -1; lb.dryRy0 = H; lb.dryRy1 = -1;
  // a copy's rows: its source rows before the vertical shift, one more for a fractional overhang (sim rowSpan)
  const int loW = sourceRy0 + tyW.i, hiW = sourceRy1 + tyW.i + (tyW.w1 ? 1 : 0);
  const int loD = sourceRy0 + tyD.i, hiD = sourceRy1 + tyD.i + (tyD.w1 ? 1 : 0);
  for (int ry = 0; ry < H; ry++) {
    if (lb.sourceRows[ry] >= loW && lb.sourceRows[ry] <= hiW) {
      if (ry < lb.ry0) lb.ry0 = ry;
      if (ry > lb.ry1) lb.ry1 = ry;
    }
    if (lb.drySourceRows[ry] >= loD && lb.drySourceRows[ry] <= hiD) {
      if (ry < lb.dryRy0) lb.dryRy0 = ry;
      if (ry > lb.dryRy1) lb.dryRy1 = ry;
    }
  }
  lb.bw = bw; lb.bh = bh; lb.yTop = yTop; lb.vertical = V;
  lb.sprite = sprite; lb.font = font; lb.gap = gap; lb.shadow = shadow; lb.shadowT = alphaT(shadowA); lb.shadowOff = shadowOff;
  digitRowColors(p, bh, lb.rows);
  lb.have = true;
  return true;
}

// Coverage (0..255) and colour of glyph pixel (cx, cy); both only defined inside w x h.
struct BitmapSampler {
  const uint8_t *g; const Font &f; const Labels &lb; int w, h, msb; bool rot;
  // rot (vertical watch): turned a quarter — panel (cx, cy) reads glyph column cy, row bh - 1 - cx
  BitmapSampler(const Font &ff, int d, const Labels &l) : g(ff.g[d]), f(ff), lb(l), w(l.vertical ? l.bh : l.bw), h(l.vertical ? l.bw : l.bh), msb(1 << (ff.w - 1)), rot(l.vertical) {}
  int a(int cx, int cy) const {
    const int gx = rot ? cy : cx, gy = rot ? lb.bh - 1 - cx : cy;
    int col = gx * f.w / lb.bw; if (col > f.w - 1) col = f.w - 1;
    int row = gy * f.h / lb.bh; if (row > f.h - 1) row = f.h - 1;
    return (g[row] & (msb >> col)) ? 255 : 0;
  }
  uint16_t c(int cx, int cy) const { return lb.rows[rot ? lb.bh - 1 - cx : cy]; }
  int aw(int cx, int cy) const { return a(cx, cy); }                  // no baked shadow: one plane
  uint16_t cw(int cx, int cy) const { return c(cx, cy); }
};
struct SpriteSampler {
  const ScaledGlyph &g; int w, h;
  explicit SpriteSampler(const ScaledGlyph &gg) : g(gg), w(gg.w), h(gg.h) {}
  int a(int cx, int cy) const { return g.a[cy * g.w + cx]; }
  uint16_t c(int cx, int cy) const { return g.c[cy * g.w + cx]; }
  int aw(int cx, int cy) const { return g.aw[cy * g.w + cx]; }
  uint16_t cw(int cx, int cy) const { return g.cw[cy * g.w + cx]; }
};
// One destination column xd across the meniscus (0 < wet share k < 256; sim drawGlyph): every tube row, its source row
// blended from the dry warp toward the wet one by k, the parallax likewise (shiftTap), bilinear taps (weights 1/65536)
// of the plane the Mark picks per pixel: coverage and premultiplied colour (mix565). xg: the copy's panel x (glyph x plus
// the shadow offset). Only the columns under a meniscus take this per-pixel path.
// Tube rows [r0, r1) only (step 9: band by band; 0, lb.H = every row).
template <class S>
static void __attribute__((noinline)) drawRampColumn(const S &s, int xg, int xd, int k, int y0, int yTop, const Labels &lb, const Mark &mark, bool shadowPass,
                                                     int r0, int r1) {
  const ShiftTap tx = shiftTap(lb.sx16d, lb.sx16w, k), ty = shiftTap(lb.sy16d, lb.sy16w, k);
  const int cx = xd - xg - tx.i; if (cx < 0 || cx > s.w) return;
  const int sourceTop = yTop - y0 + (shadowPass ? lb.shadowOff : 0) + ty.i;
  auto covOf = [&](int a) { return shadowPass ? LUT_alphaT16[a] * lb.shadowT >> 8 : LUT_alphaT16[a]; };
  if (!tx.w1 && !ty.w1) {   // whole px: the one tap
    if (cx >= s.w) return;
    for (int ry = r0; ry < r1; ry++) {
      const int cy = blendRow(lb.drySourceRows[ry], lb.sourceRows[ry], k) - sourceTop; if (cy < 0 || cy >= s.h) continue;
      const bool L = mark.inLiquid(xd, ry);
      const int a = L ? s.aw(cx, cy) : s.a(cx, cy); if (!a) continue;
      mark(xd, y0 + ry, shadowPass ? (uint16_t)lb.shadow : L ? s.cw(cx, cy) : s.c(cx, cy), covOf(a));
    }
    return;
  }
  const int wx0 = 256 - tx.w1, wy0 = 256 - ty.w1;
  const int w00 = wx0 * wy0, w10 = tx.w1 * wy0, w01 = wx0 * ty.w1, w11 = tx.w1 * ty.w1;
  for (int ry = r0; ry < r1; ry++) {
    const int cy = blendRow(lb.drySourceRows[ry], lb.sourceRows[ry], k) - sourceTop; if (cy < 0 || cy > s.h) continue;
    const bool L = mark.inLiquid(xd, ry);
    auto tap = [&](int u, int v) -> int { return u < 0 || v < 0 || u >= s.w || v >= s.h ? 0 : L ? s.aw(u, v) : s.a(u, v); };
    auto col = [&](int m, int u, int v) -> uint32_t { return m ? (L ? s.cw(u, v) : s.c(u, v)) : 0; };   // a weighted tap lies inside
    const int a00 = tap(cx, cy) * w00, a10 = tap(cx - 1, cy) * w10, a01 = tap(cx, cy - 1) * w01, a11 = tap(cx - 1, cy - 1) * w11;
    const int a = (a00 + a10 + a01 + a11 + 32768) >> 16; if (!a) continue;
    const uint16_t c = shadowPass ? (uint16_t)lb.shadow
      : mix565(a00, a10, a01, a11, col(a00, cx, cy), col(a10, cx - 1, cy), col(a01, cx, cy - 1), col(a11, cx - 1, cy - 1), a);
    mark(xd, y0 + ry, c, covOf(a));
  }
}
// The rows drawRampColumn can draw for this column (its row test alone), widened into [lo, hi].
static void __attribute__((noinline)) rampColumnRows(int sw, int sh, int xg, int xd, int k, int y0, int yTop, const Labels &lb, bool shadowPass,
                                                     int16_t &lo, int16_t &hi) {
  const ShiftTap tx = shiftTap(lb.sx16d, lb.sx16w, k), ty = shiftTap(lb.sy16d, lb.sy16w, k);
  const int cx = xd - xg - tx.i; if (cx < 0 || cx > sw || (cx == sw && !tx.w1)) return;
  const int sourceTop = yTop - y0 + (shadowPass ? lb.shadowOff : 0) + ty.i;
  for (int ry = 0; ry < lb.H; ry++) {
    const int cy = blendRow(lb.drySourceRows[ry], lb.sourceRows[ry], k) - sourceTop; if (cy < 0 || cy > sh || (cy == sh && !ty.w1)) continue;
    if (ry < lo) lo = (int16_t)ry;
    if (ry > hi) hi = (int16_t)ry;
  }
}
// Step 9: one glyph pass, planned once a frame (Tube::planLabels; the marks are then drawn band by band): which columns
// its copies draw, its meniscus (ramp) columns and the rows those can draw. PSRAM (MarkPlan).
struct GlyphPlan {
  const ScaledGlyph *g;                 // sprite glyph (pass 0); null for a bitmap pass
  uint8_t pass, d;                      // 0 sprite, 1 bitmap shadow copy, 2 bitmap body; the digit (bitmap)
  bool anyDry, anyWet;
  int16_t x, yTop;                      // the glyph's panel x (sprite: after the vertical margin), its label row
  int16_t rampLo, rampHi, rampR0, rampR1;   // ramp columns [rampLo, rampHi] (none: rampLo > rampHi), their rows [rampR0, rampR1]
  int16_t dA0, dA1, dB0, dB1, w0, w1;   // sprite: the copies' glyph columns
  int16_t xg;                           // bitmap: the copy's panel x
  int16_t ixD, iyD, wxD, wyD, ixW, iyW, wxW, wyW;   // the dry / wet copy's parallax taps (shiftTap at share 0 / 256)
  uint32_t dcol[5], wcol[5];            // bitmap: glyph columns 0..128 the dry / wet copy draws
};
static inline bool bit(const uint32_t *m, int i) { return (m[i >> 5] >> (i & 31)) & 1; }
// The plan of one bitmap glyph pass (drawGlyph's set-up). A glyph (see sim drawGlyph): a panel column shows one image,
// chosen by its wet share: behind air (0) the dry copy (digitDryLens rows) at the dry parallax, behind liquid (256) the
// wet copy (bottomLens rows) at the wet one, sub-pixel parallax bilinearly resampled (weights 1/256: coverage and
// premultiplied colour, mix565) so it glides; across the meniscus drawRampColumn. Rows outer (glyph memory is
// row-major); every pixel is written at most once.
// The dry and the wet copy's parallax taps (share 0 / 256).
static inline void planTaps(const Labels &lb, GlyphPlan &gp) {
  const ShiftTap dx = shiftTap(lb.sx16d, lb.sx16w, 0), dy = shiftTap(lb.sy16d, lb.sy16w, 0);
  const ShiftTap wx = shiftTap(lb.sx16d, lb.sx16w, 256), wy = shiftTap(lb.sy16d, lb.sy16w, 256);
  gp.ixD = (int16_t)dx.i; gp.wxD = (int16_t)dx.w1; gp.iyD = (int16_t)dy.i; gp.wyD = (int16_t)dy.w1;
  gp.ixW = (int16_t)wx.i; gp.wxW = (int16_t)wx.w1; gp.iyW = (int16_t)wy.i; gp.wyW = (int16_t)wy.w1;
}
template <class S>
static void planGlyph(const S &s, int x, int y0, int yTop, const Labels &lb, const Warp &warp, bool shadowPass, GlyphPlan &gp) {
  // the shadow copy sits down-right as read: a vertical watch's down is the panel's left
  const int off = shadowPass ? lb.shadowOff : 0, xg = x + (lb.vertical ? -off : off);
  const int gw = s.w > 128 ? 128 : s.w;
  gp.g = nullptr; gp.pass = shadowPass ? 1 : 2; gp.x = (int16_t)x; gp.yTop = (int16_t)yTop; gp.xg = (int16_t)xg;
  planTaps(lb, gp);
  memset(gp.dcol, 0, sizeof(gp.dcol)); memset(gp.wcol, 0, sizeof(gp.wcol));
  bool anyDry = false, anyWet = false;
  // copy column c lies at panel xg + i + c; one more for a fractional overhang
  for (int cx = 0, n = gw + (gp.wxD ? 1 : 0); cx < n; cx++)
    if (warp(xg + gp.ixD + cx) == 0) { gp.dcol[cx >> 5] |= 1u << (cx & 31); anyDry = true; }
  for (int cx = 0, n = gw + (gp.wxW ? 1 : 0); cx < n; cx++)
    if (warp(xg + gp.ixW + cx) == 256) { gp.wcol[cx >> 5] |= 1u << (cx & 31); anyWet = true; }
  gp.anyDry = anyDry; gp.anyWet = anyWet;
  gp.rampLo = 1; gp.rampHi = 0; gp.rampR0 = (int16_t)lb.H; gp.rampR1 = -1;
  if (warp.all()) return;
  const int xr1 = xg + gw + (gp.ixD > gp.ixW ? gp.ixD : gp.ixW);
  for (int xd = xg + (gp.ixD < gp.ixW ? gp.ixD : gp.ixW); xd <= xr1; xd++) {
    const int k = warp(xd);
    if (!(k > 0 && k < 256)) continue;
    if (gp.rampLo > gp.rampHi) gp.rampLo = (int16_t)xd;
    gp.rampHi = (int16_t)xd;
    rampColumnRows(s.w, s.h, xg, xd, k, y0, yTop, lb, shadowPass, gp.rampR0, gp.rampR1);
  }
}
// A planned bitmap glyph pass over tube rows [r0, r1).
template <class S>
static void drawGlyphRows(const S &s, const GlyphPlan &gp, int y0, const Labels &lb, const Warp &warp, const Mark &mark, int r0, int r1) {
  const bool shadowPass = gp.pass == 1;
  const int off = shadowPass ? lb.shadowOff : 0, xg = gp.xg, sourceTop = gp.yTop - y0 + off;
  auto covT = [&](int a) { return shadowPass ? LUT_alphaT16[a] * lb.shadowT >> 8 : LUT_alphaT16[a]; };   // shadow copy at its own opacity
  const int gw = s.w > 128 ? 128 : s.w;
  const bool anyDry = gp.anyDry, anyWet = gp.anyWet;
  // Plane per PIXEL: the behind-liquid plane (aw/cw) exactly where the Mark composites through the liquid,
  // the behind-air plane elsewhere. The column's wet share above decides which image (warp and parallax) it shows;
  // the meniscus makes rows of one column differ, and there the Mark's per-row test picks the plane.
  auto A = [&](bool L, int cx, int cy) -> int { return L ? s.aw(cx, cy) : s.a(cx, cy); };
  auto Cc = [&](bool L, int cx, int cy) -> uint16_t { return L ? s.cw(cx, cy) : s.c(cx, cy); };
  auto tap = [&](bool L, int cx, int cy) -> int { return cx < 0 || cy < 0 || cx >= s.w || cy >= s.h ? 0 : A(L, cx, cy); };
  // One copy's glyph row: copy column c at panel xg + ix + c samples source (c - fx, cy - fy) (taps at columns c / c-1,
  // rows cy / cy-1); whole px: the one tap with its own colour.
  auto copyRow = [&](const uint32_t *cols, int ix, int wx1, int wy1, int cy, int ry, int y) {
    if (!wx1 && !wy1) {
      if (cy >= s.h) return;
      for (int cx = 0; cx < gw; cx++) {
        if (!bit(cols, cx)) continue;
        const bool L = mark.inLiquid(xg + ix + cx, ry); int a = A(L, cx, cy); if (!a) continue;
        mark(xg + ix + cx, y, shadowPass ? (uint16_t)lb.shadow : Cc(L, cx, cy), covT(a));
      }
      return;
    }
    const int wx0 = 256 - wx1, wy0 = 256 - wy1;
    const int w00 = wx0 * wy0, w10 = wx1 * wy0, w01 = wx0 * wy1, w11 = wx1 * wy1;
    for (int cx = 0, n = gw + (wx1 ? 1 : 0); cx < n; cx++) {
      if (!bit(cols, cx)) continue;
      const bool L = mark.inLiquid(xg + ix + cx, ry);
      int a00 = tap(L, cx, cy) * w00, a10 = tap(L, cx - 1, cy) * w10;
      int a01 = tap(L, cx, cy - 1) * w01, a11 = tap(L, cx - 1, cy - 1) * w11;
      int a = (a00 + a10 + a01 + a11 + 32768) >> 16; if (!a) continue;
      auto col = [&](int m, int u, int v) -> uint32_t { return m ? Cc(L, u, v) : 0; };   // a weighted tap lies inside
      const uint16_t c = shadowPass ? (uint16_t)lb.shadow
        : mix565(a00, a10, a01, a11, col(a00, cx, cy), col(a10, cx - 1, cy), col(a01, cx, cy - 1), col(a11, cx - 1, cy - 1), a);
      mark(xg + ix + cx, y, c, covT(a));
    }
  };
  int a0 = lb.dryRy0 < lb.ry0 ? lb.dryRy0 : lb.ry0, a1 = lb.dryRy1 > lb.ry1 ? lb.dryRy1 : lb.ry1;
  if (a0 < r0) a0 = r0; if (a1 > r1 - 1) a1 = r1 - 1;
  for (int ry = a0; ry <= a1; ry++) {
    const int y = y0 + ry;
    const int cyD = lb.drySourceRows[ry] - sourceTop - gp.iyD;
    if (anyDry && ry >= lb.dryRy0 && ry <= lb.dryRy1 && cyD >= 0 && cyD <= s.h) copyRow(gp.dcol, gp.ixD, gp.wxD, gp.wyD, cyD, ry, y);
    const int cy = lb.sourceRows[ry] - sourceTop - gp.iyW;
    if (anyWet && ry >= lb.ry0 && ry <= lb.ry1 && cy >= 0 && cy <= s.h) copyRow(gp.wcol, gp.ixW, gp.wxW, gp.wyW, cy, ry, y);
  }
  const int ra = r0 > gp.rampR0 ? r0 : gp.rampR0, rb = r1 < gp.rampR1 + 1 ? r1 : gp.rampR1 + 1;
  if (ra >= rb) return;
  for (int xd = gp.rampLo; xd <= gp.rampHi; xd++) {
    const int k = warp(xd);
    if (k > 0 && k < 256) drawRampColumn(s, xg, xd, k, y0, gp.yTop, lb, mark, shadowPass, ra, rb);
  }
}
// ---------------------------------------------------------------------------------------------
// sprite glyphs: row-run compositor
// ---------------------------------------------------------------------------------------------
// The generic path classifies every texel on its own (edge test, band test, strip test, plane choice),
// which is branchy enough to spill on Xtensa. Here a glyph row is cut once into runs on which every
// decision is constant — top / behind air / behind liquid — and each run goes through a small loop.
// Sprite digits differ from drawGlyph<SpriteSampler> in one look decision (step 8 of the LCD perf plan,
// 2026-10-30; sim drawDigitLayer): no surface band is composited over them, so no pixel needs the per-pixel
// compositor outside the ramp.

// MODE 0: on top or behind air (coverage scaled by scaleT: 256 on top, the row's dryT behind air).
// MODE 1: behind liquid, transparency baked into the plane and no contrast floor: the texel colour as is.
// MODE 2: behind liquid, general (throughLiquid per pixel).
// MODE 3: behind liquid, transparency baked into the plane, with a contrast floor (Mark::wetColourT).
// The through-liquid colour (MODE 2 / 3) of the last texel: along a glyph row the liquid behind is mostly one
// colour and neighbouring texels repeat, and throughLiquid with a contrast floor is two lumas and up to four
// divisions. Exact: same inputs, same outputs.
struct LiquidMemo {
  uint16_t bg = 0, c = 0, out = 0; int cov = -1, covOut = 0;
  uint32_t recipT = 0;
  inline uint16_t get(uint16_t bg_, uint16_t c_, int &covT, int T, int C, bool baked) {
    if (bg_ == bg && c_ == c && covT == cov) { covT = covOut; return out; }
    bg = bg_; c = c_; cov = covT;
    if (baked && !recipT) recipT = Mark::recipOf(T);
    out = baked ? Mark::wetColourT(bg_, c_, covT, T, C, true, recipT) : throughLiquid(bg_, c_, T, C);
    covOut = covT; return out;
  }
};
// Profile (2026-10-29, LCD native, wide tubes, user preset; -DDIGIT_PROF and throwaway re-draw probes): the digit
// pass is ~90 % compute, not PSRAM — each run drawn a second time right away (everything cached) costs 85-89 % of the
// first draw, a whole glyph 92 % — at ~1.5-2 cycles an instruction. So fewer instructions per pixel: the scalar blend
// on byte lanes from EXP565 (no unpacking of either colour, the strip pixel read and written byte-swapped as it lies),
// the SIMD blend below on the LCD, the fractional taps in their own pass (gone with step 8's whole-px parallax),
// the per-row band / liquid facts once per row instead of once per glyph row (DigitRow). Hours tube, pinned: rear
// digits 12.7-13.2 -> 9.7-10.1 ms, run kernels 0.97 -> 0.65 us a pixel; digit stage cost 14.9 -> 7.7 ms of the render.
// Byte-identical (check_render_frames; the LCD SIMD path on the board, -DDIGIT_VERIFY).
// The blend of MODE 0 / 1 runs on the LCD build: the S3's 128-bit SIMD (PIE), 8 strip pixels a step. Per pixel the
// scalar part only finds the coverage T (0..256) and colour; the blend is blend565T's exactly, on 16-bit lanes:
// channels expanded as expand565, out = a + floor((d T + 128) / 256) with d = b - a, computed as
// floor(2 d T / 256) - floor(d T / 256) (ee.vmul.s16 = the product shifted right by SAR, floor; SAR = 8 throughout,
// field shifts are multiplies by powers of two). T = 0 rewrites a pixel bit for bit and T = 256 gives the colour, so
// a run is blended in whole 16-B blocks of its strip row with T = 0 around it (the core owns the row; a run whose
// blocks would leave the row takes the scalar loop). Semantics probed on the board (2026-10-29: vmul floors the
// shifted 32-bit product, keeps its low 16 bits); equal to the scalar path on every run (-DDIGIT_VERIFY).
// AMOLED builds keep the scalar path (check_render_frames proves it on the host).
#if DIGIT_PIE
// The broadcast constants pieBlend reads, in its order (one ee.vldbc.16 each: no spare q registers to keep them).
static const int16_t __attribute__((aligned(16))) PIE_K[24] = {
  0x00f8, 1, 8, 0x00f8,                                                        // red
  0x1f00, 8, 0x001f, 2048, 64, 0x00f8, 8192,                                   // blue
  0x0007, 8192, 128, (int16_t)0xe000, 1, 32, 0x07e0, 32, 4, 8, 0x001c, 16384, 8192 };   // green
// nb blocks of 8 strip pixels at d (16-B aligned, byte-swapped 565) blended toward colours C (565) by T (int16, 0..256).
// q0 strip, q1 colour, q2 T, q5 result, q3 q4 q6 q7 scratch.
TUBE_IRAM static void __attribute__((noinline)) pieBlend(uint16_t *d, const int16_t *T, const uint16_t *C, int nb) {
  const int16_t *k;
  asm volatile(
    "ssai 8\n"
    "1:\n"
    "mov %[k], %[k0]\n"
    "ee.vld.128.ip q0, %[d], 0\n"
    "ee.vld.128.ip q1, %[C], 16\n"
    "ee.vld.128.ip q2, %[T], 16\n"
    // red: strip r5 << 3 sits at bits 3-7 (byte-swapped), the colour's at 11-15
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 0x00f8
    "ee.andq q5, q0, q4\n"
    "ee.vldbc.16.ip q6, %[k], 2\n"   // 1
    "ee.vmul.u16 q7, q1, q6\n"       // c >> 8
    "ee.andq q7, q7, q4\n"
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 8
    "ee.vmul.s16 q6, q5, q4\n"       // >> 5
    "ee.orq q5, q5, q6\n"            // a = r8 behind
    "ee.vmul.s16 q6, q7, q4\n"
    "ee.orq q7, q7, q6\n"            // b = r8 of the mark
    "ee.vsubs.s16 q7, q7, q5\n"      // d
    "ee.vadds.s16 q6, q7, q7\n"
    "ee.vmul.s16 q6, q6, q2\n"       // floor(2 d T / 256)
    "ee.vmul.s16 q7, q7, q2\n"       // floor(d T / 256)
    "ee.vsubs.s16 q6, q6, q7\n"
    "ee.vadds.s16 q5, q5, q6\n"      // r8 out
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 0x00f8
    "ee.andq q5, q5, q4\n"           // r5 << 3: bits 3-7
    // blue: strip b5 at bits 8-12, the colour's at 0-4
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 0x1f00
    "ee.andq q6, q0, q4\n"
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 8
    "ee.vmul.s16 q6, q6, q4\n"       // b5 << 3
    "ee.vmul.s16 q7, q6, q4\n"       // b5 >> 2
    "ee.orq q6, q6, q7\n"            // a
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 0x001f
    "ee.andq q7, q1, q4\n"
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 2048
    "ee.vmul.s16 q3, q7, q4\n"       // b5 << 3
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 64
    "ee.vmul.s16 q7, q7, q4\n"       // b5 >> 2
    "ee.orq q7, q3, q7\n"            // b
    "ee.vsubs.s16 q7, q7, q6\n"
    "ee.vadds.s16 q3, q7, q7\n"
    "ee.vmul.s16 q3, q3, q2\n"
    "ee.vmul.s16 q7, q7, q2\n"
    "ee.vsubs.s16 q3, q3, q7\n"
    "ee.vadds.s16 q6, q6, q3\n"      // b8 out
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 0x00f8
    "ee.andq q6, q6, q4\n"
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 8192
    "ee.vmul.s16 q6, q6, q4\n"       // << 5: b5 at bits 8-12
    "ee.orq q5, q5, q6\n"
    // green: strip g[5:3] at bits 0-2, g[2:0] at 13-15; the colour's g6 at 5-10
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 0x0007
    "ee.andq q6, q0, q4\n"
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 8192
    "ee.vmul.s16 q7, q6, q4\n"       // << 5
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 128
    "ee.vmul.s16 q6, q6, q4\n"       // >> 1
    "ee.orq q6, q6, q7\n"
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 0xe000
    "ee.andq q7, q0, q4\n"
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 1
    "ee.vmul.u16 q7, q7, q4\n"       // >> 8 (unsigned)
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 32
    "ee.vmul.s16 q7, q7, q4\n"       // >> 3: g[2:0] << 2
    "ee.orq q6, q6, q7\n"            // a = g8 behind
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 0x07e0
    "ee.andq q7, q1, q4\n"
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 32
    "ee.vmul.s16 q7, q7, q4\n"       // g6 << 2
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 4
    "ee.vmul.s16 q3, q7, q4\n"       // g6 >> 4
    "ee.orq q7, q7, q3\n"            // b
    "ee.vsubs.s16 q7, q7, q6\n"
    "ee.vadds.s16 q3, q7, q7\n"
    "ee.vmul.s16 q3, q3, q2\n"
    "ee.vmul.s16 q7, q7, q2\n"
    "ee.vsubs.s16 q3, q3, q7\n"
    "ee.vadds.s16 q6, q6, q3\n"      // g8 out
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 8
    "ee.vmul.s16 q7, q6, q4\n"       // >> 5: g[5:3] at bits 0-2
    "ee.orq q5, q5, q7\n"
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 0x001c
    "ee.andq q6, q6, q4\n"
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 16384
    "ee.vmul.s16 q6, q6, q4\n"       // << 6
    "ee.vldbc.16.ip q4, %[k], 2\n"   // 8192
    "ee.vmul.u16 q6, q6, q4\n"       // << 5 (unsigned): g[2:0] at bits 13-15
    "ee.orq q5, q5, q6\n"
    "ee.vst.128.ip q5, %[d], 16\n"
    "addi %[nb], %[nb], -1\n"
    "bnez %[nb], 1b\n"
    : [d] "+r"(d), [T] "+r"(T), [C] "+r"(C), [nb] "+r"(nb), [k] "=&r"(k)
    : [k0] "r"(PIE_K)
    : "memory");
}
#if DIGIT_PIE
// Step 6: drawTube's soft ramp + folded glow (rampRowR / rampRowL, trace mode: blended over the residue) on the SIMD
// blend. The same alpha per pixel as the scalar loop, as T (a >= 1: 256, else (int)(a 256 + 0.5), what rowPxa's blend565
// takes) into the lanes of the whole 16-B blocks around the drawn columns; skipped columns and lanes outside keep T 0
// (pieBlend leaves them as they are). false (nothing written): the blocks would leave the strip [lo, hi) or the lanes.
#define RAMP_LANES 144
TUBE_IRAM static bool __attribute__((noinline)) rampPieR(uint16_t *row, int a0, int aEnd, float ex, float hw, float invW, float invGlow,
                                               bool glow, float glowStrength, float lightK, int x0, int solidLo, int solidHi,
                                               uint16_t fg, const uint16_t *lo, const uint16_t *hi) {
  const int xa = a0 > x0 ? a0 : x0, xb = aEnd + 1 < PANEL_W ? aEnd + 1 : PANEL_W;   // the columns the loop may draw
  if (xb <= xa) return true;
  uint16_t *const blk = (uint16_t *)((uintptr_t)(row + xa) & ~(uintptr_t)15);
  const int lead = (int)(row + xa - blk), nb = (lead + xb - xa + 7) >> 3;
  if (blk < lo || blk + 8 * nb > hi || 8 * nb > RAMP_LANES) return false;
  int16_t T[RAMP_LANES] __attribute__((aligned(16))); uint16_t C[RAMP_LANES] __attribute__((aligned(16)));
  for (int i = 0; i < 8 * nb; i++) { T[i] = 0; C[i] = fg; }
  int xl = xa;   // one past the last column reached
  for (int x = a0; x <= aEnd; x++) {
    float t = glow ? fmx(0, 1 - (x + 0.5f - ex) * invGlow) : 0;
    float a = fmn(1, clampf((ex + hw - x - 0.5f) * invW, 0, 1) + t * t * glowStrength * lightK);
    if (a <= 0) break;
    if (a >= 1 && x >= solidLo && x < solidHi) continue;
    const int Tx = a >= 1 ? 256 : (int)(a * 256 + 0.5f);
    if (Tx <= 0) break;   // the alpha never rises along the walk (see rampRowR): every pixel from here on stays as it is
    if (x >= x0 && x < PANEL_W) { T[lead + x - xa] = (int16_t)Tx; xl = x + 1; }
  }
  if (xl > xa) pieBlend(blk, T, C, (lead + xl - xa + 7) >> 3);
  return true;
}
TUBE_IRAM static bool __attribute__((noinline)) rampPieL(uint16_t *row, int xStart, int bEnd, float exL, float hw, float invW, float invGlow,
                                               bool glow, float glowStrength, float lightKL, int x0, int xi, int solidLo, int solidHi,
                                               uint16_t fg, const uint16_t *lo, const uint16_t *hi) {
  if (bEnd < x0) bEnd = x0;
  int xa = bEnd, xb = xStart + 1; if (xb > xi) xb = xi; if (xb > PANEL_W) xb = PANEL_W;   // drawn columns lie in [xa, xb)
  if (xb <= xa) return true;
  uint16_t *const blk = (uint16_t *)((uintptr_t)(row + xa) & ~(uintptr_t)15);
  const int lead = (int)(row + xa - blk), nb = (lead + xb - xa + 7) >> 3;
  if (blk < lo || blk + 8 * nb > hi || 8 * nb > RAMP_LANES) return false;
  int16_t T[RAMP_LANES] __attribute__((aligned(16))); uint16_t C[RAMP_LANES] __attribute__((aligned(16)));
  for (int i = 0; i < 8 * nb; i++) { T[i] = 0; C[i] = fg; }
  int xf = xb;   // the lowest column reached
  for (int x = xStart; x >= bEnd; x--) {
    float t = glow ? fmx(0, 1 - (exL - (x + 0.5f)) * invGlow) : 0;
    float a = fmn(1, clampf((x + 0.5f - exL + hw) * invW, 0, 1) + t * t * glowStrength * lightKL);
    if (a <= 0) break;
    const int Tx = a >= 1 ? 256 : (int)(a * 256 + 0.5f);
    if (Tx <= 0) break;   // as in rampPieR
    if (x < x0 || x >= xi || x >= PANEL_W) continue;
    if (a >= 1 && x >= solidLo && x < solidHi) continue;
    T[lead + x - xa] = (int16_t)Tx; xf = x;
  }
  if (xf < xb) {   // blocks from the one holding xf to the one holding xb - 1
    const int i0 = (lead + xf - xa) & ~7;
    pieBlend(blk + i0, T + i0, C + i0, ((lead + xb - xa + 7) >> 3) - (i0 >> 3));
  }
  return true;
}
#endif
#ifdef DIGIT_VERIFY
// -DDIGIT_VERIFY: every pieBlend checked against the scalar blend (render_digit_verify, printed by `f`).
static volatile uint32_t digitVerifyPx[2], digitVerifyBad[2];   // per core: both render at once
static inline void digitVerify(int px, int bad) { const int k = esp_cpu_get_core_id() & 1; digitVerifyPx[k] += px; digitVerifyBad[k] += bad; }
void render_digit_verify(uint32_t &px, uint32_t &bad) { px = digitVerifyPx[0] + digitVerifyPx[1]; bad = digitVerifyBad[0] + digitVerifyBad[1]; }
#endif
// A run's lanes for pieBlend: the whole 16-B blocks of its strip row around it, T = 0 outside the run. The lanes are the
// Tube's DigitScratch (never the stack).
struct PieRun {
  int16_t *T; uint16_t *C;
#ifdef DIGIT_VERIFY
  uint16_t *want;
#endif
  uint16_t *blk; int lead, nb;
  explicit PieRun(DigitScratch &ds) : T(ds.T), C(ds.C) {
#ifdef DIGIT_VERIFY
    want = ds.want;
#endif
  }
  // fb: the run's first strip pixel, column px0, n pixels. false: its blocks would leave the strip row (scalar path).
  static inline bool fits(const uint16_t *fb, int px0, int n) {
    const int lead = (int)(((uintptr_t)fb & 15) >> 1), nb = (lead + n + 7) >> 3;
    return px0 - lead >= 0 && px0 - lead + nb * 8 <= PANEL_W && nb * 8 <= PIE_LANES;
  }
  inline bool begin(uint16_t *fb, int px0, int n) {
    if (!fits(fb, px0, n)) return false;
    lead = (int)(((uintptr_t)fb & 15) >> 1); nb = (lead + n + 7) >> 3;
    blk = fb - lead;
    for (int i = 0; i < lead; i++) T[i] = 0;
    for (int i = lead + n; i < nb * 8; i++) T[i] = 0;
    return true;
  }
  inline void end() {
#ifdef DIGIT_VERIFY
    for (int i = 0; i < nb * 8; i++) {
      const int t = T[i];
      want[i] = t <= 0 ? blk[i] : t >= 256 ? __builtin_bswap16(C[i]) : blendLanesSw(lanesSw(blk[i]), lanes565(C[i]), t);
    }
#endif
    pieBlend(blk, T, C, nb);
#ifdef DIGIT_VERIFY
    int bad = 0; for (int i = 0; i < nb * 8; i++) bad += blk[i] != want[i];
    digitVerify(nb * 8, bad);
#endif
  }
};
#endif
// fb: the run's first strip pixel (column px0), n pixels from glyph texel a / c on. scaleT: MODE 0's coverage scale.
template <int MODE>
static void __attribute__((noinline)) spriteRunInt(uint16_t *fb, int px0, int n, const uint8_t *a, const uint16_t *c, int scaleT, int T, int C,
                                                   DigitScratch &ds) {
#if DIGIT_PIE
  if (MODE < 2) {
    PieRun r(ds);
    if (r.begin(fb, px0, n)) {
      int16_t *t = r.T + r.lead; uint16_t *cc = r.C + r.lead;
      for (int i = 0; i < n; i++) {
        int covT = LUT_alphaT16[a[i]];   // 0 for alpha 0
        if (MODE == 0) covT = covT * scaleT >> 8;
        t[i] = (int16_t)covT; cc[i] = c[i];
      }
      r.end();
      return;
    }
  }
#endif
  LiquidMemo memo;
  for (int i = 0; i < n; i++) {
    const int al = a[i]; if (!al) continue;
    int covT = LUT_alphaT16[al];
    if (MODE == 0) { covT = covT * scaleT >> 8; if (covT <= 0) continue; }
    if (MODE >= 2) {
      const uint16_t bg = __builtin_bswap16(fb[i]), col = memo.get(bg, c[i], covT, T, C, MODE == 3);
      fb[i] = __builtin_bswap16(covT >= 256 ? col : blend565T(bg, col, covT));
    } else fb[i] = covT >= 256 ? __builtin_bswap16(c[i]) : blendLanesSw(lanesSw(fb[i]), lanes565(c[i]), covT);
  }
}

static inline int clampI(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }
// Sub-pixel parallax (sprite digits): destination column cx samples taps (cx, cy), (cx-1, cy), (cx, cy-1),
// (cx-1, cy-1) of one plane (weights 1/65536, taps outside the glyph are 0): coverage and premultiplied colour
// (mix565, divide-free), as the generic path. The taps take their own pass over a run (the left taps' alphas and colours carried):
// each pixel's coverage and colour, then the blend (SIMD lanes, or a scalar second pass). In one loop the weights,
// carries, row pointers and the blend did not fit the register file and spilled every pixel.
// Zero rows stand in for rows outside the glyph (a glyph is at most 128 columns wide in the draw, see gw).
static const uint8_t ZERO_A[256] = {};
static const uint16_t ZERO_C[256] = {};
struct FracRun {
  const uint8_t *a0, *a1;    // alpha rows cy, cy - 1 at the run's first column (ZERO_A outside the glyph)
  const uint16_t *c0, *c1;   // their colours (ZERO_C outside the glyph)
  int nIn;                   // columns whose own taps lie in the glyph (cx < w); the rest (the overhang) read 0
  int p0, p1, q0, q1;        // the first column's left alphas and colours
  int w00, w10, w01, w11, scaleT, T, C;
  DigitScratch *ds;
#if DIGIT_PIE
  FracMemo *memo;
#endif
};
// The taps of one destination column: its coverage (0 = nothing) and, when covered, its colour. p0 / p1 / q0 / q1 carry
// the column's own taps to the next one as its left taps.
template <int MODE>
static inline __attribute__((always_inline)) int fracTap(int n0, int n1, uint32_t k0, uint32_t k1, int &p0, int &p1, int &q0, int &q1,
                                                          int w00, int w10, int w01, int w11, int scaleT, uint16_t &col) {
  const int a00 = n0 * w00, a10 = p0 * w10, a01 = n1 * w01, a11 = p1 * w11;
  const int al = (a00 + a10 + a01 + a11 + 32768) >> 16;
  int covT = al ? LUT_alphaT16[al] : 0;
  if (MODE == 0) covT = covT * scaleT >> 8;
  if (covT > 0) col = mix565(a00, a10, a01, a11, k0, (uint32_t)q0, k1, (uint32_t)q1, al);
  p0 = n0; p1 = n1; q0 = (int)k0; q1 = (int)k1;
  return covT;
}
#if DIGIT_PIE
static_assert(FRAC_MEMO_MAX == FRAC_RUN_MAX, "FracMemo holds one run part");
#endif
// Scalar: the taps into the scratch row (covT << 16 | colour), then the blend. AMOLED, and runs the SIMD path does not take.
template <int MODE>
static void __attribute__((noinline)) spriteRunFracScalar(uint16_t *fb, int n, const FracRun &f) {
  const uint8_t *a0 = f.a0, *a1 = f.a1; const uint16_t *c0 = f.c0, *c1 = f.c1;
  const int w00 = f.w00, w10 = f.w10, w01 = f.w01, w11 = f.w11, scaleT = f.scaleT;
  int p0 = f.p0, p1 = f.p1, q0 = f.q0, q1 = f.q1, nIn = f.nIn;
  uint32_t *const row = f.ds->row;   // covT << 16 | colour, 0 = nothing
  LiquidMemo memo;
  while (n > 0) {
    const int m = n < FRAC_RUN_MAX ? n : FRAC_RUN_MAX, mIn = nIn < m ? nIn : m;
    uint32_t *o = row;
    for (int i = 0; i < mIn; i++) {
      uint16_t col = 0; const int covT = fracTap<MODE>(a0[i], a1[i], c0[i], c1[i], p0, p1, q0, q1, w00, w10, w01, w11, scaleT, col);
      *o++ = covT > 0 ? (uint32_t)covT << 16 | col : 0;
    }
    for (int i = mIn; i < m; i++) {
      uint16_t col = 0; const int covT = fracTap<MODE>(0, 0, 0, 0, p0, p1, q0, q1, w00, w10, w01, w11, scaleT, col);
      *o++ = covT > 0 ? (uint32_t)covT << 16 | col : 0;
    }
    for (int i = 0; i < m; i++) {
      const uint32_t v = row[i]; if (!v) continue;
      const int covT = (int)(v >> 16); const uint16_t col = (uint16_t)(v & 0xffff);
      if (MODE >= 2) {
        int cT = covT; const uint16_t bg = __builtin_bswap16(fb[i]), cc = memo.get(bg, col, cT, f.T, f.C, MODE == 3);
        fb[i] = __builtin_bswap16(cT >= 256 ? cc : blend565T(bg, cc, cT));
      } else fb[i] = covT >= 256 ? __builtin_bswap16(col) : blendLanesSw(lanesSw(fb[i]), lanes565(col), covT);
    }
    fb += m; a0 += m; a1 += m; c0 += m; c1 += m; n -= m; nIn -= mIn;
  }
}
#if DIGIT_PIE
// SIMD (MODE 0 / 1, one part): the taps straight into the lanes; a run repeating the last one's source row and
// columns (FracMemo) takes its lanes from there and only blends. Memo hits: ~1/3 of the hours wet rows under the user
// preset's bottomLens; hours run kernels 7.2 -> 6.4 ms (2026-10-29, same boot, memo off / on).
template <int MODE>
static void __attribute__((noinline)) spriteRunFracPie(uint16_t *fb, int px0, int n, const FracRun &f) {
  const uint8_t *a0 = f.a0, *a1 = f.a1; const uint16_t *c0 = f.c0, *c1 = f.c1;
  const int w00 = f.w00, w10 = f.w10, w01 = f.w01, w11 = f.w11, scaleT = f.scaleT, nIn = f.nIn;
  int p0 = f.p0, p1 = f.p1, q0 = f.q0, q1 = f.q1;
  PieRun r(*f.ds); r.begin(fb, px0, n);   // fits: checked by spriteRunFrac
  FracMemo *mm = f.memo;
  if (mm && mm->valid && mm->a0 == a0 && mm->a1 == a1 && mm->cq == c0 && mm->m == n && mm->nIn == nIn && mm->p0 == p0 && mm->p1 == p1
      && mm->q0 == q0 && mm->q1 == q1 && mm->scaleT == scaleT && mm->mode == MODE && mm->w00 == w00 && mm->w10 == w10 && mm->w01 == w01 && mm->w11 == w11) {
    memcpy(r.T + r.lead, mm->T, n * sizeof(int16_t)); memcpy(r.C + r.lead, mm->C, n * sizeof(uint16_t));
#ifdef DIGIT_VERIFY
    { int bad = 0;   // the taps again: the memo must equal them
      for (int i = 0; i < n; i++) {
        uint16_t col = 0;
        const int covT = fracTap<MODE>(i < nIn ? a0[i] : 0, i < nIn ? a1[i] : 0, i < nIn ? c0[i] : 0, i < nIn ? c1[i] : 0, p0, p1, q0, q1,
                                       w00, w10, w01, w11, scaleT, col);
        const int want = covT > 0 ? covT : 0;
        bad += r.T[r.lead + i] != want || (want && r.C[r.lead + i] != col);
      }
      digitVerify(n, bad); }
#endif
  } else {
    if (mm) { mm->a0 = a0; mm->a1 = a1; mm->cq = c0; mm->m = n; mm->nIn = nIn; mm->p0 = p0; mm->p1 = p1; mm->q0 = q0; mm->q1 = q1;
              mm->scaleT = scaleT; mm->mode = MODE; mm->w00 = w00; mm->w10 = w10; mm->w01 = w01; mm->w11 = w11; }
    int16_t *t = r.T + r.lead; uint16_t *cc = r.C + r.lead;
    for (int i = 0; i < nIn; i++) {
      uint16_t col = 0; const int covT = fracTap<MODE>(a0[i], a1[i], c0[i], c1[i], p0, p1, q0, q1, w00, w10, w01, w11, scaleT, col);
      t[i] = (int16_t)(covT > 0 ? covT : 0); if (covT > 0) cc[i] = col;
    }
    for (int i = nIn; i < n; i++) {
      uint16_t col = 0; const int covT = fracTap<MODE>(0, 0, 0, 0, p0, p1, q0, q1, w00, w10, w01, w11, scaleT, col);
      t[i] = (int16_t)(covT > 0 ? covT : 0); if (covT > 0) cc[i] = col;
    }
    if (mm) { memcpy(mm->T, r.T + r.lead, n * sizeof(int16_t)); memcpy(mm->C, r.C + r.lead, n * sizeof(uint16_t)); mm->valid = true; }
  }
  r.end();
}
#endif
// fb: the run's first strip pixel (column px0), n pixels. The scalar row and the SIMD lanes are the Tube's scratch.
template <int MODE>
static inline void spriteRunFrac(uint16_t *fb, int px0, int n, const FracRun &f) {
#if DIGIT_PIE
  if (MODE < 2 && n <= FRAC_RUN_MAX && PieRun::fits(fb, px0, n)) { spriteRunFracPie<MODE>(fb, px0, n, f); return; }
#endif
  spriteRunFracScalar<MODE>(fb, n, f);
}
// One glyph row of one copy (dry or wet, each at its parallax): panel columns [px0, px1) map to glyph
// columns from cx0; cut into runs and blit. run / plain inline into copies (one call per glyph row); seg is one
// function for every mode (its four templated copies inlined three times made copies ~17 KB, more than the 16 KB
// instruction cache).
struct SpriteRow {
  const Tube &t; const Mark &mark; const ScaledGlyph &g; int y, ry;
  uint16_t *fb;          // strip row y
  const DigitRow *dr;    // this row's liquid interval
  int liqMode, Tuse;
  int xD, xW, dA0, dA1, dB0, dB1, w0, w1;   // the glyph's copies at their whole-px parallax (planSpriteGlyph)
  // A copy's tap weights (1/65536: w00 own tap, w10 left, w01 above, w11 above-left; frac false: the one tap).
  struct Taps { int w00, w10, w01, w11; bool frac; } tD, tW;
  void __attribute__((noinline)) copies(bool dry, int cyD, bool wet, int cy) const {
    if (dry) {
      if (dA1 > dA0) run(xD + dA0, xD + dA1, dA0, cyD, tD);
      if (dB1 > dB0) run(xD + dB0, xD + dB1, dB0, cyD, tD);
    }
    if (wet) run(xW + w0, xW + w1, w0, cy, tW);
  }
  inline __attribute__((always_inline)) void run(int px0, int px1, int cx0, int cy, const Taps &tp) const {
    if (px0 < 0) { cx0 += -px0; px0 = 0; }
    if (px1 > PANEL_W) px1 = PANEL_W;
    if (px0 < px1) plain(px0, px1, cx0, cy, tp);
  }
  inline __attribute__((always_inline)) void plain(int px0, int px1, int cx0, int cy, const Taps &tp) const {
    if (mark.onTop) { seg(0, px0, px1, cx0, cy, false, 256, tp); return; }
    const int dT = t.pal.dryT[ry], Li = dr->Li, Hi = dr->Hi;
    if (Hi <= Li || px1 <= Li || px0 >= Hi) { seg(0, px0, px1, cx0, cy, false, dT, tp); return; }
    if (px0 < Li) { seg(0, px0, Li, cx0, cy, false, dT, tp); cx0 += Li - px0; px0 = Li; }
    const int e = Hi < px1 ? Hi : px1;
    seg(liqMode, px0, e, cx0, cy, true, 256, tp);
    cx0 += e - px0; px0 = e;
    if (px0 < px1) seg(0, px0, px1, cx0, cy, false, dT, tp);
  }
  // A run on one plane (L: behind liquid) and compositor mode, clipped to the glyph row's covered columns.
  void __attribute__((noinline)) seg(int mode, int px0, int px1, int cx0, int cy, bool L, int scaleT, const Taps &tp) const {
    if (px0 >= px1) return;
    const uint8_t *aP = L ? g.aw : g.a; const uint16_t *cP = L ? g.cw : g.c;
    const bool frac = tp.frac;
    if (const uint8_t *sp = g.span[L ? 1 : 0]) {   // clip to the columns that have coverage
      int s0 = 0, s1 = 0;
      if (!frac) { s0 = sp[cy * 2]; s1 = sp[cy * 2 + 1]; }
      else {   // destination cx draws taps cx and cx - 1 of rows cy and cy - 1: the union of their spans, one wider
        s0 = 1 << 30; s1 = 0;
        if (cy < g.h && sp[cy * 2 + 1] > sp[cy * 2]) { s0 = sp[cy * 2]; s1 = sp[cy * 2 + 1] + 1; }
        if (cy > 0 && sp[cy * 2 - 1] > sp[cy * 2 - 2]) { if (sp[cy * 2 - 2] < s0) s0 = sp[cy * 2 - 2]; if (sp[cy * 2 - 1] + 1 > s1) s1 = sp[cy * 2 - 1] + 1; }
      }
      if (s1 <= s0) return;
      const int lo = px0 + (s0 - cx0), hi = px0 + (s1 - cx0);
      if (lo > px0) { cx0 += lo - px0; px0 = lo; }
      if (hi < px1) px1 = hi;
      if (px0 >= px1) return;
    }
#ifdef DIGIT_PROF
    t.prof[(frac ? 4 : 2) + (mode ? 1 : 0)] += px1 - px0; t.prof[7]++;
#endif
#ifdef DIGIT_PROF
    const uint32_t c0 = esp_cpu_get_cycle_count();
#endif
    uint16_t *const d = fb + px0; const int n = px1 - px0;
    if (!frac) {
      const uint8_t *a = aP + cy * g.w + cx0; const uint16_t *c = cP + cy * g.w + cx0;
      switch (mode) {
        case 0: spriteRunInt<0>(d, px0, n, a, c, scaleT, Tuse, mark.Cin, *t.scratch); break;
        case 1: spriteRunInt<1>(d, px0, n, a, c, scaleT, Tuse, mark.Cin, *t.scratch); break;
        case 2: spriteRunInt<2>(d, px0, n, a, c, scaleT, Tuse, mark.Cin, *t.scratch); break;
        default: spriteRunInt<3>(d, px0, n, a, c, scaleT, Tuse, mark.Cin, *t.scratch); break;
      }
    } else {
      const bool r0 = cy >= 0 && cy < g.h, r1 = cy >= 1 && cy - 1 < g.h;
      const int wz = r0 || r1 ? g.w : 256;   // zero rows: any column reads 0
      FracRun f;
      f.a0 = (r0 ? aP + cy * g.w : ZERO_A) + cx0; f.a1 = (r1 ? aP + (cy - 1) * g.w : ZERO_A) + cx0;
      f.c0 = (r0 ? cP + cy * g.w : ZERO_C) + cx0; f.c1 = (r1 ? cP + (cy - 1) * g.w : ZERO_C) + cx0;
      f.nIn = clampI(wz - cx0, 0, n);
      const bool left = cx0 >= 1 && cx0 - 1 < wz;
      f.p0 = left ? f.a0[-1] : 0; f.p1 = left ? f.a1[-1] : 0; f.q0 = left ? f.c0[-1] : 0; f.q1 = left ? f.c1[-1] : 0;
      f.w00 = tp.w00; f.w10 = tp.w10; f.w01 = tp.w01; f.w11 = tp.w11; f.scaleT = scaleT; f.T = Tuse; f.C = mark.Cin; f.ds = t.scratch;
#if DIGIT_PIE
      f.memo = t.fracMemo;
#endif
      switch (mode) {
        case 0: spriteRunFrac<0>(d, px0, n, f); break;
        case 1: spriteRunFrac<1>(d, px0, n, f); break;
        case 2: spriteRunFrac<2>(d, px0, n, f); break;
        default: spriteRunFrac<3>(d, px0, n, f); break;
      }
    }
#ifdef DIGIT_PROF
    t.profCyc[0] += esp_cpu_get_cycle_count() - c0;
#endif
  }
};

// One row's facts (DigitRow, all but depth) for a mark layer.
TICK_IRAM static void __attribute__((noinline)) markRowFacts(DigitRow &r, int ry, const Mark &mark) {
  const BandInfo *band = mark.onTop ? nullptr : mark.edges.band;
  r.Li = r.Hi = 0;
  if (!mark.onTop) { r.Li = (int)fceil(mark.edges.lo[ry]); r.Hi = (int)fceil(mark.edges.hi[ry]); }
  r.nb = 0;
  if (!band) return;
  // Where bandMark can return true on this row: per side with a stroke, its footprint in the render
  // frame is -hw - 0.5 < tt < w + 0.5 (see bandMark); widened by a pixel each way and mirrored back.
  for (int side = 0; side < 2; side++) {
    const float wEff = band->w[side][ry]; if (wEff <= 0) continue;
    const float xm = band->xm[side][ry], hw = band->hw;
    const float lo = side == 0 ? xm - hw - 1 : xm - wEff - 1, hi = side == 0 ? xm + wEff : xm + hw;
    int r0 = (int)ffloor(lo) - 1, r1 = (int)fceil(hi) + 1;
    if (band->mirror) { const int t0 = band->L - 1 - r1, t1 = band->L - 1 - r0; r0 = t0; r1 = t1; }
    r.b0[r.nb] = r0; r.b1[r.nb] = r1 + 1; r.nb++;
  }
  if (r.nb == 2 && r.b0[1] < r.b0[0]) { int t0 = r.b0[0], t1 = r.b1[0]; r.b0[0] = r.b0[1]; r.b1[0] = r.b1[1]; r.b0[1] = t0; r.b1[1] = t1; }
  if (r.nb == 2 && r.b0[1] < r.b1[0]) { if (r.b1[1] > r.b1[0]) r.b1[0] = r.b1[1]; r.nb = 1; }   // overlapping: one footprint
}
// The row facts every glyph of a sprite layer shares (DigitRow), for the rows spriteGlyphRows visits in [r0, r1).
void Tube::spriteRowFacts(int y0, const Labels &lb, const Mark &mark, int r0, int r1) const {
  int a0 = lb.dryRy0 < lb.ry0 ? lb.dryRy0 : lb.ry0, a1 = lb.dryRy1 > lb.ry1 ? lb.dryRy1 : lb.ry1;
  if (a0 < r0) a0 = r0; if (a1 > r1 - 1) a1 = r1 - 1;
  for (int ry = a0; ry <= a1; ry++) {
    const int y = y0 + ry;
    if (y < baseY || y >= baseY + H) continue;
    markRowFacts(digitRows[ry], ry, mark);
  }
}
// The plan of one sprite glyph (its column set-up): false = the glyph draws nothing.
// Column ranges of the two copies from the wet shares (generic path: dcol / wcol): the dry copy on the columns before
// the first and after the last one with any liquid, the wet copy on the columns that are liquid on every row (an
// interval: the rows' intervals intersected). Every other column is under a meniscus and takes drawRampColumn (a share-0
// column between two meniscus ones included: there it draws what the dry copy would). A column shows one image.
static bool planSpriteGlyph(const ScaledGlyph &g, int x, int y0, int yTop, const Labels &lb, const Warp &warp, GlyphPlan &gp) {
  if (lb.vertical) x -= g.w - lb.bh;   // the baked shadow margin lies below the body as read: left of it on the panel
  const int gw = g.w > 128 ? 128 : g.w;
  planTaps(lb, gp);
  // copy columns c at panel x + i + c (each copy at its whole-px parallax), one more for a fractional overhang
  const int xD = x + gp.ixD, xW = x + gp.ixW, gwD = gw + (gp.wxD ? 1 : 0), gwW = gw + (gp.wxW ? 1 : 0);
  int dA0 = 0, dA1 = 0, dB0 = gwD, dB1 = gwD, w0 = 0, w1 = gwW;
  if (!warp.all()) {
    while (dA1 < gwD && warp(xD + dA1) == 0) dA1++;
    if (dA1 < gwD) while (warp(xD + dB0 - 1) == 0) dB0--;   // stops at dA1, whose share is > 0
    int a = w0; while (a < w1 && warp(xW + a) != 256) a++;
    int b = a; while (b < w1 && warp(xW + b) == 256) b++;
    w0 = a; w1 = b;
  }
  // under a meniscus: every column that neither copy draws (shares strictly between, or 0 between two such columns)
  const int xr0 = x + (gp.ixD < gp.ixW ? gp.ixD : gp.ixW), xr1 = x + gw + (gp.ixD > gp.ixW ? gp.ixD : gp.ixW);
  auto ramp = [&](int xd, int k) { return k != 256 && (k != 0 || (xd - xD >= dA1 && xd - xD < dB0)); };
  gp.rampLo = 1; gp.rampHi = 0; gp.rampR0 = (int16_t)lb.H; gp.rampR1 = -1;
  if (!warp.all()) for (int xd = xr0; xd <= xr1; xd++) {
    const int k = warp(xd);
    if (!ramp(xd, k)) continue;
    if (gp.rampLo > gp.rampHi) gp.rampLo = (int16_t)xd;
    gp.rampHi = (int16_t)xd;
    rampColumnRows(g.w, g.h, x, xd, k, y0, yTop, lb, false, gp.rampR0, gp.rampR1);
  }
  const bool anyRamp = gp.rampLo <= gp.rampHi;
  const bool anyDry = dA1 > dA0 || dB1 > dB0, anyWet = w1 > w0;
  if (!anyDry && !anyWet && !anyRamp) return false;
  gp.g = &g; gp.pass = 0; gp.d = 0; gp.anyDry = anyDry; gp.anyWet = anyWet; gp.x = (int16_t)x; gp.yTop = (int16_t)yTop;
  gp.dA0 = (int16_t)dA0; gp.dA1 = (int16_t)dA1; gp.dB0 = (int16_t)dB0; gp.dB1 = (int16_t)dB1; gp.w0 = (int16_t)w0; gp.w1 = (int16_t)w1;
  return true;
}
// A planned sprite glyph over tube rows [r0, r1): its copies' glyph rows, then its meniscus columns.
void Tube::spriteGlyphRows(const GlyphPlan &gp, int y0, const Labels &lb, const Warp &warp, const Mark &mark, int r0, int r1) const {
  const ScaledGlyph &g = *gp.g;
  const int x = gp.x, yTop = gp.yTop, sourceTop = yTop - y0;
  const bool anyDry = gp.anyDry, anyWet = gp.anyWet;
  auto taps = [](int wx1, int wy1) {
    const int wx0 = 256 - wx1, wy0 = 256 - wy1;
    return SpriteRow::Taps{wx0 * wy0, wx1 * wy0, wx0 * wy1, wx1 * wy1, wx1 != 0 || wy1 != 0};
  };
  SpriteRow r{*this, mark, g, 0, 0, nullptr, nullptr, !mark.bakedT ? 2 : mark.Cin <= 0 ? 1 : 3, mark.T, x + gp.ixD, x + gp.ixW,
              gp.dA0, gp.dA1, gp.dB0, gp.dB1, gp.w0, gp.w1, taps(gp.wxD, gp.wyD), taps(gp.wxW, gp.wyW)};
  int a0 = lb.dryRy0 < lb.ry0 ? lb.dryRy0 : lb.ry0, a1 = lb.dryRy1 > lb.ry1 ? lb.dryRy1 : lb.ry1;
  if (a0 < r0) a0 = r0; if (a1 > r1 - 1) a1 = r1 - 1;
  for (int ry = a0; ry <= a1; ry++) {
    const int y = y0 + ry;
    if (y < baseY || y >= baseY + H) continue;
#ifdef DIGIT_PROF
    prof[1]++;
#endif
    const int cyD = lb.drySourceRows[ry] - sourceTop - gp.iyD, cy = lb.sourceRows[ry] - sourceTop - gp.iyW;
    const bool dry = anyDry && ry >= lb.dryRy0 && ry <= lb.dryRy1 && cyD >= 0 && (cyD < g.h || (cyD == g.h && gp.wyD));
    const bool wet = anyWet && ry >= lb.ry0 && ry <= lb.ry1 && cy >= 0 && (cy < g.h || (cy == g.h && gp.wyW));
    if (!dry && !wet) continue;
    r.y = y; r.ry = ry; r.fb = FB + (y - baseY) * PANEL_W; r.dr = digitRows + ry;
    TCLIP(r.fb, PANEL_W);
    r.copies(dry, cyD, wet, cy);
  }
  const int ra = r0 > gp.rampR0 ? r0 : gp.rampR0, rb = r1 < gp.rampR1 + 1 ? r1 : gp.rampR1 + 1;
  if (ra >= rb) return;
  const int dA1 = gp.dA1, dB0 = gp.dB0, xD = x + gp.ixD;
  auto ramp = [&](int xd, int k) { return k != 256 && (k != 0 || (xd - xD >= dA1 && xd - xD < dB0)); };
  const SpriteSampler ss(g);
#ifdef DIGIT_PROF
  const uint32_t c0 = esp_cpu_get_cycle_count();
#endif
  for (int xd = gp.rampLo; xd <= gp.rampHi; xd++) { const int k = warp(xd); if (ramp(xd, k)) drawRampColumn(ss, x, xd, k, y0, yTop, lb, mark, false, ra, rb); }
#ifdef DIGIT_PROF
  profCyc[2] += esp_cpu_get_cycle_count() - c0;
#endif
}

// ---------------------------------------------------------------------------------------------
// ticks: one call per tick row
// ---------------------------------------------------------------------------------------------
// Profile (2026-10-29, LCD native, wide tubes, user preset; -DTICK_PROF): ~3.8 ms a tube for ~320 tick rows (~1,600
// px), compute-bound (a row drawn again at once: 93 % of its first draw) plus one PSRAM line fill a row (~1.3 us).
// Through Mark::operator() a pixel was ~575 cycles: the out-of-line operator, bandMark's footprint test on every pixel
// while the surface band is on, wetColourT -> throughLiquid (two lumas), the emboss, blend565T. Hours, pinned, now
// ~1.5 ms: line fills, the row facts, memo fills. The kernels sit in IRAM on the LCD (TICK_IRAM): from flash, behind
// the 16 KB instruction cache both render cores share, the same rows took ~1.7x as long. Here a plot / plotF row is one call. A row wholly
// behind liquid or wholly not, clear of the band footprints and of the strip's ends (nearly all of them), writes per
// pixel what TickMemo holds for the pixel behind: along a row the pixel behind is the liquid's (or the back's) row
// colour, so after the first pixel each one is a load, a compare and a store. Other rows go pixel by pixel (tickPx),
// band-footprint pixels through Mark::operator(). A pixel's ops read and write only that pixel, so pixels may go in any
// order, the two ops of one pixel (plotF's edge columns: emboss, then body) in theirs. Byte-identical (check_render_frames).
struct TickInk { uint16_t c, hi, lo; };   // a tick colour and its emboss highlight / shadow
struct TickRows {
  const Mark &mark; uint16_t *fb; DigitRow *rows; const uint16_t *dryT;   // fb: strip row of tick row 0
  int y0, H, T, C, embT; float emb; bool rear, emboss;   // emb: tickEmboss clamped (plotF's edge-column shares)
  bool generic;   // every pixel through Mark::operator() (no row facts: render_init failed, or a baked mark)
  bool depth;     // rows[].depth holds the lens depth of every row (else computed per base row)
  int r0 = 0, r1 = 0;   // the tube rows this call draws (step 9: a band, or 0, H)
#ifdef TICK_PROF
  uint32_t *prof;
#endif
};
// One tick op over the pixel behind bg (565) of a known kind: Mark::operator()'s colour and coverage (w: bg's colour
// through the liquid, when wet). blend565T gives bg for a coverage <= 0, where Mark::operator() writes nothing.
static inline uint16_t tickOp(const TickRows &k, const TickInk &ink, bool wet, int dT, uint16_t bg, uint16_t w, int covT, int rel) {
  uint16_t col; int cv = covT;
  if (wet) { col = rel > 0 ? embossHi(w) : rel < 0 ? embossLo(w) : w; if (rel) cv = cv * k.T >> 8; }   // rear relief fades with the liquid's opacity
  else { col = rel > 0 ? ink.hi : rel < 0 ? ink.lo : ink.c; if (k.rear) cv = cv * dT >> 8; }        // rear marks vanish behind the wall band
  return blend565T(bg, col, cv);
}
// Column class i of a row (TickMemo::o) over the pixel behind bg: its ops in their order (w0: bg through the liquid).
static uint16_t tickColumn(const TickRows &k, const TickInk &ink, bool wet, int dT, uint16_t bg, uint16_t w0, int i, int fT, int eA, int eF) {
  auto wc = [&](uint16_t b) { return wet ? throughLiquid(b, ink.c, k.T, k.C) : (uint16_t)0; };
  switch (i) {
    case 0: return tickOp(k, ink, wet, dT, bg, w0, eA, 1);
    case 1:
      if (!fT) return tickOp(k, ink, wet, dT, bg, w0, 256, 0);
      if (k.emboss) { const uint16_t b = tickOp(k, ink, wet, dT, bg, w0, eF, 1); return tickOp(k, ink, wet, dT, b, wc(b), 256 - fT, 0); }
      return tickOp(k, ink, wet, dT, bg, w0, 256 - fT, 0);
    case 2: return tickOp(k, ink, wet, dT, bg, w0, 256, 0);
    case 3:
      if (!fT) return tickOp(k, ink, wet, dT, bg, w0, eA, -1);
      if (k.emboss) { const uint16_t b = tickOp(k, ink, wet, dT, bg, w0, eA, -1); return tickOp(k, ink, wet, dT, b, wc(b), fT, 0); }
      return tickOp(k, ink, wet, dT, bg, w0, fT, 0);
    default: return tickOp(k, ink, wet, dT, bg, w0, eF, -1);
  }
}
// The memo for the pixel behind raw: every column class the row has (plot: no x + w + 1; without emboss no x - 1).
TICK_IRAM static void __attribute__((noinline)) tickMemoFill(const TickRows &k, const TickInk &ink, TickMemo &m, bool wet, int dT, uint16_t raw,
                                                             int fT, int eA, int eF) {
  const uint16_t bg = __builtin_bswap16(raw), w0 = wet ? throughLiquid(bg, ink.c, k.T, k.C) : 0;
  m.raw = raw; m.c = ink.c; m.fT = (int16_t)fT;
  for (int i = 0; i < 5; i++)
    m.o[i] = (i == 0 && !k.emboss) || (i == 4 && (!fT || !k.emboss)) ? 0 : __builtin_bswap16(tickColumn(k, ink, wet, dT, bg, w0, i, fT, eA, eF));
}
// A pixel of a memo row that shows another pixel behind than the memo's (strip layout in and out).
static uint16_t __attribute__((noinline)) tickColumnRaw(const TickRows &k, const TickInk &ink, bool wet, int dT, uint16_t raw, int i, int fT, int eA, int eF) {
  const uint16_t bg = __builtin_bswap16(raw);
  return __builtin_bswap16(tickColumn(k, ink, wet, dT, bg, wet ? throughLiquid(bg, ink.c, k.T, k.C) : 0, i, fT, eA, eF));
}
// One op of a row that straddles the liquid's edge, a band footprint or the strip's ends: Mark::operator() given the
// row's facts.
TICK_IRAM static void __attribute__((noinline)) tickPx(const TickRows &k, const TickInk &ink, const DigitRow &r, int dT, uint16_t *row,
                                              int y, int px, int covT, int rel) {
  if (r.nb && ((px >= r.b0[0] && px < r.b1[0]) || (r.nb > 1 && px >= r.b0[1] && px < r.b1[1]))) { k.mark(px, y, ink.c, covT, rel); return; }
  if ((unsigned)px >= (unsigned)PANEL_W) return;
  uint16_t *const d = row + px;
  const uint16_t bg = __builtin_bswap16(*d);
  uint16_t col; int cv = covT;
  if (k.rear && px >= r.Li && px < r.Hi) {
    col = throughLiquid(bg, ink.c, k.T, k.C);
    if (rel) { col = rel > 0 ? embossHi(col) : embossLo(col); cv = cv * k.T >> 8; }   // rear relief fades with the liquid's opacity
  } else {
    if (k.rear) cv = cv * dT >> 8;   // rear marks vanish behind the wall band
    col = rel > 0 ? ink.hi : rel < 0 ? ink.lo : ink.c;
  }
  if (cv <= 0) return;   // on top Mark::operator() writes the pixel back unchanged
  *d = __builtin_bswap16(cv >= 256 ? col : blend565T(bg, col, cv));
}
// One plot (fT 0: columns x .. x + w - 1, emboss eA at x - 1 / x + w) or plotF row (edge columns x / x + w at
// 256 - fT / fT, emboss eA at x - 1 / x + w and eF at x / x + w + 1) of tick row ry (0 <= ry < H, checked by the caller).
TICK_IRAM static void __attribute__((noinline)) tickRow(const TickRows &k, const TickInk &ink, int ry, int x, int w, int fT, int eA, int eF) {
  const int y = k.y0 + ry;
  const bool emb = k.emboss;
  if (k.generic) {
    const uint16_t c = ink.c;
    if (!fT) {
      if (emb) { k.mark(x - 1, y, c, eA, 1); k.mark(x + w, y, c, eA, -1); }
      for (int i = 0; i < w; i++) k.mark(x + i, y, c);
      return;
    }
    if (emb) { k.mark(x - 1, y, c, eA, 1); k.mark(x, y, c, eF, 1); k.mark(x + w, y, c, eA, -1); k.mark(x + w + 1, y, c, eF, -1); }
    k.mark(x, y, c, 256 - fT);
    for (int i = 1; i < w; i++) k.mark(x + i, y, c);
    k.mark(x + w, y, c, fT);
    return;
  }
  uint16_t *const row = k.fb + ry * PANEL_W;
  TCLIP(row, PANEL_W);
  DigitRow &r = k.rows[ry];
  const int dT = k.rear ? k.dryT[ry] : 256;
  const int xa = emb ? x - 1 : x, xb = x + w - 1 + (fT ? 1 : 0) + (emb ? 1 : 0);   // the row's pixels, inclusive
  int kind = -1;   // 0: every pixel behind air (or on top), 1: every pixel behind liquid; -1: pixel by pixel
  if (xa >= 0 && xb < PANEL_W && !(r.nb && ((xa < r.b1[0] && xb >= r.b0[0]) || (r.nb > 1 && xa < r.b1[1] && xb >= r.b0[1])))) {
    if (!k.rear || xb < r.Li || xa >= r.Hi) kind = 0;
    else if (xa >= r.Li && xb < r.Hi) kind = 1;
  }
#ifdef TICK_PROF
  if (k.prof) k.prof[kind < 0 ? TP_ROW_MIX : kind ? TP_ROW_WET : TP_ROW_DRY]++;
#endif
  if (kind < 0) {
    if (!fT) {
      if (emb) { tickPx(k, ink, r, dT, row, y, x - 1, eA, 1); tickPx(k, ink, r, dT, row, y, x + w, eA, -1); }
      for (int i = 0; i < w; i++) tickPx(k, ink, r, dT, row, y, x + i, 256, 0);
      return;
    }
    if (emb) {
      tickPx(k, ink, r, dT, row, y, x - 1, eA, 1); tickPx(k, ink, r, dT, row, y, x, eF, 1);
      tickPx(k, ink, r, dT, row, y, x + w, eA, -1); tickPx(k, ink, r, dT, row, y, x + w + 1, eF, -1);
    }
    tickPx(k, ink, r, dT, row, y, x, 256 - fT, 0);
    for (int i = 1; i < w; i++) tickPx(k, ink, r, dT, row, y, x + i, 256, 0);
    tickPx(k, ink, r, dT, row, y, x + w, fT, 0);
    return;
  }
  // Every pixel of the row is one column class of TickMemo: written from the memo when it shows the pixel behind the
  // memo was made for (along a row nearly all do, and the next ticks' rows too: same pixel behind, same fT), else on its own.
  const bool wet = kind;
  TickMemo &m = r.tm[kind];
  uint16_t *const d = row + x;
  const uint16_t raw0 = d[emb ? -1 : 0];
  if (!(m.fT == fT && m.raw == raw0 && m.c == ink.c)) {
#ifdef TICK_PROF
    const uint32_t f0 = esp_cpu_get_cycle_count();
#endif
    tickMemoFill(k, ink, m, wet, dT, raw0, fT, eA, eF);
#ifdef TICK_PROF
    if (k.prof) { k.prof[TP_FILLS]++; k.prof[TP_CYC_FILLS] += esp_cpu_get_cycle_count() - f0; }
#endif
  }
  const uint16_t key = m.raw;
#define TICK_PIX(q, i) do { const uint16_t rq = *(q); *(q) = rq == key ? m.o[i] : tickColumnRaw(k, ink, wet, dT, rq, i, fT, eA, eF); } while (0)
  if (emb) TICK_PIX(d - 1, 0);
  TICK_PIX(d, 1);
  for (int i = 1; i < w; i++) TICK_PIX(d + i, 2);
  if (fT || emb) TICK_PIX(d + w, 3);
  if (fT && emb) TICK_PIX(d + w + 1, 4);
#undef TICK_PIX
}

// The lens depth of tick row by (sim drawTicks point): the same expression as the table planTicks fills.
static inline float tickDepth(int by, int H) {
  const float radius = fmx(1, (H - 1) / 2.0f), centre = (H - 1) / 2.0f;
  const float qy = (by - centre) / radius;
  return sqrtf(fmx(0, 1 - qy * qy));
}
// One segment of a tick (sim drawTicks): rows outer .. inner, each at its subpixel position x0 + dx * depth (rows
// whole, shifted by dy * depth; a jump of more than one row is filled in between), edge columns antialiased. One
// call per segment: the per-row bookkeeping in registers, one tickRow call a row.
// Step 9: only the walk's steps f .. l (base rows, in the walk's order; outer .. inner = all of it) and of their rows
// only those in [k.r0, k.r1). A walk resumed at f takes the state of step f - dir from the same expressions the walk
// carries (x0 + dx * depth, by + round(dy * depth)), so every row it plots is the full walk's.
TICK_IRAM static void __attribute__((noinline)) tickSegment(const TickRows &k, const TickInk &ink, int x0, int w, int outer, int inner, float dx, float dy,
                                                            int f, int l) {
  const int H = k.H, dir = inner >= outer ? 1 : -1;
  auto plotF = [&](float xf, int ry) __attribute__((always_inline)) {
    if (ry < k.r0 || ry >= k.r1) return;
    const int x = (int)ffloor(xf), fT = (int)jround((xf - x) * 256);
#ifdef TICK_PROF
    if (k.prof) k.prof[TP_ROWS]++;
    const uint32_t k0 = esp_cpu_get_cycle_count();
#endif
    if (fT == 0 || fT == 256) tickRow(k, ink, ry, x + (fT >> 8), w, 0, k.embT, 0);
    else {
      const int a = 256 - fT;   // left share of the edge columns; fT the right one
      tickRow(k, ink, ry, x, w, fT, k.emboss ? alphaT(k.emb * (a * (1 / 256.0f))) : 0, k.emboss ? alphaT(k.emb * (fT * (1 / 256.0f))) : 0);   // sim emboss * share / 256
    }
#ifdef TICK_PROF
    if (k.prof) k.prof[TP_CYC_ROWS] += esp_cpu_get_cycle_count() - k0;
#endif
  };
  // Without parallax every segment is vertical: no lens-depth or line interpolation needed (f .. l: rows in the band).
  if (dx == 0 && dy == 0) {
    for (int ry = f;; ry += dir) {
#ifdef TICK_PROF
      if (k.prof) k.prof[TP_ROWS]++;
      const uint32_t k0 = esp_cpu_get_cycle_count();
#endif
      tickRow(k, ink, ry, x0, w, 0, k.embT, 0);   // plot: rows outer .. inner lie in the strip
#ifdef TICK_PROF
      if (k.prof) k.prof[TP_CYC_ROWS] += esp_cpu_get_cycle_count() - k0;
#endif
      if (ry == l) break;
    }
    return;
  }
  auto depth = [&](int by) __attribute__((always_inline)) { return k.depth ? k.rows[by].depth : tickDepth(by, H); };
  float px0; int py0, by;
  if (f == outer) {
    const float d = depth(outer);
    px0 = x0 + dx * d; py0 = outer + (int)jround(dy * d);
    plotF(px0, py0);
    if (outer == inner || l == outer) return;
    by = outer + dir;
  } else {
    const int b = f - dir; const float d = depth(b);
    px0 = x0 + dx * d; py0 = b + (int)jround(dy * d);
    by = f;
  }
  for (;; by += dir) {
    const float d = depth(by);
    const float px1 = x0 + dx * d; const int py1 = by + (int)jround(dy * d);
    int n = abs(py1 - py0); if (n < 1) n = 1;
    if (n == 1) plotF(px1, py1);   // one row on (also preserves repeated rows)
    else for (int j = 1; j <= n; j++) plotF(px0 + (px1 - px0) * j / n, (int)jround(py0 + (float)(py1 - py0) * j / n));
    px0 = px1; py0 = py1;
    if (by == l) break;
  }
}

// ---------------------------------------------------------------------------------------------
// step 9: the marks' plans (once a frame) and their bands
// ---------------------------------------------------------------------------------------------
// On the tiled LCD (step 7) the base stages render 4-row tiles in internal RAM; the marks (ticks, digits, fizz, bubble,
// top layers) used to run after the last tile, reading and writing the PSRAM strip through the data cache on lines the
// tiles had left cold. Now every mark stage runs per tile, on the tile's rows only, in the frame's stage order, right
// after the tile's base stages: no CPU access to the strip at all (unless the strip lens runs, below). A mark op reads
// and writes only its own pixel (row facts and plans are per row or per frame), so restricting each stage to a band's
// rows and running the bands in turn keeps every pixel's ops and their order: the pixels are identical. What is set up
// per frame and per item (a tick's segments, a glyph's columns, a bubble's disc) is planned once a frame, here, into
// the tube's MarkPlan (PSRAM, render_init; sized for the worst case), so no set-up repeats per band. Non-tiled builds
// (AMOLED, -DTILE_OFF) draw every stage once over the whole tube [0, H), after the band loop, as before.
#define MAX_TICK_SEGS 118    // a layer: < 60 ticks (step >= 1, i < ticksN <= 60) x 2 segments
#define MAX_GLYPH_PLANS (LABELS_MAX * 2 * 2)   // labels x 2 digits x 2 passes (a bitmap glyph with its shadow copy)
#define MARK_BANDS ((TUBE_HEIGHT_MAX + TUBE_BAND - 1) / TUBE_BAND)
static_assert(TUBE_HEIGHT_MAX <= 127 && FIZZ_POOL * MARK_BANDS <= 32767, "MarkPlan indexes rows by int8, band lists by int16");
struct TickSeg { float dx, dy; int16_t x0, w, outer, inner; uint8_t ink; };
// A bubble's disc set-up (drawTube step 5), one 64-B cache line: what planBubble computes per bubble. bubbleRows
// derives the rest of its DiscRow per band (the same expressions as before, so the same values), on its stack, and
// fills the per-row fields there (the plan stays in PSRAM, written once a frame).
struct alignas(64) BubblePlan {
  float fx, r, offX, offY, bX, bY, tintA, y, m, pop;
  int16_t ixa, ixb, iyA, iyB;
  uint16_t cBlick; bool blick; int8_t cls; uint8_t lvl; int16_t qt;   // size class (-1: none, a popping bubble swells), depth level; masked: x = qt / FIZZ_MQ
};
// The fizz look of one tube (PSRAM, render_init): per size class (FIZZ_SIZES, v = 0.5 + (k + 0.5) / FIZZ_SIZES) the disc
// set-up a bubble of that size takes (planBubble / bubbleRows took it per bubble) and its AA ring's coverage by d2,
// rebuilt when the size or shading params change; per depth level (z = (l + 0.5) / FIZZ_DEPTHS) the colours a bubble
// mixes toward the body per row, every frame (planFizz).
// Its masks: per class one quadrant of the disc's coverage 0..255 as discRowT computes it per pixel (outside out2: 0,
// inside in2: 255, between: the AA ring min(1, r + 0.5 - sqrt(d2))), by |dx| in steps of 1 / FIZZ_MQ px (a class
// bubble's x is rounded to them, so a pixel's |dx| is one: |FIZZ_MQ ix + FIZZ_MQ / 2 - qt| steps for x = qt / FIZZ_MQ)
// and |dy| in steps of 1 / FIZZ_MDY px (a row's distance from the centre, squashed, rounded to one), each |dy| row with
// its widest covered step. A class bubble's row takes its coverage by index; the core and the pinpoint stay per bubble
// (they follow the light), decided per row by their chords. In one pool per tube (PSRAM, render_init: small enough to
// stay in the cache), shared by both tubes (fizzMasks): internal RAM while they fit FIZZ_MASK_INTL (user-fav and most
// presets: a PSRAM table misses the cache the bands share, ~1 us a bubble row), else a PSRAM pool sized at boot for the
// sliders' largest bubbles; params past those draw every bubble analytically (fizzMaskOverflow).
struct FizzClass {
  float r, in2, out2, kc, core2Lo, core2Hi, off, bk, rbOut, bIn2, bOut2;
  bool core, blick;
  int xw, dyl, maskOff;   // mask: dyl |dy| rows of xw |dx| steps at pool + maskOff, then dyl bytes: each row's widest step (255: none)
};
struct FizzLook {
  float key[4]; bool valid, masks;   // fizzSize, fizzSizeVar, fizzShadeOff, fizzBlick the classes were built for; masks fit
  FizzClass k[FIZZ_SIZES];
  const uint8_t *mask; int need;      // this frame's masks (fizzMasks, shared); bytes the classes' masks take
  bool sane;                         // every class a real disc (masks can be built)
  float tintA[FIZZ_DEPTHS];
  uint16_t cRim[FIZZ_DEPTHS][TUBE_HEIGHT_MAX], cBlick[FIZZ_DEPTHS][TUBE_HEIGHT_MAX];   // rim per row; pinpoint by the centre row
  int16_t veilLo[TUBE_HEIGHT_MAX], veilHi[TUBE_HEIGHT_MAX];   // per row: DiscRow veilLo / veilHi (no band: never)
};
static_assert(sizeof(BubblePlan) == 64, "one cache line a bubble");
struct MarkPlan {
  // the tick layer (one a frame: ticksOnTop picks rear or top)
  bool tickOn, tickGeneric, tickDepth, tickEmboss; int tickEmbT; float tickEmb; TickInk ink[2];
  int nSeg; TickSeg seg[MAX_TICK_SEGS];
#if TILE_RENDER
  int8_t segBy[MAX_TICK_SEGS][MARK_BANDS][2];   // a slanted segment: its first / last walk step (base row) plotting into a band, -1 none
#endif
  // the digit layer (one a frame: digitsOnTop picks it); rows [labelR0, labelR1] hold all it draws
  int nGlyph, labelR0, labelR1; GlyphPlan glyph[MAX_GLYPH_PLANS];
  // fizz
  int nBub; BubblePlan bub[FIZZ_POOL];
#if TILE_RENDER
  int16_t bandStart[MARK_BANDS + 1]; uint16_t bandBub[FIZZ_POOL * MARK_BANDS];   // per band: the bubbles with a row in it, in plan order
#endif
};
// The tick layer's plan (sim drawTicks). wetRows/dryRows: source-row tables behind liquid vs behind air, blended by a
// tick's wet share (wetShare, built by drawTube for these edges); edges null = all wet. Parallax is liquid-only. True:
// tickBand leaves every row's facts for this mark (markRowFacts) in digitRows, for a digit layer with an equal mark.
bool Tube::planTicks(int y0, const Params &p, int ticksN, const int16_t *wetRows, const int16_t *dryRows,
                     const Edges *edges, const Mark &mark, float dxFull, float dyFull) const {
  MarkPlan &mp = *plan;
  mp.tickOn = false; mp.nSeg = 0;
  bool minutes = ticksN == 60;
  if (!(minutes ? p.ticksM : p.ticksH)) return false;
  int step = (int)fmx(1, jround(minutes ? p.tickStepM : p.tickStepH));
  int majorEvery = (int)fmx(0, jround(minutes ? p.tickMajorEveryM : p.tickMajorEveryH));
  int hMin = (int)fmx(0, jround(minutes ? p.tickMinorHeightM : p.tickMinorHeightH));
  int hMaj = (int)fmx(0, jround(minutes ? p.tickMajorHeightM : p.tickMajorHeightH));
  int wMin = (int)fmx(1, jround(minutes ? p.tickMinorWidthM : p.tickMinorWidthH));
  int wMaj = (int)fmx(1, jround(minutes ? p.tickMajorWidthM : p.tickMajorWidthH));
  float br = p.brightness * p.tickBright;
  uint16_t cMin = q(scale(hexToRgb(minutes ? p.tickColorM : p.tickColorH), br));
  uint16_t cMaj = q(scale(hexToRgb(minutes ? p.tickMajorColorM : p.tickMajorColorH), br));
  int pos = (int)jround(minutes ? p.tickPosM : p.tickPosH);
  auto warpedRange = [&](const int16_t *sourceRows, int sourceA, int sourceB, int &a, int &b) {
    a = H; b = -1;
    for (int ry = 0; ry < H; ry++) if (sourceRows[ry] >= sourceA && sourceRows[ry] <= sourceB) {
      if (ry < a) a = ry;
      if (ry > b) b = ry;
    }
  };
  // The row kernels' context (tickBand): the facts of every row (the strip rows are the tick rows: y0 is the strip's
  // first row) with an empty TickMemo, the lens depth table when there is parallax; the generic per-pixel path without them.
  mp.tickOn = true;
  mp.tickEmbT = alphaT(clampf(p.tickEmboss, 0, 1)); mp.tickEmb = clampf(p.tickEmboss, 0, 1); mp.tickEmboss = p.tickEmboss > 0;
  mp.tickGeneric = !digitRows || mark.bakedT || y0 != baseY;
  mp.tickDepth = digitRows && (dxFull != 0 || dyFull != 0);
#ifdef TICK_PROF
  const uint32_t f0 = esp_cpu_get_cycle_count();
#endif
  if (mp.tickDepth) for (int ry = 0; ry < H; ry++) digitRows[ry].depth = tickDepth(ry, H);
#ifdef TICK_PROF
  if (mark.prof) mark.prof[TP_CYC_FACTS] += esp_cpu_get_cycle_count() - f0;
#endif
  mp.ink[0] = {cMin, embossHi(cMin), embossLo(cMin)}; mp.ink[1] = {cMaj, embossHi(cMaj), embossLo(cMaj)};
  auto addSegment = [&](int x0, int w, uint16_t c, int rangeA, int rangeB, bool top, float k) {
    if (rangeB < 0) return;
#ifdef TICK_PROF
    if (mark.prof) mark.prof[TP_SEGS]++;
#endif
    const int outer = top ? 0 : H - 1;
    int inner = top ? rangeB : rangeA; if (inner < 0) inner = 0; if (inner >= H) inner = H - 1;
    if (mp.nSeg >= MAX_TICK_SEGS) abort();   // cannot happen (MAX_TICK_SEGS)
    const int n = mp.nSeg++;
    TickSeg &s = mp.seg[n];
    s.dx = dxFull * k; s.dy = dyFull * k; s.x0 = (int16_t)x0; s.w = (int16_t)w; s.outer = (int16_t)outer; s.inner = (int16_t)inner;
    s.ink = c == cMin ? 0 : 1;
#if TILE_RENDER
    if (s.dx == 0 && s.dy == 0) return;   // vertical: tickBand clips its rows directly
    // The walk's rows (tickSegment: step `by` plots rows between the last row and by + round(dy depth)): per band the
    // first and last step that can plot into it.
    int8_t (*const by)[2] = mp.segBy[n];
    for (int b = 0; b < MARK_BANDS; b++) by[b][0] = by[b][1] = -1;
    auto touch = [&](int st, int lo, int hi) {
      if (lo < 0) lo = 0; if (hi > H - 1) hi = H - 1;
      for (int b = lo / TUBE_BAND; lo <= hi && b <= hi / TUBE_BAND; b++) { if (by[b][0] < 0) by[b][0] = (int8_t)st; by[b][1] = (int8_t)st; }
    };
    auto depth = [&](int r) { return mp.tickDepth ? digitRows[r].depth : tickDepth(r, H); };
    const int dir = inner >= outer ? 1 : -1;
    int py0 = outer + (int)jround(s.dy * depth(outer));
    touch(outer, py0, py0);
    if (outer != inner) for (int b = outer + dir;; b += dir) {
      const int py1 = b + (int)jround(s.dy * depth(b));
      touch(b, py0 < py1 ? py0 : py1, py0 < py1 ? py1 : py0);
      py0 = py1;
      if (b == inner) break;
    }
#endif
  };
  // Where wet, the ticks follow the digits' remap (sim tickFollowRange): rows of a tick ending at `edge` in a
  // column of wet share `share`, [0, topB] from the near wall and [botA, H - 1] from the far one.
  const bool follow = edges && rc.tickFollow;
  auto followRange = [&](float edge, int share, int &topA, int &topB, int &botA, int &botB) {
    const float *dry = digitOff, *wet = digitOff + TUBE_HEIGHT_MAX;
    const float k = share * (1 / 256.0f), E = H / 2.0f + edge;
    const int last = (int)fceil(E) - 1, first = (int)ffloor(H - E);
    auto off = [&](int ry) { return dry[ry] + (wet[ry] - dry[ry]) * k; };
    auto row = [&](int ry) { return blendRow(offsetRow(H, dry[ry]), offsetRow(H, wet[ry]), share); };
    int b = -1, a = H;
    while (b + 1 < H && off(b + 1) < edge && row(b + 1) <= last) b++;
    while (a > 0 && off(a - 1) > -edge && row(a - 1) >= first) a--;
    topA = b < 0 ? H : 0; topB = b; botA = a; botB = a < H ? H - 1 : -1;
  };
  // Warped row ranges depend only on (wet/dry table, minor/major height): 8 ranges, computed once.
#ifdef TICK_PROF
  const uint32_t r0 = esp_cpu_get_cycle_count();
#endif
  int rng[2][2][4];   // [wet][major][topA, topB, botA, botB]
  for (int wi = 0; wi < 2; wi++) for (int mj = 0; mj < 2; mj++) {
    const int16_t *rows = wi ? wetRows : dryRows; int h = mj ? hMaj : hMin;
    if (h <= 0 || (mj && majorEvery <= 0)) continue;   // no major tick: their ranges are never read
    if (wi && follow) { followRange(rc.tickEdge[minutes][mj], 256, rng[wi][mj][0], rng[wi][mj][1], rng[wi][mj][2], rng[wi][mj][3]); continue; }
    warpedRange(rows, 0, h - 1, rng[wi][mj][0], rng[wi][mj][1]); warpedRange(rows, H - h, H - 1, rng[wi][mj][2], rng[wi][mj][3]);
  }
#ifdef TICK_PROF
  if (mark.prof) mark.prof[TP_CYC_RANGE] += esp_cpu_get_cycle_count() - r0;
#endif
  const bool flip = p.vertical && p.remaining;   // the scale runs from the top (right) end
  for (int i = step; i < ticksN; i += step) {
    int xc = (int)jround((float)i * L / ticksN); if (flip) xc = L - xc;
    bool major = majorEvery > 0 && i % majorEvery == 0;
    int h = major ? hMaj : hMin; if (h <= 0) continue;
    int w = major ? wMaj : wMin, x0 = xc - ((w - 1) >> 1); uint16_t c = major ? cMaj : cMin;
    const int share = Warp(edges ? wetShare : nullptr)(xc);
    int topA, topB, botA, botB;
#ifdef TICK_PROF
    const uint32_t r1 = esp_cpu_get_cycle_count();
    if (mark.prof) mark.prof[TP_TICKS]++;
#endif
    if (share == 0 || share == 256) { const int *R = rng[share ? 1 : 0][major ? 1 : 0]; topA = R[0]; topB = R[1]; botA = R[2]; botB = R[3]; }
    else if (follow) followRange(rc.tickEdge[minutes][major], share, topA, topB, botA, botB);
    else {   // across the meniscus: the tick's own source rows (sim drawTicks)
      int16_t rows[TUBE_HEIGHT_MAX];
      for (int ry = 0; ry < H; ry++) rows[ry] = (int16_t)blendRow(dryRows[ry], wetRows[ry], share);
      warpedRange(rows, 0, h - 1, topA, topB); warpedRange(rows, H - h, H - 1, botA, botB);
    }
#ifdef TICK_PROF
    if (mark.prof) mark.prof[TP_CYC_RANGE] += esp_cpu_get_cycle_count() - r1;
#endif
    const float k = share * (1 / 256.0f);   // air refracts nothing: the parallax grows with the wet share
    if (pos != 1) addSegment(x0, w, c, topA, topB, true, k);
    if (pos != 0) addSegment(x0, w, c, botA, botB, false, k);
  }
  return !mp.tickGeneric;
}
// The planned tick layer over tube rows [r0, r1) (a band, or 0, H): the rows' facts with an empty TickMemo, then every
// segment's rows in the band in plan order.
void Tube::tickBand(int y0, const Mark &mark, int r0, int r1) const {
  const MarkPlan &mp = *plan;
  if (!mp.tickOn) return;
  TickRows K{mark, FB + (y0 - baseY) * PANEL_W, digitRows, pal.dryT, y0, H, mark.T, mark.Cin, mp.tickEmbT, mp.tickEmb,
             !mark.onTop, mp.tickEmboss, mp.tickGeneric, mp.tickDepth, r0, r1};
#ifdef TICK_PROF
  K.prof = mark.prof;
  const uint32_t f0 = esp_cpu_get_cycle_count();
#endif
  if (!K.generic) for (int ry = r0; ry < r1; ry++) {
    DigitRow &r = digitRows[ry];
    markRowFacts(r, ry, mark); r.tm[0].fT = r.tm[1].fT = -1;
  }
#ifdef TICK_PROF
  if (mark.prof) mark.prof[TP_CYC_FACTS] += esp_cpu_get_cycle_count() - f0;
#endif
  const bool whole = r0 == 0 && r1 == H;
  for (int i = 0; i < mp.nSeg; i++) {
    const TickSeg &s = mp.seg[i];
    int f, l;
    if (s.dx == 0 && s.dy == 0) {   // vertical: rows outer .. inner, clipped to the band
      if (s.inner >= s.outer) { f = s.outer > r0 ? s.outer : r0; l = s.inner < r1 - 1 ? s.inner : r1 - 1; if (f > l) continue; }
      else { f = s.outer < r1 - 1 ? s.outer : r1 - 1; l = s.inner > r0 ? s.inner : r0; if (f < l) continue; }
    } else if (whole) { f = s.outer; l = s.inner; }
    else {
#if TILE_RENDER
      const int8_t *b = mp.segBy[i][r0 / TUBE_BAND];
      if (b[0] < 0) continue;
      f = b[0]; l = b[1];
#else
      f = s.outer; l = s.inner;   // (bands are whole tubes here)
#endif
    }
    tickSegment(K, mp.ink[s.ink], s.x0, s.w, s.outer, s.inner, s.dx, s.dy, f, l);
  }
#ifdef TICK_PROF
  if (mark.prof) mark.prof[TP_CYC] += esp_cpu_get_cycle_count() - f0;   // the band's share of the layer (the plan adds its own)
#endif
}
// The digit layer's plan: every glyph (pass) in draw order (sim drawDigitLayer).
void Tube::planLabels(const Labels &lb, const Warp &warp, int y0) const {
  MarkPlan &mp = *plan;
#if DIGIT_PIE
  if (fracMemo) fracMemo->valid = false;   // the planes may have been rebaked since the last frame
#endif
  mp.nGlyph = 0;
  int r0 = lb.dryRy0 < lb.ry0 ? lb.dryRy0 : lb.ry0, r1 = lb.dryRy1 > lb.ry1 ? lb.dryRy1 : lb.ry1;
  for (int i = 0; i < lb.n; i++) {
    const Label &l = lb.list[i]; int x = l.x0, y = l.y;
    for (int k = 0; k < l.len; k++) {
      const int d = l.text[k] - '0';
      if (mp.nGlyph + 2 > MAX_GLYPH_PLANS) abort();   // cannot happen (MAX_GLYPH_PLANS)
      if (lb.sprite) {
        if (planSpriteGlyph(lb.sprite[d], x, y0, y, lb, warp, mp.glyph[mp.nGlyph])) {
#ifdef DIGIT_PROF
          prof[0]++;
#endif
          mp.nGlyph++;
        }
      } else {
        const BitmapSampler s(*lb.font, d, lb);
        if (lb.shadow >= 0) { planGlyph(s, x, y0, y, lb, warp, true, mp.glyph[mp.nGlyph]); mp.glyph[mp.nGlyph++].d = (uint8_t)d; }   // 1 px shadow copy offset down-right, then the body
        planGlyph(s, x, y0, y, lb, warp, false, mp.glyph[mp.nGlyph]); mp.glyph[mp.nGlyph++].d = (uint8_t)d;
      }
      if (lb.vertical) y += l.adv[k] + lb.gap; else x += l.adv[k] + lb.gap;
    }
  }
  for (int i = 0; i < mp.nGlyph; i++) {
    const GlyphPlan &gp = mp.glyph[i];
    if (gp.rampR0 <= gp.rampR1) { if (gp.rampR0 < r0) r0 = gp.rampR0; if (gp.rampR1 > r1) r1 = gp.rampR1; }
  }
  mp.labelR0 = r0; mp.labelR1 = r1;
}
// The planned digit layer over tube rows [r0, r1). rowFacts: digitRows already holds these rows' facts for an equal mark
// (the rear ticks' layer drew this band just before).
void Tube::labelBand(int y0, const Labels &lb, const Warp &warp, const Mark &mark, bool rowFacts, int r0, int r1) const {
  const MarkPlan &mp = *plan;
  if (r1 <= mp.labelR0 || r0 > mp.labelR1 || !mp.nGlyph) return;
  if (lb.sprite && !rowFacts) spriteRowFacts(y0, lb, mark, r0, r1);
  for (int i = 0; i < mp.nGlyph; i++) {
    const GlyphPlan &gp = mp.glyph[i];
    if (gp.pass == 0) spriteGlyphRows(gp, y0, lb, warp, mark, r0, r1);
    else { const BitmapSampler s(*lb.font, gp.d, lb); drawGlyphRows(s, gp, y0, lb, warp, mark, r0, r1); }
  }
}

// ---------------------------------------------------------------------------------------------
// fizz
// ---------------------------------------------------------------------------------------------
// The fizz's random draws. LCD: a xorshift32 per core (frand runs in stepFizz on core 1 and, for scattered presets, in
// both renders), seeded from the hardware RNG once (render_init). esp_random() itself waits until ~22 us passed since
// its previous call (S3: 1778 APB cycles, a 45 kHz cap), and a fizz step draws 5-15 times in a burst (step 5,
// 2026-10-29). AMOLED (no static RAM to spare) and host builds: esp_random.
#if defined(BOARD_LCD316) && defined(__XTENSA__)
#include "esp_cpu.h"
static uint32_t fizzRng[2] = {0x9e3779b9u, 0x7f4a7c15u};
static inline uint32_t fizzDraw() { uint32_t &x = fizzRng[esp_cpu_get_core_id() & 1]; x ^= x << 13; x ^= x >> 17; x ^= x << 5; return x; }
static void fizzSeed() { for (int i = 0; i < 2; i++) { uint32_t v; do v = esp_random(); while (!v); fizzRng[i] = v; } }
static bool fizzReseed(uint32_t seed) { fizzRng[0] = seed | 1; fizzRng[1] = (seed * 2654435761u) | 1; return true; }
#else
static inline uint32_t fizzDraw() { return esp_random(); }
static void fizzSeed() {}
static bool fizzReseed(uint32_t) { return false; }
#endif
#ifdef FIZZ_PROF
static uint32_t fizzStepProfCore[2][FS_N], fizzStepProf[FS_N];   // stepFizz counters per core (each tube steps on its render's core), summed when read
#define FS_P (fizzStepProfCore[esp_cpu_get_core_id() & 1])
static inline float frand() {
  const uint32_t c0 = esp_cpu_get_cycle_count(), v = fizzDraw();
  FS_P[FS_CYC_RAND] += esp_cpu_get_cycle_count() - c0; FS_P[FS_RANDS]++;
  return (v >> 8) / 16777216.0f;
}
#define FS_ADD(i, v) FZ_ADD(FS_P, i, v)
#define FS_CNT(i, n) (FS_P[i] += (n))
#else
static inline float frand() { return (fizzDraw() >> 8) / 16777216.0f; }
#define FS_ADD(i, v) ((void)0)
#define FS_CNT(i, n) ((void)0)
#endif
static inline float fizzR(const Params &p, float v) { return p.fizzSize / 2 * (1 + (v - 1) * p.fizzSizeVar); }
// Size classes and depth levels (fizz perf, 2026-11-03): a bubble's size factor v and depth z take FIZZ_SIZES /
// FIZZ_DEPTHS values, one draw each as before, so the render shares a class's disc set-up and coverage table and a
// level's colours (planFizz). See sim fizzV / fizzZ.
static inline float fizzV() { return 0.5f + ((int)(frand() * FIZZ_SIZES) + 0.5f) * (1.0f / FIZZ_SIZES); }
static inline float fizzZ() { return ((int)(frand() * FIZZ_DEPTHS) + 0.5f) * (1.0f / FIZZ_DEPTHS); }
static inline int fizzClass(float v) { const int k = (int)((v - 0.5f) * FIZZ_SIZES); return k < 0 ? 0 : k >= FIZZ_SIZES ? FIZZ_SIZES - 1 : k; }
static inline int fizzLevel(float z) { const int l = (int)(z * FIZZ_DEPTHS); return l < 0 ? 0 : l >= FIZZ_DEPTHS ? FIZZ_DEPTHS - 1 : l; }
static inline float fizzWall(const Params &p) { return p.glassWall > 0 ? fmx(1, p.glassWall) : 0; }   // band px per side (buildPalette wallU)
// Row where a bubble of size v is fully behind the wall band (respawn/turnaround bound); 3 px without a band.
static inline float fizzHideY(const Params &p, float v) { float w = fizzWall(p); return w > 0 ? fmx(0, w - fizzR(p, v)) : 3; }
// Random row with the whole bubble in the bore, so bubbles never sit half behind the wall.
static inline float fizzSpawnY(const Params &p, int H, float v) { float lo = fizzWall(p) + fizzR(p, v), hi = H - lo; return hi <= lo ? H / 2.0f : lo + frand() * (hi - lo); }
// Surface front `surf` (liquid frame) at float row y, in u = side * x: where a parked bubble's centre sits.
FIZZ_IRAM static float foamFront(const float *surf, int H, float y, int side) {
  const float yc = clampf(y, 0, H - 1); const int i = (int)ffloor(yc), j = i + 1 < H ? i + 1 : H - 1;
  return side * (surf[i] + (surf[j] - surf[i]) * (yc - i));
}
// Furthest centre (in u = side * x) a bubble of radius r at row y can take with its whole disc inside the
// surface `surf` (liquid frame): the tightest row of the disc. See sim discFit.
// Rows whose term provably exceeds the term of the row nearest y (B) cannot be the minimum: they skip their root
// (side * surf - B > root, checked by squares with an absolute margin far above float rounding). The minimum over the
// rows left is the minimum over all of them, bit for bit (a skipped term is strictly greater than one that is kept).
FIZZ_IRAM static float discFitRows(const float *surf, int a, int b, float y, float r, int side) {
  const int ic = (int)clampf(jround(y), (float)a, (float)b);
  const float dyc = ic - y, B = side * surf[ic] - sqrtExact(fmx(0, r * r - dyc * dyc));
  float u = INFINITY;
  for (int iy = a; iy <= b; iy++) {
    const float dy = iy - y, rem = fmx(0, r * r - dy * dy);   // as the all-rows loop wrote it (the board fuses one product)
    if (iy != ic) { const float e = side * surf[iy] - B - 1e-3f; if (e > 0 && e * e > rem * 1.00001f) continue; }
    u = fmn(u, side * surf[iy] - sqrtExact(rem));
  }
  return u;
}
FIZZ_IRAM static float discFit(const float *surf, int H, float y, float r, int side) {
  FZ_T0(c0);
  const int a = (int)fmx(0, fceil(y - r)), b = (int)fmn(H - 1, ffloor(y + r));
  const float u = a > b ? foamFront(surf, H, y, side) - r : discFitRows(surf, a, b, y, r, side);
  FS_ADD(FS_CYC_FIT, c0); FS_CNT(FS_FITS, 1); FS_CNT(FS_FIT_ROWS, b >= a ? b - a + 1 : 0);
  return u;
}
// A lower bound of discFit without its roots: every row's root is at most r (rounded up to r1 here), so each row's
// term side * surf - root is at least side * surf - r1 (rounding is monotone), and so is their minimum. Lets stepFizz
// skip discFit for a bubble far from the surface: f.x <= low - FOAM_CATCH implies f.x <= discFit - FOAM_CATCH.
static inline float discFitLow(const float *surf, int H, float y, float r, int side) {
  const int a = (int)fmx(0, fceil(y - r)), b = (int)fmn(H - 1, ffloor(y + r));
  if (a > b) return -INFINITY;   // discFit takes another path there: no bound
  const float r1 = r + r * 1e-6f;   // >= the float above r, >= any rounded root of r * r - dy * dy
  float u = INFINITY;
  for (int iy = a; iy <= b; iy++) u = fmn(u, side * surf[iy] - r1);
  return u;
}
// The foam's work space, one per tube (PSRAM, render_init): the parked bubbles (settleFoam) or touchesFoam's candidates
// (stepFizz) as a slot list with each one's fizzR, in a grid over (u = side * x, y) so a pair test only visits bubbles
// within reach: the foam lines the surface front across the whole bore and packs back from it in layers, and the free
// bubbles fill the tube behind it. The grid holds each slot at the (u, y) it had when it was built (u0, y0); `drift`
// bounds how far any has moved since, so a query widened by it still finds every bubble a pair test could accept: what
// it leaves out is farther than the contact distance m on one axis alone, where every test it would have taken fails.
// Each pass visits what it did before, in the same order: the results are bit-identical to the all-pairs scans.
// `order` (the packing sweep order) is kept from step to step: it is re-sorted, not rebuilt from slot order.
#define FOAM_CELLS 1024   // grid cells (u x y) at most: the u cells widen past it
#define FOAM_BRUTE 8      // up to this many bubbles a grid costs more than it saves: every pass scans them all
struct FoamWork {
  int16_t order[FIZZ_POOL]; int nOrder;       // the packing sweep order (parked, front first), kept between steps
  int16_t list[FIZZ_POOL]; int nList;         // settleFoam: the parked in slot order; stepFizz: touchesFoam's candidates
  int16_t pos[FIZZ_POOL];                     // slot -> its index in order (packing sweep)
  int16_t next[FIZZ_POOL], head[FOAM_CELLS];  // the grid: per cell (row-major, nu a row) a linked list of slots, -1 ends
  uint32_t mark[(FIZZ_POOL + 31) / 32];       // one bubble's gathered partners: their sweep indices as bits
  uint8_t inOrder[FIZZ_POOL];                 // slot kept in order from the last step (settleFoam, cleared after use)
  float R[FIZZ_POOL];                         // fizzR per slot of list: only bounds the reach (rMax); the tests call fizzR,
                                              // whose products fuse into their sums on the board as before
  float u0[FIZZ_POOL], y0[FIZZ_POOL];         // the slot's (u, y) at the grid's build
  float uLo, invCu, invCy, cell;              // grid origin in u, 1 / cell size in u and y, cell size in y
  float uMin, uMax, drift, rMax;              // u extent of everything in it; bound on |u - u0|, |y - y0| (a bubble moving
                                              // farther is moved to its new cell); largest R
  int nu, ny, side; bool moved;               // nu 0: no grid (few bubbles); a bubble changed cells (a gather made before is stale)
};
// The cell of u / y, clamped to the grid (monotone in u / y; NaN: cell 0, no float-to-int conversion of it).
static inline int foamCell(float t, int n) { return t >= 0 ? (t < n - 1 ? (int)t : n - 1) : 0; }
static inline int foamCu(const FoamWork &w, float u) { return foamCell((u - w.uLo) * w.invCu, w.nu); }
static inline int foamCy(const FoamWork &w, float y) { return foamCell(y * w.invCy, w.ny); }
static inline void foamAdd(FoamWork &w, int s, float u, float y) {   // into the grid (nu > 0)
  w.u0[s] = u; w.y0[s] = y; const int c = foamCy(w, y) * w.nu + foamCu(w, u); w.next[s] = w.head[c]; w.head[c] = (int16_t)s;
}
// A grid over list[0, nList) at its current (u, y) (R set), or none for a few bubbles. Cells: the largest R + 0.5 high,
// so a contact reach spans about five; as wide, or wider when the foam is long.
static void foamGridBuild(FoamWork &w, const Fizz *fz, int H, int side, bool moving) {
  w.side = side; w.drift = 0; w.rMax = 0; w.uMin = INFINITY; w.uMax = -INFINITY; w.moved = false;
  for (int i = 0; i < w.nList; i++) { const int s = w.list[i]; const float u = side * fz[s].x; w.rMax = fmx(w.rMax, w.R[s]); w.uMin = fmn(w.uMin, u); w.uMax = fmx(w.uMax, u); }
  if (w.nList <= FOAM_BRUTE) { w.nu = 0; return; }
  w.cell = fmx(1, w.rMax + 0.5f); w.invCy = 1 / w.cell; w.drift = moving ? 0.5f * w.cell : 0;
  w.ny = (int)(H * w.invCy) + 2; if (w.ny > FOAM_CELLS / 4) w.ny = FOAM_CELLS / 4;
  const float span = w.uMax - w.uMin;
  if (!(span < 65536)) { w.nu = 0; return; }   // NaN or an absurd spread: every pass scans them all (the same answers)
  int nu = (int)(span * w.invCy) + 2;
  if (nu * w.ny > FOAM_CELLS) { nu = FOAM_CELLS / w.ny; w.invCu = (nu - 1) / (span + 1); } else w.invCu = w.invCy;
  w.nu = nu; w.uLo = w.uMin;
  for (int c = 0; c < nu * w.ny; c++) w.head[c] = -1;
  for (int i = w.nList - 1; i >= 0; i--) { const int s = w.list[i]; foamAdd(w, s, side * fz[s].x, fz[s].y); }
}
// Bubble s moved to (u, y) (settleFoam) past the drift bound from where the grid holds it: to its cell there.
static void __attribute__((noinline)) foamMove(FoamWork &w, int s, float u, float y) {
  int16_t *link = &w.head[foamCy(w, w.y0[s]) * w.nu + foamCu(w, w.u0[s])];
  while (*link != s) link = &w.next[*link];
  *link = w.next[s];
  foamAdd(w, s, u, y); w.moved = true;
}
// The grid cells within reach of (u, y): every bubble a contact test with one of radius r there can accept.
struct FoamRange { int u0, u1, y0, y1; };
static inline FoamRange foamRange(const FoamWork &w, float u, float y, float r) {
  const float reach = r + w.rMax + 0.5f + w.drift + 0.01f;   // >= any pair's m plus the drift, with a margin over rounding
  return {foamCu(w, u - reach), foamCu(w, u + reach), foamCy(w, y - reach), foamCy(w, y + reach)};
}
// A free bubble f (radius r) touching foam parked on `side` — not foam on the other edge, nor foam this tick is
// still to release (its life still carries the old side).
// Scans the candidates (stepFizz keeps them in the foam work space: every slot that is foam on `side` now, where it
// parked, which no foam leaves before settleFoam), only the cells within reach and nothing when the bubble is farther
// than any contact from all of them in u; others are skipped by the same test as before. The answer is an OR over that
// set, so the order of the scan does not matter.
FIZZ_IRAM static bool touchesFoam(const Tube &t, const FoamWork &w, const Fizz &f, float r, const Params &p, int side) {
  FS_CNT(FS_TOUCHES, 1);
  const float uq = side * f.x, reach = r + w.rMax + 0.5f + 0.01f;   // >= any candidate's m, with a margin far above float rounding
  if (uq + reach < w.uMin || uq - reach > w.uMax) return false;    // |dx| > m from all of them
  auto hit = [&](int j) {
    const Fizz &g = t.fizz[j];
    if (g.life * side <= 0) return false;
    const float m = r + fizzR(p, g.v) + 0.5f, dx = g.x - f.x, dy = g.y - f.y;   // fizzR here, not R: the same fused ops as before
    return fabsf(dx) < m && fabsf(dy) < m && dx * dx + dy * dy < m * m;
  };
  if (w.nu == 0) {
    FS_CNT(FS_TOUCH_SCAN, w.nList);
    for (int c = 0; c < w.nList; c++) if (hit(w.list[c])) return true;
    return false;
  }
  const FoamRange q = foamRange(w, uq, f.y, r);
  for (int cy = q.y0; cy <= q.y1; cy++)
    for (int cu = q.u0; cu <= q.u1; cu++)
      for (int j = w.head[cy * w.nu + cu]; j >= 0; j = w.next[j]) { FS_CNT(FS_TOUCH_SCAN, 1); if (hit(j)) return true; }
  return false;
}
// Respawn x in the liquid of the bubble's (new) row: at < 0 random, 0 just inside the time edge, > 0 just
// inside the home edge (the side the flow comes from). See sim stepFizz respawn.
static void __attribute__((noinline)) fizzRespawnX(const Tube &t, const Params &p, Fizz &f, int at) {   // births / respawns: rare, flash
  const float r = fizzR(p, f.v);
  const float lo = -discFit(t.fizzSurfL, t.H, f.y, r, -1) + FOAM_CATCH, hi = discFit(t.fizzSurf, t.H, f.y, r, 1) - FOAM_CATCH;
  f.x = hi <= lo ? (lo + hi) / 2 : at < 0 ? lo + frand() * (hi - lo) : at > 0 ? lo : hi;
}
// Spring (fizzSource 1): a new size and depth, born at the spring — fizzSourceY across the bore (whole disc
// inside), fizzSourceX along that row's liquid (between the surfaces, as a respawn) as it sits at home, so
// fizzShift px back in a slug that slid away — each axis jittered by up to ±fizzSourceSpread px, kept in the
// liquid. See sim springSpawn.
static void __attribute__((noinline)) springSpawn(const Tube &t, const Params &p, Fizz &f) {
  f.v = fizzV(); f.z = fizzZ(); f.life = 0;
  const float r = fizzR(p, f.v), s = p.fizzSourceSpread, lo = fizzWall(p) + r, hi = t.H - lo;
  f.y = hi <= lo ? t.H / 2.0f : clampf(lo + p.fizzSourceY * (hi - lo) + (2 * frand() - 1) * s, lo, hi);
  const float xl = -discFit(t.fizzSurfL, t.H, f.y, r, -1) + FOAM_CATCH, xh = discFit(t.fizzSurf, t.H, f.y, r, 1) - FOAM_CATCH;
  f.x = xh <= xl ? (xl + xh) / 2 : clampf(xl + p.fizzSourceX * (xh - xl) - t.fizzShift + (2 * frand() - 1) * s, xl, xh);
}
// Scattered birth: a new size and depth anywhere in the liquid. See sim stepFizz scatter.
static void __attribute__((noinline)) fizzScatter(const Tube &t, const Params &p, Fizz &f) {
  f.life = 0; f.v = fizzV(); f.y = fizzSpawnY(p, t.H, f.v); fizzRespawnX(t, p, f, -1); f.z = fizzZ();
}
// A spring's bubble leaving or popping: its slot goes idle until the cadence fills it.
static inline void fizzFree(Fizz &f) { f.v = 0; f.life = 0; }
// This spring birth in tube t comes from the spring itself (covered by the liquid), not scattered. See sim springBirth.
static inline bool springBirth(const Tube &t) { return t.springScatter <= 0 || frand() >= t.springScatter; }
// Bubbles a column of `len` px holds: fizzCount is a full tube's, up to doubled by shaking; past the fixed pool it
// is capped and reported (fizzOverflow). See sim fizzWant.
static int fizzWant(const Params &p, float len, float agitation) {
  int want = (int)ffloor(p.fizzCount * (len / L) * (1 + (agitation < 0.05f ? 0 : agitation))); if (want < 0) want = 0;
  if (want > FIZZ_POOL) { atomicMax(fizzOverflowPeak, want); want = FIZZ_POOL; }
  return want;
}
// A spring fills its pool at its cadence instead, up to the same count (stepFizz).
void Tube::ensureFizz(const Params &p, float len, float agitation) {
  fizzLen = len;
  if (p.fizzSource == 1) return;
  const int want = fizzWant(p, len, agitation);
  while (fizzN < want) { float v = fizzV(); fizz[fizzN++] = { frand() * len, fizzSpawnY(p, H, v), v, 0, fizzZ() }; }
  fizzN = want;
}
// Parked bubbles: sit centred on the surface front — foam floats half out of the liquid — lagging behind an
// advance (and gliding on after being caught) no faster than the rise, pushed back by a recession; slide along
// the meniscus toward the higher contact line (the corners: the foam ring) and pack, late arrivals filling the
// meniscus from its front backward. Against a closed end (glass: glassVy = the across rise px/s) the whole disc
// stays inside and the bubbles slide along the glass with the rise instead. Works in u = side * x, so the home
// edge (side -1) is the time edge mirrored. See sim settleFoam.
FIZZ_IRAM static void __attribute__((noinline)) settleFoam(Tube &t, const Params &p, float speed, const float *surf, int side, float dt, bool glass, float glassVy) {
  const int H = t.H; const float wall = fizzWall(p), follow = fmn(1, FOAM_FOLLOW * dt);
  FoamWork &w = *t.foam; Fizz *const fz = t.fizz;
  auto front = [&](float y, float r) { return glass ? discFit(surf, H, y, r, side) : foamFront(surf, H, y, side); };
  auto place = [&](int s, float u, float y) {   // in the bore and not past the front of its row
    Fizz &f = fz[s]; const float r = fizzR(p, f.v), lo = wall + r, hi = H - lo;
    f.y = hi <= lo ? H / 2.0f : clampf(y, lo, hi);
    const float un = fmn(u, front(f.y, r));   // its new u (side * x: side is +-1)
    f.x = side * un;
    const float d = fmx(fabsf(un - w.u0[s]), fabsf(f.y - w.y0[s])); if (d > w.drift && w.nu) foamMove(w, s, un, f.y);
  };
  // The parked bubbles, in slot order (none parks or leaves in here): the slide pass and the packing sweep run over them.
  int n = 0;
  for (int i = 0; i < t.fizzN; i++) if (fz[i].life != 0) { w.list[n++] = (int16_t)i; w.R[i] = fizzR(p, fz[i].v); }
  w.nList = n;
  foamGridBuild(w, fz, H, side, true);
  for (int a = 0; a < n; a++) {
    const int i = w.list[a];
    Fizz &f = fz[i];
    const float r = fizzR(p, f.v);
    const int fy = (int)clampf(jround(f.y), 0, H - 1);
    const float tu = front(f.y, r);
    float u = side * f.x;
    u = u < tu ? u + fmn((tu - u) * follow, speed * dt) : tu;   // buoyancy: no faster than the rise
    const float slope = side * (surf[fy + 1 < H ? fy + 1 : H - 1] - surf[fy > 0 ? fy - 1 : 0]) / 2;   // px per row
    float slide = glass ? glassVy * dt : FOAM_SLIDE * speed * clampf(2 * slope, -1, 1) * dt;
    // Touching a neighbour on the slide side: line up along the surface. Slide 0 skips every neighbour anyway.
    auto touch = [&](int j) {
      const Fizz &g = fz[j];
      if (j == i || slide * (g.y - f.y) <= 0) return false;
      const float m = r + fizzR(p, g.v) + 0.5f, du = side * g.x - u, dy = g.y - f.y;
      return du * du + dy * dy < m * m;
    };
    if (slide != 0) {
      if (w.nu == 0) { for (int b = 0; b < n; b++) if (touch(w.list[b])) { slide = 0; break; } }
      else {
        const FoamRange q = foamRange(w, u, f.y, r);
        for (int cy = q.y0; cy <= q.y1 && slide != 0; cy++)
          for (int cu = q.u0; cu <= q.u1 && slide != 0; cu++)
            for (int j = w.head[cy * w.nu + cu]; j >= 0; j = w.next[j]) if (touch(j)) { slide = 0; break; }
      }
    }
    place(i, u, f.y + slide);
  }
  // The sweep order: last step's, those still parked, then the newly parked in slot order. The first sort orders it
  // by u, front first, ties by slot: what a stable sort of slot order gives (the sim's), from a nearly sorted start.
  {
    int m = 0;
    for (int a = 0; a < w.nOrder; a++) { const int s = w.order[a]; if (s < t.fizzN && fz[s].life != 0 && !w.inOrder[s]) { w.inOrder[s] = 1; w.order[m++] = (int16_t)s; } }
    for (int a = 0; a < n; a++) { const int s = w.list[a]; if (!w.inOrder[s]) w.order[m++] = (int16_t)s; else w.inOrder[s] = 0; }
    w.nOrder = m;   // == n
  }
  int16_t *const order = w.order;
  uint32_t *const mark = w.mark;
  // Pack: pairwise relaxation swept front to back; an overlapping pair is pushed apart, clamped to the bore
  // and the front, and whatever overlap the clamps leave the rear one takes by stepping back. See sim.
  for (int it = 0; it < FOAM_RELAX; it++) {
    for (int a = 1; a < n; a++) {   // insertion sort: nearly sorted (the last sweep's order; the first: the last step's)
      const int16_t k = order[a]; const float uk = side * fz[k].x; int b = a - 1;
      if (it == 0) while (b >= 0 && (side * fz[order[b]].x < uk || (side * fz[order[b]].x == uk && order[b] > k))) { order[b + 1] = order[b]; b--; }
      else while (b >= 0 && side * fz[order[b]].x < uk) { order[b + 1] = order[b]; b--; }
      order[b + 1] = k;
    }
    for (int a = 0; a < n; a++) w.pos[order[a]] = (int16_t)a;
    for (int a = 0; a < n; a++) {
      const int fi = order[a]; Fizz &f = fz[fi]; const float rf = fizzR(p, f.v);
      // a's partners later in the sweep, visited in sweep order: all of them, or those in the cells within reach (as
      // bits of mark), gathered again past `after` whenever a move widens the reach or the grid is rebuilt.
      FoamRange q{0, -1, 0, -1}; int qb = a;   // the gather's cells; the partner visited last
      auto gather = [&](int after) {
        const int w0 = (after + 1) >> 5, w1 = (n - 1) >> 5;
        for (int k = w0; k <= w1; k++) mark[k] = 0;
        if (w.nu == 0) {
          for (int k = w0; k <= w1; k++) mark[k] = ~0u;
        } else {
          q = foamRange(w, side * f.x, f.y, rf);
          for (int cy = q.y0; cy <= q.y1; cy++)
            for (int cu = q.u0; cu <= q.u1; cu++)
              for (int j = w.head[cy * w.nu + cu]; j >= 0; j = w.next[j]) { const int b = w.pos[j]; if (b > after) mark[b >> 5] |= 1u << (b & 31); }
        }
        if (w0 <= w1) mark[w0] &= ~0u << ((after + 1) & 31);   // only past `after`
        if (((n - 1) & 31) != 31 && w0 <= w1) mark[w1] &= ~(~0u << (((n - 1) & 31) + 1));   // not past the last
      };
      gather(a);
      for (;;) {
        // the next partner past qb: the lowest set bit at or after qb + 1
        int k = (qb + 1) >> 5; if (k > (n - 1) >> 5) break;
        uint32_t bits = mark[k] & (~0u << ((qb + 1) & 31));
        while (!bits && ++k <= (n - 1) >> 5) bits = mark[k];
        if (!bits) break;
        qb = (k << 5) + __builtin_ctz(bits);
        const int gs = order[qb]; Fizz &g = fz[gs];
        const float m = rf + fizzR(p, g.v) + 0.5f;
        float du = side * (g.x - f.x), dy = g.y - f.y;
        if (fabsf(du) >= m || fabsf(dy) >= m || du * du + dy * dy >= m * m) continue;
        const float d = sqrtExact(du * du + dy * dy), kk = (m - d) / 2;
        const float nu = d > 1e-4f ? du / d : -1, ny = d > 1e-4f ? dy / d : 0;   // coincident: g (later in the sweep) steps back
        place(fi, side * f.x - kk * nu, f.y - kk * ny);
        place(gs, side * g.x + kk * nu, g.y + kk * ny);
        du = side * (g.x - f.x); dy = g.y - f.y;
        if (du * du + dy * dy < m * m) {
          const bool gFront = du > 0; const int rs = gFront ? fi : gs; const Fizz &fr = gFront ? g : f;
          place(rs, side * fr.x - sqrtExact(fmx(0, m * m - dy * dy)), fz[rs].y);
        }
        if (w.nu) {   // moves: a bubble that changed cells, or a's wider reach, may bring partners the gather left out
          const FoamRange c = foamRange(w, side * f.x, f.y, rf);
          if (w.moved || c.u0 < q.u0 || c.u1 > q.u1 || c.y0 < q.y0 || c.y1 > q.y1) { w.moved = false; gather(qb); }
        }
      }
    }
  }
}
// Rises against in-plane gravity at fizzSpeed px/s on both axes; face up = slow screen-up rise plus a drift
// toward the exposed surface (the time edge, or the home edge of a free slug whose time edge sits against
// the far end). While the rise points at an exposed surface and fizzFoamLife > 0, a bubble reaching it parks
// in its meniscus (settleFoam) and pops later; otherwise it respawns at the far side. A spring (fizzSource 1)
// takes every birth instead, at its cadence (springClock), so the bubbles rise as a stream; a bubble leaving or
// popping frees its slot. A slug sliding off the spring leaves it dry, and its births go scattered instead
// (springScatter). The glass holds a spring's bubbles (see SPRING_BACK). See sim stepFizz.
int fizzOverflow() { return fizzOverflowPeak.load(std::memory_order_relaxed); }
int fizzCounts(int idx, int &foam, int &slots) {
  const Tube &t = tubeAt(idx); int live = 0; foam = 0; slots = t.fizzN;
  for (int i = 0; i < t.fizzN; i++) { if (t.fizz[i].v != 0) live++; if (t.fizz[i].life != 0) foam++; }
  return live;
}

// One tube's step (idx): each tube steps only its own state, so two may step at once on two cores (main: each on the
// core that renders it); stepFizz steps all, one after the other.
FIZZ_IRAM void stepFizzTube(int idx, const Params &p, float dt, float along, float across, float agitation) {
  FZ_T0(st0); if (idx == 1) FS_CNT(FS_STEPS, 1);   // a step: both tubes
  if (mirrored(p)) along = -along;   // fizz lives in the mirrored liquid frame (see drawTube)
  const float speed = p.fizzSpeed * (1 + 3 * agitation);
  const float up = sqrtExact(fmx(0.0f, 1 - along * along - across * across));
  const float a = clampf(across * p.fizzAcrossGain, -1, 1), al = clampf(along * p.fizzDriftGain, -1, 1);
  // Vertical watch: the viewer's up is the tube's top end (+x), so the face-up rise goes along the tube, not across it.
  const float flat = up * p.fizzFlatRise; const bool V = p.vertical;
  const float vy = -speed * ((V ? 0 : (1 - fabsf(a)) * flat) + a);
  const float vxTilt = -speed * (al - (V ? (1 - fabsf(al)) * flat : 0));
  const bool spring = p.fizzSource == 1; const float wall = fizzWall(p);
  const bool hold = spring && p.fizzFoamLife > 0 && vy != 0;   // the bore wall the rise points at holds the stream
  const float letGo = hold ? dt * (1 + 3 * agitation) / p.fizzFoamLife : 0;   // per-step chance a held bubble lets go
  {
    Tube &t = tubeAt(idx); const float len = t.fizzLen; const int H = t.H; const int exposed = t.fizzExposed;
    if (len <= 0) return;   // no liquid drawn yet: no surfaces
    FZ_T0(sp0);
    // The spring point: a mean bubble's centre as springSpawn places it (row sy, in the span sxl..sxh), dry once
    // the slug slides it past its home surface.
    const float sr = fizzR(p, 1), slo = fizzWall(p) + sr, sy = H - slo <= slo ? H / 2.0f : slo + p.fizzSourceY * (H - 2 * slo);
    const float sxl = spring ? -discFit(t.fizzSurfL, H, sy, sr, -1) + FOAM_CATCH : 0, sxh = spring ? discFit(t.fizzSurf, H, sy, sr, 1) - FOAM_CATCH : 0;
    const float sx = sxl + p.fizzSourceX * fmx(0, sxh - sxl) - t.fizzShift;
    if (spring) t.springScatter = sx <= -foamFront(t.fizzSurfL, H, sy, -1) ? 1 : fmx(0, t.springScatter - dt / SPRING_BACK);
    const int dir = exposed & 1 ? 1 : exposed & 2 ? -1 : 0;   // +x = the time edge
    const float vx = vxTilt + speed * up * p.fizzEdgeRise * dir;
    // The surface the rise heads for, if exposed and foam is on: +1 time edge, -1 home edge, 0 none; a spring's
    // foam also parks against a closed end (glass).
    const int side = p.fizzFoamLife <= 0 ? 0 : vx > 0 && (spring || (exposed & 1)) ? 1 : vx < 0 && (spring || (exposed & 2)) ? -1 : 0;
    const bool glass = side != 0 && !(exposed & (side > 0 ? 1 : 2));
    // On the bore wall the rise points at (row wallY: the disc touching the glass), held by it.
    auto wallY = [&](const Fizz &g) { return vy < 0 ? wall + fizzR(p, g.v) : H - wall - fizzR(p, g.v); };
    auto held = [&](const Fizz &g) { return g.v != 0 && g.life == 0 && fabsf(g.y - wallY(g)) < 1e-3f; };
    FS_ADD(FS_CYC_SPRINGPT, sp0); FS_CNT(FS_SLOTS, t.fizzN);
    // touchesFoam's candidates (the foam work space, free until settleFoam below): the foam on `side` now, plus every
    // bubble that parks during the loop (only bubble k changes in step k; foam does not move before settleFoam).
    FoamWork &w = *t.foam;
    w.nList = 0;
    if (side != 0) {
      for (int j = 0; j < t.fizzN; j++) if (t.fizz[j].life * side > 0) { w.list[w.nList++] = (int16_t)j; w.R[j] = fizzR(p, t.fizz[j].v); }
    }
    foamGridBuild(w, t.fizz, H, side, false);   // side 0: empty (no candidates, no touchesFoam); the candidates stay put
    auto parked = [&](int k, float r) {   // bubble k (radius r) parked: a candidate from now on
      const float u = side * t.fizz[k].x;
      w.R[k] = r; w.rMax = fmx(w.rMax, r); w.uMin = fmn(w.uMin, u); w.uMax = fmx(w.uMax, u);
      if (w.nu == 0) w.list[w.nList++] = (int16_t)k; else foamAdd(w, k, u, t.fizz[k].y);
    };
    FZ_T0(lp0);
    for (int k = 0; k < t.fizzN; k++) {
      Fizz &f = t.fizz[k];
      if (f.v == 0) { if (!spring) fizzScatter(t, p, f); continue; }   // idle: the spring's cadence fills it below
      FS_CNT(FS_LIVE, 1);
      if (f.life != 0) {
        const int was = f.life > 0 ? 1 : -1;
        if (was != side) {   // the surface tilted away: the foam releases into the flow, from where it is drawn
          f.x = was * fmn(was * f.x, foamFront(was > 0 ? t.fizzSurf : t.fizzSurfL, H, f.y, was));
          f.life = 0;
        }
        else {
          const float left = fabsf(f.life) - dt * (1 + 3 * agitation);   // shaking pops the foam
          if (left > 0) f.life = side * left;
          else if (spring) fizzFree(f);
          else fizzScatter(t, p, f);
          continue;
        }
      }
      const float r = fizzR(p, f.v), wlo = wall + r, whi = H - wlo; const bool grip = hold && whi > wlo;
#ifdef FIZZ_PROF
      if (grip && held(f)) FS_CNT(FS_HELD, 1);
#endif
      if (grip && held(f) && frand() >= letGo) f.x += vx * dt;   // held by the glass: slides along it
      else {
        const bool inBore = f.y > wlo && f.y < whi;   // not one letting go, already on the glass row
        f.y += vy * f.v * dt;
        f.x += vx * f.v * dt;
        if (grip && inBore && (vy < 0 ? f.y < wlo : f.y > whi)) {   // carried into the glass: held, or coalesces into a held bubble
          f.y = vy < 0 ? wlo : whi;
          bool merge = false;
          FZ_T0(mg0);
          for (int j = 0; j < t.fizzN; j++) {
            const Fizz &g = t.fizz[j];
            if (j == k || !held(g)) continue;
            const float m = r + fizzR(p, g.v) + 0.5f, dx = g.x - f.x, dy = g.y - f.y;
            if (dx * dx + dy * dy < m * m) { merge = true; break; }
          }
          FS_ADD(FS_CYC_MERGE, mg0);
          if (merge) { fizzFree(f); continue; }
        }
      }
      // Vertical exit: once fully behind the wall band, respawn fully behind the opposite one and rise out of it.
      const float hide = fizzHideY(p, f.v);
      if (f.y < hide || f.y >= H - hide) {
        if (spring) fizzFree(f);
        else { f.v = fizzV(); const float h = fizzHideY(p, f.v); f.y = vy <= 0 ? H - h : h; fizzRespawnX(t, p, f, -1); f.z = fizzZ(); }
        continue;
      }
      // The flow carrying its rim within FOAM_CATCH of a surface (the whole disc, so big bubbles never poke
      // through), or into the foam already there (it joins at the back): at the surface the rise heads for it
      // parks (settleFoam); anywhere else it is recycled at the side the flow comes from. A bubble the flow does
      // not carry into a surface only rides it, centre held inside, floating half out like the foam.
      const bool outR = vx > 0 && f.x > discFitLow(t.fizzSurf, H, f.y, r, 1) - FOAM_CATCH && f.x > discFit(t.fizzSurf, H, f.y, r, 1) - FOAM_CATCH,
                 outL = vx < 0 && -f.x > discFitLow(t.fizzSurfL, H, f.y, r, -1) - FOAM_CATCH && -f.x > discFit(t.fizzSurfL, H, f.y, r, -1) - FOAM_CATCH;
#ifdef FIZZ_PROF
      FZ_T0(tf0);
      const bool touch = (side > 0 && outR) || (side < 0 && outL) || (side != 0 && touchesFoam(t, w, f, r, p, side));
      FS_ADD(FS_CYC_TOUCH, tf0);
      if (touch) { f.life = side * p.fizzFoamLife * (0.5f + frand()); parked(k, r); }
#else
      if ((side > 0 && outR) || (side < 0 && outL) || (side != 0 && touchesFoam(t, w, f, r, p, side))) {
        f.life = side * p.fizzFoamLife * (0.5f + frand()); parked(k, r);
      }
#endif
      else if ((outR || outL) && spring) fizzFree(f);
      else if (outR || outL) { f.v = fizzV(); f.y = fizzSpawnY(p, H, f.v); fizzRespawnX(t, p, f, vx < 0 ? 0 : 1); f.z = fizzZ(); }
      else f.x = fmx(-foamFront(t.fizzSurfL, H, f.y, -1), fmn(foamFront(t.fizzSurf, H, f.y, 1), f.x));
    }
    FS_ADD(FS_CYC_LOOP, lp0);
    FZ_T0(cd0);
    if (spring) {
      // Cadence: fizzSourceRate bubbles/s (shaking nucleates up to twice as many), each into an idle slot (the first,
      // else a new one); idle slots at the end are dropped, so the loops stay as short as the bubbles in flight.
      // The tube holds at most its fizzCount share (fizzWant, foam included): at it a birth waits for a bubble to
      // leave, keeping one birth of credit and no more, so a stream the tilt keeps in the liquid (a drift that
      // stalls or keeps reversing) thins out instead of filling the pool, and no burst follows. Bubbles already
      // over a count that dropped (a shorter column) live on. See sim.
      const int cap = fizzWant(p, len, agitation);   // <= FIZZ_POOL: a slot is always there below it
      int live = 0;
      for (int k = 0; k < t.fizzN; k++) if (t.fizz[k].v != 0) live++;
      t.springClock += fmx(0, p.fizzSourceRate) * (1 + (agitation < 0.05f ? 0 : agitation)) * dt;
      int slot = 0;
      while (t.springClock >= 1) {
        if (live >= cap) { t.springClock = 1; break; }
        while (slot < t.fizzN && t.fizz[slot].v != 0) slot++;
        if (slot == t.fizzN) t.fizz[t.fizzN++] = { 0, 0, 0, 0, 0 };
        if (springBirth(t)) springSpawn(t, p, t.fizz[slot]); else fizzScatter(t, p, t.fizz[slot]);
        t.springClock -= 1; live++;
      }
      while (t.fizzN > 0 && t.fizz[t.fizzN - 1].v == 0) t.fizzN--;
    }
    FS_ADD(FS_CYC_CADENCE, cd0);
    FZ_T0(se0);
    if (side != 0) settleFoam(t, p, speed, side > 0 ? t.fizzSurf : t.fizzSurfL, side, dt, glass, vy);
    FS_ADD(FS_CYC_SETTLE, se0);
  }
  FS_ADD(FS_CYC, st0);
}
void stepFizz(const Params &pH, const Params &pM, float dt, float along, float across, float agitation) {
  stepFizzTube(0, pH, dt, along, across, agitation); stepFizzTube(1, pM, dt, along, across, agitation);
}
#if TUBE_COUNT == 3
void stepFizz(const Params &pH, const Params &pM, const Params &pS, float dt, float along, float across, float agitation) {
  stepFizz(pH, pM, dt, along, across, agitation); stepFizzTube(2, pS, dt, along, across, agitation);
}
#endif

// Magnification for a bubble of radius r at float row y: mean of the row table over the rows the
// pre-squashed sprite covers, iterated once (see sim fizzMag). Single-row reads snap between rows.
static float fizzMag(const float *mag, int H, float y, float r) {
  float m = 1;
  for (int it = 0; it < 2; it++) {
    // Clamp into the tube with a <= b: a bubble stranded past a shrunken tube (tubeHeight pushed while fizz
    // is on) otherwise gets an empty range, magnification 0 and an unbounded draw loop (task-wdt on core 0).
    float ry = r / m;
    int a = (int)fmn(H - 1, fmx(0, ffloor(y - ry))), b = (int)fmx(a, fmn(H - 1, fceil(y + ry)));
    float s = 0; for (int i = a; i <= b; i++) s += mag[i];
    m = s / (b - a + 1);
  }
  return m;
}
// Lens magnification per row: rendered lens (supersampled row map, per source row) x physical glass
// (topLens, continuous) x center-weighted fizzSquash. See sim lensMagRows.
inline float Tube::fizzSquashRow(const Params &p, int y) const {
  float d = (y + 0.5f - H / 2.0f) / (H / 2.0f);   // full fizzSquash at mid-height, ~1 at the edges
  return 1 + (p.fizzSquash - 1) * (1 - d * d);
}
static bool lensExponent(float lens, float curve, float &strength, float &e) {
  float signedCurve = lens < 0 ? -curve : curve; strength = fabsf(lens);
  if (strength == 0 || signedCurve == 0) return false;
  e = signedCurve > 0 ? 1 + signedCurve * 2 : 1 / (1 - signedCurve * 2);
  return true;
}
void Tube::lensMagRows(const Params &p, float *rows) const {
  for (int y = 0; y < H; y++) rows[y] = 1;
  float curve = clampf(p.lensCurve, -3, 3), strength, e;
  if (lensExponent(clampf(p.lens, -1, 1), curve, strength, e)) {
    // Supersampled row map averaged per source row (see sim); dropped rows inherit the previous row.
    const int N = 8;
    float sum[TUBE_HEIGHT_MAX] = {0}, cnt[TUBE_HEIGHT_MAX] = {0};
    for (int i = 0; i < H * N; i++) {
      float d = ((i + 0.5f) / N - H / 2.0f) / (H / 2.0f), u = fabsf(d);
      float s = (d < 0 ? -1 : 1) * ((1 - strength) * u + strength * powf(u, e));
      int src = (int)clampf(ffloor(H / 2.0f + s * H / 2.0f), 0, H - 1);
      sum[src] += 1 / ((1 - strength) + strength * e * powf(u, e - 1)); cnt[src]++;
    }
    float last = 1;
    for (int y = 0; y < H; y++) if (cnt[y] > 0) { last = sum[y] / cnt[y]; break; }
    for (int y = 0; y < H; y++) rows[y] = cnt[y] > 0 ? (last = sum[y] / cnt[y]) : last;
  }
  if (lensExponent(clampf(p.topLens, -1, 1), curve, strength, e)) {
    for (int y = 0; y < H; y++) {
      float u = fmx(1.0f / H, fabsf((y + 0.5f - H / 2.0f) / (H / 2.0f)));
      rows[y] /= (1 - strength) + strength * e * powf(u, e - 1);
    }
  }
  for (int y = 0; y < H; y++) rows[y] = clampf(rows[y] * fizzSquashRow(p, y), 0.2f, 5);
}

// ---------------------------------------------------------------------------------------------
// tube
// ---------------------------------------------------------------------------------------------
// Row coordinate -1..1 as seen through the physical glass (meniscusLens, same warp as topLens).
static float lensRow(float d, const Params &p) {
  float lens = clampf(p.meniscusLens, -1, 1), strength = fabsf(lens);
  float curve = clampf(p.lensCurve, -3, 3), signedCurve = lens < 0 ? -curve : curve;
  if (strength == 0 || signedCurve == 0) return d;
  float exponent = signedCurve > 0 ? 1 + signedCurve * 2 : 1 / (1 - signedCurve * 2);
  float u = fabsf(d);
  return (d < 0 ? -1 : 1) * ((1 - strength) * u + strength * powf(u, exponent));
}
// Contact-angle meniscus, the same for both ends of a slug (sim capShape): a spherical cap set by the
// end's contact angle — the static angle moved by the hydrostatic head along the slug (tilt = along
// follower into this end) and by the column's travel against the pinned wall ring (pin, px), held within
// the hysteresis band; a dragged line (lineV = outward px/s, 0 while held) is pushed further by
// Cox–Voinov. side = across follower (sag ∝ Bond number), cap = wobble, k = per-end short-column limit
// (sim capScale).
#define MENISCUS_SAG_K 1.0f
CapShape Tube::capShape(const Params &p, float len, float tilt, float side, float cap, float pin, float lineV) const {
  const ContactLeads cl = contactLeads(p, len, tilt, MM_PER_PX_AT(TUBE_PX_SCALE(idx)));
  const float R = cl.R, rad = (float)M_PI / 180, PI = (float)M_PI;
  // the held ring's lead inside the band, back to its angle (lead = R·tan(pi/4 - theta/2))
  float th = PI / 2 - 2 * atanf(clampf(cl.rest - pin, cl.adv, cl.rec) / R);
  float dyn = fmx(0, p.contactDyn) * rad, g = dyn * dyn * dyn / FILM_FULL_PX_S_AT(TUBE_PX_SCALE(idx));
  th = cbrtf(clampf(th * th * th + g * lineV, 0, PI * PI * PI));
  float lc = fmx(0.1f, p.capLength), Rmm = R * MM_PER_PX_AT(TUBE_PX_SCALE(idx));
  CapShape c;
  c.cosT = cosf(th);
  float sinT = sinf(th);
  c.h = R * c.cosT / (1 + sinT);
  c.asym = MENISCUS_SAG_K * (Rmm / lc) * (Rmm / lc) * side * (c.cosT < 0 ? -1.0f : c.cosT > 0 ? 1.0f : 0.0f);
  c.cap = cap;
  c.k = fmn(1, fmx(0, len) / 2 / fmx(1, fabsf(c.h) * (1 + fabsf(c.asym)) + fabsf(cap)));
  return c;
}
// Cap profile: px the surface at row ry leads the surface centre along +x: the spherical cap through
// the ring (stable form), sagged by the across tilt (clamped at 0), minus the wobble mode u^2. See sim edgeCap.
inline float Tube::edgeCap(int ry, const CapShape &c) const {
  const float R = rc.boreR, u2 = rc.rowU2[ry];
  float sphere = c.cosT * R * u2 / (1 + sqrtf(fmx(0, 1 - c.cosT * c.cosT * u2)));
  return sphere * fmx(0, 1 + c.asym * rc.rowD[ry]) - c.cap * u2;
}
// Px an end's cap can reach into the column at a wall row (0 for a concave cap at rest): what the two leans of
// a free slug have to leave of the gap between the edge centres (sim edgeSkews).
static inline float capReach(const CapShape &c) {
  return c.k * fmx(0, fabsf(c.h * c.asym) + fabsf(c.cap) - c.h);
}
// tanA = the end's skew, px per row, hoisted per tube (was recomputed per row).
inline float Tube::edgeX(int ry, float xe, float tanA, const CapShape &c) const {
  const float yc = (H - 1) / 2.0f;
  return xe + tanA * (ry - yc) + c.k * edgeCap(ry, c);
}
// Home-end edge of a free slug centred at xs: mirror image of edgeX (its CapShape takes the mirrored
// forcing, tanA is the home end's own skew), flattening onto the end cap.
inline float Tube::edgeXL(int ry, float xs, float tanA, const CapShape &c) const {
  const float yc = (H - 1) / 2.0f;
  return xs + fmn(1, xs / 8) * (tanA * (ry - yc) - c.k * edgeCap(ry, c));
}
// Wall-ring lead: the contact ring all round the bore (edgeCap at u = 1, across sag interpolated
// by the row's d) — one x per row seen side-on; the visible surface at a row is the lens between
// edgeCap (the mid-depth section) and this. Meets edgeCap at the wall rows. See sim wallCap.
inline float Tube::wallCap(int ry, const CapShape &c) const {
  return c.h * fmx(0, 1 + c.asym * rc.rowD[ry]) - c.cap;
}
inline float Tube::wallX(int ry, float xe, float tanA, const CapShape &c) const {
  const float yc = (H - 1) / 2.0f;
  return xe + tanA * (ry - yc) + c.k * wallCap(ry, c);
}
inline float Tube::wallXL(int ry, float xs, float tanA, const CapShape &c) const {
  const float yc = (H - 1) / 2.0f;
  return xs + fmn(1, xs / 8) * (tanA * (ry - yc) - c.k * wallCap(ry, c));
}


void Tube::buildRowCache(const Params &p, uint32_t gen) {
  if (rc.valid && rc.gen == gen && rc.H == H) return;
  rc.valid = true; rc.gen = gen; rc.H = H;
  markSourceRows(H, p.tickLens, rc.tickWet);
  markSourceRows(H, p.tickDryLens, rc.tickDry);
  rc.tickFollow = rearTicksFollowDigits(p);
  if (rc.tickFollow) {
    markSourceOffsets(H, p.digitDryLens, digitOff); markSourceOffsets(H, p.bottomLens, digitOff + TUBE_HEIGHT_MAX);
    const MarkWarp tick(p.tickDryLens), digit(p.digitDryLens);
    const float heights[2][2] = {{p.tickMinorHeightH, p.tickMajorHeightH}, {p.tickMinorHeightM, p.tickMajorHeightM}};
    for (int m = 0; m < 2; m++) for (int j = 0; j < 2; j++) {
      const float h = fmx(0, jround(heights[m][j])), t = clampf((h - H / 2.0f) / (H / 2.0f), -1, 1), u = tick.inv(fabsf(t));
      rc.tickEdge[m][j] = (t < 0 ? -1 : t > 0 ? 1 : 0) * digit.at(u) * H / 2.0f;
    }
  }
  lensMagRows(p, rc.mag);
  {
    float lens = clampf(p.lens, -1, 1), curve = clampf(p.lensCurve, -3, 3);
    float signedCurve = lens < 0 ? -curve : curve, strength = fabsf(lens);
    rc.lensOn = !(strength == 0 || signedCurve == 0); rc.lensPos = signedCurve > 0;
    float exponent = signedCurve > 0 ? 1 + signedCurve * 2 : 1 / (1 - signedCurve * 2);
    for (int yd = 0; yd < H; yd++) {
      float d = (yd + 0.5f - H / 2.0f) / (H / 2.0f), u = fabsf(d);
      float s = (d < 0 ? -1 : 1) * ((1 - strength) * u + strength * powf(u, exponent));
      rc.lensSrc[yd] = (int16_t)clampf(ffloor(H / 2.0f + s * H / 2.0f), 0, H - 1);
    }
  }
  const float yc = (H - 1) / 2.0f;
  rc.boreR = boreR(p);
  // wall-band ease (sim boreRow): D = outer / bore radius, eased from a0 onto 1 at the outer edge
  // with g(s) = (4 - n)s^3 + (n - 3)s^4 (n <= 4) or s^n: no s^2 term, so a 0°/180° cap meets the edge flat
  const float easeD = yc / rc.boreR, easeA0 = fmx(0, 2 - easeD), easeDl = 1 - easeA0, easeTau = easeD - easeA0;
  const float easeN = easeTau / easeDl;
  for (int ry = 0; ry < H; ry++) {
    int x0 = 0;
    if (p.cornerR > 0) {
      float r = fmn(p.cornerR, H / 2.0f), dy = fabsf(ry - yc);
      if (dy > yc - r) { float k = (dy - (yc - r)) / r; x0 = (int)jround(r - sqrtf(fmx(0, 1 - k * k)) * r); }
    }
    rc.capX0[ry] = x0;
    // across the bore; the wall band eases C1 onto the contact ring at the outer edge (sim boreRow)
    const float a = fabsf(ry - yc) / rc.boreR;
    float ua = easeD <= 1 ? fmn(1, a) : a;
    if (easeD > 1 && a > easeA0) {
      const float s = fmx(0, easeD - a) / easeTau, s3 = s * s * s;
      ua = 1 - easeDl * (easeN <= 4 ? (4 - easeN) * s3 + (easeN - 3) * s3 * s : powf(s, easeN));
    }
    float d = lensRow(ry < yc ? -ua : ua, p), u = fabsf(d);
    rc.rowD[ry] = d; rc.rowU2[ry] = u * u;
  }
  RGB hi888 = ambientize(scale(hexToRgb(p.liquidHi), p.brightness * p.liquidBright), ambientBodyL(p), ambientAmt(p));
  rc.hiC = q(hi888);
  // pure liquid colour (no transparency mix) halfway to the highlight: brighter and more saturated than the body
  RGB liquid888 = scale(hexToRgb(p.liquid), p.brightness * p.liquidBright);
  rc.lensC = q(mix(liquid888, hi888, 0.55f));
  rc.darkC = q(scale(liquid888, 0.35f));
  rc.toneC = p.surfaceTone < 0 ? rc.darkC : rc.hiC; rc.toneT = alphaT(fmn(1, fabsf(p.surfaceTone)));
}

void Tube::applyLens(const Params &p) {
  if (!rc.lensOn) return;
  auto copyRow = [&](int yd) {
    int sy = rc.lensSrc[yd];
    if (sy != yd) memcpy(FB + (size_t)yd * PANEL_W, FB + (size_t)sy * PANEL_W, PANEL_W * 2);
  };
  if (rc.lensPos) {
    for (int yd = 0; yd < H / 2; yd++) copyRow(yd);
    for (int yd = H - 1; yd >= H / 2; yd--) copyRow(yd);
  } else {
    for (int yd = H / 2 - 1; yd >= 0; yd--) copyRow(yd);
    for (int yd = H / 2; yd < H; yd++) copyRow(yd);
  }
}

// `remaining`: liquid at the right end, draining. Its base is rendered in a mirrored frame, then
// flipped before panel-coordinate marks and bubbles are composited.
// Edge-effect blend tables: (row, k) -> 565, a function of the palette and lightK only. Rebuilt when
// lightK moves (exact compare: at rest it is constant, in motion it changes every frame anyway).
// Front brightening has no table (frontBright is wider than EFFECT_MAX in practice); it takes the direct path below.
// glow: blend(tubeBack, row, min(1, t*t*glowStrength*lightK)) as 565; front: alphaT(min(1, t*t*0.85*lightK*rowK)).
// Index [ry * EFFECT_MAX + k]. Returns nullptr when the effect is wider than the table (caller computes directly).
const uint16_t *Tube::effectTable(EffectTable &T, const Params &p, const Palette &pal, uint32_t gen, float lightK, bool glow) const {
  int n = glow ? (int)fceil(p.edgeGlow) : (int)p.frontBright;
  if (n > EFFECT_MAX) return nullptr;
  if (T.valid && T.gen == gen && T.H == H && T.lightK == lightK) return T.c;
  T.valid = true; T.gen = gen; T.H = H; T.lightK = lightK;
  for (int ry = 0; ry < H; ry++) for (int k = 0; k < n; k++) {
    uint16_t *o = T.c + ry * EFFECT_MAX + k;
    if (glow) { float t = 1 - k / p.edgeGlow; *o = blend565(pal.tubeBackRows[ry], pal.rows[ry], fmn(1, t * t * p.glowStrength * lightK)); }
    else { float t = 1 - (k + 1) / p.frontBright; *o = (uint16_t)alphaT(fmn(1, t * t * 0.85f * lightK * pal.rowK[ry])); }
  }
  return T.c;
}

void Tube::drawTube(int y0, const TubeState &st, const Params &p, uint32_t gen, int ticksN) {
  TU_T0();
  TubeState s = st;
  const bool mir = mirrored(p);
  if (mir) { s.fillPos = -st.fillPos; s.edgeLight = -st.edgeLight; s.cap = -st.cap; }
  float len = columnLen(s.fillTarget, p);
  float xs = p.freeLiquid ? (mir ? L - len - s.slugPos : s.slugPos) : 0;   // home-end edge centre
  float xe = xs + len + clampf(s.fillPos, -len, len);                                // time-edge centre; slosh can't exceed the volume
  float lightK = fmx(0.25f, 1 + p.edgeLightGain * s.edgeLight) * (1 + s.agitation);
  float lightKL = fmx(0.25f, 1 - p.edgeLightGain * s.edgeLight) * (1 + s.agitation);
  int xsI = (int)jround(xs);
  // Per-end meniscus: the home end takes the mirrored forcing; the pinned-line state is already in each
  // end's own outward sense (physics). See sim drawTube.
  const CapShape capR = capShape(p, len, s.edgeLight, s.acrossTilt, s.cap, s.pinFree, s.lineVFree);
  const CapShape capL = capShape(p, len, -s.edgeLight, s.acrossTilt, -s.cap, s.pinHome, s.lineVHome);
  // Skew per end: the liquid lies on the low wall at both, so the home end leans the other way; off the
  // end cap the two leans share what the gap has left past both caps and the time edge's remaining free lean
  // (one budget for the pair), so the lean never makes the ends cross. See sim edgeSkews.
  const float tanA = tanf(s.angle * (float)M_PI / 180), ycA = fmx(1, (H - 1) / 2.0f), offA = clampf(xs / 8, 0, 1);
  const float leanLim = fmx(0, xe - xs - capReach(capR) - offA * capReach(capL) - (1 - offA) * fabsf(tanA) * ycA) / (2 * ycA);
  const float lean = clampf(tanA, -leanLim, leanLim);
  const float tanR = tanA + offA * (lean - tanA), tanL = -lean;
  const bool hasLiquid = xe - xs >= 0.5f;   // an empty column draws nothing, not even an AA sliver
  fizzShift = xs;
  ensureFizz(p, clampf(xe - xs - 6, 0, L), s.agitation);
  fizzExposed = (xe < L - 0.5f ? 1 : 0) | (p.freeLiquid && xs > 0.5f ? 2 : 0);

  int softW = p.edgeSoft > 0 ? (int)fmx(1, jround(p.edgeSoft)) : 0;
  const bool traceMode = p.traces && p.traceAmount > 0 && st.trace;

  // Cached edge geometry, before the residue backing and liquid body.
  const int16_t *capX0 = rc.capX0;
  for (int ry = 0; ry < H; ry++) {
    float ex = edgeX(ry, xe, tanR, capR);
    float exL = p.freeLiquid ? edgeXL(ry, xs, tanL, capL) : 0;
    edges[ry] = ex; edgesL[ry] = exL;
    fizzSurf[ry] = ex - xs; fizzSurfL[ry] = exL - xs;   // surface fronts for stepFizz (foam parks on the profile)
  }
  TU_MARK(TU_BACK);

  // Residue and wet film form the backing UNDER the liquid. Paint them first, then
  // blend the body AA over that backing once. Masking residue by (1 - coverage)
  // over an already-AA body leaks the bare tube colour at their junction.
  // The residue's per-frame terms (computed here once; its rows are drawn band by band below).
  bool trRows = false, bandR = false, bandL = false, shearR = false, shearL = false;
  int trN = 0, trA0 = 0, trA1 = 0, aLo = 65535, aHi = 0, trG = 0, trZ = 257;   // aLo / aHi: path coefficient band of the span (traceFillRow's LUT); trZ: first visible phi index
  float invSoftW = 0, invN = 0, invBW = 1, etaR = 0, etaL = 0, visR = 0, visL = 0, ZR = 1, ZL = 1, invZR = 1, invZL = 1;
  if (traceMode) {
    const float hw = softW * 0.5f;
    const int N = p.wetFilm > 0 ? (int)fmx(1, jround(p.wetFilm)) : 0; trN = N;
    bandR = hasLiquid && N > 0 && s.filmFree > 0.02f;
    bandL = hasLiquid && N > 0 && p.freeLiquid && s.filmHome > 0.02f;
    invSoftW = softW > 0 ? 1.0f / softW : 0.0f;
    invN = N > 0 ? 1.0f / N : 0.0f; invBW = 1.0f / (softW > 1 ? softW : 1);
    // film thickness per edge (eta * follower) and its visibility, fading out with the follower from 0.2 to
    // the 0.02 gate (see sim: a tangent row sees a vanishing film at full chord)
    const float filmFull = FILM_FULL_PX_S_AT(TUBE_PX_SCALE(idx)), eta = filmEta(p, filmFull, filmFull); etaR = bandR ? eta * s.filmFree : 0.0f; etaL = bandL ? eta * s.filmHome : 0.0f;
    visR = bandR ? ease((0.2f - s.filmFree) * (1.0f / 0.18f)) : 0.0f; visL = bandL ? ease((0.2f - s.filmHome) * (1.0f / 0.18f)) : 0.0f;
    // Columns that may receive residue or band: the occupied residue range (physics keeps
    // [traceLo, traceHi) tight) mirrored into the render frame, plus each band's reach over all rows.
    // Permanent film (traceFilm, a share of the thin-film cap, see sim): every column carries residue at least
    // that thick, so the range is the whole tube and the per-column thickness floors there.
    const float filmV = p.traceFilm > 0 ? fmn(1.0f, p.traceFilm) : 0.0f;
    int lo = L, hi = 0;
    if (filmV > 0) { lo = 0; hi = L; }
    else if (st.traceHi > st.traceLo) { lo = mir ? L - st.traceHi : st.traceLo; hi = mir ? L - st.traceLo : st.traceHi; }
    // Imminent residue (see sim): within Z = 2 max|Delta| px of a liquid edge the residue is sampled
    // Delta * w back, Delta = this row's contact line minus the edge centre physics deposits at, so the
    // fresh smear hugs the meniscus — only where a deposit lies within reach and on rows with |Delta| >= 1/8.
    float dR = 0, dL = 0, eR0 = L, eR1 = 0, eL0 = L, eL1 = 0;
    for (int ry = 0; ry < H; ry++) {
      dR = fmx(dR, fabsf(edges[ry] - xe)); eR0 = fmn(eR0, edges[ry]); eR1 = fmx(eR1, edges[ry]);
      dL = fmx(dL, fabsf(edgesL[ry] - xs)); eL0 = fmn(eL0, edgesL[ry]); eL1 = fmx(eL1, edgesL[ry]);
    }
    ZR = fmx(1, 2 * dR); ZL = fmx(1, 2 * dL); invZR = 1.0f / ZR; invZL = 1.0f / ZL;
    const int depLo = mir ? L - st.traceHi : st.traceLo, depHi = mir ? L - st.traceLo : st.traceHi;
    auto nearDep = [depLo, depHi](float e0, float e1, float z) { return depHi > depLo && depLo < e1 + z + 4 && depHi > e0 - z - 4; };
    shearR = hasLiquid && dR >= 0.125f && nearDep(eR0, eR1, ZR);
    shearL = hasLiquid && p.freeLiquid && dL >= 0.125f && nearDep(eL0, eL1, ZL);
    const float extR = fmx(bandR ? (float)N : 0.0f, shearR ? ZR : 0.0f), extL = fmx(bandL ? (float)N : 0.0f, shearL ? ZL : 0.0f);
    if (extL > 0 || extR > 0) for (int ry = 0; ry < H; ry++) {
      if (extL > 0) { int a = (int)ffloor(edgesL[ry] - extL), b = (int)fceil(edgesL[ry] + hw) + 1; if (a < lo) lo = a; if (b > hi) hi = b; }
      if (extR > 0) { int a = (int)ffloor(edges[ry] - hw), b = (int)fceil(edges[ry] + extR) + 1; if (a < lo) lo = a; if (b > hi) hi = b; }
    }
    if (hi > lo) {
      // widened +-4 for the blur reach (and 4 more for the columns the blur reads); columns outside
      // the residue range are guaranteed zero and the band only reads its own columns.
      const int a0 = lo - 4 < 0 ? 0 : lo - 4, a1 = hi + 4 > L ? L : hi + 4;
      const int c0 = a0 - 4 < 0 ? 0 : a0 - 4, c1 = a1 + 4 > L ? L : a1 + 4;
      // Memo across frames (step 6): traceA[x] is a function of traceRaw over [x - 4, x + 4] (clamped), filmV, x and
      // the tube only, so a column is recomputed only where its window holds a changed or unknown value or it was not
      // computed last frame (pinned, the stain dried: none; the blur and streak were ~1.1 ms a tube).
      traceBlur(st.trace, mir, a0, a1, c0, c1, filmV, aLo, aHi);
      trRows = true; trA0 = a0; trA1 = a1;
      trG = (int)(p.traceAmount * 256 + 0.5f);   // stain depth gain 1/256
      // the first phi index whose depth shows (T > 0, depthT's rounding) at this gain: FILM_PHI is non-decreasing, so
      // every coat whose index is below it takes T 0 (depthT and depthF alike)
      trZ = 1;   // FILM_PHI[0] = 0
      while (trZ <= 256 && (((trZ >= 256 ? 256 : FILM_PHI[trZ]) * trG + 128) >> 8) == 0) trZ++;
    }
  }
  TU_MARK(TU_TRPREP);
  float strokeA = 0, pullR = 0, pullL = 0, veilA = 0;   // 3e: the stroke's opacity; receding pull per edge; foam veil opacity

  // Step 9, facts first: what the marks read per row, before the band loop (the tiled marks run inside it). The 3e
  // band's per-frame terms and, per row and edge, its stroke width and layer weights (strokeR / L, bandFill / Blick /
  // Rim: the band loop draws the stroke from the same expressions, concave()), the mark bounds, the wet share, the
  // label layout and the marks' plans. None of them reads a pixel.
  const bool band3e = hasLiquid && p.surfaceBand > 0;
  // interior opacity of the dish (surfaceFill; rim and blick keep their own) and the blick's per-row
  // weight: a tent centred at the light angle's highlight row, BLICK_H of the tube tall (see sim blickRow)
  const float fill = clampf(p.surfaceFill, 0, 1);
  float blickY = 0, blickInvH = 0;
  if (band3e) {
    // opaque from surfaceBand ~0.6 whatever the light; the unlit edge gets a darker stroke; motion
    // never fades it, only reshapes the dish through TubeState.cap (see sim)
    strokeA = fmn(1, 1.6f * p.surfaceBand);
    // dynamic contact angle: a receding line (~0° by half the full-film speed) is liquid thinning into
    // its film — liquid colour, no shoulder or rim; instantaneous edge speed, so both are back once the
    // line stops (see sim)
    const float recede = mir ? 1 : -1;
    const float filmFull = FILM_FULL_PX_S_AT(TUBE_PX_SCALE(idx));
    pullR = clampf(2 * recede * (s.fillVel + s.slugVel) / filmFull, 0, 1);
    pullL = p.freeLiquid ? clampf(-2 * recede * s.slugVel / filmFull, 0, 1) : 0.0f;
    veilA = FOAM_VEIL * strokeA * fill;
    const float yc = (H - 1) / 2.0f;
    blickY = yc - yc * sinf(s.light * (float)M_PI / 180); blickInvH = 1 / fmx(2, BLICK_H * H);
  }
  auto blickRow = [&](int ry) __attribute__((always_inline)) -> float {
    return p.surfaceBlick > 0 ? p.surfaceBlick * fmx(0, 1 - fabsf(ry - blickY) * blickInvH) : 0.0f; };
  // A concave ring (tw > 0: its lead in the edge's outward sense): its opacity a, width wEff, blick and rim weights;
  // false = below visible opacity (no stroke, rim or band for the marks).
  auto concave = [&](int ry, float tw, int dir, float lk, float &a, float &wEff, float &blickK, float &rimK) __attribute__((always_inline)) -> bool {
    a = strokeA * fmn(1, tw);
    if (a < 1 / 255.0f) return false;
    wEff = fmn(p.surfaceWidth, tw);
    const float pull = dir > 0 ? pullR : pullL;
    blickK = blickRow(ry) * fmn(1, lk) * (1 - pull);
    // the ring is a thin liquid lens: lit (light side, row shaded) over a dark back, a deep liquid tone
    // at light-independent opacity over a light one; backK blends the two (sim rimK / rimC)
    const float backK = palCache->bandBackK[ry];
    rimK = p.surfaceRim * fmn(1, wEff / 2) * (1 - pull) * ((1 - backK) * (0.5f + 0.5f * pal.rowK[ry]) * fmn(1, lk) + backK);
    return true;
  };
  for (int ry = 0; ry < H; ry++) {
    strokeR[ry] = strokeL[ry] = 0;
    bandFill[0][ry] = bandFill[1][ry] = bandBlick[0][ry] = bandBlick[1][ry] = bandRim[0][ry] = bandRim[1][ry] = 0;
    if (band3e) {   // the rear-mark compositor's layer weights (Mark::bandMark) and the strokes (fizz veil)
      auto facts = [&](float xm, float xw, int dir, float lk, int side, float *stroke) __attribute__((always_inline)) {
        const float tw = dir * (xw - xm);
        if (!(tw > 0)) return;   // flat or convex: no stroke
        float a, wEff, blickK, rimK;
        if (!concave(ry, tw, dir, lk, a, wEff, blickK, rimK)) return;
        bandFill[side][ry] = a * fill; bandBlick[side][ry] = a * blickK; bandRim[side][ry] = a * rimK;
        stroke[ry] = wEff;
      };
      facts(edges[ry], wallX(ry, xe, tanR, capR), 1, lightK, 0, strokeR);
      if (p.freeLiquid) facts(edgesL[ry], wallXL(ry, xs, tanL, capL), -1, lightKL, 1, strokeL);
    }
    // Panel-frame column bounds for the mark compositor (liquid where lo <= x < hi): the body only. The
    // concave band past it is composited per pixel by its own layer opacities (Mark::bandMark, render
    // frame), so a faint or receding band never hides a mark as liquid and there is no threshold (see sim).
    const float lo = edgesL[ry], hi = edges[ry];
    if (mir) { boundLo[ry] = L - hi; boundHi[ry] = L - lo; } else { boundLo[ry] = lo; boundHi[ry] = hi; }
  }
  const BandInfo band{{edges, edgesL}, {strokeR, strokeL}, {bandFill[0], bandFill[1]}, {bandBlick[0], bandBlick[1]},
                      {bandRim[0], bandRim[1]}, {pullR, pullL}, softW * 0.5f, mir, L};
  Edges bounds{boundLo, boundHi, hasLiquid && p.surfaceBand > 0 ? &band : nullptr};
  if (!p.ticksOnTop || !p.digitsOnTop) buildWetShare(bounds, H, wetShare, wetRun);
  TU_MARK(TU_BOUNDS);

  // The marks' plans (MarkPlan), all before bubbles; the tick and digit layers each sit behind or on top (one each).
#ifdef DIGIT_PROF
  uint32_t profT = esp_timer_get_time();
#endif
  const bool haveLabels = layoutLabels(y0, p, gen, ticksN, st, st.fillTarget, labels);
#ifdef DIGIT_PROF
  prof[8] = esp_timer_get_time() - profT;
#endif
  Mark tickMark(*this, y0, bounds, p, p.ticksOnTop, p.markContrast * p.tickBright);
#ifdef TICK_PROF
  tickMark.prof = tickProf;
  const uint32_t tc0 = esp_cpu_get_cycle_count();
#endif
  const bool tickFacts = planTicks(y0, p, ticksN, rc.tickWet, p.ticksOnTop ? rc.tickWet : rc.tickDry, p.ticksOnTop ? nullptr : &bounds, tickMark,
                                   p.ticksOnTop ? 0 : -st.edgeLight * p.tickParallax, p.ticksOnTop ? 0 : st.acrossTilt * p.tickParallax);
#ifdef TICK_PROF
  tickProf[TP_CYC] += esp_cpu_get_cycle_count() - tc0; tickProf[TP_FRAMES]++;
#endif
  const bool rearFacts = !p.ticksOnTop && tickFacts;   // the rear tick layer leaves each band's row facts for the rear digits
  const bool bakedD = haveLabels && labels.sprite && labels.shadow >= 0;
  float floorC; uint16_t floorR; floorBake(p, floorC, floorR);
  Mark digitMark(*this, y0, bounds, p, p.digitsOnTop, p.markContrast * p.digitBright, bakedD, bakedD && floorC > 0);
  // Sprite digits take no surface band (sim drawDigitLayer): its rim, blick and dish are not layered over them
  // (step 8 of the LCD perf plan, a look decision: the runs need no per-pixel band test). Bitmap digits keep it.
  if (haveLabels && labels.sprite) digitMark.edges.band = nullptr;
  const Warp digitWarp(p.digitsOnTop ? nullptr : wetShare);
  if (haveLabels) planLabels(labels, digitWarp, y0);
  // 5: fizz — AA discs, pre-squashed by the local lens magnification (see sim step 5)
  if (p.fizz) {
    FZ_T0(fz0);
#ifdef FIZZ_PROF
    fizzProf[FZ_FRAMES]++;
#endif
    const FizzFrame ff{rc.mag,
                       (H - 1) / 2.0f * (1 - sinf(st.light * (float)M_PI / 180)),   // highlight row (continuous, from the light angle): the core shifts away from it, the pinpoint toward it (see sim)
                       2.0f / H,                // one division per tube, not per bubble
                       mir ? -1.0f : 1.0f,      // liquid frame mirrored under remaining
                       veilA, pullR, pullL, xsI, L,
                       q({255 * p.brightness, 255 * p.brightness, 255 * p.brightness}),   // sim blickC
                       mir};
    planFizz(p, ff);
    FZ_ADD(fizzProf, FZ_CYC, fz0);
  }
  // 6: bubble
  const float bx = xe - p.bubbleGap - s.edgeLight * p.bubbleTiltGain, by = (H - 1) * p.bubbleY - (H - 1) / 2.0f * s.acrossTilt * p.bubbleRollGain;
  const float brx = p.bubbleW / 2, bry = p.bubbleH / 2;
  const bool bubbleOn = p.bubble && bx - brx > xs + 2;
  // The strip lens (applyLens) maps rows onto others: where it runs on the strip (digits printed over it), it and those
  // digits stay after the band loop, on the strip; the push applies it otherwise (lensRowsOut).
  const bool lensOut = lensRowsOut && !(haveLabels && p.digitsOnTop);
  const bool stripLens = !lensOut && rc.lensOn;
  TU_MARK(TU_LABELS);
  auto mapX = [&](int x) { return mir ? L - 1 - x : x; };
  auto span = [&](int y, int xa, int xb, uint16_t c) {
    if (mir) hspan(y, L - 1 - xb, L - xa, c);
    else hspan(y, xa, xb + 1, c);
  };
  // Every mark stage over tube rows [r0, r1) (a band, or the whole tube), in the frame's order: rear ticks, rear digits,
  // fizz, bubble, top ticks, and (topDigits) the top digits.
  auto marks = [&](const int r0, const int r1, const bool topDigits) {
#ifdef DIGIT_PROF
    uint32_t profM = esp_timer_get_time();
#endif
    if (!p.ticksOnTop) tickBand(y0, tickMark, r0, r1);
    TU_MARK(TU_TICKS);
#ifdef DIGIT_PROF
    prof[9] += esp_timer_get_time() - profM; profM = esp_timer_get_time();
#endif
    if (haveLabels && !p.digitsOnTop) labelBand(y0, labels, digitWarp, digitMark, rearFacts, r0, r1);
    TU_MARK(TU_DIGITS);
#ifdef DIGIT_PROF
    prof[10] += esp_timer_get_time() - profM;
#endif
    if (p.fizz) {
      FZ_T0(fz1);
      fizzBand(r0, r1);
      FZ_ADD(fizzProf, FZ_CYC, fz1);
    }
    TU_MARK(TU_FIZZ);
    if (bubbleOn) {
      const int ya = (int)ffloor(by - bry), yb = (int)fceil(by + bry);
      for (int yy = ya > r0 ? ya : r0; yy <= yb && yy < r1; yy++) {
        float dy = (yy - by) / bry;
        if (fabsf(dy) > 1) continue;
        float hw = sqrtf(1 - dy * dy) * brx;
        int xa = (int)jround(bx - hw), xb = (int)jround(bx + hw);
        int ryi = yy < 0 ? 0 : yy > H - 1 ? H - 1 : yy;
        span(y0 + yy, xa, xb, pal.bubbleIn[ryi]);
        px(mapX(xa), y0 + yy, pal.bubbleRim); px(mapX(xb), y0 + yy, pal.bubbleRim);
      }
      int yt = (int)jround(by - bry), ybt = (int)jround(by + bry);   // the spans clip to the rows being drawn
      span(y0 + yt, (int)jround(bx - brx * 0.45f), (int)jround(bx + brx * 0.45f), pal.bubbleRim);
      span(y0 + ybt, (int)jround(bx - brx * 0.45f), (int)jround(bx + brx * 0.45f), pal.bubbleRim);
    }
    if (p.ticksOnTop) tickBand(y0, tickMark, r0, r1);
    if (topDigits && haveLabels && p.digitsOnTop) labelBand(y0, labels, digitWarp, digitMark, false, r0, r1);
    TU_MARK(TU_TOP);
  };

  // Everything up to the marks, row band by row band: each stage below writes and reads only its own row, so running
  // them over TUBE_BAND rows at a time (stage order kept within every row) gives the same pixels while the band's strip
  // rows stay in the data cache (one pass over the whole strip per stage missed every line each time, 2026-10-29).
  // The band's code is a lambda, in IRAM on the LCD (12.6 KB): from flash, all of it went through the instruction
  // cache again for every band (+1 fps, step 6). -DTUBE_BAND_INLINE keeps it inline in flash (gives the IRAM back).
  // The rows a band's SIMD ramps may blend whole 16-B blocks in (rampPieR / L): the strip, or the band's tile.
  const uint16_t *bandLo = FB, *bandHi = FB + H * PANEL_W;
#if TILE_RENDER
  // Tiled (tiles.h): each band renders into a tile slot (FB points so that its rows land there), then (step 9) every
  // mark stage on the band's rows, copied to the strip while the next band renders into the other slot. A slot's rows
  // start 16-B aligned like the strip's (TILE_ROWS 4, rows of 1,640 B), so the ramps and the digit runs take the same
  // SIMD / scalar path as on the strip. The pixel helpers clip to the band's rows (rowLo / rowHi).
  uint16_t *const stripFB = FB;
  int tileSlot = 0;
  // Change record of this strip (tiles.h TileDirty): every finished tile hashed against the tube's last render, unless
  // the CPU rewrites the strip after the tiles (stripLens: no record). Usable by the push when that last render hashed
  // the same rows (hashH).
  TileDirty *const rec = dirtyFor(stripFB);
  const bool hashOn = !stripLens;
  rec->valid = false;
  tile_begin(laneOf(), stripFB, H);
  TU_MARK(TU_TILE);
#define TILE_BAND_START(rb0) do { uint16_t *const t_ = tile_slot(laneOf(), tileSlot); const int e_ = (rb0) + TILE_ROWS < H ? (rb0) + TILE_ROWS : H; \
                                  FB = t_ - (rb0) * PANEL_W; bandLo = t_; bandHi = t_ + TILE_ROWS * PANEL_W; rowLo = baseY + (rb0); rowHi = baseY + e_; \
                                  TCLIP_SET(t_, t_ + (e_ - (rb0)) * PANEL_W); } while (0)
#define TILE_BAND_MARKS(rb0, rb1) marks(rb0, rb1, !stripLens)
#define TILE_BAND_END(rb0, rb1) do { tile_put(laneOf(), tileSlot, stripFB + (rb0) * PANEL_W, (rb1) - (rb0)); TU_MARK(TU_TILE); \
                                     if (hashOn) tileHashes((const uint32_t *)tile_slot(laneOf(), tileSlot), (rb1) - (rb0), \
                                                            tileHash + (rb0) / TILE_ROWS * TILE_PAIRS, rec->bits[(rb0) / TILE_ROWS]); \
                                     tileSlot ^= 1; TU_MARK(TU_HASH); } while (0)
#else
#define TILE_BAND_START(rb0) ((void)0)
#define TILE_BAND_MARKS(rb0, rb1) ((void)0)
#define TILE_BAND_END(rb0, rb1) ((void)0)
#endif
#ifndef TUBE_BAND_INLINE
  auto bandRows = [&](const int rb0, const int rb1) TUBE_IRAM {
#else
  for (int rb0 = 0; rb0 < H; rb0 += TUBE_BAND) {
  const int rb1 = rb0 + TUBE_BAND < H ? rb0 + TUBE_BAND : H;
  TILE_BAND_START(rb0);
#endif
  for (int ry = rb0; ry < rb1; ry++) hspan(y0 + ry, 0, L, pal.tubeBackRows[ry]);   // the tube back
  TU_MARK(TU_BACK);
  if (trRows) {
      const float hw = softW * 0.5f;
      const int N = trN, a0 = trA0, a1 = trA1, G = trG;
      for (int ry = rb0; ry < rb1; ry++) {
        const int y = y0 + ry;
        const float ex = edges[ry], exL = edgesL[ry], xm = (ex + exL) * 0.5f;
        // film path weight 1/(1 - u^2) of this row (sim kRow); the outermost rows graze the wall. K: the same
        // in 1/256, capped where any coat fills the row (sim)
        const float gr = 1 - rc.rowU2[ry], kRow = gr > 1e-6f ? 1.0f / gr : 1e6f;
        const uint32_t K = kRow >= 1024 ? 262144u : (uint32_t)(kRow * 256 + 0.5f);
        // the residue is the first layer over the tube back: B^(1-tau) C^tau from the two rows' logs
        int Br, Bg, Bb, Cr, Cg, Cb;
        expand565(pal.tubeBackRows[ry], Br, Bg, Bb); expand565(pal.rows[ry], Cr, Cg, Cb);
        ResidueTint tint;
        tint.lgB0 = FILM_LG[Br]; tint.lgB1 = FILM_LG[Bg]; tint.lgB2 = FILM_LG[Bb];
        tint.dl0 = FILM_LG[Cr] - tint.lgB0; tint.dl1 = FILM_LG[Cg] - tint.lgB1; tint.dl2 = FILM_LG[Cb] - tint.lgB2;
        tint.ex = FILM_EX; tint.phi = FILM_PHI; tint.K = K; tint.G = G; tint.kq = K * (1.0f / 65536); tint.full = pal.rows[ry];
        const int xr = (int)jround(ex), xrL = (int)jround(exL);   // hard edge: liquid where xrL <= x < xr
        // this row's Delta per edge, where the smear is sheared at all
        const float shR = shearR && fabsf(ex - xe) >= 0.125f ? ex - xe : 0.0f, shL = shearL && fabsf(exL - xs) >= 0.125f ? exL - xs : 0.0f;
        // Row split into segments so the per-pixel coverage/band math only runs near the edges (see
        // sim): [a0, pl1) plain residue . [pl1, zl0) home-edge sheared dry residue . [zl0, zl1) home-edge
        // zone . [zl1, zr0) fully covered, skipped . [zr0, zr1) time-edge zone . [zr1, pr0) time-edge sheared
        // dry residue . [pr0, a1) plain residue. A zone reaches the soft ramp, and the wet reach N while a film
        // is up; the sheared spans carry it on to Z (the sim runs them as zone: same pixels).
        int pl1 = a1, zl0 = a1, zl1 = a1, zr0 = a1, zr1 = a1, pr0 = a1;
        if (hasLiquid) {
          // at least half a pixel even for hard edges: the midpoint blend bt spans max(1, softW) px
          const float hz = fmx(0.5f, hw);
          float gl = fmx(hz, bandL ? (float)N : 0.0f), gr = fmx(hz, bandR ? (float)N : 0.0f);
          const float dl = fmx(gl, shL != 0 ? ZL : 0.0f), dr = fmx(gr, shR != 0 ? ZR : 0.0f);
          // The sheared dry spans equal the general zone only for ordered edges (exL <= ex: past each reach the
          // midpoint share is 0 / 1). A short convex slug compressed by slosh can cross them on a row: keep the
          // whole reach in the general zone there (no dry spans), as the sim does everywhere.
          if (exL > ex) { gl = dl; gr = dr; }
          auto clampx = [a0, a1](int v) { return v < a0 ? a0 : v > a1 ? a1 : v; };
          pl1 = clampx((int)ffloor(exL - dl - 0.5f) + 1);
          zl0 = clampx((int)ffloor(exL - gl - 0.5f) + 1);
          const int sk0 = clampx(softW > 0 ? (int)fceil(exL + hw - 0.5f) : xrL);       // first fully covered column
          const int sk1 = clampx(softW > 0 ? (int)ffloor(ex - hw - 0.5f) + 1 : xr);   // one past the last
          zr1 = clampx((int)fceil(ex + gr - 0.5f));
          pr0 = clampx((int)fceil(ex + dr - 0.5f));
          zl1 = sk0 < zr1 ? sk0 : zr1; zr0 = sk1 > zl1 ? sk1 : zl1;
        }
        // Plain residue is the hot loop of a smeared tube (up to L x H blends a frame): it writes the
        // strip row directly — y is inside the strip (drawTube's y0 is baseY), [a0, a1) inside [0, PANEL_W).
        static_assert(TUBE_LENGTH_PX <= PANEL_W, "trace columns index the strip row directly");
        uint16_t *const row = FB + ry * PANEL_W;
        // a row with no shear and no film up: the zone is only the soft ramp over plain residue
        const bool rowPlain = shL == 0 && shR == 0 && !bandL && !bandR;
        const ZoneRow zr{traceA, &tint, ex, exL, hw, invSoftW, xm, invBW, invN, shL, shR, invZL, invZR, etaL, etaR, kRow, visL, visR,
                         softW, xrL, xr, a0, a1, rowPlain, aHi, trZ, traceMemo->blkMax, zl0, zl1, zr0, zr1};
        // thin row (no coat of the span shows on it) and its films: residueRowMode
        const int mode = residueRowMode(zr);
        const bool thin = mode & 1;   // (a thin row's fill and sheared spans write nothing)
#ifdef TUBE_VERIFY
        memcpy(verifyRow, row, PANEL_W * 2);
#endif
        TU_SUB0(tuF);
        if (!thin) traceFillRow(row, traceA, a0, pl1, pr0, a1, tint, aLo, aHi, trZ, traceMemo->blkMax, traceLut);
        TU_SUB(TU_TRFILL, tuF); TU_SUB0(tuS);
        if (!thin && zl0 > pl1) traceShearRow(row, traceA, a0, a1, pl1, zl0, tint, exL, true, shL, invZL);
        if (!thin && pr0 > zr1) traceShearRow(row, traceA, a0, a1, zr1, pr0, tint, ex, false, shR, invZR);
        TU_SUB(TU_TRSHEAR, tuS); TU_SUB0(tuZ);
        {
          residueZones(row, zr, mode);   // not thin as a row: each segment may still be (the deposits lie elsewhere)
#ifdef TUBE_VERIFY
          { uint16_t *const keep = FB; FB = verifyRow - ry * PANEL_W;   // step 6's fill and shear calls, then the step-5 loop, on the copy (px writes FB)
            traceFillRow(verifyRow, traceA, a0, pl1, pr0, a1, tint, aLo, aHi, trZ, traceMemo->blkMax, traceLut);
            if (zl0 > pl1) traceShearRow(verifyRow, traceA, a0, a1, pl1, zl0, tint, exL, true, shL, invZL);
            if (pr0 > zr1) traceShearRow(verifyRow, traceA, a0, a1, zr1, pr0, tint, ex, false, shR, invZR);
        for (int seg = 0; seg < 2; seg++) {
          const int z0 = seg ? zr0 : zl0, z1 = seg ? zr1 : zl1;
          for (int x = z0; x < z1; x++) {
            // liquid coverage the body pass will paint: full inside, the soft-edge ramp across each edge
            // Both coverage ramps share a width: take the smaller numerator before scaling and
            // clamp once. Reciprocals above avoid software float division in this pixel loop.
            const float cr = ex + hw - x - 0.5f, cl = x + 0.5f - exL + hw;
            const float cov = softW > 0
              ? clampf((cr < cl ? cr : cl) * invSoftW, 0, 1)
              : (x >= xrL && x < xr ? 1.0f : 0.0f);
            if (cov >= 1) continue;
            if (rowPlain) {   // the general path below reduces to exactly this
              const int T = traceA[x] ? tint.depthT(traceA[x]) : 0;
              if (T > 0) px(x, y0 + ry, tint.at(T));
              continue;
            }
            // px outward of each contact line; bt = the time edge's share, 0 / 1 on each half, blended across
            // a softW-wide window at the midpoint (short slug, overlapping ramps: the warps join continuously)
            const float oL = exL - x - 0.5f, oR = x + 0.5f - ex, bt = clampf((x + 0.5f - xm) * invBW + 0.5f, 0, 1);
            // shift toward the edge centre and film weight 1/256; the film eases to 0 at N px out, thinning there
            // too (eta * wN: legs) with visibility wN * vis on top (see sim)
            float sh = 0, fw = 0;
            if (bt < 1) { const float k = 1 - bt, wN = ease(oL * invN); if (shL != 0) sh += k * shL * ease(oL * invZL); if (etaL > 0) fw += k * filmRowT(etaL * wN, kRow) * wN * visL; }
            if (bt > 0) { const float wN = ease(oR * invN); if (shR != 0) sh += bt * shR * ease(oR * invZR); if (etaR > 0) fw += bt * filmRowT(etaR * wN, kRow) * wN * visR; }
            // imminent residue sampled at the shifted column, linear between columns
            const float xf = x - sh;
            const int i0 = (int)ffloor(xf);
            const float ft = xf - i0;
            const float r0 = i0 >= a0 && i0 < a1 ? (float)traceA[i0] : 0.0f, r1 = i0 + 1 >= a0 && i0 + 1 < a1 ? (float)traceA[i0 + 1] : 0.0f;
            // the residue the line just laid and the wet film behind it are one coat, counted once: the deeper
            // of the two, never lighter than the residue beside it (see sim)
            const int T = (int)(fmx(r0 + r1 > 0 ? tint.depthF(r0 + (r1 - r0) * ft) : 0.0f, fw) + 0.5f);
            if (T > 0) px(x, y0 + ry, tint.at(T));
          }
        }
            FB = keep; int bad = 0; for (int x = 0; x < PANEL_W; x++) bad += verifyRow[x] != row[x];
            tubeVerify(TV_ZONE, a1 - a0, bad); }
#endif
        }
        TU_SUB(TU_TRZONE, tuZ);
      }
  }
  TU_MARK(TU_TRROWS);

  // Local backing per row and edge for the convex nose (3e): first pixel past the soft ramp, before the
  // body and glow paint it, plus the first pixel of the 3c wet film. See sim.
  if (hasLiquid) {
    const float hw = softW * 0.5f, yc = (H - 1) / 2.0f;
    const bool film3c = !traceMode && p.wetFilm > 0;
    for (int ry = rb0; ry < rb1; ry++) {
      const int y = y0 + ry; const float d = (ry - yc) / yc, rowW = 0.4f + 0.6f * d * d;
      const int xr = (int)ffloor(edges[ry] + hw - 0.5f) + 1, xl = (int)fceil(edgesL[ry] - hw - 0.5f) - 1;
      uint16_t bR = xr >= 0 && xr < L && inStrip(xr, y) ? rd(xr, y) : pal.tubeBackRows[ry];
      uint16_t bL = xl >= capX0[ry] && xl < L && inStrip(xl, y) ? rd(xl, y) : pal.tubeBackRows[ry];
      if (film3c && s.filmFree > 0.02f && jround(p.wetFilm * s.filmFree) > 0) bR = blend565(bR, pal.rows[ry], 0.35f * s.filmFree * rowW);
      if (film3c && p.freeLiquid && s.filmHome > 0.02f && jround(p.wetFilm * s.filmHome) > 0) bL = blend565(bL, pal.rows[ry], 0.35f * s.filmHome * rowW);
      backR[ry] = bR; backL[ry] = bL;
    }
  }
  TU_MARK(TU_BACKING);

  // Liquid body and its soft edge, over the residue backing.
  for (int ry = rb0; ry < rb1; ry++) {
    const float ex = edges[ry], exL = edgesL[ry];
    const int x0 = capX0[ry];
    if (!hasLiquid) continue;
    int xi = (int)ffloor(ex); float frac = ex - xi;
    int xiL = (int)ffloor(exL); float fracL = exL - xiL;
    int xa = x0 > xiL + 1 ? x0 : xiL + 1;
    // Preserve the underlay in partially covered pixels until the AA pass blends them.
    const int solidLo = traceMode && softW > 0 ? (int)fmx(xa, fceil(exL + softW * 0.5f - 0.5f)) : xa;
    const int solidHi = traceMode && softW > 0 ? (int)fmn(xi, ffloor(ex - softW * 0.5f - 0.5f) + 1) : xi;
    hspan(y0 + ry, solidLo, solidHi, pal.rows[ry]);
    if (p.edgeSoft > 0) {  // soft edge: a coverage ramp `w` px wide centred on the geometric edge.
      // The glow (if any) folds into the same per-pixel alpha min(1, cov + g), anchored to the
      // sub-pixel edge: no integer snapping, so no seam before the glow and no 1-px stepping
      // while the edge moves. alpha is monotone in x by construction (cov and g both decline).
      int w = (int)fmx(1, jround(p.edgeSoft)); float hw = w * 0.5f;
      bool glow = p.edgeGlow > 0 && p.glowStrength > 0;
      const float invW = 1.0f / w, invGlow = glow ? 1 / p.edgeGlow : 0;   // no FP divide unit: multiply in the pixel loops
      // A bead shorter than the two AA ramps composites once using their intersection.
      if (traceMode && ex - exL < w) {
        const float reach = hw + (glow ? p.edgeGlow : 0);
        const int first = (int)fmx(x0, ffloor(exL - reach)), end = (int)fmn(L, fceil(ex + reach));
        for (int x = first; x < end; x++) {
          const float gr = glow ? fmx(0, 1 - (x + 0.5f - ex) * invGlow) : 0;
          const float gl = glow ? fmx(0, 1 - (exL - x - 0.5f) * invGlow) : 0;
          const float ar = fmx(0, (ex + hw - x - 0.5f) * invW) + gr * gr * p.glowStrength * lightK;
          const float al = fmx(0, (x + 0.5f - exL + hw) * invW) + gl * gl * p.glowStrength * lightKL;
          const float a = fmn(1, fmn(ar, al));
          if (a > 0) pxa(x, y0 + ry, pal.rows[ry], a);
        }
        continue;
      }
      int a0 = (int)ffloor(ex - hw - 0.5f) + 1;
      int aEnd = glow ? (int)fceil(ex + hw - 0.5f + p.edgeGlow) : (int)fceil(ex + hw - 0.5f) - 1;
      uint16_t *const row = FB + ry * PANEL_W;
      TU_SUB0(tuR);
#ifdef TUBE_VERIFY
      memcpy(verifyRow, row, PANEL_W * 2);
      rampRowRScalar(verifyRow, a0, aEnd, ex, hw, invW, invGlow, glow, p.glowStrength, lightK, x0, solidLo, solidHi,
                     traceMode, pal.tubeBackRows[ry], pal.rows[ry]);
#endif
      rampRowR(row, a0, aEnd, ex, hw, invW, invGlow, glow, p.glowStrength, lightK, x0, solidLo, solidHi,
               traceMode, pal.tubeBackRows[ry], pal.rows[ry], bandLo, bandHi);
      int b0 = (int)ffloor(exL - hw - 0.5f) + 1;
      int bEnd = glow ? (int)ffloor(exL - hw - 0.5f - p.edgeGlow) : b0;  // home edge: glow to the left
#ifdef TUBE_VERIFY
      rampRowLScalar(verifyRow, (int)fceil(exL + hw - 0.5f) - 1, bEnd, exL, hw, invW, invGlow, glow, p.glowStrength, lightKL, x0, xi,
                     solidLo, solidHi, traceMode, pal.tubeBackRows[ry], pal.rows[ry]);
#endif
      rampRowL(row, (int)fceil(exL + hw - 0.5f) - 1, bEnd, exL, hw, invW, invGlow, glow, p.glowStrength, lightKL, x0, xi,
               solidLo, solidHi, traceMode, pal.tubeBackRows[ry], pal.rows[ry], bandLo, bandHi);
#ifdef TUBE_VERIFY
      { int bad = 0; for (int x = 0; x < PANEL_W; x++) bad += verifyRow[x] != row[x]; tubeVerify(TV_RAMP, 1, bad); }
#endif
      TU_SUB(TU_RAMP, tuR);
    } else {
      if (frac >= 0.5f) px(xi, y0 + ry, pal.rows[ry]);
      if (fracL < 0.5f && xiL >= x0) px(xiL, y0 + ry, pal.rows[ry]);
    }
  }

  TU_MARK(TU_BODY);
  // 3a: front brightening, weighted by row luma
  if (hasLiquid && p.frontBright > 0) {
    const float invFront = 1 / p.frontBright;
    const uint16_t hiC = rc.hiC;
    const uint16_t *fT = nullptr, *fTL = nullptr; const bool tab = false;
    for (int ry = rb0; ry < rb1; ry++) {
      int xi = (int)ffloor(edges[ry]); float rowK = pal.rowK[ry];
      int xiL = (int)ffloor(edgesL[ry]);
      for (int k = 1; k <= p.frontBright; k++) {
        int x = xi - k; if (x < 0) break;
        if (x >= L) continue;
        int T; if (tab) T = fT[ry * EFFECT_MAX + k - 1]; else { float t = 1 - k * invFront; T = alphaT(fmn(1, t * t * 0.85f * lightK * rowK)); }
        px(x, y0 + ry, blend565T(rd(x, y0 + ry), hiC, T));
      }
      if (!p.freeLiquid) continue;
      for (int k = 1; k <= p.frontBright; k++) {   // home edge: lit by the opposite tilt
        int x = xiL + k; if (x >= xi - p.frontBright) break;
        if (x < 0 || x >= L) continue;
        int T; if (tab) T = fTL[ry * EFFECT_MAX + k - 1]; else { float t = 1 - k * invFront; T = alphaT(fmn(1, t * t * 0.85f * lightKL * rowK)); }
        px(x, y0 + ry, blend565T(rd(x, y0 + ry), hiC, T));
      }
    }
  }

  TU_MARK(TU_FRONT);
  // 3b: edge glow — a few px past the edge. Hard-edge path only (edgeSoft = 0); with a soft
  // edge the glow is folded into the step-3 per-pixel alpha.
  if (hasLiquid && p.edgeSoft <= 0 && p.edgeGlow > 0 && p.glowStrength > 0) {
    const float invGlow = 1 / p.edgeGlow;
    const uint16_t *gT = traceMode ? nullptr : effectTable(glowT[0], p, pal, gen, lightK, true);
    const uint16_t *gTL = !traceMode && p.freeLiquid ? effectTable(glowT[1], p, pal, gen, lightKL, true) : nullptr;
    const bool tab = gT && (!p.freeLiquid || gTL);
    for (int ry = rb0; ry < rb1; ry++) {
      // glow starts at the first px past the RENDERED hard edge (round(ex)), never leaving a
      // 1-px tube-back gap that flickers as frac crosses 0.5
      int xg = (int)jround(edges[ry]), xgL = (int)jround(edgesL[ry]) - 1;
      for (int k = 0; k < p.edgeGlow; k++) {
        int xr = xg + k, xl = xgL - k;
        if (xr < L) {
          if (traceMode) { float t = 1 - k * invGlow; pxa(xr, y0 + ry, pal.rows[ry], fmn(1, t * t * p.glowStrength * lightK)); }
          else {
            uint16_t c; if (tab) c = gT[ry * EFFECT_MAX + k]; else { float t = 1 - k * invGlow; c = blend565(pal.tubeBackRows[ry], pal.rows[ry], fmn(1, t * t * p.glowStrength * lightK)); }
            px(xr, y0 + ry, c);
          }
        }
        if (p.freeLiquid && xl >= capX0[ry]) {
          if (traceMode) { float t = 1 - k * invGlow; pxa(xl, y0 + ry, pal.rows[ry], fmn(1, t * t * p.glowStrength * lightKL)); }
          else {
            uint16_t c; if (tab) c = gTL[ry * EFFECT_MAX + k]; else { float t = 1 - k * invGlow; c = blend565(pal.tubeBackRows[ry], pal.rows[ry], fmn(1, t * t * p.glowStrength * lightKL)); }
            px(xl, y0 + ry, c);
          }
        }
      }
    }
  }

  TU_MARK(TU_GLOW);
  // 3c: wet film left by a receding edge (see sim step 3c). In trace mode the film is the wet band
  // of 3d instead (full liquid at the edge, thinning into the residue), so this faint one is skipped.
  if (!traceMode && hasLiquid && p.wetFilm > 0 && (s.filmFree > 0.02f || (p.freeLiquid && s.filmHome > 0.02f))) {
    const float yc = (H - 1) / 2.0f;
    for (int ry = rb0; ry < rb1; ry++) {
      float d = (ry - yc) / yc, rowW = 0.4f + 0.6f * d * d;
      int nR = (int)jround(p.wetFilm * s.filmFree), nL = p.freeLiquid ? (int)jround(p.wetFilm * s.filmHome) : 0;
      int xg = softW > 0 ? (int)fceil(edges[ry] + softW * 0.5f - 0.5f) : (int)fceil(edges[ry]);
      int xgL = softW > 0 ? (int)ffloor(edgesL[ry] - softW * 0.5f - 0.5f) : (int)ffloor(edgesL[ry]);
      for (int k = 0; k < nR; k++) if (xg + k < L) pxa(xg + k, y0 + ry, pal.rows[ry], 0.35f * s.filmFree * rowW * (1 - (float)k / nR));
      for (int k = 0; k < nL; k++) if (xgL - k >= capX0[ry]) pxa(xgL - k, y0 + ry, pal.rows[ry], 0.35f * s.filmHome * rowW * (1 - (float)k / nL));
    }
  }

  TU_MARK(TU_FILM);
  // 4: highlight inset
  if (hasLiquid && p.highlightInset > 0) {
    int hiTop = highlightTop(p, s.light);
    for (int ry = hiTop > rb0 ? hiTop : rb0; ry < hiTop + p.highlightH && ry < rb1; ry++) {
      if (ry < 0) continue;
      float ex = edges[ry];
      int bi = hiTop + (int)p.highlightH + 1; if (bi > H - 1) bi = H - 1;
      uint16_t bodyRow = pal.rows[bi];
      int xl = (int)fmx(0, ffloor(edgesL[ry]));   // home edge (0 unless the liquid is free)
      for (int x = (int)ffloor(ex - p.highlightInset); x < (int)ffloor(ex); x++) {
        if (x < xl) continue;   // never outside the column
        float t = (x - (ex - p.highlightInset)) / p.highlightInset;
        px(x, y0 + ry, blend565(pal.rows[ry], bodyRow, t));
      }
      for (int x = xl; x < xl + p.highlightInset && x < ex; x++) {
        float t = 1 - (float)(x - xl) / p.highlightInset;
        px(x, y0 + ry, blend565(pal.rows[ry], bodyRow, t));
      }
    }
  }

  TU_MARK(TU_INSET);
  // 3e: meniscus surface, over residue and the inset highlight. Concave bands grade from
  // a dark inner shoulder to a lit rim with subpixel coverage; convex noses shade inward.
  // Alpha-over blends the stroke over the actual smear. Both branches fade as the ring
  // meets the profile. See sim step 3e. No extra buffers or allocations. Its per-frame terms and the marks' facts
  // per row (strokes, layer weights) come from before the band loop (step 9; concave() there and here).
  if (band3e) {
    const float hw = softW * 0.5f, transK = clampf(p.liquidTransparency, 0, 1);
    const uint16_t hiC = rc.hiC;
    auto tone = [&](uint16_t c) -> uint16_t { return rc.toneT > 0 ? blend565T(c, rc.toneC, rc.toneT) : c; };
    auto surface = [&](int ry, float xm, float xw, int dir, float lk, int xlo, int xhi) TUBE_IRAM {
      const int y = y0 + ry; const float tw = dir * (xw - xm);   // ring lead in the edge's own outward sense
      if (tw == 0) return;
      const float lo = fmn(xm, xw), hi = fmx(xm, xw);   // pixel centres in [lo, hi)
      int x0 = (int)fceil(lo - 0.5f), x1 = (int)fceil(hi - 0.5f); if (x0 < xlo) x0 = xlo; if (x1 > xhi) x1 = xhi;
      if (tw > 0) {   // concave: shaded surfaceWidth-px band, clipped to the wall ring
        // Overlap the body's AA ramp so it joins the shoulder without a bare-glass seam.
        float a, wEff, blickK, rimK;
        if (!concave(ry, tw, dir, lk, a, wEff, blickK, rimK)) return;   // below visible opacity
        const float shade = 0.6f * (1 - fmn(1, lk));   // unlit edge: toward the deep liquid colour
        const PalCache &pc = *palCache;   // per-row colours (buildBandRows)
        const uint16_t inner = pc.bandInner[ry];
        const uint16_t outer = tone(blend565(pc.bandLensMix[ry], rc.darkC, shade));
        const float invWidth = 1 / (wEff + hw);
        const float pull = dir > 0 ? pullR : pullL;
        // Float mixes once per row, like the sim's blend565.
        const uint16_t rimC = pc.bandRimC[ry];
#ifdef TUBE_VERIFY
        {
          const float backK = pc.bandBackK[ry];
          const float backK0 = fmn(1, luma(to888(pal.tubeBackRows[ry])) / 255.0f);
          const uint16_t inner0 = tone(blend565(pal.rows[ry], rc.darkC, 0.3f));
          const uint16_t outer0 = tone(blend565(blend565(rc.lensC, pal.rows[ry], 0.2f), rc.darkC, shade));
          const uint16_t rimC0 = q(mix(to888(hiC), to888(q(mix(to888(pal.rows[ry]), to888(rc.darkC), 0.75f))), backK0));
          tubeVerify(TV_BAND, 4, (inner0 != inner) + (outer0 != outer) + (rimC0 != rimC) + (memcmp(&backK0, &backK, 4) != 0));
        }
#endif
        // Pixel-footprint coverage for the stroke and rim; no integer-column snapping. See sim.
        const float cLo = dir > 0 ? xm - hw : xm - wEff, cHi = dir > 0 ? xm + wEff : xm + hw;
        int xa = (int)ffloor(cLo), xb = (int)fceil(cHi); if (xa < xlo) xa = xlo; if (xb > xhi) xb = xhi;
        TU_SUB0(tuB);
        TCLIP(FB + ry * PANEL_W, PANEL_W);
        bandRow(FB + ry * PANEL_W, xa, xb, xm, dir, hw, wEff, invWidth, a, fill, blickK, pull, rimK, inner, outer, pal.rows[ry], hiC, rimC);
        TU_SUB(TU_BANDK, tuB);
      } else {   // convex: thin nose inside the profile back to the ring
        // The thin nose shows the local backing sampled before body and glow (bare back, or a receding
        // edge's liquid-coloured film / residue: no pale crescent). Motion never fades it. See sim.
        const float noseK = p.surfaceBand;
        const uint16_t back = dir > 0 ? backR[ry] : backL[ry];
        const uint16_t c = tone(blend565(blend565(pal.rows[ry], back, 0.55f), hiC, 0.5f * transK));
        const float invTw = 1 / tw;
        for (int x = x0; x < x1; x++) {
          float t = dir * (x + 0.5f - xm); if (t > -hw) continue;
          float a = noseK * fmn(1, -tw) * (1 - sqrtf(fmx(0, t * invTw)));   // t/tw: 1 at the ring, 0 at the tip
          if (a >= 1 / 255.0f) pxa(x, y, c, fmn(1, a));
        }
      }
    };
    for (int ry = rb0; ry < rb1; ry++) {
      int xi = (int)ffloor(edges[ry]), xa = (int)ffloor(edgesL[ry]) + 1; if (xa < capX0[ry]) xa = capX0[ry];
      surface(ry, edges[ry], wallX(ry, xe, tanR, capR), 1, lightK, xa, L);
      if (p.freeLiquid) surface(ry, edgesL[ry], wallXL(ry, xs, tanL, capL), -1, lightKL, capX0[ry], xi);
    }
  }

  TU_MARK(TU_BAND);
  // remaining: the base rendered mirrored, flipped here (the mark bounds came mirrored from before the loop)
  if (mir) for (int ry = rb0; ry < rb1; ry++) {
    uint16_t *row = FB + ry * PANEL_W;
    TCLIP(row, PANEL_W);
    for (int a = 0, b = L - 1; a < b; a++, b--) { uint16_t t = row[a]; row[a] = row[b]; row[b] = t; }
  }
  TU_MARK(TU_BOUNDS);
#ifndef TUBE_BAND_INLINE
  };
  for (int rb0 = 0; rb0 < H; rb0 += TUBE_BAND) {
    const int rb1 = rb0 + TUBE_BAND < H ? rb0 + TUBE_BAND : H;
    TILE_BAND_START(rb0);
    bandRows(rb0, rb1);
    TILE_BAND_MARKS(rb0, rb1);
    TILE_BAND_END(rb0, rb1);
  }
#else
  TILE_BAND_MARKS(rb0, rb1);
  TILE_BAND_END(rb0, rb1);
  }   // row bands
#endif
#undef TILE_BAND_START
#undef TILE_BAND_MARKS
#undef TILE_BAND_END
#if TILE_RENDER
  FB = stripFB; bandLo = FB; bandHi = FB + H * PANEL_W; rowLo = baseY; rowHi = baseY + H;
  TCLIP_SET(stripFB, stripFB + (size_t)H * PANEL_W);
  tile_end(laneOf());   // nothing touched the strip since tile_begin: every mark ran in the tiles
  TU_MARK(TU_TILE);
  if (stripLens) {   // reads other rows: on the strip, then the digits printed over it (the push writes the lines back)
    applyLens(p);
    if (haveLabels && p.digitsOnTop) labelBand(y0, labels, digitWarp, digitMark, false, 0, H);
    TU_MARK(TU_TOP);
  }
  {
    const int e = cleanStrip[0] == stripFB ? 0 : cleanStrip[1] == stripFB ? 1 : cleanStrip[0] == nullptr ? 0 : 1;
    cleanStrip[e] = stripLens ? nullptr : stripFB;
  }
  rec->tube = (int8_t)idx; rec->seq = renderSeq; rec->rows = (int16_t)H;
  rec->valid = hashOn && hashH == H;   // the table held the tube's last render (renderSeq - 1), the same rows
  hashH = hashOn ? H : -1;
#if defined(TILE_VERIFY) && !defined(TUBE_BAND_INLINE)
  {   // the whole render again straight into a PSRAM copy of the strip (the step-6 path: bands, then every mark over the
      // whole tube, the lens, the top digits), compared with what the tiles left
    FB = tileVerifyStrip; bandLo = FB; bandHi = FB + H * PANEL_W;
    TCLIP_SET(tileVerifyStrip, tileVerifyStrip + (size_t)H * PANEL_W);
    for (int rb0 = 0; rb0 < H; rb0 += TUBE_BAND) bandRows(rb0, rb0 + TUBE_BAND < H ? rb0 + TUBE_BAND : H);
    marks(0, H, false);
    if (stripLens) applyLens(p);
    if (haveLabels && p.digitsOnTop) labelBand(y0, labels, digitWarp, digitMark, false, 0, H);
    uint32_t bad = 0;
    for (int i = 0; i < H * PANEL_W; i++) bad += tileVerifyStrip[i] != stripFB[i];
    tileVerify((uint32_t)H * PANEL_W, bad);
    FB = stripFB; bandLo = FB; bandHi = FB + H * PANEL_W;
    TCLIP_SET(stripFB, stripFB + (size_t)H * PANEL_W);
    TU_MARK(TU_TILE);
  }
#endif
#else
  marks(0, H, false);   // the strip path: every mark stage over the whole tube
  if (stripLens) applyLens(p);
  if (haveLabels && p.digitsOnTop) labelBand(y0, labels, digitWarp, digitMark, false, 0, H);
  TU_MARK(TU_TOP);
#endif
  if (lensOut) *lensRowsOut = rc.lensOn ? rc.lensSrc : nullptr;   // the push applies it
}

// A class's mask geometry for a radius r (dyl |dy| rows of xw |dx| steps, plus a byte a row): its bytes.
static inline int fizzMaskGeom(float r, int &xw, int &dyl) {
  const float rOut = r + 0.5f; xw = (int)(rOut * FIZZ_MQ) + 2; dyl = (int)(rOut * FIZZ_MDY) + 2;
  return dyl * (xw + 1);
}
static std::atomic<int> fizzMaskPeak{0};   // bytes a size push asked for past the pool (0: none; INT_MAX: radii no mask can hold), reported by main
int fizzMaskOverflow() { return fizzMaskPeak.load(std::memory_order_relaxed); }
static void buildFizzClasses(FizzLook &fl, const Params &p) {
  int need = 0; bool sane = true;   // every class a real disc (fizzSizeVar past 2 would make the small ones negative)
  fl.masks = false;
  for (int k = 0; k < FIZZ_SIZES; k++) {
    FizzClass &c = fl.k[k];
    const float r = fizzR(p, 0.5f + (k + 0.5f) * (1.0f / FIZZ_SIZES)), rIn = r - 0.5f, rOut = r + 0.5f, kc = r - 1;   // fizzV's values
    c.r = r; c.kc = kc;
    c.in2 = rIn >= 1 ? rIn * rIn * (1 - 1e-4f) : -1; c.out2 = rOut * rOut * (1 + 1e-4f);
    c.core = r >= 1.5f && kc > 0; c.core2Lo = kc * kc * (1 - 1e-4f); c.core2Hi = kc * kc * (1 + 1e-4f);
    c.off = fmn(r * p.fizzShadeOff, r - 1);   // core shift, centre kept in the disc (sim)
    c.blick = r >= 2.5f && p.fizzBlick > 0;
    const float rb = fmx(0.6f, r * 0.25f), rbIn = rb - 0.5f;
    c.bk = 0.4f * (r - 1); c.rbOut = rb + 0.5f; c.bIn2 = rbIn * rbIn * (1 - 1e-4f); c.bOut2 = c.rbOut * c.rbOut * (1 + 1e-4f);
    // A mask holds 0 < r < 62 (a row's widest |dx| step is a byte); past that (sizes pushed beyond the sliders) no
    // size arithmetic is done and every bubble draws analytically.
    const bool ok = r > 0 && r < 62;
    sane = sane && ok;
    c.maskOff = need;
    if (ok) need += fizzMaskGeom(r, c.xw, c.dyl); else c.xw = c.dyl = 0;
  }
  fl.need = need; fl.sane = sane;
  fl.key[0] = p.fizzSize; fl.key[1] = p.fizzSizeVar; fl.key[2] = p.fizzShadeOff; fl.key[3] = p.fizzBlick; fl.valid = true;
}
// The masks both tubes share: the first tube to find them stale for its size params (re)builds them (planFizz); a tube
// takes them only while they match its params, and one that finds the other building draws analytically that frame
// (the two cores render at once; both tubes have the same params, so neither is drawing from them then).
// ready: release / acquire, so a tube that sees them ready for its params sees every byte of them.
#ifndef MALLOC_CAP_INTERNAL   // host builds
#define MALLOC_CAP_INTERNAL 0
#define MALLOC_CAP_8BIT 0
#endif
#ifdef BOARD_LCD316
#define FIZZ_MASK_INTL 8192   // internal RAM: user-fav needs 8123 B, the median preset ~2 KB
#else
#define FIZZ_MASK_INTL 0      // the AMOLED keeps its internal RAM
#endif
static struct {
  std::atomic<bool> ready{false}, building{false};
  float key[2] = {0, 0};                      // fizzSize, fizzSizeVar they are built for
  uint8_t *intl = nullptr, *ps = nullptr;     // the internal pool (FIZZ_MASK_INTL), the PSRAM one (fizzMaskWorst), render_init
  int psCap = 0;
  const uint8_t *pool = nullptr;              // the pool they are in
} fizzMasks;
static void writeFizzMasks(const FizzLook &fl, uint8_t *pool) {
  for (int k = 0; k < FIZZ_SIZES; k++) {
      const FizzClass &c = fl.k[k];
      uint8_t *const m = pool + c.maskOff, *const wide = m + c.dyl * c.xw;
      for (int dq = 0; dq < c.dyl; dq++) {
        const float dy = dq * (1.0f / FIZZ_MDY); int xm = 255;
        for (int i = 0; i < c.xw; i++) {
          const float dx = i * (1.0f / FIZZ_MQ), d2 = dx * dx + dy * dy;
          const float cov = d2 >= c.out2 ? 0 : d2 <= c.in2 ? 1 : clampf(c.r + 0.5f - sqrtExact(d2), 0, 1);
          const int t8 = (int)(cov * 255 + 0.5f);
          m[dq * c.xw + i] = (uint8_t)t8;
          if (t8) xm = i;
        }
        wide[dq] = (uint8_t)xm;
      }
  }
}
// This frame's masks for a tube (planFizz, before its bubbles are planned).
static void takeFizzMasks(FizzLook &fl, const Params &p) {
  const bool intl = fl.need <= FIZZ_MASK_INTL && fizzMasks.intl, fits = fl.sane && (intl || fl.need <= fizzMasks.psCap);
  if (!fits) { atomicMax(fizzMaskPeak, fl.sane ? fl.need : INT_MAX); fl.masks = false; return; }
  auto match = [&]() { return fizzMasks.ready.load(std::memory_order_acquire) && fizzMasks.key[0] == p.fizzSize && fizzMasks.key[1] == p.fizzSizeVar; };
  bool idle = false;
  if (!match() && fizzMasks.building.compare_exchange_strong(idle, true, std::memory_order_acquire)) {
    if (!match()) {   // still stale (the other tube may have built them meanwhile)
      fizzMasks.ready.store(false, std::memory_order_release);
      uint8_t *const pool = intl ? fizzMasks.intl : fizzMasks.ps;
      writeFizzMasks(fl, pool);
      fizzMasks.pool = pool; fizzMasks.key[0] = p.fizzSize; fizzMasks.key[1] = p.fizzSizeVar;
      fizzMasks.ready.store(true, std::memory_order_release);
    }
    fizzMasks.building.store(false, std::memory_order_release);
  }
  fl.masks = match(); fl.mask = fl.masks ? fizzMasks.pool : nullptr;
}
// The live loop renders both tubes at once: it prepares the masks here first, on one core (main renderBoth), so no
// tube builds them while the other draws; sequential callers (host checks, `X`) may skip it (planFizz builds them).
void render_fizz_prepare(const Params &p) {
  if (!p.fizz) return;
  FizzLook &fl = *tubes[0].look;
  if (!fl.valid || fl.key[0] != p.fizzSize || fl.key[1] != p.fizzSizeVar || fl.key[2] != p.fizzShadeOff || fl.key[3] != p.fizzBlick) buildFizzClasses(fl, p);
  takeFizzMasks(fl, p);
}
// The mask pool's bytes for the sliders' largest bubbles (fizzSize 16 design px, fizzSizeVar 0..1): per class the
// bigger of its sizes at spread 0 and 1 (a class's radius is linear in the spread and its mask grows with the radius),
// so no slider setting needs more (render_init). +0.5 px: the board's px scaling may round.
static int fizzMaskWorst() {
  const float size = 16 * PX_SCALE_MAX + 0.5f; int worst = 0;
  for (int k = 0; k < FIZZ_SIZES; k++) {
    int xw, dl, most = 0;
    for (int e = 0; e <= 1; e++) { const int b = fizzMaskGeom(size / 2 * (1 + (0.5f + (k + 0.5f) * (1.0f / FIZZ_SIZES) - 1) * e), xw, dl); if (b > most) most = b; }
    worst += most;
  }
  return worst;
}
// Step 5, one bubble (drawTube): its disc setup (planBubble, once a frame), then its rows (bubbleRows, discRow; step 9:
// band by band). Out of drawTube (noinline, in IRAM on the LCD): inside it the setup spilled and its code competed for
// the instruction cache with the other core's render.
FIZZ_IRAM void __attribute__((noinline)) Tube::planBubble(const Fizz &f, const Params &p, const FizzFrame &ff, BubblePlan &b) {
  const float *mag = ff.mag; const float yHi = ff.yHi, invHalfH = ff.invHalfH, lxSign = ff.lxSign;
  const float lxS = -0.7f;   // light from screen-left (a constant, as it was in drawTube: lxS * lxS folds)
  const FizzLook &fl = *look;
  FZ_T0(fb0);
  int fy = (int)clampf(jround(f.y), 0, H - 1);
  // Centres stay inside this frame's surfaces (the stepper ran on an older one, so a receding surface pushes
  // them back here): whatever touches a surface floats at most half out of it, like the foam.
  const float fx = fmx(-foamFront(fizzSurfL, H, f.y, -1), fmn(foamFront(fizzSurf, H, f.y, 1), f.x));
  // A parked bubble in its last FOAM_POP_T s pops: swells and fades out, breaking the surface (no size class then).
  const float pop = f.life != 0 && fabsf(f.life) < FOAM_POP_T ? fabsf(f.life) / FOAM_POP_T : 1;
  const int cls = fizzClass(f.v), lvl = fizzLevel(f.z);
  const FizzClass &c = fl.k[cls];
  const float r = pop < 1 ? fizzR(p, f.v) * (1 + 0.6f * (1 - pop)) : c.r;
  const float m = fizzMag(mag, H, f.y, r), ry = r / m, off = pop < 1 ? fmn(r * p.fizzShadeOff, r - 1) : c.off;   // core shift, centre kept in the disc (sim)
  // Light direction in unsquashed disc space (liquid frame): x fixed toward screen-left, y toward the highlight row.
  const float ly = clampf((yHi - f.y) * invHalfH, -1, 1), nrm = rsqrtApprox(lxS * lxS + ly * ly);   // sim: exact 1/sqrt; <= 2.1e-7 rel.
  const float dirX = lxSign * lxS * nrm, dirY = ly * nrm;
  b.fx = fx; b.r = r; b.offX = -dirX * off; b.offY = -dirY * off;   // dark core shifted away from the light
  // Specular pinpoint on the lit side (r >= 2.5, fizzBlick > 0), depth-tinted (sim cBlickD).
  b.blick = pop < 1 ? r >= 2.5f && p.fizzBlick > 0 : c.blick;
  if (b.blick) { const float bk = pop < 1 ? 0.4f * (r - 1) : c.bk; b.bX = dirX * bk; b.bY = dirY * bk; b.cBlick = fl.cBlick[lvl][fy]; }
  else { b.bX = b.bY = 0; b.cBlick = 0; }
  b.tintA = fl.tintA[lvl];   // sim tintA
  b.cls = (int8_t)(pop < 1 ? -1 : cls); b.lvl = (uint8_t)lvl;
  if (b.cls >= 0 && fl.masks) {   // by its mask: x rounded to the mask's steps
    const int qt = (int)ffloor(fx * FIZZ_MQ + 0.5f);
    b.qt = (int16_t)qt; b.fx = qt * (1.0f / FIZZ_MQ);
  } else b.qt = 0;
  b.ixa = (int16_t)(int)ffloor(b.fx - r - 1); b.ixb = (int16_t)(int)fceil(b.fx + r);
  b.iyA = (int16_t)(int)ffloor(f.y - ry - 1); b.iyB = (int16_t)(int)fceil(f.y + ry);
  b.y = f.y; b.m = m; b.pop = pop;
#ifdef FIZZ_PROF
  fizzProf[FZ_BUBBLES]++; FZ_ADD(fizzProf, FZ_CYC_SETUP, fb0);
#endif
}
// A planned bubble's rows in [r0, r1): its DiscRow on the stack, the disc set-up derived from the plan as planBubble
// derived it before (the same expressions, so the same values), then each row's fields.
// A planned bubble's disc set-up, every DiscRow field but the per-row ones: the size class's, or (popping) derived from
// its own radius as planBubble derived it before (the same expressions, so the same values).
void Tube::discOf(const BubblePlan &b, DiscRow &d) const {
  d.fx = b.fx; d.offX = b.offX; d.offY = b.offY;
  d.blick = b.blick;
  if (b.cls >= 0) {
    const FizzClass &c = look->k[b.cls];
    d.r = c.r; d.kc = c.kc; d.in2 = c.in2; d.out2 = c.out2; d.core = c.core; d.core2Lo = c.core2Lo; d.core2Hi = c.core2Hi;
    d.rbOut = c.rbOut; d.bIn2 = c.bIn2; d.bOut2 = c.bOut2;
  } else {
    const float r = b.r, rIn = r - 0.5f, rOut = r + 0.5f, kc = r - 1;   // ring 1 px at its thinnest; the offset only shifts the core
    const float rb = fmx(0.6f, r * 0.25f), rbIn = rb - 0.5f;
    d.r = r; d.kc = kc;
    d.in2 = rIn >= 1 ? rIn * rIn * (1 - 1e-4f) : -1; d.out2 = rOut * rOut * (1 + 1e-4f);
    d.core = r >= 1.5f && kc > 0; d.core2Lo = kc * kc * (1 - 1e-4f); d.core2Hi = kc * kc * (1 + 1e-4f);
    d.rbOut = rb + 0.5f; d.bIn2 = rbIn * rbIn * (1 - 1e-4f); d.bOut2 = d.rbOut * d.rbOut * (1 + 1e-4f);
  }
  if (b.blick) { d.blickK = fzBlickK; d.bX = b.bX; d.bY = b.bY; } else { d.blickK = d.bX = d.bY = d.rbOut = d.bIn2 = d.bOut2 = 0; }
  d.cBlick = b.cBlick;
  d.veilA = fzVeilA; d.pullR = fzPullR; d.pullL = fzPullL;
  d.mirror = fzMir; d.xsI = fzXsI; d.L = fzL; d.tintA = b.tintA;
#ifdef FIZZ_PROF
  d.prof = const_cast<uint32_t *>(fizzProf);
#endif
}
// One row of a planned bubble, analytic (discRowT): its DiscRow d with this row's fields filled in.
inline void Tube::discRowOf(const BubblePlan &b, DiscRow &d, int iy, float wallT, float dy) {
  d.wallT = wallT; d.dy = dy;
  // Past the profile a bubble is seen through the concave band's front-glass wedge, thickest at the
  // profile and gone at the band's outer rim.
  d.sR = fizzSurf[iy]; d.sL = fizzSurfL[iy]; d.bR = strokeR[iy]; d.bL = strokeL[iy];   // stroke widths: 0 where no band is drawn
  d.veilLo = look->veilLo[iy]; d.veilHi = look->veilHi[iy];
  d.cRim = look->cRim[b.lvl][iy];
  TCLIP(FB + iy * PANEL_W, PANEL_W);
  discRow(FB + iy * PANEL_W, b.ixa, b.ixb, d);
}
// A planned bubble's rows in [r0, r1). A size class's (masks built) by its mask: the coverage by index, the core and the
// pinpoint by their chords on each row, analytic (discRowT) on a row a surface band veils; a popping one analytic.
FIZZ_IRAM void __attribute__((noinline)) Tube::bubbleRows(const BubblePlan &b, int r0, int r1) {
  FZ_T0(fp0);
  const int iy0 = b.iyA > r0 ? b.iyA : r0, iy1 = b.iyB < r1 - 1 ? b.iyB : r1 - 1;
  DiscRow d;
  if (b.cls >= 0 && look->masks) { maskRows(b, iy0, iy1); return; }
  {
    discOf(b, d);
    FZ_ADD(fizzProf, FZ_CYC_SETUP, fp0);
    for (int iy = iy0; iy <= iy1; iy++) {
      if (iy < 0 || iy >= H) continue;
      const float wallT = pal.dryT[iy] / 256.0f * b.pop;   // bubbles live in the bore: invisible where the ray only sees the wall band
      if (wallT <= 0) continue;
      const float dy = (iy + 0.5f - b.y) * b.m;
      if (dy * dy >= d.out2) continue;     // the disc misses this row (discRowT would return at once)
      FZ_T0(fr1);
      discRowOf(b, d, iy, wallT, dy);
      FZ_ADD(fizzProf, FZ_CYC_DISC, fr1);
#ifdef FIZZ_PROF
      fizzProf[FZ_ROWS]++;
#endif
    }
  }
}
static inline int ifloor(float x) { const int i = (int)x; return i - (x < i); }   // floor for |x| < 2^31
static inline int iceil(float x) { const int i = (int)x; return i + (x > i); }
// A size-class bubble's rows [iy0, iy1] by its mask (masks built): the coverage by index, the core and the pinpoint
// by their chords on each row; a row a surface band veils analytic (discRowT). Out of bubbleRows so that its few live
// values stay in registers.
FIZZ_IRAM void __attribute__((noinline)) Tube::maskRows(const BubblePlan &b, int iy0, int iy1) {
  FZ_T0(fp0);
  const FizzClass &c = look->k[b.cls];
  const uint8_t *const mk = look->mask + c.maskOff, *const wide = mk + c.dyl * c.xw;
  const int xw = c.dyl > 0 ? c.xw : 0, dyl = c.dyl, qt = b.qt;   // the bubble's x = qt / FIZZ_MQ (planBubble)
  MaskRowK k; k.base = FIZZ_MQ / 2 - qt;
  k.tint256 = (int)(b.tintA * 256 + 0.5f); k.x0 = fzMir ? fzL - 1 - fzXsI : fzXsI; k.step = fzMir ? -1 : 1;
  const int pLo = fzMir ? k.x0 - (PANEL_W - 1) : -k.x0, pHi = fzMir ? k.x0 : PANEL_W - 1 - k.x0;   // the tube columns on the panel
  const uint16_t *const cRim = look->cRim[b.lvl];
  const int16_t *const vLo = look->veilLo, *const vHi = look->veilHi;
  const float cxc = b.fx + b.offX - 0.5f, kc2 = c.kc * c.kc, m = b.m, offY = b.offY;   // the core's centre column, its radius squared
  const bool core = c.core, blick = b.blick;
  if (iy0 < 0) iy0 = 0; if (iy1 > H - 1) iy1 = H - 1;
  FZ_ADD(fizzProf, FZ_CYC_SETUP, fp0);
  for (int iy = iy0; iy <= iy1; iy++) {
    FZ_T0(fr0);
    const float dy = (iy + 0.5f - b.y) * m;   // per row, not stepped: the tiled bands start anywhere
    const int W = pal.dryT[iy];   // the wall's transmission x 256 (bubbles live in the bore)
    if (W <= 0) continue;
    const int dq = (int)(fabsf(dy) * FIZZ_MDY + 0.5f);
    if (dq >= dyl) continue;
    const int xm = wide[dq];
    if (xm == 255) continue;   // nothing covered on this row
    // the columns with |FIZZ_MQ ix + base| <= xm
    int a = (qt - FIZZ_MQ / 2 - xm + FIZZ_MQ - 1) >> 2, e = (qt - FIZZ_MQ / 2 + xm) >> 2;
    static_assert(FIZZ_MQ == 4, "the shifts divide by FIZZ_MQ");
    if (a < pLo) a = pLo; if (e > pHi) e = pHi;
    if (a > e) continue;   // nothing covered (or off the panel)
#ifdef FIZZ_PROF
    fizzProf[FZ_ROWS]++;
#endif
    uint16_t *const row = FB + iy * PANEL_W;
    TCLIP(row, PANEL_W);
    k.m = mk + dq * xw; k.W256 = W; k.rim = rimLanes(cRim[iy]);
    k.c0 = 1; k.c1 = 0;
    if (core) { const float cy = dy - offY, rem = kc2 - cy * cy; if (rem > 0) { const float hw = sqrtApprox(rem); k.c0 = ifloor(cxc - hw) + 1; k.c1 = iceil(cxc + hw) - 1; } }
    // Unveiled columns [lo, hi] (a surface band veils ix >= veilLo and ix < veilHi), the pinpoint's reach [p0, p1]
    // within them: maskRow; everything else maskPx.
    const int veilLo = vLo[iy], veilHi = vHi[iy];
    const int lo = a > veilHi ? a : veilHi, hi = e < veilLo - 1 ? e : veilLo - 1;
    int p0 = 1, p1 = 0; float bdy2 = 0, bRem = 0;
    if (blick) {
      const float bdy = dy - b.bY; bdy2 = bdy * bdy; bRem = c.bOut2 - bdy2;
      if (bRem > 0) { const float bw = sqrtApprox(bRem) + 0.01f; p0 = ifloor(b.fx + b.bX - bw - 0.5f); p1 = iceil(b.fx + b.bX + bw - 0.5f); }
      else bRem = 0;
    }
    if (p0 <= p1) { if (p0 < lo) p0 = lo; if (p1 > hi) p1 = hi; if (p0 > p1) { p0 = 1; p1 = 0; } }   // its part in [lo, hi]
    const bool pin = p0 <= p1;
    FZ_ADD(fizzProf, FZ_CYC_ROWPREP, fr0);
    FZ_T0(fr1);
    if (!pin && lo == a && hi == e) maskRow(row, a, e, k);   // the common row: nothing veiled, out of the pinpoint's reach
    else {
      MaskPxK q{b.fx, b.bX, bdy2, bRem, c.bIn2, c.rbOut, fzBlickK, b.tintA,
                fizzSurf[iy], fizzSurfL[iy], strokeR[iy], strokeL[iy], fzVeilA, fzPullR, fzPullL, veilLo, veilHi, cRim[iy], b.cBlick};
      if (lo > hi) maskPx(row, a, e, k, q);
      else {
        if (a < lo) maskPx(row, a, lo - 1, k, q);
        if (!pin) maskRow(row, lo, hi, k);
        else { if (lo < p0) maskRow(row, lo, p0 - 1, k); maskPx(row, p0, p1, k, q); if (p1 < hi) maskRow(row, p1 + 1, hi, k); }
        if (hi < e) maskPx(row, hi + 1, e, k, q);
      }
    }
    FZ_ADD(fizzProf, FZ_CYC_DISC, fr1);
  }
}
// The frame's bubbles, planned in slot order (idle slots: v 0), and (tiled) each band's list of them.
void Tube::planFizz(const Params &p, const FizzFrame &ff) {
  MarkPlan &mp = *plan;
  fzVeilA = ff.veilA; fzPullR = ff.pullR; fzPullL = ff.pullL; fzBlickK = p.fizzBlick; fzXsI = ff.xsI; fzL = ff.L; fzMir = ff.mir;
  FizzLook &fl = *look;
  if (!fl.valid || fl.key[0] != p.fizzSize || fl.key[1] != p.fizzSizeVar || fl.key[2] != p.fizzShadeOff || fl.key[3] != p.fizzBlick) buildFizzClasses(fl, p);
  takeFizzMasks(fl, p);
  for (int l = 0; l < FIZZ_DEPTHS; l++) {   // a depth level's colours: as planBubble / bubbleRows mixed them per bubble (sim cRimD / cBlickD)
    const float z = (l + 0.5f) * (1.0f / FIZZ_DEPTHS), depthK = 1 - p.fizzDepth * z * (1 - p.liquidTransparency);   // fizzZ's values
    const int depthT = depthK < 1 ? (int)(depthK * 256 + 0.5f) : 256;
    fl.tintA[l] = p.bubbleDark * depthK;
    for (int iy = 0; iy < H; iy++) {
      fl.cRim[l][iy] = blend565T(pal.rows[iy], pal.bubbleRimRows[iy], depthT);
      fl.cBlick[l][iy] = depthK < 1 ? blend565(pal.rows[iy], ff.blickC, depthK) : ff.blickC;
    }
  }
  for (int iy = 0; iy < H; iy++) {   // ix + 1 > sR  <=>  ix >= floor(sR); ix < sL  <=>  ix < ceil(sL); no band: never (|ix| < PANEL_W)
    const float lo = ffloor(fizzSurf[iy]), hi = fceil(fizzSurfL[iy]);   // clamped to int16: the same answers for |ix| < PANEL_W
    look->veilLo[iy] = strokeR[iy] > 0 ? (int16_t)(int)clampf(lo, -32767, 32767) : INT16_MAX;
    look->veilHi[iy] = strokeL[iy] > 0 ? (int16_t)(int)clampf(hi, -32767, 32767) : INT16_MIN;
  }
  mp.nBub = 0;
  for (int k = 0; k < fizzN; k++) if (fizz[k].v != 0) planBubble(fizz[k], p, ff, mp.bub[mp.nBub++]);
#if TILE_RENDER
  const int nb = (H + TUBE_BAND - 1) / TUBE_BAND;
  int16_t *const start = mp.bandStart;
  for (int b = 0; b <= nb; b++) start[b] = 0;
  auto bands = [&](const BubblePlan &u, int &b0, int &b1) {
    const int lo = u.iyA > 0 ? u.iyA : 0, hi = u.iyB < H - 1 ? u.iyB : H - 1;
    b0 = lo / TUBE_BAND; b1 = lo <= hi ? hi / TUBE_BAND : b0 - 1;
  };
  for (int i = 0; i < mp.nBub; i++) { int b0, b1; bands(mp.bub[i], b0, b1); for (int b = b0; b <= b1; b++) start[b + 1]++; }
  for (int b = 0; b < nb; b++) start[b + 1] += start[b];
  int16_t at[MARK_BANDS];
  for (int b = 0; b < nb; b++) at[b] = start[b];
  for (int i = 0; i < mp.nBub; i++) { int b0, b1; bands(mp.bub[i], b0, b1); for (int b = b0; b <= b1; b++) mp.bandBub[at[b]++] = (uint16_t)i; }
#endif
}
// The planned bubbles over tube rows [r0, r1): a band's list, or all of them over the whole tube.
void Tube::fizzBand(int r0, int r1) {
  MarkPlan &mp = *plan;
  if (r0 == 0 && r1 == H) { for (int i = 0; i < mp.nBub; i++) bubbleRows(mp.bub[i], r0, r1); return; }
#if TILE_RENDER
  const int b = r0 / TUBE_BAND;
  for (int j = mp.bandStart[b]; j < mp.bandStart[b + 1]; j++) bubbleRows(mp.bub[mp.bandBub[j]], r0, r1);
#endif
}

bool render_init(bool fast) {
  fizzSeed();
  fizzMasks.psCap = fizzMaskWorst();   // the sliders' largest bubbles (~55 KB on the LCD)
  fizzMasks.ps = (uint8_t *)heap_caps_malloc(fizzMasks.psCap, MALLOC_CAP_SPIRAM);
  if (FIZZ_MASK_INTL && fast) fizzMasks.intl = (uint8_t *)heap_caps_malloc(FIZZ_MASK_INTL, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
  EXP565 = (uint32_t *)heap_caps_malloc(512 * sizeof(uint32_t), MALLOC_CAP_SPIRAM);
  buildLuts();
  bool ok = EXP565 != nullptr && fizzMasks.ps && (!FIZZ_MASK_INTL || !fast || fizzMasks.intl);
#if TUBE_COUNT == 3
#ifdef BOARD_LCD316
  const uint32_t tubeSCaps = fast ? MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT : MALLOC_CAP_SPIRAM;   // fast: hot per-row arrays internal
#else
  const uint32_t tubeSCaps = MALLOC_CAP_SPIRAM;
#endif
  if (void *mem = heap_caps_malloc(sizeof(Tube), tubeSCaps)) tubeS = new (mem) Tube();   // never freed
  if (!tubeS) return false;
  for (int i = 0; i < 3; i++) tubeAt(i).lane = TUBE_LANE(i);
#endif
  for (int i = 0; i < TUBE_COUNT; i++) {
    Tube &tb = tubeAt(i);
    tb.idx = i;   // the tube's px scale (TUBE_PX_SCALE) before its first render: stepFizzTube reads it
    tb.set.poolC = (uint16_t *)heap_caps_malloc(GLYPH_POOL_PX * 2, GLYPH_POOL_CAPS);
    tb.set.poolA = (uint8_t *)heap_caps_malloc(GLYPH_POOL_PX, GLYPH_POOL_CAPS);
    tb.set.poolS = (uint8_t *)heap_caps_malloc(GLYPH_SPAN_BYTES, MALLOC_CAP_SPIRAM);
    tb.wetShare = (uint16_t *)heap_caps_malloc(PANEL_W * sizeof(uint16_t), MALLOC_CAP_SPIRAM);
    tb.wetRun = (int16_t *)heap_caps_malloc((PANEL_W + 1) * sizeof(int16_t), MALLOC_CAP_SPIRAM);
    tb.digitOff = (float *)heap_caps_malloc(2 * TUBE_HEIGHT_MAX * sizeof(float), MALLOC_CAP_SPIRAM);
    tb.traceLut = (uint16_t *)heap_caps_malloc(2 * TRACE_LUT * sizeof(uint16_t), MALLOC_CAP_SPIRAM);
    tb.fizz = (Fizz *)heap_caps_malloc(FIZZ_POOL * sizeof(Fizz), MALLOC_CAP_SPIRAM);
    tb.palCache = (PalCache *)heap_caps_malloc(sizeof(PalCache), MALLOC_CAP_SPIRAM);
    {   // step 9; bubble plans one 64-B cache line each: aligned by hand (never freed)
      const uintptr_t raw = (uintptr_t)heap_caps_malloc(sizeof(MarkPlan) + 63, MALLOC_CAP_SPIRAM);
      tb.plan = raw ? (MarkPlan *)((raw + 63) & ~(uintptr_t)63) : nullptr;
    }
    ok = ok && tb.plan;
    {   // 16-B aligned by hand (never freed). LCD fast mode: internal RAM (the SIMD lanes are rewritten every run; in PSRAM they
        // cost the pinned render ~1.5 ms, 2026-11-06); the BLE window and the AMOLED: PSRAM
#ifdef BOARD_LCD316
      const uint32_t scratchCaps = fast ? MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT : MALLOC_CAP_SPIRAM;
#else
      const uint32_t scratchCaps = MALLOC_CAP_SPIRAM;
#endif
      const uintptr_t raw = (uintptr_t)heap_caps_malloc(sizeof(DigitScratch) + 15, scratchCaps);
      tb.scratch = raw ? (DigitScratch *)((raw + 15) & ~(uintptr_t)15) : nullptr;
    }
    ok = ok && tb.scratch;
#if DIGIT_PIE
    tb.fracMemo = (FracMemo *)heap_caps_malloc(sizeof(FracMemo), MALLOC_CAP_SPIRAM);
    if (tb.fracMemo) tb.fracMemo->valid = false;
    ok = ok && tb.fracMemo;
#endif
    tb.look = (FizzLook *)heap_caps_malloc(sizeof(FizzLook), MALLOC_CAP_SPIRAM);   // ~5 KB
    if (tb.look) {
      FizzLook &fl = *tb.look;
      fl.valid = fl.masks = false; fl.mask = nullptr;
    }
    ok = ok && tb.look;
    tb.foam = (FoamWork *)heap_caps_malloc(sizeof(FoamWork), MALLOC_CAP_SPIRAM);   // ~12 KB
    if (tb.foam) memset(tb.foam, 0, sizeof(FoamWork));
    ok = ok && tb.foam;
#ifdef BOARD_LCD316
    tb.glowT = (EffectTable *)heap_caps_malloc(2 * sizeof(EffectTable), MALLOC_CAP_SPIRAM);
    if (tb.glowT) for (int k = 0; k < 2; k++) tb.glowT[k].valid = false;
    ok = ok && tb.glowT;
#endif
#if TILE_RENDER && defined(TILE_VERIFY)
    tb.tileVerifyStrip = (uint16_t *)heap_caps_malloc((size_t)TUBE_HEIGHT_MAX * PANEL_W * 2, MALLOC_CAP_SPIRAM);
    ok = ok && tb.tileVerifyStrip;
#endif
#if TILE_RENDER
    tb.tileHash = (uint32_t *)heap_caps_malloc((size_t)TILE_MAX * TILE_PAIRS * sizeof(uint32_t), MALLOC_CAP_SPIRAM);   // ~51 KB
    for (int e = 0; e < 2; e++) {
      tb.dirty[e] = (TileDirty *)heap_caps_malloc(sizeof(TileDirty), MALLOC_CAP_SPIRAM);   // ~1.6 KB
      if (tb.dirty[e]) { tb.dirty[e]->strip = nullptr; tb.dirty[e]->valid = false; }
    }
    ok = ok && tb.tileHash && tb.dirty[0] && tb.dirty[1];
#endif
#ifdef TUBE_VERIFY
    tb.verifyRow = (uint16_t *)heap_caps_malloc(PANEL_W * 2, MALLOC_CAP_SPIRAM);
    tb.verifyPal = (Palette *)heap_caps_malloc(sizeof(Palette), MALLOC_CAP_SPIRAM);
    ok = ok && tb.verifyRow && tb.verifyPal;
#endif
    if (tb.palCache) tb.palCache->valid = false;
    tb.traceMemo = (TraceMemo *)heap_caps_malloc(sizeof(TraceMemo), MALLOC_CAP_SPIRAM);
    if (tb.traceMemo) tb.traceMemo->valid = false;
    tb.traceStreakTab = (float *)heap_caps_malloc(TUBE_LENGTH_PX * sizeof(float), MALLOC_CAP_SPIRAM);
    if (tb.traceStreakTab) for (int x = 0; x < TUBE_LENGTH_PX; x++) tb.traceStreakTab[x] = traceStreak(x + (uint32_t)i * 6151u);
    ok = ok && tb.traceStreakTab;
    if (uint8_t *rows = (uint8_t *)heap_caps_malloc(TUBE_HEIGHT_MAX * sizeof(DigitRow) + 63, MALLOC_CAP_SPIRAM))   // one row per cache line
      tb.digitRows = (DigitRow *)(((uintptr_t)rows + 63) & ~(uintptr_t)63);
    ok = ok && tb.fizz && tb.set.poolC && tb.set.poolA && tb.set.poolS && tb.wetShare && tb.wetRun && tb.digitOff
         && tb.digitRows && tb.traceLut && tb.palCache && tb.traceMemo;
  }
  FILM_PHI = (uint16_t *)heap_caps_malloc(257 * sizeof(uint16_t), MALLOC_CAP_SPIRAM);
  FILM_LG = (uint16_t *)heap_caps_malloc(256 * sizeof(uint16_t), MALLOC_CAP_SPIRAM);
  FILM_EX = (uint8_t *)heap_caps_malloc(4096, MALLOC_CAP_SPIRAM);
  ok = ok && FILM_PHI && FILM_LG && FILM_EX;
  if (FILM_PHI && FILM_LG && FILM_EX) buildFilmLuts();
#if TILE_RENDER
  ok = tiles_init() && ok;   // the tile slots and their copy engine (tiles.h)
#endif
  return ok;
}

// traceFillLutI's block bounds: the largest traceA of each TRACE_BLK block over [a0, a1). Once a frame a tube: flash
// (no IRAM to spare).
static void __attribute__((noinline)) traceBlockMax(const uint16_t *traceA, int a0, int a1, uint16_t *blkMax) {
  for (int b = a0 / TRACE_BLK; b * TRACE_BLK < a1; b++) {
    const int x0 = b * TRACE_BLK > a0 ? b * TRACE_BLK : a0, x1 = (b + 1) * TRACE_BLK < a1 ? (b + 1) * TRACE_BLK : a1;
    uint16_t m = 0;
    for (int x = x0; x < x1; x++) if (traceA[x] > m) m = traceA[x];
    blkMax[b] = m;
  }
}
// drawTube 3d's residue blur and streak (traceA over [a0, a1), and its non-zero range aLo / aHi), with its memo across
// frames (TraceMemo): traceA[x] is a function of traceRaw over [x - 4, x + 4] (clamped), filmV, x and the tube only, so a
// column is recomputed only where its window holds a changed or unknown value or it was not computed last frame; a frame
// with no change at all over the same range keeps last frame's aLo / aHi too (pinned, the stain dried: the whole blur
// was ~1.1 ms a tube, step 6). The streak per column comes from a table built once (traceStreakTab, the same function).
TUBE_IRAM void __attribute__((noinline)) Tube::traceBlur(const uint16_t *trace, bool mir, int a0, int a1, int c0, int c1, float filmV,
                                                           int &aLoOut, int &aHiOut) {
  TraceMemo &tm = *traceMemo;
  const bool memo = tm.valid && __builtin_bit_cast(uint32_t, tm.filmV) == __builtin_bit_cast(uint32_t, filmV);
#ifdef TUBE_VERIFY
  bool fastHit = false; const int keepLo = tm.aLo, keepHi = tm.aHi;
#endif
  if (memo && a0 == tm.a0 && a1 == tm.a1 && c0 == tm.c0 && c1 == tm.c1) {
    uint32_t diff = 0;
    for (int x = c0; x < c1; x++) diff |= (uint32_t)(trace[mir ? L - 1 - x : x] ^ traceRaw[x]);
#ifndef TUBE_VERIFY
    if (!diff) { aLoOut = tm.aLo; aHiOut = tm.aHi; return; }
#else
    fastHit = !diff;   // verify: recompute every column (all memo hits, checked below) and the range
#endif
  }
  uint8_t *const dirty = tm.dirty;
  for (int x = a0; x < a1; x++) dirty[x] = !memo || x < tm.a0 || x >= tm.a1;
  for (int x = c0; x < c1; x++) {
    const uint16_t v = trace[mir ? L - 1 - x : x];
    if (!memo || x < tm.c0 || x >= tm.c1 || v != traceRaw[x]) {
      const int d0 = x - 4 < a0 ? a0 : x - 4, d1 = x + 5 > a1 ? a1 : x + 5;
      for (int d = d0; d < d1; d++) dirty[d] = 1;
    }
    traceRaw[x] = v;
  }
  tm.valid = true; tm.filmV = filmV; tm.a0 = a0; tm.a1 = a1; tm.c0 = c0; tm.c1 = c1;
  int aLo = 65535, aHi = 0;
  // +-4 px triangular blur before the streak texture (see sim): tapers the smear's outer end
  // (dense turnaround deposit next to bare glass) into a tide mark instead of a 1-px cliff. The streak
  // scatters the coat's thickness; A = eta (2 - eta) 2^16 is the column's film path coefficient.
  // Columns 4 .. L - 5 read their window without clamping (the same indices).
  const float *const streak = traceStreakTab;
  for (int x = a0; x < a1; x++) {
#ifndef TUBE_VERIFY
    if (!dirty[x]) { const int ta = traceA[x]; if (ta) { if (ta < aLo) aLo = ta; if (ta > aHi) aHi = ta; } continue; }
#endif
    uint32_t acc = 5u * traceRaw[x];
    if (x >= 4 && x <= L - 5) {
      const uint16_t *r = traceRaw + x;
      acc += 4u * (r[-1] + r[1]) + 3u * (r[-2] + r[2]) + 2u * (r[-3] + r[3]) + (uint32_t)(r[-4] + r[4]);
    } else for (int d = 1; d <= 4; d++) {
      const int m = x < d ? 0 : x - d, q2 = x > L - 1 - d ? L - 1 : x + d;
      acc += (uint32_t)(5 - d) * (traceRaw[m] + traceRaw[q2]);
    }
    const float v = acc * (1.0f / 25.0f);
    const float eta = FILM_ETA_MAX * fmx(v * (1.0f / TRACE_FULL), filmV) * streak[x];
    const int ta = (int)(eta * (2 - eta) * 65536.0f + 0.5f);
#ifdef TUBE_VERIFY
    if (!dirty[x]) tubeVerify(TV_TRACE, 1, traceA[x] != (uint16_t)ta);
    { const float sk = traceStreak(x + (uint32_t)idx * 6151u); tubeVerify(TV_TRACE, 1, __builtin_bit_cast(uint32_t, sk) != __builtin_bit_cast(uint32_t, streak[x])); }
#endif
    traceA[x] = (uint16_t)ta;
    if (ta) { if (ta < aLo) aLo = ta; if (ta > aHi) aHi = ta; }
  }
#ifdef TUBE_VERIFY
  if (fastHit) tubeVerify(TV_TRACE, 2, (keepLo != aLo) + (keepHi != aHi));
#endif
  tm.aLo = aLo; tm.aHi = aHi;
  aLoOut = aLo; aHiOut = aHi;
  traceBlockMax(traceA, a0, a1, tm.blkMax);
}

// Safe to call for tubes on different lanes (hours and minutes / seconds) concurrently from different tasks: each touches
// only tubeAt(idx), its lane's scratch and its own strip; params / state are read-only for the duration of the call.
void renderTube(int idx, const TubeState &s, const Params &p, uint32_t gen, uint16_t *strip, const int16_t **lensRows, int y0) {
  Tube &t = tubeAt(idx);
#ifdef DIGIT_PROF
  memset(t.prof, 0, sizeof(t.prof)); memset(t.profCyc, 0, sizeof(t.profCyc));
#endif
#ifdef TUBE_PROF
  const uint32_t tu0 = esp_cpu_get_cycle_count();
#endif
  TubeLayout lay = tubeLayout(p);
  t.FB = strip; t.H = lay.H; t.baseY = y0 >= 0 ? y0 : idx == 0 ? lay.yH : lay.yM; t.idx = TUBE_COUNT == 3 ? idx : idx & 1;
  t.rowLo = t.baseY; t.rowHi = t.baseY + t.H;
  TCLIP_SET(strip, strip + (size_t)t.H * PANEL_W);
  t.lensRowsOut = lensRows; if (lensRows) *lensRows = nullptr;
  t.buildRowCache(p, gen);
  Palette &pal = t.pal;
  if (!(pal.valid && pal.gen == gen && pal.H == t.H && pal.light == s.light)) {
    t.buildPalCache(p, gen, *t.palCache);
#ifdef TUBE_PROF
    const uint32_t tp0 = esp_cpu_get_cycle_count();
#endif
    t.buildPalette(p, s.light, pal, *t.palCache);
#ifdef TUBE_PROF
    const uint32_t tp1 = esp_cpu_get_cycle_count(); t.tubeProf[TU_PALP] += tp1 - tp0;
#endif
    t.buildBandRows(*t.palCache);
#ifdef TUBE_PROF
    t.tubeProf[TU_PALB] += esp_cpu_get_cycle_count() - tp1;
#endif
#ifdef TUBE_VERIFY
    {
      Palette &r = *t.verifyPal; t.buildPaletteRef(p, s.light, r); int bad = 0;
      for (int y = 0; y < t.H; y++)
        bad += (r.rows[y] != pal.rows[y]) + (r.bubbleIn[y] != pal.bubbleIn[y]) + (r.tubeBackRows[y] != pal.tubeBackRows[y])
               + (r.bubbleRimRows[y] != pal.bubbleRimRows[y]) + (memcmp(&r.rowK[y], &pal.rowK[y], 4) != 0) + (r.dryT[y] != pal.dryT[y]);
      bad += (r.body != pal.body) + (r.tubeBack != pal.tubeBack) + (r.bubbleRim != pal.bubbleRim);
      tubeVerify(TV_PAL, 6 * t.H + 3, bad);
    }
#endif
    pal.valid = true; pal.gen = gen; pal.H = t.H; pal.light = s.light;
  }
#ifdef TUBE_PROF
  t.tubeProf[TU_PAL] += esp_cpu_get_cycle_count() - tu0;
#endif
#if TILE_RENDER
  t.renderSeq++;   // the change records (tiles.h) count every render
#endif
  t.drawTube(t.baseY, s, p, gen, idx == 0 ? 12 : 60);
#ifdef TUBE_PROF
  t.tubeProf[TU_ALL] += esp_cpu_get_cycle_count() - tu0; t.tubeProf[TU_FRAMES]++;
#endif
}

#ifdef FIZZ_PROF
const uint32_t *render_fizz_profile(int idx) { return tubeAt(idx).fizzProf; }
const uint32_t *render_fizz_step_profile() { for (int i = 0; i < FS_N; i++) fizzStepProf[i] = fizzStepProfCore[0][i] + fizzStepProfCore[1][i]; return fizzStepProf; }
void render_fizz_profile_reset() { for (int i = 0; i < TUBE_COUNT; i++) memset(tubeAt(i).fizzProf, 0, sizeof(tubeAt(i).fizzProf)); memset(fizzStepProfCore, 0, sizeof(fizzStepProfCore)); }
#endif
#ifdef TUBE_PROF
const uint32_t *render_tube_profile(int idx) { return tubeAt(idx).tubeProf; }
void render_tube_profile_reset() { for (int i = 0; i < TUBE_COUNT; i++) memset(tubeAt(i).tubeProf, 0, sizeof(tubeAt(i).tubeProf)); }
#endif
#ifdef TICK_PROF
const uint32_t *render_tick_profile(int idx) { return tubeAt(idx).tickProf; }
void render_tick_profile_reset() { for (int i = 0; i < TUBE_COUNT; i++) memset(tubeAt(i).tickProf, 0, sizeof(tubeAt(i).tickProf)); }
#endif
#if TILE_RENDER
const TileDirty *tile_dirty(const uint16_t *strip) {
  for (int i = 0; i < TUBE_COUNT; i++)
    for (int e = 0; e < 2; e++) { const TileDirty *d = tubeAt(i).dirty[e]; if (strip && d && d->strip == strip) return d; }
  return nullptr;
}
bool tile_strip_clean(const uint16_t *strip) {
  for (int i = 0; i < TUBE_COUNT; i++)
    for (int e = 0; e < 2; e++) { Tube &t = tubeAt(i); if (strip && t.cleanStrip[e] == strip) { t.cleanStrip[e] = nullptr; return true; } }
  return false;
}
#endif
bool render_seq_reset(uint32_t seed) {
  for (int i = 0; i < TUBE_COUNT; i++) { Tube &t = tubeAt(i); t.fizzN = 0; t.fizzLen = 0; t.springScatter = 0; t.springClock = 0; if (t.foam) t.foam->nOrder = 0; }
  return fizzReseed(seed);
}
#ifdef DIGIT_PROF
const uint32_t *render_profile(int idx) { return tubeAt(idx).prof; }
const uint32_t *render_profile_cycles(int idx) { return tubeAt(idx).profCyc; }
#endif
