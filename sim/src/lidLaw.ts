// The desk-view lid's liquid (docs/lid-fill/model.md; firmware/src/lid_law.h is the same maths in float32).
// The lid is the free surface seen from above: a ray to lid position u (0 the front contact line .. 1 the back one)
// meets the meniscus, a little of it mirrors off (Fresnel), the rest refracts and runs through the liquid to the back
// wall, where the tube back shows. So the liquid's opacity there is 1 - t^(path / 2R), t = liquidTransparency: an
// absorbing liquid reads as itself from the front line on and thins out to the backing at the back line, a clear one
// stays a faint wedge. The surface is the renderer's own dish: a spherical cap of radius R / cos(theta) (theta =
// contactAngle) sheared onto the level plane, traced on the centre plane; other rows scale the path by their chord.
// Built when the pose or the look changes (a square root or two a sample), read per pixel by one interpolation.
const F = Math.fround;
export const LID_N = 32;                     // samples over u: LID_N + 1 entries
/** The law is built for the pose in steps of 1 / LID_KEY_STEPS rad, re-keyed when the pose leaves its step by more than
 *  LID_KEY_HOLD of one (the IMU's noise at rest would rebuild it every frame: ~0.15 ms a tube on the S3). Steps of
 *  1 / 1024 rad (0.056 deg): near a grazing refracted ray the path is steep in the pose, and 1 / 128 rad steps showed as
 *  jumps there (review 2: tau -44.5 deg, e 20, theta 89: 33/255). lidKey: the step an angle takes from its last key
 *  (NaN: none yet). Firmware lidKey. */
export const LID_KEY_STEPS = 1024, LID_KEY_HOLD = 0.6;
export function lidKey(angle: number, key: number): number {
  const a = F(angle);
  if (Math.abs(F(a - key)) <= F(LID_KEY_HOLD / LID_KEY_STEPS)) return key;   // (a NaN key fails the test: keyed afresh)
  return F(Math.floor(F(F(a * LID_KEY_STEPS) + 0.5)) / LID_KEY_STEPS);
}
/** surfaceBand's share of the liquid under the lid: the whole absorption from a stroke opacity of LID_BAND_FULL on (a
 *  surfaceBand of 0.1), fading with it to nothing below (surfaceBand 0 is no lid at all: no jump on the way there). */
export const LID_BAND_FULL = 0.16;
const NW = F(4 / 3), RW = F(0.75);           // water against air
const ATT_N = 64;                            // exp(-i / 8) by the float32 recurrence of fizzLight.ts / fizz_light.h
const ATT: Float32Array = (() => { const t = new Float32Array(ATT_N + 2), c = F(0.8824969); t[0] = 1; for (let i = 1; i <= ATT_N + 1; i++) t[i] = F(t[i - 1] * c); return t; })();
/** exp(-v / 8) for v >= 0 (0 past the table). */
function att8(v: number): number {
  if (!(v < ATT_N)) return 0;
  const i = Math.trunc(v), f = F(v - i);
  return F(ATT[i] + F(F(ATT[i + 1] - ATT[i]) * f));
}

/** lam[i]: the liquid path / 2R under lid position u = i / LID_N on the centre row; keep[i]: 1 - the share the surface
 *  mirrors of the dry tube back above the liquid (the same colour as what the liquid lets through, so it only thins the
 *  liquid's opacity); k8: 8 x the optical depth of a bore diameter, -8 ln t; inv1t: 1 / (1 - t), 0 for t ~ 1. */
export interface LidLaw { lam: Float32Array; keep: Float32Array; k8: number; inv1t: number; hm: number }   // hm: the meniscus rise at the wall / R
export const newLidLaw = (): LidLaw => ({ lam: new Float32Array(LID_N + 1), keep: new Float32Array(LID_N + 1), k8: 0, inv1t: 0, hm: 0 });
/** The back contact band: the meniscus climbing the back wall, seen from above. Its width px is LID_RIM_K of the
 *  meniscus rise hm R (R tan(45 deg - theta / 2): 3.5 px at theta 70 on a 20 px bore, so 1.2 px; more wetting, a taller
 *  meniscus, a wider band), between LID_RIM_MIN (the old hairline) and LID_RIM_MAX. The key light's reflection on the
 *  meniscus (surfaceBlick) is a crescent of the same width just in front of it. Firmware lidRimW. */
export const LID_RIM_K = 0.35, LID_RIM_MIN = 0.5, LID_RIM_MAX = 3;
export function lidRimW(o: LidLaw, R: number): number {
  return Math.max(LID_RIM_MIN, Math.min(LID_RIM_MAX, F(F(o.hm * F(R)) * F(LID_RIM_K))));
}
/** tau: the stand's back tilt, delta: the eye above the screen normal (rad, lidAngles); thetaDeg: contactAngle;
 *  transparency: liquidTransparency. Trig and a log here only; the samples take + - x /, sqrt and clamps. */
export function lidLawBuild(o: LidLaw, tau: number, delta: number, thetaDeg: number, transparency: number): void {
  const t = Math.max(0.01, Math.min(1, transparency));
  o.k8 = F(-8 * F(Math.log(t))); o.inv1t = t < 0.999 ? F(1 / F(1 - t)) : 0;
  const th = F(Math.max(20, Math.min(89, thetaDeg)) * F(Math.PI / 180));   // concave dishes; 90 = flat (a cap too wide to tell)
  const tanT = F(Math.tan(tau)), tanD = F(Math.tan(delta)), T = F(tanT + tanD);
  const sd = F(Math.sin(delta)), cd = F(Math.cos(delta));
  // bore radius 1: the cap's radius A = 1 / cos theta, its rise at the wall hm = A - sqrt(A^2 - 1)
  const A = F(1 / F(Math.cos(th))), A2 = F(A * A), hm = F(A - F(Math.sqrt(F(A2 - 1))));
  o.hm = hm;
  const xF = F(hm - T), W = F(2 * T);                 // the front line's screen x, the lid's height
  const xRing = F(hm + tanT);                         // the back contact ring on the back wall (tube x)
  const dx = F(-sd), dz = F(-cd);                     // the ray, from the eye
  const a = F(1 + F(T * T));
  let zPrev = 1;
  for (let i = 0; i <= LID_N; i++) {
    const u = F(i / LID_N), xs = F(xF + F(u * W)), b = F(A - xs);
    // the dish at screen x: (1 + T^2) z^2 - 2 b T z + b^2 - A^2 = 0; its lower root is on the cap (the other one on the
    // far side of the cap's sphere)
    const bT = F(b * T), disc = F(F(bT * bT) - F(a * F(F(b * b) - A2)));
    let z = zPrev;
    if (disc >= 0) { const zz = F(F(bT - F(Math.sqrt(disc))) / a); z = Math.max(-1, Math.min(1, zz)); }
    if (z > zPrev) z = zPrev;                         // monotone toward the back (a folded dish: the last one seen)
    zPrev = z;
    const s = F(Math.sqrt(Math.max(1e-6, F(A2 - F(z * z)))));
    const x = F(F(A - s) - F(z * tanT));              // the surface point (tube frame)
    // its normal into the air, n ~ (1, -f'), f' = z / s - tan tau
    const fp = F(F(z / s) - tanT), nn = F(1 / F(Math.sqrt(F(1 + F(fp * fp))))), nx = nn, nz = F(-fp * nn);
    const ci = Math.max(0, F(-F(F(dx * nx) + F(dz * nz))));
    // Fresnel, air to water
    const s2 = F(F(RW * RW) * F(1 - F(ci * ci))), ct = F(Math.sqrt(Math.max(0, F(1 - s2))));
    const rs = F(F(ci - F(NW * ct)) / F(ci + F(NW * ct))), rp = F(F(ct - F(NW * ci)) / F(ct + F(NW * ci)));
    const fr = F(F(F(rs * rs) + F(rp * rp)) * 0.5);
    // refracted ray to the back wall z = -1
    const k = F(F(RW * ci) - ct), tx = F(F(RW * dx) + F(k * nx)), tz = F(F(RW * dz) + F(k * nz));
    const lz = F(z + 1);
    // its path / 2R to the wall it runs to (|t| = 1 up to rounding): the back wall, at extreme poses the front one
    // (the eye far above a deep dish: review 1); along the tube it never leaves the liquid (4: opaque)
    const tl = F(F(0.5) * F(Math.sqrt(F(F(tx * tx) + F(tz * tz)))));
    let lam = 4;
    if (tz < -1e-3) lam = F(F(lz / F(-tz)) * tl);
    else if (tz > 1e-3) lam = F(F(F(1 - z) / tz) * tl);
    o.lam[i] = Math.min(4, lam);
    // the mirror ray: toward the dry back wall above the ring it shows the tube back (weight ramps in over 0.15 R);
    // lower it meets the dish again and shows liquid, back toward the viewer the room: neither thins the liquid
    const mx = F(dx + F(F(2 * ci) * nx)), mz = F(dz + F(F(2 * ci) * nz));
    let dry = 0;
    if (mz < -1e-3) { const xm = F(x + F(lz * F(mx / F(-mz)))); dry = Math.max(0, Math.min(1, F(F(xm - xRing) * F(1 / 0.15)))); }
    o.keep[i] = F(1 - F(fr * dry));
  }
  // never less liquid nearer the front line (a ray that enters at the front wall itself, toward it, has no path of its own)
  // The back contact line itself has no liquid under it, whichever way the refracted ray runs: with the ray near the
  // tube's axis (the tube tipped far forward) its entry flipped 0 <-> 4 between two pose steps and the lid's back rim
  // line with it (review 3: e 40, theta 80, tau -41.26 deg). The last cell fades to it over half a px.
  o.lam[LID_N] = 0;
  for (let i = LID_N - 1; i >= 0; i--) if (o.lam[i] < o.lam[i + 1]) o.lam[i] = o.lam[i + 1];
}
/** The table at u in 0..1. */
function at(tab: Float32Array, u: number): number {
  const v = F(Math.max(0, Math.min(1, u)) * LID_N), i = Math.min(LID_N - 1, Math.trunc(v)), f = F(v - i);
  return F(tab[i] + F(F(tab[i + 1] - tab[i]) * f));
}
/** The liquid's opacity over the tube back at lid position u; q = the row's chord share z_R / R. */
export function lidOpacity(o: LidLaw, q: number, u: number): number {
  return F(at(o.keep, u) * F(1 - att8(F(F(o.k8 * q) * at(o.lam, u)))));
}
/** The share of "seen through the whole liquid" a rear mark takes under the lid at u (0 dry .. 1 as behind the body):
 *  (1 - t^lam) / (1 - t), the path itself for a clear liquid. */
export function lidWet(o: LidLaw, q: number, u: number): number {
  const l = F(q * at(o.lam, u));
  return Math.min(1, o.inv1t > 0 ? F(F(1 - att8(F(o.k8 * l))) * o.inv1t) : l);
}
