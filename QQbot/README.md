# QQ Voice Bot

This folder contains a QQ official bot adapter that connects:

```text
QQ message -> remote RoleWeaver text API over SSH tunnel -> local GPT-SoVITS -> QQ voice reply
```

The entrypoint is:

```powershell
python -m QQbot.main --config QQbot\qq_voice_bot.config.csv
```

## Setup

1. Copy `QQbot/qq_voice_bot.config.example.csv` to `QQbot/qq_voice_bot.config.csv`.
2. Fill the QQ credentials:
   - `qq_app_id`
   - `qq_app_secret`
3. Fill the SSH tunnel fields:
   - `ssh_user`
   - `ssh_host`
   - `ssh_port`
   - `ssh_identity_file` if needed
   - `ssh_remote_port`, usually the port where RoleWeaver text API runs on the server
4. Fill the local TTS fields:
   - `gpt_weights_path`
   - `sovits_weights_path`
   - `ref_audio_path`
   - `prompt_text`
5. Fill `public_audio_base_url`.

QQ media upload needs a URL that QQ servers can fetch. If GPT-SoVITS generates files locally, expose `audio_output_dir` through a small public file server, object storage, or a temporary tunnel, then put that URL prefix in `public_audio_base_url`.

## Runtime Pieces

- `ssh_tunnel.py`: starts `ssh -N -L local_port:remote_host:remote_port`.
- `roleweaver_client.py`: calls the remote `/chat` API through the local forwarded port.
- `tts_client.py`: calls local GPT-SoVITS `api_v2.py`, sets GPT/SoVITS weights, and saves audio.
- `bot.py`: handles QQ group @ and C2C messages through `qq-botpy`.

## Server Side

On the server that runs the large RoleWeaver model:

```powershell
cd /path/to/RoleWeaver
python -m QQbot.remote_roleweaver_api --config roleweaver.config.csv --host 127.0.0.1 --port 8000
```

Keep it bound to `127.0.0.1` when you use SSH tunneling. The local QQ bot will forward `127.0.0.1:18000` to this server-side `127.0.0.1:8000`.

## Local Start Order

Start local GPT-SoVITS first:

```powershell
cd C:\Users\kator\Desktop\RoleWeaver\G
python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml
```

Then start the QQ bot:

```powershell
cd C:\Users\kator\Desktop\RoleWeaver
python -m QQbot.main --config QQbot\qq_voice_bot.config.csv
```

The QQ bot starts the SSH tunnel itself when `ssh_enable=true`.

## Important QQ Voice Note

QQ official rich media voice upload uses `file_type=3`. Public docs and botpy comments describe this as voice/silk. GPT-SoVITS produces wav/ogg/aac, so production voice sending may require a silk converter. Configure `silk_converter_command` as a command template:

```csv
silk_converter_command,C:\tools\silk_encoder.exe {input} {output}
```

If no converter is configured, the bot uploads the generated file as-is. If QQ rejects it, the bot falls back to text when `fallback_to_text=true`.
