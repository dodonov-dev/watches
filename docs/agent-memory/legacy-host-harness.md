---
name: legacy-host-harness
description: The legacy firmware renderer (render.cpp + physics.cpp) compiles on the host with two stub headers; replaying sim pushes there reproduces board crashes and parity gaps without the board
metadata:
  type: project
---

firmware/src/render.cpp and physics.cpp have no Arduino dependency beyond `esp_heap_caps.h`
(`heap_caps_malloc` -> calloc) and `esp_random.h` (`esp_random` -> rand). With those two stubbed,
`g++ -I src -I ../spec` builds a host harness that starts from PRESET_DEFAULT, applies `name=value`
writes in the sim's push order (rendering + stepping physics after each), or renders one dumped
`.compare/job.json` state. Host output matched the board pixel-for-pixel (2026-09-18), so it is a
faithful stand-in: it reproduced the fizz/tubeHeight task-wdt crash and the residue clamp divergence.

**Why:** the board is often held by the browser's Web Serial session, and device.py pushes take
~1-2 s per write; the host replays 150 writes in a second.
**How to apply:** for any "push all makes the device X" or parity report, rebuild the harness
(see KAIZEN "host harness" note; sources were in the session scratchpad, not committed) before
touching the board. Related: [[firmware-e2e-tooling]], [[e2e-delegate-opus]].
