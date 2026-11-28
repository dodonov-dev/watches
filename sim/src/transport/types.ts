// Transport abstraction: the UI drives the watch through this interface only.
// Implementations: serial.ts (Web Serial), ble.ts (Web Bluetooth NUS); both via line.ts.
import type { ParamKey, Params } from '../params';

export type TransportStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export interface WatchTransport {
  readonly status: TransportStatus;
  onStatus: (s: TransportStatus, detail?: string) => void;
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  /** FPS from the device's most recently completed two-second window. */
  getFps(): Promise<number>;
  /** Full struct as exported by the device. */
  getParams(): Promise<Partial<Params>>;
  /** Resolves false if the device rejected the key. */
  setParam(key: ParamKey, value: Params[ParamKey]): Promise<boolean>;
  setParams(patch: Partial<Params>): Promise<void>;
  setTime(epochMs: number, tzOffsetMin: number): Promise<void>;
  setDemoSpeed(speed: number): Promise<void>;
  /** Minutes sweep: seconds per empty→full→empty cycle, 0 = off. Persists on the device. */
  setSweep(period: number): Promise<void>;
  /** Logo LED 0..255 (firmware `L`). Persists on the device; throws if the board has none. */
  setLed(level: number): Promise<void>;
}
