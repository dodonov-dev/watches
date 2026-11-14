#!/usr/bin/env python3
"""Cross-section of one slot edge: front-wall profile options, to scale (writes out/profile-options.svg).

Section across a slot: LCD glass at y = 0, front wall 3 mm (outer face y = 3), slot 8.6 wide, 8 x 4 half-rod on the
glass. Run: python3 cad/desk/profile_options.py
"""
import math, pathlib

S = 22                       # px per mm
FRONT, SLOT_HALF, ROD_R, X_END = 3.0, 4.3, 4.0, 11.0
OUT = pathlib.Path(__file__).parent / "out" / "profile-options.svg"


def wall_profile(kind):
    """Right-hand wall outline (x, y) from the slot edge on the glass, up to the face, then to X_END."""
    e = SLOT_HALF
    if kind == "now":                 # v1: vertical 1.5 rim, then 45 deg to the face
        pts = [(e, 0), (e, 1.5), (e + 1.5, FRONT)]
    elif kind == "chamfer0":          # straight 45 deg all the way down to zero
        pts = [(e, 0), (e + FRONT, FRONT)]
    elif kind == "concave0":          # curve tangent to the glass at the edge: a feather edge
        pts = [(e + FRONT * math.sin(t), FRONT - FRONT * math.cos(t)) for t in [i / 20 * math.pi / 2 for i in range(21)]]
    elif kind == "convex0":           # round-over: meets the glass at 90 deg, full rod visible
        pts = [(e + FRONT - FRONT * math.cos(t), FRONT * math.sin(t)) for t in [i / 20 * math.pi / 2 for i in range(21)]]
    return pts + [(X_END, FRONT), (X_END, 0)]


PANELS = [
    ("now", "A. v1 now: 45° bevel to a 1.5 mm rim", "rod 2.5 mm above the rim; bottom 1.5 mm hidden"),
    ("chamfer0", "B. straight 45° to zero", "whole rod visible; edge = 45° wedge (thin, can chip)"),
    ("concave0", "C. concave curve to zero", "edge = 0° knife: not makeable (what I said 'can't')"),
    ("convex0", "D. rounded-over to zero", "whole rod visible; edge meets the glass at 90°: strong"),
]


def panel(kind, title, note, ox, oy):
    X = lambda x: ox + (x + X_END) * S
    Y = lambda y: oy + (6.0 - y) * S
    g = [f'<text x="{ox + 4}" y="{oy - 14}" font-size="15" font-family="sans-serif" font-weight="bold">{title}</text>',
         f'<text x="{ox + 4}" y="{oy + 8.4 * S}" font-size="13" font-family="sans-serif">{note}</text>',
         f'<rect x="{X(-X_END)}" y="{Y(0)}" width="{2 * X_END * S}" height="{1.2 * S}" fill="#4a6f8a"/>',
         f'<text x="{X(-X_END) + 4}" y="{Y(-0.85)}" font-size="11" fill="white" font-family="sans-serif">LCD glass</text>']
    for side in (1, -1):
        pts = wall_profile(kind)
        poly = " ".join(f"{X(side * x):.1f},{Y(y):.1f}" for x, y in pts)
        g.append(f'<polygon points="{poly}" fill="#c8a27a" stroke="#5a3d22" stroke-width="1.5"/>')
    rod = [(ROD_R * math.cos(t), ROD_R * math.sin(t)) for t in [i / 40 * math.pi for i in range(41)]]
    g.append(f'<polygon points="{" ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in rod)}" fill="#dff4fa" '
             f'stroke="#2a7a9a" stroke-width="1.5" fill-opacity="0.85"/>')
    g.append(f'<line x1="{X(-X_END)}" y1="{Y(FRONT)}" x2="{X(X_END)}" y2="{Y(FRONT)}" stroke="#999" stroke-dasharray="4 3"/>')
    g.append(f'<text x="{X(X_END) - 70}" y="{Y(FRONT) - 4}" font-size="11" fill="#666" font-family="sans-serif">face</text>')
    g.append(f'<text x="{X(0) - 18}" y="{Y(1.6)}" font-size="11" fill="#2a7a9a" font-family="sans-serif">rod</text>')
    return g


W, H = int(2 * X_END * S * 2 + 120), int(2 * 10.5 * S + 60)
body = []
for i, (k, t, n) in enumerate(PANELS):
    body += panel(k, t, n, 30 + (i % 2) * (2 * X_END * S + 60), 50 + (i // 2) * (10.5 * S))
scale = f'<text x="30" y="{H - 10}" font-size="12" font-family="sans-serif">to scale: wall 3 mm, slot 8.6 mm, rod 8 × 4 mm</text>'
OUT.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
               f'<rect width="100%" height="100%" fill="white"/>{"".join(body)}{scale}</svg>')
print(OUT)
