#!/usr/bin/env python3
"""CHECK 1: Inspect chat template rendering and token length distribution."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from transformers import AutoTokenizer

FINETUNE = Path("data/training/finetune.jsonl")
MODEL_ID = "Qwen/Qwen2.5-Coder-7B-Instruct"
IM_END = "<|" + "im_end" + "|>"

if not FINETUNE.exists():
    print(f"MISSING {FINETUNE}")
    sys.exit(1)

tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)

examples = []
with FINETUNE.open(encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i >= 3:
            break
        examples.append(json.loads(line))

print("=== RENDERED CHAT FORMAT (what the model actually sees) ===\n")
for i, ex in enumerate(examples):
    rendered = tok.apply_chat_template(
        ex["messages"], tokenize=False, add_generation_prompt=False
    )
    print(f"--- Example {i} ---")
    print(rendered[:600])
    print()
    if not rendered.startswith("<|im_start|>system"):
        print("STOP: wrong chat template — expected <|im_start|>system")
        sys.exit(1)
    if IM_END not in rendered:
        print(f"STOP: missing {IM_END} separator")
        sys.exit(1)
    netlist = ex["messages"][2]["content"]
    if ".end" not in netlist.lower():
        print(f"STOP: example {i} netlist missing .end")
        sys.exit(1)

print("=== TOKEN COUNT DISTRIBUTION ===")
lengths = []
with FINETUNE.open(encoding="utf-8") as f:
    for line in f:
        ex = json.loads(line)
        rendered = tok.apply_chat_template(
            ex["messages"], tokenize=False, add_generation_prompt=False
        )
        lengths.append(len(tok.encode(rendered)))

lengths.sort()
n = len(lengths)
over_2048 = sum(1 for ln in lengths if ln > 2048)
over_1536 = sum(1 for ln in lengths if ln > 1536)
print(f"Total examples: {n}")
print(f"Min tokens:     {lengths[0]}")
print(f"Median tokens:  {lengths[n // 2]}")
print(f"90th pct:       {lengths[int(n * 0.9)]}")
print(f"Max tokens:     {lengths[-1]}")
print(f"Over 2048:      {over_2048} examples (WILL BE TRUNCATED)")
print(f"Over 1536:      {over_1536} examples (truncation risk)")

if over_2048 > 50:
    print(f"\nRECOMMEND: set MAX_SEQ_LEN=3072 in finetune_lora.py ({over_2048} > 2048)")
    sys.exit(2)
print("\nCHECK 1 PASSED")
