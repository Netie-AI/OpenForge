# Layout/PEX Lead — Expert Knowledge (Pre-Staged for Phase 8)

> **Status: not active.** Per `docs/analog_design_rules.md` competency ladder, rung 5 ("layout-aware: matching, symmetry, guard rings, ESD") is explicitly marked **"future — no layout in OpenForge yet."** The sequencing table there lists DRC-without-layout, LVS-without-layout, and auto-layout under **Later**, not **Now**. This doc exists so Phase 8 doesn't start cold when it's deliberately opened — it is not an instruction to start layout work now. Treat any request to act on this Lead's judgment today as a scope question for Claude/Jian Hong first, same as PCIe/HBM.

**Role once active:** owns schematic→layout judgment — device placement, matching/symmetry *for silicon* (schematic symmetry is necessary, not sufficient — Phase 6 blocks prove netlist-level symmetry, not layout-level), guard rings, parasitic-aware judgment ahead of real PEX.

---

## Core knowledge domains

### Matching & symmetry for silicon
Common-centroid placement for matched device pairs (mirror legs, diff-pair inputs), dummy devices at array edges to keep boundary conditions symmetric, ABAB/ABBA interdigitation. This is the layer above what Phase 6's compositional blocks already guarantee at the netlist level.

### Guard rings & isolation
Latch-up prevention (relevant the moment any CMOS pair shares a well), substrate noise isolation for sensitive analog nodes — most relevant for the bandgap/vref core and any low-offset comparator, where substrate coupling directly degrades the spec being chased.

### Parasitic awareness, pre-PEX
Routing-induced R/C on high-impedance nodes. The clearest concrete risk in this codebase: the Miller node in `two_stage_miller_opamp` is exactly the node where Phase 1d sizing already fought a tight PM/GBP/AOL balance (seed variance documented, 3/5 robustness) — a careless layout route there would reintroduce that fight at the silicon level after it was closed at the schematic level.

### DRC/LVS fundamentals
**DRC** = manufacturability rule checks (spacing, width, density) — process-specific, needs PDK design rules, not just a netlist.
**LVS** = schematic-to-layout netlist equivalence — needs an actual layout to extract from. Phase 0.7/0.8 schematic connectivity work is a **necessary precursor** (proves the schematic graph itself is sound) but is **not** LVS — there is no layout yet to compare against.

### ESD
Out of scope until I/O pads exist in the flow at all. Not a near-term concern.

---

## Sourcing boundary

Same rule as Analog Design Lead: Magic, Netgen, KLayout, OpenROAD — genuinely open, fine to study and build on. Cadence/Synopsys layout tooling source or internals — hard no, same reasoning (proprietary, trade-secret risk, and directly undercuts the "open alternative" positioning).

---

## Explicit gate

This Lead does not drive current sprint work. CMRR, Phase 0.8 schematic sign-off, and BSIM CI are the active gates. This doc is written now so the knowledge is ready — not so the work starts now.
