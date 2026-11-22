// Headless reference render: reads a JSON {params, hours, minutes, seconds?, sprites:[{i,w,h,cellW,cellH,widths,rgbaFile}]}
// (the digit sheet at each cell height: the canvas's is used, SPRITE_CELL_H; `sprite`: one sheet) from argv[2], renders one frame exactly as the browser sim would (fizz must be off), writes the
// PANEL_W x PANEL_H RGB565 framebuffer (little-endian u16) to argv[3]. Used by firmware/tools/compare-device.py.
// Board: LW_BOARD / LW_RES / LW_TUBES (spec/layout.ts), as the device reports it (`v`); params are the device's (design px).
// Three tubes: `seconds` is the seconds tube's state (required then).
// Run: see compare-device.py (compiles with tsc like check:imu).
// Stepped fizz job (`fizzSteps` in the job; firmware/tools/check_fizz_steps.py --sim): params are design params (a preset
// file's fields over DEFAULT_PARAMS); the fizz draws come from the shared seeded generator (xorshift32, (word >>> 8) / 2^24,
// the native stub's); a frame before the first step, after every `every`-th and before a run that changes params; after
// each step (and its frame) one state line per tube to argv[3] ('-' = stdout): `S step tube fizzN draws springClock
// springScatter bodyH blocked`, x y v life z and the vertical body's y z contact per slot, then the frame's surfaces it steps on: `len exposed shift H` + surf, surfL per
// row. lockstep (a file of the firmware's lines): each step starts from the firmware's state and surfaces.
// eslint-disable-next-line @typescript-eslint/no-var-requires
const fs = require('fs'); declare const process: any; declare const Buffer: any; declare function require(m: string): any;
import { renderFrame, fb, setSprite, stepFizz, fizzTestState, fizzTestLoad, fizzTestInputs } from '../src/render';
import { newTube, type TubeState } from '../src/physics';
import { tubeParams, migrateParams, DEFAULT_PARAMS, type Params } from '../src/params';
import { TUBE_COUNT, TUBE_LENGTH_PX, SPRITE_CELL_H } from '@spec/layout';

const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const sheets: any[] = job.sprites ?? (job.sprite ? [job.sprite] : []);
if (sheets.length) {
  const sp = sheets.find((s) => s.cellH === SPRITE_CELL_H);
  if (!sp) throw new Error(`render-ref: the job has no digit sheet of ${SPRITE_CELL_H} rows (has ${sheets.map((s) => s.cellH).join(', ')})`);
  const data = new Uint8ClampedArray(fs.readFileSync(sp.rgbaFile));
  setSprite(sp.i, { cellW: sp.cellW, cellH: sp.cellH, widths: sp.widths, data, w: sp.w, h: sp.h });
}
// dried-trace residue and its wet part dumped by the board (`TRACE` / `WET` lines of the `x` dump), 4 hex
// chars per column; the render reads the residue only
const hex16 = (hex: unknown): Uint16Array => {
  const a = new Uint16Array(TUBE_LENGTH_PX);
  if (typeof hex === 'string' && hex.length >= 4 * TUBE_LENGTH_PX) for (let i = 0; i < a.length; i++) a[i] = parseInt(hex.substr(i * 4, 4), 16);
  return a;
};
const trace = (hex: unknown, wet: unknown, st: TubeState): void => {
  st.traceWet = hex16(wet);
  if (typeof hex !== 'string' || hex.length < 4 * TUBE_LENGTH_PX) return;
  const a = hex16(hex);
  st.trace = a;
  // the render only draws inside [traceLo, traceHi) — recover the bounds the device's physics held
  let lo = TUBE_LENGTH_PX, hi = 0;
  for (let i = 0; i < a.length; i++) if (a[i]) { if (i < lo) lo = i; hi = i + 1; }
  st.traceLo = lo; st.traceHi = hi;
};
const names = ['hours', 'minutes', 'seconds'].slice(0, TUBE_COUNT);
if (names.some((k) => !job[k])) throw new Error(`render-ref: the job needs ${names.join(', ')} (LW_TUBES=${TUBE_COUNT})`);
const tubes: TubeState[] = names.map((k) => ({ ...newTube(), ...job[k] }));   // device STATE carries only the drawn fields
names.forEach((k, i) => trace(job[k].trace, job[k].traceWet, tubes[i]));
if (job.fizzSteps) fizzJob(job.fizzSteps);
else {
  renderFrame(tubes, tubeParams(job.params));   // each tube at its own px scale (LW_RES tube widths)
  fs.writeFileSync(process.argv[3], Buffer.from(fb.buffer, fb.byteOffset, fb.byteLength));
  console.log('ok');
}

interface FizzRun { n: number; dt: number; along: number; across: number; normal?: number; agitation: number; set?: Partial<Params> }
// lockstep: the firmware's state lines of the same job (a file): each step starts from the firmware's state after the
// step before (and its frame), so a comparison sees one step's arithmetic, not doubles and floats drifting apart.
// inputs (a file of the firmware's F lines, one per tube after each of its frames: len exposed shift H, surf, surfL,
// strokeR, strokeL per row): after each frame the kernel's inputs are the firmware frame's (--free: the state runs free).
function fizzJob(fj: { seed: number; every: number; runs: FizzRun[]; lockstep?: string; inputs?: string }): void {
  let x = fj.seed >>> 0 || 1, draws = 0;
  Math.random = (): number => {   // the fizz's only random source: the native stub's xorshift32, counted
    x = (x ^ (x << 13)) >>> 0; x = (x ^ (x >>> 17)) >>> 0; x = (x ^ (x << 5)) >>> 0; draws++;
    return (x >>> 8) / 16777216;
  };
  const inp: string[][] = fj.inputs ? fs.readFileSync(fj.inputs, 'utf8').split('\n').filter((l: string) => l).map((l: string) => l.split(' ')) : [];
  let inpAt = 0;
  const frame = (ps: readonly Params[]): void => {
    renderFrame(tubes, ps);
    if (!inp.length) return;
    tubes.forEach((_, i) => {
      const w = inp[inpAt++];
      if (!w || +w[2] !== i) throw new Error(`render-ref: inputs line ${inpAt}: ${w ? w.slice(0, 3).join(' ') : 'missing'}, want tube ${i}`);
      const H = +w[6], rows = (k: number): Float32Array => Float32Array.from(w.slice(7 + k * H, 7 + (k + 1) * H), Number);
      fizzTestInputs(i, +w[3], +w[4], +w[5], rows(0), rows(1), rows(2), rows(3));
    });
  };
  const ref: string[][] = fj.lockstep ? fs.readFileSync(fj.lockstep, 'utf8').split('\n').filter((l: string) => l).map((l: string) => l.split(' ')) : [];
  let design: Params = { ...DEFAULT_PARAMS, ...migrateParams(job.params) }, ps = tubeParams(design);
  const g = (v: number): string => (Object.is(v, -0) ? 0 : v).toPrecision(9);
  const out: string[] = [];
  let step = 0;
  for (const run of fj.runs) {
    if (run.set) { design = { ...design, ...run.set }; ps = tubeParams(design); }
    // the run's gain-free pose: physics.cpp updatePose in float32 (the native harness's), face up when it is not valid
    const f = Math.fround, px = f(-f(run.along)), py = f(-f(run.across)), pz = f(run.normal ?? 1), m2 = f(f(f(px * px) + f(py * py)) + f(pz * pz));
    const ok = m2 >= f(f(0.3) * f(0.3)) && Number.isFinite(m2), inv = f(1 / f(Math.sqrt(m2)));
    const pose = ok ? { x: f(px * inv), y: f(py * inv), z: f(pz * inv) } : { x: 0, y: 0, z: 1 };
    if (step === 0 || run.set) frame(ps);   // the first frame, and one after a params change (the native job's)
    for (let k = 0; k < run.n; k++) {
      if (ref.length && step > 0 && !(k === 0 && run.set)) tubes.forEach((_, i) => {
        const w = ref[(step - 1) * tubes.length + i], n = +w[3], slots = [], body = new Float32Array(2 * n), contact = new Uint8Array(n), e = 9 + 8 * n, H = +w[e + 3];
        if (+w[1] !== step || +w[2] !== i) throw new Error(`render-ref: lockstep line ${w.slice(0, 3).join(' ')}, want step ${step} tube ${i}`);
        for (let s = 0, o = 9; s < n; s++, o += 8) {
          slots.push({ x: +w[o], y: +w[o + 1], v: +w[o + 2], life: +w[o + 3], z: +w[o + 4] }); body[2 * s] = +w[o + 5]; body[2 * s + 1] = +w[o + 6]; contact[s] = +w[o + 7];
        }
        const rows = (o: number): Float32Array => Float32Array.from(w.slice(o, o + H), Number);
        fizzTestLoad(i, { fizz: slots, springClock: +w[5], springScatter: +w[6], body, contact, bodyH: +w[7], blocked: +w[8],
          len: +w[e], exposed: +w[e + 1], shift: +w[e + 2], surf: rows(e + 4), surfL: rows(e + 4 + H) });
      });
      for (const t of tubes) t.agitation = run.agitation;
      stepFizz(ps, run.dt, run.along, run.across, run.agitation, pose);
      step++;
      if (step % fj.every === 0) frame(ps);
      tubes.forEach((_, i) => {   // after the step and its frame
        const st = fizzTestState(i);
        let line = `S ${step} ${i} ${st.fizz.length} ${draws} ${g(st.springClock)} ${g(st.springScatter)} ${st.bodyH} ${st.blocked}`;
        st.fizz.forEach((f, k) => { line += ` ${g(f.x)} ${g(f.y)} ${g(f.v)} ${g(f.life)} ${g(f.z)} ${g(st.body[2 * k])} ${g(st.body[2 * k + 1])} ${st.contact[k]}`; });
        line += ` ${g(st.len)} ${st.exposed} ${g(st.shift)} ${st.surf.length}`;
        for (const v of st.surf) line += ` ${g(v)}`;
        for (const v of st.surfL) line += ` ${g(v)}`;
        out.push(line);
      });
    }
  }
  out.push('');
  if (process.argv[3] === '-') process.stdout.write(out.join('\n')); else fs.writeFileSync(process.argv[3], out.join('\n'));
}
