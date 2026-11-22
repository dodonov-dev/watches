// IMU feed over a line transport (serial or BLE): the board's `i` stream (t_ms,ax,ay,az,gx,gy,gz at 50 Hz),
// mapped to the tube frame using spec/layout IMU_* constants.
import { IMU_AXIS_ALONG_TUBE, IMU_ALONG_TUBE_SIGN, IMU_AXIS_ACROSS_TUBE, IMU_ACROSS_TUBE_SIGN, IMU_AXIS_NORMAL, IMU_NORMAL_SIGN } from '@spec/layout';
import { GravityNorm, type TiltInput } from './physics';
import type { LineTransport } from './transport/line';

export class SerialImu {
  last: TiltInput = { along: 0, across: 0, gyroAlong: 0, gyroAcross: 0, normal: 1 };   // face up until a sample
  raw = '';
  private norm = new GravityNorm();

  constructor(private t: LineTransport) { this.attach(t); }

  attach(t: LineTransport): void { this.t = t; t.onLine = (l) => this.parse(l); }

  /** `i` toggles on the board; the reply states the resulting state, so re-send if it mismatches. */
  async setStream(on: boolean): Promise<void> {
    const isReply = (l: string) => l.startsWith('imu stream ');
    const r = await this.t.request('i', isReply);
    if (r.includes('off') === on) await this.t.request('i', isReply);
  }

  private parse(line: string): void {
    const f = line.split(',').map(Number);
    if (f.length < 7 || f.some(Number.isNaN)) return;
    const a = [f[1], f[2], f[3]], g = [f[4], f[5], f[6]];
    // Normalise by the slow-tracked gravity magnitude (board reads ~0.94 g), NOT by this
    // sample's |a| — instantaneous |a| collapses during jerks and would amplify transients.
    const n = this.norm.update(Math.hypot(a[0], a[1], a[2]));
    this.last = {
      along: (IMU_ALONG_TUBE_SIGN * a[IMU_AXIS_ALONG_TUBE]) / n,
      across: (IMU_ACROSS_TUBE_SIGN * a[IMU_AXIS_ACROSS_TUBE]) / n,
      gyroAlong: g[IMU_AXIS_ALONG_TUBE],
      gyroAcross: g[IMU_AXIS_ACROSS_TUBE],
      normal: (IMU_NORMAL_SIGN * a[IMU_AXIS_NORMAL]) / n,   // measured, signed (+ face up)
    };
    this.raw = line;
  }
}
