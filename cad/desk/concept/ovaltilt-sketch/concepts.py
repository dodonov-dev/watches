from geo import *
import geo, sys

def Fp(yt, s): return np.array((yt + s * S15, LID + s * C15))
DIR = np.array([S15, C15])
def sqp(z0, z1, x0, x1, p, n=70):
    """superellipse quadrant as a profile: x0 at z0 (vertical tangent) -> x1 at z1 (horizontal tangent)"""
    th = np.linspace(0, np.pi / 2, n + 1)
    return np.c_[x1 + (x0 - x1) * np.cos(th) ** (2 / p), z0 + (z1 - z0) * np.sin(th) ** (2 / p)]
RU = 2.2 / (1 - math.cos(math.radians(45)))      # underside radius whose first 45 deg fit in 2.2 of the 3 mm lid
RUN = RU * math.sin(math.radians(45))            # 5.31: how far the flat foot lies inside the rim
def under(rim, sg, belly, zb, k=2.2, m=None):
    """pebble underside: flat foot -> arc in the lid (tangent to the desk, 45 deg at z 2.2) -> 0.8 land -> shell from the rim at 45 deg up to the belly"""
    ph = np.radians(np.linspace(0, 45, 12)); foot = rim - sg * RUN
    arc = np.c_[foot + sg * RU * np.sin(ph), RU * (1 - np.cos(ph))]
    m = m if m is not None else 0.45 * (zb - LID)
    return [arc, line(arc[-1], (rim, LID)), bez((rim, LID), (rim + sg * k, LID + k), (belly, zb - m), (belly, zb))]

# ---------------------------------------------------------------- 1 pebble (refined d)
def pebble():
    yt = 0.0; H = 110.0; ap = (38.0, H)
    f10, f98 = Fp(yt, 10), Fp(yt, 98.5)
    ph = np.radians(np.linspace(0, 45, 12)); rimf = 2.9
    arcf = np.c_[rimf + RUN - RU * np.sin(ph), RU * (1 - np.cos(ph))]
    front = chain(arcf, line(arcf[-1], (rimf, LID)), bez((rimf, LID), (rimf - 1.3, LID + 1.3), f10 - 4.2 * DIR, f10), line(f10, f98), bez(f98, f98 + 6.5 * DIR, (31.5, H), ap))
    bw, bz = PEB_BW, PEB_BZ
    back = chain(*under(55.8, 1, 60.0, bz), bez((60.0, bz), (60.0, 75), (56.5, H), ap))
    wl = chain(*under(bw - 3.4, 1, bw, bz), sqp(bz, H, bw, 0.0, PEB_P))
    return [Body(front, back, wl * np.array([-1, 1]), wl, n=PEB_N, yt=yt, cfrac=0.46)], yt, dict(flat_top=0)
PEB_P, PEB_N = 2.9, 2.8   # pebble: front-outline exponent above the belly (lower = more egg), plan exponent
PEB_BW, PEB_BZ = 30.0, 30.0   # pebble: belly half-width and its height above the desk (widest point)

# ---------------------------------------------------------------- 2 found stone (asymmetric pebble)
def found():
    yt = 0.0; H = 110.0; ap = (37.0, H); xa = -3.0
    f10, f98 = Fp(yt, 10), Fp(yt, 98.5)
    ph = np.radians(np.linspace(0, 45, 12)); rimf = 2.9
    arcf = np.c_[rimf + RUN - RU * np.sin(ph), RU * (1 - np.cos(ph))]
    front = chain(arcf, line(arcf[-1], (rimf, LID)), bez((rimf, LID), (rimf - 1.3, LID + 1.3), f10 - 4.2 * DIR, f10), line(f10, f98), bez(f98, f98 + 6.5 * DIR, (30.5, H), ap))
    back = chain(*under(56.3, 1, 61.0, 24), bez((61.0, 24), (61.0, 72), (56.5, H), ap))
    left = chain(*under(-25.6, -1, -28.5, 40), sqp(40, H, -28.5, xa, 2.7))
    right = chain(*under(29.5, 1, 33.5, 22), sqp(22, H, 33.5, xa, 2.7))
    xback = lambda z: 5.0 * (1 - z / H)          # the back's apex sits right of centre low down: a skewed egg plan
    return [Body(front, back, left, right, yt=yt, xback=xback, nb=2.5, cfrac=0.46)], yt, dict(flat_top=0)

# ---------------------------------------------------------------- 3 soft cairn (pear: belly low, head leaning back)
def cairn():
    yt = 0.0; H = 110.0; R = 12.0; zt = H - R
    f10 = Fp(yt, 10)
    zz = zt + R * np.sin(np.linspace(0, np.pi / 2, 24)); d = R - np.sqrt(np.maximum(R * R - (zz - zt) ** 2, 0))
    face = lambda z: yt + (z - LID) * T15
    t6 = math.tan(math.radians(6)); upb = lambda z: yt + 52.3 + (z - 80) * t6
    ph = np.radians(np.linspace(0, 45, 12)); rimf = 2.9
    arcf = np.c_[rimf + RUN - RU * np.sin(ph), RU * (1 - np.cos(ph))]
    front = chain(arcf, line(arcf[-1], (rimf, LID)), bez((rimf, LID), (rimf - 1.3, LID + 1.3), f10 - 4.2 * DIR, f10), line(f10, (face(zt), zt)), np.c_[face(zz) + d, zz])
    b62 = np.array((upb(62), 62.0)); bd = np.array((t6, 1.0))
    back = chain(*under(57.5, 1, 62.0, 18, m=7), bez((62.0, 18), (62.0, 34), b62 - 20 * bd, b62), line(b62, (upb(zt), zt)), np.c_[upb(zz) - d, zz])
    wl = chain(*under(28.2, 1, 32.0, 18, m=7), bez((32.0, 18), (32.0, 38), (27.2, 50), (26.0, 70)), line((26.0, 70), (25.0, zt)), np.c_[25.0 - d, zz])
    return [Body(front, back, wl * np.array([-1, 1]), wl, yt=yt)], yt, dict(flat_top=4)

# ---------------------------------------------------------------- 4 leaning stones (oval slab + prop stone)
def stones():
    yt = 0.0; H = 108.0; DS = 33.0
    f3, f97 = Fp(yt, 3), Fp(yt, 97)
    front = chain(bez((1.2, 0), (0.5, 0.9), f3 - 2.5 * DIR, f3), line(f3, f97), bez(f97, f97 + 6.0 * DIR, (31.0, H), (40.0, H)))
    bl = lambda z: yt + DS + (z - LID) * T15
    pb = np.array((bl(95), 95.0))
    back = chain(line((bl(0) - 0.6, 0), (bl(1.5), 1.5)), line((bl(1.5), 1.5), pb), bez(pb, pb + 7 * DIR, (52.0, H), (40.0, H)))
    wl = chain(bez((27.2, 0), (27.6, 0.6), (28.0, 1.5), (28.0, 3)), line((28.0, 3), (28.0, 90)), bez((28.0, 90), (28.0, 101), (23.0, H), (13.0, H)))
    slab = Body(front, back, wl * np.array([-1, 1]), wl, yt=yt)
    zc, az, yc, ay, ax = 11.0, 18.0, 38.0, 18.0, 23.0
    zp = zc + az * np.sin(np.linspace(math.asin(-zc / az), np.pi / 2, 70)); zp[0] = 0.0; k = np.sqrt(np.maximum(1 - ((zp - zc) / az) ** 2, 0)); k[-1] = 0.02
    prop = Body(np.c_[yc - ay * k, zp], np.c_[yc + ay * k, zp], np.c_[-ax * k, zp], np.c_[ax * k, zp], n=2.0, yt=yt, bow=False, hidden=True)
    return [slab, prop], yt, dict(flat_top=0)

# ---------------------------------------------------------------- 5 menhir (bowed-back oval)
def menhir():
    yt = 0.0; H = 108.0; R = 7.0; zt = H - R
    zz = zt + R * np.sin(np.linspace(0, np.pi / 2, 24)); d = R - np.sqrt(np.maximum(R * R - (zz - zt) ** 2, 0))
    face = lambda z: yt + (z - LID) * T15
    bk = lambda z: 48.5 + 0.00047 * z * z
    f3 = Fp(yt, 3); zm = np.linspace(2, zt, 40)
    front = chain(bez((1.2, 0), (0.5, 0.9), f3 - 2.5 * DIR, f3), line(f3, (face(zt), zt)), np.c_[face(zz) + d, zz])
    back = chain(bez((47.9, 0), (48.3, 0.6), (48.5, 1.2), (bk(2), 2)), np.c_[bk(zm), zm], np.c_[bk(zz) - d, zz])
    wl = chain(bez((27.2, 0), (27.6, 0.6), (28.0, 1.5), (28.0, 3)), line((28.0, 3), (28.0, zt)), np.c_[28.0 - d, zz])
    return [Body(front, back, wl * np.array([-1, 1]), wl, yt=yt)], yt, dict(flat_top=4)

# ---------------------------------------------------------------- references a-d (for the critique numbers)
def wedge(D0=51.5, Wd=56.0, H=108.0, beta=0.0, yt=0.0):
    z = np.linspace(0, H, 50); tb = math.tan(math.radians(beta))
    return [Body(np.c_[yt + (z - LID) * T15, z], np.c_[D0 + z * tb, z], np.c_[np.full_like(z, -Wd / 2), z], np.c_[np.full_like(z, Wd / 2), z], yt=yt)], yt, dict(flat_top=4)

CONCEPTS = dict(pebble=pebble, found=found, cairn=cairn, stones=stones, menhir=menhir)
if __name__ == "__main__":
    for nm, fn in CONCEPTS.items():
        bodies, yt, kw = fn(); analyse(nm, bodies, yt, **kw)
    print()
    analyse("a wedge 56x51.5", *wedge()[:2], flat_top=4)
    analyse("a wedge 56x50 (as prompted)", *wedge(D0=50)[:2], flat_top=4)
    analyse("b bottle/oblique 56x37.3 horizontal", *wedge(D0=37.3 - 0.8, beta=15)[:2], flat_top=4)
    analyse("c column 56x52 with facet from the toe (mass ~ wedge with full-depth sides)", *wedge(D0=52)[:2], flat_top=4)
