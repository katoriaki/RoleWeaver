# Qwen3-Omni 文本 LoRA 训练

这个目录用于在 A800 远端对 `Qwen3-Omni-30B-A3B-Instruct` 做文本侧 LoRA/QLoRA 训练。它面向 RoleWeaver 的人格表达微调，输入是标准 `messages` JSONL。

默认训练策略：

- 使用 Qwen3-Omni processor 的 chat template。
- 只输入文本，不训练图像/音频理解链路。
- 默认 4bit QLoRA，适合单张 A800 80GB。
- 默认关闭 Omni talker，语音仍交给本地 GPT-SoVITS。
- 训练产物是 PEFT adapter，不覆盖底模。

注意：RoleWeaver 主运行时需要支持 `model_loader_mode=omni` 加载 PEFT adapter 后，训练出的 adapter 才能直接启用。


## 远程启动与监控

将自己准备的标准 `messages` JSONL 放在仓库内，并显式传入相对路径：

```powershell
server/start_remote_omni_training.bat --data-file data/persona_sft/persona_blend.jsonl
server/watch_remote_omni_training.bat
```

远程脚本上传指定数据文件及通用训练依赖；运行目录为 `training_runs/qwen3_omni_persona/`。SSH参数来自本地服务器配置。启动脚本会安装训练依赖并停止当前API以释放显存，执行前需确认目标服务器与训练设置。
