// derive(material, design) → Params (docs/physical-renderer.md): a pure, deterministic function that
// fills every legacy Params key exactly once — from the design (pass-through of the allowlist), from the
// material (the laws; colour in optical.ts, dynamics / film / gas here) or from a fixed policy. Invalid
// or incompatible inputs are rejected with a visible error, never silently fixed. Pure: no DOM, no Node.
import { DEFAULT_PARAMS, PARAM_META, PARAMS_VERSION, type Material as MaterialClass, type Params } from '../params';
import { DESIGN_H as PANEL_H, DESIGN_TUBE_HEIGHT_MAX as TUBE_HEIGHT_MAX, DESIGN_MM_PER_PX as MM_PER_PX } from '../../../spec/layout';   // derived params are in design px, whatever the board
import { VISC, coherenceIssues, luma as lumaHex } from './coherence';
import {
  DEFAULT_MATERIAL, DESIGN_KEYS, MATERIAL_KEYS, MATERIAL_META, validateDesign, validateMaterial,
  type Design, type DesignKey, type Material, type MaterialKey,
} from './model';
import { U_WALL, anchored, clamp, classClamp, colourLaws, displayOffset, enc255, hexRgb, luma3, rgbHex, type Anchor, type RGB3 } from './optical';
import { buildPalette } from '../render';
import { rgb565, rgb565to888 } from '../../../spec/layout';

// ---------------------------------------------------------------------------------------------
// Ownership of every legacy key

/** Keys the material derives (the doc's "Derived" set). */
export const DERIVED_KEYS = [
  'liquid', 'liquidHi', 'liquidLo', 'liquidTransparency', 'liquidThin', 'shadeDepth',
  'highlightH', 'highlightBright', 'highlightSharp', 'glassHi', 'glassHiBright', 'glassReflect', 'glassRim', 'glassWall',
  'glassWallGlow', 'wallWet', 'rimLight', 'rimTint', 'glassBody', 'glassOverLiquid', 'lightPhys', 'lightAngle', 'ambientLight', 'liquidBright',
  'tickLens', 'bottomLens', 'bubbleRim', 'bubbleDark', 'edgeGlow', 'glowStrength', 'frontBright', 'edgeLightGain', 'edgeSoft',
  'surfaceFill', 'surfaceBlick', 'contactAngle', 'contactHyst', 'contactDyn', 'capLength', 'freeDamp', 'freeBounce', 'meniscusK',
  'meniscusDamp', 'meniscusInertia', 'angleTiltGain', 'angleGyroGain', 'angleMax', 'wetFilm', 'traces', 'traceAmount', 'traceDry',
  'traceDrain', 'traceStain', 'traceFilm', 'fizz', 'fizzCount', 'fizzSize', 'fizzSpeed', 'fizzFoamLife', 'fizzFlatRise',
  'fizzEdgeRise', 'fizzDriftGain',
] as const satisfies readonly (keyof Params)[];
export type DerivedKey = (typeof DERIVED_KEYS)[number];

/** Keys under a fixed policy. `fillK fillDamp fillSloshGain angleK angleDamp` take the plasma values for a
 *  plasma (the doc lists them as derived for plasma); `freeLiquid` (design) is forced off for a plasma. */
export const FIXED_KEYS = [
  'v', 'highlightInset', 'surfaceBand', 'surfaceRim', 'surfaceWidth', 'surfaceTone', 'freeGain',
  'fillK', 'fillDamp', 'fillSloshGain', 'angleK', 'angleDamp',
  'acrossK', 'acrossDamp', 'acrossGyroGain', 'shakeGain', 'deadzone', 'accelLpHz', 'gyroHpHz', 'gyroDeadzone', 'gyroMax', 'inputGain',
  'bubble', 'bubbleW', 'bubbleH', 'bubbleGap', 'bubbleY', 'bubbleRollGain', 'bubbleTiltGain',
] as const satisfies readonly (keyof Params)[];
export type FixedKey = (typeof FIXED_KEYS)[number];

// Compile-time: the three sets are disjoint and cover keyof Params (a new Params key without an owner,
// or a key owned twice, fails `tsc`).
type Owned = DesignKey | DerivedKey | FixedKey;
type Assert<T extends true> = T;
export type OwnershipComplete = Assert<[Exclude<keyof Params, Owned>] extends [never] ? true : false>;
export type OwnershipDisjoint = Assert<[Extract<DesignKey, DerivedKey> | Extract<DesignKey, FixedKey> | Extract<DerivedKey, FixedKey>] extends [never] ? true : false>;

/** Runtime ownership check against the actual Params object (DEFAULT_PARAMS): [] when every key has
 *  exactly one owner. */
export function ownershipIssues(): string[] {
  const bad: string[] = [];
  const owner = new Map<string, string[]>();
  const add = (set: string, keys: readonly string[]): void => {
    for (const k of keys) owner.set(k, [...(owner.get(k) ?? []), set]);
  };
  add('design', DESIGN_KEYS); add('derived', DERIVED_KEYS); add('fixed', FIXED_KEYS);
  for (const k of Object.keys(DEFAULT_PARAMS)) if (!owner.has(k)) bad.push(`Params key ${k} has no owner`);
  for (const [k, sets] of owner) {
    if (!(k in DEFAULT_PARAMS)) bad.push(`owned key ${k} is not a Params key`);
    if (sets.length > 1) bad.push(`Params key ${k} is owned by ${sets.join(' and ')}`);
  }
  return bad;
}

// ---------------------------------------------------------------------------------------------
// Coordinates and classes

/** Class thresholds of μ_eff (2.5, 500) as x_μ = log10 μ_eff: the anchor coordinates of every x_μ law. */
export const X_W = Math.log10(2.5);
export const X_V = Math.log10(500);
type Band = 'watery' | 'medium' | 'viscous';
const bandOf = (muEff: number): Band => (muEff < 2.5 ? 'watery' : muEff < 500 ? 'medium' : 'viscous');
/** A law with a class jump: one anchor table per viscosity band, each clamped at its own ends, so the
 *  value changes exactly where the class does and never interpolates through a forbidden range. */
const jump = (x: number, band: Band, t: Record<Band, readonly Anchor[]>): number => anchored(x, t[band]);

const FREE_DAMP: Record<Band, readonly Anchor[]> = {
  watery: [[-1, 0.5], [0, 0.8], [X_W, 1.4]], medium: [[X_W, 1.6], [1, 2.5], [X_V, 4]], viscous: [[X_V, 6], [4, 9], [5, 14]],
};
const MENISCUS_K: Record<Band, readonly Anchor[]> = {
  watery: [[0, 475], [X_W, 420]], medium: [[X_W, 340], [X_V, 210]], viscous: [[X_V, 140], [4, 90], [5, 60]],
};
const MENISCUS_DAMP: Record<Band, readonly Anchor[]> = {
  watery: [[-1, 4], [0, 8], [X_W, 14]], medium: [[X_W, 14], [X_V, 24]], viscous: [[X_V, 26], [4, 34], [5, 50]],
};
const TILT: Record<Band, readonly Anchor[]> = {
  watery: [[0, 6.5], [X_W, 5]], medium: [[X_W, 5], [X_V, 3]], viscous: [[X_V, 2.5], [4, 1.5], [5, 0.5]],
};
const GYRO: Record<Band, readonly Anchor[]> = {
  watery: [[0, 0.42], [X_W, 0.3]], medium: [[X_W, 0.3], [X_V, 0.15]], viscous: [[X_V, 0.12], [4, 0.06], [5, 0.02]],
};
const FREE_BOUNCE: readonly Anchor[] = [[-3.5, 0.55], [-2.6, 0.2], [-2.0, 0.1], [-1.0, 0.03], [-0.5, 0]];
const INERTIA: readonly Anchor[] = [[0, 3], [X_V, 2], [5, 1]];
const WET_FILM: readonly Anchor[] = [[-5, 8], [-4.5, 10], [-3.9, 15], [-2.3, 18], [-1, 26], [0, 30]];
const FIZZ_SPEED: readonly Anchor[] = [[-1, 0], [0.5, 3], [1.5, 20], [2, 40], [2.5, 55], [3, 60]];
const GLOW: readonly Anchor[] = [[0.02, 0.4], [1, 0.8]];
const GAS: readonly MaterialClass['gas'][] = ['none', 'carbonated', 'boiling', 'trapped'];
const GAS_RANGE: Record<MaterialClass['gas'], { speed: [number, number] } | undefined> = {
  none: undefined,
  carbonated: { speed: [30, 55] },
  boiling: { speed: [45, 60] },
  trapped: { speed: [0, 8] },
};
/** The drawable fizz diameter (PARAM_META.fizzSize): the only bound on the bubble-radius law — the size
 *  follows bubbleRadius in every gas class. */
const FIZZ_SIZE: [number, number] = [PARAM_META.fizzSize.min ?? 1, PARAM_META.fizzSize.max ?? 16];
/** digitFont values ≥ this select the image sprite fonts (render.ts SPRITE_FONT = FONTS.length). */
const SPRITE_FONT = 5;
/** A backing this light (luma, 8-bit) is named by an overexposure rejection (9: "darken the backing"). */
const LIGHT_BACK = 128;

export interface DeriveCoords {
  muEff: number; x: number; Oh: number; Ca0: number; lc: number; pxPerMm: number; T: number; Tsnap: number; ELum: number;
  /** Two-pass luma transmittance and the attainability bound (T = min of both before the snap). */
  Tlum: number; Tmax: number; Tup: number;
}
export interface DeriveReport {
  params: Params;
  classes: MaterialClass;
  coords: DeriveCoords;
  /** Centre-row composite residual of the body, 8-bit levels. */
  residual: number;
  /** Linear body radiance at the centre sample, the wall row's target (B_w plus the side light, emission
   *  excluded) and the wall sample's display row offset d(0.85). */
  body: { centre: RGB3; wall: RGB3; wallOffset: number };
  /** The side-light rim fit: the chosen `rimLight` gain, the fitted body-only wall row's error against the
   *  wall target after the RGB565 round trip (8-bit levels, every channel), the part of it the rim answers
   *  for (`rimError`, rejection 12 above 5) and `bodyOver`, the overshoot of channels already above the
   *  target with no rim (tint 0: the body shading's miss, which an additive rim cannot lower). All 0 when
   *  the rim is off. */
  rim: { gain: number; error: number; rimError: number; bodyOver: number };
  /** Rejections; derive() throws when non-empty. */
  issues: string[];
  /** The same rejections, one per `issues` entry in the same order, with the inputs each points at. */
  problems: DeriveProblem[];
}

/** One rejection and the inputs it points at (the UI flags those controls). */
export interface DeriveProblem {
  /** The rejection number (1–12). */
  code: number;
  /** The issue string, identical to the matching `issues` entry. */
  text: string;
  /** Material properties the rejection points at. */
  material: MaterialKey[];
  /** Design keys (legacy Params the user edits in material mode) it points at. */
  design: DesignKey[];
  /** Derived / fixed legacy keys a realism (coherence) message names: the out-of-range derived values. */
  derived: (keyof Params)[];
}

// ---------------------------------------------------------------------------------------------
// Problems: which inputs a rejection points at

const EMISSION_KEYS: readonly MaterialKey[] = ['emissionR', 'emissionG', 'emissionB'];
const ABSORPTION_KEYS: readonly MaterialKey[] = ['absorptionR', 'absorptionG', 'absorptionB'];
/** The material drivers of a derived legacy key (rejection 11 names derived values; the user edits these). */
const DRIVERS: readonly { keys: readonly (keyof Params)[]; material: readonly MaterialKey[]; design?: readonly DesignKey[] }[] = [
  { keys: ['freeDamp', 'freeBounce', 'meniscusK', 'meniscusDamp', 'angleTiltGain', 'angleGyroGain', 'wetFilm'],
    material: ['viscosity', 'density', 'surfaceTension', 'innerRadius'] },
  { keys: ['liquidTransparency', 'liquid', 'liquidHi', 'liquidLo', 'shadeDepth', 'liquidThin'],
    material: [...ABSORPTION_KEYS, 'scattering', 'exposure', 'ambient'], design: ['tubeBack'] },
  { keys: ['glowStrength', 'edgeGlow', 'lightPhys', 'liquidBright', 'glassOverLiquid'], material: EMISSION_KEYS },
  { keys: ['contactAngle', 'contactHyst'], material: ['contactAngle', 'contactHysteresis'] },
  { keys: ['wetFilm', 'traces', 'traceAmount', 'traceDry', 'traceDrain', 'traceStain', 'traceFilm'],
    material: ['solidsFraction', 'dryingTime', 'viscosity', 'density', 'innerRadius'] },
  { keys: ['fizz', 'fizzCount', 'fizzSize', 'fizzSpeed', 'fizzFoamLife', 'fizzFlatRise', 'fizzEdgeRise', 'fizzDriftGain'],
    material: ['gasMode', 'gasLevel', 'bubbleRadius', 'foamStability', 'viscosity'] },
  { keys: ['highlightBright'], material: ['lightIntensity', 'lightElevation', 'lightSize'] },
];
const PARAM_KEYS = Object.keys(DEFAULT_PARAMS).filter((k) => k.length > 1) as (keyof Params)[];
/** Keys that are also plain words in the realism messages ("a liquid is a free slug"): named only in code
 *  position — `luma(liquid)`, `liquid = …`, `liquid #…`, `liquid 0.4`. */
const PROSE_KEYS: ReadonlySet<string> = new Set(['liquid']);
/** Prose names of legacy keys in the realism messages. */
const PROSE_ALIASES: readonly [RegExp, readonly (keyof Params)[]][] = [
  [/\btube back\b/, ['tubeBack']], [/\bcontact angle\b/, ['contactAngle', 'contactHyst']],
];
const reEsc = (s: string): string => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
/** Keys of `keys` named in `text` (whole-word, longest first; a match is blanked so a shorter key never
 *  matches inside it), in order of first appearance. */
export function namedKeys<K extends string>(text: string, keys: readonly K[]): K[] {
  let s = text;
  const at: [number, K][] = [];
  for (const k of [...keys].sort((a, b) => b.length - a.length)) {
    const re = PROSE_KEYS.has(k) ? new RegExp(`(?<=\\()${reEsc(k)}\\b|\\b${reEsc(k)}(?= [=#\\d])`, 'g') : new RegExp(`\\b${reEsc(k)}\\b`, 'g');
    let first = -1;
    s = s.replace(re, (hit, pos: number) => { if (first < 0) first = pos; return ' '.repeat(hit.length); });
    if (first >= 0) at.push([first, k]);
  }
  return at.sort((a, b) => a[0] - b[0]).map(([, k]) => k);
}
const isDesign = (k: string): k is DesignKey => (DESIGN_KEYS as readonly string[]).includes(k);
const uniq = <T>(a: readonly T[]): T[] => [...new Set(a)];
/** A realism (coherence) message as a problem: every legacy key it names — a design key points at itself,
 *  a derived one at its material drivers (DRIVERS; unknown drivers: none). `text` defaults to the message. */
export function coherenceProblem(message: string, text = message): DeriveProblem {
  const material: MaterialKey[] = [], design: DesignKey[] = [], derived: (keyof Params)[] = [];
  const named = namedKeys(message, PARAM_KEYS);
  for (const [re, keys] of PROSE_ALIASES) if (re.test(message)) named.push(...keys);
  for (const k of named) {
    if (isDesign(k)) { design.push(k); continue; }
    derived.push(k);
    for (const d of DRIVERS) if (d.keys.includes(k)) { material.push(...d.material); design.push(...(d.design ?? [])); }
  }
  return { code: 11, text, material: uniq(material), design: uniq(design), derived: uniq(derived) };
}

/** Every material field finite and in range (invalid ones replaced by the default so the report stays
 *  finite; they are listed as rejections). */
function sanitizeMaterial(input: unknown, reject: (text: string) => void): Material {
  try { return validateMaterial(input); } catch (error) { reject(`rejection 7 (invalid material): ${(error as Error).message}`); }
  const src = (typeof input === 'object' && input !== null ? input : {}) as Record<string, unknown>;
  const m = { ...DEFAULT_MATERIAL };
  for (const meta of MATERIAL_META) {
    const v = src[meta.key];
    if (typeof v === 'number' && Number.isFinite(v) && v >= meta.min && v <= meta.max && (!meta.integer || Number.isInteger(v))) m[meta.key] = v;
  }
  return m;
}
function sanitizeDesign(input: unknown, reject: (text: string) => void): Design {
  try { return validateDesign(input); } catch (error) { reject(`rejection 7 (invalid design): ${(error as Error).message}`); }
  const src = (typeof input === 'object' && input !== null ? input : {}) as Record<string, unknown>;
  const d: Record<string, unknown> = {};
  for (const k of DESIGN_KEYS) {
    try { Object.assign(d, validateDesign({ [k]: src[k] })); } catch { /* dropped, already reported */ }
  }
  return d as Design;
}

/** Design fields that must be integers (enumerations, steps, edge positions); every field with PARAM_META
 *  options is one too. */
const INTEGER_DESIGN: readonly DesignKey[] = [
  'tubeBackGradient', 'digitFont', 'tickStepH', 'tickStepM', 'tickMajorEveryH', 'tickMajorEveryM', 'tickPosH', 'tickPosM',
  'digitMinuteStep', 'digitHourStep', 'digitHourStart', 'digitMinuteStart',
];
const POSITIVE_DESIGN = ['digitScaleX', 'digitScaleY', 'digitScaleXMin', 'digitScaleYMin'] as const;
/** Value checks of the (type-valid) complete design against PARAM_META bounds and the explicit rules;
 *  out-of-range values are rejected (7), never clamped. */
export function designBoundIssues(d: Pick<Params, DesignKey>): string[] {
  const bad: string[] = [];
  const say = (msg: string): void => { bad.push(`rejection 7 (design bounds): ${msg}`); };
  for (const k of DESIGN_KEYS) {
    const v = d[k];
    if (typeof v !== 'number') continue;
    const meta = PARAM_META[k];
    const lo = meta?.min ?? (meta?.options ? 0 : undefined), hi = meta?.max ?? (meta?.options ? meta.options.length - 1 : undefined);
    if (lo !== undefined && v < lo) say(`${k} = ${v} is below its minimum ${lo}`);
    if (hi !== undefined && v > hi) say(`${k} = ${v} is above its maximum ${hi}`);
    if ((INTEGER_DESIGN.includes(k) || meta?.options) && !Number.isInteger(v)) say(`${k} = ${v} must be an integer`);
  }
  if (d.freeHomeK < 0) say(`freeHomeK = ${d.freeHomeK} must be ≥ 0`);
  if (d.playHold < 0) say(`playHold = ${d.playHold} must be ≥ 0`);
  for (const k of ['readTiltStart', 'readTiltEnd'] as const) if (d[k] < 0 || d[k] > 90) say(`${k} = ${d[k]} must be within 0..90°`);
  if (!(d.readTiltStart < d.readTiltEnd)) say(`readTiltStart ${d.readTiltStart} must be below readTiltEnd ${d.readTiltEnd}`);
  for (const k of POSITIVE_DESIGN) if (!(d[k] > 0)) say(`${k} = ${d[k]} must be > 0`);
  return [...new Set(bad)];
}

/** The palette's per-row backing back(t) (buildPalette), 8-bit. */
function backAt(d: Pick<Params, 'tubeBack' | 'tubeBack2' | 'tubeBackGradient'>, t: number): RGB3 {
  const g = Math.round(d.tubeBackGradient);
  const k = g === 1 ? t : g === 2 ? 1 - Math.abs(t * 2 - 1) : g === 3 ? Math.abs(t * 2 - 1) : 0;
  const a = hexRgb(d.tubeBack), b = hexRgb(d.tubeBack2);
  return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
}

export function deriveReport(material: Material, design: Design): DeriveReport {
  const issues: string[] = [], problems: DeriveProblem[] = [];
  /** One rejection: the issue string and the inputs it points at. */
  const reject = (text: string, mat: readonly MaterialKey[] = [], des: readonly DesignKey[] = [], derived: readonly (keyof Params)[] = []): void => {
    issues.push(text);
    problems.push({ code: +(/^rejection (\d+)/.exec(text)?.[1] ?? 0), text, material: uniq(mat), design: uniq(des), derived: uniq(derived) });
  };
  /** Rejection 7: the validators and bounds name the offending key. */
  const rejectNamed = (text: string, what: 'material' | 'design'): void =>
    what === 'material' ? reject(text, namedKeys(text, MATERIAL_KEYS)) : reject(text, [], namedKeys(text, DESIGN_KEYS));
  const m = sanitizeMaterial(material, (t) => rejectNamed(t, 'material'));
  const dIn = sanitizeDesign(design, (t) => rejectNamed(t, 'design'));
  const d = {} as Pick<Params, DesignKey>;
  for (const k of DESIGN_KEYS) (d as Record<string, unknown>)[k] = hasOwn(dIn, k) ? dIn[k] : DEFAULT_PARAMS[k];

  for (const t of designBoundIssues(d)) rejectNamed(t, 'design');
  // layout (tubeLayout limits) and the one physical→display conversion
  const H = Math.max(4, Math.min(TUBE_HEIGHT_MAX, Math.round(d.tubeHeight)));
  if (Math.round(d.tubeHeight) !== H) reject(`rejection 7 (layout): tubeHeight ${d.tubeHeight} outside [4, ${TUBE_HEIGHT_MAX}] px`, [], ['tubeHeight']);
  for (const k of ['hoursY', 'minutesY'] as const) {
    const y = Math.round(d[k]);
    if (y < 0 || y > PANEL_H - H) reject(`rejection 7 (layout): ${k} ${d[k]} puts the ${H} px tube outside the ${PANEL_H} px panel`, [], [k]);
  }
  const Rpx = (H - 1) / 2, r = m.innerRadius, pxPerMm = Rpx / (r + m.wallThickness);

  // dimensionless coordinates (SI inside)
  const mu = m.viscosity / 1000, rho = m.density, gamma = m.surfaceTension / 1000, g = 9.81;
  const muEff = m.viscosity * (1000 / rho) * (2.25 / r) ** 2, x = Math.log10(muEff);
  const Oh = mu / Math.sqrt(rho * gamma * r / 1000);
  const U0 = 25 / pxPerMm / 1000;
  const Ca0 = mu * U0 / gamma;
  const lc = Math.sqrt(gamma / (rho * g)) * 1000;
  const E: RGB3 = [m.emissionR, m.emissionG, m.emissionB], ELum = luma3(E);

  // classes
  const plasma = m.phase === 1, metal = !plasma && m.metallic === 1, emissive = ELum > 0.02;
  const band = bandOf(muEff);
  const viscosity: MaterialClass['viscosity'] = plasma ? 'plasma' : metal ? 'metal' : band;
  const wetting = !plasma && m.contactAngle + m.contactHysteresis < 90;
  const gas: MaterialClass['gas'] = plasma ? 'none' : GAS[m.gasMode];

  const colour = colourLaws({
    material: m, backCentre: backAt(d, 0.5), backWall: backAt(d, (1 + displayOffset(U_WALL, m)) / 2), metal, plasma, emissive, ELum, Rpx, H,
  });
  const { Tsnap, opacity } = colour;
  const classes: MaterialClass = { viscosity, opacity, emissive, wetting, gas };

  // rejections (the design's explicit freeLiquid: an absent key is plasma-derived, not overwritten)
  if (!plasma && !wetting && !(m.contactAngle - m.contactHysteresis > 90))
    reject(`rejection 1 (contact band): contact angle ${m.contactAngle} ± ${m.contactHysteresis} includes 90°`, ['contactAngle', 'contactHysteresis']);
  if (!plasma && m.gasMode === 1 && viscosity !== 'watery')
    reject(`rejection 2 (carbonation): dissolved gas implies a watery liquid, this one is ${viscosity} (μ_eff ${muEff.toPrecision(3)})`,
      ['gasMode', 'viscosity', 'density', 'innerRadius']);
  if (plasma) {
    if (!emissive) reject(`rejection 3 (plasma): a plasma must emit (E_lum ${ELum.toFixed(3)} ≤ 0.02)`, ['phase', ...EMISSION_KEYS]);
    if (m.gasMode !== 0) reject(`rejection 3 (plasma): a plasma has no gas (gasMode ${m.gasMode})`, ['phase', 'gasMode']);
    if (dIn.freeLiquid === true) reject('rejection 3 (plasma): a plasma cannot slide — the design must set freeLiquid false', ['phase'], ['freeLiquid']);
  }
  // the backing colours the palette draws: tubeBack, and tubeBack2 with a gradient
  const backs: [DesignKey, string][] = Math.round(d.tubeBackGradient) !== 0 ? [['tubeBack', d.tubeBack], ['tubeBack2', d.tubeBack2]] : [['tubeBack', d.tubeBack]];
  if (emissive) {
    for (const [k, b] of backs) if (lumaHex(b) >= 16)
      reject(`rejection 4 (emissive backing): backing ${b} luma ${lumaHex(b).toFixed(1)} ≥ 16 behind an emissive liquid`, EMISSION_KEYS, [k]);
  }
  if (opacity === 'clear' && emissive)
    reject(`rejection 5 (clear emitter): a clear liquid (T ${colour.T.toFixed(3)}) cannot emit — a glowing liquid is translucent`, [...EMISSION_KEYS, ...ABSORPTION_KEYS]);
  const El = m.exposure * (m.ambient + 0.5 * m.lightIntensity);
  if (El < 0.01 && !emissive)
    reject(`rejection 6 (nothing to render): no illumination (E_l ${El.toFixed(4)}) and no emission`, ['lightIntensity', 'ambient', 'exposure', ...EMISSION_KEYS]);
  if (colour.unrepresentable)
    reject(`rejection 10 (unrepresentable body): ${colour.unrepresentable} — lower exposure or the backing contrast`,
      ['exposure', ...ABSORPTION_KEYS, 'scattering'], ['tubeBack']);
  if (colour.overexposed)
    reject(`rejection 9 (overexposed): ${colour.overexposed} — lower exposure, lightIntensity, ambient or emission, or darken the backing`,
      ['exposure', 'lightIntensity', 'ambient', ...EMISSION_KEYS], backs.filter(([, b]) => lumaHex(b) >= LIGHT_BACK).map(([k]) => k));
  if (d.digitFont >= SPRITE_FONT && d.digitBottom + 8 * d.digitScaleY > d.tubeHeight)
    reject(`rejection 8 (sprite digits): digitBottom ${d.digitBottom} + 8·digitScaleY ${d.digitScaleY} > tubeHeight ${d.tubeHeight}`,
      [], ['digitBottom', 'digitScaleY', 'tubeHeight']);

  // dynamics
  const V = VISC[viscosity];
  const kFactor = Math.sqrt(m.surfaceTension / 72 * 1000 / rho);
  const meniscusK = plasma ? 400
    : metal ? classClamp(650 * kFactor, VISC.metal.meniscusK)
    : !wetting ? clamp(650 * kFactor, 350, 800)
    : classClamp(jump(x, band, MENISCUS_K) * kFactor, V.meniscusK);
  const wetFilm = plasma || !wetting ? 0 : classClamp(anchored(Math.log10(Ca0), WET_FILM), V.wetFilm);

  // gas
  const gr = GAS_RANGE[gas];
  const rb = m.bubbleRadius / 1000;
  const vbPx = 2 * rho * g * rb * rb / (9 * mu) * 1000 * pxPerMm;
  const fizzSpeed = classClamp(anchored(Math.log10(Math.max(vbPx, 1e-12)), FIZZ_SPEED), gr?.speed);
  const s = Math.min(1, fizzSpeed / 30);
  const fizzCount = gas === 'carbonated' ? Math.round(30 + 30 * m.gasLevel)
    : gas === 'boiling' ? Math.round(45 + 15 * m.gasLevel) : gas === 'trapped' ? Math.round(120 * m.gasLevel) : 0;

  const lens = Math.min(1, 0.45 * (m.ior - 1) / 0.333);
  const derived: Pick<Params, DerivedKey> = {
    ...colour.params,
    rimTint: '#000000',
    glassWall: m.wallThickness * pxPerMm,
    lightPhys: emissive ? 0 : 1,
    lightAngle: m.lightElevation / 2,
    ambientLight: 0,   // the derived colours already carry the white room light (highlight, rim); ambientize would desaturate twice
    liquidBright: emissive ? 1.3 : 1,
    tickLens: lens,
    bottomLens: lens,
    edgeGlow: emissive ? Math.round(18 + 16 * Math.min(1, ELum)) : metal ? 0 : 19,
    glowStrength: emissive ? anchored(ELum, GLOW) : metal ? 0 : Math.min(0.25, 0.08 * m.lightIntensity * Tsnap),
    frontBright: metal ? 20 : emissive ? Math.round(16 * Math.min(1, ELum) + 4) : 0,
    edgeLightGain: emissive ? 0.3 : 0.55,
    edgeSoft: wetting ? 2.4 : 0,
    surfaceFill: clamp(1 - 0.9 * Tsnap),
    surfaceBlick: 0.9 * colour.params.highlightBright,
    contactAngle: plasma ? 100 : m.contactAngle,
    contactHyst: plasma ? 0 : m.contactHysteresis,
    contactDyn: plasma ? 0 : Math.min(90, Math.cbrt(9 * Ca0 * 9.2) * 180 / Math.PI),
    capLength: lc * pxPerMm * MM_PER_PX,   // render px-mm: (boreR·MM_PER_PX / capLength)² = (r / lc)²
    freeDamp: classClamp(jump(x, band, FREE_DAMP), V.freeDamp),
    freeBounce: classClamp(anchored(Math.log10(Oh), FREE_BOUNCE), V.freeBounce),
    meniscusK,
    meniscusDamp: plasma ? 30 : classClamp(jump(x, band, MENISCUS_DAMP), V.meniscusDamp),
    meniscusInertia: plasma ? 0 : metal ? 4 : anchored(x, INERTIA),
    angleTiltGain: plasma ? 0.5 : metal ? 2 : classClamp(jump(x, band, TILT), V.angleTiltGain),
    angleGyroGain: plasma ? 0.03 : metal ? 0.4 : classClamp(jump(x, band, GYRO), V.angleGyroGain),
    angleMax: plasma ? 2 : 6,
    wetFilm,
    traces: wetting && m.solidsFraction > 0,
    traceAmount: 0.3 + 1.7 * m.solidsFraction * (1 - Tsnap),
    traceDry: clamp(m.dryingTime, 0.1, 2),
    // a wall film at the thin-film cap (h = r/10) runs down at ρgh²/3μ under 1 g (physics drainTrace), px/s
    traceDrain: rho * g * (0.1 * r * 1e-3) ** 2 / (3 * mu) * 1000 * pxPerMm,
    traceStain: 0.05 + 0.65 * m.solidsFraction,
    traceFilm: 0.05 * m.solidsFraction * clamp(x / X_V),
    fizz: gas !== 'none',
    fizzCount,
    fizzSize: clamp(2 * m.bubbleRadius * pxPerMm, ...FIZZ_SIZE),
    fizzSpeed,
    fizzFoamLife: m.foamStability,
    fizzFlatRise: 0.15 + 0.3 * s,
    fizzEdgeRise: 0.2 + 0.3 * s,
    fizzDriftGain: 0.4 + 0.6 * s,
  };
  const fixed: Pick<Params, FixedKey> = {
    v: PARAMS_VERSION, highlightInset: 0,
    surfaceBand: 0.35, surfaceRim: 0.45, surfaceWidth: 4, surfaceTone: 0, freeGain: 570,
    ...(plasma
      ? { fillK: 260, fillDamp: 22, fillSloshGain: 0.5, angleK: 300, angleDamp: 26 }
      : { fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207, angleDamp: 17.6 }),
    acrossK: 200, acrossDamp: 20, acrossGyroGain: 0, shakeGain: 0, deadzone: 0,
    accelLpHz: 15.2, gyroHpHz: 5, gyroDeadzone: 31, gyroMax: 470, inputGain: 1,
    bubble: false, bubbleW: DEFAULT_PARAMS.bubbleW, bubbleH: DEFAULT_PARAMS.bubbleH, bubbleGap: DEFAULT_PARAMS.bubbleGap,
    bubbleY: DEFAULT_PARAMS.bubbleY, bubbleRollGain: DEFAULT_PARAMS.bubbleRollGain, bubbleTiltGain: DEFAULT_PARAMS.bubbleTiltGain,
  };
  const designPart: Pick<Params, DesignKey> = { ...d, freeLiquid: plasma ? false : d.freeLiquid };
  const params = { ...designPart, ...derived, ...fixed } as Params;
  // a pre-image body (opaque / translucent / metal) settled on the real palette's centre row, before the rim is fitted over it
  if (!plasma && opacity !== 'clear') params.liquid = settleLiquid(params, q565([0, 1, 2].map((i) => enc255(colour.C0[i] + E[i]))));
  let rim = { gain: 0, error: 0, rimError: 0, bodyOver: 0 };
  if (params.rimLight > 0) {
    const { tint, ...fit } = fitRim(params, displayOffset(U_WALL, m), colour.Wall, E);
    rim = fit;
    params.rimLight = fit.gain;
    params.rimTint = tint;
    if (fit.rimError > RIM_TOLERANCE)
      reject(`rejection 12 (unattainable rim (${fit.rimError} levels)): the side-light rim misses the wall sample by ${fit.rimError} > ${RIM_TOLERANCE} levels even at rimLight ${fit.gain} (rimTint ${tint}) — the wall leaves the rim term no reach; thin the wall or widen the bore`,
        ['wallThickness', 'innerRadius']);
    else if (fit.bodyOver > BODY_OVER_TOLERANCE)
      reject(`rejection 12 (unrepresentable wall shading (${fit.bodyOver} levels)): the body-only wall row is ${fit.bodyOver} levels above the target with the rim at 0 — the class's shadeDepth floor shades more than this flat-lit body does; lower ambient or exposure, or raise the light`,
        ['ambient', 'exposure', 'lightIntensity']);
  }
  // the complete result must satisfy the realism rules of its inferred classes; design fields are never
  // rewritten, a contradiction is a rejection. Skipped when the material is already rejected on its own
  // (1–6, 8–10, 12): the checker would only echo that reason.
  if (issues.every((s) => s.startsWith('rejection 7 ')))
    for (const msg of coherenceIssues(params, classes)) {
      const p = coherenceProblem(msg);
      reject(`rejection 11 (design contradicts the material's realism rules): ${msg}`, p.material, p.design, p.derived);
    }

  return {
    params, classes, residual: colour.residual, rim, issues, problems,
    body: { centre: colour.C0, wall: colour.Wall, wallOffset: displayOffset(U_WALL, m) },
    coords: { muEff, x, Oh, Ca0, lc, pxPerMm, T: colour.T, Tsnap, ELum, Tlum: colour.Tlum, Tmax: colour.Tmax, Tup: colour.Tup },
  };
}

/** Overlays zeroed and the panel dimmer at 1: the palette rows then carry only the body, the part the
 *  derivation fits (check-materials reads the same rows). */
export const BODY_ONLY: Partial<Params> = {
  brightness: 1, highlightBright: 0, glassHiBright: 0, glassReflect: 0, glassBody: 0, glassRim: 0, glassWallGlow: 0, wallWet: 1, ambientLight: 0,
};
/** RGB565 round trip of 8-bit channels (rounded, clamped). */
export const q565 = (c: readonly number[]): RGB3 =>
  rgb565to888(rgb565(...(c.map((v) => Math.round(clamp(v, 0, 255))) as [number, number, number]))) as RGB3;
/** Largest accepted miss of the fitted wall row against its target, 8-bit levels (rejection 12 above). */
export const RIM_TOLERANCE = 5;
/** Bounded allowance for a channel ABOVE the target with the rim at 0: one RGB565 5-bit step (the luma-only
 *  shadeDepth fit magnified by the quantisation, glow's blue); more is an unrepresentable body, rejection 12. */
export const BODY_OVER_TOLERANCE = 8;
/** The centre row settled on the real palette: the pre-image is rounded to 8 bits and the row then truncated
 *  to RGB565, so a sub-level rounding loss can cross a 5-bit step (8 levels) the target does not. Per channel,
 *  of the rounded pre-image and its ±1 neighbours (±1 always outweighs a rounding loss of ≤ ½·(1 − T)), the
 *  value whose body-only centre row (rimLight 0; RGB565) is nearest the target is taken; ties keep the rounded one. */
function settleLiquid(p: Params, target: RGB3): string {
  const q = { ...p, ...BODY_ONLY, rimLight: 0 }, base = hexRgb(p.liquid);
  const y = Math.floor((buildPalette(q, 0).rows.length - 1) / 2);
  const best = [...base], err = [Infinity, Infinity, Infinity];
  for (const k of [0, -1, 1]) {
    const c = base.map((v) => clamp(v + k, 0, 255));
    const got = rgb565to888(buildPalette({ ...q, liquid: rgbHex(c) }, 0).rows[y]);
    for (let i = 0; i < 3; i++) if (Math.abs(got[i] - target[i]) < err[i]) { err[i] = Math.abs(got[i] - target[i]); best[i] = c[i]; }
  }
  return rgbHex(best);
}
/** rimLight gains tried in order: the smallest at which no channel of the solved tint saturates wins. */
const RIM_GAINS = [1, 2, 3, 4] as const;
/** The side-light rim fit on the real palette: for each gain of RIM_GAINS the tint is solved (solveRimTint);
 *  the first gain whose tint has no channel at 255 is taken (else the largest). The fitted body-only wall
 *  row is then measured against the target after the RGB565 round trip: `error` is the worst channel's
 *  miss in levels; `rimError` the worst over the channels the rim answers for (rejection 12 when it exceeds
 *  RIM_TOLERANCE — never a silent saturation), i.e. all but a channel whose tint is 0 with the row above the
 *  target: that overshoot (`bodyOver`) is the body shading's, the additive rim cannot lower it. */
function fitRim(p: Params, d: number, wall: RGB3, E: RGB3): { gain: number; tint: string; error: number; rimError: number; bodyOver: number } {
  const q = { ...p, ...BODY_ONLY }, H = buildPalette({ ...q, rimLight: 0 }, 0).rows.length, yc = (H - 1) / 2;
  const y = Math.round(yc * (1 + d));
  const target = q565([0, 1, 2].map((i) => enc255(wall[i] + E[i])));
  let gain: number = RIM_GAINS[0], tint = '#000000';
  for (gain of RIM_GAINS) {
    tint = solveRimTint({ ...q, rimLight: gain }, y, target);
    if (!hexRgb(tint).some((v) => v >= 255)) break;
  }
  const got = rgb565to888(buildPalette({ ...q, rimLight: gain, rimTint: tint }, 0).rows[y]), t = hexRgb(tint);
  const miss = [0, 1, 2].map((i) => got[i] - target[i]), body = [0, 1, 2].map((i) => t[i] === 0 && miss[i] > 0);
  return {
    gain, tint, error: Math.max(...miss.map(Math.abs)),
    rimError: Math.max(0, ...miss.filter((_, i) => !body[i]).map(Math.abs)),
    bodyOver: Math.max(0, ...miss.filter((_, i) => body[i])),
  };
}
/** rimTint solved on the real palette at the given gain: the body-only rows `q` read at the wall sample's
 *  display row y = round(yc·(1 + d)). The first estimate is the doc's (target − P_w)/u² with P_w the row at
 *  rimLight 0 and u the palette's row coordinate there (≈ d); target = the wall sample (B_w + side light) + E,
 *  encoded, after the RGB565 round trip. P_w is itself quantised, so each channel is settled on the rendered
 *  row: the integer tint 0..255 whose RGB565 row channel is nearest the target (the row is monotone in the
 *  tint; a bisection, eight palettes). */
function solveRimTint(q: Params, y: number, target: RGB3): string {
  const row = (t: readonly number[]): RGB3 => rgb565to888(buildPalette({ ...q, rimTint: rgbHex(t) }, 0).rows[y]) as RGB3;
  // lowest tint whose row reaches the target, per channel (255 when none does)
  let lo = [0, 0, 0], hi = [255, 255, 255];
  while (lo.some((v, i) => v < hi[i])) {
    const mid = lo.map((v, i) => (v + hi[i]) >> 1), got = row(mid);
    lo = lo.map((v, i) => (v < hi[i] && got[i] < target[i] ? mid[i] + 1 : v));
    hi = hi.map((v, i) => (lo[i] < v && got[i] >= target[i] ? mid[i] : v));
  }
  // …or the one below it when that row is nearer
  const below = lo.map((v) => Math.max(0, v - 1)), gA = row(lo), gB = row(below);
  return rgbHex([0, 1, 2].map((i) => (Math.abs(gB[i] - target[i]) < Math.abs(gA[i] - target[i]) ? below[i] : lo[i])));
}

/** derive(material, design) → Params; throws an Error listing every rejection. */
export function derive(material: Material, design: Design): Params {
  const r = deriveReport(material, design);
  if (r.issues.length) throw new Error(`material rejected:\n- ${r.issues.join('\n- ')}`);
  return r.params;
}

function hasOwn<T extends object>(o: T, k: PropertyKey): k is keyof T {
  return Object.prototype.hasOwnProperty.call(o, k);
}
