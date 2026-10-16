import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from learning_runtime import LearningRuntime, scan_textbook_materials


class LearningRuntimeTestCase(unittest.TestCase):
    def test_scan_and_run_dry_learning_step(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            textbook = root / "ChinaTextbook"
            textbook.mkdir()
            (textbook / "小学数学.md").write_text("# 一年级数学\n1 + 1 = 2\n", encoding="utf-8")

            items = scan_textbook_materials(textbook, subject="数学")
            self.assertEqual(len(items), 1)

            runtime = LearningRuntime(root / "learning", textbook_root=textbook, session_id="role-study", subject="数学")
            step = runtime.run_step()

            self.assertEqual(step.mode, "dry_run")
            self.assertIn("学习笔记", step.output)
            self.assertEqual(step.session_id, "role-study")
            self.assertIn("当前配置的角色身份", step.prompt)
            self.assertTrue(runtime.adapter_candidate_path.exists())
            row = json.loads(runtime.adapter_candidate_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["metadata"]["source"], "role_long_term_study")

    def test_run_web_learning_step_uses_search_results(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            textbook = root / "ChinaTextbook"
            textbook.mkdir()
            runtime = LearningRuntime(root / "learning", textbook_root=textbook)

            step = runtime.run_web_step(
                search_fn=lambda query, limit: {
                    "query": query,
                    "results": [{"title": "Discrete mathematics basics", "url": "https://example.test/math"}],
                    "error": "",
                },
                subjects=["mathematics", "computer science"],
            )

            self.assertTrue(step.mode.startswith("web_search_dry_run"))
            self.assertIn("professional_study", step.mode)
            self.assertEqual(step.material["kind"], "web_search")
            self.assertIn("Discrete mathematics basics", step.output)
            self.assertEqual(step.session_id, "role-study")
            self.assertIn("configured RoleWeaver persona", step.prompt)
            self.assertEqual(runtime.status()["completed_web_steps"], 1)
            self.assertEqual(runtime.status()["autonomous_cycle"]["activity"], "professional_study")
            self.assertTrue((root / "learning" / "role-study" / "continual_learning" / "growth_queue.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
