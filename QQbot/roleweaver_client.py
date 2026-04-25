from .config import QQVoiceBotConfig
from .http_json import post_json


class RoleWeaverTextClient:
    def __init__(self, config: QQVoiceBotConfig):
        self.config = config

    def chat(self, session_id: str, user_text: str) -> str:
        payload = {
            "session_id": session_id,
            "user_text": user_text,
            "max_new_tokens": self.config.max_new_tokens,
        }
        data = post_json(
            self.config.roleweaver_chat_url,
            payload,
            timeout=self.config.roleweaver_timeout_seconds,
        )
        if isinstance(data, bytes):
            return data.decode("utf-8").strip()
        for key in ("text", "reply", "assistant_text", "content"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        raise RuntimeError(f"RoleWeaver chat response did not include text: {data}")
