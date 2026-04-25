import argparse
from functools import lru_cache
from typing import Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel

from role_chat_service import RoleChatService
from role_config import RoleConfig


class ChatRequest(BaseModel):
    user_text: str
    session_id: str = "api"
    max_new_tokens: int = 120


class ChatResponse(BaseModel):
    text: str
    session_id: str


class ConsolidateResponse(BaseModel):
    result: dict


def create_app(config_file: Optional[str] = None) -> FastAPI:
    app = FastAPI(title="RoleWeaver API")

    @lru_cache(maxsize=1)
    def get_service() -> RoleChatService:
        config = RoleConfig.from_env(config_file=config_file)
        return RoleChatService(config=config)

    @app.get("/health")
    async def health():
        service = get_service()
        return {
            "status": "ok",
            "role_name": service.config.role_name,
            "base_model_path": service.config.base_model_path,
            "lora_path": service.config.lora_path,
            "skill_file": service.config.skill_file,
        }

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
