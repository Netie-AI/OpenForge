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

## Seed corpus health (Phase 2 — 2026-06-14)

Measured on WSL ngspice after Masala/AnalogGenie parenthesis → ngspice-flat conversion.

| Metric | Value |
|--------|-------|
| Total seeds | 1,010 |
| Original `masala-paren` dialect | 1,000 (99%) |
| Original `ngspice-flat` | 10 (spice-datasets) |
| **sim_validated after conversion** | **768 (76.0%)** |
| Incompatible / DC op fail | 242 (24.0%) |

### What `sim_validated` means

**Not parse-only.** `check_syntax()` → `run_op()` runs `ngspice -b` with `.op` appended.
A seed is `sim_validated=True` only when ngspice exits 0 and the DC operating point
converges (no “DC solution failed”, no fatal model/parse errors). Independent re-run
on 2026-06-14: **765/1010** matched the same criterion (3 borderline timeouts).

### Failure breakdown (242 seeds — not waste, diagnostic data)

| Failure type | Count | Phase 3 / scope |
|--------------|-------|-----------------|
| DC op fail — analog topology (floating / ill-conditioned nodes) | 238 | Bias-stub limits on topology-only seeds; may improve with better deck prep |
| DC op fail — BJT in original netlist | 2 | **Unblocks on SKY130** parasitic BJTs |
| ngspice timeout (>5s deck) | 2 | Large hierarchical netlists; increase timeout or simplify |
| PFD / XOR (digital) | 0 failed | Digital cells rarely appear in failed set; **out of scope** for analog forge |

Converter path: `openanalog/ingestion/dialect.py` + `converter.py`. Regenerate with:

```bash
wsl -u root -e bash -lc "cd /mnt/c/Users/oojia/OpenForge && source .venv_wsl/bin/activate && python scripts/renormalize_seeds.py"
```
