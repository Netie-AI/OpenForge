# OpenForge category status (updated 2026-06-17)

Honest state against **RS-series envelopes** in `openanalog/forge/spec_envelopes.py`.

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

## Phase 3 Status (2026-06-15)

| Category    | Bundled | SKY130  | Notes                              |
|-------------|---------|---------|-------------------------------------|
| opamp       | ✅      | ✅      | AOL=107dB GBP=1.09MHz PM=76°       |
| comparator  | ✅      | ✅      | tp=0.19µs Vos=0.30mV Iq=0.62µA    |
| switch      | ✅      | ✅      | RON=13Ω BW=167MHz                  |
| ldo         | ✅      | ✅      | vout=3.3V reg bench all measured   |
| charge_pump | ✅      | ✅      | vout=5.0V bootstrapped NMOS Dickson|
| multiplier  | ⚠️      | ⚠️      | Gilbert cell experimental (partial)|
| vref        | ⏸      | ⚠️      | BJT needed; deferred to Phase 3.5  |

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
