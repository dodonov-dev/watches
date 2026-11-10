# Physical materials: how a liquid's properties become a look

Status: contract and formula table (plan block A, 2026-09-25). Implementation follows in
`sim/src/material/` (blocks B–D). The 2026-09-18 standalone optical renderer (`sim/physical.html`,
`firmware/src/physical/`) is retired 2026-09-25; its cylinder trace, Fresnel and Beer–Lambert code
(now `sim/src/material/optics/`) is the colour model here.

## Architecture

A physical preset is a **material** (`spec/material-schema.json`: 30 numeric properties with units,
bounds and defaults — optics, fluid, wetting, gas, vessel, lighting) plus a **design** object (the
allowlisted legacy `Params` keys for layout, backing, marks and watch behaviour, listed in the schema's
`design.allow`). `derive(material, design) → Params` (`sim/src/material/derive.ts`) is a pure,
deterministic function that fills EVERY legacy field: from the material by the laws below, from the
design by pass-through, or from a fixed policy. The result is an ordinary legacy `Params`: the existing
renderer, physics, firmware, `gen_params.py`, `dump:presets`, `e2e.sh` and screenshots all apply
unchanged, and the derived `Params` must pass the unchanged coherence rules
(`sim/src/material/coherence.ts`, the rules every signature preset passes today) for the class the
material implies. There is no firmware material struct: firmware receives the derived legacy preset.

Realism by design means: the user cannot reach an unrealistic corner because there is no knob for
it. One viscosity drives every viscosity-dependent field in the same direction; colour comes from
absorption, scattering and the chord length through the real bore; glow exists only when the
material emits; a non-wetting liquid leaves no film. Absolute SI dynamics are NOT the target: the
watch's motion is deliberately slowed (gravity `freeGain` = 570 px/s²) for readability, so the dynamic
laws map physical dimensionless groups onto the legacy regime through **anchored monotone maps**
calibrated to the existing class values. Coupling and ordering are the physics; the anchors are the
watch.

### Conventions

- Units: mm, mPa·s, kg/m³, mN/m, degrees, seconds; `g` = 9.81 m/s²; the panel's nominal pitch is
  0.083 mm/px (`MM_PER_PX`), used only where the legacy code uses it (`capShape`).
- **One physical→display conversion**: the drawn tube (`tubeHeight`, design) shows the whole vessel,
  so `pxPerMm = R_px / (r + wallThickness)` with `R_px = (tubeHeight − 1)/2`. Every length or speed
  that crosses between the material and the screen uses it: wall band, bubble diameter, bubble rise,
  and the physical speed behind the legacy reference edge speed `U₀ = 25 px/s` (`FILM_FULL_PX_S`):
  `U₀_mm = 25 / pxPerMm` mm/s (2.59 mm/s at the default 54 px tube: `pxPerMm` = 26.5/2.75 = 9.64).
- Reference bore `r₀` = 2.25 mm (the default), used only in the viscosity-class coordinate.
- Optical targets are computed in linear light and encoded **once**. Two encodings are named
  explicitly: `enc01(v)` = sRGB transfer, 0..1, and `enc255(v) = 255·enc01(v)`, 8-bit levels. The legacy
  palette (`buildPalette`, render.ts:83–193) mixes and scales *encoded* 8-bit RGB, so every palette
  pre-image below is written in `enc255` units; luma-based weights use `enc01`. Residuals are stated in
  8-bit levels (≤ 5 levels = 5/255). The panel dimmer `brightness` and the per-layer trims stay design.
- `anchored(x, [(x₀,y₀), (x₁,y₁), …])`: monotone piecewise-linear interpolation, clamped at both
  ends. Anchor tables list the coordinate first.
- `classClamp(value, range)`: after a law, the value is clamped into the coherence range of the
  inferred class. Where consecutive class ranges do not touch (e.g. `freeDamp` watery ≤ 1.5, medium
  ≥ 1.5, viscous ≥ 6) the law has a documented **jump at the class threshold**; there is no
  interpolation through forbidden values.

### Dimensionless coordinates (SI inside)

| Symbol | Definition | Used for |
|---|---|---|
| `μ_eff` | `μ · (1000/ρ) · (r₀/r)²` — kinematic viscosity relative to water in the reference bore, in mPa·s-equivalents | viscosity class, every drag/damping law (`x_μ = log10 μ_eff`) |
| `Oh` | `μ / √(ρ γ r)` (Ohnesorge) | end bounce, wobble inertia |
| `Ca₀` | `μ U₀ / γ` (capillary number at the reference speed) | dynamic contact angle, film |
| `lc` | `√(γ / (ρ g))` mm (capillary length) | meniscus head/sag (`capLength`) |
| `v_b` | `2 ρ g r_b² / (9 μ)` (Stokes rise of a bubble of radius `r_b`, Δρ ≈ ρ), converted to px/s | bubble speed |
| `T` | luma-weighted two-flux transmittance of the centre chord (below) | opacity class, `liquidTransparency` |
| `E_lum` | luma of the emission RGB | emissive class, glow |

### Class inference (drives the coherence rules and the class clamps)

- viscosity: `phase = plasma → plasma`; else `metallic → metal`; else by `μ_eff`: `< 2.5 watery`,
  `2.5 ≤ μ_eff < 500 medium`, `≥ 500 viscous`. The anchor coordinates of every `x_μ` law sit exactly
  at the thresholds, `x₁ = log10 2.5 = 0.39794` and `x₂ = log10 500 = 2.69897` (written 0.398 / 2.699
  below), so a class-shared boundary value is reached exactly where the class changes. (Water 1, champagne 1.5, blood 3.8, milk 2.9,
  malt 3, olive oil 92, honey 7000; liquid oxygen 0.17, mercury 0.11 but metal.)
- opacity: `metallic → opaque`; else by `T`: `≤ 0.12 opaque`, `0.25–0.55 translucent`, `≥ 0.7 clear`.
  **Clear is for colourless liquids only** (PRESETS.md: a tinted liquid mixed toward the back turns
  khaki, so tinted ones are translucent): the class is clear only when the channel spread of the
  two-pass transmittance `max_i Tr_i² − min_i Tr_i² < 0.15`; otherwise `T = min(T, 0.55)`. `T` inside
  a gap (0.12–0.25, 0.55–0.7) is **snapped to the nearer band edge**, ties up — except that when the
  `T_max` bound (below) is the binding one the snap goes **down** so the composite stays attainable
  (a documented discontinuity inherited from the checker's disjoint bands; noted in KAIZEN).
- emissive: `E_lum > 0.02`. wetting: `contactAngle + contactHysteresis < 90` (concave);
  non-wetting: `contactAngle − contactHysteresis > 90`; a band that includes 90° is **rejected**.
- gas: `gasMode` directly (none / carbonated=dissolved / boiling / trapped).

### Exception precedence and rejections (visible errors, never a silent fix)

Precedence: **plasma** overrides everything (non-wetting, no gas, no slug, no film, no residue,
self-lit); then **metallic** (opaque conductor, metal dynamics class); then the dielectric laws.
Non-wetting is a surface property independent of the bulk class: a non-wetting non-plasma liquid
takes the checker's non-wetting spring band (350–800) whatever its viscosity, keeps its viscosity's
damping, and has no film or residue.

Rejected inputs: 1. a contact-angle band `θ ± h` that includes 90°. 2. `gasMode = dissolved` with a
non-watery class (carbonation implies watery). 3. plasma with `E_lum ≤ 0.02`, with `gasMode ≠ none`,
or with a design `freeLiquid = true` (plasma cannot slide; the design must say so, it is not silently
overwritten). 4. an emissive liquid with a backing brighter than luma 16 — the displayed backing, i.e. `tubeBack` and, when `tubeBackGradient ≠ 0`, `tubeBack2` too. 5. a clear
class with emission (the checker's clear `glassOverLiquid ≥ 0.5` and emissive `≤ 0.4` cannot both
hold; a glowing clear liquid is a translucent one with low absorption). 6. no illumination and no
emission (`E_l < 0.01` and `E_lum ≤ 0.02`: nothing to render). 7. any design key outside
`design.allow`, any non-finite or out-of-range property, a layout outside the panel (existing
`tubeLayout` limits). 8. sprite digits that do not fit the tube (`digitBottom + 8·digitScaleY >
tubeHeight`) — reported, not resized. 9. **overexposed**: the derived `liquid` reaches luma ≥ 248 levels (after the pre-image and emission), or the highlight floor cannot fit below 255 — lower `exposure`, `lightIntensity`, `ambient` or emission, or darken the backing. 10. **unrepresentable body**: the composite residual exceeds 5 levels after every bound and snap (a body brighter than the legacy mix can carry; lower `exposure` or the backing contrast). 12. **unattainable rim / wall shading (N levels)**: the solved side-light rim misses the wall sample by more than 5 levels (after the RGB565 round trip) even at the maximum `rimLight` gain 4 (see the `rimLight` row); or a channel sits ABOVE the wall target with the rim at 0 by more than one RGB565 step (8 levels) — the rim can only add light, and the luma-only `shadeDepth` fit magnified by quantisation is allowed one step (glow's blue), no more: an opaque class needs `shadeDepth ≥ 0.5`, so a flat-lit scattering body under a strong ambient (milk, ambient 1, exposure 0.5) is rejected rather than shown 25 levels off. 11. **design contradicts the material's realism rules**: `derive` runs `coherenceIssues` on the complete result for the inferred classes and rejects with those messages (a free slug switched off for a liquid, a sprite font that does not fit, on-top marks invisible against the backing, out-of-range trims…); design fields are never rewritten. Design values are validated against their `PARAM_META` bounds (and explicit non-negativity for the stiffness/rate fields) before derivation, and a current-version material/envelope with unknown keys is rejected — unknown keys are only dropped by an explicit older-version migration step. Rear marks are allowed behind every class; their legibility floor
`markContrast` (design) may fake at most what the liquid lets through, `markContrast ≤ 120·T` (≤ 14 behind an
opaque liquid, where they show dimly through `T ≤ 0.12`), and a clear liquid's must be ≥ 16.

## Colour model (two-flux Kubelka–Munk per channel, on the phase-1 cylinder trace)

Per channel `i` with absorption `K_i` (1/mm), reduced scattering `S` (1/mm), a chord length `d` (mm)
and a backing reflectance `Rg` behind the layer: `a = 1 + K/S`, `b = √(a² − 1)`, `x = b·S·d` (capped
at 50), `R(d, Rg) = (1 − Rg·(a − b·coth x)) / (a − Rg + b·coth x)`,
`Tr(d) = b / (a·sinh x + b·cosh x)`. **Limit branches** (executable, not limits taken by hand):
`S < 10⁻⁶`: Beer–Lambert `Tr = exp(−K d)`, `R = Rg·exp(−2 K d)`; `K < 10⁻⁹` with `S > 0`:
`Tr = 1/(1 + S d)`, `R = (Rg + S d (1 − Rg)) / (1 + S d (1 − Rg))`; `d ≤ 0`: `Tr = 1`, `R = Rg`.
(`S` is the *reduced* coefficient `μs(1−g)`: blood ≈ 1/mm with `K` ≈ (1, 20, 25) → `R∞` ≈ (0.27,
0.02, 0.02); milk `S` ≈ 3, `K` ≈ 0.001 → `R∞` ≈ 0.97.)

Chords come from `traceRow(y, wet, p)` (phase-1 `geometry.ts`, now `sim/src/material/optics/geometry.ts`): the centre
row (`d_c` ≈ 2r after refraction) and the wall sample at `u = 0.85` of the bore. **Display row of a
bore position**: the drawn tube spans the outer radius, so bore position `u` sits at row offset
`d(u) = u · r / (r + wallThickness)` from the centre (0.695 at the defaults, row fraction
`t = (1 + d)/2` = 0.848) — the same `d` feeds the backing gradient, the palette's chord factor
`(1 − √(1 − d²))²` in the `liquidThin` fit, and the `buildPalette` assertions. The panel row at
`y = 0.85 r` sees a ray refracted toward the axis, so its liquid chord is `d_w = 2r·√(1 − (0.85/ior)²)`
(1.54 r for water, 1.64 r for honey) — the traced chord, not the geometric one at that height; the
same ray supplies `F₃`/`F₄` below.
`traceRow` also gives the Fresnel transmission product `F_t` of the four interfaces. Illumination
(all × `exposure`): backing irradiance `E_b = backingLight(p)` (phase-1 `lighting.ts`, now `sim/src/material/optics/lighting.ts`: ambient +
projected light), liquid-side irradiance `E_l = ambient + 0.5·lightIntensity`.

Backing per sample: the palette blends each row against its own backing
`back(t) = mix(tubeBack, tubeBack2, m(t))`, `m` = `t` (gradient 1), `1 − |2t − 1|` (2), `|2t − 1|` (3),
0 (0), `t` = row fraction. The centre sample uses `t = 0.5`, the wall sample `t = (1 + d(0.85))/2` (0.848 at the defaults); the derived
`liquid` is fitted at the centre row, and rows with a different backing take the palette's own per-row
mix (more backing where the backing is brighter — the physically right direction, not a fitted one).
A gradient-backed fixture checks the centre-row residual.

Body radiance per channel at a sample of chord `d` and bore position `u`, from the light that
entered through the front wall along the **traced path**:
`C_i(u) = E_l·R_i(d, 0) + lin(back_i(t))·[R_i(d, 1) − R_i(d, 0)] + E_l·F_far(u)·Tr_i(d)² + C_side,i(u)`,
The backing term is the two-flux response to a white ground, `R(d, 1) − R(d, 0)`, scaled by the DISPLAYED backing colour `lin(back)`: the legacy compositor shows the dry backing at its hex brightness, so that colour is the ground truth for the wet side too (lighting the backing by `E_b·albedo` made a white backing derive darker under a colourless liquid than beside it, and a reflectance `Rg = lin(back)/E_l` capped at 1 still lost 30 % on white). `E_b` (`backingLight`) is not used by the colour model. The first term is the backing seen through the
liquid. The second is the light the far interfaces return: `F_far = 1 − (1 − F₃)(1 − F₄)` with `F₃`,
`F₄` the Fresnel reflectances at the traced ray's actual incidence on the far liquid→wall and
wall→air interfaces (`traceRow` exposes them; a face-on ray never reaches total internal reflection
there, so this term is 4–6 % at every row). **`C_side` is a separate, calibrated off-axis
approximation**, not part of the primary trace: environment light entering through the wall band from
outside the traced path lights the grazing rows through a thin chord,
`C_side,i(u) = exposure · (ambient + 0.25·lightIntensity) · u⁴ · Tr_i(d(u))` (the `u⁴` confines it to
the rims; the 0.25 share is calibrated so water gives the legacy `glassWallGlow` base 0.25). It is what
lights the rims of a tinted liquid on a dark ground. Emission `E_i` is NOT part of `C`; it is added
after the palette inversion (below).

| Legacy key | Law |
|---|---|
| `liquidTransparency` | Front-lit marks and backing are illuminated *through* the liquid and seen *through* it, so the legacy "how much shows through" is a **two-pass** quantity: `T_lum = luma(F_t · Tr_i(d_c)²)` (`F_t` covers the four interfaces once: two in, two out). The palette mixes the raw backing by one scalar, so it cannot show a colour-filtered backing; the largest transparency at which every channel of the composite stays attainable is `T_max = min_i t_i / back_i(0.5)`, `t_i = enc255(C_i(0) + E_i)` the `liquid` row's pre-image target (emission included), over channels with `back_i ≥ 8` levels (∞ on a dark backing). The pre-image also has an upper feasibility bound (no channel may need more than 255 levels): `T_up = min_i (255 − t_i) / (255 − back_i(0.5))` (so a bright emitter over a dark backing is held near opaque: the mix cannot show `C + E` through a transparency; glow 0.35 → 0.04) over channels with `back_i < 255`. `T = min(T_lum, T_max, T_up)`, then band-snapped as above (down when a bound binds). If the composite residual of the snapped result still exceeds 5 levels (opaque/translucent, non-plasma) the material is rejected (10) rather than shown wrong. A tinted liquid on a light backing therefore derives to a low transparency with the full colour in the body — the pattern the 2026-09-23 presets (pinot, cuvée) used by hand — and the composite residual stays ≤ 5 levels by construction. Metallic: 0. Plasma: 0.5 fixed. |
| `liquid` | Encoded-space pre-image of the palette's `mix(liquid, back, T)` (with `liquidBright` 1), 8-bit units: `liquid_i = clamp((enc255(C_i(0)) − T·back_i(0.5)) / (1 − T), 0, 255)` for the opaque and translucent classes (and metallic, `T` = 0), rounded to 8 bits and then **settled on the real palette**: the palette truncates the composite to RGB565, so a sub-level loss from rounding the pre-image can cross a 5-bit step (8 levels) the target does not (olive oil on #110b03: red 59.46 → 59 put the centre row at 33 against a target of 41); per channel, of the rounded value and its ±1 neighbours (±1 always outweighs a rounding loss of ≤ ½·(1 − T)), the one whose body-only centre row (`rimLight` 0, RGB565) is nearest `q565(enc255(C + E))` is taken, ties keeping the rounded value — before `rimTint` is fitted over it; the **clear class takes `enc255(C⁰_i(0))` directly**, where `C⁰` is the backing-independent body `E_l·[R_i(d, 0) + F_far·Tr_i²] + C_side` (the legacy mix adds the backing itself; dividing by `1 − T ≤ 0.3` is ill-conditioned and the mix cannot show a haze brighter than `(1−T)·255` anyway: that attenuation is an accepted, documented residual). The target includes the emission summed in linear light, `enc255(C_i + E_i)` (the legacy mix then shows `C + E` exactly; an emitter that clips is rejection 9); plasma is the exception: `liquid = enc255(E)` with no pre-image, the legacy xenon convention; emissive: the encoded value ÷ 1.3 (the `liquidBright` trim below, applied to `liquid`, `liquidLo` and `liquidHi` alike). The composite residual `\|((1−T)·liquid + T·back) − enc255(C + E)\|` (before the ÷ 1.3 trim) in 8-bit levels is reported per fixture and must be ≤ 5 levels for opaque/translucent fixtures. Metallic: `C = metalReflectance · E_l · 0.6` (grey conductor under diffuse light; the mirror term is the highlight). Plasma: `C = 0`. |
| `liquidLo` | Same rule (pre-image, or direct for clear) applied to the shaded body `enc255(C_i(0) · f_lo + E_i)`, `f_lo = max(0.15, ambient / max(10⁻⁶, ambient + lightIntensity))` (emission is not shaded); plasma `enc255(E_i)` directly (= `liquid`, no shading); emissive ÷ 1.3. |
| `liquidThin` | Fit of the palette's wall desaturation `mix(c, grey(max channel), liquidThin·(1−chord)²)` to the wall sample. The palette's chord is the refracted one, `√(1 − (u·R/(n·r))²)` at display offset `u` (a ray gets no closer to the axis than `u·R/n`; `n` = `THIN_IOR` 1.333, legacy params carry no index; `R/r = 1/(1 − 2·glassWall/H)`), so the wall floors it (0.54 at the silhouette for 4 px on a 72 px tube). `liquidThin = clamp((1 − sat(enc01 C(0.85)) / sat(enc01 C(0))) / (1 − paletteChord(d(0.85)))², 0, 1)`, `paletteChord(d) = √(1 − (d·(r + wall)/(1.333·r))²)`; 0 when `sat(enc01 C(0)) < 0.05`, when a colour is black (guarded normalisation), or metallic. |
| `shadeDepth` | Fitted to the wall sample: the palette darkens a row by `shadeDepth · (1 − λ(d))` under the world-up light, `λ(d) = cos(asin d)` (Lambert at the row's surface normal; 0.72 at `d` = 0.695), and physically only the *scattered* light is Lambert-shaded (a backlit transmission is not). The wall body without side light is `B_w = E_l · [λ(d)·R_i(d_w, 0) + (R_i(d_w, Rg) − R_i(d_w, 0)) + F_far·Tr²]`; `shadeDepth = clamp((1 − luma(B_w) / luma(B_c)) / (1 − λ(d)), class range)` (opaque 0.5–0.95, translucent 0.4–0.85, clear 0.3–0.55; class minimum when `luma(B_c)` = 0). A scattering opaque body → 0.95; a clear or backlit one → the class minimum. Metallic 0.95, plasma 0.85. |
| `liquidHi` | The specular is the light's colour added **over the body**, summed in linear light and encoded once: `enc255(clip(C_b + L_hi · (0.7·white + 0.3·thin) + 1.5·E))`, `C_b` = `C⁰(0)` for clear, else `C(0)`; `thin` = `C(0.85)` normalised to luma 1 (white when its luma < 10⁻⁴). Because the palette mixes `liquid` with the backing before adding the highlight, the checker compares the pre-image with the highlight; `liquidHi` is therefore **floored** at `luma(liquid) + 8` levels (scaled up uniformly), and a floor that would exceed 255 is rejection 9. Clear liquids get a neutral highlight (checker: saturation < 0.2). Metallic: white. Emissive ÷ 1.3. |
| `highlightH` | Rows of cylinder whose normal reflects the source into the viewer: `round(2 · R_px · sin(lightSize/4) · cos(lightElevation/2))`, ≥ 3 px, ≤ H/3 (30° source, 60° elevation, 54 px tube → 6 px). |
| `highlightSharp` | 2 (tent² ≈ the Gaussian source). `highlightInset` 0. |
| `highlightBright` | Specular radiance `L_hi = min(1, F(θ_i; 1 → wallIor) · lightIntensity · L_SPEC)`, `θ_i = lightElevation/2`, **`L_SPEC = 12`** (a lamp's radiance relative to a white diffuse surface, calibrated so `lightIntensity` 1 gives the legacy base band 0.35–0.55: F(30°) = 0.04 → 0.48). Mix weight that adds it over the body: `clamp(L_hi / max(0.05, 1 − luma(enc01 C(0))), 0, 1)` (normalised luma, 0..1). Metallic: `min(1.3, metalReflectance · lightIntensity · L_SPEC)` (metal is exempt from the ×liquidBright ≤ 1.3 rule). |
| `glassHi` | Neutral light colour `#dfe6ea`. `glassHiBright = 0.55·L_hi`, `glassReflect = 0.25·L_hi`, `glassRim = 0.45 + 0.35·L_hi` (grazing Fresnel → 1, clipped to the legacy look), `glassBody = 0.4·ambient`. |
| `glassWallGlow` | The legacy neutral wall band (the side light piped along the glass; the palette lays it on the dry band, and over the contents by `1 − wallWet` — a wetted wall frustrates the piping and the near index-matched liquid fills the band, its side light being `rimLight`): `clamp(0.6 · exposure · (ambient + 0.25·lightIntensity), 0, 1)`, a property of the glass and the lighting, not of the contents (0.27 for every fixture, metallic and plasma included). |
| `wallWet` (**new legacy Param, v25**, mirrored in `render.cpp` / `gen_params.py` / presets) | How far the contents fill the wall band and frustrate its piped glow. A ray at height `y` reaches contents of index `n` only if `y ≤ n·r` (the invariant `n·ρ·sin θ`; it must first reach the bore, so `n ≤ wallIor`): the contents fill `(min(ior, wallIor) − 1)·r` of the wall, `wallWet = clamp((min(ior, wallIor) − 1) · innerRadius / wallThickness, 0, 1)` (water, oil, honey 1; liquid oxygen 0.99; a gas 0). Metallic 1 (the mirror surface keeps the liquid look). The palette: over the contents the glow is scaled by `1 − wallWet`, and the contents end at display `liqU = wallU + wallWet·(1 − wallU)` (`n·r`): past it each liquid row is the empty tube's row (the wall's internal reflection), ramped in like the bore edge, weight `1 − liqT`, `liqT = 1 − exp(−(liqU − |u|)/0.04)` inside (the ray grazes the inner wall there) — a gas's band is the empty tube's (`liqU = wallU`, the bore's `dryT` ramp), its column seen where the back would be. 1 in every legacy preset but Xenon (0); at 1 and 0 the band is byte-identical to v24 (the 2026-11-04 edge only changes 0 < wallWet < 1, which blended `(1 − wallWet)·(1 − dryT)` uniformly). |
| `rimLight`, `rimTint` (**new legacy Params, v24**, mirrored in `render.cpp` / `gen_params.py` / presets) | The side-lit rim of a tinted liquid on a dark ground: the palette adds `rimLight · u² · rimTint` (8-bit, clamped) to every liquid row after the transparency mix and before the highlight and glass, `u` = row offset from the centre (0..1); `rimLight` is a gain 0..4 (the sum clamps at 255, so a gain above 1 only extends the reach of the term at the sample row, whose `u²` shrinks with a thick wall: `u_w = 0.85·r/(r + wall)`). Zero in every legacy preset (byte-identical rendering, migration default). Derivation: for dielectric liquids with side light the gain is the smallest of 1, 2, 3, 4 at which no channel of the solved tint saturates (0 for metallic and plasma), and `rimTint` is **solved on the real palette**: `derive` builds the body-only `buildPalette` (the params with `rimLight` 0, the specular/glass overlays and `ambientLight` zeroed, `brightness` 1: the rows `check:materials` reads), reads the wall row `P_w` at `y = round(yc·(1 + d))`, and estimates `rimTint_i = clamp((target_w,i − P_w,i) / u_w², 0, 255)` per channel (`u_w` the palette's row coordinate there, ≈ `d`), `target_w` = `enc255(W_i + E_i)` after the RGB565 round trip, where `W = B_w + E_s·u⁴·Tr(d_w)` is the full wall sample with its scattered share Lambert-shaded (the `shadeDepth` row's `B_w` plus the side light; metallic `λ·C`). `P_w` is itself RGB565-quantised (5-bit blue: 8-level steps), so each channel is then settled on the rendered row: the integer tint whose RGB565 channel is nearest the target (the row is monotone in the tint; bisection). The fitted row is then measured on the real palette (both sides after the RGB565 round trip): a residual above 5 levels in a channel the rim answers for (a vessel whose wall leaves the rim term no reach, e.g. olive oil in a 0.5 mm bore with a 1 mm wall: 25 levels at gain 4) is **rejection 12, unattainable rim** — never a silent saturation; a channel already above the target with no rim (tint 0) is the body shading's miss, which an additive rim cannot lower: it is reported (`DeriveReport.rim.bodyOver`, printed by `check:materials`), not rejected (glow: blue one RGB565 step, 8 levels, over). The fit is exact at the sample (0 levels on every fixture, including olive oil with a 1 mm wall); at the silhouette the rim is `1/u_w²` ≈ 2× brighter, as the side light is. Water (#0a0e10) gain 2, (131,131,125) (at gain 1 it clips: (255,255,250)); olive oil with a 1 mm wall gain 2, (147,154,100); olive oil (194,196,111); honey (184,177,61); cola (197,185,140); pinot on parchment (122,71,82); blood (0,0,0), milk (10,10,10): ≈ 0 (no side light through an opaque body). |
| `glassOverLiquid` | Share of the empty wall's specular that survives over the liquid: an empty tube reflects at the outer and inner wall surfaces, a filled one at the outer and the (index-matched) wall–liquid interface: `ratio = (F(1→wallIor) + F(wallIor→ior)) / (2·F(1→wallIor))` at normal incidence (water 0.54, honey 0.50, mercury 1); relative to the body's own light: `ratio / (1 + 2·E_lum)`; then **clamped to the inferred class**: emissive `≤ 0.4`, clear `≥ 0.5` (rejection 5 removes the overlap). The grazing rim (`glassRim`) is not scaled by it: that is the outer surface's reflection, the same over the liquid as over the dry glass. |
| `glassWall` | Projected wall band: `wallThickness · pxPerMm` (0.5 mm, 54 px tube → 4.8 px). |
| `lightPhys` / `lightAngle` | Non-emissive: 1 (world-up light from the IMU) / `lightElevation/2`. Emissive: 0 / `lightElevation/2` (self-lit; the checker's binary rule — KAIZEN: a weakly self-lit liquid would want a share). |
| `ambientLight` | 0. The legacy `ambientize` desaturates bright colours toward white as a stand-in for room reflections; the derived highlight, rim and thin-chord colours already contain the white light, so applying it again turned tinted rims grey (cola came out beige). |
| `liquidBright`, `brightness` | `liquidBright = 1`; emissive: 1.3 with the derived encoded `liquid`/`liquidHi`/`liquidLo` ÷ 1.3 (the palette scales encoded values, so the product is unchanged). `brightness` design. |
| `tickLens`, `bottomLens` | Depth warp of rear marks seen through the liquid cylinder grows with its index: `min(1, 0.45·(ior − 1)/0.333)` (water 0.45, oil 0.63). The dry-side and rod fields are design (rod calibration). |
| `liquidIor` (**new legacy Param**, mirrored in `render.cpp` / `gen_params.py` / presets) | The contents' index `ior` (gas / plasma 1). The rear wall's view-angle parallax behind the contents is the behind-air one (`rearParallax`, design) / `liquidIor`: the ray through the front vertex bends to 1/n of its angle (along the tube a slab; across it the cylinder, whose lens is already the source-row warp). Legacy presets 1.333 (water). |
| `bubbleRim` | `enc255(min(1, E_s·Tr(r) + 0.35·C⁰(0)))` with the backing-free body `C⁰`, `E_s = exposure·(ambient + 0.25·lightIntensity)` (the side-light irradiance of the rim term) and `Tr(r)` the Kubelka–Munk transmission over half the bore (the side light is filtered by the liquid on its way to the bubble: a tinted liquid's bubbles carry its colour, a colourless one's stay white). A bubble's rim totally reflects the light inside the liquid, not the backing behind it: it reads darker than a light backing and brighter than a dark one (the former `0.65·white` made bubbles vanish on white). The renderer shades the ring by the liquid's body lighting at that row (not the composited row: backing, surface highlight and glass do not light a bubble), so on a dark backing a bubble is lighter than the liquid. Frizzante: luma 219 on #ffffff, 181 on #000000. `bubbleDark = 1 − (1 − F)²`, `F = ((n − 1)/(n + 1))²`: the core is a clear window that loses only the reflection at its two surfaces (water 0.04, oil 0.07; the former `0.25 + 0.5·(1 − T)` drew dark cores). |

## Edge and glow

| Key | Law |
|---|---|
| `edgeGlow`, `glowStrength` | Non-emissive: a caustic of the backing light focused by the meniscus, `glowStrength = min(0.25, 0.08 · lightIntensity · T)` (ink 0, water 0.07), `edgeGlow = 19` px. Emissive: `glowStrength = anchored(E_lum, [(0.02, 0.4), (1, 0.8)])`, `edgeGlow = 18 + 16·min(1, E_lum)` px. Metallic non-emissive: 0/0. |
| `frontBright` | Bright convex cap: metallic 20, emissive `round(16 · min(1, E_lum) + 4)`, else 0. |
| `edgeLightGain` | 0.55 (tilt changes the light at the cap; fixed policy). Emissive 0.3. |
| `edgeSoft` | 2.4 px (the contact line seen through the rod); non-wetting 0 (a sharp bead). |
| `surfaceBand` 0.35, `surfaceRim` 0.45, `surfaceWidth` 4, `surfaceTone` 0 | Fixed to the current meniscus look (2026-09-23 presets). |
| `surfaceFill` | `clamp(1 − 0.9·T)` (a clear liquid's dish is see-through, an opaque one is filled). `surfaceBlick = 0.9·highlightBright`. |
| `cornerR` | design. `meniscusLens` design (rod). |

## Meniscus and dynamics (all through `μ_eff`, `Oh`, `Ca₀`, `lc`)

Class anchors are the legacy class partials (watery / medium / viscous / metal in `params.ts`) and
the coherence ranges. `x_μ = log10 μ_eff`; class thresholds at `x_μ = 0.398` (2.5) and `2.699` (500).

| Key | Law |
|---|---|
| `contactAngle`, `contactHyst` | Pass-through of the material pair. Plasma: 100 / 0 fixed. |
| `contactDyn` | Cox–Voinov at the reference speed: `θ_d³ = 9·Ca₀·ln(L/l)` with `ln(L/l) = 9.2` (10⁴ scale ratio), `contactDyn = min(90, deg(∛(9·Ca₀·9.2)))`. `Ca₀ = μ·U₀_mm/γ` with `U₀_mm = 25/pxPerMm`. Water 8.2°, blood 14.1°, olive oil 47°, honey 90° (clamped), mercury 5.1° — the legacy 8 / 15 / 40 / 90 / 3. Plasma 0. |
| `capLength` | `lc · pxPerMm · 0.083`: `capShape` takes the Bond number on the drawn bore `boreR = (tubeHeight − 1)/2 − glassWall` px (the contact ring sits on the inner wall), so the ratio `(r/lc)²` is preserved under display scaling. Water 2.17, oil 1.51, mercury 1.53, honey 1.79 (54 px tube). |
| `freeGain` | 570 (watch gravity, every liquid). `freeHomeK`, `readTilt*`, `playHold`, `freeLiquid` design; plasma forces `freeLiquid = false`. |
| `freeDamp` | `anchored(x_μ, [(−1, 0.5), (0, 0.8), (0.398, 1.4) ∣ (0.398, 1.6), (1, 2.5), (2.699, 4) ∣ (2.699, 6), (4, 9), (5, 14)])` (∣ = class jump), then class clamp (metal 0.8–1.5). Water 0.8, blood 1.87, milk 1.67, oil 3.35, honey 8.65, mercury 0.52 → 0.8 (clamped). |
| `freeBounce` | `anchored(log10 Oh, [(−3.5, 0.55), (−2.6, 0.2), (−2.0, 0.1), (−1.0, 0.03), (−0.5, 0)])`, class clamp. Mercury 0.51, water 0.20, blood 0.10, oil 0 → 0.05 (clamped), honey 0. |
| `meniscusK` | `base(x_μ) · √(γ/72 · 1000/ρ)` (square root of the capillary frequency ratio `γ/(ρ r³)` at fixed r), `base = anchored(x_μ, [(0, 475), (0.398, 420) ∣ (0.398, 340), (2.699, 210) ∣ (2.699, 140), (4, 90), (5, 60)])`; metal and every non-wetting liquid: base 650, clamped to 350–800 (metal 500–800); plasma 400 fixed; class clamp. Water 475, honey 79, mercury 500 (clamped up). |
| `meniscusDamp` | `anchored(x_μ, [(−1, 4), (0, 8), (0.398, 14), (2.699, 24) ∣ (2.699, 26), (4, 34), (5, 50)])`, class clamp (metal 8–16: mercury 4.2 → 8). Plasma 30. |
| `meniscusInertia` | `anchored(x_μ, [(0, 3), (2.699, 2), (5, 1)])`; metal 4; plasma 0. |
| `angleTiltGain` | `anchored(x_μ, [(0, 6.5), (0.398, 5), (2.699, 3) ∣ (2.699, 2.5), (4, 1.5), (5, 0.5)])`; metal 2; plasma 0.5. `angleMax` 6 (plasma 2). |
| `angleGyroGain` | `anchored(x_μ, [(0, 0.42), (0.398, 0.30), (2.699, 0.15) ∣ (2.699, 0.12), (4, 0.06), (5, 0.02)])` (0.30 is valid in both the watery and the medium band, so the class change is continuous); metal 0.4; plasma 0.03. |
| `fillK` 756, `fillDamp` 40, `fillSloshGain` 5.5, `angleK` 207, `angleDamp` 17.6 | Fixed (the pinned-column caps in `physics.ts` bound them anyway). Plasma: 260 / 22 / 0.5 / 300 / 26. |
| `acrossK` 200, `acrossDamp` 20, `acrossGyroGain` 0, `shakeGain` 0, `deadzone` 0, `accelLpHz` 15.2, `gyroHpHz` 5, `gyroDeadzone` 31, `gyroMax` 470, `inputGain` 1 | Fixed IMU policy (the 2026-09-23 presets' values). |

## Film and residue (wetting liquids only; non-wetting and plasma: `wetFilm` 0, `traces` off)

| Key | Law |
|---|---|
| `wetFilm` | Landau–Levich: the deposited film grows as `Ca^(2/3)`; the legacy value is the drawn trail length, so `wetFilm = anchored(log10 Ca₀, [(−5, 8), (−4.5, 10), (−3.9, 15), (−2.3, 18), (−1, 26), (0, 30)])`, class clamp. Water 10.5, blood 15.3, oil 18.8, honey 28.3. |
| `traces` | `solidsFraction > 0`. |
| `traceAmount` | `0.3 + 1.7 · solidsFraction · (1 − T)` (a stain of a dark liquid reads denser). Blood 1.0, ink 1.15, oil 0.6. |
| `traceStain` | `0.05 + 0.65 · solidsFraction`. `traceDry = clamp(dryingTime, 0.1, 2)` (the checker's watch regime; the schema allows up to 10 s and the excess is clamped, documented). |
| `traceDrain` | Gravity drain speed of a film at the thin-film cap, `ρ·g·(r/10)²/(3μ)` in px/s (r = innerRadius, × pxPerMm): water ~1600, olive oil ~17, honey ~0.2 (bounds: watery ≥ 100, viscous ≤ 20). The deposit itself needs no key: it is the wet-film law of `contactDyn`. `traceFilm = 0.05 · solidsFraction · clamp(x_μ / 2.699)` (a permanent coat needs a viscous, solids-rich liquid). |

## Gas

| Key | Law |
|---|---|
| `fizz` | `gasMode ≠ none` and not plasma. |
| `fizzSize` | Drawn diameter `2·r_b · pxPerMm` px (0.06 mm, 54 px tube → 1.16 px), bounded only by the drawable range 1–16 px (no class clamp: the size is the look's, so the bubble-radius slider is live over its whole 0.02–0.4 mm; 0.4 mm, 54 px tube → 7.7 px). The spread `fizzSizeVar` is a design key. |
| `fizzSpeed` | `anchored(log10 v_b[px/s], [(−1, 0), (0.5, 3), (1.5, 20), (2, 40), (2.5, 55), (3, 60)])`, class clamp (carbonated 30–55, boiling 45–60, trapped 0–8). `v_b` in px/s = `v_b[m/s] · 1000 · pxPerMm`. Water/0.06 mm: 76 px/s → 35; cola/0.07 mm: 89 → 38; honey/0.12 mm: 0.04 px/s → 0 (trapped band); liquid oxygen (μ 0.19, ρ 1141)/0.05 mm: 315 px/s → 55. |
| `fizzCount` | carbonated `30 + 30·gasLevel`, boiling `45 + 15·gasLevel`, trapped `round(120·gasLevel)` (a few held bubbles to a dense suspension; honey 0.04 → 5). `fizzFoamLife = foamStability`. |
| `fizzFlatRise`, `fizzEdgeRise`, `fizzDriftGain` | Scale with the rise: `s = min(1, fizzSpeed/30)`: `0.15 + 0.3 s`, `0.2 + 0.3 s`, `0.4 + 0.6 s`. `fizzAcrossGain fizzSquash fizzShadeOff fizzDepth fizzBlick` are design keys. |
| `bubble*` (spirit level) | `bubble` off; the rest at `DEFAULT_PARAMS`. |

## Ownership of every legacy `Params` key

- **Design pass-through** (schema `design.allow`): `tubeHeight hoursY minutesY tubeStack tubeGap remaining vertical cornerR lens
  lensCurve meniscusLens topLens topParallax tickDryLens digitDryLens tickParallax rearParallax rearParallaxSettle tubeBack
  tubeBack2 tubeBackGradient` all `tick*` (except `tickLens`) `ticksOnTop tickEmboss` all `digit*`
  `digitsOnTop freeLiquid freeHomeK readTiltStart readTiltEnd playHold brightness tickBright digitBright`,
  `markContrast` (the rear marks' legibility floor: bounded by the realism rules at `120·T`, clear ≥ 16; derived
  until 2026-09-26 — opaque 0, else 24 with rear marks — and the presets pin those values), and the
  fizz look `fizzSizeVar fizzShadeOff fizzDepth fizzBlick fizzSquash fizzAcrossGain` (taste, not physics: fixed
  policy until 2026-09-26; the presets pin the former values 0.5 / 0.3 / 0.7 / 0.6 / 1.25 / 1.05).
- **Derived** (tables above): `liquid liquidHi liquidLo liquidTransparency liquidThin shadeDepth
  highlightH highlightBright highlightSharp glassHi glassHiBright glassReflect glassRim glassWall
  glassWallGlow wallWet liquidIor glassBody glassOverLiquid lightPhys lightAngle ambientLight liquidBright
  tickLens bottomLens bubbleRim bubbleDark edgeGlow glowStrength frontBright edgeLightGain edgeSoft
  surfaceFill surfaceBlick contactAngle contactHyst contactDyn capLength freeDamp freeBounce meniscusK
  meniscusDamp meniscusInertia angleTiltGain angleGyroGain angleMax wetFilm traces traceAmount traceDry
  traceDrain traceStain traceFilm fizz fizzCount fizzSize fizzSpeed fizzFoamLife fizzFlatRise
  fizzEdgeRise fizzDriftGain`, and `freeLiquid`/`fillK fillDamp fillSloshGain angleK angleDamp` for plasma.
- **Fixed policy**: `v` (= `PARAMS_VERSION`), `highlightInset` 0, `surfaceBand surfaceRim surfaceWidth
  surfaceTone`, `freeGain` 570, `fillK fillDamp fillSloshGain angleK angleDamp` (liquids), `acrossK
  acrossDamp acrossGyroGain shakeGain deadzone accelLpHz gyroHpHz gyroDeadzone gyroMax inputGain`,
  `bubble` off + `bubbleW
  bubbleH bubbleGap bubbleY bubbleRollGain bubbleTiltGain` defaults.
  `derive` asserts that the union of the three sets is exactly `keyof Params`, so a new legacy field
  cannot appear without an owner.

## Fixtures (computed with the reference prototype of these laws)

Inputs common to all: bore 2.25 mm, wall 0.5 mm, wall index 1.49, light 60° / 30° / 1.0, ambient 0.2,
exposure 1, 54 px tube (`pxPerMm` 9.64), design backing as listed. Colours are 8-bit encoded levels; tolerance ±3 levels on colours and ±0.03 on the glass/highlight weights (the prototype approximated the far-interface incidence angles that `traceRow` computes exactly), ±2 % on dynamics, exact on classes, booleans and clamped values.

| Fixture | Inputs | Class / opacity | Colour | Dynamics | Film, residue, gas, glow |
|---|---|---|---|---|---|
| water | μ 1, ρ 1000, γ 72, ior 1.333, K 0, S 0, θ 20 ± 10, solids 0, gas dissolved 0.6 / r_b 0.06 / foam 4, back #0a0e10 | watery / clear, T 0.92 (two-pass 0.85² ≈ 0.72 through the liquid; the fixture's F_t·Tr² luma) | liquid (48,48,48) backing-free haze taken directly (clear class; the legacy mix attenuates it, residual accepted), liquidLo (15,15,15), liquidHi (189,190,190), liquidThin 0, shadeDepth 0.3 (was 0.35; clear class minimum), highlightBright 0.60, glassWallGlow 0.27, wallWet 1, glassOverLiquid 0.54 | freeDamp 0.8, bounce 0.20, K 475, damp 8, contactDyn 8.2, capLength 2.17, tilt 6.5, gyro 0.42 | wetFilm 10.5, traces off, fizz 1.16 px / 35 px/s / 48, glow 0.07 |
| olive oil | μ 84, ρ 915, γ 32, ior 1.47, K (0.05, 0.07, 0.45), θ 15 ± 8, solids 0.3, drying 2, back #110b03 | medium / translucent, T 0.47 | liquid (57,53,0), liquidLo (5,7,0), liquidHi (192,189,164), residual 0, liquidThin 1.0, shadeDepth 0.4, highlightBright 0.55, glassWallGlow 0.27, glassOverLiquid 0.5 | freeDamp 3.35, bounce 0.05 (clamped), K 200 (clamped), damp 20.8, contactDyn 47, capLength 1.51, tilt 3.64, gyro 0.20 | wetFilm 18.8, traceAmount 0.57, traceStain 0.24, traceDrain 17.4, glow 0.04 |
| honey | μ 10000, ρ 1420, γ 70, ior 1.49, K (0.06, 0.18, 0.7), θ 25 ± 20, solids 0.8, drying 2, gas trapped 0.04 / r_b 0.12 / foam 20, back #0c0703 | viscous / translucent, T 0.27 | liquid (44,21,0), liquidLo (9,2,0), liquidHi (199,184,161), residual 0.6 levels, liquidThin 1.0, shadeDepth 0.4, highlightBright 0.53, glassWallGlow 0.27 | freeDamp 8.65, bounce 0, K 79, damp 33, contactDyn 90, capLength 1.79, tilt 1.62, gyro 0.07 | wetFilm 28.3, traceAmount 1.32, traceStain 0.57, traceDrain 0.23, fizz 2.31 px / 0 px/s / 5 |
| mercury | metallic 1, reflectance 0.75, μ 1.55, ρ 13546, γ 485, θ 140 ± 15 | metal / opaque, T 0 | liquid (152,152,152), liquidLo (65,65,65), liquidHi white, shadeDepth 0.95, highlightBright 1.3, glassWallGlow 0.27, glassOverLiquid 1 | freeDamp 0.8 (clamped), bounce 0.51, K 500 (clamped), damp 8 (clamped), contactDyn 5.1, capLength 1.53, tilt 2, gyro 0.4 | wetFilm 0, traces off, fizz off, glow 0 |
| xenon | phase plasma, emission (0.35, 0.2, 0.9), ior 1.0, back #05020c, design freeLiquid false | plasma / translucent, T 0.5 fixed | liquid (123,95,187) = enc(E)/1.3, liquidLo (123,95,187) (was (53,39,83): emission is not shaded), liquidHi (196,176,196) (white specular + 1.5·E clipped in linear, ÷ 1.3), shadeDepth 0.85, glassWallGlow 0.27, wallWet 0, glassOverLiquid 0.4 | freeLiquid off, fill 260/22/0.5, angle 300/26/0.5/max 2, gyro 0.03, contact 100/0/0, K 400, damp 30, inertia 0 | film 0, traces off, fizz off, glowStrength 0.52, edgeGlow 23, lightPhys 0, liquidBright 1.3 |
| blood | μ 4, ρ 1060, γ 58, ior 1.35, K (1, 20, 25), S 1, θ 30 ± 15, solids 0.45, drying 1.5, back #050203, front marks | medium / opaque, T 0.000 | liquid (120,35,31), liquidLo (49,9,7), liquidHi (247,168,166), residual 0, shadeDepth 0.95 (was 0.9; scattering body, class maximum), highlightBright 0.63, glassOverLiquid 0.53 | freeDamp 1.87, bounce 0.10, K 288, damp 14.8, contactDyn 14.1, capLength 1.89, tilt 4.85, gyro 0.29 | wetFilm 15.3, traceAmount 1.06, traceStain 0.34, traceDrain 423 |
| milk | μ 2.9, ρ 1030, γ 45, ior 1.35, K 0.001, S 3, θ 30 ± 15 | medium / opaque | liquid (212,212,212), liquidLo (93,93,93), liquidHi white, T 0.00, shadeDepth 0.95 (was 0.9), highlightBright 1 | freeDamp 1.67, bounce 0.11, K 263, damp 14.2, contactDyn 13.8 | wetFilm 15.2, traces off |
| liquid oxygen | μ 0.19, ρ 1141, γ 13, ior 1.22, K (0.005, 0.002, 0), θ 5 ± 3, gas boiling 0.7 / r_b 0.05 / foam 0 | watery / clear, T 0.88 | liquid (50,51,52) haze taken directly, liquidLo (16,17,17), liquidHi (190,190,190), shadeDepth 0.3 (was 0.35), glassWallGlow 0.27, wallWet 0.99, glassOverLiquid 0.63 | freeDamp 0.57, bounce 0.35, K 400 (clamped), damp 4.9, contactDyn 8.4, capLength 0.86 | wetFilm 10.7, fizz 1 px (clamped) / 55 px/s / 56 |
| cola | μ 1.2, ρ 1040, γ 60, ior 1.35, K (0.05, 0.15, 0.35), θ 20 ± 10, gas dissolved 0.4 / r_b 0.07, back #070403 | watery / translucent, T 0.32 | liquid (52,29,5), liquidLo (12,4,0), liquidHi (196,184,170), residual ≤ 1 level, liquidThin 1, shadeDepth 0.4, glassWallGlow 0.27 |
| oil on parchment | olive oil above with back #f1e6cf | medium / opaque, T_lum 0.47 but T_max 0.133 → T 0.133 (snap 0.12) | liquid (195,169,3), liquidLo (67,55,0), liquidHi (255,246,163), residual 0 (the light backing is carried by the body, not by the mix) |
| pinot on parchment | μ 1.5, ρ 990, γ 46, ior 1.35, K (0.15, 0.65, 0.5), θ 20 ± 10, solids 0.03, back #f1e6cf | watery / opaque, T_lum 0.07, T_max 0.030 → 0.030 | liquid (129,0,14), liquidLo (49,0,0), liquidHi (253,164,169), residual 0; colour and class only | freeDamp 0.89, bounce 0.18, K 418, damp 8.9, contactDyn 9.3 | wetFilm 11.8, fizz 1.35 px / 38 px/s / 42 |

Boundary fixtures (finite output, no exception): K = S = 0; K = 0 with S = 3; S = 0 with K = 50; a
zero-length chord (`u` = 1); ambient 0 with light 0 and emission 0.3 (allowed: self-lit; at 0.5 the body, now summed with its emission in linear light, pre-images to display white and is rejection 9); black
backing with a colourless liquid (zero-colour normalisation); `E_lum` at 0.02 and 0.021 (both sides
of the emissive threshold, `glassOverLiquid` respects the class clamp on both); a
yellow liquid (K (0.002, 0.03, 2.6)) with T_lum ≥ 0.7 classes as translucent, not clear; oil on white at
exposure 2.5 (T_max 0.20 in the gap) snaps down to 0.12 with residual ≤ 5 levels; T at 0.12, 0.185,
0.25, 0.55, 0.625, 0.7 (snap direction); the encoded composite `(1−T)·liquid + T·back` versus
`enc255(C)` for a black backing, T 0.5 and target linear 0.2 (expects 248 → composite 124 levels);
a gradient backing (`tubeBackGradient` 2, dark `tubeBack`, light `tubeBack2`) and a light uniform
backing (parchment) behind a translucent liquid, both with the centre-row residual ≤ 5 levels (via
`T_max`); a bright scattering body (`S` 0.05, `K` (0, 0.3, 0.3), exposure 4, black backing) either
snaps down through `T_up` to a residual ≤ 5 or is rejected (10); design bounds: `freeHomeK` −1 rejected,
`digitBright` 10 rejected (11), `freeLiquid` false for a liquid rejected (11), sprite `digitScaleY >
digitScaleX` rejected (11); actual `buildPalette(params)` centre AND wall rows (`y = round(yc·(1 + d))`) reproduce the
targets within 5 levels after the RGB565 round trip for every non-clear, non-plasma fixture (the wall
row through the fitted `shadeDepth` and the solved `rimTint`); a fixture with `rimLight` 0 renders
byte-identically to the same params before v24 (`check:meniscus` parity unchanged); overexposure: milk at exposure 3 rejected (9), milk at exposure 1.1 accepted with `luma(liquidHi) > luma(liquid)`; `μ_eff` exactly at 2.5 and 500 and one step either side (class, `traceDrain`
≤ 20 with traces on at 500, `freeDamp` jump direction).

Every fixture's derived `Params` must return zero coherence issues for its inferred class, and the
viscosity sweep μ = 0.2 … 10⁵ (other inputs fixed) must give monotone non-increasing `freeBounce`,
`meniscusK`, `angleTiltGain`, `angleGyroGain`, `traceDrain`, `fizzSpeed` and monotone
non-decreasing `freeDamp`, `meniscusDamp`, `contactDyn`, `wetFilm`, `traceFilm` **across the whole
sweep** (the class-threshold jumps go in the same direction as the law; the boundary values shared by
two classes make `angleGyroGain` and `angleTiltGain` continuous; `traceDrain` is one law across them).

## Provenance of preset values

Every physical preset (`sim/src/material/presets.ts`, `presets/materials/*.json`) records for each
property `measured` (a handbook value at 20 °C), `estimated` (a plausible value, e.g. absorption
coefficients chosen for the look) or `artistic` (emission, lighting, exposure). Optical absorption
coefficients are estimates unless stated; viscosities, densities, surface tensions and refractive
indices of the common liquids are handbook values.
