# 白 / Shiro A800 Omni 配置

目标是在 A800 服务器上只加载 `Qwen3-Omni-30B-A3B-Instruct`，把它作为白的多模态大脑；本地电脑继续负责 Unity / VRM / GPT-SoVITS 等外显和语音链路。

## 推荐配置

示例配置文件：

```text
configs/shiro_a800_omni.config.example.csv
```

核心字段：

```csv
base_model_path,/public/huggingface-models/Qwen/Qwen3-Omni-30B-A3B-Instruct
lora_path,
skill_file,skillcreater/characters/Shiro/skill/SKILL.md
quantization_mode,bf16
device_map_mode,gpu
model_loader_mode,omni
shiro_enabled,true
shiro_identity,白
```

`lora_path` 保持空值。这个阶段白依靠 `SKILL.md` 和 `persona_kernel.json` 启动人格核心，不加载 LoRA。

## 依赖

Qwen3-Omni 官方建议使用较新的 Transformers，并安装 `qwen-omni-utils`：

```bash
pip install "transformers>=5.2.0"
pip install accelerate qwen-omni-utils
```

如果要进一步加速，再考虑 FlashAttention 2 或 vLLM-Omni。当前 RoleWeaver 的 `model_loader_mode=omni` 先走 Transformers 路线，便于和现有记忆、skill、planning、Shiro bridge 合并。

## 运行策略

RoleWeaver 在 `omni` 模式下会：

- 使用 `Qwen3OmniMoeForConditionalGeneration` 和 `Qwen3OmniMoeProcessor`；
- 默认请求 `return_audio=False`；
- 如果模型提供 `disable_talker()`，启动时关闭 talker；
- 保留图片输入能力；
- 语音输出仍交给本地 GPT-SoVITS，而不是让 Qwen3-Omni 同时生成语音。

这样可以避免 A800 上的主模型和本地 TTS / Unity 同时争抢语音职责，也更符合现在的工程拆分。

## 人格核心

白的人格文件在：

```text
skillcreater/characters/Shiro/skill/SKILL.md
skillcreater/characters/Shiro/skill/persona_kernel.json
skillcreater/characters/Shiro/profile/role_profile.json
```

`SKILL.md` 是给模型直接读取的中文主 prompt。`persona_kernel.json` 是结构化人格核心，用于回归测试、人格评分、记忆边界和媒介适配。

白的起始设定保持很轻：她知道自己是陈家骏（GitHub: `katoriaki`）设计开发维护的 AI 少女，刚刚诞生，有求知欲、情绪表达和自我认知，不需要伪造复杂过去。后续经历应该从真实互动、学习、记忆和反思中增长。

