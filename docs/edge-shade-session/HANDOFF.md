# Edge shade session — handoff (2026-11-20, paused for a PC reboot)

Branch `edge-shade` (this worktree), based on desk-housing 65f0bef. Not pushed, not merged.
Frozen audit snapshot worktree: ../watches-perf-audit (detached 6df29da, read-only; remove with
`git worktree remove ../watches-perf-audit` when done).

## Where it stands
- Moiré diagnosis: the stripes are the LCD's pixel rows magnified ~1.77x by the 8 mm rod (one stripe per panel row,
  photo-stripes.png); not software-removable. Physical: matte film / Magic Tape / sanded base (air gap, no OCA), lip
  over the outer ~0.3–0.5 mm of the rod.
- Edge shade: params v30 = `edgeShade` (strength) + `edgeShadePow` (shape), rod-optics profile (TUBE_ROD_MM,
  ROD_GAP_MM 0.87, ROD_N 1.49). Folded into the colour producers (0.75–0.97 ms on the user's look, was 9.3 ms).
- Open when paused (see the last WIP commit message for what landed):
  1. Profile plateau: past the rod's fold (x 3.68 → 3.95 mm apparent on 8 mm) the rod shows inner panel rows again
     (d 1.92 → 0.9 mm) → light strip between dark fold band and dark TIR edge on the board. Fix: full depth for every
     panel row seen in the fold-back up to x_c = x_fold + 0.8·(x_tir − x_fold) (d_p ≈ 1.6 mm), ramp normalised to
     reach 1 at d_p.
  2. Astra review 4 items 1–8 (astra-review4.md).
  3. Sim view-only overlay (style.css .vial gloss 0.55 + inset shadow) reads as a light stripe over darkened edges
     (sim-edge-strips.png, left side only). Separate, view-only; not started.
- Board: lcd316@320w8-8. User's look: read `p?` (look-now.json = edgeShade 0.52, pow 1, rimLight 0.89,
  glassWallGlow 0.35 at pause time). restore.py <look.json> <port> rewrites a look and diffs `p?`
  (run from firmware/).

## Perf audits (for the user's choice; nothing implemented)
astra-audit.md (Astra) and below (Fable, condensed). Measured on the board 2026-11-20: a still board with the live
IMU costs ~1 ms render + 0.5 ms push vs inputGain 0 (53.8/52.9 vs 56.5/56.9 fps) — light-angle jitter defeats the
exact-float palette key.
Fable ranked list (hours core, estimates): keep the pre-fizz image and redraw only bubble tiles at rest (9–10 ms,
high risk); quantise what the renderer reads from physics (edges 1/16 px, light/angle with hysteresis: 1.0–1.4 ms a
tube at rest, 0.5–0.9 in motion); ramp+glow alpha from a phase table (0.5–1.0 ms); hash only possibly-changed tiles
(0.6–1.0 ms at rest); back fill only outside the solid body (0.3–0.6 ms, exact; Astra agrees); memoise per-frame
plans (0.5–0.8 ms at rest); bubble squash table (0.3–0.5 ms); band rows memo; skip frames with no physics step.
Panel refresh is 46.1 Hz: fps above that at rest is headroom, not visible.

## Backlog added (BACKLOG.md)
fps-safe param sync; physics fast-forward after a stall (main.cpp:739, up to 5x replay); fps monitoring session.
