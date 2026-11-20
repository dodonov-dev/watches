// Face layout (render.ts faceLayout; firmware render.h mirrors it): for every board, LCD res tag and tube count the
// sim takes, every preset and a tubeHeight / row sweep, the tubes lie in face order (hours, minutes, seconds), do not
// overlap and stay inside the canvas; a two-tube face keeps each tube at its own params' row (as before the seconds
// tube); a three-tube face keeps the rows boardParams capped (tube3HeightAt) and fits the canvas. Stacked (tubeStack): the
// tubes lie tubeGap mm apart by the panel's pitch (cut to the rows the canvas has left), the stack centred. Tube widths:
// every narrow / wide combination, plus mm faces (MM_TAGS). Edge shade (render.ts edgeShadeRows): on every tube of every
// layout, each panel row (the LCD's 320, nearest-neighbour from the canvas rows) gets a factor within 1/256 of the mean
// of the ideal ones of the panel rows its canvas row covers (at 320 rows and on the AMOLED: the ideal one), the ideal one
// from that panel row's mm off the tube's centre on the panel at the panel's own pitch, through the rod: here
// docs/physical-tube-model.py's source() with its trigonometry, the fold by sampling and the inverse by bisection in x
// (not render.ts's algebra). 320w8-8 prints a table of the profile once.
// Run: npm run check:layout (the parent spawns one child per configuration: spec/layout reads LW_* at import).
const { execFileSync } = require('child_process'); declare const process: any; declare function require(m: string): any;
declare const __filename: string;
import { BOARD, BOARD_TAG, PANEL_H, LCD_PANEL_H, LCD_MM_PER_PX, TUBE_COUNT, TUBE_PX_SCALE, LCD_RES, NARROW_MM, resTag, tube3HeightAt, TUBE_ROD_MM, ROD_GAP_MM, ROD_N } from '@spec/layout';
import { DEFAULT_PARAMS, PRESETS, presetParams, tubeParams, type Params } from '../src/params';
import { edgeShadeRows, faceLayout, tubeLayout, tubeRows } from '../src/render';

// mm faces (layout.h LCD_MM_x): the widest and narrowest, equal mm, mm next to wide / narrow.
const MM_TAGS: Record<number, string[]> = { 2: ['10-6', '10-10', '3-f', '7.5-f', '8-8'], 3: ['10-8-6', '9-7-5', '10-10-10', '3-3-3', 'f-7-5', '10-f-10', '6-6-9.5'] };
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
const MM_PER_PX = BOARD === 'lcd316' ? LCD_MM_PER_PX * LCD_PANEL_H / PANEL_H : 0.083;
// Edge shade: the panel's rows (the LCD's 320 / the AMOLED's own), canvas row y covering [bs(y), bs(y + 1)), mm per panel row
const PANEL_ROWS = BOARD === 'lcd316' ? LCD_PANEL_H : PANEL_H, PANEL_MM = BOARD === 'lcd316' ? LCD_MM_PER_PX : 0.083;
const bs = (y: number): number => Math.floor((y * PANEL_ROWS + PANEL_H - 1) / PANEL_H);
const SHADES: [number, number][] = [[0.67, 1], [1, 0.25], [1, 4], [0.6, 2.5]];   // edgeShade, edgeShadePow
// docs/physical-tube-model.py source(x, R, gap, n): the screen offset seen at apparent offset x
const source = (x: number, R: number, g: number, n: number): number => {
  const al = Math.asin(x / R), th = al - Math.asin(Math.sin(al) / n), z = Math.sqrt(R * R - x * x), sa = n * Math.sin(th);
  return Math.abs(sa) >= 1 ? NaN : x - z * Math.tan(th) - g * Math.tan(Math.asin(sa));
};
const rodModel = TUBE_ROD_MM.map((mm) => {   // per tube: radius, the fold (by sampling), the ideal w(d) at power 1
  const R = mm / 2; let xF = 0, dF = -1;
  for (let i = 1; i < 200000; i++) { const x = R * i / 200000, d = source(x, R, ROD_GAP_MM, ROD_N); if (d > dF) { dF = d; xF = x; } }
  const xOf = (d: number): number => { let lo = 0, hi = xF; for (let i = 0; i < 80; i++) { const m = (lo + hi) / 2; if (source(m, R, ROD_GAP_MM, ROD_N) < d) lo = m; else hi = m; } return (lo + hi) / 2; };
  const memo = new Map<number, number>();   // by the row's offset in half panel rows (|n + 0.5 - c| is a multiple of 0.5)
  const baseAt = (h: number): number => { let v = memo.get(h); if (v === undefined) { const d = h / 2 * PANEL_MM; v = d >= dF ? 1 : xOf(d) / xF; memo.set(h, v); } return v; };
  return { R, xF, dF, base: (d: number): number => d >= dF ? 1 : xOf(d) / xF, baseAt, xOf };
});
if (BOARD_TAG === 'lcd316@320w8-8') {
  const m = rodModel[0];
  console.log(`  rod 320w8-8: R ${m.R.toFixed(4)} mm, gap ${ROD_GAP_MM}, n ${ROD_N}: fold at x ${m.xF.toFixed(4)} mm (alpha ${(Math.asin(m.xF / m.R) * 180 / Math.PI).toFixed(2)} deg), d ${m.dF.toFixed(4)} mm`);
  console.log('    d mm   x mm   alpha deg   source(x) mm   w (pow 1)');
  for (let d = 0; d <= 3.0001; d += 0.25) {
    const x = d >= m.dF ? m.xF : m.xOf(d), w = m.base(d) ** 2;
    console.log(`    ${d.toFixed(2)}   ${x.toFixed(4)}   ${(Math.asin(x / m.R) * 180 / Math.PI).toFixed(2).padStart(6)}      ${source(x, m.R, ROD_GAP_MM, ROD_N).toFixed(4)}       ${w.toFixed(4)}`);
  }
}
let fails = 0, shadeRowsChecked = 0;
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
  for (const [k, pw] of SHADES) rows.forEach((r, i) => {
    const q = { ...ps[i], edgeShade: k, edgeShadePow: pw }, T = edgeShadeRows(i, r.y, r.H, q)!;
    const p0 = bs(r.y), p1 = bs(r.y + r.H), c = (p0 + p1) / 2;
    const ideal = (n: number): number => k * rodModel[i].baseAt(Math.round(Math.abs(n + 0.5 - c) * 2)) ** (2 * pw) * 256;
    for (let n = p0; n < p1; n++) {
      const y = Math.floor(n * PANEL_H / PANEL_ROWS), g = [...Array(bs(y + 1) - bs(y))].map((_, j) => ideal(bs(y) + j));
      const t = T[y - r.y], mean = g.reduce((s, v) => s + v, 0) / g.length;   // the covered panel rows' mean, not just its range
      if (Math.abs(t - mean) > 1) { err(`edge shade ${k}/${pw} tube ${i} panel row ${n}: ${t}, ideal mean ${mean.toFixed(1)} of ${g.map((v) => v.toFixed(1))}`); return; }
    }
    shadeRowsChecked += p1 - p0;
  });
}
console.log(`${fails ? 'FAIL' : 'ok  '} ${BOARD_TAG}: ${cases.length} layouts, edge shade ${shadeRowsChecked} panel rows${fails ? `, ${fails} failures` : ''}`);
process.exit(fails ? 1 : 0);
