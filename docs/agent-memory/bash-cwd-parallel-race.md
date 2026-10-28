---
name: bash-cwd-parallel-race
description: "Parallel Bash calls share one shell cwd; a `cd` in one call breaks relative paths in the other (shot.mjs, KAIZEN.md writes failed this way)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 638ffd7d-d591-4f8e-9f7a-6a4f72eb0a79
  modified: 2026-09-22T13:11:46.349Z
---

Two Bash tool calls issued in the same response run in the same shell, and the working directory
persists between calls. A `cd sim` in one call made the other resolve `../.claude/skills/run-sim/shot.mjs`
and `KAIZEN.md` against the wrong directory (2026-09-22, meniscus session): "Cannot find module",
FileNotFoundError, and a python patch script that silently wrote nothing.

**Why:** the failures looked like missing files, not like a race, and cost several retries.
**How to apply:** in this repo use absolute paths everywhere, and when a tool needs a specific cwd
(run-sim's shot.mjs imports playwright from `process.cwd()`), wrap it in a subshell:
`(cd /home/andrey/_PROJECTS/watches/sim && node /abs/path/shot.mjs ...)`. Never rely on the cwd a
previous call left behind. Related: [[image-gen-lanes]] (shot.mjs lives in .claude/skills/run-sim).
