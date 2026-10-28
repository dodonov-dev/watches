// A/B resolution face (render_ab.cpp, build flag -DAB_COMPARE=<rows>, LCD only): a second renderer + physics for a
// canvas of AB_COMPARE rows, showing the minutes tube next to the native one. `design` = params in design px.
#pragma once
#include <stdint.h>
#include "gen/params_gen.h"

namespace abcmp {
bool init();                                     // boot: its pools and residue buffers (false = PSRAM alloc failed)
int width();                                     // its canvas, PANEL_W x PANEL_H of AB_COMPARE rows
int height();
void layout(const Params &design, uint32_t gen, int &H, int &y);   // its minutes tube: rows, top canvas row
// one physics step; the filtered tilt (TiltInput fields, g / dps) as floats: physics.h is this file's namespace's own
void step(float along, float across, float gyroAlong, float gyroAcross, float fillTarget, const Params &design, uint32_t gen, float dt);
void render(uint16_t *strip, const Params &design, uint32_t gen, const int16_t **lensRows);       // strip stride = width()
}
