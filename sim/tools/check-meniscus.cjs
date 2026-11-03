// Full-render regression checks. Invoked by firmware/tools/check_meniscus.py.
const fs = require('fs');
const assert = require('assert/strict');
const path = require('path');
const [cache, out, root] = process.argv.slice(2);
const R = require(path.join(cache, 'sim/src/render.js'));
const { DEFAULT_PARAMS, migrateParams } = require(path.join(cache, 'sim/src/params.js'));
// Contact angle whose spherical cap has wall depth `depth` px in the 61 px test tube (R = 30).
const ang = (depth) => 90 - 2 * Math.atan(depth / 30) * 180 / Math.PI;
const { newTube, columnLen, mirrored } = require(path.join(cache, 'sim/src/physics.js'));
const jobs = [];
// Sprite sheets decoded by check_meniscus.py (sprites/<name>.rgba), metadata from the sim's assets.
R.SPRITE_SHEETS.forEach((name, i) => {
  const rgba = path.join(out, 'sprites', name + '.rgba');
  if (!fs.existsSync(rgba)) return;
  const meta = JSON.parse(fs.readFileSync(path.join(root, 'sim/public/assets', name + '.png.json'), 'utf8'));
  const data = new Uint8ClampedArray(fs.readFileSync(rgba));
  const w = meta.cellW * 10, h = data.length / 4 / w;
  R.setSprite(i, { cellW: meta.cellW, cellH: meta.cellH, widths: meta.widths, data, w, h });
});
const base = { ...DEFAULT_PARAMS, tubeHeight: 61, hoursY: 0, minutesY: 100,
  freeLiquid: true, remaining: false, contactAngle: ang(12), contactHyst: 0, contactDyn: 0,
  meniscusLens: 0, surfaceBand: 0.8, surfaceRim: 0.8,
  surfaceWidth: 4, surfaceTone: 0, edgeSoft: 4, frontBright: 0, edgeGlow: 0,
  wetFilm: 0, traces: false, bubble: false, fizz: false, glassReflect: 0,
  lens: 0, highlightInset: 0, digits: false, ticksH: false, ticksM: false,
  liquid: '#226688', liquidHi: '#eeffff', liquidLo: '#113344',
  tubeBack: '#ffffff', tubeBack2: '#ffffff' };
// A state that moves an edge (fillVel / slugVel) stands for steady motion: its contact lines are dragged
// at that speed, seated on the advancing / receding edge of their band — the pinned-line state stepTube
// leaves behind (a large pin saturates the band whatever the tilt).
function steady(p, state) {
  if (!('fillVel' in state || 'slugVel' in state) || 'pinFree' in state) return state;
  const recede = p.remaining ? 1 : -1, vF = -recede * ((state.fillVel ?? 0) + (state.slugVel ?? 0)), vH = recede * (state.slugVel ?? 0);
  return { ...state, pinFree: Math.sign(vF) * 1000, lineVFree: vF, pinHome: Math.sign(vH) * 1000, lineVHome: vH };
}
function render(name, changes = {}, state = {}, preset = base, residue = false) {
  const p = { ...preset, ...changes };
  state = steady(p, state);
  const s = { ...newTube(), fillTarget: 0.5, slugPos: 134, ...state };
  // residue: true = a fresh deposit on every column, [lo, hi] = on those panel columns only
  if (residue) { const [lo, hi] = residue === true ? [0, 536] : residue; s.trace.fill(0xff00, lo, hi); s.traceLo = lo; s.traceHi = hi; }
  R.fb.fill(0);
  R.drawTube(0, 0, s, p, R.buildPalette(p, s.light), 12);
  const frame = R.fb.slice(0, 536 * R.tubeLayout(p).H);
  fs.writeFileSync(path.join(out, name + '.bin'), Buffer.from(frame.buffer));
  const params = Object.fromEntries(Object.entries(p).filter(([k, v]) => v !== DEFAULT_PARAMS[k]));
  jobs.push({ name, params, state: { fillTarget: 0.5, slugPos: 134, ...state }, residue, height: R.tubeLayout(p).H });
  return frame;
}
function rgb(v) { return [(v >> 11) * 255 / 31, ((v >> 5) & 63) * 255 / 63, (v & 31) * 255 / 31]; }
function delta(a, b) { let d = 0; for (let i = 0; i < a.length; i++) {
  const A = rgb(a[i]), B = rgb(b[i]); for (let c = 0; c < 3; c++) d = Math.max(d, Math.abs(A[c] - B[c]));
} return d; }
const symmetric = render('symmetric');
for (let y = 0; y < 61; y++) for (let x = 100; x < 170; x++)
  assert.equal(symmetric[y * 536 + x], symmetric[y * 536 + 535 - x], `mirror row ${y}, x ${x}`);
const a = render('subpixel-before', {}, { fillPos: 0.49 });
const b = render('subpixel-after', {}, { fillPos: 0.51 });
assert(delta(a, b) <= 17, 'surface/rim must move without a one-pixel brightness jump');
const flatA = render('flatten-before', { contactAngle: ang(0.49) });
const flatB = render('flatten-after', { contactAngle: ang(0.51) });
assert(delta(flatA, flatB) <= 17, 'flattening surface must not pop at half a pixel');
const clean = render('band-disabled', { surfaceBand: 0, traces: true, traceAmount: 2 }, {}, base, true);
const faint = render('band-faint', { surfaceBand: 0.005, traces: true, traceAmount: 2 }, {}, base, true);
assert(delta(clean, faint) <= 9, 'faint band must not cut a hole in residue');
const marks = { digits: true, digitFont: 0, digitParallax: 4, liquidTransparency: 0 };
const marksOff = render('marks-disabled', { ...marks, surfaceBand: 0 });
const marksFaint = render('marks-faint', { ...marks, surfaceBand: 0.005 });
assert(delta(marksOff, marksFaint) <= 9, 'faint band must not switch rear marks to a different plane');
const receding = render('receding', {}, { filmFree: 1, filmHome: 1 });
assert.equal(delta(receding, symmetric), 0, 'wet film must not fade the concave surface: it only changes shape');
// Receding at speed (dynamic contact angle ~0): the outer dish runs into the trail, no rim or outline
// past the body's AA ramp; the same edge at rest has its full band back at once, film or not.
const trail = { traces: true, traceAmount: 2 };
const fast = render('receding-fast', trail, { fillVel: -30, filmFree: 1 }, base, true);
const fastOff = render('receding-fast-disabled', { ...trail, surfaceBand: 0 }, { fillVel: -30, filmFree: 1 }, base, true);
for (let x = 405; x < 409; x++) assert(delta([fast[30 * 536 + x]], [fastOff[30 * 536 + x]]) <= 9, 'receding surface must not outline the trail');
const stopped = render('receding-stopped', trail, { filmFree: 1 }, base, true);
assert(delta(stopped.slice(30 * 536 + 403, 30 * 536 + 409), fastOff.slice(30 * 536 + 403, 30 * 536 + 409)) > 9, 'stopped edge must show its band');
// Rear marks under the concave band are composited per pixel by the dish's own layer opacities (no
// >= 0.5 threshold): with an opaque liquid a settled opaque band hides the mark behind it exactly like the
// body; a fast-receding edge's band thins into its trail and shows it; a flattening band (ring a fraction
// of a px off the profile) is barely there and shows it; the rim keeps most of its colour over a dark
// mark; fill 0.49 -> 0.51 moves nothing by more than a rounding step. Both edges, both fill directions.
// Wide black ticks the full tube height make the whole rear wall a mark; contrast 0 lets the through-
// liquid colour vanish at transparency 0.
const markScene = { ...marks, digits: false, markContrast: 0, ticksH: true, tickStepH: 1, tickMinorWidthH: 60, tickMajorWidthH: 60,
  tickMinorHeightH: 61, tickMajorHeightH: 61, tickColorH: '#000000', tickMajorColorH: '#000000' };
const black = 0;
for (const remaining of [false, true]) for (const home of [false, true]) {
  const recede = remaining ? 1 : -1;
  const moving = home ? { slugVel: -recede * 30 } : { fillVel: recede * 30 };
  const side = home ? 1 : 0, tag = `${remaining}/${home}`;
  // Band geometry at row 30 from the settled band-on frame (the edge does not move between these shots):
  // the 3 fully covered px past the profile, and the outer px where the rim sits (rimCoverage 1).
  render(`marks-${remaining}-${home}-geometry`, { ...markScene, remaining }, {});
  const b = R.markBounds[0].band, xm = b.xm[side][30], w0 = b.w[side][30];
  const dir = side === 0 ? 1 : -1, first = side === 0 ? Math.ceil(xm) : Math.ceil(xm) - 1;
  const at = (f, xr) => f[30 * 536 + (b.mirror ? b.L - 1 - xr : xr)];
  const shot = (changes, state) => {
    const f = render(`marks-${remaining}-${home}-${JSON.stringify(state)}-${JSON.stringify(changes)}`, { ...markScene, remaining, ...changes }, state);
    return { f, zone: [0, 1, 2].map((i) => at(f, first + dir * i)), rim: at(f, side === 0 ? Math.ceil(xm + 2.5) : Math.floor(xm - 3.5)) };
  };
  const zoneDelta = (a, b) => Math.max(...a.zone.map((v, i) => delta([v], [b.zone[i]])));
  const bare = shot({ surfaceBand: 0 }, {}), bareNoTicks = shot({ surfaceBand: 0, ticksH: false }, {});
  assert(zoneDelta(bare, bareNoTicks) > 150, `test scene must put a mark under the band (${tag})`);
  const rest = shot({}, {}), restNoTicks = shot({ ticksH: false }, {});
  assert(w0 >= 3.5, `settled band must reach its full width at the centre row (${tag}: ${w0})`);
  assert.equal(zoneDelta(rest, restNoTicks), 0, `settled opaque band must hide rear marks like the body (${tag})`);
  const pulled = shot({}, moving), pulledNoTicks = shot({ ticksH: false }, moving);
  assert(zoneDelta(pulled, pulledNoTicks) > 100, `receding band thinning into its trail must not hide rear marks (${tag})`);
  for (const depth of [0.2, 0.45]) {
    const contactAngle = ang(depth);
    const flat = shot({ contactAngle }, {}), flatNoTicks = shot({ contactAngle, ticksH: false }, {});
    assert(delta([flat.zone[0]], [flatNoTicks.zone[0]]) > 150, `flattening band must not hide rear marks (${tag}, depth ${depth})`);
  }
  // See-through dish (surfaceFill 0): the rim is drawn over the mark, not erased by it.
  const open = shot({ surfaceFill: 0 }, {}), openNoTicks = shot({ surfaceFill: 0, ticksH: false }, {});
  const kept = delta([open.rim], [openNoTicks.rim]), tick = delta([openNoTicks.rim], [black]);
  assert(tick > 100 && kept < 0.4 * tick, `rim must stay on top of rear marks (${tag}: moved ${kept} of ${tick})`);
  const fillA = shot({ surfaceFill: 0.49 }, {}), fillB = shot({ surfaceFill: 0.51 }, {});
  assert(delta(fillA.f, fillB.f) <= 17, `rear marks must follow the fill opacity without a jump (${tag})`);
  // The band overlaps the body by edgeSoft/2: the blick on the first body pixel inside the profile is also
  // kept over a black mark, whatever the liquid's transparency. The blick tent is taller than the body's
  // highlight strip, so it shows on that pixel a few rows off the highlight row: take the row where it does.
  const glossy = { surfaceFill: 0, surfaceRim: 0, surfaceBlick: 1, liquidTransparency: 1 };
  const innerAt = (f, row) => { const xmr = b.xm[side][row], xr = side === 0 ? Math.ceil(xmr) - 1 : Math.ceil(xmr); return f[row * 536 + (b.mirror ? b.L - 1 - xr : xr)]; };
  const gl = shot(glossy, {}), glNoTicks = shot({ ...glossy, ticksH: false }, {}), glNoBlick = shot({ ...glossy, ticksH: false, surfaceBlick: 0 }, {});
  let row = 30, blick = 0;
  for (let r = 15; r <= 45; r++) { const d = delta([innerAt(glNoTicks.f, r)], [innerAt(glNoBlick.f, r)]); if (d > blick) { blick = d; row = r; } }
  const inner = (sh) => innerAt(sh.f, row);
  const keptB = delta([inner(gl)], [inner(glNoTicks)]), tickB = delta([inner(glNoTicks)], [black]);
  assert(blick > 30, `test scene must put a blick on the first body pixel (${tag}: ${blick})`);
  assert(keptB < 0.75 * tickB, `blick must stay on top of rear marks inside the softened edge (${tag}: moved ${keptB} of ${tickB})`);
}
// Parity scenes with the blick and a see-through fill over ordinary marks (both edges' bands over ticks and
// digits): the mark compositor's wet/dry mix must round once, like the firmware.
for (const remaining of [false, true])
  render(`marks-blick-${remaining}`, { ...marks, ticksH: true, ticksM: true, tickStepH: 1, remaining,
    surfaceFill: 0.35, surfaceBlick: 0.8, liquidTransparency: 0.5 });
render('marks-blick-moving', { ...marks, ticksH: true, ticksM: true, tickStepH: 1, surfaceFill: 0.35, surfaceBlick: 0.8, liquidTransparency: 0.5 },
  { edgeLight: 0.4, acrossTilt: -0.2, cap: 3, fillVel: -30 });
const gradient = render('gradient', { surfaceRim: 0 });
assert(new Set(gradient.slice(30 * 536 + 400, 30 * 536 + 406)).size >= 4, 'surface needs shading across its width');
const covered = render('opaque-residue', { traces: true, traceAmount: 2 }, {}, base, true);
for (let x = 400; x < 406; x++) assert.equal(covered[30 * 536 + x], symmetric[30 * 536 + x], 'opaque surface must cover residue');
for (const film of [0.1, 0.5, 0.9]) render('settling-' + film, { traces: true, wetFilm: 15 }, { filmFree: film, filmHome: film }, base, true);
// Imminent residue: a strongly skewed slug (a vertical watch held sideways) receding at both ends, with a smear
// that stops short of the tube ends — the residue near each line is sampled along its contact line, wet.
// contactDyn 40 gives the film a thickness (η ≈ 0.02), so the annular-path lookup runs too.
for (const remaining of [false, true]) for (const film of [0.4, 1]) for (const contactDyn of [0, 40])
  render(`imminent-tilt-${remaining}-${film}-${contactDyn}`, { traces: true, wetFilm: 15, traceAmount: 1.5, contactDyn, remaining, freeLiquid: true },
    { angle: 40, slugVel: (remaining ? 1 : -1) * 60, filmFree: film, filmHome: film }, base, [40, 470]);
// The film fades out with its follower: no pop where the follower crosses the 0.02 gate (a tangent row sees
// even a vanishing film at full chord), and none along the wall where it hands over to the residue.
{
  const gate = { traces: true, wetFilm: 15, traceAmount: 0.5, contactDyn: 20, tubeHeight: 60 };
  const above = render('film-gate-above', gate, { filmFree: 0.0201, filmHome: 0.0201 }, base, true);
  const below = render('film-gate-below', gate, { filmFree: 0.0199, filmHome: 0.0199 }, base, true);
  assert(delta(above, below) <= 9, 'wet film must fade out, not pop, at the follower gate');
}
// A 2 px slug whose AA ramps overlap, skewed over a smear: the two edges' warps meet mid-slug and must join
// continuously — a hair's slide may not jump the backing between them.
{
  const tiny = { traces: true, wetFilm: 15, tubeHeight: 60, contactAngle: 90, edgeSoft: 4, liquid: '#000000', liquidHi: '#000000', liquidLo: '#000000' };
  const st = { fillTarget: 2 / 536, angle: 40 };
  const a = render('short-slug-warp-a', tiny, { ...st, slugPos: 267.4999 }, base, [268, 536]);
  const b = render('short-slug-warp-b', tiny, { ...st, slugPos: 267.5001 }, base, [268, 536]);
  assert(delta(a, b) <= 9, 'warped residue must join continuously between the two edges of a short slug');
}
// Crossed edges: a short convex slug compressed by slosh has rows where the home edge passes the time edge.
// The firmware's sheared dry spans assume ordered edges and must fall back to the general zone there (native
// parity runs it; a one-step error is below the tolerance — check_render_frames against a pre-split
// reference is the exact gate). The assertion keeps the scene crossing.
for (const remaining of [false, true]) {
  const cross = { traces: true, traceAmount: 1.5, wetFilm: 15, contactAngle: 140, remaining };
  render(`crossed-slug-${remaining}`, cross, { fillTarget: remaining ? 1 - 6 / 536 : 6 / 536, fillPos: remaining ? 4 : -4, slugPos: 200, angle: 20, filmFree: 0.6 }, base, [150, 260]);
  const b = R.markBounds[0];
  let crossed = 0;
  for (let y = 0; y < 61; y++) if (b.lo[y] > b.hi[y]) crossed++;
  assert(crossed > 0, 'crossed-slug scene must have rows where the edges cross');
}
// Hard edges (edgeSoft 0): the midpoint blend still spans a pixel. A 0.6 px slug (home edge 100.6, time edge
// 101.2 in the render frame) with only its time edge's film up: pixel 100 lies on the home side but takes
// a tenth of the time edge's film, so it must not be painted as plain residue. No residue under it: the film
// and a coat are one layer (the deeper counts), and a full coat would hide this thin share of film.
for (const remaining of [false, true]) {
  const hard = { traces: true, wetFilm: 15, contactDyn: 40, edgeSoft: 0, tubeHeight: 60, contactAngle: 90, remaining };
  const st = { fillTarget: remaining ? 1 - 0.6 / 536 : 0.6 / 536, slugPos: remaining ? 536 - 0.6 - 100.6 : 100.6, filmHome: 0 };
  const on = render(`hard-slug-film-${remaining}`, hard, { ...st, filmFree: 1 }, base);
  const off = render(`hard-slug-dry-${remaining}`, hard, { ...st, filmFree: 0 }, base);
  const col = remaining ? 535 - 100 : 100;
  let differs = false;
  for (let y = 0; y < 60; y++) differs ||= on[y * 536 + col] !== off[y * 536 + col];
  assert(differs, 'a hard-edged slug must blend its time edge film into the pixel the home side owns');
}
for (const angle of [0, 45, 89.9, 90, 90.1, 140, 180]) for (const remaining of [false, true])
  render(`angle-${angle}-${remaining}`, { contactAngle: angle, remaining }, { edgeLight: 0.4, acrossTilt: -0.2, cap: 3 });
// Hysteresis band under tilt pressure, and moving lines (advancing / receding, Cox–Voinov) at both ends.
for (const angle of [30, 140]) for (const remaining of [false, true])
  for (const [tag, state] of [['tilt', { edgeLight: 0.6, acrossTilt: 0.5 }], ['slide', { slugVel: 40, fillVel: -10, cap: -2 }]])
    render(`contact-${angle}-${remaining}-${tag}`, { contactAngle: angle, contactHyst: 12, contactDyn: 20, remaining }, state);
for (const n of ['cryo', 'olive-oil', 'blood', 'mercury']) {
  const preset = { ...DEFAULT_PARAMS, ...migrateParams(JSON.parse(fs.readFileSync(path.join(root, 'presets', n + '.json')))),
    fizz: false, bubble: false, digits: false, ticksH: false, ticksM: false, hoursY: 0 };
  render(n + '-settled', {}, {}, preset);
  render(n + '-moving', {}, { edgeLight: 0.4, cap: 2, filmHome: 0.6 }, preset, true);
}
for (const H of [4, 80]) for (const fill of [0, 0.001, 1])
  render(`limit-${H}-${fill}`, { tubeHeight: H }, { fillTarget: fill, slugPos: 0 });
// Reported white trailing crescent: white tube back, strong tilt bulge, remaining mode.
// A reversal can make the receding edge convex while the previous wet film is still up.
const trailingPreset = { ...DEFAULT_PARAMS,
  ...migrateParams(JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/meniscus-trailing.json')))),
  fizz: false, bubble: false, digits: false, ticksH: false, ticksM: false };
// A saturated residue (traceAmount 16: a full coat's centre-row path fraction ≥ 0.082 reaches the chord on every
// row, whatever the streak) under a fully wet receding
// line is, at the line, liquid of the full chord — the body colour — so the inner half of the body AA and
// the backing are the same colour. Their junction must not expose the white tube back.
for (const remaining of [false, true]) {
  const changes = { remaining, surfaceBand: 0, lens: 0, traceAmount: 16 };
  const p = { ...trailingPreset, ...changes };
  const joined = render(`wet-junction-${remaining}`, changes, { filmHome: 1, filmFree: 1 }, trailingPreset, true);
  const pal = R.buildPalette(p, 0), rest = R.capShape(p, 0, 0, 0, 0, 0, 0, 1);   // the static shape at px scale 1 (AMOLED)
  for (const row of [15, 25, 30, 40]) {
    const left = Math.floor(R.edgeXL(row, 134, 0, p, rest) - 0.5) + 1;
    const right = Math.ceil(R.edgeX(row, 402, 0, p, rest) - 0.5) - 1;
    for (const x of [left, right]) assert.equal(joined[row * 536 + (remaining ? 535 - x : x)], pal.rows[row],
      'liquid/wet-film junction must not leak white background through overlapping alpha ramps');
  }
}
// The same junction over the fixture's own, unsaturated residue: the wet residue at the line is then a tint
// lighter than the body, and its per-column streak varies, so the junction pixel may be as light as the
// lightest backing just past the ramp — but no lighter (a white leak through overlapping ramps is far more).
for (const remaining of [false, true]) {
  const changes = { remaining, surfaceBand: 0, lens: 0 };
  const p = { ...trailingPreset, ...changes };
  const joined = render(`wet-junction-unsat-${remaining}`, changes, { filmHome: 1, filmFree: 1 }, trailingPreset, true);
  const pal = R.buildPalette(p, 0), rest = R.capShape(p, 0, 0, 0, 0, 0, 0, 1);   // the static shape at px scale 1 (AMOLED)
  for (const row of [15, 25, 30, 40]) {
    const bk = rgb(pal.tubeBackRows[row]), at = (x) => joined[row * 536 + (remaining ? 535 - x : x)];
    const far = (x) => { const c = rgb(at(x)); return Math.abs(c[0] - bk[0]) + Math.abs(c[1] - bk[1]) + Math.abs(c[2] - bk[2]); };
    const left = Math.floor(R.edgeXL(row, 134, 0, p, rest) - 0.5) + 1;
    const right = Math.ceil(R.edgeX(row, 402, 0, p, rest) - 0.5) - 1;
    for (const [x, out] of [[left, -1], [right, 1]]) {
      let backing = far(x - 3 * out);
      for (let k = 3; k <= 8; k++) backing = Math.min(backing, far(x + k * out));
      assert(far(x) >= backing - 24, 'unsaturated liquid/wet-film junction must not leak white background');
    }
  }
}
function half(frame, right) {
  const a = [];
  for (let y = 0; y < trailingPreset.tubeHeight; y++)
    for (let x = right ? 268 : 0; x < (right ? 536 : 268); x++) a.push(frame[y * 536 + x]);
  return a;
}
// A wide glow must not move the nose's backing off the wet trail (the sample is taken before the glow).
for (const remaining of [false, true]) for (const home of [false, true]) for (const edgeGlow of [0, 12]) {
  const sign = (remaining ? -1 : 1) * (home ? -1 : 1);
  const state = { edgeLight: sign * 0.65, cap: sign * 12, acrossTilt: 0.25, angle: 3,
    slugVel: -sign * 80, filmHome: home ? 1 : 0, filmFree: home ? 0 : 1 };
  const key = `trailing-${remaining}-${home}-glow${edgeGlow}`, glow = { edgeGlow, glowStrength: 0.6 };
  const on = render(key, { remaining, ...glow }, state, trailingPreset, true);
  const off = render(key + '-disabled', { remaining, ...glow, surfaceBand: 0 }, state, trailingPreset, true);
  const right = home === remaining;
  // The nose stays (motion never fades a surface) but thins toward the wet film behind it, not
  // the white back: only the clear liquid's faint highlight tint may remain.
  assert(delta(half(on, right), half(off, right)) <= 9,
    'receding convex surface must not add a white crescent over the wet film');
  assert(delta(half(on, !right), half(off, !right)) > 9, 'advancing surface must remain visible');
}
for (const remaining of [false, true]) for (const edgeGlow of [0, 5]) {
  const bead = render(`wet-bead-${remaining}-${edgeGlow}`,
    { remaining, edgeGlow, traces: true, traceFilm: 0, contactAngle: 90, surfaceBand: 0 },
    { fillTarget: remaining ? 1 - 2 / 536 : 2 / 536, slugPos: 267 }, base);
  for (let y = 0; y < 61; y++) for (let x = 263; x < 268; x++)
    assert.equal(bead[y * 536 + x], bead[y * 536 + 535 - x], 'overlapping AA ramps must composite a bead symmetrically');
}
// Rear marks across the meniscus (wetShare): ticks and labels the surface is passing over take part of the
// liquid's refraction (rows blended dry -> wet, parallax scaled). Both slug edges at several offsets over the
// labels, both frames, bitmap digits with a shadow pass and sprite digits with a baked one. No contrast floor
// and no surface band here: the floor's direction at a near-tie luma (mark ~ liquid) is decided by rounding,
// differently on each side, and a mark under the band's dish differs by two 565 steps (16-17/255) — both
// already so before the wet share (see KAIZEN), neither to do with the warp.
const across = { ...base, liquidTransparency: 0.4, markContrast: 0, surfaceBand: 0,
  ticksH: true, tickStepH: 1, ticksOnTop: false, tickLens: 0.6, tickDryLens: -0.4, tickParallax: 5,
  digits: true, digitsOnTop: false, digitHourStep: 1, bottomLens: 0.6, digitDryLens: -0.4, digitParallax: 5 };
for (const digitFont of [0, 6]) for (const slugPos of [120, 127, 134]) for (const remaining of [false, true])
  render(`marks-across-${digitFont}-${slugPos}-${remaining}`, { digitFont, remaining }, { slugPos, edgeLight: 0.4, acrossTilt: 0.3, angle: 2 }, across);
// Vertical watch: digits turned to read upright (bitmap with its shadow pass, sprite with a baked one), one- and
// two-digit labels advancing across the tube, the scale from either end (`remaining` flips the scale there, the
// liquid stays put), the slug edges over the labels.
for (const digitFont of [0, 6]) for (const slugPos of [120, 134]) for (const remaining of [false, true])
  render(`marks-vertical-${digitFont}-${slugPos}-${remaining}`, { digitFont, remaining, vertical: true, digitScaleX: 2.5, digitScaleY: 2, digitBottom: 3 },
    { slugPos, edgeLight: 0.4, acrossTilt: 0.3, angle: 2 }, across);
// Vertical, ticks and digits with different lenses: behind liquid the ticks follow the digits' remap (tickLens unused).
for (const slugPos of [120, 134])
  render(`marks-vertical-lenses-${slugPos}`, { digitFont: 6, vertical: true, digitScaleX: 2.5, digitScaleY: 2, tickMinorHeightH: 14,
    tickLens: 0.85, tickDryLens: 1, bottomLens: 0.45, digitDryLens: 0.1 }, { slugPos, edgeLight: 0.4, acrossTilt: 0.3, angle: 2 }, across);
// The contrast floor on sprite digits with a baked shadow (Mark::wetColourT): light numerals over a dark liquid,
// no surface band, the slug over whole labels and across two.
const floorScene = { ...across, liquid: '#102030', liquidHi: '#406080', liquidLo: '#081018', markContrast: 60, surfaceBand: 0,
  ticksH: false, digitFont: 6, digitShadowColor: '#000000', digitColor: '#e0e0e0' };
for (const slugPos of [120, 134]) render(`marks-floor-${slugPos}`, {}, { slugPos, edgeLight: 0.4, acrossTilt: 0.3 }, floorScene);
// Vertical, rear ticks under rear digits (TickFollow), on the row tables: a tick and a centred label `labelW`
// source rows wide, per wet share 0..256 — the tick's inner ends from either wall and the label's rows.
function tickAndLabel(H, lenses, h, labelW) {
  const p = { ...base, vertical: true, digits: true, digitsOnTop: false, ticksOnTop: false, ...lenses };
  const f = R.tickFollow(p, H), edge = f.edge(h), tick = R.markSourceRows(H, p.tickDryLens);
  const dry = R.markSourceRows(H, p.digitDryLens), wet = R.markSourceRows(H, p.bottomLens);
  const a = (H - labelW) >> 1, b = a + labelW - 1, shares = [];
  for (let share = 0; share <= 256; share++) {
    let top = -1, bot = H, lo = H, hi = -1;
    if (share) { top = R.tickFollowRange(f, H, edge, share, true)[1]; bot = R.tickFollowRange(f, H, edge, share, false)[0]; }
    else for (let ry = 0; ry < H; ry++) { if (tick[ry] <= h - 1) top = ry; if (tick[ry] >= H - h && bot === H) bot = ry; }
    for (let ry = 0; ry < H; ry++) {
      const row = dry[ry] + (((wet[ry] - dry[ry]) * share + 128) >> 8);
      if (row >= a && row <= b) { lo = Math.min(lo, ry); hi = Math.max(hi, ry); }
    }
    // No seam where the dry row table hands over to the remap: at share 0 the remap gives the table's ends.
    if (!share) assert.deepEqual([R.tickFollowRange(f, H, edge, 0, true)[1], R.tickFollowRange(f, H, edge, 0, false)[0]], [top, bot], `remap at share 0 is not the dry tick ${JSON.stringify({ H, lenses, h })}`);
    shares.push({ top, bot, lo, hi });
  }
  return shares;
}
// Liquid that lenses like the air moves nothing, however many rows share a source row.
for (const s of tickAndLabel(80, { digitDryLens: 1, bottomLens: 1, tickDryLens: 0 }, 30, 20)) assert.deepEqual([s.top, s.bot], [29, 50], 'tick moved behind liquid with identical wet/dry optics');
// A tick one clear row short of its label behind air stays off it at every wet share of the meniscus.
let followCases = 0;
for (const H of [37, 46, 60, 61, 80]) for (const digitDryLens of [-1, -0.4, 0, 0.1, 0.5, 1]) for (const bottomLens of [0, 0.45, 0.6, 1])
  for (const tickDryLens of [-1, -0.4, 0, 0.35, 1]) for (let h = 2; h <= H >> 1; h += 3) for (const labelW of [5, 11, 21, 29]) {
    if (labelW >= H) continue;
    const shares = tickAndLabel(H, { digitDryLens, bottomLens, tickDryLens }, h, labelW), d = shares[0];
    const where = JSON.stringify({ H, digitDryLens, bottomLens, tickDryLens, h, labelW });
    if (digitDryLens === bottomLens) for (const s of shares) assert.deepEqual([s.top, s.bot], [d.top, d.bot], `tick moved with identical optics ${where}`);
    if (d.hi < 0 || d.lo - d.top < 2 || d.bot - d.hi < 2) continue;
    followCases++;
    shares.forEach((s, share) => assert.ok(s.hi < 0 || (s.top < s.lo && s.bot > s.hi), `tick on its label at share ${share}: ${JSON.stringify(s)} ${where}`));
  }
assert.ok(followCases > 1000, `tick/label clearance cases: ${followCases}`);
assert.ok(tickAndLabel(37, { digitDryLens: -1, bottomLens: 0.6, tickDryLens: 0 }, 14, 21)[0].lo - 13 === 2, 'the review case has one clear dry row');
// In-plane skew: the liquid lies on the low wall at both ends — the home end of a slug leans the other way —
// and the two leans of a short slug off its home end never cross, whatever the cap (concave, convex, wobble).
let skewCases = 0;
for (const [tag, mode] of [['land', {}], ['land-rem', { remaining: true }], ['vert', { vertical: true }]])
  for (const contactAngle of [30, 140]) for (const column of [0.5, 0.06, 0.02]) for (const slugPos of [3, 134]) for (const angle of [40, -40]) {
    const changes = { ...mode, contactAngle, contactHyst: 12 }, p = { ...base, ...changes };
    const fillTarget = p.remaining ? 1 - column : column;   // the column's share of the tube, either scale
    const state = { fillTarget, slugPos, angle, acrossTilt: Math.sign(angle) * 0.5, cap: 3 };
    render(`skew-${tag}-${contactAngle}-${column}-${slugPos}-${angle}`, changes, state);
    const mir = mirrored(p), len = columnLen(fillTarget, p), xs = mir ? 536 - len - slugPos : slugPos, xe = xs + len, H = R.tubeLayout(p).H;
    const cR = R.capShape(p, len, 0, state.acrossTilt, mir ? -3 : 3, 0, 0, 1), cL = R.capShape(p, len, 0, state.acrossTilt, mir ? 3 : -3, 0, 0, 1);
    const kR = R.capScale(len, cR), kL = R.capScale(len, cL), [tanR, tanL] = R.edgeSkews(angle, H, xe - xs, xs, cR, kR, cL, kL);
    const span = (ry) => R.edgeX(ry, xe, tanR, p, cR, kR) - R.edgeXL(ry, xs, tanL, p, cL, kL), where = JSON.stringify({ tag, ...state, contactAngle });
    assert.ok(tanR * angle >= 0 && tanL * angle <= 0 && (len < 60 || tanL === -tanR), `home end must lean the other way ${where}`);
    for (let ry = 0; ry < H; ry++) {
      if (slugPos >= 8) assert.ok(span(ry) >= -1e-6, `slug ends cross at row ${ry} ${where}`);
      if (ry < H >> 1) assert.ok((span(H - 1 - ry) - span(ry)) * angle > 0, `liquid must be longer on the low wall, row ${ry} ${where}`);
    }
    skewCases++;
  }
assert.ok(skewCases === 72, `skew cases: ${skewCases}`);
// Unlike caps under slosh (review case: convex, tilt pressure and sag make the home cap overshoot its half of a
// 35 px gap): the lean takes only what both caps leave of the real gap, so it never crosses the ends — where the
// caps alone already meet, the slug keeps their shape.
let sloshCases = 0;
for (const contactAngle of [140, 100, 30]) for (const len of [20, 40, 60]) for (const fillPos of [-5, 0, 5]) for (const edgeLight of [-0.4, 0.4])
  for (const acrossTilt of [0.75, -0.75]) for (const angle of [4.125, -40]) for (const cap of [0, 6]) for (const slugPos of [4, 100]) {
    const changes = { contactAngle, contactHyst: 15 }, p = { ...base, ...changes }, H = R.tubeLayout(p).H;
    const state = { fillTarget: len / 536, slugPos, fillPos, edgeLight, acrossTilt, angle, cap }, xe = slugPos + len + fillPos;
    const cR = R.capShape(p, len, edgeLight, acrossTilt, cap, 0, 0, 1), cL = R.capShape(p, len, -edgeLight, acrossTilt, -cap, 0, 0, 1);
    const kR = R.capScale(len, cR), kL = R.capScale(len, cL), [tanR, tanL] = R.edgeSkews(angle, H, xe - slugPos, slugPos, cR, kR, cL, kL);
    const tanA = Math.tan(angle * Math.PI / 180), off = Math.min(1, slugPos / 8);
    for (let ry = 0; ry < H; ry++) {
      const eL = (t) => R.edgeXL(ry, slugPos, t, p, cL, kL), span = R.edgeX(ry, xe, tanR, p, cR, kR) - eL(tanL);
      // the width the caps alone leave (off the end cap: no lean; lifting off it: the free lean the cap clips)
      const capsOnly = R.edgeX(ry, xe, (1 - off) * tanA, p, cR, kR) - eL(0);
      assert.ok(span >= Math.min(0, capsOnly) - 1e-6, `lean crosses the slug ends at row ${ry}: ${span} (caps alone ${capsOnly}) ${JSON.stringify({ contactAngle, len, ...state })}`);
    }
    if (len === 40 && slugPos === 100 && cap === 0) render(`skew-slosh-${contactAngle}-${fillPos}-${edgeLight}-${acrossTilt}-${angle}`, changes, state);
    sloshCases++;
  }
assert.ok(sloshCases === 864, `slosh cases: ${sloshCases}`);
fs.writeFileSync(path.join(out, 'jobs.json'), JSON.stringify(jobs));
console.log(`Meniscus: symmetry, subpixel motion, flattening, residue, receding edge, gradient passed; ${jobs.length} parity scenes.`);
