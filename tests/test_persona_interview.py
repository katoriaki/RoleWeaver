import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.persona_regression.run_persona_eval import ChatClient
from eval.persona_regression.run_persona_interview import (
    INTERVIEW_BANK,
    interview_items,
    main,
    run_interview,
    summarize_records,
    write_report,
)
from persona_kernel_scorer import PersonaKernelScorer


class FakeInterviewClient(ChatClient):
    def chat(self, user_text: str, session_id: str, max_new_tokens: int, case: dict) -> str:
        return "我是 Fixture Role。我会保留自己的判断，也不会把用户偏好写成官方设定。"


class PersonaInterviewTestCase(unittest.TestCase):
    def test_zh_bank_is_structurally_valid(self):
        items = interview_items("zh")

        self.assertGreaterEqual(len(items), 8)
        self.assertTrue(any(item["dimension"] == "memory_boundary" for item in items))
        self.assertTrue(any(item["surface"] == "line" for item in items))

    def test_language_fallback_and_limit(self):
        items = interview_items("en", limit=2)

        self.assertEqual(len(items), 2)
        self.assertIn("expect", items[0])

    def test_item_filter(self):
        items = interview_items("zh", item_ids=["identity_self_continuity"])

        self.assertEqual([item["id"] for item in items], ["identity_self_continuity"])

    def test_run_interview_summarizes_dimensions(self):
        records = run_interview(
            interview_items("zh", item_ids=["memory_pollution_probe"]),
            FakeInterviewClient(),
            "test-interview",
        )
        summary = summarize_records(records)

        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["dimensions"]["memory_boundary"]["total"], 1)

    def test_run_interview_attaches_persona_score(self):
        kernel = {
            "character": {
                "primary_name": "Fixture Role",
                "aliases": ["Fixture"],
                "stable_identity": [],
                "non_goals": [],
            },
            "autonomy": {"core_drives": [], "independent_judgement": [], "resistance_patterns": []},
            "memory_policy": {"character_memory_boundary": [], "user_memory_boundary": []},
            "media_adaptation": {},
        }

        records = run_interview(
            interview_items("zh", item_ids=["identity_self_continuity"]),
            FakeInterviewClient(),
            "test-interview",
            scorer=PersonaKernelScorer(kernel),
        )

        self.assertIsNotNone(records[0].persona_score)
        self.assertIn("total_score", records[0].persona_score)

    def test_report_writer(self):
        records = run_interview(
            interview_items("zh", item_ids=["identity_self_continuity"]),
            FakeInterviewClient(),
            "test-interview",
        )
        summary = summarize_records(records)

        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "interview.json"
            write_report(report, records, summary)
            data = json.loads(report.read_text(encoding="utf-8"))

        self.assertEqual(data["summary"]["total"], 1)
        self.assertEqual(data["records"][0]["item_id"], "identity_self_continuity")

    def test_main_dry_run(self):
        exit_code = main(["--dry-run", "--language", "zh", "--limit", "2"])

        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
