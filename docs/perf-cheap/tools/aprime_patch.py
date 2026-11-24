#!/usr/bin/env python3
"""perf-cheap A' as a source patch of firmware/src/render.cpp: aprime_patch.py IN OUT. Applied to this branch's render.cpp
before A' (B only) it gives A'; applied to 87f19af's it gives the reference the B-exactness checks compare against."""
import sys
s = open(sys.argv[1]).read()
def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (s.count(a), a[:80]); s = s.replace(a, b)
rep('''  uint32_t gen = 0; int H = 0; float light = 0; bool valid = false;   // cache key (light is exact: hit while the tube is at rest)''',
'''  // cache key: light = the light its colours were made for (renderTube's lightKey, perf-cheap A'), hiTop = the highlight
  // band's row (from the exact light), gen, H
  uint32_t gen = 0; int H = 0; float light = 0; int hiTop = 0; bool valid = false;''')
rep('''  int highlightTop(const Params &p, float lightDeg) const;''',
'''  int highlightTop(const Params &p, float lightDeg) const;
  // perf-cheap A': the light the palette's colours are made for, lightKey = the exact light in LIGHT_KEY_Q steps, re-keyed only
  // when the light leaves it by LIGHT_KEY_HYST (renderTube); lightKeyOk false: none yet
  float lightKey = 0; bool lightKeyOk = false;''')
rep('''  void buildPalette(const Params &p, float lightDeg, Palette &pal, const PalCache &pc) const;''',
'''  void buildPalette(const Params &p, float lightDeg, int hiTop, Palette &pal, const PalCache &pc) const;''')
rep('void buildPaletteRef(const Params &p, float lightDeg, Palette &pal) const;', 'void buildPaletteRef(const Params &p, float lightDeg, int hiTop, Palette &pal) const;')
rep('void Tube::buildPaletteRef(const Params &p, float lightDeg, Palette &pal) const {', 'void Tube::buildPaletteRef(const Params &p, float lightDeg, int hiTop, Palette &pal) const {')
rep('void Tube::buildPalette(const Params &p, float lightDeg, Palette &pal, const PalCache &pc) const {', 'void Tube::buildPalette(const Params &p, float lightDeg, int hiTop, Palette &pal, const PalCache &pc) const {')
rep('  int hiTop = highlightTop(p, lightDeg);\n', '', 2)
rep('''// Style top light blended (lightPhys) with a Lambert cylinder lit from 2*light (sim buildPalette).''',
'''// Style top light blended (lightPhys) with a Lambert cylinder lit from 2*light (sim buildPalette). lightDeg: the light the
// colours are made for (renderTube's lightKey); hiTop: the highlight band's row, from the exact light (highlightTop). The
// light's only other consumers here are colours: the Lambert weight lam (body shading, glassW's glass weight) and what
// follows from it (rowL -> bubbleRimRows, rowK); the band's rows and its tent take hiTop.''')
rep('''  if (!(pal.valid && pal.gen == gen && pal.H == t.H && pal.light == s.light)) {''',
'''  // perf-cheap A': the colours from the light in LIGHT_KEY_Q steps with hysteresis (a still watch's sensor noise no longer
  // rebuilds the palette every frame: each step moves a palette row by at most 1 RGB565 LSB, STATUS); every decision the
  // light takes stays on the exact light (the highlight row here, highlightTop; blickY, the fizz's highlight row, the inset)
  if (!t.lightKeyOk || fabsf(s.light - t.lightKey) > LIGHT_KEY_HYST) { t.lightKey = floorf(s.light / LIGHT_KEY_Q + 0.5f) * LIGHT_KEY_Q; t.lightKeyOk = true; }
  const float lightKey = t.lightKey; const int hiTop = t.highlightTop(p, s.light);
  if (!(pal.valid && pal.gen == gen && pal.H == t.H && pal.light == lightKey && pal.hiTop == hiTop)) {''')
rep('''    t.buildPalette(p, s.light, pal, *t.palCache);''', '''    t.buildPalette(p, lightKey, hiTop, pal, *t.palCache);''')
rep('''      Palette &r = *t.verifyPal; t.buildPaletteRef(p, s.light, r); int bad = 0;''', '''      Palette &r = *t.verifyPal; t.buildPaletteRef(p, lightKey, hiTop, r); int bad = 0;''')
rep('''    pal.valid = true; pal.gen = gen; pal.H = t.H; pal.light = s.light; pal.ver++;''', '''    pal.valid = true; pal.gen = gen; pal.H = t.H; pal.light = lightKey; pal.hiTop = hiTop; pal.ver++;''')
# constants and the getter
rep('''// Safe to call for tubes on different lanes (hours and minutes / seconds) concurrently from different tasks: each touches''',
'''uint32_t render_palette_builds(int idx) { return tubeAt(idx).pal.ver; }
float render_light_key(int idx) { const Tube &t = tubeAt(idx); return t.lightKeyOk ? t.lightKey : NAN; }
void render_set_light_key(int idx, float key) { Tube &t = tubeAt(idx); t.lightKey = key; t.lightKeyOk = key == key; }
// Safe to call for tubes on different lanes (hours and minutes / seconds) concurrently from different tasks: each touches''')
rep('''struct Palette {''', '''// perf-cheap A': the palette's colour light in steps of LIGHT_KEY_Q (any palette row moves at most 1 RGB565 LSB a step:
// docs/perf-cheap/tools/palstep.cpp), re-keyed when the exact light leaves the key by LIGHT_KEY_HYST (0.6 step). See sim.
#define LIGHT_KEY_Q 0.125f
#define LIGHT_KEY_HYST 0.075f
struct Palette {''')
open(sys.argv[2], 'w').write(s)
