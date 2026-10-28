---
name: judge-visuals-correctness-first
description: "When ranking generated visuals/animations, judge visual correctness and recognisability before richness"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 5f11e290-6d9f-4157-b60b-9b9ed7090288
  modified: 2026-10-01T15:00:47.493Z
---

Rank generated visuals (animations, renders, model-bench pages) by visual correctness first: containment (stays inside its vessel, enters/exits at openings), continuity (amount conserved, no cross-fade ghosts, duplicates, blank frames), the subject reading as what it should be (does the cat look like a cat), and smooth motion (measure real fps — heavy canvases stutter). Richness/polish only breaks ties; simple-but-correct beats rich-but-flawed.

**Why:** 2026-10-01 liquid-cat bench — user rejected a richness-led ranking ("you ranked by richness, but not by correctness... at all"), noted Grok's cat didn't look like a cat and twitched, and moved simple claude-fable-5-1 into the top tier.

**How to apply:** film enough frames around the key transition (not 4 s apart), check each criterion explicitly, measure fps one page at a time, then rank.
