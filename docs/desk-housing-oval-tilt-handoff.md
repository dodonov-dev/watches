# Desk housing, track A2: the tilted oval (handoff, 2026-11-20)

A new smooth shell that combines the **oval's look** with the **tilt15's readability**. Not designed yet: start
with pictures and decisions, then CAD.

Read first: `docs/desk-housing-handoff.md` (entry, tools, decisions for every track), the end of
`docs/desk-housing-plan.md` ("FDM round 1", "FDM round 2", "Round 3 CAD"): what printing taught us.
Repo rules: `CLAUDE.md` (side ideas to `KAIZEN.md`, laconically). Commit only when the user asks.

## What the user said (2026-11-20)
- The **oval** shell looks optically the nicest of the three printed shells.
- On the table the **15° front** is the easiest to read the time from.
- Combine the two. Taking a step back is fine: new concept pictures first, with **codex** or **agy's Neon model**
  (the user finds Neon consistent; other Google models are good for search and ideas, not for consistency).
- Earlier: white Basic looked "hospital-like"; PLA Matte white is the current material (a test print is running).
  Colours are still open (warm off-white + dark accent, earthy mid-tones, dark bodies; see the plan's notes).

## The two parents (built, printed, in `cad/desk/smooth.py`)
| | oval | tilt15 |
|---|---|---|
| Size (W × D × H, with the 3 mm lid) | 56 × 36 × 110 | 50 × 49.7 × 106.5 |
| Plan | superellipse \|2x/W\|^n + \|2(y−D/2)/D\|^n = 1, n 2.8, extruded straight up | rounded rectangle, rear corners R10, R5 chain |
| Front | curved outside, flat inside (4.55 on the centre line) | flat, leaning back 15°, 3 mm |
| Top | flat 44 × 24, R6 edge; 45° taper inside (ceiling bridge 14.5) | R15 roll into a 5.3 deep flat top |
| USB | hole in the back (MOGOOD adapter) | notch at the rim, right-angle extension (the MOGOOD sticks out a little) |
| Logo | 14 mm, front, under the tubes | 24 mm, left side |
| Code | `OvalModel` (overrides plan, outer body, cavity; `front_out_y`), `build_oval` | `Model` with `TILT=15` (`to_world`, `y_front`) |
| Reports | `cad/desk/out-smooth/oval/report.txt` | `cad/desk/out-smooth/tilt15/report.txt` |

Hardware fits in all three printed shells (photos `images/cable_photos/`); the oval even takes two batteries.

## Shared rules that came from printing (keep them)
- **Slots:** 8.1 wide for 8.0 rods, a straight **0.6 land** at the inner face, then 45° out to the face; straight
  ends; 66.85 long for rods cut to 66.65 (1 mm shorter than the lit area). No knife edges anywhere: a 0.4 nozzle
  drops anything thinner than ~0.4.
- **Logo:** glow-through. One rounded-rectangle pocket from inside, **1.0 skin**, left/right sides flared 45°,
  plus a flat-printed stencil (white preferred) with matching slopes. Nothing printed standing may start in mid-air.
- **Print:** standing on the rim, no supports, X1E 0.4, 0.08 High Quality (0.12 for quick tests), 4 walls, seam
  back, Arachne, **ironing on top surfaces**, textured PEI. Flat tops look patchy without ironing.
- **Known marks:** a horizontal line at the slots' top on one side (bridge layers); abrupt wall-thickness steps
  show as sink lines; thin skins in white PLA show through unlit.
- Front thicker than 3 for more rod relief: skipped for now (user). A lip over the slot sides against moiré is a
  later option.

## Open decisions (ask the user; do not let a subagent pick)
1. **How it tilts:** (a) a wedge: front leans 15°, back vertical, the oval section shrinking in depth with height
   (like tilt15); (b) the whole oval leaning back 15° on a cut foot (a leaning bottle); (c) something else from
   the pictures.
2. **Plan and size:** keep the oval's 56 × 36 superellipse (its depth must still hold the board stack + battery
   when leaning), or widen/deepen.
3. **Top:** the oval's flat top with R6, or a roll like tilt15.
4. **Logo place and size**, **USB route** (hole vs notch), tipping stability (tilt15 report has the method).

## Suggested order
1. **Pictures:** 2-4 concepts (codex: `cad/desk/concept/codex-render.sh <out.png> <prompt.txt> <image>…`, examples
   in `cad/desk/concept/prompts/`; give the photos of the printed oval and tilt15 as the look; agy Neon for its own
   variants, one image per concept: check `agy --help` for the model id, call form in `docs/desk-housing-handoff.md`).
   Judge true proportions first; codex draws rounded tube ends and garbles digits.
2. **Clay / massing** at true proportions (`cad/desk/concept/clay.py`, `massing.py`, or a small study script) for
   the chosen variant; the user decides.
3. **CAD** as a new variant in `smooth.py` (reuse `OvalModel` + the tilt frame and every existing check: insertion
   sweeps, wall measure, slot land, pocket/stencil checks), outputs `cad/desk/out-smooth/<name>/`, copies to
   `cad/desk/to-print/`. Do not edit `housing.py` or `rolypoly.py`.
4. **Review:** Astra through the Codex CLI, critical issues only, reproducing numbers from the exported files:
   `~/_PROJECTS/pigeon_drop/tools/codex-run.sh <run-dir> -m gpt-6.2-astra -e high -C <repo> -- "<brief>"`.
   Last round it found four checks too weak to catch their own faults: ask it to try fault injection.
5. **Print** in Bambu Studio (the user's projects are in `cad/desk/to-print/*.3mf`); a quick 0.12 test first.

## Concept round 1 (2026-11-20)
Pictures in `images/desk-housing-v3/` (`sheet-codex.jpg`; `agy/` Neon; `fable/` true-scale SVG sheets + `fable-concepts.md`;
`profiles-true-scale.png` from `cad/desk/concept/oval_tilt_profiles.py`). Prompts: `cad/desk/concept/prompts/oval-tilt-*.txt`
(`codex-render.sh` now takes `CODEX_MODEL=gpt-6.1-sol|gpt-6.2-astra`).
- **User's pick: the leaning pebble** (`4-pebble-astra.png`). At true size (Fable, `fable/pebble-true.*`, renders
  `5-pebble-true-{astra,sol}.png`): 60 W × 58 D × 110 H, egg outline widest at z 30, front straight 15° over the slots,
  back one convex curve, underside R7.5 to a 43 × 42 foot (first 45° in the lid), dome with a 45° tent inside; est. tips
  21° back / 25° fwd; logo 12 on the chin (14 does not fit), USB rim notch at the back.
- **User: the front stays bowed across the width like the oval** (curved outside, flat inside; 4.55 / 3.0 at the glass
  edge). Along the length at most ~0.5 crown over the slots (Fable), else the openings barrel and the rods sink.
- Ruled out by numbers: leaning bottle (tips ~6-9° back), sliced oval (flat face, D top). Alternatives kept: Fable's
  "leaning stones" (oval slab propped by a small stone, 24° back) and "soft cairn" (#13 at true size, 64 wide).
- Generic: board + battery are ~85 of ~150 g, so CoM sits ~30 behind the face's toe, ~49 up in every shell: the foot
  must reach ~51 behind the toe to tip as late as tilt15.
- **Decisions (user, 2026-11-20):** the astra "calm stone" form (Fable's `pebble-true` as drawn, not the sol teardrop);
  logo on the front chin, 12 mm; front straight along the lean over the slots (no crown), curving away only above and
  below them. Next: 3D clay massing at true geometry, then CAD as a new `smooth.py` variant.
- **Clay at true geometry** (`cad/desk/concept/ovaltilt-sketch/clay_pebble.py`, Fable's section loft as a mesh; views
  `images/desk-housing-v3/clay-pebble-{hero,ortho}.png`): Fable's model switched the bow on/off at the face's ends and
  below a half-width 17.5, leaving creases at z ~12 and ~98; now faded (`BOW_FADE`, smoothstep). A: Fable's outline
  (`PEB_P` 2.9, `PEB_N` 2.8): battery 5.0, board 3.7, plugs 2.5, roof 1.6 beyond a 3 wall. B "more egg" (2.5 / 2.5):
  3.5 / 1.9 / 2.1 / roof 0.2 (tight at the top). Both 60 × 58 × 110, ~152 g, tip ~21.5° back / 25° fwd.
- **User: "closer to A + wider + wider at the base".** New knobs `PEB_BW` / `PEB_BZ` (belly half-width / height).
  C: 64 wide, belly z 22 (P 2.9) — battery 5.5, board 4.6, plugs 4.3, roof 1.75; D: 66 wide, belly z 18, P 2.7 —
  5.4 / 4.2 / 5.3 / 1.6. Both ~155 g, tip ~21.3° back (depth unchanged: widening helps sideways only), foot 47-49 × 42.
  Sheets `images/desk-housing-v3/clay-pebble-wide-{hero,ortho}.png`.
- **User picked D (2026-11-20):** `PEB_P 2.7, PEB_N 2.8, PEB_BW 33, PEB_BZ 18` → 66 W × 58 D × 110 H. Next: CAD.
- **CAD started (2026-11-20), paused for a reboot:** a `pebble` variant in `cad/desk/smooth.py` (PebbleModel, outputs
  `cad/desk/out-smooth/pebble/`). Resume from `cad/desk/out-smooth/pebble/WIP.md`. After the CAD: Astra review
  (user: yes), critical issues only, with fault injection. Uncommitted: everything since 4d9e16e (`git status`).
- **WIP print (user, 2026-11-21; unchecked preview STLs, PLA Matte, 0.08 HQ):** "extremely nice", reads as cast /
  alabaster / ceramic, not plastic. Notes: (1) a **trench** (recessed line) across the face at the slots' top, worst
  right of the right slot: avoid it; where a seam is unavoidable make it a **proud scar** (sandable), never a groove;
  (2) **front too thick**: the rods protrude less than wanted; (3) the **45° bevels and the bridge "nose"** between the
  slots look too geometric on the pebble.
  - (1) is probably the slicer, not the geometry: the roly-poly session found the same line on the layer where the
    openings' tops close (outer wall slowed to 10 mm/s "overhang wall" there vs 60 elsewhere; PLA Basic profile with
    Matte loaded), test plate `watches-rolypoly/cad/desk/to-print/_6_closure_ring_test.3mf` printing (2026-11-21; replaces the first closure-ring STL, which tested the wrong thing).
  - (2) user: wall 3.0 at the slot centres (inner face forward, outer bow kept; rods ~0.6 proud). (3) user: soft
    edges, picture first (`images/desk-housing-v3/slot-edges-*.png`), then CAD.
- **User picked A (2026-11-21):** wall 3.0 at the slot centres (inner face forward to 3.39 on the centre line, outer bow
  kept; 2.05 over the glass edge by design), 0.6 land, then a round lip (radius = depth left, per side) vertical at the
  land and tangent to the face; no 45° bevels, no nose (bridge flat 7.1 with round shoulders); rods 0.65 proud.
  Pictures `images/desk-housing-v3/slot-edges-{section,clay}.png`, script `concept/ovaltilt-sketch/slot_edges.py`.
- **Logo rectangle still faintly visible from outside** on the WIP print (photo in chat 2026-11-21): soften it.

**A print feedback (2026-11-23)** (`to-print/pebble-A-*.stl`): turned out well. (1) Slot top ends print ragged: they are perpendicular to the face = ~75° ceilings when printed standing; fix: lean the top end so it is ≤45° (outer opening ~1.7–2 above the inner). (2) Tiny "horns" at the openings' outer top corners, where the round lips meet the straight ends (visible in the CAD render too; not in the WIP); fix: lips wrap round the corners. (3) Logo rectangle still visible; user: drop the stencil (it shrinks the logo), thicker skin is fine, subtle glow wanted. Proposal: letter-shaped pocket from inside, 45° flanks, no stencil. (4) The WIP's rough "worked stone / wood" look (less clinical) was the preview's coarse tessellation (31.8k vs 229k triangles); user wants some relief/stone pattern back (plus harsh sanding). (5) Without the WIP's 45° nose the tubes read too far apart (bridge flat 7.04 vs 4.47). (6) FYI: openings slightly longer, rods held less by friction; not an issue (rods get cut to length). Pictures for 1/2/4/5 in progress: `images/desk-housing-v3/slot-ends-nose-*.png`, `relief-*.png`.
- User answers (2026-11-23): keep the stencil concept (complex logos, easy swap); the logo shrank because the pocket's top/bottom were tapered: straighten them, skin 1.3, logo as large as fits. Slots: rounded nose (N1) at tube c-c 18 (firmware moves its columns, one parameter), lips round the corners (no horns), A' sloped ends (support-free; tree supports from inside the open shell also work). Relief: open (pictures `relief-{hero,ortho}.png`; recommendation: the WIP's facet look reproduced on purpose, as a mesh pass). CAD round B started.

## Round B in Bambu, and round C (2026-11-24)
- **Round B built:** `to-print/pebble-B-*`; the slots were cut on the mesh with manifold3d. In Bambu the user saw three problems:
  - The openings were not symmetric: a wide crown on the inner side, a narrow lip on the outer side.
  - The top ends were not flat.
  - A line ran down the nose, and some horns were partly back.
- **The ends must be flat.** They have to be full-depth walls square to the tubes, because the tubes butt against them. The A' sloped ends were a misread: the user had asked for supports. The top end prints as a ~75° ceiling with tree supports from inside.
- **User answers:**
  - flat full-depth ends with a ~0.5 face round; the side lips fade into it near the ends, with no horns;
  - symmetric lips, 2.5 each side; tubes c-c 18 (bridge on the face ~4.9);
  - variant sections and clay renders first, before any modelling.
- **User, later on 2026-11-24:** all C variants (symmetric 2.5 lips with fading ends) were rejected.
  - **Round C now:** round A's openings exactly as printed (round lips, flat square ends, tree supports at the top ends).
  - **Changes from A:** tubes at c-c 18; horns fixed locally at the corners; B's logo kept.
  - **Next:** after the user's review, two relief versions of C get built for printing.
- **Horns:** no geometric fix. The relief runs up to the openings and is expected to hide them, as on the WIP.
- **Reliefs on the C shell:** F5, F9 and W. W is close to the WIP's coarse-tessellation look, but with clean openings and facets that follow the form.
- **Checks cut to four:** manifold mesh, overhangs outside the supported top end walls, seated rod and adapter clearances, logo skin.
- **Print of plate _10 (2026-11-25): W and N1 "knapped" (Fable's natural relief) plus E+H stencils, all came out very nice.**
  - **Supports:** the inner-tree trick works: tree(manual) from the build plate only, enforcers over the slot top end walls, 10° branch angle so the trees can't escape out of the front opening, xy distance 0.7.
  - **Lid:** printed unflipped and came out badly, worst at the holes. It must print inner face down. `make_plate.py` now flips lids; `_11` is the lid reprint.
  - **F5/F9 (triangle facets):** rejected as too geometric.
  - **N2/N3:** not printed; the STLs are left uncommitted and can be regenerated with `relief_natural.py`.

## Layer seam at the back (2026-11-25/26)
- **The scar** on plate _10's shells is the layer seam (seam = back, no scarf): a near-straight line that ignores the relief.
- **Where it can hide** (measured on N1, sliced with OrcaSlicer 2.5.0 and Bambu Studio 2.9.1's own CLI):
  - z 23.6–87.7 (slot zone) and below z 6.3 (cable notch): outer skin and cavity are one contour, so the seam can sit on the cavity wall. Both slicers already put part of it there.
  - z 6.3–23.6 (foot) and z 87.7–107 (dome) are closed rings: the seam has to be outside. Plan: on the relief's arrises.
- **Painted seam** (Bambu's seam enforcer, `paint_seam="4"` per triangle, 0.8 mm strip) + seam = aligned: the seam follows a route to ~0.15 mm (0.5 on the flat roof above z 104). With seam = back it jitters across the strip. Aligned without paint goes to the slot openings on the front: do not use.
- **Edges as they are:** N1 arrises are 5–15° corners within a layer, W's facet edges 3–6° (too faint). A z-monotone route needs edges never flatter than ~30° to the horizontal; N1 gives 70–90 % cover, the rest crosses flake floors. Purpose-built arris chains in the two bands are not modelled yet (they wait for the coupon).
- **Coupon, plate `_13_plate_seam_coupon.3mf`** (`cad/desk/seam_coupon.py`, paint via `make_plate.py`'s optional route): N1's dome cap (z ≥ 88.5) twice, same painted route, ids = notches in the front rim: 1 plain seam on the edges, 2 + scarf joint. Per-object settings confirmed in Bambu Studio's G-code (`seam_coupon.py check`). 1 h 42, 15 g. Printed at the shell's own 0.08 profile: seam and scarf look depend on layer height. Held back in the script (low expected effect, next to try if both disappoint): 3 outer-first walls, 4 outer wall 30 mm/s.
  - If 2 is clean, no purpose-built edges are needed. Otherwise the seam stays on edges, and they get sharpened (≥ 15°).
  - **Printed (2026-11-26), user:** both came out nicely; in 2 the scar protrudes slightly less, not a critical difference. So: painted seam on the existing edges, scarf on (external), no purpose-built edges, 3 and 4 not needed.
- **Shell plate with the seam hidden, `_15_plate_pebble_W_N1_seam.3mf`** (`cad/desk/seam_shell.py`; plate _10's two shells, same supports; user prints N1 only, W is changed too). Seam = aligned + scarf (external) + painted strips, routes in `to-print/pebble-C-seam-route-{W,N1}.csv`, picture `images/desk-housing-v3/seam-shell-routes.png`:
  - **Cavity strip** up the cavity's back wall at x = 6 (clear of the cable notch), z 0–99.8. It is the main body's only seam below z 6.3 and in the slot zone, and the cavity loop's seam in the two bands.
  - **Edge routes** on the back skin where it is a loop of its own: foot z 5.8–23.7, dome z 87.4–top. On an edge > 5°: N1 62 % (foot) / 73 % (dome), W 14 % / 39 % (W's edges are faint; user expects W worse, still better than a straight scar). N1's foot route has one diagonal crossing of a flake floor (z 14–19.5, x −9 → −1).
  - **Front pillar** (own loop, z 23.8–87.4): not painted, its inner face is two 64 mm triangles. Aligned puts its seam up the inner (cavity side) left corner, x = −4.74, no scarf; plate _10 had it on the inner right corner.
  - **Sliced with Bambu Studio 2.9.1's CLI** (`seam_shell.py check`), both shells: the cavity strip holds a seam in all 1249 layers; the edge routes hold the outer skin's seam in every layer of the two bands (z 6.0–23.4, 87.8–top), all with a scarf ramp. Distance to the route within the layer: median 0.2 mm, 90 % under 0.5, up to 1.0 where the route leans. Where a loop touches both strips (a few layers at z 5.4–5.9, 23.6–24.2, 86.9–87.5) this slicer took the cavity strip; another version may take the edge route there, which only lengthens the route by those layers. Left on the visible skin, none of it on the back: loop starts at the slots' bottom ends (z 23.5–23.8, 9 in 4 layers; identical in plate _10's slice), a few tiny loops at z 16.5 (front) and at the slots' top ends (z 87.6), and the last ~0.8 mm of the apex. 13 h 9 for both shells, 127 g. Not printed yet. The user re-slices on another machine: paint and settings are per object in the 3mf, the result there is not checked.
  - **N1 alone, sliced here:** `_16_plate_pebble_N1_seam.3mf` (`SEAM_ONLY=N1`, shell in the middle of the bed) and its slice `_16_plate_pebble_N1_seam.gcode.3mf` (Bambu Studio 2.9.1 CLI: X1E 0.4, Bambu PLA Basic 220 °C, Textured PEI 55 °C; 7 h 23, 64 g), made so the user can carry the slice to the machine that talks to the printer. Seams identical to the two-shell slice. The CLI's file has no thumbnails and an empty printer id: opening / sending it there is not tested.
  - **Reviewed by Astra (codex CLI, 2026-11-26):** no fault found in the paint or the settings; four weaknesses in `check` (frame fitted on the seams it verifies, loops starting as an overhang wall, 3-d instead of in-layer distance, slot lips counted as inside) are fixed, the numbers above are from the fixed check.
- **The shell STLs are unchanged:** the seam is hidden by paint and seam settings in the plate files only. The routes follow the exact surface (STL coordinates), so after regenerating a shell STL (e.g. a relief change) the old route CSVs and plates are stale: rerun `cad/desk/seam_shell.py`, slice again and run its `check`.

## Board keeper, pebble round D (2026-11-26)
- **Problem:** the pebble's board was only located by the rods (x, s); along the depth it had to be taped. Tape is not wanted (a strong one breaks the display on removal).
- **Chosen (user):** a printed fork behind the board's acrylic back plate plus ribs on the shell's side walls. UART, J5 and I2C open upwards, so the plug side has no prong, upper pad or upper rib: 3 pads, 3 ribs. Details and numbers: `cad/desk/out-smooth/pebble/WIP.md` (top) and `report.txt` (last line).
- **Variants looked at and dropped** (sketches in `cad/desk/concept/board-bracket/`, one line each in `KAIZEN.md`): magnet bracket on the M2 screws, wedge sled on the back wall, strap + battery tray, strap + battery on foam.
- **Built:** `smooth.py pebble` adds the ribs on the mesh and exports the fork; `keeper_to_print.py` puts the same ribs on round C's relief shells. Files `to-print/pebble-D-*`.
- **Assembly:** board with its cables, adapter, fork, lid. The 0.5 foam strips at the glass's short ends stay, but must not stick to the glass (wall side only, or liner left on).
- **Open:** the remaining board measurements in `docs/lcd316-mechanical.md` ("To measure"; the total thickness is done: 9.15); round E of the keeper (2026-11-27: frame fork open on the plug side, 4 ribs reaching over the board; `out-smooth/pebble/WIP.md`) is built, with a closed USB-C slot (11 × 5) in the back wall instead of the rim notch; print plate `_18_plate_pebble_E_N1_fork.3mf`; round D's print plate is `_17_plate_pebble_D_N1_fork_lid.3mf` (N1 with seam paint, fork, lid; `SEAM_ROUND=D SEAM_ONLY=N1 seam_shell.py`); `_15` / `_16` are round C, not printed. No D plate for W.

## Simplified Schleiferbock stencils (2026-11-26)
- **User:** the plate _12 stencils are good but too detailed for a glow-through logo. Wanted: goat's head only, bigger wheel / gear, bigger sparks.
- **Logo:** `images/schleiferbock-logo/simple.py` draws it in mm at stencil size (14 × 8.83 box) and writes `schleiferbock-simple-{wheel,gear}.svg` + `simple-preview.png`. No arm, no knife. Wheel Ø 6.2 (was 4.1), gear 8 teeth 0.9 high, sparks 1.05 wide × ~2 long (were 0.4 × 1.5). Nothing narrower than 0.5 (0.4 nozzle), ≥ 0.8 of plate between the five cuts.
- **Stencils:** `cad/desk/schleiferbock_simple_stencils.py` (same plate and the two types, through / sparks, as `schleiferbock_stencils.py`), STLs `to-print/logo-stencil-schleiferbock-simple-*`, plate `_14_plate_schleiferbock_simple_stencils.3mf`. Not printed yet.
