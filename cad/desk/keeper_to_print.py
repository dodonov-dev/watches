#!/usr/bin/env python3
"""Round D of the pebble (the board keeper: ribs + fork, smooth.py's KEEPER) into to-print/:
  pebble-D-shell.stl             = out-smooth/pebble/shell.stl (ribs included)
  pebble-D-fork.stl              = out-smooth/pebble/fork-print.stl (flat on its back, pads up, +PAD_OVER to sand)
  pebble-D-shell-relief-{N1,W}   = round C's relief shells + out-smooth/pebble/ribs.stl
The relief only moves the outer skin, so the C relief shells' cavity is the smooth shell's: the same rib mesh is added
to them (manifold3d). Checked per shell: the ribs add one piece each (all in the cavity: none comes out through the
skin), by the same volume as on the smooth shell, and the result is one closed piece.
    ~/.venvs/cad/bin/python cad/desk/keeper_to_print.py      (after smooth.py pebble)
"""
import pathlib, shutil
import numpy as np, pyvista as pv, manifold3d as m3

HERE = pathlib.Path(__file__).parent
OUT, TP = HERE / "out-smooth" / "pebble", HERE / "to-print"
RELIEFS = ("N1", "W")


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


if __name__ == "__main__":
    shutil.copyfile(OUT / "shell.stl", TP / "pebble-D-shell.stl")
    shutil.copyfile(OUT / "fork-print.stl", TP / "pebble-D-fork.stl")
    print("to-print/pebble-D-shell.stl, to-print/pebble-D-fork.stl copied")
    ribs = load(OUT / "ribs.stl")
    N_RIBS = len(ribs.decompose())
    smooth_c = load(TP / "pebble-C-shell.stl")                 # the shell the reliefs were made from
    ref = (ribs - smooth_c).volume()
    for tag in RELIEFS:
        src = load(TP / f"pebble-C-shell-relief-{tag}.stl")
        added = ribs - src
        n, v = len(added.decompose()), added.volume()
        assert n == N_RIBS, f"{tag}: the ribs add {n} pieces, not {N_RIBS} (through the skin?)"
        assert abs(v - ref) < 0.5, f"{tag}: the ribs add {v:.1f} mm3, on the smooth shell {ref:.1f}: another cavity?"
        U = src + ribs
        assert U.status() == m3.Error.NoError and len(U.decompose()) == 1, f"{tag}: {U.status()}, {len(U.decompose())} pieces"
        print(f"{tag}: ribs add {v:.1f} mm3 in {n} pieces (smooth shell: {ref:.1f})")
        save(U, TP / f"pebble-D-shell-relief-{tag}.stl")
