# OpenForge — Analog Design Rules & Senior Hire Onboarding

This document captures **general analog design knowledge** we want encoded in OpenForge checks, reviews, and future verification layers. It is intentionally **not** a corpus of prior employer designs.

---

## IP boundary (read first)

| Allowed | Not allowed |
|---------|-------------|
| Textbook-level principles, checklists, operating-region rules | Schematics/netlists from prior employers |
| Judgment on **OpenForge-generated** outputs | Proprietary sizing recipes, foundry confidential decks |
| General topology intuition (mirror matching, Miller node, etc.) | Uploading NDA training data into the repo |

Same clone-audit discipline as GitHub imports — applied to human knowledge.

**What we want from a senior analog hire:** rules, judgment, and review passes — not their old company's IP.

---

## Competency ladder (what “good” looks like)

Structured progression for humans and for future automated checks:

1. **Fundamentals** — KCL/KVL, Thevenin/Norton, units, orders of magnitude
2. **Devices** — MOSFET/BJT regions (cutoff, linear, saturation), small-signal models
3. **Building blocks** — current mirror, diff pair, cascode, follower, bandgap core
4. **System blocks** — op-amp, comparator, LDO, reference, switch, charge pump
5. **Layout-aware** — matching, symmetry, guard rings, ESD (future — no layout in OpenForge yet)
6. **Bench** — scope, DMM, SMU, load conditions that match the datasheet

OpenForge today sits between **3 and 4**: netlist + ngspice + schematic connectivity. DRC/LVS/layout is **north star**, not next task.

---

## Tractable checks now (implement on data we have)

These are “old analog guy brain” checks on **simulation + netlist**, not silicon prediction:

### KCL at DC operating point
- After `.op`, sum currents into each node; flag any node where |ΣI| > tolerance
- Catches disconnected nodes, wrong polarity, broken bias

### Device operating region
- For each MOSFET: Vgs, Vds, Vth → classify saturation vs linear vs cutoff
- Flag devices intended as switches sitting in linear region at the measurement point
- Flag mirror reference devices not in saturation

### Matching / symmetry
- Diff-pair W/L ratio, tail bias, mirror device pairing
- Comparator/op-amp: input pair and load mirror should be structurally symmetric in netlist

### Schematic connectivity (Phase 0.7)
- Every device terminal on a wire segment (or IO stub for external pins)
- IO stubs must **reach** gate/drain terminals — not stop 16 px short
- Netlist adjacency ≡ wire-graph adjacency
- No false junction dots at unrelated-net crossings

### Schematic rendering — gate-stub-then-fold (Phase 0.8 target)

**Invariant:** Every routed wire must *emanate from* a device, not start in mid-air near it. This is how real schematic capture tools draw; it fixes the “floating/ugly” look permanently.

**Rule (hard):**
1. At each device terminal, emit a **short terminal stub** in the terminal’s **natural direction** and **collinear** with that direction.
2. Only **after** the stub end does the wire **fold** (折) orthogonally toward its routing target.

**Terminal directions (NMOS/PMOS, origin at top-left, non-mirrored):**

| Terminal | Stub direction | Default stub length |
|----------|----------------|---------------------|
| Gate (`g`) | Horizontal, **out the gate side** (left for our symbol) | 10 px (1 grid) |
| Drain (`d`) | Vertical, **out the drain side** (up for our symbol) | 10 px |
| Source (`s`) | Vertical, **out the source side** (down for our symbol) | 10 px |

Mirrored devices: stub direction follows the **same transform** as `render_symbol` / `terminal_positions` (mirror flips gate side).

Two-terminal (R, C, I): stub horizontally out from `p` and `n` anchors.

**Routing order:**
```
terminal anchor → terminal stub (collinear) → stub-end → Manhattan fold → junction/target
```

**Verifier assertion (to implement in `schematic_connectivity.py`):**
- For each non-IO, non-rail wire segment incident on a device terminal `T`:
  - Either that segment is the terminal stub (collinear with terminal direction, length ≤ stub_max), **or**
  - The segment meets the stub-end of `T`, not `T` directly at a non-collinear angle.
- **Fail** if the first routed segment from a terminal is orthogonal to the terminal direction (wire “teleports” beside the device).
- IO stubs (`vinp`/`vinn`/`vout`) exempt: they are external pins, not device terminal stubs.

**Emitter change (when implemented):** `schematic_layout.py` — `_terminal_stub()` per placed device before `_route_net()`; route from stub-ends, not raw anchors.

**Why this matters:** Connectivity tests (0.7) prove nets join; they do **not** prove wires look electrically attached. Stub-then-fold is a separate, checkable aesthetic+correctness layer.

### Spec compliance
- RS-series envelopes after ngspice (already in forge)

---

## Rules by circuit class

### Current mirror
- Reference and output devices must be **matched** (same L, intentional W ratio)
- All mirror FETs in **saturation** at the bias point
- Gate nodes of mirrored devices must be **common** (same net)

### Differential pair
- Tail current source sets common-mode rejection baseline
- Inputs must reach **both** gate terminals in schematic and netlist
- Symmetric placement for layout-forgiving topology (even before layout)

### Two-stage Miller op-amp
- Compensation cap **right plate** on high-impedance node (typically second-stage input)
- Output stage must sink/source load current at spec
- PM/GBP tradeoff: Cc and second-stage gm are coupled — sizing story must be causal

### Comparator
- Diff pair + decision stage; valid trip point and propagation delay **under stated load**
- Input common-mode range must include the test fixture

### Bandgap / reference
- Core PTAT + CTAT combination; startup circuit often as important as core
- Load regulation and line regulation are separate checks

### Charge pump
- Switching nodes bootstrapped above rail if NMOS topologies used
- Output ripple measured with realistic load cap

---

## Review pass template (human or agent)

When reviewing a forge output, ask:

1. **Topology** — Does this block even make sense for the stated product type?
2. **Bias** — Is every device in a plausible region at `.op`?
3. **Nets** — Do critical nodes (gates, Miller node, mirror gate) connect what they should?
4. **Schematic** — Do IO stubs touch terminals? Symmetry preserved for mirrored devices?
5. **Simulation** — Is the bench fixture realistic (load, edges, Cload, supply)?
6. **Spec** — Which metrics are measured vs assumed? Any false pass from loose tolerance?

Document findings as: **observed / inferred / not verified**.

---

## Sequencing (what not to build yet)

| Now | Later |
|-----|-------|
| KCL/KVL on `.op` | DRC without layout |
| Region checks | LVS without layout |
| IO-stub + connectivity verifier (0.7) | Full “world model for silicon” |
| **Gate-stub-then-fold** renderer + verifier (0.8) | Auto-layout |
| Close open spec gaps (e.g. vref iq) | Layout → DRC → LVS → ESD → OPC |

---

## Contributing as senior analog advisor

1. Add or refine rules in this file (general principles only)
2. Review generated SVG + netlist + metrics; paste findings into issues/handoff
3. Prioritize which automated check comes next
4. Never commit employer-owned artifacts

---

*Starter doc — extend with domain expert input. Last updated: 2026-06-19.*
