---
name: openforge-cursor-conventions
description: >-
  OpenForge Cursor project conventions — evidence gatekeeping, handoff anchoring,
  and phase-status discipline. Cursor agents should read this at session start or
  when the user mentions handoff, STATUS.md, verification, or Claude/Cursor role split.
  This is NOT an Anthropic Claude Skill; see "What this file is" below.
---

# OpenForge — Cursor project conventions

## What this file is (and is not)

This file lives at `.cursor/.skills/SKILL.md` — a **Cursor project-conventions** location, not Anthropic's Claude Skill loader.

| | This file | Anthropic skill-creator format (`.cursor/.skills/skill-creator.md`) |
|---|-----------|---------------------------------------------------------------------|
| **Purpose** | Persistent rules for Cursor agents working in OpenForge | Reusable capability Claude loads when description matches context |
| **Who reads it** | Cursor (when user/@-references it or project rules point here) | Claude's skill system via `available_skills` + description triggering |
| **Mechanism** | Instructions / rules file (like `.cursorrules` or AGENTS.md) | YAML `name`/`description` + progressive disclosure + optional eval harness |
| **Auto-trigger** | No — Cursor does not auto-invoke from description alone | Yes — description is the primary trigger signal |

The YAML frontmatter above helps **discovery and labeling** in Cursor; it does **not** register this with Claude's skill system. If the goal is "Claude consults this automatically in chat," that requires a separately authored skill in Claude's skill path — not a rename of this file.

**Reference used for structure ideas:** `.cursor/.skills/skill-creator.md` (concise body, progressive disclosure, explain-the-why). **Not implemented here:** eval harness, with-skill/baseline subagent runs, description optimization loop.

---

# Claude/Cursor Gatekeeper

Use these conventions when work is split between:

- **Claude**: reviewer, planner, diagnosis, architecture decisions, risk calls.
- **Cursor**: code execution agent, patch author, local verifier, evidence collector.

The purpose is to prevent "trust me" summaries from replacing evidence. Every claim about changed code, test results, command output, generated files, or hardware behavior must be backed by something readable: a diff, file excerpt, command output, JSON artifact, or explicit statement that it was not verified.

## Core rule

Do not treat a summary as proof. Treat proof as:

- `git diff` or pasted changed functions for code changes.
- Verbose command output for tests, mypy, ruff, CLI runs, or hardware probes.
- `results.json`, generated report paths, or file listings for produced artifacts.
- Commit hash and branch status when discussing pushed work.
- Explicit "not run" / "not verified" notes when evidence is absent.

If a prior session fabricated output, raise the evidence threshold. Do not add another unverified layer.

## Role split

### Claude reviewer/planner

Claude should:

- Review pasted diffs, changed functions, logs, and artifacts directly.
- Diagnose from evidence and label hypotheses clearly.
- Produce implementation plans with file paths, intended changes, risks, and verification gates.
- Gate acceptance: call out inconsistencies, dead code, missing tests, stale constants, or claims not supported by evidence.
- Avoid generating full patches when Cursor is available to execute, unless the user explicitly asks for code.

Claude should not:

- Say code is done without seeing a diff or file content.
- Treat "tests passed" as sufficient without command output or an artifact.
- Clone/re-test by default when the user can paste concrete evidence.
- Rewrite Cursor's job into speculative code unless asked.

### Cursor executor/verifier

Cursor should:

- Read the relevant project rules before editing.
- Execute Claude's plan conservatively in the repo.
- Make scoped patches only in the listed files unless the codebase proves another file is needed.
- Run the agreed verification gates using the project toolchain.
- Return evidence Claude can review: diff, changed functions, command output, artifacts, and remaining risks.

Cursor should not:

- Reply with "done" alone.
- Hide failed commands behind a summary.
- Claim hardware behavior from unit tests.
- Convert hypotheses into facts in handoff docs.

## Workflow

1. **Clarify the task type**

   Decide whether this is review, plan, execution, or verification. If the user asks for a plan, stay in planning. If the user says "execute what Claude says", Cursor executes and verifies.

2. **Capture the evidence packet**

   Before acting, identify what evidence exists:

   - Pasted diff or changed functions.
   - Test output.
   - Generated artifacts such as `results.json`.
   - Git status, branch, or commit hash.
   - Handoff doc entries.

   If evidence is missing, ask for it or have Cursor generate it. Do not fill gaps with confident guesses.

3. **Make a bounded plan**

   Include:

   - Files expected to change.
   - Behavior being changed.
   - Verification commands.
   - What remains hypothetical.
   - What should not be touched.

4. **Execute with local proof**

   Cursor applies the plan, then collects:

   - `git diff -- <files>`.
   - Focused test output.
   - Type/lint output if relevant.
   - Artifact paths and contents where relevant.
   - Any command that was not run and why.

5. **Review before declaring done**

   Claude or Cursor reviews the evidence for internal consistency:

   - Does the diff match the plan?
   - Are timeout constants single-source or duplicated?
   - Are tests asserting the real production path?
   - Did a renamed or removed constant leave dead code?
   - Does the handoff wording say "diagnosed", "implemented", or "hypothesis" accurately?

6. **Close with an evidence-based result**

   Final response should state:

   - What changed.
   - What passed.
   - What was not verified.
   - What follow-up remains.

## Gate levels

Use the smallest gate that proves the claim.

### Gate A: desk review

Use when only pasted evidence exists. Output should say "reviewed from pasted diff/output". Do not claim local execution.

Required evidence:

- Diff or changed functions.
- Test output if test claims are being reviewed.
- Artifact excerpts if artifact claims are being reviewed.

### Gate B: local unit verification

Use when Cursor can run tests locally without hardware.

Required evidence:

- Focused pytest output.
- mypy/ruff output when touched code is typed or style-sensitive.
- `git diff` for changed files.

### Gate C: hardware/runtime verification

Use for NVMe, GPU, driver, benchmark, or OS-storage behavior.

Required evidence:

- Exact command run.
- Full relevant stdout/stderr.
- `results.json` or generated report contents.
- Timing information when diagnosing hangs/timeouts.
- Clear note if the result is environment-specific.

## Standard evidence bundle

Cursor should paste this after executing a plan:

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
- <hardware/runtime/manual checks not run>

### Notes for Claude
- <known risks, hypotheses, inconsistencies, or review questions>
````

If the diff is too large, paste changed functions plus `git diff --stat`, then offer the full diff.

## Claude response template

Claude should answer Cursor/user evidence with:

```markdown
## Review

Findings first:
- <bug/risk/inconsistency, with file/function reference>

What looks correct:
- <evidence-backed acceptance points>

Open questions:
- <missing evidence or hypotheses>

Decision:
- Accept / accept with follow-up / needs patch / needs runtime verification

Cursor next steps:
- <exact files or commands Cursor should run>
```

If there are no findings, say that clearly and still note residual risk.

## Cursor response template

Cursor should answer Claude/user plans with:

````markdown
## Cursor Execution Result

Implemented:
- <scoped change summary>

Verification:
```text
<verbatim command output>
```

Evidence for review:
```diff
<relevant diff or changed functions>
```

Not verified:
- <anything not run>

Message for Claude:
Claude, please review the pasted diff/output only. No need to generate code or run tests unless the evidence is internally inconsistent. Cursor is the execution agent and can provide more diffs, artifacts, or command output on request.
````

## Short handoff blocks

Append one of these under plans or results.

### Message to Claude

```markdown
Claude: please act as reviewer/planner only. Do not generate code unless asked. Review the pasted diff, changed functions, command output, and artifacts. Flag unsupported claims, dead code, test gaps, or wording that turns hypotheses into facts. Tell Cursor exactly what to change or verify next.
```

### Message to Cursor

```markdown
Cursor: execute Claude's plan in the repo. Make scoped edits, run the requested gates with `uv run ...`, and paste the evidence bundle: relevant `git diff`, verbatim test/type/lint output, artifact paths or contents, and a clear "not verified" section. Do not summarize success without evidence.
```

### Message to both agents

```markdown
Shared rule: evidence beats claims. If output is not pasted, generated, or directly verified, label it as unverified. Claude reviews and plans; Cursor executes and proves.
```

## Review checklist

Before accepting a change, check:

- The diff implements the stated plan and no unrelated refactor slipped in.
- Public signatures remain typed and compatible unless a rename was explicitly approved.
- Constants and defaults have one source of truth where practical.
- Tests exercise the production path, not a dead or patched-only constant.
- Timeout wrappers kill at the real blocking boundary when possible.
- Thread wrappers are used only where no kill boundary exists.
- Handoff docs distinguish `implemented`, `diagnosed`, `hypothesis`, and `not verified`.
- Hardware claims are backed by hardware/runtime output, not unit tests.
- If a report includes both a locked smoke seed and a multi-seed sweep, the text explicitly reconciles them (for example, "smoke seed passes" versus "N/M robustness sweep passes").
- Upstream dependency claims cite direct repository evidence for node support, license, and artifact type (digital cell library vs analog/SPICE transistor-model PDK).

## Project-specific defaults for OpenForge

When working in this repo:

- Read `docs/STATUS.md` before writing phase updates; keep milestone language aligned with evidence logs under `evidence/`.
- Treat `docs/HANDOFF.md` as the master handoff anchor and update it at every meaningful checkpoint (not just at session end).
- Every handoff update must separate **short-term goal** (current phase exit gate / next concrete task) from **long-term goal** (multi-phase roadmap target) so priorities stay explicit.
- For SKY130 work, always distinguish placeholder level-1 cards from fetched BSIM models and state which path was exercised.
- For seed claims, report both the gated smoke seed result and any sweep robustness count, and reconcile them in one sentence.
- For advanced-node/PDK discussions, verify upstream README/docs directly and separate three facts: supported node list, license, and whether the artifact is usable for analog SPICE design.
- Prefer reproducible commands in docs (`make smoke-wsl`, `python scripts/verify_phase*.py`) and do not mark CI coverage for flows that the workflow does not run.

## When evidence is missing

Use this response instead of guessing:

```markdown
I cannot review that as completed yet because the evidence packet is missing <diff/output/artifact>. Cursor should provide:
- `git diff -- <files>`
- the exact command output for <tests/checks>
- `<artifact path>` or contents

Until then, treat the status as unverified.
```
