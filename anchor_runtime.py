import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_MAX_ANCHOR_CHARS = 900


def anchor_candidates_for_skill(skill_file: Optional[str]) -> List[Path]:
    if not skill_file:
        return []
    skill_path = Path(skill_file).expanduser()
    base = skill_path.parent if skill_path.suffix.lower() == ".md" else skill_path
    return [
        base / "anchors" / "anchors.jsonl",
        base / "anchors" / "anchors.json",
        base / "ANCHORS.jsonl",
        base / "ANCHORS.json",
    ]


def discover_anchor_file(skill_file: Optional[str]) -> Optional[Path]:
    for candidate in anchor_candidates_for_skill(skill_file):
        if candidate.exists():
            return candidate
    return None


def _load_jsonl(path: Path) -> List[Dict]:
    anchors = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                anchors.append(item)
    return anchors


def _load_json(path: Path) -> List[Dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("anchors", [])
    return [item for item in data if isinstance(item, dict)]


def load_anchor_bank(skill_file: Optional[str], limit: int = 500) -> List[Dict]:
    path = discover_anchor_file(skill_file)
    if path is None:
        return []
    try:
        anchors = _load_jsonl(path) if path.suffix.lower() == ".jsonl" else _load_json(path)
    except Exception:
        return []
    normalized = []
    for anchor in anchors[:limit]:
        if not anchor.get("id"):
            continue
        anchor = dict(anchor)
        anchor["_anchor_file"] = str(path)
        normalized.append(anchor)
    return normalized


def _current_block_kind(schedule: Optional[Dict]) -> str:
    if not schedule:
        return ""
    today = datetime.now().astimezone().date().isoformat()
    current_minute = datetime.now().astimezone().hour * 60 + datetime.now().astimezone().minute
    for day in schedule.get("days", []):
        if day.get("date") != today:
            continue
        for block in day.get("blocks", []):
            try:
                start_h, start_m = str(block.get("start", "00:00")).split(":", 1)
                end_h, end_m = str(block.get("end", "00:00")).split(":", 1)
                start = int(start_h) * 60 + int(start_m)
                end = int(end_h) * 60 + int(end_m)
            except Exception:
                continue
            if start <= current_minute < end:
                return str(block.get("kind") or "")
    return ""


def _score_anchor(anchor: Dict, block_kind: str, user_text: str) -> int:
    score = int(anchor.get("priority", 0) or 0)
    time_blocks = set(anchor.get("time_blocks") or [])
    tags = set(anchor.get("tags") or [])
    dimensions = set(anchor.get("persona_dimensions") or [])
    text = user_text or ""

    if block_kind and block_kind in time_blocks:
        score += 8
    if block_kind and block_kind in tags:
        score += 4
    if any(word in text for word in ["训练", "レッスン", "舞台", "live", "ライブ", "偶像", "アイドル"]):
        score += 5 if {"ambition", "discipline", "idol_training"} & (tags | dimensions | time_blocks) else 0
    if any(word in text for word in ["专业", "解释", "代码", "论文", "技术", "研究", "どういう", "what is"]):
        score += 5 if {"identity", "autonomy", "persona_boundary"} & (tags | dimensions) else 0
    if any(word in text for word in ["累", "睡", "休息", "おやすみ", "疲"]):
        score += 4 if {"rest", "sleepiness", "care"} & (tags | dimensions | time_blocks) else 0
    if any(word in text for word in ["你是谁", "人设", "人格", "角色", "identity", "persona"]):
        score += 6 if {"identity", "autonomy"} & (tags | dimensions) else 0
    return score


def select_anchor(
    anchors: List[Dict],
    *,
    schedule: Optional[Dict] = None,
    user_text: str = "",
    session_id: str = "default",
) -> Optional[Dict]:
    if not anchors:
        return None
    block_kind = _current_block_kind(schedule)
    scored = [(_score_anchor(anchor, block_kind, user_text), anchor) for anchor in anchors]
    scored.sort(key=lambda item: (item[0], str(item[1].get("id"))), reverse=True)
    top_score = scored[0][0]
    pool = [anchor for score, anchor in scored if score >= top_score - 2][:12]
    today = datetime.now().astimezone().date().isoformat()
    raw = f"{session_id}|{today}|{block_kind}|{user_text[:80]}".encode("utf-8", errors="ignore")
    index = int(hashlib.sha256(raw).hexdigest()[:8], 16) % len(pool)
    return pool[index]


def render_anchor_context(anchor: Optional[Dict], max_chars: int = DEFAULT_MAX_ANCHOR_CHARS) -> str:
    if not anchor:
        return ""
    lines = [
        "【Persona Anchor Replay】",
        "以下は公式/検証済み資料から抽出された人格アンカー。これは新しい出来事やユーザーとの記憶ではなく、人格の自己校正用コンテキストとしてのみ使う。",
        f"- anchor_id: {anchor.get('id')}",
        f"- source: {anchor.get('source_file') or anchor.get('source_id') or anchor.get('_anchor_file')}",
    ]
    title = anchor.get("title")
    if title:
        lines.append(f"- scene: {title}")
    dimensions = ", ".join(anchor.get("persona_dimensions") or anchor.get("tags") or [])
    if dimensions:
        lines.append(f"- persona_dimensions: {dimensions}")
    summary = anchor.get("summary")
    if summary:
        lines.append(f"- summary: {summary}")
    quotes = anchor.get("evidence_quotes") or anchor.get("quotes") or []
    if quotes:
        lines.append("- short_evidence:")
        for quote in quotes[:2]:
            if isinstance(quote, dict):
                jp = str(quote.get("ja") or "").strip()
                zh = str(quote.get("zh") or "").strip()
                quote_text = f"{jp} / {zh}".strip(" /")
            else:
                quote_text = str(quote).strip()
            if quote_text:
                lines.append(f"  - {quote_text[:140]}")
    lines.append("このアンカーは口調・判断・関係姿勢を保つための補助であり、ユーザーの現在発話への回答義務を上書きしない。")
    text = "\n".join(lines)
    return text[:max_chars]
