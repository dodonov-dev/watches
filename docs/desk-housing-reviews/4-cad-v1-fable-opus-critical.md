# CAD v1, critical-only reviews: Fable and Opus (2026-11-14), summarised

Both reviewers found **nothing critical** for the prototype parts (shell, flat lid, test strip). The model changed while
they reviewed: PROTOTYPE mode, 0.5 tape, the magnet fix, then the flat lid. Both re-checked against the final state.

**Verified independently:**
- Slots against the AA: z 21.60..91.05 (AA 22.50..90.15), x ±10.23.
- Bevel in the solid: 8.62 wide at the glass, 14.58 × 75.43 on the face.
- The logo cuts fully through, with no islands; thinnest strip 1.230.
- Magnet holes identical in shell and lid, 0.61 wall including the bottom chamfer. ~59 gf per pair at a 0.4 gap.
- All STLs are watertight; no trapped powder.

**Notes that still matter:**
- **Tape lands for the glass:** 5.5 mm at the USB end. Only 1.67 mm at the far end, between the slot end and the glass
  edge: cut that strip ≤ 1.5 mm wide or it shows in the slot. Use small patches or removable tape, so the board can
  come out again.
- **The shell is not neutral to USB/battery:** it fixes the space under the PCB, the hole height and the cavity depth
  (28 inside). Since then: MOGOOD adapter (PCB bottom 12.5), battery 10 × 35 × 68: both checked in the model.
- **If the carrier / light box come back (`PROTOTYPE = False`):**
  - The light box RST clearance is 0.30. Needed 0.6: set `LB_BTN_CLR` 0.6 with `LB_BACK` 0.6 (keeps the 1.0 diffuser
    margin). Measure `BTN_PROUD` first.
  - The lid ribs leave 0.5 for 0.5 foam: zero preload. Move the rib face to `CAR_Y1 + 0.1`, or use 1 mm foam; add a
    lead-in chamfer.
  - There is no 2 mm opal sheet sourced (diconfa starts at 3 mm).
- **Measure on the board:** J5/I2C plug protrusion including the wire bend (assumed 4.0; above ~5.0 the board can't
  go in).
