// All tunables live here. Colours are RGB888 hex strings but are quantised to RGB565 at render time.
import { legacyTraceDrain } from './physics';
import { PX_SCALE } from '../../spec/layout';
// Export/import as JSON from the control panel; the exported file is the contract for Phase 3 (spec/params.h).

export interface Params {
  v: number;             // params schema version (not shown in the UI); bumped when a key changes meaning
  // --- colours (hex "#rrggbb"); quantised to RGB565 before drawing ---
  liquid: string;        // body colour
  liquidHi: string;      // specular highlight strip
  liquidLo: string;      // bottom shade (cylinder shading)
  tubeBack: string;      // colour behind the liquid and glass layers (very dark; 0 = AMOLED off)
  tubeBack2: string;     // second colour used by the tube-back gradient
  tubeBackGradient: number; // 0 solid, 1 top-to-bottom, 2 centre band, 3 edge bands
  // --- glass tube shading (empty part; specular also over the liquid) ---
  glassHi: string;       // specular colour of the glass wall
  glassBody: number;     // 0..1 ambient cylinder shade of the empty wall (0 = pure black, AMOLED off)
  glassHiBright: number; // 0..1 strength of the specular band (same rows as the liquid highlight)
  glassReflect: number;  // 0..1 faint second reflection on the lower wall
  glassRim: number;      // 0..1 grazing reflection across the wall band, brightest at the silhouette
  glassWall: number;     // px wall thickness at the top/bottom silhouette: dry rows behind it show no tube back (only the grazing reflection), rear marks fade out there
  glassWallGlow: number; // 0..1 the dry wall band lit by light piped along the glass (visible on a black tube back; over the liquid the band shows the liquid); plateau across the band under the grazing rim
  wallWet: number;       // 0..1 how far the contents fill the wall band and frustrate the glow piped along it: 1 a liquid (seen to the silhouette, no glow over it), 0 a gas (the band over the column is the empty tube's)
  rimLight: number;      // 0..4 gain: side-lit rim of a tinted liquid on a dark ground: adds rimLight·u²·rimTint to the liquid rows toward the walls
  rimTint: string;       // colour of that rim light (8-bit, scaled by brightness)
  glassOverLiquid: number; // 0..1 how much of the glass specular is laid over the liquid too
  lens: number;          // -1..1 vertical distortion; negative compresses, positive magnifies
  lensCurve: number;     // -3..3 profile; negative reverses the distortion direction
  bubbleRim: string;
  // --- layout (px) ---
  tubeHeight: number;    // across-tube size, ≤ TUBE_HEIGHT_MAX
  hoursY: number;        // top row of the hours tube
  minutesY: number;      // top row of the minutes tube
  // --- shape ---
  remaining: boolean;    // true = liquid at the right end, draining as time passes; false = fills from the left
  vertical: boolean;     // watch worn upright, USB end down: liquid always at the bottom (left end), digits rotated to read upright; `remaining` then only flips the scale (1 at the top, the liquid shows what is left)
  highlightH: number;    // px, height of highlight strip at top of column
  highlightInset: number;
  highlightBright: number; // 0..1.5 strength of the specular band
  highlightSharp: number;  // 0.3..4 band profile exponent (high = narrow, glossy)
  shadeDepth: number;    // 0..1, how dark the bottom rows get (cylinder shading)
  liquidThin: number;    // 0..1 the liquid lightens and desaturates toward the walls (short path through the column)
  contactAngle: number;  // deg, static contact angle on the glass: < 90 wetting (concave), > 90 non-wetting (convex bead)
  contactHyst: number;   // deg, hysteresis half-band: a line advances at θ + this, recedes at θ − this; tilt pressure moves θ within it
  contactDyn: number;    // deg, Cox–Voinov speed term: the angle a zero-angle line reaches advancing at 25 px/s (viscosity / surface tension)
  capLength: number;     // mm, capillary length √(γ/ρg): with the ~2–3 mm bore it sets the across-tilt sag and the tilt pressure
  meniscusLens: number;  // -1..1 pre-warp of the cap profile against the physical glass (like topLens); negative compensates magnification
  meniscusK: number;     // 1/s^2 spring of the free surface between the pinned contact lines
  meniscusDamp: number;  // 1/s damping of that spring (low = visible wobble after a flick)
  meniscusInertia: number; // 0..10 how much edge forcing (flick kick, slug acceleration) bulges the surface centre ahead of the contact lines
  wetFilm: number;       // px trailing wet film a receding edge leaves on the glass
  traces: boolean;       // a receding edge leaves a residue on the glass (blood smear, syrup coating, legs)
  traceAmount: number;   // 0..2 residue depth gain: the stain's Beer–Lambert depth relative to its film (clamped at the bulk chord)
  traceDry: number;      // s, drying time constant of the residue: the wet film evaporates, its stain fades
  traceDrain: number;    // px/s a wet film at the thin-film cap (h = R/10) runs down under 1 g, ρgh²/3μ (thinner films ∝ h²; 0 = stays put)
  traceStain: number;    // 0..1 share of a drying film left on the glass as stain (0 = it evaporates without a trace)
  traceFilm: number;     // 0..1 permanent thin film over the whole glass, as a residue level (0 = bare glass between smears)
  edgeSoft: number;      // px, anti-aliased edge width (0 = hard pixel edge)
  frontBright: number;   // px, band just behind the fill edge blended toward liquidHi (bright convex cap look)
  surfaceBand: number;   // 0..1 visible meniscus surface: shaded concave band or thin convex nose
  surfaceRim: number;    // 0..1 lit 1-px line on the outer edge of the concave surface stroke
  surfaceWidth: number;  // px thickness of the concave surface stroke (a bright band following the edge profile; never past the wall contact ring)
  surfaceTone: number;   // -1..1 surface colour shift: darker (toward the deep liquid colour) .. lighter (toward the highlight); both the concave stroke and the convex nose
  surfaceFill: number;   // 0..1 opacity of the concave surface's shaded interior; the rim and the blick stay — at 0 only they define the surface (see-through dish)
  surfaceBlick: number;  // 0..1 specular patch on the concave surface at the highlight rows (a reflection of the room light in the dish)
  edgeGlow: number;      // px, dim glow fading out past the fill edge (0 = off)
  glowStrength: number;  // 0..1 brightness of the glow at the edge
  cornerR: number;       // px, rounding of the column's left end (tube end cap)
  edgeLightGain: number; // 0..1, how much along-tilt brightens (+) / dims (-) the fill-edge light
  // --- bubble ---
  bubble: boolean;
  bubbleW: number;       // px
  bubbleH: number;       // px
  bubbleGap: number;     // px, distance from fill edge to bubble centre
  bubbleY: number;       // 0..1 vertical position in the tube (0.5 = centre, like a spirit level)
  bubbleDark: number;    // 0..1, fizz: opacity of the dark tint over the see-through interior; spirit bubble: darkening of its fill
  bubbleRollGain: number; // 0..2 bubble rise toward the high wall per g of across-tilt (1 = follows the wall)
  bubbleTiltGain: number; // px the bubble slides toward the high end per g of along-tilt
  // --- fizz (small drifting bubbles, like the reference photo) ---
  fizz: boolean;
  fizzCount: number;
  fizzSize: number;      // px (1..16)
  fizzSizeVar: number;   // 0..1, per-bubble size spread (bigger ones rise faster)
  fizzShadeOff: number;  // 0..1, dark core offset away from the light, fraction of radius
  fizzSpeed: number;
  fizzDriftGain: number; // 0..2 steering: fraction of rise speed that goes toward the high end per g of along-tilt
  fizzAcrossGain: number; // 0..2, across-tilt → on-screen rise direction (1 = rises toward the physically high edge)
  fizzFlatRise: number;   // 0..1, on-screen rise speed when the face points up (bubbles rise toward the viewer)
  fizzSquash: number;     // 0.5..2, extra vertical pre-squash on fizz discs at mid-height, fading to 1 at the edges
  fizzEdgeRise: number;   // 0..1, face-up rise toward the fill edge (the surface) as a fraction of fizzSpeed, so bubbles reach it at rest
  fizzFoamLife: number;   // s, mean time a bubble sits parked under the surface before it pops (0 = never parks, the old respawn)
  fizzDepth: number;      // 0..1 how much a bubble deeper in the bore fades toward the liquid (scaled by 1 − liquidTransparency)
  fizzBlick: number;      // 0..1 specular pinpoint on bubbles ≥ 2.5 px radius, on the lit side
  fizzSource: number;     // 0 scattered (born anywhere in the liquid), 1 spring (born at one point, like an aquarium airstone)
  fizzSourceX: number;    // 0..1 spring position along the liquid column (0 = home end, 1 = surface)
  fizzSourceY: number;    // 0..1 spring position across the bore (0 = top wall, 1 = bottom wall)
  fizzSourceSpread: number; // px, ± jitter around the spring point on both axes
  fizzSourceRate: number;  // bubbles/s the spring releases (its pool follows, up to the tube's fizzCount share)
  // --- ticks, hours tube (units = hours) ---
  ticksH: boolean;
  tickStepH: number;       // minor tick every N hours
  tickMajorEveryH: number; // major tick every N hours (0 = none) — in units, not "every N-th minor"
  tickMinorHeightH: number;// px
  tickMajorHeightH: number;// px
  tickMinorWidthH: number; // px
  tickMajorWidthH: number; // px
  tickColorH: string;      // minor
  tickMajorColorH: string;
  tickPosH: number;        // 0 top, 1 bottom, 2 both
  // --- ticks, minutes tube (units = minutes) ---
  ticksM: boolean;
  tickStepM: number;
  tickMajorEveryM: number; // major tick every N minutes (0 = none)
  tickMinorHeightM: number;
  tickMajorHeightM: number;
  tickMinorWidthM: number;
  tickMajorWidthM: number;
  tickColorM: string;
  tickMajorColorM: string;
  tickPosM: number;
  ticksOnTop: boolean;   // false rear/bottom surface, true curved front/top surface
  tickLens: number;      // 0..1 cylinder depth warp before the whole-tube lens
  tickParallax: number;  // px rear-surface shift per g of tilt
  tickDryLens: number;   // -1..1 cylinder warp for rear ticks behind air (no liquid); negative stretches the edges
  tickEmboss: number;    // 0..1 glass-cut edge strength
  // --- digits along the bottom of the tube (3x5 pixel font) ---
  digits: boolean;
  digitColor: string;    // top of glyph
  digitColor2: string;   // bottom of glyph (vertical gradient → metallic look; set equal for flat)
  digitShadow: boolean;  // 1 px darker copy offset down-right (emboss); bitmap and sprite fonts
  digitShadowColor: string;
  digitShadowStrength: number; // 0..1 shadow opacity
  digitShadowOffset: number;   // px, down-right
  digitTint: string;     // sprite fonts only: multiply colour (e.g. #cd7f32 bronze)
  digitTintAmount: number; // 0 = untinted sheet, 1 = fully tinted
  digitTone: number;     // sprite fonts only: -1 = black, 0 = source, 1 = white
  digitFont: number;     // 0..4 bitmap, 5..11 image sprites
  digitScaleX: number;   // hours tube: horizontal scale (0.5..6, fractional OK — nearest-neighbour)
  digitScaleY: number;   // hours tube: vertical scale — keep lower than X to counter the vial's vertical stretch
  digitScaleXMin: number; // minutes tube
  digitScaleYMin: number;
  digitBottomMin: number; // minutes tube baseline (px from bottom edge)
  digitBottom: number;   // hours tube: px from the tube's bottom edge to the digit baseline
  digitsOnTop: boolean;  // true = printed on the glass (fully opaque over the liquid); false = behind the liquid, seen through it by liquidTransparency
  bottomLens: number;    // 0..1 depth warp for digits printed behind the liquid
  digitDryLens: number;  // -1..1 depth warp for rear digits behind air; negative stretches the edges
  topLens: number;       // -1..1 pre-distortion for digits printed on top; negative compensates physical glass magnification
  topParallax: number;   // px across-shift of top digits per g of across-tilt; counters the apparent shift under the physical lens
  digitParallax: number; // px shift of rear digits behind the liquid per g of tilt (along → along the tube, across → across it); behind air none
  liquidTransparency: number; // 0..1 how much of ticks/digits shows through the liquid (0 = opaque liquid)
  markContrast: number;  // min luma difference a tick/digit must keep from the liquid behind it (0 = off)
  digitsLeadingZero: boolean; // minutes as 05,10,... instead of 5,10,...
  digitMinuteStep: number; // label every N minutes (5,10,15,20,30)
  digitHourStep: number;   // label every N hours (1..6)
  digitHourStart: number;  // first labelled hour (0 = step); step 2 + start 1 = odd hours
  digitMinuteStart: number; // first labelled minute (0 = step)
  digitsLastOnlyH: boolean; // hours: one label only, the last passed hour (none before 1)
  digitsLastOnlyM: boolean; // minutes: one label only, last passed multiple of digitMinuteStep
  // --- tilt-controlled liquid: gentle tilt reads time, strong tilt releases the slug ---
  freeLiquid: boolean;   // true = automatic tilt response; false = always pinned
  freeGain: number;      // px/s^2 per g of along-tilt
  freeDamp: number;      // 1/s viscous drag
  freeBounce: number;    // 0..1 restitution at the tube ends
  freeHomeK: number;     // 1/s^2 pull toward the home end while reading (critically damped)
  readTiltStart: number; // degrees from horizontal: time held below this angle
  readTiltEnd: number;   // degrees from horizontal: fully free above this angle
  playHold: number;      // seconds to stay free after deliberate back-and-forth tilting; 0 disables
  // --- physics (fixed-step 50 Hz) ---
  fillK: number;         // spring stiffness of fill-edge position (1/s^2)
  fillDamp: number;      // damping ratio-ish (1/s)
  fillSloshGain: number; // px per g of along-tube acceleration
  angleK: number;        // spring stiffness of surface angle
  angleDamp: number;
  angleTiltGain: number; // deg of in-plane front skew per g of across-tube tilt (static response)
  angleGyroGain: number; // fill-edge kick per dps of rotation about the across axis (flicks)
  angleMax: number;      // deg clamp
  lightPhys: number;     // 0..1: 0 = fixed style light at lightAngle, 1 = world-up light from the IMU (highlight row, cylinder shading)
  lightAngle: number;    // deg, style highlight angle: 0 = centre row, 90 = top wall
  acrossK: number;       // spring stiffness of the light (roll) swing
  acrossDamp: number;
  acrossGyroGain: number; // deg impulse per dps of roll rate (gyro about the tube axis)
  shakeGain: number;     // 0..2 agitation sensitivity to gyro energy (fizz speed, edge glow)
  deadzone: number;      // g, ignore tiny accelerations
  // --- IMU conditioning (applied to board / phone input before the springs; ported to firmware) ---
  accelLpHz: number;     // low-pass cutoff for accel (gravity direction), Hz
  gyroHpHz: number;      // high-pass cutoff for gyro: removes bias and slow rotations, keeps flicks
  gyroDeadzone: number;  // dps, ignore gyro below this after filtering
  gyroMax: number;       // dps, clamp
  inputGain: number;     // overall multiplier on tilt input (0.1..2)
  // --- display ---
  // brightness is the panel-wide dimmer; the three below are per-layer trims on top of it, so the
  // liquid can glow while the printed scale sits back in the shadow at the bottom wall of the tube.
  brightness: number;    // 0..1 global multiplier (emulates cmd 0x51)
  liquidBright: number;  // liquid only: body / highlight / shade, and the bubble + fizz derived from them
  tickBright: number;    // tick ladder only
  digitBright: number;   // numeric labels only (glyph gradient, emboss shadow and image sheets)
  ambientLight: number;  // 0..1: liquid colours brighter than the diffuse body desaturate toward neutral — reflections of white room light instead of the liquid glowing in its own colour
}

export const PARAMS_VERSION = 27;

export const DEFAULT_PARAMS: Params = {
  v: PARAMS_VERSION,
  tubeHeight: 72,
  hoursY: 0,
  minutesY: 168,
  remaining: false,
  vertical: false,
  liquid: '#346a2a',
  liquidHi: '#b6ffa0',
  liquidLo: '#1e7515',
  tubeBack: '#090d10',
  tubeBack2: '#253039',
  tubeBackGradient: 2,
  glassHi: '#a8c0c8',
  glassBody: 0.1,
  glassHiBright: 0.55,
  glassReflect: 0.22,
  glassRim: 0.4,
  glassWall: 4,
  glassWallGlow: 0.25,
  wallWet: 1,
  rimLight: 0,
  rimTint: '#000000',
  glassOverLiquid: 0.4,
  lens: 0.6,
  lensCurve: 1,
  bubbleRim: '#b0c7a9',
  highlightH: 11,
  highlightBright: 1,
  highlightSharp: 1,
  highlightInset: 0,
  shadeDepth: 0.49,
  liquidThin: 0.4,
  contactAngle: 25,
  contactHyst: 10,
  contactDyn: 8,
  capLength: 2.7,
  meniscusLens: 0,
  meniscusK: 180,
  meniscusDamp: 9,
  meniscusInertia: 6,
  wetFilm: 6,
  traces: false,
  traceAmount: 0.6,
  traceDry: 1,
  traceDrain: 2376.8,   // legacyTraceDrain of these defaults (water: contactDyn 8°, capLength 2.7 mm, this bore)
  traceStain: 0.3,
  traceFilm: 0,
  edgeSoft: 2.6,
  frontBright: 21,
  surfaceBand: 0.5,
  surfaceRim: 0.6,
  surfaceWidth: 4,
  surfaceTone: 0,
  surfaceFill: 1,
  surfaceBlick: 0,
  edgeGlow: 15,
  glowStrength: 0.25,
  cornerR: 0,
  edgeLightGain: 1,
  bubble: false,
  bubbleW: 16,
  bubbleH: 19,
  bubbleGap: 22,
  bubbleY: 0.2,
  bubbleRollGain: 0.5,
  bubbleTiltGain: 0,
  bubbleDark: 1,
  fizz: true,
  fizzCount: 10,
  fizzSize: 2,
  fizzSizeVar: 0.5,
  fizzShadeOff: 0.3,
  fizzDriftGain: 1,
  fizzAcrossGain: 1,
  fizzFlatRise: 0.3,
  fizzSquash: 1,
  fizzEdgeRise: 0.3,
  fizzFoamLife: 6,
  fizzDepth: 0.7,
  fizzBlick: 0.6,
  fizzSource: 0,
  fizzSourceX: 0.2,
  fizzSourceY: 1,
  fizzSourceSpread: 1.5,
  fizzSourceRate: 5,
  fizzSpeed: 14,
  ticksH: true, tickStepH: 1, tickMajorEveryH: 3, tickMinorHeightH: 27, tickMajorHeightH: 13, tickMinorWidthH: 1, tickMajorWidthH: 2, tickColorH: '#303030', tickMajorColorH: '#303030', tickPosH: 2,
  ticksM: true, tickStepM: 5, tickMajorEveryM: 3, tickMinorHeightM: 27, tickMajorHeightM: 16, tickMinorWidthM: 1, tickMajorWidthM: 2, tickColorM: '#303030', tickMajorColorM: '#303030', tickPosM: 2,
  ticksOnTop: false,
  tickLens: 0.35,
  tickParallax: 3,
  tickDryLens: -0.4,
  tickEmboss: 0.25,
  digits: true,
  digitColor: '#e3e3e3',
  digitColor2: '#20312f',
  digitShadow: true,
  digitShadowColor: '#101010',
  digitShadowStrength: 1,
  digitShadowOffset: 1,
  digitFont: 5,
  digitTint: '#6d6617',
  digitTintAmount: 0.65,
  digitTone: 0,
  digitScaleX: 6,
  digitScaleY: 5,
  digitScaleXMin: 3.75,
  digitScaleYMin: 4.5,
  digitBottomMin: 19,
  digitBottom: 16,
  digitsOnTop: false,
  bottomLens: 0.35,
  digitDryLens: -0.4,
  topLens: 0,
  topParallax: 0,
  digitParallax: 3,
  liquidTransparency: 0.17,
  markContrast: 0,
  digitsLeadingZero: false,
  digitMinuteStep: 15,
  digitHourStep: 3,
  digitHourStart: 0,
  digitMinuteStart: 0,
  digitsLastOnlyH: false,
  digitsLastOnlyM: false,
  freeLiquid: true,
  freeGain: 500,
  freeDamp: 1.5,
  freeBounce: 0.25,
  freeHomeK: 30,
  readTiltStart: 20,
  readTiltEnd: 50,
  playHold: 5,
  fillK: 246,
  fillDamp: 14.8,
  fillSloshGain: 5.5,
  angleK: 207,
  angleDamp: 17.6,
  angleTiltGain: 5.5,
  angleGyroGain: 0.37,
  angleMax: 6,
  lightPhys: 0,
  lightAngle: 53,
  acrossK: 200,
  acrossDamp: 20,
  acrossGyroGain: 0,
  shakeGain: 0,
  deadzone: 0,
  accelLpHz: 15.2,
  gyroHpHz: 5,
  gyroDeadzone: 31,
  gyroMax: 470,
  inputGain: 1,
  brightness: 0.92,
  liquidBright: 1.29,
  tickBright: 1.2,
  digitBright: 0.82,
  ambientLight: 0,
};

/** Explicitly keep non-material presets plain when DEFAULT_PARAMS uses a textured backing. */
const PLAIN_TUBE_BACK: Partial<Params> = {
  tubeBack2: '#18212a', tubeBackGradient: 0,
};

// ---------------------------------------------------------------------------
// Signature presets. Each one is a real liquid in a real vessel: optics, glass,
// scale, labels and the physics of that liquid's viscosity, wetting and density.
// The `mat` descriptor on each PRESETS entry is the contract the numbers must
// satisfy — see presets/PRESETS.md and tools/check-presets.ts.
// Applied over DEFAULT_PARAMS (see presetParams), so they are reproducible.
// ---------------------------------------------------------------------------

/** What the preset claims to be; check-presets.ts derives the allowed ranges from it. */
export interface Material {
  viscosity: 'watery' | 'medium' | 'viscous' | 'metal' | 'plasma';
  opacity: 'opaque' | 'translucent' | 'clear';
  emissive: boolean;
  wetting: boolean;   // concave meniscus + wet film vs convex bead
  gas: 'none' | 'carbonated' | 'boiling' | 'trapped';
}

/** The modern base every liquid preset is built on (from examples/nice_meniscus.json, 2026-08-27):
 *  thin tubes spread to the panel edges, lens −0.5 + topLens 0.35 for the physical rod, physical light
 *  with a broad soft highlight, rear sprite digits every hour / 5 min, dark rear ticks on both edges,
 *  a hysteretic wetting meniscus (contact lag, film, hard edge, faint caustic) and the free slug.
 *  Rear ticks and rear digits share one wall, so presets keep tickLens = bottomLens and tickDryLens = digitDryLens,
 *  and ticks at digit positions stop a couple of source rows short of the digit. */
export const MODERN_BASE: Partial<Params> = {
  tubeHeight: 46, hoursY: 12, minutesY: 185,
  tubeBack: '#000000', tubeBack2: '#000000', tubeBackGradient: 1,
  glassHi: '#859093', glassBody: 0.04, glassHiBright: 0.34, glassReflect: 0.2, glassRim: 0.52, glassOverLiquid: 0.4,
  lens: -0.5, lensCurve: -0.05,
  highlightH: 17, highlightBright: 0.35, highlightSharp: 2, highlightInset: 0, shadeDepth: 0.68,
  meniscusLens: 0,
  meniscusK: 475, meniscusDamp: 15.5, meniscusInertia: 2.1, wetFilm: 15,
  edgeSoft: 0, frontBright: 0, edgeGlow: 19, glowStrength: 0.06, cornerR: 0, edgeLightGain: 0.55,
  bubble: false, bubbleW: 27, bubbleH: 20, bubbleGap: 28, bubbleY: 0.28, bubbleTiltGain: 14, bubbleDark: 0.91,
  ticksOnTop: false, tickLens: 0.45, tickParallax: 4.75, tickDryLens: 0.1, tickEmboss: 0.3,
  ticksH: true, tickStepH: 1, tickMajorEveryH: 0, tickMinorHeightH: 6, tickMajorHeightH: 22, tickMinorWidthH: 2, tickMajorWidthH: 3,
  tickColorH: '#404040', tickMajorColorH: '#4d4d4d', tickPosH: 2,
  ticksM: true, tickStepM: 5, tickMajorEveryM: 0, tickMinorHeightM: 10, tickMajorHeightM: 28, tickMinorWidthM: 2, tickMajorWidthM: 2,
  tickColorM: '#383838', tickMajorColorM: '#4d4d4d', tickPosM: 2,
  digits: true, digitFont: 7, digitsOnTop: false, digitShadow: true, digitColor: '#e3e3e3', digitColor2: '#20312f', digitShadowColor: '#101010',
  digitTint: '#827c40', digitTintAmount: 0.9, digitTone: -0.4,
  digitScaleX: 3.5, digitScaleY: 3.25, digitBottom: 15, digitHourStep: 1, digitHourStart: 0, digitsLastOnlyH: false,
  digitScaleXMin: 2.5, digitScaleYMin: 2.75, digitBottomMin: 13, digitMinuteStep: 5, digitMinuteStart: 0, digitsLeadingZero: false, digitsLastOnlyM: false,
  bottomLens: 0.45, digitDryLens: 0.1, topLens: 0.35, topParallax: -10, digitParallax: 4.75,
  liquidTransparency: 0.52, markContrast: 0,
  freeLiquid: true, freeGain: 570, freeDamp: 0.8, freeBounce: 0.15, freeHomeK: 150,
  fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207, angleDamp: 17.6, angleTiltGain: 5.5, angleGyroGain: 0.37, angleMax: 6,
  lightPhys: 1, lightAngle: 73,
  brightness: 1, liquidBright: 2, tickBright: 1.2, digitBright: 1.75,
};

/** Wider tubes pushed to the panel edges (examples/frizzante_slightly_fixed.json). */
const LAYOUT_WIDE: Partial<Params> = { tubeHeight: 55, hoursY: 7, minutesY: 224 };

/** Print on the front of the glass: no cylinder lens, no parallax, opaque over the liquid. Used for opaque
 *  liquids (nothing shows through) and lab glassware. Light tick colours so the ladder reads on the dry side. */
const FRONT_PRINT: Partial<Params> = {
  ticksOnTop: true, tickEmboss: 0, tickLens: 0, tickParallax: 0,
  tickMinorWidthH: 1, tickMajorWidthH: 2, tickMinorWidthM: 1, tickMajorWidthM: 2,
  tickMinorHeightH: 7, tickMajorHeightH: 14, tickMinorHeightM: 6, tickMajorHeightM: 12,
  tickMajorEveryH: 3, tickMajorEveryM: 15,
  tickColorH: '#9aa4ac', tickMajorColorH: '#e8eef2', tickColorM: '#9aa4ac', tickMajorColorM: '#e8eef2',
  tickPosH: 0, tickPosM: 0,
  digitsOnTop: true, digitShadow: false,
};

// Viscosity classes on top of the base (checker ranges in tools/check-presets.ts).
const WATERY: Partial<Params> = { contactAngle: 20, contactHyst: 10, contactDyn: 8, capLength: 2.7, freeDamp: 0.8, freeBounce: 0.2, meniscusK: 475, meniscusDamp: 8, meniscusInertia: 3, wetFilm: 10, angleTiltGain: 6.5, angleGyroGain: 0.42 };
const MEDIUM: Partial<Params> = { contactAngle: 30, contactHyst: 15, contactDyn: 15, capLength: 2.3, freeDamp: 2.5, freeBounce: 0.1, meniscusK: 280, meniscusDamp: 16, meniscusInertia: 2, wetFilm: 15, angleTiltGain: 4, angleGyroGain: 0.25 };
const VISCOUS: Partial<Params> = { contactAngle: 25, contactHyst: 20, contactDyn: 90, capLength: 1.9, freeDamp: 9, freeBounce: 0, meniscusK: 90, meniscusDamp: 34, meniscusInertia: 1, wetFilm: 26, angleTiltGain: 1.5, angleGyroGain: 0.06 };
const METAL: Partial<Params> = { contactAngle: 140, contactHyst: 15, contactDyn: 3, capLength: 1.9, freeDamp: 1, freeBounce: 0.55, meniscusK: 650, meniscusDamp: 12, meniscusInertia: 4, wetFilm: 0, angleTiltGain: 2, angleGyroGain: 0.4 };

/** Sparkling mineral water in a lab cylinder: the water itself is colourless — what you see is the
 *  back through it, a white surface reflection, the meniscus and a constant fine bead. */
export const PRESET_FRIZZANTE: Partial<Params> = {
  ...MODERN_BASE, ...LAYOUT_WIDE, ...FRONT_PRINT, ...WATERY,
  liquid: '#5d6c72', liquidHi: '#f4ffff', liquidLo: '#2b3438', tubeBack: '#0a0e10', tubeBack2: '#1c2529', tubeBackGradient: 2,
  bubbleRim: '#f4ffff',
  glassHi: '#dfeef4', glassBody: 0.12, glassHiBright: 0.55, glassReflect: 0.28, glassRim: 0.75, glassOverLiquid: 0.7,
  highlightH: 8, highlightBright: 0.9, highlightSharp: 3, shadeDepth: 0.45,
  liquidTransparency: 0.85, markContrast: 20,
  tickStepM: 1, tickMajorEveryM: 5, tickColorH: '#9fb8c2', tickMajorColorH: '#ffffff', tickColorM: '#8fa9b4', tickMajorColorM: '#ffffff',
  digitFont: 9, digitTintAmount: 0, digitTone: 0,
  digitScaleX: 3.25, digitScaleY: 3.25, digitBottom: 5, digitHourStep: 3,
  digitScaleXMin: 2.25, digitScaleYMin: 2.25, digitBottomMin: 16, digitMinuteStep: 15,
  liquidBright: 1.3, tickBright: 1.1, digitBright: 1.1,
};

/** Alpine spring water: a cool, nearly colourless bead against pale ceramic, with
 *  a restrained capillary surface and fine carbonation. Rear slate markings stay
 *  legible through the clear liquid and its dry glass. */
export const PRESET_ALPINE: Partial<Params> = {
  ...MODERN_BASE, ...WATERY,
  tubeHeight: 54, hoursY: 0, minutesY: 185, remaining: true,
  liquid: '#548b9d', liquidHi: '#f5ffff', liquidLo: '#295c6d',
  tubeBack: '#f2eee5', tubeBack2: '#f2eee5', tubeBackGradient: 0,
  glassHi: '#aabcc0', glassBody: 0.04, glassHiBright: 0.22,
  glassReflect: 0.3, glassRim: 0.58, glassWall: 4.5,
  glassWallGlow: 0.08, glassOverLiquid: 0.65,
  lens: -0.2, lensCurve: 0.2, bubbleRim: '#f5ffff',
  highlightH: 8, highlightBright: 0.68, highlightSharp: 2.6,
  shadeDepth: 0.5, liquidThin: 0.45,
  meniscusInertia: 2.5,
  edgeSoft: 1.4, surfaceBand: 0.38, surfaceRim: 0.35,
  surfaceWidth: 3, surfaceTone: 0, edgeGlow: 8, glowStrength: 0.03,
  tickStepH: 1, tickMajorEveryH: 2, tickMinorHeightH: 5,
  tickMajorHeightH: 7, tickMinorWidthH: 1, tickMajorWidthH: 2,
  tickStepM: 5, tickMajorEveryM: 10, tickMinorHeightM: 5,
  tickMajorHeightM: 8, tickMinorWidthM: 1, tickMajorWidthM: 2,
  tickColorH: '#607477', tickMajorColorH: '#293d43',
  tickColorM: '#607477', tickMajorColorM: '#293d43',
  tickPosH: 2, tickPosM: 2, tickLens: 0.45,
  digitFont: 10, digitTint: '#394d52', digitTintAmount: 0.3,
  digitTone: -0.2, digitShadowStrength: 0.4,
  digitScaleX: 3.3, digitScaleY: 3.1, digitBottom: 10,
  digitScaleXMin: 2.35, digitScaleYMin: 2.35, digitBottomMin: 11,
  digitHourStep: 2, digitMinuteStep: 10,
  liquidTransparency: 0.72, markContrast: 25,
  liquidBright: 0.9, tickBright: 1.05, digitBright: 1.15,
  ambientLight: 0.1,
};

/** Urine in a specimen cup: tinted amber (translucent, not colourless), watery, no bead
 *  (examples/urine_1.json + nice_meniscus.json, minus the bubbles). */
export const PRESET_URINE: Partial<Params> = {
  ...MODERN_BASE, ...WATERY,
  liquid: '#6d6112', liquidHi: '#809419', liquidLo: '#79792a', bubbleRim: '#322606',
  meniscusK: 475, meniscusDamp: 15.5, meniscusInertia: 2.1, wetFilm: 15,
  liquidTransparency: 0.52,
};

/** Venous blood in a graduated syringe: opaque, a few times thicker than water, coats the glass. */
export const PRESET_BLOOD: Partial<Params> = {
  ...MODERN_BASE, ...LAYOUT_WIDE, ...FRONT_PRINT, ...MEDIUM,
  liquid: '#6e0b16', liquidHi: '#c8443f', liquidLo: '#1c0306', tubeBack: '#050203', tubeBack2: '#0a0405', bubbleRim: '#e08a80',
  glassHi: '#93a2ae', glassBody: 0.06, glassHiBright: 0.3, glassReflect: 0.14, glassRim: 0.5, glassOverLiquid: 0.22,
  highlightH: 10, highlightBright: 0.5, highlightSharp: 2, shadeDepth: 0.86,
  traces: true, traceAmount: 1.1, traceDry: 1.5, traceStain: 0.35,   // blood smears the wall, crawls back, dries last
  liquidTransparency: 0.05,
  digitFont: 9, digitTintAmount: 0, digitTone: 0,
  digitScaleX: 3.25, digitScaleY: 3.25, digitBottom: 5, digitHourStep: 3,
  digitScaleXMin: 2.25, digitScaleYMin: 2.25, digitBottomMin: 16, digitMinuteStep: 15, digitsLeadingZero: true,
  liquidBright: 1.4, tickBright: 1, digitBright: 1.1,
};

/** Milk: an opaque scattering colloid — soft wide highlight, gentle shading, a little thicker than water. */
export const PRESET_MILK: Partial<Params> = {
  ...MODERN_BASE, ...LAYOUT_WIDE, ...FRONT_PRINT, ...MEDIUM,
  liquid: '#c9c5ba', liquidHi: '#ffffff', liquidLo: '#7a7568', tubeBack: '#0a0a0a', tubeBack2: '#101010', bubbleRim: '#ffffff',
  glassHi: '#d8dde0', glassBody: 0.08, glassHiBright: 0.4, glassReflect: 0.18, glassRim: 0.5, glassOverLiquid: 0.35,
  highlightH: 16, highlightBright: 0.4, highlightSharp: 0.8, shadeDepth: 0.5,
  liquidTransparency: 0.03,
  tickColorH: '#7aa3bd', tickMajorColorH: '#5b8db0', tickColorM: '#7aa3bd', tickMajorColorM: '#5b8db0',
  digitFont: 10, digitTint: '#4f86ab', digitTintAmount: 0.8, digitTone: -0.1,
  digitScaleX: 3.25, digitScaleY: 3.25, digitBottom: 5, digitHourStep: 3,
  digitScaleXMin: 2.25, digitScaleYMin: 2.25, digitBottomMin: 16, digitMinuteStep: 15,
  liquidBright: 1.2, tickBright: 1.1, digitBright: 1.3,
};

/** Mercury thermometer: opaque non-wetting bead with a mirror specular that follows real gravity;
 *  the scale is etched on the glass because nothing shows through the metal. */
export const PRESET_MERCURY: Partial<Params> = {
  ...MODERN_BASE, ...LAYOUT_WIDE, ...FRONT_PRINT, ...METAL,
  liquid: '#8f9aa2', liquidHi: '#ffffff', liquidLo: '#232b31',
  tubeBack: '#3a444c', tubeBack2: '#6a7880', tubeBackGradient: 2,
  bubbleRim: '#e8f0f5',
  glassHi: '#e2edf5', glassBody: 0.13, glassHiBright: 0.6, glassReflect: 0.35, glassRim: 0.78, glassOverLiquid: 0.5,
  highlightH: 7, highlightBright: 1.3, highlightSharp: 3.6, shadeDepth: 0.95,
  frontBright: 22, edgeGlow: 0, glowStrength: 0, edgeLightGain: 0.7,
  liquidTransparency: 0,
  tickEmboss: 0.35, tickColorH: '#0e1418', tickMajorColorH: '#060a0c', tickColorM: '#0e1418', tickMajorColorM: '#060a0c',
  digitFont: 10, digitTint: '#1e262c', digitTintAmount: 0.6, digitTone: -0.6,
  digitScaleX: 3.5, digitScaleY: 3.25, digitBottom: 6, digitHourStep: 3,
  digitScaleXMin: 2.5, digitScaleYMin: 2.5, digitBottomMin: 16, digitMinuteStep: 15,
  liquidBright: 1.35, tickBright: 1.05, digitBright: 1,
};

/** Honey: translucent amber syrup — overdamped, climbs and clings, a few slow trapped bubbles,
 *  brass numerals seen through it. */
export const PRESET_HONEY: Partial<Params> = {
  ...MODERN_BASE, ...VISCOUS,
  liquid: '#7a4206', liquidHi: '#f0c060', liquidLo: '#3d1c03', tubeBack: '#0c0703', tubeBack2: '#1c1208', bubbleRim: '#ffd890',
  glassHi: '#f0dcb0', glassBody: 0.08, glassHiBright: 0.45, glassReflect: 0.25, glassRim: 0.6,
  highlightH: 14, highlightBright: 0.4, highlightSharp: 1.8, shadeDepth: 0.78,
  traces: true, traceAmount: 0.7, traceDry: 2, traceStain: 0.45,   // syrup coats thickly whatever the speed, crawls back slowly
  liquidTransparency: 0.32,
  tickColorH: '#4a3210', tickMajorColorH: '#5a3e14', tickColorM: '#4a3210', tickMajorColorM: '#5a3e14',
  digitFont: 6, digitTint: '#d4923a', digitTintAmount: 0.5, digitTone: 0,
  liquidBright: 1.8, tickBright: 1.1, digitBright: 1.5,
};

/** Cola: dark but translucent in a thin tube, watery, lively bead; cream enamel numerals behind. */
export const PRESET_COLA: Partial<Params> = {
  ...MODERN_BASE, ...WATERY,
  liquid: '#3a1206', liquidHi: '#e8b890', liquidLo: '#120602', tubeBack: '#070403', tubeBack2: '#140c07', bubbleRim: '#f0d8c4',
  glassHi: '#e8dcd2', glassBody: 0.08, glassHiBright: 0.5, glassReflect: 0.25, glassRim: 0.6, glassOverLiquid: 0.5,
  highlightH: 9, highlightBright: 0.5, highlightSharp: 3, shadeDepth: 0.7,
  liquidTransparency: 0.38, markContrast: 24,
  tickColorH: '#4a3e32', tickMajorColorH: '#5a4a3c', tickColorM: '#4a3e32', tickMajorColorM: '#5a4a3c',
  digitFont: 9, digitTint: '#f3e6c8', digitTintAmount: 0.4, digitTone: 0,
  liquidBright: 1.7, tickBright: 1.1, digitBright: 1.4,
};

/** Single malt in cut crystal: warm amber, a shade thicker than water, alcohol legs on the wall,
 *  brass numerals under the liquid, ticks cut into the glass. */
export const PRESET_MALT: Partial<Params> = {
  ...MODERN_BASE, ...MEDIUM,
  liquid: '#7a4e14', liquidHi: '#ffe0a8', liquidLo: '#2e1704', tubeBack: '#0a0603', tubeBack2: '#160e05', bubbleRim: '#f0c88a',
  glassHi: '#f2e0b4', glassBody: 0.1, glassHiBright: 0.5, glassReflect: 0.3, glassRim: 0.7, glassOverLiquid: 0.45,
  highlightH: 12, highlightBright: 0.5, highlightSharp: 1.6, shadeDepth: 0.78,
  wetFilm: 18,
  traces: true, traceAmount: 0.45, traceDry: 0.6, traceStain: 0.2,   // thin legs crawl down and dry quickly
  liquidTransparency: 0.42, markContrast: 24,
  ticksOnTop: true, tickLens: 0, tickParallax: 0, tickEmboss: 0.5,
  tickMinorWidthH: 1, tickMajorWidthH: 2, tickMinorWidthM: 1, tickMajorWidthM: 2, tickMajorEveryH: 3, tickMajorEveryM: 15,
  tickColorH: '#6a5a40', tickMajorColorH: '#b09660', tickColorM: '#6a5a40', tickMajorColorM: '#b09660',
  digitFont: 6, digitTint: '#c08a2a', digitTintAmount: 0.4, digitTone: 0.1,
  liquidBright: 1.8, tickBright: 0.9, digitBright: 1.4,
};

/** Champagne flute: tinted pale gold (translucent), watery, dense fine bead, amber-resin numerals. */
export const PRESET_CHAMPAGNE: Partial<Params> = {
  ...MODERN_BASE, ...WATERY,
  liquid: '#8a7228', liquidHi: '#fff8dc', liquidLo: '#4a3808', tubeBack: '#080602', tubeBack2: '#161004', bubbleRim: '#fff4cc',
  glassHi: '#f6ecd0', glassBody: 0.1, glassHiBright: 0.55, glassReflect: 0.3, glassRim: 0.7, glassOverLiquid: 0.55,
  highlightH: 9, highlightBright: 0.55, highlightSharp: 2.6, shadeDepth: 0.55,
  liquidTransparency: 0.5, markContrast: 24,
  tickColorH: '#4a3e18', tickMajorColorH: '#5a4c20', tickColorM: '#4a3e18', tickMajorColorM: '#5a4c20',
  digitFont: 11, digitTint: '#e0b45a', digitTintAmount: 0.2, digitTone: 0,
  liquidBright: 1.8, tickBright: 1.1, digitBright: 1.1,
};

/** Cryogenic oxygen: clear pale blue, thinner than water, boiling hard, frosted wall. */
export const PRESET_CRYO: Partial<Params> = {
  ...MODERN_BASE, ...WATERY,
  liquid: '#3a7aa8', liquidHi: '#ffffff', liquidLo: '#0e3f66', tubeBack: '#03070c', tubeBack2: '#0c1620', bubbleRim: '#f0fbff',
  glassHi: '#e2f4ff', glassBody: 0.16, glassHiBright: 0.45, glassReflect: 0.28, glassRim: 0.85, glassOverLiquid: 0.6,
  highlightH: 10, highlightBright: 0.45, highlightSharp: 1.8, shadeDepth: 0.45,
  meniscusK: 520, meniscusDamp: 4, meniscusInertia: 4, wetFilm: 8,
  freeDamp: 0.5, freeBounce: 0.3, angleTiltGain: 8, angleGyroGain: 0.5,
  liquidTransparency: 0.72, markContrast: 20,
  tickColorH: '#3a5060', tickMajorColorH: '#465e70', tickColorM: '#3a5060', tickMajorColorM: '#465e70',
  digitFont: 5, digitTint: '#a6d8ff', digitTintAmount: 0.6, digitTone: 0.15,
  liquidBright: 1.6, tickBright: 1.1, digitBright: 1.3,
};

/** India ink: matte black body, almost every pixel off, enamel numerals printed on the glass. */
export const PRESET_INK: Partial<Params> = {
  ...MODERN_BASE, ...LAYOUT_WIDE, ...FRONT_PRINT, ...MEDIUM,
  liquid: '#0e1428', liquidHi: '#5a70a0', liquidLo: '#03040c', tubeBack: '#000000', tubeBack2: '#000000', bubbleRim: '#4a5a78',
  glassHi: '#8c9bb5', glassBody: 0.05, glassHiBright: 0.3, glassReflect: 0.2, glassRim: 0.45, glassOverLiquid: 0.3,
  highlightH: 7, highlightBright: 0.8, highlightSharp: 2.6, shadeDepth: 0.9,
  traces: true, traceAmount: 0.5, traceDry: 1.2, traceStain: 0.4,   // thin ink drains back fast, the stain lingers a beat
  liquidTransparency: 0,
  tickMinorWidthH: 1, tickMajorWidthH: 1, tickMinorWidthM: 1, tickMajorWidthM: 1,
  tickColorH: '#5c6470', tickMajorColorH: '#e8e4d8', tickColorM: '#5c6470', tickMajorColorM: '#e8e4d8',
  digitFont: 9, digitTint: '#efe7d2', digitTintAmount: 0.5, digitTone: 0.1,
  digitScaleX: 3.25, digitScaleY: 3.25, digitBottom: 5, digitHourStep: 3,
  digitScaleXMin: 2.25, digitScaleYMin: 2.25, digitBottomMin: 16, digitMinuteStep: 15,
  brightness: 0.85, liquidBright: 1.3, tickBright: 1.2, digitBright: 1.1,
};

/** Glow stick: fluorescent green ester, its own light source — glow past the cap, no world light,
 *  a shade thicker than water; seven-segment print on the tube. */
export const PRESET_GLOW: Partial<Params> = {
  ...MODERN_BASE, ...LAYOUT_WIDE, ...FRONT_PRINT, ...MEDIUM,
  liquid: '#5ad81e', liquidHi: '#e4ffc8', liquidLo: '#1f7a08', tubeBack: '#020602', tubeBack2: '#061006', bubbleRim: '#dfffc0',
  glassHi: '#a8d8a0', glassBody: 0.06, glassHiBright: 0.35, glassReflect: 0.15, glassRim: 0.4, glassOverLiquid: 0.4,
  highlightH: 14, highlightBright: 0.6, highlightSharp: 1.2, shadeDepth: 0.55,
  edgeSoft: 0, frontBright: 14, edgeGlow: 28, glowStrength: 0.7, edgeLightGain: 0.3,
  liquidTransparency: 0.35, markContrast: 30,
  tickPosH: 2, tickPosM: 2, tickColorH: '#4f8a3e', tickMajorColorH: '#c6ffb0', tickColorM: '#4f8a3e', tickMajorColorM: '#c6ffb0',
  digitFont: 3, digitColor: '#e6ffd6', digitColor2: '#8fe070',
  digitScaleX: 3.5, digitScaleY: 3.25, digitBottom: 10, digitHourStep: 3,
  digitScaleXMin: 2.5, digitScaleYMin: 2.75, digitBottomMin: 14, digitMinuteStep: 15,
  lightPhys: 0, lightAngle: 45,
  liquidBright: 1.3, tickBright: 1, digitBright: 1,
};

/** Xenon discharge tube: violet plasma has no inertia — no slosh, no meniscus dynamics, no film, no slug —
 *  glow past the column end, bold print. */
export const PRESET_XENON: Partial<Params> = {
  ...MODERN_BASE, ...LAYOUT_WIDE,
  contactAngle: 100, contactHyst: 0, contactDyn: 0, wallWet: 0,
  liquid: '#5a30d8', liquidHi: '#d9c8ff', liquidLo: '#1a0570', tubeBack: '#05020c', tubeBack2: '#0a0418', bubbleRim: '#d8ccff',
  glassHi: '#a394d8', glassBody: 0.1, glassHiBright: 0.5, glassReflect: 0.2, glassRim: 0.6, glassOverLiquid: 0.4,
  highlightH: 14, highlightBright: 0.7, highlightSharp: 1.5, shadeDepth: 0.42,
  meniscusK: 400, meniscusDamp: 30, meniscusInertia: 0, wetFilm: 0,
  edgeSoft: 0, frontBright: 18, edgeGlow: 26, glowStrength: 0.6, cornerR: 14, edgeLightGain: 0.3,
  liquidTransparency: 0.5, markContrast: 34,
  tickMinorHeightH: 11, tickMajorEveryH: 3, tickMajorEveryM: 15, tickColorH: '#3a2a6a', tickMajorColorH: '#9a86ff', tickColorM: '#3a2a6a', tickMajorColorM: '#9a86ff',
  digitFont: 4, digitsOnTop: true, digitShadow: false, digitColor: '#00e5ff', digitColor2: '#00708f',
  digitScaleX: 3.5, digitScaleY: 3.25, digitBottom: 10, digitHourStep: 3,
  digitScaleXMin: 2.5, digitScaleYMin: 2.75, digitBottomMin: 14, digitMinuteStep: 15,
  freeLiquid: false, fillK: 260, fillDamp: 22, fillSloshGain: 0.5, angleK: 300, angleDamp: 26, angleTiltGain: 0.5, angleGyroGain: 0.03, angleMax: 2,
  lightPhys: 0, lightAngle: 40,
  liquidBright: 1.3, tickBright: 1, digitBright: 0.9,
};

/** Molten iron in a sooted vial: emissive, opaque, dense, does not wet the wall, slow gas bubbles;
 *  forged numerals printed on the glass. */
export const PRESET_MOLTEN: Partial<Params> = {
  ...MODERN_BASE, ...LAYOUT_WIDE, ...FRONT_PRINT, ...MEDIUM,
  contactAngle: 120, contactHyst: 10, contactDyn: 5, capLength: 5,
  liquid: '#e04c00', liquidHi: '#ffd98a', liquidLo: '#5e0e00', tubeBack: '#0b0300', tubeBack2: '#160600', bubbleRim: '#ffd08a',
  glassHi: '#c08a60', glassBody: 0.07, glassHiBright: 0.4, glassReflect: 0.18, glassRim: 0.45, glassOverLiquid: 0.3,
  highlightH: 10, highlightBright: 0.6, highlightSharp: 1.2, shadeDepth: 0.78,
  meniscusK: 400, meniscusDamp: 14, meniscusInertia: 4, wetFilm: 0,
  freeDamp: 2.5, freeBounce: 0.05,
  edgeSoft: 0, frontBright: 16, edgeGlow: 26, glowStrength: 0.6, edgeLightGain: 1,
  liquidTransparency: 0.06,
  tickEmboss: 0.35, tickPosH: 2, tickPosM: 2, tickColorH: '#6a5248', tickMajorColorH: '#b39a8c', tickColorM: '#6a5248', tickMajorColorM: '#b39a8c',
  digitFont: 8, digitTint: '#b06a34', digitTintAmount: 0.45, digitTone: 0.3,
  digitScaleX: 3.5, digitScaleY: 3.25, digitBottom: 6, digitHourStep: 3,
  digitScaleXMin: 2.5, digitScaleYMin: 2.5, digitBottomMin: 16, digitMinuteStep: 15,
  lightPhys: 0, lightAngle: 45,
  liquidBright: 1.3, tickBright: 1, digitBright: 1.1,
};

/** Free liquid: the column slides as a slug at strong tilt and settles home at a gentle viewing angle.
 *  Dark bottle green, low-climb wetting
 *  liquid with a watery surface (K 460, ζ≈0.12), copper gauge numerals behind the liquid. Saved 2026-08-26. */
const PRESET_FREE: Partial<Params> = {
  ...PLAIN_TUBE_BACK,
  contactAngle: 20, contactHyst: 10, contactDyn: 8, capLength: 2.4,
  tubeHeight: 56, hoursY: 9, minutesY: 180, liquid: '#1f602f', liquidHi: '#1a6528', liquidLo: '#214002',
  tubeBack: '#10140f', glassBody: 0.03, glassHiBright: 0.15, glassReflect: 0.11, glassRim: 0.13,
  glassOverLiquid: 0.25, lens: -0.4, lensCurve: 0.6, bubbleRim: '#255917', highlightH: 26, highlightBright: 0.15,
  highlightSharp: 3, highlightInset: 31, shadeDepth: 0.74,
  meniscusK: 460, meniscusDamp: 5, meniscusInertia: 2,
  wetFilm: 15, edgeSoft: 0.7, frontBright: 23, edgeGlow: 40, glowStrength: 0.21, edgeLightGain: 0.55, bubbleW: 28,
  bubbleH: 20, bubbleGap: 18, bubbleY: 0.28, bubbleTiltGain: 14, bubbleDark: 0.55,
  tickMajorEveryH: 0, tickMinorHeightH: 11, tickMajorHeightH: 22, tickMinorWidthH: 2,
  tickMajorWidthH: 3, tickColorH: '#243120', tickMajorColorH: '#243120', tickPosH: 1, tickMajorEveryM: 0,
  tickMinorHeightM: 5, tickMajorHeightM: 28, tickMinorWidthM: 2, tickColorM: '#243120', tickMajorColorM: '#243120',
  tickPosM: 1, tickLens: 0.45, tickParallax: 4.75, tickDryLens: 0.35, tickEmboss: 0.55, digitFont: 7,
  digitTint: '#827c40', digitTintAmount: 0.9, digitTone: -0.1, digitScaleX: 3.5, digitScaleY: 3.25,
  digitScaleXMin: 2.5, digitScaleYMin: 3, digitBottomMin: 17, digitBottom: 17, bottomLens: 0.45, digitDryLens: 0.35,
  topLens: 0.35, topParallax: -10, liquidTransparency: 0.47, markContrast: 34, digitMinuteStep: 5, digitHourStep: 1,
  freeLiquid: true, freeGain: 990, freeDamp: 0.8, freeHomeK: 150,
  fillK: 756, fillDamp: 40, lightPhys: 1, brightness: 1, liquidBright: 2, digitBright: 1.53,
};

/** User-tuned olive oil (2026-09-18), preserved independently of the material-class ranges. */
const PRESET_OLIVE_OIL: Partial<Params> = {
  contactAngle: 15, contactHyst: 8, contactDyn: 40, capLength: 1.9,
  tubeHeight: 60, hoursY: 0, minutesY: 185, remaining: false,
  liquid: '#5e5b08', liquidHi: '#8a8619', liquidLo: '#89861f',
  tubeBack: '#110b03', tubeBack2: '#000000', tubeBackGradient: 0, glassHi: '#322d2a',
  glassBody: 0.32, glassHiBright: 0.77, glassReflect: 0.35, glassRim: 0.69, glassWall: 5, glassWallGlow: 0.6, glassOverLiquid: 0.64,
  lens: -0.2, lensCurve: 0.2, bubbleRim: '#2d3319',
  highlightH: 9, highlightBright: 0.35, highlightSharp: 2, highlightInset: 0, shadeDepth: 0.25, liquidThin: 0.6,
  meniscusLens: 0,
  meniscusK: 685, meniscusDamp: 38, meniscusInertia: 10, wetFilm: 15,
  traces: true, traceAmount: 2, traceDry: 2, traceStain: 1,
  edgeSoft: 3.7, frontBright: 0, edgeGlow: 27, glowStrength: 0.34, cornerR: 0, edgeLightGain: 0.55,
  bubble: false, bubbleW: 27, bubbleH: 20, bubbleGap: 28, bubbleY: 0.28,
  bubbleRollGain: 0.5, bubbleTiltGain: 14, bubbleDark: 0.12,
  ticksH: true, tickStepH: 1, tickMajorEveryH: 0, tickMinorHeightH: 17, tickMajorHeightH: 22,
  tickMinorWidthH: 2, tickMajorWidthH: 3, tickColorH: '#372e0b', tickMajorColorH: '#4d4d4d', tickPosH: 2,
  ticksM: true, tickStepM: 5, tickMajorEveryM: 0, tickMinorHeightM: 18, tickMajorHeightM: 28,
  tickMinorWidthM: 2, tickMajorWidthM: 2, tickColorM: '#372e0b', tickMajorColorM: '#4d4d4d', tickPosM: 2,
  ticksOnTop: false, tickLens: 0.45, tickParallax: 6, tickDryLens: 0.1, tickEmboss: 0.4,
  digits: true, digitColor: '#e3e3e3', digitColor2: '#20312f', digitShadow: true,
  digitShadowColor: '#101010', digitShadowStrength: 1, digitShadowOffset: 1, digitFont: 6,
  digitTint: '#2a1c09', digitTintAmount: 0, digitTone: 0.05,
  digitScaleX: 3.5, digitScaleY: 2.75, digitScaleXMin: 3, digitScaleYMin: 2.75,
  digitBottomMin: 21, digitBottom: 22, digitsOnTop: false,
  bottomLens: 0.45, digitDryLens: 0.1, topLens: 0.35, topParallax: -10, digitParallax: 4.75,
  liquidTransparency: 0.39, markContrast: 0, digitsLeadingZero: false,
  digitMinuteStep: 5, digitHourStep: 1, digitHourStart: 0, digitMinuteStart: 0,
  digitsLastOnlyH: false, digitsLastOnlyM: false,
  freeLiquid: true, freeGain: 840, freeDamp: 7, freeBounce: 0, freeHomeK: 150,
  readTiltStart: 20, readTiltEnd: 50, playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5,
  angleK: 207, angleDamp: 17.6, angleTiltGain: 6.5, angleGyroGain: 0.42, angleMax: 6,
  lightPhys: 1, lightAngle: 73, acrossK: 200, acrossDamp: 20, acrossGyroGain: 0, shakeGain: 0,
  deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5, gyroDeadzone: 31, gyroMax: 470, inputGain: 1,
  brightness: 1, liquidBright: 0.98, tickBright: 1.2, digitBright: 2, ambientLight: 1,
};

/** Pinot noir (2026-09-23): a thin column of red wine reads ruby, not black — a saturated, bright body at
 *  low transparency (a dark body mixed toward the back turns mauve). Parchment cellar-thermometer backing,
 *  bronze numerals seen dimly through the wine, and legs: a clinging coat that drains slowly after a tilt.
 *  Standard rod only, exempt from the material-class ranges (it keeps the current tuned slug physics). */
const PRESET_PINOT: Partial<Params> = {
  contactAngle: 20, contactHyst: 10, contactDyn: 8, capLength: 2.4,
  tubeHeight: 54, hoursY: 0, minutesY: 185, remaining: true, liquid: '#8c0a1c', liquidHi: '#ffb8c0',
  liquidLo: '#4a0410', tubeBack: '#f1e6cf', tubeBack2: '#000000', tubeBackGradient: 0, glassHi: '#5c5654',
  glassBody: 0, glassHiBright: 0.08, glassReflect: 0.2, glassRim: 0.63, glassWall: 4.5, glassWallGlow: 0,
  glassOverLiquid: 0.25, lens: -0.2, lensCurve: 0.2, bubbleRim: '#3a0a10', highlightH: 10,
  highlightBright: 0.35, highlightSharp: 2, highlightInset: 0, shadeDepth: 0.5, liquidThin: 0.15,
  meniscusLens: 0.05,
  meniscusK: 685, meniscusDamp: 38, meniscusInertia: 5.6, wetFilm: 18, traces: true,
  traceAmount: 1, traceDry: 1.5, traceStain: 0.3, traceFilm: 0.03,
  edgeSoft: 4, frontBright: 0, surfaceBand: 0.3, surfaceRim: 0.35, surfaceWidth: 4, surfaceTone: -0.1,
  edgeGlow: 0, glowStrength: 0, cornerR: 0, edgeLightGain: 0.55, bubble: false, bubbleW: 27, bubbleH: 20,
  bubbleGap: 28, bubbleY: 0.28, bubbleRollGain: 0.5, bubbleTiltGain: 14, bubbleDark: 0,
  ticksH: true, tickStepH: 1, tickMajorEveryH: 0, tickMinorHeightH: 11, tickMajorHeightH: 22,
  tickMinorWidthH: 2, tickMajorWidthH: 3, tickColorH: '#6a4a20', tickMajorColorH: '#6a4a20', tickPosH: 2,
  ticksM: true, tickStepM: 5, tickMajorEveryM: 0, tickMinorHeightM: 12, tickMajorHeightM: 28,
  tickMinorWidthM: 2, tickMajorWidthM: 2, tickColorM: '#6a4a20', tickMajorColorM: '#6a4a20', tickPosM: 2,
  ticksOnTop: false, tickLens: 0.45, tickParallax: 6, tickDryLens: 0.1, tickEmboss: 0.4, digits: true,
  digitColor: '#e3e3e3', digitColor2: '#20312f', digitShadow: true, digitShadowColor: '#121212',
  digitShadowStrength: 0.5, digitShadowOffset: 1, digitFont: 6, digitTint: '#3a1a08', digitTintAmount: 0.5,
  digitTone: -0.3, digitScaleX: 3.5, digitScaleY: 2.75, digitScaleXMin: 3, digitScaleYMin: 2.75,
  digitBottomMin: 21, digitBottom: 22, digitsOnTop: false, bottomLens: 0.45, digitDryLens: 0.1, topLens: 0.35,
  topParallax: -10, digitParallax: 4.75, liquidTransparency: 0.12, markContrast: 0, digitsLeadingZero: false,
  digitMinuteStep: 5, digitHourStep: 1, digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false,
  digitsLastOnlyM: false, freeLiquid: true, freeGain: 840, freeDamp: 7, freeBounce: 0, freeHomeK: 0,
  readTiltStart: 0, readTiltEnd: 1, playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207,
  angleDamp: 17.6, angleTiltGain: 6.5, angleGyroGain: 0.42, angleMax: 6, lightPhys: 1, lightAngle: 31,
  acrossK: 200, acrossDamp: 20, acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5,
  gyroDeadzone: 31, gyroMax: 470, inputGain: 1, brightness: 1, liquidBright: 1.1, tickBright: 2,
  digitBright: 2, ambientLight: 0,
};

/** Aperol spritz (2026-09-23): a vivid orange-red aperitivo that stays saturated in a thin column — bright body
 *  at low transparency, amber highlight instead of white so it never goes pastel, dark-rimmed prosecco bead
 *  that packs into a foam ring at the surface. White bar-glass backing with navy enamel numerals seen dimly
 *  through the drink. Standard rod only, on the current tuned slug physics (exempt from the class ranges). */
const PRESET_SPRITZ: Partial<Params> = {
  contactAngle: 20, contactHyst: 10, contactDyn: 8, capLength: 2.4,
  tubeHeight: 54, hoursY: 0, minutesY: 185, remaining: true, liquid: '#e8420a', liquidHi: '#f7a44c',
  liquidLo: '#8f1c06', tubeBack: '#fbf7ee', tubeBack2: '#000000', tubeBackGradient: 0, glassHi: '#5c5654',
  glassBody: 0, glassHiBright: 0.08, glassReflect: 0.4, glassRim: 0.63, glassWall: 4.5, glassWallGlow: 0,
  glassOverLiquid: 0.6, lens: -0.2, lensCurve: 0.2, bubbleRim: '#5a1605', highlightH: 9, highlightBright: 0.4,
  highlightSharp: 2, highlightInset: 0, shadeDepth: 0.4, liquidThin: 0.4,
  meniscusLens: 0.05, meniscusK: 685,
  meniscusDamp: 38, meniscusInertia: 5.6, wetFilm: 14, traces: false, traceAmount: 0,
  traceDry: 1, traceStain: 0.2, traceFilm: 0, edgeSoft: 4, frontBright: 0,
  surfaceBand: 0.3, surfaceRim: 0.35, surfaceWidth: 4, surfaceTone: 0, edgeGlow: 0, glowStrength: 0,
  cornerR: 0, edgeLightGain: 0.55, bubble: false, bubbleW: 27, bubbleH: 20, bubbleGap: 28, bubbleY: 0.28,
  bubbleRollGain: 0.5, bubbleTiltGain: 14, bubbleDark: 0,
  ticksH: true, tickStepH: 1,
  tickMajorEveryH: 0, tickMinorHeightH: 11, tickMajorHeightH: 22, tickMinorWidthH: 2, tickMajorWidthH: 3,
  tickColorH: '#233052', tickMajorColorH: '#233052', tickPosH: 2, ticksM: true, tickStepM: 5,
  tickMajorEveryM: 0, tickMinorHeightM: 12, tickMajorHeightM: 28, tickMinorWidthM: 2, tickMajorWidthM: 2,
  tickColorM: '#233052', tickMajorColorM: '#233052', tickPosM: 2, ticksOnTop: false, tickLens: 0.5,
  tickParallax: 6, tickDryLens: 0.1, tickEmboss: 0.4, digits: true, digitColor: '#e3e3e3',
  digitColor2: '#20312f', digitShadow: true, digitShadowColor: '#121212', digitShadowStrength: 0.5,
  digitShadowOffset: 1, digitFont: 9, digitTint: '#1d2b4f', digitTintAmount: 0.85, digitTone: -0.2,
  digitScaleX: 3.5, digitScaleY: 2.75, digitScaleXMin: 3, digitScaleYMin: 2.75, digitBottomMin: 21,
  digitBottom: 22, digitsOnTop: false, bottomLens: 0.5, digitDryLens: 0.1, topLens: 0.35, topParallax: -10,
  digitParallax: 5.5, liquidTransparency: 0.22, markContrast: 0, digitsLeadingZero: false, digitMinuteStep: 5,
  digitHourStep: 1, digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false, digitsLastOnlyM: false,
  freeLiquid: true, freeGain: 840, freeDamp: 7, freeBounce: 0, freeHomeK: 0, readTiltStart: 0, readTiltEnd: 1,
  playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207, angleDamp: 17.6, angleTiltGain: 6.5,
  angleGyroGain: 0.42, angleMax: 6, lightPhys: 1, lightAngle: 31, acrossK: 200, acrossDamp: 20,
  acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5, gyroDeadzone: 31, gyroMax: 470,
  inputGain: 1, brightness: 1, liquidBright: 1.3, tickBright: 2, digitBright: 2, ambientLight: 1,
};

/** Cuvée: straw-gold sparkling wine, ivory backing and bronze rear numerals.
 *  Tuned against the current renderer and the September 2026 reference exports;
 *  bubble diameter, brightness and damping are outside the historical material ranges.
 *  The reading pose parks the liquid; strong tilt releases it. Standard rod only. */
const PRESET_CUVEE: Partial<Params> = {
  contactAngle: 20, contactHyst: 10, contactDyn: 8, capLength: 2.4,
  tubeHeight: 54, hoursY: 0, minutesY: 185, remaining: true, liquid: '#c1a04a', liquidHi: '#fff7de',
  liquidLo: '#7b6229', tubeBack: '#f4f0e5', tubeBack2: '#f4f0e5', tubeBackGradient: 0, glassHi: '#9a9b8d',
  glassBody: 0, glassHiBright: 0.12, glassReflect: 0.28, glassRim: 0.55, glassWall: 4.5, glassWallGlow: 0,
  glassOverLiquid: 0.7, lens: -0.2, lensCurve: 0.2, bubbleRim: '#f4edce', highlightH: 9, highlightBright: 0.4,
  highlightSharp: 2.8, highlightInset: 0, shadeDepth: 0.36, liquidThin: 0.46,
  meniscusLens: 0.05, meniscusK: 685,
  meniscusDamp: 38, meniscusInertia: 5.6, wetFilm: 16, traces: false, traceAmount: 0,
  traceDry: 1.15, traceStain: 1, traceFilm: 0, edgeSoft: 2.4, frontBright: 0,
  surfaceBand: 0.18, surfaceRim: 0.24, surfaceWidth: 3, surfaceTone: -0.08, edgeGlow: 0, glowStrength: 0,
  cornerR: 0, edgeLightGain: 0.55, bubble: false, bubbleW: 27, bubbleH: 20, bubbleGap: 28, bubbleY: 0.28,
  bubbleRollGain: 0.5, bubbleTiltGain: 14, bubbleDark: 0.3,
  ticksH: true, tickStepH: 1,
  tickMajorEveryH: 0, tickMinorHeightH: 11, tickMajorHeightH: 22, tickMinorWidthH: 1, tickMajorWidthH: 3,
  tickColorH: '#51472d', tickMajorColorH: '#51472d', tickPosH: 2, ticksM: true, tickStepM: 5,
  tickMajorEveryM: 0, tickMinorHeightM: 12, tickMajorHeightM: 28, tickMinorWidthM: 1, tickMajorWidthM: 2,
  tickColorM: '#51472d', tickMajorColorM: '#51472d', tickPosM: 2, ticksOnTop: false, tickLens: 0.4,
  tickParallax: 6, tickDryLens: 0.1, tickEmboss: 0.4, digits: true, digitColor: '#e3e3e3',
  digitColor2: '#20312f', digitShadow: true, digitShadowColor: '#121212', digitShadowStrength: 0.35,
  digitShadowOffset: 1, digitFont: 7, digitTint: '#503719', digitTintAmount: 0.6, digitTone: -0.3,
  digitScaleX: 3.5, digitScaleY: 2.75, digitScaleXMin: 3, digitScaleYMin: 2.75, digitBottomMin: 21,
  digitBottom: 22, digitsOnTop: false, bottomLens: 0.4, digitDryLens: 0.1, topLens: 0.35, topParallax: -10,
  digitParallax: 4.75, liquidTransparency: 0.48, markContrast: 0, digitsLeadingZero: false,
  digitMinuteStep: 5, digitHourStep: 1, digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false,
  digitsLastOnlyM: false, freeLiquid: true, freeGain: 840, freeDamp: 7, freeBounce: 0, freeHomeK: 150,
  readTiltStart: 20, readTiltEnd: 50, playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207,
  angleDamp: 17.6, angleTiltGain: 6.5, angleGyroGain: 0.42, angleMax: 6, lightPhys: 1, lightAngle: 31,
  acrossK: 200, acrossDamp: 20, acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5,
  gyroDeadzone: 31, gyroMax: 470, inputGain: 1, brightness: 1, liquidBright: 1.05, tickBright: 1.5,
  digitBright: 1.65, ambientLight: 0.7,
};

/** Nocturne: opaque blue-black ink in smoked glass, with silver front markings.
 *  A soft reflective band and a wetting surface reveal the dark column; medium
 *  drag and draining residue make the ink feel weighty. Standard rod only. */
const PRESET_NOCTURNE: Partial<Params> = {
  contactAngle: 30, contactHyst: 15, contactDyn: 15, capLength: 2.3,
  tubeHeight: 54, hoursY: 0, minutesY: 185, remaining: false, liquid: '#182943', liquidHi: '#849bbc',
  liquidLo: '#050b16', tubeBack: '#6d7883', tubeBack2: '#3c4652', tubeBackGradient: 2, glassHi: '#91a2b6',
  glassBody: 0.025, glassHiBright: 0.16, glassReflect: 0.13, glassRim: 0.55, glassWall: 4.5,
  glassWallGlow: 0.04, glassOverLiquid: 0.3, lens: -0.2, lensCurve: 0.2, bubbleRim: '#f4edce', highlightH: 11,
  highlightBright: 0.62, highlightSharp: 2.5, highlightInset: 0, shadeDepth: 0.72, liquidThin: 0.3,
  meniscusLens: 0.05,
  meniscusK: 300, meniscusDamp: 24, meniscusInertia: 3, wetFilm: 18, traces: true,
  traceAmount: 0.9, traceDry: 1.8, traceStain: 0.5, traceFilm: 0,
  edgeSoft: 2.2, frontBright: 0, surfaceBand: 0.35, surfaceRim: 0.48, surfaceWidth: 3, surfaceTone: -0.15,
  edgeGlow: 0, glowStrength: 0, cornerR: 0, edgeLightGain: 0.55, bubble: false, bubbleW: 27, bubbleH: 20,
  bubbleGap: 28, bubbleY: 0.28, bubbleRollGain: 0.5, bubbleTiltGain: 14, bubbleDark: 0.3,
  ticksH: true,
  tickStepH: 1, tickMajorEveryH: 2, tickMinorHeightH: 6, tickMajorHeightH: 11, tickMinorWidthH: 1,
  tickMajorWidthH: 2, tickColorH: '#a1adba', tickMajorColorH: '#d8e2eb', tickPosH: 0, ticksM: true,
  tickStepM: 1, tickMajorEveryM: 5, tickMinorHeightM: 4, tickMajorHeightM: 9, tickMinorWidthM: 1,
  tickMajorWidthM: 1, tickColorM: '#a1adba', tickMajorColorM: '#d8e2eb', tickPosM: 0, ticksOnTop: true,
  tickLens: 0, tickParallax: 0, tickDryLens: 0, tickEmboss: 0, digits: true, digitColor: '#e3e3e3',
  digitColor2: '#20312f', digitShadow: true, digitShadowColor: '#121212', digitShadowStrength: 0.3,
  digitShadowOffset: 1, digitFont: 5, digitTint: '#bfcddd', digitTintAmount: 0.25, digitTone: 0.1,
  digitScaleX: 3.6, digitScaleY: 3.2, digitScaleXMin: 2.8, digitScaleYMin: 2.8, digitBottomMin: 14,
  digitBottom: 13, digitsOnTop: true, bottomLens: 0.4, digitDryLens: 0.1, topLens: 0.0, topParallax: 0,
  digitParallax: 0, liquidTransparency: 0.06, markContrast: 0, digitsLeadingZero: false, digitMinuteStep: 10,
  digitHourStep: 2, digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false, digitsLastOnlyM: false,
  freeLiquid: true, freeGain: 700, freeDamp: 4, freeBounce: 0.05, freeHomeK: 150, readTiltStart: 20,
  readTiltEnd: 50, playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207, angleDamp: 17.6,
  angleTiltGain: 4, angleGyroGain: 0.25, angleMax: 6, lightPhys: 1, lightAngle: 40, acrossK: 200,
  acrossDamp: 20, acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5,
  gyroDeadzone: 31, gyroMax: 470, inputGain: 1, brightness: 1, liquidBright: 1.1, tickBright: 1,
  digitBright: 1.25, ambientLight: 0.5,
};

/** Bioluminescent tide (2026-09-23): a night-sea sample in a near-black vial — dark teal water that lights
 *  itself cyan where it is thin (edge glow, lit cap, bright rim), with slow drifting plankton sparks instead of
 *  a rising bead (tiny bright fizz, no foam, stirred by motion). Dim steel graduations and sprite digits sit
 *  behind the glass and are lit through the water. The opposite of the spritz on every axis: dark, self-lit,
 *  cold, calm. Standard rod only, current tuned slug physics (exempt from the class ranges). */
const PRESET_TIDE: Partial<Params> = {
  contactAngle: 20, contactHyst: 10, contactDyn: 8, capLength: 2.4,
  tubeHeight: 54, hoursY: 0, minutesY: 185, remaining: true, liquid: '#0d4658', liquidHi: '#9dfaff',
  liquidLo: '#031419', tubeBack: '#04070b', tubeBack2: '#0a1219', tubeBackGradient: 0, glassHi: '#7fb8c4',
  glassBody: 0.05, glassHiBright: 0.25, glassReflect: 0.15, glassRim: 0.45, glassWall: 4.5,
  glassWallGlow: 0.12, glassOverLiquid: 0.35, lens: -0.2, lensCurve: 0.2, bubbleRim: '#d8ffff',
  highlightH: 10, highlightBright: 0.45, highlightSharp: 1.6, highlightInset: 0, shadeDepth: 0.6,
  liquidThin: 0.2,
  meniscusLens: 0.05, meniscusK: 685, meniscusDamp: 38, meniscusInertia: 5.6, wetFilm: 12,
  traces: false, traceAmount: 0, traceDry: 1, traceStain: 0.2, traceFilm: 0,
  edgeSoft: 4, frontBright: 10, surfaceBand: 0.35, surfaceRim: 0.5, surfaceWidth: 4, surfaceTone: 0.2,
  edgeGlow: 26, glowStrength: 0.6, cornerR: 0, edgeLightGain: 0.3, bubble: false, bubbleW: 27, bubbleH: 20,
  bubbleGap: 28, bubbleY: 0.28, bubbleRollGain: 0.5, bubbleTiltGain: 14, bubbleDark: 0,
  ticksH: true,
  tickStepH: 1, tickMajorEveryH: 3, tickMinorHeightH: 5, tickMajorHeightH: 11, tickMinorWidthH: 1,
  tickMajorWidthH: 2, tickColorH: '#3f6a76', tickMajorColorH: '#6fa4ae', tickPosH: 2, ticksM: true,
  tickStepM: 5, tickMajorEveryM: 15, tickMinorHeightM: 5, tickMajorHeightM: 12, tickMinorWidthM: 1,
  tickMajorWidthM: 2, tickColorM: '#3f6a76', tickMajorColorM: '#6fa4ae', tickPosM: 2, ticksOnTop: false,
  tickLens: 0.5, tickParallax: 6, tickDryLens: 0.1, tickEmboss: 0.4, digits: true, digitColor: '#e3e3e3',
  digitColor2: '#20312f', digitShadow: true, digitShadowColor: '#121212', digitShadowStrength: 0.5,
  digitShadowOffset: 1, digitFont: 5, digitTint: '#7fd6dd', digitTintAmount: 0.5, digitTone: -0.1,
  digitScaleX: 3.5, digitScaleY: 2.75, digitScaleXMin: 3, digitScaleYMin: 2.75, digitBottomMin: 21,
  digitBottom: 22, digitsOnTop: false, bottomLens: 0.5, digitDryLens: 0.1, topLens: 0.35, topParallax: -10,
  digitParallax: 5.5, liquidTransparency: 0.4, markContrast: 30, digitsLeadingZero: false,
  digitMinuteStep: 15, digitHourStep: 3, digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false,
  digitsLastOnlyM: false, freeLiquid: true, freeGain: 840, freeDamp: 7, freeBounce: 0, freeHomeK: 0,
  readTiltStart: 0, readTiltEnd: 1, playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207,
  angleDamp: 17.6, angleTiltGain: 6.5, angleGyroGain: 0.42, angleMax: 6, lightPhys: 0.25, lightAngle: 45,
  acrossK: 200, acrossDamp: 20, acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5,
  gyroDeadzone: 31, gyroMax: 470, inputGain: 1, brightness: 1, liquidBright: 1.25, tickBright: 1.1,
  digitBright: 1.2, ambientLight: 0,
};

/** Gas is chosen separately from the liquid: a preset's `p` carries no fizz key, its `gas` lists the models
 *  that fit the liquid (the first is its signature, applied by presetParams) and the picker's gas dropdown
 *  swaps between them. A model sets every GAS_KEYS key (unset ones take DEFAULT_PARAMS). */
export const GAS_KEYS = [
  'fizz', 'fizzCount', 'fizzSize', 'fizzSizeVar', 'fizzShadeOff', 'fizzSpeed', 'fizzDriftGain', 'fizzAcrossGain',
  'fizzFlatRise', 'fizzSquash', 'fizzEdgeRise', 'fizzFoamLife', 'fizzDepth', 'fizzBlick',
  'fizzSource', 'fizzSourceX', 'fizzSourceY', 'fizzSourceSpread', 'fizzSourceRate',
] as const satisfies readonly (keyof Params)[];
export type GasKey = (typeof GAS_KEYS)[number];

export interface GasModel { id: string; name: string; note: string; p: Partial<Pick<Params, GasKey>> }

/** The gas catalogue, each taken from the preset whose bead defined it (2026-09-27). */
export const GAS_MODELS: readonly GasModel[] = [
  { id: 'none', name: 'No gas', note: 'still liquid', p: { fizz: false } },
  { id: 'fine-bead', name: 'Fine bead', note: 'dense 1 px carbonation rising fast (frizzante, champagne, alpine)',
    p: { fizz: true, fizzCount: 60, fizzSize: 1, fizzSizeVar: 0.4, fizzShadeOff: 0.3, fizzSpeed: 44, fizzDriftGain: 0.85, fizzAcrossGain: 1.05, fizzFlatRise: 0.5, fizzSquash: 1.3, fizzEdgeRise: 0.5, fizzFoamLife: 4 } },
  { id: 'lively-bead', name: 'Lively bead', note: 'soda bubbles, slightly larger, long-lived foam (cola)',
    p: { fizz: true, fizzCount: 40, fizzSize: 1.5, fizzSizeVar: 0.6, fizzShadeOff: 0.3, fizzSpeed: 36, fizzDriftGain: 0.85, fizzAcrossGain: 1.05, fizzFlatRise: 0.45, fizzSquash: 1.3, fizzEdgeRise: 0.5, fizzFoamLife: 5 } },
  { id: 'pearl-bead', name: 'Pearl bead', note: 'visible pale pearls collecting briefly at the surface (cuvée)',
    p: { fizz: true, fizzCount: 64, fizzSize: 3.8, fizzSizeVar: 0.8, fizzShadeOff: 0.2, fizzSpeed: 28, fizzDriftGain: 1.35, fizzAcrossGain: 1.05, fizzFlatRise: 0.4, fizzSquash: 1.05, fizzEdgeRise: 0.4, fizzFoamLife: 1.6 } },
  { id: 'brisk-pearls', name: 'Brisk pearls', note: 'pearls racing up, short foam (lime soda, prosecco)',
    p: { fizz: true, fizzCount: 60, fizzSize: 4, fizzSizeVar: 0.5, fizzShadeOff: 0.3, fizzSpeed: 59, fizzDriftGain: 1, fizzAcrossGain: 1, fizzFlatRise: 0.45, fizzSquash: 1, fizzEdgeRise: 0.5, fizzFoamLife: 1.5 } },
  { id: 'foam-ring', name: 'Foam ring', note: 'lively large bead packing into a ring at the surface (spritz)',
    p: { fizz: true, fizzCount: 80, fizzSize: 5, fizzSizeVar: 0.65, fizzShadeOff: 0.2, fizzSpeed: 30, fizzDriftGain: 1.35, fizzAcrossGain: 1.05, fizzFlatRise: 0.45, fizzSquash: 1.25, fizzEdgeRise: 0.35, fizzFoamLife: 2.5 } },
  { id: 'large-bubbles', name: 'Large bubbles', note: 'big round bubbles, few, quick to pop (glycerol)',
    p: { fizz: true, fizzCount: 48, fizzSize: 7.5, fizzSizeVar: 0.65, fizzShadeOff: 0.15, fizzSpeed: 28, fizzDriftGain: 1.35, fizzAcrossGain: 1.05, fizzFlatRise: 0.45, fizzSquash: 1.1, fizzEdgeRise: 0.3, fizzFoamLife: 1.5 } },
  { id: 'slow-bubbles', name: 'Slow bubbles', note: 'a few big bubbles drifting up lazily (free liquid, oil)',
    p: { fizz: true, fizzCount: 19, fizzSize: 4.5, fizzSizeVar: 0.7, fizzShadeOff: 0.55, fizzSpeed: 13, fizzDriftGain: 0.85, fizzAcrossGain: 1.05, fizzFlatRise: 0.45, fizzSquash: 2, fizzEdgeRise: 0.3, fizzFoamLife: 6 } },
  { id: 'trapped', name: 'Trapped bubbles', note: 'many bubbles held almost still in a thick liquid (dark glycerol; the material trapped class)',
    p: { fizz: true, fizzCount: 120, fizzSize: 5.7818, fizzSizeVar: 0.65, fizzShadeOff: 0.15, fizzSpeed: 2.455, fizzDriftGain: 0.4491, fizzAcrossGain: 1.05, fizzFlatRise: 0.1745, fizzSquash: 1.1, fizzEdgeRise: 0.2245, fizzFoamLife: 1.5 } },
  { id: 'held-air', name: 'Held air', note: 'a handful of bubbles caught in syrup (honey)',
    p: { fizz: true, fizzCount: 5, fizzSize: 3, fizzSizeVar: 0.6, fizzShadeOff: 0.5, fizzSpeed: 3, fizzDriftGain: 0.4, fizzAcrossGain: 0.8, fizzFlatRise: 0.15, fizzSquash: 1.4, fizzEdgeRise: 0.2, fizzFoamLife: 20 } },
  { id: 'gas-pockets', name: 'Gas pockets', note: 'slow bubbles in a melt (molten iron)',
    p: { fizz: true, fizzCount: 10, fizzSize: 2.5, fizzSizeVar: 0.5, fizzShadeOff: 0.4, fizzSpeed: 7, fizzDriftGain: 0.6, fizzAcrossGain: 0.8, fizzFlatRise: 0.25, fizzSquash: 1.4, fizzEdgeRise: 0.2, fizzFoamLife: 15 } },
  { id: 'boiling', name: 'Boiling', note: 'fine vapour bubbles streaming up (cryo oxygen)',
    p: { fizz: true, fizzCount: 55, fizzSize: 1, fizzSizeVar: 0.5, fizzShadeOff: 0.3, fizzSpeed: 52, fizzDriftGain: 1.2, fizzAcrossGain: 1.05, fizzFlatRise: 0.6, fizzSquash: 1.3, fizzEdgeRise: 0.6, fizzFoamLife: 2 } },
  { id: 'sparks', name: 'Plankton sparks', note: 'tiny bright specks drifting, no foam (bioluminescent tide)',
    p: { fizz: true, fizzCount: 55, fizzSize: 1.5, fizzSizeVar: 0.6, fizzShadeOff: 0, fizzSpeed: 9, fizzDriftGain: 1.6, fizzAcrossGain: 1.05, fizzFlatRise: 0.3, fizzSquash: 1, fizzEdgeRise: 0.1, fizzFoamLife: 0 } },
  { id: 'spring-pearls', name: 'Spring pearls', note: 'one spring at the home end sending a sparse line of large pearls across the bore (subtle soda)',
    p: { fizz: true, fizzCount: 64, fizzSize: 5.5, fizzSizeVar: 0.5, fizzShadeOff: 0.3, fizzSpeed: 48, fizzDriftGain: 1, fizzAcrossGain: 1, fizzFlatRise: 0.45, fizzSquash: 1.2, fizzEdgeRise: 0.5, fizzFoamLife: 1.5, fizzSource: 1, fizzSourceX: 0, fizzSourceY: 0.5, fizzSourceSpread: 1.5, fizzSourceRate: 5 } },
];
export type GasId = string;

/** Every GAS_KEYS value of model `id` (unset keys from DEFAULT_PARAMS). Throws on an unknown id. */
export function gasParams(id: GasId): Pick<Params, GasKey> {
  const g = GAS_MODELS.find((x) => x.id === id);
  if (!g) throw new Error(`no gas model ${id}`);
  const out = {} as Record<GasKey, unknown>;
  for (const k of GAS_KEYS) out[k] = DEFAULT_PARAMS[k];
  return { ...(out as Pick<Params, GasKey>), ...g.p };
}

/** Fitting-gas lists: the signature first, then the groups, `none` always offered. */
const SODA = ['fine-bead', 'lively-bead', 'pearl-bead', 'brisk-pearls', 'foam-ring', 'large-bubbles'];
const OILY = ['slow-bubbles', 'trapped'];
const gases = (first: GasId, ...groups: readonly GasId[][]): GasId[] => [...new Set([first, ...groups.flat(), 'none'])];

export interface PresetEntry { id: string; name: string; note: string; p: Partial<Params>; gas: readonly GasId[]; mat?: Material; legacy?: boolean; big?: boolean }

/** Big-lens twin of a preset (examples/urine_big.json, 2026-08-27): the second physical rod is wider and
 *  barely magnifies, so the tubes grow to 72 px at y 11 / 144, `lens` drops to −0.05 with a −3 curve, and
 *  the marks move with the tube. Thin (46 px) presets take the example's hand-tuned mark values; wider ones
 *  scale their own by 72 / tubeHeight. */
export function bigLens(p: Partial<Params>): Partial<Params> {
  const base = { ...DEFAULT_PARAMS, ...p };
  const out: Partial<Params> = { ...p, tubeHeight: 72, hoursY: 11, minutesY: 144, lens: -0.05, lensCurve: -3 };
  // front digits were pre-warped against the thin rod's magnification; the big rod hardly magnifies
  if (base.digitsOnTop) Object.assign(out, { topLens: 0, topParallax: -3 });
  if (base.tubeHeight === MODERN_BASE.tubeHeight) {
    Object.assign(out, { tickMinorHeightH: 21, tickMinorHeightM: 16, digitScaleYMin: 3, digitBottom: 25, digitBottomMin: 26 });
    // rear ticks sit on the rear digits' wall: same lens behind liquid and behind air
    if (!base.ticksOnTop) Object.assign(out, { tickLens: base.bottomLens, tickParallax: 3.75, tickDryLens: base.digitDryLens, tickEmboss: 0.25 });
    if (!base.digitsOnTop) Object.assign(out, { digitParallax: 3.75 });
  } else {
    const k = 72 / base.tubeHeight;
    for (const key of ['tickMinorHeightH', 'tickMajorHeightH', 'tickMinorHeightM', 'tickMajorHeightM', 'digitBottom', 'digitBottomMin'] as const)
      out[key] = Math.round(base[key] * k);
  }
  return out;
}

const M = (viscosity: Material['viscosity'], opacity: Material['opacity'], emissive: boolean, wetting: boolean, gas: Material['gas']): Material =>
  ({ viscosity, opacity, emissive, wetting, gas });

/** Everything the preset picker and `?preset=<id>` offer. */
/** Phosphor sample (2026-09-23, from the user's phosphor-vial photo): a pale green watery solution in a
 *  clear lab vial standing on white paper, labelled in marker on the glass. Built to show the see-through
 *  meniscus: the dish is a faint wash (surfaceFill 0.25, tone toward the white reflection), its far contact
 *  ring a liquid-tinted contour over the paper (rim colour follows the backdrop), a white blick on the
 *  surface and a bright front contact line (frontBright). Still liquid: no gas, light residue. */
export const PRESET_PHOSPHOR: Partial<Params> = {
  ...MODERN_BASE, ...WATERY, ...FRONT_PRINT,
  tubeHeight: 54, hoursY: 0, minutesY: 185,
  liquid: '#6ccf92', liquidHi: '#f4fff8', liquidLo: '#35905d',
  tubeBack: '#f4f2ec', tubeBack2: '#e4e0d6', tubeBackGradient: 1,
  glassHi: '#c8d3d5', glassBody: 0.03, glassHiBright: 0.24,
  glassReflect: 0.25, glassRim: 0.55, glassWall: 4,
  glassWallGlow: 0.05, glassOverLiquid: 0.6,
  lens: -0.2, lensCurve: 0.2, bubbleRim: '#f4fff8',
  highlightH: 9, highlightBright: 0.55, highlightSharp: 2.4,
  shadeDepth: 0.5, liquidThin: 0.4,
  meniscusInertia: 2.5,
  edgeSoft: 1.4, frontBright: 4, edgeGlow: 6, glowStrength: 0.03,
  surfaceBand: 0.7, surfaceRim: 1, surfaceWidth: 5, surfaceTone: 0.3,
  surfaceFill: 0.35, surfaceBlick: 0.8,
  bubble: false,
  tickStepH: 1, tickMajorEveryH: 3, tickStepM: 5, tickMajorEveryM: 15,
  tickColorH: '#5c5c5c', tickMajorColorH: '#232323', tickColorM: '#5c5c5c', tickMajorColorM: '#232323',
  digitFont: 10, digitTint: '#262626', digitTintAmount: 0.4, digitTone: -0.3,
  digitScaleX: 3.3, digitScaleY: 3.1, digitBottom: 10,
  digitScaleXMin: 2.35, digitScaleYMin: 2.35, digitBottomMin: 11,
  digitHourStep: 3, digitMinuteStep: 15,
  liquidTransparency: 0.5, liquidBright: 1.15, tickBright: 1, digitBright: 1,
};

/** Absinthe (zip params (52), 2026-09-02): vivid green on a white backing in the widest (79 px) tubes, large black numerals behind the liquid. */
const PRESET_ABSINTHE: Partial<Params> = {
  tubeHeight: 79, hoursY: 5, minutesY: 156, remaining: false, liquid: '#1d6e12', liquidHi: '#809419',
  liquidLo: '#79792a', tubeBack: '#ffffff', tubeBack2: '#2e2e2e', tubeBackGradient: 0, glassHi: '#859093',
  glassBody: 0.42, glassHiBright: 0.46, glassReflect: 0.2, glassRim: 0.53, glassWall: 4, glassWallGlow: 0.25,
  rimLight: 0, rimTint: '#000000', glassOverLiquid: 0.41, lens: -0.1, lensCurve: -0.05, bubbleRim: '#245b28',
  highlightH: 16, highlightBright: 0.35, highlightSharp: 2, highlightInset: 0, shadeDepth: 0.68,
  liquidThin: 0.4, contactAngle: 76.8361, contactHyst: 12.1639, contactDyn: 8, capLength: 2.7, meniscusLens: 0,
  meniscusK: 475, meniscusDamp: 15.5, meniscusInertia: 2.1, wetFilm: 20, traces: true, traceAmount: 1.55,
  traceDry: 0.95, traceStain: 0.65, traceFilm: 0, edgeSoft: 3.6,
  frontBright: 0, surfaceBand: 0.5, surfaceRim: 0.6, surfaceWidth: 4, surfaceTone: 0, surfaceFill: 1,
  surfaceBlick: 0, edgeGlow: 17, glowStrength: 0.3, cornerR: 0, edgeLightGain: -0.2, bubble: false,
  bubbleW: 27, bubbleH: 20, bubbleGap: 28, bubbleY: 0.28, bubbleRollGain: 0.5, bubbleTiltGain: 14,
  bubbleDark: 0.21, ticksH: true, tickStepH: 1, tickMajorEveryH: 0, tickMinorHeightH: 26, tickMajorHeightH: 22,
  tickMinorWidthH: 2, tickMajorWidthH: 3, tickColorH: '#404040', tickMajorColorH: '#4d4d4d', tickPosH: 2,
  ticksM: true, tickStepM: 5, tickMajorEveryM: 0, tickMinorHeightM: 26, tickMajorHeightM: 28,
  tickMinorWidthM: 2, tickMajorWidthM: 2, tickColorM: '#383838', tickMajorColorM: '#4d4d4d', tickPosM: 2,
  ticksOnTop: false, tickLens: 0.75, tickParallax: 5, tickDryLens: 0.8, tickEmboss: 0.4, digits: true,
  digitColor: '#e3e3e3', digitColor2: '#20312f', digitShadow: true, digitShadowColor: '#101010',
  digitShadowStrength: 1, digitShadowOffset: 1, digitFont: 7, digitTint: '#827c40', digitTintAmount: 0.9,
  digitTone: -0.4, digitScaleX: 3.5, digitScaleY: 3.25, digitScaleXMin: 2.5, digitScaleYMin: 2.75,
  digitBottomMin: 30, digitBottom: 27, digitsOnTop: false, bottomLens: 0.45, digitDryLens: 0.1, topLens: 0.35,
  topParallax: -10, digitParallax: 5, liquidTransparency: 0.15, markContrast: 62, digitsLeadingZero: false,
  digitMinuteStep: 5, digitHourStep: 1, digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false,
  digitsLastOnlyM: false, freeLiquid: true, freeGain: 570, freeDamp: 0.8, freeBounce: 0.2, freeHomeK: 150,
  readTiltStart: 20, readTiltEnd: 50, playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207,
  angleDamp: 17.6, angleTiltGain: 6.5, angleGyroGain: 0.42, angleMax: 6, lightPhys: 1, lightAngle: 73,
  acrossK: 200, acrossDamp: 20, acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5,
  gyroDeadzone: 31, gyroMax: 470, inputGain: 1, brightness: 1, liquidBright: 1.75, tickBright: 2,
  digitBright: 1.59, ambientLight: 1,
};

/** Chartreuse (zip params (40), 2026-08-31): bright yellow-green on black, soft glowing edge, bronze numerals behind the liquid. */
const PRESET_CHARTREUSE: Partial<Params> = {
  tubeHeight: 47, hoursY: 0, minutesY: 185, remaining: false, liquid: '#1d6e12', liquidHi: '#809419',
  liquidLo: '#79792a', tubeBack: '#000000', tubeBack2: '#000000', tubeBackGradient: 1, glassHi: '#859093',
  glassBody: 0.04, glassHiBright: 0.34, glassReflect: 0.2, glassRim: 0.52, glassWall: 4, glassWallGlow: 0.25,
  rimLight: 0, rimTint: '#000000', glassOverLiquid: 0.4, lens: -0.5, lensCurve: -0.05, bubbleRim: '#425b2a',
  highlightH: 17, highlightBright: 0.35, highlightSharp: 2, highlightInset: 0, shadeDepth: 0.68,
  liquidThin: 0.4, contactAngle: 67.8596, contactHyst: 18, contactDyn: 8, capLength: 2.7, meniscusLens: 0,
  meniscusK: 475, meniscusDamp: 15.5, meniscusInertia: 2.1, wetFilm: 15, traces: false, traceAmount: 0.6,
  traceDry: 1, traceStain: 0.3, traceFilm: 0, edgeSoft: 3.1, frontBright: 0,
  surfaceBand: 0.5, surfaceRim: 0.6, surfaceWidth: 4, surfaceTone: 0, surfaceFill: 1, surfaceBlick: 0,
  edgeGlow: 17, glowStrength: 0.3, cornerR: 0, edgeLightGain: 0.55, bubble: false, bubbleW: 27, bubbleH: 20,
  bubbleGap: 28, bubbleY: 0.28, bubbleRollGain: 0.5, bubbleTiltGain: 14, bubbleDark: 0.38, ticksH: true,
  tickStepH: 1, tickMajorEveryH: 0, tickMinorHeightH: 11, tickMajorHeightH: 22, tickMinorWidthH: 2,
  tickMajorWidthH: 3, tickColorH: '#404040', tickMajorColorH: '#4d4d4d', tickPosH: 2, ticksM: true,
  tickStepM: 5, tickMajorEveryM: 0, tickMinorHeightM: 10, tickMajorHeightM: 28, tickMinorWidthM: 2,
  tickMajorWidthM: 2, tickColorM: '#383838', tickMajorColorM: '#4d4d4d', tickPosM: 2, ticksOnTop: false,
  tickLens: 0.85, tickParallax: 6, tickDryLens: 0.65, tickEmboss: 0.15, digits: true, digitColor: '#e3e3e3',
  digitColor2: '#20312f', digitShadow: true, digitShadowColor: '#101010', digitShadowStrength: 1,
  digitShadowOffset: 1, digitFont: 7, digitTint: '#827c40', digitTintAmount: 0.9, digitTone: -0.4,
  digitScaleX: 3.5, digitScaleY: 3.25, digitScaleXMin: 2.5, digitScaleYMin: 2.75, digitBottomMin: 13,
  digitBottom: 15, digitsOnTop: false, bottomLens: 0.45, digitDryLens: 0.1, topLens: 0.35, topParallax: -10,
  digitParallax: 6, liquidTransparency: 0.52, markContrast: 0, digitsLeadingZero: false, digitMinuteStep: 5,
  digitHourStep: 1, digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false, digitsLastOnlyM: false,
  freeLiquid: true, freeGain: 570, freeDamp: 0.8, freeBounce: 0.2, freeHomeK: 150, readTiltStart: 20,
  readTiltEnd: 50, playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207, angleDamp: 17.6,
  angleTiltGain: 6.5, angleGyroGain: 0.42, angleMax: 6, lightPhys: 1, lightAngle: 73, acrossK: 200,
  acrossDamp: 20, acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5, gyroDeadzone: 31,
  gyroMax: 470, inputGain: 1, brightness: 1, liquidBright: 2, tickBright: 1.38, digitBright: 2,
  ambientLight: 0,
};

/** Bottle green (zip params (50), 2026-09-01): dark green in 80 px tubes on a charcoal backing, faint rear numerals and a coating residue. */
const PRESET_BOTTLE: Partial<Params> = {
  tubeHeight: 80, hoursY: 0, minutesY: 224, remaining: false, liquid: '#405e08', liquidHi: '#27800f',
  liquidLo: '#2a6416', tubeBack: '#0f0f0f', tubeBack2: '#2e2e2e', tubeBackGradient: 0, glassHi: '#859093',
  glassBody: 0.06, glassHiBright: 0.3, glassReflect: 0.14, glassRim: 0.5, glassWall: 4, glassWallGlow: 0.25,
  rimLight: 0, rimTint: '#000000', glassOverLiquid: 0.22, lens: 0.1, lensCurve: -1.3, bubbleRim: '#0c1f05',
  highlightH: 10, highlightBright: 0, highlightSharp: 2, highlightInset: 0, shadeDepth: 0.86, liquidThin: 0.4,
  contactAngle: 75.5715, contactHyst: 13.4285, contactDyn: 8, capLength: 2.7, meniscusLens: 0, meniscusK: 280,
  meniscusDamp: 16, meniscusInertia: 2, wetFilm: 15, traces: true, traceAmount: 0.55, traceDry: 0.55, traceStain: 0.6, traceFilm: 0, edgeSoft: 1.9, frontBright: 0, surfaceBand: 0.5,
  surfaceRim: 0.6, surfaceWidth: 4, surfaceTone: 0, surfaceFill: 1, surfaceBlick: 0, edgeGlow: 14,
  glowStrength: 0.06, cornerR: 0, edgeLightGain: 0.55, bubble: false, bubbleW: 27, bubbleH: 20, bubbleGap: 28,
  bubbleY: 0.28, bubbleRollGain: 0.5, bubbleTiltGain: 14, bubbleDark: 0.26, ticksH: true, tickStepH: 1,
  tickMajorEveryH: 0, tickMinorHeightH: 24, tickMajorHeightH: 26, tickMinorWidthH: 1, tickMajorWidthH: 2,
  tickColorH: '#7a7a7a', tickMajorColorH: '#e8eef2', tickPosH: 2, ticksM: true, tickStepM: 5,
  tickMajorEveryM: 0, tickMinorHeightM: 34, tickMajorHeightM: 36, tickMinorWidthM: 3, tickMajorWidthM: 2,
  tickColorM: '#ffffff', tickMajorColorM: '#ffffff', tickPosM: 2, ticksOnTop: false, tickLens: 0.9,
  tickParallax: 3.75, tickDryLens: 0.8, tickEmboss: 0.3, digits: true, digitColor: '#e3e3e3',
  digitColor2: '#20312f', digitShadow: false, digitShadowColor: '#101010', digitShadowStrength: 1,
  digitShadowOffset: 1, digitFont: 7, digitTint: '#664e1a', digitTintAmount: 0.9, digitTone: 0.15,
  digitScaleX: 3.25, digitScaleY: 3.75, digitScaleXMin: 2.25, digitScaleYMin: 3, digitBottomMin: 28,
  digitBottom: 26, digitsOnTop: false, bottomLens: 0.35, digitDryLens: 0.15, topLens: 1, topParallax: -5.25,
  digitParallax: 3.75, liquidTransparency: 0.48, markContrast: 0, digitsLeadingZero: false,
  digitMinuteStep: 10, digitHourStep: 1, digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false,
  digitsLastOnlyM: false, freeLiquid: true, freeGain: 570, freeDamp: 2.5, freeBounce: 0.1, freeHomeK: 150,
  readTiltStart: 20, readTiltEnd: 50, playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207,
  angleDamp: 17.6, angleTiltGain: 4, angleGyroGain: 0.25, angleMax: 6, lightPhys: 0.5, lightAngle: 73,
  acrossK: 200, acrossDamp: 20, acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5,
  gyroDeadzone: 31, gyroMax: 470, inputGain: 1, brightness: 1, liquidBright: 1.34, tickBright: 0.34,
  digitBright: 0.97, ambientLight: 0,
};

/** Claret (zip params (55), 2026-09-18): near-opaque dark red draining toward the right, light numerals on a white backing. */
const PRESET_CLARET: Partial<Params> = {
  tubeHeight: 60, hoursY: 0, minutesY: 185, remaining: true, liquid: '#420000', liquidHi: '#240000',
  liquidLo: '#2e0000', tubeBack: '#ffffff', tubeBack2: '#000000', tubeBackGradient: 0, glassHi: '#322d2a',
  glassBody: 0.32, glassHiBright: 0.06, glassReflect: 0.35, glassRim: 0.67, glassWall: 10, glassWallGlow: 0.79,
  rimLight: 0, rimTint: '#000000', glassOverLiquid: 0.64, lens: -0.2, lensCurve: 0.2, bubbleRim: '#8f2828',
  highlightH: 9, highlightBright: 0.35, highlightSharp: 2, highlightInset: 0, shadeDepth: 0.25,
  liquidThin: 0.6, contactAngle: 72.6537, contactHyst: 0, contactDyn: 8, capLength: 2.7, meniscusLens: 0,
  meniscusK: 685, meniscusDamp: 38, meniscusInertia: 10, wetFilm: 0, traces: false, traceAmount: 0.25,
  traceDry: 1.7, traceStain: 0.35, traceFilm: 0, edgeSoft: 3.2,
  frontBright: 1, surfaceBand: 0.5, surfaceRim: 0.6, surfaceWidth: 4, surfaceTone: 0, surfaceFill: 1,
  surfaceBlick: 0, edgeGlow: 27, glowStrength: 0.34, cornerR: 0, edgeLightGain: 0.55, bubble: false,
  bubbleW: 27, bubbleH: 20, bubbleGap: 28, bubbleY: 0.28, bubbleRollGain: 0.5, bubbleTiltGain: 14,
  bubbleDark: 0.87, ticksH: true, tickStepH: 1, tickMajorEveryH: 0, tickMinorHeightH: 25, tickMajorHeightH: 22,
  tickMinorWidthH: 2, tickMajorWidthH: 3, tickColorH: '#372e0b', tickMajorColorH: '#4d4d4d', tickPosH: 2,
  ticksM: true, tickStepM: 5, tickMajorEveryM: 0, tickMinorHeightM: 25, tickMajorHeightM: 28,
  tickMinorWidthM: 2, tickMajorWidthM: 2, tickColorM: '#372e0b', tickMajorColorM: '#4d4d4d', tickPosM: 2,
  ticksOnTop: false, tickLens: 0.85, tickParallax: 6, tickDryLens: 1, tickEmboss: 0.4, digits: true,
  digitColor: '#e3e3e3', digitColor2: '#20312f', digitShadow: true, digitShadowColor: '#101010',
  digitShadowStrength: 0.8, digitShadowOffset: 1, digitFont: 9, digitTint: '#2a1c09', digitTintAmount: 0.15,
  digitTone: -0.25, digitScaleX: 3.5, digitScaleY: 2.75, digitScaleXMin: 3, digitScaleYMin: 2.75,
  digitBottomMin: 21, digitBottom: 22, digitsOnTop: false, bottomLens: 0.45, digitDryLens: 0.1, topLens: 0.35,
  topParallax: -10, digitParallax: 4.75, liquidTransparency: 0.1, markContrast: 0, digitsLeadingZero: false,
  digitMinuteStep: 5, digitHourStep: 1, digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false,
  digitsLastOnlyM: false, freeLiquid: true, freeGain: 1300, freeDamp: 2.2, freeBounce: 0, freeHomeK: 150,
  readTiltStart: 20, readTiltEnd: 50, playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207,
  angleDamp: 17.6, angleTiltGain: 6.5, angleGyroGain: 0.42, angleMax: 6, lightPhys: 1, lightAngle: 73,
  acrossK: 200, acrossDamp: 20, acrossGyroGain: 0, shakeGain: 2, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5,
  gyroDeadzone: 31, gyroMax: 470, inputGain: 1, brightness: 1, liquidBright: 1.3, tickBright: 1.2,
  digitBright: 2, ambientLight: 1,
};

/** Olive oil on white (zip params (58), 2026-09-18): the tuned olive oil drained from the right over a white backing, heavy residue. */
const PRESET_OLIVE_WHITE: Partial<Params> = {
  tubeHeight: 60, hoursY: 0, minutesY: 185, remaining: true, liquid: '#5e5b08', liquidHi: '#8a8619',
  liquidLo: '#89861f', tubeBack: '#ffffff', tubeBack2: '#000000', tubeBackGradient: 0, glassHi: '#322d2a',
  glassBody: 0.32, glassHiBright: 0.06, glassReflect: 0.35, glassRim: 0.67, glassWall: 9, glassWallGlow: 0.79,
  rimLight: 0, rimTint: '#000000', glassOverLiquid: 0.64, lens: -0.2, lensCurve: 0.2, bubbleRim: '#3e3d1d',
  highlightH: 9, highlightBright: 0.35, highlightSharp: 2, highlightInset: 0, shadeDepth: 0.25,
  liquidThin: 0.6, contactAngle: 72.6537, contactHyst: 11.4, contactDyn: 8, capLength: 2.7, meniscusLens: 0,
  meniscusK: 685, meniscusDamp: 38, meniscusInertia: 10, wetFilm: 15, traces: true, traceAmount: 2,
  traceDry: 1.7, traceStain: 1, traceFilm: 0, edgeSoft: 4, frontBright: 1,
  surfaceBand: 0.5, surfaceRim: 0.6, surfaceWidth: 4, surfaceTone: 0, surfaceFill: 1, surfaceBlick: 0,
  edgeGlow: 27, glowStrength: 0.34, cornerR: 0, edgeLightGain: 0.55, bubble: false, bubbleW: 27, bubbleH: 20,
  bubbleGap: 28, bubbleY: 0.28, bubbleRollGain: 0.5, bubbleTiltGain: 14, bubbleDark: 0.43, ticksH: true,
  tickStepH: 1, tickMajorEveryH: 0, tickMinorHeightH: 25, tickMajorHeightH: 22, tickMinorWidthH: 2,
  tickMajorWidthH: 3, tickColorH: '#372e0b', tickMajorColorH: '#4d4d4d', tickPosH: 2, ticksM: true,
  tickStepM: 5, tickMajorEveryM: 0, tickMinorHeightM: 25, tickMajorHeightM: 28, tickMinorWidthM: 2,
  tickMajorWidthM: 2, tickColorM: '#372e0b', tickMajorColorM: '#4d4d4d', tickPosM: 2, ticksOnTop: false,
  tickLens: 0.85, tickParallax: 6, tickDryLens: 1, tickEmboss: 0.4, digits: true, digitColor: '#e3e3e3',
  digitColor2: '#20312f', digitShadow: true, digitShadowColor: '#101010', digitShadowStrength: 0.8,
  digitShadowOffset: 1, digitFont: 7, digitTint: '#2a1c09', digitTintAmount: 0.6, digitTone: -0.25,
  digitScaleX: 3.5, digitScaleY: 2.75, digitScaleXMin: 3, digitScaleYMin: 2.75, digitBottomMin: 21,
  digitBottom: 22, digitsOnTop: false, bottomLens: 0.45, digitDryLens: 0.1, topLens: 0.35, topParallax: -10,
  digitParallax: 4.75, liquidTransparency: 0.17, markContrast: 0, digitsLeadingZero: false, digitMinuteStep: 5,
  digitHourStep: 1, digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false, digitsLastOnlyM: false,
  freeLiquid: true, freeGain: 840, freeDamp: 7, freeBounce: 0, freeHomeK: 150, readTiltStart: 20,
  readTiltEnd: 50, playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207, angleDamp: 17.6,
  angleTiltGain: 6.5, angleGyroGain: 0.42, angleMax: 6, lightPhys: 1, lightAngle: 73, acrossK: 200,
  acrossDamp: 20, acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5, gyroDeadzone: 31,
  gyroMax: 470, inputGain: 1, brightness: 1, liquidBright: 1.62, tickBright: 1.2, digitBright: 2,
  ambientLight: 1,
};

/** Menthe (zip params (67), 2026-09-25): translucent teal on white, dark rear numerals. */
const PRESET_MENTHE: Partial<Params> = {
  tubeHeight: 54, hoursY: 0, minutesY: 185, remaining: true, liquid: '#187767', liquidHi: '#b7c2bd',
  liquidLo: '#1c7364', tubeBack: '#ffffff', tubeBack2: '#000000', tubeBackGradient: 0, glassHi: '#545c4d',
  glassBody: 0.15, glassHiBright: 0.25, glassReflect: 0.18, glassRim: 0.69, glassWall: 5, glassWallGlow: 0,
  rimLight: 0, rimTint: '#000000', glassOverLiquid: 0.75, lens: -0.2, lensCurve: 0.2, bubbleRim: '#6f807e',
  highlightH: 8, highlightBright: 0.35, highlightSharp: 2, highlightInset: 0, shadeDepth: 0.56,
  liquidThin: 0.6, contactAngle: 60, contactHyst: 14.5, contactDyn: 27, capLength: 2.1, meniscusLens: -0.3,
  meniscusK: 355, meniscusDamp: 21.5, meniscusInertia: 5.3, wetFilm: 13, traces: false, traceAmount: 0.6,
  traceDry: 1.15, traceStain: 1, traceFilm: 0.88, edgeSoft: 4, frontBright: 0,
  surfaceBand: 0.3, surfaceRim: 0.25, surfaceWidth: 6.5, surfaceTone: 0, surfaceFill: 0.45, surfaceBlick: 0,
  edgeGlow: 0, glowStrength: 0, cornerR: 0, edgeLightGain: 0.55, bubble: false, bubbleW: 27, bubbleH: 20,
  bubbleGap: 28, bubbleY: 0.28, bubbleRollGain: 0.5, bubbleTiltGain: 14, bubbleDark: 0.32, ticksH: true,
  tickStepH: 1, tickMajorEveryH: 0, tickMinorHeightH: 25, tickMajorHeightH: 22, tickMinorWidthH: 2,
  tickMajorWidthH: 3, tickColorH: '#372e0b', tickMajorColorH: '#4d4d4d', tickPosH: 2, ticksM: true,
  tickStepM: 5, tickMajorEveryM: 0, tickMinorHeightM: 25, tickMajorHeightM: 28, tickMinorWidthM: 2,
  tickMajorWidthM: 2, tickColorM: '#372e0b', tickMajorColorM: '#4d4d4d', tickPosM: 2, ticksOnTop: false,
  tickLens: 0.85, tickParallax: 6, tickDryLens: 1, tickEmboss: 0.4, digits: true, digitColor: '#e3e3e3',
  digitColor2: '#20312f', digitShadow: true, digitShadowColor: '#121212', digitShadowStrength: 0.5,
  digitShadowOffset: 1, digitFont: 7, digitTint: '#3a2308', digitTintAmount: 0.65, digitTone: -0.4,
  digitScaleX: 3.5, digitScaleY: 2.75, digitScaleXMin: 3, digitScaleYMin: 2.75, digitBottomMin: 21,
  digitBottom: 22, digitsOnTop: false, bottomLens: 0.45, digitDryLens: 0.1, topLens: 0.35, topParallax: -10,
  digitParallax: 4.75, liquidTransparency: 0.74, markContrast: 0, digitsLeadingZero: false, digitMinuteStep: 5,
  digitHourStep: 1, digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false, digitsLastOnlyM: false,
  freeLiquid: true, freeGain: 840, freeDamp: 7, freeBounce: 0, freeHomeK: 0, readTiltStart: 0, readTiltEnd: 1,
  playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207, angleDamp: 17.6, angleTiltGain: 6.5,
  angleGyroGain: 0.42, angleMax: 6, lightPhys: 1, lightAngle: 31, acrossK: 200, acrossDamp: 20,
  acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5, gyroDeadzone: 31, gyroMax: 470,
  inputGain: 1, brightness: 1, liquidBright: 1.79, tickBright: 2, digitBright: 2, ambientLight: 1,
};

/** Lime soda (zip params (68), 2026-09-26): pale lime over white, a physical-material export tuned by hand. */
const PRESET_LIME: Partial<Params> = {
  tubeHeight: 54, hoursY: 0, minutesY: 185, remaining: false, liquid: '#98ff5a', liquidHi: '#ffffff',
  liquidLo: '#000000', tubeBack: '#ffffff', tubeBack2: '#000000', tubeBackGradient: 0, glassHi: '#dfe6ea',
  glassBody: 0.092, glassHiBright: 0.3283, glassReflect: 0.1492, glassRim: 0.6589, glassWall: 7.5149,
  glassWallGlow: 0.2969, rimLight: 1, rimTint: '#49125f', glassOverLiquid: 0.533, lens: -0.2, lensCurve: 0.2,
  bubbleRim: '#b9c4b3', highlightH: 14, highlightBright: 1, highlightSharp: 2, highlightInset: 0,
  shadeDepth: 0.4, liquidThin: 1, contactAngle: 70, contactHyst: 8.5, contactDyn: 5.1794, capLength: 6.279,
  meniscusLens: 0.05, meniscusK: 550, meniscusDamp: 8.8728, meniscusInertia: 2.9786, wetFilm: 8, traces: true,
  traceAmount: 0.4377, traceDry: 1, traceStain: 0.167,
  traceFilm: 0.0002, edgeSoft: 2.4, frontBright: 0, surfaceBand: 0.35, surfaceRim: 0.45, surfaceWidth: 4,
  surfaceTone: 0, surfaceFill: 0.505, surfaceBlick: 0.9, edgeGlow: 19, glowStrength: 0.055, cornerR: 0,
  edgeLightGain: 0.55, bubble: false, bubbleW: 16, bubbleH: 19, bubbleGap: 22, bubbleY: 0.2,
  bubbleRollGain: 0.5, bubbleTiltGain: 0, bubbleDark: 0.0439, ticksH: true, tickStepH: 1, tickMajorEveryH: 0,
  tickMinorHeightH: 15, tickMajorHeightH: 22, tickMinorWidthH: 2, tickMajorWidthH: 3, tickColorH: '#372e0b',
  tickMajorColorH: '#4d4d4d', tickPosH: 2, ticksM: true, tickStepM: 5, tickMajorEveryM: 0,
  tickMinorHeightM: 15, tickMajorHeightM: 28, tickMinorWidthM: 2, tickMajorWidthM: 2, tickColorM: '#372e0b',
  tickMajorColorM: '#4d4d4d', tickPosM: 2, ticksOnTop: false, tickLens: 0.473, tickParallax: 5.5,
  tickDryLens: 0.1, tickEmboss: 0.25, digits: true, digitColor: '#e3e3e3', digitColor2: '#20312f',
  digitShadow: true, digitShadowColor: '#121212', digitShadowStrength: 0.5, digitShadowOffset: 1, digitFont: 7,
  digitTint: '#3a2308', digitTintAmount: 0.65, digitTone: -0.4, digitScaleX: 3.5, digitScaleY: 2.75,
  digitScaleXMin: 3, digitScaleYMin: 2.75, digitBottomMin: 20, digitBottom: 19, digitsOnTop: false,
  bottomLens: 0.473, digitDryLens: 0.1, topLens: 0.35, topParallax: -10, digitParallax: 4.75,
  liquidTransparency: 0.55, markContrast: 26, digitsLeadingZero: false, digitMinuteStep: 5, digitHourStep: 1,
  digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false, digitsLastOnlyM: false, freeLiquid: true,
  freeGain: 570, freeDamp: 0.8873, freeBounce: 0.3197, freeHomeK: 0, readTiltStart: 0, readTiltEnd: 1,
  playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207, angleDamp: 17.6,
  angleTiltGain: 6.2818, angleGyroGain: 0.4025, angleMax: 6, lightPhys: 1, lightAngle: 22.5, acrossK: 200,
  acrossDamp: 20, acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5, gyroDeadzone: 31,
  gyroMax: 470, inputGain: 1, brightness: 1, liquidBright: 0.86, tickBright: 0.92, digitBright: 1.51,
  ambientLight: 1,
};

/** Patrick pink (zip patrick_pin, 2026-09-09): opaque bubblegum pink, yellow numerals and ticks printed on the glass. */
const PRESET_PATRICK: Partial<Params> = {
  tubeHeight: 60, hoursY: 0, minutesY: 185, remaining: false, liquid: '#dd73b6', liquidHi: '#dd73b6',
  liquidLo: '#dd73b6', tubeBack: '#110b03', tubeBack2: '#000000', tubeBackGradient: 0, glassHi: '#4e3145',
  glassBody: 0.32, glassHiBright: 0, glassReflect: 0.35, glassRim: 0.69, glassWall: 4, glassWallGlow: 0.25,
  rimLight: 0, rimTint: '#000000', glassOverLiquid: 0.64, lens: -0.2, lensCurve: 0.2, bubbleRim: '#2d3319',
  highlightH: 9, highlightBright: 0.35, highlightSharp: 2, highlightInset: 0, shadeDepth: 0.25,
  liquidThin: 0.4, contactAngle: 159.5921, contactHyst: 1.2, contactDyn: 8, capLength: 2.7, meniscusLens: 0,
  meniscusK: 360, meniscusDamp: 3, meniscusInertia: 10, wetFilm: 0, traces: false, traceAmount: 2, traceDry: 2, traceStain: 1, traceFilm: 0, edgeSoft: 4, frontBright: 0,
  surfaceBand: 0.5, surfaceRim: 0.6, surfaceWidth: 4, surfaceTone: 0, surfaceFill: 1, surfaceBlick: 0,
  edgeGlow: 0, glowStrength: 0, cornerR: 0, edgeLightGain: 0.55, bubble: false, bubbleW: 27, bubbleH: 20,
  bubbleGap: 28, bubbleY: 0.28, bubbleRollGain: 0.5, bubbleTiltGain: 14, bubbleDark: 0.12, ticksH: true,
  tickStepH: 1, tickMajorEveryH: 0, tickMinorHeightH: 25, tickMajorHeightH: 22, tickMinorWidthH: 2,
  tickMajorWidthH: 3, tickColorH: '#7e8c18', tickMajorColorH: '#4d4d4d', tickPosH: 2, ticksM: true,
  tickStepM: 5, tickMajorEveryM: 0, tickMinorHeightM: 25, tickMajorHeightM: 28, tickMinorWidthM: 2,
  tickMajorWidthM: 2, tickColorM: '#7e8c18', tickMajorColorM: '#4d4d4d', tickPosM: 2, ticksOnTop: true,
  tickLens: 0.85, tickParallax: 6, tickDryLens: 1, tickEmboss: 0.4, digits: true, digitColor: '#e3e3e3',
  digitColor2: '#20312f', digitShadow: true, digitShadowColor: '#101010', digitShadowStrength: 1,
  digitShadowOffset: 1, digitFont: 9, digitTint: '#ffea00', digitTintAmount: 1, digitTone: 0.2, digitScaleX: 3,
  digitScaleY: 2.5, digitScaleXMin: 2.25, digitScaleYMin: 2, digitBottomMin: 31, digitBottom: 27,
  digitsOnTop: true, bottomLens: 0.45, digitDryLens: 0.1, topLens: 0.35, topParallax: -10, digitParallax: 4.75,
  liquidTransparency: 0, markContrast: 0, digitsLeadingZero: false, digitMinuteStep: 5, digitHourStep: 1,
  digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false, digitsLastOnlyM: false, freeLiquid: true,
  freeGain: 1110, freeDamp: 1.7, freeBounce: 0.4, freeHomeK: 150, readTiltStart: 20, readTiltEnd: 50,
  playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207, angleDamp: 17.6, angleTiltGain: 6.5,
  angleGyroGain: 0.42, angleMax: 6, lightPhys: 1, lightAngle: 73, acrossK: 200, acrossDamp: 20,
  acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5, gyroDeadzone: 31, gyroMax: 470,
  inputGain: 1, brightness: 1, liquidBright: 0.98, tickBright: 1.2, digitBright: 2, ambientLight: 1,
};

/** Seltzer (zip perfect_frizzante, 2026-09-23): colourless water on white, the reference the Cuvée glass was tuned against. */
const PRESET_SELTZER: Partial<Params> = {
  tubeHeight: 54, hoursY: 0, minutesY: 185, remaining: true, liquid: '#b8daff', liquidHi: '#b8daff',
  liquidLo: '#b8daff', tubeBack: '#ffffff', tubeBack2: '#000000', tubeBackGradient: 0, glassHi: '#545c4d',
  glassBody: 0, glassHiBright: 0.08, glassReflect: 0.58, glassRim: 0.63, glassWall: 4.5, glassWallGlow: 0,
  rimLight: 0, rimTint: '#000000', glassOverLiquid: 0.75, lens: -0.2, lensCurve: 0.2, bubbleRim: '#ffffff',
  highlightH: 0, highlightBright: 0.35, highlightSharp: 2, highlightInset: 0, shadeDepth: 0.31,
  liquidThin: 0.42, contactAngle: 77.0824, contactHyst: 10.5, contactDyn: 8, capLength: 2.7,
  meniscusLens: 0.05, meniscusK: 685, meniscusDamp: 38, meniscusInertia: 5.6, wetFilm: 16, traces: false,
  traceAmount: 0, traceDry: 1.15, traceStain: 1, traceFilm: 0, edgeSoft: 4,
  frontBright: 0, surfaceBand: 0.1, surfaceRim: 0.2, surfaceWidth: 6, surfaceTone: 0.05, surfaceFill: 1,
  surfaceBlick: 0, edgeGlow: 0, glowStrength: 0, cornerR: 0, edgeLightGain: 0.55, bubble: false, bubbleW: 27,
  bubbleH: 20, bubbleGap: 28, bubbleY: 0.28, bubbleRollGain: 0.5, bubbleTiltGain: 14, bubbleDark: 0.06,
  ticksH: true, tickStepH: 1, tickMajorEveryH: 0, tickMinorHeightH: 25, tickMajorHeightH: 22,
  tickMinorWidthH: 2, tickMajorWidthH: 3, tickColorH: '#372e0b', tickMajorColorH: '#4d4d4d', tickPosH: 2,
  ticksM: true, tickStepM: 5, tickMajorEveryM: 0, tickMinorHeightM: 25, tickMajorHeightM: 28,
  tickMinorWidthM: 2, tickMajorWidthM: 2, tickColorM: '#372e0b', tickMajorColorM: '#4d4d4d', tickPosM: 2,
  ticksOnTop: false, tickLens: 0.85, tickParallax: 6, tickDryLens: 1, tickEmboss: 0.4, digits: true,
  digitColor: '#e3e3e3', digitColor2: '#20312f', digitShadow: true, digitShadowColor: '#121212',
  digitShadowStrength: 0.5, digitShadowOffset: 1, digitFont: 7, digitTint: '#3a2308', digitTintAmount: 0.65,
  digitTone: -0.4, digitScaleX: 3.5, digitScaleY: 2.75, digitScaleXMin: 3, digitScaleYMin: 2.75,
  digitBottomMin: 21, digitBottom: 22, digitsOnTop: false, bottomLens: 0.5, digitDryLens: 0.1, topLens: 0.35,
  topParallax: -10, digitParallax: 5.5, liquidTransparency: 0.92, markContrast: 0, digitsLeadingZero: false,
  digitMinuteStep: 5, digitHourStep: 1, digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false,
  digitsLastOnlyM: false, freeLiquid: true, freeGain: 840, freeDamp: 7, freeBounce: 0, freeHomeK: 0,
  readTiltStart: 0, readTiltEnd: 1, playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207,
  angleDamp: 17.6, angleTiltGain: 6.5, angleGyroGain: 0.42, angleMax: 6, lightPhys: 1, lightAngle: 31,
  acrossK: 200, acrossDamp: 20, acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5,
  gyroDeadzone: 31, gyroMax: 470, inputGain: 1, brightness: 1, liquidBright: 0.51, tickBright: 2,
  digitBright: 2, ambientLight: 1,
};

/** Glycerol on white (zip glycerin, 2026-09-23): colourless viscous liquid on white with a coating residue. */
const PRESET_GLYCEROL: Partial<Params> = {
  tubeHeight: 54, hoursY: 0, minutesY: 185, remaining: true, liquid: '#878787', liquidHi: '#878787',
  liquidLo: '#575757', tubeBack: '#ffffff', tubeBack2: '#000000', tubeBackGradient: 0, glassHi: '#545c4d',
  glassBody: 0, glassHiBright: 0, glassReflect: 0.58, glassRim: 0.63, glassWall: 4.5, glassWallGlow: 0,
  rimLight: 0, rimTint: '#000000', glassOverLiquid: 0, lens: -0.2, lensCurve: 0.2, bubbleRim: '#2f3f0d',
  highlightH: 1, highlightBright: 0.35, highlightSharp: 2, highlightInset: 0, shadeDepth: 0.31,
  liquidThin: 0.42, contactAngle: 72.8328, contactHyst: 10.5, contactDyn: 8, capLength: 2.7,
  meniscusLens: 0.05, meniscusK: 685, meniscusDamp: 38, meniscusInertia: 5.6, wetFilm: 16, traces: true,
  traceAmount: 0.35, traceDry: 1.15, traceStain: 1, traceFilm: 0.21,
  edgeSoft: 4, frontBright: 14, surfaceBand: 0.25, surfaceRim: 0.95, surfaceWidth: 4, surfaceTone: -0.05,
  surfaceFill: 1, surfaceBlick: 0, edgeGlow: 0, glowStrength: 0, cornerR: 0, edgeLightGain: 0.55,
  bubble: false, bubbleW: 27, bubbleH: 20, bubbleGap: 28, bubbleY: 0.28, bubbleRollGain: 0.5,
  bubbleTiltGain: 14, bubbleDark: 0, ticksH: true, tickStepH: 1, tickMajorEveryH: 0, tickMinorHeightH: 25,
  tickMajorHeightH: 22, tickMinorWidthH: 2, tickMajorWidthH: 3, tickColorH: '#372e0b',
  tickMajorColorH: '#4d4d4d', tickPosH: 2, ticksM: true, tickStepM: 5, tickMajorEveryM: 0,
  tickMinorHeightM: 25, tickMajorHeightM: 28, tickMinorWidthM: 2, tickMajorWidthM: 2, tickColorM: '#372e0b',
  tickMajorColorM: '#4d4d4d', tickPosM: 2, ticksOnTop: false, tickLens: 0.85, tickParallax: 6, tickDryLens: 1,
  tickEmboss: 0.4, digits: true, digitColor: '#e3e3e3', digitColor2: '#20312f', digitShadow: true,
  digitShadowColor: '#121212', digitShadowStrength: 0.5, digitShadowOffset: 1, digitFont: 7,
  digitTint: '#3a2308', digitTintAmount: 0.65, digitTone: -0.4, digitScaleX: 3.5, digitScaleY: 2.75,
  digitScaleXMin: 3, digitScaleYMin: 2.75, digitBottomMin: 21, digitBottom: 22, digitsOnTop: false,
  bottomLens: 0.45, digitDryLens: 0.1, topLens: 0.35, topParallax: -10, digitParallax: 4.75,
  liquidTransparency: 0.81, markContrast: 0, digitsLeadingZero: false, digitMinuteStep: 5, digitHourStep: 1,
  digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false, digitsLastOnlyM: false, freeLiquid: true,
  freeGain: 840, freeDamp: 7, freeBounce: 0, freeHomeK: 0, readTiltStart: 0, readTiltEnd: 1, playHold: 5,
  fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207, angleDamp: 17.6, angleTiltGain: 6.5,
  angleGyroGain: 0.42, angleMax: 6, lightPhys: 1, lightAngle: 31, acrossK: 200, acrossDamp: 20,
  acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5, gyroDeadzone: 31, gyroMax: 470,
  inputGain: 1, brightness: 1, liquidBright: 0, tickBright: 2, digitBright: 2, ambientLight: 1,
};

/** Dark glycerol (2026-09-27, user export): smoky grey viscous liquid on a pale sage backing, rim-lit, dark rear
 *  numerals, a slow clinging coat; its signature gas (trapped) is the one it was saved with. */
const PRESET_GLYCEROL_DARK: Partial<Params> = {
  tubeHeight: 54, hoursY: 0, minutesY: 185, remaining: false, liquid: '#2d2d2d', liquidHi: '#bcbcbc',
  liquidLo: '#0e0e0e', tubeBack: '#babbaa', tubeBack2: '#000000', tubeBackGradient: 0, glassHi: '#dfe6ea',
  glassBody: 0.08, glassHiBright: 0.2612, glassReflect: 0.1187, glassRim: 0.6162, glassWall: 4.8182,
  glassWallGlow: 0.2678, rimLight: 1, rimTint: '#6d6b6a', glassOverLiquid: 0.5002, lens: -0.2, lensCurve: 0.2,
  bubbleRim: '#b4b4b4', highlightH: 6, highlightBright: 1, highlightSharp: 2, highlightInset: 0,
  shadeDepth: 0.3, liquidThin: 1, contactAngle: 20, contactHyst: 12, contactDyn: 90, capLength: 2.2131,
  meniscusLens: 0.05, meniscusK: 105.7451, meniscusDamp: 28.1531, meniscusInertia: 1.8478, wetFilm: 24.534,
  traces: true, traceAmount: 0.3317, traceDry: 2, traceStain: 0.18,
  traceFilm: 0.01, edgeSoft: 2.4, frontBright: 0, surfaceBand: 0.35, surfaceRim: 0.45, surfaceWidth: 4,
  surfaceTone: 0, surfaceFill: 0.1838, surfaceBlick: 0.9, edgeGlow: 19, glowStrength: 0.0726, cornerR: 0,
  edgeLightGain: 0.55, bubble: false, bubbleW: 16, bubbleH: 19, bubbleGap: 22, bubbleY: 0.2,
  bubbleRollGain: 0.5, bubbleTiltGain: 0, bubbleDark: 0.33, ticksH: true, tickStepH: 1, tickMajorEveryH: 0,
  tickMinorHeightH: 25, tickMajorHeightH: 22, tickMinorWidthH: 2, tickMajorWidthH: 3, tickColorH: '#372e0b',
  tickMajorColorH: '#4d4d4d', tickPosH: 2, ticksM: true, tickStepM: 5, tickMajorEveryM: 0,
  tickMinorHeightM: 25, tickMajorHeightM: 28, tickMinorWidthM: 2, tickMajorWidthM: 2, tickColorM: '#372e0b',
  tickMajorColorM: '#4d4d4d', tickPosM: 2, ticksOnTop: false, tickLens: 0.6405, tickParallax: 6,
  tickDryLens: 1, tickEmboss: 0.4, digits: true, digitColor: '#e3e3e3', digitColor2: '#20312f',
  digitShadow: true, digitShadowColor: '#121212', digitShadowStrength: 0.5, digitShadowOffset: 1, digitFont: 7,
  digitTint: '#3a2308', digitTintAmount: 0.65, digitTone: -0.4, digitScaleX: 3.5, digitScaleY: 2.75,
  digitScaleXMin: 3, digitScaleYMin: 2.75, digitBottomMin: 21, digitBottom: 22, digitsOnTop: false,
  bottomLens: 0.6405, digitDryLens: 0.1, topLens: 0.35, topParallax: -10, digitParallax: 4.75,
  liquidTransparency: 0.65, markContrast: 36, digitsLeadingZero: false, digitMinuteStep: 5, digitHourStep: 1,
  digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false, digitsLastOnlyM: false, freeLiquid: true,
  freeGain: 570, freeDamp: 6.8074, freeBounce: 0, freeHomeK: 0, readTiltStart: 0, readTiltEnd: 1, playHold: 5,
  fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207, angleDamp: 17.6, angleTiltGain: 2.2309,
  angleGyroGain: 0.1039, angleMax: 6, lightPhys: 1, lightAngle: 30, acrossK: 200, acrossDamp: 20,
  acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5, gyroDeadzone: 31, gyroMax: 470,
  inputGain: 1, brightness: 1, liquidBright: 1, tickBright: 1.27, digitBright: 1.12, ambientLight: 0,
};

/** Prosecco (zip realistic_with_gas, 2026-09-26): pale straw on white, derived from a physical material (Params as derived today). */
const PRESET_PROSECCO: Partial<Params> = {
  tubeHeight: 54, hoursY: 0, minutesY: 185, remaining: false, liquid: '#ffe6b3', liquidHi: '#ffffff',
  liquidLo: '#000000', tubeBack: '#ffffff', tubeBack2: '#000000', tubeBackGradient: 0, glassHi: '#dfe6ea',
  glassBody: 0.08, glassHiBright: 0.2655, glassReflect: 0.1207, glassRim: 0.619, glassWall: 4.8182,
  glassWallGlow: 0.2577, rimLight: 1, rimTint: '#0c0f15', glassOverLiquid: 0.5314, lens: -0.2, lensCurve: 0.2,
  bubbleRim: '#b4b2ad', highlightH: 6, highlightBright: 1, highlightSharp: 2, highlightInset: 0,
  shadeDepth: 0.4, liquidThin: 1, contactAngle: 20, contactHyst: 10, contactDyn: 10.1656, capLength: 2.2069,
  meniscusLens: 0.05, meniscusK: 400, meniscusDamp: 9.718, meniscusInertia: 2.9578, wetFilm: 12.7417,
  traces: false, traceAmount: 0.3, traceDry: 1, traceStain: 0.05,
  traceFilm: 0, edgeSoft: 2.4, frontBright: 0, surfaceBand: 0.35, surfaceRim: 0.45, surfaceWidth: 4,
  surfaceTone: 0, surfaceFill: 0.505, surfaceBlick: 0.9, edgeGlow: 19, glowStrength: 0.044, cornerR: 0,
  edgeLightGain: 0.55, bubble: false, bubbleW: 16, bubbleH: 19, bubbleGap: 22, bubbleY: 0.2,
  bubbleRollGain: 0.5, bubbleTiltGain: 0, bubbleDark: 0.0439, ticksH: true, tickStepH: 1, tickMajorEveryH: 0,
  tickMinorHeightH: 25, tickMajorHeightH: 22, tickMinorWidthH: 2, tickMajorWidthH: 3, tickColorH: '#372e0b',
  tickMajorColorH: '#4d4d4d', tickPosH: 2, ticksM: true, tickStepM: 5, tickMajorEveryM: 0,
  tickMinorHeightM: 25, tickMajorHeightM: 28, tickMinorWidthM: 2, tickMajorWidthM: 2, tickColorM: '#372e0b',
  tickMajorColorM: '#4d4d4d', tickPosM: 2, ticksOnTop: false, tickLens: 0.473, tickParallax: 6, tickDryLens: 1,
  tickEmboss: 0.4, digits: true, digitColor: '#e3e3e3', digitColor2: '#20312f', digitShadow: true,
  digitShadowColor: '#121212', digitShadowStrength: 0.5, digitShadowOffset: 1, digitFont: 7,
  digitTint: '#3a2308', digitTintAmount: 0.65, digitTone: -0.4, digitScaleX: 3.5, digitScaleY: 2.75,
  digitScaleXMin: 3, digitScaleYMin: 2.75, digitBottomMin: 21, digitBottom: 22, digitsOnTop: false,
  bottomLens: 0.473, digitDryLens: 0.1, topLens: 0.35, topParallax: -10, digitParallax: 4.75,
  liquidTransparency: 0.55, markContrast: 0, digitsLeadingZero: false, digitMinuteStep: 5, digitHourStep: 1,
  digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false, digitsLastOnlyM: false, freeLiquid: true,
  freeGain: 570, freeDamp: 0.9718, freeBounce: 0.1686, freeHomeK: 0, readTiltStart: 0, readTiltEnd: 1,
  playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207, angleDamp: 17.6,
  angleTiltGain: 6.0705, angleGyroGain: 0.3856, angleMax: 6, lightPhys: 1, lightAngle: 30, acrossK: 200,
  acrossDamp: 20, acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5, gyroDeadzone: 31,
  gyroMax: 470, inputGain: 1, brightness: 0.63, liquidBright: 1, tickBright: 1.05, digitBright: 1.73,
  ambientLight: 0,
};

/** Subtle soda (user config, 2026-09-28): muted lime over warm grey, a spring of large pearls at the home end
 *  (gas 'spring-pearls'), see-through dish. */
const PRESET_SUBTLE_SODA: Partial<Params> = {
  tubeHeight: 54, hoursY: 0, minutesY: 185, remaining: false, liquid: '#98ff5a', liquidHi: '#aab98d',
  liquidLo: '#1e501b', tubeBack: '#cbcbb3', tubeBack2: '#000000', tubeBackGradient: 0, glassHi: '#dfe6ea',
  glassBody: 0.19, glassHiBright: 0.3283, glassReflect: 0.1492, glassRim: 0.38, glassWall: 6.5,
  glassWallGlow: 0.25, rimLight: 0.67, rimTint: '#000000', glassOverLiquid: 0.18, lens: -0.2, lensCurve: 0.2,
  bubbleRim: '#b8ccad', highlightH: 8, highlightBright: 0.05, highlightSharp: 2, highlightInset: 0,
  shadeDepth: 0.4, liquidThin: 1, contactAngle: 70, contactHyst: 9, contactDyn: 5.1794, capLength: 5.4,
  meniscusLens: 0.05, meniscusK: 550, meniscusDamp: 8.8728, meniscusInertia: 2.9786, wetFilm: 8, traces: true,
  traceAmount: 0.4377, traceDry: 1, traceStain: 0.167,
  traceFilm: 0.0002, edgeSoft: 2.4, frontBright: 0, surfaceBand: 0.35, surfaceRim: 0.45, surfaceWidth: 4,
  surfaceTone: 0, surfaceFill: 0.505, surfaceBlick: 0.9, edgeGlow: 19, glowStrength: 0.055, cornerR: 0,
  edgeLightGain: 0.55, bubble: false, bubbleW: 16, bubbleH: 19, bubbleGap: 22, bubbleY: 0.2,
  bubbleRollGain: 0.5, bubbleTiltGain: 0, bubbleDark: 0, ticksH: true, tickStepH: 1, tickMajorEveryH: 0,
  tickMinorHeightH: 15, tickMajorHeightH: 22, tickMinorWidthH: 2, tickMajorWidthH: 3, tickColorH: '#372e0b',
  tickMajorColorH: '#4d4d4d', tickPosH: 2, ticksM: true, tickStepM: 5, tickMajorEveryM: 0,
  tickMinorHeightM: 15, tickMajorHeightM: 28, tickMinorWidthM: 2, tickMajorWidthM: 2, tickColorM: '#372e0b',
  tickMajorColorM: '#4d4d4d', tickPosM: 2, ticksOnTop: false, tickLens: 0.473, tickParallax: 5.5,
  tickDryLens: 0.1, tickEmboss: 0.25, digits: true, digitColor: '#e3e3e3', digitColor2: '#20312f',
  digitShadow: true, digitShadowColor: '#5c5c5c', digitShadowStrength: 0.7, digitShadowOffset: 2, digitFont: 7,
  digitTint: '#483c0f', digitTintAmount: 0.6, digitTone: -0.6, digitScaleX: 3.5, digitScaleY: 2.75,
  digitScaleXMin: 3, digitScaleYMin: 2.75, digitBottomMin: 20, digitBottom: 19, digitsOnTop: false,
  bottomLens: 0.473, digitDryLens: 0.1, topLens: 0.35, topParallax: -10, digitParallax: 4.75,
  liquidTransparency: 0.67, markContrast: 26, digitsLeadingZero: false, digitMinuteStep: 5, digitHourStep: 1,
  digitHourStart: 0, digitMinuteStart: 0, digitsLastOnlyH: false, digitsLastOnlyM: false, freeLiquid: true,
  freeGain: 570, freeDamp: 0.8873, freeBounce: 0.3197, freeHomeK: 0, readTiltStart: 0, readTiltEnd: 1,
  playHold: 5, fillK: 756, fillDamp: 40, fillSloshGain: 5.5, angleK: 207, angleDamp: 17.6,
  angleTiltGain: 6.2818, angleGyroGain: 0.4025, angleMax: 6, lightPhys: 1, lightAngle: 22.5, acrossK: 200,
  acrossDamp: 20, acrossGyroGain: 0, shakeGain: 0, deadzone: 0, accelLpHz: 15.2, gyroHpHz: 5, gyroDeadzone: 31,
  gyroMax: 470, inputGain: 1, brightness: 1, liquidBright: 0.46, tickBright: 0.92, digitBright: 1.51,
  ambientLight: 1,
};

export const PRESETS: PresetEntry[] = [
  { id: 'frizzante', name: 'Frizzante', note: 'colourless sparkling water, lab print, fine bead', p: PRESET_FRIZZANTE, gas: gases('fine-bead', SODA), mat: M('watery', 'clear', false, true, 'carbonated') },
  { id: 'urine', name: 'Urine sample', note: 'clear amber, watery, specimen-cup graduations', p: PRESET_URINE, gas: gases('none', SODA, ['slow-bubbles']), mat: M('watery', 'translucent', false, true, 'none') },
  { id: 'blood', name: 'Blood', note: 'opaque venous red, coats the glass, syringe print', p: PRESET_BLOOD, gas: gases('none', OILY), mat: M('medium', 'opaque', false, true, 'none') },
  { id: 'milk', name: 'Milk', note: 'opaque white colloid, soft highlight, printed scale', p: PRESET_MILK, gas: gases('none', OILY), mat: M('medium', 'opaque', false, true, 'none') },
  { id: 'mercury', name: 'Mercury', note: 'convex bead, mirror specular, etched scale', p: PRESET_MERCURY, gas: gases('none'), mat: M('metal', 'opaque', false, false, 'none') },
  { id: 'honey', name: 'Honey', note: 'amber syrup, overdamped, clings, trapped air', p: PRESET_HONEY, gas: gases('held-air', ['trapped']), mat: M('viscous', 'translucent', false, true, 'trapped') },
  { id: 'olive-oil', name: 'Olive oil', note: 'user-tuned olive green, viscous slug, lingering residue', p: PRESET_OLIVE_OIL, gas: gases('none', OILY) },
  { id: 'cola', name: 'Cola', note: 'dark translucent, lively bead, enamel numerals', p: PRESET_COLA, gas: gases('lively-bead', SODA), mat: M('watery', 'translucent', false, true, 'carbonated') },
  { id: 'malt', name: 'Single malt', note: 'amber, legs on the wall, brass numerals', p: PRESET_MALT, gas: gases('none', SODA), mat: M('medium', 'translucent', false, true, 'none') },
  { id: 'champagne', name: 'Champagne', note: 'pale gold, dense bead, amber resin numerals', p: PRESET_CHAMPAGNE, gas: gases('fine-bead', SODA), mat: M('watery', 'translucent', false, true, 'carbonated') },
  { id: 'cryo', name: 'Cryo oxygen', note: 'pale blue, boiling, frosted wall', p: PRESET_CRYO, gas: gases('boiling', ['fine-bead']), mat: M('watery', 'clear', false, true, 'boiling') },
  { id: 'ink', name: 'India ink', note: 'matte black, enamel numerals, panel mostly off', p: PRESET_INK, gas: gases('none', ['slow-bubbles']), mat: M('medium', 'opaque', false, true, 'none') },
  { id: 'glow', name: 'Glow stick', note: 'fluorescent green, glows past the cap, seven-segment print', p: PRESET_GLOW, gas: gases('none', ['sparks', 'slow-bubbles']), mat: M('medium', 'translucent', true, true, 'none') },
  { id: 'xenon', name: 'Xenon', note: 'violet discharge tube, glowing ends, no inertia', p: PRESET_XENON, gas: gases('none'), mat: M('plasma', 'translucent', true, false, 'none') },
  { id: 'molten', name: 'Molten iron', note: 'emissive orange, dense, non-wetting, forged numerals', p: PRESET_MOLTEN, gas: gases('gas-pockets'), mat: M('medium', 'opaque', true, false, 'trapped') },
  { id: 'free', name: 'Free liquid', note: 'bottle green slug; gentle tilt reads time, strong tilt flows', p: PRESET_FREE, gas: gases('slow-bubbles', SODA) },
];
// The original signatures also have big-rod variants; later additions are single standard-rod looks.
PRESETS.push(...PRESETS.map((e) => ({ ...e, id: e.id + '-big', name: e.name + ' (big lens)', p: bigLens(e.p), big: true })));
PRESETS.push({ id: 'phosphor', name: 'Phosphor sample', note: 'pale green solution in a clear lab vial on white paper, see-through meniscus, marker labels on the glass', p: PRESET_PHOSPHOR, gas: gases('none', SODA, ['sparks']), mat: M('watery', 'translucent', false, true, 'none') });
PRESETS.push({ id: 'alpine', name: 'Alpine spring', note: 'clear sparkling water, pale ceramic backing, slate markings', p: PRESET_ALPINE, gas: gases('fine-bead', SODA), mat: M('watery', 'clear', false, true, 'carbonated') });
PRESETS.push({ id: 'pinot', name: 'Pinot noir', note: 'ruby red wine, legs on the glass, bronze cellar numerals', p: PRESET_PINOT, gas: gases('none', SODA) });
PRESETS.push({ id: 'spritz', name: 'Aperol spritz', note: 'vivid orange aperitivo, lively bead with a foam ring, navy enamel numerals on white', p: PRESET_SPRITZ, gas: gases('foam-ring', SODA) });

PRESETS.push({ id: 'cuvee', name: 'Cuvée', note: 'straw-gold sparkling wine, ivory backing, bronze numerals and a fine pale bead', p: PRESET_CUVEE, gas: gases('pearl-bead', SODA) });

PRESETS.push({ id: 'nocturne', name: 'Nocturne', note: 'blue-black ink, smoked glass, silver front markings and lingering wet residue', p: PRESET_NOCTURNE, gas: gases('none', ['slow-bubbles']), mat: M('medium', 'opaque', false, true, 'none') });
PRESETS.push({ id: 'tide', name: 'Bioluminescent tide', note: 'night-sea water glowing cyan at the edge, drifting plankton sparks, steel marks behind black glass', p: PRESET_TIDE, gas: gases('sparks', SODA) });
// User looks recovered from presets.zip (2026-09-27): standard rod, exempt from the material ranges.
PRESETS.push(
  { id: 'absinthe', name: 'Absinthe', note: 'vivid green on white in the widest tubes, large black rear numerals', p: PRESET_ABSINTHE, gas: gases('pearl-bead', SODA) },
  { id: 'chartreuse', name: 'Chartreuse', note: 'bright yellow-green on black, soft glowing edge, bronze rear numerals', p: PRESET_CHARTREUSE, gas: gases('slow-bubbles', SODA) },
  { id: 'bottle', name: 'Bottle green', note: 'dark green in 80 px tubes on charcoal, faint rear numerals, coating residue', p: PRESET_BOTTLE, gas: gases('large-bubbles', SODA, ['slow-bubbles']) },
  { id: 'claret', name: 'Claret', note: 'near-opaque dark red draining right, light numerals on white', p: PRESET_CLARET, gas: gases('slow-bubbles', SODA) },
  { id: 'olive-white', name: 'Olive oil on white', note: 'the tuned olive oil drained from the right over a white backing, heavy residue', p: PRESET_OLIVE_WHITE, gas: gases('slow-bubbles', OILY) },
  { id: 'menthe', name: 'Menthe', note: 'translucent teal on white, dark rear numerals', p: PRESET_MENTHE, gas: gases('foam-ring', SODA) },
  { id: 'lime', name: 'Lime soda', note: 'pale lime over white, hand-tuned physical export', p: PRESET_LIME, gas: gases('brisk-pearls', SODA) },
  { id: 'patrick', name: 'Patrick pink', note: 'opaque bubblegum pink, yellow print on the glass', p: PRESET_PATRICK, gas: gases('none', OILY) },
  { id: 'seltzer', name: 'Seltzer', note: 'colourless water on white, the reference glass for Cuvée', p: PRESET_SELTZER, gas: gases('pearl-bead', SODA) },
  { id: 'glycerol', name: 'Glycerol on white', note: 'colourless viscous liquid on white, coating residue', p: PRESET_GLYCEROL, gas: gases('large-bubbles', ['trapped', 'held-air']) },
  { id: 'glycerol-dark', name: 'Dark glycerol', note: 'smoky grey viscous liquid on pale sage, rim-lit, dark rear numerals', p: PRESET_GLYCEROL_DARK, gas: gases('trapped', ['large-bubbles', 'held-air']) },
  { id: 'prosecco', name: 'Prosecco', note: 'pale straw on white, from a physical material', p: PRESET_PROSECCO, gas: gases('brisk-pearls', SODA) },
);
// User look (2026-09-28): standard rod, exempt from the material ranges.
PRESETS.push({ id: 'subtle-soda', name: 'Subtle soda', note: 'muted lime over warm grey, a spring of large pearls rising from the home end, see-through dish', p: PRESET_SUBTLE_SODA, gas: gases('spring-pearls', SODA) });

/** Presets are whole looks: apply over the defaults, not over the current edit. `gas` defaults to the
 *  preset's signature (its first fitting model). */
export function presetParams(e: PresetEntry, gas: GasId = e.gas[0]): Params {
  const p = { ...structuredClone(DEFAULT_PARAMS), ...e.p, ...gasParams(gas) };
  // hand-made presets carry no material: their film's drain speed follows from their own contact params
  if (!('traceDrain' in e.p)) p.traceDrain = legacyTraceDrain(p);
  return p;
}

export type ParamKey = keyof Params;

/** Params with a px dimension (sizes, px/s speeds, px/g and px/s² gains, glyph scales): presets, the panel, the
 *  device's NVS and `p` writes hold them in design px (spec/layout DESIGN_H); boardParams scales them to the
 *  board's canvas. firmware/tools/gen_params.py reads this list for the firmware's copy (PARAM_PX). */
export const PX_KEYS = [
  'tubeHeight', 'hoursY', 'minutesY', 'glassWall', 'highlightH', 'highlightInset', 'wetFilm', 'traceDrain',
  'edgeSoft', 'frontBright', 'surfaceWidth', 'edgeGlow', 'cornerR',
  'bubbleW', 'bubbleH', 'bubbleGap', 'bubbleTiltGain', 'fizzSize', 'fizzSpeed', 'fizzSourceSpread',
  'tickMinorHeightH', 'tickMajorHeightH', 'tickMinorWidthH', 'tickMajorWidthH',
  'tickMinorHeightM', 'tickMajorHeightM', 'tickMinorWidthM', 'tickMajorWidthM', 'tickParallax',
  'digitShadowOffset', 'digitScaleX', 'digitScaleY', 'digitScaleXMin', 'digitScaleYMin', 'digitBottomMin', 'digitBottom',
  'topParallax', 'digitParallax', 'freeGain', 'fillSloshGain', 'angleGyroGain',
] as const satisfies readonly ParamKey[];
/** The PX_KEYS that are whole pixels by design (positions and sizes on a 1 px slider step): rounded after scaling,
 *  so a preset's rows, ticks, baselines and offsets stay on the pixel grid (the renderer takes them as integers). */
export const PX_WHOLE_KEYS: readonly (typeof PX_KEYS)[number][] = [
  'tubeHeight', 'hoursY', 'minutesY', 'highlightH', 'highlightInset', 'frontBright', 'edgeGlow', 'cornerR',
  'bubbleW', 'bubbleH', 'bubbleGap', 'tickMinorHeightH', 'tickMajorHeightH', 'tickMinorWidthH', 'tickMajorWidthH',
  'tickMinorHeightM', 'tickMajorHeightM', 'tickMinorWidthM', 'tickMajorWidthM', 'digitShadowOffset', 'digitBottomMin', 'digitBottom',
];

/** The params the renderer and physics run on: `p` (design px) with every PX_KEYS field scaled by the board's
 *  PX_SCALE, PX_WHOLE_KEYS rounded. The AMOLED (scale 1) gets `p` itself. Mirrored by firmware main.cpp. */
export function boardParams(p: Params): Params {
  if (PX_SCALE === 1) return p;
  const o = { ...p };
  for (const k of PX_KEYS) o[k] = Math.fround(Math.fround(p[k]) * Math.fround(PX_SCALE));   // float32 product, as the firmware scales
  for (const k of PX_WHOLE_KEYS) o[k] = Math.round(o[k]);
  return o;
}

/** Map keys from older exports (shared tick settings, digitScale, digitFontBig) onto the current schema. */
export function migrateParams(o: Record<string, unknown>): Partial<Params> {
  const r: Record<string, unknown> = { ...o };
  const from = typeof r.v === 'number' ? r.v : 1;
  if ('glass' in r) { if (!('tubeBack' in r)) r.tubeBack = r.glass; delete r.glass; }
  if ('ticks' in r) { r.ticksH = r.ticksM = r.ticks; delete r.ticks; }
  if ('tickMajorH' in r) { r.tickMajorHeightH = r.tickMajorHeightM = r.tickMajorH; delete r.tickMajorH; }
  if ('tickMinorH' in r) { r.tickMinorHeightH = r.tickMinorHeightM = r.tickMinorH; delete r.tickMinorH; }
  if ('tick' in r) { r.tickColorH = r.tickColorM = r.tickMajorColorH = r.tickMajorColorM = r.tick; delete r.tick; }
  if ('digitScale' in r) { r.digitScaleX = r.digitScaleY = r.digitScaleXMin = r.digitScaleYMin = r.digitScale; delete r.digitScale; }
  if ('digitFontBig' in r) { r.digitFont = r.digitFontBig ? 2 : 0; delete r.digitFontBig; }
  if ('tickLayer' in r) { r.ticksOnTop = r.tickLayer === 1; delete r.tickLayer; }
  if (!('tickLens' in r) && typeof r.bottomLens === 'number') r.tickLens = r.bottomLens;
  // older presets: same warp behind air as behind liquid, as before
  if (!('tickDryLens' in r) && typeof r.tickLens === 'number') r.tickDryLens = r.tickLens;
  if (!('digitDryLens' in r) && typeof r.bottomLens === 'number') r.digitDryLens = r.bottomLens;
  // older presets: rear digits refract like the rear ticks
  if (!('digitParallax' in r) && typeof r.tickParallax === 'number') r.digitParallax = r.tickParallax;
  if (from < 2) {
    // v1 counted "major every N-th minor tick"; v2 counts units (hours / minutes).
    for (const [every, step] of [['tickMajorEveryH', 'tickStepH'], ['tickMajorEveryM', 'tickStepM']] as const) {
      const e = r[every], k = r[step] ?? 1;
      if (typeof e === 'number' && typeof k === 'number') r[every] = e * k;
    }
  }
  if (from < 3) {
    // v3 re-modelled the liquid as capillary-pinned: hard caps in physics.ts plus much softer
    // response defaults. Old physics/IMU tunings produced runaway visuals on real accelerometer
    // input, so drop them and fall back to the new defaults instead of carrying them over.
    for (const k of ['fillK', 'fillDamp', 'fillSloshGain', 'angleK', 'angleDamp', 'angleTiltGain',
      'angleGyroGain', 'angleMax', 'acrossK', 'acrossDamp', 'acrossGyroGain', 'shakeGain', 'deadzone', 'accelLpHz', 'gyroHpHz',
      'gyroDeadzone', 'gyroMax', 'inputGain']) delete r[k];
  }
  // Gesture thresholds/timers have no angle equivalent. Old exports get the new viewing band.
  if (from < 16) {
    r.readTiltStart = DEFAULT_PARAMS.readTiltStart;
    r.readTiltEnd = DEFAULT_PARAMS.readTiltEnd;
  }
  if (from < 17) r.playHold = DEFAULT_PARAMS.playHold;
  if (from < 19) { r.surfaceBand = DEFAULT_PARAMS.surfaceBand; r.surfaceRim = DEFAULT_PARAMS.surfaceRim; r.surfaceWidth = DEFAULT_PARAMS.surfaceWidth; r.surfaceTone = DEFAULT_PARAMS.surfaceTone; }
  if (from < 20) { r.fizzEdgeRise = DEFAULT_PARAMS.fizzEdgeRise; r.fizzFoamLife = DEFAULT_PARAMS.fizzFoamLife; }
  if (from < 21) { r.surfaceFill = DEFAULT_PARAMS.surfaceFill; r.surfaceBlick = DEFAULT_PARAMS.surfaceBlick; }
  if (from < 22) {
    // v22: the meniscus is a contact-angle model. The old wall climb maps onto the angle whose spherical
    // cap has that depth (h = R·tan(45° − θ/2)); the old px-per-speed lag onto the hysteresis band.
    const D = r.meniscusDepth, lag = r.contactLag, H = typeof r.tubeHeight === 'number' ? r.tubeHeight : DEFAULT_PARAMS.tubeHeight;
    if (typeof D === 'number') r.contactAngle = 90 - 2 * Math.atan(D / Math.max(1, (H - 1) / 2)) * 180 / Math.PI;
    // …kept on its side of 90°, so a shallow old dish cannot turn over under tilt
    const a = typeof r.contactAngle === 'number' ? r.contactAngle : DEFAULT_PARAMS.contactAngle;
    if (typeof lag === 'number') r.contactHyst = Math.max(0, Math.min(25, lag * 6, Math.abs(90 - a) - 1));
  }
  if (from < 23) { r.fizzDepth = DEFAULT_PARAMS.fizzDepth; r.fizzBlick = DEFAULT_PARAMS.fizzBlick; }
  if (from < 24) { r.rimLight = DEFAULT_PARAMS.rimLight; r.rimTint = DEFAULT_PARAMS.rimTint; }
  if (from < 25) r.wallWet = DEFAULT_PARAMS.wallWet;
  // v26: the deposit follows the film law (filmEta), so the inverted speed-thinning knob traceThin is gone.
  // v27: the artistic drain-back rate traceFollow gives way to the film's physical drain speed traceDrain,
  // here from the preset's own contact params (legacyTraceDrain)
  if (from < 27 && !('traceDrain' in r)) r.traceDrain = legacyTraceDrain({ ...DEFAULT_PARAMS, ...r } as Params);
  for (const k of Object.keys(r)) if (!(k in DEFAULT_PARAMS)) delete r[k];
  r.v = PARAMS_VERSION;
  return r as Partial<Params>;
}

/** UI metadata: [min, max, step] for numeric params; grouping for the panel. */
export const PARAM_META: Record<string, { group: string; label?: string; help?: string; min?: number; max?: number; step?: number; options?: readonly string[] }> = {
  liquid: { help: 'Body colour of the liquid.', group: 'Colour' }, liquidHi: { help: 'Specular highlight strip colour.', group: 'Colour' }, liquidLo: { help: 'Bottom shade colour (cylinder shading).', group: 'Colour' },
  tubeBack: { help: 'First tube-back colour. #000000 = AMOLED pixels off when the gradient is Solid.', group: 'Colour', label: 'tube back colour 1' },
  tubeBack2: { help: 'Second colour used by the tube-back gradient.', group: 'Colour', label: 'tube back colour 2' },
  tubeBackGradient: {
    help: 'Fast two-colour gradient across the short axis of the tube. It is folded into the existing per-row colour table.',
    group: 'Colour', label: 'tube back gradient', min: 0, max: 3, step: 1,
    options: ['Solid colour 1', 'Colour 1 → colour 2', 'Colour 2 centre band', 'Colour 2 edge bands'],
  },
  bubbleRim: { help: 'Rim colour of the spirit-level bubble and fizz.', group: 'Colour' },
  glassHi: { help: 'Specular colour of the glass wall.', group: 'Glass', label: 'specular colour' },
  glassBody: { help: 'Ambient cylinder shade of the empty wall. 0 = pure black.', group: 'Glass', label: 'ambient body', min: 0, max: 0.5, step: 0.01 },
  glassHiBright: { help: 'Strength of the glass specular band (same rows as the liquid highlight).', group: 'Glass', label: 'specular', min: 0, max: 1, step: 0.01 },
  glassReflect: { help: 'Faint second reflection on the lower wall.', group: 'Glass', label: 'lower reflection', min: 0, max: 1, step: 0.01 },
  glassRim: { help: 'Grazing reflection across the wall band: brightest at the silhouette, fading inward. The outer surface reflects it, so it is the same over the liquid.', group: 'Glass', label: 'wall rims', min: 0, max: 1, step: 0.01 },
  glassWall: { help: 'Wall thickness at the top/bottom silhouette in px. Behind it the empty tube shows no tube back (only the rim reflection) and rear marks fade out; the liquid reaches the silhouette.', group: 'Glass', label: 'wall thickness', min: 0, max: 10, step: 0.5 },
  glassWallGlow: { help: 'Light piped along the dry glass lights the wall band itself, so the walls read on a black tube back; over the liquid the band shows the liquid (grazing rim only). Plateau across the band, the grazing rim on top.', group: 'Glass', label: 'wall glow', min: 0, max: 1, step: 0.01 },
  wallWet: { help: 'How far the contents fill the wall band: 1 a liquid, seen to the silhouette with no wall glow over it; 0 a gas, the band over the column looks like the empty tube (wall only, glowing).', group: 'Glass', label: 'wall wetting', min: 0, max: 1, step: 0.01 },
  rimLight: { help: 'Side-lit rim of a tinted liquid on a dark ground: adds rimLight·u²·rimTint to the liquid rows toward the walls (a gain 0..4; the sum clamps at 255).', group: 'Glass', label: 'rim light', min: 0, max: 4, step: 0.01 },
  rimTint: { help: 'Side-lit rim of a tinted liquid on a dark ground: adds rimLight·u²·rimTint to the liquid rows toward the walls.', group: 'Glass', label: 'rim tint' },
  glassOverLiquid: { help: 'How much of the glass specular is laid over the liquid too (not the grazing rim: that stays full).', group: 'Glass', label: 'specular over liquid', min: 0, max: 1, step: 0.01 },
  brightness: { help: 'Global panel dimmer (emulates cmd 0x51).', group: 'Colour', label: 'brightness (panel)', min: 0.1, max: 1, step: 0.01 },
  liquidBright: { help: 'Per-layer trim on top of brightness: liquid body, highlight, shade, bubble, fizz.', group: 'Colour', label: '· liquid trim', min: 0, max: 2, step: 0.01 },
  tickBright: { help: 'Per-layer trim on top of brightness: tick ladder only.', group: 'Colour', label: '· ticks trim', min: 0, max: 2, step: 0.01 },
  digitBright: { help: 'Per-layer trim on top of brightness: digit labels only.', group: 'Colour', label: '· digits trim', min: 0, max: 2, step: 0.01 },
  ambientLight: { help: 'Liquid colours brighter than the diffuse body (highlight band, edge glow, front brightening, fizz rims) desaturate toward neutral grey of the same luma — reflections of white room light instead of the liquid glowing in its own colour. 0 = self-lit (fluorescent) look, 1 = fully ambient-lit. Scaled down by liquidTransparency: a transparent liquid keeps its tint (its bright areas are transmitted, coloured light).', group: 'Colour', label: 'ambient light', min: 0, max: 1, step: 0.01 },
  tubeHeight: { help: 'Across-tube size, px.', group: 'Layout', label: 'tube height', min: 16, max: 80, step: 1 },
  hoursY: { help: 'Top row of the hours tube, px.', group: 'Layout', label: 'hours tube y', min: 0, max: 224, step: 1 },
  minutesY: { help: 'Top row of the minutes tube, px.', group: 'Layout', label: 'minutes tube y', min: 0, max: 224, step: 1 },
  remaining: { help: 'On: liquid sits at the right end and drains as time passes. Off: fills from the left.', group: 'Shape', label: 'liquid = remaining' },
  vertical: { help: 'Watch worn upright, USB end down (hours tube on the left). The liquid always rests at the bottom and the digits are rotated to read upright. "liquid = remaining" then only flips the scale: off = digits run bottom to top and the liquid shows the time passed, on = digits run top to bottom and the liquid shows what is left. Digits are centred across the tube (digit bottom offsets do not apply). Digit scale X / Y swap roles (X stays along the tube).', group: 'Shape', label: 'vertical watch' },
  highlightH: { help: 'Height of the specular strip at the top of the column, px.', group: 'Shape', min: 0, max: 30, step: 1 },
  highlightInset: { help: 'Inset of the highlight from the fill edge, px.', group: 'Shape', min: 0, max: 40, step: 1 },
  highlightBright: { help: 'Strength of the specular band.', group: 'Shape', min: 0, max: 1.5, step: 0.05 },
  highlightSharp: { help: 'Band profile exponent. High = narrow, glossy.', group: 'Shape', min: 0.3, max: 4, step: 0.1 },
  shadeDepth: { help: 'How dark the bottom rows get (cylinder shading).', group: 'Shape', min: 0, max: 1, step: 0.01 },
  liquidThin: { help: 'The liquid lightens and desaturates toward the walls, where the path through the column is short.', group: 'Shape', label: 'thin edge', min: 0, max: 1, step: 0.01 },
  contactAngle: { help: 'Static contact angle of the liquid on the glass, degrees. Sets both ends\' curvature: a spherical cap whose ring leads its centre by R·(1 − sin θ)/cos θ — a hemisphere at 0°, flat at 90°, a convex bead above (mercury ~140°). Water on glass ~20–30°.', group: 'Shape', label: 'contact angle °', min: 0, max: 180, step: 1 },
  contactHyst: { help: 'Contact-angle hysteresis, degrees either side of the static angle. Tilting the watch along the tube presses the liquid into the lower end: that end flattens toward the advancing angle, the upper end deepens toward the receding angle — both keep the curvature\'s sign unless the band crosses 90°. A moving contact line sits at the advancing / receding angle.', group: 'Shape', label: 'hysteresis °', min: 0, max: 40, step: 0.5 },
  contactDyn: { help: 'Dynamic contact angle (Cox–Voinov, θ³ = θ₀³ ± G·v): the angle a zero-angle line reaches advancing at 25 px/s — grows with viscosity over surface tension (water ~8°, oil ~40°, honey 180°). An advancing edge flattens with speed, a receding one deepens until θ = 0 and it pulls its film.', group: 'Meniscus dynamics', label: 'dynamic angle °', min: 0, max: 180, step: 1 },
  capLength: { help: 'Capillary length √(γ/ρg) of the liquid, mm (water 2.7, oils / honey / mercury ~1.9). Against the ~2–3 mm bore it sets how much the cap sags onto the low wall under across-tilt (Bond number) and how strongly an along-tilt pushes the two ends\' angles apart.', group: 'Shape', label: 'capillary length mm', min: 0.5, max: 6, step: 0.1 },
  meniscusLens: { help: 'Pre-warp of the cap profile against the physical glass, same convention as the front-digits lens: negative undoes the vertical magnification so the drawn cap keeps its shape through the rod. Set it equal to topLens.', group: 'Shape', label: 'meniscus vs glass lens', min: -1, max: 1, step: 0.05 },
  meniscusK: { help: 'Spring of the free surface between the pinned contact lines, 1/s². Lower = slower, larger wobble.', group: 'Meniscus dynamics', label: 'surface spring K', min: 10, max: 800, step: 5 },
  meniscusDamp: { help: 'Damping of the surface wobble, 1/s. Below ~2·√K it rings after a flick.', group: 'Meniscus dynamics', label: 'surface damping', min: 0, max: 60, step: 0.5 },
  meniscusInertia: { help: 'How much the forcing on the edge (flick kick, free-slug acceleration) bulges the surface centre ahead of the contact lines: a flick makes the cap bulge, then ring at the surface spring. Hard-capped at 12 px.', group: 'Meniscus dynamics', label: 'bulge per edge forcing', min: 0, max: 10, step: 0.1 },
  wetFilm: { help: 'Trailing wet film a receding edge leaves on the glass, px at full speed (25 px/s); brightest at the walls, drains in ~0.5 s. With traces on it is the band over which the liquid thins out into its residue (full liquid at the edge, residue this many px out).', group: 'Meniscus dynamics', label: 'wet film px', min: 0, max: 30, step: 1 },
  traces: { help: 'A receding edge leaves its film on the glass where the liquid has been (blood smear, syrup coating, legs): thicker the faster the line went and the more viscous the liquid (the wet-film law of contactDyn; a watery line leaves microns, a syrup coats). Gravity runs the wet film down the tube, into the liquid where it reaches it; it dries into a fading stain.', group: 'Meniscus dynamics' },
  traceAmount: { help: 'Depth of the residue\'s tint: a stain is a Beer–Lambert tint of the tube back toward the liquid\'s own colour, this many times its film\'s depth (strongest at the wall rows, weaker at mid-height), clamped at the full chord — no smear reads denser than the column.', group: 'Meniscus dynamics', label: 'residue amount', min: 0, max: 2, step: 0.05 },
  traceDry: { help: 'Drying time constant of the residue, s: the wet film evaporates to 37% in this many seconds, leaving its stain, which fades at the same rate. Tilt does not change it (gravity moves a wet film, it does not dry it).', group: 'Meniscus dynamics', label: 'drying time s', min: 0.1, max: 2, step: 0.05 },
  traceDrain: { help: 'Drainage: the speed, px/s, at which gravity (1 g along the tube) runs a wet film at the thin-film cap (h = R/10) down the bore — ρgh²/3μ, so a film half as thick runs a quarter as fast. The film flows toward the tube\'s low end: into the liquid when that is downhill, onto the end otherwise. Water ~2000, olive oil ~15, honey ~0.2: a watery film of microns or any syrup barely moves before it dries; a fast, thick oily film sags. 0 = the film stays where it was laid. Derived from density, viscosity and bore for material presets.', group: 'Meniscus dynamics', label: 'drain speed px/s', min: 0, max: 20000, step: 0.01 },
  traceStain: { help: 'Share of a drying film left on the glass as stain (scattered 0.7–1 per column), which then fades over traceDry. 0 = the film evaporates without a trace, 1 = all of it stays.', group: 'Meniscus dynamics', label: 'stain intensity', min: 0, max: 1, step: 0.05 },
  traceFilm: { help: 'Permanent thin film over the whole glass, as a residue level: the tube never looks perfectly clean between smears. Rendered exactly like residue that has dried to this level — streaked, strongest at the wall rows, under the liquid, wet band at the edge — so fresh smears stand out above it and its depth at the walls ≈ traceFilm^0.65 × residue amount (0.05 → ~14% of the residue amount), capped at the liquid\'s own opacity (1 − transparency). 0 = bare glass. Needs traces on.', group: 'Meniscus dynamics', label: 'film everywhere', min: 0, max: 1, step: 0.01 },
  edgeSoft: { help: 'Soft edge: anti-aliased ramp width in px, centred on the edge (0 = hard pixel edge, 1 = classic 1-px AA).', group: 'Shape', min: 0, max: 4, step: 0.1 },
  frontBright: { help: 'Band just behind the fill edge blended toward liquidHi (bright convex cap), px.', group: 'Shape', min: 0, max: 40, step: 1 },
  surfaceBand: { help: 'Intensity of the visible meniscus surface. A concave surface grades from a darker inner shoulder to a lit rim and closes at the walls. It never fades as the liquid settles: a receding edge clings and deepens the dish, an advancing one flattens it, and it springs back as the edge settles. While an edge recedes fast (zero contact angle) the surface is liquid thinning into the wet trail, without shoulder or rim; both return as soon as it stops. A convex nose thins toward whatever is behind it (tube back, or the wet film a receding edge left), with a highlight tint for clear liquids. 0 disables surface shading.', group: 'Shape', label: 'surface band', min: 0, max: 1, step: 0.05 },
  surfaceRim: { help: 'Strength of the thin rim on the concave surface: the contact ring on the far glass, lit (liquidHi, light side only) over a dark tube back and a deep liquid-tinted contour, whatever the light, over a light one. Independent of surfaceFill, so it can draw the surface alone. Moves smoothly with the edge and fades with the surface band. Follows the edge light and row shading. No effect on a convex meniscus.', group: 'Shape', label: 'surface rim', min: 0, max: 1, step: 0.05 },
  surfaceWidth: { help: 'Thickness of the concave surface stroke, px, measured outward from the edge profile. It never extends past the wall contact ring (where the cap meets the glass), so it tapers to nothing at the walls.', group: 'Shape', label: 'surface width', min: 1, max: 16, step: 0.5 },
  surfaceTone: { help: 'Tone of the visible surface: 0 = the shaded shoulder and lit rim (concave) / the limb-darkened or pale nose (convex); negative darkens toward the deep liquid colour, positive lightens toward the highlight.', group: 'Shape', label: 'surface tone', min: -1, max: 1, step: 0.05 },
  surfaceFill: { help: 'Opacity of the shaded interior of the concave surface (the dish between the edge profile and the wall contact ring). 1 = the classic filled, shaded band. Lower it and the dish turns see-through — what is behind shows through a tint — while the lit rim and the blick keep drawing it; at 0 only they define the surface, as on a real vial where the surface is nearly invisible and the contact ring on the far glass catches the light. Rear marks count the dish as liquid only where its opacity reaches 0.5; the foam veil scales with it too.', group: 'Shape', label: 'surface fill', min: 0, max: 1, step: 0.05 },
  surfaceBlick: { help: 'Specular patch on the concave surface: the room light reflected in the dish. Centred on the highlight row for the light angle, about a third of the tube tall (independent of highlightH, so it works with the body strip off), peaks mid-dish and vanishes at the edge profile and at the rim, liquidHi coloured. Follows the edge light, so only the lit edge has one; gone while the edge recedes fast. 0 = off.', group: 'Shape', label: 'surface blick', min: 0, max: 1, step: 0.05 },
  edgeGlow: { help: 'Dim glow fading out past the fill edge, px. 0 = off.', group: 'Shape', min: 0, max: 40, step: 1 },
  glowStrength: { help: 'Brightness of the glow at the edge.', group: 'Shape', min: 0, max: 1, step: 0.01 },
  cornerR: { help: 'Rounding of the column left end (tube end cap), px.', group: 'Shape', min: 0, max: 36, step: 1 },
  edgeLightGain: { help: 'How much along-tilt brightens (+) / dims (-) the fill-edge light.', group: 'Shape', label: 'edge light vs tilt', min: -1, max: 2, step: 0.05 },
  bubbleDark: { help: 'Fizz: opacity of a dark tint over a bubble\'s see-through interior (the liquid and what is behind it show as they are; 0 = a bare ring, the cheapest). Spirit-level bubble: darkening of its fill.', group: 'Bubble', label: 'bubble & fizz dark', min: 0, max: 1, step: 0.01 },
  bubble: { help: 'Show the spirit-level bubble.', group: 'Bubble' },
  bubbleW: { help: 'Bubble width, px.', group: 'Bubble', min: 2, max: 40, step: 1 },
  bubbleH: { help: 'Bubble height, px.', group: 'Bubble', min: 2, max: 30, step: 1 },
  bubbleGap: { help: 'Distance from fill edge to bubble centre, px.', group: 'Bubble', min: 0, max: 80, step: 1 },
  bubbleY: { help: 'Vertical position in the tube. 0.5 = centre.', group: 'Bubble', min: 0.1, max: 0.9, step: 0.01 },
  bubbleRollGain: { help: 'Bubble rise toward the high wall per g of across-tilt. 1 = follows the wall.', group: 'Bubble', label: 'bubble rise vs across tilt', min: 0, max: 2, step: 0.05 },
  bubbleTiltGain: { help: 'Bubble slides toward the high end per g of along-tilt, px.', group: 'Bubble', label: 'bubble slides to high end px/g', min: 0, max: 80, step: 1 },
  fizz: { help: 'Small drifting bubbles.', group: 'Bubble' },
  fizzCount: { help: 'Number of fizz bubbles in a full tube. For a spring it is the most the tube holds: the rate sets how many are in flight, and at this count the spring waits for a bubble to leave.', group: 'Bubble', label: 'fizz count (full tube)', min: 0, max: 120, step: 1 },
  fizzSize: { help: 'Fizz bubble size, px.', group: 'Bubble', min: 1, max: 16, step: 0.5 },
  fizzSizeVar: { help: 'Per-bubble size spread. 0 = all equal; 1 = 0.5x..1.5x. Bigger bubbles rise faster.', group: 'Bubble', label: 'fizz size spread', min: 0, max: 1, step: 0.05 },
  fizzShadeOff: { help: 'Shift of the see-through interior away from the light (direction from the highlight angle, magnitude here), as a fraction of radius, at most radius − 1. The ring is 1 px at its thinnest; the shift thickens it on the lit side and can open it on the shaded side (a lit crescent).', group: 'Bubble', label: 'fizz shade offset', min: 0, max: 1, step: 0.05 },
  fizzSpeed: { help: 'Fizz rise speed, px/s.', group: 'Bubble', min: 0, max: 60, step: 1 },
  fizzDriftGain: { help: 'Fraction of rise speed steered toward the high end per g of along-tilt.', group: 'Bubble', label: 'fizz steers to high end', min: 0, max: 2, step: 0.05 },
  fizzAcrossGain: { help: 'Across-tilt → on-screen rise direction. 1 = rises toward the physically high edge.', group: 'Bubble', label: 'fizz rises vs across-tilt', min: 0, max: 2, step: 0.05 },
  fizzFlatRise: { help: 'On-screen rise speed when the face points up (bubbles rise toward the viewer).', group: 'Bubble', label: 'fizz rise when face up', min: 0, max: 1, step: 0.05 },
  fizzSquash: { help: 'Extra vertical pre-squash on fizz discs at mid-height (fades to none at top/bottom), on top of lens + topLens compensation. >1 flattens the center on screen so the stronger glass magnification there rounds them.', group: 'Bubble', label: 'fizz squash', min: 0.5, max: 2, step: 0.05 },
  fizzEdgeRise: { help: 'Face-up rise toward the fill edge (the liquid surface) as a fraction of fizz speed, so bubbles reach the surface at rest. 0 = they only rise toward the viewer.', group: 'Bubble', label: 'fizz rise to surface', min: 0, max: 1, step: 0.05 },
  fizzFoamLife: { help: 'Bubbles reaching the surface park under it (following the meniscus, sliding to its corners and packing into a foam ring) and pop after this many seconds on average (each ±50 %). Shaking pops them faster; tilting the surface down releases them. A spring\'s bubbles also stay on the glass they rise into for about this long (see fizz source). 0 = respawn at the far end as before.', group: 'Bubble', label: 'foam life s', min: 0, max: 30, step: 0.5 },
  fizzDepth: { help: 'Each bubble sits at a random depth in the bore; a deeper one is seen through more liquid and fades toward it by this much (at the back wall). Scaled by 1 − liquidTransparency: an opaque liquid shows only the front bubbles, a clear one shows all alike. 0 = every bubble at full strength.', group: 'Bubble', label: 'fizz depth fade', min: 0, max: 1, step: 0.05 },
  fizzBlick: { help: 'Specular pinpoint on the lit side of bubbles of 2.5 px radius and up: neutral white room light (dimmed by brightness only), placed where the lit rim meets the dark core. 0 = none.', group: 'Bubble', label: 'fizz blick', min: 0, max: 1, step: 0.05 },
  fizzSource: { help: 'Where bubbles are born. Scattered: anywhere in the liquid, recycled at the side the flow comes from. Spring: every bubble is born at one point, so they rise as a stream, like an aquarium airstone or an underwater spring. The spring is fixed in the tube and works at any tilt while the liquid covers it, at a steady rate (spring rate): a tilt that shortens the path of the bubbles shows fewer of them rather than a faster stream. With foam life > 0 the glass holds the gas the stream carries into it: at the bore wall the bubbles slide along the glass (one arriving onto another joins it) and let go after about foam life s, so the stream bends along the wall instead of ending there; at a closed end they gather as foam. When a free slug slides off the spring, new bubbles are born scattered instead, and once the liquid is back over it the spring takes its births back over about 3 s. Bubbles already rising keep their paths.', group: 'Bubble', label: 'fizz source', min: 0, max: 1, step: 1, options: ['scattered', 'spring'] },
  fizzSourceX: { help: 'Spring: position along the liquid column as it sits at home, 0 = home end, 1 = the surface (a fraction of the liquid, so it stays submerged as the column changes; a free slug sliding away leaves it behind).', group: 'Bubble', label: '· spring along', min: 0, max: 1, step: 0.01 },
  fizzSourceY: { help: 'Spring: position across the bore, 0 = top wall, 1 = bottom wall (the whole bubble stays inside).', group: 'Bubble', label: '· spring across', min: 0, max: 1, step: 0.01 },
  fizzSourceSpread: { help: 'Spring: ± px a bubble is born away from the spring point on both axes. 0 = a single point (one bead line).', group: 'Bubble', label: '· spring spread px', min: 0, max: 20, step: 0.5 },
  fizzSourceRate: { help: 'Spring: bubbles born per second, a steady cadence whatever the tilt; shaking nucleates up to twice as many. How many are in flight follows from it and their path, up to fizz count: a tilt that keeps the bubbles in the liquid makes the spring wait instead of crowding the tube.', group: 'Bubble', label: '· spring rate /s', min: 0.5, max: 20, step: 0.5 },
  ticksOnTop: { help: 'Off: rear/bottom surface. On: opaque front/top surface. Both follow the cylinder and whole-tube lens.', group: 'Ticks', label: 'ticks on top' },
  tickLens: { help: 'Cylinder depth warp for ticks before the whole-tube lens. Vertical watch with rear ticks and rear digits: unused — behind liquid the ticks move with the digits (dry-side lens → rear digit lens), so they keep their clearance from the labels.', group: 'Ticks', label: 'cylinder lens', min: 0, max: 1, step: 0.05 },
  tickDryLens: { help: 'Cylinder warp for rear ticks where the tube is empty. Liquid magnifies the middle; air barely lenses, and negative stretches the edges instead, so the scale visibly jumps at the fill edge. Rear parallax is liquid-only.', group: 'Ticks', label: 'dry-side lens', min: -1, max: 1, step: 0.05 },
  tickParallax: { help: 'Rear tick displacement at the tube centre per g of tilt. Circular depth bows the mark while its edge stays attached to the silhouette.', group: 'Ticks', label: 'rear parallax px/g', min: 0, max: 10, step: 0.25 },
  tickEmboss: { help: 'Highlight and shadow around ticks, like grooves cut into glass. 0 = flat.', group: 'Ticks', label: 'glass-cut emboss', min: 0, max: 1, step: 0.05 },
  ticksH: { help: 'Show the hours tick ladder.', group: 'Ticks · hours', label: 'show ticks' },
  tickStepH: { help: 'Minor tick every N hours.', group: 'Ticks · hours', label: 'minor every N h', min: 1, max: 6, step: 1 },
  tickMajorEveryH: { help: 'Major tick every N hours (units, not every N-th minor). 0 = none.', group: 'Ticks · hours', label: 'major every N h (0 = none)', min: 0, max: 12, step: 1 },
  tickMinorHeightH: { help: 'Minor tick height, px.', group: 'Ticks · hours', label: 'minor height', min: 0, max: 36, step: 1 },
  tickMajorHeightH: { help: 'Major tick height, px.', group: 'Ticks · hours', label: 'major height', min: 0, max: 36, step: 1 },
  tickMinorWidthH: { help: 'Minor tick width, px.', group: 'Ticks · hours', label: 'minor width', min: 1, max: 5, step: 1 },
  tickMajorWidthH: { help: 'Major tick width, px.', group: 'Ticks · hours', label: 'major width', min: 1, max: 5, step: 1 },
  tickColorH: { help: 'Minor tick colour.', group: 'Ticks · hours', label: 'minor colour' },
  tickMajorColorH: { help: 'Major tick colour.', group: 'Ticks · hours', label: 'major colour' },
  tickPosH: { help: 'Tube edge used by the hours ladder.', group: 'Ticks · hours', label: 'edge', min: 0, max: 2, step: 1, options: ['top', 'bottom', 'both'] },
  ticksM: { help: 'Show the minutes tick ladder.', group: 'Ticks · minutes', label: 'show ticks' },
  tickStepM: { help: 'Minor tick every N minutes.', group: 'Ticks · minutes', label: 'minor every N min', min: 1, max: 30, step: 1 },
  tickMajorEveryM: { help: 'Major tick every N minutes. 0 = none.', group: 'Ticks · minutes', label: 'major every N min (0 = none)', min: 0, max: 30, step: 1 },
  tickMinorHeightM: { help: 'Minor tick height, px.', group: 'Ticks · minutes', label: 'minor height', min: 0, max: 36, step: 1 },
  tickMajorHeightM: { help: 'Major tick height, px.', group: 'Ticks · minutes', label: 'major height', min: 0, max: 36, step: 1 },
  tickMinorWidthM: { help: 'Minor tick width, px.', group: 'Ticks · minutes', label: 'minor width', min: 1, max: 5, step: 1 },
  tickMajorWidthM: { help: 'Major tick width, px.', group: 'Ticks · minutes', label: 'major width', min: 1, max: 5, step: 1 },
  tickColorM: { help: 'Minor tick colour.', group: 'Ticks · minutes', label: 'minor colour' },
  tickMajorColorM: { help: 'Major tick colour.', group: 'Ticks · minutes', label: 'major colour' },
  tickPosM: { help: 'Tube edge used by the minutes ladder.', group: 'Ticks · minutes', label: 'edge', min: 0, max: 2, step: 1, options: ['top', 'bottom', 'both'] },
  liquidTransparency: { help: 'How much of ticks/digits shows through the liquid. 0 = opaque liquid.', group: 'Shape', min: 0, max: 1, step: 0.01 },
  markContrast: { help: 'Min luma difference a tick/digit keeps from the liquid behind it. 0 = off. Material mode: at most 120 × the liquid transparency (the floor may fake only what the liquid lets through); a clear liquid needs 16 or more.', group: 'Shape', label: 'mark contrast in liquid', min: 0, max: 120, step: 2 },
  // digits — shared
  digits: { help: 'Show numeric labels along the bottom of the tube.', group: 'Digits', label: 'show digits' },
  digitFont: {
    help: 'Bitmap fonts are code-rendered. Image fonts preserve rendered material, bevel, and texture.',
    group: 'Digits',
    label: 'font',
    min: 0, max: 11, step: 1,
    options: ['3×5 bitmap', '4×6 narrow bitmap', '5×7 round bitmap', '5×7 seven-segment', '6×8 bold bitmap',
      'Steel', 'Brass steampunk', 'Copper gauge', 'Forged iron', 'Ivory enamel', 'Carved slate', 'Amber resin'],
  },
  digitTint: { help: 'Sprite fonts only: multiply colour.', group: 'Digits', label: 'image tint colour' },
  digitTintAmount: { help: 'Sprite fonts only: 0 = untinted sheet, 1 = fully tinted.', group: 'Digits', label: 'image tint amount', min: 0, max: 1, step: 0.05 },
  digitTone: { help: 'Sprite fonts only: darken toward black or lighten toward white after tinting.', group: 'Digits', label: 'image tone', min: -1, max: 1, step: 0.05 },
  digitColor: { help: 'Top of glyph (vertical gradient; set equal to bottom for flat).', group: 'Digits', label: 'colour top' },
  digitColor2: { help: 'Bottom of glyph.', group: 'Digits', label: 'colour bottom' },
  digitShadow: { help: 'Darker copy offset down-right (emboss), so glyphs read as physical pieces on the glass.', group: 'Digits', label: 'emboss shadow' },
  digitShadowColor: { help: 'Emboss shadow colour.', group: 'Digits', label: 'shadow colour' },
  digitShadowStrength: { help: 'Shadow opacity. 0 = invisible.', group: 'Digits', label: 'shadow strength', min: 0, max: 1, step: 0.05 },
  digitShadowOffset: { help: 'Shadow offset in pixels, down-right.', group: 'Digits', label: 'shadow offset', min: 1, max: 4, step: 1 },
  digitsOnTop: { help: 'Printed on the glass, opaque and excluded from the whole-tube lens. Off: behind the liquid, seen through it and depth-warped.', group: 'Digits', label: 'print on top of liquid' },
  bottomLens: { help: 'Depth warp for digits behind the liquid.', group: 'Digits', label: 'rear lens', min: 0, max: 1, step: 0.05 },
  digitDryLens: { help: 'Depth warp for rear digits where the tube is empty, chosen per pixel column. Negative stretches the edges instead of magnifying the middle.', group: 'Digits', label: 'rear lens behind air', min: -1, max: 1, step: 0.05 },
  topParallax: { help: 'Across-shift of top digits per g of across-tilt, countering the apparent shift under the physical lens. Sign flips direction.', group: 'Digits', label: 'front parallax px/g', min: -10, max: 10, step: 0.25 },
  digitParallax: { help: 'Rear digits seen through the liquid slide with tilt (along-tilt along the tube, across-tilt across it) while those behind air stay put, so a label straddling the fill edge breaks at it. Same scale as the tick parallax.', group: 'Digits', label: 'rear parallax px/g', min: 0, max: 10, step: 0.25 },
  // digits — hours tube
  digitHourStep: { help: 'Label every N hours.', group: 'Digits · hours', label: 'label every N h', min: 1, max: 6, step: 1 },
  digitsLastOnlyH: { help: 'Show only the last passed hour.', group: 'Digits · hours', label: 'last passed only' },
  digitHourStart: { help: 'First labelled hour; 0 = same as step. Step 2 + start 1 = odd hours.', group: 'Digits · hours', label: 'first label h', min: 0, max: 11, step: 1 },
  digitScaleX: { help: 'Hours tube horizontal scale (nearest-neighbour).', group: 'Digits · hours', label: 'scale X', min: 0.5, max: 6, step: 0.25 },
  digitScaleY: { help: 'Hours tube vertical scale. Keep below X to counter the vial vertical stretch.', group: 'Digits · hours', label: 'scale Y', min: 0.5, max: 6, step: 0.25 },
  digitBottom: { help: 'Hours tube: px from the tube bottom edge to the digit baseline.', group: 'Digits · hours', label: 'baseline from bottom', min: 0, max: 40, step: 1 },
  // digits — minutes tube
  digitMinuteStep: { help: 'Label every N minutes.', group: 'Digits · minutes', label: 'label every N min', min: 5, max: 30, step: 5 },
  digitsLastOnlyM: { help: 'Show only the last passed multiple of the step.', group: 'Digits · minutes', label: 'last passed only' },
  digitMinuteStart: { help: 'First labelled minute; 0 = same as step.', group: 'Digits · minutes', label: 'first label min', min: 0, max: 55, step: 5 },
  digitsLeadingZero: { help: 'Minutes as 05, 10 instead of 5, 10.', group: 'Digits · minutes', label: 'leading zero (05)' },
  digitScaleXMin: { help: 'Minutes tube horizontal scale.', group: 'Digits · minutes', label: 'scale X', min: 0.5, max: 6, step: 0.25 },
  digitScaleYMin: { help: 'Minutes tube vertical scale.', group: 'Digits · minutes', label: 'scale Y', min: 0.5, max: 6, step: 0.25 },
  digitBottomMin: { help: 'Minutes tube: px from the tube bottom edge to the digit baseline.', group: 'Digits · minutes', label: 'baseline from bottom', min: 0, max: 40, step: 1 },
  freeLiquid: { help: 'Automatically holds the time at gentle tilt and releases the liquid as tilt increases. Deliberate back-and-forth tilts keep it free for the play hold, even through the viewing angle. Turn off to keep the column pinned.', group: 'Free liquid', label: 'tilt-controlled flow' },
  freeGain: { help: 'Slug acceleration per g of along-tilt, px/s².', group: 'Free liquid', label: 'gravity px/s²/g', min: 0, max: 2000, step: 10 },
  freeDamp: { help: 'Viscous drag on the slug, 1/s. Higher = syrup.', group: 'Free liquid', label: 'drag', min: 0, max: 20, step: 0.1 },
  freeBounce: { help: 'Restitution when the slug hits a tube end. 0 = splat, 1 = elastic.', group: 'Free liquid', label: 'end bounce', min: 0, max: 1, step: 0.05 },
  freeHomeK: { help: 'Pull toward the home end while reading, 1/s² (critically damped).', group: 'Free liquid', label: 'home pull K', min: 0, max: 300, step: 1 },
  readTiltStart: { help: 'Degrees from horizontal, counting both tilt axes. Below this angle the liquid settles to the exact time; above it the home pull gradually releases.', group: 'Free liquid', label: 'read below °', min: 0, max: 89, step: 1 },
  readTiltEnd: { help: 'Degrees from horizontal at which the liquid flows completely freely. The transition is smooth; this is kept at least 1° above the reading angle.', group: 'Free liquid', label: 'fully free above °', min: 1, max: 90, step: 1 },
  playHold: { help: 'Seconds to keep flowing freely after substantial back-and-forth tilts within 2 seconds. Further tilts refresh the hold; a steady pose does not. Zero disables the hold.', group: 'Free liquid', label: 'play hold s', min: 0, max: 30, step: 0.5 },
  fillK: { help: 'Spring stiffness of fill-edge position, 1/s².', group: 'Physics', min: 1, max: 800, step: 1 },
  fillDamp: { help: 'Damping of the fill-edge spring, 1/s.', group: 'Physics', min: 0, max: 40, step: 0.1 },
  fillSloshGain: { help: 'Fill-edge shift per g of along-tube acceleration, px.', group: 'Physics', label: 'slosh px/g (capped 30)', min: 0, max: 30, step: 0.5 },
  angleK: { help: 'Spring stiffness of the surface angle.', group: 'Physics', min: 1, max: 800, step: 1 },
  angleDamp: { help: 'Damping of the surface-angle spring.', group: 'Physics', min: 0, max: 40, step: 0.1 },
  angleTiltGain: { help: 'In-plane front skew per g of across-tube tilt, deg (static).', group: 'Physics', label: 'skew deg/g across', min: 0, max: 20, step: 0.5 },
  angleGyroGain: { help: 'Fill-edge kick per dps of rotation about the across axis (flicks).', group: 'Physics', min: 0, max: 3, step: 0.005 },
  angleMax: { help: 'Surface angle clamp, deg.', group: 'Physics', label: 'angle clamp (hard cap 20)', min: 0, max: 20, step: 1 },
  lightPhys: { help: '0 = fixed style light at lightAngle; 1 = world-up light from the IMU (highlight row, cylinder shading).', group: 'Shape', label: 'light: style 0 .. physical 1', min: 0, max: 1, step: 0.05 },
  lightAngle: { help: 'Style highlight angle, deg. 0 = centre row, 90 = top wall.', group: 'Shape', label: 'style light angle (deg)', min: -85, max: 85, step: 1 },
  acrossK: { help: 'Spring stiffness of the light (roll) swing.', group: 'Physics', label: 'light spring K', min: 1, max: 800, step: 1 },
  acrossDamp: { help: 'Damping of the light swing.', group: 'Physics', label: 'light damping', min: 0, max: 40, step: 0.1 },
  acrossGyroGain: { help: 'Light impulse per dps of roll rate (gyro about the tube axis), deg.', group: 'Physics', label: 'light kick deg/dps', min: 0, max: 2, step: 0.01 },
  shakeGain: { help: 'Agitation sensitivity to gyro energy: fizz speed, edge glow.', group: 'Physics', label: 'shake → fizz/glow', min: 0, max: 2, step: 0.05 },
  deadzone: { help: 'Ignore accelerations below this, g.', group: 'Physics', min: 0, max: 0.2, step: 0.005 },
  accelLpHz: { help: 'Low-pass cutoff for accel (gravity direction), Hz.', group: 'IMU filter', min: 0.2, max: 25, step: 0.1 },
  gyroHpHz: { help: 'High-pass cutoff for gyro: removes bias and slow rotations, keeps flicks. Hz.', group: 'IMU filter', min: 0, max: 5, step: 0.05 },
  gyroDeadzone: { help: 'Ignore gyro below this after filtering, dps.', group: 'IMU filter', min: 0, max: 60, step: 1 },
  gyroMax: { help: 'Gyro clamp, dps.', group: 'IMU filter', min: 50, max: 1000, step: 10 },
  inputGain: { help: 'Overall multiplier on tilt input.', group: 'IMU filter', min: 0.1, max: 2, step: 0.05 },
};
