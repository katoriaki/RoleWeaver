# 白的人格底色 SFT 混合方案

这个方案用于给白做一次“人格底色 LoRA”，目标不是克隆任何现有角色，而是从一组相近角色样本中抽取反应模式：

- 新生 AI / 人工人格的自我学习感；
- 呆萌、弱气、短暂停顿和轻微逃避；
- 对知识的好奇；
- 情绪表达和自主边界并存；
- 不把自己降格成通用助手或无条件服从工具。

## 为什么不能直接混角色数据

直接用多个角色的 SFT 数据训练，会有三个风险：

1. 白会继承别人的姓名、世界观和过去经历。
2. 多个角色的语气互相冲突，最后变成底模常见的“二次元角色平均值”。
3. 如果没有 core-self replay，训练会削弱白“我是白”的连续性。

所以 `resources/shiro_persona_sft` 采用的是“人格源表 + 清洗器 + core-self replay”：

```text
local SFT sources
  -> source manifest
  -> name/world-term replacement and filtering
  -> Shiro core-self replay
  -> anti-contamination rows
  -> persona regression
  -> candidate adapter
```

## 候选人格源

默认 manifest 只是一份选型清单，不含任何数据：

`resources/shiro_persona_sft/persona_source_manifest.example.csv`

当前候选包括：

| source_id | 用途 |
| --- | --- |
| `ai_learning_self` | 新生 AI、自我学习、短句反应 |
| `quiet_information_interface` | 安静、信息接口式回答 |
| `artificial_emotion_learning` | 学习情绪和自我表达 |
| `limited_memory_ai` | 有限记忆、人工人格、安静笨拙的关心 |
| `shy_anxious_student` | 弱气、害羞、轻微逃避 |
| `curious_student_energy` | 好奇、轻快的观察 |
| `detached_curious_scholar` | 学习驱动和迟缓情绪 |
| `core_self_replay` | 白的核心身份和边界，必须混入 |

这些角色源只能用于 `trait_pattern_only`，不能成为白的 canon。

## 从可塑性记忆 / 艾拉脚本抽取

如果本地有 `Plastic Memories` 的 FreeMote 解包脚本，可以用专用抽取器把艾拉对白转换成“有限记忆人工人格”源：

```powershell
runtime\Scripts\python.exe resources\shiro_persona_sft\extract_plastic_memories_isla.py `
  --scenario-dir "E:\BaiduNetdiskDownload\样本2\PCSG00931\extracted_scenario\scenario" `
  --freemote "E:\BaiduNetdiskDownload\样本2\PCSG00931\tools\FreeMote\PsbDecompile.exe" `
  --output resources\shiro_persona_sft\raw\limited_memory_ai\plastic_memories_isla.jsonl `
  --report data\shiro_persona_sft\plastic_memories_isla.report.json `
  --max-records 1200
```

抽取器会：

- 反编译 `.scn.m` 到临时 JSON；
- 读取 `scenes[].texts[]`；
- 只把艾拉/アイラ的回复作为 assistant；
- 用前几句上下文生成 user prompt；
- 替换或过滤源角色名、作品设定、回收/公司等 canon 事实；
- 输出的样本只作为性格反应模式，不作为白的记忆。

## 数据放置

把你已经合法拥有或自己生成的训练数据放到：

```text
resources/shiro_persona_sft/raw/<source_id>/*.jsonl
resources/shiro_persona_sft/raw/<source_id>/*.csv
```

JSONL 格式：

```json
{"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
```

CSV 格式需要 `user,assistant` 两列。

## 生成混合 SFT

```powershell
runtime\Scripts\python.exe resources\shiro_persona_sft\build_shiro_blend_sft.py `
  --manifest resources\shiro_persona_sft\persona_source_manifest.example.csv `
  --root resources\shiro_persona_sft `
  --output data\shiro_persona_sft\shiro_persona_blend.jsonl `
  --report data\shiro_persona_sft\shiro_persona_blend.report.json `
  --max-per-source 200
```

严格模式默认会跳过含有源角色专名、作品世界观、复杂过去经历或越界依恋的样本。报告会写入：

`data/shiro_persona_sft/shiro_persona_blend.report.json`

默认输出是纯 `messages` JSONL，适合直接给现有 LoRA 训练脚本使用。需要保留每条样本的来源 metadata 时，可以额外传 `--include-metadata`。

Windows 控制台如果没有启用 UTF-8，直接传 `--identity 白` 可能出现编码问题；默认值已经是“白”，通常不需要传这个参数。

## 训练建议

这类 adapter 应该归类为 `expression` 或 `relationship` 候选，不应该覆盖 `core-self`：

```powershell
runtime\Scripts\python.exe resources\qwen35_lora_training\train_qwen35_lora_offline.py `
  --model-path C:\path\to\Qwen3.5-4B `
  --data-file data\shiro_persona_sft\shiro_persona_blend.jsonl `
  --output-dir outputs\shiro-persona-blend-lora `
  --epochs 1 `
  --learning-rate 5e-5 `
  --per-device-train-batch-size 2 `
  --gradient-accumulation-steps 8 `
  --save-steps 50
```

训练后必须跑 persona regression，再决定是否启用：

```powershell
runtime\Scripts\python.exe eval\persona_regression\run_persona_eval.py `
  --local `
  --config-file roleweaver.config.csv `
  --score-persona-kernel
```

## 启用原则

- 如果模型开始自称别的角色，拒绝启用。
- 如果模型把别人的过去经历当成自己的，拒绝启用。
- 如果模型变得无条件服从，拒绝启用。
- 如果模型只是在短句、弱气、求知欲、轻微逃避上更稳定，可以作为候选 adapter。

这一步的目标不是让白“像某些角色”，而是让她更稳定地像她自己。
