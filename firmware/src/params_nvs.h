#pragma once
// The params' NVS blob (namespace lw: "cur" = Params, "crc" = its schema CRC): the boot load with the migrations from
// older schemas, and the save. Templates over the store (Preferences) and the log (Print), so the host test
// (tools/test_params_nvs.py) runs these very functions against a mock store.
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include "gen/params_gen.h"

// Legacy layouts still read. v35 = v36 without fizzPhys (4 B after fizzBlick, in the fizz block; every later field 4 B
// lower; every field before it, the older steps' insert points included, at its v36 offset). v34 = v35 without
// edgeShadeEndWidth (4 B after edgeShadeEnd; every later field 4 B lower). v33 = v34 without edgeShadeEnd (4 B after
// edgeShadeFold; every later field 4 B lower again). v31 (edgeShadePow) and v32 (edgeShadeShape in that slot) are one
// layout: v33 without viewElevation (4 B after `vertical`; every later field 4 B lower again). The host test checks this
// against v31's, v32's, v33's, v34's and v35's own params_gen.h, field by field.
#define PARAMS_SCHEMA_CRC_V31 0x6bb6cdafu
#define PARAMS_SCHEMA_CRC_V32 0xcd2763c1u
#define PARAMS_SCHEMA_CRC_V33 0x970ee607u
#define PARAMS_SCHEMA_CRC_V34 0x44a578adu
#define PARAMS_SCHEMA_CRC_V35 0xa97f1010u
constexpr int PARAMS_V = 36;
constexpr size_t PARAMS_V32_SIZE = 720, PARAMS_V33_SIZE = 724, PARAMS_V34_SIZE = 728, PARAMS_V35_SIZE = 732;
constexpr size_t PARAMS_V36_FIZZ_PHYS = offsetof(Params, fizzPhys);
constexpr size_t PARAMS_V35_END_WIDTH = offsetof(Params, edgeShadeEndWidth);
constexpr size_t PARAMS_V34_EDGE_SHADE_END = offsetof(Params, edgeShadeEnd);   // (the same offset in v34)
constexpr size_t PARAMS_V33_VIEW_ELEVATION = offsetof(Params, viewElevation) - 8;   // its offset in the v33 layout
static_assert(PARAMS_SCHEMA_CRC == 0x76872393u, "params schema changed: add the migration from v36 (params_nvs.h paramsNvsLoad)");
static_assert(offsetof(Params, v) == 0 && sizeof(Params::v) == 4, "v first: the migrations set it");
static_assert(sizeof(Params) == PARAMS_V35_SIZE + 4 && PARAMS_V35_SIZE == PARAMS_V34_SIZE + 4 && PARAMS_V34_SIZE == PARAMS_V33_SIZE + 4 &&
              PARAMS_V33_SIZE == PARAMS_V32_SIZE + 4, "v36 / v35 / v34 / v33 / v32 sizes: 4 B apart");
static_assert(sizeof(Params::fizzPhys) == 4 && sizeof(Params::fizzBlick) == 4 && PARAMS_V36_FIZZ_PHYS == offsetof(Params, fizzBlick) + 4 &&
              offsetof(Params, fizzSource) == PARAMS_V36_FIZZ_PHYS + 4, "v35 layout = v36 without fizzPhys");
static_assert(sizeof(Params::edgeShadeEndWidth) == 4 && PARAMS_V35_END_WIDTH == PARAMS_V34_EDGE_SHADE_END + 4 &&
              offsetof(Params, bubbleRim) == PARAMS_V35_END_WIDTH + 4, "v34 layout = v35 without edgeShadeEndWidth");
static_assert(sizeof(Params::edgeShadeEnd) == 4 && PARAMS_V34_EDGE_SHADE_END == offsetof(Params, edgeShadeFold) + 4,
              "v33 layout = v34 without edgeShadeEnd");
static_assert(sizeof(Params::viewElevation) == 4 && offsetof(Params, highlightH) == offsetof(Params, viewElevation) + 4 &&
              PARAMS_V35_END_WIDTH + 4 <= PARAMS_V33_VIEW_ELEVATION, "v32 layout = v33 without viewElevation");
static_assert(offsetof(Params, edgeShadeShape) + 4 <= PARAMS_V34_EDGE_SHADE_END, "edgeShadeShape: one offset in v31 .. v36");
static_assert(PARAMS_V33_VIEW_ELEVATION + 8 + 4 <= PARAMS_V36_FIZZ_PHYS && PARAMS_V35_END_WIDTH + 4 <= PARAMS_V36_FIZZ_PHYS,
              "the older steps' insert points (viewElevation, edgeShadeEnd, edgeShadeEndWidth) all before fizzPhys: their offsets as in v36");

// v31 -> v32 in the v32 layout: edgeShadePow's slot is edgeShadeShape's (the perceptual profile), its default.
inline void paramsV31toV32(uint8_t *b) {
  const float shape = 1.5f; const int v = 32;
  memcpy(b + offsetof(Params, edgeShadeShape), &shape, 4); memcpy(b, &v, 4);
}
// One field inserted in place (b holds sizeof(Params) bytes, the old blob's first `size`): at `at`, value x, v.
inline void paramsInsert(uint8_t *b, size_t size, size_t at, float x, int v) {
  memmove(b + at + 4, b + at, size - at);
  memcpy(b + at, &x, 4); memcpy(b, &v, 4);
}
inline void paramsV32toV33(uint8_t *b) { paramsInsert(b, PARAMS_V32_SIZE, PARAMS_V33_VIEW_ELEVATION, 0, 33); }   // viewElevation 0 (off)
inline void paramsV33toV34(uint8_t *b) { paramsInsert(b, PARAMS_V33_SIZE, PARAMS_V34_EDGE_SHADE_END, 0, 34); }   // edgeShadeEnd 0 (off)
inline void paramsV34toV35(uint8_t *b) { paramsInsert(b, PARAMS_V34_SIZE, PARAMS_V35_END_WIDTH, 1, 35); }       // edgeShadeEndWidth 1
inline void paramsV35toV36(uint8_t *b) { paramsInsert(b, PARAMS_V35_SIZE, PARAMS_V36_FIZZ_PHYS, 0, 36); }       // fizzPhys 0 (the explicit look)

// The blob, then the CRC that labels it (only after the whole blob is written: an interrupted save keeps the old label,
// so the next boot never reads the new bytes as the old layout). False (and the log says why) when either write fails.
template <class Store, class Log> bool paramsNvsSave(Store &prefs, const Params &p, Log &out, const char *what) {
  if (prefs.putBytes("cur", &p, sizeof(Params)) != sizeof(Params)) { out.print("error params: "); out.print(what); out.println(" not saved (blob write)"); return false; }
  if (prefs.putUInt("crc", PARAMS_SCHEMA_CRC) != 4) { out.print("error params: "); out.print(what); out.println(" not saved (crc write)"); return false; }
  return true;
}

// The blob size of schema v (31 .. PARAMS_V), 0 for any other.
constexpr size_t paramsSizeOf(int v) {
  return v == 31 || v == 32 ? PARAMS_V32_SIZE : v == 33 ? PARAMS_V33_SIZE : v == 34 ? PARAMS_V34_SIZE : v == 35 ? PARAMS_V35_SIZE
       : v == PARAMS_V ? sizeof(Params) : 0;
}

// Boot: params from NVS when the blob is whole and its schema known (this one, or v35 / v34 / v33 / v32 / v31 migrated
// and saved at once: the next edit would otherwise overwrite the old look with the defaults). Read into a copy
// (sizeof(Params) of the boot stack): a short read or an unknown schema leaves params as they are and NVS untouched.
// A migration's save interrupted between the blob and its label (power lost, a failed CRC write) leaves the migrating
// firmware's blob under the old CRC: v36's (736 B, v 36) or, from the v35 / v34 / v33 firmware, a v35 (732 B, v 35), v34
// (728 B, v 34) or v33 (724 B, v 33) blob. A blob under a known CRC whose size is a newer layout's (sizes 724 .. 736 are
// one schema each, and a blob the firmware saved normally always has its own CRC's size) and whose v is that layout's
// (the migrations set v; a mismatch: dropped) is that layout's: migrated on from there and saved, or (v36) relabelled.
// Not told apart: a v32 blob (720 B, v32's interrupted v31 -> v32) under the v31 CRC is read as v31, so edgeShadeShape
// takes 1.5 again (the rest kept).
template <class Store, class Log> bool paramsNvsLoad(Store &prefs, Params &params, Log &out) {
  const uint32_t crc = prefs.getUInt("crc", 0);
  const size_t len = prefs.getBytesLength("cur");
  Params tmp; uint8_t *const b = (uint8_t *)&tmp;
  const int from = crc == PARAMS_SCHEMA_CRC_V31 ? 31 : crc == PARAMS_SCHEMA_CRC_V32 ? 32 : crc == PARAMS_SCHEMA_CRC_V33 ? 33
                 : crc == PARAMS_SCHEMA_CRC_V34 ? 34 : crc == PARAMS_SCHEMA_CRC_V35 ? 35 : crc == PARAMS_SCHEMA_CRC ? PARAMS_V : 0;
  int at = 0;   // the layout the blob holds: its CRC's, or a newer one an interrupted migration's save left under it
  if (from && len == paramsSizeOf(from)) at = from;
  else if (from) for (int k = from + 1; k <= PARAMS_V; k++) if (len == paramsSizeOf(k) && k >= 33) { at = k; break; }
  if (!at) {
    if (crc || len) {   // dropped: one line, what was found against what this firmware reads (256 B of the boot stack)
      char ver[16];
      if (from) snprintf(ver, sizeof ver, "v%d", from); else snprintf(ver, sizeof ver, "unknown");
      char m[256];
      snprintf(m, sizeof m, "params: nvs blob dropped: schema %s (crc %08x, %u B), expected v36 (crc %08x, %u B), v35 (%u B), v34 (%u B), v33 (%u B) or v32 / v31 (%u B); defaults, replaced on the next save",
               ver, (unsigned)crc, (unsigned)len, (unsigned)PARAMS_SCHEMA_CRC, (unsigned)sizeof(Params), (unsigned)PARAMS_V35_SIZE,
               (unsigned)PARAMS_V34_SIZE, (unsigned)PARAMS_V33_SIZE, (unsigned)PARAMS_V32_SIZE);
      out.println(m);
    }
    return false;
  }
  if (prefs.getBytes("cur", b, len) != len) {
    if (at == PARAMS_V) out.println("error params: nvs blob unreadable, defaults (nvs kept)");
    else { char m[64]; snprintf(m, sizeof m, "error params: v%d blob unreadable, defaults (nvs kept)", at); out.println(m); }
    return false;
  }
  char m[160];
  if (at != from && tmp.v != at) {
    snprintf(m, sizeof m, "params: nvs blob dropped: a v%d-sized blob under the v%d crc, not v %d; defaults, replaced on the next save", at, from, at);
    out.println(m); return false;
  }
  if (at == PARAMS_V) {
    params = tmp;
    if (from == PARAMS_V) { out.println("params: restored from nvs"); return true; }
    if (prefs.putUInt("crc", PARAMS_SCHEMA_CRC) != 4) out.println("error params: interrupted v36 save: crc not relabelled (crc write)");
    else out.println("params: restored from nvs (an interrupted v36 save: crc relabelled)");
    return true;
  }
  char what[16]; snprintf(what, sizeof what, "v%d -> v36", at);
  if (at == 31) paramsV31toV32(b);
  if (at <= 32) paramsV32toV33(b);
  if (at <= 33) paramsV33toV34(b);
  if (at <= 34) paramsV34toV35(b);
  paramsV35toV36(b);
  params = tmp;
  if (paramsNvsSave(prefs, params, out, what)) {
    static const char *const added[] = {"edgeShadeShape 1.5, viewElevation 0, edgeShadeEnd 0, edgeShadeEndWidth 1, fizzPhys 0",
                                        "viewElevation 0, edgeShadeEnd 0, edgeShadeEndWidth 1, fizzPhys 0",
                                        "edgeShadeEnd 0, edgeShadeEndWidth 1, fizzPhys 0", "edgeShadeEndWidth 1, fizzPhys 0", "fizzPhys 0"};
    if (at == from) snprintf(m, sizeof m, "params: restored from nvs (%s: %s)", what, added[at - 31]);
    else snprintf(m, sizeof m, "params: restored from nvs (%s: %s; an interrupted v%d save under the v%d crc)", what, added[at - 31], at, from);
    out.println(m);
  }
  return true;
}
