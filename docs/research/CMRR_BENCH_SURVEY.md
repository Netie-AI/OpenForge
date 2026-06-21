# CMRR Bench Survey — RS321 / OpenForge ngspice precedent

**Date:** 2026-06-20  
**Agent:** analog-research (read-only)  
**Purpose:** Confirm RS321 CMRR spec and cite bench-design precedent before CMRR implementation.  
**Not in scope:** topology choice, forge/sizer edits.

---

## RS321 family CMRR spec (primary source)

**Source:** `PDF/RS321_datasheet.txt` (RS321, RS358, RS324, RS321S, RS358S)

| Field | Value |
|-------|-------|
| CMRR | **80 dB** |
| Conditions (table header) | TA = +25 °C, VS = 5 V, RL = 10 kΩ to VS/2 |
| Frequency | **Not stated** in repo extract |
| VICR at test | **Not stated** in repo extract |
| min/typ/max | **Single value only** |

**Primary quote:**

> ELECTRICAL CHARACTERISTICS (TA=+25C, VS=5V, RL=10k to VS/2)  
> CMRR Common-Mode Rejection Ratio 80 dB

**Do not conflate:** PSRR = 85 dB (same table, separate parameter).

**Inference (not primary source):** Informative bench comparison target is **≥80 dB** at header conditions; exact frequency must be chosen by executor (see Open questions).

---

## OpenForge status

| Location | CMRR state |
|----------|------------|
| `openanalog/forge/spec_envelopes.py` | **Not** in `DEV_MODE_SPECS` |
| `docs/STATUS.md` | Next PVT metric after PSRR |
| `openanalog/interface/datasheet.py` | Parses `cmrr_dB: 80.0`, mode `min` |
| `OpAmpTopology.measurable_specs()` | Omitted before the current CMRR bench work |
| `tests/test_sizer_score.py` | CMRR → N/A before measurable bench wiring |
| `docs/analog_design_rules.md` | "CM step or AC on VIN+/VIN−" |

---

## Public measurement precedents

### TI AN-1516 (SPICE Universal Test Circuits, Rev. F) — §2.3

CMRR = open-loop differential gain (ADM) / common-mode gain (ACM).

- **ACM circuit:** AC source on **both** inputs; inductor in feedback (DC short, AC open).
- **ADM circuit:** Differential AC via VCVS pair on second DUT copy.
- AC sweep → post-process ADM/ACM ratio vs frequency.
- Match datasheet VS, VCM, RL, CL.

### EDN — Ian Williams, Part 3 (input-referred errors)

Same dual-copy ADM/ACM method; intended for SPICE model verification.

### ADI MT-042 — Op Amp CMRR

- Fig 3: closed-loop diff amp — CMRR limited by **external resistor matching** (about 66 dB for 0.1% mismatch).
- Fig 4: symmetric supply shift for DC CMRR without matched resistors.

### TI Precision Labs / E2E CMRR PDF

- DC: CMRR(V/V) = ΔVos/ΔVcm.
- AC: same fixture plus post-processor on AC transfer curves.

### P.E. Allen — Simulation and Measurement of Op Amps (2018)

CMRR = Avd/Acm; open-loop measurement; separate ICMR definition.

---

## PSRR bench analogy (repo precedent)

**Pattern** (`docs/semicon-log.md` entries 4–5):

1. Separate `_build_*_deck` (does not alter main `.op`/AC deck).
2. AC stimulus magnitude `0.1` (100 mVpp).
3. `meas ac … at=100` Hz.
4. `scripts/verify_*.py` with informative datasheet comparison.
5. **Not** in `DEV_MODE_SPECS` until envelope gate decision.

**Repo files:**

- `openanalog/forge/topologies/opamp.py` — `_build_psrr_deck`; open-loop AC harness (`1T` inductor break).
- `openanalog/forge/topologies/ldo.py`, `vref.py` — PSRR decks (supply ripple).
- `scripts/verify_psrr.py` — opamp vs RS321 PSRR **85 dB** (not CMRR).

| PSRR (landed) | CMRR (proposed analog) |
|---------------|------------------------|
| Ripple on VDD | Common-mode AC/step on Vinp & Vinn |
| Inputs at VCM = VS/2 | Same VCM |
| Closed-loop implicit | **Open-loop** ADM/ACM per TI/EDN |
| `vdb(vout) at=100` | ADM/ACM ratio or CM-only open-loop |
| opamp, ldo, vref | opamp, comparator (`PARKING_LOT.md`) |

**Semicon-log lesson (entry 5):** Distinguish sizer blind spot (metric not in envelope) from structural floor (manual knob sweep cannot reach bar). Expect mirror/tail knobs (W1, W3, tail) for CMRR — analogous to W3 for PSRR — but require a causal sweep before claiming the bench is exercising that path.

---

## Datasheet ambiguities

1. **Truncated extract** — full PDF may add frequency, VICR, min/typ/max.
2. **No CMRR frequency** — 100 Hz is OpenForge PSRR convention, not RS321 primary source.
3. **RL=10k in header** — current opamp harness uses CL=10pF only, no RL.
4. **80 dB vs PSRR 85 dB** — different parameters; do not cross-compare.
5. **RS358/RS324** — grouped in title; no separate CMRR values in extract.

---

## Recommended bench conditions (aligned where possible)

| Parameter | Recommendation | Basis |
|-----------|----------------|-------|
| VS | 5 V | Datasheet header |
| VCM | VS/2 = 2.5 V | PSRR precedent + header |
| RL | 10 kΩ to VS/2 | Datasheet header |
| CL | Document choice (10 pF OpenForge default) | Repo vs TI examples |
| Frequency | 100 Hz (PSRR parity) or DC/low-freq | RS321 silent; TI says DC highest |
| Method | Open-loop ADM/ACM (TI AN-1516) | Avoids external resistor ceiling |
| Informative target | 80 dB | Datasheet extract |

---

## Open questions (for Analog Design Lead / executor)

1. Scalar bench frequency: 100 Hz vs DC?
2. Add RL=10k to opamp CMRR deck?
3. Single CM AC deck vs dual ADM/ACM per TI?
4. When to add `cmrr>80dB` to `DEV_MODE_SPECS`?
5. Full RS321 PDF for missing fields?

---

## Citations

**Repo:**

- `PDF/RS321_datasheet.txt`
- `openanalog/interface/datasheet.py`
- `openanalog/forge/spec_envelopes.py`
- `openanalog/forge/topologies/opamp.py`
- `scripts/verify_psrr.py`
- `docs/semicon-log.md` (entries 4–5)
- `docs/STATUS.md`, `docs/PARKING_LOT.md`, `docs/analog_design_rules.md`

**External:**

- TI AN-1516: https://www.ti.com/lit/an/snoa475f/snoa475f.pdf
- EDN Part 3: https://www.edn.com/designing-with-a-complete-simulation-test-bench-for-op-amps-part-3-input-referred-errors/
- ADI MT-042: https://www.analog.com/en/resources/analog-dialogue/articles/mt-042.html
- P.E. Allen: https://aicdesign.org/wp-content/uploads/2018/12/43_SimulationMesurement_of_Op_Amps181213.pdf
