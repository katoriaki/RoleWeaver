# RoleWeaver

Weaving personalities into intelligent agents.

RoleWeaver turns a trained LoRA adapter into a reusable local role-chat runtime.

Milestone 1 target:

- provide a base model path
- provide a trained LoRA adapter path
- optionally provide a `SKILL.md`
- get a local chat service with role prompting, per-session memory, and an optional LINE bot entrypoint

## Local Chat

Copy `roleweaver.config.example.csv` to `roleweaver.config.csv`, open it in Excel or any text editor, then fill only these three values:

- `base_model_path`
- `lora_path`
- `skill_file`

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

## Memory System

RoleWeaver uses a per-session hybrid memory runtime. Each `session_id` gets its own memory directory, so different users or roles do not share private conversation state unless you deliberately reuse the same session.

The memory layer has four parts:

- recent dialogue window: keeps the latest turns available for immediate continuity
- episodic memory: stores selected long-term events, preferences, and relationship facts
- knowledge graph: stores structured triples such as user facts, role facts, and stable relationship information
- profile view: builds a compact user profile from graph facts and injects it into future prompts

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
