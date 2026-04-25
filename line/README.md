# LINE Bot 接入说明 / LINE Bot Integration Guide

## 1. 目标 / Goal

中文：  
这份文档说明如何把 RoleWeaver 本地角色对话系统挂到 LINE Messaging API 上，作为一个可接收文本消息并回复的 LINE Bot。

English:  
This document explains how to connect the local RoleWeaver role chat system to the LINE Messaging API as a LINE bot that receives text messages and replies to them.

## 2. 本次新增文件 / New Files

- `app.py`
- `requirements.txt`
- `.env.example`

中文：  
LINE 相关代码都收在 `line/` 目录中，本地 CLI 入口是项目根目录的 `local_chat.py`。

English:  
All LINE-specific code now lives under the `line/` directory, while the local CLI entry is `local_chat.py` at the project root.

## 3. 架构说明 / Architecture

中文：  
为了让 CLI、本地调试和 LINE 机器人共用一套核心逻辑，核心运行时在 `role_chat_service.py`：

- 模型和 tokenizer 只加载一次
- 不同 LINE 用户使用不同的 `session_id`
- 每个用户的记忆会落到独立目录，避免串号

LINE webhook 流程如下：

1. 用户给 LINE 官方账号发消息
2. LINE 平台向你的 `/callback` 发送 webhook
3. `line/app.py` 验证签名
4. 解析文本消息事件
5. 根据 `user_id / group_id / room_id` 生成 session id
6. 调用 `RoleChatService.chat_once()`
7. 把结果通过 Messaging API reply 回用户

English:  
To let the CLI, local debugging, and LINE bot share the same core logic, the runtime lives in `role_chat_service.py`:

- the model and tokenizer are loaded only once
- different LINE users get different `session_id`s
- each user gets isolated memory files to avoid memory leakage across users

The LINE webhook flow is:

1. A user sends a message to your LINE Official Account
2. LINE sends a webhook to your `/callback`
3. `line/app.py` verifies the signature
4. It parses text message events
5. It builds a session id from `user_id / group_id / room_id`
6. It calls `RoleChatService.chat_once()`
7. It replies to the user through the Messaging API

## 4. 环境变量 / Environment Variables

参考文件 / Reference file: `line/.env.example`

- `LINE_CHANNEL_SECRET`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `ROLEWEAVER_CONFIG_FILE`
- `ROLEWEAVER_IDLE_CONSOLIDATION_SECONDS`
  - `0` means disable idle auto consolidation

角色本身只需要在 `roleweaver.config.csv` 里填写：

- `base_model_path`
- `lora_path`
- `skill_file`

## 5. 安装依赖 / Install Dependencies

```powershell
& '.\.venv\Scripts\python.exe' -m pip install -r line\requirements.txt
```

## 6. 启动服务 / Run the Service

```powershell
& '.\.venv\Scripts\python.exe' -m uvicorn line.app:app --host 0.0.0.0 --port 8000
```

健康检查地址 / Health check:

- `GET http://127.0.0.1:8000/health`

Webhook 地址 / Webhook endpoint:

- `POST http://127.0.0.1:8000/callback`

## 7. LINE 控制台配置 / LINE Console Setup

中文：

1. 创建或打开你的 LINE Official Account / Messaging API Channel
2. 获取：
   - Channel secret
   - Channel access token
3. 在 Messaging API 设置页启用 `Use webhook`
4. 把 Webhook URL 设置为：
   - `https://你的公网域名/callback`
5. 点击 LINE Developers Console 里的 `Verify`

注意：

- LINE 验证 webhook 时可能发送 `events: []`
- 你的服务必须也对这种请求返回 `200`

English:

1. Create or open your LINE Official Account / Messaging API channel
2. Get:
   - Channel secret
   - Channel access token
3. Enable `Use webhook` in the Messaging API settings
4. Set the webhook URL to:
   - `https://your-public-domain/callback`
5. Click `Verify` in the LINE Developers Console

Note:

- LINE may send an empty webhook with `events: []`
- your server must also return `200` for that request

## 8. 本地开发建议 / Local Development Tips

中文：  
如果你本机没公网地址，可以先用反向隧道工具暴露本地 `8000` 端口，例如：

- Cloudflare Tunnel
- ngrok

然后把 HTTPS 的公网地址填进 LINE Developers Console。

English:  
If your local machine doesn't have a public URL, expose local port `8000` using a tunnel tool such as:

- Cloudflare Tunnel
- ngrok

Then register the HTTPS public URL in the LINE Developers Console.

## 9. 现在这版的限制 / Current Limitations

中文：

- 当前只处理文本消息
- 群聊/房间消息会按 `group_id/room_id + user_id` 做 session 区分
- 模型推理是同步执行的，回复慢时 webhook 处理也会变慢
- 还没有做异步队列、typing/loading 提示、图片/语音处理

English:

- Only text messages are handled for now
- Group/room sessions are isolated by `group_id/room_id + user_id`
- Model inference is synchronous, so slow generation also slows webhook handling
- No async queue, typing/loading indicator, or media handling is implemented yet

## 10. 下一步建议 / Suggested Next Steps

中文：

1. 增加 LINE 友好回复策略，例如超长消息分段、欢迎语、错误兜底
2. 加异步任务队列，避免 webhook 卡太久
3. 加管理命令，例如只允许你本人在 LINE 中使用 `/mem` 系列命令
4. 加白名单/管理员校验，避免陌生人污染记忆

English:

1. Add LINE-friendly reply strategies such as chunked long replies, welcome text, and better fallback errors
2. Add an async task queue so webhook handling doesn't block for too long
3. Add admin-only command controls for `/mem`-style commands
4. Add allowlists/admin checks to prevent strangers from polluting memory
