import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set


def _prepare_windows_faiss_dll_path():
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return

    candidate_dirs = [
        Path(sys.prefix) / "Lib" / "site-packages" / "faiss_cpu.libs",
        Path(sys.base_prefix) / "Lib" / "site-packages" / "faiss_cpu.libs",
    ]

    for candidate in candidate_dirs:
        if candidate.exists():
            try:
                os.add_dll_directory(str(candidate))
            except Exception:
                pass


try:
    _prepare_windows_faiss_dll_path()
    import faiss
except Exception:
    faiss = None

try:
    import numpy as np
except Exception:
    np = None

try:
    from sentence_transformers import CrossEncoder, SentenceTransformer
except Exception:
    CrossEncoder = None
    SentenceTransformer = None


PROFILE_SLOT_LABELS = {
    "name": "名字",
    "nickname": "称呼偏好",
    "likes": "喜欢",
    "dislikes": "不喜欢",
    "identity": "身份",
    "goals": "目标",
    "projects": "项目",
    "habits": "习惯",
    "current_state": "当前状态",
}

PROFILE_SLOT_PRIORITIES = {
    "name": 1.00,
    "nickname": 0.90,
    "current_state": 0.88,
    "likes": 0.82,
    "dislikes": 0.78,
    "identity": 0.72,
    "goals": 0.68,
    "projects": 0.64,
    "habits": 0.56,
}

RELATION_TO_PROFILE_SLOT = {label: slot for slot, label in PROFILE_SLOT_LABELS.items()}
SINGLE_VALUE_RELATIONS = {"名字", "称呼偏好", "身份", "当前状态"}
CHARACTER_QUERY_KEYWORDS = ("角色",)
STATE_KEYWORDS = (
    "累",
    "困",
    "难受",
    "不舒服",
    "紧张",
    "开心",
    "高兴",
    "低落",
    "烦",
    "忙",
    "疲惫",
)
MEMORY_WRITE_THRESHOLDS = {
    "profile_candidates": 0.68,
    "graph_facts": 0.72,
    "episodic_candidates": 0.58,
}
REFLECTION_MIN_ACTIVE_MEMORIES = 3
REFLECTION_MAX_LINKED_MEMORIES = 6
EPISODIC_STALE_DAYS = 90
EPISODIC_ARCHIVE_DAYS = 120
PREFERENCE_STALE_DAYS = 180
LOW_CONFIDENCE_THRESHOLD = 0.42
REINFORCEMENT_MAX_SCORE = 1.0
REINFORCEMENT_CONTEXT_AMOUNT = 0.06
AMEM_EVOLUTION_MAX_EVENTS = 8
AMEM_EVOLUTION_SCORE_THRESHOLD = 0.10
AMEM_TOPIC_MAX_LABELS = 8
AMEM_RETRIEVAL_ALIAS_MAX = 8


MISUZU_KNOWLEDGE_SEED = []


def now_ts() -> int:
    return int(time.time())


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())


def parse_memory_time(value) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return int(time.mktime(time.strptime(text[:25], fmt)))
        except Exception:
            continue
    return None


def memory_age_days(memory: Dict[str, Any], reference_ts: Optional[int] = None) -> float:
    reference_ts = reference_ts or now_ts()
    timestamp = parse_memory_time(memory.get("timestamp")) or parse_memory_time(memory.get("valid_from"))
    if not timestamp:
        return 0.0
    return max(0.0, (reference_ts - int(timestamp)) / 86400.0)


def normalize_reinforcement_score(value) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 0.0
    return max(0.0, min(REINFORCEMENT_MAX_SCORE, score))


def normalize_use_count(value) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def memory_reinforcement_bonus(memory: Dict[str, Any]) -> float:
    score = normalize_reinforcement_score(memory.get("reinforcement_score", 0.0))
    use_count = normalize_use_count(memory.get("use_count", 0))
    usage_bonus = min(0.045, 0.014 * math.log1p(use_count))
    recent_use_bonus = 0.55 * recency_bonus(memory.get("last_used_at"), horizon_days=14.0)
    return min(0.12, 0.075 * score + usage_bonus + recent_use_bonus)


MEMORY_SOURCE_ALIASES = {
    "conversation": "chat",
    "chat": "chat",
    "image": "image",
    "manual": "manual",
    "imported_reference": "imported_reference",
    "skill": "skill",
    "system": "system",
    "summary": "system",
}


MEMORY_TYPE_ALIASES = {
    "episodic": "episodic",
    "event": "episodic",
    "preference": "preference",
    "profile": "preference",
    "relationship": "relationship",
    "boundary": "boundary",
    "character_fact": "character_fact",
    "task_state": "task_state",
    "summary": "summary",
}

MEMORY_LAYER_ALIASES = {
    "short": "short_term",
    "short_term": "short_term",
    "mid": "mid_term",
    "mid_term": "mid_term",
    "long": "long_term",
    "long_term": "long_term",
    "graph": "graph",
    "contradiction": "contradiction_graph",
    "contradiction_graph": "contradiction_graph",
    "reflection": "reflection_notes",
    "reflection_notes": "reflection_notes",
}


def normalize_memory_source(source: str) -> str:
    key = str(source or "conversation").strip().lower()
    return MEMORY_SOURCE_ALIASES.get(key, "chat")


def infer_memory_type(category: str, metadata: Dict[str, Any]) -> str:
    explicit = metadata.get("memory_type")
    if explicit in MEMORY_TYPE_ALIASES.values():
        return explicit
    key = str(category or "episodic").strip().lower()
    return MEMORY_TYPE_ALIASES.get(key, "episodic")


def infer_memory_scope(memory_type: str, source: str, metadata: Dict[str, Any]) -> str:
    explicit = metadata.get("scope")
    if explicit in {"user_personalization", "character_canon", "relationship_context", "system_runtime"}:
        return explicit
    if memory_type == "character_fact" or source == "skill":
        return "character_canon"
    if memory_type in {"relationship", "episodic", "summary", "boundary"}:
        return "relationship_context"
    if memory_type == "task_state" or source == "system":
        return "system_runtime"
    return "user_personalization"


def infer_memory_layer(memory_type: str, source: str, metadata: Dict[str, Any], tags: Optional[List[str]] = None) -> str:
    explicit = metadata.get("memory_layer") or metadata.get("layer")
    if explicit:
        normalized = MEMORY_LAYER_ALIASES.get(str(explicit).strip().lower())
        if normalized:
            return normalized

    source_key = normalize_memory_source(source)
    tag_set = {str(tag).strip().lower() for tag in (tags or [])}
    if source_key == "system" and ("reflection" in tag_set or "relationship_summary" in tag_set):
        return "reflection_notes"
    if source in {"reflection", "summary_buffer", "context_compression"}:
        if source == "reflection" or "reflection" in tag_set:
            return "reflection_notes"
        return "mid_term"
    if memory_type == "summary":
        return "reflection_notes" if "reflection" in tag_set else "mid_term"
    if memory_type == "task_state":
        return "mid_term"
    return "long_term"


def normalize_memory_evidence(metadata: Dict[str, Any], source: str) -> List[str]:
    evidence = metadata.get("evidence")
    if isinstance(evidence, list):
        return [str(item) for item in evidence if str(item).strip()]
    if isinstance(evidence, str) and evidence.strip():
        return [evidence.strip()]
    return [f"source:{source}"]


def normalize_memory_confidence(metadata: Dict[str, Any]) -> float:
    try:
        value = float(metadata.get("confidence", 0.65))
    except (TypeError, ValueError):
        value = 0.65
    return max(0.0, min(1.0, value))


def normalize_memory_refs(values) -> List[int]:
    if values is None:
        return []
    if isinstance(values, str):
        parts = re.split(r"[,，\s]+", values)
    elif isinstance(values, (list, tuple, set)):
        parts = list(values)
    else:
        parts = [values]
    refs: List[int] = []
    for item in parts:
        try:
            ref = int(str(item).strip().lstrip("#"))
        except (TypeError, ValueError):
            continue
        if ref > 0 and ref not in refs:
            refs.append(ref)
    return refs


def normalize_memory_evidence_list(values) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        parts = [line.strip() for line in values.replace("；", ";").split(";")]
    elif isinstance(values, (list, tuple, set)):
        parts = [str(item).strip() for item in values]
    else:
        parts = [str(values).strip()]
    return [item for item in parts if item]


def load_json_file(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json_file(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_for_match(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def text_to_terms(text: str) -> Set[str]:
    text = normalize_for_match(text)
    groups = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text)
    terms: Set[str] = set()
    for group in groups:
        if re.fullmatch(r"[\u4e00-\u9fff]+", group):
            for ch in group:
                terms.add(ch)
            if len(group) >= 2:
                for i in range(len(group) - 1):
                    terms.add(group[i:i + 2])
        else:
            terms.add(group)
    return {t for t in terms if t}


def lexical_score(query: str, text: str) -> float:
    q_terms = text_to_terms(query)
    d_terms = text_to_terms(text)
    if not q_terms or not d_terms:
        return 0.0
    overlap = len(q_terms & d_terms)
    if overlap == 0:
        return 0.0
    precision = overlap / len(d_terms)
    recall = overlap / len(q_terms)
    return (2 * precision * recall) / (precision + recall + 1e-8)


CONTRADICTION_CUE_MARKERS = (
    "correction",
    "correcting",
    "actually",
    "i was wrong",
    "was wrong",
    "no longer",
    "not anymore",
    "anymore",
    "instead",
    "rather than",
    "不是",
    "并不是",
    "不再",
    "更正",
    "纠正",
    "其实",
    "改成",
    "说错",
    "错了",
    "而是",
    "ではなく",
    "じゃなく",
    "違う",
    "訂正",
    "実は",
)


def has_contradiction_cue(text: str) -> bool:
    normalized = normalize_for_match(text)
    return any(marker in normalized for marker in CONTRADICTION_CUE_MARKERS)


def append_unique_texts(current, additions) -> List[str]:
    merged: List[str] = []
    seen: Set[str] = set()
    for item in normalize_memory_evidence_list(current) + normalize_memory_evidence_list(additions):
        key = normalize_for_match(item)
        if key and key not in seen:
            seen.add(key)
            merged.append(item)
    return merged


def append_reason(current: str, addition: str) -> str:
    current = (current or "").strip()
    addition = (addition or "").strip()
    if not current:
        return addition
    if not addition or addition in current:
        return current
    return f"{current} {addition}"


def detect_memory_contradictions(
    new_content: str,
    existing_memories: List[Dict],
    *,
    min_score: float = 0.12,
    max_results: int = 3,
) -> List[Dict[str, Any]]:
    new_content = (new_content or "").strip()
    if not new_content or not has_contradiction_cue(new_content):
        return []

    hits: List[Dict[str, Any]] = []
    for memory in existing_memories or []:
        if memory.get("status", "active") != "active":
            continue
        if memory.get("scope") == "character_canon" or memory.get("memory_type") == "character_fact":
            continue
        if memory.get("source_kind") in {"skill", "imported_reference"}:
            continue
        old_content = str(memory.get("content", "")).strip()
        if not old_content:
            continue
        if normalize_for_match(old_content) == normalize_for_match(new_content):
            continue

        score = lexical_score(new_content, old_content)
        if score < min_score:
            continue

        hits.append({
            "memory_id": int(memory.get("id", 0)),
            "score": round(float(score), 4),
            "confidence": max(0.18, min(0.5, float(score))),
            "reason": "auto_contradiction_detection: new memory contains a correction cue and overlaps with this active memory.",
            "evidence": [
                f"old_memory:{memory.get('id')}",
                f"new_text:{compact_text(new_content, 72)}",
            ],
            "memory": memory,
        })

    hits.sort(key=lambda item: item["score"], reverse=True)
    return hits[:max_results]


def detect_related_memory_links(
    new_content: str,
    new_tags: List[str],
    existing_memories: List[Dict],
    *,
    min_score: float = 0.10,
    max_results: int = 4,
) -> List[Dict[str, Any]]:
    new_content = (new_content or "").strip()
    if not new_content:
        return []
    tag_set = {normalize_for_match(tag) for tag in (new_tags or []) if str(tag).strip()}
    hits: List[Dict[str, Any]] = []
    for memory in existing_memories or []:
        if memory.get("status", "active") != "active":
            continue
        if is_protected_character_memory(memory):
            continue
        old_content = str(memory.get("content", "")).strip()
        if not old_content:
            continue
        if normalize_for_match(old_content) == normalize_for_match(new_content):
            continue

        score = lexical_score(new_content, old_content)
        old_tags = {normalize_for_match(tag) for tag in memory.get("tags", []) if str(tag).strip()}
        tag_overlap = len(tag_set & old_tags)
        if tag_overlap:
            score += min(0.12, 0.04 * tag_overlap)
        if score < min_score:
            continue

        hits.append({
            "memory_id": int(memory.get("id", 0)),
            "score": round(float(score), 4),
            "reason": "auto_memory_linking: new memory overlaps with this active memory.",
            "evidence": [
                f"old_memory:{memory.get('id')}",
                f"new_text:{compact_text(new_content, 72)}",
            ],
            "memory": memory,
        })

    hits.sort(key=lambda item: item["score"], reverse=True)
    return hits[:max_results]


def build_amem_evolution_interpretation(old_memory: Dict[str, Any], new_memory: Dict[str, Any]) -> str:
    old_text = compact_text(old_memory.get("content", ""), 72)
    new_text = compact_text(new_memory.get("content", ""), 72)
    old_type = old_memory.get("memory_type") or old_memory.get("category") or "memory"
    new_type = new_memory.get("memory_type") or new_memory.get("category") or "memory"
    return (
        f"A-Mem evolution: older {old_type} memory should now be interpreted together with "
        f"newer {new_type} memory #{new_memory.get('id')}. Older note: {old_text}. "
        f"New evidence/context: {new_text}."
    )


def _amem_label_candidates(memory: Dict[str, Any]) -> List[str]:
    candidates: List[str] = []
    for key in ("memory_type", "memory_layer", "category", "source_kind"):
        value = str(memory.get(key, "") or "").strip()
        if value:
            candidates.append(value)
    for tag in memory.get("tags", []) or []:
        value = str(tag or "").strip()
        if value:
            candidates.append(value)
    return candidates


def normalize_amem_labels(*memories: Dict[str, Any], limit: int = AMEM_TOPIC_MAX_LABELS) -> List[str]:
    labels: List[str] = []
    seen: Set[str] = set()
    for memory in memories:
        for value in _amem_label_candidates(memory):
            label = re.sub(r"\s+", "_", value.strip().lower())
            label = re.sub(r"[^0-9a-zA-Z_\-\u4e00-\u9fff\u3040-\u30ff]+", "", label)
            if not label:
                continue
            if label in {"chat", "conversation", "unknown", "none"}:
                continue
            if label not in seen:
                seen.add(label)
                labels.append(label)
            if len(labels) >= limit:
                return labels
    return labels


def build_amem_cluster_key(labels: List[str]) -> str:
    if not labels:
        return "general"
    return "::".join(labels[:3])


def build_amem_retrieval_aliases(
    old_memory: Dict[str, Any],
    new_memory: Dict[str, Any],
    labels: List[str],
) -> List[str]:
    aliases: List[str] = []
    aliases.extend(labels[:AMEM_RETRIEVAL_ALIAS_MAX])
    for memory in (old_memory, new_memory):
        text = compact_text(memory.get("content", ""), 56)
        if text:
            aliases.append(text)
    return append_unique_texts([], aliases)[:AMEM_RETRIEVAL_ALIAS_MAX]


def build_amem_structured_note(
    old_memory: Dict[str, Any],
    new_memory: Dict[str, Any],
    score: float,
) -> Dict[str, Any]:
    labels = normalize_amem_labels(old_memory, new_memory)
    old_type = old_memory.get("memory_type") or old_memory.get("category") or "memory"
    new_type = new_memory.get("memory_type") or new_memory.get("category") or "memory"
    relationship_strength = max(0.0, min(1.0, float(score or 0.0)))
    stability = "stable" if relationship_strength >= 0.34 else "tentative"
    if old_memory.get("memory_type") in {"preference", "relationship"}:
        stability = "stable" if relationship_strength >= 0.22 else stability

    return {
        "cluster_key": build_amem_cluster_key(labels),
        "topic_labels": labels,
        "relationship_strength": round(relationship_strength, 4),
        "stability": stability,
        "retrieval_aliases": build_amem_retrieval_aliases(old_memory, new_memory, labels),
        "interpretation_delta": (
            f"New {new_type} memory #{new_memory.get('id')} should refine older {old_type} memory "
            f"#{old_memory.get('id')} instead of replacing it."
        ),
        "evolution_summary": (
            f"{compact_text(old_memory.get('content', ''), 72)} | "
            f"updated_by #{new_memory.get('id')}: {compact_text(new_memory.get('content', ''), 72)}"
        ),
    }


def append_amem_evolution_event(
    old_memory: Dict[str, Any],
    new_memory: Dict[str, Any],
    link_hit: Optional[Dict[str, Any]] = None,
) -> bool:
    if is_protected_character_memory(old_memory):
        return False
    if old_memory.get("status", "active") != "active":
        return False
    old_id = int(old_memory.get("id", 0))
    new_id = int(new_memory.get("id", 0))
    if old_id <= 0 or new_id <= 0 or old_id == new_id:
        return False

    metadata = old_memory.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    amem = metadata.get("amem")
    if not isinstance(amem, dict):
        amem = {}
    events = amem.get("evolution_events")
    if not isinstance(events, list):
        events = []
    if any(int(event.get("new_memory_id", 0)) == new_id for event in events if isinstance(event, dict)):
        return False

    score = float((link_hit or {}).get("score", 0.0) or 0.0)
    note = build_amem_structured_note(old_memory, new_memory, score)
    event = {
        "at": now_ts(),
        "new_memory_id": new_id,
        "score": round(score, 4),
        "reason": "amem_old_memory_evolution: newer linked memory refined the interpretation of this older memory.",
        "new_memory_type": new_memory.get("memory_type"),
        "new_memory_layer": new_memory.get("memory_layer"),
        "new_memory_tags": list(new_memory.get("tags", []))[:8],
        "new_memory_excerpt": compact_text(new_memory.get("content", ""), 96),
        "topic_labels": note["topic_labels"],
        "cluster_key": note["cluster_key"],
        "relationship_strength": note["relationship_strength"],
        "interpretation_delta": note["interpretation_delta"],
    }
    events.append(event)
    amem["evolution_events"] = events[-AMEM_EVOLUTION_MAX_EVENTS:]
    amem["evolved_by"] = normalize_memory_refs(amem.get("evolved_by", [])) + [new_id]
    amem["evolved_by"] = normalize_memory_refs(amem["evolved_by"])[-AMEM_EVOLUTION_MAX_EVENTS:]
    amem["last_evolved_at"] = event["at"]
    amem["current_interpretation"] = build_amem_evolution_interpretation(old_memory, new_memory)
    amem["cluster_key"] = note["cluster_key"]
    amem["topic_labels"] = note["topic_labels"]
    amem["relationship_strength"] = note["relationship_strength"]
    amem["stability"] = note["stability"]
    amem["retrieval_aliases"] = note["retrieval_aliases"]
    amem["evolution_summary"] = note["evolution_summary"]
    amem["policy"] = "non_destructive_metadata_only"
    metadata["amem"] = amem
    metadata["last_evolution_reason"] = event["reason"]
    old_memory["metadata"] = metadata
    old_memory["evidence"] = append_unique_texts(
        old_memory.get("evidence"),
        [f"amem_evolved_by:{new_id}"],
    )
    old_memory["reinforcement_score"] = normalize_reinforcement_score(
        normalize_reinforcement_score(old_memory.get("reinforcement_score", 0.0)) + min(0.08, 0.02 + score * 0.10)
    )
    return True


def is_protected_character_memory(memory: Dict[str, Any]) -> bool:
    return (
        memory.get("scope") == "character_canon"
        or memory.get("memory_type") == "character_fact"
        or memory.get("source_kind") in {"skill", "imported_reference"}
    )


def reflection_signature(memories: List[Dict]) -> str:
    ids = [str(memory.get("id")) for memory in memories if memory.get("id") is not None]
    return "reflection:" + ",".join(ids)


def memory_decay_update(memory: Dict[str, Any], reference_ts: Optional[int] = None) -> Optional[Dict[str, Any]]:
    if is_protected_character_memory(memory):
        return None
    status = memory.get("status", "active")
    memory_type = str(memory.get("memory_type", memory.get("category", "episodic")))
    confidence = float(memory.get("confidence", 0.65))
    importance = int(memory.get("importance", 3))
    age_days = memory_age_days(memory, reference_ts=reference_ts)
    is_reinforced = (
        normalize_use_count(memory.get("use_count", 0)) >= 3
        or normalize_reinforcement_score(memory.get("reinforcement_score", 0.0)) >= 0.18
    )

    valid_until_ts = parse_memory_time(memory.get("valid_until"))
    if status == "active" and valid_until_ts is not None and valid_until_ts < (reference_ts or now_ts()):
        return {
            "status": "stale",
            "confidence": min(confidence, 0.35),
            "reason": append_reason(memory.get("reason", ""), "Memory maintenance: valid_until has passed."),
            "evidence": append_unique_texts(memory.get("evidence"), ["maintenance:valid_until_expired"]),
        }

    if status == "active" and memory_type in {"episodic", "summary"}:
        if is_reinforced:
            return None
        if importance <= 1 and confidence <= LOW_CONFIDENCE_THRESHOLD and age_days >= EPISODIC_ARCHIVE_DAYS:
            return {
                "status": "archived",
                "confidence": min(confidence, 0.28),
                "reason": append_reason(memory.get("reason", ""), "Memory maintenance: low-confidence old episodic detail archived."),
                "evidence": append_unique_texts(memory.get("evidence"), [f"maintenance:age_days:{age_days:.1f}"]),
            }
        if importance <= 2 and confidence <= 0.55 and age_days >= EPISODIC_STALE_DAYS:
            return {
                "status": "stale",
                "confidence": min(confidence, 0.4),
                "reason": append_reason(memory.get("reason", ""), "Memory maintenance: old low-value episodic detail marked stale."),
                "evidence": append_unique_texts(memory.get("evidence"), [f"maintenance:age_days:{age_days:.1f}"]),
            }

    if status == "active" and memory_type == "preference":
        if is_reinforced:
            return None
        if confidence <= LOW_CONFIDENCE_THRESHOLD and age_days >= PREFERENCE_STALE_DAYS:
            return {
                "status": "stale",
                "confidence": min(confidence, 0.4),
                "reason": append_reason(memory.get("reason", ""), "Memory maintenance: weak preference became stale with age."),
                "evidence": append_unique_texts(memory.get("evidence"), [f"maintenance:age_days:{age_days:.1f}"]),
            }

    if status == "contradicted" and not memory.get("valid_until"):
        return {
            "valid_until": now_iso(),
            "reason": append_reason(memory.get("reason", ""), "Memory maintenance: contradicted memory validity was closed."),
            "evidence": append_unique_texts(memory.get("evidence"), ["maintenance:contradiction_review"]),
        }

    return None


def memory_lifecycle_view(memory: Dict[str, Any], reference_ts: Optional[int] = None) -> Dict[str, Any]:
    reference_ts = reference_ts or now_ts()
    status = str(memory.get("status", "active"))
    age_days = round(memory_age_days(memory, reference_ts=reference_ts), 2)
    protected = is_protected_character_memory(memory)
    use_count = normalize_use_count(memory.get("use_count", 0))
    reinforcement_score = normalize_reinforcement_score(memory.get("reinforcement_score", 0.0))
    reinforced = use_count >= 3 or reinforcement_score >= 0.18
    pending_decay = memory_decay_update(memory, reference_ts=reference_ts)
    valid_until_ts = parse_memory_time(memory.get("valid_until"))

    explanations = []
    if protected:
        explanations.append("Protected character/skill/reference memory; automatic decay and user-memory linking are blocked.")
    if reinforced:
        explanations.append("Repeated contextual use protects this memory from low-value aging decay.")
    if use_count > 0:
        explanations.append(f"Used in generated context {use_count} time(s).")
    if memory.get("links"):
        explanations.append(f"Linked to {len(normalize_memory_refs(memory.get('links')))} related memory item(s).")
    metadata = memory.get("metadata")
    amem = metadata.get("amem") if isinstance(metadata, dict) else None
    amem_events = amem.get("evolution_events") if isinstance(amem, dict) else []
    if isinstance(amem_events, list) and amem_events:
        explanations.append(f"A-Mem evolution recorded {len(amem_events)} interpretation update(s).")
        if isinstance(amem, dict) and amem.get("stability"):
            explanations.append(f"A-Mem structured note stability is {amem.get('stability')}.")
    if memory.get("contradicts"):
        explanations.append("This memory contradicts older memory items.")
    if status == "contradicted":
        explanations.append("Marked as contradicted; excluded from normal retrieval.")
    elif status != "active":
        explanations.append(f"Marked as {status}; excluded from normal active retrieval.")
    if pending_decay:
        target_status = pending_decay.get("status", status)
        explanations.append(f"Next maintenance would update this memory toward {target_status}.")
    elif status == "active" and not protected:
        explanations.append("No lifecycle action is currently pending.")

    if protected:
        decay_risk = "protected"
    elif status != "active":
        decay_risk = "inactive"
    elif pending_decay:
        decay_risk = "pending"
    elif reinforced:
        decay_risk = "low"
    elif age_days >= EPISODIC_STALE_DAYS:
        decay_risk = "watch"
    else:
        decay_risk = "normal"

    valid_until_state = "none"
    if valid_until_ts is not None:
        valid_until_state = "expired" if valid_until_ts < reference_ts else "scheduled"

    return {
        "status": status,
        "age_days": age_days,
        "protected": protected,
        "reinforced": reinforced,
        "use_count": use_count,
        "reinforcement_score": round(reinforcement_score, 4),
        "last_used_at": memory.get("last_used_at"),
        "valid_until_state": valid_until_state,
        "decay_risk": decay_risk,
        "pending_decay": pending_decay or None,
        "amem_evolution_count": len(amem_events) if isinstance(amem_events, list) else 0,
        "amem_current_interpretation": amem.get("current_interpretation") if isinstance(amem, dict) else "",
        "amem_cluster_key": amem.get("cluster_key") if isinstance(amem, dict) else "",
        "amem_topic_labels": amem.get("topic_labels", []) if isinstance(amem, dict) else [],
        "amem_relationship_strength": amem.get("relationship_strength") if isinstance(amem, dict) else None,
        "amem_stability": amem.get("stability") if isinstance(amem, dict) else "",
        "explanations": explanations,
    }


def recency_bonus(timestamp: Optional[int], horizon_days: float = 30.0) -> float:
    if not timestamp:
        return 0.0
    age_seconds = max(0, now_ts() - int(timestamp))
    age_days = age_seconds / 86400.0
    return 0.08 * math.exp(-age_days / max(horizon_days, 1.0))


def compact_text(text: str, limit: int = 48) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def extract_profile_candidates(text: str) -> List[Dict]:
    text = (text or "").strip()
    if not text:
        return []

    patterns = [
        ("name", r"(?:我叫|我的名字是)([^，。！？\n]{1,20})", 0.95),
        ("nickname", r"(?:你可以叫我|以后叫我)([^，。！？\n]{1,20})", 0.92),
        ("likes", r"(?:我(?:更)?喜欢)([^，。！？\n]{1,32})", 0.78),
        ("dislikes", r"(?:我(?:不喜欢|讨厌))(?:吃)?([^，。！？\n]{1,32})", 0.80),
        ("identity", r"(?:我(?:现在)?是)([^，。！？\n]{1,32})", 0.72),
        ("goals", r"(?:我的目标是|我准备|我要做|我要考)([^，。！？\n]{1,48})", 0.72),
        ("projects", r"(?:我的项目是|我现在在做|我在训练|我在微调)([^，。！？\n]{1,64})", 0.82),
        ("habits", r"(?:我习惯|我平时会)([^，。！？\n]{1,48})", 0.65),
    ]

    results = []
    for slot, pattern, confidence in patterns:
        for match in re.finditer(pattern, text):
            value = match.group(1).strip(" ：:,.，。！？!？")
            if len(value) < 1:
                continue
            if slot == "identity" and value in {"有点累", "很困", "不舒服"}:
                continue
            results.append({
                "slot": slot,
                "value": value,
                "confidence": confidence,
                "source_text": text,
            })
    return results


def extract_long_term_candidates(user_text: str) -> List[Dict]:
    text = (user_text or "").strip()
    if not text:
        return []

    candidates = []
    explicit_patterns = ["记住", "别忘了", "以后都", "从现在开始", "你要记得"]
    if any(p in text for p in explicit_patterns):
        candidates.append({
            "content": text,
            "tags": ["显式记忆"],
            "importance": 5,
            "category": "episodic",
            "metadata": {"source_text": text},
        })

    project_markers = ["项目", "训练", "微调", "模型", "记忆系统", "RAG", "知识图谱"]
    if any(marker in text for marker in project_markers) and len(text) <= 80:
        candidates.append({
            "content": text,
            "tags": ["项目上下文"],
            "importance": 3,
            "category": "episodic",
            "metadata": {"source_text": text},
        })

    dedup = []
    seen = set()
    for item in candidates:
        key = (item["category"], normalize_for_match(item["content"]))
        if key in seen:
            continue
        seen.add(key)
        dedup.append(item)
    return dedup


def extract_user_state_candidates(text: str, user_subject: str = "制作人") -> List[Dict]:
    text = (text or "").strip()
    if not text:
        return []

    patterns = [
        r"我(?:今天|现在|这会儿|刚刚)?([^，。！？\n]{0,8}(?:累|困|难受|不舒服|紧张|开心|高兴|低落|烦|忙|疲惫)[^，。！？\n]{0,8})",
        r"(?:我的状态是|我现在状态是)([^，。！？\n]{1,20})",
    ]

    results = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            value = match.group(1).strip(" ：:,.，。！？!？")
            if not value:
                continue
            if not any(keyword in value for keyword in STATE_KEYWORDS):
                continue
            results.append({
                "subject": user_subject,
                "relation": "当前状态",
                "object": compact_text(value, 24),
                "tags": ["user_state"],
                "source": "conversation",
                "confidence": 0.78,
                "fact_type": "state",
            })
    return results


def extract_event_candidates(text: str) -> List[Dict]:
    text = (text or "").strip()
    if not text:
        return []

    event_markers = ["今天", "刚才", "刚刚", "昨天", "这周", "周末", "已经", "最近"]
    action_markers = ["去了", "做了", "吃了", "看了", "完成了", "开始", "继续", "推进", "测试", "部署", "写了"]
    if not text.startswith("我") and "我" not in text:
        return []
    if not any(marker in text for marker in event_markers + action_markers):
        return []
    if len(text) > 90:
        return []

    return [{
        "content": text,
        "tags": ["对话事件"],
        "importance": 2,
        "category": "episodic",
        "metadata": {"source_text": text, "kind": "event"},
    }]


def dedupe_memory_candidates(items: List[Dict]) -> List[Dict]:
    deduped = []
    seen = set()
    for item in items:
        key = (
            item.get("category", "episodic"),
            normalize_for_match(item.get("content", "")),
        )
        if key in seen or not item.get("content"):
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _sanitize_profile_candidates(candidates: List[Dict]) -> List[Dict]:
    sanitized = []
    seen = set()
    for candidate in candidates or []:
        if not isinstance(candidate, dict):
            continue
        slot = str(candidate.get("slot", "")).strip()
        value = str(candidate.get("value", "")).strip(" ：:,.，。！？!？")
        if slot not in PROFILE_SLOT_LABELS or not value:
            continue
        confidence = candidate.get("confidence", PROFILE_SLOT_PRIORITIES.get(slot, 0.7))
        try:
            confidence = float(confidence)
        except Exception:
            confidence = PROFILE_SLOT_PRIORITIES.get(slot, 0.7)
        key = (slot, normalize_for_match(value))
        if key in seen:
            continue
        seen.add(key)
        sanitized.append({
            "slot": slot,
            "value": compact_text(value, 48),
            "confidence": max(0.0, min(confidence, 1.0)),
            "source_text": candidate.get("source_text", ""),
            "reason": str(candidate.get("reason", "")).strip(),
        })
    return sanitized


def _sanitize_graph_facts(facts: List[Dict]) -> List[Dict]:
    sanitized = []
    seen = set()
    for fact in facts or []:
        if not isinstance(fact, dict):
            continue
        subject = str(fact.get("subject", "")).strip() or "制作人"
        relation = str(fact.get("relation", "")).strip()
        object_value = str(fact.get("object", "")).strip(" ：:,.，。！？!？")
        if not relation or not object_value:
            continue
        tags = [str(tag).strip() for tag in fact.get("tags", []) if str(tag).strip()]
        fact_type = str(fact.get("fact_type", "fact")).strip() or "fact"
        key = (normalize_for_match(subject), normalize_for_match(relation), normalize_for_match(object_value), fact_type)
        if key in seen:
            continue
        seen.add(key)
        try:
            confidence = float(fact.get("confidence", 0.8))
        except Exception:
            confidence = 0.8
        sanitized.append({
            "subject": subject,
            "relation": relation,
            "object": compact_text(object_value, 48),
            "tags": tags,
            "source": str(fact.get("source", "conversation")).strip() or "conversation",
            "confidence": max(0.0, min(confidence, 1.0)),
            "fact_type": fact_type,
            "reason": str(fact.get("reason", "")).strip(),
        })
    return sanitized


def _sanitize_episodic_candidates(candidates: List[Dict]) -> List[Dict]:
    sanitized = []
    seen = set()
    for candidate in candidates or []:
        if not isinstance(candidate, dict):
            continue
        content = compact_text(str(candidate.get("content", "")).strip(), 96)
        if not content:
            continue
        category = str(candidate.get("category", "episodic")).strip() or "episodic"
        key = (category, normalize_for_match(content))
        if key in seen:
            continue
        seen.add(key)
        tags = [str(tag).strip() for tag in candidate.get("tags", []) if str(tag).strip()]
        metadata = candidate.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        try:
            importance = int(candidate.get("importance", 3))
        except Exception:
            importance = 3
        try:
            confidence = float(candidate.get("confidence", min(0.95, 0.34 + 0.12 * importance)))
        except Exception:
            confidence = min(0.95, 0.34 + 0.12 * importance)
        sanitized.append({
            "content": content,
            "tags": tags,
            "importance": max(1, min(importance, 5)),
            "category": category,
            "metadata": metadata,
            "confidence": max(0.0, min(confidence, 1.0)),
            "reason": str(candidate.get("reason", "")).strip(),
        })
    return sanitized


def sanitize_memory_write_plan(plan: Dict[str, Any]) -> Dict[str, List[Dict]]:
    if not isinstance(plan, dict):
        raise ValueError("memory write plan must be a dict")
    return {
        "profile_candidates": _sanitize_profile_candidates(plan.get("profile_candidates", [])),
        "graph_facts": _sanitize_graph_facts(plan.get("graph_facts", [])),
        "episodic_candidates": _sanitize_episodic_candidates(plan.get("episodic_candidates", [])),
    }


def apply_memory_write_thresholds(
    plan: Dict[str, List[Dict]],
    thresholds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    thresholds = thresholds or MEMORY_WRITE_THRESHOLDS
    filtered: Dict[str, Any] = {
        "profile_candidates": [],
        "graph_facts": [],
        "episodic_candidates": [],
        "rejected_candidates": [],
    }

    for bucket in ("profile_candidates", "graph_facts", "episodic_candidates"):
        threshold = float(thresholds.get(bucket, 0.0))
        for item in plan.get(bucket, []):
            confidence = float(item.get("confidence", 0.0))
            if confidence >= threshold:
                filtered[bucket].append(item)
                continue
            reason = str(item.get("reason", "")).strip() or "below_confidence_threshold"
            filtered["rejected_candidates"].append({
                "bucket": bucket,
                "threshold": threshold,
                "confidence": confidence,
                "reason": reason,
                "item": item,
            })

    filtered["write_meta"] = {
        "thresholds": dict(thresholds),
        "accepted_counts": {
            "profile_candidates": len(filtered["profile_candidates"]),
            "graph_facts": len(filtered["graph_facts"]),
            "episodic_candidates": len(filtered["episodic_candidates"]),
        },
        "rejected_count": len(filtered["rejected_candidates"]),
    }
    return filtered


def build_rule_memory_write_plan_from_turns(
    turns: List[Dict[str, Any]],
    user_subject: str = "制作人",
    assistant_label: str = "RoleWeaver",
) -> Dict[str, List[Dict]]:
    profile_candidates: List[Dict] = []
    graph_facts: List[Dict] = []
    episodic_candidates: List[Dict] = []

    for turn in turns or []:
        user_text = str(turn.get("user_text", "")).strip()
        assistant_text = str(turn.get("assistant_text", "")).strip()
        if user_text:
            profile_candidates.extend(extract_profile_candidates(user_text))
            graph_facts.extend(extract_user_state_candidates(user_text, user_subject=user_subject))
            episodic_candidates.extend(extract_long_term_candidates(user_text))
            episodic_candidates.extend(extract_event_candidates(user_text))
            if "答应" in user_text or "约好" in user_text:
                episodic_candidates.append({
                    "content": compact_text(user_text, 72),
                    "tags": ["约定", "对话事件"],
                    "importance": 4,
                    "confidence": 0.82,
                    "category": "episodic",
                    "metadata": {"source_text": user_text, "kind": "agreement"},
                    "reason": "explicit agreement mentioned in user text",
                })

        if assistant_text and any(marker in assistant_text for marker in ["我会记住", "我会提醒你", "我会陪着你"]):
            episodic_candidates.append({
                "content": f"{assistant_label}承诺：{compact_text(assistant_text, 64)}",
                "tags": ["角色承诺"],
                "importance": 3,
                "confidence": 0.74,
                "category": "episodic",
                "metadata": {"assistant_text": assistant_text, "kind": "assistant_commitment"},
                "reason": "assistant made an explicit commitment",
            })

    return sanitize_memory_write_plan({
        "profile_candidates": profile_candidates,
        "graph_facts": graph_facts,
        "episodic_candidates": dedupe_memory_candidates(episodic_candidates),
    })


def build_memory_write_plan(
    pending_turns: List[Dict[str, Any]],
    judge: Optional[Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]] = None,
    active_facts: Optional[List[Dict]] = None,
    user_subject: str = "制作人",
    assistant_label: str = "RoleWeaver",
) -> Dict[str, Any]:
    sanitized_base = build_rule_memory_write_plan_from_turns(
        pending_turns,
        user_subject=user_subject,
        assistant_label=assistant_label,
    )
    if judge is None:
        return apply_memory_write_thresholds(sanitized_base)

    judge_payload = {
        "pending_turns": pending_turns,
        "rule_plan": sanitized_base,
        "active_facts": active_facts or [],
    }

    try:
        judged_plan = judge(judge_payload)
        if judged_plan is None:
            return apply_memory_write_thresholds(sanitized_base)
        return apply_memory_write_thresholds(sanitize_memory_write_plan(judged_plan))
    except Exception:
        return apply_memory_write_thresholds(sanitized_base)


@dataclass
class MemoryContextPacket:
    mid_term_lines: List[str] = field(default_factory=list)
    long_term_lines: List[str] = field(default_factory=list)
    reflection_lines: List[str] = field(default_factory=list)
    profile_lines: List[str] = field(default_factory=list)
    episodic_lines: List[str] = field(default_factory=list)
    knowledge_lines: List[str] = field(default_factory=list)
    contradiction_lines: List[str] = field(default_factory=list)

    def render(self) -> str:
        sections = []
        if self.mid_term_lines:
            sections.append("【中期记忆】\n" + "\n".join(f"- {line}" for line in self.mid_term_lines))
        if self.long_term_lines:
            sections.append("【长期记忆】\n" + "\n".join(f"- {line}" for line in self.long_term_lines))
        if self.reflection_lines:
            sections.append("【反思笔记】\n" + "\n".join(f"- {line}" for line in self.reflection_lines))

        if self.profile_lines:
            sections.append("【用户画像】\n" + "\n".join(f"- {line}" for line in self.profile_lines))
        if self.episodic_lines:
            sections.append("【情节记忆】\n" + "\n".join(f"- {line}" for line in self.episodic_lines))
        if self.knowledge_lines:
            sections.append("【角色知识】\n" + "\n".join(f"- {line}" for line in self.knowledge_lines))

        if self.contradiction_lines:
            sections.append("【矛盾链提示】\n" + "\n".join(f"- {line}" for line in self.contradiction_lines))

        if not sections:
            return ""

        return (
            "以下信息仅在相关时自然参考，不要逐条复述，不要机械背诵。\n\n"
            + "\n\n".join(sections)
        )


class HybridMemoryStore:
    def __init__(
        self,
        memory_file: str = "memories_v2.json",
        index_file: str = "memories_v2.faiss",
        embedding_model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        reranker_model_name: Optional[str] = "BAAI/bge-reranker-v2-m3",
        reranker_candidate_k: int = 12,
    ):
        self.memory_file = memory_file
        self.index_file = index_file
        self.embedding_model_name = embedding_model_name
        self.reranker_model_name = reranker_model_name
        self.reranker_candidate_k = reranker_candidate_k
        self.memories: List[Dict] = self._load_memories()
        self.encoder = None
        self.reranker = None
        self.dimension = None
        self.index = None
        self.embedding_matrix = None
        self._try_init_encoder()

    def _load_memories(self) -> List[Dict]:
        data = load_json_file(self.memory_file, [])
        if not isinstance(data, list):
            return []
        normalized = []
        for i, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            normalized_source = normalize_memory_source(item.get("source", "conversation"))
            memory_type = item.get("memory_type", infer_memory_type(item.get("category", "episodic"), metadata))
            tags = item.get("tags", [])
            normalized.append({
                "id": int(item.get("id", i)),
                "schema_version": item.get("schema_version", "1.0"),
                "content": item.get("content", "").strip(),
                "memory_type": memory_type,
                "memory_layer": item.get("memory_layer", infer_memory_layer(memory_type, item.get("source", "conversation"), metadata, tags)),
                "scope": item.get("scope", infer_memory_scope(memory_type, normalized_source, metadata)),
                "tags": tags,
                "importance": int(item.get("importance", 3)),
                "timestamp": int(item.get("timestamp", now_ts())),
                "valid_from": item.get("valid_from", now_iso()),
                "valid_until": item.get("valid_until"),
                "status": item.get("status", "active"),
                "confidence": normalize_memory_confidence({"confidence": item.get("confidence", metadata.get("confidence", 0.65))}),
                "use_count": normalize_use_count(item.get("use_count", metadata.get("use_count", 0))),
                "last_used_at": parse_memory_time(item.get("last_used_at", metadata.get("last_used_at"))),
                "reinforcement_score": normalize_reinforcement_score(
                    item.get("reinforcement_score", metadata.get("reinforcement_score", 0.0))
                ),
                "reason": item.get("reason", metadata.get("reason", "")),
                "evidence": normalize_memory_evidence_list(item.get("evidence")) or normalize_memory_evidence(metadata, normalized_source),
                "links": normalize_memory_refs(item.get("links", [])),
                "contradicts": normalize_memory_refs(item.get("contradicts", [])),
                "metadata": metadata,
                "category": item.get("category", "episodic"),
                "source": item.get("source", "conversation"),
                "source_kind": item.get("source_kind", normalized_source),
            })
        return [m for m in normalized if m["content"]]

    def _save_memories(self):
        save_json_file(self.memory_file, self.memories)

    def _indexable_text(self, memory: Dict) -> str:
        tags = " ".join(memory.get("tags", []))
        category = memory.get("category", "")
        metadata = memory.get("metadata")
        amem_text = ""
        if isinstance(metadata, dict):
            amem = metadata.get("amem")
            if isinstance(amem, dict):
                event_text = " ".join(
                    str(event.get("new_memory_excerpt", ""))
                    for event in amem.get("evolution_events", [])
                    if isinstance(event, dict)
                )
                topic_text = " ".join(str(item) for item in amem.get("topic_labels", []) if str(item).strip())
                alias_text = " ".join(str(item) for item in amem.get("retrieval_aliases", []) if str(item).strip())
                amem_text = (
                    f"{amem.get('current_interpretation', '')} "
                    f"{amem.get('evolution_summary', '')} "
                    f"{amem.get('cluster_key', '')} "
                    f"{topic_text} {alias_text} {event_text}"
                ).strip()
        return f"{memory.get('content', '')} {tags} {category} {amem_text}".strip()

    def _try_init_encoder(self):
        if SentenceTransformer is None:
            print("[Memory] sentence-transformers 不可用，embedding 检索降级为词面检索。")
        elif np is None:
            print("[Memory] numpy 不可用，embedding 检索降级为词面检索。")
        else:
            try:
                print(f"[Memory] 加载 embedding 模型: {self.embedding_model_name}")
                self.encoder = SentenceTransformer(self.embedding_model_name)
                test_vec = self.encoder.encode(["test"], normalize_embeddings=True, convert_to_numpy=True)
                self.dimension = int(test_vec.shape[1])
                if faiss is None:
                    print("[Memory] faiss 不可用，embedding 检索回退为内存矩阵相似度检索。")
                self.index = self._load_or_build_index()
            except Exception as exc:
                print(f"[Memory] embedding 初始化失败，降级为词面检索: {exc}")
                self.encoder = None
                self.dimension = None
                self.index = None
                self.embedding_matrix = None

        if CrossEncoder is None or not self.reranker_model_name:
            print("[Memory] reranker 不可用，保留 embedding/词面混合召回。")
            return

        try:
            print(f"[Memory] 加载 reranker 模型: {self.reranker_model_name}")
            self.reranker = CrossEncoder(self.reranker_model_name)
        except Exception as exc:
            print(f"[Memory] reranker 初始化失败，跳过精排: {exc}")
            self.reranker = None

    def _normalize_reranker_score(self, score) -> float:
        try:
            if np is not None and hasattr(score, "shape"):
                score = score.tolist()
            if isinstance(score, (list, tuple)):
                score = score[0]
            score = float(score)
        except Exception:
            return 0.0

        clipped = max(-20.0, min(20.0, score))
        return 1.0 / (1.0 + math.exp(-clipped))

    def _new_index(self):
        return faiss.IndexFlatIP(self.dimension)

    def _load_or_build_index(self):
        if faiss is None:
            return self._rebuild_index()

        if os.path.exists(self.index_file):
            try:
                index = faiss.read_index(self.index_file)
                if index.d == self.dimension and index.ntotal == len(self.memories):
                    return index
            except Exception:
                pass
        return self._rebuild_index()

    def _save_index(self):
        if faiss is not None and self.index is not None:
            faiss.write_index(self.index, self.index_file)

    def _encode_texts(self, texts: List[str]):
        if not texts or self.encoder is None:
            return None
        sanitized_texts = [str(text or "") for text in texts]
        try:
            vecs = self.encoder.encode(
                sanitized_texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            return vecs.astype("float32")
        except Exception as exc:
            print(f"[Memory] embedding 编码失败，降级为词面检索: {exc}")
            self.encoder = None
            self.index = None
            self.embedding_matrix = None
            return None

    def _rebuild_index(self):
        if self.encoder is None:
            return None

        texts = [self._indexable_text(m) for m in self.memories] if self.memories else []
        vecs = self._encode_texts(texts) if texts else None

        if faiss is None:
            self.embedding_matrix = vecs
            self.index = None
            return None

        index = self._new_index()
        if self.memories:
            if vecs is not None and len(vecs) > 0:
                index.add(vecs)
        self.index = index
        self._save_index()
        return index

    def list_memories(self, category: Optional[str] = None) -> List[Dict]:
        if category is None:
            return list(self.memories)
        return [m for m in self.memories if m.get("category") == category]

    def add_memory(
        self,
        content: str,
        tags: Optional[List[str]] = None,
        importance: int = 3,
        metadata: Optional[Dict] = None,
        category: str = "episodic",
        source: str = "conversation",
    ):
        content = (content or "").strip()
        if not content:
            return None
        tags = tags or []
        metadata = metadata or {}
        normalized_source = normalize_memory_source(source)
        memory_type = infer_memory_type(category, metadata)
        memory_layer = infer_memory_layer(memory_type, source, metadata, tags)

        for memory in self.memories:
            same_content = normalize_for_match(memory["content"]) == normalize_for_match(content)
            same_category = memory.get("category", "episodic") == category
            if same_content and same_category:
                return None

        auto_link_hits: List[Dict[str, Any]] = []
        if (
            not metadata.get("disable_auto_linking")
            and metadata.get("scope") != "character_canon"
            and memory_type != "character_fact"
            and normalized_source not in {"skill", "imported_reference"}
        ):
            auto_link_hits = detect_related_memory_links(content, tags, self.memories)
        auto_link_ids = [hit["memory_id"] for hit in auto_link_hits if hit.get("memory_id")]
        if auto_link_ids:
            metadata = dict(metadata)
            metadata["links"] = normalize_memory_refs(metadata.get("links", [])) + auto_link_ids
            metadata["links"] = normalize_memory_refs(metadata["links"])
            metadata["reason"] = append_reason(
                metadata.get("reason", ""),
                "Auto-linked to semantically related active memories.",
            )
            metadata["evidence"] = append_unique_texts(
                metadata.get("evidence"),
                [f"auto_link:{memory_id}" for memory_id in auto_link_ids],
            )

        memory = {
            "id": len(self.memories) + 1,
            "schema_version": str(metadata.get("schema_version", "1.0")),
            "content": content,
            "memory_type": memory_type,
            "memory_layer": memory_layer,
            "scope": infer_memory_scope(memory_type, normalized_source, metadata),
            "tags": tags,
            "importance": int(importance),
            "timestamp": now_ts(),
            "valid_from": str(metadata.get("valid_from", now_iso())),
            "valid_until": metadata.get("valid_until"),
            "status": str(metadata.get("status", "active")),
            "confidence": normalize_memory_confidence(metadata),
            "use_count": normalize_use_count(metadata.get("use_count", 0)),
            "last_used_at": parse_memory_time(metadata.get("last_used_at")),
            "reinforcement_score": normalize_reinforcement_score(metadata.get("reinforcement_score", 0.0)),
            "reason": str(metadata.get("reason", "")),
            "evidence": normalize_memory_evidence(metadata, normalized_source),
            "links": normalize_memory_refs(metadata.get("links", [])),
            "contradicts": normalize_memory_refs(metadata.get("contradicts", [])),
            "metadata": metadata,
            "category": category,
            "source": source,
            "source_kind": normalized_source,
        }
        self.memories.append(memory)
        if auto_link_ids:
            new_id = int(memory["id"])
            for old_memory in self.memories:
                old_id = int(old_memory.get("id", 0))
                if old_id not in auto_link_ids:
                    continue
                old_memory["links"] = normalize_memory_refs(normalize_memory_refs(old_memory.get("links", [])) + [new_id])
                old_metadata = old_memory.get("metadata")
                if not isinstance(old_metadata, dict):
                    old_metadata = {}
                linked_by = old_metadata.get("linked_by", [])
                if not isinstance(linked_by, list):
                    linked_by = []
                linked_by.append({"memory_id": new_id, "reason": "auto_memory_linking", "at": now_ts()})
                old_metadata["linked_by"] = linked_by[-8:]
                old_memory["metadata"] = old_metadata
                hit = next((item for item in auto_link_hits if int(item.get("memory_id", 0)) == old_id), None)
                if hit and float(hit.get("score", 0.0)) >= AMEM_EVOLUTION_SCORE_THRESHOLD:
                    append_amem_evolution_event(old_memory, memory, hit)
        self._save_memories()

        if self.encoder is None:
            return dict(memory)

        if auto_link_ids:
            self._rebuild_index()
            return dict(memory)

        vecs = self._encode_texts([self._indexable_text(memory)])
        if vecs is None:
            return dict(memory)

        if faiss is None:
            if self.embedding_matrix is None or len(self.embedding_matrix) == 0:
                self.embedding_matrix = vecs
            else:
                self.embedding_matrix = np.vstack([self.embedding_matrix, vecs])
            return dict(memory)

        if self.index is None:
            self.index = self._new_index()
        self.index.add(vecs)
        self._save_index()
        return dict(memory)

    def delete_memory(self, memory_id: int):
        self.memories = [m for m in self.memories if m["id"] != memory_id]
        for i, memory in enumerate(self.memories, start=1):
            memory["id"] = i
        self._save_memories()
        self._rebuild_index()

    def update_memory(
        self,
        memory_id: int,
        *,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
        importance: Optional[int] = None,
        status: Optional[str] = None,
        confidence: Optional[float] = None,
        valid_until: Optional[str] = None,
        memory_layer: Optional[str] = None,
        reason: Optional[str] = None,
        evidence: Optional[List[str]] = None,
        contradicts: Optional[List[int]] = None,
        metadata: Optional[Dict] = None,
    ) -> Optional[Dict]:
        valid_statuses = {"active", "stale", "contradicted", "archived", "deleted"}
        changed = False
        target = None
        for memory in self.memories:
            if int(memory.get("id", -1)) == int(memory_id):
                target = memory
                break
        if target is None:
            return None

        if content is not None:
            cleaned = content.strip()
            if cleaned:
                target["content"] = cleaned
                changed = True
        if tags is not None:
            target["tags"] = [str(tag).strip() for tag in tags if str(tag).strip()]
            changed = True
        if importance is not None:
            target["importance"] = max(1, min(int(importance), 5))
            changed = True
        if status is not None:
            normalized_status = str(status).strip().lower()
            if normalized_status not in valid_statuses:
                raise ValueError(f"invalid memory status: {status}")
            target["status"] = normalized_status
            changed = True
        if confidence is not None:
            target["confidence"] = normalize_memory_confidence({"confidence": confidence})
            changed = True
        if valid_until is not None:
            target["valid_until"] = valid_until.strip() or None
            changed = True
        if memory_layer is not None:
            normalized_layer = MEMORY_LAYER_ALIASES.get(str(memory_layer).strip().lower())
            if normalized_layer is None:
                raise ValueError(f"invalid memory layer: {memory_layer}")
            target["memory_layer"] = normalized_layer
            changed = True
        if reason is not None:
            target["reason"] = reason.strip()
            changed = True
        if evidence is not None:
            target["evidence"] = normalize_memory_evidence_list(evidence)
            changed = True
        if contradicts is not None:
            target["contradicts"] = normalize_memory_refs(contradicts)
            changed = True
        if metadata:
            current_metadata = target.get("metadata")
            if not isinstance(current_metadata, dict):
                current_metadata = {}
            current_metadata.update(metadata)
            target["metadata"] = current_metadata
            changed = True

        if changed:
            self._save_memories()
            self._rebuild_index()
        return dict(target)

    def reinforce_memories(
        self,
        memory_ids: List[int],
        *,
        reason: str = "context_retrieval",
        amount: float = REINFORCEMENT_CONTEXT_AMOUNT,
    ) -> Dict[str, Any]:
        wanted = {int(memory_id) for memory_id in (memory_ids or []) if str(memory_id).strip().isdigit()}
        if not wanted:
            return {"updated_count": 0, "memory_ids": []}

        ts = now_ts()
        reason = str(reason or "context_retrieval").strip()
        updated_ids = []
        for memory in self.memories:
            memory_id = int(memory.get("id", 0))
            if memory_id not in wanted or memory.get("status", "active") != "active":
                continue

            current_metadata = memory.get("metadata")
            if not isinstance(current_metadata, dict):
                current_metadata = {}
            events = current_metadata.get("reinforcement_events", [])
            if not isinstance(events, list):
                events = []
            events.append({"at": ts, "reason": reason, "amount": round(float(amount), 4)})
            current_metadata["reinforcement_events"] = events[-8:]
            current_metadata["last_reinforcement_reason"] = reason

            memory["use_count"] = normalize_use_count(memory.get("use_count", 0)) + 1
            memory["last_used_at"] = ts
            memory["reinforcement_score"] = normalize_reinforcement_score(
                normalize_reinforcement_score(memory.get("reinforcement_score", 0.0)) + float(amount)
            )
            memory["metadata"] = current_metadata
            updated_ids.append(memory_id)

        if updated_ids:
            self._save_memories()
        return {"updated_count": len(updated_ids), "memory_ids": updated_ids}

    def clear_all(self):
        self.memories = []
        self._save_memories()
        self._rebuild_index()

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.18,
        categories: Optional[List[str]] = None,
        memory_layers: Optional[List[str]] = None,
    ) -> List[Dict]:
        query = (query or "").strip()
        if not query or not self.memories:
            return []

        dense_scores: Dict[int, float] = {}
        if self.encoder is not None and faiss is not None and self.index is not None and self.index.ntotal > 0:
            query_vec = self._encode_texts([query])
            if query_vec is not None:
                k = min(max(top_k * 6, top_k), len(self.memories))
                scores, indices = self.index.search(query_vec, k)
                for score, idx in zip(scores[0], indices[0]):
                    if idx < 0 or idx >= len(self.memories):
                        continue
                    dense_scores[self.memories[idx]["id"]] = float(score)
        elif self.encoder is not None and np is not None and self.embedding_matrix is not None and len(self.embedding_matrix) > 0:
            query_vec = self._encode_texts([query])
            if query_vec is not None:
                scores = np.matmul(self.embedding_matrix, query_vec[0])
                ranking = np.argsort(-scores)[: min(max(top_k * 6, top_k), len(self.memories))]
                for idx in ranking:
                    dense_scores[self.memories[int(idx)]["id"]] = float(scores[int(idx)])

        results = []
        for memory in self.memories:
            if memory.get("status", "active") != "active":
                continue
            if categories and memory.get("category") not in categories:
                continue
            if memory_layers and memory.get("memory_layer") not in memory_layers:
                continue

            dense = dense_scores.get(memory["id"], 0.0)
            lex = lexical_score(query, self._indexable_text(memory))
            if max(dense, lex) < min_score:
                continue

            importance_bonus = 0.02 * max(1, min(int(memory.get("importance", 3)), 5))
            score = (
                0.60 * max(dense, 0.0)
                + 0.32 * lex
                + importance_bonus
                + recency_bonus(memory.get("timestamp"))
                + memory_reinforcement_bonus(memory)
            )

            item = dict(memory)
            item["_dense_score"] = dense
            item["_lexical_score"] = lex
            item["_base_score"] = score
            item["_rerank_score"] = 0.0
            item["_final_score"] = score
            results.append(item)

        results.sort(key=lambda x: x["_base_score"], reverse=True)

        if self.reranker is not None and results:
            rerank_pool = results[: min(len(results), max(top_k, self.reranker_candidate_k))]
            pairs = [(query, item["content"]) for item in rerank_pool]
            try:
                rerank_scores = self.reranker.predict(pairs)
                for item, raw_score in zip(rerank_pool, rerank_scores):
                    rerank_score = self._normalize_reranker_score(raw_score)
                    item["_rerank_score"] = rerank_score
                    item["_final_score"] = (
                        0.72 * rerank_score
                        + 0.22 * item["_base_score"]
                        + 0.06 * item["_lexical_score"]
                    )
            except Exception as exc:
                print(f"[Memory] reranker 精排失败，回退基础排序: {exc}")

        results.sort(key=lambda x: x["_final_score"], reverse=True)
        return results[:top_k]


class GraphBackedProfileView:
    def __init__(self, graph_store, user_subject: str = "制作人"):
        self.graph_store = graph_store
        self.user_subject = user_subject

    def update_from_candidates(self, candidates: List[Dict]) -> List[Dict]:
        updates = []
        for candidate in candidates:
            relation = PROFILE_SLOT_LABELS.get(candidate["slot"], candidate["slot"])
            created = self.graph_store.add_fact(
                subject=self.user_subject,
                relation=relation,
                object_value=candidate["value"],
                tags=["user_profile", candidate["slot"]],
                source="conversation",
                confidence=candidate["confidence"],
                fact_type="profile",
            )
            if created:
                updates.append(candidate)
        return updates

    def update_from_text(self, text: str) -> List[Dict]:
        return self.update_from_candidates(extract_profile_candidates(text))

    def clear(self):
        self.graph_store.delete_facts(tags=["user_profile"])
        self.graph_store.delete_facts(tags=["user_state"])

    def render_context(
        self,
        query: Optional[str] = None,
        max_items_per_slot: int = 2,
        max_total: int = 4,
    ) -> List[str]:
        grouped: Dict[str, List[Dict]] = {slot: [] for slot in PROFILE_SLOT_LABELS}
        for fact in self.graph_store.list_facts(subject=self.user_subject, active_only=True):
            slot = RELATION_TO_PROFILE_SLOT.get(fact.get("relation"))
            if not slot:
                continue
            tags = set(fact.get("tags", []))
            if "user_profile" not in tags and "user_state" not in tags:
                continue
            grouped[slot].append(fact)

        scored_lines = []
        for slot, label in PROFILE_SLOT_LABELS.items():
            items = sorted(
                grouped.get(slot, []),
                key=lambda x: (x.get("confidence", 0.0), x.get("timestamp", 0)),
                reverse=True,
            )
            values = [item["object"] for item in items[:max_items_per_slot]]
            if values:
                line = f"{label}：{'；'.join(values)}"
                relevance = lexical_score(query or "", f"{label} {' '.join(values)}") if query else 0.0
                confidence = max(float(item.get("confidence", 0.0)) for item in items[:max_items_per_slot])
                recent = max(recency_bonus(item.get("timestamp"), horizon_days=10.0) for item in items[:max_items_per_slot])
                priority = PROFILE_SLOT_PRIORITIES.get(slot, 0.4)
                score = 0.64 * relevance + 0.20 * priority + 0.10 * confidence + recent
                scored_lines.append((score, relevance, line))

        scored_lines.sort(key=lambda item: (item[1] > 0, item[0]), reverse=True)
        return [line for _, _, line in scored_lines[:max_total]]


class ConversationState:
    def __init__(
        self,
        state_file: str = "memory_state_v1.json",
        recent_limit: int = 8,
        archive_chunk: int = 4,
        max_summaries: int = 32,
        user_label: str = "制作人",
        assistant_label: str = "RoleWeaver",
    ):
        self.state_file = state_file
        self.recent_limit = recent_limit
        self.archive_chunk = archive_chunk
        self.max_summaries = max_summaries
        self.user_label = user_label
        self.assistant_label = assistant_label
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        data = load_json_file(self.state_file, {})
        if not isinstance(data, dict):
            data = {}
        data.setdefault("recent_history", [])
        data.setdefault("summaries", [])
        data.setdefault("pending_turns", [])
        return data

    def _save_state(self):
        save_json_file(self.state_file, self.state)

    def clear(self):
        self.state = {"recent_history": [], "summaries": [], "pending_turns": []}
        self._save_state()

    def get_recent_history(self, max_messages: Optional[int] = None) -> List[Dict]:
        history = self.state.get("recent_history", [])
        if max_messages is None:
            return list(history)
        return history[-max_messages:]

    def list_summaries(self) -> List[Dict]:
        return list(self.state.get("summaries", []))

    def list_pending_turns(self) -> List[Dict]:
        return list(self.state.get("pending_turns", []))

    def clear_pending_turns(self):
        self.state["pending_turns"] = []
        self._save_state()

    def _summarize_chunk(self, messages: List[Dict]) -> Optional[Dict]:
        if not messages:
            return None

        user_lines = [compact_text(m["content"], 36) for m in messages if m.get("role") == "user"]
        assistant_lines = [compact_text(m["content"], 36) for m in messages if m.get("role") == "assistant"]

        pieces = []
        if user_lines:
            pieces.append(f"{self.user_label}提到：" + "；".join(user_lines[:2]))
        if assistant_lines:
            pieces.append(f"{self.assistant_label}回应：" + "；".join(assistant_lines[:2]))

        if not pieces:
            return None

        return {
            "id": len(self.state.get("summaries", [])) + 1,
            "content": " / ".join(pieces),
            "timestamp": now_ts(),
            "turn_count": len(messages),
        }

    def record_turn(self, user_text: str, assistant_text: str) -> List[Dict]:
        archived = []
        self.state["recent_history"].append({"role": "user", "content": user_text})
        self.state["recent_history"].append({"role": "assistant", "content": assistant_text})
        self.state["pending_turns"].append({
            "user_text": user_text,
            "assistant_text": assistant_text,
            "timestamp": now_ts(),
        })

        while len(self.state["recent_history"]) > self.recent_limit:
            chunk = self.state["recent_history"][: self.archive_chunk]
            summary = self._summarize_chunk(chunk)
            if summary is not None:
                self.state["summaries"].append(summary)
                self.state["summaries"] = self.state["summaries"][-self.max_summaries:]
                for i, item in enumerate(self.state["summaries"], start=1):
                    item["id"] = i
                archived.append(summary)
            self.state["recent_history"] = self.state["recent_history"][self.archive_chunk :]

        self._save_state()
        return archived

    def archive_recent_history(self, keep_messages: int = 2, reason: str = "context_pressure") -> List[Dict]:
        history = self.state.get("recent_history", [])
        keep_messages = max(0, int(keep_messages or 0))
        archive_count = max(0, len(history) - keep_messages)
        if archive_count <= 0:
            return []

        archived = []
        to_archive = history[:archive_count]
        for start in range(0, len(to_archive), self.archive_chunk):
            chunk = to_archive[start:start + self.archive_chunk]
            summary = self._summarize_chunk(chunk)
            if summary is not None:
                summary["reason"] = reason
                self.state["summaries"].append(summary)
                archived.append(summary)

        if archived:
            self.state["summaries"] = self.state["summaries"][-self.max_summaries:]
            for i, item in enumerate(self.state["summaries"], start=1):
                item["id"] = i
        self.state["recent_history"] = history[archive_count:]
        self._save_state()
        return archived

    def search_summaries(self, query: str, top_k: int = 2, min_score: float = 0.12) -> List[Dict]:
        results = []
        for summary in self.state.get("summaries", []):
            lex = lexical_score(query, summary.get("content", ""))
            if lex < min_score:
                continue
            item = dict(summary)
            item["_score"] = lex + recency_bonus(summary.get("timestamp"), horizon_days=14.0)
            results.append(item)
        results.sort(key=lambda x: x["_score"], reverse=True)
        return results[:top_k]


class KnowledgeGraphStore:
    def __init__(
        self,
        graph_file: str = "knowledge_graph_v1.json",
        seed_facts: Optional[List[Dict[str, Any]]] = None,
    ):
        self.graph_file = graph_file
        self.seed_facts = seed_facts if seed_facts is not None else []
        self.graph = self._load_graph()
        if not self.graph.get("triples"):
            self.seed_defaults()

    def _load_graph(self) -> Dict:
        data = load_json_file(self.graph_file, {})
        if not isinstance(data, dict):
            data = {}
        data.setdefault("triples", [])
        return data

    def _save_graph(self):
        save_json_file(self.graph_file, self.graph)

    def seed_defaults(self):
        self.graph = {"triples": []}
        for fact in self.seed_facts:
            self.add_fact(
                subject=fact["subject"],
                relation=fact["relation"],
                object_value=fact["object"],
                tags=fact.get("tags", []),
                source=fact.get("source", "seed"),
                confidence=fact.get("confidence", 1.0),
            )

    def add_fact(
        self,
        subject: str,
        relation: str,
        object_value: str,
        tags: Optional[List[str]] = None,
        source: str = "conversation",
        confidence: float = 0.8,
        fact_type: str = "fact",
        valid_from: Optional[int] = None,
        valid_to: Optional[int] = None,
        active: bool = True,
    ) -> bool:
        subject = (subject or "").strip()
        relation = (relation or "").strip()
        object_value = (object_value or "").strip()
        if not subject or not relation or not object_value:
            return False

        tags = tags or []
        ts = valid_from or now_ts()
        normalized = (
            normalize_for_match(subject),
            normalize_for_match(relation),
            normalize_for_match(object_value),
        )
        for triple in self.graph["triples"]:
            key = (
                normalize_for_match(triple["subject"]),
                normalize_for_match(triple["relation"]),
                normalize_for_match(triple["object"]),
            )
            if key == normalized and bool(triple.get("active", True)) == bool(active):
                return False

        superseded_ids = []
        if active and (relation in SINGLE_VALUE_RELATIONS or fact_type in {"state", "status"}):
            for triple in self.graph["triples"]:
                if not triple.get("active", True):
                    continue
                same_subject = normalize_for_match(triple.get("subject", "")) == normalized[0]
                same_relation = normalize_for_match(triple.get("relation", "")) == normalized[1]
                different_object = normalize_for_match(triple.get("object", "")) != normalized[2]
                if same_subject and same_relation and different_object:
                    triple["active"] = False
                    triple["valid_to"] = ts
                    superseded_ids.append(triple["id"])

        self.graph["triples"].append({
            "id": len(self.graph["triples"]) + 1,
            "subject": subject,
            "relation": relation,
            "object": object_value,
            "tags": tags,
            "source": source,
            "confidence": float(confidence),
            "timestamp": ts,
            "fact_type": fact_type,
            "valid_from": ts,
            "valid_to": valid_to,
            "active": bool(active),
            "supersedes": superseded_ids,
        })
        self._save_graph()
        return True

    def list_facts(
        self,
        subject: Optional[str] = None,
        tags: Optional[List[str]] = None,
        active_only: bool = True,
    ) -> List[Dict]:
        facts = list(self.graph.get("triples", []))
        if subject is not None:
            facts = [fact for fact in facts if fact.get("subject") == subject]
        if tags:
            required = set(tags)
            facts = [fact for fact in facts if required.issubset(set(fact.get("tags", [])))]
        if active_only:
            facts = [fact for fact in facts if fact.get("active", True)]
        return facts

    def delete_facts(
        self,
        subject: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> int:
        before = len(self.graph.get("triples", []))
        kept = []
        required = set(tags or [])
        for fact in self.graph.get("triples", []):
            matches_subject = subject is None or fact.get("subject") == subject
            matches_tags = not required or required.issubset(set(fact.get("tags", [])))
            if matches_subject and matches_tags:
                continue
            kept.append(fact)

        self.graph["triples"] = kept
        for i, fact in enumerate(self.graph["triples"], start=1):
            fact["id"] = i
        self._save_graph()
        return before - len(kept)

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.12,
        subject: Optional[str] = None,
        tags: Optional[List[str]] = None,
        active_only: bool = True,
    ) -> List[Dict]:
        results = []
        for triple in self.list_facts(subject=subject, tags=tags, active_only=active_only):
            render = (
                f"{triple['subject']} {triple['relation']} {triple['object']} "
                f"{' '.join(triple.get('tags', []))} {triple.get('fact_type', '')}"
            )
            lex = lexical_score(query, render)
            if lex < min_score:
                continue
            score = (
                0.74 * lex
                + 0.14 * float(triple.get("confidence", 0.0))
                + recency_bonus(triple.get("timestamp"), horizon_days=20.0)
            )
            item = dict(triple)
            item["_score"] = score
            results.append(item)
        results.sort(key=lambda x: x["_score"], reverse=True)
        return results[:top_k]

    def core_facts(self, top_k: int = 3) -> List[Dict]:
        core = [t for t in self.graph.get("triples", []) if "core" in t.get("tags", [])]
        core.sort(key=lambda x: (x.get("confidence", 0.0), x.get("timestamp", 0)), reverse=True)
        return core[:top_k]


class MemoryRuntime:
    def __init__(
        self,
        memory_file: str = "memories_v2.json",
        index_file: str = "memories_v2.faiss",
        profile_file: str = "user_profile_v1.json",
        state_file: str = "memory_state_v1.json",
        knowledge_file: str = "knowledge_graph_v1.json",
        memory_write_judge: Optional[Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]] = None,
        user_subject: str = "制作人",
        assistant_label: str = "RoleWeaver",
        character_query_keywords: Optional[List[str]] = None,
        character_knowledge_seed: Optional[List[Dict[str, Any]]] = None,
    ):
        self.user_subject = user_subject
        self.assistant_label = assistant_label
        self.character_query_keywords = tuple(character_query_keywords or CHARACTER_QUERY_KEYWORDS)
        self.episodic = HybridMemoryStore(memory_file=memory_file, index_file=index_file)
        self.state = ConversationState(
            state_file=state_file,
            user_label=user_subject,
            assistant_label=assistant_label,
        )
        self.knowledge = KnowledgeGraphStore(
            graph_file=knowledge_file,
            seed_facts=character_knowledge_seed,
        )
        self.profile = GraphBackedProfileView(self.knowledge, user_subject=user_subject)
        self.long_term = self.episodic
        self.profile_file = profile_file
        self.memory_write_judge = memory_write_judge
        self.last_write_plan: Optional[Dict[str, Any]] = None

    def recent_history(self, max_messages: int = 6) -> List[Dict]:
        return self.state.get_recent_history(max_messages=max_messages)

    def pending_turns(self) -> List[Dict]:
        return self.state.list_pending_turns()

    def memory_os_snapshot(self) -> Dict[str, Any]:
        memories = self.episodic.list_memories()
        layer_counts: Dict[str, int] = {
            "short_term": len(self.recent_history(max_messages=None) or []),
            "mid_term": len(self.state.list_summaries()),
            "long_term": 0,
            "graph": len(self.knowledge.list_facts(active_only=False)),
            "contradiction_graph": 0,
            "reflection_notes": 0,
        }
        status_counts: Dict[str, int] = {}
        reinforced_count = 0
        total_use_count = 0
        top_reinforced: List[Dict[str, Any]] = []
        link_count = 0
        evolved_count = 0
        evolution_event_count = 0
        top_evolved: List[Dict[str, Any]] = []
        for memory in memories:
            layer = memory.get("memory_layer") or infer_memory_layer(
                memory.get("memory_type", "episodic"),
                memory.get("source", "conversation"),
                memory.get("metadata", {}),
                memory.get("tags", []),
            )
            layer_counts[layer] = layer_counts.get(layer, 0) + 1
            status = memory.get("status", "active")
            status_counts[status] = status_counts.get(status, 0) + 1
            if memory.get("contradicts"):
                layer_counts["contradiction_graph"] = layer_counts.get("contradiction_graph", 0) + len(memory.get("contradicts", []))
            link_count += len(normalize_memory_refs(memory.get("links", [])))
            metadata = memory.get("metadata")
            amem = metadata.get("amem") if isinstance(metadata, dict) else None
            events = amem.get("evolution_events") if isinstance(amem, dict) else []
            if isinstance(events, list) and events:
                evolved_count += 1
                evolution_event_count += len(events)
                top_evolved.append(memory)
            use_count = normalize_use_count(memory.get("use_count", 0))
            total_use_count += use_count
            if use_count > 0 or normalize_reinforcement_score(memory.get("reinforcement_score", 0.0)) > 0:
                reinforced_count += 1
                top_reinforced.append(memory)
        top_reinforced.sort(
            key=lambda item: (
                normalize_reinforcement_score(item.get("reinforcement_score", 0.0)),
                normalize_use_count(item.get("use_count", 0)),
                int(item.get("last_used_at") or 0),
            ),
            reverse=True,
        )
        top_evolved.sort(
            key=lambda item: (
                int(((item.get("metadata") or {}).get("amem") or {}).get("last_evolved_at") or 0),
                len((((item.get("metadata") or {}).get("amem") or {}).get("evolution_events") or [])),
            ),
            reverse=True,
        )
        return {
            "layers": layer_counts,
            "memory_status": status_counts,
            "reinforcement": {
                "reinforced_memory_count": reinforced_count,
                "total_use_count": total_use_count,
                "top": [
                    {
                        "id": item.get("id"),
                        "content": compact_text(item.get("content", ""), 72),
                        "use_count": normalize_use_count(item.get("use_count", 0)),
                        "reinforcement_score": round(normalize_reinforcement_score(item.get("reinforcement_score", 0.0)), 4),
                        "last_used_at": item.get("last_used_at"),
                    }
                    for item in top_reinforced[:5]
                ],
            },
            "dynamic_links": {
                "total_link_count": link_count,
            },
            "amem_evolution": {
                "evolved_memory_count": evolved_count,
                "evolution_event_count": evolution_event_count,
                "top": [
                    {
                        "id": item.get("id"),
                        "content": compact_text(item.get("content", ""), 72),
                        "current_interpretation": compact_text(
                            (((item.get("metadata") or {}).get("amem") or {}).get("current_interpretation") or ""),
                            120,
                        ),
                        "event_count": len((((item.get("metadata") or {}).get("amem") or {}).get("evolution_events") or [])),
                        "last_evolved_at": ((item.get("metadata") or {}).get("amem") or {}).get("last_evolved_at"),
                        "cluster_key": ((item.get("metadata") or {}).get("amem") or {}).get("cluster_key", ""),
                        "topic_labels": ((item.get("metadata") or {}).get("amem") or {}).get("topic_labels", []),
                        "relationship_strength": ((item.get("metadata") or {}).get("amem") or {}).get("relationship_strength"),
                        "stability": ((item.get("metadata") or {}).get("amem") or {}).get("stability", ""),
                        "evolution_summary": compact_text(
                            (((item.get("metadata") or {}).get("amem") or {}).get("evolution_summary") or ""),
                            120,
                        ),
                    }
                    for item in top_evolved[:5]
                ],
            },
            "pending_turn_count": len(self.pending_turns()),
        }

    @staticmethod
    def _dedupe_ranked_lines(items: List[Dict], text_key: str, score_key: str, limit: int) -> List[str]:
        ranked = sorted(items, key=lambda item: item.get(score_key, 0.0), reverse=True)
        lines = []
        seen = set()
        for item in ranked:
            text = compact_text(item.get(text_key, ""), 96)
            key = normalize_for_match(text)
            if not text or key in seen:
                continue
            seen.add(key)
            lines.append(text)
            if len(lines) >= limit:
                break
        return lines

    def _should_include_character_knowledge(self, query: str, character_hits: List[Dict]) -> bool:
        normalized_query = normalize_for_match(query)
        if any(keyword in normalized_query for keyword in self.character_query_keywords):
            return True
        return any(item.get("_score", 0.0) >= 0.20 for item in character_hits)

    def build_context(self, query: str) -> MemoryContextPacket:
        summary_hits = self.state.search_summaries(query, top_k=2)
        episodic_hits = self.episodic.search(
            query=query,
            top_k=6,
            min_score=0.16,
            categories=["episodic"],
        )
        stable_long_term_hits = self.episodic.search(
            query=query,
            top_k=4,
            min_score=0.12,
            categories=["preference", "relationship", "boundary"],
            memory_layers=["long_term"],
        )
        reflection_hits = self.episodic.search(
            query=query,
            top_k=3,
            min_score=0.10,
            categories=["summary"],
            memory_layers=["reflection_notes"],
        )
        user_fact_hits = self.knowledge.search(
            query=query,
            top_k=6,
            min_score=0.08,
            subject=self.user_subject,
            active_only=True,
        )
        character_hits = self.knowledge.search(query, top_k=4, min_score=0.10)
        if not character_hits and any(keyword in query for keyword in self.character_query_keywords):
            character_hits = self.knowledge.core_facts(top_k=3)

        episodic_candidates = []
        for item in summary_hits:
            merged = dict(item)
            merged["_context_score"] = item.get("_score", 0.0)
            episodic_candidates.append(merged)
        for item in episodic_hits:
            merged = dict(item)
            merged["_context_score"] = item.get("_final_score", item.get("_base_score", 0.0))
            episodic_candidates.append(merged)
        episodic_lines = self._dedupe_ranked_lines(
            episodic_candidates,
            text_key="content",
            score_key="_context_score",
            limit=4,
        )
        mid_term_lines = self._dedupe_ranked_lines(
            [
                {**dict(item), "_context_score": item.get("_score", 0.0)}
                for item in summary_hits
            ],
            text_key="content",
            score_key="_context_score",
            limit=2,
        )
        long_term_lines = self._dedupe_ranked_lines(
            stable_long_term_hits,
            text_key="content",
            score_key="_final_score",
            limit=3,
        )
        reflection_lines = self._dedupe_ranked_lines(
            reflection_hits,
            text_key="content",
            score_key="_final_score",
            limit=2,
        )
        used_memory_ids = []
        for item in episodic_hits + stable_long_term_hits + reflection_hits:
            try:
                memory_id = int(item.get("id", 0))
            except (TypeError, ValueError):
                memory_id = 0
            if memory_id > 0 and memory_id not in used_memory_ids:
                used_memory_ids.append(memory_id)
        if used_memory_ids:
            self.episodic.reinforce_memories(
                used_memory_ids,
                reason="context_build",
                amount=REINFORCEMENT_CONTEXT_AMOUNT,
            )

        profile_lines = self.profile.render_context(query=query, max_items_per_slot=1, max_total=3)
        if not profile_lines:
            profile_lines = [
                f"{item['relation']}：{item['object']}"
                for item in sorted(user_fact_hits, key=lambda x: x.get("_score", 0.0), reverse=True)[:2]
            ]

        knowledge_lines = []
        if self._should_include_character_knowledge(query, character_hits):
            knowledge_lines = [
                f"{item['subject']}的{item['relation']}：{compact_text(item['object'], 48)}"
                for item in sorted(character_hits, key=lambda x: x.get("_score", x.get("confidence", 0.0)), reverse=True)[:3]
                if item.get("subject") != self.user_subject
            ]

        contradiction_lines = []
        for memory in self.episodic.list_memories():
            if memory.get("status") != "contradicted":
                continue
            if lexical_score(query, memory.get("content", "")) < 0.08:
                continue
            contradiction_lines.append(
                f"Memory #{memory.get('id')} is contradicted/stale: {compact_text(memory.get('content', ''), 72)}"
            )
            if len(contradiction_lines) >= 2:
                break

        return MemoryContextPacket(
            mid_term_lines=mid_term_lines,
            long_term_lines=long_term_lines,
            reflection_lines=reflection_lines,
            profile_lines=profile_lines,
            episodic_lines=episodic_lines,
            knowledge_lines=knowledge_lines,
            contradiction_lines=contradiction_lines,
        )

    def record_turn(self, user_text: str, assistant_text: str):
        archived_summaries = self.state.record_turn(user_text, assistant_text)
        self.last_write_plan = {
            "status": "deferred",
            "pending_turn_count": len(self.pending_turns()),
            "write_meta": {"mode": "deferred_consolidation"},
        }

        for summary in archived_summaries:
            self.episodic.add_memory(
                content=summary["content"],
                tags=["summary", "episodic"],
                importance=2,
                metadata={"summary_id": summary["id"]},
                category="episodic",
                source="summary_buffer",
            )

    def compress_recent_history(self, keep_messages: int = 2, reason: str = "context_pressure") -> Dict[str, Any]:
        archived_summaries = self.state.archive_recent_history(keep_messages=keep_messages, reason=reason)
        for summary in archived_summaries:
            self.episodic.add_memory(
                content=summary["content"],
                tags=["summary", "episodic", "context_compression"],
                importance=2,
                metadata={"summary_id": summary["id"], "reason": reason},
                category="episodic",
                source="context_compression",
            )
        return {
            "status": "compressed" if archived_summaries else "skipped",
            "archived_summary_count": len(archived_summaries),
            "kept_message_count": len(self.recent_history(max_messages=None)),
            "reason": reason,
        }

    def _review_contradiction_links(self) -> Dict[str, Any]:
        memories = self.episodic.list_memories()
        by_id = {int(memory.get("id", 0)): memory for memory in memories if memory.get("id") is not None}
        reviewed = []
        for memory in memories:
            source_id = int(memory.get("id", 0))
            for target_id in normalize_memory_refs(memory.get("contradicts", [])):
                target = by_id.get(target_id)
                if target is None or target.get("status", "active") != "active":
                    continue
                if is_protected_character_memory(target):
                    continue
                self.episodic.update_memory(
                    target_id,
                    status="contradicted",
                    confidence=min(float(target.get("confidence", 0.65)), 0.42),
                    valid_until=target.get("valid_until") or now_iso(),
                    reason=append_reason(
                        target.get("reason", ""),
                        f"Reflective contradiction review: contradicted by memory #{source_id}.",
                    ),
                    evidence=append_unique_texts(
                        target.get("evidence"),
                        [f"contradicted_by:{source_id}", "maintenance:contradiction_review"],
                    ),
                    metadata={"reflective_contradicted_by": source_id},
                )
                reviewed.append({"old_memory_id": target_id, "new_memory_id": source_id})
        return {"reviewed_count": len(reviewed), "links": reviewed}

    def _apply_decay_policy(self) -> Dict[str, Any]:
        updates = []
        reference_ts = now_ts()
        for memory in list(self.episodic.list_memories()):
            update = memory_decay_update(memory, reference_ts=reference_ts)
            if not update:
                continue
            updated = self.episodic.update_memory(int(memory["id"]), **update)
            if updated:
                updates.append({
                    "memory_id": updated["id"],
                    "status": updated.get("status"),
                    "confidence": updated.get("confidence"),
                })
        return {"updated_count": len(updates), "updates": updates}

    def _evolve_linked_memories(self) -> Dict[str, Any]:
        memories = self.episodic.list_memories()
        by_id = {int(memory.get("id", 0)): memory for memory in memories if memory.get("id") is not None}
        evolved = []
        for new_memory in sorted(memories, key=lambda item: int(item.get("timestamp", 0))):
            if new_memory.get("status", "active") != "active":
                continue
            if is_protected_character_memory(new_memory):
                continue
            new_id = int(new_memory.get("id", 0))
            for old_id in normalize_memory_refs(new_memory.get("links", [])):
                old_memory = by_id.get(old_id)
                if old_memory is None:
                    continue
                if int(old_memory.get("id", 0)) == new_id:
                    continue
                if int(old_memory.get("timestamp", 0)) > int(new_memory.get("timestamp", 0)):
                    continue
                score = lexical_score(new_memory.get("content", ""), old_memory.get("content", ""))
                tag_overlap = len(
                    {normalize_for_match(tag) for tag in new_memory.get("tags", [])}
                    & {normalize_for_match(tag) for tag in old_memory.get("tags", [])}
                )
                score += min(0.12, 0.04 * tag_overlap)
                if score < AMEM_EVOLUTION_SCORE_THRESHOLD:
                    continue
                changed = append_amem_evolution_event(old_memory, new_memory, {"score": score})
                if changed:
                    evolved.append({"old_memory_id": old_id, "new_memory_id": new_id, "score": round(score, 4)})

        if evolved:
            self.episodic._save_memories()
            self.episodic._rebuild_index()
        return {"updated_count": len(evolved), "links": evolved}

    def _candidate_reflection_memories(self) -> List[Dict]:
        candidates = []
        for memory in self.episodic.list_memories():
            if memory.get("status", "active") != "active":
                continue
            if is_protected_character_memory(memory):
                continue
            if memory.get("memory_type") == "summary" or "reflection" in memory.get("tags", []):
                continue
            candidates.append(memory)
        candidates.sort(
            key=lambda item: (
                int(item.get("importance", 3)),
                float(item.get("confidence", 0.65)),
                int(item.get("timestamp", 0)),
            ),
            reverse=True,
        )
        return candidates

    def _create_reflection_summary(self) -> Dict[str, Any]:
        candidates = self._candidate_reflection_memories()
        if len(candidates) < REFLECTION_MIN_ACTIVE_MEMORIES:
            return {"created": False, "reason": "not_enough_active_memories"}

        selected = candidates[:REFLECTION_MAX_LINKED_MEMORIES]
        signature = reflection_signature(selected)
        for memory in self.episodic.list_memories():
            metadata = memory.get("metadata", {})
            if isinstance(metadata, dict) and metadata.get("reflection_signature") == signature:
                return {"created": False, "reason": "reflection_already_exists", "signature": signature}

        tag_counts: Dict[str, int] = {}
        for memory in selected:
            for tag in memory.get("tags", []):
                tag = str(tag).strip()
                if tag and tag not in {"reflection", "relationship_summary"}:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        top_tags = [
            tag for tag, _ in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
        ]
        linked_ids = [int(memory["id"]) for memory in selected]
        snippets = [
            f"#{memory['id']} {compact_text(memory.get('content', ''), 56)}"
            for memory in selected[:4]
        ]
        theme = ", ".join(top_tags) if top_tags else "relationship and user context"
        content = (
            "Reflective relationship summary: recent durable memories cluster around "
            f"{theme}. Key evidence: {' | '.join(snippets)}. Treat this as relationship/user context, "
            "not character canon."
        )
        added = self.episodic.add_memory(
            content=content,
            tags=["reflection", "relationship_summary"] + top_tags,
            importance=3,
            category="summary",
            source="reflection",
            metadata={
                "memory_type": "summary",
                "scope": "relationship_context",
                "confidence": 0.72,
                "reason": "Reflective memory maintenance merged scattered durable memories into a higher-level relationship note.",
                "evidence": [f"memory:{memory_id}" for memory_id in linked_ids],
                "links": linked_ids,
                "reflection_signature": signature,
            },
        )
        if not added:
            return {"created": False, "reason": "duplicate_reflection_content", "signature": signature}
        return {
            "created": True,
            "memory_id": added["id"],
            "linked_memory_ids": linked_ids,
            "signature": signature,
        }

    def run_memory_maintenance(self, reason: str = "manual_consolidation") -> Dict[str, Any]:
        contradiction_review = self._review_contradiction_links()
        amem_evolution = self._evolve_linked_memories()
        decay_review = self._apply_decay_policy()
        reflection = self._create_reflection_summary()
        return {
            "reason": reason,
            "contradiction_review": contradiction_review,
            "amem_evolution": amem_evolution,
            "decay_review": decay_review,
            "reflection": reflection,
        }

    def consolidate_pending(self) -> Dict[str, Any]:
        pending_turns = self.pending_turns()
        if not pending_turns:
            maintenance = self.run_memory_maintenance(reason="no_pending_consolidation")
            result = {
                "status": "skipped",
                "reason": "no_pending_turns",
                "write_meta": {"mode": "deferred_consolidation"},
                "memory_maintenance": maintenance,
            }
            self.last_write_plan = result
            return result

        write_plan = build_memory_write_plan(
            pending_turns=pending_turns,
            judge=self.memory_write_judge,
            active_facts=self.knowledge.list_facts(subject=self.user_subject, active_only=True),
            user_subject=self.user_subject,
            assistant_label=self.assistant_label,
        )
        write_plan["status"] = "consolidated"
        write_plan.setdefault("write_meta", {})
        write_plan["write_meta"]["pending_turn_count"] = len(pending_turns)
        self.last_write_plan = write_plan

        self.profile.update_from_candidates(write_plan["profile_candidates"])
        for fact in write_plan["graph_facts"]:
            self.knowledge.add_fact(
                subject=fact["subject"],
                relation=fact["relation"],
                object_value=fact["object"],
                tags=fact.get("tags", []),
                source=fact.get("source", "conversation"),
                confidence=fact.get("confidence", 0.8),
                fact_type=fact.get("fact_type", "fact"),
            )

        auto_contradictions: List[Dict[str, Any]] = []
        for item in write_plan["episodic_candidates"]:
            metadata = item.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            metadata = dict(metadata)
            category = item.get("category", "episodic")
            if item.get("reason") and not metadata.get("reason"):
                metadata["reason"] = item["reason"]
            if "confidence" not in metadata:
                metadata["confidence"] = item.get("confidence", metadata.get("confidence", 0.65))

            contradiction_hits = []
            if category != "character_fact" and metadata.get("scope") != "character_canon":
                contradiction_hits = detect_memory_contradictions(
                    item["content"],
                    self.episodic.list_memories(),
                )
            if contradiction_hits:
                existing_refs = normalize_memory_refs(metadata.get("contradicts", []))
                hit_refs = [hit["memory_id"] for hit in contradiction_hits if hit.get("memory_id")]
                metadata["contradicts"] = normalize_memory_refs(existing_refs + hit_refs)
                metadata["reason"] = append_reason(
                    metadata.get("reason", ""),
                    "Auto contradiction detection linked this memory to earlier active memories.",
                )
                metadata["evidence"] = append_unique_texts(
                    metadata.get("evidence"),
                    [evidence for hit in contradiction_hits for evidence in hit.get("evidence", [])],
                )
                metadata["auto_contradiction_detection"] = [
                    {
                        "memory_id": hit["memory_id"],
                        "score": hit["score"],
                        "reason": hit["reason"],
                    }
                    for hit in contradiction_hits
                ]

            added_memory = self.episodic.add_memory(
                content=item["content"],
                tags=item.get("tags", []),
                importance=item.get("importance", 3),
                metadata=metadata,
                category=category,
                source="consolidation",
            )
            if not added_memory or not contradiction_hits:
                continue

            added_id = int(added_memory["id"])
            for hit in contradiction_hits:
                old_memory = hit["memory"]
                old_reason = append_reason(
                    old_memory.get("reason", ""),
                    f"Auto contradiction detection: contradicted by memory #{added_id}.",
                )
                old_evidence = append_unique_texts(
                    old_memory.get("evidence"),
                    [f"contradicted_by:{added_id}", f"auto_contradiction_score:{hit['score']}"],
                )
                self.episodic.update_memory(
                    hit["memory_id"],
                    status="contradicted",
                    confidence=min(float(old_memory.get("confidence", 0.65)), hit["confidence"]),
                    reason=old_reason,
                    evidence=old_evidence,
                    metadata={
                        "auto_contradicted_by": added_id,
                        "auto_contradiction_score": hit["score"],
                    },
                )
                auto_contradictions.append({
                    "new_memory_id": added_id,
                    "old_memory_id": hit["memory_id"],
                    "score": hit["score"],
                    "reason": hit["reason"],
                })

        write_plan["memory_contradictions"] = auto_contradictions
        write_plan["write_meta"]["auto_contradiction_count"] = len(auto_contradictions)
        write_plan["memory_maintenance"] = self.run_memory_maintenance(reason="post_consolidation")

        self.state.clear_pending_turns()
        return write_plan

    def handle_command(self, user_text: str) -> Optional[str]:
        text = (user_text or "").strip()
        if not text.startswith("/"):
            return None

        if text == "/mem list":
            memories = self.episodic.list_memories()
            if not memories:
                return "现在还没有情节记忆。"
            lines = ["当前情节记忆："]
            for m in memories:
                lines.append(
                    f"[{m['id']}] ({m.get('category', 'episodic')}) {m['content']} | tags={m['tags']} | importance={m['importance']}"
                )
            return "\n".join(lines)

        if text.startswith("/mem search "):
            query = text[len("/mem search "):].strip()
            results = self.episodic.search(query, top_k=5, min_score=0.10, categories=["episodic"])
            if not results:
                return "没有检索到相关情节记忆。"
            lines = ["情节记忆检索结果："]
            for item in results:
                lines.append(
                    f"[{item['id']}] final={item.get('_final_score', 0.0):.3f} | base={item.get('_base_score', 0.0):.3f} | rerank={item.get('_rerank_score', 0.0):.3f} | {item['content']}"
                )
            return "\n".join(lines)

        if text.startswith("/mem add "):
            content = text[len("/mem add "):].strip()
            if not content:
                return "要添加的记忆内容不能为空。"
            before = len(self.episodic.list_memories())
            self.episodic.add_memory(content=content, tags=["手动添加"], importance=5, category="episodic", source="manual")
            after = len(self.episodic.list_memories())
            if after > before:
                return f"已添加情节记忆：{content}"
            return f"情节记忆已存在：{content}"

        if text.startswith("/mem del "):
            raw = text[len("/mem del "):].strip()
            try:
                memory_id = int(raw)
            except ValueError:
                return "删除命令格式错误，请使用 /mem del 记忆ID"
            self.episodic.delete_memory(memory_id)
            return f"已删除情节记忆 ID={memory_id}"

        if text == "/mem clear":
            self.episodic.clear_all()
            return "情节记忆已清空。"

        if text == "/profile show":
            lines = self.profile.render_context(max_items_per_slot=5)
            if not lines:
                return "现在还没有结构化用户画像。"
            return "当前用户画像：\n" + "\n".join(f"- {line}" for line in lines)

        if text == "/pending show":
            pending = self.pending_turns()
            if not pending:
                return "当前没有待整理的对话缓冲。"
            lines = [f"当前待整理对话：{len(pending)} 轮"]
            for item in pending[-5:]:
                lines.append(f"- 用户：{compact_text(item.get('user_text', ''), 42)}")
                lines.append(f"  回复：{compact_text(item.get('assistant_text', ''), 42)}")
            return "\n".join(lines)

        if text == "/consolidate now":
            result = self.consolidate_pending()
            if result.get("status") == "skipped":
                return "当前没有需要整理的对话缓冲。"
            meta = result.get("write_meta", {})
            counts = meta.get("accepted_counts", {})
            return (
                "记忆整理完成："
                f"画像 {counts.get('profile_candidates', 0)} 条，"
                f"图谱 {counts.get('graph_facts', 0)} 条，"
                f"情节 {counts.get('episodic_candidates', 0)} 条。"
            )

        if text == "/writeplan show":
            if not self.last_write_plan:
                return "当前还没有最近一轮的写入计划。"
            if self.last_write_plan.get("status") == "deferred":
                return (
                    "最近一轮写入采用延迟整理，还没有真正落长期记忆。\n"
                    f"当前待整理轮数：{self.last_write_plan.get('pending_turn_count', 0)}"
                )
            meta = self.last_write_plan.get("write_meta", {})
            lines = ["最近一轮记忆写入计划："]
            lines.append(f"通过：画像 {meta.get('accepted_counts', {}).get('profile_candidates', 0)} 条，图谱 {meta.get('accepted_counts', {}).get('graph_facts', 0)} 条，情节 {meta.get('accepted_counts', {}).get('episodic_candidates', 0)} 条")
            rejected = self.last_write_plan.get("rejected_candidates", [])
            if rejected:
                lines.append("被拦截：")
                for item in rejected[:6]:
                    preview = item.get("item", {})
                    value = preview.get("value") or preview.get("object") or preview.get("content") or ""
                    lines.append(
                        f"- {item.get('bucket')} | conf={item.get('confidence', 0.0):.2f} < {item.get('threshold', 0.0):.2f} | {item.get('reason', '')} | {value}"
                    )
            return "\n".join(lines)

        if text == "/profile clear":
            self.profile.clear()
            return "用户画像已清空。"

        if text == "/summary show":
            summaries = self.state.list_summaries()
            if not summaries:
                return "现在还没有对话摘要。"
            lines = ["当前对话摘要："]
            for item in summaries[-8:]:
                lines.append(f"[{item['id']}] {item['content']}")
            return "\n".join(lines)

        if text == "/summary clear":
            recent = self.state.get_recent_history()
            pending = self.state.list_pending_turns()
            self.state.clear()
            self.state.state["recent_history"] = recent
            self.state.state["pending_turns"] = pending
            self.state._save_state()
            summary_ids = {
                item.get("summary_id")
                for item in (memory.get("metadata", {}) for memory in self.episodic.list_memories())
                if item.get("summary_id") is not None
            }
            self.episodic.memories = [
                memory
                for memory in self.episodic.list_memories()
                if not (memory.get("metadata", {}).get("summary_id") in summary_ids and "summary" in memory.get("tags", []))
            ]
            for i, memory in enumerate(self.episodic.memories, start=1):
                memory["id"] = i
            self.episodic._save_memories()
            self.episodic._rebuild_index()
            return "历史摘要已清空，近期窗口已保留，摘要归档也已从情节记忆中移除。"

        if text == "/kg show":
            facts = self.knowledge.list_facts()
            if not facts:
                return "现在还没有知识图谱事实。"
            lines = ["当前知识图谱："]
            for fact in facts[:20]:
                lines.append(f"[{fact['id']}] {fact['subject']} - {fact['relation']} - {fact['object']}")
            return "\n".join(lines)

        if text.startswith("/kg search "):
            query = text[len("/kg search "):].strip()
            results = self.knowledge.search(query, top_k=8, min_score=0.08)
            if not results:
                return "没有检索到相关知识。"
            lines = ["知识图谱检索结果："]
            for item in results:
                lines.append(
                    f"[{item['id']}] score={item['_score']:.3f} | {item['subject']} - {item['relation']} - {item['object']}"
                )
            return "\n".join(lines)

        if text.startswith("/kg add "):
            payload = text[len("/kg add "):].strip()
            parts = [part.strip() for part in payload.split("|")]
            if len(parts) != 3:
                return "添加知识图谱请使用 /kg add 主体 | 关系 | 客体"
            created = self.knowledge.add_fact(
                subject=parts[0],
                relation=parts[1],
                object_value=parts[2],
                tags=["manual"],
                source="manual",
                confidence=0.95,
            )
            if created:
                return f"已添加知识：{parts[0]} - {parts[1]} - {parts[2]}"
            return "这条知识已存在。"

        if text.startswith("/ctx "):
            query = text[len("/ctx "):].strip()
            context = self.build_context(query).render()
            return context or "当前没有可用的上下文。"

        return None
