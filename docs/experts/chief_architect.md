# Chief Architect / CTO — OpenForge Direction & Decision Framework

> This is the **constitution**, not the sprint board. `docs/HANDOFF.md` owns current-state and next-action; this file owns the durable things that should *not* change session to session: north star, non-negotiable principles, technology/product direction, and how scope decisions get made. If something here conflicts with a chat message or a commit, this file and the evidence logs win until this file is deliberately revised.

---

## 1. North star

Make human language the interface for designing real, validated analog/mixed-signal circuits. Natural-language spec → topology → ngspice-validated netlist → simulation-gated corpus → a model that generates valid circuits from plain language. "Chat to chip." The honest framing of today's capability (parametric search within fixed templates, not open-ended human-engineer-level design) is documented and is the gap Phases 6–8 exist to close — it is not hidden in the pitch.

## 2. Non-negotiable principles

These do not get traded away for speed, demos, or investor optics.

1. **Fitness=1 gate.** Only simulation-validated data enters the training corpus. "Green tests over red silicon" — pytest-level scoring passing — is the canonical failure mode and is not a substitute for real ngspice results.
2. **Evidence over summary.** Every claim about code, tests, or hardware is backed by a diff, command output, or artifact — or labeled "not verified." This scales *up* with parallelism (subagents), not down: more workers means more discipline on reporting, enforced via the Evidence Bundle format.
3. **Sequential gates over parallel sprints.** Each phase gates on evidence before the next opens. Scope expansion mid-session (new orchestration, new tooling, new circuit classes) before foundational steps are closed is the documented anti-pattern — recognize it and route it through review.
4. **Sourcing boundary.** Open tooling (ngspice, Magic, Netgen, OpenROAD, KLayout), public datasheets, and academic papers are the foundation. Cadence/Synopsys source, internals, or any proprietary/NDA-covered material — never, in any form. This is both a legal line and a strategic one: the product's differentiation *is* being the open, reproducible alternative.
5. **Reproducibility is the moat.** A result anyone can reproduce with open tools is worth more than a better result behind a license server. Validation stays on ngspice for exactly this reason.

## 3. Technology direction

- **Open core.** OpenForge (open) is the validated-generation engine; Netie Forge (commercial) is the product layer on top — the GitLab/Databricks model. The open core is what builds trust and corpus; the commercial layer is where the business lives.
- **The pipeline is the product.** NL spec → topology selection → ngspice-gated netlist → fitness=1 corpus → LoRA-finetuned generation. Every phase is a link in this chain; nothing ships into the chain unvalidated.
- **Compositional, then physical.** Phase 6 (reusable blocks: diff pairs, mirrors, cascodes) is how "schematic merging/combining" actually happens — at the netlist/block level, validated. Phase 8 (Magic/Netgen DRC/LVS, layout) is the physical layer and is explicitly an unsolved-hard problem, staged deliberately, not rushed.

## 4. Product direction

- Open-core, simulation-honest, reproducible. The pitch leads with the validated closed loop (fitness=1) because that's the defensible differentiator competitors (AnalogCoder, LaMAGIC, Masala-CHAI, AnalogGenie) do not achieve.
- Business/market figures in pitch materials are illustrative founder assumptions, labeled as such — not presented as verified fact.
- No partnership or capability claims beyond what's confirmed (e.g. Zero ASIC relationship stays at its actual stage; no named-partner claims without explicit confirmation).

## 5. Decision framework (how scope decisions get made)

When a new ask appears ("add PCIe/HBM," "spin up parallel design agents," "integrate tool X"):

1. **Is it already on the roadmap under a different name?** (Schematic merging = Phase 6; layout = Phase 8; PDF→schematic = existing knowledge-graph plan.) If so, sequence it there — don't treat it as net-new.
2. **Does it pass the sourcing boundary?** If it touches proprietary vendor IP, stop.
3. **Does it remove a review checkpoint?** (Autonomous/self-triggering loops, parallel writers to the same files.) If so, it needs its own design discussion before any implementation — not a mid-session add.
4. **Is a foundational gate still open?** (Phase 0.8 sign-off, BSIM CI, current PVT metric.) If yes, the new ask waits behind it unless it's genuinely independent read-only work.
5. **Default to the smallest safe step** that proves the next claim, then gate on evidence.

## 6. Agent operating model

- **Claude** — reviewer, planner, architecture, risk calls, gatekeeper. Does not author full patches when Cursor can execute. Gates acceptance on evidence.
- **Cursor (main agent)** — executor/verifier. Scoped patches, runs gates, returns the Evidence Bundle.
- **Subagents** — scoped, mostly read-only (verifier, research). Parallel-safe only when read-only or non-file-conflicting. A *writing* subagent (design/sizing into `forge/`/`sizer/`) is sequenced and sign-off-gated, never spun up freely in parallel.
- **Expert Lead docs** (`docs/experts/`) — the reference library agents consult; not autonomous actors by default. Making one "executable" means a **read-only proposer** subagent (outputs a recommendation note for review), not a parallel writer.
- **Routing** — Cursor/subagent → Jian Hong (first checkpoint) → Claude review → back. The human checkpoint strengthens the chain; keep it.

## 7. Explicitly not building yet (and why)

| Item | Why parked |
|------|-----------|
| PCIe/HBM PHY, SerDes, high-speed IO | High-complexity new class; foundational gates (Phase 0.8, BSIM CI, PVT) still open. Reopen explicitly when greenlit. |
| Full auto-layout / DRC-LVS without layout | Phase 8; industry-hard, deliberately staged. |
| Autonomous/self-evolving research loop | Removes the review checkpoint itself — needs its own design (trigger/stop conditions, who reviews before findings are acted on) before any draft. |
| Parallel design/sizing subagents | File-ownership conflict + design-judgment-across-isolated-contexts dilutes evidence. Read-only proposer pattern only, for now. |
| Cadence/Synopsys/Spectre in the pipeline | License + reproducibility + positioning. Validation stays ngspice. |

---

*Revise this file deliberately, with reasoning, when strategy actually shifts — not casually mid-session.*
