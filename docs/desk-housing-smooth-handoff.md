# Desk housing, track A: the smooth design (handoff, 2026-11-15)

A better-looking successor to the v1 box. Front and top are one band with a rolled top edge, laid over a U (back +
both sides) with soft rear corners. Upright, or with the front tilted back by up to 20°.
Order of work: **settle the open decisions with the user, then CAD.**

**2026-11-15: decided and built.** One-piece soft shell + flat lid (not band over U), upright and 15°, slot E.
State and numbers: "Smooth shells" at the end of `docs/desk-housing-plan.md`. The rest of this file is history.

Read first: `docs/desk-housing-handoff.md` (entry, decisions for every track, tools), `docs/desk-housing-plan.md`
(v1 spec and build notes), `docs/lcd316-mechanical.md` (board). Pictures: `images/desk-housing-v2/sheet.jpg`,
`sheet-2.jpg`, `sheet-3.jpg`; true geometry in `clay-hero.png`, `clay-ortho.png`, `clay-w20-*.png`.

## What the user said
- v1 "is good, but was based on limitations of hardware"; the render of it "is not that nice".
- Already on the print, split it as the wood version would be: **U-shaped back + sides, and front + top, with a
  smooth curve**. A one-piece wooden shell may be expensive.
- A smaller logo because of smoother curves "is not a problem".
- **A logo low on the side is not a good idea, unless the body narrows strongly towards the top**; with a tilted
  front it is fine.
- Angle: **straight, or tilted 20° or less** (2026-11-15). Earlier they mentioned 30° as an example.
- Slot ends flat, slot = rod length (see the entry handoff).
- Asked how the curved front + top would be made in a part-wood version. Not decided.
- Not said: which variant, which materials, which depth. Walnut + ivory and black + ivory are my proposals.

## Variants massed so far
Commands run in `cad/desk/concept/`; then `clay.py <tag> two`.

| Variant | Command | Size (W × D × H) | Notes |
|---|---|---|---|
| Upright slab | `massing.py d LEAN=0` | 50 × 30 × 110.5 | logo at mid-height on the side |
| Leaning slab 6° | `massing.py a` | 50 × 30 (41 with the lean) × 108.4 | tips backwards easily, see below |
| Wedge 20°, vertical back | `massing.py w20 WEDGE=1 LEAN=20 H=100 RW=12 SLOT_Z0=20 TOP=14 LOGO_W=20 LOGO_H=12.6 LOGO_Y=25 LOGO_Z=18` | 50 × 48 × 96.5 | logo 20 mm fits low on the side (flat width 29 at z 15, 26 at z 25) |
| Wedge 30° (above the user's limit) | same with `LEAN=30 H=98.5 LOGO_W=24 LOGO_H=15.1 LOGO_Y=36 LOGO_Z=19` | 50 × 63 × 88 | kept for comparison |

- Flat-end slots in a massing: add `SLOT_PROFILE=1 SLOT_L=66.85 ROD_L=66.65` with `SLOT_Z0=22.3` on a slab or
  `SLOT_Z0=21.3` on a wedge (keeps the tubes' centre), and `T=4 SLOT_LAND=1` for the 4 mm front.
- Common to all: band 3 mm (`T`), roll R15 on the slab / R12 on the wedge (`RW`), rear corners R10 (`RB`), outer
  edges R1.5, a dark plinth inset 2 mm and 2.5 high, slots 20.46 apart.
- Face margins on the slab: 21 below the slots, 2.5 flat + the roll above. Hardware fixes the lower margin (USB
  adapter under the board); the roll supplies the upper one.

## Numbers from hand calculations (verify in CAD)
- **Stack depth:** front 3 (or 4) + tape 0.5 + board 9.0 + battery 10 + back 3.
- **Slab depth 30:** v1's "up, then forward" insertion with rods and battery attached leaves about 0.5 mm behind the
  battery; v1 demands 1.0. Either the rods go on from the front after the board is in, or the band comes off (see
  the decisions), or the depth is 32.
- **Roll and board:** the roll's tangent line sits at `H − RW`; the glass may pass about 3 mm above it before it
  meets the inside of the roll (inner radius 12, tape 0.5).
- **Wedge top:** the massing's top is 14 mm deep. With the battery behind the board it needs about 18–20, so the
  20° wedge's base grows from 48 to about 55.
- **Tipping (rough, ~130 g total):** a push at the top of about 10 g tips the 6° slab backwards, about 16 g the
  upright slab, about 19 g the v1 box. A steel plinth, or a plinth reaching ~8 mm further back, recovers it. The
  wedge is not a concern (base 48–55 deep).
- **Small logo:** v1's cut-through letters have 1.23 mm strips at 24 mm width; at 15 mm they drop to about 0.8.
  A small logo therefore wants the glow-through skin (works in wood and ivory PLA, not in black PLA).
- **Viewing:** at a desk the eye looks down at roughly 35°, so a tilted front faces the viewer better.

## Open decisions (ask the user; my recommendation in brackets)
1. **Variant:** upright slab, or wedge with the front at ≤ 20°? (Wedge at 15–20°: the logo gets its place low on
   the side, it cannot tip, it faces the viewer. Costs a base of about 55 mm instead of 30.)
2. **Slot:** E (3 mm front) or F (4 mm)? Comes from the test strip. (Model F as the default, keep the switch.)
3. **How the body opens:** v1's bottom lid, or the band as a removable magnetic front with a closed bottom? (The
   removable band: no seam near the desk, no insertion constraint, and it lets the slab be 30 deep. In both cases
   make the bottom a dark plinth inset 2 mm.)
4. **Materials:** next print black cradle + ivory band? Later walnut cradle + ivory band? (Yes to both. Brass: no,
   the reflections compete with the tubes.)
5. **Logo:** glow through a thin skin, or cut letters with inlays? Position? (Skin; on the wedge low on the left
   side at ~20 mm; on the slab at mid-height at ~15 mm.)
6. **Curved front + top in a part-wood version:**

   | Route | Surface | Catch |
   |---|---|---|
   | Printed (SLA or SLS for the keeper), as is or painted | any colour | FDM shows layer steps on the roll |
   | Veneer over the printed part | real wood, grain running up and over | flexible veneer should take R12–15; needs a test on scrap |
   | Kerf-bent board | solid wood | flat CNC part with cuts inside; may facet or crack at this radius |
   | Bent lamination, or milled from solid | solid wood | most hand work; or expensive and weak across the grain |

   On the wedge the roll can go: a flat front panel, with the top belonging to the cradle. (Print for now; decide
   the wood route after the print.)
7. **USB:** keep the MOGOOD adapter and a hole in the back, or a flush socket? (Keep it for the first print.)

## Work steps
0. **Check the ground:** `git status`; run the v1 rebuild (entry handoff) and see it pass; regenerate one clay view
   (`massing.py a`, `clay.py a two`) to confirm the concept tools run.
1. **Decisions:** put the list above to the user. Do not model before 1–3 are answered.
2. **Massing at real numbers:** rerun `massing.py` with the chosen variant, the real stack depth and the flat-end
   slot; show the clay and one codex render (`codex-render.sh`, `prompts/ribbon-wedge.txt` as the pattern).
3. **CAD:** a new parametric model `cad/desk/smooth.py`, outputs in `cad/desk/out-smooth/`.
   - Import the hardware numbers and helpers from `cad/desk/housing.py` (board, glass, AA, tubes, rods, battery,
     adapter, `flat_end_cutter`, the `Body` dummies, `check`, the report style). Do not edit `housing.py`.
   - Parts: the band (front + top), the cradle (U; with a floor if the band is the door), the plinth / lid, logo
     skin or inlays, magnet seats. Keep every radius, the tilt, the front thickness and the slot profile as
     parameters.
   - Asserts, as in v1: board, battery, adapter and plugs fit; the assembly path is free (insertion sweep, or the
     band sliding on over the rods); rod-to-slot clearances; the slot ends inside the lit area; logo fits its flat;
     magnet walls; minimum wall. Add a tipping estimate to the report.
   - Print orientation per part in the report (the band standing with supports inside; the cradle standing).
4. **Outputs:** STL + STEP per part, `report.txt`, views (adapt `cad/desk/render.py`), one codex render from the
   real model's views.
5. **Docs:** add build notes at the end of `docs/desk-housing-plan.md`, update `docs/desk-housing-parts.md` (print
   list) and the entry handoff. Side ideas go to `KAIZEN.md`.

## Done when
- The build passes its asserts and writes the report.
- The user has seen the views and a render and has the print files.
- Open points that need the printed part are listed (fit of the band on the cradle, layer steps on the roll, logo
  glow, tipping in the hand).

## Traps
- Codex draws the tubes lower than the model and with rounded ends. Compare every render with the clay.
- The plan-view fillet trick for the rear corners only works in the body's own frame on the slab; the wedge rounds
  them after the tilt (see `massing.py`).
- An FDM band printed on its side gives a clean roll but needs supports in the slots; standing, the roll shows layer
  steps near the top.
- Board checks (anything on the real display) need the user present; ask first.
