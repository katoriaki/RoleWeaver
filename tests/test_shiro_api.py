import csv
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from API import create_app


class ShiroApiTestCase(unittest.TestCase):
    def test_pet_model_metadata(self):
        old_worker = os.environ.get("ROLEWEAVER_BACKGROUND_WORKER")
        os.environ["ROLEWEAVER_BACKGROUND_WORKER"] = "0"
        try:
            client = TestClient(create_app())
            response = client.get("/pet/model")

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["model_name"], "March 7th")
            self.assertTrue(data["expressions"])
            self.assertTrue(all(item["exists"] for item in data["expressions"]))
            self.assertEqual(data["vts_websocket_url"], "ws://127.0.0.1:8001")
        finally:
            if old_worker is None:
                os.environ.pop("ROLEWEAVER_BACKGROUND_WORKER", None)
            else:
                os.environ["ROLEWEAVER_BACKGROUND_WORKER"] = old_worker

    def test_learning_status_and_dry_run(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            textbook = root / "ChinaTextbook"
            textbook.mkdir()
            (textbook / "小学数学.md").write_text("# 数学\n1 + 1 = 2\n", encoding="utf-8")

            old_worker = os.environ.get("ROLEWEAVER_BACKGROUND_WORKER")
            os.environ["ROLEWEAVER_BACKGROUND_WORKER"] = "0"
            try:
                with patch("API.TEXTBOOK_ROOT", textbook), patch("API.LEARNING_ROOT", root / "learning"):
                    client = TestClient(create_app())
                    status = client.get("/learning/status?session_id=shiro-study&subject=数学")
                    self.assertEqual(status.status_code, 200)
                    self.assertEqual(status.json()["runtime"]["material_count"], 1)

                    response = client.post(
                        "/learning/run-once",
                        json={"session_id": "shiro-study", "subject": "数学", "use_model": False},
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("学习笔记", response.json()["step"]["output"])
            finally:
                if old_worker is None:
                    os.environ.pop("ROLEWEAVER_BACKGROUND_WORKER", None)
                else:
                    os.environ["ROLEWEAVER_BACKGROUND_WORKER"] = old_worker

    def test_shiro_status_and_manual_observe(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "roleweaver.config.csv"
            with config_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["key", "value"])
                writer.writerow(["base_model_path", str(temp_path / "model")])
                writer.writerow(["session_root", str(temp_path / "memory")])
                writer.writerow(["shiro_enabled", "true"])
                writer.writerow(["shiro_root", str(temp_path / "shiro")])
                writer.writerow(["shiro_identity", "白"])

            old_worker = os.environ.get("ROLEWEAVER_BACKGROUND_WORKER")
            os.environ["ROLEWEAVER_BACKGROUND_WORKER"] = "0"
            try:
                client = TestClient(create_app(config_file=str(config_path)))
                session = client.post("/sessions").json()

                status = client.get(f"/sessions/{session['session_id']}/shiro")
                self.assertEqual(status.status_code, 200)
                self.assertTrue(status.json()["available"])
                self.assertEqual(status.json()["identity"], "白")

                observed = client.post(
                    f"/sessions/{session['session_id']}/shiro/observe",
                    json={"text": "帮我计划一下今天。", "source": "manual", "metadata": {}},
                )
                self.assertEqual(observed.status_code, 200)
                self.assertTrue(observed.json()["available"])

                refreshed = client.get(f"/sessions/{session['session_id']}/shiro").json()
                self.assertTrue(refreshed["recent_transitions"])
                self.assertIn("thought_context", refreshed)

                intentions = client.post(
                    f"/sessions/{session['session_id']}/shiro/tool-intentions",
                    json={"text": r"帮我读 C:\docs\a.pdf 并上网搜解法", "metadata": {}},
                )
                self.assertEqual(intentions.status_code, 200)
                names = {item["tool_name"] for item in intentions.json()["intentions"]}
                self.assertIn("document.pdf_read", names)
                self.assertIn("planning.web_search", names)
            finally:
                if old_worker is None:
                    os.environ.pop("ROLEWEAVER_BACKGROUND_WORKER", None)
                else:
                    os.environ["ROLEWEAVER_BACKGROUND_WORKER"] = old_worker


if __name__ == "__main__":
    unittest.main()
