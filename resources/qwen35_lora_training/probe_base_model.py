import argparse

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def main():
    parser = argparse.ArgumentParser(description="Smoke-test a local Qwen-style base model")
    parser.add_argument(
        "--model-path",
        default="/public/huggingface-models/Qwen/Qwen3.5-9B",
        help="Local base model path",
    )
    parser.add_argument("--prompt", default="你是?", help="Prompt to test")
    parser.add_argument("--max-new-tokens", type=int, default=40)
    parser.add_argument("--local-files-only", action="store_true", default=True)
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(
        args.model_path,
        use_fast=True,
        trust_remote_code=True,
        local_files_only=args.local_files_only,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        device_map="auto",
        trust_remote_code=True,
        local_files_only=args.local_files_only,
    )
    model.generation_config.pad_token_id = tokenizer.pad_token_id

    messages = [{"role": "user", "content": args.prompt}]
    inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)

    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=args.max_new_tokens)

    generated = outputs[0][inputs["input_ids"].shape[-1]:]
    print(tokenizer.decode(generated, skip_special_tokens=True))


if __name__ == "__main__":
    main()
