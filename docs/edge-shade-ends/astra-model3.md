At `edgeShade=0.4`, shape `3`, fold `0.4`, set **`edgeShadeEnd=0.8`** for the requested look. From the outside inward, retained RGB code is **55, 104, 132, 148, 153, 154** out of 256. The last row matches the saved `edgeShade=0.8` result exactly. Five rows inward, the panel is back at today’s grey. At 45°, the rod spreads that last row over **0.174 mm**. At 60°, the fitted rod has **no direct image of the drawn tube**.

## 1. Side-view magnification

Use the 8 mm half-rod, \(R=4\) mm, \(n=1.49\), equivalent air gap \(g=0.87\) mm and physical pitch \(p=0.0825\) mm. The design views are \(\theta=\pm(45+2.5k)^\circ,\ k=0,\ldots,14\), each with weight \(1/30\). This deliberately gives side views the entire vote. Positive tilt sees the negative-offset panel edge. Reversing tilt mirrors the image.

The table gives **apparent widths in µm**. Each cell is **finite row width / row-centre estimate**. The first sums the projected lengths of *all* images of the physical row, including partial images. The second is \(p\sum |dx/dd|\) over all images of its centre. Use the **first** for shading. For example, even group 31 has a visible sliver at 45° although its centre is invisible. Divide either width by 82.5 to get magnification. The 45° column is also the maximum over the chosen views for every listed row. The mean includes the invisible views and the opposite tilt.

| Parity, group \(j\) from centre | 45° = max | 47.5° | 50° | 52.5° | 55° | 57.5° | 60–80° | Weighted mean | Finite-width count \(C_j\) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Even 35, outermost at 72 | 173.78 / 167.21 | 74.10 / 73.47 | 38.60 / 38.44 | 19.26 / 19.20 | 6.87 / 6.85 | 0.28 / 0 | 0 | 10.43 / 10.17 | 41011 |
| Even 34 | 87.11 / 85.69 | 42.79 / 42.47 | 20.47 / 20.36 | 6.71 / 6.66 | 0.21 / 0 | 0 | 0 | 5.24 / 5.17 | 20616 |
| Even 33 | 43.97 / 43.42 | 19.57 / 19.39 | 5.12 / 4.88 | 0.02 / 0 | 0 | 0 | 0 | 2.29 / 2.26 | 9002 |
| Even 32 | 15.56 / 15.28 | 2.64 / 0.90 | 0 | 0 | 0 | 0 | 0 | 0.61 / 0.54 | 2386 |
| Even 31 | 0.41 / 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.014 / 0 | 54 |
| Even 0–30 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Odd 36, outermost at 73 | 795.86 / 257.82 | 95.05 / 94.10 | 49.03 / 48.84 | 25.99 / 25.93 | 11.80 / 11.78 | 2.31 / 2.11 | 0 | 32.67 / 14.69 | 128455 |
| Odd 35, outermost at 71 | 120.79 / 118.05 | 57.09 / 56.65 | 29.14 / 29.01 | 12.84 / 12.79 | 2.43 / 2.02 | 0 | 0 | 7.41 / 7.28 | 29136 |
| Odd 34 | 62.84 / 61.99 | 30.44 / 30.21 | 12.44 / 12.35 | 1.88 / 0.78 | 0 | 0 | 0 | 3.59 / 3.51 | 14103 |
| Odd 33 | 28.56 / 28.19 | 9.84 / 9.69 | 0.83 / 0 | 0 | 0 | 0 | 0 | 1.31 / 1.26 | 5143 |
| Odd 32 | 5.20 / 4.10 | 0.02 / 0 | 0 | 0 | 0 | 0 | 0 | 0.174 / 0.137 | 684 |
| Odd 0–31 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

The parity is that of the **physical span**. A 72-row span is even. The adjacent 71- and 73-row spans use the same odd grid, with different outermost groups. The large 73-row value at 45° comes from two disjoint images, approximately \(x=[-3.783,-3.498]\) and \([-2.528,-2.017]\) mm. A centre-ray estimate misses most of their combined width.

**Physical viewing range.** At 72 rows the panel ends at \(|d|=2.970\) mm. At 45° its direct image occupies \(x=-4.000\) to \(-3.679\) mm. The last row occupies \(-3.853\) to \(-3.679\) mm. Its image shrinks to zero at **58.17°**. The corresponding cutoffs are **56.91°** for 71 rows and **59.37°** for 73. At 60° even the limiting grazing ray lands at \(d=-3.034\) mm. The PMMA-to-air critical angle is **42.16° inside the rod** and applies separately to each ray. Other rays still transmit at 60° but land beyond the drawn rows. I also checked the nominal flat slot E midsection, using its 8.1 mm opening, 0.6 mm land, 3 mm front, 45° bevel and midpoint tape thickness. It clips none of the counted images. A different seating or housing can reduce the visible footprint. [Slot E dimensions](/home/andrey/_PROJECTS/watches-edge-ends/cad/desk/smooth.py:58) · [Gasket and tape dimensions](/home/andrey/_PROJECTS/watches-edge-ends/cad/desk/housing.py:67)

## 2. Exact row factor

Let \(r=0\) be the outermost physical row, increasing toward the centre. Let \(F^0_r\) be the existing solver’s **unrounded** retained code factor at that row. When `edgeShade=0`, use \(F^0_r=1\). Let \(e\) be `edgeShadeEnd`, rounded to binary32, clamped to \([0,1]\), with missing or NaN mapped to zero.

\[
\boxed{F_r=F^0_r\,[1-(e\,e)\,w_r]}
\]

At \(e=0\), take today’s rendering path directly. At \(e=1\), the outermost physical factor is zero. The square calibrates the slider to the requested reference. At \(e=0.8\) the old grey retains \(1-0.8^2=0.36\) of its code, giving \(K=55\). With gamma 2.2, the bare-panel \(L^*\) values across the first six rows are **21.6, 43.9, 55.4, 61.6, 63.5, 63.9**. Most of the perceived recovery occurs in the first two row pitches. Magnification determines which rows to darken. Fresnel transmission enters the appearance prediction separately.

| Physical span | \(w_r\), outside inward at the specified settings | All subsequent rows |
|---|---|---:|
| 72 | 1, 0.502694, 0.219502, 0.058180, 0.001317 | 0 |
| 71 | 1, 0.484040, 0.176517, 0.023476 | 0 |
| 73 | 1, 0.226819, 0.109789, 0.040037, 0.005325 | 0 |

**Normative weight rule for any span, shape and fold.** Use the integer counts, with the displayed decimals above serving as a check.

1. Compute \(K^0_r=\lfloor256F^0_r+0.5\rfloor\) **only to locate the join**. Let \(b\) be the last row of the contiguous run from \(r=0\) having \(K^0_r=K^0_0\). At the specified 72-row setting, \(b=13\).
2. Read the parity-specific counts in edge-first order as \(C[r]\). Set \(u_0=1\). For \(r>0\), set \(u_r=\min((9/16)u_{r-1},\,C[r]/C[0])\). If \(C[0]=0\), use \(u_r=(9/16)u_{r-1}\). The \(9/16\) limit makes the falloff rapid on other spans whose largest side image lies farther inward. It does not bind in the three tabulated profiles.
3. For \(b\ge1\), set \(z=\operatorname{clamp}((b-r)/\min(2,b),0,1)\) and \(w_r=u_r z^2(3-2z)\). This reaches zero with zero slope at the old band boundary, including when a change of fold shortens the band. For the degenerate \(b=0\), set \(w_0=1\) and all other weights to zero. The edge and the old boundary then occupy the same physical row, so the edge endpoint takes precedence. Discrete panel rows still quantise a steep gradient.

## 3. Retained code and apparent lightness

**Complete `320w8-8`, H=72 half-row table.** Row \(71-r\) uses the same code as row \(r\). Each entry is retained \(K/256\).

| Physical rows, edge → centre | `edgeShadeEnd=0.5` | `edgeShadeEnd=0.8` | `edgeShadeEnd=1` |
|---|---|---|---|
| 0–5 | 115, 134, 145, 151, 154, 154 | **55, 104, 132, 148, 153, 154** | 0, 76, 120, 145, 153, 154 |
| 6–13 | 154 × 8 | 154 × 8 | 154 × 8 |
| 14–19 | 164, 175, 184, 193, 200, 207 | same | same |
| 20–25 | 213, 218, 223, 226, 230, 233 | same | same |
| 26–31 | 235, 237, 238, 239, 240, 241 | same | same |
| 32–35 | 241, 242, 242, 242 | same | same |

**Predicted apparent \(L^*\) across the rod.** Uniform white input, referenced to unshaded straight-on centre white. Triples are for \(e=0.5/0.8/1\). A single number applies to all three. A dash means the position has no direct image of the drawn tube. Zero means the ray sees a row commanded black. The 45° column shows the view that drives the design.

| Projected \(x\), mm | 0° | 30° | 45° | 60° |
|---:|---:|---:|---:|---:|
| −3.990 | — | 40.0 | 39.2 / 38.4 / 37.6 | — |
| −3.950 | 68.8 | 51.6 | 48.6 / 44.3 / 40.3 | — |
| −3.780 | 59.3 | 59.7 | **45.2 / 19.6 / 0** | — |
| −3.000 | 71.3 | 63.5 | — | — |
| −2.000 | 88.8 | 63.8 | — | — |
| −1.000 | 94.3 | 80.5 | — | — |
| 0 | 95.3 | 90.3 | — | — |
| +1.000 | 94.3 | 91.1 | — | — |
| +2.000 | 88.8 | 67.2 | — | — |
| +2.130 | 87.0 | 46.3 / 46.0 / 46.0 | — | — |
| +2.140 | 87.0 | 39.5 / 30.1 / 20.6 | — | — |
| +2.1465 | 87.0 | **33.2 / 12.6 / 0** | — | — |
| +3.000 | 71.3 | — | — | — |
| +3.679 | 60.9 | — | — | — |
| +3.84489 | 57.3 | — | — | — |
| +3.94042 | 69.2 | — | — | — |
| +3.97425 | 27.3 / 24.4 / 21.7 | — | — | — |
| +3.97435 | 24.7 / 17.8 / 10.8 | — | — | — |
| +3.97447 | **20.1 / 5.4 / 0** | — | — | — |

For any other \(x\), use \(Y=\tau(x,\theta)(K_r/256)^{2.2}\). Use \(L^*=116\sqrt[3]{Y}-16\) above \(Y=(6/29)^3\), and \(L^*=(24389/27)Y\) below it. Here \(\tau\) is the existing unpolarised curved-surface, base and cover Fresnel product divided by its straight-on centre value. Evaluate the curved interface at incidence \(a\) and the flat base at internal incidence \(h\), defined below. These are direct-light predictions before RGB565 channel quantisation, panel angular emission and room reflections. [Firmware Fresnel model](/home/andrey/_PROJECTS/watches-edge-ends/firmware/src/rod.h)

## 4. Generation and renderer integration

- **Generate one integer table on the host and emit it for both targets.** Key it by rod geometry and physical pitch. For the new table, canonicalise radius and pitch to the nearest \(10^{-6}\) mm, giving exactly the nominal inputs \(4\) and \(0.0825\) here. For each of the 15 positive tilts, take \(N=2^{20}\) projected midpoints \(x_i=R[2(i+0.5)/N-1]\). With angles in radians, compute \(a=\arcsin(x_i/R)\), \(h=\theta+a-\arcsin(\sin(a)/n)\), \(v=n\sin h\), \(B=x_i/(n\cos h)\), and \(d=B-gv/\sqrt{1-v^2}\). Accept only the exposed semicircle \(|\theta+a|\le\pi/2\), a forward path \(\cos h>0\), \(|v|<1\), and a base hit \(|B|\le R\). Count each accepted sample once per parity, using \(j_{\rm even}=\lfloor |d|/p\rfloor\) and \(j_{\rm odd}=\lfloor |d|/p+0.5\rfloor\). Discard groups beyond the largest supported span. Summing counts automatically includes repeat images. The mean width of one physical row is \(C_j(2R/N)/30\), by mirror symmetry. Double \(C_0\) for the odd central row only, since it is its own mirror. The normative table uses the bare rod aperture. [Existing host generator](/home/andrey/_PROJECTS/watches-edge-ends/firmware/tools/gen_rod_rays.py)
- **Apply the multiplier on physical rows.** Run the current solver as written, including its float32 ray sums. Read its pooled factor as \(F^0_r\) but index the new weight by the **actual** physical group. Use binary64 in the displayed operation order with contraction disabled. Average the resulting unrounded \(F_r\) across the current `bs(y)..bs(y+1)-1` physical rows, then emit \(T_y=256-\lfloor256\,\mathrm{mean}(F_r)+0.5\rfloor\). This preserves scaled-LCD behavior. A canvas row covering multiple physical rows receives their mean even when its outermost member is black. Feed \(T_y\) through the existing `lensSrc`, lightest-source factor and `postT` conflict correction. Include `edgeShadeEnd` in the row-cache key and enable shading when either strength is positive. [Firmware `Tube::buildShade`](/home/andrey/_PROJECTS/watches-edge-ends/firmware/src/render.cpp:5352) · [Simulator `edgeShadeRows`](/home/andrey/_PROJECTS/watches-edge-ends/sim/src/render.ts:3197)
- **Storage and compatibility.** Store two `uint32_t` count arrays per distinct geometry in flash, sized for the maximum supported physical group count. Reuse fixed-size or boot-allocated row workspace and fail visibly on a capacity mismatch. Add `edgeShadeEnd` as a float with default `0`, range `0..1`, UI step `0.01`. Append the stored field, advance schema 33 to 34, and migrate old presets and known NVS layouts with the new field zero. Preserve the existing v31/v32 migration chain. [Parameter schema](/home/andrey/_PROJECTS/watches-edge-ends/sim/src/params.ts:208) · [NVS migration](/home/andrey/_PROJECTS/watches-edge-ends/firmware/src/params_nvs.h:11)

I verified the 72-row baseline against every half-row code in the saved `0.4 / 3 / 0.4` dump. Doubling the projected sampling density changed the listed finite widths by at most **0.008 µm**. The angular distribution and squared slider response are design choices. The results are read-only Python predictions for the fitted stack. I made no file or Git changes and opened no serial ports. [Saved row dump](/home/andrey/_PROJECTS/watches-edge-ends/docs/edge-shade-ends/rows-now.txt)
exit 0
