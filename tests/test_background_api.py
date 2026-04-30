import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from API import create_app


class BackgroundApiTestCase(unittest.TestCase):
    def test_background_status_and_planning_job(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "roleweaver.config.csv"
            with config_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["key", "value"])
                writer.writerow(["base_model_path", str(temp_path / "model")])
                writer.writerow(["session_root", str(temp_path / "memory")])
                writer.writerow(["background_jobs_enabled", "true"])
                writer.writerow(["background_llm_enabled", "false"])
                writer.writerow(["background_idle_seconds", "600"])

            client = TestClient(create_app(config_file=str(config_path)))
            session = client.post("/sessions").json()
            status = client.get("/background/status")
            self.assertEqual(status.status_code, 200)
            self.assertIn("idle_seconds", status.json())

            run = client.post(
                "/background/run-once",
                json={
                    "job_type": "planning_regenerate",
                    "session_id": session["session_id"],
                    "force": True,
                },
            )
            self.assertEqual(run.status_code, 200)
            self.assertEqual(run.json()["status"], "completed")

    def test_background_llm_job_is_gated(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "roleweaver.config.csv"
            with config_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["key", "value"])
                writer.writerow(["base_model_path", str(temp_path / "model")])
                writer.writerow(["session_root", str(temp_path / "memory")])
                writer.writerow(["background_llm_enabled", "false"])

            client = TestClient(create_app(config_file=str(config_path)))
            session = client.post("/sessions").json()
            run = client.post(
                "/background/run-once",
                json={
                    "job_type": "memory_consolidation",
                    "session_id": session["session_id"],
                    "force": True,
                },
            )

            self.assertEqual(run.status_code, 200)
            self.assertEqual(run.json()["status"], "skipped")
            self.assertIn("LLM background jobs", run.json()["reason"])

    def test_autonomous_learning_background_job_can_run_dry(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "roleweaver.config.csv"
            with config_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["key", "value"])
                writer.writerow(["base_model_path", str(temp_path / "model")])
                writer.writerow(["session_root", str(temp_path / "memory")])
                writer.writerow(["background_llm_enabled", "true"])
                writer.writerow(["autonomous_learning_enabled", "true"])
                writer.writerow(["autonomous_learning_subjects", "mathematics, computer science"])
                writer.writerow(["autonomous_learning_use_model", "false"])

            with patch("API.web_search") as mocked_search:
                mocked_search.return_value = {
                    "query": "mathematics",
                    "results": [{"title": "Math search result", "url": "https://example.test/math"}],
                    "error": "",
                }
                client = TestClient(create_app(config_file=str(config_path)))
                session = client.post("/sessions").json()
                run = client.post(
                    "/background/run-once",
                    json={
                        "job_type": "autonomous_learning",
                        "session_id": session["session_id"],
                        "force": True,
                    },
                )

            self.assertEqual(run.status_code, 200)
            body = run.json()
            self.assertEqual(body["status"], "completed")
            self.assertEqual(body["result"]["status"], "completed")
            self.assertTrue(body["result"]["learning"]["step"]["mode"].startswith("web_search_dry_run"))
            self.assertEqual(body["result"]["cycle_action"]["activity"], "professional_study")
            self.assertIn("Math search result", body["result"]["learning"]["step"]["output"])


if __name__ == "__main__":
    unittest.main()
