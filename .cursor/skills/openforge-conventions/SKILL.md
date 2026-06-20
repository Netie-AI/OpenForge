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
5. Message for Claude

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
