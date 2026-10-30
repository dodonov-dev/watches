"""Standalone ideal half-cylinder study; run with python3 docs/physical-tube-model.py.

No firmware/simulation dependencies. Units: mm. Reverse trace from an on-axis
observer at infinity through a circular PMMA surface, flat base and air gap.
The air gap is measured to the emitting plane, not the cover-glass surface.
Real cover glass, finite pupil, surface errors and pixel layouts are not modeled.
"""
import math


def index(wavelength_nm, nd=1.49, abbe=57):
    """Two-term Cauchy approximation fitted to nd and Abbe number, not a grade spec."""
    b = (nd - 1) / abbe / (486.13**-2 - 656.27**-2)
    return nd + b * (wavelength_nm**-2 - 587.56**-2)


def source(x, radius, gap, n):
    """Screen coordinate sampled at apparent coordinate x by exact Snell tracing."""
    alpha = math.asin(x / radius)
    theta = alpha - math.asin(math.sin(alpha) / n)
    z = math.sqrt(radius * radius - x * x)
    sin_air = n * math.sin(theta)
    if abs(sin_air) >= 1:
        return math.nan  # Total internal reflection at the flat base.
    return x - z * math.tan(theta) - gap * math.tan(math.asin(sin_air))


def central_magnification(radius, gap, n=1.49):
    return 1 / (1 / n - gap * (n - 1) / radius)


def verify():
    for radius in (3, 4):
        for gap in (0, .5, 1):
            assert source(0, radius, gap, 1.49) == 0
            x = .4 * radius
            assert abs(source(x, radius, gap, 1) - x) < 1e-12
            assert abs(source(x, radius, gap, 1.49)
                       + source(-x, radius, gap, 1.49)) < 1e-12
            numerical = 1e-5 / source(1e-5, radius, gap, 1.49)
            assert abs(numerical - central_magnification(radius, gap)) < 1e-8
    assert abs(index(587.56) - 1.49) < 1e-12
    assert abs((index(486.13) - index(656.27)) - .49 / 57) < 1e-12


if __name__ == '__main__':
    verify()
    print('Checks passed: identity, symmetry, paraxial limit, dispersion fit.')
    print('panel,diameter_mm,air_gap_mm,central_M,pixel_apparent_mm,RGB_third_pitch_mm')
    for panel, radius, pitch in [('AMOLED', 3, .083), ('LCD', 4, .0912)]:
        for gap in (0, .5, 1):
            m = central_magnification(radius, gap)
            print(f'{panel},{2*radius},{gap},{m:.3f},{pitch*m:.4f},{pitch*m/3:.4f}')
    print('\n8mm lens, 0.5mm air gap: wavelength-dependent screen sampling')
    print('apparent_x_over_R,red_green_separation_um,blue_red_separation_um')
    for frac in (0, .25, .5, .75, .9):
        points = [source(frac*4, 4, .5, index(w)) for w in (450, 530, 630)]
        print(f'{frac},{abs(points[2]-points[1])*1000:.2f},'
              f'{abs(points[2]-points[0])*1000:.2f}')
    print('\nIdeal material comparison: 8mm lens, 0.5mm air gap, x/R=0.75')
    print('material,nd,Vd,central_M,red_green_screen_separation_um')
    for material, nd, abbe in [('PMMA cast', 1.49, 57),
                               ('PMMA extruded', 1.49, 57),
                               ('N-BK7', 1.51680, 64.17),
                               ('COP representative', 1.535, 56),
                               ('PC representative', 1.586, 30)]:
        rg = abs(source(3, 4, .5, index(630, nd, abbe))
                 - source(3, 4, .5, index(530, nd, abbe))) * 1000
        print(f'{material},{nd},{abbe},{central_magnification(4,.5,nd):.3f},{rg:.2f}')
    # Sensitivity scenario, not measured XT roughness: sinusoidal height error
    # at the crown, h=A*sin(2*pi*x/period). Linearized Snell trace gives
    # |delta x_screen| = [R*(n-1)/n + g*(n-1)] * |dh/dx|.
    # It moves all channels; it is not itself a predicted colored fringe width.
    print('\nHypothetical surface ripple: 1um amplitude, 0.2mm period')
    for radius in (3, 4):
        displacement = (radius*.49/1.49 + .5*.49) * (2*math.pi*.001/.2)
        print(f'D={2*radius}mm: peak first-order screen shift={displacement*1000:.1f}um')
    print('\nDiffuser first estimate, air propagation: blur FWHM = 2*d*tan(angle/2)')
    for distance in (.5, 1):
        for angle in (1, 2, 3.5, 5):
            blur = 2*distance*math.tan(math.radians(angle/2))
            print(f'd={distance}mm angle={angle}deg blur={blur*1000:.1f}um')
