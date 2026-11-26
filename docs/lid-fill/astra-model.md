**Verdict:** the reported fog is real. The current fill is too weak and independent of liquid opacity. However, the proposed flat-plane law also keeps the rear half too dark: the curved dish shortens its liquid paths substantially. The front rim requires grazing reflection and secondary surface hits; the back contact line should normally approach the backing colour, not acquire a dark stroke.

**Model and assumptions**

- \(R=20\) px; \(n_\mathrm{air}=1\), \(n_\mathrm{water}=1.333\), \(n_\mathrm{glass}=1.5\).
- Parallel, zero-thickness glass walls: refraction and incoherent Fresnel reflections retained; wall offsets ignored. This is the permitted thin-wall approximation, not a thick cylindrical-glass simulation.
- Main tables assume **glass with air behind it**, then a diffuse backing. An optically coupled backing gives different TIR behaviour; comparison below.
- Infinite liquid column below the meniscus; no foam, marks, roughness or caustics.
- Colours use the renderer’s blend/luma units, not a calibrated sRGB-to-radiance conversion. Absolute apparent luma is conditional on illumination.
- Pale backing and front-room illumination calibrated to the supplied dry/body measurements, \(197/18\): backing source \(B=221.38\), front environment \(E=50.79\). Dark-back case: dry luma \(16\), corresponding source \(B=10.20\). Black/clear liquid intrinsic luma \(C_l=0\); “light liquid” examples explicitly use \(C_l=160\).
- Fresnel and Snell equations are unpolarized dielectric equations. [Reference](https://www.pbr-book.org/4ed/Reflection_Models/Specular_Reflection_and_Transmission)

The supplied \(t\) becomes effective Beer–Lambert transmission:

\[
\lambda=\ell/(2R),\qquad a=t^\lambda,\qquad
C_\mathrm{segment}=(1-a)C_l+aC_\mathrm{destination}.
\]

Reflected and transmitted branches were both traced, including repeated wall reflections. Increasing the board trace depth from 60 to 100 events changed the reported values negligibly.

The renderer-compatible surface is

\[
A=\frac{R}{\cos\theta},\quad
c(y,z)=A-\sqrt{A^2-y^2-z^2},\quad
x=c(y,z)-z\tan\tau .
\]

Use \(c=0\) at \(\theta=90^\circ\). This is a **sheared spherical cap**, preserving the documented ring projection. At nonzero tilt, \(\theta\) is its curvature parameter, not a uniform physical contact angle: at the board pose, its front/back local contact angles are approximately \(82.4^\circ/59.3^\circ\). A real equilibrium meniscus needs a gravity/contact-angle solution.

\[
\delta=e-\tau,\quad T=\tan\tau+\tan\delta,\quad
x'=c-zT,\quad z_R=\sqrt{R^2-y^2}.
\]

\[
s=x'-(h_m-z_RT),\quad W=2z_RT,\quad u=s/W.
\]

Here \(s=0\) is the front contact line; \(s=W\) is the back.

**Board trace: \(e=24^\circ,\tau=13^\circ,\theta=70^\circ\), \(W=17.010\) px**

\(F_s\) is the first **liquid–air surface** reflectance encountered. Below the contact line, a ray can reach the back wall without encountering that surface.

| Position | \(s\), px | \(\lambda_0\) | \(F_s\) | First mirror destination | Ink/pale | Clear/pale | Ink/dark | Clear/dark |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| Below front | −3 | 1.010 | — | Front glass reflects room | 18 | 165 | 3 | 11 |
| Below front | −1 | 1.010 | — | Same | 18 | 165 | 3 | 11 |
| \(u=0^+\) | 0 | 1.527* | 69.0% | Dish again | 48 | 119 | 6 | 11 |
| \(u=.25\) | 4.252 | .662 | 10.9% | Dry back wall | 57 | 174 | 7 | 14 |
| \(u=.50\) | 8.505 | .369 | 5.7% | Dry back wall | 87 | 185 | 8 | 14 |
| \(u=.75\) | 12.757 | .164 | 4.0% | Dry back wall | 135 | 193 | 10 | 14 |
| \(u=.90\) | 15.309 | .062 | 3.4% | Dry back wall | 171 | 197 | 12 | 15 |
| \(u=1^-\) | 17.010 | 0 | 3.1% | Dry back wall | 198 | 200 | 13 | 15 |
| Above back | 18.010 | 0 | — | Glass reflections | 196 | 197 | 16 | 16 |
| Above back | 20.010 | 0 | — | Glass reflections | 196 | 197 | 16 | 16 |

\(*\) \(\lambda_0\) is liquid distance to the first wall, including any preceding surface reflection. At this sample the wall totally internally reflects: the transmitted branch subsequently remains trapped between ideal parallel walls. Its total liquid path is unbounded; the luma includes absorption along subsequent traversals.

The actual first optical interface is the outside front glass:

| Interface, board pose | Reflectance |
|---|---:|
| First air–glass face | 4.00% |
| Complete dry glass slab | 7.70% |
| Complete glass slab entering liquid | 4.32% |

Across the requested poses, these ranges are respectively \(4.00–4.57\%\), \(7.69–8.75\%\), \(4.32–4.91\%\).

**Sanity comparison**

The proposed flat law gives

\[
F_\mathrm{flat}=0.0949,\quad
\lambda_\mathrm{flat}=1.20253(1-u),\quad
Y_\mathrm{flat}=197\,[F_\mathrm{flat}+(1-F_\mathrm{flat})\,0.08^{\lambda_\mathrm{flat}}].
\]

| Model / \(u\) | 0 | .25 | .50 | .75 | .90 | 1 |
|---|---:|---:|---:|---:|---:|---:|
| Today: supplied measured range† | 120–145 | 120–145 | 120–145 | 120–145 | 120–145 | 120–145 |
| Proposed flat law, including reflection | 27 | 37 | 58 | 102 | 150 | 197 |
| Curved trace, air-backed glass | 48 | 57 | 87 | 135 | 171 | 198 |
| Curved trace, optically coupled backing‡ | 50 | 58 | 87 | 134 | 170 | 197 |

† The brief supplies a whole-lid range, not six separate samples. These are not invented per-position measurements.

‡ Recalibrated to the same dry/body \(197/18\), with the rear interface terminating on the backing instead of glass–air reflection.

- “Black until \(u\approx.77\)” is incorrect even for the proposed law. At \(u=.77\), **transmission is already approximately 50%**. It crosses 10% near \(u=.24\).
- Relative to the flat law, curved paths are approximately **27% longer at the front**, then **27%, 39%, 46%, 49% shorter** at \(u=.25,.5,.75,.9\).
- A reported prototype sequence \(58\rightarrow21\), if ordered front-to-back across the lid, is not this physical profile. The rear limit must recover the backing.
- `liquidHi=#000000` makes today’s neutral “blick” black. It is an absorbing overlay, not a reflection of the pale back or room.

**Dish projection matters**

\[
u=\frac{z_R-z}{2z_R}+\frac{c(y,z)-h_m}{2z_RT}.
\]

At the board centre row:

| Quantity | Flat assumption | Curved cap |
|---|---:|---:|
| Screen \(u\) of physical dish centre \(z=0\) | .500 | .293 |
| Physical \(z/R\) at screen \(u=.500\) | 0 | −.362 |
| Maximum displacement from flat projection | 0 | 3.53 px |

A 3.53 px displacement within a 17 px lid is material.

For off-centre rows, \(W\) and flat-surface liquid lengths scale with

\[
q=z_R/R=\sqrt{1-(y/R)^2}.
\]

The curved trace does **not** scale exactly by \(q\): its normal gains a \(y\)-component, refraction leaves the original row plane, and wall incidence changes. Use

\[
\mathbf n\propto
\left(1,-\frac y{\sqrt{A^2-y^2-z^2}},
\tan\tau-\frac z{\sqrt{A^2-y^2-z^2}}\right)
\]

and intersect the refracted ray with \(y^2+z^2=R^2\). Chord scaling is an approximation for interior rows, not the wall fringe.

For \(R=2.3\) mm and capillary length \(2.7\) mm, \(Bo=0.726\). An upright axisymmetric Young–Laplace calculation gives:

| \(\theta\) | Spherical rise, px | Gravity-corrected rise, px |
|---|---:|---:|
| 40° | 9.33 | 8.77 |
| 70° | 3.53 | 3.37 |
| 90° | 0 | 0 |

Thus gravity changes the upright \(70^\circ\) rise by about **0.16 px**, much less than omitting the dish entirely. This does not validate the tilted cap’s contact angles. [Capillary-length reference](https://farside.ph.utexas.edu/teaching/336L/Fluidhtml/node43.html)

**Rims and TIR**

\[
\theta_{\mathrm{critical,water\to air}}=48.61^\circ.
\]

With parallel glass followed by air, the intermediate glass does not eliminate this effective escape limit. The actual TIR occurs at the glass–air interface. An optically coupled backing removes that particular trap.

| Board feature | Physical extent | Luma / interpretation |
|---|---:|---|
| Near-side grazing shoulder, \(F_s>20\%\) | First **1.94 px** inside lid | Ink/pale roughly 48–58; strong reflection can still look dark because it reflects another part of the dish |
| Reflected ray hits dish again | First **1.61 px** | A constant pale mirror source is wrong here |
| Primary rear-wall TIR | First **0.030 px** | Subpixel; do not draw a 1 px TIR stripe |
| Wet-front surface TIR below contact | **None** at board pose | Below-front rays directly cross the liquid |
| Rear recovery to ≥90% of dry pale luma | Last **1.28 px** | Natural absorption taper, not a dark line |

Point values at a contact are not pixel values. Integrating a 1 px footprint centred on the front line gives:

| Material/backing | Front-contact pixel luma |
|---|---:|
| Ink / pale | 34 |
| Clear / pale | 158 |
| Clear / dark | 12 |
| Light liquid \(C_l=160,t=.8\) / dark | 45 |

For that light-liquid example, the body is 43, mid-lid 27, and rear limit 16. A brighter room changes the reflected rim; backing contrast alone does not determine its brightness.

- **Front contact line:** junction of wet glass/body and dry-glass/surface view, plus the near-side grazing shoulder. A 1 px antialiased contact edge is reasonable; **1 px alone is too narrow** for the board’s approximately 2 px optical shoulder. Its source colour must follow the reflected scene.
- **Back contact line:** liquid depth tends to zero as the meniscus meets the wall. For ink/pale, it recovers pale backing. For light liquid/dark, it returns toward dark backing. Neither demands an extra universal dark contour.
- Today’s 0.5 px back stroke has integrated opacity approximately
  \[
  .56\cdot.45\cdot.5=.126.
  \]
  Over pale 197 with a nearly black stroke, it can add an artificial **approximately 25-luma notch**. Its principal error is tone, not insufficient width.
- At \(\theta=40^\circ\), the projected dish folds below the front contact by **0.52–4.92 px** across the requested poses. Wet-front TIR can extend approximately **1.28–5.87 px below** the contact. A fixed 1 px rim cannot represent those cases.

The mirror direction is

\[
\mathbf m=\mathbf d+2[-\mathbf d\cdot\mathbf n]\mathbf n.
\]

Trace its nearest intersection: another surface hit takes precedence over a wall. At \(\theta=40^\circ\), the rear portion generally reflects the **front environment**, with the switch near \(u=.41–.58\); “mirror = dry back” is not general.

**Cheap renderer law**

Use physical absorption plus an explicit reflected-scene term:

\[
a=t^{\lambda(u,y)},\qquad
C=(1-F)\,[aB+(1-a)C_l]+F\,M.
\]

Equivalent single composite:

\[
A=1-(1-F)a,\qquad
P=(1-F)(1-a)C_l+FM,\qquad
C_\mathrm{out}=(1-A)B+P.
\]

Here \(C_l\) is the intrinsic lit liquid colour, **before** mixing in `tubeBack`. Reusing the already-translucent body row double-counts backing transmission.

For a mirror ray hitting the dish again:

\[
M=F_2M_2+(1-F_2)\,[a_2B_2+(1-a_2)C_l].
\]

Do not replace \(M\) with `liquidHi`, or assume it always equals the backing. For an actually trapped absorbing branch, its limiting contribution is \(C_l\).

A direct surface intersection requires only a quadratic. With \(b=A-x'\):

\[
(1+T^2)z^2-2bTz+b^2-A^2+y^2=0.
\]

Choose the nearest valid root inside the bore, satisfying \(b-Tz\ge0\); include front-wall entry when \(s<0\). This handles the fold instead of clamping it away.

Recommended execution:

| Stage | Work |
|---|---|
| Row setup | Build **33 samples** over the visible surface plus its below-front shoulder; solve geometry, Fresnel, attenuation and mirror destinations |
| Sampling | Prefilter contact/TIR discontinuities over a 1 px footprint |
| Pixel | One interpolating LUT lookup; existing premultiplied blend |
| Glass | Apply once; do not add a second dry-glass veil over coefficients already containing glass |
| Marks | Use the same direct transmission coefficient; reflected backing is not transmission of the original rear mark |
| Foam | Use liquid distance to the foam, not automatically the full distance to the back wall |

A **single static 33-entry scratch LUT**, rebuilt for each processed row/pass, is sufficient: `(A, Pr, Pg, Pb)` as float32 = **528 bytes**. Retaining all rows is optional and must use a fixed worst-case allocation. Any ray-work scratch must likewise be statically bounded; overflow must be visible, never trigger another allocation.

The closed-form law is cheap; complete secondary-interface handling adds setup cost. No frame-time claim is implied. Keep all square roots, Fresnel evaluation and powers outside the pixel loop.

For TypeScript/C++ parity: identical branch ordering and shared single-precision math approximations; explicit `Math.fround` intermediates in TS; no C++ contraction/fast-math differences. `Math.fround` alone does not guarantee that platform `log`/trig implementations match.

Preserve the clear-liquid style with the existing artistic fill as a floor:

\[
a_\mathrm{old}=\min(1,1.6\,\texttt{surfaceBand})\,
\texttt{surfaceFill}\,(1-u),
\]

\[
A_\mathrm{abs}=\max\left(1-t^\lambda,\ a_\mathrm{old}\right).
\]

Use this in place of \(1-a\) in the surface composite. At \(t=.8\), board mid-lid physical absorption is only **.079**, versus old fill **.141**: the old appearance largely survives. For ink, physical absorption dominates.

| Control | Proposed meaning |
|---|---|
| `surfaceBand` | Strength of the optional legacy fill/cosmetic accents; must not gate physical absorption |
| `surfaceFill` | Additional artistic fill through the floor above; zero does not make opaque ink transparent |
| `surfaceRim` | Optional contact accent only; physical grazing shoulder remains |
| `surfaceBlick` | Room/key reflection accent over the Fresnel base; remove the compulsory \(4u(1-u)\) tent |
| `surfaceTone` | Shift intrinsic liquid tone; leave backing transmission and reflected environment separate |

Remove the forced dark back contour from the physical base. Keep antialiased contact coverage; let optical depth and reflected direction determine the two shoulders.

**Full requested centre-plane sweep**

Every cell is ordered:

\[
s=(-3\text{ px},\ 0^+,\ .5W,\ .9W,\ W+3\text{ px}).
\]

`λ₀` and `Fs` omit the fifth value, which is always \(0\) and “no liquid-surface hit”. `*` marks subsequent rear-wall TIR; total primary liquid path then continues beyond the listed first-wall distance. `Fs` is percent; `—` means no liquid-surface intersection.

`Ink/P` = \(t=.08\), pale back; `Clear/P` = \(t=.8\), pale back; `Clear/D` = \(t=.8\), dark back. Same illumination calibration throughout.

**\(\theta=40^\circ\)**

| \(e/\tau\) | \(\lambda_0\), four positions | \(F_s\%\), four positions | Ink/P | Clear/P | Clear/D |
|---|---|---|---|---|---|
| 15/0 | 2.23*/.33/.12/.02 | 100/4/2/2 | 2/93/147/187/195 | 2/186/194/196/196 | 2/14/15/13/16 |
| 15/13 | 1.60*/.29/.11/.02 | 100/5/3/2 | 2/102/150/188/197 | 2/188/193/196/197 | 2/14/13/14/16 |
| 15/25 | 1.16/.31/.12/.02 | 100/7/3/3 | 13/100/147/189/197 | 159/187/192/198/197 | 11/14/13/15/16 |
| 24/0 | 1.56*/.68/.21/.03 | 100/8/2/2 | 2/46/118/181/193 | 2/155/189/196/196 | 2/15/15/15/16 |
| 24/13 | 1.20/.54/.18/.03 | 100/7/2/2 | 12/64/125/183/196 | 156/179/189/196/197 | 11/14/14/14/16 |
| 24/25 | 1.00/.52/.18/.03 | —/8/3/2 | 18/69/128/184/197 | 166/181/190/198/197 | 11/14/13/15/16 |
| 30/0 | 1.24/1.07*/.27/.04 | 100/13/2/2 | 11/22/99/175/192 | 153/29/182/194/196 | 11/5/15/15/15 |
| 30/13 | 1.02/.75/.23/.04 | —/10/2/2 | 17/47/114/180/196 | 165/168/189/195/197 | 11/14/14/14/16 |
| 30/25 | 1.00/.67/.21/.03 | —/10/2/2 | 18/56/118/181/197 | 166/175/190/195/197 | 11/13/14/14/16 |
| 40/0 | 1.14/2.73*/.40/.06 | —/35/2/2 | 14/15/48/159/189 | 159/26/130/185/189 | 11/6/18/17/13 |
| 40/13 | 1.06/1.31*/.31/.05 | —/19/2/2 | 16/20/93/174/194 | 163/39/184/193/196 | 11/6/15/14/16 |
| 40/25 | 1.02/1.00/.27/.04 | —/16/2/2 | 18/33/102/177/196 | 165/159/187/195/197 | 11/13/14/14/16 |

**\(\theta=70^\circ\)**

| \(e/\tau\) | \(\lambda_0\), four positions | \(F_s\%\), four positions | Ink/P | Clear/P | Clear/D |
|---|---|---|---|---|---|
| 15/0 | 1.02/1.21*/.32/.05 | —/58/9/5 | 18/64/99/174/194 | 165/107/185/197/196 | 11/10/14/15/16 |
| 15/13 | 1.00/.95/.27/.05 | —/56/9/5 | 18/75/110/178/197 | 166/175/190/198/197 | 11/14/14/15/16 |
| 15/25 | 1.01/.92/.27/.05 | —/66/11/7 | 18/81/112/178/197 | 164/178/190/196/197 | 10/14/14/13/16 |
| 24/0 | 1.05/2.10*/.45/.07 | —/65/6/3 | 17/41/69/162/193 | 164/75/171/192/193 | 11/9/15/15/13 |
| 24/13 | 1.01/1.53*/.37/.06 | —/69/6/3 | 18/48/87/171/196 | 165/119/185/197/197 | 11/11/14/15/16 |
| 24/25 | 1.00/1.23/.35/.06 | —/59/6/4 | 18/56/92/172/197 | 166/168/186/195/197 | 11/13/14/13/16 |
| 30/0 | 1.08/2.16*/.52/.08 | —/35/4/3 | 16/35/49/151/192 | 163/63/147/186/192 | 11/8/17/16/13 |
| 30/13 | 1.02/1.55*/.42/.07 | —/37/4/3 | 17/37/75/166/196 | 165/70/182/196/196 | 11/8/14/15/13 |
| 30/25 | 1.00/1.25/.38/.07 | —/32/4/3 | 18/44/83/169/197 | 166/162/185/195/197 | 11/13/14/13/16 |
| 40/0 | 1.14/2.38*/.67*/.11* | —/13/3/2 | 14/30/10/8/189 | 159/30/10/8/189 | 11/6/5/5/13 |
| 40/13 | 1.06/1.64*/.51/.09 | —/14/3/2 | 16/28/59/157/193 | 163/31/173/192/193 | 11/6/14/15/13 |
| 40/25 | 1.02/1.30/.44/.08 | —/12/3/2 | 18/34/71/164/196 | 165/153/182/196/197 | 11/13/14/15/16 |

**\(\theta=90^\circ\)**

| \(e/\tau\) | \(\lambda_0\), four positions | \(F_s\%\), four positions | Ink/P | Clear/P | Clear/D |
|---|---|---|---|---|---|
| 15/0 | 1.02/1.38/.69/.14 | —/21/21/21 | 18/49/69/143/194 | 165/150/168/184/196 | 11/14/15/16/15 |
| 15/13 | 1.00/1.16/.58/.12 | —/21/21/21 | 18/53/80/159/197 | 166/164/180/195/197 | 11/13/14/15/16 |
| 15/25 | 1.01/1.05/.53/.11 | —/21/21/21 | 18/55/85/163/197 | 164/167/183/196/197 | 10/13/14/15/16 |
| 24/0 | 1.05/1.46/.73/.15 | —/9/9/9 | 17/26/43/114/193 | 164/127/145/163/196 | 11/14/16/18/15 |
| 24/13 | 1.01/1.20/.60/.12 | —/9/9/9 | 18/30/60/151/196 | 165/157/176/194/197 | 11/13/14/15/16 |
| 24/25 | 1.00/1.08/.54/.11 | —/9/9/9 | 18/33/67/157/197 | 166/162/180/196/197 | 11/13/14/14/16 |
| 30/0 | 1.08/1.54*/.77*/.15* | —/6/6/6 | 16/16/16/16/192 | 163/16/16/16/192 | 11/5/5/5/13 |
| 30/13 | 1.02/1.24/.62/.12 | —/6/6/6 | 17/23/53/146/196 | 165/153/174/192/197 | 11/13/14/15/16 |
| 30/25 | 1.00/1.10/.55/.11 | —/6/6/6 | 18/26/61/154/197 | 166/160/179/196/197 | 11/13/14/14/16 |
| 40/0 | 1.14/1.74*/.87*/.17* | —/3/3/3 | 14/11/11/11/189 | 159/11/11/11/189 | 11/5/5/5/13 |
| 40/13 | 1.06/1.34/.67/.13 | —/3/3/3 | 16/16/42/135/193 | 163/144/165/185/193 | 11/13/14/16/13 |
| 40/25 | 1.02/1.15/.58/.12 | —/3/3/3 | 18/20/54/150/196 | 165/156/176/194/197 | 11/12/14/15/16 |

The large dark zones at high elevation and low tube tilt are consequences of the **air-backed wall assumption**, not predictions for an optically coupled display backing.

Primary rear-wall TIR intervals inside the lid:

| \(\theta\) | \(e\) | \(\tau=0^\circ\) | \(\tau=13^\circ\) | \(\tau=25^\circ\) |
|---|---:|---|---|---|
| 40° | 15°, 24° | None | None | None |
| 40° | 30° | \(u<.117\) | None | None |
| 40° | 40° | \(u<.460\) | \(u<.053\) | None |
| 70° | 15° | \(u<.040\) | None | None |
| 70° | 24° | \(u<.228\) | \(u<.00175\) | None |
| 70° | 30° | \(u<.393\) | \(u<.011\) | None |
| 70° | 40° | \(u<.928\) | \(u<.086\) | None |
| 90° | 15°, 24° | None | None | None |
| 90° | 30°, 40° | Entire lid | None | None |

Repository files were not changed; calculation scripts were written and run only under `/tmp`.