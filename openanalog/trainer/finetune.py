from __future__ import annotations

from pathlib import Path

from rich.console import Console

from openanalog.trainer.dataset_builder import build_alpaca_dataset

console = Console()

LORA_DEFAULTS = {
    "r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj"],
}
BASE_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"


def run_finetune(
    dataset_path: Path | None = None,
    *,
    epochs: int = 1,
    output_dir: str = "data/training/lora_out",
) -> None:
    data = build_alpaca_dataset(dataset_path)
    try:
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
        import torch
        from datasets import Dataset
    except ImportError as e:
        raise RuntimeError("Install train extras: pip install -e '.[train]'") from e

    records = __import__("json").loads(data.read_text(encoding="utf-8"))
    if not records:
        console.print("[yellow]No winner records — run forge first[/yellow]")
        return

    ds = Dataset.from_list(records)
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    lora = LoraConfig(**LORA_DEFAULTS, task_type="CAUSAL_LM")
    model = get_peft_model(model, lora)

    def fmt(ex):
        text = f"### Instruction:\n{ex['instruction']}\n### Response:\n{ex['output']}"
        return tokenizer(text, truncation=True, max_length=2048)

    tokenized = ds.map(fmt, remove_columns=ds.column_names)
    args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        logging_steps=10,
        save_steps=500,
        fp16=True,
    )
    Trainer(model=model, args=args, train_dataset=tokenized).train()
    model.save_pretrained(output_dir)
    console.print(f"[green]Saved LoRA adapter to {output_dir}[/green]")
