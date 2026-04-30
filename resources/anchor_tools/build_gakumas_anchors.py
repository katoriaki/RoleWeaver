import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


MESSAGE_RE = re.compile(r"^\[message\s+text=(.*?)\s+name=([^\s\]]+)", re.S)
RUBY_RE = re.compile(r"<r\\=(.*?)>(.*?)</r>", re.S)
TAG_RE = re.compile(r"<[^>]+>")


DIMENSION_KEYWORDS = {
    "identity": ["秦谷美鈴", "秦谷美铃", "美鈴", "美铃", "わたし", "自己紹介"],
    "autonomy": ["理解", "受け入れて", "期待", "選", "选择", "一緒したい", "ご一緒"],
    "care": ["料理", "花", "お世話", "照顾", "お昼寝", "散歩", "休息"],
    "ambition": ["アイドル", "偶像", "ステージ", "舞台", "ライブ", "勝", "オーディション"],
    "discipline": ["レッスン", "練習", "训练", "勉強", "学习", "体内時計"],
    "relationship_boundary": ["プロデューサー", "制作人", "あなた", "您", "距離", "一緒"],
    "sleepiness": ["昼寝", "お昼寝", "眠", "睡", "休む"],
}

TIME_BLOCK_FOR_DIMENSION = {
    "identity": ["relationship_time"],
    "autonomy": ["relationship_time", "idol_training"],
    "care": ["rest", "walk", "cooking"],
    "ambition": ["idol_training"],
    "discipline": ["classes", "homework", "idol_training"],
    "relationship_boundary": ["relationship_time"],
    "sleepiness": ["rest", "lunch"],
}


def clean_text(value: str) -> str:
    value = value.replace("\\r\\n", "\n").replace("\\n", "\n")
    value = TAG_RE.sub("", value)
    value = value.replace("\\=", "=").replace("\\\"", "\"")
    return re.sub(r"\s+", " ", value).strip()


def parse_message_line(line: str) -> Dict:
    match = MESSAGE_RE.match(line.strip())
    if not match:
        return {}
    raw_text, name = match.groups()
    pairs = []
    for ruby in RUBY_RE.finditer(raw_text):
        ja = clean_text(ruby.group(1))
        zh = clean_text(ruby.group(2))
        if ja or zh:
            pairs.append({"ja": ja, "zh": zh})
    if not pairs:
        text = clean_text(raw_text)
        if text:
            pairs.append({"ja": "", "zh": text})
    return {"speaker": clean_text(name), "pairs": pairs}


def parse_adv_file(path: Path) -> List[Dict]:
    messages = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.startswith("[message "):
                continue
            message = parse_message_line(line)
            if message:
                message["line"] = line_number
                messages.append(message)
    return messages


def load_titles(master_trans: Path) -> Dict[str, str]:
    titles: Dict[str, str] = {}
    for path in master_trans.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            item_id = str(row.get("id") or row.get("storyId") or "")
            title = str(row.get("title") or row.get("name") or "")
            if item_id and title:
                titles[item_id] = title
    return titles


def normalize_id(value: str) -> str:
    value = value.lower()
    value = value.replace("adv_", "")
    value = value.replace("p_story", "pstory")
    return re.sub(r"[^a-z0-9]+", "", value)


def title_for_file(path: Path, titles: Dict[str, str]) -> str:
    file_key = normalize_id(path.stem)
    best = ""
    best_len = 0
    for item_id, title in titles.items():
        key = normalize_id(item_id)
        if key and (key in file_key or file_key in key) and len(key) > best_len:
            best = title
            best_len = len(key)
    return best


def dimensions_for_text(text: str) -> List[str]:
    dims = []
    for dim, words in DIMENSION_KEYWORDS.items():
        if any(word in text for word in words):
            dims.append(dim)
    return dims or ["voice_style"]


def time_blocks_for_dimensions(dimensions: Iterable[str]) -> List[str]:
    blocks = []
    for dim in dimensions:
        blocks.extend(TIME_BLOCK_FOR_DIMENSION.get(dim, []))
    return sorted(set(blocks or ["relationship_time"]))


def source_category(path: Path) -> str:
    stem = path.stem
    if stem.startswith("adv_dear_"):
        return "dearness"
    if stem.startswith("adv_pstory_"):
        return "produce_story"
    if stem.startswith("adv_pevent_"):
        return "produce_event"
    if stem.startswith("adv_cidol-"):
        return "idol_card"
    if stem.startswith("adv_event_"):
        return "event"
    if stem.startswith("adv_startup_"):
        return "startup"
    return "story"


def quote_text(pair: Dict) -> str:
    return " ".join(part for part in [pair.get("ja", ""), pair.get("zh", "")] if part)


def candidate_score(messages: List[Dict], index: int, character_names: List[str]) -> int:
    message = messages[index]
    text = " ".join(quote_text(pair) for pair in message.get("pairs", []))
    score = 0
    score += len(dimensions_for_text(text)) * 4
    score += min(len(text), 80) // 10
    if any(name in message.get("speaker", "") for name in character_names):
        score += 10
    if any(word in text for word in ["理解", "受け入れて", "アイドル", "プロデューサー", "お昼寝", "秦谷"]):
        score += 8
    return score


def build_anchor(path: Path, messages: List[Dict], index: int, title: str, character_id: str, character_names: List[str]) -> Dict:
    message = messages[index]
    pairs = message.get("pairs", [])[:2]
    text = " ".join(quote_text(pair) for pair in pairs)
    dimensions = dimensions_for_text(text)
    category = source_category(path)
    source_id = path.stem
    digest = hashlib.sha1(f"{source_id}:{message.get('line')}:{text}".encode("utf-8", errors="ignore")).hexdigest()[:10]
    speaker = message.get("speaker") or character_names[0]
    summary = (
        f"{title or source_id} 中，{speaker} 的短对白体现了 "
        f"{'、'.join(dimensions)}；运行时只把它作为人格锚点，不当作新的用户记忆。"
    )
    return {
        "schema_version": "1.0",
        "id": f"{character_id}-{digest}",
        "character_id": character_id,
        "title": title or source_id,
        "source_file": str(path.name),
        "source_category": category,
        "line": message.get("line"),
        "speaker": speaker,
        "summary": summary,
        "persona_dimensions": dimensions,
        "tags": sorted(set(dimensions + [category])),
        "time_blocks": time_blocks_for_dimensions(dimensions),
        "priority": 10 + len(dimensions),
        "confidence": 0.86,
        "evidence_quotes": [
            {
                "ja": pair.get("ja", "")[:80],
                "zh": pair.get("zh", "")[:80],
            }
            for pair in pairs
            if pair.get("ja") or pair.get("zh")
        ],
    }


def iter_character_files(resource: Path, character_id: str) -> Iterable[Path]:
    yield from sorted(resource.glob(f"adv_*{character_id}*.txt"))


def build_anchors(
    local_files_root: Path,
    character_id: str,
    character_names: List[str],
    limit: int,
) -> Tuple[List[Dict], Dict]:
    resource = local_files_root / "resource"
    master_trans = local_files_root / "masterTrans"
    titles = load_titles(master_trans)
    candidates = []
    files = list(iter_character_files(resource, character_id))
    for path in files:
        messages = parse_adv_file(path)
        title = title_for_file(path, titles)
        for index, message in enumerate(messages):
            speaker = message.get("speaker", "")
            if not any(name in speaker for name in character_names):
                continue
            score = candidate_score(messages, index, character_names)
            anchor = build_anchor(path, messages, index, title, character_id, character_names)
            candidates.append((score, anchor))
    candidates.sort(key=lambda item: (item[0], item[1]["id"]), reverse=True)
    anchors = []
    seen = set()
    for _, anchor in candidates:
        key = json.dumps(anchor.get("evidence_quotes", []), ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        anchors.append(anchor)
        if len(anchors) >= limit:
            break
    meta = {
        "schema_version": "1.0",
        "character_id": character_id,
        "source_root": str(local_files_root),
        "source_file_count": len(files),
        "anchor_count": len(anchors),
        "note": "Generated anchors contain short evidence snippets and derived summaries only. They are persona anchors, not conversation memories.",
    }
    return anchors, meta


def write_jsonl(path: Path, anchors: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for anchor in anchors:
            f.write(json.dumps(anchor, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build RoleWeaver persona anchors from Gakumas Localify ADV scripts.")
    parser.add_argument("--local-files-root", required=True, help="Path to gakumas-local/local-files")
    parser.add_argument("--character-id", default="hmsz")
    parser.add_argument("--character-name", action="append", default=["美铃", "美鈴", "秦谷美铃", "秦谷美鈴"])
    parser.add_argument("--output", required=True)
    parser.add_argument("--meta-output", default="")
    parser.add_argument("--limit", type=int, default=120)
    args = parser.parse_args()

    anchors, meta = build_anchors(
        Path(args.local_files_root),
        character_id=args.character_id,
        character_names=args.character_name,
        limit=args.limit,
    )
    output = Path(args.output)
    write_jsonl(output, anchors)
    meta_output = Path(args.meta_output) if args.meta_output else output.with_suffix(".meta.json")
    meta_output.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
