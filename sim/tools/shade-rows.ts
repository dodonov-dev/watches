// The edge shade factors (render.ts edgeShadeRows) of every tube for each look of a JSON list (argv[2]): one line per
// look, "i:H:T,T,...:L,L,...;" per tube (its rows (factors, empty when off; the fold's lens map lensSourceRows, empty without a lens). Board: LW_BOARD / LW_RES / LW_TUBES. Run by firmware/tools/check_shade_rows.py.
const fs = require('fs'); declare const process: any; declare function require(m: string): any;
import { edgeShadeRows, faceLayout, lensSourceRows, tubeRows } from '../src/render';
import { tubeParams, type Params } from '../src/params';
const looks: Params[] = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
for (const p of looks) {
  const ps = tubeParams(p), lay = faceLayout(ps);
  process.stdout.write(ps.map((q, i) => {
    const r = tubeRows(lay, i), T = edgeShadeRows(i, r.y, r.H, q), L = lensSourceRows(r.H, q);
    return `${i}:${r.H}:${T ? Array.from(T).join(',') : ''}:${L ? Array.from(L).join(',') : ''}`;
  }).join(';') + '\n');
}
