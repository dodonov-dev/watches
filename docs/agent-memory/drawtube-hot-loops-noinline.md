---
name: drawtube-hot-loops-noinline
description: Per-pixel loops inside Tube::drawTube spill registers every iteration; hoisting a hot loop into a small noinline function with an exact 2-lane 565 blend cut the dried-trace pass 17.8 -> 5.7 ms (2026-09-22)
metadata: 
  node_type: memory
  type: project
  originSessionId: 85ea2863-a144-47de-9c43-67f448331f56
  modified: 2026-09-22T09:19:55.413Z
---

Tube::drawTube (firmware/src/render.cpp) is ~300 lines with hundreds of live locals, so any per-pixel
loop written inline there spills to the stack on every iteration (seen in the xtensa objdump: s32i/l32i
to a1 inside the loop, l32r constants reloaded). Moving the dried-trace plain fill into
`traceFillRow` (noinline, byte-swapped-layout blend, r/b as two 16-bit lanes of one uint32) took a fully
smeared tube from 17.8 ms to 5.7 ms; the lane blend alone (still inline) only reached 8.5 ms.
The blend path itself is ~57 cycles/px (a uniform thin film over a fully dry tube costs ~9 ms); the
5.7 ms figure included the opaque T>=256 fast path of heavy residue. A later rewrite (a<<8)+(b-a)*T with
unsigned lane wrap and a parallel 5->8 bit expansion cut the partial-alpha loop 55->47 instructions (film
over a dry tube 9.1 -> 7.9 ms); firmware/tools/check_residue.py re-proves bit-exactness on the host.

**Why:** the compiler cannot allocate registers well across a giant function; the same 30 ops run ~2x
faster in their own register window. The lane formula floor((a(256-T)+bT+128)/256) is bit-identical to
blend565T's a+(((b-a)T+128)>>8), so sim parity is untouched (verified exhaustively on the host).
**How to apply:** for the next per-pixel stage cost in drawTube (glow, glass, digits behind liquid),
first try extracting the inner loop into a noinline helper and check the disassembly for spills before
changing the math. Measure with a pinned residue scene (traceDry pinned high, d60 drain, then d0; see
KAIZEN). Related: [[firmware-e2e-tooling]], [[perf-plan-after-handoff-2]].
