// Liquid Watch — single source of truth for panel layout (TS mirror of spec/layout.h).
// KEEP IN SYNC with spec/layout.h. Landscape, origin top-left.
// The board, the tube count, the LCD's render height and its tube widths are picked once at start-up, because modules
// size their buffers from these constants at import: browser `?board=lcd316&res=320f&tubes=3` (remembered in
// localStorage), node tools LW_BOARD / LW_RES / LW_TUBES. Default: the AMOLED, two tubes. No live switching — the sim
// reloads with the new choice.
// Tubes, top to bottom: hours, minutes (two-tube face: hours top, minutes bottom); with TUBE_COUNT 3 (layout.h) a seconds
// tube takes the bottom slot and minutes moves to the middle (render.ts faceLayout). The seconds tube draws with the
// minutes tube's ticks and digits (0..60).
// LCD res tag = rows + tube widths (layout.h LCD_FILL_H / LCD_FILL_M / LCD_FILL_S): no suffix all narrow (px params at
// the AMOLED's physical size), `f` all wide (scaled with the canvas height), else `f` + the wide tubes' letters in
// h / m / s order: `320fh` hours wide, `320fm` minutes wide; three tubes add `fs`, `fhm`, `fhs`, `fms`. A tube in mm
// (layout.h LCD_MM_H / _M / _S, 3 to 10, one decimal: the presets' 6 mm tube drawn that wide, 6 = narrow, wide ≈ 8.8):
// `w` + one width per tube, `-` between, `f` wide: `320w10-8-6`, `320wf-7-5` (only when a tube is neither narrow nor
// wide).

export type Board = 'amoled191' | 'lcd316';
export const BOARDS: readonly Board[] = ['amoled191', 'lcd316'];
export const LCD_RES: readonly number[] = [240, 256, 288, 320];   // render heights the LCD build takes (RENDER_H)
export const TUBE_COUNTS: readonly number[] = [2, 3];
/** Tube letters in face order (res tags, labels): hours, minutes, seconds. */
export const TUBE_LETTERS = 'hms';
/** An LCD tube width: 'f' = wide (layout.h LCD_FILL_x), else mm (LCD_MM_x; 6 = narrow, the AMOLED's physical size). */
export type TubeWidth = 'f' | number;
/** LCD tube widths, one per tube (hours, minutes[, seconds]). */
export type TubeWidths = readonly TubeWidth[];
export const NARROW_MM = 6;
/** The mm widths a tube takes (layout.h LCD_MM_x): 3 to 10, one decimal. */
export const TUBE_MM_MIN = 3, TUBE_MM_MAX = 10;
const isMm = (w: TubeWidth): w is number => w !== 'f';

/** LCD res tag (`320`, `320f`, `320fh`, `320fm`, three tubes also `320fs`, `320fhm`, …, a tube in mm `320w10-8-6`) from
 *  rows and tube widths. */
export function resTag(rows: number, widths: TubeWidths): string {
  if (widths.some((w) => isMm(w) && w !== NARROW_MM)) return `${rows}w${widths.map(String).join('-')}`;
  const n = widths.filter((w) => w === 'f').length;
  return `${rows}${n === 0 ? '' : n === widths.length ? 'f' : 'f' + widths.map((w, i) => w === 'f' ? TUBE_LETTERS[i] : '').join('')}`;
}
/** Rows and tube widths of an LCD res tag for a face of `tubes` tubes; null if it is not one (one name per build: the
 *  letters of all tubes are spelled `f`, an mm tag has a tube in mm other than 6). */
export function parseRes(tag: string, tubes = 2): { rows: number; widths: TubeWidths } | null {
  const m = /^(\d+)(?:(f[hms]*)|w((?:f|\d+(?:\.\d)?)(?:-(?:f|\d+(?:\.\d)?))*))?$/.exec(tag);
  if (!m || !LCD_RES.includes(Number(m[1]))) return null;
  const rows = Number(m[1]);
  let widths: TubeWidth[];
  if (m[3] !== undefined) {
    widths = m[3].split('-').map((t) => t === 'f' ? 'f' : Number(t));
    if (widths.length !== tubes || widths.some((w) => isMm(w) && (w < TUBE_MM_MIN || w > TUBE_MM_MAX))) return null;
  } else {
    const sub = m[2]?.slice(1);
    widths = sub === undefined ? Array(tubes).fill(NARROW_MM) : sub === '' ? Array(tubes).fill('f')
      : [...TUBE_LETTERS.slice(0, tubes)].map((c) => sub.includes(c) ? 'f' : NARROW_MM);
  }
  if (resTag(rows, widths) !== tag) return null;   // unknown, repeated, out-of-order or all letters; 6-only mm, `9.0`
  return { rows, widths };
}
/** A tube width in words: `narrow`, `wide`, `9.5 mm`. */
export function widthWords(w: TubeWidth): string { return w === 'f' ? 'wide' : w === NARROW_MM ? 'narrow' : `${w} mm`; }

const STORE_KEY = 'liquid-watch.board';
const browser = (globalThis as any).location?.search !== undefined;
/** The choice the sim remembers ({ board, res, tubes }: res = the last LCD res tag, kept while on the AMOLED). */
function stored(): { board?: string; res?: string; tubes?: number } | null {
  try {
    const s = JSON.parse((globalThis as any).localStorage?.getItem(STORE_KEY) ?? 'null');
    return s && { board: s.board, res: s.res === undefined ? undefined : String(s.res), tubes: s.tubes === undefined ? undefined : Number(s.tubes) };
  } catch { return null; }
}
function pick(): { board: Board; rows: number; widths: TubeWidths; tubes: number } {
  const g = globalThis as any;
  let board: string | null | undefined, res: string | null | undefined, tubesArg: string | number | null | undefined;
  if (browser) {
    const u = new URLSearchParams(g.location.search);
    board = u.get('board'); res = u.get('res'); tubesArg = u.get('tubes');
    if (!board) { const s = stored(); board = s?.board; res ??= s?.res; tubesArg ??= s?.tubes; }
  } else { board = g.process?.env?.LW_BOARD; res = g.process?.env?.LW_RES; tubesArg = g.process?.env?.LW_TUBES; }
  if (board && !(BOARDS as readonly string[]).includes(board)) { console.warn(`board ${board}: unknown, using amoled191`); board = undefined; }
  let tubes = tubesArg === null || tubesArg === undefined || tubesArg === '' ? 2 : Number(tubesArg);
  if (!TUBE_COUNTS.includes(tubes)) { console.warn(`tubes ${tubesArg}: not one of ${TUBE_COUNTS.join(' / ')}, using 2`); tubes = 2; }
  const b = (board || 'amoled191') as Board;
  if (b !== 'lcd316') return { board: b, rows: 240, widths: Array(tubes).fill(NARROW_MM), tubes };
  const r = parseRes(res || '320', tubes);
  if (!r) console.warn(`res ${res}: not one of ${LCD_RES.join(' / ')} (+ f / f + wide tube letters ${TUBE_LETTERS.slice(0, tubes)} / w + ${tubes} widths in mm or f, - between) for ${tubes} tubes, using 320`);
  return { board: b, ...(r ?? { rows: 320, widths: Array(tubes).fill(NARROW_MM) }), tubes };
}
const chosen = pick();
export const BOARD: Board = chosen.board;
/** Tubes on the face (layout.h TUBE_COUNT): 2 = hours + minutes, 3 = + seconds. */
export const TUBE_COUNT = chosen.tubes;
/** The LCD res tag the sim's board controls start from: this page's on the LCD, else the last one used (a letter tag
 *  reads for any tube count, an mm tag for its own; the controls read the tubes they show). */
export const LAST_LCD_RES = chosen.board === 'lcd316' ? resTag(chosen.rows, chosen.widths)
  : TUBE_COUNTS.some((n) => parseRes(stored()?.res ?? '', n)) ? stored()!.res! : '320';
if (browser) (globalThis as any).localStorage?.setItem(STORE_KEY, JSON.stringify({ board: chosen.board, res: LAST_LCD_RES, tubes: chosen.tubes }));
/** Reload the sim on another board / LCD res tag (rows + tube widths, resTag) / tube count; the page's other URL
 *  parameters are kept. */
export function switchBoard(board: Board, res = '320', tubes = 2): void {
  const g = globalThis as any;
  g.localStorage?.setItem(STORE_KEY, JSON.stringify({ board, res, tubes }));
  const u = new URL(g.location.href);
  u.searchParams.set('board', board);
  if (board === 'lcd316') u.searchParams.set('res', res); else u.searchParams.delete('res');
  if (tubes !== 2) u.searchParams.set('tubes', String(tubes)); else u.searchParams.delete('tubes');
  g.location.href = u.toString();
}

export const DESIGN_H = 240;               // canvas rows the params / presets are tuned on
export const DESIGN_TUBE_HEIGHT_MAX = 80;  // largest tubeHeight a preset may ask for, design px

// Slider limits (PARAM_META reads them) that the firmware's fixed buffers are sized from. Values pushed past a
// slider over serial are capped and reported, never written past a buffer.
export const FIZZ_COUNT_MAX = 240;   // fizzCount: bubbles in a full tube
export const FIZZ_POOL = 2 * FIZZ_COUNT_MAX;   // bubbles per tube: full agitation (<= 1) doubles fizzCount
export const DIGIT_SCALE_MAX = 6;    // digitScaleX / Y (and Min): design px per em cell
export const DIGIT_SHADOW_OFFSET_MAX = 4;   // digitShadowOffset, design px
export const GLYPH_EM_W = 5;         // the nominal em of the sprite fonts, cells (same as the bitmap fonts: a scale means the same)
export const GLYPH_EM_H = 7;
export const MARK_CONTRAST_MAX = 120;   // markContrast

export const LCD_PANEL_W = 820, LCD_PANEL_H = 320;
export const PANEL_W = BOARD === 'lcd316' ? chosen.rows * LCD_PANEL_W / LCD_PANEL_H : 536;
export const PANEL_H = BOARD === 'lcd316' ? chosen.rows : 240;
/** LCD tube widths, one per tube ('f' wide, else mm); all narrow on the AMOLED. */
export const TUBE_WIDTHS: TubeWidths = chosen.widths;
/** The LCD's res tag (`320f`, …); '' on the AMOLED. */
export const RES_TAG = BOARD === 'lcd316' ? resTag(chosen.rows, chosen.widths) : '';
/** Canvas px per design px of tube i (0 = hours, 1 = minutes, 2 = seconds; 1 on the AMOLED): params.ts boardParams
 *  scales every px param by it. LCD narrow: at the AMOLED's physical size (0.083 / 0.0912 mm per panel px, the float32
 *  of layout.h); wide: with the canvas height; mm: narrow x mm / 6 (layout.h PX_SCALE_MM, float32). */
const PX_SCALE_NARROW = Math.fround(830 * PANEL_H / (912 * LCD_PANEL_H));
export const TUBE_PX_SCALE: readonly number[] = BOARD === 'lcd316'
  ? chosen.widths.map((w) => w === 'f' ? PANEL_H / DESIGN_H : w === NARROW_MM ? PX_SCALE_NARROW
    : Math.fround(PX_SCALE_NARROW * Math.fround(Math.fround(w) / 6)))
  : Array(TUBE_COUNT).fill(1);
/** The larger tube scale: what buffers are sized for. */
export const PX_SCALE_MAX = Math.max(...TUBE_PX_SCALE);
/** The liquid's px scale: the fizz is the liquid's (its size and rise speed do not depend on the bore), so every tube
 *  draws it at the widest tube's scale (params.ts FIZZ_PX_KEYS); a narrower tube holds fewer bubbles (its volume, bore²). */
export const PX_SCALE_FIZZ = PX_SCALE_MAX;
/** Short name of the canvas for labels: `amoled191`, `lcd316@320`, `lcd316@320f`, `lcd316@320fh` (see resTag); a
 *  three-tube face adds `+t3` (`amoled191+t3`, `lcd316@320fh+t3`). */
export const BOARD_TAG = (BOARD === 'lcd316' ? `lcd316@${RES_TAG}` : BOARD) + (TUBE_COUNT === 3 ? '+t3' : '');
/** A board tag (`v`) split into board, LCD res tag and tube count; null if it is not one. */
export function parseBoardTag(tag: string): { board: Board; res: string; tubes: number } | null {
  const m = /^(amoled191|lcd316)(?:@([0-9a-z.-]+))?(?:\+t(\d+))?$/.exec(tag);
  if (!m) return null;
  const tubes = m[3] === undefined ? 2 : Number(m[3]);
  if (!TUBE_COUNTS.includes(tubes) || (m[1] === 'lcd316') !== (m[2] !== undefined)) return null;
  if (m[2] !== undefined && !parseRes(m[2], tubes)) return null;
  return { board: m[1] as Board, res: m[2] ?? '', tubes };
}

export const TUBE_LENGTH_PX = PANEL_W; // full width; leather may mask the outer ~10px
// Strip buffer rows: the largest preset tube at this scale. Defaults below; runtime values come from params
// tubeHeight / hoursY / minutesY (design px, scaled).
export const TUBE_HEIGHT_MAX = Math.floor(Math.fround(Math.fround(DESIGN_TUBE_HEIGHT_MAX * Math.fround(PX_SCALE_MAX)) + Math.fround(0.999)));
/** Rows a tube of px scale k may take on a three-tube face (params.ts boardParams caps tubeHeight): a third of the
 *  canvas at equal widths, else its share by scale, so the three fit (layout.h TUBE3_HEIGHT_AT, float32). */
export function tube3HeightAt(k: number): number {
  const f = Math.fround, [h, m, s] = TUBE_PX_SCALE;
  if (TUBE_PX_SCALE.every((x) => x === h)) return Math.floor(PANEL_H / 3);
  return Math.trunc(f(f(PANEL_H * f(k)) / f(f(h + m) + s)));
}
export const TUBE_HEIGHT_PX = Math.floor(Math.fround(72 * Math.fround(PX_SCALE_MAX)));  // ≈ 6 mm at 0.083 mm per design px (the wider tube)
export const HOURS_TUBE_Y = 0;                          // along the top edge
export const MINUTES_TUBE_Y = PANEL_H - TUBE_HEIGHT_PX; // along the bottom edge
export const BRIDGE_Y0 = TUBE_HEIGHT_PX;                // bridge zone between the tubes must stay pure black
export const BRIDGE_Y1 = MINUTES_TUBE_Y;

export const LIQUID_RGB888 = 0x5dcaa5;
export const LIQUID_HI_RGB888 = 0x9fe1cb;
export const BG_RGB888 = 0x000000;

/** mm per design px (the AMOLED's pitch): params are derived / migrated with it (material layer, legacyTraceDrain). */
export const DESIGN_MM_PER_PX = 0.083;
/** mm per canvas px for the physical meniscus of a tube at px scale k: a scaled bore stays the same bore in mm (layout.h). */
export const mmPerPxAt = (k: number): number => DESIGN_MM_PER_PX / k;

export function rgb565(r: number, g: number, b: number): number {
  return ((r & 0xf8) << 8) | ((g & 0xfc) << 3) | (b >> 3);
}
export function rgb888to565(rgb: number): number {
  return rgb565((rgb >> 16) & 0xff, (rgb >> 8) & 0xff, rgb & 0xff);
}
/** Expand RGB565 back to 8-bit channels exactly as the panel will show them. */
export function rgb565to888(c: number): [number, number, number] {
  const r5 = (c >> 11) & 0x1f, g6 = (c >> 5) & 0x3f, b5 = c & 0x1f;
  return [(r5 << 3) | (r5 >> 2), (g6 << 2) | (g6 >> 4), (b5 << 3) | (b5 >> 2)];
}

// ---- IMU axis mapping (QMI8658, measured 2026-08-20 with USB_LEFT=1) ----
export const IMU_AXIS_ALONG_TUBE = 1;   // 0=x 1=y 2=z
export const IMU_ALONG_TUBE_SIGN = -1;  // tilt_along = sign * ay → positive = right end down
export const IMU_AXIS_ACROSS_TUBE = 0;
export const IMU_ACROSS_TUBE_SIGN = -1; // positive = top (far) edge up
