#!/usr/bin/env python3
"""Pre-download HF model with env.local token, verbose per-file logging."""
from __future__ import annotations

import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.train_env import load_env_local  # noqa: E402

load_env_local()

# XET/CAS can hang on Windows; classic HTTP is more reliable
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")

MODEL = sys.argv[1] if len(sys.argv) > 1 else "Qwen/Qwen2.5-Coder-7B-Instruct"
START_AT = int(sys.argv[2]) if len(sys.argv) > 2 else 1  # resume from file N
LOG_DIR = _ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"download_{MODEL.replace('/', '_')}.log"


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def cache_root() -> Path:
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        return Path(hf_home) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def cleanup_stale(cache: Path, repo_slug: str) -> None:
    lock_dir = cache / ".locks" / f"models--{repo_slug}"
    if lock_dir.exists():
        shutil.rmtree(lock_dir, ignore_errors=True)
        log(f"cleared locks: {lock_dir.name}")

    blobs = cache / f"models--{repo_slug}" / "blobs"
    if not blobs.exists():
        return
    removed = 0
    skipped = 0
    for inc in blobs.glob("*.incomplete"):
        try:
            inc.unlink()
            removed += 1
        except OSError:
            skipped += 1
    if removed:
        log(f"removed {removed} stale .incomplete partials")
    if skipped:
        log(f"skipped {skipped} locked .incomplete (another download active)")


def fmt_size(n: int | float | None) -> str:
    if not n:
        return "?"
    n = float(n)
    if n >= 1e9:
        return f"{n / 1e9:.2f} GB"
    if n >= 1e6:
        return f"{n / 1e6:.1f} MB"
    return f"{n / 1e3:.0f} KB"


def main() -> None:
    from huggingface_hub import HfApi, hf_hub_download

    token = os.environ.get("HF_TOKEN", "").strip()
    repo_slug = MODEL.replace("/", "--")
    cache = cache_root()

    log(f"=== download start: {MODEL} ===")
    log(f"HF_TOKEN: {'set' if token else 'MISSING'}")
    log(f"log file: {LOG_FILE}")
    log(f"HF_HUB_DISABLE_XET={os.environ.get('HF_HUB_DISABLE_XET', '')}")

    cleanup_stale(cache, repo_slug)

    api = HfApi(token=token or None)
    siblings = api.model_info(MODEL).siblings
    files = [s.rfilename for s in siblings]
    sizes = {s.rfilename: s.size for s in siblings}
    total_bytes = sum(sizes.get(f) or 0 for f in files)
    log(f"files: {len(files)}, total ~{fmt_size(total_bytes)}")

    done = 0
    t_all = time.time()
    for i, fname in enumerate(files, 1):
        if i < START_AT:
            log(f"[{i}/{len(files)}] skip (cached): {fname}")
            done += 1
            continue
        log(f"[{i}/{len(files)}] {fname} ({fmt_size(sizes.get(fname))}) ...")
        t0 = time.time()
        last_err = None
        for attempt in range(1, 11):
            try:
                # Fresh client each attempt — fixes "client has been closed" after DNS drops
                try:
                    from huggingface_hub.utils import hf_raise_for_status  # noqa: F401
                    import huggingface_hub.constants as _hc
                    _hc.HF_HUB_HTTP_TIMEOUT = 60
                except Exception:
                    pass
                try:
                    from huggingface_hub.utils._http import reset_sessions
                    reset_sessions()
                except Exception:
                    pass

                path = hf_hub_download(
                    MODEL,
                    fname,
                    token=token or None,
                    etag_timeout=60,
                    resume_download=True,
                )
                elapsed = time.time() - t0
                done += 1
                log(f"[{i}/{len(files)}] OK in {elapsed:.0f}s -> {path}")
                last_err = None
                break
            except Exception as e:
                last_err = e
                wait = min(120, 10 * attempt)
                log(f"[{i}/{len(files)}] attempt {attempt}/10 failed: {e} — retry in {wait}s")
                time.sleep(wait)
        if last_err is not None:
            log(f"[{i}/{len(files)}] FAILED after retries: {last_err}")
            sys.exit(1)

    log(f"=== done in {(time.time()-t_all)/60:.1f} min ({done}/{len(files)} files) ===")
    log(f"View log: {LOG_FILE}")


if __name__ == "__main__":
    main()
