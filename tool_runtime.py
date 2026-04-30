import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class ToolRuntimeError(Exception):
    pass


@dataclass
class ToolContext:
    session_id: str = "web"
    actor: str = "user"
    action_id: str = ""


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    mutates: bool = False
    requires_session: bool = False
    requires_llm: bool = False
    category: str = "runtime"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "mutates": self.mutates,
            "requires_session": self.requires_session,
            "requires_llm": self.requires_llm,
            "category": self.category,
        }


ToolHandler = Callable[[Dict[str, Any], ToolContext], Any]


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_json_safe(item) for item in value]
        return str(value)


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True


class ToolRuntime:
    """Small, auditable registry for RoleWeaver tools.

    The registry is deliberately boring: all tools are registered in-process,
    arguments are checked against a small JSON-schema-like shape, and every
    call is appended to a JSONL action log.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.action_log_path = self.root / "actions.jsonl"
        self._tools: Dict[str, ToolSpec] = {}
        self._handlers: Dict[str, ToolHandler] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        if not spec.name or "." not in spec.name:
            raise ValueError("Tool names should use a namespace, such as memory.search.")
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec
        self._handlers[spec.name] = handler

    def list_tools(self) -> List[Dict[str, Any]]:
        return [self._tools[name].to_dict() for name in sorted(self._tools)]

    def recent_actions(self, limit: int = 50) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit or 50), 200))
        if not self.action_log_path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        with self.action_log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows[-limit:]

    def run(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        *,
        session_id: str = "web",
        actor: str = "user",
    ) -> Dict[str, Any]:
        name = (tool_name or "").strip()
        if name not in self._tools:
            raise ToolRuntimeError(f"Unknown tool: {name}")
        args = arguments or {}
        if not isinstance(args, dict):
            raise ToolRuntimeError("Tool arguments must be an object.")
        spec = self._tools[name]
        self._validate_args(spec, args)

        action_id = uuid.uuid4().hex[:16]
        context = ToolContext(session_id=session_id or "web", actor=actor or "user", action_id=action_id)
        started = time.time()
        base = {
            "id": action_id,
            "tool_name": name,
            "session_id": context.session_id,
            "actor": context.actor,
            "created_at": _now_iso(),
            "arguments": _json_safe(args),
            "mutates": spec.mutates,
            "requires_llm": spec.requires_llm,
        }
        try:
            result = self._handlers[name](dict(args), context)
            record = {
                **base,
                "status": "completed",
                "duration_ms": int((time.time() - started) * 1000),
                "result": _json_safe(result),
            }
        except Exception as exc:
            record = {
                **base,
                "status": "failed",
                "duration_ms": int((time.time() - started) * 1000),
                "error": str(exc),
            }
            self._append_action(record)
            if isinstance(exc, ToolRuntimeError):
                raise
            raise ToolRuntimeError(str(exc)) from exc

        self._append_action(record)
        return record

    def _append_action(self, record: Dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.action_log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(_json_safe(record), ensure_ascii=False) + "\n")

    def _validate_args(self, spec: ToolSpec, args: Dict[str, Any]) -> None:
        schema = spec.parameters or {}
        properties = schema.get("properties") or {}
        required = schema.get("required") or []
        for key in required:
            if key not in args or args.get(key) in (None, ""):
                raise ToolRuntimeError(f"Missing required argument: {key}")
        if schema.get("additionalProperties") is False:
            extras = sorted(set(args) - set(properties))
            if extras:
                raise ToolRuntimeError(f"Unexpected argument(s): {', '.join(extras)}")
        for key, value in args.items():
            expected = (properties.get(key) or {}).get("type")
            if expected and value is not None and not _type_matches(value, expected):
                raise ToolRuntimeError(f"Argument {key} must be {expected}.")
