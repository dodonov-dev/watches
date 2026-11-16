# Roly-poly: slicer check (2026-11-16)

The five print files of round 4 (`cad/desk/to-print/rolypoly-*.stl`) sliced with OrcaSlicer 2.5.0 from the command
line, and the toolpaths read back from the G-code. By the parent chat, not an outside reviewer.

**Method.** `orca-slicer.exe --load-settings "machine.json;process.json" --load-filaments filament.json --slice 0
--outputdir <dir> <part>.stl`, run through a `.bat` (the exe prints nothing to a WSL console). Orca's printer
profiles are packed (`.opc`), so the settings are a generic machine (0.4 nozzle, 256³) plus Orca's
`resources/profiles_template` process and PLA templates with: layer 0.12 (first 0.2), 4 walls, Arachne, line
0.42 / 0.45, tree(auto) supports at the default 30° threshold. Parts turned as the build sheet says. This is a
generic profile, not a real printer: times and support shapes are indicative.

| Part, orientation | Layers | Filament | Of it support | Time |
|---|---|---|---|---|
| body, seam ring down, supports from the bed only | 883 | 61.1 g | 11 % | 5 h 56 |
| cup-rock on its back, 100 % infill, brim | 415 | 21.1 g | 23 % | 2 h 32 |
| cup-rock rim down (for comparison) | 183 | 22.1 g | 26 % | 2 h 56 |
| cup-flat, foot down, no supports | 83 | 12.0 g | – | 0 h 56 |
| door, face down, no supports | 41 | 6.2 g | – | 0 h 28 |

## Findings
1. **Fault: supports inside the logo letters.** Every downward-facing face of the letter pockets (the top edge of
   each letter and of the E's bars, up to z 34.4) gets support interface at z 32.2–34.3, lying against the 0.8 skin
   from inside, on four trunks that rise from the bed behind the logo. It cannot be removed from a 1.6 mm deep
   pocket and would shadow the glow. Fix: 45° roofs in the pockets (round 5). `slicer-logo-support.png`.
2. **Logo skin: prints as two lines.** 0.40–0.42 mm each (0.37–0.52), both as outer walls, over the whole logo.
3. **Body, inside:** tabs, bosses, bulkhead and ledges get no support. Supported are only the bulkhead notch and
   the USB hole (z 32–34), the door opening's top edge and a cap of about 10 × 9 mm at the very top of the crown
   (z 125), on trunks 100 mm tall. `slicer-body-top.png`.
4. **Door opening's top edge:** a 29.5 mm overhang, held by a line of support interface on trees that stand in
   front of the body and lean in over the alcove. They pass close to the alcove's visible surface.
5. **Cup on its back:** the part touches the bed on 11 × 5 mm (54 mm²); the slicer's own support base, about
   60 × 30 mm (990 mm²), carries it, with a brim round the part. Trunks inside the bowl stand on the bed in front
   of the open bowl. The R44 surface is vertical walls in every layer: no support on it. One of the eight seam
   holes gets a support tip. `slicer-cup-back.png`.
6. **Cup rim down:** all eight holes are filled with support, and the last layer at the pole is 2.2 × 13 mm (6.6 ×
   21 one layer lower): the flat the build sheet warns of. On its back is the better orientation.
7. **Door:** no overhang walls; lines 0.35–0.74 wide; the bevels print as plain walls.
8. **Flat cup:** no supports needed: overhang walls 268 mm in all, longest 4.1; bridges up to 2.8.
9. The body's run printed `Error: Not precalculated Placeable areas requested` several times (the tree support
   code); the G-code is complete. Not looked into.

## After round 5 (45° roofs in the letter pockets)
The body sliced again with the same settings: **no support in or behind the logo** (none between x 23 and 38 in
front of y −8); the skin is still two lines of 0.40–0.42. Support interface at z 30–36 is left only at the USB
hole. Body: 60.9 g, 5 h 49. `slicer-logo-round5.png` shows the same four layers. To judge on the print: the wall
above each letter's top edge now thickens from 0.8 to 2.4 over 1.6 mm, so the top edges may glow softer than the
bottom edges.

Not covered: a real printer's profile, cooling and warping, support removal by hand, the look of the skin.
Pictures in `images/desk-housing-v2/slicer-*.png` (toolpaths of single layers, colours by line type).
