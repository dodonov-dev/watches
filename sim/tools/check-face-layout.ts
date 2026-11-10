// Face layout (render.ts faceLayout; firmware render.h mirrors it): for every board, LCD res tag and tube count the
// sim takes, every preset and a tubeHeight / row sweep, the tubes lie in face order (hours, minutes, seconds), do not
// overlap and stay inside the canvas; a two-tube face keeps each tube at its own params' row (as before the seconds
// tube); a three-tube face keeps the rows boardParams capped (tube3HeightAt) and fits the canvas. Stacked (tubeStack): the
// tubes lie tubeGap mm apart by the panel's pitch (cut to the rows the canvas has left), the stack centred. Tube widths:
// every narrow / wide combination, plus mm faces (MM_TAGS).
// Run: npm run check:layout (the parent spawns one child per configuration: spec/layout reads LW_* at import).
const { execFileSync } = require('child_process'); declare const process: any; declare function require(m: string): any;
declare const __filename: string;
import { BOARD, BOARD_TAG, PANEL_H, LCD_PANEL_H, TUBE_COUNT, TUBE_PX_SCALE, LCD_RES, NARROW_MM, resTag, tube3HeightAt } from '@spec/layout';
import { DEFAULT_PARAMS, PRESETS, presetParams, tubeParams, type Params } from '../src/params';
import { faceLayout, tubeLayout, tubeRows } from '../src/render';

// mm faces (layout.h LCD_MM_x): the widest and narrowest, equal mm, mm next to wide / narrow.
const MM_TAGS: Record<number, string[]> = { 2: ['10-6', '10-10', '3-f', '7.5-f'], 3: ['10-8-6', '9-7-5', '10-10-10', '3-3-3', 'f-7-5', '10-f-10', '6-6-9.5'] };
if (!process.env.LW_CHILD) {
  const runs: Record<string, string>[] = [];
  for (const tubes of ['2', '3']) {
    runs.push({ LW_BOARD: 'amoled191', LW_TUBES: tubes });
    const n = +tubes;
    for (const rows of LCD_RES) for (let bits = 0; bits < 1 << n; bits++)
      runs.push({ LW_BOARD: 'lcd316', LW_RES: resTag(rows, [...Array(n)].map((_, i) => bits & (1 << i) ? 'f' : NARROW_MM)), LW_TUBES: tubes });
    for (const rows of [240, 320]) for (const w of MM_TAGS[n]) runs.push({ LW_BOARD: 'lcd316', LW_RES: `${rows}w${w}`, LW_TUBES: tubes });
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
for (let h = 4; h <= 80; h += 4) for (const tubeGap of [0, 0.1, 0.5, 1, 2.5, 6, 10, 400, -3])
  cases.push([`h${h} stacked ${tubeGap} mm`, { ...DEFAULT_PARAMS, tubeHeight: h, hoursY: 12, minutesY: 100, tubeStack: true, tubeGap }]);
// mm per canvas px, from the panels' pitches (not from spec/layout PX_PER_MM, which the layout under test reads)
const MM_PER_PX = BOARD === 'lcd316' ? 0.0912 * LCD_PANEL_H / PANEL_H : 0.083;
let fails = 0;
for (const [name, p] of cases) {
  const ps = tubeParams(p), lay = faceLayout(ps), rows = ps.map((_, i) => tubeRows(lay, i));
  const err = (m: string): void => { if (fails++ < 10) console.log(`  FAIL ${BOARD_TAG} ${name}: ${m} ${JSON.stringify(lay)}`); };
  rows.forEach((r, i) => {
    if (r.H !== tubeLayout(ps[i]).H) err(`tube ${i} rows ${r.H}, its params ${tubeLayout(ps[i]).H}`);
    if (r.y < 0 || r.y + r.H > PANEL_H) err(`tube ${i} off the canvas`);
    if (TUBE_COUNT === 3 && r.H > tube3HeightAt(TUBE_PX_SCALE[i])) err(`tube ${i} taller than its share ${tube3HeightAt(TUBE_PX_SCALE[i])}`);
  });
  if (rows.reduce((a, r) => a + r.H, 0) > PANEL_H) err('tubes taller than the canvas');
  for (let i = 1; i < rows.length; i++) if (rows[i].y < rows[i - 1].y + rows[i - 1].H && (TUBE_COUNT === 3 || p.tubeStack)) err(`tube ${i} overlaps tube ${i - 1}`);
  if (p.tubeStack) {
    const n = rows.length, sum = rows.reduce((a, r) => a + r.H, 0), gaps = rows.slice(1).map((r, i) => r.y - rows[i].y - rows[i].H);
    const room = Math.floor((PANEL_H - sum) / (n - 1)), want = Math.max(0, p.tubeGap) / MM_PER_PX;
    if (gaps.some((g) => g !== gaps[0])) err('stacked gaps differ');
    if (gaps[0] > room || (gaps[0] < room ? Math.abs(gaps[0] - want) > 0.501 : want < room - 0.501)) err(`stacked gap ${gaps[0]} px, asked ${want.toFixed(2)}, room ${room}`);
    const below = PANEL_H - rows[n - 1].y - rows[n - 1].H;
    if (below - rows[0].y < 0 || below - rows[0].y > 1) err(`stack off centre: ${rows[0].y} rows above, ${below} below`);
  } else if (TUBE_COUNT === 2 && (lay.yH !== tubeLayout(ps[0]).yH || lay.yM !== tubeLayout(ps[1]).yM)) err('two-tube rows moved');
}
console.log(`${fails ? 'FAIL' : 'ok  '} ${BOARD_TAG}: ${cases.length} layouts${fails ? `, ${fails} failures` : ''}`);
process.exit(fails ? 1 : 0);
