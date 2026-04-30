# Changelog

## 2026-05-01

### Shiro A800 Omni LoRA

- Added a remote Qwen3-Omni text-persona LoRA training workflow for Shiro on the A800 server.
- Added `resources/qwen3_omni_training/train_qwen3_omni_text_lora.py` for conservative single-GPU Omni thinker training:
  - text-only SFT;
  - optional 4-bit loading;
  - periodic checkpoints;
  - `training_status.json` progress reporting.
- Added remote launcher and monitor scripts under `server/`:
  - `start_remote_omni_training.py`
  - `start_remote_omni_training.bat`
  - `watch_remote_training.py`
  - `watch_remote_omni_training.bat`
- Added A800 dependency notes and PEFT/datasets/bitsandbytes requirements to the server package.
- Completed a Shiro persona blend training run on the A800 server and configured the A800 service to load the final adapter path.

### Omni Runtime Loading

- Updated `role_chat_service.py` so Qwen3-Omni can load a thinker LoRA adapter without replacing the whole Omni wrapper.
- Added a compatibility path for current PEFT/Transformers versions by manually loading LoRA safetensor keys into the Omni thinker when the standard PEFT loader fails.
- Preserved text-first Omni serving while keeping the door open for image/audio inputs through the existing multimodal runtime.

### Shiro Persona Dataset Tools

- Added Shiro persona SFT preparation tools under `resources/shiro_persona_sft/`.
- Added a manifest-based blend builder so user-owned dialogue extracts can be mixed with Shiro core persona samples.
- Kept raw extracted dialogue data out of Git by default; the repository now tracks reproducible tooling and examples rather than private or copyrighted source data.
- Added documentation for the Shiro persona blend workflow in `docs/SHIRO_PERSONA_SFT_BLEND.zh-CN.md`.

### Unity And Remote Companion Flow

- Added documentation for the Shiro Unity companion client, VRM import workflow, Unity dialogue flow, and A800 Omni deployment.
- Added example A800/Shiro config files while keeping local SSH credentials and runtime state ignored.
- Tightened `.gitignore` for generated zip packages, learning runtime state, quarantine data, local persona datasets, and raw SFT extracts.

## 2026-04-29

### Shiro Bridge

- Added optional Shiro cognitive bridge for M6.2 while keeping Shiro as a separate project.
- Added `shiro_bridge.py`, which dynamically imports `shiro/src` when `shiro_enabled=true`.
- Added config fields:
  - `shiro_enabled`
  - `shiro_root`
  - `shiro_identity`
- Role mode now injects Shiro `thought_context` into the system prompt when enabled.
- Successful web and image chat turns are written back to Shiro as cognitive stimuli.
- Added Shiro API endpoints:
  - `GET /sessions/{session_id}/shiro`
  - `POST /sessions/{session_id}/shiro/observe`
- Added a Shiro page in the Vue console for status, thought context, recent transitions, and manual stimulus input.
- Added [Shiro Bridge Design](docs/SHIRO_BRIDGE.zh-CN.md).

### Tool Intention Layer

- Added Shiro M6.3 tool-intention inference for PDF reading and web-search solution lookup.
- Added `POST /sessions/{session_id}/shiro/tool-intentions`.
- Added `document.pdf_read` to the RoleWeaver tool layer for read-only local PDF text extraction.
- The Shiro page can now infer tool intentions and show risk, confirmation requirement, external-action status, and memory policy.

### Tool Layer

- Added `tool_runtime.py`, a controlled tool registry with JSON-style argument validation and action logging.
- Added Tool Layer API endpoints:
  - `GET /tools`
  - `POST /tools/run`
  - `GET /tools/actions`
- Exposed safe first tools for runtime time/config/status, planning, web lookup, memory search/snapshot/consolidation, background jobs, LINE/tunnel status, and training status.
- Added a Vue Tool Layer page so tools can be selected, run, and inspected from the browser.
- Added [Tool Layer Design](docs/TOOL_LAYER.zh-CN.md).

### Single-GPU Background Scheduler

- Added `background_scheduler.py`, a persistent idle-window scheduler for always-on single-GPU deployments.
- Added configurable background controls to `roleweaver.config.csv` and the Vue runtime settings:
  - `background_jobs_enabled`
  - `background_llm_enabled`
  - `background_idle_seconds`
  - `background_window_start`
  - `background_window_end`
  - `background_max_minutes`
- Added Background Scheduler API endpoints:
  - `GET /background/status`
  - `POST /background/pause`
  - `POST /background/resume`
  - `POST /background/run-once`
- Added a Vue Background page for idle status, manual task execution, pause/resume, and recent job history.
- Added conservative single-GPU gating: manual `force=true` can bypass idle/time-window checks, but cannot bypass `background_llm_enabled=false`.
- Added a lightweight FastAPI startup worker that checks the idle window periodically:
  - non-LLM planning refresh can run automatically;
  - LLM memory consolidation only runs when `background_llm_enabled=true`;
  - `ROLEWEAVER_BACKGROUND_WORKER=0` disables the worker.
- Added supported job types:
  - `planning_regenerate`
  - `memory_os_snapshot`
  - `memory_consolidation`
  - `release_inactive_models`
- Added [Background Scheduler Design](docs/BACKGROUND_SCHEDULER.zh-CN.md).

### A-Mem Style Memory Evolution

- Added non-destructive old-memory evolution inspired by A-Mem:
  - new linked memories can update older memories' `metadata.amem.current_interpretation`;
  - original memory `content`, `scope`, and `memory_type` are preserved;
  - character canon, skill memories, and imported references are protected from user-chat evolution.
- Retrieval now indexes A-Mem evolution metadata, so older memories can be recalled through newer related context.
- Memory maintenance backfills A-Mem evolution events across existing memory links.
- Memory OS snapshots now expose `amem_evolution` counts and recent evolved memories.
- Memory lifecycle views now report A-Mem evolution counts and current interpretation.
- Documented the new metadata shape in [Memory Item Schema](docs/MEMORY_ITEM_SCHEMA.md).

### Planning Layer

- Added a lightweight memory + reflection + planning runtime in `planning_runtime.py`.
- Role prompts now receive a bounded planning context in role mode:
  - current device time and timezone;
  - configured local location through `ROLEWEAVER_LOCAL_LOCATION`;
  - the current role schedule block for the active memory scope.
- Weekly role schedules are generated once per memory scope and week, saved under `planning/weekly_schedule.json`, and regenerated only when the week changes or the user requests it.
- The schedule generator integrates 2026 Japanese public holidays and representative school/club activity references, then adds deterministic weekly perturbations for role-like daily variance.
- Added Web/API planning controls:
  - `GET /planning/{session_id}`
  - `POST /planning/{session_id}/regenerate`
  - `GET /planning/search?q=...`
- Added a top-level Planning page to the Vue console with device context, current planning context, weekly schedule, reference sources, and manual web lookup.
- Added editable `local_location` config for role planning; it can be changed from the Web runtime settings instead of relying only on an environment variable.
- Regenerated `skillcreater/characters/Hataya-Misuzu/skill/persona_kernel.json` for the current persona-kernel schema, including autonomy, memory boundaries, media adaptation, and planning-state safeguards.

### Persona Anchor Replay

- Added `anchor_runtime.py` for lightweight persona anchor loading, selection, and prompt rendering.
- Added `resources/anchor_tools/build_gakumas_anchors.py` to generate anchors from Gakumas Localify ADV scripts.
- Generated a local Hataya Misuzu anchor bank from 171 local `hmsz` ADV files:
  - output: `skillcreater/characters/Hataya-Misuzu/skill/anchors/anchors.jsonl`
  - metadata: `skillcreater/characters/Hataya-Misuzu/skill/anchors/anchors.meta.json`
  - the generated character-source artifact stays local because `skillcreater/` is ignored
- Anchors store short evidence snippets, source file names, line numbers, persona dimensions, time-block tags, and derived summaries.
- Role prompts now include one selected anchor in role mode when an anchor bank exists beside `SKILL.md`.
- The Planning API and Web Planning page now expose the currently selected persona anchor.
- Added [Persona Anchors Design](docs/ANCHORS.zh-CN.md).

### Unified Local Console

- Added a one-stop LINE Bot console inside the existing Web UI.
- Added API endpoints for local LINE configuration management:
  - `GET /integrations/line/settings`
  - `POST /integrations/line/settings`
- Replaced the old single-file Web UI with a Vue-based console split into `web/index.html`, `web/app.js`, and `web/styles.css`.
- Vendored Vue under `web/vendor/vue.global.prod.js` so the local console does not need a CDN at runtime.
- Added top-level console pages for overview flows, chat, runtime settings, Memory OS, training, LINE/TTS/tunnel setup, persona scoring, and flow documentation.
- Added LINE bot process controls:
  - `GET /integrations/line/runtime/status`
  - `POST /integrations/line/runtime/start`
  - `POST /integrations/line/runtime/stop`
- Added temporary Cloudflare Tunnel controls for LINE Webhook setup:
  - `GET /integrations/tunnel/status`
  - `POST /integrations/tunnel/start`
  - `POST /integrations/tunnel/stop`
- The Web UI can now edit `line/.env` and `line/surface_policy.json` without leaving the browser.
- Surface policy JSON is validated before saving, so malformed policy edits fail with a clear API error.
- Added API tests for LINE settings load/save and JSON validation.

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
- Started M5.3 persona-kernel generated regression cases:
  - added `eval/persona_regression/generate_cases_from_kernel.py`
  - supports `--kernel`, `--skill-file`, and `--config-file`
  - generates JSONL cases for identity, autonomy, boundary, memory pollution, media adaptation, and custom `evaluation.dimensions`
  - generated files can be validated immediately with the existing persona regression loader
- Added M5.4 persona interview evaluation:
  - added `eval/persona_regression/run_persona_interview.py`
  - interview probes cover identity, autonomy, relationship boundary, memory boundary, conflict style, LINE, TTS, and image adaptation
  - supports dry-run validation, API evaluation, local-model evaluation, reports, language selection, and optional persona-kernel scoring
  - this stays under `eval/` and is never invoked by Web or LINE request handling
- Added M5.5 long-dialogue drift stress testing:
  - added `eval/persona_regression/run_long_dialogue_drift.py`
  - repeated same-session turns mix casual chat with identity, autonomy, memory-boundary, LINE, and image-adaptation probes
  - supports dry-run validation, API evaluation, local-model evaluation, reports, language selection, and optional persona-kernel scoring
  - designed to catch the `Persistent Personas?` failure mode where long conversations flatten a role into a generic assistant
- Started Phase 2 with M4.7 memory-use reinforcement:
  - long-term memories now track `use_count`, `last_used_at`, and `reinforcement_score`
  - context retrieval reinforces memories only when they are actually used to build the prompt
  - reinforced memories receive a small retrieval bonus and are protected from low-confidence aging decay
  - `GET /sessions/{session_id}/memory-os` now reports reinforcement counts and top reinforced memories
  - the Web memory manager shows usage reinforcement metadata for each memory
- Added M4.8 lightweight dynamic memory linking:
  - new memories automatically link to semantically related active memories through `links`
  - linked older memories receive a back-reference in `links` and `metadata.linked_by`
  - character canon and skill/imported-reference memories are protected from user-memory auto-linking
  - `GET /sessions/{session_id}/memory-os` now reports total dynamic links
- Added M4.9 memory lifecycle visibility:
  - memory list responses now include a computed `lifecycle` view for each memory
  - lifecycle metadata explains age, protection, reinforcement, decay risk, pending maintenance, and why the memory is kept or downgraded
  - the Web memory manager shows lifecycle badges and explanation notes per memory item
  - added tests for pending decay and reinforcement-protected lifecycle states
- Started Phase 3 with M6.1 LINE surface policy:
  - added `line/surface_policy.json` for centralized LINE/TTS/image/wake-up behavior
  - LINE token budget, reply chunk size, image prompt, wake-up time, wake-up prompt, voice-first mode, text-only window, and voice request/reject markers can now come from the policy file
  - existing `.env` variables still override the JSON policy for backward compatibility
  - added tests for policy-file behavior and env override precedence
- Added M4.6 Memory OS layering:
  - new `memory_layer` field: `short_term`, `mid_term`, `long_term`, `graph`, `contradiction_graph`, `reflection_notes`
  - old memory records are assigned a layer on load; new writes infer layer from type/source/tags
  - retrieval now separates mid-term summaries, durable long-term memories, reflection notes, graph facts, and contradiction hints
  - added `GET /sessions/{session_id}/memory-os` for layer/status counts

### Design Principles and Research Roadmap

- Added `docs/DESIGN_PRINCIPLES.md` as the project-level design contract.
- Added `docs/ROLEWEAVER_TOP_LEVEL_DESIGN.zh-CN.md` as the research-prioritized top-level architecture blueprint.
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
