#!/usr/bin/env python3
"""The pebble's current keeper round (RND; the board keeper: ribs + fork, smooth.py's KEEPER) into to-print/:
  pebble-E-shell.stl             = out-smooth/pebble/shell.stl (ribs included)
  pebble-E-fork.stl              = out-smooth/pebble/fork-print.stl (flat on its back, pads up, +PAD_OVER to sand)
  pebble-E-shell-relief-{N1,W}   = round C's relief shells + out-smooth/pebble/ribs.stl
The relief only moves the outer skin, so the C relief shells' cavity is the smooth shell's: the same rib mesh is added
to them (manifold3d). Checked per shell: the ribs add one piece each (all in the cavity: none comes out through the
skin), by the same volume as on the smooth shell, and the result is one closed piece.
Round E also has a USB-C slot in the back wall where rounds A..D had the rim notch (smooth.py's PEBBLE["USB_SLOT"]): on
the relief shells the notch's foot (below the slot) is filled from the new smooth shell, then the slot is cut. Both
are below / beside where the relief starts (z 5, faded near the notch); checked: the back wall's foot round the slot
is the smooth shell's.
Round E's glass pocket stops (out-smooth/pebble/stops.stl: wedge, rails, bottom corners on the front wall's inner
face) are added like the ribs; checked: they add the same volume as on the smooth shell (so none of them comes out
through the relief skin).
    ~/.venvs/cad/bin/python cad/desk/keeper_to_print.py      (after smooth.py pebble)
"""
import pathlib, shutil
import numpy as np, pyvista as pv, manifold3d as m3

HERE = pathlib.Path(__file__).parent
OUT, TP = HERE / "out-smooth" / "pebble", HERE / "to-print"
RELIEFS = ("N1", "W")
RND = "E"                              # D: one prong, 3 ribs (printed 2026-11-26); E: frame fork, 4 wide ribs


def load(path):
    me = pv.read(str(path)).clean()
    assert me.n_open_edges == 0, f"{path.name}: {me.n_open_edges} open edges"
    M = m3.Manifold(m3.Mesh64(vert_properties=np.ascontiguousarray(me.points, np.float64),
                              tri_verts=np.ascontiguousarray(me.faces.reshape(-1, 4)[:, 1:], np.uint64)))
    assert M.status() == m3.Error.NoError and not M.is_empty(), f"{path.name}: {M.status()}"
    return M


def save(M, path):
    me = M.to_mesh64()
    V, F = np.asarray(me.vert_properties)[:, :3], np.asarray(me.tri_verts, np.int64)
    pd = pv.PolyData(V, np.c_[np.full(len(F), 3), F].ravel())
    assert pd.clean().n_open_edges == 0, f"{path.name}: open edges"
    pd.save(str(path), binary=True)
    print(f"{path.relative_to(HERE)}  {len(F)} triangles, {M.volume() / 1000:.2f} cm3")


USB_SLOT = (11.0, 5.0, 2.5)            # smooth.py's PEBBLE["USB_SLOT"]: width, height, lower edge above the rim
NOTCH_W = 5.6                          # the rim notch of rounds A..D


def slot_cutter(grow=0.0):
    """the slot as a prism along y through the back wall (the polygon inscribed: never wider than the model's)"""
    w, h, z0 = USB_SLOT; r, a = h / 2 + grow, (w - h) / 2
    t = np.linspace(-np.pi / 2, np.pi / 2, 49)
    P = np.r_[np.c_[a + r * np.cos(t), r * np.sin(t)], np.c_[-a - r * np.cos(t), -r * np.sin(t)]]      # (x, z - zc), ccw
    return m3.Manifold.extrude(m3.CrossSection([P.tolist()]), 20.0).transform([[1, 0, 0, 0], [0, 0, 1, 45.0], [0, 1, 0, z0 + h / 2]])


def box(x0, x1, y0, y1, z0, z1):
    return m3.Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def with_slot(src, smooth, tag):
    """src (a round C relief shell, with the notch) -> the notch's foot filled from the smooth shell, the slot cut"""
    w, h, z0 = USB_SLOT
    check_in = (smooth ^ slot_cutter()).volume()
    assert check_in < 0.05, f"the smooth shell has {check_in:.3f} mm3 inside the slot: USB_SLOT differs from smooth.py's?"
    foot = smooth ^ box(-NOTCH_W / 2 - 0.3, NOTCH_W / 2 + 0.3, 45.0, 65.0, -0.1, z0 + 0.2)
    U = (src + foot) - slot_cutter()
    B = box(-w / 2 - 3.0, w / 2 + 3.0, 45.0, 65.0, -0.1, 4.4)                # the back wall's foot round the slot, below the relief
    d = ((U ^ B) - (smooth ^ B)).volume() + ((smooth ^ B) - (U ^ B)).volume()
    assert d < 0.05, f"{tag}: the back wall's foot differs from the smooth shell's by {d:.3f} mm3"
    left = (U ^ slot_cutter(-0.05)).volume()
    assert left < 1e-6, f"{tag}: {left:.4f} mm3 left inside the slot"
    print(f"{tag}: notch foot filled ({foot.volume():.1f} mm3), slot cut; the wall's foot differs from the smooth shell's by {d:.4f} mm3")
    return U


if __name__ == "__main__":
    shutil.copyfile(OUT / "shell.stl", TP / f"pebble-{RND}-shell.stl")
    shutil.copyfile(OUT / "fork-print.stl", TP / f"pebble-{RND}-fork.stl")
    print(f"to-print/pebble-{RND}-shell.stl, to-print/pebble-{RND}-fork.stl copied")
    ribs = load(OUT / "ribs.stl")
    N_RIBS = len(ribs.decompose())
    smooth_c = load(TP / "pebble-C-shell.stl")                 # the shell the reliefs were made from
    ref = (ribs - smooth_c).volume()
    stops = load(OUT / "stops.stl")
    stops_ref = (stops - smooth_c).volume()
    for tag in RELIEFS:
        src = load(TP / f"pebble-C-shell-relief-{tag}.stl")
        added = ribs - src
        n, v = len(added.decompose()), added.volume()
        assert n == N_RIBS, f"{tag}: the ribs add {n} pieces, not {N_RIBS} (through the skin?)"
        assert abs(v - ref) < 0.5, f"{tag}: the ribs add {v:.1f} mm3, on the smooth shell {ref:.1f}: another cavity?"
        U = with_slot(src, load(OUT / "shell.stl"), tag) + ribs
        sv = (stops - src).volume()
        assert abs(sv - stops_ref) < 0.5, f"{tag}: the pocket stops add {sv:.1f} mm3, on the smooth shell {stops_ref:.1f}: through the skin?"
        U = U + stops
        print(f"{tag}: pocket stops add {sv:.1f} mm3 (smooth shell: {stops_ref:.1f})")
        assert U.status() == m3.Error.NoError and len(U.decompose()) == 1, f"{tag}: {U.status()}, {len(U.decompose())} pieces"
        print(f"{tag}: ribs add {v:.1f} mm3 in {n} pieces (smooth shell: {ref:.1f})")
        save(U, TP / f"pebble-{RND}-shell-relief-{tag}.stl")
