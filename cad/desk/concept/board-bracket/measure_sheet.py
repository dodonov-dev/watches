"""Picture of what to measure on the ESP32-S3-LCD-3.16 for the pebble's board keeper: the numbered items of
docs/lcd316-mechanical.md, "To measure". Drawn from the assumed values (the ones to be replaced by the measurements).
    ~/.venvs/cad/bin/python measure_sheet.py      -> docs/lcd316-to-measure.png"""
import pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyBboxPatch

OUT = pathlib.Path(__file__).resolve().parents[4] / "docs" / "lcd316-to-measure.png"
W, H = 33.35, 78.85                                  # PCB, seen from the back, USB-C at the bottom
SCREW = [(3.0, 3.0), (W - 3.0, 3.0), (3.0, 75.75), (W - 3.0, 75.75)]
SOCK = {"UART": 22.45, "J5": 39.42, "I2C": 56.39, "RTC": 67.5}       # above the PCB's bottom edge
BAT = (10.675, 24.075, 14.6, 28.1)                   # the plate's window, seen from the back
HOT, COOL, DONE = "#c62828", "#1a4f8a", "#2e7d32"                     # needed before the shell is printed / the fork only
PCB_C, PLATE_C, CONN_C = "#7fa383", "#d9ecf5", "#f7f7f7"


def dim(ax, p0, p1, n, col, txt=None, off=(0, 0), ext=()):
    """dimension arrow p0 <-> p1 with its item number in a circle; ext: extension lines [(from, to), ...]"""
    for a, b in ext:
        ax.plot([a[0], b[0]], [a[1], b[1]], color=col, lw=0.8)
    ax.annotate("", p0, p1, arrowprops=dict(arrowstyle="<->", color=col, lw=1.8, shrinkA=0, shrinkB=0))
    m = ((p0[0] + p1[0]) / 2 + off[0], (p0[1] + p1[1]) / 2 + off[1])
    ax.text(*m, str(n), ha="center", va="center", fontsize=13, fontweight="bold", color="white",
            bbox=dict(boxstyle="circle,pad=0.25", fc=col, ec="none"), zorder=10)
    if txt:
        ax.text(m[0], m[1], txt, fontsize=9, color=col)


fig = plt.figure(figsize=(17, 10.5), facecolor="white")
ax = fig.add_axes([0.01, 0.02, 0.40, 0.93]); ax.set_aspect("equal"); ax.axis("off")
ax.set_xlim(-19, 47); ax.set_ylim(-9, 86)
ax.set_title("Back of the board (acrylic plate side), USB-C at the bottom", fontsize=13, loc="left")
ax.add_patch(Rectangle((0, 0), W, H, fc=PLATE_C, ec="black", lw=1.2))
for k in ("UART", "J5", "I2C"):                                              # the plate's cut-outs, the sockets in them
    s = SOCK[k]
    ax.add_patch(Rectangle((0, s - 3.5), 5.0, 7.0, fc=PCB_C, ec="black", lw=0.8))
    ax.add_patch(Rectangle((0.2, s - 2.8), 4.3, 5.6, fc=CONN_C, ec="black", lw=0.8))
    ax.text(6.0, s, k, va="center", fontsize=10)
s = SOCK["RTC"]
ax.add_patch(Rectangle((0.2, s - 2.2), 4.3, 4.4, fc=CONN_C, ec="black", lw=0.8, ls="--"))
ax.text(6.0, s, "RTC (under the plate)", va="center", fontsize=10)
ax.add_patch(Rectangle((BAT[0], BAT[2]), BAT[1] - BAT[0], BAT[3] - BAT[2], fc=PCB_C, ec="black", lw=0.8))
ax.add_patch(Rectangle((14.2, 16.6), 6.0, 4.5, fc=CONN_C, ec="black", lw=0.8)); ax.text(17.2, 24.5, "BAT", ha="center", fontsize=10)
for x, y in SCREW:
    ax.add_patch(Circle((x, y), 1.9, fc="#b9c9d2", ec="black", lw=0.8)); ax.add_patch(Circle((x, y), 1.1, fc="#8a8a8a", ec="black", lw=0.6))
ax.add_patch(Rectangle((W / 2 - 4.5, -1.5), 9.0, 7.0, fc="#b0b0b0", ec="black", lw=0.8)); ax.text(W / 2, -4.2, "USB-C", ha="center", fontsize=10)
for nm, z in (("switch", 11.5), ("BOOT", 25.72), ("RST", 36.49)):
    ax.add_patch(Rectangle((W, z - 2.0), 1.0, 4.0, fc="#c44", ec="black", lw=0.6)); ax.text(W + 2.0, z, nm, va="center", fontsize=9)
ax.plot([W / 2, W / 2], [9, 34], color="gray", lw=0.8, ls="-.")                # the board's centre line
ax.text(W / 2 + 0.6, 33.0, "centre line", fontsize=8, color="gray")
# plugs: UART / J5 / I2C stand up out of their sockets (see the section), RTC goes in from the side
for k in ("UART", "J5", "I2C"):
    ax.add_patch(Rectangle((0.8, SOCK[k] - 2.0), 3.1, 4.0, fc="#e8c85a", ec="black", lw=0.8))
ax.text(-18.5, SOCK["J5"] - 1.5, "UART, J5, I2C:\nplugs stand up,\ntowards you\n(4a in the section)", fontsize=9, color=COOL)
s = SOCK["RTC"]
ax.add_patch(Rectangle((-3.0, s - 1.8), 3.2, 3.6, fc="#e8c85a", ec="black", lw=0.8))
for dy in (-0.6, 0.6):
    ax.plot([-3.0, -4.9 - 0.4 * (0.6 - dy), -4.9 - 0.4 * (0.6 - dy)], [s + dy, s + dy, s - 8 + dy], color="#444", lw=1.4, solid_joinstyle="round")
ax.text(-18.5, s - 7.0, "RTC: plug + wires\nto their outermost\npoint", fontsize=9, color=HOT)
dim(ax, (0, s + 3.4), (-5.4, s + 3.4), "4b", HOT, off=(0, 2.5), ext=[((0, s + 1.8), (0, s + 4.2)), ((-5.4, s + 0.8), (-5.4, s + 4.2))])
# 5: a cut-out's depth and length (UART)
s = SOCK["UART"]
dim(ax, (0, s - 5.2), (5.0, s - 5.2), "5a", COOL, off=(0, -2.6), ext=[((0, s - 3.5), (0, s - 6.0)), ((5.0, s - 3.5), (5.0, s - 6.0))])
dim(ax, (-6.5, s - 3.5), (-6.5, s + 3.5), "5b", COOL, off=(-3.0, 0), ext=[((0, s - 3.5), (-7.3, s - 3.5)), ((0, s + 3.5), (-7.3, s + 3.5))])
# 6: RTC centre below the top-left screw's centre
dim(ax, (-11.0, SOCK["RTC"]), (-11.0, 75.75), 6, COOL, off=(-3.0, 0), ext=[((0.2, SOCK["RTC"]), (-12.0, SOCK["RTC"])), ((3.0, 75.75), (-12.0, 75.75))])
# 7: BAT window: width, offset of its centre from the centre line
dim(ax, (BAT[0], 11.5), (BAT[1], 11.5), "7a", COOL, off=(0, -2.6), ext=[((BAT[0], BAT[2]), (BAT[0], 10.7)), ((BAT[1], BAT[2]), (BAT[1], 10.7))])
cx = (BAT[0] + BAT[1]) / 2
ax.plot([cx, cx], [BAT[3], 33.5], color=COOL, lw=0.8)
dim(ax, (W / 2, 31.0), (cx, 31.0), "7b", COOL, off=(6.5, 0))
# 8: the screw recess's diameter
x, y = SCREW[3]
dim(ax, (x - 1.9, y + 4.0), (x + 1.9, y + 4.0), 8, COOL, off=(4.8, 0), ext=[((x - 1.9, y), (x - 1.9, y + 4.8)), ((x + 1.9, y), (x + 1.9, y + 4.8))])

# ---- section across the board at a socket ----
bx = fig.add_axes([0.42, 0.60, 0.56, 0.36]); bx.set_aspect("equal"); bx.axis("off")
bx.set_xlim(-10, 46); bx.set_ylim(-4.5, 13.5)
bx.set_title("Section across the board at an upward socket: UART, J5, I2C (glass / front down, back up)", fontsize=13, loc="left")
bx.add_patch(Rectangle((1.075, 0), 31.2, 3.9, fc="#aebccb", ec="black", lw=1.0)); bx.text(W / 2, 1.95, "glass (LCD)", ha="center", va="center", fontsize=10)
bx.add_patch(Rectangle((0, 3.9), W, 1.0, fc=PCB_C, ec="black", lw=1.0)); bx.text(W / 2, 4.4, "PCB", ha="center", va="center", fontsize=9)
for x in (3.0, W - 3.0):
    bx.add_patch(Rectangle((x - 1.75, 4.9), 3.5, 2.1, fc="#d0a060", ec="black", lw=0.8))
bx.text(W - 3.0, 5.95, "standoff", ha="center", va="center", fontsize=8)
bx.add_patch(Rectangle((5.0, 7.0), W - 5.0, 2.0, fc=PLATE_C, ec="black", lw=1.0)); bx.text(11.0, 8.0, "acrylic plate", ha="center", va="center", fontsize=10)
bx.add_patch(Rectangle((W - 3.0 - 1.9, 8.0), 3.8, 1.0, fc="white", ec="black", lw=0.8)); bx.add_patch(Rectangle((W - 3.0 - 1.5, 8.0), 3.0, 0.8, fc="#8a8a8a", ec="black", lw=0.6))
bx.add_patch(Rectangle((0.2, 4.9), 4.3, 3.1, fc=CONN_C, ec="black", lw=0.8)); bx.text(-0.4, 5.6, "socket", ha="right", va="center", fontsize=8)
bx.add_patch(Rectangle((0.8, 5.6), 3.1, 4.4, fc="#e8c85a", ec="black", lw=0.8)); bx.text(2.35, 7.6, "plug", ha="center", va="center", fontsize=8)
for i, x in enumerate((1.3, 2.0, 2.7, 3.4)):
    bx.plot([x, x, -7.0], [10.0, 11.4 + 0.2 * i, 11.4 + 0.2 * i], color="#444", lw=1.4, solid_joinstyle="round")
bx.text(12.0, 9.6, "(the plate is cut out over the socket)", fontsize=8, color="gray")
dim(bx, (7.5, 9.0), (7.5, 12.0), "4a", COOL, off=(2.6, 0.3), ext=[((3.4, 12.0), (8.3, 12.0))])
dim(bx, (38.5, 0), (38.5, 9.0), 1, DONE, off=(2.4, 0), ext=[((32.3, 0), (39.5, 0)), ((W, 9.0), (39.5, 9.0))])
bx.text(40.0, 1.0, "measured: 9.15", fontsize=9, color=DONE)
dim(bx, (20.0, 7.0), (20.0, 9.0), "2a", COOL, off=(-2.6, 0))
dim(bx, (26.0, 4.9), (26.0, 7.0), "2b", COOL, off=(-2.6, 0))
dim(bx, (-3.0, 8.0), (-3.0, 9.0), 3, COOL, off=(-2.6, 0), ext=[((0.2, 8.0), (-4.0, 8.0)), ((5.0, 9.0), (-4.0, 9.0))])

# ---- the list ----
cx_ = fig.add_axes([0.42, 0.03, 0.36, 0.56]); cx_.axis("off"); cx_.set_xlim(0, 1); cx_.set_ylim(0, 1)
rows = [(1, DONE, "Total thickness, glass front to the plate's back face: measured 9.15"),
        ("2", COOL, "a: plate thickness (2.0?)   b: standoff height (~2.1?)"),
        (3, COOL, "Socket top below the plate's back face (~1); also with a plug in"),
        ("4", HOT, "a: upward plugs + wire bend above the plate's back face (4.0?)\nb: RTC plug + wires beyond the board's edge (model: 4.0)"),
        ("5", COOL, "A cut-out: a depth in from the edge (~5), b length (~7)"),
        (6, COOL, "RTC socket's centre below the top-left screw's centre (~8)"),
        ("7", COOL, "BAT window: a width (~13), b its centre off the centre line (~0.7)"),
        (8, COOL, "Screw recess diameter in the plate"),
        (9, COOL, "Revision: 1 kΩ across the RTC pins, board on USB (right)"),
        (10, COOL, "Polarity of the RTC socket (right)")]
cx_.text(0.0, 0.97, "What to measure (mm)", fontsize=13, fontweight="bold", va="top")
for i, (n, col, t) in enumerate(rows):
    y = 0.87 - i * 0.083
    cx_.text(0.03, y, str(n), ha="center", va="center", fontsize=11, fontweight="bold", color="white", bbox=dict(boxstyle="circle,pad=0.25", fc=col, ec="none"))
    cx_.text(0.08, y, t, va="center", fontsize=9.6)
cx_.add_patch(FancyBboxPatch((0.0, 0.0), 0.98, 0.065, boxstyle="round,pad=0.01", fc="#fdecea", ec=HOT, lw=1.0))
cx_.text(0.02, 0.032, "Green: measured. Red (4b): touches the shell's lower rib. Blue: fork or RTC cell only.", va="center", fontsize=10.5, color=HOT)

# ---- multimeter ----
dx = fig.add_axes([0.79, 0.03, 0.20, 0.56]); dx.axis("off"); dx.set_xlim(0, 10); dx.set_ylim(0, 26)
dx.text(0, 25.3, "RTC socket, board powered over USB", fontsize=11, fontweight="bold", va="top")
def socket(y):
    dx.add_patch(Rectangle((1.0, y), 3.0, 3.6, fc=CONN_C, ec="black", lw=1.0))
    for py in (y + 0.9, y + 2.7):
        dx.add_patch(Circle((2.5, py), 0.35, fc="#c9a227", ec="black", lw=0.6))
socket(17.5)
dx.plot([2.5, 6.0, 6.0], [20.2, 20.2, 19.9], color="black", lw=1.2); dx.plot([2.5, 6.0, 6.0], [18.4, 18.4, 18.7], color="black", lw=1.2)
dx.add_patch(Rectangle((5.6, 18.7), 0.8, 1.2, fc="#e9d8a6", ec="black", lw=1.0)); dx.text(6.7, 19.3, "1 kΩ", va="center", fontsize=10)
dx.add_patch(Circle((8.9, 19.3), 0.8, fc="white", ec=COOL, lw=1.4)); dx.text(8.9, 19.3, "V", ha="center", va="center", fontsize=11, color=COOL)
dx.plot([6.0, 8.9, 8.9], [20.2, 21.2, 20.1], color=COOL, lw=1.0); dx.plot([6.0, 8.9, 8.9], [18.4, 17.4, 18.5], color=COOL, lw=1.0)
dx.text(0, 16.6, "9  Volts across the resistor:\n   ~0.5 V = Rev 1.1,  ~3 V = original.\n   Never short the two pins.", fontsize=10, va="top", color=COOL)
socket(7.0)
dx.add_patch(Circle((8.9, 8.8), 0.8, fc="white", ec=COOL, lw=1.4)); dx.text(8.9, 8.8, "V", ha="center", va="center", fontsize=11, color=COOL)
dx.plot([2.5, 8.9, 8.9], [9.7, 10.6, 9.6], color=COOL, lw=1.0)
dx.plot([8.9, 8.9, 5.2], [8.0, 6.3, 6.3], color=COOL, lw=1.0); dx.text(0.9, 6.3, "USB-C shell (GND)", va="center", fontsize=9)
dx.text(0, 5.0, "10  No resistor. One probe on the USB\n    shell, the other on each pin in turn:\n    the pin showing ~ +3 V is plus.\n    Match the cell's lead to it.", fontsize=10, va="top", color=COOL)

fig.savefig(OUT, dpi=120); print(OUT)
