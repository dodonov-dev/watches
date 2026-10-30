// Renderer: draws into an RGB565 framebuffer (Uint16Array, PANEL_W*PANEL_H) with only
// operations that port 1:1 to the MCU: per-row horizontal spans, a per-row colour LUT,
// a few filled ellipses/dots. Mirrored 1:1 by firmware/src/render.cpp.
import {
  PANEL_W, PANEL_H, TUBE_LENGTH_PX, TUBE_HEIGHT_MAX,
  rgb565, rgb565to888, MM_PER_PX, PX_SCALE,
} from '@spec/layout';
import type { Params } from './params';
import { boreR, columnLen, contactLeads, filmEta, mirrored, FILM_ETA_MAX, FILM_FULL_PX_S, TRACE_FULL, type TubeState } from './physics';

export const fb = new Uint16Array(PANEL_W * PANEL_H);
const lensScratch = new Uint16Array(PANEL_W * TUBE_HEIGHT_MAX);

function hexToRgb(h: string): [number, number, number] {
  const v = parseInt(h.replace('#', ''), 16);
  return [(v >> 16) & 0xff, (v >> 8) & 0xff, v & 0xff];
}
function mix(a: [number, number, number], b: [number, number, number], t: number): [number, number, number] {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}
function scale(a: [number, number, number], k: number): [number, number, number] {
  return [a[0] * k, a[1] * k, a[2] * k];
}
function q(c: [number, number, number]): number {
  return rgb565(Math.round(Math.max(0, Math.min(255, c[0]))), Math.round(Math.max(0, Math.min(255, c[1]))),
    Math.round(Math.max(0, Math.min(255, c[2]))));
}
/** Blend two RGB565 colours (t in 0..1) — used only for edge anti-aliasing (edgeSoft). */
function blend565(a: number, b: number, t: number): number {
  const A = rgb565to888(a), B = rgb565to888(b);
  return q(mix(A, B, t));
}

export interface TubeLayout { H: number; yH: number; yM: number; }
/** Tube geometry from params, clamped to the panel and the strip buffer. */
export function tubeLayout(p: Params): TubeLayout {
  const H = Math.max(4, Math.min(TUBE_HEIGHT_MAX, Math.round(p.tubeHeight)));
  const y = (v: number) => Math.max(0, Math.min(PANEL_H - H, Math.round(v)));
  return { H, yH: y(p.hoursY), yM: y(p.minutesY) };
}

export interface Palette {
  rows: Uint16Array;     // H colours: body shade per row incl. highlight band
  tubeBackRows: Uint16Array; // tube-back colour with glass shading per row
  body: number; tubeBack: number; bubbleRim: number; bubbleIn: Uint16Array;
  bubbleRimRows: Uint16Array; // H: fizz ring colour per row, dimmed by the cylinder's light (the scalar rim stays for the spirit bubble / pinpoint)
  dryT: Float32Array;    // H: what an empty tube transmits of the back per row (0 inside the glass wall band); fades rear marks behind air
}

/** Ambient-light desaturation (params.ambientLight): a colour brighter than the diffuse body luma
 *  `bodyL` reads as a reflection of the (neutral) room light, so it loses the liquid's chroma —
 *  grey of the same luma — instead of the liquid glowing brighter in its own colour. Ramps from no
 *  change at the body luma to full desaturation at twice it. Callers scale `amt` by the liquid's
 *  opacity: bright areas of a transparent liquid are mostly light transmitted through it (tinted),
 *  so full desaturation would leave it colourless. */
function ambientize(c: [number, number, number], bodyL: number, amt: number): [number, number, number] {
  if (amt <= 0) return c;
  const l = luma(c);
  const k = amt * Math.min(1, Math.max(0, (l - bodyL) / bodyL));
  return k > 0 ? mix(c, [l, l, l], k) : c;
}
/** Diffuse body luma: the ambientize reference. */
function ambientBodyL(p: Params): number {
  return Math.max(1, luma(scale(hexToRgb(p.liquid), p.brightness * p.liquidBright)));
}
/** Effective ambientize amount: the knob, scaled down by transparency (see ambientize). */
function ambientAmt(p: Params): number {
  return p.ambientLight * (1 - Math.max(0, Math.min(1, p.liquidTransparency)));
}

/** Top row of the highlight band for highlight angle `lightDeg` (TubeState.light):
 *  the cylinder surface point whose normal makes that angle with the screen normal. */
export function highlightTop(p: Params, H: number, lightDeg: number): number {
  const yc = (H - 1) / 2;
  return Math.round(yc - yc * Math.sin((lightDeg * Math.PI) / 180) - (p.highlightH - 1) / 2);
}

/** Step 0: build the per-row colour LUT. Firmware rebuilds it when the light moves.
 *  Shading blends (lightPhys) a stylised top light (bright at 1/3, dark at the bottom) with a
 *  Lambert cylinder lit from direction 2*light in the cross-section (world-up when physical).
 *  The highlight band sits at `light` in both. The acrylic rod over the panel supplies the real specular. */
export function buildPalette(p: Params, lightDeg = 0): Palette {
  const body = hexToRgb(p.liquid), hi = hexToRgb(p.liquidHi), lo = hexToRgb(p.liquidLo);
  const br = p.brightness * p.liquidBright;   // tube back stays on the panel dimmer alone
  const H = tubeLayout(p).H, yc = (H - 1) / 2;
  const lightRad = (2 * lightDeg * Math.PI) / 180;
  /** Lambert weight 0..1 of row y under the physical light. */
  const lambert = (y: number): number => Math.max(0, Math.cos(Math.asin(Math.max(-1, Math.min(1, (yc - y) / yc))) - lightRad));
  const rows = new Uint16Array(H);
  const bubbleIn = new Uint16Array(H);
  const bubbleRimRows = new Uint16Array(H), rimC = hexToRgb(p.bubbleRim), rowL = new Float32Array(H);
  // The lit rim colour after the panel clip: bright presets push it past white, so the row shading is
  // applied to the clipped colour (otherwise it saturates away). Capped below white so the pinpoint reads.
  const rimLit = scale(rimC, br).map((v) => Math.min(255, v)) as [number, number, number];
  const tubeBackRows = new Uint16Array(H);
  const tubeBack = hexToRgb(p.tubeBack), tubeBack2 = hexToRgb(p.tubeBack2), ghi = hexToRgb(p.glassHi);
  const liquidHiScaled = scale(hi, br), glassHiScaled = scale(ghi, p.brightness);
  const rimTint = scale(hexToRgb(p.rimTint), p.brightness);
  const bodyL = ambientBodyL(p), ambAmt = ambientAmt(p);
  /** Glass wall shading weight 0..1 for a row: specular tent on the top wall, a faint band on the
   *  lower wall, brighter outermost rows. */
  const glassW = (y: number): number => {
    const t = y / (H - 1);
    // ambient: style = cylinder lit from above (brightest near 1/3, darkest near 2/3, lifting again at the bottom)
    const amb = 0.5 + 0.5 * Math.cos((t - 0.3) * Math.PI * 1.6);
    let w = p.glassBody * (amb + (lambert(y) - amb) * p.lightPhys);
    if (y >= hiTop && y < hiTop + p.highlightH)
      w += p.glassHiBright * Math.pow(1 - Math.abs((y - hiTop) / Math.max(1, p.highlightH - 1) - 0.5) * 2, p.highlightSharp);
    const d = (t - 0.82) / 0.07;
    w += p.glassReflect * Math.exp(-d * d);
    return Math.min(1, w);
  };
  const hiTop = highlightTop(p, H, lightDeg);
  // Wall band (from the physical renderer's cylinder trace): rows whose ray misses the bore pass
  // through wall only and never reach the back (`dryT` 0), ramping up over a few rows inside; the
  // liquid is near index-matched to the wall, so the wet side still shows through there. The
  // front surface reflects the room at grazing incidence: a neutral rim rising toward the
  // silhouette on both sides (`glassRim`). `glassWall` 0 keeps only a one-row rim.
  const wallU = 1 - 2 * Math.max(1, p.glassWall) / H;
  const glassEdge = scale(mix(ghi, [180, 190, 195], 0.72), p.brightness);
  const dryT = new Float32Array(H);
  const rimW = (u: number): number => p.glassRim * Math.pow(Math.max(0, (Math.abs(u) - wallU) / (1 - wallU)), 2.5);
  // Wall glow: light piped along the wall (internal paths the cylinder trace omits) lights the band
  // itself, a plateau with a short ramp starting just inside the band; the grazing rim adds on top.
  // Dry glass only, as far as the contents wet the wall (`wallWet`): a liquid frustrates the total
  // internal reflection that pipes the light (glass/liquid critical angle ~62° vs ~42° against air),
  // and, near index-matched, fills the band, so the column reads as wide as the tube; it takes the
  // grazing rim (a front-surface reflection) alone. A gas (wallWet 0) does neither: over its column
  // the glow stays and the band is the empty tube's — the contents are seen where the back would be
  // (dryT). In between, both blend by wallWet. At 1 neither step runs.
  const glowW = (u: number): number => p.glassWallGlow * Math.max(0, Math.min(1, 0.4 + 3 * (Math.abs(u) - wallU) / (1 - wallU)));
  const wallW = (u: number): number => { const g = glowW(u), r = rimW(u); return g + r - g * r; };
  const wallT = (u: number): number => p.glassWall <= 0 ? 1 : Math.abs(u) >= wallU ? 0 : 1 - Math.exp(-(wallU - Math.abs(u)) / 0.04);
  const wet = Math.max(0, Math.min(1, p.wallWet));
  for (let y = 0; y < H; y++) {
    const t = y / (H - 1);
    const gradient = Math.round(p.tubeBackGradient);
    const backMix = gradient === 1 ? t : gradient === 2 ? 1 - Math.abs(t * 2 - 1)
      : gradient === 3 ? Math.abs(t * 2 - 1) : 0;
    const back = mix(tubeBack, tubeBack2, backMix);
    const u = (y + 0.5 - H / 2) / (H / 2), rim = rimW(u), wall = wallW(u);
    const g = glowW(u) * (1 - wet), wetRim = g + rim - g * rim;   // over the contents: the glow they leave piped, the rim
    dryT[y] = wallT(u);
    // style shading: brightest around 1/3 from top, darkest at the bottom
    let c: [number, number, number];
    if (t < 0.33) c = mix(mix(body, lo, 0.25), body, t / 0.33);
    else c = mix(body, lo, ((t - 0.33) / 0.67) * p.shadeDepth);
    if (p.lightPhys > 0) c = mix(c, mix(lo, body, 1 - p.shadeDepth * (1 - lambert(y))), p.lightPhys);
    // Thin edge: the chord through the column shortens toward the walls, so less of the light is
    // absorbed there — the colour drifts to a grey of its own peak channel (Beer-Lambert, all
    // channels converging), strongest on the outermost rows.
    if (p.liquidThin > 0) {
      const chord = Math.sqrt(Math.max(0, 1 - u * u)), m = Math.max(c[0], c[1], c[2]);
      c = mix(c, [m, m, m], p.liquidThin * (1 - chord) * (1 - chord));
    }
    rowL[y] = luma(c);   // the light inside the liquid at this row (before the backing, highlight and glass: they do not light a bubble)
    // A transparent liquid shows the tube back through it: blend the lit liquid toward the
    // (panel-dimmed) back. The highlight is a reflection off the liquid surface, so it goes on
    // after that (undiluted), and the glass wall over both.
    c = scale(c, br);
    c = mix(c, scale(back, p.brightness), p.liquidTransparency);
    // Side-lit rim (rimLight/rimTint): light entering through the side walls of a tinted liquid on a
    // dark ground, rising as u² toward the walls.
    if (p.rimLight > 0) {
      const rk = p.rimLight * u * u;
      c = [Math.min(255, c[0] + rk * rimTint[0]), Math.min(255, c[1] + rk * rimTint[1]), Math.min(255, c[2] + rk * rimTint[2])];
    }
    if (y >= hiTop && y < hiTop + p.highlightH) {
      const k = Math.pow(1 - Math.abs((y - hiTop) / Math.max(1, p.highlightH - 1) - 0.5) * 2, p.highlightSharp); // tent
      c = mix(c, liquidHiScaled, Math.min(1, (0.35 + 0.65 * k) * p.highlightBright));
    }
    const gw = glassW(y);
    const wetK = p.glassOverLiquid + (1 - p.glassOverLiquid) * p.liquidTransparency, glassWet = gw * wetK;
    // Empty tube: the back shows through only where the ray reaches it (wall band dark), the glass
    // body/specular over it, and the wall glow + grazing rim on top.
    const dryRow = mix(scale(mix(scale(back, dryT[y]), ghi, gw), p.brightness), glassEdge, wall);
    tubeBackRows[y] = q(dryRow);
    // Glass shading over the liquid: `glassOverLiquid` of the dry-side weight for an opaque liquid,
    // rising to the full dry-side weight as the liquid turns transparent (the lower reflection
    // band must run continuously across the meniscus of a clear liquid). The grazing rim is the outer
    // surface's reflection, whatever is inside: full weight over the liquid and the residue alike.
    c = ambientize(mix(mix(c, glassHiScaled, glassWet), glassEdge, wetRim), bodyL, ambAmt);
    if (wet < 1) c = mix(c, dryRow, (1 - wet) * (1 - dryT[y]));   // unwetted band: the empty tube's row
    rows[y] = q(c);
    bubbleIn[y] = q(mix(c, [0, 0, 0], p.bubbleDark));
  }
  // Fizz ring: the lit rim shaded as the liquid is lit at that row (the body shading relative to its brightest row;
  // the backing seen through, the surface highlight and the glass reflections are not light inside the liquid),
  // capped at 0.8 so the white pinpoint reads above it. Shading by the composited row capped the ring below the
  // liquid body on glossy presets (the highlight / glass rows set the maximum) and left bubbles darker than it.
  const rowLMax = Math.max(1, ...rowL);
  for (let y = 0; y < H; y++) bubbleRimRows[y] = q(ambientize(scale(rimLit, 0.8 * rowL[y] / rowLMax), bodyL, ambAmt));
  return {
    rows, tubeBackRows, body: q(scale(body, br)), tubeBack: q(scale(tubeBack, p.brightness)),
    bubbleRim: q(ambientize(scale(rimC, br), bodyL, ambAmt)), bubbleIn, bubbleRimRows, dryT,
  };
}

function hspan(y: number, x0: number, x1: number, c: number): void {
  if (y < 0 || y >= PANEL_H) return;
  x0 = Math.max(0, x0); x1 = Math.min(PANEL_W, x1);
  if (x1 <= x0) return;
  fb.fill(c, y * PANEL_W + x0, y * PANEL_W + x1);
}
/** Blend colour c over the existing pixel with opacity t (1 = replace). */
function pxa(x: number, y: number, c: number, t: number): void {
  if (x < 0 || y < 0 || x >= PANEL_W || y >= PANEL_H) return;
  const i = y * PANEL_W + x;
  fb[i] = t >= 1 ? c : blend565(fb[i], c, t);
}
function px(x: number, y: number, c: number): void {
  if (x < 0 || y < 0 || x >= PANEL_W || y >= PANEL_H) return;
  fb[y * PANEL_W + x] = c;
}

// Bitmap digit fonts 0-9; rows top→bottom, w bits per row (MSB = left). Selected by params.digitFont.
interface Font { w: number; h: number; g: number[][]; name: string }
const FONT_3x5: Font = { name: '3x5', w: 3, h: 5, g: [
  [0b111,0b101,0b101,0b101,0b111], [0b010,0b110,0b010,0b010,0b111], [0b111,0b001,0b111,0b100,0b111],
  [0b111,0b001,0b111,0b001,0b111], [0b101,0b101,0b111,0b001,0b001], [0b111,0b100,0b111,0b001,0b111],
  [0b111,0b100,0b111,0b101,0b111], [0b111,0b001,0b001,0b001,0b001], [0b111,0b101,0b111,0b101,0b111],
  [0b111,0b101,0b111,0b001,0b111] ] };
const FONT_4x6: Font = { name: '4x6 narrow', w: 4, h: 6, g: [
  [0b0110,0b1001,0b1001,0b1001,0b1001,0b0110], [0b0010,0b0110,0b0010,0b0010,0b0010,0b0111],
  [0b0110,0b1001,0b0001,0b0010,0b0100,0b1111], [0b1110,0b0001,0b0110,0b0001,0b1001,0b0110],
  [0b0010,0b0110,0b1010,0b1111,0b0010,0b0010], [0b1111,0b1000,0b1110,0b0001,0b1001,0b0110],
  [0b0110,0b1000,0b1110,0b1001,0b1001,0b0110], [0b1111,0b0001,0b0010,0b0100,0b0100,0b0100],
  [0b0110,0b1001,0b0110,0b1001,0b1001,0b0110], [0b0110,0b1001,0b1001,0b0111,0b0001,0b0110] ] };
const FONT_5x7: Font = { name: '5x7 round', w: 5, h: 7, g: [
  [0b01110,0b10001,0b10011,0b10101,0b11001,0b10001,0b01110], [0b00100,0b01100,0b00100,0b00100,0b00100,0b00100,0b01110],
  [0b01110,0b10001,0b00001,0b00010,0b00100,0b01000,0b11111], [0b11111,0b00010,0b00100,0b00010,0b00001,0b10001,0b01110],
  [0b00010,0b00110,0b01010,0b10010,0b11111,0b00010,0b00010], [0b11111,0b10000,0b11110,0b00001,0b00001,0b10001,0b01110],
  [0b00110,0b01000,0b10000,0b11110,0b10001,0b10001,0b01110], [0b11111,0b00001,0b00010,0b00100,0b01000,0b01000,0b01000],
  [0b01110,0b10001,0b10001,0b01110,0b10001,0b10001,0b01110], [0b01110,0b10001,0b10001,0b01111,0b00001,0b00010,0b01100] ] };
const FONT_7SEG: Font = { name: '5x7 seven-segment', w: 5, h: 7, g: [
  [0b11111,0b10001,0b10001,0b10001,0b10001,0b10001,0b11111], [0b00001,0b00001,0b00001,0b00001,0b00001,0b00001,0b00001],
  [0b11111,0b00001,0b00001,0b11111,0b10000,0b10000,0b11111], [0b11111,0b00001,0b00001,0b11111,0b00001,0b00001,0b11111],
  [0b10001,0b10001,0b10001,0b11111,0b00001,0b00001,0b00001], [0b11111,0b10000,0b10000,0b11111,0b00001,0b00001,0b11111],
  [0b11111,0b10000,0b10000,0b11111,0b10001,0b10001,0b11111], [0b11111,0b00001,0b00001,0b00001,0b00001,0b00001,0b00001],
  [0b11111,0b10001,0b10001,0b11111,0b10001,0b10001,0b11111], [0b11111,0b10001,0b10001,0b11111,0b00001,0b00001,0b11111] ] };
const FONT_6x8B: Font = { name: '6x8 bold', w: 6, h: 8, g: [
  [0b011110,0b110011,0b110011,0b110011,0b110011,0b110011,0b110011,0b011110], [0b001100,0b011100,0b001100,0b001100,0b001100,0b001100,0b001100,0b111111],
  [0b011110,0b110011,0b000011,0b000110,0b001100,0b011000,0b110000,0b111111], [0b111110,0b000011,0b000011,0b011110,0b000011,0b000011,0b110011,0b011110],
  [0b000110,0b001110,0b011110,0b110110,0b111111,0b000110,0b000110,0b000110], [0b111111,0b110000,0b110000,0b111110,0b000011,0b000011,0b110011,0b011110],
  [0b011110,0b110000,0b110000,0b111110,0b110011,0b110011,0b110011,0b011110], [0b111111,0b000011,0b000110,0b001100,0b011000,0b011000,0b011000,0b011000],
  [0b011110,0b110011,0b110011,0b011110,0b110011,0b110011,0b110011,0b011110], [0b011110,0b110011,0b110011,0b011111,0b000011,0b000011,0b000011,0b011110] ] };
export const FONTS: Font[] = [FONT_3x5, FONT_4x6, FONT_5x7, FONT_7SEG, FONT_6x8B];
export const SPRITE_FONT = FONTS.length; // digitFont value that selects the image-based glyphs

/** Image-based glyph sheet (AI-generated metal digits, see tools/make-digit-sprites.py).
 *  Firmware equivalent: one pre-scaled RGB565+A8 table per tube size, generated offline. */
export interface SpriteSheet { cellW: number; cellH: number; widths: number[]; data: Uint8ClampedArray; w: number; h: number; }
/** w x h texels (body plus the baked shadow margin); `adv` is the body width the layout advances by. a = 0..255 coverage.
 *  c/a: the glyph as drawn behind air; cw/aw: as drawn behind liquid (the shadow composite depends on the liquid's
 *  transparency, see bakeShadow). Without a shadow both pairs are the same arrays. */
interface ScaledGlyph { w: number; h: number; adv: number; c: Uint16Array; a: Uint8Array; cw: Uint16Array; aw: Uint8Array; }
/** Sheet names in digitFont order starting at SPRITE_FONT (files live in public/assets/<name>.png[.json]). */
export const SPRITE_SHEETS = [
  'digits-steel',
  'digits-brass-steampunk',
  'digits-copper-gauge',
  'digits-forged-iron',
  'digits-ivory-enamel',
  'digits-carved-slate',
  'digits-amber-resin',
];
const sprites: (SpriteSheet | null)[] = SPRITE_SHEETS.map(() => null);
const scaledCache = new Map<string, ScaledGlyph[]>();
/** Inject a decoded sheet directly (headless tests / node reference renders). */
export function setSprite(i: number, sheet: SpriteSheet): void { sprites[i] = sheet; scaledCache.clear(); }
export function loadSprites(base: string): void {
  SPRITE_SHEETS.forEach((n, i) => loadSprite(base + n + '.png').then(sh => { sprites[i] = sh; scaledCache.clear(); })
    .catch(e => console.warn('digit sprite not loaded', n, e)));
}
function loadSprite(url: string): Promise<SpriteSheet> {
  return Promise.all([
    fetch(url + '.json').then(r => r.json()),
    new Promise<HTMLImageElement>((ok, err) => { const im = new Image(); im.onload = () => ok(im); im.onerror = err; im.src = url; }),
  ]).then(([meta, im]) => {
    const cv = document.createElement('canvas'); cv.width = im.width; cv.height = im.height;
    const ctx = cv.getContext('2d')!; ctx.drawImage(im, 0, 0);
    return { cellW: meta.cellW, cellH: meta.cellH, widths: meta.widths, data: ctx.getImageData(0, 0, im.width, im.height).data, w: im.width, h: im.height };
  });
}
/** Index of texel (x, y) of a w x h glyph as the viewer reads it. `rot` = vertical watch: the planes are stored
 *  as the panel shows them (turned a quarter clockwise — the watch is turned the other way — so h columns by w
 *  rows, the glyph's bottom row in column 0), and the draw pass handles them like any other bitmap. */
const texel = (x: number, y: number, w: number, h: number, rot: boolean): number => rot ? x * h + (h - 1 - y) : y * w + x;
/** Bake the digit shadow into one plane (w x h texels c/a holding the body at the top-left): the shadow copy,
 *  offset `off` px down-right in the shadow colour at `shadowA`, composited UNDER the body. The draw pass used
 *  to blend the two copies one after the other, each at its coverage times the factor k the compositor applies
 *  to a mark behind liquid (liquidTransparency; 1 behind air):
 *  out = bg(1 - k*s)(1 - k*b) + shadowC*k*s*(1 - k*b) + bodyC*k*b. That is one blend of the composite with
 *  alpha A = 1 - (1 - k*s)(1 - k*b) and colour (shadowC*k*s*(1 - k*b) + bodyC*k*b) / A — the transparency
 *  INCLUDED, because two layers at k reach an opacity (up to 1 - (1-k)^2) a single mark at k never could.
 *  So a plane is baked per context: behind air with k = 1, behind liquid with k = transparency, and markFn
 *  skips its own transparency step for these glyphs (`bakedT`). Exact to within one quantisation step at half
 *  the per-frame work; the approximations are the wall-band fade rows behind air (their factor varies per row)
 *  and a non-zero markContrast (floored on the composite instead of per layer). Texels are visited bottom-right
 *  to top-left so the body texel a shadow sample reads, (x-off, y-off), has not been rewritten yet.
 *  Mirrored by the firmware. */
function bakeShadow(c: Uint16Array, a: Uint8Array, w: number, h: number, bw: number, bh: number, off: number, shadowC: number, shadowA: number, k: number, rot = false): void {
  const sc = rgb565to888(shadowC);
  for (let y = h - 1; y >= 0; y--) for (let x = w - 1; x >= 0; x--) {
    const i = texel(x, y, w, h, rot);
    const as = x >= off && y >= off ? a[texel(x - off, y - off, w, h, rot)] : 0;
    const ab = x < bw && y < bh ? a[i] : 0;
    if (!as && (!ab || k >= 1)) continue;                // empty, or a body-only texel behind air: unchanged
    const s = as * shadowA * (1 / 255) * k, b = ab * (1 / 255) * k, A = 1 - (1 - s) * (1 - b);
    if (A <= 0) { c[i] = 0; a[i] = 0; continue; }        // fully transparent (k = 0: opaque liquid hides the mark)
    const ws = s * (1 - b) / A, wb = b / A;
    const bc = ab ? rgb565to888(c[i]) : [0, 0, 0];
    c[i] = q([sc[0] * ws + bc[0] * wb, sc[1] * ws + bc[1] * wb, sc[2] * ws + bc[2] * wb]);
    a[i] = Math.round(A * 255);
  }
}
/** The contrast floor (markContrast) baked into the behind-liquid plane against one liquid colour R (the body,
 *  floorR): per texel the colour that, blended over R by its coverage as is, gives what markFn's floor would have
 *  made of it over R — the floored composite at a = max(T, cov), c' = R + (floor(mix(R, c, a)) − R) / a. Drawn
 *  without a floor, so the liquid behind still shows through by the same coverage; only the floor's colour push is
 *  fixed per texel instead of per pixel behind (cheaper on the board). Mirrored by the firmware (bakeFloor). */
function bakeFloor(c: Uint16Array, a: Uint8Array, transK: number, contrast: number, floorR: number): void {
  const R = rgb565to888(floorR), lb = luma(R);
  for (let i = 0; i < a.length; i++) {
    if (!a[i]) continue;
    const ak = Math.max(transK, a[i] / 255);
    if (ak <= 0) continue;
    let m = mix(R, rgb565to888(c[i]), ak);
    const lc = luma(m), d = lc - lb;
    if (Math.abs(d) >= contrast) continue;   // already apart: the texel as is
    const dir = d !== 0 ? Math.sign(d) : lb > 110 ? -1 : 1;
    const target = Math.max(0, Math.min(255, lb + dir * contrast));
    m = dir < 0 ? scale(m, target / Math.max(1, lc)) : mix(m, [255, 255, 255], Math.min(1, (target - lc) / Math.max(1, 255 - lc)));
    c[i] = q([R[0] + (m[0] - R[0]) / ak, R[1] + (m[1] - R[1]) / ak, R[2] + (m[2] - R[2]) / ak]);
  }
}
/** Box-filter the sheet glyph d into bw x bh device pixels (once per size; firmware ships the result).
 *  shadow: 565 colour of the baked digit shadow (-1 = none), shadowA its opacity, shadowOff its px offset,
 *  transK the liquid transparency the behind-liquid plane is baked for. */
function scaledGlyphs(sheet: number, bw: number, bh: number, brightness: number, tint: [number, number, number], tintAmt: number, tone: number,
                      shadow: number, shadowA: number, shadowOff: number, transK: number, rot = false, floorC = 0, floorR = 0): ScaledGlyph[] | null {
  const sprite = sprites[sheet]; if (!sprite) return null;
  const key = `${sheet}:${bw}x${bh}@${brightness}/${tint}/${tintAmt}/${tone}/${shadow}/${shadowA}/${shadowOff}/${transK}/${rot}/${floorC}/${floorR}`; const hit = scaledCache.get(key); if (hit) return hit;
  const off = shadow >= 0 ? shadowOff : 0;   // baked shadow margin (right and bottom)
  const out: ScaledGlyph[] = [];
  // tint = multiply by colour (greyscale sheets become bronze/gold/etc.), blended by tintAmt
  const tm = (v: number, ch: number) => v * (1 - tintAmt) + v * (tint[ch] / 255) * tintAmt;
  const t = Math.max(-1, Math.min(1, tone));
  const tn = (v: number) => t < 0 ? v * (1 + t) : v + (255 - v) * t;
  for (let d = 0; d < 10; d++) {
    const gw = Math.max(1, Math.round(sprite.widths[d] * bw / sprite.cellW));
    const cx0 = d * sprite.cellW + (sprite.cellW - sprite.widths[d]) / 2;
    const tw = gw + off, th = bh + off;
    const c = new Uint16Array(tw * th), a = new Uint8Array(tw * th);
    // Box bounds as exact ratios (x * width / gw, not x / sx): the reciprocal form lands a hair above an
    // integer in doubles and a hair below in the firmware's floats, dropping the glyph's last sheet column there.
    for (let y = 0; y < bh; y++) for (let x = 0; x < gw; x++) {
      const X0 = Math.floor(cx0 + (x * sprite.widths[d]) / gw), X1 = Math.max(X0 + 1, Math.floor(cx0 + ((x + 1) * sprite.widths[d]) / gw));
      const Y0 = Math.floor((y * sprite.cellH) / bh), Y1 = Math.max(Y0 + 1, Math.floor(((y + 1) * sprite.cellH) / bh));
      let r = 0, g = 0, b = 0, al = 0, n = 0;
      for (let Y = Y0; Y < Y1; Y++) for (let X = X0; X < X1; X++) {
        const i = (Y * sprite.w + X) * 4, pa = sprite.data[i + 3];
        r += sprite.data[i] * pa; g += sprite.data[i + 1] * pa; b += sprite.data[i + 2] * pa; al += pa; n++;
      }
      const k = texel(x, y, tw, th, rot);
      if (al > 0) { c[k] = q(scale([tn(tm(r / al, 0)), tn(tm(g / al, 1)), tn(tm(b / al, 2))], brightness)); a[k] = Math.round(al / n); }
    }
    let cw = c, aw = a;
    if (off > 0) {
      cw = c.slice(); aw = a.slice();
      bakeShadow(c, a, tw, th, gw, bh, off, shadow, shadowA, 1, rot);
      bakeShadow(cw, aw, tw, th, gw, bh, off, shadow, shadowA, transK, rot);
      if (floorC > 0) bakeFloor(cw, aw, transK, floorC, floorR);
    }
    out.push({ w: rot ? th : tw, h: rot ? tw : th, adv: gw, c, a, cw, aw });
  }
  scaledCache.set(key, out);
  return out;
}
/** Composites one mark (tick / label) pixel; `cov` is glyph anti-alias coverage 0..1.
 *  `rel` = +1 / -1 draws the emboss highlight / shadow of body colour `c`. */
type MarkFn = (x: number, y: number, c: number, cov?: number, rel?: number) => void;
const embossOf = (c: number, rel: number): number =>
  rel > 0 ? q(mix(rgb565to888(c), [255, 255, 255], 0.7)) : q(scale(rgb565to888(c), 0.25));

const luma = (c: [number, number, number]): number => 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2];
/** Colour of a mark seen through the liquid: alpha-blended by `liquidTransparency`, then pushed
 *  away from the liquid behind it until the two differ by at least `contrast` in luma.
 *  Without that floor a mid-grey tick is invisible against the highlight band (which covers most
 *  of the upper half of the tube) and against the shaded body alike. `contrast` is `markContrast`
 *  scaled by the layer's brightness trim, so dimming a layer also relaxes its legibility floor —
 *  otherwise the floor would simply undo the dimming wherever the mark sits over liquid.
 *  Firmware note: the liquid behind a mark is the per-row LUT colour, so this whole function
 *  collapses into one extra H-row table per mark colour, built when params change. */
function throughLiquid(bg: number, mark: number, p: Params, contrast: number, transparency = p.liquidTransparency): number {
  const B = rgb565to888(bg);
  let c = mix(B, rgb565to888(mark), transparency);
  const lb = luma(B), lc = luma(c), d = lc - lb;
  if (Math.abs(d) >= contrast) return q(c);
  const dir = d !== 0 ? Math.sign(d) : lb > 110 ? -1 : 1;      // no room to darken a near-black row: go up
  const target = Math.max(0, Math.min(255, lb + dir * contrast));
  c = dir < 0 ? scale(c, target / Math.max(1, lc))
    : mix(c, [255, 255, 255], Math.min(1, (target - lc) / Math.max(1, 255 - lc)));
  return q(c);
}
/** Mark compositor for one tube. `onTop` marks ignore the liquid and are drawn opaque. Rear marks
 *  behind air fade by `dryT` (invisible inside the glass wall band, like the tube back there).
 *  Emboss pixels derive from the body's through-liquid colour so the relief survives the contrast floor. */
/** `bakedT`: the mark's coverage already includes the liquid's transparency (sprite digits with a baked shadow,
 *  see bakeShadow); behind liquid the contrast floor is applied at full glyph coverage (see below). */
/** Contrast floor of the rear sprite digits, baked into their behind-liquid plane (bakeFloor): [contrast, body 565]
 *  or [0, 0] when there is none (no floor, digits on top, no baked shadow plane). */
function floorBake(p: Params): [number, number] {
  const contrast = p.markContrast * p.digitBright;
  if (!(contrast > 0) || p.digitsOnTop || !(p.digitShadow && p.digitShadowStrength > 0)) return [0, 0];
  return [contrast, q(scale(hexToRgb(p.liquid), p.brightness * p.liquidBright))];
}
function markFn(y0: number, edges: Edges, p: Params, onTop: boolean, contrast: number, dryT: Float32Array | null = null, bakedT = false, floorBaked = false): MarkFn {
  const H = edges.hi.length, band = onTop ? undefined : edges.band;
  const transK = Math.max(0, Math.min(1, p.liquidTransparency));
  return (x, y, c, cov = 1, rel = 0) => {
    const ry = y - y0;
    if (ry < 0 || ry >= H || x < 0 || x >= PANEL_W) return;
    const inside = x >= edges.lo[ry] && x < edges.hi[ry];
    if (!onTop) {
      // The concave surface band's footprint at this pixel — it overlaps the body by hw inside the
      // profile: how much its rim and blick let through (they stay on top of every rear mark) and, past
      // the body, the fill's own opacity there. (Approximation: the layers' own colour also yields to the
      // mark by that share; exact compositing would need the back as it was before the band.)
      let through = 1, wet = 0, under = false;
      if (band) {
        const xr = band.mirror ? band.L - 1 - x : x, hw = band.hw;
        // the edge whose footprint (hw inside the profile to the stroke width past it) can hold this pixel
        const side: 0 | 1 = xr + 0.5 > band.xm[0][ry] - hw ? 0 : 1;
        const wEff = band.w[side][ry];   // 0: no band on that side; a far pixel gets no coverage below
        if (wEff > 0) {
          const t = (side === 0 ? 1 : -1) * (xr + 0.5 - band.xm[side][ry]);
          const lo = Math.max(t - 0.5, -hw), hi = Math.min(t + 0.5, wEff), coverage = hi - lo;
          if (coverage > 0) {
            const u = Math.max(0, Math.min(1, ((lo + hi) / 2 + hw) / (wEff + hw))), us = u * u * (3 - 2 * u);
            const ab = Math.min(1, band.blick[side][ry] * coverage * 4 * u * (1 - u));
            const ar = Math.min(1, band.rim[side][ry] * Math.max(0, hi - Math.max(lo, Math.max(0, wEff - 1))));
            through = (1 - ab) * (1 - ar);
            if (!inside) { wet = Math.min(1, band.fill[side][ry] * coverage * (1 - band.pull[side] * us)); under = true; }
          }
        }
      }
      if (inside) {
        if (!bakedT) c = throughLiquid(fb[y * PANEL_W + x], c, p, contrast, transK);
        else if (contrast > 0 && !floorBaked) {
          // The coverage already carries the transparency (glyph alpha x T, more where a baked shadow overlaps
          // the body), so the texel as is would never meet the floor. Floor what the glyph shows at full glyph
          // coverage — the texel over the liquid at a = max(T, cov) — and blend that by the rest, cov / a:
          // the ticks' floor-then-coverage order, so digits keep the ticks' contrast. (Without a floor the
          // texel is drawn as is: the same blend, cov = a * (cov / a).)
          const a = Math.max(transK, cov);
          c = throughLiquid(fb[y * PANEL_W + x], c, p, contrast, a);
          cov /= a;
        }
        // The glass-cut relief is on the rear wall too: it fades with the liquid's opacity (invisible
        // through an opaque liquid) while its colour still derives from the floored through-liquid body.
        if (rel !== 0) cov *= transK;
        cov *= through;
      } else if (under) {
        // Under the band past the body the rear wall is seen through the dish: the mark is liquid-tinted
        // as far as the fill is opaque there (its own per-pixel opacity — no threshold to jump), dry for
        // the rest. The band's plane is the behind-air one, so the coverage never has the transparency
        // baked in and the wet part applies it itself. The wet/dry colour mix and the blend over the pixel
        // are taken in 888 and rounded ONCE (parity: each extra 565 rounding stacks between renderers).
        const i = y * PANEL_W + x;
        const aw = cov * wet * (rel !== 0 ? transK : 1), ad = cov * (1 - wet) * (dryT ? dryT[ry] : 1);
        const al = (aw + ad) * through;
        if (al < 1 / 255) return;
        let M = rgb565to888(c);
        if (aw > 0) {
          const CT = rgb565to888(throughLiquid(fb[i], c, p, contrast, transK));
          M = ad > 0 ? mix(M, CT, aw / (aw + ad)) : CT;
        }
        if (rel !== 0) M = rgb565to888(embossOf(q(M), rel));
        fb[i] = al >= 1 ? q(M) : q(mix(rgb565to888(fb[i]), M, al));
        return;
      } else if (dryT) cov *= dryT[ry];
    }
    if (rel !== 0) c = embossOf(c, rel);
    pxa(x, y, c, cov);
  };
}

/** Stable integer hash shared with firmware: the texture must not shimmer between frames. */
// ---------------------------------------------------------------------------
// Scale = tick ladder + numeric labels, both laid out from the same `ticksN` grid.
// ---------------------------------------------------------------------------

/** One numeric label: its text, the glyph advances, and the box it occupies. */
interface Label { text: string; x0: number; y: number; adv: number[]; }
/** Everything the draw pass and the tick pass need to know about a tube's labels. */
interface Labels {
  list: Label[]; bw: number; bh: number; ry0: number; ry1: number; y0: number; yTop: number; sourceRows: Int16Array;
  /** Rear digits behind air (see `digitDryLens`); same as the wet tables for digits on top. */
  drySourceRows: Int16Array; dryRy0: number; dryRy1: number;
  /** Refraction shift (px, fractional) of the columns behind liquid (`digitParallax`); 0 behind air and for digits on top. */
  wetDx: number; wetDy: number;
  sprite: ScaledGlyph[] | null; font: Font; gap: number; rows: Uint16Array; shadow: number; shadowA: number; shadowOff: number;
  /** Vertical watch: glyphs are turned to read upright, a label's digits advance across the tube (panel y) from
   *  `Label.y`, and `Label.x0` is where the glyph body starts along it. bw x bh stay the glyph as read. */
  vertical: boolean;
}

/** Panel x of scale value i of n. A vertical watch in `remaining` mode runs the scale from the top (right) end. */
const scaleFlip = (p: Params): boolean => p.vertical && p.remaining;

/** Cylinder warp of an independently warped mark: |row offset from the axis| 0..1 → the source's. */
function markWarp(lens: number, curve = 1): (u: number) => number {
  const strength = Math.abs(Math.max(-1, Math.min(1, lens)));
  const signedCurve = lens < 0 ? -Math.max(-3, Math.min(3, curve)) : Math.max(-3, Math.min(3, curve));
  const exponent = signedCurve > 0 ? 1 + signedCurve * 2 : 1 / (1 - signedCurve * 2);
  return (u) => signedCurve === 0 ? u : (1 - strength) * u + strength * Math.pow(u, exponent);
}
/** Destination tube row to source row for independently warped marks. */
export function markSourceRows(H: number, lens: number, curve = 1): Int16Array {
  const out = new Int16Array(H), warp = markWarp(lens, curve);
  for (let yd = 0; yd < H; yd++) {
    const d = (yd + 0.5 - H / 2) / (H / 2);
    const s = Math.sign(d) * warp(Math.abs(d));
    out[yd] = Math.max(0, Math.min(H - 1, Math.floor(H / 2 + s * H / 2)));
  }
  return out;
}
/** markSourceRows before it is rounded to rows: the source's offset from the tube axis, in rows. */
function markSourceOffsets(H: number, lens: number): Float64Array {
  const out = new Float64Array(H), warp = markWarp(lens);
  for (let yd = 0; yd < H; yd++) {
    const d = (yd + 0.5 - H / 2) / (H / 2);
    out[yd] = Math.sign(d) * warp(Math.abs(d)) * H / 2;
  }
  return out;
}
/** The markSourceRows row of such an offset. */
const offsetRow = (H: number, off: number): number => Math.max(0, Math.min(H - 1, Math.floor(H / 2 + off)));
/** Inverse of a markWarp (monotone on 0..1), by bisection. */
function markUnwarp(warp: (u: number) => number, w: number): number {
  let lo = 0, hi = 1;
  for (let i = 0; i < 32; i++) { const m = (lo + hi) / 2; if (warp(m) < w) lo = m; else hi = m; }
  return (lo + hi) / 2;
}

/** Vertical watch, rear ticks under rear digits: both lie on one wall and on one axis across the tube, so the
 *  liquid moves them by ONE remap — the digits' (behind air → behind liquid, `digitDryLens` → `bottomLens`), and
 *  a tick clear of a label behind air stays clear of it behind liquid, at every wet share of the meniscus.
 *  Behind air the tick is its own `tickDryLens` image; `tickLens` has no say. Where a column is wet, a row is
 *  tick when the digit source position it shows (`dry` → `wet` by the share; offsets from the axis, in rows)
 *  lies wallward of the one under the dry tick's end (`edge`) — through the unrounded maps, as rounded rows
 *  would smear the end over every row a strong lens folds onto one source row — and its digit source ROW (the
 *  labels' own rounding) does too. */
export interface TickFollow { dry: Float64Array; wet: Float64Array; edge: (h: number) => number; }
const rearTicksFollowDigits = (p: Params): boolean => p.vertical && p.digits && !p.digitsOnTop && !p.ticksOnTop;
export function tickFollow(p: Params, H: number): TickFollow {
  const tick = markWarp(p.tickDryLens), digit = markWarp(p.digitDryLens);
  return {
    dry: markSourceOffsets(H, p.digitDryLens), wet: markSourceOffsets(H, p.bottomLens),
    /** Digit source offset under the inner end of a dry tick `h` source rows long, the one from the near wall. */
    edge: (h) => {
      const t = Math.max(-1, Math.min(1, (h - H / 2) / (H / 2)));
      return Math.sign(t) * digit(markUnwarp(tick, Math.abs(t))) * H / 2;
    },
  };
}

/** Measure (but do not draw) the labels of one tube. Returns null when digits are off. */
function layoutLabels(y0: number, p: Params, ticksN: number, acrossTilt: number, edgeLight: number, fill: number): Labels | null {
  if (!p.digits) return null;
  const minutes = ticksN === 60;
  const every = Math.max(1, Math.round(minutes ? p.digitMinuteStep : p.digitHourStep));
  const kx = minutes ? p.digitScaleXMin : p.digitScaleX, ky = minutes ? p.digitScaleYMin : p.digitScaleY;
  const bottom = (minutes ? p.digitBottomMin : p.digitBottom) + (p.digitsOnTop ? Math.round(acrossTilt * p.topParallax) : 0);
  const idx = Math.round(p.digitFont), useSprite = idx >= SPRITE_FONT;
  const font = FONTS[Math.max(0, Math.min(FONTS.length - 1, idx))];
  // sprite glyphs use the same nominal 5x7 em as the bitmap fonts so the scale sliders mean the same thing
  // Vertical watch: the glyph's width lies across the tube and its height along it, so the scales swap roles
  // (X stays the along-tube one, Y the one the vial stretches).
  const V = p.vertical, kw = V ? ky : kx;
  const bw = Math.max(1, Math.round((useSprite ? 5 : font.w) * kw));
  const bh = Math.max(1, Math.round((useSprite ? 7 : font.h) * (V ? kx : ky)));
  const shadowA = Math.max(0, Math.min(1, p.digitShadowStrength)), shadowOff = Math.max(1, Math.round(p.digitShadowOffset));
  const shadow = p.digitShadow && shadowA > 0 ? q(scale(hexToRgb(p.digitShadowColor), p.brightness * p.digitBright)) : -1;
  // Sprite glyphs carry the shadow baked in (one draw pass); bitmap glyphs still draw it as a second pass.
  // The behind-liquid plane is baked for the transparency markFn applies.
  const transK = Math.max(0, Math.min(1, p.liquidTransparency));
  const sprite = useSprite
    ? scaledGlyphs(idx - SPRITE_FONT, bw, bh, p.brightness * p.digitBright, hexToRgb(p.digitTint), p.digitTintAmount, p.digitTone, shadow, shadowA, shadowOff, transK, V,
        ...floorBake(p))
    : null;
  const gap = sprite ? Math.max(1, Math.round(bw / 5)) : Math.max(1, Math.round(kw));
  const yBase = y0 + tubeLayout(p).H - 1 - bottom, yTop = yBase - bh + 1;
  const H = tubeLayout(p).H;
  const sourceRows = p.digitsOnTop ? markSourceRows(H, p.topLens, p.lensCurve) : markSourceRows(H, p.bottomLens);
  const drySourceRows = p.digitsOnTop ? sourceRows : markSourceRows(H, p.digitDryLens);
  // Liquid refracts the rear wall: the wet columns slide with tilt (same sign convention as the ticks).
  // Fractional: the wet copy is resampled at draw time so it glides rather than steps.
  const wetDx = p.digitsOnTop ? 0 : -edgeLight * p.digitParallax;
  const wetDy = p.digitsOnTop ? 0 : acrossTilt * p.digitParallax;
  const list: Label[] = [];
  const start = Math.round(minutes ? p.digitMinuteStart : p.digitHourStart) || every;
  const flip = scaleFlip(p);
  let yMin = yBase + 1, yMax = yBase;   // vertical: the labels' extent across the tube
  const push = (i: number) => {
    const text = minutes && p.digitsLeadingZero ? String(i).padStart(2, '0') : String(i);
    const adv = [...text].map((ch) => sprite?.[ch.charCodeAt(0) - 48]?.adv ?? bw);
    const w = adv.reduce((a, b) => a + b + gap, -gap);
    const m = Math.round(p.cornerR);
    if (V) {
      // centred on its tick along the tube and on the tube's axis across it (`digitBottom` has no say; the front
      // parallax still shifts it); a label too wide for the tube starts at the near wall
      const y = Math.max(y0, y0 + ((H - w) >> 1) - (p.digitsOnTop ? Math.round(acrossTilt * p.topParallax) : 0));
      yMin = Math.min(yMin, y); yMax = Math.max(yMax, y + w - 1);
      const c = (i * TUBE_LENGTH_PX) / ticksN;
      const x0 = Math.max(m, Math.min(TUBE_LENGTH_PX - bh - m, Math.round((flip ? TUBE_LENGTH_PX - c : c) - bh / 2)));
      list.push({ text, x0, y, adv });
      return;
    }
    const x0 = Math.max(m, Math.min(TUBE_LENGTH_PX - w - m, Math.round((i * TUBE_LENGTH_PX) / ticksN - w / 2)));
    list.push({ text, x0, y: yTop, adv });
  };
  if (minutes ? p.digitsLastOnlyM : p.digitsLastOnlyH) { const s = minutes ? every : 1, i = Math.floor(Math.min(ticksN - 1e-6, Math.max(0, fill) * ticksN) / s) * s; if (i > 0) push(i); }
  else for (let i = start; i < ticksN; i += every) push(i);
  const sourceRy0 = (V ? yMin : yTop) - y0, sourceRy1 = (V ? yMax : yBase) - y0 + (shadow >= 0 ? shadowOff : 0);
  const rowSpan = (rows: Int16Array, shift: number): [number, number] => {
    let a = H, b = -1;
    for (let ry = 0; ry < H; ry++) if (rows[ry] >= sourceRy0 + Math.floor(shift) && rows[ry] <= sourceRy1 + Math.ceil(shift)) { a = Math.min(a, ry); b = Math.max(b, ry); }
    return [a, b];
  };
  const [ry0, ry1] = rowSpan(sourceRows, wetDy), [dryRy0, dryRy1] = rowSpan(drySourceRows, 0);
  return { list, bw, bh, y0, yTop, ry0, ry1, sourceRows, drySourceRows, dryRy0, dryRy1, wetDx, wetDy, sprite, font, gap, rows: digitRowColors(p, bh), shadow, shadowA, shadowOff, vertical: V };
}

/** Liquid column bounds per tube row in panel coordinates: liquid where lo <= x < hi. */
/** Concave surface band of one tube for the rear-mark compositor (render frame, i.e. before the
 *  `remaining` mirror; index 0 = time edge, dir +1, 1 = home edge, dir -1). Per row: the profile x,
 *  the outward stroke width (0 = no band) and the fill / blick / rim weights, stroke opacity included. */
export interface BandInfo {
  xm: [Float32Array, Float32Array]; w: [Float32Array, Float32Array];
  fill: [Float32Array, Float32Array]; blick: [Float32Array, Float32Array]; rim: [Float32Array, Float32Array];
  pull: [number, number]; hw: number; mirror: boolean; L: number;
}
/** Liquid body bounds per tube row (panel frame) plus, when drawn, the surface band past them. */
export interface Edges { lo: Float32Array; hi: Float32Array; band?: BandInfo; }
/** Wet share of each panel column in 1/256: how many of the tube rows are liquid there (lo <= x < hi, the
 *  compositor's own test) — 256 where every row is, 0 where none is, the meniscus in between. A rear mark
 *  takes that share of the liquid's refraction (its source rows moved from the behind-air warp toward the
 *  behind-liquid one, its parallax scaled), so the warp grows as the surface passes over it instead of
 *  switching at one row's edge. Integer math, mirrored by the firmware (one table per Tube there: its two tubes
 *  render at the same time, one per core). */
const wetShare = new Uint16Array(PANEL_W), wetRun = new Int16Array(PANEL_W + 1);
function buildWetShare(e: Edges, H: number): void {
  wetRun.fill(0);
  for (let ry = 0; ry < H; ry++) {
    const a = Math.max(0, Math.min(PANEL_W, Math.ceil(e.lo[ry]))), b = Math.max(0, Math.min(PANEL_W, Math.ceil(e.hi[ry])));
    if (b > a) { wetRun[a]++; wetRun[b]--; }
  }
  for (let x = 0, n = 0; x < PANEL_W; x++) { n += wetRun[x]; wetShare[x] = Math.floor((n * 256 + (H >> 1)) / H); }
}
const shareAt = (x: number): number => (x < 0 || x >= PANEL_W ? 0 : wetShare[x]);
/** Source row for wet share k (1/256): the behind-air row `dry` moved toward the behind-liquid row `wet`. */
const blendRow = (dry: number, wet: number, k: number): number => dry + (((wet - dry) * k + 128) >> 8);
/** Rows of a tick ending at `edge` (TickFollow) in a column of wet share `share` (1/256): [0, b] from the near
 *  wall (`top`) or [a, H - 1] from the far one; [H, -1] = none. */
export function tickFollowRange(f: TickFollow, H: number, edge: number, share: number, top: boolean): [number, number] {
  const k = share / 256, E = H / 2 + edge;
  const row = (ry: number): number => blendRow(offsetRow(H, f.dry[ry]), offsetRow(H, f.wet[ry]), share);
  const off = (ry: number): number => f.dry[ry] + (f.wet[ry] - f.dry[ry]) * k;
  if (top) {
    const last = Math.ceil(E) - 1; let b = -1;
    while (b + 1 < H && off(b + 1) < edge && row(b + 1) <= last) b++;
    return [b < 0 ? H : 0, b];
  }
  const first = Math.floor(H - E); let a = H;
  while (a > 0 && off(a - 1) > -edge && row(a - 1) >= first) a--;
  return [a, a < H ? H - 1 : -1];
}
/** Wet share of a column (see wetShare); 256 everywhere for digits on top. */
type WarpFn = (x: number) => number;
/** Sprite digits behind liquid move by whole px: the refraction shift (`wetDx`, `wetDy`) rounded, kept until the shift
 *  is more than 0.7 px away, so a shift resting near x.5 does not flicker between two px. Render state across frames,
 *  one per tube (firmware Labels::holdWhole); `setDigitHold` puts the one a board dump held (render-ref.ts). */
interface DigitHold { dx: number; dy: number; held: boolean; }
const digitHold: [DigitHold, DigitHold] = [{ dx: 0, dy: 0, held: false }, { dx: 0, dy: 0, held: false }];
export function setDigitHold(idx: number, dx: number, dy: number): void { digitHold[idx & 1] = { dx, dy, held: true }; }
function holdWhole(h: DigitHold, lb: Labels): void {
  const hold = (v: number, w: number): number => !h.held || Math.abs(v - w) > 0.7 ? Math.round(v) : w;
  h.dx = hold(lb.wetDx, h.dx); h.dy = hold(lb.wetDy, h.dy); h.held = true;
}
/** Coverage (0..255) and colour of glyph pixel (cx, cy); both only defined inside w x h. */
interface GlyphSampler {
  w: number; h: number; a: (cx: number, cy: number) => number; c: (cx: number, cy: number) => number;
  /** The same glyph as drawn behind liquid (baked shadow composite for the liquid's transparency). */
  aw: (cx: number, cy: number) => number; cw: (cx: number, cy: number) => number;
}
/** Draw one glyph. A panel column shows one image, chosen by its wet share (see wetShare): behind air (0)
 *  the dry copy, unshifted; behind liquid (256) the wet copy at the fractional refraction shift (`wetDx`,
 *  `wetDy`), bilinearly resampled so it glides with tilt instead of stepping a whole pixel at a time; across
 *  the meniscus (between) the image the column's share of the liquid's refraction gives — source rows blended
 *  from the dry warp to the wet one, the shift scaled — so a label the surface passes over warps gradually.
 *  A resampled pixel's colour comes from the tap contributing the most coverage. */
/** `inLiquid(x, ry)`: whether the mark at that pixel is composited through the liquid (the markFn test);
 *  null = never (digits on top). */
type InLiquidFn = ((x: number, ry: number) => boolean) | null;
/** `whole` (sprite digits, see DigitHold): the wet copy at that whole-px shift instead of the fractional one, the
 *  meniscus columns at their share of it rounded to whole px; null = the fractional shift (bitmap digits). */
function drawGlyph(s: GlyphSampler, x: number, yTop: number, lb: Labels, warp: WarpFn, mark: MarkFn, withShadow: boolean, inLiquid: InLiquidFn,
  whole: DigitHold | null = null): void {
  // Plane per PIXEL: the behind-liquid plane (aw/cw) exactly where markFn composites through the liquid,
  // the behind-air plane elsewhere. The column's share decides which image (warp and shift) it shows; the
  // meniscus makes rows of one column differ, and there the compositor's per-row test picks the plane.
  const A = (L: boolean, cx: number, cy: number): number => L ? s.aw(cx, cy) : s.a(cx, cy);
  const C = (L: boolean, cx: number, cy: number): number => L ? s.cw(cx, cy) : s.c(cx, cy);
  const H = lb.sourceRows.length;
  const tap = (L: boolean, cx: number, cy: number): number => cx < 0 || cy < 0 || cx >= s.w || cy >= s.h ? 0 : A(L, cx, cy);
  // pass 0 = 1 px shadow copy offset down-right as read (the glyph's alpha mask in the shadow colour; a vertical
  // watch's down is the panel's left), pass 1 = body
  for (let pass = withShadow ? 0 : 1; pass < 2; pass++) {
    const shadow = pass === 0, off = shadow ? lb.shadowOff : 0, xg = x + (lb.vertical ? -off : off), sourceTop = yTop - lb.y0 + off;
    // Coverage of glyph alpha a (0..255) in the firmware's 1/256 steps, the shadow copy at its own opacity
    // (also 1/256): a float coverage lands a blend on the other side of a rounding step now and then, and the
    // shadow and body passes on one pixel stack that into two 565 steps between the renderers.
    const alphaT = (t: number): number => Math.floor(t * 256 + 0.5), shadowT = alphaT(lb.shadowA);
    const cov = (a: number): number => (shadow ? (alphaT(a / 255) * shadowT) >> 8 : alphaT(a / 255)) / 256;
    /** Destination column xd at shift (sx, sy) px: its rows `rows(ry)` (source row before the vertical shift)
     *  sample source (cx - fx, cy - fy), taps at columns cx / cx-1, rows cy / cy-1. */
    const shifted = (xd: number, sx: number, sy: number, ry0: number, ry1: number, rows: (ry: number) => number): void => {
      const ix = Math.floor(sx), fx = sx - ix, iy = Math.floor(sy), fy = sy - iy, cx = xd - xg - ix;
      if (cx < 0 || cx > s.w) return;
      // The firmware weighs the taps in 1/256 steps; use the same weights for the coverage and for the colour,
      // which comes from the heaviest tap, so near-ties resolve alike (a baked shadow puts a dark texel right
      // next to a bright one, so a flipped tie is a visible pixel, not a rounding step).
      const wx1 = Math.floor(fx * 256 + 0.5), wx0 = 256 - wx1, wy1 = Math.floor(fy * 256 + 0.5), wy0 = 256 - wy1;
      const w00 = wx0 * wy0, w10 = wx1 * wy0, w01 = wx0 * wy1, w11 = wx1 * wy1;
      for (let ry = ry0; ry <= ry1; ry++) {
        const cy = rows(ry) - sourceTop - iy; if (cy < 0 || cy > s.h) continue;
        const L = inLiquid !== null && inLiquid(xd, ry);
        const t00 = tap(L, cx, cy), t10 = tap(L, cx - 1, cy), t01 = tap(L, cx, cy - 1), t11 = tap(L, cx - 1, cy - 1);
        const m00 = t00 * w00, m10 = t10 * w10, m01 = t01 * w01, m11 = t11 * w11, m = Math.max(m00, m10, m01, m11);
        const a = (m00 + m10 + m01 + m11 + 32768) >> 16; if (!a) continue;
        const c = shadow ? lb.shadow : m === m00 ? C(L, cx, cy) : m === m10 ? C(L, cx - 1, cy) : m === m01 ? C(L, cx, cy - 1) : C(L, cx - 1, cy - 1);
        mark(xd, lb.y0 + ry, c, cov(a));
      }
    };
    for (let cx = 0; cx < s.w; cx++) {                        // behind air: the dry copy
      const xd = xg + cx; if (warp(xd) !== 0) continue;
      for (let ry = lb.dryRy0; ry <= lb.dryRy1; ry++) {
        const cy = lb.drySourceRows[ry] - sourceTop; if (cy < 0 || cy >= s.h) continue;
        const L = inLiquid !== null && inLiquid(xd, ry);
        const a = A(L, cx, cy); if (!a) continue;
        mark(xd, lb.y0 + ry, shadow ? lb.shadow : C(L, cx, cy), cov(a));
      }
    }
    // behind liquid, and across the meniscus: every destination column the shifted glyph can reach
    const wetRows = (ry: number): number => lb.sourceRows[ry];
    const dx = whole ? whole.dx : lb.wetDx, dy = whole ? whole.dy : lb.wetDy;
    const part = (v: number, k: number): number => whole ? Math.round(v * (k / 256)) : v * (k / 256);
    const x0 = xg + Math.min(0, Math.floor(dx)), x1 = xg + s.w + Math.max(0, Math.ceil(dx));
    for (let xd = x0; xd <= x1; xd++) {
      const k = warp(xd); if (k === 0) continue;
      if (k === 256) shifted(xd, dx, dy, lb.ry0, lb.ry1, wetRows);
      else shifted(xd, part(dx, k), part(dy, k), 0, H - 1, (ry) => blendRow(lb.drySourceRows[ry], lb.sourceRows[ry], k));
    }
  }
}
/** Image glyph: per-pixel coverage from the pre-scaled sheet, at the tube's held whole-px shift. */
function drawSpriteGlyph(g: ScaledGlyph | undefined, x: number, yTop: number, lb: Labels, warp: WarpFn, mark: MarkFn, inLiquid: InLiquidFn, whole: DigitHold): void {
  if (!g) return;
  if (lb.vertical) x -= g.w - lb.bh;   // the baked shadow margin lies below the body as read: left of it on the panel
  // the shadow is baked into the sprite (scaledGlyphs), so a single pass draws both
  drawGlyph({
    w: g.w, h: g.h, a: (cx, cy) => g.a[cy * g.w + cx], c: (cx, cy) => g.c[cy * g.w + cx],
    aw: (cx, cy) => g.aw[cy * g.w + cx], cw: (cx, cy) => g.cw[cy * g.w + cx],
  }, x, yTop, lb, warp, mark, false, inLiquid, whole);
}
/** Bitmap glyph, nearest-neighbour scaled into bw x bh. */
function drawBitmapGlyph(f: Font, d: number, x: number, yTop: number, lb: Labels, warp: WarpFn, mark: MarkFn, inLiquid: InLiquidFn): void {
  const g = f.g[d]; if (!g) return;
  const msb = 1 << (f.w - 1);
  const bit = (gx: number, gy: number): number => g[Math.min(f.h - 1, Math.floor((gy * f.h) / lb.bh))] & (msb >> Math.min(f.w - 1, Math.floor((gx * f.w) / lb.bw))) ? 255 : 0;
  if (lb.vertical) {   // turned a quarter: panel (cx, cy) reads glyph column cy, row bh - 1 - cx
    const a = (cx: number, cy: number): number => bit(cy, lb.bh - 1 - cx), c = (cx: number, _cy: number): number => lb.rows[lb.bh - 1 - cx];
    drawGlyph({ w: lb.bh, h: lb.bw, a, c, aw: a, cw: c }, x, yTop, lb, warp, mark, lb.shadow >= 0, inLiquid);
    return;
  }
  const a = bit;
  const c = (_cx: number, cy: number): number => lb.rows[cy];
  drawGlyph({ w: lb.bw, h: lb.bh, a, c, aw: a, cw: c }, x, yTop, lb, warp, mark, lb.shadow >= 0, inLiquid);   // no baked shadow: one plane
}
function digitRowColors(p: Params, bh: number): Uint16Array {
  const n = Math.max(1, bh), out = new Uint16Array(n);
  const a = hexToRgb(p.digitColor), b = hexToRgb(p.digitColor2);
  for (let i = 0; i < n; i++) {
    // metallic: bright top, darker middle-low, slight kick back up at the very bottom
    const t = n === 1 ? 0 : i / (n - 1); const u = t < 0.8 ? t / 0.8 : 1 - (t - 0.8) / 0.2 * 0.35;
    out[i] = q(scale(mix(a, b, u), p.brightness * p.digitBright));
  }
  return out;
}
/** `edges` null = digits on top: everything uses the wet (whole-tube) tables. Otherwise wetShare holds
 *  these edges' shares (drawTube). `whole`: the tube's held shift (sprite digits). */
function drawLabels(lb: Labels, _p: Params, edges: Edges | null, mark: MarkFn, whole: DigitHold): void {
  const warp: WarpFn = edges ? shareAt : () => 256;
  const inLiquid: InLiquidFn = edges ? (x, ry) => x >= edges.lo[ry] && x < edges.hi[ry] : null;
  for (const l of lb.list) {
    let x = l.x0, y = l.y;
    for (let i = 0; i < l.text.length; i++) {
      const d = l.text.charCodeAt(i) - 48;
      if (lb.sprite) drawSpriteGlyph(lb.sprite[d], x, y, lb, warp, mark, inLiquid, whole);
      else drawBitmapGlyph(lb.font, d, x, y, lb, warp, mark, inLiquid);
      if (lb.vertical) y += l.adv[i] + lb.gap; else x += l.adv[i] + lb.gap;
    }
  }
}

const tickRows = new Int16Array(TUBE_HEIGHT_MAX);   // a tick's source rows across the meniscus
/** Tick ladder. Majors are both longer AND wider than minors, and are placed every
 *  `tickMajorEvery` UNITS (hours / minutes), not every N-th minor, so they stay put
 *  when the minor step changes. */
/** `wetRows`/`dryRows`: source-row tables for ticks behind liquid vs behind air (a liquid-filled
 *  cylinder lenses far more than an empty one); a tick takes its column's wet share of both (wetShare, set
 *  for these edges by drawTube). `edges` null = every tick uses `wetRows` and full parallax. `follow`: where
 *  wet, the ticks follow the digits' remap instead of `wetRows` (see TickFollow). */
function drawTicks(y0: number, p: Params, ticksN: number, wetRows: Int16Array, dryRows: Int16Array,
  edges: Edges | null, mark: MarkFn, dxFull = 0, dyFull = 0, follow: TickFollow | null = null): void {
  const minutes = ticksN === 60;
  if (!(minutes ? p.ticksM : p.ticksH)) return;
  const H = tubeLayout(p).H, L = TUBE_LENGTH_PX;
  const step = Math.max(1, Math.round(minutes ? p.tickStepM : p.tickStepH));
  const majorEvery = Math.max(0, Math.round(minutes ? p.tickMajorEveryM : p.tickMajorEveryH));
  const hMin = Math.max(0, Math.round(minutes ? p.tickMinorHeightM : p.tickMinorHeightH));
  const hMaj = Math.max(0, Math.round(minutes ? p.tickMajorHeightM : p.tickMajorHeightH));
  const wMin = Math.max(1, Math.round(minutes ? p.tickMinorWidthM : p.tickMinorWidthH));
  const wMaj = Math.max(1, Math.round(minutes ? p.tickMajorWidthM : p.tickMajorWidthH));
  const br = p.brightness * p.tickBright;
  const cMin = q(scale(hexToRgb(minutes ? p.tickColorM : p.tickColorH), br));
  const cMaj = q(scale(hexToRgb(minutes ? p.tickMajorColorM : p.tickMajorColorH), br));
  const pos = Math.round(minutes ? p.tickPosM : p.tickPosH);
  const warpedRange = (sourceRows: Int16Array, sourceA: number, sourceB: number): [number, number] => {
    let a = H, b = -1;
    for (let ry = 0; ry < H; ry++) if (sourceRows[ry] >= sourceA && sourceRows[ry] <= sourceB) {
      a = Math.min(a, ry); b = Math.max(b, ry);
    }
    return [a, b];
  };
  const emboss = Math.max(0, Math.min(1, p.tickEmboss));
  const drawSegment = (x0: number, w: number, c: number, range: [number, number], top: boolean, k: number): void => {
    if (range[1] < 0) return;
    const dx = dxFull * k, dy = dyFull * k;
    const outer = top ? 0 : H - 1;
    const inner = Math.max(0, Math.min(H - 1, top ? range[1] : range[0]));
    const dir = inner >= outer ? 1 : -1;
    const radius = Math.max(1, (H - 1) / 2), centre = (H - 1) / 2;
    // x stays fractional (the refraction shift scaled by the depth), rows are whole: a row of the tick is drawn at
    // its subpixel position, its edge columns antialiased (1/256 steps), so a slanted tick is a smooth line, not a
    // staircase of whole-pixel jumps (most visible on an upscaled canvas). Mirrored by the firmware drawTicks.
    const point = (baseY: number): [number, number] => {
      const qy = (baseY - centre) / radius;
      const depth = Math.sqrt(Math.max(0, 1 - qy * qy));
      return [x0 + Math.fround(dx * depth), baseY + Math.round(dy * depth)];
    };
    const plot = (xf: number, ry: number): void => {
      if (ry < 0 || ry >= H) return;
      const x = Math.floor(xf), fT = Math.round((xf - x) * 256);
      if (fT === 0 || fT === 256) {
        const xi = x + (fT >> 8);
        if (emboss > 0) { mark(xi - 1, y0 + ry, c, emboss, 1); mark(xi + w, y0 + ry, c, emboss, -1); }
        for (let k = 0; k < w; k++) mark(xi + k, y0 + ry, c);
        return;
      }
      const a = (256 - fT) / 256, b = fT / 256;   // left / right share of the edge columns
      if (emboss > 0) {
        mark(x - 1, y0 + ry, c, emboss * a, 1); mark(x, y0 + ry, c, emboss * b, 1);
        mark(x + w, y0 + ry, c, emboss * a, -1); mark(x + w + 1, y0 + ry, c, emboss * b, -1);
      }
      mark(x, y0 + ry, c, a);
      for (let k = 1; k < w; k++) mark(x + k, y0 + ry, c);
      mark(x + w, y0 + ry, c, b);
    };
    let [px0, py0] = point(outer); plot(px0, py0);
    if (outer === inner) return;
    for (let baseY = outer + dir; ; baseY += dir) {
      const [px1, py1] = point(baseY);
      const n = Math.max(1, Math.abs(py1 - py0));
      for (let j = 1; j <= n; j++) plot(n === 1 ? px1 : Math.fround(px0 + Math.fround((px1 - px0) * j / n)), n === 1 ? py1 : Math.round(py0 + (py1 - py0) * j / n));
      px0 = px1; py0 = py1;
      if (baseY === inner) break;
    }
  };
  const flip = scaleFlip(p);
  const edgeMin = follow ? follow.edge(hMin) : 0, edgeMaj = follow ? follow.edge(hMaj) : 0;
  for (let i = step; i < ticksN; i += step) {
    const xc = flip ? L - Math.round((i * L) / ticksN) : Math.round((i * L) / ticksN);
    const major = majorEvery > 0 && i % majorEvery === 0;
    const h = major ? hMaj : hMin; if (h <= 0) continue;
    const w = major ? wMaj : wMin, x0 = xc - ((w - 1) >> 1), c = major ? cMaj : cMin;
    const share = edges ? shareAt(xc) : 256;
    let rows = share === 256 ? wetRows : dryRows;
    if (share > 0 && share < 256) { for (let ry = 0; ry < H; ry++) tickRows[ry] = blendRow(dryRows[ry], wetRows[ry], share); rows = tickRows; }
    const k = share / 256;   // air refracts nothing: the parallax grows with the wet share
    const wet = follow !== null && share > 0, edge = major ? edgeMaj : edgeMin;
    const topRange = wet ? tickFollowRange(follow, H, edge, share, true) : warpedRange(rows, 0, h - 1);
    const botRange = wet ? tickFollowRange(follow, H, edge, share, false) : warpedRange(rows, H - h, H - 1);
    if (pos !== 1) drawSegment(x0, w, c, topRange, true, k);
    if (pos !== 0) drawSegment(x0, w, c, botRange, false, k);
  }
}

/** px in the liquid frame; v = size/speed factor, 0 = an idle slot (a spring's pool: not drawn, not moved);
 *  life ≠ 0 = parked under a surface, |life| s left before it
 *  pops: > 0 under the time edge, < 0 under the home edge of a free slug; z = depth in the bore (0 = front
 *  wall, 1 = back wall), drawn at spawn and every recycle (never on a move, park or release). */
export interface Fizz { x: number; y: number; v: number; life: number; z: number; }
export const fizz: Fizz[][] = [[], []];
// Bubbles per tube (firmware MAX_FIZZ): the sliders' worst case, fizzCount 120 doubled by full agitation.
// A count pushed past the sliders is capped and reported, not silently dropped.
const FIZZ_MAX = 240;
let fizzOverflowPeak = 0;
const foamOrder = new Int16Array(FIZZ_MAX);   // settleFoam's sweep order (parked, front first)
const fizzLen = [0, 0];   // liquid length px per tube, set by drawTube
/** Per tube, set by drawTube: the surface front per row in the liquid frame — the profile (edges − xs,
 *  edgesL − xs), which is also the inner rim of a concave surface band: foam floats on the liquid there,
 *  not out on the band that climbs the wall to the contact ring — for the time edge and the home edge,
 *  and which of them is exposed (bit 1 = time edge short of the far end, bit 2 =
 *  home edge of a free slug off the near end). Fizz parks only in an exposed surface. */
const fizzSurf: Float32Array[] = [new Float32Array(0), new Float32Array(0)];
const fizzSurfL: Float32Array[] = [new Float32Array(0), new Float32Array(0)];
/** Last drawn rear-mark column bounds per tube (panel frame) — read by the regression checks. */
export const markBounds: Edges[] = [{ lo: new Float32Array(0), hi: new Float32Array(0) }, { lo: new Float32Array(0), hi: new Float32Array(0) }];
const fizzExposed = [0, 0];
// Foam constants (mirrored in firmware/src/render.cpp): the pop's swell + fade time, slide speed along the
// surface as a fraction of fizzSpeed per px/row of meniscus slope, lag rate behind an advancing surface
// (also how a caught bubble glides onto the surface), how far short of the profile a free bubble's rim is
// caught (or recycled, at a surface foam can't form on), and how much of a concave surface band veils the
// foam behind it at the profile (the liquid wedge climbing the front glass, thinning to nothing at the ring).
// FOAM_RELAX: packing sweeps per step.
const FOAM_POP_T = 0.3, FOAM_SLIDE = 0.5, FOAM_FOLLOW = 6, FOAM_CATCH = 2 * PX_SCALE, FOAM_VEIL = 0.7, FOAM_RELAX = 3;
// A spring is fixed in the tube (mirrored in firmware): `fizzSourceX` of the column as it sits at home. While the
// liquid covers it, it takes every birth, whatever the tilt; a free slug sliding off it leaves it dry, and every
// birth goes scattered. Covered again, it takes its births back over SPRING_BACK s (a share ramping to 0), so a
// slug bouncing at home does not flip the stream. Births only: nothing in flight moves.
// It emits at a steady cadence, `fizzSourceRate` bubbles/s, into idle slots of the pool: how many are in flight
// follows from their path, so a tilt that shortens it shows fewer — up to the tube's `fizzCount` share (fizzWant),
// where a birth waits for a bubble to leave: a tilt that keeps the stream in the liquid thins it out.
// Glass holds the gas a spring's rise carries into it (with `fizzFoamLife` > 0), so the stream bends along the
// glass instead of ending there: at the bore wall a bubble stays against the glass and slides along it with the
// along drive (one pace for all, so a train keeps its gaps) until it lets go — at random, on average after
// `fizzFoamLife` s, sooner when shaken — and slips behind the wall band; one arriving onto a bubble already held
// there coalesces into it. At a closed end (the tube's end glass, not a surface) it parks as foam does, slides
// along the glass with the across rise and pops after its life.
const SPRING_BACK = 3;
/** Per tube: px the liquid frame sits off its home (a free slug that slid away; 0 pinned), set by drawTube. */
const fizzShift = [0, 0];
/** Per tube: share of spring births born scattered instead (0 = all at the spring), advanced by stepFizz. */
const springScatter = [0, 0];
/** Per tube: bubbles the spring may release now (its cadence accrued). */
const springClock = [0, 0];
/** This spring birth in tube i comes from the spring itself (covered by the liquid), not scattered. */
const springBirth = (i: number): boolean => springScatter[i] <= 0 || Math.random() >= springScatter[i];
/** Half-height of the surface blick's row tent as a fraction of the tube height (firmware BLICK_H). */
const BLICK_H = 0.18;

/** Bubbles a column of `len` px holds: `fizzCount` is the count for a full tube; density stays constant as the
 *  column shortens. Shake nucleates bubbles: up to 2x with agitation, shrinking back as it decays. Past the
 *  fixed pool it is capped and reported. */
function fizzWant(p: Params, len: number, agitation: number): number {
  let want = Math.max(0, Math.floor(p.fizzCount * (len / TUBE_LENGTH_PX) * (1 + (agitation < 0.05 ? 0 : agitation))));
  if (want > FIZZ_MAX) {
    if (want > fizzOverflowPeak) { fizzOverflowPeak = want; console.warn(`fizz pool: ${want} bubbles requested, ${FIZZ_MAX} fit`); }
    want = FIZZ_MAX;
  }
  return want;
}
/** A spring fills its pool at its cadence instead, up to the same count (stepFizz). */
function ensureFizz(i: number, p: Params, len: number, agitation = 0): void {
  const arr = fizz[i];
  fizzLen[i] = len;
  if (p.fizzSource === 1) return;
  const want = fizzWant(p, len, agitation);
  const H = tubeLayout(p).H;
  while (arr.length < want) {
    const v = 0.5 + Math.random(); arr.push({ x: Math.random() * len, y: fizzSpawnY(p, H, v), v, life: 0, z: Math.random() });
  }
  if (arr.length > want) arr.length = want;
}
/** Bubble radius px for size factor `v`. */
const fizzR = (p: Params, v: number): number => p.fizzSize / 2 * (1 + (v - 1) * p.fizzSizeVar);
/** Glass wall band px per side (see buildPalette `wallU`); 0 when the band is off. */
const fizzWall = (p: Params): number => p.glassWall > 0 ? Math.max(1, p.glassWall) : 0;
/** Row where a bubble of size `v` is fully behind the wall band (respawn/turnaround bound); the old
 *  3 px margin without a band. */
function fizzHideY(p: Params, v: number): number {
  const w = fizzWall(p);
  return w > 0 ? Math.max(0, w - fizzR(p, v)) : 3;
}
/** Random row with the whole bubble in the bore (fully visible), so bubbles never sit half behind the wall. */
function fizzSpawnY(p: Params, H: number, v: number): number {
  const lo = fizzWall(p) + fizzR(p, v), hi = H - lo;
  return hi <= lo ? H / 2 : lo + Math.random() * (hi - lo);
}
/** Spring (`fizzSource` 1): a new size and depth, born at the spring — `fizzSourceY` across the bore (whole
 *  disc inside), `fizzSourceX` along that row's liquid (between the surfaces, as a respawn) as it sits at home,
 *  so `shift` px back in a slug that slid away — each axis jittered by up to ±`fizzSourceSpread` px, kept in
 *  the liquid. */
function springSpawn(f: Fizz, p: Params, H: number, surf: Float32Array, surfL: Float32Array, shift: number): void {
  f.v = 0.5 + Math.random(); f.z = Math.random(); f.life = 0;
  const r = fizzR(p, f.v), s = p.fizzSourceSpread, lo = fizzWall(p) + r, hi = H - lo;
  f.y = hi <= lo ? H / 2 : Math.max(lo, Math.min(hi, lo + p.fizzSourceY * (hi - lo) + (2 * Math.random() - 1) * s));
  const xl = -discFit(surfL, H, f.y, r, -1) + FOAM_CATCH, xh = discFit(surf, H, f.y, r, 1) - FOAM_CATCH;
  f.x = xh <= xl ? (xl + xh) / 2 : Math.max(xl, Math.min(xh, xl + p.fizzSourceX * (xh - xl) - shift + (2 * Math.random() - 1) * s));
}
/** Fizz rises against the in-plane gravity (`along`, `across`) at `fizzSpeed` px/s on both axes:
 *  along-tilt drives it toward the high end (`fizzDriftGain`), across-tilt toward the high edge (`fizzAcrossGain`).
 *  Out-of-plane gravity (face up) reads as a slow screen-up rise (`fizzFlatRise`: -y, or +x on a vertical watch) plus a drift toward the
 *  exposed surface (`fizzEdgeRise`: the time edge, or the home edge of a free slug whose time edge sits
 *  against the far end); shake speeds everything up.
 *  A bubble leaving the liquid on either axis respawns at the low side of that axis — except at an exposed
 *  surface the rise points at: with `fizzFoamLife` > 0 it parks in it (see settleFoam) and pops later.
 *  A spring (`fizzSource` 1) takes every birth instead, at its cadence (springClock), so the bubbles rise as a
 *  stream; a bubble leaving or popping frees its slot. A slug sliding off the spring leaves it dry, and its births
 *  go scattered instead (springScatter). The glass holds a spring's bubbles (see SPRING_BACK). */
export function stepFizz(p: Params, dt: number, along = 0, across = 0, agitation = 0): void {
  if (mirrored(p)) along = -along; // fizz lives in the mirrored liquid frame (see drawTube)
  const speed = p.fizzSpeed * (1 + 3 * agitation);
  const up = Math.sqrt(Math.max(0, 1 - along * along - across * across));
  const a = Math.max(-1, Math.min(1, across * p.fizzAcrossGain)), al = Math.max(-1, Math.min(1, along * p.fizzDriftGain));
  // Vertical watch: the viewer's up is the tube's top end (+x), so the face-up rise goes along the tube, not across it.
  const flat = up * p.fizzFlatRise, V = p.vertical;
  const vy = -speed * ((V ? 0 : (1 - Math.abs(a)) * flat) + a);   // screen up = -y
  const vxTilt = -speed * (al - (V ? (1 - Math.abs(al)) * flat : 0));
  const H = tubeLayout(p).H, spring = p.fizzSource === 1, wall = fizzWall(p);
  const hold = spring && p.fizzFoamLife > 0 && vy !== 0;   // the bore wall the rise points at holds the stream
  const letGo = hold ? dt * (1 + 3 * agitation) / p.fizzFoamLife : 0;   // per-step chance a held bubble lets go
  for (let i = 0; i < 2; i++) {
    const len = fizzLen[i], surf = fizzSurf[i], surfL = fizzSurfL[i], exposed = fizzExposed[i];
    if (surf.length !== H || len <= 0) continue;   // no surfaces for this height yet (drawTube publishes them)
    // The spring point: a mean bubble's centre as springSpawn places it (row sy, in the span sxl..sxh), dry once
    // the slug slides it past its home surface.
    const sr = fizzR(p, 1), slo = fizzWall(p) + sr, sy = H - slo <= slo ? H / 2 : slo + p.fizzSourceY * (H - 2 * slo);
    const sxl = spring ? -discFit(surfL, H, sy, sr, -1) + FOAM_CATCH : 0, sxh = spring ? discFit(surf, H, sy, sr, 1) - FOAM_CATCH : 0;
    const sx = sxl + p.fizzSourceX * Math.max(0, sxh - sxl) - fizzShift[i];
    if (spring) springScatter[i] = sx <= -foamFront(surfL, H, sy, -1) ? 1 : Math.max(0, springScatter[i] - dt / SPRING_BACK);
    const dir = exposed & 1 ? 1 : exposed & 2 ? -1 : 0;   // +x = the time edge
    const vx = vxTilt + speed * up * p.fizzEdgeRise * dir;
    // The surface the rise heads for, if exposed and foam is on: +1 time edge, -1 home edge, 0 none; a spring's
    // foam also parks against a closed end (glass).
    const side = p.fizzFoamLife <= 0 ? 0 : vx > 0 && (spring || exposed & 1) ? 1 : vx < 0 && (spring || exposed & 2) ? -1 : 0;
    const glass = side !== 0 && !(exposed & (side > 0 ? 1 : 2));
    // Respawn at a random x in the liquid of the new row, or just inside the edge the flow comes from.
    const respawn = (f: Fizz, at: number): void => {
      const r = fizzR(p, f.v), lo = -discFit(surfL, H, f.y, r, -1) + FOAM_CATCH, hi = discFit(surf, H, f.y, r, 1) - FOAM_CATCH;
      f.x = hi <= lo ? (lo + hi) / 2 : at < 0 ? lo + Math.random() * (hi - lo) : at > 0 ? lo : hi;
    };
    // Scattered birth: a new size and depth anywhere in the liquid.
    const scatter = (f: Fizz): void => { f.life = 0; f.v = 0.5 + Math.random(); f.y = fizzSpawnY(p, H, f.v); respawn(f, -1); f.z = Math.random(); };
    // A spring's bubble leaving or popping: its slot goes idle until the cadence fills it.
    const free = (f: Fizz): void => { f.v = 0; f.life = 0; };
    // On the bore wall the rise points at (row wallY: the disc touching the glass), held by it.
    const wallY = (g: Fizz): number => vy < 0 ? wall + fizzR(p, g.v) : H - wall - fizzR(p, g.v);
    const held = (g: Fizz): boolean => g.v !== 0 && g.life === 0 && Math.abs(g.y - wallY(g)) < 1e-3;
    for (const f of fizz[i]) {
      if (f.v === 0) { if (!spring) scatter(f); continue; }   // idle: the spring's cadence fills it below
      if (f.life !== 0) {
        const was = f.life > 0 ? 1 : -1;
        if (was !== side) {   // the surface tilted away: the foam releases into the flow, from where it is drawn
          f.x = was * Math.min(was * f.x, foamFront(was > 0 ? surf : surfL, H, f.y, was));
          f.life = 0;
        }
        else {
          const left = Math.abs(f.life) - dt * (1 + 3 * agitation);   // shaking pops the foam
          if (left > 0) f.life = side * left;
          else if (spring) free(f);
          else scatter(f);
          continue;
        }
      }
      const r = fizzR(p, f.v), wlo = wall + r, whi = H - wlo, grip = hold && whi > wlo;
      if (grip && held(f) && Math.random() >= letGo) f.x += vx * dt;   // held by the glass: slides along it
      else {
        const inBore = f.y > wlo && f.y < whi;   // not one letting go, already on the glass row
        f.y += vy * f.v * dt;
        f.x += vx * f.v * dt;
        if (grip && inBore && (vy < 0 ? f.y < wlo : f.y > whi)) {   // carried into the glass: held, or coalesces into a held bubble
          f.y = vy < 0 ? wlo : whi;
          let merge = false;
          for (const g of fizz[i]) {
            if (g === f || !held(g)) continue;
            const m = r + fizzR(p, g.v) + 0.5, dx = g.x - f.x, dy = g.y - f.y;
            if (dx * dx + dy * dy < m * m) { merge = true; break; }
          }
          if (merge) { free(f); continue; }
        }
      }
      // Vertical exit: once fully behind the wall band, respawn fully behind the opposite one and rise out of it.
      const hide = fizzHideY(p, f.v);
      if (f.y < hide || f.y >= H - hide) {
        if (spring) free(f);
        else { f.v = 0.5 + Math.random(); const h = fizzHideY(p, f.v); f.y = vy <= 0 ? H - h : h; respawn(f, -1); f.z = Math.random(); }
        continue;
      }
      // The flow carrying its rim within FOAM_CATCH of a surface (the whole disc, so big bubbles never poke
      // through), or into the foam already there (it joins at the back, not rising through it): at the
      // surface the rise heads for it parks for a random life around fizzFoamLife and glides onto it
      // (settleFoam); anywhere else it is recycled at the side the flow comes from. A bubble the flow does
      // not carry into a surface only rides it, centre held inside — released foam, one moving along a
      // curved meniscus — and floats half out like the foam until it drifts back in.
      const outR = vx > 0 && f.x > discFit(surf, H, f.y, r, 1) - FOAM_CATCH, outL = vx < 0 && -f.x > discFit(surfL, H, f.y, r, -1) - FOAM_CATCH;
      if ((side > 0 && outR) || (side < 0 && outL) || (side !== 0 && touchesFoam(fizz[i], f, r, p, side))) f.life = side * p.fizzFoamLife * (0.5 + Math.random());
      else if ((outR || outL) && spring) free(f);
      else if (outR || outL) { f.v = 0.5 + Math.random(); f.y = fizzSpawnY(p, H, f.v); respawn(f, vx < 0 ? 0 : 1); f.z = Math.random(); }
      else f.x = Math.max(-foamFront(surfL, H, f.y, -1), Math.min(foamFront(surf, H, f.y, 1), f.x));
    }
    if (spring) {
      // Cadence: fizzSourceRate bubbles/s (shaking nucleates up to twice as many), each into an idle slot (the
      // first, else a new one); idle slots at the end are dropped, so the loops stay as short as the bubbles
      // in flight. The tube holds at most its fizzCount share (fizzWant, foam included): at it a birth waits for
      // a bubble to leave, keeping one birth of credit and no more, so a stream the tilt keeps in the liquid (a
      // drift that stalls or keeps reversing) thins out instead of filling the pool, and no burst follows.
      // Bubbles already over a count that dropped (a shorter column) live on.
      const arr = fizz[i];
      const cap = fizzWant(p, len, agitation);   // <= FIZZ_MAX
      let live = 0;
      for (const f of arr) if (f.v !== 0) live++;
      springClock[i] += Math.max(0, p.fizzSourceRate) * (1 + (agitation < 0.05 ? 0 : agitation)) * dt;
      let slot = 0;
      while (springClock[i] >= 1) {
        if (live >= cap) { springClock[i] = 1; break; }
        while (slot < arr.length && arr[slot].v !== 0) slot++;
        if (slot === arr.length) arr.push({ x: 0, y: 0, v: 0, life: 0, z: 0 });
        if (springBirth(i)) springSpawn(arr[slot], p, H, surf, surfL, fizzShift[i]); else scatter(arr[slot]);
        springClock[i] -= 1; live++;
      }
      while (arr.length > 0 && arr[arr.length - 1].v === 0) arr.pop();
    }
    if (side !== 0) settleFoam(fizz[i], p, H, speed, side > 0 ? surf : surfL, side, dt, glass ? vy : NaN);
  }
}
/** Furthest centre (in u = side · x) a bubble of radius r at row y can take with its whole disc inside the
 *  surface `surf` (liquid frame): the tightest row of the disc. */
function discFit(surf: Float32Array, H: number, y: number, r: number, side: number): number {
  const a = Math.max(0, Math.ceil(y - r)), b = Math.min(H - 1, Math.floor(y + r));
  if (a > b) return foamFront(surf, H, y, side) - r;
  let u = Infinity;
  for (let iy = a; iy <= b; iy++) { const dy = iy - y; u = Math.min(u, side * surf[iy] - Math.sqrt(Math.max(0, r * r - dy * dy))); }
  return u;
}
/** A free bubble f (radius r) touching foam parked on `side` — not foam on the other edge, nor foam this
 *  tick is still to release (its life still carries the old side). */
function touchesFoam(arr: Fizz[], f: Fizz, r: number, p: Params, side: number): boolean {
  for (const g of arr) {
    if (g.life * side <= 0) continue;
    const m = r + fizzR(p, g.v) + 0.5, dx = g.x - f.x, dy = g.y - f.y;
    if (Math.abs(dx) < m && Math.abs(dy) < m && dx * dx + dy * dy < m * m) return true;
  }
  return false;
}
/** Surface front `surf` (liquid frame) at float row y, in u = side · x: where a parked bubble's centre sits. */
function foamFront(surf: Float32Array, H: number, y: number, side: number): number {
  const yc = Math.max(0, Math.min(H - 1, y)), i = Math.floor(yc), j = Math.min(H - 1, i + 1);
  return side * (surf[i] + (surf[j] - surf[i]) * (yc - i));
}
/** Parked bubbles: each sits centred on the surface front — foam floats half out of the liquid — lagging
 *  behind an advance (and gliding on after being caught), pushed back by a recession; slides along the
 *  meniscus toward the higher contact line — the corners, where the foam ring forms — and packs: late
 *  arrivals fill the meniscus from its front backward. Pairs among the parked only.
 *  Against a closed end (`glassVy` a number: the across rise px/s) the whole disc stays inside and the
 *  bubbles slide along the glass with the rise instead.
 *  Works in u = side · x, so the home edge (side -1) is the time edge mirrored. */
function settleFoam(arr: Fizz[], p: Params, H: number, speed: number, surf: Float32Array, side: number, dt: number, glassVy: number): void {
  const wall = fizzWall(p), follow = Math.min(1, FOAM_FOLLOW * dt), glass = !Number.isNaN(glassVy);
  const front = (y: number, r: number): number => glass ? discFit(surf, H, y, r, side) : foamFront(surf, H, y, side);
  // In the bore and not past the front of its row.
  const place = (f: Fizz, u: number, y: number): void => {
    const r = fizzR(p, f.v), lo = wall + r, hi = H - lo;
    f.y = hi <= lo ? H / 2 : Math.max(lo, Math.min(hi, y));
    f.x = side * Math.min(u, front(f.y, r));
  };
  for (const f of arr) {
    if (f.life === 0) continue;
    const r = fizzR(p, f.v), fy = Math.max(0, Math.min(H - 1, Math.round(f.y)));
    const tu = front(f.y, r);
    let u = side * f.x;
    u = u < tu ? u + Math.min((tu - u) * follow, speed * dt) : tu;   // buoyancy: no faster than the rise
    const slope = side * (surf[Math.min(H - 1, fy + 1)] - surf[Math.max(0, fy - 1)]) / 2;   // px per row, + = surface leads toward +y
    let slide = glass ? glassVy * dt : FOAM_SLIDE * speed * Math.max(-1, Math.min(1, 2 * slope)) * dt;
    for (const g of arr) {   // touching a neighbour on the slide side: line up along the surface
      if (g === f || g.life === 0 || slide * (g.y - f.y) <= 0) continue;
      const m = r + fizzR(p, g.v) + 0.5, du = side * g.x - u, dy = g.y - f.y;
      if (du * du + dy * dy < m * m) { slide = 0; break; }
    }
    place(f, u, f.y + slide);
  }
  // Pack: pairwise relaxation, positions carried over between ticks, swept front to back (parked sorted
  // by u, the front-most first). An overlapping pair is pushed apart along the line between them, then
  // clamped to the bore and the front; whatever overlap the clamps leave (both pinned: at the front, at a
  // wall) the rear one takes by stepping back, where nothing stops it — into bubbles the sweep has yet to
  // visit, so one sweep settles most of the layers and they grow backward.
  let n = 0;
  for (let i = 0; i < arr.length; i++) if (arr[i].life !== 0) foamOrder[n++] = i;
  for (let it = 0; it < FOAM_RELAX; it++) {
    for (let a = 1; a < n; a++) {   // insertion sort: nearly sorted from the last step
      const k = foamOrder[a], uk = side * arr[k].x; let b = a - 1;
      while (b >= 0 && side * arr[foamOrder[b]].x < uk) { foamOrder[b + 1] = foamOrder[b]; b--; }
      foamOrder[b + 1] = k;
    }
    for (let a = 0; a < n; a++) {
      const f = arr[foamOrder[a]], rf = fizzR(p, f.v);
      for (let b = a + 1; b < n; b++) {
        const g = arr[foamOrder[b]];
        const m = rf + fizzR(p, g.v) + 0.5;
        let du = side * (g.x - f.x), dy = g.y - f.y;
        if (Math.abs(du) >= m || Math.abs(dy) >= m || du * du + dy * dy >= m * m) continue;
        const d = Math.sqrt(du * du + dy * dy), k = (m - d) / 2;
        const nu = d > 1e-4 ? du / d : -1, ny = d > 1e-4 ? dy / d : 0;   // coincident: g (later in the sweep) steps back
        place(f, side * f.x - k * nu, f.y - k * ny);
        place(g, side * g.x + k * nu, g.y + k * ny);
        du = side * (g.x - f.x); dy = g.y - f.y;
        if (du * du + dy * dy >= m * m) continue;
        const [front, rear] = du > 0 ? [g, f] : [f, g];
        place(rear, side * front.x - Math.sqrt(Math.max(0, m * m - dy * dy)), rear.y);
      }
    }
  }
}

/** Row coordinate -1..1 seen through the physical glass: the cap profile is evaluated where the
 *  row will appear, so the rod's vertical magnification does not flatten it (same warp as topLens). */
function lensRow(d: number, p: Params): number {
  const lens = Math.max(-1, Math.min(1, p.meniscusLens)), strength = Math.abs(lens);
  const signedCurve = lens < 0 ? -Math.max(-3, Math.min(3, p.lensCurve)) : Math.max(-3, Math.min(3, p.lensCurve));
  if (strength === 0 || signedCurve === 0) return d;
  const exponent = signedCurve > 0 ? 1 + signedCurve * 2 : 1 / (1 - signedCurve * 2);
  const u = Math.abs(d);
  return Math.sign(d) * ((1 - strength) * u + strength * Math.pow(u, exponent));
}
// ---------------------------------------------------------------------------
// Meniscus: contact-angle model, the same for both ends of a slug.
// Each end is a spherical cap set by its contact angle θ (capillary-dominated baseline: the bore is
// ~2–3 mm, the capillary length ~2–3 mm). θ comes from the liquid's static angle and
//  · the hydrostatic head along the slug (along-tilt): the lower end carries more pressure, so its
//    curvature drops (θ up), the upper end's rises — held within the hysteresis band [θR, θA];
//  · the contact line's history: the line is pinned, so the column's own travel moves the surface
//    centre against the held wall ring and θ with it, until θ reaches θA / θR and the line is dragged
//    (TubeState.pin* / lineV*, stepped in physics) — tremor-sized back-and-forth never moves the ring;
//  · the dragged line's speed: Cox–Voinov moves it past θA / θR, θ³ = θ₀³ ± G·v (a fast receding
//    line reaches θ = 0 and leaves its film behind).
// Across-tilt sags the cap onto the low wall in proportion to the Bond number (R / capillary
// length)²; the flick/slide wobble (TubeState.cap) is the surface's pinned-line mode on top.
// ---------------------------------------------------------------------------
const MENISCUS_SAG_K = 1;      // across sag per unit Bond number and g

/** One end's meniscus for this frame. `cosT` = cos θ (> 0 concave), `h` = px its contact ring
 *  leads the surface centre (R(1 − sin θ)/cos θ: R at θ = 0, 0 at 90°, −R at 180°), `asym` =
 *  across sag, `cap` = wobble (px the centre leads the ring, the edge's own +x sense). */
export interface CapShape { cosT: number; h: number; asym: number; cap: number }
/** `len` = column length px, `tilt` = along follower into this end (TubeState.edgeLight, edge's
 *  own sense), `side` = across follower, `pin` = px of surface-centre travel against the held ring and
 *  `lineV` = dragged line speed outward (advancing > 0), px/s (TubeState.pin* / lineV*). */
export function capShape(p: Params, len = 0, tilt = 0, side = 0, cap = 0, pin = 0, lineV = 0): CapShape {
  const c = contactLeads(p, len, tilt), R = c.R, rad = Math.PI / 180;
  // the held ring's lead inside the hysteresis band, back to its angle (lead = R·tan(π/4 − θ/2))
  let th = Math.PI / 2 - 2 * Math.atan(Math.max(c.adv, Math.min(c.rec, c.rest - pin)) / R);
  const dyn = Math.max(0, p.contactDyn) * rad, g = dyn * dyn * dyn / FILM_FULL_PX_S;   // Cox–Voinov
  th = Math.cbrt(Math.max(0, Math.min(Math.PI ** 3, th * th * th + g * lineV)));
  const cosT = Math.cos(th), sinT = Math.sin(th);
  // Sag: side > 0 (top up) moves the bottom (d = +1) contact line out, whether the cap is concave or convex
  const lc = Math.max(0.1, p.capLength), Rmm = R * MM_PER_PX;
  const asym = MENISCUS_SAG_K * (Rmm / lc) ** 2 * side * Math.sign(cosT);
  return { cosT, h: R * cosT / (1 + sinT), asym, cap };
}
/** Row coordinate -1..1 across the bore (boreR), as seen through the glass. The thick wall smears the
 *  bore's near-wall fringe over the wall band: from a0 = max(0, 2 − D) (D = outer / bore radius) the
 *  row eases C1 onto ±1 at the outer edge, u = 1 − δ·g(t/τ) (t = D − a, τ = D − a0, δ = 1 − a0,
 *  g(1) = 1, g'(1) = n = τ/δ). g has no s² term — g = (4 − n)s³ + (n − 3)s⁴ up to n = 4 (monotone),
 *  s^n past it — so 1 − u = o(t²) and even a 0° / 180° cap, whose √(1 − u²) would turn a quadratic
 *  ease back into a finite slope, meets the edge flat. No flat rows inside the band, no cut at the ring. */
function boreRow(ry: number, p: Params): number {
  const yc = (tubeLayout(p).H - 1) / 2, a = Math.abs(ry - yc) / boreR(p), D = yc / boreR(p);
  const a0 = Math.max(0, 2 - D), dl = 1 - a0, tau = D - a0, n = tau / dl;
  let u = D <= 1 ? Math.min(1, a) : a;
  if (D > 1 && a > a0) {
    const s = Math.max(0, D - a) / tau, s3 = s * s * s;
    u = 1 - dl * (n <= 4 ? (4 - n) * s3 + (n - 3) * s3 * s : Math.pow(s, n));
  }
  return lensRow(ry < yc ? -u : u, p);
}
/** Cap profile: px the surface at tube-row `ry` leads the surface centre, along +x: the spherical
 *  cap of radius R / cos θ (R = boreR) through the ring (stable form, exact parabola as θ → 90°), sagged
 *  by the across tilt (clamped at 0: the sag never turns the curvature over), minus the wobble mode u². */
function edgeCap(ry: number, p: Params, c: CapShape): number {
  const R = boreR(p);
  const d = boreRow(ry, p), u2 = d * d;   // -1..1, as seen through the glass
  const sphere = c.cosT * R * u2 / (1 + Math.sqrt(Math.max(0, 1 - c.cosT * c.cosT * u2)));
  return sphere * Math.max(0, 1 + c.asym * d) - c.cap * u2;
}
/** Wall-ring lead: px the contact ring — the contact line all round the bore, edgeCap at u = 1 —
 *  leads the surface centre, with the across sag interpolated by the row's d. Seen side-on the
 *  ring projects to one x per row; the visible surface at a row is the lens between edgeCap (the
 *  mid-depth section) and this. Meets edgeCap at the wall rows, so the lens closes there. */
function wallCap(ry: number, p: Params, c: CapShape): number {
  return c.h * Math.max(0, 1 + c.asym * boreRow(ry, p)) - c.cap;
}
/** Meniscus amplitude limiter for one end: its cap may not reach past half a column `len` px long
 *  (a short slug is a bead, not two crossing scoops). 1 for any column longer than the features. */
export function capScale(len: number, c: CapShape): number {
  return Math.min(1, Math.max(0, len) / 2 / Math.max(1, Math.abs(c.h) * (1 + Math.abs(c.asym)) + Math.abs(c.cap)));
}
/** In-plane skew of the two ends, px per row: [time edge, home edge] (TubeState.angle). The liquid lies on
 *  the low wall at both ends, so the home end leans the other way: a slug off its home end is a trapezoid,
 *  not a parallelogram. There (`xs` px off the end cap, the ramp edgeXL flattens by) the two leans share what
 *  the column (`gap` px between the edge centres, slosh included) has left past both caps' reach into it at a
 *  wall row, so the lean never makes the ends of a short slug cross — one budget for the pair: the caps are
 *  not alike under tilt. A column on its end cap leans freely (the cap clips it); lifting off, the part of that
 *  free lean still in the time edge comes out of the same budget. */
export function edgeSkews(angleDeg: number, H: number, gap: number, xs: number, cR: CapShape, kR: number, cL: CapShape, kL: number): [number, number] {
  const tanA = Math.tan((angleDeg * Math.PI) / 180), yc = Math.max(1, (H - 1) / 2), off = Math.max(0, Math.min(1, xs / 8));
  const reach = (c: CapShape, k: number): number => k * Math.max(0, Math.abs(c.h * c.asym) + Math.abs(c.cap) - c.h);
  const lim = Math.max(0, gap - reach(cR, kR) - off * reach(cL, kL) - (1 - off) * Math.abs(tanA) * yc) / (2 * yc);
  const lean = Math.max(-lim, Math.min(lim, tanA));
  return [tanA + off * (lean - tanA), -lean];
}
/** Fill-edge x for tube-row `ry` (0..H-1), given edge centre `xe`, in-plane skew `tanA` (px per row,
 *  edgeSkews) and this end's cap. */
export function edgeX(ry: number, xe: number, tanA: number, p: Params, c = capShape(p), k = 1): number {
  const yc = (tubeLayout(p).H - 1) / 2;
  return xe + tanA * (ry - yc) + k * edgeCap(ry, p, c);
}
/** Home-end edge of a free slug whose centre sits at `xs`: the mirror image of edgeX (its cap takes
 *  the mirrored forcing, the centre leads in -x; `tanA` = the home end's own skew, edgeSkews). Flattens
 *  onto the end cap over the last 8 px. */
export function edgeXL(ry: number, xs: number, tanA: number, p: Params, c = capShape(p), k = 1): number {
  const yc = (tubeLayout(p).H - 1) / 2;
  return xs + Math.min(1, xs / 8) * (tanA * (ry - yc) - k * edgeCap(ry, p, c));
}
/** Wall-ring x of the time edge / home edge: edgeX / edgeXL with wallCap in place of edgeCap. */
function wallX(ry: number, xe: number, tanA: number, p: Params, c: CapShape, k: number): number {
  const yc = (tubeLayout(p).H - 1) / 2;
  return xe + tanA * (ry - yc) + k * wallCap(ry, p, c);
}
function wallXL(ry: number, xs: number, tanA: number, p: Params, c: CapShape, k: number): number {
  const yc = (tubeLayout(p).H - 1) / 2;
  return xs + Math.min(1, xs / 8) * (tanA * (ry - yc) - k * wallCap(ry, p, c));
}

/** Stable per-column streak factor 0.82..1 for the dried traces — a subtle texture, not stripes.
 *  The integer hash must match firmware/src/render.cpp exactly, so the two smears show the same
 *  striations. */
function traceStreak(n: number): number {
  let h = (Math.imul(n, 2654435761) + 0x9e3779b9) | 0;
  h ^= h >>> 15; h = Math.imul(h, 2246822519); h ^= h >>> 13;
  return 0.82 + 0.18 * ((h >>> 16) / 65535);
}
const traceA = new Uint16Array(TUBE_LENGTH_PX);     // per-column film path coefficient A = η(2 − η)·2^16 of the residue coat
const traceRaw = new Uint16Array(TUBE_LENGTH_PX);   // render-frame copy of the residue, input to the taper blur

// Wet film (step 3d): the liquid a receding line leaves on the bore wall, h = η·R (physics filmEta), drawn
// as a fully drawn line (FILM_FULL_PX_S) leaves it. The edge's film follower (TubeState.film*) then scales
// it — it drains as the follower decays, thinning to nothing instead of switching off. A watery line leaves
// microns: only the rays grazing the wall see it; a syrup coats the bore.
// Seen across the tube, a row at bore coordinate u (boreRow) crosses the annular film at both walls:
// path / full chord f = 1 − √(1 − q), q = (2η − η²)/(1 − u²), 1 once the ray misses the gas core (the
// palette's outer rows already carry their own short chord, so f = 1 there is the body colour of that
// row). FILM_PHI[i] is f in 1/256 at q = i/256. Colour: Beer–Lambert against the
// backing in linear light, D·(C/D)^f = D^(1−f)·C^f per channel (C the body row = full chord, D the local
// backing) — monotone between the two and exact at both ends. The residue is the same coat: a dried dye
// stain is a tint, B^(1−τ)·C^τ against the tube back B, τ = traceAmount × its annular path fraction (≤ 1, so
// no smear reads denser than the column): wall lines for a watery film, a faint tint and legs for a syrup.
// FILM_LG = −log2 of the decoded sRGB channel, Q8; FILM_EX encodes 2^(−m/256) back to sRGB; integer tables,
// as the firmware.
const FILM_PHI = new Uint16Array(257), FILM_LG = new Uint16Array(256), FILM_EX = new Uint8Array(4096);
const srgbLin = (c: number): number => c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
const srgbEnc = (l: number): number => l <= 0.0031308 ? 12.92 * l : 1.055 * Math.pow(l, 1 / 2.4) - 0.055;
for (let i = 0; i <= 256; i++) FILM_PHI[i] = Math.floor(256 * (1 - Math.sqrt(1 - i / 256)) + 0.5);
for (let v = 0; v < 256; v++) FILM_LG[v] = Math.min(4095, Math.floor(-Math.log2(srgbLin(Math.max(1, v) / 255)) * 256 + 0.5));
for (let m = 0; m < 4096; m++) FILM_EX[m] = Math.floor(255 * srgbEnc(Math.pow(2, -m / 256)) + 0.5);
/** One channel of D^(1−f)·C^f, f = fT / 256 (0 < fT < 256), from the channels' Q8 logs. */
function filmMix(lgD: number, lgC: number, fT: number): number {
  return FILM_EX[(lgD * (256 - fT) + lgC * fT + 128) >> 8];
}
/** The film path fraction through a row, 1/256, for film thickness eta (FILM_PHI at q = (2η − η²)·kRow). */
function filmRowT(eta: number, kRow: number): number {
  if (eta <= 0) return 0;
  const q = eta * (2 - eta) * kRow;
  return q >= 1 ? 256 : FILM_PHI[Math.floor(q * 256 + 0.5)];
}
/** 1 − smoothstep(t), t clamped to 0..1: the eases of the imminent zone (1 at the line, 0 at its reach). */
function ease(t: number): number {
  const s = Math.min(1, Math.max(0, t));
  return 1 - s * s * (3 - 2 * s);
}

/** Draw one tube. y0 = top of tube in panel coords.
 *  `remaining` mode: the liquid sits at the right end and drains as time passes. The liquid layer is
 *  rendered in a mirrored frame (edge from the right, along-axis signs flipped), then flipped before
 *  panel-coordinate marks and bubbles are composited. */
export function drawTube(idx: number, y0: number, state: TubeState, p: Params, pal: Palette, ticksN: number,
                         lensEffect = true, lensSmooth = false): void {
  const H = pal.rows.length, L = TUBE_LENGTH_PX;
  // Mirroring flips along-axis quantities only; across-axis ones (angle, light, acrossTilt) are invariant.
  const mir = mirrored(p);
  const s = mir ? { ...state, fillPos: -state.fillPos, edgeLight: -state.edgeLight, cap: -state.cap } : state;
  const len = columnLen(s.fillTarget, p);
  const xs = p.freeLiquid ? (mir ? L - len - s.slugPos : s.slugPos) : 0; // home-end edge centre
  const xe = xs + len + Math.max(-len, Math.min(len, s.fillPos));              // time-edge centre; slosh can't exceed the volume
  // Tilt changes the LIGHT at the fill edge, not the liquid itself: gravity pressing the
  // liquid into the right end brightens the cap glow, draining away from it dims it.
  const lightK = Math.max(0.25, 1 + p.edgeLightGain * s.edgeLight) * (1 + s.agitation);
  const lightKL = Math.max(0.25, 1 - p.edgeLightGain * s.edgeLight) * (1 + s.agitation);
  const xsI = Math.round(xs);
  // Per-end meniscus: the home end takes the mirrored forcing; the pinned-line state is already in each
  // end's own outward sense (physics), so the mirror leaves it alone.
  const capR = capShape(p, len, s.edgeLight, s.acrossTilt, s.cap, s.pinFree, s.lineVFree);
  const capL = capShape(p, len, -s.edgeLight, s.acrossTilt, -s.cap, s.pinHome, s.lineVHome);
  const capK = capScale(len, capR), capKL = capScale(len, capL);
  const [tanR, tanL] = edgeSkews(s.angle, H, xe - xs, xs, capR, capK, capL, capKL);
  const hasLiquid = xe - xs >= 0.5;   // an empty column draws nothing, not even an anti-aliased sliver
  fizzShift[idx] = xs;
  ensureFizz(idx, p, Math.max(0, Math.min(L, xe - xs - 6)), s.agitation);

  const softW = p.edgeSoft > 0 ? Math.max(1, Math.round(p.edgeSoft)) : 0;
  const traceMode = p.traces && p.traceAmount > 0 && !!state.trace;

  // Step 1: tube back — whole strip
  for (let ry = 0; ry < H; ry++) hspan(y0 + ry, 0, L, pal.tubeBackRows[ry]);

  // Cache the two curved edges before composing the backing and liquid. The
  // home edge `edgesL` sits on the end cap (x <= 0) unless the liquid is free.
  const edges = new Float32Array(H), edgesL = new Float32Array(H), capX0 = new Int16Array(H);
  // Surface fronts for stepFizz: per-row profiles in the liquid frame, and which of them is exposed.
  const surf = fizzSurf[idx].length === H ? fizzSurf[idx] : (fizzSurf[idx] = new Float32Array(H));
  const surfL = fizzSurfL[idx].length === H ? fizzSurfL[idx] : (fizzSurfL[idx] = new Float32Array(H));
  fizzExposed[idx] = (xe < L - 0.5 ? 1 : 0) | (p.freeLiquid && xs > 0.5 ? 2 : 0);
  for (let ry = 0; ry < H; ry++) {
    const ex = edgeX(ry, xe, tanR, p, capR, capK);
    const exL = p.freeLiquid ? edgeXL(ry, xs, tanL, p, capL, capKL) : 0;
    edges[ry] = ex; edgesL[ry] = exL;
    surf[ry] = ex - xs; surfL[ry] = exL - xs;
    let x0 = 0;
    if (p.cornerR > 0) { // rounded left end cap
      const r = Math.min(p.cornerR, H / 2), yc = (H - 1) / 2, dy = Math.abs(ry - yc);
      if (dy > yc - r) { const k = (dy - (yc - r)) / r; x0 = Math.round(r - Math.sqrt(Math.max(0, 1 - k * k)) * r); }
    }
    capX0[ry] = x0;
  }

  // Residue and wet film form the backing UNDER the liquid. Paint them first, then
  // blend the body AA over that backing once. Masking residue by (1 - coverage)
  // over an already-AA body leaks the bare tube colour at their junction.
  if (traceMode) {
    const hw = softW / 2;
    const N = p.wetFilm > 0 ? Math.max(1, Math.round(p.wetFilm)) : 0, invN = N > 0 ? 1 / N : 0, invBW = 1 / Math.max(1, softW);
    const bandR = hasLiquid && N > 0 && s.filmFree > 0.02, bandL = hasLiquid && N > 0 && p.freeLiquid && s.filmHome > 0.02;
    // Film thickness per edge (η·follower: it thins as the follower drains). Its visibility also fades
    // out with the follower from 0.2 down to the 0.02 gate (the film breaks up as it dries): a tangent row
    // sees even a vanishing film at full chord, so thickness alone would pop it off at the gate.
    const eta = filmEta(p), etaR = bandR ? eta * s.filmFree : 0, etaL = bandL ? eta * s.filmHome : 0;
    const visR = bandR ? ease((0.2 - s.filmFree) / 0.18) : 0, visL = bandL ? ease((0.2 - s.filmHome) / 0.18) : 0;
    // Columns that may receive residue or band: the occupied residue range (physics keeps
    // [traceLo, traceHi) tight) mirrored into the render frame, plus each band's reach over all rows.
    // Permanent film (traceFilm, a share of the thin-film cap): every column carries residue at least that
    // thick, so the range is the whole tube and the per-column thickness floors there.
    const filmV = p.traceFilm > 0 ? Math.min(1, p.traceFilm) : 0;
    let lo = L, hi = 0;
    if (filmV > 0) { lo = 0; hi = L; }
    else if (state.traceHi > state.traceLo) { lo = mir ? L - state.traceHi : state.traceLo; hi = mir ? L - state.traceLo : state.traceHi; }
    // Imminent residue: physics lays a deposit at its edge's mid-row centre (xe / xs, the columns stepTube
    // deposits at), but the line really left it along the contact line, which leads or lags that centre
    // per row by Δ = edge − centre (tilt skew, meniscus cap). Within Z px of the line the residue is
    // sampled Δ·w back, w easing 1 → 0 over Z = 2·max|Δ| (keeps the map monotone): the fresh smear hugs
    // the meniscus instead of leaving a bare wedge where the line leads. Past Z the deposit stays where
    // it dried. Only where a deposit lies within reach of the edge (a uniform traceFilm floor shears onto
    // itself) and only on rows whose |Δ| ≥ 1/8 px: everything else stays on the fast plain-residue path.
    let dR = 0, dL = 0, eR0 = L, eR1 = 0, eL0 = L, eL1 = 0;
    for (let ry = 0; ry < H; ry++) {
      dR = Math.max(dR, Math.abs(edges[ry] - xe)); eR0 = Math.min(eR0, edges[ry]); eR1 = Math.max(eR1, edges[ry]);
      dL = Math.max(dL, Math.abs(edgesL[ry] - xs)); eL0 = Math.min(eL0, edgesL[ry]); eL1 = Math.max(eL1, edgesL[ry]);
    }
    const ZR = Math.max(1, 2 * dR), ZL = Math.max(1, 2 * dL), invZR = 1 / ZR, invZL = 1 / ZL;
    const depLo = mir ? L - state.traceHi : state.traceLo, depHi = mir ? L - state.traceLo : state.traceHi;
    const near = (e0: number, e1: number, z: number): boolean => depHi > depLo && depLo < e1 + z + 4 && depHi > e0 - z - 4;
    const shearR = hasLiquid && dR >= 0.125 && near(eR0, eR1, ZR);
    const shearL = hasLiquid && p.freeLiquid && dL >= 0.125 && near(eL0, eL1, ZL);
    const extR = Math.max(bandR ? N : 0, shearR ? ZR : 0), extL = Math.max(bandL ? N : 0, shearL ? ZL : 0);
    if (extL > 0 || extR > 0) for (let ry = 0; ry < H; ry++) {
      if (extL > 0) { lo = Math.min(lo, Math.floor(edgesL[ry] - extL)); hi = Math.max(hi, Math.ceil(edgesL[ry] + hw) + 1); }
      if (extR > 0) { lo = Math.min(lo, Math.floor(edges[ry] - hw)); hi = Math.max(hi, Math.ceil(edges[ry] + extR) + 1); }
    }
    if (hi > lo) {
      // widened ±4 for the blur reach (and 4 more for the columns the blur reads); columns outside
      // the residue range are guaranteed zero and the band only reads its own columns.
      const a0 = Math.max(0, lo - 4), a1 = Math.min(L, hi + 4);
      const c0 = Math.max(0, a0 - 4), c1 = Math.min(L, a1 + 4);
      for (let x = c0; x < c1; x++) traceRaw[x] = state.trace[mir ? L - 1 - x : x];
      // ±4 px triangular blur before the streak texture: the smear's outer end starts where the edge
      // turned around at ~zero speed (dense deposit next to bare glass) — blurred it tapers like a
      // tide mark instead of a 1-px cliff. The streak scatters the film's thickness (an uneven coat).
      for (let x = a0; x < a1; x++) {
        let v = 5 * traceRaw[x];
        for (let d = 1; d <= 4; d++) v += (5 - d) * (traceRaw[Math.max(0, x - d)] + traceRaw[Math.min(L - 1, x + d)]);
        v *= 1 / 25;
        const eta = FILM_ETA_MAX * Math.max(v / TRACE_FULL, filmV) * traceStreak(x + idx * 6151);
        traceA[x] = Math.floor(eta * (2 - eta) * 65536 + 0.5);
      }
      const G = Math.floor(p.traceAmount * 256 + 0.5);
      for (let ry = 0; ry < H; ry++) {
        const y = y0 + ry;
        const ex = edges[ry], exL = edgesL[ry], xm = (ex + exL) / 2;
        // film path weight 1/(1 − u²) of this row; the outermost rows graze the wall (u → 1). K = the same
        // weight in 1/256, capped where any film fills the row: the path index is (A·K + 2^15) >> 16
        const u = boreRow(ry, p), gr = 1 - u * u, kRow = gr > 1e-6 ? 1 / gr : 1e6;
        const K = Math.min(262144, Math.floor(kRow * 256 + 0.5));
        // stain depth 1/256 (with the chord clamp) of a coat with path coefficient A: traceAmount × path fraction
        const depth = (A: number): number => {
          const i = Math.floor(A * K / 65536 + 0.5);
          return Math.min(256, (i >= 256 ? 256 : FILM_PHI[i]) * G / 256);
        };
        // the residue is the first layer over the tube back: B^(1−τ)·C^τ from the two rows' logs
        const B = rgb565to888(pal.tubeBackRows[ry]), C = rgb565to888(pal.rows[ry]);
        const lgB0 = FILM_LG[B[0]], lgB1 = FILM_LG[B[1]], lgB2 = FILM_LG[B[2]];
        const lgC0 = FILM_LG[C[0]], lgC1 = FILM_LG[C[1]], lgC2 = FILM_LG[C[2]];
        const tint = (T: number): number => T >= 256 ? pal.rows[ry]
          : rgb565(filmMix(lgB0, lgC0, T), filmMix(lgB1, lgC1, T), filmMix(lgB2, lgC2, T));
        const xr = Math.round(ex), xrL = Math.round(exL);   // hard edge: liquid where xrL <= x < xr
        // this row's Δ per edge, where the smear is sheared at all
        const shR = shearR && Math.abs(ex - xe) >= 0.125 ? ex - xe : 0, shL = shearL && Math.abs(exL - xs) >= 0.125 ? exL - xs : 0;
        // Row split into segments so the per-pixel coverage/band math only runs near the edges:
        // [a0, pl1) plain residue · [zl0, zl1) home-edge zone · [zl1, zr0) fully covered, skipped ·
        // [zr0, zr1) time-edge zone · [pr0, a1) plain residue. A zone reaches hw px in and out from its
        // edge (soft ramp), N px out while a wet film is up, Z px out on a sheared row.
        let pl1 = a1, zl0 = a1, zl1 = a1, zr0 = a1, zr1 = a1, pr0 = a1;
        if (hasLiquid) {
          // at least half a pixel even for hard edges: the midpoint blend bt spans max(1, softW) px
          const hz = Math.max(0.5, hw), dl = Math.max(hz, bandL ? N : 0, shL ? ZL : 0), dr = Math.max(hz, bandR ? N : 0, shR ? ZR : 0);
          const clamp = (v: number): number => Math.max(a0, Math.min(a1, v));
          pl1 = clamp(Math.floor(exL - dl - 0.5) + 1);
          const sk0 = clamp(softW > 0 ? Math.ceil(exL + hw - 0.5) : xrL);       // first fully covered column
          const sk1 = clamp(softW > 0 ? Math.floor(ex - hw - 0.5) + 1 : xr);   // one past the last
          pr0 = clamp(Math.ceil(ex + dr - 0.5));
          zl0 = pl1; zl1 = Math.min(sk0, pr0); zr0 = Math.max(sk1, zl1); zr1 = pr0;
        }
        for (let seg = 0; seg < 2; seg++) {
          const p0 = seg ? pr0 : a0, p1 = seg ? a1 : pl1;
          for (let x = p0; x < p1; x++) {
            if (!traceA[x]) continue;
            const T = Math.floor(depth(traceA[x]) + 0.5);
            if (T) px(x, y, tint(T));
          }
        }
        for (let seg = 0; seg < 2; seg++) {
          const z0 = seg ? zr0 : zl0, z1 = seg ? zr1 : zl1;
          for (let x = z0; x < z1; x++) {
            // liquid coverage the body pass will paint: full inside, the soft-edge ramp across each edge
            const cov = softW > 0
              ? Math.min(1, Math.max(0, (ex + hw - x - 0.5) / softW), Math.max(0, (x + 0.5 - exL + hw) / softW))
              : (x >= xrL && x < xr ? 1 : 0);
            if (cov >= 1) continue;
            // px outward of each contact line (< 0 under its soft ramp). bt = how much the pixel belongs to the
            // time edge: 0 / 1 on each half, blended across a softW-wide window at the midpoint so the two
            // edges' warps and films join continuously where a short slug's ramps overlap.
            const oL = exL - x - 0.5, oR = x + 0.5 - ex, bt = Math.min(1, Math.max(0, (x + 0.5 - xm) * invBW + 0.5));
            // shift toward the edge centre (Δ·w) and film weight 1/256. The film eases from the contact line
            // to 0 at N px out and thins there too (η·wN), so its full-chord rows retreat to the walls — legs —
            // and its visibility takes wN·vis on top, so even a tangent row hands over to the residue smoothly.
            let sh = 0, fw = 0;
            if (bt < 1) { const k = 1 - bt, wN = ease(oL * invN); if (shL) sh += k * shL * ease(oL * invZL); if (etaL > 0) fw += k * filmRowT(etaL * wN, kRow) * wN * visL; }
            if (bt > 0) { const wN = ease(oR * invN); if (shR) sh += bt * shR * ease(oR * invZR); if (etaR > 0) fw += bt * filmRowT(etaR * wN, kRow) * wN * visR; }
            // imminent residue sampled at the shifted column, linear between columns
            const xf = x - sh, i0 = Math.floor(xf), ft = xf - i0;
            const r0 = i0 >= a0 && i0 < a1 ? traceA[i0] : 0, r1 = i0 + 1 >= a0 && i0 + 1 < a1 ? traceA[i0 + 1] : 0;
            // The residue the line just laid down and the wet film behind it are one coat, counted once: the
            // deeper of the two. Never lighter than the residue beside it; the body's soft edge and the
            // meniscus join it to the column.
            const T = Math.floor(Math.max(r0 + r1 ? depth(r0 + (r1 - r0) * ft) : 0, fw) + 0.5);
            if (T > 0) px(x, y, tint(T));
          }
        }
      }
    }
  }

  // Local backing per row and edge for the convex nose (step 3e): the first pixel past the soft
  // ramp, taken BEFORE the body and its glow paint over it — the bare back or the residue/wet band,
  // plus the first pixel of the step-3c wet film — so no glow width can move it off the wet trail.
  const backR = new Uint16Array(H), backL = new Uint16Array(H);
  if (hasLiquid) {
    const hw = softW / 2, yc = (H - 1) / 2;
    const film3c = !traceMode && p.wetFilm > 0;
    for (let ry = 0; ry < H; ry++) {
      const y = y0 + ry, d = (ry - yc) / yc, rowW = 0.4 + 0.6 * d * d;
      const xr = Math.floor(edges[ry] + hw - 0.5) + 1, xl = Math.ceil(edgesL[ry] - hw - 0.5) - 1;
      let bR = xr >= 0 && xr < L ? fb[y * PANEL_W + xr] : pal.tubeBackRows[ry];
      let bL = xl >= capX0[ry] && xl < L ? fb[y * PANEL_W + xl] : pal.tubeBackRows[ry];
      if (film3c && s.filmFree > 0.02 && Math.round(p.wetFilm * s.filmFree) > 0) bR = blend565(bR, pal.rows[ry], 0.35 * s.filmFree * rowW);
      if (film3c && p.freeLiquid && s.filmHome > 0.02 && Math.round(p.wetFilm * s.filmHome) > 0) bL = blend565(bL, pal.rows[ry], 0.35 * s.filmHome * rowW);
      backR[ry] = bR; backL[ry] = bL;
    }
  }

  // Liquid body and its soft edge, over the residue backing.
  for (let ry = 0; ry < H; ry++) {
    const ex = edges[ry], exL = edgesL[ry], x0 = capX0[ry];
    if (!hasLiquid) continue;
    const xi = Math.floor(ex), frac = ex - xi;
    const xiL = Math.floor(exL), fracL = exL - xiL;
    const xa = Math.max(x0, xiL + 1);
    // Keep the underlay intact in partially covered pixels until the AA pass blends them.
    const solidLo = traceMode && softW > 0 ? Math.max(xa, Math.ceil(exL + softW / 2 - 0.5)) : xa;
    const solidHi = traceMode && softW > 0 ? Math.min(xi, Math.floor(ex - softW / 2 - 0.5) + 1) : xi;
    hspan(y0 + ry, solidLo, solidHi, pal.rows[ry]);
    if (p.edgeSoft > 0) {  // soft edge: a coverage ramp `w` px wide centred on the geometric edge.
      // The glow (if any) folds into the same per-pixel alpha min(1, cov + g), anchored to the
      // sub-pixel edge: no integer snapping, so no seam before the glow and no 1-px stepping
      // while the edge moves. alpha is monotone in x by construction (cov and g both decline).
      const w = Math.max(1, Math.round(p.edgeSoft)), hw = w / 2;
      const glow = p.edgeGlow > 0 && p.glowStrength > 0;
      // A bead shorter than the two AA ramps must composite once using their intersection.
      if (traceMode && ex - exL < w) {
        const reach = hw + (glow ? p.edgeGlow : 0);
        for (let x = Math.max(x0, Math.floor(exL - reach)), end = Math.min(L, Math.ceil(ex + reach)); x < end; x++) {
          const gr = glow ? Math.max(0, 1 - (x + 0.5 - ex) / p.edgeGlow) : 0;
          const gl = glow ? Math.max(0, 1 - (exL - x - 0.5) / p.edgeGlow) : 0;
          const ar = Math.max(0, (ex + hw - x - 0.5) / w) + gr * gr * p.glowStrength * lightK;
          const al = Math.max(0, (x + 0.5 - exL + hw) / w) + gl * gl * p.glowStrength * lightKL;
          const a = Math.min(1, ar, al);
          if (a > 0) pxa(x, y0 + ry, pal.rows[ry], a);
        }
        continue;
      }
      const a0 = Math.floor(ex - hw - 0.5) + 1;
      const aEnd = glow ? Math.ceil(ex + hw - 0.5 + p.edgeGlow) : Math.ceil(ex + hw - 0.5) - 1;
      for (let x = a0; x <= aEnd; x++) {
        const t = glow ? Math.max(0, 1 - (x + 0.5 - ex) / p.edgeGlow) : 0;
        const a = Math.min(1, Math.max(0, (ex + hw - x - 0.5) / w) + t * t * p.glowStrength * lightK);
        if (a <= 0) break;
        if (a >= 1 && x >= solidLo && x < solidHi) continue;   // the span already drew it full
        if (x >= x0) {
          if (traceMode) pxa(x, y0 + ry, pal.rows[ry], a);
          else px(x, y0 + ry, blend565(pal.tubeBackRows[ry], pal.rows[ry], a));
        }
      }
      const b0 = Math.floor(exL - hw - 0.5) + 1;
      const bEnd = glow ? Math.floor(exL - hw - 0.5 - p.edgeGlow) : b0;  // home edge: glow to the left
      for (let x = Math.ceil(exL + hw - 0.5) - 1; x >= bEnd; x--) {
        const t = glow ? Math.max(0, 1 - (exL - (x + 0.5)) / p.edgeGlow) : 0;
        const a = Math.min(1, Math.max(0, (x + 0.5 - exL + hw) / w) + t * t * p.glowStrength * lightKL);
        if (a <= 0) break;
        if (x < x0 || x >= xi) continue;
        if (a >= 1 && x >= solidLo && x < solidHi) continue;
        if (traceMode) pxa(x, y0 + ry, pal.rows[ry], a);
        else px(x, y0 + ry, blend565(pal.tubeBackRows[ry], pal.rows[ry], a));
      }
    } else {
      if (frac >= 0.5) px(xi, y0 + ry, pal.rows[ry]);
      if (fracL < 0.5 && xiL >= x0) px(xiL, y0 + ry, pal.rows[ry]);
    }
  }

  // Highlight colour and per-row luma weight (row luma / max luma) shared by the edge lighting
  // passes: lighting RELATIVE to each row's shade keeps the flat highlight colour from lighting
  // up the dark bottom wall near the cap, which would read as the drop bulging along the bottom.
  // Firmware: rc.hiC / pal.rowK.
  const hi888 = ambientize(scale(hexToRgb(p.liquidHi), p.brightness * p.liquidBright), ambientBodyL(p), ambientAmt(p));
  const hiC = q(hi888);
  // Lit edge of the concave surface: pure liquid colour mixed toward the highlight;
  // the inner shoulder uses the body colour so the surface has depth across its width.
  const liquid888 = scale(hexToRgb(p.liquid), p.brightness * p.liquidBright);
  const lensC = q(mix(liquid888, hi888, 0.55));
  // surfaceTone target: the deep liquid colour (darker) or the highlight (lighter); tone() shifts a colour toward it
  const darkC = q(scale(liquid888, 0.35));   // deep liquid colour: the dark tone target, and the unlit stroke's shade
  const toneC = p.surfaceTone < 0 ? darkC : hiC, toneK = Math.min(1, Math.abs(p.surfaceTone));
  const tone = (c: number): number => toneK > 0 ? blend565(c, toneC, toneK) : c;
  const rowKs = new Float32Array(H);
  { let lmax = 1;
    for (let ry = 0; ry < H; ry++) { rowKs[ry] = luma(rgb565to888(pal.rows[ry])); lmax = Math.max(lmax, rowKs[ry]); }
    for (let ry = 0; ry < H; ry++) rowKs[ry] /= lmax; }
  // Backdrop luma per row (0..1) for the surface rim: the contact ring on the far glass is a thin liquid
  // lens — it reflects the highlight over a dark back and shows as a liquid-tinted line over a light one.
  const backKs = new Float32Array(H);
  for (let ry = 0; ry < H; ry++) backKs[ry] = Math.min(1, luma(rgb565to888(pal.tubeBackRows[ry])) / 255);

  // Step 3a: front brightening — last `frontBright` px before the edge lerp toward the highlight colour (per row).
  if (hasLiquid && p.frontBright > 0) {
    for (let ry = 0; ry < H; ry++) {
      const ex = edges[ry]; const xi = Math.floor(ex); const rowK = rowKs[ry];
      const xiL = Math.floor(edgesL[ry]);
      for (let k = 1; k <= p.frontBright; k++) {
        const x = xi - k; if (x < 0) break;
        if (x >= L) continue;
        const t = (1 - k / p.frontBright); px(x, y0 + ry, blend565(fb[(y0 + ry) * PANEL_W + x], hiC, Math.min(1, t * t * 0.85 * lightK * rowK)));
      }
      if (!p.freeLiquid) continue;
      for (let k = 1; k <= p.frontBright; k++) {   // home edge: lit by the opposite tilt
        const x = xiL + k; if (x >= xi - p.frontBright) break;
        if (x < 0 || x >= L) continue;
        const t = (1 - k / p.frontBright); px(x, y0 + ry, blend565(fb[(y0 + ry) * PANEL_W + x], hiC, Math.min(1, t * t * 0.85 * lightKL * rowK)));
      }
    }
  }

  // Step 3b: edge glow — a few px past the edge fade from liquid to the tube back. Hard-edge path
  // only (edgeSoft = 0); with a soft edge the glow is folded into the step-3 per-pixel alpha.
  if (hasLiquid && p.edgeSoft <= 0 && p.edgeGlow > 0 && p.glowStrength > 0) {
    for (let ry = 0; ry < H; ry++) {
      // glow starts at the first px past the RENDERED hard edge (round(ex)), never leaving a
      // 1-px tube-back gap that flickers as frac crosses 0.5
      const xg = Math.round(edges[ry]), xgL = Math.round(edgesL[ry]) - 1;
      for (let k = 0; k < p.edgeGlow; k++) {
        const t = (1 - k / p.edgeGlow), xr = xg + k, xl = xgL - k;
        if (xr < L) {
          const a = Math.min(1, t * t * p.glowStrength * lightK);
          if (traceMode) pxa(xr, y0 + ry, pal.rows[ry], a);
          else px(xr, y0 + ry, blend565(pal.tubeBackRows[ry], pal.rows[ry], a));
        }
        if (p.freeLiquid && xl >= capX0[ry]) {
          const a = Math.min(1, t * t * p.glowStrength * lightKL);
          if (traceMode) pxa(xl, y0 + ry, pal.rows[ry], a);
          else px(xl, y0 + ry, blend565(pal.tubeBackRows[ry], pal.rows[ry], a));
        }
      }
    }
  }

  // Step 3c: wet film — a receding edge leaves liquid on the glass past its contact lines: a faint
  // liquid-coloured trail over the glow, strongest at the wall rows, fading with TubeState.film*.
  // In trace mode the film is the wet band of step 3d instead (full liquid at the edge, thinning
  // into the residue), so this faint version is skipped there.
  if (!traceMode && hasLiquid && p.wetFilm > 0 && (s.filmFree > 0.02 || (p.freeLiquid && s.filmHome > 0.02))) {
    const yc = (H - 1) / 2;
    for (let ry = 0; ry < H; ry++) {
      const d = (ry - yc) / yc, rowW = 0.4 + 0.6 * d * d;
      const nR = Math.round(p.wetFilm * s.filmFree), nL = p.freeLiquid ? Math.round(p.wetFilm * s.filmHome) : 0;
      const xg = softW > 0 ? Math.ceil(edges[ry] + softW / 2 - 0.5) : Math.ceil(edges[ry]);
      const xgL = softW > 0 ? Math.floor(edgesL[ry] - softW / 2 - 0.5) : Math.floor(edgesL[ry]);
      for (let k = 0; k < nR; k++) if (xg + k < L) pxa(xg + k, y0 + ry, pal.rows[ry], 0.35 * s.filmFree * rowW * (1 - k / nR));
      for (let k = 0; k < nL; k++) if (xgL - k >= capX0[ry]) pxa(xgL - k, y0 + ry, pal.rows[ry], 0.35 * s.filmHome * rowW * (1 - k / nL));
    }
  }

  // Step 4: highlight inset — erase highlight near the edge so it reads as a cylinder (optional)
  // (handled by LUT; inset applied by drawing glass over highlight rows past xe - inset? simpler: skip)
  if (hasLiquid && p.highlightInset > 0) {
    const hiTop = highlightTop(p, H, s.light);
    for (let ry = Math.max(0, hiTop); ry < hiTop + p.highlightH && ry < H; ry++) {
      const ex = edges[ry];
      // fade the highlight into the body colour over the last `inset` px
      const bodyRow = pal.rows[Math.min(H - 1, hiTop + p.highlightH + 1)];
      const exL = edgesL[ry], xl = Math.max(0, Math.floor(exL));   // home edge (0 unless the liquid is free)
      for (let x = Math.floor(ex - p.highlightInset); x < Math.floor(ex); x++) {
        if (x < xl) continue;   // never outside the column
        const t = (x - (ex - p.highlightInset)) / p.highlightInset; // 0..1 toward edge
        px(x, y0 + ry, blend565(pal.rows[ry], bodyRow, t));
      }
      for (let x = xl; x < xl + p.highlightInset && x < ex; x++) {
        const t = 1 - (x - xl) / p.highlightInset;
        px(x, y0 + ry, blend565(pal.rows[ry], bodyRow, t));
      }
    }
  }

  // Step 3e: meniscus surface, over residue and the inset highlight. Normal alpha-over
  // compositing blends the surface over the actual smear; no separate residue mask can
  // expose bare glass under a faint band.
  // Concave: a dark inner shoulder grades into a lit outer rim, clipped to the wall ring.
  // Pixel-footprint coverage keeps both ends symmetric and the rim smooth during motion.
  // Convex: shade the thin nose inside the profile, leaving the existing soft ramp intact.
  // Both branches fade as ring and profile meet, avoiding a pop at the curvature sign change.
  // Per-row stroke extents and layer weights also tell the rear-mark compositor what the surface
  // covers and how opaque each of its layers is there (markFn, BandInfo).
  const strokeR = new Float32Array(H), strokeL = new Float32Array(H);
  const bandFill: [Float32Array, Float32Array] = [new Float32Array(H), new Float32Array(H)];
  const bandBlick: [Float32Array, Float32Array] = [new Float32Array(H), new Float32Array(H)];
  const bandRim: [Float32Array, Float32Array] = [new Float32Array(H), new Float32Array(H)];
  let strokeA = 0, pullR = 0, pullL = 0, veilA = 0;   // the stroke's opacity; receding pull per edge; foam veil opacity
  if (hasLiquid && p.surfaceBand > 0) {
    const hw = softW / 2, transK = Math.max(0, Math.min(1, p.liquidTransparency));
    // Opaque from surfaceBand ~0.6 whatever the light (the edge lit by the opposite tilt gets a
    // darker stroke, not a translucent one). Motion never fades it: the interface is always there,
    // only its shape moves — a receding line clings and deepens the dish, an advancing one flattens
    // it (TubeState.cap), and it springs back with a wobble as the edge settles.
    strokeA = Math.min(1, 1.6 * p.surfaceBand);
    // Dynamic contact angle: a line receding at speed pulls a wet film and meets the glass at ~0°
    // (collapsed by half the full-film speed). The dish is then liquid thinning into its film — no
    // limb-dark shoulder, no rim — so the band takes the liquid's own colour and runs out into the
    // trail along the dish. Instantaneous edge speed, not the draining film: once the line stops the
    // angle is back and so are shoulder and rim — nothing fades in afterwards. 0..1 per edge.
    const recede = mir ? 1 : -1, sat = (v: number): number => Math.max(0, Math.min(1, 2 * v / FILM_FULL_PX_S));
    pullR = sat(recede * (s.fillVel + s.slugVel)); pullL = p.freeLiquid ? sat(-recede * s.slugVel) : 0;
    // Interior opacity of the dish (surfaceFill): the rim and the blick keep their own opacity, so at 0 the
    // surface is drawn by its rim alone. The blick is the room light reflected in the dish: a tent of rows
    // centred where the highlight sits for the light angle (the same cylinder point as highlightTop), its
    // own height (BLICK_H of the tube: independent of highlightH, so it exists with the body strip off),
    // peaking mid-dish across the band.
    const fill = Math.max(0, Math.min(1, p.surfaceFill));
    veilA = FOAM_VEIL * strokeA * fill;   // a see-through dish does not veil the foam behind it
    const yc = (H - 1) / 2, blickY = yc - yc * Math.sin((s.light * Math.PI) / 180), blickInvH = 1 / Math.max(2, BLICK_H * H);
    const blickRow = (ry: number): number => p.surfaceBlick > 0 ? p.surfaceBlick * Math.max(0, 1 - Math.abs(ry - blickY) * blickInvH) : 0;
    // one-write layer compositor for the band pixel loop (see there); P premultiplied 888, A alpha
    const P: [number, number, number] = [0, 0, 0]; let A = 0, nL = 0, cLast = 0;
    const layer = (col: number, al: number): void => {
      if (al < 1 / 255) return;
      const C = rgb565to888(col), k = 1 - al;
      P[0] = P[0] * k + C[0] * al; P[1] = P[1] * k + C[1] * al; P[2] = P[2] * k + C[2] * al;
      A = A * k + al; nL++; cLast = col;
    };
    const surface = (ry: number, xm: number, xw: number, dir: number, lk: number, xlo: number, xhi: number): number => {
      const y = y0 + ry, tw = dir * (xw - xm);   // ring lead in the edge's own outward sense
      if (tw === 0) return 0;
      const lo = Math.min(xm, xw), hi = Math.max(xm, xw);   // pixel centres in [lo, hi)
      const x0 = Math.max(xlo, Math.ceil(lo - 0.5)), x1 = Math.min(xhi, Math.ceil(hi - 0.5));
      if (tw > 0) {   // concave: shaded surfaceWidth-px band, clipped to the wall ring
        // Overlap the body's AA ramp so it joins the shoulder without a bare-glass seam.
        const a = strokeA * Math.min(1, tw);
        if (a < 1 / 255) return 0;   // below visible opacity: no stroke, rim or band for the marks
        const shade = 0.6 * (1 - Math.min(1, lk));   // unlit edge: toward the deep liquid colour
        const inner = tone(blend565(pal.rows[ry], darkC, 0.3));
        const outer = tone(blend565(blend565(lensC, pal.rows[ry], 0.2), darkC, shade));
        const wEff = Math.min(p.surfaceWidth, tw);
        const invWidth = 1 / (wEff + hw);
        const pull = dir > 0 ? pullR : pullL;
        const blickK = blickRow(ry) * Math.min(1, lk) * (1 - pull);
        // The ring is a thin liquid lens: over a dark back it reflects the highlight (lit side only, row
        // shaded); over a light back it is absorption along a grazing path — a deep liquid tone, whatever
        // the light. backK blends the two.
        const backK = backKs[ry];
        const rimK = p.surfaceRim * Math.min(1, wEff / 2) * (1 - pull) * ((1 - backK) * (0.5 + 0.5 * rowKs[ry]) * Math.min(1, lk) + backK);
        const rimC = blend565(hiC, blend565(pal.rows[ry], darkC, 0.75), backK);
        const side = dir > 0 ? 0 : 1;   // layer weights for the rear-mark compositor (markFn)
        bandFill[side][ry] = a * fill; bandBlick[side][ry] = a * blickK; bandRim[side][ry] = a * rimK;
        // Integrate pixel footprints, including the rim, instead of snapping to a last column.
        const cLo = dir > 0 ? xm - hw : xm - wEff, cHi = dir > 0 ? xm + wEff : xm + hw;
        for (let x = Math.max(xlo, Math.floor(cLo)), xb = Math.min(xhi, Math.ceil(cHi)); x < xb; x++) {
          const t = dir * (x + 0.5 - xm);
          const lo = Math.max(t - 0.5, -hw), hi = Math.min(t + 0.5, wEff);
          const coverage = Math.max(0, hi - lo);
          if (coverage <= 0) continue;
          const u = Math.max(0, Math.min(1, ((lo + hi) / 2 + hw) * invWidth));
          const us = u * u * (3 - 2 * u);
          const c = blend565(inner, outer, us);
          const af = a * fill * coverage * (1 - pull * us);
          const ab = a * blickK * coverage * 4 * u * (1 - u);
          const rimCoverage = Math.max(0, hi - Math.max(lo, Math.max(0, wEff - 1)));
          const ar = a * rimK * rimCoverage;
          // Fill, blick and rim over one pixel are composited as ONE write (premultiplied sum, normal
          // over-operator order), so the firmware's fixed-point rounding is taken once per pixel: two
          // same-direction layers (a tinted rim over the fill on a light back) stacked to 2 LSB before.
          // A single layer takes the plain path, byte-identical to the separate writes.
          nL = 0; A = 0; P[0] = P[1] = P[2] = 0;
          layer(pull > 0 ? blend565(c, pal.rows[ry], pull) : c, af); layer(hiC, Math.min(1, ab)); layer(rimC, Math.min(1, ar));
          if (nL === 1) pxa(x, y, cLast, A);
          else if (nL > 1) pxa(x, y, q([P[0] / A, P[1] / A, P[2] / A]), A);
        }
        return wEff;
      } else {   // convex: thin nose inside the profile back to the ring — limb-darkened for an
        // opaque liquid (the surface turns away from the viewer), pale for a clear one (nothing left to absorb)
        // The thin nose shows what is behind it: the local backing (bare tube back, or the wet film /
        // residue a receding edge left — liquid-coloured, so a trailing convex nose never thins to a
        // pale crescent), sampled before the body and glow. Motion never fades it.
        const noseK = p.surfaceBand;
        const back = dir > 0 ? backR[ry] : backL[ry];
        const c = tone(blend565(blend565(pal.rows[ry], back, 0.55), hiC, 0.5 * transK));
        for (let x = x0; x < x1; x++) {
          const t = dir * (x + 0.5 - xm); if (t > -hw) continue;
          const a = noseK * Math.min(1, -tw) * (1 - Math.sqrt(Math.max(0, t / tw)));   // t/tw: 1 at the ring, 0 at the tip
          if (a >= 1 / 255) pxa(x, y, c, Math.min(1, a));
        }
        return 0;
      }
    };
    for (let ry = 0; ry < H; ry++) {
      const xi = Math.floor(edges[ry]), xa = Math.max(capX0[ry], Math.floor(edgesL[ry]) + 1);
      strokeR[ry] = surface(ry, edges[ry], wallX(ry, xe, tanR, p, capR, capK), 1, lightK, xa, L);
      if (p.freeLiquid) strokeL[ry] = surface(ry, edgesL[ry], wallXL(ry, xs, tanL, p, capL, capKL), -1, lightKL, capX0[ry], xi);
    }
  }

  // Panel-frame column bounds for the mark compositor (liquid where lo <= x < hi): the body only. The
  // concave band past it is composited per pixel by its own layer opacities (markFn / BandInfo, render
  // frame), so a faint or receding band never hides a mark as liquid and there is no threshold to jump.
  const bounds: Edges = markBounds[idx] = { lo: new Float32Array(H), hi: new Float32Array(H) };
  if (hasLiquid && p.surfaceBand > 0)
    bounds.band = { xm: [edges, edgesL], w: [strokeR, strokeL], fill: bandFill, blick: bandBlick, rim: bandRim, pull: [pullR, pullL], hw: softW / 2, mirror: mir, L };
  for (let ry = 0; ry < H; ry++) {
    const lo = edgesL[ry], hi = edges[ry];
    if (mir) {
      const row = (y0 + ry) * PANEL_W;
      for (let a = 0, b = L - 1; a < b; a++, b--) { const t = fb[row + a]; fb[row + a] = fb[row + b]; fb[row + b] = t; }
      bounds.lo[ry] = L - hi; bounds.hi[ry] = L - lo;
    } else { bounds.lo[ry] = lo; bounds.hi[ry] = hi; }
  }
  if (!p.ticksOnTop || !p.digitsOnTop) buildWetShare(bounds, H);

  // Scale marks, all before bubbles.
  const labels = layoutLabels(y0, p, ticksN, state.acrossTilt, state.edgeLight, state.fillTarget);
  const drawTickLayer = (onTop: boolean): void => {
    if (p.ticksOnTop === onTop) {
      const wetRows = markSourceRows(H, p.tickLens);
      const dryRows = onTop ? wetRows : markSourceRows(H, p.tickDryLens);
      const dx = onTop ? 0 : -state.edgeLight * p.tickParallax;
      const dy = onTop ? 0 : state.acrossTilt * p.tickParallax;
      drawTicks(y0, p, ticksN, wetRows, dryRows, onTop ? null : bounds,
        markFn(y0, bounds, p, onTop, p.markContrast * p.tickBright, onTop ? null : pal.dryT), dx, dy,
        !onTop && rearTicksFollowDigits(p) ? tickFollow(p, H) : null);
    }
  };
  const drawDigitLayer = (onTop: boolean): void => {
    if (!labels || p.digitsOnTop !== onTop) return;
    const baked = !!labels.sprite && labels.shadow >= 0;
    // Sprite digits take no surface band: its rim, blick and dish are not layered over them (a look decision, firmware
    // perf: their runs need no per-pixel band test). Bitmap digits keep it.
    const digitEdges: Edges = labels.sprite ? { lo: bounds.lo, hi: bounds.hi } : bounds;
    holdWhole(digitHold[idx], labels);
    drawLabels(labels, p, onTop ? null : bounds, markFn(y0, digitEdges, p, onTop, p.markContrast * p.digitBright, onTop ? null : pal.dryT, baked, baked && floorBake(p)[0] > 0),
      digitHold[idx]);
  };
  drawTickLayer(false);
  drawDigitLayer(false);
  const mapX = (x: number): number => mir ? L - 1 - x : x;
  const span = (y: number, xa: number, xb: number, c: number): void => {
    if (mir) hspan(y, L - 1 - xb, L - xa, c);
    else hspan(y, xa, xb + 1, c);
  };

  // Step 5: fizz — anti-aliased discs at float positions, squashed vertically by the local lens
  // magnification so they come out round after applyLens (size >= 3: darker interior, bright rim).
  if (p.fizz) {
    const mag = lensMagRows(H, p);
    const blickC = q(scale([255, 255, 255], p.brightness));   // pinpoint: neutral white through the panel dimmer only
    // Highlight row (continuous, from the light angle): the core shifts away from it, the pinpoint toward it.
    const yHi = (H - 1) / 2 * (1 - Math.sin((s.light * Math.PI) / 180));
    const lxS = -0.7, lxSign = mir ? -1 : 1;   // light from screen-left; the liquid frame is mirrored under remaining
    for (const f of fizz[idx]) {
      if (f.v === 0) continue;   // idle slot
      const fy = Math.max(0, Math.min(H - 1, Math.round(f.y)));
      // Centres stay inside this frame's surfaces (the stepper ran on an older one, so a receding surface
      // pushes them back here): whatever touches a surface floats at most half out of it, like the foam.
      const fx = Math.max(-foamFront(surfL, H, f.y, -1), Math.min(foamFront(surf, H, f.y, 1), f.x));
      // A parked bubble in its last FOAM_POP_T s pops: swells and fades out, breaking the surface.
      const pop = f.life !== 0 && Math.abs(f.life) < FOAM_POP_T ? Math.abs(f.life) / FOAM_POP_T : 1;
      const r = fizzR(p, f.v) * (1 + 0.6 * (1 - pop));
      // Seen through liquid ∝ its depth: a deeper bubble fades toward the liquid, less so the clearer it is.
      // Seen through liquid in proportion to its depth: the liquid in front tints a deeper bubble toward the
      // body colour (a colour mix, so the disc stays an opaque store as before: rear marks are behind the bubble).
      const depthK = 1 - p.fizzDepth * f.z * (1 - p.liquidTransparency);
      const tintA = p.bubbleDark * depthK;   // interior: a dark tint over the liquid as-is (the bubble is see-through), fading with depth
      const cBlickD = depthK < 1 ? blend565(pal.rows[fy], blickC, depthK) : blickC;   // the pinpoint sinks with the bubble
      // Ring 1 px thick at its thinnest (core radius r − 1); the core shifts away from the light by fizzShadeOff·r,
      // clamped so its centre stays in the disc: the ring thickens on the lit side, may open on the shaded side.
      const m = fizzMag(mag, H, f.y, r), ry = r / m, off = Math.min(r * p.fizzShadeOff, r - 1);
      // Light direction in unsquashed disc space (liquid frame): x fixed toward screen-left, y toward the highlight row.
      const ly = Math.max(-1, Math.min(1, (yHi - f.y) / (H / 2))), nrm = 1 / Math.sqrt(lxS * lxS + ly * ly);
      const dirX = lxSign * lxS * nrm, dirY = ly * nrm;
      const offX = -dirX * off, offY = -dirY * off;   // dark core shifted away from the light
      // Specular pinpoint on the lit side (r >= 2.5, fizzBlick > 0): scalar rim colour mixed into the pixel before its one blend.
      const blick = r >= 2.5 && p.fizzBlick > 0, bk = 0.4 * (r - 1), bX = dirX * bk, bY = dirY * bk, rb = Math.max(0.6, r / 4);
      for (let iy = Math.floor(f.y - ry - 1); iy <= Math.ceil(f.y + ry); iy++) {
        if (iy < 0 || iy >= H) continue;
        const wallT = pal.dryT[iy] * pop;   // bubbles live in the bore: invisible where the ray only sees the wall band
        if (wallT <= 0) continue;
        const cRimD = depthK < 1 ? blend565(pal.rows[iy], pal.bubbleRimRows[iy], depthK) : pal.bubbleRimRows[iy];
        // Past the profile a bubble is seen through the concave band's front-glass wedge, thickest at the
        // profile and gone at the band's outer rim; a receding edge's band thins out the same way it is drawn.
        const sR = surf[iy], sL = surfL[iy], bR = strokeR[iy], bL = strokeL[iy];   // stroke widths: 0 where no band is drawn
        for (let ix = Math.floor(fx - r - 1); ix <= Math.ceil(fx + r); ix++) {
          const dx = ix + 0.5 - fx, dy = (iy + 0.5 - f.y) * m;
          const d = Math.sqrt(dx * dx + dy * dy);
          let cov = Math.min(1, r + 0.5 - d) * wallT;
          if (cov <= 0) continue;
          // Veil by the pixel's footprint over each band [profile, profile ± width]: continuous as the edge moves.
          if (ix + 1 > sR && bR > 0) { const a1 = Math.min(ix + 1, sR + bR), a0 = Math.max(ix, sR);
            if (a1 > a0) { const q = ((a0 + a1) / 2 - sR) / bR; cov *= 1 - veilA * (a1 - a0) * (1 - q) * (1 - pullR * q); } }
          if (ix < sL && bL > 0) { const a1 = Math.min(ix + 1, sL), a0 = Math.max(ix, sL - bL);
            if (a1 > a0) { const q = (sL - (a0 + a1) / 2) / bL; cov *= 1 - veilA * (a1 - a0) * (1 - q) * (1 - pullL * q); } }
          const cx = dx - offX, cy = dy - offY, dc = Math.sqrt(cx * cx + cy * cy);
          const inCore = r >= 1.5 && dc < r - 1;
          let g = 0;
          if (blick) { const ex = dx - bX, ey = dy - bY; g = p.fizzBlick * Math.max(0, Math.min(1, rb + 0.5 - Math.sqrt(ex * ex + ey * ey))); }
          if (inCore) {
            // See-through interior: the liquid and whatever is behind it stay as they are; only the pinpoint (specular,
            // neutral room light, panel-dimmed, depth-tinted) or the dark tint is laid over, one write, nothing at tint 0.
            // Pinpoint and tint fused: out = bg·(1 − A) + blick·cov·g with A = cov·(g + tint·(1 − g)), as one blend of
            // blick·g/(g + tint·(1 − g)) at A — no untinted hole under the pinpoint's AA fringe (a division only there).
            if (g > 0) { const w = g + tintA * (1 - g); pxa(mapX(ix + xsI), y0 + iy, tintA > 0 ? blend565(0, cBlickD, g / w) : cBlickD, cov * w); }
            else if (tintA > 0) pxa(mapX(ix + xsI), y0 + iy, 0, cov * tintA);
            continue;
          }
          pxa(mapX(ix + xsI), y0 + iy, g > 0 ? blend565(cRimD, cBlickD, g) : cRimD, cov);
        }
      }
    }
  }

  // Step 6: spirit-level bubble — filled ellipse (darkened body) with 1 px bright rim
  if (p.bubble) {
    const bx = xe - p.bubbleGap - s.edgeLight * p.bubbleTiltGain, by = (H - 1) * p.bubbleY - (H - 1) / 2 * s.acrossTilt * p.bubbleRollGain;   // bubble rises toward the high wall
    const rx = p.bubbleW / 2, ry_ = p.bubbleH / 2;
    if (bx - rx > xs + 2) {
      for (let yy = Math.floor(by - ry_); yy <= Math.ceil(by + ry_); yy++) {
        const dy = (yy - by) / ry_;
        if (Math.abs(dy) > 1) continue;
        const hw = Math.sqrt(1 - dy * dy) * rx;
        const xa = Math.round(bx - hw), xb = Math.round(bx + hw);
        const ryi = Math.max(0, Math.min(H - 1, yy));
        span(y0 + yy, xa, xb, pal.bubbleIn[ryi]);
        px(mapX(xa), y0 + yy, pal.bubbleRim); px(mapX(xb), y0 + yy, pal.bubbleRim);
      }
      // top/bottom rim rows
      const yt = Math.round(by - ry_), yb = Math.round(by + ry_);
      span(y0 + yt, Math.round(bx - rx * 0.45), Math.round(bx + rx * 0.45), pal.bubbleRim);
      span(y0 + yb, Math.round(bx - rx * 0.45), Math.round(bx + rx * 0.45), pal.bubbleRim);
    }
  }
  drawTickLayer(true);
  if (lensEffect) applyLens(y0, H, p, lensSmooth);

  // Front-facing marks are composited last, as on the physical display.
  drawDigitLayer(true);
}

/** Magnification for a bubble of radius r centred at float row y: mean of the row table over the rows
 *  the (pre-squashed) sprite covers, iterated once since that height depends on it. Reading a single row
 *  makes the sprite snap whenever the centre crosses a row where the table is steep. */
function fizzMag(mag: Float32Array, H: number, y: number, r: number): number {
  let m = 1;
  for (let it = 0; it < 2; it++) {
    // Clamp into the tube with a <= b: a bubble stranded past a shrunken tube (tubeHeight pushed while fizz
    // is on) otherwise gets an empty range, magnification 0 and an unbounded draw loop.
    const ry = r / m, a = Math.min(H - 1, Math.max(0, Math.floor(y - ry))), b = Math.max(a, Math.min(H - 1, Math.ceil(y + ry)));
    let s = 0; for (let i = a; i <= b; i++) s += mag[i];
    m = s / (b - a + 1);
  }
  return m;
}

/** Lens magnification per row (dest rows per source row): the rendered lens (`lens`, exactly as
 *  supersampled continuous row map, averaged per source row) times the physical glass (`topLens`, continuous), times a
 *  center-weighted `fizzSquash`, so pre-lens sprites can be pre-squashed. Rendered lens and glass act
 *  in sequence, so their magnifications multiply. */
let lensMagCache: { key: string; rows: Float32Array } | null = null;
function lensExponent(lens: number, curve: number): { strength: number; e: number } | null {
  const signedCurve = lens < 0 ? -curve : curve, strength = Math.abs(lens);
  if (strength === 0 || signedCurve === 0) return null;
  return { strength, e: signedCurve > 0 ? 1 + signedCurve * 2 : 1 / (1 - signedCurve * 2) };
}
function lensMagRows(H: number, p: Params): Float32Array {
  const key = `${H}:${p.lens}:${p.topLens}:${p.lensCurve}:${p.fizzSquash}`;
  if (lensMagCache && lensMagCache.key === key) return lensMagCache.rows;
  const rows = new Float32Array(H).fill(1);
  const curve = Math.max(-3, Math.min(3, p.lensCurve));
  const rendered = lensExponent(Math.max(-1, Math.min(1, p.lens)), curve);
  if (rendered) {
    // Supersample the continuous row map: average the local magnification (1 / d src/d dest) of the
    // samples landing on each source row; rows no sample lands on (dropped by applyLens) inherit the
    // previous row. Averaging over what lands on a row avoids the d src/d dest singularity at mid-height.
    const { strength, e } = rendered, N = 8, sum = new Float32Array(H), cnt = new Float32Array(H);
    for (let i = 0; i < H * N; i++) {
      const d = ((i + 0.5) / N - H / 2) / (H / 2), u = Math.abs(d);
      const s = Math.sign(d) * ((1 - strength) * u + strength * Math.pow(u, e));
      const src = Math.max(0, Math.min(H - 1, Math.floor(H / 2 + s * H / 2)));
      sum[src] += 1 / ((1 - strength) + strength * e * Math.pow(u, e - 1)); cnt[src]++;
    }
    let last = 1;
    for (let y = 0; y < H; y++) if (cnt[y] > 0) { last = sum[y] / cnt[y]; break; }
    for (let y = 0; y < H; y++) rows[y] = cnt[y] > 0 ? (last = sum[y] / cnt[y]) : last;
  }
  const glass = lensExponent(Math.max(-1, Math.min(1, p.topLens)), curve);
  if (glass) {
    const { strength, e } = glass;
    for (let y = 0; y < H; y++) {
      const u = Math.max(1 / H, Math.abs((y + 0.5 - H / 2) / (H / 2)));
      rows[y] /= (1 - strength) + strength * e * Math.pow(u, e - 1);
    }
  }
  // Extra squash is center-weighted: full fizzSquash at mid-height, ~1 at the top/bottom edges.
  for (let y = 0; y < H; y++) { const d = (y + 0.5 - H / 2) / (H / 2); rows[y] = Math.max(0.2, Math.min(5, rows[y] * (1 + (p.fizzSquash - 1) * (1 - d * d)))); }
  lensMagCache = { key, rows };
  return rows;
}

function applyLens(y0: number, H: number, p: Params, smooth: boolean): void {
  const lens = Math.max(-1, Math.min(1, p.lens));
  const curve = Math.max(-3, Math.min(3, p.lensCurve));
  const signedCurve = lens < 0 ? -curve : curve;
  const strength = Math.abs(lens);
  if (strength === 0 || signedCurve === 0) return;
  const exponent = signedCurve > 0 ? 1 + signedCurve * 2 : 1 / (1 - signedCurve * 2);
  if (smooth) lensScratch.set(fb.subarray(y0 * PANEL_W, (y0 + H) * PANEL_W));
  const sourceRow = (yd: number): number => {
    const d = (yd + 0.5 - H / 2) / (H / 2), u = Math.abs(d);
    const s = Math.sign(d) * ((1 - strength) * u + strength * Math.pow(u, exponent));
    return Math.max(0, Math.min(H - 1, H / 2 + s * H / 2 - (smooth ? 0.5 : 0)));
  };
  const copyRow = (yd: number): void => {
    const sy = sourceRow(yd);
    const dst = (y0 + yd) * PANEL_W;
    if (!smooth) {
      const src = (y0 + Math.floor(sy)) * PANEL_W;
      if (src !== dst) fb.copyWithin(dst, src, src + PANEL_W);
      return;
    }
    const a = Math.floor(sy), b = Math.min(H - 1, a + 1), t = sy - a;
    const rowA = a * PANEL_W, rowB = b * PANEL_W;
    for (let x = 0; x < PANEL_W; x++) fb[dst + x] = blend565(lensScratch[rowA + x], lensScratch[rowB + x], t);
  };
  const mid = Math.floor(H / 2);
  if (signedCurve > 0) {
    for (let yd = 0; yd < mid; yd++) copyRow(yd);
    for (let yd = H - 1; yd >= mid; yd--) copyRow(yd);
  } else {
    for (let yd = mid - 1; yd >= 0; yd--) copyRow(yd);
    for (let yd = mid; yd < H; yd++) copyRow(yd);
  }
}

/** Full frame. Bridge zone and margins stay black (we never draw there). */
export function renderFrame(hours: TubeState, minutes: TubeState, p: Params, lensEffect = true, lensSmooth = false): void {
  fb.fill(0);
  const palH = buildPalette(p, hours.light);
  const palM = hours.light === minutes.light ? palH : buildPalette(p, minutes.light);
  const lay = tubeLayout(p);
  drawTube(0, lay.yH, hours, p, palH, 12, lensEffect, lensSmooth);
  drawTube(1, lay.yM, minutes, p, palM, 60, lensEffect, lensSmooth);
}

/** Blit RGB565 framebuffer to a canvas ImageData (exact 565 expansion). */
export function blit(img: ImageData): void {
  const d = img.data;
  for (let i = 0, j = 0; i < fb.length; i++, j += 4) {
    const c = fb[i];
    const r5 = (c >> 11) & 0x1f, g6 = (c >> 5) & 0x3f, b5 = c & 0x1f;
    d[j] = (r5 << 3) | (r5 >> 2); d[j + 1] = (g6 << 2) | (g6 >> 4); d[j + 2] = (b5 << 3) | (b5 >> 2); d[j + 3] = 255;
  }
}
