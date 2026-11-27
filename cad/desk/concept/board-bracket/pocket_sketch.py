"""Concept sketch (user, 2026-11-27: the rods are not glued to the glass, so the shell must hold the board along the
face and sideways): the glass already sits in a shallow pocket in the front wall (floor t 3.39; bottom ledge 1.0 and
side steps 1.2 high, no top end). Proposal: make that pocket hold the glass: a wedge closing its top, taller side
rails, taller bottom corners. All printable standing without supports (<= 30 deg to the face where they overhang).
Round E shell, body frame.     ~/.venvs/cad/bin/python pocket_sketch.py"""
import math, pathlib
import numpy as np, trimesh
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon
HERE = pathlib.Path(__file__).parent
A = math.radians(15); C, S = math.cos(A), math.sin(A); SN = np.array([0, S, C])
tm = trimesh.load(HERE.parents[1] / "to-print" / "pebble-E-shell.stl")
FRONT, G0, G1, PCB1, PL0, PL1 = 3.392, 3.892, 7.79, 8.79, 11.04, 13.04
GX, GS0, GS1, PX, PS0, PS1 = 15.6, 17.925, 94.525, 16.675, 16.8, 95.65
POCK_X, LEDGE_S = 15.9, 17.6
RAIL_T, RAIL_X1 = 6.4, 18.4                       # NEW: side rails up to here (now 4.56), their outer edge
TAN = math.tan(math.radians(30))
TOP_S0 = GS1 + 0.3 - (G0 - FRONT) / TAN            # NEW: the wedge leaves the pocket floor here: it meets the glass 0.3 above its top
BOT_T, BOT_X0 = 6.0, 7.5                           # NEW: bottom corners up to here (now 4.40), outside the adapter's way
RED = dict(fc="#d0453a", ec="#7a1d16", lw=1, zorder=5)
note = lambda ax, txt, xy, xt, **k: ax.annotate(txt, xy, xt, fontsize=8, ha="center", arrowprops=dict(arrowstyle="->", lw=0.8),
                                                bbox=dict(fc="white", ec="#999", lw=0.5, alpha=0.92), zorder=9, **k)

def vsec(ax, x0, lo, hi, title):
    seg = trimesh.intersections.mesh_plane(tm, [1, 0, 0], [x0, 0, 0]); y, z = seg[..., 1], seg[..., 2]
    T, Sx = y * C - z * S, y * S + z * C
    for a, b, c, d in zip(T[:, 0], T[:, 1], Sx[:, 0], Sx[:, 1]): ax.plot([a, b], [c, d], color="#7a6a4c", lw=1.6)
    ax.add_patch(Rectangle((G0, GS0), G1 - G0, GS1 - GS0, fc="#b9c7d6", ec="#445", lw=0.8))
    ax.add_patch(Rectangle((G1, PS0), PCB1 - G1, PS1 - PS0, fc="#5f7f62", ec="#243", lw=0.8))
    ax.add_patch(Rectangle((PL0, PS0), PL1 - PL0, PS1 - PS0, fc="#dcecf4", ec="#6d8fa3", lw=0.8))
    ax.set_xlim(-2, 15); ax.set_ylim(lo, hi); ax.set_aspect("equal"); ax.set_title(title, fontsize=9.5)
    ax.set_xlabel("t, depth behind the front face"); ax.set_ylabel("s up the face")

fig, ax = plt.subplots(1, 4, figsize=(19, 8.2), gridspec_kw=dict(width_ratios=[1.15, 0.85, 0.85, 1.15]))
# 1. the front wall seen from inside
a = ax[0]
a.add_patch(Rectangle((-POCK_X, LEDGE_S), 2 * POCK_X, 96 - LEDGE_S, fc="#f4efe2", ec="#7a6a4c", lw=1.4))
for sx in (-1, 1): a.add_patch(Rectangle((sx * 9 - 4.05, 24.7), 8.1, 66.85, fc="white", ec="#999", lw=0.8))
a.add_patch(Rectangle((-GX, GS0), 2 * GX, GS1 - GS0, fc="#b9c7d6", ec="#445", lw=0.8, alpha=0.45))
a.add_patch(Rectangle((-6, 8.3), 12, 8.5, fc="#cbb6d3", ec="#7a4f86", lw=0.8)); a.text(0, 12.5, "USB\nadapter", ha="center", va="center", fontsize=7)
a.add_patch(Rectangle((-POCK_X, TOP_S0), 2 * POCK_X, 5.5, **RED))
for sx in (-1, 1):
    a.add_patch(Rectangle((min(sx * POCK_X, sx * RAIL_X1), 20.0), RAIL_X1 - POCK_X, 74.0, **RED))
    a.add_patch(Rectangle((min(sx * BOT_X0, sx * POCK_X), 14.6), POCK_X - BOT_X0, LEDGE_S - 14.6, **RED))
note(a, "top: wedge closing the pocket,\n0.3 above the glass", (5, TOP_S0 + 3), (0, 105))
note(a, "sides: rails, 1.2 -> 3.0 high,\nat the pocket's own edge\n(glass + 0.3 each side)", (-17.2, 60), (-30, 72))
note(a, "bottom corners: ledge 1.0 -> 2.6 high,\noutside the adapter's way", (11.5, 16), (27, 6))
a.text(0, 58, "glass\n(in the pocket)", ha="center", va="center", fontsize=8); a.text(9, 40, "slot", ha="center", fontsize=7); a.text(-9, 40, "slot", ha="center", fontsize=7)
a.set_xlim(-42, 42); a.set_ylim(0, 110); a.set_aspect("equal"); a.set_title("front wall from inside: the glass pocket, additions in red", fontsize=9.5)
a.set_xlabel("x"); a.set_ylabel("s up the face")
# 2. top end   3. bottom end
vsec(ax[1], -12.0, 86, 104, "top end (section x -12)")
h = 5.5; ax[1].add_patch(Polygon([(FRONT - 0.8, TOP_S0), (FRONT, TOP_S0), (FRONT + 2.6, TOP_S0 + 2.6 / TAN), (FRONT + 2.6, TOP_S0 + h + 1), (FRONT - 0.8, TOP_S0 + h + 1)], **RED))
note(ax[1], "30 deg to the face\n(steepest that prints).\nGlass can rise 0.3", (FRONT + 0.7, GS1 + 0.5), (10, 100.5))
vsec(ax[2], -12.0, 8, 26, "bottom end (section x -12)")
ax[2].add_patch(Polygon([(4.2, 17.6 - (BOT_T - 4.4) / TAN - 0.3), (4.4, 17.6 - (BOT_T - 4.4) / TAN), (BOT_T, LEDGE_S), (4.2, LEDGE_S)], **RED))
note(ax[2], "flat top, 0.3 under the glass:\nthe board comes over it\nand drops forward", (5.2, 17.5), (10.5, 11.5))
# 4. across the face at s 60
a = ax[3]
seg = trimesh.intersections.mesh_plane(tm, SN, SN * 60.0); x = seg[..., 0]; t = seg[..., 1] * C - seg[..., 2] * S
for p, q, c, d in zip(x[:, 0], x[:, 1], t[:, 0], t[:, 1]): a.plot([p, q], [c, d], color="#7a6a4c", lw=1.6)
a.add_patch(Rectangle((-GX, G0), 2 * GX, G1 - G0, fc="#b9c7d6", ec="#445", lw=0.8)); a.add_patch(Rectangle((-PX, G1), 2 * PX, PCB1 - G1, fc="#5f7f62", ec="#243", lw=0.8))
a.add_patch(Rectangle((-PX, PL0), 2 * PX, PL1 - PL0, fc="#dcecf4", ec="#6d8fa3", lw=0.8))
a.add_patch(Rectangle((-PX - 1.0, G1), 1.0, 4.0, fc="#b04040", ec="k", lw=0.5))
for sx in (-1, 1): a.add_patch(Polygon([(sx * POCK_X, 4.3), (sx * POCK_X, RAIL_T - 0.6), (sx * (POCK_X + 0.6), RAIL_T), (sx * RAIL_X1, RAIL_T), (sx * RAIL_X1, 4.9)], **RED))
note(a, "rail beside the glass: ends 1.4 in front\nof the PCB and the buttons", (-17.3, 6.3), (-13, 0.6))
note(a, "glass", (0, 6), (0, 10.3)); a.text(11, 12.1, "plate", ha="center", va="center", fontsize=7)
a.set_xlim(-23, 23); a.set_ylim(15, -2); a.set_aspect("equal"); a.set_title("across the face at s 60 (front wall up)", fontsize=9.5); a.set_xlabel("x"); a.set_ylabel("t")
plt.tight_layout(); plt.savefig(HERE / "pocket-views.png", dpi=92); print(HERE / "pocket-views.png", "wedge from s", round(TOP_S0, 2))
