import mimetypes
import time
from pathlib import Path
from urllib import parse

from .config import QQVoiceBotConfig
from .http_json import get_text, post_json


def _replace_endpoint(url: str, endpoint: str) -> str:
    parsed = parse.urlsplit(url)
    return parse.urlunsplit((parsed.scheme, parsed.netloc, endpoint, "", ""))


class LocalTTSClient:
    def __init__(self, config: QQVoiceBotConfig):
        self.config = config
        self._weights_ready = False

    def ensure_weights(self):
        if self._weights_ready:
            return
        if self.config.gpt_weights_path:
            url = _replace_endpoint(self.config.tts_url, "/set_gpt_weights")
            query = parse.urlencode({"weights_path": self.config.gpt_weights_path})
            get_text(f"{url}?{query}", timeout=self.config.tts_timeout_seconds)
        if self.config.sovits_weights_path:
            url = _replace_endpoint(self.config.tts_url, "/set_sovits_weights")
            query = parse.urlencode({"weights_path": self.config.sovits_weights_path})
            get_text(f"{url}?{query}", timeout=self.config.tts_timeout_seconds)
        self._weights_ready = True

    def synthesize_to_file(self, text: str, session_id: str) -> Path:
        self.ensure_weights()
        output_dir = Path(self.config.audio_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "text": text,
            "text_lang": self.config.text_lang,
            "ref_audio_path": self.config.ref_audio_path,
            "prompt_text": self.config.prompt_text,
            "prompt_lang": self.config.prompt_lang,
            "media_type": self.config.tts_media_type,
            "text_split_method": self.config.tts_text_split_method,
            "speed_factor": self.config.tts_speed_factor,
            "streaming_mode": False,
        }
        audio_bytes = post_json(self.config.tts_url, payload, timeout=self.config.tts_timeout_seconds)
        if not isinstance(audio_bytes, bytes):
            raise RuntimeError(f"TTS API returned JSON instead of audio: {audio_bytes}")

        ext = self.config.tts_media_type.lower().lstrip(".") or "wav"
        path = output_dir / f"{int(time.time() * 1000)}_{session_id}.{ext}"
        path.write_bytes(audio_bytes)
        return path

    def public_url_for(self, path: Path) -> str:
        base = self.config.public_audio_base_url.rstrip("/")
        if not base:
            return ""
        return f"{base}/{path.name}"

    @staticmethod
    def content_type_for(path: Path) -> str:
        return mimetypes.guess_type(str(path))[0] or "application/octet-stream"
