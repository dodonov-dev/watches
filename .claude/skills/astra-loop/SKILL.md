---
name: astra-loop
description: Multi-model delivery loop for a sizeable task — Fable orchestrates, Astra (GPT-6 via cli-proxy) structures and reviews, Opus implements well-specified points and runs all tests. Use when the user hands over a feature or refactor bigger than a few edits and wants it driven to "all points settled" with block-level review, not per-point polling.
---

# Astra loop

Session must run via `claude-proxy` (cli-proxy-api on :8317); the `astra` agent in
`.claude/agents/astra.md` is `model: gpt-6.2-astra` and only resolves through the proxy.
Not proxied → say so and fall back to `pigeon_drop/tools/codex-run.sh -m gpt-6.2-astra`.

Roles, fixed:
- **Fable (you)**: intent, routing, taste and visual calls, adjustments after review.
- **Astra**: structure once, review per block. Read-only. One agent for the whole task,
  continued with SendMessage so it keeps the plan and prior verdicts.
- **Opus** (`Agent`, `model: opus`): implementation from a crisp spec; all testing
  (check scripts, sim screenshots via `run-sim`, board e2e via `firmware-e2e`).

## Protocol

1. **Brief**: write `<scratchpad>/brief.md` — goal, constraints, and what you know from
   the conversation that Astra cannot see. Include memory facts that apply.
2. **Structure**: spawn `astra` with the brief; it returns a numbered plan. Save it to
   `<scratchpad>/plan.md` with a status column (`open` / `done` / `settled`). Keep the
   agent id.
3. **Route**: tag each point `fable` (visual, ambiguous, tuned constants) or `opus`
   (well-specified). Bulk mechanical edits may go to codex-sol via `codex-code`. Group
   points into blocks of 2–5 that make sense to review together.
4. **Block**: implement, then an Opus agent runs the checks for every point in the
   block and reports verbatim results. Do not review a block that has not passed.
5. **Review**: SendMessage the same `astra` agent with the point numbers and the diff
   range (`git diff <base>..HEAD -- <paths>`). It answers per point: settled / issue.
6. **Adjust**: fix or route each issue, Opus re-tests. Re-review only if any issue was
   substantive (logic, constraint violation), not for one-line fixes you verified.
   Two rounds per block max; a third disagreement goes to the user with both positions.
7. Mark points `settled` in `plan.md`. Next block. Stop when every point is settled and
   report the plan with statuses.

## Rules

- Astra sees diffs and the plan, never whole-repo dumps: no prompt caching through the
  proxy, Codex quota burns per token.
- Astra's verdict is a review, not an order. Where it conflicts with a screenshot or a
  measured number, evidence wins; say so in the reply to it.
- Ideas outside the plan go to `KAIZEN.md`, one line each.
