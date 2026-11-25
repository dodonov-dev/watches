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

// Boot: params from NVS when the blob is whole and its schema known (this one, or v35 / v34 / v33 / v32 / v31 migrated
// and saved at once: the next edit would otherwise overwrite the old look with the defaults). Read into a copy
// (sizeof(Params) of the boot stack): a short read or an unknown schema leaves params as they are and NVS untouched. A
// migration's save interrupted between the blob and its label (power lost, a failed CRC write) leaves a v36 blob under
// the old CRC: whole (sizeof(Params): no older layout has that size) and v 36, it is this schema's, loaded and
// relabelled at once.
template <class Store, class Log> bool paramsNvsLoad(Store &prefs, Params &params, Log &out) {
  const uint32_t crc = prefs.getUInt("crc", 0);
  const size_t len = prefs.getBytesLength("cur");
  Params tmp; uint8_t *const b = (uint8_t *)&tmp;
  const int from = crc == PARAMS_SCHEMA_CRC_V31 ? 31 : crc == PARAMS_SCHEMA_CRC_V32 ? 32 : crc == PARAMS_SCHEMA_CRC_V33 ? 33
                 : crc == PARAMS_SCHEMA_CRC_V34 ? 34 : crc == PARAMS_SCHEMA_CRC_V35 ? 35 : crc == PARAMS_SCHEMA_CRC ? PARAMS_V : 0;
  if (from && len == sizeof(Params)) {
    if (prefs.getBytes("cur", b, sizeof(Params)) != sizeof(Params)) { out.println("error params: nvs blob unreadable, defaults (nvs kept)"); return false; }
    if (from != PARAMS_V) {
      if (tmp.v != PARAMS_V) { out.println("params: nvs blob dropped: a v36-sized blob under an old schema's crc, not v 36; defaults, replaced on the next save"); return false; }
      params = tmp;
      if (prefs.putUInt("crc", PARAMS_SCHEMA_CRC) != 4) out.println("error params: interrupted v36 save: crc not relabelled (crc write)");
      else out.println("params: restored from nvs (an interrupted v36 save: crc relabelled)");
      return true;
    }
    params = tmp; out.println("params: restored from nvs"); return true;
  }
  const size_t want = from == 35 ? PARAMS_V35_SIZE : from == 34 ? PARAMS_V34_SIZE : from == 33 ? PARAMS_V33_SIZE : PARAMS_V32_SIZE;
  if (!from || from == PARAMS_V || len != want) {
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
  char what[16]; snprintf(what, sizeof what, "v%d -> v36", from);
  if (prefs.getBytes("cur", b, want) != want) {
    out.print("error params: v"); out.print(from == 31 ? "31" : from == 32 ? "32" : from == 33 ? "33" : from == 34 ? "34" : "35");
    out.println(" blob unreadable, defaults (nvs kept)"); return false;
  }
  if (from == 31) paramsV31toV32(b);
  if (from <= 32) paramsV32toV33(b);
  if (from <= 33) paramsV33toV34(b);
  if (from <= 34) paramsV34toV35(b);
  paramsV35toV36(b);
  params = tmp;
  if (paramsNvsSave(prefs, params, out, what)) {
    out.print("params: restored from nvs ("); out.print(what);
    out.println(from == 31 ? ": edgeShadeShape 1.5, viewElevation 0, edgeShadeEnd 0, edgeShadeEndWidth 1, fizzPhys 0)"
                : from == 32 ? ": viewElevation 0, edgeShadeEnd 0, edgeShadeEndWidth 1, fizzPhys 0)"
                : from == 33 ? ": edgeShadeEnd 0, edgeShadeEndWidth 1, fizzPhys 0)" : from == 34 ? ": edgeShadeEndWidth 1, fizzPhys 0)" : ": fizzPhys 0)");
  }
  return true;
}
