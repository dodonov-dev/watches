# Edge shade: make it (nearly) free by folding it into existing computation

Worktree: /home/andrey/_PROJECTS/watches-edge-shade (branch edge-shade, HEAD 6df29da). Work only there; never touch
/home/andrey/_PROJECTS/watches. Rules: CLAUDE.md / AGENTS.md (static/boot memory only; side ideas -> KAIZEN.md).
Read STATUS.md's "Edge shade" entry first: it documents the current design (per-row factor T in 1/256, applied as a
post-pass `Tube::edgeShade` / `shadeRow` via per-channel LUTs, in the tiles or after a strip lens; sim
`edgeShadeRows` / `applyEdgeShade`).

Problem: on the board it costs 2.9 ms/frame (51.1 -> 45.4 fps, fixed pose, edge 0.6/1.4/1.9) and the user now uses
a wider band: edgeShade 0.67, From 1.15, To 2.85 (look saved at
/tmp/claude-1000/-home-andrey--PROJECTS-watches/6b36e029-86b5-44da-bf6a-b636a5744698/scratchpad/board-look-1120.json),
so more rows are shaded. The user asks: why does it need that much, can't the coefficient be woven into existing
calculations by distance from the centre?

Step 1, measure (board: /dev/ttyACM0 or ACM1, firmware-e2e skill, bench.py --fix-pose --stage, one bench at a
time): cost at the user's settings, and where it goes (pixels shaded per frame, ns/px, internal vs PSRAM strip,
tile vs strip path). Explain the number.

Step 2, fold: the darkening is linear, so shade(blend(a, b, t)) ~= blend(shade(a), shade(b), t). Apply the row
factor where per-row colours are already produced instead of re-touching every pixel afterwards: the palette rows
(back / liquid / wall / rim per row, built at param change in the row cache), the per-row colours of marks (ticks,
digits, shadows), fizz, meniscus/surface, residue, glow... Find every producer of colour in a tube row; anything
that writes a colour not derived from a per-row-shaded source needs its own per-row factor (often already a per-row
table nearby). Lens: shading is defined on SHOWN rows; with the nearest-row lens a drawn row may feed several shown
rows (STATUS: `shadeSrc` handles conflicts) — keep a correct path for that case (the existing post-pass is an
acceptable fallback only there). Goal: shade cost ~0 at edgeShade > 0 on the user's look, and per-frame cost
unchanged at 0.
Exactness: the result may differ from the current post-pass by rounding (the sim changes the same way: the sim and
firmware must stay at 0 px > 12/255, ideally byte-equal on the host checks). edgeShade 0 must stay byte-identical
to HEAD (check_render_frames, check_board_render, check_fizz_steps as before).

Step 3, verify: host checks as in the previous round (lcd316 320w8-8 strip/--tiles/--tiles --push-lens, 240f,
amoled191, check:layout, sim build/checks), flash the board (if it stays in download mode:
`~/.platformio/penv/bin/python ~/.platformio/packages-lcd316/tool-esptoolpy/esptool.py --port <p> --before no-reset
--after watchdog-reset chip-id`; flash builds need PLATFORMIO_PACKAGES_DIR=~/.platformio/packages-lcd316, flash.sh
sets it), restore the user's look from board-look-1120.json if NVS is dropped (scratchpad restore.py), bench
fixed-pose off vs the user's settings, compare-device. Leave the board on the user's look (edge 0.67/1.15/2.85).

Deliver: commit(s) in the worktree (trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`), STATUS.md
updated; report: the cost explanation, the design, verbatim check numbers, fps before/after. Do not push.
