// Fixed-timestep (50 Hz) liquid dynamics — two spring-dampers per tube.
// Mirrors what the firmware will run. No rendering here.
import type { Params } from './params';
import { DESIGN_MM_PER_PX, DESIGN_TUBE_HEIGHT_MAX, mmPerPxAt, TUBE_HEIGHT_MAX, TUBE_LENGTH_PX } from '../../spec/layout';

export const PHYS_HZ = 50;
export const PHYS_DT = 1 / PHYS_HZ;
// Rear parallax gate (stepTube): the shift acts on slow tilts and while settling, and holds still (eases to straight-on)
// while the wrist keeps swinging. Tilt smoothed over REAR_RATE_S for its rate (g/s); activity = that rate with a fast
// attack (REAR_ACT_ATTACK /s) and a slow decay (REAR_ACT_DECAY_S); the gate closes smoothly from REAR_GATE_LO to
// REAR_GATE_HI g/s. Reaching REAR_GATE_HI latches it shut, and only REAR_QUIET_S of activity continuously below
// REAR_GATE_LO releases it: a sustained swing's reversals (where the rate passes zero) cannot reopen it. The shift
// eases toward gate x the high-passed shift over REAR_EASE_S (no snaps either way).
export const REAR_RATE_S = 0.1;
export const REAR_ACT_ATTACK = 20;
export const REAR_ACT_DECAY_S = 1;
export const REAR_GATE_LO = 0.5;
export const REAR_GATE_HI = 1;
export const REAR_QUIET_S = 1;
export const REAR_EASE_S = 0.15;
const PLAY_STROKE_G = 0.35; // substantial change in filtered gravity (~20° near horizontal)
const PLAY_REVERSAL_S = 2;  // opposite strokes must be close together to count as play

/** Input in the tube's frame (already mapped from IMU axes via spec/layout IMU_* constants). */
export interface TiltInput {
  along: number;  // g, +1 = right end of the tube is down (liquid wants to flow right)
  across: number; // g, +1 = far (top) edge up
  gyroAlong: number; // deg/s rotation rate about the along-tube axis... (rolling the tube)
  gyroAcross: number; // deg/s rotation about the across axis (tilting left/right end up/down) — drives slosh
  // g, the measured out-of-plane component: +1 = face up (IMU +Z out of the screen, spec/layout IMU_AXIS_NORMAL),
  // -1 = face down. Signed, never reconstructed from along / across. Nothing in stepTube reads it (legacy signals).
  normal: number;
}

/** Physical pose: the unit buoyancy direction b = normalize(-along, -across, +normal) in tube coordinates
 *  (x along the tube toward its top, y across, z toward the viewer; docs/tilted-fizz-plan.md), from the filtered
 *  gravity WITHOUT inputGain (an interaction gain, not a change of gravity's direction). */
export interface Pose { x: number; y: number; z: number }
/** Below this |g| (filtered, g) the vector is noise (free fall, a missing axis): the pose keeps its last valid value. */
export const POSE_MIN_G = 0.3;
/** A phone's deviceorientation (deg; W3C Z-X'-Y'': beta about x, then gamma about y) as tube-frame gravity, the phone
 *  lying with its x along the tube: "up" in its frame is (-cos b sin g, sin b, cos b cos g), so along = -x,
 *  across = y, normal = z (+ face up; |beta| past 90: face down). A unit vector: the three agree in 3D. */
export function orientationTilt(betaDeg: number, gammaDeg: number): { along: number; across: number; normal: number } {
  const b = (betaDeg * Math.PI) / 180, g = (gammaDeg * Math.PI) / 180;
  return { along: Math.cos(b) * Math.sin(g), across: Math.sin(b), normal: Math.cos(b) * Math.cos(g) };
}
/** The phone input the sim feeds: a vertical watch takes the 3D mapping (orientationTilt); landscape keeps its legacy
 *  along = sin gamma, across = sin beta (its tuned liquid / light response), only normal from the one rotation. */
export function phoneTilt(betaDeg: number, gammaDeg: number, vertical: boolean): { along: number; across: number; normal: number } {
  const o = orientationTilt(betaDeg, gammaDeg);
  if (vertical) return o;
  return { along: Math.sin((gammaDeg * Math.PI) / 180), across: Math.sin((betaDeg * Math.PI) / 180), normal: o.normal };
}
/** Before any valid sample: face up (what the legacy zero along / across means: flat on the table). */
export const POSE_DEFAULT: Readonly<Pose> = { x: 0, y: 0, z: 1 };
/** Desk view: the stand's tilt τ = atan2(z, x) of the pose, rad, signed: > 0 back (the top end leaning away from the
 *  viewer), < 0 forward (the screen tipped toward the viewer); clamped to ±BACK_TILT_MAX_DEG (face up / down, turned over:
 *  the caps). In float32 as physics.cpp. */
export const BACK_TILT_MAX_DEG = 45;
export function poseBackTilt(pose: Readonly<Pose>): number {
  const F = Math.fround, t = F(Math.atan2(F(pose.z), F(pose.x))), hi = F(F(BACK_TILT_MAX_DEG * F(Math.PI)) / 180);
  return t > hi ? hi : t < -hi ? -hi : t;
}
/** Sets `pose` to normalize(-along, -across, normal) and returns true; a vector shorter than POSE_MIN_G or not
 *  finite leaves `pose` as it was (the last valid orientation) and returns false. Same maths in physics.cpp. */
export function updatePose(pose: Pose, along: number, across: number, normal: number): boolean {
  const x = -along, y = -across, z = normal, m2 = x * x + y * y + z * z;
  if (!(m2 >= POSE_MIN_G * POSE_MIN_G) || !Number.isFinite(m2)) return false;
  const inv = 1 / Math.sqrt(m2);
  pose.x = x * inv; pose.y = y * inv; pose.z = z * inv;
  return true;
}

// The liquid is a viscous column pinned by capillarity in a thin sealed tube: tilting and
// shaking may only nudge the fill edge and shift the light, never relocate the column.
// These are hard caps applied on top of whatever the params say, so no gain/filter tuning
// can ever make the liquid run off the end of the tube. Ported to firmware as-is.
// px caps and speeds are design px: a tube's canvas px = × its px scale k (spec/layout TUBE_PX_SCALE).
export const FILL_SLOSH_MAX_DESIGN_PX = 30;   // |fillPos| cap
export const fillSloshMaxPx = (k: number): number => FILL_SLOSH_MAX_DESIGN_PX * k;
export const ANGLE_HARD_MAX_DEG = 20; // |angle| cap (params.angleMax tightens it, never widens)
export const ANGLE_VERTICAL_MAX_DEG = 45; // |angle| cap of a vertical watch, whose upper surface stays level against the tilted tube
export const LIGHT_MAX_DEG = 85;      // |light| cap
// What the render reads of the physics (perf-cheap A): the light angle and the edge skew, each held in whole steps of *_Q
// (a power of two: exact in float32 and double) by quantHyst: it follows the spring's value when that leaves +-*_Q_HYST
// steps around it (a fast excursion: to the nearest step inside the band, one step at a time on a slow tilt), and steps
// toward the value's mean (a QUANT_MEAN_S running average) while that mean sits more than a quarter of the band away (a
// slow change, or the band's offset after a motion: the settled error is at most a quarter band). A still watch's sensor
// noise then neither rebuilds the palette nor redraws the edge's tiles every frame. Steps: LIGHT_Q_DEG, any palette row
// moves at most 1 RGB565 LSB a step (STATUS.md, perf-cheap A); ANGLE_Q_DEG, an edge row at most 1/16 px at the tallest
// tube. The bands span about twice the board's noise at rest (STATUS). Every value a threshold sees — the IMU filter, the
// rests, the springs, the means — is float32 here, step for step as the firmware's (physics.cpp, no fused multiply-add),
// so both pick the same steps (firmware/tools/check_held.py). The stand's back tilt is not held. Same constants in firmware
// physics.h.
export const LIGHT_Q_DEG = 0.125;
export const LIGHT_Q_HYST = 3;
export const ANGLE_Q_DEG = 0.03125;
export const ANGLE_Q_HYST = 8;
export const QUANT_MEAN_S = 1;
const F = Math.fround;
/** One physics step of a held value (firmware physics.h quantHyst, float32): `mean` = its running average, updated and
 *  returned with the new held value (`held`: the current one, a multiple of q). */
export function quantHyst(v: number, mean: number, held: number, q: number, h: number, dt: number): [number, number] {
  mean = F(mean + F(F(v - mean) * Math.min(1, F(F(dt) / QUANT_MEAN_S))));
  const u = F(v / q), i = F(held / q), m = F(mean / q);
  if (F(u - i) > h) return [F(Math.ceil(F(u - h)) * q), mean];
  if (F(i - u) > h) return [F(Math.floor(F(u + h)) * q), mean];
  if (F(m - i) > 0.25 * h && u > i) return [F(held + q), mean];   // resting off the mean: back toward it, a step at a time
  if (F(i - m) > 0.25 * h && u < i) return [F(held - q), mean];
  return [held, mean];
}
/** A held value inside the spring's limit [-lim, lim]: at most the step nearest the limit inside it, and that step while
 *  the spring rests on the limit (firmware heldClamp). */
export function heldClamp(held: number, raw: number, lim: number, q: number): number {
  const top = F(Math.floor(F(F(lim) / q)) * q);
  return raw >= lim || held > top ? top : raw <= -lim || held < -top ? -top : held;
}
/** The held light and angle back on their springs (nearest step, the means at the springs): after a params change, which
 *  may move a spring's rest or limit (firmware heldReseat, main paramsChanged). */
export function heldReseat(s: TubeState): void {
  s.light = F(Math.floor(F(F(s.lightRaw / LIGHT_Q_DEG) + 0.5)) * LIGHT_Q_DEG); s.lightMean = s.lightRaw;
  s.angle = F(Math.floor(F(F(s.angleRaw / ANGLE_Q_DEG) + 0.5)) * ANGLE_Q_DEG); s.angleMean = s.angleRaw;
}
export const CAP_DYN_MAX_DESIGN_PX = 12;     // |cap| cap: dynamic meniscus bulge / hollow
export const capDynMaxPx = (k: number): number => CAP_DYN_MAX_DESIGN_PX * k;
export const PIN_RELAX_S = 3;         // a held contact line creeps back to the static shape (wrist micro-motion), s
export const FILM_FULL_DESIGN_PX_S = 25;   // edge speed (design px/s) at which the trailing wet film is fully drawn
export const filmFullPxS = (k: number): number => FILM_FULL_DESIGN_PX_S * k;   // the same in canvas px/s
export const TRACE_DEPOSIT_MAX_DESIGN_PX = 32; // max px of newly exposed glass per tick that gets a fresh deposit
export const traceDepositMaxPx = (k: number): number => TRACE_DEPOSIT_MAX_DESIGN_PX * k;
export const TRACE_FULL = 0xff00;      // a film at FILM_ETA_MAX (8.8 fixed point)
export const TRACE_MIN = 2 << 8;       // dry residue below this is gone (buffer empties); also the thinnest deposit
export const TRACE_DRAIN_MAX_PX_S = 48; // cap of a film's drain speed: TRACE_DRAIN_STEPS upwind steps a tick stay stable (3·c·dt/steps < 1); canvas px, not scaled (a stability bound)
export const TRACE_DRAIN_STEPS = 3;
export const RETRACT_S = 2;            // a full tube empties over this long when its scale wraps (followClock), s

// The film a receding line leaves on the bore wall, h = η·R: Bretherton's tube law with the finite-Ca
// correction, η = 1.34 Ca^⅔ / (1 + 3.35 Ca^⅔), capped at FILM_ETA_MAX (thin-film limit). Ca is the one
// capShape's Cox–Voinov term is calibrated with (θ³ = θ₀³ − G·v ⇒ Ca ≈ θ_dyn³ / 9Λ at filmFullPxS;
// material/derive.ts inverts the same law for contactDyn), scaled by the line's speed. A watery line leaves
// microns, thicker the faster it goes (∝ U^⅔); a syrup coats the bore whatever the speed.
export const FILM_LAMBDA = 9.2, FILM_ETA_MAX = 0.1;
// speed: the line's px/s; full: filmFullPxS of its tube (speed = full: the fully drawn film).
export function filmEta(p: Params, speed: number, full: number): number {
  const dyn = Math.max(0, p.contactDyn) * Math.PI / 180, ca = dyn * dyn * dyn / (9 * FILM_LAMBDA) * (speed / full);
  const c = Math.cbrt(ca * ca);
  return Math.min(FILM_ETA_MAX, 1.34 * c / (1 + 3.35 * c));
}
/** traceDrain from the render params alone (presets without a material; migration to Params v27): ρg/μ from
 *  the capillary length (γ/ρg = lc²) and the Ca contactDyn is calibrated with (μ = Ca·γ/U at filmFullPxS),
 *  v = ρg·h²/3μ = U·h²/(3·Ca·lc²) for h = FILM_ETA_MAX·R, in px/s. contactDyn tops out at 90°, so a syrup comes
 *  out faster than its material would make it (the material layer derives it from ρ and μ instead).
 *  `p` and the result are in design px (a preset's own units, whatever the board). */
export function legacyTraceDrain(p: Params): number {
  const dyn = Math.max(0, p.contactDyn) * Math.PI / 180, ca = dyn * dyn * dyn / (9 * FILM_LAMBDA);
  if (!(ca > 0)) return 0;
  const H = Math.max(4, Math.min(DESIGN_TUBE_HEIGHT_MAX, Math.round(p.tubeHeight)));
  const R = Math.max(1, (H - 1) / 2 - Math.max(0, p.glassWall));   // boreR in design px
  const r = R * DESIGN_MM_PER_PX / Math.max(0.1, p.capLength);   // R / lc (render px-mm on both sides)
  return FILM_FULL_DESIGN_PX_S * FILM_ETA_MAX * FILM_ETA_MAX * r * r / (3 * ca);
}

export interface TubeState {
  fillTarget: number;  // 0..1 from time, as shown (followClock)
  clockPrev: number;   // the clock's fill at the previous followClock (wrap detection)
  retract: number;     // 0..1 through a wrap's retract, 1 = none running
  retractFrom: number; // fillTarget when the wrap began
  fillPos: number;     // px offset of the edge relative to target (slosh), spring toward 0
  fillVel: number;
  angle: number;       // deg, in-plane skew of the time edge (+ = bottom contact line leads); follows across-tilt. The home edge of a free slug leans the other way (render.ts edgeSkews). Held: angleRaw by quantHyst (ANGLE_Q_*)
  angleVel: number;
  angleRaw: number;    // deg, the spring's skew (angle is what the render reads)
  angleMean: number;   // quantHyst's running mean of angleRaw
  light: number;       // deg, highlight surface-normal angle in the tube cross-section (0 = centre row, + = toward the top edge). Held: lightRaw by quantHyst (LIGHT_Q_*)
  lightVel: number;
  lightRaw: number;    // deg, the spring toward lightRest() (light is what the render reads)
  lightMean: number;   // quantHyst's running mean of lightRaw
  agitation: number;   // 0..1, gyro energy with fast attack / slow decay: fizz speed, edge glow
  edgeLight: number;   // -1..1, slow along-tilt follower — brightens/dims the fill edge (render only)
  acrossTilt: number;  // -1..1, slow across-tilt follower — meniscus sag toward the low wall (render only)
  // Rear (view-angle) parallax, an approximation driven by tilt: with the head still, turning the wrist changes the
  // viewing angle, read here as the change of in-plane gravity, high-passed so the shift settles back after a turn
  // (artificial: a held wrist angle does not really become straight-on). `rearLp*` = the tilt low-passed over
  // rearParallaxSettle. The shift, quantised once here (1/16 px; render and `x` dump take these integers, so the sim
  // and the firmware render the same taps): `rearX16`/`rearY16` the rear wall behind air (panel x / rows down),
  // `rearX16w`/`rearY16w` behind liquid (/ liquidIor).
  rearLpAlong: number;
  rearLpAcross: number;
  rearInit: boolean;
  // the gate (REAR_* above): the tilt smoothed for its rate, the swinging activity (g/s), the eased shift behind air (px)
  rearSmAlong: number;
  rearSmAcross: number;
  rearAct: number;
  rearLatch: boolean;  // the gate held shut by a swing (REAR_GATE_HI reached), until REAR_QUIET_S of quiet
  rearQuiet: number;   // s of activity continuously below REAR_GATE_LO
  rearSx: number;
  rearSy: number;
  rearX16: number;
  rearY16: number;
  rearX16w: number;
  rearY16w: number;
  // Meniscus wobble: the wall contact lines are pinned by capillarity, the free surface between
  // them is not. `cap` = px the surface centre leads the contact lines in +x (panel frame): an
  // impulse bulges it ahead (inertia) and it rings at the surface spring.
  cap: number;
  capVel: number;
  // Pinned contact lines, one per meniscus end (free = the time edge, home = a free slug's home edge),
  // each in its end's own outward sense. `pin*` = px the surface centre has travelled against its held
  // wall ring (+ = outward): hysteresis lets the ring's lead drift inside [lead(θA), lead(θR)] while the
  // line stays put; travel past that drags the line along. `lineV*` = its speed, px/s, over ~0.5 s: the
  // dynamic angle is a steady-motion law (a viscous surface takes ~μR/γ to reshape, honey ~0.5 s), so a
  // stick-slip creep of a line held at θA / θR under tremor sets its mean, not a flicker.
  pinFree: number;
  pinHome: number;
  lineVFree: number;
  lineVHome: number;
  // Trailing wet film 0..1 left on the glass by a receding edge (drains away in ~0.5 s).
  filmFree: number;    // the time edge receding toward its home end
  filmHome: number;    // the home edge (free-liquid only) receding toward the time edge
  // Dried traces: residue 0..TRACE_FULL (8.8 fixed point, film thickness relative to FILM_ETA_MAX) per
  // panel-frame column, deposited where an edge receded (blood smears the wall, syrup coats it). Its wet
  // part `traceWet` (<= trace) runs down under gravity and rejoins the liquid it reaches, and evaporates
  // into a stain that fades (params.traceDrain / traceStain / traceDry); the render reads `trace` only.
  // Owned by the tube (newTube allocates; firmware: a static buffer and a PSRAM one per tube).
  trace: Uint16Array;
  traceWet: Uint16Array;
  traceLo: number;     // occupied residue columns [traceLo, traceHi): deposits widen, decay shrinks.
  traceHi: number;     // lo >= hi = empty; physics and render skip the buffer entirely then.
  xtPrev: number;      // panel-frame time-edge x at the previous tick (deposit tracking)
  xhPrev: number;      // panel-frame home-edge x at the previous tick
  traceInit: boolean;  // false until the first step primed the prev positions
  // Free liquid: the column is a slug that slides along the tube; `slugPos` = px of its home-end
  // edge from the tube's left end (panel frame), 0 when pinned. `reading` 1 = the pose pull holds
  // it home so the time edge is true; 0 = free.
  slugPos: number;
  slugVel: number;
  reading: number;
  playTimer: number; // seconds of free flow remaining after deliberate tilts
  playWindow: number; // seconds in which an opposite stroke can start play
  playAnchorAlong: number; playAnchorAcross: number;
  playDirAlong: number; playDirAcross: number; // unit direction of the last substantial stroke
  playInit: boolean;
  // Desk view (render only): the stand's back tilt τ, rad (poseBackTilt of the pose, set per physics step by main; 0 =
  // upright). The lid's height follows it with params viewElevation (render.ts lidT).
  backTilt: number;
}

export function newTube(): TubeState {
  return { fillTarget: 0, clockPrev: 0, retract: 1, retractFrom: 0, fillPos: 0, fillVel: 0, angle: 0, angleVel: 0, angleRaw: 0, angleMean: 0, light: 0, lightVel: 0, lightRaw: 0, lightMean: 0, agitation: 0, edgeLight: 0, acrossTilt: 0,
    rearLpAlong: 0, rearLpAcross: 0, rearInit: false, rearSmAlong: 0, rearSmAcross: 0, rearAct: 0, rearLatch: false, rearQuiet: 0, rearSx: 0, rearSy: 0, rearX16: 0, rearY16: 0, rearX16w: 0, rearY16w: 0,
    cap: 0, capVel: 0, pinFree: 0, pinHome: 0, lineVFree: 0, lineVHome: 0, filmFree: 0, filmHome: 0,
    trace: new Uint16Array(TUBE_LENGTH_PX), traceWet: new Uint16Array(TUBE_LENGTH_PX), traceLo: TUBE_LENGTH_PX, traceHi: 0, xtPrev: 0, xhPrev: 0, traceInit: false,
    slugPos: 0, slugVel: 0, reading: 1, playTimer: 0, playWindow: 0,
    playAnchorAlong: 0, playAnchorAcross: 0, playDirAlong: 0, playDirAcross: 0, playInit: false, backTilt: 0 };
}

/** Per-column unevenness of the dried traces: the high 16 bits scatter the drying rates, the low 16
 *  the stain share. The integer hash must match firmware/src/physics.cpp exactly (and is salted
 *  differently from the renderer's traceStreak, so opacity striations and dissolve don't line up). */
function traceUneven(n: number): number {
  let h = (Math.imul(n ^ 0x27d4eb2f, 2654435761) + 0x9e3779b9) | 0;
  h ^= h >>> 15; h = Math.imul(h, 2246822519); h ^= h >>> 13;
  return h >>> 0;
}

/** Gravity `g` (g along the tube, panel +x) runs the wet film down the bore. A viscous film on a wall moves
 *  at a mean speed ρ·g·h²/3μ, so the flux out of a column is q = c·w, c = traceDrain·|g|·(w / TRACE_FULL)²
 *  (traceDrain: that speed for a film at the thin-film cap, h = FILM_ETA_MAX·R), capped at
 *  TRACE_DRAIN_MAX_PX_S. Thick parts outrun thin ones, so a draining film thins from its top; a watery film
 *  of microns, or any syrup, barely moves before it dries. Upwind in integers, downstream column first:
 *  what leaves one column lands in the next, exactly. The tube's ends hold it (a drop pools there) and a
 *  column saturated at TRACE_FULL backs the film up. The range [traceLo, traceHi) grows with it. */
export function drainTrace(s: TubeState, p: Params, g: number, dt: number): void {
  if (!(p.traceDrain > 0) || g === 0 || s.traceHi <= s.traceLo) return;
  const k = p.traceDrain * Math.abs(g) / (TRACE_FULL * TRACE_FULL), dts = dt / TRACE_DRAIN_STEPS;
  const w = s.traceWet, t = s.trace, L = TUBE_LENGTH_PX;
  const out = (v: number, into: number): number =>
    Math.min(Math.floor(Math.min(TRACE_DRAIN_MAX_PX_S, k * v * v) * v * dts), TRACE_FULL - t[into]);
  for (let n = 0; n < TRACE_DRAIN_STEPS; n++) {
    const lo = s.traceLo, hi = s.traceHi;
    if (g > 0) for (let x = Math.min(hi, L - 1) - 1; x >= lo; x--) {
      const f = w[x] ? out(w[x], x + 1) : 0;
      if (f <= 0) continue;
      w[x] -= f; t[x] -= f; w[x + 1] += f; t[x + 1] += f;
      if (x + 1 >= s.traceHi) s.traceHi = x + 2;
    }
    else for (let x = Math.max(lo, 1); x < hi; x++) {
      const f = w[x] ? out(w[x], x - 1) : 0;
      if (f <= 0) continue;
      w[x] -= f; t[x] -= f; w[x - 1] += f; t[x - 1] += f;
      if (x - 1 < s.traceLo) s.traceLo = x - 1;
    }
  }
}

/** Whether the column is drawn from the right end (the mirrored frame). A vertical watch keeps the liquid at
 *  the bottom (left end) whatever `remaining` says: there the flag only flips the scale and the column length. */
export function mirrored(p: Params): boolean {
  return p.remaining && !p.vertical;
}

/** Length of the liquid column, px. */
export function columnLen(fillTarget: number, p: Params): number {
  return (p.remaining ? 1 - fillTarget : fillTarget) * TUBE_LENGTH_PX;
}

/** Bore radius, px in row-centre units: the tube's (H − 1)/2 less the glass wall band. The contact
 *  ring sits on the bore's inner surface, not the outer silhouette. */
export function boreR(p: Params): number {
  const H = Math.max(4, Math.min(TUBE_HEIGHT_MAX, Math.round(p.tubeHeight)));
  return Math.max(1, (H - 1) / 2 - Math.max(0, p.glassWall));
}
/** One meniscus end's wall-ring leads, px the contact ring leads the surface centre (R(1 − sin θ)/cos θ,
 *  R = boreR,
 *  see render.ts capShape): `adv` / `rec` = at the advancing / receding contact angle (adv <= rec),
 *  `rest` = where the hydrostatic head along the slug puts it (`len` = column px, `tilt` = along follower
 *  into this end), held within [adv, rec] — the pressure's static shape, no history. A line with `pin` px
 *  of centre travel against it shows clamp(rest − pin, adv, rec). `mmPerPx`: the tube's (spec/layout mmPerPxAt). */
export function contactLeads(p: Params, len: number, tilt: number, mmPerPx: number): { R: number; rest: number; adv: number; rec: number } {
  const R = boreR(p), rad = Math.PI / 180;
  const t0 = Math.max(0, Math.min(180, p.contactAngle)) * rad, hy = Math.max(0, p.contactHyst) * rad;
  const lead = (th: number): number => R * Math.cos(th) / (1 + Math.sin(th));
  // hydrostatic head, split between the two ends: Δcos θ = R·L·sin α / (4 lc²), all in mm
  const lc = Math.max(0.1, p.capLength), Rmm = R * mmPerPx;
  const cs = Math.max(-1, Math.min(1, Math.cos(t0) - Rmm * Math.max(0, len) * mmPerPx * tilt / (4 * lc * lc)));
  const adv = lead(Math.min(Math.PI, t0 + hy)), rec = lead(Math.max(0, t0 - hy));
  return { R, rest: Math.max(adv, Math.min(rec, R * cs / (1 + Math.sqrt(1 - cs * cs)))), adv, rec };
}

/** Highlight angle the light settles at. Physical: the light is world-up; its direction in the
 *  tube cross-section is atan2(across, normal) and a specular seen along the normal sits at half
 *  that angle. Face up → centre row; roll toward the top edge → highlight climbs toward it.
 *  Blended with the fixed style angle `lightAngle` by `lightPhys`. */
export function lightRest(along: number, across: number, p: Params): number {
  // float32 step for step as physics.cpp (the light's held steps compare its spring: perf-cheap A)
  const a = F(along), c = F(across);
  const n = F(Math.sqrt(Math.max(0, F(F(1 - F(a * a)) - F(c * c)))));
  const phys = F(F(F(F(Math.atan2(c, n)) * 180) / F(Math.PI)) / 2);
  // Vertical watch: held upright the cross-section sees almost no gravity and the angle is noise — fade to the
  // style angle as that component vanishes (full weight from 0.5 g).
  const w = p.vertical ? Math.min(1, F(2 * F(Math.sqrt(F(F(c * c) + F(n * n)))))) : 1;
  return F(F(p.lightAngle) + F(F(F(phys - F(p.lightAngle)) * F(p.lightPhys)) * w));
}

function dz(v: number, d: number): number {
  return Math.abs(v) < d ? 0 : v - Math.sign(v) * d;
}

/** One physics step of a tube; `k`: its px scale (spec/layout TUBE_PX_SCALE), `p` its params (boardParams at k). */
export function stepTube(s: TubeState, inp: TiltInput, p: Params, dt: number, k: number): void {
  const FILL_SLOSH_MAX_PX = fillSloshMaxPx(k), CAP_DYN_MAX_PX = capDynMaxPx(k), FILM_FULL_PX_S = filmFullPxS(k);
  const along = dz(inp.along, p.deadzone);
  const across = dz(inp.across, p.deadzone);

  // Pose uses filtered gravity before the artistic gain/deadzone. Both tilt axes count.
  // A smooth band releases the slug without a mode boundary or a timed reading gesture.
  const gain = p.inputGain > 0 ? p.inputGain : 1;
  const poseAlong = inp.along / gain, poseAcross = inp.across / gain;
  const hold = Math.max(0, Math.min(30, p.playHold));
  s.playTimer = Math.max(0, Math.min(hold, s.playTimer) - dt);
  s.playWindow = Math.max(0, s.playWindow - dt);
  if (!p.freeLiquid || hold === 0) {
    s.playTimer = s.playWindow = 0; s.playInit = false;
  } else if (!s.playInit) {
    s.playAnchorAlong = poseAlong; s.playAnchorAcross = poseAcross; s.playInit = true;
  } else {
    // Remember substantial excursions, ignoring small jitter. One move can be lowering/raising
    // an arm; an opposing move soon afterwards is stronger evidence of intentional play.
    const da = poseAlong - s.playAnchorAlong, dc = poseAcross - s.playAnchorAcross;
    const distance = Math.hypot(da, dc);
    if (distance >= PLAY_STROKE_G) {
      const reversal = s.playWindow > 0 && da * s.playDirAlong + dc * s.playDirAcross < -0.5 * distance;
      if (reversal || s.playTimer > 0) s.playTimer = hold;
      s.playDirAlong = da / distance; s.playDirAcross = dc / distance;
      s.playAnchorAlong = poseAlong; s.playAnchorAcross = poseAcross;
      s.playWindow = PLAY_REVERSAL_S;
    }
  }
  // Vertical watch: the reading pose is upright, bottom end down — gravity toward the bottom end is no tilt; what
  // counts is gravity toward the top end (turned over) or across the tube (laid on its side).
  const tilt = Math.asin(Math.min(1, Math.hypot(p.vertical ? Math.max(0, inp.along) : inp.along, inp.across) / gain)) * 180 / Math.PI;
  const start = Math.max(0, Math.min(89, p.readTiltStart));
  const end = Math.max(start + 1, Math.min(90, p.readTiltEnd));
  const t = Math.max(0, Math.min(1, (tilt - start) / (end - start)));
  const readTarget = p.freeLiquid ? (s.playTimer > 0 ? 0 : 1 - t * t * (3 - 2 * t)) : 1;
  s.reading += (readTarget - s.reading) * Math.min(1, 4 * dt);
  const flow = p.freeLiquid ? 1 - s.reading : 1;

  // Fill-edge slosh: static offset proportional to along-tilt; spring returns to rest.
  // Vertical watch: the along axis carries gravity itself, which the tube's closed bottom end takes — it is no
  // tilt offset for the edge or its light (the slug, the light angle and the film's drying still feel it).
  const sloshAlong = p.vertical ? 0 : along;
  const fillRest = Math.max(-FILL_SLOSH_MAX_PX, Math.min(FILL_SLOSH_MAX_PX, sloshAlong * p.fillSloshGain * flow));
  const fillKick = inp.gyroAcross * p.angleGyroGain * 4 * flow; // quick flicks kick the edge
  const fillAcc = -p.fillK * (s.fillPos - fillRest) - p.fillDamp * s.fillVel + fillKick;
  const fill0 = s.fillPos;
  s.fillVel += fillAcc * dt;
  s.fillPos += s.fillVel * dt;
  if (s.fillPos > FILL_SLOSH_MAX_PX) { s.fillPos = FILL_SLOSH_MAX_PX; s.fillVel = Math.min(0, s.fillVel); }
  if (s.fillPos < -FILL_SLOSH_MAX_PX) { s.fillPos = -FILL_SLOSH_MAX_PX; s.fillVel = Math.max(0, s.fillVel); }

  // Free liquid: the slug slides under the along component of gravity with viscous drag and
  // bounces off the tube ends; while reading, a critically damped pull parks it at its home end.
  const travel = Math.max(0, TUBE_LENGTH_PX - columnLen(s.fillTarget, p));
  const mir = mirrored(p);
  const home = mir ? travel : 0;
  let slugAcc = 0, slugStep = 0;   // px the slug really moved this tick (a wall stops it, whatever slugVel says)
  if (!p.freeLiquid) { s.slugPos = home; s.slugVel = 0; }
  else {
    slugAcc = flow * along * p.freeGain - p.freeDamp * s.slugVel
      + s.reading * (-p.freeHomeK * (s.slugPos - home) - 2 * Math.sqrt(p.freeHomeK) * s.slugVel);
    const v0 = s.slugVel, x0 = s.slugPos;
    s.slugVel += slugAcc * dt;
    s.slugPos += s.slugVel * dt;
    // At an end the wall carries the load (no forcing on the surface); the hit itself is an impulse.
    if (s.slugPos <= 0 || s.slugPos >= travel) {
      const wall = s.slugPos <= 0 ? 0 : travel;
      const hit = s.slugPos <= 0 ? s.slugVel < 0 : s.slugVel > 0;
      // Pressed into the wall it already sat on: resting contact, not an impact — no rebound, no speed.
      const resting = hit && Math.abs(x0 - wall) < 0.01;
      s.slugPos = wall;
      if (resting) s.slugVel = 0;
      else if (hit) s.slugVel = -s.slugVel * p.freeBounce;
      slugAcc = hit && !resting ? (s.slugVel - v0) / dt * 0.25 : 0;
    }
    slugStep = s.slugPos - x0;
  }

  // Meniscus wobble (panel frame, +x): the surface centre is pushed ahead of the pinned contact
  // lines by the forcing on the edge — the flick kick and the slug's acceleration, not the fill
  // spring's own restoring force, which is what keeps the column pinned — and springs back with a
  // wobble. A steadily moving line is the renderer's dynamic contact angle, not an offset here.
  const edgeVel = s.fillVel + s.slugVel, edgeAcc = fillKick + slugAcc;
  const capAcc = -p.meniscusK * s.cap - p.meniscusDamp * s.capVel + p.meniscusInertia * edgeAcc;
  s.capVel += capAcc * dt;
  s.cap += s.capVel * dt;
  if (s.cap > CAP_DYN_MAX_PX) { s.cap = CAP_DYN_MAX_PX; s.capVel = Math.min(0, s.capVel); }
  if (s.cap < -CAP_DYN_MAX_PX) { s.cap = -CAP_DYN_MAX_PX; s.capVel = Math.max(0, s.capVel); }

  // Wet film: fast attack while an edge recedes (moves toward the liquid), slow drain.
  const recede = mir ? 1 : -1;   // panel-frame direction the time edge moves when receding
  const filmT = (v: number): number => Math.max(0, Math.min(1, v / FILM_FULL_PX_S));
  const follow = (cur: number, target: number): number => cur + (target - cur) * Math.min(1, (target > cur ? 15 : 2) * dt);
  s.filmFree = follow(s.filmFree, filmT(recede * edgeVel));
  s.filmHome = follow(s.filmHome, p.freeLiquid ? filmT(-recede * s.slugVel) : 0);

  // Dried traces: the mid-row edges the renderer draws (meniscus detail skipped — the residue is
  // behind the contact line anyway), in the panel frame. An edge that receded leaves its film on the
  // columns it uncovered, all of it wet. Gravity runs the wet film down the tube (drainTrace) — into the
  // liquid where it reaches it, onto the tube end where it does not — while it evaporates over traceDry,
  // leaving traceStain of itself as a stain that fades at the same rate. Tilt moves the film, it does
  // not dry it. A per-column hash scatters the rates and the stain share: the smear dissolves unevenly,
  // patches linger. Toggling off empties the buffers.
  if (p.traces) {
    const len = columnLen(s.fillTarget, p);
    const fp = Math.max(-len, Math.min(len, s.fillPos));
    const xt = mir ? s.slugPos + fp : (p.freeLiquid ? s.slugPos : 0) + len + fp;
    const xh = mir ? len + s.slugPos : p.freeLiquid ? s.slugPos : 0;
    if (!s.traceInit) s.traceInit = true;
    else {
      // the time edge recedes toward -x when filling (!remaining), toward +x when draining;
      // the home edge only moves for a free slug and recedes the opposite way. The deposit is the film
      // the line leaves at its speed (filmEta, relative to FILM_ETA_MAX): a fast stretch of a slide lays
      // a thicker film than a slow one, a creeping line next to none. The uncovered columns were under
      // the liquid, which dissolved whatever lay there: a deposit too thin to count clears them.
      const dep = (a: number, b: number): void => {
        if (b <= a) return;
        let v = Math.round(TRACE_FULL * filmEta(p, (b - a) / dt, FILM_FULL_PX_S) / FILM_ETA_MAX);
        if (v < TRACE_MIN) v = 0;
        const lo = Math.max(0, Math.round(a)), hi = Math.min(TUBE_LENGTH_PX, Math.round(a + Math.min(b - a, traceDepositMaxPx(k))));
        for (let x = lo; x < hi; x++) s.trace[x] = s.traceWet[x] = v;
        if (v && hi > lo) { if (lo < s.traceLo) s.traceLo = lo; if (hi > s.traceHi) s.traceHi = hi; }
      };
      if (mir) dep(s.xtPrev, xt); else dep(xt, s.xtPrev);
      if (p.freeLiquid) { if (mir) dep(xh, s.xhPrev); else dep(s.xhPrev, xh); }
    }
    s.xtPrev = xt; s.xhPrev = xh;
    // gravity along the tube as the pose sees it (no artistic gain or deadzone)
    drainTrace(s, p, Math.max(-1, Math.min(1, poseAlong)), dt);
    // film that ran into the liquid (or that the liquid ran over) rejoins it; the columns under the
    // liquid are [round(lo), round(hi)), the complement of where dep() lays its deposits
    const lo = Math.min(xt, xh), hi = Math.max(xt, xh);
    for (let x = Math.max(s.traceLo, Math.round(lo)), x1 = Math.min(s.traceHi, Math.round(hi)); x < x1; x++) {
      s.trace[x] -= s.traceWet[x]; s.traceWet[x] = 0;
    }
    // Linearised rates (dt·rate ≪ 1 always: caps below). Math.floor, not round-to-nearest — with a
    // slow traceDry the per-tick decrement is under half an LSB and rounding would stall forever;
    // floor keeps the decay monotone (worst case 1 LSB/tick ⇒ even the faintest stain clears).
    const dryK = Math.min(0.5, dt / Math.max(0.05, p.traceDry));
    let nLo = TUBE_LENGTH_PX, nHi = 0;   // the occupied range re-tightens as columns dry out
    for (let x = s.traceLo; x < s.traceHi; x++) {
      const v = s.trace[x];
      if (!v) continue;
      const h = traceUneven(x), k = dryK * (0.75 + 0.5 * ((h >>> 16) / 65535));
      const stain = p.traceStain * (0.7 + 0.3 * ((h & 0xffff) / 65535));
      // the wet film evaporates, leaving `stain` of itself on the glass; the stain fades
      const w = s.traceWet[x], dw = w * k;
      const nw = Math.floor(w - dw), nv = Math.floor(nw + (v - w) * (1 - k) + stain * dw);
      // only a dry column counts as gone below TRACE_MIN: a draining film splits into thin columns at its
      // front, and deleting those would make a tilted film vanish (the wet part evaporates 1 LSB a tick anyway)
      if (nw === 0 && nv < TRACE_MIN) { s.trace[x] = s.traceWet[x] = 0; continue; }
      s.trace[x] = nv; s.traceWet[x] = nw;
      if (x < nLo) nLo = x;
      nHi = x + 1;
    }
    s.traceLo = nLo; s.traceHi = nHi;
  } else if (s.traceInit) { s.traceInit = false; s.trace.fill(0); s.traceWet.fill(0); s.traceLo = TUBE_LENGTH_PX; s.traceHi = 0; }

  // Front skew: the screen is the tube's cross-section plane, so only the across component of
  // gravity (the one fizz rises against) tilts the front on screen. Along-tilt is out of plane.
  // Vertical watch: the surface of an upright column stays level, so the front settles at the tube's own in-plane
  // tilt from the vertical (whatever the material: viscosity only sets how fast, angleK / angleDamp), faded out
  // as the plane of the panel loses gravity (lying flat: no in-plane direction, only noise). The sign follows the
  // across component alone — the liquid lies on the low wall whichever end is down: turned over, the time edge
  // is the slug's hanging end and the level surface is its home edge, which the renderer leans the other way.
  // On its side (along ≈ 0) the lean sits at the cap, both ends on the low wall.
  // The skew and light springs in float32, step for step as physics.cpp (their held steps: perf-cheap A).
  const fd = F(dt), pa = F(F(inp.along) / F(gain)), pc = F(F(inp.across) / F(gain));
  const dzF = (v: number, d: number): number => (Math.abs(v) < d ? 0 : F(v - (v > 0 ? d : -d)));
  const fAlong = dzF(F(inp.along), F(p.deadzone)), fAcross = dzF(F(inp.across), F(p.deadzone));
  const aMax = p.vertical ? ANGLE_VERTICAL_MAX_DEG : Math.min(F(p.angleMax), ANGLE_HARD_MAX_DEG);
  const angleRest = Math.max(-aMax, Math.min(aMax, p.vertical
    ? F(F(F(Math.min(1, F(2 * F(Math.sqrt(F(F(pa * pa) + F(pc * pc)))))) * F(Math.atan2(pc, Math.abs(pa)))) * 180) / F(Math.PI))
    : F(fAcross * F(p.angleTiltGain))));
  const angleAcc = F(F(F(-F(p.angleK)) * F(s.angleRaw - angleRest)) - F(F(p.angleDamp) * s.angleVel));
  s.angleVel = F(s.angleVel + F(angleAcc * fd));
  s.angleRaw = F(s.angleRaw + F(s.angleVel * fd));
  if (s.angleRaw > aMax) { s.angleRaw = aMax; s.angleVel = Math.min(0, s.angleVel); }
  if (s.angleRaw < -aMax) { s.angleRaw = -aMax; s.angleVel = Math.max(0, s.angleVel); }
  [s.angle, s.angleMean] = quantHyst(s.angleRaw, s.angleMean, s.angle, ANGLE_Q_DEG, ANGLE_Q_HYST, dt);   // what the render reads
  s.angle = heldClamp(s.angle, s.angleRaw, aMax, ANGLE_Q_DEG);

  // Light: a full-bore pinned column does not move under roll; roll moves only the light.
  // Spring toward the rest angle, kicked by roll rate (gyro about the tube axis).
  const rest = lightRest(fAlong, fAcross, p);
  const lightAcc = F(F(F(F(-F(p.acrossK)) * F(s.lightRaw - rest)) - F(F(p.acrossDamp) * s.lightVel))
    + F(F(F(inp.gyroAlong) * F(p.acrossGyroGain)) * 10));
  s.lightVel = F(s.lightVel + F(lightAcc * fd));
  s.lightRaw = F(s.lightRaw + F(s.lightVel * fd));
  if (s.lightRaw > LIGHT_MAX_DEG) { s.lightRaw = LIGHT_MAX_DEG; s.lightVel = Math.min(0, s.lightVel); }
  if (s.lightRaw < -LIGHT_MAX_DEG) { s.lightRaw = -LIGHT_MAX_DEG; s.lightVel = Math.max(0, s.lightVel); }
  [s.light, s.lightMean] = quantHyst(s.lightRaw, s.lightMean, s.light, LIGHT_Q_DEG, LIGHT_Q_HYST, dt);
  s.light = heldClamp(s.light, s.lightRaw, LIGHT_MAX_DEG, LIGHT_Q_DEG);

  // Agitation: fast attack on gyro energy, slow decay.
  const shake = Math.min(1, ((Math.abs(inp.gyroAcross) + Math.abs(inp.gyroAlong)) / 200) * p.shakeGain);
  s.agitation += (shake - s.agitation) * Math.min(1, (shake > s.agitation ? 20 : 2) * dt);

  // Edge light: slow follower of along-tilt. +1 = gravity presses the liquid into the right
  // end (edge glows brighter), -1 = drains away from it (edge dims). Consumed by the renderer.
  s.edgeLight += (Math.max(-1, Math.min(1, sloshAlong)) - s.edgeLight) * Math.min(1, 5 * dt);
  s.acrossTilt += (Math.max(-1, Math.min(1, across)) - s.acrossTilt) * Math.min(1, 5 * dt);

  // Rear parallax, an approximate tilt-driven one: the eye stays put while the face turns, so the viewing direction
  // in the watch frame turns with the face; for an eye roughly above the face that is minus the change of in-plane
  // gravity. A rear wall `rearParallax` px deep then shifts toward the eye's side by about depth · Δg (rows down: an
  // across-tilt raising the top edge moves it up); behind liquid by that / liquidIor (its apparent depth, the
  // small-angle approximation). The tilt is high-passed (time constant rearParallaxSettle), so the shift settles
  // back after a turn: artificial settling, as parallax wallpapers do.
  if (!s.rearInit) { s.rearLpAlong = s.rearSmAlong = along; s.rearLpAcross = s.rearSmAcross = across; s.rearInit = true; }
  const rearA = Math.min(1, dt / Math.max(0.05, p.rearParallaxSettle));
  s.rearLpAlong += (along - s.rearLpAlong) * rearA;
  s.rearLpAcross += (across - s.rearLpAcross) * rearA;
  // the gate: no motion while swinging (activity above REAR_GATE_HI), full parallax on slow tilts / settling
  const smA = Math.min(1, dt / REAR_RATE_S), pA = s.rearSmAlong, pC = s.rearSmAcross;
  s.rearSmAlong += (along - s.rearSmAlong) * smA;
  s.rearSmAcross += (across - s.rearSmAcross) * smA;
  const dA = s.rearSmAlong - pA, dC = s.rearSmAcross - pC, rate = Math.sqrt(dA * dA + dC * dC) / dt;
  s.rearAct += (rate - s.rearAct) * Math.min(1, rate > s.rearAct ? dt * REAR_ACT_ATTACK : dt / REAR_ACT_DECAY_S);
  if (s.rearAct >= REAR_GATE_HI) s.rearLatch = true;
  s.rearQuiet = s.rearAct < REAR_GATE_LO ? s.rearQuiet + dt : 0;
  if (s.rearQuiet >= REAR_QUIET_S) s.rearLatch = false;
  const gu = Math.max(0, Math.min(1, (s.rearAct - REAR_GATE_LO) / (REAR_GATE_HI - REAR_GATE_LO)));
  const gate = s.rearLatch ? 0 : 1 - gu * gu * (3 - 2 * gu);
  const ease = Math.min(1, dt / REAR_EASE_S);
  s.rearSx += (gate * -p.rearParallax * (along - s.rearLpAlong) - s.rearSx) * ease;
  s.rearSy += (gate * -p.rearParallax * (across - s.rearLpAcross) - s.rearSy) * ease;
  const rearDx = s.rearSx, rearDy = s.rearSy;
  const rearInv = 1 / Math.max(1, p.liquidIor);
  s.rearX16 = Math.round(rearDx * 16); s.rearY16 = Math.round(rearDy * 16);
  s.rearX16w = Math.round(rearDx * rearInv * 16); s.rearY16w = Math.round(rearDy * rearInv * 16);

  // Pinned contact lines (contact-angle hysteresis): the tilt pressure moves each end's static lead — a
  // held line that would end up past θA / θR is re-seated on the band's edge, which moves nothing on
  // screen, so no line speed — then the edge's travel this tick (the slosh and the slug's real, wall-
  // clamped move) is taken up by the held ring until the lead reaches θA / θR, and only the rest drags the
  // line. Tremor-sized back-and-forth stays inside the band: the wall ring holds still instead of flipping
  // between the advancing and receding shapes. A held line creeps back to the static shape over
  // PIN_RELAX_S, which also keeps a parked slug's creep after its home (remaining mode) under 0.5 px.
  const lenNow = columnLen(s.fillTarget, p), tiltFree = -recede * s.edgeLight;
  const relax = 1 - Math.min(1, dt / PIN_RELAX_S);
  const seat = (held: number, lineV: number, tilt: number, out: number): [number, number] => {
    const c = contactLeads(p, lenNow, tilt, mmPerPxAt(k)), lo = c.rest - c.rec, hi = c.rest - c.adv;
    const moved = Math.max(lo, Math.min(hi, held * relax)) + out, pinned = Math.max(lo, Math.min(hi, moved));
    return [pinned, lineV + ((moved - pinned) / dt - lineV) * Math.min(1, 2 * dt)];
  };
  [s.pinFree, s.lineVFree] = seat(s.pinFree, s.lineVFree, tiltFree, -recede * (s.fillPos - fill0 + slugStep));
  [s.pinHome, s.lineVHome] = seat(s.pinHome, s.lineVHome, -tiltFree, recede * slugStep);
}

/** Sets the shown fill from the clock's (0..1). A wrap — the clock falling back by over half the scale, full →
 *  empty at the hour / at 12 — retracts the column over RETRACT_S, eased in and out, onto the clock as it runs
 *  on, instead of emptying the tube in one tick. `snap` (the clock was set) goes straight to it. */
export function followClock(s: TubeState, clock: number, dt = PHYS_DT, snap = false): void {
  if (snap) s.retract = 1;
  else if (clock < s.clockPrev - 0.5) { s.retract = 0; s.retractFrom = s.fillTarget; }
  s.clockPrev = clock;
  if (s.retract >= 1) { s.fillTarget = clock; return; }
  s.retract = Math.min(1, s.retract + dt / RETRACT_S);
  const u = s.retract;
  s.fillTarget = s.retractFrom + (clock - s.retractFrom) * u * u * (3 - 2 * u);
}

/** Continuous fill levels per the layout spec. */
export function fillLevels(d: Date): { hours: number; minutes: number; seconds: number } {
  const h = d.getHours() % 12, m = d.getMinutes(), s = d.getSeconds() + d.getMilliseconds() / 1000;
  return { hours: (h + (m + s / 60) / 60) / 12, minutes: (m + s / 60) / 60, seconds: s / 60 };
}

/** Tracks the magnitude of gravity as the sensor reports it (this QMI8658 reads ~0.94 g at rest).
 *  Normalising each sample by its own instantaneous |a| amplifies transients enormously — |a| dips
 *  toward 0 during the jerk/free-fall phase of any hand movement, so dividing by it multiplies the
 *  noise 3-5x. Divide by this slow EMA instead, floored so the divisor can never blow the signal up.
 *  Same maths goes into the firmware. */
export class GravityNorm {
  private mag = 1;
  private init = false;
  reset(): void { this.init = false; }
  /** Feed |a| of the current sample, get the divisor to use for it. */
  update(n: number): number {
    if (!this.init) { this.mag = n > 0.5 ? n : 1; this.init = true; }
    else this.mag += (n - this.mag) * 0.01; // tau ~2 s at 50 Hz: tracks sensor scale error, not motion
    return Math.max(0.5, this.mag);
  }
}

/** IMU conditioning: accel low-pass (gravity), gyro high-pass + deadzone + clamp (transients only).
 *  The accel path is two cascaded one-poles (12 dB/oct): a single pole lets enough of a sharp
 *  wrist-jerk spike through to visibly kick the springs. One-pole maths; same goes into firmware. */
export const GYRO_LP_HZ = 12; // smooths both gyro outputs: sensor noise otherwise twitches fizz/agitation
export class ImuFilter {
  private lpAlong = 0; private lpAcross = 0; private lpNormal = 0;    // stage 1
  private lpAlong2 = 0; private lpAcross2 = 0; private lpNormal2 = 0; // stage 2
  /** The physical pose of the last step (updatePose of the filtered gravity, no inputGain); kept over a reset. */
  readonly pose: Pose = { ...POSE_DEFAULT };
  /** A valid sample has set pose (before it POSE_DEFAULT, face up): the desk view's lid keeps τ 0 until then (firmware). */
  poseValid = false;
  /** Desk view: the stand's back tilt τ of the pose, 0 before a valid sample (firmware ImuFilter::backTilt). */
  backTilt(): number { return this.poseValid ? poseBackTilt(this.pose) : 0; }
  private hpPrevIn = 0; private hpPrevOut = 0;
  private lpGyroAcross = 0; private lpGyroAlong = 0;
  private init = false;
  reset(): void { this.init = false; this.hpPrevIn = this.hpPrevOut = 0; this.lpGyroAcross = this.lpGyroAlong = 0; }
  step(raw: TiltInput, p: Params, dt = PHYS_DT): TiltInput {
    // float32 step for step as physics.cpp ImuFilter::step: the springs whose held steps the render reads take these
    // (perf-cheap A); expf / atan2f / sqrtf as Math's, rounded once.
    const F = Math.fround, PI = F(Math.PI), fd = F(dt);
    // A tilt (gravity direction) can never exceed 1 g — anything beyond is linear acceleration.
    // Clip before filtering so a hard knock carries bounded energy into the springs.
    const c12 = F(1.2), clip = (v: number): number => (v < -c12 ? -c12 : v > c12 ? c12 : v);
    const iA = clip(F(raw.along)), iC = clip(F(raw.across)), iN = clip(F(raw.normal));
    if (!this.init) {
      this.lpAlong = this.lpAlong2 = iA; this.lpAcross = this.lpAcross2 = iC; this.lpNormal = this.lpNormal2 = iN;
      this.hpPrevIn = F(raw.gyroAcross); this.init = true;
    }
    const a = F(1 - F(Math.exp(F(F(F(-2 * PI) * F(p.accelLpHz)) * fd))));
    this.lpAlong = F(this.lpAlong + F(F(iA - this.lpAlong) * a));
    this.lpAcross = F(this.lpAcross + F(F(iC - this.lpAcross) * a));
    this.lpAlong2 = F(this.lpAlong2 + F(F(this.lpAlong - this.lpAlong2) * a));
    this.lpAcross2 = F(this.lpAcross2 + F(F(this.lpAcross - this.lpAcross2) * a));
    this.lpNormal = F(this.lpNormal + F(F(iN - this.lpNormal) * a));
    this.lpNormal2 = F(this.lpNormal2 + F(F(this.lpNormal - this.lpNormal2) * a));
    if (updatePose(this.pose, this.lpAlong2, this.lpAcross2, this.lpNormal2)) this.poseValid = true;
    let g: number;
    const gA = F(raw.gyroAcross);
    if (p.gyroHpHz <= 0) g = gA;
    else {
      const rc = F(1 / F(F(2 * PI) * F(p.gyroHpHz))), k = F(rc / F(rc + fd));
      g = F(k * F(F(this.hpPrevOut + gA) - this.hpPrevIn));
      this.hpPrevIn = gA; this.hpPrevOut = g;
    }
    const dzc = F(p.gyroDeadzone), mx = F(p.gyroMax);
    const cond = (v: number): number => {
      v = Math.abs(v) < dzc ? 0 : F(v - (v > 0 ? dzc : -dzc));
      return v < -mx ? -mx : v > mx ? mx : v;
    };
    const gl = F(1 - F(Math.exp(F(F(F(-2 * PI) * GYRO_LP_HZ) * fd))));
    this.lpGyroAcross = F(this.lpGyroAcross + F(F(cond(g) - this.lpGyroAcross) * gl));
    this.lpGyroAlong = F(this.lpGyroAlong + F(F(cond(F(raw.gyroAlong)) - this.lpGyroAlong) * gl));
    const ig = F(p.inputGain);
    return { along: F(this.lpAlong2 * ig), across: F(this.lpAcross2 * ig), gyroAlong: F(this.lpGyroAlong * ig), gyroAcross: F(this.lpGyroAcross * ig),
      normal: F(this.lpNormal2 * ig) };
  }
}
