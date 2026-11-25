#!/usr/bin/env python3
"""The params' NVS load / save (firmware/src/params_nvs.h, main.cpp paramsLoad / paramsFlush) against a mock
Preferences store, on the host (no board): python3 firmware/tools/test_params_nvs.py

Old blobs are written by programs built with the old schemas' own params_gen.h (git: v31 at 2439440^, v32 at
ed46e32^, v33 at 5ef545f): PRESET_DEFAULT with fizzCount 237 and a few fields set on both sides of v33's viewElevation
and v34's edgeShadeEnd. A v33 / v32 / v31 blob must load as v34 with every field of the old schema equal by name (v 34;
v31: edgeShadePow -> edgeShadeShape 1.5), edgeShadeEnd 0 (v32 / v31: viewElevation 0 too), and be saved at once under
the v34 CRC; the next boot restores it as is. A truncated blob, a failed
read and an unknown schema leave the defaults and NVS untouched (a dropped blob: one line with the schema, CRC and
bytes found and expected); a failed blob write keeps the old blob and CRC (the next boot migrates again); a failed CRC
write (or power lost after the blob) leaves the v34 blob under the old CRC: the next boot restores the migrated look and
relabels the CRC. Exit 1 on a failure.
"""
import os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY = {'v31': ('2439440^', 0x6bb6cdaf), 'v32': ('ed46e32^', 0xcd2763c1), 'v33': ('5ef545f', 0x970ee607)}   # commit of the schema's params_gen.h, its CRC
SET = {'fizzCount': '237', 'glassWall': '4.5', 'vertical': '1', 'highlightH': '7.25', 'ambientLight': '0.123'}
SET_V = {'v31': {'edgeShadePow': '2.5'}, 'v32': {'edgeShadeShape': '2.5'}, 'v33': {'edgeShadeShape': '2.5', 'edgeShadeFold': '0.7', 'viewElevation': '12'}}
SIZE = {'v31': 720, 'v32': 720, 'v33': 724}

SETPARAM = r'''
static bool setParam(Params &p, const char *name, const char *val) {   // main.cpp setParam
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
static void dumpFields(const Params &p) {   // F name hex, every field by name (bool 1 B, else 4 B)
  for (const ParamField &f : PARAM_FIELDS) {
    const uint8_t *q = (const uint8_t *)&p + f.off; printf("F %s ", f.name);
    for (int i = 0; i < (f.type == 'b' ? 1 : 4); i++) printf("%02x", q[i]);
    printf("\n");
  }
}
'''

# an old schema's blob: argv[1] = blob file, then name=value
WRITER = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "gen/params_gen.h"
''' + SETPARAM + r'''
int main(int argc, char **argv) {
  Params p = PRESET_DEFAULT;
  for (int i = 2; i < argc; i++) { char *eq = strchr(argv[i], '='); *eq = 0; if (!setParam(p, argv[i], eq + 1)) return 4; }
  FILE *f = fopen(argv[1], "wb"); fwrite(&p, sizeof p, 1, f); fclose(f);
  printf("SIZE %zu\nCRC %08x\n", sizeof p, PARAMS_SCHEMA_CRC); dumpFields(p);
  return 0;
}
'''

# the firmware's load (and a second boot) on a mock store: argv crc-hex blob-file|- fail-flags
LOADER = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include "params_nvs.h"
''' + SETPARAM + r'''
struct Log {   // Print's print / println
  std::string line;
  void print(const char *s) { line += s; }
  void println(const char *s) { line += s; printf("LOG %s\n", line.c_str()); line.clear(); }
};
struct MockPrefs {   // Arduino Preferences' semantics for the calls used: 0 = missing / failed
  bool hasCrc = false, hasBlob = false; uint32_t crc = 0; std::vector<uint8_t> blob;
  bool failRead = false, failBlob = false, failCrc = false;
  uint32_t getUInt(const char *, uint32_t d = 0) { return hasCrc ? crc : d; }
  size_t getBytesLength(const char *) { return hasBlob ? blob.size() : 0; }
  size_t getBytes(const char *, void *buf, size_t maxLen) {
    if (!hasBlob || blob.size() > maxLen || failRead) return 0;
    memcpy(buf, blob.data(), blob.size()); return blob.size();
  }
  size_t putBytes(const char *, const void *buf, size_t n) {
    if (failBlob) return 0;
    blob.assign((const uint8_t *)buf, (const uint8_t *)buf + n); hasBlob = true; return n;
  }
  size_t putUInt(const char *, uint32_t v) { if (failCrc) return 0; crc = v; hasCrc = true; return 4; }
};
static void dumpStore(const MockPrefs &s, const Params &p) {
  printf("STORE %08x %zu %s\n", s.hasCrc ? s.crc : 0, s.blob.size(),
         s.blob.size() == sizeof(Params) && !memcmp(s.blob.data(), &p, sizeof p) ? "params" : "other");
  printf("BLOB "); for (uint8_t c : s.blob) printf("%02x", c); printf("\n");
}
int main(int argc, char **argv) {
  MockPrefs s; Log out;
  s.crc = strtoul(argv[1], nullptr, 16); s.hasCrc = s.crc != 0;
  if (strcmp(argv[2], "-")) { FILE *f = fopen(argv[2], "rb"); int c; while ((c = fgetc(f)) != EOF) s.blob.push_back((uint8_t)c); fclose(f); s.hasBlob = true; }
  if (argc > 4) s.blob.resize(atoi(argv[4]));   // truncated
  const char *fl = argv[3];
  s.failRead = strstr(fl, "read"); s.failBlob = strstr(fl, "blob"); s.failCrc = strstr(fl, "crc");
  Params p = PRESET_DEFAULT;
  printf("RET %d\n", (int)paramsNvsLoad(s, p, out));
  printf("DEFAULTS %d\n", !memcmp(&p, &PRESET_DEFAULT, sizeof p));
  dumpFields(p); dumpStore(s, p);
  s.failRead = s.failBlob = s.failCrc = false;
  Params q = PRESET_DEFAULT;   // the next boot
  printf("RET2 %d\n", (int)paramsNvsLoad(s, q, out));
  printf("SAME2 %d\n", !memcmp(&p, &q, sizeof p));
  printf("STORE2 %08x %zu\n", s.hasCrc ? s.crc : 0, s.blob.size());
  return 0;
}
'''

def cxx(src, inc, out):
    subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O1', '-Wall', '-Wno-unused-function', '-I', str(inc), '-x', 'c++', '-', '-o', str(out)],
                   input=src.encode(), check=True)

def parse(text):
    r = {'F': {}, 'LOG': []}
    for l in text.splitlines():
        k, _, v = l.partition(' ')
        if k == 'F': n, h = v.split(); r['F'][n] = h
        elif k == 'LOG': r['LOG'].append(v)
        else: r[k] = v
    return r

def f32(h):
    import struct; return struct.unpack('<f', bytes.fromhex(h))[0]

def main():
    fails = []
    def check(ok, what):
        print(('ok   ' if ok else 'FAIL ') + what)
        if not ok: fails.append(what)
    with tempfile.TemporaryDirectory(prefix='watches-nvs-') as tmp:
        tmp = Path(tmp)
        cxx(LOADER, ROOT / 'firmware/src', tmp / 'load')
        cur = 0x44a578ad
        blobs = {}
        for tag, (rev, crc) in LEGACY.items():
            d = tmp / tag / 'gen'; d.mkdir(parents=True)
            (d / 'params_gen.h').write_bytes(subprocess.run(['git', 'show', f'{rev}:firmware/src/gen/params_gen.h'], cwd=ROOT, stdout=subprocess.PIPE, check=True).stdout)
            cxx(WRITER, tmp / tag, tmp / tag / 'w')
            w = parse(subprocess.run([str(tmp / tag / 'w'), str(tmp / f'{tag}.bin'), *(f'{k}={v}' for k, v in {**SET, **SET_V[tag]}.items())],
                                     stdout=subprocess.PIPE, text=True, check=True).stdout)
            check(w['SIZE'] == str(SIZE[tag]) and int(w['CRC'], 16) == crc, f'{tag} schema ({rev}): {w["SIZE"]} B, CRC {w["CRC"]}')
            blobs[tag] = w

        def load(crc, blob, flags='-', trunc=None):
            args = [str(tmp / 'load'), f'{crc:x}', blob, flags] + ([str(trunc)] if trunc else [])
            return parse(subprocess.run(args, stdout=subprocess.PIPE, text=True, check=True).stdout)

        for tag, (rev, crc) in LEGACY.items():
            old = blobs[tag]['F']; r = load(crc, str(tmp / f'{tag}.bin'))
            new = r['F']
            renamed = {'edgeShadePow': 'edgeShadeShape'} if tag == 'v31' else {}
            expect = {renamed.get(n, n): h for n, h in old.items()}
            expect['v'] = (34).to_bytes(4, 'little').hex(); expect['edgeShadeEnd'] = '00000000'
            if tag != 'v33': expect['viewElevation'] = '00000000'
            if tag == 'v31': expect['edgeShadeShape'] = bytes.fromhex('0000c03f').hex()   # 1.5f
            bad = [n for n in sorted(set(expect) | set(new)) if expect.get(n) != new.get(n)]
            check(r['RET'] == '1' and not bad, f'{tag} blob ({SIZE[tag]} B) -> v34: {len(new)} fields, fizzCount {f32(new["fizzCount"]):g}, '
                  f'viewElevation {f32(new["viewElevation"]):g}, edgeShadeFold {f32(new["edgeShadeFold"]):g}, edgeShadeEnd {f32(new["edgeShadeEnd"]):g}, edgeShadeShape {f32(new["edgeShadeShape"]):g}, v {int.from_bytes(bytes.fromhex(new["v"]), "little")}'
                  + (f'; differ: {bad[:8]}' if bad else ''))
            check(f32(new['fizzCount']) == 237 and f32(new['ambientLight']) == f32(old['ambientLight']) and f32(new['highlightH']) == 7.25,
                  f'{tag}: fizzCount 237, highlightH 7.25, ambientLight 0.123 (past viewElevation / edgeShadeEnd) kept')
            check(r['STORE'] == f'{cur:08x} 728 params', f'{tag}: saved at once as v34 ({r["STORE"]}); log {r["LOG"][:1]}')
            check(r['RET2'] == '1' and r['SAME2'] == '1' and 'params: restored from nvs' in r['LOG'], f'{tag}: the next boot restores the v34 blob as is')

        DROP = 'params: nvs blob dropped: schema'
        WANT = f'expected v34 (crc {cur:08x}, 728 B), v33 (724 B) or v32 / v31 (720 B); defaults, replaced on the next save'
        v32 = str(tmp / 'v32.bin'); v32crc = LEGACY['v32'][1]; v32hex = open(v32, 'rb').read().hex()
        r = load(v32crc, v32, trunc=716)
        check(r['RET'] == '0' and r['DEFAULTS'] == '1' and r['STORE'] == f'{v32crc:08x} 716 other' and r['BLOB'] == v32hex[:716 * 2],
              f'truncated v32 blob (716 B): defaults, NVS kept ({r["STORE"]}); log {r["LOG"][:1]}')
        check(r['LOG'][:1] == [f'{DROP} v32 (crc {v32crc:08x}, 716 B), {WANT}'], 'truncated v32 blob: the drop line names schema, crc, bytes, expected')
        r = load(cur, v32)
        check(r['RET'] == '0' and r['DEFAULTS'] == '1' and r['LOG'][:1] == [f'{DROP} v34 (crc {cur:08x}, 720 B), {WANT}'],
              f'v34 CRC on a 720 B blob: defaults; log {r["LOG"][:1]}')
        v33crc = LEGACY['v33'][1]
        r = load(v33crc, v32)
        check(r['RET'] == '0' and r['DEFAULTS'] == '1' and r['LOG'][:1] == [f'{DROP} v33 (crc {v33crc:08x}, 720 B), {WANT}'],
              f'v33 CRC on a 720 B blob: defaults; log {r["LOG"][:1]}')
        r = load(v33crc, str(tmp / 'v33.bin'), trunc=720)
        check(r['RET'] == '0' and r['DEFAULTS'] == '1' and r['STORE'] == f'{v33crc:08x} 720 other',
              f'truncated v33 blob (720 B): defaults, NVS kept; log {r["LOG"][:1]}')
        r = load(v32crc, v32, 'read')
        check(r['RET'] == '0' and r['DEFAULTS'] == '1' and r['STORE'] == f'{v32crc:08x} 720 other' and r['BLOB'] == v32hex,
              f'v32 blob, read fails: defaults, NVS kept; log {r["LOG"][:1]}')
        r = load(v32crc, v32, 'blob')
        check(r['RET'] == '1' and r['DEFAULTS'] == '0' and r['STORE'] == f'{v32crc:08x} 720 other' and r['BLOB'] == v32hex
              and any('not saved (blob write)' in l for l in r['LOG']), f'v32 blob, blob write fails: migrated in RAM, old blob and CRC kept; log {r["LOG"][:1]}')
        for tag in ('v32', 'v33'):
            ocrc = LEGACY[tag][1]; r = load(ocrc, str(tmp / f'{tag}.bin'), 'crc')
            check(r['RET'] == '1' and r['STORE'] == f'{ocrc:08x} 728 params' and any('not saved (crc write)' in l for l in r['LOG'])
                  and r['RET2'] == '1' and r['SAME2'] == '1' and r['STORE2'] == f'{cur:08x} 728'
                  and any('interrupted v34 save: crc relabelled' in l for l in r['LOG']),
                  f'{tag} blob, CRC write fails (the v34 blob under the {tag} CRC): the next boot restores the migrated look and relabels ({r["STORE2"]})')
        r = load(v32crc, v32, 'blob')
        check(r['RET2'] == '1' and r['SAME2'] == '1' and r['STORE2'] == f'{cur:08x} 728',
              f'v32 blob, blob write fails: the next boot migrates again ({r["STORE2"]})')
        r = load(0x12345678, v32)
        check(r['RET'] == '0' and r['DEFAULTS'] == '1' and r['STORE'] == '12345678 720 other' and r['BLOB'] == v32hex
              and r['LOG'][:1] == [f'{DROP} unknown (crc 12345678, 720 B), {WANT}'], f'unknown schema: defaults, NVS kept; log {r["LOG"][:1]}')
        r = load(0, '-')
        check(r['RET'] == '0' and r['DEFAULTS'] == '1' and r['LOG'] == [] and r['STORE'] == '00000000 0 other', 'empty NVS: defaults, nothing logged')
    print('all ok' if not fails else f'FAIL {len(fails)}')
    sys.exit(1 if fails else 0)

if __name__ == '__main__': main()
