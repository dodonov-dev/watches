---
name: plans-handed-to-agents
description: User may feed a finished plan to another agent instead of approving it here; write plans self-contained and export them under docs/
metadata:
  type: feedback
---

On 2026-09-26 the user rejected ExitPlanMode for the H573 bench plan and asked to export it to .md "I'll feed it
to another agent, after verifying that board is connected, working etc." — then asked for it under docs/
(docs/h573-bench-plan.md).

**Why:** hardware work gets handed to a fresh agent once the user has the board ready; that agent has none of
this conversation.
**How to apply:** for board / hardware plans, include hand-off notes (environment, rules, reference numbers,
pins, what is not installed) and a step-0 bring-up check; offer the docs/ export. See [[e2e-delegate-opus]].
