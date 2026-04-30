import csv
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from API import create_app
import planning_runtime
from planning_runtime import ensure_weekly_schedule, render_planning_context, web_search


class PlanningRuntimeTestCase(unittest.TestCase):
    def test_weekly_schedule_is_stable_per_scope_and_has_context(self):
        with TemporaryDirectory() as temp_dir:
            scope = Path(temp_dir) / "memory_scope"
            first = ensure_weekly_schedule(scope, role_name="Hataya Misuzu", location="Tokyo, Japan", force=True)
            second = ensure_weekly_schedule(scope, role_name="Hataya Misuzu", location="Tokyo, Japan", force=False)

            self.assertEqual(first["week_start"], second["week_start"])
            self.assertEqual(len(first["days"]), 7)
            rendered = render_planning_context(first)
            self.assertIn("week_start", rendered)
            self.assertIn("planning context", rendered)

    def test_planning_api_for_session(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "roleweaver.config.csv"
            skill_dir = temp_path / "role"
            skill_dir.mkdir()
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("# Role\n", encoding="utf-8")
            anchor_dir = skill_dir / "anchors"
            anchor_dir.mkdir()
            anchor = {
                "id": "anchor-api-test",
                "title": "API Anchor",
                "summary": "Planning API anchor.",
                "persona_dimensions": ["identity"],
                "time_blocks": ["relationship_time"],
            }
            (anchor_dir / "anchors.jsonl").write_text(json.dumps(anchor, ensure_ascii=False) + "\n", encoding="utf-8")
            with config_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["key", "value"])
                writer.writerow(["base_model_path", str(temp_path / "model")])
                writer.writerow(["skill_file", str(skill_file)])
                writer.writerow(["session_root", str(temp_path / "memory")])

            client = TestClient(create_app(config_file=str(config_path)))
            created = client.post("/sessions").json()
            session_id = created["session_id"]

            response = client.get(f"/planning/{session_id}")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(len(data["schedule"]["days"]), 7)
            self.assertIn("current_context", data)
            self.assertEqual(data["current_anchor"]["id"], "anchor-api-test")
            self.assertTrue(data["sources"])

            regenerated = client.post(f"/planning/{session_id}/regenerate")
            self.assertEqual(regenerated.status_code, 200)

    def test_web_search_auto_prefers_china_friendly_provider(self):
        calls = []

        def fake_fetch(url, timeout):
            calls.append(url)
            if "cn.bing.com" in url:
                return '<li class="b_algo"><h2><a href="https://example.test/math">数学教程</a></h2></li>'
            raise AssertionError(f"unexpected url: {url}")

        original_fetch = planning_runtime._fetch_search_page
        try:
            planning_runtime._fetch_search_page = fake_fetch
            result = web_search("离散数学 教程", limit=3, provider="auto")
        finally:
            planning_runtime._fetch_search_page = original_fetch

        self.assertEqual(result["provider"], "bing_cn")
        self.assertEqual(result["results"][0]["title"], "数学教程")
        self.assertTrue(calls and "cn.bing.com" in calls[0])

    def test_web_search_auto_falls_back_to_baidu(self):
        calls = []

        def fake_fetch(url, timeout):
            calls.append(url)
            if "cn.bing.com" in url:
                return "<html></html>"
            if "baidu.com" in url:
                return '<h3 class="t"><a href="https://example.test/cs">计算机学习</a></h3>'
            raise AssertionError(f"unexpected url: {url}")

        original_fetch = planning_runtime._fetch_search_page
        try:
            planning_runtime._fetch_search_page = fake_fetch
            result = web_search("计算机系统", limit=3, provider="auto")
        finally:
            planning_runtime._fetch_search_page = original_fetch

        self.assertEqual(result["provider"], "baidu")
        self.assertEqual(result["results"][0]["title"], "计算机学习")
        self.assertTrue(any("baidu.com" in url for url in calls))


if __name__ == "__main__":
    unittest.main()
