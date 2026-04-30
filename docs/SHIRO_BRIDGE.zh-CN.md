# Shiro Bridge

Shiro Bridge 是 RoleWeaver 与独立 `shiro/` 项目的软连接层。

它的目标是完成 M6.2：

- RoleWeaver 读取 Shiro 的 `thought_context`；
- 聊天后把用户输入和模型回复作为 stimulus 回写 Shiro；
- 前端可以查看白的当前认知状态；
- 保持 Shiro 项目独立，不把 Shiro 源码复制进 RoleWeaver。

## 配置项

在 `roleweaver.config.csv` 中：

```csv
shiro_enabled,true,Enable Shiro cognitive-state bridge
shiro_root,shiro\data\roleweaver,Directory where Shiro stores session cognitive state
shiro_identity,白,Cognitive identity name
```

默认 `shiro_enabled=false`，所以未启用时不会影响 RoleWeaver 和 LINE bot。

## 数据隔离

当前 bridge 采用 session scope：

```text
shiro_root/
  sessions/
    <session_id>/
      cognitive_state.json
      state_transitions.jsonl
```

这样可以避免不同 RoleWeaver 会话、不同角色、不同实验互相污染。未来如果要让“白”成为跨会话的唯一人格，可以把 scope 策略改成 global。

## Prompt 注入

在 role mode 下，RoleWeaver 会读取：

```python
runtime.export_packet()["thought_context"]
```

并把它作为当前认知状态加入 system prompt。这个 context 只能引导当下思考，不能覆盖 persona core、skill 或角色自主性。

## 回写

聊天成功后，RoleWeaver 会调用：

```python
observe_chat_turn(session_id, user_text, assistant_text, surface="web")
```

看图聊天会使用 `surface="image"`。

## API

### `GET /sessions/{session_id}/shiro`

读取当前 session 的 Shiro 状态。

### `POST /sessions/{session_id}/shiro/observe`

手动写入一个 stimulus。

```json
{
  "text": "帮我计划一下今天。",
  "source": "manual",
  "metadata": {}
}
```

### `POST /sessions/{session_id}/shiro/tool-intentions`

让 Shiro 先推断工具意图，不直接执行工具。

```json
{
  "text": "帮我读 C:\\docs\\paper.pdf，并上网搜解法",
  "metadata": {}
}
```

当前会返回 `document.pdf_read` 和/或 `planning.web_search` 意图。PDF 是本地读取，web search 是外部网络动作，默认需要确认。

## 工具执行

RoleWeaver 工具层当前提供：

- `document.pdf_read`：读取用户提供的本地 PDF，返回抽取文本和 `memory_policy`。
- `planning.web_search`：搜索网页资料，结果保留标题与 URL。

## 前端

一站式前端新增“白”页面：

- 查看 enabled/available/identity；
- 查看 thought context；
- 查看 `cognitive_state.json` 内容；
- 查看最近状态转移；
- 手动写入 stimulus。
