# OpenForge category status (updated each phase)

Honest state of each circuit category. **"Working" means a real ngspice run
produces measured specs in range and `make smoke` reaches fitness=1.**

| Category | State | Notes |
|----------|-------|-------|
| opamp | working | Two-stage Miller; sizer pushes PM to spec (default PM ~15° is intentional — under-compensated seed) |
| comparator | working | Input-referred Vos via DC sweep; transient tp/trise/tfall; output switches |
| switch | working | RON via load current; AC −3 dB BW; fixed `{LN}` ngspice param parse bug |
| charge_pump | working | Dickson ladder; fixed duplicate `C0`; vout/ripple/settle measured |
| vref | **deferred (Phase 3)** | Real ~1.2 V bandgap needs SKY130 parasitic BJTs — not achievable on level-1 MOS |

## Why vref is deferred

Bandgap ~1.2 V is a **silicon junction property** (V_BE + PTAT). Bundled level-1
MOSFET models have no BJT, no meaningful tempco, and hard-coded VTO. Stacking
diode-connected MOS or resistor dividers can hit 1.2 V cosmetically but cannot
validate line regulation or tempco. **Do not build a fake bandgap in dev mode.**

## Known limits

- Bundled level-1 models: indicative for opamp/comparator/switch/charge_pump only.
- ngspice smoke requires WSL/Linux with ngspice on PATH; CI runs pytest only.

## Verification

```bash
make test          # pytest (scoring + parsing; no ngspice required)
make smoke-wsl     # 4 dev-mode categories (excludes vref)
```
