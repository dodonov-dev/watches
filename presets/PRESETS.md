# Signature presets — list and acceptance rules

Every preset is one real liquid in one real vessel, declared with a *material* (`mat` in
`sim/src/params.ts`), and the numbers must agree with that material. `npm run check:presets`
(`sim/tools/check-presets.ts`) enforces the rules below; `npm run dump:presets` writes the JSONs here.

## The list

| id | name | material | vessel / scale |
|---|---|---|---|
| frizzante | Frizzante | clear, watery, wetting, carbonated | lab cylinder, white print on the glass |
| alpine | Alpine spring | clear, watery, wetting, carbonated | pale ceramic backing, rear slate scale, fine bead |
| pinot | Pinot noir | translucent ruby, watery, wetting, legs (2026-09-23), exempt from material ranges | parchment backing, bronze numerals behind the liquid |
| spritz | Aperol spritz | vivid orange-red aperitivo (translucent), watery, wetting, carbonated with a foam ring (2026-09-23), exempt from material ranges | white bar-glass backing, navy enamel numerals behind the liquid |
| cuvee | Cuvée | straw-gold sparkling wine, wetting, carbonated (2026-09-23), exempt from historical material ranges | ivory backing, bronze rear numerals, pale bead, restrained reflections |
| nocturne | Nocturne | opaque blue-black ink, medium viscosity, wetting, no gas | smoked glass, silver front markings, draining residue |
| rockpool | Rock pool | clear blue-green spring water, watery, wetting, no gas (2026-11-22), Cuvée's rod and physics, exempt from material ranges | pale stone backing for the pebble housing, childish ochre brush numerals (font 13) behind the water, no ticks |
| tide | Bioluminescent tide | dark teal night-sea water, self-lit cyan edge, watery, wetting, plankton sparks (2026-09-23), exempt from material ranges | near-black vial, dim steel graduations and digits behind the glass |
| phosphor | Phosphor sample | pale green watery solution (translucent), wetting, no gas (2026-09-23) | clear lab vial on white paper, marker labels on the glass; see-through meniscus (`surfaceFill` 0.25, `surfaceBlick` 0.8) |
| urine | Urine sample | tinted amber (translucent), watery, wetting | specimen cup graduations on the glass |
| blood | Blood | opaque venous red, medium viscosity, wetting | syringe print on the glass |
| milk | Milk | opaque white colloid, medium-thin, wetting | printed scale on the glass |
| mercury | Mercury | opaque liquid metal, non-wetting, stiff surface | thermometer, etched glass scale |
| honey | Honey | translucent amber, viscous, wetting, trapped air | brass numerals behind the liquid |
| olive-oil | Olive oil | user-tuned olive green (2026-09-18), exempt from material ranges | pale numerals behind the liquid, lingering residue |
| cola | Cola | translucent dark, watery, carbonated | enamel numerals behind the liquid |
| malt | Single malt | translucent amber, medium-thin, clings (legs) | brass numerals behind the liquid |
| champagne | Champagne | tinted pale gold (translucent), watery, fine bead | amber-resin numerals behind the liquid |
| cryo | Cryo oxygen | clear pale blue, superfluid-thin, boiling | frosted wall, steel numerals behind |
| ink | India ink | opaque black, medium viscosity | enamel numerals on the glass |
| glow | Glow stick | emissive green, medium viscosity, translucent | seven-segment print on the glass |
| xenon | Xenon | emissive plasma, no inertia | rear ticks, bold print |
| molten | Molten iron | emissive opaque metal, non-wetting, gas bubbles | forged numerals behind (dry side only) |
| free | Free liquid | user-tuned slug (2026-08-26), exempt from the checker | copper numerals |
| absinthe | Absinthe | user look from presets.zip (2026-09-02), exempt | vivid green on white, widest 79 px tubes, large black rear numerals |
| chartreuse | Chartreuse | user look (2026-08-31), exempt | bright yellow-green on black, soft glowing edge, bronze rear numerals |
| bottle | Bottle green | user look (2026-09-01), exempt | dark green, 80 px tubes on charcoal, faint rear numerals |
| claret | Claret | user look (2026-09-18), exempt | near-opaque dark red draining right, light numerals on white |
| olive-white | Olive oil on white | user look (2026-09-18), exempt | the tuned olive oil drained from the right over white |
| menthe | Menthe | user look (2026-09-25), exempt | translucent teal on white, dark rear numerals |
| lime | Lime soda | user look (2026-09-26, hand-tuned physical export), exempt | pale lime over white |
| patrick | Patrick pink | user look (2026-09-09), exempt | opaque pink, yellow print on the glass |
| seltzer | Seltzer | user look (2026-09-23, the Cuvée reference), exempt | colourless water on white |
| glycerol | Glycerol on white | user look (2026-09-23), exempt | colourless viscous liquid on white |
| glycerol-dark | Dark glycerol | user export (2026-09-27), exempt | smoky grey viscous liquid on pale sage, rim-lit, dark rear numerals |
| prosecco | Prosecco | user physical material (2026-09-26), stored as its derived Params, exempt | pale straw on white |

The original signature presets also exist as `<id>-big` for the second, wider physical rod (`bigLens()` in `params.ts`, from
`examples/urine_big.json`): 72 px tubes at y 11 / 144, `lens` −0.05 with curve −3, marks moved with the tube
(thin presets take the example's hand-tuned mark values, wider ones scale theirs by 72 / tubeHeight), and
front digits drop their `topLens` pre-warp. `urine-big` reproduces the example exactly. Alpine spring,
Pinot noir, Aperol spritz, Cuvée, Nocturne, Bioluminescent tide and Phosphor sample are standard-rod only.

Removed: `user1`, `mint`, `neon`, `concept` (legacy colour-only looks; superseded by `glow`/`frizzante`).

The user looks from absinthe on came from `presets.zip` (2026-09-27, 25 exports; glycerol-dark is a later export). Dropped as
duplicates or superseded: `alpine_mineral` (= alpine), `bubbly_urine` and `params (38)` (= urine + gas),
`params (37)` (= free), `olive_oil_small` (= olive-oil), `params (39)`/`(51)`/`(57)`/`(56)`/`(66)` (earlier
saves of chartreuse / absinthe / olive-white / seltzer / lime), `great_material` (lime is its later hand-tuned
export), `material`/`material (1)` (unnamed material-mode drafts of aerated oil and spritz).

## Gas

A preset is the liquid and vessel only: its `p` sets no `fizz*` key (checked). Gas is a separate model from
`GAS_MODELS` in `params.ts`; each preset lists the models that fit it (`gas`, signature first, `none` always
offered), `presetParams(e, gas = e.gas[0])` applies one, the picker's gas dropdown swaps it without touching
anything else, and `?gas=<id>` selects it by URL. Dumped JSONs and the material checks use the signature.

| id | name | taken from |
|---|---|---|
| none | No gas | — |
| fine-bead | Fine bead | frizzante / champagne / alpine (merged 2026-09-27; alpine's bead went from 2 px to 1 px) |
| lively-bead | Lively bead | cola |
| pearl-bead | Pearl bead | cuvée |
| brisk-pearls | Brisk pearls | lime soda / prosecco |
| foam-ring | Foam ring | spritz |
| large-bubbles | Large bubbles | glycerol |
| slow-bubbles | Slow bubbles | free liquid |
| trapped | Trapped bubbles | dark glycerol (replaced the aerated-oil haze, 2026-09-27) |
| held-air | Held air | honey |
| gas-pockets | Gas pockets | molten iron |
| boiling | Boiling | cryo oxygen |
| sparks | Plankton sparks | bioluminescent tide |

In material mode the gas comes from the material (gasMode / gasLevel), so the dropdown is disabled there.

## Physical collection

The same looks as material presets (`MATERIAL_PRESETS` in `sim/src/material/presets.ts`): each is a physical
material (viscosity, density, surface tension, index, absorption / scattering, emission, wetting, residue, gas)
plus the design keys (layout, backing, marks, digits) its legacy preset sets, or — for the material-only entries
(aerated-oil, glycerine) — a design of its own on the house base. All other legacy `Params` are
derived by `sim/src/material/derive.ts` from `presets/materials/*.json` (the material files); the derived
`Params` are in `presets/physical/<id>.json` (same format as the legacy JSONs, input of `gen_params.py`).
`npm run dump:presets` writes both directories; `npm run check:materials` (section 14) checks that every entry
derives without rejection, is coherent for its inferred class, has complete per-property provenance
(`measured` / `estimated` / `artistic`) and that both files are fresh. Open one in the sim with
`?material=<id>`. The classes below are the derived ones (derive's `classes`), not declared.

| id | name | viscosity | opacity | gas | emissive | provenance |
|---|---|---|---|---|---|---|
| frizzante | Frizzante | watery | clear | carbonated | no | handbook; absorption 0 |
| alpine | Alpine spring | watery | translucent | carbonated | no | handbook; trace absorption estimated |
| olive-oil | Olive oil | medium | translucent | none | no | handbook; absorption estimated |
| aerated-oil | Aerated oil | medium | translucent | trapped (90, 2.9 px) | no | handbook (sunflower oil); absorption estimated; gas level artistic; own design (espresso backing, cream print, copper rear numerals) |
| honey | Honey | viscous | translucent | trapped | no | handbook (viscosity 20 °C ~10 Pa·s); absorption estimated |
| glycerine | Aerated glycerine | viscous | clear | trapped (120, 2.9 px) | no | handbook (glycerol); absorption estimated; gas level artistic; own design (blue-black backing, steel rear numerals) |
| blood | Blood | medium | opaque | none | no | handbook; optical coefficients from tissue-optics literature (reduced scattering) |
| milk | Milk | medium | opaque | none | no | handbook (viscosity at ~10 °C); scattering estimated |
| mercury | Mercury | metal | opaque | none | no | handbook; reflectance estimated |
| cola | Cola | watery | translucent | carbonated | no | estimated |
| champagne | Champagne | watery | translucent | carbonated | no | handbook; absorption estimated |
| cuvee | Cuvée | watery | translucent | carbonated | no | handbook; absorption estimated |
| ink | India ink | medium | opaque | none | no | estimated |
| nocturne | Nocturne | medium | opaque | none | no | estimated |
| glow | Glow stick | medium | opaque | none | yes | artistic emission; fluid estimated |
| xenon | Xenon | plasma | translucent | none | yes | density handbook (xenon gas at STP); emission artistic |
| molten | Molten iron | metal | opaque | trapped | yes | handbook (1600 °C); emission artistic |
| urine | Urine sample | watery | translucent | none | no | handbook; absorption estimated |
| malt | Single malt | medium | translucent | none | no | handbook (40 % ethanol); absorption estimated |
| cryo | Cryo oxygen | watery | clear | boiling | no | handbook (90 K) |
| pinot | Pinot noir | watery | opaque (on parchment) | none | no | handbook (12 % ethanol); absorption estimated |
| spritz | Aperol spritz | watery | translucent | carbonated | no | estimated |
| tide | Bioluminescent tide | watery | opaque | carbonated | yes | sea water handbook; emission artistic |
| phosphor | Phosphor sample | watery | opaque (on white paper) | none | no | estimated |

Design changes against the legacy look, each forced by a derive rejection: olive-oil `digitBright` 2 → 1.8,
cuvee `tickBright` 1.5 → 1.3, pinot and spritz `tickBright` 2 → 1.3, `digitBright` 2 → 1.8. Glow derives
opaque: its emission is summed into the body in linear light, and a bright emitter over a dark backing can
only be shown near opaque (`T_up`). Xenon keeps the legacy design (`freeLiquid` false: a plasma is pinned).
`markContrast` is a design key since 2026-09-26: every entry pins the value the former policy derived (24 for rear
marks behind a non-opaque liquid, else 0), so the derived Params did not change.

## Base look (from `examples/`)

All liquids are built over `MODERN_BASE` in `params.ts` (= `examples/nice_meniscus.json` minus its colours
and bubbles): 46 px tubes at y 12 / 185 (or `LAYOUT_WIDE` 55 px at 7 / 224), `lens` −0.5 + `topLens` 0.35
for the rod, physical light with a broad soft highlight, dark body × high `liquidBright` for a saturated tint
at ~0.5 transparency, sprite digits behind the liquid every hour / 5 min at a mid-tube baseline, dark rear
ticks on both edges, hysteretic wetting meniscus (contact lag 3, film 15, hard edge, faint caustic glow) and
the **tilt-controlled slug** (time held below 20°, smoothly released by 50°; deliberate back-and-forth
tilts keep it free for `playHold`, default 5 s). Opaque liquids and lab glassware use
`FRONT_PRINT` instead (marks on the glass). Xenon is the only pinned column — plasma is not a slug.

## Acceptance rules (checked)

`freeGain` is gravity (570 for every slug); viscosity class → slug drag/bounce, surface spring, hysteresis, film, static skew, flick kick:

| class | freeDamp | freeBounce | meniscusK | meniscusDamp | wetFilm | skew °/g | gyro kick |
|---|---|---|---|---|---|---|---|
| watery | 0.4–1.5 | 0.15–0.35 | 400–550 | 3–16 | 8–15 | 5–9 | 0.3–0.55 |
| medium | 1.5–4 | 0.05–0.15 | 200–350 | 12–25 | 12–20 | 3–5 | 0.15–0.35 |
| viscous | 6–14 | 0 | 60–150 | 25–50 | 20–30 | 0.5–2.5 | 0.02–0.12 |
| metal | 0.8–1.5 | 0.4–0.7 | 500–800 | 8–16 | 0 | 1.5–3 | 0.3–0.5 |
| plasma | pinned (freeLiquid off) | | any | any | 0 | 0–1 | 0–0.06 |

Non-wetting liquids (mercury, molten, xenon) take the metal-like surface rule (meniscusK 350–800, film 0) whatever their bulk class.

Traces (the film a receding edge leaves on the glass — blood smear, syrup coating, legs — thicker the faster the line and the more viscous the liquid (the wet-film law of `contactDyn`: watery liquids barely stain, syrup coats); gravity runs its wet part down the tube, into the liquid where that is downhill, and it dries into a fading stain): need a wetting liquid — non-wetting and plasma presets must have `traces` off. A wetting preset that leaves it on keeps `traceAmount` 0.2–2 (the stain's tint depth per unit of the coat's path through the bore, clamped at the column's own colour; blood 1.1), `traceDry` 0.1–2 s — the drying time constant, tilt-independent (blood 1.5, honey 2, ink 1.2, malt 0.6) — `traceDrain` 0–20000 px/s, the physical drain speed ρg(R/10)²/3μ of a film at the thin-film cap — watery liquids ≥ 100 (water ~1600), viscous ones ≤ 20 (honey ~0.2) — and `traceStain` 0.05–0.7 for the share of a drying film left as stain (thick coatings high: honey 0.45; thin legs low: malt 0.2). `traceFilm` 0–1 is a permanent coat over the whole glass as a share of the thin-film cap (0 = bare glass between smears; it shows as wall lines and a faint tint): coating liquids (blood, honey, olive oil) may carry one, watery ones stay near 0.

Opacity (`liquidTransparency`):
- Residue is a tint of the tube back toward the liquid's own colour (Beer–Lambert, never denser than the column); `traceAmount`, `traceStain`, and drying control its depth.
- rear marks (any class): the legibility floor fakes what the liquid lets through, so `markContrast ≤ 120 × liquidTransparency`.
- opaque ≤ 0.12: ticks and digits printed on top, or rear marks shown dimly (markContrast ≤ 14); shadeDepth 0.5–0.95.
- translucent 0.25–0.55: rear marks allowed (bright sprite digits need no markContrast floor); shadeDepth 0.5–0.85.
- clear ≥ 0.7 (colourless liquids only — a tinted liquid mixed 70 % toward the dark back turns khaki, so tinted ones are translucent): shadeDepth 0.3–0.55; liquidHi is a white surface reflection (saturation < 0.2); glassOverLiquid ≥ 0.5; rear marks need markContrast ≥ 16.

Light:
- emissive: glowStrength 0.4–0.8, edgeGlow 18–34, lightPhys 0 (it is its own light), glassOverLiquid ≤ 0.4, liquidBright 1.15–1.35, tube back luma < 16.
- not emissive: glowStrength ≤ 0.25 (a caustic at most); lightPhys ≥ 0.2.
- edgeSoft is a coverage ramp centred on the edge (0 = hard edge, 1 = classic 1-px AA, ≥ 2 a visibly soft meniscus); with a soft edge the glow folds into the same per-pixel alpha (min(1, cov + glow)) — seamless at any width, and the edge moves sub-pixel smooth.

Wetting:
- The meniscus is a contact-angle model (`contactAngle`, `contactHyst`, `contactDyn`, `capLength`): both ends are spherical caps set by
  their angle; tilt pressure moves it within the hysteresis band; the contact line is pinned, so the column's travel moves the angle
  across the band (tremor stays inside it) and only travel past θA / θR drags the line (Cox–Voinov on its speed).
- wetting: `contactAngle + contactHyst` < 90° (concave at both ends), wetFilm per class.
- non-wetting: `contactAngle − contactHyst` > 90° (convex bead), wetFilm 0.
- plasma: no meniscus dynamics (`meniscusInertia`, `contactHyst`, `contactDyn` all 0).

Gas:
- none: fizz off.
- carbonated: fizz on, speed 30–55, count 30–60 (watery only).
- boiling: fizz on, speed 45–60, count 45–60.
- trapped (viscous / molten): fizz on, speed ≤ 8, count ≤ 120 (a few held bubbles to a dense suspension: they never leave, so a trapped liquid holds more than a bead shows).
- bubble size is a look, not a class: any drawable `fizzSize` (1–16 px) is coherent.

Colour & scale:
- luma(liquid) < luma(liquidHi) (liquidLo is the Lambert dark under physical light and may sit above a very dark body).
- on-top ticks/digits must differ ≥ 40 luma from the tube back (they sit on the dry side too; dark-on-light is fine).
- highlightBright × liquidBright ≤ 1.3 for non-metal, non-emissive liquids (else the specular burns to a white stripe).
- sprite fonts, hours tube: digitScaleY ≤ digitScaleX (vial stretch) and baseline + 8·scaleY ≤ tubeHeight (glyph fits).
- trims: liquidBright 0.9–2 (1.15–1.5 if emissive), tickBright 0.8–1.3, digitBright 0.8–1.8.

## Cuvée — current renderer (2026-09-23)

Select **Cuvée** in the simulator, open `?fresh=1&preset=cuvee&t=7:23&settle=1`,
or import `cuvee.json`. One standard-rod preset: 54 px tubes at y 0 / 185.

Uses the two `perfect_*` reference exports for glass geometry and damped surface motion.
Warm straw colour, an ivory backing, bronze rear markings and pale bubble rims give depth
without emissive glow. A short-lived bead collects at the meniscus. The 20–50° reading
band and home spring keep the time legible at rest, releasing the slug under strong tilt.
The JSON contains the complete v20 configuration, including inactive controls.

The current renderer uses 3.8 px bubble diameters, 0.48 transparency and the references'
685 / 38 meniscus spring/damping; this look is exempt from the historical material ranges,
like Pinot noir and Aperol spritz. Preview: `images/presets/cuvee.png`.

## Nocturne — current renderer (2026-09-23)

Select **Nocturne**, open `?fresh=1&preset=nocturne&t=7:23&settle=1`, or import
`nocturne.json`. One standard-rod preset: 54 px tubes at y 0 / 185.

Blue-black ink fills from the left against smoked grey glass. Silver numerals and
fine graduations sit on the front glass so they remain readable over opaque ink.
A soft reflection and a concave meniscus define the column; after a tilt, a wet
smear drains back and fades. No bubbles or glow. The reading pose holds the time,
while strong tilt releases the liquid. Best viewed with the black cuff.

The complete v20 JSON matches the picker. Its declared medium, opaque, wetting
material is covered by `npm run check:presets`. Preview: `images/presets/nocturne.png`.

## Bioluminescent tide — current renderer (2026-09-23)

Select **Bioluminescent tide**, open `?fresh=1&preset=tide&t=7:23&settle=1`, or import
`tide.json`. One standard-rod preset: 54 px tubes at y 0 / 185.

A night-sea sample in a near-black vial. The water is dark teal in bulk and lights itself
cyan where the path is short: a glow past the fill edge, a lit concave cap and a bright
rim, with a faint physical highlight so the vial still reads as glass. Tiny bright sparks
drift slowly through the column and are stirred by motion; they never form a foam. Dim
steel graduations every hour / 5 min and sprite digits every 3 h / 15 min sit behind the
glass and are lit through the water. No residue. The slug is always free, on the current
tuned physics, and is exempt from the material ranges. Preview: `images/presets/tide.png`.
