# Changelog

## 2026-04-27

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
