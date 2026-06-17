"""Shared training environment helpers for finetune scripts."""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FINETUNE = ROOT / "data" / "training" / "finetune.jsonl"
MIN_VRAM_GB_7B_4BIT = 10.0
LAMBDA_VRAM_GB = 24.0
FULL_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
SMOKE_MODEL = "Qwen/Qwen2.5-Coder-0.5B-Instruct"


def load_env_local() -> None:
    """Load HF_TOKEN and related vars from env.local / .env (no overwrite if already set)."""
    for name in ("env.local", ".env"):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and val and key not in os.environ:
                os.environ[key] = val
    # huggingface_hub reads HF_TOKEN
    token = os.environ.get("HF_TOKEN", "").strip()
    if token:
        os.environ["HF_TOKEN"] = token
        os.environ.setdefault("HUGGING_FACE_HUB_TOKEN", token)


# Load before any HF hub calls
load_env_local()


def configure_stdio_utf8() -> None:
    """Windows consoles default to cp1252; avoid crashes on Unicode in logs."""
    if os.name != "nt":
        return
    os.environ.setdefault("PYTHONUTF8", "1")
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


def ensure_repo_root() -> None:
    """Run training from repo root so paths and imports stay consistent."""
    os.chdir(ROOT)


def finetune_data_path() -> Path:
    override = os.environ.get("FINETUNE_JSONL", "").strip()
    if override:
        return Path(override)
    return DEFAULT_FINETUNE


def hf_hub_cache() -> Path:
    hf_home = os.environ.get("HF_HOME", "").strip()
    if hf_home:
        return Path(hf_home) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def model_cache_dir(model_id: str) -> Path:
    return hf_hub_cache() / f"models--{model_id.replace('/', '--')}"


def model_download_status(model_id: str) -> dict:
    """Local HF cache status without network."""
    cache = model_cache_dir(model_id)
    blobs = cache / "blobs"
    incomplete = list(blobs.glob("*.incomplete")) if blobs.exists() else []
    snapshots = cache / "snapshots"
    shard_files: list[str] = []
    ready = False
    if snapshots.exists():
        for snap in sorted(snapshots.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not snap.is_dir():
                continue
            shards = sorted(p.name for p in snap.glob("*.safetensors"))
            if shards:
                shard_files = shards
                ready = (snap / "config.json").exists() and not incomplete
                break
    total_bytes = 0
    if blobs.exists():
        total_bytes = sum(
            f.stat().st_size for f in blobs.iterdir() if f.is_file() and ".incomplete" not in f.name
        )
    return {
        "ready": ready,
        "shards": len(shard_files),
        "shard_files": shard_files,
        "incomplete": len(incomplete),
        "cache_gb": total_bytes / 1e9,
        "cache": cache,
    }


def force_smoke_enabled() -> bool:
    return os.environ.get("OPENFORGE_FORCE_SMOKE", "").strip().lower() in ("1", "true", "yes")


def pick_training_model(
    env: dict,
    *,
    force_smoke: bool = False,
    force_full: bool = False,
    model_override: str | None = None,
    require_full: bool = False,
) -> tuple[str, bool, str]:
    """Return (model_id, use_4bit, reason)."""
    if force_smoke:
        return SMOKE_MODEL, False, "0.5B (--smoke)"

    if force_smoke_enabled() and not force_full:
        status = model_download_status(FULL_MODEL)
        if status["ready"]:
            print(
                "[train_env] WARN: OPENFORGE_FORCE_SMOKE is set but 7B is cached — "
                "using 7B. Clear with: Remove-Item Env:OPENFORGE_FORCE_SMOKE",
                flush=True,
            )

    if model_override:
        mid = model_override.strip()
        if mid in (SMOKE_MODEL, "0.5b", "smoke"):
            return SMOKE_MODEL, False, f"--model {mid}"
        st = model_download_status(mid)
        if not st["ready"]:
            print(
                f"[train_env] Model not cached: {mid} ({st['cache_gb']:.1f} GB, "
                f"{st['incomplete']} partial)",
                flush=True,
            )
            if require_full or force_full:
                sys.exit(1)
        use_4bit = (
            env.get("cuda")
            and env.get("vram_gb", 0.0) >= MIN_VRAM_GB_7B_4BIT
            and mid == FULL_MODEL
        )
        return mid, use_4bit, f"--model {mid}"

    if force_full:
        status = model_download_status(FULL_MODEL)
        if not status["ready"]:
            print(f"[train_env] --full: 7B not cached ({status['cache_gb']:.1f} GB)", flush=True)
            sys.exit(1)
        if env.get("cuda") and env.get("vram_gb", 0.0) >= MIN_VRAM_GB_7B_4BIT:
            return FULL_MODEL, True, "7B 4-bit QLoRA (--full)"
        return FULL_MODEL, False, "7B bf16 (--full, low VRAM — may OOM)"

    status = model_download_status(FULL_MODEL)
    if not status["ready"]:
        msg = (
            f"[train_env] 7B model not fully downloaded "
            f"({status['cache_gb']:.1f} GB cached, {status['incomplete']} partial file(s))\n"
            f"[train_env] Resume: python scripts/download_model.py {FULL_MODEL} 9\n"
            f"[train_env] Status:  .\\scripts\\train.ps1 download-status"
        )
        if require_full:
            print(msg, flush=True)
            sys.exit(1)
        print(msg, flush=True)
        print("[train_env] Falling back to 0.5B (--smoke for explicit 0.5B)", flush=True)
        return SMOKE_MODEL, False, "7B incomplete — smoke fallback"

    if env.get("cuda") and env.get("vram_gb", 0.0) >= MIN_VRAM_GB_7B_4BIT:
        return FULL_MODEL, True, "7B 4-bit QLoRA (default — 15GB cached)"

    if env.get("cuda"):
        return (
            SMOKE_MODEL,
            False,
            f"VRAM {env.get('vram_gb', 0.0):.1f}GB < {MIN_VRAM_GB_7B_4BIT}GB",
        )

    return SMOKE_MODEL, False, "CPU fallback"


def filter_sft_config_kwargs(kwargs: dict) -> dict:
    """Drop SFTConfig keys unsupported by installed TRL (e.g. group_by_length removed in 1.6+)."""
    import inspect

    from trl import SFTConfig

    allowed = set(inspect.signature(SFTConfig.__init__).parameters) - {"self"}
    dropped = [k for k in kwargs if k not in allowed]
    if dropped:
        print(f"[train_env] SFTConfig: dropped unsupported keys: {', '.join(dropped)}", flush=True)
    return {k: v for k, v in kwargs.items() if k in allowed}


def _bnb_package_dir() -> Path | None:
    """Locate bitsandbytes package without importing it (avoids cuda132 DLL crash)."""
    spec = importlib.util.find_spec("bitsandbytes")
    if spec is None or not spec.origin:
        return None
    return Path(spec.origin).resolve().parent


def _available_bnb_cuda_versions(bnb_dir: Path) -> list[int]:
    versions: list[int] = []
    for dll in bnb_dir.glob("libbitsandbytes_cuda*.dll"):
        m = re.search(r"cuda(\d+)", dll.name)
        if m:
            versions.append(int(m.group(1)))
    for so in bnb_dir.glob("libbitsandbytes_cuda*.so"):
        m = re.search(r"cuda(\d+)", so.name)
        if m:
            versions.append(int(m.group(1)))
    return sorted(set(versions))


def _torch_cuda_tag() -> str | None:
    """Read torch CUDA tag without importing torch (torch-before-datasets crashes on Windows)."""
    spec = importlib.util.find_spec("torch")
    if spec is None or not spec.origin:
        return None
    version_py = Path(spec.origin).resolve().parent / "version.py"
    if not version_py.exists():
        return None
    text = version_py.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"cuda:\s*Optional\[str\]\s*=\s*['\"]([^'\"]+)['\"]", text)
    if not m:
        m = re.search(r"cuda\s*=\s*['\"]([^'\"]+)['\"]", text)
    if not m:
        return None
    parts = m.group(1).split(".")
    return f"{parts[0]}{parts[1]}" if len(parts) >= 2 else parts[0]


def ensure_bitsandbytes() -> str | None:
    """Set BNB_CUDA_VERSION before first bitsandbytes import if needed."""
    if os.environ.get("BNB_CUDA_VERSION", "").strip():
        return os.environ["BNB_CUDA_VERSION"].strip()

    bnb_dir = _bnb_package_dir()
    if bnb_dir is None:
        return None

    requested = _torch_cuda_tag()
    if not requested:
        return None

    requested_dll = f"libbitsandbytes_cuda{requested}.dll"
    requested_so = requested_dll.replace(".dll", ".so")
    if (bnb_dir / requested_dll).exists() or (bnb_dir / requested_so).exists():
        return None

    available = _available_bnb_cuda_versions(bnb_dir)
    if not available:
        return None

    fallback = str(available[-1])
    os.environ["BNB_CUDA_VERSION"] = fallback
    print(
        f"[train_env] bitsandbytes: cuda{requested} DLL missing; "
        f"pre-set BNB_CUDA_VERSION={fallback}",
        flush=True,
    )
    return fallback


def print_train_env() -> dict:
    """Print diagnostics; return summary dict."""
    info: dict = {"cuda": False, "vram_gb": 0.0, "gpu": "", "batch_size": 1}

    fb = ensure_bitsandbytes()
    if fb:
        info["bnb_fallback"] = fb

    for pkg in ("datasets", "peft", "trl", "transformers"):
        try:
            mod = __import__(pkg)
            print(f"[train_env] {pkg} {getattr(mod, '__version__', 'ok')}", flush=True)
        except ImportError:
            print(f"[train_env] MISSING {pkg}", flush=True)

    try:
        import bitsandbytes as bnb

        print(f"[train_env] bitsandbytes {bnb.__version__}", flush=True)
    except ImportError:
        print(
            "[train_env] bitsandbytes NOT installed — pip install -e '.[train]'",
            flush=True,
        )

    try:
        import torch
    except ImportError:
        print("[train_env] torch NOT installed", flush=True)
        return info

    info["cuda"] = torch.cuda.is_available()
    print(f"[train_env] torch {torch.__version__}  cuda={info['cuda']}", flush=True)

    if info["cuda"]:
        props = torch.cuda.get_device_properties(0)
        info["gpu"] = torch.cuda.get_device_name(0)
        info["vram_gb"] = props.total_memory / 1e9
        print(f"[train_env] GPU: {info['gpu']} ({info['vram_gb']:.1f} GB)", flush=True)
        if info["vram_gb"] >= LAMBDA_VRAM_GB:
            info["batch_size"] = 2

    hf = "set" if os.environ.get("HF_TOKEN", "").strip() else "missing"
    print(f"[train_env] HF_TOKEN: {hf}", flush=True)

    data = finetune_data_path()
    print(f"[train_env] finetune data: {data}  exists={data.exists()}", flush=True)
    if not data.exists():
        print(
            f"[train_env] MISSING {data} — run scripts/build_training_jsonl.py",
            flush=True,
        )

    return info


def require_train_deps() -> None:
    configure_stdio_utf8()
    ensure_repo_root()
    ensure_bitsandbytes()
    missing = []
    order = ("datasets", "peft", "trl", "transformers", "bitsandbytes", "torch")
    # Import torch AFTER datasets/peft/trl — torch-first + datasets crashes on Windows cu132
    for pkg in order:
        try:
            print(f"[train_env] importing {pkg}...", flush=True)
            __import__(pkg)
            print(f"[train_env] ok {pkg}", flush=True)
        except ImportError:
            missing.append(pkg)
        except Exception as exc:
            print(f"[train_env] FAILED importing {pkg}: {exc}", flush=True)
            sys.exit(1)
    if missing:
        print("[train_env] Install train extras: pip install -e '.[train]'", flush=True)
        print(f"[train_env] Missing: {', '.join(missing)}", flush=True)
        sys.exit(1)
