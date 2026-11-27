Critical: none. High: none.

1. **Settled:** directional wall intersection and the documented monotonic envelope address the zero-path issue.
2. **Settled:** the residual ≤2.5% opacity step is acceptable, below medium severity, given the explicit `surfaceBand=0` semantics.
3. **Settled:** fill and marks now use the physical coordinate.
4. **Settled:** bounds are per law, per entry, and weighted by actual input ULP differences.

5. **Medium — [render.cpp:5687](/home/aadod/_PROJECTS/watches/firmware/src/render.cpp:5687), [render.ts:2862](/home/aadod/_PROJECTS/watches/sim/src/render.ts:2862): pose-key transitions visibly flash.** Sweep τ upward from −45°: at e=20°, θ=89°, transparency=.8, the transition −44.50°→−44.49° changes opacity at q=1, u=31/32 from .556 to .396—far above the claimed 1%. With `surfaceBand=.35`, `edgeSoft=4`, black liquid and white backing, 84 pixels change by >17/255; maximum ≈33/255. Exact-pose control peaks at one colour step. **Smallest fix:** cross-fade old/new laws when re-keying, using fixed per-tube storage. First-use, hysteresis bookkeeping, and cache isolation otherwise look sound.

6. **No medium-or-higher issue:** colour mixing uses bounded integer/float arithmetic.
7. **No medium-or-higher issue:** the exception remains narrowly capped; the run reports only the documented pixel.

No other medium-or-higher findings. Law checks, meniscus checks, board replay, and TypeScript passed; leak detection was disabled for the sandbox’s ptrace limitation.