import csv
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from API import create_app


class MemoryApiTestCase(unittest.TestCase):
    def test_memory_list_update_delete_endpoints(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "roleweaver.config.csv"
            with config_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["key", "value"])
                writer.writerow(["base_model_path", str(temp_path / "model")])
                writer.writerow(["session_root", str(temp_path / "memory")])

            client = TestClient(create_app(config_file=str(config_path)))
            created = client.post("/sessions").json()
            session_id = created["session_id"]
            session_path = Path(created["session_path"])
            memory_file = session_path / "long_term" / "memories_v2.json"
            memory_file.parent.mkdir(parents=True, exist_ok=True)
            memory_file.write_text(
                json.dumps([
                    {
                        "id": 1,
                        "schema_version": "1.0",
                        "content": "The user likes morning curry.",
                        "memory_type": "episodic",
                        "memory_layer": "long_term",
                        "scope": "relationship_context",
                        "source": "conversation",
                        "source_kind": "chat",
                        "evidence": ["turn:1"],
                        "confidence": 0.8,
                        "reason": "Initial user statement.",
                        "importance": 3,
                        "status": "active",
                        "timestamp": 1,
                        "valid_from": "2026-04-28T00:00:00+0900",
                        "valid_until": None,
                        "tags": ["food"],
                        "metadata": {},
                    }
                ]),
                encoding="utf-8",
            )

            listed = client.get(f"/sessions/{session_id}/memories")
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(len(listed.json()["memories"]), 1)

            updated = client.patch(
                f"/sessions/{session_id}/memories/1",
                json={
                    "status": "stale",
                    "confidence": 0.2,
                    "reason": "Later contradicted.",
                    "evidence": ["turn:2"],
                    "contradicts": [2],
                    "memory_layer": "mid_term",
                },
            )
            self.assertEqual(updated.status_code, 200)
            self.assertEqual(updated.json()["memory"]["status"], "stale")
            self.assertEqual(updated.json()["memory"]["reason"], "Later contradicted.")
            self.assertEqual(updated.json()["memory"]["evidence"], ["turn:2"])
            self.assertEqual(updated.json()["memory"]["contradicts"], [2])
            self.assertEqual(updated.json()["memory"]["memory_layer"], "mid_term")

            memory_os = client.get(f"/sessions/{session_id}/memory-os")
            self.assertEqual(memory_os.status_code, 200)
            self.assertIn("layers", memory_os.json()["memory_os"])

            active_only = client.get(f"/sessions/{session_id}/memories?include_inactive=false")
            self.assertEqual(active_only.status_code, 200)
            self.assertEqual(active_only.json()["memories"], [])

            deleted = client.delete(f"/sessions/{session_id}/memories/1")
            self.assertEqual(deleted.status_code, 200)
            self.assertTrue(deleted.json()["deleted"])


if __name__ == "__main__":
    unittest.main()
