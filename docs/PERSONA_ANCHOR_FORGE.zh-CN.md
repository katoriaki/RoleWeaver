# Persona Anchor Forge

Persona Anchor Forge 用于生成白的人格锚点候选，而不是直接改写人格核心。

设计动机来自 EACL 2026 的 `Persistent Personas? Role-Playing, Instruction Following, and Safety in Extended Interactions`：长对话中 persona fidelity 会退化，尤其是目标导向任务会把模型拉向普通助手；persona-directed dialogue 能更好地维持角色特征，但也不能过量使用，否则会牺牲任务能力。

## 流程

1. 读取当前 session 的随机周计划。
2. 判断当前场景，例如上课、吃饭、训练、休息、关系时间。
3. 生成 1-6 轮短的 persona-directed dialogue。
4. 让白自然回答，不暴露开发者模式和内部机制。
5. 从回答中抽取候选锚点，写入：

```text
data/persona_anchors/<session_id>/candidate_anchors.jsonl
```

6. 候选锚点默认 `status=candidate`，需要人工或导师模型审核后才 promote 到正式 skill anchors。

## API

查看候选：

```http
GET /persona-anchors/status?session_id=shiro-study
```

运行一次短对话：

```http
POST /persona-anchors/run
Content-Type: application/json

{
  "session_id": "shiro-study",
  "turns": 3,
  "max_new_tokens": 160,
  "mentor_notes": [
    "不要把亲近写成无条件服从。",
    "优先保留自主性、求知欲、情绪表达和边界。"
  ]
}
```

人工审核后提升为正式 anchor：

```http
POST /persona-anchors/promote
Content-Type: application/json

{
  "session_id": "shiro-study",
  "candidate_id": "shiro-pdialogue-xxxx"
}
```

正式 anchor 会追加到：

```text
skillcreater/characters/Shiro/skill/anchors/anchors.jsonl
```

## 与持续 LoRA 的关系

人格锚点不等于 LoRA。建议分层：

- 人格核心：SKILL.md + persona_kernel.json，极少改。
- 人格锚点：由 persona-directed dialogue 生成，人工审核后加入，低频更新。
- 领域 LoRA：数学、计算机、工具使用、表达风格等，可按领域训练。
- 路由策略：先检索人格锚点，再按任务需要临时加载领域 LoRA；单卡环境下只能切换，不能多个大模型常驻。

不要把所有日常学习都训练进一个总 LoRA。更好的策略是 adapter bank：

- `core-self replay` 永远参与少量回放，防止人格被领域知识覆盖；
- 数学、计算机、工具、表达分别训练小 adapter；
- 每个 adapter 通过 persona regression 后才能启用；
- 对话时根据意图选择 adapter，退出后回到主模型；
- 失败 adapter 可回滚，不覆盖人格核心。

## 使用频率建议

- 普通聊天中随机低频触发，例如每天 2-5 次。
- 只在空闲、切换日程块、睡前整理、学习结束后触发。
- 每次 1-3 轮即可。
- 不要在每轮都注入，否则会让角色显得自我复读。
