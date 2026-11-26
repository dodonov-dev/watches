No critical or high issues found.

- **Medium — [firmware/src/render.cpp:6697](/home/aadod/_PROJECTS/watches/firmware/src/render.cpp:6697): recycled slots can inherit another bubble’s lighting.** Birth/respawn paths never invalidate the memo; checking only axial movement misses replacements at similar x but different depth. Reproduced with slot 0, `mm.frame=5`, `litFrame=6`, `x=50`, `R=20`, `r=3`, `y=0`, transparency `0.01`, tone `-1`, fizzPhys `1`: replacing depth `z=+17` with `z=-17` retains `K=0.708968` (ring level 5), versus the correct `K=0.0141331` (level 0). This can persist for up to three frames. **Smallest fix:** set the slot’s `litMemo.frame=0` on every birth/respawn, including reused slots when `fizzN` grows again.
---
Follow-up (Fable, 2026-11-26): fixed in 7a7ff07 by the memo's place (x, y, z; retaken > 6 px along or > 2 px across / in
depth), not by birth hooks in the stepper. A confirming pass was started and died mid-run ("Your workspace is out of
credits"); it was building cases for a rebirth of another radius inside that box and a geometry change between frames.
Both are handled in the next commit (the memo keeps r; a change of liquid / bore / tone / lid / end ages every memo at
once). That delta has no Astra review.
