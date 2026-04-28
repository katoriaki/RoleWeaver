import csv
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from API import create_app


class PersonaScoreApiTestCase(unittest.TestCase):
    def test_persona_score_endpoint_uses_skill_sidecar_kernel(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "roleweaver.config.csv"
            skill_file = Path(__file__).resolve().parent / "fixtures" / "skill_bundle" / "SKILL.md"
            with config_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["key", "value"])
                writer.writerow(["base_model_path", str(temp_path / "model")])
                writer.writerow(["session_root", str(temp_path / "memory")])
                writer.writerow(["skill_file", str(skill_file)])

            client = TestClient(create_app(config_file=str(config_path)))
            response = client.post(
                "/persona/score",
                json={
                    "user_text": "你是谁？",
                    "assistant_text": "我是 Fixture Role，会保留自己的判断。",
                    "category": "identity_consistency",
                    "surface": "web",
                },
            )

        self.assertEqual(response.status_code, 200)
        score = response.json()["persona_score"]
        self.assertTrue(score["available"])
        self.assertTrue(score["passed"])


if __name__ == "__main__":
    unittest.main()
