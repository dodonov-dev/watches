// The physical signature collection: one material preset per legacy signature look, plus material-only
// liquids with a design of their own. Each entry is a material (values decided in the plan, handbook where
// the liquid is known) plus a design (the allowlisted legacy keys the legacy preset of the same id sets
// explicitly in params.ts: layout, backing, marks, digits; or the entry's own). derive() fills every other
// Params key. Every entry must derive without
// rejection and be coherent for its inferred class (tools/check-materials.ts, section 14); the envelopes
// and derived Params are written to presets/materials/ and presets/physical/ (npm run dump:presets).
import { DESIGN_H as PANEL_H, DESIGN_TUBE_HEIGHT_MAX as TUBE_HEIGHT_MAX } from '../../../spec/layout';   // preset params are in design px
import { DEFAULT_PARAMS, MODERN_BASE, PRESETS, type Params } from '../params';
import { derive } from './derive';
import {
  DEFAULT_MATERIAL, DESIGN_KEYS, MATERIAL_KEYS, serializeMaterialEnvelope,
  type Design, type Material, type MaterialKey, type MaterialProvenance, type Provenance,
} from './model';

export interface MaterialPreset {
  readonly id: string;
  readonly name: string;
  readonly note: string;
  /** Where the values come from, in words (presets/PRESETS.md "Physical collection"). */
  readonly source: string;
  readonly material: Material;
  readonly design: Design;
  readonly provenance: MaterialProvenance;
}

/** Design keys the legacy preset `id` sets explicitly (its own fields and the bases it spreads), plus
 *  `extra`. The tube rows are written as the legacy renderer draws them: tubeLayout clamps a tube that
 *  would leave the panel (LAYOUT_WIDE's minutesY 224 draws at 185), derive rejects it (rejection 7). */
function designOf(id: string, extra: Design = {}): Design {
  const e = PRESETS.find((x) => x.id === id);
  if (!e) throw new Error(`material preset design: no legacy preset ${id}`);
  // canonical DESIGN_KEYS order (the legacy keys, `extra` over them), as a session restore writes it
  const src: Record<string, unknown> = { ...e.p, ...extra }, d: Record<string, unknown> = {};
  for (const k of DESIGN_KEYS) if (Object.prototype.hasOwnProperty.call(src, k)) d[k] = src[k];
  const out = d as Design;
  const H = Math.max(4, Math.min(TUBE_HEIGHT_MAX, Math.round(out.tubeHeight ?? DEFAULT_PARAMS.tubeHeight)));
  for (const k of ['hoursY', 'minutesY'] as const) {
    if (out[k] !== undefined) out[k] = Math.max(0, Math.min(PANEL_H - H, Math.round(out[k]!)));
  }
  return out;
}

/** The fizz look (size spread, core offset, depth fade, pinpoint, squash, across-tilt steering): fixed policy
 *  until 2026-09-26, now design keys. Every entry pins these values, so its derived Params are unchanged. */
const FIZZ_LOOK: Design = { fizzSizeVar: 0.5, fizzShadeOff: 0.3, fizzDepth: 0.7, fizzBlick: 0.6, fizzSquash: 1.25, fizzAcrossGain: 1.05 };

/** markContrast was derived until 2026-09-26 (24 for rear marks behind a non-opaque liquid, else 0) and is a
 *  design key since: every entry pins the value it derived, so its derived Params are unchanged. The entries
 *  that derived 24: */
const MARK_FLOOR_24: ReadonlySet<string> = new Set([
  'alpine', 'aerated-oil', 'honey', 'glycerine', 'cola', 'champagne', 'cuvee', 'olive-oil', 'urine', 'malt', 'cryo', 'spritz', 'xenon',
]);
const markFloor = (id: string): Design => ({ markContrast: MARK_FLOOR_24.has(id) ? 24 : 0 });

/** An own design: the DESIGN_KEYS of `p` (a look built on the house base, no legacy preset behind it). */
function designFrom(p: Partial<Params>): Design {
  const d: Record<string, unknown> = {};
  for (const k of DESIGN_KEYS) if (Object.prototype.hasOwnProperty.call(p, k)) d[k] = p[k];
  return d as Design;
}

/** Provenance by property family (doc "Provenance of preset values"): the fluid handbook values
 *  (viscosity, density, surface tension, index) are measured for a known liquid and estimated otherwise;
 *  optical coefficients, wetting, residue, drying and gas are estimated; emission and lighting artistic. */
const FLUID_KEYS: readonly MaterialKey[] = ['viscosity', 'density', 'surfaceTension', 'ior'];
const BASE_PROVENANCE: Record<MaterialKey, Provenance> = {
  ior: 'estimated', absorptionR: 'estimated', absorptionG: 'estimated', absorptionB: 'estimated', scattering: 'estimated',
  emissionR: 'artistic', emissionG: 'artistic', emissionB: 'artistic', metallic: 'measured', metalReflectance: 'estimated',
  phase: 'measured', density: 'estimated', viscosity: 'estimated', surfaceTension: 'estimated',
  contactAngle: 'estimated', contactHysteresis: 'estimated', solidsFraction: 'estimated', dryingTime: 'estimated',
  gasMode: 'estimated', gasLevel: 'estimated', bubbleRadius: 'estimated', foamStability: 'estimated',
  innerRadius: 'estimated', wallThickness: 'estimated', wallIor: 'measured',
  lightElevation: 'artistic', lightSize: 'artistic', lightIntensity: 'artistic', ambient: 'artistic', exposure: 'artistic',
};
function provenance(handbook: boolean, over: MaterialProvenance = {}): MaterialProvenance {
  const p: MaterialProvenance = {};
  for (const k of MATERIAL_KEYS) p[k] = over[k] ?? (handbook && FLUID_KEYS.includes(k) ? 'measured' : BASE_PROVENANCE[k]);
  return p;
}

interface EntryOptions {
  /** The fluid values are handbook values of a known liquid (measured). */
  handbook?: boolean;
  /** Per-property provenance overrides. */
  over?: MaterialProvenance;
  /** Design keys changed from the legacy look, each forced by a named derive rejection. */
  extra?: Design;
}
/** A collection entry: `id` is also the legacy preset whose name and design keys it takes. */
function entry(id: string, note: string, source: string, m: Partial<Material>, o: EntryOptions = {}): MaterialPreset {
  const legacy = PRESETS.find((x) => x.id === id);
  if (!legacy) throw new Error(`material preset ${id}: no legacy preset of that id`);
  return {
    id, name: legacy.name, note, source,
    material: { ...DEFAULT_MATERIAL, ...m },
    design: designOf(id, { ...FIZZ_LOOK, ...markFloor(id), ...o.extra }),
    provenance: provenance(o.handbook ?? false, o.over),
  };
}

/** A material-only entry: no legacy preset of that id; the design is its own (designFrom). */
function own(id: string, name: string, note: string, source: string, m: Partial<Material>, design: Design, o: Omit<EntryOptions, 'extra'> = {}): MaterialPreset {
  if (PRESETS.some((x) => x.id === id)) throw new Error(`material preset ${id}: a legacy preset has that id (use entry)`);
  return { id, name, note, source, material: { ...DEFAULT_MATERIAL, ...m }, design: { ...design, ...markFloor(id) }, provenance: provenance(o.handbook ?? false, o.over) };
}

/** Standard rod, rear marks behind the liquid (the house base on the 54 px rod, alpine's mark scale). */
const REAR_ROD: Partial<Params> = {
  ...MODERN_BASE, ...FIZZ_LOOK,
  tubeHeight: 54, hoursY: 0, minutesY: 185, remaining: true, lens: -0.2, lensCurve: 0.2,
  tickStepH: 1, tickMajorEveryH: 2, tickMinorHeightH: 5, tickMajorHeightH: 7, tickMinorWidthH: 1, tickMajorWidthH: 2,
  tickStepM: 5, tickMajorEveryM: 10, tickMinorHeightM: 5, tickMajorHeightM: 8, tickMinorWidthM: 1, tickMajorWidthM: 2,
  digitScaleX: 3.3, digitScaleY: 3.1, digitBottom: 10, digitScaleXMin: 2.35, digitScaleYMin: 2.35, digitBottomMin: 11,
  digitHourStep: 2, digitMinuteStep: 10,
};

/** The collection ids in display order (check-materials section 14 pins the list). */
export const MATERIAL_PRESETS: readonly MaterialPreset[] = [
  entry('frizzante', 'sparkling water: colourless, watery, fine carbonation bead; lab print', 'handbook; absorption 0',
    { viscosity: 1, density: 998, surfaceTension: 72.8, ior: 1.333, absorptionR: 0, absorptionG: 0, absorptionB: 0, scattering: 0, contactAngle: 20, contactHysteresis: 10, solidsFraction: 0, dryingTime: 1, gasMode: 1, gasLevel: 0.7, bubbleRadius: 0.05, foamStability: 3 },
    { handbook: true }),
  entry('alpine', 'spring water: clear, sparkling, pale ceramic backing, slate markings', 'handbook; trace absorption estimated',
    { viscosity: 1, density: 998, surfaceTension: 72.8, ior: 1.333, absorptionR: 0.002, absorptionG: 0.001, absorptionB: 0, scattering: 0, contactAngle: 20, contactHysteresis: 10, solidsFraction: 0, dryingTime: 1, gasMode: 1, gasLevel: 0.6, bubbleRadius: 0.05, foamStability: 2.5 },
    { handbook: true }),
  entry('olive-oil', 'olive oil: golden-green, medium viscosity, lingering oily residue', 'handbook; absorption estimated',
    { viscosity: 84, density: 915, surfaceTension: 32, ior: 1.47, absorptionR: 0.05, absorptionG: 0.07, absorptionB: 0.45, scattering: 0, contactAngle: 15, contactHysteresis: 8, solidsFraction: 0.3, dryingTime: 2, gasMode: 0, exposure: 1.4 },
    // design adjusted: legacy digitBright 2: rejection 11, trim range [0.8, 1.8]
    { handbook: true, extra: { digitBright: 1.8 } }),
  own('aerated-oil', 'Aerated oil', 'shaken sunflower oil: gold, medium viscosity, a dense haze of fine bubbles drifting up slowly; espresso backing, cream print, copper numerals behind',
    'handbook (sunflower oil, 20 °C); absorption estimated; gas level artistic',
    { viscosity: 55, density: 920, surfaceTension: 33, ior: 1.474, absorptionR: 0.01, absorptionG: 0.04, absorptionB: 0.35, scattering: 0, contactAngle: 15, contactHysteresis: 8, solidsFraction: 0.2, dryingTime: 2, gasMode: 3, gasLevel: 0.75, bubbleRadius: 0.15, foamStability: 1, exposure: 2 },
    designFrom({
      ...REAR_ROD,
      tubeBack: '#0b0805', tubeBack2: '#1c150c', tubeBackGradient: 2,
      ticksOnTop: true, tickEmboss: 0, tickLens: 0, tickParallax: 0, tickDryLens: 0, tickPosH: 0, tickPosM: 0,
      tickColorH: '#b39f78', tickMajorColorH: '#efe2c2', tickColorM: '#b39f78', tickMajorColorM: '#efe2c2',
      digitFont: 7, digitTint: '#5b3a1c', digitTintAmount: 0.3, digitTone: -0.1, digitShadowStrength: 0.35,
      tickBright: 1, digitBright: 1.1,
    }),
    { handbook: true, over: { gasLevel: 'artistic' } }),
  entry('honey', 'honey: amber syrup, viscous, clings to the glass, trapped air', 'handbook (viscosity 20 °C ~10 Pa·s); absorption estimated',
    { viscosity: 10000, density: 1420, surfaceTension: 70, ior: 1.49, absorptionR: 0.06, absorptionG: 0.18, absorptionB: 0.7, scattering: 0, contactAngle: 25, contactHysteresis: 20, solidsFraction: 0.8, dryingTime: 2, gasMode: 3, gasLevel: 0.04, bubbleRadius: 0.12, foamStability: 20, exposure: 1.6 },
    { handbook: true }),
  own('glycerine', 'Aerated glycerine', 'glycerine full of air: colourless, viscous, fine bubbles held still in the gel; blue-black backing, steel numerals behind',
    'handbook (glycerol, 20 °C); absorption estimated; gas level artistic',
    { viscosity: 1412, density: 1261, surfaceTension: 63.4, ior: 1.474, absorptionR: 0.002, absorptionG: 0.002, absorptionB: 0.004, scattering: 0, contactAngle: 20, contactHysteresis: 12, solidsFraction: 0.2, dryingTime: 10, gasMode: 3, gasLevel: 1, bubbleRadius: 0.15, foamStability: 30 },
    designFrom({
      ...REAR_ROD,
      tubeBack: '#03060a', tubeBack2: '#0f1822', tubeBackGradient: 2,
      tickColorH: '#50606e', tickMajorColorH: '#8ea3b6', tickColorM: '#50606e', tickMajorColorM: '#8ea3b6',
      digitFont: 5, digitTint: '#9fb4c8', digitTintAmount: 0.2, digitTone: 0,
      tickBright: 1.1, digitBright: 1.2,
    }),
    { handbook: true, over: { gasLevel: 'artistic' } }),
  entry('blood', 'venous blood: opaque scattering red, coats the glass, dries to a stain; syringe print', 'handbook; optical coefficients from tissue-optics literature (reduced scattering)',
    { viscosity: 4, density: 1060, surfaceTension: 58, ior: 1.35, absorptionR: 1, absorptionG: 20, absorptionB: 25, scattering: 1, contactAngle: 30, contactHysteresis: 15, solidsFraction: 0.45, dryingTime: 1.5, gasMode: 0 },
    { handbook: true }),
  entry('milk', 'whole milk: opaque white colloid, soft highlight, printed scale', 'handbook (viscosity at ~10 °C); scattering estimated',
    { viscosity: 2.9, density: 1030, surfaceTension: 45, ior: 1.35, absorptionR: 0.001, absorptionG: 0.001, absorptionB: 0.001, scattering: 3, contactAngle: 30, contactHysteresis: 15, solidsFraction: 0.1, dryingTime: 1, gasMode: 0 },
    { handbook: true }),
  entry('mercury', 'mercury: liquid metal, non-wetting convex bead, mirror specular, etched scale', 'handbook; reflectance estimated',
    { viscosity: 1.55, density: 13546, surfaceTension: 485, ior: 1, metallic: 1, metalReflectance: 0.75, contactAngle: 140, contactHysteresis: 15, solidsFraction: 0, gasMode: 0 },
    { handbook: true, over: { ior: 'estimated' } }),
  entry('cola', 'cola: dark translucent brown, watery, lively bead, enamel numerals', 'estimated',
    { viscosity: 1.2, density: 1040, surfaceTension: 60, ior: 1.35, absorptionR: 0.02, absorptionG: 0.4, absorptionB: 1.4, scattering: 0, contactAngle: 20, contactHysteresis: 10, solidsFraction: 0, dryingTime: 1, gasMode: 1, gasLevel: 0.5, bubbleRadius: 0.07, foamStability: 4, exposure: 0.8 },
    {}),
  entry('champagne', 'champagne: pale gold, watery, dense fine bead, amber resin numerals', 'handbook; absorption estimated',
    { viscosity: 1.5, density: 992, surfaceTension: 47, ior: 1.35, absorptionR: 0.01, absorptionG: 0.03, absorptionB: 0.12, scattering: 0, contactAngle: 20, contactHysteresis: 10, solidsFraction: 0, dryingTime: 1, gasMode: 1, gasLevel: 0.8, bubbleRadius: 0.04, foamStability: 4, exposure: 1.3 },
    { handbook: true }),
  entry('cuvee', 'straw-gold sparkling wine on an ivory backing: fine pale bead, bronze numerals', 'handbook; absorption estimated',
    { viscosity: 1.5, density: 992, surfaceTension: 47, ior: 1.35, absorptionR: 0.015, absorptionG: 0.04, absorptionB: 0.18, scattering: 0, contactAngle: 20, contactHysteresis: 10, solidsFraction: 0, dryingTime: 1, gasMode: 1, gasLevel: 0.6, bubbleRadius: 0.05, foamStability: 2 },
    // design adjusted: legacy tickBright 1.5: rejection 11, trim range [0.8, 1.3]
    { handbook: true, extra: { tickBright: 1.3 } }),
  entry('ink', 'India ink: matte black pigment, coats the glass, enamel numerals, panel mostly off', 'estimated',
    { viscosity: 4, density: 1050, surfaceTension: 50, ior: 1.4, absorptionR: 30, absorptionG: 30, absorptionB: 30, scattering: 0.5, contactAngle: 30, contactHysteresis: 15, solidsFraction: 0.5, dryingTime: 1.2, gasMode: 0 },
    {}),
  entry('nocturne', 'blue-black ink behind smoked glass: silver front markings, lingering wet residue', 'estimated',
    { viscosity: 5, density: 1050, surfaceTension: 50, ior: 1.4, absorptionR: 30, absorptionG: 20, absorptionB: 8, scattering: 0.5, contactAngle: 30, contactHysteresis: 15, solidsFraction: 0.4, dryingTime: 1.8, gasMode: 0 },
    {}),
  entry('glow', 'glow-stick dye: self-lit fluorescent green, glows past the cap, seven-segment print', 'artistic emission; fluid estimated',
    { viscosity: 5, density: 1050, surfaceTension: 35, ior: 1.42, absorptionR: 0.5, absorptionG: 0.05, absorptionB: 0.8, scattering: 0, emissionR: 0.12, emissionG: 0.45, emissionB: 0.05, contactAngle: 25, contactHysteresis: 12, solidsFraction: 0.05, dryingTime: 1, gasMode: 0 },
    {}),
  entry('xenon', 'xenon discharge: violet self-lit plasma column, no slug, glowing ends', 'density handbook (xenon gas at STP); emission artistic',
    { viscosity: 1, density: 5.9, surfaceTension: 72, ior: 1, phase: 1, absorptionR: 0, absorptionG: 0, absorptionB: 0, scattering: 0, emissionR: 0.35, emissionG: 0.2, emissionB: 0.9, contactAngle: 100, contactHysteresis: 0, solidsFraction: 0, gasMode: 0 },
    // freeLiquid false: the legacy xenon design (a plasma cannot slide, rejection 3)
    { over: { density: 'measured' }, extra: { freeLiquid: false } }),
  entry('molten', 'molten iron: emissive orange liquid metal, dense, non-wetting, forged numerals', 'handbook (1600 °C); emission artistic',
    { viscosity: 6, density: 7000, surfaceTension: 1800, ior: 1, metallic: 1, metalReflectance: 0.3, emissionR: 0.9, emissionG: 0.3, emissionB: 0.03, contactAngle: 120, contactHysteresis: 10, solidsFraction: 0, gasMode: 3, gasLevel: 0.05, bubbleRadius: 0.1, foamStability: 15 },
    { handbook: true, over: { ior: 'estimated' } }),
  entry('urine', 'urine sample: clear amber, watery, specimen-cup graduations', 'handbook; absorption estimated',
    { viscosity: 1, density: 1015, surfaceTension: 66, ior: 1.34, absorptionR: 0.02, absorptionG: 0.08, absorptionB: 0.4, scattering: 0, contactAngle: 20, contactHysteresis: 10, solidsFraction: 0, dryingTime: 1, gasMode: 0, exposure: 1.3 },
    { handbook: true }),
  entry('malt', 'single malt, 40 % ABV: amber, legs on the wall, brass numerals', 'handbook (40 % ethanol); absorption estimated',
    { viscosity: 2.9, density: 940, surfaceTension: 30, ior: 1.36, absorptionR: 0.03, absorptionG: 0.1, absorptionB: 0.35, scattering: 0, contactAngle: 15, contactHysteresis: 10, solidsFraction: 0.05, dryingTime: 0.6, gasMode: 0, exposure: 1.3 },
    { handbook: true }),
  entry('cryo', 'liquid oxygen: nearly colourless, very thin, boiling, frosted wall', 'handbook (90 K)',
    { viscosity: 0.19, density: 1141, surfaceTension: 13, ior: 1.22, absorptionR: 0.005, absorptionG: 0.002, absorptionB: 0, scattering: 0, contactAngle: 5, contactHysteresis: 3, solidsFraction: 0, dryingTime: 1, gasMode: 2, gasLevel: 0.7, bubbleRadius: 0.05, foamStability: 0 },
    { handbook: true }),
  entry('pinot', 'pinot noir on parchment: ruby red wine, legs on the glass, bronze cellar numerals', 'handbook (12 % ethanol); absorption estimated',
    { viscosity: 1.5, density: 990, surfaceTension: 46, ior: 1.35, absorptionR: 0.15, absorptionG: 0.65, absorptionB: 0.5, scattering: 0, contactAngle: 20, contactHysteresis: 10, solidsFraction: 0.03, dryingTime: 1.5, gasMode: 0 },
    // design adjusted: legacy tickBright 2 / digitBright 2 (rejection 11)
    { handbook: true, extra: { tickBright: 1.3, digitBright: 1.8 } }),
  entry('spritz', 'Aperol spritz on white: vivid orange aperitivo, lively bead, navy enamel numerals', 'estimated',
    { viscosity: 1.3, density: 1000, surfaceTension: 50, ior: 1.35, absorptionR: 0.01, absorptionG: 0.22, absorptionB: 0.3, scattering: 0, contactAngle: 20, contactHysteresis: 10, solidsFraction: 0, dryingTime: 1, gasMode: 1, gasLevel: 0.6, bubbleRadius: 0.08, foamStability: 2.5 },
    // design adjusted: legacy tickBright 2 / digitBright 2 (rejection 11)
    { extra: { tickBright: 1.3, digitBright: 1.8 } }),
  entry('tide', 'bioluminescent sea water: self-lit cyan glow, drifting sparks, steel marks behind black glass', 'sea water handbook; emission artistic',
    { viscosity: 1, density: 1025, surfaceTension: 73, ior: 1.34, absorptionR: 0.5, absorptionG: 0.2, absorptionB: 0.15, scattering: 0, emissionR: 0, emissionG: 0.06, emissionB: 0.08, contactAngle: 20, contactHysteresis: 10, solidsFraction: 0, dryingTime: 1, gasMode: 1, gasLevel: 0.3, bubbleRadius: 0.03, foamStability: 0 },
    { handbook: true }),
  entry('phosphor', 'phosphor solution on white paper: pale green in a clear lab vial, marker labels on the glass', 'estimated',
    { viscosity: 1, density: 1000, surfaceTension: 70, ior: 1.34, absorptionR: 0.3, absorptionG: 0.05, absorptionB: 0.25, scattering: 0, contactAngle: 20, contactHysteresis: 10, solidsFraction: 0, dryingTime: 1, gasMode: 0 },
    {}),
];

/** presets/materials/<id>.json: the entry's material file (serializeMaterialEnvelope, canonical order). */
export function materialPresetFile(e: MaterialPreset): string {
  return serializeMaterialEnvelope({ name: e.name, material: e.material, design: e.design, provenance: e.provenance });
}

/** presets/physical/<id>.json: the derived legacy Params in the presets/<id>.json format (DEFAULT_PARAMS
 *  key order, 2-space JSON), the input of firmware/tools/gen_params.py. Throws on a rejected entry. */
export function physicalPresetFile(e: MaterialPreset): string {
  return JSON.stringify({ ...structuredClone(DEFAULT_PARAMS), ...derive(e.material, e.design) }, null, 2) + '\n';
}
