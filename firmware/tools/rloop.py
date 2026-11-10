#!/usr/bin/env python3
"""Reboot loop: `r` N times, one port session each, and tally how each restart went.

  tools/rloop.py [--port COM11] [-n 10] [PRE_CMD ...]     PRE_CMD: sent before every `r` (e.g. 'p~fizz=0')

Per restart: what the port did (kept; reenum = dropped once and re-opened within device.REOPEN_S, the LCD firmware's
USB re-enumeration after a CPU-only reset, diag.cpp; drop = gone for longer, as when a hung restart ends in a system
reset), the ROM's `rst:` reason and saved PC (printed before the re-enumeration), the boot banner's `reset <reason>`
(after it), and the free heap from `s` after the boot. The tally at the end counts the outcomes.
--stop-on-fail: exit 1 at once on the first restart that is not clean (check_restart: the port gone or dropped more
than once, more than one boot banner or ROM reset line, a reason other than sw, no single `ready.` after the banner,
any panic / watchdog text; no follow-up `s`, no further restarts): run Step W of docs/hang-investigation-plan.md next.
Use it as `-n 1 --stop-on-fail`, one announced restart per run.
"""
import argparse, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from device import Device, PORT_LOST, PORT_BACK, PORT_GONE, REOPEN_S

# A clean `r`: the port kept, or dropped once and back (the re-enumeration); one ROM reset line at most, and that one
# RTC_SW_CPU_RST; exactly one boot banner, with reason sw; exactly one `ready.`, after that banner; no panic / watchdog /
# abort text anywhere in between.
FAIL_TEXT = ('Guru Meditation', 'abort()', 'Backtrace:', 'Rebooting...', 'panic', 'task_wdt', 'Task watchdog',
             'Interrupt wdt', 'Stack canary', 'stack overflow', 'FATAL', 'STACK GUARD', 'CPU halted')

def check_restart(out):
    """(ok, why) for the transcript of one `r`, from the command up to (and including) `ready.`, with device.py's
    PORT_LOST / PORT_BACK / PORT_GONE lines where the port dropped."""
    if PORT_GONE in out: return False, f'port dropped, not back within {REOPEN_S} s'
    drops = out.count(PORT_LOST)
    if drops > 1: return False, f'port dropped {drops} times'
    if drops and PORT_BACK not in out: return False, 'port dropped, not re-opened'
    banners = list(re.finditer(r'liquid-watch \|.*\| reset (\S+)', out))
    roms = re.findall(r'rst:(0x[0-9a-f]+) \((\w+)\)', out)
    if len(banners) != 1: return False, f'{len(banners)} boot banners'
    if banners[0].group(1) != 'sw': return False, f'banner reason {banners[0].group(1)}'
    if len(roms) > 1: return False, f'{len(roms)} ROM reset lines'
    if roms and roms[0][1] != 'RTC_SW_CPU_RST': return False, f'ROM reset {roms[0][1]}'
    if out.count('ready.') != 1: return False, f"{out.count('ready.')} 'ready.' lines"
    if out.index('ready.') < banners[0].end(): return False, "'ready.' before the boot banner"
    bad = [t for t in FAIL_TEXT if t in out]
    if bad: return False, 'failure text: ' + ', '.join(bad)
    return True, 'ok'

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port'); ap.add_argument('-n', type=int, default=10); ap.add_argument('pre', nargs='*')
    ap.add_argument('--stop-on-fail', action='store_true', help='exit 1 on the first failed restart, before anything else touches the port')
    a = ap.parse_args()
    tally = {}
    for i in range(a.n):
        rom = app = pc = '-'; dropped = False; out = ''
        d = Device(a.port)
        try:
            for c in a.pre: d.raw(c, '\n', 3)
            out = d.raw('r', 'ready.', 15, reopen=REOPEN_S)
            dropped = PORT_GONE in out
            m = re.search(r'rst:(0x[0-9a-f]+) \((\w+)\)', out); rom = m.group(2) if m else '-'
            m = re.search(r'Saved PC:(0x[0-9a-f]+)', out); pc = m.group(1) if m else '-'
            m = re.search(r'liquid-watch \|.*\| reset (\S+)', out); app = m.group(1) if m else '-'
        except (RuntimeError, OSError):   # the bridge died with the port (not re-opened)
            dropped = True
        ok, why = (False, 'port dropped') if dropped and not out else check_restart(out)
        port = 'drop' if dropped else 'reenum' if PORT_LOST in out else 'kept'
        if a.stop_on_fail and not ok:
            print(i, f'FAILED restart ({why}): port {port} rom {rom} pc {pc} app {app}: stopping (Step W next)', flush=True)
            try: d.close()
            except Exception: pass
            sys.exit(1)
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
        k = f'{port} rom {rom} app {app}'
        tally[k] = tally.get(k, 0) + 1
        heap = re.search(r'heap (\d+)', s)
        print(i, k, '| pc', pc, '| heap', heap.group(1) if heap else s[:80], flush=True)
        time.sleep(2)
    for k, n in sorted(tally.items()): print(f'{n:4}  {k}')

if __name__ == '__main__':
    main()
