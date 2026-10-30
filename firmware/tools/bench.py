#!/usr/bin/env python3
"""fps benchmark on the board, in a pinned scene so runs are comparable.

  tools/bench.py [--scene 10:09:30] [--samples 5] [--settle 4] [--stages [LIST]] [--stage name=value ...] [--quick]
                 [--preset FILE.json] [--live-imu] [--allow-dead-imu] [--runs N] [--label TEXT] [--json]

Pins: optional preset (--preset: every key of the JSON the board knows, written with `p<name>=<v>`; `v` and
unknown keys are skipped and listed once), clock fixed (`t`), demo frozen (`d0`), IMU influence off
(`pinputGain=0`, unless --live-imu), waits for the physics to settle, then reads `f` once per 2 s window and
reports the median fps / render ms / push-wait ms. LCD board: also the panel refill health over the base samples
(`f` refill totals, display.h display_refill_health): late refills = twitches, restarts = bad frames; any -> TWITCH.
--preset: a flash that changes PARAMS_SCHEMA_CRC resets NVS to presets/1.json, so benches across a Params
change are only comparable with a pinned preset.
IMU check: after pinning, `s` is read; along/across/gyro all exactly 0 = the "IMU dead after flash" signature.
The board is then rebooted (`r`), the pins are re-applied and `s` re-checked once; still dead -> exit code 3.
--allow-dead-imu accepts a dead IMU without the reboot (e.g. -DNO_IMU / --bare builds). The tilt goes in the
header line either way, because even the pinned scene depends on it.
--live-imu: inputGain is not pinned (the board's / preset's value stays), for moving-light cases
(e.g. `--live-imu --stage fizz=0`).
--stages additionally turns rendering stages off one at a time (digits, ticks, fizz, glow, ...) and prints what
each costs. --runs N repeats the whole measurement (base + stages) N times and reports, per line, the median
across runs and the min-max spread across runs (fizz positions are random: ~±0.5 ms per run on heavy presets).
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
        for _ in range(3):   # the serial bridge now and then returns an empty reply: ask again
            r = d.talk('f')  # "fps 19.8  render 46.48 ms  push-wait 0.02 ms  (...)"
            t = r.split()
            if len(t) > 6 and t[0] == 'fps': break
        else: raise SystemExit(f'bench.py: no parsable `f` reply after 3 tries: {r!r}')
        rows.append((float(t[1]), float(t[3]), float(t[6])))
        LAST_F = r.strip()
        m = re.search(r'refill late (\d+) restarts (\d+) worst (\d+)%', r)
        if m: REFILLS.append(tuple(int(x) for x in m.groups()))
    med = lambda i: statistics.median(r[i] for r in rows)
    return med(0), med(1), med(2), rows

def parse_tilt(reply):
    """`s` -> (along, across, gyro) or None."""
    m = re.search(r'along (\S+) across (\S+) gyro (\S+)', reply)
    if not m: return None
    try: return tuple(float(x) for x in m.groups())
    except ValueError: return None

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
    ap.add_argument('--live-imu', action='store_true', help='do not pin inputGain=0')
    ap.add_argument('--allow-dead-imu', action='store_true', help='accept along/across/gyro all 0 (no reboot, no exit 3)')
    ap.add_argument('--runs', type=int, default=1, help='repeat base + stages N times; median and spread across runs')
    ap.add_argument('--label', default=''); ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    stage_samples, stage_settle = max(3, a.samples - 2), 1.5
    if a.quick:
        if a.samples == 5: a.samples = 3
        if a.settle == 4: a.settle = 2
        stage_samples, stage_settle = 2, 1
    if a.runs < 1: ap.error('--runs must be >= 1')
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
    snap = json.loads(talk('p?').splitlines()[-1])
    cur = dict(snap)                         # what the board holds now (the stage "on" values)
    touched = set()
    def setp(k, v):
        touched.add(k)
        r = talk(f'p{k}={fmt(v)}')
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
        talk('l'); talk(f't {a.scene}'); talk('d0')
        if not a.live_imu and not same(cur['inputGain'], 0): setp('inputGain', 0)
        return n
    def read_tilt(tries=3):
        tilt = None
        for i in range(tries):   # the first `s` after boot can precede the first IMU poll
            tilt = parse_tilt(talk('s'))
            if tilt is None or any(tilt): return tilt
            if i + 1 < tries: time.sleep(0.5)
        return tilt
    def reboot():
        try: talk('r', timeout=3)
        except Exception: pass
        deadline = time.time() + REBOOT_TIMEOUT_S
        time.sleep(2)
        while time.time() < deadline:
            try:
                if parse_tilt(talk('s', timeout=2)) is not None: return
            except Exception:              # the port dropped with the reset: reopen it
                try: dev[0].close()
                except Exception: pass
                try: dev[0] = device.Device(a.port)
                except BaseException: pass
            time.sleep(1)
        raise SystemExit(f'bench.py: the board did not answer `s` within {REBOOT_TIMEOUT_S} s after `r`')

    result = {'scene': a.scene, 'label': a.label, 'preset': a.preset, 'runs': a.runs}
    try:
        n = pin()
        if preset is not None: print(f'bench.py: preset {a.preset}: {n} of {len(preset_keys)} params written', file=sys.stderr)
        tilt = read_tilt()
        dead = lambda t: t is not None and not any(t)
        if dead(tilt) and a.allow_dead_imu:
            print('bench.py: IMU reads exactly 0 (dead) - allowed by --allow-dead-imu', file=sys.stderr)
        elif dead(tilt):
            print('bench.py: WARNING: IMU reads exactly 0 (along/across/gyro) - dead after flash? rebooting with `r`',
                  file=sys.stderr)
            reboot()
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
        if a.live_imu:
            imu_txt += f' (inputGain {fmt(cur["inputGain"])})'
            if same(cur['inputGain'], 0): print('bench.py: WARNING: --live-imu but inputGain is 0', file=sys.stderr)
        if dead(tilt): imu_txt += ', IMU dead'
        result.update(tilt=None if tilt is None else dict(zip(('along', 'across', 'gyro'), tilt)), imu=imu_txt)
        print(f'{a.label + ": " if a.label else ""}scene {a.scene}  preset {a.preset or "(board NVS)"}  {tilt_txt}  '
              f'{imu_txt}  runs {a.runs}')

        per_run = []
        for run in range(a.runs):
            if a.runs > 1: print(f'bench.py: run {run + 1}/{a.runs}', file=sys.stderr)
            fps, ren, wait, rows = sample(dev[0], a.samples, a.settle)
            base_f = LAST_F
            rr = {'fps': fps, 'render_ms': ren, 'wait_ms': wait, 'samples': rows, 'stages': {}}
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
        for k in touched: talk(f'p{k}={fmt(snap[k])}')
        talk('d1')
        # The board autosaves params to NVS 2 s after the last write, so the pinned values (inputGain 0)
        # were saved mid-bench; hold the session past the autosave so the restored ones replace them.
        time.sleep(2.5); talk('s'); dev[0].close()
    if a.json: print(json.dumps(result))

if __name__ == '__main__': main()
