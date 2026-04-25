import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


QQBOT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = QQBOT_ROOT.parent
DEFAULT_CONFIG_PATH = QQBOT_ROOT / "qq_voice_bot.config.csv"


def _clean(value):
    if value is None:
        return None
    value = str(value).strip().strip('"').strip("'")
    return value or None


def _bool(value, default: bool = False) -> bool:
    value = _clean(value)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "y", "on", "开启", "是"}


def _int(value, default: int) -> int:
    value = _clean(value)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _float(value, default: float) -> float:
    value = _clean(value)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _read_csv(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return values

    header = [cell.strip().lower() for cell in rows[0]]
    if "key" in header and "value" in header:
        start = 1
        key_index = header.index("key")
        value_index = header.index("value")
    else:
        start = 0
        key_index = 0
        value_index = 1

    for row in rows[start:]:
        if len(row) <= max(key_index, value_index):
            continue
        key = row[key_index].strip()
        if not key or key.startswith("#"):
            continue
        value = _clean(row[value_index])
        if value is not None:
            values[key] = value
    return values


@dataclass
class QQVoiceBotConfig:
    qq_app_id: str
    qq_app_secret: str
    qq_sandbox: bool
    enable_group_at: bool
    enable_c2c: bool

    roleweaver_chat_url: str
    roleweaver_timeout_seconds: float
    max_new_tokens: int

    ssh_enable: bool
    ssh_user: str
    ssh_host: str
    ssh_port: int
    ssh_identity_file: Optional[str]
    ssh_local_port: int
    ssh_remote_host: str
    ssh_remote_port: int
    ssh_extra_args: str

    tts_url: str
    tts_timeout_seconds: float
    gpt_weights_path: Optional[str]
    sovits_weights_path: Optional[str]
    ref_audio_path: str
    prompt_text: str
    prompt_lang: str
    text_lang: str
    tts_media_type: str
    tts_text_split_method: str
    tts_speed_factor: float

    audio_output_dir: str
    public_audio_base_url: str
    silk_converter_command: Optional[str]
    qq_voice_file_type: int

    send_text_preview: bool
    fallback_to_text: bool
    worker_queue_size: int

    @classmethod
    def load(cls, path: Optional[str] = None) -> "QQVoiceBotConfig":
        config_path = Path(path).expanduser() if path else DEFAULT_CONFIG_PATH
        if not config_path.exists():
            raise FileNotFoundError(f"QQ bot config not found: {config_path}")
        data = _read_csv(config_path)

        def get(key: str, default=None):
            return _clean(data.get(key)) if key in data else default

        return cls(
            qq_app_id=get("qq_app_id", ""),
            qq_app_secret=get("qq_app_secret", ""),
            qq_sandbox=_bool(get("qq_sandbox"), False),
            enable_group_at=_bool(get("enable_group_at"), True),
            enable_c2c=_bool(get("enable_c2c"), True),
            roleweaver_chat_url=get("roleweaver_chat_url", "http://127.0.0.1:18000/chat"),
            roleweaver_timeout_seconds=_float(get("roleweaver_timeout_seconds"), 120.0),
            max_new_tokens=_int(get("max_new_tokens"), 120),
            ssh_enable=_bool(get("ssh_enable"), True),
            ssh_user=get("ssh_user", ""),
            ssh_host=get("ssh_host", ""),
            ssh_port=_int(get("ssh_port"), 22),
            ssh_identity_file=get("ssh_identity_file"),
            ssh_local_port=_int(get("ssh_local_port"), 18000),
            ssh_remote_host=get("ssh_remote_host", "127.0.0.1"),
            ssh_remote_port=_int(get("ssh_remote_port"), 8000),
            ssh_extra_args=get("ssh_extra_args", ""),
            tts_url=get("tts_url", "http://127.0.0.1:9880/tts"),
            tts_timeout_seconds=_float(get("tts_timeout_seconds"), 180.0),
            gpt_weights_path=get("gpt_weights_path"),
            sovits_weights_path=get("sovits_weights_path"),
            ref_audio_path=get("ref_audio_path", ""),
            prompt_text=get("prompt_text", ""),
            prompt_lang=get("prompt_lang", "zh"),
            text_lang=get("text_lang", "zh"),
            tts_media_type=get("tts_media_type", "wav"),
            tts_text_split_method=get("tts_text_split_method", "cut5"),
            tts_speed_factor=_float(get("tts_speed_factor"), 1.0),
            audio_output_dir=get("audio_output_dir", str(PROJECT_ROOT / "data" / "qqbot_audio")),
            public_audio_base_url=get("public_audio_base_url", ""),
            silk_converter_command=get("silk_converter_command"),
            qq_voice_file_type=_int(get("qq_voice_file_type"), 3),
            send_text_preview=_bool(get("send_text_preview"), False),
            fallback_to_text=_bool(get("fallback_to_text"), True),
            worker_queue_size=_int(get("worker_queue_size"), 1),
        )

    def validate(self):
        missing = []
        for key in ("qq_app_id", "qq_app_secret", "roleweaver_chat_url", "tts_url"):
            if not getattr(self, key):
                missing.append(key)
        if self.ssh_enable:
            for key in ("ssh_user", "ssh_host"):
                if not getattr(self, key):
                    missing.append(key)
        for key in ("ref_audio_path", "prompt_text"):
            if not getattr(self, key):
                missing.append(key)
        if missing:
            raise ValueError("Missing required QQ bot config values: " + ", ".join(missing))
