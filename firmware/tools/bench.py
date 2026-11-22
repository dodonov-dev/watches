#!/usr/bin/env python3
"""fps benchmark on the board, in a pinned scene so runs are comparable.

  tools/bench.py [--scene 10:09:30] [--samples 5] [--settle 4] [--stages [LIST]] [--stage name=value ...] [--quick]
                 [--preset FILE.json] [--fix-pose | --pose flat|stand|A,C,N] [--live-imu] [--allow-dead-imu] [--runs N] [--label TEXT] [--json]
                 [--ble-window]

Pins: optional preset (--preset: every key of the JSON the board knows; `v` and unknown keys are skipped and listed
once), clock fixed (`t`), demo frozen (`d0`), IMU influence off (`inputGain=0`, unless --live-imu), waits for the physics to settle, then reads `f` once per 2 s window and
reports the median fps / render ms / push-wait ms. LCD board: also the panel refill health over the base samples
(`f` refill totals, display.h display_refill_health): late refills = twitches, restarts = bad frames; any -> TWITCH.
--preset: a flash that changes PARAMS_SCHEMA_CRC resets NVS to presets/1.json, so benches across a Params
change are only comparable with a pinned preset.
IMU check: after pinning, `s` is read; along/across/gyro all exactly 0 = the "IMU dead after flash" signature.
The board is then rebooted (`r`), the pins are re-applied and `s` re-checked once; still dead -> exit code 3.
--allow-dead-imu accepts a dead IMU without the reboot (e.g. -DNO_IMU / --bare builds). The tilt goes in the
header line either way, because even the pinned scene depends on it.
Param pins are volatile writes (`p~`, never autosaved: a dropped session leaves NVS as it was); firmware without
`p~` gets `p` writes (autosaved, restored at the end).
--fix-pose: the scene no longer depends on how the board lies: tilt override `g -0.5 0` for 4 s (a free slug slides
home), then `g 0 0` for 4 s (tilt state 0), then the pins; the override is released (`g`) at the end. No dead-IMU
check then (the override reads as all 0). Same as `--pose flat`.
--pose stand | A,C,N: tilt override with the signed normal (`g A C 0 0 N`, + face up) held for the whole bench, the
pins on top, released at the end; stand = the board on its stand (along -0.976, across -0.01, normal +0.22). The
vertical fizz kernel reads `g 0 0` (--fix-pose) as face up (bubbles stall): bench vertical fizz at `--pose stand`.
The liquid sees the pose (inputGain is not pinned to 0; 0 on the board or preset becomes 1), settle +8 s first
(fizz pool at its steady state). The summary adds the medians of the per-core, frame-p95 and fizz-step figures.
--live-imu: inputGain is not pinned (the board's / preset's value stays), for moving-light cases
(e.g. `--live-imu --stage fizz=0`).
--stages additionally turns rendering stages off one at a time (digits, ticks, fizz, glow, ...) and prints what
each costs. --runs N repeats the whole measurement (base + stages) N times and reports, per line, the median
across runs and the min-max spread across runs (fizz positions are random: ~±0.5 ms per run on heavy presets).
Fast mode: firmware that reports `ble on|off` in `s` boots into fast mode, a BLE window (slower memory layout) only
after `B1` (ble.h); a board found in its window is first switched to fast mode (`B0`, a reboot). --ble-window benches
the window as it is (no switch).
Every param it touched is restored from a `p?` snapshot at the end (not `p!`, which would also overwrite
NVS-tuned params) and demo speed goes back to x1.
"""
import argparse, json, os, re, statistics, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import device

DEFAULT_STAGES = [  # name -> "off" value; the measured delta is that stage's cost
    ('digits', 0), ('digitShadow', 0), ('ticksH', 0), ('ticksM', 0), ('fizz', 0),
    ('edgeGlow', 0), ('frontBright', 0), ('surfaceBand', 0), ('contactAngle', 90), ('lens', 0), ('wetFilm', 0), ('traces', 0),
    ('glassBody', 0), ('glassRim', 0), ('liquidTransparency', 1),
]
EXIT_DEAD_IMU = 3
REBOOT_TIMEOUT_S = 30

def fmt(v):
    if isinstance(v, bool): return '1' if v else '0'
    if isinstance(v, float) and v.is_integer(): return str(int(v))
    return str(v)   # colours stay "#rrggbb": the firmware's `c` parser skips the '#' and reads hex

def same(a, b): return fmt(a).lower() == fmt(b).lower()

LAST_F = ''   # the last raw `f` line of the base measurement: push, cores, frame-p95 for the log
REFILLS = []  # (late, restarts, worst %) of each `f` of the last sample() call (LCD panel refill health; [] if absent)

def sample(d, n, settle):
    global LAST_F, REFILLS
    time.sleep(settle)
    rows = []; REFILLS = []
    for _ in range(n):
        time.sleep(2.1)
        parsable = lambda r: len(r.split()) > 6 and r.split()[0] == 'fps'
        r = d.talk('f', ok=parsable)  # "fps 19.8  render 46.48 ms  push-wait 0.02 ms  (...)"; device.py asks again
        if not parsable(r): raise SystemExit(f'bench.py: no parsable `f` reply: {r!r}')
        t = r.split()
        m = FX.search(r)
        rows.append((float(t[1]), float(t[3]), float(t[6]), *((float(x) for x in m.groups()) if m else ())))
        LAST_F = r.strip()
        m = re.search(r'refill late (\d+) restarts (\d+) worst (\d+)%', r)
        if m: REFILLS.append(tuple(int(x) for x in m.groups()))
    med = lambda i: statistics.median(r[i] for r in rows)
    return med(0), med(1), med(2), rows

def extras(rows):
    """median per FX_KEYS figure over `f` rows that carried them (older firmware: {})."""
    rows = [r for r in rows if len(r) == 3 + len(FX_KEYS)]
    return {k: statistics.median(r[3 + i] for r in rows) for i, k in enumerate(FX_KEYS)} if rows else {}

def parse_tilt(reply):
    """`s` -> (along, across, gyro) or None."""
    m = re.search(r'along (\S+) across (\S+) gyro (\S+)', reply)
    if not m: return None
    try: return tuple(float(x) for x in m.groups())
    except ValueError: return None

STAND_POSE = (-0.976, -0.01, 0.22)   # along, across, normal: the LCD board on its stand (IMU, 2026-11-22)

def parse_pose(ap, a):
    """--pose / --fix-pose -> None (IMU), 'flat' (legacy g 0 0 + inputGain 0) or (along, across, normal)."""
    if a.pose is None: return 'flat' if a.fix_pose else None
    if a.fix_pose and a.pose != 'flat': ap.error('--fix-pose is --pose flat: give one of them')
    if a.pose in ('flat', 'stand'): return 'flat' if a.pose == 'flat' else STAND_POSE
    try: v = tuple(float(x) for x in a.pose.split(','))
    except ValueError: v = ()
    if len(v) != 3: ap.error(f'--pose {a.pose}: flat, stand or along,across,normal')
    return v

FX = re.compile(r'cores h (\S+) / m (\S+) ms.*frame-p95 (\d+) ms\s+phys (\S+) steps x \(tube (\S+) \+ fizz (\S+) ms, max (\S+)\)')
FX_KEYS = ('core_h', 'core_m', 'p95', 'steps', 'tube_ms', 'fizz_ms', 'fizz_max')

def spread(xs): return f'{min(xs):.2f}–{max(xs):.2f}'

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port'); ap.add_argument('--scene', default='10:09:30')
    ap.add_argument('--samples', type=int, default=5); ap.add_argument('--settle', type=float, default=4)
    ap.add_argument('--stages', nargs='?', const='all', default=None, metavar='LIST',
                    help='per-stage costs: all default stages, or a comma list of names from the default table (e.g. fizz,digits)')
    ap.add_argument('--stage', action='append', default=[])
    ap.add_argument('--quick', action='store_true', help='3 base samples, 2 per stage, settle 2 s / 1 s (about half the time; +-0.1 ms noisier)')
    ap.add_argument('--preset', help='preset JSON (e.g. ../presets/cola.json) loaded before the pins')
    ap.add_argument('--fix-pose', action='store_true', help='tilt override: slug home (g -0.5 0, 4 s), then g 0 0 (4 s) before the pins (= --pose flat)')
    ap.add_argument('--pose', help='flat (= --fix-pose) | stand | along,across,normal: tilt override with the signed normal for the whole bench')
    ap.add_argument('--live-imu', action='store_true', help='do not pin inputGain=0')
    ap.add_argument('--allow-dead-imu', action='store_true', help='accept along/across/gyro all 0 (no reboot, no exit 3)')
    ap.add_argument('--runs', type=int, default=1, help='repeat base + stages N times; median and spread across runs')
    ap.add_argument('--label', default=''); ap.add_argument('--json', action='store_true')
    ap.add_argument('--ble-window', action='store_true', help='bench the BLE window (no switch to fast mode)')
    a = ap.parse_args()
    stage_samples, stage_settle = max(3, a.samples - 2), 1.5
    if a.quick:
        if a.samples == 5: a.samples = 3
        if a.settle == 4: a.settle = 2
        stage_samples, stage_settle = 2, 1
    if a.runs < 1: ap.error('--runs must be >= 1')
    pose = parse_pose(ap, a)
    preset = None
    if a.preset:
        with open(a.preset) as fh: preset = json.load(fh)
    stages = []
    if a.stages == 'all': stages = list(DEFAULT_STAGES)
    elif a.stages:
        table = dict(DEFAULT_STAGES)
        for name in a.stages.split(','):
            if name not in table: raise SystemExit(f'bench.py: --stages {name}: not a default stage ({", ".join(table)})')
            stages.append((name, table[name]))
    for s in a.stage:
        k, v = s.split('=', 1); stages.append((k, v))

    dev = [device.Device(a.port)]           # a list so a reconnect after `r` can swap it
    talk = lambda cmd, **kw: dev[0].talk(cmd, **kw)
    def reboot(cmd='r'):
        try: talk(cmd, timeout=3)
        except Exception: pass
        deadline = time.monotonic() + REBOOT_TIMEOUT_S
        time.sleep(2)
        while time.monotonic() < deadline:
            try:
                if parse_tilt(talk('s', timeout=2)) is not None: return
            except Exception:              # the port dropped with the reset: reopen it
                try: dev[0].close()
                except Exception: pass
                try: dev[0] = device.Device(a.port)
                except BaseException: pass
            time.sleep(1)
        raise SystemExit(f'bench.py: the board did not answer `s` within {REBOOT_TIMEOUT_S} s after `{cmd}`')
    mode = re.search(r' ble (on|off)', talk('s'))
    if mode and mode.group(1) == 'on' and not a.ble_window:
        print('bench.py: board in its BLE window: rebooting into fast mode (B0)', file=sys.stderr)
        reboot('B0')
        mode = re.search(r' ble (on|off)', talk('s'))
        if not mode or mode.group(1) != 'off': raise SystemExit('bench.py: the board did not come back in fast mode after B0')
    mode_txt = '' if not mode else ('  BLE window' if mode.group(1) == 'on' else '  fast mode')
    snap = json.loads(talk('p?').splitlines()[-1])
    cur = dict(snap)                         # what the board holds now (the stage "on" values)
    touched = set()
    def setp(k, v):
        touched.add(k)
        r = dev[0].set(k, fmt(v))
        if r.strip() != f'ok {k}': print(f'bench.py: p{k}={fmt(v)} -> {r!r}', file=sys.stderr)
        cur[k] = v
    preset_keys = []
    if preset is not None:
        preset_keys = [k for k in preset if k != 'v' and k in snap]
        unknown = [k for k in preset if k != 'v' and k not in snap]
        if unknown: print(f'bench.py: preset keys unknown to the board, skipped: {" ".join(unknown)}', file=sys.stderr)
    def pin():
        n = 0
        for k in preset_keys:
            if not same(cur[k], preset[k]): setp(k, preset[k]); n += 1
        talk('l', timeout=1); talk(f't {a.scene}'); talk('d0')   # `l` prints nothing: do not wait 10 s for it
        if pose is not None and same(cur['inputGain'], 0): setp('inputGain', 1)   # the prep tilt has to reach the liquid
        if pose == 'flat':
            talk('g -0.5 0'); time.sleep(4); talk('g 0 0'); time.sleep(4)
        elif pose is not None:
            talk(f'g {pose[0]} {pose[1]} 0 0 {pose[2]}'); time.sleep(8)
        if pose is None or pose == 'flat':
            if not a.live_imu and not same(cur['inputGain'], 0): setp('inputGain', 0)
        return n
    def read_tilt(tries=3):
        tilt = None
        for i in range(tries):   # the first `s` after boot can precede the first IMU poll
            tilt = parse_tilt(talk('s'))
            if tilt is None or any(tilt): return tilt
            if i + 1 < tries: time.sleep(0.5)
        return tilt

    result = {'scene': a.scene, 'label': a.label, 'preset': a.preset, 'runs': a.runs}
    try:
        n = pin()
        if preset is not None: print(f'bench.py: preset {a.preset}: {n} of {len(preset_keys)} params written', file=sys.stderr)
        tilt = read_tilt()
        dead = lambda t: t is not None and not any(t)
        if pose is not None:
            pass                           # the override: nothing to check
        elif dead(tilt) and a.allow_dead_imu:
            print('bench.py: IMU reads exactly 0 (dead) - allowed by --allow-dead-imu', file=sys.stderr)
        elif dead(tilt):
            print('bench.py: WARNING: IMU reads exactly 0 (along/across/gyro) - dead after flash? rebooting with `r`',
                  file=sys.stderr)
            reboot('B1' if mode and mode.group(1) == 'on' else 'B0')   # keeps the mode it benches
            cur = dict(json.loads(talk('p?').splitlines()[-1]))   # NVS state after the reboot; restore target stays `snap`
            pin(); time.sleep(1)
            tilt = read_tilt()
            if dead(tilt):
                print('bench.py: IMU still dead after a reboot (along/across/gyro exactly 0); the scene would not be '
                      'comparable. Power-cycle the board, or pass --allow-dead-imu.', file=sys.stderr)
                raise SystemExit(EXIT_DEAD_IMU)
            print('bench.py: IMU alive after the reboot', file=sys.stderr)
        if tilt is None: print('bench.py: WARNING: could not parse the tilt from `s`', file=sys.stderr)
        tilt_txt = 'tilt ?' if tilt is None else f'tilt along {tilt[0]:.3f} across {tilt[1]:.3f} gyro {tilt[2]:.1f}'
        imu_txt = 'IMU live' if a.live_imu else 'IMU pinned'
        if isinstance(pose, tuple): imu_txt = f'pose {a.pose} (g {pose[0]} {pose[1]} 0 0 {pose[2]}, inputGain {fmt(cur["inputGain"])})'
        elif a.live_imu:
            imu_txt += f' (inputGain {fmt(cur["inputGain"])})'
            if same(cur['inputGain'], 0): print('bench.py: WARNING: --live-imu but inputGain is 0', file=sys.stderr)
        if pose == 'flat': imu_txt += ', pose fixed (g 0 0)'
        elif dead(tilt): imu_txt += ', IMU dead'
        result.update(tilt=None if tilt is None else dict(zip(('along', 'across', 'gyro'), tilt)), imu=imu_txt)
        print(f'{a.label + ": " if a.label else ""}scene {a.scene}  preset {a.preset or "(board NVS)"}  {tilt_txt}  '
              f'{imu_txt}  runs {a.runs}{mode_txt}')

        per_run = []
        for run in range(a.runs):
            if a.runs > 1: print(f'bench.py: run {run + 1}/{a.runs}', file=sys.stderr)
            fps, ren, wait, rows = sample(dev[0], a.samples, a.settle)
            base_f = LAST_F
            rr = {'fps': fps, 'render_ms': ren, 'wait_ms': wait, 'samples': rows, 'stages': {}, **extras(rows)}
            if len(REFILLS) > 1:   # totals since boot: count what happened between the first and the last `f`
                rr['refill'] = {'late': REFILLS[-1][0] - REFILLS[0][0], 'restarts': REFILLS[-1][1] - REFILLS[0][1],
                                'worst_pct': max(x[2] for x in REFILLS[1:]), 'seconds': 2.1 * (len(REFILLS) - 1)}
            for k, v in stages:
                if k not in cur or same(cur[k], v): continue
                on = cur[k]
                setp(k, v)
                f2, r2, _, _ = sample(dev[0], stage_samples, stage_settle)
                setp(k, on)
                rr['stages'][k] = {'fps': f2, 'render_ms': r2, 'cost_ms': ren - r2}
            per_run.append(rr)
        med = lambda xs: statistics.median(xs)
        fps, ren, wait = (med([r[f] for r in per_run]) for f in ('fps', 'render_ms', 'wait_ms'))
        rens = [r['render_ms'] for r in per_run]
        result.update(fps=fps, render_ms=ren, wait_ms=wait, render_spread=[min(rens), max(rens)], per_run=per_run)
        if a.runs == 1:
            rows = per_run[0]['samples']
            print(f'{a.label + ": " if a.label else ""}fps {fps:.1f}  render {ren:.2f} ms  push-wait {wait:.2f} ms  '
                  f'(scene {a.scene}, median of {a.samples}; spread {min(r[0] for r in rows):.1f}–{max(r[0] for r in rows):.1f})')
        else:
            print(f'{a.label + ": " if a.label else ""}fps {fps:.1f}  render {ren:.2f} ms  push-wait {wait:.2f} ms  '
                  f'(scene {a.scene}, median of {a.runs} runs x {a.samples}; render across runs {spread(rens)} ms)')
        ex = [r for r in per_run if 'fizz_ms' in r]
        if ex:
            m = {k: med([r[k] for r in ex]) for k in FX_KEYS}; result.update(m)
            print(f'{a.label + ": " if a.label else ""}cores h {m["core_h"]:.2f} / m {m["core_m"]:.2f} ms  frame-p95 {m["p95"]:.0f} ms  '
                  f'phys {m["steps"]:.2f} steps x (tube {m["tube_ms"]:.2f} + fizz {m["fizz_ms"]:.2f} ms, max {m["fizz_max"]:.2f})  '
                  f'(median{f" of {a.runs} runs" if a.runs > 1 else ""}; fizz per run {spread([r["fizz_ms"] for r in ex])}, '
                  f'p95 per run {spread([r["p95"] for r in ex])})')
        print(f'{a.label + ": " if a.label else ""}last f: {base_f}')
        refills = [r['refill'] for r in per_run if 'refill' in r]
        if refills:
            late, restarts = sum(r['late'] for r in refills), sum(r['restarts'] for r in refills)
            worst, secs = max(r['worst_pct'] for r in refills), sum(r['seconds'] for r in refills)
            result['refill'] = {'late': late, 'restarts': restarts, 'worst_pct': worst, 'seconds': secs}
            print(f'{a.label + ": " if a.label else ""}panel refills: {"OK" if late + restarts == 0 else "TWITCH"}  '
                  f'late {late}  restarts {restarts}  over {secs:.0f} s  (worst refill {worst}% of its deadline)')
        if stages:
            multi = a.runs > 1
            print(f'{"stage off":22} {"fps":>6} {"render":>8} {"cost ms":>8}' + (f' {"cost min–max":>13}' if multi else ''))
            result['stages'] = {}
            for k, v in stages:
                if k not in cur: print(f'{k:22} (unknown param)'); continue
                if same(cur[k], v): print(f'{k:22} already {fmt(v)}'); continue
                rs = [r['stages'][k] for r in per_run]
                f2, r2, c = (med([s[f] for s in rs]) for f in ('fps', 'render_ms', 'cost_ms'))
                costs = [s['cost_ms'] for s in rs]
                result['stages'][k] = {'fps': f2, 'render_ms': r2, 'cost_ms': c, 'cost_min': min(costs), 'cost_max': max(costs)}
                print(f'{k + "=" + fmt(v):22} {f2:6.1f} {r2:8.2f} {c:+8.2f}' + (f' {spread(costs):>13}' if multi else ''))
    finally:
        for k in touched: dev[0].set(k, fmt(snap[k]))
        talk('d1')
        if pose is not None: talk('g')
        # Without `p~` the pins were autosaved mid-bench: device.py holds the session past the autosave on close,
        # so the restored values replace them.
        talk('s'); dev[0].close()
    if a.json: print(json.dumps(result))

if __name__ == '__main__': main()
