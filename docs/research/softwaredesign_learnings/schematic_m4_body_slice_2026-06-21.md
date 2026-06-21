# Software design learning — M4 body slice & schematic 0.9 (2026-06-21)

Captured after the user flagged “the M3/n1 wire crosses M4’s body” on the two-stage Miller op-amp schematic. Goal: preserve the full reasoning chain, what each agent tier did well, and the verification pattern so future windows do not re-open placement when the bug is router/scorer.

---

## Scenario

**Symptom:** Horizontal `n1` segment at **y=156**, **x=332→380**, visually slices through **M4** PMOS load body while reaching M4’s gate riser at **x=380**.

**User intent:** “Everything must be pretty” — pin breakout + orthogonal routing, not SVG cosmetics. Real connectable logic (netlist/LVS precursor), not a drawing patch.

**Stack:** Parent (Opus) executor + prior Claude reviewer framing + Composer-style evidence discipline.

**Outcome:** Schematic **0.9** — router per-net obstacles + active-body slice scorer. **0** transverse slices through active transistors on opamp/comparator invariant check. Tests green: connectivity **42/42**, no_tangling **7/7**, netlist_schematic **13/13**. Artifact: `logs/schematic_opamp_m4_fix.svg`.

---

## Coordinates (ground truth)

| Object | Region / point |
|--------|----------------|
| M4 body (inset rect) | x∈[343,373], y∈[123,165] (origin 340,120, mirror, 36×48 symbol) |
| Bad jog (before fix) | `(332,156)→(380,156)` — interior overlap with M4 body on x∈[344,370] |
| M4 gate terminal | (370, 144); gate stub end | (380, 144) |
| Good route (after fix) | `(172,168)→(172,180)→(380,180)→(380,144)` — below body bottom (y=168), rise on outer column x=380 |

**Rule:** Geometry disputes resolve with coordinates from the same render path as the browser (`render_schematic_svg` → `route_nets`), not from memory or an old golden SVG.

---

## Decision trail (who thought what)

| Stage | Agent / role | Contribution | Verdict |
|-------|----------------|--------------|---------|
| Eye check | User | Spotted body slice; refused to waive as “good enough” | **Correct** — defect was real |
| Triage | Claude reviewer | Confirmed coords; argued placement (mirror M4 gate inward) vs routing patch; parked placement session | **Directionally right on sequencing discipline**; root cause was slightly richer (see below) |
| Diagnose | Composer/Opus executor | Traced `n1` through route pipeline; counted **2** precise transverse slices (M4 + Cc passive tap) | **Found scorer blind spot** |
| Hypothesis 1 | Executor | Mirrored device obstacle box wrong | **False** — mirror keeps same bounding box |
| Hypothesis 2 | Executor | Gate stub `(380,144)` inside own device obstacle (margin 10 → box to x=386) | **True** — router unreachable pin → fallback slice |
| Hypothesis 3 | Executor | Post-process (`_repair_collinear_overlaps`) caused slice | **False** — slice present before post-process when obstacles blocked routing |
| Fix A | Executor | `device_obstacles_for_net`: 0 px margin to **connected** devices, 10 px to others | **Working** — pin breakout reachable, foreign bodies blocked |
| Fix B | Executor | `find_bad_crossings`: flag same-net **transverse slice** through **active** (`kind=="M"`) bodies | **Working** — eye and score agree |
| Test debt | Executor | Old test `test_opamp_n1_m4_gate_riser_trimmed_at_380` asserted riser top **at y=156** (the slice) | **Removed/replaced** — tests must encode invariants, not bugs |

---

## What Claude did great (keep doing)

1. **Coordinates over opinion** — “The x=380 trim worked, but y=156 still slices M4” is exactly the right granularity; no hand-waving.
2. **Sequencing without panic** — Treating body-cross as placement-adjacent when the mirror forces an inward gate is valid *product* thinking; avoids endless router whack-a-mole on the wrong layer.
3. **Honest demo framing** — UI/video briefs anchored on real SVGs, real PASS metrics, “chat-to-chip” as vision not claim.
4. **Not failing the human** — Correctly noted that catching the slice is reachable logic; the gap was which *layer* owned the fix.

**Claude pattern to reuse:** When the user’s eye disagrees with green tests, ask “what layer owns this?” (placement / routing / scoring / render) before declaring done.

---

## What Composer / Opus executor did (whole way of thinking)

### 1. Evidence floor first

Read order: `HANDOFF.md` → `STATUS.md` → `PARKING_LOT.md` → conventions skill. No STATUS upgrade without verbatim pytest + artifact path.

### 2. Separate three truths

| Truth | Question |
|-------|----------|
| **Connectivity** | Does every terminal touch the right net graph? |
| **Orthogonality** | Manhattan only, stubs on named nets? |
| **Readability / semantics** | Does any signal **slice through** a device body it should route **around**? |

Passing (1) and (2) does **not** imply (3). This session is the canonical example.

### 3. Diagnose before patching placement

Placement fix (flip M4) would work but fights diff-pair spine alignment (drains face inward by design). Executor proved a **clean L-route exists** at y=180 once obstacles allow reaching `(380,144)`.

**Lesson:** Placement session stays parked for *orientation policy*; this specific bug closed in **router + scorer** without mirror churn.

### 4. Instrument, don’t argue

Use small scripts on the **production** API:

- `scripts/diag_schematic_invariants.py` — 0 active slices, 0 cross-net collinear overlaps (opamp + comparator, no ngspice).
- Stage trace (ephemeral) — MST edges returning `path=[]` when start buried in own obstacle.

### 5. Scorer design: precise transverse slice

Naive “any wire touching own device net” → 26 false positives (stubs, risers).  
**Precise rule:** horizontal segment strictly inside body height **and** spanning full body width (vertical: dual).  
Only **active** bodies (`DeviceBox.kind == "M"`) for same-net case; passive Miller tap on `nout1` through Cc remains allowed.

### 6. Tests encode invariants, not coordinates

| Bad proxy | Good invariant |
|-----------|----------------|
| Riser top at y=156 | Riser reaches gate y=144; extends to y≥168 (below body); zero M4 slice in scorer |
| nb and GND both avoid x=192 | No collinear overlap between `nb` and `0` anywhere |

### 7. Verification under slow ngspice

`design()`-backed tests ~24 s each. Background pytest in harness **aborts**; run synchronously or in chunks. Parent re-run beats subagent stdout.

---

## Architecture boundaries (updated)

```
symbols.py          → pin geometry, escape direction, mirror anchor math
schematic_layout.py → floorplan, variant score, DeviceBox for scorer
schematic_router.py → stubs, visibility graph, per-net obstacles, hops
schematic_geometry.py → crossing score, transverse slice detection
schematic_connectivity.py → LVS-precursor graph checks
```

**Do not:** wholesale replace layout with `files/` bundle; do not relax `crossing_score` threshold without stronger semantic checks (OpenForge gatekeeping rule).

---

## Code touchpoints (schematic 0.9)

| File | Change |
|------|--------|
| `openanalog/eda/schematic_router.py` | `_OWN_DEVICE_MARGIN = 0`, `device_obstacles_for_net()` |
| `openanalog/eda/schematic_geometry.py` | `_segment_slices_rect()`, same-net active slice in `find_bad_crossings` |
| `openanalog/eda/schematic_layout.py` | `DeviceBox.kind` from device |
| `tests/test_schematic_no_tangling.py` | Slice regression + render-path no-active-slice test |
| `tests/test_schematic_connectivity.py` | Replaced tests that encoded the y=156 bug |

---

## Verify commands (copy-paste next window)

```powershell
# Fast geometry (no ngspice)
python scripts/diag_schematic_invariants.py
python scripts/render_opamp_schematic.py logs/schematic_opamp_m4_fix.svg

# Schematic evidence floor
python -m pytest tests/test_schematic_no_tangling.py -q
python -m pytest tests/test_schematic_connectivity.py -q   # ~10+ min (design() per case)
python -m pytest tests/test_netlist_schematic.py -q
```

Expected: `ALL_INVARIANTS_OK=True`; active-body slices **0**; opamp `crossing_score=2` (two n1/nout1 wire-hops, not body cuts).

---

## Parking lot / north star (unchanged)

| Item | Status after 0.9 |
|------|------------------|
| M4 mirror placement policy | Still valid future work for readability; **not** required for this bug |
| KiCad per-device export | Phase 6 — netlist is real logic today |
| DRC/LVS | Phase 7+ — schematic-only |
| PVT envelope expansion | Next honest simulation sprint (PSRR landed; CMRR Option B parked) |

**User ask “finish all parking lot”:** Cannot honestly close multi-year items (layout, SerDes, LoRA). Close **one session = one gate** with evidence.

---

## Do not repeat

1. **Trust crossing_score alone** when the user sees a body slice on a same-net wire.
2. **Write regression tests that codify the bug** (y=156 jog as “correct”).
3. **Assume placement** because mirror “feels” wrong — run obstacle + stub-end reachability first.
4. **Background long pytest** on Windows harness for gate claims — sync run or chunked.
5. **Delete/replace tracked diag scripts** without checking `git ls-tree HEAD` (restored `diag_opamp_schematic_route.py` from HEAD this session).

---

## Agent handoff snippet (next Cursor window)

```
Read: docs/research/softwaredesign_learnings/schematic_m4_body_slice_2026-06-21.md
Schematic 0.9 landed (uncommitted): per-net router margins + active-body slice scorer.
Next sequenced: PVT envelope expansion — not CMRR churn, not parking-lot layout.
Eye vs test: if they disagree, check scorer semantics before router or placement.
```

---

## Related docs

- `docs/research/SCHEMATIC_ENGINE_ROADMAP.md` — Window B (overlap/route-channel) partially addressed by 0.9
- `docs/HANDOFF.md`, `docs/STATUS.md` — schematic 0.9 row
- `.cursor/skills/openforge-conventions/SKILL.md` — schematic evidence floor (SVG + three pytest files)
