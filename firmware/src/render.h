// Port of sim/src/render.ts. Draws the two tube strips into a 536x240 RGB565 framebuffer whose
// pixels are stored BYTE-SWAPPED (panel is big-endian; see PsramCanvas in main.cpp).
#pragma once
#include <stdint.h>
#include "gen/params_gen.h"
#include "physics.h"

// Fizz animation state (sim: stepFizz), call at PHYS_HZ.
void stepFizz(const Params &p, float dt, float along = 0, float across = 0, float agitation = 0);
// Largest fizz count requested past the fixed pool since boot (0 = everything fitted); main reports it.
int fizzOverflow();
// Live bubbles of tube idx; foam = how many of them are parked foam, slots = pool slots the per-step loops run over.
int fizzCounts(int idx, int &foam, int &slots);
// Tube geometry from params, clamped to the panel and the strip buffer (sim: tubeLayout).
struct TubeLayout { int H, yH, yM; bool operator!=(const TubeLayout &o) const { return H != o.H || yH != o.yH || yM != o.yM; } };
TubeLayout tubeLayout(const Params &p);
// Draw one tube (0 = hours, 1 = minutes) into `strip`: H x PANEL_W RGB565, byte-swapped,
// representing panel rows yH.. / yM.. . Everything else on the panel stays as is.
// Allocates the fixed render pools (once, at boot). False = PSRAM allocation failed.
bool render_init();
// gen: params generation counter (bumped by main on every param write / preset load / NVS restore);
// all param-only tables inside the renderer are keyed on it.
// lensRows (optional): when nothing is drawn after the whole-tube lens (no front-printed digits), the lens is not
// applied to the strip; *lensRows gets its row map instead (strip row r shows row lensRows[r], H entries, valid until
// the next render of this tube; nullptr = no lens), for a push that remaps rows anyway (display_lcd316.cpp).
void renderTube(int idx, const TubeState &s, const Params &p, uint32_t gen, uint16_t *strip, const int16_t **lensRows = nullptr);
#ifdef DIGIT_PROF
// Last frame's digit-path counters of one tube (build with -DDIGIT_PROF): glyphs, rows, int px plain,
// int px liquid, frac px plain, frac px liquid, slow (band) px, runs.
const uint32_t *render_profile(int idx);
const uint32_t *render_profile_cycles(int idx);   // CPU cycles of the last frame: plain runs, band runs, ramp columns
#endif
