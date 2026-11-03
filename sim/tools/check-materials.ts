// Regression fixtures for the material coherence validator (src/material/coherence.ts): every rule
// family gets a passing Params built from a signature preset of that class plus one minimal mutation
// that must yield exactly that rule's message; every range is probed at its endpoints (pass) and one
// step outside (fail); every signature preset with a Material yields no issue. Run: npm run check:materials
declare const process: any; declare function require(m: string): any;
import { PRESETS, presetParams, type Material, type Params } from '../src/params';
import { MARK_CONTRAST_PER_T, VISC, coherenceIssues, hex, luma, sat } from '../src/material/coherence';
import {
  DEFAULT_MATERIAL, DESIGN_KEYS, MATERIAL_KEYS, MATERIAL_META, MATERIAL_VERSION, migrateMaterial, parseMaterialEnvelope,
  serializeMaterialEnvelope, validateDesign, validateMaterial, type Design, type Material as MaterialProps,
} from '../src/material/model';
import { DEFAULT_PARAMS, PARAMS_VERSION } from '../src/params';
import { BODY_ONLY, BODY_OVER_TOLERANCE, RIM_TOLERANCE, coherenceProblem, derive, deriveReport, ownershipIssues, q565, type DeriveProblem, type DeriveReport } from '../src/material/derive';
import { PARAM_META } from '../src/params';
import { buildPalette } from '../src/render';
import { PHYS_DT, newTube, stepTube } from '../src/physics';
import { rgb565, rgb565to888 } from '../../spec/layout';
import { MATERIAL_PRESETS, materialPresetFile, physicalPresetFile } from '../src/material/presets';
import { compositeResidual, displayOffset, enc255, hexRgb, km, opacityOf, paletteChord, preImage, sampleRow, snapT, U_WALL, type KM } from '../src/material/optical';
import { traceRow } from '../src/material/optics/geometry';
import { beer, fresnel, refract, type PhysicalParams } from '../src/material/optics/optics';

type Visc = Material['viscosity'];
type R = [number, number];
let fixtures = 0, failures = 0;

function report(name: string, got: string[], want: string[]): void {
  fixtures++;
  const same = got.length === want.length && got.every((g, i) => g === want[i]);
  console.log(`${name}: ${same ? 'ok' : 'FAIL'}`);
  if (same) return;
  failures++;
  for (const w of want) console.log(`  - want: ${w}`);
  for (const g of got) console.log(`  - got:  ${g}`);
  if (!want.length) console.log('  - want: (no issues)');
  if (!got.length) console.log('  - got:  (no issues)');
}

function entry(id: string) {
  const e = PRESETS.find((x) => x.id === id);
  if (!e || !e.mat) throw new Error(`fixture base ${id} is not a signature preset with a material`);
  return e;
}
/** Params + Material of a signature preset with a mutation (and optional material override) applied. */
function build(id: string, set: Partial<Params> = {}, mat: Partial<Material> = {}): { p: Params; m: Material } {
  const e = entry(id);
  return { p: { ...presetParams(e), ...set }, m: { ...e.mat!, ...mat } };
}
function expect(name: string, id: string, set: Partial<Params>, want: string[], mat: Partial<Material> = {}): void {
  const { p, m } = build(id, set, mat);
  report(name, coherenceIssues(p, m), want);
}
const r6 = (v: number): number => +v.toFixed(6);

/** Probe an inclusive range [lo, hi] on one key: endpoints pass, endpoint ∓ step fails with msg(v).
 *  lo / hi = null means that side is unbounded (not probed). */
function range(name: string, id: string, key: keyof Params, lo: number | null, hi: number | null, step: number,
  msg: (v: number) => string, setup: Partial<Params> = {}, mat: Partial<Material> = {}): void {
  const at = (v: number): Partial<Params> => ({ ...setup, [key]: v });
  if (lo !== null) {
    expect(`${name} ${String(key)}=${lo} (low end)`, id, at(lo), [], mat);
    const v = r6(lo - step);
    expect(`${name} ${String(key)}=${v} (below)`, id, at(v), [msg(v)], mat);
  }
  if (hi !== null) {
    expect(`${name} ${String(key)}=${hi} (high end)`, id, at(hi), [], mat);
    const v = r6(hi + step);
    expect(`${name} ${String(key)}=${v} (above)`, id, at(v), [msg(v)], mat);
  }
}

// ---------------------------------------------------------------------------------------------
// 0. Signature presets: every preset with a material is coherent (the set check:presets reports ok).
let withMat = 0;
for (const e of PRESETS) {
  if (!e.mat) continue;
  withMat++;
  report(`preset ${e.id}`, coherenceIssues(presetParams(e), e.mat), []);
}
report(`presets with a material: ${withMat} (> 0)`, withMat > 0 ? [] : ['no signature preset has a material'], []);

// ---------------------------------------------------------------------------------------------
// 1. Viscosity. Pinned copy of the class table (presets/PRESETS.md) so a silently widened range
//    in VISC fails here instead of passing its own fixtures.
const PINNED: Record<Visc, Record<string, R>> = {
  watery:  { freeDamp: [0.4, 1.5], freeBounce: [0.15, 0.35], meniscusK: [400, 550], meniscusDamp: [3, 16], wetFilm: [8, 15], angleTiltGain: [5, 9], angleGyroGain: [0.3, 0.55] },
  medium:  { freeDamp: [1.5, 4], freeBounce: [0.05, 0.15], meniscusK: [200, 350], meniscusDamp: [12, 25], wetFilm: [12, 20], angleTiltGain: [3, 5], angleGyroGain: [0.15, 0.35] },
  viscous: { freeDamp: [6, 14], freeBounce: [0, 0], meniscusK: [60, 150], meniscusDamp: [25, 50], wetFilm: [20, 30], angleTiltGain: [0.5, 2.5], angleGyroGain: [0.02, 0.12] },
  metal:   { freeDamp: [0.8, 1.5], freeBounce: [0.4, 0.7], meniscusK: [500, 800], meniscusDamp: [8, 16], wetFilm: [0, 0], angleTiltGain: [1.5, 3], angleGyroGain: [0.3, 0.5] },
  plasma:  { fillSloshGain: [0, 1], angleTiltGain: [0, 1], angleGyroGain: [0, 0.06], wetFilm: [0, 0] },
};
report('VISC table matches the pinned class table', JSON.stringify(VISC) === JSON.stringify(PINNED) ? [] : [`VISC = ${JSON.stringify(VISC)}`], []);

// class base + the setup that makes it wetting where the class base is not (wetFilm / meniscusK
// follow the class only for a wetting liquid)
const CLASS_BASE: Record<Visc, { id: string; wet?: { set: Partial<Params>; mat: Partial<Material> } }> = {
  watery: { id: 'urine' },
  medium: { id: 'blood' },
  viscous: { id: 'honey' },
  metal: { id: 'mercury', wet: { set: { contactAngle: 40 }, mat: { wetting: true } } },
  plasma: { id: 'xenon', wet: { set: { contactAngle: 40 }, mat: { wetting: true } } },
};
for (const v of Object.keys(PINNED) as Visc[]) {
  const b = CLASS_BASE[v];
  for (const [key, [lo, hi]] of Object.entries(PINNED[v])) {
    const wetKey = key === 'wetFilm' || key === 'meniscusK';
    const setup = wetKey && b.wet ? b.wet.set : {}, mat = wetKey && b.wet ? b.wet.mat : {};
    const step = hi >= 50 ? 1 : 0.01;
    range(`visc ${v}${wetKey && b.wet ? ' (wetting)' : ''}`, b.id, key as keyof Params, lo, hi, step,
      (x) => `${key} = ${x} not in [${lo}, ${hi}] for ${v}`, setup, mat);
  }
}
// non-wetting: surface-tension dominated whatever the bulk class
for (const id of ['mercury', 'molten']) {
  const v = entry(id).mat!.viscosity;
  range(`non-wetting ${id}`, id, 'meniscusK', 350, 800, 1, (x) => `meniscusK (non-wetting) = ${x} not in [350, 800] for ${v}`);
}
// slug on / off
expect('plasma freeLiquid on', 'xenon', { freeLiquid: true }, ['plasma is not a slug: freeLiquid must be off']);
expect('liquid freeLiquid off', 'urine', { freeLiquid: false }, ['a liquid is a free slug: freeLiquid must be on']);
expect('pinned slug skips freeGain', 'xenon', { freeGain: 100 }, []);
range('slug', 'urine', 'freeGain', 500, 800, 1, (x) => `freeGain ${x} is gravity, the same for every liquid: 500–800`);
// plasma meniscus dynamics
const PLASMA_DYN = 'plasma has no meniscus dynamics (inertia/hysteresis/dynamic angle must be 0)';
expect('plasma meniscusInertia', 'xenon', { meniscusInertia: 0.5 }, [PLASMA_DYN]);
expect('plasma contactHyst', 'xenon', { contactHyst: 5 }, [PLASMA_DYN]);
expect('plasma contactDyn', 'xenon', { contactDyn: 1 }, [PLASMA_DYN]);
range('plasma', 'xenon', 'angleMax', null, 3, 0.01, () => 'plasma: angleMax ≤ 3');

// ---------------------------------------------------------------------------------------------
// 2. Opacity
range('opaque', 'blood', 'liquidTransparency', null, 0.12, 0.01, (x) => `opaque: liquidTransparency ${x} > 0.12`);
range('opaque', 'blood', 'shadeDepth', 0.5, 0.95, 0.01, (x) => `opaque: shadeDepth ${x} not in [0.5, 0.95]`);
// rear marks: markContrast within [0, 120·T] in every class (a floor may fake at most what the liquid lets through)
const markCap = (id: string): number => +(MARK_CONTRAST_PER_T * presetParams(entry(id)).liquidTransparency).toFixed(2);
const markMsg = (id: string) => (x: number): string => {
  const t = presetParams(entry(id)).liquidTransparency;
  return `rear marks: markContrast ${x} > ${markCap(id)} (${MARK_CONTRAST_PER_T} × liquidTransparency ${+t.toFixed(3)}) fakes more than the liquid lets through`;
};
range('opaque rear ticks', 'blood', 'markContrast', null, markCap('blood'), 0.01, markMsg('blood'), { ticksOnTop: false });
range('opaque rear digits', 'blood', 'markContrast', null, markCap('blood'), 0.01, markMsg('blood'), { digitsOnTop: false });
expect('opaque rear marks, markContrast 0', 'blood', { ticksOnTop: false, digitsOnTop: false, markContrast: 0 }, []);
expect('opaque on-top marks ignore markContrast', 'blood', { markContrast: 30 }, []);
range('translucent', 'urine', 'liquidTransparency', 0.25, 0.55, 0.01, (x) => `translucent: liquidTransparency ${x} not in [0.25, 0.55]`);
range('translucent', 'urine', 'shadeDepth', 0.4, 0.85, 0.01, (x) => `translucent: shadeDepth ${x} not in [0.4, 0.85]`);
expect('translucent rear marks need no markContrast', 'urine', { ticksOnTop: false, digitsOnTop: false, markContrast: 0 }, []);
range('translucent rear marks', 'urine', 'markContrast', null, markCap('urine'), 0.01, markMsg('urine'), { ticksOnTop: false, digitsOnTop: false });
range('clear', 'frizzante', 'liquidTransparency', 0.7, null, 0.01, (x) => `clear: liquidTransparency ${x} < 0.7`);
expect('clear liquidTransparency=1', 'frizzante', { liquidTransparency: 1 }, []);
range('clear', 'frizzante', 'shadeDepth', 0.3, 0.55, 0.01, (x) => `clear: shadeDepth ${x} not in [0.3, 0.55]`);
range('clear', 'frizzante', 'glassOverLiquid', 0.5, null, 0.01, (x) => `clear: glassOverLiquid ${x} < 0.5`);
// neutral liquidHi: saturation < 0.2 (exclusive); #ffffcc is exactly 0.2
report('sat(#ffffcc) = 0.2, sat(#ffffcd) < 0.2', sat('#ffffcc') === 0.2 && sat('#ffffcd') < 0.2 ? [] : ['helper sat drifted'], []);
expect('clear liquidHi #ffffcd (sat 0.196)', 'frizzante', { liquidHi: '#ffffcd' }, []);
expect('clear liquidHi #ffffcc (sat 0.20)', 'frizzante', { liquidHi: '#ffffcc' }, ['clear: liquidHi #ffffcc is a white surface reflection (saturation 0.20 ≥ 0.2)']);
expect('clear liquidHi #c8f0ff (tinted)', 'frizzante', { liquidHi: '#c8f0ff' }, ['clear: liquidHi #c8f0ff is a white surface reflection (saturation 0.22 ≥ 0.2)']);
range('clear rear ticks', 'frizzante', 'markContrast', 16, null, 1, (x) => `clear rear marks: markContrast ${x} < 16`, { ticksOnTop: false });
range('clear rear digits', 'frizzante', 'markContrast', 16, null, 1, (x) => `clear rear marks: markContrast ${x} < 16`, { digitsOnTop: false });
range('clear rear marks', 'frizzante', 'markContrast', null, markCap('frizzante'), 0.01, markMsg('frizzante'), { digitsOnTop: false });
expect('clear on-top marks, markContrast 0', 'frizzante', { markContrast: 0 }, []);

// ---------------------------------------------------------------------------------------------
// 3. Light
range('emissive', 'glow', 'glowStrength', 0.4, 0.8, 0.01, (x) => `emissive: glowStrength ${x} not in [0.4, 0.8]`);
range('emissive', 'glow', 'edgeGlow', 18, 34, 1, (x) => `emissive: edgeGlow ${x} not in [18, 34]`);
range('emissive', 'glow', 'lightPhys', 0, 0, 0.01, () => 'emissive: lightPhys must be 0 (it is its own light)');
range('emissive', 'glow', 'glassOverLiquid', null, 0.4, 0.01, (x) => `emissive: glassOverLiquid ${x} > 0.4`);
range('emissive', 'glow', 'liquidBright', 1.15, 1.5, 0.01, (x) => `emissive: liquidBright ${x} not in [1.15, 1.5]`);
// tube back luma < 16 (exclusive): #0f0f0f = 15 passes, #101011 = 16.1 fails
expect('emissive tubeBack #0f0f0f (luma 15)', 'glow', { tubeBack: '#0f0f0f' }, []);
expect('emissive tubeBack #101011 (luma 16.1)', 'glow', { tubeBack: '#101011' }, ['emissive: tube back luma 16 ≥ 16']);
expect('emissive tubeBack #202020 (luma 32)', 'glow', { tubeBack: '#202020' }, ['emissive: tube back luma 32 ≥ 16']);
range('not emissive', 'blood', 'glowStrength', null, 0.25, 0.01, (x) => `not emissive: glowStrength ${x} > 0.25`);
range('not emissive', 'blood', 'lightPhys', 0.2, null, 0.01, (x) => `not emissive: lightPhys ${x} < 0.2`);

// ---------------------------------------------------------------------------------------------
// 4. Wetting: the whole hysteresis band stays on one side of 90° (exclusive)
{
  const h = build('urine').p.contactHyst;
  expect(`wetting contactAngle ${90 - h} ± ${h} (touches 90°)`, 'urine', { contactAngle: 90 - h }, [`wetting: contact angle ${90 - h} ± ${h} must stay below 90° (concave)`]);
  expect(`wetting contactAngle ${r6(90 - h - 0.01)} ± ${h}`, 'urine', { contactAngle: r6(90 - h - 0.01) }, []);
  expect('wetting contactHyst widened to 90°', 'urine', { contactHyst: 70 }, ['wetting: contact angle 20 ± 70 must stay below 90° (concave)']);
  const hm = build('mercury').p.contactHyst;
  expect(`non-wetting contactAngle ${90 + hm} ± ${hm} (touches 90°)`, 'mercury', { contactAngle: 90 + hm }, [`non-wetting: contact angle ${90 + hm} ± ${hm} must stay above 90° (convex)`]);
  expect(`non-wetting contactAngle ${r6(90 + hm + 0.01)} ± ${hm}`, 'mercury', { contactAngle: r6(90 + hm + 0.01) }, []);
  expect('non-wetting contactHyst widened to 90°', 'mercury', { contactHyst: 50 }, ['non-wetting: contact angle 140 ± 50 must stay above 90° (convex)']);
  range('non-wetting', 'mercury', 'wetFilm', null, 0, 0.01, (x) => `non-wetting: wetFilm ${x} must be 0`);
}

// ---------------------------------------------------------------------------------------------
// 5. Traces
const TRACES_WET = 'traces need a wetting liquid: non-wetting / plasma must have them off';
expect('non-wetting traces on', 'mercury', { traces: true }, [TRACES_WET]);
expect('non-wetting traces on (molten)', 'molten', { traces: true }, [TRACES_WET]);
expect('plasma traces on', 'xenon', { traces: true }, [TRACES_WET]);
expect('wetting plasma traces on', 'xenon', { traces: true, contactAngle: 40 }, [TRACES_WET], { wetting: true });
expect('wetting plasma traces off', 'xenon', { contactAngle: 40 }, [], { wetting: true });
expect('wetting traces off', 'urine', { traces: false }, []);
expect('wetting traces off ignores out-of-range trace knobs', 'urine', { traces: false, traceAmount: 5, traceDrain: -1 }, []);
range('traces', 'blood', 'traceAmount', 0.2, 2, 0.01, (x) => `traceAmount ${x} not in [0.2, 2]`);
range('traces', 'blood', 'traceDry', 0.1, 2, 0.01, (x) => `traceDry ${x} not in [0.1, 2]`);
range('traces', 'blood', 'traceDrain', 0, 20000, 0.01, (x) => `traceDrain ${x} not in [0, 20000]`);
range('traces', 'blood', 'traceStain', 0.05, 0.7, 0.01, (x) => `traceStain ${x} not in [0.05, 0.7]`);
range('traces', 'blood', 'traceFilm', 0, 1, 0.01, (x) => `traceFilm ${x} not in [0, 1]`);
range('traces viscous', 'honey', 'traceDrain', null, 20, 0.01, (x) => `viscous: traceDrain ${x} > 20`);
range('traces watery', 'urine', 'traceDrain', 100, null, 0.01, (x) => `watery: traceDrain ${x} < 100`, { traces: true });
expect('traces medium traceDrain 0 fine', 'blood', { traceDrain: 0 }, []);

// ---------------------------------------------------------------------------------------------
// 6. Gas
expect('no gas, fizz on', 'blood', { fizz: true }, ['no gas: fizz must be off']);
expect('carbonated, fizz off', 'frizzante', { fizz: false }, ['carbonated: fizz must be on']);
expect('boiling, fizz off', 'cryo', { fizz: false }, ['boiling: fizz must be on']);
expect('trapped, fizz off', 'honey', { fizz: false }, ['trapped: fizz must be on']);
const GAS: Array<[string, string, R, R]> = [
  ['carbonated', 'frizzante', [30, 55], [30, 60]],
  ['carbonated', 'cola', [30, 55], [30, 60]],
  ['boiling', 'cryo', [45, 60], [45, 60]],
  ['trapped', 'honey', [0, 8], [0, 120]],
  ['trapped', 'molten', [0, 8], [0, 120]],
];
for (const [gas, id, speed, count] of GAS) {
  const v = entry(id).mat!.viscosity;
  const probe = (key: 'fizzSpeed' | 'fizzCount', [lo, hi]: R, step: number): void =>
    range(`${gas} ${id}`, id, key, lo, hi, step, (x) => `${key} = ${x} not in [${lo}, ${hi}] for ${v}`);
  probe('fizzSpeed', speed, 1); probe('fizzCount', count, 1);
  // the size is the look's (bubble radius), not the class's: the whole drawable range is coherent
  for (const fizzSize of [1, 8, 16]) expect(`${gas} ${id} fizzSize ${fizzSize}`, id, { fizzSize }, []);
}
const CARB: Partial<Params> = { fizz: true, fizzSize: 1.5, fizzSpeed: 40, fizzCount: 40 };
expect('carbonated medium', 'malt', CARB, ['carbonated implies watery'], { gas: 'carbonated' });
expect('carbonated watery', 'urine', CARB, [], { gas: 'carbonated' });

// ---------------------------------------------------------------------------------------------
// 7. Colour & scale
expect('liquidHi = liquid', 'blood', { liquidHi: '#6e0b16' }, ['luma(liquid) < luma(liquidHi)']);
expect('liquidHi darker than liquid', 'blood', { liquidHi: '#400000' }, ['luma(liquid) < luma(liquidHi)']);
report('luma grey 40 = 40, grey 39 < 40', luma('#282828') === 40 && luma('#272727') < 40 ? [] : ['helper luma drifted'], []);
// ink: black tube back, ticks and digits on top (sprite font → digitColor rule off)
for (const k of ['tickColorH', 'tickMajorColorH', 'tickColorM', 'tickMajorColorM'] as const) {
  expect(`on-top ${k} #282828 (40 from back)`, 'ink', { [k]: '#282828' }, []);
  expect(`on-top ${k} #272727 (39 from back)`, 'ink', { [k]: '#272727' }, [`on-top ${k} #272727 is < 40 luma from the tube back (invisible on the dry side)`]);
  expect(`rear ${k} #000000 not checked`, 'urine', { [k]: '#000000' }, []);
}
expect('on-top dark-on-light tick fine', 'phosphor', { tickColorH: '#000000' }, []);
// glow: vector font (3), digits on top
expect('on-top digitColor #282828 (40 from back)', 'glow', { tubeBack: '#000000', digitColor: '#282828' }, []);
expect('on-top digitColor #272727 (39 from back)', 'glow', { tubeBack: '#000000', digitColor: '#272727' }, ['on-top digitColor #272727 < 40 luma from the tube back']);
expect('rear digitColor not checked', 'glow', { digitsOnTop: false, digitColor: '#020602', markContrast: 0 }, []);
expect('sprite font digitColor not checked', 'ink', { digitColor: '#000000' }, []);
// sprite fonts (digitFont ≥ 5) must fit the hours tube
const FIT = 'sprite font, hours tube: digitScaleY ≤ digitScaleX and baseline + 8·scaleY ≤ tubeHeight (glyph must fit the tube)';
{
  const { p } = build('frizzante');
  const top = r6(p.tubeHeight - 8 * p.digitScaleY);
  range('sprite fit', 'frizzante', 'digitBottom', null, top, 0.01, () => FIT);
  range('sprite fit', 'frizzante', 'digitScaleY', null, p.digitScaleX, 0.01, () => FIT);
  expect('sprite fit digitFont 5 applies', 'frizzante', { digitFont: 5, digitScaleY: p.digitScaleX + 0.5 }, [FIT]);
  expect('vector font digitFont 4 exempt', 'frizzante', { digitFont: 4, digitScaleY: p.digitScaleX + 0.5, digitBottom: 60 }, []);
}
// specular: highlightBright × liquidBright ≤ 1.3 for non-metal, non-emissive
range('specular', 'blood', 'highlightBright', null, 1.3, 0.01, (x) => `highlightBright × liquidBright = ${x.toFixed(2)} > 1.3 burns a white stripe`, { liquidBright: 1 });
expect('specular: metal exempt', 'mercury', { highlightBright: 2, liquidBright: 1.5 }, []);
expect('specular: emissive exempt', 'glow', { highlightBright: 2 }, []);
range('trim', 'urine', 'liquidBright', 0.9, 2, 0.01, (x) => `liquidBright ${x} not in [0.9, 2]`, { highlightBright: 0.5 });
range('trim', 'blood', 'tickBright', 0.8, 1.3, 0.01, (x) => `tickBright ${x} not in [0.8, 1.3]`);
range('trim', 'blood', 'digitBright', 0.8, 1.8, 0.01, (x) => `digitBright ${x} not in [0.8, 1.8]`);

// ---------------------------------------------------------------------------------------------
// 8. Generated material model (src/material/model.ts from spec/material-schema.json): strict material
//    validation, allowlisted design, versioned envelope and migration.
/** fn must not throw. */
function accepts(name: string, fn: () => unknown): void {
  let got: string[] = [];
  try { fn(); } catch (error) { got = [(error as Error).message]; }
  report(name, got, []);
}
/** fn must throw an error whose message contains `want`. */
function rejects(name: string, fn: () => unknown, want: string): void {
  let got: string[];
  try { fn(); got = ['accepted']; } catch (error) {
    const msg = (error as Error).message;
    got = msg.includes(want) ? [] : [msg];
  }
  report(name, got, []);
  if (got.length) console.log(`  - want an error containing: ${want}`);
}
function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== 'object' || typeof b !== 'object' || a === null || b === null || Array.isArray(a) !== Array.isArray(b)) return false;
  const ka = Object.keys(a), kb = Object.keys(b);
  return ka.length === kb.length && ka.every((k) => Object.prototype.hasOwnProperty.call(b, k)
    && deepEqual((a as Record<string, unknown>)[k], (b as Record<string, unknown>)[k]));
}
const withField = (key: string, v: unknown): Record<string, unknown> => ({ ...DEFAULT_MATERIAL, [key]: v });

accepts('material: DEFAULT_MATERIAL', () => validateMaterial(DEFAULT_MATERIAL));
report('material: validateMaterial(DEFAULT_MATERIAL) is a copy with the same values',
  deepEqual(validateMaterial(DEFAULT_MATERIAL), DEFAULT_MATERIAL) ? [] : ['values changed'], []);
for (const m of MATERIAL_META) {
  accepts(`material: ${m.key} = min ${m.min}`, () => validateMaterial(withField(m.key, m.min)));
  accepts(`material: ${m.key} = max ${m.max}`, () => validateMaterial(withField(m.key, m.max)));
  const lo = r6(m.min - m.step), hi = r6(m.max + m.step);
  rejects(`material: ${m.key} = ${lo} (below min)`, () => validateMaterial(withField(m.key, lo)), `${m.key} = ${lo} must be in [${m.min}, ${m.max}]`);
  rejects(`material: ${m.key} = ${hi} (above max)`, () => validateMaterial(withField(m.key, hi)), `${m.key} = ${hi} must be in [${m.min}, ${m.max}]`);
  if (m.integer) {
    const v = m.min + 0.5;
    rejects(`material: integer ${m.key} = ${v}`, () => validateMaterial(withField(m.key, v)), `${m.key} = ${v} must be an integer`);
    report(`material: ${m.key} options cover [${m.min}, ${m.max}]`, m.options && m.options.length === m.max - m.min + 1 ? [] : ['options missing or wrong length'], []);
  }
}
rejects('material: ior = NaN', () => validateMaterial(withField('ior', NaN)), 'ior must be a finite number');
rejects('material: viscosity = Infinity', () => validateMaterial(withField('viscosity', Infinity)), 'viscosity must be a finite number');
rejects('material: density = "1000" (string)', () => validateMaterial(withField('density', '1000')), 'density must be a finite number');
rejects('material: missing ior', () => { const o: Record<string, unknown> = { ...DEFAULT_MATERIAL }; delete o.ior; return validateMaterial(o); }, 'missing field ior');
rejects('material: unknown key', () => validateMaterial(withField('color', 1)), 'unknown field(s) color');
rejects('material: not an object', () => validateMaterial([1]), 'expected an object');

const DESIGN0: Record<string, unknown> = {};
{
  const p = presetParams(PRESETS[0]) as unknown as Record<string, unknown>;
  for (const k of DESIGN_KEYS) DESIGN0[k] = p[k];
}
accepts(`design: full allowlist from preset ${PRESETS[0].id} (${DESIGN_KEYS.length} keys)`, () => validateDesign(DESIGN0));
report('design: validateDesign keeps every allowlisted value', deepEqual(validateDesign(DESIGN0), DESIGN0) ? [] : ['values changed'], []);
accepts('design: empty', () => validateDesign({}));
rejects('design: liquid (derived key)', () => validateDesign({ ...DESIGN0, liquid: '#ff0000' }), 'not in the design allowlist (derived from the material or fixed): liquid');
rejects('design: v', () => validateDesign({ v: 23 }), 'not in the design allowlist');
rejects('design: tubeHeight "40" (wrong type)', () => validateDesign({ tubeHeight: '40' }), 'tubeHeight must be a number');
rejects('design: digits 1 (wrong type)', () => validateDesign({ digits: 1 }), 'digits must be a boolean');
rejects('design: tubeBack 0 (wrong type)', () => validateDesign({ tubeBack: 0 }), 'tubeBack must be a string');
rejects('design: hoursY NaN', () => validateDesign({ hoursY: NaN }), 'hoursY must be finite');
rejects('design: tubeBack #12345 (bad hex)', () => validateDesign({ tubeBack: '#12345' }), 'must be a #rrggbb colour');
rejects('design: digitColor #gg0000 (bad hex)', () => validateDesign({ digitColor: '#gg0000' }), 'must be a #rrggbb colour');
accepts('design: tubeBack #AbCdEf (hex any case)', () => validateDesign({ tubeBack: '#AbCdEf' }));

{
  const env = {
    name: 'Round trip', material: { ...DEFAULT_MATERIAL, viscosity: 84, gasMode: 2 }, design: DESIGN0 as Design,
    provenance: { viscosity: 'measured', absorptionR: 'estimated', exposure: 'artistic' } as const,
  };
  const text = serializeMaterialEnvelope(env);
  const back = parseMaterialEnvelope(text);
  report('envelope: serialize → parse deep-equals', deepEqual(back, { kind: 'liquid-watch-material', version: MATERIAL_VERSION, ...env }) ? [] : [text], []);
  report('envelope: serialize is stable', serializeMaterialEnvelope(back) === text ? [] : ['second serialization differs'], []);
  accepts('envelope: parse an object (no name / provenance)', () => parseMaterialEnvelope({ kind: 'liquid-watch-material', version: 1, material: DEFAULT_MATERIAL, design: {} }));
  rejects('envelope: legacy Params JSON', () => parseMaterialEnvelope(JSON.stringify(presetParams(PRESETS[0]))), 'legacy Params export');
  rejects('envelope: kind liquid-watch-physical', () => parseMaterialEnvelope({ kind: 'liquid-watch-physical', version: 1, material: DEFAULT_MATERIAL, design: {} }), 'kind must be "liquid-watch-material"');
  rejects('envelope: no kind', () => parseMaterialEnvelope({ version: 1, material: DEFAULT_MATERIAL, design: {} }), 'kind must be');
  rejects('envelope: version 2 (newer)', () => parseMaterialEnvelope({ kind: 'liquid-watch-material', version: 2, material: DEFAULT_MATERIAL, design: {} }), 'newer than this simulator');
  rejects('envelope: version 0', () => parseMaterialEnvelope({ kind: 'liquid-watch-material', version: 0, material: DEFAULT_MATERIAL, design: {} }), 'unsupported version 0');
  rejects('envelope: version "1"', () => parseMaterialEnvelope({ kind: 'liquid-watch-material', version: '1', material: DEFAULT_MATERIAL, design: {} }), 'unsupported version "1"');
  rejects('envelope: not JSON', () => parseMaterialEnvelope('{kind:'), 'not JSON');
  rejects('envelope: missing design', () => parseMaterialEnvelope({ kind: 'liquid-watch-material', version: 1, material: DEFAULT_MATERIAL }), 'Invalid design');
  rejects('envelope: design with liquid', () => parseMaterialEnvelope({ kind: 'liquid-watch-material', version: 1, material: DEFAULT_MATERIAL, design: { liquid: '#ff0000' } }), 'liquid');
  rejects('envelope: name 3', () => parseMaterialEnvelope({ kind: 'liquid-watch-material', version: 1, name: 3, material: DEFAULT_MATERIAL, design: {} }), 'name must be a string');
  rejects('envelope: provenance guessed', () => parseMaterialEnvelope({ kind: 'liquid-watch-material', version: 1, material: DEFAULT_MATERIAL, design: {}, provenance: { ior: 'guessed' } }), 'ior must be one of');

  // strict import: a current-version file keeps every key, so an unknown one is rejected by name (keys are
  // dropped only by an explicit older-version migration step, of which version 1 has none)
  const old = { kind: 'liquid-watch-material', version: 1, material: { ...DEFAULT_MATERIAL, colour: 3 }, design: { tubeHeight: 40 }, extra: true, provenance: { ior: 'measured', colour: 'estimated' } };
  const mig = migrateMaterial(old);
  report('migrate v1 (current): passes every key through, drops nothing', deepEqual(mig, old) ? [] : [JSON.stringify(mig)], []);
  report('migrate v1: input untouched', 'colour' in old.material && 'extra' in old ? [] : ['input mutated'], []);
  const base1 = { kind: 'liquid-watch-material', version: 1, material: DEFAULT_MATERIAL, design: {} };
  rejects('strict import: unknown envelope key', () => parseMaterialEnvelope({ ...base1, extra: true }), 'unknown field(s) extra');
  rejects('strict import: unknown material key', () => parseMaterialEnvelope({ ...base1, material: { ...DEFAULT_MATERIAL, colour: 3 } }), 'unknown field(s) colour');
  rejects('strict import: unknown provenance key', () => parseMaterialEnvelope({ ...base1, provenance: { ior: 'measured', colour: 'estimated' } }), 'unknown material field(s) colour');
  rejects('strict import: all three at once (first reported)', () => parseMaterialEnvelope(old), 'unknown field(s)');
  rejects('migrate: version 2 (newer)', () => migrateMaterial({ ...old, version: 2 }), 'newer than this simulator');
}

// ---------------------------------------------------------------------------------------------
// 9. derive(material, design) → Params (src/material/derive.ts, docs/physical-renderer.md).
//    (a) the doc's fixture table within its tolerances, (b) every fixture coherent for its inferred
//    class, (c) boundary fixtures, (d) viscosity sweep monotonicity, (e) rejections, (f) sampled inputs.
type Kind = 'c' | 'w' | 'd' | 'x' | 'T';
/** One expectation: a Params key (or a report field), the doc's printed value, the tolerance kind:
 *  c = colour ±3 levels per channel, w = glass/highlight/colour weight ±0.03, T = transmittance ±0.01,
 *  d = dynamics ±2 % (or half the doc's last printed digit, whichever is larger), x = exact. */
type Want = [string, string | number | boolean | [number, number, number], Kind];
const MAT0 = { innerRadius: 2.25, wallThickness: 0.5, wallIor: 1.49, lightElevation: 60, lightSize: 30, lightIntensity: 1, ambient: 0.2, exposure: 1 };
const mat = (m: Partial<MaterialProps>): MaterialProps => ({ ...DEFAULT_MATERIAL, ...MAT0, ...m });
/** Fixture design: the listed backing (plain), 54 px tube, a sprite font that fits it, rear marks. */
const FRONT: Design = { ticksOnTop: true, digitsOnTop: true, tickColorH: '#9aa4ac', tickMajorColorH: '#e8eef2', tickColorM: '#9aa4ac', tickMajorColorM: '#e8eef2' };
/** markContrast of the rear-mark fixtures behind a non-opaque liquid (the policy value before it became a design key). */
const REAR24: Design = { markContrast: 24 };
const fdesign = (back: string, extra: Design = {}): Design => ({
  tubeHeight: 54, hoursY: 0, minutesY: 185, tubeBack: back, tubeBack2: back, tubeBackGradient: 0,
  digitFont: 9, digitScaleX: 3.25, digitScaleY: 3.25, digitBottom: 5, ...extra,
});
interface Fixture { name: string; m: MaterialProps; d: Design; want: Want[] }
const FIXTURES: Fixture[] = [
  { name: 'water', m: mat({ viscosity: 1, density: 1000, surfaceTension: 72, ior: 1.333, contactAngle: 20, contactHysteresis: 10, solidsFraction: 0, gasMode: 1, gasLevel: 0.6, bubbleRadius: 0.06, foamStability: 4 }),
    d: fdesign('#0a0e10', REAR24), want: [
      ['viscosity', 'watery', 'x'], ['opacity', 'clear', 'x'], ['T', '0.92', 'T'], ['pxPerMm', '9.64', 'd'],
      ['liquid', [48, 48, 48], 'c'], ['liquidLo', [15, 15, 15], 'c'], ['liquidHi', [189, 190, 190], 'c'], ['liquidThin', '0', 'w'], ['shadeDepth', '0.3', 'w'],
      ['highlightBright', '0.60', 'w'], ['glassWallGlow', '0.27', 'w'], ['wallWet', 1, 'x'], ['glassOverLiquid', '0.54', 'w'],
      ['freeDamp', '0.8', 'd'], ['freeBounce', '0.20', 'd'], ['meniscusK', '475', 'd'], ['meniscusDamp', '8', 'd'], ['contactDyn', '8.2', 'd'],
      ['capLength', '2.17', 'd'], ['angleTiltGain', '6.5', 'd'], ['angleGyroGain', '0.42', 'd'],
      ['wetFilm', '10.5', 'd'], ['traces', false, 'x'], ['fizz', true, 'x'], ['fizzSize', '1.16', 'd'], ['fizzSpeed', '35', 'd'], ['fizzCount', 48, 'x'], ['glowStrength', '0.07', 'd'],
    ] },
  { name: 'olive oil', m: mat({ viscosity: 84, density: 915, surfaceTension: 32, ior: 1.47, absorptionR: 0.05, absorptionG: 0.07, absorptionB: 0.45, contactAngle: 15, contactHysteresis: 8, solidsFraction: 0.3, dryingTime: 2 }),
    d: fdesign('#110b03', REAR24), want: [
      ['viscosity', 'medium', 'x'], ['opacity', 'translucent', 'x'], ['T', '0.47', 'T'],
      ['liquid', [57, 53, 0], 'c'], ['liquidLo', [5, 7, 0], 'c'], ['liquidHi', [192, 189, 164], 'c'], ['residual', '0', 'c'],
      ['liquidThin', '1.0', 'w'], ['shadeDepth', '0.4', 'w'], ['highlightBright', '0.55', 'w'], ['glassWallGlow', '0.27', 'w'],
      ['glassOverLiquid', '0.5', 'w'],
      ['freeDamp', '3.35', 'd'], ['freeBounce', 0.05, 'x'], ['meniscusK', 200, 'x'], ['meniscusDamp', '20.8', 'd'], ['contactDyn', '47', 'd'],
      ['capLength', '1.51', 'd'], ['angleTiltGain', '3.64', 'd'], ['angleGyroGain', '0.20', 'd'],
      ['wetFilm', '18.8', 'd'], ['traces', true, 'x'], ['traceAmount', '0.57', 'd'], ['traceStain', '0.24', 'd'], ['traceDrain', '17.4', 'd'], ['glowStrength', '0.04', 'd'],
    ] },
  { name: 'honey', m: mat({ viscosity: 10000, density: 1420, surfaceTension: 70, ior: 1.49, absorptionR: 0.06, absorptionG: 0.18, absorptionB: 0.7, contactAngle: 25, contactHysteresis: 20, solidsFraction: 0.8, dryingTime: 2, gasMode: 3, gasLevel: 0.04, bubbleRadius: 0.12, foamStability: 20 }),
    d: fdesign('#0c0703', REAR24), want: [
      ['viscosity', 'viscous', 'x'], ['opacity', 'translucent', 'x'], ['T', '0.27', 'T'],
      ['liquid', [44, 21, 0], 'c'], ['liquidLo', [9, 2, 0], 'c'], ['liquidHi', [199, 184, 161], 'c'], ['residual', '0.6', 'c'],
      ['liquidThin', '1.0', 'w'], ['shadeDepth', '0.4', 'w'], ['highlightBright', '0.53', 'w'], ['glassWallGlow', '0.27', 'w'],
      ['freeDamp', '8.65', 'd'], ['freeBounce', 0, 'x'], ['meniscusK', '79', 'd'], ['meniscusDamp', '33', 'd'], ['contactDyn', 90, 'x'],
      ['capLength', '1.79', 'd'], ['angleTiltGain', '1.62', 'd'], ['angleGyroGain', '0.07', 'd'],
      ['wetFilm', '28.3', 'd'], ['traces', true, 'x'], ['traceAmount', '1.32', 'd'], ['traceStain', '0.57', 'd'], ['traceDrain', '0.23', 'd'],
      ['fizz', true, 'x'], ['fizzSize', '2.31', 'd'], ['fizzSpeed', 0, 'x'], ['fizzCount', 5, 'x'],
    ] },
  { name: 'mercury', m: mat({ metallic: 1, metalReflectance: 0.75, viscosity: 1.55, density: 13546, surfaceTension: 485, contactAngle: 140, contactHysteresis: 15 }),
    d: fdesign('#000000'), want: [
      ['viscosity', 'metal', 'x'], ['opacity', 'opaque', 'x'], ['wetting', false, 'x'], ['liquidTransparency', 0, 'x'],
      ['liquid', [152, 152, 152], 'c'], ['liquidLo', [65, 65, 65], 'c'], ['liquidHi', [255, 255, 255], 'x'],
      ['shadeDepth', 0.95, 'x'], ['highlightBright', 1.3, 'x'], ['glassWallGlow', '0.27', 'w'], ['glassOverLiquid', 1, 'x'],
      ['freeDamp', 0.8, 'x'], ['freeBounce', '0.51', 'd'], ['meniscusK', 500, 'x'], ['meniscusDamp', 8, 'x'], ['contactDyn', '5.1', 'd'],
      ['capLength', '1.53', 'd'], ['angleTiltGain', 2, 'x'], ['angleGyroGain', 0.4, 'x'],
      ['wetFilm', 0, 'x'], ['traces', false, 'x'], ['fizz', false, 'x'], ['glowStrength', 0, 'x'],
    ] },
  { name: 'xenon', m: mat({ phase: 1, emissionR: 0.35, emissionG: 0.2, emissionB: 0.9, ior: 1 }),
    d: fdesign('#05020c', { freeLiquid: false, ...REAR24 }), want: [
      ['viscosity', 'plasma', 'x'], ['opacity', 'translucent', 'x'], ['emissive', true, 'x'], ['liquidTransparency', 0.5, 'x'],
      ['liquid', [123, 95, 187], 'c'], ['liquidLo', [123, 95, 187], 'c'], ['liquidHi', [196, 176, 196], 'c'], ['shadeDepth', 0.85, 'x'], ['glassWallGlow', '0.27', 'w'], ['wallWet', 0, 'x'], ['glassOverLiquid', 0.4, 'x'],
      ['freeLiquid', false, 'x'], ['fillK', 260, 'x'], ['fillDamp', 22, 'x'], ['fillSloshGain', 0.5, 'x'], ['angleK', 300, 'x'], ['angleDamp', 26, 'x'],
      ['angleTiltGain', 0.5, 'x'], ['angleMax', 2, 'x'], ['angleGyroGain', 0.03, 'x'], ['contactAngle', 100, 'x'], ['contactHyst', 0, 'x'], ['contactDyn', 0, 'x'],
      ['meniscusK', 400, 'x'], ['meniscusDamp', 30, 'x'], ['meniscusInertia', 0, 'x'],
      ['wetFilm', 0, 'x'], ['traces', false, 'x'], ['fizz', false, 'x'], ['glowStrength', '0.52', 'd'], ['edgeGlow', 23, 'x'], ['lightPhys', 0, 'x'], ['liquidBright', 1.3, 'x'],
    ] },
  { name: 'blood', m: mat({ viscosity: 4, density: 1060, surfaceTension: 58, ior: 1.35, absorptionR: 1, absorptionG: 20, absorptionB: 25, scattering: 1, contactAngle: 30, contactHysteresis: 15, solidsFraction: 0.45, dryingTime: 1.5 }),
    d: fdesign('#050203', FRONT), want: [
      ['viscosity', 'medium', 'x'], ['opacity', 'opaque', 'x'], ['T', '0.000', 'T'],
      ['liquid', [120, 35, 31], 'c'], ['liquidLo', [49, 9, 7], 'c'], ['liquidHi', [247, 168, 166], 'c'], ['residual', '0', 'c'], ['shadeDepth', '0.95', 'w'], ['highlightBright', '0.63', 'w'], ['glassOverLiquid', '0.53', 'w'],
      ['freeDamp', '1.87', 'd'], ['freeBounce', '0.10', 'd'], ['meniscusK', '288', 'd'], ['meniscusDamp', '14.8', 'd'], ['contactDyn', '14.1', 'd'],
      ['capLength', '1.89', 'd'], ['angleTiltGain', '4.85', 'd'], ['angleGyroGain', '0.29', 'd'],
      ['wetFilm', '15.3', 'd'], ['traces', true, 'x'], ['traceAmount', '1.06', 'd'], ['traceStain', '0.34', 'd'], ['traceDrain', '423', 'd'],
    ] },
  { name: 'milk', m: mat({ viscosity: 2.9, density: 1030, surfaceTension: 45, ior: 1.35, absorptionR: 0.001, absorptionG: 0.001, absorptionB: 0.001, scattering: 3, contactAngle: 30, contactHysteresis: 15 }),
    d: fdesign('#000000'), want: [
      ['viscosity', 'medium', 'x'], ['opacity', 'opaque', 'x'], ['T', '0.00', 'T'],
      ['liquid', [212, 212, 212], 'c'], ['liquidLo', [93, 93, 93], 'c'], ['liquidHi', [255, 255, 255], 'c'], ['shadeDepth', '0.95', 'w'], ['highlightBright', 1, 'x'],
      ['freeDamp', '1.67', 'd'], ['freeBounce', '0.11', 'd'], ['meniscusK', '263', 'd'], ['meniscusDamp', '14.2', 'd'], ['contactDyn', '13.8', 'd'],
      ['wetFilm', '15.2', 'd'], ['traces', false, 'x'],
    ] },
  { name: 'liquid oxygen', m: mat({ viscosity: 0.19, density: 1141, surfaceTension: 13, ior: 1.22, absorptionR: 0.005, absorptionG: 0.002, absorptionB: 0, contactAngle: 5, contactHysteresis: 3, gasMode: 2, gasLevel: 0.7, bubbleRadius: 0.05, foamStability: 0 }),
    d: fdesign('#000000', REAR24), want: [
      ['viscosity', 'watery', 'x'], ['opacity', 'clear', 'x'], ['T', '0.88', 'T'],
      ['liquid', [50, 51, 52], 'c'], ['liquidLo', [16, 17, 17], 'c'], ['liquidHi', [190, 190, 190], 'c'], ['shadeDepth', '0.3', 'w'], ['glassWallGlow', '0.27', 'w'], ['wallWet', '0.99', 'w'], ['glassOverLiquid', '0.63', 'w'],
      ['freeDamp', '0.57', 'd'], ['freeBounce', '0.35', 'd'], ['meniscusK', 400, 'x'], ['meniscusDamp', '4.9', 'd'], ['contactDyn', '8.4', 'd'], ['capLength', '0.86', 'd'],
      ['wetFilm', '10.7', 'd'], ['fizz', true, 'x'], ['fizzSize', 1, 'x'], ['fizzSpeed', '55', 'd'], ['fizzCount', 56, 'x'],
    ] },
  { name: 'cola', m: mat({ viscosity: 1.2, density: 1040, surfaceTension: 60, ior: 1.35, absorptionR: 0.05, absorptionG: 0.15, absorptionB: 0.35, contactAngle: 20, contactHysteresis: 10, gasMode: 1, gasLevel: 0.4, bubbleRadius: 0.07 }),
    d: fdesign('#070403', REAR24), want: [
      ['viscosity', 'watery', 'x'], ['opacity', 'translucent', 'x'], ['T', '0.32', 'T'],
      ['liquid', [52, 29, 5], 'c'], ['liquidLo', [12, 4, 0], 'c'], ['liquidHi', [196, 184, 170], 'c'], ['residual', '0', 'c'],
      ['liquidThin', '1', 'w'], ['shadeDepth', '0.4', 'w'], ['glassWallGlow', '0.27', 'w'],
      ['freeDamp', '0.89', 'd'], ['freeBounce', '0.18', 'd'], ['meniscusK', '418', 'd'], ['meniscusDamp', '8.9', 'd'], ['contactDyn', '9.3', 'd'],
      ['wetFilm', '11.8', 'd'], ['fizz', true, 'x'], ['fizzSize', '1.35', 'd'], ['fizzSpeed', '38', 'd'], ['fizzCount', 42, 'x'],
    ] },
  { name: 'oil on parchment', m: mat({ viscosity: 84, density: 915, surfaceTension: 32, ior: 1.47, absorptionR: 0.05, absorptionG: 0.07, absorptionB: 0.45, contactAngle: 15, contactHysteresis: 8, solidsFraction: 0.3, dryingTime: 2 }),
    d: fdesign('#f1e6cf'), want: [
      ['viscosity', 'medium', 'x'], ['opacity', 'opaque', 'x'], ['Tlum', '0.47', 'T'], ['Tmax', '0.133', 'T'], ['T', '0.133', 'T'],
      ['liquid', [195, 169, 3], 'c'], ['liquidLo', [67, 55, 0], 'c'], ['liquidHi', [255, 246, 163], 'c'], ['residual', '0', 'c'],
    ] },
  { name: 'pinot on parchment', m: mat({ viscosity: 1.5, density: 990, surfaceTension: 46, ior: 1.35, absorptionR: 0.15, absorptionG: 0.65, absorptionB: 0.5, contactAngle: 20, contactHysteresis: 10, solidsFraction: 0.03 }),
    d: fdesign('#f1e6cf'), want: [
      ['viscosity', 'watery', 'x'], ['opacity', 'opaque', 'x'], ['Tlum', '0.07', 'T'], ['Tmax', '0.030', 'T'], ['T', '0.030', 'T'],
      ['liquid', [129, 0, 14], 'c'], ['liquidLo', [49, 0, 0], 'c'], ['liquidHi', [253, 164, 169], 'c'], ['residual', '0', 'c'],
    ] },
  // sampled input #152 (seed 20260925): a strongly blue-absorbing liquid whose luma transmittance reads clear;
  // clear is colourless only, so the two-pass channel spread caps it at the translucent edge
  { name: 'sampled #152 (yellow, weak light)', m: { ...DEFAULT_MATERIAL, ior: 1.04468, absorptionR: 0.00234678, absorptionG: 0.0324305, absorptionB: 2.59272, scattering: 0, emissionR: 0, emissionG: 0, emissionB: 0, metallic: 0, metalReflectance: 0.704611, phase: 0, density: 11337.4, viscosity: 9.44863, surfaceTension: 1393.56, contactAngle: 22.3205, contactHysteresis: 1.57502, solidsFraction: 0.193126, dryingTime: 2.71643, gasMode: 3, gasLevel: 0.968764, bubbleRadius: 0.147843, foamStability: 21.2025, innerRadius: 1.90599, wallThickness: 0.376686, wallIor: 1.54815, lightElevation: 9.7622, lightSize: 74.9773, lightIntensity: 0.124824, ambient: 0.269158, exposure: 2.54719 },
    d: { tubeHeight: 40, hoursY: 10, minutesY: 190, tubeBack: '#000000', tubeBack2: '#000000', tubeBackGradient: 0, ...FRONT, digitFont: 3, digitColor: '#e3e3e3' },
    want: [['opacity', 'translucent', 'x'], ['liquidTransparency', 0.55, 'x']] },
];

function lookup(r: DeriveReport, key: string): unknown {
  if (key in r.classes) return (r.classes as unknown as Record<string, unknown>)[key];
  if (key === 'T' || key === 'Tlum' || key === 'Tmax' || key === 'pxPerMm') return r.coords[key];
  if (key === 'residual') return r.residual;
  const v = (r.params as unknown as Record<string, unknown>)[key];
  return typeof v === 'string' && v.startsWith('#') ? hex(v) : v;
}
function check(got: unknown, want: Want[1], kind: Kind): boolean {
  if (Array.isArray(want)) {
    const g = got as number[];
    const tol = kind === 'x' ? 0 : 3;
    return Array.isArray(g) && want.every((w, i) => Math.abs(g[i] - w) <= tol);
  }
  if (typeof want === 'boolean' || (typeof want === 'string' && Number.isNaN(Number(want)))) return got === want;
  if (typeof got !== 'number') return false;
  const w = Number(want);
  if (kind === 'x') return got === w;
  if (kind === 'c') return Math.abs(got - w) <= 1 + 1e-9; // residual: ±1 level
  if (kind === 'w') return Math.abs(got - w) <= 0.03 + 1e-9;
  if (kind === 'T') return Math.abs(got - w) <= 0.01 + 1e-9;
  const printed = String(want), dec = printed.includes('.') ? printed.split('.')[1].length : 0;
  return Math.abs(got - w) <= Math.max(0.02 * Math.abs(w), 0.5 * 10 ** -dec) + 1e-9;
}
const show = (v: unknown): string => Array.isArray(v) ? `(${v.map((x) => +(+x).toFixed(3)).join(',')})` : typeof v === 'number' ? String(+v.toFixed(4)) : String(v);

report('derive: every Params key has exactly one owner (design / derived / fixed)', ownershipIssues(), []);
for (const f of FIXTURES) {
  let r: DeriveReport;
  try { r = deriveReport(f.m, f.d); } catch (error) { report(`fixture ${f.name}: deriveReport`, [(error as Error).message], []); continue; }
  report(`fixture ${f.name}: no rejection`, r.issues, []);
  const bad: string[] = [];
  for (const [key, want, kind] of f.want) {
    const got = lookup(r, key);
    if (!check(got, want, kind)) bad.push(`${key}: got ${show(got)}, doc ${show(want)} (${kind})`);
  }
  report(`fixture ${f.name}: ${f.want.length} values vs the doc table`, bad, []);
  const opaqueOrTranslucent = r.classes.opacity !== 'clear' && r.classes.viscosity !== 'plasma';
  report(`fixture ${f.name}: residual ${r.residual.toFixed(2)} levels${opaqueOrTranslucent ? ' ≤ 5' : ' (clear/plasma: reported only)'}`,
    opaqueOrTranslucent && r.residual > 5 ? [`residual ${r.residual.toFixed(2)} > 5`] : [], []);
  // (b) coherence for the inferred class
  report(`fixture ${f.name}: coherent as ${JSON.stringify(r.classes)}`, coherenceIssues(r.params, r.classes), []);
}

// determinism, pass-through, fixed policy
{
  const f = FIXTURES[0], a = derive(f.m, f.d), b = derive(f.m, f.d);
  report('derive: deterministic (two calls deep-equal)', deepEqual(a, b) ? [] : ['differs'], []);
  report('derive: output has exactly the Params keys', deepEqual(Object.keys(a).sort(), Object.keys(DEFAULT_PARAMS).sort()) ? [] : [Object.keys(a).join(',')], []);
  report('derive: v = PARAMS_VERSION', a.v === PARAMS_VERSION ? [] : [`v ${a.v}`], []);
  const passBad = DESIGN_KEYS.filter((k) => a[k] !== (k in f.d ? (f.d as Record<string, unknown>)[k] : DEFAULT_PARAMS[k]));
  report('derive: design keys pass through, unsupplied ones take DEFAULT_PARAMS', passBad.map((k) => `${k} = ${String(a[k])}`), []);
  report('derive: input material and design untouched (1)', deepEqual(f.m, mat({ viscosity: 1, density: 1000, surfaceTension: 72, ior: 1.333, contactAngle: 20, contactHysteresis: 10, solidsFraction: 0, gasMode: 1, gasLevel: 0.6, bubbleRadius: 0.06, foamStability: 4 })) ? [] : ['material mutated'], []);
}

// The real renderer: buildPalette(derived Params) must reproduce the encoded body targets (linear body plus
// emission, encoded once) at the centre row and at the wall sample's display row — the wall through the
// fitted shadeDepth and the solved rimTint. The specular / glass overlays and the panel dimmer are zeroed in
// a copy (derive's BODY_ONLY) so the rows carry only the body; both sides are compared after the panel's
// RGB565 round trip. Clear (accepted haze residual) and plasma (no body) are skipped.
{
  const worst: Record<'centre' | 'wall', [number, string]> = { centre: [0, ''], wall: [0, ''] };
  for (const f of FIXTURES) {
    const r = deriveReport(f.m, f.d);
    if (r.issues.length || r.classes.opacity === 'clear' || r.classes.viscosity === 'plasma') continue;
    const p = { ...r.params, ...BODY_ONLY }, pal = buildPalette(p, 0), H = pal.rows.length, yc = (H - 1) / 2;
    const E = [f.m.emissionR, f.m.emissionG, f.m.emissionB];
    const rows: Array<['centre' | 'wall', number, number[]]> = [
      ['centre', Math.floor(yc), r.body.centre],
      ['wall', Math.round(yc * (1 + r.body.wallOffset)), r.body.wall],
    ];
    for (const [name, y, lin] of rows) {
      const got = rgb565to888(pal.rows[y]), want = q565(lin.map((v, i) => enc255(v + E[i])));
      const err = Math.max(...[0, 1, 2].map((i) => Math.abs(got[i] - want[i])));
      if (err >= worst[name][0]) worst[name] = [err, f.name];
      report(`buildPalette ${f.name}: ${name} row ${y} ${show(got)} vs target ${show(want)} (${err} levels ≤ 5; rimLight ${r.params.rimLight}, rimTint ${r.params.rimTint}, shadeDepth ${r.params.shadeDepth.toFixed(3)})`, err <= 5 ? [] : [`${err} levels`], []);
    }
  }
  console.log(`  buildPalette body rows: worst centre ${worst.centre[0]} levels (${worst.centre[1]}), worst wall ${worst.wall[0]} levels (${worst.wall[1]}) (after RGB565)`);
  // rimLight 0 renders the legacy (v23) way: the addition is exactly zero, whatever rimTint holds — every
  // palette table equals the one with a black tint, and a black tint at rimLight 1 adds nothing either
  for (const f of FIXTURES) {
    const r = deriveReport(f.m, f.d);
    if (r.issues.length) continue;
    const tables = (q: Params): string => { const pl = buildPalette(q, 20) as unknown as Record<string, ArrayLike<number> | number>; return JSON.stringify(Object.keys(pl).sort().map((k) => [k, typeof pl[k] === 'number' ? pl[k] : Array.from(pl[k] as ArrayLike<number>)])); };
    const off = tables({ ...r.params, rimLight: 0 }), legacy = tables({ ...r.params, rimLight: 0, rimTint: '#000000' }), black = tables({ ...r.params, rimLight: 1, rimTint: '#000000' });
    report(`buildPalette ${f.name}: rimLight 0 (rimTint ${r.params.rimTint}) equals the v23 palette`, off === legacy && black === legacy ? [] : ['differs'], []);
  }
}
// Rim fit (rimLight gain 1..4, rejection 12): the wall row is measured here independently of derive's own
// figure (body-only palette, RGB565 round trip) and the two must agree; an error above 5 levels is only
// ever reported as rejection 12, never accepted.
/** Independent wall-row error of a report, 8-bit levels after RGB565 (the buildPalette check above). */
function wallError(r: DeriveReport, m: MaterialProps): number {
  const pal = buildPalette({ ...r.params, ...BODY_ONLY }, 0), yc = (pal.rows.length - 1) / 2;
  const got = rgb565to888(pal.rows[Math.round(yc * (1 + r.body.wallOffset))]);
  const want = q565(r.body.wall.map((v, i) => enc255(v + [m.emissionR, m.emissionG, m.emissionB][i])));
  return Math.max(...[0, 1, 2].map((i) => Math.abs(got[i] - want[i])));
}
/** The rim contract on one input with the rim on (rimLight > 0; metal / plasma have none): the measured
 *  error equals derive's; an error above 5 is rejection 12 unless all of it is `bodyOver` (a channel above
 *  the target with tint 0 — the body shading's miss, printed on the line, not the rim's); rejection 12
 *  only above 5. */
function rimContract(name: string, m: MaterialProps, d: Design): DeriveReport {
  const r = deriveReport(m, d), err = wallError(r, m), r12 = r.issues.some((s) => s.startsWith('rejection 12 ('));
  if (r.params.rimLight === 0) return r;
  const bad: string[] = [], { error, rimError, bodyOver } = r.rim;
  if (err !== error) bad.push(`derive reports ${error} levels, measured ${err}`);
  if (err > RIM_TOLERANCE && !r12 && !(rimError <= RIM_TOLERANCE && bodyOver === err && bodyOver <= BODY_OVER_TOLERANCE)) bad.push(`wall error ${err} > ${RIM_TOLERANCE} levels without rejection 12`);
  if (r12 !== (rimError > RIM_TOLERANCE || bodyOver > BODY_OVER_TOLERANCE)) bad.push(`rejection 12 ${r12 ? 'at' : 'missing at'} rim error ${rimError}, body overshoot ${bodyOver}`);
  const body = bodyOver > RIM_TOLERANCE ? `, body overshoot ${bodyOver} at tint 0 (not the rim's)` : '';
  report(`rim ${name}: rimLight ${r.params.rimLight}, rimTint ${r.params.rimTint}, wall error ${err} levels${body} (${r12 ? 'rejection 12' : 'accepted'}; never silently > ${RIM_TOLERANCE})`, bad, []);
  return r;
}
{
  const OLIVE = MATERIAL_PRESETS.find((e) => e.id === 'olive-oil')!;
  const thick = { ...OLIVE.material, wallThickness: 1.0 } as MaterialProps;
  const r = rimContract('olive-oil preset, wallThickness 1.0', thick, OLIVE.design);
  const sat255 = hexRgb(r.params.rimTint).some((v) => v >= 255);
  report(`rim olive-oil preset, wallThickness 1.0: derives, error ${wallError(r, thick)} ≤ 5, gain 2 (${r.params.rimLight}), tint ${r.params.rimTint} not saturated`,
    [...r.issues, ...(wallError(r, thick) > 5 ? ['error > 5'] : []), ...(r.params.rimLight !== 2 ? [`gain ${r.params.rimLight}`] : []), ...(sat255 ? ['tint saturated'] : [])], []);
  const bore = { ...OLIVE.material, innerRadius: 0.5, wallThickness: 1.0 } as MaterialProps;
  const rb = rimContract('olive-oil preset, innerRadius 0.5, wallThickness 1.0', bore, OLIVE.design);
  const other = rb.issues.filter((s) => !s.startsWith('rejection 12 ('));
  report('rim olive-oil preset, innerRadius 0.5, wallThickness 1.0: derives within 5 levels or rejects 12 only', other, []);
  // A flat-lit opaque body: the opaque class needs shadeDepth ≥ 0.5, the target hardly shades, the rim cannot lower a
  // channel — an overshoot beyond one RGB565 step is rejection 12, never a silent acceptance (Astra, block C round 2).
  const MILKP = MATERIAL_PRESETS.find((e) => e.id === 'milk')!;
  const flat = { ...MILKP.material, wallThickness: 0.05, ambient: 1, exposure: 0.5 } as MaterialProps;
  const rf = rimContract('milk preset, wallThickness 0.05, ambient 1, exposure 0.5 (body overshoot)', flat, MILKP.design);
  report(`rim milk preset flat-lit: body overshoot ${rf.rim.bodyOver} > ${BODY_OVER_TOLERANCE} is rejection 12`,
    rf.rim.bodyOver > BODY_OVER_TOLERANCE && !rf.issues.some((s) => s.startsWith('rejection 12 (unrepresentable wall shading')) ? ['accepted'] : [], []);
  for (const f of FIXTURES) rimContract(`fixture ${f.name}`, f.m, f.d);
  for (const e of MATERIAL_PRESETS) rimContract(`preset ${e.id}`, e.material, e.design);
}
// Finite motion: 250 physics ticks on every fixture's derived Params under a swinging tilt keep all state finite.
for (const f of FIXTURES) {
  const r = deriveReport(f.m, f.d);
  if (r.issues.length) continue;
  const tube = newTube(), bad: string[] = [];
  tube.fillTarget = 0.5;
  for (let i = 0; i < 250; i++) {
    const t = i / 50;
    stepTube(tube, { along: 0.8 * Math.sin(2.1 * t), across: 0.5 * Math.cos(1.3 * t), gyroAlong: 60 * Math.sin(5 * t), gyroAcross: 120 * Math.cos(4 * t) }, r.params, PHYS_DT, 1);
  }
  for (const [k, v] of Object.entries(tube)) {
    if (typeof v === 'number' && !Number.isFinite(v)) bad.push(`${k} = ${v}`);
    if (v instanceof Uint16Array || v instanceof Float32Array || Array.isArray(v)) for (const x of Array.from(v as ArrayLike<number>)) if (!Number.isFinite(x)) { bad.push(`${k} has ${x}`); break; }
  }
  report(`finite motion: ${f.name}, 250 ticks`, bad, []);
}

// ---------------------------------------------------------------------------------------------
// 10. Boundary fixtures (finite output, no exception) and the colour-model limit branches.
const finiteIssues = (p: Params): string[] => {
  const bad: string[] = [];
  for (const [k, v] of Object.entries(p)) {
    if (typeof v === 'number' && !Number.isFinite(v)) bad.push(`${k} = ${v}`);
    if (typeof v === 'string' && !/^#[0-9a-f]{6}$/.test(v)) bad.push(`${k} = ${v}`);
  }
  return bad;
};
/** derive must succeed with finite output, coherent for its class; returns the report. */
function boundary(name: string, m: MaterialProps, d: Design): DeriveReport | null {
  let r: DeriveReport;
  try { derive(m, d); r = deriveReport(m, d); } catch (error) { report(`boundary ${name}: derive succeeds`, [(error as Error).message], []); return null; }
  report(`boundary ${name}: finite output`, finiteIssues(r.params), []);
  report(`boundary ${name}: coherent as ${JSON.stringify(r.classes)}`, coherenceIssues(r.params, r.classes), []);
  return r;
}
const WATER = FIXTURES[0], COLA = FIXTURES[8], OIL = FIXTURES[1];
boundary('K = S = 0', { ...WATER.m, absorptionR: 0, absorptionG: 0, absorptionB: 0, scattering: 0 }, WATER.d);
boundary('K = 0, S = 3', { ...WATER.m, absorptionR: 0, absorptionG: 0, absorptionB: 0, scattering: 3, gasMode: 0 }, { ...WATER.d, markContrast: 0 });   // opaque
{
  const r = boundary('S = 0, K = 50 on a black backing (black body, guarded normalisation)', { ...WATER.m, absorptionR: 50, absorptionG: 50, absorptionB: 50, scattering: 0, gasMode: 0 }, fdesign('#000000', FRONT));
  if (r) report('boundary K = 50: liquid #000000, liquidThin 0', r.params.liquid === '#000000' && r.params.liquidThin === 0 ? [] : [`${r.params.liquid} ${r.params.liquidThin}`], []);
}
{
  const r = boundary('colourless liquid on a black backing', { ...WATER.m, gasMode: 0 }, fdesign('#000000', REAR24));
  if (r) report('boundary colourless on black: liquidThin 0, neutral liquidHi', r.params.liquidThin === 0 && sat(r.params.liquidHi) < 0.2 ? [] : [`${r.params.liquidThin} ${r.params.liquidHi}`], []);
}
{
  // zero-length chord: the d ≤ 0 branch, and the traced row at the bore edge (u = 1) stays finite
  const z = km(3, 2, 0, 0.4), zb = km(3, 0, -1, 0.4);
  report('km: d = 0 → Tr = 1, R = Rg (both scattering branches)', z.Tr === 1 && z.R === 0.4 && zb.Tr === 1 && zb.R === 0.4 ? [] : [JSON.stringify([z, zb])], []);
  const s = sampleRow(1, WATER.m);
  report(`sampleRow(u = 1): finite (d ${s.d.toFixed(3)} mm, F_far ${s.Ffar.toFixed(3)})`, [s.d, s.Ft, s.Ffar].every(Number.isFinite) ? [] : [JSON.stringify(s)], []);
  const s0 = sampleRow(0, WATER.m), sw = sampleRow(U_WALL, WATER.m);
  report(`sampleRow(0): d = 2r (${s0.d.toFixed(4)}), F_far 4–6 % (${s0.Ffar.toFixed(3)})`, Math.abs(s0.d - 4.5) < 1e-9 && s0.Ffar > 0.03 && s0.Ffar < 0.07 ? [] : [JSON.stringify(s0)], []);
  report(`sampleRow(0.85): traced chord ${(sw.d / 2.25).toFixed(3)} r, F_far ${sw.Ffar.toFixed(3)} (no TIR)`, sw.d > 0 && sw.d < 4.5 && sw.Ffar < 0.07 ? [] : [JSON.stringify(sw)], []);
  // limit branches agree with the general formula next to them
  const near = (a: KM, b: KM): boolean => Math.abs(a.R - b.R) < 1e-4 && Math.abs(a.Tr - b.Tr) < 1e-4;
  report('km: K → 0 branch matches the general formula (K 1e-8 vs 0, S 3)', near(km(1e-8, 3, 4.5, 0.3), km(0, 3, 4.5, 0.3)) ? [] : [JSON.stringify([km(1e-8, 3, 4.5, 0.3), km(0, 3, 4.5, 0.3)])], []);
  report('km: S → 0 branch matches the general formula (S 2e-6 vs 0, K 0.3)', near(km(0.3, 2e-6, 4.5, 0.3), km(0.3, 0, 4.5, 0.3)) ? [] : [JSON.stringify([km(0.3, 2e-6, 4.5, 0.3), km(0.3, 0, 4.5, 0.3)])], []);
  const big = km(50, 50, 4.5, 1);
  report('km: x capped at 50 stays finite (K = S = 50)', Number.isFinite(big.R) && Number.isFinite(big.Tr) ? [] : [JSON.stringify(big)], []);
  report('km: blood R∞ ≈ (0.27, 0.02, 0.02)', [[1, 0.27], [20, 0.02], [25, 0.02]].every(([K, want]) => Math.abs(km(K, 1, 1e3, 0).R - want) < 0.01) ? [] : ['blood R∞ drifted'], []);
  report('km: milk R∞ ≈ 0.97', Math.abs(km(0.001, 3, 1e4, 0).R - 0.97) < 0.01 ? [] : [`${km(0.001, 3, 1e4, 0).R}`], []);
}
// emission 0.3: at 0.5 the body, now summed with its emission in linear light, pre-images to display white
// (luma 254 at T_up) and is rejection 9 (overexposed) by the rule, no longer a self-lit boundary
boundary('ambient 0, light 0, emission 0.3 (self-lit)', { ...COLA.m, ambient: 0, lightIntensity: 0, emissionR: 0.3, emissionG: 0.3, emissionB: 0.3 }, COLA.d);
for (const e of [0.02, 0.021]) {
  const r = boundary(`E_lum ${e}`, { ...COLA.m, emissionR: e, emissionG: e, emissionB: e }, COLA.d);
  if (!r) continue;
  const want = e > 0.02;
  report(`boundary E_lum ${e}: emissive ${want}, glassOverLiquid ${r.params.glassOverLiquid.toFixed(3)} ${want ? '≤ 0.4' : 'unclamped'}`,
    r.classes.emissive === want && (!want || r.params.glassOverLiquid <= 0.4) ? [] : [JSON.stringify(r.classes)], []);
}
{
  const cases: Array<[number, number, string]> = [
    [0.12, 0.12, 'opaque'], [0.15, 0.12, 'opaque'], [0.185, 0.25, 'translucent'], [0.2, 0.25, 'translucent'], [0.25, 0.25, 'translucent'],
    [0.55, 0.55, 'translucent'], [0.6, 0.55, 'translucent'], [0.625, 0.7, 'clear'], [0.65, 0.7, 'clear'], [0.7, 0.7, 'clear'],
  ];
  for (const [T, want, cls] of cases)
    report(`snapT(${T}) = ${want} (${cls})`, snapT(T) === want && opacityOf(snapT(T)) === cls ? [] : [`${snapT(T)} ${opacityOf(snapT(T))}`], []);
  // T_max binding: a gap value snaps down so the composite stays attainable
  for (const [T, want] of [[0.2, 0.12], [0.185, 0.12], [0.24, 0.12], [0.6, 0.55], [0.69, 0.55], [0.3, 0.3]] as const)
    report(`snapT(${T}, T_max binding) = ${want}`, snapT(T, true) === want ? [] : [`${snapT(T, true)}`], []);
}
{
  const r = boundary('olive oil on a white backing at exposure 2.5, ambient 0.6 (T_max binds in the gap)', { ...OIL.m, exposure: 2.5, ambient: 0.6 }, fdesign('#ffffff'));
  if (r) report(`boundary oil on white: T_max ${r.coords.Tmax.toFixed(3)} → T ${r.coords.Tsnap} = 0.12, residual ${r.residual.toFixed(2)} ≤ 5 levels`,
    r.coords.Tsnap === 0.12 && r.residual <= 5 ? [] : [`T ${r.coords.Tsnap} residual ${r.residual.toFixed(2)}`], []);
}
{
  // clear is colourless only: the two-pass channel spread decides
  const grey = deriveReport({ ...WATER.m, absorptionR: 0.02, absorptionG: 0.02, absorptionB: 0.02, gasMode: 0 }, WATER.d);
  const tint = deriveReport({ ...WATER.m, absorptionR: 0, absorptionG: 0, absorptionB: 0.3, gasMode: 0 }, WATER.d);
  report(`clear needs a colourless liquid: grey K 0.02 → ${grey.classes.opacity}, blue-absorbing K_B 0.3 → ${tint.classes.opacity} (T ${tint.coords.Tsnap.toFixed(3)})`,
    grey.classes.opacity === 'clear' && tint.classes.opacity === 'translucent' && tint.coords.Tsnap <= 0.55 ? [] : ['spread rule'], []);
  report('clear/tinted pair coherent', coherenceIssues(grey.params, grey.classes).concat(coherenceIssues(tint.params, tint.classes)), []);
}
{
  const target = [enc255(0.2), enc255(0.2), enc255(0.2)], back = [0, 0, 0];
  const pre = preImage(target, back, 0.5, false), shown = Math.round(pre[0]);
  const comp = 0.5 * shown;
  report(`composite: black back, T 0.5, linear 0.2 → pre-image ${pre[0].toFixed(2)} ≈ 248, composite ${comp} ≈ 124 levels`,
    Math.abs(pre[0] - 248) <= 1 && Math.abs(comp - 124) <= 1 && compositeResidual([shown, shown, shown], back, 0.5, target) <= 1 ? [] : [`${pre[0]} ${comp}`], []);
}
{
  const r = boundary('gradient backing (2: dark tubeBack, light tubeBack2)', OIL.m, { ...OIL.d, tubeBack: '#050403', tubeBack2: '#b0a898', tubeBackGradient: 2, markContrast: 0 });   // opaque on this backing
  if (r) report(`boundary gradient backing: centre residual ${r.residual.toFixed(2)} ≤ 5 levels (T ${r.coords.T.toFixed(3)} via T_max)`, r.residual <= 5 ? [] : [`residual ${r.residual.toFixed(2)}`], []);
  const u = boundary('light uniform backing (parchment) behind oil', OIL.m, fdesign('#f1e6cf'));
  if (u) report(`boundary parchment: centre residual ${u.residual.toFixed(2)} ≤ 5 levels (T ${u.coords.T.toFixed(3)} via T_max)`, u.residual <= 5 ? [] : [`residual ${u.residual.toFixed(2)}`], []);
}
// bubbleRim is the side light, not the backing: a bubble reads darker than a white backing and brighter than a
// black one (frizzante; the white design's on-top tick colours are a design rejection, not the colour's concern)
{
  const FR = MATERIAL_PRESETS.find((e) => e.id === 'frizzante')!;
  for (const [back, below] of [['#ffffff', true], ['#000000', false]] as const) {
    const rim = deriveReport(FR.material, { ...FR.design, tubeBack: back, tubeBack2: back }).params.bubbleRim;
    const lr = luma(rim), lb = luma(back);
    report(`bubbleRim frizzante on ${back}: luma ${lr.toFixed(1)} ${below ? '<' : '>'} backing ${lb.toFixed(1)} (${rim})`, (below ? lr < lb : lr > lb) ? [] : [`luma ${lr.toFixed(1)}`], []);
  }
}
// A bubble totally reflects the light inside the liquid and its centre is a window: on a dark backing every see-through
// (clear / translucent) gas preset's fizz ring (the real palette's ring rows) is brighter than the liquid on at least 2/3 of the bore rows (the
// surface highlight in front may stay above it), and the core tint is the Fresnel loss of two surfaces (< 0.1).
// The ring colour carries the liquid's filter: a tinted liquid's rim is not grey.
{
  const L565 = (v: number): number => { const [r, g, b] = rgb565to888(v); return 0.299 * r + 0.587 * g + 0.114 * b; };
  for (const e of MATERIAL_PRESETS) {
    const r = deriveReport(e.material, e.design);
    if (!r.params.fizz) continue;
    report(`bubbleDark ${e.id}: ${r.params.bubbleDark.toFixed(3)} < 0.1 (window core)`, r.params.bubbleDark < 0.1 ? [] : [`${r.params.bubbleDark}`], []);
    if (luma(r.params.tubeBack) >= 32 || r.classes.opacity === 'opaque') continue;
    const pal = buildPalette(r.params);
    let n = 0, up = 0;
    for (let y = 0; y < pal.rows.length; y++) if (pal.dryT[y] >= 0.99) { n++; if (L565(pal.bubbleRimRows[y]) > L565(pal.rows[y])) up++; }
    report(`fizz ring ${e.id} on a dark backing: brighter than the liquid on ${up}/${n} bore rows (≥ 2/3)`, up * 3 >= n * 2 ? [] : [`${up}/${n}`], []);
  }
  const OILP = MATERIAL_PRESETS.find((e) => e.id === 'aerated-oil')!;
  const [rr, , rb] = hexRgb(deriveReport(OILP.material, OILP.design).params.bubbleRim);
  report(`bubbleRim aerated-oil carries the oil's filter: blue ${rb} < red ${rr} − 40`, rb < rr - 40 ? [] : [`${rr} ${rb}`], []);
}
{
  const MILK = FIXTURES[6];
  const r = boundary('milk at exposure 1.1 (bright body, highlight floored above it)', { ...MILK.m, exposure: 1.1 }, MILK.d);
  if (r) report(`boundary milk exposure 1.1: luma(liquidHi) ${luma(r.params.liquidHi).toFixed(1)} > luma(liquid) ${luma(r.params.liquid).toFixed(1)}`,
    luma(r.params.liquidHi) > luma(r.params.liquid) ? [] : ['highlight not above the body'], []);
}
{
  const at = (mu: number): DeriveReport | null => boundary(`μ_eff ${mu}`, { ...WATER.m, viscosity: mu, gasMode: 0, solidsFraction: 0.3 }, WATER.d);
  const [w, m0, m1, m2, v0, v1] = [2.49, 2.5, 2.51, 499.99, 500, 500.01].map(at);
  if (w && m0 && m1 && m2 && v0 && v1) {
    report('μ_eff 2.49 / 2.5 / 2.51: watery / medium / medium', [w, m0, m1].map((r) => r.classes.viscosity).join() === 'watery,medium,medium' ? [] : [[w, m0, m1].map((r) => r.classes.viscosity).join()], []);
    report('μ_eff 499.99 / 500 / 500.01: medium / viscous / viscous', [m2, v0, v1].map((r) => r.classes.viscosity).join() === 'medium,viscous,viscous' ? [] : [[m2, v0, v1].map((r) => r.classes.viscosity).join()], []);
    report(`μ_eff 500: traces on, traceDrain ${v0.params.traceDrain} ≤ 20`, v0.params.traces && v0.params.traceDrain <= 20 ? [] : [`${v0.params.traces} ${v0.params.traceDrain}`], []);
    report(`freeDamp jumps up at 2.5 (${w.params.freeDamp.toFixed(3)} → ${m0.params.freeDamp}) and at 500 (${m2.params.freeDamp.toFixed(3)} → ${v0.params.freeDamp})`,
      w.params.freeDamp < m0.params.freeDamp && m2.params.freeDamp < v0.params.freeDamp && m0.params.freeDamp <= m1.params.freeDamp && v0.params.freeDamp <= v1.params.freeDamp ? [] : ['jump direction'], []);
  }
}

{
  // row mapping: bore position u sits at display offset d(u) = u·r/(r + wall); the palette chord at the wall sample
  const d = displayOffset(U_WALL, WATER.m);
  report(`row mapping: d(0.85) = ${d.toFixed(3)} ≈ 0.695, t = ${((1 + d) / 2).toFixed(3)} ≈ 0.848, chord ${paletteChord(d).toFixed(3)}`,
    Math.abs(d - 0.6955) < 1e-3 && Math.abs((1 + d) / 2 - 0.848) < 1e-3 ? [] : [`${d}`], []);
  // a bright scattering body on black: either snaps down through T_up to residual ≤ 5 or is rejected (10), never shown wrong
  for (const S of [0.05, 0.1]) {
    const m = { ...DEFAULT_MATERIAL, scattering: S, absorptionR: 0, absorptionG: 0.3, absorptionB: 0.3, exposure: 4 };
    const r = deriveReport(m, fdesign('#000000'));
    const codes = [...new Set(r.issues.map((s) => s.slice(0, 13)))];
    const ok = r.issues.length ? codes.includes('rejection 10 ') : r.residual <= 5;
    report(`bright scattering body S ${S}, K (0, 0.3, 0.3), exposure 4, black: ${r.issues.length ? `rejected ${codes.join(' ')}` : `derives, T ${r.coords.Tsnap.toFixed(3)} (T_up ${r.coords.Tup.toFixed(3)}), residual ${r.residual.toFixed(2)}`}`,
      ok ? [] : [r.issues.length ? r.issues.join(' | ') : `residual ${r.residual.toFixed(2)}`], []);
  }
}

{
  // bubble radius → drawn size: the law 2·r_b·pxPerMm in every gas class, bounded only by the drawable 1–16 px
  for (const [gas, gasMode] of [['carbonated', 1], ['boiling', 2], ['trapped', 3]] as const) {
    const bad: string[] = [];
    for (const rb of [0.02, 0.05, 0.1, 0.2, 0.3, 0.4]) {
      const r = deriveReport({ ...WATER.m, gasMode, bubbleRadius: rb }, WATER.d);
      const want = Math.min(16, Math.max(1, 2 * rb * r.coords.pxPerMm));
      bad.push(...r.issues.map((s) => `r_b ${rb}: ${s}`), ...coherenceIssues(r.params, r.classes).map((s) => `r_b ${rb}: ${s}`));
      if (Math.abs(r.params.fizzSize - want) > 1e-9) bad.push(`r_b ${rb}: fizzSize ${r.params.fizzSize} ≠ ${want}`);
    }
    report(`bubble radius 0.02–0.4 mm (${gas}): fizzSize = 2·r_b·pxPerMm within [1, 16], derives, coherent`, bad, []);
  }
}

// ---------------------------------------------------------------------------------------------
// 11. Viscosity sweep μ = 0.2 … 1e5 (40 log steps): whole-range monotonicity. (i) the water fixture as
//     is (dissolved gas: every non-watery point carries exactly rejection 2 and is read from the report);
//     (ii) the water fixture with trapped gas and solids 0.3 (every point derives and is coherent).
const DOWN = ['freeBounce', 'meniscusK', 'angleTiltGain', 'angleGyroGain', 'traceDrain', 'fizzSpeed'] as const;
const UP = ['freeDamp', 'meniscusDamp', 'contactDyn', 'wetFilm', 'traceFilm'] as const;
const MUS = Array.from({ length: 40 }, (_, i) => 0.2 * (1e5 / 0.2) ** (i / 39));
for (const [label, extra] of [['water fixture', {}], ['water + trapped gas + solids 0.3', { gasMode: 3, solidsFraction: 0.3 }]] as const) {
  const rows = MUS.map((mu) => deriveReport({ ...WATER.m, ...extra, viscosity: mu }, WATER.d));
  const rej = rows.flatMap((r, i) => r.issues.filter((s) => !(s.startsWith('rejection 2 ') && r.classes.viscosity !== 'watery')).map((s) => `μ ${MUS[i].toPrecision(3)}: ${s}`));
  report(`sweep (${label}): only the listed carbonation rejection`, rej, []);
  if (label !== 'water fixture') {
    const inc = rows.flatMap((r, i) => coherenceIssues(r.params, r.classes).map((s) => `μ ${MUS[i].toPrecision(3)}: ${s}`));
    report(`sweep (${label}): every point coherent`, inc, []);
  }
  for (const k of [...DOWN, ...UP]) {
    const down = (DOWN as readonly string[]).includes(k), bad: string[] = [];
    for (let i = 1; i < rows.length; i++) {
      const a = rows[i - 1].params[k], b = rows[i].params[k];
      if (down ? b > a + 1e-12 : b < a - 1e-12) bad.push(`μ ${MUS[i - 1].toPrecision(3)} → ${MUS[i].toPrecision(3)}: ${a} → ${b}`);
    }
    report(`sweep (${label}): ${k} monotone ${down ? 'non-increasing' : 'non-decreasing'}`, bad, []);
  }
}

// ---------------------------------------------------------------------------------------------
// 12. Rejections: derive throws, naming the reason; deriveReport lists it, and its `problems` mirror the
//     issues one to one with the inputs each points at (material keys / DESIGN_KEYS / legacy keys only).
const PROBLEMS: Record<string, DeriveProblem[]> = {};
function rejected(name: string, m: MaterialProps, d: Design, code: number): void {
  const tag = `rejection ${code} (`;
  let got: string[];
  try { derive(m, d); got = ['accepted']; } catch (error) {
    const msg = (error as Error).message;
    got = msg.includes(tag) ? [] : [msg];
  }
  report(`rejects ${name} (${tag.trim()})`, got, []);
  const r = deriveReport(m, d), bad: string[] = [];
  if (!r.problems.length) bad.push('no problems');
  if (r.problems.length !== r.issues.length) bad.push(`${r.problems.length} problems for ${r.issues.length} issues`);
  r.problems.forEach((p, i) => {
    if (p.text !== r.issues[i]) bad.push(`problem ${i} text ≠ issue: ${p.text}`);
    if (!r.issues[i]?.startsWith(`rejection ${p.code} (`)) bad.push(`problem ${i} code ${p.code}: ${p.text}`);
    for (const k of p.material) if (!(MATERIAL_KEYS as readonly string[]).includes(k)) bad.push(`problem ${i}: ${k} is not a material key`);
    for (const k of p.design) if (!(DESIGN_KEYS as readonly string[]).includes(k)) bad.push(`problem ${i}: ${k} is not a design key`);
    for (const k of p.derived) if (!(k in DEFAULT_PARAMS) || (DESIGN_KEYS as readonly string[]).includes(k)) bad.push(`problem ${i}: ${k} is not a derived / fixed key`);
  });
  report(`  problems of ${name}: one per issue, keys in their sets`, bad, []);
  PROBLEMS[name] = r.problems;
}
/** The problem with `code` of a case above lists `want` (material / design / derived keys). */
function points(name: string, code: number, want: { material?: string[]; design?: string[]; derived?: string[]; noMaterial?: boolean }): void {
  const ps = (PROBLEMS[name] ?? []).filter((p) => p.code === code), bad: string[] = [];
  if (!ps.length) bad.push(`no rejection ${code} among ${(PROBLEMS[name] ?? []).map((p) => p.code).join(', ')}`);
  const has = (field: 'material' | 'design' | 'derived', k: string): boolean => ps.some((p) => (p[field] as string[]).includes(k));
  for (const field of ['material', 'design', 'derived'] as const) for (const k of want[field] ?? []) if (!has(field, k)) bad.push(`${field} lacks ${k}: ${JSON.stringify(ps)}`);
  if (want.noMaterial && ps.some((p) => p.material.length)) bad.push(`material keys listed: ${JSON.stringify(ps)}`);
  const all = (f: 'material' | 'design' | 'derived') => ps.flatMap((p) => p[f] as string[]).join(' ');
  report(`problem ${name} (rejection ${code}) → material [${all('material')}] design [${all('design')}] derived [${all('derived')}]`, bad, []);
}
const EMISSIVE_COLA: MaterialProps = { ...COLA.m, emissionR: 0.4, emissionG: 0.2, emissionB: 0.1 };
report('emissive cola base derives (the rejection 4 base)', (() => { try { derive(EMISSIVE_COLA, COLA.d); return []; } catch (e) { return [(e as Error).message]; } })(), []);
rejected('contact band 80 ± 15 (wetting side touches 90°)', { ...WATER.m, contactAngle: 80, contactHysteresis: 15 }, WATER.d, 1);
rejected('contact band 100 ± 15', { ...WATER.m, contactAngle: 100, contactHysteresis: 15 }, WATER.d, 1);
rejected('contact band 75 ± 15 (exactly 90°)', { ...WATER.m, contactAngle: 75, contactHysteresis: 15 }, WATER.d, 1);
rejected('dissolved gas in a medium liquid', { ...OIL.m, gasMode: 1 }, OIL.d, 2);
rejected('dissolved gas in a metal', { ...FIXTURES[3].m, gasMode: 1 }, FIXTURES[3].d, 2);
rejected('plasma without emission', { ...FIXTURES[4].m, emissionR: 0, emissionG: 0, emissionB: 0 }, FIXTURES[4].d, 3);
rejected('plasma with E_lum 0.02', { ...FIXTURES[4].m, emissionR: 0.02, emissionG: 0.02, emissionB: 0.02 }, FIXTURES[4].d, 3);
rejected('plasma with gas', { ...FIXTURES[4].m, gasMode: 2 }, FIXTURES[4].d, 3);
rejected('plasma with design freeLiquid true', FIXTURES[4].m, { ...FIXTURES[4].d, freeLiquid: true }, 3);
rejected('emissive liquid on tubeBack luma 32', EMISSIVE_COLA, { ...COLA.d, tubeBack: '#202020', tubeBack2: '#202020' }, 4);
rejected('emissive liquid on tubeBack luma 16.1', EMISSIVE_COLA, { ...COLA.d, tubeBack: '#101011', tubeBack2: '#101011' }, 4);
rejected('emissive liquid, gradient on, light tubeBack2', EMISSIVE_COLA, { ...COLA.d, tubeBack2: '#404040', tubeBackGradient: 1 }, 4);
rejected('emissive liquid on the default design (tubeBack2 #253039, gradient 2)', EMISSIVE_COLA, {}, 4);
rejected('clear liquid with emission', { ...WATER.m, gasMode: 0, emissionR: 0.5, emissionG: 0.5, emissionB: 0.5 }, WATER.d, 5);
rejected('no illumination and no emission', { ...WATER.m, ambient: 0, lightIntensity: 0 }, WATER.d, 6);
rejected('design key liquid (derived)', WATER.m, { ...WATER.d, liquid: '#ff0000' } as Design, 7);
rejected('design tubeHeight "54" (wrong type)', WATER.m, { ...WATER.d, tubeHeight: '54' } as unknown as Design, 7);
rejected('viscosity NaN', { ...WATER.m, viscosity: NaN }, WATER.d, 7);
rejected('viscosity 1e6 (out of range)', { ...WATER.m, viscosity: 1e6 }, WATER.d, 7);
rejected('unknown material key', { ...WATER.m, colour: 1 } as unknown as MaterialProps, WATER.d, 7);
rejected('tubeHeight 100 (> 80 px strip)', WATER.m, { ...WATER.d, tubeHeight: 100, digitBottom: 5 }, 7);
rejected('tubeHeight 3', WATER.m, { ...WATER.d, tubeHeight: 3, digitFont: 3 }, 7);
rejected('hoursY 200 with a 54 px tube (off the panel)', WATER.m, { ...WATER.d, hoursY: 200 }, 7);
rejected('minutesY -5', WATER.m, { ...WATER.d, minutesY: -5 }, 7);
rejected('sprite digits taller than the tube', WATER.m, { ...WATER.d, digitBottom: 30, digitScaleY: 3.25 }, 8);
rejected('design freeHomeK -1 (bounds)', WATER.m, { ...WATER.d, freeHomeK: -1 }, 7);
rejected('design readTiltStart 60 ≥ readTiltEnd 50', WATER.m, { ...WATER.d, readTiltStart: 60, readTiltEnd: 50 }, 7);
rejected('design playHold -1', WATER.m, { ...WATER.d, playHold: -1 }, 7);
rejected('design digitScaleX 0', WATER.m, { ...WATER.d, digitScaleX: 0 }, 7);
rejected('design digitFont 5.5 (integer field)', WATER.m, { ...WATER.d, digitFont: 5.5 }, 7);
rejected('design tubeBackGradient 7 (beyond its options)', WATER.m, { ...WATER.d, tubeBackGradient: 7 }, 7);
rejected('design tickStepH 1.5 (integer field)', WATER.m, { ...WATER.d, tickStepH: 1.5 }, 7);
// Astra's design mutations: the result would break the realism rules → rejection 11, design never rewritten
rejected('freeLiquid false for a liquid', WATER.m, { ...WATER.d, freeLiquid: false }, 11);
rejected('sprite digitScaleX 2 / digitScaleY 3', WATER.m, { ...WATER.d, digitScaleX: 2, digitScaleY: 3 }, 11);
rejected('front tickColorH #000000 on a black backing', FIXTURES[5].m, { ...FIXTURES[5].d, tubeBack: '#000000', tubeBack2: '#000000', tickColorH: '#000000' }, 11);
rejected('digitBright 10', WATER.m, { ...WATER.d, digitBright: 10 }, 11);
rejected('tickBright 1.5 (in bounds, outside the realism range)', WATER.m, { ...WATER.d, tickBright: 1.5 }, 11);
points('contact band 80 ± 15 (wetting side touches 90°)', 1, { material: ['contactAngle', 'contactHysteresis'] });
points('plasma without emission', 3, { material: ['phase', 'emissionG'] });
points('plasma with gas', 3, { material: ['phase', 'gasMode'] });
points('plasma with design freeLiquid true', 3, { material: ['phase'], design: ['freeLiquid'] });
points('emissive liquid, gradient on, light tubeBack2', 4, { material: ['emissionR'], design: ['tubeBack2'] });
points('hoursY 200 with a 54 px tube (off the panel)', 7, { design: ['hoursY'] });
points('viscosity 1e6 (out of range)', 7, { material: ['viscosity'] });
points('design readTiltStart 60 ≥ readTiltEnd 50', 7, { design: ['readTiltStart', 'readTiltEnd'] });
points('sprite digits taller than the tube', 8, { design: ['digitBottom', 'digitScaleY', 'tubeHeight'] });
points('tickBright 1.5 (in bounds, outside the realism range)', 11, { design: ['tickBright'], noMaterial: true });
points('freeLiquid false for a liquid', 11, { design: ['freeLiquid'], noMaterial: true });
points('front tickColorH #000000 on a black backing', 11, { design: ['tickColorH', 'tubeBack'] });
points('digitBright 10', 11, { design: ['digitBright'] });
{
  // a realism message naming a derived value points at its material drivers; unknown keys point at nothing
  const cases: [string, string[], string[], string[]][] = [
    ['freeDamp = 20 not in [6, 14] for viscous', ['viscosity', 'density', 'surfaceTension', 'innerRadius'], [], ['freeDamp']],
    ['luma(liquid) < luma(liquidHi)', ['absorptionR', 'scattering', 'exposure'], ['tubeBack'], ['liquid', 'liquidHi']],
    ['traceDrain 50 > 20 for viscous', ['solidsFraction', 'dryingTime', 'viscosity', 'density', 'innerRadius'], [], ['traceDrain']],
    ['carbonated: fizz must be on', ['gasMode', 'gasLevel', 'bubbleRadius'], [], ['fizz']],
    ['emissive: glowStrength 0.2 not in [0.4, 0.8]', ['emissionR', 'emissionG', 'emissionB'], [], ['glowStrength']],
    ['emissive: tube back luma 40 ≥ 16', [], ['tubeBack'], []],
    ['a liquid is a free slug: freeLiquid must be on', [], ['freeLiquid'], []],
    ['carbonated implies watery', [], [], []],
  ];
  for (const [msg, mat, des, der] of cases) {
    const p = coherenceProblem(msg), bad: string[] = [];
    for (const k of mat) if (!p.material.includes(k as never)) bad.push(`material lacks ${k}`);
    for (const k of des) if (!p.design.includes(k as never)) bad.push(`design lacks ${k}`);
    for (const k of der) if (!p.derived.includes(k as never)) bad.push(`derived lacks ${k}`);
    if (!mat.length && p.material.length) bad.push(`material ${p.material.join(' ')} (want none)`);
    if (!der.length && p.derived.length) bad.push(`derived ${p.derived.join(' ')} (want none)`);
    report(`coherenceProblem "${msg}" → [${p.material.join(' ')}] [${p.design.join(' ')}] [${p.derived.join(' ')}]`, bad, []);
  }
}
{
  const p = derive(WATER.m, WATER.d);
  report('rejection 11 never rewrites design: an accepted design passes through unchanged', p.freeLiquid === true && p.digitBright === DEFAULT_PARAMS.digitBright ? [] : ['rewritten'], []);
}
rejected('milk at exposure 3 (overexposed body)', { ...FIXTURES[6].m, exposure: 3 }, FIXTURES[6].d, 9);
// the doc names no liquid for the white-backing case: water (clear, backing-free body) and olive oil (luma 226)
// stay below 248 there, milk does not
rejected('milk on a white backing at exposure 2.5, ambient 0.6 (overexposed)', { ...FIXTURES[6].m, exposure: 2.5, ambient: 0.6 }, fdesign('#ffffff'), 9);
{
  const r = deriveReport({ ...WATER.m, contactAngle: 85, contactHysteresis: 10, gasMode: 1, viscosity: 50 }, { ...WATER.d, hoursY: 230 });
  const codes = new Set(r.issues.map((s) => /^rejection \d+/.exec(s)?.[0] ?? s));
  report(`deriveReport lists every rejection (1, 2, 7 among ${[...codes].join(', ')})`, ['rejection 7', 'rejection 1', 'rejection 2'].every((c) => codes.has(c)) ? [] : r.issues, []);
  report('deriveReport with rejections still returns finite params', finiteIssues(r.params), []);
}
{
  const OLIVE = MATERIAL_PRESETS.find((e) => e.id === 'olive-oil')!;
  rejected('olive oil in a 0.5 mm bore with a 1 mm wall (unattainable rim)', { ...OLIVE.material, innerRadius: 0.5, wallThickness: 1.0 } as MaterialProps, OLIVE.design, 12);
}
points('milk on a white backing at exposure 2.5, ambient 0.6 (overexposed)', 9, { material: ['exposure', 'lightIntensity', 'ambient'], design: ['tubeBack'] });
points('olive oil in a 0.5 mm bore with a 1 mm wall (unattainable rim)', 12, { material: ['wallThickness', 'innerRadius'] });
accepts('opaque liquid with rear marks is allowed (markContrast 0)', () => {
  const p = derive(FIXTURES[5].m, fdesign('#050203'));
  if (p.markContrast !== 0) throw new Error(`markContrast ${p.markContrast}`);
});
{
  // a design markContrast passes through up to 120·T and is rejected above it, pointing at itself and the optics
  const T = derive(FIXTURES[5].m, fdesign('#050203')).liquidTransparency, cap = Math.floor(MARK_CONTRAST_PER_T * T);
  accepts(`opaque liquid, rear marks, markContrast ${cap} (≤ 120·T ${T.toFixed(3)}) passes through`, () => {
    const p = derive(FIXTURES[5].m, fdesign('#050203', { markContrast: cap }));
    if (p.markContrast !== cap) throw new Error(`markContrast ${p.markContrast}`);
  });
  rejected('opaque liquid, rear marks, markContrast 24 (> 120·T)', FIXTURES[5].m, fdesign('#050203', REAR24), 11);
  points('opaque liquid, rear marks, markContrast 24 (> 120·T)', 11, { design: ['markContrast'], derived: ['liquidTransparency'], material: ['scattering'] });
}

// ---------------------------------------------------------------------------------------------
// 13. Sampled inputs: 200 seeded pseudo-random valid materials × (3 fixed designs + 1 sampled design). derive succeeds or throws
//     only listed rejections; every success is coherent (a failure is a law bug: printed with its input).
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rnd = mulberry32(20260925);
const pick = (lo: number, hi: number): number => lo + (hi - lo) * rnd();
const logPick = (lo: number, hi: number): number => Math.exp(pick(Math.log(lo), Math.log(hi)));
function sampleMaterial(): MaterialProps {
  const m = { ...DEFAULT_MATERIAL };
  for (const meta of MATERIAL_META) {
    const v = meta.integer ? Math.floor(pick(meta.min, meta.max + 1 - 1e-9)) : meta.log ? logPick(Math.max(meta.min, 1e-3), meta.max) : pick(meta.min, meta.max);
    m[meta.key] = +v.toPrecision(6);
  }
  // shape the draw toward the realistic families (every draw stays inside the schema bounds)
  m.phase = rnd() < 0.1 ? 1 : 0;
  m.metallic = rnd() < 0.15 ? 1 : 0;
  for (const k of ['absorptionR', 'absorptionG', 'absorptionB'] as const) if (rnd() < 0.2) m[k] = 0;
  if (rnd() < 0.5) m.scattering = 0;
  if (rnd() < 0.7) { m.emissionR = 0; m.emissionG = 0; m.emissionB = 0; }
  return m;
}
const SAMPLE_DESIGNS: Array<[string, Design]> = [
  ['DEFAULT_PARAMS design', {}],
  ['pale backing, rear marks', { tubeHeight: 54, hoursY: 0, minutesY: 185, tubeBack: '#f2eee5', tubeBack2: '#f2eee5', tubeBackGradient: 0, digitFont: 10, digitScaleX: 3.3, digitScaleY: 3.1, digitBottom: 10 }],
  ['black backing, front print, vector digits', { tubeHeight: 40, hoursY: 10, minutesY: 190, tubeBack: '#000000', tubeBack2: '#000000', tubeBackGradient: 0, ...FRONT, digitFont: 3, digitColor: '#e3e3e3' }],
];
{
  let ok = 0, rejectedN = 0;
  const okBy = new Map<string, number>();
  const unlisted: string[] = [], incoherent: string[] = [];
  const byCode = new Map<string, number>();
  /** The material's own sampled design: every numeric design field uniform within its PARAM_META bounds
   *  (integers where the field is one), each boolean flipped from DEFAULT_PARAMS by a coin toss (flipping all
   *  of them turns freeLiquid off for every liquid, a certain rejection 11); colours kept. */
  const sampleDesign = (): Design => {
    const d: Record<string, unknown> = {};
    for (const k of DESIGN_KEYS) {
      const v = DEFAULT_PARAMS[k], meta = PARAM_META[k];
      if (typeof v === 'boolean') d[k] = rnd() < 0.5 ? !v : v;
      else if (typeof v === 'number' && meta) {
        const lo = meta.min ?? 0, hi = meta.max ?? (meta.options ? meta.options.length - 1 : undefined);
        if (hi === undefined) continue;
        const integer = !!meta.options || (meta.step !== undefined && Number.isInteger(meta.step) && Number.isInteger(lo));
        const x = pick(lo, hi);
        d[k] = integer ? Math.min(hi, Math.floor(x + 0.5)) : +x.toPrecision(6);
      }
    }
    if ((d.readTiltStart as number) >= (d.readTiltEnd as number)) d.readTiltEnd = Math.min(90, (d.readTiltStart as number) + 1);
    return d as Design;
  };
  for (let i = 0; i < 200; i++) {
    const m = sampleMaterial();
    for (const [dn, d] of [...SAMPLE_DESIGNS, ['sampled design', sampleDesign()] as [string, Design]]) {
      let p: Params;
      try { p = derive(m, d); } catch (error) {
        rejectedN++;
        const lines = (error as Error).message.split('\n').slice(1).map((s) => s.slice(2));
        for (const s of lines) {
          const code = /^rejection (?:[1-9]|1[012]) \(/.exec(s)?.[0];
          if (!code || !/^material rejected:/.test((error as Error).message)) unlisted.push(`#${i} ${dn}: ${s}`);
          else byCode.set(code, (byCode.get(code) ?? 0) + 1);
        }
        continue;
      }
      ok++;
      okBy.set(dn, (okBy.get(dn) ?? 0) + 1);
      const r = deriveReport(m, d);
      const inc = coherenceIssues(p, r.classes).concat(finiteIssues(p));
      if (p.rimLight > 0) {
        const err = wallError(r, m);
        if (err !== r.rim.error || (err > RIM_TOLERANCE && !(r.rim.rimError <= RIM_TOLERANCE && r.rim.bodyOver === err && r.rim.bodyOver <= BODY_OVER_TOLERANCE)))
          inc.push(`rim: wall error ${err} levels accepted (derive: error ${r.rim.error}, rim ${r.rim.rimError}, body overshoot ${r.rim.bodyOver})`);
      }
      if (inc.length) incoherent.push(`#${i} ${dn} ${JSON.stringify(r.classes)}: ${inc.join('; ')}\n      material ${JSON.stringify(m)}`);
    }
  }
  console.log(`  sampled: ${ok} derived, ${rejectedN} rejected (${[...byCode].sort((a, b) => parseInt(a[0].slice(10)) - parseInt(b[0].slice(10))).map(([c, n]) => `${c.slice(10, -2)}×${n}`).join(' ')})`);
  console.log(`  sampled successes per design: ${[...okBy].map(([k, n]) => `${k} ${n}`).join(', ')}`);
  report('sampled: every rejection is a listed one', unlisted, []);
  report(`sampled: at least 150 of 800 derive (${ok})`, ok >= 150 ? [] : [`only ${ok}`], []);
  report(`sampled: every derived Params is coherent and finite (${incoherent.length} law bug(s))`, incoherent, []);
}

// ---------------------------------------------------------------------------------------------
// 14. Material presets (src/material/presets.ts), the physical collection: the ids are exactly the
//     pinned list, every entry derives without rejection, is coherent for its inferred class, has a
//     design inside the allowlist and complete provenance, and presets/materials/<id>.json and
//     presets/physical/<id>.json equal a fresh serialize / derive (npm run dump:presets rewrites them).
{
  const COLLECTION = ['frizzante', 'alpine', 'olive-oil', 'aerated-oil', 'honey', 'glycerine', 'blood', 'milk', 'mercury', 'cola', 'champagne', 'cuvee',
    'ink', 'nocturne', 'glow', 'xenon', 'molten', 'urine', 'malt', 'cryo', 'pinot', 'spritz', 'tide', 'phosphor'];
  const got = MATERIAL_PRESETS.map((e) => e.id);
  report('material presets: ids are exactly the collection, in order', got.join(' ') === COLLECTION.join(' ') ? [] : [`got ${got.join(' ')}`], []);
  const fs = require('fs'), path = require('path');
  const root = path.join(process.cwd(), '..', 'presets');
  const fresh = (dir: string, id: string, want: () => string): string[] => {
    const f = path.join(root, dir, id + '.json');
    if (!fs.existsSync(f)) return [`${dir}/${id}.json missing (npm run dump:presets)`];
    let w: string;
    try { w = want(); } catch (error) { return [(error as Error).message]; }
    return fs.readFileSync(f, 'utf8') === w ? [] : [`${dir}/${id}.json is stale (npm run dump:presets)`];
  };
  for (const dir of ['materials', 'physical']) {
    const on = fs.existsSync(path.join(root, dir)) ? fs.readdirSync(path.join(root, dir)) as string[] : [];
    const extra = on.filter((f) => !COLLECTION.includes(f.replace(/\.json$/, ''))).map((f) => `presets/${dir}/${f} is not in the collection`);
    report(`presets/${dir}: no file outside the collection`, extra, []);
  }
  const ids = new Set<string>();
  for (const e of MATERIAL_PRESETS) {
    report(`material preset ${e.id}: unique id`, ids.has(e.id) ? ['duplicate id'] : [], []);
    ids.add(e.id);
    const env: string[] = [];
    try { parseMaterialEnvelope({ kind: 'liquid-watch-material', version: MATERIAL_VERSION, name: e.name, material: e.material, design: e.design, provenance: e.provenance }); }
    catch (error) { env.push((error as Error).message); }
    report(`material preset ${e.id}: valid envelope (material, design, provenance)`, env, []);
    const missing = MATERIAL_META.filter((m) => !e.provenance[m.key]).map((m) => `no provenance for ${m.key}`);
    report(`material preset ${e.id}: provenance for every property`, missing, []);
    const r = deriveReport(e.material, e.design);
    report(`material preset ${e.id}: derives without rejection`, r.issues, []);
    report(`material preset ${e.id}: coherent as ${JSON.stringify(r.classes)}`, coherenceIssues(r.params, r.classes), []);
    report(`material preset ${e.id}: presets/materials/${e.id}.json is fresh`, fresh('materials', e.id, () => materialPresetFile(e)), []);
    report(`material preset ${e.id}: presets/physical/${e.id}.json is fresh`, fresh('physical', e.id, () => physicalPresetFile(e)), []);
    const back = JSON.parse(fs.readFileSync(path.join(root, 'materials', e.id + '.json'), 'utf8'));
    report(`material preset ${e.id}: material file round-trips`, JSON.stringify(parseMaterialEnvelope(back)) === JSON.stringify(parseMaterialEnvelope(materialPresetFile(e))) ? [] : ['differs'], []);
  }
}

// ---------------------------------------------------------------------------------------------
// 15. Optical kernel (src/material/optics/, ported from the retired phase-1 lab's check): Fresnel at
//     normal incidence, matched indices and TIR; Beer–Lambert composes over thickness and thinner
//     transmits more; the central ray crosses the full bore; every row of a spread of tubes gives a
//     finite path with transmission in [0, 1] and non-negative reflected radiance.
{
  const P0: PhysicalParams = {
    innerRadiusMm: 2.55, wallThicknessMm: 0.45, liquidIor: 1.47, wallIor: 1.49, absorptionR: 0.09, absorptionG: 0.12,
    absorptionB: 0.8, lightAngleDeg: -35, lightSizeDeg: 30, lightIntensity: 2, ambientIntensity: 0.15,
    backingReflectance: 0.35, marksReflectance: 0.85, exposure: 1, hoursY: 0, minutesY: 168,
  };
  const near = (name: string, got: number, want: number, tol = 1e-6): void =>
    report(`optics: ${name}`, Number.isFinite(got) && Math.abs(got - want) <= tol ? [] : [`${got} != ${want}`], []);
  near('fresnel normal incidence air→1.5', fresnel(1, 1, 1.5), ((1 - 1.5) / (1 + 1.5)) ** 2);
  near('fresnel matched indices (normal) = 0', fresnel(1, 1.5, 1.5), 0);
  near('fresnel matched indices (grazing) = 0', fresnel(0, 1.5, 1.5), 0);
  near('fresnel past the critical angle = 1 (TIR)', fresnel(0.5, 1.5, 1), 1);
  report('optics: refract returns null at TIR', refract({ y: 0.8660254, z: -0.5 }, { y: 0, z: 1 }, 1.5, 1) === null ? [] : ['refracted'], []);
  near('beer composes over thickness', beer(0.8, 1.0), beer(0.8, 0.4) * beer(0.8, 0.6));
  report('optics: thinner film transmits more', beer(0.8, 0.2) > beer(0.8, 0.8) ? [] : ['not monotone'], []);
  near('central ray crosses the full bore', traceRow(0, true, P0).distance, 2 * P0.innerRadiusMm, 1e-5);
  const bad: string[] = [];
  for (const innerRadiusMm of [0.5, 1, 2.55, 3]) for (const wallThicknessMm of [0.05, 0.45, 0.9]) {
    const p = { ...P0, innerRadiusMm, wallThicknessMm }, R = innerRadiusMm + wallThicknessMm;
    for (let i = 0; i < 17; i++) for (const wet of [false, true]) {
      const y = (-1 + (i + 0.5) / 17 * 2) * R, path = traceRow(y, wet, p);
      const at = `r ${innerRadiusMm} wall ${wallThicknessMm} y ${y.toFixed(3)} ${wet ? 'wet' : 'dry'}`;
      if (![path.distance, path.transmission, path.reflection, path.backY].every(Number.isFinite)) bad.push(`${at}: non-finite path`);
      if (path.transmission < -1e-6 || path.transmission > 1 + 1e-6) bad.push(`${at}: transmission ${path.transmission}`);
      if (path.reflection < -1e-6) bad.push(`${at}: reflection ${path.reflection}`);
    }
  }
  report('optics: 12 tubes × 17 rows × wet/dry: finite, transmission in [0,1], reflection ≥ 0', bad, []);
}

console.log(`${fixtures} fixture(s), ${failures} failure(s)`);
if (failures) process.exit(1);
