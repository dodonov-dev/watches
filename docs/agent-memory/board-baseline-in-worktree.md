---
name: board-baseline-in-worktree
description: Take the pre-change board bench (e2e.sh --stages) from an isolated worktree of HEAD while the implementer edits the main checkout; link sim/node_modules for the parity step
metadata:
  node_type: memory
  type: feedback
  originSessionId: d615a746-5202-406a-b839-15570bda5b85
  modified: 2026-09-25T09:49:17.821Z
---

For a perf-budgeted render change, run the baseline `tools/e2e.sh --stages` from an Opus agent with
`isolation: "worktree"` (HEAD copy) so the flash/build never races the implementer's edits in the main
checkout. The worktree has no `sim/node_modules`, so e2e's parity step (`render-ref` via tsc) fails there:
symlink the main checkout's `sim/node_modules` for the run, or run `compare-device.py` alone afterwards.
The log lands in the worktree's `firmware/.compare/e2e.log`; copy it out before the worktree is cleaned.

**Why:** the fizz-shading loop (2026-09-25) needed a "before" fizz-stage cost; STATUS.md quoted 0.9 ms but
the board's NVS preset gave 3.59 ms, so only a same-day measurement on the same scene is a valid baseline.

**How to apply:** baseline in a worktree first, implementation in parallel, then the "after" e2e on the
main tree once the diff is final (a later source edit means re-flashing: check the file mtime against the
build start). See [[firmware-e2e-tooling]], [[e2e-delegate-opus]], [[astra-via-cliproxy]].
