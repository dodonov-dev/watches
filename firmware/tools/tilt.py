#!/usr/bin/env python3
"""Tilt the board without touching it: scripted poses through the firmware's `g` override, one line per 2 s `f` window.

  tools/tilt.py [--hold 10] POSE [POSE ...]
    POSE = along,across              hold the pose (g units: upright vertical watch = -1,0; face up = 0,0)
           a1,c1>a2,c2@T             swing between two poses, T s per cycle

  tools/tilt.py --hold 60 '-1,0>0.6,0@3'        # pitch back and forth: a spring's bubbles stay in, the pool sits at its cap
  tools/tilt.py --hold 20 -0.97,0.1 0.6,0.2     # settle upright, then step to a pose

Each line: fps, render ms (per core), frame p95, physics steps per frame x (tube + fizz ms per step, worst fizz step),
per tube live bubbles / parked foam / pool slots; push ms and the panel refill totals where the firmware reports them
(LCD). The override is released (`g`) on exit; nothing is persisted.
"""
import argparse, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import device

F = re.compile(r'fps (\S+)\s+render (\S+) ms.*cores h (\S+) / m (\S+) ms.*frame-p95 (\d+) ms\s+phys (\S+) steps x '
               r'\(tube (\S+) \+ fizz (\S+) ms, max (\S+)\).*fizz h (\d+) \(foam (\d+), slots (\d+)\) m (\d+) \(foam (\d+), slots (\d+)\)')

PUSH = re.compile(r'\bpush (\S+) ms')
REFILL = re.compile(r'refill late (\d+) restarts (\d+) worst (\d+)%')

def short(reply):
    m = F.search(reply)
    if not m: return reply
    g = m.groups()
    out = (f'fps {g[0]:>5} render {g[1]:>6} (h {g[2]:>6} m {g[3]:>6}) p95 {g[4]:>3} | steps {g[5]} x (tube {g[6]} + fizz {g[7]:>5}, max {g[8]:>5})'
           f' | live/foam/slots h {g[9]:>3}/{g[10]:>3}/{g[11]:>3} m {g[12]:>3}/{g[13]:>3}/{g[14]:>3}')
    p, r = PUSH.search(reply), REFILL.search(reply)
    if p: out += f' | push {p.group(1):>5}'
    if r: out += f' | refill late {r.group(1)} restarts {r.group(2)} worst {r.group(3)}%'
    return out

def pose(s):
    a, c = s.split(','); return float(a), float(c)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port'); ap.add_argument('--hold', type=float, default=10, help='seconds per pose')
    a, poses = ap.parse_known_args()   # poses start with '-': not options
    if not poses: ap.error('no poses')
    a.poses = poses
    with device.Device(a.port) as d:
        try:
            for ps in a.poses:
                swing = None
                if '>' in ps:
                    ab, T = ps.split('@'); p1, p2 = ab.split('>'); swing = (pose(p1), pose(p2), float(T))
                t0 = time.monotonic(); report = t0 + 2.2; flip = 0; turn = t0
                while time.monotonic() - t0 < a.hold:
                    if time.monotonic() >= turn:
                        al, ac = swing[flip % 2] if swing else pose(ps)
                        d.talk(f'g {al} {ac}'); flip += 1
                        turn = time.monotonic() + swing[2] / 2 if swing else float('inf')
                    if time.monotonic() >= report:
                        print(f'{ps:>24} t={time.monotonic() - t0:5.1f}  {short(d.talk("f"))}', flush=True); report = time.monotonic() + 2.2
                    time.sleep(0.05)
        finally:
            print(d.talk('g'))

if __name__ == '__main__':
    main()
