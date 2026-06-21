# Agentic AI in chip design — survey (pattern extraction only)

**Date:** 2026-06-19  
**Scope:** Read, distill, human decides. No integration, no new dependencies, no architecture changes triggered from this doc.

**OpenForge layer (for comparison):** spec envelope → topology param mutation → ngspice → **fitness=1 gate** → keep/discard (`openanalog/forge/`). Analog SPICE, not digital RTL.

**Already checked (not re-researched):** ChipAgents / William Wang — digital RTL/verification agent (VerilogEval-class), not analog SPICE generation. Evaluated here as **agentic workflow patterns** only.

---

## 1. Synopsys AI (`synopsys.com/ai.html`)

### What it actually is

Vendor marketing hub for **Synopsys.ai** — a portfolio spanning optimization ML, analytics, GenAI copilots, and **Agentic AI / AgentEngineer™** multi-agent workflows.

### Design stack layer

| Product line | Layer | Claimed problem |
|--------------|-------|-----------------|
| **DSO.ai**, Fusion Compiler, PrimeTime | Digital implementation & signoff | PPA closure, floorplan, timing — search huge discrete spaces |
| **VSO.ai**, VCS, Verdi | Digital verification | Coverage closure, debug, regression triage |
| **ASO.ai**, Custom Compiler, PrimeSim | **Analog/mixed-signal on existing designs** | IP migration, multi-objective **sizing**, PVT corner optimization, waveform outlier analysis |
| **AgentEngineer™** | Cross-flow orchestration | Multi-agent RTL gen, verification planning, testbench creation — **spec → RTL** under human checkpoints |
| **3DSO.ai**, Silicon.da / Fab.da | System / manufacturing | Multi-die, yield, fab analytics |

ASO.ai detail page: reinforcement learning optimizes **hierarchical schematics already drawn** across hundreds of PVT corners. SmartScaling interpolates corners from anchors. No claim of **generating novel analog topologies from a datasheet spec** with SPICE-validated pass/fail.

AgentEngineer page: L1–L5 autonomy ladder; L1–L2 ≈ assistive; L3+ orchestration; L5 = fully autonomous (aspirational). Tasks named: RTL generation, verification planning, testbench creation — all **digital frontend**.

### vs OpenForge

Synopsys AI tools sit **above** and **beside** a mature PDK-backed custom/analog flow: migration, sizing, corner analysis, layout-adjacent signoff. None of the public pages claim **topology invention from RS-style spec envelopes gated by ngspice fitness=1** — the layer OpenForge targets. Closest analog overlap is **ASO.ai sizing optimization**, which assumes topology and netlist structure already exist.

**Marketing vs evidence:** Productivity multiples (5×, 20×, 30%) are stated without reproducible benchmarks on the marketing pages. Treat as directional vendor positioning.

---

## 2. Semiconductor Engineering — industry survey

**Primary article:** [Best Options For Using AI In Chip Design](https://semiengineering.com/best-options-for-using-ai-in-chip-design/) (Ed Sperling, Aug 2025 — part 2 of EDA-vendor panel; part 1: [How AI Will Impact Chip Design And Designers](https://semiengineering.com/how-ai-will-impact-chip-design-and-designers/), Jul 2025).

**Panel:** Cadence, Siemens EDA, Synopsys, ChipAgents (Mehir Arora), Baya Systems, Keysight.

### What it actually is

Roundtable synthesis — more even-handed than vendor pages, still EDA-incumbent heavy. No hands-on benchmarks.

### Landscape (as described)

| Approach | Where it applies | Maturity (panel) |
|----------|------------------|------------------|
| ML/RL **optimization** inside tools | PPA, test, analog corners | Production for years ("value tier 1") |
| **Analytics** on design/manufacturing data | Foundation for next tiers | Production |
| **GenAI assistance** | Script gen, log analysis, debug hints, knowledge assistants | Available now; junior-engineer leverage |
| **Agentic workflows** | Multi-step orchestration across EDA tools | Early — Synopsys L1–L2 today, L5 aspirational |
| Vertical / domain-specific agents | Automotive digital twin, HPC, RF/materials | Customer-built on vendor MCP APIs |

### Key claims and caveats

- **Narrow verticals win** — not "design me a PLL at 2nm" from a chat box (Siemens).
- **Value hierarchy:** optimization → analytics → generative → agentic (Synopsys).
- **Agents need different tooling than humans** — parallelism, patience, aggressive trial (ChipAgents): future "EDA for agents," not only copilots on GUIs.
- **Legibility problem:** as agents do more, humans need compressed "proof of work" reviews — informal evidence that checks boxes without re-deriving everything (ChipAgents).
- **Junior engineers:** panel split — force multiplier vs. risk of automating entry-level learning paths.
- **Human signoff non-negotiable** for tapeout-grade correctness (all vendors).

### Simulation-validated closed loop?

**Not discussed for analog SPICE topology generation.** Panel scope is digital spec→RTL→verify→implement and tool-assist analog **on existing** designs. No participant describes an evolutionary **mutate → SPICE → hard spec gate → corpus** loop like OpenForge's fitness=1 bar.

Related SE pieces (same ecosystem, not the primary survey article):

- [Agentic AI In Chip Design](https://semiengineering.com/agentic-ai-and-chip-design/) — ChipAgents intro; agents plan and self-correct on verification tasks.
- [Human-Centered Agentic AI Comes To RTL Verification](https://semiengineering.com/human-centered-agentic-ai-comes-to-rtl-verification/) — Siemens Questa MCP agents (RTL, CDC, verification planning).

### vs OpenForge

Confirms industry focus on **digital verification bottleneck** and **implementation closure**, not analog topology search from spec. The **hard gate from simulator output** pattern appears implicitly (tests pass/fail, coverage, signoff tools) but not as a unified **analog fitness envelope** across product categories.

---

## 3. ChipAgents / William Wang — agent architecture (not domain transfer)

**Sources:** [ChipAgents blog — agentic shift](https://chipagents.ai/blogs/agentic-ai-biggest-shift-since-eda), [DVCon Taiwan 2025 deck](https://dvcontaiwan.org/wp-content/uploads/2025/09/3.8-DVCon-Taiwan-2025_Tutorial-28-ChipAgents.pptx.pdf), [DAC 62 exhibitor forum (YouTube)](https://www.youtube.com/watch?v=645IuCxgLLY), [SemiWiki 2026 outlook](https://semiwiki.com/eda/chipagents-ai/364729-2026-outlook-with-william-wang-of-chipagents-ai/).

**Talk:** DAC 62 TechTalk — *"Beyond Automation: How Agentic AI is Reinventing Chip Design and Verification"* (William Wang). Digital RTL/DV domain.

### What it actually is

Multi-agent platform for **Verilog/SystemVerilog** design and verification: spec→code, testbench/assertion generation, waveform RCA, regression triage. Integrates with existing simulators, linters, formal tools. Benchmark: **ChipAgentsBench** — real taped-out-scale repos; success = **tests pass after agent edits**.

### Design stack layer

Digital **frontend + verification** only. Same category as Yosys/lambdapdk flows — HDL generation and DV automation, not SPICE netlist topology forging.

### Agentic architecture patterns (extracted)

| Pattern | ChipAgents implementation |
|---------|---------------------------|
| **Propose → tool verify → self-correct** | Agent runs sim; reads logs/waveforms; iterates until tests pass or budget exhausted |
| **Domain-specific tools, not raw LLM** | Waveform understanding engine — standard LLMs cannot ingest multi-GB VCDs |
| **Multi-agent roles** | Prover–verifier pairs for RCA; aggregator assigns confidence scores |
| **Guardrails / staged trust** | Start with docs, spec analysis, triage; add formal checks before RTL mutation; audit trails + reproducibility for every change |
| **Determinism boundary** | AI for large search spaces with objective pass/fail; humans retain signoff, architecture, tapeout |
| **Self-directed context** | Agent selects relevant files/signals in huge repos — offloads context curation from human |
| **Benchmark discipline** | ChipAgentsBench: failing test + waveform → fix must pass regression (analogous in *shape* to fitness gate, different domain) |

### vs OpenForge forge loop

| | ChipAgents | OpenForge |
|---|------------|-----------|
| Domain | Digital RTL/DV | Analog SPICE topologies |
| Verifier | Simulator + tests, linters, formal | ngspice + RS `spec_envelopes` |
| Success criterion | Tests pass / coverage goals | `fitness=1` / `meets_all` |
| Mutation unit | Code edits across project | Param mutation on fixed topology library (Phase 4: directed topology variants) |
| Self-correction | LLM replans from tool stderr/logs | Discard loser; keep winner — **no LLM in the inner loop today** |
| Multi-agent | Yes (RCA, specialized agents) | No — evolutionary population, not role-based agents |
| Confidence / legibility | Explicit confidence scores on RCA hypotheses | Evidence logs (`docs/STATUS.md`, `evidence/`) — no calibrated agent confidence |

---

## 4. Analog / SPICE generation landscape (gap check)

OpenForge's prior read: AnalogCoder, LaMAGIC, Masala-CHAI, AnalogGenie do not close a **simulation-validated fitness=1 loop across product spec envelopes** the way OpenForge aims to. Spot-check from papers/repos:

| System | Topology generation? | SPICE/sim loop? | Spec envelope gate? |
|--------|---------------------|-----------------|---------------------|
| **AnalogCoder** (AAAI 2025) | Yes — LLM writes PySpice | Yes — execution feedback in agent loop | Task benchmarks (24 tasks); not RS-series multi-metric envelopes |
| **AnalogGenie** (ICLR 2025) | Yes — generative graph sequences | Validity + GA sizing; ngspice in supplement | Validity %/novelty %; sizing separate from generation |
| **LaMAGIC** | Limited (small power converters) | Simulation for evaluation | Fixed graph size constraints |
| **Masala-CHAI** | Dataset corpus | Enables training/eval of other agents | Corpus quality labels, not forge fitness |
| **Synopsys ASO.ai** | No — optimizes existing schematics | Massive corner sim | Designer-defined objectives, not autogenerated topology |

**Academic agentic EDA survey** ([arXiv 2512.23189](https://arxiv.org/html/2512.23189v1), Dec 2025): explicitly **digital RTL-to-GDSII only**; states analog automation needs separate review. Describes ReAct loops, generator–critic, MCP tool orchestration — same pattern vocabulary as ChipAgents/Synopsys, digital scope.

**Conclusion (unchanged, reinforced):** The **spec → topology → ngspice → hard multi-metric pass gate → evolutionary keep/discard** stack remains a genuine gap in published analog work and vendor marketing. Closest neighbors use sim feedback for **task completion** or **sizing**, not category-wide **fitness=1** forging.

---

## 5. Adjacent frameworks (brief — not primary sources)

Mentioned in secondary search; useful pattern references only:

- **MCP4EDA** — MCP server for open-source RTL-to-GDS; closed-loop synthesis refinement from post-layout metrics.
- **FluxEDA** — stateful MCP gateway for persistent EDA tool sessions; timing ECO case studies.
- **Siemens Fuse / Questa Agentic Toolkit** — MCP-native verification agents, human-in-the-loop by design.
- **Cadence ChipStack super-agent** — mental model of design intent; iterative tool calls with team checkpoints.

All **digital implementation/verification** orchestration — same pattern layer as ChipAgents, different packaging.

---

## Patterns potentially relevant to OpenForge's forge loop / Phase 4 evolutionary engine

These are **pattern candidates for human review**, not an integration plan.

### 1. Propose → verify → self-correct (ChipAgents, Synopsys AgentEngineer, MCP4EDA)

**Shape match:** OpenForge already has **mutate → ngspice → gate**. Missing piece: **structured feedback into the mutator** — today a fail is discard-only; agents enrich failure with *why* (which spec, which metric margin) to bias next mutation. Phase 4 directed mutation could ingest metric deltas without adding an LLM.

### 2. Staged guardrails (ChipAgents trust ladder)

Low-risk wins first (documentation, seed scoring), then behavioral tests, then topology variants. Maps cleanly: Phase 1–2 closed; Phase 3 honest partials; Phase 4 only after structural gates (e.g., vref real error amp) pass. **Do not size through ideal elements.**

### 3. Confidence / legibility layer (ChipAgents RCA aggregator)

When Phase 4 explores topology variants, not every ngspice run is equal — some fail one spec by 0.1%, others by 10×. A **ranked hypothesis log** (metric margins, not LLM confidence theater) would help human review without reading every deck. Analog to ChipAgents' "high confidence RCA first."

### 4. Multi-agent decomposition (industry default)

Hierarchical roles — generator, critic, tool-runner — appear in AnaFlow, ChatEDA, ChipAgents RCA. OpenForge's evolutionary loop is **population-based**, not role-based. Possible hybrid: critic pass could prune mutations before sim (cheap structural checks in `circuit_checker`) — already partial; formal "critic" for connectivity before ngspice is low-hanging fruit.

### 5. MCP / tool-session state (FluxEDA, Siemens, Cadence)

Relevant if OpenForge later exposes forge to external agents — **stateful ngspice sessions, pinned PDK context, reproducible artifact paths**. Not needed for Phase 4 core loop; note for Phase 5+ serving UI.

### 6. Benchmark discipline (ChipAgentsBench, arXiv agentic EDA survey)

Industry moving to **end-to-end pass/fail on real designs**, not single-metric leaderboards. OpenForge's `make smoke-wsl` + per-phase `verify_phase*.py` + seed sweeps are aligned. **Reconcile smoke seed vs robustness sweep in one sentence** (already a project rule) matches their "realistic benchmark" ethos.

### 7. What the industry is *not* doing (OpenForge differentiation)

- No vendor page claims **autonomous analog topology invention** from spec with SPICE fitness=1 across diverse block types (opamp, comparator, switch, vref, …).
- Agentic EDA literature **defers analog** to future work.
- Research analog generators rarely combine **topology search + strict multi-metric envelope + evolutionary corpus** the way OpenForge's `winners.jsonl` gate does.

### 8. Failure modes others report (avoid in Phase 4)

- **Hallucinated correctness** — pass syntax, fail physics (AnalogCoder 57% valid circuits before iteration).
- **Ideal element masking** — OpenForge analog: VCVS error amp, level-1 BJT cards (see `docs/semicon-log.md` entry 1).
- **Overconfidence without calibrated margins** — agent proposes fix; human chases low-confidence paths.
- **Skipping legibility** — "trust me" summaries; project SKILL.md already gates this.

---

## Explicit non-scope

- Installing ChipAgents, Synopsys tools, MCP servers, or FluxEDA
- Cloning vendor or research repos into OpenForge
- Proposing Phase 4/5 architecture changes from this survey
- Evaluating ChipAgents as integration target (digital RTL — wrong layer)

**Human decision point:** Which patterns (if any) to adopt in Phase 4 mutator feedback, structural gates, or evidence logging — after Phase 3 exit criteria are met.
