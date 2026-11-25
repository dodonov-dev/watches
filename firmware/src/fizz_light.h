// Fizz lit where it is (Params::fizzPhys; docs/fizz-light/model.md): sim/src/fizzLight.ts in float32, operation for
// operation and in the same order (the sim rounds with Math.fround after every operation of the per-bubble kernel).
// tools/check_fizz_light.py holds the two sides to the same numbers (fizzLit bit for bit on the same frame).
// A bubble's ring is total internal reflection: seen along the view axis V it mirrors a cone of the surroundings within
// 82.8 deg of -V (water, n = 4/3). Four probes sample that cone, q = -mu V +- beta U / W (mu = 1 / n^2, U the tube axis,
// W across): each carries the room's light L(q) = A + (1 - A) max(0, q . l) (l: the key, world-up) through the liquid from
// where its ray first leaves it: the bore wall, the open surface, or an end. Their sum is the ring's light E (1 in a
// clear liquid), their imbalance C its bright side. The pinpoint is the key's own Fresnel reflection: one ray along l.
// No Arduino / ESP dependency. The includer may define FIZZ_SQRT (a correctly rounded float sqrt: render.cpp's
// sqrtExact, sqrtf being two out-of-line calls on the S3) before including this; default sqrtf. The per-bubble fizzLit
// takes only + - * /, FIZZ_SQRT, compares and one table (no library call); fizzLightFrame runs once a frame.
#pragma once
#include <math.h>
#include <stdint.h>
#ifndef FIZZ_SQRT
#define FIZZ_SQRT sqrtf
#endif

#define FIZZ_LIGHTS 8             // ring colour levels: the ring's mix weight K quantised to l / (FIZZ_LIGHTS - 1)
#define FIZZ_RING_KEEP 0.6f       // the core's largest shift px under fizzPhys: the ring thins toward one side, never opens
#define FIZZ_ATT_N 64             // attenuation table: exp(-tau) at tau = i / 8, 0 past 8
// The constants as the sim's Math.fround(double): a double literal rounded to float (never a float literal: the decimal
// rounded once could differ from the sim's twice-rounded value).
#define FIZZ_AMB ((float)0.35)        // the room's ambient share of the radiance
#define FIZZ_MU ((float)0.5625)       // the ring cone's probes: 1 / n^2
#define FIZZ_BETA ((float)0.8267973)  // sqrt(1 - mu^2)
#define FIZZ_INV_MU ((float)1.7777778)
#define FIZZ_F_REF 0.0463394          // (double) Fresnel reflectance at 77 deg between light and view: fizzBlick's calibration (the stand)
#define FIZZ_C_GAIN ((float)2)        // ring asymmetry: the probes' imbalance to the core's shift
#define FIZZ_NEVER ((float)1e9)       // a ray that meets no such boundary
#define FIZZ_ATT_C ((float)0.8824969) // exp(-1 / 8)

// exp(-i / 8) by the sim's float32 recurrence (FIZZ_ATT), evaluated by the compiler (IEEE single, as at run time): a
// constant table in flash (.rodata), no internal RAM, shared by every tube.
struct FizzAttTable { float v[FIZZ_ATT_N + 2]; };
static constexpr FizzAttTable fizzAttBuild() {
  FizzAttTable t{};
  t.v[0] = 1;
  for (int i = 1; i <= FIZZ_ATT_N + 1; i++) t.v[i] = t.v[i - 1] * FIZZ_ATT_C;
  return t;
}
static constexpr FizzAttTable FIZZ_ATT_T = fizzAttBuild();
#define FIZZ_ATT FIZZ_ATT_T.v
// Math.min / Math.max (a first) as compares, no calls: equal to the sim's for non-NaN arguments, signed zeros included.
static inline float fizzMn(float a, float b) { return b < a ? b : a; }
static inline float fizzMx(float a, float b) { return a < b ? b : a; }
// exp(-a8 d / 8): a8 = 8 x the optical depth a px, d >= 0 px.
static inline float fizzAtt(float a8, float d) {
  const float u = a8 * d;
  if (!(u < FIZZ_ATT_N)) return 0;   // past the table (and NaN): dark
  const int i = (int)u;
  if (i < 0) return 1;               // u <= -1: never in the sim's domain (it reads past its table there)
  const float f = u - (float)i;
  return FIZZ_ATT[i] + (FIZZ_ATT[i + 1] - FIZZ_ATT[i]) * f;
}

// A frame's light for one tube (sim FizzLight). Ring probes 0..3: +x, -x, +y, -y (each tilted back by mu); 4: the key ray.
struct FizzLight {
  float a8;              // 8 x optical depth a px: -8 ln(transparency) / 2R
  float R, R2;           // bore radius px
  float w[4];            // probe weights L_i / sum L (a clear, open tube: E = 1)
  float invS[5];         // 1 / (q . n) against the time edge's surface (0: the ray never meets it)
  float invH[5];         // the home edge's
  float ly, lz, la, invA;   // the key ray against the bore wall: its cross-section part, |.|^2 and 1 / that (0: never)
  float fk;              // the pinpoint's Fresnel factor min(1, F / F_REF)
  float hx, hy;          // the pinpoint's place per radius (liquid frame), at most 0.75
  bool openR, openL;     // the time / home surface is open to the room (else an end glass: dark)
  bool lid; float kLid;  // desk view: a foam's view path per px of clearance under the level line
  float tone;            // -1..1: the ring's tone against the liquid (> 0 a lit ring, < 0 a shade ring)
};
// A bubble's light (sim FizzLit).
struct FizzLit {
  float K;          // the ring's mix weight 0..1 (liquid .. lit rim): view transmission x the ring's light
  float cx, cy;     // the ring's thick side, liquid frame, |.| <= 1: toward the light for a lit ring, away for a shade ring
  float wl;         // the pinpoint's weight 0..1 (x fizzBlick): Fresnel x the key's path in and the view path out
  float tv;         // view transmission 0..1
  float sk;         // 0 at an open surface .. 1 from a diameter below it (the core's dark tint fades out in foam)
};

// up: the pose's unit up in the LIQUID frame (x toward the time edge); lightDeg: TubeState.light (the palette's light sits
// at 2 x that in the cross-section); lid: the desk view's lid is drawn (tau, delta its angles, rad); exposed: drawTube's
// fizzExposed bits; tone: fizzTone. Once a frame: the sim's float32 steps exactly, its Fresnel factor in double; the
// transcendentals and its other double steps (the pinpoint's place, the lid's view path) in float32 (a few ulps).
static void __attribute__((noinline)) fizzLightFrame(FizzLight &o, float transparency, float R, float upX, float lightDeg,
                                                     bool lid, float tau, float delta, int exposed, float tone) {
  const float t = fizzMx(0.01f, fizzMn(1, transparency));
  o.a8 = (-8 * logf(t)) / (2 * R);
  const float bx = fizzMx(-1, fizzMn(1, upX)), c = sqrtf(fizzMx(0, 1 - bx * bx)), a2 = (2 * lightDeg) * (float)(M_PI / 180);
  const float lx = bx, ly = -c * sinf(a2), lz = c * cosf(a2);
  const float qx[5] = {FIZZ_BETA, -FIZZ_BETA, 0, 0, lx}, qy[5] = {0, 0, FIZZ_BETA, -FIZZ_BETA, ly};
  const float qz[5] = {-FIZZ_MU, -FIZZ_MU, -FIZZ_MU, -FIZZ_MU, lz};
  float sum = 0;
  for (int i = 0; i < 4; i++) { o.w[i] = FIZZ_AMB + (1 - FIZZ_AMB) * fizzMx(0, (qx[i] * lx + qy[i] * ly) + qz[i] * lz); sum = sum + o.w[i]; }
  for (int i = 0; i < 4; i++) o.w[i] = o.w[i] / sum;
  // the time edge's surface: the level plane under the lid (normal (1, 0, tan tau)), else across the tube (the drawn meniscus)
  const float tanT = lid ? tanf(tau) : 0.0f;
  for (int i = 0; i < 5; i++) {
    const float den = qx[i] + qz[i] * tanT, denH = -qx[i];
    o.invS[i] = den > 1e-3 ? 1 / den : 0;     // the sim's double 1e-3
    o.invH[i] = denH > 1e-3 ? 1 / denH : 0;
  }
  const float a = ly * ly + lz * lz;
  // Fresnel at half the angle between light and view (V = +z), water to air: in double as the sim (in float32 the
  // factor drifted ~1e-6 relative; a dozen soft-float operations a frame)
  const double nd = 4.0 / 3, ci = sqrt(fmax(0, (1 + (double)lz) / 2)), s2 = 1 - ci * ci;
  double fr = 1;
  if (nd * nd * s2 < 1) {
    const double ct = sqrt(1 - nd * nd * s2), rs = (nd * ci - ct) / (nd * ci + ct), rp = (ci - nd * ct) / (ci + nd * ct);
    fr = (rs * rs + rp * rp) / 2;
  }
  const float n = 4.0f / 3;
  // the pinpoint sits where the bubble's normal halves light and view: r (lx, ly) / sqrt(2 (1 + lz)), kept within 0.75 r
  const float hk = 1 / sqrtf(fizzMx(1e-3f, 2 * (1 + lz))), hm = sqrtf(lx * lx + ly * ly) * hk, hc = hm > 0.75f ? 0.75f / hm : 1;
  // under the lid a foam's view ray refracts at the surface: path = clearance x cos tau / cos theta_w, sin theta_w = cos e / n
  float kLid = 0;
  if (lid) { const float sw = cosf(tau + delta) / n; kLid = cosf(tau) / sqrtf(fizzMx(0.05f, 1 - sw * sw)); }
  o.R = R; o.R2 = R * R; o.ly = ly; o.lz = lz; o.la = a; o.invA = a > 1e-6 ? 1 / a : 0;
  o.fk = (float)fmin(1, fr / FIZZ_F_REF); o.hx = lx * hk * hc; o.hy = ly * hk * hc;
  o.openR = (exposed & 1) != 0; o.openL = (exposed & 2) != 0; o.lid = lid; o.kLid = kLid; o.tone = fizzMx(-1, fizzMn(1, tone));
}
// The ring's tone from its lit colour and the liquid behind it (RGB565; liqA / liqB: the palette's rows at a quarter and
// three quarters of the tube, so a highlight band on the centre row does not count as the liquid):
// (Y_rim - (Y_a + Y_b) / 2) / 32 in 8-bit luma, -1..1. Integers until the last division (exact in float).
static inline int fizzLuma(uint16_t c) {
  const int r = (c >> 11) & 31, g = (c >> 5) & 63, b = c & 31;
  return (((r << 3) | (r >> 2)) * 77 + ((g << 2) | (g >> 4)) * 150 + ((b << 3) | (b >> 2)) * 29) >> 8;
}
static inline float fizzTone(uint16_t rim565, uint16_t liqA565, uint16_t liqB565) {
  return fizzMx(-1, fizzMn(1, (float)(2 * fizzLuma(rim565) - fizzLuma(liqA565) - fizzLuma(liqB565)) / 64));
}

// One probe's ray: the first boundary it meets (the wall at dw, the time / home surface) and whether light comes in there.
static inline float fizzRay(const FizzLight &fl, int i, float dw, float clr, float clrL) {
  float d = dw; bool m = true;
  if (fl.invS[i] > 0) { const float ds = clr * fl.invS[i]; if (ds < d) { d = ds; m = fl.openR; } }
  if (fl.invH[i] > 0) { const float dh = clrL * fl.invH[i]; if (dh < d) { d = dh; m = fl.openL; } }
  return m ? fizzAtt(fl.a8, d) : 0.0f;
}
// x: the drawn centre along the tube (liquid frame); y, z: its place in the bore's cross-section, px from the centre
// (z toward the viewer); r: radius; S / SL: the time / home surface at its row (liquid frame); B: the lid's height at its
// row (0: no lid there). Build with -ffp-contract=off to keep the sim's roundings (a fused multiply-add rounds once).
static inline void fizzLit(const FizzLight &fl, float x, float y, float z, float r, float S, float SL, float B, FizzLit &o) {
  const float a8 = fl.a8, y2 = y * y;
  const float zR = FIZZ_SQRT(fizzMx(0, fl.R2 - y2));
  const float rem = fizzMx(0, (fl.R2 - y2) - z * z);   // R^2 - y^2 - z^2
  // clearance under the time edge's surface along the tube (under the lid: the level line at its depth), over the home edge
  const bool lid = fl.lid && B > 0 && zR > 0;
  const float clr = fizzMx(0, lid ? (S + ((zR - z) * B) / (2 * zR)) - x : S - x);
  const float clrL = fizzMx(0, x - SL);
  // view path: to the front glass, or (lid) up through the surface
  float dv = fizzMx(0, zR - z);
  if (lid && fl.openR) dv = fizzMn(dv, clr * fl.kLid);
  const float tv = fizzAtt(a8, dv);
  // ring probes
  const float dwx = (zR + z) * FIZZ_INV_MU;   // +-x probes: back to the wall, (z_R + z) / mu
  const float vp = y * FIZZ_BETA - z * FIZZ_MU, vm = -y * FIZZ_BETA - z * FIZZ_MU;
  const float a0 = fl.w[0] * fizzRay(fl, 0, dwx, clr, clrL), a1 = fl.w[1] * fizzRay(fl, 1, dwx, clr, clrL);
  const float a2 = fl.w[2] * fizzRay(fl, 2, fizzMx(0, FIZZ_SQRT(vp * vp + rem) - vp), clr, clrL);
  const float a3 = fl.w[3] * fizzRay(fl, 3, fizzMx(0, FIZZ_SQRT(vm * vm + rem) - vm), clr, clrL);
  const float E = (a0 + a1) + (a2 + a3);
  // the ring's bright side: the probes' imbalance, gained to fizzShadeOff's calibration, at most 1 long
  float cx = 0, cy = 0;
  if (E > 1e-6f) {   // == the sim's E > 1e-6 (double): (float)1e-6 is below it, no float between
    const float g = FIZZ_C_GAIN / E;
    cx = (a0 - a1) * g; cy = (a2 - a3) * g;
    const float c2 = cx * cx + cy * cy;
    if (c2 > 1) { const float k = 1 / FIZZ_SQRT(c2); cx = cx * k; cy = cy * k; }
  }
  // the key ray: the lamp's own path in
  float wl = 0;
  {
    const float v = y * fl.ly + z * fl.lz;
    const float dw = fl.invA > 0 ? fizzMx(0, FIZZ_SQRT(v * v + rem * fl.la) - v) * fl.invA : FIZZ_NEVER;
    float d = dw; bool m = true;
    if (fl.invS[4] > 0) { const float ds = clr * fl.invS[4]; if (ds < d) { d = ds; m = fl.openR; } }
    if (fl.invH[4] > 0) { const float dh = clrL * fl.invH[4]; if (dh < d) { d = dh; m = fl.openL; } }
    if (m) wl = fl.fk * fizzAtt(a8, d + dv);
  }
  const float tp = fizzMx(0, fl.tone);
  o.K = tv * (1 - tp * (1 - fizzMn(1, E)));
  o.cx = cx * fl.tone; o.cy = cy * fl.tone;
  o.wl = wl; o.tv = tv;
  const float d2 = 2 * r, near = fizzMn(fl.openR ? clr : FIZZ_NEVER, fl.openL ? clrL : FIZZ_NEVER);
  o.sk = near < d2 ? near / d2 : 1;
}
