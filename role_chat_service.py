import argparse
import gc
import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from memory_runtime import MemoryRuntime, memory_lifecycle_view, now_ts
from persona_kernel_scorer import PersonaKernelScorer
from planning_runtime import ensure_weekly_schedule, render_planning_context
from anchor_runtime import load_anchor_bank, render_anchor_context, select_anchor
from shiro_bridge import ShiroBridge
from role_config import (
    DEFAULT_IDLE_CONSOLIDATION_SECONDS,
    RoleConfig,
    normalize_idle_consolidation_seconds,
)


def sanitize_session_id(session_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", (session_id or "default").strip())
    return cleaned[:100] or "default"


def _identity_component(value: Optional[str], fallback: str) -> str:
    if not value:
        return fallback
    name = Path(str(value)).name or Path(str(value)).stem or fallback
    cleaned = re.sub(r"[^a-zA-Z0-9_.\-\u4e00-\u9fffぁ-んァ-ン一-龯]+", "_", name)
    return cleaned[:48].strip("._-") or fallback


def _short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:10]


def _read_json_file(path: Path, default):
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _write_json_file(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
        self.memory_root = Path(self.config.session_root)
        self.session_root = self._config_memory_dir()
        self.session_root.mkdir(parents=True, exist_ok=True)

        self._tokenizer = None
        self._processor = None
        self._model = None
        self._vision_generation_enabled = False
        self._omni_generation_enabled = False
        self._init_lock = threading.Lock()
        self._generate_lock = threading.Lock()
        self._runtime_cache: Dict[str, MemoryRuntime] = {}
        self._torch = None
        self._memory_judge_enabled = True
        self._persona_scorer = PersonaKernelScorer.from_skill_file(self.config.skill_file)
        self.last_persona_score: Optional[Dict] = None
        self._anchor_bank = load_anchor_bank(self.config.skill_file)
        self._shiro_bridge = ShiroBridge(
            enabled=self.config.shiro_enabled,
            root=self.config.shiro_root,
            identity=self.config.shiro_identity,
        )
        self.idle_consolidation_seconds = normalize_idle_consolidation_seconds(
            self.config.idle_consolidation_seconds
        )

    def release_model(self):
        """Release loaded model weights so another config can own the GPU."""
        with self._init_lock:
            with self._generate_lock:
                model = self._model
                tokenizer = self._tokenizer
                processor = self._processor
                self._model = None
                self._tokenizer = None
                self._processor = None
                self._vision_generation_enabled = False
                self._omni_generation_enabled = False
                del model
                del tokenizer
                del processor
                gc.collect()
                if self._torch is not None and getattr(self._torch, "cuda", None):
                    try:
                        self._torch.cuda.empty_cache()
                        self._torch.cuda.ipc_collect()
                    except Exception:
                        pass

    def is_model_loaded(self) -> bool:
        return self._model is not None and self._tokenizer is not None

    def preload_model(self) -> None:
        """Load tokenizer, processor, base model, and optional adapter without generating a reply."""
        self._ensure_model_loaded()

    def _config_memory_dir(self) -> Path:
        identity = {
            "base_model_path": self.config.base_model_path or "",
            "lora_path": self.config.lora_path or "",
            "skill_file": self.config.skill_file or "",
            "skill_text": self.config.skill_text or "",
        }
        identity_text = json.dumps(identity, ensure_ascii=False, sort_keys=True)
        base_name = _identity_component(self.config.base_model_path, "base-model")
        lora_name = _identity_component(self.config.lora_path, "base-only")
        skill_name = _identity_component(self.config.skill_file, "inline-skill" if self.config.skill_text else "no-skill")
        folder_name = f"{base_name}__{lora_name}__{skill_name}__{_short_hash(identity_text)}"
        return self.memory_root / sanitize_session_id(folder_name)

    @staticmethod
    def new_session_id() -> str:
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    def _settings_snapshot(self, extra_settings: Optional[Dict] = None) -> Dict:
        snapshot = {
            "role_name": self.config.role_name,
            "base_model_path": self.config.base_model_path or "",
            "lora_path": self.config.lora_path or "",
            "skill_file": self.config.skill_file or "",
            "skill_text": self.config.skill_text or "",
            "quantization_mode": self.config.quantization_mode,
            "device_map_mode": self.config.device_map_mode,
            "model_loader_mode": self.config.model_loader_mode,
            "context_window_tokens": self.config.context_window_tokens,
            "local_location": self.config.local_location,
            "background_jobs_enabled": self.config.background_jobs_enabled,
            "background_llm_enabled": self.config.background_llm_enabled,
            "background_idle_seconds": self.config.background_idle_seconds,
            "background_window_start": self.config.background_window_start,
            "background_window_end": self.config.background_window_end,
            "background_max_minutes": self.config.background_max_minutes,
            "preload_model_on_startup": self.config.preload_model_on_startup,
            "shiro_enabled": self.config.shiro_enabled,
            "shiro_root": self.config.shiro_root,
            "shiro_identity": self.config.shiro_identity,
            "session_root": str(self.memory_root),
        }
        if extra_settings:
            snapshot.update({k: v for k, v in extra_settings.items() if v is not None})
        return snapshot

    def create_session(self, session_id: Optional[str] = None, extra_settings: Optional[Dict] = None) -> Dict:
        session_id = sanitize_session_id(session_id or self.new_session_id())
        original_session_id = session_id
        counter = 2
        while (self.session_root / session_id).exists():
            session_id = sanitize_session_id(f"{original_session_id}-{counter:02d}")
            counter += 1
        path = self._session_dir(session_id)
        created_ts = now_ts()
        display_name = str((extra_settings or {}).get("display_name") or "Untitled chat").strip()[:80] or "Untitled chat"
        snapshot = self._settings_snapshot(extra_settings=extra_settings)
        snapshot["display_name"] = display_name
        self._save_session_meta(
            session_id,
            {
                "session_id": session_id,
                "display_name": display_name,
                "created_ts": created_ts,
                "updated_ts": created_ts,
                "role_mode": self.config.role_mode_default,
                "last_activity_ts": None,
                "memory_scope_path": str(self.session_root),
                "settings_snapshot": snapshot,
            },
        )
        _write_json_file(path / "short_term" / "settings_snapshot.json", snapshot)
        return {
            "session_id": session_id,
            "display_name": display_name,
            "created_ts": created_ts,
            "updated_ts": created_ts,
            "session_path": str(path),
            "memory_scope_path": str(self.session_root),
            "settings_snapshot": snapshot,
        }

    def _ensure_model_loaded(self):
        if self._model is not None and self._tokenizer is not None:
            return

        with self._init_lock:
            if self._model is not None and self._tokenizer is not None:
                return

            try:
                import torch
                from transformers import (
                    AutoModelForCausalLM,
                    AutoProcessor,
                    AutoTokenizer,
                    BitsAndBytesConfig,
                )
                try:
                    from transformers import AutoModelForImageTextToText
                except ImportError:
                    AutoModelForImageTextToText = None
                try:
                    from transformers import Qwen3OmniMoeForConditionalGeneration, Qwen3OmniMoeProcessor
                except ImportError:
                    Qwen3OmniMoeForConditionalGeneration = None
                    Qwen3OmniMoeProcessor = None
            except ModuleNotFoundError as exc:
                missing = exc.name or "unknown"
                raise RuntimeError(
                    "当前 Python 环境缺少运行本地模型所需依赖。\n"
                    f"缺失模块: {missing}\n"
                    f"当前解释器: {os.sys.executable}\n\n"
                    "至少需要：torch transformers accelerate sentence-transformers faiss-cpu；加载 LoRA 时还需要 peft"
                ) from exc

            self._torch = torch

            print("CUDA available:", torch.cuda.is_available())
            if not torch.cuda.is_available():
                raise RuntimeError("没有检测到 CUDA，请确认你是在 GPU 环境下运行。")

            print("Device:", torch.cuda.get_device_name(0))
            model_loader_mode = (self.config.model_loader_mode or "auto").lower()
            print("加载 tokenizer...")
            tokenizer = AutoTokenizer.from_pretrained(
                self.base_model_path,
                trust_remote_code=True,
                use_fast=True,
            )
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            processor = None
            if model_loader_mode == "omni":
                if Qwen3OmniMoeForConditionalGeneration is None or Qwen3OmniMoeProcessor is None:
                    raise RuntimeError(
                        "model_loader_mode=omni requires transformers>=5.2.0 with Qwen3OmniMoeForConditionalGeneration "
                        "and Qwen3OmniMoeProcessor, plus qwen-omni-utils on the A800 server."
                    )
                print("Loading Qwen3-Omni processor...")
                processor = Qwen3OmniMoeProcessor.from_pretrained(
                    self.base_model_path,
                    trust_remote_code=True,
                )
            has_vision_processor = (Path(self.base_model_path) / "preprocessor_config.json").exists()
            if model_loader_mode in {"auto", "vision"} and has_vision_processor:
                try:
                    print("加载 vision processor...")
                    processor = AutoProcessor.from_pretrained(
                        self.base_model_path,
                        trust_remote_code=True,
                        use_fast=True,
                    )
                except Exception as exc:
                    print(f"警告: vision processor 加载失败，图片输入将不可用: {exc}")

            quantization_mode = (self.config.quantization_mode or "4bit").lower()
            device_map_mode = (self.config.device_map_mode or "gpu").lower()
            model_kwargs = {"trust_remote_code": True}
            if device_map_mode == "auto":
                print("设备放置: auto（允许 CPU offload，可能变慢）")
                model_kwargs["device_map"] = "auto"
                model_kwargs["offload_buffers"] = True
            else:
                print("设备放置: gpu（强制放入 CUDA:0，不允许静默 CPU offload）")
                model_kwargs["device_map"] = {"": 0}
            if quantization_mode == "4bit":
                print("加载 4bit base model...")
                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                )
                model_kwargs["torch_dtype"] = torch.float16
            elif quantization_mode == "8bit":
                print("加载 8bit base model...")
                model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
                model_kwargs["torch_dtype"] = torch.float16
            elif quantization_mode == "bf16":
                print("加载 bf16 base model...")
                model_kwargs["torch_dtype"] = torch.bfloat16
            elif quantization_mode == "fp16":
                print("加载 fp16 base model...")
                model_kwargs["torch_dtype"] = torch.float16
            else:
                print("加载 base model without quantization...")

            if model_loader_mode == "omni":
                if "torch_dtype" in model_kwargs:
                    model_kwargs["dtype"] = model_kwargs.pop("torch_dtype")
                else:
                    model_kwargs["dtype"] = "auto"

            if model_loader_mode == "text":
                print("模型加载器: text（强制 AutoModelForCausalLM；适合纯文本 LoRA）")
                vision_generation_enabled = False
                model_loader = AutoModelForCausalLM
                omni_generation_enabled = False
            elif model_loader_mode == "vision":
                if processor is None:
                    raise RuntimeError("model_loader_mode=vision 需要底模目录包含可用的 vision processor。")
                if AutoModelForImageTextToText is None:
                    raise RuntimeError("model_loader_mode=vision 需要当前 transformers 支持 AutoModelForImageTextToText。")
                print("模型加载器: vision（强制 image-text 模型类）")
                vision_generation_enabled = True
                model_loader = AutoModelForImageTextToText
                omni_generation_enabled = False
            elif model_loader_mode == "omni":
                print("Model loader: omni (Qwen3-Omni; text output only by default).")
                vision_generation_enabled = True
                omni_generation_enabled = True
                model_loader = Qwen3OmniMoeForConditionalGeneration
            else:
                print("模型加载器: auto")
                vision_generation_enabled = processor is not None and AutoModelForImageTextToText is not None
                model_loader = AutoModelForImageTextToText if vision_generation_enabled else AutoModelForCausalLM
                omni_generation_enabled = False
            if vision_generation_enabled:
                print("检测到 vision processor，使用 image-text 模型类加载 base model...")
            elif processor is not None:
                print("警告: 当前 transformers 缺少 AutoModelForImageTextToText，图片输入不可用；文本聊天仍可使用。")

            base_model = model_loader.from_pretrained(
                self.base_model_path,
                **model_kwargs,
            )
            device_map = getattr(base_model, "hf_device_map", None)
            if device_map:
                devices = sorted({str(device) for device in device_map.values()})
                print("模型设备分布:", ", ".join(devices))
                if any(device in {"cpu", "disk"} for device in devices):
                    print("警告: 检测到 CPU/disk offload，加载和生成会明显变慢。")

            if self.lora_path:
                try:
                    from peft import PeftConfig, PeftModel, get_peft_model
                except ModuleNotFoundError as exc:
                    raise RuntimeError(
                        "当前配置填写了 LoRA adapter，但 Python 环境缺少 peft。\n"
                        f"当前解释器: {os.sys.executable}\n\n"
                        "请安装：pip install peft"
                    ) from exc
                print("加载 LoRA adapter...")
                if omni_generation_enabled and hasattr(base_model, "thinker"):
                    adapter_dir = Path(self.lora_path)
                    try:
                        peft_config = PeftConfig.from_pretrained(str(adapter_dir))
                        thinker = get_peft_model(base_model.thinker, peft_config)
                        try:
                            from safetensors.torch import load_file as load_safetensors
                        except ModuleNotFoundError as exc:
                            raise RuntimeError("Omni LoRA adapter loading requires safetensors.") from exc
                        adapter_weights = adapter_dir / "adapter_model.safetensors"
                        if not adapter_weights.exists():
                            raise FileNotFoundError(f"Omni LoRA adapter weights not found: {adapter_weights}")
                        raw_state_dict = load_safetensors(str(adapter_weights), device="cpu")
                        state_dict = {}
                        for key, value in raw_state_dict.items():
                            fixed_key = key
                            fixed_key = fixed_key.replace(".lora_A.weight", ".lora_A.default.weight")
                            fixed_key = fixed_key.replace(".lora_B.weight", ".lora_B.default.weight")
                            state_dict[fixed_key] = value
                        load_result = thinker.load_state_dict(state_dict, strict=False)
                        missing = len(getattr(load_result, "missing_keys", []) or [])
                        unexpected = len(getattr(load_result, "unexpected_keys", []) or [])
                        print(f"Loaded Omni thinker LoRA manually: missing={missing}, unexpected={unexpected}")
                        base_model.thinker = thinker
                    except Exception as exc:
                        raise RuntimeError(f"Failed to load Omni thinker LoRA adapter: {self.lora_path}: {exc}") from exc
                    model = base_model
                else:
                    model = PeftModel.from_pretrained(base_model, self.lora_path)
            else:
                print("未配置 LoRA adapter，直接使用 base model。")
                model = base_model
            model.eval()
            if omni_generation_enabled and hasattr(model, "disable_talker"):
                try:
                    model.disable_talker()
                    print("Qwen3-Omni talker disabled; RoleWeaver will request text output and leave voice to GPT-SoVITS.")
                except Exception as exc:
                    print(f"Warning: Qwen3-Omni disable_talker failed; generation will still request return_audio=False: {exc}")

            self._tokenizer = tokenizer
            self._processor = processor
            self._model = model
            self._vision_generation_enabled = vision_generation_enabled
            self._omni_generation_enabled = omni_generation_enabled

    def _session_dir(self, session_id: str) -> Path:
        path = self.session_root / sanitize_session_id(session_id)
        path.mkdir(parents=True, exist_ok=True)
        (path / "short_term").mkdir(exist_ok=True)
        (path / "mid_term").mkdir(exist_ok=True)
        (path / "long_term").mkdir(exist_ok=True)
        (path / "graph").mkdir(exist_ok=True)
        (path / "contradiction_graph").mkdir(exist_ok=True)
        (path / "reflection_notes").mkdir(exist_ok=True)
        return path

    def _meta_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "short_term" / "session_meta.json"

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
        _write_json_file(path, meta)

    def _transcript_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "short_term" / "transcript.jsonl"

    def _score_persona_response(
        self,
        *,
        user_text: str,
        assistant_text: str,
        category: str = "",
        surface: str = "web",
    ) -> Optional[Dict]:
        self.last_persona_score = None
        if self._persona_scorer is None or not self._persona_scorer.available():
            return None
        score = self._persona_scorer.score_response(
            user_text=user_text,
            assistant_text=assistant_text,
            category=category,
            surface=surface,
        ).to_dict()
        self.last_persona_score = score
        return score

    def _append_transcript_turn(
        self,
        session_id: str,
        user_text: str,
        assistant_text: str,
        metadata: Optional[Dict] = None,
    ):
        path = self._transcript_path(session_id)
        record = {
            "timestamp": now_ts(),
            "messages": [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": assistant_text},
            ],
        }
        if metadata:
            record["metadata"] = metadata
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load_session_messages(self, session_id: str, limit: int = 200) -> List[Dict]:
        transcript_path = self._transcript_path(session_id)
        messages = []
        if transcript_path.exists():
            try:
                with transcript_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        item = json.loads(line)
                        messages.extend(item.get("messages", []))
            except Exception:
                messages = []
        if not messages:
            runtime = self._runtime_for_session(session_id)
            messages = runtime.recent_history(max_messages=limit)
        return messages[-limit:]

    def _runtime_for_session(self, session_id: str) -> MemoryRuntime:
        session_id = sanitize_session_id(session_id)
        if session_id in self._runtime_cache:
            return self._runtime_cache[session_id]

        base = self._session_dir(session_id)
        runtime = MemoryRuntime(
            memory_file=str(base / "long_term" / "memories_v2.json"),
            index_file=str(base / "long_term" / "memories_v2.faiss"),
            profile_file=str(base / "graph" / "user_profile_v1.json"),
            state_file=str(base / "short_term" / "memory_state_v1.json"),
            knowledge_file=str(base / "graph" / "knowledge_graph_v1.json"),
            memory_write_judge=self._memory_write_judge,
            user_subject=self.config.user_subject,
            assistant_label=self.config.role_name,
            character_query_keywords=self.config.character_query_keywords,
            character_knowledge_seed=self.config.character_knowledge_seed,
        )
        self._runtime_cache[session_id] = runtime
        return runtime

    def _maybe_empty_cuda_cache_after_generate(self):
        value = os.getenv("ROLEWEAVER_CUDA_EMPTY_CACHE_AFTER_GENERATE", "1").strip().lower()
        if value in {"0", "false", "no", "off"}:
            return
        if self._torch is not None and getattr(self._torch, "cuda", None):
            try:
                self._torch.cuda.empty_cache()
            except Exception:
                pass

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
        parsed = self._extract_json_object(result)
        del inputs, outputs, generated_ids
        self._maybe_empty_cuda_cache_after_generate()
        return parsed

    def consolidate_session_memory(self, session_id: str) -> Dict:
        runtime = self._runtime_for_session(session_id)
        return runtime.consolidate_pending()

    def list_session_memories(
        self,
        session_id: str = "default",
        include_inactive: bool = True,
        status: Optional[str] = None,
        query: Optional[str] = None,
    ) -> List[Dict]:
        runtime = self._runtime_for_session(session_id)
        if query:
            memories = runtime.episodic.search(query, top_k=50, min_score=0.0)
        else:
            memories = runtime.episodic.list_memories()
        if not include_inactive:
            memories = [memory for memory in memories if memory.get("status", "active") == "active"]
        if status:
            memories = [memory for memory in memories if memory.get("status", "active") == status]
        return self._attach_memory_reverse_links(memories, runtime.episodic.list_memories())

    @staticmethod
    def _attach_memory_reverse_links(memories: List[Dict], all_memories: List[Dict]) -> List[Dict]:
        reverse: Dict[int, List[int]] = {}
        for memory in all_memories:
            source_id = int(memory.get("id", 0) or 0)
            for target_id in memory.get("contradicts", []) or []:
                try:
                    target_id = int(target_id)
                except (TypeError, ValueError):
                    continue
                reverse.setdefault(target_id, [])
                if source_id and source_id not in reverse[target_id]:
                    reverse[target_id].append(source_id)
        enriched = []
        for memory in memories:
            item = dict(memory)
            item["contradicted_by"] = reverse.get(int(item.get("id", 0) or 0), [])
            item["lifecycle"] = memory_lifecycle_view(item)
            enriched.append(item)
        return enriched

    def update_session_memory(self, session_id: str, memory_id: int, **updates) -> Optional[Dict]:
        runtime = self._runtime_for_session(session_id)
        memory = runtime.episodic.update_memory(memory_id, **updates)
        if memory is None:
            return None
        return self._attach_memory_reverse_links([memory], runtime.episodic.list_memories())[0]

    def session_memory_os_snapshot(self, session_id: str) -> Dict:
        return self._runtime_for_session(session_id).memory_os_snapshot()

    def delete_session_memory(self, session_id: str, memory_id: int) -> bool:
        runtime = self._runtime_for_session(session_id)
        before = len(runtime.episodic.list_memories())
        runtime.episodic.delete_memory(memory_id)
        return len(runtime.episodic.list_memories()) < before

    def shiro_status(self, session_id: str = "default") -> Dict:
        return self._shiro_bridge.status(session_id)

    def observe_shiro_stimulus(
        self,
        session_id: str,
        text: str,
        *,
        source: str = "manual",
        metadata: Optional[Dict] = None,
    ) -> Dict:
        return self._shiro_bridge.observe_text(session_id, text, source=source, metadata=metadata or {})

    def infer_shiro_tool_intentions(
        self,
        session_id: str,
        text: str,
        *,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        return self._shiro_bridge.infer_tool_intentions(session_id, text, metadata=metadata or {})

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

    def _build_messages(
        self,
        user_text: str,
        role_mode: bool,
        runtime: MemoryRuntime,
        session_id: str,
        max_history_messages: int = 6,
    ):
        base_system = self.config.build_role_system_prompt() if role_mode else self.config.normal_system_prompt
        memory_context = runtime.build_context(user_text).render()
        planning_context = ""
        anchor_context = ""
        shiro_context = ""
        schedule = None
        if role_mode:
            try:
                shiro_context = self._shiro_bridge.thought_context(session_id)
            except Exception as exc:
                shiro_context = f"【Shiro Cognitive Context】\n- unavailable: {exc}"
            try:
                schedule = ensure_weekly_schedule(
                    self._session_dir(session_id).parent,
                    role_name=self.config.role_name,
                    location=self.config.local_location,
                )
                planning_context = render_planning_context(schedule)
            except Exception as exc:
                planning_context = f"【現在時刻と生活状態】\n- planning context unavailable: {exc}"
            try:
                anchor = select_anchor(
                    self._anchor_bank,
                    schedule=schedule,
                    user_text=user_text,
                    session_id=session_id,
                )
                anchor_context = render_anchor_context(anchor)
            except Exception as exc:
                anchor_context = f"【Persona Anchor Replay】\n- anchor context unavailable: {exc}"

        final_system = base_system
        if memory_context:
            final_system += "\n\n" + memory_context
        if shiro_context:
            final_system += "\n\n" + shiro_context
        if planning_context:
            final_system += "\n\n" + planning_context
        if anchor_context:
            final_system += "\n\n" + anchor_context

        messages = []
        if final_system.strip():
            messages.append({"role": "system", "content": final_system.strip()})
        if max_history_messages > 0:
            messages.extend(runtime.recent_history(max_messages=max_history_messages))
        messages.append({"role": "user", "content": user_text})
        return messages

    def _messages_to_prompt_text(self, messages: List[Dict]) -> str:
        if self._omni_generation_enabled and self._processor is not None:
            omni_messages = self._messages_to_omni_messages(messages)
            return self._processor.apply_chat_template(
                omni_messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        try:
            return self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            return self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

    @staticmethod
    def _messages_to_vision_messages(messages: List[Dict], image_path: str, user_text: str) -> List[Dict]:
        vision_messages = []
        last_user_index = -1
        for index, message in enumerate(messages):
            content = message.get("content", "")
            if isinstance(content, list):
                normalized_content = content
            else:
                normalized_content = [{"type": "text", "text": str(content)}]
            vision_messages.append({"role": message.get("role", "user"), "content": normalized_content})
            if message.get("role") == "user":
                last_user_index = index

        multimodal_content = [
            {"type": "image", "image": image_path},
            {"type": "text", "text": user_text},
        ]
        if last_user_index >= 0:
            vision_messages[last_user_index] = {"role": "user", "content": multimodal_content}
        else:
            vision_messages.append({"role": "user", "content": multimodal_content})
        return vision_messages

    @staticmethod
    def _messages_to_omni_messages(messages: List[Dict]) -> List[Dict]:
        omni_messages = []
        for message in messages:
            content = message.get("content", "")
            if isinstance(content, list):
                normalized_content = []
                for item in content:
                    if not isinstance(item, dict):
                        normalized_content.append({"type": "text", "text": str(item)})
                        continue
                    item_type = item.get("type")
                    if item_type == "image":
                        normalized_content.append({"type": "image", "image": item.get("image") or item.get("path") or item.get("url")})
                    elif item_type == "audio":
                        normalized_content.append({"type": "audio", "audio": item.get("audio") or item.get("path") or item.get("url")})
                    elif item_type == "video":
                        normalized_content.append({"type": "video", "video": item.get("video") or item.get("path") or item.get("url")})
                    else:
                        normalized_content.append({"type": "text", "text": str(item.get("text", ""))})
            else:
                normalized_content = [{"type": "text", "text": str(content)}]
            omni_messages.append({"role": message.get("role", "user"), "content": normalized_content})
        return omni_messages

    def _omni_messages_to_inputs(self, messages: List[Dict]):
        if self._processor is None:
            raise RuntimeError("model_loader_mode=omni requires a Qwen3-Omni processor.")
        try:
            from qwen_omni_utils import process_mm_info
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "model_loader_mode=omni requires qwen-omni-utils on the A800 server: pip install -U qwen-omni-utils"
            ) from exc

        omni_messages = self._messages_to_omni_messages(messages)
        text = self._processor.apply_chat_template(
            omni_messages,
            add_generation_prompt=True,
            tokenize=False,
        )
        audios, images, videos = process_mm_info(omni_messages, use_audio_in_video=True)
        inputs = self._processor(
            text=text,
            audio=audios,
            images=images,
            videos=videos,
            return_tensors="pt",
            padding=True,
            use_audio_in_video=True,
        )
        return inputs.to(self._model.device)

    def _decode_generated_text(self, outputs, inputs) -> str:
        if self._omni_generation_enabled:
            text_ids = outputs[0] if isinstance(outputs, tuple) else outputs
            sequences = getattr(text_ids, "sequences", text_ids)
            prompt_len = inputs["input_ids"].shape[1] if "input_ids" in inputs else 0
            decoded = self._processor.batch_decode(
                sequences[:, prompt_len:],
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )
            return decoded[0] if decoded else ""

        generated_ids = outputs[0][inputs["input_ids"].shape[1]:]
        result = self._tokenizer.decode(generated_ids, skip_special_tokens=False)
        del generated_ids
        return result

    def _vision_messages_to_inputs(self, messages: List[Dict], image_path: str):
        if self._omni_generation_enabled:
            return self._omni_messages_to_inputs(messages)
        if self._processor is None:
            raise RuntimeError(
                "当前模型没有可用的 vision processor，无法读取图片。请确认底模目录包含 preprocessor_config.json，"
                "并且模型是 Qwen-VL / Qwen3-VL 这类原生视觉模型。"
            )
        if not self._vision_generation_enabled:
            raise RuntimeError(
                "当前模型是按纯文本模型类加载的，无法接收图片张量。请升级 transformers，"
                "确保环境支持 AutoModelForImageTextToText，然后重启 RoleWeaver。"
            )
        try:
            from PIL import Image
        except ModuleNotFoundError as exc:
            raise RuntimeError("当前 Python 环境缺少 Pillow，无法读取图片。请安装: pip install pillow") from exc

        with Image.open(image_path) as opened_image:
            image = opened_image.convert("RGB")
        try:
            text = self._processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            text = self._processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        return self._processor(text=[text], images=[image], return_tensors="pt").to(self._model.device)

    def _count_prompt_tokens(self, messages: List[Dict]) -> int:
        text = self._messages_to_prompt_text(messages)
        encoded = self._tokenizer(text, add_special_tokens=False)
        return len(encoded.get("input_ids", []))

    def _context_window_tokens(self) -> int:
        configured = int(getattr(self.config, "context_window_tokens", 0) or 0)
        if configured > 0:
            return configured

        candidates = []
        model_config = getattr(self._model, "config", None)
        for attr in ("max_position_embeddings", "seq_length", "n_positions", "model_max_length"):
            value = getattr(model_config, attr, None) if model_config is not None else None
            if isinstance(value, int):
                candidates.append(value)
        tokenizer_limit = getattr(self._tokenizer, "model_max_length", None)
        if isinstance(tokenizer_limit, int):
            candidates.append(tokenizer_limit)

        sane = [value for value in candidates if 1024 <= value <= 262144]
        return min(sane) if sane else 8192

    def _prepare_messages_with_context_budget(
        self,
        user_text: str,
        role_mode: bool,
        runtime: MemoryRuntime,
        session_id: str = "default",
        max_new_tokens: int = 96,
    ) -> List[Dict]:
        context_limit = self._context_window_tokens()
        generation_reserve = max(int(max_new_tokens or 0), 1) + 256
        target_prompt_tokens = int(context_limit * 0.90) - generation_reserve
        if target_prompt_tokens < 128:
            target_prompt_tokens = max(64, int(context_limit * 0.60))

        messages = self._build_messages(
            user_text=user_text,
            role_mode=role_mode,
            runtime=runtime,
            session_id=session_id,
            max_history_messages=6,
        )
        prompt_tokens = self._count_prompt_tokens(messages)
        if prompt_tokens <= target_prompt_tokens:
            return messages

        print(
            "上下文接近上限，开始自动压缩:",
            f"prompt_tokens={prompt_tokens}",
            f"target={target_prompt_tokens}",
            f"window={context_limit}",
        )
        compression_result = runtime.compress_recent_history(
            keep_messages=2,
            reason="near_context_limit",
        )
        if compression_result.get("status") == "compressed":
            print(
                "已压缩旧上下文:",
                f"summaries={compression_result.get('archived_summary_count', 0)}",
                f"kept_messages={compression_result.get('kept_message_count', 0)}",
            )

        for history_messages in (2, 0):
            messages = self._build_messages(
                user_text=user_text,
                role_mode=role_mode,
                runtime=runtime,
                session_id=session_id,
                max_history_messages=history_messages,
            )
            prompt_tokens = self._count_prompt_tokens(messages)
            if prompt_tokens <= target_prompt_tokens:
                return messages

        hard_limit = max(512, context_limit - max(int(max_new_tokens or 0), 1) - 32)
        if prompt_tokens > hard_limit:
            raise RuntimeError(
                "当前 prompt 已超过模型上下文窗口，自动压缩历史后仍无法安全生成。\n"
                f"prompt_tokens={prompt_tokens}, context_window={context_limit}, max_new_tokens={max_new_tokens}\n"
                "请缩短当前输入、降低 max_new_tokens，或精简 SKILL.md / inline skill。"
            )
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

        messages = self._prepare_messages_with_context_budget(
            user_text=user_text,
            role_mode=role_mode,
            runtime=runtime,
            session_id=session_id,
            max_new_tokens=max_new_tokens,
        )
        if self._omni_generation_enabled:
            inputs = self._omni_messages_to_inputs(messages)
        else:
            text = self._messages_to_prompt_text(messages)
            inputs = self._tokenizer(text, return_tensors="pt").to(self._model.device)

        with self._generate_lock:
            with self._torch.no_grad():
                if self._omni_generation_enabled:
                    outputs = self._model.generate(
                        **inputs,
                        max_new_tokens=max_new_tokens,
                        return_audio=False,
                        thinker_return_dict_in_generate=True,
                        use_audio_in_video=True,
                    )
                else:
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

        result = self._decode_generated_text(outputs, inputs)
        result = self.clean_response(result)
        del inputs, outputs
        self._maybe_empty_cuda_cache_after_generate()

        persona_score = self._score_persona_response(
            user_text=user_text,
            assistant_text=result,
            surface="web",
        )
        runtime.record_turn(user_text, result)
        self._shiro_bridge.observe_chat_turn(session_id, user_text, result, surface="web")
        self._append_transcript_turn(
            session_id,
            user_text,
            result,
            metadata={"persona_score": persona_score} if persona_score else None,
        )
        meta["role_mode"] = role_mode
        meta["last_activity_ts"] = int(time.time())
        meta["updated_ts"] = int(time.time())
        if not meta.get("settings_snapshot"):
            meta["settings_snapshot"] = self._settings_snapshot()
        self._save_session_meta(session_id, meta)
        return result

    def chat_once_with_image(
        self,
        user_text: str,
        image_path: str,
        session_id: str = "default",
        max_new_tokens: int = 96,
    ) -> str:
        self._ensure_model_loaded()

        runtime = self._runtime_for_session(session_id)
        meta = self._load_session_meta(session_id)
        self._maybe_consolidate_after_idle(session_id, meta)

        display_user_text = f"[Image: {Path(image_path).name}] {user_text}".strip()
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

        messages = self._prepare_messages_with_context_budget(
            user_text=display_user_text,
            role_mode=role_mode,
            runtime=runtime,
            session_id=session_id,
            max_new_tokens=max_new_tokens,
        )
        vision_messages = self._messages_to_vision_messages(
            messages=messages,
            image_path=image_path,
            user_text=user_text,
        )
        inputs = self._vision_messages_to_inputs(vision_messages, image_path)

        with self._generate_lock:
            with self._torch.no_grad():
                if self._omni_generation_enabled:
                    outputs = self._model.generate(
                        **inputs,
                        max_new_tokens=max_new_tokens,
                        return_audio=False,
                        thinker_return_dict_in_generate=True,
                        use_audio_in_video=True,
                    )
                else:
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

        result = self._decode_generated_text(outputs, inputs)
        result = self.clean_response(result)
        del inputs, outputs
        self._maybe_empty_cuda_cache_after_generate()

        persona_score = self._score_persona_response(
            user_text=display_user_text,
            assistant_text=result,
            surface="image",
        )
        runtime.record_turn(display_user_text, result)
        self._shiro_bridge.observe_chat_turn(session_id, display_user_text, result, surface="image")
        self._append_transcript_turn(
            session_id,
            display_user_text,
            result,
            metadata={"persona_score": persona_score} if persona_score else None,
        )
        meta["role_mode"] = role_mode
        meta["last_activity_ts"] = int(time.time())
        meta["updated_ts"] = int(time.time())
        if not meta.get("settings_snapshot"):
            meta["settings_snapshot"] = self._settings_snapshot()
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
    parser.add_argument(
        "--config",
        default=None,
        help="CSV/TOML/JSON config file. Defaults to roleweaver.config.csv when present.",
    )
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
        config_file=args.config,
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
