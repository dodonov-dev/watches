---
name: presets-disposable
description: Signature presets are disposable — model/param changes need not preserve their look; mechanical migration + passing checks is enough
metadata:
  type: feedback
---

Presets (`presets/*.json`, `PRESETS` in sim/src/params.ts) will be rewritten eventually; the user said
(2026-09-24) "do NOT care much for the presets".

**Why:** effort spent re-tuning each preset's look after a renderer/param change is wasted.

**How to apply:** when a model change alters or replaces params, migrate presets mechanically (a sensible
mapping of old → new keys), keep `check:presets` / dump / gen_params working, and move on — no per-preset
visual matching. Firmware mirroring ([[params-mirror-firmware]]) still applies. Related: [[presets-own-design]].
