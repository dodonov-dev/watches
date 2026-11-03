// Headless IMU replay check. Feeds realistic QMI8658 traces (rest bias as measured on the
// board 2026-08-20, wrist waves, hard flicks, free-fall dips, sustained 90° tilt, shaking)
// through the exact pipeline the sim uses on Web Serial input:
//   raw sample → axis map + GravityNorm (serial.ts) → ImuFilter → stepTube
// and asserts the liquid can never go crazy: edge deviation from the time-true fill stays
// inside a small window, angle/fillPos respect the hard caps, nothing goes non-finite.
//
// Run:  cd sim && npx tsc tools/replay-check.ts --outDir /tmp/replay-check --module commonjs \
//         --target es2021 --moduleResolution node --esModuleInterop \
//       && node /tmp/replay-check/tools/replay-check.js
// (compiled outside sim/ so package.json "type":"module" doesn't bite the CJS output)
import {
  ANGLE_HARD_MAX_DEG, ANGLE_VERTICAL_MAX_DEG, capDynMaxPx, fillSloshMaxPx, filmFullPxS, GravityNorm, ImuFilter, PHYS_DT,
  columnLen, contactLeads, drainTrace, mirrored, newTube, stepTube, type TiltInput,
} from '../src/physics';
import { DEFAULT_PARAMS, PRESETS, migrateParams, presetParams } from '../src/params';

// Constants copied from spec/layout.ts + render.ts edgeX so this file needs no '@spec' alias. The AMOLED (npm run
// check:imu sets LW_BOARD=amoled191): px scale K = 1.
const TUBE_LENGTH_PX = 536, TUBE_HEIGHT_PX = 72, K = 1;
const FILL_SLOSH_MAX_PX = fillSloshMaxPx(K), CAP_DYN_MAX_PX = capDynMaxPx(K), FILM_FULL_PX_S = filmFullPxS(K);
// axis map (spec/layout.ts): along = -ay, across = -ax, gyroAcross = gx
const mapSample = (s: number[], d: number): TiltInput =>
  ({ along: -s[1] / d, across: -s[0] / d, gyroAlong: s[4], gyroAcross: s[3] });
// Wall-row edge of the contact-angle meniscus (render.ts capShape / edgeCap at rest speed, no lens):
// the static angle shifted by the tilt pressure within the hysteresis band, the across sag, the wobble.
const MM_PER_PX = 0.083;
function edgeX(ry: number, xe: number, angleDeg: number, tilt: number, side: number, cap: number, len: number): number {
  const R = (TUBE_HEIGHT_PX - 1) / 2, d = (ry - R) / R, P = DEFAULT_PARAMS, rad = Math.PI / 180;
  const t0 = P.contactAngle * rad, hy = P.contactHyst * rad, lc = P.capLength, Rmm = R * MM_PER_PX;
  const cs = Math.max(Math.cos(Math.min(Math.PI, t0 + hy)), Math.min(Math.cos(Math.max(0, t0 - hy)),
    Math.cos(t0) - Rmm * len * MM_PER_PX * tilt / (4 * lc * lc)));
  const asym = (Rmm / lc) ** 2 * side * Math.sign(cs);
  const sphere = cs * R * d * d / (1 + Math.sqrt(Math.max(0, 1 - cs * cs * d * d)));
  return xe + Math.tan((angleDeg * Math.PI) / 180) * (ry - R) + sphere * Math.max(0, 1 + asym * d) - cap * d * d;
}

// deterministic noise
let seed = 42;
const rnd = (): number => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff - 0.5; };

// Samples are [ax, ay, az, gx, gy, gz] in g / dps, 50 Hz, matching the board's CSV.
// Board at rest (STATUS.md): a ≈ (-0.19, -0.06, +0.92) g (|a| ≈ 0.94), gyro bias ≈ (-1.4, 0, 0.4) dps.
const REST = [-0.19, -0.06, 0.92], GBIAS = [-1.4, 0, 0.4];
const noisy = (a: number[], g: number[], an = 0.01, gn = 0.6): number[] =>
  [a[0] + rnd() * an, a[1] + rnd() * an, a[2] + rnd() * an, g[0] + rnd() * gn, g[1] + rnd() * gn, g[2] + rnd() * gn];

function scenario(name: string, seconds: number, f: (t: number) => number[]): [string, number[][]] {
  const out: number[][] = [];
  for (let i = 0; i < seconds * 50; i++) out.push(f(i * PHYS_DT));
  return [name, out];
}

const scenarios: [string, number[][]][] = [
  scenario('rest 5 s (bias + noise)', 5, () => noisy(REST, GBIAS)),
  // wrist wave: ±50° about the across axis at 1.2 Hz — gravity swings along the tube
  scenario('wrist wave ±50° @1.2 Hz', 6, (t) => {
    const th = (50 * Math.PI / 180) * Math.sin(2 * Math.PI * 1.2 * t);
    const dth = 50 * 2 * Math.PI * 1.2 * Math.cos(2 * Math.PI * 1.2 * t); // deg/s
    return noisy([-0.19, -0.94 * Math.sin(th), 0.94 * Math.cos(th)], [GBIAS[0] + dth, 0, 0.4]);
  }),
  // hard flicks: 60 ms bursts of ±3 g linear accel + ±600 dps once a second
  scenario('flicks 3 g / 600 dps', 6, (t) => {
    const burst = t % 1 < 0.06 ? (Math.floor(t) % 2 ? 1 : -1) : 0;
    return noisy([REST[0], REST[1] + 3 * burst, REST[2]], [GBIAS[0] + 600 * burst, 0, 0.4]);
  }),
  // drop: 150 ms of ~free fall (|a| → 0.05 g) then a 2.5 g catch spike — the case that used
  // to explode with per-sample |a| normalisation
  scenario('free-fall dip + catch', 4, (t) => {
    const ph = t % 2;
    if (ph < 0.15) return noisy([0.01, 0.01, 0.05], [80 * rnd(), 0, 0], 0.005, 20);
    if (ph < 0.21) return noisy([0.3, -2.5, 1.2], [300 * rnd(), 0, 0], 0.05, 30);
    return noisy(REST, GBIAS);
  }),
  // sustained vertical: tube pointing straight down then straight up, 4 s each
  scenario('sustained ±90° tilt', 8, (t) =>
    noisy([-0.1, t < 4 ? -0.94 : 0.94, 0.05], GBIAS)),
  // vigorous shake: 8 Hz ±1.5 g along, ±0.5 g across
  scenario('shake 8 Hz ±1.5 g', 3, (t) =>
    noisy([REST[0] + 0.5 * Math.sin(2 * Math.PI * 8 * t + 1), REST[1] + 1.5 * Math.sin(2 * Math.PI * 8 * t), REST[2]],
      [GBIAS[0] + 200 * Math.cos(2 * Math.PI * 8 * t), 0, 0.4], 0.02, 5)),
];

const p = { ...DEFAULT_PARAMS, freeLiquid: false };
// Max distance the drawn edge may ever sit from the time-true fill edge (px):
// hard slosh cap + tan(hard angle cap)·(H/2) + |meniscus| (≤ a hemisphere, sagged) + wobble + 1 px slack.
const EDGE_BUDGET = FILL_SLOSH_MAX_PX + Math.tan((ANGLE_HARD_MAX_DEG * Math.PI) / 180) * (TUBE_HEIGHT_PX / 2)
  + (TUBE_HEIGHT_PX / 2) * (1 + (TUBE_HEIGHT_PX / 2 * 0.083 / DEFAULT_PARAMS.capLength) ** 2) + CAP_DYN_MAX_PX + 1;   // cap ≤ a hemisphere, sagged

let failures = 0;
const fail = (msg: string): void => { failures++; console.error('  FAIL', msg); };

for (const [name, samples] of scenarios) {
  const norm = new GravityNorm(), filt = new ImuFilter();
  const tubes = [newTube(), newTube()];
  tubes[0].fillTarget = 0.5; tubes[1].fillTarget = 0.02; // mid-tube and the fragile near-empty case
  let maxDev = 0, maxAngle = 0, maxFill = 0, maxIn = 0, maxCap = 0;
  for (const s of samples) {
    const d = norm.update(Math.hypot(s[0], s[1], s[2]));
    const inp = filt.step(mapSample(s, d), p);
    maxIn = Math.max(maxIn, Math.abs(inp.along), Math.abs(inp.across));
    for (const tube of tubes) {
      stepTube(tube, inp, p, PHYS_DT, K);
      if (!(isFinite(tube.fillPos) && isFinite(tube.angle) && isFinite(tube.light) && isFinite(tube.edgeLight)
        && isFinite(tube.cap) && isFinite(tube.filmFree) && isFinite(tube.slugPos) && isFinite(tube.reading)
        && isFinite(tube.pinFree) && isFinite(tube.pinHome) && isFinite(tube.lineVFree) && isFinite(tube.lineVHome)))
        { fail(`${name}: non-finite state`); break; }
      for (const ry of [0, TUBE_HEIGHT_PX >> 1, TUBE_HEIGHT_PX - 1]) {
        const dev = Math.abs(edgeX(ry, tube.fillTarget * TUBE_LENGTH_PX + tube.fillPos, tube.angle, tube.edgeLight, tube.acrossTilt, tube.cap, columnLen(tube.fillTarget, p)) - tube.fillTarget * TUBE_LENGTH_PX);
        maxDev = Math.max(maxDev, dev);
      }
      maxAngle = Math.max(maxAngle, Math.abs(tube.angle));
      maxFill = Math.max(maxFill, Math.abs(tube.fillPos));
      maxCap = Math.max(maxCap, Math.abs(tube.cap));
      if (tube.slugPos !== 0) fail(`${name}: pinned liquid moved (slugPos ${tube.slugPos})`);
    }
  }
  if (maxFill > FILL_SLOSH_MAX_PX + 1e-9) fail(`${name}: fillPos ${maxFill.toFixed(1)} px exceeds cap ${FILL_SLOSH_MAX_PX}`);
  if (maxAngle > ANGLE_HARD_MAX_DEG + 1e-9) fail(`${name}: angle ${maxAngle.toFixed(1)}° exceeds cap ${ANGLE_HARD_MAX_DEG}`);
  if (maxCap > CAP_DYN_MAX_PX + 1e-9) fail(`${name}: cap ${maxCap.toFixed(1)} px exceeds cap ${CAP_DYN_MAX_PX}`);
  if (maxDev > EDGE_BUDGET) fail(`${name}: edge deviation ${maxDev.toFixed(1)} px exceeds budget ${EDGE_BUDGET.toFixed(1)}`);
  if (maxIn > 1.2 * p.inputGain + 1e-9) fail(`${name}: filtered tilt ${maxIn.toFixed(2)} g exceeds clip`);
  console.log(`${failures ? '' : 'ok  '}${name}: edge dev ${maxDev.toFixed(1)} px (budget ${EDGE_BUDGET.toFixed(1)}), angle ${maxAngle.toFixed(1)}°, slosh ${maxFill.toFixed(1)} px, cap ${maxCap.toFixed(1)} px, tilt in ${maxIn.toFixed(2)} g`);
}

// Pinned contact lines: 9 Hz hand tremor (0.02 g, 2 dps) over a slow drift, the liquid pinned or parked
// for reading, must never drag a meniscus line — the wall ring holds still. The old model switched the
// contact angle between θA and θR on the sign of the edge velocity, i.e. on every tremor half-cycle.
// A deliberate wrist wave must still drag it.
{
  const tremor = (t: number): number[] => {
    const along = Math.sin((3 + Math.sin(0.7 * t)) * Math.PI / 180) + 0.02 * Math.sin(2 * Math.PI * 9 * t);
    const across = Math.sin((8 + Math.sin(0.5 * t)) * Math.PI / 180) + 0.012 * Math.sin(2 * Math.PI * 9 * t + 1);
    return noisy([-0.94 * across, -0.94 * along, 0.94 * Math.sqrt(1 - along * along - across * across)],
      [GBIAS[0] + 2 * Math.cos(2 * Math.PI * 9 * t), 0, 0.4]);
  };
  const cases: [string, number[][], boolean][] = [
    ['tremor', scenario('', 10, tremor)[1], false], ['wrist wave', scenarios[1][1], true]];
  for (const [name, samples, drags] of cases) for (const freeLiquid of [false, true]) for (const contactDyn of [8, 90]) {
    const pl = { ...DEFAULT_PARAMS, freeLiquid, contactDyn };
    const norm = new GravityNorm(), filt = new ImuFilter(), tube = newTube();
    tube.fillTarget = 0.5;
    // the time end's wall-ring lead as drawTube sees it (render.ts capShape, no sag / wobble) less its
    // static tilt shape — the pinned line's own part — and its tick-to-tick change: the old per-tick
    // velocity switch flipped it across the band (~9 px here) within two ticks; a line creeping at its
    // θA edge under tremor (Cox–Voinov, honey-grade contactDyn 90) moves it < 0.1 px per tick
    const lead = (): number => {
      const c = contactLeads(pl, columnLen(tube.fillTarget, pl), tube.edgeLight, MM_PER_PX), R = c.R;
      const g = (contactDyn * Math.PI / 180) ** 3 / FILM_FULL_PX_S;
      const th0 = Math.PI / 2 - 2 * Math.atan(Math.max(c.adv, Math.min(c.rec, c.rest - tube.pinFree)) / R);
      const th = Math.cbrt(Math.max(0, Math.min(Math.PI ** 3, th0 ** 3 + g * tube.lineVFree)));
      return R * Math.cos(th) / (1 + Math.sin(th)) - c.rest;
    };
    let maxV = 0, maxStep = 0, prev = NaN;
    samples.forEach((s, i) => {
      stepTube(tube, filt.step(mapSample(s, norm.update(Math.hypot(s[0], s[1], s[2]))), pl), pl, PHYS_DT, K);
      maxV = Math.max(maxV, Math.abs(tube.lineVFree), Math.abs(tube.lineVHome));
      const h = lead();
      if (i > 50) maxStep = Math.max(maxStep, Math.abs(h - prev));
      prev = h;
    });
    const tag = `contact lines, ${name}, ${freeLiquid ? 'free' : 'pinned'}, contactDyn ${contactDyn}`;
    const bad = drags ? maxV <= 1 : maxV > 0.5 || maxStep > 0.25;
    if (bad) fail(`${tag}: line speed ${maxV.toFixed(2)} px/s, ring step ${maxStep.toFixed(3)} px (${drags ? 'must be dragged' : 'must stay held'})`);
    else console.log(`ok  ${tag}: max line speed ${maxV.toFixed(2)} px/s, ring step ${maxStep.toFixed(3)} px/tick`);
  }
}

// Automatic liquid: remain bounded during motion, read indefinitely at gentle tilt, release
// at strong tilt, and return without a gyro gesture. Exercise both elapsed and remaining time.
{
  const pf = { ...DEFAULT_PARAMS, freeLiquid: true };
  for (const [name, samples] of scenarios) {
    const norm = new GravityNorm(), filt = new ImuFilter();
    const tube = newTube(); tube.fillTarget = 0.3;
    let bad = false;
    for (const s of samples) {
      const inp = filt.step(mapSample(s, norm.update(Math.hypot(s[0], s[1], s[2]))), pf);
      stepTube(tube, inp, pf, PHYS_DT, K);
      const travel = TUBE_LENGTH_PX - columnLen(tube.fillTarget, pf);
      if (!(isFinite(tube.slugPos) && tube.slugPos >= 0 && tube.slugPos <= travel + 1e-6)) { bad = true; break; }
    }
    if (bad) fail(`free liquid, ${name}: slug left the tube (${tube.slugPos})`);
    else console.log(`ok  free liquid, ${name}: slug ${tube.slugPos.toFixed(1)} px, reading ${tube.reading.toFixed(2)}`);
  }
  for (const remaining of [false, true]) for (const fill of [0, 0.02, 0.3, 0.98, 1]) {
    const pp = { ...pf, remaining };
    const tube = newTube(); tube.fillTarget = fill;
    const travel = TUBE_LENGTH_PX - columnLen(fill, pp), home = remaining ? travel : 0;
    const sign = remaining ? -1 : 1;
    const filt = new ImuFilter();
    const step = (along: number, across: number, n: number) => {
      for (let i = 0; i < n; i++) {
        stepTube(tube, filt.step({ along, across, gyroAlong: 0, gyroAcross: 0 }, pp), pp, PHYS_DT, K);
        if (!Number.isFinite(tube.slugPos) || tube.slugPos < 0 || tube.slugPos > travel + 1e-6)
          throw new Error(`automatic liquid escaped: ${tube.slugPos}, travel ${travel}`);
      }
    };
    step(sign * 0.9, 0, 250);
    if (tube.reading > 0.01 || Math.abs(tube.slugPos - home) < travel - 5)
      fail(`automatic liquid: did not release (remaining=${remaining}, fill=${fill})`);
    step(sign * 0.2, 0.1, 200);
    if (tube.reading < 0.99 || Math.abs(tube.slugPos - home) > 0.1 || Math.abs(tube.fillPos) > 0.1)
      fail(`automatic liquid: did not return to accurate time (remaining=${remaining}, fill=${fill}, pos=${tube.slugPos})`);
    step(sign * 0.2, 0.1, 3000); // a full minute: no timeout, no turn required
    if (tube.reading < 0.99 || Math.abs(tube.slugPos - home) > 0.01 || Math.abs(tube.fillPos) > 0.01)
      fail('automatic liquid: reading drifted while held');
    step(sign * 0.9, 0, 250);
    if (tube.reading > 0.01 || Math.abs(tube.slugPos - home) < travel - 5)
      fail('automatic liquid: failed to release again');
  }
  console.log('ok  automatic liquid: tilt → read → hold 60 s → tilt, both directions and fill extremes');

  // Vertical watch: upright (bottom end down) is the reading pose and a true rest — no bounce, no film, no slosh;
  // the surface stays level against a sideways tilt whatever the material; turned over, a free slug lets go.
  for (const freeLiquid of [false, true]) for (const remaining of [false, true]) for (const viscous of [false, true]) {
    const pp = { ...DEFAULT_PARAMS, vertical: true, freeLiquid, remaining, ...(viscous ? { angleTiltGain: 1.5, angleMax: 3 } : {}) };
    const tube = newTube(); tube.fillTarget = 0.3;
    const travel = TUBE_LENGTH_PX - columnLen(0.3, pp), filt = new ImuFilter();
    const tag = `vertical (free=${freeLiquid}, remaining=${remaining}, viscous=${viscous})`;
    const step = (along: number, across: number, n: number) => { for (let i = 0; i < n; i++) stepTube(tube, filt.step({ along, across, gyroAlong: 0, gyroAcross: 0 }, pp), pp, PHYS_DT, K); };
    const still = () => Math.abs(tube.slugPos) < 0.01 && tube.slugVel === 0 && tube.filmHome < 0.01 && Math.abs(tube.fillPos) < 0.01;
    step(-1, 0, 500);
    if (tube.reading < 0.99 || !still() || Math.abs(tube.angle) > 0.5 || Math.abs(tube.edgeLight) > 0.01)
      fail(`${tag}: upright is not a rest (reading ${tube.reading}, slug ${tube.slugPos} @ ${tube.slugVel}, film ${tube.filmHome}, slosh ${tube.fillPos}, angle ${tube.angle})`);
    step(-0.866, 0.5, 500);
    if (Math.abs(tube.angle - 30) > 1 || !still()) fail(`${tag}: 30° sideways: angle ${tube.angle}, slug ${tube.slugPos} @ ${tube.slugVel}`);
    step(-0.866, -0.5, 500);
    if (Math.abs(tube.angle + 30) > 1 || !still()) fail(`${tag}: -30° sideways: angle ${tube.angle}, slug ${tube.slugPos} @ ${tube.slugVel}`);
    // turned over and tilted sideways: the time edge is the hanging end, still leaning onto the low wall (the level
    // surface is the home edge, drawn with the opposite lean); on its side: at the cap, the same way, no flipping
    for (const side of [0.5, -0.5]) {
      step(0.866, side, 500);
      if (Math.abs(tube.angle - Math.sign(side) * 30) > 1) fail(`${tag}: inverted, across ${side}: angle ${tube.angle}`);
    }
    for (const along of [0.05, 0, -0.05]) {
      step(along, 1, 500);
      if (Math.abs(tube.angle - ANGLE_VERTICAL_MAX_DEG) > 0.5) fail(`${tag}: on its side (along ${along}): angle ${tube.angle}`);
    }
    step(-1, 0, 500);
    step(0, 0, 500);
    if (Math.abs(tube.angle) > 0.5 || tube.reading < 0.99 || Math.abs(tube.slugPos) > 0.01 || Math.abs(tube.slugVel) > 0.01 || Math.abs(tube.fillPos) > 0.01) fail(`${tag}: flat: angle ${tube.angle}, reading ${tube.reading}`);
    if (freeLiquid) {
      step(0.9, 0, 250);
      if (tube.reading > 0.01 || tube.slugPos < travel - 5 || tube.slugVel !== 0) fail(`${tag}: turned over: reading ${tube.reading}, slug ${tube.slugPos} @ ${tube.slugVel} of ${travel}`);
      step(-1, 0, 500);
      if (tube.reading < 0.99 || Math.abs(tube.slugPos) > 0.01 || Math.abs(tube.slugVel) > 0.01) fail(`${tag}: did not return upright (reading ${tube.reading}, slug ${tube.slugPos})`);
    }
  }
  console.log('ok  vertical watch: upright rest, low-wall lean at ±30° upright and inverted, on its side, flat, turned over and back');

  // Both axes and diagonals use the physical angle, independent of artistic input gain/deadzone.
  for (const inputGain of [0.1, 1, 2]) for (const axis of ['along', 'across', 'diagonal']) {
    const pp = { ...pf, inputGain, deadzone: 0.2 };
    const tube = newTube(); tube.fillTarget = 0.3;
    const filt = new ImuFilter();
    let prev = 1;
    for (const degrees of [0, 20, 25, 35, 45, 50, 80]) {
      const g = Math.sin(degrees * Math.PI / 180);
      const raw = { along: axis === 'across' ? 0 : g / (axis === 'diagonal' ? Math.SQRT2 : 1),
        across: axis === 'along' ? 0 : g / (axis === 'diagonal' ? Math.SQRT2 : 1), gyroAlong: 0, gyroAcross: 0 };
      for (let i = 0; i < 250; i++) stepTube(tube, filt.step(raw, pp), pp, PHYS_DT, K);
      if (tube.reading > prev + 1e-6) fail('automatic liquid: release is not monotonic');
      if (degrees <= 20 && tube.reading < 0.999) fail('automatic liquid: gentle tilt released');
      if (degrees === 35 && Math.abs(tube.reading - 0.5) > 0.001) fail('automatic liquid: midpoint depends on axis/gain');
      if (degrees >= 50 && tube.reading > 0.001) fail('automatic liquid: strong tilt held');
      prev = tube.reading;
    }
  }
  console.log('ok  automatic liquid: smooth viewing band across axes and input gains');

  // Every liquid material must return home with its own drag/spring tuning: from up to 200 px off its home end
  // (the far end in the mirrored frame), a gentle tilt away from home held against it. A slug left always free
  // (no home pull, freeHomeK 0) is never parked: it must slide home under a tilt toward that end and rest there.
  for (const e of PRESETS) {
    const pp = presetParams(e), tube = newTube(); tube.fillTarget = 0.3; tube.reading = 0;
    const travel = TUBE_LENGTH_PX - columnLen(tube.fillTarget, pp), home = mirrored(pp) ? travel : 0, away = home ? -1 : 1;
    const parks = pp.freeHomeK > 0;
    tube.slugPos = home + away * Math.min(200, travel);
    const along = (parks ? 0.2 : -0.9) * away * pp.inputGain, n = parks ? 250 : 500;
    for (let i = 0; i < n; i++) stepTube(tube, { along, across: 0, gyroAlong: 0, gyroAcross: 0 }, pp, PHYS_DT, K);
    if (!(Math.abs(tube.slugPos - home) <= 0.1) || !(Math.abs(tube.slugVel) <= 0.1))
      fail(`${e.id}: ${parks ? 'reading did not settle' : 'free slug did not come to rest at home'} (${tube.slugPos} @ ${tube.slugVel}, home ${home})`);
  }
  const migrated = migrateParams({ v: 15, freeLiquid: true, readFaceUp: 1, readTurn: 125, readHold: 11 });
  if (migrated.readTiltStart !== 20 || migrated.readTiltEnd !== 50 || 'readTurn' in migrated)
    fail('automatic liquid: legacy gesture settings did not migrate');
  for (const [start, end] of [[50, 20], [90, 90], [0, 0]]) {
    const pp = { ...pf, readTiltStart: start, readTiltEnd: end }, tube = newTube();
    for (let i = 0; i < 100; i++) stepTube(tube, { along: 0.7, across: 0.7, gyroAlong: 0, gyroAcross: 0 }, pp, PHYS_DT, K);
    if (!Number.isFinite(tube.reading) || tube.reading < 0 || tube.reading > 1) fail('automatic liquid: invalid band produced invalid state');
  }
  console.log('ok  automatic liquid: material presets, legacy settings and overlapping thresholds');
}
// Play needs opposite substantial tilts, then remains free through the viewing angle.
// Use the real filter and gradual movements, including roll and low/high artistic gains.
for (const axis of ['along', 'across', 'diagonal']) for (const inputGain of [0.1, 1, 2]) {
  const pp = { ...DEFAULT_PARAMS, inputGain }, tube = newTube(), filter = new ImuFilter();
  tube.fillTarget = 0.3;
  let position = 0;
  const move = (target: number, seconds: number) => {
    const from = position, n = Math.round(seconds / PHYS_DT);
    for (let i = 0; i < n; i++) {
      position = from + (target - from) * (i + 1) / n;
      const raw = { along: axis === 'across' ? 0 : position / (axis === 'diagonal' ? Math.SQRT2 : 1),
        across: axis === 'along' ? 0 : position / (axis === 'diagonal' ? Math.SQRT2 : 1), gyroAlong: 0, gyroAcross: 0 };
      stepTube(tube, filter.step(raw, pp), pp, PHYS_DT, K);
      if (!Number.isFinite(tube.slugPos) || tube.slugPos < 0 || tube.slugPos > TUBE_LENGTH_PX - columnLen(tube.fillTarget, pp) + 1e-6)
        fail('play: slug escaped');
    }
  };
  const expectNoPlay = (label: string) => { if (tube.playTimer > 0) fail(`play: ${label} triggered a hold (${axis}, gain ${inputGain})`); };
  move(0, 0.5);
  move(0.9, 0.6); // lower arm: one stroke, then leave it down
  expectNoPlay('single lowering');
  move(0.9, 8);
  expectNoPlay('steady hand down');
  move(0, 0.6); move(0, 2);
  expectNoPlay('single raise to read');
  if (tube.reading < 0.99) fail('play: ordinary raise delayed reading');
  move(0.9, 5); move(0, 5);
  expectNoPlay('slow posture changes');
  for (let i = 0; i < 100; i++) move(i % 2 ? 0.02 : -0.02, 0.04);
  expectNoPlay('small jitter');

  move(0.8, 0.5); move(-0.8, 0.7); move(0.1, 0.4); move(0.1, 1);
  if (tube.playTimer < 3 || tube.reading > 0.01) fail(`play: back-and-forth did not hold free (${axis}, gain ${inputGain})`);
  const left = tube.playTimer;
  move(0.1, 1);
  if (Math.abs(tube.playTimer - (left - 1)) > 1e-5) fail('play: steady pose refreshed the timer');
  move(0.8, 0.5);
  if (tube.playTimer < pp.playHold - 0.5) fail('play: further tilt did not refresh');
  move(0.1, 0.5); move(0.1, pp.playHold + 4);
  if (tube.playTimer !== 0 || tube.reading < 0.99 || Math.abs(tube.slugPos) > 0.1)
    fail('play: failed to settle home after expiry');

  move(-0.8, 0.5); move(0.8, 0.7); move(0.8, pp.playHold + 1);
  if (tube.playTimer !== 0 || tube.reading > 0.01) fail('play: expiry at steep tilt should retain ordinary free flow');
  move(0, 0.6); move(0, 3);
  expectNoPlay('raise after play expired while down');

  move(0.8, 0.5); move(-0.8, 0.7);
  pp.freeLiquid = false; move(0, 0.5);
  if (tube.playTimer !== 0 || tube.slugPos !== 0) fail('play: pinned override did not cancel');
  pp.freeLiquid = true; pp.playHold = 0;
  move(0.8, 0.5); move(-0.8, 0.7); move(0, 0.5); move(0, 3);
  if (tube.playTimer !== 0 || tube.reading < 0.99) fail('play: zero duration did not disable the hold');
}
console.log('ok  play hold: intentional reversals, refresh, expiry, quiet poses, slow motion, axes/gains and overrides');
const previousTilt = migrateParams({ v: 16, readTiltStart: 15, readTiltEnd: 60 });
if (previousTilt.playHold !== 5 || previousTilt.readTiltStart !== 15 || previousTilt.readTiltEnd !== 60)
  fail('play: migration lost custom viewing angles');
if (migrateParams({ v: 17, playHold: 0 }).playHold !== 0) fail('play: migration lost disabled hold');

// Residue physics: the deposit is the film a receding line leaves (thicker the faster for a watery liquid,
// saturated for a syrup); gravity runs the wet part down the tube into the liquid, conservatively; tilt
// moves it, never dries it. A pinned column (liquid on [0, len)), the vertical watch (no slosh offset).
{
  const res = (o: Partial<typeof DEFAULT_PARAMS>) => ({ ...DEFAULT_PARAMS, traces: true, freeLiquid: false, vertical: true, inputGain: 1, ...o });
  const sum = (t: { trace: Uint16Array }): number => t.trace.reduce((a, v) => a + v, 0);
  const centroid = (t: { trace: Uint16Array }): number => { let m = 0, x = 0; t.trace.forEach((v, i) => { m += v; x += v * i; }); return m ? x / m : 0; };
  const run = (tube: ReturnType<typeof newTube>, pp: typeof DEFAULT_PARAMS, along: number, seconds: number, fillRate = 0): void => {
    for (let i = 0; i < seconds * 50; i++) { tube.fillTarget += fillRate * PHYS_DT; stepTube(tube, { along, across: 0, gyroAlong: 0, gyroAcross: 0 }, pp, PHYS_DT, K); }
  };
  // a line receding at U px/s for 0.4 s from 0.8 full: the densest deposit it laid
  const deposit = (contactDyn: number, U: number): number => {
    const pp = res({ contactDyn, traceDrain: 0, traceDry: 2 }), tube = newTube(); tube.fillTarget = 0.8;
    run(tube, pp, 0, 0.1); run(tube, pp, 0, 0.4, -U / TUBE_LENGTH_PX);
    return Math.max(...tube.trace);
  };
  const w20 = deposit(8, 20), w80 = deposit(8, 80), h20 = deposit(90, 20), h80 = deposit(90, 80);
  if (!(w20 > 0 && w80 > 2.2 * w20 && w80 < 0.1 * 0xff00)) fail(`residue: watery deposit 20 / 80 px/s = ${w20} / ${w80} (microns, U^⅔: ×2.5)`);
  if (!(h20 > 0.8 * 0xff00 && h80 < 1.25 * h20)) fail(`residue: syrup deposit 20 / 80 px/s = ${h20} / ${h80} (near the cap whatever the speed)`);
  // a thick wet film above the liquid of an upright tube (along -1: gravity toward the liquid at x < 268)
  const film = (pp: typeof DEFAULT_PARAMS): ReturnType<typeof newTube> => {
    const tube = newTube(); tube.fillTarget = 0.5; run(tube, pp, 0, 0.02);
    for (let x = 300; x < 340; x++) tube.trace[x] = tube.traceWet[x] = 0xff00;
    tube.traceLo = 300; tube.traceHi = 340; return tube;
  };
  const slow = res({ contactDyn: 90, traceDrain: 25, traceDry: 1000 });
  const up = film(slow), m0 = sum(up), c0 = centroid(up);
  run(up, slow, -1, 0.3);
  if (!(centroid(up) < c0 - 5 && sum(up) <= m0)) fail(`residue: upright film did not run down (centroid ${c0} → ${centroid(up)}, mass ${m0} → ${sum(up)})`);
  run(up, slow, -1, 2);
  // the thick front runs in; the tail thins as it drains and slows with h² (its front spreads as t^⅓),
  // so it lingers and dries in place
  if (sum(up) > 0.9 * m0) fail(`residue: upright film did not rejoin the liquid (${sum(up)} of ${m0} left)`);
  // a watery film as a 25 px/s line leaves it (~900), with a mobility that makes it run (~25 px/s; water's own
  // ~2400 barely moves it): drained upright it must not thin away on the way — a draining film splits into
  // sub-TRACE_MIN columns at its front, which are wet, not gone
  const thin = res({ contactDyn: 8, traceDrain: 127000, traceDry: 2, traceStain: 1 });
  const thinFilm = (along: number): number => {
    const tube = newTube(); tube.fillTarget = 0.5; run(tube, thin, 0, 0.02);
    for (let x = 300; x < 340; x++) tube.trace[x] = tube.traceWet[x] = 895;
    tube.traceLo = 300; tube.traceHi = 340; run(tube, thin, along, 0.4); return sum(tube);
  };
  const tFlat = thinFilm(0), tUp = thinFilm(-1);
  if (Math.abs(tUp / tFlat - 1) > 0.02) fail(`residue: a thin draining film lost mass on the way (${tUp} upright vs ${tFlat} flat after 0.4 s)`);
  // the flux alone, turned over (away from the liquid): exactly conservative, it pools on the tube end
  const over = film(slow), o0 = sum(over);
  for (let i = 0; i < 50 * 80; i++) drainTrace(over, slow, 1, PHYS_DT);
  if (!(sum(over) === o0 && over.trace[TUBE_LENGTH_PX - 1] === 0xff00 && over.trace.every((v, i) => over.traceWet[i] === v && v <= 0xff00)))
    fail(`residue: inverted film lost mass or did not pool (${o0} → ${sum(over)}, end column ${over.trace[TUBE_LENGTH_PX - 1]})`);
  // flat: it stays put; tilted away from the liquid: it moves but dries no faster
  const dry = res({ contactDyn: 90, traceDrain: 25, traceDry: 1, traceStain: 0.5 });
  const flat = film(dry), tilt = film(dry), f0 = centroid(tilt);
  run(flat, dry, 0, 1); run(tilt, dry, 1, 1);
  if (flat.trace.some((v, i) => v > 0 && (i < 300 || i >= 340))) fail('residue: a flat tube moved its film');
  if (!(centroid(tilt) > f0 + 5)) fail(`residue: tilted film did not run down (${f0} → ${centroid(tilt)})`);
  if (Math.abs(sum(tilt) / sum(flat) - 1) > 0.05) fail(`residue: tilt changed the drying (${sum(tilt)} vs ${sum(flat)} flat)`);
  console.log(`ok  residue: deposit watery ${w20} → ${w80}, syrup ${h20} → ${h80}; upright film runs into the liquid, inverted pools at the end, flat stays, tilt does not dry`);
  // A drop (the repro pose: a vertical watch turned over and on its side, so the free slug slides up and its home
  // edge recedes): the line speeds up as it goes, so the residue is densest right behind it, next to the liquid.
  {
    const pp = res({ freeLiquid: true, contactDyn: 8, traceDrain: 2377, traceDry: 1.7, traceStain: 1, freeGain: 840, freeDamp: 7, freeHomeK: 150 });
    const tube = newTube(); tube.fillTarget = 0.4;
    const pose = (along: number, across: number, seconds: number): void => {
      for (let i = 0; i < seconds * 50; i++) stepTube(tube, { along, across, gyroAlong: 0, gyroAcross: 0 }, pp, PHYS_DT, K);
    };
    pose(-1, 0, 2); pose(0.7, 0.7, 2.5);   // mid-slide (terminal ~84 px/s, ~320 px of travel)
    // the trail from where the slide started (x = 0) to the line, in 10 px bins: densest in the last one
    const xs = Math.round(tube.slugPos), bins: number[] = [];
    for (let a = 0; a + 10 <= xs; a += 10) { let m = 0; for (let x = a; x < a + 10; x++) m += tube.trace[x]; bins.push(m / 10); }
    const near = bins[bins.length - 1] ?? 0, start = bins[0] ?? 0;
    if (!(xs > 100 && near === Math.max(...bins) && near > 2 * start)) fail(`residue: a drop's densest residue is not next to the liquid (slug at ${xs}, bins ${bins.map((v) => v.toFixed(0)).join(' ')})`);
    else console.log(`ok  residue: a drop (slug at ${xs} px) leaves ${near.toFixed(0)} right behind its line, ${start.toFixed(0)} where it started`);
  }
}
if (failures) throw new Error(`${failures} failure(s)`);
console.log('all scenarios within bounds');
