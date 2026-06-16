#!/usr/bin/env python3
"""CHECK 4: Verify LoRA target module names for Qwen2.5-Coder-7B (no weight download)."""
from __future__ import annotations

import sys

import torch
from transformers import AutoConfig, Qwen2ForCausalLM

MODEL_ID = "Qwen/Qwen2.5-Coder-7B-Instruct"
EXPECTED = {
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
}

print("=== LINEAR LAYERS (LoRA targets) ===")
config = AutoConfig.from_pretrained(MODEL_ID, trust_remote_code=True)
try:
    from transformers import Qwen2ForCausalLM
except ImportError:
    from transformers.models.qwen2.modeling_qwen2 import Qwen2ForCausalLM

with torch.device("meta"):
    model = Qwen2ForCausalLM(config)

seen: set[str] = set()
for name, module in model.named_modules():
    if "Linear" in type(module).__name__:
        leaf = name.split(".")[-1]
        if leaf not in seen:
            seen.add(leaf)
            print(f"  {leaf}")

missing = EXPECTED - seen
if missing:
    print(f"\nSTOP: expected modules missing: {missing}")
    sys.exit(1)
print(f"\nAll expected LoRA targets present: {sorted(EXPECTED)}")
print("CHECK 4 PASSED")
