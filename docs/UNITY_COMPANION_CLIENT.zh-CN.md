# Unity 版 Companion Client 方案

可以做 Unity 开发，而且这个方向适合后续扩展到强化学习、空间交互、桌面常驻和更复杂的 Live2D/3D 表现。

当前建议不是立刻替换 RoleWeaver，而是把 Unity 作为新的“外显客户端”：

```text
RoleWeaver / Shiro 后端
  - LLM 推理
  - Memory OS
  - emotion state machine
  - learning runtime
  - adapter bank
  - tool guard

Unity Companion Client
  - Live2D/3D 形象
  - 状态机动画
  - 桌面宠物窗口
  - 交互事件采集
  - RL/behavior sandbox UI
```

## 第一版 Unity 模块

建议 Unity 工程放在：

```text
unity/RoleWeaverCompanion
```

核心 C# 模块：

- `RoleWeaverApiClient.cs`
  - 调 `/health`
  - 调 `/chat`
  - 调 `/chat/image`
  - 调 `/sessions/{id}/shiro`
  - 调 `/learning/status`
  - 调 `/learning/run-once`

- `ShiroStateController.cs`
  - 读取 Shiro `emotion.primary`
  - 读取 `live2d.expression`
  - 控制 Live2D 表情、动作、参数

- `LearningPanel.cs`
  - 启动/停止学习
  - 显示阶段、题目、学习笔记、adapter 候选样本路径

- `ToolActionPanel.cs`
  - 只显示白名单工具
  - 外部动作必须要求确认

- `ReinforcementSandbox.cs`
  - 后续接 RL 时放 reward、trajectory、policy candidate
  - 不直接改人格核心

## 为什么 Unity 更适合后续强化学习

Web 前端适合配置、调试和文本工作流；Unity 更适合：

- 长时间运行的桌面实体；
- Live2D/3D 动画、动作混合、状态机；
- 空间化交互，例如点击、拖拽、注视、距离；
- 多模态输入，例如摄像头、麦克风、屏幕区域；
- 强化学习可视化，例如 state、action、reward、episode；
- 行为实验沙盒，不直接污染正式人格。

## 与 VTube Studio 的关系

短期：

- 继续用 VTube Studio 渲染 Live2D；
- RoleWeaver Web 前端通过 VTS API 控制表情；
- Unity 可以先只做状态面板。

中期：

- Unity 接 Live2D Cubism SDK for Unity；
- VTube Studio 变成可选；
- Shiro 的 `live2d` 信号直接映射到 Unity Animator / Cubism 参数。

长期：

- Unity 作为白的主外显层；
- RoleWeaver 作为本地大脑服务；
- Shiro 作为认知/情绪/成长状态；
- RL sandbox 只训练行为策略，不直接覆盖核心人格。

## 关键边界

Unity 不能直接让模型任意执行外部动作。它只能提交“意图”和“观察”，最终仍应经过 RoleWeaver 的 tool guard：

```text
Unity interaction
  -> stimulus
  -> Shiro state update
  -> tool intention
  -> risk check
  -> user confirmation if needed
  -> action
  -> outcome memory
```

这能保证白更像一个会行动的人，而不是失控的脚本集合。
