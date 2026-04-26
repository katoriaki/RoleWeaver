import json
import re
from pathlib import Path

INPUT_FILE = "role_sft_source.jsonl"
OUTPUT_FILE = "role_sft_train.jsonl"

# 是否保留 system
KEEP_SYSTEM = False

# 如果保留 system，是否统一替换成短版
SHORTEN_SYSTEM = False
SHORT_SYSTEM_TEXT = ""

# 允许的 role
ALLOWED_ROLES = {"system", "user", "assistant"}

# 明显会污染训练的文本特征
BAD_PATTERNS = [
    r"^第[一二三四五六七八九十百0-9]+话",
    r"^第[一二三四五六七八九十百0-9]+章",
    r"^地点[:：]",
    r"^场景[:：]",
    r"^时间[:：]",
    r"^旁白[:：]",
    r"^\s*（.*?）\s*$",   # 整句只有括号说明
    r"^\s*\(.*?\)\s*$",
]

bad_regexes = [re.compile(p) for p in BAD_PATTERNS]


def is_bad_text(text: str) -> bool:
    """判断一段文本是否明显像标题/场景说明/角色标签，而不是自然对话。"""
    if not isinstance(text, str):
        return True

    t = text.strip()
    if not t:
        return True

    for rgx in bad_regexes:
        if rgx.search(t):
            return True

    # 行首角色标签过多，也判脏
    role_tag_hits = 0
    for line in t.splitlines():
        s = line.strip()
        if re.match(r"^.{1,24}[:：]", s):
            role_tag_hits += 1
    if role_tag_hits >= 1:
        return True

    return False


def normalize_text(text: str) -> str:
    """基础清洗：去首尾空白，压多余空行。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def clean_messages(messages):
    """
    返回:
      cleaned_messages, reason
    reason 为 None 表示成功，否则表示丢弃原因
    """
    if not isinstance(messages, list) or len(messages) == 0:
        return None, "empty_or_invalid_messages"

    cleaned = []

    for msg in messages:
        if not isinstance(msg, dict):
            return None, "message_not_dict"

        role = msg.get("role")
        content = msg.get("content")

        if role not in ALLOWED_ROLES:
            return None, "invalid_role"

        if not isinstance(content, str):
            return None, "content_not_str"

        content = normalize_text(content)
        if not content:
            return None, "empty_content"

        # system 处理
        if role == "system":
            if not KEEP_SYSTEM:
                continue
            if SHORTEN_SYSTEM:
                content = SHORT_SYSTEM_TEXT

        # user / assistant 做脏文本过滤
        if role in {"user", "assistant"} and is_bad_text(content):
            return None, f"bad_{role}_text"

        cleaned.append({"role": role, "content": content})

    if len(cleaned) == 0:
        return None, "all_removed"

    # 如果删掉 system 后，不是至少 user+assistant，就不要
    non_system = [m for m in cleaned if m["role"] in {"user", "assistant"}]
    if len(non_system) < 2:
        return None, "not_enough_turns"

    # 最终只保留 user / assistant，避免 system 干扰
    if not KEEP_SYSTEM:
        cleaned = [m for m in cleaned if m["role"] in {"user", "assistant"}]

    # 保证最后至少有一条 assistant
    if not any(m["role"] == "assistant" for m in cleaned):
        return None, "no_assistant"

    # 最常见理想情况：user -> assistant
    # 如果有多轮，也允许保留
    # 但第一条最好不是 assistant
    if cleaned[0]["role"] == "assistant":
        return None, "starts_with_assistant"

    return cleaned, None


def convert_record(obj):
    """把原始样本转成最终训练样本。"""
    if not isinstance(obj, dict):
        return None, "record_not_dict"

    messages = obj.get("messages")
    cleaned_messages, reason = clean_messages(messages)
    if reason is not None:
        return None, reason

    return {"messages": cleaned_messages}, None


def main():
    input_path = Path(INPUT_FILE)
    output_path = Path(OUTPUT_FILE)

    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    total = 0
    kept = 0
    dropped = 0
    drop_reasons = {}

    with input_path.open("r", encoding="utf-8") as fin, \
         output_path.open("w", encoding="utf-8") as fout:

        for line_no, line in enumerate(fin, start=1):
            line = line.strip()
            if not line:
                continue

            total += 1

            try:
                obj = json.loads(line)
            except Exception:
                dropped += 1
                drop_reasons["json_decode_error"] = drop_reasons.get("json_decode_error", 0) + 1
                continue

            cleaned, reason = convert_record(obj)
            if reason is not None:
                dropped += 1
                drop_reasons[reason] = drop_reasons.get(reason, 0) + 1
                continue

            fout.write(json.dumps(cleaned, ensure_ascii=False) + "\n")
            kept += 1

    print("=" * 50)
    print("清洗完成")
    print(f"输入文件: {input_path}")
    print(f"输出文件: {output_path}")
    print(f"总样本数: {total}")
    print(f"保留样本数: {kept}")
    print(f"丢弃样本数: {dropped}")
    print(f"保留率: {kept / total:.2%}" if total else "保留率: N/A")
    print("-" * 50)
    print("丢弃原因统计:")
    for k, v in sorted(drop_reasons.items(), key=lambda x: (-x[1], x[0])):
        print(f"{k}: {v}")
    print("=" * 50)


if __name__ == "__main__":
    main()
