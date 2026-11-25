**I’d keep the centre and use Profile A, starting at `edgeShade=0.30`, shape 3, fold 0.40.** The earlier 0.002 mm conclusion applies only to a straight-on view with the fitted air gap. At 30° tilt, the outer band on one side occupies **1.84 mm** of the rod image, although the very last row still appears in a narrow **0.0042 mm** strip elsewhere. At 45°, that last 0.0825 mm panel row occupies **0.174 mm**, about **2.1×** its physical width. Reversing the tilt exchanges the two sides. The model supports your observation that the outermost rows can be quite visible.

At 0.30, the proposed profile keeps the bare-panel centre at **\(L^*=96.3\)**, keeps the old grey at **73.2**, and reaches **52.6** at the last row. At 0.40 those three values are **95.3, 63.9, 38.8**. The stronger setting also retains a more conspicuous stripe close to straight-on.

## 1. Which rows the rod shows

All distances below are in mm. \(d\) is signed distance on the panel from the tube centre. \(x\) is apparent position **in the plane perpendicular to the line of sight**, measured from the projected rod axis. Positive tilt puts the eye on the \(+d\) side. The physical row group counted from the centre is \(j=\lfloor |d|/0.0825\rfloor\), for \(0\le j<36\). The drawn tube ends at \(|d|=2.970\).

**Apparent footprint of the outer band, \(2.000\le |d|\le2.970\).** Widths in parentheses are projected image widths. A row can have more than one image.

| Tilt | Images of the negative-\(d\) outer band | Images of the positive-\(d\) outer band | Image of the very last row, \(2.8875\le |d|\le2.970\) |
|---:|---|---|---|
| 0° | \(+3.97302\) to \(+3.97452\) **(0.00150)** | Mirror interval at negative \(x\) **(0.00150)** | **0.000101** per side, at \(|x|=3.97442\)–3.97452 |
| 10° | \(-3.98182\) to \(-3.34210\) **(0.63972)** and \(+3.77836\) to \(+3.78424\) **(0.00588)** | No direct image | \(+3.78384\) to \(+3.78424\) **(0.000393)** |
| 20° | \(-4.00000\) to \(-2.88068\) **(1.11932)** and \(+3.25527\) to \(+3.27327\) **(0.01800)** | No direct image | \(+3.27210\) to \(+3.27327\) **(0.00117)** |
| 30° | \(-4.00000\) to \(-2.16442\) **(1.83558)** and \(+2.07719\) to \(+2.14858\) **(0.07138)** | No direct image | \(+2.14434\) to \(+2.14858\) **(0.00424)** |
| 45° | \(-4.00000\) to \(-3.67916\) **(0.32084)** | No direct image | \(-3.85294\) to \(-3.67916\) **(0.17378)** |

The wide and narrow images contain different rows. At 30°, the wide image reaches \(d=-2.503\). A row at \(d=-2.500\) appears **three times**. The wide image first touches the last row at **42.24°**, reaches its centre at **43.10°**, and reaches the physical edge at **43.89°**. By 45° both folds have passed beyond the drawn tube. The remaining strip then shows only \(d=-2.623\) through \(-2.970\). This explains how the last row can become prominent even as the total visible tube area shrinks.

**Full branch map.** Read each row left to right in increasing apparent \(x\). Each cell is \((x,d)\). Between consecutive cells, \(d\) runs monotonically through every intervening panel coordinate. Infinite \(d\) denotes the limiting ray at total internal reflection (TIR). The drawn image ends earlier, where \(|d|=2.970\).

| Tilt | Left transmitting limit | First fold | Second fold | Right transmitting limit |
|---:|---:|---:|---:|---:|
| 0° | \((-3.9783,+\infty)\) | \((-3.6786,-1.9216)\) | \((+3.6786,+1.9216)\) | \((+3.9783,-\infty)\) |
| 10° | \((-4.0000,-1.4376)\) | \((-3.8427,-2.1653)\) | \((+3.3174,+1.4943)\) | \((+3.7989,-\infty)\) |
| 20° | \((-4.0000,-2.1929)\) | \((-3.8779,-2.3275)\) | \((+2.6042,+0.7314)\) | \((+3.3135,-\infty)\) |
| 30° | \((-4.0000,-2.3737)\) | \((-3.7784,-2.5028)\) | \((+1.2734,-0.5570)\) | \((+2.2653,-\infty)\) |
| 45° | \((-4.0000,-2.6234)\) | \((-3.1300,-3.0350)\) | \((-2.2392,-3.0031)\) | \((-0.5991,-\infty)\) |

**Local magnification.** Each entry below is **\(x\) / \(|dx/dd|\)**. The last column samples the centre of the last row. At a fold the point magnification diverges, which is why the finite-row widths above are the better measure of what the eye sees.

| Tilt | Panel centre \(d=0\) | \(d=-2.000\) | \(d=-2.500\) | \(d=-2.92875\) |
|---:|---|---|---|---|
| 0° | \(0/1.771\), \(\pm3.9643/0.0091\) | \(3.9730/0.0020\) | \(3.9739/0.0015\) | \(3.9745/0.0012\) |
| 10° | \(0.4111/1.759\), \(3.7437/0.0368\) | \(-3.9818/0.149\), \(-3.3421/2.274\), \(3.7784/0.0078\) | \(3.7818/0.0059\) | \(3.7840/0.0048\) |
| 20° | \(0.9238/1.806\), \(3.1246/0.170\) | \(-2.8807/2.296\), \(3.2553/0.0246\) | \(3.2658/0.0181\) | \(3.2727/0.0142\) |
| 30° | — | \(-2.1644/2.289\), \(2.0772/0.108\) | \(-3.8398/10.01\), \(-3.7076/13.29\), \(2.1207/0.0702\) | \(2.1465/0.0514\) |
| 45° | — | — | — | \(-3.7826/2.027\) |

For an arbitrary row or the opposite tilt, the continuous map is as follows. Let \(\theta\) be eye tilt and \(a\) the signed angle from the eye direction to the curved-surface normal. For positive tilt, \(-90^\circ\le a\le90^\circ-\theta\). With \(R=4\), \(n=1.49\), and \(g=0.87\),

\[
x=R\sin a,\qquad h=\theta+a-\arcsin(\sin a/n),\qquad v=n\sin h,
\]
\[
d(a)=\frac{x}{n\cos h}-g\,\frac{v}{\sqrt{1-v^2}},\qquad
M(a)=\left|\frac{R\cos a}{d'(a)}\right|.
\]

Keep rays with \(|v|<1\). On each branch containing the requested \(d\), invert \(d(a)\) to get its image. For negative tilt, negate both \(x\) and \(d\). I checked the zero-tilt form against the repository’s independent ray equation over the drawn image. [Physical ray model](./docs/physical-tube-model.py) · [Firmware ray and Fresnel model](./firmware/src/rod.h)

### Could seating explain the observation straight-on?

**A modest gap change can expose the start of the outer band. Exposing the last row on the main branch requires a much larger change.** These are the largest centred air gaps that allow the on-axis fold to reach each landmark.

| Main branch must reach | Largest \(g\) | Reduction from fitted 0.87 |
|---|---:|---:|
| Start of outer band, \(d=2.000\) | 0.796 | 0.074 |
| \(d=2.500\) | 0.410 | 0.460 |
| Inner boundary of last row, \(d=2.8875\) | 0.200 | 0.670 |
| Centre of last row, \(d=2.92875\) | 0.182 | 0.688 |
| Physical edge, \(d=2.970\) | 0.164 | 0.706 |

For example, at \(g=0.15\) the last row has a **0.0547 mm main image** and a **0.0087 mm same-side return image**. That geometry predicts central magnification **1.53**, appreciably below the photo fit of **1.77**. A lateral seating offset at the fitted gap can also expose one edge. It takes **0.966 mm** of offset to reach the beginning of the last row and **1.007 mm** to reach its centre. The opposite edge moves farther out of reach.

I would attribute visibility that switches sides with wrist tilt to viewing angle. For a consistently visible last row *straight-on*, gap, centring and the actual cover stack matter. The single photo constrains central magnification. Air and cover glass with the same paraxial equivalent gap bend high-angle rays differently, so the table gives conditional thresholds rather than mechanical tolerances for the assembled watch. [Geometry constants and fit](./spec/layout.h#L177) · [Earlier stack analysis](./docs/edge-shade-session/astra-model.md#L69)

## 2. Profile A mapped to the visible image

I weighted **80% of views uniformly over 0–30° and 20% uniformly over 30–45°**, equally from either side. The 20% is a design choice. It gives the last rows weight in the poses where they acquire a substantial image. With only 0–30° and the same optics, the outermost three rows at 0.40 all round to \(K=92\), and the outermost five at 0.30 all round to \(K=125\). Including the steeper desk and wrist views gives a distinct code to every row of the old grey band at both requested strengths.

For adjacent row centres \(d_j,d_{j+1}\), let \(W_j\) be the angle-weighted sum of **transmitted apparent width**. At each view, integrate \(\tau(x,\theta)\,dx\) over every image where \(d_j\le |d(x,\theta)|<d_{j+1}\). This counts repeated images, includes local magnification through \(dx=|dx/dd|\,|dd|\), and gives less weight to a dim grazing ray. Here \(\tau\) is the firmware’s unpolarised curved-surface, flat-base and cover transfer, relative to straight-on centre transmission.

Let \(b\) be the innermost row of the old constant-\(K\) run and \(e\) the outermost row, indexed **from the centre**. Keep all old rows through \(b\). Beyond it use

\[
u_j=\frac{\sum_{i=b}^{j-1}W_i}{\sum_{i=b}^{e-1}W_i},\qquad
K_j=\left\lfloor K_b\left(1-s\,u_j\sqrt{u_j}\right)+\tfrac12\right\rfloor .
\]

**Complete half-row table, `320w8-8`, H=72.** Here the physical row index runs **from the edge toward the centre**, matching the saved dump. Row \(71-y\) uses the same \(K\) as row \(y\). The retained RGB code factor is \(K/256\). Shape is 3 and fold is 0.40 throughout.

| Physical rows, edge → centre | A at 0.40 | A at 0.30 |
|---|---|---|
| 0–5 | 92, 95, 98, 101, 104, 108 | 125, 128, 131, 134, 137, 141 |
| 6–11 | 113, 119, 126, 133, 140, 146 | 146, 152, 158, 165, 171, 176 |
| 12–17 | 151, **154**, 164, 175, 184, 193 | **179**, 180, 188, 195, 202, 209 |
| 18–23 | 200, 207, 213, 218, 223, 226 | 214, 219, 224, 228, 231, 234 |
| 24–29 | 230, 233, 235, 237, 238, 239 | 236, 239, 240, 242, 243, 244 |
| 30–35 | 240, 241, 241, 242, 242, 242 | 244, 245, 245, 245, 245, 245 |

The bold entries are the old grey anchors. **Without the rod**, from physical row 0 through rows 3, 6, 9 and 12, the 0.40 profile rises through \(L^*=\) **38.8, 42.6, 47.7, 55.8, 62.8**, reaching **63.9** at row 13. At 0.30 those five values are **52.6, 56.2, 60.8, 68.1, 73.2**, reaching the anchor at row 12.

**Predicted apparent \(L^*\) through the rod.** Each cell gives **0.40 / 0.30** for a uniform white input. I used \(Y=\tau(x,\theta)(K_j/256)^{2.2}\), with the same unshaded straight-on white reference at every angle. The values include row-code rounding. Actual RGB565 colour, panel angular emission, pupil blur and reflected housing light can change the observed contrast. A dash means no direct image of the drawn tube at that position.

| Apparent \(x\), mm | 0° | 15° | 30° |
|---:|---:|---:|---:|
| −3.990 | — | 34.4 / 43.0 | 28.7 / 37.9 |
| −3.950 | 68.8 / 70.4 | 42.4 / 53.0 | 37.9 / 49.0 |
| −3.780 | 59.3 / 68.4 | 49.4 / 61.2 | 42.4 / 55.0 |
| −3.000 | 71.3 / 78.5 | 62.4 / 72.8 | 49.8 / 62.7 |
| −2.000 | 88.8 / 91.5 | 80.7 / 85.7 | 62.7 / 73.1 |
| −1.000 | 94.3 / 96.0 | 91.2 / 93.3 | 80.5 / 85.4 |
| 0 | **95.3 / 96.3** | **94.9 / 96.3** | **90.3 / 92.3** |
| +1.000 | 94.3 / 96.0 | 95.2 / 96.2 | 91.1 / 92.7 |
| +2.000 | 88.8 / 91.5 | 92.5 / 94.2 | 67.2 / 71.4 |
| +2.121 | 87.0 / 90.5 | 91.8 / 93.8 | 32.5 / 43.0 |
| +2.1465 | 87.0 / 90.5 | 91.8 / 93.8 | **25.7 / 36.3** |
| +3.000 | 71.3 / 78.5 | 84.9 / 88.3 | — |
| +3.400 | 62.7 / 72.2 | 84.7 / 86.3 | — |
| +3.5086 | 62.2 / 71.7 | 79.8 / 80.7 | — |
| +3.5827 | 60.7 / 70.9 | **21.9 / 31.4** | — |
| +3.84489, just inside row change | **57.3 / 66.2** | — | — |
| +3.94042, on-axis stripe | **69.2 / 71.4** | — | — |
| +3.97447, on-axis last row | **14.7 / 22.4** | — | — |

At 30°, apparent \(x=0\) samples an off-centre panel row. The physical centre itself is outside the direct view. A fixed symmetric row table can preserve the panel centre and still produce this asymmetric rod image.

## 3. Is B’s centre cap worth it?

**For your preference, I’d leave B out.** Its strongest benefit is at 0–10°. At 15° and 30°, the worst remaining rise occurs on the outer side and B leaves it unchanged.

I compared A with the same new outer ramp plus the previous B centre cap. The metric is the **largest trough-to-later-peak rise in \(L^*\)** when moving outward from the brightest point of the main image toward either rim. It includes individual row-boundary steps. The table reports the worse rim at each angle.

| Tilt | A 0.40 | B 0.40 | A 0.30 | B 0.30 |
|---:|---:|---:|---:|---:|
| 0° | 11.9 | 1.4 | 5.4 | 1.7 |
| 5° | 12.1 | 1.7 | 5.5 | 1.5 |
| 10° | 6.1 | 2.4 | 2.5 | 2.0 |
| 15° | 2.3 | 2.3 | 2.2 | 2.2 |
| 20° | 2.4 | 2.4 | 1.9 | 1.9 |
| 30° | 1.8 | 1.8 | 1.7 | 1.7 |

At 0.40, B buys about **10.5 \(L^*\)** of straight-on stripe suppression at a **13.4 \(L^*\)** centre cost, from 95.3 to 81.9. At 0.30 it buys **3.8 \(L^*\)** at a **2.3 \(L^*\)** centre cost, from 96.3 to 94.0. A at 0.30 therefore keeps the centre and cuts the straight-on rebound to less than half the 0.40 value. Its remaining straight-on rise spans about **0.09 mm**. That stripe is the trade-off in the recommendation. [Previous cap definition](./docs/edge-shade-ends/astra-model.md)

## 4. Sim and firmware implementation

- **Generate one cumulative apparent-width table per rod geometry, physical pitch and row parity.** Store the prefix sums of \(W_j\) in generated flash data and emit the same values for TypeScript. The model used projected-width midpoint samples, 65,536 per view, and 0.25° angular bins. Halving the angular step and doubling the ray count reproduced every proposed \(K\). Runtime needs two prefix differences and a normalisation per tail row. [Existing rod-table generator](./firmware/tools/gen_rod_rays.py)
- **Keep the existing solver for the boundary and centre.** Use its current float32 sums, find the innermost row of the contiguous outer run with the same rounded \(K\), and anchor the new ramp there. Use binary64 and the same operation order for `u * sqrt(u)` and final rounding in both implementations. Apply the profile on physical rows before the existing physical-to-canvas averaging. Preserve the old factors inward of the anchor, the zero-strength bypass, and the existing lens row mapping. A one-row outer run has no interpolation interval. [Firmware row builder](./firmware/src/render.cpp#L5352) · [Simulator row builder](./sim/src/render.ts#L3197)
- **Keep firmware memory deterministic.** Bound generated prefixes and existing per-tube work arrays for the largest supported physical span, with a visible failure if the span exceeds capacity. No per-angle table or ray trace is needed on the board. The frame loop continues to consume the integer blend weight \(256-K\). [Firmware workspace](./firmware/src/render.cpp#L1549)
- **Keep the three controls and `PARAMS_VERSION=33`.** The view distribution is a fixed design choice. `edgeShade` sets the additional endpoint reduction, shape controls the existing inner profile, and fold locates the old grey anchor. The saved fields, preset schema and NVS layout can stay as they are. For implementation parity, check both row parities, a scaled LCD canvas, and the two 72-row tables above. [Parameter version](./sim/src/params.ts#L208) · [Row parity checks](./firmware/tools/check_shade_rows.py)

I ran the model read-only in Python and reproduced every baseline half-row code in the supplied 0.40 and 0.80 dumps. The off-axis results are predictions for the fitted optical stack; its layer thicknesses and angular light output have not been measured. I made no file or Git changes and opened no serial ports.
exit 0
