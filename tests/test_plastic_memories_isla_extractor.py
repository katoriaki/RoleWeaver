import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from resources.shiro_persona_sft.extract_plastic_memories_isla import build_dataset


class PlasticMemoriesIslaExtractorTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(".codex_tmp/test_plastic_memories_isla")
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True)
        sample = {
            "scenes": [
                {
                    "texts": [
                        ["水柿司", None, "你在想什么？"],
                        ["艾拉", None, "我也不知道。只是有点在意。", [{"name": "アイラ"}]],
                        ["水柿司", None, "艾拉，你没事吧？"],
                        ["艾拉", None, "终端服务的工作还没有结束。", [{"name": "アイラ"}]],
                    ]
                }
            ]
        }
        (self.root / "sample.scn.m.json").write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        if self.root.exists():
            shutil.rmtree(self.root)

    def test_extracts_target_rows_and_skips_source_facts(self):
        output = self.root / "out.jsonl"
        report = self.root / "report.json"
        result = build_dataset(
            self.root,
            output,
            report,
            identity="白",
            context_turns=2,
            max_records=100,
            keep_fact_rows=False,
        )
        rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(result["records"], 1)
        self.assertEqual(len(rows), 1)
        self.assertIn("有点在意", rows[0]["messages"][1]["content"])
        self.assertNotIn("艾拉", rows[0]["messages"][0]["content"])
        self.assertEqual(result["skipped"]["source_fact"], 1)


if __name__ == "__main__":
    unittest.main()
