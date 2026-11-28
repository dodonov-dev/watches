#!/usr/bin/env python3
"""Roly-poly, USB-C socket in the back wall (the pebble's round E slot carried over): where it can go. A side section at
x -5 (the port's plane, world frame) of round 8's body with the keeper and of the cup, with the seated parts; the
pebble's slot (11 x 5, lower edge 2.5 above the rim) drawn in the body's back wall. A sketch: nothing is built.

  ~/.venvs/cad/bin/python cad/desk/concept/rolypoly_usb_slot.py   -> images/rolypoly-usb/usb-slot-room.png
"""
import sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import numpy as np, pyvista as pv
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import rolypoly as rp

D = HERE.parent / "out-rolypoly"
OUT = HERE.parent.parent.parent / "images" / "rolypoly-usb"
X = rp.XOFF
SLOT = (11.0, 5.0, 2.5)                                    # the pebble's: width, height, lower edge above the rim


def sec(path, x=X):
    s = pv.read(str(path)).slice(normal="x", origin=(x, 0, 0))
    P = np.asarray(s.points)
    return [P[c[1:], 1:] for c in s.lines.reshape(-1, 3)]


def draw(ax, path, col, lw=1.0, x=X, **kw):
    for a in sec(path, x):
        ax.plot(a[:, 0], a[:, 1], color=col, lw=lw, **kw)


def bbox(path):
    b = pv.read(str(path)).bounds
    return b


fig, ax = plt.subplots(figsize=(11, 7.5))
draw(ax, D / "keeper" / "body.stl", "k", 1.4)
draw(ax, D / "cup-rock.stl", "#555555", 1.4)
for n, c in (("dummy-cast.stl", "#9a8f7a"), ("dummy-pcb.stl", "#2f6f4f"), ("dummy-glass.stl", "#7aa6c2"), ("dummy-usb-head.stl", "#8a4fa0"),
             ("dummy-usb-cable.stl", "#8a4fa0"), ("keeper/dummy-cell.stl", "#c8961e"), ("keeper/fork.stl", "#d2691e")):
    draw(ax, D / n, c, 1.2)
b = bbox(D / "keeper" / "ribs.stl")
fy = [float(v) for v in rp.to_world(np.array([10.6, 10.6]), np.array([24.0, 40.0]))[0]]
ax.plot([fy[0], 24.6, 24.9, fy[1], fy[0]], [22.0, 22.0, 39.3, 39.3, 22.0], color="#7d5fb0", lw=0.9, ls="--")      # fins, beside this plane
# the pebble's slot in the body's back wall
z0 = rp.SEAM + SLOT[2]
wall = [a for a in sec(D / "keeper" / "body.stl") if a[:, 0].max() > 20]
yb = np.concatenate(wall)
k = (yb[:, 1] > z0) & (yb[:, 1] < z0 + SLOT[1]) & (yb[:, 0] > 20)
yi, yo = yb[k, 0].min(), yb[k, 0].max()
ax.add_patch(plt.Rectangle((yi - 0.3, z0), yo - yi + 0.6, SLOT[1], fc="#e33", ec="#a00", alpha=0.55, zorder=5))
cell = bbox(D / "keeper" / "dummy-cell.stl")
port = rp.to_world(-6.5, rp.PCB_Z0)
cs = np.concatenate(sec(D / "keeper" / "dummy-cell.stl"))                 # the cell's back face at the slot's mid height:
k0, k1 = cs[np.argmin(cs[:, 1])], cs[np.argmax(cs[:, 0])]                 # its lower and upper back corners in this plane
yc = float(k0[0] + (z0 + 2.5 - k0[1]) * (k1[0] - k0[0]) / (k1[1] - k0[1]))
ax.annotate("", (yi, z0 + 2.5), (yc, z0 + 2.5), arrowprops=dict(arrowstyle="<->", color="#a00"))
ax.text((yi + yc) / 2, z0 + 3.2, f"{yi - yc:.1f} from the cell's back to the wall", ha="center", fontsize=8, color="#a00")
zc = pv.read(str(D / "dummy-cast.stl")).bounds[5]
ax.annotate("", (float(port[0]) - 6, zc), (float(port[0]) - 6, float(port[1])), arrowprops=dict(arrowstyle="<->", color="#333"))
ax.text(float(port[0]) - 5.3, (zc + float(port[1])) / 2, f"{float(port[1]) - zc:.1f} under the\nport to the cast", ha="left", va="center", fontsize=8)
ax.axhline(rp.SEAM, color="#888", lw=0.6, ls=":")
for txt, xy in (("seam (body / cup)", (30.5, rp.SEAM + 0.4)), ("cast, top 17.0", (-2, 12.5)), ("old 90 deg head + cable\n(through the notch in the seam)", (2, 17.8)),
                ("cell (new place)", (cell[2] + 1.0, 45)), ("fork", (-6.5, 33)), ("board", (-12.5, 45)),
                ("pebble's slot 11 x 5,\n2.5 above the rim", (yo + 1.0, z0 + 1.5)), ("fins (dashed), at x -9.9 and 4:\nthe slot's 11 mm does not fit between them", (12, 41))):
    ax.text(*xy, txt, fontsize=8)
ax.set_xlim(-22, 40); ax.set_ylim(0, 60); ax.set_aspect("equal")
ax.set_xlabel("y: front -> back (world, mm)"); ax.set_ylabel("z (world, mm)")
ax.set_title("Roly-poly: side section at x -5 (the USB port's plane). Room for a USB-C socket in the back wall")
OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / "usb-slot-room.png", dpi=150, bbox_inches="tight")
print("wrote", OUT / "usb-slot-room.png", "| wall", round(yi, 2), round(yo, 2), "| cell back y at the slot", round(yc, 2), "cell z", round(cell[4], 2), "| port", np.round(port, 2), "| cast top", zc)
