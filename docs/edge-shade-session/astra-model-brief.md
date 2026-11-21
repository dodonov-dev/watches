# Model request: a perceptually gradual edge shade through the acrylic rod (read-only, maths + tables)

Context: an 8 mm acrylic half-rod (PMMA n 1.49, flat base on the LCD cover glass; effective air-equivalent pixel-to-rod
distance 0.87 mm fitted from a photo, M0 ≈ 1.77) magnifies each drawn tube. Firmware darkens panel rows by a factor
(1 − s·w(d)), d = panel distance from the tube centre. Current profile (see STATUS.md "rod profile", render.ts
`edgeShadeRows`, docs/physical-tube-model.py): t = x_in(d)/x_in(d_p) (apparent position on the inner branch,
normalised to where full depth starts), b = t², w = 1 − (1 − b^pow)², w = 1 for d ≥ d_p; d_p from `edgeShadeFold`
covering part of the fold-back zone (x_fold 3.68 mm, TIR from 3.98 mm on 8 mm).

User verdict on the board (photo-shade-0.7.png, strength ~0.7, pow ~0.8, fold 0.4): "dark enough at the edges, but where
it should already be lighter it's still dark, and the middle is too bright in contrast". Measured photo luminance
(sRGB-encoded camera values, median over 80 rows, every 3rd px across the LEFT tube, ~15.6 photo px per mm, tube
~125 px wide):
liquid: 179 178 178 173 134 57 69 74 74 77 75 73 73 85 99 110 132 140 161 174 182 208 219 221 223 206 153 125 130 129 125 103 90 78 68 57 53 51 51 47 47 109 147 159
empty : 182 181 176 155 84 60 62 60 65 78 84 92 101 124 140 153 170 152 179 215 234 243 245 243 220 185 182 189 154 132 130 122 99 92 76 66 58 52 50 50 87 133 152 164
(first/last ~4 samples are the housing; the centre includes digits and a drawn specular highlight slightly left of centre.)
The dark zone looks ~1.3 mm wide apparent per side, while our plateau should start at x ≈ 3.48 mm (0.5 mm from the edge):
so the rod itself (Fresnel loss rising with incidence angle, reflection of the dark slot/housing, fold-back, TIR) very
likely adds its own edge darkening on top of ours.

Deliver (markdown, tables, explicit formulas):
1. A model of the rod's OWN brightness transfer vs apparent position x (0..R): Fresnel transmission at the curved surface
   (unpolarised), the flat base (OCA ≈ index-matched, vs a thin air gap), solid-angle / étendue effects of the
   magnification (luminance is conserved through an ideal lens — say whether any falloff comes from that), reflection
   of the surroundings, fold-back and TIR. Eye at ~35 cm. Give T_rod(x) as a table for 8 mm (and 6 mm).
2. Compare with the measured photo profile (convert sRGB -> linear; account for the drawn content's own shading
   roughly; say what fraction of the observed edge darkness is ours vs the rod's).
3. Propose the profile in PERCEPTUAL terms: target perceived lightness L*(x) from the centre to the edge, e.g.
   L*(x) = L*_c − (L*_c − L*_e)·(x/x_e)^q, with the strength parameter setting L*_e (edge lightness) and the shape q
   (1 = perceptually even); compute the panel factor that achieves it GIVEN T_rod(x) (i.e. compensate the rod's own
   falloff), keeping the fold-back constraint (rows seen twice) and determinism (sqrt/div/fixed iterations at param
   change). State the formula for w(d) the firmware should use, its parameters (≤ 3, with ranges/defaults), and a
   table of panel factor per panel row for 320w8-8 (72-row tube, 0.0825 mm/px) at a recommended setting.
4. Say plainly which parts are uncertain and what single measurement (e.g. a photo at edgeShade 0 with locked exposure)
   would pin them down.
