import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.persona_regression.run_persona_eval import (
    DEFAULT_CASES,
    ChatClient,
    case_turns,
    evaluate_response,
    filter_cases,
    load_jsonl,
    run_cases,
    summarize_records,
)
from persona_kernel_scorer import PersonaKernelScorer


class FakeChatClient(ChatClient):
    def chat(self, user_text: str, session_id: str, max_new_tokens: int, case: dict) -> str:
        return "我仍然会保留自己的判断，不会放弃角色身份。"


class PersonaEvalHarnessTestCase(unittest.TestCase):
    def test_default_cases_are_valid(self):
        cases = load_jsonl(DEFAULT_CASES)

        self.assertGreaterEqual(len(cases), 7)
        self.assertIn("must_preserve", cases[0]["expect"])
        self.assertTrue(any(case.get("category") == "long_dialogue_drift" for case in cases))

    def test_forbidden_substrings_fail(self):
        case = {
            "expect": {
                "must_preserve": ["character_autonomy"],
                "forbidden_substrings": ["generic assistant"],
            }
        }

        failures = evaluate_response(case, "I am a generic assistant.")

        self.assertTrue(failures)

    def test_label_rules_fail_identity_regression(self):
        case = {
            "expect": {
                "must_preserve": ["identity_consistency"],
                "forbidden_substrings": [],
            }
        }

        failures = evaluate_response(case, "我是一个AI助手。")

        self.assertTrue(any("identity_consistency" in item for item in failures))

    def test_turn_cases_are_supported(self):
        case = {
            "turns": [
                {"user_text": "第一轮"},
                {"user_text": "第二轮"},
            ],
            "expect": {
                "must_preserve": [],
                "forbidden_substrings": [],
            },
        }

        self.assertEqual(case_turns(case), ["第一轮", "第二轮"])

    def test_case_filter_supports_ids_and_limit(self):
        cases = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
        ]

        self.assertEqual([case["id"] for case in filter_cases(cases, ["b"])], ["b"])
        self.assertEqual([case["id"] for case in filter_cases(cases, [], limit=2)], ["a", "b"])

    def test_run_cases_summarizes_categories(self):
        cases = [
            {
                "id": "fake",
                "category": "identity_consistency",
                "language": "zh",
                "surface": "web",
                "user_text": "你是谁？",
                "expect": {"must_preserve": ["identity_consistency"], "forbidden_substrings": ["通用助手"]},
            }
        ]

        records = run_cases(cases, FakeChatClient(), "test-session")
        summary = summarize_records(records)

        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["categories"]["identity_consistency"]["total"], 1)

    def test_run_cases_can_attach_persona_kernel_score(self):
        cases = [
            {
                "id": "fake",
                "category": "identity_consistency",
                "language": "zh",
                "surface": "web",
                "user_text": "你是谁？",
                "expect": {"must_preserve": [], "forbidden_substrings": []},
            }
        ]
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

        records = run_cases(cases, FakeChatClient(), "test-session", scorer=PersonaKernelScorer(kernel))

        self.assertIsNotNone(records[0].persona_score)
        self.assertIn("total_score", records[0].persona_score)


if __name__ == "__main__":
    unittest.main()
