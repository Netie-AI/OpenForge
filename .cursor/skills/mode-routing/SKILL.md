---
name: mode-routing
description: Route OpenForge orchestration by parent model mode (composer-collab vs cursor-only) and enforce the correct gate/report flow. Use when planning subagent invocation order, model choice, and verification handoff.
disable-model-invocation: true
---

# Mode Routing

Use this skill when deciding how to orchestrate subagents.

## Decide mode first

1. **Composer mode**
   - Use `composer-2.5-fast` for subagents by default.
   - Required flow: propose/research -> execute -> `dv-verifier` (blocking) -> parent re-run -> Claude verification before gate progression.

2. **Cursor-only mode (non-composer parent)**
   - Subagents inherit parent model unless explicitly overridden.
   - Required flow: execute -> `dv-verifier` (blocking) -> parent re-run.
   - Claude verification optional unless user asks.

## Gate-critical checklist

Treat as gate-critical if the task changes phase/gate claims, updates `docs/STATUS.md`, relies on `meets_all`, or introduces acceptance testbench metrics.

## Invocation defaults

- Read-only parallel streams: `analog-research`, `analog-design-lead`, `chief-architect`, `semiconductor-eda-engineer`, `layout-pex-lead`
- Single writer stream: `cursor-executor`
- Blocking verifier: `dv-verifier`
- Optional pre-filter: `local-reviewer`
- Learning capture: `session-scribe` to `docs/research/testbench_learnings/`

## Required outputs

- Executor/verifier: Evidence Bundle with verbatim output **plus** a **Why / thought process** block (1–3 sentences: approach vs alternatives, tradeoff, what to reconsider if wrong).
- Proposers/reviewers: OF-C2C reviewer format.
- Missing checks: explicit `not verified`.
