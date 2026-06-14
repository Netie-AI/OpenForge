from __future__ import annotations

import os
import platform
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "env.local")

PAPERS_INBOX = ROOT / "papers" / "inbox"
PDF_INBOX = ROOT / "PDF"
PAPERS_PROCESSED = ROOT / "papers" / "processed"
DATA_DIR = ROOT / "data"
ANALOGGENIE_DIR = ROOT / "AnalogGenie"
SEEDS_DIR = DATA_DIR / "seeds"
MASALA_DIR = SEEDS_DIR / "Masala-CHAI"
KG_SEEDS = DATA_DIR / "kg_seeds.jsonl"
SEEDS_NORMALIZED = DATA_DIR / "seeds_normalized.jsonl"
TRAINING_DIR = DATA_DIR / "training"
KG_DIR = DATA_DIR / "knowledge_graph"
CHECKPOINT = DATA_DIR / "checkpoint.json"
FORGE_STATE = DATA_DIR / "forge_state.json"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
SEA_LION_API_KEY = os.getenv("SEA_LION_API_KEY", "")

# LLM routing — upgrade models via env without code changes
OPENFORGE_LLM_PROVIDER = os.getenv("OPENFORGE_LLM_PROVIDER", "openrouter")
OPENFORGE_LLM_MODEL = os.getenv("OPENFORGE_LLM_MODEL", "")
OPENFORGE_GPT_MODEL = os.getenv("OPENFORGE_GPT_MODEL", "openai/gpt-4.1")
OPENFORGE_CLAUDE_MODEL = os.getenv("OPENFORGE_CLAUDE_MODEL", "claude-sonnet-4-20250514")
OPENFORGE_GROQ_MODEL = os.getenv("OPENFORGE_GROQ_MODEL", "llama-3.3-70b-versatile")
OPENFORGE_SEA_LION_MODEL = os.getenv("OPENFORGE_SEA_LION_MODEL", "aisingapore/Llama-3.1-SEA-LION-8B-R")

# PDK model set: bundled (fast/dev) | sky130 (silicon-plausible)
MODEL_SET = os.getenv("OPENFORGE_MODEL_SET", "bundled").lower()
PDK_DIR = DATA_DIR / "pdk" / "sky130"

NGSPICE_TIMEOUT = int(os.getenv("NGSPICE_TIMEOUT", "30"))
SIM_WORKERS = int(os.getenv("SIM_WORKERS", "4"))
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "openanalog")

# Fallback: spice-datasets cloned at repo root
SPICE_DATASETS_FALLBACK = ROOT / "spice-datasets"


def is_wsl() -> bool:
    if platform.system().lower() != "linux":
        return False
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8").lower()
    except Exception:
        return False


def resolve_ngspice_cmd() -> list[str] | None:
    """
    Resolve an ngspice executable appropriate for the current environment.

    Master-plan rules:
    - WSL: /usr/bin/ngspice
    - Windows native: C:/msys64/mingw64/bin/ngspice.exe (if installed)
    - Linux: `which ngspice`
    """
    sys = platform.system().lower()
    if is_wsl():
        p = Path("/usr/bin/ngspice")
        return [str(p)] if p.exists() else None
    if sys == "windows":
        p = Path("C:/msys64/mingw64/bin/ngspice.exe")
        return [str(p)] if p.exists() else None
    # linux / darwin
    for p in (Path("/usr/bin/ngspice"), Path("/bin/ngspice")):
        if p.exists():
            return [str(p)]
    # fall back to PATH resolution
    return ["ngspice"]


def ensure_dirs() -> None:
    for p in (
        PAPERS_INBOX,
        PAPERS_PROCESSED,
        SEEDS_DIR,
        TRAINING_DIR,
        KG_DIR,
        DATA_DIR,
    ):
        p.mkdir(parents=True, exist_ok=True)
