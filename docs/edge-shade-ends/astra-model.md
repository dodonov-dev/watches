**I recommend the fold-back-limited profile below, starting at `edgeShade=0.30`, `edgeShadeShape=3`, `edgeShadeFold=0.40`.** On a uniform reference field, the bare panel goes from \(L^*=73.2\) at the old band boundary to **52.6 at the last row**, with a centre of **94.0**. At the photographed `0.40 / 3 / 0.40` setting, the same profile keeps the boundary at **63.9** and reaches **38.8** at the last row. The stronger setting costs more centre brightness, down to **81.9**, to suppress the light stripe seen through the rod.

### Why the sides look uniformly grey

The photograph shows what the renderer sends to the bare panel. At `0.40 / 3 / 0.40`, the outermost **14 rows per side** all retain exactly \(154/256\) of the input RGB code. That is about **32.7% of the unshaded light** under the model’s gamma of 2.2. The pooled group accounts for 13 rows. The next row inward rounds to the same value. Together they make a **1.155 mm band on each side**. At strength 0.80, the outer 13 rows retain \(55/256\), about **3.4% light**. Increasing strength changes the grey level while leaving a broad constant band. [Saved row dump](docs/edge-shade-ends/rows-now.txt) · [Bare-panel photo](docs/edge-shade-ends/photo-no-rods-0.4.png)

The current builder reaches its target edge lightness at apparent \(x_e=3.485\) mm, holds the target constant beyond it, pools the outer panel rows, and applies a lower code-factor limit of \(1-s\). At 0.40 the floor binds. At 0.80 the pooled solution is slightly above the floor and still gives every pooled row one value. [Simulator row builder](/home/andrey/_PROJECTS/watches-perf-cheap/sim/src/render.ts:3197) · [Firmware row builder](/home/andrey/_PROJECTS/watches-perf-cheap/firmware/src/render.cpp:5352)

The rod shows those rows in a surprising order. Let \(x\) be apparent distance from the rod axis, \(d\) the **signed** panel offset, and \(j=0,\ldots,35\) the half-row index counted **from the centre**.

| Apparent interval on one side | What the rod shows |
|---|---|
| \(0\)–\(3.679\) mm | The main branch moves from \(d=0\) to \(+1.922\) mm, reaching only rows \(j=0\) through 23. At 0.40 it enters the flat band at \(x=3.324\) mm. |
| \(3.679\)–\(3.96431\) mm | The ray folds back from row 23 through progressively brighter rows to the panel centre. For example, the centre of row 12 appears at both \(x=1.836\) and \(3.945\) mm. |
| \(3.96431\)–\(3.97452\) mm | The ray crosses the axis and reads the opposite half of the panel. **Rows 24–35 appear only in the last 0.00155 mm** of this interval. They occupy 0.990 mm on the bare panel. |
| \(3.97452\)–\(3.97830\) mm | The direct ray lands outside the drawn tube. Its brightness depends on the surrounding pixels. |
| \(3.97830\)–\(4.000\) mm | Total internal reflection cuts off the direct panel ray. Reflected room or housing light can still be visible. |

This explains why darkening the last dozen panel rows fixes the photograph but scarcely affects the stripe **through** the rod. At the current 0.40 setting the rod image falls to **\(L^*=57.3\)** just before \(x=3.845\) mm, then rises to **69.2** at \(3.940\) mm. That second position is showing an inner row. [Signed ray model](/home/andrey/_PROJECTS/watches-perf-cheap/docs/physical-tube-model.py) · [Firmware ray and Fresnel transfer](/home/andrey/_PROJECTS/watches-perf-cheap/firmware/src/rod.h)

### Two profiles with the existing controls

**A. Preserve the centre and darken the panel ends.** Keep the existing profile through the first row of the old flat band, including that row’s actual rounded factor. Call its half-row index \(b\), its retained factor \(F_b\), and the outermost index \(e\). For each row centre at panel distance \(d_j\), find \(x_-(d_j)\), the apparent position on the returning ray where the **signed** panel coordinate equals \(-d_j\). This is the branch that actually reaches every outer row. Set

\[
u_j=\frac{x_-(d_j)-x_-(d_b)}{x_-(d_e)-x_-(d_b)},\qquad
F_j=F_b\left(1-s\,u_j\sqrt{u_j}\right),\qquad b<j\le e.
\]

The interpolation measures **apparent distance**. Its local scale is \(|dx/dd|\), the rod’s local magnification. At 0.40 its endpoints on that branch are 3.972719 and 3.974473 mm. The \(u^{3/2}\) easing is a design choice that gives a gentle start at the old grey. The endpoint \(F_b(1-s)\) applies one further shade-strength reduction. At 0.40 this takes the panel from \(154/256\) to \(92/256\), or from **32.7% to 10.5% light**. Profile A preserves the bright centre, but the **11.9 \(L^*\)** fold-back rebound survives.

**B. Apply the same end profile and limit the fold-back stripe.** This is my recommendation for the assembled watch. Two apparent positions that share a row must share its panel output. If that output is \(F_j\), direct observed luminance is

\[
Y(x)=\tau(x)F_j^{2.2},
\]

where \(\tau\) is the rod’s Fresnel transmission relative to its centre. For each row on the returning positive-\(d\) branch, let \(t_j\) be \(\tau\) where the ray **enters** that row. Starting at the band boundary and walking toward the panel centre, cap each factor using the preceding row’s factor,

\[
F_j=\min\!\left(F_j^{A},\ F_{j+1}(t_{j+1}/t_j)^{1/3}\right).
\]

For an unusually wide fold cover, apply the same inequality on the other side of the fixed anchor by walking outward to the fold and raising a tail factor to \(F_{j-1}(t_{j-1}/t_j)^{1/3}\) if needed. The tabled settings need no such adjustment. Beyond the largest main-branch row, use A’s end profile.

The cube root lets an inner row brighten enough to recover some centre contrast. While the cap binds, the return-branch entry luminance falls in proportion to \(t_j^{\,1-2.2/3}=t_j^{4/15}\). At strength 0.40 the broad rebound falls from **11.9 to 1.4 \(L^*\)**. At 0.30 the largest residual rise is **1.7 \(L^*\)**. These are row-boundary steps. With a uniform white input passed through the renderer’s RGB565 channel quantisation, the corresponding modelled rises are about **1.9** and **2.7 \(L^*\)**.

**Exact pointwise darkening has a physical limit.** As the return ray crosses into a brighter inner row, its transmission is continuous and the commanded panel brightness jumps up. Some upward step therefore survives wherever the panel has a gradient. There is also a measurable cost even with continuous interpolation. At \(x=3.96431\) mm the ray sees the panel centre with \(\tau=0.356\). To keep that point below the present trough of \(L^*=57.3\), the bare centre must be **\(L^*\le87.4\)**. Today it is **95.3**. Profile B spends that brightness to obtain a declining envelope. At strength 0.80 the same rule would take the centre down to **30.7**, which is why I recommend 0.30–0.40 for this rod.

### Predicted appearance

These are direct-light \(L^*\) values for a uniform input, using the quantised row factors, gamma 2.2 and the repository’s on-axis 8 mm rod with a 0.87 mm equivalent air gap. White is the unshaded field viewed through the rod centre. The bare-panel values use the corresponding unshaded panel white. The photograph establishes the visible band, but does not calibrate panel gamma, reflections or the housing.

| Apparent \(x\), mm | Current 0.40 | A 0.40 | **B 0.40** | **B 0.30** |
|---:|---:|---:|---:|---:|
| 0, centre | 95.3 | 95.3 | **81.9** | **94.0** |
| 1.000 | 94.3 | 94.3 | 78.3 | 89.5 |
| 2.000 | 88.8 | 88.8 | 73.2 | 83.9 |
| 2.500 | 83.1 | 83.1 | 70.5 | 81.0 |
| 3.000 | 71.3 | 71.3 | 66.5 | 76.4 |
| 3.485, old target reaches edge level | 62.4 | 62.4 | 62.4 | 71.9 |
| 3.679, fold | 60.9 | 60.2 | 60.2 | 69.9 |
| 3.800, returning through old band | 58.8 | 58.8 | 58.8 | 67.8 |
| 3.845, immediately before row change | 57.3 | 57.3 | 57.3 | 66.2 |
| 3.900 | 63.9 | 63.9 | 57.8 | 66.4 |
| 3.94042, current stripe peak | 69.2 | 69.2 | 56.5 | 65.2 |
| 3.960 | 65.9 | 65.9 | 54.4 | 62.9 |
| 3.96431, ray crosses panel centre | 62.9 | 62.9 | 53.4 | 61.9 |
| 3.970, opposite half | 53.7 | 53.7 | 42.9 | 50.1 |
| 3.97452, last drawn row before exit | 28.6 | 14.6 | **14.6** | **22.3** |

**Bare panel, no rod.** Here row 0 is the physical outside edge and row 35 is next to the centre.

| Panel row | Current 0.40 | A 0.40 | **B 0.40** | **B 0.30** |
|---:|---:|---:|---:|---:|
| 0, outside edge | 63.9 | 38.8 | **38.8** | **52.6** |
| 3 | 63.9 | 46.0 | 46.0 | 58.9 |
| 8 | 63.9 | 56.6 | 56.6 | 68.4 |
| 12, old boundary at 0.30 | 63.9 | 63.1 | 63.1 | **73.2** |
| 13, old boundary at 0.40 | **63.9** | **63.9** | **63.9** | 73.6 |
| 17 | 78.3 | 78.3 | 68.8 | 79.0 |
| 23 | 89.9 | 89.9 | 74.0 | 84.7 |
| 35, centre | 95.3 | 95.3 | 81.9 | 94.0 |

**Complete half-row tables, H=72, `320w8-8`.** Each integer is retained RGB code \(K\), giving factor \(K/256\) and firmware blend-to-black weight \(256-K\). Read each cell left to right, from edge toward centre. Row \(71-y\) uses the same value as row \(y\). Shape is 3 and fold cover is 0.40 throughout.

| Physical rows | A at 0.40 | **B at 0.40** | **B at 0.30** |
|---|---|---|---|
| 0–5 | 92, 98, 103, 109, 114, 119 | 92, 98, 103, 109, 114, 119 | 125, 130, 136, 141, 146, 151 |
| 6–11 | 125, 130, 135, 140, 145, 149 | 125, 130, 135, 140, 145, 149 | 156, 161, 166, 170, 174, 177 |
| 12–17 | 152, 154, 164, 175, 184, 193 | 152, 154, 158, 162, 165, 167 | 179, 180, 185, 189, 192, 195 |
| 18–23 | 200, 207, 213, 218, 223, 226 | 170, 172, 174, 177, 179, 181 | 198, 201, 204, 206, 209, 211 |
| 24–29 | 230, 233, 235, 237, 238, 239 | 183, 185, 187, 189, 191, 193 | 214, 216, 218, 221, 223, 225 |
| 30–35 | 240, 241, 241, 242, 242, 242 | 194, 196, 198, 200, 201, 203 | 227, 229, 231, 233, 236, 238 |

### Implementation and stored settings

- **Keep the three controls.** `edgeShade` sets the grey at the old boundary and, through \(F_{\rm end}=F_b(1-s)\), the final depth. Its old \(1-s\) code floor ends at the boundary. `edgeShadeShape` keeps its current main-branch curvature wherever the return cap permits it. `edgeShadeFold` still selects how much fold-back is covered, but its selected row now anchors the start of additional darkening. Update the control help accordingly. At zero strength, bypass shading. If the anchor is already black, further darkening while preserving it is impossible.
- **Build from the actual old rows.** Run the existing solver first. Find the innermost member of the contiguous outer run with the same rounded \(K\). Using only the nominal pooled-group boundary would miss row 13 at 0.40. Use the old physical-row \(K/256\) as the baseline, keep the new factors in double through both passes, average over the existing physical-to-canvas row mapping, then emit \(256-\lfloor256F+0.5\rfloor\). A one-row run has no tail interval to interpolate. Use the current even/odd row-centre and boundary conventions.
- **Match the arithmetic on both sides.** Preserve the current baseline solver’s explicit float32 ray sums. Use binary64 for the new geometry and factor passes, in the same operation order in C++ and TypeScript. Use the existing fold/TIR search, 60 fixed bisections on the descending branch for each signed inverse, `u * sqrt(u)` for easing, and a fixed 48-step cube-root bisection on a bracket containing the root. Disable fused contraction for parity. The inverse coordinates and entry transmissions depend only on geometry and row parity, so they can be generated into flash or built once at boot. Size all arrays to the supported worst case, reuse the per-tube `ROD_GROUPS` workspace, and fail visibly on overflow. The frame loop keeps consuming its existing integer table. [Firmware cache](/home/andrey/_PROJECTS/watches-perf-cheap/firmware/src/render.cpp:1543)
- **Keep `PARAMS_VERSION=33`, the preset fields, and the NVS layout/CRC.** Existing saved values select the revised rendering directly. Their appearance changes deliberately. The implementation should refresh the row/frame expectations for the new rendering and retain host parity checks for both row parities and LCD scaling. I checked the baseline calculation against the supplied 0.40 and 0.80 dumps and reproduced every half-row factor. The proposed tables are read-only model results, without a firmware run or hardware measurement. [Parameter definitions](/home/andrey/_PROJECTS/watches-perf-cheap/sim/src/params.ts:208) · [NVS layout](/home/andrey/_PROJECTS/watches-perf-cheap/firmware/src/params_nvs.h:11)
exit 0
