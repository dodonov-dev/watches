"""Concept sketch, board keeper round E (user, 2026-11-27): the fork becomes a frame open on the plug side (a top bar
across both upper screws, the button side's prong, a lower block across both lower screws), a 4th rib on the plug
side's wall at the upper screw, above the RTC socket; ribs as wide as the board's way in allows. Left: back view to
scale (round D dashed). Right: clay from behind. Real round C shell (no ribs); the rest are concept boxes / polygons.
    ~/.venvs/cad/bin/python keeper_e_clay.py"""
import math, pathlib
import numpy as np
import pyvista as pv
import trimesh
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle, Circle

HERE = pathlib.Path(__file__).parent
TP = HERE.parents[1] / "to-print"
A = math.radians(15); C, S = math.cos(A), math.sin(A)
M = np.eye(4); M[1, 1:3] = (C, S); M[2, 1:3] = (-S, C)          # body (x, t, s) -> world
TN, SN = np.array([0, C, -S]), np.array([0, S, C])
W = lambda x, t, s: (M[:3, :3] @ np.array([x, t, s])).tolist()

# ---- numbers (body frame; from smooth.py's KEEPER / housing.py unless marked NEW) ------------------------
E_X = 33.35 / 2                                 # board edge
T_PLATE, T_F0, T_F1, T_R1 = 13.04, 14.54, 17.04, 20.54   # NEW: ribs 3.5 thick (D 2.5)
SCR_X, SCR_S = 13.675, (19.8, 92.55)
PCB_S = (16.8, 95.65)
PLUGS = {"UART": 39.25, "J5": 56.22, "I2C": 73.19}; RTC_S = 84.3
BAT_WIN = (-7.4, 6.0, 31.4, 44.9)
AD = (6.0, 8.3, 16.8)                           # adapter half width, s0, s1
SLOT_X, EAR_X, EAR_S1, TOP_S = 8.5, 24.0, 30.0, 95.3
WALL_GAP = 0.5                                  # NEW: the fork's edges this far from the side walls (D: 0.85)
BAR_S0 = 88.0                                   # NEW: top bar s 88.0..95.3, wall to wall
LOW_S0 = 17.1                                   # NEW: lower block starts above the adapter (it goes in after the fork)
PRONG_X, HEAD_S0 = 21.0, 80.0                   # NEW: above s 80 the fork widens to the walls (D: 20.5..21.0 all the way)
# NEW (user, 2026-11-27: the board slides in along the front wall, so ribs may reach over it): behind the pads
RIBS = [(-1, 11.0, 84.0, 96.0),                 # button side: over the whole pad (x 11.2..16.2)
        (1, 13.0, 95.5, 96.0),                  # plug side: a 45 deg wedge that leaves the RTC socket and its plug in view
        (-1, 14.0, 24.8, 31.0), (1, 14.0, 24.8, 31.0)]   # lower pair: as far in as 45 deg from the rim allows
RIBS_D = [(-1, 17.5, 84.0, 96.0), (-1, 21.5, 15.0, 31.0), (1, 21.5, 15.0, 31.0)]

tm = trimesh.load(TP / "pebble-C-shell.stl")

def wall(s, t=(T_F1 + T_R1) / 2):
    seg = trimesh.intersections.mesh_plane(tm, SN, SN * s)
    x = seg[..., 0]; tt = seg[..., 1] * C - seg[..., 2] * S
    c = (tt[:, 0] - t) * (tt[:, 1] - t) < 0
    u = (t - tt[c, 0]) / (tt[c, 1] - tt[c, 0]); xc = x[c, 0] + u * (x[c, 1] - x[c, 0])
    return xc[xc > 0].min()

SS = np.arange(6.5, 99.01, 0.5); XW = np.array([wall(s) for s in SS]); XWF = np.array([wall(s, (T_F0 + T_F1) / 2) for s in SS])
xw = lambda s: float(np.interp(s, SS, XW)); xwf = lambda s: float(np.interp(s, SS, XWF))

def rib_poly(sx, x_in, s_a, s_b, emb=1.0):
    s_c = s_a
    while x_in + (s_a - s_c) < xw(s_c) + emb: s_c -= 0.05
    side = [(sx * (xw(s) + emb), s) for s in np.arange(s_b, s_c, -0.5)]
    return [(sx * x_in, s_a), (sx * x_in, s_b)] + side + [(sx * (x_in + s_a - s_c), s_c)]

def fork_poly():
    """outline (x positive = plug side). Above HEAD_S0 the outer edges follow the side walls, WALL_GAP inside them"""
    edge = lambda s: min(EAR_X, xwf(s) - WALL_GAP)
    head = [(edge(s), s) for s in np.r_[np.arange(HEAD_S0 + 3.0, TOP_S, 1.0), TOP_S]]
    plug = [(SLOT_X, BAR_S0), (edge(BAR_S0), BAR_S0)] + [q for q in head if q[1] > BAR_S0]
    button = [(-x, s) for x, s in head[::-1]] + [(-PRONG_X, HEAD_S0), (-PRONG_X, EAR_S1)]
    return ([(-EAR_X, 4.7), (-SLOT_X, 4.7), (-SLOT_X, LOW_S0), (SLOT_X, LOW_S0), (SLOT_X, 4.7), (EAR_X, 4.7), (EAR_X, EAR_S1),
             (-SLOT_X, EAR_S1), (-SLOT_X, BAR_S0)] + plug + button + [(-EAR_X, EAR_S1)]), edge

FORK, EDGE = fork_poly()
FORK_D = [(-EAR_X, 4.7), (EAR_X, 4.7), (EAR_X, EAR_S1), (SLOT_X, EAR_S1), (SLOT_X, 8.0), (-SLOT_X, 8.0), (-SLOT_X, 95.3), (-20.5, 95.3),
          (-21.0, 93.8), (-21.0, EAR_S1), (-EAR_X, EAR_S1)]
PADS = [(sx, s) for sx in (-1, 1) for s in SCR_S]

# ---- clay --------------------------------------------------------------------------------------------------
def box(x0, x1, t0, t1, s0, s1):
    x0, x1 = sorted((x0, x1))
    return pv.Box((x0, x1, t0, t1, s0, s1)).triangulate().transform(M, inplace=False)

def prism(poly, t0, t1):
    import manifold3d as m3
    P = np.array(poly)                                               # (x, s)
    if 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]) < 0: P = P[::-1]
    me = m3.Manifold.extrude(m3.CrossSection([P.tolist()]), t1 - t0).to_mesh()                          # (x, s, t - t0)
    V = np.asarray(me.vert_properties)[:, :3]; F = np.asarray(me.tri_verts)
    pts = np.c_[V[:, 0], V[:, 2] + t0, V[:, 1]]
    return pv.PolyData(pts, np.c_[np.full(len(F), 3), F].ravel()).transform(M, inplace=False)

def clay(path):
    shell = pv.read(TP / "pebble-C-shell.stl").clip(normal=tuple(TN), origin=W(0, T_R1 + 0.3, 0), invert=True)
    cx = E_X - 5.0
    plate = [box(-E_X, cx, T_PLATE - 2, T_PLATE, *PCB_S)]
    edges = [PCB_S[0]] + [v for s in PLUGS.values() for v in (s - 3.5, s + 3.5)] + [PCB_S[1]]
    plate += [box(cx, E_X, T_PLATE - 2, T_PLATE, a, b) for a, b in zip(edges[0::2], edges[1::2])]
    pcb = box(-E_X, E_X, 7.79, 8.79, *PCB_S)
    plugs = [box(cx, E_X, 8.79, T_PLATE + 4.0, s - 3.5, s + 3.5) for s in PLUGS.values()]
    plugs.append(box(E_X - 4, E_X + 4.0, 8.79, T_PLATE - 2.2, RTC_S - 2.2, RTC_S + 2.2))
    fork = [prism(FORK, T_F0, T_F1)] + [box(sx * (SCR_X - 2.5), sx * (SCR_X + 2.5), T_PLATE, T_F0, s - 2.5, s + 2.5) for sx, s in PADS]
    ribs = [prism(rib_poly(*r), T_F1, T_R1) for r in RIBS]
    adapter = box(-AD[0], AD[0], 5.89, 26.89, AD[1], AD[2])
    parts = [(shell, "#e2d6c0", 1), (pv.merge(ribs), "#b98a4e", 1), (pcb, "#5f7f62", 1), (pv.merge(plate), "#cfe3ee", 0.55),
             (pv.merge(plugs), "#f4f4f4", 1), (pv.merge(fork), "#e8893a", 1), (adapter, "#7a4f86", 0.35)]
    pl = pv.Plotter(off_screen=True, window_size=(900, 1250)); pl.set_background("#d8d5cf", top="#f3f1ed")
    for m, col, op in parts:
        pl.add_mesh(m, color=col, opacity=op, ambient=0.3, diffuse=0.75, specular=0.08)
    ctr = W(0, 15, 50)
    pl.camera_position = [[ctr[0] + 120, ctr[1] + 290, ctr[2] - 40], ctr, list(SN)]; pl.camera.view_angle = 24
    for txt, p in [("new rib (above the RTC socket)", W(21, T_R1, 93)), ("top bar", W(0, T_F1, 91.5)), ("upper rib, over the pad", W(-16, T_R1, 90)),
                   ("open side: cables", W(15, T_F1, 55)), ("lower block over both lower screws", W(0, T_F1, 24)),
                   ("USB adapter (goes in after the fork)", W(0, 27, 11)), ("RTC plug", W(21, 12, RTC_S))]:
        pl.add_point_labels([p], [txt], font_size=13, point_size=1, shape_opacity=0.85, always_visible=True, text_color="black", shape_color="white", margin=3)
    pl.enable_anti_aliasing("ssaa"); pl.screenshot(str(path)); pl.close()

# ---- back view ------------------------------------------------------------------------------------------------
def back_view(ax):
    ax.plot(np.r_[XWF, -XWF[::-1]], np.r_[SS, SS[::-1]], color="#8a7a5c", lw=2.5)                       # cavity wall at the fork's depth
    ax.add_patch(Rectangle((-E_X, PCB_S[0]), 2 * E_X, PCB_S[1] - PCB_S[0], fc="#dcecf4", ec="#6d8fa3", lw=1.2))
    for n, s in PLUGS.items():
        ax.add_patch(Rectangle((E_X - 5, s - 3.5), 5, 7, fc="white", ec="#444", lw=1)); ax.text(E_X - 2.5, s, n, ha="center", va="center", fontsize=7)
    ax.add_patch(Rectangle((E_X, RTC_S - 2.2), 4.0, 4.4, fc="white", ec="#444", lw=1, ls="--")); ax.text(E_X + 2, RTC_S, "RTC", ha="center", va="center", fontsize=7)
    ax.add_patch(Rectangle((BAT_WIN[0], BAT_WIN[2]), BAT_WIN[1] - BAT_WIN[0], BAT_WIN[3] - BAT_WIN[2], fc="white", ec="#6d8fa3", lw=1))
    ax.text(-0.7, 38, "BAT\nwindow", ha="center", va="center", fontsize=7)
    ax.add_patch(Rectangle((-AD[0], AD[1]), 2 * AD[0], AD[2] - AD[1], fc="#cbb6d3", ec="#7a4f86", lw=1)); ax.text(0, 12.5, "USB\nadapter", ha="center", va="center", fontsize=7)
    for r in RIBS: ax.add_patch(Polygon(rib_poly(*r), fc="#b98a4e", ec="#6b4a1c", lw=1, zorder=3))
    for r in RIBS_D: ax.add_patch(Polygon(rib_poly(*r), fc="none", ec="k", lw=0.9, ls=":", zorder=6))
    ax.add_patch(Polygon(FORK, fc="#e8893a", ec="#8a4a10", lw=1.4, alpha=0.6, zorder=4))
    ax.add_patch(Polygon(FORK_D, fc="none", ec="k", lw=0.9, ls="--", zorder=6))
    for sx, s in PADS:
        ax.add_patch(Rectangle((sx * SCR_X - 2.5, s - 2.5), 5, 5, fc="#b85c12", ec="k", lw=0.8, zorder=5)); ax.add_patch(Circle((sx * SCR_X, s), 1.1, fc="#ddd", ec="k", lw=0.6, zorder=7))
    note = lambda txt, xy, xt, **k: ax.annotate(txt, xy, xt, fontsize=8.5, arrowprops=dict(arrowstyle="->", lw=0.8), zorder=9,
                                               bbox=dict(fc="white", ec="#999", lw=0.5, alpha=0.9), **k)
    note("NEW rib, plug side: 45 deg wedge\nabove the RTC socket and plug", (19, 93), (30, 104), ha="center")
    note("NEW top bar s 88..95.3, wall to wall,\npad over each upper screw", (2, 92), (-9, 105), ha="center")
    note("upper rib reaches over the board to x 11:\nright behind the pad (D: stopped at 17.5)", (-14, 86), (-42, 76), ha="center")
    note("open side: cables leave here.\nThe battery cable is slipped in\nbefore the fork goes up", (17, 60), (40, 58), ha="center")
    note("lower block starts above the adapter:\nfork first, then the adapter", (0, 19), (-41, 40), ha="center")
    note("lower ribs: 21.5 -> 14 at the top,\n45 deg up from the rim", (-19, 26), (-41, 12), ha="center")
    note("UART / J5 / I2C must be empty\nwhile the fork slides up\n(the bar passes over them)", (E_X - 2.5, 50), (40, 36), ha="center")
    ax.plot([], [], "k--", lw=0.9, label="round D fork"); ax.plot([], [], "k:", lw=0.9, label="round D ribs")
    ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
    ax.set_xlim(58, -58); ax.set_ylim(0, 110); ax.set_aspect("equal")                                    # seen from behind: plug side on the left
    ax.set_xlabel("x, mm (seen from behind: plug side left, button side right)"); ax.set_ylabel("s up the face, mm")
    ax.set_title("Round E keeper, back view to scale: fork (orange), pads (dark), ribs (brown)", fontsize=10)

if __name__ == "__main__":
    clay(HERE / "keeper-e-clay.png")
    fig, ax = plt.subplots(1, 2, figsize=(17, 10.2), gridspec_kw=dict(width_ratios=[1.25, 0.8]))
    back_view(ax[0]); ax[1].imshow(plt.imread(HERE / "keeper-e-clay.png")); ax[1].axis("off")
    ax[1].set_title("clay, from behind (shell cut behind the ribs)", fontsize=10)
    plt.tight_layout(); plt.savefig(HERE / "keeper-e-views.png", dpi=95); (HERE / "keeper-e-clay.png").unlink()
    print(HERE / "keeper-e-views.png")
    for s in (20, 30, 60, 84, 88, 92, 95.3): print(f"wall at s {s}: fork depth {xwf(s):.2f}, rib depth {xw(s):.2f}")
    print("fork edge at s 84, 88, 92, 95.3:", [round(EDGE(q), 2) for q in (84, 88, 92, 95.3)], "rib corbels end at s", [round(min(p[1] for p in rib_poly(*r)), 1) for r in RIBS])
