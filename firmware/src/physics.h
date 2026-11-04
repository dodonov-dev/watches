// Port of sim/src/physics.ts — fixed-step 50 Hz liquid dynamics + IMU conditioning.
#pragma once
#include "gen/params_gen.h"
#include <math.h>
#include "layout.h"   // TUBE_LENGTH_PX (trace bounds default below), PANEL_H, DESIGN_H

#define PHYS_HZ 50
#define PHYS_DT (1.0f / PHYS_HZ)
#define PLAY_STROKE_G 0.35f      // substantial filtered gravity excursion (~20° near horizontal)
#define PLAY_REVERSAL_S 2.0f     // opposite strokes inside this window count as play
// Structural caps — params only tighten, never widen. px caps and speeds are design px: a tube's canvas px = x its px
// scale k (layout.h TUBE_PX_SCALE), the _AT(k) forms.
#define FILL_SLOSH_MAX_DESIGN_PX 30.0f   // |fillPos| cap
#define FILL_SLOSH_MAX_PX_AT(k) (FILL_SLOSH_MAX_DESIGN_PX * (k))
#define ANGLE_HARD_MAX_DEG 20.0f
#define ANGLE_VERTICAL_MAX_DEG 45.0f   // vertical watch: the surface stays level against the tilted tube
#define LIGHT_MAX_DEG 85.0f
#define CAP_DYN_MAX_DESIGN_PX 12.0f      // |cap| cap: dynamic meniscus bulge / hollow
#define CAP_DYN_MAX_PX_AT(k) (CAP_DYN_MAX_DESIGN_PX * (k))
#define PIN_RELAX_S 3.0f          // a held contact line creeps back to the static shape (wrist micro-motion), s
#define FILM_FULL_DESIGN_PX_S 25.0f      // edge speed at which the trailing wet film is fully drawn
#define FILM_FULL_PX_S_AT(k) (FILM_FULL_DESIGN_PX_S * (k))
#define TRACE_DEPOSIT_MAX_DESIGN_PX 32.0f // max px of newly exposed glass per tick that gets a fresh deposit
#define TRACE_DEPOSIT_MAX_PX_AT(k) (TRACE_DEPOSIT_MAX_DESIGN_PX * (k))
#define TRACE_FULL 0xff00         // a film at FILM_ETA_MAX (8.8 fixed point)
#define TRACE_MIN (2 << 8)        // dry residue below this is gone (buffer empties); also the thinnest deposit
#define TRACE_DRAIN_MAX_PX_S 48.0f // cap of a film's drain speed: TRACE_DRAIN_STEPS upwind steps a tick stay stable (canvas px, a stability bound: not scaled)
#define TRACE_DRAIN_STEPS 3
#define RETRACT_S 2.0f            // a full tube empties over this long when its scale wraps (followClock), s
#define FILM_LAMBDA 9.2f          // Cox-Voinov log factor contactDyn is calibrated with (sim filmEta)
#define FILM_ETA_MAX 0.1f         // thin-film limit of the film thickness eta = h / R
#define GYRO_LP_HZ 12.0f          // smooths both gyro outputs (sensor noise twitches fizz/agitation)

struct TiltInput { float along, across, gyroAlong, gyroAcross; };

struct TubeState {
  // fillTarget: 0..1 from time, as shown (followClock): clockPrev = the clock's fill at the previous call (wrap
  // detection), retract = 0..1 through a wrap's retract (1 = none running), retractFrom = fillTarget at the wrap
  float clockPrev = 0, retract = 1, retractFrom = 0;
  float fillTarget = 0, fillPos = 0, fillVel = 0, angle = 0, angleVel = 0, light = 0, lightVel = 0, agitation = 0, edgeLight = 0, acrossTilt = 0;
  // meniscus dynamics: surface centre leading the pinned contact lines (px, panel +x); trailing wet films 0..1
  float cap = 0, capVel = 0, filmFree = 0, filmHome = 0;
  // pinned contact lines per meniscus end (free = time edge, home = free slug's home edge), each in its
  // end's outward sense: pin = px of surface-centre travel against the held wall ring (hysteresis band),
  // lineV = px/s the line is dragged at past the band, over ~0.5 s (0 while held). See sim TubeState.
  float pinFree = 0, pinHome = 0, lineVFree = 0, lineVHome = 0;
  // dried traces: residue 0..TRACE_FULL (8.8 fixed point, film thickness relative to FILM_ETA_MAX) per
  // panel-frame column where an edge receded (blood smear); its wet part traceWet (<= trace) runs down
  // under gravity and evaporates into a fading stain. trace: one of the static traceBuf()s, traceWet: a
  // PSRAM traceWetBuf() (physics_init), both assigned at boot; the render reads trace only
  uint16_t *trace = nullptr, *traceWet = nullptr;
  // occupied residue columns [traceLo, traceHi): deposits widen, decay shrinks; lo >= hi = empty
  // (physics and render skip the buffer entirely then)
  int16_t traceLo = TUBE_LENGTH_PX, traceHi = 0;
  float xtPrev = 0, xhPrev = 0;   // panel-frame edge positions at the previous tick
  bool traceInit = false;
  // free liquid: slug home-edge position (px from the left end), reading 1 = parked home showing the time
  float slugPos = 0, slugVel = 0, reading = 1;
  float playTimer = 0, playWindow = 0;
  float playAnchorAlong = 0, playAnchorAcross = 0, playDirAlong = 0, playDirAcross = 0;
  bool playInit = false;
};

// Params as a tube's physics and render take them: p (design px, as presets, `p` writes and NVS hold them) with the
// PARAM_FIELDS px fields scaled by the tube's px scale k (layout.h TUBE_PX_SCALE), the whole-pixel ones rounded, the
// liquid's (px 3: the fizz) by the liquid's scale kf (PX_SCALE_FIZZ); a tube narrower than kf holds fewer bubbles,
// fizzCount x (k / kf)^2 (its share of the volume). See sim params.ts boardParams.
inline void boardParams(const Params &p, Params &out, float k, float kf) {
  out = p;
  if (k == 1.0f && kf == 1.0f) return;
  for (const ParamField &f : PARAM_FIELDS) if (f.px) {
    float &v = *(float *)((uint8_t *)&out + f.off);
    v *= f.px == 3 ? kf : k;
    if (f.px == 2) v = floorf(v + 0.5f);   // whole pixels stay on the grid (JS Math.round)
  }
#if TUBE_COUNT == 3
  // Three tubes fit the canvas: rows past a tube's share of it are cut (layout.h TUBE3_HEIGHT_AT: a third at equal widths;
  // only a wide LCD tube at the tallest tubeHeight reaches it: 3 x 107 > 320). Physics and render read the capped height
  // alike. See sim boardParams.
  if (out.tubeHeight > TUBE3_HEIGHT_AT(k)) out.tubeHeight = TUBE3_HEIGHT_AT(k);
#endif
  if (k != kf) { const float r = k / kf, q = r * r; out.fizzCount = floorf(p.fizzCount * q + 0.5f); }
  // Scaled other than the canvas height (LCD at physical size): the tube rows keep their place in the room a tube can
  // move in (canvas rows minus its height), so the tubes stay at the face's edges.
  if (k != (float)PANEL_H / DESIGN_H) {
    const float room = DESIGN_H - p.tubeHeight, k = room > 1.0f ? (PANEL_H - out.tubeHeight) / room : 1.0f;
    out.hoursY = floorf(p.hoursY * k + 0.5f); out.minutesY = floorf(p.minutesY * k + 0.5f);
  }
}

float columnLen(float fillTarget, const Params &p);   // liquid column length, px
// Column drawn from the right end (mirrored frame). A vertical watch keeps the liquid at the bottom (left end):
// there `remaining` only flips the scale and the column length. See sim mirrored().
inline bool mirrored(const Params &p) { return p.remaining && !p.vertical; }
uint16_t *traceBuf(int i);                            // static residue buffer of tube i
bool physics_init();                                  // boot: the wet-film buffers in PSRAM (false = not allocated)
uint16_t *traceWetBuf(int i);                         // wet-film buffer of tube i (nullptr before physics_init)
// The film a line receding at `speed` px/s leaves, eta = h / R (Bretherton, capped at FILM_ETA_MAX); full = its tube's
// FILM_FULL_PX_S_AT (speed = full: the fully drawn film). See sim filmEta.
float filmEta(const Params &p, float speed, float full);

float lightRest(float along, float across, const Params &p);
// Bore radius, px in row-centre units: (H - 1)/2 less the glass wall band. See sim boreR.
float boreR(const Params &p);
// One meniscus end's wall-ring leads (px the ring leads the surface centre, R = boreR): adv / rec = at θA / θR
// (adv <= rec), rest = from the hydrostatic head (len = column px, tilt = along follower into this end)
// held within [adv, rec]; mmPerPx = the tube's (layout.h MM_PER_PX_AT). See sim contactLeads.
struct ContactLeads { float R, rest, adv, rec; };
ContactLeads contactLeads(const Params &p, float len, float tilt, float mmPerPx);
// One physics step of a tube: k = its px scale (layout.h TUBE_PX_SCALE), p = its params (boardParams at k). See sim.
void stepTube(TubeState &s, const TiltInput &in, const Params &p, float dt, float k);
// Shown fill from the clock's (0..1): a wrap (the clock falling back by over half the scale) retracts the column
// over RETRACT_S instead of emptying it in one tick; snap (the clock was set) goes straight to it. See sim followClock.
void followClock(TubeState &s, float clock, float dt = PHYS_DT, bool snap = false);

// Slow EMA of |a| used as the gravity divisor (sensor reads ~0.94 g; never divide by instantaneous |a|).
struct GravityNorm {
  float mag = 1; bool init = false;
  void reset() { init = false; }
  float update(float n);
};

// accel: two cascaded one-pole LPs; gyro: one-pole HP + deadzone + clamp.
struct ImuFilter {
  float lpAlong = 0, lpAcross = 0, lpAlong2 = 0, lpAcross2 = 0, hpPrevIn = 0, hpPrevOut = 0, lpGyroAcross = 0, lpGyroAlong = 0;
  bool init = false;
  void reset() { init = false; hpPrevIn = hpPrevOut = lpGyroAcross = lpGyroAlong = 0; }
  TiltInput step(const TiltInput &raw, const Params &p, float dt = PHYS_DT);
};
