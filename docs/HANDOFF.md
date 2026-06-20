# OpenForge — Session Handoff

**Updated:** 2026-06-20 (Phase 0.8 signed off; CMRR partial; governance lock)  
**HEAD (local):** `09fdcfe` on `feat/schematic-orthogonal-router`

**Structural log:** `docs/semicon-log.md` entries 2–6 — vref Option B locked; CMRR bench landed but requires normalization/fixture follow-up before acceptance.

**Read order:** this file → `docs/STATUS.md` → `docs/PARKING_LOT.md` → `AGENT_PLAN.md` §0 → `.cursor/skills/openforge-conventions/SKILL.md` → `.cursor/skills/mode-routing/SKILL.md`

Use this file at the **start of every new Cursor window**.

---

## North star (long term)

**OpenForge** = analog IC design forge: datasheet spec → ngspice-validated netlist + measured specs → (later) evolutionary topology search → (later) multitask LoRA that only ships fitness=1 designs.

Ultimate demo (Phase 5 exit): *"design me a low-Vos comparator under 1 µA"* → verifier-gated netlist with real ngspice numbers.

Broader product vision (CEO master plan tail in `AGENT_PLAN.md`): Palantir/Cadence-friendly UI, assisted editing (add a wire → re-sim → new topology class), DRC/LVS, parasitic extraction — **all gated on honest ngspice fitness=1 first.**

---

## Short term (do next)

| Priority | Task | Gate |
|----------|------|------|
| **1** | **BSIM CI proof on pushed HEAD** | `sky130-bsim-smoke` workflow job added; next push/PR must show Actions green with run URL in `STATUS.md` |
| **2** | **CMRR fixture policy decision** | RL fixture sanity done (`diag_opamp_cmrr_fixture.py`); choose production fixture path (base vs RL) and keep `bench-only` until datasheet-equivalence is proven |
| **3** | **UI E2E (human tick)** | `docs/UI_E2E_CHECKLIST.md` — agent PASS 2026-06-20; footer git hash DOM bug optional fix |
| **4** | **Schematic tangling reduction follow-up** | Keep 0.8 router path; reduce opamp `crossing_score` from 6 toward `<=3` without regressing `tests/test_schematic_connectivity.py` |
| Parking lot | Schematic drag-reroute, vref iq architecture (Option A) | After PVT tail; see § vref decision |

**Do NOT start:** Phase 4/5, LoRA, cross-repo Cursor brain, layout/DRC/LVS, PLL/SerDes/standard-cells/high-speed IO (`PARKING_LOT.md` § out of scope).

### Phase 3 vref — decision locked (**Option B**, 2026-06-20)

**Evidence:** `scripts/diag_vref_iq_breakdown.py` + `scripts/verify_phase3_vref.py` (end-to-end; exit 1 on iq = honest fail, not crash).

| Run | iq µA | vref V | line_reg mV |
|-----|-------|--------|-------------|
| defaults | 203.8 | 1.146 | 1.30 |
| manual amp floor (`iref_amp=1 µA`) | **166.0** | 1.152 | 0.69 |
| sized (seed=42, budget=80) | 138.5 | 1.196 | 1.25 |

**Verdict:** iq **not closable by sizing alone** — structural floor ~166 µA (PMOS mirror + BJT stack). Dead `ibias_uA` sizer knob removed.

**Decision: Option B — honest partial.** Topology + real error amp validated; **iq remains open** on level-1 BJT placeholders. Do **not** burn seeds or param sweeps on iq now. Revisit **Option A** (bias architecture redesign) only when (1) RS431 iq is a hard demo gate, or (2) real SKY130 BJT cards land.

**Next engineering:** PVT/testbench expansion (not vref iq redesign).

### Recently done (this session chain)

| Item | Notes |
|------|-------|
| 0.7 connectivity + IO stubs | Verifier caught 16px gap; tests 10/10 |
| 0.8 stub-then-fold sign-off | Parent + `dv-verifier` rerun complete: `pytest tests/test_schematic_connectivity.py -v` **14/14 pass**; `logs/schematic_0.8_*.svg` vs 0.7 confirms terminal-stub deltas (`0→21`, `0→20`) |
| UI hotfix | `renderError()` restored after JS corruption |
| Docs | `PARKING_LOT.md`, `UI_E2E_CHECKLIST.md`, `SESSION_NOTES.md`, etc. |
| VCVS → real error amp | vref topology validated; **iq still open** |
| BSIM smoke + CI wiring | Local rerun `OPENFORGE_MODEL_SET=sky130 OPENFORGE_SKY130_CARD=bsim python scripts/smoke_all.py 80` = 5/5 pass (`vref` deferred); `.github/workflows/ci.yml` now includes `sky130-bsim-smoke` job (Actions proof pending push) |
| Schematic tangling guard | Added `openanalog/eda/schematic_geometry.py`, opamp placement-variant scoring in `schematic_layout.py`, and `tests/test_schematic_no_tangling.py` (**5 passed**). Chosen variant `tail_aligned`; `nb` x-span **300→174**; residual `crossing_score=6` still open |
| Agentic EDA survey | `docs/research/AGENTIC_EDA_SURVEY.md` |
| Cursor conventions | `.cursor/skills/openforge-conventions/SKILL.md` |

---

## Progress snapshot

### Phase 0 — Infrastructure ✅

| Item | Status |
|------|--------|
| 0.4 ngspice reachability (WSL) | ✅ |
| 0.5 rendering | ✅ |
| 0.6 schematic floorplan | ✅ |
| 0.7 connectivity verification | ✅ |
| 0.8 gate-stub-then-fold router | ✅ signed off (parent + `dv-verifier` + artifact compare) |
| CI on Linux + ngspice behavioral job | ✅ |

### Phase 1 — THE GATE (four dev-mode categories vs `spec_envelopes.py`)

| Phase | Category | Part | Status | Verification script |
|-------|----------|------|--------|---------------------|
| **1a** | comparator | RS8901 | ✅ `working` | `scripts/verify_phase1a.py` |
| **1b** | analog_switch | RS2105 | ✅ `working` | `scripts/verify_phase1b.py` |
| **1c** | charge_pump | RS2660 | ✅ `working` | `scripts/verify_phase1c.py` |
| **1d** | opamp | RS321 | ✅ `working` (seed=42) | `scripts/verify_phase1d.py` |

**Phase 1 exit criteria** (`AGENT_PLAN.md`): all four `working` + `make smoke-wsl` + CI behavioral tests green on pushed HEAD.

---

## Environment (this host)

```powershell
# Windows — ngspice NOT on PATH; use WSL Ubuntu
$env:OPENFORGE_WSL_DISTRO='Ubuntu'

# Simulation venv (WSL)
wsl -d Ubuntu bash -lc "cd /mnt/c/Users/oojia/OpenForge && source .venv_wsl/bin/activate && python scripts/verify_phase1c.py"

# Web server (Windows)
cd C:\Users\oojia\OpenForge
.venv\Scripts\Activate.ps1
python -m openanalog.web
# → http://127.0.0.1:8080  (added openanalog/web/__main__.py this session)

# Alternate port if 8080 blocked
python -m openanalog serve --host 127.0.0.1 --port 8090

# Full smoke (WSL)
make smoke-wsl

# Behavioral tests only (WSL or Linux CI)
python -m pytest tests/test_ngspice_behavior.py -v
```

| Resource | Location |
|----------|----------|
| Fitness bar (only bar) | `openanalog/forge/spec_envelopes.py` → `DEV_MODE_SPECS` |
| Honest status | `docs/STATUS.md` |
| Agent execution order | `AGENT_PLAN.md` |
| Secrets | `env.local` — **never commit** |
| Training corpus | `data/training/winners.jsonl` — fitness=1 only |
| CI workflow | `.github/workflows/ci.yml` — unit tests + ngspice behavioral job |

**Rule 8:** Never add a second looser tolerance. Never mark a phase done without **Actions green on pushed HEAD**.

---

## Phase 1 lessons (apply to 1d)

1. **Diagnose before sizing** — large misses often mean wrong bench or topology bug, not "try more seeds."
2. **Show causal evidence** — param diffs, netlist structure identity, seed sweep, re-measure historical failures.
3. **Historical numbers may be stale** — comparator 8 µs was old tran deck (`99d68df`); switch 834 Ω was S/D swap (`175da53`); charge pump 4.27 V was pre-bootstrap (`8297008`).
4. **Behavioral test must assert real ngspice metrics** — not `_design()` pass alone.
5. **CI green ≠ claim true** — verify underlying cause, then push, then check Actions tab.

---

## What this session closed vs left open

### Closed (with evidence)
- **0.7 verifier:** IO stubs must reach terminals; parser fix for `class="signal-wire io-stub"`; tests caught 16px gap then passed after fix.
- **SVG emitter:** Valid CSS classes; dynamic IO stub coords; golden logs `logs/schematic_0.7_*.svg`.
- **0.8 router + sign-off:** `terminal_stub()` + orthogonal routing — `logs/schematic_0.8_orthogonal_*.svg`; parent + `dv-verifier` rerun `pytest tests/test_schematic_connectivity.py -v` (14/14), with SVG compare showing terminal-stub markers in 0.8 only.
- **UI hotfix:** Restored `renderError()` after JS corruption; `node --check` on embedded script.
- **Docs:** `PARKING_LOT.md`, `UI_E2E_CHECKLIST.md`, `analog_design_rules.md` (stub rule), `SESSION_NOTES.md`, `VERIFY_BRIEF.md`.

### Open (real gates)
- **PVT / testbench metrics** — **PSRR @ 100 Hz landed** (`verify_psrr.py`). **CMRR bench remains `partial`** (`verify_cmrr.py`): normalization fixed and RL fixture sanity run (`diag_opamp_cmrr_fixture.py`), but datasheet-equivalence remains unverified (see `STATUS.md` / `semicon-log.md`).
- **BSIM in CI** — workflow wired (`sky130-bsim-smoke`), but no pushed-HEAD Actions proof URL yet.
- **Schematic tangling residual** — placement pressure mitigation landed, but opamp `crossing_score` still 6 (target `<=3`) under current router.
- **vref iq** — documented open (Option B); verify gate exits 1 honestly — not a sizing sprint.

### Discipline reminders
- Passing connectivity tests ≠ schematic looks good ≠ UI loads.
- UI churn caused a startup crash — always run `UI_E2E_CHECKLIST.md` after `index.html` edits.
- Generic external roadmaps restate `AGENT_PLAN.md` — fold to parking lot, don’t panic-replan.
- Governance ownership lock: treat `.cursor/agents/`, `.cursor/rules/`, and `.cursor/skills/` as owner-managed; executor agents do not modify them unless explicitly instructed by owner.
- Mode routing: composer-mode requires Claude verification before gate progression; non-composer (Codex) mode may complete locally with `dv-verifier` + parent re-run evidence.
- Shorthand contract: user `continue` = execute next step now; user `continue and next window` = execute now and output next-window snippet (files + skills/rules + agent pipeline).

---

## Copy-paste — next **Cursor** window (executor)

```
Read first: docs/HANDOFF.md, docs/PARKING_LOT.md (Do next only), .cursor/skills/openforge-conventions/SKILL.md, .cursor/skills/mode-routing/SKILL.md

You are the executor. Do NOT expand scope.

Sequence:
1. BSIM CI proof: push/PR and record first green `sky130-bsim-smoke` Actions URL in `docs/STATUS.md`.
2. CMRR fixture policy decision — keep bench-only until datasheet-equivalence is proven (`diag_opamp_cmrr_fixture.py` evidence already landed).
3. Schematic tangling follow-up: keep `route_nets()` path, reduce opamp `crossing_score` from 6 toward `<=3`, preserve `tests/test_schematic_connectivity.py` green.

Do NOT: vref iq sizing sweeps (Option B locked), Phase 4/5, LoRA, PLL/SerDes/vision→corpus, layout/DRC/LVS.
Do NOT: edit `.cursor/agents`, `.cursor/rules`, `.cursor/skills` (owner-managed governance files).
If user says "continue", execute next step now (not plan-only).
If user says "continue and next window", execute now and finish with a concise next-window handoff snippet.

Evidence: paste command output, diff, or artifact paths. Zero-trust — no "trust me" summaries.

Env: WSL Ubuntu + .venv_wsl for ngspice; Windows .venv for web (python -m openanalog.web).
```

---

## Copy-paste — next **Claude** window (reviewer / gatekeeper)

```
Read first: docs/HANDOFF.md, docs/STATUS.md, docs/PARKING_LOT.md

You are the reviewer, not the patch author. Gate acceptance on evidence.

This session context:
- vref Option B locked — topology validated, iq open on placeholder BJTs; verify exits 1 on iq (honest).
- Next engineering: PVT/testbench expansion, not vref redesign.
- 0.8 router signed off with parent + `dv-verifier` reruns; STATUS updated with 14/14 pytest + SVG deltas.
- PARKING_LOT: PSRR/CMRR/THD/PVT + out-of-scope (PLL/SerDes/vision→corpus).

When Cursor returns work, check:
1. Real ngspice bench output for new metric (not stub pass alone)
2. git diff / pytest output / STATUS update consistency
3. No scope creep into Phase 4+ or tooling mega-setup

Push back on: restated roadmaps, "tests passed" without output, UI claims without browser check.
```

---

## Key files touched recently

| Area | Files |
|------|-------|
| Schematic 0.7/0.8 | `openanalog/eda/schematic_layout.py`, `schematic_router.py`, `schematic_connectivity.py`, `symbols.py` |
| Tests | `tests/test_schematic_connectivity.py` |
| Golden SVGs | `logs/schematic_0.7_*.svg`, `logs/schematic_0.8_orthogonal_*.svg` |
| Web UI | `openanalog/web/index.html`, `app.py`, `__main__.py` |
| Docs | `docs/PARKING_LOT.md`, `UI_E2E_CHECKLIST.md`, `SESSION_NOTES.md`, `analog_design_rules.md`, `VERIFY_BRIEF.md` |
| Phase 3 vref | `scripts/verify_phase3_vref.py`, `docs/semicon-log.md` |

---

## Copy-paste prompt — legacy (Phase 3 only)

```
Read docs/HANDOFF.md and docs/STATUS.md first.

Phase 1–2 closed. Phase 3: BSIM 5/5 smoke on pinned v0.13.0 (local only).
Evidence: evidence/phase3_*_2026-06-19.log

Next (legacy note): vref bandgap on SKY130 BJTs, then BSIM CI follow-up. Current active priority is higher in this file: capture first green pushed-HEAD `sky130-bsim-smoke` Actions proof URL.
Do NOT start Phase 4/5 or LoRA training.
Zero-trust: done = real artifacts checked, not summaries.
Environment: WSL Ubuntu, .venv_wsl, OPENFORGE_WSL_DISTRO=Ubuntu.
```

---

## Key commits (forensics)

| Commit | What it fixed |
|--------|----------------|
| `99d68df` | Comparator tran deck (8 µs → ~0.2 µs on same params) |
| `175da53` | Switch PMOS/NMOS S/D orientation (834 Ω → ~23 Ω) |
| `8297008` / `2c90319` | Charge pump bootstrapped NMOS Dickson (4.27 V → ~5 V) |
| `7f1947e` | CI `win_path_to_wsl` on Linux runners |
| `828b7d0` | Phase 1a RS8901 behavioral CI gate |
| `2390957` | Phase 1b RS2105 behavioral CI gate |
| (Phase 1c) | `4c57f63` — RS2660 behavioral CI gate, handoff doc |

---

## Files changed this session (Phase 1c)

- `tests/test_ngspice_behavior.py` — `test_charge_pump_meets_rs2660_bar`
- `scripts/verify_phase1c.py` — reproducible evidence
- `docs/STATUS.md` — Phase 1c section
- `docs/HANDOFF.md` — this file
