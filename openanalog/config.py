from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
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
# WSL distro hosting ngspice (default Ubuntu; not docker-desktop).
OPENFORGE_WSL_DISTRO = os.getenv("OPENFORGE_WSL_DISTRO", "Ubuntu").strip() or "Ubuntu"
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


def _uses_wsl(cmd: list[str]) -> bool:
    if not cmd:
        return False
    return Path(cmd[0]).stem.lower() in ("wsl", "wsl.exe")


def win_path_to_wsl(path: Path) -> str:
    """Convert a Windows absolute path to the Ubuntu WSL mount path (/mnt/c/...)."""
    s = str(path).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        drive = s[0].lower()
        rest = s[2:]
        if not rest.startswith("/"):
            rest = "/" + rest
        return f"/mnt/{drive}{rest}"
    return str(path.resolve()).replace("\\", "/")


def ngspice_path_arg(sp_path: Path, cmd: list[str]) -> str:
    """Convert a Windows path when invoking ngspice through WSL."""
    if _uses_wsl(cmd):
        return win_path_to_wsl(sp_path)
    return str(sp_path)


def _wsl_has_ngspice(distro: str) -> bool:
    try:
        r = subprocess.run(
            ["wsl", "-d", distro, "-e", "test", "-x", "/usr/bin/ngspice"],
            capture_output=True,
            timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


def resolve_ngspice_cmd() -> list[str] | None:
    """
    Resolve an ngspice executable appropriate for the current environment.

    Master-plan rules:
    - WSL: /usr/bin/ngspice
    - Windows native: C:/msys64/mingw64/bin/ngspice.exe (if installed)
    - Windows + WSL: wsl -d Ubuntu -e /usr/bin/ngspice when MSYS ngspice is absent
    - Linux: `which ngspice`
    - Override: NGSPICE_CMD env (space-separated argv prefix)
    """
    override = os.getenv("NGSPICE_CMD", "").strip()
    if override:
        return override.split()
    sys = platform.system().lower()
    if is_wsl():
        p = Path("/usr/bin/ngspice")
        return [str(p)] if p.exists() else None
    if sys == "windows":
        p = Path("C:/msys64/mingw64/bin/ngspice.exe")
        if p.exists():
            return [str(p)]
        distro = OPENFORGE_WSL_DISTRO
        if _wsl_has_ngspice(distro):
            return ["wsl", "-d", distro, "-e", "/usr/bin/ngspice"]
        return None
    # linux / darwin — only return a path that actually exists
    for p in (Path("/usr/bin/ngspice"), Path("/bin/ngspice")):
        if p.exists():
            return [str(p)]
    found = shutil.which("ngspice")
    return [found] if found else None


def probe_ngspice(*, timeout: int = 10) -> tuple[bool, str]:
    """Run a trivial ngspice deck; True only when batch mode completes cleanly."""
    cmd = resolve_ngspice_cmd()
    if not cmd:
        return False, "ngspice not found"
    deck = "* openforge health probe\nV1 a 0 1\nR1 a 0 1k\n.op\n.end\n"
    with tempfile.NamedTemporaryFile("w", suffix=".sp", delete=False, prefix="ofprobe_") as tmp:
        tmp.write(deck)
        path = Path(tmp.name)
    try:
        r = subprocess.run(
            [*cmd, "-b", ngspice_path_arg(path, cmd)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        text = (r.stdout or "") + (r.stderr or "")
        fatal = any(
            kw in text.lower()
            for kw in ("fatal", "error on line", "simulation interrupted due to error")
        )
        if r.returncode == 0 and not fatal:
            return True, "ok"
        return False, (text[:300] or f"exit {r.returncode}").strip()
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except FileNotFoundError:
        return False, "ngspice executable missing"
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


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
