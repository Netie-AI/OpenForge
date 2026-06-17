#!/usr/bin/env python3
"""CHECK 3: GPU/CPU dry-run — 10 training steps using finetune_lora.py logic."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.train_env import (  # noqa: E402
    FULL_MODEL,
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

MAX_SEQ_LEN = 2048


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="OpenForge dry-run (10 training steps)")
    p.add_argument("--smoke", action="store_true", help="Force 0.5B model")
    p.add_argument("--full", action="store_true", help="Force 7B 4-bit QLoRA")
    p.add_argument("--model", default=None, help=f"HF model id (default: auto, prefer {FULL_MODEL})")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    data = finetune_data_path()
    if not data.exists():
        print(f"MISSING {data} — run from repo root: python scripts/dryrun_finetune.py", flush=True)
        sys.exit(1)

    env = print_train_env()
    model_id, use_4bit, reason = pick_training_model(
        env,
        force_smoke=args.smoke,
        force_full=args.full,
        model_override=args.model,
    )
    print(f"Dry-run: {model_id} ({reason})", flush=True)

    out = Path(tempfile.mkdtemp(prefix="openforge_dryrun_"))
    use_cuda = env["cuda"]

    print(f"[dryrun] Loading {model_id}...", flush=True)
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
    elif use_cuda:
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

    raw = load_dataset("json", data_files=str(data), split="train")
    subset = raw.select(range(min(16, len(raw))))

    sft_args = SFTConfig(
        output_dir=str(out),
        max_steps=10,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=2,
        gradient_checkpointing=True,
        learning_rate=2e-4,
        bf16=use_cuda,
        logging_steps=1,
        save_strategy="no",
        report_to="none",
        max_length=MAX_SEQ_LEN,
        assistant_only_loss=True,
        dataloader_num_workers=0,
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_args,
        train_dataset=subset,
        processing_class=tok,
    )

    print("Starting 10-step dry-run...", flush=True)
    trainer.train()
    print(f"\nCHECK 3 PASSED — dry-run completed ({model_id}), temp dir {out}", flush=True)
    shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[dryrun] interrupted", flush=True)
        sys.exit(130)
    except Exception as exc:
        print(f"\n[dryrun] FAILED: {exc}", flush=True)
        sys.exit(1)
