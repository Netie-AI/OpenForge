# Semicon log — structural questions before sizing

Discipline: write the structural question and prediction **before** parameter sweeps, so idealizations cannot be mistaken for topology wins.

---

## Entry 1 — Phase 3 vref bandgap (2026-06-19)

**Status:** partial progress, two stacked idealizations — not a validated real circuit yet.

### What changed (real)

- Resistor-divider placeholder replaced by a **PTAT/CTAT bandgap structure** on SKY130 substrate PNPs (`openanalog/forge/topologies/vref.py`, `sky130_bandgap`).
- Failures reported honestly: **line_reg** and **iq** still miss RS431 bar after sizing attempt — not buried.

### Elevated caveat (not a footnote)

The bandgap loop amplifier is a **VCVS** (`Eop`), not a transistor differential error amp:

```62:64:openanalog/forge/topologies/vref.py
def _error_amp(ms: ResolvedModels) -> str:
    """Bandgap loop amplifier — VCVS servo (structural; MOS opamp sizing is follow-on)."""
    return "* bandgap error amp: force PTAT node ra1 ≈ CTAT emitter qp1\nEop net2 0 ra1 qp1 {OPAMP_GAIN}\n"
```

An ideal infinite-gain behavioral element perfect-servos the PTAT/CTAT balance. The clean **`vref_V ≈ 1.200 V`** result is therefore **very likely an artifact of ideal servo action**, not evidence the topology is dialed in.

**Second idealization:** BJT cards are **level-1 placeholders** (`SKY130_MODELS_BUILTIN` in `openanalog/sim/models.py`). Real fetched NPN corner files 404'd. Same caveat tier as early "5/5 SKY130" on hand-written MOSFET cards — disclosed proactively this time, but still not silicon validation.

**Net:** two idealizations stacked (placeholder BJTs + ideal error amp), not one real circuit with two metrics left to tune.

### Prediction (log now, check later)

When the VCVS is replaced by a **real NMOS/PMOS differential error amp** (even minimal):

- **Expect** `vref` accuracy to get **worse before it re-converges** — finite gain, offset, and bias-dependent behavior all degrade the ideal case.
- If `vref` **stays** clean without explanation, that is worth understanding (why the ideal case transferred), not silently accepting.

Same prediction applies to **line_reg**: ideal amp may be masking loop dynamics that a real amp exposes.

### Next structural step (before further sizing)

1. Swap VCVS → minimal differential-pair error amp in the bandgap loop.
2. Re-run `scripts/verify_phase3_vref.py` (defaults + sized).
3. Compare `vref_V`, `line_reg_mV`, `iq_uA` against this entry's prediction.

**Interpretation gate:**

| Outcome | Meaning |
|---------|---------|
| Metrics degrade as predicted, then recover with sizing | Topology validated; remaining work is real opamp sizing |
| `vref` or `line_reg` fall apart with real amp and do not recover | Topology problem the VCVS was masking — not a sizing problem |

### Evidence pointers

- Topology: `openanalog/forge/topologies/vref.py`
- Verify: `scripts/verify_phase3_vref.py`
- BJT placeholder: `openanalog/sim/models.py` (`SKY130_MODELS_BUILTIN`, lines 29–31)
- STATUS (phase gate): `docs/STATUS.md` § Phase 3 vref bandgap

---

## Entry 2 — Real diff-pair error amp replaces VCVS (2026-06-19)

**Status:** topology **structurally validated** — loop converges with real MOS amp; remaining gap is **iq** (and default vref margin), not topology revision.

### Change

- Removed `Eop` VCVS and net2 `Iref`/`n0` bias shim.
- Inserted **opamp input-stage reuse**: `emit_diff_pair` + `emit_pmos_load` + tail bias (`ea1–ea8` in `vref.py`), opamp-default W/L (`W1=8 µm`, `IREF_AMP=15 µA`).
- `net2` remains PMOS mirror gate (p1–p3) and diff-amp single-ended output.

### VCVS baseline (same session, pre-swap)

| Run | vref_V | line_reg_mV | iq_uA |
|-----|--------|-------------|-------|
| defaults | 1.197 | 28.13 | 181.4 |
| sized (seed=42, budget=80) | 0.752 | 5.62 | 61.2 |

### Real-amp result (`verify_phase3_vref.py`, SKY130 level-1 BJT placeholders)

| Run | vref_V | line_reg_mV | iq_uA | `.op` |
|-----|--------|-------------|-------|-------|
| defaults | **1.146** | **1.30** | 203.8 | converged; V(ra1)≈V(qp1)≈0.699 V |
| sized (seed=42, budget=80) | **1.196** | **1.25** | 138.5 | converged |

Evidence: `evidence/phase3_vref_real_amp_2026-06-19.log`

### vs prediction (entry 1)

| Metric | Predicted | Observed |
|--------|-----------|----------|
| vref (defaults) | worse before re-converge | **Slightly worse** (1.197→1.146, −51 mV) — not collapse |
| line_reg | likely worse | **Wrong direction — improved** (28.1→1.3 mV, now **passes** `<5 mV` bar) |
| iq | (not predicted) | **Worse** (181→204 µA defaults; sized 61→138 µA) |
| loop convergence | if `.op` fails → topology revision | **`.op` clean** — loop self-biases with finite amp |

**Why line_reg improved (hypothesis):** VCVS + `n0`/net2 bias shim may have over-driven the mirror gate; real amp provides finite-gain servo with physical output impedance, reducing supply sensitivity. Needs follow-up if iq sizing exposes interaction.

### Interpretation

- **Topology validated:** BJT PTAT/CTAT stack + PMOS mirror + **real** diff-pair loop holds ~1.15–1.20 V without ideal servo.
- **Not a topology revision case** — do not revert to VCVS.
- **Open metrics:** `iq_uA` misses RS431 (`<100 µA`) on both default and sized runs; default `vref_V` is 34 mV below 1.18 V floor (sized lands in band).
- **Next:** amp + mirror **sizing** to close iq (and default vref margin) — structural gate passed.

### `ok=False` vs clean `.op` (reconciled)

`verify_phase3_vref.py` prints `defaults: ok=False` while ngspice `.op` converges. These are **different gates**:

| Signal | Meaning |
|--------|---------|
| `.op` converges, V(ra1)≈V(qp1) | Loop is **structurally closed** and self-biasing |
| `TopologyMetrics.ok` (`vref.py` line 206) | Narrow **vref-only** band: `1.18 ≤ vref_V ≤ 1.22` |
| `design()` / `meets_all` | Full **RS431 envelope**: vref + line_reg + iq |

Defaults with real amp: **vref=1.146 V** (34 mV below `ok` floor), **line_reg=1.3 mV** (passes RS431), **iq=204 µA** (fails RS431). So `ok=False` is **vref margin**, not simulation failure — consistent with clean `.op`.

---

## Entry 3 — vref iq: sizing vs structural floor (2026-06-20)

**Standing rule (Phase 3+):** Before param sweeps on iq (or any large miss vs envelope), run a **manual causal sweep** on the suspected bias paths. If the best manual point is still far from bar, stop sizing — it is structural, not a seed/budget problem. Same discipline as Phase 1a comparator (bench fix before sizing).

### Question

Is the iq gap closable by **error-amp bias sizing alone**, or is the real diff-pair amp a **permanent current floor** the topology cannot avoid at RS431 `<100 µA`?

### Method

`scripts/diag_vref_iq_breakdown.py` — defaults + manual `VRefParams` sweeps + sizer seed=42 budget=80 (no schematic).

### Results (SKY130 level-1 BJT placeholders)

| Case | iq_uA | vref_V | line_reg_mV |
|------|-------|--------|-------------|
| defaults | **203.8** | 1.146 | 1.30 |
| iref_amp 3 µA | 171.2 | 1.150 | 0.88 |
| iref_amp 1 µA | **166.0** | 1.152 | 0.69 |
| mirror_w 4 µm | 201.7 | 1.140 | 1.71 |
| ibias 1 µA | 203.8 | 1.146 | 1.30 |
| sized (seed=42) | **138.5** | 1.196 | 1.25 |

### Interpretation

| Finding | Meaning |
|---------|---------|
| `iref_amp_uA` 15→1 µA saves ~38 µA but **floor ≈166 µA** | Amp tail bias is **not** the dominant term; PMOS mirror + BJT stack dominate |
| `ibias_uA` / `mirror_w_um` sweeps ≈ no change | Removed dead `ibias_uA` from `param_ranges` + netlist (was unwired — sizer no-op) |
| Sizer hits **138.5 µA** — still +38% over bar | Budget=80 explored resistor/mirror space; **cannot reach 100 µA** from current topology + param_ranges |
| Miss magnitude (+38–104%) | **Not a small sizing miss** — do not burn cycles on seed sweeps expecting iq to land |

**Verdict:** iq failure is **structural at current topology level**, not “one more sizing seed.”

**Decision (2026-06-20): Option B — honest partial.** Record iq open on placeholder BJTs; defer architecture redesign until real BJT cards or hard RS431 iq demo. **Next project work:** PVT/testbench expansion (PSRR/CMRR/THD), not vref iq sizing.

### Evidence

- `scripts/diag_vref_iq_breakdown.py`
- `scripts/verify_phase3_vref.py` (end-to-end; exit 1 on iq)

---

## Entry 4 — PSRR @ 100 Hz bench (2026-06-20)

**Status:** bench landed — **not** added to `DEV_MODE_SPECS` fitness gate yet.

### Pattern

AC ripple on supply (`dc VDD ac 0.1`), inputs at bias (opamp: VCM; LDO: closed loop; vref: bandgap output), `meas ac psrr_db find vdb(node) at=100`. Same pattern as existing LDO `_build_ac_deck`.

### Results (`scripts/verify_psrr.py`)

| Category | psrr_dB (defaults) | psrr_dB (sized) | vs product |
|----------|-------------------|-----------------|------------|
| opamp | 20.0 | 54.7 (s42) | RS321 typ 85 dB — **open** |
| ldo | 102.7 | 110.3 (s7) | strong |
| vref | 86.1 | — | iq still Option B |

**Interpretation:** PSRR infrastructure works. LDO/vref strong. Opamp gap is **not** a vref-iq-style structural floor — see entry 5.

### Evidence

- `openanalog/forge/topologies/opamp.py` — `_build_psrr_deck`
- `openanalog/forge/topologies/vref.py` — `_build_psrr_deck` (separate ngspice run; **does not alter** main bandgap `.op`/DC bias deck)
- `scripts/verify_psrr.py`

---

## Entry 5 — Opamp PSRR gap: sizer blind spot, not structural floor (2026-06-20)

**Question:** Is RS321 85 dB PSRR closable by sizing, or Option-B defer?

**Method:** `scripts/diag_opamp_psrr_breakdown.py` — manual param sweeps + compare to sized seed=42 (RS321 fitness, no PSRR in envelope).

### Causal sweep (bundled L1, PSRR @ 100 Hz)

| Knob | psrr_dB | Notes |
|------|---------|-------|
| defaults | 20.0 | W3=8 µm |
| Cc 0.5–10 pF | 20.0 | Miller cap **does not move** PSRR at this bench |
| Iref 5 µA | 20.0 | Bias current irrelevant |
| W6 120 µm | 20.0 | Output stage width irrelevant |
| **W3 30 µm** | **66.5** | PMOS mirror load — **dominant knob** |
| W3 60 µm | 75.7 | |
| W3 100 µm | 80.1 | |
| W3 150 µm | **83.1** | Within ~2 dB of RS321 85 dB typ |
| sized s42 (RS321 gate) | 54.7 | Sizer trades W3 for GBP/PM/iq — **not optimizing PSRR** |

**Mechanism (hypothesis):** Supply ripple on `VDD` couples through PMOS mirror load (M3/M4, `{W3}`) into the diff-pair tail/output. Wider mirror load ↑ rejection. Not a separate architecture problem — mirror sizing tradeoff the RS321 sizer doesn't see.

### Decision

| | |
|---|---|
| **Not Option B** | Manual W3 sweep reaches **83 dB** — gap is closable on bundled L1 |
| **Deferred from fitness gate** | PSRR not in `DEV_MODE_SPECS`; seed=42 `meets_all=True` while PSRR=54.7 dB is expected |
| **Reopen when** | (1) add `psrr>85dB` to RS321 envelope + sizer weights, or (2) dedicated PSRR sizing session (W3↑ with GBP/PM guard), or (3) BSIM card where mirror ro differs |

**Do not:** burn blind seed sweeps expecting PSRR to move under current envelope — same discipline as vref iq, but here the fix is **envelope + W3**, not topology redesign.

### Evidence

- `scripts/diag_opamp_psrr_breakdown.py`
- `scripts/verify_psrr.py` (raw stdout in STATUS sign-off)

---

## Entry 6 — CMRR @ 100 Hz bench (2026-06-20)

**Status:** bench landed for opamp only — **not** added to `DEV_MODE_SPECS` fitness gate.

### Pattern

Open-loop common-mode AC drive on both inputs (no feedback harness): `Vinp vinp 0 dc {VCM} ac 0.1`, `Vinn vinn 0 dc {VCM} ac 0.1`, then `meas ac acm_db find vdb(vout) at=100`. After `dv-verifier` review, CMRR normalization was corrected for AC-amplitude mismatch (`ac` diff=1 vs CM=0.1): `cmrr_dB = aol_db_100 - (acm_db + 20)`.

### Results (`scripts/verify_cmrr.py`, `scripts/diag_opamp_cmrr_breakdown.py`)

| Case | cmrr_dB | Notes |
|------|---------|-------|
| defaults | **152.0** | corrected from prior +20 dB artifact; RS321 typ reference 80 dB |
| sized s42 (RS321 gate) | **151.4** | `meets_all=True`; CMRR still not part of gate |
| Cc sweep (0.5–10 pF) | 148.1–152.3 | mild change |
| Iref=5 µA | 163.2 | stronger rejection |
| W3 sweep (8→150 µm) | 143.4–162.8 | non-monotonic low point at W3=30 |
| W6=120 µm | 168.4 | highest in this quick sweep |

### Tail / bias causal sweep (`scripts/diag_opamp_cmrr_breakdown.py`, 2026-06-20 rerun)

Parallel to PSRR W3 sweep — sweep tail (M5) and bias mirror (M8 on `nb`) geometry vs CMRR, reporting both open-loop and `RL=10k` fixture columns:

| Sweep | CMRR range (open-loop) | CMRR range (rl10k) | Notes |
|-------|------------------------|--------------------|-------|
| **Lb (M8)** 0.5→8 µm (bundled) | **159.5 → 125.5 dB** | 137.6 → 118.6 dB | **Strongest causal knob** — shorter Lb inflates CMRR; rl10k gap narrows at long Lb |
| **Lb (M8)** 0.5→8 µm (**sky130/BSIM**) | **168.4 → 135.7 dB** | 142.8 → 128.1 dB | Same Lb causality on BSIM; **more** inflated at short Lb than bundled L1 (168.4 vs 159.5 @ Lb=0.5) |
| L5 (M5 tail) 0.5→8 µm | 142.7 → 156.4 dB | 119.1 → 147.1 dB | Non-monotonic open-loop; **rl10k rises with L5** (opposite trend) |
| W5 (M5 tail) 4→64 µm | 142.7 → 155.2 dB | 119.1 → 134.7 dB | Weak / non-monotonic |
| W3 (PMOS load) 8→150 µm | 143.4 → 162.8 dB | 127.4 → 152.3 dB | PSRR tracks W3 (20→83 dB); CMRR moves less consistently |

**Interpretation:** **Lb** (M8 bias stack Ro) is causally confirmed on both bundled L1 and SKY130 BSIM — shorter Lb inflates CMRR. The prior “bundled-model-only artifact” hypothesis is **refuted**: BSIM is **worse** at short Lb (168.4 dB vs 159.5 dB @ Lb=0.5). PSRR stays flat **20.0 dB** across the BSIM Lb sweep while CMRR remains 136–168 dB — same internal inconsistency as bundled. The loaded fixture is consistently more pessimistic (~15–25 dB on bundled defaults) but still far above RS321 typ 80 dB — so neither fixture is datasheet-validated yet. **Do not lock production-fixture policy** until equivalence is proven (same discipline as pre–Option B vref iq). Next axis: why open-loop CM drive yields ACM so small that normalized CMRR lands 55–88 dB above datasheet; RS321 RL=10k feedback fixture may be required before envelope compare.

### Fixture sanity (`scripts/diag_opamp_cmrr_fixture.py`)

Datasheet header includes `RL=10k` to `VS/2`. Added diagnostic path in `_build_cmrr_deck(..., rl_to_vcm_ohm=...)` and compared:

| Case | base cmrr_dB | rl=10k cmrr_dB | delta |
|------|---------------|----------------|-------|
| defaults | 152.0 | 127.4 | -24.6 dB |
| sized s42 | 151.4 | 142.4 | -9.0 dB |

Interpretation: RL materially changes measured CMRR but still leaves values far above RS321 typ 80 dB. This resolves one fixture dimension (load), not full datasheet-equivalence.

### ACM noise-floor probe (`scripts/diag_opamp_cmrr_acm_floor.py`, 2026-06-20)

Claude reviewer gate before further sweeps: confirm CM-AC output is real signal, not dB-of-near-zero artifact.

| Lb | Model | acm_vm @100 Hz | stim_ok | phase_ok | Verdict |
|----|-------|----------------|---------|----------|---------|
| 0.5 | bundled | **69.5 µV** | yes (0.1000 V both inputs) | yes (0° Δ) | Real signal |
| 1.0 | bundled | **98.0 µV** | yes | yes | Real signal |
| 8.0 | bundled | **272 µV** | yes | yes | Real signal |
| 0.5 | BSIM | **46.9 µV** | yes | yes | Real signal |
| 8.0 | BSIM | **185 µV** | yes | yes | Real signal |

Harness confirmed: `Vinp vinp 0 dc {VCM} ac 0.1`, `Vinn vinn 0 dc {VCM} ac 0.1` — both nodes at **0.1000 V** magnitude, **-20.0 dB**, **0° phase delta** at 100 Hz. **Noise-floor hypothesis refuted** (acm_vm ≫ 1 nV). Lb sweep Δ pattern is real ACM variation, not simulator floor division. Remaining gap vs RS321 typ 80 dB is **not** explained by near-zero ACM — next axis: feedback/fixture equivalence (RL=10k harness matching datasheet conditions).

### Decision

CMRR bench is measurable and normalization-corrected, but **not closed**. 152 dB open-loop magnitude is not physically credible for this topology on bundled or BSIM models; tail/bias Ro (especially M8 **Lb**) is confirmed causal but does not bring numbers toward RS321 typ 80 dB. Remains bench-only until fixture-equivalence is explicitly resolved. **No production-fixture policy lock.**

### Evidence

- `openanalog/forge/topologies/opamp.py` — `_build_cmrr_deck`, `aol_db_100`, and `cmrr_dB` wiring
- `scripts/verify_cmrr.py`
- `scripts/diag_opamp_cmrr_breakdown.py` — `--lb-only` for BSIM follow-up; `OPENFORGE_MODEL_SET=sky130 OPENFORGE_SKY130_CARD=bsim python scripts/diag_opamp_cmrr_breakdown.py --lb-only` (parent + dv-verifier rerun 2026-06-20)
- `scripts/diag_opamp_cmrr_acm_floor.py` — raw `acm_vm` + input stimulus probe (parent rerun 2026-06-20)
