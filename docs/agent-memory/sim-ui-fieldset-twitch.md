---
name: sim-ui-fieldset-twitch
description: Recurring sim-UI twitch — fieldset default min-inline-size:min-content grows the box with variable-length monospace readouts; fix with min-inline-size:0 + fixed-length text
metadata: 
  node_type: memory
  type: project
  originSessionId: 71d233d8-9804-4b02-ad49-8a675e9890ea
  modified: 2026-08-20T14:55:28.374Z
---

The Liquid Watch sim's control fieldsets twitched more than once (recurred across sessions, user pointed it out 2026-08-20): any per-frame readout with variable text length (e.g. `#imuraw` showing the raw serial CSV) widens its `<fieldset>` despite `width: 340px`, because fieldsets default to `min-inline-size: min-content` and `white-space: pre`/`nowrap` makes min-content = full line length. `overflow: hidden` on the child does NOT prevent this.

**Why:** browser default UA style for fieldset, easy to reintroduce when adding new readouts.

**How to apply:** keep `min-inline-size: 0` on the `fieldset` rule in `sim/src/style.css`, and give every per-frame text readout a fixed box AND fixed-length/sign-stable formatting (pad + slice). Related: [[liquid-pinned-model]].
