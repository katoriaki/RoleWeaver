import argparse
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from role_config import DEFAULT_BASE_MODEL_PATH


def main():
    parser = argparse.ArgumentParser(description="Quickly probe a base chat model with a short prompt")
    parser.add_argument("--base-model-path", default=DEFAULT_BASE_MODEL_PATH, help="Path to the base model")
    parser.add_argument("--system-prompt", default="你是一个简洁自然的聊天角色。", help="System prompt")
    parser.add_argument("--user-prompt", default="今天感觉怎么样？请只用一句话回答。", help="User prompt")
    parser.add_argument("--max-new-tokens", type=int, default=32, help="Max generated tokens")
    args = parser.parse_args()

    print("CUDA available:", torch.cuda.is_available())
    if not torch.cuda.is_available():
        raise RuntimeError("没有检测到 CUDA，请确认你是在 GPU 环境下运行。")
    print("Device:", torch.cuda.get_device_name(0))

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    print("加载 tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model_path, use_fast=True, trust_remote_code=True)

    print("加载 model...")
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model_path,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.float16,
        trust_remote_code=True,
    )

    messages = [
        {"role": "system", "content": args.system_prompt},
        {"role": "user", "content": args.user_prompt},
    ]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )

    inputs = tokenizer(text, return_tensors="pt")
    inputs = {key: value.to(model.device) for key, value in inputs.items()}

    print("开始生成...")
    t0 = time.time()

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=args.max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.8,
            repetition_penalty=1.0,
        )

    dt = time.time() - t0
    new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
    result = tokenizer.decode(new_tokens, skip_special_tokens=True)

    print(f"生成完成，用时 {dt:.1f} 秒")
    print(result)


if __name__ == "__main__":
    main()
