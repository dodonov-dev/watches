# Desk housing: frozen spec v1 (2026-11-13)

A desk version of the Liquid Watch on the Waveshare ESP32-S3-LCD-3.16, standing upright, USB-C end down. Two clear
8 × 4 acrylic half-rods on the glass act as lenses over the two drawn tubes. The E+H letters are cut through one side
and lit from inside. Printed prototype first (MJF PA12), wood later, so the print follows the wood's rules.
Board data: `docs/lcd316-mechanical.md`. Parts: `docs/desk-housing-parts.md`. Mood: `images/2tubeswood.png`.
History: the pre-review plan was reviewed by Fable and Astra (2026-11-13). This spec includes their findings and the
user's decisions.

CAD: build123d, `~/.venvs/cad`. Files in `cad/desk/`:
- `housing.py`: v0 draft, parametric, with asserts; to be evolved into v1.
- `trace_logo.py` → `eh_logo.json`: letters from `eh-logo.svg`.
- `render.py`: previews with feature edges, coloured section.
- `out/`: STEP + STL per part.

Axes: X right (seen from the front), Y front → back (front face y = 0), Z up (shell rim z = 0).

## Body
- **Shell: one piece, open at the bottom.** Every visible face is seamless; the only seam is the bottom edge.
- **Outer size:** 50 × ~101 (shell) × 34 mm, plus a 3 mm lid below → total ≈ 50 × 104 × 34. All values are
  parameters; the height is derived from the stack.
- **Edges:** vertical edges R4 (keeps 26 mm of flat side for the logo), top edges R3, bottom edge 0.5 break.
- **Walls:** sides 3, back 3, top 7 (wood end grain).
  - **Front 3 mm with a 45° bevel round each slot down to a 1.5 mm rim** at the slot edge. That is the wood geometry,
    printed now so the look is judged on the print.
  - The front thickness and the bevel are parameters, so a flat 1.5 mm front variant is one switch.
- **Cavity:** a plain pocket from the bottom, inner corners R6 (a 12 mm router bit in wood). **No internal features
  in the shell.** Everything else is cut from outside or glued in as a separate part.
- **No vents in v0** (parameter off). The test: 2 h charging with the display on, battery ≤ 40 °C.

## Front slots and rods
- **Slots: 8.6 × 69.45** (rod 68.65 = lit length + 1, plus 0.8). **Square corners** for the print (R parameter, 0.5
  for wood).
- **Placement:** centred on the firmware's drawn tubes: X ±10.23 about the lit area's centre, Z on the lit area's
  centre. The lit area (AA) centre is PCB bottom + 7.5 + 67.65/2 (measured; the AA sits ~2 mm off the PCB centre
  towards the far end).
- Firmware layout: 2-tube 8 mm build, `tubeHeight` 54 → drawn tubes 5.94 mm, flush with the AA long edges, 20.46 c-c.
- **Rods:** stuck to the glass with OCA tape (~0.05–0.25 mm), **possibly before insertion**.

## Board, carrier, assembly
- The glass rests against the front wall's inner face; the gasket thickness is a parameter, 0 for now. The board is
  centred in X. The PCB bottom sits 13 mm above the lid plug (the chin).
- **Carrier** (printed):
  - a plate behind the board, screwed to the board's 4 M2 nuts (27.35 × 72.75, 3.0 in from the PCB edges), with
    countersunk heads on the battery side;
  - legs down to the lid;
  - battery rails for a 47.7 × 29.5 × 9.9 cell between the nut rows.
  - **Nothing on the carrier near the side walls.**
- **Insertion: up, then forward.** With the rods glued on, the board + carrier enters about 4.5 mm further back
  (rod 4 + tape + clearance), goes up, then moves forward into the slots. **Check this swept path in the CAD**
  (cavity depth and corner arcs against the carrier, battery, breakout and anything glued in).
- **Lid** (printed):
  - a full-outline plate under the rim (3 mm), with a 2 mm locating plug (0.3 clearance);
  - **magnets Ø2 × 1** (supermagnete S-02-01-N; holes Ø2.1 × 1.2) in the 4 rim corners and matching holes in the lid;
  - **ribs** that fill the gap behind the carrier after the forward move and press it forward (0.5 foam on their faces);
  - a **cradle for the USB-C breakout** (Pololu 2585: 20.3 × 14, connector ~1.3 beyond the board edge, socket mouth
    flush against the back wall's inner face).
- **USB:** through the board's J5 (MX1.25 4-pin: VBUS, D−, D+, GND, parallel to the Type-C) to the breakout.
  - Back-wall hole 13.5 × 7.5, R3, centred on the socket.
  - BOOT/RST and the board's power slide are **not** exposed; the slide stays ON.

## Logo
- **The E+H letters only** (`eh-logo.svg`, paths path25269 + path25271, via `trace_logo.py`). They are cut through the
  **left** side wall (−X, the board's button side, which has free room inside), horizontal and readable from
  outside. The vertical centre is ~4 mm above the tubes' mid-height.
- **Target: letters 25 mm wide** (about 15 high), so the wall strips between the cuts are ~1.5 mm.
  - At 25 the letters nearly fill the 26 mm flat side.
  - Inside, the cavity's R6 corners leave only ~16 mm of flat wall, so a flat diffuser behind 25 mm letters does not
    fit as is.
  - Report the options with numbers and do not silently shrink. Options: deeper box, smaller letters, a light box
    that sits further in or follows the corners, a flexible opal film.
- **Light:** a separate small printed light box with a 2 mm opal acrylic window (letters + ~2 mm all round) and a
  pocket for 2–3 warm-white 0603 LEDs, **glued into the shell** behind the cut-out before assembly.
  - It must clear the board's buttons (PCB edge x = −16.675, buttons ~1 mm proud) and the carrier's insertion path.
- **Minimum strip width:** report it (target ≥ 1.2 print, ≥ 2 wood).

## Extra part
- **Test strip:** a plate as thick as the front (same bevel), with slots 8.3 / 8.5 / 8.7 / 9.0 × 69.45 at full
  length. One adjacent pair is at the real 20.46 c-c, so the bridge is tested too. It is ordered with the shell.

## Print order (v0 → v1)
- Shell: black MJF PA12.
- Carrier, lid, light box, test strip: any MJF.
- Exports: STEP + STL per part, plus renders and a section in `cad/desk/out/`.

## v1 build notes (2026-11-14)
- Built by `cad/desk/housing.py`; the full numbers are in `cad/desk/out/report.txt`.
- **Prototype mode (`PROTOTYPE = True`, user decision):** print only **shell, lid (a flat 3 mm plate with 4 magnet holes: no lip, no ribs, no USB cradle), test strip**. The inner parts wait for the USB and battery choice.
  - The board's glass is taped to the inside of the front wall with ~0.5 mm foam tape (`GASKET`).
    - Tape lands: 5.5 mm at the USB end.
    - **Only 1.67 mm at the far end**, between the slot's end and the glass edge. Cut that strip ≤ 1.5 mm wide, or it
      shows in the slot.
  - The battery is taped to the board's back over Kapton. Diffuser film is glued behind the logo, with the LEDs
    hot-glued behind it.
  - The carrier, light box and lid ribs stay in the code for later (`PROTOTYPE = False`). Before using them, fix:
    - the light box's RST clearance → 0.6;
    - the rib preload (rib face at `CAR_Y1 + 0.1`, or 1 mm foam).
- **Front:** a 45° chamfer from the 3 mm face to the glass (`SLOT_RIM` 0, user's choice B). Slot 8.6 × 69.45 at the
  glass, 14.6 × 75.45 on the face. Flat face between the slots 5.86.
  - Rods: ~0.55–0.75 proud of the face with 0.5 tape, ~3.6 proud of the slot edge.
- **Logo:** R_IN 3, R_OUT 4. Letters 24.0 × 15.1, thinnest strip 1.23 (print OK, wood needs ~2).
- **Magnets:** Ø2 × 1 in Ø2.1 × 1.2 holes, placed against the 0.5 bottom chamfer, 0.61 wall. Glue them in;
  polarity by stacking.
- **Test strip:** 86.0 × 85.5 × 3, slots 8.3 / 8.5 / 8.7 / 9.0, all at 20.46 pitch.
- **Reviews of the CAD (Astra full; Sol, Opus, Fable critical-only):** nothing critical for shell, lid or test strip. The shell fixes the space under the PCB at 15 mm (flat lid), the USB hole at z 8 and the cavity depth at 28 mm (battery ≤ 13 thick without a carrier). Tape the board with small patches or removable tape so it can come out again.
  Fixed: the magnet chamfer and the nut pitch 72.75.
- **USB for the prototype (user, 2026-11-14):** a 90° USB-C adapter (bending over the flat side) in the board's own
  port; optionally a short C male → female extension. A normal cable plugs in through the back hole, now
  **15 × 8.5 stadium** (a whole plug with its overmould passes) at z ≈ 8.
  - Only ~23 mm from the port axis to the back face: a long extension sticks out of the back.
  - Hot-glue the adapter/extension to the shell, so plugging in doesn't load the board's port.
- **Adapter chosen: MOGOOD 90° USB-C** (listing: plug 8, body 7 × 12 × 21). PCB bottom now 12.5 above the rim
  (`PCB_Z0_PROTO`): the adapter body hangs 1.5–8.5 below the PCB, 4 mm above the lid. Shell 98.85 + lid 3 = **101.85
  tall**. Back hole 15 × 8.5 centred 7.5 above the rim. The adapter's socket face sits ~4.5 inside the back wall, so
  no extension. Assumed: the port face is flush with the PCB edge, and the port axis is ~2 mm in front of the back of
  the board stack. Check on the board.
- **Battery picked (user): 3000 mAh, 10 × 35 × 68, MX1.25 plug.** Taped upright behind the board, centred on its
  height (z 17.9..85.9). It clears the adapter below it. Even attached before the up-then-forward insertion, it leaves
  3.9 to the back wall (8.4 seated). Checked in the model.
