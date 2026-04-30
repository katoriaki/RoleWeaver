import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import memory_runtime


class FakeReranker:
    def __init__(self, scores):
        self.scores = scores

    def predict(self, pairs):
        if isinstance(self.scores, dict):
            values = []
            for _, content in pairs:
                values.append(self.scores.get(content, 0.0))
            return values
        return self.scores[: len(pairs)]


class MemoryRuntimeTestCase(unittest.TestCase):
    def setUp(self):
        tmp_root = Path(__file__).resolve().parents[1] / ".tmp_tests"
        tmp_root.mkdir(exist_ok=True)
        self.temp_dir = tempfile.TemporaryDirectory(dir=tmp_root)
        self.addCleanup(self.temp_dir.cleanup)

        self.encoder_patcher = patch.object(
            memory_runtime.HybridMemoryStore,
            "_try_init_encoder",
            lambda store: None,
        )
        self.encoder_patcher.start()
        self.addCleanup(self.encoder_patcher.stop)

        base = Path(self.temp_dir.name)
        self.runtime = memory_runtime.MemoryRuntime(
            memory_file=str(base / "memories.json"),
            index_file=str(base / "memories.faiss"),
            profile_file=str(base / "profile.json"),
            state_file=str(base / "state.json"),
            knowledge_file=str(base / "kg.json"),
            assistant_label="美铃",
            character_query_keywords=["角色", "美铃", "秦谷美铃"],
            character_knowledge_seed=[
                {
                    "subject": "秦谷美铃",
                    "relation": "生日",
                    "object": "2月6日",
                    "tags": ["core"],
                    "confidence": 1.0,
                    "fact_type": "character",
                    "source": "test_seed",
                }
            ],
        )

    def test_profile_extraction_and_persistence(self):
        self.runtime.record_turn(
            "我叫小林，你可以叫我阿林，我喜欢寿司，我现在在做记忆系统。",
            "我记住了。",
        )
        self.runtime.consolidate_pending()

        profile_lines = self.runtime.profile.render_context(max_items_per_slot=5)
        self.assertTrue(any("名字：小林" in line for line in profile_lines))
        self.assertTrue(any("称呼偏好：阿林" in line for line in profile_lines))
        self.assertTrue(any("喜欢：寿司" in line for line in profile_lines))
        self.assertTrue(any("项目：记忆系统" in line for line in profile_lines))

        memories = self.runtime.episodic.list_memories()
        contents = {item["content"] for item in memories}
        self.assertNotIn("制作人的名字：小林", contents)
        self.assertNotIn("制作人的称呼偏好：阿林", contents)
        self.assertNotIn("制作人的喜欢：寿司", contents)

        facts = self.runtime.knowledge.search("制作人 名字 小林", top_k=5, min_score=0.01)
        rendered = {(item["subject"], item["relation"], item["object"]) for item in facts}
        self.assertIn(("制作人", "名字", "小林"), rendered)

    def test_summary_buffer_archives_old_turns(self):
        turns = [
            ("我今天有点累。", "那就先休息一会儿。"),
            ("我想先把项目做完。", "别太勉强自己。"),
            ("不过还是要推进记忆系统。", "我会陪着你慢慢做。"),
            ("我刚才吃了烤肉套餐。", "嗯，那听起来不错。"),
            ("你还记得我今天做了什么吗？", "我会记得。"),
        ]

        for user_text, assistant_text in turns:
            self.runtime.record_turn(user_text, assistant_text)

        summaries = self.runtime.state.list_summaries()
        self.assertGreaterEqual(len(summaries), 1)
        self.assertIn("制作人提到：", summaries[0]["content"])
        self.assertIn("美铃回应：", summaries[0]["content"])

        recent_history = self.runtime.state.get_recent_history()
        self.assertLessEqual(len(recent_history), 8)

        summary_memories = [
            item for item in self.runtime.episodic.list_memories(category="episodic")
            if "summary" in item.get("tags", [])
        ]
        self.assertGreaterEqual(len(summary_memories), 1)

    def test_context_pressure_compresses_recent_history(self):
        for i in range(5):
            self.runtime.record_turn(f"第{i}轮用户输入很长很长", f"第{i}轮助手回复也很长很长")

        result = self.runtime.compress_recent_history(keep_messages=2, reason="test_context_pressure")

        self.assertEqual(result["status"], "compressed")
        self.assertEqual(len(self.runtime.recent_history(max_messages=None)), 2)
        self.assertGreaterEqual(result["archived_summary_count"], 1)
        summary_memories = [
            item for item in self.runtime.episodic.list_memories(category="episodic")
            if "context_compression" in item.get("tags", [])
        ]
        self.assertGreaterEqual(len(summary_memories), 1)

    def test_hybrid_long_term_search_finds_relevant_memory(self):
        self.runtime.episodic.add_memory(
            content="上次你说过最想吃烤肉套餐。",
            tags=["episodic", "food"],
            importance=4,
            category="episodic",
        )
        self.runtime.episodic.add_memory(
            content="这周你一直在做本地秦谷美铃模型。",
            tags=["episodic", "project"],
            importance=4,
            category="episodic",
        )
        self.runtime.episodic.add_memory(
            content="今天下雨了",
            tags=["episodic"],
            importance=1,
            category="episodic",
        )

        results = self.runtime.episodic.search(
            "你还记得我喜欢吃什么吗，我最喜欢烤肉。",
            top_k=3,
            min_score=0.01,
        )

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["content"], "上次你说过最想吃烤肉套餐。")

    def test_knowledge_seed_and_context_rendering(self):
        facts = self.runtime.knowledge.search("美铃 生日", top_k=5, min_score=0.01)
        objects = {item["object"] for item in facts}
        self.assertIn("2月6日", objects)

        context_text = self.runtime.build_context("美铃生日是什么时候").render()
        self.assertIn("【角色知识】", context_text)
        self.assertIn("秦谷美铃的生日：2月6日", context_text)

    def test_commands_cover_profile_summary_and_knowledge(self):
        self.runtime.record_turn("我叫小林，我喜欢寿司。", "嗯，我会记住。")
        self.runtime.record_turn("今天有点困。", "那就靠过来休息一下。")
        self.runtime.record_turn("不过项目还是要继续。", "好，我陪着你。")
        self.runtime.record_turn("刚才我去散步了。", "慢一点也没关系。")
        self.runtime.record_turn("你还记得前面说过什么吗？", "记得一些。")
        consolidate_text = self.runtime.handle_command("/consolidate now")
        self.assertIn("记忆整理完成", consolidate_text)

        profile_text = self.runtime.handle_command("/profile show")
        self.assertIsNotNone(profile_text)
        self.assertIn("名字：小林", profile_text)

        summary_text = self.runtime.handle_command("/summary show")
        self.assertIsNotNone(summary_text)
        self.assertIn("当前对话摘要：", summary_text)

        add_result = self.runtime.handle_command("/kg add 制作人 | 当前状态 | 正在测试记忆模块")
        self.assertEqual(add_result, "已添加知识：制作人 - 当前状态 - 正在测试记忆模块")

        kg_text = self.runtime.handle_command("/kg search 当前状态")
        self.assertIsNotNone(kg_text)
        self.assertIn("正在测试记忆模块", kg_text)

        context_text = self.runtime.handle_command("/ctx 寿司")
        self.assertIsNotNone(context_text)
        self.assertIn("【用户画像】", context_text)

    def test_state_fact_supersedes_previous_value(self):
        self.runtime.record_turn("我今天有点累。", "那就先休息一下。")
        self.runtime.record_turn("我现在很开心。", "这样就好。")
        self.runtime.consolidate_pending()

        all_state_facts = self.runtime.knowledge.list_facts(
            subject="制作人",
            tags=["user_state"],
            active_only=False,
        )
        self.assertEqual(len(all_state_facts), 2)

        active_state_facts = self.runtime.knowledge.list_facts(
            subject="制作人",
            tags=["user_state"],
            active_only=True,
        )
        self.assertEqual(len(active_state_facts), 1)
        self.assertEqual(active_state_facts[0]["object"], "很开心")

        inactive_facts = [fact for fact in all_state_facts if not fact.get("active", True)]
        self.assertEqual(len(inactive_facts), 1)
        self.assertIsNotNone(inactive_facts[0].get("valid_to"))

        context_text = self.runtime.build_context("你现在状态怎么样").render()
        self.assertIn("当前状态：很开心", context_text)
        self.assertNotIn("有点累", context_text)

    def test_unrelated_query_does_not_inject_character_knowledge(self):
        self.runtime.record_turn("我叫小林，我喜欢烤肉套餐。", "我会记住。")
        self.runtime.consolidate_pending()
        context_text = self.runtime.build_context("你还记得我喜欢吃什么吗").render()
        self.assertIn("【用户画像】", context_text)
        self.assertIn("喜欢：烤肉套餐", context_text)
        self.assertNotIn("【角色知识】", context_text)

    def test_memory_write_judge_can_refine_rule_plan(self):
        judged_runtime = memory_runtime.MemoryRuntime(
            memory_file=str(Path(self.temp_dir.name) / "judge_memories.json"),
            index_file=str(Path(self.temp_dir.name) / "judge_memories.faiss"),
            profile_file=str(Path(self.temp_dir.name) / "judge_profile.json"),
            state_file=str(Path(self.temp_dir.name) / "judge_state.json"),
            knowledge_file=str(Path(self.temp_dir.name) / "judge_kg.json"),
            assistant_label="美铃",
            memory_write_judge=lambda payload: {
                "profile_candidates": payload["rule_plan"]["profile_candidates"],
                "graph_facts": [
                    {
                        "subject": "制作人",
                        "relation": "当前状态",
                        "object": "有点累",
                        "tags": ["user_state"],
                        "confidence": 0.9,
                        "fact_type": "state",
                    }
                ],
                "episodic_candidates": [
                    {
                        "content": "这周你在推进 LINE 机器人接入。",
                        "tags": ["项目上下文", "judge_added"],
                        "importance": 4,
                        "category": "episodic",
                        "metadata": {"source": "judge"},
                    }
                ],
            },
        )

        judged_runtime.record_turn(
            "我今天有点累，不过这周还在推进 LINE 机器人接入。",
            "我会慢慢陪着你做。",
        )
        judged_runtime.consolidate_pending()

        state_facts = judged_runtime.knowledge.list_facts(
            subject="制作人",
            tags=["user_state"],
            active_only=True,
        )
        self.assertEqual(len(state_facts), 1)
        self.assertEqual(state_facts[0]["object"], "有点累")

        memory_contents = {item["content"] for item in judged_runtime.episodic.list_memories()}
        self.assertIn("这周你在推进 LINE 机器人接入。", memory_contents)
        self.assertNotIn("美铃承诺：我会慢慢陪着你做。", memory_contents)

    def test_consolidation_auto_marks_contradicted_memory(self):
        judged_runtime = memory_runtime.MemoryRuntime(
            memory_file=str(Path(self.temp_dir.name) / "contradiction_memories.json"),
            index_file=str(Path(self.temp_dir.name) / "contradiction_memories.faiss"),
            profile_file=str(Path(self.temp_dir.name) / "contradiction_profile.json"),
            state_file=str(Path(self.temp_dir.name) / "contradiction_state.json"),
            knowledge_file=str(Path(self.temp_dir.name) / "contradiction_kg.json"),
            assistant_label="Misuzu",
            memory_write_judge=lambda payload: {
                "profile_candidates": [],
                "graph_facts": [],
                "episodic_candidates": [
                    {
                        "content": "Correction: I was wrong before. I do not like curry now; I like sushi.",
                        "tags": ["food"],
                        "importance": 4,
                        "confidence": 0.9,
                        "category": "episodic",
                        "metadata": {"evidence": ["turn:2"]},
                    }
                ],
            },
        )
        old_memory = judged_runtime.episodic.add_memory(
            content="The user likes curry.",
            tags=["food"],
            importance=4,
            category="episodic",
            source="conversation",
            metadata={"confidence": 0.86, "evidence": ["turn:1"]},
        )

        judged_runtime.record_turn(
            "Correction: I was wrong before. I do not like curry now; I like sushi.",
            "I will remember that.",
        )
        result = judged_runtime.consolidate_pending()

        memories = judged_runtime.episodic.list_memories()
        old = next(item for item in memories if item["id"] == old_memory["id"])
        new = next(item for item in memories if item["id"] != old_memory["id"])

        self.assertEqual(old["status"], "contradicted")
        self.assertLess(old["confidence"], 0.86)
        self.assertIn(old["id"], new["contradicts"])
        self.assertEqual(result["write_meta"]["auto_contradiction_count"], 1)
        self.assertEqual(result["memory_contradictions"][0]["old_memory_id"], old["id"])

    def test_auto_contradiction_does_not_downgrade_character_canon(self):
        judged_runtime = memory_runtime.MemoryRuntime(
            memory_file=str(Path(self.temp_dir.name) / "canon_contradiction_memories.json"),
            index_file=str(Path(self.temp_dir.name) / "canon_contradiction_memories.faiss"),
            profile_file=str(Path(self.temp_dir.name) / "canon_contradiction_profile.json"),
            state_file=str(Path(self.temp_dir.name) / "canon_contradiction_state.json"),
            knowledge_file=str(Path(self.temp_dir.name) / "canon_contradiction_kg.json"),
            assistant_label="Misuzu",
            memory_write_judge=lambda payload: {
                "profile_candidates": [],
                "graph_facts": [],
                "episodic_candidates": [
                    {
                        "content": "Correction: Misuzu is not an idol anymore.",
                        "tags": ["character"],
                        "importance": 4,
                        "confidence": 0.9,
                        "category": "episodic",
                    }
                ],
            },
        )
        canon_memory = judged_runtime.episodic.add_memory(
            content="Misuzu is an idol.",
            tags=["character"],
            importance=5,
            category="character_fact",
            source="skill",
            metadata={"memory_type": "character_fact", "scope": "character_canon", "confidence": 1.0},
        )

        judged_runtime.record_turn("Correction: Misuzu is not an idol anymore.", "No.")
        result = judged_runtime.consolidate_pending()

        canon = next(item for item in judged_runtime.episodic.list_memories() if item["id"] == canon_memory["id"])
        self.assertEqual(canon["status"], "active")
        self.assertEqual(result["write_meta"]["auto_contradiction_count"], 0)

    def test_reflective_maintenance_creates_relationship_summary(self):
        first = self.runtime.episodic.add_memory(
            content="The user is integrating RoleWeaver with LINE.",
            tags=["project", "line"],
            importance=4,
            category="episodic",
            metadata={"confidence": 0.82},
        )
        second = self.runtime.episodic.add_memory(
            content="The user prefers concise replies during work hours.",
            tags=["preference", "line"],
            importance=4,
            category="preference",
            metadata={"confidence": 0.86, "memory_type": "preference"},
        )
        third = self.runtime.episodic.add_memory(
            content="Misuzu should keep character autonomy even when adapting to LINE.",
            tags=["relationship", "persona"],
            importance=5,
            category="relationship",
            metadata={"confidence": 0.9, "memory_type": "relationship"},
        )

        result = self.runtime.run_memory_maintenance(reason="test_reflection")

        self.assertTrue(result["reflection"]["created"])
        summary = next(
            memory for memory in self.runtime.episodic.list_memories()
            if memory["id"] == result["reflection"]["memory_id"]
        )
        self.assertEqual(summary["memory_type"], "summary")
        self.assertIn("reflection", summary["tags"])
        self.assertIn(first["id"], summary["metadata"]["links"])
        self.assertIn(second["id"], summary["metadata"]["links"])
        self.assertIn(third["id"], summary["metadata"]["links"])

    def test_memory_layers_are_inferred_and_searchable(self):
        preference = self.runtime.episodic.add_memory(
            content="The user prefers concise replies during work hours.",
            tags=["preference"],
            importance=4,
            category="preference",
            metadata={"confidence": 0.9, "memory_type": "preference"},
        )
        summary = self.runtime.episodic.add_memory(
            content="Reflective relationship summary: work-hour replies should stay concise.",
            tags=["reflection"],
            importance=3,
            category="summary",
            source="reflection",
            metadata={"confidence": 0.8, "memory_type": "summary"},
        )

        self.assertEqual(preference["memory_layer"], "long_term")
        self.assertEqual(summary["memory_layer"], "reflection_notes")

        long_hits = self.runtime.episodic.search(
            "work hour concise replies",
            top_k=5,
            min_score=0.01,
            memory_layers=["long_term"],
        )
        reflection_hits = self.runtime.episodic.search(
            "work hour concise replies",
            top_k=5,
            min_score=0.01,
            memory_layers=["reflection_notes"],
        )

        self.assertTrue(any(item["id"] == preference["id"] for item in long_hits))
        self.assertFalse(any(item["id"] == summary["id"] for item in long_hits))
        self.assertTrue(any(item["id"] == summary["id"] for item in reflection_hits))

    def test_memory_os_snapshot_counts_layers_and_contradictions(self):
        old_memory = self.runtime.episodic.add_memory(
            content="The user wants voice replies all day.",
            tags=["voice"],
            category="preference",
            metadata={"memory_type": "preference", "confidence": 0.8},
        )
        self.runtime.episodic.add_memory(
            content="The user wants text replies during work hours.",
            tags=["voice"],
            category="preference",
            metadata={"memory_type": "preference", "contradicts": [old_memory["id"]], "confidence": 0.9},
        )

        snapshot = self.runtime.memory_os_snapshot()

        self.assertGreaterEqual(snapshot["layers"]["long_term"], 2)
        self.assertEqual(snapshot["layers"]["contradiction_graph"], 1)

    def test_context_retrieval_reinforces_used_memories(self):
        memory = self.runtime.episodic.add_memory(
            content="The user prefers concise LINE replies during work hours.",
            tags=["line", "preference"],
            importance=4,
            category="preference",
            metadata={"confidence": 0.82, "memory_type": "preference"},
        )

        context_text = self.runtime.build_context("work hours LINE concise replies").render()
        refreshed = next(item for item in self.runtime.episodic.list_memories() if item["id"] == memory["id"])
        snapshot = self.runtime.memory_os_snapshot()

        self.assertIn("concise LINE replies", context_text)
        self.assertEqual(refreshed["use_count"], 1)
        self.assertIsNotNone(refreshed["last_used_at"])
        self.assertGreater(refreshed["reinforcement_score"], 0.0)
        self.assertEqual(snapshot["reinforcement"]["reinforced_memory_count"], 1)
        self.assertEqual(snapshot["reinforcement"]["total_use_count"], 1)

    def test_new_memory_auto_links_related_active_memories(self):
        first = self.runtime.episodic.add_memory(
            content="The user is integrating RoleWeaver with LINE.",
            tags=["project", "line"],
            importance=4,
            category="episodic",
            metadata={"confidence": 0.82},
        )
        second = self.runtime.episodic.add_memory(
            content="LINE integration should keep concise replies while preserving persona.",
            tags=["project", "line", "persona"],
            importance=4,
            category="relationship",
            metadata={"confidence": 0.86, "memory_type": "relationship"},
        )

        refreshed_first = next(item for item in self.runtime.episodic.list_memories() if item["id"] == first["id"])

        self.assertIn(first["id"], second["links"])
        self.assertIn(second["id"], refreshed_first["links"])
        self.assertIn("auto_link", ";".join(second["evidence"]))
        self.assertEqual(refreshed_first["metadata"]["linked_by"][-1]["memory_id"], second["id"])
        self.assertIn("amem", refreshed_first["metadata"])
        self.assertEqual(refreshed_first["metadata"]["amem"]["evolved_by"][-1], second["id"])
        self.assertIn("current_interpretation", refreshed_first["metadata"]["amem"])
        self.assertEqual(refreshed_first["metadata"]["amem"]["cluster_key"], "episodic::long_term::project")
        self.assertIn("persona", refreshed_first["metadata"]["amem"]["topic_labels"])
        self.assertIn("retrieval_aliases", refreshed_first["metadata"]["amem"])
        self.assertGreater(refreshed_first["metadata"]["amem"]["relationship_strength"], 0.0)
        lifecycle = memory_runtime.memory_lifecycle_view(refreshed_first)
        self.assertEqual(lifecycle["amem_evolution_count"], 1)
        self.assertIn("A-Mem evolution", lifecycle["amem_current_interpretation"])
        self.assertEqual(lifecycle["amem_cluster_key"], "episodic::long_term::project")
        self.assertIn(lifecycle["amem_stability"], {"tentative", "stable"})

    def test_auto_linking_does_not_link_user_memory_to_character_canon(self):
        canon = self.runtime.episodic.add_memory(
            content="Misuzu keeps persona autonomy in LINE.",
            tags=["line", "persona"],
            importance=5,
            category="character_fact",
            source="skill",
            metadata={"confidence": 1.0, "memory_type": "character_fact", "scope": "character_canon"},
        )
        user_memory = self.runtime.episodic.add_memory(
            content="The user is testing LINE persona autonomy.",
            tags=["line", "persona"],
            importance=3,
            category="episodic",
            metadata={"confidence": 0.7},
        )

        refreshed_canon = next(item for item in self.runtime.episodic.list_memories() if item["id"] == canon["id"])

        self.assertNotIn(canon["id"], user_memory["links"])
        self.assertNotIn(user_memory["id"], refreshed_canon["links"])
        self.assertNotIn("amem", refreshed_canon["metadata"])

    def test_memory_maintenance_backfills_amem_evolution_for_existing_links(self):
        old_memory = self.runtime.episodic.add_memory(
            content="The user wants concise LINE replies.",
            tags=["line", "reply"],
            importance=4,
            category="preference",
            metadata={"confidence": 0.8, "memory_type": "preference", "disable_auto_linking": True},
        )
        new_memory = self.runtime.episodic.add_memory(
            content="Concise LINE replies should preserve the role persona.",
            tags=["line", "reply", "persona"],
            importance=4,
            category="relationship",
            metadata={
                "confidence": 0.86,
                "memory_type": "relationship",
                "links": [old_memory["id"]],
                "disable_auto_linking": True,
            },
        )

        result = self.runtime.run_memory_maintenance(reason="test_amem_backfill")
        refreshed_old = next(item for item in self.runtime.episodic.list_memories() if item["id"] == old_memory["id"])
        snapshot = self.runtime.memory_os_snapshot()

        self.assertEqual(result["amem_evolution"]["updated_count"], 1)
        self.assertEqual(refreshed_old["metadata"]["amem"]["evolved_by"], [new_memory["id"]])
        self.assertEqual(snapshot["amem_evolution"]["evolved_memory_count"], 1)
        self.assertEqual(snapshot["amem_evolution"]["evolution_event_count"], 1)
        self.assertEqual(snapshot["amem_evolution"]["top"][0]["cluster_key"], "preference::long_term::line")
        self.assertIn("line", snapshot["amem_evolution"]["top"][0]["topic_labels"])
        self.assertIn(snapshot["amem_evolution"]["top"][0]["stability"], {"tentative", "stable"})

    def test_amem_evolution_is_included_in_search_index_text(self):
        old_memory = self.runtime.episodic.add_memory(
            content="The user prefers short replies.",
            tags=["line"],
            importance=3,
            category="preference",
            metadata={"confidence": 0.8, "memory_type": "preference"},
        )
        new_memory = self.runtime.episodic.add_memory(
            content="Short LINE replies should avoid persona collapse.",
            tags=["line", "persona"],
            importance=4,
            category="relationship",
            metadata={"confidence": 0.86, "memory_type": "relationship", "links": [old_memory["id"]]},
        )
        refreshed_old = next(item for item in self.runtime.episodic.list_memories() if item["id"] == old_memory["id"])

        indexable = self.runtime.episodic._indexable_text(refreshed_old)

        self.assertIn("persona collapse", indexable)
        self.assertIn("retrieval_aliases", refreshed_old["metadata"]["amem"])
        self.assertIn("preference", indexable)
        self.assertIn("line", indexable)
        self.assertIn(str(new_memory["id"]), refreshed_old["metadata"]["amem"]["current_interpretation"])

    def test_reinforcement_bonus_can_raise_frequently_used_memory(self):
        older = self.runtime.episodic.add_memory(
            content="The user prefers quiet short replies.",
            tags=["line"],
            importance=2,
            category="preference",
            metadata={"confidence": 0.62, "memory_type": "preference"},
        )
        newer = self.runtime.episodic.add_memory(
            content="The user prefers quiet short replies with extra notes.",
            tags=["line"],
            importance=5,
            category="preference",
            metadata={"confidence": 0.62, "memory_type": "preference", "disable_auto_linking": True},
        )
        self.runtime.episodic.reinforce_memories([older["id"]], amount=0.8, reason="test_reinforcement")

        results = self.runtime.episodic.search(
            "quiet short replies",
            top_k=2,
            min_score=0.01,
            categories=["preference"],
        )

        self.assertEqual(results[0]["id"], older["id"])
        self.assertGreater(results[0]["_final_score"], results[1]["_final_score"])
        self.assertEqual(newer["id"], results[1]["id"])

    def test_manual_contradiction_review_downgrades_target_memory(self):
        old_memory = self.runtime.episodic.add_memory(
            content="The user wants voice replies all day.",
            tags=["line", "voice"],
            importance=3,
            category="preference",
            metadata={"confidence": 0.8, "memory_type": "preference"},
        )
        self.runtime.episodic.add_memory(
            content="The user wants text replies during work hours unless voice is requested.",
            tags=["line", "voice"],
            importance=4,
            category="preference",
            metadata={"confidence": 0.86, "memory_type": "preference", "contradicts": [old_memory["id"]]},
        )

        result = self.runtime.run_memory_maintenance(reason="test_manual_contradiction")

        old = next(memory for memory in self.runtime.episodic.list_memories() if memory["id"] == old_memory["id"])
        self.assertEqual(old["status"], "contradicted")
        self.assertEqual(result["contradiction_review"]["reviewed_count"], 1)

    def test_decay_archives_old_low_confidence_episodic_but_preserves_stable_memories(self):
        weak = self.runtime.episodic.add_memory(
            content="The user casually mentioned a low-value detail once.",
            tags=["casual"],
            importance=1,
            category="episodic",
            metadata={"confidence": 0.25},
        )
        preference = self.runtime.episodic.add_memory(
            content="The user prefers concise LINE replies.",
            tags=["line"],
            importance=4,
            category="preference",
            metadata={"confidence": 0.88, "memory_type": "preference"},
        )
        canon = self.runtime.episodic.add_memory(
            content="Misuzu is an idol.",
            tags=["character"],
            importance=5,
            category="character_fact",
            source="skill",
            metadata={"confidence": 1.0, "memory_type": "character_fact", "scope": "character_canon"},
        )

        old_ts = memory_runtime.now_ts() - 130 * 86400
        for memory in self.runtime.episodic.memories:
            if memory["id"] in {weak["id"], preference["id"], canon["id"]}:
                memory["timestamp"] = old_ts
        self.runtime.episodic._save_memories()

        result = self.runtime.run_memory_maintenance(reason="test_decay")

        memories = {memory["id"]: memory for memory in self.runtime.episodic.list_memories()}
        self.assertEqual(memories[weak["id"]]["status"], "archived")
        self.assertEqual(memories[preference["id"]]["status"], "active")
        self.assertEqual(memories[canon["id"]]["status"], "active")
        self.assertEqual(result["decay_review"]["updated_count"], 1)

    def test_decay_preserves_reinforced_old_low_confidence_memory(self):
        weak = self.runtime.episodic.add_memory(
            content="The user repeatedly asks for a gentle evening check-in.",
            tags=["line", "evening"],
            importance=1,
            category="episodic",
            metadata={"confidence": 0.25},
        )
        self.runtime.episodic.reinforce_memories([weak["id"]], amount=0.24, reason="test_repeated_use")
        old_ts = memory_runtime.now_ts() - 130 * 86400
        for memory in self.runtime.episodic.memories:
            if memory["id"] == weak["id"]:
                memory["timestamp"] = old_ts
        self.runtime.episodic._save_memories()

        result = self.runtime.run_memory_maintenance(reason="test_reinforced_decay")

        refreshed = next(memory for memory in self.runtime.episodic.list_memories() if memory["id"] == weak["id"])
        self.assertEqual(refreshed["status"], "active")
        self.assertEqual(result["decay_review"]["updated_count"], 0)

    def test_lifecycle_view_explains_reinforced_and_pending_decay(self):
        weak = self.runtime.episodic.add_memory(
            content="The user casually mentioned a low-value detail once.",
            tags=["casual"],
            importance=1,
            category="episodic",
            metadata={"confidence": 0.25},
        )
        old_ts = memory_runtime.now_ts() - 130 * 86400
        for memory in self.runtime.episodic.memories:
            if memory["id"] == weak["id"]:
                memory["timestamp"] = old_ts
        self.runtime.episodic._save_memories()
        stale_view = memory_runtime.memory_lifecycle_view(
            next(memory for memory in self.runtime.episodic.list_memories() if memory["id"] == weak["id"])
        )

        self.assertEqual(stale_view["decay_risk"], "pending")
        self.assertEqual(stale_view["pending_decay"]["status"], "archived")
        self.assertTrue(any("Next maintenance" in item for item in stale_view["explanations"]))

        self.runtime.episodic.reinforce_memories([weak["id"]], amount=0.24, reason="test_repeated_use")
        reinforced_view = memory_runtime.memory_lifecycle_view(
            next(memory for memory in self.runtime.episodic.list_memories() if memory["id"] == weak["id"])
        )

        self.assertTrue(reinforced_view["reinforced"])
        self.assertEqual(reinforced_view["decay_risk"], "low")
        self.assertIsNone(reinforced_view["pending_decay"])

    def test_memory_write_judge_fallbacks_to_rule_plan_on_error(self):
        judged_runtime = memory_runtime.MemoryRuntime(
            memory_file=str(Path(self.temp_dir.name) / "fallback_memories.json"),
            index_file=str(Path(self.temp_dir.name) / "fallback_memories.faiss"),
            profile_file=str(Path(self.temp_dir.name) / "fallback_profile.json"),
            state_file=str(Path(self.temp_dir.name) / "fallback_state.json"),
            knowledge_file=str(Path(self.temp_dir.name) / "fallback_kg.json"),
            assistant_label="美铃",
            memory_write_judge=lambda payload: (_ for _ in ()).throw(RuntimeError("judge failure")),
        )

        judged_runtime.record_turn(
            "我叫小林，我现在在做记忆系统。",
            "我会记住。",
        )
        judged_runtime.consolidate_pending()

        profile_lines = judged_runtime.profile.render_context(max_items_per_slot=5)
        self.assertTrue(any("名字：小林" in line for line in profile_lines))
        memory_contents = {item["content"] for item in judged_runtime.episodic.list_memories()}
        self.assertIn("我叫小林，我现在在做记忆系统。", memory_contents)
        self.assertIn("美铃承诺：我会记住。", memory_contents)

    def test_low_confidence_candidates_are_rejected_by_threshold(self):
        judged_runtime = memory_runtime.MemoryRuntime(
            memory_file=str(Path(self.temp_dir.name) / "threshold_memories.json"),
            index_file=str(Path(self.temp_dir.name) / "threshold_memories.faiss"),
            profile_file=str(Path(self.temp_dir.name) / "threshold_profile.json"),
            state_file=str(Path(self.temp_dir.name) / "threshold_state.json"),
            knowledge_file=str(Path(self.temp_dir.name) / "threshold_kg.json"),
            assistant_label="美铃",
            memory_write_judge=lambda payload: {
                "profile_candidates": [
                    {"slot": "nickname", "value": "阿林", "confidence": 0.31, "reason": "too uncertain"}
                ],
                "graph_facts": [
                    {
                        "subject": "制作人",
                        "relation": "当前状态",
                        "object": "可能有点困",
                        "tags": ["user_state"],
                        "confidence": 0.45,
                        "fact_type": "state",
                        "reason": "ambiguous mood",
                    }
                ],
                "episodic_candidates": [
                    {
                        "content": "你也许提到过想吃寿司。",
                        "tags": ["猜测"],
                        "importance": 2,
                        "confidence": 0.22,
                        "category": "episodic",
                        "metadata": {},
                        "reason": "only weak evidence",
                    }
                ],
            },
        )

        judged_runtime.record_turn("嗯。", "好。")
        judged_runtime.consolidate_pending()

        self.assertEqual(judged_runtime.profile.render_context(max_items_per_slot=5), [])
        self.assertEqual(judged_runtime.knowledge.list_facts(subject="制作人", tags=["user_state"]), [])
        self.assertEqual(judged_runtime.episodic.list_memories(), [])

        rejected = judged_runtime.last_write_plan["rejected_candidates"]
        self.assertEqual(len(rejected), 3)
        self.assertTrue(any(item["reason"] == "too uncertain" for item in rejected))

        plan_text = judged_runtime.handle_command("/writeplan show")
        self.assertIn("被拦截", plan_text)
        self.assertIn("too uncertain", plan_text)

    def test_record_turn_defers_long_term_write_until_consolidation(self):
        self.runtime.record_turn("我叫小林，我喜欢寿司。", "我会记住。")

        self.assertEqual(self.runtime.pending_turns()[-1]["user_text"], "我叫小林，我喜欢寿司。")
        self.assertIn("延迟整理", self.runtime.handle_command("/writeplan show"))
        self.assertIn("待整理", self.runtime.handle_command("/pending show"))
        self.assertEqual(self.runtime.profile.render_context(max_items_per_slot=5), [])

        self.runtime.consolidate_pending()
        self.assertTrue(any("名字：小林" in line for line in self.runtime.profile.render_context(max_items_per_slot=5)))

    def test_reranker_can_reorder_candidate_memories(self):
        self.runtime.episodic.add_memory(
            content="前几天你提过自己偏爱寿司。",
            tags=["episodic", "food"],
            importance=4,
            category="episodic",
        )
        self.runtime.episodic.add_memory(
            content="你反复说过真正最喜欢的是烤肉套餐。",
            tags=["episodic", "food"],
            importance=4,
            category="episodic",
        )
        self.runtime.episodic.reranker = FakeReranker({
            "前几天你提过自己偏爱寿司。": 0.1,
            "你反复说过真正最喜欢的是烤肉套餐。": 5.0,
        })

        results = self.runtime.episodic.search(
            "你还记得我真正最喜欢吃什么吗？",
            top_k=2,
            min_score=0.01,
        )

        self.assertEqual(results[0]["content"], "你反复说过真正最喜欢的是烤肉套餐。")
        self.assertGreater(results[0]["_rerank_score"], results[1]["_rerank_score"])
        self.assertGreater(results[0]["_final_score"], results[1]["_final_score"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
