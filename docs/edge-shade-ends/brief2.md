# Follow-up: off-axis viewing (read-only, maths + tables)

Your model (docs/edge-shade-ends/astra-model.md) is on-axis only and concludes the outer ~12 panel rows show only in
a 0.002 mm sliver. The user disagrees from direct observation: "Since I use the rod for magnification, the outermost
rows are quite visible." The watch/desk device is viewed at varying angles (wrist tilt, desk view; the user earlier
noted the moire is strongest at the edges "when we watch from the side", and narrowing the tube kills the 3D look
from the side). Also re-check the on-axis geometry itself (drawn half-width ~2.97 mm under an 8 mm rod, gap 0.87 mm
fitted from one photo): could a plausible gap / rod seating error make the outer rows visible on-axis?

Deliver:
1. Which panel rows (distance d from the tube centre) are seen where (apparent position, magnification |dx/dd|), for
   viewing angles across the tube of 0, 10, 20, 30, 45 deg (eye at distance >> rod; parallel rays at that angle),
   both sides. Show where the outermost rows (d 2.0-2.97 mm) appear and how wide they look, per angle.
2. Profile A of your model (keep today's grey at the old band boundary, darken further toward the outermost row,
   centre unchanged), but with the ramp variable u mapped to apparent position / magnification as seen over a
   representative range of angles (say 0-30 deg, weighted as you see fit, explain), instead of the on-axis returning
   branch only. Row table (retained code K per half row, H 72 at 320w8-8) at edgeShade 0.4 and 0.3, shape 3, fold
   0.4, plus predicted apparent L* across the rod at 0, 15, 30 deg.
3. Whether B's centre-dimming rebound cap is still worth it once off-axis viewing is counted (quantify; the user
   prefers keeping the centre).
4. Implementation notes as before (sim/firmware parity, generated tables, no new params if possible).
