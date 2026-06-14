# OpenForge category status (updated 2026-06-15)

Honest state against **RS-series envelopes** in `openanalog/forge/spec_envelopes.py`.

| Category | Bundled | SKY130 | Notes |
|----------|---------|--------|-------|
| opamp | ✅ working | ✅ working | level-1 calibrated |
| comparator | ✅ working | ✅ working | 2 forge winners confirmed |
| switch | ⚠️ partial | ⚠️ partial | RON ~4–23Ω after PMOS S/D fix (was 678Ω); target <50Ω |
| charge_pump | ❌ partial | ❌ partial | vout 4.29V/3.88V < 4.75V bar |
| ldo | ⚠️ partial | ⚠️ partial | vout ✅ iq ✅ reg bench ✅ (dropout/line/load all measured) |
| vref | ⏸ deferred | ⚠️ partial | needs BJT on bundled; SKY130 bandgap ok |

## Forge fitness gate (Phase 4 gate)

- Forge mutates **topology params** (not raw seed netlists)
- **Winners include `netlist` field** (same content as `output`) — training data complete
- 2+ winners with `fitness=1` and real `measured_specs`

## Fixes (2026-06-15)

1. **winners.jsonl** — `DatasetWriter` now writes `netlist` key on winner records
2. **LDO reg bench** — separate DC decks with `.control dc …; meas dc …` (line/load/dropout)
3. **Switch RON** — PMOS pass device S/D corrected (source=sig, drain=out); RON 678Ω→~4Ω

## Verification

```bash
python -m openanalog forge --n 20 --reset
python scripts/smoke_all.py 80
OPENFORGE_MODEL_SET=sky130 python scripts/smoke_all.py 80
python -m pytest tests/ -q
```
