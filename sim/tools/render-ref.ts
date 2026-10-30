// Headless reference render: reads a JSON {params, hours, minutes, sprite:{i,w,h,cellW,cellH,widths,rgbaFile}, digitShift?}
// from argv[2], renders one frame exactly as the browser sim would (fizz must be off), writes the
// PANEL_W x PANEL_H RGB565 framebuffer (little-endian u16) to argv[3]. Used by firmware/tools/compare-device.py.
// Board: LW_BOARD / LW_RES (spec/layout.ts), as the device reports it (`v`); params are the device's (design px).
// Run: see compare-device.py (compiles with tsc like check:imu).
// eslint-disable-next-line @typescript-eslint/no-var-requires
const fs = require('fs'); declare const process: any; declare const Buffer: any; declare function require(m: string): any;
import { renderFrame, fb, setSprite, setDigitHold } from '../src/render';
import { newTube, type TubeState } from '../src/physics';
import { boardParams } from '../src/params';
import { TUBE_LENGTH_PX } from '@spec/layout';

const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
if (job.sprite) {
  const sp = job.sprite;
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
const h: TubeState = { ...newTube(), ...job.hours }, m: TubeState = { ...newTube(), ...job.minutes };  // device STATE carries only the drawn fields
trace(job.hours.trace, job.hours.traceWet, h); trace(job.minutes.trace, job.minutes.traceWet, m);
// the sprite digits' whole-px shift the board held (`DIGITS` line of the `x` dump; render.ts DigitHold): carried
// across frames, so one dumped state alone would not give it
if (Array.isArray(job.digitShift)) job.digitShift.forEach((d: number[], i: number) => setDigitHold(i, d[0], d[1]));
renderFrame(h, m, boardParams(job.params));
fs.writeFileSync(process.argv[3], Buffer.from(fb.buffer, fb.byteOffset, fb.byteLength));
console.log('ok');
