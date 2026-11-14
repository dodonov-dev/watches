#!/usr/bin/env python3
"""Headless PNG preview of a part (STL / STEP / 3MF / OBJ) for agents; run with ~/.venvs/cad/bin/python.

    cad_preview.py part.step out.png [--view iso|top|front|right|all] [--size 1000x750]
    cad_preview.py --smoke OUTDIR        # build123d test part -> STEP/STL/3MF + PNG (setup check)

Offscreen VTK: GLX when $DISPLAY is set, else EGL (NVIDIA), else OSMesa (apt libosmesa6).
"""
import argparse
import sys
from pathlib import Path

import pyvista as pv

VIEWS = {"iso": "view_isometric", "top": "view_xy", "front": "view_xz", "right": "view_yz"}


def load(path: Path) -> pv.PolyData:
    if path.suffix.lower() in (".step", ".stp"):
        import tempfile
        from build123d import export_stl, import_step
        shape = import_step(path)
        with tempfile.TemporaryDirectory() as d:
            stl = Path(d) / "part.stl"
            export_stl(shape, stl, tolerance=0.01, angular_tolerance=0.1)
            return pv.read(stl)
    if path.suffix.lower() == ".3mf":
        import trimesh
        m = trimesh.load(path, force="mesh")
        return pv.wrap(m)
    return pv.read(path)


def render(mesh: pv.PolyData, out: Path, view: str, size: tuple[int, int]) -> None:
    views = list(VIEWS) if view == "all" else [view]
    pl = pv.Plotter(off_screen=True, window_size=size, shape=(1, len(views)) if len(views) > 1 else (1, 1))
    for i, v in enumerate(views):
        pl.subplot(0, i)
        pl.add_mesh(mesh, color="tan", smooth_shading=True, split_sharp_edges=True)
        pl.add_mesh(mesh.extract_feature_edges(30), color="black", line_width=1)
        pl.add_text(v, font_size=10)
        getattr(pl, VIEWS[v])()
        pl.show_axes()
    b = mesh.bounds
    print(f"{out}: bbox {b[1]-b[0]:.2f} x {b[3]-b[2]:.2f} x {b[5]-b[4]:.2f} mm, {mesh.n_cells} tris")
    pl.screenshot(out)


def smoke(outdir: Path) -> None:
    from build123d import Axis, BuildPart, Box, Hole, Locations, Mesher, export_step, export_stl, fillet
    outdir.mkdir(parents=True, exist_ok=True)
    with BuildPart() as p:
        Box(40, 20, 10)
        fillet(p.edges().filter_by(Axis.Z), radius=3)
        with Locations(p.faces().sort_by(Axis.Z)[-1]):
            Hole(4)
    export_step(p.part, outdir / "smoke.step")
    export_stl(p.part, outdir / "smoke.stl")
    m = Mesher()
    m.add_shape(p.part)
    m.write(str(outdir / "smoke.3mf"))
    print(f"volume {p.part.volume:.1f} mm3 (expect ~7420)")
    render(load(outdir / "smoke.step"), outdir / "smoke.png", "iso", (1000, 750))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?")
    ap.add_argument("output", nargs="?")
    ap.add_argument("--view", default="iso", choices=[*VIEWS, "all"])
    ap.add_argument("--size", default="1000x750")
    ap.add_argument("--smoke", metavar="OUTDIR")
    a = ap.parse_args()
    if a.smoke:
        smoke(Path(a.smoke))
        return 0
    if not (a.input and a.output):
        ap.error("input and output required")
    w, h = (int(x) for x in a.size.split("x"))
    if a.view == "all":
        w *= 4
    render(load(Path(a.input)), Path(a.output), a.view, (w, h))
    return 0


if __name__ == "__main__":
    sys.exit(main())
