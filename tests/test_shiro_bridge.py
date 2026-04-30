import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from shiro_bridge import ShiroBridge


class ShiroBridgeTestCase(unittest.TestCase):
    def test_disabled_bridge_is_noop(self):
        with TemporaryDirectory() as temp_dir:
            bridge = ShiroBridge(enabled=False, root=temp_dir, identity="白")

            self.assertFalse(bridge.available)
            self.assertEqual(bridge.thought_context("s1"), "")
            self.assertFalse(bridge.observe_text("s1", "hello")["available"])

    def test_enabled_bridge_writes_session_scoped_state(self):
        with TemporaryDirectory() as temp_dir:
            bridge = ShiroBridge(enabled=True, root=temp_dir, identity="白")
            result = bridge.observe_text("session-a", "谢谢你，今天陪我一下。")

            self.assertTrue(result["available"])
            state_path = Path(temp_dir) / "sessions" / "session-a" / "cognitive_state.json"
            self.assertTrue(state_path.exists())
            data = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(data["identity"], "白")
            self.assertIn("白的认知状态", bridge.thought_context("session-a"))

    def test_chat_turn_updates_transition_log(self):
        with TemporaryDirectory() as temp_dir:
            bridge = ShiroBridge(enabled=True, root=temp_dir, identity="白")
            bridge.observe_chat_turn("session-a", "帮我计划一下", "我们先列清单。")
            status = bridge.status("session-a")

            self.assertTrue(status["available"])
            self.assertEqual(status["scope"], "session")
            self.assertEqual(len(status["recent_transitions"]), 1)

    def test_infer_tool_intentions(self):
        with TemporaryDirectory() as temp_dir:
            bridge = ShiroBridge(enabled=True, root=temp_dir, identity="白")
            result = bridge.infer_tool_intentions("session-a", r"帮我读 C:\docs\a.pdf，再上网搜解法")

            self.assertTrue(result["available"])
            names = {item["tool_name"] for item in result["intentions"]}
            self.assertIn("document.pdf_read", names)
            self.assertIn("planning.web_search", names)


if __name__ == "__main__":
    unittest.main()
