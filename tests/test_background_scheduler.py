import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from background_scheduler import BackgroundScheduler, BackgroundSchedulerConfig


class FakeClock:
    def __init__(self, value: int):
        self.value = value

    def __call__(self):
        return self.value


class BackgroundSchedulerTestCase(unittest.TestCase):
    def test_idle_and_window_gate_background_jobs(self):
        with TemporaryDirectory() as temp_dir:
            # 2026-04-29 03:00:00 local time in the test environment.
            clock = FakeClock(1777402800)
            scheduler = BackgroundScheduler(
                Path(temp_dir),
                BackgroundSchedulerConfig(
                    enabled=True,
                    allow_llm=False,
                    idle_after_seconds=600,
                    window_start="00:00",
                    window_end="23:59",
                ),
                now_fn=clock,
            )

            scheduler.record_activity("test")
            allowed, reason = scheduler.eligibility()
            self.assertFalse(allowed)
            self.assertIn("waiting for idle", reason)

            clock.value += 700
            allowed, reason = scheduler.eligibility()
            self.assertTrue(allowed, reason)

    def test_llm_jobs_require_explicit_permission(self):
        with TemporaryDirectory() as temp_dir:
            scheduler = BackgroundScheduler(
                Path(temp_dir),
                BackgroundSchedulerConfig(allow_llm=False),
            )

            allowed, reason = scheduler.eligibility(manual=True, requires_llm=True)

            self.assertFalse(allowed)
            self.assertIn("LLM background jobs", reason)

    def test_run_once_persists_completed_job(self):
        with TemporaryDirectory() as temp_dir:
            scheduler = BackgroundScheduler(
                Path(temp_dir),
                BackgroundSchedulerConfig(allow_llm=True),
            )

            job = scheduler.run_once(
                "planning_regenerate",
                lambda item: {"seen": item["job_type"]},
                manual=True,
            )
            status = scheduler.status()

            self.assertEqual(job["status"], "completed")
            self.assertEqual(status["recent_jobs"][-1]["result"]["seen"], "planning_regenerate")


if __name__ == "__main__":
    unittest.main()
