# Verification brief — paste to Claude reviewer

**Session:** 2026-06-19  
**Executor:** Cursor  
**Reviewer:** Claude (gatekeeper)

---

## What changed

### 1. SVG schematic emitter (`openanalog/eda/schematic_layout.py`, `symbols.py`)

| Bug | Fix |
|-----|-----|
| Malformed `.wire` CSS (`stroke="#..."` inside style rule) | Proper CSS classes: `.signal-wire`, `.dim`, `.title`, `.mono` |
| Invalid `font="..."` on `<text>` | CSS classes or `font-family`/`font-size`/`font-weight` attrs |
| IN+/IN− stubs stopped ~16 px short of gates | `_pin_labels(placed, topology)` — dynamic stubs from `terminal_positions` to `vinp`/`vinn`/`vout` |
| Duplicate `class` on IO stubs | Single `class="signal-wire io-stub"` |

### 2. Connectivity verifier (`openanalog/eda/schematic_connectivity.py`)

| Gap | Fix |
|-----|-----|
| IO stubs excluded from checks; `vin*` terminals skipped | `_verify_io_stubs()` — each external net terminal must lie on an `io-stub` segment |
| `anchor_wire_diffs` skipped input gates | Input gates must be on io-stub **or** routed wire |
| `io-stub` detection brittle | `'io-stub' in attrs` (works with combined classes) |

New test: `test_io_stubs_reach_terminals` in `tests/test_schematic_connectivity.py`.

### 3. Web UI (`openanalog/web/index.html`, `app.py`)

| Request | Change |
|---------|--------|
| Header too tall | Compact header (~52px), removed Explore/Assisted toggle |
| Preset dropdown redundant | Removed — product-type chips + use-case cards load specs |
| PDK picker | Read-only statement: **OpenForge L1** (bundled level-1 models) |
| Theme | Palantir-adjacent: dark blue-gray, cyan `#5ad1c9` accent, IBM Plex, grid background |

### 4. Docs

- `docs/analog_design_rules.md` — senior hire onboarding + IP boundary + tractable checks

---

## Verification gates (run before accepting)

```bash
# From repo root with venv active
python -m pytest tests/test_schematic_connectivity.py -v
python -m pytest tests/test_netlist_schematic.py -v
python scripts/render_and_verify_schematics.py
```

**Expected:**
- All connectivity tests pass (including `test_io_stubs_reach_terminals`)
- Regenerated `logs/schematic_0.7_*.svg` have valid `<style>` block and IO stubs ending at gate coords

**Manual SVG check (Claude):**
1. Open `logs/schematic_0.7_two_stage_miller_opamp.svg`
2. Confirm `<style>` uses `stroke:#5ad1c9` not `stroke="#5ad1c9"`
3. Confirm IN+ stub `x2` equals M1 gate x (~146), same y as gate (~254)
4. Confirm no `font="..."` on any `<text>`

---

## Evidence to paste back

- [ ] `pytest tests/test_schematic_connectivity.py -v` output
- [ ] First 20 lines of regenerated opamp SVG (style block + first IO stub)
- [ ] Screenshot or description of new UI header + PDK statement
- [ ] Any remaining risks (vout stub alignment, comparator floorplan, etc.)

---

## Not in scope (this session)

- vref iq closure
- KCL/KVL automated check on `.op`
- DRC/LVS implementation
- Removing backend `/api/verify` or `presets.py` (API kept; UI no longer exposes preset picker)

---

## Reviewer questions

1. Do IO stubs now land on the correct terminals by coordinate trace?
2. Would the old 16 px gap have failed the new `_verify_io_stubs`?
3. Is the UI header compact enough; is OpenForge L1 naming clear?
4. Is `analog_design_rules.md` the right frame for a senior hire without IP risk?
