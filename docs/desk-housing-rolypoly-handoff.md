# Desk housing, track B: the roly-poly (handoff, 2026-11-15)

A soft, drop-shaped body (the "soft cairn") that rocks from side to side when pushed and settles with the tubes
plumb. No stand and no mechanism: a rounded, weighted underside. The liquid on the display reacts to the rocking.
Order of work: **settle the open decisions with the user, then CAD for a cheap FDM print, then the final white body
by SLA.**

Read first: `docs/desk-housing-handoff.md` (entry, decisions for every track, tools), `docs/lcd316-mechanical.md`
(board). Pictures: `images/desk-housing-v2/sheet-5.jpg` (18 at rest, 19 mid-rock, 20 plain FDM), `13-cairn-soft.jpg`
(the look), `clay-rolypoly-*.png` and `clay-rolypoly-asym-*.png` (true proportions).

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
- **Logo:** low on the left flank, about 14 mm, glowing through a thinned wall. At true size there is no room
  beside the alcove on the front.
- **Opening:** intended as one seamless body with the panel as the only door, held by magnets.

Run it: `~/.venvs/cad/bin/python cad/desk/concept/rolypoly.py [KEY=value …]` → `out-rolypoly/report.txt`, `body.stl`,
`clay-hero.png`, `clay-ortho.png`. Parameters are at the top of the file.

## Numbers
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
- By a rough count 25–30 segments (125–150 g) fit in the bowl in layers. Shape the bowl's inside as shallow steps so
  they lie flat. Optional: fill gaps with 4.5 mm steel airgun BBs (0.35 g each) in hot glue or epoxy.
- **Trim:** with everything in, on a level table, move a 5 g segment from the low side to the high side. 10 mm of
  travel changes the lean by about 1°. A phone spirit level on the flat panel shows when it is plumb.
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

## Open decisions (ask the user; my recommendation in brackets)
1. **Size:** is 86 × 50 × 128 at 290–370 g right? It is larger than picture 13 suggests, because the 40 × 79 panel is
   real. (Judge it on the first print.)
2. **Asymmetry:** how much, which side? (About the example above; show the clay first.)
3. **USB inside:** the study leaves only 4 mm under the board, so the MOGOOD adapter in the board's own port does
   not fit. Either wire a socket to the board's J5 header (MX1.25 4-pin, same nets as the Type-C), or raise the
   board ~9 mm and the body with it. (J5 + a breakout socket low at the back; see `docs/desk-housing-parts.md`.)
   Or the right-angle extension cable above, if its head fits under the board.
4. **Charging in use:** a plugged cable fights the rocking. Socket low at the back and unplug to play, or a wireless
   coil in the base later? The battery runtime is unknown: measure it. (Socket for the prototype.)
5. **Panel as the door:** the board is 78.85 long, so the opening must be about 82 tall, or the board goes in at an
   angle. Magnets to hold the panel? (Yes; grow the panel.)
6. **Slot:** E (3 mm panel) or F (4 mm)? Track A builds E. (E, keep the switch; confirm with the user.)
7. **Ballast amount:** not a decision: size the bowl for the heavy case and tune with segments.
8. **One clock or several?** Decides print versus casting. (One.)

## Work steps
0. **Check the ground:** `git status`; run `rolypoly.py` and compare its report with the table above.
1. **Decisions:** put the list above to the user. Do not model before 2, 3 and 5 are answered.
2. **Liquid test (user, with the board):** hold the bare board upright and rock it by hand at about one swing per
   second, `vertical` on. Does the surface stay level, with how much lag? Board checks need the user present.
3. **CAD:** `cad/desk/rolypoly.py`, outputs in `cad/desk/out-rolypoly/`.
   - Take the shape functions from the study (`a_side`, `bf_of`, `bb_of`, the panel plane). Import the hardware
     numbers and `flat_end_cutter` from `cad/desk/housing.py`; do not edit it.
   - The organic shell: first try build123d, lofting 30–40 section wires into an outer and an inner solid and
     subtracting (an offset or shell of a free-form body tends to fail). That gives STEP for the SLA provider. If the
     lofts fail, build a watertight mesh from the outer and inner surfaces and cut it with a mesh boolean library
     (`manifold3d` or `trimesh`, not installed yet): STL only.
   - The alcove is a smooth blend in the study; in CAD cut it as a flared pocket with a large fillet.
   - Parts: body (one piece, or split where the user accepts a seam), panel with the two flat-end slots and the
     board + battery mounts, stepped ballast bowl, magnet seats, socket hole, thinned logo wall.
   - **Mass check on the real geometry** with asserts: centre of mass at least 8 mm under the rocking centre with
     the ballast that fits; rights itself from any sideways tilt; fore-aft limit at least 25°; the rocking arc
     symmetric; board and battery pass the opening and fit; how many 5 g segments fit. Reuse the study's formulas.
4. **Print set:** STL (+ STEP) per part, `report.txt`, views, one codex render from the real model
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
