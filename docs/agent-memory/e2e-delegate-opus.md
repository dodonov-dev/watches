---
name: e2e-delegate-opus
description: Run firmware e2e verification (flash/bench/parity) via a cheaper Opus subagent, not the main model
metadata:
  type: feedback
---

Delegate mechanical firmware verification — `tools/e2e.sh`, bench re-runs, parity sweeps, boot-banner
captures — to an Opus subagent (`Agent` with `model: opus`) and only read back the result lines.

**Why:** the user said (2026-08-27) "e2e verification can be done with cheaper Opus agent"; the runs are
2–5 min of waiting with a fixed script and a small verbatim result.
**How to apply:** give the agent the exact command(s), the reset snippet for a silent board, and ask for the
bench line / stage table / mismatch line verbatim. See [[firmware-e2e-tooling]].
