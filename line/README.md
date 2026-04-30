# RoleWeaver LINE Bot

This folder contains the LINE Official Account integration for RoleWeaver. The first milestone is simple automatic text reply:

1. A user sends a text message to your LINE Official Account.
2. LINE sends a webhook event to `POST /callback`.
3. `line/app.py` validates the LINE signature.
4. RoleWeaver builds an isolated memory session for that LINE user/group/room.
5. RoleWeaver replies through the LINE Messaging API.

## What You Need From LINE

Do not publish these values. Put them in `line/.env` only.

- `LINE_CHANNEL_SECRET`
- `LINE_CHANNEL_ACCESS_TOKEN`

You can find both in LINE Developers Console under your Messaging API channel.

## One-Click Local Start

Double-click:

```text
line/start_line_bot.bat
```

The script will:

- create `line/.env` from `line/.env.example` if it does not exist;
- open `line/.env` in Notepad for you to fill the LINE credentials;
- check Python dependencies;
- optionally install `line/requirements.txt`;
- start the bot server on `http://127.0.0.1:8010`.

Health check:

```text
http://127.0.0.1:8010/health
```

Webhook endpoint:

```text
POST http://127.0.0.1:8010/callback
```

## Public HTTPS URL

LINE cannot call `127.0.0.1` directly. Expose local port `8010` with a public HTTPS tunnel, then register:

```text
https://<your-public-domain>/callback
```

Common tunnel choices:

- Cloudflare Tunnel
- ngrok
- a reverse proxy on your VPS

The URL must be HTTPS and reachable from LINE.

## `line/.env` Example

```dotenv
LINE_CHANNEL_SECRET=your_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token
ROLEWEAVER_CONFIG_FILE=roleweaver.config.csv
ROLEWEAVER_LINE_HOST=0.0.0.0
ROLEWEAVER_LINE_PORT=8010
ROLEWEAVER_SESSION_ROOT=
ROLEWEAVER_LINE_DEBUG_ERRORS=0
ROLEWEAVER_LINE_MAX_NEW_TOKENS=192
ROLEWEAVER_CUDA_EMPTY_CACHE_AFTER_GENERATE=1
ROLEWEAVER_IDLE_CONSOLIDATION_SECONDS=600
```

For this workspace, the default LINE config is:

```text
line/roleweaver.line.config.csv
```

It currently points to:

- base model: `C:\Users\kator\Desktop\RoleWeaver\Qwen3.5-4b`
- LoRA: `C:\Users\kator\Desktop\RoleWeaver\outputs\4B-hmsz\checkpoint-250`
- skill: `C:\Users\kator\Desktop\RoleWeaver\skillcreater\characters\Hataya-Misuzu\skill\SKILL.md`

`ROLEWEAVER_CONFIG_FILE` can also point to the same config file used by the local RoleWeaver web UI. That config controls:

- base model path
- LoRA path
- skill file
- quantization mode
- memory settings

## Built-In Commands

Send these messages to the official account:

- `/ping`: returns `pong`
- `/help`: shows a short command list
- `/status`: checks whether RoleWeaver config can be loaded
- `/wake on`: subscribe the current LINE user/group/room to the daily 07:00 wake-up push
- `/wake off`: unsubscribe from the daily wake-up push

Any other text message is sent to the current RoleWeaver role.

If LINE replies are being cut off, increase:

```dotenv
ROLEWEAVER_LINE_MAX_NEW_TOKENS=192
```

The default is `192`; values are clamped between `16` and `4096`.

For a long-running local GPU bot, keep this enabled unless you are chasing maximum speed:

```dotenv
ROLEWEAVER_CUDA_EMPTY_CACHE_AFTER_GENERATE=1
```

## Daily Wake-Up Push

The bot can send a daily morning push while both the LINE bot server and the public tunnel are running.

In `line/.env`:

```dotenv
ROLEWEAVER_WAKEUP_ENABLED=1
ROLEWEAVER_WAKEUP_TIME=07:00
ROLEWEAVER_WAKEUP_TIMEZONE=Asia/Tokyo
ROLEWEAVER_WAKEUP_VOICE=0
```

Then send this to the official account:

```text
/wake on
```

Contacts are stored in:

```text
data/line_contacts.json
```

The free LINE Communication Plan in Japan includes a small monthly quota for push-style messages. A once-per-day single-user wake-up push is about 30 push messages per month.

### Voice Wake-Up

LINE audio messages require a public HTTPS `mp3` or `m4a` URL. RoleWeaver can call local GPT-SoVITS, save audio under `data/line_audio`, convert it to `mp3`, and serve it from `/audio/<file>`.

First start GPT-SoVITS:

```text
G/start_roleweaver_tts_api.bat
```

Then set these in `line/.env`:

```dotenv
ROLEWEAVER_WAKEUP_VOICE=1
ROLEWEAVER_REPLY_VOICE=1
ROLEWEAVER_PUBLIC_BASE_URL=https://your-current-tunnel.trycloudflare.com
ROLEWEAVER_TTS_URL=http://127.0.0.1:9880/
ROLEWEAVER_TTS_REFER_WAV_PATH=C:\path\to\reference.wav
ROLEWEAVER_TTS_PROMPT_TEXT=reference audio transcript
ROLEWEAVER_TTS_PROMPT_LANGUAGE=ja
ROLEWEAVER_TTS_TEXT_LANGUAGE=ja
```

Use the same public base URL as the webhook URL, but without `/callback`.

`ROLEWEAVER_REPLY_VOICE=1` makes normal chat replies voice-first. Built-in commands such as `/ping`, `/help`, `/status`, `/wake on`, and `/wake off` remain text so they are easy to debug.

### Surface Policy File

M6.1 adds a central policy file for LINE, TTS, image, and wake-up behavior:

```dotenv
ROLEWEAVER_SURFACE_POLICY_FILE=line\surface_policy.json
```

If an environment variable is set, it still overrides the JSON policy. This keeps old `.env` files compatible while letting new users edit one structured file for:

- `line.max_new_tokens`
- `line.reply_chunk_size`
- `line.image_prompt`
- `line.voice.reply_voice`
- `line.voice.text_only_start` / `text_only_end`
- `line.voice.request_markers` / `reject_markers`
- `line.wake_up.time`
- `line.wake_up.prompt`

### Daytime Text-Only Window

To avoid generating voice during work or school hours, enable the text-only window:

```dotenv
ROLEWEAVER_REPLY_VOICE=1
ROLEWEAVER_VOICE_TEXT_ONLY_WINDOW_ENABLED=1
ROLEWEAVER_VOICE_TEXT_ONLY_START=08:00
ROLEWEAVER_VOICE_TEXT_ONLY_END=17:30
ROLEWEAVER_VOICE_TEXT_ONLY_TIMEZONE=Asia/Tokyo
```

Between `08:00` and `17:30`, normal chat replies are text only. If the user explicitly asks for voice in Chinese, Japanese, or English, the bot synthesizes voice for that one reply only.

## Image Messages

If the configured base model is a native vision model such as Qwen-VL/Qwen3-VL, LINE image messages can be routed into the same RoleWeaver memory session.

When a user sends an image, the bot downloads the LINE message content into:

```text
data/line_images/<line-session-id>/
```

Then it calls `RoleChatService.chat_once_with_image()` with this prompt:

```dotenv
ROLEWEAVER_LINE_IMAGE_PROMPT=Look at this image and reply briefly and naturally in the current role, like a LINE chat.
```

You can replace that prompt in `line/.env`. Text-only models will still handle normal messages, but image messages require a model directory with a usable vision processor, for example a `preprocessor_config.json` backed by a compatible Transformers version.

## Current Limits

- Image messages do not support captions yet; LINE sends the image event separately, so RoleWeaver uses `ROLEWEAVER_LINE_IMAGE_PROMPT`.
- Inference is still synchronous, so very slow model replies can approach LINE's reply-token time limit.
- Loading animation and async queue are planned for a later milestone.

## 中文说明

这个目录是 RoleWeaver 的 LINE 官方账号接入层。当前目标是先跑通自动文字回复：

1. 用户给 LINE 官方账号发文本。
2. LINE 调用我们的 `POST /callback`。
3. `line/app.py` 校验签名。
4. RoleWeaver 按 LINE 用户/群/房间创建独立记忆。
5. 通过 LINE Messaging API 回复用户。

你需要在 LINE Developers Console 里拿到：

- `LINE_CHANNEL_SECRET`
- `LINE_CHANNEL_ACCESS_TOKEN`

然后双击：

```text
line/start_line_bot.bat
```

第一次运行会自动生成 `line/.env` 并用记事本打开。填好两个 LINE 凭证后重新运行即可。默认配置文件是：

```text
line/roleweaver.line.config.csv
```

它已经指向：

- 底模：`C:\Users\kator\Desktop\RoleWeaver\Qwen3.5-4b`
- LoRA：`C:\Users\kator\Desktop\RoleWeaver\outputs\4B-hmsz\checkpoint-250`
- Skill：`C:\Users\kator\Desktop\RoleWeaver\skillcreater\characters\Hataya-Misuzu\skill\SKILL.md`

### 早上 7 点叫醒

在 `line/.env` 里打开：

```dotenv
ROLEWEAVER_WAKEUP_ENABLED=1
ROLEWEAVER_WAKEUP_TIME=07:00
ROLEWEAVER_WAKEUP_TIMEZONE=Asia/Tokyo
```

然后在 LINE 里给官方账号发：

```text
/wake on
```

如果要语音叫醒，先启动：

```text
G/start_roleweaver_tts_api.bat
```

再设置：

```dotenv
ROLEWEAVER_WAKEUP_VOICE=1
ROLEWEAVER_REPLY_VOICE=1
ROLEWEAVER_PUBLIC_BASE_URL=https://你的当前公网地址
ROLEWEAVER_TTS_REFER_WAV_PATH=C:\path\to\reference.wav
ROLEWEAVER_TTS_PROMPT_TEXT=参考音频里说的话
ROLEWEAVER_TTS_PROMPT_LANGUAGE=ja
ROLEWEAVER_TTS_TEXT_LANGUAGE=ja
```

`ROLEWEAVER_PUBLIC_BASE_URL` 使用和 Webhook 同一个 Cloudflare/ngrok 地址，但不要加 `/callback`。

`ROLEWEAVER_REPLY_VOICE=1` 会让普通聊天回复优先走语音；`/ping`、`/help`、`/status`、`/wake on` 这类调试命令仍然用文字，方便排错。

### Surface Policy 文件

M6.1 增加了集中策略文件：

```dotenv
ROLEWEAVER_SURFACE_POLICY_FILE=line\surface_policy.json
```

老的 `.env` 变量仍然优先生效；如果没写 env，就读取 JSON。你可以在这个文件里统一改 LINE 生成长度、图片提示、白天文字模式、语音触发词、wake-up 时间和叫醒提示词。

### 白天文字模式

如果想在每天 08:00 到 17:30 默认不合成语音，只在用户明确要求时合成一次，设置：

```dotenv
ROLEWEAVER_REPLY_VOICE=1
ROLEWEAVER_VOICE_TEXT_ONLY_WINDOW_ENABLED=1
ROLEWEAVER_VOICE_TEXT_ONLY_START=08:00
ROLEWEAVER_VOICE_TEXT_ONLY_END=17:30
ROLEWEAVER_VOICE_TEXT_ONLY_TIMEZONE=Asia/Tokyo
```

这段时间内，普通回复走文字；用户用中文、日语或英语明确要求“语音/音声/voice/audio”等时，只为当前这一轮合成一次语音。

本地服务默认端口是 `8010`，健康检查是：

```text
http://127.0.0.1:8010/health
```

LINE 控制台里的 Webhook URL 不能填本地地址，需要用 Cloudflare Tunnel、ngrok 或 VPS 反代得到公网 HTTPS 地址，然后填：

```text
https://你的公网域名/callback
```
