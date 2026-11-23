# Desk view: the surface seen from a seated viewer (2026-11-22)

User: desktop watch, stand tilted τ = 15° back, viewer seated in front of the table, looking slightly from above.
Decisions: build the lid (not params only); the time is read at the BACK contact line.
Derivation: Fable (scratchpad deskview/, compare.png = current | params only | lid mock).

## Geometry (vertical watch, tube frame x up the tube, y across, z toward the viewer)
- Eye elevation e above horizontal (seated: 25-35°, default 30°); the stand tilt τ comes from the live pose
  (τ = atan2(normal, −along) clamped ≥ 0; ≈ 13° on the user's stand). δ = e − τ above the screen normal.
  Grazing bound (2026-11-23, review 5 item 1): δ = min(e − τ, 75°) (lidAngles), the same δ for T (tan δ) and the fizz's
  P; tipped forward past e − 75° the eye would graze the glass (tan δ → ∞ at 90°: T was 6874 at e 60, τ −29.99° and
  1.96e16 at −30°). Continuous in τ; inactive for e ≤ 30° (τ ≥ −45°).
- Level plane in the tube: x = x0 − z·tan τ. Orthographic view through dry front glass and air: x' = x − z·tan δ.
- The contact ring (meniscus rise h_m = R·tan(45° − θ/2), θ = contactAngle; 0.176R at 70°) projects to an ellipse:
  x'(y) = x0 + h_m ∓ T·√(R² − y²), T = tan τ + tan δ (≈ 0.54 for e = 30°, nearly pose-independent: 0.54-0.58 for τ 0-30°).
  Lower arc = FRONT contact line (the liquid body ends there); upper arc = BACK contact line; between them the lid:
  the surface seen from above, ≥ 91 % transmitting (Fresnel 6 % at e = 30°, water), drawn above the body.
- Lid height at the centre row 2RT (≈ 30 px on the 72-row tube at e = 30°; 25 / 36 px at δ 10° / 20°), pinching to 0
  at the walls (√(R² − y²)). Wall slope (90° − θ) < e → no fold, the dish centre is not a visible edge.
- Liquid under the lid: path ≈ 1.2× the body's at the front line → 0 at the back line: fill opacity gradient
  (with liquidTransparency 0.72: 0.33 → 0).
- Time: the back contact line's apex (centre row) sits at today's time-edge position: x0 + h_m + T·R = time edge.
  Rear marks (on the back wall) read parallax-free against it.

## Params
- New design param `viewElevation` (deg, 0 = off = today's look exactly; vertical only; slider 0-60, default 0;
  the user's look → 20). T computed per frame from the pose (τ) and e; T = 0 when off.
- surfaceWidth keeps its meaning only when off; with the lid the band is the lid (its height is geometric, no cap).
- surfaceBlick: physically a ~6 % mirror at that angle; the blick becomes a thin crescent at the back rim (the
  meniscus there reflects the ceiling) — optional, after the lid.
- Proposed values for the user's look once built: viewElevation 20 (user: "the lid shouldn't be too big"; "slightly
from above": e 20° → δ ≈ 5-7°, T ≈ 0.36, lid ≈ 20 px on the 72-row tube instead of 30 at e 30°), surfaceBlick 0.2;
others kept. The lid must read as two thin contact lines over see-through liquid (low fill, gradient), not a slab.

## Fizz (after the perf pass merges)
- k = clamp((z_R − z) / (2·z_R), 0, 1), z_R = √(R² − y²) (un-eroded R): 0 on the front glass, 1 on the back.
- L = S + k·B with S = front line, B = 2·z_R·T (S + B = back line); P = r·(1 − cos τ + sin τ·tan δ) ≈ 0.1r;
  u_target = L − r + P. Veil × 0 (foam seen through the lid from above, no wedge in front).
  Implemented as max(0, ·) (negative for τ < 0 and τ > 2e). Open (2026-11-23, review 5 item 4), not changed yet:
  exact under the same oblique projection (bubble centre r below its contact along n = (cos τ, 0, sin τ), x' = x − z tan δ,
  checked numerically over e 10-60, τ ±45°, error 6e-8): the sphere's silhouette top is r (1 − cos e) / cos δ (≥ 0) above
  the CONTACT, but L is the level line at the bubble CENTRE's depth z (k from the body's z) and the contact sits r sin τ
  deeper, r sin τ T lower in x'; above L the silhouette top is r (1 / cos δ − 1 / cos τ), signed (< 0 for τ > e / 2, e.g.
  −0.019 r on the stand at e 20, τ 13°). Either P = r (1 / cos δ − 1 / cos τ) (signed: the lp ≥ 0 sentinel and the
  P ≥ 0 skips revisited) or P = r (1 − cos e) / cos δ with L at the contact's depth (k from z + r sin τ). With the
  faded / gained T (below) the level line is not the geometric one either.
- Drift: buoyancy is normal to the level plane → no surface drift from the plane's slope (σ_z = −tan τ, σ_y meniscus
  only); foam stays at the front arc because bubbles arrive along the front glass.
- General form L = x0 + c(ρ) − z·T; today's rule is T = 0.

## Lid size vs tilt (user, 2026-11-22)
The eye is unknown: assume viewElevation e, scale with the signed stand tilt τ (forward < 0), internal constants:
T = (tan τ + tan δ) · f_back · g_fwd; f_back = 1 − smoothstep(lo, lo + 30°, τ), lo = min(e − 5°, 45° − 30°) (far back
the capillary-held end meniscus is seen edge-on: the lid vanishes; the window ends by τ's ±45° clamp at every e, review 5
item 3: at e 60 it was 55-85° and T stayed 1.27 face up; e ≤ 20 bit for bit as before, the branch picked in degrees);
g_fwd = 1 + 0.2·smoothstep(0°, 30°, −τ) (tilting it forward = looking in; 2026-11-23: was e+10→e+35 and 0.5, so back tilt from the stand grew the lid and −30° was 2.6x).
δ = min(e − τ, 75°) (Geometry). e 60: T −45° 3.278, −30° 3.786, 0° 1.732, 30° 0.577, 45° 0 (was 0, 1.96e16, 1.732, 1.155, 1.268).

## Ordered bounds (review 5 item 2)
The lid's rows are budgeted: back line = max(home profile, ring − T R + T z_R), lid = min(2 T z_R · lidEnd, back − home),
front = back − lid; so home ≤ front ≤ back on every row, zero width included (a short slug under a tall lid: its edge rows
sit home = front = back; H 61, wall 3, θ 70°, e 60, τ 0, slug 16.08 at 60 had row 3 home 55.44 > front 29.31).
The stepper's surf / surfL / strokeR are those rows, so its endpoint intervals are never inverted. check-meniscus asserts
the order on every row of every lid budget scene.
