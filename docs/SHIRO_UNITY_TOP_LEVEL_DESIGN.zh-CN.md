# Shiro Unity 顶层设计

## 目标

Unity 端不是替代 RoleWeaver/Shiro 后端，而是作为白的外显身体、空间环境和未来强化学习沙盒。后端继续负责模型推理、记忆、反思、工具守卫和长期学习；Unity 负责可见世界、动作、表情、环境状态和交互事件。

```text
RoleWeaver / Shiro 后端
  - LLM / VLM 推理
  - Memory OS
  - reflection / planning
  - emotion state machine
  - learning runtime
  - tool intention guard
  - adapter bank

Unity ShirosWorld
  - 3D 世界与桌宠窗口
  - Live2D / 3D avatar 表现
  - 情绪、动作、注视、姿态映射
  - 现实空间/3DGS 资产入口
  - 学习、工具、记忆状态可视化
  - 未来 RL/world-model sandbox
```

## 核心原则

1. **大脑和身体分离**  
   RoleWeaver 是大脑服务，Unity 是身体和世界。Unity 不直接改写人格核心，也不直接执行高风险外部动作。

2. **先意图，后动作**  
   Unity 产生交互刺激或动作请求后，先交给 Shiro/RoleWeaver 形成 tool intention，再经过 risk guard，必要时等待用户确认。

3. **世界状态进入记忆，但不污染人格核心**  
   3D 场景、3DGS、摄像头、点击、距离、时间地点等都作为 stimulus/observation 写入记忆系统。它们可以影响情绪和计划，但不能直接覆盖 core-self/persona kernel。

4. **强化学习只训练行为策略，不直接训练人格核心**  
   RL sandbox 可以训练移动、注视、互动节奏、学习策略等行为层；adapter bank 必须通过 persona regression 才能启用。

5. **可观察优先**  
   每个阶段都要能看到：当前情绪、Live2D/动作信号、学习阶段、工具意图、记忆写入、反思结果。白可以变复杂，但系统不能变黑箱。

## 可交付里程碑

### M1. Unity Bridge Baseline

目标：Unity 能作为 RoleWeaver 的外显控制台启动。

交付：
- 自动创建 Unity 端 RoleWeaver overlay；
- 可配置后端 URL 和 session id；
- 调用 `/health`；
- 调用 `/learning/status`；
- 调用 `/learning/bootstrap-shiro`；
- 调用 `/learning/run-once`；
- 显示 Shiro emotion、Live2D expression/motion、thought policy、学习材料数量和 adapter candidate 路径；
- 将后端状态映射成 Unity 侧 `CompanionPresentationState`。

状态：已完成第一版。

### M2. Embodiment Driver

目标：把 Shiro 的 emotion/live2d 信号接到实际外显模型。

交付：
- Live2D Cubism SDK 接入；
- expression/motion/parameter 映射表；
- 情绪强度到眨眼、口型、姿态、注视的平滑控制；
- VTube Studio 与 Unity Live2D 二选一运行方案；
- 失败时回退到 Unity debug avatar。

### M3. 3D World Shell

目标：构建白可以“生活”的最小 3D 世界。

交付：
- 房间/书桌/学习区域基础场景；
- 角色 anchor 点、相机、交互区域；
- 时间、天气、日程状态可视化；
- 场景事件写入 Shiro stimulus；
- 现实环境资产导入接口预留。

### M4. Spatial Memory / 3DGS Ingest

目标：让现实空间成为可被记忆系统引用的世界层。

交付：
- 3DGS/mesh/point-cloud 资产导入规范；
- 空间对象 registry；
- 视觉识别结果与场景对象绑定；
- “我在哪里看到过什么”的空间记忆；
- 场景变化触发 observation。

### M5. Learning and Planning Console

目标：Unity 能观察并调度白的长期学习。

交付：
- 学习计划、当前材料、阶段、测验结果显示；
- 空闲学习/夜间整理/手动学习控制；
- thought policy 变化记录；
- adapter candidate 生成与评测状态显示。

### M6. Tool Intention Console

目标：Unity 作为工具意图的可视化和确认入口。

交付：
- tool desire / risk / expected outcome 显示；
- 高风险外部动作确认；
- 工具结果进入 memory outcome；
- PDF、网页搜索、文件阅读等工具的 Unity 面板。

### M7. RL / World-Model Sandbox

目标：为未来“像生物一样变化”的行为学习提供可控环境。

交付：
- Unity ML-Agents 或自定义 episode runner；
- observation/action/reward schema；
- 行为策略训练与回放；
- reward 不直接绑定用户依赖；
- persona regression 作为启用门槛；
- 可回滚 policy/adapters。

## M1 验收方式

1. 打开 `shiro/unity/ShirosWorld`。
2. 进入 Play Mode。
3. 场景中自动出现 RoleWeaver overlay。
4. 如果 `API.py` 正在运行，`Refresh` 能显示 online。
5. `Bootstrap Shiro` 能写入白的默认本地配置。
6. `Dry Study Step` 能推进学习 runtime 并更新 Shiro 状态。
7. Overlay 能显示 emotion、expression、motion、learning status。

