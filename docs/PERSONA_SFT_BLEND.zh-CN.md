# 可配置角色的 SFT 数据混合

`resources/persona_sft/` 提供本地训练数据混合、角色名替换、来源事实过滤、去重、来源报告和 core-self replay。目标角色由 `--identity` 指定，默认示例名称为 `RoleAgent`。

外部角色样本只作为表达方式参考，不应直接变成目标角色的姓名、经历、世界观或对用户的记忆。生成的通用 replay 模板仅用于演示身份边界；正式训练前需要用经过审核的目标角色样本替换或补充。

## 数据和来源清单

复制并调整 `resources/persona_sft/persona_source_manifest.example.csv`。清单包含来源 ID、别名、用途、过滤词、混合权重和本地文件模式，不包含源作品数据。

将有权使用的数据放到：

```text
resources/persona_sft/raw/<source_id>/*.jsonl
resources/persona_sft/raw/<source_id>/*.csv
```

JSONL 使用 `messages` 数组；CSV 使用 `user,assistant` 两列。`core_self_replay` 项应指向当前角色的已审核身份与边界样本。

## 生成混合数据

```powershell
python resources/persona_sft/build_persona_blend_sft.py `
  --manifest resources/persona_sft/persona_source_manifest.example.csv `
  --root resources/persona_sft `
  --identity RoleAgent `
  --output data/persona_sft/persona_blend.jsonl `
  --report data/persona_sft/persona_blend.report.json `
  --max-per-source 200
```

默认严格过滤来源专名、设定词和禁止内容，并输出纯 `messages` JSONL。`--include-metadata` 保留每条样本的来源；报告记录接受数、过滤原因与身份参数。随机抽样和输出次序由 `--seed` 控制。

## 本地 Plastic Memories / Isla 脚本提取

源提取器保留为可选数据预处理工具。它读取本地 FreeMote 场景文件，提取指定说话人的回答、前序上下文，并替换或过滤来源身份及设定。

```powershell
python resources/persona_sft/extract_plastic_memories_isla.py `
  --scenario-dir C:/datasets/scenario `
  --freemote C:/tools/FreeMote/PsbDecompile.exe `
  --identity RoleAgent `
  --output resources/persona_sft/raw/limited_memory_ai/plastic_memories_isla.jsonl `
  --report data/persona_sft/plastic_memories_isla.report.json
```

已有反编译 JSON 时可直接调用模块中的 `build_dataset`。输出仍是表达参考，不作为目标角色的记忆或事实来源。

## 训练和验证

```powershell
python resources/qwen35_lora_training/train_qwen35_lora_offline.py `
  --model-path C:/models/base-model `
  --data-file data/persona_sft/persona_blend.jsonl `
  --output-dir outputs/persona-blend-lora
```

训练前审查样本及来源报告；训练后运行 persona regression，并用独立对话与人评检查身份、事实和表达。规则检查通过不代表人格质量已得到研究验证。保留原adapter、训练参数和数据版本，以便比较与回退。
