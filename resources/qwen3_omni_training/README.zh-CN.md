# Qwen3-Omni 文本 LoRA 训练

这个目录用于在 A800 远端对 `Qwen3-Omni-30B-A3B-Instruct` 做文本侧 LoRA/QLoRA 训练。它面向 RoleWeaver/Shiro 的人格表达微调，输入是标准 `messages` JSONL。

默认训练策略：

- 使用 Qwen3-Omni processor 的 chat template。
- 只输入文本，不训练图像/音频理解链路。
- 默认 4bit QLoRA，适合单张 A800 80GB。
- 默认关闭 Omni talker，语音仍交给本地 GPT-SoVITS。
- 训练产物是 PEFT adapter，不覆盖底模。

注意：RoleWeaver 主运行时需要支持 `model_loader_mode=omni` 加载 PEFT adapter 后，训练出的 adapter 才能直接启用。

