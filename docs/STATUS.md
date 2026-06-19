# OpenForge category status (updated 2026-06-19)

Honest state against **RS-series envelopes** in `openanalog/forge/spec_envelopes.py`.

## Documentation anchor (read order)

| File | Role | Update when |
|------|------|-------------|
| **`docs/HANDOFF.md`** | **Master handoff** — short-term goal, long-term north star, next-window prompt | Every meaningful checkpoint (not only session end) |
| **`docs/STATUS.md`** | Evidence-backed phase/category status (this file) | After a verified run changes a phase gate |
| **`AGENT_PLAN.md`** | Phase order, exit criteria, verify/check/improve loop | When roadmap gates or rules change |
| **`.cursor/.skills/SKILL.md`** | Cursor agent conventions (evidence, handoff discipline) | When workflow rules change |

**Short-term vs long-term:** `HANDOFF.md` owns both — "Short term (do next)" table and "North star (long term)". `STATUS.md` does not duplicate goals; it records what is proven true/false per phase.

---
## Phase 1a — Comparator / RS8901 (2026-06-18)

| Item | Status | Notes |
|------|--------|-------|
| Netlist structure | ✅ | Default vs seed=7 sized: **11 devices, identical connectivity** (only `.param` W/L/Iref/Rload change). Verified via `scripts/verify_phase1a.py`. |
| Sizing causal story (iq) | ✅ | **Iref 500 nA → 71 nA (7× down)** is the main iq move: 1.58 µA → 0.62 µA. Secondary: W3↓ (lighter diff load), Rload 50 kΩ→23 kΩ, W5↑ (tail width). **tp barely moves with sizing** (0.21→0.19 µs at defaults vs seed=7). |
| tp / 8 µs history | ✅ | **Not a sizing win.** Stored “failed” params (`designs.jsonl` line 6) still measure **tp=0.23 µs today**. Old tran deck (`83bcb4d`) on same params gives **tp=8.08 µs**; current deck gives **0.23 µs** — fixed in commit **`99d68df`** (stimulus + `t_plh` target edge). The ~40× tp gap was a **measurement-deck fix already on main**, not this session’s sizing. |
| Symptom reconciliation | ✅ | **113 µA** = loose `iq<200 µA` profile (not RS8901). **8 µs** = old `.tran` bench on RS8901 params (iq ~5–6 µA on those records). Never one combined RS8901 run. |
| Seed sensitivity (budget=250) | ✅ | **4/4 pass** (seeds 1, 3, 7, 12): tp 0.19–0.97 µs, iq 0.30–0.77 µA, vos <0.31 mV. Not seed-7-only. |
| tp bench sanity | ⚠️ | Current deck: 300 mV input step, **50 ps edges**, vout trip at 50% VDD, **no explicit Cload** (Rload only). RS8901 product sample cites typ **0.8 µs** / **0.5 µA** — all sized seeds beat `<1 µs` bar; Rload sweep 10–100 kΩ moves tp 0.14–0.22 µs (seed=7 params). Fast edges + no output cap may be **optimistic vs full datasheet fixture**; still real ngspice step response, not scoring stub. |
| RS8901 bar (`make smoke`) | ✅ | seed=7 budget=250: **tp=0.19 µs, vos=0.30 mV, iq=0.62 µA**, `meets_all=True` |
| Default params (unsized) | ⚠️ | **tp=0.21 µs, iq=1.58 µA** — tp/vos pass, iq misses RS8901; sizing required for iq |
| Behavioral test | ✅ | `tests/test_ngspice_behavior.py::test_comparator_meets_rs8901_bar` |
| CI | ✅ | Run **#9** green on pushed HEAD `828b7d0` — unit + ngspice behavioral jobs ([Actions run](https://github.com/Netie-AI/OpenForge/actions/runs/27747331852)) |

**Category verdict:** `working` (RS8901, bundled models) — robust across seeds; iq closed by bias sizing, tp closed by prior bench fix + valid step measurement.

Reproduce: `python scripts/verify_phase1a.py` (WSL, ngspice on PATH).

## Phase 1b — Analog Switch / RS2105 (2026-06-18)

| Item | Status | Notes |
|------|--------|-------|
| Netlist structure | ✅ | `cmos_transmission_gate`: NMOS+PMOS pass pair + ctrl inverter. Default vs sized: **same 8-element graph**, only W/L change. |
| Sizing causal story (Ron) | ✅ | **Wn 50→220 µm (4.4×), Wp 100→776 µm (7.8×)** at Vctrl=VDD, Vsig=2.5 V. Ron **97 Ω→13 Ω** (seed=11). ton/toff already pass at defaults (1.4 ns / 8.4 ns); sizing mainly closes Ron margin. |
| Prior ~834 Ω / ton unmeasured history | ✅ | **Not a sizing miss.** Pre-`175da53` PMOS/NMOS **source/drain swap** in `_core()` produced ~835 Ω Ron and broken tran. Same historical params today: **Ron≈23 Ω**. Fixed in commit **`175da53`**. |
| Seed sensitivity (budget=250) | ✅ | **5/5 pass** (seeds 1, 3, 7, 11, 12): Ron 2–17 Ω, BW 155–231 MHz, ton 0.3–0.6 ns, toff 10–12 ns. |
| Bench sanity | ✅ | DC Ron at mid-rail with 1 kΩ//10 pF load; ton/toff from ctrl 0→5 V pulse (100 ps edges). Product sample typ Ron=25 Ω, ton=12 ns, toff=10 ns — sized results consistent with bar, not optimistic stubs. |
| RS2105 bar (`make smoke`) | ✅ | seed=11 budget=250: **Ron=13 Ω, BW=167 MHz, ton=0.33 ns, toff=10.2 ns**, `meets_all=True` |
| Default params (unsized) | ⚠️ | **Ron=97 Ω** — misses `<50 Ω`; ton/toff/BW pass; sizing required for Ron |
| Behavioral test | ✅ | `tests/test_ngspice_behavior.py::test_switch_meets_rs2105_bar` |
| CI | ✅ | Run **#11** green on pushed HEAD `2390957` ([Actions run](https://github.com/Netie-AI/OpenForge/actions/runs/27748985425)) |

**Category verdict:** `working` (RS2105, bundled models) — robust across seeds; Ron closed by device width sizing after prior S/D orientation fix.

Reproduce: `python scripts/verify_phase1b.py` (WSL, ngspice on PATH).

## Phase 1c — Charge Pump / RS2660 (2026-06-18)

| Item | Status | Notes |
|------|--------|-------|
| Topology | ✅ | Bootstrapped **2-stage NMOS Dickson** (`dickson_charge_pump`): gate bootstrapped above VDD via Cboot + Dboot per stage. Fixed in **`8297008`** / **`2c90319`**. |
| **What closed the category** | ✅ | **The bootstrap fix (`8297008`/`2c90319`) closed RS2660 — not the sizer.** Default vout=**4.997 V** already passes before sizing; seed=19 sized vout=**4.999 V** is a **+0.04%** confirmatory tweak (ripple/settle margin only). Do not read this as "the sizer closed a real vout gap." |
| Target-mode tolerance | ✅ | **Re-verified 2026-06-19:** `score_design` → `_passes(..., tol=0.05)` in `openanalog/forge/sizer.py` lines 36–44, 87 — **5% default, not 30%.** Target vout=5 V pass band **4.75–5.25 V**. Measured 4.999 V passes at 5%; would also pass old 30% band (3.5–6.5 V), so **this measurement alone does not prove no regression** — the code read confirms 5% is still in effect. |
| Duplicate instance grep | ✅ | **Re-verified 2026-06-19:** seed=19 sized netlist — **13 device instances, duplicate names: NONE** (first-token grep on emitted netlist). Historical duplicate-`C0` suspect: **checked, none found.** |
| Prior ~4.1–4.3 V history | ✅ | Pre-bootstrap diode/NMOS pump (`6b2d356` era) lost ~Vth per stage → ~4.27 V in `designs.jsonl` (also passed under old 30% tolerance — false pass). Bootstrapped topology today: **vout≈5.0 V** at defaults. |
| Seed sensitivity (budget=250) | ✅ | **6/6 pass** (seeds 1, 3, 7, 11, 19, 42): vout 4.998–4.999 V, ripple <0.08 mV, settle <0.02 ms. |
| Bench sanity | ✅ | `.tran` avg vout over last 30% window; ripple pp same window. Product sample: vout=5 V, ripple=30 mV, settle=3 ms — results consistent, ripple/settle well inside bar. |
| RS2660 bar (`make smoke`) | ✅ | seed=19 budget=250: **vout=4.999 V, ripple=0.017 mV, settle=0.003 ms**, `meets_all=True` |
| Default params (unsized) | ✅ | **vout=4.997 V** — passes RS2660 without sizing |
| Behavioral test | ✅ | `tests/test_ngspice_behavior.py::test_charge_pump_meets_rs2660_bar` |
| CI | ✅ | Run **#13** green on pushed HEAD `4c57f63` ([Actions run](https://github.com/Netie-AI/OpenForge/actions/runs/27771500132)) |

**Category verdict:** `working` (RS2660, bundled models) — **bootstrap topology fix (`8297008`/`2c90319`) is what made vout real**; Phase 1c sizing/CI work was verification + confirmatory tuning, not the primary fix.

Reproduce: `python scripts/verify_phase1c.py` (WSL, ngspice on PATH; ~13 min for full seed sweep).

## Phase 1d — Op-Amp / RS321 (2026-06-18)

| Item | Status | Notes |
|------|--------|-------|
| Topology | ✅ | `two_stage_miller_opamp`: diff pair + PMOS mirror + Miller-compensated 2nd stage (Cc between vout/nout1). Structure unchanged by sizing. |
| **What closes the category** | ✅ | **Sizing closes RS321; defaults fail.** Default: AOL=92 dB, PM=16°, GBP=8.9 MHz, Iq=102 µA → `meets_all=False`. Sized (seed=42): AOL=102 dB, GBP=1.11 MHz, PM=63°, Iq=32 µA. Main moves: **Cc→~0 (GBP trim), Iref↓, W1↓, W6↑**. |
| Tolerance (`_passes`) | ✅ | Target GBP: **5%** (`tol=0.05`). Min AOL/PM/slew: **≥98% of target**. Max Iq: **≤102% of target**. Sized GBP=1.107 MHz passes 1.045–1.155 MHz band. |
| Duplicate instance grep | ✅ | seed=42 sized netlist: **zero duplicate device names** (checked 2026-06-18). |
| Seed sensitivity (budget=250) | ⚠️ | **3/5 pass** (seeds 1, 7, 42); seeds 3 & 99 fail **AOL** (~86 dB vs 93.1 dB floor). Gate locked to **seed=42** in test/smoke — not as robust as 1b/1c, but repeatable. |
| Prior AOL ~93 dB failures | ✅ | `designs.jsonl` RS321 misses are **AOL short by 2–3 dB** at wrong Cc/GBP — same axis as seed variance, not a separate bench bug. |
| RS321 bar (`make smoke`) | ✅ | seed=42 budget=250: **AOL=102 dB, GBP=1.11 MHz, PM=63°, Iq=32 µA, slew=0.56 V/µs**, `meets_all=True` |
| Default params (unsized) | ❌ | Fails RS321 on AOL, PM, GBP, Iq — sizing required |
| Behavioral test | ✅ | `tests/test_ngspice_behavior.py::test_opamp_meets_rs321_bar` |
| CI | ✅ | Run **#16** green on pushed HEAD `d27ccca` ([Actions run](https://github.com/Netie-AI/OpenForge/actions/runs/27774104165)) |

**Category verdict:** `working` (RS321, bundled models, seed=42 gate) — sizing-dependent with **AOL seed variance** documented.

Reproduce: `python scripts/verify_phase1d.py` (WSL, ngspice on PATH).

## Phase 1 exit — THE GATE (2026-06-18)

| Category | Part | Status |
|----------|------|--------|
| comparator | RS8901 | ✅ `working` |
| analog_switch | RS2105 | ✅ `working` |
| charge_pump | RS2660 | ✅ `working` |
| opamp | RS321 | ✅ `working` (seed=42; AOL variance noted) |

All four have named behavioral tests in CI. Run `make smoke-wsl` on pushed HEAD to confirm end-to-end.

**Phase 1 exit verified 2026-06-19:** `make smoke-wsl` green on HEAD `515e8a8` — 5 dev-mode categories pass RS bar (opamp seed=42, comparator seed=7, switch seed=11, charge_pump seed=19, ldo seed=23).

## Phase 2 — Seed corpus → forge fitness (2026-06-19)

| Item | Status | Notes |
|------|--------|-------|
| Corpus | ✅ | `data/seeds_normalized.jsonl`: **1010 total, 768 sim_validated (76%)**, **634 benchable sim_validated** (opamp=563, comparator=38, switch=33) |
| Dialect converter | ✅ | `dialect.py` + `converter.py` — Masala/AnalogGenie paren → ngspice-flat |
| Fitness path | ✅ | `evaluate_forge_fitness()` scores raw seed netlists on RS bar (`forge_eval.py` + `netlist_measure.py`) |
| Forge wiring | ✅ | `openanalog/forge/seed_scoring.py`; `run_forge(..., score_seeds=True)` scores up to 25 benchable seeds at start |
| CLI | ✅ | `python -m openanalog forge --score-seeds/--no-score-seeds --seed-score-limit N` |
| Verification | ✅ | `python scripts/verify_phase2.py` — 768 sim_validated, sample scoring wired (2026-06-19) |
| CI | ✅ | Run **#18** green on pushed HEAD `6bc0599` ([Actions run](https://github.com/Netie-AI/OpenForge/actions/runs/27799932447)) |
| Raw seed fitness=1 | ⚠️ | Expected rare — seeds are topology starters, not RS-sized designs; wiring gate ≠ pass rate |

Reproduce: `python scripts/verify_phase2.py` (WSL, ngspice on PATH).

## Phase 0 — Infrastructure (2026-06-17)

| Item | Status | Notes |
|------|--------|-------|
| 0.4 ngspice reachability (Windows → WSL) | ✅ | `OPENFORGE_WSL_DISTRO=Ubuntu`; 5× `/api/health` probe OK; opamp+comparator `/api/design` return real metrics. **Server:** port **8090** on this host (8080 blocked by Windows port exclusion — use `scripts/verify_phase04.py 8090`) |
| 0.5 netlist/schematic rendering | ✅ | **Frontend:** netlist tab line-number table collapsed content column → fixed with `<pre>` + gutter spans. **Backend:** `netlist_graph.py` emits device-level schematic (M1…Mn + wires) instead of OPAMP block symbol |
| 0.6 schematic layout (floorplan) | ✅ | Role-based floorplans for `two_stage_miller_opamp` + `diff_pair_comparator`: fixed MOSFET symbols, orthogonal routing, VDD/GND rails, junction dots at 3+-way ties. **Note:** mirrored-device wire endpoints were misaligned at 0.6 ship (grid snap after mirror transform); fixed in 0.7. |
| 0.7 schematic connectivity verification | ✅ | `openanalog/eda/schematic_connectivity.py` + `tests/test_schematic_connectivity.py`: terminal-to-wire match (anchors from `symbols.py`), netlist-to-schematic adjacency on placed devices, no dangling routed endpoints, no false junction dots on unrelated-net crossings. Sample SVGs in `logs/schematic_0.7_*.svg`. |
| CI (GitHub Actions) | ✅ | Was **red from `f0d8324` (0.6) through `91d07d1` (0.7)** without anyone checking Actions on push — process gap, not a silent ngspice miss. **Cause:** `win_path_to_wsl()` called `Path.resolve()` on `C:/…` paths; on Linux CI that produces garbage paths → `test_config_ngspice.py` failed. **Not** missing ngspice — workflow already runs `apt-get install ngspice`. Fixed in `openanalog/config.py`. **Done means:** local pass + CI green on pushed HEAD. |
| Default WSL distro | ⚠️ | docker-desktop is default; ngspice lives in **Ubuntu** — set `OPENFORGE_WSL_DISTRO=Ubuntu` |
| Phase 5 infra (vLLM / TurboQuant / serving) | ⏸ | Deferred until trained LoRA adapter exists — no install/wiring this session |

### Phase 5 — early / unauthorized smoke test (2026-06-18)

A 3-epoch LoRA training run completed ahead of plan gating and saved an adapter to `openforge-lora-v1/`. **Treat as throwaway smoke-test artifact**, not a milestone — corpus predates Phase 1-4 fitness=1 bar across categories.

- `scripts/validate_lora.py` fixed: loads local `./openforge-lora-v1` path instead of Hub repo ID
- Do not wire this adapter into serving UI or re-train until Phase 1-4 gates pass

### 0.5 fix summary (2026-06-17)

| Layer | Bug | Fix |
|-------|-----|-----|
| **Frontend** | Netlist tab showed line numbers 1–37 with **no SPICE text** — table `.code` column collapsed to zero visible width in the three-pane layout | Replaced table with `<pre id="netlistPre">` + gutter spans; `resolveNetlist()` fetches `/api/last-design` or `/api/netlist` when slim response omits netlist |
| **Backend** | Schematic tab showed one **OPAMP/CMP block symbol** with no transistor connectivity | Added `openanalog/eda/netlist_graph.py` — parses M/C/R/I from netlist, renders device boxes + wire connections; `render_svg()` prefers netlist graph when ≥2 MOSFETs |

**Verify:** `pytest tests/test_netlist_schematic.py`; `python scripts/verify_phase04.py 8090`

**Reproduce server (Windows, this host):**
```powershell
$env:OPENFORGE_WSL_DISTRO='Ubuntu'
.\.venv_train\Scripts\python.exe -m openanalog serve --host 127.0.0.1 --port 8090
# → http://127.0.0.1:8090  (8080 blocked — Windows excluded port range)
```

## Phase 3 — SKY130 PDK (2026-06-19)

**Zero-trust checkpoint:** evidence in `evidence/zerotrust_checkpoint_2026-06-19/` plus follow-up in `evidence/phase3_*_2026-06-19.log`.

**SKY130/BSIM CI gap:** All SKY130 and BSIM work verified **locally only** — CI runs Phase 1 bundled-model behavioral tests only; **zero SKY130/BSIM coverage in GitHub Actions** until an explicit workflow step is added.

| Item | Status | Notes |
|------|--------|-------|
| Config switch | ✅ | `OPENFORGE_MODEL_SET=bundled\|sky130`; `OPENFORGE_SKY130_CARD=level1\|bsim` |
| SKY130 level-1 smoke (5/5) | ⚠️ **not real SKY130** | **5/5 pass is against a hand-written level=1 placeholder** (`SKY130_MODELS_BUILTIN` in `openanalog/sim/models.py`) — SKY130-style device names, **not** loaded from `data/pdk/sky130/models.sp`, not BSIM4. **Do not treat as silicon validation.** |
| BSIM subckt emit | ✅ | `mos_line`/`mos_inst` emit `X` instances for fetched BSIM4 subckts |
| BSIM card sim | ✅ **5/5 smoke on pinned v0.13.0** | Root cause of pfet crash: missing BSIM mismatch `.param`s + newline glue bug — fixed in `openanalog/sim/models.py`. Models pinned to **`google/skywater-pdk-libs-sky130_fd_pr@v0.13.0`** (`2997061e…`). Re-run: `evidence/phase3_bsim_smoke_rerun_2026-06-19.log` — opamp **AOL=105.5 dB**, GBP=1.09 MHz, PM=75° (seed=42). Prior 4/5 log (`sky130_bsim_smoke_raw.log`, AOL=82 dB) was pre-fix / unstable AC on broken pfet path — **superseded.** |
| Switch Ron seed sensitivity (BSIM) | ✅ **5/5 pass** | Seeds 1,3,7,11,12 @ budget=150: Ron **39.8–49.4 Ω** (all `<50 Ω`). Tight but robust — not a single lucky seed. `evidence/phase3_switch_bsim_seeds_2026-06-19.log` |
| Opamp AOL on BSIM | ✅ **closed (seed=42 gate)** | Sizer closes via **L1↑ (0.5→2.37 µm)**, **W3→60 µm**, **W7→120 µm**, **Iref↓**, **Cc→0** for GBP trim. Causal: short L1 on BSIM4 collapsed input-pair ro → ~82 dB AOL when pfet AC sim was broken; longer L1 restores DC gain once models.py fix lands. Seed sweep (budget=200): **3/5 pass** (seeds 3,7,42); seed=1 misses GBP by 0.2%; seed=99 misses iq — **AOL passes all 5 seeds** (94–105 dB). The Phase 3 BSIM smoke **5/5** headline is the locked gate run at **seed=42**, while the separate robustness sweep over seeds **1/3/7/42/99** is **3/5 meets_all**. Same gate discipline as Phase 1d. `evidence/phase3_opamp_bsim_seeds_2026-06-19.log` |
| vref bandgap | ⏳ **partial** | Topology runs on SKY130 BJTs (`scripts/verify_phase3_vref.py`). Default deck is **resistor divider → ~1.2 V**; BJT PTAT branch not wired to output. RS431 **line_reg fails** (~600 mV vs `<5 mV` bar) — needs real bandgap, not divider tweak. `resolve_models()` now honors `OPENFORGE_MODEL_SET` when context unset. |
| Model pin | ✅ **fetch script pinned** | `scripts/fetch_sky130_models.py` + `data/pdk/sky130/PIN.txt`: tag **v0.13.0**, commit **2997061e461c71e6e5c85153e3403ca74c62f69c**. **Volare still not installed** — pin is via raw GitHub fetch, not volare-managed PDK tree. |
| CI | ✅ | Run **#19** green on pushed HEAD `7dc7182` — Phase 1 behavioral gate only; does not exercise SKY130 BSIM path |

Reproduce BSIM smoke: `OPENFORGE_MODEL_SET=sky130 OPENFORGE_SKY130_CARD=bsim python scripts/smoke_all.py 80` (WSL)  
Switch seeds: `python scripts/verify_phase3_switch_bsim_seeds.py`  
Opamp diag: `python scripts/diag_phase3_opamp_bsim_aol.py`

## Phase 3 Status (2026-06-15, superseded — see above)

| Category    | Bundled | SKY130 (placeholder level-1) | Notes                              |
|-------------|---------|------------------------------|-------------------------------------|
| opamp       | ✅      | ⚠️ placeholder 5/5           | RS bar pass on hand-written level-1 card — **not real SKY130 PDK** |
| comparator  | ✅      | ⚠️ placeholder 5/5           | same caveat                         |
| switch      | ✅      | ⚠️ placeholder 5/5           | same caveat                         |
| ldo         | ✅      | ⚠️ placeholder 5/5           | same caveat                         |
| charge_pump | ✅      | ⚠️ placeholder 5/5           | same caveat                         |
| multiplier  | ⚠️      | ⚠️                           | Gilbert cell experimental (partial)|
| vref        | ⏸      | ⏸                            | BJT needed; deferred until BSIM path works |

## Schematic / Phase 7 (2026-06-16, updated 2026-06-18)
- **0.7:** Automated schematic connectivity checks — terminal anchors from `symbols.py` must match routed wires; netlist adjacency must match wire graph for placed devices; CI via `tests/test_schematic_connectivity.py`. Fixed mirrored-terminal routing (removed post-mirror grid snap that pulled M2 source off `(344,268)`).
- **0.6:** Role-based schematic layout — MOSFET symbols with fixed gate/drain/source geometry, orthogonal Manhattan wires, VDD/GND rails, per-topology floorplans (`two_stage_miller_opamp`, `diff_pair_comparator`). Shipped with mirrored wire offset bug (see 0.7). KiCad export still uses one library symbol — unchanged.
- **0.5 (fixed):** Web UI netlist tab + netlist-driven device graph SVG (M1–M8 boxes with node wires). KiCad export still uses one library symbol — unchanged.
- **Prior diagnosis (still true for KiCad):** `kicad_sch.py` emits one KiCad library chip symbol + power rails — no `Device:M` / per-transistor symbols.
- Full pretty symbol library / KiCad per-device placement gated on Phase 6 blocks.

## Phase 6 — compositional blocks (2026-06-16)
- Comparator decomposed: `forge/blocks/` — `tail_current_source`, `differential_pair`, `current_mirror`, `comparator_output`, `comparator_core`
- `comparator.py` and `topology_variants.py` compose blocks
- **Regression gate PASSED:** pre-refactor (HEAD) vs post-refactor (blocks), identical `forge --n 50` seeds: **11/50 winners**, 50/50 per-generation fitness match, 0 spec mismatches (`scripts/run_comparator_regression.sh`)

## Forge Status
- Loop: ✅ topology param mutation → RS fitness gate → winners.jsonl
- Winners: **1002+** total (charge_pump=381, ldo=364, switch=135, opamp=53, comparator=69)
- Opamp warm-start: ✅ Cc=1.9pF center, 35% warm fraction — 53 winners with W1 diversity (σ=0.52)
- Topology variants: scaffold in `topology_variants.py` (comparator cross-coupled POC)
- Training corpus: **READY for Phase 5** — ≥1000 winners, ≥50 opamp, all fitness=1
- Quality note: 66 switch/comparator winners have `tfall_ns=None` (optional spec); core bar still passes

## Web UI (localhost:8080)
- **Run:** `make serve-wsl` or `bash scripts/run_web.sh` (WSL) — `pip install -e ".[web]"` first
- Product line: 18 RS-series products across Amplifiers, Switches, Power, Compute, Interface, Digital, Data Converters, System
- Presets: RS321, RS8901, RS2105, RS2660, RS3001 LDO, RS431 (deferred), RS7001 multiplier (experimental), plus low-Iq / fast variants
- **Achievable ranges:** data-driven min/median/max from `data/training/winners.jsonl` (Iq, current, all measured specs)
- **Applications:** battery/low-Iq, sensor front-end, analog multiply, vector-MAC, analog-replaces-digital use cases
- Compute family: RS7001 Analog Multiplier (β), RS7100 MAC crossbar (planned), RS7200 compute tile (planned)

## Charge pump note
- 4-phase clock duty cycle fixed: pulse width `{quarter}` (25%) instead of `{half}` (50%) in `_clock_lines` — eliminates phase overlap
- Default sizer still prefers 2-phase on bundled models; 4-phase interleaved switching under validation

## Verification

```bash
# WSL (ngspice required)
make smoke-wsl
OPENFORGE_MODEL_SET=sky130 make smoke-wsl
python -m pytest tests/ -q
make serve-wsl   # → http://127.0.0.1:8080
```
