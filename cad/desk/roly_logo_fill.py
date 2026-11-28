#!/usr/bin/env python3
"""The logo's stencil pocket as solids, for roly_keeper.py to close it (user, 2026-11-28: the body will be black, no light
through it, and the pocket shows from outside). From rolypoly.py's own surfaces and pocket cutter, no shell rebuild:

  out-rolypoly/keeper/logo-pocket.stl  the pocket as round 8 cut it (for the check)
  out-rolypoly/keeper/logo-fill.stl    its filler: the cutter grown GROW all round, from FRONT behind the outer surface (inside
                                       the 1.0 skin) to BACK short of the inner face (a shallow dip stays inside), clear of the
                                       seam bosses: it overlaps the wall everywhere, no face of it lies on a face of the body

  ~/.venvs/cad/bin/python cad/desk/roly_logo_fill.py        (~1 min)
"""
import pathlib
import rolypoly as rp
from build123d import export_stl, Solid
from OCP.gp import gp_Trsf, gp_Pnt
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

GROW, FRONT, BACK, BOSS = 1.04, 0.5, 0.2, 0.15
OUT = pathlib.Path(__file__).resolve().parent / "out-rolypoly" / "keeper"
S = rp.Surfaces(rp.SH8)
P = rp.logo_pocket(S)
z0, z1 = rp.SEAM - 2.0, rp.LOGO_ZC + P["ph"] / 2 + 12.0
c = P["tool"].center()
tr = gp_Trsf()
tr.SetScale(gp_Pnt(c.X, c.Y, c.Z), GROW)                    # about the cutter's own centre (Shape.scale is about the origin)
tool = Solid(BRepBuilderAPI_Transform(P["tool"].wrapped, tr, True).Shape())
fill = (tool & S.band(FRONT, z0, z1)) - S.band(rp.WALL - BACK, z0 - 1.0, z1 + 1.0)
for b in rp.boss_spots():
    fill = fill - rp.zcyl(b["x"], b["y"], b["r_boss"] + BOSS, rp.SEAM - 1.0, rp.SEAM + b["h"] + BOSS)
fill = fill & rp.box(-100, 100, -100, 100, rp.SEAM, 200)
fill = rp.one_solid(fill, "logo fill")
export_stl(P["cut"], str(OUT / "logo-pocket.stl"), tolerance=0.005, angular_tolerance=0.05)
export_stl(fill, str(OUT / "logo-fill.stl"), tolerance=0.005, angular_tolerance=0.05)
bt, bc = tool.bounding_box(), P["tool"].bounding_box()
rp.check(all(a < b for a, b in zip(bt.min, bc.min)) and all(a > b for a, b in zip(bt.max, bc.max)), "the grown cutter does not enclose the cutter")
print(f"pocket {P['cut'].volume:.1f} mm3, fill {fill.volume:.1f} mm3, trims {P['trims']}")
