# OpenForge — Session Handoff

**Updated:** 2026-06-19 (session)  
**HEAD:** `a9fba7f` — copy-chat task + doc anchor hierarchy pushed.

**Read order:** this file → `docs/STATUS.md` → `AGENT_PLAN.md` §0 → `.cursor/.skills/SKILL.md` (Cursor conventions).

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
| **Now** | Phase 3 exit | vref on SKY130 BJTs + BSIM CI job (after local stability) |
| Done | Switch Ron BSIM seed sweep | 5/5 pass — `scripts/verify_phase3_switch_bsim_seeds.py` |
| Done | Pin SKY130 models | `v0.13.0` / `2997061e…` in fetch script + `PIN.txt` |
| Done | Opamp AOL on BSIM | 5/5 smoke; seed=42 gate; 3/5 seed sweep (reconciled in STATUS) |
| Done | Copy Cursor chat | `scripts/copy_cursor_chat.py` + task **Copy Cursor Chat** (`Ctrl+Shift+Alt+C` in user keybindings) |
| Done | Cursor conventions doc | `.cursor/.skills/SKILL.md` — evidence gatekeeper; not an Anthropic Skill |
| Not yet | Phase 4 / Phase 5 | Do **not** start until Phase 3 exit |
| Deferred | Advanced-node PDK survey | Research doc only (`docs/research/ADVANCED_NODE_SURVEY.md`) — after Phase 3 close; lambdapdk/ASAP7 not analog SPICE |

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
| **1d** | opamp | RS321 | ✅ `working` (seed=42) | `scripts/verify_phase1d.py` |

**Phase 1 exit criteria** (`AGENT_PLAN.md`): all four `working` + `make smoke-wsl` + CI behavioral tests green on pushed HEAD.

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

## Copy-paste prompt — next Cursor window (Phase 3 exit)

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
