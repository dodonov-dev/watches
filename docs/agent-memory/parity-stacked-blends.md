---
name: parity-stacked-blends
description: check:meniscus 12/255 tolerance breaks when one stage alpha-blends the same pixel twice in the same direction; compose layers into one write instead of loosening the check
metadata:
  node_type: memory
  type: project
  originSessionId: dfea9812-f50e-4690-87b1-8b0e82ed0e8f
  modified: 2026-09-23T15:54:29.395Z
---

The sim/firmware parity check (`npm run check:meniscus`, threshold 12/255) tolerates exactly one
fixed-point blend rounding (±1 LSB of a 5-bit channel ≈ 8/255) per pixel per stage. Two separate
`pxa`/`rowPxa` writes on the same pixel that push the same direction (e.g. a liquid-tinted rim over the
dark fill on a white tube back) stack to 2 LSB = 17/255 and fail; a near-white layer over a light back
hid this before because its blend was a no-op.

**Why:** firmware `blend565T` quantises alpha to 1/256 and truncates 888→565 while the sim rounds; the
error is per write, so it adds up with the number of writes.

**How to apply:** when a stage gains a second layer on the same pixels (step 3e fill + blick + rim is the
precedent, 2026-09-23), accumulate a premultiplied 888 sum and alpha and write once; keep the plain
single-layer path for byte-identity. The same applies to a colour computed in steps: each intermediate
565 quantisation (through-liquid colour → mix → blend, the 2026-09-23 mark path: 17/255) stacks; compute in
888 float and `q` once at the write. Instrument both renderers at the failing pixel (`--out` keeps the
harness; `$OUT/check` re-runs natively) before guessing — the first two guesses (float vs 1/256 weight,
missing loop visit) were wrong. Related: [[params-mirror-firmware]], [[xtensa-float-costs]].

**2026-10-02, `marks-blick-moving` (403,34):** the two writes were a bitmap digit's shadow and body passes under
the band; the first already differed by one step because the sim blended with float glyph coverage (0.475)
and the firmware with `covT` (122/256). Fixed on the input side, not by composing: sim `drawGlyph` now takes
coverage in the firmware's 1/256 steps (`LUT_alphaT16`, `shadowT`). Check input quantisation before
restructuring writes. Tracing recipe: Proxy over `R.fb` in the `--out` sim cache + `fprintf` in a scratch
copy of render.cpp built with a one-job `check.cpp`.
