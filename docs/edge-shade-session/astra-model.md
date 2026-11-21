**Keep the present edge depth and change how the shade approaches it.** At 2.7 mm from the centre of the 8 mm rod, where the reported dark band begins, the ideal air-gap stack still transmits **99.2%** of its centre value. The present firmware has already reduced the panel’s RGB code to **0.379**, or about **12% of its unshaded linear luminance** under a gamma‑2.2 panel model. The 0.5 mm plateau therefore understates the width of the visible shade. Much of the preceding ramp already looks dark.

I recommend targeting **\(L^*=91.6\) at the centre and \(30\) at the start of the edge plateau**, with shape \(q=1.5\). On a uniform reference field, the calculated row table takes the centre from \(L^*=100\) to **91**, lifts the shoulder at 2.5 mm from **45 to 55**, and keeps the fold at **30**. These are model predictions for the board. The photograph supports the direction of the change, but cannot establish the board’s optical transfer by itself.

## 1. The rod’s brightness transfer

Let \(x\) be apparent distance from the axis, \(R\) the rod radius, \(n=1.49\), and \(g=0.87\) mm the fitted air-equivalent distance. For an on-axis distant observer, reverse-trace a ray from air through the curved surface. Its angles to the curved normal are \(\alpha\) in air and \(\beta\) inside PMMA. Its angle to the flat-base normal is \(\theta\).

\[
\alpha=\sin^{-1}(x/R),\qquad
\beta=\sin^{-1}(\sin\alpha/n),\qquad
\theta=\alpha-\beta.
\]

For the repository’s equivalent-air geometry, the **signed** panel coordinate is

\[
d(x)=x-\sqrt{R^2-x^2}\tan\theta
       -g\,\frac{n\sin\theta}{\sqrt{1-n^2\sin^2\theta}}.
\]

The fold occurs at the maximum of \(d(x)\). Beyond it, successive apparent positions show panel rows in reverse order. Very close to the rim, the ray can cross the panel centre or leave the drawn tube. At \(n\sin\theta\ge1\), total internal reflection at a PMMA–air base cuts off the direct panel ray. [Repository ray model](/home/andrey/_PROJECTS/watches-edge-shade/docs/physical-tube-model.py)

For a lossless interface \(n_1\to n_2\), write \(c_i=\cos i\), \(c_t=\cos t\), with \(n_1\sin i=n_2\sin t\). The two power reflectances are

\[
r_s=\left(\frac{n_1c_i-n_2c_t}{n_1c_i+n_2c_t}\right)^2,\qquad
r_p=\left(\frac{n_2c_i-n_1c_t}{n_2c_i+n_1c_t}\right)^2.
\]

Let \(r_{c,j}\) denote curved-surface reflectance and \(r_{b,j}\) flat PMMA–air reflectance for polarization \(j\). The direct, unpolarised, single-pass transfer is

\[
T_m(x)=\frac12\sum_{j=s,p}(1-r_{c,j})(1-r_{b,j})^m .
\]

Here \(m=0\) represents an index-matched adhesive and cover, \(m=1\) counts the curved surface and one flat air boundary, and \(m=2\) includes the return from air into cover glass of index 1.49. For \(m=1,2\), set \(T_m=0\) beyond base TIR. The products are taken per polarization before averaging. This matters near the rim, and the LCD’s actual polarization can shift the result. [Fresnel equations, University of Arizona](https://webs.optics.arizona.edu/gsmith/Fresnel.html)

### Direct transmission for 8 mm and 6 mm rods

The first three transmission columns are absolute Fresnel power fractions. The final column, \(\tau=T_2(x)/T_2(0)\), is the centre-normalised transfer used for the firmware calculation. Both diameters have the same ideal angular transfer at a given \(x/R\).

| \(x/R\) | \(x\), 8 mm | \(x\), 6 mm | Matched \(T_0\) | One air boundary \(T_1\) | Air gap + cover \(T_2\) | Relative \(\tau\) |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.000 | 0.000 | .961 | .924 | .888 | 1.000 |
| .500 | 2.000 | 1.500 | .960 | .923 | .887 | .998 |
| .675 | 2.700 | 2.025 | .954 | .917 | .881 | .992 |
| .750 | 3.000 | 2.250 | .946 | .909 | .874 | .984 |
| .850 | 3.400 | 2.550 | .921 | .884 | .849 | .955 |
| .875 | 3.500 | 2.625 | .907 | .870 | .835 | .940 |
| .900 | 3.600 | 2.700 | .888 | .850 | .815 | .918 |
| .920 | 3.680 | 2.760 | .865 | .826 | .791 | .891 |
| .950 | 3.800 | 2.850 | .806 | .764 | .728 | .819 |
| .975 | 3.900 | 2.925 | .699 | .644 | .600 | .675 |
| .990 | 3.960 | 2.970 | .542 | .434 | .357 | .402 |
| .994 | 3.976 | 2.982 | .458 | .219 | .112 | .126 |
| .995 | 3.980 | 2.985 | .429 | 0 | 0 | 0 |
| 1.000 | 4.000 | 3.000 | 0 | 0 | 0 | 0 |

**Magnification contributes no independent brightness penalty.** A lossless imaging system conserves radiance divided by \(n^2\). A resolved uniform panel patch covers a different apparent width, while its luminance in the same external medium is conserved. Multiplying by \(1/M\), \(1/M^2\), or \(|d'(x)|\) would introduce a spurious dark zone at the fold. Angular LCD emission, pupil clipping and housing occlusion can reduce the observed signal. [Radiance and étendue, Northeastern University](https://ece.northeastern.edu/courses/eece4646/dimarzio/7105/slides12.pdf)

**Reflections depend on what surrounds the watch.** A useful observation model is \(Y_{\rm seen}(x)=T_m(x)Y_{\rm panel}(d,\theta)+B(x)\), where \(B\) includes the curved-surface reflection of the room or slot, internal reflected paths and camera flare. A dark slot returns little light as panel transmission falls. A bright surround can produce a bright rim in the same place. TIR extinguishes the direct path, while the reflected path can still carry scene light.

| Rod | Central \(M\), equivalent air | Fold \(x\) | Largest inner-branch \(d\) | Base TIR starts | Fold \(x\) at 350 mm | Base TIR at 350 mm |
|---|---:|---:|---:|---:|---:|---:|
| 8 mm | 1.77 | 3.679 mm | 1.922 mm | 3.978 mm | 3.678 mm | 3.979 mm |
| 6 mm | 1.89 | 2.657 mm | 1.238 mm | 2.984 mm | 2.656 mm | 2.984 mm |

For the 350 mm check I placed the eye on axis, 350 mm above the base. The outgoing ray’s angle to the curved normal becomes \(\alpha+\tan^{-1}[x/(350-\sqrt{R^2-x^2})]\). The largest visible inner-branch panel offset changes by 0.019 mm on the 8 mm rod and 0.013 mm on the 6 mm rod. The distant-eye approximation is adequate for the proposed 0.0825 mm row table.

The important geometry uncertainty is **where the fitted 0.87 mm resides**. A real layer of thickness \(h_i\) and index \(n_i\) contributes \(h_i\tan[\sin^{-1}(n\sin\theta/n_i)]\) to lateral displacement. A central magnification fit constrains approximately \(\sum h_i/n_i\). Different stacks with that same sum can have different outer branches. A fully matched base also removes the base-air TIR. I use the repository’s equivalent-air map for the proposed rows and treat its fold and TIR positions as conditional predictions. [Physical stack notes](/home/andrey/_PROJECTS/watches-edge-shade/docs/physical-tube-optics.md)

## 2. What the photograph attributes to firmware and optics

I decoded the supplied samples with \(u=v/255\) and \(Y=u/12.92\) for \(u\le0.04045\), otherwise \(Y=[(u+0.055)/1.055]^{2.4}\). I used sample index 21.5 as the provisional centre, averaged mirrored samples **after** decoding, and normalised each trace by the mean of its central four decoded samples. I excluded the housing transition. Decoding an already-combined camera brightness gives an approximate linear trace, particularly for the blue liquid. The supplied scale and the visible opening make the \(x\) registration approximate as well. [sRGB specification](https://www.w3.org/Graphics/Color/srgb) · [Board photograph](/home/andrey/_PROJECTS/watches-edge-shade/docs/edge-shade-session/photo-shade-0.7.png)

The firmware blends RGB565 **codes** toward black. For the old profile I used \(s=.70\), power .8, fold cover .4 and an assumed panel response \(Y\propto{\rm code}^{2.2}\). Thus its linear factor is \(A=(1-.70w_{\rm old})^{2.2}\). The residual \(C=Y_{\rm photo}/(A\tau)\) estimates how much brightness remains after accounting for firmware and ideal Fresnel losses. It includes the drawn material and centre highlight, angular panel response, registration error and room light. [Current row calculation and compositor](/home/andrey/_PROJECTS/watches-edge-shade/sim/src/render.ts:2252)

| Apparent \(x\), mm | Photo liquid | Photo empty | Old firmware \(A\) | Ideal rod \(\tau\) | Residual \(C\), liquid / empty |
|---:|---:|---:|---:|---:|---:|
| 0.87 | .459 | .443 | .713 | 1.000 | .64 / .62 |
| 1.44 | .272 | .279 | .457 | 1.000 | .60 / .61 |
| 2.02 | .133 | .131 | .255 | .998 | .52 / .52 |
| 2.60 | .086 | .061 | .132 | .994 | .66 / .46 |
| 2.79 | .082 | .050 | .108 | .990 | .77 / .47 |
| 2.98 | .073 | .047 | .090 | .984 | .83 / .53 |
| 3.17 | .059 | .044 | .078 | .975 | .77 / .58 |

A fraction of darkness needs a convention because these losses multiply. Using **log attenuation**, the firmware share is \(\ln A/\ln Y_{\rm photo}\) and the ideal rod share is \(\ln\tau/\ln Y_{\rm photo}\). Across **2.60–3.17 mm**, firmware accounts for approximately **83–92%** of the liquid trace’s attenuation and **72–82%** of the empty trace’s. Ideal Fresnel loss accounts for **less than 1%** of either trace’s log attenuation there. At **2.02 mm**, the firmware share is about **67–68%**, and both traces have a residual factor near .52. The bright drawn centre and darker drawn shoulders are credible contributors of that size. The different liquid and empty residuals show why assigning all of it to the acrylic would give a misleading result.

These percentages apply to the broad dark shoulder. In the last 0.1 mm, optical transmission really does collapse, rows repeat, and some rays leave the tube. The photograph does not resolve a reliable firmware-versus-rod fraction in that strip.

## 3. Perceptual target and firmware row factors

Use two adjustable parameters. Keep the existing fold cover fixed at .4 for this design.

| Parameter | Range | Recommended | Meaning |
|---|---|---:|---|
| Strength \(s\) | 0–1 | .70 | Sets edge lightness \(L_e^*=100(1-s)\). Also trims the bright centre to \(L_c^*=100-12s\). |
| Shape \(q\) | .5–3, in steps of .5 | 1.5 | \(q=1\) gives equal lightness change per apparent mm. \(q>1\) keeps the shoulder lighter and gives a gentler slope at the centre. |

The white reference \(Y_n\) is an unshaded uniform reference field viewed through the rod centre. The target describes that field. Digits, blue liquid and the specular highlight keep their own contrast. The centre trim is a design choice responding to the board verdict.

With \(x_f\) the fold and \(x_t\) the base TIR onset, set \(x_o=x_f+.4(x_t-x_f)\), \(d_p=d(x_o)\), and \(x_e=x_{\rm inner}(d_p)\). On the 8 mm rod these are \(x_o=3.799\), \(d_p=1.879\), and \(x_e=3.485\) mm. Define

\[
L^*(x)=L_c^*-(L_c^*-L_e^*)\min(x/x_e,1)^q,\qquad
Y_t(x)=
\begin{cases}
[(L^*(x)+16)/116]^3,&L^*(x)>8,\\
L^*(x)/(24389/27),&L^*(x)\le8 .
\end{cases}
\]

For a singly seen position the required **linear panel factor** is \(Y_t/\tau\), subject to available panel output. The corresponding **RGB code factor** is \((Y_t/\tau)^{1/2.2}\). Omitting this last conversion would darken the shoulder a second time. [CIE lightness definition](https://cie.co.at/eilvterm/17-23-076)

**One factor per physical row.** To resolve the fold, sample apparent \(x\) uniformly and group all direct rays that land on the same panel row. Share one factor across the plateau rows. If \(S_k\) is the set of apparent samples assigned to group \(k\), the least-squares linear panel factor, code factor and firmware weight are

\[
a_k=\frac{\sum_{x\in S_k}\tau(x)Y_t(x)}
          {\sum_{x\in S_k}\tau(x)^2},\qquad
F_k=\operatorname{clip}\!\left(a_k^{1/2.2},\,1-s,\,1\right),\qquad
w(d)=
\begin{cases}
(1-F_k)/s,&s>0,\\
0,&s=0.
\end{cases}
\]

This minimises squared error in observed relative luminance per unit **apparent width** before clipping. A repeated row receives one realizable command. The clamp preserves the existing maximum code-darkening meaning of \(s\). With a measured additive term \(b(x)=B(x)/Y_n\), use \(Y_t-b\) in the numerator. Reject TIR and rays outside the drawn tube before accumulation.

For the 72-row tube I used pitch \(p=.0825\) mm and 8,192 midpoint samples on \(0<x<4\) mm. A ray with \(|d|<36p\) enters group \(k=\min(\lfloor|d|/p\rfloor,\operatorname{round}(d_p/p))\). The plateau group is 23. Repeating with 65,536 samples gave identical quantised factors for every row.

### 320w8-8 row table

Each entry is the **retained RGB code numerator** \(K=\operatorname{round}(256F_k)\). The panel factor is **\(K/256\)**. The existing blend-toward-black compositor takes **\(256-K\)**. Row numbers are zero-based, and each listed pair has the same factor. The last range covers all 26 outer rows.

| Panel rows | \(K\) | Panel rows | \(K\) | Panel rows | \(K\) |
|---|---:|---|---:|---|---:|
| 35, 36 | 230 | 27, 44 | 193 | 19, 52 | 132 |
| 34, 37 | 228 | 26, 45 | 187 | 18, 53 | 124 |
| 33, 38 | 225 | 25, 46 | 180 | 17, 54 | 115 |
| 32, 39 | 221 | 24, 47 | 172 | 16, 55 | 106 |
| 31, 40 | 216 | 23, 48 | 165 | 15, 56 | 97 |
| 30, 41 | 211 | 22, 49 | 157 | 14, 57 | 88 |
| 29, 42 | 206 | 21, 50 | 149 | 13, 58 | 78 |
| 28, 43 | 200 | 20, 51 | 141 | 0–12, 59–71 | 77 |

| Apparent \(x\), mm | Old \(L^*\) | Target \(L^*\) | Predicted \(L^*\) with quantised rows |
|---:|---:|---:|---:|
| 0.00 | 100.0 | 91.6 | 91.2 |
| 1.00 | 84.5 | 82.1 | 82.9 |
| 2.00 | 58.0 | 64.8 | 65.0 |
| 2.50 | 45.2 | 54.2 | 55.2 |
| 2.70 | 40.7 | 49.6 | 48.3 |
| 3.48 | 31.1 | 30.1 | 31.6 |
| 3.68, fold | 30.2 | 30.0 | 30.3 |
| 3.80, outer branch | 28.9 | 30.0 | 29.4 |
| 3.90, outer branch | 30.3 | 30.0 | 37.3 |
| 3.96, outer branch | 63.3 | 30.0 | 59.6 |

The main compromise is visible in the last two rows. At 3.96 mm the rod shows a panel position only about 0.38 mm from centre. Driving that row dark enough to hold \(L^*=30\) at the rim would darken the central image. The calculated profile preserves the broad shoulder improvement and accepts a narrow outer rebound. At 3.90 mm that rebound is **7 \(L^*\) lighter than the current profile**. Its visibility on the real watch depends on the slot and the actual base stack.

**Deterministic implementation.** Stream the fixed midpoint grid into two statically sized sums per row group, sized for the largest supported tube. Rebuild the table only on geometry or parameter changes. The existing square-root/division form of `rodScreen` supplies the ray and Fresnel cosines. Half-step \(q\) needs only multiplication and square root. A fixed 24-step bisection for \(F^{11}=a^5\) implements the gamma‑2.2 inverse on \(0\le a\le1\). The frame loop consumes the existing integer shade table. Capacity overflow should fail visibly. [Firmware row builder](/home/andrey/_PROJECTS/watches-edge-shade/firmware/src/render.cpp:4245)

## 4. The single measurement to take

**Take one on-axis, locked-exposure RAW photograph at 35 cm with `edgeShade=0`, showing three long bands along the same rod: panel black, uniform 50% neutral code, and uniform white.** Each band should span the full tube width, with enough length to average away individual pixels. Use the assembled housing and normal room lighting, disable the drawn glass, digits and highlights for this frame, and expose below white clipping.

From linear camera values \(I_0(x), I_{50}(x), I_{100}(x)\), compute

\[
\tau_{\rm assembled}(x)=
\frac{I_{100}(x)-I_0(x)}{I_{100}(0)-I_0(0)},\qquad
\gamma_{\rm eff}(x)=
\frac{\ln[(I_{50}(x)-I_0(x))/(I_{100}(x)-I_0(x))]}{\ln(0.5)} .
\]

The black band estimates the additive floor, including panel black and reflections. The white-minus-black trace measures the assembled rod, slot and angular panel response together. The middle band checks the assumed code-to-light conversion. That single frame would determine whether the shoulder needs appreciable optical compensation and supply the transfer the firmware actually needs. The separate contributions of adhesive, surface finish and LCD polarization would remain unresolved.
