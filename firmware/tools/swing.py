#!/usr/bin/env python3
"""Swing the tilt via `g` (like tools/tilt.py) and print the push-relevant fields of each 2 s `f` window.
   swing.py PORT HOLD_S 'a1,c1>a2,c2@T'   e.g. swing.py COM11 40 '-1,0>0.6,0@3' (after a bench: the clock stays pinned)"""
import os, re, statistics, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import device

port, hold, ps = sys.argv[1], float(sys.argv[2]), sys.argv[3]
ab, T = ps.split('@'); p1, p2 = ab.split('>'); T = float(T)
poses = [tuple(map(float, p1.split(','))), tuple(map(float, p2.split(',')))]
pat = re.compile(r'fps (\S+).*cores h (\S+) / m (\S+) ms.*frame-p95 (\d+) ms.*push (\S+) ms.*refill late (\d+) restarts (\d+) worst (\d+)%(.*)')
fpss = []; pushes = []
with device.Device(port) as d:
    try:
        t0 = time.monotonic(); report = t0 + 4.2; flip = 0; turn = t0
        while time.monotonic() - t0 < hold:
            if time.monotonic() >= turn:
                al, ac = poses[flip % 2]; d.talk(f'g {al} {ac}'); flip += 1; turn = time.monotonic() + T / 2
            if time.monotonic() >= report:
                r = d.talk('f'); m = pat.search(r)
                if m:
                    g = m.groups(); fpss.append(float(g[0])); pushes.append(float(g[4]))
                    print(f't={time.monotonic()-t0:5.1f} fps {g[0]} cores h {g[1]} / m {g[2]} p95 {g[3]} push {g[4]} refill late {g[5]} restarts {g[6]} worst {g[7]}%{g[8]}', flush=True)
                else: print('?', r.strip(), flush=True)
                report = time.monotonic() + 2.2
            time.sleep(0.05)
    finally:
        print(d.talk('g').strip())
if fpss: print(f'median fps {statistics.median(fpss):.1f} push {statistics.median(pushes):.2f} ms over {len(fpss)} windows')
