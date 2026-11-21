#!/usr/bin/env python3
"""Roly-poly battery study (handoff "Start here", 2026-11-20): which cell, where, and what it does to the rocking.

Numbers only, on the round-5 geometry: the printed parts are the exported meshes (out-rolypoly/{body,cup-rock,door}.stl),
the cast is integrated from the CAD's own inner sections, the board / rods / misc / segments are the CAD's mass model
(rolypoly.mass_parts). Each case swaps the battery (size, mass, position) and, where the cell sits in the bowl, takes its
volume (and 1 mm round it) out of the cast. The trim (plumb) is not modelled: the centre of mass is moved to x 0.

  ~/.venvs/cad/bin/python cad/desk/concept/rolypoly_battery.py [BOARD=52]   -> table on stdout
"""
import sys, math, pathlib
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import rolypoly as r

ARGS = dict(kv.split("=") for kv in sys.argv[1:])
M_BOARD = float(ARGS.get("BOARD", 52.0))          # user (2026-11-20): "online checks: 52 g" (board stack, taken as the board)
CAST_TOP = 17.9                                   # round 5: pourable cavity up to the trim terrace's step
RHO_CAST = 5.1
GAP = 1.0                                         # battery to walls / cast / board, at least

# cells: name -> (L along x, W, T, mass g). Masses of the catalogue cells are typical vendor figures (assumed).
CELLS = {
    "3000 mAh 10x35x68 (have)": (68.0, 35.0, 10.0, 55.0),
    "2000 mAh 103450": (50.0, 34.0, 10.0, 38.0),
    "1500 mAh 103048 (BerryBase)": (47.7, 29.5, 9.9, 32.0),
    "1200 mAh 102060": (60.0, 20.0, 10.0, 25.0),
    "1000 mAh 102050": (50.0, 20.0, 10.0, 21.0),
    "1800 mAh 902060": (60.0, 20.0, 9.0, 33.0),
}


# ---- inner sections of the shell (the CAD's inner offset), for the cast and the fits --------------------------------
def poly_props(xy):
    x, y = xy[:, 0], xy[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    c = x * y1 - x1 * y
    A = c.sum() / 2
    cx = ((x + x1) * c).sum() / (6 * A)
    cy = ((y + y1) * c).sum() / (6 * A)
    Ixx_x2 = ((x * x + x * x1 + x1 * x1) * c).sum() / 12        # integral of x^2 dA
    return abs(A), cx, cy, abs(Ixx_x2)


ZS = np.linspace(r.WALL + 0.3, CAST_TOP, 80)
SECS = r.offset_rows(r.WALL, list(ZS))


def free_span(z, y0, y1):
    try:
        lo, hi = r.inner_x_limits(z, y0 - GAP, y1 + GAP)
    except ValueError:                                 # the y band leaves the section: no room at this level
        return 0.0, 0.0
    return lo + GAP, hi - GAP


def box_fits(L, y0, y1, z0, z1, x=0.0):
    for z in np.linspace(z0, z1, 6):
        lo, hi = free_span(z, y0, y1)
        if x - L / 2 < lo or x + L / 2 > hi:
            return False
    return True


def cast_part(top, hole=None):
    """Cast up to `top`, minus an axis-aligned box `hole` (x0, x1, y0, y1, z0, z1) grown by GAP."""
    dz = ZS[1] - ZS[0]
    m = mx = my = mz = ixz = 0.0
    slabs = []
    for z, sec in zip(ZS, SECS):
        if z > top:
            break
        A, cx, cy, ix2 = poly_props(sec[:, :2])
        if hole is not None and hole[4] - GAP <= z <= hole[5] + GAP:
            hx = (hole[1] - hole[0]) + 2 * GAP
            hy = (hole[3] - hole[2]) + 2 * GAP
            hcx = (hole[0] + hole[1]) / 2
            ah = hx * hy
            A, cx, cy = A - ah, (A * cx - ah * hcx) / (A - ah), (A * cy - ah * (hole[2] + hole[3]) / 2) / (A - ah)
            ix2 -= ah * (hcx ** 2 + hx ** 2 / 12)
        k = RHO_CAST / 1000 * A * dz
        slabs.append((k, cx, cy, z, ix2 * RHO_CAST / 1000 * dz))
    M = sum(s[0] for s in slabs)
    c = np.array([sum(s[0] * s[i] for s in slabs) / M for i in (1, 2, 3)])
    Iyy = sum(s[4] + s[0] * (s[3] - c[2]) ** 2 for s in slabs) - M * c[0] ** 2
    I = np.diag([Iyy, Iyy, Iyy])                       # only I[1, 1] (rocking axis) is used
    return dict(m=M, c=c, I=I, name="cast")


MESH = {n: r.mesh_props(r.OUT / f"{n}.stl", r.RHO_DOOR if n == "door" else r.RHO_PLA) for n in ("body", "cup-rock", "door")}
PTS = np.vstack([MESH["body"]["pts"], MESH["cup-rock"]["pts"]])


def segments_on_cast(n=6, z0=CAST_TOP, y=1.0):
    """The trim layer: n segments of 12 x 19 x 4 on the cast, spread symmetric along x (round 5 fits 6)."""
    xs = (np.arange(n) - (n - 1) / 2) * (r.SEG[0] + r.SEG_GAP)
    return [(x, y, r.SEG[0], r.SEG[1], z0) for x in xs]


def evaluate(bat_box, m_bat, cast, segs):
    parts = r.mass_parts(MESH, segs, battery=bat_box, extra=[cast], m_board=M_BOARD, m_bat=m_bat)
    M, G, I = r.combine(parts)
    G = G.copy()
    G[0] = 0.0                                         # trimmed plumb
    st = dict(M=M, G=G, I=I)
    margin, T, k = r.rocking(st)
    _, fwd, back = r.pitch_limits(PTS, G, step=0.1)
    return M, G, margin, T, k, fwd, back


def positions(L, W, T):
    """Candidate placements: (label, box (x0, y0, z0, x1, y1, z1), in the bowl?)."""
    out = []
    y0 = r.BAT_Y0                                     # behind the board stack (+ Kapton gap)
    # on its long edge behind the board, from z 23 (round 5)
    out.append(("edge, behind board", (-L / 2, y0, 23.0, L / 2, y0 + T, 23.0 + W), False))
    # flat on a shelf just above the seam, behind the board
    out.append(("flat, on the seam, behind board", (-L / 2, y0, 23.0, L / 2, y0 + W, 23.0 + T), False))
    # flat in the bowl, centred fore-aft on the cup, as low as it fits (its top must stay 1 under the PCB: z 25)
    yc = 1.0
    z0 = next((z for z in np.arange(r.WALL + GAP, 25.0 - T + 0.01, 0.25)
               if box_fits(L, yc - W / 2, yc + W / 2, z, z + T)), 25.0 - T)
    out.append(("flat, in the bowl (lowest fit)", (-L / 2, yc - W / 2, z0, L / 2, yc + W / 2, z0 + T), True))
    # standing on its long edge across (L along x), in the bowl's upper part and the body: lowest z where it fits
    return out


def fits(b, in_bowl):
    x0, y0, z0, x1, y1, z1 = b
    if not in_bowl and y1 > 24.6 - GAP:
        return False
    return box_fits(x1 - x0, y0, y1, z0, z1)


def main():
    rows = []
    cast_full = cast_part(CAST_TOP)
    for name, (L, W, T, m) in CELLS.items():
        for label, b, in_bowl in positions(L, W, T):
            ok = fits(b, in_bowl)
            if in_bowl:
                hole = (b[0], b[3], b[1], b[4], b[2], b[5])
                cast = cast_part(CAST_TOP, hole)           # balls and epoxy round and under the cell
                segs = [] if b[5] > CAST_TOP else segments_on_cast()
            else:
                cast, segs = cast_full, segments_on_cast()
            res = evaluate(b, m, cast, segs)
            rows.append((name, label, b, ok, cast["m"], len(segs), *res))
    print(f"board {M_BOARD:.0f} g; cast 304 balls in epoxy at {RHO_CAST} g/cm3 up to z {CAST_TOP} (or 1 mm under a battery in the bowl);"
          f" trim layer 6 x 5 g unless the battery is in the bowl; centre of mass trimmed to x 0")
    print(f"{'cell':30s} {'position':34s} {'z':>9s} {'fits':5s} {'cast g':>6s} {'segs':>4s} {'total':>6s} {'G z':>6s} {'margin':>6s} {'period':>6s} {'k mNm/deg':>9s} {'fwd':>5s} {'back':>5s}")
    for name, label, b, ok, mc, ns, M, G, margin, T, k, fwd, back in rows:
        print(f"{name:30s} {label:34s} {b[2]:4.1f}-{b[5]:4.1f} {'yes' if ok else 'NO':5s} {mc:6.0f} {ns:4d} {M:6.0f} {G[2]:6.1f} {margin:6.1f} {T:6.2f} {k:9.2f} {fwd:5.1f} {back:5.1f}")


if __name__ == "__main__":
    main()
