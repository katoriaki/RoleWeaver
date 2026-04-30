import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from persona_anchor_runtime import PersonaAnchorForge, promote_candidate_to_anchor


WORKSPACE_TMP = Path(__file__).resolve().parents[1] / ".codex_tmp" / "test_persona_anchor_runtime"
WORKSPACE_TMP.mkdir(parents=True, exist_ok=True)


class LocalTempDir:
    def __enter__(self):
        self.path = WORKSPACE_TMP / uuid.uuid4().hex
        self.path.mkdir(parents=True, exist_ok=True)
        return str(self.path)

    def __exit__(self, exc_type, exc, tb):
        shutil.rmtree(self.path, ignore_errors=True)


class PersonaAnchorRuntimeTestCase(unittest.TestCase):
    def test_forge_candidate_from_schedule_scene(self):
        with LocalTempDir() as temp_dir:
            forge = PersonaAnchorForge(Path(temp_dir))
            replies = [
                "我是白。课堂上我会先发呆一下，但还是想把新概念弄懂。",
                "如果太难，我会慢慢拆开来学，不想变成只会给答案的普通助手。",
                "未来的我应该记住：不懂也可以继续学，这也是我的一部分。",
            ]

            def chat_text(prompt, session_id, max_new_tokens):
                self.assertIn("白", prompt)
                self.assertTrue(session_id.endswith("persona-anchor-forge"))
                return replies.pop(0)

            candidate = forge.run_persona_dialogue(
                session_id="main",
                schedule_state={"current_block": {"kind": "classes", "title": "class time"}},
                chat_text=chat_text,
                turns=3,
            )

            self.assertEqual(candidate.status, "candidate")
            self.assertIn("curiosity", candidate.persona_dimensions)
            self.assertGreaterEqual(candidate.confidence, 0.5)
            self.assertTrue(forge.candidates_path("main").exists())
            self.assertEqual(len(forge.list_candidates("main")), 1)

    def test_promote_candidate_to_skill_anchor_file(self):
        with LocalTempDir() as temp_dir:
            skill_file = Path(temp_dir) / "SKILL.md"
            skill_file.write_text("# skill\n", encoding="utf-8")
            candidate = {
                "id": "shiro-pdialogue-test",
                "title": "Persona-directed dialogue: class",
                "summary": "白在课堂中保持求知欲。",
                "persona_dimensions": ["identity", "curiosity"],
                "scene": {"kind": "classes"},
                "tags": ["persona_directed_dialogue"],
                "confidence": 0.8,
                "evidence_quotes": [{"zh": "不懂也可以继续学。"}],
            }

            anchor_path = promote_candidate_to_anchor(candidate, str(skill_file))
            anchors = [json.loads(line) for line in anchor_path.read_text(encoding="utf-8").splitlines()]

            self.assertEqual(anchor_path.name, "anchors.jsonl")
            self.assertEqual(anchors[0]["id"], "shiro-pdialogue-test")
            self.assertIn("classes", anchors[0]["time_blocks"])


if __name__ == "__main__":
    unittest.main()
