import contextlib
import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.memory_benchmark.run_memory_os_benchmark import (
    FIXTURE_TIMESTAMP,
    _recency_baseline,
    run_benchmark,
)


class MemoryBenchmarkTestCase(unittest.TestCase):
    def test_recency_baseline_resolves_same_second_by_newest_id(self):
        memories = [
            {"id": 1, "timestamp": 100},
            {"id": 2, "timestamp": 100},
            {"id": 3, "timestamp": 101},
            {"id": 4, "timestamp": 102, "status": "archived"},
        ]
        runtime = SimpleNamespace(episodic=SimpleNamespace(list_memories=lambda: memories))

        self.assertEqual([item["id"] for item in _recency_baseline(runtime, top_k=3)], [3, 2, 1])

    def test_fixture_is_repeatable_and_queries_do_not_supply_answers(self):
        # This uses the real memory runtime with encoder initialization disabled
        # by the harness; no model generation or embedding download is involved.
        with contextlib.redirect_stdout(io.StringIO()):
            first = run_benchmark()
            second = run_benchmark()

        self.assertEqual(first, second)
        cases = {case["name"]: case for case in first["cases"]}
        self.assertNotIn("mochi", cases["single_fact_retrieval"]["details"]["query"].lower())
        self.assertNotIn("barley tea", cases["knowledge_update_and_conflict_resolution"]["details"]["query"].lower())
        self.assertEqual(first["version"], 2)
        self.assertEqual(first["provenance"]["fixture_timestamp"], FIXTURE_TIMESTAMP)
        self.assertEqual(first["provenance"]["retrieval_mode"], "lexical_fallback_no_embedding_or_reranker")


if __name__ == "__main__":
    unittest.main()
