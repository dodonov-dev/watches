// The desk-view lid's law (src/lidLaw.ts) on a job file (argv[2]), the sim side of firmware/tools/check_lid_law.py.
// Input lines: "W tau delta thetaDeg transparency" (a law), "P q u" (a point of the last law), "K angle key" (lidKey);
// numbers as float32 bits in hex (the check's generator).
// Output: per law "L tanT tanD sd cd A k8 inv1t lam[LID_N + 1] keep[LID_N + 1]", per point "O lidOpacity lidWet", per key
// "Y lidKey": float32 bits in hex. tanT .. A are lidLawBuild's own first lines (the inputs of its sample loop, which the native side can be
// fed): if they drifted from lidLaw.ts the fed tables would stop matching the sim's bit for bit.
const fs = require('fs'); declare const process: any; declare function require(m: string): any;
import { LID_N, lidKey, lidLawBuild, lidOpacity, lidWet, newLidLaw } from '../src/lidLaw';
const F = Math.fround;
const buf = new DataView(new ArrayBuffer(4));
const fromHex = (h: string): number => { buf.setUint32(0, parseInt(h, 16)); return buf.getFloat32(0); };
const hex = (v: number): string => { buf.setFloat32(0, v); return buf.getUint32(0).toString(16).padStart(8, '0'); };
const out: string[] = [];
const law = newLidLaw(); let have = false;
for (const line of fs.readFileSync(process.argv[2], 'utf8').split('\n')) {
  const w = line.trim().split(/\s+/);
  if (w[0] === 'W') {
    const [tau, delta, thetaDeg, transparency] = w.slice(1).map(fromHex);
    lidLawBuild(law, tau, delta, thetaDeg, transparency);
    const th = F(Math.max(20, Math.min(89, thetaDeg)) * F(Math.PI / 180));
    const trig = [F(Math.tan(tau)), F(Math.tan(delta)), F(Math.sin(delta)), F(Math.cos(delta)), F(1 / F(Math.cos(th)))];
    if (law.lam.length !== LID_N + 1) throw new Error('LID_N');
    out.push(['L', ...trig.map(hex), hex(law.k8), hex(law.inv1t), ...Array.from(law.lam, hex), ...Array.from(law.keep, hex)].join(' '));
    have = true;
  } else if (w[0] === 'K') {
    const [angle, key] = w.slice(1).map(fromHex);
    out.push('Y ' + hex(lidKey(angle, key)));
  } else if (w[0] === 'P' && have) {
    const [q, u] = w.slice(1).map(fromHex);
    out.push(['O', hex(lidOpacity(law, q, u)), hex(lidWet(law, q, u))].join(' '));
  }
}
process.stdout.write(out.join('\n') + '\n');
