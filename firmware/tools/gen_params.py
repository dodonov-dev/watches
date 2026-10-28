#!/usr/bin/env python3
"""Generate firmware/src/gen/params_gen.h (Params struct + presets) and
firmware/src/gen/sprites_gen.h (digit sprite sheets) from the sim's preset JSON files and assets.

Usage (from repo root):  python3 firmware/tools/gen_params.py presets/1.json [more.json ...]
The first preset becomes PRESET_DEFAULT.
"""
import json, os, re, sys, zlib
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'firmware', 'src', 'gen')
SHEETS = [
    'digits-steel', 'digits-brass-steampunk', 'digits-copper-gauge',
    'digits-forged-iron', 'digits-ivory-enamel', 'digits-carved-slate',
    'digits-amber-resin',
]  # digitFont 5..11
# (name, ctype) — order defines the struct layout. Mirrors sim/src/params.ts `Params`.
FIELDS = [
 ('v','int'),
 ('tubeHeight','float'),('hoursY','float'),('minutesY','float'),
 ('liquid','rgb'),('liquidHi','rgb'),('liquidLo','rgb'),('tubeBack','rgb'),('tubeBack2','rgb'),('tubeBackGradient','float'),('glassHi','rgb'),('glassBody','float'),('glassHiBright','float'),('glassReflect','float'),('glassRim','float'),('glassWall','float'),('glassWallGlow','float'),('wallWet','float'),('rimLight','float'),('rimTint','rgb'),('glassOverLiquid','float'),('lens','float'),('lensCurve','float'),('bubbleRim','rgb'),
 ('remaining','bool'),('vertical','bool'),('highlightH','float'),('highlightInset','float'),('highlightBright','float'),('highlightSharp','float'),('shadeDepth','float'),('liquidThin','float'),('contactAngle','float'),
 ('contactHyst','float'),('contactDyn','float'),('capLength','float'),('meniscusLens','float'),
  ('meniscusK','float'),('meniscusDamp','float'),('meniscusInertia','float'),('wetFilm','float'),('traces','bool'),('traceAmount','float'),('traceDry','float'),('traceDrain','float'),('traceStain','float'),('traceFilm','float'),('edgeSoft','float'),
 ('frontBright','float'),('surfaceBand','float'),('surfaceRim','float'),('surfaceWidth','float'),('surfaceTone','float'),('surfaceFill','float'),('surfaceBlick','float'),('edgeGlow','float'),('glowStrength','float'),('cornerR','float'),('edgeLightGain','float'),
 ('bubble','bool'),('bubbleW','float'),('bubbleH','float'),('bubbleGap','float'),('bubbleY','float'),('bubbleDark','float'),('bubbleRollGain','float'),('bubbleTiltGain','float'),
 ('fizz','bool'),('fizzCount','float'),('fizzSize','float'),('fizzSizeVar','float'),('fizzShadeOff','float'),('fizzSpeed','float'),('fizzDriftGain','float'),('fizzAcrossGain','float'),('fizzFlatRise','float'),('fizzSquash','float'),('fizzEdgeRise','float'),('fizzFoamLife','float'),('fizzDepth','float'),('fizzBlick','float'),('fizzSource','float'),('fizzSourceX','float'),('fizzSourceY','float'),('fizzSourceSpread','float'),('fizzSourceRate','float'),
 ('ticksH','bool'),('tickStepH','float'),('tickMajorEveryH','float'),('tickMinorHeightH','float'),('tickMajorHeightH','float'),
 ('tickMinorWidthH','float'),('tickMajorWidthH','float'),('tickColorH','rgb'),('tickMajorColorH','rgb'),('tickPosH','float'),
 ('ticksM','bool'),('tickStepM','float'),('tickMajorEveryM','float'),('tickMinorHeightM','float'),('tickMajorHeightM','float'),
 ('tickMinorWidthM','float'),('tickMajorWidthM','float'),('tickColorM','rgb'),('tickMajorColorM','rgb'),('tickPosM','float'),
 ('ticksOnTop','bool'),('tickLens','float'),('tickParallax','float'),('tickDryLens','float'),('tickEmboss','float'),
 ('digits','bool'),('digitColor','rgb'),('digitColor2','rgb'),('digitShadow','bool'),('digitShadowColor','rgb'),('digitShadowStrength','float'),('digitShadowOffset','float'),
 ('digitTint','rgb'),('digitTintAmount','float'),('digitTone','float'),('digitFont','float'),
 ('digitScaleX','float'),('digitScaleY','float'),('digitScaleXMin','float'),('digitScaleYMin','float'),
 ('digitBottomMin','float'),('digitBottom','float'),('digitsOnTop','bool'),('bottomLens','float'),('digitDryLens','float'),('topLens','float'),('topParallax','float'),('digitParallax','float'),
 ('liquidTransparency','float'),('markContrast','float'),('digitsLeadingZero','bool'),
 ('digitMinuteStep','float'),('digitHourStep','float'),('digitHourStart','float'),('digitMinuteStart','float'),('digitsLastOnlyH','bool'),('digitsLastOnlyM','bool'),
 ('freeLiquid','bool'),('freeGain','float'),('freeDamp','float'),('freeBounce','float'),('freeHomeK','float'),
 ('readTiltStart','float'),('readTiltEnd','float'),('playHold','float'),
 ('fillK','float'),('fillDamp','float'),('fillSloshGain','float'),('angleK','float'),('angleDamp','float'),
 ('angleTiltGain','float'),('angleGyroGain','float'),('angleMax','float'),('lightPhys','float'),('lightAngle','float'),('acrossK','float'),('acrossDamp','float'),('acrossGyroGain','float'),('shakeGain','float'),('deadzone','float'),
 ('accelLpHz','float'),('gyroHpHz','float'),('gyroDeadzone','float'),('gyroMax','float'),('inputGain','float'),
 ('brightness','float'),('liquidBright','float'),('tickBright','float'),('digitBright','float'),('ambientLight','float'),
]
CTYPE = {'int': 'int', 'float': 'float', 'bool': 'bool', 'rgb': 'uint32_t'}

def px_keys():
    """sim/src/params.ts PX_KEYS / PX_WHOLE_KEYS: {name: 1 scaled to the board's canvas, 2 scaled and rounded}
    (sim boardParams, firmware main.cpp paramsChanged)."""
    src = open(os.path.join(ROOT, 'sim', 'src', 'params.ts')).read()
    def names(const):
        m = re.search(r'export const %s\b[^=]*= \[(.*?)\]' % const, src, re.S)
        if not m: sys.exit('gen_params: %s not found in sim/src/params.ts' % const)
        return re.findall(r"'(\w+)'", m.group(1))
    keys, whole = names('PX_KEYS'), names('PX_WHOLE_KEYS')
    types = dict(FIELDS)
    bad = [k for k in keys if types.get(k) != 'float'] + [k for k in whole if k not in keys]
    if bad: sys.exit('gen_params: PX_KEYS must be float fields, PX_WHOLE_KEYS a subset: %s' % bad)
    return {k: 2 if k in whole else 1 for k in keys}

def cval(t, v):
    if t == 'rgb': return '0x%06X' % int(v.lstrip('#'), 16)
    if t == 'bool': return 'true' if v else 'false'
    if t == 'int': return str(int(v))
    return repr(float(v)) + 'f'

def ident(path):
    return re.sub(r'\W', '_', os.path.splitext(os.path.basename(path))[0])

def gen_params(presets):
    o = ['// GENERATED by firmware/tools/gen_params.py — do not edit. Mirrors sim/src/params.ts.',
         '#pragma once', '#include <stdint.h>', '#include <stddef.h>', '', 'struct Params {']
    for n, t in FIELDS: o.append('  %s %s;' % (CTYPE[t], n))
    crc = zlib.crc32(','.join('%s:%s' % f for f in FIELDS).encode()) & 0xffffffff
    o += ['};', '', '#define PARAMS_NUM_FIELDS %d' % len(FIELDS),
          '#define PARAMS_SCHEMA_CRC 0x%08xu  // field names+types; guards the NVS blob' % crc, '',
          '// Field table for serial/GATT/JSON access: name, type code (i/f/b/c), byte offset, px = a design-px',
          '// dimension scaled to the board\'s canvas: 1 scaled, 2 scaled and rounded (sim params.ts boardParams)',
          'struct ParamField { const char *name; char type; uint16_t off; uint8_t px; };',
          'static const ParamField PARAM_FIELDS[PARAMS_NUM_FIELDS] = {']
    px = px_keys()
    for n, t in FIELDS:
        o.append('  {"%s", \'%s\', (uint16_t)offsetof(Params, %s), %d},' % (n, {'int':'i','float':'f','bool':'b','rgb':'c'}[t], n, px.get(n, 0)))
    o.append('};')
    for i, (path, p) in enumerate(presets):
        o += ['', '// from %s' % os.path.relpath(path, ROOT), 'static const Params PRESET_%s = {' % ident(path).upper()]
        for n, t in FIELDS:
            if n not in p: sys.exit('preset %s lacks key %s' % (path, n))
            o.append('  %s, // %s' % (cval(t, p[n]), n))
        o.append('};')
        extra = set(p) - {n for n, _ in FIELDS}
        if extra: print('warning: unknown keys in', path, extra)
    o += ['', '#define PRESET_DEFAULT PRESET_%s' % ident(presets[0][0]).upper(), '']
    with open(os.path.join(OUT, 'params_gen.h'), 'w') as f: f.write('\n'.join(o))

def gen_sprites():
    o = ['// GENERATED by firmware/tools/gen_params.py — digit sprite sheets (RGBA8, row-major).',
         '#pragma once', '#include <stdint.h>', '',
         'struct SpriteSheet { uint16_t w, h, cellW, cellH; uint8_t widths[10]; const uint8_t *rgba; };', '']
    names = []
    for s in SHEETS:
        base = os.path.join(ROOT, 'sim', 'public', 'assets', s + '.png')
        meta = json.load(open(base + '.json'))
        im = Image.open(base).convert('RGBA')
        data = im.tobytes()
        cname = s.replace('-', '_')
        o.append('static const uint8_t %s_rgba[%d] = {' % (cname, len(data)))
        for i in range(0, len(data), 64):
            o.append(','.join(str(b) for b in data[i:i+64]) + ',')
        o.append('};')
        o.append('static const SpriteSheet SPRITE_%s = {%d, %d, %d, %d, {%s}, %s_rgba};' % (
            cname.upper(), im.width, im.height, meta['cellW'], meta['cellH'], ','.join(map(str, meta['widths'])), cname))
        names.append('&SPRITE_' + cname.upper())
        print('%s: %dx%d %d bytes' % (s, im.width, im.height, len(data)))
    o += ['', '#define NUM_SPRITE_SHEETS %d' % len(SHEETS),
          'static const SpriteSheet *const SPRITE_SHEETS[NUM_SPRITE_SHEETS] = {%s};' % ', '.join(names), '']
    with open(os.path.join(OUT, 'sprites_gen.h'), 'w') as f: f.write('\n'.join(o))

if __name__ == '__main__':
    paths = sys.argv[1:] or [os.path.join(ROOT, 'presets', '1.json')]
    os.makedirs(OUT, exist_ok=True)
    gen_params([(p, json.load(open(p))) for p in paths])
    gen_sprites()
    print('wrote', OUT)
