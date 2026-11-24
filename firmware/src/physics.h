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
// rear parallax gate (sim physics.ts REAR_*): rate smoothing s, activity attack /s and decay s, gate g/s (HI also latches
// it shut), quiet s that releases the latch, ease s
#define REAR_RATE_S 0.1f
#define REAR_ACT_ATTACK 20.0f
#define REAR_ACT_DECAY_S 1.0f
#define REAR_GATE_LO 0.5f
#define REAR_GATE_HI 1.0f
#define REAR_QUIET_S 1.0f
#define REAR_EASE_S 0.15f
#define ANGLE_VERTICAL_MAX_DEG 45.0f   // vertical watch: the surface stays level against the tilted tube
#define LIGHT_MAX_DEG 85.0f
// What the render reads of the physics (perf-cheap A): the light angle and the edge skew, each held by quantHyst. In
// motion it follows the spring's value whenever that leaves +-*_Q_HYST steps of *_Q around it (to the nearest step of
// the *_Q grid inside the band, one step at a time on a slow tilt) and walks onto the limit while the spring rests on
// it; a slow change is followed while the value's mean (a QUANT_MEAN_S running average) sits more than half the band
// away (a step at a time). Once nothing of that has moved it for QUANT_SETTLE steps and the spring passes its mean (it
// has caught up) it walks to the mean in eighth steps and then holds exactly that mean; it settles again (eighth steps)
// only when the spring's envelope (its peaks, relaxing toward the mean over QUANT_ENV_S) leaves it.
// At rest the render then sees one value from inside the spring's own recent range: neither the palette (its key is the
// light) nor the edge's tiles change, and the image is one the noisy spring showed, its discrete parts included (the
// highlight band's row, highlightTop of the light; the wet share of the edge rows). Steps: LIGHT_Q_DEG, any palette row
// moves at most 1 RGB565 LSB a step (STATUS.md, perf-cheap A); ANGLE_Q_DEG, an edge row at most 1/16 px at the tallest
// 8 mm tube. The bands span about twice the board's noise at rest. The stand's back tilt is not held (the lid's end
// factor makes it too sensitive near the end glass; STATUS). heldReseat puts both on their springs under new params
// (main paramsChanged). Every value these thresholds see is computed with + - * / and sqrtf only, in a fixed order
// (pAtan2, pExpNeg below for the library calls): the sim (physics.ts, float32) gets the same bits.
#define LIGHT_Q_DEG 0.125f
#define LIGHT_Q_HYST 3.0f
#define ANGLE_Q_DEG 0.03125f
#define ANGLE_Q_HYST 8.0f
#define QUANT_MEAN_S 1.0f
#define QUANT_ENV_S 1.0f   // s, the envelope's relaxation toward the mean: the spring's peaks over ~1 s
#define QUANT_SETTLE 100   // physics steps without a move before the walk to the mean (2 s: the mean has converged)
#pragma GCC push_options
#pragma GCC optimize("fp-contract=off")   // no fused multiply-add in what the thresholds see (the sim rounds every step)
// Parity arithmetic: float32, + - * / and sqrtf only, a fixed order, the constants as float32 values (9 digits): the sim's
// pAtan2 / pExpNeg give the same bits.
// atan of x >= 0 (Cephes atanf: reduction by tan(3 pi / 8) and tan(pi / 8), a degree-9 odd polynomial, ~1e-7).
inline float pAtanPos(float x) {
  float y = 0, t = x;
  if (x > 2.41421366f) { y = 1.57079637f; t = -1.0f / x; }
  else if (x > 0.414213568f) { y = 0.785398185f; t = (x - 1.0f) / (x + 1.0f); }
  const float z = t * t;
  return y + (((((0.0805374458f * z - 0.138776854f) * z + 0.199777111f) * z - 0.333329499f) * z) * t + t);
}
inline float pAtan2(float y, float x) {
  const float ax = fabsf(x), ay = fabsf(y);
  if (ax == 0 && ay == 0) return 0;
  float r = ax >= ay ? pAtanPos(ay / ax) : 1.57079637f - pAtanPos(ax / ay);
  if (x < 0) r = 3.14159274f - r;
  return y < 0 ? -r : r;
}
// e^-x, x >= 0 (a filter coefficient): (e^(-x / 16))^16, the inner one by its Taylor series to x^7.
inline float pExpNeg(float x) {
  const float t = x * 0.0625f;
  float e = ((((((-0.000198412701f * t + 0.00138888892f) * t - 0.00833333377f) * t + 0.0416666679f) * t - 0.166666672f) * t + 0.5f) * t - 1.0f) * t + 1.0f;
  for (int k = 0; k < 4; k++) e = e * e;
  return e;
}
// One physics step of a held value: v = its spring, mean = v's running average and lo / hi = its recent envelope (both
// updated here, dt), quiet = steps since the hold last moved (QUANT_SETTLE + 1: settled), held = the current value inside
// +-lim, lim = the spring's limit; returned: the new held value. See sim quantHyst.
inline float quantHyst(float v, float &mean, float &lo, float &hi, int16_t &quiet, float held, float q, float h, float lim, float dt) {
  const float k = fminf(1, dt / QUANT_MEAN_S), ke = fminf(1, dt / QUANT_ENV_S);
  mean += (v - mean) * k;
  hi = fmaxf(v, hi + (mean - hi) * ke); lo = fminf(v, lo + (mean - lo) * ke);   // the envelope: the spring's peaks, relaxing
  const float u = v / q, i = held / q, m = mean / q, top = fmaxf(0, lim) / q;   // top: the limit itself
  float r = i; bool moved = true;
  if (u - i > h) r = ceilf(u - h);
  else if (i - u > h) r = floorf(u + h);
  else if (v >= lim && i < top) r = i + 1;     // the spring rests on its limit: walk onto it, a step at a time
  else if (v <= -lim && i > -top) r = i - 1;
  else if (m - i > 0.5f * h && u > i) r = i + 1;   // a slow change: toward the mean, a step at a time
  else if (i - m > 0.5f * h && u < i) r = i - 1;
  else {
    moved = false;
    // settled, but the spring's envelope has left it (its mean drifted): settle again
    if (quiet > QUANT_SETTLE && (i > hi / q || i < lo / q)) quiet = QUANT_SETTLE;
    if (quiet < QUANT_SETTLE) quiet++;
    else if (quiet == QUANT_SETTLE && fabsf(m - u) <= 0.125f) {   // quiet long enough, the spring passing its mean
      // (the mean caught up): to the mean in eighth steps, then exactly on it, settled
      if (m - i > 0.125f) r = i + 0.125f;
      else if (i - m > 0.125f) r = i - 0.125f;
      else { r = m; quiet = QUANT_SETTLE + 1; }
    }
  }
  if (moved) quiet = 0;
  return (r > top ? top : r < -top ? -top : r) * q;
}
#pragma GCC pop_options
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

// normal (g): the measured out-of-plane component, + = face up (IMU +Z out of the screen, layout.h IMU_AXIS_NORMAL);
// signed, never reconstructed from along / across. Last so the {along, across, gyroAlong, gyroAcross} initialisers
// keep their meaning (normal 0 there: no information). stepTube does not read it. See sim TiltInput.
struct TiltInput { float along, across, gyroAlong, gyroAcross, normal; };

// Physical pose: the unit buoyancy direction b = normalize(-along, -across, +normal) in tube coordinates (x along the
// tube toward its top, y across, z toward the viewer; docs/tilted-fizz-plan.md), from the filtered gravity without
// inputGain. updatePose leaves it as it was (the last valid one) and returns false below POSE_MIN_G g or non-finite.
struct Pose { float x, y, z; };
#define POSE_MIN_G 0.3f
#define POSE_DEFAULT Pose{0, 0, 1}   // before any valid sample: face up (the legacy zero along / across: flat)
bool updatePose(Pose &pose, float along, float across, float normal);
// Desk view: the stand's back tilt tau = atan2(z, x) of the pose (the top end leaning away from the viewer), rad,
// signed: < 0 tipped forward (the screen toward the viewer); clamped to +-BACK_TILT_MAX_DEG (face up / down, turned over:
// the caps). See sim poseBackTilt.
#define BACK_TILT_MAX_DEG 45.0f
float poseBackTilt(const Pose &pose);

struct TubeState {
  // fillTarget: 0..1 from time, as shown (followClock): clockPrev = the clock's fill at the previous call (wrap
  // detection), retract = 0..1 through a wrap's retract (1 = none running), retractFrom = fillTarget at the wrap
  float clockPrev = 0, retract = 1, retractFrom = 0;
  // angle / light: what the render reads, held by quantHyst (ANGLE_Q_*, LIGHT_Q_*) from the springs' angleRaw / lightRaw
  float fillTarget = 0, fillPos = 0, fillVel = 0, angle = 0, angleVel = 0, light = 0, lightVel = 0, agitation = 0, edgeLight = 0, acrossTilt = 0;
  float angleRaw = 0, lightRaw = 0, angleMean = 0, lightMean = 0;   // the springs; quantHyst's running means
  float angleLo = 0, angleHi = 0, lightLo = 0, lightHi = 0;         // quantHyst's envelopes of the springs
  int16_t angleQuiet = 0, lightQuiet = 0;                           // quantHyst's steps since a move
  // rear (view-angle) parallax (sim TubeState): the tilt low-passed over rearParallaxSettle; the shift quantised once
  // here, 1/16 px, behind air (X16 / Y16) and behind liquid (w: / liquidIor), panel x / rows down. The render and the
  // `x` dump take these integers.
  float rearLpAlong = 0, rearLpAcross = 0;
  float rearSmAlong = 0, rearSmAcross = 0, rearAct = 0, rearSx = 0, rearSy = 0;   // the gate (sim TubeState, physics.cpp REAR_*)
  float rearQuiet = 0;   // with rearLatch (below): latched shut by a swing, until REAR_QUIET_S of quiet
  int rearX16 = 0, rearY16 = 0, rearX16w = 0, rearY16w = 0;
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
  float xtPrev = 0, xhPrev = 0;   // panel-frame edge positions at the previous tick (traceInit: primed, below)
  // free liquid: slug home-edge position (px from the left end), reading 1 = parked home showing the time
  float slugPos = 0, slugVel = 0, reading = 1;
  float playTimer = 0, playWindow = 0;
  float playAnchorAlong = 0, playAnchorAcross = 0, playDirAlong = 0, playDirAcross = 0;
  // desk view (render only): the stand's back tilt tau, rad, from the pose (poseBackTilt; set per physics step by main,
  // 0 = upright). The render's lid height follows it with params viewElevation. See sim TubeState.backTilt.
  float backTilt = 0;
  // the flags together (no padding after each): rear gate latched, rear parallax primed, trace prev positions primed,
  // play anchor primed
  bool rearLatch = false, rearInit = false, traceInit = false, playInit = false;
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
// The held light and angle back on their springs under the params p (the tube's, as stepTube takes them): the springs
// clamped to p's limits, held at them exactly, the means at them, the settle stage to come. After a params change (it
// may move a rest or a limit), before anything renders. See sim heldReseat.
void heldReseat(TubeState &s, const Params &p);

// Slow EMA of |a| used as the gravity divisor (sensor reads ~0.94 g; never divide by instantaneous |a|).
struct GravityNorm {
  float mag = 1; bool init = false;
  void reset() { init = false; }
  float update(float n);
};

// accel: two cascaded one-pole LPs; gyro: one-pole HP + deadzone + clamp.
// pose: the physical pose of the last step (updatePose of the filtered gravity, no inputGain); kept over a reset.
struct ImuFilter {
  float lpAlong = 0, lpAcross = 0, lpAlong2 = 0, lpAcross2 = 0, hpPrevIn = 0, hpPrevOut = 0, lpGyroAcross = 0, lpGyroAlong = 0;
  float lpNormal = 0, lpNormal2 = 0;
  Pose pose = POSE_DEFAULT;
  bool poseValid = false;   // a valid sample has set pose (before it: POSE_DEFAULT, face up; the lid's tau stays 0, backTilt())
  bool init = false;
  float backTilt() const { return poseValid ? poseBackTilt(pose) : 0.0f; }   // desk view: the stand's back tilt, 0 before a valid sample
  void reset() { init = false; hpPrevIn = hpPrevOut = lpGyroAcross = lpGyroAlong = 0; }
  TiltInput step(const TiltInput &raw, const Params &p, float dt = PHYS_DT);
};
