import json
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


DEFAULT_BACKGROUND_IDLE_SECONDS = 600
DEFAULT_BACKGROUND_WINDOW_START = "02:00"
DEFAULT_BACKGROUND_WINDOW_END = "05:30"
DEFAULT_BACKGROUND_MAX_MINUTES = 20


@dataclass
class BackgroundSchedulerConfig:
    enabled: bool = True
    allow_llm: bool = False
    idle_after_seconds: int = DEFAULT_BACKGROUND_IDLE_SECONDS
    window_start: str = DEFAULT_BACKGROUND_WINDOW_START
    window_end: str = DEFAULT_BACKGROUND_WINDOW_END
    max_job_minutes: int = DEFAULT_BACKGROUND_MAX_MINUTES


def parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "n", "off", "disabled"}:
        return False
    return default


def parse_positive_int(value: Any, default: int, minimum: int = 0) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = int(default)
    return max(minimum, normalized)


def parse_hhmm(value: Any, default: str) -> str:
    text = str(value or "").strip()
    try:
        hour_text, minute_text = text.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (TypeError, ValueError):
        return default
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return default


def _minutes_of_day(value: str) -> int:
    hour_text, minute_text = value.split(":", 1)
    return int(hour_text) * 60 + int(minute_text)


def _inside_window(now: datetime, start: str, end: str) -> bool:
    start_minute = _minutes_of_day(start)
    end_minute = _minutes_of_day(end)
    current = now.hour * 60 + now.minute
    if start_minute == end_minute:
        return True
    if start_minute < end_minute:
        return start_minute <= current < end_minute
    return current >= start_minute or current < end_minute


class BackgroundScheduler:
    """Small persistent scheduler for single-GPU idle work.

    The scheduler does not know how to run RoleWeaver jobs by itself. API.py
    passes a handler for each job, so this module stays independent from model
    loading and FastAPI.
    """

    def __init__(
        self,
        state_dir: Path,
        config: Optional[BackgroundSchedulerConfig] = None,
        now_fn: Optional[Callable[[], float]] = None,
    ):
        self.state_dir = Path(state_dir)
        self.state_path = self.state_dir / "scheduler_state.json"
        self.config = config or BackgroundSchedulerConfig()
        self.now_fn = now_fn or time.time
        self._lock = threading.RLock()
        self._state = self._load_state()

    def update_config(self, config: BackgroundSchedulerConfig) -> None:
        with self._lock:
            self.config = config

    def _now(self) -> int:
        return int(self.now_fn())

    def _load_state(self) -> Dict[str, Any]:
        default = {
            "paused": False,
            "last_activity_ts": int(self.now_fn()),
            "last_activity_surface": "startup",
            "active_job": None,
            "jobs": [],
        }
        try:
            if self.state_path.exists():
                with self.state_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    default.update(data)
        except Exception:
            pass
        return default

    def _save_state(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self.state_path.open("w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)

    def record_activity(self, surface: str = "api") -> None:
        with self._lock:
            self._state["last_activity_ts"] = self._now()
            self._state["last_activity_surface"] = surface
            self._save_state()

    def set_paused(self, paused: bool) -> Dict[str, Any]:
        with self._lock:
            self._state["paused"] = bool(paused)
            self._save_state()
            return self.status()

    def eligibility(self, *, manual: bool = False, requires_llm: bool = False) -> Tuple[bool, str]:
        with self._lock:
            if manual:
                if requires_llm and not self.config.allow_llm:
                    return False, "LLM background jobs are disabled."
                return True, "manual"
            if self._state.get("paused"):
                return False, "scheduler paused"
            if not self.config.enabled:
                return False, "background jobs disabled"
            if requires_llm and not self.config.allow_llm:
                return False, "LLM background jobs are disabled"
            if self._state.get("active_job"):
                return False, "another background job is active"
            idle_seconds = self._now() - int(self._state.get("last_activity_ts") or 0)
            if idle_seconds < self.config.idle_after_seconds:
                return False, f"waiting for idle window: {idle_seconds}s/{self.config.idle_after_seconds}s"
            if not _inside_window(
                datetime.fromtimestamp(self.now_fn()),
                self.config.window_start,
                self.config.window_end,
            ):
                return False, f"outside background window {self.config.window_start}-{self.config.window_end}"
            return True, "eligible"

    def enqueue(
        self,
        job_type: str,
        session_id: str = "",
        payload: Optional[Dict[str, Any]] = None,
        *,
        requires_llm: bool = False,
    ) -> Dict[str, Any]:
        job = {
            "id": f"{int(self.now_fn() * 1000)}-{len(self._state.get('jobs') or []) + 1}",
            "job_type": job_type,
            "session_id": session_id,
            "payload": payload or {},
            "requires_llm": bool(requires_llm),
            "status": "queued",
            "created_ts": self._now(),
            "started_ts": None,
            "finished_ts": None,
            "message": "",
            "result": None,
        }
        with self._lock:
            self._state.setdefault("jobs", []).append(job)
            self._trim_jobs()
            self._save_state()
        return job

    def run_once(
        self,
        job_type: str,
        handler: Callable[[Dict[str, Any]], Dict[str, Any]],
        *,
        session_id: str = "",
        payload: Optional[Dict[str, Any]] = None,
        manual: bool = False,
        requires_llm: bool = False,
    ) -> Dict[str, Any]:
        allowed, reason = self.eligibility(manual=manual, requires_llm=requires_llm)
        if not allowed:
            return {
                "status": "skipped",
                "job_type": job_type,
                "session_id": session_id,
                "reason": reason,
            }

        job = self.enqueue(job_type, session_id=session_id, payload=payload, requires_llm=requires_llm)
        with self._lock:
            job["status"] = "running"
            job["started_ts"] = self._now()
            self._state["active_job"] = job
            self._save_state()

        try:
            result = handler(job)
            job["status"] = "completed"
            job["result"] = result
            job["message"] = "completed"
        except Exception as exc:
            job["status"] = "failed"
            job["message"] = str(exc)
            job["result"] = {"error": str(exc)}
        finally:
            with self._lock:
                job["finished_ts"] = self._now()
                self._state["active_job"] = None
                jobs = self._state.get("jobs") or []
                for index, existing in enumerate(jobs):
                    if existing.get("id") == job.get("id"):
                        jobs[index] = job
                        break
                self._trim_jobs()
                self._save_state()
        return job

    def _trim_jobs(self) -> None:
        jobs = self._state.get("jobs")
        if isinstance(jobs, list) and len(jobs) > 100:
            self._state["jobs"] = jobs[-100:]

    def status(self) -> Dict[str, Any]:
        with self._lock:
            now = self._now()
            idle_seconds = max(0, now - int(self._state.get("last_activity_ts") or now))
            non_llm_allowed, non_llm_reason = self.eligibility(manual=False, requires_llm=False)
            llm_allowed, llm_reason = self.eligibility(manual=False, requires_llm=True)
            jobs: List[Dict[str, Any]] = list(self._state.get("jobs") or [])
            return {
                "config": asdict(self.config),
                "paused": bool(self._state.get("paused")),
                "now_ts": now,
                "last_activity_ts": int(self._state.get("last_activity_ts") or 0),
                "last_activity_surface": self._state.get("last_activity_surface") or "",
                "idle_seconds": idle_seconds,
                "eligible_non_llm": non_llm_allowed,
                "eligible_non_llm_reason": non_llm_reason,
                "eligible_llm": llm_allowed,
                "eligible_llm_reason": llm_reason,
                "active_job": self._state.get("active_job"),
                "recent_jobs": jobs[-20:],
            }
