#!/usr/bin/env python3
"""Roly-poly board keeper, option sketch (surface level, no CAD build): the pebble's round-D fork + ribs do not port as
they are, because here the 68 x 35 x 10 cell lies 1 mm behind the board's back plate and fills the cavity's width (it cannot
move back: its way in goes negative at +1.15). Sections in the board frame (the board upright; in the world it leans 8
deg back) of round 8's inner surface with the candidates drawn as boxes:
  1  a cranked "stick" that runs behind the cell and steps forward above it to the button side's upper screw; the cell stays
  2  the pebble's fork behind the plate, the cell turned upright behind it
Numbers ASSUMED as in the pebble: plate's back face 9.15 behind the glass front, plugs standing 4.0 behind the plate.

  ~/.venvs/cad/bin/python cad/desk/concept/rolypoly_keeper.py [out dir]   (default images/rolypoly-keeper)
"""
import sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon
import rolypoly as rp
import housing as hw

OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent.parent.parent / "images" / "rolypoly-keeper"
OUT.mkdir(parents=True, exist_ok=True)

X0 = rp.XOFF
YB = rp.Y_GLASS0 + 9.15                                   # the plate's back face (measured stack, the pebble's KEEPER["BOARD_T"])
PAD_H, FORK_T, RIB_T, PAD = 1.5, 2.5, 2.5, 5.0            # the pebble's
F0, F1 = YB + PAD_H, YB + PAD_H + FORK_T                  # fork plane
SCREW_X = (X0 - hw.NUT_DX / 2, X0 + hw.NUT_DX / 2)        # button side (-x), plug side (+x)
SCREW_Z = (rp.PCB_Z0 + hw.NUT_INSET, rp.PCB_Z0 + hw.NUT_INSET + hw.NUT_DZ)
PLUGS = {"UART": 22.45, "J5": 39.42, "I2C": 56.39}        # upward sockets above the PCB bottom (the pebble's KEEPER / hw)
RTC_Z = 67.5
BAT = dict(x=(rp.BAT_X - rp.BAT_L / 2, rp.BAT_X + rp.BAT_L / 2), y=(YB + rp.BAT_GAP, YB + rp.BAT_GAP + rp.BAT_T),
           z=(rp.BAT_Z0, rp.BAT_Z0 + rp.BAT_HT))
COL = dict(shell="#b9b4a8", board="#2f6f4f", glass="#8fb8c9", bat="#d9a441", keeper="#c8452f", rib="#6b3fa0", usb="#555555",
           plug="#1f5fa8", foam="#f2d98a")


def grid(t):
    if t not in rp._QB:
        Q = (rp.SH8.G_OUT - t * rp.SH8.N_OUT).reshape(-1, 3)
        rp._QB[t] = rp.pts_board(Q).reshape(rp.SH8.G_OUT.shape)
    return rp._QB[t]


def section(zb, t=rp.WALL):
    """The surface offset t inwards, cut at board-frame height zb: a closed polyline (x, y)."""
    Q = grid(t)
    zc = np.maximum.accumulate(Q[:, :, 2], axis=0) + np.arange(len(Q))[:, None] * 1e-9
    return np.array([[np.interp(zb, zc[:, j], Q[:, j, k]) for k in (0, 1)] for j in range(Q.shape[1])])


def y_at(P, x):
    a, b = P, np.roll(P, -1, 0)
    k = (a[:, 0] - x) * (b[:, 0] - x) <= 0
    y = a[k, 1] + (x - a[k, 0]) * (b[k, 1] - a[k, 1]) / np.where(b[k, 0] == a[k, 0], 1e-12, b[k, 0] - a[k, 0])
    return (y.min(), y.max()) if len(y) else (np.nan, np.nan)


def x_at(P, y):
    return y_at(P[:, ::-1], y)


def seam_zb(y, z=rp.SEAM):
    return rp.PIV_Z + (z - rp.PIV_Z + (y - rp.PIV_Y) * rp.SIN_T) / rp.COS_T


ZS = np.arange(23.0, 126.0, 1.0)
SEC = {t: [section(z, t) for z in ZS] for t in (0.0, rp.WALL)}


def rect(ax, a0, a1, b0, b1, c, **kw):
    kw.setdefault("ec", "k"); kw.setdefault("lw", 0.5)
    ax.add_patch(Rectangle((min(a0, a1), min(b0, b1)), abs(a1 - a0), abs(b1 - b0), fc=c, **kw))


def side(ax, x, title):
    """Section at x: y to the right (the back), z up."""
    for t, lw in ((0.0, 1.0), (rp.WALL, 0.6)):
        fr = np.array([y_at(P, x) for P in SEC[t]])
        ax.plot(fr[:, 0], ZS, color="k", lw=lw); ax.plot(fr[:, 1], ZS, color="k", lw=lw)
    yy = np.array([-22.0, 30.0])
    ax.plot(yy, seam_zb(yy), color="k", lw=0.6, ls="--"); ax.text(27.5, seam_zb(27.5) + 0.8, "seam", fontsize=6, ha="right")
    ax.plot(yy, seam_zb(yy, 17.0), color="0.5", lw=0.6, ls=":"); ax.text(27.5, seam_zb(27.5, 17.0) - 3.0, "cast", fontsize=6, ha="right", color="0.4")
    rect(ax, rp.Y_GLASS0, rp.Y_GLASS1, rp.GLASS_Z0, rp.GLASS_Z0 + hw.GLASS_H, COL["glass"])
    rect(ax, rp.Y_GLASS1, YB, rp.PCB_Z0, rp.PCB_Z1, COL["board"])
    rect(ax, rp.HEAD_Y0, rp.HEAD_Y1, rp.HEAD_Z0, rp.HEAD_Z1, COL["usb"], alpha=0.5)
    ax.set_aspect("equal"); ax.set_xlim(-22, 30); ax.set_ylim(14, 128)
    ax.set_title(title, fontsize=8); ax.set_xlabel("y: front  ->  back", fontsize=7); ax.tick_params(labelsize=6)


def back(ax, y0, y1, title):
    """Seen from the back: x runs right to left (the button side on the right), z up. The cavity over the depth band y0..y1."""
    band = np.array([[x_at(P, y) for y in np.linspace(y0, y1, 7)] for P in SEC[rp.WALL]])     # (z, y, lo / hi)
    lim = np.c_[band[:, :, 0].max(1), band[:, :, 1].min(1)]
    out = np.array([x_at(P, 0.5 * (y0 + y1)) for P in SEC[0.0]])
    ax.plot(out[:, 0], ZS, "k", lw=1.0); ax.plot(out[:, 1], ZS, "k", lw=1.0)
    ax.plot(lim[:, 0], ZS, "k", lw=0.6); ax.plot(lim[:, 1], ZS, "k", lw=0.6)
    ax.axhline(seam_zb(0.5 * (y0 + y1)), color="k", lw=0.6, ls="--")
    rect(ax, X0 - hw.PCB_W / 2, X0 + hw.PCB_W / 2, rp.PCB_Z0, rp.PCB_Z1, COL["board"], alpha=0.45)
    for n, z in hw.BTN_Z.items():
        rect(ax, X0 - hw.PCB_W / 2 - hw.BTN_PROUD, X0 - hw.PCB_W / 2, rp.PCB_Z0 + z - 2, rp.PCB_Z0 + z + 2, "0.3")
    for n, z in PLUGS.items():
        used = n == "I2C"
        rect(ax, X0 + hw.PCB_W / 2 - 5, X0 + hw.PCB_W / 2, rp.PCB_Z0 + z - 3.5, rp.PCB_Z0 + z + 3.5, COL["plug"], alpha=1.0 if used else 0.3)
        ax.text(X0 + hw.PCB_W / 2 + 0.8, rp.PCB_Z0 + z, n + ("" if used else " (free)"), fontsize=5.5, va="center", ha="right", color=COL["plug"])
    rect(ax, X0 + hw.PCB_W / 2, X0 + hw.PCB_W / 2 + 4, rp.PCB_Z0 + RTC_Z - 2.2, rp.PCB_Z0 + RTC_Z + 2.2, COL["plug"], alpha=0.3)
    for sx in SCREW_X:
        for sz in SCREW_Z:
            ax.plot(sx, sz, "o", ms=3, mfc="w", mec="k", mew=0.6, zorder=6)
    rect(ax, rp.HEAD_X - rp.HEAD_W / 2, rp.HEAD_X + rp.HEAD_W / 2, rp.HEAD_Z0, rp.HEAD_Z1, COL["usb"], alpha=0.5)
    ax.set_aspect("equal"); ax.set_xlim(46, -46); ax.set_ylim(14, 128)
    ax.set_title(title, fontsize=8); ax.set_xlabel("seen from the back (buttons on the right)", fontsize=7); ax.tick_params(labelsize=6)


def note(ax, text):
    ax.axis("off")
    ax.text(0.0, 1.0, text, fontsize=7.6, va="top", ha="left", linespacing=1.45, transform=ax.transAxes, wrap=True)


fig, A = plt.subplots(3, 3, figsize=(13.5, 19.5), gridspec_kw=dict(width_ratios=[1.0, 1.75, 1.35]))
xs = SCREW_X[0]                                           # the side sections: through the button side's screw column

# ---- 0: round 8 as it is -------------------------------------------------------------------------------------------
side(A[0, 0], xs, f"NOW (round 8)  side section at x {xs:.1f}")
rect(A[0, 0], *BAT["y"], *BAT["z"], COL["bat"])
back(A[0, 1], BAT["y"][0], BAT["y"][1], "NOW  the cell's depth band")
rect(A[0, 1], *BAT["x"], *BAT["z"], COL["bat"], alpha=0.75)
A[0, 1].text(rp.BAT_X, 44.5, "cell 68 x 35 x 10\n1 mm behind the plate", fontsize=7, ha="center", va="center")
note(A[0, 2],
     "NOW (round 8)\n"
     "- The cell lies on its long edge, taped 1 mm behind the board's back\n"
     "  plate, z 27..62. It is 68 wide in a cavity 69 wide: 0.5 a side.\n"
     "- It covers the plate's lower half and both lower screws.\n"
     "- It cannot move back: the body's flanks close in on its top corners.\n"
     "  Way in: +0.51 now, +0.14 at 1.15 back, -0.73 at 3.15 back\n"
     "  (the pebble's fork needs 4.0 behind the plate: 3.15 more).\n"
     "- So the pebble's fork does not fit between the plate and this cell.\n"
     "- Board held today: gasket tape on the glass + a foam pad between the\n"
     "  cell and the back wall.\n"
     "- I2C (used: logo LEDs) opens upwards at z 79..86, above the cell.\n"
     "  UART and J5 are free in the roly-poly.\n"
     "- Mass: the rocking centre is only 8.7 above the centre of mass, so\n"
     "  moving the 47 g cell 1 mm sideways tilts the rest position ~1 deg.")

# ---- 1: the stick ----------------------------------------------------------------------------------------------------
LEG = (BAT["y"][1] + 0.65, BAT["y"][1] + 0.65 + 2.5)      # behind the cell (0.65: foam)
Z_CR = (BAT["z"][1] + 1.0, BAT["z"][1] + 4.5)             # the crank bar, above the cell
TOP = SCREW_Z[1] + PAD / 2 + 0.3
ax = A[1, 0]
side(ax, xs, f"1  STICK behind the cell  side section at x {xs:.1f}")
rect(ax, *BAT["y"], *BAT["z"], COL["bat"])
ax.add_patch(Polygon([(F0, TOP), (F1, TOP), (F1, Z_CR[1]), (LEG[1], Z_CR[1]), (LEG[1], 23.8), (LEG[0], 23.8), (LEG[0], Z_CR[0]),
                      (F0, Z_CR[0])], closed=True, fc=COL["keeper"], ec="k", lw=0.5))
rect(ax, YB, F0, SCREW_Z[1] - PAD / 2, SCREW_Z[1] + PAD / 2, COL["keeper"])
for z0 in (31.0, 52.0):
    rect(ax, BAT["y"][1], LEG[0], z0, z0 + 6.0, COL["foam"])
rect(ax, F1, F1 + RIB_T, 93.2, 105.2, COL["rib"])                       # upper rib (the pebble's)
ax.add_patch(Polygon([(LEG[1], 23.0), (LEG[1], 31.0), (LEG[1] + 3, 31.0), (y_at(SEC[rp.WALL][2], xs + 3.2)[1], 26.0),
                      (y_at(SEC[rp.WALL][0], xs + 3.2)[1], 23.0)], closed=True, fc=COL["rib"], ec="k", lw=0.5))
ax.annotate("pad on the\nupper screw", (F0 - 0.5, SCREW_Z[1]), (-20.5, 116), fontsize=6, arrowprops=dict(arrowstyle="-", lw=0.4))
ax.annotate("upper rib", (F1 + 1.2, 99), (9, 112), fontsize=6, arrowprops=dict(arrowstyle="-", lw=0.4))
ax.annotate("foam pads\non the cell", (LEG[0] - 0.3, 55), (13, 72), fontsize=6, arrowprops=dict(arrowstyle="-", lw=0.4))
ax.annotate("lower rib\n(from the rim)", (LEG[1] + 4, 27), (11, 38), fontsize=6, arrowprops=dict(arrowstyle="-", lw=0.4))
ax = A[1, 1]
back(ax, BAT["y"][0], LEG[1], "1  STICK  (cell unchanged)")
rect(ax, *BAT["x"], *BAT["z"], COL["bat"], alpha=0.55)
SX = (X0 - 12.5, X0 - 8.5)                                              # the stick's plane (4 thick), beside the pin boss
rect(ax, SX[0], SX[1], 23.8, Z_CR[1], COL["keeper"])                    # leg (behind the cell) + crank
rect(ax, X0 - 20.5, SX[1], Z_CR[1], TOP, COL["keeper"])                 # the prong as the pebble's (12 wide), behind the plate
rect(ax, xs - PAD / 2, xs + PAD / 2, SCREW_Z[1] - PAD / 2, SCREW_Z[1] + PAD / 2, "w", lw=0.8)
lim = rp.inner_x_limits(99.0, F1, F1 + RIB_T)
rect(ax, lim[0], X0 - 18.0, 93.2, 105.2, COL["rib"])                    # upper rib from the button-side wall
rect(ax, SX[0] - 0.75, SX[1] + 0.75, 22.6, 31.0, COL["rib"], alpha=0.8)
ax.text(X0 - 10.5, 45, "leg behind\nthe cell", fontsize=6, ha="center", va="center", color="w", rotation=90)
note(A[1, 2],
     "1  STICK behind the cell  (recommended)\n"
     "- One flat printed part, 4 thick, printed lying on its side. It runs up\n"
     "  behind the cell, steps forward above it (z 63) and ends as the\n"
     "  pebble's prong with a pad on the button side's upper screw.\n"
     "- Upper end of the board: held at that screw, backed by an upper rib\n"
     "  on the side wall (the pebble's rib, same place).\n"
     "- Lower end: two foam pads on the stick press the cell, the cell\n"
     "  presses the plate. Backed by a short rib that grows from the rim\n"
     "  in front of the back wall.\n"
     "- Order: board with cables, stick, cell (slides up between plate and\n"
     "  stick), USB head, cup. The stick stands on the cell's top edge.\n"
     "- Nothing passes the plug column. Cell, wiring, mass, rest position\n"
     "  and the way in stay as printed in round 8.\n"
     "- Body: + 2 ribs inside (one starts at the rim, one has a 45 deg\n"
     "  corbel). Nothing shows outside. Cup unchanged.\n"
     "- Weak spot: the lower hold goes through the pouch and foam (firm\n"
     "  enough for a 34 g board, not a hard stop like the pads).")

# ---- 2: the pebble's fork, the cell upright behind it -------------------------------------------------------------------
UB = dict(x=(X0 - 17.5, X0 + 17.5), y=(F1, F1 + rp.BAT_T), z=(27.0, 95.0))
ax = A[2, 0]
side(ax, xs, f"2  PEBBLE'S FORK, cell upright  side section at x {xs:.1f}")
rect(ax, F0, F1, 26.5, TOP, COL["keeper"])
for sz in SCREW_Z:
    rect(ax, YB, F0, sz - PAD / 2, sz + PAD / 2, COL["keeper"])
rect(ax, *UB["y"], *UB["z"], COL["bat"])
rect(ax, F1, F1 + RIB_T, 93.2, 105.2, COL["rib"])
rect(ax, F1, F1 + RIB_T, 22.6, 39.2, COL["rib"])
ax.annotate("cell corner\n~3 from the\nback wall", (UB["y"][1], 94.5), (12, 110), fontsize=6, arrowprops=dict(arrowstyle="-", lw=0.4))
ax = A[2, 1]
back(ax, F0, UB["y"][1], "2  PEBBLE'S FORK  (cell upright, 35 wide)")
rect(ax, *UB["x"], *UB["z"], COL["bat"], alpha=0.45)
rect(ax, X0 - 24.0, X0 + 24.0, 26.5, 31.6, COL["keeper"])               # bridge over the lower screw row
for sx in (-1, 1):
    rect(ax, X0 + sx * 8.5, X0 + sx * 24.0, 26.5, 39.2, COL["keeper"])  # feet
rect(ax, X0 - 20.5, X0 - 8.5, 26.5, TOP, COL["keeper"])                 # prong, button side
for sx, sz in ((SCREW_X[0], SCREW_Z[0]), (SCREW_X[1], SCREW_Z[0]), (SCREW_X[0], SCREW_Z[1])):
    rect(ax, sx - PAD / 2, sx + PAD / 2, sz - PAD / 2, sz + PAD / 2, "w", lw=0.8)
lim = rp.inner_x_limits(99.0, F1, F1 + RIB_T)
rect(ax, lim[0], X0 - 18.0, 93.2, 105.2, COL["rib"])
lim = rp.inner_x_limits(30.0, F1, F1 + RIB_T)
rect(ax, lim[0], X0 - 21.5, 22.6, 39.2, COL["rib"])
rect(ax, X0 + 21.5, lim[1], 22.6, 39.2, COL["rib"])
ax.annotate("I2C plug: the cell\nright behind it", (X0 + hw.PCB_W / 2 - 2.5, rp.PCB_Z0 + PLUGS["I2C"]), (-20, 116), fontsize=6,
            arrowprops=dict(arrowstyle="-", lw=0.4))
note(A[2, 2],
     "2  PEBBLE'S FORK as it is, the cell upright behind it\n"
     "- Fork, 3 pads and 3 ribs exactly as on the pebble (the two lower\n"
     "  ribs become fins from the side walls, 12 and 22 long).\n"
     "- The cell has to leave the plate: only upright (35 wide, z 27..95)\n"
     "  does it fit behind the fork, centred on the board.\n"
     "- Cost: the cell's centre goes up 16.5, back 3.2, left 4:\n"
     "  centre of mass +2.5 up (margin 8.7 -> ~6.2, estimated), rest\n"
     "  position ~5 deg to the left until re-trimmed (about 2 more steel\n"
     "  spots on the right); fore-aft not computed.\n"
     "- The I2C plug and its wire (4.0 assumed) get no spare room: the\n"
     "  cell is right behind them. Its top corners are ~3 from the back\n"
     "  wall, so it can give them 2 more at most.\n"
     "- Variant 2b: the same fork with a smaller cell on its long edge\n"
     "  (e.g. 103450, 2000 mAh, 50 wide: clears the I2C plug, low\n"
     "  centre of mass). Needs a new cell and a new trim.")

fig.suptitle("Roly-poly board keeper: options (board frame: the board upright; in the world it leans 8 deg back). "
             "Red = printed keeper, violet = ribs in the body, yellow = cell, blue = plugs", fontsize=9, y=0.995)
fig.tight_layout(rect=(0, 0, 1, 0.99))
fig.savefig(OUT / "keeper-options.png", dpi=110)
print("wrote", OUT / "keeper-options.png")
