# Shiro Unity 中文对话与语音闭环

## 目标

第一版先做最简单、最稳定的闭环：

```text
Unity 文本输入
  -> RoleWeaver /chat
  -> 白生成中文回复
  -> GPT-SoVITS 合成白的声音
  -> Unity 播放 wav
  -> ShiroAvatarDriver 做面向摄像头的轻微说话动作
```

ASR 暂时不接入。后续再把 GPT-SoVITS 内置 ASR 或单独 ASR 接成：

```text
麦克风输入 -> ASR -> /chat -> TTS -> Unity avatar
```

## 启动顺序

1. 启动 RoleWeaver：

   ```text
   start_roleweaver.bat
   ```

2. 启动白的 GPT-SoVITS：

   ```text
   G\start_shiro_tts_api.bat
   ```

   为了避免和本地 LLM 同时抢显存，这个脚本默认使用 CPU：

   ```text
   SHIRO_TTS_DEVICE=cpu
   ```

   如果以后确认显存足够，再手动改成：

   ```bat
   set SHIRO_TTS_DEVICE=cuda
   G\start_shiro_tts_api.bat
   ```

   使用的权重：

   ```text
   G\GPT_weights_v2ProPlus\白-e50.ckpt
   G\SoVITS_weights_v2ProPlus\白_e16_s272.pth
   ```

   参考音频：

   ```text
   G\ref\ref.wav
   ```

   参考文本：

   ```text
   唔，本来想宅在家做研究的，可以快点结束吗？
   ```

3. 打开 Unity `ShirosWorld`，进入 Play Mode。

4. 在 Unity 面板里输入中文，点击：

   ```text
   发送并说话
   ```

## 普通模式和开发者模式

普通模式只显示：

- 连接状态；
- 简单情绪/动作状态；
- 中文对话输入；
- 白的回复；
- 语音开关。

人格自主性、记忆策略、thought policy、学习 runtime 等信息默认隐藏。只有勾选 `Developer Mode` 后才显示这些工程调试信息。

## 安全运行策略

Unity 普通模式不会自动调用 `/learning/status`，也不会自动触发模型加载。启动时只做轻量 `/health` 检查。

真正会加载 LLM 的动作只有：

- 点击 `发送并说话`；
- Developer Mode 里手动请求学习/状态；
- 其他显式模型调用。

建议第一次测试时：

1. 先开 Unity，不开 RoleWeaver/TTS，确认场景稳定。
2. 开 RoleWeaver，点 `刷新连接`。
3. 开 `G\start_shiro_tts_api.bat`，保持默认 CPU。
4. 输入短句测试。

## 当前限制

- 先支持中文。
- 当前肢体活动是轻量级 avatar driver，不是完整动作库。
- 口型/表情还没有直接绑定 VRM expression；现在先通过 speaking sway、面向摄像机、Animator 参数预留来表现说话状态。
- 后续 M2.3 会把 `Speaking`、`Emotion`、`Valence`、`Arousal` 等参数接到实际 Animator / VRM Expression。
