# ESP32-S3-LCD-3.16 — native 820×320 face

_Follows the 1:1 bring-up (env `lcd316`, `firmware/src/display_lcd316.cpp`): the 536×240 canvas is shown centred, pixel
for pixel, with black margins. This plan fills the whole panel at its own resolution._

## Status (2026-10-27)
Phases A (sizes), B and C are in, in this shape (STATUS.md has the numbers): the canvas is RENDER_H rows of the
panel's aspect (`-DRENDER_H` / `LW_RES`, 240–320), upscaled nearest-neighbour in the CPU push; params stay in design
px and `boardParams` scales them (PX_KEYS, whole-pixel ones rounded) in sim and firmware; MM_PER_PX is
design-consistent. Native runs at 13.2 fps, 240 at 28.0 — below the 30 fps gate. GDMA push (A.2) not done.

### Display path (next)
The push costs 16–29 ms at every RENDER_H (it always writes 820×192 px into the scanned PSRAM framebuffer); PSRAM
strips cost the render ~1.4×. Candidate: bounce-buffer scan-out, no framebuffer (`flags.no_fb`,
`bounce_buffer_size_px`, `on_bounce_empty`, all in the IDF 5.5 headers): front copies of the two strips in PSRAM in
canvas layout; the "push" becomes a row-major memcpy back→front (each core its own tube, right after rendering it);
the ISR gathers each scan line (one canvas column, upscaled through colOf / rowOf, black outside the tube rows) into
the internal bounce buffer. Removes the transposing push and the DMA's 24 MB/s framebuffer scan; costs an ISR of
~7 Mpx/s gather (est. 10–15 % of one core) and 2 × front strips of PSRAM. Faces other than the liquid one gather
from the PsramCanvas. Risks: ISR deadline under PSRAM contention (glitch, not a drift), NVS flash writes stall it.
Estimate: native ~45 ms → ~21 fps, 240 (one strip internal) ~18 ms → ~40+ fps. Alternative: GDMA scatter push (A.2),
keeps the framebuffer, halves its write traffic.

## Hand-off notes (for an agent without this conversation)
- Rules: repo `CLAUDE.md` (no lazy allocation: every buffer static or allocated once at boot, fail visibly; side ideas
  → `KAIZEN.md`). Params mirror the firmware: a sim `Params` change ⇒ `firmware/tools/gen_params.py` + `render.cpp` +
  `presets/1.json` + regen, grep the whole repo. Presets are disposable: migrate mechanically, don't re-tune looks.
- Board: Waveshare ESP32-S3-LCD-3.16 — ESP32-S3R8 (8 MB octal PSRAM, AP 3 V), 16 MB QIO flash, ST7701 RGB LCD 320×820
  scanned portrait (320-px lines, 820 lines), no frame memory, no hardware rotation. QMI8658 + PCF85063 on I2C SDA 15 /
  SCL 7. Backlight PWM GPIO 6, active low. Pins, init sequence, timings: `display_lcd316.cpp` (from Waveshare's demo
  `07_LVGL_V8_Test`; LCD CS is GPIO0 via R38, the wiki pin table's IO42 is wrong).
- Tooling: `firmware/tools/flash-win.sh --env lcd316 [COMx]` (board on the Windows side), `tools/e2e.sh --env lcd316`,
  `tools/device.py --port COMx f s x`. The AMOLED board (`amoled191`) stays the default everywhere; never regress it.
- Reference numbers, 1:1 bring-up, default preset, scene pinned (`g 0 0`, `t 10:09:30`, `d0`; 2026-10-27): 50.0 fps,
  render 11.9 ms, push ~7.1 ms at pclk 16 MHz (50.8 fps at 14 MHz); internal heap 4.2–4.5 KB free with BLE up.

## Constraints found in the bring-up (read before designing)
1. **PSRAM bandwidth is the scarce resource.** The LCD DMA scans the 525 KB framebuffer out of PSRAM at 46.1 Hz
   (pclk 16 MHz, 24 MB/s). At Waveshare's 18 MHz the picture jumped sideways and back now and then, even on the static
   `h` face: the DMA fell behind until the restart at VSYNC (no bounce buffers). 16 and 14 MHz were steady; anything that
   adds PSRAM traffic can bring the jump back — check by eye, it is not reported anywhere. The CPU quarter-turn copy of a 536×72 strip into it takes 3.7 ms (3.0 copy + 0.7 cache write-back),
   bound by cache-line fills and write-backs, not by the loop: 32-bit stores changed nothing, and pushing both strips
   from both cores at once made each push 7.0 ms (bus saturated) and slowed the renders. At native size the same path
   would cost ~17 ms per frame.
2. **Internal RAM is full.** The two strips (2 × 536 × 80 × 2 B = 171 KB) sit in internal RAM; ~4 KB stays free with
   BLE. Native strips (820 × ~108 rows) are 177 KB each — both cannot be internal.
3. **Render cost scales with pixels:** 820×H·4/3 per tube is ~2.3× today's pixels → expect ~30 ms render on two cores
   before any PSRAM penalty, i.e. ~25–30 fps unless something else gives.
4. Fixed sizes to revisit: `Labels::rows[96]` in `render.cpp` (must hold `TUBE_HEIGHT_MAX`), `static Tube tubes[2]`
   (internal RAM; its per-row and per-column arrays grow with `TUBE_HEIGHT_MAX` / `TUBE_LENGTH_PX`), `g_trace` in
   `physics.cpp` (static, `TUBE_LENGTH_PX`), sprite glyph pools (`GLYPH_POOL_PX`, PSRAM).

## Step 0 — board check
- `tools/device.py --port COMx s f`: banner `liquid-watch | lcd316`, IMU ok, ~44 fps on the 1:1 build.
- `h` face upright with USB-C on the left (verified 2026-10-27), IMU tilt signs match the AMOLED (`i` stream; `board.h`
  `IMU_REF`), no sideways jump of the picture.

## Phase A — firmware feasibility spike (no sim changes yet; go / no-go)
Goal: real numbers for a native frame before touching the sim, params or presets.
1. `layout.h`: board block under `BOARD_LCD316` — `PANEL_W 820`, `PANEL_H 320`, `TUBE_LENGTH_PX 820`,
   `TUBE_HEIGHT_MAX 108`, defaults ×4/3 (tube 96 px at y 0 / 224). Fix the fixed sizes of constraint 4. Strips move to
   PSRAM (boot-time, fail visibly), which frees 171 KB of internal RAM for what follows.
2. Push through GDMA instead of the CPU: the CPU turns the strip into a small internal ping-pong chunk (N scan lines ×
   H px), a GDMA M2M transfer writes the chunk's N line segments into the framebuffer through a scatter RX descriptor
   list (`esp_private/gdma_link.h`: `gdma_new_link_list` / `gdma_link_mount_buffers`, present in the prebuilt libs).
   DMA writes skip the write-allocate fills (half the traffic) and leave the CPU free; the 1:1 build gains from it too
   (its push is the same CPU copy, ~7 ms/frame). PSRAM EDMA alignment: segment
   start and length on the external-memory block size (16/32/64 B) → tube rows on multiples of 8 px on this board, or
   CPU-write the unaligned head/tail. Cache: the CPU must not hold dirty framebuffer lines (write back + invalidate once
   after the boot clear).
3. Measure with a preset pinned (`e2e.sh --env lcd316 --preset …`): fps, render (strips in PSRAM vs internal for one
   tube), push, frame-p95, internal heap, and a visual check for the sideways jump / tearing (ask the user to watch,
   one change per round). Lower `pclk` (14 MHz = 40 Hz scan, −12 % scan-out traffic) if the jump returns.
- **Gate:** ≥ 30 fps on the default preset with no visible drift → Phase B. Otherwise stop and report the numbers; the
  fallback is ×4/3 upscaling of the 536×240 canvas in the push (sim and presets untouched, softer image).

## Phase B — layout per board in the spec
1. `spec/layout.ts` mirrors the board block. The sim picks the board once at start-up — URL `?board=lcd316` in the
   browser, `LW_BOARD=lcd316` for node tools — because modules size buffers from the constants at import
   (`render.ts` `fb`, `physics.ts` traces, `main.ts` canvases, `overlay.ts`, `material/derive.ts`, `material/presets.ts`).
   No live switching.
2. Tools take the board: `check-meniscus.cjs`, `check:imu`, `compare-device.py`, `check_render_frames.py`, the legacy
   host harness (memory: render.cpp + physics.cpp build on host with stub headers) — build it per board.

## Phase C — px params across boards
Most look params are in px (sizes, px/s speeds, px/g gains — see `sim/src/params.ts` comments); presets are tuned on
the 240-px-tall canvas.
1. Recommended: params stay in **design px** (the 536×240 canvas); a board step `boardParams(p)` scales every
   px-dimensioned field by `s = PANEL_H / 240` (4/3 here) after preset load / derive, in sim and firmware alike. Tag the
   unit of each field in the params metadata (`px`, `px/s`, `px/g`, `px/s²`, none) and let `gen_params.py` emit the same
   scale table for the firmware, so both sides scale one list. Digits scale through `digitScaleX/Y` (fractional,
   nearest-neighbour). Rounded geometry (`tubeHeight`, `hoursY`, `minutesY`) rounds after scaling, with the alignment
   rule of A.2.
2. `MM_PER_PX` per board (0.083 AMOLED, ≈0.0912 LCD): decide whether the physical meniscus and the material layer use
   the real pitch (honest physics: a bigger bore → flatter meniscus on the LCD) or the design canvas (same look on both).
   Recommendation: real pitch; it is what the material layer models.
3. Alternative, not recommended: per-board preset sets migrated by a script — doubles every future preset change.

## Phase D — verify
- AMOLED: byte-identical strips (`check_render_frames.py`), parity and fps unchanged (`e2e.sh`).
- LCD native: sim vs device parity within 12/255 (`compare-device.py` with the board), `check-meniscus.cjs` per board,
  `d60` soak 60 s without reboot, BLE connected, frame-p95 recorded.
- Sim: `?board=lcd316` renders the presets proportionally (screenshots of default + two presets, `run-sim` skill).

## Not now (→ KAIZEN)
Double-buffered framebuffer / VSYNC swap against tearing (none visible at 1:1), the bounce-buffer compositor
(`no_fb` + `on_bounce_empty`, needs stable strips).

## Done when
Native face on the LCD at ≥ 30 fps with sim parity, the AMOLED unchanged, numbers in STATUS.md.
