# Implement `edgeShadeEnd`: darker very edges falling off by side-view magnification

Worktree: /home/andrey/_PROJECTS/watches-edge-ends (branch `edge-ends`, on top of perf-cheap 5ef545f). Work only
here; never touch /home/andrey/_PROJECTS/watches or other worktrees. Rules: CLAUDE.md / AGENTS.md (static/boot memory
only; side findings -> KAIZEN.md; sim Params changes mirrored in firmware codegen, presets, NVS).
Context: docs/edge-shade-ends/SUMMARY.md, brief3.md (the design), the edge-shade sections of STATUS.md; code
firmware/src/render.cpp `Tube::buildShade` (~5351) + rod.h + tools/gen_rod_rays.py, sim/src/render.ts `edgeShadeRows`.

User's wish: the very edges of each tube really dark, then the darkness falls off quickly, following how strongly
the rod magnifies each panel row when the device is seen from the side; inward of today's grey band nothing changes.

## Phase 1 (now, before the maths spec arrives)
- New param `edgeShadeEnd` (float 0..1, default 0, UI slider next to the other edge-shade controls, help text:
  "darkness at the very edge; falls off quickly by the rod's side-view magnification"). PARAMS_VERSION bump with the
  usual migration (presets get 0), firmware codegen, NVS schema handled the way previous param additions were (check
  git log for v32/v33 how the board's blob is dropped or migrated; keep the user's look: the restore path below).
- Plumb it into buildShade / edgeShadeRows as a per-physical-row extra factor applied to the existing per-row factors
  before the physical-to-canvas averaging and lens mapping, with a placeholder weight table (all zeros) so that
  edgeShadeEnd 0 AND the placeholder are byte-identical to 5ef545f. Cache keys (RodCache etc.) must include the new
  param.
- Checks (lean, per the user's preference): sim tsc/build, check:presets, check_shade_rows (one board/res: lcd316
  320w8-8), check_render_frames strip vs 5ef545f (byte-identical at edgeShadeEnd 0). Commit.

## Phase 2 (when I send you the spec from Astra: docs/edge-shade-ends/astra-model3.md)
- Implement the exact weights / formula from the spec (generated table or closed form, sim and firmware
  bit-identical), check_shade_rows extended with edgeShadeEnd values, the spec's row tables reproduced.
- Board (lcd316@320w8-8 on /dev/ttyACM0; skill firmware-e2e; check the port is free first; the user's browser sim may
  hold it): read `p?` and save it to docs/edge-shade-ends/board-look-before.json, flash, restore the look if NVS was
  dropped (docs/edge-shade-session/restore.py <look.json> <port>, from firmware/), diff `p?`, then set edgeShadeEnd
  0.8 (keep the user's other values) and leave it there. One quick bench (pinned) to show no per-frame cost change,
  compare-device 0 px > 12/255.
- STATUS.md section, commit (trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`), do not push.
Report via SendMessage (not only SubagentHandback): what changed, checks verbatim, the row table at 0.4/3/0.4 with
edgeShadeEnd 0.5/0.8/1, board state.
