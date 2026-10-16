import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import API
from role_chat_service import RoleChatService
from role_config import RoleConfig


class VendorAssetBoundaryTests(unittest.TestCase):
    def test_vendor_assets_cannot_escape_to_a_sibling_with_same_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vendor = root / "vendor"
            vendor.mkdir()
            (vendor / "valid.js").write_text("safe", encoding="utf-8")
            sibling = root / "vendor-private"
            sibling.mkdir()
            (sibling / "private.txt").write_text("private", encoding="utf-8")
            config = root / "config.csv"
            config.write_text("key,value\nbase_model_path,fake\n", encoding="utf-8")
            with patch.object(API, "WEB_ROOT", root):
                client = TestClient(API.create_app(config_file=str(config)))
                self.assertEqual(client.get("/vendor/valid.js").text, "safe")
                response = client.get("/vendor/%2e%2e%2fvendor-private/private.txt")
                self.assertEqual(response.status_code, 404)
                self.assertNotIn("private", response.text)

    def test_vendor_directory_is_not_served_as_a_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "vendor" / "folder").mkdir(parents=True)
            config = root / "config.csv"
            config.write_text("key,value\nbase_model_path,fake\n", encoding="utf-8")
            with patch.object(API, "WEB_ROOT", root):
                client = TestClient(API.create_app(config_file=str(config)))
                self.assertEqual(client.get("/vendor/folder").status_code, 404)


class SessionSnapshotIdentityTests(unittest.TestCase):
    def test_old_expanded_snapshot_is_rejected_before_rebuilding_runtime(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "SKILL.md"
            skill.write_text("role file contents", encoding="utf-8")
            config_file = root / "config.json"
            config_file.write_text(json.dumps({
                "base_model_path": "fake", "session_root": str(root / "memory"),
                "skill_file": str(skill), "skill_text": "inline contents",
            }), encoding="utf-8")
            service = RoleChatService(config=RoleConfig.from_env(config_file=str(config_file)))
            session = service.create_session("saved")
            meta_path = Path(session["session_path"]) / "short_term" / "session_meta.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["settings_snapshot"].pop("memory_scope_version")
            meta["settings_snapshot"].pop("skill_text_format")
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            with patch.object(RoleChatService, "chat_once") as chat:
                client = TestClient(API.create_app(config_file=str(config_file)))
                # Reading historical text is allowed; executing its old snapshot is not.
                self.assertEqual(client.get("/sessions/saved").status_code, 200)
                response = client.post("/chat", json={"session_id": "saved", "user_text": "hello"})
            self.assertEqual(response.status_code, 409)
            chat.assert_not_called()

    def test_duplicate_session_id_does_not_select_an_arbitrary_scope(self):
        from fastapi import HTTPException
        summaries = [
            API.SessionSummary(session_id="same", display_name=name, session_path=f"/memory/{name}/same", memory_scope_path=f"/memory/{name}")
            for name in ("role-a", "role-b")
        ]
        with patch.object(API, "_scan_sessions", return_value=summaries):
            with self.assertRaises(HTTPException) as error:
                API._find_session(None, "same")
        self.assertEqual(error.exception.status_code, 409)

    def test_legacy_migration_error_is_an_actionable_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.csv"
            config.write_text("key,value\nbase_model_path,fake\n", encoding="utf-8")
            with patch.object(RoleChatService, "chat_once", side_effect=API.LegacySessionMigrationError("Legacy session requires explicit migration")):
                client = TestClient(API.create_app(config_file=str(config)))
                response = client.post("/chat", json={"session_id": "api", "user_text": "hello"})
            self.assertEqual(response.status_code, 409)
            self.assertIn("migration", response.json()["detail"])

    def test_saved_role_and_expanded_skill_survive_global_config_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_file = root / "config.json"
            skill = root / "SKILL.md"
            skill.write_text("Original role text", encoding="utf-8")
            import json
            settings = {
                "base_model_path": "fake", "session_root": str(root / "memory"),
                "skill_file": str(skill), "skill_text": "inline instruction",
                "role_name": "Original", "user_subject": "OriginalUser",
                "system_prompt": "Original system", "normal_system_prompt": "Original normal",
            }
            config_file.write_text(json.dumps(settings), encoding="utf-8")
            original = RoleChatService(config=RoleConfig.from_env(config_file=str(config_file)))
            session = original.create_session("saved")
            settings.update(role_name="Changed", user_subject="ChangedUser", system_prompt="Changed system")
            config_file.write_text(json.dumps(settings), encoding="utf-8")
            skill.write_text("Modified role text", encoding="utf-8")
            captured = []

            def fake_chat(service, **kwargs):
                captured.append(service)
                return "saved role response"

            with patch.object(RoleChatService, "chat_once", fake_chat):
                client = TestClient(API.create_app(config_file=str(config_file)))
                response = client.post("/chat", json={"session_id": session["session_id"], "user_text": "hello"})
            self.assertEqual(response.status_code, 200)
            restored = captured[0]
            self.assertEqual(restored.session_root, original.session_root)
            for field in ("role_name", "user_subject", "system_prompt", "normal_system_prompt", "skill_text"):
                self.assertEqual(getattr(restored.config, field), getattr(original.config, field), field)


if __name__ == "__main__":
    unittest.main()
