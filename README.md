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
