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
| vref        | ⏸      | ⚠️      | BJT needed; deferred to Phase 3.5  |

## Forge Status
- Loop: ✅ topology param mutation → RS fitness gate → winners.jsonl
- Winners: **1002** total (charge_pump=381, ldo=364, switch=135, opamp=53, comparator=69)
- Opamp warm-start: ✅ Cc=1.9pF center, 35% warm fraction — 53 winners with W1 diversity (σ=0.52)
- Topology variants: scaffold in `topology_variants.py` (comparator cross-coupled POC)
- Training corpus: **READY for Phase 5** — ≥1000 winners, ≥50 opamp, all fitness=1
- Quality note: 66 switch/comparator winners have `tfall_ns=None` (optional spec); core bar still passes

## Verification

```bash
python -m openanalog forge --n 20 --reset
python scripts/smoke_all.py 80
OPENFORGE_MODEL_SET=sky130 python scripts/smoke_all.py 80
python -m pytest tests/ -q
```
