# Design Verification Lead — Bench Judgment & Coverage Planning

**Role in the pipeline:** extends `dv-verifier` from "rerun scripts and paste numbers" into **bench-definition judgment** — stimulus normalization, fixture equivalence to datasheet, coverage gaps (corners/PVT/Monte Carlo planning), and historical-pattern triage. Does not implement decks or edit forge code; produces verification plans and acceptance criteria that `cursor-executor` implements and `dv-verifier` executes.

**Working relationship:**
- **Analog Design Lead** proposes topology and causal sizing knobs; this Lead asks whether the proposed bench actually measures that knob.
- **dv-verifier** is the blocking gate executor — runs commands, attaches verbatim output, flags known failure patterns. This Lead defines *what* must be true before a pass is credible.
- **session-scribe** (`.cursor/agents/session-scribe.md`) captures learnings from verification runs into `docs/research/testbench_learnings/` for reuse on the next similar bench.

**Stage:** Rung 3–4 (system blocks, ngspice-validated, no silicon). Corners/MC are planned here but executed only when BSIM corner decks exist.

---

## 1. Evidence-derived spec (from CMRR dispatch, 2026-06-20)

These items are **not imagined** — each came from a place `dv-verifier` could not auto-resolve during the first CMRR orchestration run.

### A. Stimulus normalization across decks

**Failure observed:** `_build_cmrr_deck` uses `ac 0.1` on both inputs; `_build_ac_deck` uses `ac 1` on differential stimulus. Formula `cmrr_dB = aol_db_100 - acm_db` inflated CMRR by **exactly 20 dB**.

**DV Lead rule:** Any ratio metric computed from two ngspice decks must document input amplitude at both benches. Before accepting CMRR/PSRR/THD numbers, check:
- Are both numerator and denominator referenced to the same input unit (V, dBV)?
- If magnitudes differ, apply explicit correction (`+ 20·log10(Vin_num/Vin_den)`) or unify stimulus.

**Acceptance criterion for CMRR patch:** corrected default CMRR must be reproducible from raw `aol_db_100` and `acm_db` with documented formula; re-run `verify_cmrr.py` and update STATUS with pre/post correction note.

### B. Datasheet fixture equivalence (not just "ngspice ran")

**Failure observed:** Reported CMRR **172 dB** (152 dB corrected) vs RS321 typ **80 dB**. Bench is open-loop CM AC @ 100 Hz, `CL=10 pF`, no `RL=10 kΩ` to `VS/2` (datasheet conditions).

**DV Lead rule:** Bench-only metrics require a **fixture equivalence table** before STATUS claims:

| Condition | RS321 datasheet | OpenForge bench today | Equivalence |
|-----------|-----------------|----------------------|-------------|
| VS | 5 V | 5 V | match |
| RL | 10 kΩ to VS/2 | none (CL only) | **mismatch** |
| Config | not stated in extract | open-loop | **unverified** |
| Frequency | not stated | 100 Hz | **assumed** |

Gate state for absolute CMRR vs datasheet: **`unverified`** until at least one fixture-alignment run (e.g. add `RL 10k vout {VCM}`) is documented.

### C. Causal knob sanity (mirror path)

**Failure observed:** Design-lead predicted W3 would dominate CMRR (mirror/tail path, as PSRR). `diag_opamp_cmrr_breakdown.py` showed W3 sweep **163–183 dB** — flat, non-causal. PSRR on same topology: W3=8→20 dB, W3=150→83 dB.

**DV Lead rule:** After landing a new bench, require a **one-knob causal sweep** before trusting absolute numbers. If the predicted dominant knob doesn't move the metric, classify the bench as:
- `relative_only` (good for regression, bad for datasheet compare), or
- `needs_fixture_patch` (bench not exercising intended path).

Do not add metric to `DEV_MODE_SPECS` while classification is `relative_only` or `needs_fixture_patch`.

### D. Historical blind-spot pattern (PSRR class)

**Failure observed:** `meets_all=True` on seed=42 while CMRR is bench-only — same class as PSRR before envelope gate (sizer optimizes GBP/PM/iq, not CMRR).

**DV Lead checklist before "pass":**
- [ ] Metric in `DEV_MODE_SPECS` or explicitly labeled bench-only?
- [ ] pytest behavioral assertion exists or `not verified` stated?
- [ ] Sized seed reported alongside defaults?
- [ ] Any loosened tolerance in `_passes()` — grep sizer, not assumed?
- [ ] Stale deck risk — diff shows deck change if numbers shifted?

### E. Coverage gaps dv-verifier cannot close alone

From CMRR run, flagged as **Not Verified** and owned by this Lead for planning:

| Gap | When to execute | Owner |
|-----|-----------------|-------|
| PVT corners (TT/FF/SS) | After local BSIM CI job | DV Lead plans matrix; dv-verifier runs |
| Temperature sweep | Phase 3+ envelope min/max °C | Plan `.temp` list per metric |
| Monte Carlo mismatch | After single-corner stable | Plan W/L/ΔVth scatter + yield |
| Datasheet method alignment | Before envelope gate | Research + fixture patch |
| Comparator CMRR / ICMR | RS8901 envelope lacks cmrr_dB | Defer — different bench class |

---

## 2. Verification planning template (per new metric)

When Analog Design Lead proposes a bench, this Lead returns:

```markdown
## Verification plan: <metric> @ <frequency/conditions>

### Stimulus definition
- Deck A: <netlist lines>
- Deck B (if ratio): <netlist lines>
- Normalization: <formula>

### Fixture equivalence
| Datasheet condition | Bench | Match? |

### Causal sanity sweep
- Primary knob: <param> range <min–max>
- Pass if: monotonic or documented non-monotonic reason

### Gate classification
- [ ] bench-only | envelope candidate | defer

### dv-verifier commands
- <exact scripts>

### Not verified (explicit)
- <corners, MC, temp, CI pytest>
```

---

## 3. Relationship to competency ladder (`docs/analog_design_rules.md`)

| Rung | DV Lead scope today |
|------|---------------------|
| 3 — Building blocks | Single-metric ngspice benches, causal sweeps, normalization |
| 4 — System blocks | Multi-metric PVT tables, seed robustness, envelope gate readiness |
| 5 — Product-like | Corner/MC planning (execute when BSIM lands) |
| 6 — Physical test | **Out of scope** — Testing engineer role premature |

---

## 4. Next actions from CMRR dispatch (concrete)

1. Patch normalization in `opamp.py` `measure()` — owned by cursor-executor, criteria owned here.
2. Add optional `RL=10k` branch; compare CMRR delta — plan owned here, run by dv-verifier.
3. Re-classify STATUS CMRR row: `partial` / fixture `unverified` until (1)+(2) done.
4. Do **not** add `cmrr>80dB` to `DEV_MODE_SPECS` until fixture equivalence row is green.
5. Feed this entry + `docs/research/testbench_learnings/CMRR_2026-06-20.md` into next CMRR/comparator ICMR work.

---

## 5. What this Lead is not

- Not a replacement for `dv-verifier` (no command execution required).
- Not ISO/AEC-Q reporting (no fabricated part — Quality engineer premature).
- Not physical ATE (Testing engineer premature).
- Not a new orchestration layer — one blocking gate (`dv-verifier`) remains; this doc informs what that gate checks.

---

## 6. Schematic semantic acceptance gate (new)

Use this gate whenever schematic visuals are part of the claim.

### Required checks (before accepting "looks correct")

1. **Terminal identity integrity**
   - Verify pin-level mapping is preserved (no duplicate-node collapse hiding drain/gate/source terminals).
   - Diode-connected devices must show both physical terminals connected to the same net.

2. **Topology-sign correctness**
   - For op-amp classes, validate input polarity labels against small-signal sign path (not just net names).
   - Bias mirrors must be physically diode-connected where intended by topology.

3. **Render semantics**
   - No diagonal signal segments.
   - No floating passive terminal stubs.
   - No same-track visual ambiguities that can be mistaken as rail shorts without explicit junction semantics.

4. **Evidence artifacts**
   - Attach regenerated SVG from the exact run.
   - Attach connectivity + schematic + tangling pytest output verbatim.

### Gate state guidance

- If any of the above checks are missing: mark `unverified`.
- If wiring is topologically correct but visual ambiguity remains: mark `partial`.
- Only mark `working` when pin semantics, render semantics, and evidence artifacts are all present.
