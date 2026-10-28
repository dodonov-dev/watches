---
name: residue-physics
description: "Residue model since 2026-10-02/03: absolute Bretherton deposit, stain depth = annular path × traceAmount, wet buffer drained by ρgh²/3μ (traceDrain, v27); the traps hit while building it"
metadata:
  node_type: memory
  type: project
  originSessionId: 359ce7b8-ba28-4b56-b414-485cd2742af1
  modified: 2026-10-03T10:26:25.785Z
---

2026-10-02 (docs/residue-physics-handoff.md executed), revised 2026-10-03 after an Astra review the user asked for
(critical bugs + realism; user picked the physical options except stain lifetime, kept fading with drying):
deposit = `filmEta(p, U)`/0.1 (physics owns the Bretherton law); stain = B^(1−τ)·C^τ with τ = traceAmount ×
FILM_PHI[(A·K + 2^15) >> 16] (A = η(2−η)·2^16 per column, K = 256/(1−u²) per row, integers on both sides);
near a receding line the coat and the wet film count once (max). `traceWet` drained by `drainTrace`,
c = traceDrain·|g|·(w/FULL)², `traceDrain` = ρg(R/10)²/3μ px/s (derive.ts from ρ, μ, r; hand-made presets:
`legacyTraceDrain` from capLength + contactDyn). `traceThin`, `traceFollow`, `TRACE_TILT_DRY`, the trace gamma gone.

**Why:** physical laws make the residue subtle — the user's watery repro preset shows almost nothing, honey shows
wall legs; that is the intended outcome, not a regression to re-tune.
**How to apply:** a conservative flux splits a film into thin columns at its front: never delete a column below a
visibility threshold while it is still wet (Astra caught it: a tilted thin film vanished 4× faster). End-to-end
`stepTube` checks, not flux-only ones. h³ drainage spreads as t^⅓; test horizons must follow. Per-column physics loops
on the S3: inline min + (int) truncation, no libm fminf/floorf. Scratch tables per Tube (both cores render), not stack
or file-static. Checks: `check:imu` residue scenarios, `check_residue.py` (tint + depth law vs reference).
Related: [[imminent-residue]], [[xtensa-float-costs]], [[firmware-two-core-render]].
