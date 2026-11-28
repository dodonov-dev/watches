# Pebble (track A2) CAD: status 2026-11-27 — round E built (board keeper: frame fork, 4 wide ribs)

> **Insertion in practice (user, 2026-11-27):** the board slides in along the front wall, also with the rods already on the glass. The model's path (up `insert_shift` 4–6.7 behind the seat, then forward) is **not** needed and must not limit anything behind the board (ribs may reach over the board). Round D's upper rib was kept outside the board's edge for that wrong reason; its fork snapped off the rib.


> **Rods are not glued to the glass (user, 2026-11-27):** gluing loses the sanded low-pass filter and the moire comes back. So the rods do not locate the board; the shell has to hold it along the face (it slides up) and sideways. The glass already sits in a shallow pocket in the front wall (floor t 3.39; bottom ledge 1.0 at s 17.6, side steps 1.2 at |x| 15.9; no top end for ~6.5 mm). **Built (`SEAT`, `PebbleModel.seat_mesh`, `stops.stl`, picture `pocket-stops-views.png`; sketches `concept/board-bracket/pocket-views.png`, `vstop-views.png`):** a wedge closing the pocket's top (leaves the floor 0.3 above the glass, 29.5° to the face, 2.6 deep), rails on the side steps (0.15 from the glass each side, 3.0 high), taller bottom corners (|x| 10–15.75, 2.6 high, flat top 0.33 under the glass). 787 mm³, steepest face 44.5°, no supports; glass 0.15 from them, board and buttons 0.9–1.4. **The user assembles without the 0.5 foam strips** (D's pads +0.2 were "a little loose" bare, "perfectly tight" with tape on the glass): the wedge starts for the glass on the pocket's floor (with strips it can rise 0.9 more), and the fork's pads are now printed +0.7 (`PAD_OVER`). The model itself still has `hw.GASKET` 0.5; the board without it is not modelled, and the adapter dummy is the old 90° adapter (the user now has a short bendable extension).

**Round E = round D with a new keeper** (user, 2026-11-27, after printing D; `smooth.py`'s `KEEPER`; numbers in `report.txt`'s last line; picture `keeper-views.png`, sketch `concept/board-bracket/keeper-e-views.png`). Built and checked. **To print:** `to-print/pebble-E-{shell,fork}.stl`, `pebble-E-shell-relief-{N1,W}.stl` (`keeper_to_print.py`), plate **`_18_plate_pebble_E_N1_fork.3mf`** (`SEAM_ROUND=E SEAM_ONLY=N1 seam_shell.py`: N1 with seam paint and slot supports, the fork flat with pads up; no lid, it is unchanged). Rebuilt with the pocket stops and +0.7 pads; sliced once here (Bambu Studio CLI): 8 h 42, 74 g; a seam on a painted strip in every layer; new below the slot: the outer skin's seam for z 0–2.5 sits on the back, under the slot (x −4..−2.8). The user may still extend the plate.
- **D as printed (plate `_17`):** the fork held and its pads pressed as intended (the fork bends slightly), but the one-prong fork snapped off its narrow upper rib. The pad sat 5 mm inboard of where the rib backed the prong.
- **Fork:** a frame open on the plug side. Top bar across both upper screws (s 88–95.3, wall to wall, 0.47 from the walls), the button side's prong (widened to the wall above s 80), a lower block across both lower screws (s 17.1–30, above the adapter), two feet; 4 pads.
- **Ribs:** 4, 3.5 thick, reaching over the board behind the pads: upper button side to |x| 11; upper plug side a 45° wedge (inner edge 13 at the top) that leaves the RTC socket and its plug in view; lower pair to |x| 14 at the top (45° up from just above the rim, so not over the lower pads).
- **Bearing on the ribs:** 33.7 (plug-side wedge), 94.1, 106.6, 183.2 mm²; at least 30.6 with the fork pushed sideways to a wall. Steepest rib face 43.1°.
- **Order now:** board (UART / J5 / I2C empty: the top bar passes over them; user: plugged in later), fork, adapter (the bar cannot pass it), battery plug and upward plugs through the fork's open side, lid.
- **Checks changed:** the board's back-shifted up move is no longer swept against the ribs (see the note above); instead the seated board, plugs, buttons and adapter against the ribs (4.0). The fork's way up is checked without the adapter and the three upward plugs. The skew pose is gone: the bar runs wall to wall, the bearing is taken with the fork pushed sideways. Not reviewed by Astra.
- **USB-C slot instead of the rim notch** (user, 2026-11-27: a short bendable extension's socket end sits in the opening): `PEBBLE["USB_SLOT"]` 11 wide × 5.5 high (5 in the first print of round E; user 2026-11-28: "increase the usb opening to 11 by 5.5"), round-ended, level through the back wall at x 0, lower edge 2.5 above the rim, closed all round. Tight on purpose (the user sands it). "5 by 1.1" in the user's words, read as 5 mm × 1.1 cm. The lid is unchanged (`lid.stl` = `pebble-C-lid.stl`). For the relief shells `keeper_to_print.py` fills the notch's foot from the smooth shell and cuts the slot; `seam_shell.py` moves the cavity seam strip to x 8 for round E. Run for plate `_18`: the relief shells' back wall foot round the slot equals the smooth shell's (0.05 mm³).
- **Print feedback on plate `_17` (user, 2026-11-27):** a thin horizontal ridge on the body's outer wall, on both flanks, ~11 mm below the slot tops (from a photo, ~z 76–77), not on the pillar. Nothing in the G-code at that height (the user's own slice, layers 30–87 mm: same loops, speed, flow, no pause). Cause open (filament, a stall, Z); the user watches the reprint.

---

*Round D, as printed 2026-11-26/27 (superseded by E above):*

**Round D = round C + the board keeper** (`smooth.py`'s `KEEPER`, `PebbleModel.fork` / `rib_mesh`; numbers in `report.txt`'s last line; picture `keeper-views.png`). The outer form, slots, logo and lid are unchanged.
- **Why:** the rods fix the board along x and s, but nothing held it against the front wall, and it hangs under the 15° lean.
- **Plug side (user, 2026-11-26):** UART, J5 and I2C open upwards, so their plugs and wires stand behind the plate, in the column of that side's screws. Nothing of the fork may slide up through that column. So the fork has **no prong and no upper pad on the plug side**, and the shell no upper rib there. The board is held at 3 points: both lower screws and the button side's upper one. Three points and the front wall hold a stiff board.
- **Fork** (`fork.step` seated, `fork-print.stl` flat with pads up): 2.5 thick, slides up from the open bottom right behind the board's acrylic back plate. Two feet, one prong on the button side. 3 pads 5 × 5 over the plate's screws, 1.5 proud, printed +0.2: sand them to fit. The bridge passes under the adapter; the foot is level, 0.15 above the lid.
- **Ribs** (3, on the side walls, `ribs.stl`): two lower ones behind the feet, one upper on the button side. Added on the mesh like the slots, 1.0 into the wall. Square top, 45° corbel below (43.1° printed standing, no supports).
- **Order:** board with its cables, adapter, fork, lid. The battery is off the board (Kapton to the back wall); it has no dummy any more.
- **Plugs in the model** (`PebbleModel.moving_bodies`, dummies): UART / J5 / I2C standing 4.0 behind the plate, RTC 4.0 beyond the edge. Both numbers are assumed.
- **Checks added (lean):** each rib is one piece inside the cavity, 1.0 in the wall; their steepest face; the board's insertion past the ribs (0.83: the board's edge at the upper rib, the RTC plug at the lower plug-side rib); the fork seated and on its way up against shell, board, plugs, adapter, lid; its contact areas in the ribs' front plane; its pads on the plate over the screws.
- **Reviewed by Astra (codex CLI, 2026-11-26), three passes.** Placement, mirror sides, tilt, insertion paths and printing found right. Fixed after it: the print mesh welded; the upper rib moved in to |x| 17.5 and the prong made 0.5 wider, because the one-prong fork can sway (0.84° until the bridge meets the adapter, 0.92 sideways to the wall); its bearing on the upper rib is now checked in that pose, solved against lid, adapter and wall: 15.3 mm² left, the same figure Astra measured on the meshes; the checks state what must be there on their own (plug names, the three pads, the three contact patches) and test each rib's hold in the wall along its span.
- **The 0.5 foam strips stay** (`hw.GASKET`, between the glass's short ends and the front wall): stuck to the wall only, or with the liner left on towards the glass. Without them the board sits 0.5 further forward: the pads do not reach it and the adapter meets the chin.
- **To print:** `to-print/pebble-D-{shell,fork}.stl`, and `pebble-D-shell-relief-{N1,W}.stl` = round C's relief shells + the same ribs (`keeper_to_print.py`). Lid: `pebble-C-lid.stl`, unchanged.
- **Plate `_17_plate_pebble_D_N1_fork_lid.3mf`** (`SEAM_ROUND=D SEAM_ONLY=N1 seam_shell.py`): N1 round D with the painted seam and the slot supports, the fork (flat, pads up, no supports) and the lid (flipped; round C's lid, unchanged). Route `pebble-D-seam-route-N1.csv` = the C route (the ribs touch neither the skin nor the cavity strip at x 6). Sliced once here (Bambu Studio CLI) and checked: seams as on `_16` (cavity strip in all 1249 layers, both edge routes, scarf); 8 h 25, 76 g. `_15` / `_16` stay round C (no ribs): not for D.
- **Measured (user, 2026-11-26):** glass front to the plate's back face = 9.15, now in the model (`KEEPER["BOARD_T"]`; `hw.BOARD_T` 9.0 still places the port and adapter). **Still assumed** (`docs/lcd316-mechanical.md`, "To measure"; picture `docs/lcd316-to-measure.png`): the RTC plug's reach beyond the edge (4.0; no plug at hand, the lower plug-side rib can be filed back) and the upward plugs' height (4.0).
- Concept sketches and the variants not pursued: `cad/desk/concept/board-bracket/`, `KAIZEN.md`. The sketches there still show the two-prong fork.

# Pebble (track A2) CAD: status 2026-11-24 16:56 — round C built

**Round C**: `to-print/pebble-C-{shell,lid,teststrip}.stl` plus `logo-stencils-pebble-C.stl` (the same as B's). A's openings are kept as printed, at c-c 18. Horns are left as in A; the relief is to hide them. The logo is as in B. Four checks were run and all passed; see `report.txt`. The slots are cut on the mesh, so `shell-noslots.step` has none. Relief versions F5, F9 and W are in progress. Round B's status follows, kept for history.

# Pebble (track A2) CAD: status 2026-11-24 14:25 — round B built

**Round B is built and printable:** `cad/desk/to-print/pebble-B-{shell,lid,teststrip}.stl` plus `logo-stencils-pebble-B.stl`. They are copies of `out-smooth/pebble/`, from build 13 of `smooth.py pebble`. Every lean check passed; figures are in `report.txt`. Nothing is committed.
- **Slots are cut on the mesh with manifold3d,** because OCC could not cut the B-spline slot surface. `shell-noslots.step` has **no slots**.
- **Bottom-corner change from the sketch:** beside the slot, the cut never gets deeper going down. N1's corner blend had left a 68° ceiling within 0.25 mm of each bottom corner.
- **Logo floor:** set from the front's nearest 3D point, so the skin is 1.300 at its thinnest and 1.688 at the pocket's centre. Letters 14 × 8.83; stencil 1.60 thick.
- **Clearances:** rods in the slots 0.06; adapter sweep 0.09 (A was 0.08). Overhangs: slots 44.16°, outside 44.75°.
- **Mesh:** 1 piece, 0 open or non-manifold edges. About 3.1k slivers (inscribed radius < 1e-4) come from the manifold cut.
- Round A's status follows; it is kept for history.

# Pebble (track A2) CAD: status 2026-11-21 20:35

**Front "A" is built and printable**: `cad/desk/to-print/pebble-A-{shell,lid,teststrip}.stl`. They are copies of `out-smooth/pebble/`, built by `smooth.py pebble`. Every check of `build_pebble` passed and `report.txt` is written (rerun 20:47; its STLs are byte-identical to the copies). Stencils: `to-print/logo-stencils-12mm-pebble.stl`. Nothing is committed.

**Weak spots:** the adapter's up-move passes the chin with only 0.08 of clearance (it was 1.25 at front 4.55). The seat wall is exactly at its 1.9 limit (x 16.4, s 93).

## What A is (user, 2026-11-21)
- **Flat inner face** at t 3.392, so the wall is 3.0 at the slot centres. The outer surface is unchanged (the oval's curve over the slots).
- **Seat (named exception):** the flat face spans the glass + 0.3. Over the glass's edge the wall drops to ~2.0, accepted ≥ 1.9. `PebbleModel.seat()` also covers the logo's mouth.
- **Slots:** 0.6 land, then a round lip per side (`PebbleModel.lip()`, `slot_cutter()`).
  - Each lip is an arc, vertical at the land, solved to meet the bowed face tangentially. It ends 3° short of tangency (the boolean stays transversal).
  - Inner side R 2.77, outer side R 1.39.
  - Rods sit ~0.55..0.75 proud of the face.
- **Logo pocket (`PebbleModel.pocket()`):**
  - Rounded floor 14.2 × 9.8 R2. Skin 1.0.
  - All flanks tapered: sides and bottom 45°, top 60° (printed, a 45° ceiling, no bridge).
  - The mouth runs ~3.6 under the glass's lower border (0.5 in front of the glass).
  - Stencil follows the pocket; it is printed wide face down.
- **Up-move shift: 6.8** (was 5.6 at front 4.55). The rods are now further forward, and the chin's inner rim edge did not move.
- **Ceiling:** z 100 (was 99.5). Tent 43° (44 lofted to 45.02).

## Measurement fixes made on the way
- **Volumes:** from meshes of the STEP read back. OCC's volume integration is off by up to 0.5 % on these B-spline faces.
- **STLs:** written from the STEP read back. The in-memory shell meshes with open edges or folds, and a second round trip opens edges too.
- **Sections:** `section_segments(fast=True)` samples in C++. Plane sections of the envelope sometimes come back incomplete, so `front_out_t` uses a line-surface intersection instead.

## Baseline (front 4.55, 45° bevels) for comparison
`report-baseline-front4.55.txt`

## Next
- Judge the test strip: lips, proud rods, logo.
- **Trench at the slots' top end:** the geometry has a real but shallow dent, 0.02–0.03 (see the report to the coordinator). The fix, if wanted, is to use the oval curve as the bow everywhere, so there is no second blend.
- Upright, tilt15 and oval were re-run after the shared-code changes: reports identical, STEP diffs timestamp / signed-zero only (restored). The later edits (`vol_props` precise path, `land_tol`) only run on the pebble path.


## Round B (2026-11-23): IN PROGRESS, blocked on the slot cut (no B STLs yet)
Implemented in smooth.py (pebble only; the other three variants were re-run: reports identical, STEP diffs timestamp-only):
- tubes c-c 18 (`PebbleModel.tube_cc`; `Model.tube_cc` / `logo_skin` attributes, defaults unchanged);
- slots N1 / A' / lips round the corners: `slot_params`, `slot_surface` (a port of slot_ends.surface), `slot_cutter` (a
  B-spline heightfield of it + the through-slot box per slot), `pebble_land` (the lands measured on the planar faces);
- logo: Model's pocket (sides 45, top / bottom straight), skin 1.3, letters 14 (the largest <= 14 that leaves a 1.2 stencil:
  stencil 1.62 thick), `front_logo_wz`; stencils via make_stencils(t=...);
- the dent fix: the oval's curve now fades with the sketch's bow (dents <= 0.002 over the slots; 0.015 at x 15, z 99.6);
- lean `build_pebble` (six checks; PEB_FULL_CHECKS gates the rest).
Blocker: OCC cuts the shell with the heightfield cutter wrongly (valid-looking cutter; body - cutter is invalid or leaves
the slot uncut; tried: one/two heightfields, x/index parameters, ledge 0.02/0.1, guards). A polyhedral cutter
(`polyhedral_heightfield`) cuts correctly but takes ~11 min per slot and leaves two 0.1 x 0.6 x 65.7 chips beside the
land. A mesh boolean (manifold3d) would be the robust route; installing it was refused by the permission system.
