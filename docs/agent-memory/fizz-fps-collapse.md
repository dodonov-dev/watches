---
name: fizz-fps-collapse
description: "2026-10-02 — board fps drops to 5–12 came from the spring-fizz pool filling up (pitching with across ~0), not from render; fixed by capping spring births at the fizzCount share, floor now 21–25 fps"
metadata:
  node_type: memory
  type: project
  originSessionId: 3cd654f2-4248-4043-a259-b6cf5e37143f
  modified: 2026-10-02T12:04:06.211Z
---

Board fps collapse (30 → 10–12, floor ~5) with a spring-fizz preset (`fizzSource 1`, `fizzSourceRate 5`) in
vertical mode was the fizz physics, not the renderer. Chain: the spring emitted at its rate whatever the tube
held; bubbles only leave through a surface they drift to or the bore wall, so pitching back and forth with
across ~0 (the vertical watch's nominal plane) let none out — a tilt flip releases parked foam and the next
park gives it a fresh life — and the pool filled to `MAX_FIZZ` 240 per tube in ~40 s; `stepFizz` costs
~15 µs per free bubble per step and `settleFoam` is quadratic in parked foam (124 parked ≈ 8 ms, 200 ≈
20–30 ms a step); `liquid_tick` runs it once per 50 Hz catch-up step, up to 5 a frame, so a slow step feeds
back (steps pinned at 5.00 = the 10 fps plateau). With across ≥ 0.1 the pool stays ~35 per tube.

Fix applied 2026-10-02 (sim + firmware, uncommitted at the time): spring births wait once the tube holds its
`fizzCount × len/L` share (`fizzWant`, foam included, one birth of credit kept). Same swing afterwards:
21–25 fps, steps ≤ 2.3, recovery < 7 s. `fizzCount` now matters for spring presets (spring-pearls gas went
12 → 64 to keep its look). Fable and Astra both reviewed: cap first; Astra advised against the per-frame
`stepFizz` call (changes foam relaxation and let-go statistics), and the `settleFoam` early-out is unsafe on
live distances (packing moves bubbles after the sort).

**Why:** the user reported "sometimes when tilting" drops to 10–12 fps; static poses and bench.py's pinned
scene never show it because the pool takes tens of seconds of reversing drift to fill.

**How to apply:** for any fps complaint read the `f` breakdown first (`phys N steps x (tube + fizz ms)`,
`fizz live (foam, slots)`) and reproduce with `tools/tilt.py --hold 60 '-1,0>0.6,0@3'` (see
[[firmware-e2e-tooling]]). Remaining cost at the cap (~210 live: render +10 ms, fizz 3–4 ms × 2.2 steps) and
the other candidates are in KAIZEN "Fizz fps collapse". `fizz=0` does not stop `stepFizz`, so it is not a
clean control. Model changes go to both sides ([[params-mirror-firmware]], [[presets-disposable]]).
