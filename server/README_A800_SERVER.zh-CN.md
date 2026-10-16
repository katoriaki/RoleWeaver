# RoleWeaver A800 服务器部署包

这个包用于在 A800 服务器上启动 RoleWeaver HTTP API。服务器只负责大模型、多模态理解、记忆和 Web/API 服务；本地电脑继续负责 Unity/VRM、摄像头、麦克风、GPT-SoVITS、LINE webhook 等外部形象和语音链路。

## 已内置的服务器配置

配置文件：

```text
server/roleweaver.a800.config.csv
```

默认加载：

```text
/public/huggingface-models/Qwen/Qwen3-Omni-30B-A3B-Instruct
```

关键设置：

```csv
model_loader_mode,omni
quantization_mode,bf16
device_map_mode,gpu
lora_path,
skill_file,
```

`lora_path` 默认留空。需要角色定义时，将 `skill_file` 指向自己的 `SKILL.md`；同目录可提供 `persona_kernel.json`。

## 一键启动

上传并解压后，在服务器进入包目录：

```bash
cd RoleWeaver_A800_Server
chmod +x server/start_a800_server.sh server/health_check.sh
server/start_a800_server.sh
```

脚本会自动：

1. 创建 `runtime/server_venv`；
2. 安装 `server/requirements-a800.txt`；
3. 使用 `server/roleweaver.a800.config.csv` 启动 API；
4. 默认仅监听 `127.0.0.1:8000`，通过 SSH 转发访问管理接口。

如果服务器环境已经装好依赖，不想每次检查安装：

```bash
ROLEWEAVER_SKIP_INSTALL=1 server/start_a800_server.sh
```

如果要改端口：

```bash
ROLEWEAVER_PORT=8011 server/start_a800_server.sh
```

## 启动后怎么访问

在服务器本机：

```bash
server/health_check.sh
```

在本地电脑建立 SSH 转发（将 `user@server` 替换为自己的登录地址）：

```bash
ssh -N -L 8000:127.0.0.1:8000 user@server
```

保持隧道运行，然后在本地电脑浏览器打开：

```text
http://127.0.0.1:8000/
```

常用接口：

```text
GET  /health
GET  /config
POST /chat
POST /chat/image
POST /sessions/{session_id}/consolidate
```

示例：

```bash
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"role-server","user_text":"你好，请介绍一下当前角色。","max_new_tokens":160}'
```

## 网络暴露方式

管理 API 目前没有应用层身份验证，且可读取 LINE 配置、修改文件和启动训练。默认使用上述 SSH 转发；公开反向代理必须先配置访问认证，并限制直接访问后端端口。

如果已有受控网络、访问白名单或带认证的反向代理，可以显式修改监听地址：

```bash
ROLEWEAVER_HOST=0.0.0.0 server/start_a800_server.sh
```

显式绑定并不会启用身份验证。不要将管理端口直接映射到无访问控制的公网隧道；LINE webhook 服务应单独暴露。

## Qwen3-Omni 行为

RoleWeaver 的 `omni` 模式会：

- 使用 `Qwen3OmniMoeForConditionalGeneration` 和 `Qwen3OmniMoeProcessor`；
- 默认请求 `return_audio=False`；
- 如果模型支持 `disable_talker()`，启动时关闭 talker；
- 把语音输出交给本地 GPT-SoVITS；
- 保留图片输入，后续可扩展音频/视频输入。

这样可以避免服务器大模型和本地 TTS 同时承担语音输出，降低链路复杂度。

## 故障排查

如果提示找不到 Qwen3-Omni 类：

```bash
runtime/server_venv/bin/python -m pip install "transformers>=5.2.0" qwen-omni-utils -U
```

如果模型目录不存在：

```bash
ls /public/huggingface-models/Qwen/Qwen3-Omni-30B-A3B-Instruct
```

如果外部访问不到：

1. 确认脚本显示监听 `127.0.0.1:8000`，并确认本地 SSH 转发已建立；
2. 确认服务器防火墙/安全组允许访问端口；
3. 先在服务器本机 `curl http://127.0.0.1:8000/health`。
## 单卡安全切换 Omni / Adapter

A800 80GB 单卡不能长期同时常驻 Qwen3-Omni-30B 和额外的 4B LoRA adapter。
如果要测试 continual adapter，请用同一个 8000 端口做模式切换，而不是另开侧车常驻。

切回主 Omni 服务：

```bash
cd /root/data/RoleWeaver_A800_Server
python3 server/a800_service_manager.py switch-main --wait
```

临时切到 4B + continual adapter 测试服务：

```bash
cd /root/data/RoleWeaver_A800_Server
python3 server/a800_service_manager.py switch-adapter --adapter-config /path/to/adapter.config.csv --wait
```

查看当前 8000 状态：

```bash
python3 server/a800_service_manager.py status
```

停止 8000：

```bash
python3 server/a800_service_manager.py stop
```

`start-adapter-sidecar` 和 `start-main-sidecar` 只用于调试。单卡常时运行时不建议使用侧车，因为它可能和主模型争抢显存并导致 OOM。

