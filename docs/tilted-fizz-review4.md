**Block 4 is not fully settled.** I found five P2 issues. The review-3 fixes, foam-life derivation and flash-placement decision are settled at code-review level; board bit-exact acceptance remains open.

1. **Lid geometry — P2: short plugs can have crossed endpoints; full tubes still get an open lid.**

   The lid displacement at [render.cpp:5268](/home/aadod/_PROJECTS/watches/firmware/src/render.cpp:5268) ignores the available column span and whether the time end is closed. [TypeScript]( /home/aadod/_PROJECTS/watches/sim/src/render.ts:2227) does the same.

   Native repro: `H=61`, `glassWall=3`, `viewElevation=20`, `backTilt=0.26`, free slug at `xs=60`, length `16.08`:

   - Home profile: `60`.
   - Front contact line: `56.8925`.
   - Back contact line: `76.08`.

   The front passes **3.1075 pixels behind the home profile**, leaving an inverted body interval. At full fill with elevation `60`, the centre-row front is `442.469` and back is `536`, while `fizzExposed=0`: a **93.53-pixel lid** is published where the kernel considers the end closed.

   **Fix:** budget the lid against both end profiles, maintaining ordered body bounds through short-column transitions. Handle the closed-end transition explicitly and preserve the physical glass constraint. Add short free-slug, empty/full and remaining-mode regressions checking body ordering and endpoint support. The unrestricted ellipse is insufficient at these boundaries under the retained-plug convention.

2. **Time-at-back-line — P2: cap wobble moves the rear apex off the time edge.**

   At [render.cpp:5273](/home/aadod/_PROJECTS/watches/firmware/src/render.cpp:5273), subtracting `capR.k * capR.h` leaves `wallX`’s `−capR.k * capR.cap` term. At the centre, the back apex is therefore **`xe − k·cap`**, not `xe`.

   Native repro: the same geometry, length `268`, `xs=60`, `cap=4`. The expected time edge is `328`; the rear apex is `324`. With `cap=0`, it is `328`. Sim and firmware share the error; the marks do not receive this displacement.

   **Fix:** normalize the ring against its complete centre-row offset before applying the ellipse. Preserve intended shape variation without translating the reading point. Test nonzero positive/negative `cap`, including moving states.

3. **Device replay — P2: `backTilt` is missing from captured render state.**

   [main.cpp:944](/home/aadod/_PROJECTS/watches/firmware/src/main.cpp:944) omits it from `STATE`; [compare-device.py:74](/home/aadod/_PROJECTS/watches/firmware/tools/compare-device.py:74) consequently reconstructs a tube with `backTilt=0`.

   Headless repro with `H=61`, `glassWall=3`, elevation `20`: actual tilt `0.26` produces lid width `19.1875`; replay’s zero tilt produces `19.6544`. Otherwise identical renders differ at **622 pixels**, with approximately **57/255** maximum channel difference.

   **Fix:** append `backTilt` to the dump and parser, preserving compatibility with older records. Add a dump/replay round-trip with nonzero tilt and the lid enabled. Current static-fixture parity does not validate this capture path.

4. **Surface model / `b43fe20` — P2: the advertised whole-step transverse cap excludes uncontacted drift.**

   [render.cpp:4158](/home/aadod/_PROJECTS/watches/firmware/src/render.cpp:4158) initializes `push=0`. Drift placements run uncapped; `FOAM_PUSH` is enabled only for subsequent contacts. A bubble receiving no contact placement never gets capped. TypeScript matches this.

   Native repro: one foam bubble, flat zero-width band, `r=r_ref=2.5`, `U=48`, `dt=0.02`, unit buoyancy `(0.6, 0.8, 0)`. It moves **0.4608 pixels** transversely, exceeding the documented whole-step limit **0.339411 pixels**.

   **Fix:** enforce the selected `FOAM_PUSH·U_i·dt` budget from the first placement, including drift. Test isolated foam and contacting foam under substantial transverse buoyancy. The drift formula, equal-share parting and resident no-push-down policy otherwise match the supplied model.

5. **NVS migration — P2 persistence regression, although layout rejection is safe.**

   The CRC/size checks at [main.cpp:138](/home/aadod/_PROJECTS/watches/firmware/src/main.cpp:138) correctly prevent interpreting an old blob as the new layout. However, both v31 and v32 saved tuning are silently abandoned.

   A mock using the actual load/flush functions reproduced: a valid **720-byte v32** blob with `fizzCount=237` is never read; the **724-byte v33** defaults use `fizzCount=10`. A subsequent saved edit overwrites the old blob.

   **Fix:** migrate through an explicit legacy layout, initialize `viewElevation=0`, and retain the v31 shading conversion. Preserve the old blob on read/write failure. The documented one-time reset explains the behavior but does not preserve saved tuning.

**Performance bounds — settled mathematically for the intended geometry; board bit identity remains pending.** The chord inequality gives a lower support bound. The box helper conservatively bounds `k`, uses minimum row distance and scans a superset of possible support rows. The global surface minimum is likewise conservative. Box reuse checks containment; unsupported cases fall back to exact evaluation. I found no incorrect bound direction or skip predicate.

The disclosed board divergence from frame 239 still prevents calling the pass bit-exact on ESP32-S3. **Fix:** finish contraction pinning, inspect generated arithmetic and rerun board sequence equality. Host equality cannot close that issue.

**Other items settled:** review-3 side-wall and stale-contact fixes passed their targeted self-tests; the lone-obstacle behavior passed. Foam-life derivation matches the specified formula and rounding. Moving the stepper to flash is justified by the recorded BLE failure/headroom comparison. Added firmware scratch remains fixed-capacity and boot-allocated. Ordinary lid geometry, fill gradient and bitmap/tick thinning passed, subject to the issues above. The explicitly deferred lid-fizz flip is not counted as a new finding.

Validation: **521** native/sim meniscus frames passed, maximum channel difference **9/255**, UBSan clean; **4/4** common-input vertical jobs passed with self-tests and comparator mutations; **80/80** native before/after preset/scene runs were identical over **350 frames each** with contraction disabled. No repository files were modified and no serial device was accessed.