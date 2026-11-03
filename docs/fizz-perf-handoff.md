# Fizz perf hand-off: 240 bubbles at a full tube

Goal: the wide LCD (`lcd316@320f`, `LCD_FILL=1`) holds **≥ 30 fps with `fizzCount` 240 on a full tube**, pinned and
swinging. Today it does 18.1 / 25.4. The look may change slightly (not bit-exact); the user reviews every look change on
the board.

## State (2026-11-03, `master` a3ad26c)
- `FIZZ_COUNT_MAX` 240, `FIZZ_POOL` 480 (`spec/layout.h` / `.ts`; ×2 = full agitation, rare: keep it). `Tube::fizz` is
  in PSRAM (render_init), `MarkPlan` per tube in PSRAM (step 9).
- The board on COM11 runs a3ad26c's wide build.
- Measured on the board (full tube = clock 11:59:30, `g 0 0`, `fizzSource 0`, user-fav otherwise):

| bubbles / tube | fps pinned | fps swinging | hours core render | fizz step pinned | steps / frame |
|---|---|---|---|---|---|
| 120 | 33.9 | 35.9 | 19.6 ms | 2.05 ms | 1.5 |
| 240 | 18.1 | 25.4 | 29.8 ms | 6.39 ms | 2.8 |
| 480 | 5.4 | 11.7 | 50.1 ms | 25.2 ms | 5 (cap) |

- Render is linear: ~85 µs a bubble on the hours core. The fizz step grows faster than the count and feeds itself:
  `liquid_tick` runs `stepFizz` once per 50 Hz catch-up step (up to 5), so a slow frame asks for more steps.
- At 240 pinned the 55 ms frame is ~18 ms physics + ~37 ms render/push: both must shrink. Physics alone free ≈ 27 fps.
- user-fav normal bench (`e2e.sh … --fix-pose`, low fill): 51.6 fps pinned. Must not regress.

## Step 0
1. `tools/device.py v` → `board lcd316@320f`; save `p?` to `firmware/.pio/fizz/params-found.json`; put it back at the end.
2. Write `firmware/tools/fizz_bench.py` from the recipe below; run it on a3ad26c and keep the table as the baseline
   (`firmware/.pio/fizz/baseline.txt`). Same-session A/B only: IRAM placement moves the render by up to ~2.5 ms between
   builds, so bench the old and new build alternately in one session (see the firmware-e2e skill).
3. A `-DFIZZ_PROF` build at 240 bubbles full tube, pinned and swinging: where the step goes (`fizz-step`: frand, spring
   point, loop, discFit, touchesFoam, merge, cadence, settleFoam) and the render (`fizz-prof`: setup, row prep, discRow,
   rows, bubbles). Decide the order of the levers from this, not from the list below.

Bench recipe (what produced the table; `device.py`, `tilt.short`): volatile pins only (`d.set` = `p~`), restore every
touched key in `finally`, then set the real clock (`T <epoch> <tz_min>`).
```
l; t 11:59:30; d0; g -0.5 0 (4 s); g 0 0 (4 s); p~fizzSource=0
for count in 120 240 480: p~fizzCount=count; g 0 0; wait 5 s
  pinned: `f`, wait 6 s, `f` -> line
  swinging: `f`, alternate g -0.5 0 / g 0.5 0 every 1.5 s for 8 s, `f` -> line
spring: p~fizzSource=1 p~fizzSourceRate=20, count 240 (wait count/20 + 3 s), pinned line
```
Watch: at 480 with a spring the hours pool stayed at 33 slots (not understood; maybe the clock wrapping past 12:00).
Keep the scene inside 11:59:30 + run time, or freeze the clock.

## Levers (user's direction: reuse between steps in physics, between bubbles in the render)
Physics (`stepFizz`, `settleFoam`, `touchesFoam` in firmware/src/render.cpp; the same names in sim/src/render.ts):
1. **settleFoam's sort:** it rebuilds `foamOrder` in slot order every step and then insertion-sorts it; the comment says
   "nearly sorted from the last step", which is not true. Keep the sorted order between steps (per tube, both tubes are
   stepped one after the other on core 1; per-Tube storage, not file-static, if it must outlive the call).
2. **Neighbour list:** the slide pass and the 3 packing sweeps test every parked pair. Foam moves < 1 px a step: a list
   of pairs within 2·r_max + margin, rebuilt when any bubble moved more than margin/2, serves the sweeps and the next
   steps. Also: sorted by u, the inner loop can stop at the first bubble farther than 2·r_max (KAIZEN).
3. **Catch-up steps:** `fizzSurf` / `fizzSurfL` change only when drawTube runs, so the 2-5 steps of one frame see the
   same surfaces: the spring point (`discFit` ×2, `foamFront`), the surface fits per bubble row can be done once a
   frame. Bigger: one `stepFizz` per frame with the summed dt (KAIZEN: "one call per frame with the summed dt would
   break the loop") — check bubbles do not tunnel through a surface or the wall at 5× dt (cap the sub-step if they do).
4. **Per-slot radius:** `fizzR(p, v)` is recomputed per pair and per test; it changes only at spawn. Store r (and
   wallY / hide rows) in the slot or a parallel array. Same for `touchesFoam`'s candidate scan.
5. Idle slots: one long-lived bubble keeps `fizzN` at its high-water mark (KAIZEN); compact or keep a live list.

Render (`planBubble`, `bubbleRows`, `discRow` / `discRowT`; step 9 plans in `MarkPlan`):
6. **Per-row tables, exact:** every bubble row copies `sR, sL, bR, bL, veilLo, veilHi`, computes `wallT` and `cRim`
   (blend by depth): one table per tube per frame, the DiscRow points into it. The light direction (`ly`, `nrm`, `dirX`,
   `dirY`) depends only on the row. In the step 5 profile setup + row prep were ~25 % of fizz, discRow ~75 %.
7. **Size classes and depth levels (look change):** sizes come from continuous `v` (0.5..1.5) and depth from `z`
   (0..1). Quantise at spawn to ~8-16 radii (fizzSizeVar spread) and 4 depth levels: bubbles of a class share the disc
   set-up and a pre-rendered coverage mask per subpixel phase (KAIZEN: per-px work ~2-3× less, "Per-radius /
   subpixel-phase coverage sprites"; 4 depth levels with per-row tint tables). Masks sized at boot for the slider
   maxima (fizzSize 16 → PX_SCALE), PSRAM or internal per measurement.
8. The plan: 160 B a bubble written to cold PSRAM lines (step 9 Log: fizz plan 0.75 ms at ~50 bubbles): compact it,
   or with 6/7 most of it disappears.

## Rules
- Firmware memory: no lazy allocation; every buffer static or allocated once at boot, worst case (`FIZZ_POOL`), fail
  visibly. Both tubes render concurrently on two cores: per-frame scratch per Tube, never file-static. Free heap with
  BLE is 14.1 KB now: new tables go to PSRAM in render_init unless measured faster in internal RAM (then report heap).
- The sim mirrors every change in the same step (sim/src/render.ts stepFizz / settleFoam / drawing). Sim parity must
  stay `>12/255 off: 0` (`e2e.sh` parity line).
- Xtensa: `fminf` / `floorf` / `/` / `sqrtf` are calls; use `fmn` / `fmx` / `ffloor` / `fceil` / reciprocals. Hot
  per-pixel loops `noinline` out of their caller (spills). Fizz kernels live in IRAM on the LCD (`FIZZ_IRAM`).
- Not bit-exact any more (fused math, and the levers change rounding/order). What replaces it:
  - host `check_render_frames.py --tolerance N --list-diffs` and `check_fizz_steps.py --pixels-only -v` against
    `git show a3ad26c:firmware/src/render.cpp`: report how many presets/frames differ and by how much, and the fizz
    populations (`-v`: live / foam maxima and end counts) — they must stay close (same physics, not a new look);
  - levers 1, 2, 4, 6 should be exact or within a few LSB; if one is not, say why;
  - board: `X` / `check_board_steps.py` runs must still agree with themselves (deterministic), not with the old build.
- Look changes (3, 7, anything visible): **the user reviews them on the board, one change per round; stop and ask
  when a build is ready to look at** (no unattended timed sweeps). Measure symptoms first (counts, pixel diffs).
- KAIZEN.md: side ideas and workarounds, laconically. No commits; the user commits.

## Deliverables
- A Log section at the end of this file per lever: what changed, same-session A/B (fizz_bench table + the user-fav
  bench), host diff numbers, heap / worker stack, what the user saw.
- The board on the last build the user approved, params as found, clock set to real time.

## Log (2026-11-03)
Bench: `firmware/tools/fizz_bench.py` (new, the recipe above; `bench/user-fav.json` pinned volatile, 11:59:30 frozen,
plain builds flashed alternately with `--flash`). Board params as found: `firmware/.pio/fizz/params-found.json`; never
written (all pins `p~`). Saved builds and every table: `firmware/.pio/fizz/` (A = a3ad26c, B3, M5, M6 = final).
Profiles below are `-DFIZZ_PROF` builds (hours tube, per frame; step: both tubes, per step), 240 bubbles, pinned.

### Final, same session (A, M6, A, M6)
| scene | A a3ad26c | M6 |
|---|---|---|
| 120 pinned / swinging | 36.6 36.3 / 35.2 35.4 | 41.4 41.3 / 40.0 39.1 |
| 240 pinned / swinging | 23.8 23.8 / 24.9 24.6 | **31.0 31.1 / 31.6 32.0** |
| 480 pinned / swinging | 7.4 6.4 / 13.9 12.8 | 14.7 14.7 / 22.3 22.8 |
| 240 spring (rate 20) | 22.8 22.0 | 30.8 29.4 |
| user-fav normal bench (`bench.py --fix-pose`) | 51.6 51.6 | 51.5 51.5 (spread 51.2-51.8) |
Pinned 240 moves with the parked count (10-30 a tube after 11 s): ±0.7 fps between runs of one build.
Sim parity on M6 (`compare-device.py`): 159 px mismatched, `>12/255 off: 0`. AMOLED builds, static RAM 76.2 KB.
Memory: free heap with BLE 14.7 KB -> 4.5-4.7 KB (8 KB shared masks internal, ~1.3 KB more IRAM); worker stack free
1160 (unchanged); PSRAM +~110 KB (FoamWork 2 x 12 KB, FizzLook 2 x 5 KB, mask pool 55 KB, plans aligned). BLE connect
at this heap not tested (no `bleak` on the Windows python).

### Levers 1, 2 (physics, exact): foam work space per tube
- `FoamWork` (PSRAM, render_init) replaces the file-static `foamOrder`: the sweep order kept between steps (the first
  sort ties by slot: what the sim's stable sort of slot order gives); the parked bubbles, or touchesFoam's candidates,
  in a (u, y) grid; touchesFoam returns at once when the bubble is farther than any contact from the foam's u extent;
  the pack sweep gathers partners from the cells within reach into an ordered bitset; a bubble that drifts half a cell
  moves to its new cell. The tests are the old ones on the same pairs in the same order.
- Profile: touchesFoam 1.84 -> 0.10 ms a step (24 -> 3-8 slots a call); 480 pinned 13.3 -> 0.15 ms; settle at ~15
  parked 1.0 -> 0.6-0.9 ms; spring at the glass (~120 parked) 6.7 -> 5.9 ms (KAIZEN: next lever there).
- Exactness: host 80/80 presets + 5 stress scenes (up to 255 parked) state-hash identical, with and without `--fma`,
  tiled; board `X` (B3 = grid + R1) 350/350 frames identical on user-fav, fav-240 and found-spring240. The relink step
  (no global grid rebuild) is exact without fused math; with `--fma` and on the board one parked bubble's y differs by
  1 ULP after ~300 frames (a branch in the inlined place() moves one fusion), populations unchanged.
- discFit: rows skip their root when their term provably exceeds the nearest row's (exact: board `X` identical).
- Same session A / B3 (grid + R1): 240 pinned 23.5 -> 27.9, swinging 24.7 -> 28.3.

### Lever 3 (catch-up steps): each tube's fizz steps on its own core (new, structural)
- One summed step was not tried (changes foam relaxation and let-go, Astra 2026-10-02). Instead liquid_tick records
  each step's inputs and the hours tube steps on core 0 right before its render, the minutes tube on core 1 (main.cpp
  FIZZ_SPLIT, `stepFizzTube`); `X` / host keep `stepFizz` (both tubes, one core): the checks are unchanged. `f`'s fizz
  step stays the two tubes' sum. M5 -> M6: 240 pinned 29.8 30.0 -> 32.3 31.5, swinging 30.8 31.0 -> 32.0 31.6.
- Not exact against A on the board (the hours tube now draws from core 0's xorshift); `X` runs agree with each other.

### Lever 4 (per-slot radius): reach bound only
- A stored radius in the pair tests broke the board's fused `rf + fizzR(...)` (host `--fma` 57/80): the tests keep
  fizzR; the stored radius only bounds the grid reach.

### Lever 5 (idle slots): not done (an idle slot costs ~10 cycles a step).

### Lever 6 (render, exact): per-row tables, compact plan
- The plan is one 64-B line a bubble (was 160 B, 3 lines); bubbleRows rebuilds the DiscRow on its stack from it (same
  expressions); veil bounds per row. check_render_frames 13136 strips byte-identical (also tiled, big fizz);
  check_fizz_steps 80/80 + stress identical. Row prep 2.34 -> 1.0 ms.

### Lever 7 (look change): size classes, depth levels, shared masks
- Model (sim + firmware): v takes 12 values (0.5 + (k + 0.5) / 12), z 4 (one draw each, as before).
- Render: per class one quadrant of the disc's coverage (|dx| in 1/4 px, |dy| in 1/8 px; a class bubble's x is rounded
  to 1/4 px), 8 KB for user-fav, shared by both tubes (built by the first tube to see new sizes), internal RAM up to
  8 KB, PSRAM past it, analytic past the sliders. The core and the pinpoint stay per bubble (they follow the light),
  by their chords per row; veiled and pinpoint pixels per pixel on the mask's coverage; popping bubbles analytic.
  Per depth level: rim and pinpoint colour per row (no blend565 per bubble row).
- Profile hours fizz 17.3 -> 11.0 ms (set-up 2.75 -> 2.3, row prep 2.34 -> 1.66, disc 9.17 -> 4.48).
- Host vs a3ad26c: 2003 of 13136 strips differ (all with fizz on), 16843 px, worst 91/255; big fizz worst 255 (ring
  pixels move with the radius snap); non-fizz byte-identical. Stepped populations (LCD): live max 0.92-1.00 of the
  reference, parked mean median 1.00 (0.77-1.26 on means under 5), the 240-bubble stress scenes 0.88-1.01.
- Measured dead ends: a d2 coverage table per class (disc 11.3 vs 9.2 ms: the index maths costs a root); a
  span-classified exact kernel (10.9 vs 9.2: the out-of-line pinpoint call); a Newton reciprocal in fizzMag (slower
  than the division); masks per phase in PSRAM (44 KB a tube: row prep +1.4 ms from misses); the same masks in PSRAM
  vs internal 11.6 vs 10.25 ms.
- User review on the board (2026-11-03): approved. M7 on the user's own look, then side by side (a throwaway build:
  hours tube a3ad26c's per-bubble path, minutes tube M7's, both at the minutes' fill, half full; the old side proven
  exact on the host, 80/80 presets with both tubes old). The user: less size variety is acceptable.

### Review (Astra, gpt-6-astra via Codex CLI, read-only) and fixes (M7)
- Fixed: sizes past the sliders overflowed the mask byte count (a class now needs 0 < r < 62, else analytic and
  reported); the pool's worst case is per class the larger of spread 0 and 1 (sampling 65 spreads could fall short on
  other canvases); the live loop builds the masks on core 1 before the worker starts (render_fizz_prepare), so no tube
  builds them while the other draws (the atomic flags stay for the sequential host / `X` paths); the overflow peaks are
  atomic maxima (both cores step now); the grid's cell index takes NaN without a float-to-int conversion; `f`'s fizz
  max is again the worst single step (both tubes), not a frame's average.
- Checked sound by the review: foam order and grid exclusions, bitset bounds, discFit row skip, mask indexing and
  clipping (incl. negative x and mirroring), split-step order and per-tube state, spawn quantisation = sim at all five
  sites, boot-time allocations.
- Host after the fixes: identical to M6 (render frames, big fizz, stepped tiled 80/80). Board M7: 240 pinned 31.9,
  swinging 32.0, spring 32.5; `X` runs agree (fav-240, found-spring240); free heap with BLE 4.2 KB.
- Not fixed (pre-existing at a3ad26c, KAIZEN): a NaN fizz param crashes foamFront.
