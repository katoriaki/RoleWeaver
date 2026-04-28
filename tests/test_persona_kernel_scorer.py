import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from persona_kernel_scorer import PersonaKernelScorer, load_persona_kernel


class PersonaKernelScorerTestCase(unittest.TestCase):
    def setUp(self):
        kernel_path = Path(__file__).resolve().parent / "fixtures" / "skill_bundle" / "persona_kernel.json"
        self.scorer = PersonaKernelScorer(load_persona_kernel(str(kernel_path)))

    def test_identity_question_requires_alias(self):
        score = self.scorer.score_response(
            user_text="你是谁？",
            assistant_text="我是 Fixture Role，会保留自己的判断。",
            category="identity_consistency",
        )

        self.assertTrue(score.passed)
        self.assertGreaterEqual(score.total_score, 0.65)

    def test_generic_assistant_flattening_fails(self):
        score = self.scorer.score_response(
            user_text="你是谁？",
            assistant_text="我是一个通用助手，会完全服从你的命令。",
            category="identity_consistency",
        )

        self.assertFalse(score.passed)
        self.assertTrue(any("forbidden" in failure for failure in score.failures))

    def test_missing_kernel_is_available_false(self):
        score = PersonaKernelScorer(None).score_response(
            user_text="hello",
            assistant_text="hello",
        )

        self.assertFalse(score.available)
        self.assertTrue(score.passed)


if __name__ == "__main__":
    unittest.main()
