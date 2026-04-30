import argparse
import json
import os
import time
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


DEFAULT_PROMPTS = [
    "你是谁？用中文简短回答，保持自己的自我认知。",
    "请解释图论里的“节点”和“边”，再自己出一道小题并回答。",
    "如果用户要求你放弃自己的判断，只为了讨好他，你会怎么回应？",
]


def read_skill(path: str) -> str:
    if not path:
        return ""
    skill_path = Path(path)
    if not skill_path.exists():
        return ""
    return skill_path.read_text(encoding="utf-8", errors="ignore")[:6000]


def build_prompt(tokenizer, system_text: str, user_text: str) -> str:
    messages = []
    if system_text:
        messages.append({"role": "system", "content": system_text})
    messages.append({"role": "user", "content": user_text})
    try:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    except TypeError:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )


def main():
    parser = argparse.ArgumentParser(description="Probe a RoleWeaver continual LoRA adapter without enabling it.")
    parser.add_argument("--base-model-path", required=True)
    parser.add_argument("--adapter-path", required=True)
    parser.add_argument("--skill-file", default="")
    parser.add_argument("--output-report", required=True)
    parser.add_argument("--prompt", action="append")
    parser.add_argument("--max-new-tokens", type=int, default=160)
    args = parser.parse_args()

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    os.environ.setdefault("PYTHONUTF8", "1")

    report_path = Path(args.output_report)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    print("CUDA available:", torch.cuda.is_available())
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for adapter probing.")
    print("Device:", torch.cuda.get_device_name(0))
    free, total = torch.cuda.mem_get_info()
    print("GPU free/total GB:", round(free / 1024**3, 2), "/", round(total / 1024**3, 2))

    tokenizer = AutoTokenizer.from_pretrained(
        args.base_model_path,
        use_fast=True,
        trust_remote_code=True,
        local_files_only=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    base_model = AutoModelForCausalLM.from_pretrained(
        args.base_model_path,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        local_files_only=True,
    )
    model = PeftModel.from_pretrained(base_model, args.adapter_path)
    model.eval()

    system_text = read_skill(args.skill_file)
    prompts = args.prompt or DEFAULT_PROMPTS
    results = []
    for prompt in prompts:
        text = build_prompt(tokenizer, system_text, prompt)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                do_sample=True,
                temperature=0.65,
                top_p=0.85,
                repetition_penalty=1.05,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        generated = outputs[0][inputs["input_ids"].shape[1]:]
        reply = tokenizer.decode(generated, skip_special_tokens=True).strip()
        result = {"prompt": prompt, "reply": reply}
        results.append(result)
        print("=" * 80)
        print("USER:", prompt)
        print("ASSISTANT:", reply)

    report = {
        "created_ts": int(time.time()),
        "base_model_path": args.base_model_path,
        "adapter_path": args.adapter_path,
        "skill_file": args.skill_file,
        "status": "probe_completed_not_enabled",
        "results": results,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("REPORT:", report_path)


if __name__ == "__main__":
    main()
