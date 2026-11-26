# Model request: what the desk-view lid really shows (read-only: physics + numbers + a cheap law)

User (2026-11-27, black ink look on the board, viewElevation 24): "the surface itself looks foggy instead of like the
current liquid ... surface fill affects only the front part of the surface to the middle (lower), not middle to the rim.
So the part middle to the rim and the rim itself might need fixes. Model physics for it and check."
Board look: docs/lid-fill/board-look.json (liquid #000000, liquidTransparency 0.08, tubeBack #cbcbb3 (pale), surfaceBand
0.35, surfaceFill 0.505, surfaceRim 0.45, surfaceBlick 0.9, surfaceTone 0, contactAngle 70, viewElevation 24, vertical).
Measured in the sim on that look (8-bit luma; tube back 197, ink body 18): the lid is a flat 120-145 from front to back.

## The scene (docs/tilted-fizz-deskview.md)
Vertical glass tube on a stand tilted back tau (pose, ~13 deg), bore radius R (~20 px, ~2.3 mm; the tube is 8 mm outside),
liquid inside up to a level surface; the eye in front, elevation e = viewElevation above the horizontal (24 deg here), so
delta = e - tau above the screen normal. Tube frame: x up the tube, y across, z toward the viewer. Orthographic view,
x' = x - z tan delta. The contact ring projects to an ellipse: front contact line (lower arc, z = +z_R, z_R =
sqrt(R^2 - y^2)) and back contact line (upper arc), 2 z_R T apart, T = tan tau + tan delta; the lid between them is the
free surface seen from above, through the dry front glass and the air above the liquid. Below the front line the body is
seen through the front glass. u = 0 at the front line .. 1 at the back line (u = (z_R - z) / 2 z_R on a flat level plane).
Meniscus: contactAngle theta (70 deg), the renderer takes the spherical-cap rise h_m = R tan(45 deg - theta / 2) (0.176 R);
the real bore is near Bo ~ 1 (capillary length 2.7 mm). Behind the tube: the tube back (a pale or dark backing, panel
colour tubeBack), also seen through the dry tube above the liquid.
liquidTransparency t = the share of the tube back showing through the full liquid (centre chord 2R); the body row colour
is mix(lit liquid colour, back, t) plus glass reflections.

## What is drawn today (sim/src/render.ts `lid`, ~l.2843; firmware lidRow)
Per row, from the front line to the back line (w = lid height on that row), one composited write of:
- fill: colour = a blend inner -> outer of liquid-row / dark-liquid tones (not the tube back), opacity
  af = a fill (1 - u), a = min(1, 1.6 surfaceBand), fill = surfaceFill. So at most a fill at the front line, LINEAR to 0
  at the back line, independent of liquidTransparency. Board look: 0.56 x 0.505 = 0.28 at the very front.
- blick: neutral grey at liquidHi's luma, opacity a surfaceBlick rowtent 4 u (1 - u) (peaks mid-lid);
- front rim: 1 px on the front line, weight surfaceRim..., colour liquidHi over a dark back / a deep liquid-tinted
  contour over a light back;
- back contour: 0.5 px on the back line, deep liquid tint, weight surfaceRim.
Rear marks (digits / ticks on the back wall) under the lid and foam under it take the same opacities.

## Fable's first-order physics (check it)
A ray to lid position u meets the level surface at incidence 90 deg - e (66 deg at e 24): Fresnel R ~ 9 % (the mirror
direction is the dry back wall / tube back above the liquid), the rest refracts to theta_w = asin(cos e / n) (43 deg) and
runs to the back wall: in the tube frame it makes theta_w + tau with the axis, so its path in the liquid is
l(u) = 2 z_R (1 - u) / sin(theta_w + tau)  (~1.2 x 2 z_R (1 - u)), and what it then sees is the back wall / tube back.
Colour ~ R C_mirror + (1 - R) mix(liquid colour, back, T), T = t^(l / 2R). For ink (t 0.08) that is ~black until u ~ 0.77
and fades to the backing only in the last quarter; for a clear liquid (t 0.8) a faint wedge, as today.
A prototype of opacity = max(a fill (1 - u), 1 - t^(1.2 (1 - u))) read 58 -> 21 on the board look (was 120-145).

## Deliver (file-ready markdown; you may write and run a ray tracer under /tmp, do not edit the repository)
1. A ray trace of the centre plane (y = 0; say how rows off centre scale) through the real interfaces: dry front glass
   (thin, ignore its offset or not: say), air, the meniscus surface (spherical cap by the renderer's rule; comment on
   Bo ~ 1), liquid, back wall, and for rays below the front contact line the front glass + liquid wedge on the front
   wall. For screen positions from a few px below the front line to a few px above the back line give: the liquid path
   l(s) / 2R, the first-surface Fresnel reflectance and where the mirror ray goes, total internal reflection zones if
   any, and the resulting apparent luma for the board look (ink on the pale back) and for a clear liquid (t 0.8) and a
   dark back. Cases: e 15 / 24 / 30 / 40, tau 0 / 13 / 25, theta 40 / 70 / 90.
2. Verdict on the user's observation and on my first-order law: where it is wrong (front zone, back zone, the rims),
   by how much, and whether the dish (not a flat plane) changes the u mapping enough to matter at a 17 px tall lid.
3. What the two rims physically are and how they look for (dark liquid, light back) and (clear / light liquid, dark back):
   the back contact line (the meniscus climbing the back wall, seen from above) and the front contact line (the meniscus on
   the front glass seen through it, grazing reflection off the dish's near side). Width in px at R = 20, luma, and
   whether today's 1 px front rim / 0.5 px back contour are right, too thin, or the wrong tone.
4. A cheap law for the renderer: opacity(u, row) and a reflection term, as closed forms or a table over u of <= 33
   entries built per frame (per pixel: one lookup + the existing blend; float32; static memory; identical in the
   TypeScript sim and the C++ firmware), plus the rim / contour treatment. Say how surfaceBand, surfaceFill, surfaceRim,
   surfaceBlick, surfaceTone should act on top (artistic scales over a physical base, or which of them becomes redundant),
   keeping a clear liquid's lid close to today's look.
5. Sanity table for the board look: luma along the lid (u = 0, 0.25, 0.5, 0.75, 0.9, 1) today, by my first-order law, and
   by your trace.
Terse; formulas and numbers over prose.
