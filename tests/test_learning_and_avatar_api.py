import csv
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from API import create_app


def write_test_config(root):
    config_path = root / "roleweaver.config.csv"
    with config_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["key", "value"])
        writer.writerows([
            ("base_model_path", str(root / "model")),
            ("session_root", str(root / "memory")),
        ])
    return str(config_path)


class LearningAndAvatarApiTestCase(unittest.TestCase):
    def test_pet_model_metadata(self):
        with TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"ROLEWEAVER_BACKGROUND_WORKER": "0"}):
            root = Path(temp_dir)
            model_root = root / "pet-model"
            (model_root / "expressions").mkdir(parents=True)
            (model_root / "motions").mkdir()
            (model_root / "expressions" / "smile.exp3.json").write_text("{}", encoding="utf-8")
            (model_root / "motions" / "idle.motion3.json").write_text("{}", encoding="utf-8")
            model_json = model_root / "fixture.model3.json"
            model_json.write_text(json.dumps({"FileReferences": {"Expressions": [
                {"Name": "smile", "File": "expressions/smile.exp3.json"},
                {"Name": "missing", "File": "expressions/missing.exp3.json"},
            ]}}), encoding="utf-8-sig")
            with patch("API.PET_MODEL_ROOT", model_root), patch("API.PET_MODEL_JSON", model_json):
                with TestClient(create_app(config_file=write_test_config(root))) as client:
                    response = client.get("/pet/model")

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["model_name"], "fixture")
            self.assertEqual(data["model_json"], str(model_json))
            self.assertEqual(data["expressions"], [
                {"name": "smile", "file": "expressions/smile.exp3.json", "exists": True},
                {"name": "missing", "file": "expressions/missing.exp3.json", "exists": False},
            ])
            self.assertEqual(data["motions"], [{"name": "idle.motion3", "file": "motions/idle.motion3.json"}])
            self.assertEqual(data["vts_websocket_url"], "ws://127.0.0.1:8001")

    def test_pet_model_missing_returns_not_found(self):
        with TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"ROLEWEAVER_BACKGROUND_WORKER": "0"}):
            root = Path(temp_dir)
            with patch("API.PET_MODEL_JSON", root / "missing.model3.json"):
                with TestClient(create_app(config_file=write_test_config(root))) as client:
                    response = client.get("/pet/model")
            self.assertEqual(response.status_code, 404)
            self.assertIn("Live2D model not found", response.json()["detail"])

    def test_learning_status_and_dry_run(self):
        with TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"ROLEWEAVER_BACKGROUND_WORKER": "0"}):
            root = Path(temp_dir)
            textbook = root / "ChinaTextbook"
            textbook.mkdir()
            (textbook / "小学数学.md").write_text("# 数学\n1 + 1 = 2\n", encoding="utf-8")

            with patch("API.TEXTBOOK_ROOT", textbook), patch("API.LEARNING_ROOT", root / "learning"):
                with TestClient(create_app(config_file=write_test_config(root))) as client:
                    status = client.get("/learning/status?session_id=role-study&subject=数学")
                    self.assertEqual(status.status_code, 200)
                    self.assertEqual(status.json()["runtime"]["material_count"], 1)

                    response = client.post(
                        "/learning/run-once",
                        json={"session_id": "role-study", "subject": "数学", "use_model": False},
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("学习笔记", response.json()["step"]["output"])


if __name__ == "__main__":
    unittest.main()
