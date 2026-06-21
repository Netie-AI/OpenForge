# Semiconductor / EDA-Tooling Engineer — Reference Knowledge (Pre-Staged)

> **Status: reference only, mostly future-staged.** This doc encodes what an EDA-tooling-aware engineer knows, so the knowledge is ready when Phase 8 (physical) and the v2 RTL lane open. It is **not** an instruction to integrate any of the proprietary tools named below.
>
> **Critical sourcing frame:** Calibre (Siemens), Spectre/Virtuoso (Cadence), PVS/IC Validator (Cadence/Synopsys), VCS/UVM tooling (Synopsys) are **industry-standard reference points only**. OpenForge does not build on, wrap, parse, or integrate them. Every entry below pairs the proprietary tool with the **open equivalent OpenForge actually uses or targets**. The proprietary names exist here so an engineer knows the landscape — not as integration targets. The fitness=1 validation gate stays on ngspice; the physical-verification target stack is Magic/Netgen/KLayout.

---

## 1. Industry tool ↔ OpenForge open equivalent

| Function | Industry-standard (reference only) | OpenForge open stack (actual / target) |
|----------|-----------------------------------|----------------------------------------|
| Analog simulation | Spectre | **ngspice** (the validation gate — non-negotiable) |
| Schematic/layout capture | Virtuoso | OpenForge schematic engine (Phase 7); Magic/KLayout for layout (Phase 8 target) |
| DRC (design-rule check) | Calibre nmDRC, PVS, IC Validator | **Magic** (Phase 8 target) |
| LVS (layout-vs-schematic) | Calibre nmLVS, PVS | **Netgen** (Phase 8 target) |
| PEX (parasitic extraction) | Calibre xRC/xACT, StarRC, QRC | open PEX (Magic ext / future) — Phase 8 |
| Digital sim / verification | VCS, Xcelium + UVM | **Icarus/Verilator + Yosys** (v2 RTL lane only) |

Nothing in the left column is in OpenForge's dependency tree, now or planned.

## 2. Physical-design concepts (Phase 8 — not active)

- **Vias & metal stack.** Vias connect routing layers; via count/placement affects resistance and electromigration. Relevant once real routing exists — Phase 8, not before.
- **Governed/constraint-driven layout.** Placement and routing under matching, symmetry, and spacing constraints — this is the *automated analog placement/routing* problem flagged repeatedly as **unsolved industry-wide**, explicitly not near-term sprint work.
- **DRC** = manufacturability (spacing/width/density), process-specific, needs PDK rules. **LVS** = layout netlist ≡ schematic netlist, needs an actual layout. Phase 0.7/0.8 schematic-connectivity work is a *precursor* (proves the schematic graph is sound) — it is **not** LVS; there is no layout yet to compare against.
- **PEX** = extract real R/C parasitics from layout, re-simulate (post-layout sim). The risk node to watch when this lands: the Miller node in the two-stage opamp, where Phase 1d already fought a tight PM/GBP/AOL balance — careless routing reintroduces that fight at silicon level.

## 3. Verification methodology concepts (v2 RTL lane — not active)

- **UVM** (Universal Verification Methodology) is a **digital** verification framework — constrained-random stimulus, coverage-driven closure, scoreboards. It is relevant only to the **digital RTL lane scoped as a v2 milestone** (Verilog/Yosys/Icarus), not to analog front-end generation. Do not conflate UVM with the analog ngspice bench discipline — different domain, different lane.
- The analog equivalent of "coverage closure" in OpenForge is the **PVT/corner/Monte-Carlo** expansion (real corner decks on SKY130 BSIM, temperature sweeps, mismatch scatter) — staged after single-corner stability, per `analog_design_rules.md`.

## 4. What this role does once active

Owns the bridge from validated netlist (Analog Design Lead's output) to manufacturable physical design: running DRC/LVS/PEX on the **open** stack, interpreting violations, and feeding parasitic reality back into the sizing loop. Until Phase 8 opens, this is reference knowledge — the active gates are CMRR, Phase 0.8 sign-off, and BSIM CI.

## 5. Sourcing boundary (hard rule, restated)

Open EDA source (Magic, Netgen, KLayout, OpenROAD, ngspice, Yosys, Icarus, Verilator) — fine to study and build on. Cadence/Synopsys/Siemens tool source, internals, encrypted PDK decks under NDA, or any proprietary verification IP — never, in any form. If a "reference flow" or "example deck" turns out to be derived from a proprietary tool, flag it and stop.
