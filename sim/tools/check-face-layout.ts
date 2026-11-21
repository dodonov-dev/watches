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
const SHADES: [number, number, number][] = [[0.7, 1.5, 0.4], [1, 0.5, 0], [1, 3, 1], [0.3, 2, 0.4], [0.42, 1, 0.8]];   // edgeShade, edgeShadeShape, edgeShadeFold
// docs/physical-tube-model.py source(x, R, gap, n): the screen offset seen at apparent offset x
const source = (x: number, R: number, g: number, n: number): number => {
  const al = Math.asin(x / R), th = al - Math.asin(Math.sin(al) / n), z = Math.sqrt(R * R - x * x), sa = n * Math.sin(th);
  return Math.abs(sa) >= 1 ? NaN : x - z * Math.tan(th) - g * Math.tan(Math.asin(sa));
};
// The perceptual profile by docs/physical-tube-model.py's trigonometry and astra-model.md's formulas (not render.ts's
// algebra and fixed-step solvers): fold and TIR onset by sampling, inverses by bisection in x, Fresnel from the angles,
// the gamma inverse by Math.pow. Per tube: the rays of the same midpoint grid (8192 on 0 < x < R); per (rows, strength,
// shape, cover) the code factor F per row distance j.
const fres = (n1: number, i: number, n2: number, t: number): [number, number] => {
  const a = (n1 * Math.cos(i) - n2 * Math.cos(t)) / (n1 * Math.cos(i) + n2 * Math.cos(t)), b = (n2 * Math.cos(i) - n1 * Math.cos(t)) / (n2 * Math.cos(i) + n1 * Math.cos(t));
  return [a * a, b * b];
};
const T2 = (x: number, R: number): number => {
  const al = Math.asin(x / R), be = Math.asin(Math.sin(al) / ROD_N), th = al - be, sa = ROD_N * Math.sin(th);
  if (Math.abs(sa) >= 1) return 0;
  const [cs, cp] = fres(1, al, ROD_N, be), [bs_, bp] = fres(ROD_N, th, 1, Math.asin(sa));
  return 0.5 * ((1 - cs) * (1 - bs_) ** 2 + (1 - cp) * (1 - bp) ** 2);
};
const NRAYS = 8192;
const rodOf = (mm: number) => {
  const R = mm / 2; let xF = 0, dF = -1, xT = 0;
  for (let i = 1; i < 200000; i++) { const x = R * i / 200000, d = source(x, R, ROD_GAP_MM, ROD_N); if (d === d) xT = x; if (d > dF) { dF = d; xF = x; } }
  { let lo = xT, hi = Math.min(R, xT + R / 200000); for (let i = 0; i < 80; i++) { const m = (lo + hi) / 2; if (source(m, R, ROD_GAP_MM, ROD_N) === source(m, R, ROD_GAP_MM, ROD_N)) lo = m; else hi = m; } xT = lo; }
  const xOf = (d: number): number => { let lo = 0, hi = xF; for (let i = 0; i < 80; i++) { const m = (lo + hi) / 2; if (source(m, R, ROD_GAP_MM, ROD_N) < d) lo = m; else hi = m; } return (lo + hi) / 2; };
  const t0 = T2(0, R), rx = new Float64Array(NRAYS), rd = new Float64Array(NRAYS), rt = new Float64Array(NRAYS);
  for (let i = 0; i < NRAYS; i++) { const x = (i + 0.5) * R / NRAYS; rx[i] = x; rd[i] = source(x, R, ROD_GAP_MM, ROD_N); rt[i] = T2(x, R) / t0; }
  const cut = (f: number) => { const xC = xF + f * (xT - xF), dP = Math.max(0, source(xC, R, ROD_GAP_MM, ROD_N)); return { xC, dP, xE: dP > 0 ? xOf(dP) : 0 }; };
  const target = (x: number, s: number, q: number, xE: number): number => { const Le = 100 * (1 - s), Lc = 100 - 12 * s; return Lc - (Lc - Le) * (xE > 0 ? Math.min(1, x / xE) : 1) ** q; };
  const Ylum = (L: number): number => L > 8 ? ((L + 16) / 116) ** 3 : L / (24389 / 27);
  const memo = new Map<string, { F: number[]; plateau: number }>();
  // the code factor of row distance j (in rows, o: 0.5 for an even span) for a tube of `span` panel rows
  const factors = (span: number, s: number, q: number, f: number) => {
    const key = `${span}:${s}:${q}:${f}`; let e = memo.get(key);
    if (!e) {
      const o = span % 2 === 0 ? 0.5 : 0, half = span / 2 * PANEL_MM, { dP, xE } = cut(f);
      const plateau = Math.min(Math.floor((span + 1) / 2), Math.max(0, Math.floor(dP / PANEL_MM - o + 1)));
      const num = new Array(plateau + 1).fill(0), den = new Array(plateau + 1).fill(0);
      for (let i = 0; i < NRAYS; i++) {   // rays off the drawn tube or past TIR count nowhere; rows from the plateau on pool
        const d = rd[i]; if (d !== d) continue;
        const ad = Math.abs(d); if (ad >= half) continue;
        const j = Math.min(plateau, Math.floor(ad / PANEL_MM - o + 0.5));
        const Y = Ylum(target(rx[i], s, q, xE)); num[j] += rt[i] * Y; den[j] += rt[i] * rt[i];
      }
      const solve = (j: number, empty: number): number => den[j] > 0 ? Math.max(1 - s, Math.min(1, (num[j] / den[j]) ** (1 / 2.2))) : empty;
      const F: number[] = []; F[plateau] = solve(plateau, 1 - s);
      for (let j = 0; j < plateau; j++) F[j] = solve(j, F[plateau]);
      e = { F, plateau }; memo.set(key, e);
    }
    return e;
  };
  return { R, xF, dF, xT, cut, factors, target, Ylum, xOf };
};
const rodModel = TUBE_ROD_MM.map(rodOf);
if (BOARD_TAG === 'lcd316@320w8-8') {   // the profile on the 8 mm rod at the recommended look, and on every rod size at three covers
  const m = rodModel[0], s = 0.7, q = 1.5, f = Math.fround(0.4), c = m.cut(f), e = m.factors(72, s, q, f);
  console.log(`  rod 8 mm, s ${s} q ${q} fold 0.4: fold x ${m.xF.toFixed(4)} d ${m.dF.toFixed(4)}; TIR onset ${m.xT.toFixed(4)}; x_c ${c.xC.toFixed(4)} d_p ${c.dP.toFixed(4)} x_e ${c.xE.toFixed(4)}; plateau from row distance ${e.plateau}`);
  const Ks = (F: number[]): string => F.map((v) => Math.floor(256 * v + 0.5)).join(' ');
  console.log(`    K per row distance j (rows 35 - j and 36 + j; the last: the pooled plateau, j >= ${e.plateau}):`, Ks(e.F));
  console.log(`    s 0.9 (same rod, shape, cover): K ${Ks(m.factors(72, Math.fround(0.9), q, f).F)}`);
  console.log('    x mm   target L*   predicted L* (quantised rows)');
  for (const x of [0, 1, 2, 2.5, 2.7, 3.48, 3.68, 3.8, 3.9, 3.96]) {
    const d = Math.abs(source(Math.max(x, 1e-9), m.R, ROD_GAP_MM, ROD_N)), j = Math.floor(d / PANEL_MM - 0.5 + 0.5);
    const K = Math.floor(256 * e.F[Math.min(j, e.plateau)] + 0.5);
    const Y = T2(x, m.R) / T2(0, m.R) * (K / 256) ** 2.2, L = Y > 216 / 24389 ? 116 * Math.cbrt(Y) - 16 : Y * 24389 / 27;
    console.log(`    ${x.toFixed(2)}   ${m.target(x, s, q, c.xE).toFixed(1).padStart(5)}       ${L.toFixed(1).padStart(5)}`);
  }
  for (const mm of [3, 6, 8, 10]) {
    const r = rodOf(mm);
    for (const fo of [0, 0.4, 0.8]) {
      const cc = r.cut(Math.fround(fo)), span = Math.round(mm * 0.75 / PANEL_MM), ee = r.factors(span, 0.7, 1.5, Math.fround(fo));
      console.log(`  rod ${mm} mm fold ${fo}: d_fold ${r.dF.toFixed(4)} d_p ${cc.dP.toFixed(4)} x_in(d_p) ${cc.xE.toFixed(4)}; ${span}-row tube, s 0.7 q 1.5: K ${ee.F.map((v) => Math.floor(256 * v + 0.5)).join(' ')} (the last: plateau)`);
    }
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
  for (const [k, pw, fo] of SHADES) rows.forEach((r, i) => {   // pw: the shape
    const q = { ...ps[i], edgeShade: k, edgeShadeShape: pw, edgeShadeFold: fo }, T = edgeShadeRows(i, r.y, r.H, q)!;
    const p0 = bs(r.y), p1 = bs(r.y + r.H), c = (p0 + p1) / 2, o = (p1 - p0) % 2 === 0 ? 0.5 : 0;
    const e = rodModel[i].factors(p1 - p0, Math.fround(k), pw, Math.fround(fo));
    const ideal = (n: number): number => { const j = Math.floor(Math.abs(n + 0.5 - c) - o + 0.5); return 256 * (1 - e.F[Math.min(j, e.plateau)]); };
    for (let n = p0; n < p1; n++) {
      const y = Math.floor(n * PANEL_H / PANEL_ROWS), g = [...Array(bs(y + 1) - bs(y))].map((_, j) => ideal(bs(y) + j));
      const t = T[y - r.y], mean = g.reduce((s, v) => s + v, 0) / g.length;   // the covered panel rows' mean, not just its range
      if (Math.abs(t - mean) > 1) { err(`edge shade ${k}/${pw}/${fo} tube ${i} panel row ${n}: ${t}, ideal mean ${mean.toFixed(1)} of ${g.map((v) => v.toFixed(1))}`); return; }
    }
    shadeRowsChecked += p1 - p0;
  });
}
console.log(`${fails ? 'FAIL' : 'ok  '} ${BOARD_TAG}: ${cases.length} layouts, edge shade ${shadeRowsChecked} panel rows${fails ? `, ${fails} failures` : ''}`);
process.exit(fails ? 1 : 0);
