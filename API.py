import argparse
import csv
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from role_chat_service import RoleChatService
from role_config import (
    DEFAULT_CONFIG_FILENAMES,
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


class SessionResponse(BaseModel):
    session_id: str
    session_path: str
    memory_scope_path: str


class ConfigResponse(BaseModel):
    config_file: str
    base_model_path: str = ""
    lora_path: str = ""
    skill_file: str = ""
    skill_text: str = ""
    quantization_mode: str = "4bit"
    ui_language: str = "zh"


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
    return _read_config_response(str(path))


def create_app(config_file: Optional[str] = None) -> FastAPI:
    app = FastAPI(title="RoleWeaver API")

    @lru_cache(maxsize=1)
    def get_service() -> RoleChatService:
        config = RoleConfig.from_env(config_file=config_file)
        return RoleChatService(config=config)

    @app.get("/", include_in_schema=False)
    async def web_index():
        index_file = WEB_ROOT / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return HTMLResponse(
            "<h1>RoleWeaver API</h1><p>web/index.html was not found. The API is still running.</p>"
        )

    @app.get("/health")
    async def health():
        service = get_service()
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
        return response

    @app.post("/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest):
        text = get_service().chat_once(
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
        text = get_service().chat_once(
            user_text=user_text,
            session_id=session_id,
            max_new_tokens=max_new_tokens,
        )
        return ChatResponse(text=text, session_id=session_id)

    @app.post("/sessions", response_model=SessionResponse)
    async def create_session():
        return SessionResponse(**get_service().create_session())

    @app.post("/consolidate/{session_id}", response_model=ConsolidateResponse)
    async def consolidate(session_id: str):
        result = get_service().consolidate_session_memory(session_id)
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
