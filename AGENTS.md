# AGENTS.md

RHDH Users Agent Plugin — Agent Skills for Red Hat Developer Hub (RHDH) users, packaged as an [Agent Plugin](https://agent-plugins.org/) (`plugin.json` at the repository root). Skills follow the [Agent Skills open standard](https://agentskills.io/specification).

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- If you write 200 lines and it could be 50, rewrite it.

Bundled Python scripts should prefer the standard library. Avoid new runtime dependencies unless clearly justified.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: every changed line should trace directly to what was asked.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

Run `uv run pytest` before reporting any task complete. Do not report completion based on code existing — verify it works.

## 5. No Irreversible Commands Without Confirmation

Never force push, reset HEAD, merge branches, or run destructive commands without asking. If unsure whether a command is destructive, ask.

## 6. Learn From Corrections

If told an implementation was wrong, apply the correction and then record what went wrong so the same mistake is not repeated. Patterns and gotchas specific to this project belong in the relevant `references/` file under each skill.

---

## Available skills

User-facing skills live under `skills/`:

- `rhdh-templates` — Software Templates authoring and validation
- `skill-maker` — Create, audit, and consolidate Agent Skills
- `rhdh-upgrade-helper` — Upgrade assessment for RHDH — analyzes config files against a target release to produce a prioritized migration plan with readiness scoring

When adding a skill, update [README.md](./README.md) and keep `SKILL.md` `name` aligned with the directory name per the Agent Skills spec. Do not nest a `plugin.json` inside a skill directory; the Plugin manifest stays at the repository root.
