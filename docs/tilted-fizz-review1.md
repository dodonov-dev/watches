**Block 1 is not fully settled.** The fixed-capacity scaffolding is sound, but points 1 and 3 need corrections. Point 2 has one landscape input regression.

I reproduced the 12/12 lockstep pass, birth self-test and allocation-failure check. I also ran independent stepping and targeted native repros. No repository files were modified.

**Point 1 — Issue: parity acceptance is too permissive.**

- **P1: The comparator accepts invalid state and unbounded surface differences.** In [check_fizz_steps.py:410](/home/aadod/_PROJECTS/watches/firmware/tools/check_fizz_steps.py:410), comparisons use `abs(a-b) > tolerance` without checking finiteness. Replacing a bubble’s `x` with `NaN` passes. Surface coordinates, liquid length and shift are recorded but never constrained; changing a surface value from 10 to 1000 also passes.

  **Fix:** Validate record lengths and reject all non-finite state. Enforce justified bounds on the surface inputs, length and shift, or explicitly supply common surfaces to both kernels and test surface generation separately. Add comparator mutation checks for these cases.

- **P1 for final acceptance: lockstep plus `FOAM_TOL = 2` does not establish trajectory parity.** Reloading firmware state every step erases accumulated divergence. A two-pixel allowance can conceal different packing/contact decisions, which subsequently affect lifetimes and RNG consumption.

  Independent runs failed in all three jobs I checked:

  | Job | First failure |
  |---|---|
  | Upright | Step 218, tube 1 |
  | Height + mode changes | Step 242, tube 1 |
  | Landscape | Step 35, tube 0 |

  **Fix:** Keep lockstep as a diagnostic, label its result accordingly, and require independently advanced vertical runs for acceptance. Make the new vertical contact helpers use matching arithmetic and deterministic contact/tie rules. Do not widen tolerances to accommodate branch divergence.

**Must `--free` hold?** Yes, for the completed vertical implementation: exact discrete state and RNG consumption, with a small, justified numerical bound for continuous state. Lockstep alone is insufficient.

The disclosed legacy foam differences can remain a **temporary scaffold exception** until points 4–6 replace those helpers. Do not repair landscape arithmetic merely to make its sim/native `--free` comparison pass; its existing native old/new byte-identity check remains the regression gate. Also add contact state to the test serialization when point 4 starts using it.

**Point 2 — Mostly settled; one P2 regression.**

Signed normal, filtering before `inputGain`, the low-magnitude pose hold and firmware input capture are reasonable. Not consuming `Pose` in the current motion scaffold is an acknowledged point-4 dependency.

However, [main.ts:287](/home/aadod/_PROJECTS/watches/sim/src/main.ts:287) applies `orientationTilt()` unconditionally. This changes the landscape phone’s existing `along` input from

\[
\sin\gamma
\quad\text{to}\quad
\cos\beta\sin\gamma.
\]

At \(\beta=60^\circ,\gamma=45^\circ\), it changes from approximately 0.707 to 0.354. That affects landscape liquid motion and lighting despite the vertical-only kernel gate. The current phone tests check pure-axis cases, which miss this regression.

**Fix:** Gate the corrected phone mapping to vertical mode, preserving the old landscape mapping, or explicitly obtain approval for this separate behaviour change. Add a combined-angle landscape regression. When wiring point 4, pass the captured gain-free `Pose` through every stepping path, including sequence jobs and AB mode; the current harness parses `normal` but does not use it.

**Point 3 — Allocation settled; births and state rebuilding have P2 issues.**

The sidecar is fixed-capacity, per tube, allocated at boot in PSRAM, and allocation failure correctly rejects initialization. The added body storage is 5,760 bytes per tube. Keeping legacy motion temporarily is acceptable as a disclosed scaffold; I am not counting the deferred wall-motion replacement as a new finding.

Three current foundation issues remain:

- **Births can succeed when no axial space exists.** [springSpawnV:3755](/home/aadod/_PROJECTS/watches/firmware/src/render.cpp:3755) averages reversed bounds and returns success. Native reproduction: with surfaces at \(x=0\) and \(x=1\), a radius-2.5 bubble is successfully born at \(x=0.5\). Scattered respawn inherits the same midpoint behaviour; initial `ensureFizz` births sample `x` independently of the row’s surface bounds.

  **Fix:** Route vertical births through a common valid-span check. If the required interval is empty, leave the slot idle and preserve bounded birth credit. Use the published profiles for initial scattered births as well. Extend the self-test to short columns, steep/curved profiles and initial `ensureFizz`; its current 300-pixel straight column does not exercise these failures.

- **Body reconstruction does not actually constrain the body to the disc.** [fizzBodiesFor:3761](/home/aadod/_PROJECTS/watches/firmware/src/render.cpp:3761) clamps only `z`. If `|y| > R-r`, setting `z=0` cannot restore containment.

  Native reproduction: shrinking height 54→20 leaves a bubble at `y=30.5`, although its allowable centre radius is only `1.5`; its displayed row remains 40. The invalidation key also ignores same-height changes to `glassWall`, `fizzSize` and `fizzSizeVar`.

  **Fix:** Track all geometry/radius inputs affecting containment. Define a deterministic resize policy that constrains both coordinates and updates the derived row/tint, retiring visibly impossible fits. Preserve continuous depth for existing vertical bodies rather than reconstructing it from a tint bin on every geometry change. Test containment immediately after rebuilding, before motion can conceal the error.

- **Blocked births are counted but not visibly reported.** [fizzBlocked:3773](/home/aadod/_PROJECTS/watches/firmware/src/render.cpp:3773) has no production diagnostic consumer; the sim getter is likewise not surfaced.

  **Fix:** Expose the counter/reason in the existing firmware status output and a throttled sim diagnostic. A test-only readable counter does not satisfy the “fail visibly” requirement.

These corrections belong in the current foundation. Block 2 can proceed against the scaffold, but the reported lockstep pass should not be presented as completed sim/firmware parity.