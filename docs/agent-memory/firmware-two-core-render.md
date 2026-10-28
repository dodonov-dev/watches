---
name: firmware-two-core-render
description: firmware renders hours on core 0 and minutes on core 1 concurrently — per-frame scratch in render.cpp must live in Tube, never file-static
metadata:
  type: project
---

`firmware/src/main.cpp` renders the hours tube in a worker pinned to core 0 while `loop()` renders the
minutes tube on core 1, at the same time. Any per-frame table or scratch buffer in render.cpp therefore
belongs to its Tube (a member, or a per-Tube PSRAM buffer from render_init when large — internal RAM is nearly
full, see [[firmware-static-memory]]), never a file-scope static.

**Why:** 2026-09-26 the rear-mark wet-share table was one file-static array; the two cores overwrote each
other's shares and full tubes flickered / end digits vanished on the board a few seconds after boot. The
host checks (check_meniscus, check_render_frames, hostjob) render tubes sequentially and cannot see it,
and the `x` dump also re-renders both tubes on one core, so compare-device cannot either.

**How to apply:** when adding render-time state to render.cpp, grep for new `static` arrays and move them
into Tube; verify on the panel (live frames), not only with the host tools. Related: [[firmware-static-memory]],
[[legacy-host-harness]], [[firmware-e2e-tooling]].
