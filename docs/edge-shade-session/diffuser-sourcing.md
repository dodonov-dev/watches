# Diffuser sourcing for the rod (2026-11-21)

Goal: soften the LCD's pixel rows under the acrylic rod. Searches: Gemini 4 Neon via agy (marketplaces; EU specialist
shops) and Codex gpt-6.1-sol (web search). Every link below was re-opened by a separate fetch; "verified" = the page
loaded and showed the product and the quoted numbers. Raw search reports: diffuser-search-*.md.

Rule that decides the stack: a surface-matte film or a sanded face scatters only against air. Glue/OCA on the matte
face (index ≈ 1.47–1.5) wets it out and the haze vanishes. Bulk-scattering films / hazy OCA keep their haze when bonded.

## Verified, orderable in small quantities

| Product | Shop | Link | Specs (from the page / datasheet) | Price | Notes |
|---|---|---|---|---|---|
| Velken Entspiegelungsfolie 551030 (anti-glare PET, matte top, silicone adhesive) | velken.de (DE) | https://www.velken.de/p/entspiegelungsfolie-fuer-displays-touchscreens/ | haze 11.9 %, transmission 90.5 %, ≈125 µm | 9×9 cm sample from 2.20 €; cuts 59.90 €/m², min 5×5 cm | Low haze: closest to "a little softening". Repositionable, no residue. Surface-matte: rod must rest dry on it. |
| elbfolien LED-Diffusorfolie 20 % / 30 % / 60 %, self-adhesive | elbfolien.de (DE) | https://elbfolien.de/produkt/led-diffusorfolie-20-streufolie-2-x-200cm/ · https://elbfolien.de/produkt/led-diffusorfolie-30-selbstklebend-2x200-cm-gleichmaessiges-led-licht/ · https://elbfolien.de/produkt/led-diffusorfolie-60-streufolie-2-x-200cm-kopie/ | 20/30/60 % diffusion (titles), 80 µm (20 and 30); haze / transmission not stated | 17.99 € per 2×200 cm; free samples offered on the category page | LED-strip diffuser: likely much stronger and dimmer than display AG films. Try the 20 % sample first. |
| ORACAL 8510 Etched Glass Cal (frosted decor PVC) | plotterfolie.de (DE) | https://plotterfolie.de/de/oracal-8510-etched-glass-cal-glasdekorfolie-aetz-effekt.html | 80 µm; optics not stated | from 2.34 € (31×20 cm sheet) | Window frosting: probably far too hazy; cheap to try. |
| Diffusionsfolie 46 % (DE210/46) | klebefolien.com (DE) | https://www.klebefolien.com/produkt/diffusionsfolie-46-prozent/ | 46 % light transmission, PVC 80 µm | 24.99 € per running m (126 cm) | Too dark for this use (46 % transmission); listed for completeness. |
| 3M Fasara SH2MACRX2 Mat Crystal 2 (matte PET decor film) | foliencenter24.com (DE) | https://www.foliencenter24.com/3m-fasara-glasdesignfolie-sh2macrx2 | optics not on the page | 58.50 € per m × 127 cm, min 2 m | Far more than needed; ask for a sample. |

## Partly verified

| Product | Link | What is verified | Notes |
|---|---|---|---|
| Photodon display AG films: HSG, MXT, MXH (US) — build-your-own sample pack | https://www.photodon.com/p/film-sample-build-your-own.html | HSG datasheet (https://www.photodon.com/HSG-TDS.pdf): haze 35 %, transmission 90 %, 280 ± 10 µm without liners, silicone adhesive. The order page refuses automated access (403): price (from US$7 + US$5 shipping per Codex) and the MXT/MXH values (haze ≈15 / ≈12 %) are unverified. | Pick 3×5" samples (2×3" is shorter than the rod). Open the page in a browser. |

## Industrial hazy OCA (bulk scattering, keeps haze when bonded) — B2B, ask for engineering samples

- LINTEC Opteria MO-8017 / MO-8017UV2 (light-diffusion OCA, haze 10–99 % per search reports) — https://www.opteria-global.com/english/products/mo/grant/
- ZACROS (Fujimori) light-diffusible adhesive film, POL-204G20H65 / K20H65 (haze ≈64–65 % per search reports) — https://electronics.zacros.co.jp/products/optical-adhesives/light-diffusible-adhesive-film/
- Tomoegawa DA series diffuse adhesive (haze ≈25–81 % per search reports) — https://www.tomoegawa.co.jp/product/display/diffuse/
- KGK MGOC acrylic-gel optical diffusion adhesive (haze 24.6 / 52.3 % per Codex; its datasheet link returned 404)

None of these pages were re-verified; no small-quantity channel found.

## Not suitable / failed links
- Gemini's links for 3M 7725-314, ASLAN D 160 (Modulor, Foliencenter24), Edmund #17-683: 404 or a different product.
- tesa / 3M / Lohmann optical OCAs (8146, 8171, 9483, DuploCOLL OC, tesa 880xx): clear (<1 % haze), and sold in B2B rolls.
- Translucent non-woven double-sided tapes (tesa 4959, DuploCOLL 200, 3M 9080): paper fibres, likely visible texture.
- tesafilm matt-unsichtbar / Scotch Magic 810: matte single-sided tape, a free stand-in for the matte-film test.

## Suggested first order
Velken 551030 sample (2.20 €) + elbfolien 20 % free sample + Photodon sample pack (HSG + MXT + MXH). Test each dry under
a resting rod; for a bonded build, only bulk-scattering material (elbfolien/LED diffusers, hazy OCA) survives the glue.
