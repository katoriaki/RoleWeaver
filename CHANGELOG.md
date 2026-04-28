# Changelog

## 2026-04-28

### Project Runtime Environment

- Added `setup_runtime.bat` to create and refresh a project-local `runtime/` virtual environment.
- Installed RoleWeaver dependencies into `runtime/`, including CUDA 12.8 PyTorch for local NVIDIA GPUs.
- Updated `start_roleweaver.bat` and `line/start_line_bot.bat` to prefer `runtime\Scripts\python.exe`.
- Ignored `runtime/` so the local environment is not committed to Git.

### Memory OS Milestone

- Added session memory management APIs:
  - `GET /sessions/{session_id}/memories`
  - `PATCH /sessions/{session_id}/memories/{memory_id}`
  - `DELETE /sessions/{session_id}/memories/{memory_id}`
- Added Web UI Memory manager under the More menu.
- Added memory status transitions: `active`, `stale`, `contradicted`, `archived`, `deleted`.
- Added memory edit fields for reason, evidence, outgoing contradiction links, and incoming `contradicted_by` visualization.
- Changed memory retrieval so non-active memories are excluded from search/context recall.
- Added tests for memory status updates and API memory management.
- Added M4.3 automatic contradiction detection during deferred memory consolidation:
  - new correction-like memories can automatically link to older active memories through `contradicts`
  - older linked memories are marked `contradicted` instead of being deleted
  - auto-detected links write evidence and reason traces for human review
  - character canon and skill/reference memories are protected from automatic downgrades
- Added M4.4 reflective memory maintenance:
  - memory consolidation can now create higher-level relationship summaries from several durable memories
  - reflection summaries store source memory ids through `links` and `evidence`
  - manual contradiction links are reviewed and can downgrade older active targets to `contradicted`
- Added M4.5 forgetting and validity maintenance:
  - expired memories become `stale`
  - old, low-confidence, low-importance episodic details can be archived
  - weak old preferences can become stale while stable preferences remain active
  - character canon, skill, and imported-reference memories are protected from automatic forgetting
- Added M5.1 true-model persona regression:
  - `eval/persona_regression/run_persona_eval.py` can now run against a live API or load RoleWeaver locally with `--local`
  - default cases cover identity consistency, boundary consistency, long-dialogue drift, media adaptation, and memory pollution
  - multi-turn cases are supported for drift testing
  - JSON reports can be written with `--report`
  - added `eval/persona_regression/run_local_persona_eval.bat` as a one-click local evaluator
- Added `model_loader_mode` configuration:
  - `text` forces `AutoModelForCausalLM`, matching LoRA adapters trained by the bundled SFT script
  - `vision` forces image-text loading for multimodal use
  - `auto` keeps the previous processor-detection behavior
  - the current local RoleWeaver and LINE configs use `text` so the 4B HMSZ LoRA no longer attaches to the VLM wrapper
- Added M5.2 persona kernel rule scoring:
  - new `persona_kernel_scorer.py` scores identity, autonomy, generic-assistant flattening, memory-boundary pollution, and media adaptation
  - chat transcripts store persona score metadata when a `persona_kernel.json` is available
  - API responses can include `persona_score`, and `POST /persona/score` can score arbitrary replies
  - persona regression supports `--score-persona-kernel`, `--persona-kernel`, and `--persona-threshold`
- Added M4.6 Memory OS layering:
  - new `memory_layer` field: `short_term`, `mid_term`, `long_term`, `graph`, `contradiction_graph`, `reflection_notes`
  - old memory records are assigned a layer on load; new writes infer layer from type/source/tags
  - retrieval now separates mid-term summaries, durable long-term memories, reflection notes, graph facts, and contradiction hints
  - added `GET /sessions/{session_id}/memory-os` for layer/status counts

### Design Principles and Research Roadmap

- Added `docs/DESIGN_PRINCIPLES.md` as the project-level design contract.
- Added `docs/PERSONA_KERNEL_SCHEMA.md` and `docs/persona_kernel.schema.json` as the first structured persona kernel specification.
- Added `docs/MEMORY_ITEM_SCHEMA.md` and `docs/memory_item.schema.json` as the target memory metadata contract.
- Added `eval/persona_regression/` with a lightweight JSONL-based persona regression harness.
- Backfilled the runtime memory store so newly written memories carry schema, type, scope, evidence, confidence, status, and validity metadata while old memories remain readable.
- Updated skill loading so `SKILL.md` automatically includes a nearby `persona_kernel.json` or `references/persona_kernel.json` when present.
- Defined the core priority order:
  - character autonomy
  - persona consistency
  - long-term relationship memory
  - current task completion
  - output length, voice, image, and platform formatting
- Clarified that Web, LINE, TTS, and image prompts are media adaptation layers and must not override the persona kernel.
- Introduced the next design roadmap:
  - persona kernel schema
  - memory metadata with evidence, confidence, source, validity, and status
  - reflective memory write-manage-read loop
  - persona regression evaluation
  - media-safe adaptation tests
- Linked the design principles from the English, Chinese, and Japanese README files.

## 2026-04-27

### LINE Bot Voice and Wake-Up Push

- Added a one-click LINE bot launcher under `line/start_line_bot.bat`.
- Added `line/run_line_bot.py` so the LINE service can be started from the project root without Python import path issues.
- Added a LINE-specific config file, `line/roleweaver.line.config.csv`, for the current 4B base model, LoRA checkpoint, and Misuzu `SKILL.md`.
- Added built-in LINE commands:
  - `/ping`
  - `/help`
  - `/status`
  - `/wake on`
  - `/wake off`
- Added persistent LINE contact registration for daily wake-up pushes.
- Added configurable 07:00 wake-up push support through `ROLEWEAVER_WAKEUP_*` environment variables.
- Added optional voice-first LINE replies through `ROLEWEAVER_REPLY_VOICE=1`.
- Added LINE audio file serving under `/audio/{filename}` for generated voice replies.
- Added local GPT-SoVITS startup helpers under `G/start_roleweaver_tts_api.*`.
- Added safer TTS reference path handling, including compatibility with accidental `r"C:\..."` dotenv values.
- Added fallback-to-text behavior when TTS generation, audio conversion, or public audio URL setup fails.

### Skill Loading and GPU Runtime Stability

- Added single-file `SKILL.md` loading support:
  - users only need to provide one `SKILL.md` path in Settings
  - nearby `references/*.md` files are loaded automatically when present
  - standalone `SKILL.md` files still work without sidecar references
- Added regression tests for bundled skill loading:
  - single-file skill loading
  - `SKILL.md` plus `references/role_reference.md` loading
- Added `device_map_mode` configuration:
  - `gpu` is now the default and forces CUDA placement
  - `auto` remains available for CPU offload fallback
  - the web Settings panel exposes this as "Device placement"
- Changed model loading to print the selected placement mode and warn when CPU/disk offload is detected.
- Fixed a model-switching cache issue where old `RoleChatService` instances could keep model weights on GPU while a new model was loading.
  - switching settings or loading a session with a different snapshot now releases inactive model weights
  - release calls clear model/tokenizer references and run CUDA cache cleanup
- Updated config examples and UI copy to explain automatic reference loading and GPU-only placement.
- Ignored local `.tmp_tests/` and the nested `skillcreater/` workspace in the main RoleWeaver repository.

### Automatic Context Compression

- Added pre-generation context budget checks using the active tokenizer.
- Added automatic compression when prompt tokens approach the model context window:
  - old `recent_history` messages are summarized into the session summary buffer
  - compression summaries are also archived into episodic memory with `context_compression` tags
  - recent raw messages are reduced before generation continues
- Added `context_window_tokens` configuration:
  - `0` means auto-detect from model/tokenizer metadata
  - manual values such as `8192` or `32768` can be set from Settings
- Added a hard failure path when skill text, memory context, and user input still exceed the model context window after compression.
- Added regression coverage for context-pressure compression.

### RoleWeaver Framework Milestone

- Generalized the original role-specific HMSZ workflow into a reusable RoleWeaver runtime:
  - base model path
  - optional LoRA adapter path
  - optional `SKILL.md` path
  - optional inline skill text
- Added CSV-based configuration through `roleweaver.config.csv` so users do not need to edit Python files for normal setup.
- Added quantization mode selection:
  - `4bit`
  - `8bit`
  - `bf16`
  - `fp16`
  - `none`
- Made LoRA loading optional. Blank `lora_path` now starts the base model directly.

### Web UI and Session Management

- Added a ChatGPT-style local web frontend served by `API.py`.
- Added Chinese, Japanese, and English UI text.
- Added a Settings panel for model paths, skill paths, inline skill text, quantization mode, and UI language.
- Added persistent chat history in the sidebar.
- Added per-session settings snapshots so old chats restore their own base model, LoRA, skill, and quantization settings.
- Hid internal `session_id` values from users and added editable `display_name` values for chat names.
- Added history deletion with confirmation. Deleting a history item removes only the matching local session folder under `memory/`.
- Fixed sidebar history scrolling so long history lists scroll inside the history area instead of compressing controls.

### Memory System

- Introduced memory isolation by model, LoRA, skill, and session:
  - model/LoRA/skill combinations get separate memory scopes
  - each chat session gets its own short-term, long-term, and graph files
- Added exit-time and page-close memory consolidation.
- Kept dense embedding retrieval when available and lexical fallback when embedding dependencies or models fail.

### Local LoRA Training

- Added a web Training panel for local machines that can fine-tune directly.
- Added `/training/start`, `/training/status`, `/training/stop`, and `/training/template`.
- Added `resources/qwen35_lora_training/role_sft_template.xlsx`.
- Added `convert_excel_to_jsonl.py`, supporting:
  - `.xlsx`
  - `.xlsm`
  - `.xltx`
  - `.csv`
  - standard messages `.jsonl`
- Excel and CSV training files use the simple two-column format:

```text
user | assistant
```

- The backend converts spreadsheet input into standard `messages` JSONL under `training_runs/<run_id>/`.
- The Qwen training reference now disables thinking tags when building SFT text.

### Launcher and API Improvements

- Added `start_roleweaver.bat`.
- The launcher now opens an existing RoleWeaver server on `127.0.0.1:8000` instead of starting a duplicate model process.
- If port `8000` is occupied by another process, the launcher chooses the next free port through `8020`.
- Added full API documentation to the README.

### Documentation

- Rebuilt the GitHub README set:
  - `README.md` in English
  - `README.zh-CN.md` in Chinese
  - `README.ja.md` in Japanese
- Added language-switch links at the top of each README so GitHub users can switch languages with one click.
- Expanded the README API reference with endpoint purpose, request bodies, response fields, and training formats.

## 2026-04-24

### Memory Layering Refactor

- Refactored the memory runtime from a feature-stacked layout into a clearer semantic structure:
  - `working memory`
  - `episodic memory`
  - `graph-backed semantic memory`
  - `character knowledge`
- Reframed summary buffering as a compression mechanism for working memory overflow instead of a standalone long-term memory layer.
- Moved user profile to a graph-backed source of truth:
  - stable user facts are now stored in `KnowledgeGraphStore`
  - profile rendering is now handled by `GraphBackedProfileView`
- Kept `HybridMemoryStore` focused on episodic text memory such as:
  - explicit reminders
  - project-process context
  - archived summary traces
- Preserved the `Embedding + FAISS` coarse retrieval path and `BGE-Reranker` fine reranking path.

### Runtime and Command Updates

- Updated `test_memory.py` command descriptions so they match the new semantic layering.
- Kept command compatibility while changing their conceptual meaning:
  - `/mem *` now refers to episodic memory
  - `/profile *` now reflects graph-projected user profile facts
  - `/summary *` now reflects the summary buffer and its archived traces

### Tests

- Recompiled:
  - `memory_runtime.py`
  - `test_memory.py`
  - `tests/test_memory_runtime.py`
- Re-ran regression tests:
  - `6` tests passed
  - command used: `python -m unittest -v tests.test_memory_runtime`

### Documentation

- Updated bilingual system design documentation to match the new semantic layering.
- Updated the memory test report to reflect:
  - graph-backed user profile semantics
  - summary-to-episodic archiving
  - episodic retrieval terminology

### LINE Bot Integration

- Added `MisuzuChatService` to share one chat core between local CLI and webhook integrations.
- Added lazy model loading so the LINE app can start without immediately loading the model.
- Added a dedicated `line/` folder for LINE-specific code and setup files.
- Added `line/app.py` based on FastAPI and the official LINE Python SDK v3 webhook flow.
- Added per-session memory isolation for LINE users via session-specific storage directories.
- Added setup assets for deployment:
  - `line/requirements.txt`
  - `line/.env.example`
  - `line/README.md`
- Added lightweight LINE integration tests:
  - `tests/test_line_bot_app.py`
- Re-ran regression tests:
  - `9` tests passed
  - command used: `python -m unittest -v tests.test_memory_runtime tests.test_line_bot_app`

## 2026-04-25

### Memory Consolidation Workflow

- Reworked memory writing from per-turn immediate judging into deferred session consolidation.
- Added `pending_turns` buffering so online chat keeps short-term continuity without running a second model pass every round.
- Added manual consolidation via `/consolidate now` and pending-buffer inspection via `/pending show`.
- Added exit-time consolidation for the local CLI and idle-triggered consolidation on the next incoming message.
- Kept summary archiving active during the conversation while moving profile/graph/episodic writeback to the consolidation step.

### Hybrid Writer and Gating

- Upgraded the write planner to support session-level consolidation over multiple buffered turns.
- Kept the hybrid `rule plan + model judge` path, but now it runs on buffered sessions instead of every single reply.
- Added per-bucket confidence thresholds for:
  - `profile_candidates`
  - `graph_facts`
  - `episodic_candidates`
- Added rejection tracking so filtered candidates are preserved with `confidence`, `threshold`, and `reason`.
- Added `/writeplan show` support for both deferred and consolidated write states.

### Configurability

- Added configurable `idle_consolidation_seconds` to `MisuzuChatService`.
- Added CLI flag `--idle-consolidation-seconds`.
- Added LINE env var `MISUZU_IDLE_CONSOLIDATION_SECONDS`.
- Added normalization logic so invalid values fall back and negative values clamp to `0`.

### Verification

- Recompiled:
  - `memory_runtime.py`
  - `misuzu_chat_service.py`
  - `line/app.py`
  - `local_chat.py`
  - `tests/test_memory_runtime.py`
  - `tests/test_line_bot_app.py`
- Re-ran regression tests:
  - `16` tests passed
  - command used: `python -m unittest -v tests.test_memory_runtime tests.test_line_bot_app`
