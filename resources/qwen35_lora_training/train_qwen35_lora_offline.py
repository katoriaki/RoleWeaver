import argparse
import os

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from trl import SFTTrainer


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline Qwen3.5-9B LoRA SFT training reference")
    parser.add_argument(
        "--model-path",
        default="/public/huggingface-models/Qwen/Qwen3.5-9B",
        help="Local base model path",
    )
    parser.add_argument("--data-file", default="meiling_sft_updated_v2.jsonl", help="JSONL dataset path")
    parser.add_argument("--output-dir", default="./meiling-qwen35-9b-lora", help="LoRA output directory")
    parser.add_argument("--epochs", type=float, default=3)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--per-device-train-batch-size", type=int, default=2)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--save-steps", type=int, default=50)
    parser.add_argument("--save-total-limit", type=int, default=2)
    parser.add_argument("--logging-steps", type=int, default=10)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument(
        "--online",
        action="store_true",
        help="Allow Hugging Face/network access. By default the script runs local/offline only.",
    )
    return parser


def main():
    args = build_arg_parser().parse_args()
    local_files_only = not args.online
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

    if local_files_only:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"

    print("1) loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_path,
        use_fast=True,
        trust_remote_code=True,
        local_files_only=local_files_only,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("2) loading model...")
    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        device_map="auto",
        dtype=torch.bfloat16,
        trust_remote_code=True,
        local_files_only=local_files_only,
    )
    model.generation_config.pad_token_id = tokenizer.pad_token_id
    model.config.use_cache = False

    print("3) attaching LoRA...")
    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    print("4) loading dataset...")
    dataset = load_dataset("json", data_files=args.data_file, split="train")
    print("dataset size:", len(dataset))
    print("columns:", dataset.column_names)
    print("sample[0]:", dataset[0])

    def build_chat_text(example):
        template_kwargs = {
            "tokenize": False,
            "add_generation_prompt": False,
            "enable_thinking": False,
        }
        try:
            text = tokenizer.apply_chat_template(example["messages"], **template_kwargs)
        except TypeError:
            template_kwargs.pop("enable_thinking")
            text = tokenizer.apply_chat_template(example["messages"], **template_kwargs)
        return {"text": text}

    print("5) building text field...")
    dataset = dataset.map(build_chat_text)
    print("sample text:")
    print(dataset[0]["text"])
    print("-" * 80)

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        num_train_epochs=args.epochs,
        bf16=True,
        fp16=False,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,
        report_to="none",
    )

    print("6) building trainer...")
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        args=training_args,
    )

    print("7) start training...")
    trainer.train()

    print("8) saving...")
    trainer.model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"done. saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
