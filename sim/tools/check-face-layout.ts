// Face layout (render.ts faceLayout; firmware render.h mirrors it): for every board, LCD res tag and tube count the
// sim takes, every preset and a tubeHeight / row sweep, the tubes lie in face order (hours, minutes, seconds), do not
// overlap and stay inside the canvas; a two-tube face keeps each tube at its own params' row (as before the seconds
// tube); a three-tube face keeps the rows boardParams capped (TUBE3_HEIGHT_MAX).
// Run: npm run check:layout (the parent spawns one child per configuration: spec/layout reads LW_* at import).
const { execFileSync } = require('child_process'); declare const process: any; declare function require(m: string): any;
declare const __filename: string;
import { BOARD_TAG, PANEL_H, TUBE_COUNT, TUBE3_HEIGHT_MAX, LCD_RES, resTag } from '@spec/layout';
import { DEFAULT_PARAMS, PRESETS, presetParams, tubeParams, type Params } from '../src/params';
import { faceLayout, tubeLayout, tubeRows } from '../src/render';

if (!process.env.LW_CHILD) {
  const runs: Record<string, string>[] = [];
  for (const tubes of ['2', '3']) {
    runs.push({ LW_BOARD: 'amoled191', LW_TUBES: tubes });
    const n = +tubes;
    for (const rows of LCD_RES) for (let bits = 0; bits < 1 << n; bits++)
      runs.push({ LW_BOARD: 'lcd316', LW_RES: resTag(rows, [...Array(n)].map((_, i) => !!(bits & (1 << i)))), LW_TUBES: tubes });
  }
  let bad = 0;
  for (const env of runs) {
    try { process.stdout.write(execFileSync('node', [__filename], { env: { ...process.env, ...env, LW_CHILD: '1' } }).toString()); }
    catch (e: any) { bad++; process.stdout.write(String(e.stdout ?? '') + String(e.stderr ?? '')); }
  }
  console.log(bad ? `${bad} of ${runs.length} configurations FAILED` : `face layout: ${runs.length} configurations ok`);
  process.exit(bad ? 1 : 0);
}

const cases: [string, Params][] = PRESETS.map((e) => [e.id, presetParams(e)]);
for (let h = 4; h <= 80; h++) for (const hoursY of [0, 12, 100, 224]) for (const minutesY of [0, 100, 168, 185, 224])
  cases.push([`h${h} y${hoursY}/${minutesY}`, { ...DEFAULT_PARAMS, tubeHeight: h, hoursY, minutesY }]);
let fails = 0;
for (const [name, p] of cases) {
  const ps = tubeParams(p), lay = faceLayout(ps), rows = ps.map((_, i) => tubeRows(lay, i));
  const err = (m: string): void => { if (fails++ < 10) console.log(`  FAIL ${BOARD_TAG} ${name}: ${m} ${JSON.stringify(lay)}`); };
  rows.forEach((r, i) => {
    if (r.H !== tubeLayout(ps[i]).H) err(`tube ${i} rows ${r.H}, its params ${tubeLayout(ps[i]).H}`);
    if (r.y < 0 || r.y + r.H > PANEL_H) err(`tube ${i} off the canvas`);
    if (TUBE_COUNT === 3 && r.H > TUBE3_HEIGHT_MAX) err(`tube ${i} taller than a third`);
  });
  if (TUBE_COUNT === 2) { if (lay.yH !== tubeLayout(ps[0]).yH || lay.yM !== tubeLayout(ps[1]).yM) err('two-tube rows moved'); }
  else for (let i = 1; i < 3; i++) if (rows[i].y < rows[i - 1].y + rows[i - 1].H) err(`tube ${i} overlaps tube ${i - 1}`);
}
console.log(`${fails ? 'FAIL' : 'ok  '} ${BOARD_TAG}: ${cases.length} layouts${fails ? `, ${fails} failures` : ''}`);
process.exit(fails ? 1 : 0);
