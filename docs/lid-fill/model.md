# The desk-view lid's liquid (2026-11-27)

Request and Astra's ray trace: brief.md, astra-model.md. Built: sim/src/lidLaw.ts + render.ts lid() / markFn; firmware
firmware/src/lid_law.h + render.cpp (lidRow, the mark kernels' lid branch).

## What was wrong
The lid's fill was a (surfaceBand) x surfaceFill x (1 - u): at most 0.28 on the board's ink look, linear to 0 at the back
line, whatever liquidTransparency. Black ink read as a flat grey veil (luma 120-145 between a body of 18 and a back of
197). Rear marks under the lid took the same a (1 - u) as their liquid path.

## Physics (my trace and Astra's agree)
A ray to lid position u (0 front contact line .. 1 back) meets the dish (the renderer's cap of radius R / cos theta,
theta = contactAngle, sheared onto the level plane), mirrors a share F (Fresnel, air to water), refracts and runs to the
back wall; there the tube back shows. Path / 2R on the centre row, board pose (e 24, tau 13, theta 70):
u 0 1.53, 0.25 0.66, 0.5 0.37, 0.75 0.16, 0.9 0.06, 1 0 (a flat level plane would give 1.2 (1 - u): the dish shortens the
back half's paths by 40-50 %). F: 11 % at u 0.25, 6 % mid-lid, 3-4 % at the back; in the first ~2 px the mirror ray
meets the dish again (no light from the tube back).
Ink (t 0.08) on the pale back, luma: 48 / 57 / 87 / 135 / 171 / 198 at u 0 / .25 / .5 / .75 / .9 / 1 (Astra's trace).
So the lid of a dark liquid is its own colour at the front and thins out to the backing toward the back contact line: a
gradient, never a uniform veil; a clear liquid (t 0.8) stays a faint wedge (opacity 0.29 .. 0), as it was drawn.

## The law
- lidLawBuild (per tube, when tau, delta, contactAngle or liquidTransparency change): 33 samples over u of the centre
  plane: the dish point by a quadratic, its normal, Fresnel, the refracted path lam(u) = l / 2R, and keep(u) = 1 - F
  where the mirror ray reaches the dry back wall above the ring (ramping in over 0.15 R), else 1.
- Opacity of the liquid at (u, row): keep(u) (1 - t^(q lam(u))), q = the row's chord share z_R / R; t^x by the
  exp(-i / 8) table of the fizz light. The mirrored tube back is the colour the liquid lets through, so it only thins
  the opacity.
- Lid fill: af = max(a fill (1 - u), min(1, w) opacity) x coverage x (1 - pull us): the shaded fill of surfaceBand /
  surfaceFill stays as a floor (a clear liquid's lid as before), the absorption does not depend on them.
- Rear marks under the lid: wet = max(a (1 - u), min(1, w) (1 - t^(q lam)) / (1 - t)) (the share of "seen through the
  whole liquid"; the path itself for t ~ 1).
- Kept as they were: the blick (it takes liquidHi's luma: black on a look with liquidHi #000000), the front rim, the back
  contour (physically the back line recovers the backing with no dark stroke; the contour is the line the time is read
  at, scaled by surfaceRim), the fill's colours, the foam veil's lid branch (a popping bubble's fade target only).
- theta is clamped to 20..89 deg (a flat surface is a cap too wide to tell); rows off centre scale the path by the chord
  (an approximation near the walls).
- The law's coordinate is its own: 0 at the front line itself, (lo + hi) / 2w of the pixel's footprint; the artistic
  layers keep the stroke's u (which starts edgeSoft / 2 inside the body). Review 1.
- surfaceBand's share (lidPb = min(1, strokeA / 0.16), strokeA = min(1, 1.6 surfaceBand)): the whole absorption from
  surfaceBand 0.1 on, fading to nothing with it (surfaceBand 0 is no lid at all, the side view: no jump on the way; Astra
  asked for absorption even at 0, not taken: 0 means the surface is not drawn). Review 1.
- A refracted ray that runs toward the front wall (the eye far above a deep dish: delta 75 deg, theta 20) takes its path
  to that wall, along the tube 4 (opaque); the table never has less liquid nearer the front line. Review 1.
- The pose key: the law is built for tau and delta in steps of 1 / 1024 rad (0.056 deg), re-keyed when the exact angle
  leaves its step by more than 0.6 of one (lidKey). One build is 0.14-0.2 ms on the S3 (a throwaway build repeating it
  20 times a frame: +3.85 ms), and the IMU's noise changed the exact angles every frame. 1 / 128 rad steps showed as
  jumps where the refracted ray grazes the tube axis (review 2: tau -44.5 deg, e 20, theta 89: 33/255 on a re-key).
- The back contact line's entry lam(1) is 0 by definition (no liquid under the contact line), whichever wall the
  refracted ray runs to: left to the trace it flipped 0 <-> 4 with the ray's direction when the tube is tipped far
  forward (review 3: e 40, theta 80, tau -41.26 deg: the lid's back rim line jumped). A sweep of tau -45..45 deg in
  0.002 deg steps now moves the opacity by at most 5.7/255 a re-key there, <= 11/255 at the extremes, 1.6/255 at the
  board's e 24 / theta 70.

## Board (lcd316@320w8-8, the tuned ink look board-look-tuned.json, stand pose pinned, fizz on; 2026-11-27)
- Final build: 43.2 fps / render 22.50 ms. The per-pixel law costs ~0.4 ms of it (the same build with the law compiled
  out, -DLID_LAW_OFF: 22.09 ms); a law rebuild 0.14-0.2 ms a tube, only when the pose leaves its key step.
- Against the firmware before the lid change (f61144f): 20.5 / 21.5 / 21.8 ms in three runs (fizz is random), so the new
  build reads 0.7-2 ms slower; ~0.4 ms of that is the law, the rest could not be told from run-to-run and build-layout
  noise (with the lid off, viewElevation 0, the two builds read 17.7 vs 18.8 ms in one run and 20.0 in another; with
  surfaceBand 0 they agree, 18.60 vs 18.62).

## Liquid, not fog (2026-11-27, the user after the law: "shading is okay now, but too foggy, not liquid-ish; the back
rim should be a little wider, probably by the wall wetting")
The absorption gradient is what a liquid with 7 % transmission a bore diameter does over a pale back; it stays. What made
it read as fog is what fog has and a surface does not: no edge (the fill fades out to a 0.5 px hairline) and no gloss
(the blick was off: it took liquidHi's luma, black on this look). A translucent liquid reads as liquid by its meniscus
and its reflections.
- The back contact band: the meniscus climbing the back wall. Width = 0.35 of its rise R tan(45 deg - theta / 2),
  0.5..3 px: theta 70 on a 20 px bore 1.2 px, theta 45 3 px (more wetting, taller meniscus, wider band). Colour and
  weight as the old contour (deep liquid tint, surfaceRim).
- The lid's light: the key light mirrored in the meniscus. A lamp above needs the surface tilted toward the eye by
  (elevation - e) / 2, more than the dish has away from the back wall, so the reflection sits on the back meniscus: a
  crescent as wide as the band, just in front of it, on the blick's rows, white through the panel dimmer;
  surfaceBlick is its strength. The side view's blick (a soft patch mid-dish at liquidHi's luma) is not drawn on the lid.
- Band and crescent are each at most a third of the lid's height on a row (the lid pinches to nothing at the walls).
- Rear marks under the lid take the same band and crescent; the foam veil's lid branch keeps the old ones.
- Not built: refraction of the rear marks under the lid (a mark on the back wall is seen ~0.6x compressed along the tube
  through the surface, with a kink at the back contact line: the straw-in-a-glass cue), a lid denser than the body's
  transparency says (it read more liquid in a prototype at 2-3x the path, but it is not what the liquid would do).
Picture: lid-rim-gloss.png (before | band, surfaceBlick 0 | surfaceBlick 0.6 | contactAngle 45).

## Checks
check_lid_law.py (tables bit for bit on the sim's trig, lidOpacity / lidWet, lidKey, the board pose's numbers);
test_compare_device.py on the lid look and the board's ink looks (sim vs native pixels); check_meniscus.py (560 lid /
meniscus scenes, sim vs native, and rear marks under the lid against the law); lid off: check_render_frames byte-identical.
