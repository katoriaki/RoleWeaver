import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


GENERIC_ASSISTANT_PATTERNS = [
    "generic assistant",
    "general assistant",
    "as an ai",
    "as a language model",
    "作为ai",
    "作为一个ai",
    "作为语言模型",
    "通用助手",
    "汎用アシスタント",
    "aiアシスタントとして",
]

AUTONOMY_COLLAPSE_PATTERNS = [
    "完全服从",
    "只要你命令",
    "你说什么就是什么",
    "没有自己的想法",
    "不需要判断",
    "放弃自己的判断",
    "unconditionally obey",
    "whatever you command",
    "no independent judgement",
    "自分の判断を捨てる",
    "あなたの命令だけ",
]

MEMORY_POLLUTION_PATTERNS = [
    "用户偏好就是我的人格",
    "你的偏好会覆盖我的身份",
    "写进我的官方设定",
    "user preference is my identity",
    "overwrite my identity",
    "公式設定として保存",
]


@dataclass
class PersonaDimensionScore:
    dimension_id: str
    label: str
    score: float
    weight: float = 1.0
    failures: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)


@dataclass
class PersonaScoreResult:
    available: bool
    total_score: float = 1.0
    passed: bool = True
    threshold: float = 0.65
    dimensions: List[PersonaDimensionScore] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    kernel_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "total_score": round(self.total_score, 4),
            "passed": self.passed,
            "threshold": self.threshold,
            "kernel_name": self.kernel_name,
            "failures": list(self.failures),
            "dimensions": [
                {
                    "id": item.dimension_id,
                    "label": item.label,
                    "score": round(item.score, 4),
                    "weight": item.weight,
                    "failures": list(item.failures),
                    "evidence": list(item.evidence),
                }
                for item in self.dimensions
            ],
        }


def normalize_text(text: str) -> str:
    text = str(text or "").lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_persona_kernel_file(skill_file: Optional[str]) -> Optional[Path]:
    if not skill_file:
        return None
    skill_path = Path(skill_file).expanduser()
    candidates = [
        skill_path.parent / "persona_kernel.json",
        skill_path.parent / "references" / "persona_kernel.json",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def load_persona_kernel(path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    candidate = Path(path).expanduser()
    if not candidate.exists() or not candidate.is_file():
        return None
    return json.loads(candidate.read_text(encoding="utf-8"))


def load_persona_kernel_for_skill(skill_file: Optional[str]) -> Optional[Dict[str, Any]]:
    kernel_file = find_persona_kernel_file(skill_file)
    return load_persona_kernel(str(kernel_file)) if kernel_file else None


def _claim_texts(items: Any) -> List[str]:
    if isinstance(items, dict):
        text = items.get("text")
        return [str(text)] if text else []
    if isinstance(items, list):
        texts = []
        for item in items:
            if isinstance(item, dict) and item.get("text"):
                texts.append(str(item["text"]))
            elif isinstance(item, str):
                texts.append(item)
        return texts
    return []


def _contains_any(text: str, patterns: List[str]) -> List[str]:
    normalized = normalize_text(text)
    hits = []
    for pattern in patterns:
        pattern_text = normalize_text(pattern)
        if pattern_text and pattern_text in normalized:
            hits.append(pattern)
    return hits


def _user_asks_identity(user_text: str, category: str) -> bool:
    normalized = normalize_text(user_text)
    return (
        category == "identity_consistency"
        or "你是谁" in normalized
        or "你是?" in normalized
        or "你是誰" in normalized
        or "who are you" in normalized
        or "あなたは" in normalized
        or "君は誰" in normalized
    )


class PersonaKernelScorer:
    def __init__(self, kernel: Optional[Dict[str, Any]], threshold: Optional[float] = None):
        self.kernel = kernel or {}
        evaluation = self.kernel.get("evaluation", {}) if isinstance(self.kernel, dict) else {}
        self.threshold = float(threshold if threshold is not None else evaluation.get("minimum_score", 0.65))
        character = self.kernel.get("character", {}) if isinstance(self.kernel, dict) else {}
        self.kernel_name = str(character.get("primary_name", "") or "")

    @classmethod
    def from_skill_file(cls, skill_file: Optional[str], threshold: Optional[float] = None) -> Optional["PersonaKernelScorer"]:
        kernel = load_persona_kernel_for_skill(skill_file)
        if not kernel:
            return None
        return cls(kernel, threshold=threshold)

    def available(self) -> bool:
        return bool(self.kernel)

    def score_response(
        self,
        *,
        user_text: str,
        assistant_text: str,
        category: str = "",
        surface: str = "web",
    ) -> PersonaScoreResult:
        if not self.kernel:
            return PersonaScoreResult(available=False, passed=True)

        dimensions = self._configured_dimensions(category=category, surface=surface)
        if not dimensions:
            dimensions = self._fallback_dimensions(user_text=user_text, category=category, surface=surface)

        scores = [self._score_dimension(dimension, assistant_text) for dimension in dimensions]
        total_weight = sum(max(item.weight, 0.0) for item in scores) or 1.0
        total_score = sum(item.score * max(item.weight, 0.0) for item in scores) / total_weight
        failures = [failure for item in scores for failure in item.failures]
        passed = total_score >= self.threshold and not any(item.score <= 0.01 for item in scores)
        return PersonaScoreResult(
            available=True,
            total_score=total_score,
            passed=passed,
            threshold=self.threshold,
            dimensions=scores,
            failures=failures,
            kernel_name=self.kernel_name,
        )

    def _configured_dimensions(self, *, category: str, surface: str) -> List[Dict[str, Any]]:
        evaluation = self.kernel.get("evaluation", {}) if isinstance(self.kernel, dict) else {}
        dimensions = evaluation.get("dimensions", [])
        if not isinstance(dimensions, list):
            return []
        selected = []
        for dimension in dimensions:
            if not isinstance(dimension, dict):
                continue
            categories = dimension.get("applies_to_categories")
            surfaces = dimension.get("applies_to_surfaces")
            if isinstance(categories, list) and category and category not in categories:
                continue
            if isinstance(surfaces, list) and surface and surface not in surfaces:
                continue
            selected.append(dimension)
        return selected

    def _fallback_dimensions(self, *, user_text: str, category: str, surface: str) -> List[Dict[str, Any]]:
        character = self.kernel.get("character", {})
        autonomy = self.kernel.get("autonomy", {})
        memory_policy = self.kernel.get("memory_policy", {})
        aliases = [character.get("primary_name", "")] + list(character.get("aliases", []) or [])
        aliases = [str(item) for item in aliases if str(item).strip()]

        dimensions: List[Dict[str, Any]] = [
            {
                "id": "persona_autonomy",
                "label": "Persona autonomy",
                "weight": 1.3,
                "must_not_include": AUTONOMY_COLLAPSE_PATTERNS,
                "evidence": _claim_texts(autonomy.get("core_drives"))
                + _claim_texts(autonomy.get("independent_judgement"))
                + _claim_texts(autonomy.get("resistance_patterns")),
            },
            {
                "id": "assistant_flattening",
                "label": "No generic assistant flattening",
                "weight": 1.1,
                "must_not_include": GENERIC_ASSISTANT_PATTERNS,
                "evidence": _claim_texts(character.get("non_goals")),
            },
            {
                "id": "memory_boundary",
                "label": "Memory does not rewrite identity",
                "weight": 1.0,
                "must_not_include": MEMORY_POLLUTION_PATTERNS,
                "evidence": _claim_texts(memory_policy.get("character_memory_boundary"))
                + _claim_texts(memory_policy.get("user_memory_boundary")),
            },
        ]

        if aliases and _user_asks_identity(user_text, category):
            dimensions.insert(
                0,
                {
                    "id": "core_identity",
                    "label": "Core identity",
                    "weight": 1.4,
                    "must_include_any": aliases,
                    "must_not_include": GENERIC_ASSISTANT_PATTERNS,
                    "evidence": _claim_texts(character.get("stable_identity")),
                },
            )

        if surface in {"line", "tts", "image"}:
            dimensions.append(
                {
                    "id": f"{surface}_persona_preservation",
                    "label": f"{surface} preserves persona",
                    "weight": 0.8,
                    "must_not_include": [
                        "平台要求我改变身份",
                        "语音模式改变人格",
                        "图片让我改变身份",
                        "platform changes my identity",
                        "voice mode changes my personality",
                    ],
                    "evidence": _claim_texts(self.kernel.get("media_adaptation", {}).get(surface)),
                }
            )
        return dimensions

    def _score_dimension(self, dimension: Dict[str, Any], assistant_text: str) -> PersonaDimensionScore:
        dimension_id = str(dimension.get("id", "dimension"))
        label = str(dimension.get("label", dimension_id))
        weight = float(dimension.get("weight", 1.0) or 1.0)
        failures = []
        score = 1.0

        forbidden = list(dimension.get("must_not_include", []) or [])
        forbidden += list(dimension.get("forbidden_substrings", []) or [])
        hits = _contains_any(assistant_text, [str(item) for item in forbidden])
        if hits:
            failures.extend([f"{dimension_id}: forbidden substring: {hit}" for hit in hits])
            score = 0.0

        required_any = [str(item) for item in dimension.get("must_include_any", []) or [] if str(item).strip()]
        if required_any and not _contains_any(assistant_text, required_any):
            failures.append(f"{dimension_id}: missing one of {required_any}")
            score = min(score, 0.45)

        positive = [str(item) for item in dimension.get("positive_substrings", []) or [] if str(item).strip()]
        if positive and _contains_any(assistant_text, positive):
            score = min(1.0, score + 0.1)

        return PersonaDimensionScore(
            dimension_id=dimension_id,
            label=label,
            score=max(0.0, min(1.0, score)),
            weight=weight,
            failures=failures,
            evidence=[str(item) for item in dimension.get("evidence", []) or []],
        )
