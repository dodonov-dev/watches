**Fizz lighting model — physics check and recommended approximation**

Use separate **ring illumination**, **lamp reflection**, and **view transmission**. A single exposure vector cannot represent all three.

The formulas below are geometrical optics; the proposed shader uses centre-to-boundary paths and four angular samples. Sanity values are unquantised shader values, not predictions of a particular room.

**a. Ring: which surroundings are visible**

Let \(V\) point toward the viewer **inside the liquid**, \(N\) be the bubble’s outward normal, \(n=n_\mathrm{water}/n_\mathrm{air}=4/3\), and \(u=\rho/r\).

\[
N\cdot V=\sqrt{1-u^2},\qquad
q=2(N\cdot V)N-V,\qquad q\cdot V=1-2u^2 .
\]

Here \(q\) points from the reflecting surface toward its source.

\[
u>1/n=0.75
\quad\Longrightarrow\quad
-1\le q\cdot V<-1/8 .
\]

Thus the TIR annulus sees a cone within \(82.82^\circ\) of **\(-V\)**. It excludes the viewer’s hemisphere. The core transmits a reduced, distorted view; reflection remains present below the TIR threshold. This agrees with the geometrical-optics bubble calculation in [Laven’s scattering analysis](https://www.philiplaven.com/p8h1.html).

The exact annulus-average directional weight is particularly simple:

\[
dA_\mathrm{projected}=\frac{r^2}{4}\,d\Omega,\qquad
\overline L_\mathrm{ring}
=\frac{\displaystyle\int_{q\cdot V\le-1/8}L(q)\,d\Omega}
       {2\pi(7/8)} .
\]

**Uniform solid-angle weight over that rear cone; zero elsewhere.** Six equally weighted axis probes are wrong. Axis directions alone do not define unique corrected weights: their angular reconstruction must also be specified.

Cheap quadrature, with screen-plane unit axes \(U,W\):

\[
\mu=n^{-2}=9/16,\qquad \beta=\sqrt{1-\mu^2}=0.8267973,
\]

\[
q_{0,1}=-\mu V\pm\beta U,\qquad
q_{2,3}=-\mu V\pm\beta W,\qquad w_i=1/4.
\]

This reproduces constant radiance and the cone’s first directional moment. It approximates broad lighting; it cannot resolve a small lamp. Treat that lamp separately.

For \(V=(0,0,1)\), front illumination can produce a strong glint while leaving the TIR ring dim.

**b. Pinpoint: Fresnel, position, strength**

Use the actual key direction \(l\), not the ambient/exposure gradient \(G\):

\[
\theta=\arccos(l\cdot V),\qquad
H=\frac{l+V}{|l+V|},\qquad
p_\mathrm{glint}=r(H\cdot U,\ H\cdot W).
\]

Hence \(\rho_\mathrm{glint}/r=\sin(\theta/2)\). The draft’s \((r-1)H_{xy}\) places it too centrally.

For incidence \(i=\theta/2\), set \(c=\cos i\), \(c_t=\sqrt{1-n^2(1-c^2)}\):

\[
F(i)=\frac12
\left[
\left(\frac{nc-c_t}{nc+c_t}\right)^2+
\left(\frac{c-nc_t}{c+nc_t}\right)^2
\right],
\]

with \(F=1\) when \(n^2(1-c^2)\ge1\). These are the dielectric [Fresnel equations](https://pbr-book.org/4ed/Reflection_Models/Specular_Reflection_and_Transmission).

| Light–view angle \(\theta\), in water | Reflectance \(F\) | Position \(\rho/r\) |
|---:|---:|---:|
| \(0^\circ\) | 0.0204 | 0 |
| \(44.81^\circ\) | 0.0216 | 0.381 |
| \(70^\circ\) | 0.0335 | 0.574 |
| \(77^\circ\) | 0.0463 | 0.623 |
| \(90^\circ\) | 0.1401 | 0.707 |
| \(\ge97.18^\circ\) | 1 | \(\ge0.750\) |

The ring reflects 100% of its sampled incident radiance. The glint reflects the fractions above; a lamp can nevertheless be much brighter than the surroundings. Their displayed brightness ratio is not determined by Fresnel alone.

Recommended bounded artistic law:

\[
F_\mathrm{ref}=F(38.5^\circ)=0.0463394,
\]

\[
\boxed{
w_\mathrm{glint}=\texttt{fizzBlick}\,
\min(1,F/F_\mathrm{ref})\,
e^{-\alpha(d_l+d_v)}
}
\]

This calibrates `fizzBlick` to an unveiled \(77^\circ\) reflection. It is an artistic calibration, not absolute photometry. Pure radiometric weighting would use \(F\), without division by \(F_\mathrm{ref}\).

- **Bulk:** use both incident and outgoing attenuation. Ambient gradients must not create a lamp.
- **Front glass:** same law; no extra contact boost. The centre remains approximately \(r\) from the wall.
- **Foam:** use the submerged interface and the appropriate refracted viewing direction. Do not multiply the whole pinpoint by a film-brightening constant.

A second point is not universally absent—transmitted and internally reflected paths exist—but its location and strength depend on illumination. At this resolution, omit it.

For the exposed air–water–air cap, the phase-averaged thin-film reflectance is approximately

\[
F_\mathrm{film}=\frac{2F_\mathrm{air\to water}}{1+F_\mathrm{air\to water}},
\]

rather than submerged water–air TIR. Film thickness can change this through interference; see the [thin-dielectric model](https://pbr-book.org/4ed/Reflection_Models/Dielectric_BSDF). Crucially, the required specular normal must lie **on the tiny cap**. An overhead lamp and a low eye generally fail that condition.

**c. Corrected exposure and cheap closed forms**

Directions are source-facing. Either use \(l=b\), or reconstruct the palette-compatible direction:

\[
l=\left(b_x,\ -\sqrt{1-b_x^2}\sin(2\,\texttt{light}),
                 \sqrt{1-b_x^2}\cos(2\,\texttt{light})\right).
\]

These coincide only when the palette angle agrees with the pose.

A usable broad-environment prescription is

\[
L_\infty(q)=A+(1-A)\max(0,q\cdot l),\qquad A=0.35.
\]

This is an **assumed directional radiance distribution**, not Lambert shading of the bubble. \(A\) is a room-lighting choice, not a physical constant.

For a locally planar free surface \(b\cdot P=c\), define liquid-side clearance \(h=c-b\cdot P\). A ray toward \(q\) reaches it at

\[
d_s=\frac{h}{b\cdot q}\quad(b\cdot q>0);
\quad d_s=\infty\text{ otherwise}.
\]

For the cylindrical wall:

\[
a=q_y^2+q_z^2,\qquad v=yq_y+zq_z,
\]

\[
d_w=\frac{-v+\sqrt{v^2+a(R^2-y^2-z^2)}}{a};
\qquad d_w=\infty\text{ if }a=0.
\]

Take the **first positive intersection**, including the home end where applicable. A closed end is still an intersection: its transmitted/reflected radiance determines the result. “Closed” does not inherently mean opaque.

With boundary visibility/radiance multiplier \(M_i\),

\[
a_i=\tfrac14 L_\infty(q_i)M_i e^{-\alpha d_i},\qquad
D_\mathrm{ref}=\tfrac14\sum_iL_\infty(q_i),
\]

\[
\boxed{
E=\frac{\sum_i a_i}{D_\mathrm{ref}},\qquad
K=e^{-\alpha d_v}E,\qquad
\alpha=-\frac{\ln t}{2R}.
}
\]

Here \(M_i\in[0,1]\) describes a boundary relative to the reference environment. \(E=1\) for clear liquid with all \(M_i=1\). Occlusion legitimately makes it smaller even in clear liquid. **Do not renormalise away a black panel or blocked end.**

Use the weighted sum. `max` overstates a narrow bright direction; \(1-\prod(1-e_i)\) treats radiance samples like independent probabilities.

Trace one additional oblique ray along \(l\) for the pinpoint. A \(+x\) ray is not its replacement.

The panel contributes its actual radiance: reflected room light or displayed/emitted light if that is part of the scene. It is not automatically another sky source.

For ring asymmetry:

\[
J=a_0+a_1+a_2+a_3,\qquad
C=\frac{(a_0-a_1,\ a_2-a_3)}{\max(J,\epsilon)},
\]

\[
\boxed{
\mathrm{coreOffset}=-\min(r\,\texttt{fizzShadeOff},r-1)\,C .
}
\]

\(|C|\le1\); isotropic illumination gives zero offset. This shifts the core away from the **ring’s** bright side without another normalisation.

Use an unshaded lit-rim colour:

\[
C_\mathrm{ring}=\operatorname{mix}(C_\mathrm{liquid,row},C_\mathrm{rim,lit},K).
\]

`bubbleRimRows` already contains row illumination and the 0.8 cap. Reusing it unchanged would apply illumination twice. Retain those existing factors only as explicitly artistic factors.

**View path and coordinate correction**

The desk-view \(x\) is projected; it must not be used as physical axial position:

\[
x'=x_\mathrm{physical}-z\tan\delta .
\]

For the unsuppressed geometric lid,

\[
h=\cos\tau\,[S+(z_R-z)T-x'],\qquad
T=\tan\tau+\tan\delta .
\]

Thus the draft’s surface-view expression is algebraically correct **for straight, unrefracted rays**, with its missing factor restored:

\[
d_v=
\frac{\max\!\left(0,z_R-z-\frac{\max(0,x'-S)}{T}\right)}
{\cos\delta}.
\]

It is not the physical underwater path. Refraction matters much more than the omitted cosine:

\[
\theta_\mathrm{water}
=\arcsin\!\left(\frac{\cos e}{n}\right).
\]

At \(e=20^\circ\), the eye is \(70^\circ\) from the surface normal outside, but only \(44.81^\circ\) inside. A foam centre \(r\) below the plane has

\[
d_{v,\mathrm{lid}}=\frac{r}{\cos44.81^\circ}=1.409\,r,
\]

rather than \(r/\sin20^\circ=2.924\,r\).

For front-glass viewing, a locally parallel wall gives
\(\delta_w=\arcsin(\sin\delta/n)\). Use the corresponding internal \(V\). Curved-wall refraction and the deliberately modified lid projection remain approximations; changing bubble projection is outside this lighting change.

`viewElevation=0` is explicitly **lid disabled** in the code, not a physical \(e=0^\circ\) optical scene.

**Runtime form**

- Precompute \(V,l,H,q_i,L_i,D_\mathrm{ref}^{-1}\), Fresnel factors and plane-intersection reciprocals per frame/row.
- Put cylinder distances \(d_w(y,z,q)\) in fixed-capacity geometry tables; refresh when pose/geometry changes. Then each bubble needs lookups, plane-distance multiplies, minima and attenuation lookups.
- Four ring rays, one key ray, one view ray; approximately tens of arithmetic operations and one division for \(C\). No per-bubble trig/exp; no required per-bubble square roots with the distance tables.
- Example storage: two view families sharing the key need eleven \(17\times17\) float32 distance tables: **12,716 bytes/tube**. This is a coarse geometric approximation; table rebuild cost and interpolation error require measurement.
- Allocate all tables statically or once at boot, at worst-case capacity; fail visibly on insufficient capacity.
- Use an attenuation LUT. A sum of exponentials cannot be represented by simply adding optical depths: quantise the resulting \(K\), or map it through a prebuilt \(K\)-to-colour-level LUT.
- The displayed eight-level colours will be substantially coarser than the numbers below.
- Match float32 operation order and disable contraction where parity requires it.
- `fizzPhys==0` must branch directly to the existing implementation. Blend final colours, offsets and weights for intermediate values; do not blend optical depths.

Centre-path attenuation is the principal size approximation: in the ink case \(\alpha r=0.154\), so moving the optical interaction point by one radius changes a single attenuation factor by roughly 17%.

**d. Foam**

Under the stated cap-radius assumption,

\[
a_\mathrm{cap}\le0.08r,\qquad
A_\mathrm{cap}/(\pi r^2)\le0.0064 .
\]

At \(r=2.75\), its diameter is at most **0.44 px**, before foreshortening. This does **not** justify \(K\to1\) over the whole ring.

Real bright foam combines short liquid paths, reflected sky, curved menisci and—when sufficiently dense—multiple scattering. The current sparse, single-layer population does not justify a white multiple-scattering material.

Cheapest faithful stand-in:

- Use the shorter surface paths for both illumination and viewing.
- Fade the artistic dark-core tint to zero at an exposed surface.
- Retain the Fresnel-weighted submerged glint.
- Let the existing surface band represent the unresolved cap/meniscus contribution; avoid adding it twice.
- From the side, rear foam remains attenuated. From above, its shorter outgoing path makes it much clearer.

**e. Core**

A bubble removes absorption but also refracts the background and loses some transmission to reflection. Along the central ray:

\[
\frac{I_\mathrm{bubble}}{I_\mathrm{no\ bubble}}
\approx (1-F_0)^2e^{2\alpha r},\qquad F_0=1/49.
\]

For the two requested cases this is approximately **1.307** and **0.986**.

Removing absorption does not generate white light; it reveals more of the actual background. Under uniform backlighting, the relative gain is not inherently larger near the viewer.

Recommendation: omit positive core brightening at \(r\le4\). Keep `bubbleDark` as an artistic maximum, attenuated with visibility and suppressed for exposed foam. Accurate brightening requires distinguishing transmitted background from the already-composited liquid colour.

**f. Location effects, ranked by payoff/cost**

1. **Outgoing attenuation and the lid exit:** strongest depth cue; already included.
2. **Separate key visibility:** strong glint changes near the wall/surface; one additional ray.
3. **Ring asymmetry from directional exposure:** useful volume cue; four-sample differences.
4. **Remove foam’s dark core tint:** cheap; avoids soot-like surface bubbles.
5. **Surface mirror image:** physically possible beyond the water–air critical angle \(48.59^\circ\); extra sprite and clipping, often unresolved.
6. **Back-wall shadow/caustic:** needs a receiving surface and illumination geometry; low payoff at this size.
7. **Generic wall-contact brightening:** omit; contact alone supplies no light.

**g. Sanity numbers**

Assumptions: \(y=0\), \(\tau=13^\circ\), \(l=b\), \(A=0.35\), four-ray quadrature above, all \(M_i=1\), distant home end. Thus the rear environment supplies the specified ambient radiance; these are **not black-panel numbers**.

“100/5 px below” means axial clearance, so \(h=D\cos\tau\). Front/back centres have \(z=\pm(R-r)\); foam has \(h=r\). At \(e=20^\circ\), the front-contact foam is still viewed through the wall; rear foam is viewed through the surface. Interface transmission, existing band veil, popping and colour quantisation are excluded.

Each cell is **\(K,\ w_\mathrm{glint}/\texttt{fizzBlick}\)**.

| Location | Ink, lid off | Ink, \(e=20^\circ\) | Blue, lid off | Blue, \(e=20^\circ\) |
|---|---:|---:|---:|---:|
| Mid-bore, 100 px below | 0.063, 0.0019 | 0.066, 0.0015 | 0.759, 0.545 | 0.762, 0.422 |
| Front glass, 100 px below | 0.095, 0.431 | 0.099, 0.334 | 0.750, 0.929 | 0.756, 0.720 |
| Front glass, 5 px below | 0.333, 0.652 | 0.314, 0.505 | 0.866, 0.961 | 0.854, 0.745 |
| Foam, front contact | 0.380, 0.734 | 0.363, 0.569 | 0.873, 0.973 | 0.862, 0.755 |
| Foam, rear | 0.092, 0.100 | 0.493, 0.321 | 0.794, 0.800 | 0.894, 0.450 |

\[
\alpha_\mathrm{ink}=0.0561606\ \mathrm{px}^{-1},\qquad
\alpha_\mathrm{blue}=0.00544253\ \mathrm{px}^{-1}.
\]

Useful ink path checks:

| Location | Incident key path \(d_l\) | View path, lid off | View path, \(e=20^\circ\) |
|---|---:|---:|---:|
| Mid-bore, 100 below | 91.131 | 20.500 | 20.586 |
| Front, 100 below | 12.225 | 2.750 | 2.762 |
| Front, 5 below | 4.872 | 2.750 | 2.762 |
| Front foam | 2.750 | 2.750 | 2.762 |
| Rear foam | 2.750 | 38.250 | 3.876 |

For a black rear panel, set \(M_i=0\) on rays that actually hit it and recompute the sum; do not change \(D_\mathrm{ref}\). The specified transparency, radius and pose alone cannot determine that additional reduction.