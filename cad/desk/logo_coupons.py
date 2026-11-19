"""Logo fit coupons: slices of the real smooth shells (upright front, tilt15 left side) around the logo cut-out,
kept in print orientation (rim on the bed). Run from cad/desk: ~/.venvs/cad/bin/python logo_coupons.py"""
import sys
from build123d import import_step, Box, Pos, export_stl, Align
A = (Align.MIN, Align.MIN, Align.MIN)
def cut(src, x0, x1, y0, y1, z0, z1, out):
    s = import_step(src)
    c = s & (Pos(x0, y0, z0) * Box(x1 - x0, y1 - y0, z1 - z0, align=A))
    sols = c.solids()
    bb = c.bounding_box()
    print(out, 'solids', len(sols), 'vol', round(c.volume, 1), 'bbox', [round(v, 2) for v in (bb.min.X, bb.min.Y, bb.min.Z, bb.max.X, bb.max.Y, bb.max.Z)])
    export_stl(c, out, tolerance=0.01, angular_tolerance=0.1)
cut('out-smooth/upright/shell.step', -12, 12, -1, 6, -0.01, 16, 'to-print/logo-coupon-upright.stl')
cut('out-smooth/tilt15/shell.step', -27, -18, 11, 41, -0.01, 26, 'to-print/logo-coupon-tilt15.stl')
# Roly-poly logo glow coupon: the belly around the 14 mm glow-through logo (0.8 skin), printed like the body (seam ring
# on the bed, z 22). For the LED glow test; the material matters (PLA Basic vs Matte vs resin).
cut('out-rolypoly/body.step', 20, 44, -22, -4, 21.99, 40, 'to-print/rolypoly-logo-coupon.stl')
