# Tilted oval (track A2): critique, new concepts, true-scale sketches

Text and SVG only; nothing rendered, no repo file touched.

## How the numbers were made
- A thin-shell estimate (3 mm wall, superellipse sections, board 30 g + battery 55 g), **not CAD**. Checked against
  the tilt15 report: 152 g (150), centre of mass 28.6 / 50.1 (29.2 / 49.1), tips 21.6° back / 30.0° forward (22 / 29).
  Read every figure as ±1 mm, ±1-2°.
- Fit is tested with the **real stack**, inner face at t 4.55 (bowed front, as the oval): battery's top-back corners
  (s 85.7, t 24.65 with its 0.5 insertion offset, x ±17.5), board top (s 95.55), plugs at x +20.7. "Clearance" =
  what is left beyond a 3.0 wall. tilt15 scores 0.8-1.3 on the same test.
- The stack box asked for the sketches (s 12..95, t 3..26) is drawn as given, s counted from the rim. It is larger
  than the real stack: its top-back corner pokes 0.8 mm out of the real tilt15. The real limit is the battery's
  top-back corner, 9 mm lower.
- **Invariant:** board + battery are 85 of ~150 g, so the centre of mass sits ~30-31 behind the face's toe and
  ~48-50 up in every shell. To tip as late as tilt15 (22° back) the flat foot must reach ~51 behind the toe; for the
  oval's 18°, ~47. Every concept below is a different way to put a foot there.

## 1. Critique of (a)-(d)
**(a) Oval wedge.** Needs 51.5-52 at the desk, not the prompted 50 (at 50 the battery's top corners sit 0.5 inside
the wall). Centre of mass 31 back / 50 up, tips ~22° back / 31° forward. Prints trivially (15° inside, nothing
outside). Oval character about half: the plan is 56 × 52 at the desk (a squircle) and 56 × 23 at the top, so the
top flat is a 44 × 10 strip and the side view is tilt15's trapezoid. With plain shrinking superellipses the bow at
the glass edge falls from 1.8 to 1.1 along the slot (openings taper 0.7 per side): sweep the oval's front arc
unchanged along the lean and let only sides and back shrink.

**(b) Leaning bottle.** 100 % oval, and it cannot stand: foot 56 × 37, centre of mass 31 back / 53 up, only ~6
inside the foot's back edge, so it tips at ~6° (the parent's sheet says 9°). The top-back hangs 28 behind the foot
(66 deep in plan). It needs a foot to ~51 (a lid plate 15 longer at the back; ballast would be ~85 g of steel low in front, where there is no room).
Only ~4 mm between the adapter and the back wall: no room for the right-angle plug. Prints fine (15° both ways).

**(c) Sliced oval.** Column must be 56 × 52; tips ~23° / 31°. The prompt has the facet upside-down: a plane leaning
back cuts deepest at the top, so the facet is a U, ±14 wide at the logo, ±20 at the board's bottom, full width at
z 100. The top becomes a D of 56 × 24 with a hard front edge. Flat face = tilt15's slots exactly, which the user
has now ruled out (bowed front). About 40 % oval.

**(d) Leaning pebble.** The favourite, but not at 60 × 55 × 104: the board top (z 95.3) plus roof and dome needs
H 108-110, and the back must stay ≥ 52 behind the toe up to z 80, so it cannot "round over to the desk" from the
top; it is a long flat arc with the shoulder in the last 25 mm. The rendered underside (tangent to the desk) starts
at a 90° overhang and leaves a ~30 mm foot: ~15° back / 19° forward. Fixed in the next section.

## 2. Leaning pebble, true size (refined d) — `fable-svg/pebble-true.svg`
- **60 W × 58 D × 110 H.** Egg outline: widest at z 30, 54 wide at z 80, 46 at z 95, apex at z 110, 38 behind the
  face's toe. Back: one convex curve, deepest (60 behind the toe line) at z 30, 57 at z 80.
- **Front (user's decision):** bowed across the width exactly like the oval, flat inside: wall 4.55 on the centre
  line, 4.09 at the slot centre, 3.09 at x 15.6, 3.00 at x 15.9 (oval: 4.55 / 4.16 / 3.21 / 3.00). Slots as the
  oval's: opening 14.3, bridge 4.5, rod crown 0.54 under the face. The bow is the same at every height (front
  exponent 2.65-3.2 by height); shown in the top view and in section A-A + 3× detail.
- **Curvature along the length:** workable only up to ~0.5 mm of crown over the 67 mm slots (R ≈ 1.1 m). The 0.6
  land is unaffected (it is cut from the flat inner face), but every 0.5 of crown deepens the bevels by 0.5 in the
  middle: opening 14.3 → 15.3 (edges bow 0.5 per side), bridge 4.5 → 3.5, rod 0.54 → 1.04 under the face. At 1.0
  the bridge is on the 2.5 floor and the openings look barrel-shaped. 0.5 is barely visible, so my advice: keep
  the face straight from s 10 to 98 and let it curve away right below and above the slots (into the underside and
  the dome); the face then reads as one soft curve. A visible crown (≥ 1.5) needs another slot style: no.
- **Underside that prints:** R7.5 all round. Its first 45° (2.2 high, 5.3 wide) are the lid's edge (the lid prints
  flat, desk side up), then a 0.8 land; the shell starts at the rim at 45° and eases to vertical at z 30. Flat
  foot 43 × 42. Profiles reach 43°; cap the plan's diagonals at 45° in CAD (they come out ~46° in the first 3 mm).
- **Dome:** free outside; inside a 45° tent and a small flat bridge, top wall growing 3 → ~7 without a step.
- **Numbers:** ~153 g, centre of mass 23 behind the foot's front edge, 48 up; tips **21° back / 25° forward**,
  23° sideways. Clearance: battery 5.0, plugs 2.4, roof 1.1. So the depth could drop ~3, at ~2.5° of tipping.
- **Logo:** front chin, 12 mm (14 runs onto the underside's curve with the board bottom at s 16.7).
  **USB:** rim notch at the back, right-angle plug; ~21 behind the adapter (tilt15 16.6).
- **Risks:** contour rings on the top ~8 mm of the dome at 0.08 (adaptive layers there, or sanding; SLA has none);
  the largest footprint (60 × 58 against the oval's 56 × 36).

## 3. New concepts
### Leaning stones — `fable-svg/leaning-stones.svg`
- **Idea:** keep the oval whole (constant 56 × 33 plan, front and back parallel at 15°) and prop it with a small
  round stone behind its heel. From the seat you see the oval alone; from the side, two stones leaning.
- **Size:** 56 W × 57.5 D × 108 H. Slab 31.9 thick, front bowed as the oval, soft crowned top (front roll from
  s 97, back shoulder at z 95). Prop: ellipsoid 46 W × 36 D × 29 H, centre 38 behind the toe; crease with the
  slab's back at z ≈ 29. Flat foot 54 × 51.
- **15°:** the whole slab leans, as (b); the prop supplies the foot (b) lacks.
- **Numbers:** ~149 g, centre of mass 28 behind the foot's front, 49 up; tips **24° back / 30° forward**, 23°
  diagonally. Clearance: battery 2.4, plugs 4.2.
- **Logo:** front chin, 14 mm (constant-depth body, so not on a side). **USB:** notch at the prop's back; the prop
  is the cable garage (~20 behind the adapter) and a pocket for ballast.
- **Print:** slab walls 15°; prop flares ≤ 33° above the rim; its roof is flatter than 45° only in its top 7 mm,
  solid there, and the slab's back wall starts on it. Inside the prop the slab has no back wall.
- **Why oval:** it is the oval's section and parallel silhouette, the slimmest top of all.
- **Risk:** the prop reading as a kick-stand instead of a stone; the crease is a seam the print will show.

### Soft cairn — `fable-svg/soft-cairn.svg`
- **Idea:** #13 at true size: a pear. A full belly low down gives the foot; above the waist the body is nearly the
  oval's section and nods back.
- **Size:** 64 W × 60 D × 110 H. Belly 64 × 58 at z 18; 54 × 35 at z 60; 51 × 32 at z 80; soft top R12. Front as
  the pebble (straight, bowed across). Back: belly 62 behind the toe line → waist 50 at z 60 → leans back 6° to 54
  at z 98. Same lid-split underside; flat foot 46 × 44.
- **15°:** a wedge in the lower half (the belly), near-parallel above.
- **Numbers:** ~154 g; tips **23° back / 25° forward**. Clearance: battery 0.8 (tilt15's level), plugs 2.0.
- **Logo:** front chin 12 mm; a 20 mm logo on the belly's flank is allowed by the "wider at the base" rule but the
  skin there is doubly curved. **USB:** rim notch at the belly's back.
- **Risk:** vase / bowling-pin look if the waist is too marked; the widest body; close to the pebble.

### Menhir — `fable-svg/menhir.svg`
- **Idea:** the calm fallback: every section the oval's superellipse, 56 wide, front 15°, and the back one slow
  concave bow, vertical at the desk and 6° back at the top. The top overhangs the foot by 5, so it reads as
  leaning rather than as a wedge.
- **Size:** 56 W × 53 D × 108 H. Back y = 48.5 + 0.00047 z². Flat top 42 × 12, R7. Flat foot 54 × 47.
- **Numbers:** ~151 g; tips **19.5° back / 29° forward**. Clearance: battery 0.8.
- **It is (a) with a dial:** each degree of back-lean saves ~1.5 of base depth and costs ~1.4° of tipping:
  0° 51.5 / 22°; 3° 47 / 18°; 5° 44 / 15°; 10° 37.5 / 8°; 15° = (b).
- **Logo:** front chin 14. **USB:** tilt15's rim notch. **CAD:** OvalModel + the tilt frame with a depth function.
- **Risk:** the least stable of mine; from the front it is (a); the top is a narrow strip.

### Found stone — `fable-svg/found-stone.svg`
- **Idea:** the pebble as a real, lopsided stone: apex 3 left of the tubes, a fuller, lower hip on the right (the
  board's plug side), the plan's back shifted 5 right at the desk. The logo sits low right and balances it.
- **Size:** 62 W × 59 D × 110 H. Left flank −28.5 at z 40, right +33.5 at z 22; flat foot 44.5 × 43.
- **Numbers:** tips **22° back / 25° forward**. Clearance: battery 3.6, plugs 5.1.
- **Front panel** (|x| < 19) keeps the oval's symmetric bow, so both slots stay identical.
- **Logo:** 12 mm at x +10, under the right tube. **USB:** rim notch on the centre line.
- **Risk:** two dead-straight tubes in a lopsided body read as a mistake unless the asymmetry is decisive; an
  experiment on top of the pebble, not a separate direction.

## 4. Ranking (oval look + 15° + printable + stable)
1. **Leaning pebble, true size** — the user's favourite survives the real numbers (60 × 58 × 110, 21° / 25°,
   prints on its rim) and the bowed front keeps the oval's face.
2. **Leaning stones** — the only one that keeps the oval itself and still tips later than tilt15 (24°), and the
   prop solves the cable.
3. **Soft cairn** — the loved #13 at true size and the most stable soft form (23° / 25°), at 64 wide.

Then: Menhir (calm fallback, a better-looking (a)); (a) wedge (works at 51.5 deep, boxy side, strip top); Found
stone (try it once the pebble is chosen); (c) sliced (out: flat face, D-shaped top); (b) bottle (falls over).

## 5. Concept paragraphs for `oval-tilt-common.txt`
**Leaning stones**

"Leaning stones". Real size: 56 mm wide, 108 mm tall, 58 mm deep overall. TWO stones fused into one printed piece. The MAIN stone is a tall slab with the oval shell's plan (a bar of soap, 56 mm wide and 33 mm deep, the same at every height), leaning back 15 degrees as a whole: front and back are parallel and both lean, so from the side it is a slim leaning tablet about 32 mm thick. Its front is gently curved across its width like the oval's front, and straight along the lean. Its top is a soft rounded crown, not a flat cut. BEHIND its heel sits a SMALL round stone like a river pebble: 46 mm wide (narrower than the slab), 29 mm high, reaching 23 mm behind the slab at the desk. The slab leans on it; where they meet there is a soft crease, as between two touching stones, about 29 mm above the desk. Above the small stone the slab's back is free and leans over it. From the front the small stone is hidden behind the slab; in the side view it is a low dome behind the slab's foot. The two tubes sit in the slab's leaning front, centred, starting about 27 mm above the desk. A tiny 14 mm "EH" logo is centred on the front below the tubes, as a soft glow through the wall.

**Soft cairn**

"Soft cairn". Real size: 64 mm wide at its widest, 110 mm tall, 60 mm deep. One soft piece shaped like a pear leaning back. A full round belly low down (widest about 18 mm above the desk: 64 mm wide, 58 mm deep) slims in one continuous line to an upper body about 51 mm wide and 32 mm deep, ending in a softly rounded top with almost no flat. The front is one straight line leaning back 15 degrees from near the desk to the top, gently curved across its width (not a flat plane). The back sweeps in from the belly to a waist about 60 mm above the desk, then leans back about 6 degrees up to the top, so the head nods back over the waist. Underneath, the belly rounds in to a smaller flat foot (about 46 x 44 mm), so it rests on the desk like a stone with a thin shadow under its edge. Every horizontal section is a soft oval; no corners, no edges. The two tubes sit in the front, centred, starting about 27 mm above the desk. A tiny 12 mm "EH" logo glows through the wall on the front below the tubes.

**Leaning pebble, true size** (not asked for, but it carries the bowed-front decision)

"Leaning pebble, true size". Real size: 60 mm wide, 110 mm tall, 58 mm deep. A smooth river stone standing up and leaning back. Front view: an egg outline, widest (60 mm) about 30 mm above the desk, still 54 mm wide at 80 mm, closing in a broad round top. Side view: the front is a straight line leaning back 15 degrees from about 12 mm above the desk up to 98 mm, then rolls over a rounded apex at 110 mm; the back is one long convex curve from the apex down to its deepest point 30 mm above the desk. Underneath, the stone rounds in all round (radius about 7.5 mm) to a flat foot of 43 x 42 mm, with a thin shadow line under its edge. The front is NOT flat: across its width it is gently convex like the oval shell's front (about 1.5 mm proud on the centre line compared with the tubes' outer edges) and straight along the lean where the tubes are. The two tubes sit in the front, centred, starting about 27 mm above the desk. A tiny 12 mm "EH" logo glows through the wall on the front below the tubes.

## 6. Files
All in `/tmp/claude-1000/-home-andrey--PROJECTS-watches/a944203c-ea3d-4592-be59-806ce86d7bca/scratchpad/`.

True-scale SVG sheets (1 mm = 4 px, 10 mm grid; front, left side with the front on the right, top; rods, the
stack box, the real board and battery, centre of mass, flat foot):
- `/tmp/claude-1000/-home-andrey--PROJECTS-watches/a944203c-ea3d-4592-be59-806ce86d7bca/scratchpad/fable-svg/pebble-true.svg` (also section A-A at z 57 and a 3× detail of the front wall)
- `/tmp/claude-1000/-home-andrey--PROJECTS-watches/a944203c-ea3d-4592-be59-806ce86d7bca/scratchpad/fable-svg/leaning-stones.svg`
- `/tmp/claude-1000/-home-andrey--PROJECTS-watches/a944203c-ea3d-4592-be59-806ce86d7bca/scratchpad/fable-svg/soft-cairn.svg`
- `/tmp/claude-1000/-home-andrey--PROJECTS-watches/a944203c-ea3d-4592-be59-806ce86d7bca/scratchpad/fable-svg/menhir.svg`
- `/tmp/claude-1000/-home-andrey--PROJECTS-watches/a944203c-ea3d-4592-be59-806ce86d7bca/scratchpad/fable-svg/found-stone.svg`

PNG previews of the same sheets (Chrome headless), usable as geometry images for codex:
`/tmp/claude-1000/-home-andrey--PROJECTS-watches/a944203c-ea3d-4592-be59-806ce86d7bca/scratchpad/prev/`.
Generator: `geo.py`, `concepts.py`, `draw.py`, `build.py` in the scratchpad (`python3 build.py`).

## 7. Side notes for the parent (KAIZEN candidates, not pursued)
- A 15° printed shoe under the existing oval print would show the look and the tipping of (b) / Leaning stones in
  the hand within an hour, before any CAD.
- Prompt fixes: (a) 50 → 52 deep; (c) the facet is widest at the top, not at the bottom.
- The 14 mm front logo does not fit on a leaning face with a rounded underside while the board bottom stays at
  s 16.7: 12 mm, or raise the stack ~3.
- Ballast low at the back (the roly-poly's steel shot + epoxy) would give any of these the heft of a stone; a
  3 mm steel lid lifts a 5° Menhir from ~15° to ~20° (estimate).
