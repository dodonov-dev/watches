"""True-scale side profiles of the tilted-oval concepts (track A2) with the hardware stack, rough centre of mass
and tipping angles. 2D sketch only, for judging proportions before CAD.
    ~/.venvs/cad/bin/python cad/desk/concept/oval_tilt_profiles.py [out.png]
"""
import sys, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

T15 = math.radians(15)
# stack in the tilt frame (s along the face from the rim, t into the body from the outer face): tilt15 report
STACK_S = (12.0, 95.0)      # adapter bottom .. glass top
STACK_T = (3.0, 26.0)       # front inner face .. battery back + clearance
SHELL_G, STACK_G = 65.0, 85.0
STACK_SC = (17.7 + 85.7) / 2  # battery / board centre along s


def frame(s, t, lean=T15, y0=0.0):
    """tilt frame -> side view (y back, z up); the face leans back by `lean` from the point (y0, 0)."""
    return (y0 + s * math.sin(lean) + t * math.cos(lean), s * math.cos(lean) - t * math.sin(lean))


def rounded(pts, r, n=8):
    """round every corner of a polygon by r (simple fillet by arc sampling)."""
    pts = np.asarray(pts, float); out = []
    for i in range(len(pts)):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
        a, b = p0 - p1, p2 - p1
        la, lb = np.linalg.norm(a), np.linalg.norm(b)
        if la < 1e-9 or lb < 1e-9:
            continue
        a, b = a / la, b / lb
        ang = math.acos(max(-1, min(1, a @ b)))
        if ang > math.pi - 1e-3 or r <= 0:
            out.append(p1); continue
        d = min(r / math.tan(ang / 2), la / 2, lb / 2)
        rr = d * math.tan(ang / 2)
        c = p1 + (a + b) / np.linalg.norm(a + b) * rr / math.sin(ang / 2)
        q0, q1 = p1 + a * d, p1 + b * d
        t0, t1 = math.atan2(*(q0 - c)[::-1]), math.atan2(*(q1 - c)[::-1])
        dt = (t1 - t0 + math.pi) % (2 * math.pi) - math.pi
        out += [c + rr * np.array([math.cos(t0 + dt * k / n), math.sin(t0 + dt * k / n)]) for k in range(n + 1)]
    return np.array(out)


def centroid(poly):
    x, y = poly[:, 0], poly[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cr = x * y1 - x1 * y
    a = cr.sum() / 2
    return np.array([((x + x1) * cr).sum() / (6 * a), ((y + y1) * cr).sum() / (6 * a)])


def concepts():
    H = 108.0
    c = {}
    # (a) oval wedge: front 15 deg, back vertical
    D = 52.0
    c["a  oval wedge\n52 deep at desk, back vertical"] = dict(
        outline=rounded([(0, 0), (D, 0), (D, H), (H * math.tan(T15), H)], 6), lean=T15, y0=0.0, foot=(0.5, D - 0.5))
    # (b) leaning bottle: the oval 36 deep leaning 15 deg as a whole, foot cut level
    L, Dp = 110.0, 36.0
    pts = [frame(0, 0), frame(0, Dp), frame(L, Dp), frame(L, 0)]
    # cut level at z=0: the lower back corner sits below the desk; clip by extending
    p = np.array(pts)
    zb = p[1, 1]                       # back-bottom is below 0 (negative)
    back_dir = p[2] - p[1]; k = -zb / back_dir[1]
    pb = p[1] + back_dir * k
    c["b  leaning bottle\noval 36 deep, whole body 15 deg"] = dict(
        outline=rounded([p[0], pb, p[2], p[3]], 6), lean=T15, y0=0.0, foot=(0.5, pb[0] - 0.5))
    # (c) sliced oval: upright column 52 deep, front sliced by a 15 deg plane: same side profile as (a); the
    # difference is in plan (flat facet + curved sides vs. shrinking oval sections) -> shown by the plan inset
    # (d) leaning pebble: front 15 deg, back one large curve to the desk
    c["d  leaning pebble\nback rounds over, 60 at desk"] = dict(
        outline=rounded([(0, 0), (60, 0), (63, 45), (57, 88), (42, 106), (29, 108)], 16), lean=T15, y0=0.0,
        foot=(4.0, 52.0))
    return c


def main(out):
    cs = concepts()
    fig, axs = plt.subplots(1, len(cs), figsize=(5 * len(cs), 6.5))
    for ax, (name, cfg) in zip(axs, cs.items()):
        poly = cfg["outline"]
        ax.add_patch(Polygon(poly, closed=True, fc="#efe9df", ec="#555", lw=1.5))
        st = np.array([frame(s, t, cfg["lean"], cfg["y0"]) for s, t in
                       [(STACK_S[0], STACK_T[0]), (STACK_S[0], STACK_T[1]), (STACK_S[1], STACK_T[1]), (STACK_S[1], STACK_T[0])]])
        ax.add_patch(Polygon(st, closed=True, fc="#9ab", ec="#456", alpha=0.6))
        rod = np.array([frame(s, 0.8, cfg["lean"], cfg["y0"]) for s in (24.6, 91.45)])
        ax.plot(rod[:, 0], rod[:, 1], color="#27c", lw=4)
        # rough mass: shell as its side-profile centroid, stack at its centre
        sc = centroid(poly)
        stc = np.array(frame(STACK_SC, 14.0, cfg["lean"], cfg["y0"]))
        com = (sc * SHELL_G + stc * STACK_G) / (SHELL_G + STACK_G)
        f0, f1 = cfg["foot"]
        back = math.degrees(math.atan2(f1 - com[0], com[1]))
        fwd = math.degrees(math.atan2(com[0] - f0, com[1]))
        ax.plot(*com, "o", color="#c33"); ax.plot([f0, f1], [-1, -1], color="#c33", lw=3)
        inside = all(Polygon(poly).contains_point(p) for p in st)
        ax.set_title(f"{name}\nCoM {com[0]:.0f} back, {com[1]:.0f} up; tips at ~{back:.0f} deg back / {fwd:.0f} fwd"
                     f"\nstack {'fits' if inside else 'DOES NOT FIT'} (no wall allowance)", fontsize=9)
        ax.axhline(0, color="#999", lw=0.8)
        ax.set_xlim(-10, 75); ax.set_ylim(-5, 120); ax.set_aspect("equal"); ax.grid(alpha=0.25)
        ax.set_xlabel("depth, mm (front at left)")
    fig.suptitle("Tilted oval concepts: true-scale side profiles (left side view). Blue: display+board+battery stack; "
                 "blue line: rod; red: rough centre of mass and foot. (c) sliced oval has the profile of (a).", fontsize=10)
    fig.tight_layout(); fig.savefig(out, dpi=110)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "cad/desk/concept/out-ovaltilt/profiles.png")
