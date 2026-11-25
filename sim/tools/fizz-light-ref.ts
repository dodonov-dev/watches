// fizzPhys's kernel (src/fizzLight.ts) on a job file (argv[2]), the sim side of firmware/tools/check_fizz_light.py.
// Input lines: "F transparency R upX lightDeg lid tau delta exposed tone" (a frame), "B x y z r S SL B" (a bubble of the
// last frame), "T rim liqA liqB" (fizzTone, RGB565); numbers as float32 bits in hex (the check's generator).
// Output: "A" + FIZZ_ATT; per frame "L" + its FizzLight fields; per bubble "O K cx cy wl tv sk"; per tone "T tone":
// float32 bits in hex (8 digits), booleans 0 / 1, in the order of fizz_light.h's driver.
const fs = require('fs'); declare const process: any; declare function require(m: string): any;
import { FIZZ_ATT, fizzLightFrame, fizzLit, fizzTone, newFizzLit, type FizzLight } from '../src/fizzLight';
const buf = new DataView(new ArrayBuffer(4));
const fromHex = (h: string): number => { buf.setUint32(0, parseInt(h, 16)); return buf.getFloat32(0); };
const hex = (v: number): string => { buf.setFloat32(0, v); return buf.getUint32(0).toString(16).padStart(8, '0'); };
const out: string[] = ['A ' + Array.from(FIZZ_ATT, hex).join(' ')];
let lit: FizzLight | null = null;
const o = newFizzLit();
for (const line of fs.readFileSync(process.argv[2], 'utf8').split('\n')) {
  const w = line.trim().split(/\s+/);
  if (w[0] === 'F') {
    const v = w.slice(1).map(fromHex);
    lit = fizzLightFrame(v[0], v[1], v[2], v[3], v[4] !== 0, v[5], v[6], Math.round(v[7]), v[8]);
    const L = lit;
    out.push(['L', hex(L.a8), hex(L.R), hex(L.R2), ...Array.from(L.w, hex), ...Array.from(L.invS, hex), ...Array.from(L.invH, hex),
      hex(L.ly), hex(L.lz), hex(L.la), hex(L.invA), hex(L.fk), hex(L.hx), hex(L.hy), L.openR ? 1 : 0, L.openL ? 1 : 0, L.lid ? 1 : 0,
      hex(L.kLid), hex(L.tone)].join(' '));
  } else if (w[0] === 'B' && lit) {
    const v = w.slice(1).map(fromHex);
    fizzLit(lit, v[0], v[1], v[2], v[3], v[4], v[5], v[6], o);
    out.push(['O', hex(o.K), hex(o.cx), hex(o.cy), hex(o.wl), hex(o.tv), hex(o.sk)].join(' '));
  } else if (w[0] === 'T') {
    const v = w.slice(1).map((h: string) => parseInt(h, 16));
    out.push('T ' + hex(fizzTone(v[0], v[1], v[2])));
  }
}
process.stdout.write(out.join('\n') + '\n');
