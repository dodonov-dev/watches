# Model request: edge shade that keeps darkening to the very end (read-only, maths + tables)

User (2026-11-24): "Whichever the combination of shading parameters, sides are universal grey — I expect considerably
darker at the very ends." Photo of the panel without rods, board at edgeShade 0.4 / shape 3 / fold 0.4:
docs/edge-shade-ends/photo-no-rods-0.4.png (each tube shows a flat grey band along both sides, then the gradient).
Earlier wishes (same user): real dark at the very edge, then lighter gradually all the way to the middle; subtle
shading up to the middle is fine; the earlier light/dark/light stripes at the side were not acceptable.

Current profile: firmware/src/render.cpp `Tube::buildShade` (~5340) and sim render.ts `edgeShadeRows`; your design in
docs/edge-shade-session/astra-model.md section 3; rod model docs/physical-tube-model.py (8 mm half-rod, gap 0.87 mm,
n 1.49, fold x 3.68 / d 1.92 mm, TIR from 3.98 mm). Code factors per row now (sim, H 72 at 320w8-8, edge -> centre):
docs/edge-shade-ends/rows-now.txt (decoded: at 0.4/3/0.4 the outer 13 of 36 half rows sit at code 0.60 = 33 % light,
flat; at 0.8 they sit at 0.21 = 3 %). Cause: the target L* saturates at Le for x >= x_e (min(x/x_e, 1)), and the
clip F >= 1 - s, so every row whose rays land past x_e (and the pooled fold-back plateau) gets the same factor.

Deliver:
1. Why the band is flat, in the rod's terms: which panel rows are seen where (main branch vs fold-back), and what the
   viewer sees through the rod at the current settings (apparent L* vs x), so the user's "universal grey" is explained.
2. One or two profiles where darkness keeps increasing to the outermost apparent edge and the outermost panel rows
   (no flat band on the panel), with the same 3 params if at all possible (edgeShade = darkness at the very end;
   edgeShadeShape = how far in the gradient reaches / its curvature; edgeShadeFold = fold-back cover), or say
   precisely which param must change meaning. Handle the fold-back non-injectivity honestly: show the apparent L*(x)
   through the rod including the fold-back zone, and whether a light strip near the apparent edge returns; if a
   trade-off is unavoidable, quantify it.
3. Row tables (code factor per half row, H 72 at 320w8-8) for 2-3 recommended settings, and the predicted apparent
   L*(x) through the rod for each, plus the panel-only view (no rod), since the user judges both.
4. Implementation notes for sim + firmware parity (same operations both sides, doubles, fixed iterations), and whether
   PARAMS_VERSION / presets / NVS need to change.

## User's clarification (2026-11-24, after the brief)
"Yes, it can be as grey as it is where it starts (or less if I reduce shade) and then darken towards the edges — map
it to magnification and real look." So: keep today's level at the band's inner boundary (it scales with edgeShade),
and from there darken further toward the very end, following the rod's local magnification / what is actually seen
through the rod (not a panel-mm ramp). Design the extra darkening and its end value accordingly (e.g. the end value
derived from edgeShade, or one extra parameter if unavoidable — say which and why).
