import argparse
import csv
import json
from functools import lru_cache
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
    normalize_quantization_mode,
)


WEB_ROOT = PROJECT_ROOT / "web"
CONFIG_NOTES = {
    "base_model_path": "Required: local path to the base model directory",
    "lora_path": "Optional: local path to the trained LoRA adapter directory; leave blank to use the base model only",
    "skill_file": "Optional: local path to the role SKILL.md file",
    "skill_text": "Optional: short inline skill text; useful for small role notes without a file",
    "quantization_mode": "Model loading mode: 4bit, 8bit, bf16, fp16, or none",
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


class ConfigUpdate(BaseModel):
    base_model_path: Optional[str] = None
    lora_path: Optional[str] = None
    skill_file: Optional[str] = None
    skill_text: Optional[str] = None
    quantization_mode: Optional[str] = None
    ui_language: Optional[str] = None


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
        summaries.append(SessionSummary(
            session_id=session_id,
            display_name=meta.get("display_name") or session_id,
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


def create_app(config_file: Optional[str] = None) -> FastAPI:
    app = FastAPI(title="RoleWeaver API")
    session_config_overrides: Dict[str, Dict] = {}
    service_cache: Dict[str, RoleChatService] = {}

    @lru_cache(maxsize=1)
    def get_service() -> RoleChatService:
        config = RoleConfig.from_env(config_file=config_file)
        return RoleChatService(config=config)

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
            )
            service_cache[key] = RoleChatService(config=config)
        return service_cache[key]

    def get_service_for_session(session_id: str) -> RoleChatService:
        snapshot = session_config_overrides.get(session_id)
        if snapshot:
            return service_for_snapshot(snapshot)
        return get_service()

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
            "memory_root": str(service.memory_root),
            "memory_scope_path": str(service.session_root),
        }

    @app.get("/config", response_model=ConfigResponse)
    async def get_config():
        return _read_config_response(config_file)

    @app.post("/config", response_model=ConfigResponse)
    async def update_config(payload: ConfigUpdate):
        response = _write_config(config_file, payload)
        get_service.cache_clear()
        service_cache.clear()
        return response

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
