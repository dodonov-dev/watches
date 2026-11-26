# Fizz lit where it is: `fizzPhys` (2026-11-25)

Request, draft and Astra's physics check: brief.md, astra-model.md. This is what is built. Sim: sim/src/fizzLight.ts
(kernel) + render.ts step 5; firmware: firmware/src/fizz_light.h + render.cpp planFizz / planBubble.

## Param
`fizzPhys` 0..1 (v36, default 0, UI "· fizz physical light"). 0 = the explicit look, the old code path, byte for byte.
> 0: each bubble's light is computed where it is and blended with the explicit values by fizzPhys (weights, offsets,
the ring's mix weight; not optical depths). The explicit params stay as the artistic maxima: `bubbleRim` the lit ring's
colour, `fizzBlick` the pinpoint's weight at the stand's angle and no liquid in the way, `fizzShadeOff` (x r, at most
FIZZ_RING_KEEP = 0.6 px) the core's largest shift, `bubbleDark` the core tint away from a surface.

## Optics (Astra, checked)
- Ring = total internal reflection. Seen along V (the screen normal) the annulus rho > r / n mirrors a cone within
  82.8 deg of -V (water, n = 4/3): the surroundings beside and behind the bubble, never the viewer's side. Four probes,
  uniform over that cone: q = -mu V +- beta U, -mu V +- beta W; mu = 1 / n^2 = 9/16, beta = sqrt(1 - mu^2); U the tube
  axis (liquid frame x, toward the time edge), W across (y).
- Room: L(q) = A + (1 - A) max(0, q . l), A = 0.35 (a choice). Key l = world-up: its along-tube part from the pose the
  fizz was last stepped with (liquid frame), its cross-section part at 2 x TubeState.light, as the palette's light:
  l = (b_x, -c sin 2 lambda, c cos 2 lambda), c = sqrt(1 - b_x^2).
- A probe's ray leaves the liquid at the first of: the bore wall (always lit), the time edge's surface (lit if exposed,
  else an end glass: dark), the home edge (lit only for a free slug's exposed end). a_i = w_i M_i exp(-alpha d_i),
  w_i = L(q_i) / sum L, alpha = -ln(max(t, 0.01)) / 2R, t = liquidTransparency.
  E = sum a_i (1 in a clear open tube; a blocked end is not renormalised away).
  - wall, +-x probes: d = (z_R + z) / mu, z_R = sqrt(R^2 - y^2); +-y probes: d = -v + sqrt(v^2 + R^2 - y^2 - z^2),
    v = +-y beta - z mu.
  - surface: d = clr / (q . n), clr = S - x (side view: the drawn meniscus, n = the tube axis), under the lid
    clr = S + (z_R - z) B / 2 z_R - x (the level line at the body's depth; B the lid's height at its row) and
    n = (1, 0, tan tau); a row the lid does not cover (B = 0: closed against the end glass) takes the side view's
    rule, rays included. q . n <= 0: never. Home edge: clrL = x - S_home, n = -axis.
- Ring asymmetry: C = C_GAIN ((a_0 - a_1), (a_2 - a_3)) / E, |C| <= 1, C_GAIN = 2 (a clear liquid lit from the side gives
  ~0.25..0.3 before the gain: broad light leaves the ring nearly even).
- Pinpoint = the key's own Fresnel reflection off the bubble: at r H_xy, H = (l + V) / |l + V| (rho / r = sin(theta / 2),
  kept <= 0.75), weight fizzBlick min(1, F(theta / 2) / F_ref) exp(-alpha (d_l + d_v)), F_ref = F at 77 deg between light
  and view = 0.0463 (the stand; face-on 0.44 of it, from 97 deg on total). d_l: one ray along l to the first boundary
  (0 weight through a dark end).
- View path d_v = z_R - z (front glass); under the lid also min(., clr cos tau / cos theta_w), sin theta_w =
  cos(tau + delta) / n: foam seen from above through the surface (refracted). T_v = exp(-alpha d_v).

## What a bubble takes from it
- tone = clamp((Y(lit rim) - Y(liquid, mid row)) / 32, -1, 1) (8-bit luma of the 565 colours; lit rim = 0.8 x the scalar
  bubbleRim): a ring brighter than the liquid is its lit side, a darker one its shade.
- K = T_v (1 - max(0, tone) (1 - E)): the ring's mix weight liquid .. lit rim. Colour = mix(liquid row,
  mix(bubbleRimRows[row], lit rim, fizzPhys), K'), K' = lerp(old depthK, K, fizzPhys) quantised to FIZZ_LIGHTS = 8 levels
  (l / 7; T = round(256 l / 7) for blend565T).
- core shift = -min(r fizzShadeOff, r - 1, 0.6) tone C: thick toward the light for a lit ring, away for a shade ring;
  the ring thins but never opens.
- pinpoint: white (blickC, no depth mix: the weight carries it), at r H_xy, weight as above; old weight x old depthK
  on the explicit side of the blend.
- core tint = bubbleDark T_v min(1, clearance / 2r) (gone in foam at an open surface).
Not done (KAIZEN): core brightening, the surface's mirror image, a ring gradient per pixel, shadows / caustics.

## Cost
Per bubble: 4 sqrt, 1-3 divisions, 6 table lerps (exp(-tau), 65 entries by a float32 recurrence), ~100 flops; per pixel
nothing. Per frame: trig / log / divisions in fizzLightFrame, skipped while its inputs repeat. The level table: 8 x H
blends on a palette change. Memory: FizzLook (+ 4 x TUBE_HEIGHT_MAX x 2 B, the frame struct) and the per-slot memo
(FIZZ_POOL x 44 B = 21,120 B), PSRAM, boot-time.

Board (lcd316@320w8-8, the pale look, stand pose pinned, 100 + 18 bubbles; 2026-11-26):
- First port (planBubbleLit in flash, the frame set-up with a double Fresnel): fizzPhys 1 = +0.94 ms a frame, 53.7 -> 51.0 fps.
  FIZZ_PROF: fizzLit + the blend ~5.6 us a bubble on the S3 (host 34 ns); the rest was the set-up's soft-float doubles and
  instruction-cache misses of 3.6 KB of flash code fetched every frame.
- Now: the set-up in float32 and keyed on its inputs; planBubbleLit in IRAM (3.2 KB of internal heap, 29 KB left free);
  firmware only: each slot keeps its last FizzLit (FizzLitMemo) and takes a new one every 4th frame, slots staggered, at
  once when older, not where it was taken (> 6 px along the tube, > 2 px across or in depth: a slot reborn elsewhere,
  Astra review 3) or of another radius; all at once when the scene changes (liquid, bore, tone, a lid or an end opening); the blend with the explicit values runs
  every frame. fizzPhys 1 = +0.4..0.6 ms a frame: 53.2 -> 52.1 fps (+0.39 ms) and, the final build, 53.3 -> 51.6 fps
  (+0.57 ms, runs 0.05..0.79; the hours core 16.4 vs ~15.95 ms both times), medians of 3 runs x 5. fizzPhys 0: unchanged path.
  The sim computes every bubble every frame (a firmware bubble's light is at most 3 frames old).
