---
name: xtensa-float-costs
description: "On the ESP32-S3 build fminf/fmaxf/floorf/ceilf, float `/` and sqrtf are out-of-line calls; render.cpp uses inline fmn/fmx/ffloor/fceil — the 2026-09-23 perf pass took the bench scene 27.4 -> ~35 fps with this"
metadata:
  node_type: memory
  type: project
  originSessionId: 06c4e026-49cf-4e39-bf8a-b71ec4eebff7
  modified: 2026-09-22T22:51:10.844Z
---

The Xtensa LX7 FPU in the ESP32-S3 has no min/max/floor/ceil, divide or sqrt instructions. libm
fminf/fmaxf/floorf/ceilf are flash calls, `/` is ROM `__divsf3`, sqrtf is newlib's bit-by-bit loop.
Before 2026-09-23 render.cpp had ~290 such call sites, a dozen per pixel in the edge loops. Swapping in the
inline `fmn/fmx/ffloor/fceil` (top of render.cpp, same values for non-NaN input) and taking loop-invariant
divisors out as reciprocals cut the edge glow 4.7 -> 1.8 ms, the surface band 3.7 -> 2.0 and fizz 2.3 -> 1.1.
It was byte-identical on `check_render_frames.py`.

**Why:** grep for these calls in the object (`objdump -dr render.cpp.o | grep -E "fminf|__divsf3|sqrtf"`) before
blaming the maths; they cost 20–250 cycles each. The I-cache is 16 KB, shared by both cores (prebuilt
Arduino libs). Free internal heap is ~5 KB with BLE up, so moving render code to IRAM is not an option.

**How to apply:** in new per-pixel render code use fmn/fmx/ffloor/fceil, multiply by a hoisted reciprocal,
and compare squared distances. Use `sqrtApprox` only where a 1/256 alpha step is acceptable. For stage costs
the bench.py stage-off deltas are ±1 ms noise. A cycle-counter probe around drawTube stages is far more
precise (see KAIZEN). Related: [[drawtube-hot-loops-noinline]], [[firmware-e2e-tooling]], [[firmware-static-memory]].
Physics loops count too (they run in the frame): the residue drain's per-column fminf/floorf cost ~1 ms a step under
sweep stress (2026-10-02); inline min + (int) truncation fixed it. See [[residue-physics]].
