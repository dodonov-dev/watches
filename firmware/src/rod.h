// The edge shade's rod geometry (render.cpp buildShade; tools/gen_rod_rays.py runs rodRays on the build host for the
// generated ray tables, so the board and the host checks share these exact operations). Needs layout.h.
#pragma once
#include <math.h>
#include <stdint.h>
#include "layout.h"
// RodRays: ROD_RAYS rays at apparent offsets x_i = (i + 0.5) R / ROD_RAYS through one rod (immutable: one per distinct
// rod geometry, generated into flash or built once at boot): per ray sqrt(x_i / R) (r), its Fresnel transfer relative to
// the centre's (tau, tau^2) and the panel row it lands on, as the distance in rows from the tube's centre for an even
// (j[0] = floor(u)) and an odd (j[1] = floor(u + 0.5)) number of panel rows, u = |d| / pitch (ROD_NOROW past TIR).
#define ROD_RAYS 8192
#define ROD_NOROW INT16_MAX
struct RodRays { float r[ROD_RAYS], tau[ROD_RAYS], tau2[ROD_RAYS]; int16_t j[2][ROD_RAYS]; };
// The edge shade's rod (layout.h ROD_GAP_MM / ROD_N / TUBE_ROD_MM; sim render.ts rodScreen / rodFold / rodInner / rodRay /
// rodRays, the same double operations in the same order: square roots and divisions are exact roundings on both sides,
// so the two agree bit for bit; no library call). A ray leaving the rod's curved surface
// toward a viewer at infinity, at angle alpha to its normal (s = sin alpha, apparent offset R s), refracts through the
// PMMA and its flat base and lands on the pixel plane at rodScreen(s): docs/physical-tube-model.py source(R s, R, gap,
// n) with its trigonometry written out (sin / cos of the refracted angles from s alone); NaN past total internal
// reflection at the base, as source(). It grows with s to the fold (sF: the largest screen offset any ray reaches) and
// turns back: past the fold the rod shows rows from further in again, up to the TIR onset sT (the last transmitting s).
static inline double rodScreen(double s, double R, double g, double n) {
  const double s1 = s / n, c1 = sqrt(1 - s1 * s1), ca = sqrt(1 - s * s);
  const double st = s * c1 - ca * s1, ct = ca * c1 + s * s1, sa = n * st;
  if (!(sa < 1 && sa > -1)) return NAN;
  return R * s - (R * ca) * (st / ct) - g * (sa / sqrt(1 - sa * sa));
}
// s of the ray that lands at d on the rising branch [0, sF] (fixed bisection).
static inline double rodInner(double d, double R, double g, double n, double sF) {
  double lo = 0, hi = sF;
  for (int i = 0; i < 60; i++) { const double m = (lo + hi) / 2; if (rodScreen(m, R, g, n) < d) lo = m; else hi = m; }
  return (lo + hi) / 2;
}
// The rod's fixed points (fixed steps, no tolerance: the same on both sides): the TIR onset sT (the last transmitting s)
// by bisection on n sin theta < 1, the fold sF (the largest screen offset) by golden section below it.
static inline void rodFold(double R, double g, double n, double &sF, double &sT) {
  double lo = 0, hi = 1;
  for (int i = 0; i < 60; i++) {
    const double m = (lo + hi) / 2, s1 = m / n, st = m * sqrt(1 - s1 * s1) - sqrt(1 - m * m) * s1;
    if (n * st < 1) lo = m; else hi = m;
  }
  sT = lo;
  double a = 0, b = sT;
  for (int i = 0; i < 100; i++) {
    const double c = b - (b - a) * 0.6180339887498949, e = a + (b - a) * 0.6180339887498949;
    if (rodScreen(c, R, g, n) < rodScreen(e, R, g, n)) a = c; else b = e;
  }
  sF = (a + b) / 2;
}
// Fresnel power reflectances (s, p) of a lossless n1 -> n2 interface, cosines of incidence ci and transmission ct.
static inline void fresnel(double n1, double ci, double n2, double ct, double &rs, double &rp) {
  const double a = (n1 * ci - n2 * ct) / (n1 * ci + n2 * ct), b = (n2 * ci - n1 * ct) / (n2 * ci + n1 * ct);
  rs = a * a; rp = b * b;
}
// The ray at s: the panel offset it lands on (rodScreen's operations, NaN past TIR) and its direct transfer (rays from
// the viewer, unpolarised, products per polarisation): the curved surface, the PMMA -> air base and air -> cover glass
// (index ROD_N: the base's reflectances again), T2 = 1/2 sum (1 - rc)(1 - rb)^2, 0 past TIR;
// docs/edge-shade-session/astra-model.md section 1. Its cosines from s as rodScreen's (square roots and divisions).
static inline void rodRay(double s, double R, double g, double n, double &d, double &t2) {
  const double s1 = s / n, c1 = sqrt(1 - s1 * s1), ca = sqrt(1 - s * s);
  const double st = s * c1 - ca * s1, ct = ca * c1 + s * s1, sa = n * st;
  if (!(sa < 1 && sa > -1)) { d = NAN; t2 = 0; return; }
  const double cb = sqrt(1 - sa * sa);
  d = R * s - (R * ca) * (st / ct) - g * (sa / cb);
  double cs, cp, bs, bp;
  fresnel(1, ca, n, c1, cs, cp);
  fresnel(n, ct, 1, cb, bs, bp);
  t2 = 0.5 * ((1 - cs) * (1 - bs) * (1 - bs) + (1 - cp) * (1 - bp) * (1 - bp));
}
// The panel's row pitch in mm (the LCD's 320 rows / the AMOLED's own), as the canvas sees it.
static inline double shadePitch() {
#ifdef BOARD_LCD316
  const int R = LCD_PANEL_H;
#else
  const int R = PANEL_H;
#endif
  const float pxmm = PX_PER_MM;
  return (double)PANEL_H / R / (double)pxmm;
}
// The edge end (edgeShadeEnd e; render.cpp buildShade, sim render.ts rodEndCounts / edgeShadeRows, the same operations
// in the same order): extra darkness at the tube's very edge, falling off inward by the rod's side-view magnification
// (docs/edge-shade-ends/astra-model3.md sections 2 and 4). RodEnd: per row parity (of the physical span) and panel row
// group j from the tube's centre, the count of projected samples whose ray lands in that row, over 15 side views
// theta = 45 + 2.5 k deg (k 0..14), N = 2^20 midpoints x_i = R (2 (i + 0.5) / N - 1) each: a = asin(x / R),
// h = theta + a - asin(sin a / n), v = n sin h, B = x / (n cos h), d = B - g v / sqrt(1 - v^2); only the exposed
// semicircle |theta + a| <= pi/2, cos h > 0, |v| < 1, |B| <= R. The angles enter by their sines and cosines (sqrt and
// the addition theorems; the 15 tilts' as decimal literals, the same doubles in C and JS), so the counts need no
// library call; radius and pitch canonicalised to 1e-6 mm first. Groups past the table's are dropped; the odd parity's
// central group 0 counts twice (its own mirror). Immutable: one per distinct rod, generated into flash
// (tools/gen_rod_rays.py; the sim's copy sim/src/rodEndGen.ts) or counted into the boot-allocated table on first use.
#define ROD_GROUPS (TUBE_HEIGHT_MAX + 2)   // a group per panel row of half the largest tube (render.cpp RodCache)
#define ROD_END_TILTS 15
#define ROD_END_SAMPLES (1 << 20)
struct RodEnd { uint32_t c[2][ROD_GROUPS]; };
static const double ROD_END_SIN[ROD_END_TILTS] = {0.7071067811865475, 0.7372773368101241, 0.766044443118978, 0.7933533402912352,
  0.8191520442889918, 0.8433914458128857, 0.8660254037844386, 0.8870108331782217, 0.9063077870366499, 0.9238795325112867,
  0.9396926207859083, 0.9537169507482269, 0.9659258262890683, 0.9762960071199334, 0.984807753012208};
static const double ROD_END_COS[ROD_END_TILTS] = {0.7071067811865476, 0.6755902076156602, 0.6427876096865394, 0.6087614290087207,
  0.5735764363510462, 0.5372996083468239, 0.5000000000000001, 0.46174861323503386, 0.42261826174069944, 0.38268343236508984,
  0.3420201433256688, 0.30070579950427306, 0.25881904510252074, 0.2164396139381029, 0.17364817766693041};
static inline double rodCanon(double v) { return floor(v * 1e6 + 0.5) / 1e6; }
static inline void rodEndCounts(double R0, double g, double n, double pitch0, uint32_t *c0, uint32_t *c1, int groups) {
  const double R = rodCanon(R0), pitch = rodCanon(pitch0);
  for (int j = 0; j < groups; j++) c0[j] = c1[j] = 0;
  for (int k = 0; k < ROD_END_TILTS; k++) {
    const double sT = ROD_END_SIN[k], cT = ROD_END_COS[k];
    for (int i = 0; i < ROD_END_SAMPLES; i++) {
      const double x = R * (2 * (i + 0.5) / ROD_END_SAMPLES - 1), sa = x / R, ca = sqrt(1 - sa * sa);
      if (cT * ca - sT * sa < 0) continue;   // |theta + a| > pi/2: the far side of the rod
      const double sb = sa / n, cb = sqrt(1 - sb * sb), sd = sa * cb - ca * sb, cd = ca * cb + sa * sb;   // a - b
      const double sh = sT * cd + cT * sd, ch = cT * cd - sT * sd, v = n * sh;
      if (!(ch > 0) || !(v < 1 && v > -1)) continue;
      const double B = x / (n * ch);
      if (!(fabs(B) <= R)) continue;
      const double u = fabs(B - g * v / sqrt(1 - v * v)) / pitch, j0 = floor(u), j1 = floor(u + 0.5);
      if (j0 < groups) c0[(int)j0]++;
      if (j1 < groups) c1[(int)j1]++;
    }
  }
  if (groups > 0) c1[0] *= 2;
}
static inline void rodEndCounts(double R, double g, double n, double pitch, RodEnd &out) { rodEndCounts(R, g, n, pitch, out.c[0], out.c[1], ROD_GROUPS); }
#define ROD_END_UNCOUNTED UINT32_MAX   // c[0][0] of a boot-allocated table not counted yet (a count stays below 15 x 2^20)
// The weight w_r of the physical row r rows in from the tube's outermost (r = 0) of a span with `groups` groups, its
// counts C (one parity), edge-first C[r] = C(groups - 1 - r), and b the last row of the run from the edge whose
// rounded old code equals the edge's: u_0 = 1, u_r = min(9/16 u_{r-1}, C[r] / C[0]) (C[0] 0: 9/16 u_{r-1}); b >= 1:
// z = clamp((b - r) / min(2, b), 0, 1), w_r = u_r z^2 (3 - 2 z); b 0: w_0 = 1, the rest 0. Rows r >= b: 0. Fills
// w[0 .. b) (w[0] alone for b 0); the caller multiplies F_r by 1 - e^2 w_r.
static inline int rodEndWeights(const uint32_t *C, int groups, int b, double *w) {
  if (b == 0) { w[0] = 1; return 1; }
  const double c0 = C[groups - 1], zd = b < 2 ? b : 2;
  double u = 1;
  for (int r = 0; r < b; r++) {
    if (r > 0) { const double cap = 0.5625 * u, t = (double)C[groups - 1 - r] / c0; u = c0 > 0 && t < cap ? t : cap; }
    double z = (b - r) / zd; if (z > 1) z = 1;
    w[r] = u * (z * z) * (3 - 2 * z);
  }
  return b;
}
// The tube's rays (RodRays), panel rows `pitch` mm apart.
static inline void rodRays(double R, double g, double n, double pitch, RodRays &r) {
  double d0, t0; rodRay(0, R, g, n, d0, t0);
  for (int i = 0; i < ROD_RAYS; i++) {
    const double s = (i + 0.5) / ROD_RAYS;
    double d, t2; rodRay(s, R, g, n, d, t2);
    r.r[i] = (float)sqrt(s); r.tau[i] = (float)(t2 / t0); r.tau2[i] = r.tau[i] * r.tau[i];
    if (!(d == d)) { r.j[0][i] = r.j[1][i] = ROD_NOROW; continue; }
    const double u = fabs(d) / pitch, j0 = floor(u), j1 = floor(u + 0.5);
    r.j[0][i] = (int16_t)(j0 < ROD_NOROW ? j0 : ROD_NOROW); r.j[1][i] = (int16_t)(j1 < ROD_NOROW ? j1 : ROD_NOROW);
  }
}
