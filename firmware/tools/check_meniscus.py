#!/usr/bin/env python3
"""Check meniscus appearance invariants and native firmware/simulator pixel parity.

Requires sim/node_modules, Node and a native C++ compiler; no device or flashing.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def run_check(tmp):
    cache = tmp / 'sim-cache'
    subprocess.run([str(ROOT / 'sim/node_modules/.bin/tsc'), '-p',
                    str(ROOT / 'sim/tools/render-ref.tsconfig.json'), '--outDir', str(cache)], check=True)
    (cache / 'package.json').write_text('{}')
    alias = cache / 'node_modules/@spec'
    alias.mkdir(parents=True, exist_ok=True)
    shutil.copy(cache / 'spec/layout.js', alias / 'layout.js')
    # The sprite digit sheets as raw RGBA for the sim side (the firmware has them compiled in).
    from PIL import Image
    (tmp / 'sprites').mkdir(exist_ok=True)
    for png in sorted((ROOT / 'sim/public/assets').glob('digits-*.png')):
        (tmp / 'sprites' / (png.stem + '.rgba')).write_bytes(Image.open(png).convert('RGBA').tobytes())
    subprocess.run(['node', str(ROOT / 'sim/tools/check-meniscus.cjs'), str(cache), str(tmp), str(ROOT)], check=True,
                   env=dict(os.environ, LW_BOARD='amoled191', LW_RES=''))   # the native side below is the AMOLED build
    jobs = json.loads((tmp / 'jobs.json').read_text())
    cpp = ['#include <cstdio>\n#include "render.h"\nstatic uint16_t strip[536*80], trace[536];',
           'int main() { if (!render_init()) return 1;']
    for i, job in enumerate(jobs):
        cpp.append('{ Params p=PRESET_DEFAULT; TubeState s;')
        for key, value in job['params'].items():
            literal = ('0x' + value[1:] if isinstance(value, str) else
                       str(value).lower() if isinstance(value, bool) else repr(value))
            cpp.append(f'p.{key}={literal};')
        for key, value in job['state'].items():
            cpp.append(f's.{key}={value};')
        cpp.append('s.trace=trace;')
        if job['residue']:
            lo, hi = (0, 536) if job['residue'] is True else job['residue']
            cpp.append(f'for (int i=0;i<536;i++) trace[i]=i>={lo}&&i<{hi}?0xff00:0; s.traceLo={lo}; s.traceHi={hi};')
        else:
            cpp.append('for (auto &v:trace) v=0; s.traceLo=536; s.traceHi=0;')
        cpp.append(f'renderTube(0,s,p,{i + 1},strip);')
        cpp.append('if (std::fwrite(strip,2,536*tubeLayout(p).H,stdout) != size_t(536*tubeLayout(p).H)) return 2; }')
    cpp.append('}')
    (tmp / 'check.cpp').write_text('\n'.join(cpp))
    (tmp / 'esp_heap_caps.h').write_text('#pragma once\n#include <cstdlib>\n#define MALLOC_CAP_SPIRAM 0\n'
                                       'inline void *heap_caps_malloc(size_t n,int){return std::malloc(n);}\n')
    (tmp / 'esp_random.h').write_text('#pragma once\n#include <cstdint>\ninline uint32_t esp_random(){return 0xabcdef01;}\n')
    subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O2', '-ffp-contract=off',
                    '-fsanitize=undefined,float-cast-overflow', '-fno-sanitize-recover=all',
                    '-I', str(tmp), '-I', str(ROOT / 'firmware/src'), '-I', str(ROOT / 'spec'),
                    str(tmp / 'check.cpp'), str(ROOT / 'firmware/src/render.cpp'),
                    str(ROOT / 'firmware/src/physics.cpp'), '-o', str(tmp / 'check')], check=True)
    result = subprocess.run([str(tmp / 'check')], stdout=subprocess.PIPE, check=True).stdout
    offset = worst = differing = 0
    for job in jobs:
        count = 536 * job['height']
        ref = struct.unpack('<' + 'H' * count, (tmp / (job['name'] + '.bin')).read_bytes())
        native = struct.unpack_from('>' + 'H' * count, result, offset)
        offset += count * 2
        for index, (a, b) in enumerate(zip(ref, native)):
            if a == b:
                continue
            differing += 1
            def rgb(c):
                r, g, bl = c >> 11, (c >> 5) & 63, c & 31
                return (r << 3) | (r >> 2), (g << 2) | (g >> 4), (bl << 3) | (bl >> 2)
            delta = max(abs(x - y) for x, y in zip(rgb(a), rgb(b)))
            worst = max(worst, delta)
            if delta > 12:
                raise AssertionError(f"{job['name']}: ({index % 536},{index // 536}) channel delta {delta} > 12")
    assert offset == len(result), 'Unexpected native frame data'
    print(f'{len(jobs)} native/sim frames passed: {differing} differing pixels, max channel delta {worst}/255; UBSan clean.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='Keep frames and harness here for visual inspection')
    args = parser.parse_args()
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        run_check(args.out.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='watches-meniscus-') as directory:
            run_check(Path(directory))
