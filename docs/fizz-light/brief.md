# Model request: fizz lit where it is (read-only: physics + maths, no code edits)

User (2026-11-25): "Currently fizz shade and blick are set as explicit parameters. It may be cool in some cases [photo:
black liquid, dim blue-grey rings with a white pinpoint], but when fizz reaches the surface and it's tilted so that the
surface is big, it may look better. I'd like to make shade more realistic and depending on the location — it may add to
the 3D feeling and realism. Dynamic physics-based shade / blick / other fizz properties, without much fps reduction."

Branch `fizz-light` (on edge-ends 41121d2). Fable designs and implements; you check and correct the physics and give
the cheap closed forms. Answer in a file-ready markdown (I save it as docs/fizz-light/astra-model.md).

## What is drawn today (sim/src/render.ts step 5 ~l.2931-3056; firmware/src/render.cpp planBubble ~l.6587, planFizz ~l.6787)
A bubble = an AA disc of radius r (1.5-4 px typical; LCD tube H 54-72 rows, bore radius R ~ 20-29 px):
- ring: colour `bubbleRimRows[row]` (bubbleRim x the liquid's own row light, capped 0.8), mixed toward the liquid row
  colour by depthK = 1 - fizzDepth z (1 - liquidTransparency), z = 0 front glass .. 1 back (4 levels, tables per level
  and row: FizzLook cRim[lvl][row]);
- see-through core of radius r - 1 shifted AWAY from the light by fizzShadeOff r (ring thick on the lit side), with a
  dark tint bubbleDark x depthK;
- pinpoint ("blick", r >= 2.5): white, radius max(0.6, r / 4), at 0.4 (r - 1) toward the light, weight fizzBlick
  (vertical watch: x (1 - zc)^2, zc the continuous depth 0..1);
- "the light" for both: direction normalize(-0.7, (yHi - y) / (H / 2)) in the screen plane, i.e. fixed screen-left
  plus toward the cylinder's highlight row. Not the pose, not the surface.
Nothing depends on where the bubble is along the tube, on the free surface, or on the lid.

## Geometry available per bubble and frame (vertical watch; docs/tilted-fizz-deskview.md, tilted-fizz-surface-model.md)
Tube frame: x along the tube (liquid frame, toward the time edge = the free surface, physically up on the stand), y across
(rows), z toward the viewer. Bore radius R. Bubble centre (x, y, z) continuous (FizzBody), radius r, y^2 + z^2 <= (R - r)^2.
- Pose b = unit "up" in the tube frame (bx, by, bz); stand: tau = atan2(bz, bx) ~ 13 deg back.
- Cylinder light: `light` deg (TubeState.light), the highlight normal's angle in the cross-section; the palette's
  Lambert uses the light at 2 x light from the view axis, toward -y for light > 0 (world-up when lightPhys 1).
- Free surface (time edge) per row: S(y) = fizzSurf[row] (side view: the meniscus profile; desk view: the FRONT contact
  line), exposed or closed (full tube: the end glass). Home edge likewise (exposed only for a free slug).
- Desk view (viewElevation e > 0): eye delta = e - tau above the screen normal, lid slope T = tan tau + tan delta; the
  level line at a body's depth is L = S + (z_R - z) T, z_R = sqrt(R^2 - y^2); foam hangs under it, seen from above
  through the surface. tan tau is at hand (FizzLid.tanT).
- liquidTransparency t = what shows through the full liquid (the bore's centre chord 2R): alpha = -ln(t) / 2R.
- Foam: Bo <= 0.01, a sphere hanging under the surface, film cap <= 8 % of r.

## Draft model (Fable) — check it, replace what is wrong
One new param `fizzPhys` 0..1 (like lightPhys): 0 = today's explicit look, byte for byte; 1 = below. Explicit params stay
as the artistic maxima (fizzBlick = pinpoint weight where fully lit and unveiled, fizzShadeOff = ring asymmetry under a
fully sideways light, bubbleRim = the lit ring colour).

1. Light: key = world-up, unit l in the liquid frame (lx along the tube from the pose; cross-section part at 2 x light
   as the palette), plus an ambient share A ~ 0.35: radiance from direction n: Lr(n) = A + (1 - A) max(0, n . l).
2. Exposure: six axis probes n_i = +-x, +-y, +-z with path d_i to the liquid's boundary:
   +x: S + (z_R - z) tan tau - x (0 light if the end is closed), -x: x - S_home (0 unless a free slug's exposed end),
   +-y: sqrt(R^2 - z^2) -+ y, +-z: z_R -+ z;  e_i = Lr(n_i) exp(-alpha d_i).
   - light vector G = sum_i n_i e_i (smooth; in a clear liquid G = (1 - A) l), g = G / |G|;
   - scalar exposure E in 0..1, = 1 in a clear liquid, = "the best-lit boundary dominates" in a dark one. Candidates:
     max_i(e_i) / max_i Lr(n_i), or 1 - prod_i(1 - e_i / Lmax), or sum e_i / sum Lr. Which is the defensible estimate of
     the light a bubble's TIR ring shows the viewer, and with what normalisation?
3. View path d_v: through the front glass z_R - z; under the lid (x > S, T > 0) through the surface instead:
   d_v = max(0, (z_R - z) - max(0, x - S) / T). T_v = exp(-alpha d_v). (1 / cos delta dropped.)
4. Ring colour = mix(liquid row colour, lit rim colour, K), K = T_v E (replaces depthK; quantised to ~8 levels of a
   per-row table, index linear in optical depth so no exp per bubble on the ESP32-S3).
5. Core offset (ring thick on the lit side): direction -(gx, gy) / |g_xy|, amount min(r fizzShadeOff |g_xy|, r - 1).
6. Pinpoint: at (r - 1) h_xy, h = normalize(g + V), V = (0, 0, 1) (the specular point of the effective light); weight
   fizzBlick T_v |G| / (1 - A) capped 1.
7. Everything blended with today's values by fizzPhys.

## Questions
a. Is the ring picture right: seen along -z, the annulus rho > r / n (water: 0.75 r) is total internal reflection and
   shows the surroundings from "straight behind" (rim) to ~83 deg off axis (inner edge), never the viewer's hemisphere;
   the core transmits (minified)? What does that imply for WHICH directions' exposure sets the ring's brightness and
   its bright side (my six probes weight all sides alike, +z included)? Give the right weights if they differ.
b. The glint: Fresnel strength of the lamp's reflection off the outside of an air bubble in water versus the angle
   between light and view (2 % near normal, TIR past 97 deg). With the lamp above and the eye in front (~77-90 deg
   apart on the stand, desk view), how strong is it relative to the ring, where on the disc does it sit, and is there
   a second bright point (light refracted through the bubble / internal reflection) worth a pixel? Recommend the
   pinpoint's position and weight law for (i) a bubble in the bulk, (ii) against the front glass, (iii) foam under
   the lid seen from above (cap film in air: what changes).
c. Exposure estimate (2): the best cheap form and its normalisation; whether six axis probes suffice or the +x probe
   should follow l (one oblique ray to the first of surface / wall); the ambient share; whether the tube back (-z, the
   panel) should count as a light.
d. Foam at the surface in a dark liquid, seen from above (lid) and from the side: what makes it look bright in reality
   (cap film, meniscus ring, multiple scattering) and the cheapest faithful stand-in with ring + core + pinpoint
   (e.g. core tint off, ring lit by the sky directly: K -> 1, pinpoint x ?).
e. The core: today a dark tint (bubbleDark). Physically the bubble removes absorbing path (a clear window) and
   minifies what is behind. Is a location-dependent core term worth it at r <= 4 px (e.g. lighter core where the
   bubble spans much of the view path), and its law?
f. Anything location-dependent I missed that reads strongly at 3-8 px bubble diameter (e.g. the bubble's shadow /
   caustic on the back, the mirror image in the surface from below (TIR past 48.6 deg), brightening against the wall).
   Rank by visual payoff per cost; one line each.
g. Sanity numbers for the user's looks: (1) black ink: t = 0.1, R = 20.5, r = 2.75, stand tau 13 deg, e 0 and e 20;
   (2) clear blue: t = 0.8, R = 20.5, r = 2.5. K and pinpoint weight for: mid-bore 100 px below the surface; on the
   front glass 100 px below; on the front glass 5 px below the surface; foam at the front contact line; foam at the back
   of the lid.

## Constraints
- ESP32-S3, float32, per bubble per frame: a few dozen flops, <= 2 sqrt, <= 1 division, no exp / pow / trig (tables
  built when params change are fine; per frame once: anything). ~120 bubbles a tube. Per pixel: nothing new.
- Sim (TypeScript, Math.fround) and firmware (C++) must compute the same values: + - x / sqrt, clamps, table lookups.
- Firmware memory static / boot-time only.
- Keep it to what reads at this size; simple-correct beats rich-flawed.
