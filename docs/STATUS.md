# OpenForge category status (updated 2026-06-15)

Honest state against **RS-series envelopes** in `openanalog/forge/spec_envelopes.py`.

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

## Schematic / Phase 7 (2026-06-16)
- **Diagnosis (confirmed):** `kicad_sch.py` emits one KiCad library chip symbol + power rails — no `Device:M` / per-transistor symbols. Not an unflattened `.subckt` bug.
- Topology files do **not** set `kicad_symbol`; `footprints.py` maps category→symbol when `attach_eda_metadata()` runs (comparator→`Comparator:LMV331`, etc.). Missing `eda` falls back to `LM358`.
- Real fix gated on Phase 6 blocks (device-level schematic from block boundaries).

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
