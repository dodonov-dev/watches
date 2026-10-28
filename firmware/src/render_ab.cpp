// A/B resolution face (LCD only, build flag -DAB_COMPARE=<rows>, e.g. 256): the renderer and the physics compiled a
// second time, into namespace ab, for a canvas of AB_COMPARE rows (spec/layout.h RENDER_H) — their own canvas, px
// scale, constants, tube contexts and pools. main.cpp shows the minutes tube twice: the native renderer in the top slot,
// this one in the bottom slot (upscaled in the push), both on the same clock and tilt. Hours are not shown.
// Empty in every other build.
#if defined(AB_COMPARE) && defined(BOARD_LCD316)
#include <climits>
#include <math.h>
#include <string.h>
#include <stdlib.h>
#include <esp_heap_caps.h>
#include <esp_random.h>
#include "gen/params_gen.h"
#include "gen/sprites_gen.h"
#undef RENDER_H
#define RENDER_H AB_COMPARE   // read by layout.h, first included below, inside the namespace
namespace ab {
#define clampf physics_clampf   // file-local helpers of both files, now in one translation unit
#include "physics.cpp"
#undef clampf
#include "render.cpp"
}
#include "render_ab.h"

namespace abcmp {
static ab::TubeState tube;          // the comparison minutes tube
static Params eff;                  // the design params scaled to this canvas
static uint32_t effGen = 0;
static void scaled(const Params &design, uint32_t gen) { if (gen != effGen) { ab::boardParams(design, eff); effGen = gen; } }

bool init() {
  if (!ab::render_init() || !ab::physics_init()) return false;
  tube.trace = ab::traceBuf(1); tube.traceWet = ab::traceWetBuf(1);
  return true;
}
int width() { return PANEL_W; }
int height() { return PANEL_H; }
void layout(const Params &design, uint32_t gen, int &H, int &y) { scaled(design, gen); const ab::TubeLayout l = ab::tubeLayout(eff); H = l.H; y = l.yM; }
void step(float along, float across, float gyroAlong, float gyroAcross, float fillTarget, const Params &design, uint32_t gen, float dt) {
  scaled(design, gen);
  const ab::TiltInput t = {along, across, gyroAlong, gyroAcross};
  tube.fillTarget = fillTarget;   // the native minutes tube's shown fill (a share, the same on every canvas)
  ab::stepTube(tube, t, eff, dt);
  ab::stepFizz(eff, dt, along, across, tube.agitation);
}
void render(uint16_t *strip, const Params &design, uint32_t gen, const int16_t **lensRows) {
  scaled(design, gen);
  ab::renderTube(1, tube, eff, gen, strip, lensRows);
}
}
#endif
