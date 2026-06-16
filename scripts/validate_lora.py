#!/usr/bin/env python3
"""Post-training validation — run on Lambda after finetune_lora.py."""
from __future__ import annotations

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = "Qwen/Qwen2.5-Coder-7B-Instruct"
LORA = "openforge-lora-v1"

SYSTEM = (
    "You are an analog IC design assistant. Given a specification, "
    "output a valid ngspice SPICE netlist for a circuit that meets the spec. "
    "Output only the netlist, no explanation."
)

TEST_PROMPT = """Design a comparator circuit with the following specifications:
  iq_uA: 0.45
  vos_mV: 0.28
  tp_us: 0.55
Output a complete ngspice SPICE netlist."""


def main() -> None:
    tokenizer = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(base_model, LORA)
    model.eval()

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": TEST_PROMPT},
    ]

    input_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(input_text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=512,
            temperature=0.1,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated = tokenizer.decode(
        outputs[0][inputs.input_ids.shape[1] :], skip_special_tokens=True
    )
    print("=== GENERATED NETLIST ===")
    print(generated)
    print("=== END ===")

    checks = [
        (
            ".subckt" in generated.lower()
            or "m0" in generated.lower()
            or "mn" in generated.lower(),
            "Contains MOSFET",
        ),
        (".end" in generated.lower(), "Has .end statement"),
        (len(generated) > 100, "Non-trivial length"),
        ("vdd" in generated.lower() or "VDD" in generated, "Has supply node"),
    ]
    passed = sum(1 for ok, _ in checks if ok)
    for ok, name in checks:
        print(f"  {'OK' if ok else 'FAIL'} {name}")
    if passed < 3:
        raise SystemExit(f"Validation failed: {passed}/4 checks passed (need >= 3)")


if __name__ == "__main__":
    main()
