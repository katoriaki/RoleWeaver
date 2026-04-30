# RoleWeaver 工具层

工具层是 RoleWeaver 后续“像人一样调用工具”的入口。当前版本先实现受控白名单、统一 API 和调用日志，不让模型直接执行任意命令。

## 设计原则

- **白名单优先**：所有工具必须在 `ToolRuntime` 中显式注册。
- **参数校验**：每个工具提供一个简化 JSON Schema，拒绝缺少参数、类型错误和多余参数。
- **全量留痕**：每次调用都会写入 `data/tool_actions/actions.jsonl`。
- **轻重分离**：工具会标注是否 `requires_llm`、是否 `mutates`，便于单卡常驻时做调度和确认。
- **会话隔离**：记忆、规划类工具必须带 `session_id`，不会把一个角色/会话的状态错接到另一个会话。

## API

### `GET /tools`

列出当前可用工具。

### `POST /tools/run`

请求体：

```json
{
  "tool_name": "runtime.time_now",
  "session_id": "web",
  "actor": "user",
  "arguments": {}
}
```

返回值包含 `id`、`status`、`duration_ms`、`result` 或 `error`。

### `GET /tools/actions?limit=50`

读取最近的工具调用日志。

## 当前工具

- `runtime.time_now`：读取设备时间、时区、本地地点。
- `runtime.health`：读取轻量运行状态，不强制加载模型。
- `config.read`：读取当前配置。
- `planning.current`：读取或重新生成当前角色日程和 anchor。
- `planning.web_search`：做参考资料搜索。
- `memory.search`：查询当前 session 的记忆。
- `memory.os_snapshot`：读取 Memory OS 快照。
- `memory.consolidate`：手动整理当前 session 记忆，可能调用本地大模型。
- `background.status`：读取后台调度状态。
- `background.run_once`：手动执行一个白名单后台任务。
- `integration.line_status`：读取 LINE bot 运行状态。
- `integration.tunnel_status`：读取公网临时 tunnel 状态。
- `training.status`：读取 LoRA 训练状态。

## 下一步

下一步可以把工具层接进角色运行时，但建议分级：

- 只读工具可自动调用，例如时间、日程、记忆查询。
- 会改变状态的工具需要策略判断，例如整理记忆、后台任务。
- 外部通信工具需要用户确认，例如 LINE push、文件写入、未来的系统命令。
