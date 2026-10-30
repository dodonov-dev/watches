#!/usr/bin/env python3
"""Board A/B of two builds over the deterministic step sequence (`X`, firmware/src/seq.h): fizz, residue, memos.

  tools/check_board_steps.py [--port P] [--preset FILE.json] [--runs 2] --save FILE      # build A flashed
  tools/check_board_steps.py [--port P] [--preset FILE.json] [--runs 2] --compare FILE   # build B flashed

`X` restarts both tubes and the fizz from a fixed state (fizz draws reseeded; LCD only, the AMOLED draws from
esp_random), steps a fixed tilt script and prints a hash per tube per frame. Same params + same code = the same lines,
so a rewrite that should be exact (e.g. the fizz: the board fuses a * b + c, the host checks do not) is proven on the
board itself. --runs N runs it N times and requires the runs to agree first (the build is deterministic). --preset:
every key the board knows is pinned with volatile writes (`p~`) and restored afterwards. The tubes jump back to the
clock afterwards; nothing reaches NVS. Host counterpart: check_fizz_steps.py.
The USB serial path now and then loses a whole line of the ~14 KB reply (seen: 8 of 350): frames are keyed by number,
the runs are merged, and only frames both sides have are compared (each hash stands alone); a reply missing more
than 10 % is asked again.
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import device

def frames(text):
    """{frame: line} of the SEQ lines in text."""
    out = {}
    for l in text.splitlines():
        t = l.split()
        if len(t) > 2 and t[0] == 'SEQ' and t[1].isdigit(): out[int(t[1])] = l.strip()
    return out

def run_seq(d):
    total = lambda r: int(m.group(1)) if (m := re.search(r'SEQ END (\d+) frames', r)) else None
    enough = lambda r: total(r) is not None and len(frames(r)) >= 0.9 * total(r)
    r = d.talk('X', end='SEQ END', timeout=180, ok=enough)
    if not enough(r): raise SystemExit(f'check_board_steps: incomplete `X` reply ({len(r)} chars); firmware without `X`?')
    end = [l for l in r.splitlines() if l.startswith('SEQ END')][0]
    if 'unseeded' in end: print('check_board_steps: WARNING: fizz draws unseeded (esp_random): not reproducible', file=sys.stderr)
    f = frames(r)
    print(f'check_board_steps: {end.strip()}, {total(r) - len(f)} lines lost in transit', file=sys.stderr)
    return f, total(r)

def first_diff(a, b):
    """(line a, line b) at the first frame both have that differs, or None; and how many frames were compared."""
    common = sorted(set(a) & set(b))
    for k in common:
        if a[k] != b[k]: return (a[k], b[k]), len(common)
    return None, len(common)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port'); ap.add_argument('--preset'); ap.add_argument('--runs', type=int, default=2)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--save'); g.add_argument('--compare')
    a = ap.parse_args()
    with device.Device(a.port) as d:
        board = d.talk('v')
        snap = json.loads(d.talk('p?', ok=lambda r: r.strip().endswith('}')).splitlines()[-1])
        touched = []
        try:
            if a.preset:
                preset = json.load(open(a.preset))
                for k, v in preset.items():
                    if k == 'v' or k not in snap: continue
                    v = ('1' if v else '0') if isinstance(v, bool) else str(v)
                    if d.set(k, v).strip() != f'ok {k}': print(f'check_board_steps: {k}={v} refused', file=sys.stderr)
                    touched.append(k)
            runs = [run_seq(d) for _ in range(a.runs)]
        finally:
            for k in touched:
                v = snap[k]; d.set(k, ('1' if v else '0') if isinstance(v, bool) else str(v))
    total = runs[0][1]
    merged = dict(runs[0][0])
    for i, (r, _) in enumerate(runs[1:], 2):
        diff, n = first_diff(runs[0][0], r)
        if diff: raise SystemExit(f'check_board_steps: run {i} differs from run 1 (not deterministic):\n  1: {diff[0]}\n  {i}: {diff[1]}')
        merged.update(r)
    head = f'# {board} preset {a.preset or "(board params)"}'
    if a.save:
        with open(a.save, 'w') as f: f.write(head + '\n' + '\n'.join(merged[k] for k in sorted(merged)) + '\n')
        print(f'saved {len(merged)} of {total} frames ({a.runs} runs agree) to {a.save}')
        return
    saved = frames(open(a.compare).read())
    hdr = open(a.compare).readline().strip()
    if hdr != head: print(f'check_board_steps: WARNING: saved with "{hdr}", now "{head}"', file=sys.stderr)
    diff, n = first_diff(saved, merged)
    if diff: print(f'DIFFERS from {a.compare}:\n  saved   {diff[0]}\n  current {diff[1]}'); sys.exit(1)
    print(f'identical: {n} of {total} frames compared ({a.runs} runs agree) match {a.compare}')

if __name__ == '__main__': main()
