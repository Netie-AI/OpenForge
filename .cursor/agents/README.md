# OpenForge Cursor Agents

Reusable subagent prompts for this repo.

## Operating model

- Use `dv-verifier` as the gate checker after code changes.
- Keep expert agents read-only proposers unless a human explicitly authorizes write scope.
- Use `OF-C2C-v1` from `openforge-conventions` for every cross-agent handoff.
- Speed profile: **all subagents default to `composer-2.5-fast`**, including `cursor-executor` and blocking `dv-verifier`. Parent re-runs verify after subagents. Optional `local-reviewer` is not a second gate. `session-scribe` captures learnings to `docs/research/testbench_learnings/`.

## Recommended order in a typical change

1. `cursor-executor` (implement scoped patch)
2. `dv-verifier` (blocking verification gate for gate-critical checks)
3. `local-reviewer` (local pre-filter)

For phase-closing or high-risk changes, escalate final acceptance to the external Claude review step; do not treat `local-reviewer` as a substitute for that gate.

## Parallel run pattern

When work is decomposable, launch these in one turn in parallel:

- `analog-research` (background)
- one or more expert proposers (`analog-design-lead`, `chief-architect`, `semiconductor-eda-engineer`, `layout-pex-lead`)
- `cursor-executor` for scoped code tasks

Then run `dv-verifier` as blocking gate before claiming completion.
