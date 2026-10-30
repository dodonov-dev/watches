# Physical half-round optics — 2026-10-29

User's current samples: 6 mm half-round on AMOLED, 8 mm on LCD. The complaint is
stripes and red/green separation, not inadequate pixel density. Gap, surface profile,
subpixel orientation and photographs have not been measured. This is a conditional
engineering recommendation, not identification of the actual defect.

## Recommendation

Follow-up: the user accepts color fringing near the sides. The main issue is
striping/color artifacts elsewhere, so ideal edge dispersion is not a sufficient
explanation of the complaint.

First compare an untreated sample with a gently hand-polished sample of the existing
extruded PMMA. If shallow surface tooling marks cause the stripes, polishing can
help without changing material. If lines remain inside the material, or removing
surface waviness damages the lens profile, commission a cast-PMMA sample with a
machined and polished flat base. Do not start with generic lacquer.

Cast stock is a fabrication improvement, not an achromatic material. Both cast and
extruded PMMA retain dispersion. A clear glossy surface is also not a guarantee of
correct optical figure: local buffing can leave a glossy but distorted lens.

## Model

Run `python3 docs/physical-tube-model.py`. Standard-library-only offline calculation;
no firmware changes. Checked identity at n=1, symmetry, paraxial agreement and the
dispersion fit. Geometry: ideal half-circle, flat side toward display, observer at
infinity looking normally through the curved side. Exact Snell refraction at both
surfaces; nominal PMMA nd=1.49, Vd=57, two-term Cauchy dispersion estimate.

Central apparent lateral magnification is

    M = 1 / [1/n - g(n-1)/R]

where g is an air gap to the emitting plane and R is radius. Actual cover glass must
be modeled as another layer: near the axis, a thickness t with index nc contributes
t/nc to the equivalent air gap. Zero gap is an ideal limiting case.

| Lens | M at g=0 | M at g=0.5 mm | M at g=1 mm |
|---|---:|---:|---:|
| 6 mm AMOLED | 1.490 | 1.696 | 1.969 |
| 8 mm LCD | 1.490 | 1.640 | 1.823 |

For an 8 mm lens with 0.5 mm air gap, 530 and 630 nm rays at the same apparent
position sample screen locations separated by 5.4 micrometres at x/R=0.5,
8.3 micrometres at 0.75, and 11.9 micrometres at 0.9. Blue/red (450/630 nm)
separations are 12.5, 19.3 and 27.7 micrometres. These are screen-plane sampling
differences, not measured fringe widths. They show that smooth ideal PMMA can
produce color separation at high-contrast boundaries, especially away from center.

Separately, RGB emitters occupy different physical locations. A lens can reveal
color structure without an objectionable visible pixel grid. Assuming equal RGB
stripes, the nominal subpixel pitch would be 28–30 micrometres for the repository's
0.083/0.0912 mm pixel pitches. Actual panel layout and its orientation relative to
the cylinder must be inspected; this assumption is not an AMOLED specification.

This model excludes surface grooves, internal index variations, coatings, stress,
finite observer distance/pupil and actual emission spectra. It cannot predict how
much polishing will improve an unmeasured sample.

## Distinguish causes before further fabrication

- Inspect the removed rod under a reflected straight light source. Distorted or
  broken reflections suggest surface figure/marks; inspect both curved and flat faces.
- Compare over a printed black/white pattern as well as the display. Defects on the
  printed target establish that display subpixels are not required for that defect.
- Compare uniform neutral gray, white and separate red/green/blue fields, then a
  white edge on black. Record which artifacts follow the rod versus the image.
  Dispersion shifts existing wavelengths; it does not turn green light into red.
  Single-channel LCD emission is not perfectly monochromatic, so use this as a
  diagnostic rather than an absolute proof.
- Stress patterns between crossed polarizers identify birefringence, but do not
  prove it causes naked-eye color fringes in the assembled watch.

## Polishing experiment

Use a spare 30–50 mm piece; retain an untreated piece from the same stock. Wash
with mild soap and water, rinse, and inspect. Hand-polish using a fine abrasive
polish explicitly suitable for PMMA and clean soft cotton. Support the flat base
on a clean padded surface, hold by the ends, and work the entire curved face
evenly with light pressure. Use short passes and inspect after rinsing away the
compound. Do not concentrate on a narrow stripe: preserving the cylinder matters.
Inspect the flat face separately; polishing only the dome cannot fix base scratches.

If polish alone fails and actual surface grooves are visible, wet sanding is a
second, more invasive experiment on scrap. A possible fine progression is FEPA
P2000 → P3000 → P5000 then PMMA polish; this is a conservative trial sequence,
not the manufacturer's prescribed lens-making process. Fine paper may not remove
deep extrusion grooves. Use a broad conforming support on the dome, keep it wet,
and rinse between grades. The face becomes hazy before final polishing. If the
task requires substantial material removal, a properly machined replacement is
more predictable than freehand sanding. Do not use flame or solvent polishing
for this experiment: optical figure and residual stress are central concerns.

## Alternatives

### Cast versus extruded: what the model actually establishes

The initial model described ideal homogeneous PMMA, not manufacturing quality.
The script now compares ideal materials at identical geometry (8 mm diameter,
0.5 mm air gap, x/R=0.75), using representative nd/Vd values and the same Cauchy
approximation. These are screen sampling differences, not visible fringe widths:

| Material | nd | Vd | Central M | 530/630 nm sampling difference |
|---|---:|---:|---:|---:|
| Cast PMMA | 1.49 | 57 | 1.640 | 8.33 um |
| Extruded PMMA | 1.49 | 57 | 1.640 | 8.33 um |
| N-BK7 glass | 1.5168 | 64.17 | 1.682 | 7.74 um |
| Representative COP | 1.535 | 56 | 1.711 | 9.15 um |
| Representative polycarbonate | 1.586 | 30 | 1.794 | 18.66 um |

The two PMMA rows deliberately use identical nominal constants. This demonstrates
that changing the manufacturing label alone does not alter ideal ray tracing; it
does not prove that actual grades have precisely identical optical constants.
Manufacturing comparisons need measured surface profile, index homogeneity and
stress. No such measurements are available for these samples.

As a sensitivity illustration, a hypothetical sinusoidal surface error with 1 um
amplitude and 0.2 mm period produces about 49 um peak screen-coordinate displacement
near the crown of the 8 mm lens with 0.5 mm gap (39 um for 6 mm). Linearized Snell
tracing gives delta_x = [R*(n-1)/n + g*(n-1)]*surface_slope. This is displacement of
the image, not red/green separation, and those ripple dimensions are invented test
inputs, not a measured or typical extrusion specification. It illustrates why a
microscopically shallow surface defect can matter more than changing bulk material.

### Are extrusion stripes internal?

Not necessarily. Longitudinal surface draw/die marks are one possibility; internal
index variations and residual stress are separate possibilities. Polishing can
remove surface defects, not bulk variations or stress. The label XT alone does not
establish which is present. A failed mild-polish test also does not prove a bulk
defect: the polishing may simply have removed too little material.

Manufacturer evidence is deliberately qualified:

- [Gevacril's quality specification](https://www.gevacril.com/docs/en/downloads/Quality_Description_en.pdf)
  explicitly covers extruded half-rounds and permits slight visible extrusion stripes.
  It does not establish that those stripes are internal.
- [PLEXIGLAS CA/EX technical information](https://www.plexiglas.de/files/plexiglas-content/pdf/technische-informationen/211-12-EN-PLEXIGLAS-rods-and-tubes.pdf)
  describes its EX rods/tubes as having smooth surfaces free of striations. This is
  a product-specific surface claim, not a guarantee of imaging-grade wavefront quality.
- The PLEXIGLAS machining guide identifies manufacturing-related internal stress
  in XT, particularly tubes. Stress is not automatically a visible stripe or color
  artifact without a polarization-sensitive viewing path.

### Finished cast half-round sourcing lead

[Gammacril's manufacturer product listing](https://light-building.messefrankfurt.com/frankfurt/en/exhibitor-search.detail.html/gammacril-gmbh/mf_1_0015030960_4867743_10000016202601.html)
explicitly offers cast acrylic half-round rods among its special shapes. This is
a relevant alternative to cutting full rods. The listing does not confirm 6/8 mm
half-round dimensions, tolerances, price, stock or minimum order. Request those
and an optical comparison sample before choosing the fabrication route.

Sourcing follow-up: a finished imaging-quality 6/8 mm cast half-round has NOT been
verified as a retail purchase. [Gammacril/Italplastics](https://www.gammacril.de/index.php?site=2)
lists half-rounds on request. A [Plastics Co UK listing](https://plasticsco.co.uk/products/cast-acrylic-clear-rod-for-decorative-elements-signage)
advertises cast 6 mm half-rounds in packs of ten 2 m lengths, with a smooth
transparent finish, but no optical finish specification and no 8 mm option. The
search index exposed the listing; a direct page fetch failed. Treat it as an
unconfirmed lead, not a purchase recommendation. Ordinary polished cast round
stock is easier to source, e.g. [Siegle 8 mm GS](https://ecommerce.siegle.de/556AGRUG-0081).
For a small prototype, preserving the supplied curved surface and machining/lapping
only the flat base is the practical alternative if supplier inquiries fail.

Small-quantity search (user accepts 10 mm as a material-quality experiment; shipping
must reach Germany, Switzerland or Russia):

- [Plexishop 10 mm cast half-round](https://plexishop.it/barre-mezzetonde-trasparenti/22915-barra-a-mezzo-cerchio-metacrilato-o-10-mm.html),
  reference bmtc10: listing says cast PMMA, EUR 6.14/m incl. displayed VAT. Current
  Italian text describes a configurator accepting piece counts and lengths in mm;
  older category text specifies 1/2 m stock lengths and a separate cutting service.
  Exact short-piece minimum and configured checkout price not verified. No 6/8 mm
  half-round listed. Their category invites inquiries for unlisted diameters.
- [Shipping policy](https://plexishop.it/en/content/1-shipping-and-delivery) provides
  international courier shipping and destination-based quotes, but the inspected
  policy does not explicitly confirm Germany/Switzerland/Russia. Country-specific
  acceptance and price remain to be checked at checkout or by supplier response.
- [Plastics Co UK](https://plasticsco.co.uk/) advertises one-piece custom cuts and
  publishes sales@plasticsco.co.uk / +44 1744 520110. Its 6 mm cast half-round page
  still lists ten 2 m rods. Ask to split a pack or supply a paid short sample;
  neither a split pack nor export shipping has been confirmed.
- [Alternative Plastics product catalogue](https://intranet.alternativeplastics.co.uk/rod-and-bar)
  distinguishes cast/extruded half-rounds and offers cutting; no confirmed 6/8 mm
  dimensions or minimum order. Quote lead only.

Search found no confirmed small-quantity 6/8 mm cast half-round with confirmed
delivery to one of the user's countries. Do not substitute an XT listing or a
round rod and call it a match. No suppliers were contacted or orders placed.

| Option | What it can improve | Limit / decision |
|---|---|---|
| Polish existing XT | Shallow scratches and surface extrusion lines | First experiment; cannot remove bulk defects or dispersion |
| Cast PMMA machined to half-round | Extrusion-related defects; more suitable machining stock | Best next prototype if polishing fails; specify optical finish and profile |
| Clear lacquer | May fill fine surface grooves if compatible and sufficiently leveling | Adds curing, thickness and surface-figure uncertainty; not first choice |
| N-BK7 glass | Scratch resistance; specified optical finish | Still dispersive; extra cost, weight, fabrication and breakage concerns |
| Polycarbonate | Impact resistance | Typical Abbe ~30 vs PMMA ~57; poor change for a color-fringe complaint |
| Precision PMMA cylindrical/aspheric optic | Controlled figure and monochromatic aberrations | Premium fabrication route; no inherent achromatization |
| Hollow curved shell | Changes optical power and appearance | Redesign, not a drop-in equivalent of the liked solid-lens effect |

For cast stock, ask a fabricator to fixture a full rod and mill/lap one side to the
diametral plane, preserving the good curved surface. A centered saw cut loses its
kerf: two resulting pieces are thinner than true half-circles. Rough-cut on the
waste side of the intended plane, then finish one accurate part. Request stress
relief per the material supplier and judge a sample over the actual display.

If smooth optics still show color structure, trial a separate removable narrow-angle
diffuser behind the rod, with a controlled distance from the emitting plane. This
is a conditional optical mixing experiment, not the response to the current user's
pixel-density complaint. First-order blur FWHM in air is approximately
2*d*tan(theta/2): 2° at 1 mm gives 35 micrometres, 5° gives 87 micrometres. Start
weak; diffusion softens markings too. A film directly against emitters has little
spatial mixing distance. Manufacturer diffusion angles are typically FWHM for a
collimated input; the real panel/lens stack needs a bench comparison.

## Sources

- [PLEXIGLAS polishing guide](https://www.plexiglas.de/de/service/verarbeitung/plexiglas-schleifen-und-polieren):
  hand polishing, wet sanding, heat control, and optical changes from local removal.
- [PLEXIGLAS machining manual](https://www.plexiglas.de/files/plexiglas-content/pdf/verarbeitungsrichtlinie/311-1-Machining-PLEXIGLAS.pdf):
  GS/XT processing, polishing, annealing, stress and solvent interaction.
- [ePlastics, its cast/extruded rod and tube comparison](https://www.eplastics.com/blog/cast-extruded-acrylic-rod-tube):
  extrusion lines, cast-stock finishing and machining differences.
- [MGC optical resin reference](https://iupizeta.mgc.co.jp/en/column/abbe-number/):
  nominal indices and Abbe numbers; these are representative, not grade guarantees.
- [Luminit diffuser data](https://www.luminitco.com/sites/default/files/2024-05/Luminit_angles_sizes_formats_datasheet.pdf):
  available 1°, 2°, 3.5°, 5° films and FWHM convention.
- [GS Plastic Optics manufacturer announcement](https://www.optica.org/about/newsroom/corporate_member_news/2021/gs_plastic_optics_reduces_diamond_turning_lead_time/):
  precision diamond machining of PMMA and other optical polymers.
