"""Concept sketch: what stops the board sliding UP in the pebble (user, 2026-11-27: the fork holds it forward, not along
the face). Section at x = -12 (button side, through a slot and the upper rib), body frame, round E shell. Three panels:
as built (only the rods in the slots stop it), A a printed wedge on the front wall above the glass, B a square ledge there.
    ~/.venvs/cad/bin/python vstop_sketch.py"""
import math, pathlib
import numpy as np, trimesh
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon
HERE = pathlib.Path(__file__).parent
A = math.radians(15); C, S = math.cos(A), math.sin(A); X0 = -12.0
tm = trimesh.load(HERE.parents[1] / "to-print" / "pebble-E-shell.stl")
seg = trimesh.intersections.mesh_plane(tm, [1, 0, 0], [X0, 0, 0]); y, z = seg[..., 1], seg[..., 2]
T, Sx = y * C - z * S, y * S + z * C
FRONT, G0, G1, PCB1, PL0, PL1, F0, F1 = 3.392, 3.892, 7.79, 8.79, 11.04, 13.04, 14.54, 17.04
GTOP, PTOP, SLOT1, ROD1 = 94.525, 95.65, 91.55, 91.45
rod_h = math.sqrt(16 - (abs(X0) - 9) ** 2)

def base(ax, title):
    for a, b, c, d in zip(T[:, 0], T[:, 1], Sx[:, 0], Sx[:, 1]): ax.plot([a, b], [c, d], color="#7a6a4c", lw=1.6)
    ax.add_patch(Rectangle((G0, 60), G1 - G0, GTOP - 60, fc="#b9c7d6", ec="#445", lw=0.8)); ax.text((G0 + G1) / 2, 88.5, "glass", rotation=90, ha="center", va="center", fontsize=8)
    ax.add_patch(Rectangle((G1, 60), PCB1 - G1, PTOP - 60, fc="#5f7f62", ec="#243", lw=0.8))
    ax.add_patch(Rectangle((PL0, 60), PL1 - PL0, PTOP - 60, fc="#dcecf4", ec="#6d8fa3", lw=0.8)); ax.text((PL0 + PL1) / 2, 88.5, "plate", rotation=90, ha="center", va="center", fontsize=8)
    ax.add_patch(Rectangle((PL1, 90.05), F0 - PL1, 5.0, fc="#b85c12", ec="k", lw=0.6))
    ax.add_patch(Rectangle((F0, 88.0), F1 - F0, 7.3, fc="#e8893a", ec="#8a4a10", lw=0.8)); ax.text((F0 + F1) / 2, 91.6, "fork", rotation=90, ha="center", va="center", fontsize=8)
    ax.add_patch(Rectangle((G0 - 0.15 - rod_h, 60), rod_h, ROD1 - 60, fc="#f3f3f3", ec="#666", lw=0.8)); ax.text(G0 - 1.5, 86, "rod", rotation=90, ha="center", va="center", fontsize=8)
    ax.text(18.8, 91, "rib", rotation=90, ha="center", va="center", fontsize=8); ax.text(1.2, 98.5, "front\nwall", ha="center", va="center", fontsize=8)
    ax.set_xlim(-2.5, 23); ax.set_ylim(84, 108); ax.set_aspect("equal"); ax.set_title(title, fontsize=9.5)
    ax.set_xlabel("t, depth behind the front face, mm"); ax.set_ylabel("s up the face, mm")

note = lambda ax, txt, xy, xt: ax.annotate(txt, xy, xt, fontsize=8, ha="center", arrowprops=dict(arrowstyle="->", lw=0.8),
                                           bbox=dict(fc="white", ec="#999", lw=0.5, alpha=0.92), zorder=9)
fig, ax = plt.subplots(1, 3, figsize=(17, 7.6))
base(ax[0], "as built: only the rods stop the board going up")
note(ax[0], "rod end to the slot's top end:\n0.1 mm (if the rods are stuck\nto the glass)", (1.6, 91.5), (15.5, 98.2))
note(ax[0], "the pocket above the glass:\nfree for ~6.5 mm", (4.6, 98.0), (12, 103.2))
base(ax[1], "A: wedge on the front wall above the glass (prints without supports)")
s0 = GTOP - 0.4; h = 6.0; d = h * math.tan(math.radians(30))
ax[1].add_patch(Polygon([(FRONT - 0.8, s0), (FRONT, s0), (FRONT + d, s0 + h), (FRONT + d, s0 + h + 1.5), (FRONT - 0.8, s0 + h + 1.5)], fc="#d0453a", ec="#7a1d16", lw=1, zorder=5))
note(ax[1], "30 deg to the face (45 printed standing).\nThe glass's top edge meets it after ~0.5 mm.\nIt can only ride up by pushing the fork back", (FRONT + 0.6, GTOP + 0.6), (14, 103))
base(ax[2], "B: square ledge above the glass (needs the slot ends' tree supports)")
ax[2].add_patch(Polygon([(FRONT - 0.8, GTOP + 0.3), (FRONT + 2.0, GTOP + 0.3), (FRONT + 2.0, GTOP + 2.3), (FRONT + 4.3, GTOP + 6.3), (FRONT - 0.8, GTOP + 6.3)], fc="#d0453a", ec="#7a1d16", lw=1, zorder=5))
note(ax[2], "flat stop 0.3 above the glass, 2 deep:\na hard stop, but an overhang like the\nslots' top ends: supports from inside", (FRONT + 1.2, GTOP + 0.3), (14, 103))
plt.tight_layout(); plt.savefig(HERE / "vstop-views.png", dpi=95); print(HERE / "vstop-views.png")
