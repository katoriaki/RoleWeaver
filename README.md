# RoleWeaver

RoleWeaver turns a trained LoRA adapter into a reusable local role-chat runtime.

Milestone 1 target:

- provide a base model path
- provide a trained LoRA adapter path
- optionally provide a `SKILL.md`
- get a local chat service with role prompting, per-session memory, optional LINE bot entrypoint, and the same runtime shape as the original HMSZ prototype

## Local Chat

```powershell
python local_chat.py `
  --role-name "Your Role" `
  --base-model-path "C:\models\base-model" `
  --lora-path "C:\models\your-role-lora" `
  --skill-file "C:\roles\your-role\SKILL.md" `
  --session-id "local-cli"
```

The old project-specific entrypoint is still available as a compatibility wrapper:

```powershell
python misuzu_chat_service.py
```

## Environment Variables

The recommended prefix is `ROLEWEAVER_`:

```powershell
$env:ROLEWEAVER_ROLE_NAME="Your Role"
$env:ROLEWEAVER_USER_SUBJECT="用户"
$env:ROLEWEAVER_BASE_MODEL_PATH="C:\models\base-model"
$env:ROLEWEAVER_LORA_PATH="C:\models\your-role-lora"
$env:ROLEWEAVER_SKILL_FILE="C:\roles\your-role\SKILL.md"
$env:ROLEWEAVER_SESSION_ROOT="C:\roleweaver-sessions"
```

`MISUZU_*` variables are still accepted by the LINE bot for migration compatibility.

## LINE Bot

The LINE app reads the same `ROLEWEAVER_*` variables plus:

```powershell
$env:LINE_CHANNEL_SECRET="..."
$env:LINE_CHANNEL_ACCESS_TOKEN="..."
```

Run with your ASGI server of choice, for example:

```powershell
uvicorn line.app:app --host 0.0.0.0 --port 8000
```

## Training A New Adapter

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
python adapter_probe.py `
  --role-name "Your Role" `
  --base-model-path "C:\models\base-model" `
  --lora-path "C:\models\your-role-lora" `
  --skill-file "C:\roles\your-role\SKILL.md"
```
