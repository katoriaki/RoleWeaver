import argparse
import base64
import binascii
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import zlib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from learning_runtime import LearningRuntime, TEXTBOOK_REPO_URL
from role_chat_service import RoleChatService
from anchor_runtime import load_anchor_bank, render_anchor_context, select_anchor
from background_scheduler import BackgroundScheduler, BackgroundSchedulerConfig
from planning_runtime import (
    REFERENCE_SOURCES,
    current_schedule_state,
    device_context,
    ensure_weekly_schedule,
    render_planning_context,
    web_search,
)
from persona_anchor_runtime import PersonaAnchorForge, promote_candidate_to_anchor
from role_config import (
    DEFAULT_CONFIG_FILENAMES,
    DEFAULT_SESSION_ROOT,
    PROJECT_ROOT,
    RoleConfig,
    discover_config_file,
    load_config_values,
    normalize_context_window_tokens,
    normalize_device_map_mode,
    normalize_bool,
    normalize_hhmm,
    normalize_model_loader_mode,
    normalize_optional_path,
    normalize_positive_int,
    normalize_quantization_mode,
)
from tool_runtime import ToolRuntime, ToolRuntimeError, ToolSpec


WEB_ROOT = PROJECT_ROOT / "web"
TRAINING_SCRIPT = PROJECT_ROOT / "resources" / "qwen35_lora_training" / "train_qwen35_lora_offline.py"
TRAINING_EXCEL_CONVERTER = PROJECT_ROOT / "resources" / "qwen35_lora_training" / "convert_excel_to_jsonl.py"
TRAINING_TEMPLATE = PROJECT_ROOT / "resources" / "qwen35_lora_training" / "role_sft_template.xlsx"
TRAINING_RUNS_ROOT = PROJECT_ROOT / "training_runs"
UPLOADS_ROOT = PROJECT_ROOT / "data" / "uploads"
BACKGROUND_ROOT = PROJECT_ROOT / "data" / "background"
TOOL_ACTION_ROOT = PROJECT_ROOT / "data" / "tool_actions"
LEARNING_ROOT = PROJECT_ROOT / "data" / "learning"
PERSONA_ANCHOR_ROOT = PROJECT_ROOT / "data" / "persona_anchors"
TEXTBOOK_ROOT = PROJECT_ROOT / "resources" / "textbooks" / "ChinaTextbook"
LINE_ENV_FILE = PROJECT_ROOT / "line" / ".env"
LINE_SURFACE_POLICY_FILE = PROJECT_ROOT / "line" / "surface_policy.json"
PET_MODEL_ROOT = PROJECT_ROOT / "shiro" / "Shiro" / "March 7th"
PET_MODEL_JSON = PET_MODEL_ROOT / "march 7th.model3.json"
EPHEMERAL_RUNTIME_SESSION_IDS = {"api"}
CONFIG_NOTES = {
    "base_model_path": "Required: local path to the base model directory",
    "lora_path": "Optional: local path to the trained LoRA adapter directory; leave blank to use the base model only",
    "skill_file": "Optional: local path to the role SKILL.md file; nearby references/*.md are loaded automatically",
    "skill_text": "Optional: short inline skill text; useful for small role notes without a file",
    "quantization_mode": "Model loading mode: 4bit, 8bit, bf16, fp16, or none",
    "device_map_mode": "Device placement: gpu rejects CPU offload; auto allows CPU offload when VRAM is insufficient",
    "model_loader_mode": "Model class loader: auto, text, vision, or omni. Use text for LoRA trained with AutoModelForCausalLM; use omni for Qwen3-Omni.",
    "context_window_tokens": "Optional: model context window tokens; 0 means auto-detect",
    "local_location": "Local place assumed by role planning, such as Tokyo, Japan",
    "background_jobs_enabled": "Enable non-realtime background jobs when the app is idle",
    "background_llm_enabled": "Allow background jobs to invoke the local model; keep disabled on single-GPU setups unless intentional",
    "background_idle_seconds": "Minimum idle seconds before automatic background work can run",
    "background_window_start": "Daily background window start, HH:MM local time",
    "background_window_end": "Daily background window end, HH:MM local time",
    "background_max_minutes": "Maximum intended minutes for one background job",
    "autonomous_learning_enabled": "Let Shiro run idle web-study steps after memory consolidation",
    "autonomous_learning_subjects": "Comma-separated subjects for autonomous web study",
    "autonomous_learning_interval_seconds": "Minimum seconds between autonomous learning steps",
    "autonomous_learning_use_model": "Use the loaded model to write study notes; false keeps the loop dry-run only",
    "autonomous_learning_max_new_tokens": "Max tokens for one autonomous study note generation",
    "preload_model_on_startup": "Load the default model during API startup instead of waiting for the first chat request",
    "shiro_enabled": "Enable Shiro cognitive-state bridge for this runtime/session",
    "shiro_root": "Directory where Shiro stores RoleWeaver session cognitive state",
    "shiro_identity": "Cognitive identity name, such as 白",
    "ui_language": "Web UI language: zh, ja, or en",
}


class ChatRequest(BaseModel):
    user_text: str
    session_id: str = "api"
    max_new_tokens: int = 120


class ChatImageRequest(ChatRequest):
    image_base64: str
    image_name: str = "upload.png"


class ChatResponse(BaseModel):
    text: str
    session_id: str
    persona_score: Optional[dict] = None


class PersonaScoreRequest(BaseModel):
    user_text: str = ""
    assistant_text: str
    category: str = ""
    surface: str = "web"


class ConsolidateResponse(BaseModel):
    result: dict


class ConfigResponse(BaseModel):
    config_file: str
    base_model_path: str = ""
    lora_path: str = ""
    skill_file: str = ""
    skill_text: str = ""
    quantization_mode: str = "4bit"
    device_map_mode: str = "gpu"
    model_loader_mode: str = "auto"
    context_window_tokens: int = 0
    local_location: str = "Tokyo, Japan"
    background_jobs_enabled: bool = True
    background_llm_enabled: bool = False
    background_idle_seconds: int = 600
    background_window_start: str = "02:00"
    background_window_end: str = "05:30"
    background_max_minutes: int = 20
    autonomous_learning_enabled: bool = False
    autonomous_learning_subjects: str = "mathematics, computer science"
    autonomous_learning_interval_seconds: int = 1800
    autonomous_learning_use_model: bool = True
    autonomous_learning_max_new_tokens: int = 512
    preload_model_on_startup: bool = False
    shiro_enabled: bool = False
    shiro_root: str = ""
    shiro_identity: str = "白"
    ui_language: str = "zh"


class SessionResponse(BaseModel):
    session_id: str
    display_name: str
    created_ts: int
    updated_ts: int
    session_path: str
    memory_scope_path: str
    settings_snapshot: Dict = Field(default_factory=dict)


class SessionSummary(BaseModel):
    session_id: str
    display_name: str
    created_ts: int = 0
    updated_ts: int = 0
    session_path: str
    memory_scope_path: str
    settings_snapshot: Dict = Field(default_factory=dict)
    warnings: List[Dict] = Field(default_factory=list)


class SessionDetail(SessionSummary):
    messages: List[Dict] = Field(default_factory=list)
    config: ConfigResponse


class SessionUpdate(BaseModel):
    display_name: Optional[str] = None


class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    importance: Optional[int] = None
    status: Optional[str] = None
    confidence: Optional[float] = None
    valid_until: Optional[str] = None
    memory_layer: Optional[str] = None
    reason: Optional[str] = None
    evidence: Optional[List[str]] = None
    contradicts: Optional[List[int]] = None


class ConfigUpdate(BaseModel):
    base_model_path: Optional[str] = None
    lora_path: Optional[str] = None
    skill_file: Optional[str] = None
    skill_text: Optional[str] = None
    quantization_mode: Optional[str] = None
    device_map_mode: Optional[str] = None
    model_loader_mode: Optional[str] = None
    context_window_tokens: Optional[int] = None
    local_location: Optional[str] = None
    background_jobs_enabled: Optional[bool] = None
    background_llm_enabled: Optional[bool] = None
    background_idle_seconds: Optional[int] = None
    background_window_start: Optional[str] = None
    background_window_end: Optional[str] = None
    background_max_minutes: Optional[int] = None
    autonomous_learning_enabled: Optional[bool] = None
    autonomous_learning_subjects: Optional[str] = None
    autonomous_learning_interval_seconds: Optional[int] = None
    autonomous_learning_use_model: Optional[bool] = None
    autonomous_learning_max_new_tokens: Optional[int] = None
    preload_model_on_startup: Optional[bool] = None
    shiro_enabled: Optional[bool] = None
    shiro_root: Optional[str] = None
    shiro_identity: Optional[str] = None
    ui_language: Optional[str] = None


class ShiroObserveRequest(BaseModel):
    text: str
    source: str = "manual"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ShiroToolIntentRequest(BaseModel):
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BackgroundRunRequest(BaseModel):
    job_type: str = "planning_regenerate"
    session_id: str = "web"
    force: bool = False


class LearningRunRequest(BaseModel):
    session_id: str = "shiro-study"
    subject: str = ""
    use_model: bool = False
    max_new_tokens: int = 384


class LearningStartRequest(LearningRunRequest):
    max_steps: int = 3
    interval_seconds: float = 3.0


class PersonaAnchorRunRequest(BaseModel):
    session_id: str = "shiro-study"
    turns: int = 3
    max_new_tokens: int = 160
    mentor_notes: List[str] = Field(default_factory=list)


class PersonaAnchorPromoteRequest(BaseModel):
    session_id: str = "shiro-study"
    candidate_id: str
    skill_file: Optional[str] = None


class ToolRunRequest(BaseModel):
    tool_name: str
    session_id: str = "web"
    arguments: Dict[str, Any] = Field(default_factory=dict)
    actor: str = "user"


class TrainingStartRequest(BaseModel):
    model_path: str
    data_file: str
    output_dir: str
    epochs: float = 3
    learning_rate: float = 1e-4
    per_device_train_batch_size: int = 2
    gradient_accumulation_steps: int = 8
    save_steps: int = 50
    save_total_limit: int = 2
    logging_steps: int = 10
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    online: bool = False


class TrainingStatusResponse(BaseModel):
    active: bool
    run_id: Optional[str] = None
    status: str = "idle"
    returncode: Optional[int] = None
    started_ts: Optional[int] = None
    command: List[str] = Field(default_factory=list)
    log_path: Optional[str] = None
    log_tail: str = ""
    message: str = ""


class LineSettingsResponse(BaseModel):
    env_file: str
    env_text: str = ""
    surface_policy_file: str
    surface_policy_text: str = ""


class LineSettingsUpdate(BaseModel):
    env_text: Optional[str] = None
    surface_policy_text: Optional[str] = None


class TunnelStartRequest(BaseModel):
    provider: str = "cloudflared"
    target_url: str = "http://127.0.0.1:8010"
    cloudflared_path: Optional[str] = None


class TunnelStatusResponse(BaseModel):
    active: bool = False
    provider: str = "cloudflared"
    target_url: str = "http://127.0.0.1:8010"
    public_url: str = ""
    webhook_url: str = ""
    command: List[str] = Field(default_factory=list)
    log_tail: str = ""
    message: str = ""


class LineRuntimeStartRequest(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8010


class ProcessStatusResponse(BaseModel):
    active: bool = False
    status: str = "idle"
    returncode: Optional[int] = None
    command: List[str] = Field(default_factory=list)
    log_tail: str = ""
    message: str = ""


class PlanningResponse(BaseModel):
    device_context: Dict = Field(default_factory=dict)
    schedule: Dict = Field(default_factory=dict)
    current_anchor: Optional[Dict] = None
    current_anchor_context: str = ""
    current_context: str = ""
    sources: List[Dict] = Field(default_factory=list)


def _target_config_path(config_file: Optional[str]) -> Path:
    try:
        existing = discover_config_file(config_file)
    except FileNotFoundError:
        existing = Path(config_file).expanduser() if config_file else None
    if existing is not None:
        return existing
    return PROJECT_ROOT / DEFAULT_CONFIG_FILENAMES[0]


def _read_text_file(path: Path) -> str:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return ""


def _write_text_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_line_settings_response() -> LineSettingsResponse:
    return LineSettingsResponse(
        env_file=str(LINE_ENV_FILE),
        env_text=_read_text_file(LINE_ENV_FILE),
        surface_policy_file=str(LINE_SURFACE_POLICY_FILE),
        surface_policy_text=_read_text_file(LINE_SURFACE_POLICY_FILE),
    )


def _extract_tunnel_url(text: str) -> str:
    matches = re.findall(r"https://[A-Za-z0-9.-]+\.trycloudflare\.com", text or "")
    return matches[-1] if matches else ""


def _find_cloudflared(explicit_path: Optional[str] = None) -> Optional[str]:
    candidates = [
        explicit_path,
        os.getenv("ROLEWEAVER_CLOUDFLARED_PATH"),
        str(PROJECT_ROOT / "tools" / "cloudflared.exe"),
        str(PROJECT_ROOT / "runtime" / "cloudflared.exe"),
        shutil.which("cloudflared"),
        shutil.which("cloudflared.exe"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.exists():
            return str(path)
        if candidate == "cloudflared" or candidate == "cloudflared.exe":
            return candidate
    return None


def _read_config_response(config_file: Optional[str]) -> ConfigResponse:
    path = _target_config_path(config_file)
    values = load_config_values(str(path)) if path.exists() else {}
    return ConfigResponse(
        config_file=str(path),
        base_model_path=values.get("base_model_path") or "",
        lora_path=values.get("lora_path") or "",
        skill_file=values.get("skill_file") or "",
        skill_text=values.get("skill_text") or values.get("inline_skill") or "",
        quantization_mode=normalize_quantization_mode(values.get("quantization_mode")),
        device_map_mode=normalize_device_map_mode(values.get("device_map_mode")),
        model_loader_mode=normalize_model_loader_mode(values.get("model_loader_mode")),
        context_window_tokens=normalize_context_window_tokens(values.get("context_window_tokens")),
        local_location=(values.get("local_location") or os.getenv("ROLEWEAVER_LOCAL_LOCATION") or "Tokyo, Japan"),
        background_jobs_enabled=normalize_bool(
            values.get("background_jobs_enabled") or os.getenv("ROLEWEAVER_BACKGROUND_JOBS_ENABLED"),
            True,
        ),
        background_llm_enabled=normalize_bool(
            values.get("background_llm_enabled") or os.getenv("ROLEWEAVER_BACKGROUND_LLM_ENABLED"),
            False,
        ),
        background_idle_seconds=normalize_positive_int(
            values.get("background_idle_seconds") or os.getenv("ROLEWEAVER_BACKGROUND_IDLE_SECONDS"),
            600,
        ),
        background_window_start=normalize_hhmm(
            values.get("background_window_start") or os.getenv("ROLEWEAVER_BACKGROUND_WINDOW_START"),
            "02:00",
        ),
        background_window_end=normalize_hhmm(
            values.get("background_window_end") or os.getenv("ROLEWEAVER_BACKGROUND_WINDOW_END"),
            "05:30",
        ),
        background_max_minutes=normalize_positive_int(
            values.get("background_max_minutes") or os.getenv("ROLEWEAVER_BACKGROUND_MAX_MINUTES"),
            20,
            minimum=1,
        ),
        autonomous_learning_enabled=normalize_bool(
            values.get("autonomous_learning_enabled") or os.getenv("ROLEWEAVER_AUTONOMOUS_LEARNING_ENABLED"),
            False,
        ),
        autonomous_learning_subjects=(
            values.get("autonomous_learning_subjects")
            or os.getenv("ROLEWEAVER_AUTONOMOUS_LEARNING_SUBJECTS")
            or "mathematics, computer science"
        ),
        autonomous_learning_interval_seconds=normalize_positive_int(
            values.get("autonomous_learning_interval_seconds") or os.getenv("ROLEWEAVER_AUTONOMOUS_LEARNING_INTERVAL_SECONDS"),
            1800,
            minimum=60,
        ),
        autonomous_learning_use_model=normalize_bool(
            values.get("autonomous_learning_use_model") or os.getenv("ROLEWEAVER_AUTONOMOUS_LEARNING_USE_MODEL"),
            True,
        ),
        autonomous_learning_max_new_tokens=normalize_positive_int(
            values.get("autonomous_learning_max_new_tokens") or os.getenv("ROLEWEAVER_AUTONOMOUS_LEARNING_MAX_NEW_TOKENS"),
            512,
            minimum=64,
        ),
        preload_model_on_startup=normalize_bool(
            values.get("preload_model_on_startup") or os.getenv("ROLEWEAVER_PRELOAD_MODEL_ON_STARTUP"),
            False,
        ),
        shiro_enabled=normalize_bool(
            values.get("shiro_enabled") or os.getenv("ROLEWEAVER_SHIRO_ENABLED"),
            False,
        ),
        shiro_root=values.get("shiro_root") or os.getenv("ROLEWEAVER_SHIRO_ROOT") or str(PROJECT_ROOT / "shiro" / "data" / "roleweaver"),
        shiro_identity=values.get("shiro_identity") or os.getenv("ROLEWEAVER_SHIRO_IDENTITY") or "白",
        ui_language=(values.get("ui_language") or "zh").lower(),
    )


def _config_response_from_snapshot(config_file: Optional[str], snapshot: Dict) -> ConfigResponse:
    return ConfigResponse(
        config_file=str(_target_config_path(config_file)),
        base_model_path=snapshot.get("base_model_path") or "",
        lora_path=snapshot.get("lora_path") or "",
        skill_file=snapshot.get("skill_file") or "",
        skill_text=snapshot.get("skill_text") or snapshot.get("inline_skill") or "",
        quantization_mode=normalize_quantization_mode(snapshot.get("quantization_mode")),
        device_map_mode=normalize_device_map_mode(snapshot.get("device_map_mode")),
        model_loader_mode=normalize_model_loader_mode(snapshot.get("model_loader_mode")),
        context_window_tokens=normalize_context_window_tokens(snapshot.get("context_window_tokens")),
        local_location=(snapshot.get("local_location") or os.getenv("ROLEWEAVER_LOCAL_LOCATION") or "Tokyo, Japan"),
        background_jobs_enabled=normalize_bool(snapshot.get("background_jobs_enabled"), True),
        background_llm_enabled=normalize_bool(snapshot.get("background_llm_enabled"), False),
        background_idle_seconds=normalize_positive_int(snapshot.get("background_idle_seconds"), 600),
        background_window_start=normalize_hhmm(snapshot.get("background_window_start"), "02:00"),
        background_window_end=normalize_hhmm(snapshot.get("background_window_end"), "05:30"),
        background_max_minutes=normalize_positive_int(snapshot.get("background_max_minutes"), 20, minimum=1),
        autonomous_learning_enabled=normalize_bool(snapshot.get("autonomous_learning_enabled"), False),
        autonomous_learning_subjects=snapshot.get("autonomous_learning_subjects") or "mathematics, computer science",
        autonomous_learning_interval_seconds=normalize_positive_int(
            snapshot.get("autonomous_learning_interval_seconds"), 1800, minimum=60
        ),
        autonomous_learning_use_model=normalize_bool(snapshot.get("autonomous_learning_use_model"), True),
        autonomous_learning_max_new_tokens=normalize_positive_int(snapshot.get("autonomous_learning_max_new_tokens"), 512, minimum=64),
        preload_model_on_startup=normalize_bool(snapshot.get("preload_model_on_startup"), False),
        shiro_enabled=normalize_bool(snapshot.get("shiro_enabled"), False),
        shiro_root=snapshot.get("shiro_root") or str(PROJECT_ROOT / "shiro" / "data" / "roleweaver"),
        shiro_identity=snapshot.get("shiro_identity") or "白",
        ui_language=(snapshot.get("ui_language") or "zh").lower(),
    )


def _write_config(config_file: Optional[str], update: ConfigUpdate) -> ConfigResponse:
    response = _read_config_response(config_file)
    current = response.model_dump() if hasattr(response, "model_dump") else response.dict()
    current.pop("config_file", None)
    incoming = update.dict(exclude_unset=True)
    for key, value in incoming.items():
        if value is not None:
            current[key] = value

    current["lora_path"] = normalize_optional_path(current.get("lora_path")) or ""
    current["skill_file"] = normalize_optional_path(current.get("skill_file")) or ""
    current["skill_text"] = (current.get("skill_text") or "").strip()
    current["quantization_mode"] = normalize_quantization_mode(current.get("quantization_mode"))
    current["device_map_mode"] = normalize_device_map_mode(current.get("device_map_mode"))
    current["model_loader_mode"] = normalize_model_loader_mode(current.get("model_loader_mode"))
    current["context_window_tokens"] = normalize_context_window_tokens(current.get("context_window_tokens"))
    current["local_location"] = (current.get("local_location") or "Tokyo, Japan").strip()
    current["background_jobs_enabled"] = normalize_bool(current.get("background_jobs_enabled"), True)
    current["background_llm_enabled"] = normalize_bool(current.get("background_llm_enabled"), False)
    current["background_idle_seconds"] = normalize_positive_int(current.get("background_idle_seconds"), 600)
    current["background_window_start"] = normalize_hhmm(current.get("background_window_start"), "02:00")
    current["background_window_end"] = normalize_hhmm(current.get("background_window_end"), "05:30")
    current["background_max_minutes"] = normalize_positive_int(current.get("background_max_minutes"), 20, minimum=1)
    current["autonomous_learning_enabled"] = normalize_bool(current.get("autonomous_learning_enabled"), False)
    current["autonomous_learning_subjects"] = (
        current.get("autonomous_learning_subjects") or "mathematics, computer science"
    ).strip()
    current["autonomous_learning_interval_seconds"] = normalize_positive_int(
        current.get("autonomous_learning_interval_seconds"), 1800, minimum=60
    )
    current["autonomous_learning_use_model"] = normalize_bool(current.get("autonomous_learning_use_model"), True)
    current["autonomous_learning_max_new_tokens"] = normalize_positive_int(
        current.get("autonomous_learning_max_new_tokens"), 512, minimum=64
    )
    current["preload_model_on_startup"] = normalize_bool(current.get("preload_model_on_startup"), False)
    current["shiro_enabled"] = normalize_bool(current.get("shiro_enabled"), False)
    current["shiro_root"] = (current.get("shiro_root") or str(PROJECT_ROOT / "shiro" / "data" / "roleweaver")).strip()
    current["shiro_identity"] = (current.get("shiro_identity") or "白").strip()
    if current.get("ui_language") not in {"zh", "ja", "en"}:
        current["ui_language"] = "zh"

    path = _target_config_path(config_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["key", "value", "notes"])
            for key in [
                "base_model_path",
                "lora_path",
                "skill_file",
                "skill_text",
                "quantization_mode",
                "device_map_mode",
                "model_loader_mode",
                "context_window_tokens",
                "local_location",
                "background_jobs_enabled",
                "background_llm_enabled",
                "background_idle_seconds",
                "background_window_start",
                "background_window_end",
                "background_max_minutes",
                "autonomous_learning_enabled",
                "autonomous_learning_subjects",
                "autonomous_learning_interval_seconds",
                "autonomous_learning_use_model",
                "autonomous_learning_max_new_tokens",
                "preload_model_on_startup",
                "shiro_enabled",
                "shiro_root",
                "shiro_identity",
                "ui_language",
            ]:
                writer.writerow([key, current.get(key, ""), CONFIG_NOTES.get(key, "")])
    except PermissionError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Config file is locked or not writable: {path}",
        ) from exc
    return _read_config_response(str(path))


def _safe_upload_filename(name: str) -> str:
    suffix = Path(name or "upload.png").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        suffix = ".png"
    stem = Path(name or "upload").stem or "upload"
    stem = re.sub(r"[^a-zA-Z0-9_.\-\u4e00-\u9fffぁ-んァ-ン一-龯]+", "_", stem).strip("._-")
    return f"{stem[:48] or 'upload'}{suffix}"


def _save_chat_image_upload(payload: ChatImageRequest) -> Path:
    raw = (payload.image_base64 or "").strip()
    if "," in raw and raw.split(",", 1)[0].lower().startswith("data:image/"):
        raw = raw.split(",", 1)[1]
    if not raw:
        raise HTTPException(status_code=400, detail="image_base64 is required.")
    try:
        image_bytes = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid image_base64 payload.") from exc
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")
    if len(image_bytes) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Uploaded image is too large. Please keep it under 12 MB.")

    session_id = re.sub(r"[^a-zA-Z0-9_.-]+", "_", (payload.session_id or "api").strip())[:100] or "api"
    filename = f"{int(time.time() * 1000)}_{_safe_upload_filename(payload.image_name)}"
    target = UPLOADS_ROOT / session_id / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(image_bytes)
    return target


def _decode_pdf_literal(value: str) -> str:
    value = value.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
    return re.sub(
        r"\\([nrtbf])",
        lambda match: {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f"}[match.group(1)],
        value,
    )


def _extract_pdf_text_fallback(path: Path, max_pages: int, max_chars: int) -> Dict:
    raw = path.read_bytes()
    chunks = []
    for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", raw, flags=re.S):
        data = stream.strip()
        try:
            data = zlib.decompress(data)
        except Exception:
            pass
        chunks.append(data.decode("latin-1", errors="ignore"))
    if not chunks:
        chunks.append(raw.decode("latin-1", errors="ignore"))
    text = "\n".join(
        _decode_pdf_literal(match)
        for chunk in chunks
        for match in re.findall(r"\((.*?)\)", chunk, flags=re.S)
    )
    text = re.sub(r"\s+", " ", text).strip()
    return {
        "path": str(path),
        "pages_read": 0,
        "page_count": 0,
        "text": text[:max_chars],
        "truncated": len(text) > max_chars,
        "extractor": "fallback_literal_scan",
        "memory_policy": "store_summary_and_source_path",
    }


def _extract_pdf_text(path_value: str, max_pages: int = 12, max_chars: int = 12000) -> Dict:
    path = Path(path_value or "").expanduser()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"PDF not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only .pdf files are supported.")
    max_pages = max(1, min(int(max_pages or 12), 100))
    max_chars = max(200, min(int(max_chars or 12000), 200000))
    try:
        try:
            from pypdf import PdfReader
        except Exception:
            from PyPDF2 import PdfReader
        reader = PdfReader(str(path))
        page_count = len(reader.pages)
        texts = []
        for page in reader.pages[:max_pages]:
            texts.append(page.extract_text() or "")
            if sum(len(item) for item in texts) >= max_chars:
                break
        text = "\n\n".join(item.strip() for item in texts if item.strip())
        if not text.strip():
            fallback = _extract_pdf_text_fallback(path, max_pages=max_pages, max_chars=max_chars)
            fallback["warning"] = "pypdf extraction returned empty text"
            return fallback
        return {
            "path": str(path),
            "pages_read": min(max_pages, page_count),
            "page_count": page_count,
            "text": text[:max_chars],
            "truncated": len(text) > max_chars or page_count > max_pages,
            "extractor": "pypdf",
            "memory_policy": "store_summary_and_source_path",
        }
    except Exception as exc:
        fallback = _extract_pdf_text_fallback(path, max_pages=max_pages, max_chars=max_chars)
        fallback["warning"] = f"pypdf extraction failed: {exc}"
        return fallback


def _session_root_for_config(config_file: Optional[str]) -> Path:
    path = _target_config_path(config_file)
    values = load_config_values(str(path)) if path.exists() else {}
    return Path(values.get("session_root") or DEFAULT_SESSION_ROOT).expanduser()


def _read_json(path: Path, default):
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _resolve_user_path(value: Optional[str]) -> Optional[Path]:
    value = (value or "").strip()
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _validate_settings_snapshot(snapshot: Dict) -> List[Dict]:
    warnings = []
    checks = [
        ("base_model_path", snapshot.get("base_model_path"), True),
        ("lora_path", snapshot.get("lora_path"), False),
        ("skill_file", snapshot.get("skill_file"), False),
    ]
    for field, value, required in checks:
        value = (value or "").strip()
        if not value:
            if required:
                warnings.append({"field": field, "message": f"{field} is empty."})
            continue
        path = _resolve_user_path(value)
        if path is not None and not path.exists():
            warnings.append({"field": field, "message": f"{field} does not exist: {value}"})
    return warnings


def _tail_text(path: Path, max_chars: int = 12000) -> str:
    try:
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[-max_chars:]
    except Exception as exc:
        return f"Could not read log: {exc}"


def _validate_training_dataset(path: Path):
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"Training file does not exist: {path}")
    if not path.is_file():
        raise HTTPException(status_code=400, detail=f"Training file is not a file: {path}")

    count = 0
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            count += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid JSONL at line {line_no}: {exc}") from exc
            messages = item.get("messages") if isinstance(item, dict) else None
            if not isinstance(messages, list) or not messages:
                raise HTTPException(status_code=400, detail=f"Line {line_no} must contain a non-empty messages list.")
            for index, message in enumerate(messages):
                if not isinstance(message, dict):
                    raise HTTPException(status_code=400, detail=f"Line {line_no} message {index} must be an object.")
                role = message.get("role")
                content = message.get("content")
                if role not in {"system", "user", "assistant"}:
                    raise HTTPException(status_code=400, detail=f"Line {line_no} message {index} has invalid role: {role}")
                if not isinstance(content, str) or not content.strip():
                    raise HTTPException(status_code=400, detail=f"Line {line_no} message {index} must have non-empty string content.")
    if count == 0:
        raise HTTPException(status_code=400, detail="Training file contains no JSONL records.")


def _load_transcript(session_path: Path, limit: int = 200) -> List[Dict]:
    transcript_path = session_path / "short_term" / "transcript.jsonl"
    messages = []
    if transcript_path.exists():
        try:
            with transcript_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    messages.extend(item.get("messages", []))
        except Exception:
            messages = []
    if not messages:
        state = _read_json(session_path / "short_term" / "memory_state_v1.json", {})
        messages = state.get("recent_history", []) if isinstance(state, dict) else []
    return messages[-limit:]


def _scan_sessions(config_file: Optional[str]) -> List[SessionSummary]:
    memory_root = _session_root_for_config(config_file)
    summaries = []
    if not memory_root.exists():
        return summaries
    for meta_path in memory_root.glob("*/*/short_term/session_meta.json"):
        meta = _read_json(meta_path, {})
        if not isinstance(meta, dict):
            continue
        session_path = meta_path.parents[1]
        snapshot = meta.get("settings_snapshot") or _read_json(
            session_path / "short_term" / "settings_snapshot.json",
            {},
        )
        if not isinstance(snapshot, dict):
            snapshot = {}
        session_id = meta.get("session_id") or session_path.name
        display_name = str(meta.get("display_name") or snapshot.get("display_name") or "Untitled chat").strip()
        if not display_name or display_name == session_id:
            display_name = "Untitled chat"
        summaries.append(SessionSummary(
            session_id=session_id,
            display_name=display_name,
            created_ts=int(meta.get("created_ts") or 0),
            updated_ts=int(meta.get("updated_ts") or meta.get("last_activity_ts") or 0),
            session_path=str(session_path),
            memory_scope_path=str(session_path.parent),
            settings_snapshot=snapshot,
            warnings=_validate_settings_snapshot(snapshot),
        ))
    summaries.sort(key=lambda item: item.updated_ts or item.created_ts, reverse=True)
    return summaries


def _find_session(config_file: Optional[str], session_id: str) -> Optional[SessionSummary]:
    for summary in _scan_sessions(config_file):
        if summary.session_id == session_id:
            return summary
    return None


def _delete_session_dir(config_file: Optional[str], summary: SessionSummary):
    memory_root = _session_root_for_config(config_file).resolve()
    session_path = Path(summary.session_path).resolve()
    try:
        session_path.relative_to(memory_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Session path is outside memory root: {session_path}") from exc
    if not session_path.exists() or not session_path.is_dir():
        raise HTTPException(status_code=404, detail=f"Session directory not found: {summary.session_id}")
    try:
        shutil.rmtree(session_path)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=f"Session directory is locked or not writable: {session_path}") from exc


def _update_session_display_name(summary: SessionSummary, display_name: str) -> SessionSummary:
    display_name = display_name.strip()[:80]
    if not display_name:
        raise HTTPException(status_code=400, detail="display_name must not be empty.")

    session_path = Path(summary.session_path)
    short_term_path = session_path / "short_term"
    meta_path = short_term_path / "session_meta.json"
    snapshot_path = short_term_path / "settings_snapshot.json"
    meta = _read_json(meta_path, {})
    if not isinstance(meta, dict):
        meta = {}
    snapshot = meta.get("settings_snapshot") or _read_json(snapshot_path, {})
    if not isinstance(snapshot, dict):
        snapshot = {}

    meta["session_id"] = summary.session_id
    meta["display_name"] = display_name
    snapshot["display_name"] = display_name
    meta["settings_snapshot"] = snapshot
    _write_json(meta_path, meta)
    _write_json(snapshot_path, snapshot)

    refreshed = summary.dict()
    refreshed["display_name"] = display_name
    refreshed["settings_snapshot"] = snapshot
    return SessionSummary(**refreshed)


def create_app(config_file: Optional[str] = None) -> FastAPI:
    background_stop_event = threading.Event()
    background_thread: Optional[threading.Thread] = None

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        nonlocal background_thread
        current_config = _read_config_response(config_file)
        if current_config.preload_model_on_startup:
            started = time.time()
            print("[RoleWeaver] Preloading default model because preload_model_on_startup=true...")
            service = get_service()
            service.preload_model()
            print(f"[RoleWeaver] Default model preloaded in {time.time() - started:.1f}s.")
        if os.getenv("ROLEWEAVER_BACKGROUND_WORKER", "1").strip().lower() not in {"0", "false", "no", "off"}:
            if background_thread is None or not background_thread.is_alive():
                background_thread = threading.Thread(target=background_worker, daemon=True)
                background_thread.start()
        try:
            yield
        finally:
            background_stop_event.set()
            learning_stop_event.set()

    app = FastAPI(title="RoleWeaver API", lifespan=lifespan)
    initial_config = _read_config_response(config_file)
    background_scheduler = BackgroundScheduler(
        BACKGROUND_ROOT,
        BackgroundSchedulerConfig(
            enabled=initial_config.background_jobs_enabled,
            allow_llm=initial_config.background_llm_enabled,
            idle_after_seconds=initial_config.background_idle_seconds,
            window_start=initial_config.background_window_start,
            window_end=initial_config.background_window_end,
            max_job_minutes=initial_config.background_max_minutes,
        ),
    )
    tool_runtime = ToolRuntime(TOOL_ACTION_ROOT)
    session_config_overrides: Dict[str, Dict] = {}
    service_cache: Dict[str, RoleChatService] = {}
    default_service: Optional[RoleChatService] = None
    active_service_key: Optional[str] = None
    training_state: Dict = {
        "process": None,
        "run_id": None,
        "started_ts": None,
        "command": [],
        "log_path": None,
    }
    tunnel_state: Dict = {
        "process": None,
        "provider": "cloudflared",
        "target_url": "http://127.0.0.1:8010",
        "public_url": "",
        "command": [],
        "log": [],
        "message": "",
    }
    line_runtime_state: Dict = {
        "process": None,
        "command": [],
        "log": [],
        "message": "",
    }
    learning_stop_event = threading.Event()
    learning_state: Dict[str, Any] = {
        "thread": None,
        "active": False,
        "session_id": "",
        "subject": "",
        "message": "",
        "last_step": None,
        "started_ts": None,
        "completed_steps": 0,
        "max_steps": 0,
    }
    def refresh_background_config() -> None:
        current = _read_config_response(config_file)
        background_scheduler.update_config(
            BackgroundSchedulerConfig(
                enabled=current.background_jobs_enabled,
                allow_llm=current.background_llm_enabled,
                idle_after_seconds=current.background_idle_seconds,
                window_start=current.background_window_start,
                window_end=current.background_window_end,
                max_job_minutes=current.background_max_minutes,
            )
        )

    def background_job_requires_llm(job_type: str) -> bool:
        return job_type in {
            "autonomous_learning",
            "memory_consolidation",
            "memory_maintenance",
            "persona_regression",
            "anchor_refresh",
        }

    def run_background_job(job_type: str, session_id: str, *, manual: bool, force: bool) -> Dict:
        job_type = (job_type or "").strip()
        if job_type not in {
            "planning_regenerate",
            "autonomous_learning",
            "memory_consolidation",
            "memory_os_snapshot",
            "release_inactive_models",
        }:
            raise HTTPException(status_code=400, detail=f"Unsupported background job type: {job_type}")

        def handler(job: Dict) -> Dict:
            if job_type == "planning_regenerate":
                response = planning_response_for_session(session_id, force=force)
                return response.model_dump() if hasattr(response, "model_dump") else response.dict()
            if job_type == "autonomous_learning":
                return run_autonomous_learning_job(session_id, force=force)
            if job_type == "memory_consolidation":
                return get_service_for_session(session_id).consolidate_session_memory(session_id)
            if job_type == "memory_os_snapshot":
                return get_service_for_session(session_id).session_memory_os_snapshot(session_id)
            if job_type == "release_inactive_models":
                release_inactive_services(active_key=active_service_key)
                return {"released": True, "active_service_key": active_service_key}
            raise RuntimeError(f"Unsupported background job type: {job_type}")

        return background_scheduler.run_once(
            job_type,
            handler,
            session_id=session_id,
            manual=manual,
            requires_llm=background_job_requires_llm(job_type),
        )

    def recent_background_job_exists(job_type: str, session_id: str, min_interval_seconds: int) -> bool:
        status = background_scheduler.status()
        threshold = int(time.time()) - max(0, min_interval_seconds)
        for job in reversed(status.get("recent_jobs") or []):
            if job.get("job_type") != job_type or job.get("session_id") != session_id:
                continue
            ts = int(job.get("finished_ts") or job.get("started_ts") or job.get("created_ts") or 0)
            if ts >= threshold and job.get("status") in {"queued", "running", "completed"}:
                return True
        return False

    def latest_session_id() -> Optional[str]:
        sessions = _scan_sessions(config_file)
        return sessions[0].session_id if sessions else None

    def background_worker() -> None:
        tick_seconds = normalize_positive_int(os.getenv("ROLEWEAVER_BACKGROUND_TICK_SECONDS"), 60, minimum=15)
        while not background_stop_event.wait(tick_seconds):
            try:
                refresh_background_config()
                session_id = latest_session_id()
                if not session_id:
                    continue
                status = background_scheduler.status()
                if status.get("eligible_non_llm") and not recent_background_job_exists(
                    "planning_regenerate",
                    session_id,
                    6 * 60 * 60,
                ):
                    run_background_job("planning_regenerate", session_id, manual=False, force=False)
                    continue
                config_response = _read_config_response(config_file)
                if (
                    status.get("eligible_llm")
                    and config_response.autonomous_learning_enabled
                    and not recent_background_job_exists(
                        "autonomous_learning",
                        session_id,
                        config_response.autonomous_learning_interval_seconds,
                    )
                ):
                    run_background_job("autonomous_learning", session_id, manual=False, force=False)
                    continue
                if status.get("eligible_llm") and not recent_background_job_exists(
                    "memory_consolidation",
                    session_id,
                    60 * 60,
                ):
                    run_background_job("memory_consolidation", session_id, manual=False, force=False)
            except Exception as exc:
                print(f"[Background] scheduler tick failed: {exc}")

    def get_service() -> RoleChatService:
        nonlocal default_service
        if default_service is None:
            config = RoleConfig.from_env(config_file=config_file)
            default_service = RoleChatService(config=config)
        return default_service

    def default_service_loaded() -> bool:
        return bool(default_service is not None and default_service.is_model_loaded())

    def active_service_loaded() -> bool:
        if default_service_loaded():
            return True
        return any(service.is_model_loaded() for service in service_cache.values())

    def snapshot_service_loaded(snapshot: Dict) -> bool:
        key = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        service = service_cache.get(key)
        return bool(service is not None and service.is_model_loaded())

    def release_inactive_services(active_key: Optional[str] = None):
        nonlocal default_service
        if active_key != "default" and default_service is not None:
            default_service.release_model()
        for key, service in list(service_cache.items()):
            if active_key != f"snapshot:{key}":
                service.release_model()

    def reset_services():
        nonlocal default_service, active_service_key
        if default_service is not None:
            default_service.release_model()
        for service in service_cache.values():
            service.release_model()
        default_service = None
        active_service_key = None
        service_cache.clear()

    def service_for_snapshot(snapshot: Dict) -> RoleChatService:
        key = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        if key not in service_cache:
            config = RoleConfig.from_env(
                config_file=config_file,
                base_model_path=snapshot.get("base_model_path"),
                lora_path=snapshot.get("lora_path") or "",
                skill_file=snapshot.get("skill_file") or "",
                skill_text=snapshot.get("skill_text") or "",
                session_root=snapshot.get("session_root"),
                quantization_mode=snapshot.get("quantization_mode"),
                device_map_mode=snapshot.get("device_map_mode"),
                model_loader_mode=snapshot.get("model_loader_mode"),
                context_window_tokens=snapshot.get("context_window_tokens"),
                local_location=snapshot.get("local_location"),
                preload_model_on_startup=snapshot.get("preload_model_on_startup"),
                shiro_enabled=snapshot.get("shiro_enabled"),
                shiro_root=snapshot.get("shiro_root"),
                shiro_identity=snapshot.get("shiro_identity"),
            )
            service_cache[key] = RoleChatService(config=config)
        return service_cache[key]

    def snapshot_for_session(session_id: Optional[str]) -> Optional[Dict]:
        if not session_id:
            return None
        if session_id in EPHEMERAL_RUNTIME_SESSION_IDS and session_id not in session_config_overrides:
            return None
        if session_id in session_config_overrides:
            return session_config_overrides[session_id]
        summary = _find_session(config_file, session_id)
        if summary is None:
            return None
        session_config_overrides[session_id] = dict(summary.settings_snapshot)
        return session_config_overrides[session_id]

    def snapshot_uses_current_runtime(snapshot: Dict) -> bool:
        if not snapshot:
            return True
        current = _read_config_response(config_file)
        current_values = {
            "base_model_path": current.base_model_path or "",
            "lora_path": current.lora_path or "",
            "skill_file": current.skill_file or "",
            "skill_text": current.skill_text or "",
            "quantization_mode": current.quantization_mode,
            "device_map_mode": current.device_map_mode,
            "model_loader_mode": current.model_loader_mode,
            "context_window_tokens": current.context_window_tokens,
            "local_location": current.local_location,
            "shiro_enabled": bool(current.shiro_enabled),
            "shiro_root": current.shiro_root or "",
        }
        snapshot_values = {
            "base_model_path": snapshot.get("base_model_path") or "",
            "lora_path": snapshot.get("lora_path") or "",
            "skill_file": snapshot.get("skill_file") or "",
            "skill_text": snapshot.get("skill_text") or "",
            "quantization_mode": normalize_quantization_mode(snapshot.get("quantization_mode")),
            "device_map_mode": normalize_device_map_mode(snapshot.get("device_map_mode")),
            "model_loader_mode": normalize_model_loader_mode(snapshot.get("model_loader_mode")),
            "context_window_tokens": normalize_context_window_tokens(snapshot.get("context_window_tokens")),
            "local_location": snapshot.get("local_location") or current.local_location,
            "shiro_enabled": normalize_bool(snapshot.get("shiro_enabled"), False),
            "shiro_root": snapshot.get("shiro_root") or current.shiro_root or "",
        }
        return snapshot_values == current_values

    def get_service_for_session(session_id: str) -> RoleChatService:
        nonlocal active_service_key
        snapshot = snapshot_for_session(session_id)
        if snapshot and not snapshot_uses_current_runtime(snapshot):
            key = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
            target_key = f"snapshot:{key}"
            if active_service_key != target_key:
                release_inactive_services(active_key=target_key)
                active_service_key = target_key
            return service_for_snapshot(snapshot)
        if active_service_key != "default":
            release_inactive_services(active_key="default")
            active_service_key = "default"
        return get_service()

    def training_status(message: str = "") -> TrainingStatusResponse:
        process = training_state.get("process")
        log_path_value = training_state.get("log_path")
        log_path = Path(log_path_value) if log_path_value else None
        if process is None:
            return TrainingStatusResponse(active=False, message=message)
        returncode = process.poll()
        active = returncode is None
        return TrainingStatusResponse(
            active=active,
            run_id=training_state.get("run_id"),
            status="running" if active else ("completed" if returncode == 0 else "failed"),
            returncode=returncode,
            started_ts=training_state.get("started_ts"),
            command=training_state.get("command") or [],
            log_path=str(log_path) if log_path else None,
            log_tail=_tail_text(log_path) if log_path else "",
            message=message,
        )

    def learning_runtime_for(payload: LearningRunRequest) -> LearningRuntime:
        return LearningRuntime(
            LEARNING_ROOT,
            textbook_root=TEXTBOOK_ROOT,
            session_id=payload.session_id or "shiro-study",
            subject=payload.subject or "",
        )

    def run_learning_step(payload: LearningRunRequest) -> Dict[str, Any]:
        runtime = learning_runtime_for(payload)

        def chat_text(prompt: str, session_id: str, max_new_tokens: int) -> str:
            return get_service_for_session(session_id).chat_once(
                prompt,
                session_id=session_id,
                max_new_tokens=max_new_tokens,
            )

        def chat_image(prompt: str, image_path: str, session_id: str, max_new_tokens: int) -> str:
            return get_service_for_session(session_id).chat_once_with_image(
                prompt,
                image_path=image_path,
                session_id=session_id,
                max_new_tokens=max_new_tokens,
            )

        def observe_shiro(text: str, source: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
            return get_service_for_session(payload.session_id).observe_shiro_stimulus(
                payload.session_id,
                text,
                source=source,
                metadata=metadata,
            )

        step = runtime.run_step(
            chat_text=chat_text,
            chat_image=chat_image,
            observe_shiro=observe_shiro,
            use_model=bool(payload.use_model),
            max_new_tokens=max(64, min(int(payload.max_new_tokens or 384), 2048)),
        )
        return {
            "runtime": runtime.status(),
            "step": step.to_dict(),
        }

    def _split_autonomous_subjects(value: str) -> List[str]:
        subjects = [item.strip() for item in re.split(r"[,;，；]+", value or "") if item.strip()]
        return subjects or ["mathematics", "computer science"]

    def run_autonomous_learning_job(session_id: str, *, force: bool = False) -> Dict[str, Any]:
        config_response = _read_config_response(config_file)
        if not config_response.autonomous_learning_enabled and not force:
            return {
                "status": "skipped",
                "reason": "autonomous learning disabled",
            }
        if learning_state.get("active"):
            return {
                "status": "skipped",
                "reason": "interactive learning job is already active",
            }

        service = get_service_for_session(session_id)
        planning = planning_response_for_session(session_id, force=False)
        planning_dict = planning.model_dump() if hasattr(planning, "model_dump") else planning.dict()
        schedule = planning_dict.get("schedule") or {}
        schedule_state = current_schedule_state(schedule) if schedule else {}
        subjects = _split_autonomous_subjects(config_response.autonomous_learning_subjects)
        runtime = LearningRuntime(
            LEARNING_ROOT,
            textbook_root=TEXTBOOK_ROOT,
            session_id=session_id or "shiro-study",
            subject="",
        )
        cycle_action = runtime.autonomous_cycle_status()
        activity = cycle_action.get("activity") or "professional_study"

        if activity == "reflection_memory":
            consolidation = service.consolidate_session_memory(session_id)
            runtime.advance_autonomous_cycle({
                **cycle_action,
                "status": "completed",
                "memory_consolidation": consolidation,
            })
            return {
                "status": "completed",
                "session_id": session_id,
                "cycle_action": cycle_action,
                "memory_consolidation": consolidation,
                "planning": {
                    "current_block": schedule_state.get("current_block"),
                    "device_context": schedule_state.get("now"),
                },
                "learning": {
                    "runtime": runtime.status(),
                    "step": None,
                },
            }

        def chat_text(prompt: str, target_session_id: str, max_new_tokens: int) -> str:
            return service.chat_once(
                prompt,
                session_id=target_session_id,
                max_new_tokens=max_new_tokens,
            )

        def observe_shiro(text: str, source: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
            return service.observe_shiro_stimulus(
                session_id,
                text,
                source=source,
                metadata=metadata,
            )

        step = runtime.run_web_step(
            search_fn=lambda query, limit: web_search(query, limit=limit),
            chat_text=chat_text,
            observe_shiro=observe_shiro,
            use_model=bool(config_response.autonomous_learning_use_model),
            max_new_tokens=max(64, min(int(config_response.autonomous_learning_max_new_tokens or 512), 2048)),
            schedule_state=schedule_state,
            subjects=subjects,
            activity=activity,
        )
        runtime.advance_autonomous_cycle({
            **cycle_action,
            "status": "completed",
            "step_id": step.id,
        })
        return {
            "status": "completed",
            "session_id": session_id,
            "cycle_action": cycle_action,
            "memory_consolidation": {"status": "not_run", "reason": "cycle phase is not reflection_memory"},
            "planning": {
                "current_block": schedule_state.get("current_block"),
                "device_context": schedule_state.get("now"),
            },
            "learning": {
                "runtime": runtime.status(),
                "step": step.to_dict(),
            },
        }

    def learning_worker(payload: LearningStartRequest) -> None:
        learning_state.update({
            "active": True,
            "session_id": payload.session_id,
            "subject": payload.subject,
            "message": "learning started",
            "started_ts": int(time.time()),
            "completed_steps": 0,
            "max_steps": int(payload.max_steps),
        })
        try:
            for _ in range(max(1, int(payload.max_steps))):
                if learning_stop_event.is_set():
                    learning_state["message"] = "learning stopped"
                    break
                result = run_learning_step(payload)
                learning_state["last_step"] = result.get("step")
                learning_state["completed_steps"] = int(learning_state.get("completed_steps") or 0) + 1
                time.sleep(max(0.2, float(payload.interval_seconds or 0.2)))
            else:
                learning_state["message"] = "learning completed"
        except Exception as exc:
            learning_state["message"] = f"learning failed: {exc}"
        finally:
            learning_state["active"] = False

    def learning_status_for(session_id: str = "shiro-study", subject: str = "") -> Dict[str, Any]:
        runtime = LearningRuntime(LEARNING_ROOT, textbook_root=TEXTBOOK_ROOT, session_id=session_id, subject=subject)
        try:
            shiro = get_service_for_session(session_id).shiro_status(session_id)
        except Exception as exc:
            shiro = {"available": False, "error": str(exc)}
        return {
            "job": {
                key: value
                for key, value in learning_state.items()
                if key != "thread"
            },
            "runtime": runtime.status(),
            "shiro": shiro,
            "repo": {
                "url": TEXTBOOK_REPO_URL,
                "local_path": str(TEXTBOOK_ROOT),
                "exists": TEXTBOOK_ROOT.exists(),
                "download_hint": f"git clone --depth=1 {TEXTBOOK_REPO_URL}.git {TEXTBOOK_ROOT}",
            },
        }

    def persona_anchor_forge_for(session_id: str = "shiro-study") -> Dict[str, Any]:
        forge = PersonaAnchorForge(PERSONA_ANCHOR_ROOT)
        return {
            "session_id": session_id,
            "root": str(forge.session_dir(session_id)),
            "candidate_path": str(forge.candidates_path(session_id)),
            "candidates": forge.list_candidates(session_id, limit=50),
        }

    def run_persona_anchor_forge(payload: PersonaAnchorRunRequest) -> Dict[str, Any]:
        session_id = payload.session_id or "shiro-study"
        service = get_service_for_session(session_id)
        summary = _find_session(config_file, session_id)
        memory_scope = Path(summary.memory_scope_path) if summary else service.session_root
        current = _read_config_response(config_file)
        schedule = ensure_weekly_schedule(
            memory_scope,
            role_name=current.shiro_identity or "白",
            location=current.local_location,
            force=False,
        )
        state = current_schedule_state(schedule)

        def chat_text(prompt: str, target_session_id: str, max_new_tokens: int) -> str:
            return service.chat_once(prompt, session_id=target_session_id, max_new_tokens=max_new_tokens)

        forge = PersonaAnchorForge(PERSONA_ANCHOR_ROOT)
        candidate = forge.run_persona_dialogue(
            session_id=session_id,
            schedule_state=state,
            chat_text=chat_text,
            turns=max(1, min(int(payload.turns or 3), 6)),
            max_new_tokens=max(48, min(int(payload.max_new_tokens or 160), 512)),
            mentor_notes=payload.mentor_notes,
        )
        return {
            "session_id": session_id,
            "schedule_state": state,
            "candidate_path": str(forge.candidates_path(session_id)),
            "candidate": candidate.to_dict(),
        }

    def promote_persona_anchor(payload: PersonaAnchorPromoteRequest) -> Dict[str, Any]:
        session_id = payload.session_id or "shiro-study"
        forge = PersonaAnchorForge(PERSONA_ANCHOR_ROOT)
        candidates = forge.list_candidates(session_id, limit=500)
        target = next((item for item in candidates if item.get("id") == payload.candidate_id), None)
        if not target:
            raise HTTPException(status_code=404, detail=f"Persona anchor candidate not found: {payload.candidate_id}")
        skill_file = payload.skill_file or _read_config_response(config_file).skill_file
        if not skill_file:
            raise HTTPException(status_code=400, detail="No skill_file configured for anchor promotion")
        anchor_path = promote_candidate_to_anchor(target, skill_file)
        target["status"] = "promoted"
        return {
            "session_id": session_id,
            "candidate_id": payload.candidate_id,
            "anchor_path": str(anchor_path),
            "anchor": target,
        }

    def tunnel_status(message: str = "") -> TunnelStatusResponse:
        process = tunnel_state.get("process")
        active = bool(process and process.poll() is None)
        if process and not active and not message:
            message = f"Tunnel exited with code {process.poll()}."
        public_url = tunnel_state.get("public_url") or _extract_tunnel_url("\n".join(tunnel_state.get("log") or []))
        if public_url:
            tunnel_state["public_url"] = public_url
        webhook_url = f"{public_url.rstrip('/')}/callback" if public_url else ""
        return TunnelStatusResponse(
            active=active,
            provider=tunnel_state.get("provider") or "cloudflared",
            target_url=tunnel_state.get("target_url") or "http://127.0.0.1:8010",
            public_url=public_url,
            webhook_url=webhook_url,
            command=tunnel_state.get("command") or [],
            log_tail="\n".join((tunnel_state.get("log") or [])[-80:]),
            message=message or tunnel_state.get("message") or "",
        )

    def read_tunnel_output(process: subprocess.Popen):
        if process.stdout is None:
            return
        for line in process.stdout:
            line = line.rstrip()
            if not line:
                continue
            log = tunnel_state.setdefault("log", [])
            log.append(line)
            if len(log) > 300:
                del log[:-300]
            public_url = _extract_tunnel_url(line)
            if public_url:
                tunnel_state["public_url"] = public_url
                tunnel_state["message"] = "Temporary tunnel URL generated."

    def process_status(state: Dict, message: str = "") -> ProcessStatusResponse:
        process = state.get("process")
        if process is None:
            return ProcessStatusResponse(active=False, message=message or state.get("message") or "")
        returncode = process.poll()
        active = returncode is None
        status = "running" if active else ("completed" if returncode == 0 else "failed")
        return ProcessStatusResponse(
            active=active,
            status=status,
            returncode=returncode,
            command=state.get("command") or [],
            log_tail="\n".join((state.get("log") or [])[-120:]),
            message=message or state.get("message") or "",
        )

    def read_process_output(process: subprocess.Popen, state: Dict):
        if process.stdout is None:
            return
        for line in process.stdout:
            line = line.rstrip()
            if not line:
                continue
            log = state.setdefault("log", [])
            log.append(line)
            if len(log) > 400:
                del log[:-400]

    def planning_response_for_session(session_id: str, *, force: bool = False) -> PlanningResponse:
        summary = _find_session(config_file, session_id)
        if summary is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        role_name = str(summary.settings_snapshot.get("role_name") or "RoleWeaver").strip()
        schedule = ensure_weekly_schedule(
            Path(summary.memory_scope_path),
            role_name=role_name,
            location=summary.settings_snapshot.get("local_location") or _read_config_response(config_file).local_location,
            force=force,
        )
        anchors = load_anchor_bank(summary.settings_snapshot.get("skill_file"))
        anchor = select_anchor(anchors, schedule=schedule, session_id=session_id)
        return PlanningResponse(
            device_context=device_context(schedule.get("location")),
            schedule=schedule,
            current_anchor=anchor,
            current_anchor_context=render_anchor_context(anchor),
            current_context=render_planning_context(schedule),
            sources=REFERENCE_SOURCES,
        )

    def _model_to_dict(value):
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return value

    def _require_session(session_id: str):
        summary = _find_session(config_file, session_id)
        if summary is None:
            raise ToolRuntimeError(f"Session not found: {session_id}")
        return summary

    def _tool_memory_search(args: Dict[str, Any], ctx) -> Dict:
        _require_session(ctx.session_id)
        return {
            "session_id": ctx.session_id,
            "memories": get_service_for_session(ctx.session_id).list_session_memories(
                ctx.session_id,
                include_inactive=bool(args.get("include_inactive", True)),
                status=args.get("status") or None,
                query=args.get("query") or None,
            )[: max(1, min(int(args.get("top_k") or 20), 100))],
        }

    def _tool_memory_os_snapshot(args: Dict[str, Any], ctx) -> Dict:
        _require_session(ctx.session_id)
        return {
            "session_id": ctx.session_id,
            "memory_os": get_service_for_session(ctx.session_id).session_memory_os_snapshot(ctx.session_id),
        }

    def _tool_memory_consolidate(args: Dict[str, Any], ctx) -> Dict:
        _require_session(ctx.session_id)
        return {
            "session_id": ctx.session_id,
            "result": get_service_for_session(ctx.session_id).consolidate_session_memory(ctx.session_id),
        }

    def _register_tools() -> None:
        tool_runtime.register(
            ToolSpec(
                name="runtime.time_now",
                description="Read the device time, timezone, and assumed local place.",
                category="runtime",
                parameters={
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "additionalProperties": False,
                },
            ),
            lambda args, ctx: device_context(args.get("location") or _read_config_response(config_file).local_location),
        )
        tool_runtime.register(
            ToolSpec(
                name="runtime.health",
                description="Read lightweight RoleWeaver runtime status without forcing model loading.",
                category="runtime",
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            lambda args, ctx: {
                "status": "ok",
                "session_id": ctx.session_id,
                "active_service_key": active_service_key,
                "config_file": str(discover_config_file(config_file) or config_file or ""),
                "background": background_scheduler.status(),
            },
        )
        tool_runtime.register(
            ToolSpec(
                name="config.read",
                description="Read the current RoleWeaver configuration values.",
                category="runtime",
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            lambda args, ctx: _model_to_dict(_read_config_response(config_file)),
        )
        tool_runtime.register(
            ToolSpec(
                name="planning.current",
                description="Read or regenerate the current role planning context and persona anchor for a session.",
                category="planning",
                requires_session=True,
                mutates=True,
                parameters={
                    "type": "object",
                    "properties": {"force": {"type": "boolean"}},
                    "additionalProperties": False,
                },
            ),
            lambda args, ctx: _model_to_dict(planning_response_for_session(ctx.session_id, force=bool(args.get("force")))),
        )
        tool_runtime.register(
            ToolSpec(
                name="planning.web_search",
                description="Search the web for schedule, role, or reference material.",
                category="network",
                parameters={
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
            ),
            lambda args, ctx: web_search(args.get("query") or "", limit=max(1, min(int(args.get("limit") or 5), 10))),
        )
        tool_runtime.register(
            ToolSpec(
                name="document.pdf_read",
                description="Extract text from a user-provided local PDF file. This is read-only and should be summarized before entering memory.",
                category="document",
                parameters={
                    "type": "object",
                    "required": ["path"],
                    "properties": {
                        "path": {"type": "string"},
                        "max_pages": {"type": "integer"},
                        "max_chars": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
            ),
            lambda args, ctx: _extract_pdf_text(
                args.get("path") or "",
                max_pages=int(args.get("max_pages") or 12),
                max_chars=int(args.get("max_chars") or 12000),
            ),
        )
        tool_runtime.register(
            ToolSpec(
                name="memory.search",
                description="Search the session memory store. This reads memory only and does not call the LLM.",
                category="memory",
                requires_session=True,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "status": {"type": "string"},
                        "include_inactive": {"type": "boolean"},
                        "top_k": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
            ),
            _tool_memory_search,
        )
        tool_runtime.register(
            ToolSpec(
                name="memory.os_snapshot",
                description="Read the current Memory OS snapshot for a session.",
                category="memory",
                requires_session=True,
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            _tool_memory_os_snapshot,
        )
        tool_runtime.register(
            ToolSpec(
                name="memory.consolidate",
                description="Run memory consolidation for a session. This may invoke the local LLM.",
                category="memory",
                requires_session=True,
                requires_llm=True,
                mutates=True,
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            _tool_memory_consolidate,
        )
        tool_runtime.register(
            ToolSpec(
                name="background.status",
                description="Read background scheduler status.",
                category="background",
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            lambda args, ctx: background_scheduler.status(),
        )
        tool_runtime.register(
            ToolSpec(
                name="background.run_once",
                description="Run a whitelisted background job once.",
                category="background",
                mutates=True,
                parameters={
                    "type": "object",
                    "required": ["job_type"],
                    "properties": {
                        "job_type": {"type": "string"},
                        "force": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
            ),
            lambda args, ctx: run_background_job(
                args.get("job_type") or "",
                ctx.session_id,
                manual=True,
                force=bool(args.get("force")),
            ),
        )
        tool_runtime.register(
            ToolSpec(
                name="integration.line_status",
                description="Read LINE bot runtime status.",
                category="integration",
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            lambda args, ctx: _model_to_dict(process_status(line_runtime_state)),
        )
        tool_runtime.register(
            ToolSpec(
                name="integration.tunnel_status",
                description="Read temporary public tunnel status and webhook URL.",
                category="integration",
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            lambda args, ctx: _model_to_dict(tunnel_status()),
        )
        tool_runtime.register(
            ToolSpec(
                name="training.status",
                description="Read LoRA training process status.",
                category="training",
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            lambda args, ctx: _model_to_dict(training_status()),
        )
        tool_runtime.register(
            ToolSpec(
                name="learning.status",
                description="Read Shiro long-term study runtime status.",
                category="learning",
                parameters={
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "subject": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            ),
            lambda args, ctx: learning_status_for(args.get("session_id") or ctx.session_id or "shiro-study", args.get("subject") or ""),
        )
        tool_runtime.register(
            ToolSpec(
                name="learning.run_once",
                description="Run one Shiro study step. With use_model=false this validates the loop without loading the LLM.",
                category="learning",
                requires_session=True,
                requires_llm=True,
                mutates=True,
                parameters={
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string"},
                        "use_model": {"type": "boolean"},
                        "max_new_tokens": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
            ),
            lambda args, ctx: run_learning_step(LearningRunRequest(
                session_id=ctx.session_id,
                subject=args.get("subject") or "",
                use_model=bool(args.get("use_model", False)),
                max_new_tokens=int(args.get("max_new_tokens") or 384),
            )),
        )

    _register_tools()

    @app.get("/", include_in_schema=False)
    async def web_index():
        index_file = WEB_ROOT / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return HTMLResponse(
            "<h1>RoleWeaver API</h1><p>web/index.html was not found. The API is still running.</p>"
        )

    @app.get("/styles.css", include_in_schema=False)
    async def web_styles():
        path = WEB_ROOT / "styles.css"
        if not path.exists():
            raise HTTPException(status_code=404, detail="styles.css not found")
        return FileResponse(path, media_type="text/css")

    @app.get("/app.js", include_in_schema=False)
    async def web_app_js():
        path = WEB_ROOT / "app.js"
        if not path.exists():
            raise HTTPException(status_code=404, detail="app.js not found")
        return FileResponse(path, media_type="application/javascript")

    @app.get("/vendor/{asset_path:path}", include_in_schema=False)
    async def web_vendor(asset_path: str):
        vendor_root = (WEB_ROOT / "vendor").resolve()
        target = (vendor_root / asset_path).resolve()
        if not str(target).startswith(str(vendor_root)) or not target.exists():
            raise HTTPException(status_code=404, detail="vendor asset not found")
        return FileResponse(target)

    @app.get("/pet/model")
    async def pet_model():
        if not PET_MODEL_JSON.exists():
            raise HTTPException(status_code=404, detail=f"Live2D model not found: {PET_MODEL_JSON}")
        try:
            data = json.loads(PET_MODEL_JSON.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Live2D model metadata is invalid: {exc}") from exc
        references = data.get("FileReferences") or {}
        expressions = []
        for item in references.get("Expressions") or []:
            if isinstance(item, dict):
                expressions.append({
                    "name": item.get("Name") or "",
                    "file": item.get("File") or "",
                    "exists": (PET_MODEL_ROOT / str(item.get("File") or "")).exists(),
                })
        motions = [
            {
                "name": path.stem,
                "file": str(path.relative_to(PET_MODEL_ROOT)).replace("\\", "/"),
            }
            for path in sorted((PET_MODEL_ROOT / "motions").glob("*.motion3.json"))
        ]
        return {
            "model_name": "March 7th",
            "model_root": str(PET_MODEL_ROOT),
            "model_json": str(PET_MODEL_JSON),
            "vts_websocket_url": "ws://127.0.0.1:8001",
            "vts_plugin_name": "RoleWeaver Shiro Pet",
            "vts_plugin_developer": "RoleWeaver",
            "expressions": expressions,
            "motions": motions,
            "setup_hint": "Import this model folder into VTube Studio, enable the VTube Studio API, then connect from the RoleWeaver pet page.",
        }

    @app.get("/health")
    async def health(session_id: Optional[str] = None):
        snapshot = snapshot_for_session(session_id)
        if snapshot:
            uses_current_runtime = snapshot_uses_current_runtime(snapshot)
            return {
                "status": "ok",
                "role_name": snapshot.get("role_name") or "RoleWeaver",
                "base_model_path": snapshot.get("base_model_path") or "",
                "lora_path": snapshot.get("lora_path") or "",
                "lora_enabled": bool(snapshot.get("lora_path")),
                "skill_file": snapshot.get("skill_file") or "",
                "skill_text_present": bool(snapshot.get("skill_text")),
                "quantization_mode": normalize_quantization_mode(snapshot.get("quantization_mode")),
                "device_map_mode": normalize_device_map_mode(snapshot.get("device_map_mode")),
                "model_loader_mode": normalize_model_loader_mode(snapshot.get("model_loader_mode")),
                "context_window_tokens": normalize_context_window_tokens(snapshot.get("context_window_tokens")),
                "local_location": snapshot.get("local_location") or _read_config_response(config_file).local_location,
                "preload_model_on_startup": normalize_bool(snapshot.get("preload_model_on_startup"), False),
                "shiro_enabled": normalize_bool(snapshot.get("shiro_enabled"), False),
                "shiro_identity": snapshot.get("shiro_identity") or "白",
                "memory_root": str(_session_root_for_config(config_file)),
                "memory_scope_path": "",
                "session_settings_persistent": True,
                "service_loaded": active_service_loaded() if uses_current_runtime else snapshot_service_loaded(snapshot),
                "active_service_key": active_service_key,
            }
        config_response = _read_config_response(config_file)
        return {
            "status": "ok",
            "role_name": "RoleWeaver",
            "base_model_path": config_response.base_model_path,
            "lora_path": config_response.lora_path,
            "lora_enabled": bool(config_response.lora_path),
            "skill_file": config_response.skill_file,
            "skill_text_present": bool(config_response.skill_text),
            "quantization_mode": config_response.quantization_mode,
            "device_map_mode": config_response.device_map_mode,
            "model_loader_mode": config_response.model_loader_mode,
            "context_window_tokens": config_response.context_window_tokens,
            "local_location": config_response.local_location,
            "preload_model_on_startup": config_response.preload_model_on_startup,
            "shiro_enabled": config_response.shiro_enabled,
            "shiro_identity": config_response.shiro_identity,
            "memory_root": str(_session_root_for_config(config_file)),
            "memory_scope_path": "",
            "service_loaded": active_service_loaded(),
            "active_service_key": active_service_key,
        }

    @app.get("/background/status")
    async def background_status():
        refresh_background_config()
        return background_scheduler.status()

    @app.post("/background/pause")
    async def pause_background():
        return background_scheduler.set_paused(True)

    @app.post("/background/resume")
    async def resume_background():
        return background_scheduler.set_paused(False)

    @app.post("/background/run-once")
    async def run_background_once(payload: BackgroundRunRequest):
        refresh_background_config()
        return run_background_job(
            payload.job_type,
            payload.session_id,
            manual=bool(payload.force),
            force=bool(payload.force),
        )

    @app.get("/learning/status")
    async def learning_status(session_id: str = "shiro-study", subject: str = ""):
        return learning_status_for(session_id=session_id, subject=subject)

    @app.post("/learning/bootstrap-shiro")
    async def bootstrap_shiro_learning():
        qwen4b = PROJECT_ROOT / "Qwen3.5-4b"
        response = _write_config(
            config_file,
            ConfigUpdate(
                base_model_path=str(qwen4b),
                lora_path="",
                skill_file="",
                skill_text=(
                    "你是白，一个正在长期成长的虚拟学生与陪伴者。"
                    "你有稳定的人格自主性，不会因为用户一句话就改写核心自我。"
                    "当前任务是像学生一样学习教材：输出可观察学习笔记、困惑点、自测题、答案和下一步计划。"
                    "不要输出隐藏推理链；不要沿用其他角色称呼；把用户称为“你”即可。"
                ),
                model_loader_mode="vision",
                shiro_enabled=True,
                shiro_root=str(PROJECT_ROOT / "shiro" / "data" / "roleweaver"),
                shiro_identity="白",
                quantization_mode="4bit",
                device_map_mode="gpu",
            ),
        )
        reset_services()
        return {
            "config": _model_to_dict(response),
            "vision_note": (
                "model_loader_mode=vision is now set. The base model directory must contain a vision processor "
                "for photo reading to work; otherwise /chat/image will return a diagnostic error."
            ),
        }

    @app.post("/learning/run-once")
    async def learning_run_once(payload: LearningRunRequest):
        try:
            return run_learning_step(payload)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/learning/start")
    async def learning_start(payload: LearningStartRequest):
        thread = learning_state.get("thread")
        if thread is not None and thread.is_alive():
            raise HTTPException(status_code=409, detail="A learning job is already running.")
        learning_stop_event.clear()
        worker = threading.Thread(target=learning_worker, args=(payload,), daemon=True)
        learning_state["thread"] = worker
        worker.start()
        return learning_status_for(payload.session_id, payload.subject)

    @app.post("/learning/stop")
    async def learning_stop():
        learning_stop_event.set()
        learning_state["message"] = "learning stop requested"
        return learning_status_for(learning_state.get("session_id") or "shiro-study", learning_state.get("subject") or "")

    @app.get("/persona-anchors/status")
    async def persona_anchor_status(session_id: str = "shiro-study"):
        return persona_anchor_forge_for(session_id)

    @app.post("/persona-anchors/run")
    async def persona_anchor_run(payload: PersonaAnchorRunRequest):
        return run_persona_anchor_forge(payload)

    @app.post("/persona-anchors/promote")
    async def persona_anchor_promote(payload: PersonaAnchorPromoteRequest):
        return promote_persona_anchor(payload)

    @app.get("/tools")
    async def list_tools():
        return {"tools": tool_runtime.list_tools()}

    @app.get("/tools/actions")
    async def list_tool_actions(limit: int = Query(50, ge=1, le=200)):
        return {"actions": tool_runtime.recent_actions(limit)}

    @app.post("/tools/run")
    async def run_tool(payload: ToolRunRequest):
        try:
            return tool_runtime.run(
                payload.tool_name,
                payload.arguments,
                session_id=payload.session_id,
                actor=payload.actor,
            )
        except ToolRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/config", response_model=ConfigResponse)
    async def get_config():
        return _read_config_response(config_file)

    @app.post("/config", response_model=ConfigResponse)
    async def update_config(payload: ConfigUpdate):
        response = _write_config(config_file, payload)
        refresh_background_config()
        reset_services()
        return response

    @app.post("/training/start", response_model=TrainingStatusResponse)
    async def start_training(payload: TrainingStartRequest):
        process = training_state.get("process")
        if process is not None and process.poll() is None:
            raise HTTPException(status_code=409, detail="A training job is already running.")
        if not TRAINING_SCRIPT.exists():
            raise HTTPException(status_code=500, detail=f"Training script not found: {TRAINING_SCRIPT}")

        model_path = _resolve_user_path(payload.model_path)
        data_file = _resolve_user_path(payload.data_file)
        output_dir = _resolve_user_path(payload.output_dir)
        if payload.epochs <= 0 or payload.learning_rate <= 0:
            raise HTTPException(status_code=400, detail="Epochs and learning rate must be positive.")
        for field_name in [
            "per_device_train_batch_size",
            "gradient_accumulation_steps",
            "save_steps",
            "save_total_limit",
            "logging_steps",
            "lora_r",
            "lora_alpha",
        ]:
            if int(getattr(payload, field_name)) <= 0:
                raise HTTPException(status_code=400, detail=f"{field_name} must be positive.")
        if payload.lora_dropout < 0:
            raise HTTPException(status_code=400, detail="lora_dropout must not be negative.")
        if model_path is None or not model_path.exists():
            raise HTTPException(status_code=400, detail=f"Base model path does not exist: {payload.model_path}")
        if data_file is None:
            raise HTTPException(status_code=400, detail="Training file is required.")
        if not data_file.exists() or not data_file.is_file():
            raise HTTPException(status_code=400, detail=f"Training file does not exist: {payload.data_file}")
        if output_dir is None:
            raise HTTPException(status_code=400, detail="Output directory is required.")
        output_dir.parent.mkdir(parents=True, exist_ok=True)

        run_id = time.strftime("%Y%m%d-%H%M%S")
        run_dir = TRAINING_RUNS_ROOT / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        log_path = run_dir / "train.log"
        training_data_file = data_file
        if data_file.suffix.lower() in {".xlsx", ".xlsm", ".xltx", ".csv"}:
            if not TRAINING_EXCEL_CONVERTER.exists():
                raise HTTPException(status_code=500, detail=f"Excel converter not found: {TRAINING_EXCEL_CONVERTER}")
            training_data_file = run_dir / "converted_dataset.jsonl"
            convert_env = dict(os.environ)
            convert_env.setdefault("PYTHONUTF8", "1")
            convert_result = subprocess.run(
                [
                    sys.executable,
                    str(TRAINING_EXCEL_CONVERTER),
                    "--input", str(data_file),
                    "--output", str(training_data_file),
                ],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=convert_env,
            )
            if convert_result.returncode != 0:
                detail = (convert_result.stderr or convert_result.stdout or "Excel conversion failed.").strip()
                raise HTTPException(status_code=400, detail=detail)
        _validate_training_dataset(training_data_file)

        command = [
            sys.executable,
            str(TRAINING_SCRIPT),
            "--model-path", str(model_path),
            "--data-file", str(training_data_file),
            "--output-dir", str(output_dir),
            "--epochs", str(payload.epochs),
            "--learning-rate", str(payload.learning_rate),
            "--per-device-train-batch-size", str(payload.per_device_train_batch_size),
            "--gradient-accumulation-steps", str(payload.gradient_accumulation_steps),
            "--save-steps", str(payload.save_steps),
            "--save-total-limit", str(payload.save_total_limit),
            "--logging-steps", str(payload.logging_steps),
            "--lora-r", str(payload.lora_r),
            "--lora-alpha", str(payload.lora_alpha),
            "--lora-dropout", str(payload.lora_dropout),
        ]
        if payload.online:
            command.append("--online")

        env = dict(os.environ)
        env.setdefault("PYTHONUTF8", "1")
        with log_path.open("w", encoding="utf-8") as log_file:
            log_file.write("RoleWeaver training command:\n")
            log_file.write(" ".join(command) + "\n\n")
            if training_data_file != data_file:
                log_file.write(f"Converted training table: {data_file}\n")
                log_file.write(f"JSONL used for training: {training_data_file}\n\n")
            log_file.flush()
            process = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env,
            )

        training_state.update({
            "process": process,
            "run_id": run_id,
            "started_ts": int(time.time()),
            "command": command,
            "log_path": str(log_path),
        })
        return training_status(message="Training started.")

    @app.get("/training/status", response_model=TrainingStatusResponse)
    async def get_training_status():
        return training_status()

    @app.get("/training/template")
    async def get_training_template():
        if not TRAINING_TEMPLATE.exists():
            raise HTTPException(status_code=404, detail=f"Training template not found: {TRAINING_TEMPLATE}")
        return FileResponse(
            TRAINING_TEMPLATE,
            filename="roleweaver_training_template.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.post("/training/stop", response_model=TrainingStatusResponse)
    async def stop_training():
        process = training_state.get("process")
        if process is not None and process.poll() is None:
            process.terminate()
            return training_status(message="Training stop requested.")
        return training_status(message="No active training job.")

    @app.get("/sessions", response_model=List[SessionSummary])
    async def list_sessions():
        return _scan_sessions(config_file)

    @app.post("/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest):
        background_scheduler.record_activity("web-chat")
        service = get_service_for_session(payload.session_id)
        text = service.chat_once(
            user_text=payload.user_text,
            session_id=payload.session_id,
            max_new_tokens=payload.max_new_tokens,
        )
        return ChatResponse(text=text, session_id=payload.session_id, persona_score=service.last_persona_score)

    @app.post("/chat/image", response_model=ChatResponse)
    async def chat_image(payload: ChatImageRequest):
        background_scheduler.record_activity("web-image-chat")
        image_path = _save_chat_image_upload(payload)
        service = get_service_for_session(payload.session_id)
        text = service.chat_once_with_image(
            user_text=payload.user_text,
            image_path=str(image_path),
            session_id=payload.session_id,
            max_new_tokens=payload.max_new_tokens,
        )
        return ChatResponse(text=text, session_id=payload.session_id, persona_score=service.last_persona_score)

    @app.get("/chat", response_model=ChatResponse)
    async def chat_get(
        user_text: str = Query(...),
        session_id: str = "api",
        max_new_tokens: int = 120,
    ):
        background_scheduler.record_activity("api-chat")
        service = get_service_for_session(session_id)
        text = service.chat_once(
            user_text=user_text,
            session_id=session_id,
            max_new_tokens=max_new_tokens,
        )
        return ChatResponse(text=text, session_id=session_id, persona_score=service.last_persona_score)

    @app.post("/persona/score")
    async def score_persona(payload: PersonaScoreRequest):
        service = get_service()
        score = service._score_persona_response(
            user_text=payload.user_text,
            assistant_text=payload.assistant_text,
            category=payload.category,
            surface=payload.surface,
        )
        return {"persona_score": score or {"available": False}}

    @app.post("/sessions", response_model=SessionResponse)
    async def create_session():
        response = _read_config_response(config_file)
        current_config = response.model_dump() if hasattr(response, "model_dump") else response.dict()
        return SessionResponse(**get_service().create_session(extra_settings=current_config))

    @app.get("/sessions/{session_id}", response_model=SessionDetail)
    async def load_session(session_id: str):
        summary = _find_session(config_file, session_id)
        if summary is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        session_config_overrides[session_id] = dict(summary.settings_snapshot)
        session_path = Path(summary.session_path)
        return SessionDetail(
            **summary.dict(),
            messages=_load_transcript(session_path),
            config=_config_response_from_snapshot(config_file, summary.settings_snapshot),
        )

    @app.patch("/sessions/{session_id}", response_model=SessionSummary)
    async def update_session(session_id: str, payload: SessionUpdate):
        summary = _find_session(config_file, session_id)
        if summary is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        if payload.display_name is None:
            raise HTTPException(status_code=400, detail="display_name is required.")
        updated = _update_session_display_name(summary, payload.display_name)
        if session_id in session_config_overrides:
            session_config_overrides[session_id]["display_name"] = updated.display_name
        return updated

    @app.delete("/sessions/{session_id}")
    async def delete_session(session_id: str):
        summary = _find_session(config_file, session_id)
        if summary is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        _delete_session_dir(config_file, summary)
        session_config_overrides.pop(session_id, None)
        return {"deleted": True, "session_id": session_id}

    @app.post("/consolidate/{session_id}", response_model=ConsolidateResponse)
    async def consolidate(session_id: str):
        result = get_service_for_session(session_id).consolidate_session_memory(session_id)
        return ConsolidateResponse(result=result)

    @app.get("/planning/search")
    async def planning_search(q: str = Query(..., min_length=1), limit: int = Query(5, ge=1, le=10)):
        return web_search(q, limit=limit)

    @app.get("/planning/{session_id}", response_model=PlanningResponse)
    async def get_planning(session_id: str):
        return planning_response_for_session(session_id, force=False)

    @app.post("/planning/{session_id}/regenerate", response_model=PlanningResponse)
    async def regenerate_planning(session_id: str):
        return planning_response_for_session(session_id, force=True)

    @app.get("/integrations/line/settings", response_model=LineSettingsResponse)
    async def line_settings():
        return _read_line_settings_response()

    @app.post("/integrations/line/settings", response_model=LineSettingsResponse)
    async def update_line_settings(payload: LineSettingsUpdate):
        if payload.surface_policy_text is not None:
            try:
                parsed = json.loads(payload.surface_policy_text or "{}")
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid surface policy JSON: {exc}") from exc
            if not isinstance(parsed, dict):
                raise HTTPException(status_code=400, detail="Surface policy JSON must be an object.")
            _write_text_file(
                LINE_SURFACE_POLICY_FILE,
                json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
            )
        if payload.env_text is not None:
            _write_text_file(LINE_ENV_FILE, payload.env_text)
        return _read_line_settings_response()

    @app.get("/integrations/line/runtime/status", response_model=ProcessStatusResponse)
    async def get_line_runtime_status():
        return process_status(line_runtime_state)

    @app.post("/integrations/line/runtime/start", response_model=ProcessStatusResponse)
    async def start_line_runtime(payload: LineRuntimeStartRequest):
        process = line_runtime_state.get("process")
        if process and process.poll() is None:
            return process_status(line_runtime_state, message="LINE bot is already running.")
        runner = PROJECT_ROOT / "line" / "run_line_bot.py"
        if not runner.exists():
            raise HTTPException(status_code=404, detail="line/run_line_bot.py was not found.")
        env = os.environ.copy()
        env["ROLEWEAVER_LINE_HOST"] = payload.host
        env["ROLEWEAVER_LINE_PORT"] = str(payload.port)
        command = [sys.executable, str(runner)]
        try:
            process = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to start LINE bot: {exc}") from exc
        line_runtime_state.update({
            "process": process,
            "command": command,
            "log": [],
            "message": f"LINE bot is starting on {payload.host}:{payload.port}.",
        })
        threading.Thread(target=read_process_output, args=(process, line_runtime_state), daemon=True).start()
        time.sleep(0.5)
        return process_status(line_runtime_state)

    @app.post("/integrations/line/runtime/stop", response_model=ProcessStatusResponse)
    async def stop_line_runtime():
        process = line_runtime_state.get("process")
        if process and process.poll() is None:
            process.terminate()
            line_runtime_state["message"] = "LINE bot stop requested."
        return process_status(line_runtime_state)

    @app.get("/integrations/tunnel/status", response_model=TunnelStatusResponse)
    async def get_tunnel_status():
        return tunnel_status()

    @app.post("/integrations/tunnel/start", response_model=TunnelStatusResponse)
    async def start_tunnel(payload: TunnelStartRequest):
        provider = (payload.provider or "cloudflared").lower()
        if provider != "cloudflared":
            raise HTTPException(status_code=400, detail="Only cloudflared quick tunnels are supported for now.")
        process = tunnel_state.get("process")
        if process and process.poll() is None:
            return tunnel_status(message="Tunnel is already running.")
        cloudflared = _find_cloudflared(payload.cloudflared_path)
        if not cloudflared:
            raise HTTPException(
                status_code=404,
                detail="cloudflared was not found. Put cloudflared.exe in tools/, runtime/, PATH, or set ROLEWEAVER_CLOUDFLARED_PATH.",
            )
        target_url = payload.target_url.strip() or "http://127.0.0.1:8010"
        if not re.match(r"^https?://", target_url):
            raise HTTPException(status_code=400, detail="target_url must start with http:// or https://")
        command = [cloudflared, "tunnel", "--url", target_url]
        try:
            process = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to start cloudflared: {exc}") from exc
        tunnel_state.update({
            "process": process,
            "provider": "cloudflared",
            "target_url": target_url,
            "public_url": "",
            "command": command,
            "log": [],
            "message": "Tunnel is starting. The URL may take a few seconds to appear.",
        })
        threading.Thread(target=read_tunnel_output, args=(process,), daemon=True).start()
        deadline = time.time() + 12
        while time.time() < deadline:
            status = tunnel_status()
            if status.public_url or not status.active:
                return status
            time.sleep(0.25)
        return tunnel_status()

    @app.post("/integrations/tunnel/stop", response_model=TunnelStatusResponse)
    async def stop_tunnel():
        process = tunnel_state.get("process")
        if process and process.poll() is None:
            process.terminate()
            tunnel_state["message"] = "Tunnel stop requested."
        return tunnel_status()

    @app.get("/sessions/{session_id}/memories")
    async def list_memories(
        session_id: str,
        include_inactive: bool = True,
        status: Optional[str] = None,
        query: Optional[str] = None,
    ):
        summary = _find_session(config_file, session_id)
        if summary is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        memories = get_service_for_session(session_id).list_session_memories(
            session_id,
            include_inactive=include_inactive,
            status=status,
            query=query,
        )
        return {"session_id": session_id, "memories": memories}

    @app.get("/sessions/{session_id}/memory-os")
    async def memory_os_snapshot(session_id: str):
        summary = _find_session(config_file, session_id)
        if summary is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        return {
            "session_id": session_id,
            "memory_os": get_service_for_session(session_id).session_memory_os_snapshot(session_id),
        }

    @app.get("/sessions/{session_id}/shiro")
    async def shiro_status(session_id: str):
        summary = _find_session(config_file, session_id)
        if summary is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        return get_service_for_session(session_id).shiro_status(session_id)

    @app.post("/sessions/{session_id}/shiro/observe")
    async def observe_shiro(session_id: str, payload: ShiroObserveRequest):
        summary = _find_session(config_file, session_id)
        if summary is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        return get_service_for_session(session_id).observe_shiro_stimulus(
            session_id,
            payload.text,
            source=payload.source,
            metadata=payload.metadata,
        )

    @app.post("/sessions/{session_id}/shiro/tool-intentions")
    async def infer_shiro_tool_intentions(session_id: str, payload: ShiroToolIntentRequest):
        summary = _find_session(config_file, session_id)
        if summary is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        return get_service_for_session(session_id).infer_shiro_tool_intentions(
            session_id,
            payload.text,
            metadata=payload.metadata,
        )

    @app.patch("/sessions/{session_id}/memories/{memory_id}")
    async def update_memory(session_id: str, memory_id: int, payload: MemoryUpdate):
        summary = _find_session(config_file, session_id)
        if summary is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No memory fields to update.")
        try:
            memory = get_service_for_session(session_id).update_session_memory(session_id, memory_id, **updates)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if memory is None:
            raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")
        return {"session_id": session_id, "memory": memory}

    @app.delete("/sessions/{session_id}/memories/{memory_id}")
    async def delete_memory(session_id: str, memory_id: int):
        summary = _find_session(config_file, session_id)
        if summary is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        deleted = get_service_for_session(session_id).delete_session_memory(session_id, memory_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")
        return {"deleted": True, "session_id": session_id, "memory_id": memory_id}

    return app


app = create_app()


def main():
    parser = argparse.ArgumentParser(description="RoleWeaver HTTP API")
    parser.add_argument("--config", default=None, help="RoleWeaver CSV/TOML/JSON config file")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(create_app(config_file=args.config), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
