# Darker edge ends: where it stands (2026-11-24, before the PC went to sleep)

Files: brief.md / astra-model.md (on-axis model, profiles A and B), brief2.md / astra-model2.md (off-axis follow-up),
rows-now.txt (current row factors), photo-no-rods-0.4.png. Nothing implemented; board unchanged (perf-cheap 04a75a1
build, user's look, edgeShade 0.4 / shape 3 / fold 0.4).

- Why the sides are flat grey: the target darkness saturates well inside the tube and the factor is clamped at
  1 - edgeShade, so the outer 13-14 of 36 half rows get one identical factor (0.4: 33 % light; 0.8: 3 %).
- User: the outermost rows ARE visible through the rod. Astra's off-axis model agrees: straight-on they show only in a
  sliver, but tilted 20-45 deg the outer band fills 1.1-1.8 mm of the rod image, and the last row becomes prominent
  near 43-45 deg. Straight-on visibility would need a much smaller gap (<= 0.2 mm) or ~1 mm off-centre seating.
- Recommendation (Astra): Profile A. Keep today's profile up to the old grey band's start; from there darken to the
  outermost row by K_j = K_b (1 - s u^1.5), u = cumulative apparent image width the rod gives each row, weighted over
  views 0-45 deg (80 % 0-30, 20 % 30-45). Centre unchanged. Start at edgeShade 0.30 (bare panel: centre L* 96, old
  band start 73, last row 53); 0.40 gives 95 / 64 / 39. Same 3 params, PARAMS_VERSION 33, no NVS change; a generated
  prefix-width table in flash, sim mirrored.
- Profile B (cap the straight-on light rebound near the rod edge by dimming the centre) is dropped: it only helps at
  0-10 deg and costs centre brightness (0.4: 95 -> 82). A at 0.30 leaves a ~5 L* straight-on rebound over ~0.09 mm.
- Next step (awaiting the user's OK): implement A on a branch on top of perf-cheap (sim + firmware, lean checks),
  flash with the user's look at 0.30 and 0.40 for comparison through the rod.
