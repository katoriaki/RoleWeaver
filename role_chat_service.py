import argparse
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Dict, Optional

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from memory_runtime import MemoryRuntime, now_ts
from role_config import (
    DEFAULT_BASE_MODEL_PATH,
    DEFAULT_IDLE_CONSOLIDATION_SECONDS,
    DEFAULT_LORA_PATH,
    DEFAULT_SESSION_ROOT,
    RoleConfig,
    normalize_idle_consolidation_seconds,
)


def sanitize_session_id(session_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", (session_id or "default").strip())
    return cleaned[:100] or "default"


class RoleChatService:
    def __init__(
        self,
        config: Optional[RoleConfig] = None,
        base_model_path: Optional[str] = None,
        lora_path: Optional[str] = None,
        session_root: Optional[str] = None,
        skill_file: Optional[str] = None,
        role_name: Optional[str] = None,
        user_subject: Optional[str] = None,
        system_prompt: Optional[str] = None,
        idle_consolidation_seconds: Optional[int] = None,
    ):
        self.config = config or RoleConfig.from_env(
            base_model_path=base_model_path,
            lora_path=lora_path,
            session_root=session_root,
            skill_file=skill_file,
            role_name=role_name,
            user_subject=user_subject,
            system_prompt=system_prompt,
            idle_consolidation_seconds=idle_consolidation_seconds,
        )
        self.base_model_path = self.config.base_model_path
        self.lora_path = self.config.lora_path
        self.session_root = Path(self.config.session_root)
        self.session_root.mkdir(parents=True, exist_ok=True)

        self._tokenizer = None
        self._model = None
        self._init_lock = threading.Lock()
        self._generate_lock = threading.Lock()
        self._runtime_cache: Dict[str, MemoryRuntime] = {}
        self._torch = None
        self._memory_judge_enabled = True
        self.idle_consolidation_seconds = normalize_idle_consolidation_seconds(
            self.config.idle_consolidation_seconds
        )

    def _ensure_model_loaded(self):
        if self._model is not None and self._tokenizer is not None:
            return

        with self._init_lock:
            if self._model is not None and self._tokenizer is not None:
                return

            try:
                import torch
                from peft import PeftModel
                from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            except ModuleNotFoundError as exc:
                missing = exc.name or "unknown"
                raise RuntimeError(
                    "当前 Python 环境缺少运行本地模型所需依赖。\n"
                    f"缺失模块: {missing}\n"
                    f"当前解释器: {os.sys.executable}\n\n"
                    "至少需要：torch transformers peft accelerate sentence-transformers faiss-cpu"
                ) from exc

            self._torch = torch

            print("CUDA available:", torch.cuda.is_available())
            if not torch.cuda.is_available():
                raise RuntimeError("没有检测到 CUDA，请确认你是在 GPU 环境下运行。")

            print("Device:", torch.cuda.get_device_name(0))
            print("加载 tokenizer...")
            tokenizer = AutoTokenizer.from_pretrained(
                self.base_model_path,
                trust_remote_code=True,
                use_fast=True,
            )
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            print("加载 4bit base model...")
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )
            base_model = AutoModelForCausalLM.from_pretrained(
                self.base_model_path,
                quantization_config=bnb_config,
                device_map="auto",
                torch_dtype=torch.float16,
                trust_remote_code=True,
            )

            print("加载 LoRA adapter...")
            model = PeftModel.from_pretrained(base_model, self.lora_path)
            model.eval()

            self._tokenizer = tokenizer
            self._model = model

    def _session_dir(self, session_id: str) -> Path:
        path = self.session_root / sanitize_session_id(session_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _meta_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "session_meta.json"

    def _load_session_meta(self, session_id: str) -> Dict:
        path = self._meta_path(session_id)
        if not path.exists():
            return {"role_mode": self.config.role_mode_default, "last_activity_ts": None}
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("role_mode", self.config.role_mode_default)
                    data.setdefault("last_activity_ts", None)
                    return data
        except Exception:
            pass
        return {"role_mode": self.config.role_mode_default, "last_activity_ts": None}

    def _save_session_meta(self, session_id: str, meta: Dict):
        path = self._meta_path(session_id)
        with path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    def _runtime_for_session(self, session_id: str) -> MemoryRuntime:
        session_id = sanitize_session_id(session_id)
        if session_id in self._runtime_cache:
            return self._runtime_cache[session_id]

        base = self._session_dir(session_id)
        runtime = MemoryRuntime(
            memory_file=str(base / "memories_v2.json"),
            index_file=str(base / "memories_v2.faiss"),
            profile_file=str(base / "user_profile_v1.json"),
            state_file=str(base / "memory_state_v1.json"),
            knowledge_file=str(base / "knowledge_graph_v1.json"),
            memory_write_judge=self._memory_write_judge,
            user_subject=self.config.user_subject,
            assistant_label=self.config.role_name,
            character_query_keywords=self.config.character_query_keywords,
            character_knowledge_seed=self.config.character_knowledge_seed,
        )
        self._runtime_cache[session_id] = runtime
        return runtime

    @staticmethod
    def _extract_json_object(text: str) -> Optional[Dict]:
        text = (text or "").strip()
        if not text:
            return None
        if "</think>" in text:
            text = text.split("</think>", 1)[1].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < start:
            return None
        snippet = text[start:end + 1]
        try:
            data = json.loads(snippet)
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def _memory_write_judge(self, payload: Dict) -> Optional[Dict]:
        if not self._memory_judge_enabled:
            return None
        if self._model is None or self._tokenizer is None or self._torch is None:
            return None

        pending_turns = payload.get("pending_turns", [])
        if not pending_turns:
            return None

        prompt_payload = {
            "pending_turns": pending_turns,
            "active_facts": payload.get("active_facts", []),
            "rule_plan": payload.get("rule_plan", {}),
        }
        messages = [
            {"role": "system", "content": self.config.memory_judge_system_prompt},
            {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False, indent=2)},
        ]

        try:
            text = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            text = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

        inputs = self._tokenizer(text, return_tensors="pt").to(self._model.device)
        with self._generate_lock:
            with self._torch.no_grad():
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=256,
                    do_sample=False,
                    temperature=0.1,
                    top_p=0.9,
                    repetition_penalty=1.03,
                    pad_token_id=self._tokenizer.pad_token_id,
                    eos_token_id=self._tokenizer.eos_token_id,
                )

        generated_ids = outputs[0][inputs["input_ids"].shape[1]:]
        result = self._tokenizer.decode(generated_ids, skip_special_tokens=False)
        result = self.clean_response(result)
        return self._extract_json_object(result)

    def consolidate_session_memory(self, session_id: str) -> Dict:
        runtime = self._runtime_for_session(session_id)
        return runtime.consolidate_pending()

    def _maybe_consolidate_after_idle(self, session_id: str, meta: Dict):
        last_activity_ts = meta.get("last_activity_ts")
        if not last_activity_ts or self.idle_consolidation_seconds <= 0:
            return
        try:
            last_activity_ts = int(last_activity_ts)
        except Exception:
            return

        runtime = self._runtime_for_session(session_id)
        if not runtime.pending_turns():
            return
        if now_ts() - last_activity_ts >= self.idle_consolidation_seconds:
            runtime.consolidate_pending()

    def should_exit_role(self, user_text: str) -> bool:
        return any(word in user_text for word in self.config.exit_phrases)

    def should_enter_role(self, user_text: str) -> bool:
        return any(word in user_text for word in self.config.enter_phrases)

    @staticmethod
    def clean_response(text: str) -> str:
        if "</think>" in text:
            text = text.split("</think>", 1)[1]
        text = text.replace("<think>", "").replace("</think>", "")
        text = text.replace("<|im_end|>", "")
        text = text.replace("<|endoftext|>", "")
        return text.strip()

    def _build_messages(self, user_text: str, role_mode: bool, runtime: MemoryRuntime):
        base_system = self.config.build_role_system_prompt() if role_mode else self.config.normal_system_prompt
        memory_context = runtime.build_context(user_text).render()

        final_system = base_system
        if memory_context:
            final_system += "\n\n" + memory_context

        messages = [{"role": "system", "content": final_system}]
        messages.extend(runtime.recent_history(max_messages=6))
        messages.append({"role": "user", "content": user_text})
        return messages

    def chat_once(self, user_text: str, session_id: str = "default", max_new_tokens: int = 96) -> str:
        self._ensure_model_loaded()

        runtime = self._runtime_for_session(session_id)
        meta = self._load_session_meta(session_id)
        self._maybe_consolidate_after_idle(session_id, meta)

        cmd_result = runtime.handle_command(user_text)
        if cmd_result is not None:
            meta["last_activity_ts"] = int(time.time())
            self._save_session_meta(session_id, meta)
            return cmd_result
        role_mode = bool(meta.get("role_mode", self.config.role_mode_default))

        if self.should_exit_role(user_text):
            role_mode = False
        elif self.should_enter_role(user_text):
            role_mode = True

        messages = self._build_messages(user_text=user_text, role_mode=role_mode, runtime=runtime)

        try:
            text = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            text = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

        inputs = self._tokenizer(text, return_tensors="pt").to(self._model.device)

        with self._generate_lock:
            with self._torch.no_grad():
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                    temperature=0.72,
                    top_p=0.9,
                    repetition_penalty=1.08,
                    pad_token_id=self._tokenizer.pad_token_id,
                    eos_token_id=self._tokenizer.eos_token_id,
                )

        generated_ids = outputs[0][inputs["input_ids"].shape[1]:]
        result = self._tokenizer.decode(generated_ids, skip_special_tokens=False)
        result = self.clean_response(result)

        runtime.record_turn(user_text, result)
        meta["role_mode"] = role_mode
        meta["last_activity_ts"] = int(time.time())
        self._save_session_meta(session_id, meta)
        return result


def interactive_chat(
    session_id: str = "local-cli",
    max_new_tokens: int = 96,
    idle_consolidation_seconds: int = DEFAULT_IDLE_CONSOLIDATION_SECONDS,
    config: Optional[RoleConfig] = None,
):
    service = RoleChatService(
        config=config,
        idle_consolidation_seconds=idle_consolidation_seconds,
    )

    print("\n" + "=" * 80)
    print("进入本地交互模式。输入 exit 退出程序。")
    print(f"当前角色: {service.config.role_name}")
    print(f"当前 session_id: {session_id}")
    print(f"空闲整理阈值: {service.idle_consolidation_seconds} 秒（0 表示关闭）")
    print("角色模式默认开启。")
    print("记忆命令：/mem list, /profile show, /pending show, /consolidate now, /kg show, /ctx 查询词")
    print("=" * 80)

    while True:
        user_text = input("\n你：").strip()
        if user_text.lower() in ["exit", "quit", "q"]:
            result = service.consolidate_session_memory(session_id)
            if result.get("status") == "consolidated":
                meta = result.get("write_meta", {})
                counts = meta.get("accepted_counts", {})
                print(
                    "退出前已整理记忆："
                    f"画像 {counts.get('profile_candidates', 0)} 条，"
                    f"图谱 {counts.get('graph_facts', 0)} 条，"
                    f"情节 {counts.get('episodic_candidates', 0)} 条。"
                )
            print("已退出。")
            break

        reply = service.chat_once(
            user_text=user_text,
            session_id=session_id,
            max_new_tokens=max_new_tokens,
        )
        print("\n模型：", reply)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RoleWeaver local role chat CLI")
    parser.add_argument("--role-name", default=None, help="Display name for the role")
    parser.add_argument("--user-subject", default=None, help="How memory should name the user")
    parser.add_argument("--base-model-path", default=None, help="Path to the base model")
    parser.add_argument("--lora-path", default=None, help="Path to the trained LoRA adapter")
    parser.add_argument("--skill-file", default=None, help="Optional SKILL.md path used as role reference")
    parser.add_argument("--session-root", default=None, help="Root directory for per-session memory")
    parser.add_argument("--session-id", default="local-cli", help="Conversation session id")
    parser.add_argument("--max-new-tokens", type=int, default=96, help="Max new tokens per reply")
    parser.add_argument(
        "--idle-consolidation-seconds",
        type=int,
        default=DEFAULT_IDLE_CONSOLIDATION_SECONDS,
        help="Idle seconds before auto consolidation on next message; 0 disables it",
    )
    return parser


def main():
    args = build_arg_parser().parse_args()
    config = RoleConfig.from_env(
        role_name=args.role_name,
        user_subject=args.user_subject,
        base_model_path=args.base_model_path,
        lora_path=args.lora_path,
        skill_file=args.skill_file,
        session_root=args.session_root,
        idle_consolidation_seconds=args.idle_consolidation_seconds,
    )
    interactive_chat(
        session_id=args.session_id,
        max_new_tokens=args.max_new_tokens,
        idle_consolidation_seconds=args.idle_consolidation_seconds,
        config=config,
    )


if __name__ == "__main__":
    main()
