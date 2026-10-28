---
name: pkill-self-match
description: "pkill -f <pattern> kills Claude's own Bash shell when the pattern is in the command line — kill by PID"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 5f11e290-6d9f-4157-b60b-9b9ed7090288
  modified: 2026-10-01T10:17:23.012Z
---

`pkill -f "<pattern>"` run from the Bash tool matches its own `bash -c '…'` wrapper (the pattern is in that command line) and kills the shell: exit 144, the rest of the command never runs. Happened 3× in one session (2026-10-01).

**Why:** lost edits/cleanups silently chained after the pkill.

**How to apply:** get PIDs first (`pgrep -f pat | grep -v $$`, or a PID recorded at launch) and `kill <pid>`; never chain other work after a `pkill -f` in the same call.
