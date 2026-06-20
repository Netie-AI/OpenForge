# OpenForge — Parking lot (deferred workstreams)

**Purpose:** Capture good ideas without stacking them on an unverified base.  
**Rule:** One item = one focused session with its own verification gate.  
**Updated:** 2026-06-20

**How to use external advice (ChatGPT, papers, surveys):** Strip the drama (“you’re missing everything”). If the technical point is real, add **one line here** with phase mapping. If it’s already in `AGENT_PLAN.md` / `STATUS.md`, **do not re-start** — link only.

---

## Do next (sequenced)

| # | Workstream | Gate before starting |
|---|------------|----------------------|
| 1 | **BSIM CI proof via PR** | `85a8d51` pushed (`ef43ef6` + doc sync); local BSIM smoke **5/5** at HEAD; branch still has **0** PR workflow runs. Open [compare → PR](https://github.com/Netie-AI/OpenForge/compare/main...feat/schematic-orthogonal-router) and capture green `sky130-bsim-smoke` Actions URL in `STATUS.md` |
| 2 | **CMRR fixture equivalence evidence** | Tail/bias sweep done (`diag_opamp_cmrr_breakdown.py`); Lb strongest causal knob. **Hold** production-fixture decision. RL=10k diagnostic only until datasheet-equivalence proven |
| 3 | **Schematic tangling reduction follow-up** | `tail_aligned` variant landed (`nb` span 300→174); next: Cc passive tap routing second pass to drive `crossing_score` from 6 toward `<=3`; keep `route_nets()` + connectivity 14/14 green |

**First metric when PVT starts (2026-06-20):** **PSRR** — ✅ landed (`scripts/verify_psrr.py`, `STATUS.md`). **CMRR** is `partial`: normalization corrected and RL fixture sanity run, but datasheet-equivalence remains unverified.

---

## Out of scope — different discipline / multi-year / possibly separate project

**Do not treat as OpenForge near-term work.** Captured so memos do not get re-litigated each session.

High-speed mixed-signal (RF/datacom) is a **different specialty** from precision analog (opamp, comparator, LDO, vref, switch). Requires its own PDK corners, channel models, and signoff — not a Phase 4 stretch goal.

| Topic | Why not now |
|-------|-------------|
| **PLL / VCO / CDR** | Multi-block system (PD, CP, LF, VCO, divider); jitter/phase noise are their own discipline |
| **SerDes, CTLE, DFE, eye diagrams, BER** | High-speed IO — years out; no silicon, no channel models |
| **Standard cells / digital P&R** | Digital flow (Yosys, lambdapdk, ChipAgents) — **different project** from transistor-level analog forge |
| **Agent swarm** (Orchestrator → Circuit/Layout/Test/Silicon) | End-state platform pattern — study in `docs/research/AGENTIC_EDA_SURVEY.md`; one forge loop still being proven |
| **Post-silicon HIL** (PyVISA, BERT, VNA, lab automation) | No tapeout, no silicon — post-fab characterization, past current roadmap |
| **Vision OCR → netlist → training corpus** | Schematic images are lossy renderings; conflicts with fitness=1 / simulation-validated corpus only. Curated **text** principles (semicon-log, design rules) — yes; vision-extracted connectivity — **never** |

**Correct near-term expansion after Phase 3:** PVT corners + named testbench metrics (PSRR/CMRR/THD/noise) — already in “Deferred — simulation” below; buildable in weeks on existing ngspice path.

---

## Already true (do not treat as discoveries)

| Claim from generic roadmaps | OpenForge reality |
|-----------------------------|-------------------|
| “Need real PDK / BSIM, not level-1 only” | **Phase 3 in progress** — SKY130 BSIM opamp/switch closed locally; CI workflow wired (`sky130-bsim-smoke`), awaiting first green pushed-HEAD proof in `STATUS.md` |
| “Need verify loop / fitness toward spec” | **Forge + ngspice + `spec_envelopes.py`** — sizing loop exists; Phase 4 adds topology mutation |
| “Need layout → DRC → LVS → PEX” | **North star** in `AGENT_PLAN.md` / `HANDOFF.md` — explicitly after Phase 1–3 |
| “Stop UI, focus core only” | **UI has surfaced real bugs** (M2 anchor, IO stub gap, connectivity verifier gaps) — keep as diagnostic, not primary sprint |
| “Replace analog engineer in one month” | **Retire that framing** — multi-year problem; project maps phases with evidence per gate |

---

## Deferred — simulation / testbench metrics

Named targets to add **when category benches exist** — not new roadmap, just explicit line items.

| Metric | Bench sketch | Categories | Phase | After |
|--------|--------------|------------|-------|-------|
| **PSRR** | Small ripple on `VDD`, AC measure `Vout/VDD` at 100 Hz | opamp, ldo, vref | 3-tail | ✅ bench in `verify_psrr.py`; **not in fitness gate**; opamp gap vs RS321 85 dB |
| **CMRR** | Common-mode step or AC on both inputs; measure differential rejection | opamp, comparator | 3-tail | opamp AC bench solid |
| **THD / SFDR** | Sinusoidal input, `.fft` or harmonic power ratio | opamp, multiplier (if productized) | 4+ | linearity spec in envelope |
| **Line / load regulation** | Already partial (LDO/vref); unify reporting in compliance table | ldo, vref | 3 | vref iq |
| **Settling / overshoot** | Step response metrics beyond tp (comparator) or slewrate (opamp) | comparator, opamp | 3-tail | fixture sanity in STATUS |
| **Noise** (integrated) | `.noise` at output, band-limited | opamp, vref | 5+ | when spec envelopes ask for it |

Cross-ref: `openanalog/forge/spec_envelopes.py`, per-topology `.tran`/`.ac` in `openanalog/forge/topologies/`.

---

## Deferred — PVT, corners, Monte Carlo

| Item | Notes | Phase | After |
|------|-------|-------|-------|
| **Process corners** | TT / FF / SS / FS / SF — requires corner model decks or SKY130 corner flow, not bundled L1 | 3–4 | BSIM CI green; single-corner categories closed |
| **Temperature sweep** | −40 / 27 / 125 °C (or envelope min/max) on key specs | 3–4 | corner models or `.temp` sweep defined |
| **Monte Carlo mismatch** | W/L/ΔVth variation — ngspice `.mc` or scripted param scatter; report yield % to spec | 4+ | single-corner + temp stable |
| **Corner-aware sizing** | Sizer optimizes worst-corner or min-yield, not TT-only | 4+ | MC infrastructure |
| **Layout-induced variation** | Matching variance from placement — **needs layout** | 7+ | auto-layout or handoff GDS; pilot survey: `docs/research/GENERATIVE_ANALOG_LAYOUT_SURVEY.md` |

Survey note: ASO.ai-style multi-corner RL sizing optimizes **existing** schematics — different claim from OpenForge topology+spec generation (`docs/research/AGENTIC_EDA_SURVEY.md`).

---

## Deferred — layout / matching / PEX

**Survey (2026-06-20):** `docs/research/GENERATIVE_ANALOG_LAYOUT_SURVEY.md` — ALIGN, MAGICAL, OpenFASOC, BAG3++, OpenLane layer map; SerDes/HBM explicitly out of scope. **No integration until** BSIM CI PR proof + single-block pilot gate.

| Item | Notes | Phase | After |
|------|-------|-------|-------|
| **Common-centroid / interdigitation** | Diff pair, current mirror matching rules in docs + future placer | layout | schematic + netlist gates closed |
| **Symmetry constraints** | Mirror axis for matched devices | layout | floorplan symmetry already in schematic |
| **Guard rings / isolation** | Analog guard around sensitive blocks | layout | PDK DRC rules available |
| **Parasitic extraction (PEX)** | Quantus/Calibre-class R+C back-annotation | 7–8 | layout + DRC |
| **Layout-vs-schematic (LVS)** | Netlist ↔ GDS equivalence | 7–8 | layout |
| **DRC** | Foundry rule deck on generated layout | 7–8 | layout |
| **ESD / OPC** | Productization hardening | 8+ | north star |

Design-rule intuition (no employer IP): `docs/analog_design_rules.md`.

---

## Deferred — architecture / system-level

| Item | Notes | Phase | After |
|------|-------|-------|-------|
| **Building-block composition** | Charge pump + LDO + ref as system, not single block | 6 (AGENT_PLAN tail) | Phase 4 topology engine |
| **Hierarchy in netlist** | Subcircuit reuse, parameterized blocks | 4–6 | forge emits variants reliably |
| **System spec decomposition** | Top-level spec → block budgets (gain budget, noise budget) | 6+ | multiple `working` categories |
| **Assisted edit → re-classify** | “Add cascode” → new topology class + re-sim (CEO vision) | UI + forge | assisted edit wired |

Functional equivalent of “Gym / RL reward”: **`score_design` + `meets_all` + budget** — already the forge loop; Phase 4 adds **structure** mutation, not just params.

---

## Deferred — forge / verification (netlist + `.op`)

| Item | Notes | After |
|------|-------|-------|
| Min/typical/max range checking | Datasheet specs are bands, not just floors | vref iq closed |
| KCL at `.op` | Sum node currents from ngspice `.op`; flag \|ΣI\| > tol | vref iq |
| Device operating-region check | Saturation/linear/cutoff per FET at bias point | KCL or parallel |
| BSIM / SKY130 **CI** hardening | Local 5/5 smoke exists; GitHub Actions now includes `sky130-bsim-smoke` — record first green pushed-HEAD run URL in `STATUS.md` | vref iq |

---

## Deferred — schematic / EDA

| Item | Notes | After |
|------|-------|-------|
| Gate-stub-then-fold implementation | `_terminal_stub()` in layout + verifier assertion | UI E2E green |
| Schematic aesthetic regression test | Structural check beyond 0.7 connectivity | stub-then-fold |
| KiCad export polish | Footprint/symbol consistency | low priority |
| DRC/LVS **prediction** UI | Needs layout layer first | Phase 7+ |

---

## Deferred — UI / product

| Item | Notes | After |
|------|-------|-------|
| Restore preset verify path (optional) | Backend `/api/verify` exists; UI removed preset picker intentionally | UI stable |
| Assisted edit loop | NL edit → re-sim → new topology class | forge stable |
| Palantir theme iteration | Done once; avoid churn without E2E gate | UI E2E green |
| **UI as regression gate** | Any `index.html` change → `docs/UI_E2E_CHECKLIST.md` | ongoing discipline |

---

## Deferred — Cursor / tooling (own session each)

| Item | Notes | Do not |
|------|-------|--------|
| OpenForge Cursor skills/rules hardening | Owner-managed only (`.cursor/agents`, `.cursor/rules`, `.cursor/skills`); assistants treat as read-only unless explicitly requested by owner. Maintain `.cursor/rules/mode-routing-and-collab-gates.mdc` + `.cursor/skills/mode-routing/SKILL.md` | Mix with schematic edits |
| Global skills across 4 repos | OpenForge, OpenHBM, NVMe Sentinel, OpenMiddleware — **no context on other three yet** | Guess cross-repo rules |
| MCP automation setup | Subagents, parallel runners, CI hooks | Half-attentive config |
| Semiconductor skill / “Cursor brain” | Dedicated authoring + eval | Stack on open gates |
| Fine-tuned agent / N parallel subagents | Infrastructure project | Stack on vref iq |

---

## Deferred — north star (explicitly not now)

- Autonomous layout compiler (Stage-3 “final frontier” in generic roadmaps)
- World model for silicon / predictive signoff
- Multitask LoRA on fitness=1 corpus only (`AGENT_PLAN.md` Phase 5)
- Advanced-node PDK integration survey → action (`docs/research/ADVANCED_NODE_SURVEY.md`)

---

## Reading list (textbook content — no project gap implied)

Useful glossary only; **does not change sequencing above.**

- Layout-induced performance (routing, matching, guard)
- BSIM4 vs level-1 limitations (project already tracks both paths)
- PVT / mismatch statistics
- PSRR, CMRR, THD as product metrics
- System-level partitioning and spec budgeting

Paper in inbox: `papers/inbox/2407.18272v1.pdf` — ingest when Phase 2 PDF pipeline is the active task, not as a side quest.

---

## Session discipline reminder

> Passing unit tests ≠ the product works.  
> UI corruption (2026-06-19) came from rapid iteration without browser check.  
> **Green test + you opened the page** = minimum bar for “done.”

See also: `docs/HANDOFF.md`, `docs/STATUS.md`, `docs/analog_design_rules.md`, `AGENT_PLAN.md`, `.cursor/skills/openforge-conventions/SKILL.md`.
