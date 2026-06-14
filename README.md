# OpenAnalog

PDF → schematic → SPICE → ngspice forge → training data for analog IC design.

## Quick start (Windows + WSL recommended for ngspice)

```powershell
cd C:\Users\oojia\OpenForge
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
```

WSL (full stack including ngspice + marker):

```bash
bash setup.sh
source .venv/bin/activate
```

## Commands

| Command | Purpose |
|---------|---------|
| `python -m openanalog ingest --folder ./papers/inbox/` | TASK-001 PDF pipeline |
| `python -m openanalog ingest --status` | Ingest progress |
| `python -m openanalog load-seeds` | TASK-002 normalize free datasets |
| `python -m openanalog forge --topology tia --n 1000` | TASK-003 evolutionary forge |
| `python -m openanalog status` | Live dashboard |
| `python -m openanalog train --dataset data/training/winners.jsonl` | TASK-005 LoRA finetune |

## Claude feedback (constrained)

Confidence zones from `OPENANALOG_CURSOR_PROMPTS.md`:

- **≥ 0.9** — auto-accept to KG seeds
- **0.7–0.9** — accept with `needs_review`
- **0.5–0.7** — Claude chain-of-thought re-examination (`openanalog/claude.py`)
- **< 0.5** — reject

Top forge performers optionally get Level-5 Claude netlist review.

## API keys

Copy `ANTHROPIC_API_KEY` into `.env` (or use existing `env.local` — loaded automatically).

## Data

- Drop PDFs in `papers/inbox/`
- `spice-datasets` at repo root is used automatically if `data/seeds/spice-datasets` is missing
- Masala-CHAI: `git clone --depth=1 https://github.com/jitendra-bhandari/Masala-CHAI data/seeds/Masala-CHAI`
