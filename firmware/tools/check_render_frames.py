#!/usr/bin/env python3
"""Compare complete firmware strips against a saved reference render.cpp (native C++).

Usage: python3 firmware/tools/check_render_frames.py --reference /tmp/render-before.cpp [--no-fizz | --big-fizz]
                                                    [--tolerance N] [--list-diffs]
--no-fizz forces fizz off in every scene of both builds, so a fizz-only change must stay byte-identical.
--big-fizz gives the random group large bubbles (sizes 3/5/14, spread 0.65, blick and depth fade cycling) so the
disc interior, core, pinpoint and depth paths are exercised; both builds see the same scenes.
--list-diffs keeps streaming past the first differing scene and prints, per scene group, how many scenes differ
(beyond --tolerance), up to 10 of their indices and whether every one had fizz on — so a fizz-only change proves
"only fizz-on scenes differ" in one run. Still exits non-zero if any scene differs.
Host-only ESP stubs; no board, firmware allocation changes, or checked-in golden images.
"""
from pathlib import Path
import argparse
import os
import re
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
# AMOLED build (no BOARD_LCD316): canvas 536x240 = design px, so the strip rows are the design maximum
TUBE_HEIGHT_MAX = int(re.search(r'#define\s+DESIGN_TUBE_HEIGHT_MAX\s+(\d+)', (ROOT / 'spec/layout.h').read_text()).group(1))
FRAME_BYTES = 536 * TUBE_HEIGHT_MAX * 2   # every strip is padded to the largest tube height

HARNESS = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "render.h"
static uint16_t strip[536*TUBE_HEIGHT_MAX], trace[536];
static uint32_t rng=721;
static float randf() { rng=rng*1664525u+1013904223u; return (rng>>8)*(1.0f/16777216.0f); }
static long scenes=0;
static void group(const char *name) { std::fprintf(stderr,"GROUP %ld %s\n",scenes,name); }
static void emit(int idx, const TubeState &s, const Params &scene, uint32_t gen) {
#ifdef NO_FIZZ
  Params p=scene; p.fizz=false; p.fizzCount=0;   // --no-fizz: after every scene override, on both builds
#else
  const Params &p=scene;
#endif
  std::fprintf(stderr,"SCENE %ld fizz=%d\n",scenes,p.fizz && p.fizzCount>0 ? 1 : 0);   // for --list-diffs
  renderTube(idx,s,p,gen,strip);
  // Fixed output size to make mismatches easy to locate; padding is deterministic.
  int n=tubeLayout(p).H*536;
  for(int x=n;x<536*TUBE_HEIGHT_MAX;x++) strip[x]=0;
  if (std::fwrite(strip,sizeof(strip),1,stdout)!=1) std::exit(2);
  scenes++;
}

// --- digit compositor edge cases -------------------------------------------------------------
// Refraction shift targets (px): wetDx = -edgeLight * digitParallax, wetDy = acrossTilt * digitParallax.
static const float DX[]={0,0.02f,0.5f,0.98f,-0.02f,-0.5f,-0.98f,1,-1,2.5f,-3.75f};
static const float DY[]={0,0.02f,-0.02f,0.5f,-0.5f,0.98f,-0.98f,6.5f,-9.9f};
static const float SCALE[][2]={{0.5f,0.5f},{6,6},{0.5f,6},{6,0.5f},{2.25f,3.5f}};
static const float HEIGHT[]={16,37,64,80};
static const float BOTTOM[]={0,5,16,25,40,12};
static const float LENS[]={-1,-0.4f,0,1};
static const float FILL[]={0.02f,0.5f,0.98f};

static void digitBase(Params &p) {
  p=PRESET_DEFAULT;
  p.digits=true; p.digitHourStep=1; p.digitHourStart=0; p.digitMinuteStep=5; p.digitMinuteStart=0;
  p.digitsLastOnlyH=p.digitsLastOnlyM=false; p.fizz=false; p.bubble=false; p.traces=false;
}
// Fill mode 0..7: pinned near-empty / half / near-full, the same three mirrored (`remaining`), free slug in the
// middle (both meniscus edges inside the tube), plain and mirrored.
static void setFill(Params &p, TubeState &s, int mode) {
  p.freeLiquid=mode>=6; p.remaining=mode>=3 && mode<6 ? true : mode==7;
  s.fillTarget=mode<6 ? FILL[mode%3] : p.remaining ? 0.62f : 0.38f;
  s.slugPos=p.freeLiquid ? (536-columnLen(s.fillTarget,p))*0.5f : 0;
}
static void setShift(Params &p, TubeState &s, float dx, float dy) {
  float par=(dx>1||dx<-1||dy>1||dy<-1) ? 10 : 1;
  p.digitParallax=par; s.edgeLight=-dx/par; s.acrossTilt=dy/par;
}

// One mutation per sequence phase: each touches a digit-path cache input (glyph set, labels, palette, row cache).
static void mutate(Params &p, int k) {
  switch(k) {
    case 0: p.digitFont=((int)p.digitFont+1)%12; break;                                // bitmap <-> sprite crossings
    case 1: p.digitFont=5+((int)p.digitFont+2)%7; break;                               // sprite -> other sprite
    case 2: p.digitScaleX+=0.25f; p.digitScaleXMin+=0.25f; break;
    case 3: p.digitScaleY-=0.25f; p.digitScaleYMin-=0.25f; break;
    case 4: p.digitShadowOffset=p.digitShadowOffset>=4 ? 1 : 4; break;
    case 5: p.digitShadow=!p.digitShadow; break;
    case 6: p.digitShadowStrength=p.digitShadowStrength>0.5f ? 0.3f : 1; break;
    case 7: p.digitShadowColor^=0x405060; break;
    case 8: p.liquidTransparency=p.liquidTransparency>0.5f ? 0.2f : 0.85f; break;       // baked behind-liquid plane
    case 9: p.digitTint^=0x305020; break;
    case 10: p.digitTintAmount=p.digitTintAmount>0.5f ? 0.1f : 0.9f; break;
    case 11: p.digitTone=p.digitTone>0 ? -0.7f : 0.6f; break;
    case 12: p.brightness*=0.8f; break;
    case 13: p.digitBright=p.digitBright>1 ? 0.6f : 1.4f; break;
    case 14: p.digitColor^=0x204080; p.digitColor2^=0x102030; break;
    case 15: p.tubeHeight=p.tubeHeight>=60 ? 30 : 80; break;
    case 16: p.digitBottom+=7; p.digitBottomMin-=3; break;
    case 17: p.digitsOnTop=!p.digitsOnTop; break;
    case 18: p.bottomLens=1-p.bottomLens; p.digitDryLens=-p.digitDryLens; p.topLens=-p.topLens; break;
    case 19: p.digits=!p.digits; break;
    case 20: p.markContrast=p.markContrast>0 ? 0 : 90; break;
    case 21: p.digitHourStep=2; p.digitHourStart=1; p.digitMinuteStep=10; p.digitMinuteStart=5; break;
    case 22: p.digitsLeadingZero=!p.digitsLeadingZero; break;
    case 23: p.digitParallax=p.digitParallax>1 ? 0.5f : 7; break;
    case 24: p.remaining=!p.remaining; break;
    case 25: p.cornerR+=3; break;
    case 26: p.digitsLastOnlyH=!p.digitsLastOnlyH; p.digitsLastOnlyM=!p.digitsLastOnlyM; break;
    default: break;                                                                   // no-op write: gen bump only
  }
}
static const int MUTATIONS=28;

int main() {
  if (!render_init()) return 1;
  group("random");
  for(int i=0;i<4000;i++) {
    Params p=PRESET_DEFAULT;
    p.fizz=i%3 != 0; p.bubble=i%5 == 0; p.digitFont=i%12;
#ifdef BIG_FIZZ   // fizz forced on; size / blick / depth cycles decorrelated from each other and from remaining (i&1)
    p.fizz=true; p.fizzCount=60; p.fizzSize=i%3==0?5:i%3==1?14:3; p.fizzSizeVar=0.65f; p.fizzBlick=((i/3)%2)*0.6f; p.fizzDepth=((i/6)%4)/3.0f; p.bubbleDark=((i/12)%3)*0.5f;
#endif
    p.digitsOnTop=i%7 == 0; p.ticksOnTop=i%5 == 0;
    p.digitShadow=i%3 != 0; p.digitShadowOffset=1+i%4;
    p.digitScaleX=p.digitScaleXMin=0.5f+(i%12)*0.5f;
    p.digitScaleY=p.digitScaleYMin=0.5f+(i%23)*0.25f;
    p.digitParallax=(i%13)-6; p.tickParallax=(i%31)-15;
    p.tickMinorHeightH=p.tickMinorHeightM=i%40;
    p.tickMajorHeightH=p.tickMajorHeightM=i%31;
    p.tickMajorEveryH=3; p.tickMajorEveryM=5;
    p.tickStepH=1; p.tickStepM=5;
    p.tickMinorWidthH=p.tickMinorWidthM=1+i%4;
    p.tickEmboss=(i%5)*0.25f; p.markContrast=(i%3)*25;
    p.liquidTransparency=(i%17)/16.0f;
    p.tickPosH=p.tickPosM=i%3;
    p.lens=(i%9-4)*0.2f; p.lensCurve=(i%7-3)*0.25f;
    p.tickLens=(i%9-4)*0.25f; p.tickDryLens=(i%7-3)*0.25f;
    p.tubeHeight=4+(i*17)%77;
    p.remaining=i&1; p.freeLiquid=(i>>1)&1;
    p.traces=true; p.traceAmount=(i%17)*0.25f; p.traceFilm=(i%11)*0.1f;
    p.wetFilm=i%31; p.edgeSoft=i%5;
    p.contactAngle=(i%25)*7.5f; p.contactHyst=(i%4)*5; p.contactDyn=(i%3)*30; p.capLength=1+(i%5);
    TubeState s; s.fillTarget=randf(); s.fillPos=randf()*20-10; s.angle=randf()*12-6;
    s.slugPos=randf()*(536-columnLen(s.fillTarget,p)); s.cap=randf()*20-10;
    s.light=randf()*85; s.edgeLight=randf()*2-1; s.acrossTilt=randf()*2-1;
    if (i%4==0) s.edgeLight=s.acrossTilt=0;
    if (i%4==1) { s.edgeLight=1; s.acrossTilt=-1; }
    s.filmFree=i%7 ? randf() : 0; s.filmHome=i%9 ? randf() : 0;
    s.trace=trace; s.traceLo=i%200; s.traceHi=536-i%99;
    for(int x=0;x<536;x++) trace[x]=x<s.traceLo||x>=s.traceHi ? 0 : (uint16_t)(randf()*TRACE_FULL);
    emit(i&1,s,p,i+1);
  }

  // Grid: every font x on top / behind x shadow (off / offset 1 / max offset 4) x transparency 0 / mid / 1 x
  // contrast off / on, each in the 8 fill modes; scale, shift, height, baseline and lenses rotate with coprime
  // periods so their combinations spread over the grid.
  group("digit-grid");
  uint32_t gen=1000000; int n=0;
  for(int font=0;font<12;font++) for(int top=0;top<2;top++) for(int sh=0;sh<3;sh++)
  for(int tr=0;tr<3;tr++) for(int mc=0;mc<2;mc++) for(int k=0;k<8;k++,n++) {
    Params p; digitBase(p); TubeState s;
    p.digitFont=font; p.digitsOnTop=top; p.digitShadow=sh>0;
    p.digitShadowOffset=sh==2 ? 4 : 1; p.digitShadowStrength=sh==2 ? 0.6f : 1;
    p.liquidTransparency=tr*0.5f; p.markContrast=mc ? 60 : 0;
    p.digitScaleX=p.digitScaleXMin=SCALE[n%5][0]; p.digitScaleY=p.digitScaleYMin=SCALE[n%5][1];
    p.tubeHeight=HEIGHT[n%4];
    p.digitBottom=BOTTOM[n%6]; p.digitBottomMin=BOTTOM[(n+3)%6];
    p.bottomLens=(n%4)/3.0f; p.digitDryLens=LENS[(n/4)%4]; p.topLens=LENS[(n+1)%4]; p.topParallax=LENS[(n+2)%4]*10;
    p.digitTintAmount=(n%3)*0.5f; p.digitTone=(n%5-2)*0.5f;
    p.digitsLastOnlyH=p.digitsLastOnlyM=n%13==0; p.ticksOnTop=n%2;
    p.fizz=n%10==0;
    setFill(p,s,k); setShift(p,s,DX[n%11],DY[n%9]);
    s.light=(n%7)*12.0f;
    emit((k+n/8)&1,s,p,++gen);
  }

  // Sequences: several frames at one params generation (motion only: shifts crossing integer floors, fill moving
  // the last-only label, light), then one mutation (new gen), then the original params again (new gen) —
  // each phase replays the same motion on both tubes, so a cache keyed too loosely shows up as a stale frame.
  group("digit-sequences");
  for(int q=0;q<2*MUTATIONS;q++) {
    Params base; digitBase(base);
    base.digitFont=q%12; base.digitsOnTop=q%5==0; base.digitShadow=q%3!=0; base.digitShadowOffset=1+q%4;
    base.liquidTransparency=0.3f+(q%4)*0.15f; base.markContrast=q%6==0 ? 40 : 0;
    base.digitScaleX=base.digitScaleXMin=1+(q%9)*0.5f; base.digitScaleY=base.digitScaleYMin=1+(q%7)*0.5f;
    base.tubeHeight=40+(q%5)*10; base.digitsLastOnlyH=base.digitsLastOnlyM=q%2;
    base.remaining=q%4==1; base.freeLiquid=q%4==2; base.topParallax=q%3==0 ? 6 : 0;
    base.digitParallax=4;
    Params mut=base; mutate(mut,q%MUTATIONS);
    const Params *phase[3]={&base,&mut,&base};
    for(int ph=0;ph<3;ph++) {
      const Params &p=*phase[ph]; ++gen;
      for(int f=0;f<5;f++) {
        TubeState s; s.fillTarget=0.18f+f*0.17f;
        s.slugPos=p.freeLiquid ? (536-columnLen(s.fillTarget,p))*0.4f : 0;
        s.light=f<2 ? 30 : 30+f*5;                                         // frames 0,1: palette hit
        s.edgeLight=(-1.5f+f*0.74f)/4; s.acrossTilt=(1.25f-f*0.63f)/4;   // at parallax 4: wetDx 1.5 .. -1.46, wetDy 1.25 .. -1.27
        emit(0,s,p,gen); emit(1,s,p,gen);
      }
    }
  }
  group("end");
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--tolerance', type=int, default=0,
                        help='max per-channel difference (RGB888 steps) still accepted; 0 = byte-identical (default)')
    parser.add_argument('--no-fizz', action='store_true',
                        help='force fizz off (fizz=false, fizzCount=0) in every scene of both builds')
    parser.add_argument('--big-fizz', action='store_true',
                        help='large fizz with blick/depth variety in the random group (exercises the disc interior paths)')
    parser.add_argument('--list-diffs', action='store_true',
                        help='do not stop at the first differing scene: list differing scenes per group with their fizz flag')
    args = parser.parse_args()
    reference = args.reference.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='watches-frames-') as tmp:
        tmp = Path(tmp)
        (tmp / 'esp_heap_caps.h').write_text(
            '#pragma once\n#include <cstdlib>\n#define MALLOC_CAP_SPIRAM 0\n'
            'inline void *heap_caps_malloc(size_t n, int) { return std::malloc(n); }\n')
        (tmp / 'esp_random.h').write_text(
            '#pragma once\n#include <cstdint>\n'
            'inline uint32_t esp_random() { return 0xabcdef01; }\n')
        cpp = tmp / 'frames.cpp'
        cpp.write_text(HARNESS)
        sides = [('reference', reference), ('current', ROOT / 'firmware/src/render.cpp')]
        defines = (['-DNO_FIZZ'] if args.no_fizz else []) + (['-DBIG_FIZZ'] if args.big_fizz else [])
        builds = [subprocess.Popen([os.environ.get('CXX', 'c++'), '-std=c++17', '-O2', *defines,
                                    '-ffp-contract=off', '-fsanitize=undefined,float-cast-overflow', '-fno-sanitize-recover=all',
                                    '-I', str(tmp), '-I', str(ROOT / 'firmware/src'), '-I', str(ROOT / 'spec'),
                                    str(cpp), str(source), str(ROOT / 'firmware/src/physics.cpp'),
                                    '-o', str(tmp / name)]) for name, source in sides]
        for (name, _), build in zip(sides, builds):
            if build.wait():
                raise SystemExit(f'{name}: host build failed')
        # Both harnesses run side by side and are compared as they stream (no multi-GB frame files).
        runs = [subprocess.Popen([str(tmp / name)], stdout=subprocess.PIPE, stderr=open(tmp / (name + '.log'), 'w'))
                for name, _ in sides]
        scenes = scenes_differing = pixels_differing = worst = 0
        listed = []   # --list-diffs: indices of the scenes that differ (beyond --tolerance)
        failure = None
        done = False
        try:
            while True:
                a, b = runs[0].stdout.read(FRAME_BYTES), runs[1].stdout.read(FRAME_BYTES)
                if not a and not b:
                    break
                if len(a) != FRAME_BYTES or len(b) != FRAME_BYTES:
                    failure = f'incomplete output at scene {scenes}'
                    break
                if a != b:
                    if not args.tolerance:
                        if args.list_diffs:
                            listed.append(scenes)
                            scenes += 1
                            continue
                        pixel = next(i for i, (x, y) in enumerate(zip(a, b)) if x != y) // 2
                        failure = f'different pixel at x={pixel % 536}, row={pixel // 536}'
                        break
                    scenes_differing += 1
                    over = False
                    pa, pb = memoryview(a).cast('H'), memoryview(b).cast('H')   # strip words are byte-swapped 565; equal-or-not is layout-agnostic
                    for i in range(len(pa)):
                        if pa[i] == pb[i]:
                            continue
                        pixels_differing += 1
                        d = channel_delta(pa[i], pb[i])
                        if d > worst:
                            worst = d
                        if d > args.tolerance and not over:
                            over = True
                            if not args.list_diffs:
                                failure = f'pixel x={i % 536}, row={i // 536} differs by {d} > {args.tolerance} (RGB888 steps)'
                                break
                    if failure:
                        break
                    if over:
                        listed.append(scenes)
                scenes += 1
            done = not failure
        finally:
            # On any failure a surviving renderer blocks on its full stdout pipe: give a side that is already
            # exiting (crash, UBSan) a moment so its status and log are kept, then kill whatever still runs.
            deadline = time.monotonic() + 2
            for run in runs:
                if not done and run.poll() is None:
                    try:
                        run.wait(timeout=max(0, deadline - time.monotonic()))
                    except subprocess.TimeoutExpired:
                        run.kill()
                run.wait()
        crashed = [(name, run.returncode) for (name, _), run in zip(sides, runs) if run.returncode and run.returncode != -9]
        if crashed:
            raise SystemExit('\n'.join(f'{name} harness exited with {code} after {scenes} scenes:\n' + harness_log(tmp / (name + '.log'))
                                       for name, code in crashed))
        groups = [(int(m.group(1)), m.group(2)) for m in
                  re.finditer(r'^GROUP (\d+) (\S+)$', (tmp / 'reference.log').read_text(), re.M)]
        if failure:
            where = max((g for g in groups if g[0] <= scenes), default=(0, '?'))
            raise SystemExit(f'scene {scenes} ({where[1]} #{scenes - where[0]}): {failure}')
        summary = ', '.join(f'{name} {nxt - start}' for (start, name), (nxt, _) in zip(groups, groups[1:]))
        if listed:
            fizz = {int(m.group(1)): m.group(2) == '1' for m in
                    re.finditer(r'^SCENE (\d+) fizz=([01])$', (tmp / 'current.log').read_text(), re.M)}
            lines = [f'{len(listed)} of {scenes} render strips ({summary}) differ'
                     + (f' by more than {args.tolerance} RGB888 steps' if args.tolerance else '') + ':']
            for (start, name), (nxt, _) in zip(groups, groups[1:]):
                hit = [n for n in listed if start <= n < nxt]
                if not hit:
                    lines.append(f'  {name}: 0')
                    continue
                off = [n for n in hit if not fizz.get(n, False)]
                lines.append(f'  {name}: {len(hit)} differ, ' + ('all with fizz on' if not off else f'{len(off)} with fizz off')
                             + '; first: ' + ' '.join(f'#{n - start}' for n in hit[:10]))
            all_fizz = all(fizz.get(n, False) for n in listed)
            lines.append('every differing scene had fizz on' if all_fizz else 'some differing scenes had fizz off')
            raise SystemExit('\n'.join(lines))
        if not scenes_differing:
            print(f'{scenes} complete render strips ({summary}) are byte-identical; UBSan passed')
        else:
            print(f'{scenes} render strips ({summary}) within {args.tolerance} RGB888 steps: {scenes_differing} scenes / '
                  f'{pixels_differing} pixels differ, worst {worst}; UBSan passed')


def harness_log(path):
    """A harness's stderr without the per-scene SCENE lines (UBSan / crash output only)."""
    return ''.join(l for l in path.read_text().splitlines(True) if not l.startswith('SCENE '))


def channel_delta(a, b):
    """Largest per-channel RGB888 difference between two byte-swapped RGB565 strip words."""
    a, b = ((a & 0xff) << 8) | (a >> 8), ((b & 0xff) << 8) | (b >> 8)
    def expand(c):
        r5, g6, b5 = c >> 11, (c >> 5) & 63, c & 31
        return (r5 << 3) | (r5 >> 2), (g6 << 2) | (g6 >> 4), (b5 << 3) | (b5 >> 2)
    return max(abs(x - y) for x, y in zip(expand(a), expand(b)))


if __name__ == '__main__':
    main()
