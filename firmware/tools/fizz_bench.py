#!/usr/bin/env python3
"""Fizz load bench on the board: a full tube at 120 / 240 / 480 bubbles, pinned and swinging, plus a spring.

  tools/fizz_bench.py [--preset bench/user-fav.json] [--counts 120,240,480] [--no-swing] [--no-spring] [--prof]
                      [--flash BIN] [--label TEXT] [--json]

Scene (docs/fizz-perf-handoff.md): the preset pinned (volatile `p~`), `l`, clock 11:59:30 frozen (`d0`: both tubes
full), tilt override `g -0.5 0` 4 s then `g 0 0` 4 s, `fizzSource 0` (scattered). Per count: `fizzCount`, `g 0 0`,
5 s; pinned = `f`, 6 s, `f`; swinging = `f`, `g -0.5 0` / `g 0.5 0` alternating every 1.5 s for 8 s, `f`. Spring:
`fizzSource 1`, `fizzSourceRate 20`, count 240, (count / 20 + 3) s, then the pinned reading.
--prof: a -DFIZZ_PROF build; the pinned (and swinging) readings also print its fizz-prof / fizz-step lines (counters
since the previous `f`, i.e. over the 6 s / 8 s window).
--flash BIN: write BIN (an lcd316 firmware.bin, app only, NVS kept) through Windows' esptool before the bench, so two
saved builds can be benched alternately in one session (the I-cache layout moves the render between builds).
Every touched param is restored from the `p?` snapshot (volatile, NVS untouched), demo speed back to x1, the tilt
override released, and the clock set to real time (`T <epoch> <tz_min>`).
"""
import argparse, json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import device

F = re.compile(r'fps (\S+)\s+render (\S+) ms.*cores h (\S+) / m (\S+) ms.*frame-p95 (\d+) ms\s+phys (\S+) steps x '
               r'\(tube (\S+) \+ fizz (\S+) ms, max (\S+)\).*?push (\S+) ms.*fizz h (\d+) \(foam (\d+), slots (\d+)\) m (\d+) \(foam (\d+), slots (\d+)\)')
KEYS = ('fps', 'render', 'core_h', 'core_m', 'p95', 'steps', 'tube_ms', 'fizz_ms', 'fizz_max', 'push',
        'live_h', 'foam_h', 'slots_h', 'live_m', 'foam_m', 'slots_m')
HERE = os.path.dirname(os.path.abspath(__file__))

def fmt(v):
    if isinstance(v, bool): return '1' if v else '0'
    if isinstance(v, float) and v.is_integer(): return str(int(v))
    return str(v)

def same(a, b): return fmt(a).lower() == fmt(b).lower()

def parse(reply):
    m = F.search(reply)
    if not m: raise SystemExit(f'fizz_bench.py: no parsable `f` reply: {reply[:300]!r}')
    return {k: float(v) for k, v in zip(KEYS, m.groups())}

def flash(binpath, port):
    if not port.upper().startswith('COM'): raise SystemExit('fizz_bench.py: --flash needs a Windows COMx port')
    subprocess.run(['python.exe', '-m', 'esptool', '--chip', 'esp32s3', '--port', port, '--baud', '921600',
                    'write-flash', '0x10000', subprocess.run(['wslpath', '-w', os.path.abspath(binpath)], capture_output=True,
                                                             text=True, check=True).stdout.strip()], check=True)
    time.sleep(6)   # boot

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port'); ap.add_argument('--preset', default=os.path.join(HERE, '..', 'bench', 'user-fav.json'))
    ap.add_argument('--counts', default='120,240,480'); ap.add_argument('--no-swing', action='store_true')
    ap.add_argument('--no-spring', action='store_true'); ap.add_argument('--prof', action='store_true')
    ap.add_argument('--flash', metavar='BIN'); ap.add_argument('--label', default=''); ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    counts = [int(c) for c in a.counts.split(',') if c]
    port = a.port or device.find_port()
    if a.flash: flash(a.flash, port)
    with open(a.preset) as fh: preset = json.load(fh)

    d = device.Device(port)
    snap = json.loads(d.talk('p?', ok=lambda r: r.rstrip().endswith('}')).splitlines()[-1])
    cur = dict(snap); touched = set()
    def setp(k, v):
        touched.add(k); r = d.set(k, fmt(v))
        if r.strip() != f'ok {k}': print(f'fizz_bench.py: p~{k}={fmt(v)} -> {r!r}', file=sys.stderr)
        cur[k] = v
    def setv(k, v):
        if not same(cur.get(k), v): setp(k, v)
    end = 'fizz-step steps' if a.prof else '\n'
    def reading():
        r = d.talk('f', end=end, ok=lambda r: F.search(r) is not None and (not a.prof or 'fizz-step steps' in r))
        return parse(r), [l for l in r.splitlines() if l.startswith(('fizz-prof', 'fizz-step'))]
    def pinned(wait=6):
        d.talk('g 0 0'); d.talk('f', end=end); time.sleep(wait); return reading()
    def swinging():
        d.talk('f', end=end); t0 = time.monotonic(); k = 0
        while time.monotonic() - t0 < 8:
            d.talk('g -0.5 0' if k % 2 == 0 else 'g 0.5 0'); k += 1
            time.sleep(max(0, t0 + 1.5 * k - time.monotonic()))
        r = reading(); d.talk('g 0 0'); return r
    def line(name, r):
        return (f'{name:>10}  fps {r["fps"]:5.1f}  core h {r["core_h"]:5.1f} m {r["core_m"]:5.1f}  push {r["push"]:5.2f}  '
                f'steps {r["steps"]:4.2f} x fizz {r["fizz_ms"]:5.2f} (max {r["fizz_max"]:5.2f})  '
                f'live/foam/slots h {int(r["live_h"])}/{int(r["foam_h"])}/{int(r["slots_h"])} m {int(r["live_m"])}/{int(r["foam_m"])}/{int(r["slots_m"])}')
    result = {'label': a.label, 'board': d.talk('v'), 'flash': a.flash, 'rows': []}
    try:
        unknown = [k for k in preset if k != 'v' and k not in snap]
        if unknown: print(f'fizz_bench.py: preset keys unknown to the board, skipped: {" ".join(unknown)}', file=sys.stderr)
        for k in preset:
            if k != 'v' and k in snap: setv(k, preset[k])
        if same(cur.get('inputGain'), 0): setp('inputGain', 1)   # the tilt override has to reach the liquid
        d.talk('l', timeout=1); d.talk('t 11:59:30'); d.talk('d0')
        d.talk('g -0.5 0'); time.sleep(4); d.talk('g 0 0'); time.sleep(4)
        setv('fizzSource', 0)
        print(f'# fizz_bench {a.label}  {result["board"]}  preset {os.path.basename(a.preset)}' + (f'  flash {a.flash}' if a.flash else ''), flush=True)
        def emit(name, count, kind, rp):
            r, prof = rp
            result['rows'].append({'name': name, 'count': count, 'kind': kind, **r, 'prof': prof})
            print(line(name, r), flush=True)
            for l in prof: print('            ' + l, flush=True)
        for c in counts:
            setv('fizzCount', c); d.talk('g 0 0'); time.sleep(5)
            emit(f'{c} pin', c, 'pinned', pinned())
            if not a.no_swing: emit(f'{c} swing', c, 'swinging', swinging())
        if not a.no_spring:
            setv('fizzSource', 1); setv('fizzSourceRate', 20); setv('fizzCount', 240); d.talk('g 0 0')
            time.sleep(240 / 20 + 3)
            emit('240 spring', 240, 'spring', pinned())
    finally:
        for k in touched: d.set(k, fmt(snap[k]))
        d.talk('d1'); d.talk('g')
        lt = time.localtime(); d.talk(f'T {int(time.time())} {lt.tm_gmtoff // 60}')
        d.close()
    if a.json: print(json.dumps(result))

if __name__ == '__main__': main()
