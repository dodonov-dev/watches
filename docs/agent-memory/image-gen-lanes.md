---
name: image-gen-lanes
description: "Three concept-art image lanes (codex, cursor agent, agy/cliproxyapi) and their exact invocations; canonical skills live in ~/_PROJECTS/pigeon_drop/.claude/skills"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 25b10ad5-d5ed-4147-947f-4c77f142a2a4
  modified: 2026-08-25T14:40:03.537Z
---

User's image-gen lanes, documented in `~/_PROJECTS/pigeon_drop/.claude/skills/{codex-image,cursor-image,agy}/SKILL.md`:
- codex: `codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox --ephemeral -C <dir> -- "Use your image generation tool… save as X.png" </dev/null` (stdin redirect required for parallel jobs).
- cursor agent (Grok): `agent -p -f --model cursor-grok-4.5-high-fast "<prompt>; save as <abs path>"`. Plentiful quota, ~30 s–2 min.
- agy (direct CLI, user's preference — not cliproxyapi): `agy --mode accept-edits --print="Use your generate_image tool … Do not run shell commands. Reply with the full saved path." </dev/null`; output lands in `~/.gemini/antigravity-cli/brain/<id>/<name>.jpg|png`, parse path from stdout and copy. Gemini image quota: ~10 renders then RESOURCE_EXHAUSTED for hours. `--dangerously-skip-permissions` is blocked by the auto-mode classifier; accept-edits suffices.
- cursor `agent -p` hung on every prompt on 2026-08-25 (user confirmed).

**How to apply:** when user says "use codex, agent and agy" for images, run all lanes in parallel via direct CLI calls; codex gives the cleanest typography, Gemini garbles sidebar text.
