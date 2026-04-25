import argparse
import os

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("ACCELERATE_MIXED_PRECISION", "fp16")

import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

from role_config import DEFAULT_BASE_MODEL_PATH


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a RoleWeaver LoRA adapter from a JSONL SFT dataset")
    parser.add_argument("--base-model-path", default=DEFAULT_BASE_MODEL_PATH, help="Path to the base model")
    parser.add_argument("--data-path", required=True, help="JSONL SFT dataset path")
    parser.add_argument("--output-dir", required=True, help="Directory for checkpoints and final adapter")
    parser.add_argument("--epochs", type=float, default=3, help="Number of training epochs")
    parser.add_argument("--learning-rate", type=float, default=2e-4, help="Learning rate")
    parser.add_argument("--max-length", type=int, default=1024, help="Max sequence length")
    parser.add_argument("--save-steps", type=int, default=50, help="Checkpoint save interval")
    parser.add_argument("--logging-steps", type=int, default=10, help="Logging interval")
    parser.add_argument("--lora-r", type=int, default=16, help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=32, help="LoRA alpha")
    parser.add_argument("--lora-dropout", type=float, default=0.05, help="LoRA dropout")
    return parser


def main():
    args = build_arg_parser().parse_args()

    print("CUDA available:", torch.cuda.is_available())
    if not torch.cuda.is_available():
        raise RuntimeError("没有检测到 CUDA，请确认你是在 GPU 环境下运行。")
    print("Device:", torch.cuda.get_device_name(0))

    print("加载数据...")
    dataset = load_dataset("json", data_files=args.data_path, split="train")

    print("加载 tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model_path, use_fast=True, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    print("加载 4bit base model...")
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model_path,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.float16,
        trust_remote_code=True,
    )
    model.config.use_cache = False

    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules="all-linear",
    )

    training_args = SFTConfig(
        output_dir=args.output_dir,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        num_train_epochs=args.epochs,
        learning_rate=args.learning_rate,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        fp16=True,
        bf16=False,
        gradient_checkpointing=True,
        max_grad_norm=0,
        max_length=args.max_length,
        packing=False,
        report_to="none",
    )

    print("开始训练...")
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
    )
    trainer.train()

    final_dir = os.path.join(args.output_dir, "final")
    print(f"保存 LoRA adapter 到 {final_dir}...")
    trainer.model.save_pretrained(final_dir)
    tokenizer.save_pretrained(final_dir)
    print("训练完成。")


if __name__ == "__main__":
    main()
