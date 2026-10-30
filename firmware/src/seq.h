#pragma once
// A deterministic step sequence, shared by the board's `X` command and tools/check_fizz_steps.py (host): a fixed tilt
// script through the IMU filter, both tubes and the fizz stepped at PHYS_DT, a frame rendered every SEQ_FRAME_EVERY
// steps. Same params + same start = the same frames, so two builds compare frame by frame (fizz, residue, memos
// carried across frames). The caller resets the render side first (board: render_seq_reset; host: a fresh process).
#include <math.h>
#include <string.h>
#include "physics.h"
#include "render.h"

#define SEQ_PHASE_STEPS 100                     // 2 s a phase
#define SEQ_PHASES 7
#define SEQ_STEPS (SEQ_PHASES * SEQ_PHASE_STEPS)
#define SEQ_FRAME_EVERY 2
#define SEQ_FRAMES (SEQ_STEPS / SEQ_FRAME_EVERY)
#define SEQ_HOURS_FILL (10.158333f / 12)       // 10:09:30
#define SEQ_MINUTES_FILL (9.5f / 60)

// The raw tilt (g, dps) at a step.
inline TiltInput seqTilt(int step) {
  const float t = step * PHYS_DT;
  auto swing = [&](float a, float b, float T) { return fmodf(t, T) < T / 2 ? a : b; };
  switch (step / SEQ_PHASE_STEPS) {
    case 0: return {0, 0, 0, 0};                                     // face up
    case 1: return {-1, 0, 0, 0};                                    // vertical watch upright: springs fill
    case 2: return {swing(-1, 0.6f, 3), 0, 0, 0};                    // pitching with across ~0 (the fizz-collapse case)
    case 3: return {-0.3f, swing(-0.7f, 0.7f, 2), 0, 0};             // across sweeps: the slug slides, residue
    case 4: return {-0.7f, 0.7f, 0, 0};                              // held sideways
    case 5: { const float s = sinf(t * 25.13f); return {0.5f * s, 0.2f * s, 300 * s, 200 * s}; }   // shaking: agitation
    default: return {-0.5f, 0, 0, 0};                                // slug home
  }
}

// FNV-1a over a strip's first rows * w words.
inline uint32_t seqHash(const uint16_t *strip, int words) {
  uint32_t h = 2166136261u;
  for (int i = 0; i < words; i++) { h = (h ^ (strip[i] & 0xff)) * 16777619u; h = (h ^ (strip[i] >> 8)) * 16777619u; }
  return h;
}

// Runs the sequence from a fixed start (both TubeStates and their residue buffers cleared, fills snapped to
// 10:09:30). emit(frame, strips) after each frame's two renders (strips[0] hours, strips[1] minutes).
template <class Emit> void seqRun(TubeState &h, TubeState &m, const Params &p, uint32_t &gen, uint16_t *const strips[2], Emit emit) {
  TubeState *const tube[2] = {&h, &m};
  for (int i = 0; i < 2; i++) {
    TubeState &s = *tube[i];
    s = TubeState();
    s.trace = traceBuf(i); s.traceWet = traceWetBuf(i);
    if (s.trace) memset(s.trace, 0, TUBE_LENGTH_PX * sizeof(uint16_t));
    if (s.traceWet) memset(s.traceWet, 0, TUBE_LENGTH_PX * sizeof(uint16_t));
  }
  followClock(h, SEQ_HOURS_FILL, 0, true); followClock(m, SEQ_MINUTES_FILL, 0, true);
  ImuFilter filter;
  gen++;   // the render's caches key on it
  for (int step = 0; step < SEQ_STEPS; step++) {
    followClock(h, SEQ_HOURS_FILL); followClock(m, SEQ_MINUTES_FILL);
    const TiltInput in = filter.step(seqTilt(step), p);
    stepTube(h, in, p); stepTube(m, in, p);
    stepFizz(p, PHYS_DT, in.along, in.across, h.agitation);
    if ((step + 1) % SEQ_FRAME_EVERY) continue;
    renderTube(0, h, p, gen, strips[0]); renderTube(1, m, p, gen, strips[1]);
    emit((step + 1) / SEQ_FRAME_EVERY - 1, strips);
  }
}
