import argparse
import json
import os
import time
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def load_messages(path: Path, limit: int):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            messages = item.get("messages")
            if isinstance(messages, list) and messages:
                rows.append(messages)
            if len(rows) >= limit:
                break
    if not rows:
        raise RuntimeError(f"No messages found in {path}")
    return rows


def encode_messages(tokenizer, messages, max_length: int):
    try:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
            enable_thinking=False,
        )
    except TypeError:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
        )
    encoded = tokenizer(
        text,
        return_tensors="pt",
        max_length=max_length,
        truncation=True,
        padding=False,
    )
    encoded["labels"] = encoded["input_ids"].clone()
    return encoded


def main():
    parser = argparse.ArgumentParser(description="Tiny real QLoRA smoke training for RoleWeaver continual adapter bank.")
    parser.add_argument("--base-model-path", required=True)
    parser.add_argument("--data-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-samples", type=int, default=4)
    parser.add_argument("--max-steps", type=int, default=1)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--lora-r", type=int, default=4)
    parser.add_argument("--lora-alpha", type=int, default=8)
    parser.add_argument("--lora-dropout", type=float, default=0.0)
    args = parser.parse_args()

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    os.environ.setdefault("PYTHONUTF8", "1")

    data_path = Path(args.data_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("CUDA available:", torch.cuda.is_available())
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this smoke trainer.")
    print("Device:", torch.cuda.get_device_name(0))
    free, total = torch.cuda.mem_get_info()
    print("GPU free/total GB:", round(free / 1024**3, 2), "/", round(total / 1024**3, 2))

    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        args.base_model_path,
        use_fast=True,
        trust_remote_code=True,
        local_files_only=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("Loading 4bit base model...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model_path,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        local_files_only=True,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model)

    print("Attaching LoRA...")
    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()
    model.train()

    messages_rows = load_messages(data_path, args.max_samples)
    batches = [encode_messages(tokenizer, messages, args.max_length) for messages in messages_rows]
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=args.learning_rate)

    losses = []
    print("Starting smoke training...")
    for step in range(max(1, args.max_steps)):
        batch = batches[step % len(batches)]
        batch = {key: value.to(model.device) for key, value in batch.items()}
        optimizer.zero_grad(set_to_none=True)
        loss = model(**batch).loss
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
        print(f"step={step + 1} loss={losses[-1]:.6f}")

    print("Saving adapter...")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    manifest = {
        "created_ts": int(time.time()),
        "base_model_path": args.base_model_path,
        "data_path": str(data_path),
        "output_dir": str(output_dir),
        "max_samples": args.max_samples,
        "max_steps": args.max_steps,
        "max_length": args.max_length,
        "learning_rate": args.learning_rate,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "losses": losses,
        "status": "trained_smoke_not_enabled",
        "activation_policy": "Do not load automatically; require persona regression before enabling.",
    }
    (output_dir / "roleweaver_continual_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
