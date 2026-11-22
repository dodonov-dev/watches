# Fizz at the free surface: physical model (Fable, 2026-11-22)

Vertical path. Request: scratchpad surface-model.md (user: foam "pushes existing ones to the side and slightly down too
aggressively"; "worth modelling how it behaves at the surface, even if it means introducing or removing a parameter").

## Model
- Regime: Bo_r = ρgr²/γ ≤ 0.01 for every preset (board look 0.009 at r ≈ 0.26 mm in water). A surface bubble is a sphere
  hanging under the surface; film cap r_f = r·√(2Bo/3) ≤ 8 % of r.
- Lifetime: immobile-film (Reynolds) drainage under 2γ/r: τ_d = μρg·r⁵ / (4γ²h_c²), h_c ≈ 0.1 µm.
  champagne 0.02 ms, cola 0.14 ms, board look (water) 0.05 s, aerated oil 0.9 s (foamStability 1 s), glycerine 8 s
  (30 s), honey 18 s (20 s). Viscous life is derivable; watery life is surfactant-held = `foamStability`.
  `fizzFoamLife` stays in Params (same meaning); derive.ts: min(30, foamStability + τ_d). Keep the ±50 % draw and
  FOAM_POP_T (presentation; a real burst is < 1 ms).
- Lateral motion (ratios to rise speed U):
  - Cheerios attraction v/U = (2Bo/3)(r/ℓ): 0.3 % at contact (board look). Negligible: not modelled, no self-assembled raft.
  - Buoyancy tangential to the surface the bubble rides, h(y,z) = S + k·B:
    v⊥ = k_w·U_i·[b⊥ + σ(b_u − σ·b⊥)/(1+σ²)], σ = ∇h. Stand pose: ≈ 0.6·0.225·U ≈ 0.14U toward the front glass, plus the
    band slope. Tilt head across the bore 0.46R vs a θ = 70° meniscus 0.18R → foam belongs at the front glass, centred.
    Today's FOAM_SLIDE uses only the profile slope in y, so a bubble pushed back never returns.
  - Contact: an arrival under a lone resident: each gets ±U·sinφcosφ/(1+sin²φ), max U/(2√2) = 0.354U, shared equally;
    the surface holds the resident up → a resident is never pushed down; jammed against the wall, the newcomer moves and
    waits below. Raft creep v(ρ) = f·A_cell/(πρ): at 5 parks/s 0.14U at the first ring, 0.07U at the edge.
  - Measured on c6e77da (host replay, stand pose, 60 s): foam in-plane p90 0.48U, p99 1.0U (the cap); 4 % of foam-steps
    sink faster than 5 px/s — the "aggressive" motion.
- Coalescence: inter-bubble films as stable as the cap film → no merging; size classes untouched. Monolayer capacity
  ≈ 0.82(R/r)² (58 for the board look vs 7–8 present); layering is an overflow fallback, the newcomer queues below.
- Projection: the (y, z) raft seen edge-on; front bubbles crisp on the stroke end (k = 1), deeper ones lower in the band
  and veiled; u slaved to each bubble's own endpoint, k from the current body, no floor.
- Expected look (stand pose): a small calm cap of 7–8 bubbles at the front contact line, ~half the tube wide; arrivals
  shoulder in from the rope, neighbours creep outward ≤ 0.15–0.35U, nothing sinks, holes close after pops; no wall
  ring, no merges.

## "Parked surface narrower" check (LCD 320w8-8, H = 72)
- Geometry consistent: foam |y| reaches 24.6 of 24.8 px allowed (R − r, R = 35.5 − 7.33); the lens moves the rim < 0.5 px.
- By convention the liquid colour and band are drawn to ±35.3 px (wallWet 0.9, stroke rows 2..69) while bubble rims stop
  at ±28.2: 79 % of the visible width, 7.3 px a side. Same in flight and in landscape.
- Occupancy narrower still: 90 % of foam within ±18.5 px (62 %) — single-file arrivals. The pool cap throttles the spring
  to 5 parks/s (clock waiting 48 % of steps) vs the 9/s set. Full-width foam needs ~58 bubbles (a count/life matter).

## Plan
1. Drift law in settleFoamV (sim) / the band branch of settleFoam (firmware): replace FOAM_SLIDE by v⊥ above (k_w =
   FIZZ_KW, per-bubble U_i, σ_y the row slope, σ_z = B₀·6t(1−t)/w from fizzEndK's t, w); remove the approach component
   against the deepest contact (foamContactV), pull back into the disc. Float32 + − × ÷ √ only, no trig/RNG/new memory.
2. Contact law: in-plane parting per bubble ≤ FOAM_PUSH·U_i·dt (1/(2√2) derived, or the interim 0.2); a seated bubble's
   u follows only its endpoint, the rear unseated one waits. Delete FOAM_SLIDE, the k floor and the common-U₀ speed·dt cap
   on the vertical path; keep FOAM_FOLLOW, FOAM_CATCH, FOAM_GAP, FOAM_RELAX (3 sweeps), slot-parity tie, FOAM_POP_T, FOAM_VEIL.
3. Acceptance: stand job foam in-plane p99 ≤ 0.354U, zero sink beyond profile recession, foam count unchanged;
   check_fizz_steps --sim --free (vertical), check_render_frames landscape identical, check_board_render board look;
   one board round; fizz step ≤ 0.84 ms.
4. derive.ts foam life = min(30, foamStability + τ_d), τ_d rounded to 0.1 s (watery presets bit-identical);
   foamStability help = "surfactant hold"; mechanical migration honey 20 → 2.5, aerated oil 1 → 0, glycerine 30 → 21.5.
5. (Optional) width: display-only fringe map in fizzRowOf so wall bubbles reach the visible liquid edge (outer 7.3 px
   → 14.5 px via the meniscus boreRow ease), wall rim/glow composed over bubbles.
