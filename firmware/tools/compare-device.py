#!/usr/bin/env python3
"""Pixel-compare the board's rendered tube strips with the browser sim's renderer.

  python3 firmware/tools/compare-device.py [--port /dev/ttyACM0|COM6] [--out DIR]   (port auto-detected, see device.py)

Sends `x` to the firmware (dumps TubeState + every strip), renders the same state through
sim/src/render.ts in node (tools/render-ref.ts) with the params currently in the firmware (`p?`),
and writes device.png / ref.png / diff.png plus a mismatch summary. Fizz is switched off on the
device for the dump (random positions) and restored afterwards. Either board: the canvas and the tubes' rows come
from the dump's LAYOUT line, the sim renders the same canvas (LW_BOARD / LW_RES / LW_TUBES from the board's `v`; a
three-tube board dumps the seconds tube too).
"""
import argparse, json, os, subprocess, sys, time
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from device import Device
from spritesheets import job_sprites

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SIM = os.path.join(ROOT, 'sim')
W, H = 536, 240   # canvas, replaced by the dump's LAYOUT line

def talk(s, cmd, end=b'\n', timeout=10, ok=None):
    return s.talk(cmd, end.decode(), timeout, ok)

def layout(line):
    """`LAYOUT W H Hh yH yM [Hm [yS Hs]]` -> (W, H, (Hh, Hm[, Hs]), (yH, yM[, yS])): the canvas, each tube's rows and top
    (firmware before per-tube widths has no Hm: both tubes Hh rows; a three-tube board adds the seconds tube)."""
    v = list(map(int, line.split()[1:]))
    if len(v) > 7: return v[0], v[1], (v[2], v[5], v[7]), (v[3], v[4], v[6])
    return v[0], v[1], (v[2], v[5] if len(v) > 5 else v[2]), (v[3], v[4])

def whole(dump):
    """All strip rows of the `x` dump arrived (the Windows bridge now and then drops part of a reply)."""
    lay = [l for l in dump.splitlines() if l.startswith('LAYOUT')]
    if not lay: return 'END' in dump   # firmware before LAYOUT: checked by the assert below
    w, _, th, _ = layout(lay[0])
    return sum(1 for l in dump.splitlines() if len(l.strip()) == w * 4) == sum(th)

def to_img(px):  # list of (W*H) 565 ints -> RGB image, exact 565 expansion
    im = Image.new('RGB', (W, H)); d = []
    for c in px:
        r5, g6, b5 = (c >> 11) & 31, (c >> 5) & 63, c & 31
        d.append(((r5 << 3) | (r5 >> 2), (g6 << 2) | (g6 >> 4), (b5 << 3) | (b5 >> 2)))
    im.putdata(d); return im

def main():
    global W, H
    ap = argparse.ArgumentParser(); ap.add_argument('--port', default=None); ap.add_argument('--out', default=os.path.join(ROOT, 'firmware', '.compare'))
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    s = Device(a.port)
    params = json.loads(talk(s, 'p?').strip().splitlines()[-1])
    env = s.board_env()
    fizz_was = params['fizz']
    if fizz_was: s.set('fizz', 0); params['fizz'] = False   # volatile (`p~`): never reaches NVS
    dump = talk(s, 'x', b'END', timeout=60, ok=whole)
    if fizz_was: s.set('fizz', 1)
    lines = [l.strip() for l in dump.splitlines() if l.strip()]
    lay = [l for l in lines if l.startswith('LAYOUT')]
    if lay: W, H, TH, Y0 = layout(lay[0])
    else:   # firmware before LAYOUT: the AMOLED canvas, rows from the params
        th = max(4, min(120, round(params['tubeHeight']))); TH = (th, th)
        Y0 = tuple(max(0, min(H - th, round(params[k]))) for k in ('hoursY', 'minutesY'))
    st = [l for l in lines if l.startswith('STATE')][0].split()[1:]
    rows = [l for l in lines if len(l) == W * 4]
    assert len(rows) == sum(TH), f'got {len(rows)} rows, expected {" + ".join(map(str, TH))}'
    NT = len(TH); names = ('hours', 'minutes', 'seconds')[:NT]
    dev = [0] * (W * H)
    for t in range(NT):
        for y in range(TH[t]):
            r = rows[sum(TH[:t]) + y]
            dev[(Y0[t] + y) * W:(Y0[t] + y + 1) * W] = [int(r[i:i + 4], 16) for i in range(0, W * 4, 4)]
    f = list(map(float, st))
    key = ['fillTarget', 'fillPos', 'angle', 'light', 'edgeLight', 'agitation', 'acrossTilt', 'cap', 'filmFree', 'filmHome', 'slugPos', 'reading',
           'pinFree', 'pinHome', 'lineVFree', 'lineVHome', 'rearX16', 'rearY16', 'rearX16w', 'rearY16w']
    n = len(f) // NT; key = key[:n]; tubes = [dict(zip(key, f[t * n:(t + 1) * n])) for t in range(NT)]  # render-ref fills the rest from newTube()
    for tag, key in (('TRACE ', 'trace'), ('WET ', 'traceWet')):  # dried-trace residue and its wet part, hex per tube (see render-ref.ts)
        tr = [l for l in lines if l.startswith(tag)]
        parts = tr[0].split()[1:] if tr else []
        if len(parts) == NT:
            for t in range(NT): tubes[t][key] = parts[t]
    job = {'params': params, **dict(zip(names, tubes))}
    sprites = job_sprites(params['digitFont'], a.out)   # the sheet at every cell height: render-ref takes its canvas's
    if sprites: job['sprites'] = sprites
    jobf = os.path.join(a.out, 'job.json'); json.dump(job, open(jobf, 'w'))
    outdir = os.path.join(SIM, 'node_modules', '.cache', 'render-ref')
    # tsc only when a source is newer than the compiled render-ref.js (saves ~10 s per run)
    ref_js = os.path.join(outdir, 'sim', 'tools', 'render-ref.js')
    srcs = [os.path.join(SIM, 'tools', 'render-ref.ts'), os.path.join(SIM, 'tools', 'render-ref.tsconfig.json')] + \
           [os.path.join(SIM, 'src', f) for f in os.listdir(os.path.join(SIM, 'src')) if f.endswith('.ts')] + \
           [os.path.join(SIM, '..', 'spec', f) for f in os.listdir(os.path.join(SIM, '..', 'spec')) if f.endswith('.ts')]
    if not os.path.exists(ref_js) or max(os.path.getmtime(f) for f in srcs) > os.path.getmtime(ref_js):
        subprocess.check_call(['npx', 'tsc', '-p', 'tools/render-ref.tsconfig.json'], cwd=SIM)
    open(os.path.join(outdir, 'package.json'), 'w').write('{}')
    # tsc keeps the '@spec/layout' specifier; alias it for node
    spec_dir = os.path.join(outdir, 'node_modules', '@spec'); os.makedirs(spec_dir, exist_ok=True)
    import shutil; shutil.copy(os.path.join(outdir, 'spec', 'layout.js'), os.path.join(spec_dir, 'layout.js'))
    ref_bin = os.path.join(a.out, 'ref.bin')
    subprocess.check_call(['node', os.path.join(outdir, 'sim', 'tools', 'render-ref.js'), jobf, ref_bin], env=env)
    raw = open(ref_bin, 'rb').read(); ref = [raw[i] | (raw[i + 1] << 8) for i in range(0, len(raw), 2)]
    assert len(ref) == W * H, f'sim rendered {len(ref)} px, the board {W}x{H} ({env["LW_BOARD"]} {env["LW_RES"]})'
    to_img(dev).save(os.path.join(a.out, 'device.png')); to_img(ref).save(os.path.join(a.out, 'ref.png'))
    diff = Image.new('RGB', (W, H)); dd = []; n = 0; big = 0
    for i in range(W * H):
        if dev[i] == ref[i]: dd.append((0, 0, 0)); continue
        n += 1
        A, B = to_img([dev[i]]).getpixel((0, 0)), to_img([ref[i]]).getpixel((0, 0))
        e = max(abs(A[k] - B[k]) for k in range(3)); big += e > 12
        dd.append((255, 255, 0) if e > 12 else (90, 0, 0))
    diff.putdata(dd); diff.save(os.path.join(a.out, 'diff.png'))
    print('state ' + ' '.join(f'{k}={t}' for k, t in zip(names, tubes)))
    print(f'canvas {W}x{H} ({env["LW_BOARD"]}{"@" + env["LW_RES"] if env["LW_RES"] else ""}{"+t" + env["LW_TUBES"] if env.get("LW_TUBES", "2") != "2" else ""}),'
          f' tubes {" / ".join(map(str, TH))} px at y {" / ".join(map(str, Y0))}')
    print(f'mismatched pixels: {n} of {W * sum(TH)} ({100 * n / (W * sum(TH)):.2f}%), >12/255 off: {big}')
    print('wrote', a.out)

if __name__ == '__main__': main()
