# OpenForge — Session Handoff

**Updated:** 2026-06-18  
**HEAD:** `4c57f63` — CI run **#13** green ([Actions](https://github.com/Netie-AI/OpenForge/actions/runs/27771500132))

Use this file at the **start of every new Cursor window**. Read it, then `docs/STATUS.md`, then `AGENT_PLAN.md` §0 operating rules.

---

## North star (long term)

**OpenForge** = analog IC design forge: datasheet spec → ngspice-validated netlist + measured specs → (later) evolutionary topology search → (later) multitask LoRA that only ships fitness=1 designs.

Ultimate demo (Phase 5 exit): *"design me a low-Vos comparator under 1 µA"* → verifier-gated netlist with real ngspice numbers.

Broader product vision (CEO master plan tail in `AGENT_PLAN.md`): Palantir/Cadence-friendly UI, assisted editing (add a wire → re-sim → new topology class), DRC/LVS, parasitic extraction — **all gated on honest ngspice fitness=1 first.**

---

## Short term (do next)

| Priority | Task | Gate |
|----------|------|------|
| **Now** | **Phase 1d — opamp / RS321** | Last category in Phase 1 THE GATE |
| Then | Phase 1 exit check | All four categories `working` in `docs/STATUS.md` + `make smoke-wsl` green |
| Then | Phase 2 seed parser integration | Already mostly built — wire measured fraction into forge |
| Not yet | Phase 3 SKY130 re-validation | After Phase 1 green on bundled models |
| Not yet | Phase 5 LoRA / training | Throwaway smoke artifact exists — do **not** wire until Phase 1–4 gates pass |

---

## Progress snapshot

### Phase 0 — Infrastructure ✅

| Item | Status |
|------|--------|
| 0.4 ngspice reachability (WSL) | ✅ |
| 0.5 rendering | ✅ |
| 0.6 schematic floorplan | ✅ |
| 0.7 connectivity verification | ✅ |
| CI on Linux + ngspice behavioral job | ✅ |

### Phase 1 — THE GATE (four dev-mode categories vs `spec_envelopes.py`)

| Phase | Category | Part | Status | Verification script |
|-------|----------|------|--------|---------------------|
| **1a** | comparator | RS8901 | ✅ `working` | `scripts/verify_phase1a.py` |
| **1b** | analog_switch | RS2105 | ✅ `working` | `scripts/verify_phase1b.py` |
| **1c** | charge_pump | RS2660 | ✅ `working` | `scripts/verify_phase1c.py` |
| **1d** | opamp | RS321 | ⏳ **NEXT** | (create `scripts/verify_phase1d.py`) |

**Phase 1 exit criteria** (`AGENT_PLAN.md`): `make smoke` fitness=1 for all four categories on RS-series envelopes, each with a named behavioral test in `tests/test_ngspice_behavior.py`, CI green on pushed HEAD.

---

## Environment (this host)

```powershell
# Windows — ngspice NOT on PATH; use WSL Ubuntu
$env:OPENFORGE_WSL_DISTRO='Ubuntu'

# Simulation venv (WSL)
wsl -d Ubuntu bash -lc "cd /mnt/c/Users/oojia/OpenForge && source .venv_wsl/bin/activate && python scripts/verify_phase1c.py"

# Web server (Windows; port 8080 often blocked — use 8090)
$env:OPENFORGE_WSL_DISTRO='Ubuntu'
.\.venv_train\Scripts\python.exe -m openanalog serve --host 127.0.0.1 --port 8090

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

## Copy-paste prompt — next Cursor window (Phase 1d)

```
Read docs/HANDOFF.md, docs/STATUS.md, and AGENT_PLAN.md Phase 1d first.

Execute Phase 1d — opamp / RS321 (THE GATE, last of four):
- Diagnose before claiming done: default vs sized params, netlist structure,
  seed sensitivity (seeds 1, 3, 7, 42, 42), historical failures in designs.jsonl.
- RS321 envelope: gbp=1.1MHz pm>60 aol>95dB iq<80uA slew>0.5 (spec_envelopes.py)
- Add/strengthen test_opamp_meets_rs321_bar in test_ngspice_behavior.py
- Add scripts/verify_phase1d.py
- Update docs/STATUS.md Phase 1d section
- Push, confirm Actions green on HEAD, flip CI row to ✅
- If all four Phase 1 categories working, add Phase 1 exit summary to STATUS.md

Do NOT start Phase 2, Phase 3 SKY130 re-validation, or Phase 5 training until
Phase 1 exit criteria are met on pushed HEAD.

Environment: ngspice in WSL Ubuntu (.venv_wsl), OPENFORGE_WSL_DISTRO=Ubuntu.
Follow verify/check/improve loop from AGENT_PLAN.md.
```

---

## Copy-paste prompt — after Phase 1 complete

```
Phase 1 exit is green (all four categories working, CI on HEAD). Read HANDOFF.md.

Next per AGENT_PLAN.md:
1. Run make smoke-wsl and document Phase 1 exit in STATUS.md
2. Begin Phase 2 — wire seed parser / seeds_normalized.jsonl into forge fitness
   (768/1010 sim_validated already exist)
3. Do NOT start Phase 5 LoRA training

Keep Rule 8: datasheet bar only, no dev slack, Actions tab on push.
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
