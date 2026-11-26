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
