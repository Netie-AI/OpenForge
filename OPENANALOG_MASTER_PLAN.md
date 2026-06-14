# OpenAnalog — Master Plan
## From current cloned repos → final prompt-to-chip AI agent
### Status: repos cloned, venv ready, WSL needed for ngspice

---

## WHAT YOU HAVE RIGHT NOW (audit)

```
C:\Users\oojia\OpenForge\
├── AnalogGenie/          ← xz-group/AnalogGenie (ICLR 2025)
│   ├── Dataset/          ← topology graph data
│   ├── Models/           ← GPT-based topology generator
│   ├── Augmentation.py   ← data augmentation scripts  ← USE THIS
│   ├── Inference.py      ← topology generation        ← USE THIS
│   └── SPICE2GRAPH*.py   ← netlist → graph converter  ← USE THIS
│
├── spice-datasets/       ← symbench (LTSpice demos + KiCad netlists)
│   ├── kicad_github/     ← scraped KiCad netlists (most useful)
│   ├── ltspice_demos/    ← LTSpice official demo circuits
│   └── ltspice_examples/ ← LTSpice example circuits
│
├── AnalogSAGE/           ← INVESTIGATE: likely analog sizing/automation
├── Anvil/                ← INVESTIGATE: likely layout/routing tool
├── electric-circuits/    ← INVESTIGATE: circuit simulation library?
├── GraphGYM/             ← PyG GraphGYM — GNN training framework
├── PowerTouch/           ← INVESTIGATE: likely power circuit tool
├── RoSE/                 ← INVESTIGATE: likely routing/synthesis
├── spice-completion/     ← INVESTIGATE: SPICE netlist completion ML
├── symbench-athens-client ← symbench API client
├── symbench-studio/      ← symbench design studio
├── SymCAD/               ← INVESTIGATE: symbolic CAD?
├── ZeroSim/              ← INVESTIGATE: zero-shot simulation?
│
└── openanalog/           ← YOUR CODE (Cursor-generated scaffold)
    └── [pipeline scaffold from Task 001-005]
```

**IMMEDIATE ACTION:** Before writing more code, spend 30 min reading what you have.
Several of these repos may already solve sub-problems. Never rewrite what exists.

---

## STEP 0 — REPO AUDIT (do this in Cursor FIRST, ~30 min)

Paste this into Cursor chat:

```
Read every README.md in these directories and tell me exactly what each does,
what format its inputs/outputs are, and what I can reuse for OpenAnalog:

- ./AnalogSAGE/README.md
- ./Anvil/README.md  
- ./electric-circuits/README.md
- ./PowerTouch/README.md
- ./RoSE/README.md
- ./spice-completion/README.md
- ./SymCAD/README.md
- ./ZeroSim/README.md
- ./symbench-studio/README.md

For each: summarize in 3 lines: what it does, input format, output format, 
and whether I should USE IT / WRAP IT / IGNORE IT for OpenAnalog.
```

---

## FULL PIPELINE — 6 PHASES TO FINAL AGENT

---

### PHASE 1 — WSL BOOTSTRAP + ENVIRONMENT
**Time: 2 hours | Complexity: Low | Blocker: YES — nothing works without this**

```bash
# Run in PowerShell as Admin
wsl --install -d Ubuntu-22.04
wsl --set-default-version 2

# Then inside WSL:
cd /mnt/c/Users/oojia/OpenForge
bash setup.sh   # your existing setup.sh — fixes ngspice path in WSL

# Verify:
ngspice --version          # must work
python -m openanalog --help  # must work
python -m openanalog load-seeds  # should now find symbench netlists
```

**What changes after WSL:**
- `load-seeds` was returning 0 symbench entries — ngspice missing. Now it works.
- Every sim validation that was silently failing now runs.
- This unlocks Phase 2 entirely.

**Cursor task:**
```
Fix openanalog/ingestion/seed_loader.py so it:
1. Detects WSL vs Windows vs Linux automatically using platform.system() 
   and checking /proc/version for "microsoft"
2. Sets NGSPICE_PATH correctly for each environment:
   - WSL: /usr/bin/ngspice
   - Windows native: C:/msys64/mingw64/bin/ngspice.exe (if installed)
   - Linux: which ngspice
3. If ngspice not found: prints clear error with install instructions,
   does NOT silently skip sims
4. Add --dry-run flag that skips simulation and just counts/parses netlists
   (useful for testing on Windows without WSL)
```

---

### PHASE 2 — SEED EXTRACTION FROM ALL REPOS
**Time: 1 day | Complexity: Medium**

You have ~5,000+ raw netlists across your repos. Most are unclassified noise.
Goal: extract clean, classified, sim-validated seeds into `data/seeds_normalized.jsonl`

**What each repo gives you:**

| Repo | Format | Circuit types | Action |
|---|---|---|---|
| `spice-datasets/kicad_github/` | .net KiCad SPICE | Mixed (power, signal, RF) | Parse + classify + sim-filter |
| `spice-datasets/ltspice_demos/` | .asc LTSpice | Analog demos | Convert .asc→.sp then filter |
| `spice-datasets/ltspice_examples/` | .asc LTSpice | Analog examples | Same as above |
| `AnalogGenie/Dataset/` | Graph adjacency matrix | OpAmps, converters | Use SPICE2GRAPH in reverse |
| `spice-completion/` | SPICE partial netlists | Unknown | Check if completions useful |

**Cursor task — paste this:**
```
Build openanalog/ingestion/seed_loader.py with these loaders:

LOADER 1 — spice_datasets_loader(path)
  Walk kicad_github/, ltspice_demos/, ltspice_examples/
  For each .net or .asc file:
    If .asc: call ltspice_to_spice() converter (use PySpice or regex)
    Parse netlist: count components by type (M=mosfet, C=cap, R=res, L=ind, E=vsrc)
    Classify circuit_type using heuristic:
      dominant M + C → "amplifier" or "charge_pump"  
      dominant R + C + op-amp → "filter"
      current mirrors (matched M pairs) → "mirror"
      differential pair (2 matched M, tail current) → "diff_amp"
      crossbar pattern (grid M) → "crossbar"
      else → "unknown"
    Run ngspice .op simulation (DC operating point only, 5s timeout)
    If converges: mark sim_valid=True
    Emit to seeds_normalized.jsonl

LOADER 2 — analoggenie_loader(path)  
  Read AnalogGenie/Dataset/ files
  Each sample is a graph adjacency matrix + device list
  Use AnalogGenie/SPICE2GRAPH_full.py IN REVERSE to reconstruct SPICE
  (or use their provided graph→netlist converter if it exists)
  Classify by device composition
  Emit to seeds_normalized.jsonl

LOADER 3 — masala_chai_loader(path)
  If data/seeds/Masala-CHAI/ exists (optional clone):
  Read each .sp netlist file
  Pair with its description text file
  Extract circuit_type from description
  Emit to seeds_normalized.jsonl

After all loaders run, print summary table:
  circuit_type | count | sim_valid | sim_valid_pct
  amplifier    |  342  |   287     |   83.9%
  ...
  TOTAL        | 4,821 |  3,104    |   64.4%
```

---

### PHASE 3 — PDF INGESTION PIPELINE  
**Time: 2-3 days | Complexity: High — this is the real differentiator**

This is what nobody else has built. You drop analog IC papers in a folder,
it extracts every schematic, understands every connection, writes seeds.

**Tool stack (confirmed working):**
- **Marker** — PDF → Markdown + auto-extracted images (best quality, BSD license)
- **SINA** (arxiv 2601.22114) — schematic image → SPICE netlist, 96.47% accuracy
  - Uses: YOLOv11 + Connected Component Labeling + OCR + VLM
  - Install: check their GitHub for pip install instructions
- **Claude API** — fallback for SINA failures + param extraction from text
- **ngspice** — validate every extracted netlist

**Cursor task — full PDF pipeline:**
```
Build openanalog/ingestion/pdf_pipeline.py

STAGE 1 — PDF to Markdown (marker-pdf)
  from marker.convert import convert_single_pdf
  from marker.models import load_all_models
  
  models = load_all_models()  # load once, reuse for batch
  full_text, images, metadata = convert_single_pdf(pdf_path, models,
      langs=["English"], batch_multiplier=2)
  
  Save structure:
    papers/processed/{slug}/
      text.md           (full paper markdown)
      images/           (ALL figures extracted as PNG)
      metadata.json     (title, authors, abstract, year)

STAGE 2 — Detect which images are circuit schematics
  For each image in images/:
    Method A (fast, free): rule-based heuristics
      - Image has thin lines on white/light background
      - Contains symbol-like patterns (circles, triangles, rectangles)
      - Aspect ratio between 0.3 and 3.0
      - Not a graph/plot (no axis labels, no data curves)
    Method B (accurate): Claude Vision API
      Send image + prompt:
      "Is this a circuit schematic with electronic components?
       Answer JSON only: {
         is_schematic: bool,
         confidence: float 0-1,
         circuit_family: one of [amplifier|filter|power|oscillator|adc|mixed|other],
         components_seen: [list of component types visible],
         has_transistors: bool,
         approximate_device_count: int
       }"
    
    Use Method A first (0ms). If borderline: use Method B (Claude API call).
    Threshold: is_schematic=True AND confidence>0.65
    
    Mark location in text.md with HTML comment:
    <!-- SCHEMATIC_START fig_042 circuit_family=amplifier confidence=0.91 -->
    ![fig_042](images/fig_042.png)  
    <!-- SCHEMATIC_END -->

STAGE 3 — Extract context params from surrounding text
  For each confirmed schematic at position P in text.md:
    Extract text[P-800 : P+800] (surrounding context window)
    Send to Claude API:
    "From this paper excerpt near a circuit schematic, extract:
     1. All component values mentioned (transistor W/L, R values, C values)
     2. Supply voltage(s)  
     3. Target specs (gain dB, bandwidth MHz, power mW, noise nV/rtHz, etc.)
     4. Process node if mentioned (130nm, 45nm, 65nm...)
     5. Circuit topology name if explicitly stated
     Output JSON: {params:{}, specs:{}, process:str, topology_name:str}"
    
    Save as: images/fig_042_context.json

STAGE 4 — Schematic image → SPICE netlist
  Primary: Try SINA tool
    (check if SINA is pip-installable or needs local clone)
    sina_result = sina.convert(image_path)
    if sina_result.confidence > 0.70: use it
  
  Fallback: Claude Vision
    system = """You are an expert analog IC designer.
    Convert the circuit schematic to a SPICE netlist.
    Rules:
    - Use sky130 NMOS/PMOS model names: sky130_fd_pr__nfet_01v8, sky130_fd_pr__pfet_01v8
    - Name all nodes: VDD, VSS (ground=0), and net_001, net_002... for internal nodes
    - Include ALL components visible: transistors, resistors, caps, current sources
    - Standard SPICE syntax only
    - End with .end
    Output ONLY the SPICE netlist, no markdown, no explanation."""
    
    response = claude.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{
            "role": "user", 
            "content": [
                {"type": "image", "source": {"type": "base64", 
                 "media_type": "image/png", "data": img_b64}},
                {"type": "text", "text": "Convert to SPICE netlist."}
            ]
        }],
        system=system
    )
    netlist = response.content[0].text

STAGE 5 — Validate + save seed
  Run ngspice .op on extracted netlist
  If valid: confidence += 0.1 bonus
  
  Write to data/kg_seeds.jsonl:
  {
    "id": "paper_{slug}_fig_{n}",
    "source": "paper_extraction",
    "paper_title": "...",
    "circuit_family": "amplifier",
    "netlist": "...",
    "context_params": {...},
    "context_specs": {...},  
    "extraction_method": "sina|claude_vision",
    "extraction_confidence": 0.87,
    "sim_validated": true,
    "image_path": "papers/processed/{slug}/images/fig_042.png"
  }

BATCH CLI:
  python -m openanalog ingest --folder ./PDF/
  (your PDF/ folder already exists at C:\Users\oojia\OpenForge\PDF\)
  
CHECKPOINT: save progress JSON after each paper so crashes don't restart from zero
COST: ~$0.002 per image (Claude vision), ~$0.001 per text extraction
      50 papers × 8 schematics avg = 400 images × $0.003 = ~$1.20 total
```

---

### PHASE 4 — THE FORGE (simulation flywheel)
**Time: 3-5 days to build, then runs forever | This is the AlphaFold engine**

Goal: take ~5,000 validated seeds → generate 1,000,000 sim-validated training pairs

**Architecture — critical design decisions:**

**Decision 1: Parallelism strategy**
ngspice is single-threaded per call but you can run N instances in parallel.
On your machine: `--workers 8` = 8 parallel ngspice processes
On AWS spot (c5.4xlarge, 16 cores): `--workers 14` = ~280 sims/min
Target: 1M sims in ~60 hours of cloud time ≈ $12

**Decision 2: Mutation strategy per topology family**

```
CHARGE PUMP (Dickson N-stage):
  Seed params: N_stages (2-8), C_pump (1p-100p), f_clock (1M-100M), 
               W_switch (1u-20u), L_switch (0.15u-0.5u), VDD (1.2-3.3V)
  Fitness: Vout > N×VDD×0.85, ripple < 50mV, efficiency > 75%
  Mutation: vary N_stages (integer), scale C_pump, adjust W_switch

OTA (Folded Cascode):  
  Seed params: W1/L1 (input pair), W3/L3 (load), W5/L5 (tail), Ibias
  Fitness: GBW > 10MHz, PM > 60°, gain > 70dB, power < 2mW
  Mutation: scale W/L ratios, adjust Ibias, toggle cascode on/off

TIA (for crossbar output):
  Seed params: Gm (OTA), Rf (feedback R), Cf (feedback C), Ibias
  Fitness: BW > 1MHz, gain > 55dB, PM > 45°, power < 3mW, noise < 10nV/rtHz
  Mutation: vary Rf (log scale), tune Cf for stability, adjust Gm

FILTER (Sallen-Key LP):
  Seed params: R1, R2, C1, C2 (determine fc and Q)
  Fitness: fc within 10% of target, Q within 15%, stopband > 40dB
  Mutation: perturb R/C pairs maintaining fc×Q relationship

CURRENT MIRROR (Cascode Wilson):
  Seed params: W_ref, W_out (ratio = current gain), L, Vbias
  Fitness: current error < 1%, output swing > 0.8V, output impedance > 1MΩ
  Mutation: vary W ratio, adjust L for output impedance

CROSSBAR MVM UNIT:
  Seed params: W_pass, W_prog, VDD, weight_voltage range
  Fitness: linearity error < 5%, power per MAC < 10fW, BW > 1MHz
  Mutation: vary W_pass/W_prog ratio, adjust bias voltages
```

**Cursor task:**
```
Build the complete forge engine at openanalog/forge/

CRITICAL REQUIREMENT: The forge must be resumable.
Save state every 100 simulations to data/forge_state.json:
{
  "total_sims": 142847,
  "winners": 18442,
  "last_seed_id": "tia_v14_gen8",
  "kg_node_count": 847,
  "timestamp": "2026-05-06T14:23:11"
}
If forge_state.json exists on startup: resume from last checkpoint.
If --reset flag: start fresh.

PARALLELISM:
Use concurrent.futures.ProcessPoolExecutor(max_workers=N)
Each worker gets: (netlist_string, analyses_list, timeout)
Returns: SimResult or SimError
Never share state between workers — each writes to a per-worker temp file,
main process collects and writes to dataset.

PROGRESS DASHBOARD (rich library):
┌─────────────────────────────────────────────────────────┐
│  OpenAnalog Forge v0.1          [Ctrl+C to pause]       │
├─────────────────────────┬───────────────────────────────┤
│ Runtime                 │ 2h 14m 33s                    │
│ Sims total              │ 142,847                       │
│ Winners (fitness=1)     │ 18,442  (12.9%)               │
│ KG nodes live           │ 847                           │
│ KG nodes archived       │ 2,103                         │
│ Sim speed               │ 47.3 sims/sec                 │
│ ETA (1M target)         │ ~5h 32m remaining             │
├─────────────────────────┴───────────────────────────────┤
│ Topology     │ sims    │ winners │ pass% │ gen │ best   │
│ tia          │ 24,100  │  3,210  │ 13.3% │  14 │ 0.97   │
│ charge_pump  │ 31,200  │  2,890  │  9.3% │  19 │ 0.94   │
│ ota          │ 28,400  │  4,100  │ 14.4% │  11 │ 0.98   │
│ filter       │ 19,800  │  3,820  │ 19.3% │   8 │ 0.96   │
│ mirror       │ 22,100  │  3,100  │ 14.0% │  12 │ 0.99   │
│ crossbar     │ 17,247  │  1,322  │  7.7% │  22 │ 0.89   │
└──────────────┴─────────┴─────────┴───────┴─────┴────────┘
```

---

### PHASE 5 — KNOWLEDGE GRAPH + SELF-VERIFICATION
**Time: 2-3 days | This is the living brain of OpenAnalog**

The KG is not a static database. It's an evolutionary tree of what works.
Every winning netlist is a node. Every mutation relationship is an edge.
The KG answers: "given this spec, what proven topology should I start from?"

**KG structure — steal AnalogGenie's graph representation + add sim data:**

AnalogGenie uses a sequence-based, pin-level graph representation that efficiently and expressively captures large analog circuit topologies.
You use this same representation BUT add simulation-validated performance data to each node.

```python
# Node schema (NetworkX node attributes)
{
    # Identity
    "id": "tia_folded_cascode_v14",
    "topology_class": "tia",
    "generation": 14,
    "parent_id": "tia_folded_cascode_v13",
    
    # Circuit data  
    "netlist_template": "...",  # {W1}, {C1} placeholders
    "device_graph": {...},       # AnalogGenie pin-level adjacency
    "param_ranges": {
        "W_input": [2e-6, 8e-6],
        "Rf": [5000, 30000],
        "Ibias": [20e-6, 100e-6]
    },
    
    # Simulation-validated performance (THE KEY DIFFERENTIATOR)
    "sim_stats": {
        "bw_MHz":    {"min": 0.9, "max": 3.8, "mean": 1.8, "p90": 2.9},
        "gain_dB":   {"min": 58,  "max": 74,  "mean": 66,  "p90": 72},
        "power_mW":  {"min": 0.4, "max": 2.8, "mean": 1.2, "p90": 2.1},
        "PM_deg":    {"min": 47,  "max": 81,  "mean": 64,  "p90": 78}
    },
    "fitness_pass_rate": 0.73,
    "total_sims": 847,
    "total_winners": 618,
    
    # Provenance
    "paper_sources": ["razavi_2016_ch9", "sackinger_2005_tia"],
    "first_seen": "2026-05-06T14:23:11",
    "last_updated": "2026-05-06T18:41:02"
}
```

**KG scale control (prevents explosion to millions of nodes):**
- Max 500 live nodes per topology_class
- Prune: nodes with pass_rate < 0.05 after 30+ sims → archive
- Merge: nodes with param_vector cosine similarity > 0.95 → keep higher pass_rate
- Quantize: store param_ranges as INT8 for archived nodes (50% size reduction)
- Export: checkpoint to Neo4j every 10K sims

**Self-verification loop:**
```
Every generated netlist goes through 5 gates before entering KG:

Gate 1 (0ms):   SPICE syntax parser — all nodes connected, no syntax errors
Gate 2 (5s):    ngspice .op convergence — DC bias point stable
Gate 3 (30s):   ngspice .ac + .tran — full performance metrics
Gate 4 (0ms):   Fitness scorer — ALL spec checks pass with margin > 0
Gate 5 (optional, top 5% only): Claude review —
  "Does this netlist make physical sense for a {topology_class}?
   Rate confidence 1-10 and list any concerns."

Confidence score = product of gates passed:
  Pass 1-4: min 0.70 confidence (bronze — training data)
  Pass 1-5: min 0.90 confidence (gold — KG featured node)
```

**Cursor task:**
```
Build openanalog/verify/circuit_checker.py and 
openanalog/knowledge/graph.py with the schemas above.

Key method: KnowledgeGraph.query(spec: dict) → List[KGNode]
  Given: {"topology": "tia", "min_bw_MHz": 1.5, "max_power_mW": 2.0}
  Returns: top 5 KG nodes ranked by:
    1. spec_match_score (how well sim_stats overlap with requested spec)
    2. fitness_pass_rate (reliability)
    3. generation (more evolved = better)
  
  This is the v0 prompt-to-chip compiler before the finetuned model exists.
  It already works by just querying the KG with natural language specs
  parsed into structured filters.
```

---

### PHASE 6 — MODEL TRAINING + FINAL AGENT
**Time: 1 week + cloud training | The AlphaFold moment**

Only start this after Phase 4 produces 100K+ winners. Before that, train on KG retrieval.

**Training data format (Alpaca instruction tuning):**
```json
{
  "instruction": "Design a folded-cascode TIA in sky130 130nm process.\nSpecs: bandwidth > 1.5MHz, gain > 60dB, power < 2mW, phase margin > 50°, input capacitance = 200fF",
  "input": "",
  "output": "* Folded-cascode TIA — OpenAnalog verified\n* topology_id: tia_folded_cascode_v14\n* sim_result: bw=1.8MHz gain=63dB power=1.4mW PM=67deg\n\n.subckt tia_v14 inp inn outp VDD VSS\n...[full verified netlist]...\n.ends\n"
}
```

**Model choice:**
- **Qwen2.5-Coder-7B-Instruct** — best open code model, SPICE is structured code
- LoRA finetune: r=16, α=32, target q/k/v/o/gate/up projections
- 100K dataset → 1 epoch on A100 → ~4 hours → ~$4.40 (Lambda Labs)

**The verification loop at inference time (the final magic):**
```
User: "Give me a TIA for my crossbar array, 45nm-equivalent, BW > 2MHz, power under 1mW"

Step 1: Parse spec → structured filter dict
Step 2: Query KG → retrieve top 3 matching topology templates  
Step 3: Model generates netlist (informed by KG context in prompt)
Step 4: AUTO-VERIFY:
  → ngspice simulation (30s)
  → fitness check
  → if PASS: return netlist + sim results to user  ✓
  → if FAIL: extract failure reason, regenerate with reason in prompt
  → max 3 retries
  → if still failing: return best attempt + "low confidence" warning
Step 5: Every successful inference → append to training data → model improves
```

**This is the flywheel that makes it self-improving:**
More users → more prompts → more sim-verified netlists → better training data → better model → more users

---

## COMPLETE EXECUTION SEQUENCE

```
TODAY (Phase 1):
  1. Run WSL setup: wsl --install -d Ubuntu-22.04
  2. wsl -e bash -c "cd /mnt/c/Users/oojia/OpenForge && bash setup.sh"
  3. Test: python -m openanalog load-seeds --dry-run
  4. Paste STEP 0 audit prompt into Cursor (understand what repos you have)

DAY 2-3 (Phase 2):
  5. Cursor builds seed_loader.py with 3 loaders
  6. Run: python -m openanalog load-seeds
  7. Target: 3,000+ sim-validated seeds across 6 topology classes

DAY 4-6 (Phase 3):
  8. Drop your PDF papers into C:\Users\oojia\OpenForge\PDF\
  9. Cursor builds pdf_pipeline.py
  10. Run: python -m openanalog ingest --folder ./PDF/
  11. Target: 500+ additional seeds from paper extraction
  12. Add Anthropic API key to .env

DAY 7-10 (Phase 4):
  13. Cursor builds forge/ (generator + simulator + fitness + mutator)
  14. Test locally: python -m openanalog forge --topology tia --n 100
  15. Scale: python -m openanalog forge --all --n 1000000 --workers 8
  16. Let it run overnight — target 100K winners

DAY 11-12 (Phase 5):
  17. Cursor builds knowledge_graph.py + circuit_checker.py
  18. Test KG query: python -m openanalog query "TIA BW>1MHz power<2mW"
  19. Should return top 3 matching nodes from KG with sim stats

DAY 13-14 (Phase 6 prep):
  20. Build dataset_builder.py — emit training JSONL from winners
  21. Push dataset to HuggingFace Hub (public — this is your community moat)

WEEK 3+ (Phase 6 training):
  22. Rent A100 on Lambda Labs ($1.10/hr)
  23. Finetune Qwen2.5-Coder-7B on winners.jsonl (LoRA, ~4hrs)
  24. Deploy with inference verification loop
  25. Ship v0.1 with GitHub README + HuggingFace model card
```

---

## THE CURSOR SYSTEM PROMPT (paste once, use for all tasks)

Set this as Cursor's system/rules file (`.cursor/rules` or system prompt):

```
You are working on OpenAnalog — an open-source analog IC design automation 
platform located at C:\Users\oojia\OpenForge\

Project goal: Build an AlphaFold equivalent for analog circuit design.
The pipeline: PDF papers → schematic extraction → SPICE seeds → 
evolutionary simulation forge → knowledge graph → finetuned LLM → 
prompt-to-chip compiler.

CRITICAL RULES:
1. Before writing any new code, read the README of existing repos in the 
   workspace. Never rewrite what already exists.
2. All code must work in both WSL (Ubuntu 22.04) and Windows via the venv
   at .venv/. Use pathlib.Path everywhere, never hardcode separators.
3. ngspice runs as subprocess. Always set timeout=30s. Always capture stderr.
   A sim that doesn't converge is NOT an error — it's a fitness=0 result.
4. The fitness gate is sacred: fitness=0 data NEVER enters training set.
   It goes to losers.jsonl only. This is non-negotiable.
5. Every module needs a --dry-run flag that skips simulation for testing.
6. Use rich library for all CLI output. Progress bars, tables, live dashboard.
7. All data writes are atomic (write to .tmp, then rename) to prevent corruption.
8. The KG is the source of truth. When in doubt, query the KG first.

Current Python env: .venv (activate with .venv\Scripts\activate on Windows,
source .venv/bin/activate on Linux/WSL)
Key packages installed: pyspice, networkx, anthropic, rich, typer, torch,
ultralytics, marker-pdf, huggingface_hub, sky130

Existing repos to READ and potentially USE:
- AnalogGenie: topology generation + graph representation (USE graph format)
- spice-datasets: raw netlists as seeds (USE after filtering)
- symbench-studio: design API client (INVESTIGATE)
- spice-completion: ML for netlist completion (INVESTIGATE — may be useful)
- GraphGYM: GNN training framework (USE for Phase 6 GNN experiments)
- ZeroSim: possibly zero-shot simulation (INVESTIGATE)
```

---

## PAPERS TO DROP IN PDF/ RIGHT NOW

These are the highest-value papers for seeding topology knowledge.
All available free on arxiv or via Google Scholar:

**Mandatory (foundation):**
- Razavi, "Design of Analog CMOS Integrated Circuits" — textbook (skip copyright, use open excerpts)
- Masala-CHAI paper (arXiv 2411.14299) — read their textbook list, get same books
- SINA paper (arXiv 2601.22114) — may contain sample schematics
- AnalogGenie paper (arXiv 2503.00205) — their dataset methodology

**Charge pump specific:**
- Dickson 1976 charge pump — original paper
- "A High-Efficiency Charge Pump Circuit for Low-Supply-Voltage" — multiple variants
- Any Fibonacci/Cockcroft-Walton topology paper

**OTA/TIA specific:**
- "A 1.8V 67dB SNR CMOS Folded-Cascode OTA" — classic topology
- Säckinger & Guggenbuhl 1990 — transimpedance amplifier fundamentals
- "Design of High-Speed Low-Power TIA for Optical Receivers"

**Neuromorphic/crossbar:**
- "ISAAC: A Convolutional Neural Network Accelerator with In-Situ Analog Arithmetic"
- "Analog In-Memory Computing in FeFET-Based 1T1R Array"
- Any Mythic AI technical paper (search: "Mythic analog matrix processor")

**Drop these PDFs in C:\Users\oojia\OpenForge\PDF\ before running ingest.**

---

## WHAT "DONE" LOOKS LIKE

```
v0.1 (2 weeks from now):
  - 100K sim-validated training pairs
  - KG with 2,000 live nodes
  - CLI: python -m openanalog query "TIA BW>1MHz sky130"
  - Returns: top 3 KG nodes with verified SPICE + sim results
  - GitHub public, HuggingFace dataset public

v0.2 (1 month):  
  - Finetuned Qwen2.5-Coder-7B on 100K winners
  - CLI: python -m openanalog generate "folded cascode TIA, 1MHz BW, 2mW max"
  - Returns: model-generated + ngspice-verified netlist
  - Inference loop: auto-retries until fitness=1 or max 3 tries

v1.0 (3 months):
  - 1M sim-validated training pairs
  - Model accuracy: >80% first-pass fitness rate
  - "Give me a crossbar MVM array, 4x4, sky130, under 10mW" → working chip design
  - This is the moment OpenAnalog becomes real

v2.0 (6 months):
  - Prompt → SPICE → ngspice verify → Cadence SKILL layout script
  - Full analog design flow, no human in the loop
  - First external contributors
  - This is when the Synopsys conversation starts
```

---

## COST ESTIMATE (total to v1.0)

| Item | Cost |
|---|---|
| Claude API (PDF ingestion, 50 papers × ~10 images) | ~$2 |
| ngspice (free, local) | $0 |
| AWS spot c5.4xlarge (1M sims, ~60 hrs) | ~$12 |
| Lambda Labs A100 (finetuning, 4 hrs) | ~$5 |
| HuggingFace (free tier) | $0 |
| **TOTAL to v1.0** | **~$20** |

This is the most capital-efficient path to a genuinely novel AI research project
that could become a company. AlphaFold had a team of 20 and DeepMind compute.
OpenAnalog has you, Cursor, $20 of cloud credits, and the right idea.

LFG.
