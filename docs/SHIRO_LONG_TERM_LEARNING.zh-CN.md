# Shiro 长时间自学运行时

这个模块用于测试“白”是否能像学生一样持续学习，而不是只在聊天里短期回答。

目标链路：

```text
ChinaTextbook 教材
  -> LearningRuntime 扫描材料
  -> 白按阶段学习
  -> 每步输出可观察学习笔记和自测题
  -> Shiro emotion/thought state 回写
  -> Live2D 桌宠按情绪同步表情
  -> 生成 adapter 候选 SFT 样本
```

## 教材源

用户指定教材仓库：

```text
https://github.com/TapXWorld/ChinaTextbook
```

默认本地路径：

```text
resources/textbooks/ChinaTextbook
```

这个仓库很大，且包含拆分 PDF。若下载中断，学习运行时会显示 blocked/missing 状态，并给出恢复下载提示。只要本地目录里已有部分 `.md`、`.txt`、`.json`、`.pdf` 或图片文件，系统就可以先从已有材料开始。

## 模型与视觉能力

“唤醒 Shiro / 开启视觉配置”会把 RoleWeaver 配置改为：

- `base_model_path = C:\Users\kator\Desktop\RoleWeaver\Qwen3.5-4b`
- `lora_path = 空`
- `model_loader_mode = vision`
- `quantization_mode = 4bit`
- `device_map_mode = gpu`
- `shiro_enabled = true`
- `shiro_identity = 白`

注意：读照片能力要求该 4B 目录本身是原生视觉模型，或者至少包含可用的 `preprocessor_config.json`。如果它只是纯文本 Causal LM，`/chat/image` 会返回明确诊断错误，而不会静默伪装成看懂图片。

## API

### `POST /learning/bootstrap-shiro`

写入 Shiro 学习配置，并重置服务缓存。

### `GET /learning/status`

参数：

- `session_id`
- `subject`

返回教材路径、材料数量、学习进度、adapter 候选样本路径。

### `POST /learning/run-once`

运行一步学习。

```json
{
  "session_id": "shiro-study",
  "subject": "数学",
  "use_model": false,
  "max_new_tokens": 384
}
```

`use_model=false` 时用于验证整个工程链路，不加载大模型。

`use_model=true` 时会调用 RoleWeaver 当前本地模型；图片材料会走 `chat_once_with_image()`。

### `POST /learning/start`

启动后台学习任务。

```json
{
  "session_id": "shiro-study",
  "subject": "数学",
  "use_model": true,
  "max_steps": 9,
  "interval_seconds": 30,
  "max_new_tokens": 384
}
```

### `POST /learning/stop`

请求停止后台学习。

## Adapter 候选数据

每一步学习都会写入：

```text
data/learning/<session_id>/adapter_candidates/study_sft.jsonl
```

它是标准 messages JSONL，可作为后续“针对学习表达/解题能力”的 adapter 训练候选。它不会自动覆盖人格核心，也不会自动启用 adapter；后续仍应走 persona regression 和 adapter bank 的安全启用流程。

## 可观察输出

系统要求白不要输出隐藏推理链，而是输出可观察的学习状态：

1. 学习笔记
2. 暂时不懂的地方
3. 自测题
4. 我的答案
5. 下一步计划

这能让我们测试长期学习、进步、情绪变化和记忆写入，同时避免把不可控的内部推理当成日志保存。
