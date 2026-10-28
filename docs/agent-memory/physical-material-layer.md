---
name: physical-material-layer
description: Physical simulator = material→legacy Params derivation (sim/src/material), not a separate renderer; rules that must hold when touching it
metadata:
  type: project
---

The "physical simulator" (2026-09-25) is `derive(material, design) → Params` in `sim/src/material/` (laws in
`docs/physical-renderer.md`), rendered by the legacy renderer and firmware; the phase-1 standalone optical renderer was retired.

**Why:** the legacy pipeline already held the math and the realism rules; realism by construction comes from removing knobs, not
from a second renderer. Firmware stays one build (Params v24 added `rimLight`/`rimTint` only).

**How to apply:** every derived Params must pass `coherenceIssues` (the preset checker's rules) — derive rejects, never clamps;
optical targets are linear light encoded once, palette inversions in encoded 8-bit space; `ambientLight` stays 0 and any
"add light" law sums in linear before encoding; colour fits are checked against the real `buildPalette` rows (`check:materials`).
Preset tuning goes through material/lighting properties (provenance measured/estimated/artistic), never per-preset renderer
overrides. See [[params-mirror-firmware]], [[presets-disposable]].
