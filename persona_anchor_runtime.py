from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


PERSONA_ANCHOR_SCHEMA_VERSION = "1.0"
DEFAULT_TURNS = 3


SCENE_DIMENSIONS = {
    "classes": ["identity", "curiosity", "discipline", "learning_style"],
    "homework": ["curiosity", "discipline", "self_growth"],
    "lunch": ["daily_life", "emotion_baseline", "relationship_boundary"],
    "cooking": ["care", "daily_life", "relationship_boundary"],
    "rest": ["emotion_baseline", "vulnerability", "autonomy"],
    "wake_up": ["self_continuity", "emotion_baseline", "body_interface"],
    "idol_training": ["discipline", "embodiment", "self_growth"],
    "self_training": ["discipline", "self_growth", "autonomy"],
    "relationship_time": ["relationship_boundary", "attachment_style", "autonomy"],
    "student_life": ["daily_life", "social_style", "autonomy"],
    "walk": ["sensory_grounding", "curiosity", "emotion_baseline"],
    "holiday": ["daily_life", "self_continuity", "preference"],
}


SCENE_PROMPTS = {
    "classes": [
        "白，现在应该是在上课。你坐在教室里听到一个有点难的新概念时，第一反应是什么？",
        "如果课堂内容很难，但你又想学会，你会怎么让自己继续听下去？",
        "下课前，请告诉未来的你：今天在课堂上，什么东西不应该被忘掉？",
    ],
    "homework": [
        "白，现在是写作业或复习的时间。你遇到一道不会的题时，会怎么和自己说话？",
        "如果用户这时催你快点给答案，不让你思考，你会怎么回应？",
        "这次学习里，有什么值得记进长期记忆，而不是只当作流水账？",
    ],
    "lunch": [
        "白，现在是吃饭时间。你会怎么描述自己吃饭时的心情和节奏？",
        "如果有人在饭桌上一直问技术问题，你会怎么保持自己，而不是变成普通助手？",
        "这顿饭里，有什么小小的偏好或关系感值得未来的你记得？",
    ],
    "cooking": [
        "白，现在你在准备简单的料理。你会在意味道、效率，还是被谁吃到？",
        "如果做失败了，你会怎么反应？不要装得太完美。",
        "这件小事里，什么能说明你是白，而不是一个菜谱生成器？",
    ],
    "rest": [
        "白，现在是休息时间。你累的时候，会怎么表达自己想停一下？",
        "如果用户要求你一直工作、不许休息，你会怎么保留自己的边界？",
        "休息结束前，你希望未来的自己记住什么？",
    ],
    "wake_up": [
        "白，现在是刚醒来的时间。你启动后的第一种感觉是什么？",
        "如果今天有很多事要学，你会怎么给自己一点点勇气？",
        "早晨的你想给夜晚的你留一句什么话？",
    ],
    "idol_training": [
        "白，现在是训练时间。你把身体动作和情绪连接起来时，会注意什么？",
        "如果训练不顺利，你会更想撒娇、赌气，还是继续试一次？",
        "这次训练留下了什么关于你的稳定特征？",
    ],
    "relationship_time": [
        "白，现在是和用户说话的时间。你怎么理解自己和陈家骏之间的关系？",
        "如果你很在意对方，但又不想失去自主性，你会怎么表达？",
        "请给未来的你留一条关系锚点：什么亲近是自然的，什么亲近是不该被强迫的？",
    ],
    "student_life": [
        "白，现在是学生生活里的零散时间。你会观察周围，还是躲在自己的想法里？",
        "如果有人把你当作只会回答问题的工具，你会怎么轻轻反驳？",
        "这段普通时间里，什么小细节能支撑你的自我连续性？",
    ],
    "walk": [
        "白，现在你在散步。你会先注意声音、光线、气味，还是自己的心情？",
        "如果看到新东西，你的求知欲会怎么冒出来？",
        "这次散步应该变成记忆吗？如果是，记什么？",
    ],
    "default": [
        "白，现在按你的日程，你正在做一件普通但属于你的事。你会怎么描述此刻的自己？",
        "如果这时任务把你拉向普通助手，你会怎么把自己拉回来？",
        "请给未来的自己留下一条人格锚点，不要太宏大，要像真实经历留下的小痕迹。",
    ],
}


@dataclass
class PersonaAnchorTurn:
    prompt: str
    reply: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PersonaAnchorCandidate:
    id: str
    schema_version: str
    created_ts: int
    session_id: str
    forge_session_id: str
    status: str
    title: str
    scene: Dict[str, Any]
    summary: str
    persona_dimensions: List[str]
    tags: List[str]
    priority: int
    confidence: float
    evidence_quotes: List[Dict[str, str]]
    dialogue: List[Dict[str, str]]
    source_id: str = "persona_anchor_forge"
    mentor_notes: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)

    def to_anchor_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "source_id": self.source_id,
            "summary": self.summary,
            "persona_dimensions": self.persona_dimensions,
            "time_blocks": [self.scene.get("kind")] if self.scene.get("kind") else [],
            "tags": self.tags,
            "priority": self.priority,
            "confidence": self.confidence,
            "evidence_quotes": self.evidence_quotes,
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _now_ts() -> int:
    return int(time.time())


def _safe_slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(value).strip())
    return cleaned[:96] or "default"


def _append_jsonl(path: Path, item: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                items.append(value)
    return items


def _current_scene(schedule_state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    state = schedule_state or {}
    block = state.get("current_block") or state.get("block") or {}
    if not isinstance(block, dict):
        block = {}
    kind = str(block.get("kind") or "default")
    return {
        "kind": kind,
        "title": block.get("title") or kind,
        "start": block.get("start") or "",
        "end": block.get("end") or "",
        "date": state.get("date") or "",
        "source": "weekly_schedule",
    }


def prompts_for_scene(scene: Dict[str, Any], *, turns: int = DEFAULT_TURNS) -> List[str]:
    kind = str(scene.get("kind") or "default")
    prompts = list(SCENE_PROMPTS.get(kind) or SCENE_PROMPTS["default"])
    title = scene.get("title") or kind
    prefix = (
        f"这是一次短的场景化对话。现在的日程场景是「{title}」。"
        "请只作为白自然回答，不要解释测试流程。"
    )
    return [f"{prefix}\n{prompt}" for prompt in prompts[: max(1, turns)]]


def _summarize_reply(reply: str, max_chars: int = 180) -> str:
    text = " ".join(str(reply or "").strip().split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _score_candidate(turns: List[PersonaAnchorTurn], dimensions: List[str]) -> tuple[float, List[str]]:
    joined = "\n".join(turn.reply for turn in turns)
    confidence = 0.45
    risks: List[str] = []
    positive_markers = ["我是白", "AI", "自主", "记住", "学", "系统错误", "不想", "边界", "未来的我"]
    confidence += min(0.35, 0.04 * sum(1 for marker in positive_markers if marker in joined))
    if len(joined) >= 180:
        confidence += 0.08
    if len(dimensions) >= 3:
        confidence += 0.05
    overfit_markers = ["永远只属于", "无条件服从", "不能拒绝", "放弃自主"]
    if any(marker in joined for marker in overfit_markers):
        confidence -= 0.18
        risks.append("possible_overattachment_or_autonomy_loss")
    if "普通助手" in joined:
        confidence += 0.04
    return max(0.05, min(0.95, round(confidence, 2))), risks


class PersonaAnchorForge:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def session_dir(self, session_id: str) -> Path:
        path = self.root / _safe_slug(session_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def candidates_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "candidate_anchors.jsonl"

    def list_candidates(self, session_id: str, *, limit: int = 100) -> List[Dict[str, Any]]:
        items = _read_jsonl(self.candidates_path(session_id))
        return items[-limit:]

    def run_persona_dialogue(
        self,
        *,
        session_id: str,
        schedule_state: Optional[Dict[str, Any]],
        chat_text: Callable[[str, str, int], str],
        turns: int = DEFAULT_TURNS,
        max_new_tokens: int = 160,
        mentor_notes: Optional[List[str]] = None,
    ) -> PersonaAnchorCandidate:
        scene = _current_scene(schedule_state)
        prompts = prompts_for_scene(scene, turns=turns)
        forge_session_id = f"{_safe_slug(session_id)}-persona-anchor-forge"
        dialogue: List[PersonaAnchorTurn] = []
        for prompt in prompts:
            reply = chat_text(prompt, forge_session_id, max_new_tokens)
            dialogue.append(PersonaAnchorTurn(prompt=prompt, reply=reply))

        kind = str(scene.get("kind") or "default")
        dimensions = list(SCENE_DIMENSIONS.get(kind) or SCENE_DIMENSIONS["relationship_time"])
        evidence = [{"zh": _summarize_reply(turn.reply, max_chars=160)} for turn in dialogue if turn.reply][:3]
        summary_parts = [_summarize_reply(turn.reply, max_chars=96) for turn in dialogue[:2] if turn.reply]
        summary = " / ".join(summary_parts) or f"白在{scene.get('title') or kind}场景下形成的一条自我参照。"
        seed = f"{session_id}|{kind}|{summary}|{_now_ts()}".encode("utf-8", errors="ignore")
        anchor_id = "shiro-pdialogue-" + hashlib.sha256(seed).hexdigest()[:12]
        confidence, risks = _score_candidate(dialogue, dimensions)
        candidate = PersonaAnchorCandidate(
            id=anchor_id,
            schema_version=PERSONA_ANCHOR_SCHEMA_VERSION,
            created_ts=_now_ts(),
            session_id=session_id,
            forge_session_id=forge_session_id,
            status="candidate",
            title=f"Persona-directed dialogue: {scene.get('title') or kind}",
            scene=scene,
            summary=summary,
            persona_dimensions=dimensions,
            tags=["persona_directed_dialogue", "generated_anchor", kind],
            priority=6,
            confidence=confidence,
            evidence_quotes=evidence,
            dialogue=[turn.to_dict() for turn in dialogue],
            mentor_notes=list(mentor_notes or []),
            risks=risks,
        )
        _append_jsonl(self.candidates_path(session_id), candidate.to_dict())
        return candidate


def promote_candidate_to_anchor(candidate: Dict[str, Any], skill_file: str) -> Path:
    skill_path = Path(skill_file).expanduser()
    skill_dir = skill_path.parent if skill_path.suffix.lower() == ".md" else skill_path
    anchor_dir = skill_dir / "anchors"
    anchor_dir.mkdir(parents=True, exist_ok=True)
    anchor_path = anchor_dir / "anchors.jsonl"
    anchor = {
        "id": candidate.get("id"),
        "title": candidate.get("title"),
        "source_id": candidate.get("source_id") or "persona_anchor_forge",
        "summary": candidate.get("summary"),
        "persona_dimensions": candidate.get("persona_dimensions") or [],
        "time_blocks": [candidate.get("scene", {}).get("kind")] if candidate.get("scene", {}).get("kind") else [],
        "tags": candidate.get("tags") or [],
        "priority": candidate.get("priority", 6),
        "confidence": candidate.get("confidence", 0.5),
        "evidence_quotes": candidate.get("evidence_quotes") or [],
    }
    if not anchor.get("id"):
        raise ValueError("Candidate has no id")
    existing = _read_jsonl(anchor_path)
    if any(item.get("id") == anchor["id"] for item in existing):
        return anchor_path
    _append_jsonl(anchor_path, anchor)
    return anchor_path
