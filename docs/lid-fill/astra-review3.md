**Still an issue. Critical/high: none.**

The bidirectional τ sweep (−45°..45°, 0.002° increments) reduced the original case to **6.42/255 full-contrast luma per re-key**—below medium severity there.

- **Medium — [lid_law.h:29](/home/aadod/_PROJECTS/watches/firmware/src/lid_law.h:29), [lidLaw.ts:16](/home/aadod/_PROJECTS/watches/sim/src/lidLaw.ts:16): finer keys still cross a discontinuity.** At e=40°, θ=80°, transparency=.08, increasing τ from −41.260° to −41.258° changes the rear table entry from λ=4 to λ=0. The largest sampled full-contrast change was **255/255 at u=1**. Rendering black liquid over white backing (`surfaceBand=.35`, `edgeSoft=4`, fill/rim/blick zero) produced **95.4/255 luma change**, with 91 pixels exceeding 17/255. Exact-pose control peaked at 4.56/255. **Smallest robust fix:** cross-fade cached laws on replacement; finer angular steps alone cannot bound this discontinuity.

No other critical/high/medium findings in the delta. Law parity, meniscus checks, and board replay passed.
---
Follow-up (Fable, 2026-11-27): the table's back contact entry lam(1) is pinned to 0 on both sides (the next commit)
instead of a cross-fade: the flip was that one entry. Sweep of tau -45..45 deg in 0.002 deg steps, largest opacity change
per re-key x 255: 5.7 (e 40, theta 80, t .08), 10.6 (e 20, theta 89, t .8), 9.2 (e 30, theta 89, t .01), 1.6 (e 24,
theta 70, t .08). No fourth review round was run.
