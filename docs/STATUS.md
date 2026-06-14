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
- Winners: 238 total (charge_pump=93, ldo=94, switch=34, comparator=17) with netlist + measured_specs
- Training corpus: NOT YET — need ≥500 winners before finetuning
- Phase 4: OPEN — corpus scale-up in progress (238/500+ target)

## Verification

```bash
python -m openanalog forge --n 20 --reset
python scripts/smoke_all.py 80
OPENFORGE_MODEL_SET=sky130 python scripts/smoke_all.py 80
python -m pytest tests/ -q
```
