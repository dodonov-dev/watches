# Tilted fizz: 3D rise on the vertical watch (plan, 2026-11-22)

Branch `tilted_rise` (from `edge-shade` 2fddb7c). Roles: Astra (gpt-6-astra via codex-run.sh) model + review,
Fable look, Opus implementation + tests. User decisions: vertical only (landscape byte-identical); as physical as
possible incl. face-up stall; surface stays the existing 2D artwork (not physical: viewer-angle dependent); a bubble
near the front glass ends higher (contact line) even on a wide band, mid-bore at the profile; fix the colour pulse
where fizz hits the surface (user: "B, but it reads more like blue, ignoring overall transparency and surface fill").

## Status
| # | point | owner | status |
|---|-------|-------|--------|
| 1 | baseline + shared seeded jobs (state parity) | opus | comparator hardened 4842d1d; review 2: strokes compared, vertical foam tol, full-pipeline run (fixing) |
| 2 | signed normal input | opus | done e44d4c3; review 1: landscape phone mapping regression (fix agent) (board normal sign: stand reads az +0.21 ≈ 12° back, consistent; face-up check pending) |
| 3 | vertical kernel, continuous depth, valid births | opus | review-1 items fixed in block 2 |
| 4 | free flight, wall convergence, stirring | opus | done 6fe1a63; review 2: inward release crosses wall (fixing) |
| 5 | endpoint rule (k, L, P) | opus | done b9acc26; review 2: render clamp whole-disc vs current profile (fixing) |
| 6 | chain parking | opus | done a215582 (park median 20-23 → 8 px); review 2: packing in physical coords (fixing) |
| 7 | depth presentation (two-pass, 4 tint levels, row bias) | opus | done c904c53 (host): back half then front half, veil x (1 - k) every vertical bubble, pinpoint x (1 - zc)^2; 4 levels kept (step = 1/2/1 565 LSB on the board look, no interpolation) |
| 8 | pop pulse: blick neutral (all presets) + foam veil by full band opacity + vertical pop fade | opus | done ea8105b..6ec5caf (merged d1035a3); board e9c924a9: pulse gone, 56.5 vs 57.6 fps (render +0.3 ms), parity 0 > 12/255, NVS kept; user: too glossy → blick grey at liquidHi luma (in progress); k hook awaits point 5 |
| 9 | look review, parity, board perf acceptance | opus + user | perf: stand-pose bench (bench.py / fizz_bench.py --pose stand), stepFizzVertical to flash (IRAM broke the BLE window); look review open |

## Physical model (Astra v1, kept parts)
**Coordinates and input signs.** Define physical coordinates before lens remapping:

\[
x=\text{along the tube toward its top},\qquad
y=\text{across the tube},\qquad
z=\text{toward the viewer}.
\]

Let \(y=0,z=0\) be the bore centre. Use the existing `boreR()` convention, including its `(H−1)/2` row-centre geometry, rather than the current fizz bounds based on `H−wall`.

Define a new signed input `normal`, positive when the face is up. With the existing `along/across` conventions, the buoyancy direction is

\[
\hat{\mathbf b}
=\operatorname{normalize}(-\mathrm{along},-\mathrm{across},+\mathrm{normal}).
\]

The repository’s reference IMU frame has \(+Z\) out of the screen, and recorded face-up samples have positive `az`. Verify this sign on hardware before relying on it.

Carry the measured normal component through the same conditioning pipeline. Do not reconstruct it using an unsigned square root. Normalize a separate physical-pose vector after filtering, without changing the legacy `along/across` values used by landscape. Remove `inputGain` from physical orientation; it is an interaction gain, not a change in gravity direction. Handle an invalid or near-zero vector explicitly, retaining the last valid orientation rather than normalizing noise.

For pure backward tilt:

\[
\hat{\mathbf b}=(\cos\theta,0,\sin\theta).
\]

For pure forward tilt, \(b_z<0\).

**Bubble speed and applicable regime.** An overdamped tracer is appropriate for the rendering budget:

\[
\dot{\mathbf p}=\mathbf u_{\rm mix}+U(r)\hat{\mathbf b}.
\]

For a small bubble with an effectively immobile interface,

\[
U_{\rm Stokes}=\frac{2\Delta\rho\,g r^2}{9\mu}.
\]

A clean, mobile gas interface gives the Hadamard–Rybczynski limit,

\[
U_{\rm HR}=\frac{\Delta\rho\,g r^2}{3\mu}.
\]

Thus \(r^2\) scaling is reasonable in the creeping-flow regime, but the coefficient depends on interface mobility. This distinction is supported by [Manor and Chan’s microbubble study](https://researchers.ms.unimelb.edu.au/~dycc@unimelb/pdfs/164.pdf).

The validity conditions are approximately

\[
Re=\frac{2\rho U r}{\mu}\ll1,\qquad
Bo_r=\frac{\Delta\rho g r^2}{\gamma}\ll1.
\]

“Milliseconds response” is not universal across the preset range. Large bubbles, low viscosity, confinement and deformation can invalidate the literal Stokes model.

For this implementation:

- Keep the existing material-derived `fizzSpeed` as the reference speed. `derive.ts` already derives it from Stokes speed and then compresses/clamps it artistically.
- Apply size dependence using actual radius:
  \[
  U_i=\mathrm{fizzSpeed}\left(\frac{r_i}{r_{\rm ref}}\right)^2.
  \]
  The current `f.v` multiplier is not this law.
- Ignore `fizzFlatRise` and `fizzEdgeRise` on the vertical path.
- Also avoid independent axial/across gains rotating the physical rise vector. `fizzDriftGain` and `fizzAcrossGain` must remain legacy controls on this path, or influence only a common speed multiplier.
- Treat agitation-driven motion as a bounded stirring approximation, not as part of terminal buoyancy.

There is no need for per-bubble velocity state unless persistent stirring is deliberately included.

**Bore geometry and births.** A spherical bubble of radius \(r\) has its centre inside

\[
y^2+z^2\le a^2,\qquad a=R-r.
\]

Continuous physical depth is separate from the renderer’s four tint levels. Four levels can remain a shading optimization; they cannot be four physical planes.

Scattered births must sample a valid liquid volume. Sampling \(y\) uniformly and then independently assigning depth is incorrect. A uniform cross-sectional disc sample can use

\[
\rho=a\sqrt{u},\quad
\phi=2\pi v,\quad
(y,z)=\rho(\cos\phi,\sin\phi).
\]

Use deterministic bounded sampling or direct construction, not an unbounded rejection loop.

A spring must have a definite depth. With no depth parameter, use a documented fixed depth, initially \(z=0\), and apply the existing spread in a bounded 3D neighbourhood. Its submerged/dry test must use that actual point. Preserve the current source-position semantics with respect to fill, but do not move its depth or transverse position merely because the surface tilts.

If a bubble cannot fit, postpone the birth and expose the reason through diagnostics. Do not clamp it into an invalid sphere or allocate another pool.

**Free flight and first contact.** For constant pose and no stirring, trajectories are straight. For pure backward tilt, \(y\) remains constant during free flight.

The front-wall centre limit is

\[
z_w(y)=\sqrt{(R-r)^2-y^2},
\]

so

\[
t_w=\frac{z_w-z_0}{U\sin\theta},\qquad
\Delta x=(z_w-z_0)\cot\theta.
\]

Your 11 mm estimate at \(15^\circ\) is a good **centre-start estimate** for a 3 mm radius, neglecting bubble radius:

\[
3\cot15^\circ\approx11.2\ {\rm mm}.
\]

It is not a general mean. For uniformly distributed point centres in a disc, the mean forward distance to the circumference is \(8R/(3\pi)\), not \(R\).

For general motion, solve the quadratic intersection of the transverse trajectory with \(y^2+z^2=a^2\). Compare that event with the liquid surface and closed end caps. Advance to the **first** contact, then integrate the remaining time under its constraint. This prevents fast or large bubbles crossing a thin liquid wedge in one step.

**Wall motion.** At a bore-wall contact, let

\[
\mathbf n=(0,y/a,z/a).
\]

While buoyancy pushes outward, project away its normal component:

\[
\dot{\mathbf p}
=k_w U\left[\hat{\mathbf b}
-(\hat{\mathbf b}\cdot\mathbf n)\mathbf n\right].
\]

If the force turns inward, release into the liquid. Closed end caps use their own normal, and a bubble at an intersection must satisfy both constraints.

Using \(y=a\sin\phi,\ z=a\cos\phi\),

\[
\phi_*=\operatorname{atan2}(b_y,b_z),
\]

\[
\dot\phi=
-\frac{k_wU|\mathbf b_\perp|}{a}
\sin(\phi-\phi_*),\qquad
\dot x=k_wUb_x.
\]

The draft’s angular equation is therefore essentially correct, with \(R-r\) replacing \(R\).

However:

- \(k_w=0.4\ldots0.7\) is a phenomenological mobility range, not a universal lubrication result. Use one documented implementation constant initially; do not introduce an unsupported material knob.
- The existing random `letGo` followed by movement behind the wall is not a physical release mechanism.
- Existing wall “coalescence” deletes an arriving bubble without increasing the survivor’s volume. Do not carry that into a model presented as physical coalescence.
- `fizzFoamLife` should govern exposed-surface foam, not make a submerged wall bubble disappear.

The transverse attracting position is

\[
(y_*,z_*)=
(R-r)\frac{(b_y,b_z)}{\sqrt{b_y^2+b_z^2}}.
\]

This produces a narrow ridge, not necessarily a perfect single file. Finite residence time, different radii, stirring and packing give it width. At exactly upright, \(\mathbf b_\perp=0\), so there is no preferred ridge.

The convergence timescale near the ridge is

\[
\tau_w=\frac{R-r}{k_wU|\mathbf b_\perp|}.
\]

Reaching a specified narrow width takes several such timescales. The draft’s \(R/(U\sin\theta)\) is a useful order-of-magnitude estimate, not a complete stream-reformation time.

Face-up, a bubble on the **wetted front high point** has zero projected velocity. Face-down gives the analogous back-wall stall. A surface encountered first still takes precedence.


## Revised plan (Astra v2; supersedes v1 items)

**Model delta from v1.** Adopt the retained, full-bore plug convention in every pose. Keep today’s `surf/surfL`, surface artwork and rear-mark wetness. Remove the inclined-plane renderer, volume correction, new capillary solver and liquid-path optics from the plan.

Keep continuous 3D bubble motion, signed normal input, circular-bore constraints and tangential wall sliding. Use one documented wall mobility constant, initially \(k_w=0.6\). Remove `inputGain` from physical orientation and bypass artistic axial drift on the vertical path. Retain the four optical depth levels initially.

Recommend **vertical-only**, including both pulse fixes. The early branch is straightforward, preserves landscape byte identity, and avoids turning the wrist’s usual face-up pose into a stalled raft. A landscape pulse fix can be a separate decision.

One physical qualification remains: exactly face-up, submerged bubbles can stall and births can eventually wait at the population cap. Spontaneous turnover would require an explicitly cosmetic disappearance rule or a gas-loss model. Do not restore axial drift or teleport bubbles to satisfy it. Likewise, 1–2 s stream recovery is a look target for this preset, not a universal recovery time across materials.

**Exact endpoint rule.** Work in outward coordinates \(u=sx\), with \(s=+1\) for the time edge and \(s=-1\) for the home edge:

\[
S_s(j)=
\begin{cases}
\mathrm{surf}[j],&s=+1\\
-\mathrm{surfL}[j],&s=-1
\end{cases},
\qquad
B_s(j)=
\begin{cases}
\mathrm{strokeR}[j],&s=+1\\
\mathrm{strokeL}[j],&s=-1.
\end{cases}
\]

`band` means **this local positive stroke width**, in canvas pixels. Today, for an enabled, visible concave stroke,

\[
B_s(j)=\min(\mathrm{surfaceWidth},\text{local outward ring–profile separation}).
\]

It is zero when that stroke is absent, including the convex branch. It excludes the inward `edgeSoft/2` overlap. Consequently, `surfaceWidth = 16` does **not** mean a 16-pixel band on every row. The stroke endpoint is the displayed contact-line proxy; when width-limited, it can fall short of `wallX/wallXL`.

For each bubble, let \(r\) be its unswollen radius, \(y\) its physical cross-sectional offset, and \(z>0\) point toward the viewer:

\[
a=R-r,\qquad z_c=\sqrt{\max(0,a^2-y^2)}.
\]

Interpolate the local band at the bubble’s displayed centre row to get \(B_0\). Compute once per bubble:

\[
d=z_c-z,\qquad w=\min(z_c,B_0+r),
\]

\[
t=
\begin{cases}
\operatorname{clamp}(1-d/w,0,1),&w>\epsilon\\
0,&\text{otherwise},
\end{cases}
\qquad k=t^2(3-2t).
\]

Thus \(k=1\) at the front glass, fades over at most \(B_0+r\) depth, and is zero from mid-bore backward.

For each row touched by the bubble:

\[
L_s(j)=S_s(j)+kB_s(j),
\]

\[
P_s(j)=r\max\left(0.3,\ 1-\frac{B_s(j)}{2r}\right).
\]

\(L\) is the local contact boundary; \(P\) is the permitted leading-rim protrusion. For a locally flat boundary, the parked centre target is

\[
u_{\rm target}=L-r+P.
\]

For a curved profile, reuse the whole-disc support calculation: take the minimum of \(L_s(j)+P_s(j)\) minus the bubble’s axial half-chord at that row. Use the existing lens-compensated footprint.

This preserves the thin-band, half-out look. On a wide band, a front bubble reaches its local stroke endpoint, while a middle/back bubble ends at the profile with only the specified small protrusion. Since \(0\le k\le1\), the contact target never borrows a farther endpoint from another depth or row. The only permitted extension beyond it is \(P\).

Multiply the existing **veil opacity**, not its transmission, by \(1-k\). Front bubbles are unveiled; back bubbles retain the existing veil. Apply the separate pop treatment in point 8.

Do **not** add the optional \(-R\tan\theta\) term: it would detach fizz from the retained surface artwork and require a near-horizontal limiter.

**Block 1 — Baseline, inputs and bounded state**

1. **Capture the current look and extend existing parity infrastructure.**  
   **Files/functions:** `firmware/tools/check_fizz_steps.py`, `check_render_frames.py`, `sim/tools/render-ref.ts`, existing temporary native harness/stub generation.  
   **Change:** Add the supplied board-look fixture and deterministic vertical jobs covering upright, ±15°, across+back, face-up/down, shaking and crowded foam. Extend the existing job input with optional initial fizz state, fixed-step inputs, RNG seed and state output; keep ordinary frame jobs unchanged.

   Today, the sim uses `Math.random`, LCD firmware uses per-core xorshift, and native builds use stubbed `esp_random`. `check_fizz_steps.py` compares two native versions; existing sim/native frame comparisons do not prove stepped fizz parity.

   The cheapest cross-language check is to give the test-only native stub and sim job the same uint32 generator and conversion, `(word >>> 8) / 16777216`, then compare named state fields and draw counts after each step. Reuse the native `render.cpp + physics.cpp` build; no separate tool initially.  
   **Proof:** Jobs repeat exactly; the unchanged landscape subset matches `2fddb7c` in pixels and stepped state. New-kernel arithmetic uses float32 ordering in the sim and contraction-disabled host comparison. Board determinism remains a separate check.  
   **Parity:** Infrastructure only. Preserve existing native old/new tests, including their original random streams.

2. **Carry signed normal through the complete input pipeline.**  
   **Files/functions:** `physics.h/.cpp`, `sim/src/physics.ts`, `spec/layout.h/.ts`, `main.cpp::imu_poll/physStep/runFizzSteps`, `sim/src/main.ts`, `serial.ts`, override/replay/sequence inputs.  
   **Change:** Add and filter signed normal; propagate it through `FizzStepIn`, defaults, reset and test overrides. The raw IMU stream already includes `az`. Add a signed manual pose and consistent phone-orientation mapping. Form the physical buoyancy direction from `(-along, -across, normal)` without `inputGain`; preserve legacy signals.  
   **Proof:** Extend `check:imu` for both hemispheres, upright, sign reversal, gain changes and low-magnitude input. Verify the board’s normal-axis sign.  
   **Parity:** No landscape arithmetic changes. All new vertical inputs match in the shared jobs.

3. **Introduce the vertical kernel, continuous depth and valid births.**  
   **Files/functions:** both renderers’ `stepFizzTube`, fizz birth/reset helpers; firmware `Tube/render_init`; `render.h`.  
   **Change:** Add the early `p.vertical` branch. Keep physical depth separate from quantized tint depth, preferably in a sidecar preserving legacy `Fizz` layout. Generate births inside \(y^2+z^2\le(R-r)^2\); give the spring a documented fixed initial depth, \(z=0\), with bounded spread. Preserve cadence, `fizzWant`, population limits and one-birth credit.

   Allocate all sidecars, endpoint metadata and scratch once at boot, for **480 slots per tube**, in PSRAM. Mutable scratch belongs to each `Tube`. Impossible fits fail visibly; blocked births wait.  
   **Proof:** Containment, source wet/dry, pool saturation, mode/height changes and allocation-failure tests. Report exact added memory; verify no post-boot allocation.  
   **Parity:** Landscape state layout and random consumption remain unchanged. Vertical birth state and RNG counts compare through point 1.

**Block 2 — Motion, endpoints and parking pulse**

4. **Implement free flight, wall convergence and bounded stirring.**  
   **Files/functions:** vertical `stepFizzTube` helpers and per-size speed preparation in both renderers.  
   **Change:** Use a common buoyancy direction and radius-squared relative speed. Project outward wall motion onto the cylinder tangent, slowed by \(k_w\); release when forcing turns inward. Handle closed ends separately. Disable vertical `fizzFlatRise/fizzEdgeRise` and anisotropic direction gains.

   Add bounded agitation-driven transverse motion. Keep physical depth continuous through contact. Give each bubble a stable hashed display-row bias, initially ±0.75 design pixels scaled to the tube, clipped near the silhouette; it must not alter physical containment or accumulate into drift.  
   **Proof:** Analytic flight and wall-contact cases; gradual convergence and roll response; front/back stall; shake spreading and recovery. Inspect the current look for the free-flight region, soft funnel and slower rope.  
   **Parity:** Vertical changes only. Match deterministic state and random draws; keep geometry out of pixel loops.

5. **Apply the endpoint rule to movement, foam placement and drawing.**  
   **Files/functions:** `drawTube` publication of `surf/surfL/strokeR/strokeL`, vertical `discFit/foamFront` equivalents, `settleFoam`, firmware `planBubble`, sim fizz drawing.  
   **Change:** Implement \(k,L,P\) above in one endpoint helper per language. Publish the existing stroke widths alongside the existing profiles; add no surface geometry. Use whole-disc support for placement and the current frame’s profiles for render-time correction.

   Keep the existing last-drawn-surface stepping contract; associate profiles and widths with the same generation/height. Closed glass ends remain physical constraints, without surface-poke allowance.  
   **Proof:** Same-row front/middle/back bubbles, thin and 16-pixel bands, pinching wall rows, zero band, convex surfaces, both ends, large bubbles and moving profiles. Front bubbles reach their own contact proxy; back bubbles remain at the veiled profile.  
   **Parity:** Vertical endpoints and pixels change. Surface-only and all landscape frames remain byte-identical.

6. **Stop remote and same-step chain parking.**  
   **Files/functions:** vertical `touchesFoam` usage, candidate gathering and lifecycle assignment; existing `FoamWork` indexing.  
   **Change:** Snapshot eligible foam at step start; newly parked bubbles cannot recruit further bubbles that step. More importantly, starting a foam timer requires the arriving bubble to reach its **own local endpoint zone**, measured with the support helper and existing `FOAM_CATCH`. A deeper contact may block motion, but cannot start a lifetime or pull the bubble toward the surface.

   Retain spatial indexing and add depth to contact rejection so projected overlaps do not create false contacts. Do not introduce all-pairs packing.  
   **Proof:** An adversarial long chain cannot park remotely, either immediately or progressively over later ticks without reaching the surface. Replay the diagnosed board look and report park distance, parks per 0.1 s and foam-count variation. The reported 28–73-pixel remote parking must disappear.  
   **Parity:** Apply vertically only. Extending this fix to landscape would intentionally change foam state and frame hashes; leave that for a separate user decision.

**Block 3 — Depth presentation, pop pulse and acceptance**

7. **Add inexpensive depth presentation.**  
   **Files/functions:** sim fizz drawing; firmware `planFizz/planBubble`, `FizzLook`, `BubblePlan`, tile-band bubble lists.  
   **Change:** Map continuous physical depth to the existing four tint levels on both sides. Keep the physical state continuous at wall contact. Draw back-half bubbles first, front-half bubbles second, preserving slot order within each pass; preserve that order in every tile. Attenuate the pinpoint toward the back. Apply the stable row bias and endpoint veil coefficient during bubble planning.

   If four-level transitions are visible in review, add interpolation between existing optical levels as a measured follow-up within this point, rather than new physical depth classes.  
   **Proof:** Overlapping front/back bubbles, continuous depth travel, no contact-specific tint jump, tile/strip agreement and centred-digit legibility.  
   **Parity:** Vertical optical changes only. Retain existing class masks and cached colours.

8. **Remove the broad grey pop wash without abrupt disappearance.**  
   **Files/functions:** sim pop setup and fizz compositing; firmware `planBubble`, `discOf`, analytic/masked band-veil paths.  
   **Change:** For vertical surface foam, remove the `1.6r` pop expansion and retain the base-radius footprint. Let

   \[
   q=\operatorname{clamp}(|life|/\mathrm{FOAM\_POP\_T},0,1),
   \qquad a=q^2(3-2q).
   \]

   During popping, use \(k_{\rm pop}=ka\), so the front exemption from the veil disappears smoothly. Let \(V\) be the existing band-veil opacity before depth scaling, and \(C_B\) the existing pixel-footprint coverage by the band. Apply bubble coverage as

   \[
   A=A_0\,a\,[1-(1-k_{\rm pop})V]\,[1-C_B(1-a)].
   \]

   Thus a fully band-covered pop gets an additional fade toward the **already composed band**, rather than an expanding translucent ring. Outside the band it fades smoothly. Reuse existing band-footprint calculations; introduce no per-pixel geometry or surface redraw. Fade all bubble contributions consistently.  
   **Proof:** Run the diagnosed 60-second fixed-clock sequence at across 0 and 0.05. Verify a static fizz-off band, reduced grey-ring area and colour excursion, and no increased final-frame disappearance jump. Measure chain and pop fixes separately before combining them.  
   **Parity:** Vertical-only. Ordinary alpha blending can still mix colours; visual and temporal measurements must demonstrate that the diagnosed wash is removed.

9. **Complete look review, parity and board performance acceptance.**  
   **Files/functions:** existing meniscus/frame/board checkers, `fizz_bench.py`, relevant parameter help and status documentation.  
   **Change:** Extend benchmark poses to signed normal and use the supplied board look unchanged: spring rate 9, count 120, size 5, speed 48, foam life 1.5 and surface width 16. Document ignored vertical drift controls. Introduce no serialized knobs or preset retuning.

   Review each block with matched fill, pose, seed and elapsed time. For board visual checks, the user is present and only one visible change is reviewed per round.  
   **Proof:** Build/type checks, `check:imu`, meniscus checks, shared-job state comparisons, landscape byte comparisons, and board repeatability. On lcd316@320w8-8 compare against the approximately 58 fps baseline using frame-time distribution, per-core time, fizz time and catch-up count. Include crowded face-up and maximum-pool stress; no performance recovery by reducing population.  
   **Parity:** Acceptance requires unchanged landscape behaviour, matched vertical state, and established render-parity tolerances. All additional geometry work is per bubble or existing disc-row setup; all memory remains fixed-capacity.
## Art direction (Fable)

Poses: upright as today. 10-20° back: lower ~2 bore widths bubbles keep their row and brighten as they come forward,
then a soft funnel inward, then a loose rope of crisp slower bubbles near the centre line with dimmer free bubbles
overtaking behind. Flat on back: no screen motion, bubbles surface out of the tint, gather on the centre line, creep
toward whichever end is higher. Forward: dim ghost rope on back wall, veiled at the surface, no dome. Across+back: rope
off-centre toward the high side, swings with lag on roll, never jumps. Shake: cloud of mixed depths, re-forms 1-2 s.
Cues by value/cost: (1) convergence geometry with lag (stepper only), (2) continuous dynamic z → depthK tint (not 4
levels), (3) end height + veil by depth, (4) back-to-front draw order (two passes deep/front, no sort), (5) on-glass
slower than free, (6) pinpoint only near front. Not worth it: depth lens stretch, defocus, refraction row shift,
contact flattening, shadows, zig-zag, tilt-dependent surface band.
Pitfalls: ruler-straight line → ±0.5-1 px row bias per bubble (hash of size); rope runs over centred vertical digits
(check legibility in side-by-side); keep z continuous, no tint jump at wall contact; randomise depth after shake;
face-up freeze must keep turnover (let-go/coalesce, pool cap); rope positions only slide, never respawn on the line.
Surface meeting rule: end L = profile + k·band (band = local stroke width strokeR/L; k = 1 on the front glass, → 0
within ~band+r of depth, 0 from mid-bore back); may poke past L by r·max(0.3, 1 − band/(2r)) (thin band: today's
half-out look kept); veil × (1 − k) (front-glass bubble unveiled).
Pulse candidates (code reading, not reproduced): pop swell 1.6r with dark tint at spring cadence; veil jump 0→70% in
1-2 px gliding on; pile at dish centre (slope 0, column length breathes). Discriminate: fizzFoamLife=0, surfaceFill=0.
Wrist (if generic): face-up is the wrist's default, so the physical stall = a near-static raft toward the high edge,
pool at cap; today's fizzFlatRise/EdgeRise drift is what keeps it alive. Needs visible turnover (let-go/pop/coalesce)
and agitation re-scatter; the user retunes this later. Surface rule unchanged.

## Pulse diagnosis (host, round 1)

- Bare band (fizz off) is static: 0/255 change in 60 s. Every change at the surface is bubble discs.
- No clean period on band mean colour (autocorr ~0 by 0.3 s); peak-to-peak 15/19/24 RGB.
- Births regular (8.5/s, Fano 0.15). 100% of parks come from touchesFoam (render.ts ~1281), median 28 px (up to
  73 px) behind the front: chain-parking within one step, up to 6 at once, 10-15 per 0.1 s (Fano 3.3-4.2); foam count
  swings 3<->27 (0.35-0.43 Hz). touchesFoam off: parks random (Fano 0.95), foam std 4.7->2.8.
- Pop swell+fade (render.ts ~2119-2120, ring faded by wallT*pop ~2138) leaves translucent grey rings over the blue
  band: 10.6% of band px per frame (4.9% with pop off; but pop off makes bubbles vanish at once: frame-to-frame up).
  With across=0.05 front-row bubbles go grey together (visible clumps).
- Rim body-colour mix ruled out (depthK >= 0.80, bubbleDark 0). Firmware draw path matches the sim.
- Fix directions: cap chain-parking (one hop per step, or only foam already at the front); pop fades under the band
  veil instead of a translucent rim over the band.

## Pulse diagnosis (board, round 2) and decision
The blue is the surface band's blick (surfaceBlick, painted in liquidHi at full strength, ignoring surfaceFill and
transparency); foam veiled by the fill only cuts dark rings into it and each pop reveals it. Board A/B: blick 0 → no
blue. Sim and firmware agree. User (2026-11-22): blick becomes neutral room light (every preset) and foam is veiled by
the band's full layer opacity (fill + blick + rim).

## Board, block 2 (elf 33826f6e, 2026-11-22)
Flashed b-2 merge; look kept; board-look parity 32 px off, 0 > 12/255. Pinned bench (g 0 0 = face-up for the new kernel:
bubbles stall) 60.4 fps — not comparable; live on the stand 52.1 fps, fizz step 0.84 ms. Point 9 must pin the stand
pose (along ≈ −0.976, normal ≈ +0.22). IRAM +5.9 KB for stepFizzVertical: measure flash vs IRAM on the board (review 2.5).

## Review-2 fixes + "fizz explosion" (57ffb69), board elf 61951d55
Items 1-4 fixed (release re-runs first contact; whole-disc render clamp on the drawn footprint; packing in physical
(u, y) with √(m²−dz²); --free = common-input kernel parity, strokes/surfaces compared before injection, vertical foam
tol 1e-3). User saw "a small fizz explosion, including downwards" at the surface: contact push moved bubbles down 7142×
/60 s (worst 7.2 px/step), packing 3208× (worst 30 px); fixed: overdamped contacts, packing push-back ≤ fizzSpeed·dt.
Side effect: foam grows down as a column (sink > 10 px 12/199 → 138/225) — foam packs only in (u, y) at fixed z while
arrivals are single-file on the front ridge.

## Foam over the surface plane (y, z)
settleFoam (vertical): a touching foam pair parts in the surface plane (y, z) at its u to the in-plane
√((m + gap)² − du²), inside the eroded disc, each bubble ≤ fizzSpeed·dt a step in the plane (FoamWork yS / zS);
only what the plane leaves in the last sweep stacks (rear back ≤ fizzSpeed·dt); one above the other: along the wall
tangent, side by slot parity. k (veil, endpoint) follows each bubble's (y, z); the endpoint's k falls no faster than
the bubble may sink (target >= uS − fizzSpeed·dt, chord of the concave support; round the side wall k turns over
within a pixel of depth). Host replay, stand pose 60 s: foam
lives sinking > 10 px 138/225 → 0/241 (worst 8.6 px); down moves > fizzSpeed·dt 0; foam count std 3.99/3.07 →
3.67/2.88; foam depth z std 1.1 → 4.5 px (22% veiled, k < 0.5). Open: free bubbles held behind a lone ridge foam
(KAIZEN).

## Board c6e77da (elf d2501f68) + Astra review 3
Foam spreading flashed, look kept. Review 3 (docs/tilted-fizz-review3.md): point 7 and review-2 fixes settled; open:
k floor causes a 10 px rendered jump when foam crosses the side wall (remove floor, bound the coupled move), stale wall
contact after inward deflection, offset approaches behind a lone foam bubble should slide around (centred wait OK).
Fixing on the host. Point 9 (stand-pose bench, IRAM vs flash with BLE, look review) still open.

## Board, point 9 perf (2026-11-22, lcd316@320w8-8, board look pinned volatile, `--pose stand` = g -0.976 -0.01 0 0 0.22)
bench.py --runs 3 (median): IRAM (today) 53.5 fps, render 18.12 ms, cores h 16.28 / m 13.34, p95 20 ms, fizz step 1.27 ms;
flash 53.0 fps, 18.30, 16.18 / 13.39, 20 ms, 1.50 ms; flash + foamContactV noinline IRAM (+940 B) 52.9 fps, 1.51 ms (no gain).
fizz_bench 480 pin: IRAM 15.0 fps / fizz 16.4 ms, flash 13.4 / 18.9; 480 swing 10.3 / 11.9 (5-step cap).
Internal heap (fast mode, `s` heap / heap-min / heap-big): IRAM 28.6 KB / 27.9 / 13.8 KB; flash 36.2 / 35.5 / 20.5 KB.
BLE window (B1): IRAM fails at boot (BLE_INIT malloc failed, BLE assert emi.c 164 -> interrupt-WDT panic, back to fast
mode); flash: 4.9 KB free advertising, connect + subscribe + p? / p~ traffic + 3 reconnects OK, min 3.2 KB, largest
block 2.0 KB; stand bench in the window 52.2 fps. Decision: stepFizzVertical in flash (-0.5 fps, +0.23 ms fizz step).
## Review 3 fixes + foam seniority (host)
- k always from the current body (floor gone): a move in the surface plane that would sink a foam bubble's target below
  min(uS - fizzSpeed dt, its target at the step's start) is shortened (6 halvings); selftest 'side wall' (10 px band):
  drawn jump 10 px -> 0 past fizzSpeed dt.
- A held contact's wall flag follows the corrected position (FIZZ_WALL_TOL 1e-3 px); selftest 'wall flag'.
- Board (user): arrivals pushed existing foam aside / down. Interim seniority + 0.2 cap (371e8d8) superseded by the
  surface model (docs/tilted-fizz-surface-model.md points 1-3): drift v = k_w U_i [b_perp + sigma (b_u - sigma . b_perp)
  / (1 + sigma^2)] (sigma_y row slope, sigma_z = B0 6t(1 - t) / w) replaces FOAM_SLIDE, approach to the deepest contact
  removed; contacts part in the plane shared equally, a step's whole in-plane move <= FOAM_PUSH (1 / 2 sqrt 2) U_i dt;
  an arrival held under a resident moves it aside by its share (FIZZ_C_HELD); nobody is pushed along the tube (seated
  within FOAM_SEAT 0.5 px follows its endpoint, the unseated rear waits). Stand 60 s, c6e77da -> new: in-plane p90 / p99
  0.50 / 1.25 U -> 0.35 / 0.35 U; foam-steps sinking > 5 px/s 4.2 % -> 1.5 % (all endpoint-following, worst drawn 1.29
  -> 0.55 px a step; lives > 10 px 0 / 0, worst 8.6 -> 4.3 px); foam count 6.4 / 7.4 -> 6.3 / 7.1; newcomer settle
  median / p90 0.68 / 1.14 -> 0.78 / 1.46 s; waits >= 0.5 s 44 -> 118 (queues under the front cap).
- Lone ridge foam (selftest 'lone'): centred waits; offsets slide round at the frictionless rate (tau 0.21 s measured,
  0.196 s analytic): slow when near-centred, not stuck; no kernel change.

## Point 9 perf: bit-exact pass on the vertical kernel (2026-11-22, lcd316@320w8-8, board look, stand pose)
- Board profile (-DFIZZ_PROF, per step both tubes, h 125 / 13-16 foam, m 22 / 10): settle 62 %, bubble loop 26 %. Placements
  ~200 a step (~10 a foam bubble: drift, 3 sweeps of a jammed cap, held arrivals), ~2000 cycles each; the endpoint support
  (whole-disc rows, one root a row) ~800 cycles a call, ~280 calls. Division ~50, sqrtExact ~33 cycles; IRAM placement of
  the lambdas / sqrtExact and internal RAM for the fizz data gained little (I-cache / PSRAM not the bottleneck).
- Exact skips, same answers bit for bit (host contract-off: all sim jobs, self-tests and 80 presets identical):
  fizzEndLow (root-free lower bound of uc / ut: h <= r - dy^2 / 2r, slack 1e-2) gates every support whose decision it
  settles (zone, other end, placement un = A, eLo, glide, seat); fizzEndLowBox, once a step per foam bubble, bounds the
  target over its in-plane box (FOAM_PUSH U_i dt); the least surface over all rows skips discFitLow for the column;
  fizzLevelOf by comparisons away from the thresholds; 1 / a per size class; brute-force packing up to 24 foam.
  Host asserts (every bound <= the exact value, all jobs + the X sequence, contract off and fma): no failure.
- Board, same-session A/B (bench --runs 3): fizz step 3.09 -> 2.46 ms, 44.5 -> 45.6 fps (fizz_bench 120 / 240 / 480:
  3.80 / 17.2 / 34.6 -> 3.17 / 10.8 / 42.0 ms, 480 noisy at the 5-step cap); IRAM -128 B, DRAM 0, PSRAM +8.0 KB (FoamWork: box bounds,
  size-class table). The placement rewrite moves the board's madd.s contraction: X sequence identical for 238 frames, the
  minutes tube differs from frame 239 (last bit); parity lines unchanged. ~1 ms needs a behaviour change (KAIZEN).
