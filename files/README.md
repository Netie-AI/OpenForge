# Schematic layout tangling fix — drop-in patch

## Where these go in OpenForge

| File here | Destination |
|---|---|
| `schematic_geometry.py` | `openanalog/eda/schematic_geometry.py` (new file) |
| `schematic_layout.py` | `openanalog/eda/schematic_layout.py` (replaces existing) |
| `test_schematic_no_tangling.py` | `tests/test_schematic_no_tangling.py` (new file) |
| `schematic-layout-skill.md` | `docs/schematic-layout-skill.md` (new file) |

`standalone_geometry_check.py` and `standalone_integration_smoke.py` are
NOT meant to ship — they're how this was verified without access to the
real `symbols.py`/`netlist_graph.py`. Run them once locally to sanity-check
the patch landed correctly, against the real modules, before trusting
`test_schematic_no_tangling.py`'s baseline numbers:

```bash
pip install pytest --break-system-packages   # if needed
pytest tests/test_schematic_no_tangling.py -v
```

## What this actually fixes (verified)

The `two_stage_miller_opamp` floorplan's `nb` bias net (M8/M5/M7) was
spanning the full canvas and tangling through the Miller cap and input
pair — that's the wire in the original screenshot. Root cause: those three
devices were placed in three far-apart zones with no routing-level way to
avoid a long cross-canvas wire. Fixed by treating placement as a scored
search instead of a fixed table — see `schematic-layout-skill.md` for the
full writeup and the one **known remaining gap** (a smaller, localized
issue at the Miller cap leads, not the cross-canvas tangle).

## Integration notes — read before merging

1. **`_DEVICE_BBOX` / `_CAP_BBOX` in `schematic_layout.py` are approximate**,
   back-derived from the sample SVG, not read from the real `symbols.py`.
   The wire-through-device check is best-effort until these are confirmed
   against real symbol geometry.
2. **This was built and tested against a *fake* `symbols.py`/`netlist_graph.py`**
   (since I don't have access to the real ones), matching the interface the
   original `schematic_layout.py` already used — `terminal_positions(dev,
   origin, mirror) -> dict[net_name, Point]`, keyed by actual net name (this
   is directly inferable from the original file's `_io_terminals`/`_vdd_nodes`
   checks, which compare dict keys against `"vdd"`, `"0"`, `"vinp"`, etc., so
   it should be a safe assumption — but verify on first real run).
3. **`diff_pair_comparator` is untouched** (still uses `_resolve_layout`,
   no variant search) — it doesn't have a Miller-compensated second stage,
   so the original placement wasn't the source of this bug. Worth running
   `test_schematic_no_tangling.py`-style checks against it too once this is
   merged, but no changes were made there.
4. The crossing/placement search is currently scoped to `two_stage_miller_opamp`
   only (`_STAGE2_VARIANTS`). Extending it to other topologies means adding
   a variant table for them — the search machinery (`_score_placement`,
   `route_all_nets`, `schematic_geometry.score_layout`) is already generic.
