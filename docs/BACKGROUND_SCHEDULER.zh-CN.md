# RoleWeaver 单卡常驻后台调度设计

RoleWeaver 的目标环境是“一张显卡，长时间常驻”。因此后台任务必须服从一个原则：实时对话优先，后台智能后置。

## 分层

### 实时路径

用户正在 Web / LINE / 图片 / 语音聊天时，只做必要工作：

- 读取当前会话的短期上下文；
- 检索已经整理好的长期记忆；
- 注入 planning 和 persona anchor；
- 调用当前模型生成回复；
- 记录 pending turns。

实时路径不主动跑长反思、不批量整理、不做 persona regression。

### 空闲路径

空闲路径由 `background_scheduler.py` 控制，满足条件后才运行：

- 距离最后一次用户请求超过 `background_idle_seconds`；
- 当前时间落在 `background_window_start` 到 `background_window_end`；
- 后台未暂停；
- 如果任务需要 LLM，必须显式开启 `background_llm_enabled`。

默认配置对单卡更保守：轻任务启用，LLM 后台任务关闭。

## 当前任务类型

| job_type | 是否需要 LLM | 用途 |
| --- | --- | --- |
| `planning_regenerate` | 否 | 重新生成当前 memory scope 的本周角色日程 |
| `memory_os_snapshot` | 否 | 读取当前会话 Memory OS 快照，辅助检查 |
| `release_inactive_models` | 否 | 释放非当前活跃模型，降低显存压力 |
| `memory_consolidation` | 是 | 整理 pending turns，并运行记忆维护、反思和遗忘策略 |

后续 A-Mem、Anchor 刷新、Persona Regression 都应接入这个调度器，而不是直接在聊天路径里运行。

## 自动 tick

FastAPI 启动后会启动一个轻量后台线程，默认每 60 秒检查一次。可以通过环境变量调整：

- `ROLEWEAVER_BACKGROUND_WORKER=0`：完全关闭自动 tick；
- `ROLEWEAVER_BACKGROUND_TICK_SECONDS=120`：修改检查间隔，最小 15 秒。

自动 tick 当前策略：

- 如果满足非 LLM 空闲条件，最多每 6 小时为最近会话执行一次 `planning_regenerate`；
- 如果同时满足 LLM 空闲条件，最多每 1 小时为最近会话执行一次 `memory_consolidation`；
- `background_llm_enabled=false` 时不会自动调用模型。

也就是说，默认单卡常驻时，自动后台只会做轻量 planning 刷新，不会在白天抢占模型。

## API

### `GET /background/status`

返回后台调度状态：

- `config`
- `paused`
- `idle_seconds`
- `eligible_non_llm`
- `eligible_llm`
- `active_job`
- `recent_jobs`

### `POST /background/pause`

暂停后台任务。

### `POST /background/resume`

恢复后台任务。

### `POST /background/run-once`

手动运行一次后台任务。

```json
{
  "job_type": "planning_regenerate",
  "session_id": "20260429-120000",
  "force": true
}
```

`force=true` 只跳过空闲时间和时间窗口限制，不会绕过 `background_llm_enabled=false`。也就是说，LLM 后台任务仍然需要用户明确开启。

## 前端

Vue 控制台新增“后台任务”页面：

- 查看 idle 秒数和运行资格；
- 暂停/恢复后台调度；
- 手动运行 planning、memory snapshot、memory consolidation、释放模型；
- 查看最近任务记录。

Runtime 设置页新增后台参数，所有参数都写入 `roleweaver.config.csv`，不需要用户改代码。
## Autonomous Learning / A-Mem Growth Loop

The `autonomous_learning` job adds the idle learning loop used by Shiro.

When the scheduler has been idle for `background_idle_seconds`, the current time is inside the configured background window, and `background_llm_enabled=true`, RoleWeaver can run:

1. memory consolidation for the latest session;
2. current weekly schedule and anchor refresh;
3. autonomous web search for the configured interests;
4. model-generated study notes;
5. Shiro stimulus write-back, so the learning step can affect emotion, memory, reflection, and future adapter candidates.

New config keys:

- `autonomous_learning_enabled`
- `autonomous_learning_subjects`
- `autonomous_learning_interval_seconds`
- `autonomous_learning_use_model`
- `autonomous_learning_max_new_tokens`

For the A800 profile, this is enabled with `background_idle_seconds=180`, all-day background window `00:00-00:00`, and subjects `mathematics, computer science`.
