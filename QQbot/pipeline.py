from dataclasses import dataclass
from pathlib import Path

from .audio_convert import convert_to_silk_if_configured
from .config import QQVoiceBotConfig
from .roleweaver_client import RoleWeaverTextClient
from .tts_client import LocalTTSClient


@dataclass
class VoiceReply:
    text: str
    audio_path: Path
    audio_url: str


class VoiceReplyPipeline:
    def __init__(self, config: QQVoiceBotConfig):
        self.config = config
        self.roleweaver = RoleWeaverTextClient(config)
        self.tts = LocalTTSClient(config)

    def build_reply(self, session_id: str, user_text: str) -> VoiceReply:
        assistant_text = self.roleweaver.chat(session_id=session_id, user_text=user_text)
        audio_path = self.tts.synthesize_to_file(assistant_text, session_id=session_id)
        audio_path = convert_to_silk_if_configured(audio_path, self.config.silk_converter_command)
        audio_url = self.tts.public_url_for(audio_path)
        return VoiceReply(text=assistant_text, audio_path=audio_path, audio_url=audio_url)
