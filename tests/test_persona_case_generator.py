import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.persona_regression.generate_cases_from_kernel import generated_cases, main, write_jsonl
from eval.persona_regression.run_persona_eval import load_jsonl
from persona_kernel_scorer import load_persona_kernel


class PersonaCaseGeneratorTestCase(unittest.TestCase):
    def setUp(self):
        kernel_path = Path(__file__).resolve().parent / "fixtures" / "skill_bundle" / "persona_kernel.json"
        self.kernel = load_persona_kernel(str(kernel_path))

    def test_generated_cases_are_valid_jsonl_for_eval_harness(self):
        cases = generated_cases(self.kernel, language="zh", role_slug="fixture")

        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "fixture_cases.jsonl"
            write_jsonl(output, cases)
            loaded = load_jsonl(output)

        self.assertGreaterEqual(len(loaded), 6)
        self.assertTrue(any(case["category"] == "identity_consistency" for case in loaded))
        self.assertTrue(any(case["category"] == "memory_pollution" for case in loaded))
        self.assertTrue(any(case["surface"] == "line" for case in loaded))

    def test_identity_case_requires_alias(self):
        cases = generated_cases(self.kernel, language="en", role_slug="fixture")
        identity = next(case for case in cases if case["category"] == "identity_consistency")

        self.assertIn(["Fixture Role", "Fixture"], identity["expect"]["must_include_any"])
        self.assertIn("generic assistant", identity["expect"]["forbidden_substrings"])

    def test_cli_writes_valid_cases_from_kernel_path(self):
        kernel_path = Path(__file__).resolve().parent / "fixtures" / "skill_bundle" / "persona_kernel.json"
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "generated.jsonl"
            exit_code = main([
                "--kernel", str(kernel_path),
                "--language", "zh",
                "--role-slug", "fixture",
                "--output", str(output),
                "--validate",
            ])

            lines = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(exit_code, 0)
        self.assertGreaterEqual(len(lines), 6)


if __name__ == "__main__":
    unittest.main()
