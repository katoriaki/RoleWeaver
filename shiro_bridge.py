from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional


class ShiroBridge:
    """Optional bridge from RoleWeaver to the separate Shiro project.

    The bridge dynamically imports `shiro/src` so RoleWeaver and Shiro can stay
    separate repositories. If the Shiro project is missing or disabled, all
    methods degrade to empty/no-op results.
    """

    def __init__(
        self,
        *,
        enabled: bool,
        root: str,
        identity: str = "白",
        source_path: Optional[str] = None,
    ):
        self.enabled = bool(enabled)
        self.root = Path(root)
        self.identity = identity or "白"
        self.source_path = Path(source_path) if source_path else Path(__file__).resolve().parent / "shiro" / "src"
        self._runtime_cls = None
        self._stimulus_cls = None
        self._last_error = ""

    @property
    def available(self) -> bool:
        return self.enabled and self._load()

    @property
    def last_error(self) -> str:
        return self._last_error

    def _load(self) -> bool:
        if not self.enabled:
            return False
        if self._runtime_cls is not None and self._stimulus_cls is not None:
            return True
        if not self.source_path.exists():
            self._last_error = f"Shiro source path not found: {self.source_path}"
            return False
        try:
            source = str(self.source_path)
            if source not in sys.path:
                sys.path.insert(0, source)
            from shiro import CognitiveRuntime, Stimulus

            self._runtime_cls = CognitiveRuntime
            self._stimulus_cls = Stimulus
            self._last_error = ""
            return True
        except Exception as exc:
            self._last_error = str(exc)
            return False

    def _session_root(self, session_id: str) -> Path:
        safe_session_id = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in (session_id or "default"))
        return self.root / "sessions" / safe_session_id

    def runtime_for_session(self, session_id: str):
        if not self._load():
            return None
        return self._runtime_cls(self._session_root(session_id), identity=self.identity)

    def thought_context(self, session_id: str) -> str:
        runtime = self.runtime_for_session(session_id)
        if runtime is None:
            return ""
        packet = runtime.export_packet()
        return packet.get("thought_context", "")

    def status(self, session_id: str) -> Dict[str, Any]:
        runtime = self.runtime_for_session(session_id)
        if runtime is None:
            return {
                "enabled": self.enabled,
                "available": False,
                "identity": self.identity,
                "root": str(self.root),
                "source_path": str(self.source_path),
                "error": self._last_error,
            }
        data = runtime.status()
        data.update({
            "enabled": self.enabled,
            "available": True,
            "identity": self.identity,
            "scope": "session",
            "session_id": session_id,
        })
        return data

    def observe_text(
        self,
        session_id: str,
        text: str,
        *,
        source: str = "chat",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        runtime = self.runtime_for_session(session_id)
        if runtime is None:
            return {"available": False, "error": self._last_error}
        transition = runtime.observe_text(text, source=source, metadata=metadata or {})
        return {
            "available": True,
            "timestamp": transition.timestamp,
            "source": transition.source,
            "signals": transition.signals,
            "notes": transition.notes,
        }

    def observe_chat_turn(self, session_id: str, user_text: str, assistant_text: str, *, surface: str = "web") -> Dict:
        combined = f"用户输入：{user_text}\n白的回复：{assistant_text}"
        return self.observe_text(
            session_id,
            combined,
            source="chat_turn",
            metadata={
                "surface": surface,
                "user_text": user_text,
                "assistant_text": assistant_text,
            },
        )

    def infer_tool_intentions(
        self,
        session_id: str,
        text: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        runtime = self.runtime_for_session(session_id)
        if runtime is None:
            return {"available": False, "error": self._last_error, "intentions": []}
        intentions = runtime.infer_tool_intentions(text, metadata=metadata or {})
        return {
            "available": True,
            "session_id": session_id,
            "intentions": [item.to_dict() for item in intentions],
        }
