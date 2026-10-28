#include <climits>
#include "render.h"
#include "gen/sprites_gen.h"
#include "layout.h"
#ifdef DIGIT_PROF
#include "esp_timer.h"
#include "esp_cpu.h"
#endif
#include <math.h>
#include <string.h>
#include <stdlib.h>
#include <esp_heap_caps.h>
#include <esp_random.h>

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
static inline uint16_t q(RGB c) {
  return rgb565((int)jround(clampf(c.r, 0, 255)), (int)jround(clampf(c.g, 0, 255)), (int)jround(clampf(c.b, 0, 255)));
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
// Dried-trace fill of one strip row over [x0, x1) over the tube back (the only layer under it), written in the
// strip's byte-swapped layout. aLo / aHi = the smallest non-zero / largest traceA of the span, so every depth
// lies in [depthT(aLo), depthT(aHi)] (monotone in A): when that is a narrow band (a uniform traceFilm: the
// streak spans 18 %) and the span is long, the row's colours come from a LUT built once, otherwise per pixel.
// noinline: inside drawTube the loop shared a register file with hundreds of locals and spilled every
// iteration; on its own it stays in registers.
#define TRACE_LUT 48
static void __attribute__((noinline)) traceFillRow(uint16_t *row, const uint16_t *traceA, int x0, int x1, const ResidueTint &tint,
                                                    int aLo, int aHi, uint16_t *lut) {   // lut: TRACE_LUT entries, the tube's own
  const ResidueTint t = tint;
  const int Tlo = t.depthT((uint32_t)aLo), Thi = t.depthT((uint32_t)aHi);
  if (Thi - Tlo < TRACE_LUT && x1 - x0 > 2 * (Thi - Tlo + 1)) {
    for (int T = Tlo; T <= Thi; T++) lut[T - Tlo] = T ? __builtin_bswap16(t.at(T)) : 0;
    for (int x = x0; x < x1; x++) {
      if (!traceA[x]) continue;
      const int T = t.depthT(traceA[x]);
      if (T) row[x] = lut[T - Tlo];
    }
    return;
  }
  for (int x = x0; x < x1; x++) {
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
static void __attribute__((noinline)) traceShearRow(uint16_t *row, const uint16_t *traceA, int a0, int a1, int x0, int x1,
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
// Step 3 soft-edge AA ramp plus folded glow, time edge: rightwards from a0 until the alpha reaches 0.
static void __attribute__((noinline)) rampRowR(uint16_t *row, int a0, int aEnd, float ex, float hw, float invW, float invGlow,
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
static void __attribute__((noinline)) rampRowL(uint16_t *row, int xStart, int bEnd, float exL, float hw, float invW, float invGlow,
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
// newlib's sqrtf is a bit-by-bit software loop here. Reciprocal-sqrt seed + 3 Newton steps: relative error <= 2.1e-7
// against sqrtf for 1e-30 <= x < 1200 (below that it returns < 1e-10); as an 8-bit coverage it moved 1 step in
// 2.5e-7 of the samples. Not for values that must match the sim bit for bit.
static inline float rsqrtApprox(float x) {   // 1/sqrt(x), same seed and Newton steps as sqrtApprox
  uint32_t i; memcpy(&i, &x, 4); i = 0x5f3759dfu - (i >> 1);
  float y; memcpy(&y, &i, 4);
  const float hx = 0.5f * x;
  y = y * (1.5f - hx * y * y); y = y * (1.5f - hx * y * y); y = y * (1.5f - hx * y * y);
  return y;
}
static inline float sqrtApprox(float x) {
  uint32_t i; memcpy(&i, &x, 4); i = 0x5f3759dfu - (i >> 1);
  float y; memcpy(&y, &i, 4);
  const float hx = 0.5f * x;
  y = y * (1.5f - hx * y * y); y = y * (1.5f - hx * y * y); y = y * (1.5f - hx * y * y);
  return x * y;
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
};
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
// Two instantiations: BLICK false is the plain disc (small bubbles, fizzBlick 0) and carries none of the pinpoint
// state in its pixel loop; BLICK true also skips the pinpoint test on rows its disc cannot reach.
template <bool BLICK>
static void __attribute__((noinline)) discRowT(uint16_t *row, int ixa, int ixb, const DiscRow &d) {
  const float fx = d.fx, dy = d.dy, dy2 = dy * dy, r = d.r, in2 = d.in2, out2 = d.out2, offX = d.offX, offY = d.offY, wallT = d.wallT;
  const float bdy = BLICK ? dy - d.bY : 0, bRem = BLICK ? d.bOut2 - bdy * bdy : 0;   // pinpoint reach left for dx² on this row
  const bool blickRow = BLICK && bRem > 0;
  const int veilLo = d.veilLo, veilHi = d.veilHi;
  // See-through interior with no tint and no pinpoint on this row: pixels certainly inside the core (dc2 < core2Lo
  // with a pixel of slack) would reach `continue` without a write, so the loop jumps over them. Output-neutral.
  int skipLo = INT_MAX, skipHi = INT_MIN;
  if (d.core && d.tintA <= 0 && !blickRow) {
    const float cy = dy - offY, rem = d.core2Lo * (1 - 1e-4f) - cy * cy;
    if (rem > 0) { const float hw = sqrtApprox(rem) - 1; if (hw > 0) { skipLo = (int)fceil(fx + offX - hw - 0.5f); skipHi = (int)ffloor(fx + offX + hw - 0.5f); } }
  }
  for (int ix = ixa; ix <= ixb; ix++) {
    if (ix == skipLo && skipHi >= skipLo) { ix = skipHi; continue; }
    const float dx = ix + 0.5f - fx;
    const float d2 = dx * dx + dy2;
    if (d2 >= out2) continue;   // d > r + 0.5: no coverage
    float cov = (d2 <= in2 ? 1.0f : fmn(1, r + 0.5f - sqrtApprox(d2))) * wallT;
    if (cov <= 0) continue;
    if (ix >= veilLo || ix < veilHi) cov = discVeil(ix, d, cov);   // only bubbles at a surface band pay for the veil
    const float cx = dx - offX, cy = dy - offY, dc2 = cx * cx + cy * cy;
    const bool inCore = d.core && (dc2 < d.core2Lo || (dc2 <= d.core2Hi && sqrtf(dc2) < d.kc));
    float g = 0;
    if (blickRow) {   // pinpoint weight
      const float bdx = dx - d.bX, bdx2 = bdx * bdx;
      if (bdx2 < bRem) { const float db2 = bdx2 + bdy * bdy; g = d.blickK * (db2 <= d.bIn2 ? 1.0f : clampf(d.rbOut - sqrtApprox(db2), 0, 1)); }
    }
    const int x = d.mirror ? d.L - 1 - (ix + d.xsI) : ix + d.xsI;
    if (x < 0 || x >= PANEL_W) continue;
    if (inCore) {   // see-through interior (sim): the pinpoint or the dark tint over the liquid as-is, one write, nothing at tint 0
      if (g > 0) { const float w = g + d.tintA * (1 - g); rowPxa(row, x, d.tintA > 0 ? blend565(0, d.cBlick, g / w) : d.cBlick, cov * w); }   // fused with the tint (sim)
      else if (d.tintA > 0) rowPxa(row, x, 0, cov * d.tintA);
      continue;
    }
    rowPxa(row, x, g > 0 ? blend565(d.cRim, d.cBlick, g) : d.cRim, cov);   // ring, pinpoint mixed in 888 before the one blend
  }
}
static inline void discRow(uint16_t *row, int ixa, int ixb, const DiscRow &d) {
  if (d.blick) discRowT<true>(row, ixa, ixb, d); else discRowT<false>(row, ixa, ixb, d);
}
// Step 3e concave surface band over [xa, xb): pixel-footprint stroke from the inner shoulder to the outer
// colour at interior opacity `fill` (surfaceFill), thinned by the receding pull, the blick (`blickK`: this
// row's specular weight, peaking mid-dish) and the lit rim. See sim.
static void __attribute__((noinline)) bandRow(uint16_t *row, int xa, int xb, float xm, int dir, float hw, float wEff, float invWidth,
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

// Per-channel LUTs built once with the exact float formulas they replace (bit-exact with the sim):
// sprite alpha 0..255 -> blend fraction; tick emboss highlight / shadow of an expanded 565 channel.
static uint16_t LUT_alphaT16[256];
static uint8_t LUT_embHi[256], LUT_embLo[256];
static void buildLuts() {
  for (int v = 0; v < 256; v++) {
    LUT_alphaT16[v] = (uint16_t)alphaT(v / 255.0f);
    LUT_embHi[v] = (uint8_t)jround(clampf((float)v + (255.0f - (float)v) * 0.7f, 0, 255));
    LUT_embLo[v] = (uint8_t)jround(clampf((float)v * 0.25f, 0, 255));
  }
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
// bw x bh = (5 * 6) x (7 * 6) texels, each grown by the largest shadow offset (4) on the right and below,
// two planes (behind air / behind liquid) when the shadow is baked in — 31280 texels, ~92 KB per tube on the
// AMOLED; scale and offset are design px, so a board's PX_SCALE grows both sides (rounded up).
// A set that does not fit (values pushed past the sliders over serial) drops the glyphs past the budget
// (visible, not silent).
#define GLYPH_CEIL(v) ((int)(v) + ((float)(int)(v) < (v)))
#define GLYPH_POOL_PX (10 * 2 * (GLYPH_CEIL(5 * 6 * PX_SCALE) + GLYPH_CEIL(4 * PX_SCALE)) * (GLYPH_CEIL(7 * 6 * PX_SCALE) + GLYPH_CEIL(4 * PX_SCALE)))
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
// GLYPH_SPAN_ROWS covers the bh cap (96) plus the largest slider shadow offset (4 design px, 5 at PX_SCALE 4/3); a glyph pushed taller
// (or wider than 255 columns) over serial draws without spans (full rows), never past the table.
#define GLYPH_SPAN_ROWS 128
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

struct Label { int x0, y; char text[3]; int len; int adv[2]; };   // y: panel row of the first glyph's top
struct Labels {
  Label list[12]; int n; int bw, bh, ry0, ry1, yTop; ScaledGlyph *sprite; const Font *font; int gap;
  uint16_t rows[96]; int16_t sourceRows[TUBE_HEIGHT_MAX]; int shadow, shadowT, shadowOff;   // shadow colour (-1 = none), opacity 1/256, px offset
  int16_t drySourceRows[TUBE_HEIGHT_MAX]; int dryRy0, dryRy1;   // rear digits behind air (digitDryLens)
  // Vertical watch: glyphs turned to read upright, a label's digits advance across the tube (panel y) from
  // Label::y, Label::x0 is where the glyph body starts along it; bw x bh stay the glyph as read (sim Labels).
  bool vertical = false;
  float wetDx = 0, wetDy = 0;   // fractional refraction shift of the columns behind liquid (digitParallax); 0 behind air / on top
  // cache key: everything above is a function of (params gen, H) plus these motion-derived ints (the shifts
  // are applied at draw time; only floor(wetDy) enters the key, through the wet row span)
  uint32_t gen = 0; int H = 0, bottomOff = 0, first = -1, keyWetDy = 0; bool valid = false, have = false;
};

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
// Bubbles per tube (sim FIZZ_MAX): the sliders' worst case, fizzCount 120 doubled by full agitation (<= 1). A
// count pushed past the sliders over serial (or a spring needing more) is capped and reported (fizzOverflow), not
// silently dropped.
#define MAX_FIZZ 240
static int fizzOverflowPeak = 0;   // largest count requested past MAX_FIZZ (0 = everything fitted), see fizzOverflow()
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
#define FOAM_CATCH (2.0f * PX_SCALE)
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

// All mutable state of one tube's renderer (hours = tubes[0], minutes = tubes[1]). Two of these are
// static (fixed footprint, ~9 KB each); the strip pointer / geometry are set per call by renderTube.
// Nothing here is shared between the two, so the tubes can render concurrently on both cores.
struct Tube {
  uint16_t *FB = nullptr; int baseY = 0, H = TUBE_HEIGHT_PX; int idx = 0;
  const int16_t **lensRowsOut = nullptr;   // set by renderTube: hand the lens row map to the caller instead of applying it
  Palette pal; RowCache rc; Labels labels; ScaledSet set;
#ifdef DIGIT_PROF
  mutable uint32_t prof[11] = {};     // per frame: glyphs, rows, int px plain, int px liquid, frac px plain, frac px liquid, slow px, runs; us: layoutLabels, rear ticks, rear digits
  mutable uint32_t profCyc[3] = {};   // CPU cycles: plain runs, band (slow) runs, ramp columns
#endif
  EffectTable glowT[2];                                       // 0 = time edge, 1 = home edge
  float edges[TUBE_HEIGHT_MAX], edgesL[TUBE_HEIGHT_MAX];      // render-frame liquid edges per row
  // rear-mark wet share per panel column (buildWetShare) + its scratch: PANEL_W / PANEL_W + 1 entries, PSRAM,
  // allocated once by render_init (internal RAM is ~2.7 KB from full once BLE is up; 4.3 KB here hung its init)
  uint16_t *wetShare = nullptr; int16_t *wetRun = nullptr;
  // digit source offset from the axis per row behind air, then behind liquid (sim TickFollow dry / wet):
  // 2 x TUBE_HEIGHT_MAX, PSRAM, allocated once by render_init
  float *digitOff = nullptr;
  float boundLo[TUBE_HEIGHT_MAX], boundHi[TUBE_HEIGHT_MAX];   // panel-frame bounds for the mark compositor (edges + surface stroke)
  float strokeR[TUBE_HEIGHT_MAX], strokeL[TUBE_HEIGHT_MAX];   // outward extent of the concave surface stroke per edge (sim strokeR/L)
  float bandFill[2][TUBE_HEIGHT_MAX], bandBlick[2][TUBE_HEIGHT_MAX], bandRim[2][TUBE_HEIGHT_MAX];   // its layer weights per row, 0 = time edge, 1 = home: rear-mark compositor (sim BandInfo)
  uint16_t backR[TUBE_HEIGHT_MAX], backL[TUBE_HEIGHT_MAX];    // local backing past each edge before body/glow: convex nose (sim backR/L)
  Fizz fizz[MAX_FIZZ]; int fizzN = 0; float fizzLen = 0;      // liquid length px, set by drawTube
  float fizzSurf[TUBE_HEIGHT_MAX], fizzSurfL[TUBE_HEIGHT_MAX]; // liquid-frame surface front per row (profile = edges - xs, the inner rim of a surface band), time / home edge, set by drawTube: where foam parks
  uint8_t fizzExposed = 0;                                    // bit 1 = time edge short of the far end, bit 2 = home edge of a free slug off the near end
  float fizzShift = 0;                                        // px the liquid frame sits off its home (a free slug that slid away; 0 pinned), set by drawTube
  float springScatter = 0;                                    // share of spring births born scattered instead (0 = all at the spring), advanced by stepFizz
  float springClock = 0;                                      // bubbles the spring may release now (its cadence accrued)
  uint16_t traceA[TUBE_LENGTH_PX];                            // dried-trace residue depth per column, 1/256 with headroom (traceAmount > 1)
  uint16_t traceRaw[TUBE_LENGTH_PX];                          // render-frame residue copy, input to the taper blur
  uint16_t traceLut[TRACE_LUT];                               // traceFillRow's per-row colour table (one per tube: both cores render)

  inline bool inStrip(int x, int y) const { return x >= 0 && x < PANEL_W && y >= baseY && y < baseY + H; }
  inline uint16_t rd(int x, int y) const { return __builtin_bswap16(FB[(y - baseY) * PANEL_W + x]); }
  inline void wr(int x, int y, uint16_t c) const { FB[(y - baseY) * PANEL_W + x] = __builtin_bswap16(c); }
  void hspan(int y, int x0, int x1, uint16_t c) const {
    if (y < baseY || y >= baseY + H) return;
    if (x0 < 0) x0 = 0; if (x1 > PANEL_W) x1 = PANEL_W;
    if (x1 <= x0) return;
    uint16_t s = __builtin_bswap16(c);
    uint16_t *p = FB + (y - baseY) * PANEL_W + x0;
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

  float glassW(const Params &p, int y, int hiTop, float lam) const;
  int highlightTop(const Params &p, float lightDeg) const;
  void buildPalette(const Params &p, float lightDeg, Palette &pal) const;
  ScaledGlyph *scaledGlyphs(int sheetIdx, int bw, int bh, float brightness, uint32_t tintHex, float tintAmt, float tone, int shadow, float shadowA, int shadowOff, float transK, bool rot, float floorC, uint16_t floorR);
  bool layoutLabels(int y0, const Params &p, uint32_t gen, int ticksN, float acrossTilt, float edgeLight, float fill, Labels &lb);
  void drawSpriteGlyph(const ScaledGlyph &g, int x, int y0, int yTop, const Labels &lb, const Warp &warp, const Mark &mark) const;
  void drawBitmapGlyph(const Font &f, int d, int x, int y0, int yTop, const Labels &lb, const Warp &warp, const Mark &mark) const;
  void drawLabels(int y0, const Labels &lb, const Warp &warp, const Mark &mark) const;
  void drawTicks(int y0, const Params &p, int ticksN, const int16_t *wetRows, const int16_t *dryRows,
                 const Edges *edges, const Mark &mark, float dxFull = 0, float dyFull = 0) const;
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
};
static Tube tubes[2];

inline void Mark::operator()(int x, int y, uint16_t c, int covT, int rel) const {
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
float Tube::glassW(const Params &p, int y, int hiTop, float lam) const {
  float t = (float)y / (H - 1);
  float amb = 0.5f + 0.5f * cosf((t - 0.3f) * (float)M_PI * 1.6f);
  float w = p.glassBody * (amb + (lam - amb) * p.lightPhys);
  if (y >= hiTop && y < hiTop + p.highlightH)
    w += p.glassHiBright * powf(1 - fabsf((y - hiTop) / fmx(1, p.highlightH - 1) - 0.5f) * 2, p.highlightSharp);
  float d = (t - 0.82f) / 0.07f;
  w += p.glassReflect * expf(-d * d);
  return fmn(1, w);
}

// Top row of the highlight band for highlight angle lightDeg (sim highlightTop).
int Tube::highlightTop(const Params &p, float lightDeg) const {
  float yc = (H - 1) / 2.0f;
  return (int)jround(yc - yc * sinf(lightDeg * (float)M_PI / 180) - (p.highlightH - 1) / 2);
}

// Style top light blended (lightPhys) with a Lambert cylinder lit from 2*light (sim buildPalette).
void Tube::buildPalette(const Params &p, float lightDeg, Palette &pal) const {
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
      float chord = sqrtf(fmx(0, 1 - u * u)), m = fmx(c.r, fmx(c.g, c.b));
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
    float gw = glassW(p, y, hiTop, lam);
    float wetK = p.glassOverLiquid + (1 - p.glassOverLiquid) * p.liquidTransparency, glassWet = gw * wetK;
    // Empty tube: back only where the ray reaches it (wall band dark), glass over it, glow + rim on top.
    const RGB dryRow = mix(scale(mix(scale(back, dryT), ghi, gw), p.brightness), glassEdge, wall);
    pal.tubeBackRows[y] = q(dryRow);
    // Glass weight rises to the dry-side one with transparency; the grazing rim is the outer surface's
    // reflection, full weight over the liquid (sim).
    c = ambientize(mix(mix(c, glassHiScaled, glassWet), glassEdge, wetRim), bodyL, ambAmt);
    if (wet < 1) c = mix(c, dryRow, (1 - wet) * (1 - dryT));   // unwetted band: the empty tube's row
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
  if (!S.poolC || !S.poolA) return nullptr;
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


bool Tube::layoutLabels(int y0, const Params &p, uint32_t gen, int ticksN, float acrossTilt, float edgeLight, float fill, Labels &lb) {
  bool minutes = ticksN == 60;
  int every = (int)fmx(1, jround(minutes ? p.digitMinuteStep : p.digitHourStep));
  // Motion-dependent parts of the layout, folded into the cache key.
  int bottomOff = p.digitsOnTop ? (int)jround(acrossTilt * p.topParallax) : 0;
  // Liquid refracts the rear wall: the wet columns slide with tilt (same sign convention as the ticks).
  // Fractional: the wet copy is resampled at draw time so it glides rather than steps.
  lb.wetDx = p.digitsOnTop ? 0 : -edgeLight * p.digitParallax;
  lb.wetDy = p.digitsOnTop ? 0 : acrossTilt * p.digitParallax;
  int wetDy = (int)ffloor(lb.wetDy);
  int start = (int)jround(minutes ? p.digitMinuteStart : p.digitHourStart); if (start <= 0) start = every;
  int first = start, last = ticksN - 1;
  if (minutes ? p.digitsLastOnlyM : p.digitsLastOnlyH) {
    float f = fill < 0 ? 0 : fill * ticksN; if (f > ticksN - 1e-3f) f = ticksN - 1e-3f;
    int s = minutes ? every : 1; first = last = (int)f / s * s;
    if (first == 0) first = 1;
  }
  if (lb.valid && lb.gen == gen && lb.H == H && lb.bottomOff == bottomOff && lb.first == first && lb.keyWetDy == wetDy) return lb.have;
  lb.valid = true; lb.gen = gen; lb.H = H; lb.bottomOff = bottomOff; lb.first = first; lb.keyWetDy = wetDy; lb.have = false;
  if (!p.digits) return false;
  float kx = minutes ? p.digitScaleXMin : p.digitScaleX, ky = minutes ? p.digitScaleYMin : p.digitScaleY;
  float bottom = (minutes ? p.digitBottomMin : p.digitBottom) + bottomOff;
  int idx = (int)jround(p.digitFont); bool useSprite = idx >= SPRITE_FONT;
  const Font *font = &FONTS[idx < 0 ? 0 : idx >= NUM_FONTS ? NUM_FONTS - 1 : idx];
  // Vertical watch: the glyph's width lies across the tube and its height along it, so the scales swap roles.
  const bool V = p.vertical; const float kw = V ? ky : kx;
  int bw = (int)fmx(1, jround((useSprite ? 5 : font->w) * kw));
  int bh = (int)fmx(1, jround((useSprite ? 7 : font->h) * (V ? kx : ky)));
  if (bh > 96) bh = 96;
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
  for (int i = first; i <= last && lb.n < 12; i += every) {
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
  for (int ry = 0; ry < H; ry++) {
    if (lb.sourceRows[ry] >= sourceRy0 + wetDy && lb.sourceRows[ry] <= sourceRy1 + wetDy + 1) {   // +1: fractional overhang
      if (ry < lb.ry0) lb.ry0 = ry;
      if (ry > lb.ry1) lb.ry1 = ry;
    }
    if (lb.drySourceRows[ry] >= sourceRy0 && lb.drySourceRows[ry] <= sourceRy1) {
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
// One destination column xd across the meniscus (0 < wet share k < 256; sim drawGlyph): every tube row, its
// source row blended from the dry warp toward the wet one by k, the refraction shift scaled by k, bilinear
// taps (weights 1/65536) of the plane the Mark picks per pixel, the colour of the heaviest tap. xg: the copy's
// panel x (glyph x plus the shadow offset). Only the columns under a meniscus take this per-pixel path.
template <class S>
static void __attribute__((noinline)) drawRampColumn(const S &s, int xg, int xd, int k, int y0, int yTop, const Labels &lb, const Mark &mark, bool shadowPass) {
  const int off = shadowPass ? lb.shadowOff : 0, sourceTop = yTop - y0 + off;
  const float kf = k * (1 / 256.0f), sx = lb.wetDx * kf, sy = lb.wetDy * kf;
  const int ix = (int)ffloor(sx), iy = (int)ffloor(sy), cx = xd - xg - ix;
  if (cx < 0 || cx > s.w) return;
  const int wx1 = (int)((sx - ix) * 256 + 0.5f), wx0 = 256 - wx1, wy1 = (int)((sy - iy) * 256 + 0.5f), wy0 = 256 - wy1;
  const int w00 = wx0 * wy0, w10 = wx1 * wy0, w01 = wx0 * wy1, w11 = wx1 * wy1;
  for (int ry = 0; ry < lb.H; ry++) {
    const int cy = blendRow(lb.drySourceRows[ry], lb.sourceRows[ry], k) - sourceTop - iy; if (cy < 0 || cy > s.h) continue;
    const bool L = mark.inLiquid(xd, ry);
    auto tap = [&](int tx, int ty) -> int { return tx < 0 || ty < 0 || tx >= s.w || ty >= s.h ? 0 : L ? s.aw(tx, ty) : s.a(tx, ty); };
    const int a00 = tap(cx, cy) * w00, a10 = tap(cx - 1, cy) * w10, a01 = tap(cx, cy - 1) * w01, a11 = tap(cx - 1, cy - 1) * w11;
    const int a = (a00 + a10 + a01 + a11 + 32768) >> 16; if (!a) continue;
    uint16_t c;
    if (shadowPass) c = (uint16_t)lb.shadow;
    else {
      int m = a00; if (a10 > m) m = a10; if (a01 > m) m = a01; if (a11 > m) m = a11;
      const int tx = m == a00 || m == a01 ? cx : cx - 1, ty = m == a00 || m == a10 ? cy : cy - 1;
      c = L ? s.cw(tx, ty) : s.c(tx, ty);
    }
    mark(xd, y0 + ry, c, shadowPass ? LUT_alphaT16[a] * lb.shadowT >> 8 : LUT_alphaT16[a]);
  }
}
// Draw one glyph (see sim drawGlyph). A panel column shows one image, chosen by its wet share: behind air (0)
// the dry copy, unshifted; behind liquid (256) the wet copy at the fractional refraction shift (wetDx, wetDy),
// bilinearly resampled (weights in 1/256) so it glides with tilt instead of stepping a whole pixel; across the
// meniscus drawRampColumn. A resampled pixel's colour comes from the tap contributing the most coverage. Rows
// outer (glyph memory is row-major); every pixel is written at most once.
template <class S>
static void drawGlyph(const S &s, int x, int y0, int yTop, const Labels &lb, const Warp &warp, const Mark &mark, bool shadowPass) {
  // the shadow copy sits down-right as read: a vertical watch's down is the panel's left
  int off = shadowPass ? lb.shadowOff : 0, xg = x + (lb.vertical ? -off : off), sourceTop = yTop - y0 + off;
  auto covT = [&](int a) { return shadowPass ? LUT_alphaT16[a] * lb.shadowT >> 8 : LUT_alphaT16[a]; };   // shadow copy at its own opacity
  bool dcol[129], wcol[129]; int gw = s.w > 128 ? 128 : s.w;
  bool anyDry = false, anyWet = false;
  int ix = (int)ffloor(lb.wetDx), iy = (int)ffloor(lb.wetDy);
  int wx1 = (int)((lb.wetDx - ix) * 256 + 0.5f), wx0 = 256 - wx1, wy1 = (int)((lb.wetDy - iy) * 256 + 0.5f), wy0 = 256 - wy1;
  const int w00 = wx0 * wy0, w10 = wx1 * wy0, w01 = wx0 * wy1, w11 = wx1 * wy1;
  for (int cx = 0; cx <= gw; cx++) {
    dcol[cx] = cx < gw && warp(xg + cx) == 0; if (dcol[cx]) anyDry = true;
    wcol[cx] = warp(xg + ix + cx) == 256; if (wcol[cx]) anyWet = true;
  }
  // Plane per PIXEL: the behind-liquid plane (aw/cw) exactly where the Mark composites through the liquid,
  // the behind-air plane elsewhere. The column's wet share above decides which image (warp and shift) it
  // shows; the meniscus makes rows of one column differ, and there the Mark's per-row test picks the plane.
  auto A = [&](bool L, int cx, int cy) -> int { return L ? s.aw(cx, cy) : s.a(cx, cy); };
  auto Cc = [&](bool L, int cx, int cy) -> uint16_t { return L ? s.cw(cx, cy) : s.c(cx, cy); };
  auto tap = [&](bool L, int cx, int cy) -> int { return cx < 0 || cy < 0 || cx >= s.w || cy >= s.h ? 0 : A(L, cx, cy); };
  int a0 = lb.dryRy0 < lb.ry0 ? lb.dryRy0 : lb.ry0, a1 = lb.dryRy1 > lb.ry1 ? lb.dryRy1 : lb.ry1;
  for (int ry = a0; ry <= a1; ry++) {
    int y = y0 + ry;
    int cyD = lb.drySourceRows[ry] - sourceTop;
    if (anyDry && ry >= lb.dryRy0 && ry <= lb.dryRy1 && cyD >= 0 && cyD < s.h) {
      for (int cx = 0; cx < gw; cx++) {
        if (!dcol[cx]) continue;
        const bool L = mark.inLiquid(xg + cx, ry); int a = A(L, cx, cyD); if (!a) continue;
        mark(xg + cx, y, shadowPass ? (uint16_t)lb.shadow : Cc(L, cx, cyD), covT(a));
      }
    }
    int cy = lb.sourceRows[ry] - sourceTop - iy;
    if (anyWet && ry >= lb.ry0 && ry <= lb.ry1 && cy >= 0 && cy <= s.h) {
      // Integer refraction shift: only the current tap contributes, with its original colour.
      if (wx1 == 0 && wy1 == 0) {
        if (cy >= s.h) continue;
        for (int cx = 0; cx < gw; cx++) {
          if (!wcol[cx]) continue;
          const bool L = mark.inLiquid(xg + ix + cx, ry); int a = A(L, cx, cy); if (!a) continue;
          mark(xg + ix + cx, y, shadowPass ? (uint16_t)lb.shadow : Cc(L, cx, cy), covT(a));
        }
        continue;
      }
      for (int cx = 0; cx <= gw; cx++) {                    // one extra column: the fractional overhang
        if (!wcol[cx]) continue;
        // destination (cx, cy) samples source (cx - fx, cy - fy): taps at columns cx / cx-1, rows cy / cy-1
        const bool L = mark.inLiquid(xg + ix + cx, ry);
        int a00 = tap(L, cx, cy) * w00, a10 = tap(L, cx - 1, cy) * w10;
        int a01 = tap(L, cx, cy - 1) * w01, a11 = tap(L, cx - 1, cy - 1) * w11;
        int a = (a00 + a10 + a01 + a11 + 32768) >> 16; if (!a) continue;
        uint16_t c;
        if (shadowPass) c = (uint16_t)lb.shadow;
        else {
          int m = a00; if (a10 > m) m = a10; if (a01 > m) m = a01; if (a11 > m) m = a11;
          c = m == a00 ? Cc(L, cx, cy) : m == a10 ? Cc(L, cx - 1, cy) : m == a01 ? Cc(L, cx, cy - 1) : Cc(L, cx - 1, cy - 1);
        }
        mark(xg + ix + cx, y, c, covT(a));
      }
    }
  }
  if (warp.all()) return;
  const int xr1 = xg + gw + (lb.wetDx > 0 ? (int)fceil(lb.wetDx) : 0);
  for (int xd = xg + (ix < 0 ? ix : 0); xd <= xr1; xd++) {
    const int k = warp(xd);
    if (k > 0 && k < 256) drawRampColumn(s, xg, xd, k, y0, yTop, lb, mark, shadowPass);
  }
}
// ---------------------------------------------------------------------------------------------
// sprite glyphs: row-run compositor (pixel-exact rewrite of drawGlyph<SpriteSampler>)
// ---------------------------------------------------------------------------------------------
// The generic path classified every texel on its own (edge test, band test, strip test, plane choice),
// which is branchy enough to spill on Xtensa. Here a glyph row is cut once into runs on which every
// decision is constant — top / behind air / behind liquid, and whether the surface band's footprint may
// cover the pixel — and each run goes through a small loop. Only the pixels under a possible band
// footprint (a conservative superset of Mark::bandMark's own test) keep the per-pixel compositor, so
// the output is byte-identical to the generic path (check_render_frames.py against the frozen renderer).
static inline int clampI(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }

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
template <int MODE>
static void __attribute__((noinline)) spriteRunInt(const Tube &t, int y, int px0, int px1, const uint8_t *a, const uint16_t *c,
                                                   int scaleT, int T, int C) {
  uint16_t *const fb = t.FB + (y - t.baseY) * PANEL_W;
  LiquidMemo memo;
  for (int px = px0; px < px1; px++, a++, c++) {
    const int al = *a; if (!al) continue;
    int covT = LUT_alphaT16[al];
    if (MODE == 0) { covT = covT * scaleT >> 8; if (covT <= 0) continue; }
    uint16_t col = *c;
    const uint16_t bg = __builtin_bswap16(fb[px]);
    if (MODE >= 2) col = memo.get(bg, col, covT, T, C, MODE == 3);
    fb[px] = __builtin_bswap16(covT >= 256 ? col : blend565T(bg, col, covT));
  }
}
// Fractional refraction shift: destination column cx samples taps (cx, cy), (cx-1, cy), (cx, cy-1),
// (cx-1, cy-1) of one plane (weights 1/65536, taps outside the glyph are 0); the colour is the heaviest
// tap's, ties resolved in that order (as the generic path).
// Zero rows stand in for taps outside the glyph (a glyph is at most 128 columns wide in the draw, see gw).
static const uint8_t ZERO_A[256] = {}; static const uint16_t ZERO_C[256] = {};
template <int MODE>
static void __attribute__((noinline)) spriteRunFrac(const Tube &t, int y, int px0, int px1, int cx, int cy, const uint8_t *aP, const uint16_t *cP,
                                                    int w, int h, int w00, int w10, int w01, int w11, int scaleT, int T, int C) {
  const bool r0 = cy >= 0 && cy < h, r1 = cy - 1 >= 0 && cy - 1 < h;
  const uint8_t *a0 = r0 ? aP + cy * w : ZERO_A, *a1 = r1 ? aP + (cy - 1) * w : ZERO_A;
  const uint16_t *c0 = r0 ? cP + cy * w : ZERO_C, *c1 = r1 ? cP + (cy - 1) * w : ZERO_C;
  const int wz = r0 || r1 ? w : 256;   // zero rows: any column reads 0
  // The left taps of column cx are the right taps of cx - 1: carry them, two loads per pixel.
  int p0 = cx >= 1 && cx - 1 < wz ? a0[cx - 1] : 0, p1 = cx >= 1 && cx - 1 < wz ? a1[cx - 1] : 0;
  uint16_t *const fb = t.FB + (y - t.baseY) * PANEL_W;
  LiquidMemo memo;
  for (int px = px0; px < px1; px++, cx++) {
    const int n0 = cx < wz ? a0[cx] : 0, n1 = cx < wz ? a1[cx] : 0;
    const int a00 = n0 * w00, a10 = p0 * w10, a01 = n1 * w01, a11 = p1 * w11;
    p0 = n0; p1 = n1;
    const int al = (a00 + a10 + a01 + a11 + 32768) >> 16; if (!al) continue;
    int covT = LUT_alphaT16[al];
    if (MODE == 0) { covT = covT * scaleT >> 8; if (covT <= 0) continue; }
    int m = a00; if (a10 > m) m = a10; if (a01 > m) m = a01; if (a11 > m) m = a11;
    uint16_t col = m == a00 ? c0[cx] : m == a10 ? c0[cx - 1] : m == a01 ? c1[cx] : c1[cx - 1];
    const uint16_t bg = __builtin_bswap16(fb[px]);
    if (MODE >= 2) col = memo.get(bg, col, covT, T, C, MODE == 3);
    fb[px] = __builtin_bswap16(covT >= 256 ? col : blend565T(bg, col, covT));
  }
}
// Pixels a surface band may touch: the generic compositor, texel by texel (plane per pixel as before).
static void __attribute__((noinline)) spriteRunSlow(const Mark &mark, const ScaledGlyph &g, int y, int ry, int px0, int px1, int cx, int cy,
                                                    bool frac, int w00, int w10, int w01, int w11) {
  for (int px = px0; px < px1; px++, cx++) {
    const bool L = mark.inLiquid(px, ry);
    const uint8_t *aP = L ? g.aw : g.a; const uint16_t *cP = L ? g.cw : g.c;
    int al; uint16_t col;
    if (!frac) { al = aP[cy * g.w + cx]; if (!al) continue; col = cP[cy * g.w + cx]; }
    else {
      auto tap = [&](int tx, int ty) -> int { return tx < 0 || ty < 0 || tx >= g.w || ty >= g.h ? 0 : aP[ty * g.w + tx]; };
      const int a00 = tap(cx, cy) * w00, a10 = tap(cx - 1, cy) * w10, a01 = tap(cx, cy - 1) * w01, a11 = tap(cx - 1, cy - 1) * w11;
      al = (a00 + a10 + a01 + a11 + 32768) >> 16; if (!al) continue;
      int m = a00; if (a10 > m) m = a10; if (a01 > m) m = a01; if (a11 > m) m = a11;
      col = m == a00 ? cP[cy * g.w + cx] : m == a10 ? cP[cy * g.w + cx - 1] : m == a01 ? cP[(cy - 1) * g.w + cx] : cP[(cy - 1) * g.w + cx - 1];
    }
    mark(px, y, col, LUT_alphaT16[al]);
  }
}

// One glyph row of one copy (dry: unshifted, wet: shifted by the integer part of the parallax): panel
// columns [px0, px1) map to glyph columns from cx0; cut into runs and blit.
struct SpriteRow {
  const Tube &t; const Mark &mark; const ScaledGlyph &g; int y, ry;
  int Li, Hi;            // this row's liquid interval [Li, Hi) in panel x (empty when Hi <= Li)
  int nb; int b0[2], b1[2];   // possible surface-band footprints on this row, sorted, half-open
  int w00, w10, w01, w11, liqMode, Tuse;
  void run(int px0, int px1, int cx0, int cy, bool frac) const {
    if (px0 < 0) { cx0 += -px0; px0 = 0; }
    if (px1 > PANEL_W) px1 = PANEL_W;
    for (int k = 0; k < nb && px0 < px1; k++) {   // band footprints: the slow path there, plain runs between
      if (b1[k] <= px0) continue;
      if (b0[k] > px0) { const int e = b0[k] < px1 ? b0[k] : px1; plain(px0, e, cx0, cy, frac); cx0 += e - px0; px0 = e; }
      if (px0 < px1) {
        const int e = b1[k] < px1 ? b1[k] : px1;
#ifdef DIGIT_PROF
        t.prof[6] += e - px0; t.prof[7]++;
#endif
#ifdef DIGIT_PROF
        const uint32_t c0 = esp_cpu_get_cycle_count();
#endif
        spriteRunSlow(mark, g, y, ry, px0, e, cx0, cy, frac, w00, w10, w01, w11); cx0 += e - px0; px0 = e;
#ifdef DIGIT_PROF
        t.profCyc[1] += esp_cpu_get_cycle_count() - c0;
#endif
      }
    }
    if (px0 < px1) plain(px0, px1, cx0, cy, frac);
  }
  void plain(int px0, int px1, int cx0, int cy, bool frac) const {
    if (mark.onTop) { seg<0>(px0, px1, cx0, cy, frac, false, 256); return; }
    const int dT = t.pal.dryT[ry];
    if (Hi <= Li || px1 <= Li || px0 >= Hi) { seg<0>(px0, px1, cx0, cy, frac, false, dT); return; }
    if (px0 < Li) { seg<0>(px0, Li, cx0, cy, frac, false, dT); cx0 += Li - px0; px0 = Li; }
    const int e = Hi < px1 ? Hi : px1;
    if (liqMode == 1) seg<1>(px0, e, cx0, cy, frac, true, 256);
    else if (liqMode == 3) seg<3>(px0, e, cx0, cy, frac, true, 256);
    else seg<2>(px0, e, cx0, cy, frac, true, 256);
    cx0 += e - px0; px0 = e;
    if (px0 < px1) seg<0>(px0, px1, cx0, cy, frac, false, dT);
  }
  template <int MODE>
  void seg(int px0, int px1, int cx0, int cy, bool frac, bool L, int scaleT) const {
    if (px0 >= px1) return;
    const uint8_t *aP = L ? g.aw : g.a; const uint16_t *cP = L ? g.cw : g.c;
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
    t.prof[(frac ? 4 : 2) + (MODE ? 1 : 0)] += px1 - px0; t.prof[7]++;
#endif
#ifdef DIGIT_PROF
    const uint32_t c0 = esp_cpu_get_cycle_count();
#endif
    if (!frac) spriteRunInt<MODE>(t, y, px0, px1, aP + cy * g.w + cx0, cP + cy * g.w + cx0, scaleT, Tuse, mark.Cin);
    else spriteRunFrac<MODE>(t, y, px0, px1, cx0, cy, aP, cP, g.w, g.h, w00, w10, w01, w11, scaleT, Tuse, mark.Cin);
#ifdef DIGIT_PROF
    t.profCyc[0] += esp_cpu_get_cycle_count() - c0;
#endif
  }
};

void Tube::drawSpriteGlyph(const ScaledGlyph &g, int x, int y0, int yTop, const Labels &lb, const Warp &warp, const Mark &mark) const {
  if (lb.vertical) x -= g.w - lb.bh;   // the baked shadow margin lies below the body as read: left of it on the panel
  const int sourceTop = yTop - y0, gw = g.w > 128 ? 128 : g.w;
  const int ix = (int)ffloor(lb.wetDx), iy = (int)ffloor(lb.wetDy);
  const int wx1 = (int)((lb.wetDx - ix) * 256 + 0.5f), wx0 = 256 - wx1, wy1 = (int)((lb.wetDy - iy) * 256 + 0.5f), wy0 = 256 - wy1;
  const bool frac = wx1 != 0 || wy1 != 0;
  // Column ranges of the two copies from the wet shares (generic path: dcol / wcol): the dry copy on the
  // columns before the first and after the last one with any liquid, the wet copy on the shifted columns that
  // are liquid on every row (an interval: the rows' intervals intersected), one extra wet column for the
  // fractional overhang. Every other column is under a meniscus and takes drawRampColumn (a share-0 column
  // between two meniscus ones included: there it draws what the dry copy would). A column shows one image.
  int dA0 = 0, dA1 = 0, dB0 = gw, dB1 = gw, w0 = 0, w1 = frac ? gw + 1 : gw;
  if (!warp.all()) {
    while (dA1 < gw && warp(x + dA1) == 0) dA1++;
    if (dA1 < gw) while (warp(x + dB0 - 1) == 0) dB0--;   // stops at dA1, whose share is > 0
    int a = w0; while (a < w1 && warp(x + ix + a) != 256) a++;
    int b = a; while (b < w1 && warp(x + ix + b) == 256) b++;
    w0 = a; w1 = b;
  }
  // under a meniscus: every column the scaled shift can reach that neither copy draws (shares strictly between,
  // or 0 between two such columns)
  const int xr0 = x + (ix < 0 ? ix : 0), xr1 = x + gw + (lb.wetDx > 0 ? (int)fceil(lb.wetDx) : 0);
  auto ramp = [&](int xd, int k) { return k != 256 && (k != 0 || (xd - x >= dA1 && xd - x < dB0)); };
  bool anyRamp = false;
  if (!warp.all()) for (int xd = xr0; xd <= xr1 && !anyRamp; xd++) anyRamp = ramp(xd, warp(xd));
  const bool anyDry = dA1 > dA0 || dB1 > dB0, anyWet = w1 > w0;
  if (!anyDry && !anyWet && !anyRamp) return;
#ifdef DIGIT_PROF
  prof[0]++;
#endif
  SpriteRow r{*this, mark, g, 0, 0, 0, 0, 0, {0, 0}, {0, 0}, wx0 * wy0, wx1 * wy0, wx0 * wy1, wx1 * wy1,
              !mark.bakedT ? 2 : mark.Cin <= 0 ? 1 : 3, mark.T};
  const int a0 = lb.dryRy0 < lb.ry0 ? lb.dryRy0 : lb.ry0, a1 = lb.dryRy1 > lb.ry1 ? lb.dryRy1 : lb.ry1;
  const BandInfo *band = mark.onTop ? nullptr : mark.edges.band;
  for (int ry = a0; ry <= a1; ry++) {
    const int y = y0 + ry;
    if (y < baseY || y >= baseY + H) continue;
    r.y = y; r.ry = ry;
#ifdef DIGIT_PROF
    prof[1]++;
#endif
    if (!mark.onTop) { r.Li = (int)fceil(mark.edges.lo[ry]); r.Hi = (int)fceil(mark.edges.hi[ry]); }
    r.nb = 0;
    if (band) {
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
    const int cyD = lb.drySourceRows[ry] - sourceTop;
    if (anyDry && ry >= lb.dryRy0 && ry <= lb.dryRy1 && cyD >= 0 && cyD < g.h) {
      if (dA1 > dA0) r.run(x + dA0, x + dA1, dA0, cyD, false);
      if (dB1 > dB0) r.run(x + dB0, x + dB1, dB0, cyD, false);
    }
    const int cy = lb.sourceRows[ry] - sourceTop - iy;
    if (anyWet && ry >= lb.ry0 && ry <= lb.ry1 && cy >= 0 && cy <= g.h) {
      if (!frac) { if (cy < g.h) r.run(x + ix + w0, x + ix + w1, w0, cy, false); }
      else r.run(x + ix + w0, x + ix + w1, w0, cy, true);
    }
  }
  if (!anyRamp) return;
  const SpriteSampler ss(g);
#ifdef DIGIT_PROF
  const uint32_t c0 = esp_cpu_get_cycle_count();
#endif
  for (int xd = xr0; xd <= xr1; xd++) { const int k = warp(xd); if (ramp(xd, k)) drawRampColumn(ss, x, xd, k, y0, yTop, lb, mark, false); }
#ifdef DIGIT_PROF
  profCyc[2] += esp_cpu_get_cycle_count() - c0;
#endif
}
void Tube::drawBitmapGlyph(const Font &f, int d, int x, int y0, int yTop, const Labels &lb, const Warp &warp, const Mark &mark) const {
  BitmapSampler s(f, d, lb);
  if (lb.shadow >= 0) drawGlyph(s, x, y0, yTop, lb, warp, mark, true);   // 1 px shadow copy offset down-right, then the body
  drawGlyph(s, x, y0, yTop, lb, warp, mark, false);
}
void Tube::drawLabels(int y0, const Labels &lb, const Warp &warp, const Mark &mark) const {
  for (int i = 0; i < lb.n; i++) {
    const Label &l = lb.list[i]; int x = l.x0, y = l.y;
    for (int k = 0; k < l.len; k++) {
      int d = l.text[k] - '0';
      if (lb.sprite) drawSpriteGlyph(lb.sprite[d], x, y0, y, lb, warp, mark);
      else drawBitmapGlyph(*lb.font, d, x, y0, y, lb, warp, mark);
      if (lb.vertical) y += l.adv[k] + lb.gap; else x += l.adv[k] + lb.gap;
    }
  }
}

// wetRows/dryRows: source-row tables behind liquid vs behind air, blended by a tick's wet share (wetShare,
// built by drawTube for these edges); edges null = all wet. Parallax is liquid-only.
void Tube::drawTicks(int y0, const Params &p, int ticksN, const int16_t *wetRows, const int16_t *dryRows,
                     const Edges *edges, const Mark &mark, float dxFull, float dyFull) const {
  bool minutes = ticksN == 60;
  if (!(minutes ? p.ticksM : p.ticksH)) return;
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
  int embT = alphaT(clampf(p.tickEmboss, 0, 1));
  auto embossShare = [&](const Params &pp, int share) { return alphaT(clampf(pp.tickEmboss, 0, 1) * (share * (1 / 256.0f))); };   // sim emboss * share / 256
  bool emboss = p.tickEmboss > 0;
  auto drawSegment = [&](int x0, int w, uint16_t c, int rangeA, int rangeB, bool top, float k) {
    if (rangeB < 0) return;
    float dx = dxFull * k, dy = dyFull * k;
    int outer = top ? 0 : H - 1;
    int inner = top ? rangeB : rangeA; if (inner < 0) inner = 0; if (inner >= H) inner = H - 1;
    int dir = inner >= outer ? 1 : -1;
    float radius = fmx(1, (H - 1) / 2.0f), centre = (H - 1) / 2.0f;
    // x fractional, rows whole: each row of the tick at its subpixel position, edge columns antialiased (sim drawTicks).
    auto point = [&](int baseY, float &x, int &y) {
      float qy = (baseY - centre) / radius;
      float depth = sqrtf(fmx(0, 1 - qy * qy));
      x = x0 + dx * depth; y = baseY + (int)jround(dy * depth);
    };
    auto plot = [&](int x, int ry) {
      if (ry < 0 || ry >= H) return;
      if (emboss) { mark(x - 1, y0 + ry, c, embT, 1); mark(x + w, y0 + ry, c, embT, -1); }
      for (int k = 0; k < w; k++) mark(x + k, y0 + ry, c);
    };
    auto plotF = [&](float xf, int ry) {
      if (ry < 0 || ry >= H) return;
      const int x = (int)ffloor(xf), fT = (int)jround((xf - x) * 256);
      if (fT == 0 || fT == 256) { plot(x + (fT >> 8), ry); return; }
      const int a = 256 - fT;   // left share of the edge columns; fT the right one
      if (emboss) {
        mark(x - 1, y0 + ry, c, embossShare(p, a), 1); mark(x, y0 + ry, c, embossShare(p, fT), 1);
        mark(x + w, y0 + ry, c, embossShare(p, a), -1); mark(x + w + 1, y0 + ry, c, embossShare(p, fT), -1);
      }
      mark(x, y0 + ry, c, a);
      for (int k = 1; k < w; k++) mark(x + k, y0 + ry, c);
      mark(x + w, y0 + ry, c, fT);
    };
    // Without parallax every segment is vertical: no lens-depth or line interpolation needed.
    if (dx == 0 && dy == 0) {
      for (int ry = outer;; ry += dir) {
        plot(x0, ry);
        if (ry == inner) break;
      }
      return;
    }
    float px0; int py0; point(outer, px0, py0); plotF(px0, py0);
    if (outer == inner) return;
    for (int baseY = outer + dir;; baseY += dir) {
      float px1; int py1; point(baseY, px1, py1);
      int n = abs(py1 - py0); if (n < 1) n = 1;
      if (n == 1) plotF(px1, py1);   // one row on (also preserves repeated rows)
      else for (int j = 1; j <= n; j++) plotF(px0 + (px1 - px0) * j / n, (int)jround(py0 + (float)(py1 - py0) * j / n));
      px0 = px1; py0 = py1;
      if (baseY == inner) break;
    }
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
  int rng[2][2][4];   // [wet][major][topA, topB, botA, botB]
  for (int wi = 0; wi < 2; wi++) for (int mj = 0; mj < 2; mj++) {
    const int16_t *rows = wi ? wetRows : dryRows; int h = mj ? hMaj : hMin;
    if (h <= 0) continue;
    if (wi && follow) { followRange(rc.tickEdge[minutes][mj], 256, rng[wi][mj][0], rng[wi][mj][1], rng[wi][mj][2], rng[wi][mj][3]); continue; }
    warpedRange(rows, 0, h - 1, rng[wi][mj][0], rng[wi][mj][1]); warpedRange(rows, H - h, H - 1, rng[wi][mj][2], rng[wi][mj][3]);
  }
  const bool flip = p.vertical && p.remaining;   // the scale runs from the top (right) end
  for (int i = step; i < ticksN; i += step) {
    int xc = (int)jround((float)i * L / ticksN); if (flip) xc = L - xc;
    bool major = majorEvery > 0 && i % majorEvery == 0;
    int h = major ? hMaj : hMin; if (h <= 0) continue;
    int w = major ? wMaj : wMin, x0 = xc - ((w - 1) >> 1); uint16_t c = major ? cMaj : cMin;
    const int share = Warp(edges ? wetShare : nullptr)(xc);
    int topA, topB, botA, botB;
    if (share == 0 || share == 256) { const int *R = rng[share ? 1 : 0][major ? 1 : 0]; topA = R[0]; topB = R[1]; botA = R[2]; botB = R[3]; }
    else if (follow) followRange(rc.tickEdge[minutes][major], share, topA, topB, botA, botB);
    else {   // across the meniscus: the tick's own source rows (sim drawTicks)
      int16_t rows[TUBE_HEIGHT_MAX];
      for (int ry = 0; ry < H; ry++) rows[ry] = (int16_t)blendRow(dryRows[ry], wetRows[ry], share);
      warpedRange(rows, 0, h - 1, topA, topB); warpedRange(rows, H - h, H - 1, botA, botB);
    }
    const float k = share * (1 / 256.0f);   // air refracts nothing: the parallax grows with the wet share
    if (pos != 1) drawSegment(x0, w, c, topA, topB, true, k);
    if (pos != 0) drawSegment(x0, w, c, botA, botB, false, k);
  }
}

// ---------------------------------------------------------------------------------------------
// fizz
// ---------------------------------------------------------------------------------------------
static inline float frand() { return (esp_random() >> 8) / 16777216.0f; }
static inline float fizzR(const Params &p, float v) { return p.fizzSize / 2 * (1 + (v - 1) * p.fizzSizeVar); }
static inline float fizzWall(const Params &p) { return p.glassWall > 0 ? fmx(1, p.glassWall) : 0; }   // band px per side (buildPalette wallU)
// Row where a bubble of size v is fully behind the wall band (respawn/turnaround bound); 3 px without a band.
static inline float fizzHideY(const Params &p, float v) { float w = fizzWall(p); return w > 0 ? fmx(0, w - fizzR(p, v)) : 3; }
// Random row with the whole bubble in the bore, so bubbles never sit half behind the wall.
static inline float fizzSpawnY(const Params &p, int H, float v) { float lo = fizzWall(p) + fizzR(p, v), hi = H - lo; return hi <= lo ? H / 2.0f : lo + frand() * (hi - lo); }
// Surface front `surf` (liquid frame) at float row y, in u = side * x: where a parked bubble's centre sits.
static float foamFront(const float *surf, int H, float y, int side) {
  const float yc = clampf(y, 0, H - 1); const int i = (int)ffloor(yc), j = i + 1 < H ? i + 1 : H - 1;
  return side * (surf[i] + (surf[j] - surf[i]) * (yc - i));
}
// Furthest centre (in u = side * x) a bubble of radius r at row y can take with its whole disc inside the
// surface `surf` (liquid frame): the tightest row of the disc. See sim discFit.
static float discFit(const float *surf, int H, float y, float r, int side) {
  const int a = (int)fmx(0, fceil(y - r)), b = (int)fmn(H - 1, ffloor(y + r));
  if (a > b) return foamFront(surf, H, y, side) - r;
  float u = INFINITY;
  for (int iy = a; iy <= b; iy++) { const float dy = iy - y; u = fmn(u, side * surf[iy] - sqrtf(fmx(0, r * r - dy * dy))); }
  return u;
}
// A free bubble f (radius r) touching foam parked on `side` — not foam on the other edge, nor foam this tick is
// still to release (its life still carries the old side).
static bool touchesFoam(const Tube &t, const Fizz &f, float r, const Params &p, int side) {
  for (int j = 0; j < t.fizzN; j++) {
    const Fizz &g = t.fizz[j];
    if (g.life * side <= 0) continue;
    const float m = r + fizzR(p, g.v) + 0.5f, dx = g.x - f.x, dy = g.y - f.y;
    if (fabsf(dx) < m && fabsf(dy) < m && dx * dx + dy * dy < m * m) return true;
  }
  return false;
}
// Respawn x in the liquid of the bubble's (new) row: at < 0 random, 0 just inside the time edge, > 0 just
// inside the home edge (the side the flow comes from). See sim stepFizz respawn.
static void fizzRespawnX(const Tube &t, const Params &p, Fizz &f, int at) {
  const float r = fizzR(p, f.v);
  const float lo = -discFit(t.fizzSurfL, t.H, f.y, r, -1) + FOAM_CATCH, hi = discFit(t.fizzSurf, t.H, f.y, r, 1) - FOAM_CATCH;
  f.x = hi <= lo ? (lo + hi) / 2 : at < 0 ? lo + frand() * (hi - lo) : at > 0 ? lo : hi;
}
// Spring (fizzSource 1): a new size and depth, born at the spring — fizzSourceY across the bore (whole disc
// inside), fizzSourceX along that row's liquid (between the surfaces, as a respawn) as it sits at home, so
// fizzShift px back in a slug that slid away — each axis jittered by up to ±fizzSourceSpread px, kept in the
// liquid. See sim springSpawn.
static void springSpawn(const Tube &t, const Params &p, Fizz &f) {
  f.v = 0.5f + frand(); f.z = frand(); f.life = 0;
  const float r = fizzR(p, f.v), s = p.fizzSourceSpread, lo = fizzWall(p) + r, hi = t.H - lo;
  f.y = hi <= lo ? t.H / 2.0f : clampf(lo + p.fizzSourceY * (hi - lo) + (2 * frand() - 1) * s, lo, hi);
  const float xl = -discFit(t.fizzSurfL, t.H, f.y, r, -1) + FOAM_CATCH, xh = discFit(t.fizzSurf, t.H, f.y, r, 1) - FOAM_CATCH;
  f.x = xh <= xl ? (xl + xh) / 2 : clampf(xl + p.fizzSourceX * (xh - xl) - t.fizzShift + (2 * frand() - 1) * s, xl, xh);
}
// Scattered birth: a new size and depth anywhere in the liquid. See sim stepFizz scatter.
static void fizzScatter(const Tube &t, const Params &p, Fizz &f) {
  f.life = 0; f.v = 0.5f + frand(); f.y = fizzSpawnY(p, t.H, f.v); fizzRespawnX(t, p, f, -1); f.z = frand();
}
// A spring's bubble leaving or popping: its slot goes idle until the cadence fills it.
static inline void fizzFree(Fizz &f) { f.v = 0; f.life = 0; }
// This spring birth in tube t comes from the spring itself (covered by the liquid), not scattered. See sim springBirth.
static inline bool springBirth(const Tube &t) { return t.springScatter <= 0 || frand() >= t.springScatter; }
// Bubbles a column of `len` px holds: fizzCount is a full tube's, up to doubled by shaking; past the fixed pool it
// is capped and reported (fizzOverflow). See sim fizzWant.
static int fizzWant(const Params &p, float len, float agitation) {
  int want = (int)ffloor(p.fizzCount * (len / L) * (1 + (agitation < 0.05f ? 0 : agitation))); if (want < 0) want = 0;
  if (want > MAX_FIZZ) { if (want > fizzOverflowPeak) fizzOverflowPeak = want; want = MAX_FIZZ; }
  return want;
}
// A spring fills its pool at its cadence instead, up to the same count (stepFizz).
void Tube::ensureFizz(const Params &p, float len, float agitation) {
  fizzLen = len;
  if (p.fizzSource == 1) return;
  const int want = fizzWant(p, len, agitation);
  while (fizzN < want) { float v = 0.5f + frand(); fizz[fizzN++] = { frand() * len, fizzSpawnY(p, H, v), v, 0, frand() }; }
  fizzN = want;
}
// Parked bubbles: sit centred on the surface front — foam floats half out of the liquid — lagging behind an
// advance (and gliding on after being caught) no faster than the rise, pushed back by a recession; slide along
// the meniscus toward the higher contact line (the corners: the foam ring) and pack, late arrivals filling the
// meniscus from its front backward. Against a closed end (glass: glassVy = the across rise px/s) the whole disc
// stays inside and the bubbles slide along the glass with the rise instead. Works in u = side * x, so the home
// edge (side -1) is the time edge mirrored. See sim settleFoam.
static int16_t foamOrder[MAX_FIZZ];   // the packing sweep order (parked, front first); one tube at a time
static void settleFoam(Tube &t, const Params &p, float speed, const float *surf, int side, float dt, bool glass, float glassVy) {
  const int H = t.H; const float wall = fizzWall(p), follow = fmn(1, FOAM_FOLLOW * dt);
  auto front = [&](float y, float r) { return glass ? discFit(surf, H, y, r, side) : foamFront(surf, H, y, side); };
  auto place = [&](Fizz &f, float u, float y) {   // in the bore and not past the front of its row
    const float r = fizzR(p, f.v), lo = wall + r, hi = H - lo;
    f.y = hi <= lo ? H / 2.0f : clampf(y, lo, hi);
    f.x = side * fmn(u, front(f.y, r));
  };
  for (int i = 0; i < t.fizzN; i++) {
    Fizz &f = t.fizz[i];
    if (f.life == 0) continue;
    const float r = fizzR(p, f.v);
    const int fy = (int)clampf(jround(f.y), 0, H - 1);
    const float tu = front(f.y, r);
    float u = side * f.x;
    u = u < tu ? u + fmn((tu - u) * follow, speed * dt) : tu;   // buoyancy: no faster than the rise
    const float slope = side * (surf[fy + 1 < H ? fy + 1 : H - 1] - surf[fy > 0 ? fy - 1 : 0]) / 2;   // px per row
    float slide = glass ? glassVy * dt : FOAM_SLIDE * speed * clampf(2 * slope, -1, 1) * dt;
    for (int j = 0; j < t.fizzN; j++) {   // touching a neighbour on the slide side: line up along the surface
      const Fizz &g = t.fizz[j];
      if (j == i || g.life == 0 || slide * (g.y - f.y) <= 0) continue;
      const float m = r + fizzR(p, g.v) + 0.5f, du = side * g.x - u, dy = g.y - f.y;
      if (du * du + dy * dy < m * m) { slide = 0; break; }
    }
    place(f, u, f.y + slide);
  }
  // Pack: pairwise relaxation swept front to back; an overlapping pair is pushed apart, clamped to the bore
  // and the front, and whatever overlap the clamps leave the rear one takes by stepping back. See sim.
  int n = 0;
  for (int i = 0; i < t.fizzN; i++) if (t.fizz[i].life != 0) foamOrder[n++] = (int16_t)i;
  for (int it = 0; it < FOAM_RELAX; it++) {
    for (int a = 1; a < n; a++) {   // insertion sort: nearly sorted from the last step
      const int16_t k = foamOrder[a]; const float uk = side * t.fizz[k].x; int b = a - 1;
      while (b >= 0 && side * t.fizz[foamOrder[b]].x < uk) { foamOrder[b + 1] = foamOrder[b]; b--; }
      foamOrder[b + 1] = k;
    }
    for (int a = 0; a < n; a++) {
      Fizz &f = t.fizz[foamOrder[a]]; const float rf = fizzR(p, f.v);
      for (int b = a + 1; b < n; b++) {
        Fizz &g = t.fizz[foamOrder[b]];
        const float m = rf + fizzR(p, g.v) + 0.5f;
        float du = side * (g.x - f.x), dy = g.y - f.y;
        if (fabsf(du) >= m || fabsf(dy) >= m || du * du + dy * dy >= m * m) continue;
        const float d = sqrtf(du * du + dy * dy), k = (m - d) / 2;
        const float nu = d > 1e-4f ? du / d : -1, ny = d > 1e-4f ? dy / d : 0;   // coincident: g (later in the sweep) steps back
        place(f, side * f.x - k * nu, f.y - k * ny);
        place(g, side * g.x + k * nu, g.y + k * ny);
        du = side * (g.x - f.x); dy = g.y - f.y;
        if (du * du + dy * dy >= m * m) continue;
        Fizz &front = du > 0 ? g : f, &rear = du > 0 ? f : g;
        place(rear, side * front.x - sqrtf(fmx(0, m * m - dy * dy)), rear.y);
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
int fizzOverflow() { return fizzOverflowPeak; }
int fizzCounts(int idx, int &foam, int &slots) {
  const Tube &t = tubes[idx & 1]; int live = 0; foam = 0; slots = t.fizzN;
  for (int i = 0; i < t.fizzN; i++) { if (t.fizz[i].v != 0) live++; if (t.fizz[i].life != 0) foam++; }
  return live;
}

void stepFizz(const Params &p, float dt, float along, float across, float agitation) {
  if (mirrored(p)) along = -along;   // fizz lives in the mirrored liquid frame (see drawTube)
  const float speed = p.fizzSpeed * (1 + 3 * agitation);
  const float up = sqrtf(fmx(0.0f, 1 - along * along - across * across));
  const float a = clampf(across * p.fizzAcrossGain, -1, 1), al = clampf(along * p.fizzDriftGain, -1, 1);
  // Vertical watch: the viewer's up is the tube's top end (+x), so the face-up rise goes along the tube, not across it.
  const float flat = up * p.fizzFlatRise; const bool V = p.vertical;
  const float vy = -speed * ((V ? 0 : (1 - fabsf(a)) * flat) + a);
  const float vxTilt = -speed * (al - (V ? (1 - fabsf(al)) * flat : 0));
  const bool spring = p.fizzSource == 1; const float wall = fizzWall(p);
  const bool hold = spring && p.fizzFoamLife > 0 && vy != 0;   // the bore wall the rise points at holds the stream
  const float letGo = hold ? dt * (1 + 3 * agitation) / p.fizzFoamLife : 0;   // per-step chance a held bubble lets go
  for (int i = 0; i < 2; i++) {
    Tube &t = tubes[i]; const float len = t.fizzLen; const int H = t.H; const int exposed = t.fizzExposed;
    if (len <= 0) continue;   // no liquid drawn yet: no surfaces
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
    for (int k = 0; k < t.fizzN; k++) {
      Fizz &f = t.fizz[k];
      if (f.v == 0) { if (!spring) fizzScatter(t, p, f); continue; }   // idle: the spring's cadence fills it below
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
      if (grip && held(f) && frand() >= letGo) f.x += vx * dt;   // held by the glass: slides along it
      else {
        const bool inBore = f.y > wlo && f.y < whi;   // not one letting go, already on the glass row
        f.y += vy * f.v * dt;
        f.x += vx * f.v * dt;
        if (grip && inBore && (vy < 0 ? f.y < wlo : f.y > whi)) {   // carried into the glass: held, or coalesces into a held bubble
          f.y = vy < 0 ? wlo : whi;
          bool merge = false;
          for (int j = 0; j < t.fizzN; j++) {
            const Fizz &g = t.fizz[j];
            if (j == k || !held(g)) continue;
            const float m = r + fizzR(p, g.v) + 0.5f, dx = g.x - f.x, dy = g.y - f.y;
            if (dx * dx + dy * dy < m * m) { merge = true; break; }
          }
          if (merge) { fizzFree(f); continue; }
        }
      }
      // Vertical exit: once fully behind the wall band, respawn fully behind the opposite one and rise out of it.
      const float hide = fizzHideY(p, f.v);
      if (f.y < hide || f.y >= H - hide) {
        if (spring) fizzFree(f);
        else { f.v = 0.5f + frand(); const float h = fizzHideY(p, f.v); f.y = vy <= 0 ? H - h : h; fizzRespawnX(t, p, f, -1); f.z = frand(); }
        continue;
      }
      // The flow carrying its rim within FOAM_CATCH of a surface (the whole disc, so big bubbles never poke
      // through), or into the foam already there (it joins at the back): at the surface the rise heads for it
      // parks (settleFoam); anywhere else it is recycled at the side the flow comes from. A bubble the flow does
      // not carry into a surface only rides it, centre held inside, floating half out like the foam.
      const bool outR = vx > 0 && f.x > discFit(t.fizzSurf, H, f.y, r, 1) - FOAM_CATCH, outL = vx < 0 && -f.x > discFit(t.fizzSurfL, H, f.y, r, -1) - FOAM_CATCH;
      if ((side > 0 && outR) || (side < 0 && outL) || (side != 0 && touchesFoam(t, f, r, p, side))) f.life = side * p.fizzFoamLife * (0.5f + frand());
      else if ((outR || outL) && spring) fizzFree(f);
      else if (outR || outL) { f.v = 0.5f + frand(); f.y = fizzSpawnY(p, H, f.v); fizzRespawnX(t, p, f, vx < 0 ? 0 : 1); f.z = frand(); }
      else f.x = fmx(-foamFront(t.fizzSurfL, H, f.y, -1), fmn(foamFront(t.fizzSurf, H, f.y, 1), f.x));
    }
    if (spring) {
      // Cadence: fizzSourceRate bubbles/s (shaking nucleates up to twice as many), each into an idle slot (the first,
      // else a new one); idle slots at the end are dropped, so the loops stay as short as the bubbles in flight.
      // The tube holds at most its fizzCount share (fizzWant, foam included): at it a birth waits for a bubble to
      // leave, keeping one birth of credit and no more, so a stream the tilt keeps in the liquid (a drift that
      // stalls or keeps reversing) thins out instead of filling the pool, and no burst follows. Bubbles already
      // over a count that dropped (a shorter column) live on. See sim.
      const int cap = fizzWant(p, len, agitation);   // <= MAX_FIZZ: a slot is always there below it
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
    if (side != 0) settleFoam(t, p, speed, side > 0 ? t.fizzSurf : t.fizzSurfL, side, dt, glass, vy);
  }
}

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
  const ContactLeads cl = contactLeads(p, len, tilt);
  const float R = cl.R, rad = (float)M_PI / 180, PI = (float)M_PI;
  // the held ring's lead inside the band, back to its angle (lead = R·tan(pi/4 - theta/2))
  float th = PI / 2 - 2 * atanf(clampf(cl.rest - pin, cl.adv, cl.rec) / R);
  float dyn = fmx(0, p.contactDyn) * rad, g = dyn * dyn * dyn / FILM_FULL_PX_S;
  th = cbrtf(clampf(th * th * th + g * lineV, 0, PI * PI * PI));
  float lc = fmx(0.1f, p.capLength), Rmm = R * MM_PER_PX;
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

  // Tube back and cached edge geometry, before the residue backing and liquid body.
  const int16_t *capX0 = rc.capX0;
  for (int ry = 0; ry < H; ry++) {
    float ex = edgeX(ry, xe, tanR, capR);
    float exL = p.freeLiquid ? edgeXL(ry, xs, tanL, capL) : 0;
    edges[ry] = ex; edgesL[ry] = exL;
    fizzSurf[ry] = ex - xs; fizzSurfL[ry] = exL - xs;   // surface fronts for stepFizz (foam parks on the profile)
    hspan(y0 + ry, 0, L, pal.tubeBackRows[ry]);
  }

  // Residue and wet film form the backing UNDER the liquid. Paint them first, then
  // blend the body AA over that backing once. Masking residue by (1 - coverage)
  // over an already-AA body leaks the bare tube colour at their junction.
  if (traceMode) {
    const float hw = softW * 0.5f;
    const int N = p.wetFilm > 0 ? (int)fmx(1, jround(p.wetFilm)) : 0;
    const bool bandR = hasLiquid && N > 0 && s.filmFree > 0.02f;
    const bool bandL = hasLiquid && N > 0 && p.freeLiquid && s.filmHome > 0.02f;
    const float invSoftW = softW > 0 ? 1.0f / softW : 0.0f;
    const float invN = N > 0 ? 1.0f / N : 0.0f, invBW = 1.0f / (softW > 1 ? softW : 1);
    // film thickness per edge (eta * follower) and its visibility, fading out with the follower from 0.2 to
    // the 0.02 gate (see sim: a tangent row sees a vanishing film at full chord)
    const float eta = filmEta(p), etaR = bandR ? eta * s.filmFree : 0.0f, etaL = bandL ? eta * s.filmHome : 0.0f;
    const float visR = bandR ? ease((0.2f - s.filmFree) * (1.0f / 0.18f)) : 0.0f, visL = bandL ? ease((0.2f - s.filmHome) * (1.0f / 0.18f)) : 0.0f;
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
    const float ZR = fmx(1, 2 * dR), ZL = fmx(1, 2 * dL), invZR = 1.0f / ZR, invZL = 1.0f / ZL;
    const int depLo = mir ? L - st.traceHi : st.traceLo, depHi = mir ? L - st.traceLo : st.traceHi;
    auto nearDep = [depLo, depHi](float e0, float e1, float z) { return depHi > depLo && depLo < e1 + z + 4 && depHi > e0 - z - 4; };
    const bool shearR = hasLiquid && dR >= 0.125f && nearDep(eR0, eR1, ZR);
    const bool shearL = hasLiquid && p.freeLiquid && dL >= 0.125f && nearDep(eL0, eL1, ZL);
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
      for (int x = c0; x < c1; x++) traceRaw[x] = st.trace[mir ? L - 1 - x : x];
      int aLo = 65535, aHi = 0;   // path coefficient band of the span (traceFillRow's LUT)
      // +-4 px triangular blur before the streak texture (see sim): tapers the smear's outer end
      // (dense turnaround deposit next to bare glass) into a tide mark instead of a 1-px cliff. The streak
      // scatters the coat's thickness; A = eta (2 - eta) 2^16 is the column's film path coefficient
      for (int x = a0; x < a1; x++) {
        uint32_t acc = 5u * traceRaw[x];
        for (int d = 1; d <= 4; d++) {
          const int m = x < d ? 0 : x - d, q2 = x > L - 1 - d ? L - 1 : x + d;
          acc += (uint32_t)(5 - d) * (traceRaw[m] + traceRaw[q2]);
        }
        const float v = acc * (1.0f / 25.0f);
        const float eta = FILM_ETA_MAX * fmx(v * (1.0f / TRACE_FULL), filmV) * traceStreak(x + (uint32_t)idx * 6151u);
        const int ta = (int)(eta * (2 - eta) * 65536.0f + 0.5f);
        traceA[x] = (uint16_t)ta;
        if (ta) { if (ta < aLo) aLo = ta; if (ta > aHi) aHi = ta; }
      }
      const int G = (int)(p.traceAmount * 256 + 0.5f);   // stain depth gain 1/256
      for (int ry = 0; ry < H; ry++) {
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
        traceFillRow(row, traceA, a0, pl1, tint, aLo, aHi, traceLut);
        traceFillRow(row, traceA, pr0, a1, tint, aLo, aHi, traceLut);
        if (zl0 > pl1) traceShearRow(row, traceA, a0, a1, pl1, zl0, tint, exL, true, shL, invZL);
        if (pr0 > zr1) traceShearRow(row, traceA, a0, a1, zr1, pr0, tint, ex, false, shR, invZR);
        // a row with no shear and no film up: the zone is only the soft ramp over plain residue
        const bool rowPlain = shL == 0 && shR == 0 && !bandL && !bandR;
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
              if (T > 0) px(x, y, tint.at(T));
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
            if (T > 0) px(x, y, tint.at(T));
          }
        }
      }
    }
  }

  // Local backing per row and edge for the convex nose (3e): first pixel past the soft ramp, before the
  // body and glow paint it, plus the first pixel of the 3c wet film. See sim.
  if (hasLiquid) {
    const float hw = softW * 0.5f, yc = (H - 1) / 2.0f;
    const bool film3c = !traceMode && p.wetFilm > 0;
    for (int ry = 0; ry < H; ry++) {
      const int y = y0 + ry; const float d = (ry - yc) / yc, rowW = 0.4f + 0.6f * d * d;
      const int xr = (int)ffloor(edges[ry] + hw - 0.5f) + 1, xl = (int)fceil(edgesL[ry] - hw - 0.5f) - 1;
      uint16_t bR = xr >= 0 && xr < L && inStrip(xr, y) ? rd(xr, y) : pal.tubeBackRows[ry];
      uint16_t bL = xl >= capX0[ry] && xl < L && inStrip(xl, y) ? rd(xl, y) : pal.tubeBackRows[ry];
      if (film3c && s.filmFree > 0.02f && jround(p.wetFilm * s.filmFree) > 0) bR = blend565(bR, pal.rows[ry], 0.35f * s.filmFree * rowW);
      if (film3c && p.freeLiquid && s.filmHome > 0.02f && jround(p.wetFilm * s.filmHome) > 0) bL = blend565(bL, pal.rows[ry], 0.35f * s.filmHome * rowW);
      backR[ry] = bR; backL[ry] = bL;
    }
  }

  // Liquid body and its soft edge, over the residue backing.
  for (int ry = 0; ry < H; ry++) {
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
      rampRowR(row, a0, aEnd, ex, hw, invW, invGlow, glow, p.glowStrength, lightK, x0, solidLo, solidHi,
               traceMode, pal.tubeBackRows[ry], pal.rows[ry]);
      int b0 = (int)ffloor(exL - hw - 0.5f) + 1;
      int bEnd = glow ? (int)ffloor(exL - hw - 0.5f - p.edgeGlow) : b0;  // home edge: glow to the left
      rampRowL(row, (int)fceil(exL + hw - 0.5f) - 1, bEnd, exL, hw, invW, invGlow, glow, p.glowStrength, lightKL, x0, xi,
               solidLo, solidHi, traceMode, pal.tubeBackRows[ry], pal.rows[ry]);
    } else {
      if (frac >= 0.5f) px(xi, y0 + ry, pal.rows[ry]);
      if (fracL < 0.5f && xiL >= x0) px(xiL, y0 + ry, pal.rows[ry]);
    }
  }

  // 3a: front brightening, weighted by row luma
  if (hasLiquid && p.frontBright > 0) {
    const float invFront = 1 / p.frontBright;
    const uint16_t hiC = rc.hiC;
    const uint16_t *fT = nullptr, *fTL = nullptr; const bool tab = false;
    for (int ry = 0; ry < H; ry++) {
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

  // 3b: edge glow — a few px past the edge. Hard-edge path only (edgeSoft = 0); with a soft
  // edge the glow is folded into the step-3 per-pixel alpha.
  if (hasLiquid && p.edgeSoft <= 0 && p.edgeGlow > 0 && p.glowStrength > 0) {
    const float invGlow = 1 / p.edgeGlow;
    const uint16_t *gT = traceMode ? nullptr : effectTable(glowT[0], p, pal, gen, lightK, true);
    const uint16_t *gTL = !traceMode && p.freeLiquid ? effectTable(glowT[1], p, pal, gen, lightKL, true) : nullptr;
    const bool tab = gT && (!p.freeLiquid || gTL);
    for (int ry = 0; ry < H; ry++) {
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

  // 3c: wet film left by a receding edge (see sim step 3c). In trace mode the film is the wet band
  // of 3d instead (full liquid at the edge, thinning into the residue), so this faint one is skipped.
  if (!traceMode && hasLiquid && p.wetFilm > 0 && (s.filmFree > 0.02f || (p.freeLiquid && s.filmHome > 0.02f))) {
    const float yc = (H - 1) / 2.0f;
    for (int ry = 0; ry < H; ry++) {
      float d = (ry - yc) / yc, rowW = 0.4f + 0.6f * d * d;
      int nR = (int)jround(p.wetFilm * s.filmFree), nL = p.freeLiquid ? (int)jround(p.wetFilm * s.filmHome) : 0;
      int xg = softW > 0 ? (int)fceil(edges[ry] + softW * 0.5f - 0.5f) : (int)fceil(edges[ry]);
      int xgL = softW > 0 ? (int)ffloor(edgesL[ry] - softW * 0.5f - 0.5f) : (int)ffloor(edgesL[ry]);
      for (int k = 0; k < nR; k++) if (xg + k < L) pxa(xg + k, y0 + ry, pal.rows[ry], 0.35f * s.filmFree * rowW * (1 - (float)k / nR));
      for (int k = 0; k < nL; k++) if (xgL - k >= capX0[ry]) pxa(xgL - k, y0 + ry, pal.rows[ry], 0.35f * s.filmHome * rowW * (1 - (float)k / nL));
    }
  }

  // 4: highlight inset
  if (hasLiquid && p.highlightInset > 0) {
    int hiTop = highlightTop(p, s.light);
    for (int ry = hiTop; ry < hiTop + p.highlightH && ry < H; ry++) {
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

  // 3e: meniscus surface, over residue and the inset highlight. Concave bands grade from
  // a dark inner shoulder to a lit rim with subpixel coverage; convex noses shade inward.
  // Alpha-over blends the stroke over the actual smear. Both branches fade as the ring
  // meets the profile. See sim step 3e. No extra buffers or allocations.
  for (int ry = 0; ry < H; ry++) {
    strokeR[ry] = strokeL[ry] = 0;
    bandFill[0][ry] = bandFill[1][ry] = bandBlick[0][ry] = bandBlick[1][ry] = bandRim[0][ry] = bandRim[1][ry] = 0;
  }
  float strokeA = 0, pullR = 0, pullL = 0, veilA = 0;   // the stroke's opacity; receding pull per edge; foam veil opacity
  if (hasLiquid && p.surfaceBand > 0) {
    const float hw = softW * 0.5f, transK = clampf(p.liquidTransparency, 0, 1);
    // opaque from surfaceBand ~0.6 whatever the light; the unlit edge gets a darker stroke; motion
    // never fades it, only reshapes the dish through TubeState.cap (see sim)
    strokeA = fmn(1, 1.6f * p.surfaceBand);
    // dynamic contact angle: a receding line (~0° by half the full-film speed) is liquid thinning into
    // its film — liquid colour, no shoulder or rim; instantaneous edge speed, so both are back once the
    // line stops (see sim)
    const float recede = mir ? 1 : -1;
    pullR = clampf(2 * recede * (s.fillVel + s.slugVel) / FILM_FULL_PX_S, 0, 1);
    pullL = p.freeLiquid ? clampf(-2 * recede * s.slugVel / FILM_FULL_PX_S, 0, 1) : 0.0f;
    // interior opacity of the dish (surfaceFill; rim and blick keep their own) and the blick's per-row
    // weight: a tent centred at the light angle's highlight row, BLICK_H of the tube tall (see sim blickRow)
    const float fill = clampf(p.surfaceFill, 0, 1);
    veilA = FOAM_VEIL * strokeA * fill;
    const float yc = (H - 1) / 2.0f, blickY = yc - yc * sinf(s.light * (float)M_PI / 180), blickInvH = 1 / fmx(2, BLICK_H * H);
    auto blickRow = [&](int ry) -> float {
      return p.surfaceBlick > 0 ? p.surfaceBlick * fmx(0, 1 - fabsf(ry - blickY) * blickInvH) : 0.0f; };
    const uint16_t hiC = rc.hiC;
    auto tone = [&](uint16_t c) -> uint16_t { return rc.toneT > 0 ? blend565T(c, rc.toneC, rc.toneT) : c; };
    auto surface = [&](int ry, float xm, float xw, int dir, float lk, int xlo, int xhi) -> float {
      const int y = y0 + ry; const float tw = dir * (xw - xm);   // ring lead in the edge's own outward sense
      if (tw == 0) return 0;
      const float lo = fmn(xm, xw), hi = fmx(xm, xw);   // pixel centres in [lo, hi)
      int x0 = (int)fceil(lo - 0.5f), x1 = (int)fceil(hi - 0.5f); if (x0 < xlo) x0 = xlo; if (x1 > xhi) x1 = xhi;
      if (tw > 0) {   // concave: shaded surfaceWidth-px band, clipped to the wall ring
        // Overlap the body's AA ramp so it joins the shoulder without a bare-glass seam.
        const float a = strokeA * fmn(1, tw);
        if (a < 1 / 255.0f) return 0;   // below visible opacity: no stroke, rim or band for the marks
        const float shade = 0.6f * (1 - fmn(1, lk));   // unlit edge: toward the deep liquid colour
        const uint16_t inner = tone(blend565(pal.rows[ry], rc.darkC, 0.3f));
        const uint16_t outer = tone(blend565(blend565(rc.lensC, pal.rows[ry], 0.2f), rc.darkC, shade));
        const float wEff = fmn(p.surfaceWidth, tw);
        const float invWidth = 1 / (wEff + hw);
        const float pull = dir > 0 ? pullR : pullL;
        const float blickK = blickRow(ry) * fmn(1, lk) * (1 - pull);
        // the ring is a thin liquid lens: lit (light side, row shaded) over a dark back, a deep liquid tone
        // at light-independent opacity over a light one; backK blends the two (sim rimK / rimC). Float
        // mixes once per row, like the sim's blend565.
        const float backK = fmn(1, luma(to888(pal.tubeBackRows[ry])) / 255.0f);
        const float rimK = p.surfaceRim * fmn(1, wEff / 2) * (1 - pull) * ((1 - backK) * (0.5f + 0.5f * pal.rowK[ry]) * fmn(1, lk) + backK);
        const uint16_t rimC = q(mix(to888(hiC), to888(q(mix(to888(pal.rows[ry]), to888(rc.darkC), 0.75f))), backK));
        const int side = dir > 0 ? 0 : 1;   // layer weights for the rear-mark compositor (Mark::bandMark)
        bandFill[side][ry] = a * fill; bandBlick[side][ry] = a * blickK; bandRim[side][ry] = a * rimK;
        // Pixel-footprint coverage for the stroke and rim; no integer-column snapping. See sim.
        const float cLo = dir > 0 ? xm - hw : xm - wEff, cHi = dir > 0 ? xm + wEff : xm + hw;
        int xa = (int)ffloor(cLo), xb = (int)fceil(cHi); if (xa < xlo) xa = xlo; if (xb > xhi) xb = xhi;
        bandRow(FB + ry * PANEL_W, xa, xb, xm, dir, hw, wEff, invWidth, a, fill, blickK, pull, rimK, inner, outer, pal.rows[ry], hiC, rimC);
        return wEff;
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
        return 0;
      }
    };
    for (int ry = 0; ry < H; ry++) {
      int xi = (int)ffloor(edges[ry]), xa = (int)ffloor(edgesL[ry]) + 1; if (xa < capX0[ry]) xa = capX0[ry];
      strokeR[ry] = surface(ry, edges[ry], wallX(ry, xe, tanR, capR), 1, lightK, xa, L);
      if (p.freeLiquid) strokeL[ry] = surface(ry, edgesL[ry], wallXL(ry, xs, tanL, capL), -1, lightKL, capX0[ry], xi);
    }
  }

  // Panel-frame column bounds for the mark compositor (liquid where lo <= x < hi): the body only. The
  // concave band past it is composited per pixel by its own layer opacities (Mark::bandMark, render
  // frame), so a faint or receding band never hides a mark as liquid and there is no threshold (see sim).
  const BandInfo band{{edges, edgesL}, {strokeR, strokeL}, {bandFill[0], bandFill[1]}, {bandBlick[0], bandBlick[1]},
                      {bandRim[0], bandRim[1]}, {pullR, pullL}, softW * 0.5f, mir, L};
  Edges bounds{boundLo, boundHi, hasLiquid && p.surfaceBand > 0 ? &band : nullptr};
  for (int ry = 0; ry < H; ry++) {
    float lo = edgesL[ry], hi = edges[ry];
    if (mir) {
      uint16_t *row = FB + ry * PANEL_W;
      for (int a = 0, b = L - 1; a < b; a++, b--) { uint16_t t = row[a]; row[a] = row[b]; row[b] = t; }
      boundLo[ry] = L - hi; boundHi[ry] = L - lo;
    } else { boundLo[ry] = lo; boundHi[ry] = hi; }
  }
  if (!p.ticksOnTop || !p.digitsOnTop) buildWetShare(bounds, H, wetShare, wetRun);

  // Scale marks, all before bubbles.
#ifdef DIGIT_PROF
  uint32_t profT = esp_timer_get_time();
#endif
  bool haveLabels = layoutLabels(y0, p, gen, ticksN, st.acrossTilt, st.edgeLight, st.fillTarget, labels);
#ifdef DIGIT_PROF
  prof[8] = esp_timer_get_time() - profT; profT = esp_timer_get_time();
#endif
  auto drawTickLayer = [&](bool onTop) {
    if (p.ticksOnTop == onTop) {
      Mark tickMark(*this, y0, bounds, p, onTop, p.markContrast * p.tickBright);
      float dx = onTop ? 0 : -st.edgeLight * p.tickParallax;
      float dy = onTop ? 0 : st.acrossTilt * p.tickParallax;
      drawTicks(y0, p, ticksN, rc.tickWet, onTop ? rc.tickWet : rc.tickDry, onTop ? nullptr : &bounds, tickMark, dx, dy);
    }
  };
  auto drawDigitLayer = [&](bool onTop) {
    if (haveLabels && p.digitsOnTop == onTop) {
      const bool baked = labels.sprite && labels.shadow >= 0;
      float floorC; uint16_t floorR; floorBake(p, floorC, floorR);
      Mark digitMark(*this, y0, bounds, p, onTop, p.markContrast * p.digitBright, baked, baked && floorC > 0);
      drawLabels(y0, labels, Warp(onTop ? nullptr : wetShare), digitMark);
    }
  };
  drawTickLayer(false);
#ifdef DIGIT_PROF
  prof[9] = esp_timer_get_time() - profT; profT = esp_timer_get_time();
#endif
  drawDigitLayer(false);
#ifdef DIGIT_PROF
  prof[10] = esp_timer_get_time() - profT;
#endif
  auto mapX = [&](int x) { return mir ? L - 1 - x : x; };
  auto span = [&](int y, int xa, int xb, uint16_t c) {
    if (mir) hspan(y, L - 1 - xb, L - xa, c);
    else hspan(y, xa, xb + 1, c);
  };

  // 5: fizz — AA discs, pre-squashed by the local lens magnification (see sim step 5)
  if (p.fizz) {
    const float *mag = rc.mag;
    const uint16_t blickC = q({255 * p.brightness, 255 * p.brightness, 255 * p.brightness});   // sim blickC
    // Highlight row (continuous, from the light angle): the core shifts away from it, the pinpoint toward it (see sim).
    const float yHi = (H - 1) / 2.0f * (1 - sinf(st.light * (float)M_PI / 180));
    const float lxS = -0.7f, lxSign = mir ? -1.0f : 1.0f;   // light from screen-left; liquid frame mirrored under remaining
    const float invHalfH = 2.0f / H;   // one division per tube, not per bubble
    for (int k = 0; k < fizzN; k++) {
      const Fizz &f = fizz[k];
      if (f.v == 0) continue;   // idle slot
      int fy = (int)clampf(jround(f.y), 0, H - 1);
      // Centres stay inside this frame's surfaces (the stepper ran on an older one, so a receding surface pushes
      // them back here): whatever touches a surface floats at most half out of it, like the foam.
      const float fx = fmx(-foamFront(fizzSurfL, H, f.y, -1), fmn(foamFront(fizzSurf, H, f.y, 1), f.x));
      // A parked bubble in its last FOAM_POP_T s pops: swells and fades out, breaking the surface.
      const float pop = f.life != 0 && fabsf(f.life) < FOAM_POP_T ? fabsf(f.life) / FOAM_POP_T : 1;
      const float r = fizzR(p, f.v) * (1 + 0.6f * (1 - pop));
      // Seen through liquid in proportion to its depth: a deeper bubble fades toward the liquid (see sim).
      const float depthK = 1 - p.fizzDepth * f.z * (1 - p.liquidTransparency);   // rim/pinpoint: colour mix toward the body (sim cRimD / cBlickD); interior tint: alpha scale
      const float m = fizzMag(mag, H, f.y, r), ry = r / m, off = fmn(r * p.fizzShadeOff, r - 1);   // core shift, centre kept in the disc (sim)
      // Light direction in unsquashed disc space (liquid frame): x fixed toward screen-left, y toward the highlight row.
      const float ly = clampf((yHi - f.y) * invHalfH, -1, 1), nrm = rsqrtApprox(lxS * lxS + ly * ly);   // sim: exact 1/sqrt; <= 2.1e-7 rel.
      const float dirX = lxSign * lxS * nrm, dirY = ly * nrm;
      const float rIn = r - 0.5f, rOut = r + 0.5f, kc = r - 1;   // ring 1 px at its thinnest; the offset only shifts the core
      DiscRow d;
      d.fx = fx; d.r = r; d.offX = -dirX * off; d.offY = -dirY * off; d.kc = kc;   // dark core shifted away from the light
      // Specular pinpoint on the lit side (r >= 2.5, fizzBlick > 0).
      d.blick = r >= 2.5f && p.fizzBlick > 0;
      if (d.blick) {
        const float bk = 0.4f * (r - 1), rb = fmx(0.6f, r * 0.25f), rbIn = rb - 0.5f;
        d.blickK = p.fizzBlick; d.bX = dirX * bk; d.bY = dirY * bk; d.rbOut = rb + 0.5f;
        d.bIn2 = rbIn * rbIn * (1 - 1e-4f); d.bOut2 = d.rbOut * d.rbOut * (1 + 1e-4f); d.cBlick = depthK < 1 ? blend565(pal.rows[fy], blickC, depthK) : blickC;   // specular, depth-tinted (sim cBlickD)
      } else { d.blickK = d.bX = d.bY = d.rbOut = d.bIn2 = d.bOut2 = 0; d.cBlick = 0; }
      d.in2 = rIn >= 1 ? rIn * rIn * (1 - 1e-4f) : -1; d.out2 = rOut * rOut * (1 + 1e-4f);
      d.core = r >= 1.5f && kc > 0; d.core2Lo = kc * kc * (1 - 1e-4f); d.core2Hi = kc * kc * (1 + 1e-4f);
      d.veilA = veilA; d.pullR = pullR; d.pullL = pullL;
      d.mirror = mir; d.xsI = xsI; d.L = L; d.tintA = p.bubbleDark * depthK;   // sim tintA
      const int ixa = (int)ffloor(fx - r - 1), ixb = (int)fceil(fx + r);
      for (int iy = (int)ffloor(f.y - ry - 1); iy <= (int)fceil(f.y + ry); iy++) {
        if (iy < 0 || iy >= H) continue;
        d.wallT = pal.dryT[iy] / 256.0f * pop;   // bubbles live in the bore: invisible where the ray only sees the wall band
        if (d.wallT <= 0) continue;
        // Past the profile a bubble is seen through the concave band's front-glass wedge, thickest at the
        // profile and gone at the band's outer rim.
        d.sR = fizzSurf[iy]; d.sL = fizzSurfL[iy]; d.bR = strokeR[iy]; d.bL = strokeL[iy];   // stroke widths: 0 where no band is drawn
        d.veilLo = d.bR > 0 ? (int)ffloor(d.sR) : INT_MAX; d.veilHi = d.bL > 0 ? (int)fceil(d.sL) : INT_MIN;   // ix + 1 > sR  <=>  ix >= floor(sR); ix < sL  <=>  ix < ceil(sL)
        d.dy = (iy + 0.5f - f.y) * m;
        d.cRim = depthK < 1 ? blend565(pal.rows[iy], pal.bubbleRimRows[iy], depthK) : pal.bubbleRimRows[iy];
        discRow(FB + iy * PANEL_W, ixa, ixb, d);
      }
    }
  }

  // 6: bubble
  if (p.bubble) {
    float bx = xe - p.bubbleGap - s.edgeLight * p.bubbleTiltGain, by = (H - 1) * p.bubbleY - (H - 1) / 2.0f * s.acrossTilt * p.bubbleRollGain;
    float rx = p.bubbleW / 2, ry_ = p.bubbleH / 2;
    if (bx - rx > xs + 2) {
      for (int yy = (int)ffloor(by - ry_); yy <= (int)fceil(by + ry_); yy++) {
        float dy = (yy - by) / ry_;
        if (fabsf(dy) > 1) continue;
        float hw = sqrtf(1 - dy * dy) * rx;
        int xa = (int)jround(bx - hw), xb = (int)jround(bx + hw);
        int ryi = yy < 0 ? 0 : yy > H - 1 ? H - 1 : yy;
        span(y0 + yy, xa, xb, pal.bubbleIn[ryi]);
        px(mapX(xa), y0 + yy, pal.bubbleRim); px(mapX(xb), y0 + yy, pal.bubbleRim);
      }
      int yt = (int)jround(by - ry_), yb = (int)jround(by + ry_);
      span(y0 + yt, (int)jround(bx - rx * 0.45f), (int)jround(bx + rx * 0.45f), pal.bubbleRim);
      span(y0 + yb, (int)jround(bx - rx * 0.45f), (int)jround(bx + rx * 0.45f), pal.bubbleRim);
    }
  }
  drawTickLayer(true);
  if (lensRowsOut && !(haveLabels && p.digitsOnTop)) *lensRowsOut = rc.lensOn ? rc.lensSrc : nullptr;   // the push applies it
  else applyLens(p);
  drawDigitLayer(true);
}


bool render_init() {
  buildLuts();
  bool ok = true;
  for (int i = 0; i < 2; i++) {
    tubes[i].set.poolC = (uint16_t *)heap_caps_malloc(GLYPH_POOL_PX * 2, GLYPH_POOL_CAPS);
    tubes[i].set.poolA = (uint8_t *)heap_caps_malloc(GLYPH_POOL_PX, GLYPH_POOL_CAPS);
    tubes[i].set.poolS = (uint8_t *)heap_caps_malloc(GLYPH_SPAN_BYTES, MALLOC_CAP_SPIRAM);
    tubes[i].wetShare = (uint16_t *)heap_caps_malloc(PANEL_W * sizeof(uint16_t), MALLOC_CAP_SPIRAM);
    tubes[i].wetRun = (int16_t *)heap_caps_malloc((PANEL_W + 1) * sizeof(int16_t), MALLOC_CAP_SPIRAM);
    tubes[i].digitOff = (float *)heap_caps_malloc(2 * TUBE_HEIGHT_MAX * sizeof(float), MALLOC_CAP_SPIRAM);
    ok = ok && tubes[i].set.poolC && tubes[i].set.poolA && tubes[i].set.poolS && tubes[i].wetShare && tubes[i].wetRun && tubes[i].digitOff;
  }
  FILM_PHI = (uint16_t *)heap_caps_malloc(257 * sizeof(uint16_t), MALLOC_CAP_SPIRAM);
  FILM_LG = (uint16_t *)heap_caps_malloc(256 * sizeof(uint16_t), MALLOC_CAP_SPIRAM);
  FILM_EX = (uint8_t *)heap_caps_malloc(4096, MALLOC_CAP_SPIRAM);
  ok = ok && FILM_PHI && FILM_LG && FILM_EX;
  if (FILM_PHI && FILM_LG && FILM_EX) buildFilmLuts();
  return ok;
}

// Safe to call for idx 0 and 1 concurrently from different tasks: each touches only tubes[idx] and its
// own strip; params / state are read-only for the duration of the call.
void renderTube(int idx, const TubeState &s, const Params &p, uint32_t gen, uint16_t *strip, const int16_t **lensRows) {
#ifdef DIGIT_PROF
  memset(tubes[idx].prof, 0, sizeof(tubes[idx].prof)); memset(tubes[idx].profCyc, 0, sizeof(tubes[idx].profCyc));
#endif
  Tube &t = tubes[idx & 1];
  TubeLayout lay = tubeLayout(p);
  t.FB = strip; t.H = lay.H; t.baseY = idx == 0 ? lay.yH : lay.yM; t.idx = idx & 1;
  t.lensRowsOut = lensRows; if (lensRows) *lensRows = nullptr;
  t.buildRowCache(p, gen);
  Palette &pal = t.pal;
  if (!(pal.valid && pal.gen == gen && pal.H == t.H && pal.light == s.light)) {
    t.buildPalette(p, s.light, pal);
    pal.valid = true; pal.gen = gen; pal.H = t.H; pal.light = s.light;
  }
  t.drawTube(t.baseY, s, p, gen, idx == 0 ? 12 : 60);
}

#ifdef DIGIT_PROF
const uint32_t *render_profile(int idx) { return tubes[idx].prof; }
const uint32_t *render_profile_cycles(int idx) { return tubes[idx].profCyc; }
#endif
