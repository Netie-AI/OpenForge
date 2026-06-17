#!/usr/bin/env python3
"""
Model benchmark harness — compare base vs LoRA on fixed SPICE prompts.

Metrics: ngspice parse rate, forge_eval fitness=1 rate, latency.
Inference backends: transformers (default), llama.cpp (future), vLLM (WSL).

Usage:
  python scripts/benchmark_models.py --models Qwen/Qwen2.5-Coder-7B-Instruct
  python scripts/benchmark_models.py --lora openforge-lora-v1 --samples 20
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.train_env import ensure_bitsandbytes, require_train_deps  # noqa: E402

require_train_deps()
ensure_bitsandbytes()

import torch  # noqa: E402
from peft import PeftModel  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig  # noqa: E402

from openanalog.forge.forge_eval import evaluate_forge_fitness  # noqa: E402
from openanalog.sim.ngspice import check_syntax  # noqa: E402

FINETUNE = ROOT / "data" / "training" / "finetune.jsonl"
DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
SYSTEM = (
    "You are an analog IC design assistant. Given a specification, "
    "output a valid ngspice SPICE netlist for a circuit that meets the spec. "
    "Output only the netlist, no explanation."
)


def load_prompts(n: int) -> list[dict]:
    lines = [
        json.loads(l)
        for l in FINETUNE.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    random.seed(42)
    return random.sample(lines, min(n, len(lines)))


def load_model(model_id: str, lora_path: str | None):
    tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    base = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb,
        device_map="auto",
        trust_remote_code=True,
    )
    if lora_path and Path(lora_path).exists():
        model = PeftModel.from_pretrained(base, lora_path)
        label = f"{model_id}+LoRA({lora_path})"
    else:
        model = base
        label = model_id
    model.eval()
    return tok, model, label


def generate(tok, model, messages: list[dict], max_new_tokens: int = 512) -> tuple[str, float]:
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tok(text, return_tensors="pt").to(model.device)
    t0 = time.perf_counter()
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,
            do_sample=True,
            pad_token_id=tok.eos_token_id,
        )
    elapsed = time.perf_counter() - t0
    gen = tok.decode(out[0][inputs.input_ids.shape[1] :], skip_special_tokens=True)
    return gen, elapsed


def score_netlist(netlist: str, user_prompt: str) -> dict:
    topo = "opamp"
    for t in ("comparator", "switch", "ldo", "charge_pump", "opamp"):
        if t in user_prompt.lower():
            topo = t
            break
    parse_ok = check_syntax(netlist) if netlist.strip() else False
    ev = evaluate_forge_fitness(netlist, topo) if parse_ok else {"score": 0}
    return {
        "parse_ok": parse_ok,
        "fitness": ev.get("score", 0),
        "topology": topo,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Benchmark LLM netlist generation")
    p.add_argument("--models", nargs="+", default=[DEFAULT_MODEL])
    p.add_argument("--lora", default=None, help="LoRA adapter path")
    p.add_argument("--samples", type=int, default=10)
    p.add_argument("--max-new-tokens", type=int, default=512)
    args = p.parse_args()

    prompts = load_prompts(args.samples)
    print(f"Benchmark: {len(prompts)} prompts from finetune.jsonl\n")

    for model_id in args.models:
        print(f"Loading {model_id}...", flush=True)
        tok, model, label = load_model(model_id, args.lora)
        parse_ok = fitness1 = 0
        total_s = 0.0

        for i, ex in enumerate(prompts):
            user = ex["messages"][1]["content"]
            messages = [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ]
            netlist, elapsed = generate(tok, model, messages, args.max_new_tokens)
            sc = score_netlist(netlist, user)
            parse_ok += int(sc["parse_ok"])
            fitness1 += int(sc["fitness"] == 1)
            total_s += elapsed
            print(
                f"  [{i+1}/{len(prompts)}] parse={sc['parse_ok']} "
                f"fitness={sc['fitness']} {elapsed:.1f}s",
                flush=True,
            )

        n = len(prompts)
        print(f"\n=== {label} ===")
        print(f"  Parse rate:    {100*parse_ok/n:.1f}% ({parse_ok}/{n})")
        print(f"  Fitness=1:     {100*fitness1/n:.1f}% ({fitness1}/{n})")
        print(f"  Avg latency:   {total_s/n:.1f}s/prompt")
        print(f"  Target gate:   >50% fitness=1 for production LoRA\n")

        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
