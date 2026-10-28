---
name: astra-via-cliproxy
description: "How to run GPT-6 Astra as an in-process Claude Code subagent through cli-proxy-api (claude-proxy wrapper, astra agent, astra-loop skill), and the caveats"
metadata:
  node_type: memory
  type: reference
  originSessionId: 1845e7ce-307a-40dd-9fe1-dd7368ef71e3
  modified: 2026-10-01T09:19:31.201Z
---

Astra = `gpt-6-astra` (OpenAI, via the user's Codex Plus OAuth). User's model calibration (2026-09-24):
Astra best at structuring and review; Fable best at intent-reading and visual detail; Opus templated
but cheap → testing and routine implementation.

Setup (2026-09-24, verified end to end with a Read tool call):
- `~/.local/bin/claude-proxy [args]` starts `~/cli-proxy/bin/cli-proxy-api` if needed and execs
  `claude` with `ANTHROPIC_BASE_URL=http://localhost:8317` + the proxy api key. The proxy routes by
  model name: `claude-*` → Claude OAuth auth file, `gpt-6-*` → Codex auth file.
- `watches/.claude/agents/astra.md`: `model: gpt-6-astra`, read-only tools, architect/reviewer prompt.
- `watches/.claude/skills/astra-loop/SKILL.md`: the protocol (brief → structure → route → block →
  Opus tests → Astra block review → adjust, 2 rounds max → settled).

Caveats:
- Whole session goes through the proxy, so the proxy's Claude OAuth must be valid
  (`cli-proxy-api -config ~/cli-proxy/config/config.yaml -claude-login`, interactive). Expired on
  2026-09-24.
- With ANTHROPIC_AUTH_TOKEN set, Claude Code disables claude.ai connectors (Claude Docs, Gmail, …).
- Claude Code warns `unrecognized_model` for gpt-6-astra and assumes a 200k window; harmless.
- The proxy's Codex auth file (`~/cli-proxy/auths/codex-*.json`) was a root-owned July copy of the Codex
  CLI login: the proxy could not rotate it and OpenAI rejected the refresh token as reused (503
  auth_unavailable on the astra agent, 2026-09-24). Fix = give the proxy its own login: move the stale
  file aside and run `cli-proxy-api -config … -codex-login` (interactive). Until then the agent-tool
  lane fails at spawn time.
- Not proxied or Codex auth broken → fall back to `pigeon_drop/tools/codex-run.sh -m gpt-6-astra`
  (session resume via -r keeps the plan). Worked as the review lane for the whole digit-perf loop:
  structure + 2 block reviews ≈ 3 Codex calls.

- 2026-10-01: proxy upgraded 7.3.16 → 8.0.8 (old binary kept as `bin/cli-proxy-api.7.3.16`;
  `~/cli-proxy/upgrade-v8.sh` = swap-with-rollback pattern). Logins now: Claude, Codex, Antigravity
  (Gemini), xAI (Grok; needed ≥8.0.8 for the pinned Grok client version). Sibling agent: `sol`
  (gpt-6.1-sol reviewer). Test a new proxy on a spare port with a config copy before swapping —
  this session's own transport runs through :8317.

**How to apply:** for a task the user wants driven through the loop, check the session is proxied
(`echo $ANTHROPIC_BASE_URL`), load `astra-loop`, spawn `astra` once and SendMessage it for reviews.
See [[e2e-delegate-opus]] for the Opus testing lane.
