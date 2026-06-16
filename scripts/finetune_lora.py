"""
OpenForge LoRA finetuning — hardened for Lambda A100 80GB
Qwen2.5-Coder-7B-Instruct on fitness=1 SPICE netlist corpus

Requires trl>=1.6 (uses SFTConfig + assistant_only_loss).
"""
from __future__ import annotations

import torch
from datasets import load_dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

MODEL_ID = "Qwen/Qwen2.5-Coder-7B-Instruct"
DATA_PATH = "finetune.jsonl"
OUTPUT_DIR = "openforge-lora-v1"
MAX_SEQ_LEN = 2048


def main() -> None:
    tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    tok.pad_token = tok.eos_token
    tok.padding_side = "right"

    bnb_cfg = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_cfg,
        device_map="auto",
        trust_remote_code=True,
    )
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

    dataset = load_dataset("json", data_files=DATA_PATH, split="train")

    args = SFTConfig(
        output_dir=OUTPUT_DIR,
        num_train_epochs=3,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8,
        gradient_checkpointing=True,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        bf16=True,
        logging_steps=5,
        save_strategy="epoch",
        save_total_limit=2,
        report_to="none",
        dataloader_num_workers=2,
        group_by_length=True,
        max_length=MAX_SEQ_LEN,
        assistant_only_loss=True,
    )

    trainer = SFTTrainer(
        model=model,
        args=args,
        train_dataset=dataset,
        processing_class=tok,
    )

    print(f"Training on {len(dataset)} examples, max_length={MAX_SEQ_LEN}")
    print("Watch: loss should drop from ~3.0-3.5 → ~0.8-1.2 by epoch 3")
    print("If loss is still > 2.5 after 50 steps: STOP — data format issue\n")

    trainer.train()
    trainer.save_model(OUTPUT_DIR)
    tok.save_pretrained(OUTPUT_DIR)
    print(f"\nDone. Adapter saved to {OUTPUT_DIR}/")
    print("Next: python validate_lora.py")


if __name__ == "__main__":
    main()
