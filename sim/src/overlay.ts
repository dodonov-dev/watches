// Leather cuff + acrylic vial overlay. Cuff/gloss and lens smoothing are view-only.
import { PANEL_W, TUBE_COUNT } from '@spec/layout';
import { tubeRows, type FaceLayout } from './render';

export interface OverlayOpts {
  enabled: boolean;
  slotInset: number; // px of tube hidden under leather at each end
  slotPad: number;   // px the slot is taller than the tube (negative = leather covers tube edge)
  lensSmooth: boolean; // false = crisp nearest-row remap (pixels stay sharp), true = bilinear
  gloss: number;     // 0..1 opacity of the acrylic highlight
  leather: 'brown' | 'black' | 'none';
}
export const DEFAULT_OVERLAY: OverlayOpts = { enabled: true, lensSmooth: false, slotInset: 10, slotPad: -2, gloss: 0.55, leather: 'brown' };

export const LEATHER_PAD_X = 40, LEATHER_PAD_Y = 60; // must match .leather inset in style.css

export function buildOverlayDom(root: HTMLElement): { leather: HTMLElement; slots: HTMLElement; vials: HTMLElement[] } {
  const leather = document.createElement('div');
  leather.className = 'leather';
  const slots = document.createElement('div');
  slots.className = 'slots';
  const vials: HTMLElement[] = [];
  for (let i = 0; i < TUBE_COUNT; i++) {
    const slot = document.createElement('div');
    slot.className = 'slot';
    const vial = document.createElement('div');
    vial.className = 'vial';
    slot.appendChild(vial);
    slots.appendChild(slot);
    vials.push(slot);
  }
  root.appendChild(leather);
  root.appendChild(slots);
  return { leather, slots, vials };
}

export function applyOverlay(dom: { leather: HTMLElement; slots: HTMLElement; vials: HTMLElement[] }, o: OverlayOpts, lay: FaceLayout): void {
  dom.leather.style.display = o.enabled ? 'block' : 'none';
  dom.slots.style.display = o.enabled ? 'block' : 'none';
  dom.leather.dataset.leather = o.leather;
  const rows = dom.vials.map((_, i) => tubeRows(lay, i));
  const w = PANEL_W - 2 * o.slotInset, h = rows.map((r) => r.H + 2 * o.slotPad);   // per tube (widths may differ)
  // Punch the slots out of the leather with a CSS mask (exclude composite).
  const holes = rows.map((r, i) =>
    `linear-gradient(#000 0 0) ${o.slotInset + LEATHER_PAD_X}px ${r.y - o.slotPad + LEATHER_PAD_Y}px / ${w}px ${h[i]}px no-repeat`);
  const mask = `linear-gradient(#000 0 0), ${holes.join(', ')}`;
  dom.leather.style.setProperty('-webkit-mask', mask);
  dom.leather.style.setProperty('-webkit-mask-composite', 'xor');
  dom.leather.style.setProperty('mask', mask);
  dom.leather.style.setProperty('mask-composite', 'exclude');
  dom.vials.forEach((slot, i) => {
    slot.style.top = `${rows[i].y}px`;
    slot.style.left = `${o.slotInset}px`;
    slot.style.width = `${w}px`;
    slot.style.height = `${h[i]}px`;
    slot.style.marginTop = `${-o.slotPad}px`;
    (slot.firstElementChild as HTMLElement).style.opacity = String(o.gloss);
  });
}
