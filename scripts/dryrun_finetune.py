#!/usr/bin/env python3
"""CHECK 3: GPU/CPU dry-run — 10 training steps using finetune_lora.py logic."""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import torch
from datasets import load_dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

DATA = Path("data/training/finetune.jsonl")
if not DATA.exists():
    print(f"MISSING {DATA}")
    sys.exit(1)

FULL_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
SMOKE_MODEL = "Qwen/Qwen2.5-Coder-0.5B-Instruct"  # same chat template, fits 6GB GPUs
MIN_VRAM_GB_FOR_7B = 10.0
MAX_SEQ_LEN = 2048
OUT = Path(tempfile.mkdtemp(prefix="openforge_dryrun_"))

use_cuda = torch.cuda.is_available()
vram_gb = 0.0
if use_cuda:
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
    print(f"GPU: {torch.cuda.get_device_name(0)} ({vram_gb:.1f} GB)")

if use_cuda and vram_gb >= MIN_VRAM_GB_FOR_7B:
    model_id = FULL_MODEL
    use_4bit = True
    print(f"Dry-run: {model_id} 4-bit on CUDA (matches Lambda config)")
elif use_cuda:
    model_id = SMOKE_MODEL
    use_4bit = False
    print(
        f"Dry-run: {model_id} on CUDA "
        f"(VRAM {vram_gb:.1f}GB < {MIN_VRAM_GB_FOR_7B}GB — pipeline check only; "
        f"use Lambda A100 for {FULL_MODEL})"
    )
else:
    model_id = SMOKE_MODEL
    use_4bit = False
    print(f"Dry-run: {model_id} on CPU (no CUDA)")

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

raw = load_dataset("json", data_files=str(DATA), split="train")
subset = raw.select(range(min(16, len(raw))))

args = SFTConfig(
    output_dir=str(OUT),
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
)

trainer = SFTTrainer(
    model=model,
    args=args,
    train_dataset=subset,
    processing_class=tok,
)

print("Starting 10-step dry-run...")
trainer.train()
print(f"\nCHECK 3 PASSED — dry-run completed ({model_id}), temp dir {OUT}")
shutil.rmtree(OUT, ignore_errors=True)
