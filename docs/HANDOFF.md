# OpenForge — Session Handoff

**Updated:** 2026-06-20  
**HEAD (local):** `d48da02` — Phase 3 vref real amp + verify gate fix + session handoff docs

**Structural log:** `docs/semicon-log.md` entry 2 — real diff-pair amp in vref loop; topology validated, **iq open**.

**Read order:** this file → `docs/STATUS.md` → `docs/PARKING_LOT.md` → `AGENT_PLAN.md` §0 → `.cursor/.skills/SKILL.md`

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
| **1** | **UI E2E browser check** | Agent 2026-06-20: op-amp Design Chip PASS on fresh server (`065abb0`). Human should tick `docs/UI_E2E_CHECKLIST.md`; footer git hash DOM bug remains. |
| **2** | **Phase 3 vref topology decision** | Verify gate restored (`verify_phase3_vref.py` exit 1 = honest iq fail). **Decision:** lower mirror/BJT bias architecture vs documented honest-partial on placeholder BJTs — see § vref engineering brief below. **Not** more sizing seeds. |
| **3** | **Phase 0.8 schematic sign-off** | Code landed (`50da5f5`, `schematic_router.py`); run `pytest tests/test_schematic_connectivity.py -v`; compare `logs/schematic_0.8_*.svg` vs 0.7; update STATUS 0.8 row if evidence clean |
| **4** | **BSIM CI job** | After vref local stable — GitHub Actions still bundled-only for SKY130 (`STATUS.md`) |
| Parking lot | Everything else | `docs/PARKING_LOT.md` — PSRR/CMRR/THD, PVT/MC, layout/PEX; **one session each** |

**Do NOT start:** Phase 4/5, LoRA, cross-repo Cursor brain, layout/DRC/LVS, PLL/SerDes/standard-cells/high-speed IO (`PARKING_LOT.md` § out of scope).

### Phase 3 vref — engineering brief (open gate)

**Evidence (2026-06-20):** `scripts/diag_vref_iq_breakdown.py` + `scripts/verify_phase3_vref.py` (end-to-end; exit 1 on iq is honest fail).

| Run | iq µA | vref V | line_reg mV |
|-----|-------|--------|-------------|
| defaults | 203.8 | 1.146 | 1.30 |
| manual amp floor (`iref_amp=1 µA`) | **166.0** | 1.152 | 0.69 |
| sized (seed=42, budget=80) | 138.5 | 1.196 | 1.25 |

**Verdict:** iq **not closable by sizing alone** — PMOS mirror + BJT stack dominate. Dead sizer knob `ibias_uA` removed (was in `param_ranges` but unwired).

**Decision (pick one before more iq work):**

| Option | Action | When to choose |
|--------|--------|----------------|
| **A — Architecture change** | Redesign bias path (shared tail, lower mirror current, loop-gain tradeoff) | RS431 `<100 µA` bar stays the gate |
| **B — Honest partial** | STATUS: topology proven, iq open on placeholder BJTs | Defer iq until real BJT cards + architecture pass |

**After decision:** PVT/testbench (PSRR/CMRR/THD) first new capability. Schematic drag-reroute **after** vref, not interleaved.

### Recently done (this session chain)

| Item | Notes |
|------|-------|
| 0.7 connectivity + IO stubs | Verifier caught 16px gap; tests 10/10 |
| 0.8 stub-then-fold (code) | `schematic_router.py` on HEAD `065abb0`; STATUS sign-off pending |
| UI hotfix | `renderError()` restored after JS corruption |
| Docs | `PARKING_LOT.md`, `UI_E2E_CHECKLIST.md`, `SESSION_NOTES.md`, etc. |
| VCVS → real error amp | vref topology validated; **iq still open** |
| Opamp/switch BSIM (local) | 5/5 smoke; CI gap remains |
| Agentic EDA survey | `docs/research/AGENTIC_EDA_SURVEY.md` |
| Cursor conventions | `.cursor/.skills/SKILL.md` |

---

## Progress snapshot

### Phase 0 — Infrastructure ✅

| Item | Status |
|------|--------|
| 0.4 ngspice reachability (WSL) | ✅ |
| 0.5 rendering | ✅ |
| 0.6 schematic floorplan | ✅ |
| 0.7 connectivity verification | ✅ |
| 0.8 gate-stub-then-fold router | ✅ code on HEAD; STATUS sign-off pending |
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
- **0.8 router (committed):** `terminal_stub()` + orthogonal routing — `logs/schematic_0.8_orthogonal_*.svg`; `verify_terminal_stubs` in connectivity tests.
- **UI hotfix:** Restored `renderError()` after JS corruption; `node --check` on embedded script.
- **Docs:** `PARKING_LOT.md`, `UI_E2E_CHECKLIST.md`, `analog_design_rules.md` (stub rule), `SESSION_NOTES.md`, `VERIFY_BRIEF.md`.

### Open (real gates)
- **Human UI E2E** — not verified in browser this session after hotfix.
- **vref iq** — defaults ~204 µA, sized ~138 µA; target envelope still fails (`STATUS.md` Phase 3 vref row).
- **BSIM in CI** — local 5/5 smoke; Actions still bundled-only.
- **Uncommitted local diff** — web + docs may not match what next window sees on remote.

### Discipline reminders
- Passing connectivity tests ≠ schematic looks good ≠ UI loads.
- UI churn caused a startup crash — always run `UI_E2E_CHECKLIST.md` after `index.html` edits.
- Generic external roadmaps restate `AGENT_PLAN.md` — fold to parking lot, don’t panic-replan.

---

## Copy-paste — next **Cursor** window (executor)

```
Read first: docs/HANDOFF.md, docs/PARKING_LOT.md (Do next only), .cursor/.skills/SKILL.md

You are the executor. Do NOT expand scope.

Sequence:
1. If UI not yet browser-checked: remind human to run docs/UI_E2E_CHECKLIST.md — do not claim UI done without it.
2. Phase 3 vref iq — scripts/verify_phase3_vref.py (WSL), close iq + default vref margin, update docs/STATUS.md with numbers.
3. If time: Phase 0.8 STATUS sign-off — pytest tests/test_schematic_connectivity.py -v, compare logs/schematic_0.8_*.svg vs 0.7, add 0.8 row to STATUS if clean.

Do NOT: Phase 4/5, LoRA, layout/DRC/LVS, cross-repo Cursor skills, UI redesign.

Evidence: paste command output, diff, or artifact paths. Zero-trust — no "trust me" summaries.

Env: WSL Ubuntu + .venv_wsl for ngspice; Windows .venv for web (python -m openanalog.web).
```

---

## Copy-paste — next **Claude** window (reviewer / gatekeeper)

```
Read first: docs/HANDOFF.md, docs/STATUS.md, docs/PARKING_LOT.md

You are the reviewer, not the patch author. Gate acceptance on evidence.

This session context:
- 0.7 connectivity verified (IO stub gap was real; test failed then passed).
- 0.8 stub-then-fold code on HEAD 065abb0; STATUS not yet updated.
- UI index.html was corrupted and hotfixed — demand browser E2E or say "not verified."
- vref iq still open (Phase 3) — real next engineering gate.
- PARKING_LOT holds PSRR/CMRR/THD/PVT/layout — deferred, not forgotten.

When Cursor returns work, check:
1. Real ngspice numbers for vref iq (not _design() pass alone)
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

Next: vref bandgap on SKY130 BJTs; then BSIM CI job (not before local stable).
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
