---
name: openforge-conventions
description: OpenForge execution and review conventions. Use for evidence-bundle reporting, Claude-Cursor role split, and OF-C2C-v1 handoff formatting.
---

# OpenForge Conventions

Apply this skill whenever planning, execution, or verification output needs to be shared across Cursor and Claude.

## Session read order

1. `docs/HANDOFF.md`
2. `docs/STATUS.md`
3. `AGENT_PLAN.md` section 0

## Core rules

- Evidence beats claims.
- If not run, write `not verified`.
- For gate-critical checks, default `dv-verifier` to blocking mode; **parent re-runs the same verify commands** after subagent return.
- Do not soften tolerances to force pass status.
- Report locked seed and sweep robustness together when both exist.
- After testbench/orchestration work, ensure `docs/research/testbench_learnings/<metric>_<date>.md` exists (via `session-scribe` or parent).
- Load this skill at session start and before any subagent orchestration.
- User shorthand: `continue` means execute next step now; `continue and next window` means execute now and append a concise next-window run snippet.

## Gate levels (A/B/C)

- **Gate A — explore/propose**: research and design rationale only; no acceptance claims.
- **Gate B — execute/measure**: scoped implementation plus command output and diff evidence.
- **Gate C — accept/progress**: gate-critical acceptance or phase progression claim.

Gate C requires blocking `dv-verifier` + parent command re-run evidence. In composer-mode orchestration, Gate C additionally requires Claude verification before proceeding.

## Reporting matrix by mode

| Context | Minimum report |
|---|---|
| Research/proposer stream | OF-C2C findings + cited sources |
| Executor stream | OF-C2C executor format + Evidence Bundle |
| `dv-verifier` gate run | Evidence Bundle with verbatim verify output |
| Composer-mode gate close | OF-C2C package sent for Claude verification before proceed |
| Non-composer local gate close | OF-C2C + Evidence Bundle + parent re-run output (Claude optional unless requested) |

## Subagent output contracts

- Proposers/reviewers (`analog-design-lead`, `chief-architect`, `semiconductor-eda-engineer`, `layout-pex-lead`, `local-reviewer`): OF-C2C reviewer sections.
- Executor/verifier (`cursor-executor`, `dv-verifier`): full Evidence Bundle with Scope/Diff/Verification/Artifacts/Not Verified/Notes.
- Research (`analog-research`): source-cited findings and explicit open questions; no fabricated claims.
- Learning capture (`session-scribe`): writes `docs/research/testbench_learnings/*.md` and returns written path or `blocked — no evidence bundle attached`.

## OF-C2C-v1 header

```text
Protocol: OF-C2C-v1
Role: <Claude reviewer | Cursor executor>
Intent: <review | execution | clarification>
Decision: <accept | accept_with_followup | needs_patch | needs_runtime_verification | blocked>
```

## Cursor -> Claude required sections

1. Implemented
2. Verification output (verbatim)
3. Evidence for review (diff or changed functions)
4. Not verified
5. Why / thought process (1–3 sentences: approach vs alternatives, tradeoff, what to reconsider if wrong)
6. Message for Claude

## Claude -> Cursor required sections

1. Findings (highest severity first)
2. Evidence accepted
3. Missing evidence / open questions
4. Cursor next steps

## Evidence bundle template

````markdown
## Evidence Bundle

### Scope
- Changed files:
- Not changed:
- Claim being verified:

### Diff
```diff
<git diff for relevant files>
```

### Verification
```text
<verbatim command output>
```

### Artifacts
- `<path>`: <what it contains>

### Not Verified
- <checks not run>

### Notes for Claude
- <risks/questions>
````
