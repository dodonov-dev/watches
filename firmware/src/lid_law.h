// The desk-view lid's liquid (docs/lid-fill/model.md): sim/src/lidLaw.ts in float32, operation for operation and in the
// same order (the sim rounds with Math.fround after every operation of its sample loop). tools/check_lid_law.py holds
// the two sides to the same numbers (the tables bit for bit when the samples start from the sim's trig; lidOpacity /
// lidWet bit for bit on the same tables).
// A ray to lid position u (0 the front contact line .. 1 the back one) meets the dish (a spherical cap of radius
// R / cos(theta), sheared onto the level plane), a share F mirrors off (Fresnel), the rest refracts and runs through the
// liquid to the wall it runs to (the back one; at extreme poses the front one): opacity keep(u) (1 - t^(q lam(u))), lam
// the path / 2R on the centre plane, q the row's chord.
// Include after fizz_light.h (its FIZZ_ATT table and fizzAtt, fizzMn / fizzMx). No double anywhere: the constants are
// float literals or double expressions folded to float by the compiler. lidLawBuild runs when the pose's step (lidKey) or
// the look changes (flash, noinline; 0.14-0.2 ms on the S3): its roots by LID_SQRT (default
// sqrtf; an includer's override must round correctly). render.cpp keeps sqrtf: its inline sqrtExact here (six copies),
// or out of line, moved GCC's inlining across the unit (an IRAM band kernel lost an inlined blend565T, a fizz kernel
// grew 108 B; 2026-11-27, lcd316@320w8-8). lidOpacity / lidWet per
// pixel take + - * /, compares and the tables only. Build with -ffp-contract=off (or the optimize attribute) to keep the
// sim's roundings.
#pragma once
#include "fizz_light.h"
#ifndef LID_SQRT
#define LID_SQRT sqrtf
#endif

#define LID_N 32                          // samples over u: LID_N + 1 entries
#define LID_NW ((float)(4.0 / 3))         // water against air (sim F(4 / 3))
#define LID_RW 0.75f                      // 1 / n (exact)
// The law is built for the pose in steps of 1 / LID_KEY_STEPS rad, re-keyed when the pose leaves its step by more than
// LID_KEY_HOLD of one (the IMU's noise at rest would rebuild it every frame). surfaceBand's share of the absorption:
// min(1, stroke opacity / LID_BAND_FULL) (sim LID_BAND_FULL, a double literal: (float)0.16 as Math.fround'd).
#define LID_KEY_STEPS 128
#define LID_KEY_HOLD_F ((float)(0.6 / LID_KEY_STEPS))   // sim F(LID_KEY_HOLD / LID_KEY_STEPS)
#define LID_BAND_FULL ((float)0.16)

// lam[i]: the liquid path / 2R under lid position u = i / LID_N on the centre row; keep[i]: 1 - the share the surface
// mirrors of the dry tube back; k8: -8 ln t; inv1t: 1 / (1 - t), 0 for t ~ 1 (sim LidLaw).
struct LidLaw { float lam[LID_N + 1], keep[LID_N + 1]; float k8, inv1t; };

// The sample loop from the pose's trig (tanT = tan tau, tanD = tan delta, sd / cd = sin / cos delta) and the cap's radius
// A = 1 / cos theta (bore radius 1). The sim's double literals as float tests that answer the same for every float:
// (float)1e-3 is the first float above 1e-3, so x < -1e-3 (double) is x <= -1e-3f; (float)1e-6 is the last float below
// 1e-6, so max(1e-6, x) and fizzMx(1e-6f, x) differ only below 1e-6f, where both roots round to the same float (1e-3f;
// A^2 - z^2 >= A^2 - 1 > 0.13 here anyway).
static inline void lidLawSamples(LidLaw &o, float tanT, float tanD, float sd, float cd, float A) {
  const float T = tanT + tanD;
  const float A2 = A * A, hm = A - LID_SQRT(A2 - 1);
  const float xF = hm - T, W = 2 * T;           // the front line's screen x, the lid's height
  const float xRing = hm + tanT;                // the back contact ring on the back wall (tube x)
  const float dx = -sd, dz = -cd;               // the ray, from the eye
  const float a = 1 + T * T;
  float zPrev = 1;
  for (int i = 0; i <= LID_N; i++) {
    const float u = (float)i / LID_N, xs = xF + u * W, b = A - xs;
    // the dish at screen x: (1 + T^2) z^2 - 2 b T z + b^2 - A^2 = 0, its lower root
    const float bT = b * T, disc = bT * bT - a * (b * b - A2);
    float z = zPrev;
    if (disc >= 0) { const float zz = (bT - LID_SQRT(disc)) / a; z = fizzMx(-1, fizzMn(1, zz)); }
    if (z > zPrev) z = zPrev;                   // monotone toward the back
    zPrev = z;
    const float s = LID_SQRT(fizzMx(1e-6f, A2 - z * z));
    const float x = (A - s) - z * tanT;         // the surface point (tube frame)
    const float fp = z / s - tanT, nn = 1 / LID_SQRT(1 + fp * fp), nx = nn, nz = -fp * nn;
    const float ci = fizzMx(0, -(dx * nx + dz * nz));
    // Fresnel, air to water
    const float s2 = (LID_RW * LID_RW) * (1 - ci * ci), ct = LID_SQRT(fizzMx(0, 1 - s2));
    const float rs = (ci - LID_NW * ct) / (ci + LID_NW * ct), rp = (ct - LID_NW * ci) / (ct + LID_NW * ci);
    const float fr = (rs * rs + rp * rp) * 0.5f;
    // refracted ray to the back wall z = -1
    const float k = LID_RW * ci - ct, tx = LID_RW * dx + k * nx, tz = LID_RW * dz + k * nz;
    const float lz = z + 1;
    // its path / 2R to the wall it runs to: the back wall, at extreme poses the front one; along the tube it never leaves
    // the liquid (4: opaque). tz > 1e-3 (double) is tz >= 1e-3f, as above; a NaN keeps 4, as in the sim
    const float tl = 0.5f * LID_SQRT(tx * tx + tz * tz);
    float lam = 4;
    if (tz <= -1e-3f) lam = (lz / -tz) * tl;
    else if (tz >= 1e-3f) lam = ((1 - z) / tz) * tl;
    o.lam[i] = fizzMn(4, lam);
    // the mirror ray: toward the dry back wall above the ring it shows the tube back (weight ramps in over 0.15 R)
    const float mx = dx + (2 * ci) * nx, mz = dz + (2 * ci) * nz;
    float dry = 0;
    if (mz <= -1e-3f) { const float xm = x + lz * (mx / -mz); dry = fizzMx(0, fizzMn(1, (xm - xRing) * (float)(1 / 0.15))); }
    o.keep[i] = 1 - fr * dry;
  }
  // never less liquid nearer the front line (a ray that enters at the front wall itself, toward it, has no path of its own)
  for (int i = LID_N - 1; i >= 0; i--) if (o.lam[i] < o.lam[i + 1]) o.lam[i] = o.lam[i + 1];
}
// tau: the stand's back tilt, delta: the eye above the screen normal (rad, lidAngles); thetaDeg: contactAngle;
// transparency: liquidTransparency. Float transcendentals (the sim takes double ones and rounds: an ulp apart at most).
// t < 0.999 (double) is t < 0.999f: (float)0.999 is the first float above 0.999. The floor 0.01 (double in the sim):
// (float)0.01 is below it, but -8 ln and 1 / (1 - t) round to the same floats from either (36.841362, 1.0101010).
static void __attribute__((noinline, optimize("fp-contract=off"))) lidLawBuild(LidLaw &o, float tau, float delta, float thetaDeg, float transparency) {
  const float t = fizzMx(0.01f, fizzMn(1, transparency));
  o.k8 = -8 * logf(t); o.inv1t = t < 0.999f ? 1 / (1 - t) : 0;
  const float th = fizzMx(20, fizzMn(89, thetaDeg)) * (float)(M_PI / 180);   // concave dishes; 90 = flat
  const float A = 1 / cosf(th);
  lidLawSamples(o, tanf(tau), tanf(delta), sinf(delta), cosf(delta), A);
}
// floor without the libm call (render.cpp ffloor): |x| >= 2^23 is already integral (or inf / NaN)
static inline float lidFloor(float x) {
  if (!(fabsf(x) < 8388608.0f)) return x;
  const float t = (float)(int)x;
  return t > x ? t - 1 : t;
}
// The step an angle takes from its last key (sim lidKey; NaN: none yet, keyed afresh): the key while the angle stays
// within LID_KEY_HOLD of a step of it, else the nearest step, floor(a 128 + 0.5) / 128 (x 128 and / 128 exact in float:
// the sim's roundings, one at the + 0.5).
static inline float lidKey(float angle, float key) {
  if (fabsf(angle - key) <= LID_KEY_HOLD_F) return key;
  return lidFloor(angle * LID_KEY_STEPS + 0.5f) * (1.0f / LID_KEY_STEPS);
}
// The table at u in 0..1 (sim at()).
static inline float lidAt(const float *tab, float u) {
  const float v = fizzMx(0, fizzMn(1, u)) * LID_N;
  int i = (int)v; if (i > LID_N - 1) i = LID_N - 1;
  const float f = v - (float)i;
  return tab[i] + (tab[i + 1] - tab[i]) * f;
}
// The liquid's opacity over the tube back at lid position u; q = the row's chord share z_R / R.
static inline float lidOpacity(const LidLaw &o, float q, float u) {
  return lidAt(o.keep, u) * (1 - fizzAtt(o.k8 * q, lidAt(o.lam, u)));
}
// The share of "seen through the whole liquid" a rear mark takes under the lid at u: (1 - t^lam) / (1 - t), the path
// itself for a clear liquid.
static inline float lidWet(const LidLaw &o, float q, float u) {
  const float l = q * lidAt(o.lam, u);
  return fizzMn(1, o.inv1t > 0 ? (1 - fizzAtt(o.k8, l)) * o.inv1t : l);
}
