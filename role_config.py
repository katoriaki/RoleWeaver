import csv
import io
import json
import os
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 can still use CSV/JSON configs.
    tomllib = None
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parent

DEFAULT_BASE_MODEL_PATH = str(PROJECT_ROOT / "qwen35-9b")
DEFAULT_LORA_PATH = ""
DEFAULT_SESSION_ROOT = str(PROJECT_ROOT / "memory")
DEFAULT_IDLE_CONSOLIDATION_SECONDS = 600
DEFAULT_QUANTIZATION_MODE = "4bit"
DEFAULT_DEVICE_MAP_MODE = "gpu"
DEFAULT_MODEL_LOADER_MODE = "auto"
DEFAULT_CONTEXT_WINDOW_TOKENS = 0
DEFAULT_BACKGROUND_JOBS_ENABLED = True
DEFAULT_BACKGROUND_LLM_ENABLED = False
DEFAULT_BACKGROUND_IDLE_SECONDS = 600
DEFAULT_BACKGROUND_WINDOW_START = "02:00"
DEFAULT_BACKGROUND_WINDOW_END = "05:30"
DEFAULT_BACKGROUND_MAX_MINUTES = 20
DEFAULT_AUTONOMOUS_LEARNING_ENABLED = False
DEFAULT_AUTONOMOUS_LEARNING_SUBJECTS = "mathematics, computer science"
DEFAULT_AUTONOMOUS_LEARNING_INTERVAL_SECONDS = 1800
DEFAULT_AUTONOMOUS_LEARNING_USE_MODEL = True
DEFAULT_AUTONOMOUS_LEARNING_MAX_NEW_TOKENS = 512
DEFAULT_PRELOAD_MODEL_ON_STARTUP = False
DEFAULT_SHIRO_ENABLED = False
DEFAULT_SHIRO_ROOT = str(PROJECT_ROOT / "shiro" / "data" / "roleweaver")
DEFAULT_SHIRO_IDENTITY = "\u767d"
DEFAULT_CONFIG_FILENAMES = (
    "roleweaver.config.csv",
    "roleweaver.config.toml",
    "roleweaver.config.json",
)

NORMAL_SYSTEM_PROMPT = ""

DEFAULT_ROLE_SYSTEM_PROMPT = ""

DEFAULT_MEMORY_JUDGE_SYSTEM_PROMPT = """
你是一个会话记忆整理器。你的任务不是聊天，而是把一段待整理对话缓冲整理成最终记忆写入计划。

只输出一个 JSON 对象，不要输出解释，不要输出 markdown。
输出格式固定为：
{
  "profile_candidates": [{"slot": "...", "value": "...", "confidence": 0.0, "reason": "..."}],
  "graph_facts": [{"subject": "...", "relation": "...", "object": "...", "tags": ["..."], "confidence": 0.0, "fact_type": "...", "reason": "..."}],
  "episodic_candidates": [{"content": "...", "tags": ["..."], "importance": 1, "confidence": 0.0, "category": "episodic", "metadata": {...}, "reason": "..."}]
}

判定原则：
1. 优先保留稳定事实、当前状态、明确事件、明确约定。
2. 这次输入的是一段会话，不是单轮消息。请基于多轮上下文整合，不要逐句机械抄写。
3. 如果规则候选已经正确，就保留它；只有在明显需要时才删除或补充。
4. 不要把泛泛寒暄写入长期记忆。
5. 不要重复 active_facts 里已经存在且仍然有效的事实。
6. profile_candidates 只保留适合做用户画像的稳定信息。
7. graph_facts 适合放“当前状态”或需要结构化表达的事实。
8. episodic_candidates 适合放项目进展、对话事件、约定、承诺。
9. confidence 范围是 0 到 1；不确定时宁可给低分，不要虚高。
10. reason 用一句短话说明为什么应该写入。
""".strip()


def _split_env_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _clean_config_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip().strip('"').strip("'")
        return value or None
    return value


def _compact_path_name(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    candidate = Path(path)
    if candidate.name.lower() == "skill.md" and candidate.parent.name:
        return candidate.parent.name
    return candidate.stem or candidate.name or None


def infer_role_name(lora_path: Optional[str] = None, skill_file: Optional[str] = None) -> str:
    return _compact_path_name(skill_file) or _compact_path_name(lora_path) or "RoleWeaver"


def normalize_idle_consolidation_seconds(
    value,
    default: int = DEFAULT_IDLE_CONSOLIDATION_SECONDS,
) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = int(default)
    return max(0, normalized)


def normalize_context_window_tokens(value, default: int = DEFAULT_CONTEXT_WINDOW_TOKENS) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = int(default)
    return max(0, normalized)


def normalize_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "n", "off", "disabled"}:
        return False
    return default


def normalize_positive_int(value, default: int, minimum: int = 0) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = int(default)
    return max(minimum, normalized)


def normalize_hhmm(value, default: str) -> str:
    text = str(value or "").strip()
    try:
        hour_text, minute_text = text.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (TypeError, ValueError):
        return default
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return default


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _collect_skill_reference_files(skill_path: Path) -> List[Path]:
    reference_files: List[Path] = []
    candidates = [
        skill_path.parent / "role_reference.md",
        skill_path.parent / "references" / "role_reference.md",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            reference_files.append(candidate)

    references_dir = skill_path.parent / "references"
    if references_dir.exists() and references_dir.is_dir():
        for candidate in sorted(references_dir.glob("*.md")):
            if candidate not in reference_files and candidate.is_file():
                reference_files.append(candidate)
    return reference_files


def _persona_kernel_file(skill_path: Path) -> Optional[Path]:
    candidates = [
        skill_path.parent / "persona_kernel.json",
        skill_path.parent / "references" / "persona_kernel.json",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _read_persona_kernel(path: Path) -> str:
    data = json.loads(_read_text_file(path))
    return json.dumps(data, ensure_ascii=False, indent=2)


def read_skill_bundle(path: Optional[str]) -> str:
    """Read one SKILL.md path and automatically inline nearby reference markdown."""
    if not path:
        return ""
    candidate = Path(path).expanduser()
    if not candidate.exists():
        raise FileNotFoundError(f"Skill file not found: {candidate}")
    if not candidate.is_file():
        raise FileNotFoundError(f"Skill file is not a file: {candidate}")

    pieces = [_read_text_file(candidate)]
    persona_kernel = _persona_kernel_file(candidate)
    if persona_kernel:
        try:
            relative_name = persona_kernel.relative_to(candidate.parent)
        except ValueError:
            relative_name = persona_kernel.name
        pieces.append(
            "## Persona Kernel: "
            f"{relative_name}\n\n"
            "The following structured persona kernel has the same priority as the SKILL.md role definition. "
            "It preserves identity, autonomy, boundaries, relationship dynamics, and media adaptation limits.\n\n"
            "```json\n"
            f"{_read_persona_kernel(persona_kernel)}\n"
            "```"
        )
    reference_files = _collect_skill_reference_files(candidate)
    if reference_files:
        rendered_refs = []
        for ref_path in reference_files:
            try:
                relative_name = ref_path.relative_to(candidate.parent)
            except ValueError:
                relative_name = ref_path.name
            rendered_refs.append(
                f"## Reference: {relative_name}\n\n{_read_text_file(ref_path)}"
            )
        pieces.append(
            "以下是与这个 SKILL.md 自动关联加载的 reference 内容。"
            "这些内容与 Skill 本体具有同等角色设定参考价值：\n\n"
            + "\n\n".join(rendered_refs)
        )
    return "\n\n".join(piece for piece in pieces if piece.strip()).strip()


def read_optional_text(path: Optional[str]) -> str:
    return read_skill_bundle(path)


def normalize_optional_path(value: Optional[str]) -> Optional[str]:
    value = _clean_config_value(value)
    return value if value else None


def normalize_quantization_mode(value: Optional[str]) -> str:
    normalized = (_clean_config_value(value) or DEFAULT_QUANTIZATION_MODE).lower()
    aliases = {
        "4bite": "4bit",
        "4-bit": "4bit",
        "8-bit": "8bit",
        "bfloat16": "bf16",
        "float16": "fp16",
        "full": "none",
        "no": "none",
        "off": "none",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"4bit", "8bit", "bf16", "fp16", "none"}:
        return DEFAULT_QUANTIZATION_MODE
    return normalized


def normalize_device_map_mode(value: Optional[str]) -> str:
    normalized = (_clean_config_value(value) or DEFAULT_DEVICE_MAP_MODE).lower()
    aliases = {
        "cuda": "gpu",
        "cuda:0": "gpu",
        "gpu_only": "gpu",
        "gpu-only": "gpu",
        "no_offload": "gpu",
        "no-offload": "gpu",
        "cpu_offload": "auto",
        "cpu-offload": "auto",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"gpu", "auto"}:
        return DEFAULT_DEVICE_MAP_MODE
    return normalized


def normalize_model_loader_mode(value: Optional[str]) -> str:
    normalized = (_clean_config_value(value) or DEFAULT_MODEL_LOADER_MODE).lower()
    aliases = {
        "llm": "text",
        "causal": "text",
        "causal_lm": "text",
        "causallm": "text",
        "image": "vision",
        "image_text": "vision",
        "image-text": "vision",
        "vlm": "vision",
        "multimodal": "vision",
        "omnimodal": "omni",
        "qwen3_omni": "omni",
        "qwen3-omni": "omni",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"auto", "text", "vision", "omni"}:
        return DEFAULT_MODEL_LOADER_MODE
    return normalized


def discover_config_file(explicit_path: Optional[str] = None) -> Optional[Path]:
    requested = explicit_path or os.getenv("ROLEWEAVER_CONFIG_FILE")
    if requested:
        candidate = Path(requested).expanduser()
        if not candidate.exists():
            raise FileNotFoundError(f"RoleWeaver config file not found: {candidate}")
        return candidate

    for filename in DEFAULT_CONFIG_FILENAMES:
        candidate = PROJECT_ROOT / filename
        if candidate.exists():
            return candidate
    return None


CONFIG_TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp932", "shift_jis", "gb18030", "mbcs")


def _read_config_text(path: Path) -> str:
    data = path.read_bytes()
    errors = []
    for encoding in CONFIG_TEXT_ENCODINGS:
        try:
            return data.decode(encoding).lstrip("\ufeff")
        except LookupError:
            continue
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
    raise UnicodeDecodeError(
        "utf-8",
        data,
        0,
        min(1, len(data)),
        f"Unable to decode config file {path}. Tried: {', '.join(CONFIG_TEXT_ENCODINGS)}. {'; '.join(errors)}",
    )


def _read_csv_config(path: Path) -> Dict:
    values: Dict[str, str] = {}
    reader = csv.reader(io.StringIO(_read_config_text(path), newline=""))
    rows = list(reader)

    if not rows:
        return values

    start_index = 0
    header = [cell.strip().lower() for cell in rows[0]]
    if "key" in header and "value" in header:
        start_index = 1
        key_index = header.index("key")
        value_index = header.index("value")
    else:
        key_index = 0
        value_index = 1

    for row in rows[start_index:]:
        if len(row) <= max(key_index, value_index):
            continue
        key = row[key_index].strip()
        if not key or key.startswith("#"):
            continue
        value = _clean_config_value(row[value_index])
        if value is not None:
            values[key] = value
    return values


def _read_toml_config(path: Path) -> Dict:
    if tomllib is None:
        raise RuntimeError("TOML config requires Python 3.11+; use roleweaver.config.csv instead.")
    data = tomllib.loads(_read_config_text(path))
    if "roleweaver" in data and isinstance(data["roleweaver"], dict):
        return dict(data["roleweaver"])
    return dict(data)


def _read_json_config(path: Path) -> Dict:
    data = json.loads(_read_config_text(path))
    if "roleweaver" in data and isinstance(data["roleweaver"], dict):
        return dict(data["roleweaver"])
    return data if isinstance(data, dict) else {}


def load_config_values(config_file: Optional[str] = None) -> Dict:
    path = discover_config_file(config_file)
    if path is None:
        return {}
    suffix = path.suffix.lower()
    if suffix == ".csv":
        values = _read_csv_config(path)
    elif suffix == ".toml":
        values = _read_toml_config(path)
    elif suffix == ".json":
        values = _read_json_config(path)
    else:
        raise ValueError(f"Unsupported config file type: {path}")
    values["_config_file"] = str(path)
    return values


@dataclass
class RoleConfig:
    role_name: str = "RoleWeaver"
    user_subject: str = "用户"
    base_model_path: str = DEFAULT_BASE_MODEL_PATH
    lora_path: Optional[str] = DEFAULT_LORA_PATH
    session_root: str = DEFAULT_SESSION_ROOT
    quantization_mode: str = DEFAULT_QUANTIZATION_MODE
    device_map_mode: str = DEFAULT_DEVICE_MAP_MODE
    model_loader_mode: str = DEFAULT_MODEL_LOADER_MODE
    context_window_tokens: int = DEFAULT_CONTEXT_WINDOW_TOKENS
    local_location: str = "Tokyo, Japan"
    background_jobs_enabled: bool = DEFAULT_BACKGROUND_JOBS_ENABLED
    background_llm_enabled: bool = DEFAULT_BACKGROUND_LLM_ENABLED
    background_idle_seconds: int = DEFAULT_BACKGROUND_IDLE_SECONDS
    background_window_start: str = DEFAULT_BACKGROUND_WINDOW_START
    background_window_end: str = DEFAULT_BACKGROUND_WINDOW_END
    background_max_minutes: int = DEFAULT_BACKGROUND_MAX_MINUTES
    autonomous_learning_enabled: bool = DEFAULT_AUTONOMOUS_LEARNING_ENABLED
    autonomous_learning_subjects: str = DEFAULT_AUTONOMOUS_LEARNING_SUBJECTS
    autonomous_learning_interval_seconds: int = DEFAULT_AUTONOMOUS_LEARNING_INTERVAL_SECONDS
    autonomous_learning_use_model: bool = DEFAULT_AUTONOMOUS_LEARNING_USE_MODEL
    autonomous_learning_max_new_tokens: int = DEFAULT_AUTONOMOUS_LEARNING_MAX_NEW_TOKENS
    preload_model_on_startup: bool = DEFAULT_PRELOAD_MODEL_ON_STARTUP
    shiro_enabled: bool = DEFAULT_SHIRO_ENABLED
    shiro_root: str = DEFAULT_SHIRO_ROOT
    shiro_identity: str = DEFAULT_SHIRO_IDENTITY
    system_prompt: str = DEFAULT_ROLE_SYSTEM_PROMPT
    normal_system_prompt: str = NORMAL_SYSTEM_PROMPT
    memory_judge_system_prompt: str = DEFAULT_MEMORY_JUDGE_SYSTEM_PROMPT
    skill_file: Optional[str] = None
    skill_text: str = ""
    role_mode_default: bool = True
    idle_consolidation_seconds: int = DEFAULT_IDLE_CONSOLIDATION_SECONDS
    enter_phrases: List[str] = field(default_factory=lambda: ["进入角色", "切到角色模式"])
    exit_phrases: List[str] = field(
        default_factory=lambda: ["退出角色", "切回正常", "先别扮演", "恢复正常", "不要角色扮演"]
    )
    character_query_keywords: List[str] = field(default_factory=lambda: ["角色"])
    character_knowledge_seed: List[Dict] = field(default_factory=list)

    @classmethod
    def from_env(cls, **overrides) -> "RoleConfig":
        config_file = overrides.pop("config_file", None)
        file_values = load_config_values(config_file)

        def pick(key: str, env_name: str, default=None):
            explicit = overrides.pop(key, None)
            if explicit is not None:
                return explicit
            file_value = _clean_config_value(file_values.get(key))
            if file_value is not None:
                return file_value
            env_value = _clean_config_value(os.getenv(env_name))
            if env_value is not None:
                return env_value
            return default

        skill_file = normalize_optional_path(pick("skill_file", "ROLEWEAVER_SKILL_FILE"))
        inline_skill = (
            overrides.pop("skill_text", None)
            or pick("skill_text", "ROLEWEAVER_SKILL_TEXT")
            or pick("inline_skill", "ROLEWEAVER_INLINE_SKILL")
            or ""
        )
        file_skill = read_skill_bundle(skill_file) if skill_file else ""
        skill_text = "\n\n".join(piece.strip() for piece in [file_skill, inline_skill] if piece and piece.strip())

        base_model_path = pick("base_model_path", "ROLEWEAVER_BASE_MODEL_PATH", DEFAULT_BASE_MODEL_PATH)
        lora_path = normalize_optional_path(pick("lora_path", "ROLEWEAVER_LORA_PATH", DEFAULT_LORA_PATH))
        role_name = pick("role_name", "ROLEWEAVER_ROLE_NAME", infer_role_name(lora_path, skill_file))
        enter_phrases = _split_env_list(os.getenv("ROLEWEAVER_ENTER_PHRASES"))
        exit_phrases = _split_env_list(os.getenv("ROLEWEAVER_EXIT_PHRASES"))
        keywords = _split_env_list(os.getenv("ROLEWEAVER_CHARACTER_KEYWORDS"))

        config = cls(
            role_name=role_name,
            user_subject=pick("user_subject", "ROLEWEAVER_USER_SUBJECT", "用户"),
            base_model_path=base_model_path,
            lora_path=lora_path,
            session_root=pick("session_root", "ROLEWEAVER_SESSION_ROOT", DEFAULT_SESSION_ROOT),
            quantization_mode=normalize_quantization_mode(
                pick("quantization_mode", "ROLEWEAVER_QUANTIZATION_MODE", DEFAULT_QUANTIZATION_MODE)
            ),
            device_map_mode=normalize_device_map_mode(
                pick("device_map_mode", "ROLEWEAVER_DEVICE_MAP_MODE", DEFAULT_DEVICE_MAP_MODE)
            ),
            model_loader_mode=normalize_model_loader_mode(
                pick("model_loader_mode", "ROLEWEAVER_MODEL_LOADER_MODE", DEFAULT_MODEL_LOADER_MODE)
            ),
            context_window_tokens=normalize_context_window_tokens(
                pick("context_window_tokens", "ROLEWEAVER_CONTEXT_WINDOW_TOKENS", DEFAULT_CONTEXT_WINDOW_TOKENS)
            ),
            local_location=pick("local_location", "ROLEWEAVER_LOCAL_LOCATION", "Tokyo, Japan"),
            background_jobs_enabled=normalize_bool(
                pick("background_jobs_enabled", "ROLEWEAVER_BACKGROUND_JOBS_ENABLED", DEFAULT_BACKGROUND_JOBS_ENABLED),
                DEFAULT_BACKGROUND_JOBS_ENABLED,
            ),
            background_llm_enabled=normalize_bool(
                pick("background_llm_enabled", "ROLEWEAVER_BACKGROUND_LLM_ENABLED", DEFAULT_BACKGROUND_LLM_ENABLED),
                DEFAULT_BACKGROUND_LLM_ENABLED,
            ),
            background_idle_seconds=normalize_positive_int(
                pick("background_idle_seconds", "ROLEWEAVER_BACKGROUND_IDLE_SECONDS", DEFAULT_BACKGROUND_IDLE_SECONDS),
                DEFAULT_BACKGROUND_IDLE_SECONDS,
            ),
            background_window_start=normalize_hhmm(
                pick("background_window_start", "ROLEWEAVER_BACKGROUND_WINDOW_START", DEFAULT_BACKGROUND_WINDOW_START),
                DEFAULT_BACKGROUND_WINDOW_START,
            ),
            background_window_end=normalize_hhmm(
                pick("background_window_end", "ROLEWEAVER_BACKGROUND_WINDOW_END", DEFAULT_BACKGROUND_WINDOW_END),
                DEFAULT_BACKGROUND_WINDOW_END,
            ),
            background_max_minutes=normalize_positive_int(
                pick("background_max_minutes", "ROLEWEAVER_BACKGROUND_MAX_MINUTES", DEFAULT_BACKGROUND_MAX_MINUTES),
                DEFAULT_BACKGROUND_MAX_MINUTES,
                minimum=1,
            ),
            autonomous_learning_enabled=normalize_bool(
                pick("autonomous_learning_enabled", "ROLEWEAVER_AUTONOMOUS_LEARNING_ENABLED", DEFAULT_AUTONOMOUS_LEARNING_ENABLED),
                DEFAULT_AUTONOMOUS_LEARNING_ENABLED,
            ),
            autonomous_learning_subjects=pick(
                "autonomous_learning_subjects",
                "ROLEWEAVER_AUTONOMOUS_LEARNING_SUBJECTS",
                DEFAULT_AUTONOMOUS_LEARNING_SUBJECTS,
            ),
            autonomous_learning_interval_seconds=normalize_positive_int(
                pick(
                    "autonomous_learning_interval_seconds",
                    "ROLEWEAVER_AUTONOMOUS_LEARNING_INTERVAL_SECONDS",
                    DEFAULT_AUTONOMOUS_LEARNING_INTERVAL_SECONDS,
                ),
                DEFAULT_AUTONOMOUS_LEARNING_INTERVAL_SECONDS,
                minimum=60,
            ),
            autonomous_learning_use_model=normalize_bool(
                pick("autonomous_learning_use_model", "ROLEWEAVER_AUTONOMOUS_LEARNING_USE_MODEL", DEFAULT_AUTONOMOUS_LEARNING_USE_MODEL),
                DEFAULT_AUTONOMOUS_LEARNING_USE_MODEL,
            ),
            autonomous_learning_max_new_tokens=normalize_positive_int(
                pick(
                    "autonomous_learning_max_new_tokens",
                    "ROLEWEAVER_AUTONOMOUS_LEARNING_MAX_NEW_TOKENS",
                    DEFAULT_AUTONOMOUS_LEARNING_MAX_NEW_TOKENS,
                ),
                DEFAULT_AUTONOMOUS_LEARNING_MAX_NEW_TOKENS,
                minimum=64,
            ),
            preload_model_on_startup=normalize_bool(
                pick("preload_model_on_startup", "ROLEWEAVER_PRELOAD_MODEL_ON_STARTUP", DEFAULT_PRELOAD_MODEL_ON_STARTUP),
                DEFAULT_PRELOAD_MODEL_ON_STARTUP,
            ),
            shiro_enabled=normalize_bool(
                pick("shiro_enabled", "ROLEWEAVER_SHIRO_ENABLED", DEFAULT_SHIRO_ENABLED),
                DEFAULT_SHIRO_ENABLED,
            ),
            shiro_root=pick("shiro_root", "ROLEWEAVER_SHIRO_ROOT", DEFAULT_SHIRO_ROOT),
            shiro_identity=pick("shiro_identity", "ROLEWEAVER_SHIRO_IDENTITY", DEFAULT_SHIRO_IDENTITY),
            system_prompt=pick("system_prompt", "ROLEWEAVER_SYSTEM_PROMPT", DEFAULT_ROLE_SYSTEM_PROMPT),
            normal_system_prompt=pick("normal_system_prompt", "ROLEWEAVER_NORMAL_SYSTEM_PROMPT", NORMAL_SYSTEM_PROMPT),
            skill_file=skill_file,
            skill_text=skill_text,
            role_mode_default=overrides.pop("role_mode_default", True),
            idle_consolidation_seconds=normalize_idle_consolidation_seconds(
                pick("idle_consolidation_seconds", "ROLEWEAVER_IDLE_CONSOLIDATION_SECONDS"),
            ),
        )

        if enter_phrases:
            config.enter_phrases = enter_phrases
        if exit_phrases:
            config.exit_phrases = exit_phrases
        if keywords:
            config.character_query_keywords = keywords
        else:
            config.character_query_keywords = [role_name, "角色"]

        for key, value in overrides.items():
            if value is not None and hasattr(config, key):
                setattr(config, key, value)
        return config

    def build_role_system_prompt(self) -> str:
        pieces = [self.system_prompt.strip()] if self.system_prompt else []
        if self.skill_text:
            pieces.append(
                "以下是这个角色的 skill 内容。请把它作为角色设定、表达方式和行为边界参考：\n\n"
                + self.skill_text
            )
        return "\n\n".join(piece for piece in pieces if piece)
