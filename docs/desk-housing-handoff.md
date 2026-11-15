# Desk housing: handoff (2026-11-15)

Read this first if you pick the desk housing up on another machine or in a new session.

## Start here
Three tracks. The first is the working prototype; the other two are new looks that came out of the design round on
2026-11-14 and each has its own handoff.

| Track | What it is | Next step | Handoff |
|---|---|---|---|
| v1 box | the fit prototype: shell + lid + test strip, ready to print | print the **test strip v3** and judge it (it decides the slot for all tracks) | this file |
| A. Smooth design | one-piece soft shell + flat lid: upright, front tilted 15°, and oval (`cad/desk/smooth.py`, built and reviewed 2026-11-15) | order the prints (copies in `cad/desk/to-print/`), judge them on the desk | "Smooth shells" at the end of `docs/desk-housing-plan.md`; `docs/desk-housing-smooth-handoff.md` is the history |
| B. Roly-poly | a soft drop-shaped body that rocks sideways and rights itself | settle the open decisions with the user, then CAD for an FDM print | `docs/desk-housing-rolypoly-handoff.md` |

The work of 2026-11-14/15 (test strip v3, concept scripts, pictures, the smooth shells, these docs) is committed on
the branch `desk-housing`. Check `git status`.

## Where things are
| What | Where |
|---|---|
| Spec, decisions, build notes (the contract; newest notes at the end) | `docs/desk-housing-plan.md` |
| Parts with verified links, rejected options | `docs/desk-housing-parts.md` |
| Board mechanics (outline, AA offsets, connectors, measured borders) | `docs/lcd316-mechanical.md` |
| Reviews: plan (Astra), CAD v1 (Astra full, Sol / Fable / Opus critical) | `docs/desk-housing-reviews/` |
| Model v1 (parametric build123d, asserts, swept-path insertion check, report) | `cad/desk/housing.py` |
| Logo: SVG → letter polygons | `cad/desk/eh-logo.svg`, `cad/desk/trace_logo.py` → `eh_logo.json` |
| Renders | `cad/desk/render.py` → `cad/desk/out/*-views.png`, `detail-*.png` |
| Edge-profile sketch (A–D) | `cad/desk/profile_options.py` → `out/profile-options.svg` |
| Outputs to order / numbers | `cad/desk/out/{shell,lid,teststrip,logo-inlays}.{stl,step}`, `out/report.txt` |
| Concept pictures of the design round (sheets, single renders, clay views, agy sketches) | `images/desk-housing-v2/` |
| Concept tools: massing models, clay views, roly-poly mass model, render script, prompts | `cad/desk/concept/` |
| Linux setup (sudo script, PlatformIO 6.1.19 pin, node, CAD venv) | `tools/setup/README.md` |

Rebuild v1: `~/.venvs/cad/bin/python cad/desk/housing.py && ~/.venvs/cad/bin/python cad/desk/render.py`. The build
fails loudly if a fit breaks. A rebuild rewrites the STEP timestamps of unchanged parts: `git checkout` those.

## State of v1
- **Prototype (`PROTOTYPE = True`)**, ready to order by FDM:
  - **shell**: 50 × 98.85 × 34, PLA Matte black or ivory, printed upside down;
  - **lid**: a flat 3 mm plate with 4 × Ø2 × 1 magnet holes;
  - **test strip v3**: 126.8 × 85.5, widths 8.3–9.0 + flat-end pair E/F + profiles S/A/B/C/D (print it face up);
  - **logo-inlays**: translucent, 3 clearance sets.
- **Assembly:**
  - the glass taped to the inside of the front wall (far-end tape ≤ 1.5 wide);
  - the battery (user's: 3000 mAh, 10 × 35 × 68, MX1.25) taped behind the board;
  - a MOGOOD 90° USB-C adapter in the board's own port, a cable through the 15 × 8.5 back hole;
  - LEDs behind the letter inlays;
  - magnets glued in, polarity by stacking.
- **Front:** a 45° chamfer from the 3 mm face to the glass on all four sides (profile B). Rods (8 × 4 half-round,
  68.65 long) on OCA tape. **This slot is superseded** (see "Decisions for every track"); the shell keeps it until
  the test strip is judged.
- **Firmware on the board:** `lcd316@320w8-8` (2 tubes, 8 mm), the user's preset (tubeHeight 54, hoursY 0, minutesY
  224 → drawn tubes 5.94 mm at the AA's long edges, 20.46 c-c). The `m` command shows the measuring face.
- **LCD pitch 0.0825 mm/px** (ruler-confirmed). At 320 rows tubes over ~9.3 mm no longer compile (KAIZEN, "LCD pitch").

## Decisions for every track (user, 2026-11-14/15)
- **Slot:** 45° on the two long sides only; the top and bottom ends stay straight walls, so the cut end of the rod
  is hidden and the tube reads as running into the body.
- **Slot length = rod length**, about 1 mm shorter than the lit area, so no black display edge shows. Rods get cut
  to **66.65** (lit 67.65 − 1). The firmware draws the tube over the full lit length with no end cap
  (`TUBE_LENGTH_PX = PANEL_W`, presets `cornerR` 0), so this works without firmware changes.
- **Front thickness, open until the strip is judged:** E = 3 mm (the rod's crown stays 0.55–0.75 over the face, a
  sliver of the cut end shows), F = 4 mm with a 1 mm straight rim (crown 0.25–0.45 under the face, end hidden).
  New models keep it a parameter. Close-ups: `images/desk-housing-v2/slot-ends.jpg`.
  Track A builds E (user, 2026-11-15: the bevel runs to zero); F stays a switch.
- **Logo:** low on a side is wrong on a body of constant depth. It is fine where the body is clearly wider at the
  base (a tilted front, the roly-poly's belly). A smaller logo is acceptable.
- **Materials:** only ones we can make. No "porcelain". Printed plastic, resin, wood, paint.
- **Firmware:** changes are easy and not ruled out; they are only kept out of the housing sessions (user,
  2026-11-15). A tilted or rocking face probably needs a fizz pass later (fizz rises along
  the tube even when lying); try `fizzEdgeRise` / `fizzFlatRise` first (KAIZEN note).
- **Print plan:** work out sizes on cheap FDM prints, then order the final white part by SLA from another provider.
  fabparts.de is FDM only (PLA Basic / Matte / Marble / Wood / Translucent …, PETG, PETG-CF, TPU; layers 0.28 / 0.20
  / 0.12).

## Open / next for v1
1. **Order** (user): the prints above, the MOGOOD adapter, Ø2 × 1 magnets, the battery, warm-white 0603 LEDs, diffuser
   only if the inlays don't diffuse enough, Kapton.
2. **Measure when the parts arrive:**
   - the board's Type-C face vs the PCB edge (assumed flush) and its depth position (assumed 2 mm in front of the
     board's back);
   - the MOGOOD's plug-to-socket offset;
   - RST/BOOT protrusion;
   - J5/I2C plug protrusion;
   - **the weights of the board and the battery** (the roly-poly model assumes 30 g and 55 g).
3. **Test strip:** pick the slot width and the edge profile; check the rods' light spill on the chamfers (ivory).
   - **Flat ends (E, F):** lay the pair over the two lit tubes with rods cut to 66.65. Does the tube read as running
     into the body? Pick E or F.
4. **v1 iteration ideas** (user-discussed, not decided; tracks A and B replace most of them):
   - a flush USB socket: notch up from the back rim, the adapter slides up into the port, a lid tab below, depth ~26.5;
   - 2 mm walls for print;
   - ~4 mm more height for a bigger margin above the tubes.
5. **Wood version of the box** (kept for reference; track A is the wood-friendly successor):
   - ≥ 0.5 rim at the chamfer; logo strips ≥ 2 (bigger letters or a thin-skin glow); magnet meat (4 mm walls or
     steel discs); a 6 mm bit for the R3 cavity corners, ~95 deep; square slot corners → R0.5.
   - As three glued parts (user, 2026-11-14): U-body (back + both sides), a front + top piece with a smooth curve
     that covers the U's edges, a bottom lid with magnets. Estimated ~€110–280 one-off, against €200–450 for a solid
     one-piece shell. A thin-skin logo (0.6–1 mm of wood left, pocketed from inside), corner blocks for the magnets.
6. **Carrier / light box** are in the code (`PROTOTYPE = False`), with known fixes listed in
   `docs/desk-housing-reviews/4-cad-v1-fable-opus-critical.md`.

## Design round 2026-11-14: what was tried
Pictures are concept sketches by codex or agy; only the clay views show true geometry.

| Sheet (`images/desk-housing-v2/`) | Content | User's verdict |
|---|---|---|
| `sheet.jpg` (1–6) | band over U as a 6° leaning slab: walnut + ivory, upright, black + ivory print, maple, brass, rear | no explicit pick; logo low on the side rejected for this constant-depth body |
| `sheet-2.jpg` (7–9, A1–A3, H1–H3) | wedge 20° / 30°; agy: slab on a base, layered totem, capsule in a yoke, straps over tube ends, cairn | likes the yoke *principle* (it moves, the liquid reacts) and the cairn's soft look |
| `sheet-3.jpg` (10–13) | wedge with flat-end slots, yoke, layered cairn, soft cairn | **13 soft cairn loved**; 12 layers rejected; 11 yoke's design rejected |
| `sheet-4.jpg` (13–17, P) | ways to move: rocking, dish, hidden rear axis, hourglass flip, pendulum | chose **14 rocking** to think through |
| `sheet-5.jpg` (18–20 + clay) | roly-poly at true proportions: at rest, mid-rock, plain FDM | wants a smooth resin-toy finish; asymmetric outline; DIY |

## Oval body (user, 2026-11-15)
A "shampoo bottle": built as the third variant of `cad/desk/smooth.py` (56 × 36 × 110, `cad/desk/out-smooth/oval/`).
Massing: `cad/desk/concept/oval.py`. Numbers: "Oval shell" at the end of `docs/desk-housing-plan.md`. Reviewed.

## Concept tools (`cad/desk/concept/`)
All run with `~/.venvs/cad/bin/python` (build123d 0.13, pyvista 0.49, numpy 2.5). Outputs go to `out-<tag>/` next to
the script; they are throwaway, delete them after copying what you keep.

| Tool | Use |
|---|---|
| `massing.py <tag> [KEY=value …]` | solid massing of the band-over-U body: slab (`LEAN`) or wedge (`WEDGE=1`), slot profile (`SLOT_PROFILE`), logo placeholder |
| `clay.py <tag> [two\|mono\|dark]` | clay views of a massing (hero, ortho, rear-left, slot-end close-ups) |
| `rolypoly.py [KEY=value …]` | roly-poly mass model: shape, masses, centre of mass, rocking period, righting limits, clay views |
| `codex-render.sh <out.png> <prompt.txt> <image> …` | one photoreal render with the Codex CLI; examples in `prompts/` |

Rendering rules that held up:
- Give codex the clay views as the geometry and say what each clay colour means; give a liked picture as the look.
  One image per call, in the background, 1–3 min each, several in parallel are fine. The user has ample codex quota.
- Codex keeps silhouette and proportions but draws rounded tube ends and often garbles digits. Say so when showing.
- For *ideas*, also brief agy for its own concepts, with both models, from `images/` (a trusted workspace):
  `agy --model gemini-4-hydrogen-xhigh|gemini-4-argon-high --mode accept-edits --print="$(cat brief.txt)" </dev/null`.
  The user likes Hydrogen's pictures more; Argon is the stronger model. Tell it: one image per concept, no re-renders.
  Its image quota is small (13 images used it up for ~4 h); its concepts ignore the real hardware.
- Judge pictures by correctness first (true proportions, real tube geometry), richness second.

## Running both tracks from one chat
- The tracks do not share files: A writes `cad/desk/smooth.py` + `cad/desk/out-smooth/`, B writes
  `cad/desk/rolypoly.py` + `cad/desk/out-rolypoly/` (the study in `cad/desk/concept/rolypoly.py` stays as it is). Both may *import* `cad/desk/housing.py` for the hardware numbers
  (it has a `__main__` guard); neither edits it.
- Shared files (`KAIZEN.md`, this handoff, `docs/desk-housing-plan.md`, `docs/desk-housing-parts.md`) are edited by
  the parent chat only. Subagents report their notes back.
- Each track starts with decisions that only the user can make. Ask them first; do not let a subagent pick.
- Repo rules: `CLAUDE.md` (side ideas go to `KAIZEN.md`, laconically). Commit only when the user asks.
