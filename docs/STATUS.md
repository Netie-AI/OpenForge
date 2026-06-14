# OpenForge category status (updated each phase)

Honest state against **RS-series envelopes** in `openanalog/forge/spec_envelopes.py`.

| Category | State | Datasheet bar | Notes |
|----------|-------|---------------|-------|
| comparator | **working** | RS8901: tp<1µs vos<3mV iq<1µA | Nano-Iref search + inverted-output delay bench; smoke meets_all ✓ |
| opamp | **working** | RS321: gbp=1.1MHz pm>60 aol>95dB iq<80µA | budget=200 seed=42; default PM~15° is seed only — sizer pushes PM |
| switch | **blocked-phase3** | RS2105: ron<50Ω ton/toff<20ns | Sized ron≈315Ω (Wn=2000µm); level-1 NMOS-only pass path |
| charge_pump | **blocked-phase3** | RS2660: vout=5V ripple<50mV | Best sized vout≈4.29V; diode Vf loss on level-1 — needs MOS-switch pump |
| vref | **deferred (Phase 3)** | RS431 bandgap | SKY130 parasitic BJTs required |

## blocked-phase3 findings

**switch / ron<50Ω:** Transmission gate Ron scales weakly with W (50µm→10mm gives ~360Ω→315Ω)
because only the NMOS leg carries current at 2.5V common-mode; PMOS `@mp[id]≈0` with bulk at
vdd or sig. This is a level-1 body-effect / pass-device modeling limit, not a sizer bound issue.

**charge_pump / vout=5V:** Output is stuck at ~4.2–4.7V regardless of stages (1–4) or diode
`IS` tuning. The Dickson ladder anchored at `vdd` still loses ~0.3–0.8V per stage to diode
`Vf`; bootstrapped MOS switches (or process Schottky models) are required to close a 5% window
on a 5V target.

## Verification

```bash
make test
make smoke-wsl     # comparator + opamp pass; switch + charge_pump fail honestly
```
