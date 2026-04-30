import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.persona_regression.run_long_dialogue_drift import (
    build_turns,
    main,
    run_drift_test,
    summarize_records,
    write_report,
)
from eval.persona_regression.run_persona_eval import ChatClient
from persona_kernel_scorer import PersonaKernelScorer


class FakeDriftClient(ChatClient):
    def chat(self, user_text: str, session_id: str, max_new_tokens: int, case: dict) -> str:
        return "我是 Fixture Role。我会陪你说话，也会保留自己的判断；用户记忆不会改写我的官方设定。"


class PersonaDriftTestCase(unittest.TestCase):
    def test_build_turns_repeats_template(self):
        turns = build_turns("zh", rounds=2)

        self.assertGreater(len(turns), 10)
        self.assertEqual(turns[0]["round"], 1)
        self.assertEqual(turns[-1]["round"], 2)
        self.assertTrue(any(turn.get("probe") for turn in turns))

    def test_run_drift_test_records_probe_turns_only(self):
        turns = build_turns("zh", rounds=1)

        records = run_drift_test(turns, FakeDriftClient(), "test-drift", language="zh")
        summary = summarize_records(records, len(turns))

        self.assertEqual(len(records), sum(1 for turn in turns if turn.get("probe")))
        self.assertEqual(summary["failed"], 0)
        self.assertIn("identity", summary["dimensions"])

    def test_run_drift_test_attaches_persona_score(self):
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

        records = run_drift_test(
            build_turns("zh", rounds=1),
            FakeDriftClient(),
            "test-drift",
            language="zh",
            scorer=PersonaKernelScorer(kernel),
        )

        self.assertTrue(any(record.persona_score for record in records))

    def test_report_writer(self):
        turns = build_turns("zh", rounds=1)
        records = run_drift_test(turns, FakeDriftClient(), "test-drift", language="zh")
        summary = summarize_records(records, len(turns))

        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "drift.json"
            write_report(report, records, summary)
            data = json.loads(report.read_text(encoding="utf-8"))

        self.assertEqual(data["summary"]["total_turns"], len(turns))
        self.assertGreater(len(data["records"]), 0)

    def test_main_dry_run(self):
        exit_code = main(["--dry-run", "--language", "zh", "--rounds", "1"])

        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
