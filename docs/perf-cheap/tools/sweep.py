#!/usr/bin/env python3
"""perf-cheap A evidence: every stock preset with a highlight band (highlightH > 0), a few poses, the board's recorded rest
noise: 87f19af's build vs this one (noise.cpp binaries OLD / NEW, build_noise.sh), the same input, compared by cmp.py.

  sweep.py OLD NEW OUT.jsonl [-j 3] [--frames 300]
"""
import argparse, glob, json, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
POSES = {'stand': (-0.966, 0, 0.259), 'flat': (0, 0, 1), 'cola-review2': (0, 0.0328, 0.99946), 'side': (0.057, 0.9935, 0.15)}
def fmt(v): return ('1' if v else '0') if isinstance(v, bool) else str(v)
def job(a, path, pose, tmp):
    d = json.load(open(path)); d['fizz'] = False
    plines = ''.join(f'P {k}={fmt(v)}\n' for k, v in d.items() if k != 'v')
    env = dict(os.environ, NOISE_FILE=os.path.join(ROOT, 'docs/perf-cheap/tools/imu_rest_dev.txt'))
    base = os.path.join(tmp, f'{os.path.basename(path)}-{pose}')
    outs = {}
    for side, exe in (('old', a.old), ('new', a.new)):
        r = subprocess.run([exe, '-1', *map(str, POSES[pose]), str(a.frames), '0', '0', '0', '0', '0', '0'], input=plines.encode(),
                           env=dict(env, FRAMES_OUT=f'{base}.{side}'), stdout=subprocess.PIPE, check=True).stdout.decode()
        outs[side] = [l for l in r.split('\n') if l.startswith('ROWS')][0]
    rows = int(outs['new'].split()[1])
    c = json.loads(subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'cmp.py'), f'{base}.old', f'{base}.new', str(rows), '--json'],
                                  stdout=subprocess.PIPE, check=True).stdout)
    for side in ('old', 'new'): os.remove(f'{base}.{side}')
    work = {side: outs[side].split('per frame:')[1].strip() for side in outs}
    return {'preset': os.path.relpath(path, ROOT), 'pose': pose, **c, 'work': work}
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('old'); ap.add_argument('new'); ap.add_argument('out')
    ap.add_argument('-j', type=int, default=3); ap.add_argument('--frames', type=int, default=300)
    a = ap.parse_args()
    paths = [p for p in sorted(glob.glob(ROOT + '/presets/*.json') + glob.glob(ROOT + '/presets/physical/*.json'))
             if isinstance(json.load(open(p)), dict) and json.load(open(p)).get('highlightH', 0) > 0]
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(a.j) as ex, open(a.out, 'w') as f:
        for r in ex.map(lambda t: job(a, *t, tmp), [(p, q) for p in paths for q in POSES]):
            f.write(json.dumps(r) + '\n'); f.flush()
if __name__ == '__main__': main()
