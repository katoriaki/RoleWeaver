# Persona Anchors 设计

日期：2026-04-29

## 目标

Persona Anchor Replay 用来缓解长对话中的 persona drift。它不是长期记忆，也不是伪造的新剧情，而是从官方/验证资料中抽取的短人格锚点，在运行时给模型做轻量自我校准。

## 边界

- Anchor 不是用户记忆；
- Anchor 不会写入 long-term memory；
- Anchor 不能覆盖 persona kernel；
- Anchor 不能把 planning state 伪装成官方 canon；
- Anchor 只用于保持口调、判断方式、关系姿态和核心身份。

## 文件位置

RoleWeaver 会自动从 `SKILL.md` 旁边读取：

```text
skill/
  SKILL.md
  persona_kernel.json
  anchors/
    anchors.jsonl
    anchors.meta.json
```

用户仍然只需要在设置里填写 `SKILL.md`。

## Anchor 结构

每行 JSONL 是一个 anchor：

```json
{
  "id": "hmsz-xxxx",
  "character_id": "hmsz",
  "title": "剧情标题",
  "source_file": "adv_dear_hmsz_001.txt",
  "source_category": "dearness",
  "line": 68,
  "summary": "短摘要",
  "persona_dimensions": ["identity", "autonomy"],
  "tags": ["identity", "autonomy", "dearness"],
  "time_blocks": ["relationship_time"],
  "confidence": 0.86,
  "evidence_quotes": [
    {"ja": "短い原文", "zh": "短中文"}
  ]
}
```

## 生成方式

当前提供 Gakumas Localify ADV 脚本提取器：

```powershell
runtime\Scripts\python.exe resources\anchor_tools\build_gakumas_anchors.py `
  --local-files-root "E:\BaiduNetdiskDownload\DMM_GakumasLocalify_v3.2.0\gakumas-local\local-files" `
  --character-id hmsz `
  --output "skillcreater\characters\Hataya-Misuzu\skill\anchors\anchors.jsonl" `
  --limit 120
```

提取器会：

- 从 `resource/adv_*hmsz*.txt` 抽取角色对白；
- 从 `masterTrans/*.json` 尝试匹配剧情标题；
- 按关键词标注人格维度；
- 生成短证据片段、来源文件、行号和时间块标签；
- 输出短 anchor，不搬运整段剧情。

## 运行时选择

`anchor_runtime.py` 会根据：

- 当前 planning block；
- 用户输入是否偏技术/专业、身份、人设、训练、休息等；
- session 和日期；

选择一个 anchor。注入 prompt 的文本会明确写明：

```text
这是人格锚点，不是新事件，也不是用户记忆。
```

这样专业问题仍可正常回答，但角色不会轻易滑回基线助手。
