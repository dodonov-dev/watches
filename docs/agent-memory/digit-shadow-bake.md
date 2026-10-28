---
name: digit-shadow-bake
description: "Digit shadow is baked into the scaled sprite (2026-09-22); why it needs two planes and a Mark::bakedT flag, and what a mark's transparency really does behind liquid"
metadata: 
  node_type: memory
  type: project
  originSessionId: 85ea2863-a144-47de-9c43-67f448331f56
  modified: 2026-09-22T11:07:47.247Z
---

The digit shadow (digitShadow/Strength/Offset/Color) used to be a full second glyph pass (~4.8 ms of the
~9 ms digits cost). Since 2026-09-22 scaledGlyphs (sim/src/render.ts and firmware/src/render.cpp,
`bakeShadow`) composites it into the sprite once per parameter change. Non-obvious parts:

- Behind liquid the compositor blends a mark's colour toward the pixel by liquidTransparency T and
  THEN by coverage, per layer. Two layers therefore reach opacity 1 - (1 - T)^2, which one mark at T
  can never produce, so the behind-liquid plane must carry T inside its alpha and the Mark must skip
  its own T step (`Mark::bakedT` / markFn `bakedT`). Hence two planes per glyph (c/a behind air,
  cw/aw behind liquid) and GLYPH_POOL_PX sized from the slider maxima (scale 6, offset 4, two planes: 31280 texels, ~92 KB PSRAM per tube). Guard A == 0 (transparency 0) in bakeShadow: 0/0 -> NaN -> UB on the int cast.
- The plane must be chosen per PIXEL with the compositor's own edge test (`Mark::inLiquid`), not per
  column: the wet/dry column split is taken at the middle row and the meniscus rows near the walls
  differ from it (that mismatch produced 187/255 errors before the fix).
- Both bakes must use the SAME transparency value: the firmware first baked with the Mark's quantised
  T/256 while the sim used the float; the +-1 alpha that produced flipped the "colour of the heaviest tap"
  choice at near-ties between a dark shadow texel and a bright body texel (25/255 pixels). Bake with the
  clamped float on both sides, and the sim picks the tap colour with the firmware's 1/256 weights.
- The sprite box filter used `x / sx` for its sheet-column bounds; float (firmware) and double (sim) land
  on opposite sides of an integer there, so the board dropped the glyph's last sheet column (body alpha
  68 vs 136). Exact ratios `x * width / gw` on both sides fixed it. Lesson: the parity tool's `> 12/255`
  count hides 1-LSB-class gaps that any high-contrast bake will expose; check host-vs-sim with
  scratchpad hostjob/gen.py (renders a .compare job.json with the firmware code, no board).
- Residual differences vs the two-pass renderer are one 565 step almost everywhere; larger only in the
  wall-band fade rows behind air and with markContrast > 0 (see KAIZEN).
- Since 2026-09-26 the contrast floor on a baked texel is taken at full glyph coverage: a = max(T, cov),
  floor(mix(bg, texel, a)), blended by cov / a (sim markFn, firmware Mark::wetColourT, sprite-run MODE 3).
  Before that the floor saw the raw texel, so markContrast never reached shadowed sprite digits while ticks
  followed it ("marks much brighter than digits").

**Why:** the user uses the shadow as a cheap "bold"; keeping the exact look mattered more than a simpler
dilation. **How to apply:** any future "bake N mark layers into one" idea must model the per-layer
T-then-coverage order; verify with `firmware/tools/check_render_frames.py --tolerance N` against a saved
pre-change render.cpp (it renders 4000 scenes on the host, no board). Related: [[drawtube-hot-loops-noinline]],
[[params-mirror-firmware]].
