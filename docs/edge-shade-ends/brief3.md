# Design request: edge end darkness from side-view magnification (read-only, maths + exact spec)

Follow-up to astra-model.md / astra-model2.md (yours). The user (2026-11-25) rejects the gentle averaged ramp (profile
A). What they want, in their words: "it's also possible to just view from the side, and that is when the
magnification of the RGB is strongest. That's why I wanted to darken the very edges and then rapidly decline the
darkness." Earlier: "real dark ends (like edgeShade 0.8) but then a rapid decrease of darkness."

Agreed design (option 1):
- New parameter `edgeShadeEnd` (0..1): darkness at the very edge (outermost panel row). 0 = off, rendering
  byte-identical to today. edgeShade / edgeShadeShape / edgeShadeFold keep their meaning (the grey band level and the
  inner profile).
- From the outermost row inward the extra darkness falls off quickly, following the side-view magnification: rows the
  rod magnifies most when seen from the side (view roughly 45-80 deg from the panel normal, across the tube, either
  side; say what range is physically meaningful given TIR and the housing) are darkest; it lightens as soon as the
  magnification drops, reaching today's factor at or before the old grey band's inner boundary (never lighter than
  today, never a step).

Deliver an exact spec an implementer can code without judgement:
1. Per-row side-view magnification for the 8 mm rod (R 4, n 1.49, gap 0.87, H 72 at 320w8-8, pitch 0.0825 mm, both
   row parities), at the view angles you choose: which rows are seen, their apparent width (|dx/dd| times pitch,
   all images), max and weighted mean. Show the table.
2. The weight w_j per physical row (normalised, 1 at the outermost row) and the exact formula for the final code
   factor, e.g. F_j = F_old_j * (1 - e * w_j)^... or in L* terms - choose what gives "really dark at the very edge,
   then rapidly lighter", and justify perceptually (gamma 2.2, L*). Include how `e = edgeShadeEnd` maps (e = 1 ->
   black at the outermost row?).
3. Row tables (retained code K per half row, edge -> centre) for edgeShade 0.4 / shape 3 / fold 0.4 with
   edgeShadeEnd 0.5, 0.8, 1, and the predicted apparent L* across the rod at 0, 30, 60 deg.
4. How the weights are produced: a generated table (firmware/tools/gen_rod_rays.py style, flash) shared with the sim,
   or a closed-form computable in both with identical double arithmetic (fixed iterations, + - * / sqrt only). Prefer
   whichever is simpler to keep bit-identical. Note the existing physical-to-canvas row averaging and lens mapping
   (render.cpp Tube::buildShade ~5351, sim render.ts edgeShadeRows) the new factor must go through.
Keep it concise: tables + formulas + implementation notes.
