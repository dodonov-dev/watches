# LCD-3.16 native: 30+ fps on the user preset

Goal: `firmware/bench/user-fav.json` (the user's favourite look) at the native 820×320 canvas, pinned bench, **≥ 30 fps**.
Native stays: lower canvases were compared side by side on the board and look worse.

## Resume here (state 2026-10-30, branch `backup/local-worktree-20261028`)
- **Done:** step 1 (Log below), its fix for the twitch / latched sideways shift the user saw (Log, "Step 1 fix";
  user: looks good, 2026-10-29), and an automatic check for it: the panel refill monitor (Measuring). Same-day bench
  of step 1 was 16.6 fps (the 18.1 of 2026-10-28 did not reproduce on 2026-10-29), the fix 16.6.
- **Done:** step 2 (push kernel, Log): 17.3 → 21.0 fps pinned, 14.1 → 15.1 swinging the tilt; reviewed, plus a rolling
  refresh against hash collisions. The one-frame lag of the minutes tube is fine by the user
  (fast tilt), and a bigger gap between the tubes is acceptable if a step needs it (e.g. double-buffered strips).
- **Done:** step 3 (digits, Log), 2026-10-29: exact, digit stage 14.9 → 7.7–9.0 ms of the render; final build, same
  session A/B: 21.9 → 23.6 fps pinned, 15.9 → 16.8 swinging the tilt (SIMD build, another session: 21.6 → 24.2);
  reviewed.
- **Done:** step 4 (ticks, Log), 2026-10-29: exact, the hours tick layer ~3.8 → ~1.5 ms pinned (swinging, profiled:
  7.5–8.2 → 2.1–2.5); same-session A/B on a fixed pinned scene: 25.9 → 27.0 fps pinned, 17.1 → 18.1 swinging the
  tilt. Tick kernels in IRAM on the LCD (4.1 KB internal RAM). Reviewed. The board was
  being moved during step 4: benches now fix the scene first (Log, "Pinned scene"); that scene (tilt 0, slug home)
  benches ~2 fps kinder than the earlier pinned ones, so compare steps within one scene and keep quoting swinging.
- **Done:** step 5 (fizz, Log), 2026-10-29: exact (pixels identical, stepFizz bit-identical given the same draws; the
  LCD's draws now come from a seeded xorshift instead of the throttled hardware RNG). Fizz render on the hours core
  2.28 → ~1.2 ms pinned, stepFizz 0.55 → 0.17 ms a step; same-session A/B on the fixed scene 25.8 → 26.7 fps pinned,
  18.1 → 19.9 swinging the tilt. ~16 KB of fizz code in IRAM on the LCD (free heap with BLE 47.4 → 32.4 KB).
- **Done:** step 6 (tube body, Log), 2026-10-30: exact (no look change). The base stages run in 8-row bands (the strip
  stays cached), residue / palette / blur memos and LUTs, SIMD ramps, ~22.7 KB of tube code in IRAM. Same-session A/B
  on the fixed scene: 26.4 → 33.5 fps pinned, 19.6 → 25.0 swinging the tilt; cores h 30.1 → 22.0 / m 25.8 → 17.5 ms.
  Free heap with BLE 32.3 → 8.5 KB (BLE initialises; a BLE connection at that heap was not tested).
  Reviewed (2026-10-30).
- **Done:** step 7 (tiled render, Log), 2026-10-30: exact (no look change). The base stages render 4-row tiles in
  internal RAM, copied to the PSRAM strip by GDMA; the push reads the strip by GDMA too (gathered units in the tube's
  tile slots). Same-session A/B on the fixed scene: 33.6 → 40.5 fps pinned, **25.2 → 31.5 swinging the tilt** (goal
  ≥ 30 met); push both strips 20.8 → 12.7 ms swinging. Free heap with BLE 8.8 → 4.4 KB. Reviewed (2026-10-30). **Next:** a BLE connection test at this heap (`ble-session.py`
  needs `bleak` on the Windows Python); the look-
  change step 8 (simpler digits) is parked; further perf levers in KAIZEN (step 7).
- **Frame budget now** (step 7, wide, TUBE_PROF + PUSH_PROF): pinned ~24 ms a frame = hours core ~19.2 (digits 9.4,
  ticks 1.9, body + ramps 1.6, fizz 1.2, tile copies 2.4 of which ~2.1 waiting for the DMA, 3e band 0.9, back 0.7,
  residue 0.75, bounds 0.2) then its push ~4.8 (both 9.6), physics 1.2 × 0.48, rest 0.06. Swinging ~31 ms: hours
  core ~22.3 (digits 8.5, fizz 2.9, residue 2.9, ticks 2.0, body 1.7, tile 1.4, band 1.2, back 0.75) then its push
  ~5.2 (hash 1.4, store 2.6 = fbuf line traffic of ~450 changed segments, gather wait 1.2), minutes push ~6.0 (gather
  wait 2.2–2.8: it runs next to the hours tile copies) + minutes core ~21, physics ~1.55 × 1.1.
- **Detour, narrow tubes (2026-10-29, Log):** at the user's request the LCD now draws the tubes and everything in them
  at the AMOLED's physical size (49 px wide instead of 72, still the full length): pinned 21.5 → 34.5–36.8 fps,
  swinging the tilt 15.5 → 25.4–25.8. The wide tubes are `LCD_FILL=1` (board tag `lcd316@320f`). User: narrow looks
  good, but **neither is the default look**: depending on the results and the lenses (6 and 8 mm acrylic) the user
  may use either or both, so both stay working. **Bench only the wide tubes** (`--define LCD_FILL=1`, pinned + swinging
  tilt): narrow is known to be fast enough. Host parity covers both (`--res 320f` and `--res 320`).
- The pinned bench now flatters a still scene: the push skips what did not change (~85 % of it pinned, 35–50 % while
  tilting). Quote the swinging-tilt numbers next to the pinned ones from here on.
- **Way of working the user asked for:** each step = one subagent (Opus), strictly one after another (one board);
  the main session reviews, relays look changes to the user and asks for a by-eye check (one change per round, wait
  for the answer — no unattended timed tests). Goal native ≥ 30 fps; lower canvases were rejected after an A/B look.
  Each step's brief names its concrete levers, what earlier steps showed pays or not, and the dead ends.
- **Agent memory:** `docs/agent-memory/` is a copy of the main session's notes (board tooling, parity, firmware
  memory rules, pitfalls). On a new machine copy them into the Claude Code project memory dir
  (`~/.claude/projects/<project path with / as ->/memory/`) or point the session at them.
- **New machine setup:** PlatformIO (pioarduino platform, see `firmware/platformio.ini`); build `amoled191` once so
  `~/.platformio/packages` exists — the first `lcd316` flash then copies it to `~/.platformio/packages-lcd316` and
  recompiles the Arduino libs with the 64 KB data cache (~7 min, `tools/pkgdir.sh`). `cd sim && npm install` for the
  parity tools. The board's port differs per machine: `LW_PORT=COMx` (Windows side via WSL, `tools/device.py` bridges
  through `python.exe` + pyserial) or `/dev/ttyACMx`; `python3 firmware/tools/device.py --port <port> v` must answer
  `board lcd316@320 canvas 820x320 panel 820x320`. On native Windows (no WSL) the bash tools need Git Bash or
  adapting; `device.py` itself works on Linux and through WSL only.
- **Board state:** flashed with the step 7 final wide build (`--define LCD_FILL=1`); NVS `inputGain` 1, tilt from the
  IMU (`g`), checked after the step 7 runs (clock pinned at 10:09:30, demo `d0`). NVS holds the user's preset; benches pin
  `firmware/bench/user-fav.json` and restore params afterwards (clock stays pinned until "send sim time").

## Rules (every step)
- Repo rules: `CLAUDE.md` (no lazy allocation; side ideas → `KAIZEN.md`, laconic). Commit only when the user asks (steps 1–7 committed 2026-10-30).
- Firmware memory: every buffer static or allocated once at boot; per-frame scratch belongs to its `Tube` (two cores
  render at once: hours core 0, minutes core 1), never file-static.
- Sim ↔ firmware parity: a step either keeps the AMOLED render byte-identical (`firmware/tools/check_render_frames.py
  --reference <render.cpp before the step> --tolerance 0`) or changes the look on purpose, mirrored in
  `sim/src/render.ts` / `physics.ts`, with host parity no worse (`firmware/tools/check_board_render.py --board amoled191`
  and `--res 320f` / `--res 320`, `cd sim && npm run -s check:meniscus`) and board parity `>12/255 off: 0` on the user
  preset.
  A look change is reported as such (what changes, where to look): the user judges it on the board.
- Coarser params, pre-baked tables, approximations (linear / LUT instead of `powf`, `sqrtf`, `expf` …), inline
  assembly / the S3's PIE SIMD, renderer restructuring, library / sdkconfig changes: all allowed when measured.
  Xtensa notes: `fminf`/`floorf`/`/`/`sqrtf` are library calls (use `fmn`/`fmx`/`ffloor`/`fceil`, reciprocals); per-
  pixel inline loops spill (extract `noinline` kernels). Profile which bound a stage hits before choosing levers: the
  push was PSRAM-bound (fewer bytes / lines won, instruction cuts ~0), the digits compute-bound (~1.5–2 cycles an
  instruction even cached; fewer instructions and PIE won, locality ≤ 10 %). Divisions, IRAM placement and a
  cross-frame per-texel memo measured ~0 (2026-10-27).
- AMOLED (`amoled191`) must keep building and stay within its internal RAM (`pio run -e amoled191` RAM ≤ 88.4 KB).
- LCD internal RAM (user, 2026-10-29): no floor on the free heap; hot kernels go to IRAM whenever measured to pay (report
  bytes + free heap with BLE). If BLE later runs short, a separate memory pass may give it dynamic space or share RAM
  between things that never run at once.

## Measuring (board: Waveshare ESP32-S3-LCD-3.16 on Windows COM11)
```
cd firmware
LW_PORT=COM11 tools/e2e.sh --env lcd316 --define LCD_FILL=1 --preset bench/user-fav.json --runs 2 --label "<step>"   # flash + bench + parity
LW_PORT=COM11 tools/e2e.sh --env lcd316 --define LCD_FILL=1 --no-flash --stages --preset bench/user-fav.json --label "<step>"
python3 tools/swing.py COM11 40 '-1,0>0.6,0@3'   # swinging tilt, 16 `f` windows (after a bench: clock pinned)
```
- The pinned free hours slug stays where the boot pose slid it (±2 ms render between poses). When the board may have
  moved, fix the scene after the flash, then bench (step 4; the `g 0 0` override reads as a dead IMU):
  `python3 tools/device.py --port COM11 pinputGain=1 'g -0.5 0'` (4 s: slug home), `… 'g 0 0'` (4 s: tilt state 0),
  `python3 tools/bench.py --port COM11 --allow-dead-imu --runs 2 --preset bench/user-fav.json [--stages …]`, swing.py.
- lcd316 builds from `~/.platformio/packages-lcd316` (recompiled libs); `tools/flash.sh` / `e2e.sh` handle it. A bare
  `pio run -e lcd316` is refused; for a compile check: `ENV=lcd316 . tools/pkgdir.sh; ~/.platformio/penv/bin/pio run -e lcd316`.
- `-DDIGIT_PROF` (`--define DIGIT_PROF`) prints per-tube digit counters and cycle splits in `f` (`tools/device.py --port COM11 f`).
- `-DTUBE_PROF` prints per-tube drawTube stage cycles in `f` (`tube-prof`, per frame: palette, back, residue prep / rows
  (fill, shear, zone), backing, body (ramp), 3a–4, 3e band (kernel), bounds, labels, rear ticks / digits, fizz, top).
  `-DTUBE_VERIFY` (LCD) runs the step-5 code of the step-6 float paths next to the new and prints `tube-verify … bad`.
  With the tiles (step 7) it adds `tile` (the tile copies' share of the render) and a `tile-prof` line per tube: us a
  frame in tile_begin (cache drop), waiting in tile_put / tile_end, put set-up, waiting in the push's gathers.
- `-DPUSH_PROF` (LCD) prints `push-prof` per strip slot in `f`: us a push hashing, storing, waiting for the gather; changed
  segments. `-DTILE_VERIFY` (LCD) renders every frame's base stages a second time the step-6 way (into a PSRAM strip) and
  compares with what the tiles left: `tile-verify bad B of N px`; `-DPUSH_VERIFY` checks the gathered push as before.
  `-DTILE_OFF`: the strip path of step 6 (no tiles, CPU push). Host: `check_render_frames.py --tiles` builds the current
  side with the tiled band loop (memcpy sink).
- `-DTICK_PROF` prints per-tube tick costs in `f` (`tick-prof`, per-frame averages since the last `f`): the layer, its
  row facts, row ranges, tickRow calls (memo fills, per-pixel pixels), row counts by kind, fills, segments.
- `f` line: render = wall time of both cores' renders, `cores h / m` = each core's render, push = the quarter-turn of both
  strips into the PSRAM framebuffer (staggered: each next to the other core's render, step 1), rest = loop outside the face.
- The bench pins the clock (`t 10:09:30`, `d0`): nothing to undo. If the Windows bridge holds the port ("Access is
  denied", "bridge did not exit"), wait a few seconds and rerun the step that failed.
- Panel refill monitor: the LCD twitches when a bounce-buffer refill (ISR, core `LCD_ISR_CORE`) misses its deadline
  (PSRAM contention, interrupts held off). `bench.py` / `e2e.sh` print `panel refills: OK|TWITCH late N restarts M
  over S s (worst refill P% of its deadline)` over the base samples; `f` ends with `refill late N restarts M worst P%`
  (totals since boot, worst per 2 s window). Every step must stay OK and report the worst %; a by-eye check is only
  needed for look changes. It times each refill in 8 parts against the DMA's read schedule (display_lcd316.cpp);
  checked 2026-10-29 with 3 ms of interrupts off on core 0 per frame: ~1 restart a frame, worst 358%. Do not lower
  the pixel clock without saying so.

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
8. **Parked (user, 2026-10-29): simpler digits.** Likely the biggest lever left, but a look change: needs a side-by-
   side comparison on the board (like the canvas A/B, `AB_COMPARE`) before anything is chosen. After steps 4–7.
   Hours digits after step 3 (~9.7 ms of the core's ~34): run kernels ~6.4 (most px take the fractional-shift taps),
   per-glyph-row bookkeeping ~1.5, meniscus ramp columns ~0.9, band px ~0.65. Candidates: whole-px parallax (no
   fractional taps), glyph composited against the row's liquid colour (no read of the pixel behind), digit planes per
   row band, each column the dry or the wet copy under the meniscus (no ramp), no band compositor on digits.

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
- **Step 1 fix, twitch / sideways shift (2026-10-29).** User on step 1: twitches, and the face latched shifted sideways
  (liquid at the right end showing at the left, an empty gap at the left end). Cause, from the IDF 5.5 sources: with
  the Arduino default `CONFIG_LCD_RGB_RESTART_IN_VSYNC=y` the RGB driver never resets its bounce-buffer EOF count, so
  one EOF the refill ISR misses makes it refill the wrong buffer for good (one time in two): the face shifts by 41
  columns, wrapped, and the buffer being scanned is overwritten (twitching). Trigger measured with the monitor below:
  an NVS save (any param change) held the refill ISR off ~14 ms once (worst 1375%: +1 restart, +4 late refills).
  Changes: `CONFIG_LCD_RGB_RESTART_IN_VSYNC=n` in the lcd316 `custom_sdkconfig` (IDF default: restart at VSYNC only
  after a missed EOF, one bad frame); no `esp_cache_msync` after a push when `FB_BOUNCE_LINES` > 0 (the ISR copies
  fbuf through the shared data cache; the msync ran with interrupts off on the refill ISR's core: not the trigger —
  3 min with it back, 0 events — but worst refill 46% with it vs ~25% without).
  - Same-day A/B (`--ref HEAD`, runs 2): step 1 fps 16.6, render 55.17 ms, cores h 42.06 / m 32.11, push 30.02;
    fix fps 16.6, render 55.63 ms, cores h 41.85 / m 32.16, push 29.53. Parity `180 of 118080, >12/255 off: 0`.
  - No pixel change. PSRAM traffic: dirty fbuf lines are now written back on eviction instead of by the msync.
- **Panel refill monitor (2026-10-29).** fbuf is now ours (`no_fb`), refilled by our `on_bounce_empty` callback (the
  driver's copy + cache preload), timed per part; see Measuring. Bench with it (tilt moved since the A/B, not
  comparable to it): fps 17.8, `panel refills: OK late 0 restarts 0 over 82 s (worst 22%)`, parity `151 of 118080,
  >12/255 off: 0`. 3 min with the msync back: OK, worst 46%. AMOLED RAM 88368 B.
- **Review (GPT-6.1 Sol, 2026-10-29)** of step 1 + the fix + the monitor: nothing in step 1 or the fix. Monitor, both
  fixed: the worst-% snapshot / reset raced the ISR's max (now under a portMUX); the last two refills of a frame are
  read after the vertical blanking, so their deadline was ~1.9 ms too strict (possible false TWITCH). After: `panel
  refills: OK late 0 restarts 0 over 40 s (worst 25%)`, fps 17.9.
- **Step 2, push kernel (2026-10-29): 17.3 → 21.0 fps** (pinned; same-day baseline, board not moved; swinging the
  tilt 14.1 → 15.1). `display_lcd316.cpp` `turn_segs`: a strip push at native touches only what changed since the last
  push to the same rows. Per pair of scan lines and per fbuf cache line (32 face rows; scan lines are 640 B apart, so
  lines start at b % 32 == 0) a 32-bit hash of the strip words that went there, in a `PushSlot` per tube strip
  (2 × 8.2 KB internal .bss); an unchanged segment is neither read nor written, in a changed one only the 32-bit words
  that differ are stored (a line without a change stays clean: no writeback). One 32-bit load of a strip row = canvas
  columns a, a + 1 = both scan lines of the pair (bswap per 16-bit lane). Any other fbuf write (whole-frame push, A/B
  canvas) drops the overlapping slot; overlapping tubes (`hoursY` / `minutesY` close) are never tracked, always pushed
  in full. Scaled canvases, USB_LEFT 0, whole-frame pushes keep the per-pixel loop. Inner loops spill-free (objdump).
  - before `step2 baseline`: fps 17.3, render 53.94 ms (runs 52.06–55.81), cores h 39.09 / m 31.59, push 30.01 ms,
    frame-p95 57. `panel refills: OK late 0 restarts 0 over 17 s (worst 22%)`. Parity `104 of 118080, >12/255 off: 0`.
  - after `step2 final3`: fps 21.0, render 44.08 ms (runs 41.77–46.38), cores h 37.34 / m 31.62, push 13.11 ms (both
    strips, ~6.5 each), frame-p95 47. `panel refills: OK late 0 restarts 0 over 17 s (worst 22%)`. Parity `188 of
    118080 (0.16%), >12/255 off: 0`. Earlier builds of the kernel (`final` before the slot hardening, `final2` slots
    in .data): 21.3 / 21.1 fps, parity 160 / 129 px, >12/255 off: 0.
  - Variants (runs 2, no parity; `PUSH_KERNEL` experiment switch, removed): old loop 17.3 (push 29.93); line pairs with
    32-bit loads, plain stores 17.4 (28.08: ~45 % fewer instructions, ~nothing gained: memory-bound); + store changed
    words only 18.6 (25.35); + one hash per line pair, skip unchanged pairs 21.0 (12.95); + per-cache-line segments
    (kept) 21.2 (12.74). Not built: the 8×8 block / PIE transpose (the loop already keeps each strip line hot over its
    16 line pairs; SIMD would only cut instructions, see the pairs result); write-allocate avoidance: the S3 cache has
    no documented allocate-without-fill (ROM `Cache_Occupy_Addr` undocumented, not tried; GDMA idea in KAIZEN).
  - Motion (`g` swing −1,0 ↔ 0.6,0, 3 s period, 40 s, 16 `f` windows after a bench; a scratch tilt.py variant that
    prints push / refills): old loop 14.1 fps, push 26.80; kept kernel 14.9 / 19.95, final2 15.1 / 20.05, final3
    15.1 / 20.47. Renders dominate there (cores h ~50 / m ~42).
  - PUSH_VERIFY (`-DPUSH_VERIFY`, off by default; `f` appends `push-verify bad B of N px  stored  skipped …`): every
    push re-read against the old per-pixel formula. Final code: **0 of 185,398,720 px** over the pinned bench, a 30 s
    pitch swing, a 30 s sideways swing and 12 s with `minutesY` 30 (tubes overlapping), restored to 185. Pinned: 85 %
    of segments skipped, 4.2 % of words stored; swinging: 35–51 % skipped, 25–36 % stored; overlapping: none skipped.
  - Exactness: the hash (xor-multiply-xorshift) is a bijection per word, so any single changed word is caught; two or
    more collide with odds ~2^-32 per changed segment. Swinging (~1500 changed segments a frame at 15 fps) that is one
    stale segment (2 scan lines × ≤ 32 px) per ~50 h of continuous motion, until it changes again.
  - PSRAM traffic per strip push (72 rows = 3 cache lines a scan line): before ~157 KB fbuf fill reads + ~157 KB
    writebacks + ~118 KB strip reads; pinned now ~15 % of the fill reads, writebacks only for the 4 % stored words, the
    strip read unchanged (now the bulk). Refill ISR: same worst (~22 %), never late in any window or in the motion runs.
    The since-boot totals in the bench's last `f` vary by run (baseline, old loop, changed-words-only, hash per pair:
    0 / 0; pairs only 9 late / 1 restart; the kept kernel 0–15 / 0–3 over 7 boots): they come from the NVS saves of
    the bench's first param pinning after a boot (replayed on the final build: the first bench +6 / +1, a second none;
    one param change +3 / +1, worst 1336 %).
  - AMOLED builds, RAM 88368 B. lcd316 static RAM +18,984 B internal (slots 16,416 + per-core word buffer 2,560), heap
    51.7 KB free with BLE up. No look change (pixels identical: PUSH_VERIFY, parity).
  - Review (main session, 2026-10-29): kernel, slots, word alignment and edge rows (16-bit stores: the cores never
    share a word), lens-map hashing and the other fbuf writers (all through `turn_rows`, which drops overlapping slots)
    checked. Added: `SKIP_REFRESH` 64, every push compares one line pair in 64 against fbuf whatever its hashes say, so
    a collision cannot leave a stale patch on a still face for more than ~3 s. Same session, board not moved: as
    delivered fps 21.1 (push 12.59 ms), with the refresh 21.0 (push 13.17); `panel refills: OK` (worst 22%) both;
    PUSH_VERIFY with the refresh `bad 0 of 77066880 px`; parity `198 of 118080, >12/255 off: 2` once, `169, off: 0` on
    a rerun (the meniscus swing class: the `x` dump does not go through the push).
- **Detour: tubes at the AMOLED's physical width (2026-10-29).** User: tubes and everything inside narrower, as on the
  smaller board in physical size, full length. `spec/layout.h|ts`: on the LCD, PX_SCALE (canvas px per design px) is
  the pitch ratio 0.083 / 0.0912 mm (830/912 × RENDER_H / 320 = 0.910 at native) instead of the canvas height (4/3), so
  every px param (tube width, glass, digits, ticks, bubbles, meniscus, slosh gains) shrinks to the AMOLED's size in mm;
  the tubes keep the panel's full length. `boardParams` (physics.h / params.ts, float32 alike) then maps hoursY /
  minutesY over the room a tube can move in (canvas rows minus its height), so the tubes stay at the face's edges:
  user preset 54-px design tubes → 49 px at rows 0 and 270 (was 72 at 0 and 247). MM_PER_PX = the real pitch.
  TUBE_HEIGHT_MAX follows PX_SCALE (107 → 73 rows: strips, Tube rows tables, push hash slots; lcd316 static RAM
  128,136 → 113,840 B). The old scale stays as `-DLCD_FILL=1` (`v` / sim `?res=320f` / LW_RES=320f /
  `check_board_render.py --res 320f`). AMOLED untouched (88,368 B).
  - Host parity (`check_board_render.py`, 77 presets): physical 73 within 12/255 (4 presets 1 px, worst 25); fill 72
    (5 presets 1–2 px, worst 57; the known meniscus class). Board parity, physical: `203 of 80360, >12/255 off: 1`.
  - Same session, board not moved (runs 2; motion = `g` swing −1,0 ↔ 0.6,0, 3 s period, 40 s, 16 windows):
    narrow: fps 36.8 (render 24.87 ms, cores h 20.99 / m 17.40, push 7.43, frame-p95 28), motion 25.8 (push 11.05);
    wide (`LCD_FILL=1`): fps 21.5 (render 43.42, cores h 36.85 / m 31.42, push 13.18, p95 46), motion 15.5 (push
    21.19); narrow again: 34.5, motion 25.4. Panel refills OK in all (worst 19–22 %; motion windows never late).
  - Look change, on purpose: tubes ~32 % narrower with everything inside, more black between them.
- **Step 3, digits (2026-10-29): digit stage 14.9 → 7.7–9.0 ms of the render; final build, same-session A/B: 21.9 →
  23.6 fps pinned, 15.9 → 16.8 swinging** (the SIMD build in another session: 21.6 → 24.2 / 15.9 → 16.7; see Final).
  Exact: no look change. `render.cpp` (sprite digit path), `main.cpp` / `render.h` (`-DDIGIT_VERIFY` print, boot
  message).
  - Profile (hours tube, pinned, `-DDIGIT_PROF`; 13 glyphs, 559 glyph rows, 994 integer + 8,744 fractional-shift px,
    637 runs, 232 band px): rear digits 12.7–13.2 ms of the core's ~37 = run kernels 9.2–9.6 (~0.97 µs a px), ramp
    columns ~0.9, band pixels ~0.65, per-glyph-row bookkeeping ~1.8. Minutes 8.6–12.9 ms (its free slug drifts at
    inputGain 0, so its mix of integer / fractional px changes from window to window).
  - Where the time goes: **compute, not PSRAM** (unlike the push). Throwaway probes: each kernel run redrawn at once
    (all cached) costs 85–89 % of its first draw, each glyph 92 %, the whole pass ~95 % (warm or after evicting the
    data cache); lane table in internal RAM: no change. The core runs ~1.5–2 cycles an instruction even on cached code
    (probe: dependent add 1.8 incl. loop, mull 2.2–2.4, load-use 2.2 internal / 2.5 PSRAM-cached), and the hours core
    also serves the refill ISR (~15–20 % slower per px than core 1). The 2026-10-27 "PSRAM-bound" note was the
    32 KB / 32-B cache. So the coordinator's locality levers (row-band order, fewer arrays) can reach ~10 % at most:
    not tried (KAIZEN).
  - What changed: (1) scalar blend on byte lanes: a 565 colour → r | g << 8 | b << 16 from a byte-indexed table
    (EXP565, 2 KB PSRAM), the strip pixel read / written byte-swapped as it lies (blend 55 → ~43 instructions);
    (2) the fractional kernel's taps in their own pass (carried left taps, heaviest tap picked pairwise, colour by
    tap offset): it spilled every pixel in one loop; (3) per-row liquid interval + band footprints once per row for
    all glyphs (DigitRow, PSRAM) instead of per glyph row; one `seg` for all modes (the inlined copies made the row
    function ~17 KB, more than the 16 KB I-cache); (4) **SIMD blend (PIE)** on the LCD: `pieBlend`, 8 strip px a
    step, blend565T exactly on 16-bit lanes, out = a + floor(2dT/256) − floor(dT/256) (= floor((dT+128)/256)), SAR 8,
    whole 16-B blocks of the strip row with T = 0 outside the run (a run whose blocks leave the row: scalar). PIE
    semantics probed on the board first (vmul = product >> SAR, floor, low 16 bits; vsr.32 arithmetic; vadds
    saturating). (5) FracMemo: a fractional run repeating the previous one's source row and columns reuses its taps
    (32 % of the hours wet rows under bottomLens 0.473); reset every frame (no cross-frame cache). AMOLED keeps the
    scalar path (`DIGIT_PIE` 0).
  - Variants, in order (pinned, user preset; profile = hours rear digits / run kernels):
    v5 scalar (1–3): 11.6–12.2 / 8.2–9.0 ms; bench (runs 2) 22.1 fps, render 42.25 ms (41.65–42.86), cores h 35.47 /
    m 29.41; swinging 16.2. Hot rerun of its kernels 83 %; fractional px 156–163 cycles on core 1, 173–197 on core 0.
    + lane table in internal RAM: no change (8.6–8.7 / 6.7–6.9 hot) — not kept.
    + SIMD blend (4): 9.6–10.0 / 6.2–6.6 ms (0.62 µs a px; minutes integer px 0.32 vs 0.56 µs); bench (runs 2) **24.2
    fps**, render 38.38 ms (36.72–40.03), cores h 31.38 / m 25.39, push 13.42, frame-p95 41; swinging **16.7** (push
    20.61); digit stage +7.70 ms (6.47–8.94, runs 2) vs +14.85 (13.80–15.89).
    + FracMemo (5), A/B in one boot (runtime switch, removed): hours run kernels 6.3–6.8 ms on vs 7.1–7.3 off; profile
    9.65–10.1 / 6.4–6.6 ms. Minutes, windows with a similar px mix: rear digits 7.3 vs 10.5 ms (9.7k int + 1.9k frac
    vs 9.3k + 2.4k px), 5.4 vs 8.6 ms (11.2k int vs 10.7k + 0.7k px).
    Final: the fractional kernel split into a SIMD and a scalar function (one frame holding both cost 1,264 B of the
    hours task's 4 KB stack: 744 B left; now 704 B frames, 1,000 B left in the verify build).
  - Baselines, board not moved within each (runs 2): 14:23 21.1 fps (render 44.16, cores h 37.16 / m 31.46, push
    13.32), swinging 15.2, stage +18.90 (runs 1); after the user re-plugged the board (pose changed, across −0.43 →
    −0.03), 15:05: **21.6 fps** (render 43.27, 41.29–45.26, cores h 36.78 / m 31.44, push 13.02, p95 47), swinging
    **15.9** (push 20.40), stage +14.85. The numbers above compare against the 15:05 one.
  - Exactness: `check_render_frames.py --tolerance 0` byte-identical after every change (9136 strips; scalar path, as
    the host builds have no PIE); on the board `-DDIGIT_VERIFY` (off by default; `f` prints `digit-verify bad B of N
    px`) checks every SIMD blend against the scalar one and every memo hit against recomputed taps: 0 bad of 21.8 M /
    33.3 M / 37.1 M / 35.6 M px (pinned + 30 s swinging, each build). Host parity unchanged: `--res 320f` 72 of 77
    within 12/255 (5 presets 1–2 px, worst 57), `--res 320` 73 of 77 (4 presets 1 px, worst 25); `check:meniscus`
    passed (339 scenes, max 9/255). Board parity (SIMD build) `157 of 118080 (0.13%), >12/255 off: 0` (baseline 153,
    0). Panel refills OK in every bench (worst 22 %), swinging windows never late (worst 22–25 %).
  - Memory: lcd316 static RAM +16 B (pointers); PSRAM, once at boot: EXP565 2 KB, DigitRow 3 KB and FracMemo ~0.6 KB
    a tube. Stack: SIMD lanes 576 B per kernel frame (see Final). AMOLED builds, RAM 88,384 B (+16).
  - Final (the board was off USB ~1 h after 15:55; re-plugged, tilt along +0.26 across −0.01; same session, each
    build benched right after its flash, runs 2): before **21.9 fps**, render 42.86 ms (41.06–44.65), cores h 36.75 /
    m 31.63, push 13.31, frame-p95 46; swinging (`tools/swing.py`, 40 s) **15.9** (push 20.41). Final **23.6 fps**,
    render 39.58 ms (38.53–40.62), cores h 33.77 / m 27.66, push 13.57, frame-p95 44; swinging **16.8** (push 20.47).
    Panel refills OK in both benches (worst 22 / 24 %), swinging windows never late (worst 23 %). Hours render task
    stack free 1,560 → 1,320 B. Digit stage on the final build +8.97 ms (6.96–10.98, runs 2; taken after the swinging
    run, its own base render 42.38 ms vs 39.58 right after the flash: the free slug had wandered at this pose).
  - Board parity, final: the e2e step `472 of 118080, >12/255 off: 1`; re-runs with the live IMU 765 / 209 and 111 / 0
    (at this pose the free hours slug had slid ~125 px: the moving-slug skew class, KAIZEN); pinned like the bench
    (inputGain 0, 10:09:30, d0, settled) `84 / 0` and `74 / 0`. Before (live, same session): 182 / 0.
  - NVS: the bench cut off at 15:55 had left `inputGain 0`; set back to 1 before the A/B (benches restore their own
    snapshot), NVS `inputGain 1` after all runs. Board left on the final wide build. Narrow-mode check dropped (user).
- **Step 4, ticks (2026-10-29): hours tick layer ~3.8 → ~1.5 ms pinned (profiled swinging 7.5–8.2 → 2.1–2.5); A/B
  on a fixed pinned scene: 25.9 → 27.0 fps pinned, 17.1 → 18.1 swinging.** Exact: no look change. `render.cpp`
  (drawTicks, tick kernels, markRowFacts), `main.cpp` / `render.h` (`-DTICK_PROF` print).
  - Profile (`-DTICK_PROF`, per frame, hours, pinned): drawTicks 3.7–4.1 ms uninstrumented (minutes 3.3, the stage
    table's 0.5 ms was stale): 318 tick rows, 1,590 Mark::operator() calls (1,400 behind liquid), ~575 cycles each:
    out-of-line operator, bandMark's footprint test on every pixel while the band is on (~94 cycles), wetColourT →
    throughLiquid, emboss, blend565T. The contrast floor branch was never taken (0 px), point() (sqrtf, division) 0.3 ms,
    ranges 0.08. Swinging: 7.5–8.2 ms instrumented (2,180 wet px, 520 antialiased edge px).
  - Bound: compute, plus one PSRAM line fill a row. A row drawn again at once costs 93 % of its first draw; the row's
    first strip load alone 1.1–1.5 µs (probe), its DigitRow 0.25–0.57 µs. And code placement: the 16 KB instruction
    cache is shared by both render cores, so the same kernel in IRAM took 1.5 → 0.86 ms (and one IRAM move shifted
    the whole render by ~2.5 ms in a profile build: benches of two builds carry a layout offset, KAIZEN).
  - What changed: (1) one call per tick row (`tickRow`): the row's facts (DigitRow: liquid interval, band footprints,
    computed once a frame for all rows, `markRowFacts`), a row wholly behind liquid or wholly not and clear of the band
    footprints and the strip's ends is written from (2) `TickMemo` (per row and kind in DigitRow): for the pixel behind
    (strip layout), the tick colour and the edge share fT, the five column classes' outputs (x - 1, x, interior, x + w,
    x + w + 1; plotF's edge columns take their two ops in order), so the next ticks' rows (same pixel behind, same fT)
    are a load, a compare and a store a pixel; pixels showing another pixel behind compute their own; other rows go
    pixel by pixel with the facts (`tickPx`), band-footprint pixels through Mark::operator(); (3) one call per segment
    (`tickSegment`), the lens depth from a per-frame table (DigitRow.depth, the same float expression); (4) the tick
    kernels in IRAM on the LCD (`TICK_IRAM`); (5) the rear digits reuse the rear ticks' row facts (`drawLabels`
    rowFacts), major-tick ranges skipped when no tick is major, DigitRow 64 B (one cache line a row, table aligned).
  - Variants (TICK_PROF, hours, instrumented): per-pixel closure kernel without memo: 3.9–4.4 ms uninstrumented, bench
    23.6 vs 23.5 fps: no gain. + row memo: rows 1.2–1.5, layer 2.1–2.7 (was 5.1). Segment function + depth table in
    flash: kernel 1.44–1.57 (layout), + IRAM 0.86, layer 1.54. Column memo: swinging layer 3.2–3.3 → 2.2–2.4. Final:
    pinned 1.51–1.57 (facts 0.21, ranges 0.05, rows 0.91–0.95 of which memo fills 0.24 = 66 × 3.6 µs, rest ~0.3);
    minutes 1.65–1.69; swinging hours 2.06–2.55 (fills 0.41–0.46), minutes 1.93–1.99. Remaining: ~one line fill a row
    (~0.4–0.5 ms a tube), facts 0.2, fills 0.25 (KAIZEN).
  - Not built: lever 5 (floor baked like the digits', a look change): the floor maths now runs only on memo fills;
    pieBlend: rows are 3–6 px.
  - Pinned scene: the board was picked up / moved between benches (along −0.83 … +0.40; the pinned free hours slug sat
    at slugPos 0 or ~126 px depending on the boot pose: ±2 ms render). The A/B therefore fixes it before pinning:
    `g -0.5 0` 4 s (slug home), `g 0 0` 4 s (tilt state 0; the override reads as a dead IMU: `--allow-dead-imu`), then
    bench.py `--runs 2` and `tools/swing.py` (scratch `ab.sh`; KAIZEN). With the tilt state 0 every pinned tick row is
    a plot row; the swinging run covers the parallax / antialiased rows.
  - Same session, back to back (19:02 / 19:05, flash → fixed scene → bench → swing), before → final: fps 25.9 → 27.0,
    render 36.65 (36.50–36.80) → 35.20 (35.06–35.34) ms, cores h 31.02 → 29.55 / m 25.91 → 24.51, push 13.89 → 13.94,
    frame-p95 41 → 39; swinging 17.1 → 18.1 (push 20.64 → 20.52). Stage costs (runs 2): ticksH +1.35 (1.12–1.59) →
    +0.69 (0.48–0.90), ticksM +0.54 (0.42–0.67) → −0.23 (−0.39 – −0.08: below the noise; core 1 is not the long one).
    An earlier A/B (18:52, same prep): before 24.2 fps (render 39.38, cores 33.98 / 29.40), kernels in flash 24.7
    (38.48, 32.84 / 28.49), in IRAM 25.2 (37.66, 32.18 / 27.98); swinging 17.4 / 17.9 / 18.1.
  - Unfixed scene (e2e.sh): baseline 17:53 (board flat) 23.5 fps, render 39.69 (38.58–40.79), cores h 33.71 / m 27.51,
    push 13.52, p95 43; swinging 16.9 (push 20.74); stages (not right after a flash) ticksH +2.67, ticksM +3.06. Final
    19:08 (board being moved: along −0.37 across 0.54, gyro 18): 23.5 fps, render 38.81, cores h 32.99 / m 24.03 — not
    comparable.
  - Exactness: `check_render_frames.py --tolerance 0` byte-identical after every change (9136 strips); mutations of the
    footprint test, the op order, the memo key (fT, pixel behind) and the shared-facts flag each fail it (a memo keyed
    without the tick colour passes: minor and major ticks share a colour in its scenes, KAIZEN). The LCD runs the same
    C code (IRAM is placement only). Host parity unchanged: `--res 320f` 72 of 77, `--res 320` 73 of 77, `--board
    amoled191` 68 of 77. Board parity, final: e2e (live) `168 of 118080, >12/255 off: 0`; pinned (fixed scene, inputGain
    0, 10:09:30, d0) `57 of 118080, >12/255 off: 0`. Panel refills OK in every bench (worst 22–25 %), swinging never late.
  - Memory: AMOLED RAM 88,384 B (unchanged; kernels in flash there). lcd316 static RAM unchanged (128,152 wide /
    113,856 narrow); IRAM +4,144 B (tick kernels) → free heap with BLE 51.5 → 47.4 KB. DigitRow 28 → 64 B (PSRAM, once
    at boot, +63 B to align the table: 6.9 KB a tube). Hours render task stack free 1,308–1,320 B (was 1,320: the
    per-pixel tick path is one call deeper). No look change.
- **Step 5, fizz (2026-10-29): fizz render on the hours core 2.28 → ~1.2 ms pinned (swinging ~5.8 → ~4.6 ms with
  ~25 % more bubbles), stepFizz 0.55 → 0.17 ms a step pinned (1.08 → ~0.6 swinging); A/B on the fixed pinned scene:
  25.8 → 26.7 fps pinned, 18.1 → 19.9 swinging.** Exact: no look change. `render.cpp` (fizz kernels, drawBubble,
  stepFizz and helpers), `main.cpp` / `render.h` (`-DFIZZ_PROF` print).
  - Profile (`-DFIZZ_PROF`, off by default; `f` prints `fizz-prof h|m` per frame — cycles of step 5, per-bubble setup,
    per-row prep, discRow; bubbles, rows; `=2` adds pixel classes, `=3` a redraw-at-once cache probe — and
    `fizz-step` per step: all, frand, spring point, bubble loop, discFit, touchesFoam, merge, cadence, settleFoam;
    live / held / slots). Pinned, before: hours step 5 2.28 ms (setup 0.25, row prep 0.21, discRow 1.70) for ~18
    bubbles / 152 rows: 11 µs a row, 1,348 px visited a frame of which 708 outside the disc, 296 AA ring, 415 ring
    written, 224 core visited (54 written, pinpoint), 63 jumped. Minutes 1.30 ms. The redraw probe: 86 % (h) / 94 %
    (m) of the first draw: compute-bound. stepFizz 0.46 ms a step: rand 0.05 (esp_random), spring point 0.05,
    bubble loop 0.26 (discFit 0.12 at 35 calls / 250 rows, touchesFoam 0.05 scanning ~650 slots), cadence 0.03,
    settleFoam 0.07. Swinging: hours 5.8 ms (~48 bubbles), stepFizz 1.08 ms × 2.7 steps (rand 0.11, touchesFoam 0.23
    at 3,600 slots, settleFoam 0.27).
  - Where it went: (1) `sqrtApprox` / `rsqrtApprox` punned through `memcpy`, and the build has `-fno-builtin-memcpy`:
    two out-of-line calls a root. (2) The 16 KB I-cache shared with the other core's render (hours 25 % slower a row
    than from IRAM; minutes, rendering next to the hours push, unchanged). (3) ~100 cycles a visited pixel of tests and
    spills (~90 a ring root, ~130 a blend), half the visits outside the disc. (4) drawTube's inline per-bubble setup
    spilled. (5) Physics: `sqrtf` = wrapper + `__ieee754_sqrtf`, two windowed calls a disc row; the code cold in the
    I-cache after the renders (spring point 4 discFits 0.06 ms); `esp_random()` waits until ~22 µs passed since its
    last call (S3: 1778 APB cycles, a 45 kHz cap) and a step draws 5–15 times in bursts.
  - What changed (profile numbers pinned, hours, per frame unless noted):
    (a) bit-cast punning in the roots: discRow 1.70 → 1.52 ms. (b) Kernels and `discVeil` in IRAM (`FIZZ_IRAM`, LCD
    only): 9.9 → 7.4 µs a row (hours). (c) The per-bubble code out of drawTube as `Tube::drawBubble` (noinline, IRAM),
    per-tube constants in a `FizzFrame` (lxS stays a literal: `lxS * lxS` folds as before): setup 12.7 → 5.9 µs a
    bubble, row prep 1.35 → 0.93 µs a row; step 5 1.93 → 1.37 ms. (d) Kernel: a row visits only the chord (half-width
    `sqrtApprox(out2 - dy2)` + 0.01 px margin; pixels beyond it have d2 >= out2 for sure), clipped to the panel (x0 +
    step × ix, no per-pixel bounds test), minus up to two certainly-core spans that write nothing (margin 0.01 px
    instead of a whole pixel; on pinpoint rows minus the pinpoint's reach), pinpoint bubbles' rows out of the
    pinpoint's reach take the plain kernel, the rim colour's blend lanes once a row (`blend565L`, the same integers
    as blend565T), rows the disc misses skipped before their prep: visits 1,348 → 536 a frame (out 708 → 2), skipped
    63 → 196; discRow 59.5 → 45.8 µs a bubble. Probes after: AA roots ~13 %, blends ~16 % of discRow.
    (e) `sqrtExact`: the same sqrt0.s / maddn.s / divn.s sequence as `__ieee754_sqrtf`, inline (x >= 0 only: the
    wrapper adds nothing there): discFit, settleFoam, `up`, the core margin. (f) touchesFoam scans a candidate list
    (the foam on `side` at the loop's start plus each bubble that parks in it, in foamOrder, free until settleFoam;
    an OR over the same set, the same test per slot), settleFoam's slide pass over its parked list. (g) `discFitLow`:
    min over the disc's rows of side × surf − r(1 + 1e-6) bounds discFit from below (every rounded root ≤ that, rounding
    monotone), so a bubble far from the surface skips discFit: 35 → 4 calls a step. Together (d–g): stepFizz 0.45 →
    0.39 ms a step (fit 0.12 → 0.02, touch 0.045 → 0.012). (h) stepFizz, settleFoam, discFit, foamFront, touchesFoam
    in IRAM (births / respawns noinline in flash): 0.39 → 0.24 ms (spring point 0.06 → 0.01, settle 0.07 → 0.02).
    (i) LCD: the fizz draws from a xorshift32 per core (frand runs on core 1 in stepFizz and in both renders for
    scattered presets), seeded from esp_random in render_init: rand 0.12 → 0.002 ms a step, stepFizz 0.24 → 0.14 ms.
    Same uniform 24-bit draws; the hardware stream was never reproducible. AMOLED / host keep esp_random.
    Final profile pinned: hours step 5 1.19–1.29 ms (~19–20 bubbles: setup 0.10, row prep 0.12, discRow 0.89–0.96 at
    7.3 µs a row), minutes 0.87–0.91; stepFizz 0.14 ms a step (loop 0.07, settle 0.045, cadence 0.015, spring point
    0.011). Swinging (~68 / 41 bubbles): hours 4.6 ms, minutes 2.4, stepFizz 0.58 ms a step (settleFoam 0.29 at ~60
    parked, touchesFoam 0.08, loop 0.26).
  - Same session, back to back (fixed scene, bench runs 2, `swing.py` 40 s), step 4 → step 5: fps 25.8 → 26.7, render
    36.93 (36.91–36.95) → 36.33 (36.14–36.52) ms, cores h 31.53 → 30.11 / m 25.10 → 24.09, push 13.29 → 13.45, phys
    1.94 steps × (tube 0.29 + fizz 0.55 ms) → 1.84 × (0.23 + 0.17), frame-p95 40 → 39; swinging 18.1 → 19.9 (push
    21.04 → 21.15). An earlier A/B the same day (board re-plugged in between): 25.8 → 26.9, swinging 18.3 → 19.9.
    Stage cost `fizz=0` (runs 2): +0.14 (−0.48–0.75) → −0.15 (−0.76–0.45) ms: below the bench noise both times (the
    stage only drops the draw, stepFizz runs on), use the FIZZ_PROF cycles.
  - Exactness: `check_render_frames.py --tolerance 0` (and `--big-fizz`) byte-identical after every change; its
    scenes put all bubbles on one spot (constant esp_random stub, KAIZEN), so also an ad hoc host stepper (render.cpp +
    physics.cpp, LCG esp_random, 8 scenarios × 3,000 steps: spring / scattered / mirrored free slug / big bubbles /
    no glass / vertical, a tilt script; fizz state every step, strips every 2) old vs new: identical with
    `-ffp-contract=off`, with `-mfma -ffp-contract=fast`, and at the LCD's wide and narrow geometry; mutations of the
    chord margin, core skip, pinpoint reach, veil, panel clip, discFitLow and the candidate list each fail one of
    the two. On the board (FMA contraction, IRAM), a scratch verify build ran the step-4 fizz code first on each strip
    and the step-4 stepFizz with recorded draws, restored, ran the new code replaying the draws, compared strips and
    fizz state bitwise, and tested sqrtExact against libm sqrtf on 2 M inputs: 0 bad of 85.5 M px / 3,379 steps
    pinned + swinging, 0 of 147 M px / 6,000 steps with bubbleDark 1, scattered births, fizzSize 11; sqrt 0 of 2 M; a
    mutated build reported 40 k px / 21 steps bad (the check sees changes). Host parity unchanged (fizz off there):
    `--res 320f` 72 of 77, `--res 320` 73 of 77, `--board amoled191` 68 of 77. `check:meniscus` not rerun (band / veil
    maths untouched). Board parity, final, pinned: `65 of 118080, >12/255 off: 0`. Panel refills OK in every bench
    (worst 22–24 %).
  - Memory: AMOLED RAM 88,384 B (unchanged; fizz code in flash, esp_random kept). lcd316 static RAM 128,152 → 128,168 B
    (xorshift states); IRAM ~16 KB (kernels 4.8, drawBubble 2.2, stepFizz 4.4, settleFoam 2.3, the rest 0.7): free heap with BLE
    47.4 → 32.4 KB. Hours render task stack free 1,320 → 1,388–1,400 B (drawTube's frame lost the DiscRow). No
    allocation added.
  - Not built (KAIZEN): two pixels a step to overlap the root chains, cheaper conservative bounds, inline division for
    drawBubble's `__divsf3`, settleFoam's pack, physics on core 0; the look-change option (coverage sprites per radius
    and subpixel phase), since the pinned render left is ~1.2 ms of the hours core. No look change.
- **Step 6, tube body (2026-10-30): hours render 30.1 → 22.0 ms pinned (swinging 36.7 → 26.8); same-session A/B on the
  fixed scene: 26.4 → 33.5 fps pinned, 19.6 → 25.0 swinging.** Exact: no look change. `render.cpp` (drawTube's base
  stages, residue / ramp / band kernels, palette), `main.cpp` / `render.h` (`-DTUBE_PROF`, `-DTUBE_VERIFY` prints),
  `tools/check_render_frames.py` (`--tube-seq`), `tools/check_residue.py` (new traceFillRow signature).
  - Profile (`-DTUBE_PROF`, off by default; `f` prints `tube-prof h|m` per frame, cycles of each drawTube stage and of
    the palette build). Before, pinned, hours / minutes ms: all 31.7 / 26.5 = tube back fill 5.7 / 4.0, residue blur
    1.15 / 0.8, residue rows 1.9 / 1.5 (fill 1.3 / 1.2), nose backing 0.3, body + ramps 7.1 / 5.6, 3e band 1.8 / 1.3,
    bounds 0.25, rear ticks 2.2 / 1.5, rear digits 10.0 / 10.5, fizz 1.1 / 1.0; 3a / 3b / 3c / 4 ~0 (off or folded in
    the ramps in this preset). Swinging: hours all 34–36 (palette 1.0–1.9 on a moving light, back 5.6–6.0, residue rows
    2–3 (zone ~1–2.4), body 6.5–6.8, band 2.5); minutes residue rows 3.7–8.2 (fill 3.1–5.7: ~50 k px).
  - Bound: **memory for the fills, compute for the rest.** The back fill done a second time per row at once (lines
    cached) cost 0.53 / 0.29 ms against 5.7 / 4.3 first: ~2.4 us per strip line (fill + dirty-victim writeback). A second
    whole-strip pass missed again (118 KB strip > 64 KB cache): every stage that walked all rows (back, residue, body,
    band, mirror) refetched the strip. No hidden calls in the row kernels (objdump; the 3e setup's two `__divsf3` are
    ROM calls, ~5 us a row of setup was I-cache misses: see IRAM).
  - What changed (profile numbers pinned, hours, unless noted):
    (a) **Row bands:** the tube back, residue rows, nose backing, body + ramps, 3a / 3b / 3c / 4, 3e and the mirror /
    bounds run per band of `TUBE_BAND` 8 rows, stage order kept within each row (every one of them writes and reads only
    its own row; the edges, residue prep and wet share stay whole-tube): all 31.7 → 26.2 (body 7.1 → 2.7), bench 26.4 →
    28.7 / swinging 19.9 → 20.6. Band 16: body 5.2 (both cores' bands overflow the shared cache), band 4 ≈ 8.
    (b) Residue fill: the colour LUT covers every depth (was ≤ 48: grazing rows took the per-pixel colour), built once
    per row for both spans, then indexed by depthT's phi index i (T(i) non-decreasing, T > 0 from iZ on; guarded
    against 32-bit wrap): fill 1.5 → 0.32 (hours, before IRAM), minutes swinging 5–7 → 2.0. (c) Residue blur memo across
    frames (TraceMemo, PSRAM): a column is recomputed only if its ±4 window changed, a frame without any change keeps
    aLo / aHi; interior columns unclamped (same integers), the streak per column from a table built in render_init:
    blur 1.15 → 0.19 (minutes 0.07); swinging 0.8–1.2 → 0.6–0.75. (d) Ramps (trace mode) on the SIMD blend
    (`rampPieR/L`, LCD): T per pixel from the same alpha into lanes, pieBlend over whole blocks: 2.02 → 1.86; and an
    exact early stop: the alpha never rises along the walk (cov and glow monotone, also rounded), so the first T 0
    ends the run: → 1.65. (e) 3e: the band's per-row colours (inner, lens mix, rim, back luma) built with the palette
    (`buildBandRows`): band setup 0.9 → 0.77. (f) Palette: the light-independent library results (asinf, powf, expf,
    sqrtf, cosf) and row terms (wall glow, dryT, back gradient, body shading) cached per generation (PalCache, PSRAM):
    swinging 1.9 → 1.36 a rebuild. (g) Residue zone out of drawTube (`traceZoneRow`, noinline): no change (2.4
    swinging: compute, not spills); kept for the IRAM placement.
    (h) **IRAM (LCD, `TUBE_IRAM`)**: the row kernels + pieBlend + the 3e lambda (~10.2 KB): back to back 29.9 → 32.3 fps
    pinned, 21.4 → 23.9 swinging (hours: residue 1.2 → 0.8, body 2.6 → 2.1, band 1.64 → 1.05, and digits 10.6 → 9.8:
    the freed I-cache); free heap with BLE 32.4 → 22.5 KB. Then the band loop itself as an IRAM lambda (12.6 KB; it had
    gone through the I-cache from flash once per band): back to back 32.6 → 33.6 pinned, 23.9 → 24.9 swinging; heap
    21.3 → 8.8 KB. `-DTUBE_BAND_INLINE` gives the 12.6 KB back.
  - Same session, back to back (fixed scene, bench runs 2, `swing.py` 40 s; step 5 sources swapped in, then the final):
    | | step 5 | step 6 |
    |---|---|---|
    | fps pinned | 26.4 | **33.5** |
    | render ms (runs) | 36.79 (36.16–37.42) | 28.95 (28.63–29.27) |
    | cores h / m ms | 30.12 / 25.75 | 22.00 / 17.54 |
    | push ms | 14.64 | 14.76 |
    | phys | 1.89 × (0.30 + 0.10) | 1.47 × (0.34 + 0.11) |
    | frame-p95 ms | 39 | 31 |
    | swinging fps (push) | 19.6 (21.48) | **25.0** (21.16) |
    | swinging cores h / m (mean) | 36.7 / 32.7 | 26.8 / 23.8 |
    | refills (bench worst; swinging windows) | OK 25 %; never late, worst 22 % | OK 16 %; never late, worst 14 % |
    | free heap with BLE / hours stack free | 32,280 / 1,388 B | 8,540 / 1,272 B |
    Session baseline (22:28, before any change): 26.4 fps (render 36.83, cores 30.36 / 25.72), swinging 19.9.
  - Stage costs (bench `--stages`, runs 2), before → after (ms off the render): edgeGlow +0.62 → +0.41, surfaceBand
    +0.82 → −0.23 (noise), contactAngle=90 +2.74 → +1.09, lens −0.45 → +0.22, wetFilm −0.93 → −0.73, traces +0.68 →
    −0.75, glassBody −0.14 → −0.17, glassRim −0.12 → +0.39, liquidTransparency=1 −1.46 → −1.42; frontBright already 0.
    Toggles reshape other stages' work (the minutes slug drifts at inputGain 0): use the TUBE_PROF cycles.
  - Final profile (TUBE_PROF, ms a frame), pinned hours / minutes: all 22.4 / 19.8 = back 5.3 / 4.3, rear digits 9.6 /
    10.1, rear ticks 2.1 / 1.35, body 2.0 / 1.5 (ramps 1.24 / 1.09), fizz 1.25 / 1.0, band 0.89 / 0.84 (kernel 0.61 /
    0.59), residue rows 0.66 / 0.52, bounds 0.21 / 0.15, blur 0.19 / 0.07. Swinging hours ~26–27.8: digits 8.1–8.6, back
    4.7–5.4, fizz 2.5–4.2, residue 2.9–3.4 (zone 1.8–2.2, fill 0.6, shear 0.25), body 2.2–2.5, ticks 2.1, palette 1.36
    when the light moves (buildPalette 1.0, band rows 0.32), band 1.2–1.3, blur 0.63; minutes residue 3.8–4.8 (fill
    1.0–1.9, zone 1.8–2.4).
  - Exactness: `check_render_frames.py --tolerance 0` byte-identical after every change (9136 strips, `--big-fizz` too).
    Its random group changes traceFilm and gen on every scene of a tube, so state carried across frames went untested
    (a blur memo with its change detection removed passed): new `--tube-seq` (400 ten-frame sequences at one generation
    per tube: light holding then moving, small edge moves, pulls, films, residue arrays edited a few columns a frame;
    band / glow / front / inset / glass params varied), 13136 strips byte-identical. Mutations caught: memo change
    detection off, a ±3 memo window, band rows only on a new generation, iZ off by one, the blur fast path always.
    On the board (FMA contraction, IRAM) `-DTUBE_VERIFY` compares bitwise with the step-5 code: 0 bad of 2.2 M zone px,
    411 k palette entries, 1.1 M band-row colours, 5.0 M blur columns (streak table included), 235 k ramp rows (SIMD
    path), pinned + swinging. The band lambda (code moved, same source) by a scratch verify build (each band through the
    IRAM lambda and through the same body inline, rows compared): 0 bad of 110 M px. Host parity unchanged: `--res 320f`
    72 of 77, `--res 320` 73 of 77, `--board amoled191` 68 of 77; `check:meniscus` passed (339 scenes, max 9/255);
    `check_residue.py` passed. Board parity, final, pinned: `89 of 118080 (0.08%), >12/255 off: 0`. Panel refills OK in
    every bench (worst 13–16 %), swinging windows never late.
  - Memory: AMOLED RAM 88,384 → 88,224 B (the trace LUT moved to PSRAM). lcd316 static RAM 128,168 → 128,008 B wide
    (narrow 113,856 → 113,712). IRAM ~22.7 KB (kernels + 3e lambda 10.2, band lambda 12.6): free heap with BLE 32.3 →
    8.5 KB; BLE initialises and the board ran every bench stably; a BLE connection at this heap was not tested
    (`ble-session.py` needs `bleak` on the Windows python). PSRAM, once in render_init, per tube: trace LUT 1 KB,
    PalCache ~7.5 KB, TraceMemo ~0.85 KB, streak table 3.3 KB. Hours render task stack free 1,388 → 1,272 B (the band
    lambda frame; rampPie lanes 576 B, shallower than the digit chain). No allocation outside render_init.
  - Not built (KAIZEN): the back fill's line traffic (step 7), a T-run memo for rows with equal edges, an exact inline
    divide for the palette / 3e setup, a lazy first layer in bandRow, a T → colour memo in the zone. No look-change
    option built: after 1–5 the tube body's compute is ~4 ms of the hours core pinned (body 2.0, band 0.9, residue
    0.85, bounds 0.2), the rest of the core being line traffic (5.3), digits, ticks and fizz.
  - Scratch was git-ignored `firmware/.pio/step6/` (A/B and profile scripts, logs: removed). Kept for the review: the
    step-5 sources `firmware/.pio/step6/ref/` (render.cpp / .h, main.cpp, physics.h; the `--reference`); delete after it.
- **Step 7, tiled render (2026-10-30): same-session A/B on the fixed scene 33.6 → 40.5 fps pinned, 25.2 → 31.5
  swinging the tilt (goal ≥ 30 met).** Exact: no look change. New `tiles.h` / `tile_dma.cpp` (LCD), `render.cpp`
  (drawTube's band loop on tiles, glowT in PSRAM), `display_lcd316.cpp` (strips in whole tiles, 64-B aligned; the
  gathered push), `main.cpp` (prints, `x` buffers in PSRAM), `display.h` / `render.h` (prof / verify),
  `tools/check_render_frames.py` (`--tiles`).
  - (a) **Tiles:** the base stages (back fill to bounds, step 6's bands) render TILE_ROWS 4 rows at a time into one of
    two slots per tube in internal RAM (FB pointed so the band's rows land in the slot; the SIMD ramps' bounds are the
    slot, whose rows start 16-B aligned like the strip's). A finished tile goes to its strip rows by GDMA mem-to-mem
    (one channel pair per tube, no interrupt: the next copy polls the last RX descriptor) while the next tile renders
    into the other slot. Coherence: `tile_begin` drops the strip's lines from the data cache (M2C, ~15 us: the tiles
    rewrite every pixel, dirty lines are discarded), nothing touches the strip until `tile_end` (after the wet share and
    label layout, which do not read it). Back fill 5.3 → 0.75 ms (hours), 4.3 → 0.45 (minutes). Bench (00:56, runs 2):
    37.7 fps pinned (render 25.64, cores h 18.57 / m 14.58, push 14.08), swinging 27.6 (push 21.16).
  - Probes (scratch, removed): writing back the strip's dirty lines after a render (marks, fizz) 0.11–0.22 ms; a GDMA
    read of a whole strip under load 4.0–5.0 ms by 32-B bursts, 2.5–3.1 ms by 64-B; the tile copies run at ~26 MB/s
    (RX into PSRAM by 32-B bursts: a 4-row tile of 1,640-B rows is not whole in 64 B), so pinned tiles wait for the DMA
    (hours put-wait ~1–2 ms pinned, ~0.1–1 swinging).
  - (b) **Gathered push** (`PUSH_GATHER`, default with the tiles): a tracked strip push reads the strip by GDMA (TX
    bursts 64 B) in units of one segment (≤ 32 rows) × 64 columns, double-buffered in the tube's tile slots (idle then:
    each tube's push runs on its own render core, after or before its render), one unit landing while the CPU hashes and
    stores the one before; the lens row map rides in the per-row descriptors. Same hashes, skips and stores as step 2;
    the strip is written back first (C2M in 16 KB pieces: interrupts never off long on the refill ISR's core). Push
    profile swinging, per strip: read + hash 7.5–9.0 → 1.2–1.4 ms, gather wait 1.2 (hours) / 2.2–2.8 (minutes, next to
    the hours tile copies), store 2.6 unchanged. Bench: 40.5 pinned (push 9.59), swinging 31.6 (push 12.66).
  - Same session, back to back (01:25 / 01:28; fixed scene, bench runs 2, `swing.py` 40 s; step-6 sources swapped in and
    built `-DTILE_OFF`, then the final):
    | | step 6 | step 7 |
    |---|---|---|
    | fps pinned | 33.6 | **40.5** |
    | render ms (runs) | 28.81 (28.79–28.83) | 23.90 (23.70–24.10) |
    | cores h / m ms | 21.62 / 16.87 | 19.23 / 14.57 |
    | push ms (both strips) | 14.59 | 9.57 |
    | phys | 1.44 × (0.35 + 0.09) | 1.20 × (0.36 + 0.12) |
    | frame-p95 ms | 31 | 25 |
    | swinging fps (push) | 25.2 (20.82) | **31.5** (12.71) |
    | swinging windows fps / cores h / m (mean) | 23.6–29.4 / 26.9 / 23.4 | 29.6–36.1 / 23.3 / 20.6 |
    | refills (bench worst; swinging windows) | OK 14 %; never late, worst 16 % | OK 11 %; never late, worst 11 % |
    | free heap with BLE / hours stack free | 8,776 / 1,272 B | 4,440 / 1,244 B |
    `-DTUBE_BAND_INLINE` on the final (01:31): heap 17,480 B, 38.2 pinned, 29.7 swinging: the band lambda stays in IRAM.
  - Exactness: `check_render_frames.py --tolerance 0` byte-identical (plain, `--tube-seq`, and `--tiles` with
    `--big-fizz` / `--tube-seq`: 9136 / 13136 strips); a host sink 2 bytes short fails `--tiles` at once. Board
    `-DTILE_VERIFY` 0 bad of 96.6 M px (first build, pinned + swinging), final code 0 of 58.9 M (wide), 0 of 60.8 M
    (narrow, H 49: a partial last tile); `-DPUSH_VERIFY` on the gathered push 0 of 67.4 M, final 0 of 59.4 M (wide),
    0 of 61.3 M (narrow). Host parity unchanged: `--res 320f` 72 of 77, `--res 320` 73 of 77, `--board amoled191` 68 of
    77; `check:meniscus` passed (339 scenes, max 9/255); `check_residue.py` passed. Board parity, final, pinned: `103 of
    118080 (0.09%), >12/255 off: 0`. Panel refills OK in every bench; swinging windows never late.
  - Memory: lcd316 static RAM wide 128,008 → 131,604 B (narrow 113,712 → 121,620): + tile slots 26,240 (.bss, 2 tubes
    × 2 × 4 × 820 px) + DMA state ~0.2 KB; − glowT 13,696 (to PSRAM in render_init: only the hard-edge glow reads it),
    − the `x` dump line buffers 6,563 (one PSRAM buffer, setup), − the push's pair buffer 2,560 (in the tube's slots
    during its push). IRAM unchanged. Free heap with BLE 8,776 → 4,440 B (3.9–4.6 KB seen); BLE initialises (boot log
    clean, `ready`), a connection at this heap not tested. 2 more GDMA channel pairs (the panel uses 1 of 5). PSRAM:
    glowT 13.7 KB, dump buffer 3.3 KB, strips rounded to 108 rows. AMOLED 88,224 → 86,080 B (the residue dump shares
    the line buffer; no tiles there).
  - Not done (KAIZEN): marks / fizz / bubble / top per tile (they still read and write the PSRAM strip through the
    cache), the fbuf stores by DMA (store phase 2.6 ms a strip swinging), 64-B tile copies (padded strip stride),
    hashing at render time. Also found: `r` ends in `reset wdt` ~2 in 5, also with `-DTILE_OFF` (pre-existing).
  - Scratch was git-ignored `firmware/.pio/step7/` (A/B and profile scripts, logs: removed). Kept for the review: the
    step-6 sources `firmware/.pio/step7/ref/` (render.cpp / .h, main.cpp, display_lcd316.cpp, display.h / .cpp,
    physics.h, board.h, platformio.ini, check_render_frames.py; the `--reference`).
- **Review of steps 1–7 (2026-10-30):** Astra (high), Sol 6.1 (xhigh) and Fable read the whole diff for critical bugs;
  the default wide / narrow builds came out clean. Fixed: `AB_COMPARE` no longer linked (the `ab` renderer saw the tile
  API inside its namespace; it now keeps the strip path, `TILE_RENDER 0` in `render_ab.cpp`: the slots and channels are
  the native renderer's); `RENDER_H` 240 / 288 failed the 32-B tile assert (tiles off where a 4-row tile is not whole
  32-B blocks, `tiles.h`); a refused `gdma_start` or a copy that never lands now aborts with a message after 1 s instead
  of spinning (`tile_dma.cpp`). All six builds pass (240, 288, AB 256, wide, narrow, AMOLED 86,080 B); host frames
  byte-identical (plain, `--tiles --tube-seq`). Left as is: `FB_BOUNCE_LINES 0` has no VSYNC restart (KAIZEN).
