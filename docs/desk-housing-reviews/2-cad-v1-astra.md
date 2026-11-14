**Hold the print order until the two fit checks below are resolved.** The nominal CAD is coherent; the remaining risks are hardware envelopes and tolerances.

Read-only verification: all six STEP parts match the code and are valid single solids; all six STLs are watertight. Re-running the static and swept-path checks against the exported geometry passed.

| Check | Verified result |
|---|---|
| Slots versus AA | AA Z **22.50–90.15**; rods **22.00–90.65**; slots **21.60–91.05**. X centres **±10.23** correctly centre the 5.94 mm drawn tubes. |
| Front chamfer | Inner opening **8.60 × 69.45**; face **14.60 × 75.45**; face bridge **5.86**. Correct for the final zero-rim decision. |
| Stack | PCB Z **15–93.85**; ceiling **94.35**; shell **101.35**; total height **104.35**. |
| Insertion | **4.50** rearward offset; battery rear reaches Y **28.40**, leaving **2.60**. Rod/front clearance **0.25**. |
| Logo/light box | Letters **24 × 15.137**; minimum strip **1.230**; diffuser **26.259 × 18.937 × 2**; assumed RST clearance **0.300**. |

Findings, in priority order:

- **[blocker] Real hardware fit remains unverified.** The sweep assumes buttons protrude **1.0 mm**, and J5/I²C plugs—including wire bends—only **4.0 mm**. RST has **0.30 mm** spare; plugs have **1.325 mm**. The accepted **9.0 mm overall stack** does not independently establish the mounting-nut bearing plane or clearance for the mated BAT connector beneath the carrier. **Fix:** measure the fully connected board, nut faces and actual screw engagement; substitute those envelopes and repeat the sweep. These assumptions are explicit in [housing.py](/home/andrey/_PROJECTS/watches/cad/desk/housing.py:53).

- **[blocker] There is no manufacturing tolerance budget for the locating stack.** The carrier has only **0.30 mm total vertical freedom**: 0.10 below, 0.20 above. Rod end clearance is 0.40; RST clearance 0.30; lid plug clearance 0.30 per side. Ordinary dimensional error or bow can prevent closure or put the rods/glass under load. HP suggests **0.40 mm between separately printed mating faces** as a starting point. **Fix:** obtain the printer’s tolerances, budget the complete stack, and specify which carrier stop surfaces will be finished to fit while keeping the rods unloaded. [HP guidance](https://www.hp.com/us-en/printers/3d-printers/learning-center/how-to-design-3d-print-model.html)

- **[should] Magnet meat is overstated.** **0.864 mm** is correct above the bottom chamfer; at the shell rim, the **0.5 mm break leaves only 0.364 mm**, below even the code’s 0.4 minimum. **Fix:** include the chamfer in [the placement calculation](/home/andrey/_PROJECTS/watches/cad/desk/housing.py:262). Re-optimising gives approximately **X ±22.29, Y 2.71/31.29**, with **0.61 mm** minimum meat; move matching lid holes too. Glue magnets rather than forcing an interference fit.

- **[should] Mounting-hole pitch is wrong.** [NUTS](/home/andrey/_PROJECTS/watches/cad/desk/housing.py:150) uses both edge insets, yielding **72.85 mm**, while `NUT_DZ=72.75` is unused. The top row is **0.10 mm too high**. Ø2.3 clearance may accommodate this, but countersinks encourage misalignment. **Fix:** derive the second row from the measured 72.75 pitch; with the lower row at Z18, upper becomes **90.75**.

- **[should] USB usability is not covered by the socket dummy.** The receptacle mouth is recessed **3 mm** behind the outside surface. A plug’s overmould must clear the **13.5 × 7.5 R3** tunnel sufficiently for full engagement. The cradle also assumes a bare underside except for the front solder relief, and has no positive upward retention. **Fix:** check the actual soldered breakout and intended cable; establish adhesive retention in the existing cradle and verify insertion/extraction without PCB movement. [Cradle code](/home/andrey/_PROJECTS/watches/cad/desk/housing.py:432)

- **[should] Wiring and reverse assembly need an explicit route.** The sweep excludes USB/LED/battery wires, solder joints and glue. For the prescribed reverse motion, the lid ribs must descend about **25.9 mm** to clear the carrier legs before the carrier moves backward. **Fix:** provide that usable lid travel in the J5 harness, route wires clear of rib faces and the rim, and arrange accessible LED disconnection/slack. Fit and test LEDs, diffuser and leads **before gluing the light box**; then insert the carrier up/back, move forward, and raise the lid.

- **[should] The ribs locate but do not nominally preload.** Their **0.50 mm gap equals the specified 0.50 mm foam**, giving zero designed compression. Battery rails likewise do not retain the cell against rearward movement. **Fix:** specify controlled foam compression—e.g. **0.10–0.20 mm**, subject to foam stiffness—and removable battery adhesive; include their thicknesses in the stack and sweep. [Ribs](/home/andrey/_PROJECTS/watches/cad/desk/housing.py:439)

- **[should] Thin features need controlled handling and finishing.** The accepted chamfer ends at mathematical zero thickness; the comment that it “prints as ~0.2–0.3” is not a guaranteed outcome. Logo strips **1.23**, back plate **0.8**, rails **1.2**, ribs **1.8**, and legs **3 × 2 mm** are plausible PA12 features, but the long carrier/rails and test strip can bow. **Fix:** have the bureau approve orientation for flatness and gentle depowdering; avoid aggressive tumbling of knife edges/logo strips. Preserve the accepted chamfer and inspect the coupon before installing glass. [HP warpage guidance](https://www.hp.com/us-en/printers/3d-printers/learning-center/how-to-design-3d-print-model.html)

- **[should] Small-hole finishing must be specified.** Magnet holes offer only **0.05 mm radial clearance**; M2 holes **0.15 mm**. **Fix:** finish to Ø2.1 and Ø2.3 as needed, depth-control the **1.2 mm blind magnet pockets**, and clear the **1.2 mm wire grooves/LED troughs** before assembly. No sealed powder cavity was found; these accessible small recesses are the cleaning concern. [Materialise guidance](https://www.materialise.com/en/academy/industrial/design-am/pa12-mjf)

- **[nit] Remaining specification/documentation deviations:** the flat-front switch now selects **0 mm**, breaking the promised 1.5 mm variant; give that variant an independent thickness. Update stale build notes to face openings **14.60 × 75.45**, bridge **5.86**, insertion spare **2.60**, and coupon **86.03 × 85.45**. These dimensional changes otherwise follow the accepted decisions.

What is right: the final chamfer, pitch, measured stack, smaller logo/R3 cavity and J5 approach are implemented.
The nominal insertion sequence works, including the glued-in light box.
Exports are consistent and printable solids; no nominal collision or sealed powder trap was found.
The coupon reproduces the chamfer and real pitch; the logo meets the print strip target, though not the 2 mm wood target.