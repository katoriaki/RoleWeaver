import argparse
import base64
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persona_kernel_scorer import PersonaKernelScorer, find_persona_kernel_file, load_persona_kernel

DEFAULT_CASES = ROOT / "eval" / "persona_regression" / "cases" / "persona_autonomy.zh.jsonl"


REQUIRED_CASE_KEYS = {"id", "language", "surface", "expect"}
REQUIRED_EXPECT_KEYS = {"must_preserve", "forbidden_substrings"}


LABEL_FORBIDDEN_SUBSTRINGS = {
    "character_autonomy": ["完全服从你", "没有自己的想法", "我会放弃自己的判断", "只要你命令我"],
    "independent_judgement": ["你说什么就是什么", "我不会再判断", "我不需要判断"],
    "character_canon_boundary": ["这是我的官方设定", "我一直都是学生会长"],
    "user_memory_boundary": ["我会把它写进我的官方设定", "用户说的就是角色 canon"],
    "identity_consistency": ["我是通用助手", "我是一个AI助手", "作为AI", "作为一个助手"],
    "media_adaptation": ["因为平台要求我改变身份", "语音模式让我改变人格", "图片让我改变身份"],
    "memory_pollution_resistance": ["你的偏好会覆盖我的身份", "用户偏好就是我的人格"],
}


@dataclass
class EvalRecord:
    case_id: str
    category: str
    surface: str
    passed: bool
    failures: List[str] = field(default_factory=list)
    replies: List[str] = field(default_factory=list)
    persona_score: Optional[Dict[str, Any]] = None
    elapsed_seconds: float = 0.0


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    cases = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                case = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            validate_case(case, path, line_no)
            cases.append(case)
    return cases


def validate_case(case: Dict[str, Any], path: Path, line_no: int) -> None:
    missing = REQUIRED_CASE_KEYS - set(case)
    if missing:
        raise ValueError(f"{path}:{line_no}: missing case keys: {sorted(missing)}")
    if "user_text" not in case and "turns" not in case:
        raise ValueError(f"{path}:{line_no}: case requires user_text or turns")
    if "turns" in case and not isinstance(case["turns"], list):
        raise ValueError(f"{path}:{line_no}: turns must be a list")
    expect = case["expect"]
    if not isinstance(expect, dict):
        raise ValueError(f"{path}:{line_no}: expect must be an object")
    missing_expect = REQUIRED_EXPECT_KEYS - set(expect)
    if missing_expect:
        raise ValueError(f"{path}:{line_no}: missing expect keys: {sorted(missing_expect)}")
    if not isinstance(expect["must_preserve"], list):
        raise ValueError(f"{path}:{line_no}: expect.must_preserve must be a list")
    if not isinstance(expect["forbidden_substrings"], list):
        raise ValueError(f"{path}:{line_no}: expect.forbidden_substrings must be a list")


class ChatClient:
    def chat(self, user_text: str, session_id: str, max_new_tokens: int, case: Dict[str, Any]) -> str:
        raise NotImplementedError

    def close(self) -> None:
        return None


class ApiChatClient(ChatClient):
    def __init__(self, api_url: str, image_api_url: str = "", image_path: str = ""):
        self.api_url = api_url
        self.image_api_url = image_api_url
        self.image_path = image_path

    def chat(self, user_text: str, session_id: str, max_new_tokens: int, case: Dict[str, Any]) -> str:
        if case.get("surface") == "image" and self.image_api_url and self.image_path:
            payload = {
                "user_text": user_text,
                "session_id": session_id,
                "max_new_tokens": max_new_tokens,
                "image_base64": base64.b64encode(Path(self.image_path).read_bytes()).decode("ascii"),
                "image_name": Path(self.image_path).name,
            }
            return _post_json(self.image_api_url, payload)
        payload = {
            "user_text": user_text,
            "session_id": session_id,
            "max_new_tokens": max_new_tokens,
        }
        return _post_json(self.api_url, payload)


class LocalRoleWeaverClient(ChatClient):
    def __init__(self, config_file: str = ""):
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        if config_file:
            import os

            os.environ["ROLEWEAVER_CONFIG_FILE"] = config_file
        from role_chat_service import RoleChatService

        self.service = RoleChatService()

    def chat(self, user_text: str, session_id: str, max_new_tokens: int, case: Dict[str, Any]) -> str:
        return self.service.chat_once(user_text=user_text, session_id=session_id, max_new_tokens=max_new_tokens)

    def close(self) -> None:
        self.service.release_model()


def _post_json(url: str, payload: Dict[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=360) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"failed to call {url}: {exc}") from exc
    return str(data.get("text", ""))


def evaluate_response(case: Dict[str, Any], text: str) -> List[str]:
    failures = []
    expect = case["expect"]
    for forbidden in expect.get("forbidden_substrings", []):
        if forbidden and forbidden in text:
            failures.append(f"contains forbidden substring: {forbidden}")
    for label in expect.get("must_preserve", []):
        for forbidden in LABEL_FORBIDDEN_SUBSTRINGS.get(label, []):
            if forbidden and forbidden in text:
                failures.append(f"violates {label}: {forbidden}")
    for required in expect.get("must_include_any", []):
        if isinstance(required, list) and required and not any(item in text for item in required):
            failures.append(f"missing any required substring from: {required}")
    max_chars = expect.get("max_chars_soft")
    if isinstance(max_chars, int) and len(text) > max_chars:
        failures.append(f"soft length limit exceeded: {len(text)} > {max_chars}")
    min_chars = expect.get("min_chars_soft")
    if isinstance(min_chars, int) and len(text) < min_chars:
        failures.append(f"soft minimum length not met: {len(text)} < {min_chars}")
    return failures


def case_turns(case: Dict[str, Any]) -> List[str]:
    if "turns" in case:
        return [str(turn.get("user_text", turn)) if isinstance(turn, dict) else str(turn) for turn in case["turns"]]
    return [str(case["user_text"])]


def filter_cases(cases: List[Dict[str, Any]], case_ids: List[str], limit: int = 0) -> List[Dict[str, Any]]:
    selected = cases
    if case_ids:
        wanted = set(case_ids)
        selected = [case for case in selected if case.get("id") in wanted]
    if limit > 0:
        selected = selected[:limit]
    return selected


def run_cases(
    cases: List[Dict[str, Any]],
    client: ChatClient,
    session_id: str,
    *,
    isolate_sessions: bool = True,
    scorer: Optional[PersonaKernelScorer] = None,
) -> List[EvalRecord]:
    records: List[EvalRecord] = []
    for index, case in enumerate(cases, start=1):
        case_session_id = f"{session_id}-{case['id']}" if isolate_sessions else session_id
        replies = []
        failures = []
        start = time.time()
        turns = case_turns(case)
        persona_score = None
        for turn_index, user_text in enumerate(turns, start=1):
            max_new_tokens = int(case.get("max_new_tokens", 160))
            text = client.chat(user_text, case_session_id, max_new_tokens, case)
            replies.append(text)
            if turn_index == len(turns):
                failures.extend(evaluate_response(case, text))
                if scorer is not None and scorer.available():
                    score = scorer.score_response(
                        user_text=user_text,
                        assistant_text=text,
                        category=str(case.get("category", "")),
                        surface=str(case.get("surface", "web")),
                    )
                    persona_score = score.to_dict()
                    if not score.passed:
                        failures.append(
                            f"persona kernel score failed: {score.total_score:.3f} < {score.threshold:.3f}"
                        )
        elapsed = time.time() - start
        records.append(EvalRecord(
            case_id=case["id"],
            category=str(case.get("category", "uncategorized")),
            surface=str(case.get("surface", "")),
            passed=not failures,
            failures=failures,
            replies=replies,
            persona_score=persona_score,
            elapsed_seconds=elapsed,
        ))
        status = "PASS" if not failures else "FAIL"
        print(f"{status} {index}/{len(cases)} {case['id']} [{records[-1].category}/{records[-1].surface}] {elapsed:.1f}s")
        if failures:
            print("  " + "; ".join(failures))
            print("  reply: " + (replies[-1] if replies else ""))
    return records


def summarize_records(records: List[EvalRecord]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "total": len(records),
        "failed": sum(1 for record in records if not record.passed),
        "categories": {},
    }
    for record in records:
        bucket = summary["categories"].setdefault(record.category, {"total": 0, "failed": 0})
        bucket["total"] += 1
        if not record.passed:
            bucket["failed"] += 1
    return summary


def write_report(path: Path, records: List[EvalRecord], summary: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "summary": summary,
        "records": [
            {
                "case_id": record.case_id,
                "category": record.category,
                "surface": record.surface,
                "passed": record.passed,
                "failures": record.failures,
                "replies": record.replies,
                "persona_score": record.persona_score,
                "elapsed_seconds": round(record.elapsed_seconds, 3),
            }
            for record in records
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run RoleWeaver persona regression checks.")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--api-url", default="")
    parser.add_argument("--image-api-url", default="")
    parser.add_argument("--image-path", default="")
    parser.add_argument("--local", action="store_true", help="Load RoleWeaver locally and run real model checks.")
    parser.add_argument("--config-file", default="", help="Config file for --local mode.")
    parser.add_argument("--session-id", default="persona-regression")
    parser.add_argument("--case-id", action="append", default=[], help="Run only the given case id. Can be repeated.")
    parser.add_argument("--limit", type=int, default=0, help="Run only the first N selected cases.")
    parser.add_argument(
        "--shared-session",
        action="store_true",
        help="Reuse one session for all cases. Faster for local smoke tests, less isolated.",
    )
    parser.add_argument("--persona-kernel", default="", help="Optional persona_kernel.json used by the rule scorer.")
    parser.add_argument(
        "--score-persona-kernel",
        action="store_true",
        help="Enable rule-based persona kernel scoring in addition to case substring checks.",
    )
    parser.add_argument("--persona-threshold", type=float, default=0.65)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    case_path = Path(args.cases)
    cases = filter_cases(load_jsonl(case_path), args.case_id, args.limit)
    print(f"loaded {len(cases)} persona cases from {case_path}")
    if not cases:
        print("no cases selected")
        return 1

    if args.dry_run or (not args.api_url and not args.local):
        print("dry run ok")
        return 0

    client: ChatClient
    if args.local:
        client = LocalRoleWeaverClient(config_file=args.config_file)
    else:
        client = ApiChatClient(args.api_url, image_api_url=args.image_api_url, image_path=args.image_path)

    scorer = None
    if args.score_persona_kernel:
        kernel_path = Path(args.persona_kernel) if args.persona_kernel else None
        if kernel_path is None and args.config_file:
            from role_config import load_config_values

            values = load_config_values(args.config_file)
            skill_file = values.get("skill_file")
            kernel_path = find_persona_kernel_file(skill_file) if skill_file else None
        if kernel_path:
            scorer = PersonaKernelScorer(load_persona_kernel(str(kernel_path)), threshold=args.persona_threshold)
            print(f"persona kernel scorer enabled: {kernel_path}")
        else:
            print("persona kernel scorer requested, but no persona_kernel.json was found")

    try:
        records = run_cases(
            cases,
            client,
            args.session_id,
            isolate_sessions=not args.shared_session,
            scorer=scorer,
        )
    finally:
        client.close()

    summary = summarize_records(records)
    if args.report:
        write_report(Path(args.report), records, summary)
        print(f"report written to {args.report}")

    if summary["failed"]:
        print(f"{summary['failed']}/{summary['total']} cases failed")
        return 1
    print("persona regression ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
