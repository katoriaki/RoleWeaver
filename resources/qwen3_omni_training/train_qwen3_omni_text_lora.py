from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from torch.utils.data import DataLoader, Dataset
from transformers import BitsAndBytesConfig, Qwen3OmniMoeForConditionalGeneration, Qwen3OmniMoeProcessor


TEXT_LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj"]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if not isinstance(item, dict) or not isinstance(item.get("messages"), list):
                raise ValueError(f"{path}:{line_no} must contain a JSON object with a messages list")
            rows.append(item)
    return rows


def normalize_omni_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role") or "user")
        content = message.get("content", "")
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") in {"text", "image", "audio", "video"}:
                    parts.append(part)
                else:
                    parts.append({"type": "text", "text": str(part)})
        else:
            parts = [{"type": "text", "text": str(content)}]
        normalized.append({"role": role, "content": parts})
    return normalized


class ChatTextDataset(Dataset):
    def __init__(
        self,
        rows: list[dict[str, Any]],
        processor: Qwen3OmniMoeProcessor,
        max_length: int,
    ) -> None:
        self.rows = rows
        self.processor = processor
        self.max_length = max_length
        self.tokenizer = processor.tokenizer

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        messages = normalize_omni_messages(self.rows[index]["messages"])
        text = self.processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
        )
        encoded = self.tokenizer(
            text,
            max_length=self.max_length,
            truncation=True,
            padding=False,
            return_tensors=None,
        )
        input_ids = torch.tensor(encoded["input_ids"], dtype=torch.long)
        attention_mask = torch.tensor(encoded["attention_mask"], dtype=torch.long)
        labels = input_ids.clone()
        return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}


def collate_batch(batch: list[dict[str, torch.Tensor]], pad_token_id: int) -> dict[str, torch.Tensor]:
    max_len = max(item["input_ids"].shape[0] for item in batch)
    input_ids = []
    attention_mask = []
    labels = []
    for item in batch:
        length = item["input_ids"].shape[0]
        pad_len = max_len - length
        input_ids.append(torch.nn.functional.pad(item["input_ids"], (0, pad_len), value=pad_token_id))
        attention_mask.append(torch.nn.functional.pad(item["attention_mask"], (0, pad_len), value=0))
        labels.append(torch.nn.functional.pad(item["labels"], (0, pad_len), value=-100))
    return {
        "input_ids": torch.stack(input_ids),
        "attention_mask": torch.stack(attention_mask),
        "labels": torch.stack(labels),
    }


def write_status(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    payload["updated_at"] = now_iso()
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def save_adapter(model, processor, output_dir: Path, status_path: Path, status: dict[str, Any], label: str) -> Path:
    checkpoint_dir = output_dir / label
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(checkpoint_dir)
    processor.tokenizer.save_pretrained(checkpoint_dir)
    status["checkpoint_path"] = str(checkpoint_dir)
    write_status(status_path, status)
    return checkpoint_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Qwen3-Omni text-only LoRA/QLoRA trainer for RoleWeaver Shiro")
    parser.add_argument("--model-path", default="/public/huggingface-models/Qwen/Qwen3-Omni-30B-A3B-Instruct")
    parser.add_argument("--data-file", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--status-file", default="")
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--max-samples", type=int, default=0, help="0 means all samples")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--warmup-ratio", type=float, default=0.03)
    parser.add_argument("--save-steps", type=int, default=25)
    parser.add_argument("--logging-steps", type=int, default=1)
    parser.add_argument("--lora-r", type=int, default=4)
    parser.add_argument("--lora-alpha", type=int, default=8)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--quantization", choices=["4bit", "8bit", "bf16", "fp16"], default="4bit")
    parser.add_argument("--gradient-checkpointing", action="store_true", default=True)
    parser.add_argument(
        "--prepare-kbit-training",
        action="store_true",
        help="Use PEFT prepare_model_for_kbit_training. This is disabled by default for Qwen3-Omni because it can exceed 80GB.",
    )
    parser.add_argument("--online", action="store_true", help="Allow Hugging Face/network access")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    if not args.online:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("HF_DATASETS_OFFLINE", "1")

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    data_file = Path(args.data_file)
    output_dir = Path(args.output_dir)
    status_path = Path(args.status_file) if args.status_file else output_dir / "training_status.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Omni LoRA] model: {args.model_path}", flush=True)
    print(f"[Omni LoRA] data: {data_file}", flush=True)
    print(f"[Omni LoRA] output: {output_dir}", flush=True)
    print(f"[Omni LoRA] quantization: {args.quantization}", flush=True)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for Qwen3-Omni LoRA training.")
    print(f"[Omni LoRA] device: {torch.cuda.get_device_name(0)}", flush=True)

    rows = read_jsonl(data_file)
    if args.max_samples > 0:
        rows = rows[: args.max_samples]
    if not rows:
        raise RuntimeError("No training rows were loaded.")

    status: dict[str, Any] = {
        "status": "loading",
        "started_at": now_iso(),
        "model_path": args.model_path,
        "data_file": str(data_file),
        "output_dir": str(output_dir),
        "sample_count": len(rows),
        "quantization": args.quantization,
        "step": 0,
        "optimizer_step": 0,
        "loss": None,
    }
    write_status(status_path, status)

    processor = Qwen3OmniMoeProcessor.from_pretrained(
        args.model_path,
        trust_remote_code=True,
        local_files_only=not args.online,
    )
    tokenizer = processor.tokenizer
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs: dict[str, Any] = {
        "trust_remote_code": True,
        "device_map": {"": 0},
        "local_files_only": not args.online,
    }
    if args.quantization == "4bit":
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        model_kwargs["dtype"] = torch.bfloat16
    elif args.quantization == "8bit":
        model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        model_kwargs["dtype"] = torch.bfloat16
    elif args.quantization == "bf16":
        model_kwargs["dtype"] = torch.bfloat16
    else:
        model_kwargs["dtype"] = torch.float16

    omni_model = Qwen3OmniMoeForConditionalGeneration.from_pretrained(args.model_path, **model_kwargs)
    if hasattr(omni_model, "disable_talker"):
        omni_model.disable_talker()
    model = omni_model.thinker
    del omni_model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    model.config.use_cache = False
    if args.gradient_checkpointing and hasattr(model, "gradient_checkpointing_enable"):
        model.gradient_checkpointing_enable()
    if args.quantization in {"4bit", "8bit"} and args.prepare_kbit_training:
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=args.gradient_checkpointing)
    elif args.quantization in {"4bit", "8bit"} and hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=TEXT_LORA_TARGETS,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    model.train()

    dataset = ChatTextDataset(rows, processor=processor, max_length=args.max_length)
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=lambda batch: collate_batch(batch, tokenizer.pad_token_id),
    )
    updates_per_epoch = math.ceil(len(loader) / max(1, args.gradient_accumulation_steps))
    max_optimizer_steps = max(1, math.ceil(updates_per_epoch * args.epochs))
    warmup_steps = int(max_optimizer_steps * args.warmup_ratio)

    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )

    def lr_for_step(step: int) -> float:
        if warmup_steps > 0 and step < warmup_steps:
            return args.learning_rate * float(step + 1) / float(warmup_steps)
        progress = (step - warmup_steps) / max(1, max_optimizer_steps - warmup_steps)
        return args.learning_rate * max(0.0, 0.5 * (1.0 + math.cos(math.pi * progress)))

    status.update({"status": "training", "max_optimizer_steps": max_optimizer_steps})
    write_status(status_path, status)
    started = time.time()
    optimizer_step = 0
    raw_step = 0
    running_loss = 0.0

    try:
        epoch = 0
        while optimizer_step < max_optimizer_steps:
            epoch += 1
            for batch in loader:
                raw_step += 1
                batch = {k: v.to(model.device) for k, v in batch.items()}
                outputs = model(**batch)
                loss = outputs.loss / max(1, args.gradient_accumulation_steps)
                loss.backward()
                running_loss += float(loss.detach().cpu()) * max(1, args.gradient_accumulation_steps)

                if raw_step % args.gradient_accumulation_steps == 0:
                    lr = lr_for_step(optimizer_step)
                    for group in optimizer.param_groups:
                        group["lr"] = lr
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                    optimizer_step += 1
                    avg_loss = running_loss / max(1, args.gradient_accumulation_steps)
                    running_loss = 0.0

                    status.update(
                        {
                            "status": "training",
                            "epoch": epoch,
                            "step": raw_step,
                            "optimizer_step": optimizer_step,
                            "max_optimizer_steps": max_optimizer_steps,
                            "loss": avg_loss,
                            "learning_rate": lr,
                            "elapsed_seconds": int(time.time() - started),
                        }
                    )
                    write_status(status_path, status)
                    if optimizer_step % args.logging_steps == 0:
                        print(
                            f"progress optimizer_step={optimizer_step}/{max_optimizer_steps} "
                            f"raw_step={raw_step} epoch={epoch} loss={avg_loss:.6f} lr={lr:.8g}",
                            flush=True,
                        )
                    if args.save_steps > 0 and optimizer_step % args.save_steps == 0:
                        checkpoint = save_adapter(
                            model,
                            processor,
                            output_dir,
                            status_path,
                            status,
                            f"checkpoint-{optimizer_step}",
                        )
                        print(f"[Omni LoRA] saved {checkpoint}", flush=True)

                    if optimizer_step >= max_optimizer_steps:
                        break
    except KeyboardInterrupt:
        status["status"] = "interrupted"
        checkpoint = save_adapter(model, processor, output_dir, status_path, status, f"interrupted-{optimizer_step}")
        print(f"[Omni LoRA] interrupted; saved {checkpoint}", flush=True)
        return 130

    final_dir = save_adapter(model, processor, output_dir, status_path, status, "final")
    status.update(
        {
            "status": "completed",
            "finished_at": now_iso(),
            "final_adapter_path": str(final_dir),
            "elapsed_seconds": int(time.time() - started),
        }
    )
    write_status(status_path, status)
    print(f"[Omni LoRA] completed. final adapter: {final_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
