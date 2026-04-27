import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from role_chat_service import RoleChatService
from role_config import (
    DEFAULT_CONFIG_FILENAMES,
    DEFAULT_SESSION_ROOT,
    PROJECT_ROOT,
    RoleConfig,
    discover_config_file,
    load_config_values,
    normalize_optional_path,
    normalize_device_map_mode,
    normalize_quantization_mode,
)


WEB_ROOT = PROJECT_ROOT / "web"
TRAINING_SCRIPT = PROJECT_ROOT / "resources" / "qwen35_lora_training" / "train_qwen35_lora_offline.py"
TRAINING_EXCEL_CONVERTER = PROJECT_ROOT / "resources" / "qwen35_lora_training" / "convert_excel_to_jsonl.py"
TRAINING_TEMPLATE = PROJECT_ROOT / "resources" / "qwen35_lora_training" / "role_sft_template.xlsx"
TRAINING_RUNS_ROOT = PROJECT_ROOT / "training_runs"
CONFIG_NOTES = {
    "base_model_path": "Required: local path to the base model directory",
    "lora_path": "Optional: local path to the trained LoRA adapter directory; leave blank to use the base model only",
    "skill_file": "Optional: local path to the role SKILL.md file; nearby references/*.md are loaded automatically",
    "skill_text": "Optional: short inline skill text; useful for small role notes without a file",
    "quantization_mode": "Model loading mode: 4bit, 8bit, bf16, fp16, or none",
    "device_map_mode": "Device placement: gpu rejects CPU offload; auto allows CPU offload when VRAM is insufficient",
    "ui_language": "Web UI language: zh, ja, or en",
}


class ChatRequest(BaseModel):
    user_text: str
    session_id: str = "api"
    max_new_tokens: int = 120


class ChatResponse(BaseModel):
    text: str
    session_id: str


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


class ConfigUpdate(BaseModel):
    base_model_path: Optional[str] = None
    lora_path: Optional[str] = None
    skill_file: Optional[str] = None
    skill_text: Optional[str] = None
    quantization_mode: Optional[str] = None
    device_map_mode: Optional[str] = None
    ui_language: Optional[str] = None


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


def _target_config_path(config_file: Optional[str]) -> Path:
    try:
        existing = discover_config_file(config_file)
    except FileNotFoundError:
        existing = Path(config_file).expanduser() if config_file else None
    if existing is not None:
        return existing
    return PROJECT_ROOT / DEFAULT_CONFIG_FILENAMES[0]


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
        ui_language=(snapshot.get("ui_language") or "zh").lower(),
    )


def _write_config(config_file: Optional[str], update: ConfigUpdate) -> ConfigResponse:
    current = _read_config_response(config_file).dict()
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
                "ui_language",
            ]:
                writer.writerow([key, current.get(key, ""), CONFIG_NOTES.get(key, "")])
    except PermissionError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Config file is locked or not writable: {path}",
        ) from exc
    return _read_config_response(str(path))


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
    app = FastAPI(title="RoleWeaver API")
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

    def get_service() -> RoleChatService:
        nonlocal default_service
        if default_service is None:
            config = RoleConfig.from_env(config_file=config_file)
            default_service = RoleChatService(config=config)
        return default_service

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
                quantization_mode=snapshot.get("quantization_mode"),
                device_map_mode=snapshot.get("device_map_mode"),
            )
            service_cache[key] = RoleChatService(config=config)
        return service_cache[key]

    def snapshot_for_session(session_id: Optional[str]) -> Optional[Dict]:
        if not session_id:
            return None
        if session_id in session_config_overrides:
            return session_config_overrides[session_id]
        summary = _find_session(config_file, session_id)
        if summary is None:
            return None
        session_config_overrides[session_id] = dict(summary.settings_snapshot)
        return session_config_overrides[session_id]

    def get_service_for_session(session_id: str) -> RoleChatService:
        nonlocal active_service_key
        snapshot = snapshot_for_session(session_id)
        if snapshot:
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

    @app.get("/", include_in_schema=False)
    async def web_index():
        index_file = WEB_ROOT / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return HTMLResponse(
            "<h1>RoleWeaver API</h1><p>web/index.html was not found. The API is still running.</p>"
        )

    @app.get("/health")
    async def health(session_id: Optional[str] = None):
        snapshot = snapshot_for_session(session_id)
        if snapshot:
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
                "memory_root": str(_session_root_for_config(config_file)),
                "memory_scope_path": "",
                "session_settings_persistent": True,
            }
        service = get_service_for_session(session_id) if session_id else get_service()
        return {
            "status": "ok",
            "role_name": service.config.role_name,
            "base_model_path": service.config.base_model_path,
            "lora_path": service.config.lora_path,
            "lora_enabled": bool(service.config.lora_path),
            "skill_file": service.config.skill_file,
            "skill_text_present": bool(service.config.skill_text),
            "quantization_mode": service.config.quantization_mode,
            "device_map_mode": service.config.device_map_mode,
            "memory_root": str(service.memory_root),
            "memory_scope_path": str(service.session_root),
        }

    @app.get("/config", response_model=ConfigResponse)
    async def get_config():
        return _read_config_response(config_file)

    @app.post("/config", response_model=ConfigResponse)
    async def update_config(payload: ConfigUpdate):
        response = _write_config(config_file, payload)
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
        text = get_service_for_session(payload.session_id).chat_once(
            user_text=payload.user_text,
            session_id=payload.session_id,
            max_new_tokens=payload.max_new_tokens,
        )
        return ChatResponse(text=text, session_id=payload.session_id)

    @app.get("/chat", response_model=ChatResponse)
    async def chat_get(
        user_text: str = Query(...),
        session_id: str = "api",
        max_new_tokens: int = 120,
    ):
        text = get_service_for_session(session_id).chat_once(
            user_text=user_text,
            session_id=session_id,
            max_new_tokens=max_new_tokens,
        )
        return ChatResponse(text=text, session_id=session_id)

    @app.post("/sessions", response_model=SessionResponse)
    async def create_session():
        current_config = _read_config_response(config_file).dict()
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
