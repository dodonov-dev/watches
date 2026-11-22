**Points 4–6 are not fully settled.** Three correctness issues remain, plus a gap in the revised parity checks.

1. **Point 4 — issue, P2: inward release can cross the opposite wall.**  
   [render.cpp:4141](/home/aadod/_PROJECTS/watches/firmware/src/render.cpp:4141) clears wall contact and advances freely for the entire remaining timestep, without testing another collision.

   Reproduced with eroded radius `a=0.5`, starting at `y=0, z=0.5`, inward speed `60`, and `dt=0.02`: the result is `z=-0.7`, outside the bore, with wall contact cleared.

   **Fix:** route inward release through the first-contact calculation again. Handle a start exactly on the wall with inward velocity by choosing the positive forward intersection, then apply wall motion for any remaining time. Mirror this in TypeScript. Add containment tests for nearly fitting bubbles, maximum speed, and forcing reversal.

   The ordinary flight, tangential mobility, ridge convergence, pose plumbing, and closed-end lifetime behavior otherwise look consistent with the plan.

2. **Point 5 — issue, P2: render correction still checks only the centre row.**  
   [render.cpp:5807](/home/aadod/_PROJECTS/watches/firmware/src/render.cpp:5807) uses `fizzEndCentre`, although the current surface can differ from the surface used by the stepper. The nonapproaching open endpoint also uses this shortcut at [render.cpp:4265](/home/aadod/_PROJECTS/watches/firmware/src/render.cpp:4265).

   A concrete example: radius `5`, zero band width, and a profile rising one pixel per row. The whole-disc helper gives an axial target of `98`; the centre-row clamp allows `100`. A receding or changing surface can therefore leave part of the disc beyond its permitted protrusion.

   **Fix:** use whole-disc support against the current profiles for render correction and the other open endpoint. Use the actual lens-compensated footprint—the present support helper assumes a circular footprint. Compute this once per bubble, retaining the existing per-pixel renderer.

   The `k/L/P` formulation, stroke publication, and pop-hook connection are otherwise in place. Deferring nonpopping depth veil to point 7 is consistent with the stated scope.

3. **Point 6 — issue, P2: packing is still effectively 2D for partially separated depths.**  
   [render.cpp:4077](/home/aadod/_PROJECTS/watches/firmware/src/render.cpp:4077) rejects a pair when its depth separation alone exceeds the contact distance, but otherwise resolves its overlap using only axial distance and display-row distance. Smaller depth separations are ignored.

   Reproduced with contact threshold `5.5`, axial separation `5`, physical transverse separation `0`, and depth separation `3`. Their true distance is `5.831`, so they do not overlap. Nevertheless, a zero-timestep packing pass moves their axial positions from `100, 95` to approximately `100.255, 94.745`.

   Packing also uses the cosmetic row bias in its collision geometry, making that bias affect physical motion.

   **Fix:** use physical coordinates throughout packing contact, relaxation, and residual-overlap correction. With depth held fixed, the required separation in the axial/transverse plane is `sqrt(max(0, m²−dz²))`. Remove the display bias before these calculations and keep physical transverse positions current during placement. Apply the same correction to the preliminary touch test and TypeScript implementation.

   The step-start snapshot, true-3D free-to-foam contact, and own-endpoint requirement for starting foam life address the earlier chain-propagation problem.

4. **`--free` deviation — acceptable as a motion-kernel test, insufficient as end-to-end acceptance.**  
   Supplying identical frame inputs while each implementation evolves its own bubble state and RNG is a useful way to isolate accumulated kernel divergence. The reported precision is meaningful for that narrower claim.

   Two validation gaps remain:

   - The claimed separate geometry comparison does not explicitly compare `strokeR/L`: the state output at [check_fizz_steps.py:162](/home/aadod/_PROJECTS/watches/firmware/tools/check_fizz_steps.py:162) contains only the two surface arrays. Meanwhile, `--free` replaces both simulator stroke arrays with firmware values.
   - [check_fizz_steps.py:547](/home/aadod/_PROJECTS/watches/firmware/tools/check_fizz_steps.py:547) still permits **2 pixels** of foam-position disagreement, including vertical jobs. That tolerance undermines the new tightly matched vertical kernel.

   **Fix:** describe this mode as common-input kernel parity; explicitly compare independently generated surfaces **and strokes before replacement**; tighten vertical foam tolerances while retaining any justified legacy landscape allowance; add mutations for stroke values and foam positions. Preserve an independent full-pipeline test to detect integration drift. Validate the injected input records’ frame indices, dimensions, lengths, and finiteness too.

   The 14/16 result should remain explicitly qualified by its two failing jobs.

5. **IRAM +5,932 bytes — not justified for acceptance yet.**  
   Internal RAM is scarce enough that putting the entire approximately 7.3 KB vertical stepper into IRAM needs LCD-board evidence. Host timing and `DRAM +64` do not establish either a board performance benefit or sufficient BLE headroom. The point-8 board result does not validate this block.

   **Concrete next step:** compare otherwise identical LCD builds with the vertical orchestration function in flash versus IRAM. Keep only measured hot portions in IRAM if needed. Check linker placement alongside minimum free internal heap and largest allocatable block during rendering and BLE connection, subscription, parameter traffic, and reconnection, including fast mode.

   The fixed per-tube PSRAM scratch allocation is consistent with deterministic allocation; its additional size should remain covered by boot-allocation failure checks.

The review-1 fixes for birth-span validation, geometry-triggered body rebuilds, blocked-birth diagnostics, contact serialization, comparator hardening, and landscape phone mapping appear addressed.

I reran four common-input free-running jobs—upright, prolonged back tilt, crowded foam, and height changes—and their native self-tests and comparator mutations passed. Targeted native checks reproduced the issues above. No repository files were modified.