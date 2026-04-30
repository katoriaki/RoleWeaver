import unittest
import sys
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from linebot.v3.webhooks import GroupSource, ImageMessageContent, MessageEvent, UserSource

from line import app as line_bot_app
from role_config import (
    DEFAULT_IDLE_CONSOLIDATION_SECONDS,
    normalize_idle_consolidation_seconds,
)


class LineBotAppTestCase(unittest.TestCase):
    def tearDown(self):
        line_bot_app.load_surface_policy.cache_clear()

    def test_split_reply_text_chunks_long_message(self):
        text = "a" * 9001
        chunks = line_bot_app.split_reply_text(text, chunk_size=4500)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[0]), 4500)
        self.assertEqual(len(chunks[1]), 4500)
        self.assertEqual(len(chunks[2]), 1)

    def test_split_reply_text_falls_back_for_empty_reply(self):
        self.assertEqual(line_bot_app.split_reply_text(""), ["..."])

    def test_build_session_id_from_line_source(self):
        user_source = UserSource(user_id="u123")
        group_source = GroupSource(group_id="g456", user_id="u789")

        self.assertEqual(line_bot_app.build_session_id(user_source), "line_user_u123")
        self.assertEqual(line_bot_app.build_session_id(group_source), "line_group_g456_u789")

    def test_builtin_commands_do_not_require_line_credentials(self):
        self.assertEqual(line_bot_app.handle_builtin_command("/ping"), "pong")
        self.assertIn("RoleWeaver LINE Bot is online", line_bot_app.handle_builtin_command("/help"))
        self.assertIsNone(line_bot_app.handle_builtin_command("hello"))

    def test_voice_reply_policy_respects_daytime_text_window(self):
        env = {
            "ROLEWEAVER_REPLY_VOICE": "1",
            "ROLEWEAVER_VOICE_TEXT_ONLY_WINDOW_ENABLED": "1",
            "ROLEWEAVER_VOICE_TEXT_ONLY_START": "08:00",
            "ROLEWEAVER_VOICE_TEXT_ONLY_END": "17:30",
            "ROLEWEAVER_VOICE_TEXT_ONLY_TIMEZONE": "Asia/Tokyo",
        }
        morning = datetime(2026, 4, 28, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        evening = datetime(2026, 4, 28, 18, 0, tzinfo=ZoneInfo("Asia/Tokyo"))

        with patch.dict("os.environ", env, clear=False):
            self.assertFalse(line_bot_app.should_use_voice_reply("おはよう", now=morning))
            self.assertTrue(line_bot_app.should_use_voice_reply("この返事を音声でお願いします", now=morning))
            self.assertTrue(line_bot_app.should_use_voice_reply("hello", now=evening))
            self.assertFalse(line_bot_app.should_use_voice_reply("no voice, text only", now=evening))

    def test_surface_policy_file_controls_line_voice_and_tokens(self):
        policy = {
            "line": {
                "max_new_tokens": 256,
                "reply_chunk_size": 1000,
                "voice": {
                    "reply_voice": True,
                    "text_only_window_enabled": True,
                    "text_only_start": "09:00",
                    "text_only_end": "10:00",
                    "timezone": "Asia/Tokyo",
                    "allow_voice_on_request": True,
                    "request_markers": ["please sing"],
                    "reject_markers": ["silent mode"],
                },
                "wake_up": {
                    "time": "06:30",
                    "timezone": "Asia/Tokyo",
                },
            }
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = Path(temp_dir) / "surface_policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            env = {
                "ROLEWEAVER_SURFACE_POLICY_FILE": str(policy_path),
            }
            morning = datetime(2026, 4, 28, 9, 30, tzinfo=ZoneInfo("Asia/Tokyo"))
            evening = datetime(2026, 4, 28, 18, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
            with patch.dict("os.environ", env, clear=True):
                line_bot_app.load_surface_policy.cache_clear()
                self.assertEqual(line_bot_app.line_max_new_tokens(), 256)
                self.assertFalse(line_bot_app.should_use_voice_reply("hello", now=morning))
                self.assertTrue(line_bot_app.should_use_voice_reply("please sing", now=morning))
                self.assertFalse(line_bot_app.should_use_voice_reply("silent mode", now=evening))
                self.assertTrue(line_bot_app.should_use_voice_reply("hello", now=evening))
                next_wakeup = line_bot_app._next_wakeup_datetime(
                    datetime(2026, 4, 28, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
                )
                self.assertEqual((next_wakeup.hour, next_wakeup.minute), (6, 30))

    def test_surface_policy_env_overrides_file(self):
        policy = {"line": {"max_new_tokens": 256, "voice": {"reply_voice": False}}}
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = Path(temp_dir) / "surface_policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            env = {
                "ROLEWEAVER_SURFACE_POLICY_FILE": str(policy_path),
                "ROLEWEAVER_LINE_MAX_NEW_TOKENS": "384",
                "ROLEWEAVER_REPLY_VOICE": "1",
            }
            with patch.dict("os.environ", env, clear=True):
                line_bot_app.load_surface_policy.cache_clear()
                self.assertEqual(line_bot_app.line_max_new_tokens(), 384)
                self.assertTrue(line_bot_app.should_use_voice_reply("hello"))

    def test_health_and_missing_signature(self):
        client = TestClient(line_bot_app.app)

        health = client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")

        callback = client.post("/callback", content="{}")
        self.assertEqual(callback.status_code, 400)
        self.assertIn("Missing X-Line-Signature", callback.text)

    def test_callback_routes_image_messages_to_vision_chat(self):
        client = TestClient(line_bot_app.app)
        event = MessageEvent(
            source=UserSource(userId="u123"),
            timestamp=0,
            mode="active",
            webhookEventId="webhook-1",
            deliveryContext={"isRedelivery": False},
            replyToken="reply-token",
            message=ImageMessageContent(
                id="message-image-1",
                contentProvider={"type": "line"},
                quoteToken="quote-token",
            ),
        )
        parser = MagicMock()
        parser.parse.return_value = [event]
        service = MagicMock()
        service.chat_once_with_image.return_value = "image reply"

        with patch.object(line_bot_app, "get_line_parser", return_value=parser), \
            patch.object(line_bot_app, "remember_contact"), \
            patch.object(line_bot_app, "download_line_image", return_value=Path("image.jpg")) as download_image, \
            patch.object(line_bot_app, "get_chat_service", return_value=service), \
            patch.object(line_bot_app, "send_chat_reply") as send_chat_reply:
            response = client.post("/callback", content="{}", headers={"X-Line-Signature": "sig"})

        self.assertEqual(response.status_code, 200)
        download_image.assert_called_once_with("message-image-1", "line_user_u123")
        service.chat_once_with_image.assert_called_once()
        kwargs = service.chat_once_with_image.call_args.kwargs
        self.assertEqual(kwargs["image_path"], "image.jpg")
        self.assertEqual(kwargs["session_id"], "line_user_u123")
        self.assertEqual(kwargs["max_new_tokens"], 192)
        send_chat_reply.assert_called_once_with("reply-token", "image reply", "line_user_u123", kwargs["user_text"])

    def test_line_max_new_tokens_is_configurable_and_clamped(self):
        with patch.dict("os.environ", {"ROLEWEAVER_LINE_MAX_NEW_TOKENS": "384"}, clear=False):
            self.assertEqual(line_bot_app.line_max_new_tokens(), 384)
        with patch.dict("os.environ", {"ROLEWEAVER_LINE_MAX_NEW_TOKENS": "99999"}, clear=False):
            self.assertEqual(line_bot_app.line_max_new_tokens(), 4096)
        with patch.dict("os.environ", {"ROLEWEAVER_LINE_MAX_NEW_TOKENS": "1"}, clear=False):
            self.assertEqual(line_bot_app.line_max_new_tokens(), 16)
        with patch.dict("os.environ", {"ROLEWEAVER_LINE_MAX_NEW_TOKENS": "bad"}, clear=False):
            self.assertEqual(line_bot_app.line_max_new_tokens(), 192)

    def test_idle_consolidation_seconds_is_configurable(self):
        self.assertEqual(normalize_idle_consolidation_seconds("0"), 0)
        self.assertEqual(normalize_idle_consolidation_seconds("-5"), 0)
        self.assertEqual(
            normalize_idle_consolidation_seconds("bad", default=123),
            123,
        )

        line_bot_app.get_chat_service.cache_clear()
        with patch.dict("os.environ", {"ROLEWEAVER_IDLE_CONSOLIDATION_SECONDS": "42"}, clear=False):
            service = line_bot_app.get_chat_service()
            self.assertEqual(service.idle_consolidation_seconds, 42)
        line_bot_app.get_chat_service.cache_clear()
        default_service = line_bot_app.get_chat_service()
        self.assertEqual(default_service.idle_consolidation_seconds, DEFAULT_IDLE_CONSOLIDATION_SECONDS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
