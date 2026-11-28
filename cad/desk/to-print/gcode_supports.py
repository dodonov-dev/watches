"""What supports a sliced plate really carries, per object: read it BEFORE the plate goes to the printer.

Plate _20 (2026-11-28) spaghettied at z ~80: the roly-poly body's auto tree supports were one free-standing trunk
100 mm up from the plate to a patch inside the crown, with twigs 3..5 mm across from z 50 to the slots' top ends.
The slicer reported "Success", no warnings. Also look where the trunks stand (a tree outside a shell reaches in
through its openings and marks them).

   python gcode_supports.py plate_1.gcode | plate.gcode.3mf      (slice: flatpak run --command=bambu-studio
                                                                  com.bambulab.BambuStudio --slice 1 --outputdir DIR plate.3mf)
Per object: the support's length and height range, where it touches the model (interface layers), and its islands in
height bands (count, the smallest one's bounding box's short side). THIN marks an island under MIN_ACROSS mm across standing above FREE_Z:
a twig the nozzle can knock over. Exit code 1 if any object has one."""
import sys, re, math, io, zipfile, collections
import numpy as np
from scipy import ndimage as ndi

MIN_ACROSS, FREE_Z, CELL, BAND, SLAB = 6.0, 20.0, 0.4, 10.0, 0.5
src = sys.argv[1]
f = io.TextIOWrapper(zipfile.ZipFile(src).open("Metadata/plate_1.gcode"), errors="replace") if src.endswith(".3mf") else open(src, errors="replace")
num = re.compile(r'([XYEIJ])(-?\d*\.?\d+)')
x = y = z = 0.0
obj = feat = None
names, sup, total = {}, collections.defaultdict(list), collections.Counter()      # sup[(obj, z)] -> (x0, y0, x1, y1, interface)
for line in f:
    if line[0] == ';':
        if line.startswith("; Z_HEIGHT:"): z = float(line.split(":")[1])
        elif line.startswith("; FEATURE:"): feat = line.split(":", 1)[1].strip()
        elif line.startswith("; start printing object"): obj = int(line.rsplit(" ", 1)[1])
        elif line.startswith("; stop printing object"): obj = None
        elif line.startswith("; model label id:"): ids = [int(v) for v in line.split(":")[1].split(",")]
        elif line.startswith("; object max height:"): names = dict(zip(ids, (float(v) for v in line.split(":")[1].split(","))))
        continue
    if line[:3] not in ("G1 ", "G2 ", "G3 "): continue
    d = dict((k, float(v)) for k, v in num.findall(line.split(";")[0][2:]))
    nx, ny = d.get("X", x), d.get("Y", y)
    if d.get("E", 0.0) > 0 and obj is not None and feat and (nx != x or ny != y):
        total[obj] += 1
        if feat.startswith("Support"):
            pts = [(x, y), (nx, ny)]
            if line[1] in "23" and "I" in d:                 # an arc: as chords
                cx, cy = x + d["I"], y + d.get("J", 0.0)
                a0, a1, r = math.atan2(y - cy, x - cx), math.atan2(ny - cy, nx - cx), math.hypot(x - cx, y - cy)
                a1 += (-2 * math.pi if a1 >= a0 else 0.0) if line[1] == "2" else (2 * math.pi if a1 <= a0 else 0.0)
                k = max(2, int(abs(a1 - a0) * r / 0.3) + 1)
                pts = [(x, y)] + [(cx + r * math.cos(a0 + (a1 - a0) * i / k), cy + r * math.sin(a0 + (a1 - a0) * i / k)) for i in range(1, k)] + [(nx, ny)]
            sup[(obj, z)] += [(*pa, *pb, feat != "Support") for pa, pb in zip(pts, pts[1:])]
    x, y = nx, ny

bad = False
for o in sorted(total):
    zs = sorted(zz for oo, zz in sup if oo == o)
    print(f"\nobject {o} (height {names.get(o, 0):g}):", end=" ")
    if not zs:
        print("no support"); continue
    A = {zz: np.array(sup[(o, zz)]) for zz in zs}
    length = sum(float(np.hypot(a[:, 2] - a[:, 0], a[:, 3] - a[:, 1]).sum()) for a in A.values())
    touch = [zz for zz in zs if A[zz][:, 4].any()]
    runs = []
    for zz in touch:                                         # interface layers, grouped
        if runs and zz - runs[-1][1] < 0.5: runs[-1][1] = zz
        else: runs.append([zz, zz])
    print(f"support {length / 1000:.1f} m, z {zs[0]:.2f}..{zs[-1]:.2f}; touches the model at z " + (", ".join(f"{a:.1f}..{b:.1f}" for a, b in runs) or "- (no interface)"))
    allp = np.vstack(list(A.values()))
    x0, y0 = allp[:, [0, 2]].min() - 2, allp[:, [1, 3]].min() - 2
    n = (int((allp[:, [0, 2]].max() + 2 - x0) / CELL) + 2, int((allp[:, [1, 3]].max() + 2 - y0) / CELL) + 2)
    for b0 in np.arange(0.0, zs[-1] + 1e-6, BAND):
        rows = []
        for zz in np.arange(max(b0, zs[0]), min(b0 + BAND, zs[-1]) - SLAB + 1e-6, 1.0):
            g = np.zeros(n, bool)                            # a SLAB of layers together: one layer may carry only part of an outline
            for xa, ya, xb, yb, _ in (r for v in zs if zz <= v < zz + SLAB for r in A[v]):
                t = np.linspace(0, 1, max(2, int(math.hypot(xb - xa, yb - ya) / (CELL / 2)) + 1))
                g[((xa + (xb - xa) * t - x0) / CELL).astype(int), ((ya + (yb - ya) * t - y0) / CELL).astype(int)] = True
            lab, k = ndi.label(ndi.binary_fill_holes(ndi.binary_dilation(g)))
            for c in ndi.find_objects(lab):
                rows.append((min(c[0].stop - c[0].start, c[1].stop - c[1].start) * CELL - 2 * CELL, k, float(zz)))
        if rows:
            w, k, zz = min(rows)
            thin = w < MIN_ACROSS and zz > FREE_Z
            bad |= thin
            print(f"   z {b0:5.0f}..{b0 + BAND:<5.0f} up to {max(r[1] for r in rows)} island(s), the thinnest {max(w, 0):4.1f} across at z {zz:.1f}" + ("   THIN" if thin else ""))
sys.exit(1 if bad else 0)
