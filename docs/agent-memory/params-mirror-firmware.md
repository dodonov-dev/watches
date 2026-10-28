---
name: params-mirror-firmware
description: "Any Params change in sim must be mirrored in firmware (gen_params.py, render.cpp, presets/1.json)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7bd1ee47-ebac-4263-9040-a9cef2aa6450
  modified: 2026-08-26T08:59:50.710Z
---

Adding/changing a field in `sim/src/params.ts` is only half the job: firmware mirrors it.

**Why:** User expects the sim and device to stay in sync; missing the firmware half was called out as inattentive.

**How to apply:** For every params change: add to `firmware/tools/gen_params.py` FIELDS, port logic in `firmware/src/render.cpp`, add key to hand-written `presets/1.json`, run `npm run dump:presets` (sim/) then `python3 firmware/tools/gen_params.py presets/1.json`, then `pio run`. Grep the whole repo, not just `sim/`.
