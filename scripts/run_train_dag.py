#!/usr/bin/env python3
"""
48h training DAG — orchestrates preflight → dryrun → finetune → validate.

Thermal/OOM guards via nvidia-smi. Resumes from data/dag_state.json.

Usage (from repo root):
  python scripts/run_train_dag.py --hours 48
  python scripts/run_train_dag.py --max-steps 50 --skip-forge
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = _ROOT / "data" / "dag_state.json"
PYTHON = sys.executable

STAGES = [
    "check_train_env",
    "preflight_corpus",
    "build_training_jsonl",
    "validate_finetune_jsonl",
    "check_chat_format",
    "check_netlist_parse",
    "check_lora_targets",
    "dryrun_finetune",
    "finetune_lora",
    "validate_lora",
]


def _load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"completed": [], "started_at": None, "last_error": None}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def gpu_stats() -> dict | None:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=temperature.gpu,memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=10,
        ).strip()
        temp, mem_used, mem_total, util = [x.strip() for x in out.split(",")]
        return {
            "temp_c": float(temp),
            "mem_used_mb": float(mem_used),
            "mem_total_mb": float(mem_total),
            "util_pct": float(util),
            "mem_free_gb": (float(mem_total) - float(mem_used)) / 1024,
        }
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return None


def wait_for_gpu(
    temp_max: float,
    vram_min_gb: float,
    cooldown_sec: int,
    deadline: float | None,
) -> bool:
    """Return False if deadline exceeded while waiting."""
    while True:
        if deadline and time.time() > deadline:
            return False
        stats = gpu_stats()
        if stats is None:
            return True
        hot = stats["temp_c"] >= temp_max
        low_vram = stats["mem_free_gb"] < vram_min_gb
        if not hot and not low_vram:
            return True
        reason = []
        if hot:
            reason.append(f"temp={stats['temp_c']:.0f}C>={temp_max}")
        if low_vram:
            reason.append(f"free_vram={stats['mem_free_gb']:.1f}GB<{vram_min_gb}")
        print(f"[dag] GPU guard: {', '.join(reason)} — sleep {cooldown_sec}s", flush=True)
        time.sleep(cooldown_sec)


def run_script(name: str, extra_args: list[str] | None = None) -> int:
    script = _ROOT / "scripts" / f"{name}.py"
    if not script.exists():
        # finetune_lora has no .py suffix issue - all are .py
        script = _ROOT / "scripts" / name
        if script.suffix != ".py":
            script = script.with_suffix(".py")
    cmd = [PYTHON, str(script)] + (extra_args or [])
    print(f"\n[dag] === {name} ===", flush=True)
    print(f"[dag] {' '.join(cmd)}", flush=True)
    env = os.environ.copy()
    # train_env auto-sets BNB_CUDA_VERSION when needed
    proc = subprocess.run(cmd, cwd=str(_ROOT), env=env)
    return proc.returncode


def main() -> None:
    p = argparse.ArgumentParser(description="OpenForge 48h training DAG")
    p.add_argument("--hours", type=float, default=48.0, help="Max runtime (0 = no limit)")
    p.add_argument("--max-steps", type=int, default=None, help="Finetune max steps (smoke)")
    p.add_argument("--skip-forge", action="store_true", help="Skip optional forge refresh")
    p.add_argument("--skip-train", action="store_true", help="Preflight only")
    p.add_argument("--mlflow", action="store_true", help="Enable MLflow in finetune")
    p.add_argument("--thermal-max", type=float, default=82.0, help="Max GPU temp C")
    p.add_argument("--vram-min-gb", type=float, default=2.0, help="Min free VRAM before train")
    p.add_argument("--cooldown", type=int, default=300, help="Seconds to wait when hot/low VRAM")
    p.add_argument("--forge-n", type=int, default=0, help="Run forge --n N before training (grow winners)")
    p.add_argument("--reset", action="store_true", help="Clear dag_state and restart")
    args = p.parse_args()

    state = _load_state()
    if args.reset:
        state = {"completed": [], "started_at": None, "last_error": None}
        _save_state(state)

    if not state.get("started_at"):
        state["started_at"] = datetime.now(timezone.utc).isoformat()
        _save_state(state)

    deadline = None
    if args.hours > 0:
        started = datetime.fromisoformat(state["started_at"])
        deadline = started.timestamp() + args.hours * 3600

    completed = set(state.get("completed", []))

    if args.forge_n > 0 and not args.skip_forge:
        print(f"\n[dag] === forge (WSL) --n {args.forge_n} ===", flush=True)
        forge_cmd = [
            "wsl", "-e", "bash", "-lc",
            f"cd /mnt/c/Users/user/OpenForge/OpenForge && "
            f"source .venv_wsl/bin/activate && "
            f"python -m openanalog forge --n {args.forge_n} --workers 4",
        ]
        rc = subprocess.run(forge_cmd, cwd=str(_ROOT)).returncode
        if rc != 0:
            print(f"[dag] WARN: forge exited {rc} — continuing", flush=True)
        run_script("build_training_jsonl")
        run_script("harness_gate_report")

    pre_train = [
        "check_train_env",
        "preflight_corpus",
        "build_training_jsonl",
        "validate_finetune_jsonl",
        "check_chat_format",
        "check_netlist_parse",
        "check_lora_targets",
        "dryrun_finetune",
    ]

    for stage in pre_train:
        if stage in completed:
            print(f"[dag] skip (done): {stage}", flush=True)
            continue
        if not wait_for_gpu(args.thermal_max, args.vram_min_gb, args.cooldown, deadline):
            print("[dag] deadline exceeded during GPU wait", flush=True)
            sys.exit(2)
        rc = run_script(stage)
        if rc != 0:
            state["last_error"] = f"{stage} exit {rc}"
            _save_state(state)
            sys.exit(rc)
        completed.add(stage)
        state["completed"] = sorted(completed)
        _save_state(state)

    if args.skip_train:
        print("\n[dag] Preflight complete (--skip-train)", flush=True)
        return

    if "finetune_lora" not in completed:
        if not wait_for_gpu(args.thermal_max, args.vram_min_gb, args.cooldown, deadline):
            sys.exit(2)
        finetune_args = []
        if args.max_steps:
            finetune_args += ["--max-steps", str(args.max_steps)]
        if args.mlflow:
            finetune_args += ["--mlflow"]
        rc = run_script("finetune_lora", finetune_args)
        if rc != 0:
            state["last_error"] = f"finetune_lora exit {rc}"
            _save_state(state)
            sys.exit(rc)
        completed.add("finetune_lora")
        state["completed"] = sorted(completed)
        _save_state(state)

    if "validate_lora" not in completed:
        rc = run_script("validate_lora")
        if rc != 0:
            state["last_error"] = f"validate_lora exit {rc}"
            _save_state(state)
            sys.exit(rc)
        completed.add("validate_lora")
        state["completed"] = sorted(completed)
        _save_state(state)

    print("\n[dag] ALL STAGES COMPLETE", flush=True)
    stats = gpu_stats()
    if stats:
        print(f"[dag] GPU: temp={stats['temp_c']:.0f}C free_vram={stats['mem_free_gb']:.1f}GB", flush=True)


if __name__ == "__main__":
    main()
