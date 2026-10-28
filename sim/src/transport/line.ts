// Line-protocol core shared by the transports (`p name=value`, `p?`, `T epoch tz`).
// Commands are serialized: one in flight, resolved by the first line its `accept` recognises as its
// reply. Everything else is dropped — the command echo, boot banner lines after a port-open reset, and
// late replies to requests that already timed out (taking those as "the reply" shifted every later
// command by one). IMU stream lines (CSV) interleave at 50 Hz and go to `onLine`.
import { migrateParams, type ParamKey, type Params } from '../params';
import type { TransportStatus, WatchTransport } from './types';

const REPLY_TIMEOUT_MS = 1000;
const READY_ATTEMPTS = 6;   // × REPLY_TIMEOUT_MS: covers the board's boot after a port-open reset

const isCsv = (line: string): boolean => {
  const f = line.split(',');
  return f.length >= 7 && f.every((x) => x !== '' && !Number.isNaN(Number(x)));
};

const fmt = (v: Params[ParamKey]): string => (typeof v === 'boolean' ? (v ? '1' : '0') : String(v));

export abstract class LineTransport implements WatchTransport {
  status: TransportStatus = 'disconnected';
  onStatus: (s: TransportStatus, detail?: string) => void = () => {};
  /** Unsolicited lines (IMU stream). */
  onLine: (line: string) => void = () => {};
  private pending: { accept: (l: string) => boolean; resolve: (l: string) => void } | null = null;
  private queue: Promise<unknown> = Promise.resolve();
  private buf = '';
  private dec = new TextDecoder();

  abstract readonly supported: boolean;
  abstract connect(): Promise<void>;
  abstract disconnect(): Promise<void>;
  /** Null when the link is down. */
  protected abstract write(bytes: Uint8Array): Promise<void> | null;

  get connected(): boolean { return this.status === 'connected'; }

  /** Send a line; resolves with the first accepted reply line ('' on timeout or when disconnected). */
  request(line: string, accept: (l: string) => boolean): Promise<string> {
    const run = () => new Promise<string>((resolve) => {
      const timer = setTimeout(() => { this.pending = null; resolve(''); }, REPLY_TIMEOUT_MS);
      this.pending = { accept, resolve: (l) => { clearTimeout(timer); this.pending = null; resolve(l); } };
      const w = this.write(new TextEncoder().encode(line + '\n'));
      if (!w) { this.pending.resolve(''); return; }
      w.catch(() => { this.pending?.resolve(''); });
    });
    const p = this.queue.then(run, run);
    this.queue = p;
    return p;
  }

  /** Resolves once the board answers `?` (false if it never does), e.g. after the reset a port open triggers. */
  async waitReady(): Promise<boolean> {
    for (let i = 0; i < READY_ATTEMPTS && this.connected; i++)
      if (await this.request('?', (l) => l.startsWith('cmds:'))) return true;
    return false;
  }

  async getFps(): Promise<number> {
    const reply = await this.request('f', (l) => l.startsWith('fps '));
    const match = /^fps (\d+(?:\.\d+)?)\s/.exec(reply);
    if (!match) throw new Error(`no device FPS reply: ${reply || 'timeout'}`);
    return Number(match[1]);
  }

  /** The board / canvas the firmware runs (`v`: `board lcd316@320 canvas 820x320 panel 820x320`), as a
   *  spec/layout BOARD_TAG; '' when the firmware predates `v`. */
  async getBoard(): Promise<string> {
    const reply = await this.request('v', (l) => l.startsWith('board ') || l.startsWith('error unknown command'));
    return /^board (\S+)/.exec(reply)?.[1] ?? '';
  }

  async getParams(): Promise<Partial<Params>> {
    for (let i = 0; i < 2; i++) {
      const r = await this.request('p?', (l) => l.startsWith('{'));
      if (r.startsWith('{')) return migrateParams(JSON.parse(r));
    }
    throw new Error('no params reply');
  }

  async setParam(key: ParamKey, value: Params[ParamKey]): Promise<boolean> {
    const reply = await this.request(`p ${key}=${fmt(value)}`, (l) => l === `ok ${key}` || l === `unknown param ${key}`);
    return reply.startsWith('ok');
  }

  async setParams(patch: Partial<Params>): Promise<void> {
    for (const k of Object.keys(patch) as ParamKey[]) await this.setParam(k, patch[k]!);
  }

  async setTime(epochMs: number, tzOffsetMin: number): Promise<void> {
    if (!Number.isFinite(epochMs) || !Number.isInteger(tzOffsetMin)) throw new Error('invalid time');
    const reply = await this.request(`T ${Math.floor(epochMs / 1000)} ${tzOffsetMin}`, (l) => l.startsWith('time ') || l.startsWith('usage: T'));
    if (!/^time \d{2}:\d{2}:\d{2}$/.test(reply)) throw new Error(`time not accepted: ${reply || 'no reply'}`);
  }

  async setDemoSpeed(speed: number): Promise<void> {
    if (!Number.isFinite(speed) || speed < 0 || speed > 3600) throw new Error('invalid demo speed (0–3600)');
    const reply = await this.request(`d${speed}`, (l) => l.startsWith('demo speed x'));
    if (!reply.startsWith('demo speed x') || Number(reply.slice(12)) !== speed)
      throw new Error(`demo speed not accepted: ${reply || 'no reply'}`);
  }

  async setSweep(period: number): Promise<void> {
    if (!Number.isFinite(period) || (period !== 0 && (period < 1 || period > 3600))) throw new Error('invalid sweep period (0 or 1–3600 s)');
    const reply = await this.request(`w${period}`, (l) => l.startsWith('sweep ') || l.startsWith('usage: w'));
    if (reply !== (period ? `sweep ${period}s` : 'sweep off')) throw new Error(`sweep not accepted: ${reply || 'no reply'}`);
  }

  protected setStatus(s: TransportStatus, detail?: string): void { this.status = s; this.onStatus(s, detail); }

  /** Incoming bytes; lines may span chunks. */
  protected feed(bytes: Uint8Array): void {
    this.buf += this.dec.decode(bytes, { stream: true });
    let nl: number;
    while ((nl = this.buf.indexOf('\n')) >= 0) { this.dispatch(this.buf.slice(0, nl).trim()); this.buf = this.buf.slice(nl + 1); }
  }

  private dispatch(line: string): void {
    if (!line) return;
    if (isCsv(line)) { this.onLine(line); return; }
    const p = this.pending;
    if (p?.accept(line)) p.resolve(line);
  }
}
