#!/usr/bin/env python3
"""Edge shade across frames, on the host (no device, no sim): what one-frame parity checks cannot see.

  python3 firmware/tools/check_shade_frames.py [--res 320w8-8]

lcd316, the tiled band loop (-DTILE_RENDER=1) with the push's lens map (main.cpp lensRows), built with ASan / UBSan, two
strip buffers of TUBE_HEIGHT_MAX rows (the board's), params kept across renders (gen bumps only on a param change, as on
the board). Scenarios, each on the board's look (fizz off):
  spill    a 107-row tube with a lens that would want more spare rows than the strip holds, and the user's look with digits
           on top (strip lens): no write past the strip (ASan).
  record   shade-only change with the lens row map unchanged: every word the push would show changed is marked in the
           render's change record (tiles.h TileDirty) whenever that record claims to be valid.
  palette  a light change at a constant edge light (hard-edge glow table): the frame equals a fresh render of it.
Exits 1 on any failure.
"""
import argparse, json, os, struct, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import boardtag

ROOT = Path(__file__).resolve().parents[2]
LOOK = ROOT / 'firmware/tools/testdata/edge-shade-look.json'

HARNESS = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "render.h"
#include "layout.h"
#include "tiles.h"
static uint16_t strip0[PANEL_W * TUBE_HEIGHT_MAX], strip1[PANEL_W * TUBE_HEIGHT_MAX];   // separate globals: ASan redzones between
static bool setParam(Params &p, const char *name, const char *val) {
  for (const ParamField &f : PARAM_FIELDS) if (!strcmp(f.name, name)) {
    uint8_t *q = (uint8_t *)&p + f.off;
    switch (f.type) {
      case 'f': *(float *)q = atof(val); break;
      case 'i': *(int *)q = atoi(val); break;
      case 'b': *(bool *)q = !(val[0] == '0' || val[0] == 'f' || val[0] == 'F' || val[0] == 'n'); break;
      case 'c': *(uint32_t *)q = strtoul(val[0] == '#' ? val + 1 : val, nullptr, 16); break;
    }
    return true;
  }
  return false;
}
int main() {
  if (!render_init() || !physics_init()) return 3;
  Params design = PRESET_DEFAULT, p[TUBE_COUNT]; TubeState st[TUBE_COUNT]; uint32_t gen = 1;
  uint16_t *const strip[2] = {strip0, strip1};
  for (int i = 0; i < TUBE_COUNT; i++) { st[i].trace = traceBuf(i); st[i].traceWet = traceWetBuf(i); }
  char line[256];
  while (fgets(line, sizeof line, stdin)) {
    line[strcspn(line, "\r\n")] = 0;
    if (line[0] == 'P') { char *eq = strchr(line + 2, '='); if (!eq) return 4; *eq = 0; if (!setParam(design, line + 2, eq + 1)) fprintf(stderr, "unknown param %s\n", line + 2); gen++; }
    else if (line[0] == 'D') { design = PRESET_DEFAULT; gen++; }
    else if (line[0] == 'G') gen++;
    else if (line[0] == 'S') { int i; float f, l; sscanf(line + 2, "%d %f %f", &i, &f, &l); st[i] = TubeState(); st[i].trace = traceBuf(i); st[i].traceWet = traceWetBuf(i); st[i].fillTarget = f; st[i].light = l; }
    else if (line[0] == 'R') {
      for (int i = 0; i < TUBE_COUNT; i++) boardParams(design, p[i], TUBE_PX_SCALE(i), PX_SCALE_FIZZ);
      const FaceLayout lay = faceLayout(p[0], p[1]);
      for (int i = 0; i < 2; i++) {
        const int16_t *map = nullptr;
        renderTube(i, st[i], p[i], gen, strip[i], &map, lay.top(i));
        const int H = lay.rows(i);
        const TileDirty *rec = tile_dirty(strip[i]);
        int32_t hdr[3] = {H, map ? 1 : 0, rec && rec->valid ? 1 : 0};
        fwrite(hdr, sizeof hdr, 1, stdout);
        int16_t m[TUBE_HEIGHT_MAX]; for (int r = 0; r < TUBE_HEIGHT_MAX; r++) m[r] = (int16_t)(r < H ? (map ? map[r] : r) : 0);
        fwrite(m, sizeof m, 1, stdout);
        fwrite(strip[i], sizeof strip0, 1, stdout);
        static uint32_t zero[TILE_MAX][TILE_PAIR_WORDS];
        fwrite(rec ? rec->bits : zero, sizeof zero, 1, stdout);
      }
      fflush(stdout);
    }
  }
  return 0;
}
'''

def fmt(v):
    if isinstance(v, bool): return '1' if v else '0'
    return str(v)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--res', default='320w8-8')
    ap.add_argument('--render', type=Path, default=ROOT / 'firmware/src/render.cpp', help='render.cpp to check (e.g. an older one)')
    a = ap.parse_args()
    rows = boardtag.parse_res(a.res, 2)[0]
    W = rows * 820 // 320
    with tempfile.TemporaryDirectory(prefix='watches-shade-') as tmp:
        tmp = Path(tmp)
        (tmp / 'esp_heap_caps.h').write_text('#pragma once\n#include <cstdlib>\n#define MALLOC_CAP_SPIRAM 0\n'
                                             'inline void *heap_caps_malloc(size_t n, int) { return std::calloc(n, 1); }\n')
        (tmp / 'esp_random.h').write_text('#pragma once\n#include <cstdint>\ninline uint32_t esp_random() { return 0xabcdef01; }\n')
        (tmp / 'h.cpp').write_text(HARNESS)
        subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O1', '-g', '-ffp-contract=off', '-fsanitize=address,undefined',
                        '-fno-sanitize-recover=all', '-DTILE_RENDER=1', '-DBOARD_LCD316', *boardtag.tubes_flags(2), *boardtag.res_flags(a.res, 2),
                        '-I', str(tmp), '-I', str(ROOT / 'firmware/src'), '-I', str(ROOT / 'spec'),
                        str(tmp / 'h.cpp'), str(a.render), str(ROOT / 'firmware/src/physics.cpp'),
                        '-o', str(tmp / 'h')], check=True)
        look = json.load(open(LOOK))
        base = [f'P {k}={fmt(v)}' for k, v in look.items() if k != 'v'] + ['P fizz=0', 'S 0 0.42 20', 'S 1 0.71 20']

        def run(script):
            r = subprocess.run([str(tmp / 'h')], input=('\n'.join(['D'] + base + script) + '\n').encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if r.returncode: sys.stderr.write(r.stderr.decode()[-3000:]); return None
            return r.stdout

        def frames(raw):   # [(tube0, tube1)] each (H, mapped, valid, map, strip words, bits)
            hmax = frame_hmax
            n_tube = 12 + hmax * 2 + W * hmax * 2 + tile_max * pair_words * 4
            res, o = [], 0
            while o < len(raw):
                fr = []
                for _ in range(2):
                    H, mapped, valid = struct.unpack_from('<3i', raw, o); q = o + 12
                    m = struct.unpack_from(f'<{hmax}h', raw, q); q += hmax * 2
                    s = struct.unpack_from(f'<{W * hmax // 2}I', raw, q); q += W * hmax * 2
                    bits = struct.unpack_from(f'<{tile_max * pair_words}I', raw, q)
                    fr.append((H, mapped, valid, m, s, bits)); o += n_tube
                res.append(fr)
            return res

        # TUBE_HEIGHT_MAX from a probe run: one render of the base look
        probe = run(['R'])
        if probe is None: sys.exit('check_shade_frames: harness failed on the base look')
        global frame_hmax, tile_max, pair_words
        pair_words = (W // 2 + 31) // 32
        for hm in range(32, 400):
            tm = (hm + 3) // 4
            if 2 * (12 + hm * 2 + W * hm * 2 + tm * pair_words * 4) == len(probe): frame_hmax, tile_max = hm, tm; break
        else: sys.exit('check_shade_frames: cannot size the harness output')
        bad = 0

        # spill
        for name, extra in (('107-row tube, lens -1 / 0.2', ['P tubeHeight=80', 'P lens=-1', 'P lensCurve=0.2', 'P edgeShade=1']),
                            ('digits on top (strip lens)', ['P digitsOnTop=1'])):
            ok = run(extra + ['R', 'R']) is not None
            print(f'spill    {name:40s} {"ok" if ok else "FAIL (sanitizer)"}'); bad += not ok

        # record: shade-only change, the row map unchanged
        def record(name, script):
            nonlocal bad
            raw = run(script)
            if raw is None: print(f'record   {name:40s} FAIL (sanitizer)'); bad += 1; return
            fr = frames(raw); worst = 0; checked = 0
            for k in range(1, len(fr)):
                for t in range(2):
                    H, mapped, valid, m, s, bits = fr[k][t]; _, _, _, m0, s0, _ = fr[k - 1][t]
                    if not valid or m[:H] != m0[:H]: continue
                    checked += 1
                    for r in range(H):
                        a0, a1 = m0[r] * W // 2, m[r] * W // 2
                        tile = m[r] // 4
                        for pw in range(W // 2):
                            if s[a1 + pw] != s0[a0 + pw] and not (bits[tile * pair_words + pw // 32] >> (pw % 32)) & 1: worst += 1
            ok = worst == 0 and checked > 0
            print(f'record   {name:40s} {"ok" if ok else "FAIL"} ({checked} valid records checked, {worst} changed words unmarked)'); bad += not ok
        # the board's look moves the 2nd tube's lens map? keep it: only the shade depth changes
        record('shade depth 0.67 -> 0.4 -> 0.67', ['R', 'R', 'P edgeShade=0.4', 'R', 'R', 'P edgeShade=0.67', 'R'])
        record('strong lens, depth 0.5 -> 0.75', ['P lens=-1', 'P lensCurve=0.2', 'P edgeShade=0.5', 'R', 'R', 'P edgeShade=0.75', 'R', 'R'])
        # a spare tile whose drawn rows' tiles do not change with the depth (their factors are their lighter rows', unshaded
        # or unchanged) while its own rows do: the bits ORed from them would miss it (the record must not be valid)
        for lens, curve, pw, k0, k1 in ((-0.8, -1.1, 2.5, 1, 0.9), (-0.7, -2.8, 2.5, 1, 0.9)):
            record(f'lens {lens} / {curve}, pow {pw}, depth {k0} -> {k1}', [f'P lens={lens}', f'P lensCurve={curve}', f'P edgeShadePow={pw}', f'P edgeShade={k0}', 'R', 'R', f'P edgeShade={k1}', 'R', 'R'])

        # palette: a light change at a constant edge light (glow table), against a fresh render
        raw = run(['P edgeSoft=0', 'P traces=0', 'P edgeGlow=6', 'P glowStrength=1', 'S 0 0.42 -45', 'S 1 0.71 -45', 'R',
                   'S 0 0.42 45', 'S 1 0.71 45', 'R', 'G', 'R'])
        if raw is None: print('palette  glow table, light -45 -> 45            FAIL (sanitizer)'); bad += 1
        else:
            fr = frames(raw)
            diff = sum(x != y for t in range(2) for r in range(fr[1][t][0]) for x, y in
                       zip(fr[1][t][4][fr[1][t][3][r] * W // 2:(fr[1][t][3][r] + 1) * W // 2], fr[2][t][4][fr[2][t][3][r] * W // 2:(fr[2][t][3][r] + 1) * W // 2]))
            print(f'palette  {"glow table, light -45 -> 45":40s} {"ok" if diff == 0 else "FAIL"} ({diff} words differ from a fresh render)'); bad += diff != 0
        print(f'check_shade_frames lcd316@{a.res}: {"ok" if not bad else f"{bad} failed"}')
        sys.exit(1 if bad else 0)

frame_hmax = tile_max = pair_words = 0
if __name__ == '__main__': main()
