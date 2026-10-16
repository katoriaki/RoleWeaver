# Unity Companion Client 设计方案

Unity 可以作为 RoleWeaver 的外部表现客户端，负责 Live2D/3D 形象、动画、空间交互和实验可视化。RoleWeaver 提供模型推理、Memory OS、学习流程、adapter 工具与受控工具调用。本仓库的 HTTP 接口可供客户端接入；Unity 工程和形象资产需单独实现及配置。

## 客户端模块

建议工程位置：`unity/RoleWeaverCompanion`。

- `RoleWeaverApiClient.cs`：连接 `/health`、`/chat`、`/chat/image`、`/learning/status` 和 `/learning/run-once`。
- `AvatarStateController.cs`：处理客户端动画、表情和姿态状态。状态协议与模型参数映射由客户端定义，不依赖特定角色的认知运行时。
- `LearningPanel.cs`：显示学习阶段、主题、笔记和adapter候选样本。
- `ToolActionPanel.cs`：显示允许调用的工具以及执行结果，按工具策略处理确认。
- `ReinforcementSandbox.cs`：可作为后续state、action、reward和trajectory的实验界面；尚需独立实现与验证。

## 形象显示

可使用 VTube Studio 渲染 Live2D，或在Unity中集成Live2D Cubism/VRM等适用SDK。模型、表情、动作与许可证由用户自行准备。服务端接口与模型渲染保持独立，客户端显示故障不应修改角色canon。

## 交互边界

```text
Unity interaction
  -> client event
  -> RoleWeaver API / controlled tool request
  -> policy checks and confirmation when required
  -> action
  -> outcome record
```

客户端不能把场景观察直接写成角色身份。交互事件、用户记忆与角色定义应分别处理。强化学习或行为策略实验应使用隔离会话，保留原角色配置和对照记录。
