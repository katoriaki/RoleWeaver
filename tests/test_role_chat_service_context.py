import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import memory_runtime
from role_chat_service import RoleChatService
from role_config import RoleConfig, PROJECT_ROOT


class FakeBudgetTokenizer:
    model_max_length = 128

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True, **kwargs):
        rendered = []
        for message in messages:
            rendered.append(f"{message['role']}: {message['content']}")
        if add_generation_prompt:
            rendered.append("assistant:")
        return "\n".join(rendered)

    def __call__(self, text, add_special_tokens=False, **kwargs):
        return {"input_ids": text.split()}


class RoleChatServiceContextBudgetTestCase(unittest.TestCase):
    def setUp(self):
        tmp_root = PROJECT_ROOT / ".tmp_tests"
        tmp_root.mkdir(exist_ok=True)
        self.temp_dir = tempfile.TemporaryDirectory(dir=tmp_root)
        self.addCleanup(self.temp_dir.cleanup)

        self.encoder_patcher = patch.object(
            memory_runtime.HybridMemoryStore,
            "_try_init_encoder",
            lambda store: None,
        )
        self.encoder_patcher.start()
        self.addCleanup(self.encoder_patcher.stop)

    def test_prepare_messages_compresses_history_when_context_is_near_limit(self):
        base = Path(self.temp_dir.name)
        config = RoleConfig(
            base_model_path="fake-base",
            lora_path="",
            session_root=str(base / "memory"),
            skill_text=" ".join(["skill"] * 8),
            context_window_tokens=128,
        )
        service = RoleChatService(config=config)
        service._tokenizer = FakeBudgetTokenizer()
        service._model = type("FakeModel", (), {"config": type("FakeConfig", (), {})()})()

        runtime = memory_runtime.MemoryRuntime(
            memory_file=str(base / "memories.json"),
            index_file=str(base / "memories.faiss"),
            profile_file=str(base / "profile.json"),
            state_file=str(base / "state.json"),
            knowledge_file=str(base / "kg.json"),
            assistant_label="美铃",
        )
        for i in range(5):
            runtime.record_turn(
                " ".join([f"user{i}"] * 12),
                " ".join([f"assistant{i}"] * 12),
            )

        messages = service._prepare_messages_with_context_budget(
            user_text=" ".join(["new"] * 8),
            role_mode=True,
            runtime=runtime,
            max_new_tokens=8,
        )

        self.assertLessEqual(len(runtime.recent_history(max_messages=None)), 2)
        summaries = runtime.state.list_summaries()
        self.assertGreaterEqual(len(summaries), 1)
        summary_memories = [
            item for item in runtime.episodic.list_memories(category="episodic")
            if "context_compression" in item.get("tags", [])
        ]
        self.assertGreaterEqual(len(summary_memories), 1)
        non_system_messages = [message for message in messages if message["role"] != "system"]
        self.assertLessEqual(len(non_system_messages), 3)


if __name__ == "__main__":
    unittest.main()
