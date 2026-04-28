# RoleWeaver

**Languages:** English | [中文](README.zh-CN.md) | [日本語](README.ja.md)

RoleWeaver turns a base LLM, an optional LoRA adapter, and an optional role skill into a reusable local role-chat runtime with persistent per-session memory, a ChatGPT-style web UI, and training utilities for users who want to fine-tune their own adapter.

## Latest Update

2026-04-27:

- Added a Windows launcher that reuses an existing RoleWeaver server on `127.0.0.1:8000` or automatically falls back to the next free port through `8020`.
- Added a local web Training panel that accepts Excel, CSV, or standard JSONL datasets.
- Added `resources/qwen35_lora_training/role_sft_template.xlsx`, a two-column training template with `user` and `assistant` headers.
- Added editable chat display names. Internal `session_id` values remain hidden and continue to map to the original memory folders.
- Expanded session history: restore, rename, delete, and per-session settings snapshots.
- Added [RoleWeaver Design Principles](docs/DESIGN_PRINCIPLES.md), defining persona autonomy, memory boundaries, media adaptation rules, and the next design roadmap.
- Added the first [Persona Kernel schema](docs/PERSONA_KERNEL_SCHEMA.md) for structured, evidence-aware role definitions.
- Added [Memory Item schema](docs/MEMORY_ITEM_SCHEMA.md) and a lightweight [persona regression harness](eval/persona_regression/README.md).

See [CHANGELOG.md](CHANGELOG.md) for the full update announcement.

## What It Does

- Runs local role chat from a base model path.
- Loads a LoRA adapter when `lora_path` is provided; leaves it unloaded when blank.
- Loads role behavior from either a `SKILL.md` file or a small inline skill note.
- Supports `4bit`, `8bit`, `bf16`, `fp16`, or unquantized model loading.
- Stores memories under `memory/`, isolated by base model, LoRA, skill, and session.
- Provides a local FastAPI API, a browser UI, a CLI chat entrypoint, and bot integration scaffolding.
- Follows a documented design contract: character autonomy comes before persona consistency, memory personalization, task completion, and platform formatting. See [docs/DESIGN_PRINCIPLES.md](docs/DESIGN_PRINCIPLES.md).
- Automatically loads a nearby `persona_kernel.json` next to `SKILL.md` when present, while keeping `SKILL.md` as the only user-facing skill path.
- Includes an early persona regression harness for checking autonomy, media adaptation, and memory-boundary regressions.

## Quick Start

Copy the example config:

```powershell
copy roleweaver.config.example.csv roleweaver.config.csv
```

Fill these values in Excel, the web Settings panel, or a text editor:

- `base_model_path`
- `lora_path` optional; leave blank to run the base model directly
- `skill_file` optional
- `skill_text` optional short inline skill
- `quantization_mode` default `4bit`
- `ui_language` one of `zh`, `ja`, `en`

Create or refresh the project-local runtime:

```powershell
setup_runtime.bat
```

After this, `start_roleweaver.bat` and `line/start_line_bot.bat` prefer `runtime\Scripts\python.exe`.

Run the Windows launcher:

```powershell
start_roleweaver.bat
```

Or run the CLI:

```powershell
python local_chat.py --config roleweaver.config.csv
```

## Windows Launcher And Web UI

Double-click `start_roleweaver.bat` from the project root.

The launcher will:

- create `roleweaver.config.csv` from the example if it does not exist;
- offer to install `fastapi` and `uvicorn` if the active Python environment is missing them;
- open an existing RoleWeaver server if `127.0.0.1:8000` is already running RoleWeaver;
- otherwise bind to `8000`, or the next free port through `8020`;
- open the local web UI in your browser.

The web UI supports:

- Chinese, Japanese, and English interface text;
- Settings for base model, LoRA, skill file, inline skill, quantization, and UI language;
- chat history restore;
- editable display names that do not rename memory folders;
- history deletion after confirmation;
- explicit memory consolidation on Exit or page close;
- local LoRA training with Excel, CSV, or JSONL data.

## HTTP API

Start the API manually:

```powershell
python API.py --config roleweaver.config.csv --host 127.0.0.1 --port 8000
```

### `GET /`

Serves the local web UI from `web/index.html`.

### `GET /health`

Returns runtime health and currently selected model settings.

Optional query:

- `session_id`: if provided, health is checked against that session's saved settings snapshot.

Typical response fields:

- `status`
- `role_name`
- `base_model_path`
- `lora_path`
- `lora_enabled`
- `skill_file`
- `skill_text_present`
- `quantization_mode`
- `memory_root`
- `memory_scope_path`

### `POST /chat`

Generates one assistant response.

Request body:

```json
{
  "user_text": "Hello",
  "session_id": "web",
  "max_new_tokens": 160
}
```

Response:

```json
{
  "text": "...",
  "session_id": "web"
}
```

### `GET /chat`

Query-string version of `POST /chat`.

Example:

```text
/chat?user_text=Hello&session_id=api&max_new_tokens=120
```

### `POST /consolidate/{session_id}`

Runs memory consolidation for the selected session. This promotes useful pending turns into episodic memory, graph facts, and profile facts.

Response:

```json
{
  "result": {}
}
```

### `GET /config`

Returns the active editable config.

Response fields:

- `config_file`
- `base_model_path`
- `lora_path`
- `skill_file`
- `skill_text`
- `quantization_mode`
- `ui_language`

### `POST /config`

Updates `roleweaver.config.csv` and clears the in-process service cache so the next chat request loads the new settings.

Request body:

```json
{
  "base_model_path": "C:\\models\\base",
  "lora_path": "C:\\models\\adapter",
  "skill_file": "C:\\roles\\SKILL.md",
  "skill_text": "",
  "quantization_mode": "4bit",
  "ui_language": "en"
}
```

All fields are optional; omitted fields keep their current value.

### `GET /sessions`

Lists persisted sessions discovered under `memory/`.

Each item includes:

- `session_id`: internal identifier used for directories and API calls;
- `display_name`: user-facing chat name;
- `created_ts`
- `updated_ts`
- `session_path`
- `memory_scope_path`
- `settings_snapshot`
- `warnings`: missing model, LoRA, or skill paths.

### `POST /sessions`

Creates a new session in the current model/LoRA/skill memory scope. The session folder is still timestamp based; the visible display name is stored separately.

### `GET /sessions/{session_id}`

Loads one session, including its transcript and saved settings snapshot.

Response includes all `GET /sessions` fields plus:

- `messages`
- `config`

### `PATCH /sessions/{session_id}`

Updates the user-facing session display name without renaming the session folder or changing the internal `session_id`.

Request body:

```json
{
  "display_name": "My role test"
}
```

### `DELETE /sessions/{session_id}`

Deletes the matching local session folder under `memory/`. The web UI asks for confirmation before calling this endpoint.

### `POST /training/start`

Starts one local LoRA training job as a background process. Only one training job can run through the web API at a time.

Request body:

```json
{
  "model_path": "C:\\models\\base",
  "data_file": "C:\\datasets\\role_sft.xlsx",
  "output_dir": ".\\outputs\\your-role-lora",
  "epochs": 3,
  "learning_rate": 0.0001,
  "per_device_train_batch_size": 2,
  "gradient_accumulation_steps": 8,
  "save_steps": 50,
  "save_total_limit": 2,
  "logging_steps": 10,
  "lora_r": 16,
  "lora_alpha": 32,
  "lora_dropout": 0.05,
  "online": false
}
```

Supported `data_file` formats:

- `.xlsx`, `.xlsm`, `.xltx`: first sheet, first row `user | assistant`, data from row 2;
- `.csv`: first row `user,assistant`, data from row 2;
- `.jsonl`: standard messages JSONL.

Excel and CSV files are converted to JSONL under `training_runs/<run_id>/converted_dataset.jsonl` before training.

### `GET /training/status`

Returns the current or latest training job.

Response fields:

- `active`
- `run_id`
- `status`: `idle`, `running`, `completed`, or `failed`
- `returncode`
- `started_ts`
- `command`
- `log_path`
- `log_tail`
- `message`

### `POST /training/stop`

Requests termination of the active training subprocess.

### `GET /training/template`

Downloads `resources/qwen35_lora_training/role_sft_template.xlsx`.

## Training Data

The easiest format is the Excel template:

[resources/qwen35_lora_training/role_sft_template.xlsx](resources/qwen35_lora_training/role_sft_template.xlsx)

Sheet format:

```text
user | assistant
Hi   | Hello...
```

Manual conversion:

```powershell
python resources\qwen35_lora_training\convert_excel_to_jsonl.py `
  --input "C:\datasets\role_sft.xlsx" `
  --output "C:\datasets\role_sft.jsonl"
```

Manual training:

```powershell
python resources\qwen35_lora_training\train_qwen35_lora_offline.py `
  --model-path "C:\models\base-model" `
  --data-file "C:\datasets\role_sft.jsonl" `
  --output-dir ".\outputs\your-role-lora"
```

For Qwen-style thinking models, the trainer disables thinking tags while building SFT text.

## Memory System

RoleWeaver stores memory under:

```text
memory/
  base__lora__skill__hash/
    session-id/
      short_term/
        session_meta.json
        settings_snapshot.json
        transcript.jsonl
        memory_state_v1.json
      long_term/
        memories_v2.json
        memories_v2.faiss
      graph/
        knowledge_graph_v1.json
        user_profile_v1.json
```

The system uses:

- recent dialogue state for immediate continuity;
- episodic memory for selected long-term events and preferences;
- graph memory for structured facts;
- profile projection for compact user context.

If embedding dependencies or an embedding model fail, retrieval falls back to lexical search instead of crashing the runtime.

## Bot Integrations

### LINE

The LINE app lives in `line/`.

```powershell
uvicorn line.app:app --host 0.0.0.0 --port 8000
```

Endpoints:

- `GET /health`
- `POST /callback`

### QQ Voice Bot

QQ voice reply integration lives in `QQbot/`. It combines QQ official bot events, SSH access to the remote RoleWeaver text API, and a local voice synthesis API such as GPT-SoVITS.

```powershell
python -m QQbot.main --config QQbot\qq_voice_bot.config.csv
```

The minimal remote text API is:

- `GET /health`
- `POST /chat`

## Notes

- `roleweaver.config.csv` is ignored by git so local model paths do not leak.
- `memory/`, `training_runs/`, and generated outputs are ignored by git.
- The project is currently a practical local framework, not yet a polished packaged application.
