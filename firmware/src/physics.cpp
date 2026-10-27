#include "physics.h"
#include "layout.h"
#include <esp_heap_caps.h>
#include <math.h>
#include <string.h>

static inline float clampf(float v, float lo, float hi) { return v < lo ? lo : v > hi ? hi : v; }
static inline float dz(float v, float d) { return fabsf(v) < d ? 0 : v - (v > 0 ? d : -d); }
static inline float jroundf(float x) { return floorf(x + 0.5f); }   // JS Math.round

// One static residue buffer per tube (deterministic footprint, filled by stepTube)
static uint16_t g_trace[2][TUBE_LENGTH_PX];
uint16_t *traceBuf(int i) { return g_trace[i & 1]; }
// Its wet part, allocated once at boot in PSRAM (internal RAM has no 2 KB to spare)
static uint16_t *g_traceWet[2] = {nullptr, nullptr};
bool physics_init() {
  for (int i = 0; i < 2; i++) {
    if (!g_traceWet[i]) g_traceWet[i] = (uint16_t *)heap_caps_malloc(TUBE_LENGTH_PX * sizeof(uint16_t), MALLOC_CAP_SPIRAM);
    if (!g_traceWet[i]) return false;
    memset(g_traceWet[i], 0, TUBE_LENGTH_PX * sizeof(uint16_t));
  }
  return true;
}
uint16_t *traceWetBuf(int i) { return g_traceWet[i & 1]; }

float filmEta(const Params &p, float speed) {
  const float dyn = fmaxf(0, p.contactDyn) * (3.14159265f / 180.0f);
  const float ca = dyn * dyn * dyn * (1.0f / (9 * FILM_LAMBDA)) * (speed / FILM_FULL_PX_S);
  const float c = cbrtf(ca * ca);
  return fminf(FILM_ETA_MAX, 1.34f * c / (1 + 3.35f * c));
}

// Gravity g (along the tube, panel +x) runs the wet film down the bore: flux out of a column c * w,
// c = traceDrain |g| (w / TRACE_FULL)^2 (a viscous wall film moves at rho g h^2 / 3 mu; traceDrain = that speed
// at the thin-film cap), capped at TRACE_DRAIN_MAX_PX_S. Upwind in integers, downstream column first:
// exactly conservative; the tube ends hold the film, a column full at TRACE_FULL backs it up. See sim.
static void drainTrace(TubeState &s, const Params &p, float g, float dt) {
  if (!(p.traceDrain > 0) || g == 0 || s.traceHi <= s.traceLo) return;
  const float k = p.traceDrain * fabsf(g) * (1.0f / ((float)TRACE_FULL * TRACE_FULL)), dts = dt / TRACE_DRAIN_STEPS;
  uint16_t *w = s.traceWet, *t = s.trace;
  // per column per substep: inline min and truncation (== floor, all non-negative), no libm calls on the S3
  auto out = [&](float v, int into) {
    float c = k * v * v;
    if (c > TRACE_DRAIN_MAX_PX_S) c = TRACE_DRAIN_MAX_PX_S;
    const int f = (int)(c * v * dts), room = TRACE_FULL - t[into];
    return f < room ? f : room;
  };
  for (int n = 0; n < TRACE_DRAIN_STEPS; n++) {
    const int lo = s.traceLo, hi = s.traceHi;
    if (g > 0) {
      for (int x = (hi < TUBE_LENGTH_PX - 1 ? hi : TUBE_LENGTH_PX - 1) - 1; x >= lo; x--) {
        const int f = w[x] ? out(w[x], x + 1) : 0;
        if (f <= 0) continue;
        w[x] -= f; t[x] -= f; w[x + 1] += f; t[x + 1] += f;
        if (x + 1 >= s.traceHi) s.traceHi = (int16_t)(x + 2);
      }
    } else {
      for (int x = lo > 1 ? lo : 1; x < hi; x++) {
        const int f = w[x] ? out(w[x], x - 1) : 0;
        if (f <= 0) continue;
        w[x] -= f; t[x] -= f; w[x - 1] += f; t[x - 1] += f;
        if (x - 1 < s.traceLo) s.traceLo = (int16_t)(x - 1);
      }
    }
  }
}

// Per-column unevenness of the dried traces: high 16 bits scatter the drying rates, low 16 the
// stain share. Same integer hash as the sim's traceUneven (salted differently from traceStreak).
static inline uint32_t traceUneven(uint32_t n) {
  uint32_t h = (n ^ 0x27D4EB2Fu) * 2654435761u + 0x9E3779B9u;
  h ^= h >> 15; h *= 2246822519u; h ^= h >> 13;
  return h;
}

// Highlight rest angle: world-up in the tube cross-section, halved (specular seen along the
// normal), blended with the fixed style angle by lightPhys. See sim lightRest.
float lightRest(float along, float across, const Params &p) {
  float n = sqrtf(fmaxf(0, 1 - along * along - across * across));
  float phys = atan2f(across, n) * 180 / (float)M_PI / 2;
  // Vertical watch held upright: almost no gravity in the cross-section, the angle is noise — fade to the style angle.
  const float w = p.vertical ? fminf(1, 2 * sqrtf(across * across + n * n)) : 1;
  return p.lightAngle + (phys - p.lightAngle) * p.lightPhys * w;
}

void followClock(TubeState &s, float clock, float dt, bool snap) {
  if (snap) s.retract = 1;
  else if (clock < s.clockPrev - 0.5f) { s.retract = 0; s.retractFrom = s.fillTarget; }
  s.clockPrev = clock;
  if (s.retract >= 1) { s.fillTarget = clock; return; }
  s.retract = fminf(1, s.retract + dt / RETRACT_S);
  const float u = s.retract;
  s.fillTarget = s.retractFrom + (clock - s.retractFrom) * u * u * (3 - 2 * u);
}

float columnLen(float fillTarget, const Params &p) { return (p.remaining ? 1 - fillTarget : fillTarget) * TUBE_LENGTH_PX; }

float boreR(const Params &p) {
  int H = (int)jroundf(p.tubeHeight); H = H < 4 ? 4 : H > TUBE_HEIGHT_MAX ? TUBE_HEIGHT_MAX : H;
  return fmaxf(1, (H - 1) / 2.0f - fmaxf(0, p.glassWall));
}

ContactLeads contactLeads(const Params &p, float len, float tilt) {
  const float R = boreR(p), rad = (float)M_PI / 180, PI = (float)M_PI;
  const float t0 = clampf(p.contactAngle, 0, 180) * rad, hy = fmaxf(0, p.contactHyst) * rad;
  auto lead = [R](float th) { return R * cosf(th) / (1 + sinf(th)); };
  // hydrostatic head, split between the two ends: dcos = R·L·sin(alpha) / (4 lc^2), all in mm
  const float lc = fmaxf(0.1f, p.capLength), Rmm = R * MM_PER_PX;
  const float cs = clampf(cosf(t0) - Rmm * fmaxf(0, len) * MM_PER_PX * tilt / (4 * lc * lc), -1, 1);
  const float adv = lead(fminf(PI, t0 + hy)), rec = lead(fmaxf(0, t0 - hy));
  return { R, clampf(R * cs / (1 + sqrtf(1 - cs * cs)), adv, rec), adv, rec };
}

void stepTube(TubeState &s, const TiltInput &in, const Params &p, float dt) {
  const float along = dz(in.along, p.deadzone);
  const float across = dz(in.across, p.deadzone);

  // Tilt-controlled reading: filtered gravity before artistic gain/deadzone, both axes. See sim.
  const float gain = p.inputGain > 0 ? p.inputGain : 1;
  const float poseAlong = in.along / gain, poseAcross = in.across / gain;
  const float hold = clampf(p.playHold, 0, 30);
  s.playTimer = fmaxf(0, fminf(hold, s.playTimer) - dt);
  s.playWindow = fmaxf(0, s.playWindow - dt);
  if (!p.freeLiquid || hold == 0) {
    s.playTimer = s.playWindow = 0; s.playInit = false;
  } else if (!s.playInit) {
    s.playAnchorAlong = poseAlong; s.playAnchorAcross = poseAcross; s.playInit = true;
  } else {
    // Substantial back-and-forth excursions start play; further strokes refresh it. See sim.
    const float da = poseAlong - s.playAnchorAlong, dc = poseAcross - s.playAnchorAcross;
    const float distance = sqrtf(da * da + dc * dc);
    if (distance >= PLAY_STROKE_G) {
      const bool reversal = s.playWindow > 0 && da * s.playDirAlong + dc * s.playDirAcross < -0.5f * distance;
      if (reversal || s.playTimer > 0) s.playTimer = hold;
      s.playDirAlong = da / distance; s.playDirAcross = dc / distance;
      s.playAnchorAlong = poseAlong; s.playAnchorAcross = poseAcross;
      s.playWindow = PLAY_REVERSAL_S;
    }
  }
  // Vertical watch: upright (bottom end down) is the reading pose; gravity toward the bottom end is no tilt. See sim.
  const float tiltAlong = p.vertical ? fmaxf(0, in.along) : in.along;
  const float tilt = asinf(fminf(1, sqrtf(tiltAlong * tiltAlong + in.across * in.across) / gain)) * 180 / (float)M_PI;
  const float start = clampf(p.readTiltStart, 0, 89);
  const float end = fmaxf(start + 1, fminf(90, p.readTiltEnd));
  const float t = clampf((tilt - start) / (end - start), 0, 1);
  const float readTarget = p.freeLiquid ? (s.playTimer > 0 ? 0 : 1 - t * t * (3 - 2 * t)) : 1;
  s.reading += (readTarget - s.reading) * fminf(1, 4 * dt);
  const float flow = p.freeLiquid ? 1 - s.reading : 1;

  // Vertical watch: the along axis carries gravity itself, taken by the tube's closed bottom end — no tilt offset
  // for the edge or its light (the slug, the light angle and the film's drying still feel it). See sim.
  const float sloshAlong = p.vertical ? 0 : along;
  const float fillRest = clampf(sloshAlong * p.fillSloshGain * flow, -FILL_SLOSH_MAX_PX, FILL_SLOSH_MAX_PX);
  const float fillKick = in.gyroAcross * p.angleGyroGain * 4 * flow;
  const float fillAcc = -p.fillK * (s.fillPos - fillRest) - p.fillDamp * s.fillVel + fillKick;
  const float fill0 = s.fillPos;
  s.fillVel += fillAcc * dt;
  s.fillPos += s.fillVel * dt;
  if (s.fillPos > FILL_SLOSH_MAX_PX) { s.fillPos = FILL_SLOSH_MAX_PX; s.fillVel = fminf(0, s.fillVel); }
  if (s.fillPos < -FILL_SLOSH_MAX_PX) { s.fillPos = -FILL_SLOSH_MAX_PX; s.fillVel = fmaxf(0, s.fillVel); }

  // Free liquid: slug slides under along-gravity with drag, bounces at the ends, parked home while reading.
  const float travel = fmaxf(0, TUBE_LENGTH_PX - columnLen(s.fillTarget, p));
  const bool mir = mirrored(p);
  const float home = mir ? travel : 0;
  float slugAcc = 0, slugStep = 0;   // px the slug really moved this tick (a wall stops it, whatever slugVel says)
  if (!p.freeLiquid) { s.slugPos = home; s.slugVel = 0; }
  else {
    slugAcc = flow * along * p.freeGain - p.freeDamp * s.slugVel
      + s.reading * (-p.freeHomeK * (s.slugPos - home) - 2 * sqrtf(p.freeHomeK) * s.slugVel);
    const float v0 = s.slugVel, x0 = s.slugPos;
    s.slugVel += slugAcc * dt;
    s.slugPos += s.slugVel * dt;
    if (s.slugPos <= 0 || s.slugPos >= travel) {   // wall carries the load; the hit is an impulse
      const float wall = s.slugPos <= 0 ? 0 : travel;
      const bool hit = s.slugPos <= 0 ? s.slugVel < 0 : s.slugVel > 0;
      const bool resting = hit && fabsf(x0 - wall) < 0.01f;   // pressed into the wall it already sat on: no impact
      s.slugPos = wall;
      if (resting) s.slugVel = 0;
      else if (hit) s.slugVel = -s.slugVel * p.freeBounce;
      slugAcc = hit && !resting ? (s.slugVel - v0) / dt * 0.25f : 0;
    }
    slugStep = s.slugPos - x0;
  }

  // Meniscus wobble: centre pushed ahead of the contact lines by edge acceleration (inertia), springing
  // back; a steadily moving line is the renderer's dynamic contact angle.
  const float edgeVel = s.fillVel + s.slugVel, edgeAcc = fillKick + slugAcc;   // forcing only, see sim
  const float capAcc = -p.meniscusK * s.cap - p.meniscusDamp * s.capVel + p.meniscusInertia * edgeAcc;
  s.capVel += capAcc * dt;
  s.cap += s.capVel * dt;
  if (s.cap > CAP_DYN_MAX_PX) { s.cap = CAP_DYN_MAX_PX; s.capVel = fminf(0, s.capVel); }
  if (s.cap < -CAP_DYN_MAX_PX) { s.cap = -CAP_DYN_MAX_PX; s.capVel = fmaxf(0, s.capVel); }

  // Wet film: fast attack while an edge recedes, slow drain.
  const float recede = mir ? 1 : -1;
  auto filmT = [](float v) { return clampf(v / FILM_FULL_PX_S, 0, 1); };
  auto follow = [dt](float cur, float target) { return cur + (target - cur) * fminf(1, (target > cur ? 15 : 2) * dt); };
  s.filmFree = follow(s.filmFree, filmT(recede * edgeVel));
  s.filmHome = follow(s.filmHome, p.freeLiquid ? filmT(-recede * s.slugVel) : 0);

  // Dried traces: the mid-row edges the renderer draws, in the panel frame. An edge that receded leaves
  // its film (filmEta at its speed) on the columns it uncovered, all of it wet; gravity runs the wet film
  // down the tube (drainTrace) into the liquid or onto the tube end, while it evaporates over traceDry,
  // leaving traceStain of itself as a stain that fades at the same rate. Tilt moves it, never dries it. See sim.
  if (p.traces && s.trace && s.traceWet) {
    const float len = columnLen(s.fillTarget, p);
    const float fp = clampf(s.fillPos, -len, len);
    const float xt = mir ? s.slugPos + fp : (p.freeLiquid ? s.slugPos : 0.0f) + len + fp;
    const float xh = mir ? len + s.slugPos : (p.freeLiquid ? s.slugPos : 0.0f);
    if (!s.traceInit) s.traceInit = true;
    else {
      // the film the line leaves at its speed, relative to FILM_ETA_MAX: a fast stretch of a slide lays a
      // thicker film than a slow one; the uncovered columns were under the liquid, which dissolved whatever
      // lay there, so a deposit too thin to count clears them (see sim)
      auto dep = [&](float a, float b) {
        if (b <= a) return;
        int v = (int)jroundf(TRACE_FULL * filmEta(p, (b - a) / dt) / FILM_ETA_MAX);
        if (v < TRACE_MIN) v = 0;
        int lo = (int)fmaxf(0, jroundf(a)), hi = (int)fminf((float)TUBE_LENGTH_PX, jroundf(a + fminf(b - a, TRACE_DEPOSIT_MAX_PX)));
        for (int x = lo; x < hi; x++) s.trace[x] = s.traceWet[x] = (uint16_t)v;
        if (v && hi > lo) { if (lo < s.traceLo) s.traceLo = (int16_t)lo; if (hi > s.traceHi) s.traceHi = (int16_t)hi; }
      };
      if (mir) dep(s.xtPrev, xt); else dep(xt, s.xtPrev);
      if (p.freeLiquid) { if (mir) dep(xh, s.xhPrev); else dep(s.xhPrev, xh); }
    }
    s.xtPrev = xt; s.xhPrev = xh;
    drainTrace(s, p, clampf(poseAlong, -1, 1), dt);   // gravity along the tube as the pose sees it
    // film that ran into the liquid (or that the liquid ran over) rejoins it: columns [round(lo), round(hi))
    const float lo = fminf(xt, xh), hi = fmaxf(xt, xh);
    for (int x = (int)fmaxf(s.traceLo, jroundf(lo)), x1 = (int)fminf(s.traceHi, jroundf(hi)); x < x1; x++) {
      s.trace[x] -= s.traceWet[x]; s.traceWet[x] = 0;
    }
    // Linearised rates (dt·rate ≪ 1: caps below). floorf, not round-to-nearest — with a slow
    // traceDry the per-tick decrement is under half an LSB and rounding would stall forever;
    // floor keeps the decay monotone (worst case 1 LSB/tick ⇒ even the faintest stain clears).
    const float dryK = fminf(0.5f, dt / fmaxf(0.05f, p.traceDry));
    int nLo = TUBE_LENGTH_PX, nHi = 0;   // the occupied range re-tightens as columns dry out
    for (int x = s.traceLo; x < s.traceHi; x++) {
      const float v = s.trace[x];
      if (v == 0) continue;
      const uint32_t h = traceUneven(x);
      const float k = dryK * (0.75f + 0.5f * ((h >> 16) * (1.0f / 65535.0f)));
      const float stain = p.traceStain * (0.7f + 0.3f * ((h & 0xffff) * (1.0f / 65535.0f)));
      // the wet film evaporates, leaving `stain` of itself on the glass; the stain fades
      const float w = s.traceWet[x], dw = w * k;
      const int nw = (int)(w - dw), nv = (int)(nw + (v - w) * (1 - k) + stain * dw);   // truncation == floor: non-negative
      // only a dry column counts as gone below TRACE_MIN: a draining film's thin front must not be deleted (see sim)
      if (nw == 0 && nv < TRACE_MIN) { s.trace[x] = s.traceWet[x] = 0; continue; }
      s.trace[x] = (uint16_t)nv; s.traceWet[x] = (uint16_t)nw;
      if (x < nLo) nLo = x;
      nHi = x + 1;
    }
    s.traceLo = (int16_t)nLo; s.traceHi = (int16_t)nHi;
  } else if (s.traceInit && s.trace) {
    s.traceInit = false; memset(s.trace, 0, TUBE_LENGTH_PX * sizeof(uint16_t));
    if (s.traceWet) memset(s.traceWet, 0, TUBE_LENGTH_PX * sizeof(uint16_t));
    s.traceLo = TUBE_LENGTH_PX; s.traceHi = 0;
  }

  // Vertical watch: the surface stays level — the front settles at the tube's in-plane tilt from the vertical,
  // faded out as the panel's plane loses gravity. The sign follows across alone (the liquid lies on the low wall
  // whichever end is down; the renderer leans the home edge the other way), at the cap on its side (see sim).
  const float aMax = p.vertical ? ANGLE_VERTICAL_MAX_DEG : fminf(p.angleMax, ANGLE_HARD_MAX_DEG);
  const float angleRest = clampf(p.vertical
    ? fminf(1, 2 * sqrtf(poseAlong * poseAlong + poseAcross * poseAcross)) * atan2f(poseAcross, fabsf(poseAlong)) * 180 / (float)M_PI
    : across * p.angleTiltGain, -aMax, aMax);   // in-plane gravity only (see sim physics.ts)
  const float angleAcc = -p.angleK * (s.angle - angleRest) - p.angleDamp * s.angleVel;
  s.angleVel += angleAcc * dt;
  s.angle += s.angleVel * dt;
  if (s.angle > aMax) { s.angle = aMax; s.angleVel = fminf(0, s.angleVel); }
  if (s.angle < -aMax) { s.angle = -aMax; s.angleVel = fmaxf(0, s.angleVel); }

  const float rest = lightRest(along, across, p);
  const float lightAcc = -p.acrossK * (s.light - rest) - p.acrossDamp * s.lightVel + in.gyroAlong * p.acrossGyroGain * 10;
  s.lightVel += lightAcc * dt;
  s.light += s.lightVel * dt;
  if (s.light > LIGHT_MAX_DEG) { s.light = LIGHT_MAX_DEG; s.lightVel = fminf(0, s.lightVel); }
  if (s.light < -LIGHT_MAX_DEG) { s.light = -LIGHT_MAX_DEG; s.lightVel = fmaxf(0, s.lightVel); }

  const float shake = fminf(1, ((fabsf(in.gyroAcross) + fabsf(in.gyroAlong)) / 200) * p.shakeGain);
  s.agitation += (shake - s.agitation) * fminf(1, (shake > s.agitation ? 20 : 2) * dt);
  s.edgeLight += (clampf(sloshAlong, -1, 1) - s.edgeLight) * fminf(1, 5 * dt);
  s.acrossTilt += (clampf(across, -1, 1) - s.acrossTilt) * fminf(1, 5 * dt);

  // Pinned contact lines: the tilt pressure moves each end's static lead (a held line that would end up
  // past θA / θR is re-seated on the band's edge — no line speed, the ring doesn't move on screen), then
  // the edge's travel this tick is taken up by the held ring until the lead reaches θA / θR; only the rest
  // drags the line; travel = the slosh and the slug's real, wall-clamped move. A held line creeps back to
  // the static shape over PIN_RELAX_S. See sim.
  const float lenNow = columnLen(s.fillTarget, p), tiltFree = -recede * s.edgeLight;
  const float relax = 1 - fminf(1, dt / PIN_RELAX_S);
  auto seat = [&](float &held, float &lineV, float tilt, float out) {
    const ContactLeads c = contactLeads(p, lenNow, tilt);
    const float lo = c.rest - c.rec, hi = c.rest - c.adv;
    const float moved = clampf(held * relax, lo, hi) + out, pinned = clampf(moved, lo, hi);
    lineV += ((moved - pinned) / dt - lineV) * fminf(1, 2 * dt); held = pinned;
  };
  seat(s.pinFree, s.lineVFree, tiltFree, -recede * (s.fillPos - fill0 + slugStep));
  seat(s.pinHome, s.lineVHome, -tiltFree, recede * slugStep);
}

float GravityNorm::update(float n) {
  if (!init) { mag = n > 0.5f ? n : 1; init = true; }
  else mag += (n - mag) * 0.01f;
  return fmaxf(0.5f, mag);
}

TiltInput ImuFilter::step(const TiltInput &raw, const Params &p, float dt) {
  const float inAlong = clampf(raw.along, -1.2f, 1.2f), inAcross = clampf(raw.across, -1.2f, 1.2f);
  if (!init) { lpAlong = lpAlong2 = inAlong; lpAcross = lpAcross2 = inAcross; hpPrevIn = raw.gyroAcross; init = true; }
  const float a = 1 - expf(-2 * (float)M_PI * p.accelLpHz * dt);
  lpAlong += (inAlong - lpAlong) * a;
  lpAcross += (inAcross - lpAcross) * a;
  lpAlong2 += (lpAlong - lpAlong2) * a;
  lpAcross2 += (lpAcross - lpAcross2) * a;
  float g;
  if (p.gyroHpHz <= 0) g = raw.gyroAcross;
  else {
    const float rc = 1 / (2 * (float)M_PI * p.gyroHpHz), k = rc / (rc + dt);
    g = k * (hpPrevOut + raw.gyroAcross - hpPrevIn);
    hpPrevIn = raw.gyroAcross; hpPrevOut = g;
  }
  const float gl = 1 - expf(-2 * (float)M_PI * GYRO_LP_HZ * dt);
  lpGyroAcross += (clampf(dz(g, p.gyroDeadzone), -p.gyroMax, p.gyroMax) - lpGyroAcross) * gl;
  lpGyroAlong += (clampf(dz(raw.gyroAlong, p.gyroDeadzone), -p.gyroMax, p.gyroMax) - lpGyroAlong) * gl;
  return { lpAlong2 * p.inputGain, lpAcross2 * p.inputGain, lpGyroAlong * p.inputGain, lpGyroAcross * p.inputGain };
}
