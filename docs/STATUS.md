# OpenForge category status (updated each phase)

Honest state against **RS-series envelopes** in `openanalog/forge/spec_envelopes.py`.

| Category | State (bundled) | State (SKY130) | Datasheet bar | Notes |
|----------|-----------------|----------------|---------------|-------|
| comparator | **working** | **partial** | RS8901 | bundled passes; SKY130 BSIM benches need retune |
| opamp | **working** | **partial** | RS321 | bundled passes; SKY130 BSIM benches need retune |
| switch | **blocked-phase3** | **partial** | RS2105 | bundled Ron floor ~315Ω; SKY130 Ron ~113Ω (BW/ton pass, Ron>50Ω) |
| charge_pump | **blocked-phase3** | **partial** | RS2660 | bundled vout~4.3V; SKY130 NMOS ladder vout~4.3V (needs stages/tuning) |
| vref | **deferred** | **partial** | RS431 | SKY130 divider+vbe trim hits 1.2V; line_reg/tempco N/A on quick bench |

## Forge fitness gate (Step 1)

- `evaluate_forge_fitness()` scores against RS-series `DEV_MODE_SPECS` — **not** `sim_ok`
- `winners.jsonl` records include `topology`, `measured_specs`, `fitness=1` only on full spec pass
- Seed mutations: **0 winners** in 100–200 sim runs (strict bar; expected until evolution improves seeds)

## Product layer (2026-06-14)

| Feature | Status |
|---------|--------|
| Multi-model LLM router | `openanalog/llm.py` — OpenRouter/GPT, Anthropic, Groq, SEA-LION |
| Chat-to-chip | `parse_intent()` NL → spec → ngspice sizer |
| Presets + Test & Verify | `openanalog presets`, `openanalog test-presets`, web UI Test Suite tab |
| Schematic output | SVG in UI + downloadable `.kicad_sch` |
| Web UI | `python -m openanalog serve` — `/api/meta`, `/api/test-presets`, version footer |
| Model set switch | `OPENFORGE_MODEL_SET=bundled\|sky130` or UI dropdown |

## Verification

```bash
make test                    # pytest (Windows, ngspice tests skip without ngspice)
python -m openanalog presets
python -m openanalog test-presets
wsl ... python scripts/smoke_all.py 80   # bundled: opamp+comparator pass
OPENFORGE_MODEL_SET=sky130 python -m openanalog test-presets --preset rs321_opamp
```

## SKY130 PDK (lightweight)

- Fetch: `python scripts/fetch_sky130_models.py` → `data/pdk/sky130/models.sp` + pm3 includes (gitignored)
- Simulation uses **ngspice-tuned builtin BSIM4** cards in `openanalog/sim/models.py` (fetched subckts need full open_pdks)
- Pin: `google/skywater-pdk-libs-sky130_fd_pr` @ main (see `data/pdk/sky130/PIN.txt`)

## Seed corpus (Phase 2)

768 / 1,010 sim-validated (76%) after Masala parenthesis conversion.
