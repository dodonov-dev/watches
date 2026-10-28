---
name: imminent-residue
description: "Residue right behind a receding meniscus (step 3d): render-only edge-following shear + wet tint + annular film law; why, and the traps"
metadata:
  node_type: memory
  type: project
  originSessionId: 5e4b94a5-9ef3-487e-978f-84b859904c88
  modified: 2026-10-02T14:44:49.951Z
---

2026-10-02: "imminent part of residue" = the smear right behind a receding line. User's case: vertical watch
held sideways, slug slides up, home edge tilted ~45°; the 1D per-column deposit (laid at the edge's mid-row
centre) left a bare wedge beside the slanted meniscus and read as opaque green paint.

Shipped (sim + firmware, Astra math + 2 review rounds): within Z = 2·max|Δ| of an edge the residue is sampled
Δ·w back (shear only when the deposit range is near the edge and |Δ_row| ≥ 1/8); while a line recedes the
deposit within wetFilm px hands over monotonically to the body colour, D^(1−t)·C^t with t = 1 − (1 − wet·a)(1 − f)
(linear-light log/exp LUTs, PSRAM) — a first version tinted B^(1−a)·C^a and the user saw a light gap between
liquid and residue (Astra had warned; I declined wrongly). The wet
film is Bretherton η from contactDyn × follower, seen through the annular path f(u, η·wN) per row (thin water
film = wall lines only, syrup = legs), visibility ·wN·vis so tangent rows never pop.

**Why:** residue physics was left alone here and fixed afterwards the same day (see [[residue-physics]]); flipping
traceThin alone had painted the smear opaque green.
**How to apply:** upscale a user screenshot ×5 before diagnosing — at 133×204 px I misread which end the liquid
was at for an hour. Zone pixels inside drawTube cost ~1.5 µs each on the S3 (spills): keep the dry sheared
span in `traceShearRow` (noinline) and the no-shear/no-film row on the plain path; rows with crossed edges
(exL > ex: short convex slug + compressive slosh) must stay in the general zone — I first called the 2 strips
this broke "float boundary noise"; Astra replayed them. Gate a firmware refactor with check_render_frames
against a reference that differs only by the refactor (tolerance 0), not with parity's 12/255. check_render_frames' random
group has traces + residue + film in every scene, so any residue change differs in ~90 % of it. Related:
[[drawtube-hot-loops-noinline]], [[parity-stacked-blends]], [[firmware-e2e-tooling]].
