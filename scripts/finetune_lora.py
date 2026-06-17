"""
OpenForge LoRA finetuning — hardened for Lambda A100 80GB / RTX 4070 12GB
Qwen2.5-Coder-7B-Instruct on fitness=1 SPICE netlist corpus

Requires trl>=1.6 (uses SFTConfig + assistant_only_loss).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.train_env import (  # noqa: E402
    FULL_MODEL,
    SMOKE_MODEL,
    filter_sft_config_kwargs,
    finetune_data_path,
    pick_training_model,
    print_train_env,
    require_train_deps,
)

require_train_deps()

import torch  # noqa: E402
from datasets import load_dataset  # noqa: E402
from peft import LoraConfig, TaskType, get_peft_model  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig  # noqa: E402
from trl import SFTConfig, SFTTrainer  # noqa: E402

OUTPUT_DIR = "openforge-lora-v1"
MAX_SEQ_LEN = 2048


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="OpenForge LoRA finetune")
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--max-steps", type=int, default=None, help="Override epochs for smoke tests")
    p.add_argument("--batch-size", type=int, default=None, help="Auto from VRAM if omitted")
    p.add_argument("--output-dir", default=OUTPUT_DIR)
    p.add_argument("--smoke", action="store_true", help="Force 0.5B (pipeline test)")
    p.add_argument("--full", action="store_true", help="Force 7B QLoRA (default when cached)")
    p.add_argument("--model", default=None, help=f"HF model id (default: {FULL_MODEL})")
    p.add_argument("--mlflow", action="store_true", help="Log to MLflow (needs MLFLOW_TRACKING_URI)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    env = print_train_env()

    data_path = finetune_data_path()
    if not data_path.exists():
        print(f"MISSING {data_path} — run scripts/build_training_jsonl.py", flush=True)
        sys.exit(1)

    model_id, use_4bit, reason = pick_training_model(
        env,
        force_smoke=args.smoke,
        force_full=args.full,
        model_override=args.model,
        require_full=not args.smoke,
    )
    print(f"[finetune] Model: {model_id} ({reason})", flush=True)

    batch_size = args.batch_size or env.get("batch_size", 1)
    report_to = "mlflow" if args.mlflow else "none"
    if args.mlflow:
        try:
            import mlflow  # noqa: F401
        except ImportError:
            print("[finetune] mlflow not installed — pip install mlflow", flush=True)
            sys.exit(1)

    print(f"[finetune] Loading {model_id}...", flush=True)
    tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    tok.pad_token = tok.eos_token
    tok.padding_side = "right"

    load_kwargs: dict = {"trust_remote_code": True}
    if use_4bit:
        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        load_kwargs["device_map"] = "auto"
    elif env.get("cuda"):
        load_kwargs["torch_dtype"] = torch.bfloat16
        load_kwargs["device_map"] = "auto"
    else:
        load_kwargs["torch_dtype"] = torch.float32
        load_kwargs["device_map"] = "cpu"

    model = AutoModelForCausalLM.from_pretrained(model_id, **load_kwargs)
    model.config.use_cache = False
    model.enable_input_require_grads()

    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,
        lora_alpha=32,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        lora_dropout=0.05,
        bias="none",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    dataset = load_dataset("json", data_files=str(data_path), split="train")

    grad_accum = 8
    steps_per_epoch = max(1, len(dataset) // (batch_size * grad_accum))
    if args.max_steps is not None:
        total_steps = args.max_steps
    else:
        total_steps = steps_per_epoch * args.epochs
    warmup_steps = max(1, int(total_steps * 0.05))

    train_kwargs: dict = {
        "output_dir": args.output_dir,
        "per_device_train_batch_size": batch_size,
        "gradient_accumulation_steps": grad_accum,
        "gradient_checkpointing": True,
        "learning_rate": 2e-4,
        "lr_scheduler_type": "cosine",
        "warmup_steps": warmup_steps,
        "bf16": bool(env.get("cuda")),
        "logging_steps": 5,
        "save_strategy": "epoch",
        "save_total_limit": 2,
        "report_to": report_to,
        "dataloader_num_workers": 0 if os.name == "nt" else 2,
        "max_length": MAX_SEQ_LEN,
        "assistant_only_loss": True,
    }
    if args.max_steps is not None:
        train_kwargs["max_steps"] = args.max_steps
    else:
        train_kwargs["num_train_epochs"] = args.epochs

    sft_args = SFTConfig(**filter_sft_config_kwargs(train_kwargs))

    trainer = SFTTrainer(
        model=model,
        args=sft_args,
        train_dataset=dataset,
        processing_class=tok,
    )

    print(
        f"Training on {len(dataset)} examples, max_length={MAX_SEQ_LEN}, "
        f"batch_size={batch_size}",
        flush=True,
    )
    if model_id == FULL_MODEL:
        print("Watch: loss should drop from ~3.0-3.5 to ~0.8-1.2 by epoch 3", flush=True)
        print("If loss is still > 2.5 after 50 steps: STOP - data format issue\n", flush=True)

    print(f"[finetune] Starting train (~{total_steps} steps, warmup={warmup_steps})...", flush=True)
    trainer.train()
    trainer.save_model(args.output_dir)
    tok.save_pretrained(args.output_dir)
    print(f"\nDone. Adapter saved to {args.output_dir}/", flush=True)
    print("Next: python scripts/validate_lora.py", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[finetune] interrupted", flush=True)
        sys.exit(130)
    except Exception as exc:
        print(f"\n[finetune] FAILED: {exc}", flush=True)
        sys.exit(1)
