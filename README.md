# RoleWeaver

Weaving personalities into intelligent agents.

RoleWeaver turns a trained LoRA adapter into a reusable local role-chat runtime.

Milestone 1 target:

- provide a base model path
- provide a trained LoRA adapter path
- optionally provide a `SKILL.md`
- get a local chat service with role prompting, per-session memory, and an optional LINE bot entrypoint

## Local Chat

Copy `roleweaver.config.example.csv` to `roleweaver.config.csv`, open it in Excel, the web Settings panel, or any text editor, then fill the values you need:

- `base_model_path`
- `lora_path`; optional, leave blank to use only the base model
- `skill_file`; optional
- `skill_text`; optional inline skill notes
- `quantization_mode`; defaults to `4bit`
- `ui_language`; `zh`, `ja`, or `en`

`roleweaver.config.csv` is ignored by git so local machine paths do not get committed.

```powershell
python local_chat.py
```

You can also point to a specific config file:

```powershell
python local_chat.py --config "C:\roles\your-role\roleweaver.config.csv"
```

## Environment Variables

For deployment, the same config can be selected with:

```powershell
$env:ROLEWEAVER_CONFIG_FILE="C:\roles\your-role\roleweaver.config.csv"
```

Direct `ROLEWEAVER_*` variables and `MISUZU_*` variables are still accepted for migration compatibility, but normal use should go through the config file.

## HTTP API

On a server, expose RoleWeaver as a local HTTP API:

```powershell
python API.py --config roleweaver.config.csv --host 127.0.0.1 --port 8000
```

Endpoints:

- `GET /health`
- `POST /chat`
- `GET /chat?user_text=...`
- `POST /consolidate/{session_id}`
- `GET /config`
- `POST /config`
- `POST /sessions`

## Windows Launcher And Web UI

On Windows, double-click `start_roleweaver.bat` from the project root. The launcher will:

- create `roleweaver.config.csv` from the example if it does not exist
- remind you to fill `base_model_path`, optional `lora_path`, optional `skill_file` or `skill_text`, and `quantization_mode`
- start the FastAPI backend on `127.0.0.1:8000`
- open the local ChatGPT-style frontend at `http://127.0.0.1:8000/`

The web UI lives in `web/index.html`. It calls the same `/chat`, `/health`, and `/consolidate/{session_id}` endpoints as external clients, so it is only a thin local interface over the real RoleWeaver runtime.

The web UI includes a Settings panel with Chinese, Japanese, and English interface text. Settings can update:

- `base_model_path`
- `lora_path`; leave it blank to run the base model without LoRA
- `skill_file`
- short inline `skill_text`, useful when you only need a small role note instead of a full skill file
- `quantization_mode`; supported values are `4bit`, `8bit`, `bf16`, `fp16`, and `none`
- `ui_language`

Settings are saved back to `roleweaver.config.csv` through `POST /config`. After saving, the in-process RoleWeaver service cache is reset, so the next chat request loads the model with the new settings.

The web UI also has an explicit Exit button. Exit and browser page close both trigger memory consolidation for the current session.

If the browser says `127.0.0.1 refused to connect`, the backend did not start or crashed before binding the port. Keep the launcher window open and check the printed error. Common causes are:

- Python is not installed or the active environment is missing dependencies from `requirements.txt`
- `roleweaver.config.csv` points to a model path that does not exist on this machine
- `skill_file` points to a missing file; leave it blank if the role has no skill file
- another process is already using port `8000`

If the launcher reports `ModuleNotFoundError: No module named 'fastapi'`, install the web API dependencies:

```powershell
py -3 -m pip install fastapi "uvicorn[standard]"
```

The launcher also offers to install these two packages automatically.

## Memory System

RoleWeaver uses a local `memory/` directory with two levels of isolation. First, it creates a memory scope for the current base model, LoRA adapter, and skill configuration. Then each session gets its own timestamp-based folder inside that scope. Different model/LoRA/skill combinations do not share memory unless you deliberately point them at the same files and session.

The memory layer has four parts:

- recent dialogue window: keeps the latest turns available for immediate continuity
- episodic memory: stores selected long-term events, preferences, and relationship facts
- knowledge graph: stores structured triples such as user facts, role facts, and stable relationship information
- profile view: builds a compact user profile from graph facts and injects it into future prompts

The on-disk layout is:

```text
memory/
  base__lora__skill__hash/
    20260426-153012/
      short_term/
        session_meta.json
        memory_state_v1.json
      long_term/
        memories_v2.json
        memories_v2.faiss
      graph/
        knowledge_graph_v1.json
        user_profile_v1.json
```

At chat time, RoleWeaver builds a memory context packet from the current user message. It retrieves relevant episodic memories, profile facts, and character knowledge, then renders them into the prompt as sections.

Memory writing is deliberately slower than normal reply generation. New turns first enter a pending buffer. When the session has been idle for a while, or when you manually call consolidation, RoleWeaver asks the memory rules and optional model judge which details are worth keeping. Useful facts are written into episodic memory or the knowledge graph; noisy chat is left out. This keeps the character from remembering every casual sentence as if it were permanent truth.

Manual consolidation is available through the local chat command:

```text
/consolidate now
```

The HTTP API exposes the same operation:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/consolidate/default
```

Useful local memory debug commands:

```text
/mem list
/mem search
/profile show
/pending show
/writeplan show
/kg show
/ctx query
```

Retrieval uses dense embeddings when an embedding model is available, with lexical search as a fallback. If `sentence-transformers`, `faiss`, `numpy`, or the selected embedding model fails to load or encode text, RoleWeaver logs the problem and continues with lexical memory search instead of crashing the chat service.

## LINE Bot（Construction）

The LINE app reads the same `ROLEWEAVER_*` variables plus:

```powershell
$env:LINE_CHANNEL_SECRET="..."
$env:LINE_CHANNEL_ACCESS_TOKEN="..."
```

Run with your ASGI server of choice, for example:

```powershell
uvicorn line.app:app --host 0.0.0.0 --port 8000
```

## QQ Voice Bot（Construction）

QQ voice reply integration lives in `QQbot/`. It uses QQ official bot events, an SSH tunnel to the remote RoleWeaver text API, and local GPT-SoVITS for voice synthesis.

```powershell
python -m QQbot.main --config QQbot\qq_voice_bot.config.csv
```

## Training A New Adapter

For the original offline Qwen3.5-9B LoRA training workflow, see `resources/qwen35_lora_training/`.

```powershell
python train_lora.py `
  --base-model-path "C:\models\base-model" `
  --data-path "C:\datasets\role_sft.jsonl" `
  --output-dir ".\outputs\your-role-lora"
```

The final adapter is saved under `OUTPUT_DIR\final`.

## Utility Probes

Probe a base model:

```powershell
python base_model_probe.py --base-model-path "C:\models\base-model"
```

Probe a LoRA adapter through the full RoleWeaver runtime:

```powershell
python adapter_probe.py
```
