---
name: digit-sprites
description: Generate a new image-based digit font for the Liquid Watch sim — AI sheet via codex image_gen → cut into an RGBA sprite sheet → register in the sim. Use when the user asks for a new metallic / steampunk / styled digit set.
---

# New digit sprite font (codex → cutter → sim)

Produces `digitFont` entry N+1 for the sim. Takes ~3–5 min wall clock; codex generation is the slow part, so run it in the background.

## 1. Generate the sheet with codex

```bash
cd /home/andrey/_PROJECTS/watches/images/digits   # cwd MUST be this dir: codex saves next to cwd
codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox --ephemeral \
  -C /home/andrey/_PROJECTS/watches/images/digits \
  [--image=<reference.png>] \
  -- "Use your image_gen tool to create a single PNG named digits-<style>-sheet.png. Content: the ten digits 0 1 2 3 4 5 6 7 8 9 in one horizontal row, evenly spaced, never touching, same cap height. Style: <describe: material, finish, bevel/engraving, typeface feel, lighting>. Background: pure black #000000, no border, no shadow on the background, no text other than the digits. Aspect ratio about 5:1 (e.g. 2000x400). Save it into the current directory."
```

Rules that make the cutter work:
- **Pure black background** — alpha is derived from luminance.
- **Ten glyphs in one row, none touching** — the cutter splits on empty columns and asserts exactly 10 runs.
- No drop shadow / glow on the background (it becomes alpha), no frame, no caption.
- Pass `--image=` with an existing sheet (e.g. `digits-steel-sheet.png`) when you want a matching layout.
- Run as `Bash(run_in_background)` with an absolute `-C`; do **not** background a `cd && codex … &` compound (cwd race — the earlier copper sheet landed in `sim/`).
- If the file appears elsewhere, `mv` it into `images/digits/`. Sanity-check with `identify` (ImageMagick) that it's ~5:1.

## 2. Cut into a sprite sheet

```bash
python3 sim/tools/make-digit-sprites.py images/digits/digits-<style>-sheet.png sim/public/assets/digits-<style>.png 64 100
```

Writes one RGBA sheet per cell height — `digits-<style>.png` (64 rows) and `digits-<style>-100.png` — each with a `.png.json` (`{cellW, cellH, widths[10]}`). The heights are the values of `SPRITE_CELL_H` (`spec/layout.h`): a canvas with a tube wider than design size uses the 100-row cut. Needs Pillow + numpy (`pip install --break-system-packages numpy` if missing).
If it asserts `expected 10 glyphs, found N`: glyphs touch (N<10) or a glyph has a detached piece / stray speck (N>10). Fix by regenerating, or lightly edit the sheet with ImageMagick (e.g. `convert in.png -fuzz 8% -fill black -opaque '#101010' out.png` to kill noise near black).

## 3. Register in the sim

- `sim/src/render.ts`: append `'digits-<style>'` to `SPRITE_SHEETS` (index = `digitFont` value − `SPRITE_FONT`).
- `sim/src/params.ts`: bump `digitFont` meta `max` and extend the label (`… · 8 <style>`); update the comment on the `digitFont` field.
- `sim/src/render.ts`: append the sheet name to `SPRITE_SHEETS` and extend the `digitFont` comment in `sim/src/params.ts`.
- Firmware: append the name to `SHEETS` in `firmware/tools/spritesheets.py`, then `python3 firmware/tools/gen_params.py presets/1.json` (embeds both heights in `firmware/src/gen/sprites_gen.h`).

## 4. Verify

```bash
cd sim && npx vite --port 5173 &   # if not already running
~/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome --headless=new --no-sandbox \
  --window-size=1200,700 --screenshot=/tmp/claude-1000/shot.png \
  "http://localhost:5173/?p.digitFont=<N>&p.digitScaleX=3&p.digitScaleY=2.6"
```
Add `board=lcd316&res=320w10-8-6&tubes=3` to see the 100-row cut (`board=amoled191` to go back).
Read the screenshot. Greyscale sheets can be recoloured with `p.digitTint=%23cd7f32&p.digitTintAmount=1` — prefer a neutral steel-style sheet + tint over generating every colour variant. Dark sheets (oxidised copper) may need `brightness` up.

## 5. Commit

`git add images/digits sim/public/assets sim/src firmware/tools firmware/src/gen docs && git commit -m "<style> digit sprite font"`.

Hardware note: the firmware embeds the same sheets and box-filters them on the device exactly as the sim does, so any sheet that works in the sim works on the board. Source sheets need glyphs at least ~2x the largest cell height (200 px+).
