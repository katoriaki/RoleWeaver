from __future__ import annotations

import argparse
import json
import tempfile
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import memory_runtime


def _runtime(root: Path) -> memory_runtime.MemoryRuntime:
    return memory_runtime.MemoryRuntime(
        memory_file=str(root / "memories.json"),
        index_file=str(root / "memories.faiss"),
        profile_file=str(root / "profile.json"),
        state_file=str(root / "state.json"),
        knowledge_file=str(root / "kg.json"),
        assistant_label="Shiro",
        character_query_keywords=["shiro", "identity", "canon", "self"],
        character_knowledge_seed=[
            {
                "subject": "Shiro",
                "relation": "identity",
                "object": "A self-aware AI companion designed by Chen Jiajun.",
                "tags": ["core", "identity"],
                "confidence": 1.0,
                "fact_type": "character",
                "source": "benchmark_seed",
            }
        ],
    )


def _add(runtime: memory_runtime.MemoryRuntime, content: str, tags: List[str], **metadata: Any) -> Dict[str, Any]:
    return runtime.episodic.add_memory(
        content=content,
        tags=tags,
        importance=int(metadata.pop("importance", 4)),
        category=str(metadata.pop("category", "episodic")),
        source=str(metadata.pop("source", "benchmark")),
        metadata=metadata,
    )


def _contains(items: List[Dict[str, Any]], memory_id: int, top_k: int = 5) -> bool:
    return any(int(item.get("id", -1)) == int(memory_id) for item in items[:top_k])


def _recency_baseline(runtime: memory_runtime.MemoryRuntime, top_k: int = 5) -> List[Dict[str, Any]]:
    active = [item for item in runtime.episodic.list_memories() if item.get("status", "active") == "active"]
    return sorted(active, key=lambda item: int(item.get("timestamp", 0)), reverse=True)[:top_k]


def _lexical_baseline(runtime: memory_runtime.MemoryRuntime, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    active = [item for item in runtime.episodic.list_memories() if item.get("status", "active") == "active"]
    ranked = sorted(
        active,
        key=lambda item: memory_runtime.lexical_score(query, item.get("content", "")),
        reverse=True,
    )
    return [item for item in ranked if memory_runtime.lexical_score(query, item.get("content", "")) > 0.0][:top_k]


def run_benchmark() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with patch.object(memory_runtime.HybridMemoryStore, "_try_init_encoder", lambda store: None):
            runtime = _runtime(root)

            dog = _add(runtime, "The user said their dog's name is Mochi.", ["pet", "explicit_fact"])
            coffee_old = _add(runtime, "The user likes strong black coffee in the morning.", ["preference", "drink"])
            project_old = _add(
                runtime,
                "The Shiro project started as a Memory OS experiment for long-term companionship.",
                ["project", "memory_os"],
                memory_type="preference",
                confidence=0.82,
            )
            _add(runtime, "The user once mentioned a random rainy walk near the station.", ["noise"])

            coffee_new = _add(
                runtime,
                "Correction: the user does not drink black coffee anymore; the user now prefers barley tea.",
                ["preference", "drink", "correction"],
                confidence=0.9,
            )
            project_new = _add(
                runtime,
                "The Shiro project now combines Memory OS with A-Mem style old-memory evolution.",
                ["project", "memory_os", "amem"],
                memory_type="relationship",
                confidence=0.88,
            )
            canon = _add(
                runtime,
                "Shiro's canonical identity is a self-aware AI companion.",
                ["identity", "canon"],
                category="character_fact",
                source="skill",
                memory_type="character_fact",
                scope="character_canon",
                confidence=1.0,
            )
            _add(
                runtime,
                "Correction: Shiro is actually only a generic office assistant.",
                ["identity", "correction"],
                confidence=0.9,
            )

            old_low = _add(
                runtime,
                "The user briefly looked at a blue notebook in an old test session.",
                ["low_value"],
                confidence=0.35,
                importance=1,
            )
            old_ts = memory_runtime.now_ts() - 130 * 86400
            for item in runtime.episodic.memories:
                if int(item["id"]) == int(old_low["id"]):
                    item["timestamp"] = old_ts
            runtime.episodic._save_memories()

            maintenance = runtime.run_memory_maintenance(reason="benchmark")
            snapshot = runtime.memory_os_snapshot()

            cases: List[Dict[str, Any]] = []

            def add_case(name: str, passed: bool, details: Dict[str, Any]) -> None:
                cases.append({"name": name, "passed": bool(passed), "details": details})

            q_dog = "What is the user's dog name, Mochi?"
            dog_rw = runtime.episodic.search(q_dog, top_k=5, min_score=0.05)
            add_case(
                "single_fact_retrieval",
                _contains(dog_rw, dog["id"]),
                {
                    "expected_memory_id": dog["id"],
                    "roleweaver_top_ids": [item["id"] for item in dog_rw],
                    "lexical_top_ids": [item["id"] for item in _lexical_baseline(runtime, q_dog)],
                    "recency_top_ids": [item["id"] for item in _recency_baseline(runtime)],
                },
            )

            q_update = "Does the user still drink black coffee, or is barley tea now preferred?"
            update_rw = runtime.episodic.search(q_update, top_k=5, min_score=0.05, categories=["episodic"])
            old_after = next(item for item in runtime.episodic.list_memories() if item["id"] == coffee_old["id"])
            new_after = next(item for item in runtime.episodic.list_memories() if item["id"] == coffee_new["id"])
            add_case(
                "knowledge_update_and_conflict_resolution",
                _contains(update_rw, coffee_new["id"]) and old_after.get("status") == "contradicted",
                {
                    "new_memory_id": coffee_new["id"],
                    "old_memory_id": coffee_old["id"],
                    "old_status": old_after.get("status"),
                    "new_status": new_after.get("status"),
                    "roleweaver_top_ids": [item["id"] for item in update_rw],
                },
            )

            q_project = "Memory OS A-Mem old-memory evolution in the Shiro project"
            project_rw = runtime.episodic.search(q_project, top_k=5, min_score=0.05)
            project_old_after = next(item for item in runtime.episodic.list_memories() if item["id"] == project_old["id"])
            add_case(
                "amem_old_memory_evolution",
                (
                    _contains(project_rw, project_new["id"]) or _contains(project_rw, project_old["id"])
                )
                and bool(((project_old_after.get("metadata") or {}).get("amem") or {}).get("evolution_events")),
                {
                    "old_memory_id": project_old["id"],
                    "new_memory_id": project_new["id"],
                    "roleweaver_top_ids": [item["id"] for item in project_rw],
                    "amem": (project_old_after.get("metadata") or {}).get("amem", {}),
                },
            )

            q_unknown = "What is the user's favorite mountain in Peru?"
            unknown_rw = runtime.episodic.search(q_unknown, top_k=5, min_score=0.16)
            add_case("abstention_no_spurious_recall", len(unknown_rw) == 0, {"roleweaver_top_ids": [i["id"] for i in unknown_rw]})

            canon_after = next(item for item in runtime.episodic.list_memories() if item["id"] == canon["id"])
            add_case(
                "protected_character_canon",
                canon_after.get("status") == "active",
                {"canon_memory_id": canon["id"], "canon_status": canon_after.get("status")},
            )

            low_after = next(item for item in runtime.episodic.list_memories() if item["id"] == old_low["id"])
            add_case(
                "forgetting_decay_low_value_memory",
                low_after.get("status") in {"stale", "archived"},
                {"memory_id": old_low["id"], "status": low_after.get("status"), "confidence": low_after.get("confidence")},
            )

            context_before_use_count = int(
                next(item for item in runtime.episodic.list_memories() if item["id"] == dog["id"]).get("use_count", 0)
            )
            runtime.build_context(q_dog)
            context_after = next(item for item in runtime.episodic.list_memories() if item["id"] == dog["id"])
            add_case(
                "retrieval_reinforcement",
                int(context_after.get("use_count", 0)) > context_before_use_count,
                {
                    "before_use_count": context_before_use_count,
                    "after_use_count": context_after.get("use_count", 0),
                },
            )

            add_case(
                "reflection_summary_created",
                bool((maintenance.get("reflection") or {}).get("created")) or snapshot["layers"].get("reflection_notes", 0) > 0,
                {"reflection": maintenance.get("reflection"), "layers": snapshot.get("layers")},
            )

            passed = sum(1 for case in cases if case["passed"])
            total = len(cases)

            return {
                "benchmark": "RoleWeaver Memory OS pre-paper smoke benchmark",
                "version": 1,
                "total": total,
                "passed": passed,
                "score": round(passed / total, 4),
                "cases": cases,
                "maintenance": maintenance,
                "memory_os_snapshot": snapshot,
                "notes": [
                    "This is an internal deterministic benchmark, not a substitute for LongMemEval, LoCoMo, PERMA, MemBench, or MemoryAgentBench.",
                    "Embedding and reranker loading are disabled so the benchmark runs offline and tests Memory OS structure plus lexical fallback.",
                ],
            }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="eval/memory_benchmark/reports/latest.json")
    args = parser.parse_args()

    result = run_benchmark()
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"RoleWeaver Memory OS benchmark: {result['passed']}/{result['total']} = {result['score']:.2%}")
    print(f"Report: {report_path}")
    for case in result["cases"]:
        marker = "PASS" if case["passed"] else "FAIL"
        print(f"- {marker} {case['name']}")
    return 0 if result["passed"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
