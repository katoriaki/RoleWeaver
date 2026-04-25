import argparse
import os

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


DEFAULT_PROMPTS = [
    "请让我来培育你。",
    "你觉得我适合当制作人吗？",
    "今天你好像心情不错。",
    "你是在捉弄我吗？",
]


def chat_once(tokenizer, model, user_text: str, max_new_tokens: int = 120):
    messages = [{"role": "user", "content": user_text}]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )

    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.8,
            top_k=20,
            repetition_penalty=1.05,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    generated_ids = outputs[0][inputs["input_ids"].shape[1]:]
    result = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

    print("=" * 80)
    print("用户：", user_text)
    print("-" * 80)
    print("模型：", result)
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Probe a trained Qwen LoRA adapter")
    parser.add_argument(
        "--base-model-path",
        default="/public/huggingface-models/Qwen/Qwen3.5-9B",
        help="Local base model path",
    )
    parser.add_argument("--lora-path", default="./meiling-qwen35-9b-lora", help="LoRA adapter path")
    parser.add_argument("--prompt", action="append", help="Prompt to test. Can be repeated.")
    parser.add_argument("--max-new-tokens", type=int, default=120)
    parser.add_argument(
        "--online",
        action="store_true",
        help="Allow Hugging Face/network access. By default the script runs local/offline only.",
    )
    args = parser.parse_args()
    local_files_only = not args.online

    if local_files_only:
        os.environ["HF_HUB_OFFLINE"] = "1"

    print("1) loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        args.base_model_path,
        trust_remote_code=True,
        local_files_only=local_files_only,
        use_fast=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("2) loading base model...")
    base_model = AutoModelForCausalLM.from_pretrained(
        args.base_model_path,
        device_map="auto",
        torch_dtype=torch.bfloat16,
        trust_remote_code=True,
        local_files_only=local_files_only,
    )

    print("3) loading lora...")
    model = PeftModel.from_pretrained(base_model, args.lora_path)
    model.eval()

    for prompt in args.prompt or DEFAULT_PROMPTS:
        chat_once(tokenizer, model, prompt, max_new_tokens=args.max_new_tokens)


if __name__ == "__main__":
    main()
