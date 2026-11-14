# Desk housing: handoff (2026-11-14)

Read this first if you pick the desk housing up on another machine or in a new session.

## Where things are
| What | Where |
|---|---|
| Spec, decisions, build notes (the contract; newest notes at the end) | `docs/desk-housing-plan.md` |
| Parts with verified links, rejected options | `docs/desk-housing-parts.md` |
| Board mechanics (outline, AA offsets, connectors, measured borders) | `docs/lcd316-mechanical.md` |
| Reviews: plan (Astra), CAD v1 (Astra full, Sol / Fable / Opus critical) | `docs/desk-housing-reviews/` |
| Model (parametric build123d, asserts, swept-path insertion check, report) | `cad/desk/housing.py` |
| Logo: SVG → letter polygons | `cad/desk/eh-logo.svg`, `cad/desk/trace_logo.py` → `eh_logo.json` |
| Renders | `cad/desk/render.py` → `cad/desk/out/*-views.png`, `detail-*.png` |
| Edge-profile sketch (A–D) | `cad/desk/profile_options.py` → `out/profile-options.svg` |
| Outputs to order / numbers | `cad/desk/out/{shell,lid,teststrip,logo-inlays}.{stl,step}`, `out/report.txt` |
| Linux setup (sudo script, PlatformIO 6.1.19 pin, node, CAD venv) | `tools/setup/README.md` |

Rebuild: `~/.venvs/cad/bin/python cad/desk/housing.py && ~/.venvs/cad/bin/python cad/desk/render.py`. The build fails
loudly if a fit breaks.

## State
- **Prototype (`PROTOTYPE = True`)**, ready to order by FDM:
  - **shell**: 50 × 98.85 × 34, PLA Matte black or ivory, printed upside down;
  - **lid**: a flat 3 mm plate with 4 × Ø2 × 1 magnet holes;
  - **test strip**: widths 8.3–9.0 + profiles S/A/B/C/D;
  - **logo-inlays**: translucent, 3 clearance sets.
- **Assembly:**
  - the glass taped to the inside of the front wall (far-end tape ≤ 1.5 wide);
  - the battery (user's: 3000 mAh, 10 × 35 × 68, MX1.25) taped behind the board;
  - a MOGOOD 90° USB-C adapter in the board's own port, a cable through the 15 × 8.5 back hole;
  - LEDs behind the letter inlays;
  - magnets glued in, polarity by stacking.
- **Front:** a 45° chamfer from the 3 mm face to the glass (profile B). Rods (8 × 4 half-round, 68.65 long) on OCA tape.
- **Firmware on the board:** `lcd316@320w8-8` (2 tubes, 8 mm), the user's preset (tubeHeight 54, hoursY 0, minutesY
  224 → drawn tubes 5.94 mm at the AA's long edges, 20.46 c-c). The `m` command shows the measuring face.
- **LCD pitch 0.0825 mm/px** (ruler-confirmed). At 320 rows tubes over ~9.3 mm no longer compile (KAIZEN, "LCD pitch").

## Open / next
1. **Order** (user): the prints above, the MOGOOD adapter, Ø2 × 1 magnets, the battery, warm-white 0603 LEDs, diffuser
   only if the inlays don't diffuse enough, Kapton.
2. **Measure when the parts arrive:**
   - the board's Type-C face vs the PCB edge (assumed flush) and its depth position (assumed 2 mm in front of the
     board's back);
   - the MOGOOD's plug-to-socket offset;
   - RST/BOOT protrusion;
   - J5/I2C plug protrusion.
3. **Test strip:** pick the slot width and the edge profile; check the rods' light spill on the chamfers (ivory).
4. **Next iteration ideas** (user-discussed, not decided):
   - a flush USB socket: notch up from the back rim, the adapter slides up into the port, a lid tab below, depth ~26.5;
   - 2 mm walls for print;
   - ~4 mm more height for a bigger margin above the tubes.
5. **Wood version:**
   - ≥ 0.5 rim at the chamfer;
   - logo strips ≥ 2 (bigger letters or a thin-skin glow);
   - magnet meat (4 mm walls or steel discs);
   - a 6 mm bit for the R3 cavity corners, ~95 deep;
   - square slot corners → R0.5.
6. **Carrier / light box** are in the code (`PROTOTYPE = False`), with known fixes listed in
   `docs/desk-housing-reviews/4-cad-v1-fable-opus-critical.md`.
