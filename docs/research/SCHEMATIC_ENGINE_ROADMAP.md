# Schematic Engine Roadmap (OA-style Principles, Open Implementation)

Updated: 2026-06-21

## Why this roadmap exists

Recent failures showed that a schematic can pass coarse geometry checks while still being visually and semantically wrong (floating passive taps, hidden pin collapse, polarity confusion). This roadmap hardens OpenForge's schematic stack toward industry-style EDA discipline while staying open-source and Python-first.

## Target architecture

1. **Pin-typed schematic database**
   - Store terminals as `(device, pin, net)` triples, not only `(device, net)`.
   - Preserve duplicate-pin nets (for example MOS diode connection `d` and `g` both on `nb`) without collapsing geometry.
   - Keep view separation:
     - logical netlist view,
     - symbol/anchor view,
     - routed geometry view.

2. **Constraint-aware routing core**
   - Manhattan-only pathing in render path.
   - Net-order strategy with conflict guards around foreign terminal escape points.
   - Future: analog hints for symmetry groups and matched-pair route channels.

3. **Verification stack split**
   - **Connectivity gate**: net/pin equivalence vs wire graph.
   - **Geometry gate**: axis-aligned segments, no floating passive stubs, terminal-stub integrity.
   - **Semantic gate**: pin role checks (source-side orientation, diode ties, polarity labels).
   - **Artifact gate**: generated SVG required in evidence bundle.

## Near-term implementation windows

### Window A — semantic correctness (now)
- [x] Preserve terminal identity with explicit pin refs (`d/g/s`, `p/n`) in routing/verification.
- [x] Correct PMOS source/drain anchor orientation for schematic semantics.
- [x] Swap op-amp input labels to match sign path (`vinp` -> `IN-`, `vinn` -> `IN+`).
- [x] Add regression tests for polarity labeling and duplicate stub prevention.

### Window B — visual de-ambiguation
- [ ] Add explicit cross-net collinear-overlap detector and fail gate.
- [ ] Route-channel reservation to prevent one net from occupying another net's drain/gate escape line.
- [ ] Improve stage-2 placement objective with readability terms (net overlap penalty, mirror symmetry score).

### Window C — analog-aware authoring primitives
- [ ] Introduce device grouping constraints (differential pair, mirror pair, bias spine).
- [ ] Add optional symmetry templates for paired nets and mirrored stubs.
- [ ] Add capacitor/load primitives with explicit attach policies (`between_nodes`, `to_ground`, `to_supply`) and mandatory terminal proof.

### Window D — bridge toward physical layout research
- [ ] Add simple colored-layer canvas prototype (diff/poly/m1) for educational topology-to-layout mapping.
- [ ] Add extraction-lite checker to compare routed layer graph vs schematic net graph.
- [ ] Keep DRC/LVS claims as `not verified` until true layout pipeline exists.

## Research inputs (open sources only)

- OpenAccess-like data modeling concepts (public docs/papers only).
- Open-source analog flows: ALIGN, MAGICAL, OpenROAD analog-related work, KLayout scripting.
- Academic references for symmetry/matching-aware analog routing heuristics.
- Public thesis/papers on graph-based schematic readability metrics.

### Seed references (checked)

- [ALIGN-public](https://github.com/ALIGN-analoglayout/ALIGN-public) and [ALIGN constraint docs](https://align-analoglayout.github.io/ALIGN-public/notes/const.html) for constraint-driven analog placement/routing.
- [MAGICAL](https://github.com/magical-eda/MAGICAL) and tutorial papers (ICCAD/TCAS-II) for hierarchical database + placement/routing split with Python orchestration and C++ kernels.
- Layered/Sugiyama orthogonal routing literature for crossing reduction and port-aware Manhattan edge construction.

## Non-goals (until owner reopens)

- No proprietary Cadence/Synopsys code or NDA material.
- No claim of production LVS/DRC closure without physical layout.
- No autonomous "self-triggering" research loops.

## Acceptance evidence for roadmap progress

Each window closes only with:
- scoped diff,
- verbatim command output,
- artifact path(s) (SVG, diagnostics),
- explicit `not verified` list for remaining gaps.
