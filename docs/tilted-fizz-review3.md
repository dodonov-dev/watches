**Point 7 and the four review-2 correctness/test fixes are settled at code-review level. The two board-driven changes still have two P2 issues. Point 9 remains open.**

1. **Surface-plane spreading and the `k` floor — issue, P2: bounded state motion can still produce a large rendered jump.**

   Packing caches—and subsequently raises—`k` at [render.cpp:4031](/home/aadod/_PROJECTS/watches/firmware/src/render.cpp:4031). Its transverse moves can change physical depth substantially enough to change the true endpoint coefficient. Rendering independently recomputes that coefficient from the updated body in [render.cpp:5883](/home/aadod/_PROJECTS/watches/firmware/src/render.cpp:5883).

   A native reproduction with radius `2.5`, band width `10`, and `fizzSpeed·dt = 0.96` produced:

   | | Before packing | After one step |
   |---|---:|---:|
   | Physical `k` | 1 | 0 |
   | Packing `k` | 1 | 1 |
   | State axial position | 108.259 | 108.258 |
   | Rendered axial position | 108.259 | 98.258 |

   The bubble moves around the side wall within its transverse speed limit, yet visibly jumps backward **10 pixels**. On the following step, the floor raises packing `k` to `0.904`, while rendering still uses zero.

   **The floor is a numerical workaround, not a physically consistent interpretation of the defined geometric `k`.** It also masks the problem in statistics that measure only state positions.

   **Fix:** keep `k` derived from the current body. Limit the coupled axial/transverse move so its new whole-disc endpoint remains compatible with the permitted axial retreat. Shorten an inadmissible transverse move using a bounded calculation or fixed-count subdivision; retain unresolved overlap for subsequent steps. Recompute the endpoint after placement. Do not pass the artificial floor into shading merely to conceal the disagreement.

   Add a banded side-wall crossing regression that checks **rendered position**, physical endpoint support, and displacement bounds. The existing packing self-tests use zero-width bands, so they miss this case.

2. **Overdamped contact change — issue, P2: moving off the wall leaves stale wall contact.**

   The contact correction at [render.cpp:4324](/home/aadod/_PROJECTS/watches/firmware/src/render.cpp:4324) can move a bubble inward. It sets `FIZZ_C_WALL` when projecting an outside position onto the bore, but never clears an existing flag when the corrected position is inside.

   Reproduced with a large free bubble contacting a smaller foam bubble: the free bubble’s eroded radius was `16`; contact moved it from `z=16` to `z=15.7284`, but its wall flag remained set. The next call to [fizzMoveV](/home/aadod/_PROJECTS/watches/firmware/src/render.cpp:4220) normalizes it back onto the wall before advancing. This introduces an artificial displacement and applies wall mobility to an interior bubble. TypeScript has the same issue.

   **Fix:** reconcile wall contact with the corrected physical position: clear it when safely inside, retain/set it at the boundary using a small numerical tolerance. Test unequal bubble sizes, inward contact deflection, and the following timestep.

   Removing inward approach instead of applying an instantaneous separation impulse is otherwise a sound direction for this overdamped model.

3. **Point 7 — settled in implementation; final visual acceptance belongs to point 9.**

   Back-half/front-half ordering preserves slot order, and tile lists preserve that planned order. Pinpoint attenuation uses continuous depth; the endpoint veil applies to nonpopping vertical bubbles as well as popping ones. Keeping four cached tint levels is consistent with the plan and the reported transition measurements.

   I found no additional point-7 defect. The endpoint inconsistency above affects its presentation, but does not require redesigning the depth shading.

4. **Review-2 follow-ups — settled.**

   The inward-release path now checks the opposite wall; render correction uses whole-disc, lens-compensated support; packing tests physical 3D distance; and the parity harness now compares independently generated strokes and surfaces before replacement.

   Vertical foam tolerances are tightened, corrupt input checks and mutations are expanded, and an independent full-pipeline diagnostic is retained. Calling `--free` **common-input kernel parity** accurately describes its evidence; it is not independent end-to-end parity.

5. **Waiting behind a lone foam bubble — sometimes legitimate, not a reason to force parking or popping.**

   In this deterministic overdamped model, an exactly centred approach can have zero tangential motion: waiting is an admissible symmetric solution. An offset approach with available space should slide around the obstacle while respecting the bore and surface constraints.

   Test those cases separately. If near-symmetric contacts routinely remain stuck despite a clear lateral route, improve the constrained tangential motion. If deliberate symmetry breaking is needed for the look, use a small, bounded physical perturbation—not the cosmetic row bias. Contact alone should still neither start foam life nor trigger recycling.

6. **Point 9 / memory — still pending.**

   The additional `1,920` bytes per tube are fixed boot-allocated PSRAM, consistent with the memory rule. Host timing improvements do not settle the IRAM tradeoff. Retain the planned LCD-board comparison of flash versus IRAM at the stand pose, including BLE activity, minimum internal heap, and largest free block.

I reran four vertical common-input jobs; all passed, along with native self-tests, 20 comparator mutations, nine generation mutations, and four corrupt-input checks. The two targeted native reproductions above expose behavior those checks do not cover. No repository files were modified.