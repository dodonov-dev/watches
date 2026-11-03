// Port of sim/src/render.ts. Draws the two tube strips into a 536x240 RGB565 framebuffer whose
// pixels are stored BYTE-SWAPPED (panel is big-endian; see PsramCanvas in main.cpp).
#pragma once
#include <stdint.h>
#include "gen/params_gen.h"
#include "physics.h"

// Fizz animation state (sim: stepFizz), call at PHYS_HZ; each tube on its own params (pH hours, pM minutes: boardParams
// at its px scale).
void stepFizz(const Params &pH, const Params &pM, float dt, float along = 0, float across = 0, float agitation = 0);
// One tube's share of stepFizz (idx 0 hours, 1 minutes): the tubes are independent, so they may step at once on two cores.
void stepFizzTube(int idx, const Params &p, float dt, float along, float across, float agitation);
// Largest fizz count requested past the fixed pool since boot (0 = everything fitted); main reports it.
int fizzOverflow();
// Bytes the fizz size params asked of the mask pool past its boot-time size (0: they fit); bubbles then draw analytically.
int fizzMaskOverflow();
// Before rendering both tubes at once (main renderBoth): builds the fizz masks for these params (each tube's) on this
// core, so neither tube builds them while the other draws. Sequential callers may skip it.
void render_fizz_prepare(const Params &pH, const Params &pM);
// Live bubbles of tube idx; foam = how many of them are parked foam, slots = pool slots the per-step loops run over.
int fizzCounts(int idx, int &foam, int &slots);
// Tube geometry from one tube's params, clamped to the panel and the strip buffer (H: that tube's rows; sim: tubeLayout).
struct TubeLayout { int H, yH, yM; };
TubeLayout tubeLayout(const Params &p);
// Both tubes on the face, each from its own params: hours rows / top from pH, minutes from pM (sim: faceLayout).
struct FaceLayout {
  int Hh, Hm, yH, yM;
  bool operator!=(const FaceLayout &o) const { return Hh != o.Hh || Hm != o.Hm || yH != o.yH || yM != o.yM; }
};
inline FaceLayout faceLayout(const Params &pH, const Params &pM) {
  const TubeLayout h = tubeLayout(pH), m = &pM == &pH ? h : tubeLayout(pM);
  return {h.H, m.H, h.yH, m.yM};
}
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
// The whole-px shift the sprite digits of tube idx were last drawn at (render.cpp Labels::holdWhole: held across
// frames), for the `x` dump: the sim renders a dumped state at the same shift (sim setDigitHold).
void render_digit_shift(int idx, int &dx, int &dy);
// Start of a deterministic sequence (seq.h, the `X` command): no bubbles, spring clocks at 0, digit shifts not held,
// the fizz draws reseeded. false: this build draws from esp_random (AMOLED), the fizz is not reproducible.
bool render_seq_reset(uint32_t seed);
#ifdef DIGIT_PROF
// Last frame's digit-path counters of one tube (build with -DDIGIT_PROF): glyphs, rows, int px plain,
// int px liquid, frac px plain, frac px liquid, slow (band) px, runs.
const uint32_t *render_profile(int idx);
const uint32_t *render_profile_cycles(int idx);   // CPU cycles of the last frame: plain runs, band runs, ramp columns
#endif
#ifdef TUBE_PROF
// -DTUBE_PROF: drawTube stage cycles of one tube accumulated since the last reset (TU_* order in render.cpp; 240 MHz).
const uint32_t *render_tube_profile(int idx);
void render_tube_profile_reset();
#endif
#ifdef TUBE_VERIFY
void render_tube_verify(int k, uint32_t &n, uint32_t &bad);   // -DTUBE_VERIFY (LCD): k 0 residue zone px, 1 palette entries, since boot
#endif
#ifdef TILE_VERIFY
void render_tile_verify(uint32_t &px, uint32_t &bad);   // -DTILE_VERIFY (LCD tiles): the whole tiled render vs the strip path, px since boot
#endif
#ifdef TICK_PROF
// -DTICK_PROF: tick counters of one tube accumulated since the last reset (TP_* order in render.cpp; cycles at 240 MHz).
const uint32_t *render_tick_profile(int idx);
void render_tick_profile_reset();
#endif
#ifdef DIGIT_VERIFY
void render_digit_verify(uint32_t &px, uint32_t &bad);   // -DDIGIT_VERIFY (LCD): SIMD digit blends checked, since boot
#endif
#ifdef FIZZ_PROF
// -DFIZZ_PROF fizz counters (main prints them in `f`, per frame / per step; cycles at 240 MHz), accumulated until
// render_fizz_profile_reset. Render, per tube: frames; cycles of step 5, per-bubble setup, per-row prep, discRow calls
// (FIZZ_PROF=3: the same row redrawn at once, a cache probe that changes the pixels); bubbles drawn, disc rows.
// FIZZ_PROF=2 adds per-pixel classes (and slows the kernel): visited, jumped by the core skip, outside (d2 >= out2),
// cov 0, veiled, core visited, core written, core-margin sqrtf, pinpoint (g > 0), ring written, of those solid
// (cov >= 1, no pinpoint), off the panel, AA ring (sqrtApprox).
enum { FZ_FRAMES, FZ_CYC, FZ_CYC_SETUP, FZ_CYC_ROWPREP, FZ_CYC_DISC, FZ_CYC_REDRAW, FZ_BUBBLES, FZ_ROWS,
       FZ_PX_VISIT, FZ_PX_SKIP, FZ_PX_OUT, FZ_PX_COV0, FZ_PX_VEIL, FZ_PX_CORE, FZ_PX_COREW, FZ_PX_SQRT, FZ_PX_BLICK,
       FZ_PX_RING, FZ_PX_SOLID, FZ_PX_OFF, FZ_PX_AA, FZ_N };
const uint32_t *render_fizz_profile(int idx);
// stepFizz (both tubes, core 1): steps; cycles of all, inside frand (esp_random) and its calls, the spring point,
// the per-bubble loop, inside discFit (calls, rows), inside touchesFoam (calls, slots scanned), the merge scans, the
// spring cadence, settleFoam; live bubbles stepped, of those held by the glass, slots walked.
enum { FS_STEPS, FS_CYC, FS_CYC_RAND, FS_RANDS, FS_CYC_SPRINGPT, FS_CYC_LOOP, FS_CYC_FIT, FS_FITS, FS_FIT_ROWS,
       FS_CYC_TOUCH, FS_TOUCHES, FS_TOUCH_SCAN, FS_CYC_MERGE, FS_CYC_CADENCE, FS_CYC_SETTLE, FS_LIVE, FS_HELD, FS_SLOTS, FS_N };
const uint32_t *render_fizz_step_profile();
void render_fizz_profile_reset();
#endif
