#!/usr/bin/env python3
"""Reboot loop: `r` N times, one port session each, and tally how each restart went.

  tools/rloop.py [--port COM11] [-n 10] [PRE_CMD ...]     PRE_CMD: sent before every `r` (e.g. 'p~fizz=0')

Per restart: whether the port survived it (kept) or dropped (a hung restart ends in a system reset, which drops the
USB port and loses the ROM line and the banner), the ROM's `rst:` reason and saved PC when the port survived, the boot banner's
`reset <reason>`, and the free heap from `s` after the boot. The tally at the end counts the outcomes.
"""
import argparse, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from device import Device

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port'); ap.add_argument('-n', type=int, default=10); ap.add_argument('pre', nargs='*')
    a = ap.parse_args()
    tally = {}
    for i in range(a.n):
        rom = app = pc = '-'; dropped = False
        d = Device(a.port)
        try:
            for c in a.pre: d.raw(c, '\n', 3)
            out = d.raw('r', 'ready.', 15)
            m = re.search(r'rst:(0x[0-9a-f]+) \((\w+)\)', out); rom = m.group(2) if m else '-'
            m = re.search(r'Saved PC:(0x[0-9a-f]+)', out); pc = m.group(1) if m else '-'
            m = re.search(r'liquid-watch \|.*\| reset (\S+)', out); app = m.group(1) if m else '-'
        except RuntimeError:   # the bridge died with the port
            dropped = True
        try: d.close()
        except Exception: pass
        time.sleep(4 if dropped else 1)
        s = ''
        for _ in range(10):
            try:
                with Device(a.port) as d2:
                    s = d2.talk('s', timeout=3)
                break
            except Exception as e:
                s = f'ERR {e}'; time.sleep(2)
        k = ('drop' if dropped else 'kept') + f' rom {rom} app {app}'
        tally[k] = tally.get(k, 0) + 1
        heap = re.search(r'heap (\d+)', s)
        print(i, k, '| pc', pc, '| heap', heap.group(1) if heap else s[:80], flush=True)
        time.sleep(2)
    for k, n in sorted(tally.items()): print(f'{n:4}  {k}')

if __name__ == '__main__':
    main()
