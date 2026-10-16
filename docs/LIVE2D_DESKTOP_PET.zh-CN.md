# Live2D 与 VTube Studio 接入

通用桌宠功能使用 VTube Studio 渲染用户自己的 Live2D 模型，RoleWeaver 前端提供连接、授权及表情控制。模型资产由用户单独提供，不随仓库分发。

## 配置模型元数据

启动 RoleWeaver 前，设置模型 JSON 的绝对路径：

```powershell
$env:ROLEWEAVER_PET_MODEL_JSON = "C:/models/my-avatar/avatar.model3.json"
python API.py --config roleweaver.config.csv
```

`/pet/model` 返回配置模型的元数据与表情/动作引用；具体可用表情取决于资产文件。修改配置后重新启动服务。

## 使用流程

1. 在 VTube Studio 中导入自己的模型，并启用 API。
2. 打开 RoleWeaver 的桌宠页面，连接 VTube Studio。
3. 首次连接时请求授权，并在 VTube Studio 中批准连接。
4. 使用页面提供的表情控制。实际渲染、透明窗口和动作物理由 VTube Studio 负责。

前端不会根据角色名称推断固定情绪状态。若需要自动表情，需自行设计通用状态信号及其到模型表情的映射，并单独验证。

## 接口边界

```http
GET /pet/model
```

此接口提供本地模型元数据；它不是模型下载服务，也不在浏览器中加载 `.moc3`。VTube Studio、Live2D模型与相关许可需用户自行准备。
