# Kaizen — continuous-improvement backlog

- Host parity checks: sandboxed Node `spawnSync` can hang or report EPERM despite child output;
  the approved run outside the sandbox completes normally.

## Visual / layout
- Tilt pose currently uses the two in-plane gravity axes; face-down horizontal is indistinguishable
  from face-up. Carry signed normal gravity through the input pipeline if upside-down release is wanted.
- Rear ticks still round their parallax to whole pixels (each tick at its own depth, so the ladder steps one tick at a time); the digits now glide sub-pixel. The same bilinear placement would smooth the ticks.
- `digitParallax` shifts a rear label as a block; the ticks bow through the rear-half depth. A per-row depth factor
  (digits are ~centre row on every preset, so ≈1) would only matter for digits pushed toward a wall.
- Rear-mark compositors index row bounds before checking that the row is in range; clip `ry` first in sim and firmware.
- Even if hour has passed, edge might be before it, example is 06:01
- Empty space at the top and bottom of the real screen? Move tubes further away from one another?
- Now that edgeSoft is a real ramp (glow folded into its alpha), emissive presets (xenon, molten —
  both edgeSoft 0) could revisit edgeSoft 1–2 for a genuinely soft self-lit edge.
- `markContrast 0` does not hide marks (it only zeroes rear-mark throughLiquid blending); ticks/digits
  draw their own colours regardless. To suppress marks in a test harness, pass `ticksN = 0`.
- Firmware glow effectTable now serves only the edgeSoft 0 path; soft-edge glow is per-pixel float
  (same cost as the existing direct path — presets with edgeGlow > EFFECT_MAX already bypassed the table).
- Sprite fonts have no emboss shadow (`digitShadow` is bitmap-only), so light sprite numerals over a
  light liquid rely on `markContrast` alone.
- Glass wall band is drawn in the palette (pre-lens), so a strong `lens` curve squeezes/stretches the
  band with the rest of the tube; a post-lens rim would keep it a fixed px width, but needs post-lens
  edge bounds (the earlier post-lens rim pass indexed pre-lens `bounds` rows — removed for that).
- `liquidThin` is a Beer-Lambert cue; opaque or self-lit presets (blood, milk, molten, xenon) inherit
  the 0.4 default and could set it to 0 if the greyed silhouette rows look wrong on the device.
- Physical lab's area-light highlight is a broad Gaussian band at 2·(light angle); the legacy tent
  highlight (`highlightH`/`highlightSharp`) could take that profile to match the lab look further.

- Rear marks under the band (markFn / Mark::bandMark) keep the rim and blick by scaling the mark's write by
  what they let through; the layers' own colour also yields by that share. Exact compositing needs the back
  as it was before step 3e (a ~8 px × H × 2 cache per tube) — only worth it if the faint mark seen "in" a
  strong rim ever bothers.
- The rim sits at `min(surfaceWidth, ring lead)`, not at the wall contact ring: with a deep dish and a narrow
  band (depth 12, width 4) it is drawn ~8 px short of the real ring, more so while motion deepens the dish.
  `surfaceWidth` ≥ depth·(1 + tiltGain) keeps them together; a mode grading the shoulder over the whole
  lead and pinning the rim on the ring would be the faithful option (changes every preset's band width).
- Blick and rim-tint are cues, not optics: the blick is a row tent at the highlight row (`light` is already the
  cylinder highlight-normal angle, so no 2·light shift applies), the rim swaps reflection for absorption by
  backdrop luma instead of by Fresnel/viewing angle (pbr-book 4ed, Dielectric BSDF). A per-pixel dielectric
  term on a 1-px rim is not worth the S3 cycles; a separate blick colour (white blick on a coloured
  `liquidHi`) is the cheap win.
- Parity tolerance (12/255) assumes one quantised blend per pixel per stage; any stage that writes the same
  pixel twice in the same direction can stack to 2 LSB (17/255). Compose layers before writing (as step 3e
  now does) rather than widening the tolerance.

- The time edge does not flatten onto the far end cap (the home edge does, `edgeXL` `xs / 8`): a slug parked at
  the far end with a lean leaves an air wedge in the corner.
- Cap amplitudes are scaled against the nominal column (`capScale(len)`), not the real gap: under negative slosh
  two convex caps of a short slug can cross on their own (lean or not). Scaling by the gap changes non-free strips.
- A slug's hanging (gravity-ward) end leans as much as the level upper one (one `angle`); a weaker lean there
  (Bond number) would be closer to a capillary.

## Tooling / firmware
- `check_meniscus.py` raises on the first over-tolerance pixel: later scenes go uncompared. Report all
  over-tolerance scenes instead.
- Push all writes fields one at a time, so the board renders transient combinations (e.g. new
  `tubeHeight` with the old fizz positions, which used to hit the task watchdog). A `Pbegin`/`Pcommit`
  transaction like the retired physical renderer's would apply a whole preset atomically.
- Internal heap on the board idled at ~19 KB free (`s`: heap 19676) with the (retired 2026-09-25) physical
  renderer's 343 KB PSRAM layers resident; re-measure; watch it before adding anything that allocates at runtime (BLE, NVS writes).
- A task-wdt reboot while the browser holds the serial port leaves the panel black until a manual
  reset (host DTR/RTS state during re-enumeration); the sim could detect the boot banner and reconnect.
  Same root as the close-reset: on the S3's USB-serial-JTAG, DTR low with RTS high is a reset.
- A host harness for the legacy renderer (stub `esp_heap_caps.h`/`esp_random.h`, replay `name=value`
  writes with physics steps) reproduces push-all sequences without the board; worth keeping in tools/.
- Existing `scaledGlyphs()` silently drops glyphs when `GLYPH_POOL_PX` overflows; report the unsupported
  size visibly instead of leaving missing digits. Found during the physical-renderer planning audit.
- `f` now includes whole-frame p95 and the physics / fizz step, strip push and loop-rest costs; IMU I2C and serial poll are still lumped in `rest`.
- Fixed clock (`d0` + `t`/`T`) can sit milliseconds before the requested second because demo offset
  advances on fixed physics ticks; at a minute boundary `s` can consequently show the preceding minute.
- COM6 bridge reopen reverted the (now retired) volatile physical mode to legacy during testing. Audit the Windows driver's close/open reset behavior separately.
- `device.py` now dwells 2.5 s on close after any `p` write (NVS autosave) and drops RTS before DTR on
  close (no reset). Other serial clients (the browser's Web Serial) still reset the board on close, so
  a preset pushed from the sim and closed within 2 s is lost the same way.
- `device.py` `close()` waits 5 s for the Windows bridge to exit; once it took longer and `bench.py`
  died with TimeoutExpired after its work was done, which aborted `e2e.sh` before the parity step.
  Treat a slow bridge exit as non-fatal (or lengthen the wait).
- `p!` resets to the compiled preset and 2 s later overwrites the NVS-tuned params; a `p!` that does not
  persist (or a "revert to NVS") would be safer for scripts.
- Board keeps flipping between Windows COM6 and WSL `/dev/ttyACM0` (usbipd auto-attach?); re-enumeration
  looks like a reset from the firmware side. Decide one home for it.
- Clock is lost on every esptool flash (no RTC battery) — `flash.sh` could re-send `T <epoch>` afterwards.
- run-sim shots are not repeatable: two `material=honey&settle=1&fresh=1` shots differ in ~170 px (fizz/bubble positions are
  unseeded), so before/after pixel diffs carry that noise; a `seed=` URL param would make shot comparisons exact.
- `f` on the LCD: `render` now includes both pushes (staggered), `push` = both cores' push time, overlapped; earlier
  log lines (serial push) are not directly comparable on those two fields, only fps.

## Rendering: incrementality / optimisation — primarily for POWER (memory wins too)
_Added 2026-08-20 after Phase 3 (liquid face live, 38–40 fps)._

**Why:** the face currently redraws both full 72×536 strips every frame and streams them over QSPI at
~40 fps even when nothing visible changes. At rest the minutes edge moves ~0.15 px/s and the hours edge
~0.012 px/s; the only continuously animated thing is the fizz. So >95 % of the CPU (≈18 ms/frame at
240 MHz) and the panel DMA traffic is spent repainting identical pixels. On a wrist-worn battery device that
is the dominant controllable power cost after the AMOLED itself. It also dictates the memory layout
(two 77 KB internal DMA strips kept resident just so render and DMA can overlap).

**Levers, in the order we would take them:**
1. **Frame skipping at rest** — render only when something changed: any edge moved ≥ 1 px (compare the
   per-row `edges[]` against the last pushed set, or just `xe`, `angle`, `edgeLight`, `light`
   quantised), a param changed, or fizz is on. Idle → CPU sleeps between IMU samples. Cheapest, biggest win.
2. **Dirty-rect push** — when only the edge region moved, push only the columns
   `[min(oldEdge, newEdge) − frontBright, max(...) + edgeGlow]` (panel supports arbitrary column windows
   via 0x2A/0x2B). Cuts DMA time from ~7 ms to < 1 ms per frame and removes the need for full-width strips.
3. **Static-layer cache** — ticks + digits + glass never change between param edits; keep them in a
   pre-composited per-tube background (PSRAM is fine) and only paint the column + edge effects over it
   each frame. Removes the ~8 ms of mark compositing (`throughLiquid` per glyph pixel) from the hot path.
4. **LUT-ify the edge effects** — front-bright / glow blends are functions of (row, k, lightK): a
   72×(21+15) 565 table rebuilt only when `lightK` changes by > 1/64. Turns ~6 k blends/frame into
   table lookups.
5. **Fizz as a power setting** — it forces continuous repaint; make it off-by-default on battery, or
   animate it at 10 Hz in a small dirty rect.
6. **Memory follow-through** — with 1–3 in place the second internal strip (77 KB) and possibly the whole
   PSRAM canvas go away; that is the headroom Wi-Fi SoftAP needs (see docs/companion-handoff.md).
7. **Measure, don't guess** — add a `s`-style power line: frames rendered / pushed per second, ms per
   frame, and once battery hardware exists the ADC on GPIO1. Optimisations get accepted on those numbers.

**Not doing yet:** any of it before the look is signed off and the companion's param path works —
incrementality makes every render bug harder to see, so it comes after the visuals are stable.

## Other
- Sim screenshot validation: port 5190 was occupied but unreachable, and headless Chromium intermittently aborted during sandbox shutdown; used 5191 and retried. Check stale listeners/processes if either recurs.
- Sim `flick →` button is nearly invisible: 400 dps raw → ~60 dps after gyro HP 5 Hz + LP 12 Hz + deadzone, so
  `fillPos` moves 0.3 px. Either shape the button burst like a real flick (100+ ms) or show the raw kick on the scope.
- Reading gesture (`readTurn`) sums |gyroAlong|+|gyroAcross|; which IMU axis is the forearm roll on the wrist is
  unmeasured — record a real wrist-raise with `i` and pick the axis / threshold from it.
- `lens` is rendered by the firmware *and* the acrylic rod magnifies on top: with the rod fitted, device `lens`
  probably wants 0 (or negative) while the sim keeps 0.6 as a preview; `meniscusLens` / `topLens` are the
  per-layer compensations and should be calibrated together.
- Fizz respawn ignores the free slug's motion (bubbles are in the liquid frame, fine) but a bouncing slug should
  nucleate bubbles like `agitation` does — hook `slugAcc` into `ensureFizz`.
- `x` STATE now dumps 12 values per tube (acrossTilt, cap, films, slugPos, reading added); compare-device.py updated,
  anything else parsing STATE must follow.
- Light model (`lightPhys`): physical mode ignores the light's along-axis component (it only dims, does not move the highlight) and the face-down case (`n` clamped ≥ 0).
- `edgeLight -> lightK` is a proxy: pressure into the end fills the cap (modelled via `meniscusTiltGain`);
  the brightness change stands in for the stronger caustic of a fuller cap.
- Gyro about the screen normal (IMU z) is dropped in both mains; it is the rate that physically kicks the
  in-plane front skew (`angle`). Plumb it as `gyroNormal` in `TiltInput` and add an impulse term.
- Serial command parser lives in `main.cpp`; extract to `command.cpp` with an output sink before it grows
  a second transport (BLE/HTTP) — planned in docs/companion-handoff.md.
- Param writes are unvalidated on device; clamp with the sim's `PARAM_META` min/max before exposing to
  the companion.

## Companion / transport
_Added 2026-08-21 with Transport 0 (Web Serial)._
- Serial writes are one per render frame (~26 ms): "push all" = 87 × 26 ms ≈ 2.3 s. Add a batch command
  (`p {json}` or `p a=1,b=2`) on the firmware, or parse several lines per `loop()`.
- Reply matching relies on the echoed command line being intact; an IMU CSV line could in theory split
  the echo (firmware echoes per char between `imu_poll` calls). Fix firmware-side: drop echo when a
  stream is on, or prefix replies (`> ok`).
- `s` reports ~23 fps with BLE built in (STATUS says ~40). Not measured without BLE on the same build; check whether the
  BT controller task or the smaller strips cost it.
- BLE: `x` hex dump and echo-per-char are wasteful over NUS; BLE-side flow control absent (notify drops if the
  central is slow). BLE always on — measure its idle draw before the power-management work.
- `t HH:MM:SS` loses the date; `T <epoch> <tz>` + `settimeofday` per companion-handoff.md.
- FW power management: light sleep when still (QMI8658 wake-on-motion on INT1/INT2 = GPIO45/46; not RTC pins → light sleep only, not deep), AMOLED SLPIN while asleep, partial window updates for the two bar strips only, tick rate 1–2 Hz once liquid settled. Target avg <15 mA → 500 mAh cell lasts days.
  Two-stage wake: (1) QMI8658 WoM threshold/debounce tuned so walking/typing don't trip it, accel-only low-power mode; (2) on wake, gyro burst 100 Hz, classify wrist-raise (forearm-axis rotation 60–90° in 300–600 ms ending glass-up + 200 ms still) before panel on; no match → back to sleep. Tilt-away blanks early. Tune thresholds from `i` CSV recordings.

## Power / clock
- Low battery → AMOLED off + deep sleep: RTC domain (~10 µA) keeps the time until the cell is flat, not until the display can no longer run.

## Vial optic
- `lensSmooth` / `gloss` are simulator-only. Port smoothing only if nearest-row bands are visible through the acrylic rod.
- codex exec in parallel background jobs needs `</dev/null`, else stdin race (EAGAIN) kills ~half the jobs.
- Image lanes (see pigeon_drop skills): cursor `agent -p -f --model cursor-grok-4.5-high-fast "<prompt + output path>"`; cursor `agent -p` hangs headlessly (even text-only). agy: `agy --mode accept-edits --print="Use your generate_image tool… Do not run shell commands. Reply with the full saved path."`; file lands in ~/.gemini/antigravity-cli/brain/<id>/, copy it out. Gemini image quota exhausts after ~10 parallel renders.

## Presets / materials (2026-08-27)
- Residue opacity parity: firmware clamps `traceAmount` before wall attenuation; sim clamps after it,
  so amounts above 1 (including olive oil) can render stronger at mid-height in the sim.
- `liquidTransparency` conflates tint and clarity: it mixes the body toward the tube back, so a coloured
  *clear* liquid (urine, champagne) turns khaki above ~0.6. A separate tint/absorption term (multiply the
  back by the body colour, then add the lit body) would let tinted liquids stay clear.
- Rear sprite digits at `digitScaleY` 5 / `digitBottom` 16 clip at the tube's top row (the "3" loses its
  top) in honey/malt/cola; either cap the scale from the tube height or clamp the baseline.
- `check:presets` ranges (tools/check-presets.ts) are hand-set from the 14 looks; if a new mechanic lands,
  add its coherence rule there rather than tuning presets ad hoc.
- Milk: opaque white with marks printed on the glass — no single mark colour reads well on both the white
  column and the black dry side (mid-blue chosen). A per-side mark colour (wet/dry) would fix it.
- Free slug + rear digits: at `readFaceUp` 1 the time is only true while the slug is home; presets inherit
  the user's read settings (turn 125 dps, hold 11 s) — revisit once the wrist-turn detector is tuned on the board.

## Rear-wall decals removed (2026-08-27)
- Procedural texture = free to generate, not free to composite: one `blend565` per textured pixel (~26k/frame
  for a dense grain) is ~10 ms on the S3. A sparse-list + baked-dry-strip cache (PSRAM) was tried and FPS
  was still poor even with decals off — suspect the extra PSRAM traffic / `memcpy` per row or heap pressure
  rather than the blend count; not diagnosed. If revisited: measure with `f` first, keep the bake in internal
  RAM at real H, and re-check that step 1 is still a plain `hspan` when no decal is active.
- Baseline frame rate with decals removed is a steady ~18 fps on the device (`f`). Stable, so it does not
  read as stutter, but it caps how much per-pixel work any future back texture can add. First split
  `render` vs `push-wait` from `f`: if push-wait dominates, the strip DMA/SPI clock is the limit, not
  rendering; if render dominates, profile per stage (palette, liquid spans, marks/digits, fizz, lens).

## Perf hand-off 1 (2026-08-27)
- Internal RAM is the wall: 37 KB free after BLE init. TUBE_HEIGHT_MAX 80→72 would return 17 KB (strips are
  2 × 536 × 80 × 2 B); with that, the sprite glyph pools (2 × 18 KB) could move from PSRAM to internal (~2 ms/frame).
- Unexplained ~2 ms between two builds with identical hot loops (static internal glyph pool 38.3 fps vs heap
  internal 42.0 fps). Suspect flash icache layout of render.cpp; try `IRAM_ATTR` on `drawSpriteGlyph` /
  `Mark::operator()` / `throughLiquid` and measure — or accept the swing and always compare medians of ≥5.
- Parity pre-existing (not from hand-off 1): `cryo` preset 132 px > 12/255 on the minutes sprite labels,
  `free` 1 px, `free`+`remaining` 36–72 px (slug-state dependent). Diff pngs: run
  `compare-device.py` after applying the preset; investigate sim `render.ts` vs `render.cpp` sprite rows for
  digitFont 5 at that scale.
- `compare-device.py` doesn't pin the scene (`inputGain`, `t`) so the mismatch count drifts 160–230 with the
  live IMU; give it the same pin as bench.py so "must not grow" is a real bar.
- Front-bright has no cached table (frontBright 21–23 in presets > EFFECT_MAX 16, memory-bound); if a preset
  turns it on, the direct per-pixel path costs ~4 ms — a per-k `T` hoist (row-independent part) is cheap.
- `free` preset edgeGlow = 40 > EFFECT_MAX 16 → direct path; either raise the table (10 KB internal per +16
  columns) or cap the param.
- Dual-core render is core-0-bound: hours 14.7 ms vs minutes 10.6 ms (sum 25 > 22 sequential). Two levers:
  (a) balance work, e.g. give core 1 the hours labels or split by rows instead of tubes; (b) find why core 0
  is slower per tube — try a `-DNO_BLE` build and IRAM_ATTR on the hot mark path (BT controller interrupts
  and shared flash cache are the suspects).
- Hand-off 2 "not now" items still open: triple buffering, physics on core 0, a separate fizz task.
- ~~Trace decay scans all 536 columns per tube every tick even with an empty buffer~~ — done:
  `TubeState.traceLo/traceHi` occupied range, physics + render both skip/range-restrict (2026-09-01).
- Heavy residue (~585 live columns) still costs ~14 ms/frame: pure per-pixel `pxaT` blend (~42 k px).
  If that matters, next wins: skip rows where `traceA·rowW` rounds to 0, or blend row-batched spans.
- `digitFont 5` + `tubeHeight 72` has a traces-unrelated parity gap: ~1715 px mismatched, 169 px
  >12/255, all in the digit rows (25–70 / 204–239). Sprite-font/mark path, worth a separate look.
- `bench.py` median-of-5 has ~±0.5 ms noise on-device — enough to fake a cost for a free stage;
  an interleaved A/B min-of-samples mode would make small deltas trustworthy.

## Verification pass on the traces uint16 rework (2026-09-01)
- **Render task hangs (task-wdt reset) when `tubeHeight` shrinks while `fizz` is on.** Reproduced on the
  board: `ptubeHeight=72` → `ptubeHeight=55` with `pfizz=1` resets ~2/6 tries (fizz=0: 0/6); it also fires
  ~3/5 times when a preset push crosses the same transition (any green→blood style switch). Verbatim:
  `task_wdt: - IDLE0 (CPU 0) … CPU 0: render0` , backtrace `0x42025ee9` →
  `Tube::drawTube … render.cpp:984`, i.e. the fizz particle loop
  `for (int iy = floorf(f.y - ry - 1); iy <= ceilf(f.y + ry); iy++)` with `ry = r / fizzMag(...)`.
  Fizz positions still carry the *old* H when the layout changes, so `m` can go ~0/negative and `ry`
  explodes → the loop runs to INT_MAX. Not caused by the traces work (`p.traces` is false at the crash
  instant). Fix: clamp `ry` (and `m`) and/or reseed `fizz[]` on a geometry change.
- Trace render layer is ~3.0 ms/frame (46.9 → 40.9 fps on the pinned scene); the physics decay loop is
  ~0.07 ms, i.e. free. If traces need to be cheaper, the win is in `drawTube` step 3d (full L×H scan with
  a `pxaT` per non-liquid pixel), not in the decay loop.
- Trace layer is the dominant source of ≤1-LSB sim parity drift (41 px without it, ~600–645 px with heavy
  residue, all ≤9/255). Suspect the `traceA[x] = (uint8_t)(a + 0.5f)` + `(traceA[x] * rowW) >> 8` integer
  path vs the sim's float alpha; worth a bit-exact LUT if the parity bar tightens.
- `tools/device.py` cannot recover when the board re-enumerates: the Windows COM bridge dies
  (`RuntimeError: bridge died`) and every later call fails. A reconnect/retry in `Device.raw` would make
  crash hunting far less painful.
- `ambientLight` desaturates only what is brighter than the diffuse body, so over-driven emissive
  presets (glow/xenon: body luma already ≥ display max) are untouched. If those should also go
  "ambient", the knob would need a second stage that compresses the body toward an ambient level —
  overlaps with brightness/liquidBright, left out.
- Panel HBM (RM67162 B0h bit1): enabling it turns the liquid face bright cyan and a lit face trips the
  ESP32-S3 brownout detector (USB supply sags). Not a usable brightness step; 0x51=0xFF is the ceiling.
  The HBM bit survives the RESX line and a reflash; init now writes B0h=0x04 explicitly.
  `H1` serial command left in for experiments only. QSPI register readback (opcode 0x03) returns 0x00
  for everything with the sh8601 panel_io; needs dummy-cycle config if ever wanted.
- Fizz now hides behind the wall band (clipped by dryT, turnaround at wall-r): with a wide band (glassWall 10 @ H 60) each bubble spends ~wall-r rows invisible per pass, so perceived density drops a little; scale fizzCount by bore/H if that reads as thin.
- Any `p<name>=<value>` write persists: `paramsTouch()` + `paramsFlush()` store the whole blob to NVS
  2 s later (device.py even sleeps 2.5 s on close to let it land), so `p!` is not the only destructive
  command — a plain param set silently replaces the saved copy too. A read-only "try this value without
  saving" path (or a `--no-save`/session-only flag in device.py) would make board experiments safe.
- Thin dark curved arcs run across the olive-oil tubes at fixed columns (visible with traces off, so not
  residue); source not identified — check the glass / lens overlays.
- The residue wet band tapers linearly over `wetFilm` px; a preset wanting a longer fade than its film
  would need its own width param.
- Sim `blend565`/`pxa` allocate three tuples per pixel; the residue pass calls it for every dry-side
  column of the residue range every frame. An integer 565 blend (like the firmware's `blend565T`)
  would cut the GC churn when a smear covers the whole tube.
- `tools/device.py` close from WSL: the python.exe bridge does not exit within `wait(5)` after stdin
  closes, so every session ends in `TimeoutExpired` (params were already restored; unclear whether the
  port then closes with the RTS-then-DTR order). Make the bridge exit on EOF, or kill it and re-check
  the reset banner.
- `tools/bench.py` cannot measure the dried-trace stage: the pinned scene (d0, inputGain 0) has no
  receding edge, so the residue dries out within `traceDry` and `--stage traces=0` reads ~0. A residue
  scene needs `traceDry` pinned high and a demo-speed drain first (see the scratch tracepin.py recipe).
- `traceFilm` (permanent film) costs ~9 ms per fully dry tube (every dry pixel goes through the
  blend: ~57 cycles/px, close to the loop's op count; the 5.7 ms "fully smeared" figure was helped
  by the opaque fast path). Cheaper design if the film becomes always-on: bake it into the tube
  back — a per-row film-over-back LUT keyed by a quantized streak level (8 levels x H), paint the
  back with it in step 1 and blend only pixels that are not the plain back (marks). Needs the sim
  mirrored; ~0 per-pixel cost.
- `x` pixel dumps over the Windows bridge can be incomplete despite an `END` marker
  (108/120 complete rows during the 2026-09-22 residue benchmark); reject incomplete
  captures before comparing pixels. The existing bridge-close timeout also recurred after
  settings were successfully restored and verified.
- Parallel PlatformIO builds in the same output directory removed objects during compilation;
  use distinct `PLATFORMIO_BUILD_DIR` paths for concurrent builds.
- `ble.cpp`: `NimBLEService::start()` is deprecated and now a no-op; remove separately.
- Digit shadow bake (2026-09-22) only covers sprite fonts; bitmap fonts (`digitFont` < SPRITE_FONT) still
  draw the shadow as a second glyph pass. Bake them the same way if anyone uses them with a shadow.
- Baked shadow approximations, both sim and firmware alike: in the wall-band fade rows behind air the
  two layers used to be scaled per row before compositing (worst ~50/255 on a few edge texels of the
  host scene set); with `markContrast` > 0 the luma floor now acts on the composite instead of per
  layer (presets free / cola / champagne / malt / cryo). Revisit only if someone sees it on the panel.
- Step 3e convex nose still calls newlib `sqrtf` (bit-by-bit software, ~250 cycles) per nose pixel. Only
  convex presets pay it; `sqrtApprox` (fizz ring) would do if 1/256 alpha steps are acceptable there.
- Meniscus `surfaceWidth` is not derived from the tube diameter; `-big` presets may want a wider band.
- Sim drawTube allocates `strokeR/strokeL` (and the compositor bounds) per frame like `edges`; fold into
  one reused scratch set if GC churn ever shows.
- run-sim has no way to load a user-exported JSON; a 3-line node helper turning the JSON into `p.<key>=` URL params worked (2026-09-23) and belongs in the skill.
- Cuvée also uses the current renderer's tuned values outside historical material ranges; its visual
  checks and JSON parity pass, but `check:presets` skips it. A modern material profile is still needed.
- Contact-angle meniscus (2026-09-24): the flick wobble (`cap`, ±12 px) still rides on top of the cap and can
  turn a near-90° end over for a moment (physical slosh); presets got class-default angles, not per-liquid values.
- Perf ceiling (2026-09-24, `e2e.sh --bare` = no BLE/IMU): spritz 34.9 fps / 21.4 ms (normal build 29.4), preset 1
  45.4 / 14.7 (39.1). BLE+IMU cost ~3–4 ms/frame. Spritz stages on bare: digits 13.0 ms, surface band 6.5, meniscus 3.3,
  fizz 2.1, minute ticks 2.1. Normal build `f` showed cores h 16 / m 27 ms — the minutes tube on core 1 sets the frame;
  rebalancing work between the cores is a candidate — see docs/perf-core-balance.md.
- Standalone HTML preview (2026-09-24): Chromium cannot start inside the sandbox (`sandbox_host_linux.cc`, EPERM); browser verification ran with approved escalation.
- Digit row-run compositor (2026-09-24) only covers sprite fonts; bitmap fonts (`digitFont` < SPRITE_FONT) still go
  through the generic per-texel `drawGlyph` template. Same row-run treatment would apply.
- Ticks (`drawTicks`) still call `Mark::operator()` per pixel, so every rear tick pixel runs the surface-band
  test; the conservative per-row band footprint from `drawSpriteGlyph` would let ticks use plain runs too
  (ticksM 2.9 ms, surfaceBand 4.7 ms on the current preset).
- Surface band costs ~3.2 ms per tube on its own (board, live tilt, digitParallax fixed): (a) band 0.3 → 0 took the hours core
  11.35 → 8.07 ms and minutes 18.07 → 14.87. Its own drawing (`bandRow`, per-row float mixes), not the marks.
- Parity for motion-only paths (trace-mode wet band, film > 0) can't be checked by compare-device.py, which
  snapshots the board at rest. A host harness rendering one `job.json` state through both render-ref.ts
  and a native render.cpp build would cover them without the board.
- The wet-band fix adds one float division (`b / A`) per band pixel in render.cpp; only ~32 px per row while
  a film is live, but it is a call on the S3 — fold into a reciprocal if the band loop ever shows in a trace.
- Parity 2026-09-25 (grey preset, board tilted: acrossTilt -0.98, angle -6, light -41): 4215 px mismatched
  (7.3%), all <= 12/255 but one at the tube's left edge, spread over every row and column band. Pre-existing:
  the reference is byte-identical before and after the wet-band fix and the film was below the band threshold.
  Sweep this pose against the pinned scene to find which pass drifts under across-tilt.
- Fizz shading (2026-09-25) leftovers: no draw-order sort by depth `z`, so a faded back bubble can paint over a front one where
  they overlap (common in packed foam); a 4-bucket counting sort over the static pool would fix it cheaply.
- Fizz ring is uniformly bright around the bubble; a per-pixel cos(angle to the light) modulation (one dot product with 1/r
  hoisted) would give the real dark-ring / lit-arc look at big sizes. Also: cylinder optics (deeper bubbles magnified more),
  scattering blur with depth, depth-dependent drift speed — none modelled.
- `compare-device.py`'s ">12/255 off" count swings ±50 px between runs of the same build (the meniscus crescents, liquid
  position dependent), so it cannot be a strict pass/fail number without pinning the liquid state.
- Fizz depth fade tints the core and pinpoint toward the CENTRE row's body colour (one blend per bubble; the rim per row): at
  full extinction a big bubble across the highlight band leaves a faint flat-coloured footprint. Per-row targets fix it at
  ~0.4 ms on a 240-bubble scene (Astra review, 2026-09-25); a 4-level depth quantisation with per-row tint tables would be free.
- The retired physical renderer's `Pbegin`/`P k=v`/`Pcommit` was the only batch; legacy `p` params have none, so
  `bench.py --preset` sends ~100 single `p` writes (each re-renders a half-applied look and re-arms the NVS autosave).
  A legacy `pbegin`/`pcommit` would make a preset load atomic.
- `e2e.sh --ref` across a PARAMS_SCHEMA_CRC change loses the board's NVS-tuned params (each flash resets them);
  a `p?` save before and replay after the A/B would keep them.
- Fizz kernel cost is per bounding-box pixel (~60 cycles), not per drawn pixel: a 16 px bubble's box is ~450 px for a
  ~150 px ring. Clipping each row to the outer disc chord (one sqrtApprox per row) would drop the ~250 outside pixels;
  the see-through interior skip already jumps the core. Heavy scenes (120 bubbles of size 16) stay ~25 ms regardless.
- PRESETS.md rules drift from coherence.ts: translucent shadeDepth doc 0.5–0.85 vs code 0.4–0.85; emissive liquidBright doc 1.15–1.35 vs code 1.15–1.5.
- coherence.ts fizz range messages say "for <viscosity>" (e.g. "for watery") where the range comes from the gas class; unclear wording.
- coherence.ts luma(#101010) = 15.999… so a grey-16 tube back passes the emissive "luma < 16" rule (float edge).
- coherence.ts `check` had an unused `id` param (dropped in coherenceIssues); tsc CLI tool builds (check:presets etc.) run non-strict.
- material/model.ts validateDesign checks only the JS type (+ hex for strings) of design numbers: Params has no bounds metadata, so `tubeHeight: 9999` passes; bounds would need a Params range table (gen_params.py has some).
- Two exported `Material` types now: params.ts (class tags viscosity/opacity/…) and material/model.ts (30 physical numbers); renaming the params.ts one (e.g. `MaterialClass`) would avoid alias imports.
- Physical materials (2026-09-25): the coherence checker's opacity bands leave gaps (0.12–0.25, 0.55–0.7); the derivation snaps
  a computed transparency to the nearer band edge, a visible jump while sliding absorption. Continuous bands would remove it.
- The checker's emissive rules are binary (lightPhys 0, dark backing); a weakly self-lit liquid in room light (the tide look)
  cannot be expressed by the derivation — `lightPhys ∝ 1 − emission share` would need the rule relaxed.
- The legacy palette cannot show a haze brighter than (1 − T)·255 on a clear liquid (its colour and mark visibility share
  `liquidTransparency`), so the derived body of clear liquids clamps; a separate haze term in `buildPalette` would fix it.
- Fixture numbers in docs/physical-renderer.md came from a Python prototype in the session scratchpad; derive.ts is the
  reference from block B on.
- derive: the KM ground reflectance lin(back)·E_b/E_l is capped at 1 (a near-white backing under a low wide light gives up
  to 1.41 and makes the K→0 branch singular); an illumination-split two-flux model would not need the cap.
- derive: the emissive dark-backing rejection uses luma ≥ 16 (the checker's `< 16`), the doc says "brighter than 16".
- derive: rejection 11 (coherence) is evaluated only when no material rejection (1–6, 8–10) fired, so a rejected
  material lists its own reason, not the checker's echo of it; a design error on a rejected material shows up on retry.
- derive: surfaceBlick = 0.9·highlightBright gives 1.17 for metal (highlightBright 1.3), above the UI range 0..1.
- Material mode: the legacy compositor's scalar `liquidTransparency` mixes the raw backing, so a tinted liquid on a light
  backing (spritz, pinot, phosphor on paper) derives opaque and its rear marks vanish behind the liquid; physically they show
  through the least-absorbed channel. A per-channel transparency in `buildPalette`/`throughLiquid` would restore them.
- Legacy LAYOUT_WIDE (tubeHeight 55, minutesY 224) and olive-oil (60 px at 185) rely on tubeLayout's silent clamp; derive rejects
  them (rejection 7), so material presets write the clamped row (185 / 180). Normalising the legacy presets would remove the gap.
- Legacy olive-oil preset has digitBright 2.0, above the coherence trim range [0.8, 1.8] (it has no `mat`, so nothing checks it).
- main.ts `flush()` is not serialised: a push batch that takes > 50 ms can overlap the next one. Material mode pushes every key
  on a whole-state change (mode entry, preset, import), so a slow BLE link would see interleaved batches.
- Legacy panel number twins print raw floats (derived values show e.g. 0.525130…); a per-step display format would read better.
- Legacy cuvee tickBright 1.5 and pinot/spritz tickBright/digitBright 2 sit outside the coherence trim ranges (no `mat`, unchecked).
- Material mode, body emission was added in encoded 8-bit space (molten iron derived cream instead of orange); the fix sums
  C + E in linear light before encoding. Any future "add light" law must add in linear.
- Material mode: T_up lets a pre-image reach 255 levels, but rejection 9 fires at luma 248 (the highlight floor's headroom);
  a T_up ceiling of ~247 would turn those rejections into a lower T (the self-lit boundary fixture moved 0.5 → 0.3 for it).
- Emissive bodies now shade only their reflected share (liquidLo ≈ liquid for glow/tide/xenon): with lightPhys 0 they read flat;
  a small emission-side falloff toward the walls (limb darkening of a glowing column) would restore depth.
- Glow derives opaque now (T_up holds a bright emitter near opaque), so its rear digits vanish (markContrast 0); its design
  may want digits on top (or, since markContrast is a design key, a floor up to 120·T).
- check:meniscus has no rimLight > 0 scene; an ad-hoc run (6 physical presets × 3 scenes) gave the same parity as rimLight 0
  (2106 vs 2228 differing px, max 9/255). Add one when the parity baseline is next re-counted.
- Glow's wall row overshoots the target in blue by one RGB565 step (8 levels) at rim tint 0: a ~1.8-level real miss of the
  luma-only shadeDepth fit, magnified by 5-bit truncation. Reported as `rim.bodyOver`, not rejection 12; a per-channel wall fit would close it.
- Wall targets go through `q565` (rgb565 truncates, not nearest): the 5-level tolerance sits below the 8-level 5-bit step, so
  any channel the fit cannot move reads 0 or 8. Comparing the RGB565 row to the unquantised target would be a fairer metric.
- Material `name`/`provenance` stay as loaded when a field is edited in the UI or by `?m.`: an edited value keeps its preset's
  "measured". Dropping the edited key's provenance (or the name) on edit would keep exports honest.
- `e2e.sh --preset` benches the pinned preset but bench.py restores the board's saved params before `compare-device.py`,
  so the logged parity line is always the board's default look, not the preset; keep the preset applied through the parity
  step (or pass it to compare-device.py) so `--preset` runs log their own parity (found on the honey run, 2026-09-25).
- groundReflectance caps Rg at 1, so for lin(back) > E_l (parchment #f1e6cf at the defaults: 0.88 > 0.70) E_l·Rg falls short of lin(back) and the "displayed colour is ground truth" law silently breaks for light backings; decide whether to let Rg exceed 1 or reject.
- bubbleRim on a white backing: 0.35·C0 carries the backing through a clear body, so frizzante's ring is luma 219 on #ffffff (faint), not the ≈0.45 grey the E_s term alone suggests; consider C⁰ (backing-free body) instead of C0.
- Material UI: a rejected design edit leaves the legacy input showing the refused value (params restored, panel not refreshed); refresh the row on rejection.
- material/ui.ts `warn` branch is unreachable: deriveReport already turns every coherence failure into rejection 11. Drop it or make coherence advisory.
- coherence.ts messages name some keys only in prose ("tube back", "contact angle", "a liquid"); derive.ts maps them with aliases. Returning `{ keys, text }` from coherenceIssues would remove the parsing.
- WSL headless Chromium has no emoji font (⛔ renders as tofu), so the status bar draws its markers in CSS; installing fonts-noto-color-emoji would make emoji shots honest.
- Material head row: the preset select is squeezed to "custo▾" at the 340 px panel width; give it its own line or shorten the checkbox label.
- Material fizz size is now free (2·r_b·pxPerMm, 1–16 px), but count stays class-bound (carbonated ≥ 30): big bubbles at
  the count floor may crowd the bore — consider scaling fizzCount by bubble area if a large-bead look reads busy.
- Big / dense material fizz raises per-frame fill on the board (trapped now up to 120 bubbles: glycerine 120 × 2.9 px, aerated-oil 90); bench `glycerine` before shipping it.
- Still (trapped) fizz under ~2 px reads as dust, not bubbles (1-px ring = one AA pixel); a size floor for slow fizz might help.
- Palette parity (firmware `Tube::buildPalette` rows vs sim `buildPalette`, via `#include "render.cpp"` + gen_params into a temp
  tree) was built ad hoc for the fizz-ring change and matched 27/27 palettes exactly; worth committing as a check (no board needed).
- Scalar `liquidTransparency` cannot show a saturated translucent filter over a light backing: T ≤ minᵢ targetᵢ/backᵢ, so a
  liquid that nearly kills one channel derives opaque on white (old spritz: T 0.0002). Transparent spritz now = paler
  absorption (B 0.3/mm caps T at 0.29); per-channel transmission in the mix would lift the trade-off.
- T_max counts backing channels ≥ 8 levels, so a near-black backing (cola's gradient, G = 8) snaps a dark-red body opaque
  over a 2-level miss; a threshold relative to the target (or ~16 levels) would stop that.
- Side-light rim uses only the view chord Tr(d_w) (≈2.4 mm), not the light's in-path, so caramel-spectrum liquids get bright
  gold edges (malt edges #e6dfbd, old cola #deca84); cola was darkened via exposure 0.8 instead.
- `check:materials` derives each material only on its own design, but the dropdown keeps the user's design: cola
  (absorptionR 0.01) passed its check yet was rejected (12, wall 9 levels over) on spritz's white design. A material ×
  every-preset-design sweep in the checker would catch that (xenon's design rejects every liquid by rule 11, exempt it).
- Contrast-floor direction at a near-tie luma (mark ≈ liquid behind it): sim (float luma) and firmware (1/1000 integer)
  can pick opposite directions → 66/255 parity misses (bitmap digits, markContrast 40, T 0.4). A shared integer luma or a
  small dead band would fix it; check:meniscus's marks-across scenes run with markContrast 0 because of it.
- Rear marks under the surface-band dish differ sim↔firmware by 16–17/255 (two 565 steps; remaining mode even with
  markContrast 0). check:meniscus's marks-across scenes run with surfaceBand 0 because of it.
- markContrast ceiling 120·T (coherence MARK_CONTRAST_PER_T) is a first guess at "to some degree"; retune on the panel.
- Wet share weighs every tube row alike, so across a concave meniscus it falls as 1 − √((x − xe)/cap): half the warp
  change happens in the first quarter of the meniscus. Weighting rows by their lens depth might read smoother.
- check_render_frames.py only proves pure refactors; a "neutralise feature X" flag (like --no-fizz) would show that only
  the intended scenes changed after a behaviour change (the wet share changed 3523 / 9136 strips).
- Meniscus-ramp columns use the per-pixel generic mark path (drawRampColumn): host +8–10 % render with digits under both
  menisci. Rows are constant per column there, so a column-run variant of the sprite runs would cut it if the board shows it.
- Device parity with a moving free slug is dominated by frame/state skew; the wet share doubles its >12/255 count per
  sub-pixel skew. Dumping the state at the frame's physics step (or pausing physics for the dump) would make it a gate again.
- Internal RAM is ~2.7 KB from full once BLE is up (`s` heap 2684, 1940 after a compare-device session): any new static
  in render.cpp/Tube hangs BLE init (black screen, no `ready.`). A boot-time check that fails visibly when the internal
  heap after ble_init drops under a margin would turn the hang into a message.
- IMU runs at 500 Hz ODR with the QMI8658 LPF off (imu.cpp CTRL5 = 0) and is read at 50 Hz: everything above 25 Hz
  aliases into the physics band, and `accelLpHz` 15.2 at 50 Hz barely filters (85 % per pole per tick). Enabling the chip
  LPF (or a lower ODR) is a free anti-alias before any accelLpHz trade-off.
- `check_render_frames.py --reference` must point at a copy outside `firmware/src` (e.g. a scratch file): a render.cpp
  inside a worktree's `firmware/src` includes that tree's own headers, so a header change on one side yields thousands of
  bogus diffs (TubeState layout mismatch). The tool could copy the reference into its tempdir itself.
- Rear ticks and rear digits share one wall, yet their lenses are separate keys (tickLens/bottomLens,
  tickDryLens/digitDryLens). Presets were aligned by hand (2026-09-26); nothing keeps them aligned — a
  coherenceIssues rule (or one dry-lens key derived from the vessel) would. Same for tickParallax vs digitParallax
  (6 vs 4.75 / 5.5 in olive-oil, pinot, spritz, cuvee, tide): ticks slide against the digits under tilt.
- Tick heights at digit positions were clamped by a throwaway script (2026-09-26): ≥2 source rows and ≥1 screen
  row clear of the digit (incl. shadow) under both lenses. check-presets could assert the same so new presets
  and design edits can't reintroduce ticks running into digits.
- Phylactery photo study: local `sim` could not import Playwright; used the saved renderer screenshot as the image-generation reference. Capture a fresh frame when preview dependencies are available.
- Fizz spring (`fizzSource` 1): the plume is a straight bead line — no lateral wobble/widening as it rises; a
  few springs (or a spring line) would read more like an aquarium. Only Subtle soda (gas `spring-pearls`) uses it.
- Fizz spring rebirth x: firmware ensureFizz treats "surfaces published" as `fizzLen > 0`, sim as
  `fizzSurf.length === H` — they differ for one frame after a tubeHeight change (stale rows in firmware).

## Presets / gas (2026-09-27)
- Only a preset's signature gas is coherence-checked; switching a checked preset to foam-ring (80) or pearl-bead
  (64) leaves the carbonated 30–60 count range. Check every listed gas, or trim those models, if it matters.
- `presets/1.json` is a stale dump with no PRESETS entry (dump:presets never deletes files).
- Preset `note`s still describe the signature bead ("fine bead", "trapped air"), which reads odd with another gas picked.
- `presets.zip` (+ `:Zone.Identifier`) is still in the repo root; its keepers now live in `params.ts`.

- Legacy preset → tick loads the physical twin only within the page session (the pick is not persisted; after a reload the tick uses the stored material). `-big` legacy presets have no twin id, so they fall back too.
- The legacy preset dropdown keeps showing the last pick after a device pull (only reset/import clear it).

## Wall glow dry-only (2026-09-28)
- `wallWet` < 1 (Xenon) reaches the palette only: rear marks in the band over a gas column still composite through
  the contents instead of fading by dryT as behind air (Mark path, sim markFn + firmware Mark and sprite fast paths).
- `wallWet` between 0 and 1 blends the liquid and empty-tube rows; physically the contents' reach edge moves through the band.
- The glass's glow ignores light an emissive contents pipes into it (plasma, bioluminescent): only the side light `E_s` feeds it.

## Spring fizz covered/dry (2026-09-28)
- Subtle soda has `freeHomeK` 0: after a slide the slug stays wherever it stopped, so the spring stays dry until the home end is tilted down.
- SPRING_BACK (3 s) is a constant in both renders, not a param.

## Spring stream held by glass (2026-09-29)
- Moving the Fizz pools (static, 2 x 4.8 KB internal) to PSRAM in render_init measured +9.8 KB free internal heap on the board (2.2 -> 12 KB, BLE fine).
- `sim/src/material/model.ts` is generated from spec/material-schema.json; a new design key goes in the schema, then `npm run gen:material`.

## Meniscus on the bore (2026-09-29)
- Wall band now eases the cap C1 onto the ring at the outer edge (was a vertical cut); the dry band past the ring still gets no film/refraction of its own.
- Spherical cap assumes bore ≪ capillary length; several presets are outside that regime (flattened, gravity-shaped menisci not modelled).

## Meniscus help text (2026-09-29)
- `PARAM_META` help is stale vs derive: `contactDyn` says "honey 180°" (derive clamps to 90); `capLength` says "water 2.7, oils ~1.9" (derived display-scaled values are 2.17 / 1.5–1.8 since the bore-radius change).

## Vertical watch mode (2026-10-01)
- Vertical: fizz core/pinpoint light still comes from panel-left (= from below as worn); `lxS` could follow the pose.
- Vertical: phone "device orientation" input is mapped for landscape only.
- Vertical: leather overlay lighting/gloss just rotates with the panel; calibration / hello faces on the board stay landscape.
- Vertical: labels are centred across the tube with no offset knob (`digitBottom*` unused); two-digit labels can sit on long ticks or clip in narrow tubes.
- Vertical mode could switch by itself from the IMU pose (auto / hysteresis) instead of a param.
- Vertical: rear ticks and digits still have separate parallax (`tickParallax` depth-scaled in panel rows, `digitParallax` in source rows): a hard across-tilt can close the tick–label gap by a pixel or two.
- Landscape: `tickLens` ≠ `bottomLens` (or the dry pair) can still slide ticks onto labels behind liquid only; same one-wall remap would fix it but changes existing presets' look.
- Vertical: a tick takes one wet share (its centre column) while a label takes one per column; under a steep meniscus the two can sit a share apart over a wide label.
- Rear tick ends are whole rows: across the meniscus an end travelling N rows (strong lenses: 6 at H=37) moves in N one-row steps, the first as early as share 1/256 when the dry end sits on a row centre (2.9 % of a sweep). Not a table→remap seam (remap at share 0 = dry table, checked). Sub-row coverage on the end row would smooth it — both modes, changes the dry look.

## Fizz fps collapse (2026-10-02)
- Fixed: spring births wait at the tube's `fizzCount` share (sim + firmware). Worst case on the board (pitching, across ~0, `fizzCount 120`) is now 21-25 fps, was 5-10; left over at ~210 live bubbles: render +10 ms, fizz step 3-4 ms x 2.2 steps.
- `liquid_tick` runs `stepFizz` once per 50 Hz catch-up step (up to 5 a frame): a slow step feeds back into itself. Fizz is cosmetic — one call per frame with the summed dt would break the loop.
- `settleFoam` packs pairwise over all parked bubbles (3 sweeps, `discFit` + `sqrtf` per placement): ~8 ms a step at 124 parked, 20-30 ms at 200. The sweep is sorted front to back, so it can stop at the first pair farther apart than two max radii.
- `stepFizz` free bubbles cost ~15 us each per step (`discFit` = a `sqrtf` per disc row, `touchesFoam` scans every slot).
- `stepFizz` runs with `fizz=0` too (measured 1.4 ms a step, bubbles keep accumulating), so bench.py's `fizz=0` stage only sees the draw cost.
- One long-lived bubble in a high slot keeps `fizzN` at its high-water mark (seen: 45 live in 226 slots); every per-step loop walks the idle slots.
- `display_push_strip_async` blocks ~6.2 ms a frame (each band's window command waits for the band before it); it is in neither `render` nor `push-wait`.
- `tools/tilt.py` swings are open-loop host timing (serial round trip per pose); a firmware-side pose script would give repeatable phases.
- No check exercises `stepFizz` on either side (compare-device turns fizz off, check_render_frames never steps it, replay-check only `stepTube`): a host/sim population check under a reversing tilt would catch a spring-block divergence.

## Failing checks fixed (2026-10-02)
- Sim glyph coverage now uses the firmware's 1/256 steps (`drawGlyph`); the rest of `markFn` is still float where the firmware truncates (`cov * through`, `* transK`, `* dryT`, bakedT `cov / a`), and so are tick emboss coverages: the same one-step class, can stack where a tick and a digit share a pixel.
- `check:imu` material loop: no preset is `vertical`, so the vertical home path is only covered by the default-params block.
- 10 presets are always free (`freeHomeK` 0, `readTilt` 0/1): held level they never park, so the time reads only with the home end down.

## Imminent residue (2026-10-02)
- Hand-off for the residue physics items below (deposit law, dried colour, drainage): `docs/residue-physics-handoff.md`.
- Residue deposit skew is not stored: physics lays each deposit at the edge's mid-row centre, the renderer only bends the smear onto the contact line within Z of it. A per-column skew byte (tanA at deposit time) would keep an old smear slanted where it was laid; it costs the plain-residue fast path a per-row gather.
- ~~`traceThin` makes fast recession deposit less; entrained films go the other way (Bretherton, h ∝ Ca^⅔). Flipping it with traceAmount 2 painted the whole smear opaque green: the dried endpoint `traceRows` (opaque shading × 0.85) reads denser than the column; a dried dye stain is a Beer–Lambert tint too.~~ — done 2026-10-02: deposit = `filmEta(p, U)`, stain = B^(1−τ)·C^τ, `traceThin` retired (v26).
- ~~Upright tubes dry the residue up to 5× faster (`TRACE_TILT_DRY`); gravity drains a film (signed flux toward the low end, conservative), it does not evaporate it. Drain-back by distance (`traceFollow`) ignores gravity's sign.~~ — done 2026-10-02: `traceWet` + `drainTrace` (upwind, h³, integer-conservative); drying tilt-independent.
- The wet film rides the edge's `film*` follower (one value per edge, decays 2/s once the line stops); a per-column film thickness (L × u16) would let a stopped film thin from the top down instead of all at once.
- Sweep mode (`minutes sweep`) moves the edge through `fillTarget`, which `edgeVel` does not see: no wet film, no pull, no dynamic angle during a sweep drain.
- Step 3c (traces off) still draws the old faint 0.35 · film band instead of the film law.
- e2e.sh `--ref` copies `.pio/libdeps` into the temp worktree, yet PlatformIO still reinstalls the libraries there on every ref build (seen 2026-10-02).

## Residue physics (2026-10-02)
- Flat watch: no capillary pull toward the meniscus, so the wet film now dries in place (it used to drain back by distance). A short-range pull near the line would bring that back.
- One colour law for every liquid (Beer–Lambert). A scattering one (blood, milk) would want coverage or Kubelka–Munk; Params carries no scattering key to choose by.
- ~~`traceFilm` keeps its `(1 − liquidTransparency) / traceAmount` cap~~ / ~~`traceGamma` (0.65) lifts a physical thickness~~ — done (Astra review): the stain depth is the coat's annular path × traceAmount; gamma and cap gone.
- The stain fades at the solvent's drying rate (Astra: a non-volatile dye would stay). Kept by choice: a separate, slower fade or a stain that waits for the liquid are the options.
- Hand-made presets get `legacyTraceDrain` from contactDyn/capLength: contactDyn tops out at 90°, so a syrup drains ~5× faster than its material would (honey 1.16 vs 0.19 px/s), and a hand-made "glycerol" with contactDyn 8° drains like water.
- The drain flux is floor-quantised: films thinner than ~(TRACE_FULL² / (traceDrain·dt/3))^⅓ never move (a honey film below ~22 % of the cap; at 0.2 px/s it would not move visibly anyway). They dry in place.
- The dry stain under an advancing liquid is not dissolved (only the wet part merges). It is hidden by the body and overwritten when that column is uncovered again.
- The user's repro preset (contactDyn 8°) is watery by its own dynamics: its residue is now wall lines at most, mostly invisible.
- `docs/residue-physics/tiltshot.mjs` is wall-clock timed, so before/after shots of a sliding slug never line up. A fixed-step replay would make A/B frames comparable.
- `docs/hardware-handoff.md` slot geometry is stale (4 mm bridge, slots at 5.0/14.9 mm): `spec/layout.h` / preset 1 now have hours y 0–72, minutes y 168–240 → 8 mm bridge, and tubeHeight/hoursY/minutesY are per-preset runtime params.

## Boards / native LCD canvas (2026-10-27)
- Pre-existing sim/firmware render gaps: `check_board_render.py --board amoled191` (pinned scene, fizz off) puts 22 of 77
  presets beyond 12/255 on a few px (glycerol-dark 178 px, physical/honey 10, free 10; worst 99/255), identical at HEAD.
  The same class shows on the LCD canvas. Find the term (likely a float threshold at the meniscus / band).
- Only the named px constants scale with PX_SCALE (FILL_SLOSH / CAP_DYN / FILM_FULL / TRACE_DEPOSIT / FOAM_CATCH, glyph
  pool); inline px literals in render (1-px rims, `xs + 2`, blick rows …) stay canvas px.
- `TRACE_DRAIN_MAX_PX_S` (48) is a stability bound in canvas px, so on the 4/3 canvas the fastest drain is 3/4 as fast
  in design terms. Raise `TRACE_DRAIN_STEPS` with PX_SCALE to keep it.
- Upscaled canvases (RENDER_H < 320) are nearest-neighbour: every 3rd / 4th / 9th line doubled. Bilinear in the push
  would be smoother, at a per-pixel cost in a PSRAM-bound loop.
- `check_meniscus.py` and `check_render_frames.py` are AMOLED-only (536 hard-coded); `check_board_render.py` covers the
  LCD canvases preset by preset but no motion / residue scenes.
- Leather overlay (`overlay.ts`) pads are AMOLED px; on the LCD canvas the cuff is relatively thinner.
- `device.py` bridge: 3 of 7 e2e runs (2026-10-27 sweep) had the Windows bridge not exit within 20 s after bench.py
  ("bridge did not exit, killed"), and compare-device.py then hit "Access is denied" on COM11; a retry loop on open
  (40 × 0.25 s) is too short for that case.

## LCD perf follow-ups (steps 1-8, triaged 2026-10-30)
Facts / lessons moved to the firmware-e2e skill; dead ends to docs/lcd316-perf-plan.md ("Dead ends").

### Bench / tooling / host checks
- Host emulation of the ~10 PIE ops used (digits, ramps): the host tools prove the scalar path only, the SIMD one is
  proven on the board (-DDIGIT_VERIFY).
- The USB serial path loses whole lines of long replies now and then (`X`: 8 of 350, in pairs; the `x` dump's rows)
  with room in the CDC ring; likely sFlush skipping while `Serial.isConnected()` reads false over a Windows host read
  gap (unverified). check_board_steps tolerates it; the `x` dump is only re-asked.
- `compare-device.py` never closes its Device (no bridge cleanup, no dwell after a `p` write).
- `X` / check_board_steps.py can only A/B builds that have `X` (2026-10-30 on): no board reference for older commits.
- No preset's spring is slid dry by the seq.h script (springScatter stays 0): only check_fizz_steps' built-in spring
  scenes reach that path.

### Structural perf (next: 1-4 in order)
1. Marks (ticks, digits), fizz, bubble, top into the tiles: they still run on the PSRAM strip through the cache after
   the tiles, on lines the tiles left cold (wet int digit px ~0.55 us on the hours core vs ~0.32 dry on core 1). Per
   tile: a facts pass first (band layer weights / strokes, wet share for every row), a row clip in drawLabels /
   drawTicks / drawBubble; then the strip is DMA-only (no writeback before the gather).
2. Hash each tile at render time (internal RAM) per line pair: the push skips gathering unchanged segments (pinned
   ~85 %); a hash table per strip, the lens row map folded into the segment test. Replaces the push hash pass (~10
   instructions a strip word; else two interleaved chains or PIE, ~1 ms a frame).
3. Push store phase ~2.6 ms a strip swinging (~500 changed segments: fbuf line fill + writeback through the cache):
   GDMA-scatter of whole interior segments into fbuf; needs per-line invalidates against the refill ISR's cached reads
   and no CPU-dirty fbuf lines in those segments. Untried alternative: ROM `Cache_Occupy_Addr` (allocate without
   fill? "do not call", semantics unverified).
4. Tile copies to PSRAM at ~26 MB/s (32-B bursts: RX into PSRAM must be burst-aligned, a 4-row tile of 1,640-B rows is
   only whole in 32 B); 64-B bursts read at ~43 MB/s. Strip stride 1,664 B (or 8-row tiles): hours put-wait ~1 ms
   swinging, ~2 ms pinned (the minutes gather competes on PSRAM).
5. Physics on core 0 next to core 1 (the worker idles during the steps): stepFizz is per tube independent apart from
   foamOrder and the draws; ~0.3 ms a frame pinned, ~1.5 swinging.
6. `CONFIG_ESP32S3_INSTRUCTION_CACHE_32KB` on the LCD: the 16 KB I-cache is shared by both render cores and the render
   code is several times that (2 KB of ticks into IRAM moved the pinned render ~2.5 ms). Costs 16 KB internal RAM; may
   replace part of the IRAM code.

### Exact kernel levers (backlog, ~0.2-1 ms each)
- Exact inline divide (div0.s / divn.s, like sqrtExact): buildPalette (~1.0 ms a tube per light change: cosf,
  ~6 __divsf3, 4 q() a row), drawBubble's 4-5 __divsf3 a bubble, the 3e setup.
- Ramps (soft edge + glow) are bound by their per-pixel float alpha chain (~100 cycles): rows with bitwise-equal edges
  (symmetric halves of a level tube) could share one T run (memo keyed on ex and the frame's terms); pinned, ~0.6 ms a core.
- Residue zone (~2 ms a tube swinging, ~300 cycles a px) recomputes tint.at(T) per px: per-row T -> colour memo
  (stamped, PSRAM), ~10 %.
- Disc kernel ~7 us a row on the hours core for ~4-5 px (AA root ~90 cycles, blend ~130, tests ~100): two px a step to
  overlap the root chains, 1-iteration bounds for chord / core / reach (conservative margins).
- 3e band kernel (bandRow) ~280 cycles a px: first layer's premultiplied sum lazily (exact: first P = C a, A = a),
  inner / outer lanes hoisted; ~0.2 ms a core.
- pieBlend (byte-swapped 565 run toward per-px colours by T 0..256; ramps / glow / traces since step 6): ticks could
  feed it the same lanes.
- settleFoam's pack (3 sweeps, pairwise, place() with discFit) is the largest physics part in motion (~130-290 us a
  step with 40-60 parked); see the dead ends before touching it.
- Sprite digits no longer read DigitRow::nb / b0 / b1: the shared tick facts still compute them.

### Memory / BLE
- Free heap with BLE ~4.4 KB on the wide LCD build; a BLE connection at this heap is untested (Windows python has no
  `bleak`). Known room: `-DTUBE_BAND_INLINE` +13 KB (~2 fps), PushSlots 16.4 KB to PSRAM (cost untested), settleFoam
  IRAM 2.3 KB (~50-90 us a step), the 32 KB I-cache option (structural 6).

### Look options (each needs a board round)
- `fizzCount` is per tube: the LCD tube is 901 design px long at physical size (615 with LCD_FILL; 536 on the
  AMOLED), so bubbles are ~40 % sparser along it. User wants it scaled (separate chat).
- Per-radius / subpixel-phase coverage sprites for the fizz: per-px work ~2-3x less; ~0.8 ms of ~1.2 pinned to gain,
  swinging ~4.6 ms at ~70 bubbles.

### Robustness / parity
- LCD: an NVS save holds the bounce refill ISR off ~14 ms (cache off during the flash write): one bad frame per param
  change since `RESTART_IN_VSYNC=n`. Save only while the face is still / off, or PSRAM XIP so flash writes keep the
  cache on.
- check:meniscus `marks-floor-120` fails on one px (17/255): the body's soft-edge ramp is one 565 step off there before
  any mark (sim a5b7 / fw a5b8, also at HEAD: 9/255), a whole-px digit blend stacks on it. Lever: the edge ramp's
  rounding parity.
- IDF 5.5.5 esp_restart_noos does not wait for a running D-cache preload (fixed here in preload_shutdown); the stock
  RGB driver's bounce refill preloads the same way: worth an upstream issue.

### Notes
- `FB_BOUNCE_LINES 0` (DMA from PSRAM) lost its VSYNC restart with `LCD_RGB_RESTART_IN_VSYNC=n`: a DMA underrun there
  drifts until reboot. Call `esp_lcd_rgb_panel_restart()` per frame in that mode if it is ever used again.
- The skipping push is native-only (1:1, USB_LEFT 1): scaled canvases (RENDER_H < 320), USB_LEFT 0 and the A/B face keep
  the per-pixel loop.
- AMOLED keeps esp_random for the fizz draws (8 B static RAM for the per-core xorshift); ~16 B left under its 88.4 KB bar.
