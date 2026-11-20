# Edge shade: darken the tube towards its long edges (sim + firmware)

Worktree: /home/andrey/_PROJECTS/watches-edge-shade (branch `edge-shade`, from desk-housing HEAD 65f0bef).
Work ONLY there. Never touch /home/andrey/_PROJECTS/watches (the user's working copy, has uncommitted work).
Read CLAUDE.md / AGENTS.md there first (no lazy allocation in firmware; side ideas -> KAIZEN.md, one line each).

## Why
An 8 mm acrylic half-rod lies on the LCD over each drawn tube. Through it the panel's pixel rows show as stripes;
near the rod's long edges its magnification climbs (1.8x centre, 2x at ~1.65 mm from the centre on the panel,
3x at ~1.9 mm, folds beyond) and the stripes + rainbow get strong, worst when viewed from the side. Stripe
visibility scales with the brightness of the rows. Narrowing the drawn tube removes it but kills the 3D look from
the side, so instead: darken everything drawn in the tube gradually towards both long edges, keeping hue.

## What
Three new params (sim `Params` + firmware codegen + presets, schema v28 -> v29, migrate mechanically):
- `edgeShade` 0..1, default 0 (off: every render must stay byte-identical to HEAD). Darkening at full depth:
  colour *= 1 - edgeShade.
- `edgeShadeFrom` mm, default 1.4: distance from the tube's centre line on the glass where darkening starts.
- `edgeShadeTo` mm, default 1.9: distance where it reaches full depth; beyond it, full depth.
Real mm on the glass (like `tubeGap`): convert with the board's PX_PER_MM / LCD_MM_PER_PX (spec/layout.ts|h), so
the band stays under the same part of the rod at any tube width. Profile between From and To: smoothstep (no
visible ring at either end). To <= From: hard step at From.

Semantics: a final per-row multiply towards black over the tube's own rows, in DISPLAY rows (after the rendered
lens remap `applyLens`, i.e. the rows the panel shows), symmetric about the tube's centre row ((H)/2 in the
tube's rows). Applies to everything in the tube rows: liquid, empty tube back, glass wall band, rim, ticks,
digits, fizz, meniscus. Same for every tube (hours / minutes / seconds), both boards (LCD, AMOLED).

Exact sim/firmware parity is the bar (the repo checks it with tolerance 12/255, aims for 0): quantise the per-row
factor once (e.g. T in 1/256) and use the same integer 565 maths both sides (existing blend565T / sim blend565
towards 0 is a fine route). Firmware: per-row factor table computed when params change (static/boot storage,
next to the existing row caches such as lensSrc), rows with no darkening skipped; must work on every render path
the board uses (strip path, tiled band loop -DTILE_RENDER=1, LCD change-record / tile-hash push: darkened rows
must be in what gets hashed/pushed). Look how applyLens is wired into each path and follow it.

Sim: sliders/inputs wherever params get UI (follow how tubeGap / other params appear). Overlay (simulated rod
view) unchanged.

Template for adding a param end-to-end: commit a302988 (tubeStack / tubeGap): params.ts, gen_params.py,
params_gen.h, presets/*.json migration, check tool versions, STATUS/README notes.

## Checks (run them, report numbers verbatim)
- sim: the repo's npm checks that cover params/presets/layout (check:presets, check:layout, tsc/build).
- Host parity, edgeShade 0: check_board_render on lcd316 (`--res 320w8-8`, also `--tiles`) and amoled191 give the
  same figures as on HEAD (run HEAD first in a throwaway copy or note the numbers from STATUS if equal config).
- Host parity, edgeShade on: a few presets with edgeShade 0.6 (From 1.4, To 1.9) sim vs firmware, 0 px > 12/255,
  both paths (strip and --tiles). Also a sanity image showing the darkened band (save PNG to the scratchpad below).
- Firmware builds: lcd316@320w8-8 (the board's), amoled191. Static RAM delta reported.
- Board (connected: lcd316@320w8-8, /dev/ttyACM1; tools in firmware/tools, skill `firmware-e2e`): flash the new
  build. The schema CRC change drops NVS params: the user's look (v28 JSON, from `p?` before) is saved at
  /tmp/claude-1000/-home-andrey--PROJECTS-watches/6b36e029-86b5-44da-bf6a-b636a5744698/scratchpad/board-params.txt
  — restore exactly that look (migrated to v29, edgeShade 0) afterwards, verify with `p?`. Measure fps (`f`, same
  pose) with edgeShade 0 and 0.6, then leave the board on the user's look with edgeShade 0.6 / 1.4 / 1.9 set
  volatile or saved, whichever the tools normally do for a look change (say which). compare-device at the end.

## Deliver
Commit in the worktree (one commit, message ending with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`), STATUS.md entry in the repo's style (dated
2026-11-19). Add to KAIZEN.md: "liquidThin: no visible effect on the board's look (glassWall 10, wallWet 0.79,
user 2026-11-19); unchecked." Report: files touched, design decisions, every check's verbatim numbers, fps,
anything you could not do. Do not push.
