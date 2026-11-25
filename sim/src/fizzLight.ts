// Fizz lit where it is (params.fizzPhys; docs/fizz-light/model.md; firmware/src/fizz_light.h is the same maths in float32).
// A bubble's ring is total internal reflection: seen along the view axis V it mirrors a cone of the surroundings within
// 82.8 deg of -V (water, n = 4/3), never the viewer's side. Four probes sample that cone, q = -mu V +- beta U / W
// (mu = 1 / n^2, U the tube axis, W across): each carries the room's light L(q) = A + (1 - A) max(0, q . l) (l: the key,
// world-up) through the liquid from where its ray first leaves it: the bore wall, the open surface, or an end.
// Their sum is the ring's light E (1 in a clear liquid), their imbalance C its bright side. The pinpoint is the key's
// own Fresnel reflection: one ray along l, its weight by the angle between light and view. The view path d_v ends at
// the front glass, or under the desk view's lid at the surface.
// Pure functions of their arguments: + - x /, sqrt, clamps and one table (no exp, pow or trig per bubble).
const F = Math.fround;

/** Ring colour levels (firmware FIZZ_LIGHTS): the ring's mix weight K quantised to l / (FIZZ_LIGHTS - 1). */
export const FIZZ_LIGHTS = 8;
const AMB = F(0.35);                                    // the room's ambient share of the radiance
const MU = F(0.5625), BETA = F(0.8267973);              // the ring cone's probes: 1 / n^2, sqrt(1 - mu^2)
const INV_MU = F(1.7777778);
const F_REF = 0.0463394;                                // Fresnel reflectance at 77 deg between light and view: fizzBlick's calibration (the stand)
const C_GAIN = F(2);                                    // ring asymmetry: the probes' imbalance (a clear liquid lit from the side: ~0.25..0.3) to the core's shift
/** The core's largest shift px under fizzPhys: the ring is the bubble's whole total-reflection annulus, lit unevenly, so it
 *  thins toward one side but never opens (firmware FIZZ_RING_KEEP). */
export const FIZZ_RING_KEEP = 0.6;
const NEVER = F(1e9);                                   // a ray that meets no such boundary
const ATT_N = 64;                                       // attenuation table: exp(-tau) at tau = i / 8, 0 past 8
/** exp(-i / 8) by a float32 recurrence (the firmware builds the same numbers). */
export const FIZZ_ATT: Float32Array = (() => {
  const t = new Float32Array(ATT_N + 2), c = F(0.8824969);
  t[0] = 1;
  for (let i = 1; i <= ATT_N + 1; i++) t[i] = F(t[i - 1] * c);
  return t;
})();
/** exp(-a8 d / 8): a8 = 8 x the optical depth a px, d >= 0 px. */
function att(a8: number, d: number): number {
  const u = F(a8 * d);
  if (!(u < ATT_N)) return 0;   // past the table (and NaN): dark
  const i = Math.trunc(u), f = F(u - i);
  return F(FIZZ_ATT[i] + F(F(FIZZ_ATT[i + 1] - FIZZ_ATT[i]) * f));
}

/** A frame's light for one tube (firmware FizzLight). Ring probes 0..3: +x, -x, +y, -y (each tilted back by mu); 4: the key ray. */
export interface FizzLight {
  a8: number;            // 8 x optical depth a px: -8 ln(transparency) / 2R
  R: number; R2: number; // bore radius px
  w: Float32Array;       // [4] probe weights L_i / sum L (a clear, open tube: E = 1)
  invS: Float32Array;    // [5] 1 / (q . n) against the time edge's surface (0: the ray never meets it)
  invH: Float32Array;    // [5] the home edge's
  ly: number; lz: number; la: number; invA: number;   // the key ray against the bore wall: its cross-section part, |.|^2 and 1 / that (0: along the tube, never)
  fk: number;            // the pinpoint's Fresnel factor min(1, F / F_REF)
  hx: number; hy: number;   // the pinpoint's place per radius (liquid frame), at most 0.75
  openR: boolean; openL: boolean;   // the time / home surface is open to the room (else an end glass: dark)
  lid: boolean; kLid: number;       // desk view: a foam's view path per px of clearance under the level line
  tone: number;          // -1..1: the ring's tone against the liquid (> 0 a lit ring, < 0 a shade ring)
}
/** up: the pose's unit up in the LIQUID frame (x toward the time edge); lightDeg: TubeState.light (the palette's light
 *  sits at 2 x that in the cross-section); lid: the desk view's lid is drawn (tau, delta its angles, rad); exposed:
 *  drawTube's fizzExposed bits; tone: fizzTone. Once a frame (trig, a log and divisions here only). */
export function fizzLightFrame(transparency: number, R: number, upX: number, lightDeg: number,
                               lid: boolean, tau: number, delta: number, exposed: number, tone: number): FizzLight {
  const t = Math.max(0.01, Math.min(1, transparency));
  const a8 = F(F(-8 * F(Math.log(t))) / F(2 * R));
  const bx = Math.max(-1, Math.min(1, F(upX))), c = F(Math.sqrt(Math.max(0, F(1 - F(bx * bx))))), a2 = F(F(2 * lightDeg) * F(Math.PI / 180));
  const lx = bx, ly = F(-c * F(Math.sin(a2))), lz = F(c * F(Math.cos(a2)));
  // ring probes (unit): x, y, z components
  const qx = [BETA, -BETA, 0, 0, lx], qy = [0, 0, BETA, -BETA, ly], qz = [-MU, -MU, -MU, -MU, lz];
  const w = new Float32Array(4), invS = new Float32Array(5), invH = new Float32Array(5);
  let sum = 0;
  for (let i = 0; i < 4; i++) { w[i] = F(AMB + F(F(1 - AMB) * Math.max(0, F(F(F(qx[i] * lx) + F(qy[i] * ly)) + F(qz[i] * lz))))); sum = F(sum + w[i]); }
  for (let i = 0; i < 4; i++) w[i] = F(w[i] / sum);
  // the time edge's surface: the level plane under the lid (normal (1, 0, tan tau)), else across the tube (the drawn meniscus)
  const tanT = lid ? F(Math.tan(tau)) : 0;
  for (let i = 0; i < 5; i++) {
    const den = F(qx[i] + F(qz[i] * tanT)), denH = F(-qx[i]);
    invS[i] = den > 1e-3 ? F(1 / den) : 0;
    invH[i] = denH > 1e-3 ? F(1 / denH) : 0;
  }
  const a = F(F(ly * ly) + F(lz * lz));
  // Fresnel at half the angle between light and view (V = +z), water to air
  const ci = Math.sqrt(Math.max(0, (1 + lz) / 2)), s2 = 1 - ci * ci, n = 4 / 3;
  let fr = 1;
  if (n * n * s2 < 1) {
    const ct = Math.sqrt(1 - n * n * s2), rs = (n * ci - ct) / (n * ci + ct), rp = (ci - n * ct) / (ci + n * ct);
    fr = (rs * rs + rp * rp) / 2;
  }
  // the pinpoint sits where the bubble's normal halves light and view: r (lx, ly) / sqrt(2 (1 + lz)), kept within 0.75 r
  const hk = 1 / Math.sqrt(Math.max(1e-3, 2 * (1 + lz))), hm = Math.hypot(lx, ly) * hk, hc = hm > 0.75 ? 0.75 / hm : 1;
  // under the lid a foam's view ray refracts at the surface: path = clearance x cos tau / cos theta_w, sin theta_w = cos e / n
  const sw = Math.cos(tau + delta) / n, kLid = lid ? Math.cos(tau) / Math.sqrt(Math.max(0.05, 1 - sw * sw)) : 0;
  return { a8, R: F(R), R2: F(F(R) * F(R)), w, invS, invH, ly, lz, la: a, invA: a > 1e-6 ? F(1 / a) : 0,
    fk: F(Math.min(1, fr / F_REF)), hx: F(lx * hk * hc), hy: F(ly * hk * hc),
    openR: (exposed & 1) !== 0, openL: (exposed & 2) !== 0, lid, kLid: F(kLid), tone: F(Math.max(-1, Math.min(1, tone))) };
}
/** The ring's tone from its lit colour and the liquid behind it (RGB565; liqA / liqB: the palette's rows at a quarter and
 *  three quarters of the tube, so a highlight band on the centre row does not count as the liquid):
 *  (Y_rim - (Y_a + Y_b) / 2) / 32 in 8-bit luma, -1..1. Integers until the last division. */
export function fizzTone(rim565: number, liqA565: number, liqB565: number): number {
  const y = (c: number): number => { const r = (c >> 11) & 31, g = (c >> 5) & 63, b = c & 31; return (((r << 3) | (r >> 2)) * 77 + ((g << 2) | (g >> 4)) * 150 + ((b << 3) | (b >> 2)) * 29) >> 8; };
  return Math.max(-1, Math.min(1, (2 * y(rim565) - y(liqA565) - y(liqB565)) / 64));
}

/** A bubble's light (firmware FizzLit). */
export interface FizzLit {
  K: number;     // the ring's mix weight 0..1 (liquid .. lit rim): view transmission x the ring's light
  cx: number; cy: number;   // the ring's thick side, liquid frame, |.| <= 1: toward the light for a lit ring, away for a shade ring
  wl: number;    // the pinpoint's weight 0..1 (x fizzBlick): Fresnel x the key's path in and the view path out
  tv: number;    // view transmission 0..1
  sk: number;    // 0 at an open surface .. 1 from a diameter below it (the core's dark tint fades out in foam)
}
export const newFizzLit = (): FizzLit => ({ K: 1, cx: 0, cy: 0, wl: 1, tv: 1, sk: 1 });
/** x: the drawn centre along the tube (liquid frame); y, z: its place in the bore's cross-section, px from the centre
 *  (z toward the viewer); r: radius; S / SL: the time / home surface at its row (liquid frame); B: the lid's height at
 *  its row (0: no lid there). */
export function fizzLit(fl: FizzLight, x: number, y: number, z: number, r: number, S: number, SL: number, B: number, o: FizzLit): void {
  const a8 = fl.a8, y2 = F(y * y);
  const zR = F(Math.sqrt(Math.max(0, F(fl.R2 - y2))));
  const rem = Math.max(0, F(F(fl.R2 - y2) - F(z * z)));   // R^2 - y^2 - z^2
  // clearance under the time edge's surface along the tube (under the lid: the level line at its depth), over the home edge
  const lid = fl.lid && B > 0 && zR > 0;
  const clr = Math.max(0, lid ? F(F(S + F(F(F(zR - z) * B) / F(2 * zR))) - x) : F(S - x));
  const clrL = Math.max(0, F(x - SL));
  // view path: to the front glass, or (lid) up through the surface
  let dv = Math.max(0, F(zR - z));
  if (lid && fl.openR) dv = Math.min(dv, F(clr * fl.kLid));
  const tv = att(a8, dv);
  // ring probes: the first boundary each ray meets, and whether light comes in there
  const w = fl.w, invS = fl.invS, invH = fl.invH;
  const ray = (i: number, dw: number): number => {
    let d = dw, m = true;
    if (invS[i] > 0) { const ds = F(clr * invS[i]); if (ds < d) { d = ds; m = fl.openR; } }
    if (invH[i] > 0) { const dh = F(clrL * invH[i]); if (dh < d) { d = dh; m = fl.openL; } }
    return m ? att(a8, d) : 0;
  };
  const dwx = F(F(zR + z) * INV_MU);   // +-x probes: back to the wall, (z_R + z) / mu
  const vp = F(F(y * BETA) - F(z * MU)), vm = F(F(-y * BETA) - F(z * MU));
  const a0 = F(w[0] * ray(0, dwx)), a1 = F(w[1] * ray(1, dwx));
  const a2 = F(w[2] * ray(2, Math.max(0, F(F(Math.sqrt(F(F(vp * vp) + rem))) - vp))));
  const a3 = F(w[3] * ray(3, Math.max(0, F(F(Math.sqrt(F(F(vm * vm) + rem))) - vm))));
  const E = F(F(a0 + a1) + F(a2 + a3));
  // the ring's bright side: the probes' imbalance, gained to fizzShadeOff's calibration, at most 1 long
  let cx = 0, cy = 0;
  if (E > 1e-6) {
    const g = F(C_GAIN / E);
    cx = F(F(a0 - a1) * g); cy = F(F(a2 - a3) * g);
    const c2 = F(F(cx * cx) + F(cy * cy));
    if (c2 > 1) { const k = F(1 / F(Math.sqrt(c2))); cx = F(cx * k); cy = F(cy * k); }
  }
  // the key ray: the lamp's own path in
  let wl = 0;
  {
    const v = F(F(y * fl.ly) + F(z * fl.lz));
    const dw = fl.invA > 0 ? F(Math.max(0, F(F(Math.sqrt(F(F(v * v) + F(rem * fl.la)))) - v)) * fl.invA) : NEVER;
    let d = dw, m = true;
    if (invS[4] > 0) { const ds = F(clr * invS[4]); if (ds < d) { d = ds; m = fl.openR; } }
    if (invH[4] > 0) { const dh = F(clrL * invH[4]); if (dh < d) { d = dh; m = fl.openL; } }
    if (m) wl = F(fl.fk * att(a8, F(d + dv)));
  }
  const tp = Math.max(0, fl.tone);
  o.K = F(tv * F(1 - F(tp * F(1 - Math.min(1, E)))));
  o.cx = F(cx * fl.tone); o.cy = F(cy * fl.tone);
  o.wl = wl; o.tv = tv;
  const d2 = F(2 * r), near = Math.min(fl.openR ? clr : NEVER, fl.openL ? clrL : NEVER);
  o.sk = near < d2 ? F(near / d2) : 1;
}
