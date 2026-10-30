#!/usr/bin/env python3
"""Check the firmware's packed blends against scalar RGB888 interpolation, and the residue tint
(traceFillRow, ResidueTint) against the sim's filmMix formula.

Uses the actual render.cpp source; requires native C++, no board.
Run: python3 firmware/tools/check_residue.py
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def block(source, start, end_token):
    """Source from the line holding `start` through the brace that closes the first `{` after it."""
    first = source.rfind('\n', 0, source.index(start)) + 1
    brace = source.index('{', first)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[first:end] + end_token


def function(source, name):
    return block(source, name + '(', '')


HARNESS = r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <algorithm>
static uint16_t *FILM_PHI = nullptr, *FILM_LG = nullptr;
static uint8_t *FILM_EX = nullptr;
__HELPERS__

static uint16_t reference(uint16_t bg, uint16_t fg, int t) {
  if (t <= 0) return bg;
  if (t >= 256) return fg;
  int out[3];
  const int shift[3] = {11, 5, 0}, bits[3] = {5, 6, 5};
  for (int i = 0; i < 3; ++i) {
    int mask = (1 << bits[i]) - 1;
    int a = (bg >> shift[i]) & mask, b = (fg >> shift[i]) & mask;
    a = (a << (8 - bits[i])) | (a >> (2 * bits[i] - 8));
    b = (b << (8 - bits[i])) | (b >> (2 * bits[i] - 8));
    out[i] = (a * (256 - t) + b * t + 128) / 256;
  }
  return (uint16_t)(((out[0] & 248) << 8) | ((out[1] & 252) << 3) | (out[2] >> 3));
}
// The sim's residue pixel (render.ts tint / filmMix): B^(1-T/256) C^(T/256) per channel from the Q8 logs.
static uint16_t tintReference(uint16_t bg, uint16_t fg, int t) {
  if (t <= 0) return bg;
  if (t >= 256) return fg;
  int b[3], c[3];
  expand565(bg, b[0], b[1], b[2]); expand565(fg, c[0], c[1], c[2]);
  int o[3];
  for (int i = 0; i < 3; ++i) o[i] = FILM_EX[(FILM_LG[b[i]] * (256 - t) + FILM_LG[c[i]] * t + 128) >> 8];
  return rgb565(o[0], o[1], o[2]);
}
static uint16_t identityPhi[257];
// tint parameters for B -> C; phi / K / G pick the depth law (identity: depthT(A) == A for A <= 256)
static ResidueTint tintOf(uint16_t bg, uint16_t fg, const uint16_t *phi = identityPhi, uint32_t K = 65536, int G = 256) {
  int b[3], c[3];
  expand565(bg, b[0], b[1], b[2]); expand565(fg, c[0], c[1], c[2]);
  ResidueTint t;
  t.lgB0 = FILM_LG[b[0]]; t.lgB1 = FILM_LG[b[1]]; t.lgB2 = FILM_LG[b[2]];
  t.dl0 = FILM_LG[c[0]] - t.lgB0; t.dl1 = FILM_LG[c[1]] - t.lgB1; t.dl2 = FILM_LG[c[2]] - t.lgB2;
  t.ex = FILM_EX; t.phi = phi; t.K = K; t.G = G; t.kq = K * (1.0f / 65536); t.full = fg;
  return t;
}
// The sim's depth (render.ts depth, rounded): path index (A K + 2^15) >> 16, FILM_PHI, times traceAmount, chord clamp.
static int depthReference(uint64_t A, uint64_t K, int G) {
  const uint64_t i = (A * K + 32768) >> 16;
  const int f = i >= 256 ? 256 : FILM_PHI[i];
  const int T = (f * G + 128) >> 8;
  return T < 256 ? T : 256;
}
static void checkBlend(uint16_t bg, uint16_t fg, int t) {
  uint16_t want = reference(bg, fg, t);
  if (blend565T(bg, fg, t) != want || blend565(bg, fg, t * (1.0f / 256)) != want) {
    std::fprintf(stderr, "shared blend: bg=%04x fg=%04x alpha=%d want=%04x\n", bg, fg, t, want);
    std::exit(1);
  }
}
static void checkTint(uint16_t gotBE, uint16_t bg, uint16_t fg, int t) {
  uint16_t want = tintReference(bg, fg, t);
  if (__builtin_bswap16(gotBE) != want) {
    std::fprintf(stderr, "residue tint: bg=%04x fg=%04x depth=%d got=%04x want=%04x\n",
                 bg, fg, t, __builtin_bswap16(gotBE), want);
    std::exit(1);
  }
}
int main() {
  FILM_PHI = new uint16_t[257]; FILM_LG = new uint16_t[256]; FILM_EX = new uint8_t[4096];
  buildFilmLuts();
  for (int i = 0; i <= 256; ++i) identityPhi[i] = (uint16_t)i;
  uint16_t row[303], depth[303], lut[2 * TRACE_LUT];
  for (int i = 0; i < 303; ++i) depth[i] = (uint16_t)(i ? i - 1 : 0);
  // Shared blends: every RGB565 colour in both roles against the anchors, every fractional alpha,
  // opposing packed lanes (including borrows from red into blue).
  const uint16_t anchors[] = {0, 0xffff, 0xf800, 0x07e0, 0x001f, 0x07ff, 0xf81f, 0xffe0};
  uint64_t blends = 0, tints = 0, depths = 0;
  for (uint16_t anchor : anchors) for (unsigned c = 0; c < 65536; ++c) for (int reverse = 0; reverse < 2; ++reverse) {
    uint16_t bg = reverse ? anchor : c, fg = reverse ? c : anchor;
    for (int t = 0; t <= 256; t += reverse ? 1 : 3) { checkBlend(bg, fg, t); ++blends; }
  }
  // Residue tint: the same colour pairs, every depth 0..300 (>= 256: the full chord) through traceFillRow with
  // the identity depth law, the guard columns at both ends of the span untouched.
  for (uint16_t anchor : anchors) for (unsigned c = 0; c < 65536; ++c) for (int reverse = 0; reverse < 2; ++reverse) {
    uint16_t bg = reverse ? anchor : c, fg = reverse ? c : anchor;
    const ResidueTint t = tintOf(bg, fg);
    std::fill_n(row, 303, __builtin_bswap16(bg));
    if (c & 1) traceFillRow(row, depth, 1, 302, 0, 0, t, 1, 300, lut);   // one span, or the same split in two
    else traceFillRow(row, depth, 1, 151, 151, 302, t, 1, 300, lut);
    checkTint(row[0], bg, fg, 0); checkTint(row[302], bg, fg, 0);
    for (int i = 1; i < 302; ++i) checkTint(row[i], bg, fg, std::min(256, i - 1));
    tints += 301;
  }
  // The depth law with the real FILM_PHI: every coat A of the domain (eta <= FILM_ETA_MAX: A <= 12452, so A K
  // stays in 32 bits) against row weights from the centre row to the cap and gains up to 10.
  const uint32_t Ks[] = {256, 300, 1000, 4096, 65536, 100000, 262144};
  const int Gs[] = {1, 51, 256, 512, 2560};
  for (uint32_t K : Ks) for (int G : Gs) for (unsigned A = 0; A <= 12452; ++A) {
    const ResidueTint t = tintOf(0x1234, 0xabcd, FILM_PHI, K, G);
    if (t.depthT(A) != depthReference(A, K, G)) {
      std::fprintf(stderr, "depth: A=%u K=%u G=%d got=%d want=%d\n", A, K, G, t.depthT(A), depthReference(A, K, G));
      std::exit(1);
    }
    ++depths;
  }
  // The per-row LUT path: narrow coat bands (zeros in between) at several row weights and gains, the band's
  // extremes passed as the caller computes them.
  uint16_t band[303];
  const int bands[][2] = {{1, 40}, {300, 360}, {2000, 2300}, {9000, 12452}};
  for (const auto &bd : bands) for (uint32_t K : Ks) for (int G : {256, 512}) for (unsigned c = 0; c < 65536; c += 61) {
    const uint16_t bg = (uint16_t)c, fg = (uint16_t)(c * 2654435761u >> 16);
    int lo = 65535, hi = 0;
    for (int i = 0; i < 303; ++i) {
      band[i] = (uint16_t)(i % 9 == 4 ? 0 : bd[0] + (i * 7 + c) % (bd[1] - bd[0] + 1));
      if (i >= 1 && i < 302 && band[i]) { lo = std::min(lo, (int)band[i]); hi = std::max(hi, (int)band[i]); }
    }
    std::fill_n(row, 303, __builtin_bswap16(bg));
    if (c & 1) traceFillRow(row, band, 1, 302, 0, 0, tintOf(bg, fg, FILM_PHI, K, G), lo, hi, lut);
    else traceFillRow(row, band, 1, 100, 100, 302, tintOf(bg, fg, FILM_PHI, K, G), lo, hi, lut);
    checkTint(row[0], bg, fg, 0); checkTint(row[302], bg, fg, 0);
    for (int i = 1; i < 302; ++i) checkTint(row[i], bg, fg, band[i] ? depthReference(band[i], K, G) : 0);
    tints += 301;
  }
  row[0] = 0xa55a;
  traceFillRow(row, depth, 0, 0, 0, 0, tintOf(0, 0xffff), 1, 300, lut);
  if (row[0] != 0xa55a) return 1;
  std::printf("shared blends: %llu scalar cases; residue tint: %llu cases match the sim's filmMix; depth law: %llu cases; span guards intact\n",
              (unsigned long long)blends, (unsigned long long)tints, (unsigned long long)depths);
}
'''


def main():
    source = (ROOT / 'firmware/src/render.cpp').read_text()
    helpers = '\n'.join([*(function(source, name) for name in ('fmn', 'expand565', 'rgb565', 'blend565T', 'blend565', 'srgbLin', 'srgbEnc', 'buildFilmLuts')),
                         block(source, 'struct ResidueTint {', ';'), '#define TUBE_IRAM',
                         re.search(r'#define TRACE_LUT \d+', source).group(0),
                         *(function(source, name) for name in ('traceFillLut', 'traceFillLutI', 'traceFillRow'))])
    with tempfile.TemporaryDirectory(prefix='watches-residue-') as tmp:
        cpp, exe = Path(tmp) / 'check.cpp', Path(tmp) / 'check'
        cpp.write_text(HARNESS.replace('__HELPERS__', helpers))
        subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O2', '-Wall', '-Wextra',
                        '-fsanitize=undefined', str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
