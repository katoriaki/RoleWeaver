import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import memory_runtime
from memory_runtime import HybridMemoryStore


class MemorySchemaTestCase(unittest.TestCase):
    def setUp(self):
        self._sentence_transformer = memory_runtime.SentenceTransformer
        self._cross_encoder = memory_runtime.CrossEncoder
        self._np = memory_runtime.np
        memory_runtime.SentenceTransformer = None
        memory_runtime.CrossEncoder = None
        memory_runtime.np = None

    def tearDown(self):
        memory_runtime.SentenceTransformer = self._sentence_transformer
        memory_runtime.CrossEncoder = self._cross_encoder
        memory_runtime.np = self._np

    def test_new_memory_writes_schema_metadata(self):
        with TemporaryDirectory() as temp_dir:
            memory_file = Path(temp_dir) / "memories.json"
            store = HybridMemoryStore(memory_file=str(memory_file), index_file=str(Path(temp_dir) / "memories.faiss"))

            store.add_memory(
                content="User prefers short LINE replies during work hours.",
                tags=["line"],
                category="preference",
                source="conversation",
                metadata={"confidence": 0.8, "evidence": ["turn:1"], "reason": "User stated it directly."},
            )

            memory = json.loads(memory_file.read_text(encoding="utf-8"))[0]

        self.assertEqual(memory["schema_version"], "1.0")
        self.assertEqual(memory["memory_type"], "preference")
        self.assertEqual(memory["memory_layer"], "long_term")
        self.assertEqual(memory["scope"], "user_personalization")
        self.assertEqual(memory["source"], "conversation")
        self.assertEqual(memory["source_kind"], "chat")
        self.assertEqual(memory["status"], "active")
        self.assertEqual(memory["confidence"], 0.8)
        self.assertEqual(memory["evidence"], ["turn:1"])
        self.assertEqual(memory["reason"], "User stated it directly.")

    def test_old_memory_records_are_backfilled_on_load(self):
        with TemporaryDirectory() as temp_dir:
            memory_file = Path(temp_dir) / "memories.json"
            memory_file.write_text(
                json.dumps([
                    {
                        "id": 1,
                        "content": "Old event",
                        "tags": [],
                        "importance": 3,
                        "timestamp": 1,
                        "metadata": {},
                        "category": "episodic",
                        "source": "conversation",
                    }
                ]),
                encoding="utf-8",
            )

            store = HybridMemoryStore(memory_file=str(memory_file), index_file=str(Path(temp_dir) / "memories.faiss"))

        self.assertEqual(store.memories[0]["schema_version"], "1.0")
        self.assertEqual(store.memories[0]["memory_type"], "episodic")
        self.assertEqual(store.memories[0]["memory_layer"], "long_term")
        self.assertEqual(store.memories[0]["scope"], "relationship_context")
        self.assertEqual(store.memories[0]["source_kind"], "chat")
        self.assertEqual(store.memories[0]["status"], "active")

    def test_memory_status_update_removes_item_from_search_context(self):
        with TemporaryDirectory() as temp_dir:
            memory_file = Path(temp_dir) / "memories.json"
            store = HybridMemoryStore(memory_file=str(memory_file), index_file=str(Path(temp_dir) / "memories.faiss"))
            store.add_memory(
                content="The user likes morning curry.",
                tags=["food"],
                category="episodic",
                source="conversation",
            )

            updated = store.update_memory(
                1,
                status="stale",
                confidence=0.2,
                reason="User later corrected this.",
                evidence=["turn:2"],
                contradicts=[2],
            )
            results = store.search("morning curry", top_k=5, min_score=0.0)

        self.assertEqual(updated["status"], "stale")
        self.assertEqual(updated["confidence"], 0.2)
        self.assertEqual(updated["reason"], "User later corrected this.")
        self.assertEqual(updated["evidence"], ["turn:2"])
        self.assertEqual(updated["contradicts"], [2])
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
