# LCD-3.16 native: 30+ fps on the user preset

Goal: `firmware/bench/user-fav.json` (the user's favourite look) at the native 820×320 canvas, pinned bench, **≥ 30 fps**.
Native stays: lower canvases were compared side by side on the board and look worse.

## Rules (every step)
- Repo rules: `CLAUDE.md` (no lazy allocation; side ideas → `KAIZEN.md`, laconic). Do not commit.
- Firmware memory: every buffer static or allocated once at boot; per-frame scratch belongs to its `Tube` (two cores
  render at once: hours core 0, minutes core 1), never file-static.
- Sim ↔ firmware parity: a step either keeps the AMOLED render byte-identical (`firmware/tools/check_render_frames.py
  --reference <render.cpp before the step> --tolerance 0`) or changes the look on purpose, mirrored in
  `sim/src/render.ts` / `physics.ts`, with host parity no worse (`firmware/tools/check_board_render.py --board amoled191`
  and `--res 320`, `cd sim && npm run -s check:meniscus`) and board parity `>12/255 off: 0` on the user preset.
  A look change is reported as such (what changes, where to look): the user judges it on the board.
- Coarser params, pre-baked tables, approximations (linear / LUT instead of `powf`, `sqrtf`, `expf` …), inline
  assembly / the S3's PIE SIMD, renderer restructuring, library / sdkconfig changes: all allowed when measured.
  Xtensa notes: `fminf`/`floorf`/`/`/`sqrtf` are library calls (use `fmn`/`fmx`/`ffloor`/`fceil`, reciprocals); per-
  pixel inline loops spill (extract `noinline` kernels); at native everything is PSRAM-latency bound (64 KB / 64-B data
  cache since 2026-10-27): divisions, IRAM placement and a per-texel memo measured ~0 — locality and fewer bytes win.
- AMOLED (`amoled191`) must keep building and stay within its internal RAM (`pio run -e amoled191` RAM ≤ 88.4 KB).

## Measuring (board: Waveshare ESP32-S3-LCD-3.16 on Windows COM11)
```
cd firmware
LW_PORT=COM11 tools/e2e.sh --env lcd316 --preset bench/user-fav.json --runs 2 --label "<step>"            # flash + bench + parity
LW_PORT=COM11 tools/e2e.sh --env lcd316 --no-flash --stages --preset bench/user-fav.json --label "<step>"  # stage costs
```
- lcd316 builds from `~/.platformio/packages-lcd316` (recompiled libs); `tools/flash.sh` / `e2e.sh` handle it. A bare
  `pio run -e lcd316` is refused; for a compile check: `ENV=lcd316 . tools/pkgdir.sh; ~/.platformio/penv/bin/pio run -e lcd316`.
- `-DDIGIT_PROF` (`--define DIGIT_PROF`) prints per-tube digit counters and cycle splits in `f` (`tools/device.py --port COM11 f`).
- `f` line: render = wall time of both cores' renders, `cores h / m` = each core's render, push = the CPU quarter-turn
  of both strips into the PSRAM framebuffer (serial, on core 1, after both renders), rest = loop outside the face.
- The bench pins the clock (`t 10:09:30`, `d0`): nothing to undo. If the Windows bridge holds the port ("Access is
  denied", "bridge did not exit"), wait a few seconds and rerun the step that failed.
- The LCD tears / jumps sideways when the panel DMA or its bounce-buffer refill (ISR, core `LCD_ISR_CORE`) starves on
  PSRAM: it is not reported anywhere. Any step that changes PSRAM traffic or the ISR load: say so in the report
  (the user checks by eye). Do not lower the pixel clock without saying so.

## Frame budget
30 fps = 33 ms a frame. Baseline 2026-10-28 (`baseline`): **16.0 fps**, render 38.4 ms (cores h 38.8 / m 33.6; the
bounce refill ISR runs on core 0 with the hours render), push 18.8 ms serial on core 1 after both renders, physics
3.1 steps × ~1 ms, rest 1.0 ms. Stage costs (ms off the render): digits 12.5, surfaceBand 5.0, contactAngle=90 4.0,
ticksH 3.0, fizz 2.7, traces 2.3, ticksM 0.5, edgeGlow 0.3; lens / glass / transparency ~0 (spread ±1–2 ms).

## Steps (sequential; each = one subagent: implement, measure, report; then review)
1. **Balance the push.** Each core turns its own strip into the framebuffer right after rendering it (the worker on
   core 0 pushes hours), or the push is split by columns between the cores; strips double-buffered if that lets a push
   overlap the next render. Measure against PSRAM saturation (both cores pushing at once once cost more).
2. **Push kernel.** The quarter-turn loop: 2 lines per pass with 32-bit loads, 8×8 block transpose (PIE SIMD
   `EE.*`), write-allocate avoidance (full 64-B lines), skipping columns unchanged since the last push.
3. **Digits** (~12 ms): fewer PSRAM read-modify-writes per glyph pixel; coarse options (glyph composited against the
   row's liquid colour instead of the pixel behind; digit planes per row band) only with a look report.
4. **Ticks:** bake their contrast floor like the digits' (`bakeFloor`), integer kernels like the digit runs.
5. **Fizz** (~5 ms at 120 bubbles): pre-rendered discs per quantised size / depth, span kernels.
6. **Meniscus band, residue, glass, glow:** per stage, profile first; LUTs / linear approximations for per-pixel math.
7. **Tiled render** (if still short): render each tube in internal-RAM tiles and copy out, so the passes over a strip
   stop missing the cache.

## Log
(each step appends: what changed, bench line before / after, stage table if taken, parity, look change yes / no)
- **Step 1, balance the push (2026-10-28): 16.0 → 18.1 fps.** Staggered push (`main.cpp` renderBoth / renderWorker):
  core 0 renders hours, then pushes it; core 1 first pushes the *previous frame's* minutes strip (the LCD strips are
  reused, so it still holds that frame), then renders minutes. Each push runs next to the other core's render, never
  next to the other push. `display.h` `display_push_any_core` (LCD framebuffer push true; AMOLED and `LCD_SCAN 1`
  false = the old order: the loop pushes both after both renders; AB_COMPARE builds keep it too); `turn_rows` scratch
  `srcOff[2][320]` per core (static, 2.5 KB internal). msync stays at the end of each push. AMOLED builds, RAM 88360 B.
  - before `baseline`: fps 16.0, render 38.42 ms, cores h 38.76 / m 33.61, push 18.80 ms serial on core 1.
  - after `step1 stagger`: fps 18.1, render 51.86 ms (now the concurrent section *with* both pushes), cores h 38.96 /
    m 32.39, push 30.49 ms (both pushes summed, each overlapped with a render: ~15 ms each vs ~9.4 alone), frame-p95
    57 ms (was 64). Parity: `mismatched pixels: 170 of 118080 (0.14%), >12/255 off: 0`. No pixel change.
  - Variants measured (runs 1 unless noted; `PUSH_SHARE` experiment switch, removed): each core pushes its own strip
    after its render, the core done first helping with the other strip by 41-line column parts — **15.2** (runs 2;
    push summed 52.8 ms); both strips split by column parts between the cores after both renders — **15.8** (runs 2;
    both cores ~24 ms for what one does in 18.8); the parts on core 1 alone — 16.3 (push 20.6: the split itself costs
    ~nothing); own strip each, one push at a time (lock) — 16.6; stagger — 17.7; stagger + core 1 helping with the
    hours parts — 16.4; stagger with the bounce ISR on core 1 (`LCD_ISR_CORE=1`) — 16.9 (cores h 30.4 / m 33.1:
    core 1 becomes the long one). Two pushes at once are always slower than serial: the push is bound by PSRAM
    traffic (the old note holds), so pushes only gain where they overlap a render.
  - ISR placement unchanged (`LCD_ISR_CORE` 0). PSRAM traffic per frame unchanged, but it is now concurrent: a push
    runs while the other core renders, during most of the frame. Behaviour change: the minutes tube is shown one
    frame (~55 ms) after the hours tube. **User: check by eye for tearing / sideways jumps, and whether the minutes
    tube lagging the hours one shows on a fast tilt.**
