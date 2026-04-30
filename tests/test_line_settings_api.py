import csv
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import API as api_module


class LineSettingsApiTestCase(unittest.TestCase):
    def _write_config(self, path: Path) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["key", "value"])
            writer.writerow(["base_model_path", str(path.parent / "model")])
            writer.writerow(["session_root", str(path.parent / "memory")])

    def test_line_settings_round_trip_and_json_validation(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "roleweaver.config.csv"
            env_path = temp_path / "line" / ".env"
            policy_path = temp_path / "line" / "surface_policy.json"
            self._write_config(config_path)
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text("LINE_CHANNEL_SECRET=secret\n", encoding="utf-8")
            policy_path.write_text(
                json.dumps({"line": {"max_new_tokens": 192}}, ensure_ascii=False),
                encoding="utf-8",
            )

            with (
                patch.object(api_module, "LINE_ENV_FILE", env_path),
                patch.object(api_module, "LINE_SURFACE_POLICY_FILE", policy_path),
            ):
                client = TestClient(api_module.create_app(config_file=str(config_path)))

                loaded = client.get("/integrations/line/settings")
                self.assertEqual(loaded.status_code, 200)
                self.assertEqual(loaded.json()["env_file"], str(env_path))
                self.assertIn("LINE_CHANNEL_SECRET=secret", loaded.json()["env_text"])

                saved = client.post(
                    "/integrations/line/settings",
                    json={
                        "env_text": "LINE_CHANNEL_SECRET=changed\n",
                        "surface_policy_text": '{"line":{"max_new_tokens":256}}',
                    },
                )
                self.assertEqual(saved.status_code, 200)
                self.assertIn("changed", env_path.read_text(encoding="utf-8"))
                self.assertEqual(json.loads(policy_path.read_text(encoding="utf-8"))["line"]["max_new_tokens"], 256)

                rejected = client.post(
                    "/integrations/line/settings",
                    json={"surface_policy_text": "{not-json"},
                )
                self.assertEqual(rejected.status_code, 400)

    def test_web_console_assets_and_tunnel_status(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "roleweaver.config.csv"
            self._write_config(config_path)
            client = TestClient(api_module.create_app(config_file=str(config_path)))

            self.assertEqual(client.get("/").status_code, 200)
            self.assertEqual(client.get("/app.js").status_code, 200)
            self.assertEqual(client.get("/styles.css").status_code, 200)
            self.assertEqual(client.get("/vendor/vue.global.prod.js").status_code, 200)

            tunnel = client.get("/integrations/tunnel/status")
            self.assertEqual(tunnel.status_code, 200)
            self.assertFalse(tunnel.json()["active"])

    def test_extract_cloudflare_tunnel_url(self):
        text = "info https://old.trycloudflare.com\ninfo https://fresh.trycloudflare.com"
        self.assertEqual(api_module._extract_tunnel_url(text), "https://fresh.trycloudflare.com")


if __name__ == "__main__":
    unittest.main()
