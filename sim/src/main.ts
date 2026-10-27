import './style.css';
import { PANEL_W, PANEL_H } from '@spec/layout';
import { GAS_MODELS, PRESETS, gasParams, presetParams, type Params } from './params';
import { ImuFilter, PHYS_DT, fillLevels, followClock, newTube, stepTube, type TiltInput } from './physics';
import { renderFrame, blit, stepFizz, fb, fizz, loadSprites, tubeLayout } from './render';
import { DEFAULT_OVERLAY, LEATHER_PAD_X, LEATHER_PAD_Y, applyOverlay, buildOverlayDom } from './overlay';
import { DEFAULT_VIEW, loadSession, saveSession } from './persist';
import { buildPanel } from './ui';
import { LOCKED_KEYS, buildMaterialPanel, isDesignKey } from './material/ui';
import { MATERIAL_KEYS, validateMaterial } from './material/model';
loadSprites(`${import.meta.env.BASE_URL}assets/`);
import { SerialImu } from './serial';
import { SerialTransport } from './transport/serial';
import { BleTransport } from './transport/ble';
import type { LineTransport } from './transport/line';
import type { TransportStatus } from './transport/types';

// ---------- state ----------
// Params *and* view state are restored from localStorage and saved again on every edit (persist.ts).
// `?fresh=1` ignores the store and starts from the code defaults — use it after DEFAULT_PARAMS changes.
const url = new URLSearchParams(location.search);
const session = loadSession(url.get('fresh') === '1');
const params: Params = session.params;
const matState = session.material;              // physical-material mode: params = derive(material, design)
const overlay = session.view.overlay;
const manual = session.view.manual;             // sliders / drag
const setClock = session.view.setClock;
let { scale, showGrid, paused, timeMode, demoSpeed, sweep, sweepPeriod } = session.view;  // demoSpeed = demo s per real s
let sweepPhase = 0;   // 0..1 through the minutes sweep cycle
const hours = newTube(), minutes = newTube();
const input: TiltInput = { along: 0, across: 0, gyroAlong: 0, gyroAcross: 0 };
const imuFilter = new ImuFilter();
let inputSource: 'manual' | 'device' | 'serial' = 'manual'; // not persisted: device/serial need a gesture
let demoClock = Date.now();
let clockSet = false;   // the user set the clock: the fill jumps there instead of retracting (followClock)

// ---------- DOM ----------
const app = document.getElementById('app')!;
app.innerHTML = `
<header>
  <h1>Liquid Watch — sim</h1>
  <div class="top">
    <label>scale <select id="scale"><option value="0.33">0.33 (≈ real size @96 dpi)</option><option value="0.5" selected>0.5</option><option value="0.75">0.75</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option></select></label>
    <label><input type="checkbox" id="ovl" checked> leather cuff</label>
    <label>leather <select id="leather"><option>brown</option><option>black</option><option>none</option></select></label>
    <label>lens <input type="range" id="lens" min="-1" max="1" step="0.05" value="0.6"></label>
    <label>lens curve <input type="range" id="lenscurve" min="-3" max="3" step="0.05" value="1"></label>
    <label title="Front-digit pre-distortion; negative compensates physical glass magnification">front digits lens <input type="range" id="toplens" min="-1" max="1" step="0.05" value="0"></label>
    <label><input type="checkbox" id="lenssmooth"> lens smooth</label>
    <label>gloss <input type="range" id="gloss" min="0" max="1" step="0.05" value="0.55"></label>
    <label>slot inset <input type="range" id="inset" min="0" max="40" step="1" value="10"></label>
    <label><input type="checkbox" id="grid"> layout grid</label>
    <label><input type="checkbox" id="pause"> pause</label>
    <button id="resetview">reset view</button>
    <span id="fps"></span>
  </div>
</header>
<main>
  <section class="stage">
    <div id="viewport" class="viewport"><div id="panelwrap" class="panelwrap">
      <canvas id="fbc" width="${PANEL_W}" height="${PANEL_H}"></canvas>
      <canvas id="gridc" width="${PANEL_W}" height="${PANEL_H}"></canvas>
    </div></div>
    <div class="controls">
      <fieldset><legend>Time</legend>
        <label><input type="radio" id="tm-real" name="tm" value="real" checked> real</label>
        <label><input type="radio" id="tm-demo" name="tm" value="demo"> demo ×<input type="number" id="demospeed" value="60" min="1" max="3600" style="width:5em"></label>
        <label><input type="radio" id="tm-set" name="tm" value="set"> set <input type="number" id="seth" value="10" min="0" max="23" style="width:3.5em">:<input type="number" id="setm" value="9" min="0" max="59" style="width:3.5em"></label>
        <label title="Minutes tube runs empty→full→empty instead of telling time; sent to the device live and kept there across resets"><input type="checkbox" id="sweep"> minutes sweep, period <input type="number" id="sweepperiod" value="10" min="1" max="3600" style="width:4.5em"> s</label>
        <span id="clock"></span>
        <button id="settime" title="Send this time and mode to the device: real, demo speed, or frozen selected time, plus the minutes sweep">send sim time</button>
      </fieldset>
      <fieldset><legend>Tilt input</legend>
        <label><input type="radio" name="src" value="manual" checked> sliders / drag on panel</label>
        <label><input type="radio" name="src" value="device"> device orientation (phone)</label>
        <label><input type="radio" name="src" value="serial"> board IMU via link</label>
        <div id="imuraw" class="mono"></div>
        <canvas id="scope" width="316" height="70"></canvas>
        <label>along <input type="range" id="along" min="-1" max="1" step="0.01" value="0"> <output id="alongv">0</output> g</label>
        <label>across <input type="range" id="across" min="-1" max="1" step="0.01" value="0"> <output id="acrossv">0</output> g</label>
        <button id="center">centre</button> <button id="flick">flick →</button> <button id="flickl">← flick</button> <button id="shake">shake</button> <button id="wrist" title="wrist turn into the reading pose (free liquid: parks the slug home)">raise wrist</button>
      </fieldset>
      <fieldset><legend>Device</legend>
        <label><select id="link"><option value="serial">Web Serial</option><option value="ble">Bluetooth</option></select> <button id="serialbtn">connect</button> <span id="serialst">disconnected</span></label>
        <label><input type="checkbox" id="livepush" checked> push params live</label>
        <label><button id="pull">pull params</button> <button id="pushall">push all</button></label>
        <label><button id="readfps" disabled>read device fps</button> <span id="devicefps">connect to read</span></label>
      </fieldset>
    </div>
  </section>
  <aside id="panel"></aside>
</main>`;

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const wrap = document.getElementById('panelwrap')!;
const fbc = document.getElementById('fbc') as HTMLCanvasElement;
const gridc = document.getElementById('gridc') as HTMLCanvasElement;
const fbctx = fbc.getContext('2d')!;
// Full-resolution frame; at scale < 1 the visible canvases are downsampled from it with area filtering
// (a CSS-transform downscale point-samples and drops 1 px ticks).
const fullc = document.createElement('canvas'); fullc.width = PANEL_W; fullc.height = PANEL_H;
const fullctx = fullc.getContext('2d')!;
const img = fullctx.createImageData(PANEL_W, PANEL_H);
const ovlDom = buildOverlayDom(wrap);
applyOverlay(ovlDom, overlay, tubeLayout(params));

// ---------- persistence ----------
// One delegated listener covers every control on the page (top bar, time, tilt, params panel);
// programmatic changes (presets, import, drag-tilt, reset) call save() explicitly.
const save = (): void => saveSession({ params, view: { scale, showGrid, paused, timeMode, demoSpeed, sweep, sweepPeriod, setClock, manual, overlay }, material: matState });
app.addEventListener('input', save);
app.addEventListener('change', save);

const viewport = $('viewport');
let shownVertical = params.vertical;
const setScale = () => {
  const padX = overlay.enabled ? LEATHER_PAD_X : 0, padY = overlay.enabled ? LEATHER_PAD_Y : 0;
  // Vertical watch: the panel is shown as worn, turned a quarter counter-clockwise (USB end down, hours tube left).
  // a manual input still at the old resting pose follows the watch to its new one (never on the first call: no change yet)
  if (params.vertical !== shownVertical && manual.along === restAlong(shownVertical) && manual.across === 0) { manual.along = restAlong(params.vertical); syncSliders(); }
  shownVertical = params.vertical;
  const w = (PANEL_W + 2 * padX) * scale, h = (PANEL_H + 2 * padY) * scale;
  viewport.style.width = `${shownVertical ? h : w}px`; viewport.style.height = `${shownVertical ? w : h}px`;
  wrap.style.transform = shownVertical
    ? `translate(${padY * scale}px, ${(PANEL_W + padX) * scale}px) rotate(-90deg) scale(${scale})`
    : `translate(${padX * scale}px, ${padY * scale}px) scale(${scale})`;
  wrap.classList.toggle('smooth', scale < 2); // pixelated upscale only at ≥2; bilinear when shrinking
  // Below 1: canvas backing store at on-screen size, CSS size stays 536x240 so the wrap transform maps 1:1.
  const ss = Math.min(1, scale);
  for (const c of [fbc, gridc]) {
    c.width = Math.ceil(PANEL_W * ss); c.height = Math.ceil(PANEL_H * ss);
    c.style.width = `${PANEL_W}px`; c.style.height = `${PANEL_H}px`;
    const g = c.getContext('2d')!; g.setTransform(ss, 0, 0, ss, 0, 0); g.imageSmoothingQuality = 'high';
  }
  drawGrid();
};
setScale();
$('scale').oninput = (e) => { scale = +(e.target as HTMLSelectElement).value; setScale(); };
$('ovl').oninput = (e) => { overlay.enabled = (e.target as HTMLInputElement).checked; applyOverlay(ovlDom, overlay, tubeLayout(params)); setScale(); };
$('leather').oninput = (e) => { overlay.leather = (e.target as HTMLSelectElement).value as any; applyOverlay(ovlDom, overlay, tubeLayout(params)); };
$('lens').oninput = (e) => { params.lens = +(e.target as HTMLInputElement).value; paramEdited('lens'); };
$('lenscurve').oninput = (e) => { params.lensCurve = +(e.target as HTMLInputElement).value; paramEdited('lensCurve'); };
$('toplens').oninput = (e) => { params.topLens = +(e.target as HTMLInputElement).value; paramEdited('topLens'); };
$('lenssmooth').oninput = (e) => { overlay.lensSmooth = (e.target as HTMLInputElement).checked; };
$('gloss').oninput = (e) => { overlay.gloss = +(e.target as HTMLInputElement).value; applyOverlay(ovlDom, overlay, tubeLayout(params)); };
$('inset').oninput = (e) => { overlay.slotInset = +(e.target as HTMLInputElement).value; applyOverlay(ovlDom, overlay, tubeLayout(params)); };
$('grid').oninput = (e) => { showGrid = (e.target as HTMLInputElement).checked; drawGrid(); };
$('pause').oninput = (e) => { paused = (e.target as HTMLInputElement).checked; };
function selectTimeMode(mode: typeof timeMode): void {
  // Demo continues from the displayed time, including a manually selected starting time.
  if (mode === 'demo' && timeMode !== 'demo') demoClock = currentDate().getTime();
  else if (mode !== 'demo') clockSet = true;
  timeMode = mode;
  $<HTMLInputElement>(`tm-${mode}`).checked = true;
}
for (const r of document.querySelectorAll<HTMLInputElement>('input[name=tm]')) r.oninput = () => selectTimeMode(r.value as typeof timeMode);
for (const r of document.querySelectorAll<HTMLInputElement>('input[name=src]')) r.oninput = () => { inputSource = r.value as any; if (inputSource === 'device') askOrientation(); };
$('demospeed').oninput = (e) => { demoSpeed = +(e.target as HTMLInputElement).value; selectTimeMode('demo'); };
const sweepValue = (): number => (sweep ? sweepPeriod : 0);
async function pushSweep(): Promise<void> {
  if (!transport.connected) return;
  try { await transport.setSweep(sweepValue()); $('serialst').textContent = sweep ? `sweep ${sweepPeriod}s sent` : 'sweep off sent'; }
  catch (e) { $('serialst').textContent = String(e); }
}
$('sweep').oninput = (e) => { sweep = (e.target as HTMLInputElement).checked; sweepPhase = 0; pushSweep(); };
$('sweepperiod').onchange = (e) => {
  const v = +(e.target as HTMLInputElement).value;
  if (!(v >= 1 && v <= 3600)) { (e.target as HTMLInputElement).value = String(sweepPeriod); return; }
  sweepPeriod = v; sweepPhase = 0; if (sweep) pushSweep();
};
$('seth').oninput = (e) => { setClock.h = +(e.target as HTMLInputElement).value; selectTimeMode('set'); };
$('setm').oninput = (e) => { setClock.m = +(e.target as HTMLInputElement).value; selectTimeMode('set'); };
$('resetview').onclick = () => {
  Object.assign(overlay, DEFAULT_OVERLAY); Object.assign(manual, DEFAULT_VIEW.manual); Object.assign(setClock, DEFAULT_VIEW.setClock);
  ({ scale, showGrid, paused, timeMode, demoSpeed, sweep, sweepPeriod } = DEFAULT_VIEW);
  clockSet = true; syncView(); save();
};
const alongS = $<HTMLInputElement>('along'), acrossS = $<HTMLInputElement>('across');
const syncSliders = () => { alongS.value = String(manual.along); acrossS.value = String(manual.across); $('alongv').textContent = manual.along.toFixed(2); $('acrossv').textContent = manual.across.toFixed(2); };
alongS.oninput = () => { manual.along = +alongS.value; syncSliders(); };
acrossS.oninput = () => { manual.across = +acrossS.value; syncSliders(); };
// Resting pose of the manual input: flat on the table, or upright (bottom end down) for a vertical watch.
const restAlong = (vertical: boolean): number => vertical ? -1 : 0;
$('center').onclick = () => { manual.along = restAlong(params.vertical); manual.across = 0; syncSliders(); save(); };

/** Push the whole view state into the DOM + derived layers. Inverse of what `save()` collects. */
function syncView(): void {
  $<HTMLSelectElement>('scale').value = String(scale);
  $<HTMLInputElement>('ovl').checked = overlay.enabled;
  $<HTMLSelectElement>('leather').value = overlay.leather;
  $<HTMLInputElement>('lens').value = String(params.lens);
  $<HTMLInputElement>('lenscurve').value = String(params.lensCurve);
  $<HTMLInputElement>('toplens').value = String(params.topLens);
  $<HTMLInputElement>('lenssmooth').checked = overlay.lensSmooth;
  $<HTMLInputElement>('gloss').value = String(overlay.gloss);
  $<HTMLInputElement>('inset').value = String(overlay.slotInset);
  $<HTMLInputElement>('grid').checked = showGrid;
  $<HTMLInputElement>('pause').checked = paused;
  $<HTMLInputElement>('demospeed').value = String(demoSpeed);
  $<HTMLInputElement>('sweep').checked = sweep;
  $<HTMLInputElement>('sweepperiod').value = String(sweepPeriod);
  $<HTMLInputElement>('seth').value = String(setClock.h);
  $<HTMLInputElement>('setm').value = String(setClock.m);
  $<HTMLInputElement>(`tm-${timeMode}`).checked = true;
  syncSliders();
  applyOverlay(ovlDom, overlay, tubeLayout(params)); setScale(); drawGrid();
}
let kick = 0;
$('flick').onclick = () => { kick = 400; };
$('flickl').onclick = () => { kick = -400; };
let shakeT = 0;
const SHAKE_T = 2.5;
$('shake').onclick = () => { shakeT = SHAKE_T; };
let wristT = 0;   // wrist turn: 0.5 s roll burst about the tube axis, then the reading pose on the sliders
$('wrist').onclick = () => {   // vertical: upright with the face leaned back toward the eyes
  wristT = 0.5; manual.along = params.vertical ? -0.87 : 0; manual.across = params.vertical ? 0 : 0.2; syncSliders(); save();
};

// drag on panel = tilt
let dragging = false;
wrap.addEventListener('pointerdown', (e) => { dragging = true; wrap.setPointerCapture(e.pointerId); });
wrap.addEventListener('pointerup', () => { dragging = false; save(); });
wrap.addEventListener('pointermove', (e) => {
  if (!dragging) return;
  const r = wrap.getBoundingClientRect();
  const fx = (e.clientX - r.left) / r.width, fy = (e.clientY - r.top) / r.height;   // shown turned when vertical: panel x runs up the screen
  manual.along = Math.max(-1, Math.min(1, (shownVertical ? 1 - fy : fx) * 2 - 1));
  manual.across = Math.max(-1, Math.min(1, (shownVertical ? fx : fy) * 2 - 1));
  syncSliders();
});

// device orientation
const dev = { along: 0, across: 0, gyroAcross: 0 };
function askOrientation() {
  const D = DeviceOrientationEvent as any;
  const go = () => window.addEventListener('deviceorientation', (e) => {
    // phone held landscape like the watch: gamma tilts along (left/right end down), beta across
    dev.along = Math.sin(((e.gamma ?? 0) * Math.PI) / 180);
    dev.across = Math.sin(((e.beta ?? 0) * Math.PI) / 180);
  });
  if (typeof D?.requestPermission === 'function') D.requestPermission().then((s: string) => { if (s === 'granted') go(); });
  else go();
  window.addEventListener('devicemotion', (e) => { dev.gyroAcross = e.rotationRate?.beta ?? 0; });
}

// device: one link (Web Serial or BLE) serves the IMU stream and the param/time commands
const links: Record<string, LineTransport> = { serial: new SerialTransport(), ble: new BleTransport() };
let transport: LineTransport = links.serial;
const serial = new SerialImu(transport);
const srcRadio = (v: string) => document.querySelector(`input[name=src][value=${v}]`) as HTMLInputElement;
const onStatus = (st: TransportStatus, detail?: string) => {
  $('serialst').textContent = detail ? `${st}: ${detail}` : st;
  $('serialbtn').textContent = st === 'connected' ? 'disconnect' : 'connect';
  $<HTMLSelectElement>('link').disabled = st === 'connected';
  $<HTMLButtonElement>('readfps').disabled = st !== 'connected';
  if (st !== 'connected') $('devicefps').textContent = 'connect to read';
  if (st !== 'connected' && inputSource === 'serial') { inputSource = 'manual'; srcRadio('manual').checked = true; }
};
for (const t of Object.values(links)) t.onStatus = onStatus;
$('serialbtn').onclick = async () => {
  if (transport.connected) { await serial.setStream(false); await transport.disconnect(); return; }
  transport = links[$<HTMLSelectElement>('link').value]; serial.attach(transport);
  if (!transport.supported) { $('serialst').textContent = `${transport instanceof BleTransport ? 'Web Bluetooth' : 'Web Serial'} not supported (use Chrome)`; return; }
  try { await transport.connect(); } catch { return; }
  await transport.waitReady();  // port open may have reset the board: wait out its boot
  await pushTime();
  await serial.setStream(true);
  srcRadio('serial').checked = true; inputSource = 'serial';
};
// Live push: coalesce slider edits per key, flush at ≤ 20 Hz. Whole-struct changes push every field.
const dirty = new Map<keyof Params, Params[keyof Params]>();
let flushTimer = 0;
const flush = async () => {
  flushTimer = 0;
  const batch = [...dirty]; dirty.clear();
  const rejected: string[] = [];
  for (const [k, v] of batch) if (!(await transport.setParam(k, v))) rejected.push(k);
  if (rejected.length) $('serialst').textContent = `device rejected: ${rejected.join(', ')} (old firmware?)`;
};
const pushParam = (key?: keyof Params) => {
  if (!transport.connected || !$<HTMLInputElement>('livepush').checked) return;
  if (key) dirty.set(key, params[key]); else for (const k of Object.keys(params) as (keyof Params)[]) dirty.set(k, params[k]);
  if (!flushTimer) flushTimer = window.setTimeout(flush, 50);
};
$('pull').onclick = async () => {
  try {
    Object.assign(params, await transport.getParams());
    legacyPick = '';
    if (matState.mode === 'material') { materialUi.adoptDesign(); materialUi.rederive(true); } // the device's design, re-derived
    panelUi.refresh(); syncView(); save(); $('serialst').textContent = 'pulled';
  }
  catch (e) { $('serialst').textContent = String(e); }
};
$('pushall').onclick = async () => { if (!transport.connected) return; await transport.setParams(params); $('serialst').textContent = 'pushed'; };
$('readfps').onclick = async () => {
  const button = $<HTMLButtonElement>('readfps');
  button.disabled = true;
  try {
    const fps = await transport.getFps();
    if (transport.connected) $('devicefps').textContent = `${fps.toFixed(1)} fps · read ${new Date().toLocaleTimeString()}`;
  } catch (e) {
    if (transport.connected) $('devicefps').textContent = e instanceof Error ? e.message : String(e);
  }
  finally { button.disabled = !transport.connected; }
};
async function pushTime(): Promise<void> {
  if (!transport.connected) { $('serialst').textContent = 'connect first'; return; }
  const button = $<HTMLButtonElement>('settime');
  button.disabled = true;
  try {
    const d = currentDate();
    const speed = timeMode === 'demo' ? demoSpeed : timeMode === 'set' ? 0 : 1;
    if (!Number.isFinite(d.getTime()) || (timeMode === 'set' &&
      (!Number.isInteger(setClock.h) || setClock.h < 0 || setClock.h > 23 ||
       !Number.isInteger(setClock.m) || setClock.m < 0 || setClock.m > 59))) throw new Error('invalid time');
    await transport.setDemoSpeed(speed);
    await transport.setTime(d.getTime(), -d.getTimezoneOffset());
    await transport.setSweep(sweepValue());
    const mode = (speed === 0 ? 'frozen' : speed === 1 ? 'real speed' : `demo ×${speed}`) + (sweep ? `, minutes sweep ${sweepPeriod}s` : '');
    $('serialst').textContent = `${d.toTimeString().slice(0, 8)} sent (${mode})`;
  } catch (e) { $('serialst').textContent = String(e); }
  finally { button.disabled = false; }
}
$('settime').onclick = pushTime;

// params panel
const LAYOUT_KEYS: (keyof Params)[] = ['tubeHeight', 'hoursY', 'minutesY'];
/** Params changed outside a single edit (derive, preset, import): panel, top bar, cuff, grid. */
function paramsReplaced(): void {
  panelUi.refresh(); syncView();
}
/** One legacy key (`key`) or the whole struct (no key) was edited in the legacy panel / top bar. In
 *  material mode a design key goes into the design and re-derives; a whole-struct change (legacy preset,
 *  import, reset) contributes its design keys. Derived / fixed keys are locked there. */
function paramEdited(key?: keyof Params): void {
  if (!key) legacyPick = matState.mode === 'legacy' ? panelUi.presetId() : '';
  if (matState.mode === 'material') {
    if (!key) materialUi.adoptDesign();
    else if (isDesignKey(key)) matState.design = { ...matState.design, [key]: params[key] };
    else { console.warn(`material mode: ${key} is derived, edit ignored`); return; }
    materialUi.rederive(!key);
    return;
  }
  save(); pushParam(key);
  if (!key) syncView();
  if (!key || LAYOUT_KEYS.includes(key)) { applyOverlay(ovlDom, overlay, tubeLayout(params)); drawGrid(); }
}
/** The legacy preset picked in legacy mode ('' after a reset / import / pull): ticking physical material
 *  enters with its physical twin. Consumed by entering material mode. */
let legacyPick = '';
const panelUi = buildPanel($('panel'), params, { onChange: paramEdited });
const materialUi = buildMaterialPanel($('panel'), matState, {
  params,
  onDerived: (changed, whole) => {
    paramsReplaced(); save();
    // whole-state changes resync the device; a field edit pushes only what the derive changed
    if (whole) pushParam(); else for (const k of changed) pushParam(k);
  },
  onMode: (mode) => { panelUi.setLocked(mode === 'material' ? LOCKED_KEYS : new Set()); if (mode === 'material') legacyPick = ''; },
  save,
  onFlags: (keys) => panelUi.setFlagged(keys),
  revealLegacy: (key) => { panelUi.reveal(key); },
  legacyPreset: () => {
    const e = PRESETS.find((x) => x.id === legacyPick);
    return e && { id: e.id, params: presetParams(e) };
  },
});
panelUi.setLocked(matState.mode === 'material' ? LOCKED_KEYS : new Set());

// URL params, applied on top of the restored session — for reproducible states / screenshots:
//   ?fresh=1 (ignore the saved session) &preset=<id from PRESETS> &gas=<id from GAS_MODELS> &t=10:09 &demo=120 &settle=1
//   &along=0.3 &across=0 &scale=3 &cuff=0 &lens=0.6 &lenscurve=1 &lenssmooth=1 &leather=black &grid=1
//   &p.<paramKey>=<value>   e.g. &p.liquid=%2339ff14&p.bubble=0
// Physical material (applied in this order): preset → &material=<id from MATERIAL_PRESETS> (enters
// material mode) → &m.<materialKey>=<value> (enters material mode) → &p.<designKey>=<value>. In material
// mode p.<key> of a derived / fixed key is ignored with a warning; Params are then derived once.
{
  const u = url;
  const typed = (key: keyof Params, v: string): unknown => {
    const cur = (params as any)[key];
    return typeof cur === 'boolean' ? v === '1' || v === 'true' : typeof cur === 'number' ? parseFloat(v) : v;
  };
  const preset = PRESETS.find((e) => e.id === u.get('preset'));
  const gas = u.get('gas'), gasOk = GAS_MODELS.some((g) => g.id === gas);
  if (gas && !gasOk) console.warn(`?gas=${gas}: no such gas model`);
  if (preset) {
    Object.assign(params, presetParams(preset, gasOk ? gas! : preset.gas[0]));
    if (matState.mode === 'material') materialUi.adoptDesign();
  } else if (gasOk && matState.mode !== 'material') Object.assign(params, gasParams(gas!));
  if (u.has('material') && !materialUi.selectPreset(u.get('material')!, true)) console.warn(`?material=${u.get('material')}: no such material preset`);
  for (const [k, v] of u) if (k.startsWith('m.')) {
    const key = k.slice(2);
    if (!(MATERIAL_KEYS as readonly string[]).includes(key)) { console.warn(`?${k}: not a material property, ignored`); continue; }
    if (matState.mode !== 'material') materialUi.enter();
    try { matState.material = validateMaterial({ ...matState.material, [key]: parseFloat(v) }); }
    catch (error) { console.warn(`?${k}=${v} ignored: ${(error as Error).message}`); }
  }
  for (const [k, v] of u) if (k.startsWith('p.')) {
    const key = k.slice(2) as keyof Params;
    if (matState.mode !== 'material') { (params as any)[key] = typed(key, v); continue; }
    if (isDesignKey(key)) matState.design = { ...matState.design, [key]: typed(key, v) };
    else console.warn(`?${k}: ${key} is derived from the material in material mode, ignored`);
  }
  if (u.has('along')) manual.along = +u.get('along')!;
  if (u.has('across')) manual.across = +u.get('across')!;
  if (u.has('t')) { const [h, m] = u.get('t')!.split(':').map(Number); setClock.h = h; setClock.m = m; timeMode = 'set'; }
  if (u.has('demo')) { demoSpeed = +u.get('demo')!; timeMode = 'demo'; }
  if (u.has('scale')) scale = +u.get('scale')!;
  if (u.has('cuff')) overlay.enabled = u.get('cuff') === '1';
  if (u.has('lens')) params.lens = +u.get('lens')!;
  if (u.has('lenscurve')) params.lensCurve = +u.get('lenscurve')!;
  if (matState.mode === 'material') {
    if (u.has('lens')) matState.design = { ...matState.design, lens: params.lens };
    if (u.has('lenscurve')) matState.design = { ...matState.design, lensCurve: params.lensCurve };
    materialUi.refresh();
    materialUi.rederive(true);  // also after a load: the laws may have changed since the session was saved
  }
  if (u.has('lenssmooth')) overlay.lensSmooth = u.get('lenssmooth') === '1';
  if (u.has('leather')) overlay.leather = u.get('leather') as typeof overlay.leather;
  if (u.has('grid')) showGrid = u.get('grid') === '1';
  panelUi.refresh(); syncView();
}

function drawGrid() {
  const g = gridc.getContext('2d')!;
  g.clearRect(0, 0, PANEL_W, PANEL_H);
  if (!showGrid) return;
  g.strokeStyle = 'rgba(255,255,255,0.6)'; g.lineWidth = 1 / Math.min(1, scale); g.setLineDash([4, 4]);
  const { H, yH, yM } = tubeLayout(params);
  for (const y of [yH, yH + H, yM, yM + H]) { g.beginPath(); g.moveTo(0, y + 0.5); g.lineTo(PANEL_W, y + 0.5); g.stroke(); }
  const b0 = Math.min(yH, yM) + H, b1 = Math.max(yH, yM);
  g.fillStyle = 'rgba(255,0,0,0.25)'; g.fillRect(0, b0, PANEL_W, b1 - b0);
  g.fillStyle = '#fff'; g.font = '10px monospace';
  g.fillText(`hours y=${yH}`, 4, yH + 10); g.fillText(`minutes y=${yM}`, 4, yM + 10); g.fillText('bridge (must stay black)', 4, b0 + 14);
}

// ---------- IMU scope: raw (dim) vs filtered (bright) accel + gyro, ~6 s window ----------
// This is how you SEE the filter work: the liquid's response is deliberately tiny (pinned model),
// so slider effects show up here long before they show up in the tube.
const SCOPE_N = 316;
const scope = { rawA: new Float32Array(SCOPE_N), fA: new Float32Array(SCOPE_N), rawG: new Float32Array(SCOPE_N), fG: new Float32Array(SCOPE_N), i: 0 };
function scopePush(raw: TiltInput, filt: TiltInput): void {
  scope.rawA[scope.i] = raw.along; scope.fA[scope.i] = filt.along;
  scope.rawG[scope.i] = raw.gyroAcross; scope.fG[scope.i] = filt.gyroAcross;
  scope.i = (scope.i + 1) % SCOPE_N;
}
const scopeCtx = (document.getElementById('scope') as HTMLCanvasElement).getContext('2d')!;
function drawScope(): void {
  const c = scopeCtx, W = SCOPE_N, laneH = 34;
  c.fillStyle = '#0d0d0d'; c.fillRect(0, 0, W, 70);
  const lane = (buf: Float32Array, yc: number, scale: number, color: string): void => {
    c.strokeStyle = color; c.beginPath();
    for (let x = 0; x < W; x++) {
      const v = buf[(scope.i + x) % SCOPE_N];
      const y = yc - Math.max(-laneH / 2 + 1, Math.min(laneH / 2 - 1, v * scale));
      x === 0 ? c.moveTo(x, y) : c.lineTo(x, y);
    }
    c.stroke();
  };
  c.strokeStyle = '#222'; c.beginPath(); c.moveTo(0, 17.5); c.lineTo(W, 17.5); c.moveTo(0, 52.5); c.lineTo(W, 52.5); c.stroke();
  c.fillStyle = '#333'; c.fillRect(0, 34, W, 1);
  lane(scope.rawA, 17.5, 15, '#555');                      // accel lane: ±1 g full scale
  lane(scope.fA, 17.5, 15, '#5dcaa5');
  lane(scope.rawG, 52.5, 15 / Math.max(50, params.gyroMax), '#3a4a5a'); // gyro lane: ±gyroMax full scale
  lane(scope.fG, 52.5, 15 / Math.max(50, params.gyroMax), '#7ab8ff');
  c.fillStyle = '#666'; c.font = '8px monospace';
  c.fillText('accel g (raw/filt)', 3, 8); c.fillText(`gyro dps ±${Math.round(Math.max(50, params.gyroMax))}`, 3, 43);
}

// ---------- loop: fixed-step physics, decoupled render ----------
let acc = 0, last = performance.now(), frames = 0, fpsT = last;
function currentDate(): Date {
  if (timeMode === 'real') return new Date();
  if (timeMode === 'set') { const d = new Date(); d.setHours(setClock.h, setClock.m, 0, 0); return d; }
  return new Date(demoClock);
}
function physics(dt: number) {
  // Every source — manual sliders included — goes through the SAME ImuFilter the firmware will
  // run, so the IMU-filter sliders are feelable in the browser: drag the panel to feel the accel
  // low-pass lag, flick/shake to feel the gyro high-pass, deadzone and clamp (both are injected
  // as RAW input, before the filter).
  const raw: TiltInput = inputSource === 'manual'
    ? { along: manual.along, across: manual.across, gyroAlong: 0, gyroAcross: 0 }
    : inputSource === 'device'
      ? { along: dev.along, across: dev.across, gyroAlong: 0, gyroAcross: dev.gyroAcross }
      : { ...serial.last };
  if (shakeT > 0) { // ~2.5 Hz wrist shake that dies out over SHAKE_T seconds
    shakeT -= dt; const env = Math.pow(shakeT / SHAKE_T, 1.5);
    raw.along += Math.sin((SHAKE_T - shakeT) * 2 * Math.PI * 2.5) * 0.9 * env;
    raw.gyroAcross += Math.cos((SHAKE_T - shakeT) * 2 * Math.PI * 2.5) * 120 * env;
  }
  if (kick !== 0) { raw.gyroAcross += kick; kick *= Math.exp(-dt / 0.06); if (Math.abs(kick) < 5) kick = 0; }
  if (wristT > 0) { wristT -= dt; raw.gyroAlong += 250 * Math.sin((wristT / 0.5) * Math.PI); }
  Object.assign(input, imuFilter.step(raw, params, dt));
  scopePush(raw, input);
  if (timeMode === 'demo') demoClock += dt * 1000 * demoSpeed;
  const f = fillLevels(currentDate());
  if (sweep) sweepPhase = (sweepPhase + dt / sweepPeriod) % 1;
  followClock(hours, f.hours, dt, clockSet);
  followClock(minutes, sweep ? 1 - Math.abs(2 * sweepPhase - 1) : f.minutes, dt, clockSet);
  clockSet = false;
  stepTube(hours, input, params, dt);
  stepTube(minutes, input, params, dt);
  stepFizz(params, dt, input.along, input.across, hours.agitation);
}
function frame(now: number) {
  requestAnimationFrame(frame);
  const dt = Math.min(0.25, (now - last) / 1000); last = now;
  if (!paused) { acc += dt; while (acc >= PHYS_DT) { physics(PHYS_DT); acc -= PHYS_DT; } }
  if (params.vertical !== shownVertical) setScale();
  renderFrame(hours, minutes, params, true, overlay.lensSmooth);
  blit(img); fullctx.putImageData(img, 0, 0);
  fbctx.imageSmoothingEnabled = scale < 1; fbctx.drawImage(fullc, 0, 0);
  drawScope();
  frames++;
  if (now - fpsT > 1000) {
    $('fps').textContent = `${String(frames).padStart(3)} fps · fill h=${hours.fillTarget.toFixed(3)} m=${minutes.fillTarget.toFixed(3)} · angle ${hours.angle.toFixed(1).padStart(5)}° · cap ${hours.cap.toFixed(1).padStart(5)} px · read ${hours.reading.toFixed(2)}`;
    frames = 0; fpsT = now;
  }
  const d = currentDate();
  $('clock').textContent = d.toTimeString().slice(0, 8);
  const f2 = (v: number) => (v < 0 ? '' : '+') + v.toFixed(2); // sign-stable width
  $('imuraw').textContent = `filtered  along ${f2(input.along)}  across ${f2(input.across)}  gyro ${String(Math.round(input.gyroAcross)).padStart(5)}`
    + (transport.connected ? ` | ${serial.raw}`.slice(0, 46).padEnd(46) : ''); // fixed length: never widens the box
}
if (url.has('settle')) for (let i = 0; i < 250; i++) physics(PHYS_DT); // springs at rest for screenshots
requestAnimationFrame(frame);

// dev hook
(window as any).sim = { params, hours, minutes, fb, fizz, overlay, material: matState, links }; // links: check-material-ui stubs a transport
