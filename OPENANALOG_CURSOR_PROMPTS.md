# OpenAnalog — Complete Cursor Prompt Package
## Drop this folder in your repo root. Run `setup.sh`. Then prompt Cursor with each task block.

---

## ANSWER TO YOUR QUESTION FIRST

**Do you need to scrape PDFs manually? NO.**

Here is exactly what already exists free:

| Source | What you get | How |
|---|---|---|
| `github.com/jitendra-bhandari/Masala-CHAI` | 7,500 schematics + netlists | `git clone` |
| `arxiv.org/abs/2407.18272` (AICircuit) | Multi-level analog+RF param sweeps | `git clone` |
| `github.com/symbench/spice-datasets` | KiCad netlists from GitHub | `git clone` |
| `arxiv.org/abs/2503.00205` (AnalogGenie) | Graph topology dataset | `git clone` |
| Semantic Scholar API | 100K+ paper abstracts, free, no key needed | `requests` |
| arXiv API | Free bulk PDF download, cs.AR + eess.SP | `requests` |
| SkyWater sky130 PDK | Real 130nm SPICE transistor models | `pip install sky130` |
| IHP SG13G2 PDK | 130nm BiCMOS free process | `git clone` |

**The key insight:** Papers give you TOPOLOGY SEEDS (what the valid circuit families look like).
The forge generates the actual training data by mutating seeds millions of times through ngspice.
Physics = infinite free training data. You never run out.

---

## WHAT THE EXISTING DATASETS ACTUALLY ARE

Before building, understand what you're inheriting:

### Masala-CHAI
- **Type:** Schematic IMAGE → SPICE netlist pairs
- **Size:** 7,500 samples from 10 analog textbooks
- **Format:** PNG schematic + .sp netlist + natural language description
- **Gap:** No simulation results. Netlists not verified. No fitness scoring.
- **Your use:** Seed topology library + image→netlist training pairs

### AICircuit
- **Type:** Multi-level analog + RF circuit dataset with parameter sweeps
- **Size:** Hundreds of topologies, thousands of param variants
- **Format:** Circuit spec → performance metrics (some simulated)
- **Gap:** Limited to known topologies. No evolutionary mutation.
- **Your use:** Fitness spec ranges per topology class (what "good" looks like)

### AnalogGenie
- **Type:** Graph-based topology representation dataset
- **Size:** Comprehensive coverage of OpAmp family topologies
- **Format:** Sequence-based graph adjacency + component labels
- **Gap:** Generation only, no simulation loop, no KG
- **Your use:** Graph representation format — steal their adjacency matrix encoding

### symbench/spice-datasets
- **Type:** Raw KiCad/LTSpice netlists scraped from GitHub
- **Size:** Thousands of netlists, mixed quality
- **Format:** Raw .sp / .net files
- **Gap:** Noisy, mixed digital/analog, no labels
- **Your use:** Additional seed diversity after cleaning

---

## THE TOOL STACK (all free, all open)

### PDF → Markdown
**Tool: Marker** (`github.com/datalab-to/marker`)
- Best-in-class PDF→Markdown with image extraction
- Preserves circuit figure locations as `![fig_X](images/fig_X.png)`
- Use `--use_llm` flag with Claude/GPT-4o for formula correction
- Exports images automatically — zero manual cropping

### Schematic Image → Netlist
**Tool: SINA** (`arxiv.org/abs/2601.22114`) — 96.47% accuracy
- YOLOv11 component detection + CCL connectivity + OCR + VLM
- Open source, fully automated
- Stack: `YOLOv11 → Connected Component Labeling → OCR → Claude vision`
- Understands: transistors, capacitors, resistors, op-amps, wire connections

**Fallback: Claude Vision API** (for complex schematics SINA misses)
- Send cropped schematic PNG → ask Claude to output SPICE netlist
- Use structured output: component list + node connections + values

### Knowledge Graph
**Tool: NetworkX** (in-memory) + **Neo4j** (persistent, free community edition)
- Nodes = validated circuit primitives
- Edges = composition rules (TIA connects to crossbar output)
- Properties = sim-validated performance ranges per node
- **Scale control:** VQ-GNN quantization for large graphs (50% size reduction, <1% accuracy loss per arXiv 2510.22058)

### Simulation
**Tool: ngspice** (free, subprocess call, ~50ms per simple circuit)
**PDK:** SkyWater sky130 (real 130nm transistor models, Google-sponsored)

### Self-verification
**Tool:** Python fitness scorer + Claude API for confidence judgment
- Binary pass/fail per spec
- Claude rates ambiguous cases (0.4–0.6 confidence zone) as "needs re-sim"

---

## WSL + WINDOWS ENVIRONMENT SETUP

### One-time WSL setup (run once, never think about it again)

```bash
# In PowerShell as Admin — install WSL2 with Ubuntu
wsl --install -d Ubuntu-22.04
wsl --set-default-version 2
```

### `setup.sh` — paste this into your repo root, run inside WSL

```bash
#!/bin/bash
set -e
echo "=== OpenAnalog Environment Setup ==="

# Detect environment
if grep -qi microsoft /proc/version; then
    echo "[WSL detected] Configuring for WSL2..."
    IS_WSL=true
else
    echo "[Linux detected]"
    IS_WSL=false
fi

# System deps
sudo apt-get update -qq
sudo apt-get install -y ngspice git python3-pip python3-venv \
    poppler-utils tesseract-ocr libgl1-mesa-glx \
    nodejs npm curl wget unzip

# Python venv — always isolated, never pollutes system
python3 -m venv .venv
source .venv/bin/activate

# Core Python packages
pip install --upgrade pip
pip install \
    marker-pdf \
    pyspice \
    networkx \
    neo4j \
    anthropic \
    openai \
    torch torchvision \
    ultralytics \
    huggingface_hub \
    datasets \
    transformers \
    peft \
    tqdm \
    rich \
    typer \
    pydantic \
    numpy scipy matplotlib \
    scikit-learn \
    sky130

# Install sky130 PDK (real transistor models)
pip install sky130
python -c "import sky130; sky130.setup()" 2>/dev/null || true

# Clone free datasets
mkdir -p data/seeds
if [ ! -d "data/seeds/Masala-CHAI" ]; then
    echo "[Cloning Masala-CHAI...]"
    git clone --depth=1 https://github.com/jitendra-bhandari/Masala-CHAI \
        data/seeds/Masala-CHAI
fi
if [ ! -d "data/seeds/spice-datasets" ]; then
    echo "[Cloning spice-datasets...]"
    git clone --depth=1 https://github.com/symbench/spice-datasets \
        data/seeds/spice-datasets
fi

# WSL-specific: fix ngspice path
if [ "$IS_WSL" = true ]; then
    echo 'export NGSPICE_PATH=$(which ngspice)' >> .venv/bin/activate
    echo 'export DISPLAY=:0' >> .venv/bin/activate  # for any GUI tools
fi

# Create .env template
cat > .env << 'EOF'
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here_optional
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=openanalog
NGSPICE_TIMEOUT=30
SIM_WORKERS=4
EOF

echo ""
echo "=== Setup complete ==="
echo "Activate: source .venv/bin/activate"
echo "Add API keys to .env"
echo "Run: python -m openanalog --help"
```

### Windows shortcut (run from PowerShell)
```powershell
# Run the whole pipeline from Windows without touching WSL manually
wsl -e bash -c "cd /mnt/c/Users/$env:USERNAME/openanalog && source .venv/bin/activate && python -m openanalog $args"
```

---

## CURSOR PROMPT — TASK 001: PDF INGESTION PIPELINE

Paste this entire block into Cursor:

```
=== OPENANALOG TASK-001: PDF INGESTION PIPELINE ===

Build: openanalog/ingestion/pdf_pipeline.py

This is the entry point. User drops PDFs into ./papers/inbox/
Running `python -m openanalog ingest` processes everything automatically.

PIPELINE STEPS:

Step 1 — PDF → Markdown + image extraction
  Tool: marker-pdf library
  Code:
    from marker.convert import convert_single_pdf
    from marker.models import load_all_models
    models = load_all_models()
    full_text, images, metadata = convert_single_pdf(pdf_path, models)
  Output:
    papers/processed/{paper_slug}/
      full_text.md          # full paper as markdown
      images/fig_001.png    # every figure extracted
      images/fig_002.png
      metadata.json         # title, authors, year, abstract

Step 2 — Detect circuit schematic images
  For each extracted image:
    - Send to Claude vision API with prompt:
      "Is this image a circuit schematic showing electronic components
       (transistors, capacitors, resistors, op-amps, wires)?
       Answer JSON: {is_schematic: bool, confidence: float, 
       circuit_type: str, components_visible: [str]}"
    - If is_schematic=True AND confidence>0.7: mark as schematic
    - Save to papers/processed/{slug}/schematics/fig_XXX.png
    - Write location marker in full_text.md:
      <!-- SCHEMATIC: fig_XXX | type: charge_pump | confidence: 0.92 -->

Step 3 — Extract circuit parameters from surrounding text
  For each schematic, find the 500 tokens before and after its location
  in full_text.md. Send to Claude:
    "Extract all circuit parameters mentioned near this schematic:
     component values (R, C, W/L ratios), supply voltages, 
     target specs (gain, bandwidth, power, noise).
     Output JSON: {params: {name: value_with_unit}, specs: {metric: target}}"
  Save as: schematics/fig_XXX_params.json

Step 4 — Schematic image → SPICE netlist (SINA pipeline)
  Primary: SINA tool (YOLOv11 + CCL + OCR)
    - Detects component bounding boxes + type labels
    - Traces wire connections via Connected Component Labeling  
    - OCR extracts component reference designators (R1, M1, C2...)
    - VLM resolves ambiguous connections
  Fallback (if SINA confidence < 0.7): Claude vision
    System prompt: "You are an expert analog IC designer.
    Convert this circuit schematic image to a SPICE netlist.
    Rules:
    - Every node must have a unique name (net_001, net_002...)
    - Ground = 0
    - Use standard SPICE syntax: M1 drain gate source bulk NMOS W=2u L=0.18u
    - Include .model statements for NMOS/PMOS using sky130 parameters
    - End with .end
    Output ONLY the raw SPICE netlist, no explanation."
  Save as: schematics/fig_XXX.sp
  Confidence score: schematics/fig_XXX_confidence.json

Step 5 — Validate extracted netlist
  Run ngspice on extracted netlist:
    import subprocess
    result = subprocess.run(['ngspice', '-b', netlist_path], 
                           capture_output=True, timeout=30)
    valid = result.returncode == 0
  If valid: mark status="validated"
  If invalid: status="extraction_failed", log error for manual review

Step 6 — Write to knowledge graph seed file
  Append to data/kg_seeds.jsonl:
  {
    "source": "paper",
    "paper": "paper_slug",
    "figure": "fig_XXX",
    "circuit_type": "charge_pump",
    "netlist": "...raw spice...",
    "params": {...},
    "specs": {...},
    "extraction_confidence": 0.92,
    "sim_validated": true,
    "timestamp": "ISO8601"
  }

PROGRESS TRACKING:
  Use rich.progress for live terminal UI showing:
  - Papers processed / total
  - Schematics found / validated
  - KG seeds written
  Save checkpoint after each paper → resume on crash

CLI:
  python -m openanalog ingest --folder ./papers/inbox/
  python -m openanalog ingest --paper ./papers/inbox/razavi_2016.pdf
  python -m openanalog ingest --status   # show progress dashboard

CONFIDENCE TRACKING (critical):
  Every extracted object carries a confidence score 0.0-1.0
  Threshold rules:
    >= 0.9 : AUTO-ACCEPT, goes straight to KG seeds
    0.7-0.9: AUTO-ACCEPT with "needs_review" flag
    0.5-0.7: HOLD — Claude re-examines with chain-of-thought
    < 0.5  : REJECT — logged but not used as seed
```

---

## CURSOR PROMPT — TASK 002: SEED DATASET INTEGRATION

```
=== OPENANALOG TASK-002: INTEGRATE FREE DATASETS ===

Build: openanalog/ingestion/seed_loader.py

Load and normalize all 4 free datasets into unified format.

MASALA-CHAI LOADER:
  Path: data/seeds/Masala-CHAI/
  Structure: each sample has scanned_circuit.png + generated .sp netlist
  Action:
    - Read all .sp files
    - Validate each via ngspice subprocess
    - Extract circuit_type from filename/content (heuristic + Claude classify)
    - Emit to data/seeds_normalized.jsonl

AICIRCUIT LOADER (download via HuggingFace):
  from huggingface_hub import snapshot_download
  snapshot_download("aicircuit/AICircuit", local_dir="data/seeds/AICircuit")
  - This dataset has param sweeps with performance metrics
  - USE THIS for fitness spec calibration per topology class
  - Extract: {topology_type, param_ranges, perf_metrics} per circuit family

ANALOGGENIE LOADER:
  arxiv 2503.00205 — check GitHub link in paper for dataset
  - Graph adjacency matrix format
  - Convert to our netlist format using their provided converter
  - Steal their component vocabulary (node type labels)

SYMBENCH LOADER:
  Path: data/seeds/spice-datasets/
  - Mixed quality — run ngspice filter first
  - Only keep netlists that simulate without errors
  - Classify circuit type via component count heuristic

OUTPUT: data/seeds_normalized.jsonl
  Unified schema:
  {
    "id": "masala_chai_0042",
    "source": "masala_chai",
    "circuit_type": "tia",          // charge_pump | tia | ota | filter | mirror | crossbar
    "netlist": "...",
    "param_hints": {},              // known component values from source
    "spec_hints": {},               // known target specs from source
    "sim_validated": true,
    "source_confidence": 0.85
  }

STATS REPORT after loading:
  Print table showing per topology_type:
  - seed count
  - sim validation rate
  - param coverage (% of key params known)
```

---

## CURSOR PROMPT — TASK 003: FORGE + EVOLUTIONARY LOOP

```
=== OPENANALOG TASK-003: SIMULATION FORGE ===

Build: openanalog/forge/

This is the core engine. Takes seeds → generates millions of variants →
simulates → scores → evolves → writes training data.

forge/generator.py — param mutation engine
  For each seed topology, randomize component values within valid ranges:
  
  RANGES PER COMPONENT TYPE (sky130 130nm):
    NMOS W: 0.5u to 10u    L: 0.15u to 2u
    PMOS W: 1u to 20u      L: 0.15u to 2u  
    Resistor: 1k to 1M (log-uniform sampling)
    Capacitor: 10f to 10p  (log-uniform)
    Current source: 1u to 500u
    Supply VDD: 1.2V to 3.3V
  
  Mutation strategies:
    - RANDOM: all params randomized independently (exploration)
    - DIRECTED: only failed params mutated (exploitation, guided by fitness)
    - CROSSOVER: blend two high-fitness parents
  
  Always validate electrical rules before sending to sim:
    - No floating nodes
    - VDD > VSS
    - W/L ratios in physical range
    - DC bias point feasibility check (quick heuristic)

forge/simulator.py — ngspice wrapper
  def simulate(netlist: str, analyses: list) -> SimResult:
    Write netlist to tmp file
    Append sky130 .model cards
    Append requested analyses:
      .op              — DC operating point (always)
      .ac dec 100 1 10G — frequency sweep (for BW, gain, phase)
      .tran 1n 10u     — transient (for charge pumps, dynamic circuits)
      .measure commands for: gain_dB, bw_3db_MHz, phase_margin, 
                             power_mW, output_voltage, ripple_mV
    subprocess.run(['ngspice', '-b', tmp_file], timeout=30)
    Parse output → SimResult dataclass
    Cache result by netlist hash (never re-sim same netlist twice)

forge/fitness.py — binary scorer per topology class
  class FitnessSpec:
    topology: str
    checks: dict[str, Callable]  # metric → pass condition
  
  SPECS:
    "tia":         bw>1MHz, gain>55dB, PM>45°, power<3mW
    "ota":         GBW>10MHz, PM>60°, gain>70dB, power<2mW  
    "charge_pump": Vout>2*VDD*0.9, ripple<50mV, efficiency>80%
    "filter_lp":   fc_within_10pct, stopband>40dB, power<1mW
    "mirror":      matching_error<1pct, output_swing>0.8V, power<0.5mW
    "crossbar_tia": bw>1MHz, linearity_error<5pct, power<5mW
  
  Returns: score=1|0, failed_checks=[], margin_per_check={}
  The margin (how far from threshold) feeds the mutation engine

forge/mutator.py — directed evolution
  Takes: parent_netlist, failed_checks, margins
  Returns: child_netlist with targeted mutations
  
  Rules:
    failed "bw": increase Gm (wider W) OR reduce Cf
    failed "gain": increase gain stage W/L OR add cascode
    failed "power": reduce bias current OR scale down W
    failed "PM": increase Cc OR reduce second-stage gain
    failed "ripple": increase pump capacitors
  
  After 10 generations without improvement: trigger RANDOM mutation
  After 50 generations: retire topology branch, log as dead end

forge/knowledge_graph.py
  NetworkX DiGraph
  
  Node schema:
    id: str (topology_type + hash of winning params)
    netlist_template: str (param placeholders as {W1}, {C1}...)
    param_ranges: dict (validated working ranges)
    sim_stats: dict (mean/min/max of all passing sims)
    fitness_pass_rate: float (winners / total attempts)
    generation: int
    parent_id: str
    paper_sources: list[str]
  
  Edge schema:
    type: "evolved_from" | "composes_with" | "alternative_to"
    composition rules: {"tia" connects_after "crossbar_mvm"}
  
  Pruning rules (run after every 1000 sims):
    - Remove nodes with pass_rate < 0.05 after 20+ attempts
    - Archive (don't delete) — keep for "what fails" reasoning
    - Merge near-identical nodes (cosine sim > 0.95 on param vectors)
  
  KG SIZE CONTROL (prevents explosion):
    Max nodes per topology_class: 500 live + 2000 archived
    Use VQ-GNN quantization on embedding layer (INT8, 50% size reduction)
    Checkpoint KG to Neo4j every 10K sims for persistence

forge/dataset_writer.py
  Writes training data to data/training/
  
  CRITICAL RULES:
    fitness=1 → data/training/winners.jsonl    (model training)
    fitness=0 → data/training/losers.jsonl     (mutation guidance only)
    NEVER mix them. Model only trains on winners.
  
  Winner record schema:
  {
    "instruction": "Design a TIA with BW>1MHz, gain>60dB, power<2mW, sky130 130nm",
    "input": "",
    "output": "...verified SPICE netlist...",
    "sim_result": {"bw_MHz":1.8,"gain_dB":63,"power_mW":1.4,"PM_deg":67},
    "fitness": 1,
    "topology_id": "tia_folded_cascode_v14",
    "generation": 14,
    "pass_margins": {"bw":0.8,"gain":3,"power":0.6,"PM":22}
  }

CLI:
  python -m openanalog forge --topology tia --n 10000
  python -m openanalog forge --all --n 100000
  python -m openanalog forge --status   # live dashboard
```

---

## CURSOR PROMPT — TASK 004: SELF-VERIFICATION LOOP

```
=== OPENANALOG TASK-004: SELF-VERIFICATION + CONFIDENCE SYSTEM ===

Build: openanalog/verify/

Every output in this pipeline carries a confidence score.
Nothing enters the KG or training set without passing verification.

verify/circuit_checker.py
  Level 1 — SPICE syntax check (instant, free)
    Parse netlist: all nodes connected, no syntax errors
    
  Level 2 — ngspice simulation (30s max)
    DC operating point converges
    No "timestep too small" errors
    No node voltage overflow (>10*VDD suspicious)
    
  Level 3 — Physics sanity check (rule-based)
    MOSFET operating region check (sat/lin/off)
    Current density check (J < Jmax for each device)
    Supply current budget (sum of branch currents = Isupply ± 1%)
    
  Level 4 — Spec fitness (per topology_class)
    All fitness checks pass with margin > 0
    
  Level 5 — Claude cross-check (only for high-stakes / top-5% performers)
    Send netlist + sim results to Claude:
    "Review this SPICE netlist and simulation results.
     Does the topology make sense for a {circuit_type}?
     Are there any obvious design flaws?
     Confidence: X/10, Issues: [list]"
    
  Each level returns: passed: bool, confidence_contribution: float
  Final confidence = weighted product of all levels passed
  
  Confidence thresholds:
    >= 0.95: GOLD — enters KG as featured node
    0.85-0.95: SILVER — enters KG as standard node
    0.70-0.85: BRONZE — enters training data, not KG
    < 0.70:  REJECT — logged, feeds mutation engine only

verify/dashboard.py
  Rich terminal live dashboard showing:
  ┌─────────────────────────────────────────────┐
  │ OpenAnalog Forge — Live Status              │
  ├──────────────┬──────────────────────────────┤
  │ Sims run     │ 142,847                      │
  │ Winners (1)  │ 18,442  (12.9%)              │
  │ KG nodes     │ 847 live / 2,103 archived    │
  │ Training     │ 18,442 records               │
  │ Sim speed    │ 47 sims/sec (8 workers)      │
  ├──────────────┼──────────────────────────────┤
  │ Per topology │ seeds  winners  pass_rate     │
  │ tia          │ 24,100  3,210   13.3%        │
  │ charge_pump  │ 31,200  2,890   9.3%         │
  │ ota          │ 28,400  4,100   14.4%        │
  │ filter       │ 19,800  3,820   19.3%        │
  │ mirror       │ 22,100  3,100   14.0%        │
  │ crossbar     │ 17,247  1,322   7.7%         │
  └──────────────┴──────────────────────────────┘
```

---

## CURSOR PROMPT — TASK 005: TRAINING PLAN

```
=== OPENANALOG TASK-005: MODEL FINETUNING PLAN ===

Build: openanalog/trainer/

BASE MODEL: Qwen2.5-Coder-7B-Instruct
  Why: Best open code model, SPICE is structured code, 7B fits on single A100
  Alternative: CodeLlama-13B if more capacity needed

TRAINING FORMAT (Alpaca instruction format):
  {
    "instruction": "Design a folded-cascode OTA in sky130 130nm.
                    Specs: GBW > 50MHz, phase margin > 60°, 
                    power < 1mW, load cap = 1pF",
    "input": "",
    "output": ".subckt folded_cascode_ota ...\n[verified netlist]\n.ends"
  }

LORA CONFIG (fits on free Colab A100):
  r=16, alpha=32, dropout=0.05
  target_modules: ["q_proj","v_proj","k_proj","o_proj","gate_proj","up_proj"]
  
TRAINING:
  Phase 1: 100K winners → initial finetune (1 epoch, A100, ~4 hrs)
  Phase 2: 1M winners → full finetune (3 epochs, A100x4, ~48 hrs)
  Phase 3: RLHF-lite — use ngspice as reward function
    Generate netlist → simulate → pass_rate is the reward signal
    PPO or GRPO (DeepSeek-style) with physics as verifier

CLOUD COST ESTIMATE:
  ngspice: ~50ms/sim → 1M sims = 50,000 CPU-seconds
  On AWS spot (c5.4xlarge, 16 cores): ~$0.68/hr
  1M sims parallelized across 16 cores: ~50 mins → ~$0.57
  
  Training on Lambda Labs A100: ~$1.10/hr
  100K dataset, 1 epoch: ~4 hrs → ~$4.40
  Total Phase 1: under $10.

SELF-VERIFICATION DURING INFERENCE:
  After model generates a netlist:
    1. SPICE syntax parse (instant)
    2. ngspice simulation (30s)
    3. If fitness=1: return to user with sim results
    4. If fitness=0: regenerate with failure reason in prompt
    5. Max 3 retries — then return best attempt with low confidence flag
  
  This is the verification loop that makes it trustworthy.
```

---

## FOLDER STRUCTURE

```
openanalog/
├── setup.sh                    # run once — sets up WSL + Python env
├── .env                        # API keys (not committed)
├── .gitignore
├── pyproject.toml
├── README.md
│
├── papers/
│   └── inbox/                  # DROP YOUR PDFs HERE
│
├── data/
│   ├── seeds/                  # auto-cloned free datasets
│   ├── seeds_normalized.jsonl  # unified seed format
│   ├── kg_seeds.jsonl          # paper-extracted seeds
│   ├── training/
│   │   ├── winners.jsonl       # fitness=1 only — model trains on this
│   │   └── losers.jsonl        # fitness=0 — mutation engine only
│   └── knowledge_graph/
│       ├── graph.gpickle       # NetworkX checkpoint
│       └── neo4j_export/       # for Neo4j import
│
├── openanalog/
│   ├── __main__.py             # python -m openanalog
│   ├── ingestion/
│   │   ├── pdf_pipeline.py     # TASK-001
│   │   └── seed_loader.py      # TASK-002
│   ├── forge/
│   │   ├── generator.py        # TASK-003
│   │   ├── simulator.py
│   │   ├── fitness.py
│   │   ├── mutator.py
│   │   ├── knowledge_graph.py
│   │   └── dataset_writer.py
│   ├── verify/
│   │   ├── circuit_checker.py  # TASK-004
│   │   └── dashboard.py
│   └── trainer/
│       ├── dataset_builder.py  # TASK-005
│       └── finetune.py
│
└── tests/
    ├── test_simulator.py
    ├── test_fitness.py
    └── test_pipeline_e2e.py
```

---

## HOW TO RUN THE WHOLE THING

```bash
# 1. Clone this repo and setup
git clone https://github.com/YOU/openanalog
cd openanalog
bash setup.sh
source .venv/bin/activate
cp .env.template .env  # add your Anthropic API key

# 2. Drop PDFs into papers/inbox/
#    (Razavi, Gregorian, Allen-Holberg, your own collected papers)

# 3. Run ingestion (processes all PDFs, extracts schematics, validates)
python -m openanalog ingest --folder ./papers/inbox/

# 4. Load free datasets (runs once)
python -m openanalog load-seeds

# 5. Start the forge (generates + simulates + evolves)
python -m openanalog forge --all --n 1000000 --workers 8

# 6. Monitor live
python -m openanalog status

# 7. When you have enough winners, train the model
python -m openanalog train --dataset data/training/winners.jsonl
```

---

## THE VISION IN ONE SENTENCE

Drop a PDF → extract every schematic → understand every connection →
simulate every variant → keep only what works → train a model on winners →
prompt it like ChatGPT → get a verified analog chip design in 10 seconds.

That is OpenAnalog.
