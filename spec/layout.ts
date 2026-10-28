// Liquid Watch — single source of truth for panel layout (TS mirror of spec/layout.h).
// KEEP IN SYNC with spec/layout.h. Landscape, origin top-left.
// The board (and the LCD's render height) is picked once at start-up, because modules size their buffers from
// these constants at import: browser `?board=lcd316&res=320` (remembered in localStorage), node tools
// LW_BOARD / LW_RES. Default: the AMOLED. No live switching — the sim reloads with the new choice.

export type Board = 'amoled191' | 'lcd316';
export const BOARDS: readonly Board[] = ['amoled191', 'lcd316'];
export const LCD_RES: readonly number[] = [240, 256, 288, 320];   // render heights the LCD build takes (RENDER_H)

const STORE_KEY = 'liquid-watch.board';
function pick(): { board: Board; res: number } {
  const g = globalThis as any;
  let board: string | null | undefined, res: string | null | undefined;
  if (g.location?.search !== undefined) {
    const u = new URLSearchParams(g.location.search);
    board = u.get('board'); res = u.get('res');
    if (!board) { try { const s = JSON.parse(g.localStorage?.getItem(STORE_KEY) ?? 'null'); board = s?.board; res ??= s?.res && String(s.res); } catch { /* none stored */ } }
  } else { board = g.process?.env?.LW_BOARD; res = g.process?.env?.LW_RES; }
  if (board && !(BOARDS as readonly string[]).includes(board)) { console.warn(`board ${board}: unknown, using amoled191`); board = undefined; }
  const b = (board || 'amoled191') as Board;
  let r = b === 'lcd316' ? Number(res || 320) : 240;
  if (b === 'lcd316' && !LCD_RES.includes(r)) { console.warn(`res ${res}: not one of ${LCD_RES.join(' / ')}, using 320`); r = 320; }
  return { board: b, res: r };
}
const chosen = pick();
export const BOARD: Board = chosen.board;
/** Reload the sim on another board / render height (the page's other URL parameters are kept). */
export function switchBoard(board: Board, res = 320): void {
  const g = globalThis as any;
  g.localStorage?.setItem(STORE_KEY, JSON.stringify({ board, res }));
  const u = new URL(g.location.href);
  u.searchParams.set('board', board);
  if (board === 'lcd316') u.searchParams.set('res', String(res)); else u.searchParams.delete('res');
  g.location.href = u.toString();
}
if ((globalThis as any).location?.search !== undefined) (globalThis as any).localStorage?.setItem(STORE_KEY, JSON.stringify(chosen));

export const DESIGN_H = 240;               // canvas rows the params / presets are tuned on
export const DESIGN_TUBE_HEIGHT_MAX = 80;  // largest tubeHeight a preset may ask for, design px

export const LCD_PANEL_W = 820, LCD_PANEL_H = 320;
export const PANEL_W = BOARD === 'lcd316' ? chosen.res * LCD_PANEL_W / LCD_PANEL_H : 536;
export const PANEL_H = BOARD === 'lcd316' ? chosen.res : 240;
/** Canvas px per design px (1 on the AMOLED): params.ts boardParams scales every px param by it. */
export const PX_SCALE = PANEL_H / DESIGN_H;
/** Short name of the canvas for labels: `amoled191`, `lcd316@320`. */
export const BOARD_TAG = BOARD === 'lcd316' ? `lcd316@${PANEL_H}` : BOARD;

export const TUBE_LENGTH_PX = PANEL_W; // full width; leather may mask the outer ~10px
// Strip buffer rows: the largest preset tube at this scale. Defaults below; runtime values come from params
// tubeHeight / hoursY / minutesY (design px, scaled).
export const TUBE_HEIGHT_MAX = Math.floor((DESIGN_TUBE_HEIGHT_MAX * PANEL_H + DESIGN_H - 1) / DESIGN_H);
export const TUBE_HEIGHT_PX = Math.floor(72 * PANEL_H / DESIGN_H);  // ≈ 6 mm on the AMOLED at 0.083 mm/px
export const HOURS_TUBE_Y = 0;                          // along the top edge
export const MINUTES_TUBE_Y = PANEL_H - TUBE_HEIGHT_PX; // along the bottom edge
export const BRIDGE_Y0 = TUBE_HEIGHT_PX;                // bridge zone between the tubes must stay pure black
export const BRIDGE_Y1 = MINUTES_TUBE_Y;

export const LIQUID_RGB888 = 0x5dcaa5;
export const LIQUID_HI_RGB888 = 0x9fe1cb;
export const BG_RGB888 = 0x000000;

/** mm per design px (the AMOLED's pitch): params are derived / migrated with it (material layer, legacyTraceDrain). */
export const DESIGN_MM_PER_PX = 0.083;
/** mm per canvas px for the physical meniscus: a scaled bore stays the same bore in mm (see layout.h). */
export const MM_PER_PX = DESIGN_MM_PER_PX / PX_SCALE;

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
