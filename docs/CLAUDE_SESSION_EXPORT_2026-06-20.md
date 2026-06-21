# OpenForge — Full session export for new Claude window (2026-06-20)

**Purpose:** Single paste-in document so a context-restricted Claude reviewer understands the entire multi-turn session: engineering work, research, Cursor mode routing, gate state, and what was accepted vs rejected.

**Repo:** `Netie-AI/OpenForge`  
**Branch:** `feat/schematic-orthogonal-router`  
**Local HEAD:** `85aae8e` (`Add CMRR bench with tail/bias causal sweep evidence.`)  
**Push status:** `[ahead 1]` vs origin at last check — commit `85aae8e` may not be on remote yet.

**Prior chat transcript (Cursor):** agent transcript `a0afe47b-555c-4774-a062-78bda69a779b`

---

## 0. How to use this document (Claude reviewer)

You are the **reviewer / gatekeeper**, not the patch author. Accept claims only with verbatim command output, diff, or artifact paths.

**Read order after this file:**
1. `docs/HANDOFF.md`
2. `docs/STATUS.md`
3. `docs/PARKING_LOT.md`
4. `docs/semicon-log.md` entries 5–6 (PSRR, CMRR)
5. `docs/research/AGENTIC_EDA_SURVEY.md`
6. `docs/research/GENERATIVE_ANALOG_LAYOUT_SURVEY.md` (untracked in git at export time — on disk)

**Protocol:** OF-C2C-v1 (see `.cursor/rules/claude-cursor-response-contract.mdc`)

---

## 1. Cursor mode routing (Composer vs Codex vs Ask)

OpenForge uses **parent model tier** to decide collaboration mode (`.cursor/rules/mode-routing-and-collab-gates.mdc`, `.cursor/skills/mode-routing/SKILL.md`):

| Parent mode | Subagent default | Gate behavior |
|-------------|------------------|---------------|
| **Composer** (`composer-2.5-fast`) | composer-2.5-fast | Gate-critical claims need OF-C2C + Evidence Bundle → **Claude verification before advancing** |
| **Non-Composer** (e.g. **Codex high**, GPT high) | inherit parent | Cursor may close locally: executor → **dv-verifier** (blocking) → parent re-run; Claude review optional unless user asks |
| **Ask / read-only parent** | read-only only | No writing (`cursor-executor`) unless user switches mode |

**This session:** Parent was **non-Composer (Codex-class)** — local verification + dv-verifier reruns acceptable; Claude review happened when user pasted reviewer findings manually.

**User shorthand:**
- `continue` = execute next priority now (not plan-only)
- `continue and next window` = execute + emit next-window handoff snippet

**Agent model tiering (session default):** executor/verifier=`inherit`, read-only proposers/coordinator=`composer-2.5-fast` — see `openforge-gatekeeping.mdc`; don't relitigate without new friction evidence.

**Non-negotiables:**
- One writer at a time (no parallel edits to `forge/`, `sizer/`, design sources)
- `dv-verifier` blocking on gate-critical claims
- Never relax spec tolerance to pass
- Evidence beats claims
- `.cursor/agents`, `.cursor/rules`, `.cursor/skills` = owner-managed — executors do not edit unless explicitly instructed

---

## 2. Project north star (unchanged)

**OpenForge** = analog IC design forge: datasheet spec → ngspice-validated netlist + measured specs → (later) evolutionary topology search → (later) LoRA on fitness=1 corpus only.

**Current honest layer:** Phase 0–3 infrastructure + Phase 1 four-category gate (bundled models) + SKY130 BSIM smoke (local). **Not** layout/GDS, **not** Phase 4 topology mutation, **not** SerDes/HBM/PLL.

**Fitness bar:** `openanalog/forge/spec_envelopes.py` → `DEV_MODE_SPECS` — single bar, no second looser tolerance.

---

## 3. Chronological narrative — what happened this session chain

### Phase A — Schematic 0.8 sign-off (before BSIM/tangling plan)

- **0.8 orthogonal router** signed off: `openanalog/eda/schematic_router.py` implements stub-then-fold + visibility graph; used by `schematic_layout.py` via `route_nets()`.
- **Connectivity gate:** `pytest tests/test_schematic_connectivity.py -v` → **14/14 pass** (parent + dv-verifier).
- **SVG evidence:** 0.7 → 0.8 terminal_stub markers: opamp **0→21**, comparator **0→20**; io-stub **3→3** unchanged.
- **Verdict:** Routing style fixed; schematic *looks* better.

### Phase B — Root cause diagnosis (Claude review, accepted)

- **Not a draw bug — placement pressure:** `nb` net ties M8/M5/M7 in `openanalog/forge/topologies/opamp.py` (bias mirror + tail + output device).
- Floorplan in `schematic_layout.py` places them in bias/tail/output zones far apart → long cross-canvas wires even with good router.
- **0.8 fixed routing, not placement distance.**

### Phase C — Cherry-pick tangling integration (NOT wholesale `files/` merge)

**Plan:** Do NOT replace production `schematic_layout.py` with `files/schematic_layout.py`.

**Landed at commit `ef43ef6`:**
- `openanalog/eda/schematic_geometry.py` — crossing detection + `score_layout`
- `openanalog/eda/schematic_layout.py` — opamp placement variants (`isolated` vs `tail_aligned`) on top of existing `route_nets()`
- `tests/test_schematic_no_tangling.py` — **5/5 pass**
- `.github/workflows/ci.yml` — new job `sky130-bsim-smoke`

**Variant results:**
- Winner: **`tail_aligned`** (M7 moved to tail column)
- `nb` x-span: **300 → 174** (vs isolated baseline)
- `crossing_score`: **6** (target ≤3; `files/` bundle expected ≤3 — reference only)
- Connectivity: **14/14** still green

**`files/` bundle status:** Reference-only. Standalone tests fail (`crossing_score=6`, expects `isolated` winner). Do not merge wholesale.

### Phase D — BSIM CI wiring + local proof

- Local WSL: `OPENFORGE_MODEL_SET=sky130 OPENFORGE_SKY130_CARD=bsim python scripts/smoke_all.py 80` → **5/5 pass** (vref deferred), repeatedly re-verified.
- CI workflow includes `sky130-bsim-smoke` job.
- **Actions URL NOT verified:** workflow triggers on `main`/`master` push + `pull_request` only. Feature branch push does not run CI. GitHub API: **0 open PRs**, **0 PR workflow runs** on branch. `gh auth login` unavailable in Cursor environment.
- **Human action required:** Open [compare → PR](https://github.com/Netie-AI/OpenForge/compare/main...feat/schematic-orthogonal-router), wait for green `sky130-bsim-smoke`, log URL in `docs/STATUS.md`.

### Phase E — Research (read-only, no integration)

1. **`docs/research/AGENTIC_EDA_SURVEY.md`** — Synopsys/ChipAgents/agentic patterns vs OpenForge forge loop; analog topology invention gap confirmed.
2. **`docs/research/GENERATIVE_ANALOG_LAYOUT_SURVEY.md`** — ALIGN, MAGICAL, OpenFASOC, BAG3++, OpenLane; SerDes/HBM explicitly parking lot; Phase 7+ downstream of forge.

User pasted generic "Generative Analog EDA" memo (ALIGN, MAGICAL, HBM PHY, etc.) — distilled into survey; **did not reprioritize roadmap**.

### Phase F — CMRR bench + Claude pushback (critical)

**Work landed:**
- `openanalog/forge/topologies/opamp.py` — `_build_cmrr_deck`, `aol_db_100`, CMRR normalization fix
- `scripts/verify_cmrr.py`, `scripts/diag_opamp_cmrr_fixture.py`, `scripts/diag_opamp_cmrr_breakdown.py`
- Commit **`85aae8e`** (includes docs + `uv.lock`)

**Normalization bug fixed:** Prior +20 dB artifact from AC stimulus mismatch (diff deck AC=1, CM deck AC=0.1). Fix: `cmrr_dB = aol_db_100 - (acm_db + 20)`.

**Numbers (bundled models):**
| Case | CMRR open-loop | CMRR RL=10k | PSRR |
|------|----------------|-------------|------|
| defaults | 152.0 dB | 127.4 dB | 20.0 dB |
| sized s42 | 151.4 dB | 142.4 dB | 54.7 dB |

**Claude reviewer finding (accepted):** 152 dB CMRR is **not physically credible** for two-stage Miller opamp when PSRR is 20–55 dB. Locking open-loop as "production" and demoting RL=10k to "diagnostic only" was **wrong** — same shape as forbidden second-looser tolerance at fixture level.

**Cursor response:** Policy lock **reverted**. Ran tail/bias causal sweep.

**Lb sweep (M8 bias on `nb`) — strongest causal knob:**
| Lb (µm) | CMRR open-loop | CMRR rl10k | PSRR |
|---------|----------------|------------|------|
| 0.5 | 159.5 dB | 137.6 dB | 20.0 dB |
| 1.0 (default) | 152.0 dB | 127.4 dB | 20.0 dB |
| 8.0 | 125.5 dB | 118.6 dB | 20.0 dB |

**Interpretation:** Bundled level-1 models likely inflate bias-stack Ro → inflated CMRR. RL fixture consistently ~15–25 dB more pessimistic on defaults but still >> RS321 typ 80 dB. **CMRR gate NOT closed.** Next: same Lb sweep on **BSIM card** to test bundled-model artifact hypothesis.

### Phase G — vref scripts (untracked, explained)

Four untracked scripts are **pre–Option B historical exploration**, NOT authorized Option A reopening:
- `scripts/diag_vref_topology.py` — bandgap topology variant comparison
- `scripts/diag_vref_selfbias.py` — NPN Santunu-style self-biased bandgap sweep
- `scripts/diag_vref_selfbias_pnp.py` — PNP self-biased bandgap sweep (NPN/PNP pair)
- `scripts/diag_vref_tune.py` — ideal VCVS vs MOS error amp

**vref Option B still locked:** iq open on placeholder BJTs; do not sizing-sweep iq.

---

## 4. Commit history (this branch, recent)

| Commit | Summary |
|--------|---------|
| `ef43ef6` | BSIM CI smoke job + schematic tangling guard (geometry, variants, tests) |
| `a8e8097` | Doc sync BSIM/tangling gates |
| `85a8d51` | Doc sync PR blocker + tangling next-cut plan |
| `85aae8e` | CMRR bench + tail/bias sweep evidence + opamp.py wiring |

---

## 5. Gate state table (honest, 2026-06-20)

| Gate | State | Notes |
|------|-------|-------|
| Phase 0.8 router | ✅ working | 14/14 connectivity; SVG stub evidence |
| Schematic tangling | ⚠️ partial | crossing_score=6; target ≤3; tail_aligned variant |
| Local BSIM smoke | ✅ working | 5/5 @ WSL, vref deferred |
| GitHub Actions sky130-bsim-smoke | ⚠️ unverified | Needs PR; 0 runs |
| PSRR bench | ⚠️ bench-only | W3 causal story; not in DEV_MODE_SPECS |
| CMRR bench | ⚠️ partial | Lb sweep done; 152 dB implausible; no fixture policy lock |
| vref iq | ⏳ Option B partial | iq open; no sizing sweeps |
| Layout (ALIGN/MAGICAL) | ⏸ parking lot | Phase 7+ survey only |
| Phase 4/5 / LoRA | ❌ do not start | |

---

## 6. Claude decisions log

| Decision | Verdict |
|----------|---------|
| 0.8 routing sign-off | accept |
| Placement root cause on `nb` | accept |
| Cherry-pick tangling (not wholesale files/) | accept |
| BSIM local 5/5 = CI green | **reject** — local only until PR Actions URL |
| CMRR fixture policy lock (open-loop production) | **reject** — reverted; need causal + datasheet equivalence |
| 152 dB CMRR as credible | **reject** — diagnose first (Lb sweep partial answer) |
| Generative layout memo → immediate sprint | **reject** — parking lot Phase 7+ |

---

## 7. Next steps (sequenced)

1. **Human:** Open PR → capture green `sky130-bsim-smoke` Actions URL → update `STATUS.md`
2. **Engineering:** CMRR Lb sweep on **BSIM** card (parallel bundled sweep)
3. **Engineering:** Schematic Cc passive tap second pass (crossing_score 6→≤3)
4. **Cleanup:** Delete or archive untracked vref diag scripts; commit untracked `docs/research/` if desired
5. **Push:** `git push origin feat/schematic-orthogonal-router` (85aae8e ahead of origin)

---

## 8. Verification commands (re-run before gate claims)

```powershell
# Windows host — schematic (fast)
python -m pytest tests/test_schematic_no_tangling.py -q
python -m pytest tests/test_schematic_connectivity.py -v

# WSL — BSIM smoke
wsl -d Ubuntu bash -lc "cd /mnt/c/Users/oojia/OpenForge && source .venv_wsl/bin/activate && OPENFORGE_MODEL_SET=sky130 OPENFORGE_SKY130_CARD=bsim python scripts/smoke_all.py 80"

# WSL — CMRR diagnostics
wsl -d Ubuntu bash -lc "cd /mnt/c/Users/oojia/OpenForge && source .venv_wsl/bin/activate && python scripts/verify_cmrr.py"
wsl -d Ubuntu bash -lc "cd /mnt/c/Users/oojia/OpenForge && source .venv_wsl/bin/activate && python scripts/diag_opamp_cmrr_breakdown.py"
wsl -d Ubuntu bash -lc "cd /mnt/c/Users/oojia/OpenForge && source .venv_wsl/bin/activate && python scripts/diag_opamp_cmrr_fixture.py"
```

---

## 9. Copy-paste — brand new Claude window

```
Protocol: OF-C2C-v1
Role: Claude reviewer
Intent: review

Read first (in order):
1. docs/CLAUDE_SESSION_EXPORT_2026-06-20.md  (this full session export)
2. docs/HANDOFF.md
3. docs/STATUS.md
4. docs/PARKING_LOT.md
5. docs/semicon-log.md entries 5-6

You are the reviewer, not the patch author. Gate acceptance on evidence.

Branch: feat/schematic-orthogonal-router @ 85aae8e (may be ahead of origin)

Honest state:
- Schematic 0.8 router: WORKING (14/14 connectivity)
- Tangling guard: PARTIAL (crossing_score=6, nb span 300→174, tail_aligned)
- BSIM CI: workflow wired; LOCAL smoke 5/5; Actions URL NOT verified (needs PR)
- PSRR: bench-only; W3 causal story exists
- CMRR: NOT closed — 152 dB implausible on bundled models; Lb (M8) sweep 159.5→125.5 dB;
  fixture policy lock REVERTED per your review; RL=10k diagnostic only
- vref: Option B locked; iq open; untracked vref diag scripts = historical exploration only
- Layout research: GENERATIVE_ANALOG_LAYOUT_SURVEY.md — Phase 7+ parking lot

Do NOT: lock CMRR fixture without BSIM sweep + datasheet equivalence;
  reopen vref Option A without trigger; claim CI green from local smoke;
  start Phase 4/5, SerDes/HBM, or layout integration without pilot gate.

When Cursor returns work, check: verbatim ngspice output, git diff, STATUS consistency,
no scope creep, suspiciously good numbers get MORE scrutiny not less.

Zero-trust: evidence beats summaries.
```

---

## 10. Key files touched this session chain

| Area | Files |
|------|-------|
| Schematic router | `openanalog/eda/schematic_router.py` |
| Schematic layout | `openanalog/eda/schematic_layout.py` |
| Geometry | `openanalog/eda/schematic_geometry.py` |
| Tests | `tests/test_schematic_connectivity.py`, `tests/test_schematic_no_tangling.py` |
| CI | `.github/workflows/ci.yml` |
| Opamp CMRR | `openanalog/forge/topologies/opamp.py` |
| Scripts | `scripts/verify_cmrr.py`, `scripts/diag_opamp_cmrr_*.py`, `scripts/verify_psrr.py` |
| Docs | `docs/HANDOFF.md`, `docs/STATUS.md`, `docs/PARKING_LOT.md`, `docs/semicon-log.md` |
| Research | `docs/research/AGENTIC_EDA_SURVEY.md`, `docs/research/GENERATIVE_ANALOG_LAYOUT_SURVEY.md` |
| Reference only | `files/schematic_*.py`, `files/test_schematic_no_tangling.py` |

---

## 11. Process lessons (this session)

1. **Real circuit diagnostics > tooling churn** — Claude explicitly praised CMRR/Lb sweep direction over agent config edits.
2. **Don't lock policy to hide implausible numbers** — fixture selection is not a substitute for causal diagnosis.
3. **Commit evidence** — multiple turns left scripts/docs uncommitted; `85aae8e` fixes CMRR scripts but push may still be pending.
4. **Local green ≠ CI green** — especially BSIM job that only runs on PR/main.
5. **Cherry-pick, don't wholesale replace** — production 0.8 router path preserved over `files/` bundle.

---

*Export generated 2026-06-20 for handoff to context-restricted Claude reviewer window.*
