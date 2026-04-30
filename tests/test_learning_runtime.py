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

            observed = []
            runtime = LearningRuntime(root / "learning", textbook_root=textbook, session_id="shiro-study", subject="数学")
            step = runtime.run_step(
                observe_shiro=lambda text, source, metadata: observed.append((text, source, metadata)) or {"available": True},
            )

            self.assertEqual(step.mode, "dry_run")
            self.assertIn("学习笔记", step.output)
            self.assertTrue(observed)
            self.assertTrue(runtime.adapter_candidate_path.exists())
            row = json.loads(runtime.adapter_candidate_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["metadata"]["source"], "shiro_long_term_study")

    def test_run_web_learning_step_uses_search_results(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            textbook = root / "ChinaTextbook"
            textbook.mkdir()
            runtime = LearningRuntime(root / "learning", textbook_root=textbook, session_id="shiro-study")
            observed = []

            step = runtime.run_web_step(
                search_fn=lambda query, limit: {
                    "query": query,
                    "results": [{"title": "Discrete mathematics basics", "url": "https://example.test/math"}],
                    "error": "",
                },
                observe_shiro=lambda text, source, metadata: observed.append((text, source, metadata)) or {"available": True},
                subjects=["mathematics", "computer science"],
            )

            self.assertTrue(step.mode.startswith("web_search_dry_run"))
            self.assertIn("professional_study", step.mode)
            self.assertEqual(step.material["kind"], "web_search")
            self.assertIn("Discrete mathematics basics", step.output)
            self.assertTrue(observed)
            self.assertEqual(observed[0][1], "autonomous_study")
            self.assertEqual(runtime.status()["completed_web_steps"], 1)
            self.assertEqual(runtime.status()["autonomous_cycle"]["activity"], "professional_study")
            self.assertTrue((root / "learning" / "shiro-study" / "continual_learning" / "growth_queue.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
