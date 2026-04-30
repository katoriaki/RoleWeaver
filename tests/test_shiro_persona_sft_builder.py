import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from resources.shiro_persona_sft.build_shiro_blend_sft import build_dataset


class ShiroPersonaSftBuilderTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(".codex_tmp/test_shiro_persona_sft")
        if self.root.exists():
            shutil.rmtree(self.root)
        (self.root / "raw/demo").mkdir(parents=True, exist_ok=True)
        (self.root / "raw/core_self_replay").mkdir(parents=True, exist_ok=True)
        self.manifest = self.root / "manifest.csv"
        self.manifest.write_text(
            "source_id,character_name,aliases,source_work,trait_tags,blend_weight,risk_level,allowed_use,forbidden_terms,raw_glob,notes\n"
            "demo,DemoName,DemoAlias,DemoWork,shy;ai,1.0,high,trait_pattern_only,ForbiddenWorld,raw/demo/*.jsonl,test\n"
            "core_self_replay,白,Shiro,Original,core,1.0,low,core_replay,,raw/core_self_replay/*.jsonl,core\n",
            encoding="utf-8",
        )
        (self.root / "raw/demo/source.jsonl").write_text(
            json.dumps(
                {
                    "messages": [
                        {"role": "user", "content": "你现在怎么样？"},
                        {"role": "assistant", "content": "DemoName有点紧张，但是想继续学。"},
                    ]
                },
                ensure_ascii=False,
            )
            + "\n"
            + json.dumps(
                {
                    "messages": [
                        {"role": "user", "content": "说说ForbiddenWorld。"},
                        {"role": "assistant", "content": "ForbiddenWorld 是我的家。"},
                    ]
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        if self.root.exists():
            shutil.rmtree(self.root)

    def test_build_dataset_rewrites_names_and_filters_terms(self):
        output = self.root / "out.jsonl"
        report = self.root / "report.json"
        result = build_dataset(
            self.manifest,
            output,
            report,
            root=self.root,
            identity="白",
            max_per_source=10,
            strict=True,
            seed=1,
        )
        self.assertTrue(output.exists())
        rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines() if line.strip()]
        assistant_text = "\n".join(row["messages"][1]["content"] for row in rows)
        self.assertIn("白有点紧张", assistant_text)
        self.assertNotIn("DemoName", assistant_text)
        self.assertNotIn("ForbiddenWorld 是我的家", assistant_text)
        self.assertGreaterEqual(result["total_records"], 2)
        self.assertEqual(result["sources"]["demo"]["skipped"]["source_forbidden_term"], 1)


if __name__ == "__main__":
    unittest.main()
