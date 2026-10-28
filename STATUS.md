# Liquid Watch — STATUS

_Last update: 2026-10-27 (LCD-3.16 full-screen canvas, board switch)_

## Board switch + full-screen LCD canvas (2026-10-27)

- One switch for board and canvas: `LW_BOARD` (amoled191 | lcd316) / `LW_RES` (lcd316 canvas rows RENDER_H 240 / 256 /
  288 / 320, default 320 = native) or `--env` / `--res` on flash.sh, flash-win.sh, e2e.sh (`--define NAME=V` for any -D).
  Sim: `?board=lcd316&res=320` or the "board" select in the top bar (reloads; remembered in localStorage); node tools
  read LW_BOARD / LW_RES. Firmware `v` → `board lcd316@320 canvas 820x320 panel 820x320`; the sim warns on connect
  when its canvas differs, compare-device.py takes the board's canvas from `v` and the `x` dump's `LAYOUT` line.
- `spec/layout.h|ts`: PANEL_W × PANEL_H is the canvas the face renders. LCD: the panel's 41:16 aspect, RENDER_H rows,
  tubes full length (820 px native) along both long edges, upscaled nearest-neighbour to 820×320 in the push.
- Params stay in design px (the AMOLED's 240-row canvas): presets, the panel, `p` writes, `p?`, NVS. `boardParams`
  (sim params.ts, firmware physics.h) scales the 41 PX_KEYS by PX_SCALE = RENDER_H / 240 and rounds the 22 whole-pixel
  ones (positions, tick / bubble sizes, baselines, shadow offset); gen_params.py reads both lists from params.ts
  (`ParamField::px`). Named px caps (slosh, cap, film speed, deposit, foam catch, glyph pool) scale too; MM_PER_PX is
  0.083 / PX_SCALE (same bore in mm). Material layer, migration and legacyTraceDrain use the design constants.
- AMOLED unchanged: check_render_frames vs HEAD byte-identical (9136 strips), check:meniscus identical to HEAD (339
  scenes), presets re-dump identical, RAM 88296 B as before (`eff` aliases `params` at scale 1).
- New `tools/check_board_render.py [--board B] [--res N]`: host sim-vs-firmware render of every preset on any canvas.
  lcd316@320: 54 of 77 within 12/255; the AMOLED has the same class of gaps in 22 presets at HEAD (KAIZEN).
- Board parity (preset 1): native 884 px off, 0 > 12/255; 256: 0; 240 / 288: 2–5 px > 12/255.
- LCD bench, pinned scene, preset 1 (`e2e.sh --env lcd316 --res N`; SI = strips in internal RAM):

  | RENDER_H | canvas | SI | fps | render ms | push ms | frame-p95 | heap free |
  |---|---|---|---|---|---|---|---|
  | 240 | 615×240 | 0 | 21.1 | 26.9 | 18.6 | 48 ms | 169.6 KB |
  | 240 | 615×240 | 1 | **28.0** | 17.7 | 16.2 | 37 ms | 67.1 KB |
  | 256 | 656×256 | 0 | 18.9 | 30.3 | 20.6 | 54 ms | 166.3 KB |
  | 256 | 656×256 | 1 | 25.3 | 19.9 | 17.8 | 40 ms | 51.3 KB |
  | 288 | 738×288 | 0 | 17.0 | 36.6 | 20.2 | 60 ms | 161.4 KB |
  | 288 | 738×288 | 1 | 23.3 | 24.0 | 17.0 | 44 ms | 13.9 KB |
  | 320 | 820×320 | 0 | 13.2 | 44.9 | 28.6 | 77 ms | 159.2 KB |

  Default SI per build since: 1 up to RENDER_H 288 (a strip ≤ 141.7 KB), 0 at native (175.5 KB does not fit).
  Two limits, both PSRAM bandwidth: PSRAM strips render ~1.4× slower (and two of them slow each other), and the
  push (the strips turned into the 525 KB framebuffer the LCD DMA scans) costs 16–29 ms at every resolution — it
  always writes 820×192 px. Next: replace the push (plan doc, "Display path").
- Native, user preset (scratch copy; tubeHeight 54, 120 fizz, residue, sprite digits behind liquid, markContrast 26):
  13.7 fps → 15.2 (lens row map applied in the push, not as a PSRAM row shuffle) → **18.0** (64 KB / 64-B-line data
  cache, env lcd316's own recompiled libs, see platformio.ini). Parity 0 px > 12/255 throughout.
  Tried and dropped: bounce-buffer scan-out (`LCD_SCAN=1`, kept for experiments: 39–50 % of a core in the fill ISR,
  no fps gain, tears), divisions out of throughLiquid, IRAM hot loops, glyph pool / strip alone in internal RAM, a
  per-texel through-liquid memo (KAIZEN). Digits are still 15 ms of 36; markContrast 5.8 ms of them.
- Contrast floor of rear sprite digits (with a baked shadow plane) baked into the behind-liquid plane against the liquid
  body colour (sim / firmware `bakeFloor`), drawn without a per-pixel floor: transparency and refraction as before, the
  floor no longer follows shading / bubbles / glow behind a digit. All boards. Native user preset **19.1 fps**,
  markContrast now ~0 ms; host parity better than before (AMOLED: 9 of 77 presets with a few px > 12/255, was 22).
  Awaiting the user's visual check.

## Second board: Waveshare ESP32-S3-LCD-3.16 (2026-10-27)

- Env `lcd316` (`pio run -e lcd316`; plain `pio run` and the tools still mean `amoled191`): ST7701 RGB LCD 320×820,
  `display_lcd316.cpp` = bit-banged 3-wire SPI init (Waveshare demo sequence) + esp_lcd RGB panel, framebuffer in PSRAM.
  The 536×240 canvas is shown **1:1, centred**, each strip turned a quarter into the portrait framebuffer on push.
  Sim, presets, parity tools unchanged. `board.h`: IMU pins (SDA 15 / SCL 7) and the IMU turned into the AMOLED's
  frame (180° about y), so the `i` stream and the sim read both boards alike.
- Pixel clock 16 MHz (46 Hz refresh): Waveshare's 18 MHz made the picture jump sideways and back now and then (the
  DMA falls behind reading PSRAM); 16 and 14 MHz steady by eye.
- Push = CPU quarter-turn, ~7.1 ms/frame, PSRAM-bound (32-bit stores and pushing from both cores gained nothing).
  Internal heap 3.6 KB free with BLE (ADC driver for the battery ~0.5 KB, allocated at boot).
- PCF85063 RTC (`rtc.cpp`, `board.h` `HAS_RTC`): `T` writes it, power-on restores the clock from it (before the NVS
  copy) when its oscillator ran and this firmware set it; without a backup cell in the RTC header it only bridges
  resets, not power-off. `s` ends with `bat X.XX V` (GPIO 4, 200k/200k). I2C `Wire.begin` moved from `imu_init` to `setup`.
- LCD black is backlit grey: margins and bridge glow; presets were tuned on AMOLED black.
- Single framebuffer written while scanned: no tear visible on a sloshing board; a VSYNC-locked push would cap fps at 46 / 23.
- Tools: `flash-win.sh --env lcd316 [--full] COMx` (`--full` once on a board with other firmware), `flash.sh --env`,
  `e2e.sh --env lcd316`. `device.py`: retries the port while Windows still holds it ("Access is denied"), waits up to
  20 s for the bridge to exit (it raised after 5 s and stopped e2e.sh before parity).
- Verified on the board: orientation and colours (`h`), IMU directions (liquid runs downhill both ways), no jump at
  16 MHz. `e2e.sh --env lcd316 --no-flash`: **47.5 fps**, render 11.89 ms (pinned 10:09:30, board NVS preset);
  parity 666 / 77184 px mismatched, 0 > 12/255. Pinned A/B of the clock: 50.0 fps at 16 MHz vs 50.8 at 14 MHz.
  RTC: `T`, then a simulated power-on (system time zeroed + `clockRestore`) 3.5 min later restored the exact time.
  AMOLED: `pio run -e amoled191` builds (RAM 88.3 KB, unchanged); not flashed (board not attached).
- Astra review (codex, serious bugs only, 2 rounds): flash scripts ignored `$LW_PORT` (wrong board with two attached;
  `e2e.sh --ref` now routes the old tree's flash itself), the RTC's I2C handle was allocated on the first `T` after a
  soft reset (now `rtc_init` at boot, calls refused if it failed). All fixed and re-flashed.
- Next: native 820×320, `docs/lcd316-native-plan.md` (firmware spike first, ≥ 30 fps gate; PSRAM bandwidth is the limit).

## Wrap retract (2026-10-27)

- A full tube no longer empties in one tick at the wrap (minutes at the hour, hours at 12): `followClock` (sim
  `physics.ts`, firmware `physics.cpp`) eases the column back over `RETRACT_S` = 2 s (smoothstep) onto the clock as
  it runs on. Wrap = the clock's fill falling back by over half the scale; `remaining` mode refills the same way.
- A clock set snaps: firmware `t` / `T` / NVS restore (`setClockLocal`), sim time controls (set / real / reset view).
  Sweep toggles and demo speed changes do not snap.
- Residue follows the retracting edge (blood: a faint film along the tube, dries in seconds).
- Verified: `check:imu`, `check:meniscus` (339 scenes, max 9/255, UBSan clean), `pio run` (RAM +12 B), sim
  screenshots through a 10:59 → 11:00 wrap (default, blood). Not flashed.

## Vertical watch mode (2026-10-01)

Param `vertical` (bool, Shape group, design key; default off): the watch worn upright, USB end down, hours tube on the left.
- **Liquid** always rests at the bottom (panel left end): the render/physics mirror is `mirrored(p) = remaining && !vertical`.
  `remaining` then only flips the scale and the column length: off = digits 1..11 / 5..55 bottom to top, liquid = time
  passed; on = digits top to bottom, liquid = time left.
- **Digits** are turned a quarter to read upright; a label's digits advance across the tube, centred on the tube's axis
  (`digitBottom*` unused; starting at the near wall if too wide) and on the tick along the tube. Scale X stays the
  along-tube scale (glyph height), Y the across one (glyph width). Sprite planes are baked already turned (same pool,
  no new buffers); bitmap fonts turn in the sampler; the shadow stays down-right as read.
- **Rear ticks under rear digits** share the wall and the axis across the tube, so the liquid moves both by one remap,
  the digits' (`digitDryLens` → `bottomLens`): where a column is wet, a row is tick when the digit source position it
  shows lies wallward of the one under the dry tick's end — unrounded maps (axis-relative float offsets), evaluated at
  the column's wet share, plus the labels' own row rounding as a bound (`TickFollow`, sim + firmware). `tickLens` is
  unused in this case; on-top ticks/digits and landscape unchanged. A tick one clear row short of a label behind air
  stays off it behind liquid and across the meniscus. Firmware: 2 x 80 floats per tube, PSRAM from `render_init`.
- **Physics**: along-gravity is carried by the tube's bottom end — no static edge offset or edge light from it; the
  free slug, film drying and the light angle still feel it; the light angle fades to `lightAngle` when the
  cross-section sees no gravity.
- **Pose**: upright (bottom end down) is the reading pose — only gravity toward the top end or across the tube counts
  as tilt. The front settles at the tube's in-plane tilt from the vertical (level upper surface, the liquid on the low wall whichever end is down, cap 45°, `angleTiltGain` /
  `angleMax` unused; `angleK` / `angleDamp` still set the speed). A slug pressed into the wall it rests on has no
  rebound (both modes): no residual `slugVel` / film.
- **Sim**: the panel is shown turned (drag-tilt remapped); manual input rests upright (along -1), "centre" and
  "raise wrist" follow. `?p.vertical=1`. `check:imu` has a vertical block (upright rest, ±30°, flat, turned over).
- Verified: landscape byte-identical to the previous renderer (`check_render_frames.py`, 9136 strips); 8 new vertical
  parity scenes in `check-meniscus.cjs` (sim vs native firmware, max 9/255); `pio run` builds. Params schema CRC
  changed (the board drops its saved blob once). Not flashed / not seen on the board yet.
- 2026-10-02, ticks follow the digits' remap: landscape still byte-identical (9136 strips); 10 vertical parity scenes
  (2 with different tick / digit lenses) within 12/255; `check-meniscus.cjs` table checks — identical wet/dry optics
  move no tick (plateau case H=80, lens 1), and a lens/height/label sweep keeps one-row dry clearance at every wet
  share 0..256; `pio run` builds. Not flashed.
- 2026-10-02, slug skew (both modes): `angle` is the time edge's lean onto the low wall; the home edge of a free slug
  leans the other way (`edgeSkews`, sim + firmware) — a trapezoid, not a parallelogram, so the gravity-ward end no
  longer has its long leg on the high wall. Vertical: the sign follows across alone (no flip when turned over, no
  ±0.15 g band; on its side the lean sits at the 45° cap). Off the end cap the two leans share one budget — the real
  gap (slosh included) less both caps' reach and the time edge's remaining free lean — so the lean never makes a
  short slug's ends cross. `check-meniscus.cjs`: 72 `skew-*` scenes (low wall longer, no crossing) and an 864-case
  slosh / unlike-caps sweep (never narrower than 0 unless the caps alone already are; 72 rendered), sim vs native
  within 12/255; non-free strips unchanged by construction (`check_render_frames.py`: only free-slug scenes differ,
  digit groups 0); `pio run` builds. Not flashed.

## Physical materials: liquids derived from physical properties (2026-09-25, astra-loop)

The physical simulator is finished as a **material layer over the legacy renderer**, not as the phase-1 standalone renderer
(retired the same day). A liquid is authored from 30 physical properties (`spec/material-schema.json`: refractive index,
absorption RGB in 1/mm, reduced scattering, emission, metallic, phase, density, viscosity, surface tension, contact angle
and hysteresis, solids fraction, drying time, gas mode/level/bubble radius/foam, bore radius, wall, wall index, light
elevation/size/intensity, ambient, exposure) plus a design object (marks, layout, backing, watch behaviour: the
`design.allow` list). `derive(material, design)` (`sim/src/material/derive.ts`, laws in `docs/physical-renderer.md`) fills
every legacy `Params` key — colour by two-flux Kubelka–Munk per channel on the cylinder trace, transparency as the two-pass
transmittance bounded by what the legacy scalar mix can show, dynamics through one viscosity coordinate `μ/(ρr²)`, Ohnesorge,
capillary number and capillary length (Cox–Voinov dynamic angle, Landau–Levich film, Stokes bubble rise) mapped onto the
watch's slowed regime by anchored monotone maps — and rejects (11 numbered reasons) instead of clamping. Every derived
`Params` passes the unchanged preset coherence rules (`sim/src/material/coherence.ts`, extracted from `check-presets.ts`),
so realism is by construction: `npm run check:materials` (≈1000 fixtures: doc fixtures, class boundaries, monotone
viscosity sweep, 800 seeded random materials × designs, real `buildPalette` centre and wall rows at 0 levels).
- **Sim**: "physical material" mode on the main page (`sim/src/material/ui.ts`): physical controls, derived legacy rows
  locked and shown live, design rows editable; the material dropdown changes the liquid only and keeps the user's design (a "preset's design" button takes the preset's), `?material=<id>&m.<key>=` takes both, envelope import/export, `check:material-ui`.
  Editor-style feedback (2026-09-26): a fixed bottom status bar (dot + summary + class/coords line; an "N problems" chip
  opens a problems panel listing every rejection with key chips — material / design / derived), and the rows a problem
  names are flagged red in the material group and the legacy panel (`DeriveReport.problems` carries the keys; clicking a
  problem reveals and focuses its first control).
- **Collection**: 22 material presets (`sim/src/material/presets.ts`, `presets/materials/*.json`, derived
  `presets/physical/*.json` for `gen_params.py` / `e2e.sh`), provenance per property; `images/presets/physical/`.
- **Renderer/firmware**: Params **v24** adds `rimLight`/`rimTint` (side-lit rim of a tinted liquid on a dark ground,
  additive `rimLight·u²·rimTint` per row; 0 in every legacy preset ⇒ byte-identical; mirrored in `render.cpp`,
  `gen_params.py`, presets regenerated; NVS schema CRC 0xb28ec40d → 0x91818d7f, the board drops its saved blob once).
  The phase-1 standalone renderer (`physical.html`, `firmware/src/physical`, `R physical` / `Pbegin…` protocol, 343 KB
  PSRAM layers) is removed; its TS optical kernel lives on under `sim/src/material/optics/`.
- **Board** (2026-09-25, e2e.sh, ESP32-S3 via WSL): `presets/physical/honey.json` flashed and pinned — 46.1 fps, render
  14.89 ms (median of 3 runs × 5), IMU alive, no reboots; parity against the sim on honey `mismatched 1158 of 49312
  (2.35 %), >12/255 off: 0`, the rim band visible on the device; blood 60.8 fps / 9.25 ms. The e2e log's own parity
  line (117 px > 12/255) was taken on the board's restored default preset, not honey (KAIZEN: e2e.sh --preset parity).
- Limits (KAIZEN): the legacy scalar transparency cannot show a colour-filtered backing, so tinted liquids on light backings
  derive opaque with the colour in the body (rear marks hidden); clear liquids' haze clamps in the mix; emissive bodies
  render flat; a weakly self-lit liquid cannot keep the room light (binary emissive rule).

## Per-bubble fizz shading (2026-09-25, astra-loop)

Every bubble used to be the same sprite: one rim colour, a dark core shifted lower-right. Now (sim `drawTube` step 5,
firmware `discRowT` + the per-bubble setup, both from the same formulas):
- **Depth** `Fizz.z` (0 front wall .. 1 back wall, drawn at spawn and every recycle, kept while moving/parking). The
  liquid in front tints a deeper bubble toward the body: `depthK = 1 − fizzDepth·z·(1 − liquidTransparency)`, applied
  as a colour mix toward `pal.rows` (core and pinpoint per bubble at the centre row, rim per row), not as an alpha —
  the disc interior stays an opaque store, rear marks are behind the bubble as before. Opaque liquid: only front
  bubbles show; clear liquid: all alike. Params **v23**: `fizzDepth` (0..1, default 0.7), `fizzBlick` (0..1, default
  0.6); migration fills defaults; the seven presets that pinned an old `v` in their source (pinot, spritz, cuvee,
  nocturne, tide, olive-oil ×2) lost the pin, so import no longer re-defaults their surface fill/blick.
- **Rim per row** `bubbleRimRows[y] = rimLit·(0.35 + 0.45·w)`, `w = amb + (lambert − amb)·lightPhys` (glassW's
  style/Lambert mix without the highlight tent and reflections), `rimLit` = the lit rim clipped to the panel (bright
  presets drive `rim·br` past white, so the factor goes on the clipped colour) and capped below white so the pinpoint
  reads. Firmware: one more per-row palette array (+320 B), light-keyed with the palette.
- **Core offset follows the light**: `yHi = (H−1)/2·(1 − sin(light))` (continuous from `TubeState.light`),
  `dir = normalise(−0.7, clamp((yHi − y)/(H/2)))` in screen space (x mirrored into the liquid frame under `remaining`);
  the core shifts by `−dir·r·fizzShadeOff` (magnitude as before). A bubble above the highlight row has its core up,
  below it down; the tilt sweeps flip nothing.
- **Pinpoint** for r ≥ 2.5 and `fizzBlick` > 0: radius `max(0.6, r/4)` at `dir·0.4·(r − 1)` (straddles the lit edge
  of the core; at 0.55 it sat on the bright ring and vanished), neutral white × `brightness`, depth-tinted, mixed into
  the pixel colour in 888 before the one blend. Firmware kernel templated on it so small bubbles pay nothing.
- Verified: sim tsc/build, `check:presets`, `check:meniscus` (151 frames, max 9/255, UBSan clean),
  `check_render_frames.py --no-fizz` byte-identical to the pre-change renderer (9136 strips; new `--no-fizz` and
  `--big-fizz` harness modes), `--big-fizz` UBSan clean. PlatformIO RAM 89 216 B (+2 240: `z` 1 920 + rim rows 320),
  flash 1 504 319 B (+2 328). Board (same params A/B against HEAD b193d05, IMU alive): default preset fizz stage
  +0.26 vs +0.22 ms; heavy scene (fizzCount 120, fizzSize 5, lightPhys 1) 5.83 vs 4.77 ms pinned, 5.92 vs 4.64 ms
  with the IMU live — about +1 ms at the extreme, accepted. Five kernel variants (alpha fade, template split, veil
  helper, interior fast path, colour mix) all measured within noise of each other on the S3 while the host shows no
  gap at all; the remaining cost is not in the pixel arithmetic that was changed. Last board build predates the
  pinpoint depth tint (one blend per bubble). Screenshots: `fizzSize 14` on cola/champagne, transparency 0/0.5/1,
  across ±0.8, remaining, free slug, real sizes on six presets.
- **See-through interiors (same day, from the user's board test):** a fizz bubble's interior is no longer filled.
  `bubbleDark` is now the opacity of a black tint over the liquid as-is (0 = bare ring; the spirit-level bubble keeps
  its filled `bubbleIn`), scaled by the depth factor; the pinpoint and the tint are fused into one premultiplied
  write (`blick·g/(g + tint·(1−g))` at `cov·(g + tint·(1−g))`, Astra's fix for the untinted hole under the
  pinpoint's AA fringe). Rear ticks/digits show through the rings. Firmware jumps over the interior span per row
  when tint 0 and no pinpoint on that row (output-neutral: `--big-fizz` now cycles bubbleDark 0/0.5/1 and is
  byte-identical against the kernel without the skip). Board, `e2e.sh --ref 1366e97` on the board's own preset
  (fizzSize 5.5, bubbleDark 0.27): opaque 5.34 ms vs see-through 5.64 ms, quick-mode noise. The user's extreme
  scene (120 bubbles of size 16, 92 % transparent): 26.6 ms opaque, 29.6 ms with a 0.06 tint (every interior
  pixel blends), 25.7 ms at tint 0 — the ring's bounding-box arithmetic dominates, not the interior (KAIZEN).
- **Rim shading and core rule (same day, user's olive preset: "bubbles sometimes too dark"):** the ring's row factor
  is now `0.8 · luma(rows[y]) / max luma` — the rim darkens exactly as the liquid does at that row, no more (the
  fixed 0.35–0.80 light ramp left bubbles darker than a shallow-shaded liquid around them when `bubbleRim` is
  darker than the body). The core radius is `r − 1` (ring 1 px at its thinnest) and `fizzShadeOff` only shifts
  it, clamped to `r − 1`: with a large offset small bubbles used to lose their core entirely (`r − 1 − off ≤ 0`)
  and drew as solid discs of rim colour; now they are lit crescents with a see-through interior. Board, user's
  preset: fizz stage 4.9 ms (quick mode).
- The morning's "baseline" (3.59 ms) was on a different preset: the v23 schema CRC reset NVS to `presets/1.json` at
  first flash. Leftovers (KAIZEN): no depth sort, uniform ring brightness around the bubble, centre-row tint target
  for core/pinpoint, bench tooling gaps (preset pinning, IMU-dead boots, live-IMU runs).

## Perf pass (2026-09-23)

Bench scene (board NVS preset, `bench.py` 10:09:30): **27.4 → 35.0 fps, render 28.06 → 20.73 ms**, parity
>12/255 off 2 → 0. Cause: on the ESP32-S3, libm `fminf/fmaxf/floorf/ceilf` are flash calls, float `/` is ROM
`__divsf3` and `sqrtf` is a software loop, and the meniscus / glow / foam loops made a dozen of them per pixel.
render.cpp now uses inline `fmn/fmx/ffloor/fceil` everywhere (same values), reciprocals for loop-invariant
divisors, and squared-distance tests in the fizz discs. The glow ramp, surface band and fizz disc pixel loops
are noinline row helpers (`rampRowR/L`, `bandRow`, `discRow`). Stage costs: edge glow 4.7 → 1.6 ms, surface band
3.7 → 2.0, fizz 2.3 → 0.9. `check_render_frames.py` (4000 host scenes) is byte-identical to the pre-pass
renderer; `check:meniscus` is unchanged (max 9/255). The fizz ring uses `sqrtApprox` (≤ 2.1e-7 relative error;
a 1/256 alpha step in 2.5e-7 of the samples). No new buffers. Remaining costs and ideas: KAIZEN (perf pass leftovers).

## See-through meniscus surface (2026-09-23, from the user's phosphor-vial photo)

The photo: the surface of a pale green liquid in a clear vial reads as an almost transparent ellipse — a
pale wash over what is behind, a slightly darker liquid-tinted line where the contact ring meets the far glass
against the white paper, a bright line along the front contact line and a soft white blick on the surface.
The filled, shaded band (`surfaceBand`) could not do that: its interior opacity was the only opacity, so the
rim faded with it. Params **v21** (migration fills defaults, NVS schema CRC changed → the device drops its blob):
- `surfaceFill` (0..1, default 1): opacity of the concave dish's shaded interior. The rim keeps its own opacity
  (`strokeA · surfaceRim …`), so at 0 the rim alone draws the surface. The foam veil scales with it.
- `surfaceBlick` (0..1, default 0): specular patch on the dish, `liquidHi` coloured, a row tent centred on the
  light angle's highlight row (same cylinder point as `highlightTop`) with its own height (`BLICK_H` 0.18 of the
  tube each side — independent of `highlightH`: the user's config had the body strip off and saw no blick),
  `4u(1−u)` across the band, × edge light, × (1 − pull); concave only. It needs a light `liquidHi`: a dull
  highlight colour reflects a dull blick.
- Rim colour and opacity now follow the backdrop (`backK` = luma of the tube-back row / 255): over a dark
  back the lit rim as before (`liquidHi`, light side only, row shaded — byte-identical there); over a light
  back a deep liquid contour, `blend(row, darkC, 0.75)`, at light-independent opacity (absorption along a
  grazing path, not a reflection). Alpine / spritz / cuvee: the white-on-white rim used to vanish; now a
  contour, as the far ring in the photo. A first pass with the body colour at 50 % was still too pale on
  paper (user: "light on white, hard to see").
- Fill, blick and rim are composited as ONE write per pixel (premultiplied sum, one division on multi-layer
  pixels only: the 1–2 rim px per row and the blick rows). Separate writes stacked the firmware's ±1 LSB
  blend rounding twice when two layers darken the same pixel (tinted rim over the fill on a white back:
  17/255 at a 13 %-covered end pixel). Single-layer pixels take the old path unchanged.
- Rear marks under the band (review finding, same day): the mark compositor used to count the dish as liquid
  only where ≥ 0.5 opaque (`bandMarkExtent`) and drew marks dry past that, so at `surfaceFill` 0 a black rear
  tick erased the rim and the blick, and fill 0.499 → 0.501 jumped the mark boundary by 4 px. Now the mark
  bounds are the body only and the band is composited per pixel (`markFn` / `Mark::bandMark`, from per-row
  `BandInfo`: profile, stroke width, fill/blick/rim weights, pull): the mark is liquid-tinted by the fill's
  own opacity there, dry for the rest, in one write scaled by what the rim and blick let through. The
  protection covers the band's whole footprint, including its `edgeSoft/2` overlap into the body (a second
  review round found the blick erased on the first body pixel: the body path ran first, and a body pixel
  below the time edge's profile was assigned to the home edge's band). The wet/dry colour mix and the blend
  are computed in 888 and rounded once — the first version rounded three times and hit 17/255 against the
  firmware with a blick over ordinary ticks. The wet/dry warp and the digit shadow plane switch at the body
  edge (was: edge + the ≥ 0.5 extent). Harness invariants are pixel-based now (hidden at rest under an
  opaque dish, shown when receding or flattening, rim and blick kept over a black mark, no jump across
  fill 0.5), both edges, both fill directions, plus parity scenes with blick 0.8 / fill 0.35 over marks.
- Verified: sim tsc/build, `check:presets`, `npm run check:meniscus` (invariants + 139 native/sim frames, max
  channel delta 9/255, UBSan clean), PlatformIO build (RAM 87.4 KB — six per-row weight arrays per tube —,
  flash 1.49 MB). Not flashed or benchmarked on-device: bandRow gained a lambda and a division on rim/blick
  pixels, bandMark two divisions per mark pixel within a band's footprint; expect the surface-band stage within ~0.1 ms
  of its 2.0 ms. Defaults reproduce the old look except the rim tint on light backs.
  [before / after](docs/meniscus-see-through.png): pale green on a light back, alpine, frizzante, cryo with
  `surfaceFill 0.25, surfaceTone 0.6, surfaceBlick 0.8, surfaceRim 0.9, surfaceWidth 5`. Existing presets unchanged;
  the new `phosphor` preset (Phosphor sample: the photo's pale green solution in a clear vial on white paper,
  marker labels on the glass, standard rod only) carries this look (`surfaceFill` 0.35, `surfaceTone` 0.3 for a faint green wash in the dish,
  `surfaceRim` 1, `surfaceBlick` 0.8) plus `frontBright` 4 for the bright front contact line. `check:presets` ok (watery, translucent, wetting, no gas).

## Forward meniscus plan (2026-09-22, from images/thick_meniscus.png + images/fizz_on_edge.jpg)

The trailing edge reads well since the residue; the leading edge was a 2D cutout with a flat
bright fringe (`frontBright`) and a dim glow. Two realism points, the first done in this session:

1. **Surface band ("film layer"), DONE — `surfaceBand` / `surfaceRim`.** Seen side-on, the meniscus
   is not a line: the contact ring on the glass wall projects to a (nearly) straight line at
   `xe + meniscusDepth − bulge`, while the drawn curved profile is the mid-depth section. The lens
   between them (thick at the centre row, closing to zero at the top/bottom walls, changing with
   the pressure bulge and contact-lag `cap`) is the visible dish:
   - concave (wall ring ahead of the profile): `surfaceWidth` limits a shaded band which
     closes at the wall ring. The inner shoulder blends the body toward the deep liquid colour;
     a smooth gradient leads to the lit outer rim (`surfaceRim`). `surfaceTone` still shifts the
     band toward dark liquid or the highlight. Stroke and rim use pixel-footprint coverage, so
     fractional motion does not snap a full-bright pixel on/off and both ends are symmetric.
     Both curvature branches fade below 1 px of ring/profile separation, removing the previous
     discontinuity at 0.5 px. The concave band no longer fades with the wet film (2026-09-22: a
     re-forming interface read as a fade-in while settling); motion only reshapes it through `cap`
     (a receding line deepens the dish). Dynamic contact angle: a line receding at speed (pull = instantaneous
     edge speed / 12.5 px/s, not the draining film) meets the glass tangentially, so the dish is liquid
     thinning into its film: band colour → liquid row by pull, alpha × (1 − pull·u) across the band, rim
     × (1 − pull) — no dark shoulder or lit outline over the trail; both are back the moment the line stops. Rear-mark bounds extend only over the part of the stroke
     whose drawn opacity a·(1 − pull·smoothstep) is ≥ 0.5 (`bandMarkExtent`, closed-form inverse
     smoothstep; per-row `markR/L`), so a thinning receding band doesn't hide ticks/digits as liquid;
     the foam veil follows the same pull profile. `a` is the curvature-adjusted opacity strokeA·min(1, tw),
     so a flattening/wobbling band (tw < 0.5 px at full strokeA) never hides a mark it doesn't visibly
     cover. Checks: bounds per edge × fill direction via `markBounds` (sim test hook), receding and
     flattening (depth 0.2 / 0.45). Its unlit edge darkens without reducing opacity.
     The surface now composites AFTER residue and the optional highlight inset. The old residue
     exclusions are removed: faint/re-forming bands blend over the actual smear rather than
     cutting a hole through it or having residue painted back over their rim. Rear-mark bounds
     extend only when stroke opacity (including `surfaceBand`) reaches 0.5.
     No extra firmware buffers, tables or allocations; existing static row arrays are reused.
     Trailing white fringe (user's white-glass preset): residue/wet film now paints BEFORE the
     body's anti-alias ramp. Previously it was masked by `(1 - coverage)` over a body already
     blended against white, leaking white at the junction even with surface shading disabled.
     Glow blends over the same residue backing; overlapping AA ramps of a tiny bead composite
     once. Convex noses never fade either (2026-09-22): the thin nose blends toward the local backing
     (`backR/L`, first pixel past the AA ramp, sampled after the residue/wet band and BEFORE the body
     and glow, plus the first step-3c wet-film pixel in non-trace mode) — bare back, or the receding
     edge's liquid-coloured wet film / residue — so no glow width can bring back a white crescent
     (checked with edgeGlow 0 and 12, both edges, both fill directions). Firmware: +4 static
     per-row arrays in the render context (2×float, 2×uint16 × TUBE_HEIGHT_MAX). Fixture: `sim/tools/fixtures/meniscus-trailing.json`.
     [Trailing edge before / after](docs/meniscus-trailing-fix.png) uses the supplied settings.
   - convex (wall ring behind the profile): the nose inside the profile is a thin lens, blended toward a
     pale "thin liquid" tone (weight 1 − √(1 − s)); the existing soft edge / frontBright keep the rim.
   Advance vs recede is carried by the bulge sign (`meniscusTiltGain · edgeLight` + `cap`).
   Not done: the far-wall contact line as a separate visible curve, or physically solved
   reflection/refraction. The shoulder and rim are an inexpensive shading approximation. Opaque
   convex liquids get limb darkening instead of the pale lens (weight = `liquidTransparency`).
   Params **v19**: `surfaceBand` (0.5) / `surfaceRim` (0.6) / `surfaceWidth` (4) / `surfaceTone` (0), migration fills defaults; the NVS
   schema CRC changed, so the device drops its saved blob on first boot (export first if needed).
   Verified: sim build and preset checks, PlatformIO build; `npm run check:meniscus` checks
   symmetry, subpixel motion, flattening, residue, faint-band rear marks, receding edges and
   gradients, trailing wet-film joins and tiny beads, then compares 54 native/sim frames (max channel difference 9/255; UBSan clean).
   With residue disabled and neither edge receding, 4000 native strips are byte-identical to
   the pre-fringe-fix renderer; another 4000 residue-enabled stress frames pass UBSan.
   Not flashed or benchmarked on-device (bench.py has the `surfaceBand` stage).
   Visual comparison: [before / after](docs/meniscus-surface-comparison.png).
2. **Fizz at the surface, DONE — `fizzEdgeRise` / `fizzFoamLife` (params v20).** A bubble
   reaching the fill edge used to respawn at the far side, so the surface was the one place fizz
   was never seen; the photo shows the opposite. Now:
   - `fizzEdgeRise` (0..1, default 0.3): the face-up rise gets a component toward the *exposed*
     surface, so bubbles reach it at rest. The exposed surface is the time edge, or the home edge
     of a free slug whose time edge sits against the far end (the user's `remaining` + `freeLiquid`
     + `freeHomeK` 0 look: the visible meniscus there is `edgeXL`, the time edge is at the panel
     border). `drawTube` publishes both per-row surfaces and an exposed mask for the stepper.
   - `fizzFoamLife` (s, default 6, 0 = old respawn): a bubble reaching an exposed surface parks
     *on* the meniscus: caught as its rim comes within 2 px of the surface profile (with a
     concave surface band, its inner rim: the foam floats on the liquid, not out on the band that
     climbs the wall to the contact ring), it glides on until its centre sits on the profile, half
     out of the liquid, so the
     foam forms the surface instead of collecting behind it; later arrivals pack behind
     (`Fizz.life` ≠ 0, sign = which edge; no new buffers beyond the per-row fronts). Free bubbles
     are checked with their whole disc (the tightest row), not the centre: a rim within 2 px of
     the profile is caught at the foam surface and recycled at any other edge, respawning inside
     the liquid of its new row; the render clips free-bubble pixels to the liquid (one-frame lag of
     a fast slosh) and clamps foam to the current profile. Before, tilting showed big bubbles
     poking up to 4 px past the edge and foam lagging a receding surface by up to 10 px (tilt
     harness: 46 → 1–3 cut, 0 outside, per 500 frames). Over a concave surface band the foam is
     seen through the liquid wedge climbing the front glass: veiled by the band (`FOAM_VEIL` 0.7 ×
     band opacity at the profile, fading to 0 at its outer rim). The column-end respawn (`len` = column − 6 px) no longer fires for a bubble heading
     to a surface: it used to recycle them before they reached the front on the middle rows, so
     foam could only park on the rows where the meniscus falls back (behind a convex dome).
     Parked bubbles follow the surface (lag behind an advance, pushed back by a
     recession), slide along the meniscus toward the higher contact line — the horns, where the
     foam ring forms — and pack: stopped behind a bubble in front (second layer), pushed apart
     from one beside, slide blocked by a touching neighbour so they line the surface. Pairs among
     parked bubbles only (≤ 64², 50 Hz, trivial). Life is random ±50 %; shaking counts it down
     4× faster; tilting the surface down (rise pointing away) releases the foam into the flow.
     The last 0.3 s is the pop: the disc swells 1.6× and fades, breaking the surface.
   - Fizzy presets: frizzante/champagne/cola (`fizzEdgeRise` 0.5, life 4–5), cryo (0.6, 2 s:
     boiling), honey/molten (0.2, 15–20 s: trapped air). Everything else inherits the defaults;
     with 8 slow bubbles the default look accumulates only occasionally.
   - Verified: sim build/tsc/check:presets, `npm run check:meniscus` (54 native/sim frames, max
     channel delta 9/255, UBSan clean; fizz is off there), a sanitized host stress of
     renderTube + stepFizz (9600 steps, 24 scenarios incl. mid-run `tubeHeight` changes and
     empty/full columns, ASan+UBSan clean, ~22 k parked-bubble-steps), PlatformIO build (+1 KB
     static: `life` per bubble). Browser runs: frizzante forms a ring at both corners, the user's
     preset lines the visible (home) meniscus, along-tilt toward the surface holds the foam,
     away releases it within 2 s. Not flashed or benchmarked on-device.
     Foam-in-meniscus follow-up: headless sim runs (frizzante, cola, the user's convex preset with
     more bubbles) show the foam on the band / dome front; a sanitized native stress of the
     firmware (50 scenarios, ~124 k parked-bubble-steps, concave/convex/flat, free/pinned,
     remaining, `tubeHeight` change mid-run) keeps every parked disc inside the front, ASan+UBSan
     clean; check:meniscus unchanged (54 frames, max delta 9/255); PlatformIO build OK.
     Limits raised: `fizzCount` UI max 60 → 120, `fizzSize` UI max 8 → 16. Pool per tube (sim
     `FIZZ_MAX`, firmware `MAX_FIZZ`) = 240, the sliders' worst case (120 × up to 2 with
     agitation ≤ 1); a count pushed past it over serial is capped and reported (sim console warning,
     firmware `error fizz pool:` line per new peak via `fizzOverflow()`). Not benchmarked on the
     device: 240 size-16 discs per tube are far beyond the old worst-case fizz pixel work.
   - Review round (four issues, all fixed and re-measured in sim and native firmware):
     band veil is weighted by each pixel's footprint over the band (the foam added a 136/255 step
     per 0.02 px edge move with the old per-pixel-centre test, 8/255 now); a bubble is recycled or
     caught only when the flow carries it into a surface, otherwise its centre just rides the
     surface (released foam drifts back in instead of respawning: 0 teleports); packing is a
     pairwise relaxation after the wall/front clamps, swept front to back (3 sweeps), the rear one
     stepping back when both are pinned, forward creep capped at the rise speed, and a free bubble
     touching the foam joins it at the back (120 × 8 px bubbles, 3000 ticks: overlaps > 25 % in
     17–100 ticks, mostly the initial mass catch, vs 2929 before; ~0.01 pairs/tick after warm-up).
     Every bubble is drawn with its centre inside this frame's surfaces (at most half out, like
     the foam); the per-pixel free-bubble clip is gone. A free bubble joins only foam parked on the
     side it heads for (not the other edge's, nor foam still to be released that tick): reversing a
     free slug caught 23 bubbles for the wrong surface before, 0 after (native, 40 runs).
   Not done: foam left on the residue behind a receding edge, bubbles nucleating on the glass
   (zero-speed state) — see KAIZEN.

## Play hold (2026-09-10)

- Substantial opposing tilt strokes within 2 s start a 5 s free-flow hold. Each stroke changes
  filtered in-plane gravity by at least 0.35 g; its direction must oppose the previous stroke
  (dot product < −0.5). After play starts, further substantial strokes refresh the hold.
- The hold overrides reading through gentle angles; once it expires, the existing smooth tilt
  response resumes. Steady hand-down, a single raise, small jitter and slow posture changes do
  not start or refresh a hold in replay tests. Real wrist motion still needs feel tuning.
- Params v17 adds `playHold` (0–30 s, default 5; 0 disables). Older settings gain the default
  while retaining their viewing angles. Pinned mode cancels play. Six scalar floats and a bool
  per tube track the gesture; all state remains statically owned, with no allocations.
- Verified: IMU/play replays, material checks, simulator build, native firmware motion checks,
  and PlatformIO build. Static RAM increased by 64 bytes. Not flashed or wrist-tested.

## Tilt-controlled reading (2026-09-09)

- `freeLiquid` now enables automatic flow: below `readTiltStart` (20°) the slug and slosh settle
  home; above `readTiltEnd` (50°) gravity moves it freely. Smooth interpolation and a 250 ms
  follower soften the transition. Both filtered gravity axes count, before input gain/deadzone.
- Reading persists while held, with no wrist gesture or timeout. Defaults and liquid presets enable
  it; `freeLiquid=false` remains an always-pinned override (also used by the xenon plasma preset).
- Params v16 replaces `readFaceUp/readAlongMax/readTurn/readHold` with the two angle controls.
  Imported/browser v15 settings receive the new angle defaults and retain their pinned override.
  Firmware's existing schema guard rejects the old NVS blob on first boot after flashing; export
  a custom device look before upgrading if it needs preserving, then import/push it via the simulator.
- Regression coverage: motion replays, both fill directions and fill extremes, minute-long viewing,
  both tilt axes/diagonals, artistic gains, preset settling, migration and overlapping thresholds.
  The initial tilt change reduced firmware state; no buffers or allocations added.
- Verified: `check:imu`, `check:presets`, simulator production build, browser tilt/read interaction,
  and PlatformIO firmware build. Native C++/sim comparison ran 45,000 physics frames with 180
  sampled states: maximum slug difference 0.00037 px. Not flashed or tested on the wrist yet.

## Toolchain (decided)
- **PlatformIO 6.1.19** (installed via `pipx`, binary `~/.local/bin/pio`) + **pioarduino platform 55.03.311**
  = Arduino core 3.3.11 on ESP-IDF 5.5.5. Stock `espressif32` platform is stuck on Arduino 2.x and can't
  build Waveshare's `esp_lcd`-based display driver; the wiki requires core ≥3.3.0.
- Board: `esp32-s3-devkitc-1` with overrides for the N16R8 module (16 MB QIO flash, 8 MB OPI PSRAM,
  `default_16MB.csv`, USB CDC on boot). No ready-made board JSON exists for this Waveshare board.
- Serial/flash port: `/dev/ttyACM0` (native USB-JTAG/serial, VID:PID 303A:1001). User is in `dialout`.
- Commands (from `firmware/`): `pio run` · `pio run -t upload` · `pio device monitor`
- Display path: Waveshare's `esp_lcd_sh8601` driver (copied verbatim into `firmware/lib/esp_lcd_sh8601/`),
  init sequence verbatim from their `03_LVGL_V8_Test.ino`. Drawing via Adafruit GFX into a 536×240 RGB565
  framebuffer in PSRAM, staged through two 72-row internal DMA strip buffers (owned by display.cpp).
  Note: the driver does NOT support `esp_lcd_panel_swap_xy` (aborts) — orientation comes from MADCTL (0x36).
  `-DUSB_LEFT=1` (default) uses MADCTL 0x30 = USB-C on the left; 0 gives Waveshare's 0xF0 (USB right).
  Panel wants big-endian RGB565: `PsramCanvas` stores pixels pre-byte-swapped so the push is a plain memcpy
  (swapping at push time cost ~20 % fps). Before the fix the green bars rendered blue.
- Serial monitor: `pio device monitor` is silent until you send a command (firmware only prints on request);
  `echo h > /dev/ttyACM0` also works.

## Pinout (verified from Waveshare demo code AND arduino-esp32 variant `waveshare_esp32_s3_touch_amoled_191`)
| Function | GPIO |
|---|---|
| AMOLED QSPI CS / PCLK | 6 / 47 |
| AMOLED QSPI D0 D1 D2 D3 | 18 7 48 5 |
| AMOLED RST | 17 |
| AMOLED TE / PWR_EN / backlight | none (-1) — brightness via cmd 0x51 |
| I2C SDA / SCL (QMI8658, also touch on touch SKU) | 40 / 39 |
| QMI8658 address | 0x6A or 0x6B (firmware probes both; WHO_AM_I = 0x05) |
| QMI8658 INT1 / INT2 | 45 / 46 (variant header) |
| Battery ADC | GPIO1 = ADC1_CH0, 12 dB atten, voltage ×2 divider |
| TF card (SDMMC 1-bit) | D0=8, CMD=42, CLK=9 |
| UART0 | TX 43, RX 44 |
| Panel QSPI clock | 40 MHz (demo default) |
RTC: the demos contain no external RTC driver — assume ESP32-S3 internal RTC only (verify on schematic in `vendor/waveshare/` if needed).

## What is flashed on the board right now
`firmware/` @ this commit. Boots into the **liquid face** (`l`) = 1:1 port of the sim renderer + physics
with `presets/1.json` baked in, driven by the live IMU at 50 Hz; **~40 fps**. Serial commands @115200
(newline-terminated): `l` liquid, `c` calibration face, `h` hello, `f` fps bench, `s` status line,
`i` IMU CSV stream, `t HH:MM[:SS]` set clock (no RTC battery — power-on resumes from the sim time saved to NVS on `T` and each minute, else 10:09:30),
`d<N>` demo speed (×N, `d0` freeze, `d1` real), `w<N>` minutes sweep (minutes tube empty→full→empty every N s, `w0` off; NVS), `p<name>=<value>` set ANY param live by its sim name
(`pliquid=#39ff14`, `pfizz=0`, `pcontactAngle=140`), `p?` dump params as JSON (sim-importable), `p!` reset
to the preset, `b<0-255>` panel dimmer, `r` reboot, `?` help. Same protocol over **BLE** (Nordic UART Service,
advertised as `liquid-watch`; NimBLE-Arduino, RX queued into `loop()`, replies notified in MTU-3 chunks).
`TUBE_HEIGHT_MAX` = 80: the two internal-DMA strips (2 × 536 × 80 × 2 B) must leave room for the BT controller,
else `display_init` fails at boot before `ble_init`.

## Firmware e2e testing (from `firmware/`)
- `tools/device.py [CMD ...]` — serial transport, auto-detects the board: `/dev/ttyACM*` when usbipd-attached
  to WSL, otherwise the Espressif COMx on Windows through a `python.exe` bridge (`$LW_PORT` overrides).
  Opens with DTR=RTS=1 — pyserial's default open sequence *resets the ESP32-S3* (DTR0/RTS1) on both OSes.
- `tools/bench.py [--stages] [--stage name=v]` — fps in a pinned scene (`t 10:09:30`, `d0`, `inputGain=0`),
  median of N 2-s windows; `--stages` toggles digits/ticks/fizz/glow/… off one at a time and prints each
  stage's cost in ms. Touched params are restored from a `p?` snapshot (not `p!`, which would clobber NVS).
- `tools/compare-device.py` — pixel parity of both strips vs the sim renderer (`x` dump); bar: mismatches
  must not grow, none > 12/255.
- `tools/flash.sh` — `pio upload` over `/dev/ttyACM*` or `flash-win.sh` when the board is on Windows.
- `tools/e2e.sh [--stages] [--no-ble] [--no-flash] [--label X]` — build → flash → bench → parity, appends to
  `firmware/.compare/e2e.log`. `--no-ble` builds with `-DNO_BLE` (stubs in ble.cpp).
- Boot banner now ends with `reset <reason>` (`esp_reset_reason`: poweron/sw/panic/task-wdt/brownout/usb/…);
  `device.py` prints `BOARD REBOOTED (<reason>)` whenever a banner shows up in a reply.
- BLE disconnect does **not** reboot the board: 6 connect→subscribe→disconnect cycles from Windows
  (`tools/ble-session.py`, bleak under `python.exe`; also does full command/notify round trips), serial shows `ble: connect` … `ble: disconnect 531`, no banner, clock intact.
- Serial-open resets: explicitly clearing DTR/RTS at open reset the board 5/5 in one session and 0/2 later
  (timing-dependent); DTR=RTS=1 never did. Keep device.py's open sequence.
- Scene matters: fps varies 19–25 with fill level / tilt, so only compare pinned-scene numbers.

## Perf baseline (2026-08-27, f0a3de7, `-Os`, BLE on, preset from NVS, sprite font 7 @ 3.5×3.25)

- **20.6 fps, render 44.4 ms, push-wait 0.02 ms** — entirely render-bound; ~4 ms/frame of non-render loop
  (physics, IMU, serial). No-BLE build: 20.0 fps / 46.1 ms → BLE costs nothing at render time.
- Stage costs (render ms saved when off): **digits 20.7**, edgeGlow 4.0, ticksH 3.9, fizz 2.7, ticksM 2.3,
  lens 0.8; digitShadow, meniscus, wetFilm, glass*, transparency ≤ 0.2 each.
  → the sprite-digit compositing is half the frame: hand-off 3 (layer cache) is the big lever, not the math.
- Parity: 163–221 of 77184 px differ by ≤ 1 LSB (digit glyph rounding), 0 px > 12/255.

## Perf hand-off 1 (2026-08-27, docs/perf-handoff-1-math.md) — 20.6 → 38.6 fps, bit-exact
| step | fps | render ms |
|---|---|---|
| baseline `-Os` | 20.6 | 44.4 |
| `-O2` (`build_unflags = -Os`) | 25.1 | 35.9 |
| + params generation counter, param-only caches, integer mark path, glyphs on internal heap (lazy) | 42.0 | 20.0 |
| same, but deterministic memory: glyph pool in PSRAM (boot-time), glow tables static | 36.0–38.6 | 22.0–23.9 |
- Stage costs after (ms, final run): digits 9.8 (was 20.7), edgeGlow 3.4, ticksH 2.1, fizz 1.4, ticksM 1.3, lens 0.4.
- `paramsGen` (main.cpp) is bumped on every `p` write, `p!`, NVS restore and passed to `renderTube`;
  every param-only table in render.cpp is keyed on (gen, H): tick/lens row warps, lens row map, fizz
  magnification, corner mask, meniscus row terms, label layout (+ its two motion-derived ints), palette
  (+ exact `light`), edge-glow 565 tables (+ exact `lightK`). Exact float keys instead of the ½° quantisation
  the hand-off suggested: hits at rest, bit-exact in motion.
- Mark path is integer: transparency/contrast hoisted into `Mark`, sprite alpha via a 256-entry LUT built
  from the float formula, tick emboss via per-channel LUTs, tick warped ranges once per (wet/dry, minor/major).
- Memory: internal heap after BLE init is **37 KB** free (59 KB static). Glyph pools (2 × 18 KB) therefore live in
  PSRAM, allocated once in `render_init()`; putting them in internal RAM is worth ~2 ms but the BT controller
  then fails to start (build with 100 KB static hung in `ble_init`). Rule: no lazy allocation (CLAUDE.md).
- Parity unchanged: preset 1 / mercury / glow 0 px > 12/255; cryo (132 px) and free (1 px) deviate identically
  on the pre-change firmware — pre-existing, see KAIZEN.

## Perf hand-off 2 (2026-08-27, docs/perf-handoff-2-dualcore.md) — 38.6 → 45.5 fps, bit-exact
| build | fps | render ms (wall) | cores h / m ms |
|---|---|---|---|
| hand-off 1 final (sequential) | 38.6 | 22.0 | — |
| one tube per core (worker stack 8 KB) | 45.5 (spread 43.5–46.0) | 13.9 | 14.7 / 10.6 |
| final: worker stack 4 KB (~1.5 KB used) | 44.1 (spread 42.1–44.6) | 14.6 | 14.7 / 10.6 |
- `render.cpp`: all per-frame mutable state (strip pointer/geometry, row cache, edge and bound arrays, palette,
  labels, glow tables, glyph pool, fizz) lives in a static per-tube `Tube` context (`tubes[2]`, ~9 KB each,
  fixed footprint); `Mark` carries a reference to its tube; LUTs are built once in `render_init()`. Only the
  read-only LUTs and `tubes[2]` remain file-static, so `renderTube(0)` and `renderTube(1)` may run concurrently.
- `main.cpp`: pinned core-0 task `render0` (prio 1, 4 KB stack, ~1.5 KB used) draws hours into `strip[0]` while
  `loop()` (core 1) draws minutes into `strip[1]`; task-notification hand-shake both ways. Outside `renderBoth()`
  the worker is blocked, so serial/BLE commands, param writes, physics and `x` need no snapshot. Both strips are
  pushed after the join; `display_wait_pending(display_bands(H))` frees the hours strip as soon as its own DMA
  bands finish while minutes' are still in flight (push-wait stays 0.01 ms).
- `f` prints `cores h / m` (per-core render ms); `s` prints `worker-stack-free` (bytes).
- Stage costs (ms of the wall time): digits 7.1, edgeGlow 2.2, ticksH 2.0, fizz 1.2, ticksM 0.5.
- Soak: `d60` for 60 s — no watchdog / reboot, heap and worker stack unchanged; worst frame 36 fps with both
  tubes filling (cores 19.1 / 17.8). BLE central connected: 41.0 fps vs 41.2 unconnected, NimBLE left on core 0.
- Parity: 191–209 px (bench) / 140 px (after soak) ≤ 1 LSB, 0 > 12/255. The 45.5 vs 44.1 gap is within the
  medians' spread (see KAIZEN from hand-off 1: always compare medians of ≥5).

## Push "crash" (2026-09-01, fixed) — DualOut blocked on a full CDC ring
- Symptom: pushing a preset (BLE push, or any push while the CDC host was gone with DTR still
  asserted) froze the board: replies stopped after ~7 `ok`s, fps collapsed to ~1.2 (render 13 ms —
  loop() itself crawled at ~10 bytes/s), minutes-long self-recovery; user-visible as a dead/black
  screen. Traces themselves were exonerated: traces=1 + d3600 sweep + full serial blood push were all clean.
- Root cause: `DualOut::write` wrote every reply byte to `Serial` unconditionally; with the CDC host
  absent (or a stale asserted DTR with no reader) the 256-byte HWCDC ring filled and each further
  byte cost `tx_timeout_ms` (default 100 ms) in `xRingbufferSend` — 5 KB of echo+replies per preset
  push = minutes of grind inside `loop()` (NimBLE host on core 0 compounded the render starvation).
- Fix: `Serial.setTxTimeoutMs(10)`, DualOut stages per line and flushes in one bulk
  `Serial.write(sBuf, n)` gated on `Serial.isConnected()`. (First attempt used timeout 0: a momentary
  host read-gap then dropped bytes mid-line — the `p?` JSON arrived truncated; per-byte writes are
  either wedge-prone or lossy, per-line bulk is neither.) Verified: serial push 150 params in 15 s @
  47 fps. BLE-push re-verification pending (Windows radio was off).

## Traces on glass (2026-09-01, sim + firmware, bit-exact pipeline)
_Deposit law, colour and drainage superseded by "Residue physics (2026-10-02)" below._
- A receding edge leaves a **residue** on the glass where the liquid has been (blood smear, syrup
  coating, legs); the wet part **drains back after the liquid**, the stain dries: `traces` (bool),
  `traceAmount` 0..2 (>1 boosts through the attenuation, clamped per pixel), `traceDry` 0.1–2 s
  when flat — tilting along the tube dries up to 5× faster (`TRACE_TILT_DRY`), `traceThin` 0–3
  (edge speed thins the deposit; at 1, 100 px/s halves it — `TRACE_THIN_REF_PX_S`),
  `traceFollow` 1/s (drain-back rate at 25 px from the liquid),
  `traceStain` 0..1 (fraction of a fresh deposit the drain-back leaves behind; on-screen stain
  opacity ≈ traceStain × traceAmount),
  `traceFilm` 0..1 (2026-09-22: permanent film over the whole glass as a residue level — the tube
  never looks perfectly clean; render-only floor of the per-column value after the blur, so it
  gets the streak, wall weight, under-liquid coverage and wet band like any residue; forces the
  full column range, i.e. the dry side is blended every frame: ~5.7 ms worst case per tube).
  Params v15 unchanged (additive keys; NVS CRC changes → stored params fall back to the preset).
- Physics (sim `stepTube` / fw `stepTube`, identical): per-tube residue `Uint16Array(536)` (8.8
  fixed point, high byte renders) in **panel-frame columns**; an edge that receded saturates
  (`TRACE_FULL` 0xff00) the columns it uncovered — mid-row edges only (`xt = slugPos + fillPos`
  mirrored / `xh + len + fillPos`, home edge for a free slug), deposit capped at 32 px/tick
  (`TRACE_DEPOSIT_MAX_PX`) and **thinned by the edge's speed** (÷(1 + traceThin·v/100 px/s)): a
  fast sweep stretches the film, so a slosh smear comes out faint at its far end and dense toward
  where the edge slowed — toward the liquid. Decay, per column ×tick (linearised, floor-rounded),
  **two-phase** so traceStain visibly matters at second-scale drying: the wet excess above the
  **stain floor** (traceStain·full × hash 0.7–1) settles ONTO the floor at
  `traceFollow · dist/25px + 1/traceDry` per second — dist from the current liquid span, so the far
  tail of a smear collapses first and the band visibly follows a receded edge — and only residue
  at/below the floor dries toward zero ×(1 − u·(1 + 4·|along|)·dt/traceDry), making the stain the
  plateau the fade pauses at; a second hash channel `u` 0.75–1.25 scatters the rates (`traceUneven`, same
  integer hash both sides, salted differently from the render's `traceStreak`). < 2·256 → 0; off →
  buffer zeroed on transition. **Why 16-bit + floor**: the v1 `Uint8` round-to-nearest stalled — at
  50 Hz any traceDry > ~10 s decrements < 0.5 LSB and 255 rounds back to 255, so blood never dried;
  floor is monotone (worst case 1 LSB/tick) and the faintest stain always clears. Buffers: sim
  `newTube()`, fw static `g_trace[2][536]` (uint16) assigned to `TubeState.trace` in `setup`.
- Render (sim step 3d / fw "3d", drawn after the glow + wet film, mirrored index for `remaining`):
  per column: residue → ±4 px triangular blur (tapers the smear's outer end — the dense turnaround
  deposit next to bare glass — into a tide mark instead of a 1-px cliff) → ^0.65 (`TRACE_GAMMA`
  value→alpha lift — a dried stain at ~0.2–0.5 of full
  would otherwise drown in the opacity stack) × `traceStreak(x + idx·6151)` (same integer hash both
  sides — static vertical texture, 0.82–1: subtle, not stripes) × wall weight `0.4 + 0.6·d²`, colour = liquid row
  × 0.85 (dried). Drawn late
  because the glow pass paints the dry side with plain overwrite — drawn earlier it wiped the smear
  off the band next to the edge (`edgeGlow` px gap). The residue is composited UNDER the liquid:
  per pixel × (1 − liquid coverage as step 3 painted it), so the anti-aliased meniscus ramps liquid →
  residue instead of liquid → tube back (no dark seam), and fully covered columns get none (an edge
  that advanced back over residue covers it again). Wet band: over the first `wetFilm` px behind a
  receding edge the residue's alpha and colour ramp up to the liquid's own (weight
  `film × (1 − d/wetFilm)`, gated by `filmFree`/`filmHome`), so the liquid thins out into its trail
  with no visible edge while it recedes; the faint step-3c film is skipped in trace mode. Cost bound: per-column alpha
  precomputed, rows skip a=0; fw uses the integer `pxaT` path; the gamma is a lerped 256-entry LUT
  (fw `LUT_traceGamma` built in `buildLuts`, sim mirrors) — no powf per column.
- Perf: `TubeState.traceLo/traceHi` track the occupied column range (deposits widen it, the decay
  pass re-tightens it every tick; lo ≥ hi = empty). The physics decay iterates only that range and
  the whole render layer is skipped when it's empty — copy/blur/alpha/draw loops run over the range
  ±4 px (blur reach) instead of all 536×H pixels, so no residue ⇒ ~zero cost (was ~3 ms/frame flat).
  On-device (interleaved A/B bench): traces-on-empty = traces-off to ±0.02 ms (was +3.02 ms); heavy
  residue (~585 columns) costs ~14 ms of pure `pxaT` blending — same as before, see KAIZEN. Parity
  with residue: all trace-attributable deltas are exactly 1 RGB565 LSB (the gamma-LUT lerp).
  `render-ref.ts` recovers the bounds by scanning the dumped buffer. NOTE: anything poking
  `trace[x]` directly (test scripts) must also widen `traceLo/traceHi` or the residue is ignored.
- Presets (amount / dry s / follow / stain / thin): blood (1.1 / 1.5 / 0.25 / 0.35 / 0.8), honey
  (0.7 / 2 / 0.08 / 0.45 / 0.3 — syrup barely crawls, coats thickly whatever the speed), ink (0.5 /
  1.2 / 0.5 / 0.4 / 1.5 — thin, snaps back to a stain), malt (0.45 / 0.6 / 0.35 / 0.2 / 1.2).
  `check:presets` rule: non-wetting/plasma must be off; on ⇒ amount 0.2–2, dry 0.1–2 s, follow 0–1
  (viscous ≤ 0.15, watery ≥ 0.2), stain 0.05–0.7, thin 0–3.
  Presets re-dumped, `params_gen.h` regenerated, `presets/1.json` patched (traces off).
- Parity: the `x` dump gained a `TRACE ` line (space-separated, **4 hex chars per column** — keep
  the separator, compare-device counts the tokens); `compare-device.py` passes it to
  `render-ref.ts` (decoded into `TubeState.trace`). Bench: `--stages` measures `traces` off.
  Parity with v1 residue live: 54 px mismatched, 0 > 12/255 (better than the pre-trace ~200 px
  baseline); re-verify after the 16-bit drain-back rework. Drain-back verified in sim (blood,
  seeded 160-px smear: far tail collapsed to its uneven stain floors in ~5 s while the band at the
  edge stayed wet, then slow fade; buffer values sampled at 0/6/18 s).

## Digit shadow baked into the sprite (2026-09-22, sim + firmware)
- The shadow (`digitShadow*`) was a full second glyph pass. It is now composited into the scaled sprite in
  `scaledGlyphs` (`bakeShadow`), once per parameter change; the draw pass runs once. All shadow params stay
  live (they are part of the sprite cache key). Bitmap fonts still use the two-pass path (see KAIZEN).
- Two planes per glyph: behind air (k = 1) and behind liquid with the liquid transparency folded into the
  alpha, because two layers each blended at T reach opacity 1 − (1 − T)² which one mark at T cannot; the
  Mark skips its own transparency for these glyphs (`Mark::bakedT` / markFn `bakedT`) and only the contrast
  floor applies. The plane is chosen per pixel with the compositor's own edge test (`Mark::inLiquid`), not
  per column — the meniscus rows near the walls differ from the middle-row column split.
  `GLYPH_POOL_PX` is now sized for the sliders' worst case (scale 6 × 6, offset 4, two planes): 31280
  texels, ~92 KB PSRAM per tube, boot-time as before. A zero transparency bakes a fully transparent
  behind-liquid plane (guarded: no 0/0).
- Fidelity vs the two-pass renderer (`firmware/tools/check_render_frames.py --tolerance N`, 4000 host
  scenes): 99% of the differing pixels are one 565 step; the rest sit in the wall-band fade rows behind
  air (their per-row factor is not bakeable), come from `markContrast` > 0 (floor on the composite), or
  are glyph-edge texels the box-filter fix below changed on purpose.
- Board (olive-oil params, film 0.17, shadow 0.8/1 px), median of 5 pinned samples:

| scene | before (two passes) | after (baked) | shadow cost before → after |
|---|---|---|---|
| 11:59:50 nearly dry, digits behind air | 35.2 fps / 20.81 ms | 39.7 fps / 17.65 ms | 4.98 → 1.21 ms |
| 10:09:30 default, digits behind liquid | 25.1 fps / 32.08 ms | 32.7 fps / 22.97 ms | 10.97 → −0.02 ms |

- Parity: a baked shadow puts a dark texel right next to a bright one, so two old sim/firmware rounding
  gaps that used to hide inside 1 LSB became visible 25–58/255 pixels and were fixed on both sides: (1) the
  sprite box filter computed its sheet-column bounds as `x / sx` (float vs double land on opposite sides
  of an integer, dropping the glyph's last sheet column on the board) — now exact ratios `x * width / gw`;
  (2) the bake uses the same clamped float transparency on both sides, and the sim picks the colour of the
  heaviest bilinear tap with the firmware's 1/256 weights so near-ties resolve alike. Host render of the
  firmware vs the sim reference: 0 px > 12/255 on four captured states; `compare-device` on the board
  likewise (see e2e log).

## Digit compositor: row runs (2026-09-24, firmware, pixel-exact)
- The sprite-digit draw (`drawSpriteGlyph`) no longer classifies every texel on its own. A glyph row is cut
  once into runs on which everything is constant — on top / behind air / behind liquid (the row's liquid
  interval as `ceil(lo)..ceil(hi)`, the same test `Mark::inLiquid` makes) — and each run goes through a
  small `noinline` loop (`spriteRunInt` / `spriteRunFrac`, MODE 0 plain, 1 baked-T liquid, 2 general). Only
  pixels under a possible surface-band footprint (a conservative superset of `Mark::bandMark`'s coverage
  test, both sides, mirrored) keep the per-pixel compositor. Bitmap fonts still use the generic path.
- Glyph row spans: `scaledGlyphs` bakes per plane the first/one-past-last covered column of every row
  (`GLYPH_SPAN_BYTES` = 5 KB per tube, PSRAM, boot-time, same `ok` check as the pool); runs are clipped to
  them, the fractional path to the union of rows cy / cy−1 one column wider. Glyphs taller than 128 rows
  or wider than 255 columns (only reachable over serial) draw full rows.
- Gate: `firmware/tools/check_render_frames.py --reference <frozen render.cpp> --tolerance 0` now runs
  9136 scenes (random 4000 with all 12 fonts; digit-grid 3456: fonts × top/rear × shadow variants ×
  transparency × contrast × 8 fill modes with rotating fractional shifts, scales, tube heights; sequences
  1680: base → mutation → base over motion frames) under UBSan, and kills the surviving renderer when one
  side crashes. Byte-identical for every step below.
- `-DDIGIT_PROF` (build flag) adds per-tube digit-path counters printed by `f` (`digit-prof h/m …`):
  glyphs, rows, pixels per path (int/frac × plain/liquid), band-slow pixels, runs. Zero cost otherwise.
- Board, spritz params, normal build, pinned 10:09:30 (median of 5):

| step | fps | render | digits stage |
|---|---|---|---|
| baseline | 29.3 | 25.94 ms | 17.86 ms |
| row runs | 38.3 | 18.05 ms | 8.36 ms |
| + row spans | 41.2 | 16.33 ms | 8.15 ms |
| + tightened frac loop (final) | 42.3 | 15.73 ms | 7.58 ms |

  11:59:50 (digits behind air): 44.5 → 61.1 fps. Bare build: 48.2 fps / 13.73 ms. Preset 1: 48.3 fps.
  Clock sweep pinned: 00:05 17.0 ms, 06:30 15.3, 11:55 11.7. Pinned parity 489 px ≤ 1 LSB (was 514),
  0 > 12/255. Live parity runs show a few fizz pixels > 12 — pin the scene (`d0`, `inputGain 0`) first.
- Live tilt (IMU on, board resting): the minutes tube draws ~8.2k digit pixels behind liquid per frame
  through the fractional refraction path and pays ~3.2 ms for it (digitParallax 5.5 → 0: 18.05 → 14.9 ms;
  hours tube 0.4 ms). Carrying the left taps (two loads per pixel, zero rows instead of bounds checks) did
  not move that number, and a per-tube resampled-tile cache would rebuild every frame with the live tilt
  over about as many texels as it saves, so it was not built. The remaining levers there are approximations
  (2-tap horizontal, quantised weights + tile cache) — not taken; see KAIZEN for the surface band (~3.3 ms
  per tube on its own).

## Rear marks through the liquid (2026-09-26, sim + firmware + material layer)
- `markContrast` is a design key in material mode (was derived: opaque 0, else 24 with rear marks). Realism rule:
  rear marks' floor ≤ 120 × liquidTransparency in every class (≤ 14 behind an opaque liquid, which used to force 0);
  clear still needs ≥ 16. The material presets pin the former derived values: presets/physical unchanged.
- Contrast floor on shadow-baked sprite digits: the plane's alpha already carries T, so the floor used to see the
  raw texel and never fired — raising markContrast brightened ticks but not digits. Now floored at full glyph
  coverage (a = max(T, cov), then blended by cov / a): sim markFn, firmware `Mark::wetColourT` + sprite-run MODE 3.
- Gradual warp across the meniscus: a per-column wet share (rows that are liquid there, 1/256, `wetShare`) blends
  the dry → wet source rows and scales the parallax, for ticks and digits (firmware: runs for share 0 / 256, a
  per-pixel `drawRampColumn` under the meniscus). Before, the whole mark flipped at the centre row's edge.
  The firmware table is per Tube (`Tube::wetShare`, PSRAM, allocated in render_init): a first build kept one
  static table, and the two cores (hours on core 0, minutes on core 1) overwrote each other's shares — full tubes
  flickered, end digits vanished; a second put 2 × 2.1 KB into the static Tubes and BLE init hung (black screen):
  internal RAM has ~2.7 KB free once BLE is up. Board after the fix: 36.6 fps (HEAD 37.0, same scene), internal
  heap 2684 B (as HEAD), parity at 11:59:40 (both tubes full) 0 px > 12/255.
- check:meniscus gained sprite sheets (decoded with PIL) and 14 mark scenes (marks-across-*, marks-floor-*):
  165 scenes, max 9/255.
- Board A/B (`e2e.sh --ref HEAD`, cola preset pinned, one run each): HEAD 50.4 fps / 12.79 ms, new 54.6 fps /
  11.32 ms — within run-to-run noise (the free slug moves under the pinned tilt; stage deltas swung ±4 ms). Host
  timing of the same scene, warm caches: +8–10 % render with digits under both menisci (~30 ramp columns each),
  +2–5 % otherwise. Device parity 218 px > 12/255, but host = sim exactly (0 px) on the dumped state: the rest is
  frame/state skew of the moving slug, which the gradual warp makes ~2× more visible to the count (0.25 px skew:
  43 → 97 px).

## Residue physics (2026-10-02, sim + firmware; docs/residue-physics-handoff.md)
- Deposit = the film the receding line leaves: `filmEta(p, U)` (Bretherton, η = 1.34 Ca^⅔/(1 + 3.35 Ca^⅔),
  Ca = θ_dyn³/(9·9.2) · U/25, cap 0.1), stored as η/0.1 in `trace`. Watery: microns, ∝ U^⅔ (barely stains);
  syrup: near the cap whatever the speed. Uncovered columns below `TRACE_MIN` are cleared (the liquid dissolved
  them). `traceThin` retired (Params v26).
- Colour: a dye stain is a Beer–Lambert tint, B^(1−τ)·C^τ (tube back → body row, linear light, `FILM_LG`/`FILM_EX`),
  τ = traceAmount × the coat's annular path fraction (the wet film's law): per column A = η(2−η)·2^16 (η from the
  stored thickness, scattered by the streak), per row K = 256/(1 − u²) capped at 2^18, f = `FILM_PHI[(A·K + 2^15) >> 16]`,
  T = min(256, f·G/256) — the same integers on both sides; ≤ 1 = the body row, so no smear reads denser than the
  column. A watery coat is wall lines; a syrup ~0.1 at the centre plus legs. Near a receding line the coat and the
  wet film count once (the deeper of the two). `traceFilm` = a share of the cap thickness (no gamma, no cap). The
  palette's opaque `traceRows` and the 0.65 trace gamma LUT are gone. Firmware: `ResidueTint` (depthT / depthF) in
  `traceFillRow` / `traceShearRow` / the zone loop; `check_residue.py` checks the tint vs the sim's `filmMix` and the
  depth law vs a reference.
- Drainage: wet part `traceWet` (≤ trace; sim `Uint16Array`, fw PSRAM from `physics_init`). Gravity (pose
  along, ±1 g) runs it down the tube: upwind flux c·w, c = traceDrain·|g|·(w/TRACE_FULL)², capped 48 px/s, 3
  substeps, integer and exactly conservative; into the liquid it rejoins it, at a tube end it pools. `traceDrain`
  (Params v27, replaces `traceFollow`) = ρg(R/10)²/3μ in px/s, the speed of a film at the thin-film cap: derived from
  density, viscosity and bore (water ~1600, olive oil ~17, honey ~0.2); hand-made presets take `legacyTraceDrain`
  (ρg/μ from capLength and contactDyn's Ca). A watery film of microns or a syrup barely moves before it dries; a
  fast oily film sags. Drying: wet evaporates at u/traceDry leaving `traceStain` of itself as stain, which fades at
  the same rate. `TRACE_TILT_DRY` and the distance drain-back are gone. Only a dry column below `TRACE_MIN` is
  dropped (a draining film's thin front stays). `check:imu` covers deposit vs speed, a drop's profile, upright
  drain, a thin film's mass while it drains, conservation/pooling, flat, tilt-independent drying.
- Device `x` dump: new `WET` line (compare-device / render-ref parse it; the render reads `trace` only).
- Perf: `traceFillRow` builds a per-row colour LUT (per Tube, static) when the span's depths fall in a narrow band
  (a uniform `traceFilm`), else tints per pixel; byte-identical to the per-pixel path. Physics loops use inline min /
  truncation (libm `fminf`/`floorf` per column cost ~1 ms a step under the sweep stress). Board A/B after the review fixes: pending (board detached 2026-10-03).

## Measurements
- CPU 240 MHz, PSRAM 8192 KB, free heap 332 KB at boot.
- **fps (full frame 536×240×16bpp):** 32.3 fps render+push, **41.7 fps push-only**, **71.4 fps pushing only
  the two 72-px tube strips**. Target ≥30 met; dirty-strip path gives plenty of headroom.
- IMU: QMI8658 at 500 Hz ODR, ±8 g / ±1024 dps, streamed at 50 Hz. Board flat on desk, screen up:
  a ≈ (-0.19, -0.06, +0.92) g, gyro bias ≈ (-1.4, 0, 0.4) dps. |a| ≈ 0.94 g (slight scale/offset, fine).

## Open problems / to verify with the user (need eyes on the panel)
- [x] Calibration face visible, centred lines OK (user confirmed 2026-08-20). Colour was blue → byte-order fixed.
- [x] Orientation confirmed (USB-C left) and R/G/B swatch order correct (user, 2026-08-20).
- [ ] USB-C side in the cuff: defaulting to LEFT (no cuff yet; flip with `-DUSB_LEFT=0` if that changes).
- [x] IMU axis mapping measured (see `spec/layout.h`): **Y along the tube** (USB end up → ay −0.64 g),
      **X across** (far edge up → ax −0.72 g), Z out of screen. |a| ≈ 0.94 g at rest → normalize, or
      calibrate scale later.
- [~] #5DCAA5 reads as mint/turquoise on the AMOLED — channel order verified correct, so this is the spec colour
      itself. Final shade tuning deferred to Phase 2/3 (serial palette-nudge mode).

## Next step
**Phase 1 complete** (calibration face confirmed visually by user, IMU streamed + axes mapped, fps recorded).
→ Phase 2: browser-based liquid simulation (Vite + TS + Canvas), `spec/layout.ts` mirroring `spec/layout.h`.

## Phase 2 — browser simulator (`sim/`)
- Vite + TS, no framework. `cd sim && npm install && npm run dev` → http://localhost:5173
- Renders into a real RGB565 `Uint16Array` framebuffer (exact 565 quantisation) using only row spans /
  pixels / a per-row colour LUT, so the routine ports 1:1 (`sim/src/render.ts` is the spec; `firmware/src/render.cpp` mirrors it).
- Fixed-step 50 Hz physics (`sim/src/physics.ts`), decoupled from rAF rendering. IMU axes mapped via `spec/layout.ts`.
- Inputs: sliders / drag on the panel, phone DeviceOrientation, **Web Serial or Web Bluetooth to the board's `i` stream** (Chrome; link picker in the Device box).
- Time: real / demo (×N) / set HH:MM. Leather-cuff overlay with slot inset, acrylic-vial lens remap and gloss
  (presentation only, not ported). Layout-grid toggle shows the bridge zone.
- All tunables in `sim/src/params.ts` (`DEFAULT_PARAMS`), live panel, export/import JSON.
  Current defaults: `sim/params.json`.
- **Presets** (`PRESETS` in `sim/src/params.ts`, picker in the panel bar, `?preset=<id>`): each is a whole
  look — liquid optics, glass, scale, labels and the physics of that liquid's density and viscosity — and is
  applied over `DEFAULT_PARAMS` (`presetParams`), so a preset is reproducible whatever the session held.
  All liquids share `MODERN_BASE` (from `examples/nice_meniscus.json`: thin tubes at the panel edges, lens −0.5,
  physical light, rear sprite digits every hour / 5 min, free slug); opaque ones and lab glass use `FRONT_PRINT`.
  Each preset declares a *material* (`mat`: viscosity class, opacity, emissive, wetting, gas) and
  `npm run check:presets` (`sim/tools/check-presets.ts`) enforces the ranges that material implies — spring
  ζ, slosh, meniscus stiffness/lag/film, transparency vs rear-vs-top marks, glow only when emissive, fizz
  only with gas… (rules and the full list: `presets/PRESETS.md`). 2026-08-27 set: `frizzante` (colourless
  sparkling water) · `urine` · `blood` · `milk` · `mercury` (etched scale on top: nothing shows through
  metal) · `honey` (overdamped, clings) · `cola` · `malt` · `champagne` · `cryo` · `ink` · `glow` (glow
  stick, emissive) · `xenon` (plasma, no inertia) · `molten` · `free` (user-tuned slug, exempt from the
  checker); each also as `<id>-big` for the wider rod (`bigLens()`, 72 px tubes, lens −0.05). Legacy `user1` / `mint` / `neon` / `concept` and `sparkling` are gone. Panel shots:
  `images/presets/<id>.png` / `<id>-big.png` (+ `contact-sheet.png`, `contact-sheet-big.png`).
  `npm run dump:presets` writes each as a full params JSON into `presets/<id>.json` — the input format of
  `firmware/tools/gen_params.py`.
- Brightness is layered: `brightness` = panel dimmer (0x51), plus per-layer trims `liquidBright` /
  `tickBright` / `digitBright` in the Colour group. Dimming the digits sits them in the shadow at the bottom
  wall of the tube; the trim also scales that layer's `markContrast` floor, so the shadow survives over the
  liquid. `tubeBack` follows the panel dimmer only.
- Tube backs use the same fast row LUT as the liquid: `tubeBack` / `tubeBack2` can render solid,
  top-to-bottom, centre-band, or edge-band gradients across the short axis. The procedural rear-wall decal
  layer was removed (2026-08-27): per-pixel blending of a dense texture cost ~10 ms/frame on the device and
  even the baked/cached variant hurt frame rate; see KAIZEN.
- Digits include five bitmap fonts and seven generated image fonts: steel, brass steampunk, copper gauge,
  forged iron, ivory enamel, carved slate, and amber resin. Image fonts remain behind the liquid/glass layers
  and support brightness, tint, and black-to-white tone controls in the simulator and firmware.
- **Autosave** (`sim/src/persist.ts`): every edit — params, including lens calibration, and view state (zoom, cuff/gloss, layout grid,
  pause, time mode, tilt) — is written to `localStorage['liquid-watch-session-v1']`, debounced 250 ms, flushed on
  pagehide. One delegated `input` listener on `#app` covers every control. Nothing is lost on reload, so
  **Export JSON is only for checkpointing a finished look into `sim/params.json`**, and it still exports params
  only — view state never pollutes the firmware contract. `reset view` button restores the view defaults.
  Caveat: a stored value always beats a changed `DEFAULT_PARAMS`, so after editing defaults in code open
  **`?fresh=1`** to see them (it ignores the store without clearing it). Input source (device / serial) is not
  persisted — those need a user gesture.
- Scale minor and major widths are independently configurable (`tickMinorWidth*`, `tickMajorWidth*`); majors are placed every N **units**
  (`tickMajorEvery*` counts hours/minutes, migrated from the old "every N-th minor" via `params.v`).
  `ticksOnTop` selects the rear/bottom or front/top surface. Both use the cylinder `tickLens` and follow the whole-tube lens. Tilt-driven
  `tickParallax` projects them through the circular rear-half depth, producing a bow while keeping the outer endpoint attached to the tube silhouette. `tickEmboss` adds glass-cut highlight/shadow edges.
  Rear digits refract the same way (`digitParallax`, px/g): the columns behind liquid slide with tilt, those behind air stay put, so a label straddling the fill edge breaks at it. The wet copy is placed at the fractional shift and bilinearly resampled, so it glides instead of stepping a pixel at a time.
  `tickPosH/M` independently select the top, bottom, or both edges.
  Marks inside the liquid keep a minimum luma distance from it (`markContrast`). Contract: `throughLiquid` in `sim/src/render.ts`.
- Layer order is rear ticks → rear digits → bubbles/fizz → front ticks → tube lens remap → front digits. Ticks are never dropped for label bounds; later marks overwrite only intersecting pixels. `lens` and `lensCurve` use the same nearest-row remap in the simulator and firmware; `lensSmooth` is a simulator view option. Top ticks follow the curved tube. Top digits stay outside the tube lens; signed `topLens` independently pre-distorts them to compensate physical glass.
- URL params, applied on top of the restored session: `?fresh=1&preset=frizzante&t=10:09&along=0.3&across=0&settle=1&cuff=0&lens=0.6&lenscurve=1&lenssmooth=1&leather=black&grid=1&scale=3&demo=120&p.<key>=<v>`.
- Parts sourcing research: `docs/parts-sourcing.md` (board is 57.5 × 24.5 mm; 8×4 mm acrylic half-round rod recommended).
- **Pinned-liquid model + IMU hardening (2026-08-20, session 3)** — real accelerometer input no longer sends
  the visuals crazy, and the liquid can never appear/disappear with motion: `serial.ts` normalises by a slow
  gravity EMA (`GravityNorm`) instead of per-sample `|a|` (which amplified jerks 3-5×); `ImuFilter` clips tilt
  at ±1.2 g and low-passes accel with two cascaded poles; `stepTube` hard-caps slosh at ±14 px and surface
  angle at ±12° (`FILL_SLOSH_MAX_PX` / `ANGLE_HARD_MAX_DEG`, structural — params only tighten). Tilt now mostly
  changes the *light*: `edgeLightGain` scales frontBright + edge glow via `TubeState.edgeLight`. Params **v3**:
  migration drops stored physics/IMU tunings so the new soft defaults (fillSloshGain 6, angleTiltGain 5,
  angleMax 8, accelLpHz 1.5 …) take effect even with autosave. Regression: `npm run check:imu`
  (`sim/tools/replay-check.ts`) replays rest / wrist-wave / 3 g flicks / free-fall / ±90° / shake; worst edge
  deviation 18.3 px (budget 31.2) at sustained ±90°. Follow-up same day: ALL input sources (manual
  sliders/drag, flick, shake — injected as raw pre-filter values) now run through `ImuFilter`, so the
  IMU-filter sliders are feelable in the browser without the board (drag = accel LP lag, flick/shake = gyro
  HP/deadzone/clamp); per-frame readouts (`#imuraw`, slider outputs, fps, serial status) got fixed boxes +
  fixed-format text so the control menus no longer twitch from reflow (root cause of the recurring Tilt-input twitch: fieldset's default `min-inline-size: min-content` let the variable-length raw-CSV line widen the box past `width: 340px` — now `min-inline-size: 0` + fixed-length raw text). A live **IMU scope** (canvas in the
  Tilt-input fieldset, ~6 s window) plots raw vs filtered accel (grey/mint, ±1 g) and gyro (dim/bright blue,
  ±gyroMax) — the liquid's response is deliberately tiny, so filter tuning is judged on the scope, not the
  tube. Flick button = decaying ~150 ms raw gyro pulse (a single-sample kick died in the deadzone). Drop-end realism: `meniscusTiltGain` (tilt into the end bulges the meniscus, away flattens) and `meniscusAsym` (bottom-cling: mild at rest, gone when end-down — cap fills round, max when end-up — draining tail clings to the bottom wall), both driven by the smoothed `edgeLight` tilt, formula in `edgeX` (`sim/src/render.ts`).
- Open: user sign-off on the look; final palette; leather texture asset (`sim/public/assets/leather-tile.jpg`,
  CSS falls back to procedural noise if missing).

## Phase 3 — firmware liquid face (2026-08-20, session 4)
- `firmware/src/render.cpp` / `physics.cpp` are line-for-line ports of `sim/src/render.ts` / `physics.ts`
  (incl. JS `Math.round` semantics, all 5 bitmap fonts, sprite digits box-filtered **on device** from the
  seven RGBA sheets embedded in flash — `gen/sprites_gen.h`, 712 KB raw — so `digitFont`/scale/tint stay live params).
  Only deliberate deviation: per-pixel blends (`blend565`, `throughLiquid`) are integer fixed-point
  (t in 1/256, luma in 1/1000) → ±1 LSB on gradient pixels, verified 0 pixels off by >12/255.
- `Params` is a runtime struct generated from the sim preset: `python3 firmware/tools/gen_params.py presets/1.json`
  → `src/gen/params_gen.h` (struct + `PARAM_FIELDS` name/type/offset table + `PRESET_1`; first file given
  becomes `PRESET_DEFAULT`). The same run embeds digit sprites in `sprites_gen.h`. Re-run after exporting a
  new preset, changing a digit asset, or adding a key to `params.ts`
  (also add it to `FIELDS` in the generator). The field table is what the later Wi-Fi / GATT / JSON control will use.
- Pipeline per frame: IMU → `GravityNorm` → `ImuFilter` → `stepTube` ×2 (50 Hz fixed step, catch-up ≤5) →
  `renderTube` into a 72-row strip in **internal DMA RAM** → `display_push_strip_async` (panel DMA reads
  the strip directly, no bounce copy) while the other tube renders. The two strips (2 × 77 KB, internal DMA
  RAM) are owned by `display.cpp` (`display_strip(i)`) and also stage the old full-frame pushes, so the
  Phase 1 bounce buffers are gone: **free internal heap after boot ≈ 175 KB**. Wi-Fi may still want one
  strip back (see KAIZEN.md / docs/companion-handoff.md).
- Timing: render 18 ms for both tubes (digits ≈ 6 ms, front-bright ≈ 4, glow ≈ 3, fills ≈ 5), DMA
  overlapped → 40 fps. Stage costs measured with `p…=0` toggles over serial, no rebuild needed.
- **Pixel check vs the sim**: `python3 firmware/tools/compare-device.py` (board connected) → sends `x`
  (dumps TubeState + both strips), renders the same state headless through the real `render.ts`
  (`sim/tools/render-ref.ts`, fizz off), writes `firmware/.compare/{device,ref,diff}.png` + mismatch count.
  Last run: 293 / 77184 px differ, all ≤ 1 LSB (0 above 12/255).
- Not ported: cuff/gloss and lens smoothing. Fizz uses `esp_random()`. Clock is software-only (set with `t`).
- Next: Wi-Fi SoftAP / BLE GATT param control + preset select using `PARAM_FIELDS`; NVS-persist params
  and clock; real RTC/NTP. Plan: `docs/companion-handoff.md`. Long-term backlog (power/incremental
  rendering): `KAIZEN.md`.
