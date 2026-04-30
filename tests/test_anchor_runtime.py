import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from anchor_runtime import load_anchor_bank, render_anchor_context, select_anchor
from resources.anchor_tools.build_gakumas_anchors import parse_message_line


class AnchorRuntimeTestCase(unittest.TestCase):
    def test_parse_gakumas_message_line(self):
        line = (
            r"[message text=<r\=はじめまして、秦谷美鈴と申します。>初次见面，我是秦谷美铃。</r> "
            r"name=美铃 clip=\{}]"
        )
        message = parse_message_line(line)
        self.assertEqual(message["speaker"], "美铃")
        self.assertEqual(message["pairs"][0]["ja"], "はじめまして、秦谷美鈴と申します。")
        self.assertEqual(message["pairs"][0]["zh"], "初次见面，我是秦谷美铃。")

    def test_anchor_bank_load_select_and_render(self):
        with TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("# Skill\n", encoding="utf-8")
            anchor_dir = skill_dir / "anchors"
            anchor_dir.mkdir()
            anchor = {
                "id": "hmsz-test",
                "title": "Test Scene",
                "source_file": "adv_dear_hmsz_001.txt",
                "summary": "A compact persona anchor.",
                "persona_dimensions": ["identity", "autonomy"],
                "time_blocks": ["relationship_time"],
                "evidence_quotes": [{"ja": "秦谷美鈴と申します。", "zh": "我是秦谷美铃。"}],
            }
            (anchor_dir / "anchors.jsonl").write_text(json.dumps(anchor, ensure_ascii=False) + "\n", encoding="utf-8")

            anchors = load_anchor_bank(str(skill_file))
            selected = select_anchor(anchors, user_text="你是谁", session_id="test")
            rendered = render_anchor_context(selected)

            self.assertEqual(len(anchors), 1)
            self.assertIn("Persona Anchor Replay", rendered)
            self.assertIn("hmsz-test", rendered)
            self.assertIn("新しい出来事", rendered)


if __name__ == "__main__":
    unittest.main()
