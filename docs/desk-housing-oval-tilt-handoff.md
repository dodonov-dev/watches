# Desk housing, track A2: the tilted oval (handoff, 2026-11-20)

A new smooth shell that combines the **oval's look** with the **tilt15's readability**. Not designed yet: start
with pictures and decisions, then CAD.

Read first: `docs/desk-housing-handoff.md` (entry, tools, decisions for every track), the end of
`docs/desk-housing-plan.md` ("FDM round 1", "FDM round 2", "Round 3 CAD"): what printing taught us.
Repo rules: `CLAUDE.md` (side ideas to `KAIZEN.md`, laconically). Commit only when the user asks.

## What the user said (2026-11-20)
- The **oval** shell looks optically the nicest of the three printed shells.
- On the table the **15° front** is the easiest to read the time from.
- Combine the two. Taking a step back is fine: new concept pictures first, with **codex** or **agy's Neon model**
  (the user finds Neon consistent; other Google models are good for search and ideas, not for consistency).
- Earlier: white Basic looked "hospital-like"; PLA Matte white is the current material (a test print is running).
  Colours are still open (warm off-white + dark accent, earthy mid-tones, dark bodies; see the plan's notes).

## The two parents (built, printed, in `cad/desk/smooth.py`)
| | oval | tilt15 |
|---|---|---|
| Size (W × D × H, with the 3 mm lid) | 56 × 36 × 110 | 50 × 49.7 × 106.5 |
| Plan | superellipse \|2x/W\|^n + \|2(y−D/2)/D\|^n = 1, n 2.8, extruded straight up | rounded rectangle, rear corners R10, R5 chain |
| Front | curved outside, flat inside (4.55 on the centre line) | flat, leaning back 15°, 3 mm |
| Top | flat 44 × 24, R6 edge; 45° taper inside (ceiling bridge 14.5) | R15 roll into a 5.3 deep flat top |
| USB | hole in the back (MOGOOD adapter) | notch at the rim, right-angle extension (the MOGOOD sticks out a little) |
| Logo | 14 mm, front, under the tubes | 24 mm, left side |
| Code | `OvalModel` (overrides plan, outer body, cavity; `front_out_y`), `build_oval` | `Model` with `TILT=15` (`to_world`, `y_front`) |
| Reports | `cad/desk/out-smooth/oval/report.txt` | `cad/desk/out-smooth/tilt15/report.txt` |

Hardware fits in all three printed shells (photos `images/cable_photos/`); the oval even takes two batteries.

## Shared rules that came from printing (keep them)
- **Slots:** 8.1 wide for 8.0 rods, a straight **0.6 land** at the inner face, then 45° out to the face; straight
  ends; 66.85 long for rods cut to 66.65 (1 mm shorter than the lit area). No knife edges anywhere: a 0.4 nozzle
  drops anything thinner than ~0.4.
- **Logo:** glow-through. One rounded-rectangle pocket from inside, **1.0 skin**, left/right sides flared 45°,
  plus a flat-printed stencil (white preferred) with matching slopes. Nothing printed standing may start in mid-air.
- **Print:** standing on the rim, no supports, X1E 0.4, 0.08 High Quality (0.12 for quick tests), 4 walls, seam
  back, Arachne, **ironing on top surfaces**, textured PEI. Flat tops look patchy without ironing.
- **Known marks:** a horizontal line at the slots' top on one side (bridge layers); abrupt wall-thickness steps
  show as sink lines; thin skins in white PLA show through unlit.
- Front thicker than 3 for more rod relief: skipped for now (user). A lip over the slot sides against moiré is a
  later option.

## Open decisions (ask the user; do not let a subagent pick)
1. **How it tilts:** (a) a wedge: front leans 15°, back vertical, the oval section shrinking in depth with height
   (like tilt15); (b) the whole oval leaning back 15° on a cut foot (a leaning bottle); (c) something else from
   the pictures.
2. **Plan and size:** keep the oval's 56 × 36 superellipse (its depth must still hold the board stack + battery
   when leaning), or widen/deepen.
3. **Top:** the oval's flat top with R6, or a roll like tilt15.
4. **Logo place and size**, **USB route** (hole vs notch), tipping stability (tilt15 report has the method).

## Suggested order
1. **Pictures:** 2-4 concepts (codex: `cad/desk/concept/codex-render.sh <out.png> <prompt.txt> <image>…`, examples
   in `cad/desk/concept/prompts/`; give the photos of the printed oval and tilt15 as the look; agy Neon for its own
   variants, one image per concept: check `agy --help` for the model id, call form in `docs/desk-housing-handoff.md`).
   Judge true proportions first; codex draws rounded tube ends and garbles digits.
2. **Clay / massing** at true proportions (`cad/desk/concept/clay.py`, `massing.py`, or a small study script) for
   the chosen variant; the user decides.
3. **CAD** as a new variant in `smooth.py` (reuse `OvalModel` + the tilt frame and every existing check: insertion
   sweeps, wall measure, slot land, pocket/stencil checks), outputs `cad/desk/out-smooth/<name>/`, copies to
   `cad/desk/to-print/`. Do not edit `housing.py` or `rolypoly.py`.
4. **Review:** Astra through the Codex CLI, critical issues only, reproducing numbers from the exported files:
   `~/_PROJECTS/pigeon_drop/tools/codex-run.sh <run-dir> -m gpt-6.2-astra -e high -C <repo> -- "<brief>"`.
   Last round it found four checks too weak to catch their own faults: ask it to try fault injection.
5. **Print** in Bambu Studio (the user's projects are in `cad/desk/to-print/*.3mf`); a quick 0.12 test first.
