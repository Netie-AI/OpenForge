# Session side notes — 2026-06-19

Quick reference for what landed this session and how to run things.

---

## Run the web UI

```powershell
cd C:\Users\oojia\OpenForge
.venv\Scripts\Activate.ps1
python -m openanalog.web
```

**URL:** http://127.0.0.1:8080

**Alternate (same server):**
```powershell
python -m openanalog serve
```

> `python -m openanalog.web` did not work before this session — added `openanalog/web/__main__.py` so it does now.

---

## What changed (important)

### SVG schematic emitter
- Fixed malformed CSS (`.wire{stroke="#..."}` → proper `.signal-wire{stroke:#5ad1c9;...}`)
- Fixed invalid `font="..."` on SVG `<text>` → CSS classes
- **IO stubs** now dynamic: IN+/IN−/OUT extend to actual gate/drain coords (was ~16px short)
- Golden SVGs: `logs/schematic_0.7_two_stage_miller_opamp.svg`, `logs/schematic_0.7_diff_pair_comparator.svg`

### 0.7 connectivity verifier
- New `_verify_io_stubs()` — external pins must touch device terminals
- Parser fix: `class="signal-wire io-stub"` now recognized (`"signal-wire" in attrs`, not exact `class="signal-wire"`)
- Tests: `tests/test_schematic_connectivity.py` — **10/10 pass**

### Web UI (Palantir-style)
- Compact header, cyan `#5ad1c9` accent, IBM Plex fonts
- **No preset dropdown** — product-type chips + use-case cards load specs
- **PDK read-only:** OpenForge L1 (bundled level-1 models)
- Removed Explore/Assisted toggle and Test & Verify button

### Docs for Claude / senior hire
| File | Purpose |
|------|---------|
| `docs/VERIFY_BRIEF.md` | Paste to Claude for review gate |
| `docs/analog_design_rules.md` | Senior analog onboarding + IP boundary |
| `docs/STATUS.md` | Phase evidence (unchanged this session) |

---

## Verify after pull

```powershell
python -m pytest tests/test_schematic_connectivity.py tests/test_netlist_schematic.py -v
python scripts/render_and_verify_schematics.py
```

---

## Not done yet (next tasks)
- **vref iq** — still open category gap
- **UI E2E** — `docs/UI_E2E_CHECKLIST.md` (human browser gate)
- **Gate-stub-then-fold 0.8** — spec in `analog_design_rules.md`
- **KCL/KVL on `.op`** — tractable, not implemented
- **DRC/LVS** — premature without layout
- Backend `/api/verify` still exists; UI just doesn't expose preset picker

## Folded from external roadmaps (2026-06-19)
- PSRR / CMRR / THD / PVT / Monte Carlo / layout-PEX → **`docs/PARKING_LOT.md`** with phase mapping
- “Already true” table there — Phase 3 BSIM, forge fitness loop, UI as diagnostic
- Do not re-derive `AGENT_PLAN.md` from screenshots

---

## UI flow (current)
1. Pick product type chip (Op-Amp, Comparator, …)
2. Edit spec or click use-case card
3. **Design Chip** → netlist + schematic + metrics (if ngspice available)
4. **Copy SVG** → paste to Claude for schematic review

---

*Auto-generated session notes — update or delete when stale.*

---

## Hotfix — UI load regression (2026-06-19 PM)

Symptom:
- `Loading product types…` / `Loading…` never resolves.
- No design actions appeared to work.

Root cause:
- `openanalog/web/index.html` script got corrupted around the error handler:
  - orphaned statements at top-level
  - `runEdit` referenced before definition
  - `renderError` function body detached
- This crashed JS at startup, so `loadMeta()` never completed.

Fix:
- Restored `renderError(msg)` as a proper function.
- Removed broken orphan block.
- Kept event bindings only after function definitions.
- Revalidated JS syntax with `node --check`.

Related schematic polish:
- Moved `IN-` and `OUT` external labels/stubs to the right edge so they no longer overlap inner devices.
- Connectivity verifier still passes after this move.
