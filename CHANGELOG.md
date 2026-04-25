# Changelog

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
