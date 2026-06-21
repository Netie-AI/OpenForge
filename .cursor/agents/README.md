# OpenForge Cursor Agents

Reusable subagent prompts for this repo.

## Operating model

- Use `dv-verifier` as the gate checker after code changes.
- Keep expert agents read-only proposers unless a human explicitly authorizes write scope.
- Use `OF-C2C-v1` from `openforge-conventions` for every cross-agent handoff.
- Mode routing:
  - **Composer parent mode:** subagents default to `composer-2.5-fast`, and gate-critical acceptance must be reviewed by Claude before proceeding.
  - **Non-composer parent mode (e.g. Codex high):** subagents inherit parent model by default; Cursor can close locally with `dv-verifier` + parent re-run evidence.
  - Any override from defaults must be logged in `docs/HANDOFF.md`.

## Default stack

1. `cursor-executor` (implement scoped patch)
2. `dv-verifier` (blocking verification gate for gate-critical checks)
3. Parent re-runs verify commands
4. `local-reviewer` optional pre-filter (not a second blocking gate)
5. `session-scribe` captures learnings for testbench/orchestration tasks

For phase-closing or high-risk changes in composer-mode, external Claude review is required before gate progression.

## Invocation matrix

| Agent | Invoke when | Parallel-safe | Blocking | Output contract | Default model |
|---|---|---|---|---|---|
| `analog-research` | Need citations/datasheet precedent | Yes | No | OF-C2C reviewer + sources | composer |
| `analog-design-lead` | Need topology/bench rationale | Yes | No | OF-C2C reviewer | composer |
| `chief-architect` | Scope jump/phase reprioritization | Yes | No | OF-C2C reviewer | composer |
| `semiconductor-eda-engineer` | Toolchain/CI/open-PDK flow choices | Yes | No | OF-C2C reviewer | composer |
| `layout-pex-lead` | Layout/PEX risk discussion while gated | Yes | No | OF-C2C reviewer | composer |
| `cursor-executor` | Scoped implementation edits | No (single writer) | No | OF-C2C executor + Evidence Bundle | inherit |
| `dv-verifier` | Gate-critical verification claims | Yes (read-only) | **Yes** | Evidence Bundle | inherit |
| `local-reviewer` | Optional local risk pre-filter | Yes (read-only) | No | OF-C2C reviewer | inherit |
| `session-scribe` | Capture learnings after verify | Yes | No | path written / blocked note | composer |
| `parallel-composer-coordinator` | Multi-stream composer orchestration | Yes (coordinator read-only) | No (but must invoke `dv-verifier`) | merged OF-C2C + gate packet | composer |

## Parallel run pattern

When work is decomposable, launch in one turn:
- `analog-research` (background) plus relevant expert proposers,
- one writing stream only (`cursor-executor`) when implementation is approved,
- then `dv-verifier` as blocking gate before any acceptance claim.
