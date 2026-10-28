---
name: board-switch-design-px
description: "Boards/canvases switch by LW_BOARD/LW_RES (or ?board=&res=); params stay design px, boardParams scales PX_KEYS on both sides"
metadata:
  node_type: memory
  type: project
  originSessionId: cfbb3dbe-4931-48c5-a29c-bde13062d68a
  modified: 2026-10-27T14:29:26.259Z
---

Since 2026-10-27 the face renders into a per-build canvas (spec/layout.h|ts PANEL_W × PANEL_H): AMOLED 536×240,
LCD-3.16 RENDER_H rows of 41:16 (240/256/288/320, upscaled to 820×320 in the push). Selection: `LW_BOARD` / `LW_RES`
(flash.sh, flash-win.sh, e2e.sh `--env/--res`, node tools), sim `?board=lcd316&res=320` (sticky in localStorage);
firmware `v` reports `board lcd316@320 canvas …`.

Params are always design px (the 240-row canvas): presets, NVS, `p` writes. `boardParams` (sim params.ts,
firmware physics.h) scales PX_KEYS by PX_SCALE and rounds PX_WHOLE_KEYS; gen_params.py reads both lists.

**Why:** presets stay board-independent; the AMOLED stays byte-identical (scale 1 = identity).

**How to apply:** a new px-dimensioned param goes into PX_KEYS (and PX_WHOLE_KEYS if the renderer treats it as
whole pixels — fractional values broke sim digit rows once); anything that *produces* params (derive, migration,
presets) uses DESIGN_* constants, anything that renders uses canvas ones. LCD parity on the host:
`firmware/tools/check_board_render.py --res N`. Extends [[params-mirror-firmware]]; perf numbers in STATUS.md.

LCD perf (2026-10-27): env lcd316 = recompiled Arduino libs with a 64 KB / 64-B data cache (`custom_sdkconfig`), built
from `~/.platformio/packages-lcd316` (tools/pkgdir.sh; a bare `pio run -e lcd316` is refused) — the hybrid compile
rewrites the shared libs package and drops SPIRAM_BOOT_INIT unless restated. At native everything is PSRAM-latency
bound: compute-side micro-optimisations (divisions, IRAM, memo) measured ~0; cache size / locality is what moves fps.
