import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from linebot.v3.webhooks import GroupSource, UserSource

from line import app as line_bot_app
from misuzu_chat_service import (
    DEFAULT_IDLE_CONSOLIDATION_SECONDS,
    normalize_idle_consolidation_seconds,
)


class LineBotAppTestCase(unittest.TestCase):
    def test_split_reply_text_chunks_long_message(self):
        text = "a" * 9001
        chunks = line_bot_app.split_reply_text(text, chunk_size=4500)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[0]), 4500)
        self.assertEqual(len(chunks[1]), 4500)
        self.assertEqual(len(chunks[2]), 1)

    def test_build_session_id_from_line_source(self):
        user_source = UserSource(user_id="u123")
        group_source = GroupSource(group_id="g456", user_id="u789")

        self.assertEqual(line_bot_app.build_session_id(user_source), "line_user_u123")
        self.assertEqual(line_bot_app.build_session_id(group_source), "line_group_g456_u789")

    def test_health_and_missing_signature(self):
        client = TestClient(line_bot_app.app)

        health = client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")

        callback = client.post("/callback", content="{}")
        self.assertEqual(callback.status_code, 400)
        self.assertIn("Missing X-Line-Signature", callback.text)

    def test_idle_consolidation_seconds_is_configurable(self):
        self.assertEqual(normalize_idle_consolidation_seconds("0"), 0)
        self.assertEqual(normalize_idle_consolidation_seconds("-5"), 0)
        self.assertEqual(
            normalize_idle_consolidation_seconds("bad", default=123),
            123,
        )

        line_bot_app.get_chat_service.cache_clear()
        with patch.dict("os.environ", {"MISUZU_IDLE_CONSOLIDATION_SECONDS": "42"}, clear=False):
            service = line_bot_app.get_chat_service()
            self.assertEqual(service.idle_consolidation_seconds, 42)
        line_bot_app.get_chat_service.cache_clear()
        default_service = line_bot_app.get_chat_service()
        self.assertEqual(default_service.idle_consolidation_seconds, DEFAULT_IDLE_CONSOLIDATION_SECONDS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
