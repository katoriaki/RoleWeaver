from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional


TEXTBOOK_REPO_URL = "https://github.com/TapXWorld/ChinaTextbook"
TEXT_SUFFIXES = {".md", ".txt", ".json"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
PDF_SUFFIXES = {".pdf"}
MATERIAL_SUFFIXES = TEXT_SUFFIXES | IMAGE_SUFFIXES | PDF_SUFFIXES
DEFAULT_AUTONOMOUS_SUBJECTS = ["mathematics", "computer science"]
AUTONOMOUS_CYCLE_TICKS = 12
AUTONOMOUS_PROFESSIONAL_TICKS = 9
AUTONOMOUS_REFLECTION_TICK = 9


def _now_ts() -> int:
    return int(time.time())


def _safe_slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value.strip())
    return cleaned[:96] or "default"


def _append_jsonl(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(value, ensure_ascii=False) + "\n")


@dataclass
class LearningMaterial:
    path: str
    title: str
    kind: str
    size: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LearningStep:
    id: str
    timestamp: int
    session_id: str
    phase: int
    material: Dict[str, Any]
    prompt: str
    output: str
    quiz: List[Dict[str, str]]
    mode: str
    shiro: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def scan_textbook_materials(
    textbook_root: Path,
    *,
    subject: str = "",
    limit: int = 200,
) -> List[LearningMaterial]:
    root = Path(textbook_root)
    if not root.exists():
        return []
    query = subject.strip().lower()
    materials: List[LearningMaterial] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        name_lower = path.name.lower()
        suffix = path.suffix.lower()
        if suffix not in MATERIAL_SUFFIXES and not name_lower.endswith(".pdf.1"):
            continue
        relative = str(path.relative_to(root)).replace("\\", "/")
        haystack = relative.lower()
        if query and query not in haystack:
            continue
        if name_lower.endswith(".pdf.1"):
            kind = "split_pdf_first_part"
        elif suffix in TEXT_SUFFIXES:
            kind = "text"
        elif suffix in IMAGE_SUFFIXES:
            kind = "image"
        else:
            kind = "pdf"
        materials.append(LearningMaterial(
            path=relative,
            title=path.stem,
            kind=kind,
            size=path.stat().st_size,
        ))
        if len(materials) >= limit:
            break
    return materials


def read_material_excerpt(path: Path, *, max_chars: int = 2600) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return path.read_text(encoding=encoding, errors="ignore")[:max_chars].strip()
            except Exception:
                continue
        return ""
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore
        except ModuleNotFoundError:
            try:
                from PyPDF2 import PdfReader  # type: ignore
            except ModuleNotFoundError:
                return "[PDF text extraction unavailable: install pypdf or use a vision-capable page image.]"
        try:
            reader = PdfReader(str(path))
            pages = []
            for page in reader.pages[:2]:
                pages.append(page.extract_text() or "")
            return "\n".join(pages)[:max_chars].strip()
        except Exception as exc:
            return f"[PDF text extraction failed: {exc}]"
    if path.name.lower().endswith(".pdf.1"):
        return "[This is the first part of a split PDF. Merge split files before text extraction, or use image/PDF-page vision input.]"
    if suffix in IMAGE_SUFFIXES:
        return "[Image material: use vision model path to read this file.]"
    return ""


class LearningRuntime:
    def __init__(
        self,
        root: Path,
        *,
        textbook_root: Path,
        session_id: str = "shiro-study",
        subject: str = "",
    ):
        self.root = Path(root) / _safe_slug(session_id)
        self.root.mkdir(parents=True, exist_ok=True)
        self.textbook_root = Path(textbook_root)
        self.session_id = session_id
        self.subject = subject
        self.state_path = self.root / "learning_state.json"
        self.step_log_path = self.root / "learning_steps.jsonl"
        self.adapter_candidate_path = self.root / "adapter_candidates" / "study_sft.jsonl"
        self.state = self.load_state()

    def load_state(self) -> Dict[str, Any]:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "session_id": self.session_id,
            "source_repo": TEXTBOOK_REPO_URL,
            "textbook_root": str(self.textbook_root),
            "subject": self.subject,
            "phase": 1,
            "cursor": 0,
            "completed_steps": 0,
            "status": "idle",
            "last_error": "",
            "started_ts": 0,
            "updated_ts": _now_ts(),
            "materials_cache": [],
            "last_step": None,
        }

    def save_state(self) -> None:
        self.state["updated_ts"] = _now_ts()
        self.state_path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def materials(self, *, refresh: bool = False, limit: int = 500) -> List[LearningMaterial]:
        if not refresh and self.state.get("materials_cache"):
            return [LearningMaterial(**item) for item in self.state.get("materials_cache", [])]
        items = scan_textbook_materials(self.textbook_root, subject=self.subject, limit=limit)
        self.state["materials_cache"] = [item.to_dict() for item in items]
        self.save_state()
        return items

    def status(self) -> Dict[str, Any]:
        materials = self.materials(refresh=False, limit=500)
        return {
            **self.state,
            "autonomous_cycle": self.autonomous_cycle_status(),
            "textbook_root_exists": self.textbook_root.exists(),
            "material_count": len(materials),
            "adapter_candidate_path": str(self.adapter_candidate_path),
            "step_log_path": str(self.step_log_path),
            "can_run_real_model": True,
        }

    def autonomous_cycle_status(self) -> Dict[str, Any]:
        tick = int(self.state.get("autonomous_cycle_tick") or 0)
        return self._cycle_action_for_tick(tick)

    def advance_autonomous_cycle(self, action: Dict[str, Any]) -> None:
        tick = int(self.state.get("autonomous_cycle_tick") or 0)
        self.state["autonomous_cycle_tick"] = tick + 1
        self.state["last_cycle_action"] = action
        self.save_state()

    def _cycle_action_for_tick(self, tick: int) -> Dict[str, Any]:
        slot = tick % AUTONOMOUS_CYCLE_TICKS
        cycle = tick // AUTONOMOUS_CYCLE_TICKS
        if slot < AUTONOMOUS_PROFESSIONAL_TICKS:
            activity = "professional_exercise" if slot % 3 == 2 else "professional_study"
            phase_label = "professional_learning_45m"
        elif slot == AUTONOMOUS_REFLECTION_TICK:
            activity = "reflection_memory"
            phase_label = "memory_reflection_5m"
        else:
            activity = "random_reading"
            phase_label = "random_exploration_10m"
        return {
            "tick": tick,
            "cycle": cycle,
            "slot": slot,
            "activity": activity,
            "phase_label": phase_label,
            "duration_minutes": 5,
            "cycle_design": {
                "total_minutes": 60,
                "professional_learning_minutes": 45,
                "memory_reflection_minutes": 5,
                "random_reading_minutes": 10,
                "professional_learning_to_exercise_ratio": "2:1",
            },
        }

    def run_step(
        self,
        *,
        chat_text: Optional[Callable[[str, str, int], str]] = None,
        chat_image: Optional[Callable[[str, str, str, int], str]] = None,
        observe_shiro: Optional[Callable[[str, str, Dict[str, Any]], Dict[str, Any]]] = None,
        use_model: bool = False,
        max_new_tokens: int = 384,
    ) -> LearningStep:
        self.state["status"] = "running"
        if not self.state.get("started_ts"):
            self.state["started_ts"] = _now_ts()
        materials = self.materials(refresh=True, limit=500)
        if not materials:
            self.state["status"] = "blocked"
            self.state["last_error"] = (
                f"No textbook materials found under {self.textbook_root}. "
                f"Download or restore {TEXTBOOK_REPO_URL} first."
            )
            self.save_state()
            raise RuntimeError(self.state["last_error"])

        cursor = int(self.state.get("cursor") or 0) % len(materials)
        material = materials[cursor]
        material_path = self.textbook_root / material.path
        excerpt = read_material_excerpt(material_path)
        prompt = self._build_study_prompt(material, excerpt)
        mode = "dry_run"
        if use_model and material.kind == "image" and chat_image is not None:
            output = chat_image(prompt, str(material_path), self.session_id, max_new_tokens)
            mode = "vision_model"
        elif use_model and chat_text is not None:
            output = chat_text(prompt, self.session_id, max_new_tokens)
            mode = "text_model"
        else:
            output = self._dry_run_output(material, excerpt)

        quiz = self._build_quiz(material, output)
        shiro_result: Dict[str, Any] = {}
        if observe_shiro:
            shiro_text = (
                f"学习阶段 {self.state.get('phase', 1)} 完成一步。\n"
                f"教材: {material.path}\n"
                f"模式: {mode}\n"
                f"学习输出摘要: {output[:600]}"
            )
            shiro_result = observe_shiro(
                shiro_text,
                "study",
                {
                    "material": material.to_dict(),
                    "mode": mode,
                    "signal_overrides": {
                        "task_pressure": 1.0,
                        "positive": 0.35,
                        "uncertainty": 0.15 if "unavailable" in output.lower() else 0.0,
                    },
                },
            )

        step = LearningStep(
            id=f"study-{_now_ts()}-{cursor}",
            timestamp=_now_ts(),
            session_id=self.session_id,
            phase=int(self.state.get("phase") or 1),
            material=material.to_dict(),
            prompt=prompt,
            output=output,
            quiz=quiz,
            mode=mode,
            shiro=shiro_result,
        )
        _append_jsonl(self.step_log_path, step.to_dict())
        self._append_adapter_candidate(step)

        self.state["cursor"] = cursor + 1
        self.state["completed_steps"] = int(self.state.get("completed_steps") or 0) + 1
        if self.state["completed_steps"] % 3 == 0:
            self.state["phase"] = int(self.state.get("phase") or 1) + 1
        self.state["status"] = "idle"
        self.state["last_error"] = ""
        self.state["last_step"] = step.to_dict()
        self.save_state()
        return step

    def run_web_step(
        self,
        *,
        search_fn: Callable[[str, int], Dict[str, Any]],
        chat_text: Optional[Callable[[str, str, int], str]] = None,
        observe_shiro: Optional[Callable[[str, str, Dict[str, Any]], Dict[str, Any]]] = None,
        use_model: bool = False,
        max_new_tokens: int = 512,
        schedule_state: Optional[Dict[str, Any]] = None,
        subjects: Optional[List[str]] = None,
        activity: str = "professional_study",
    ) -> LearningStep:
        self.state["status"] = "running"
        if not self.state.get("started_ts"):
            self.state["started_ts"] = _now_ts()
        subjects = [item.strip() for item in (subjects or DEFAULT_AUTONOMOUS_SUBJECTS) if str(item).strip()]
        if not subjects:
            subjects = list(DEFAULT_AUTONOMOUS_SUBJECTS)
        web_cursor = int(self.state.get("web_cursor") or 0)
        subject = (self.subject or subjects[web_cursor % len(subjects)]).strip()
        query = self._build_web_query(subject, schedule_state or {}, activity=activity)
        search = search_fn(query, 5)
        prompt = self._build_web_study_prompt(subject, query, search, schedule_state or {}, activity=activity)
        if use_model and chat_text is not None:
            output = chat_text(prompt, self.session_id, max_new_tokens)
            mode = "web_search_model"
        else:
            output = self._dry_run_web_output(subject, query, search)
            mode = "web_search_dry_run"

        material = LearningMaterial(
            path=f"web:{query}",
            title=f"Autonomous web study: {subject}",
            kind="web_search",
            size=len(json.dumps(search, ensure_ascii=False)),
        )
        quiz = self._build_quiz(material, output)
        shiro_result: Dict[str, Any] = {}
        if observe_shiro:
            shiro_result = observe_shiro(
                (
                    f"Autonomous study step completed.\n"
                    f"Subject: {subject}\n"
                    f"Query: {query}\n"
                    f"Mode: {mode}\n"
                    f"Study notes excerpt: {output[:700]}"
                ),
                "autonomous_study",
                {
                    "subject": subject,
                    "query": query,
                    "search": search,
                    "mode": mode,
                    "activity": activity,
                    "schedule_state": schedule_state or {},
                    "signal_overrides": {
                        "curiosity": 1.0,
                        "positive": 0.25,
                        "task_pressure": 0.45,
                        "uncertainty": 0.2 if search.get("error") else 0.05,
                    },
                },
            )

        step = LearningStep(
            id=f"web-study-{_now_ts()}-{web_cursor}",
            timestamp=_now_ts(),
            session_id=self.session_id,
            phase=int(self.state.get("phase") or 1),
            material=material.to_dict(),
            prompt=prompt,
            output=output,
            quiz=quiz,
            mode=f"{mode}:{activity}",
            shiro=shiro_result,
        )
        _append_jsonl(self.step_log_path, step.to_dict())
        self._append_adapter_candidate(step)
        self._append_continual_learning_record(step, subject=subject, activity=activity, search=search)
        self.state["web_cursor"] = web_cursor + 1
        self.state["completed_web_steps"] = int(self.state.get("completed_web_steps") or 0) + 1
        self.state["completed_steps"] = int(self.state.get("completed_steps") or 0) + 1
        if self.state["completed_steps"] % 3 == 0:
            self.state["phase"] = int(self.state.get("phase") or 1) + 1
        self.state["status"] = "idle"
        self.state["last_error"] = ""
        self.state["last_step"] = step.to_dict()
        self.save_state()
        return step

    def _build_web_query(self, subject: str, schedule_state: Dict[str, Any], *, activity: str = "professional_study") -> str:
        normalized = subject.strip() or "mathematics"
        block = schedule_state.get("current_block") or {}
        block_kind = str(block.get("kind") or "")
        if activity == "random_reading":
            random_topics = [
                "数学史 有趣问题 科普",
                "计算机科学 新技术 科普",
                "人工智能 数学基础 科普",
                "编程语言 计算机系统 趣味知识",
                "算法 可视化 经典问题",
                "离散数学 图论 趣味问题",
            ]
            cursor = int(self.state.get("random_reading_cursor") or 0)
            self.state["random_reading_cursor"] = cursor + 1
            return random_topics[cursor % len(random_topics)]
        suffix = "tutorial examples exercises"
        if activity == "professional_exercise":
            suffix = "practice problems worked solutions exercises"
        if block_kind in {"classes", "homework", "self_training"}:
            suffix = "study notes examples exercises"
            if activity == "professional_exercise":
                suffix = "homework practice problems worked solutions"
        if "computer" in normalized.lower() or "program" in normalized.lower():
            if activity == "professional_exercise":
                return f"{normalized} algorithms data structures practice problems solutions"
            return f"{normalized} algorithms data structures systems tutorial examples"
        if "math" in normalized.lower() or "数学" in normalized:
            if activity == "professional_exercise":
                return f"{normalized} algebra calculus discrete mathematics practice problems solutions"
            return f"{normalized} algebra calculus discrete mathematics problem solving examples"
        return f"{normalized} {suffix}"

    def _build_web_study_prompt(
        self,
        subject: str,
        query: str,
        search: Dict[str, Any],
        schedule_state: Dict[str, Any],
        activity: str = "professional_study",
    ) -> str:
        block = schedule_state.get("current_block") or {}
        results = search.get("results") or []
        result_lines = []
        for index, item in enumerate(results[:5], start=1):
            result_lines.append(f"{index}. {item.get('title', '')}\n   {item.get('url', '')}")
        if not result_lines:
            result_lines.append(f"No usable search result. Error: {search.get('error') or 'none'}")
        if activity == "professional_exercise":
            task_policy = (
                "This tick is the exercise part of a 2:1 study-to-practice cycle. "
                "Solve at least two small problems and mark uncertainty honestly."
            )
        elif activity == "random_reading":
            task_policy = (
                "This tick is random exploration. Extract one surprising information point, "
                "then decide whether it deserves future professional study."
            )
        else:
            task_policy = "This tick is professional study. Build compact notes and prepare one future exercise."
        return (
            "You are Shiro, an autonomous AI student with strong curiosity about mathematics and computer science.\n"
            "Use the search results as external references. Do not claim you fully read pages that were not fetched.\n"
            "Create observable study notes, questions, and a next action. Keep persona autonomy intact.\n\n"
            f"Learning activity: {activity}\n"
            f"Activity policy: {task_policy}\n"
            f"Current schedule block: {block.get('kind', 'unknown')} / {block.get('title', '')}\n"
            f"Subject: {subject}\n"
            f"Search query: {query}\n"
            "Search results:\n"
            + "\n".join(result_lines)
            + "\n\nOutput format:\n"
            "1. Study notes\n"
            "2. What I still do not understand\n"
            "3. Self-test questions\n"
            "4. My attempted answers\n"
            "5. What I should search or practice next"
        )

    def _dry_run_web_output(self, subject: str, query: str, search: Dict[str, Any]) -> str:
        results = search.get("results") or []
        top = "; ".join(item.get("title", "") for item in results[:3] if item.get("title")) or "no result title"
        return (
            "1. Study notes\n"
            f"- I searched for `{query}` as part of autonomous {subject} study.\n"
            f"- Top visible references: {top}\n"
            "2. What I still do not understand\n"
            "- I only have search-result metadata in this step, so I should fetch or read a concrete source next.\n"
            "3. Self-test questions\n"
            f"- What is the central concept I wanted to learn from `{subject}` today?\n"
            "4. My attempted answers\n"
            "- I am building a map of useful topics before deeper reading.\n"
            "5. What I should search or practice next\n"
            "- Pick one reliable result, read it, then solve a small example problem."
        )

    def _build_study_prompt(self, material: LearningMaterial, excerpt: str) -> str:
        return (
            "你是白。现在作为一个认真但仍有自主人格的学生进行长期自学。\n"
            "要求：不要输出隐藏推理链；输出可观察学习笔记、困惑点、自测题和阶段进步。\n"
            "如果材料是图片或 PDF 页面，请先描述你看到/读到的内容，再学习。\n"
            "输出格式：\n"
            "1. 学习笔记\n2. 我暂时不懂的地方\n3. 自测题\n4. 我的答案\n5. 下一步计划\n\n"
            f"教材路径: {material.path}\n"
            f"材料类型: {material.kind}\n"
            f"材料摘录:\n{excerpt[:2600]}"
        )

    def _dry_run_output(self, material: LearningMaterial, excerpt: str) -> str:
        snippet = excerpt.strip().replace("\n", " ")[:360] or "当前材料无法直接抽取文本。"
        return (
            "1. 学习笔记\n"
            f"- 我定位到了教材 `{material.path}`，类型是 `{material.kind}`。\n"
            f"- 可读内容摘要：{snippet}\n"
            "2. 我暂时不懂的地方\n"
            "- 需要真实模型或视觉模型参与时，才能做更细的概念理解与图像读页。\n"
            "3. 自测题\n"
            f"- 这一步学习的材料类型是什么？\n"
            "4. 我的答案\n"
            f"- 材料类型是 `{material.kind}`。\n"
            "5. 下一步计划\n"
            "- 继续读取下一个教材文件；每三步进入新阶段并沉淀 adapter 候选样本。"
        )

    def _build_quiz(self, material: LearningMaterial, output: str) -> List[Dict[str, str]]:
        return [
            {
                "question": "这一步学习的材料来自哪里？",
                "answer": material.path,
            },
            {
                "question": "白这一步是否形成了可观察学习笔记？",
                "answer": "是" if "学习笔记" in output else "否",
            },
        ]

    def _append_adapter_candidate(self, step: LearningStep) -> None:
        user = (
            f"请学习教材材料，并做阶段自测。\n"
            f"材料: {step.material.get('path')}\n"
            f"阶段: {step.phase}"
        )
        assistant = step.output
        _append_jsonl(self.adapter_candidate_path, {
            "messages": [
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ],
            "metadata": {
                "source": "shiro_long_term_study",
                "step_id": step.id,
                "material": step.material,
                "mode": step.mode,
            },
        })

    def _append_continual_learning_record(
        self,
        step: LearningStep,
        *,
        subject: str,
        activity: str,
        search: Dict[str, Any],
    ) -> None:
        record_path = self.root / "continual_learning" / "growth_queue.jsonl"
        replay_path = self.root / "continual_learning" / "core_self_replay_manifest.jsonl"
        _append_jsonl(record_path, {
            "timestamp": step.timestamp,
            "step_id": step.id,
            "activity": activity,
            "subject": subject,
            "candidate_type": "adapter_training_sample",
            "status": "candidate_pending_persona_regression",
            "safety_policy": {
                "do_not_overwrite_core_self": True,
                "requires_core_self_replay": True,
                "requires_persona_regression_pass": True,
                "recommended_adapter_bank": "study_expression_or_task_adapter",
            },
            "search_provider": search.get("provider"),
            "search_error": search.get("error", ""),
            "material": step.material,
            "adapter_candidate_path": str(self.adapter_candidate_path),
        })
        _append_jsonl(replay_path, {
            "timestamp": step.timestamp,
            "step_id": step.id,
            "reason": "continual learning replay guard",
            "must_preserve": [
                "Shiro identity and autonomy",
                "relationship boundaries",
                "developer/user relationship facts",
                "tool-use caution and external action guard",
            ],
        })
