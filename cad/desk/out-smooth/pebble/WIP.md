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
