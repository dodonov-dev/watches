---
name: board-checks-need-user-ready
description: "When a board test needs the user's eyes or hands, stop and ask, then act on their reply — no unattended timed sweeps/recorders"
metadata:
  node_type: memory
  type: feedback
  originSessionId: acf585aa-2e62-4187-82ef-ac5cdc4ce23b
  modified: 2026-10-27T12:29:42.482Z
---

On 2026-10-27 (LCD-3.16 bring-up) I started a 30-min IMU recorder and a timed pclk sweep in the background and
asked the user to watch/tilt meanwhile; they were away for the first and missed the second. User: "if you need
anything from me, just stop and tell so."

**Why:** the user is not always at the board; timed runs they did not see are wasted and the results ambiguous.
**How to apply:** for visual / physical checks on hardware, end the turn with one concrete ask, wait for "ready" or
their answer, then change one thing per round (e.g. set one value, ask "stable?"). See [[e2e-delegate-opus]].
