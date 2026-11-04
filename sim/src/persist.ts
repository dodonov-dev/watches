// Session persistence. Everything you touch in the sim — params AND view state (zoom, cuff/gloss,
// time mode, tilt) — is written to localStorage on every edit, debounced. Exporting JSON is therefore
// only for checkpointing a finished look into the repo (`sim/params.json`), never to avoid losing work.
//
// `?fresh=1` starts from the code defaults *without* clearing the store: that is how you see changed
// DEFAULT_PARAMS, since a stored value always wins over a new default for a key that already existed.
import { DEFAULT_PARAMS, migrateParams, type Params } from './params';
import { DEFAULT_OVERLAY, type OverlayOpts } from './overlay';
import {
  DEFAULT_MATERIAL, MATERIAL_ENVELOPE_KIND, MATERIAL_VERSION, parseMaterialEnvelope, type Design, type Material, type MaterialProvenance,
} from './material/model';

const KEY = 'liquid-watch-session-v1';
const LEGACY_PARAMS = 'liquid-watch-params-v2'; // params-only store used before the session blob

/** Everything outside `Params`: presentation and playback, none of it ported to firmware. */
export interface ViewState {
  scale: number;
  showGrid: boolean;
  paused: boolean;
  timeMode: 'real' | 'demo' | 'set';
  demoSpeed: number;
  /** Minutes sweep: the minutes tube runs empty→full→empty every `sweepPeriod` s instead of telling time. */
  sweep: boolean;
  sweepPeriod: number;
  setClock: { h: number; m: number; s?: number };   // s: the frozen seconds (three tubes; 0 when unset)
  manual: { along: number; across: number };
  overlay: OverlayOpts;
}
export const DEFAULT_VIEW: ViewState = {
  scale: 0.5, showGrid: false, paused: false, timeMode: 'real', demoSpeed: 60, sweep: false, sweepPeriod: 10,
  setClock: { h: 10, m: 9, s: 0 }, manual: { along: 0, across: 0 }, overlay: { ...DEFAULT_OVERLAY },
};
/** Physical-material mode (material/ui.ts): in 'material' mode `params` is derive(material, design).
 *  `name` / `provenance` are the envelope metadata of the loaded material (a preset's or an imported
 *  file's), carried to the export; absent for a material with none. */
export interface MaterialState {
  mode: 'legacy' | 'material'; material: Material; design: Design; name?: string; provenance?: MaterialProvenance;
}
export const defaultMaterialState = (): MaterialState => ({ mode: 'legacy', material: { ...DEFAULT_MATERIAL }, design: {} });
export interface Session { params: Params; view: ViewState; material: MaterialState }

/** A stored material state, validated as a material envelope (material, design, optional name and
 *  provenance) plus the mode; anything invalid falls back to legacy mode with the defaults. */
function loadMaterialState(raw: unknown): MaterialState {
  if (typeof raw !== 'object' || raw === null) return defaultMaterialState();
  const o = raw as Record<string, unknown>;
  try {
    if (o.mode !== 'legacy' && o.mode !== 'material') throw new Error(`mode ${String(o.mode)}`);
    const has = (k: string): boolean => Object.prototype.hasOwnProperty.call(o, k);
    const env = parseMaterialEnvelope({
      kind: MATERIAL_ENVELOPE_KIND, version: MATERIAL_VERSION, material: o.material, design: o.design,
      ...(has('name') ? { name: o.name } : {}), ...(has('provenance') ? { provenance: o.provenance } : {}),
    });
    return {
      mode: o.mode, material: env.material, design: env.design,
      ...(env.name !== undefined ? { name: env.name } : {}), ...(env.provenance ? { provenance: env.provenance } : {}),
    };
  } catch (error) {
    console.warn(`stored material state ignored (${(error as Error).message}); legacy mode`);
    return defaultMaterialState();
  }
}

function read(key: string): Record<string, unknown> | null {
  try { const s = localStorage.getItem(key); return s ? JSON.parse(s) : null; } catch { return null; }
}

/** code defaults ← stored session (or the legacy params-only key). Keys added to the schema since the
 *  store was written fall back to their code default; keys removed from it are dropped by migrateParams. */
export function loadSession(fresh = false): Session {
  const params: Params = { ...DEFAULT_PARAMS };
  const view: ViewState = { ...DEFAULT_VIEW, overlay: { ...DEFAULT_OVERLAY }, setClock: { ...DEFAULT_VIEW.setClock }, manual: { ...DEFAULT_VIEW.manual } };
  if (fresh) return { params, view, material: defaultMaterialState() };
  const stored = read(KEY);
  const v = stored?.view as Partial<ViewState> | undefined;
  const storedParams = (stored?.params as Record<string, unknown> | undefined) ?? read(LEGACY_PARAMS);
  if (storedParams) Object.assign(params, migrateParams(storedParams));
  const legacyOverlay = v?.overlay as (Partial<OverlayOpts> & { lens?: number; lensCurve?: number }) | undefined;
  if ((!storedParams || !('lens' in storedParams)) && typeof legacyOverlay?.lens === 'number') params.lens = legacyOverlay.lens;
  if ((!storedParams || !('lensCurve' in storedParams)) && typeof legacyOverlay?.lensCurve === 'number') params.lensCurve = legacyOverlay.lensCurve;
  if (v) {
    Object.assign(view, v);
    view.overlay = { ...DEFAULT_OVERLAY, ...v.overlay };
    delete (view.overlay as any).lens;
    delete (view.overlay as any).lensCurve;
    view.setClock = { ...DEFAULT_VIEW.setClock, ...v.setClock };
    view.manual = { ...DEFAULT_VIEW.manual, ...v.manual };
  }
  return { params, view, material: loadMaterialState(stored?.material) };
}

let pending: Session | null = null;
let timer = 0;
function flush(): void {
  timer = 0;
  if (!pending) return;
  // `pending` holds the live objects, so this serialises the newest state, not the state at call time.
  try { localStorage.setItem(KEY, JSON.stringify(pending)); localStorage.removeItem(LEGACY_PARAMS); }
  catch { /* quota exceeded / private mode: keep the sim running, just unsaved */ }
  pending = null;
}
/** Debounced: dragging a slider fires `input` per pixel, one write per 250 ms is plenty. */
export function saveSession(s: Session): void {
  pending = s;
  if (!timer) timer = window.setTimeout(flush, 250);
}
/** Write immediately — used when the tab goes away mid-debounce. */
export function flushSession(): void {
  if (timer) { clearTimeout(timer); timer = 0; }
  flush();
}
addEventListener('pagehide', flushSession);
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') flushSession(); });
