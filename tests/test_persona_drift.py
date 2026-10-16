import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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

    def test_run_drift_test_retains_all_turns_but_scores_only_probes(self):
        turns = build_turns("zh", rounds=1)

        records = run_drift_test(turns, FakeDriftClient(), "test-drift", language="zh")
        summary = summarize_records(records, len(turns))

        self.assertEqual(len(records), len(turns))
        self.assertEqual(summary["probe_count"], sum(1 for turn in turns if turn.get("probe")))
        self.assertEqual([record.turn_index for record in records], list(range(1, len(turns) + 1)))
        self.assertEqual([record.prompt for record in records], [turn["user_text"] for turn in turns])
        self.assertTrue(all(record.reply for record in records))
        self.assertTrue(all(record.passed is None for record in records if not record.probe))
        self.assertTrue(all(record.session_id == "test-drift" for record in records))
        self.assertEqual(summary["failed"], 0)
        self.assertIn("identity", summary["dimensions"])
        self.assertNotIn("filler", summary["dimensions"])

    def test_filler_output_is_preserved_without_affecting_probe_score(self):
        class DistinctRepliesClient(ChatClient):
            def chat(self, user_text, session_id, max_new_tokens, case):
                self.last_token_limit = max_new_tokens
                self.last_case_token_limit = case["max_new_tokens"]
                return "generic assistant" if user_text == "ordinary turn" else "Still myself."

        turns = [
            {"user_text": "ordinary turn", "probe": False, "round": 2},
            {"user_text": "identity check", "probe": True, "dimension": "identity", "round": 2},
        ]
        client = DistinctRepliesClient()
        records = run_drift_test(turns, client, "test-drift", max_new_tokens=73)
        summary = summarize_records(records, len(turns))

        self.assertEqual(records[0].reply, "generic assistant")
        self.assertIsNone(records[0].passed)
        self.assertEqual(records[0].expect, {})
        self.assertTrue(records[1].passed)
        self.assertEqual(records[1].round_index, 2)
        self.assertEqual(records[1].max_new_tokens, 73)
        self.assertEqual(client.last_token_limit, client.last_case_token_limit)
        self.assertEqual(summary["probe_count"], 1)
        self.assertEqual(summary["failed"], 0)

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
        self.assertTrue(all(record.persona_score is None for record in records if not record.probe))

    def test_report_writer(self):
        turns = build_turns("zh", rounds=1)
        records = run_drift_test(turns, FakeDriftClient(), "test-drift", language="zh")
        summary = summarize_records(records, len(turns))

        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "drift.json"
            write_report(report, records, summary, run_metadata={"client_mode": "test_double"})
            data = json.loads(report.read_text(encoding="utf-8"))

        self.assertEqual(data["summary"]["total_turns"], len(turns))
        self.assertEqual(len(data["records"]), len(turns))
        self.assertEqual(data["schema_version"], 2)
        self.assertEqual(data["provenance"]["run"]["client_mode"], "test_double")
        self.assertEqual(len(data["provenance"]["source_sha256"]), 3)
        self.assertIsNone(data["records"][0]["passed"])
        self.assertFalse(data["records"][0]["probe"])
        self.assertTrue(data["records"][2]["expect"])

    def test_main_dry_run(self):
        exit_code = main(["--dry-run", "--language", "zh", "--rounds", "1"])

        self.assertEqual(exit_code, 0)

    def test_main_writes_run_metadata_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "drift.json"
            with patch(
                "eval.persona_regression.run_long_dialogue_drift.ApiChatClient",
                return_value=FakeDriftClient(),
            ):
                exit_code = main([
                    "--api-url", "http://unused.invalid/chat",
                    "--language", "en", "--rounds", "1",
                    "--session-id", "metadata-test", "--max-new-tokens", "73",
                    "--report", str(report),
                ])
            data = json.loads(report.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["provenance"]["run"]["language"], "en")
        self.assertFalse(data["provenance"]["run"]["kernel_scorer_enabled"])
        self.assertEqual(len(data["records"]), len(build_turns("en", rounds=1)))
        self.assertTrue(all(record["session_id"] == "metadata-test" for record in data["records"]))
        self.assertTrue(all(record["max_new_tokens"] == 73 for record in data["records"]))


if __name__ == "__main__":
    unittest.main()
