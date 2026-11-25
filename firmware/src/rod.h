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
