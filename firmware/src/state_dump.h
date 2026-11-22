#pragma once
// One tube's fields of the `x` dump's STATE line (main.cpp), in tools/compare-device.py STATE_KEYS order: the drawn
// state the sim's render-ref replays. New fields go at the end only: an older record lacks them and the replay leaves
// them at newTube()'s values (backTilt 0). Shared with the host round-trip test (tools/test_compare_device.py).
#include <cstdio>
#include "physics.h"

inline int formatTubeState(char *o, size_t n, const TubeState &t) {
  return snprintf(o, n, " %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %d %d %d %d %.6f",
                  t.fillTarget, t.fillPos, t.angle, t.light, t.edgeLight, t.agitation,
                  t.acrossTilt, t.cap, t.filmFree, t.filmHome, t.slugPos, t.reading, t.pinFree, t.pinHome,
                  t.lineVFree, t.lineVHome, t.rearX16, t.rearY16, t.rearX16w, t.rearY16w,   // the rear parallax as rendered (1/16 px)
                  t.backTilt);   // desk view: the lid's tau (rad)
}
