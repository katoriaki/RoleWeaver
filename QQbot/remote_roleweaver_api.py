import argparse
from functools import lru_cache

from fastapi import FastAPI
from pydantic import BaseModel

from role_chat_service import RoleChatService
from role_config import RoleConfig


class ChatRequest(BaseModel):
    session_id: str = "qqbot"
    user_text: str
    max_new_tokens: int = 120


class ChatResponse(BaseModel):
    text: str


def create_app(config_file: str = None) -> FastAPI:
    app = FastAPI(title="RoleWeaver Remote Chat API")

    @lru_cache(maxsize=1)
    def get_service() -> RoleChatService:
        config = RoleConfig.from_env(config_file=config_file)
        return RoleChatService(config=config)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest):
        text = get_service().chat_once(
            user_text=payload.user_text,
            session_id=payload.session_id,
            max_new_tokens=payload.max_new_tokens,
        )
        return ChatResponse(text=text)

    return app


app = create_app()


def main():
    parser = argparse.ArgumentParser(description="Remote RoleWeaver /chat API for QQbot SSH tunneling")
    parser.add_argument("--config", default=None, help="RoleWeaver CSV/TOML/JSON config file on the server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(create_app(config_file=args.config), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
