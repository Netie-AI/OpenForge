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
