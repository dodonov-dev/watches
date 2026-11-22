#pragma once
// The params' NVS blob (namespace lw: "cur" = Params, "crc" = its schema CRC): the boot load with the migrations from
// older schemas, and the save. Templates over the store (Preferences) and the log (Print), so the host test
// (tools/test_params_nvs.py) runs these very functions against a mock store.
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include "gen/params_gen.h"

// Legacy layouts still read. v31 (edgeShadePow) and v32 (edgeShadeShape in that slot) are one layout: v33 without
// viewElevation (4 B after `vertical`; every later field 4 B lower). The host test checks this against v31's and v32's
// own params_gen.h, field by field.
#define PARAMS_SCHEMA_CRC_V31 0x6bb6cdafu
#define PARAMS_SCHEMA_CRC_V32 0xcd2763c1u
constexpr size_t PARAMS_V32_SIZE = 720;
constexpr size_t PARAMS_V33_VIEW_ELEVATION = offsetof(Params, viewElevation);
static_assert(PARAMS_SCHEMA_CRC == 0x970ee607u, "params schema changed: add the migration from v33 (params_nvs.h paramsNvsLoad)");
static_assert(offsetof(Params, v) == 0 && sizeof(Params::v) == 4, "v first: the migrations set it");
static_assert(sizeof(Params) == PARAMS_V32_SIZE + 4 && sizeof(Params::viewElevation) == 4 &&
              offsetof(Params, highlightH) == PARAMS_V33_VIEW_ELEVATION + 4, "v32 layout = v33 without viewElevation");
static_assert(offsetof(Params, edgeShadeShape) + 4 <= PARAMS_V33_VIEW_ELEVATION, "edgeShadeShape: one offset in v31 / v32 / v33");

// v31 -> v32 in the v32 layout: edgeShadePow's slot is edgeShadeShape's (the perceptual profile), its default.
inline void paramsV31toV32(uint8_t *b) {
  const float shape = 1.5f; const int v = 32;
  memcpy(b + offsetof(Params, edgeShadeShape), &shape, 4); memcpy(b, &v, 4);
}
// v32 -> v33 in place (b holds sizeof(Params) bytes, the v32 blob's first PARAMS_V32_SIZE): viewElevation 0 (off).
inline void paramsV32toV33(uint8_t *b) {
  memmove(b + PARAMS_V33_VIEW_ELEVATION + 4, b + PARAMS_V33_VIEW_ELEVATION, PARAMS_V32_SIZE - PARAMS_V33_VIEW_ELEVATION);
  const float off = 0; const int v = 33;
  memcpy(b + PARAMS_V33_VIEW_ELEVATION, &off, 4); memcpy(b, &v, 4);
}

// The blob, then the CRC that labels it (only after the whole blob is written: an interrupted save keeps the old label,
// so the next boot never reads the new bytes as the old layout). False (and the log says why) when either write fails.
template <class Store, class Log> bool paramsNvsSave(Store &prefs, const Params &p, Log &out, const char *what) {
  if (prefs.putBytes("cur", &p, sizeof(Params)) != sizeof(Params)) { out.print("error params: "); out.print(what); out.println(" not saved (blob write)"); return false; }
  if (prefs.putUInt("crc", PARAMS_SCHEMA_CRC) != 4) { out.print("error params: "); out.print(what); out.println(" not saved (crc write)"); return false; }
  return true;
}

// Boot: params from NVS when the blob is whole and its schema known (this one, or v31 / v32 migrated and saved at once:
// the next edit would otherwise overwrite the old look with the defaults). Read into a copy (sizeof(Params) of the boot
// stack): a short read or an unknown schema leaves params as they are and NVS untouched.
template <class Store, class Log> bool paramsNvsLoad(Store &prefs, Params &params, Log &out) {
  const uint32_t crc = prefs.getUInt("crc", 0);
  const size_t len = prefs.getBytesLength("cur");
  Params tmp; uint8_t *const b = (uint8_t *)&tmp;
  if (crc == PARAMS_SCHEMA_CRC && len == sizeof(Params)) {
    if (prefs.getBytes("cur", b, sizeof(Params)) != sizeof(Params)) { out.println("error params: nvs blob unreadable, defaults (nvs kept)"); return false; }
    params = tmp; out.println("params: restored from nvs"); return true;
  }
  const bool v31 = crc == PARAMS_SCHEMA_CRC_V31;
  if (!(v31 || crc == PARAMS_SCHEMA_CRC_V32) || len != PARAMS_V32_SIZE) {
    if (crc || len) {   // dropped: one line, what was found against what this firmware reads (192 B of the boot stack)
      const char *const ver = v31 ? "v31" : crc == PARAMS_SCHEMA_CRC_V32 ? "v32" : crc == PARAMS_SCHEMA_CRC ? "v33" : "unknown";
      char m[192];
      snprintf(m, sizeof m, "params: nvs blob dropped: schema %s (crc %08x, %u B), expected v33 (crc %08x, %u B) or v32 / v31 (%u B); defaults, replaced on the next save",
               ver, (unsigned)crc, (unsigned)len, (unsigned)PARAMS_SCHEMA_CRC, (unsigned)sizeof(Params), (unsigned)PARAMS_V32_SIZE);
      out.println(m);
    }
    return false;
  }
  const char *const what = v31 ? "v31 -> v33" : "v32 -> v33";
  if (prefs.getBytes("cur", b, PARAMS_V32_SIZE) != PARAMS_V32_SIZE) {
    out.print("error params: "); out.print(v31 ? "v31" : "v32"); out.println(" blob unreadable, defaults (nvs kept)"); return false;
  }
  if (v31) paramsV31toV32(b);
  paramsV32toV33(b);
  params = tmp;
  if (paramsNvsSave(prefs, params, out, what)) {
    out.print("params: restored from nvs ("); out.print(what); out.println(v31 ? ": edgeShadeShape 1.5, viewElevation 0)" : ": viewElevation 0)");
  }
  return true;
}
