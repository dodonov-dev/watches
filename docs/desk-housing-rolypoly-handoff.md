# Desk housing, track B: the roly-poly (handoff, 2026-11-15)

A soft, drop-shaped body (the "soft cairn") that rocks from side to side when pushed and settles with the tubes
plumb. No stand and no mechanism: a rounded, weighted underside. The liquid on the display reacts to the rocking.
Order of work: the decisions are settled and the clay views accepted; **the CAD for a cheap FDM print is built
(round 2, see "CAD state"); then the user's print test, then the final white body by SLA.**

## Start here (next session, 2026-11-20): battery position
The CAD below (round 5) is built but **not printed yet**. Before printing, the user wants to reconsider the battery:
lower, or lying flat, or a smaller cell (the 3000 mAh 10 × 35 × 68 is not a requirement). See "Open idea" at the end.
1. **Weigh** the real board and battery (the model assumes 30 g / 55 g; the rocking is most sensitive to them).
2. **Compare** battery positions and sizes with the mass model `cad/desk/concept/rolypoly.py` (centre of mass under
   the rocking centre, period, fore-aft tip limits, steel still needed). Numbers first, then the user picks.
3. Only then **rework the CAD** (`cad/desk/rolypoly.py`): bulkhead, insertion from below, breakout, LED room.
4. **Carry over from the smooth shells' print rounds** (end of `docs/desk-housing-plan.md`):
   - The door's slots: 8.1 with a 0.6 straight land at the inner face (the knife-edge E came out 0.8 wider on the
     X1E; `rolypoly.py` still takes `housing.SLOT_W` 8.6 and `flat_end_cutter`).
   - The glow-through logo: the per-letter pockets (0.8 skin, 45° roofs) are untested; on the shells, abrupt skin
     steps left sink lines and thin white PLA showed through unlit (1.0 skin + flared sides + stencil was the fix
     there). Print `cad/desk/to-print/rolypoly-logo-coupon.stl` in PLA Matte white before deciding.
   - Printing: Bambu X1E with Bambu Studio (the user's `.3mf` projects in `cad/desk/to-print/`), ironing on top
     surfaces, PLA Matte white (candidate for a pearl-like roly-poly). Ballast glue: 5-minute epoxy (2 × 50 ml);
     with it, glue first, then drop the balls in, in three small batches (not the build sheet's pour-over).
   - Review: Astra 6.2 via the Codex CLI (`-m gpt-6.2-astra -e high`), critical issues only, with fault injection
     on the checks.

Read first: `docs/desk-housing-handoff.md` (entry, decisions for every track, tools), `docs/lcd316-mechanical.md`
(board). Pictures: `images/desk-housing-v2/sheet-5.jpg` (18 at rest, 19 mid-rock, 20 plain FDM), `13-cairn-soft.jpg`
(the look), `clay-rolypoly-13-*.png` (the chosen outline) and `clay-stable-*.png` (the stable variant), both at true
proportions. Older: `clay-rolypoly-*.png` (symmetric), `clay-rolypoly-asym-*.png` (shoulders only).

## What the user said
- Loves the look of picture 13 (soft, "Dalí-ish, liquid-ish", round a flat screen). Rejected the layered cairn (12)
  and the yoke's stand (11), but likes that a clock can **move, because the liquid responds to the accelerometer**.
- "Make it a roly-poly toy (at least partly), with the tubes upright when it's balanced, because our liquid's upper
  part moves."
- **Asymmetric outline, symmetric in mass:** one side's curve narrows later than the other, as in the sketches.
- It must be **DIY**, without complex mechanical work.
- Material: not porcelain. "Better in resin", maybe a resin skin over a print, "maybe even vinyl, like Youtooz
  toys". Plan: **work out the sizes on FDM first, then order SLA** from another provider.
- Ballast and trim were "mysterious": explained as stick-on steel weights (below).
- On the squarer keel ("basically like a boat", stiff fore-aft, rolling sideways): "I guess it's good because it
  gets the point to the user who touches it, showing that it's meant to play with left and right" (2026-11-15).
- Firmware changes are easy and not ruled out; they are only kept out of the housing sessions (2026-11-15). A fizz
  pass comes later.

## The design so far
From the study `cad/desk/concept/rolypoly.py` (a numeric mass model on an analytic surface, not CAD).

- **Body:** about 86 wide × 50 deep × 128 tall. Plan sections are soft squares (superellipse, exponent 2.6).
- **Underside:** in the front view a circular arc of radius 44, the rocking radius. Fore-aft it is nearly flat. So
  it **rocks sideways only**, the direction that slants the liquid surface, and stands firm fore-aft.
- **Panel:** flat, dark, 40 × 79, vertical, set back in a soft-edged alcove (6.4 mm at its centre). It carries the
  two flat-end slots; the tubes are plumb when the body is at rest.
- **Inside:** the board behind the panel (PCB bottom at z 26 above the bottom pole), the battery on its long edge
  behind the board (from z 23), ballast in the bowl below (up to z 22, 37.5 cm³).
- **Logo:** about 14 mm, glowing through a thinned wall. With the panel centred there is no room beside the alcove
  (the study's default puts it on the left flank); the chosen outline frees the front of the belly on the right.
- **Opening:** the panel is a door held by magnets; the bottom is a separate cup (see "Decisions").

Run it: `~/.venvs/cad/bin/python cad/desk/concept/rolypoly.py [KEY=value …]` → `out-rolypoly/report.txt`, `body.stl`,
`clay-hero.png`, `clay-ortho.png`. Parameters are at the top of the file. `OUT=<tag>` writes to `out-rolypoly-<tag>/`.
- Chosen outline: `XOFF=-5 Z2L=90 A2L=28.5 Z2R=102 A2R=34 LOGO_X=28` (`OUT=13`).
- Stable variant: the same plus `CUT=12 BALLAST_TOP=18` (`OUT=stable12`).

## Numbers (study)
The study's numbers; the real geometry's are under "CAD state".
Masses of the board (30 g) and the battery (55 g) are **assumed**; weigh them. Shell: PLA, 2.4 mm wall, 68 g.

| Ballast (`BALLAST_TOP`) | Total | Centre of mass under the rocking centre | Period | Lean per 0.5 mm of imbalance | Falls forward beyond |
|---|---|---|---|---|---|
| 67 g (12) | 242 g | 4.3 mm | 1.65 s | 6.6° | 19° |
| 112 g (16) | 287 g | 8.3 mm | 1.10 s | 3.4° | 23° |
| 191 g (22, default) | 366 g | 11.4 mm | 0.87 s | 2.5° | 27° |

- Sideways it rights itself from any tilt (the widest point of the body is above the centre of mass).
- Fore-aft it rests upright on its flat-ish keel; pushed over beyond the limit it falls on its face or back and
  stays there. The backward limit is 3–4° higher than the forward one.
- A lighter shell helps: SLS or SLA at 2.0 mm and 1.0 g/cm³ gives 13.5 mm and 0.75 s with the default ballast.
- Heavier parts barely matter: board 40 g and battery 60 g give 10.5 mm and 0.92 s.
- **Asymmetry** (`Z2L=90 A2L=28.5 Z2R=104 A2R=35`: the left shoulder narrows early, the right stays wide): the
  shell's centre of mass moves 2.4 mm, the clock would lean 2.3° with centred ballast, and hangs plumb with the
  ballast's centre 0.9 mm off-centre. Righting and period are unchanged. Only the rocking arc, the bottom ~23 mm,
  must stay symmetric. A stronger pinch (`A2L=26` at `Z2L=84`) pushes the panel 11 mm deep: too much.
- **Liquid:** the sim's `vertical` mode keeps the surface level against a tilted tube up to 45°
  (`ANGLE_VERTICAL_MAX_DEG` in `sim/src/physics.ts`); `angleK` / `angleDamp` set how fast it follows. Not tested
  with rocking. While swinging, the sensor should read about 75–90 % of the true lean (my estimate).

## Ballast and trim
- **Stick-on steel balancing weights** (tyre shops, RC model shops): a strip is 12 × 5 g = 60 g, 139.9 × 19 × 3.8 mm
  (Wegmann type 37), so a segment is about 12 × 19 × 4. Segments snap apart.
- Segments alone are not enough: only 19 fit in a stepped bowl (95 g), which gives 5.5 mm and falls forward at 22°.
- **So the ballast is a cast:** 304 stainless balls 2–6 mm (the user's mixed set, about 165 g of them in that
  range) locked in slow casting epoxy in a smooth bowl, filled by weight: about 119 g of balls + 11 ml of epoxy,
  in two pours. Picture: `images/desk-housing-v2/rolypoly-ballast-fill.svg`. 304 does not stick to the magnets.
- **Trim:** a layer of up to 6 segments on the cast, plus one standing on the bulkhead's back on the right. On a
  level table, slide a segment towards the high side: 10 mm of travel changes the lean by about 0.8°. A phone
  spirit level on the flat panel shows when it is plumb. The stable cup takes 12 segments and no cast.
- Search terms: `Klebegewichte 5g Stahl Riegel`, `Trimmgewichte selbstklebend Stahl 12x5g`, `Stahl BBs 4,5 mm 1500
  Stück`. Höllein (hoelleinshop.com) lists single strips; its price was not confirmed. 4 strips cover ballast + trim.

## Finish
| Route | Result | Fits when |
|---|---|---|
| SLA print of the white body (tough, "ABS-like" resin) + a matte or satin clear coat with UV protection | smooth, toy-like, logo can glow through | one clock (the plan) |
| FDM print + brush-on resin coat, light sanding, paint | smooth and tougher; paint blocks the logo glow | printing at home |
| Silicone mould from one perfected master, cast polyurethane resin | perfect surface on every copy | several clocks |
| Vinyl as Youtooz makes it | needs metal moulds and a factory | not for a one-off |

- Only the white body goes to resin. The dark panel stays FDM (fabparts: PETG-CF black, or PLA Matte black), so the
  slot fits do not change.
- First FDM body: PLA Matte at 0.12 mm (or PLA Marble if left as printed). The underside must be sanded where it
  rolls, or get a thin smooth strip along the rocking line; layer steps there make it rock in notches.
- The wall that glows is material-specific: test it in PLA, then again on a chip of the actual resin.

## Carried over from track A (2026-11-15)
Track A (`cad/desk/smooth.py`: upright, 15° and oval shells) was built and reviewed the same day. What applies here:

- **Slot:** track A builds **E** (3 mm front, the 45° runs to a zero rim; the user's choice). F stays a switch.
- **Assembly there:** the board goes in with the rods on, the battery afterwards. Check the same order here.
- **USB:** the user is ordering a right-angle USB-C extension (plug + socket, head about 12 × 7 × 21) that goes
  straight into the board's port. It is a third option for decision 3.
- **Logo:** 14 mm cut-through letters print with 0.72 mm strips; the inlays exist
  (`cad/desk/out-smooth/logo-inlays-small.stl`, 3 mm thick, flat). On a curved wall they stand slightly proud.
- **CAD methods to reuse from `smooth.py`** (import or copy; do not edit it):
  - superellipse sections as periodic splines through points; an inner surface from the same points moved along
    the normal. Do **not** use OCC's 2D `offset()`: the STEP writer dropped those faces.
  - `write_step` re-imports every STEP (solid count, closed, volume); `check_stl` re-reads every STL. STL export
    with absolute deflection 0.01 and 0.1 rad: a relative tolerance thinned walls in the mesh.
  - the report marks each number as designed `[d]` or measured `[m]`; a test strip is a slice of the real shell.
- **How the work ran:** one Opus subagent (general-purpose, `model: opus`) wrote the CAD and was continued across
  rounds; the parent chat edited the shared docs. Review by GPT-6 Astra through the Codex CLI, in the background:
  `~/_PROJECTS/pigeon_drop/tools/codex-run.sh <run-dir> -m gpt-6-astra -e high [-r <session>] -C <repo> -- "<prompt>"`.
  Ask it to reproduce numbers from the exported files, not from the report. It found real faults in three of four passes.
- **Files to print** are collected as copies in `cad/desk/to-print/`.

## Decisions (user, 2026-11-15)
1. **Two variants from one body:** a roly-poly and a stable one. Picture 13 itself reads as stable.
2. **Two parts:** the body, and a separate bottom cup (seam at z 22, the top of the ballast). The user wants the cup
   mainly because the weights are easy to put in. It also gives a rolling surface free of support scars and a cheap
   reprint for another rocking radius.
   - Roly-poly cup: the rocking arc, a smooth bowl for the cast ballast with a step for the trim layer.
   - Stable cup: the same body cut flat at z 12, so 10 mm tall. Foot 60 × 47, clock 116 tall, tips beyond about 40°
     sideways and 34° fore-aft (study, with 44 g of weights). Round the foot's edge in CAD.
   - The SLA body may merge the cup once the sizes are known.
3. **Outline like picture 13:** the upper body and the panel sit 5 mm left of the rocking arc's centre (`XOFF`,
   blended in between z 23 and 62); the left shoulder narrows early, the right stays wide. Rocking numbers are those
   of the default (11.4 mm, 0.87 s). The battery stays near the centre; the ballast's centre sits 1.5 mm to the
   right. The panel is set back 8.0 mm at its centre.
4. **Logo:** on the front of the belly, right of the alcove (now x 25–38, z 30; first x 21–35), on a face that curves away.
   14 mm; the user finds it small and is unsure, so keep size and position parameters. **Glow-through, not cut
   through** (user, 2026-11-16), and moved right to x 32 because the E lay on the alcove's corner. Tried in clay
   (`clay-rolypoly-logo.png`): 18 mm wraps round the belly's corner, 24 mm on the right flank is hidden from the front.
5. **USB:** a USB-C breakout low at the back **on the centre line**, wired to J5 (MX1.25 4-pin pigtail, not yet
   sourced). Thin cable straight back. The user expects small swings to work plugged in: check on the print. The
   righting stiffness is only about 0.7 mN·m per degree, so a cable pulling sideways leans the clock.
6. **Opening:** the dark panel is the door, on magnets (42.5 × 82), carrying the board. Changed in CAD: the battery
   is not on the door (that gave 6 mm and 28°) but in the belly on a bulkhead, pushed in from below with the cup off.
7. **Wireless charging:** dropped for now (steel ballast and a curved underside where the coil would sit).
8. **Tubes level.** A stagger (one tube lower, both shorter) was tried in clay (`clay-rolypoly-stagger.png`) and
   dropped.
9. **Defaults taken, not objected to:** size 86 × 50 × 128, judged on the print; slot E with F as a switch; bowl sized
   for the heavy ballast case; one clock, so print, not casting.

10. **No hole for the power switch.** Switch the board on before closing the door; the user drills one if needed.
11. **Ballast from the user's 304 ball set** (see "Ballast and trim").

The user saw `clay-rolypoly-13-*.png` and `clay-stable-*.png`: "pretty good" (5 mm shift, cut at z 12).

Still open:
- The trim segment on the bulkhead and the cup printed on its back (see "CAD state"): the user has not judged
  them yet.
- Battery runtime: unknown, measure it.

## CAD state (round 5, 2026-11-16)
`~/.venvs/cad/bin/python cad/desk/rolypoly.py` (about 8 min) → `cad/desk/out-rolypoly/`: `body`, `cup-rock`,
`cup-flat`, `door`, `arc-gauge` as STL + STEP, `report.txt`, `build-sheet.txt` (print, assembly, cast, trim),
views (`render_rolypoly.py`). Every assert passes for the nominal masses and for a bad case (board 40 g, battery
60 g, cast 4.8 g/cm³). Review: `docs/desk-housing-reviews/5-rolypoly-cad-astra.md`. Astra's second pass
reproduced the numbers below and the fits: no CAD blocker, ready to print. Print copies:
`cad/desk/to-print/rolypoly-*.stl`.

| Calculated, masses assumed | Nominal | Bad case | Required |
|---|---|---|---|
| Total | 339 g | 341 g | |
| Centre of mass under the rocking centre | 10.1 mm | 8.4 mm | ≥ 8 |
| Falls forward / backward beyond | 31.0° / 31.5° | 29.0° / 30.0° | ≥ 28 / ≥ 25 forward |
| Period | 0.95 s | 1.07 s | |
| Righting stiffness | 0.59 mN·m/° | 0.49 mN·m/° | |
| Stable cup tips beyond (right / left / fore-aft) | 64° / 44° / 36° | 53° / 43° / 36° | |

- **Keel:** the side view's lower corner is squarer than the study's (corner exponent 4.5 instead of 3.2, below
  z 28). The study's keel fell forward at 25.0° (23.0° in the bad case). `KEEL = "study"` restores it;
  `keel-compare.png` shows both.
- **Rocking arc:** R44 through the bottom pole, no flat (off by 0.005 mm). The cup prints **standing on its back**
  so every layer draws the arc. It cannot stand on its own footprint: it needs a broad support cradle with a brim.
  `arc-gauge.stl` checks the arc against the light, unlined (sandpaper in it would change the radius).
- **Seam joint:** 6 pairs of Ø3 × 2 magnets + 2 dowel pins Ø3 × 10; magnets glued flush against a flat plate. About
  172 g hangs on it; the build sheet has a proof test before the ballast goes in.
- **Plumb:** the door and board sit 5 mm left, so with the cast in the clock leans left. One 5 g segment stands on
  the bulkhead's back at x +27.5, one or two trim segments on the left are left out, the rest slide. A rib in
  the bowl or a tilted pour would cost more margin (Astra's numbers in the review).
- **USB breakout:** no cradle. It comes up from below through a notch in the bulkhead, 2.5 mm in front of its seat,
  and slides back into the socket hole; glued. It goes in before the battery.
- **Logo:** 14 mm letters at x 32 (25.4–37.7), z 30, behind a 0.8 mm skin; both letters fully open to the cavity;
  two LEDs 4.5–8.5 mm behind its centre, fed from the I2C header. Moved from x 28 in round 4: there the E sat on
  the alcove's flare. Now 2.05 mm past the flare; the face turns 18 / 30 / 51° from the front at the logo's left
  end / centre / right end. `logo-compare.png` shows both. More frontal: 12 mm letters at x 31.5 (about 46°).
  The pockets' ceilings are 45° roofs (round 5), so the slicer puts no support in the letters; the top edges may
  glow softer for it.
- **Slicer check** (OrcaSlicer, generic 0.4 / 0.12 PLA profile): `docs/desk-housing-reviews/6-rolypoly-slicer.md`.
  The skin prints as two lines; supports only at the USB hole, the opening's top edge and a cap in the crown; the
  cup on its back rides on the slicer's support base. Body about 61 g and 6 h, rocking cup 21 g and 2.5 h.
- **Door:** comes off with a suction cup on its face, or pushed from below with the cup off. Cables have 40 mm loops.
- **Slots:** 8.6 × 66.85 for 66.65 rods (0.1 play per end, as track A). Board stack 9.0 as measured (drawing 9.3).
- Round 3 changed no geometry (the STLs are byte-identical to round 2): build-sheet corrections after Astra's
  second pass, and harder asserts (pole continuity, logo skin and openness, LED and tool clearances, trim layouts).
- Assumed, to check before gluing: the plugs stand 4 mm proud, and 40 mm of cable slack lets the door come out.
  The build sheet has a dry-fit step for it.
- Not verified: real masses and ball packing, the J5 plug's height, magnet pull, a real printer's profile, epoxy heat.

## Work steps
0. **Check the ground:** `git status`; run `rolypoly.py` and compare its report with the table above.
1. **Decisions:** settled above.
2. **Liquid test (user, with the board):** hold the bare board upright and rock it by hand at about one swing per
   second, `vertical` on. Does the surface stay level, with how much lag? Board checks need the user present.
3. **CAD (done, round 5):** `cad/desk/rolypoly.py`, outputs in `cad/desk/out-rolypoly/`.
   - Take the shape functions from the study (`a_side`, `bf_of`, `bb_of`, the panel plane). Import the hardware
     numbers and `flat_end_cutter` from `cad/desk/housing.py`; do not edit it.
   - The organic shell: first try build123d, lofting 30–40 section wires into an outer and an inner solid and
     subtracting (an offset or shell of a free-form body tends to fail). That gives STEP for the SLA provider. If the
     lofts fail, build a watertight mesh from the outer and inner surfaces and cut it with a mesh boolean library
     (`manifold3d` or `trimesh`, not installed yet): STL only.
   - The alcove is a smooth blend in the study; in CAD cut it as a flared pocket with a large fillet.
   - Parts: body, roly-poly cup (stepped ballast bowl), stable cup, panel with the two flat-end slots and the
     board + battery mounts, magnet seats, socket hole, thinned logo wall.
   - **Mass check on the real geometry** with asserts: centre of mass at least 8 mm under the rocking centre with
     the ballast that fits; rights itself from any sideways tilt; fore-aft limit at least 25°; the rocking arc
     symmetric; board and battery pass the opening and fit; how many 5 g segments fit. Reuse the study's formulas.
4. **Print set (done except the codex render):** STL (+ STEP) per part, `report.txt`, views, one codex render from the real model
   (`cad/desk/concept/codex-render.sh`, `prompts/rolypoly.txt`). Write the build sheet: print orientation, sanding
   the underside, ballast, trim.
5. **After the user's FDM test** (size, rocking, cable, falling forward, trim): adjust, then the SLA version of the
   body (about 2 mm walls, one opening, tough resin) and a logo test chip in that resin.
6. **Docs:** build notes at the end of `docs/desk-housing-plan.md`, the weights and prints in
   `docs/desk-housing-parts.md`, the entry handoff. Side ideas go to `KAIZEN.md`.

## Done when
- The build passes its asserts and writes the report with the rocking numbers of the real geometry.
- The user has the FDM print files, the build sheet and a render, and has seen the clay views.
- What only the print can tell is listed: how long it keeps rocking, the cable, falling forward, the feel of the
  size, the logo glow.

## Traps
- A squashed body of revolution does not work: scaling the depth by s shrinks the fore-aft radius of the underside
  to R·s² (about 14 mm here), far under the centre of mass, and it falls over. Design the underside: round
  sideways, flat-ish fore-aft.
- Little ballast rocks slowly but gets touchy (see the 67 g row).
- Codex draws the alcove smaller than it is, the tube ends rounded and the logo on the front. Compare with the clay.
- A hand-cast or thick shell raises the centre of mass; keep the upper walls thin.
- agy's image quota is small; use codex for consistent pictures.

## Open idea (user, 2026-11-20): battery lower or lying flat
The battery is not a hard requirement (one 3000 mAh cell is plenty; a smaller one is fine). Lying flat low in the
belly (just above the seam) or a flat cell in the bowl would turn its ~55 g into ballast: lower centre of mass,
less steel or calmer rocking. Affects the bulkhead, insertion from below, the breakout and the logo LEDs' room.
Next: compare positions and sizes with `cad/desk/concept/rolypoly.py` (centre of mass, period, tip limits, steel
needed) before any CAD; weigh the real board and battery first.
