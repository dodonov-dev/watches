// Liquid Watch — single source of truth for panel layout (TS mirror of spec/layout.h).
// KEEP IN SYNC with spec/layout.h. Landscape, origin top-left.
// The board, the LCD's render height and its tube widths are picked once at start-up, because modules size their
// buffers from these constants at import: browser `?board=lcd316&res=320f` (remembered in localStorage), node tools
// LW_BOARD / LW_RES. Default: the AMOLED. No live switching — the sim reloads with the new choice.
// LCD res tag = rows + tube widths (layout.h LCD_FILL_H / LCD_FILL_M): `320` both narrow (px params at the AMOLED's
// physical size), `320f` both wide (scaled with the canvas height), `320fh` hours wide, `320fm` minutes wide.

export type Board = 'amoled191' | 'lcd316';
export const BOARDS: readonly Board[] = ['amoled191', 'lcd316'];
export const LCD_RES: readonly number[] = [240, 256, 288, 320];   // render heights the LCD build takes (RENDER_H)
/** Tube widths of an LCD build, [hours, minutes]: true = wide (layout.h LCD_FILL_H / LCD_FILL_M). */
export type TubeWide = readonly [boolean, boolean];

/** LCD res tag (`320`, `320f`, `320fh`, `320fm`) from rows and tube widths. */
export function resTag(rows: number, wide: TubeWide): string {
  return `${rows}${wide[0] && wide[1] ? 'f' : wide[0] ? 'fh' : wide[1] ? 'fm' : ''}`;
}
/** Rows and tube widths of an LCD res tag; null if it is not one. */
export function parseRes(tag: string): { rows: number; wide: TubeWide } | null {
  const m = /^(\d+)(f|fh|fm)?$/.exec(tag);
  if (!m || !LCD_RES.includes(Number(m[1]))) return null;
  return { rows: Number(m[1]), wide: [m[2] === 'f' || m[2] === 'fh', m[2] === 'f' || m[2] === 'fm'] };
}

const STORE_KEY = 'liquid-watch.board';
const browser = (globalThis as any).location?.search !== undefined;
/** The choice the sim remembers ({ board, res }: res = the last LCD res tag, kept while on the AMOLED). */
function stored(): { board?: string; res?: string } | null {
  try { const s = JSON.parse((globalThis as any).localStorage?.getItem(STORE_KEY) ?? 'null'); return s && { board: s.board, res: s.res === undefined ? undefined : String(s.res) }; } catch { return null; }
}
function pick(): { board: Board; rows: number; wide: TubeWide } {
  const g = globalThis as any;
  let board: string | null | undefined, res: string | null | undefined;
  if (browser) {
    const u = new URLSearchParams(g.location.search);
    board = u.get('board'); res = u.get('res');
    if (!board) { const s = stored(); board = s?.board; res ??= s?.res; }
  } else { board = g.process?.env?.LW_BOARD; res = g.process?.env?.LW_RES; }
  if (board && !(BOARDS as readonly string[]).includes(board)) { console.warn(`board ${board}: unknown, using amoled191`); board = undefined; }
  const b = (board || 'amoled191') as Board;
  if (b !== 'lcd316') return { board: b, rows: 240, wide: [false, false] };
  const r = parseRes(res || '320');
  if (!r) console.warn(`res ${res}: not one of ${LCD_RES.join(' / ')} (+ f / fh / fm), using 320`);
  return { board: b, ...(r ?? { rows: 320, wide: [false, false] as TubeWide }) };
}
const chosen = pick();
export const BOARD: Board = chosen.board;
/** The LCD res tag the sim's board controls start from: this page's on the LCD, else the last one used. */
export const LAST_LCD_RES = chosen.board === 'lcd316' ? resTag(chosen.rows, chosen.wide) : parseRes(stored()?.res ?? '') ? stored()!.res! : '320';
if (browser) (globalThis as any).localStorage?.setItem(STORE_KEY, JSON.stringify({ board: chosen.board, res: LAST_LCD_RES }));
/** Reload the sim on another board / LCD res tag (rows + tube widths, resTag); the page's other URL parameters are kept. */
export function switchBoard(board: Board, res = '320'): void {
  const g = globalThis as any;
  g.localStorage?.setItem(STORE_KEY, JSON.stringify({ board, res }));
  const u = new URL(g.location.href);
  u.searchParams.set('board', board);
  if (board === 'lcd316') u.searchParams.set('res', res); else u.searchParams.delete('res');
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
/** LCD tube widths [hours, minutes] (true = wide); both false on the AMOLED. */
export const TUBE_WIDE: TubeWide = chosen.wide;
/** The LCD's res tag (`320f`, …); '' on the AMOLED. */
export const RES_TAG = BOARD === 'lcd316' ? resTag(chosen.rows, chosen.wide) : '';
/** Canvas px per design px of tube i (0 = hours; 1 on the AMOLED): params.ts boardParams scales every px param by it.
 *  LCD narrow: at the AMOLED's physical size (0.083 / 0.0912 mm per panel px, the float32 of layout.h); wide: with the
 *  canvas height. */
export const TUBE_PX_SCALE: readonly [number, number] = BOARD === 'lcd316'
  ? [0, 1].map((i) => chosen.wide[i] ? PANEL_H / DESIGN_H : Math.fround(830 * PANEL_H / (912 * LCD_PANEL_H))) as [number, number]
  : [1, 1];
/** The larger tube scale: what buffers are sized for. */
export const PX_SCALE_MAX = Math.max(TUBE_PX_SCALE[0], TUBE_PX_SCALE[1]);
/** The liquid's px scale: the fizz is the liquid's (its size and rise speed do not depend on the bore), so both tubes draw
 *  it at the wider tube's scale (params.ts FIZZ_PX_KEYS); a narrower tube holds fewer bubbles (its volume, bore²). */
export const PX_SCALE_FIZZ = PX_SCALE_MAX;
/** Short name of the canvas for labels: `amoled191`, `lcd316@320`, `lcd316@320f`, `lcd316@320fh` (see resTag). */
export const BOARD_TAG = BOARD === 'lcd316' ? `lcd316@${RES_TAG}` : BOARD;

export const TUBE_LENGTH_PX = PANEL_W; // full width; leather may mask the outer ~10px
// Strip buffer rows: the largest preset tube at this scale. Defaults below; runtime values come from params
// tubeHeight / hoursY / minutesY (design px, scaled).
export const TUBE_HEIGHT_MAX = Math.floor(Math.fround(Math.fround(DESIGN_TUBE_HEIGHT_MAX * Math.fround(PX_SCALE_MAX)) + Math.fround(0.999)));
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
