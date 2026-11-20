# Renderer precompute / collapse audit (read-only)

Code: /home/andrey/_PROJECTS/watches-perf-audit (detached snapshot at 6df29da; do NOT edit anything anywhere).
Board in question: ESP32-S3 LCD-3.16 (820x320 RGB565, two 8 mm tubes of 72 rows, dual core, internal RAM tight,
PSRAM for big buffers), firmware `firmware/src/render.cpp` (+ render.h, tiles.h, tile_dma.cpp, main.cpp,
display_lcd316.cpp), mirrored by the sim `sim/src/render.ts` (parity sim <-> firmware is a hard requirement).
The user's look on the board: /tmp/claude-1000/-home-andrey--PROJECTS-watches/6b36e029-86b5-44da-bf6a-b636a5744698/scratchpad/board-look-1120.json
Last bench, fixed pose, that look family: 51.1 fps, render 19.0 ms (cores h 16.1 / m 12.0 ms), push 2.2 ms,
phys ~1 ms, fizz ~2 ms. A new post-pass (edge shade: per-row darkening of whole tube rows, render.cpp
`Tube::edgeShade` / `shadeRow`) costs 2.9 ms; another agent is already folding THAT one into the per-row palette —
do not design it, but you may mention how it interacts with your proposals.

The owner's belief: many calculations are recomputed per frame / per pixel that could be pre-executed when params
change (or per tilt state, per fill level) and collapsed into tables, so the per-frame work shrinks. Test that
belief against the code.

Read first what was already done, so you don't re-propose it: docs/perf-render-math.md, docs/perf-residue-math.md,
docs/perf-handoff-1..4, docs/lcd316-perf-plan.md, docs/lcd316-3tube-perf.md, docs/perf-core-balance.md,
docs/fizz-perf-handoff.md, KAIZEN.md perf notes, STATUS.md recent entries. Repo rules: CLAUDE.md (no lazy alloc,
static/boot buffers sized for worst case).

Deliver a ranked list (largest expected per-frame saving first, max ~12 items). For each:
- what is recomputed and where (file:line), how often (per pixel/row/frame), why it is invariant over what span
  (param change / fill change / tilt / time),
- the collapse: what table/cache, its size (bytes, internal vs PSRAM), when rebuilt, rebuild cost,
- expected saving in ms on the board's look with the reasoning (pixel counts x cost), confidence,
- parity/exactness implications (can sim do the identical thing?), risk.
Also say plainly which parts of the owner's belief do NOT hold (already collapsed, or truly per-frame dynamic).
Write it as markdown; the final message is the report.
