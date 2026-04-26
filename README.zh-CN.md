# RoleWeaver

**语言：** [English](README.md) | 中文 | [日本語](README.ja.md)

RoleWeaver 可以把一个底模、一个可选 LoRA adapter、一个可选角色 skill 组合成可复用的本地角色聊天运行时。它包含持久化会话记忆、类 ChatGPT 的本地前端，以及给能本地训练的用户使用的 LoRA 训练工具。

## 最新更新

2026-04-27：

- Windows 启动器会复用已有的 `127.0.0.1:8000` RoleWeaver 服务；如果 8000 被其他程序占用，会自动尝试 `8001-8020`。
- 本地训练面板支持 Excel、CSV、标准 JSONL。
- 新增标准训练模板 `resources/qwen35_lora_training/role_sft_template.xlsx`，只需要两列：`user` 和 `assistant`。
- 新增可编辑会话显示名。内部 `session_id` 继续隐藏，并继续映射原来的 memory 文件夹。
- 历史会话支持恢复、改名、删除和每会话设置快照。

完整更新公告见 [CHANGELOG.md](CHANGELOG.md)。

## 功能概览

- 通过本地底模路径运行角色聊天。
- `lora_path` 不为空时加载 LoRA；为空时直接使用底模。
- 角色行为可以来自 `SKILL.md`，也可以来自短的内联 skill 文本。
- 支持 `4bit`、`8bit`、`bf16`、`fp16`、不量化加载。
- 记忆存储在 `memory/`，按照底模、LoRA、skill、会话隔离。
- 提供 FastAPI API、浏览器前端、CLI 入口和 bot 集成骨架。

## 快速开始

复制配置模板：

```powershell
copy roleweaver.config.example.csv roleweaver.config.csv
```

用 Excel、网页 Settings 面板或文本编辑器填写：

- `base_model_path`
- `lora_path` 可选，留空表示只用底模
- `skill_file` 可选
- `skill_text` 可选，短内联 skill
- `quantization_mode` 默认 `4bit`
- `ui_language`：`zh`、`ja`、`en`

启动 Windows 前端：

```powershell
start_roleweaver.bat
```

或启动 CLI：

```powershell
python local_chat.py --config roleweaver.config.csv
```

## Windows 启动器和网页前端

在项目根目录双击 `start_roleweaver.bat`。

启动器会：

- 如果缺少 `roleweaver.config.csv`，从示例创建；
- 如果当前 Python 环境缺少 `fastapi` 和 `uvicorn`，提示安装；
- 如果 `127.0.0.1:8000` 已经是 RoleWeaver，直接打开现有页面；
- 否则绑定 8000，或自动选择 8001 到 8020 之间的空端口；
- 自动打开本地网页前端。

网页前端支持：

- 中文、日文、英文界面；
- 设置底模、LoRA、skill 文件、内联 skill、量化方式、界面语言；
- 历史会话恢复；
- 可编辑显示名，且不会重命名 memory 文件夹；
- 确认后删除历史会话；
- 退出或关闭页面时整理记忆；
- 使用 Excel、CSV、JSONL 进行本地 LoRA 训练。

## HTTP API

手动启动 API：

```powershell
python API.py --config roleweaver.config.csv --host 127.0.0.1 --port 8000
```

### `GET /`

返回 `web/index.html` 本地网页前端。

### `GET /health`

返回运行状态和当前模型设置。

可选 query：

- `session_id`：提供后，会按照该会话保存的设置快照检查状态。

典型响应字段：

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

生成一次助手回复。

请求体：

```json
{
  "user_text": "你好",
  "session_id": "web",
  "max_new_tokens": 160
}
```

响应：

```json
{
  "text": "...",
  "session_id": "web"
}
```

### `GET /chat`

`POST /chat` 的 query 版本。

示例：

```text
/chat?user_text=你好&session_id=api&max_new_tokens=120
```

### `POST /consolidate/{session_id}`

整理指定会话的记忆，把有价值的 pending turns 写入 episodic memory、图谱事实和用户 profile。

响应：

```json
{
  "result": {}
}
```

### `GET /config`

读取当前可编辑配置。

响应字段：

- `config_file`
- `base_model_path`
- `lora_path`
- `skill_file`
- `skill_text`
- `quantization_mode`
- `ui_language`

### `POST /config`

更新 `roleweaver.config.csv`，并清空进程内 service cache。下一次聊天会按新配置加载模型。

请求体：

```json
{
  "base_model_path": "C:\\models\\base",
  "lora_path": "C:\\models\\adapter",
  "skill_file": "C:\\roles\\SKILL.md",
  "skill_text": "",
  "quantization_mode": "4bit",
  "ui_language": "zh"
}
```

所有字段都是可选的；未传的字段保持原值。

### `GET /sessions`

列出 `memory/` 下发现的持久化会话。

每一项包含：

- `session_id`：内部 ID，用于目录和 API 调用；
- `display_name`：用户可见会话名；
- `created_ts`
- `updated_ts`
- `session_path`
- `memory_scope_path`
- `settings_snapshot`
- `warnings`：模型、LoRA、skill 路径缺失等警告。

### `POST /sessions`

在当前底模/LoRA/skill 的 memory scope 下创建新会话。文件夹仍然基于时间戳；用户可见名称单独保存。

### `GET /sessions/{session_id}`

加载一个会话，包括 transcript 和保存的设置快照。

响应除了 `GET /sessions` 的字段，还包含：

- `messages`
- `config`

### `PATCH /sessions/{session_id}`

修改用户可见的会话名，不重命名会话文件夹，不改变内部 `session_id`。

请求体：

```json
{
  "display_name": "我的角色测试"
}
```

### `DELETE /sessions/{session_id}`

删除 `memory/` 下对应的本机会话文件夹。网页前端会先弹确认。

### `POST /training/start`

以后台子进程启动一个本地 LoRA 训练任务。同一时间 API 只允许一个训练任务。

请求体：

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

支持的 `data_file`：

- `.xlsx`、`.xlsm`、`.xltx`：读取第一个工作表，第一行必须是 `user | assistant`，第二行开始是数据；
- `.csv`：第一行必须是 `user,assistant`；
- `.jsonl`：标准 messages JSONL。

Excel 和 CSV 会先转换到 `training_runs/<run_id>/converted_dataset.jsonl`，再交给训练脚本。

### `GET /training/status`

返回当前或最近一次训练任务状态。

响应字段：

- `active`
- `run_id`
- `status`：`idle`、`running`、`completed`、`failed`
- `returncode`
- `started_ts`
- `command`
- `log_path`
- `log_tail`
- `message`

### `POST /training/stop`

请求终止当前训练子进程。

### `GET /training/template`

下载 `resources/qwen35_lora_training/role_sft_template.xlsx`。

## 训练数据

最简单的输入格式是 Excel 模板：

[resources/qwen35_lora_training/role_sft_template.xlsx](resources/qwen35_lora_training/role_sft_template.xlsx)

表格格式：

```text
user | assistant
你好  | 你好呀...
```

手动转换：

```powershell
python resources\qwen35_lora_training\convert_excel_to_jsonl.py `
  --input "C:\datasets\role_sft.xlsx" `
  --output "C:\datasets\role_sft.jsonl"
```

手动训练：

```powershell
python resources\qwen35_lora_training\train_qwen35_lora_offline.py `
  --model-path "C:\models\base-model" `
  --data-file "C:\datasets\role_sft.jsonl" `
  --output-dir ".\outputs\your-role-lora"
```

对于 Qwen thinking 风格模型，训练脚本在构造 SFT 文本时会关闭 thinking 标签。

## 记忆系统

RoleWeaver 的记忆目录结构：

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

记忆分为：

- 最近对话状态：保持即时连续性；
- episodic memory：保存筛选后的长期事件和偏好；
- graph memory：保存结构化事实；
- profile projection：生成紧凑用户上下文。

如果 embedding 依赖或 embedding 模型不可用，检索会退回 lexical search，不会让聊天服务崩溃。

## Bot 集成

### LINE

LINE 应用在 `line/` 下：

```powershell
uvicorn line.app:app --host 0.0.0.0 --port 8000
```

接口：

- `GET /health`
- `POST /callback`

### QQ 语音 Bot

QQ 语音回复集成在 `QQbot/`。它组合了 QQ bot 事件、到远程 RoleWeaver 文本 API 的 SSH 连接、本地 GPT-SoVITS 语音合成。

```powershell
python -m QQbot.main --config QQbot\qq_voice_bot.config.csv
```

远程最小文本 API：

- `GET /health`
- `POST /chat`

## 注意

- `roleweaver.config.csv` 被 git 忽略，避免提交本机模型路径。
- `memory/`、`training_runs/`、生成输出被 git 忽略。
- 这个项目目前已经是可用的本地框架，但还不是完整打包的桌面应用。
