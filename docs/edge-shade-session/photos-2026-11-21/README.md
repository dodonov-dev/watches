# Edge-shade photo series (2026-11-21)

ISO 200, 1/50 s, fixed exposure. Left tube: rod sanded with 3000 (dry). Right tube: clear rod.
A off · B 0.7/1.5/0.4 · C 0.7/3/0 · D 0.8/3/0 · E 0.8/2/0 · F 0.8/3/0.4 · G 0.9/3/0 (strength / shape / fold cover).
L* (sRGB-decoded camera values, 75th percentile over liquid rows to drop digits), left edge → right edge:

| | clear: 0.07 | .25 | .5 | .75 | .9 | sanded: 0.07 | .25 | .5 | .75 | .9 |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 20 | 35 | 53 | 81 | 82 | 55 | 69 | 73 | 96 | 92 |
| B | 18 | 30 | 34 | 25 | 39 | 47 | 50 | 60 | 53 | 37 |
| C | 18 | 32 | 37 | 26 | 49 | 50 | 55 | 63 | 67 | 45 |
| D | 18 | 32 | 43 | 23 | 38 | 42 | 60 | 72 | 68 | 40 |
| E | 19 | 31 | 40 | 25 | 28 | 46 | 54 | 65 | 57 | 37 |
| F | 20 | 34 | 48 | 28 | 28 | 41 | 63 | 72 | 67 | 38 |
| G | 18 | 31 | 38 | 21 | 28 | 45 | 58 | 64 | 61 | 37 |

Findings: the drawn liquid is flat (sim render, L* 79–86 symmetric), yet A is strongly one-sided (clear rod 20 → 82):
most likely the LCD's viewing-angle response through the rod (unverified; check: bare panel tilted across the tube).
Symmetric edge shade then has nothing to darken on the dark side. The sanded rod mixes angles: D/F give a near-symmetric
dome. F chosen (board set 2026-11-21). Next if confirmed: per-side compensation using A as the measured transfer
(astra-model.md section 4).
