---
name: firmware-static-memory
description: Firmware rule — no lazy/on-demand allocation; every buffer static or boot-time so the max footprint is deterministic
metadata:
  type: feedback
---

No lazy or on-demand allocation in the firmware: caches, tables, glyph sets, effect LUTs are static arrays
(or allocated once at boot), sized for the worst case. If something does not fit, fail visibly (drop / log),
never fall back to another heap (e.g. PSRAM).

**Why:** the user wants a deterministic maximum memory footprint on the ESP32-S3 (internal DMA strips + BT
controller already compete for internal RAM; a late malloc failing at runtime is worse than a boot-time one).
Given 2026-08-27 when hand-off 1 introduced first-use `heap_caps_malloc` for edge-effect tables.
**How to apply:** `static` arrays with a `_MAX` bound; no `heap_caps_malloc` in render paths; rule is also in
CLAUDE.md / AGENTS.md. See [[firmware-e2e-tooling]] for verifying after memory changes.
Internal RAM budget (2026-09-26): only ~2.7 KB internal heap is left once BLE is up (`s` → heap 2684). A new
4.3 KB static in the Tubes made BLE init hang silently (black screen, no `ready.` on serial). New per-tube
tables go to PSRAM, allocated once in render_init next to the glyph pools (fail visibly via its return);
check `pio run` RAM against HEAD and `s` heap after any firmware memory change. Related: [[firmware-two-core-render]].
