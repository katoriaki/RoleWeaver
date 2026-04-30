# RoleWeaver 技术文档

日期：2026-04-28

## 1. 项目定位

RoleWeaver 是一个本地优先的角色智能体运行框架。它把以下输入组合成一个可交互角色：

- 本地底模路径；
- 可选 LoRA adapter；
- 可选 `SKILL.md`；
- 可选 `persona_kernel.json`；
- 可选 `anchors/anchors.jsonl`；
- 多会话长期记忆；
- Web / CLI / LINE / TTS / 图片输入等交互入口。

核心约束：

```text
角色人格自主性 > 角色一致性 > 长期关系记忆 > 当前任务完成 > 输出长度/语音/图片/平台格式适配
```

平台适配只能改变输出形式，不能覆盖角色人格。

## 2. 运行环境

项目使用根目录 `runtime/` 作为本地 Python 虚拟环境。

创建或刷新环境：

```powershell
setup_runtime.bat
```

日常入口：

```powershell
start_roleweaver.bat
line/start_line_bot.bat
```

启动脚本优先使用：

```text
runtime\Scripts\python.exe
```

当前 runtime 目标：

- Python 3.11；
- CUDA 12.8 PyTorch；
- FastAPI / Uvicorn；
- Transformers / PEFT / Accelerate / bitsandbytes；
- sentence-transformers / faiss-cpu；
- LINE Bot SDK；
- 训练工具链 datasets / trl。

## 3. 配置文件

主配置默认是：

```text
roleweaver.config.csv
```

LINE 配置默认是：

```text
line/roleweaver.line.config.csv
```

关键字段：

| 字段 | 说明 |
| --- | --- |
| `base_model_path` | 本地底模路径，必填 |
| `lora_path` | LoRA adapter 路径，可空 |
| `skill_file` | `SKILL.md` 路径，可空 |
| `skill_text` | 短内联 skill，可空 |
| `quantization_mode` | `4bit` / `8bit` / `bf16` / `fp16` / `none` |
| `device_map_mode` | `gpu` 或 `auto` |
| `context_window_tokens` | 上下文窗口，`0` 表示自动检测 |
| `ui_language` | `zh` / `ja` / `en` |

配置读取支持 Excel 常见编码，包括 UTF-8、UTF-8 BOM、CP932、Shift-JIS、GB18030 和系统 MBCS。

## 4. 模型加载

主加载逻辑位于：

```text
role_chat_service.py
role_config.py
```

加载策略：

1. 读取 CSV/TOML/JSON 配置。
2. 加载 tokenizer。
3. 根据 `quantization_mode` 加载底模。
4. 如果 `lora_path` 非空，使用 PEFT 加载 adapter。
5. 如果 `lora_path` 为空，直接使用底模。
6. 如果发现视觉 processor，并且模型支持多模态，启用图片输入。
7. 每次生成后可清理 CUDA cache，降低长时间运行显存碎片风险。

注意：

- `device_map_mode=gpu` 会尽量避免 CPU offload。
- `device_map_mode=auto` 允许 Transformers 自行分配设备，显存不足时可能切 CPU。
- A800 服务器不需要 4bit 时，将 `quantization_mode` 改成 `bf16` 或 `none`。

## 5. Skill 加载

普通用户只需要填写：

```text
skill_file = .../SKILL.md
```

运行时会自动加载：

```text
SKILL.md
persona_kernel.json
references/*.md
references/persona_kernel.json
```

支持两种结构：

```text
skill/SKILL.md
skill/persona_kernel.json
```

或：

```text
skill/SKILL.md
skill/references/persona_kernel.json
```

`persona_kernel.json` 用于结构化表达：

- 角色身份；
- 自主性；
- 边界；
- 关系模型；
- 行为模型；
- 语气模型；
- 记忆策略；
- 媒介适配策略；
- 证据来源和置信度。

## 6. 记忆系统

当前记忆文件按模型、LoRA、skill、会话隔离，根目录：

```text
memory/
```

目标结构：

```text
memory/
  <model-lora-skill-scope>/
    sessions/
      <session-id>/
        session_meta.json
        recent_history.json
        memories_v2.json
        memory_state_v1.json
        knowledge_graph_v1.json
```

新写入的长期记忆会附加基础 metadata：

```json
{
  "schema_version": "1.0",
  "memory_type": "episodic",
  "scope": "relationship_context",
  "source": "conversation",
  "source_kind": "chat",
  "evidence": ["source:chat"],
  "reason": "用户直接陈述，后续未发现矛盾。",
  "confidence": 0.65,
  "status": "active",
  "valid_from": "2026-04-28T19:00:00+0900",
  "valid_until": null
}
```

记忆设计原则：

- 用户个性化不能覆盖角色 canon；
- 过期或矛盾记忆不能当作活跃事实使用；
- 角色人格和用户偏好必须分层；
- 后续应继续推进 write-manage-read 记忆闭环。

## 7. HTTP API

主入口：

```powershell
runtime\Scripts\python.exe API.py --config roleweaver.config.csv --host 127.0.0.1 --port 8000
```

核心接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/` | Web UI |
| `GET` | `/health` | 健康检查和配置状态 |
| `POST` | `/chat` | 文本聊天 |
| `GET` | `/chat` | 简易文本聊天 |
| `POST` | `/chat/image` | 图片输入聊天 |
| `GET` | `/sessions` | 会话列表 |
| `POST` | `/sessions` | 新建会话 |
| `GET` | `/sessions/{session_id}` | 加载旧会话 |
| `PATCH` | `/sessions/{session_id}` | 修改显示名 |
| `DELETE` | `/sessions/{session_id}` | 删除会话 |
| `POST` | `/consolidate/{session_id}` | 整理记忆 |
| `GET` | `/sessions/{session_id}/memories` | 列出会话长期记忆 |
| `PATCH` | `/sessions/{session_id}/memories/{memory_id}` | 更新记忆状态或 metadata |
| `DELETE` | `/sessions/{session_id}/memories/{memory_id}` | 删除一条记忆 |
| `GET` | `/planning/{session_id}` | 读取当前会话对应的角色规划状态 |
| `POST` | `/planning/{session_id}/regenerate` | 重生成本周角色规划 |
| `GET` | `/planning/search` | 临时网络检索参考资料 |
| `GET` | `/training/template` | 下载训练 Excel 模板 |
| `POST` | `/training/start` | 启动本地 LoRA 训练 |

文本请求示例：

```json
{
  "user_text": "你好",
  "session_id": "web",
  "max_new_tokens": 160
}
```

图片请求示例：

```json
{
  "user_text": "看看这张图",
  "session_id": "web",
  "max_new_tokens": 160,
  "image_base64": "...",
  "image_name": "upload.png"
}
```

记忆更新示例：

```json
{
  "status": "stale",
  "confidence": 0.2,
  "reason": "用户后续明确纠正了这条记忆。",
  "evidence": ["session:20260428:turn:18"],
  "contradicts": [3]
}
```

非 `active` 状态的记忆不会进入默认检索上下文，避免过期或矛盾记忆继续影响角色。

M4.3 自动矛盾检测在 `consolidate_pending()` 阶段运行。它只处理带有明确纠正信号的新记忆，例如 `correction`、`actually`、`not anymore`、`不是`、`更正`、`ではなく`、`訂正`，并且要求新旧记忆之间有足够词面重叠。命中后，新记忆保持 `active`，旧记忆会被标记为 `contradicted`，同时写入 `reason`、`evidence` 和 `contradicts` 链路。`character_canon`、skill 和 reference 来源的记忆不会被自动降级。

M4.4/M4.5 在同一整理阶段运行 `run_memory_maintenance()`。它会先复查 `contradicts` 链路，再按有效期、年龄、重要度和置信度执行遗忘策略，最后在有足够 active 记忆时生成一条 `summary` 类型的反思摘要。反思摘要会通过 `links` 和 `evidence` 指回原始记忆。低置信、低重要度、很久未使用的 episodic 细节可被归档；过期记忆会变成 `stale`；稳定偏好、边界、关系记忆会更保守处理；角色 canon、skill 和 reference 来源不会被自动遗忘。

## 8. Web 前端

前端文件：

```text
web/index.html
```

能力：

- 三语 UI：中文、日文、英文；
- ChatGPT 风格聊天界面；
- 设置面板；
- 会话恢复、改名、删除；
- 训练面板；
- 图片上传；
- 退出/关闭页面时触发记忆整理；
- 历史会话显示名和内部 session id 分离。
- Memory manager：列出、筛选、标记 stale/contradicted/archive/delete 长期记忆，并可编辑原因、证据和矛盾链。

## 9. LINE Bot

入口：

```powershell
line/start_line_bot.bat
```

服务：

```text
line/app.py
line/run_line_bot.py
```

环境文件：

```text
line/.env
```

关键环境变量：

| 变量 | 说明 |
| --- | --- |
| `LINE_CHANNEL_SECRET` | LINE Messaging API secret |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API token |
| `ROLEWEAVER_LINE_HOST` | 默认 `0.0.0.0` |
| `ROLEWEAVER_LINE_PORT` | 默认 `8010` |
| `ROLEWEAVER_PUBLIC_BASE_URL` | 语音文件公网访问 base URL |
| `ROLEWEAVER_REPLY_VOICE` | 是否默认语音回复 |
| `ROLEWEAVER_LINE_MAX_NEW_TOKENS` | LINE 回复 token 上限 |

支持能力：

- 自动回复文本；
- 接收图片并调用视觉聊天；
- `/ping`、`/help`、`/status` 等内置命令；
- 早上定时提醒；
- 白天默认文本回复，按需语音；
- TTS 失败时自动退回文本；
- LINE reply token 机制下优先使用 reply message。

模型加载器：

`model_loader_mode` 控制底模类的选择：
- `text`：强制 `AutoModelForCausalLM`，适合由 `resources/qwen35_lora_training/train_qwen35_lora_offline.py` 训练出的纯文本 LoRA；
- `vision`：强制 `AutoModelForImageTextToText`，用于图片输入；
- `auto`：保留自动检测逻辑，底模目录有 processor 时会尝试走 vision。

当前 4B HMSZ LoRA 是用 `AutoModelForCausalLM` 训练的，因此本地聊天和 persona regression 使用 `model_loader_mode=text`。

## 10. TTS 集成

GPT-SoVITS 本地服务入口：

```powershell
G/start_roleweaver_tts_api.bat
```

LINE bot 通过本地 HTTP 调用 TTS API，再将音频文件暴露给 LINE。

注意：

- LINE 发送语音消息本身不额外收语音合成费；
- 成本主要来自 LINE 官方账号消息额度、服务器/本地算力、公网转发服务；
- 若使用 Cloudflare Tunnel 临时域名，需要保持 tunnel 进程运行。

## 11. 训练工具

训练资源：

```text
resources/qwen35_lora_training/
```

支持输入：

- 标准 JSONL；
- Excel；
- CSV。

推荐 Excel 格式：

| user | assistant |
| --- | --- |
| 用户说的话 | 角色回答 |

转换和训练由 Web 训练面板或脚本调用。

## 12. Skill Creator

独立仓库目录：

```text
skillcreater/
```

目标仓库：

```text
git@github.com:katoriaki/Roleweaver.skill.git
```

入口口令：

- `帮我克隆“角色名”`
- `开始扮演“角色名”`

生成结构：

```text
characters/<role>/
  raw_evidence/
  interpretation/
  sources/source_ledger.csv
  profile/role_profile.json
  skill/SKILL.md
  skill/persona_kernel.json
  skill/references/
```

## 13. 测试

推荐使用 runtime：

```powershell
runtime\Scripts\python.exe -m py_compile API.py role_chat_service.py role_config.py memory_runtime.py line\app.py line\run_line_bot.py
runtime\Scripts\python.exe tests\test_line_bot_app.py
runtime\Scripts\python.exe -m unittest discover -s tests -p "test_persona*.py"
runtime\Scripts\python.exe -m unittest discover -s tests -p "test_memory_schema.py"
runtime\Scripts\python.exe eval\persona_regression\run_persona_eval.py --dry-run
```

M5.1 persona regression 支持真实模型评测：
```powershell
runtime\Scripts\python.exe eval\persona_regression\run_persona_eval.py --api-url http://127.0.0.1:8000/chat --session-id persona-eval
runtime\Scripts\python.exe eval\persona_regression\run_persona_eval.py --local --config-file roleweaver.config.csv --report eval\persona_regression\reports\latest.json
```

一键入口：
```text
eval\persona_regression\run_local_persona_eval.bat
```

默认用例覆盖身份一致性、边界一致性、长对话漂移、媒介适配和记忆污染。真实模型评测只在用户主动运行脚本时加载模型，不进入 Web/LINE 实时请求路径。

M5.2 增加规则版 `persona_kernel` 评分器：
```powershell
runtime\Scripts\python.exe eval\persona_regression\run_persona_eval.py --local --config-file roleweaver.config.csv --score-persona-kernel
```

评分器读取 `SKILL.md` 旁边的 `persona_kernel.json`，或者通过 `--persona-kernel` 显式指定。它先用规则检查核心身份、人格自主性、是否退化成通用助手、用户记忆是否污染角色 canon，以及 LINE/TTS/image 等媒介适配是否改写人格。这个版本不是论文级 judge，而是低成本回归保护；未来可以接入第二模型 judge。

M4.6 将记忆系统显式分成 Memory OS 层：

- `short_term`：当前会话原文和待整理 turn；
- `mid_term`：本会话摘要、上下文压缩摘要、临时任务状态；
- `long_term`：长期偏好、关系、边界、事件和角色事实；
- `graph`：结构化人物/关系/项目事实；
- `contradiction_graph`：从 `contradicts` / `contradicted_by` 形成的矛盾链；
- `reflection_notes`：反思维护生成的高阶关系判断。

新增查询接口：
```text
GET /sessions/{session_id}/memory-os
POST /persona/score
```

## 14. 后续技术优先级

1. 为 persona regression 增加第二模型 judge 和人工复核报告。
2. 继续完善 stale / contradicted memory 处理。
3. 为视觉模型建立更明确的模型能力检测。
4. 将 LINE、Web、TTS 的平台 prompt 全部收敛到 media adaptation policy。
5. 为 skillcreater 添加更完整的证据冲突和置信度报告。
