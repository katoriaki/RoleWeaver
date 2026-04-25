import argparse

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from role_config import DEFAULT_BASE_MODEL_PATH


def main():
    parser = argparse.ArgumentParser(description="Load a base model in 4bit and save it to a local directory")
    parser.add_argument("--src-model-path", default=DEFAULT_BASE_MODEL_PATH, help="Source base model path")
    parser.add_argument("--save-path", required=True, help="Output directory")
    args = parser.parse_args()

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    print("加载 tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(args.src_model_path, use_fast=True, trust_remote_code=True)

    print("以 4bit 方式加载模型...")
    model = AutoModelForCausalLM.from_pretrained(
        args.src_model_path,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )

    print("准备保存，先移动到 CPU...")
    model = model.to("cpu")

    print("保存量化模型...")
    model.save_pretrained(args.save_path)
    tokenizer.save_pretrained(args.save_path)

    print(f"已保存到: {args.save_path}")


if __name__ == "__main__":
    main()
