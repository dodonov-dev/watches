// Optical half of derive(material, design) (docs/physical-renderer.md, "Colour model"): two-flux
// Kubelka–Munk per channel on the phase-1 cylinder trace, the body radiance with the far-interface and
// side-light terms, and the encoded-space pre-images of the legacy palette. Pure: no DOM, no Node.
import { traceRowDetail } from './optics/geometry';
import { backingLight } from './optics/lighting';
import { decode, encode, fresnel, type PhysicalParams } from './optics/optics';
import type { Material } from './model';
import { THIN_IOR } from '../render';

export type RGB3 = [number, number, number];
export type Anchor = readonly [number, number];
export type Opacity = 'opaque' | 'translucent' | 'clear';

// ---------------------------------------------------------------------------------------------
// Helpers

export const clamp = (v: number, lo = 0, hi = 1): number => Math.max(lo, Math.min(hi, v));
/** Monotone piecewise-linear interpolation through `pts` (coordinate first), clamped at both ends. */
export function anchored(x: number, pts: readonly Anchor[]): number {
  if (x <= pts[0][0]) return pts[0][1];
  for (let i = 1; i < pts.length; i++) {
    const [x0, y0] = pts[i - 1], [x1, y1] = pts[i];
    if (x <= x1) return x1 > x0 ? y0 + (y1 - y0) * (x - x0) / (x1 - x0) : y1;
  }
  return pts[pts.length - 1][1];
}
/** Clamp a law's value into the inferred class's coherence range; no range → unchanged. */
export const classClamp = (v: number, range: readonly [number, number] | undefined): number =>
  range ? clamp(v, range[0], range[1]) : v;
/** sRGB transfer, 0..1 (input clamped to 0..1). */
export const enc01 = (v: number): number => encode(v);
/** sRGB transfer in 8-bit levels, 0..255 (unrounded). */
export const enc255 = (v: number): number => 255 * encode(v);
/** Linear light of an 8-bit encoded level. */
export const lin255 = (v8: number): number => decode(clamp(v8, 0, 255) / 255);
export const luma3 = (c: readonly number[]): number => 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2];
/** Saturation (max − min) / max; 0 for black (guarded normalisation). */
export const sat3 = (c: readonly number[]): number => {
  const mx = Math.max(c[0], c[1], c[2]), mn = Math.min(c[0], c[1], c[2]);
  return mx > 1e-9 ? (mx - mn) / mx : 0;
};
export const hexRgb = (s: string): RGB3 => [parseInt(s.slice(1, 3), 16), parseInt(s.slice(3, 5), 16), parseInt(s.slice(5, 7), 16)];
/** 8-bit channels (rounded, clamped) → #rrggbb. */
export const rgbHex = (c: readonly number[]): string =>
  '#' + [0, 1, 2].map((i) => Math.round(clamp(c[i], 0, 255)).toString(16).padStart(2, '0')).join('');
const map3 = (f: (i: number) => number): RGB3 => [f(0), f(1), f(2)];

// ---------------------------------------------------------------------------------------------
// Two-flux Kubelka–Munk with executable limit branches

export interface KM { R: number; Tr: number }
/** Layer of absorption K and reduced scattering S (1/mm), thickness d (mm) over a ground of
 *  reflectance Rg: diffuse reflectance R and transmittance Tr. */
export function km(K: number, S: number, d: number, Rg: number): KM {
  if (!(d > 0)) return { R: Rg, Tr: 1 };
  if (S < 1e-6) { const t = Math.exp(-K * d); return { R: Rg * t * t, Tr: t }; }
  if (K < 1e-9) { const sd = S * d; return { R: (Rg + sd * (1 - Rg)) / (1 + sd * (1 - Rg)), Tr: 1 / (1 + sd) }; }
  const k = K / S, a = 1 + k, b = Math.sqrt(k * (2 + k)); // √(a² − 1) without cancellation
  const x = Math.min(50, b * S * d), coth = 1 / Math.tanh(x);
  return {
    R: (1 - Rg * (a - b * coth)) / (a - Rg + b * coth),
    Tr: b / (a * Math.sinh(x) + b * Math.cosh(x)),
  };
}

// ---------------------------------------------------------------------------------------------
// Trace sampling (phase-1 traceRow)

/** Bore fraction of the wall sample: the panel row at u = 0.85 of the bore radius. */
export const U_WALL = 0.85;
/** Display row offset from the tube centre (fraction of the drawn radius, which spans the outer wall) of
 *  bore position u: d(u) = u·r/(r + wallThickness); its row fraction is t = (1 + d)/2. */
export const displayOffset = (u: number, m: Material): number => u * m.innerRadius / (m.innerRadius + m.wallThickness);
/** The palette's chord factor at display offset d (buildPalette liquidThin): the refracted chord
 *  √(1 − (d·R/(n·r))²), n = the palette's THIN_IOR, R/r = (r + wallThickness)/r. */
export const paletteChord = (d: number, m: Material): number => {
  const k = d * (m.innerRadius + m.wallThickness) / (THIN_IOR * m.innerRadius);
  return Math.sqrt(Math.max(0, 1 - k * k));
};
/** Lamp radiance relative to a white diffuse surface (highlightBright calibration). */
export const L_SPEC = 12;

/** The phase-1 PhysicalParams the trace and backingLight read, built from the material. */
export function physicalParams(m: Material): PhysicalParams {
  return {
    innerRadiusMm: m.innerRadius, wallThicknessMm: m.wallThickness, liquidIor: m.ior, wallIor: m.wallIor,
    absorptionR: m.absorptionR, absorptionG: m.absorptionG, absorptionB: m.absorptionB,
    lightAngleDeg: m.lightElevation, lightSizeDeg: m.lightSize, lightIntensity: m.lightIntensity,
    ambientIntensity: m.ambient,
    // not read by traceRow / backingLight
    backingReflectance: 0, marksReflectance: 0, exposure: m.exposure, hoursY: 0, minutesY: 0,
  };
}

export interface RowSample {
  u: number;
  /** Chord through the liquid, mm (traceRow's refracted path). */
  d: number;
  /** Fresnel transmission product of the four interfaces. */
  Ft: number;
  /** Far-interface return 1 − (1 − F₃)(1 − F₄) at the ray's actual incidence. */
  Ffar: number;
}
/** Trace the panel row at bore fraction u (y = u·r from the axis) through the filled tube. */
export function sampleRow(u: number, m: Material): RowSample {
  const path = traceRowDetail(u * m.innerRadius, true, physicalParams(m));
  return { u, d: path.distance, Ft: path.transmission, Ffar: 1 - (1 - path.farInner) * (1 - path.farOuter) };
}

// ---------------------------------------------------------------------------------------------
// Body radiance

export interface Illumination {
  /** Liquid-side irradiance exposure·(ambient + 0.5·I). */
  El: number;
  /** Backing irradiance exposure·backingLight. */
  Eb: number;
  /** Side-light irradiance exposure·(ambient + 0.25·I) (calibrated off-axis approximation). */
  Es: number;
}
export function illumination(m: Material): Illumination {
  return {
    El: m.exposure * (m.ambient + 0.5 * m.lightIntensity),
    Eb: m.exposure * backingLight(physicalParams(m)),
    Es: m.exposure * (m.ambient + 0.25 * m.lightIntensity),
  };
}
/** Effective ground reflectance of the backing under the liquid: lin(back)/E_l (0 when E_l = 0).
 *  Capped at 1 — a reflectance above 1 has no two-flux meaning (and makes the K→0 branch singular);
 *  it happens when lin(back) > E_l (a light backing under dim light), where E_l·Rg falls short of lin(back). */
export function groundReflectance(back8: readonly number[], L: Illumination): RGB3 {
  // The legacy compositor shows the dry backing at its hex brightness, so the displayed colour is the ground truth:
  // the backing's radiance under the liquid is lin(back) (E_l·Rg = lin(back)), not E_b·albedo — otherwise a white
  // backing derived darker on the wet side than the dry side shows it (T_max capped colourless liquids at 0.63).
  return map3((i) => L.El > 0 ? Math.min(1, lin255(back8[i]) / L.El) : 0);
}

const K3 = (m: Material): RGB3 => [m.absorptionR, m.absorptionG, m.absorptionB];

/** C_i(u) = E_l·[R_i(d, Rg_i) + F_far·Tr_i(d)²] + E_s·u⁴·Tr_i(d), linear light. A black `back8` gives the
 *  backing-independent body C⁰ (the clear class's body: the legacy mix adds the backing itself). */
export function bodyRadiance(m: Material, s: RowSample, back8: readonly number[], L: Illumination): RGB3 {
  // The backing term is scaled by the DISPLAYED backing colour (the legacy shows the dry backing at its hex, so the
  // wet side must agree with it): lin(back)·[R(d, 1) − R(d, 0)] — the two-flux response to a white ground, times the
  // ground's own radiance — plus E_l·R(d, 0), the body's own scattered light. No reflectance cap is needed.
  const K = K3(m), u4 = s.u ** 4;
  return map3((i) => {
    const k0 = km(K[i], m.scattering, s.d, 0), k1 = km(K[i], m.scattering, s.d, 1), Tr = k0.Tr;
    const R = L.El * k0.R + lin255(back8[i]) * (k1.R - k0.R);
    return R + L.El * s.Ffar * Tr * Tr + L.Es * u4 * Tr;
  });
}

// ---------------------------------------------------------------------------------------------
// Transparency class

/** Snap T out of the checker's gaps (0.12–0.25, 0.55–0.7) to the nearer band edge; a tie goes up.
 *  `down`: T is bound by T_max / T_up (the attainability limits), so a gap value snaps down to stay attainable. */
export function snapT(T: number, down = false): number {
  const snap = (lo: number, hi: number): number => (down || 2 * T < lo + hi ? lo : hi);
  if (T > 0.12 && T < 0.25) return snap(0.12, 0.25);
  if (T > 0.55 && T < 0.7) return snap(0.55, 0.7);
  return T;
}
/** A clear liquid is colourless (PRESETS.md): a two-pass channel spread max Tr² − min Tr² at the centre
 *  chord of this much or more caps T at the translucent edge 0.55 before the band snap. */
export const CLEAR_SPREAD = 0.15;
export const opacityOf = (Tsnap: number): Opacity => (Tsnap <= 0.12 ? 'opaque' : Tsnap <= 0.55 ? 'translucent' : 'clear');

// ---------------------------------------------------------------------------------------------
// Palette pre-images (8-bit encoded levels)

/** Pre-image of the palette's mix(liquid, back, T) for a target enc255 colour: opaque/translucent
 *  invert the mix (clamped: an unattainable target), clear takes the target directly. */
export function preImage(target255: readonly number[], back8: readonly number[], T: number, clear: boolean): RGB3 {
  return map3((i) => clear ? target255[i] : clamp((target255[i] - T * back8[i]) / (1 - T), 0, 255));
}
/** Composite the legacy mix shows for body `liquid` over `back`, minus the target, worst channel (levels). */
export function compositeResidual(liquid255: readonly number[], back8: readonly number[], T: number, target255: readonly number[]): number {
  return Math.max(...[0, 1, 2].map((i) => Math.abs((1 - T) * liquid255[i] + T * back8[i] - target255[i])));
}

// ---------------------------------------------------------------------------------------------
// The colour laws

export interface ColourInput {
  material: Material;
  /** Per-sample backings (8-bit), the palette's back(t) at t = 0.5 and at the wall sample's row fraction. */
  backCentre: RGB3;
  backWall: RGB3;
  metal: boolean;
  plasma: boolean;
  emissive: boolean;
  /** Luma of the emission RGB. */
  ELum: number;
  /** Tube radius in px (tubeHeight − 1)/2 and tube height in px (drawn H); the wall backing is sampled
   *  at row fraction (1 + displayOffset(U_WALL))/2. */
  Rpx: number;
  H: number;
}
export interface ColourOutput {
  /** Two-pass luma transmittance luma(F_t·Tr²) of the centre chord and the largest attainable scalar
   *  transparency on this backing (∞ on a dark one); T = min of both, before the band snap. */
  Tlum: number;
  Tmax: number;
  /** Upper feasibility bound: no pre-image channel may need more than 255 levels (∞ on a white backing). */
  Tup: number;
  /** Two-pass channel spread max Tr² − min Tr² at the centre chord (≥ CLEAR_SPREAD: not clear). */
  spread: number;
  T: number;
  Tsnap: number;
  opacity: Opacity;
  /** Worst-channel composite residual of the centre-row body, 8-bit levels. */
  residual: number;
  /** Rejection 9 reason (the body or the highlight floor does not fit the 8-bit range), else null. */
  overexposed: string | null;
  /** Rejection 10 reason (the composite residual of an opaque/translucent body exceeds 5 levels), else null. */
  unrepresentable: string | null;
  centre: RowSample;
  wall: RowSample;
  C0: RGB3;
  Cw: RGB3;
  /** Wall body without the side light B_w and centre body B_c (linear), the shadeDepth fit's inputs. */
  Bw: RGB3;
  Bc: RGB3;
  /** The wall row's target (linear, emission excluded): B_w plus the side light E_s·u⁴·Tr — the full wall
   *  sample with its scattered share Lambert-shaded (a metal: λ·C, the grey conductor shaded alike). */
  Wall: RGB3;
  params: {
    liquid: string; liquidLo: string; liquidHi: string; liquidTransparency: number; liquidThin: number;
    shadeDepth: number; highlightH: number; highlightBright: number; highlightSharp: number;
    glassHi: string; glassHiBright: number; glassReflect: number; glassRim: number; glassBody: number;
    glassWallGlow: number; wallWet: number; glassOverLiquid: number; bubbleRim: string; bubbleDark: number; rimLight: number;
  };
}

const SHADE_RANGE: Record<Opacity, [number, number]> = { opaque: [0.5, 0.95], translucent: [0.4, 0.85], clear: [0.3, 0.55] };
const deg = Math.PI / 180;

export function colourLaws(c: ColourInput): ColourOutput {
  const m = c.material, L = illumination(m);
  const E: RGB3 = [m.emissionR, m.emissionG, m.emissionB];
  const K = K3(m), S = m.scattering;
  const centre = sampleRow(0, m), wall = sampleRow(U_WALL, m);

  // body radiance (C0 = C(0) over the centre backing, Cfree = C⁰ backing-independent) and transparency:
  // two-pass T_lum (lit through, seen through; F_t once), bounded by the largest scalar transparency at
  // which the palette's mix(liquid, back, T) can still reach the target in every lit backing channel
  let C0: RGB3, Cfree: RGB3, Cw: RGB3, Tlum: number, Tmax = Infinity, Tup = Infinity, spread = 0;
  // the pre-image target: the body with its emission summed in linear light, encoded once
  const target = (): RGB3 => map3((i) => enc255(C0[i] + E[i]));
  if (c.plasma) { C0 = [0, 0, 0]; Cfree = C0; Cw = C0; Tlum = 0.5; }
  else if (c.metal) { const g = m.metalReflectance * L.El * 0.6; C0 = [g, g, g]; Cfree = C0; Cw = C0; Tlum = 0; }
  else {
    C0 = bodyRadiance(m, centre, c.backCentre, L);
    Cfree = bodyRadiance(m, centre, [0, 0, 0], L);
    Cw = bodyRadiance(m, wall, c.backWall, L);
    const Tr2 = map3((i) => km(K[i], S, centre.d, 0).Tr ** 2);
    Tlum = luma3(map3((i) => centre.Ft * Tr2[i]));
    spread = Math.max(...Tr2) - Math.min(...Tr2);
    const t = target();
    for (let i = 0; i < 3; i++) {
      if (c.backCentre[i] >= 8) Tmax = Math.min(Tmax, t[i] / c.backCentre[i]);
      if (c.backCentre[i] < 255) Tup = Math.min(Tup, (255 - t[i]) / (255 - c.backCentre[i]));
    }
  }
  // T_up bounds the pre-image; a clear liquid takes C⁰ directly (no pre-image), so it applies only when
  // the result is not clear
  let T = Math.min(Tlum, Tmax);
  if (spread >= CLEAR_SPREAD) T = Math.min(T, 0.55);
  let Tsnap: number;
  if (c.plasma || c.metal) Tsnap = T;
  else if (snapT(T, Tmax < Tlum) >= 0.7) Tsnap = snapT(T, Tmax < Tlum);
  else { T = Math.min(T, Tup); Tsnap = snapT(T, Math.min(Tmax, Tup) < Tlum); }
  const opacity: Opacity = c.metal ? 'opaque' : opacityOf(Tsnap);
  const clear = opacity === 'clear', trim = c.emissive ? 1 / 1.3 : 1;
  const Cb = clear ? Cfree : C0;

  // liquid / liquidLo: pre-image of the centre body with its emission summed in linear light and encoded
  // once (clear: C⁰ + E directly); the emissive trim comes last. Plasma (C = 0) keeps the legacy xenon
  // convention: enc255(E) taken directly, no pre-image (the palette's fixed 0.5 mix dims it over the backing).
  const tgt = map3((i) => enc255(Cb[i] + E[i]));
  const body = c.plasma ? tgt : preImage(tgt, c.backCentre, Tsnap, clear);
  const residual = compositeResidual(body, c.backCentre, Tsnap, clear ? map3((i) => enc255(C0[i] + E[i])) : tgt);
  const liq255 = map3((i) => clamp(body[i], 0, 255));
  const fLo = Math.max(0.15, m.ambient / Math.max(1e-6, m.ambient + m.lightIntensity));
  const tgtLo = map3((i) => enc255(Cb[i] * fLo + E[i]));
  const bodyLo = c.plasma ? tgtLo : preImage(tgtLo, c.backCentre, Tsnap, clear);
  const liquidLo = map3((i) => clamp(bodyLo[i], 0, 255) * trim);
  const liquid = map3((i) => liq255[i] * trim);
  let overexposed: string | null = luma3(liq255) >= 248
    ? `the derived liquid reaches luma ${luma3(liq255).toFixed(1)} ≥ 248 levels` : null;

  // wall desaturation fit
  const e0 = map3((i) => enc01(C0[i])), ew = map3((i) => enc01(Cw[i]));
  const s0 = sat3(e0);
  const dW = displayOffset(U_WALL, m), chordW = paletteChord(dW, m);
  const liquidThin = c.metal || s0 < 0.05 ? 0 : clamp((1 - sat3(ew) / s0) / (1 - chordW) ** 2, 0, 1);

  // cylinder shading fitted to the wall sample: only the scattered light is Lambert-shaded at the row's
  // surface normal, λ(d) = cos(asin d); the backlit transmission and the far-wall return are not.
  // B_w = E_l·[λ·R(d_w, 0) + (R(d_w, Rg) − R(d_w, 0)) + F_far·Tr²] against the centre body B_c.
  const lam = Math.cos(Math.asin(clamp(dW, 0, 1)));
  let Bw: RGB3 = [0, 0, 0], Bc: RGB3 = [0, 0, 0], Wall: RGB3 = [0, 0, 0];
  let shadeDepth: number;
  if (c.metal) { shadeDepth = 0.95; Bc = C0; Bw = map3((i) => lam * C0[i]); Wall = Bw; }
  else if (c.plasma) shadeDepth = 0.85;
  else {
    const RgW = groundReflectance(c.backWall, L), RgC = groundReflectance(c.backCentre, L);
    Bw = map3((i) => {
      const R0 = km(K[i], S, wall.d, 0).R, Tr = km(K[i], S, wall.d, 0).Tr;
      return L.El * (lam * R0 + (km(K[i], S, wall.d, RgW[i]).R - R0) + wall.Ffar * Tr * Tr);
    });
    Bc = map3((i) => {
      const Tr = km(K[i], S, centre.d, 0).Tr;
      return L.El * (km(K[i], S, centre.d, RgC[i]).R + centre.Ffar * Tr * Tr);
    });
    Wall = map3((i) => Bw[i] + L.Es * U_WALL ** 4 * km(K[i], S, wall.d, 0).Tr);
    const range = SHADE_RANGE[opacity], lc = luma3(Bc);
    shadeDepth = lc > 0 ? clamp((1 - luma3(Bw) / lc) / (1 - lam), range[0], range[1]) : range[0];
  }

  // specular: the light's colour added over the body (summed in linear light with 1.5·E, encoded once),
  // floored at luma(liquid) + 8 levels (the palette
  // mixes liquid with the backing before the highlight, so the checker compares the pre-image with it)
  const Lhi = Math.min(1, fresnel(Math.cos(m.lightElevation / 2 * deg), 1, m.wallIor) * m.lightIntensity * L_SPEC);
  let hi: RGB3;
  if (c.metal) hi = [255, 255, 255];
  else {
    const lw = luma3(Cw);
    const thin: RGB3 = clear || lw < 1e-4 ? [1, 1, 1] : map3((i) => Cw[i] / lw);
    hi = map3((i) => enc255(Math.min(1, Cb[i] + Lhi * (0.7 + 0.3 * thin[i]) + 1.5 * E[i])));
  }
  const floor = luma3(liq255) + 8;
  if (luma3(hi) < floor) {
    const k = floor / Math.max(1, luma3(hi));
    hi = map3((i) => hi[i] * k);
    if (Math.max(...hi) > 255 && !overexposed)
      overexposed = `the highlight floor (luma ${floor.toFixed(1)}) does not fit below 255 levels`;
    hi = map3((i) => Math.min(255, hi[i]));
  }
  const liquidHi = map3((i) => hi[i] * trim);
  const highlightBright = c.metal
    ? Math.min(1.3, m.metalReflectance * m.lightIntensity * L_SPEC)
    : clamp(Lhi / Math.max(0.05, 1 - luma3(e0)), 0, 1);
  const highlightH = Math.max(3, Math.min(Math.floor(c.H / 3),
    Math.round(2 * c.Rpx * Math.sin(m.lightSize / 4 * deg) * Math.cos(m.lightElevation / 2 * deg))));

  // glass
  const F0w = fresnel(1, 1, m.wallIor);
  const ratio = c.metal ? 1 : (F0w + fresnel(1, m.wallIor, m.ior)) / (2 * F0w);
  let glassOverLiquid = ratio / (1 + 2 * c.ELum);
  if (c.emissive) glassOverLiquid = Math.min(0.4, glassOverLiquid);
  if (clear) glassOverLiquid = Math.max(0.5, glassOverLiquid);
  glassOverLiquid = clamp(glassOverLiquid);
  // The wall band's own light, piped along the glass from the side light. The palette lays it on the dry band
  // only (a wetted wall frustrates the piping and the liquid fills the band), so the contents do not set it.
  const glassWallGlow = clamp(0.6 * L.Es);
  // Wall wetting: a ray at height y reaches contents of index n only if y ≤ n·r (the invariant n·ρ·sinθ, and it must first
  // reach the bore: n ≤ wallIor), so the contents fill (min(ior, wallIor) − 1)·r of the band's wall thickness, and where
  // they touch the glass they frustrate its piped glow. A gas (ior 1) leaves the band to the wall; a metal keeps the
  // liquid look (its surface mirrors rather than refracts).
  const wallWet = c.metal ? 1 : m.wallThickness > 0 ? clamp((Math.min(m.ior, m.wallIor) - 1) * m.innerRadius / m.wallThickness) : 1;

  return {
    Tlum, Tmax, Tup, spread, T, Tsnap, opacity, residual, overexposed,
    unrepresentable: !clear && !c.plasma && residual > 5
      ? `the composite residual ${residual.toFixed(1)} levels exceeds 5 after every bound and snap (T ${Tsnap.toFixed(3)})` : null, centre, wall, C0, Cw, Bw, Bc, Wall,
    params: {
      liquid: rgbHex(liquid), liquidLo: rgbHex(liquidLo), liquidHi: rgbHex(liquidHi),
      liquidTransparency: Tsnap, liquidThin, shadeDepth,
      highlightH, highlightBright, highlightSharp: 2,
      glassHi: '#dfe6ea', glassHiBright: 0.55 * Lhi, glassReflect: 0.25 * Lhi, glassRim: 0.45 + 0.35 * Lhi,
      glassBody: 0.4 * m.ambient, glassWallGlow, wallWet, glassOverLiquid,
      // A bubble's rim totally reflects the light inside the liquid, not the backing behind it: the side light filtered
      // by the liquid on its way in (half the bore), plus the body's own colour. Its centre is a clear window: the
      // only loss is the Fresnel reflection at its two liquid/gas surfaces (the tint over the see-through core).
      bubbleRim: rgbHex(map3((i) => enc255(Math.min(1, L.Es * km(K[i], S, m.innerRadius, 0).Tr + 0.35 * Cfree[i])))),
      bubbleDark: 1 - (1 - fresnel(1, m.ior, 1)) ** 2,
      // side-lit rim of a dielectric liquid; its tint is solved on the real palette (derive.ts)
      rimLight: c.metal || c.plasma ? 0 : 1,
    },
  };
}
