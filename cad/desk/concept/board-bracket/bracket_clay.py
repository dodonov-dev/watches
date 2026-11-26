"""Concept clay: the LCD board held by a printed bracket on its 4 M2 nuts, magnets in 4 ears clicking onto 4 bosses
grown from the pebble's front wall. Real pebble C shell + dummies; bracket / bosses / magnets are concept boxes.
Body frame (x, t, s): t into the housing from the front face, s up the face; world y = t c + s s_, z = -t s_ + s c."""
import sys, math, pathlib
import numpy as np
import pyvista as pv

D = pathlib.Path("/home/andrey/_PROJECTS/watches/cad/desk/out-smooth/pebble")
OUT = pathlib.Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
A = math.radians(15); C, S = math.cos(A), math.sin(A)
M = np.eye(4); M[1, 1:3] = (C, S); M[2, 1:3] = (-S, C)          # body (x, t, s) -> world (x, y, z)
TN = np.array([0, C, -S]); SN = np.array([0, S, C])               # body t / s axes in world

def box(x0, x1, t0, t1, s0, s1):
    return pv.Box((x0, x1, t0, t1, s0, s1)).triangulate().transform(M, inplace=False)

def cyl_t(x, s, t0, t1, r):                                       # cylinder along t
    return pv.Cylinder(center=((x, (t0 + t1) / 2, s)), direction=(0, 1, 0), radius=r, height=t1 - t0,
                       resolution=40).triangulate().transform(M, inplace=False)

# ---- numbers (mm) ------------------------------------------------------------------------------------------
PCB_X, PCB_T0, PCB_T1, STACK_T1 = 16.675, 7.79, 9.39, 12.89       # PCB 1.6; nuts / parts to 12.89 (dummy)
PCB_S0, PCB_S1 = 16.8, 95.65
NUT_X, NUT_S = 27.35 / 2, (PCB_S0 + 3.0, PCB_S0 + 3.0 + 72.75)
PL_T = 1.4                                                        # bracket plate
EAR_SC = (NUT_S[0], NUT_S[1] - 3.5)                               # top pair lowered: the cavity narrows under the roll
PL = (-16.2, 16.2, STACK_T1, STACK_T1 + PL_T, PCB_S0 + 0.3, PCB_S1 - 0.3)
EAR_X = (17.8, 21.6); EAR_S = 8.0; EAR_T1 = STACK_T1 + 3.0        # ear's magnet pad (thick part)
MAG_R, MAG_H = 2.5, 2.0                                           # 5 x 2 discs
BOSS_X = EAR_X; BOSS_T1 = STACK_T1 - 0.2                          # 0.2 short: magnets squeeze the 0.5 foam gasket
BAT = (-17.5, 17.5, PL[3] + 0.1, PL[3] + 10.1, 17.8, 85.8)

def assembly(pull=0.0):
    """Board-side parts, pulled back along t by `pull` (0 = seated)."""
    off = TN * pull
    parts = {}
    for n in ("glass", "board", "rod-l", "rod-r", "adapter", "plug-j5", "plug-i2c", "button-boot", "button-rst", "button-slide"):
        f = D / f"dummy-{n}.stl"
        if f.exists():
            parts[n] = pv.read(f).translate(off, inplace=False)
    br = [box(*PL)]
    for sx in (-1, 1):
        for s in EAR_SC:
            s0, s1 = s - EAR_S / 2, s + EAR_S / 2
            br.append(box(*sorted((sx * 15.5, sx * EAR_X[0])), PL[2], PL[3], s0, s1))          # thin arm beside the battery
            br.append(box(*sorted((sx * EAR_X[0], sx * EAR_X[1])), PL[2], EAR_T1, s0, s1))     # magnet pad
            parts.setdefault("magnet", []).append(cyl_t(sx * sum(EAR_X) / 2, s, STACK_T1 - 0.01, STACK_T1 + MAG_H, MAG_R))
    # battery cradle lips (low side rails on the plate) instead of tape
    for sx in (-1, 1):
        br.append(box(*sorted((sx * 17.6, sx * 18.6)), PL[3], PL[3] + 3.0, 30, 75))
    parts["bracket"] = pv.merge(br)
    parts["battery"] = box(*BAT)
    parts["magnet"] = pv.merge(parts["magnet"])
    for k in parts:
        if k not in ("bracket", "battery", "magnet") or pull == 0:
            continue
    for k in ("bracket", "battery", "magnet"):
        parts[k] = parts[k].translate(off, inplace=False)
    return parts

def shell_parts():
    sh = pv.read(D / "shell.stl")
    bosses, mags = [], []
    for sx in (-1, 1):
        for s in EAR_SC:
            bosses.append(box(*sorted((sx * BOSS_X[0], sx * BOSS_X[1])), 5.0, BOSS_T1, s - EAR_S / 2, s + EAR_S / 2))
            mags.append(cyl_t(sx * sum(BOSS_X) / 2, s, BOSS_T1 - MAG_H, BOSS_T1 + 0.01, MAG_R))
    return sh, pv.merge(bosses), pv.merge(mags)

COL = {"shell": "#e2d6c0", "boss": "#d9c7a6", "glass": "#4f7da8", "board": "#2f6b3a", "rod-l": "#eef3ec", "rod-r": "#eef3ec",
       "adapter": "#7a4f86", "bracket": "#e8893a", "battery": "#b9b9b9", "magnet": "#c33c3c", "bmag": "#c33c3c",
       "plug": "#d9b43a", "button": "#b04040"}

def col(n):
    for k in ("plug", "button"):
        if n.startswith(k):
            return COL[k]
    return COL.get(n, "#999999")

def scene(pl, parts, shell, bosses, bmags, clip_shell=None, clip_all=None, labels=()):
    def cut(m, cl):
        if cl is None:
            return m
        return m.clip(normal=cl[0], origin=cl[1], invert=cl[2] if len(cl) > 2 else True)
    sh = cut(cut(shell, clip_shell), clip_all)
    pl.add_mesh(sh, color=COL["shell"], smooth_shading=False, ambient=0.3, diffuse=0.75, specular=0.05)
    for m, k in ((bosses, "boss"), (bmags, "bmag")):
        mm = cut(m, clip_all)
        if mm.n_points:
            pl.add_mesh(mm, color=COL[k], ambient=0.3, diffuse=0.75)
    for n, m in parts.items():
        mm = cut(m, clip_all)
        if mm.n_points:
            pl.add_mesh(mm, color=col(n), ambient=0.3, diffuse=0.75, specular=0.1,
                        opacity=0.55 if n == "battery" else 1.0)
    for txt, p in labels:
        pl.add_point_labels([p], [txt], font_size=14, point_size=1, shape_opacity=0.75, always_visible=True,
                            text_color="black", shape_color="white", margin=3)

def W(x, t, s):
    return (M[:3, :3] @ np.array([x, t, s])).tolist()

def shoot(fname, panels, size=(820, 900)):
    pl = pv.Plotter(off_screen=True, window_size=(size[0] * len(panels), size[1]), shape=(1, len(panels)))
    for i, p in enumerate(panels):
        pl.subplot(0, i)
        pl.set_background("#d8d5cf", top="#f3f1ed")
        scene(pl, *p["scene"], **p.get("kw", {}))
        pl.camera_position = p["cam"]
        if p.get("par"):
            pl.camera.parallel_projection = True
            pl.camera.parallel_scale = p["par"]
        else:
            pl.camera.view_angle = p.get("va", 22)
        pl.add_text(p["title"], font_size=11, color="black")
        pl.reset_camera_clipping_range()
    pl.enable_anti_aliasing("ssaa")
    pl.screenshot(str(OUT / fname)); pl.close(); print(OUT / fname)

shell, bosses, bmags = shell_parts()
seated, pulled = assembly(0.0), assembly(6.0)
ctr = W(0, 12, 56)
back_clip = (tuple(TN), W(0, 17.5, 0), True)        # keep the front part (t < 17.5): look in from behind
hero = [ctr[0] + 120, ctr[1] + 260, ctr[2] + 120]
hero2 = [ctr[0] - 140, ctr[1] + 240, ctr[2] + 40]

# 1. cutaway from behind: seated, and pulled back 6 (bosses + magnets visible)
labels_p = [("boss + magnet (shell)", W(19.7, 8, EAR_SC[0] - 4)), ("ear + magnet (bracket)", W(19.7, 20, EAR_SC[1] + 4)),
            ("bracket on the 4 M2 nuts", W(0, 21, 30)), ("battery in cradle", W(0, 28, 60))]
shoot("bracket-cutaway.png", [
    dict(title="seated (shell cut at t 17.5, seen from behind)", scene=(seated, shell, bosses, bmags),
         kw=dict(clip_shell=back_clip), cam=[hero, ctr, list(SN)]),
    dict(title="pulled back 6 mm: bosses and magnets", scene=(pulled, shell, bosses, bmags),
         kw=dict(clip_shell=back_clip, labels=labels_p), cam=[hero, ctr, list(SN)]),
])

# 2. sections: through the bottom ear row (plane s = const), and through the ears (plane x = 19.7)
s_cut = EAR_SC[1]
sec_s = (tuple(SN), W(0, 0, s_cut), True)            # keep below the plane, look down the s axis
cs = W(0, 15, s_cut)
sec_x = ((1, 0, 0), (19.7, 0, 0), True)               # keep x > 19.7, look from -x? keep x<19.7 seen from +x
cx = W(19.7, 15, 56)
shoot("bracket-sections.png", [
    dict(title=f"section across the face at the top ear row (s {s_cut:.1f}), seen from above",
         scene=(seated, shell, bosses, bmags), kw=dict(clip_all=sec_s),
         cam=[[cs[i] + SN[i] * 300 for i in range(3)], cs, list(TN * -1)], par=34),
    dict(title="section x 19.7 through the ears, seen from the right",
         scene=(seated, shell, bosses, bmags), kw=dict(clip_all=((1, 0, 0), (19.7, 0, 0), True)),
         cam=[[cx[0] + 300, cx[1], cx[2]], cx, [0, 0, 1]], par=60),
], size=(820, 820))

# 3. the bracket alone on the board, from behind
bonly = {k: v for k, v in seated.items() if k not in ("battery",)}
cb = W(0, 12, 56)
pl = pv.Plotter(off_screen=True, window_size=(820, 900))
pl.set_background("#d8d5cf", top="#f3f1ed")
for n, m in bonly.items():
    pl.add_mesh(m, color=col(n), ambient=0.3, diffuse=0.75)
for n in ("battery",):
    pl.add_mesh(seated[n].extract_feature_edges(), color="#555555", line_width=1)
pl.add_text("board + bracket from behind (battery outline)", font_size=11, color="black")
pl.camera_position = [[cb[0] + 60, cb[1] + 200, cb[2] + 60], cb, list(SN)]
pl.camera.view_angle = 25
pl.enable_anti_aliasing("ssaa"); pl.screenshot(str(OUT / "bracket-alone.png")); pl.close(); print(OUT / "bracket-alone.png")
