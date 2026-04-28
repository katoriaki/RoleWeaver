import os
import traceback
import asyncio
import json
import subprocess
import wave
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib import request as urlrequest
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    AudioMessage,
    ApiClient,
    Configuration,
    MessagingApi,
    MessagingApiBlob,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import (
    GroupSource,
    ImageMessageContent,
    MessageEvent,
    RoomSource,
    TextMessageContent,
    UserSource,
)

from role_chat_service import RoleChatService
from role_config import (
    DEFAULT_IDLE_CONSOLIDATION_SECONDS,
    RoleConfig,
    normalize_idle_consolidation_seconds,
)


LINE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = LINE_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
CONTACTS_PATH = DATA_DIR / "line_contacts.json"
WAKEUP_STATE_PATH = DATA_DIR / "line_wakeup_state.json"
DEFAULT_AUDIO_DIR = DATA_DIR / "line_audio"
DEFAULT_IMAGE_DIR = DATA_DIR / "line_images"
load_dotenv(LINE_DIR / ".env", override=False)
load_dotenv(override=False)

app = FastAPI(title="RoleWeaver LINE Bot")
_wakeup_task: Optional[asyncio.Task] = None


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _env_first(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _truthy_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def line_max_new_tokens() -> int:
    value = _env_int("ROLEWEAVER_LINE_MAX_NEW_TOKENS", 192)
    return max(16, min(4096, value))


def _parse_hhmm(value: str, default_hour: int, default_minute: int = 0) -> tuple[int, int]:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (AttributeError, ValueError):
        return default_hour, default_minute
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return default_hour, default_minute
    return hour, minute


def _json_load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _json_save(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@lru_cache(maxsize=1)
def get_line_parser() -> WebhookParser:
    return WebhookParser(_required_env("LINE_CHANNEL_SECRET"))


@lru_cache(maxsize=1)
def get_line_configuration() -> Configuration:
    return Configuration(access_token=_required_env("LINE_CHANNEL_ACCESS_TOKEN"))


@lru_cache(maxsize=1)
def get_chat_service() -> RoleChatService:
    default_session_root = str((LINE_DIR.parent / "data" / "line_sessions").resolve())
    config_file = _env_first("ROLEWEAVER_CONFIG_FILE", "MISUZU_CONFIG_FILE")
    session_root = _env_first("ROLEWEAVER_SESSION_ROOT", "MISUZU_SESSION_ROOT")
    if not config_file and not session_root:
        session_root = default_session_root

    config = RoleConfig.from_env(
        config_file=config_file,
        role_name=_env_first("ROLEWEAVER_ROLE_NAME", "MISUZU_ROLE_NAME"),
        user_subject=_env_first("ROLEWEAVER_USER_SUBJECT", "MISUZU_USER_SUBJECT"),
        base_model_path=_env_first("ROLEWEAVER_BASE_MODEL_PATH", "MISUZU_BASE_MODEL_PATH"),
        lora_path=_env_first("ROLEWEAVER_LORA_PATH", "MISUZU_LORA_PATH"),
        skill_file=_env_first("ROLEWEAVER_SKILL_FILE", "MISUZU_SKILL_FILE"),
        session_root=session_root,
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


def build_push_target(source) -> Optional[tuple[str, str]]:
    if isinstance(source, UserSource) and source.user_id:
        return f"user:{source.user_id}", source.user_id
    if isinstance(source, GroupSource) and source.group_id:
        return f"group:{source.group_id}", source.group_id
    if isinstance(source, RoomSource) and source.room_id:
        return f"room:{source.room_id}", source.room_id
    return None


def remember_contact(source, wakeup_enabled: Optional[bool] = None) -> Optional[str]:
    target = build_push_target(source)
    if target is None:
        return None
    key, to = target
    payload = _json_load(CONTACTS_PATH, {"contacts": {}})
    contacts = payload.setdefault("contacts", {})
    item = contacts.get(key, {})
    item.update(
        {
            "key": key,
            "to": to,
            "type": key.split(":", 1)[0],
            "last_seen_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    if wakeup_enabled is not None:
        item["wakeup_enabled"] = wakeup_enabled
    else:
        item.setdefault("wakeup_enabled", _truthy_env("ROLEWEAVER_WAKEUP_AUTO_SUBSCRIBE", False))
    contacts[key] = item
    _json_save(CONTACTS_PATH, payload)
    return key


def get_wakeup_contacts() -> list[dict]:
    payload = _json_load(CONTACTS_PATH, {"contacts": {}})
    contacts = payload.get("contacts", {})
    return [item for item in contacts.values() if item.get("wakeup_enabled") and item.get("to")]


def split_reply_text(text: str, chunk_size: int = 4500) -> list[str]:
    text = (text or "").strip()
    if not text:
        return ["..."]
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


def build_help_text() -> str:
    return (
        "RoleWeaver LINE Bot is online.\n"
        "Send any text message to chat with the current role.\n"
        "Commands:\n"
        "/help - show this help\n"
        "/ping - health check\n"
        "/status - show runtime status\n"
        "/wake on - enable 7:00 wake-up push\n"
        "/wake off - disable wake-up push"
    )


def handle_builtin_command(text: str, source=None) -> Optional[str]:
    command = text.strip().lower()
    if command in {"/help", "help", "帮助"}:
        return build_help_text()
    if command in {"/ping", "ping"}:
        return "pong"
    if command in {"/status", "status", "状态"}:
        try:
            config = get_chat_service().config
            return (
                "RoleWeaver is ready.\n"
                f"Role: {config.role_name}\n"
                f"LoRA: {'enabled' if config.lora_path else 'disabled'}"
            )
        except Exception as exc:
            return f"RoleWeaver is not ready: {exc}"
    if command in {"/wake on", "/wakeup on", "起床提醒 on", "起床提醒 开"}:
        remember_contact(source, wakeup_enabled=True)
        return "Wake-up push is on. I will message you at 07:00 while this bot server is running."
    if command in {"/wake off", "/wakeup off", "起床提醒 off", "起床提醒 关"}:
        remember_contact(source, wakeup_enabled=False)
        return "Wake-up push is off."
    return None


def send_reply(reply_token: str, text: str):
    messages = [TextMessage(text=chunk) for chunk in split_reply_text(text)[:5]]
    with ApiClient(get_line_configuration()) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages,
            )
        )


def send_reply_audio(reply_token: str, audio_url: str, duration_ms: int):
    with ApiClient(get_line_configuration()) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[AudioMessage(originalContentUrl=audio_url, duration=duration_ms)],
            )
        )


def _time_in_window(now: datetime, start: tuple[int, int], end: tuple[int, int]) -> bool:
    start_time = now.replace(hour=start[0], minute=start[1], second=0, microsecond=0)
    end_time = now.replace(hour=end[0], minute=end[1], second=0, microsecond=0)
    if start_time <= end_time:
        return start_time <= now < end_time
    return now >= start_time or now < end_time


def _voice_text_only_window_active(now: Optional[datetime] = None) -> bool:
    if not _truthy_env("ROLEWEAVER_VOICE_TEXT_ONLY_WINDOW_ENABLED", default=False):
        return False
    timezone_name = os.getenv("ROLEWEAVER_VOICE_TEXT_ONLY_TIMEZONE") or os.getenv(
        "ROLEWEAVER_WAKEUP_TIMEZONE", "Asia/Tokyo"
    )
    tz = ZoneInfo(timezone_name)
    current = now.astimezone(tz) if now else datetime.now(tz)
    start = _parse_hhmm(os.getenv("ROLEWEAVER_VOICE_TEXT_ONLY_START", "08:00"), 8, 0)
    end = _parse_hhmm(os.getenv("ROLEWEAVER_VOICE_TEXT_ONLY_END", "17:30"), 17, 30)
    return _time_in_window(current, start, end)


def _voice_rejected(user_text: str) -> bool:
    text = (user_text or "").strip().lower()
    if not text:
        return False
    negative_markers = (
        "不要语音",
        "不用语音",
        "别发语音",
        "只要文字",
        "文字で",
        "音声なし",
        "声なし",
        "テキストで",
        "no voice",
        "no audio",
        "text only",
    )
    return any(marker in text for marker in negative_markers)


def _voice_requested_once(user_text: str) -> bool:
    text = (user_text or "").strip().lower()
    if not text or _voice_rejected(text):
        return False
    positive_markers = (
        "语音",
        "語音",
        "音频",
        "音訊",
        "合成一次",
        "用声音",
        "发语音",
        "念一下",
        "读出来",
        "讀出來",
        "音声",
        "ボイス",
        "声で",
        "読み上げ",
        "読んで",
        "喋って",
        "しゃべって",
        "voice",
        "audio",
        "speak",
        "say it",
        "read aloud",
        "read it aloud",
    )
    return any(marker in text for marker in positive_markers)


def should_use_voice_reply(user_text: str, now: Optional[datetime] = None) -> bool:
    if _voice_rejected(user_text):
        return False
    if _voice_requested_once(user_text):
        return True
    if _voice_text_only_window_active(now):
        return False
    return _truthy_env("ROLEWEAVER_REPLY_VOICE", default=False)


def send_chat_reply(reply_token: str, text: str, target_key: str, user_text: str):
    if not should_use_voice_reply(user_text):
        send_reply(reply_token, text)
        return
    try:
        audio = synthesize_line_audio(text, target_key)
        if audio:
            audio_url, duration_ms = audio
            send_reply_audio(reply_token, audio_url, duration_ms)
            return
    except Exception:
        print("[RoleWeaver LINE] Voice reply failed; falling back to text:")
        traceback.print_exc()
    send_reply(reply_token, text)


def _line_image_dir() -> Path:
    return Path(os.getenv("ROLEWEAVER_LINE_IMAGE_DIR") or DEFAULT_IMAGE_DIR)


def _line_image_prompt() -> str:
    return os.getenv(
        "ROLEWEAVER_LINE_IMAGE_PROMPT",
        "请看这张图片，并用当前角色的语气像 LINE 聊天一样短一点、自然回应。不要机械描述，只抓用户可能想让你注意的重点。",
    )


def download_line_image(message_id: str, session_id: str) -> Path:
    output_dir = _line_image_dir() / session_id
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{message_id}.jpg"
    with ApiClient(get_line_configuration()) as api_client:
        content = MessagingApiBlob(api_client).get_message_content(message_id)
    target.write_bytes(bytes(content))
    return target


def push_text(to: str, text: str):
    messages = [TextMessage(text=chunk) for chunk in split_reply_text(text)[:5]]
    with ApiClient(get_line_configuration()) as api_client:
        MessagingApi(api_client).push_message(PushMessageRequest(to=to, messages=messages))


def push_audio(to: str, audio_url: str, duration_ms: int):
    with ApiClient(get_line_configuration()) as api_client:
        MessagingApi(api_client).push_message(
            PushMessageRequest(
                to=to,
                messages=[AudioMessage(originalContentUrl=audio_url, duration=duration_ms)],
            )
        )


def _audio_output_dir() -> Path:
    return Path(os.getenv("ROLEWEAVER_LINE_AUDIO_OUTPUT_DIR") or DEFAULT_AUDIO_DIR)


def _public_base_url() -> str:
    return (os.getenv("ROLEWEAVER_PUBLIC_BASE_URL") or "").rstrip("/")


def _tts_payload(text: str) -> dict:
    return {
        "refer_wav_path": _clean_env_path(os.getenv("ROLEWEAVER_TTS_REFER_WAV_PATH", "")),
        "prompt_text": os.getenv("ROLEWEAVER_TTS_PROMPT_TEXT", ""),
        "prompt_language": os.getenv("ROLEWEAVER_TTS_PROMPT_LANGUAGE", "ja"),
        "text": text,
        "text_language": os.getenv("ROLEWEAVER_TTS_TEXT_LANGUAGE", "ja"),
        "cut_punc": os.getenv("ROLEWEAVER_TTS_CUT_PUNC", "。！？"),
        "speed": float(os.getenv("ROLEWEAVER_TTS_SPEED", "1.0")),
    }


def _clean_env_path(value: str) -> str:
    value = (value or "").strip()
    if value.startswith(('r"', "r'")) and value.endswith(("\"", "'")):
        value = value[2:-1]
    return value.strip().strip('"').strip("'")


def _tts_reference_ready() -> bool:
    ref_path = _clean_env_path(os.getenv("ROLEWEAVER_TTS_REFER_WAV_PATH", ""))
    prompt_text = os.getenv("ROLEWEAVER_TTS_PROMPT_TEXT", "").strip()
    prompt_lang = os.getenv("ROLEWEAVER_TTS_PROMPT_LANGUAGE", "").strip()
    if not ref_path or not prompt_text or not prompt_lang:
        return False
    return Path(ref_path).exists()


def _wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        if rate <= 0:
            return 1000
        return max(1000, int(frames / rate * 1000))


def synthesize_line_audio(text: str, target_key: str) -> Optional[tuple[str, int]]:
    public_base = _public_base_url()
    if not public_base:
        print("[RoleWeaver LINE] ROLEWEAVER_PUBLIC_BASE_URL is empty; wake-up voice falls back to text.")
        return None
    if not _tts_reference_ready():
        print(
            "[RoleWeaver LINE] TTS reference is not ready; set "
            "ROLEWEAVER_TTS_REFER_WAV_PATH, ROLEWEAVER_TTS_PROMPT_TEXT, and ROLEWEAVER_TTS_PROMPT_LANGUAGE."
        )
        return None

    output_dir = _audio_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_target = target_key.replace(":", "_")
    wav_path = output_dir / f"wakeup_{stamp}_{safe_target}.wav"
    mp3_path = wav_path.with_suffix(".mp3")

    tts_url = os.getenv("ROLEWEAVER_TTS_URL", "http://127.0.0.1:9880/")
    data = json.dumps(_tts_payload(text), ensure_ascii=False).encode("utf-8")
    req = urlrequest.Request(tts_url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    timeout = _env_int("ROLEWEAVER_TTS_TIMEOUT_SECONDS", 180)
    with urlrequest.urlopen(req, timeout=timeout) as response:
        audio_bytes = response.read()
    wav_path.write_bytes(audio_bytes)
    duration_ms = _wav_duration_ms(wav_path)

    ffmpeg = Path(os.getenv("ROLEWEAVER_TTS_FFMPEG_PATH") or PROJECT_ROOT / "G" / "runtime" / "ffmpeg.exe")
    if ffmpeg.exists():
        subprocess.run(
            [
                str(ffmpeg),
                "-y",
                "-i",
                str(wav_path),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "96k",
                str(mp3_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        public_name = mp3_path.name
    else:
        print("[RoleWeaver LINE] ffmpeg not found; cannot convert LINE audio to mp3.")
        return None

    return f"{public_base}/audio/{public_name}", duration_ms


def build_wakeup_text(target_key: str) -> str:
    prompt = os.getenv(
        "ROLEWEAVER_WAKEUP_PROMPT",
        "现在是早上7点。请作为秦谷美鈴，用日语轻轻叫醒制作人。短一点，像真人发来的早安，不要解释。",
    )
    try:
        return get_chat_service().chat_once(user_text=prompt, session_id=f"wakeup_{target_key}")
    except Exception:
        print("[RoleWeaver LINE] Wake-up text generation failed:")
        traceback.print_exc()
        return os.getenv(
            "ROLEWEAVER_WAKEUP_FALLBACK_TEXT",
            "あら……プロデューサー。朝ですよ。少しだけ目を開けてください。私、ここにいますから。",
        )


def _wakeup_state_key(now: datetime) -> str:
    return now.strftime("%Y-%m-%d")


def _has_sent_wakeup(today_key: str) -> bool:
    state = _json_load(WAKEUP_STATE_PATH, {})
    return state.get("last_sent_date") == today_key


def _mark_wakeup_sent(today_key: str) -> None:
    _json_save(WAKEUP_STATE_PATH, {"last_sent_date": today_key, "sent_at": datetime.now().isoformat(timespec="seconds")})


async def send_wakeup_pushes():
    contacts = get_wakeup_contacts()
    if not contacts:
        print("[RoleWeaver LINE] Wake-up skipped: no subscribed contacts. Send /wake on in LINE first.")
        return
    voice_enabled = _truthy_env("ROLEWEAVER_WAKEUP_VOICE", default=False)
    for contact in contacts:
        target_key = contact["key"]
        to = contact["to"]
        text = await asyncio.to_thread(build_wakeup_text, target_key)
        if voice_enabled:
            try:
                audio = await asyncio.to_thread(synthesize_line_audio, text, target_key)
                if audio:
                    audio_url, duration_ms = audio
                    await asyncio.to_thread(push_audio, to, audio_url, duration_ms)
                    continue
            except Exception:
                print("[RoleWeaver LINE] Wake-up voice failed; falling back to text:")
                traceback.print_exc()
        await asyncio.to_thread(push_text, to, text)


def _next_wakeup_datetime(now: datetime) -> datetime:
    time_text = os.getenv("ROLEWEAVER_WAKEUP_TIME", "07:00")
    try:
        hour_text, minute_text = time_text.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError:
        hour, minute = 7, 0
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


async def wakeup_loop():
    timezone_name = os.getenv("ROLEWEAVER_WAKEUP_TIMEZONE", "Asia/Tokyo")
    tz = ZoneInfo(timezone_name)
    while True:
        now = datetime.now(tz)
        target = _next_wakeup_datetime(now)
        wait_seconds = max(1.0, (target - now).total_seconds())
        print(f"[RoleWeaver LINE] Next wake-up push at {target.isoformat(timespec='seconds')}")
        await asyncio.sleep(wait_seconds)
        today_key = _wakeup_state_key(datetime.now(tz))
        if _has_sent_wakeup(today_key):
            continue
        await send_wakeup_pushes()
        _mark_wakeup_sent(today_key)


@app.get("/")
async def root():
    return {
        "name": "RoleWeaver LINE Bot",
        "status": "ok",
        "callback": "/callback",
        "health": "/health",
    }


@app.get("/audio/{filename}")
async def audio_file(filename: str):
    candidate = _audio_output_dir() / filename
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(candidate)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    global _wakeup_task
    if _truthy_env("ROLEWEAVER_WAKEUP_ENABLED", default=False):
        _wakeup_task = asyncio.create_task(wakeup_loop())


@app.on_event("shutdown")
async def shutdown_event():
    if _wakeup_task:
        _wakeup_task.cancel()


@app.post("/")
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

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            remember_contact(event.source)
            session_id = build_session_id(event.source)
            user_text = event.message.text.strip()
            command_reply = handle_builtin_command(user_text, event.source)
            if command_reply is not None:
                send_reply(event.reply_token, command_reply)
                continue

            try:
                service = get_chat_service()
                reply_text = service.chat_once(
                    user_text=user_text,
                    session_id=session_id,
                    max_new_tokens=line_max_new_tokens(),
                )
            except Exception as exc:
                print("[RoleWeaver LINE] Chat handling failed:")
                traceback.print_exc()
                if _truthy_env("ROLEWEAVER_LINE_DEBUG_ERRORS", default=False):
                    reply_text = f"RoleWeaver error: {exc}"
                else:
                    reply_text = "RoleWeaver is temporarily unavailable. Please check the bot server logs."
            send_chat_reply(event.reply_token, reply_text, session_id, user_text)
        elif isinstance(event, MessageEvent) and isinstance(event.message, ImageMessageContent):
            remember_contact(event.source)
            session_id = build_session_id(event.source)
            user_text = _line_image_prompt()
            try:
                image_path = download_line_image(event.message.id, session_id)
                service = get_chat_service()
                reply_text = service.chat_once_with_image(
                    user_text=user_text,
                    image_path=str(image_path),
                    session_id=session_id,
                    max_new_tokens=line_max_new_tokens(),
                )
            except Exception as exc:
                print("[RoleWeaver LINE] Image chat handling failed:")
                traceback.print_exc()
                if _truthy_env("ROLEWEAVER_LINE_DEBUG_ERRORS", default=False):
                    reply_text = f"RoleWeaver image error: {exc}"
                else:
                    reply_text = "RoleWeaver cannot read this image yet. Please check the bot server logs."
            send_chat_reply(event.reply_token, reply_text, session_id, user_text)

    return JSONResponse({"status": "ok", "events": len(events)})
