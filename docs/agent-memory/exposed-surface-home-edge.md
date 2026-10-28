---
name: exposed-surface-home-edge
description: In remaining+freeLiquid presets with freeHomeK 0 the visible meniscus is the HOME edge (edgesL); the time edge sits at the panel border — surface effects must target the exposed edge
metadata:
  type: project
---

The user's daily preset (2026-09-22: `remaining` true, `freeLiquid` true, `freeHomeK` 0, `readTiltStart` 0)
leaves the slug against the near end: in the render frame `xe == L`, so the time edge is invisible at the
panel border and the meniscus you see on the right is the home edge (`edgeXL` / `edgesL`).

**Why:** the fizz foam first parked under the time edge and was invisible on the user's watch; the fix
was an "exposed surface" mask published by drawTube (bit 1 time edge short of the far end, bit 2 home
edge of a free slug off the near end) — see `fizzExposed` in sim/src/render.ts and firmware render.cpp.

**How to apply:** any new edge/surface effect must ask which edge is exposed, not assume the time edge;
test with the user's preset via URL `p.<key>=` overrides (bools 1/0, colours %23). Related:
[[liquid-pinned-model]], [[params-mirror-firmware]].
