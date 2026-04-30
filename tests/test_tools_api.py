import csv
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from API import create_app


class ToolsApiTestCase(unittest.TestCase):
    def test_list_and_run_time_tool(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "roleweaver.config.csv"
            with config_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["key", "value"])
                writer.writerow(["base_model_path", str(temp_path / "model")])
                writer.writerow(["session_root", str(temp_path / "memory")])
                writer.writerow(["local_location", "Tokyo, Japan"])

            old_worker = os.environ.get("ROLEWEAVER_BACKGROUND_WORKER")
            os.environ["ROLEWEAVER_BACKGROUND_WORKER"] = "0"
            try:
                client = TestClient(create_app(config_file=str(config_path)))
                listed = client.get("/tools")
                self.assertEqual(listed.status_code, 200)
                names = {tool["name"] for tool in listed.json()["tools"]}
                self.assertIn("runtime.time_now", names)
                self.assertIn("memory.search", names)

                run = client.post(
                    "/tools/run",
                    json={
                        "tool_name": "runtime.time_now",
                        "session_id": "web",
                        "arguments": {},
                    },
                )
                self.assertEqual(run.status_code, 200)
                body = run.json()
                self.assertEqual(body["status"], "completed")
                self.assertEqual(body["result"]["location"], "Tokyo, Japan")

                actions = client.get("/tools/actions?limit=1")
                self.assertEqual(actions.status_code, 200)
                self.assertEqual(actions.json()["actions"][0]["tool_name"], "runtime.time_now")
            finally:
                if old_worker is None:
                    os.environ.pop("ROLEWEAVER_BACKGROUND_WORKER", None)
                else:
                    os.environ["ROLEWEAVER_BACKGROUND_WORKER"] = old_worker

    def test_unknown_tool_returns_400(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "roleweaver.config.csv"
            with config_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["key", "value"])
                writer.writerow(["base_model_path", str(temp_path / "model")])
                writer.writerow(["session_root", str(temp_path / "memory")])

            client = TestClient(create_app(config_file=str(config_path)))
            run = client.post(
                "/tools/run",
                json={"tool_name": "runtime.missing", "arguments": {}},
            )
            self.assertEqual(run.status_code, 400)

    def test_pdf_read_tool_extracts_literal_text(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pdf_path = temp_path / "sample.pdf"
            pdf_path.write_bytes(
                b"%PDF-1.4\n"
                b"1 0 obj <<>> endobj\n"
                b"2 0 obj << /Length 44 >> stream\n"
                b"BT /F1 12 Tf 72 720 Td (Hello PDF Tool) Tj ET\n"
                b"endstream endobj\n%%EOF"
            )
            config_path = temp_path / "roleweaver.config.csv"
            with config_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["key", "value"])
                writer.writerow(["base_model_path", str(temp_path / "model")])
                writer.writerow(["session_root", str(temp_path / "memory")])

            client = TestClient(create_app(config_file=str(config_path)))
            run = client.post(
                "/tools/run",
                json={
                    "tool_name": "document.pdf_read",
                    "session_id": "web",
                    "arguments": {
                        "path": str(pdf_path),
                        "max_pages": 2,
                        "max_chars": 1000,
                    },
                },
            )

            self.assertEqual(run.status_code, 200)
            body = run.json()
            self.assertEqual(body["status"], "completed")
            self.assertIn("Hello PDF Tool", body["result"]["text"])
            self.assertEqual(body["result"]["memory_policy"], "store_summary_and_source_path")


if __name__ == "__main__":
    unittest.main()
