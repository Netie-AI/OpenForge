# OpenAnalog — Session Handoff
**Repo:** `C:\Users\oojia\OpenForge`  
**Date:** 2026-06-05  
**Authority:** Follow `OPENANALOG_MASTER_PLAN.md` for all decisions.

---

## Current status (one paragraph)

OpenAnalog scaffold is live (`openanalog/` package, CLI, tests). **Phase 1 (WSL + ngspice) is done** — ngspice-42 runs in WSL, `.venv` works in WSL, `load-seeds` sim-validates netlists. **Phase 2 seed loaders were just expanded** (spice-datasets subdirs, AnalogGenie/Dataset, Masala optional, AICircuit optional). Phases 3–6 are scaffolded but incomplete (PDF pipeline needs marker-pdf + Claude runs; forge needs parallel workers + resumable state; KG query CLI missing).

---

## What works right now

| Command | Where | Status |
|---------|-------|--------|
| `python -m openanalog --help` | WSL `.venv` | OK |
| `python -m openanalog load-seeds --limit 50` | WSL | OK (ngspice validates) |
| `python -m openanalog load-seeds --dry-run` | Windows | OK (parse only) |
| `python -m openanalog forge --n 10` | WSL/Windows | OK (demo seeds if no normalized file) |
| `python -m openanalog status` | Both | OK |
| `pytest tests/` | Windows `.venv` | 6 tests pass |

**WSL invoke pattern (use this — avoids sudo hang):**
```powershell
wsl -u root -e bash -lc "cd /mnt/c/Users/oojia/OpenForge && source .venv_wsl/bin/activate && <command>"
```

**IMPORTANT — separate venvs:** WSL uses `.venv_wsl/`, Windows uses `.venv/`. Never share one venv across OSes (breaks Python binary paths).

---

## Repo layout (cloned assets)

```
OpenForge/
├── openanalog/              ← YOUR CODE (pip install -e .)
├── spice-datasets/          ← symbench netlists (kicad_github, ltspice_*)
├── AnalogGenie/Dataset/     ← ~1000 .cir topology files (custom format)
├── PDF/                     ← drop papers here (ingest default)
├── papers/inbox/            ← alternate PDF inbox
├── data/
│   ├── seeds_normalized.jsonl
│   ├── kg_seeds.jsonl
│   └── training/{winners,losers}.jsonl
├── OPENANALOG_MASTER_PLAN.md
└── OPENANALOG_CURSOR_PROMPTS.md
```

**Not yet cloned:** `data/seeds/Masala-CHAI` (optional, large).

---

## Phase checklist (master plan)

| Phase | Goal | Status | Next action |
|-------|------|--------|-------------|
| **0** | Repo audit (README scan) | NOT DONE | Run STEP 0 prompt in Cursor |
| **1** | WSL + ngspice + venv | **DONE** | — |
| **2** | Seed extraction 3K+ | **IN PROGRESS** | Run full `load-seeds` in WSL; clone Masala |
| **3** | PDF ingestion | SCAFFOLD | Install `[ingest]`, drop PDFs, run ingest |
| **4** | Forge 1M sims | SCAFFOLD | Add ProcessPoolExecutor + forge_state.json |
| **5** | KG + verify + query CLI | PARTIAL | Build `openanalog query "TIA BW>1MHz"` |
| **6** | Train Qwen LoRA | SCAFFOLD | Needs 100K winners first |

---

## Claude verification rules (NON-NEGOTIABLE)

Every ambiguous extraction must go back to Claude:

| Confidence | Action |
|------------|--------|
| ≥ 0.9 | Auto-accept → `kg_seeds.jsonl` |
| 0.7–0.9 | Accept with `needs_review: true` |
| 0.5–0.7 | **`claude.reexamine_ambiguous()`** chain-of-thought |
| < 0.5 | Reject, log only |

**Code:** `openanalog/claude.py`, `openanalog/confidence.py`  
**API key:** loaded from `env.local` or `.env` (`ANTHROPIC_API_KEY`) — never commit.

**Claude is used for:**
- Schematic image classification (PDF pipeline)
- Param extraction from surrounding text
- SPICE netlist fallback when SINA confidence < 0.7
- Level-5 netlist review for top forge performers
- Re-examination of 0.5–0.7 confidence zone

---

## Known issues / gotchas

1. **Background WSL tasks killed** (exit `4294967295`) — caused by `sudo` prompts or long pip installs. Use `wsl -u root` instead.
2. **`setup.sh` was heavy** — now installs only `pip install -e .` (not torch). Optional extras: `[ingest]`, `[forge]`, `[train]`.
3. **AnalogGenie `.cir` format is NOT standard SPICE** — lines like `M0 (IB1 net64 VDD VDD) pmos4`. Most fail ngspice `.op`; still useful as topology seeds with `sim_validated=false`.
4. **Windows native has no ngspice** — use WSL for sims or `--dry-run`.
5. **NetworkX 3.x** — KG uses `pickle` not `nx.write_gpickle`.
6. **Ubuntu 24.04** — `libgl1-mesa-glx` replaced by `libgl1` in setup.sh.

---

# HANDOFF — Next Cursor session

Paste this block into a new Cursor chat:

```
You are continuing OpenAnalog at C:\Users\oojia\OpenForge.
Read OPENANALOG_MASTER_PLAN.md and OPENANALOG_HANDOFF.md first.

CURRENT PHASE: 2 (seed extraction) → then 3 (PDF ingest).

IMMEDIATE TASKS (in order):
1. Run full seed load in WSL:
   wsl -u root -e bash -lc "cd /mnt/c/Users/oojia/OpenForge && source .venv/bin/activate && python -m openanalog load-seeds --limit 2000 --analoggenie-limit 500"
   Target: 500+ sim-validated seeds, summary table printed.

2. Optional: clone Masala-CHAI:
   git clone --depth=1 https://github.com/jitendra-bhandari/Masala-CHAI data/seeds/Masala-CHAI

3. Phase 3 — enhance pdf_pipeline.py per master plan:
   - Default ingest folder: ./PDF/
   - Method A heuristic before Claude vision
   - Context window 800 tokens (not 500)
   - Save fig_XXX_context.json
   - Claude re-examine 0.5-0.7 confidence (already in claude.py — wire it)

4. Phase 4 — forge/resumable:
   - data/forge_state.json checkpoint every 100 sims
   - ProcessPoolExecutor with --workers N
   - --reset flag

5. Phase 5 — add CLI:
   python -m openanalog query "TIA BW>1MHz power<2mW"
   → KnowledgeGraph.query() top 5 nodes

RULES:
- Never rewrite AnalogGenie/spice-datasets — wrap/reuse
- fitness=0 NEVER in winners.jsonl
- All modules need --dry-run
- Use WSL for ngspice; Windows for editing only
- Revert ambiguous outputs to Claude (confidence.py thresholds)
```

**Key files to edit next:**
- `openanalog/ingestion/pdf_pipeline.py`
- `openanalog/forge/runner.py`
- `openanalog/forge/knowledge_graph.py` (add `query()`)
- `openanalog/__main__.py` (add `query` command)

---

# HANDOFF — Next Claude session

Paste this block into a new Claude chat (for verification / design review):

```
You are the verification layer for OpenAnalog — an open-source analog IC 
design automation pipeline at C:\Users\oojia\OpenForge.

Your role in this project:
1. REVIEW extracted SPICE netlists + sim results for physical plausibility
2. RE-EXAMINE ambiguous extractions (confidence 0.5–0.7)
3. CLASSIFY schematic images (is_schematic, circuit_family, confidence)
4. EXTRACT params/specs from paper text near schematics
5. CONVERT schematic images → SPICE when SINA fails (fallback)

Project state:
- WSL + ngspice working
- Seed loaders: spice-datasets, AnalogGenie, Masala (optional)
- Forge generates mutations + scores fitness via ngspice
- Confidence gates in openanalog/confidence.py

When I send you data, respond in JSON only unless asked otherwise.

Schemas you must honor:

SCHEMATIC CLASSIFICATION:
{"is_schematic": bool, "confidence": float, "circuit_family": str, 
 "components_seen": [str], "has_transistors": bool, "approximate_device_count": int}

PARAM EXTRACTION:
{"params": {"name": "value_with_unit"}, "specs": {"metric": "target"}, 
 "process": str, "topology_name": str}

RE-EXAMINATION (ambiguous zone):
{"confidence": float, "revised": object, "issues": [str], "accept": bool}

NETLIST REVIEW (top performers):
{"confidence_10": int, "issues": [str], "topology_sensible": bool}

Confidence thresholds:
- ≥0.9: auto-accept to KG
- 0.7-0.9: accept, flag needs_review
- 0.5-0.7: you must re-examine with chain-of-thought
- <0.5: reject

Next verification tasks for you:
1. Review sample seeds from data/seeds_normalized.jsonl
2. When PDF ingest runs, verify extracted netlists make sense for stated topology
3. Flag any netlist where ngspice passes but topology is wrong (false positive)
```

---

## Quick commands reference

```powershell
# Windows — edit + dry-run
cd C:\Users\oojia\OpenForge
.\.venv\Scripts\activate
python -m openanalog load-seeds --dry-run --limit 20
pytest tests -q

# WSL — real sims (recommended)
wsl -u root -e bash -lc "cd /mnt/c/Users/oojia/OpenForge && source .venv_wsl/bin/activate && python -m openanalog load-seeds --limit 2000"
wsl -u root -e bash -lc "cd /mnt/c/Users/oojia/OpenForge && source .venv/bin/activate && python -m openanalog forge --n 100"
wsl -u root -e bash -lc "cd /mnt/c/Users/oojia/OpenForge && source .venv/bin/activate && python -m openanalog status"

# PDF ingest (needs pip install -e '.[ingest]' in WSL)
wsl -u root -e bash -lc "cd /mnt/c/Users/oojia/OpenForge && source .venv/bin/activate && pip install -e '.[ingest]' -q && python -m openanalog ingest --folder ./PDF/"
```

---

## Files created/modified this session

| File | Purpose |
|------|---------|
| `openanalog/sim/ngspice.py` | Shared ngspice wrapper (`.op` for seeds) |
| `openanalog/ingestion/seed_loader.py` | Phase 2 loaders (rewritten) |
| `openanalog/config.py` | WSL detection, paths, ngspice resolve |
| `openanalog/claude.py` | Claude API + re-examination |
| `openanalog/confidence.py` | Threshold gates |
| `setup.sh` | Lightweight WSL bootstrap |
| `OPENANALOG_HANDOFF.md` | This file |

---

*End of handoff. LFG.*
