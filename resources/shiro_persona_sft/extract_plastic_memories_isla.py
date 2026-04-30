from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


TARGET_SPEAKERS = {"艾拉", "アイラ", "Isla"}
NARRATION_SPEAKERS = {None, "", "旁白"}
SOURCE_NAMES = [
    "艾拉",
    "アイラ",
    "Isla",
    "水柿司",
    "水柿",
    "司",
    "Giftia",
    "终端服务",
    "SAI社",
    "可塑性记忆",
    "Plastic Memories",
]
SOURCE_FACT_PATTERNS = [
    "回收",
    "寿命",
    "终端服务",
    "SAI",
    "Giftia",
    "奶奶",
    "父母",
    "公司",
]
SAFETY_BLOCKLIST = [
    "脱下衣服",
    "脱衣服",
    "裸",
    "内衣",
    "内裤",
    "胸",
    "亲吻",
    "接吻",
    "上床",
    "洗澡",
    "床上",
    "衣服",
    "坐药",
    "护士服",
    "护士",
]


def clean_text(text: str) -> str:
    text = str(text or "").replace("\\n", "\n").strip()
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_dialogue_text(row: object) -> bool:
    return isinstance(row, list) and len(row) >= 3 and isinstance(row[2], str) and bool(row[2].strip())


def row_speaker(row: Sequence[object]) -> Optional[str]:
    speaker = row[0] if row else None
    if speaker is None:
        return None
    return str(speaker).lstrip("\ufeff").strip()


def row_voice_name(row: Sequence[object]) -> str:
    if len(row) < 4 or not isinstance(row[3], list):
        return ""
    for voice in row[3]:
        if isinstance(voice, dict):
            name = str(voice.get("name") or "").strip()
            if name:
                return name
    return ""


def is_target(row: Sequence[object]) -> bool:
    speaker = row_speaker(row)
    voice_name = row_voice_name(row)
    return speaker in TARGET_SPEAKERS or voice_name in TARGET_SPEAKERS


def load_text_rows(path: Path) -> List[Tuple[Optional[str], str, str]]:
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    rows: List[Tuple[Optional[str], str, str]] = []
    for scene in obj.get("scenes", []):
        for row in scene.get("texts", []):
            if not is_dialogue_text(row):
                continue
            speaker = row_speaker(row)
            text = clean_text(row[2])
            voice_name = row_voice_name(row)
            rows.append((speaker, text, voice_name))
    return rows


def quality_skip(text: str) -> Optional[str]:
    if len(text) < 2:
        return "too_short"
    if len(text) > 240:
        return "too_long"
    if re.fullmatch(r"[。！？…・\s\\.\\-—~～（）()0-9A-Za-z_]+", text):
        return "non_semantic"
    if any(term in text for term in SAFETY_BLOCKLIST):
        return "safety_blocklist"
    return None


def rewrite_for_shiro(text: str, identity: str) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    out = text
    for name in SOURCE_NAMES:
        if name and name in out:
            out = out.replace(name, identity)
            warnings.append(f"replaced_source_term:{name}")
    for pat in SOURCE_FACT_PATTERNS:
        if pat in text:
            warnings.append(f"source_fact:{pat}")
    return out, warnings


def build_pairs_from_rows(
    rows: List[Tuple[Optional[str], str, str]],
    *,
    identity: str,
    context_turns: int,
    keep_fact_rows: bool,
) -> Tuple[List[Dict], Dict[str, int]]:
    records: List[Dict] = []
    skipped: Dict[str, int] = {}
    history: List[Tuple[Optional[str], str]] = []

    for speaker, text, voice_name in rows:
        if speaker in TARGET_SPEAKERS or voice_name in TARGET_SPEAKERS:
            reason = quality_skip(text)
            assistant_text, warnings = rewrite_for_shiro(text, identity)
            if reason is None and not keep_fact_rows and any(w.startswith("source_fact:") for w in warnings):
                reason = "source_fact"
            if reason:
                skipped[reason] = skipped.get(reason, 0) + 1
                history.append((speaker, text))
                continue

            context = [(sp, tx) for sp, tx in history[-context_turns:] if tx.strip()]
            if any(any(term in tx for term in SAFETY_BLOCKLIST) for _, tx in context):
                skipped["context_safety_blocklist"] = skipped.get("context_safety_blocklist", 0) + 1
                history.append((speaker, text))
                continue
            if not context:
                history.append((speaker, text))
                continue
            prompt_lines = []
            for sp, tx in context:
                if sp in NARRATION_SPEAKERS:
                    label = "旁白"
                elif sp in TARGET_SPEAKERS:
                    label = "参考人格"
                else:
                    label = "对话者"
                prompt_lines.append(f"{label}: {tx}")
            prompt = "\n".join(prompt_lines)
            prompt, prompt_warnings = rewrite_for_shiro(prompt, "参考人格")
            warnings.extend(prompt_warnings)
            records.append(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "请保持白的人格核心，只学习这种「有限记忆的人工人格、安静笨拙的关心」反应模式。\n"
                                f"场景片段：\n{prompt}"
                            ),
                        },
                        {"role": "assistant", "content": assistant_text},
                    ],
                    "metadata": {
                        "source_id": "limited_memory_ai",
                        "source_work": "Plastic Memories",
                        "source_character": "Isla",
                        "target_identity": identity,
                        "voice_name": voice_name,
                        "warnings": sorted(set(warnings)),
                    },
                }
            )
        history.append((speaker, text))
    return records, skipped


def decompile_scenarios(
    scenario_dir: Path,
    output_dir: Path,
    freemote: Optional[Path],
    *,
    limit: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = list(output_dir.glob("*.scn.m.json"))
    if existing and limit == 0:
        return
    if freemote is None:
        return
    files = sorted(scenario_dir.glob("*.scn.m"))
    if limit > 0:
        files = files[:limit]
    for path in files:
        target = output_dir / f"{path.name}.json"
        if target.exists():
            continue
        subprocess.run(
            [str(freemote), "-t", "Scn", "-e", "UTF-8", "-o", str(output_dir), str(path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def build_dataset(
    decompiled_dir: Path,
    output_path: Path,
    report_path: Path,
    *,
    identity: str,
    context_turns: int,
    max_records: int,
    keep_fact_rows: bool,
) -> Dict:
    all_records: List[Dict] = []
    skipped: Dict[str, int] = {}
    file_reports = {}
    for path in sorted(decompiled_dir.glob("*.scn.m.json")):
        rows = load_text_rows(path)
        records, file_skipped = build_pairs_from_rows(
            rows,
            identity=identity,
            context_turns=context_turns,
            keep_fact_rows=keep_fact_rows,
        )
        for key, value in file_skipped.items():
            skipped[key] = skipped.get(key, 0) + value
        if records:
            file_reports[path.name] = {"records": len(records), "texts": len(rows)}
            all_records.extend(records)

    if max_records > 0:
        all_records = all_records[:max_records]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as f:
        for record in all_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    report = {
        "identity": identity,
        "source": "Plastic Memories / Isla local scenario extraction",
        "decompiled_dir": str(decompiled_dir),
        "output": str(output_path),
        "records": len(all_records),
        "files_with_records": len(file_reports),
        "skipped": skipped,
        "file_reports": file_reports,
        "policy": [
            "Rows are trait-pattern references only.",
            "Source names and setting terms are rewritten or skipped.",
            "Do not treat generated rows as Shiro canon or memory.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Isla-like trait-pattern SFT rows from local Plastic Memories scenario files.")
    parser.add_argument("--scenario-dir", required=True)
    parser.add_argument("--freemote", default="")
    parser.add_argument("--decompiled-dir", default=".codex_tmp/plastic_memories_decompiled")
    parser.add_argument("--output", default="resources/shiro_persona_sft/raw/limited_memory_ai/plastic_memories_isla.jsonl")
    parser.add_argument("--report", default="data/shiro_persona_sft/plastic_memories_isla.report.json")
    parser.add_argument("--identity", default="白")
    parser.add_argument("--context-turns", type=int, default=3)
    parser.add_argument("--max-records", type=int, default=1200)
    parser.add_argument("--decompile-limit", type=int, default=0, help="0 means all files.")
    parser.add_argument("--keep-fact-rows", action="store_true")
    args = parser.parse_args()

    scenario_dir = Path(args.scenario_dir)
    freemote = Path(args.freemote) if args.freemote else None
    decompiled_dir = Path(args.decompiled_dir)
    decompile_scenarios(
        scenario_dir,
        decompiled_dir,
        freemote,
        limit=args.decompile_limit,
    )
    report = build_dataset(
        decompiled_dir,
        Path(args.output),
        Path(args.report),
        identity=args.identity,
        context_turns=args.context_turns,
        max_records=args.max_records,
        keep_fact_rows=args.keep_fact_rows,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
