---
name: perf-plan-after-handoff-2
description: "Decision 2026-08-27 — perf hand-off 3 (layer cache) shelved, hand-off 4 reframed as state-driven rate control; behaviour (play/carried/reading) comes first"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0666bf10-7423-4de8-96fd-4200cb8cbe5e
  modified: 2026-08-27T17:20:58.469Z
---

After hand-offs 1–2 (45.5 fps, render 13.9 ms overlapped with a 14 ms strip push), the user decided:
- **Hand-off 3 (WET/DRY layer cache) is shelved.** Its cache keys (tick parallax on edgeLight/acrossTilt,
  digit layout on acrossTilt/fillTarget, palette on light) churn every frame in motion, so worst-case frames
  get slower; fps ceiling is the push anyway; it breaks bit-exact sim parity in the meniscus band.
- **Hand-off 4 is to be redone as rate control, not pixel dirtiness:** three wearer states — *Play*
  (extreme tilt + motion: free liquid, full rate), *Carried* (arm hanging, extreme tilt, steady: slug at the
  wall, low fixed rate, fizz off; power-saving flag lowers this rate), *Reading* (arm raised, `s.reading`≈1:
  slug parked home, event-gated render). Plus windowed strip push (panel accepts 0x2A/0x2B windows).
- **Order:** implement and device-test the state logic first (pose-driven entry into sticky time without
  requiring the `readTurn` gesture, Carried state, hysteresis), then revisit power optimisation.

**Why:** power matters most in the Carried state (hours/day); the gate needs the wearer state to exist.
**How to apply:** don't propose the layer cache again; when perf comes back up, start from the state
signal and gating, keep parity bit-exact. Related: [[firmware-e2e-tooling]], [[liquid-pinned-model]].
