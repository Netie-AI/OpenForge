# Generative analog layout & open-source silicon IP — integration survey

**Date:** 2026-06-20  
**Scope:** Read, distill, human decides. No integration, no new dependencies, no architecture changes triggered from this doc.  
**Companion:** `docs/research/AGENTIC_EDA_SURVEY.md` (agentic *workflow* patterns); this doc covers *physical layout / GDS* generators and mixed-signal toolchain boundaries.

**Sourcing boundary (OpenForge rule):** Public datasheets, academic papers, and genuinely open-source EDA (ngspice, Magic, Netgen, OpenROAD, KLayout, ALIGN, MAGICAL, OpenFASOC, BAG docs) are allowed. No proprietary Cadence/Synopsys source, internals, or NDA material.

---

## Executive summary (for Claude reviewer)

The external memo on "Generative Analog EDA" is **directionally correct** but **overstates near-term fit for OpenForge**:

| Claim in generic memo | OpenForge reality |
|----------------------|-------------------|
| "Download ALIGN/MAGICAL and get enterprise PHY blocks" | Those tools target **layout from sized netlists**, not **topology invention + ngspice fitness=1** — OpenForge's current layer. |
| "OpenFASOC generates complex analog blocks" | OpenFASOC generators are **template/cell-stitched** (temp sensor, digital LDO) on **Sky130 + OpenROAD** — different architecture from RS321 two-stage Miller opamp forging. |
| "BAG/Chipyard gives serializers and wireline" | BAG3++ is **Python layout/schematic generators**; still **Virtuoso-dependent** for full flow. Chipyard analog integration is **aspirational**, not shipped. |
| "HBM PHY / SerDes open source exists" | **No functional HBM3/HBM4 PHY** in open source. CHIPS Alliance **AIB** is die-to-die IO *interface* RTL/spec — not HBM. **Parking lot** per `PARKING_LOT.md`. |
| "OpenLane routes analog + digital together" | OpenROAD/OpenLane is **digital P&R**; OpenFASOC wraps it with **custom analog-adjacent hacks** (voltage domains, NDR rules) for specific generators — not a general analog placer. |

**OpenForge differentiation (unchanged):** spec envelope → topology + param mutation → **ngspice** → `meets_all` / fitness=1 → corpus. Layout generators sit **downstream** of that gate, not upstream.

**Honest integration window:** Phase **7+** (after schematic connectivity + SKY130 BSIM category gates). First bridge is likely **netlist export → ALIGN or MAGICAL trial** on a **single closed category** (opamp or comparator), not SerDes/HBM.

---

## 1. ALIGN — Analog Layout, Intelligently Generated from Netlists

**What it is:** DARPA IDEA open-source flow (UMN, Texas A&M, Intel). SPICE netlist → hierarchical annotation → primitive cell generation (fingers, passives) → constrained place & route → GDSII.

**Inputs:** Sized/unannotated netlist, PDK (JSON design-rule abstraction + primitive generators).  
**Outputs:** GDSII, JSON layout view.  
**Repo:** [ALIGN-analoglayout/ALIGN-public](https://github.com/ALIGN-analoglayout/ALIGN-public)

**Strengths for OpenForge:**
- Accepts **SPICE netlists** — closest format match to forge output.
- Explicit **symmetry / constraint JSON** — aligns with OpenForge schematic floorplan intent (diff-pair matching, mirror axes).
- Benchmark circuits + CircleCI examples — reproducible smoke path.
- Documented on FinFET mock PDK; community has Sky130 experiments (verify PDK maturity before claiming production).

**Gaps / risks:**
- Assumes **topology and sizing already chosen** — does not replace forge/sizer.
- PDK porting cost: primitive generators must be redefined per node.
- Quality varies by block class; wireline/wireless examples in papers ≠ RS-series precision blocks without per-block validation.
- Docker-first install; not a pip dependency.

**OpenForge integration sketch (Phase 7+, not started):**
```
forge winner netlist (SPICE)
  → export script (pinned W/L, subckt hierarchy)
  → ALIGN + sky130 constraint JSON (symmetry from schematic_layout zones)
  → GDSII
  → Magic DRC / Netgen LVS (open tools)
  → optional PEX back-annotate (later)
```
**Gate before claiming value:** one OpenForge opamp netlist → ALIGN GDS → LVS clean on Sky130; compare post-layout sim vs pre-layout ngspice (manual or scripted).

---

## 2. MAGICAL — Machine Generated Analog IC Layout

**What it is:** UT Austin / IDEA open-source end-to-end AMS layout (C++ kernels, Python flow). Silicon-proven on 40 nm ΔΣ ADC (MAGICAL 1.0); extended to SAR-ADC.

**Inputs:** Netlist + optional constraint files (symmetry groups, net pairs).  
**Outputs:** GDSII.  
**Repo:** [magical-eda/MAGICAL](https://github.com/magical-eda/MAGICAL) (+ sanitized circuits repo).

**Strengths:**
- **Silicon tapeout evidence** — stronger than ALIGN on "does it tape out?"
- Automatic symmetry extraction (pattern matching) — reduces manual constraint coding vs BAG.
- ML-assisted routing (GeniusRoute) — learns from manual layouts; research-grade, not turnkey.

**Gaps / risks:**
- Active development; multi-repo build (Docker recommended).
- Device generation partially binary/NDA-stripped in public releases.
- Real PDK support requires effort; toy techfiles for demo only.
- Compared to BAG paper: reduces codified constraint cost, but still **layout-only** layer.

**OpenForge fit:** Same downstream slot as ALIGN. **Do not run in parallel** with forge topology work — separate verification gate per `PARKING_LOT.md` layout section.

**When to prefer MAGICAL vs ALIGN:** If goal is **published silicon-proven flow** and constraint extraction automation; if goal is **IDEA ecosystem + Intel co-development history**, ALIGN. Pick **one** for a pilot — not both simultaneously.

---

## 3. OpenFASOC — template generators on OpenROAD (Sky130)

**What it is:** Michigan/Brown IDEA project. **Spec → generator Python → Verilog/cell netlist → OpenROAD flow → GDSII + DRC/LVS** using Magic/Netgen.

**Shipped generators (2024–2026 docs):**
- **Temperature sensor** (sky130hd) — leakage-based ring oscillator; 64-instance silicon verification paper (SSCL 2022).
- **Digital LDO** (sky130hvl) — comparator + digital controller + pass switches; OpenROAD flow **modified** for analog-ish domains (voltage domains, custom connections).
- **GLayout** — PDK-agnostic P-cell layout with RL optimization (notebook includes op-amp *example* — not RS321 forge integration).
- WIP: cryo, DC-DC, LC-DCO, SCPA.

**Repo:** [idea-fasoc/OpenFASOC](https://github.com/idea-fasoc/OpenFASOC)

**Strengths:**
- **Fully open toolchain** on Sky130 — matches OpenForge Phase 3 PDK direction.
- CI badges on generators — evidence culture aligned with OpenForge.
- Demonstrates **how to hack OpenROAD** when native analog support is weak.

**Gaps / risks:**
- Generators are **fixed topologies**, not evolutionary forge output.
- Digital LDO ≠ OpenForge LDO topology (`openanalog/forge/topologies/`) — different architecture.
- "Op-amp in GLayout notebook" is **layout playground**, not spec-envelope forging.

**OpenForge integration sketch:**
- **Near-term (research only):** Study OpenFASOC's OpenROAD analog hacks (`read_domain_instances`, NDR rules) as **patterns** for future OpenForge LDO/charge-pump layout — do not merge generators wholesale.
- **Medium-term:** If OpenForge ships a **digital-heavy block** (charge pump digital control), OpenFASOC cell-stitch pattern may apply; precision opamp/comparator remain ALIGN/MAGICAL candidates.

---

## 4. BAG3++ — Berkeley Analog Generator

**What it is:** Python framework for **parameterized schematic + layout + testbench generators**. Modular: pick schematic-only, layout-only, or full loop.

**Docs:** [BAG3++ readthedocs](https://bag3-readthedocs.readthedocs.io/en/latest/)

**Strengths:**
- Explicit **generator philosophy** — Python describes layout params, matching OpenForge's parametric topologies conceptually.
- Testbench generator integration — interesting for Phase 3 PVT expansion (pattern, not product).

**Gaps / risks:**
- **Still requires Cadence Virtuoso** for full backend (explicit in BAG3++ docs) — conflicts with OpenForge open-tooling north star unless used as optional export path only.
- Not ngspice-first; Ocean/Spectre ecosystem historically.
- High setup cost (C++ build, PDK workspace).

**OpenForge fit:** **Low priority** until Virtuoso optional or abandoned. Useful as **reference architecture** for "generator objects" when Phase 4 topology variants need layout-aware params — read-only pattern extraction.

---

## 5. OpenLane / OpenROAD / Efabless — digital shell, analog macros

**What they are:**
- **OpenROAD** — digital implementation (floorplan, placement, CTS, routing, timing).
- **OpenLane** — RTL-to-GDS wrapper (Yosys + OpenROAD + Magic + Netgen).
- **Efabless / Sky130** — shuttle + preconfigured tool suites.

**Mixed-signal pattern (from OpenFASOC + industry):**
```
[Digital RTL] ──► OpenLane ──┐
                             ├──► OpenROAD (macros as blockages) ──► GDSII
[Analog GDS macro] ──────────┘
```
Analog block generated **externally** (ALIGN/MAGICAL/hand layout), dropped as macro; digital router routes around it.

**OpenForge fit:** Phase **8+** system integration — not Phase 3–4. OpenForge should **not** adopt OpenLane as primary analog path.

**Allowed open tools already in north star:** Magic (DRC), Netgen (LVS), KLayout (view/DRC) — verification layer after GDS exists.

---

## 6. High-speed IO, SerDes, HBM PHY — what is actually open?

| Topic | Open-source reality | OpenForge status |
|-------|---------------------|------------------|
| **HBM PHY** | No production-grade HBM3/HBM4 PHY generator | **Out of scope** — `PARKING_LOT.md`, `HANDOFF.md` |
| **SerDes / PCIe PHY** | Fragmentary RTL controllers on OpenCores/GitHub; no complete analog PHY + channel signoff | **Out of scope** |
| **CHIPS Alliance AIB** | Die-to-die parallel IO **interface** spec + RTL — foundation for chiplet IO, not memory PHY | Parking lot — study only if chiplet demo ever greenlit |
| **UC Berkeley wireline in BAG papers** | Academic generators for specific blocks; Virtuoso-era | Not transferable without proprietary stack |

**Takeaway:** Generic memos conflate **digital RTL IP** + **analog layout generators** + **bleeding-edge PHY**. OpenForge should keep these in parking lot until Phase 1–3 analog forge gates are closed with evidence.

---

## 7. Layer map — where OpenForge sits

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 4–5 (OpenForge core — IN PROGRESS / PLANNED)          │
│ spec_envelopes → topology mutate → ngspice → meets_all      │
└──────────────────────────────┬──────────────────────────────┘
                               │ sized SPICE netlist
┌──────────────────────────────▼──────────────────────────────┐
│ Phase 0.6–0.8 (OpenForge — WORKING / PARTIAL)               │
│ schematic floorplan + route_nets + connectivity tests       │
└──────────────────────────────┬──────────────────────────────┘
                               │ placement constraints (future export)
┌──────────────────────────────▼──────────────────────────────┐
│ Phase 7+ (NOT STARTED — external tools)                     │
│ ALIGN / MAGICAL / hand layout → GDSII                       │
│ Magic DRC + Netgen LVS + (later) PEX                        │
└──────────────────────────────┬──────────────────────────────┘
                               │ macro
┌──────────────────────────────▼──────────────────────────────┐
│ Phase 8+ (NOT STARTED — digital shell)                      │
│ OpenLane/OpenROAD for digital control around analog macros  │
└─────────────────────────────────────────────────────────────┘
```

**Critical insight from schematic findings (2026-06-20):** Schematic quality splits into **placement pressure** (e.g. `nb` net span M8/M5/M7) and **routing style** (0.8 stub-then-fold). Layout generators solve a **third** problem — geometric DRC-clean GDS — only after netlist is proven. Do not skip layers.

---

## 8. Recommended sequencing for OpenForge

| Step | Action | Gate |
|------|--------|------|
| **Now** | Close BSIM CI PR proof; CMRR fixture policy; tangling `crossing_score` 6→≤3 on schematic | Existing HANDOFF priorities |
| **Next layout research** | Pick **one** pilot: RS321 opamp or RS8901 comparator sized netlist | `meets_all` on BSIM seed gate |
| **Pilot A** | Docker ALIGN on Sky130 example circuit → document install + runtime | Verbatim log in `evidence/` |
| **Pilot B** (alternative) | MAGICAL sanitized benchmark OTA → compare constraint JSON to OpenForge schematic zones | Read-only; no forge merge |
| **After GDS** | Magic DRC + Netgen LVS on pilot | Clean reports attached |
| **After LVS** | Discuss post-layout ngspice (PEX or extracted netlist) | Phase 7+ gate; layout-pex-lead doc |
| **Defer** | OpenFASOC generator merge, BAG/Virtuoso, SerDes/HBM, full Chipyard analog | Until pilot proves one block |

---

## 9. Patterns to adopt (human review — not auto-integration)

1. **Constraint export from schematic** — OpenForge `_DIFF_PAIR_LAYOUT` / symmetry zones could emit ALIGN `.const.json` — reduces duplicate constraint authoring.
2. **Generator CI badges** — OpenFASOC pattern: per-generator GitHub Actions; analogous to OpenForge `sky130-bsim-smoke`.
3. **Evidence bundle on layout** — GDS + DRC + LVS logs required before STATUS layout row moves off `unverified`.
4. **Single-thread layout pilot** — same rule as forge writers: one layout integration stream at a time.

---

## 10. Explicit non-scope (from this survey)

- Installing ALIGN, MAGICAL, OpenFASOC, BAG, or OpenLane into OpenForge CI without a scoped pilot plan
- Claiming OpenForge generates GDS today (it does not)
- Treating ChatGPT "leaked commercial code" framing as actionable — **forbidden** by project sourcing rules
- Phase 4/5 reprioritization based on this memo alone

---

## References

| Resource | URL |
|----------|-----|
| ALIGN public | https://github.com/ALIGN-analoglayout/ALIGN-public |
| ALIGN flow docs | https://align-analoglayout.github.io/ALIGN-public/notes/flow.html |
| MAGICAL | https://github.com/magical-eda/MAGICAL |
| OpenFASOC | https://github.com/idea-fasoc/OpenFASOC |
| OpenFASOC docs | https://openfasoc.readthedocs.io/ |
| BAG3++ | https://bag3-readthedocs.readthedocs.io/en/latest/ |
| OpenROAD | https://github.com/The-OpenROAD-Project/OpenROAD |
| SkyWater PDK | https://github.com/google/skywater-pdk |
| CHIPS Alliance AIB | https://github.com/chipsalliance/AIB-PHY-HW |
| OpenForge agentic survey | `docs/research/AGENTIC_EDA_SURVEY.md` |
| OpenForge parking lot | `docs/PARKING_LOT.md` |

**Human decision point:** Approve or reject a **single-block ALIGN pilot** after BSIM CI PR proof — not before Phase 3 smoke gate is green in Actions.
