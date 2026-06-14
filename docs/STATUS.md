# OpenForge category status (updated each phase)

Honest state against **RS-series envelopes** in `openanalog/forge/spec_envelopes.py`.

| Category | State (bundled) | State (SKY130) | Datasheet bar | Notes |
|----------|-----------------|----------------|---------------|-------|
| comparator | **working** | **working** | RS8901 | tp<1µs vos<3mV iq<1µA |
| opamp | **working** | **working** | RS321 | gbp=1.1MHz pm>60 aol>95dB iq<80µA |
| switch | **blocked-phase3** | **partial** | RS2105 | bundled Ron floor ~315Ω; SKY130 improves PMOS pass but Ron still >50Ω in search |
| charge_pump | **blocked-phase3** | **partial** | RS2660 | diode Vf on bundled; SKY130 MOS-switch ladder ~4.3V (needs more stages/tuning) |
| vref | **deferred** | **partial** | RS431 | SKY130 bandgap bench live; tempco N/A until temp sweep |

## Product layer (2026-06-14)

| Feature | Status |
|---------|--------|
| Multi-model LLM router | `openanalog/llm.py` — OpenRouter/GPT, Anthropic, Groq, SEA-LION |
| Chat-to-chip | `parse_intent()` NL → spec → ngspice sizer |
| Presets + Test & Verify | `openanalog presets`, `openanalog test-presets`, web UI button |
| Schematic output | SVG in UI + downloadable `.kicad_sch` |
| Web UI | `python -m openanalog serve` — backend-driven `/api/meta` |
| Model set switch | `OPENFORGE_MODEL_SET=bundled\|sky130` or UI dropdown |

## Verification

```bash
make test                    # pytest (Windows, ngspice tests skip without ngspice)
python -m openanalog presets
python -m openanalog test-presets
wsl ... python scripts/smoke_all.py 80   # bundled smoke (comparator+opamp pass)
OPENFORGE_MODEL_SET=sky130 python -m openanalog test-presets --preset rs321_opamp
```

## SKY130 PDK (lightweight)

- Fetch: `python scripts/fetch_sky130_models.py` → `data/pdk/sky130/models.sp` (gitignored)
- Pin: `google/skywater-pdk-libs-sky130_fd_pr` @ main (see `data/pdk/sky130/PIN.txt`)
- Fallback: builtin level-54 cards in `openanalog/sim/models.py` when `.include` chains unavailable

## Seed corpus (Phase 2)

768 / 1,010 sim-validated (76%) after Masala parenthesis conversion.
