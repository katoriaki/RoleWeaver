import argparse
import asyncio
import logging
import re
from typing import Optional

from .config import QQVoiceBotConfig
from .pipeline import VoiceReplyPipeline
from .ssh_tunnel import SSHTunnel


LOG = logging.getLogger("QQVoiceBot")


def clean_qq_text(text: str) -> str:
    text = re.sub(r"<@!?[0-9A-Za-z_-]+>", "", text or "")
    return text.strip()


def _author_openid(message) -> Optional[str]:
    author = getattr(message, "author", None)
    for name in ("user_openid", "openid", "id"):
        value = getattr(author, name, None)
        if value:
            return value
    for name in ("user_openid", "openid"):
        value = getattr(message, name, None)
        if value:
            return value
    return None


class QQVoiceBot:
    def __init__(self, config: QQVoiceBotConfig):
        self.config = config
        self.pipeline = VoiceReplyPipeline(config)

    async def handle_group_message(self, message):
        user_text = clean_qq_text(getattr(message, "content", ""))
        if not user_text:
            return
        group_openid = getattr(message, "group_openid", "")
        session_id = f"qq_group_{group_openid}"
        await self._handle_message(message, session_id, user_text, scene="group")

    async def handle_c2c_message(self, message):
        user_text = clean_qq_text(getattr(message, "content", ""))
        if not user_text:
            return
        openid = _author_openid(message) or "unknown"
        session_id = f"qq_c2c_{openid}"
        await self._handle_message(message, session_id, user_text, scene="c2c")

    async def _handle_message(self, message, session_id: str, user_text: str, scene: str):
        LOG.info("message scene=%s session=%s text=%s", scene, session_id, user_text)
        try:
            reply = await asyncio.to_thread(self.pipeline.build_reply, session_id, user_text)
            if self.config.send_text_preview:
                await self._send_text(message, scene, reply.text)
            if not reply.audio_url:
                raise RuntimeError(
                    "public_audio_base_url is empty; QQ media upload needs a URL that QQ can fetch."
                )
            await self._send_voice(message, scene, reply.audio_url)
        except Exception as exc:
            LOG.exception("failed to build/send voice reply")
            if self.config.fallback_to_text:
                await self._send_text(message, scene, f"语音生成失败，先回文字：{exc}")

    async def _send_text(self, message, scene: str, content: str):
        api = getattr(message, "_api", None)
        if api is None:
            raise RuntimeError("botpy message does not expose _api")
        if scene == "group":
            try:
                await api.post_group_message(
                    group_openid=message.group_openid,
                    msg_type=0,
                    content=content,
                    msg_id=message.id,
                )
            except TypeError:
                await message.reply(content=content)
            return

        openid = _author_openid(message)
        if not openid:
            raise RuntimeError("cannot find c2c user openid")
        try:
            await api.post_c2c_message(
                openid=openid,
                msg_type=0,
                content=content,
                msg_id=message.id,
            )
        except TypeError:
            await message.reply(content=content)

    async def _send_voice(self, message, scene: str, audio_url: str):
        api = getattr(message, "_api", None)
        if api is None:
            raise RuntimeError("botpy message does not expose _api")
        if scene == "group":
            media = await api.post_group_file(
                group_openid=message.group_openid,
                file_type=self.config.qq_voice_file_type,
                url=audio_url,
                srv_send_msg=False,
            )
            try:
                await api.post_group_message(
                    group_openid=message.group_openid,
                    msg_type=7,
                    msg_id=message.id,
                    media=media,
                )
            except TypeError:
                await api.post_group_message(
                    group_openid=message.group_openid,
                    msg_type=7,
                    msg_id=message.id,
                    media=media,
                    content="",
                )
            return

        openid = _author_openid(message)
        if not openid:
            raise RuntimeError("cannot find c2c user openid")
        media = await api.post_c2c_file(
            openid=openid,
            file_type=self.config.qq_voice_file_type,
            url=audio_url,
            srv_send_msg=False,
        )
        try:
            await api.post_c2c_message(
                openid=openid,
                msg_type=7,
                msg_id=message.id,
                media=media,
            )
        except TypeError:
            await api.post_c2c_message(
                openid=openid,
                msg_type=7,
                msg_id=message.id,
                media=media,
                content="",
            )


def build_botpy_client(config: QQVoiceBotConfig):
    try:
        import botpy
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing dependency: install qq-botpy to run QQbot.") from exc

    voice_bot = QQVoiceBot(config)

    class Client(botpy.Client):
        async def on_ready(self):
            LOG.info("QQ bot is ready: %s", self.robot)

        async def on_group_at_message_create(self, message):
            if config.enable_group_at:
                await voice_bot.handle_group_message(message)

        async def on_c2c_message_create(self, message):
            if config.enable_c2c:
                await voice_bot.handle_c2c_message(message)

    intents = botpy.Intents.none()
    intents.public_messages = True
    return Client(intents=intents)


def main():
    parser = argparse.ArgumentParser(description="RoleWeaver QQ voice bot")
    parser.add_argument("--config", default=None, help="Path to qq_voice_bot.config.csv")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = QQVoiceBotConfig.load(args.config)
    config.validate()
    with SSHTunnel(config):
        client = build_botpy_client(config)
        client.run(appid=config.qq_app_id, secret=config.qq_app_secret)


if __name__ == "__main__":
    main()
