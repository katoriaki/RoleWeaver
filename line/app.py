import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import (
    GroupSource,
    MessageEvent,
    RoomSource,
    TextMessageContent,
    UserSource,
)

from role_chat_service import RoleChatService
from role_config import (
    DEFAULT_BASE_MODEL_PATH,
    DEFAULT_IDLE_CONSOLIDATION_SECONDS,
    DEFAULT_LORA_PATH,
    RoleConfig,
    normalize_idle_consolidation_seconds,
)


LINE_DIR = Path(__file__).resolve().parent
load_dotenv(LINE_DIR / ".env", override=False)
load_dotenv(override=False)

app = FastAPI(title="RoleWeaver LINE Bot")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@lru_cache(maxsize=1)
def get_line_parser() -> WebhookParser:
    return WebhookParser(_required_env("LINE_CHANNEL_SECRET"))


@lru_cache(maxsize=1)
def get_line_configuration() -> Configuration:
    return Configuration(access_token=_required_env("LINE_CHANNEL_ACCESS_TOKEN"))


def _env_first(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


@lru_cache(maxsize=1)
def get_chat_service() -> RoleChatService:
    default_session_root = str((LINE_DIR.parent / "data" / "line_sessions").resolve())
    config = RoleConfig.from_env(
        role_name=_env_first("ROLEWEAVER_ROLE_NAME", "MISUZU_ROLE_NAME"),
        user_subject=_env_first("ROLEWEAVER_USER_SUBJECT", "MISUZU_USER_SUBJECT"),
        base_model_path=_env_first("ROLEWEAVER_BASE_MODEL_PATH", "MISUZU_BASE_MODEL_PATH")
        or DEFAULT_BASE_MODEL_PATH,
        lora_path=_env_first("ROLEWEAVER_LORA_PATH", "MISUZU_LORA_PATH") or DEFAULT_LORA_PATH,
        skill_file=_env_first("ROLEWEAVER_SKILL_FILE", "MISUZU_SKILL_FILE"),
        session_root=_env_first("ROLEWEAVER_SESSION_ROOT", "MISUZU_SESSION_ROOT")
        or default_session_root,
        idle_consolidation_seconds=normalize_idle_consolidation_seconds(
            _env_first("ROLEWEAVER_IDLE_CONSOLIDATION_SECONDS", "MISUZU_IDLE_CONSOLIDATION_SECONDS"),
            default=DEFAULT_IDLE_CONSOLIDATION_SECONDS,
        ),
    )
    return RoleChatService(config=config)


def build_session_id(source) -> str:
    if isinstance(source, UserSource) and source.user_id:
        return f"line_user_{source.user_id}"
    if isinstance(source, GroupSource):
        user_part = getattr(source, "user_id", None) or "anonymous"
        return f"line_group_{source.group_id}_{user_part}"
    if isinstance(source, RoomSource):
        user_part = getattr(source, "user_id", None) or "anonymous"
        return f"line_room_{source.room_id}_{user_part}"
    return "line_default"


def split_reply_text(text: str, chunk_size: int = 4500) -> list[str]:
    text = (text or "").strip()
    if not text:
        return ["……"]
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


def send_reply(reply_token: str, text: str):
    messages = [TextMessage(text=chunk) for chunk in split_reply_text(text)[:5]]
    with ApiClient(get_line_configuration()) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages,
            )
        )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/callback")
async def callback(
    request: Request,
    x_line_signature: Optional[str] = Header(default=None),
):
    body_bytes = await request.body()
    body = body_bytes.decode("utf-8")
    signature = x_line_signature

    if not signature:
        raise HTTPException(status_code=400, detail="Missing X-Line-Signature")

    try:
        events = get_line_parser().parse(body, signature)
    except InvalidSignatureError as exc:
        raise HTTPException(status_code=400, detail="Invalid LINE signature") from exc

    if not events:
        return JSONResponse({"status": "ok", "events": 0})

    service = get_chat_service()

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            session_id = build_session_id(event.source)
            user_text = event.message.text.strip()
            reply_text = service.chat_once(user_text=user_text, session_id=session_id)
            send_reply(event.reply_token, reply_text)

    return JSONResponse({"status": "ok", "events": len(events)})
